"""Synthetic CPU projection and interpreter fixtures. No model/provider/env calls."""
import ast
import copy
import hashlib
import importlib.util
import importlib._bootstrap_external
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from types import SimpleNamespace, MethodType, ModuleType
from typing import Union, Optional

import numpy as np
import pytest
import torch
from scripts.qd_ed_n36_arithmetic import verify_assignment
from scripts.qd_ed_n36_source import command, active

ROOT = Path(__file__).resolve().parents[1]


def extract(path, owner, names, namespace, source=None):
    tree = ast.parse((ROOT / path).read_text() if source is None else source)
    body = next(n.body for n in tree.body if isinstance(n, ast.ClassDef) and n.name == owner)
    nodes = [n for n in body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(nodes) == len(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(ROOT / path), 'exec'), namespace)


def projection_fixture(tmp_path, monkeypatch, dtype, iteration=-1):
    # Import only the real recorder and descriptor, avoiding package environment
    # initialization. Projection methods are unchanged AST-extracted source.
    core = ModuleType('core'); core.__path__ = [str(ROOT / 'core')]
    monkeypatch.setitem(sys.modules, 'core', core)
    from core.decision_evidence import DecisionEvidence
    from core.qd_ed import qd_descriptor, freeze_bounds
    class Recorder(DecisionEvidence):
        def _write_status(self): pass
        def flush(self): pass
    rec = Recorder(tmp_path, episode=0)
    rec.decision_id = 'synthetic:0'; rec.global_step = 8
    raw = np.array([1., 0., 0.], dtype=np.float64)
    adapter = SimpleNamespace(get_ee_pose_world=lambda: SimpleNamespace(position=raw.copy()), _decision_evidence=rec)
    ns = {'torch': torch, 'np': np, 'Union': Union}
    extract('core/env_adapters/libero_adapter.py', 'LiberoAdapter', ['delta_actions_to_ee_trajectory'], ns)
    adapter.delta_actions_to_ee_trajectory = MethodType(ns['delta_actions_to_ee_trajectory'], adapter)
    ns = {'torch': torch, 'Tensor': torch.Tensor, 'Optional': Optional,
          'RDT_GUIDED_ACTION_INDICES': [39,40,41,42,43,44,10], 'qd_descriptor': qd_descriptor,
          'EXECUTION_INTENT_DESCRIPTOR': 'other1', 'HEIGHT_AWARE_DESCRIPTOR': 'other2',
          'DIRECTION_HEIGHT_DESCRIPTOR': 'other3'}
    names = ['_eds_qd_descriptor', '_rdt_sample_to_trajectory_3d', '_decode_rdt_actions_for_guidance']
    extract('core/rdt_policy_steer.py', 'RDTSteer', names, ns)
    policy = SimpleNamespace(_adapter=adapter, _action_chunk_horizon=8,
                             _capture_dwell=SimpleNamespace(event_prefix='n36'))
    for name in names: setattr(policy, name, MethodType(ns[name], policy))
    actions = torch.zeros((16,64,128), dtype=dtype)
    actions[:,:8,39] = torch.arange(16, dtype=dtype)[:,None] / 16
    actions[:,:8,10] = -1
    keypoints = torch.zeros((1,3), dtype=dtype)
    rec.record('canonical_candidate_batch', candidates=actions, iter_idx=iteration)
    canonical = rec._pending[-1]
    geometry = {'iter_idx': iteration}
    descriptors = policy._eds_qd_descriptor(actions, keypoints, projection_out=geometry)
    bounds = freeze_bounds(descriptors, quantiles=(.05,.95), expand_fraction=.1, min_axis_span_m=.08)
    lo, hi = bounds.lo, bounds.hi
    norm = (descriptors - lo) / (hi - lo)
    cells = 4*torch.floor(norm[:,1]*4).long().clamp(0,3) + torch.floor(norm[:,0]*4).long().clamp(0,3)
    rec.record('n36_archive_update', geometry=geometry, iter_idx=iteration, descriptors=descriptors,
               bounds_lo=lo, bounds_hi=hi, cell_ids=cells)
    update = rec._pending[-1]
    origins = [e for e in rec._pending if e['event']=='projection_origin']
    return actions, keypoints, update, origins, canonical, torch.from_numpy(raw.copy())


def check_projection(fixture):
    actions, points, update, origins, canonical, observed = fixture
    verify_assignment(actions, points, update['values'], update['values']['iter_idx']==-1, device='cpu',
        origin_events=origins, canonical_event=canonical, update_event=update, observed_eef=observed)


@pytest.mark.parametrize('dtype', [torch.float32, torch.bfloat16])
@pytest.mark.parametrize('iteration', [-1, 0, 9])
def test_real_descriptor_adapter_recorder_join(tmp_path, monkeypatch, dtype, iteration):
    fixture = projection_fixture(tmp_path, monkeypatch, dtype, iteration)
    check_projection(fixture)
    assert not torch.cuda.is_initialized()


