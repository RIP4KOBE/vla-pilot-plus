"""Prospective CPU alias rules; synthetic inventories never authorize dispatch."""
import copy
import importlib
import importlib.machinery
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from scripts import qd_ed_n34_source as source
from test_n34_generated_runtime import live, prospective, record, PYTHON, SITE, ROOT


def native(name, path):
    # Inert native module representation; never dlopen synthetic fixture bytes.
    return SimpleNamespace(__name__=name, __file__=str(path),
                           __spec__=importlib.machinery.ModuleSpec(name, None, origin=str(path)))


@pytest.fixture
def alias_live(live, tmp_path):
    closure, modules, _ = live
    suffix = importlib.machinery.EXTENSION_SUFFIXES[0]
    for index, name in enumerate(source.CYUTILITY_TARGETS):
        directory = tmp_path / str(index)
        directory.mkdir()
        path = directory / ('_cyutility' + suffix)
        path.write_bytes(('inert-native-' + name).encode())
        closure['modules'][name] = record(path)
        modules[name] = native(name, path)
    closure['modules']['_cyutility'] = closure['modules'][source.CYUTILITY_TARGETS[0]].copy()
    closure['module_aliases'] = source.build_cyutility_alias_rule(closure['modules'])
    closure['required_after'].append('_cyutility')
    modules['_cyutility'] = modules[source.CYUTILITY_TARGETS[0]]
    return closure, modules


@pytest.mark.parametrize('target', source.CYUTILITY_TARGETS)
def test_allowed_alias_and_receipt(alias_live, target):
    closure, modules = alias_live
    modules['_cyutility'] = modules[target]
    receipt = source.attest_runtime_receipt(closure, closure['runtime'], binding={}, after=True)
    assert receipt['module_aliases']['_cyutility']['target'] == target
    assert receipt['module_aliases']['_cyutility']['same_module_object'] is True
    source.verify_runtime_receipt(closure, receipt, binding={}, after=True)


@pytest.mark.parametrize('fault', ['unknown_path', 'changed_hash', 'identity', 'missing_target',
                                   'missing_file', 'spec_origin', 'spec_name', 'module_name',
                                   'ordinary_alias', 'ordinary_hash', 'ordinary_unknown'])
def test_live_rejections_retain_origins(alias_live, tmp_path, fault):
    closure, modules = alias_live
    target = source.CYUTILITY_TARGETS[0]
    module = modules['_cyutility']
    failure_name = '_cyutility'
    if fault == 'unknown_path':
        path = tmp_path / 'unknown.so'
        path.write_bytes(Path(module.__file__).read_bytes())
        module.__file__ = str(path)
    elif fault == 'changed_hash':
        Path(module.__file__).write_bytes(b'changed native bytes')
    elif fault == 'identity':
        modules['_cyutility'] = native(target, Path(module.__file__))
    elif fault == 'missing_target':
        del modules[target]
    elif fault == 'missing_file':
        module.__file__ = None
    elif fault == 'spec_origin':
        module.__spec__.origin += '.unexpected'
    elif fault == 'spec_name':
        module.__spec__.name = '_cyutility'
    elif fault == 'module_name':
        module.__name__ = '_cyutility'
    elif fault == 'ordinary_alias':
        modules['unapproved_alias'] = module
        failure_name = 'unapproved_alias'
    else:
        path = tmp_path / 'ordinary.py'
        path.write_text('frozen = True\n')
        modules['ordinary'] = native('ordinary', path)
        failure_name = 'ordinary'
        if fault == 'ordinary_hash':
            closure['modules']['ordinary'] = record(path)
            path.write_text('changed = True\n')
    with pytest.raises(source.RuntimeOriginError) as rejected:
        source.attest_runtime_receipt(closure, closure['runtime'], binding={}, after=True)
    diagnostic = rejected.value.runtime_failure_origin
    if fault in ('changed_hash', 'unknown_path'):
        failure_name = target  # Frozen bytes fail before walking live modules.
    assert diagnostic['name'] == failure_name
    assert diagnostic['file'] == modules[failure_name].__file__
    assert 'origin=' in str(rejected.value)
    json.dumps(diagnostic)
    if diagnostic['file'] is not None:
        assert diagnostic['sha256'] == source.w.sha(diagnostic['resolved_path'])
    if fault == 'identity':
        assert not any(diagnostic['qualified_identity'].values())
    if fault == 'spec_origin':
        assert diagnostic['spec_origin'].endswith('.unexpected')


@pytest.mark.parametrize('fault', ['unknown_target', 'unfrozen_target', 'changed_rule_hash',
                                   'empty', 'extra_alias', 'wrong_rule', 'not_native', 'legacy'])
