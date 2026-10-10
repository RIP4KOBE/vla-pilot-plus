"""Closed importlib alias identity: synthetic CPU evidence grants no release."""
import copy
import importlib
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from scripts import qd_ed_n36_source as execution


@pytest.fixture
def proof():
    names = ['os.path', 'posixpath'] + [n for pair in execution.IMPORTLIB_FROZEN_PAIRS for n in pair]
    runtime = {'interpreter': execution.interpreter_identity(), 'modules': {
        name: {'path': str(Path(sys.modules[name].__file__).resolve()),
               'sha256': execution.sha(sys.modules[name].__file__)} for name in names}}
    binding = {'context': {'path': '/synthetic/context', 'sha256': 'a'*64},
               'runtime_closure': {'path': '/synthetic/runtime', 'sha256': 'b'*64},
               'process': {'pid': os.getpid(),
                           'proc_start_ticks': Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19],
                           'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()},
               'phase': 'runtime_before'}
    receipt = {'schema': 'n36-source-execution-v2', 'binding': copy.deepcopy(binding),
               'interpreter': copy.deepcopy(runtime['interpreter']),
               'frozen_modules': sorted(['posixpath'] + [c for _, c in execution.IMPORTLIB_FROZEN_PAIRS]),
               'frozen_aliases': {'os.path': execution.live_alias(runtime, binding)},
               'frozen_importlib_aliases': execution.live_importlib_aliases(runtime, binding)}
    observed = {'binding': copy.deepcopy(binding), 'modules': copy.deepcopy(runtime['modules'])}
    return runtime, binding, receipt, observed


def test_closed_pairs(proof):
    runtime, binding, receipt, observed = proof
    assert execution.verify_importlib_aliases(receipt, runtime, observed, binding) == {
        'os.path', 'importlib._bootstrap', 'importlib._bootstrap_external'}
    assert all(alias not in receipt['frozen_modules'] for alias, _ in execution.IMPORTLIB_FROZEN_PAIRS)


@pytest.mark.parametrize('alias,canonical', execution.IMPORTLIB_FROZEN_PAIRS)
@pytest.mark.parametrize('fault', ['alias_object', 'canonical_object', 'canonical_missing', 'attribute',
    'spec', 'spec_name', 'origin', 'loader', 'module_loader', 'name', 'package', 'path', 'lexical_path',
    'hash', 'canonical_inventory', 'not_frozen', 'interpreter', 'process'])
def test_live_rejects_substitution(proof, monkeypatch, alias, canonical, fault):
    runtime, binding, _, _ = proof
    module = sys.modules[canonical]
    if fault in ('alias_object', 'canonical_object'):
        monkeypatch.setitem(sys.modules, alias if fault == 'alias_object' else canonical,
                            SimpleNamespace(**vars(module)))
    elif fault == 'canonical_missing': monkeypatch.delitem(sys.modules, canonical)
    elif fault == 'attribute': monkeypatch.setattr(importlib, alias.rsplit('.', 1)[1], object())
    elif fault == 'spec': monkeypatch.setattr(module, '__spec__', None)
    elif fault in ('spec_name', 'origin', 'loader'):
        spec = copy.copy(module.__spec__)
        setattr(spec, 'name' if fault == 'spec_name' else fault, 'wrong')
        monkeypatch.setattr(module, '__spec__', spec)
    elif fault in ('module_loader', 'name', 'package', 'path', 'lexical_path'):
        field = {'module_loader': '__loader__', 'name': '__name__', 'package': '__package__',
                 'path': '__file__', 'lexical_path': '__file__'}[fault]
        value = str(Path(module.__file__).parent) + '/./' + Path(module.__file__).name if fault == 'lexical_path' else 'wrong'
        monkeypatch.setattr(module, field, value)
    elif fault == 'hash': runtime['modules'][alias]['sha256'] = '0'*64
    elif fault == 'canonical_inventory': del runtime['modules'][canonical]
    elif fault == 'not_frozen': monkeypatch.setattr(execution._imp, 'is_frozen', lambda n: n != canonical)
    elif fault == 'interpreter': runtime['interpreter']['sha256'] = '0'*64
    else: binding['process']['pid'] += 1
    with pytest.raises(ValueError, match='N36'):
        execution.live_importlib_aliases(runtime, binding)


@pytest.mark.parametrize('alias,canonical', execution.IMPORTLIB_FROZEN_PAIRS)
@pytest.mark.parametrize('fault', ['same_module_object', 'importlib_attribute_is_module', 'is_frozen',
    'alias', 'canonical', 'module_name', 'package', 'file', 'spec_name', 'origin', 'loader',
    'hash', 'path', 'interpreter', 'claim_binding', 'context', 'runtime_closure', 'process', 'phase',
    'canonical_frozen_missing', 'canonical_runtime_missing', 'canonical_observed_missing',
    'alias_observed_missing', 'missing_proof', 'extra_proof', 'coordinated_path', 'coordinated_hash'])
def test_retained_rejects_substitution(proof, alias, canonical, fault):
    runtime, binding, receipt, observed = proof
    claim = receipt['frozen_importlib_aliases'][alias]
    if fault in ('same_module_object', 'importlib_attribute_is_module', 'is_frozen'): claim[fault] = 1
    elif fault in ('alias', 'canonical', 'module_name', 'package', 'file', 'spec_name', 'origin', 'loader'): claim[fault] = 'wrong'
    elif fault in ('hash', 'path'): claim['records'][alias]['sha256' if fault == 'hash' else 'path'] = 'wrong'
    elif fault == 'interpreter': claim['interpreter']['sha256'] = '0'*64
    elif fault == 'claim_binding': claim['binding']['process']['pid'] += 1
    elif fault in ('context', 'runtime_closure'): binding[fault]['sha256'] = '0'*64
    elif fault == 'process': binding['process']['pid'] += 1
    elif fault == 'phase': binding['phase'] = 'runtime_after'
    elif fault == 'canonical_frozen_missing': receipt['frozen_modules'].remove(canonical)
    elif fault == 'canonical_runtime_missing': del runtime['modules'][canonical]
    elif fault == 'canonical_observed_missing': del observed['modules'][canonical]
    elif fault == 'alias_observed_missing': del observed['modules'][alias]
    elif fault == 'missing_proof': del receipt['frozen_importlib_aliases'][alias]
    elif fault == 'extra_proof': receipt['frozen_importlib_aliases']['other'] = copy.deepcopy(claim)
    else:
        field = 'path' if fault == 'coordinated_path' else 'sha256'
        for records in (runtime['modules'], observed['modules'], claim['records']):
            for name in (alias, canonical): records[name][field] = 'wrong'
    with pytest.raises(ValueError, match='N36'):
        execution.verify_importlib_aliases(receipt, runtime, observed, binding)