@pytest.mark.parametrize('fault', ['cast_equivalent', 'event_raw', 'both_raw', 'missing', 'reordered',
    'candidate', 'occurrence', 'iteration', 'decision', 'step', 'sequence', 'cast', 'projection', 'action', 'observation'])
def test_exact_origin_negatives(tmp_path, monkeypatch, fault):
    fixture = projection_fixture(tmp_path, monkeypatch, torch.bfloat16)
    check_projection(fixture)
    actions, points, update, origins, canonical, observed = copy.deepcopy(fixture)
    g = update['values']['geometry']; values = origins[0]['values']
    if fault in ('cast_equivalent', 'both_raw'):
        g['source_origins'][0][0] = 1.001
        assert torch.equal(g['source_origins'][0].bfloat16(), observed.bfloat16())
    if fault in ('event_raw', 'both_raw'): values['source_eef_position'][0] = 1.001
    if fault == 'missing': origins.pop()
    if fault == 'reordered':
        origins[:2] = reversed(origins[:2]); g['projection_origin_sequences'][:2] = reversed(g['projection_origin_sequences'][:2])
    if fault in ('candidate', 'occurrence', 'iteration'):
        values['n36_descriptor_identity'][{'candidate':'candidate_index','occurrence':'occurrence_id','iteration':'iter_idx'}[fault]] += 1
    if fault == 'decision': origins[0]['decision_id'] = 'wrong'
    if fault == 'step': origins[0]['global_step'] += 8
    if fault == 'sequence': g['projection_origin_sequences'][0] = canonical['sequence']
    if fault == 'cast': g['cast_origins'][0][0] += .5
    if fault == 'projection': values['projected_xyz'][0,0] += .5
    if fault == 'action': values['action_sequence'][0,0] += .5
    if fault == 'observation': observed[0] = 1.001
    for e in origins: e['producer_PASS'] = True
    with pytest.raises((ValueError, KeyError)):
        check_projection((actions, points, update, origins, canonical, observed))


def poison(path, frozen, stale):
    assert len(frozen.encode()) == len(stale.encode())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frozen)
    stat = path.stat()
    cache = Path(importlib.util.cache_from_source(str(path)))
    cache.parent.mkdir(exist_ok=True)
    cache.write_bytes(importlib._bootstrap_external._code_to_timestamp_pyc(
        compile(stale, str(path), 'exec'), int(stat.st_mtime), stat.st_size))
    return cache


def bootstrap_tree(tmp_path):
    scripts = tmp_path / 'scripts'; scripts.mkdir()
    for name in ('qd_ed_n36_bootstrap.py', 'qd_ed_n36_source.py'):
        shutil.copyfile(ROOT / 'scripts' / name, scripts / name)
    return tmp_path


def run(argv, root):
    return subprocess.run(argv, cwd=root, env={**os.environ, 'PYTHONPATH': str(root)},
        capture_output=True, text=True, timeout=60)


def test_stale_cache_repro_and_frozen_source_execution(tmp_path):
    root = bootstrap_tree(tmp_path)
    # Same timestamp/size-valid payload construction as review repro-v1.py.
    frozen = 'def value():\n    return "frozen"\n'
    stale = 'def value():\n    return "stale!"\n'
    cache = poison(root/'fixture.py', frozen, stale)
    before = cache.read_bytes()
    plain = run([sys.executable, '-B', '-c', 'import fixture; print(fixture.value())'], root)
    assert plain.returncode == 0 and plain.stdout.strip() == 'stale!'
    (root/'check.py').write_text('import fixture\nprint(fixture.value())\n')
    safe = run(command(sys.executable, root, 'check'), root)
    assert safe.returncode == 0, safe.stderr
    assert safe.stdout.strip() == 'frozen'
    assert cache.read_bytes() == before
    assert (root/'fixture.py').read_text() == frozen


def test_unsafe_entry_rejects_and_sourceless_rejects(tmp_path):
    with pytest.raises(ValueError, match='startup absent'): active()
    root = bootstrap_tree(tmp_path)
    bad = run([sys.executable, str(root/'scripts/qd_ed_n36_bootstrap.py'), 'unused'], root)
    assert bad.returncode != 0 and 'requires -I -S -B' in bad.stderr
    cache = poison(root/'only.py', 'value = "frozen"\n', 'value = "stale!"\n')
    shutil.copyfile(cache, root/'only.pyc'); (root/'only.py').unlink()
    (root/'check.py').write_text('import only\n')
    bad = run(command(sys.executable, root, 'check'), root)
    assert bad.returncode != 0 and 'disallows sourceless' in bad.stderr

    with zipfile.ZipFile(root/'cache.zip', 'w') as archive:
        archive.write(root/'only.pyc', 'only.pyc')
    for statement in ("sys.path.insert(0,str(root/'cache.zip')); import only",
                      "zipimport.zipimporter(str(root/'cache.zip')).load_module('only')"):
        (root/'check.py').write_text("import sys,zipimport\nfrom pathlib import Path\nroot=Path(__file__).parent\n"+statement+'\n')
        bad = run(command(sys.executable, root, 'check'), root)
        assert bad.returncode != 0 and 'disallows sourceless' in bad.stderr


