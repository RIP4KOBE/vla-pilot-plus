"""Synthetic CPU receipts only. Real verification, no patched production checks."""
import copy
import json
import os
from pathlib import Path
import sys

import pytest

from scripts import qd_ed_n36_source as execution
from scripts import qd_ed_n36_build as native


def put(root, name, value):
    path = root / (name + '.json')
    path.write_text(json.dumps(value, sort_keys=True))
    return {'path': str(path), 'sha256': execution.sha(path)}


@pytest.fixture
def evidence(tmp_path):
    return preparation_evidence(tmp_path)


def preparation_evidence(root):
    root.mkdir(parents=True, exist_ok=True)
    names = ['os.path', 'posixpath'] + [n for pair in execution.IMPORTLIB_FROZEN_PAIRS for n in pair]
    names += ['encodings', 'encodings.aliases', 'encodings.utf_8']
    modules = {name: {'path': str(Path(sys.modules[name].__file__).resolve()),
                      'sha256': execution.sha(sys.modules[name].__file__)} for name in names}
    runtime_ref = put(root, 'disabled-runtime', {'SYNTHETIC_NOT_AUTHORITY': True})
    runtime = {'interpreter': execution.interpreter_identity(), 'modules': modules,
               'required_after': names, 'runtime': runtime_ref}
    closure_ref = put(root, 'closure', runtime)
    source_root = Path(__file__).resolve().parents[1]
    files = [{'path': name.replace('.', '/') + '.py',
              'sha256': execution.sha(source_root / (name.replace('.', '/') + '.py'))}
             for name in sorted(execution.PREPARATION_MODULES)]
    files.append({'path': 'scripts/qd_ed_n36_bootstrap.py',
                  'sha256': execution.sha(source_root / 'scripts/qd_ed_n36_bootstrap.py')})
    source = {'commit': 'SYNTHETIC_NOT_AUTHORITY', 'files': files}
    source_ref = put(root, 'source', source)
    libraries = []
    for name in (*native.REQUIRED, 'libcuda.so.1'):
        path = root / name
        path.write_bytes(b'SYNTHETIC inert library; never load')
        libraries.append({'path': str(path), 'sha256': execution.sha(path)})
    libraries.sort(key=lambda row: row['path'])
    native_ref = put(root, 'native', {'schema': 'n36-native-build-v1',
        'torch_version': 'SYNTHETIC', 'cuda_version': 'SYNTHETIC',
        'torch_build': 'SYNTHETIC', 'libraries': libraries})
    plan = {'source': source, 'worktree': str(source_root), 'runtime': runtime_ref,
            'runtime_closure': closure_ref, 'native_build': native_ref}
    release = {'schema': 'n36-preparation-measurement-release-v1', 'approved': True,
        'purpose': 'readiness_preparation_only', 'episode_authorized': False,
        'health_authorized': False, 'source_record': source_ref, 'resource_id': 'SYNTHETIC',
        'source_cwd': str(source_root), 'interpreter': runtime['interpreter'],
        'graph': {'plan': put(root, 'plan', plan), 'runtime': runtime_ref}}
    release_ref = put(root, 'release', release)
    process = {'pid': os.getpid(),
        'proc_start_ticks': Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19],
        'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
    binding = {'release': release_ref, 'source_record': source_ref, 'resource_id': 'SYNTHETIC',
               'process': process, 'phase': 'preparation_after'}
    receipt = {'schema': 'n36-source-execution-v2', 'binding': copy.deepcopy(binding),
        'interpreter': runtime['interpreter'], 'search_prefix': str(Path(sys.executable).resolve().parent.parent),
        'search_path': [str(source_root)],
        'bootstrap': {'path': str(source_root / files[-1]['path']), 'sha256': files[-1]['sha256']},
        'compiled': [{'module': row['path'][:-3].replace('/', '.'),
                      'path': str(source_root / row['path']), 'sha256': row['sha256']} for row in files[:-1]],
        'startup_source_only': [{'module': name, **modules[name]} for name in names[-3:]],
        'frozen_modules': sorted(['posixpath'] + [c for _, c in execution.IMPORTLIB_FROZEN_PAIRS]),
        'frozen_aliases': {'os.path': execution.live_alias(runtime, binding)},
        'frozen_importlib_aliases': execution.live_importlib_aliases(runtime, binding)}
    kwargs = dict(runtime_receipt={'schema': 'n34-runtime-receipt-v2',
        'binding': copy.deepcopy(binding), 'modules': copy.deepcopy(modules), 'generated_modules': {}},
        native_receipt={'schema': 'n36-loaded-native-build-v1', 'manifest': native_ref,
                        'libraries': copy.deepcopy(libraries)},
        release=release_ref, source_record=source_ref, runtime_closure=closure_ref,
        runtime_reference=runtime_ref, resource_id='SYNTHETIC', process=copy.deepcopy(process))
    return receipt, source_root, source, runtime, kwargs


