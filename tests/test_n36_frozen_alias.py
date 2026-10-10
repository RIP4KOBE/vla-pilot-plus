"""Closed alias proof tests; synthetic contexts confer no production authority."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import pytest
from scripts import qd_ed_n36_source as execution, qd_ed_n34_source as closure


def process():
    return {'pid':os.getpid(), 'proc_start_ticks':Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19],
            'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}


@pytest.fixture
def proof():
    record = {'path':str(Path(os.path.__file__).resolve()), 'sha256':execution.sha(os.path.__file__)}
    runtime = {'modules':{'os.path':record.copy(), 'posixpath':record.copy()},
               'interpreter':execution.interpreter_identity(), 'required_after':['episode.only']}
    binding = {'context':{'path':'/synthetic/context','sha256':'a'*64},
               'runtime_closure':{'path':'/synthetic/runtime','sha256':'b'*64},
               'process':process(), 'phase':'runtime_before'}
    claim = execution.live_alias(runtime, binding)
    receipt = {'schema':'n36-source-execution-v2', 'binding':binding.copy(),
               'interpreter':runtime['interpreter'], 'frozen_modules':['posixpath'],
               'frozen_aliases':{'os.path':claim}}
    observed = {'schema':'n34-runtime-receipt-v2', 'binding':binding.copy(),
                'modules':copy.deepcopy(runtime['modules']), 'generated_modules':{}}
    return runtime, binding, receipt, observed


def test_live_proof_and_parent_binding(proof):
    runtime,binding,receipt,observed = proof
    assert execution.verify_alias(receipt,runtime,observed,binding) == {'os.path'}
    closure.verify_runtime_receipt(runtime, observed, binding=binding, after=False)
    with pytest.raises(ValueError,match='incomplete'):
        closure.verify_runtime_receipt(runtime, observed, binding=binding, after=True)


@pytest.mark.parametrize('fault', ['object','canonical_absent','loader','origin','name','module_name','module_loader','lexical_file','not_frozen','hash','path','interpreter','process'])
def test_producer_rejects_substitution(proof, monkeypatch, fault):
    runtime,binding,_,_ = proof
    canonical = sys.modules['posixpath']
    if fault == 'object': monkeypatch.setitem(sys.modules,'os.path',SimpleNamespace(**vars(canonical)))
    elif fault == 'canonical_absent': monkeypatch.delitem(sys.modules,'posixpath')
    elif fault in ('loader','origin','name'):
        spec = copy.copy(canonical.__spec__)
        setattr(spec, {'loader':'loader','origin':'origin','name':'name'}[fault], None if fault=='loader' else 'wrong')
        monkeypatch.setattr(canonical,'__spec__',spec)
    elif fault == 'module_name': monkeypatch.setattr(canonical,'__name__','other')
    elif fault == 'module_loader': monkeypatch.setattr(canonical,'__loader__',None)
    elif fault == 'lexical_file': monkeypatch.setattr(canonical,'__file__',str(Path(canonical.__file__).parent)+'/./posixpath.py')
    elif fault == 'not_frozen': monkeypatch.setattr(execution._imp,'is_frozen',lambda _:False)
    elif fault in ('hash','path'): runtime['modules']['os.path']['sha256' if fault=='hash' else 'path'] = 'wrong'
    elif fault == 'interpreter': runtime['interpreter']['sha256'] = '0'*64
    else: binding['process']['pid'] += 1
    with pytest.raises(ValueError): execution.live_alias(runtime,binding)


@pytest.mark.parametrize('fault', ['context','process','phase','closure','interpreter','interpreter_path',
    'hash','path','canonical_absent','canonical_hash','frozen_absent','alias_name','extra_alias','boolean','loader','origin','spec_name','unbound','receipt_binding','schema','inventory_canonical_absent','frozen_boolean'])
def test_parent_rejects_mismatched_receipts(proof, fault):
    runtime,binding,receipt,observed = copy.deepcopy(proof)
    claim = receipt['frozen_aliases']['os.path']
    if fault in ('context','process','phase','closure'):
        key = 'runtime_closure' if fault=='closure' else fault
        binding = copy.deepcopy(binding)
        if fault=='phase': binding[key]='runtime_after'
        elif fault=='process': binding[key]['pid']+=1
        else: binding[key]['sha256']='f'*64
    elif fault.startswith('interpreter'): receipt['interpreter']['path' if fault.endswith('path') else 'sha256'] = 'wrong'
    elif fault in ('hash','path'): claim['records']['os.path']['sha256' if fault=='hash' else 'path'] = 'wrong'
    elif fault == 'canonical_absent': del observed['modules']['posixpath']
    elif fault == 'canonical_hash': observed['modules']['posixpath']['sha256'] = 'wrong'
    elif fault == 'frozen_absent': receipt['frozen_modules'] = []
    elif fault == 'alias_name': claim['alias'] = 'other'
    elif fault == 'extra_alias': receipt['frozen_aliases']['other'] = copy.deepcopy(claim)
    elif fault == 'boolean': claim['same_module_object'] = 1
    elif fault in ('loader','origin','spec_name'): claim[fault] = 'wrong'
    elif fault == 'unbound': binding = None
    elif fault == 'schema': receipt['schema']='n36-source-execution-v1'
    elif fault == 'inventory_canonical_absent': del runtime['modules']['posixpath']
    elif fault == 'frozen_boolean': claim['is_frozen']=1
    else: observed['binding'] = {}
    with pytest.raises(ValueError): execution.verify_alias(receipt,runtime,observed,binding)


def complete_fixture(root, proof):
    runtime,binding,receipt,observed = proof
    for alias, canonical in execution.IMPORTLIB_FROZEN_PAIRS:
        record = {'path': str(Path(sys.modules[canonical].__file__).resolve()),
                  'sha256': execution.sha(sys.modules[canonical].__file__)}
        for name in (alias, canonical):
            runtime['modules'][name] = record.copy()
            observed['modules'][name] = record.copy()
        receipt['frozen_modules'].append(canonical)
    receipt['frozen_modules'].sort()
    receipt['frozen_importlib_aliases'] = execution.live_importlib_aliases(runtime, binding)
    receipt['search_prefix'] = str(Path(sys.executable).resolve().parent.parent)
    receipt['search_path'] = [str(root)]
    names = ['scripts.qd_ed_n36_worker','scripts.qd_ed_n36_native','scripts.qd_ed_n36_arithmetic',
             'scripts.audit_decision_evidence','scripts.qd_ed_n36_source', 'ordinary']
    files = [{'path':n.replace('.','/')+'.py', 'sha256':'c'*64} for n in names]
    files.append({'path':'scripts/qd_ed_n36_bootstrap.py','sha256':'d'*64})
    receipt.update(bootstrap={'path':str(root/'scripts/qd_ed_n36_bootstrap.py'),'sha256':'d'*64},
                   compiled=[{'module':n,'path':str(root/f['path']),'sha256':f['sha256']} for n,f in zip(names,files)],
                   startup_source_only=[])
    for name in ('encodings','encodings.aliases','encodings.utf_8'):
        record={'path':'/synthetic/'+name+'.py','sha256':'e'*64}
        runtime['modules'][name]=record
        observed['modules'][name]=record
        receipt['startup_source_only'].append({'module':name,**record})
    observed['modules']['ordinary']={'path':str(root/'ordinary.py'),'sha256':'c'*64}
    runtime['modules']['ordinary']=observed['modules']['ordinary']
    return {'files':files}


@pytest.mark.parametrize('fault', [None,'ordinary_missing','arbitrary_same_path','equal_hash_substitution'])
def test_full_parent_exemption_is_only_closed_aliases(proof,tmp_path,fault):
    runtime,binding,receipt,observed=proof
    source=complete_fixture(tmp_path,proof)
    if fault=='ordinary_missing': receipt['compiled']=[r for r in receipt['compiled'] if r['module']!='ordinary']
    elif fault=='arbitrary_same_path':
        runtime['modules']['arbitrary']=runtime['modules']['posixpath'].copy()
        observed['modules']['arbitrary']=runtime['modules']['arbitrary']
    elif fault=='equal_hash_substitution': observed['modules']['os.path']['path']='/substitute/posixpath.py'
    if fault:
        with pytest.raises(ValueError): execution.verify_receipt(receipt,tmp_path,source,runtime,runtime_receipt=observed,binding=binding)
    else: execution.verify_receipt(receipt,tmp_path,source,runtime,runtime_receipt=observed,binding=binding)


@pytest.fixture(scope='module', params=['runtime_before', 'runtime_after'])
def parent_anchored_receipts(tmp_path_factory, request):
    """Capture expectations from files and /proc while the child awaits G."""
    tmp_path = tmp_path_factory.mktemp('parent-anchor-' + request.param)
    root = Path(__file__).resolve().parents[1]
    record = {'path':str(Path(os.path.__file__).resolve()), 'sha256':execution.sha(os.path.__file__)}
    # This required_after set is CPU alias coverage only, never production coverage.
    runtime = {'interpreter':execution.interpreter_identity(),
               'modules':{'os.path':record,'posixpath':record},
               'required_after':['os.path', 'posixpath', '_frozen_importlib',
                                 '_frozen_importlib_external']}
    runtime_path = tmp_path/'runtime.json'
    runtime_path.write_text(json.dumps(runtime))
    context = tmp_path/'context.json'
    context.write_text(json.dumps({'release_enabled':False, 'cpu_only':True}))
    context_ref = {'path':str(context), 'sha256':execution.sha(context)}
    command = execution.command(sys.executable, root, 'scripts.test_n36_parent_anchor_child',
                                str(runtime_path), str(context), request.param)
    child = subprocess.Popen(command, env={**os.environ, 'CUDA_VISIBLE_DEVICES':''},
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        # Bound readiness independently of communicate; surface stderr on early exit.
        import selectors
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            assert selector.select(timeout=20), 'isolated child readiness timeout'
        ready = child.stdout.readline().strip()
        if ready != 'READY':
            stdout, stderr = child.communicate(timeout=5)
            pytest.fail(f'isolated child readiness: {ready!r}; stdout={stdout}; stderr={stderr}')
        frozen_path = runtime_path.with_name('observed-runtime.json')
        runtime = json.loads(frozen_path.read_text())
        assert runtime['interpreter'] == execution.interpreter_identity()
        assert runtime['modules']['os.path'] == runtime['modules']['posixpath'] == record
        assert all(execution.sha(row['path']) == row['sha256'] for row in runtime['modules'].values())
        runtime_ref = {'path':str(frozen_path), 'sha256':execution.sha(frozen_path)}
        identity = {'pid':child.pid,
                    'proc_start_ticks':Path(f'/proc/{child.pid}/stat').read_text().rsplit(')',1)[1].split()[19],
                    'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
        binding = {'context':context_ref, 'runtime_closure':runtime_ref,
                   'process':identity, 'phase':request.param}
        # Persist the independently captured expectation BEFORE releasing receipt production.
        anchor = tmp_path/'parent-before-handoff.json'
        anchor.write_text(json.dumps({'command':command, 'expected_binding':binding,
                                      'child_poll':child.poll(), 'ready':ready}, indent=2)+'\n')
        assert child.poll() is None
        stdout, stderr = child.communicate('G', timeout=20)
        (tmp_path/'child.stdout.log').write_text(stdout)
        (tmp_path/'child.stderr.log').write_text(stderr)
        assert child.returncode == 0, stderr
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=5)
    receipts = json.loads(stdout)
    assert execution.sha(context) == context_ref['sha256']
    assert execution.sha(frozen_path) == runtime_ref['sha256']
    assert json.loads(anchor.read_text())['expected_binding'] == binding
    (tmp_path/'live-receipt.json').write_text(json.dumps({
        'command':command, 'expected_binding':binding, **receipts,
        'full_after_coverage':False}, indent=2)+'\n')
    return runtime, binding, receipts['execution'], receipts['runtime']


def test_fresh_source_bootstrap_process_receipt(parent_anchored_receipts):
    """Both phases join actual file hashes to an independently captured process."""
    runtime, binding, receipt, observed = parent_anchored_receipts
    assert execution.verify_importlib_aliases(receipt, runtime, observed, binding) == {
        'os.path', 'importlib._bootstrap', 'importlib._bootstrap_external'}
    closure.verify_runtime_receipt(runtime, observed, binding=binding,
                                   after=binding['phase'] == 'runtime_after')
    incomplete = copy.deepcopy(runtime)
    incomplete['required_after'].append('episode.only')
    with pytest.raises(ValueError, match='incomplete'):
        closure.verify_runtime_receipt(incomplete, observed, binding=binding, after=True)


@pytest.mark.parametrize('target', ['parent', 'execution', 'runtime', 'all_receipts'])
@pytest.mark.parametrize('field', ['context.path', 'context.sha256', 'runtime_closure.path',
    'runtime_closure.sha256', 'process.pid', 'process.boot_id', 'process.proc_start_ticks', 'phase'])
def test_fresh_parent_anchor_rejects_substitution(parent_anchored_receipts, target, field):
    runtime, binding, receipt, observed = copy.deepcopy(parent_anchored_receipts)
    changed = copy.deepcopy(binding)
    if field == 'phase':
        changed['phase'] = 'runtime_after' if binding['phase'] == 'runtime_before' else 'runtime_before'
    else:
        section, key = field.split('.')
        value = changed[section][key]
        if key == 'pid': value += 1
        elif key == 'proc_start_ticks': value = str(int(value) + 1)
        elif key == 'sha256': value = ('0' if value[0] != '0' else '1') + value[1:]
        else: value += '.substituted'
        changed[section][key] = value
    if target == 'parent': binding = changed
    elif target == 'execution': receipt['binding'] = changed
    elif target == 'runtime': observed['binding'] = changed
    else:
        # Internally consistent forgery must still fail against the independent parent.
        receipt['binding'] = copy.deepcopy(changed)
        observed['binding'] = copy.deepcopy(changed)
        for claim in list(receipt['frozen_aliases'].values()) + list(receipt['frozen_importlib_aliases'].values()):
            claim['binding'] = copy.deepcopy(changed)
    with pytest.raises(ValueError, match='context/process/phase differs'):
        execution.verify_importlib_aliases(receipt, runtime, observed, binding)
    if target != 'execution':
        with pytest.raises(ValueError, match='schema/binding differs'):
            closure.verify_runtime_receipt(runtime, observed, binding=binding,
                                           after=binding['phase'] == 'runtime_after')