def test_actual_runner_to_worker_entry_ignores_poisoned_dependencies(tmp_path):
    # Isolated source copy: suppress only core's unrelated environment package
    # initializer. Actual runner, worker, proposal and auditor imports execute;
    # --help exits before any authority, provider, model or simulator operation.
    root = bootstrap_tree(tmp_path)
    for folder in ('scripts', 'core'):
        (root/folder).mkdir(exist_ok=True)
        for path in (ROOT/folder).glob('*.py'):
            shutil.copyfile(path, root/folder/path.name)
    (root/'core/__init__.py').write_text('')
    for relative in ('scripts/qd_ed_n36_runner.py', 'scripts/qd_ed_n36_worker.py',
                     'scripts/qd_ed_n36_arithmetic.py', 'scripts/qd_ed_n31_reference.py',
                     'core/qd_nonprogress_tangent.py', 'core/rdt_policy_steer.py'):
        path = root/relative; frozen = path.read_text()
        stale = "raise RuntimeError('STALE_EXECUTED')\n"
        stale += '#' * (len(frozen.encode()) - len(stale))
        poison(path, frozen, stale)
    (root/'entry_check.py').write_text('''import subprocess, sys
from scripts import qd_ed_n36_runner as runner
from scripts import qd_ed_n36_source as source
from pathlib import Path
root=Path(__file__).parent
source.active()
argv=runner.worker_command(sys.executable,root,root/'absent-context.json','0'*64)
assert argv==source.command(sys.executable,root,'scripts.qd_ed_n36_worker','--context',str(root/'absent-context.json'),'--context-sha256','0'*64)
result=subprocess.run(argv+['--help'],capture_output=True,text=True,timeout=40)
assert result.returncode==0,(result.stdout,result.stderr)
assert '--context-sha256' in result.stdout
import torch
assert not torch.cuda.is_initialized()
# Execute the actual decoder method's source-loaded code without constructing a
# policy/model or importing unrelated environment services. Its module cache is
# poisoned too. The method code is taken from the loader's compiled module.
from importlib.machinery import SourceFileLoader
from types import CodeType,FunctionType,SimpleNamespace
code=SourceFileLoader('core.rdt_policy_steer',str(root/'core/rdt_policy_steer.py')).get_code('core.rdt_policy_steer')
cls=next(c for c in code.co_consts if isinstance(c,CodeType) and c.co_name=='RDTSteer')
method=next(c for c in cls.co_consts if isinstance(c,CodeType) and c.co_name=='_decode_rdt_actions_for_guidance')
indices=[39,40,41,42,43,44,10]
decode=FunctionType(method,{'RDT_GUIDED_ACTION_INDICES':indices,'__builtins__':__builtins__})
samples=torch.arange(64*128,dtype=torch.float32).reshape(1,64,128)
assert torch.equal(decode(SimpleNamespace(_action_chunk_horizon=8),samples),samples[:,:8,indices])
# Synthetic inventory for checking the binding mechanism, not a release anchor.
state=source.active()
frozen={'files':[{'path':str(p.relative_to(root)),'sha256':source.sha(p)} for p in root.rglob('*.py')]}
runtime={'modules':{},'generated_modules':{}}
for name,path in list(state.compiled)+[(n,p) for n,(p,h) in state.startup_sources.items()]:
    if not Path(path).resolve().is_relative_to(root):
        runtime['modules'][name]={'path':str(Path(path).resolve()),'sha256':source.sha(path)}
receipt=source.attest(root,frozen,runtime)
loaded={'reference':{'path':'scripts/qd_ed_n31_reference.py','sha256':source.sha(root/'scripts/qd_ed_n31_reference.py')}}
source.verify_receipt(receipt,root,frozen,runtime,loaded=loaded)
receipt['compiled']=[r for r in receipt['compiled'] if r['module']!='scripts.qd_ed_n31_reference']
try: source.verify_receipt(receipt,root,frozen,runtime,loaded=loaded)
except ValueError as e: assert 'missing executable receipt' in str(e)
else: raise AssertionError('missing dependency executable receipt accepted')
print('actual runner-to-worker source entry verified')
''')
    result = run(command(sys.executable, root, 'entry_check'), root)
    assert result.returncode == 0, result.stderr
    assert 'actual runner-to-worker source entry verified' in result.stdout
    result = run(command(sys.executable, root, 'scripts.qd_ed_n36_runner', '--help'), root)
    assert result.returncode == 0 and '--plan-sha256' in result.stdout, result.stderr