def verify(evidence):
    receipt, root, source, runtime, kwargs = evidence
    return execution.verify_preparation_receipt(receipt, root, source, runtime, **kwargs)


def test_preparation_complete_cpu_evidence(evidence):
    verify(evidence)
    import torch
    assert not torch.cuda.is_initialized()


@pytest.mark.parametrize('key', ['release', 'source_record', 'resource_id', 'process', 'phase'])
@pytest.mark.parametrize('fault', ['missing', 'wrong'])
@pytest.mark.parametrize('location', ['source', 'runtime', 'both_and_claims'])
def test_binding_cannot_self_authorize(evidence, key, fault, location):
    receipt, _, _, _, kwargs = evidence
    bindings = []
    if location in ('source', 'both_and_claims'):
        bindings.append(receipt['binding'])
    if location in ('runtime', 'both_and_claims'):
        bindings.append(kwargs['runtime_receipt']['binding'])
    if location == 'both_and_claims':
        bindings += [v['binding'] for group in ('frozen_aliases', 'frozen_importlib_aliases')
                     for v in receipt[group].values()]
    for binding in bindings:
        if fault == 'missing': del binding[key]
        else: binding[key] = {'WRONG': True} if key in ('release', 'source_record', 'process') else 'wrong'
    with pytest.raises(ValueError): verify(evidence)


@pytest.mark.parametrize('key', ['release', 'source_record', 'runtime_closure', 'runtime_reference',
                                'resource_id', 'process'])
@pytest.mark.parametrize('fault', ['missing', 'wrong'])
def test_external_anchor_required(evidence, key, fault):
    kwargs = evidence[-1]
    if fault == 'missing': kwargs[key] = None
    elif key == 'resource_id': kwargs[key] = 'foreign'
    elif key == 'process': kwargs[key]['pid'] += 1
    else: kwargs[key] = dict(kwargs[key], sha256='0'*64)
    with pytest.raises(ValueError): verify(evidence)


@pytest.mark.parametrize('fault', ['runtime_bytes', 'runtime_required_after', 'source_bytes',
    'receipt_runtime_missing', 'receipt_runtime_wrong', 'native_link', 'native_missing', 'native_bytes',
    'bootstrap', 'compiled_hash', 'producer_missing', 'producer_renamed', 'producer_wrong_path',
    'startup_missing', 'os_alias', 'importlib_alias', 'canonical_missing', 'arbitrary_alias',
    'source_receipt_schema', 'runtime_receipt_schema', 'claim_process', 'search_path'])
def test_full_evidence_checks_remain_active(evidence, fault):
    receipt, root, source, runtime, kwargs = evidence
    if fault == 'runtime_bytes': runtime['interpreter'] = dict(runtime['interpreter'], sha256='0'*64)
    elif fault == 'runtime_required_after':
        kwargs['runtime_receipt']['modules'].pop('encodings')
    elif fault == 'source_bytes': source['files'][0]['sha256'] = '0'*64
    elif fault == 'receipt_runtime_missing': kwargs['runtime_receipt'] = None
    elif fault == 'receipt_runtime_wrong': kwargs['runtime_receipt']['modules']['posixpath']['sha256'] = '0'*64
    elif fault == 'native_link': kwargs['native_receipt']['manifest'] = kwargs['source_record']
    elif fault == 'native_missing': kwargs['native_receipt']['libraries'].pop()
    elif fault == 'native_bytes': kwargs['native_receipt']['libraries'][0]['sha256'] = '0'*64
    elif fault == 'bootstrap': receipt['bootstrap']['sha256'] = '0'*64
    elif fault == 'compiled_hash': receipt['compiled'][0]['sha256'] = '0'*64
    elif fault == 'producer_missing': receipt['compiled'].pop(0)
    elif fault == 'producer_renamed': receipt['compiled'][0]['module'] = 'foreign'
    elif fault == 'producer_wrong_path': receipt['compiled'][0].update(
        path=receipt['compiled'][1]['path'], sha256=receipt['compiled'][1]['sha256'])
    elif fault == 'startup_missing': receipt['startup_source_only'].pop()
    elif fault == 'os_alias': receipt['frozen_aliases']['os.path']['same_module_object'] = False
    elif fault == 'importlib_alias': receipt['frozen_importlib_aliases'].pop('importlib._bootstrap')
    elif fault == 'canonical_missing': receipt['frozen_modules'].remove('_frozen_importlib')
    elif fault == 'arbitrary_alias': receipt['frozen_importlib_aliases']['arbitrary'] = {}
    elif fault == 'source_receipt_schema': receipt['schema'] = 'wrong'
    elif fault == 'runtime_receipt_schema': kwargs['runtime_receipt']['schema'] = 'wrong'
    elif fault == 'claim_process': receipt['frozen_importlib_aliases']['importlib._bootstrap']['binding']['process']['pid'] += 1
    else: receipt['search_path'] = ['/foreign']
    with pytest.raises(ValueError): verify(evidence)