def test_rule_rejects_expansion(alias_live, fault):
    closure, _ = alias_live
    rule = closure['module_aliases']['_cyutility']
    target = source.CYUTILITY_TARGETS[0]
    if fault == 'unknown_target': rule['targets']['other._cyutility'] = rule['targets'][target]
    elif fault == 'unfrozen_target': del closure['modules'][target]
    elif fault == 'changed_rule_hash': rule['targets'][target]['sha256'] = '0' * 64
    elif fault == 'empty': rule['targets'] = {}
    elif fault == 'extra_alias': closure['module_aliases']['other'] = copy.deepcopy(rule)
    elif fault == 'wrong_rule': rule['rule'] = 'unreviewed'
    elif fault == 'not_native':
        ordinary = closure['modules'][source.TEMPLATE_NAME]
        rule['targets'][target] = ordinary
        closure['modules'][target] = ordinary
    elif fault == 'legacy': closure['schema'] = 'n34-runtime-source-closure-v1'
    with pytest.raises(ValueError): source.verify_runtime(closure, closure['runtime'])


def test_no_rule_preserves_strict_legacy_binding(alias_live):
    closure, modules = alias_live
    del closure['module_aliases']
    modules['_cyutility'] = modules['scipy._cyutility']
    with pytest.raises(source.RuntimeOriginError, match='loaded runtime not frozen: _cyutility'):
        source.attest_runtime(closure, closure['runtime'])


@pytest.mark.parametrize('fault', ['identity_false', 'identity_number', 'target', 'hash', 'path',
                                   'qualified_absent', 'qualified_hash', 'evidence_absent',
                                   'extra_evidence', 'schema'])
def test_parent_rejects_tampered_alias_receipt(alias_live, fault):
    closure, _ = alias_live
    receipt = source.attest_runtime_receipt(closure, closure['runtime'], binding={}, after=True)
    claim = receipt['module_aliases']['_cyutility']
    if fault == 'identity_false': claim['same_module_object'] = False
    elif fault == 'identity_number': claim['same_module_object'] = 1
    elif fault == 'target': claim['target'] = 'unknown._cyutility'
    elif fault in ('hash', 'path'):
        claim['record'] = dict(claim['record'])
        claim['record']['sha256' if fault == 'hash' else 'path'] = 'wrong'
    elif fault == 'qualified_absent': del receipt['modules'][claim['target']]
    elif fault == 'qualified_hash': receipt['modules'][claim['target']] = {'path': 'wrong', 'sha256': 'wrong'}
    elif fault == 'evidence_absent': receipt['module_aliases'] = {}
    elif fault == 'extra_evidence': receipt['module_aliases']['other'] = copy.deepcopy(claim)
    elif fault == 'schema': receipt['schema'] = 'n34-runtime-receipt-v2'
    with pytest.raises(ValueError): source.verify_runtime_receipt(closure, receipt, binding={}, after=True)