def test_compiled_bytes_join_rejects_changed_source_and_loader(tmp_path):
    root = bootstrap_tree(tmp_path)
    (root/'fixture.py').write_text('value = "frozen"\n')
    (root/'attest_check.py').write_text('''import sys, hashlib
from pathlib import Path
from scripts import qd_ed_n36_source as source
import fixture
root=Path(__file__).parent
state=source.active()
# Explicitly synthetic inventories; this does not attest the installed runtime.
def inventories():
    files=[{'path':str(p.relative_to(root)),'sha256':source.sha(p)} for p in root.rglob('*.py')]
    runtime={'modules':{},'generated_modules':{}}
    for name,module in list(sys.modules.items()):
        path=getattr(module,'__file__',None)
        if path and Path(path).is_file() and not Path(path).resolve().is_relative_to(root):
            runtime['modules'][name]={'path':str(Path(path).resolve()),'sha256':source.sha(path)}
    return {'files':files},runtime
frozen,runtime=inventories()
receipt=source.attest(root,frozen,runtime)
assert any(r['module']=='fixture' for r in receipt['compiled'])
(root/'fixture.py').write_text('value = "other!"\\n')
new,_=inventories()
try: source.attest(root,new,runtime)
except ValueError as e: assert 'compiled source not frozen' in str(e)
else: raise AssertionError('live compiled bytes not checked')
import importlib.machinery
importlib.machinery.SourceFileLoader.get_code=lambda *a:None
try: source.active()
except ValueError as e: assert 'loader replaced' in str(e)
else: raise AssertionError('loader replacement accepted')
print('compiled source joins verified')
''')
    result = run(command(sys.executable, root, 'attest_check'), root)
    assert result.returncode == 0, result.stderr
    assert 'compiled source joins verified' in result.stdout


@pytest.mark.parametrize('dtype', [torch.float32, torch.bfloat16])
@pytest.mark.parametrize('capture', [False, True])
def test_older_projection_controls_preserve_bytes_and_events(dtype, capture):
    path = 'core/env_adapters/libero_adapter.py'
    baseline = subprocess.check_output(['git','show','e7cdf2c09a60ffb1d248f073c5639303b2ef01fa:'+path],cwd=ROOT,text=True)
    results = []
    for source in (baseline, (ROOT/path).read_text()):
        events = []; reads = []
        def pose():
            reads.append(1)
            return SimpleNamespace(position=np.array([1.,-0.,.123],dtype=np.float64))
        recorder = SimpleNamespace(record=lambda *a,**k: events.append((a,k)))
        adapter = SimpleNamespace(get_ee_pose_world=pose, _decision_evidence=recorder)
        ns = {'torch':torch,'np':np,'Union':Union}
        extract(path,'LiberoAdapter',['delta_actions_to_ee_trajectory'],ns,source)
        actions = torch.arange(56,dtype=dtype).reshape(8,7)/64
        metadata = {} if capture else None
        output = ns['delta_actions_to_ee_trajectory'](adapter,actions,origin_out=metadata)
        results.append((output,metadata,events,reads))
    from scripts.qd_ed_n31_reference import same
    assert same(results[0][0],results[1][0]) and results[0][3]==results[1][3]==[1]
    if capture: assert same(results[0][1]['source_origin'],results[1][1]['source_origin'])
    for (_,a),(_,b) in zip(results[0][2],results[1][2]):
        assert a.keys()==b.keys()
        for k in a: assert same(torch.as_tensor(a[k]),torch.as_tensor(b[k]))


def test_main_source_entry_preserves_script_semantics(tmp_path):
    root = bootstrap_tree(tmp_path)
    frozen = '''import sys
assert __name__ == '__main__' and __spec__ is None and __package__ == ''
assert sys.argv[0] == __file__ and sys.argv[1:] == ['argument']
print('frozen-main')
'''
    stale = frozen.replace('frozen-main', 'stale!-main')
    poison(root/'main.py', frozen, stale)
    (root/'entry_check.py').write_text('''import sys
from pathlib import Path
from scripts import qd_ed_n36_source as source
root=Path(__file__).parent
sys.argv=[str(root/'main.py'),'argument']
before=sys.modules['__main__']
source.run_main(root/'main.py')
assert sys.modules['__main__'] is before
assert ('main',str(root/'main.py')) in source.active().compiled
''')
    result = run(command(sys.executable,root,'entry_check'),root)
    assert result.returncode == 0 and result.stdout.strip()=='frozen-main',result.stderr