@pytest.mark.parametrize('entrypoint', ['verify_alias', 'verify_importlib_aliases', 'verify_receipt'])
def test_episode_entrypoints_reject_preparation(evidence, entrypoint):
    receipt, root, source, runtime, kwargs = evidence
    with pytest.raises(ValueError, match='external binding'):
        if entrypoint == 'verify_receipt':
            execution.verify_receipt(receipt, root, source, runtime,
                runtime_receipt=kwargs['runtime_receipt'], binding=receipt['binding'])
        else:
            getattr(execution, entrypoint)(receipt, runtime, kwargs['runtime_receipt'], receipt['binding'])


@pytest.mark.parametrize('phase', ['runtime_before', 'runtime_after'])
def test_episode_still_requires_episode_modules(evidence, phase):
    receipt, root, source, runtime, kwargs = evidence
    binding = {'context': kwargs['release'], 'runtime_closure': kwargs['runtime_closure'],
               'process': kwargs['process'], 'phase': phase}
    receipt['binding'] = kwargs['runtime_receipt']['binding'] = binding
    receipt['frozen_aliases'] = {'os.path': execution.live_alias(runtime, binding)}
    receipt['frozen_importlib_aliases'] = execution.live_importlib_aliases(runtime, binding)
    with pytest.raises(ValueError, match='executable receipt coverage'):
        execution.verify_receipt(receipt, root, source, runtime,
            runtime_receipt=kwargs['runtime_receipt'], binding=binding)


@pytest.mark.parametrize('fault', [None, 'source_digest', 'source_substitution', 'runtime_link',
    'native_link', 'envelope_binding', 'proof_binding', 'terminal_process', 'external_release',
    'external_source', 'external_resource', 'external_runtime'])
def test_envelope_callsite_receipt_linkage(evidence, tmp_path, fault):
    from scripts import qd_ed_n36_readiness_prepare as preparation
    receipt, root, source, runtime, kwargs = evidence
    proof = {'runtime_receipt': put(tmp_path, 'observed-runtime', kwargs['runtime_receipt']),
             'native_receipt': put(tmp_path, 'observed-native', kwargs['native_receipt']),
             'runtime_receipt_binding': copy.deepcopy(receipt['binding'])}
    envelope = dict(copy.deepcopy(proof), process=copy.deepcopy(kwargs['process']),
                    source_receipt=put(tmp_path, 'observed-source', receipt))
    common = {key: copy.deepcopy(kwargs[key]) for key in ('release', 'source_record', 'resource_id')}
    plan = {'source': source, 'worktree': str(root), 'runtime_closure': kwargs['runtime_closure'],
            'runtime': kwargs['runtime_reference']}
    if fault == 'source_digest': envelope['source_receipt']['sha256'] = '0'*64
    elif fault == 'source_substitution':
        substituted = copy.deepcopy(receipt)
        substituted['binding']['process']['pid'] += 1
        envelope['source_receipt'] = put(tmp_path, 'foreign-source', substituted)
    elif fault == 'runtime_link': envelope['runtime_receipt'] = kwargs['runtime_closure']
    elif fault == 'native_link': envelope['native_receipt'] = kwargs['source_record']
    elif fault == 'envelope_binding': del envelope['runtime_receipt_binding']['release']
    elif fault == 'proof_binding': proof['runtime_receipt_binding']['phase'] = 'runtime_after'
    elif fault == 'terminal_process': envelope['process']['pid'] += 1
    elif fault == 'external_release': common['release'] = kwargs['source_record']
    elif fault == 'external_source': common['source_record'] = kwargs['runtime_closure']
    elif fault == 'external_resource': common['resource_id'] = 'foreign'
    elif fault == 'external_runtime': plan['runtime'] = kwargs['source_record']
    if fault:
        with pytest.raises(ValueError):
            preparation.verify_execution_receipts(envelope, proof, plan, common, kwargs['process'])
    else:
        preparation.verify_execution_receipts(envelope, proof, plan, common, kwargs['process'])


@pytest.mark.parametrize('fault', ['pid_bool', 'pid_zero', 'ticks_zero', 'ticks_unicode',
                                 'boot_id_invalid', 'extra_field'])
def test_terminal_process_shape(evidence, fault):
    process = evidence[-1]['process']
    if fault == 'pid_bool': process['pid'] = True
    elif fault == 'pid_zero': process['pid'] = 0
    elif fault == 'ticks_zero': process['proc_start_ticks'] = '0'
    elif fault == 'ticks_unicode': process['proc_start_ticks'] = '\u0661'
    elif fault == 'boot_id_invalid': process['boot_id'] = 'foreign'
    else: process['extra'] = True
    with pytest.raises(ValueError): verify(evidence)