@pytest.mark.parametrize('order', list(itertools.permutations(('pandas', 'scipy.linalg', 'sklearn.cluster'))))
def test_real_import_orders(order):
    program = r'''
import importlib, json, sys
from pathlib import Path
from scripts import qd_ed_n34_source as source
from test_n34_generated_runtime import prospective, record, SITE, ROOT
closure = prospective()
# Bind qualified native files BEFORE importing any of the three packages.
for name in source.CYUTILITY_TARGETS:
    paths = list((SITE / Path(*name.split('.')[:-1])).glob('_cyutility*.so'))
    assert len(paths) == 1
    closure['modules'][name] = record(paths[0])
closure['module_aliases'] = source.build_cyutility_alias_rule(closure['modules'])
for name in sys.argv[1:]:
    importlib.import_module(name)
    rec, evidence = source._live_alias('_cyutility', sys.modules['_cyutility'], closure['module_aliases']['_cyutility'])
    assert evidence['same_module_object'] is True
import torch.distributed.nn.api.remote_module  # CPU-only generated-rule dependency
# Inventory ordinary dependencies only for this ephemeral CPU test. Qualified
# targets and their rule remain the pre-import commitments above.
for name, module in list(sys.modules.items()):
    file = getattr(module, '__file__', None)
    if file and name not in closure['modules'] and name not in ('_cyutility', source.GENERATED_NAME, 'torch.ops', 'torch.classes'):
        path = Path(file).resolve()
        if not path.is_relative_to(ROOT): closure['modules'][name] = record(path)
closure['required_after'] += ['_cyutility'] + list(source.CYUTILITY_TARGETS)
receipt = source.attest_runtime_receipt(closure, closure['runtime'], binding={'cpu_test': True}, after=True)
source.verify_runtime_receipt(closure, receipt, binding={'cpu_test': True}, after=True)
print(json.dumps({'order': sys.argv[1:], 'alias': receipt['module_aliases']['_cyutility']}))
'''
    result = subprocess.run([PYTHON, '-B', '-c', program, *order], cwd=ROOT,
                            env={**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'OMP_NUM_THREADS': '2',
                                 'OPENBLAS_NUM_THREADS': '2', 'MKL_NUM_THREADS': '2',
                                 'PYTHONPATH': str(ROOT) + os.pathsep + str(ROOT / 'tests')},
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    observed = json.loads(result.stdout.strip().splitlines()[-1])
    expected = 'pandas._libs._cyutility' if order[0] == 'pandas' else 'scipy._cyutility'
    assert observed['alias']['target'] == expected
    print(json.dumps(observed, sort_keys=True))


def test_finite_subset_does_not_expand_from_loaded_modules(alias_live):
    closure, modules = alias_live
    target = source.CYUTILITY_TARGETS[0]
    closure['module_aliases'] = source.build_cyutility_alias_rule({target: closure['modules'][target]})
    modules['_cyutility'] = modules['scipy._cyutility']
    with pytest.raises(source.RuntimeOriginError, match='alias origin/identity differs'):
        source.attest_runtime(closure, closure['runtime'])


def test_alias_first_in_module_table_and_absent_before_import(alias_live):
    closure, modules = alias_live
    module = modules.pop('_cyutility')
    receipt = source.attest_runtime_receipt(closure, closure['runtime'], binding={})
    assert receipt['module_aliases'] == {}
    source.verify_runtime_receipt(closure, receipt, binding={})
    with pytest.raises(ValueError, match='required runtime modules not loaded'):
        source.attest_runtime(closure, closure['runtime'], after=True)
    rest = dict(modules)
    modules.clear()
    modules['_cyutility'] = module
    modules.update(rest)
    receipt = source.attest_runtime_receipt(closure, closure['runtime'], binding={}, after=True)
    source.verify_runtime_receipt(closure, receipt, binding={}, after=True)


@pytest.mark.parametrize('phase', ['runtime_before', 'runtime_after'])
def test_worker_persists_rejection_origin(tmp_path, phase):
    """Execute the intact worker function with inert dispatch/Main collaborators."""
    import ast
    from contextlib import nullcontext
    import time

    path = ROOT / 'scripts/qd_ed_n36_worker.py'
    tree = ast.parse(path.read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == '_run_in_process')
    root = tmp_path
    output = tmp_path / 'output'
    (output / 'eds_eval').mkdir(parents=True)
    context = {'plan': {}, 'expected_manifest': {}, 'attempt_id': 'cpu-fixture',
               'main_argv': [str(root / 'main.py')]}
    plan = {'worktree': str(root), 'source': {}, 'scientific_source': {},
            'runtime_closure': {}, 'controller_semantics': {}, 'runtime': {}, 'native_build': {}}
    diagnostic = {'name': '_cyutility', 'file': '/synthetic/unknown.so',
                  'resolved_path': '/synthetic/unknown.so', 'sha256': 'a' * 64,
                  'qualified_identity': {name: False for name in source.CYUTILITY_TARGETS}}
    calls = []

    def attest(*args, binding, **kwargs):
        calls.append(binding)
        if binding == phase:
            raise source.RuntimeOriginError('runtime alias origin/identity differs', diagnostic)
        return {}

    def atomic_json(path, value):
        path.write_text(json.dumps(value))

    namespace = dict(Path=Path, sys=SimpleNamespace(argv=[]), os=os, time=time,
                     source_execution=SimpleNamespace(active=lambda: None, attest=lambda *a, **kw: {}, run_main=lambda *a: None),
                     validate_context=lambda _, **kw: (context, plan, {}, {}, {'output_dir': str(output)}),
                     verify_dispatch_record=lambda *a: None,
                     w=SimpleNamespace(process_identity=lambda: {}, require=source.w.require,
                                       atomic_json=atomic_json, read_ref=lambda _: {}),
                     closure=SimpleNamespace(attest_runtime_receipt=attest, RuntimeOriginError=source.RuntimeOriginError),
                     controller=SimpleNamespace(verify_semantics=lambda *a: {}, observe_instances=lambda _: nullcontext([])),
                     native_build=SimpleNamespace(attest=lambda _: {}),
                     attest_worker_loaded=lambda *a: {},
                     runtime_receipt_binding=lambda *a: a[-1])
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), namespace)
    assert namespace['_run_in_process']({}) == 2
    receipt = json.loads((output / 'eds_eval/n36-worker-receipt.json').read_text())
    assert receipt['accepted'] is False and receipt['classification'] == 'INVALID'
    assert receipt['runtime_failure_origin'] == diagnostic
    assert receipt['error_type'] == 'RuntimeOriginError'
    assert receipt['main_exit_code'] == (0 if phase == 'runtime_after' else None)
    assert calls == (['runtime_before', 'runtime_after'] if phase == 'runtime_after' else ['runtime_before'])


def test_alias_snapshot_must_still_be_current_binding(alias_live):
    closure, modules = alias_live
    snapshot = modules['_cyutility']
    modules['_cyutility'] = modules['scipy._cyutility']
    with pytest.raises(ValueError, match='alias binding changed'):
        source._live_alias('_cyutility', snapshot, closure['module_aliases']['_cyutility'])
