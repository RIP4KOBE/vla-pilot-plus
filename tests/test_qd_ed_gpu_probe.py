"""CPU mock tests only: never import torch/mujoco or dispatch a GPU process."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('qd_ed_gpu_probe', ROOT / 'scripts/qd_ed_gpu_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def valid_evidence(physical_gpu=7):
    egl = 7 if physical_gpu == 5 else 4
    return {'schema': 'qd-ed-gpu-context-probe-v2', 'boot_id': probe.current_boot_id(),
        'physical_gpu': physical_gpu, 'torch_logical_device': 0,
        'torch_uuid': 'GPU-unit-test', 'torch_visible_device_count': 1, 'cuda_kernel_result': 2.,
        'nvidia_physical_gpu': physical_gpu, 'nvidia_uuid': 'GPU-unit-test',
        'nvidia_pci_bus_id': '00000000:A1:00.0',
        'cuda_visible_devices': str(physical_gpu), 'cuda_device_order': 'PCI_BUS_ID',
        'display_egl_device_index': egl, 'display_cuda_ordinal': 0,
        'egl_cuda_ordinal_namespace': 'process_visible',
        'cuda_associated_egl_devices': [{'egl_device_index': egl, 'cuda_ordinal': 0}],
        'gl_vendor': 'NVIDIA Corporation',
        'gl_renderer': 'mock NVIDIA GPU', 'gl_version': 'mock OpenGL', 'frame_shape': [64,64,3],
        'frame_dtype': 'uint8', 'frame_nonzero_values': 30, 'frame_std': 1., 'simulation_steps': 0}


def valid_mapping(physical_gpu=7):
    return {'physical_gpu': physical_gpu, 'metadata_mapping_verified': True,
            'uuid': 'GPU-unit-test', 'egl_device_index': 7 if physical_gpu == 5 else 4,
            'pci_bus_id': '0000:a1:00.0'}


@pytest.mark.parametrize('change', [
    {'physical_gpu': 5}, {'nvidia_physical_gpu': 5}, {'nvidia_uuid': 'GPU-another-device'},
    {'nvidia_pci_bus_id': '00000000:E1:00.0'}, {'nvidia_pci_bus_id': '00000001:A1:00.0'},
    {'nvidia_pci_bus_id': ''},
    {'torch_uuid': 'GPU-another-device'}, {'display_cuda_ordinal': 7}, {'display_egl_device_index': 0},
    {'cuda_visible_devices': '0'}, {'cuda_visible_devices': '7,6'}, {'cuda_device_order': 'FASTEST_FIRST'},
    {'egl_cuda_ordinal_namespace': 'physical'}, {'torch_visible_device_count': 2},
    {'cuda_associated_egl_devices': []},
    {'cuda_associated_egl_devices': [{'egl_device_index': 0, 'cuda_ordinal': 0}]},
    {'cuda_associated_egl_devices': [{'egl_device_index': 4, 'cuda_ordinal': 7}]},
    {'cuda_associated_egl_devices': [{'egl_device_index': 4, 'cuda_ordinal': 0},
                                     {'egl_device_index': 5, 'cuda_ordinal': 0}]},
    {'gl_vendor': 'Mesa'}, {'frame_std': 0}, {'frame_nonzero_values': 0}, {'simulation_steps': 1},
])
def test_rejects_wrong_device_software_renderer_or_empty_frame(change):
    evidence = {**valid_evidence(), **change}
    with pytest.raises(probe.runner.GateError):
        probe.validate_probe_evidence(evidence, valid_mapping())


def test_masked_egl_logical_zero_requires_both_uuid_and_metadata_binding():
    probe.validate_probe_evidence(valid_evidence(), valid_mapping())
    for change in ({'physical_gpu': 6}, {'metadata_mapping_verified': False},
                   {'uuid': 'GPU-another'}, {'egl_device_index': 5}):
        with pytest.raises(probe.runner.GateError):
            probe.validate_probe_evidence(valid_evidence(), {**valid_mapping(), **change})


@pytest.mark.parametrize('physical_gpu', [5, 7])
def test_selected_physical_gpu_uses_observed_egl_index_and_cuda_zero(physical_gpu):
    probe.validate_probe_evidence(valid_evidence(physical_gpu), valid_mapping(physical_gpu))


def test_legacy_gpu7_evidence_remains_valid_but_cannot_claim_gpu5():
    legacy = {key: value for key, value in valid_evidence().items() if not key.startswith('nvidia_')}
    legacy['schema'] = 'qd-ed-gpu7-context-probe-v1'
    probe.validate_probe_evidence(legacy, valid_mapping())
    spoof = {**valid_evidence(5), 'schema': legacy['schema']}
    with pytest.raises(probe.runner.GateError, match='schema'):
        probe.validate_probe_evidence(spoof, valid_mapping(5))


def test_rejected_raw_evidence_is_persisted_before_validation(tmp_path, monkeypatch):
    evidence = {**valid_evidence(), 'display_cuda_ordinal': 7}
    original_validator = probe.validate_probe_evidence
    observed = []
    def check_after_persist(value, mapping):
        on_disk = json.loads((tmp_path / 'probe-evidence.json').read_text())
        assert on_disk['validation_status'] == 'pending'
        assert on_disk['display_cuda_ordinal'] == 7
        observed.append(True)
        original_validator(value, mapping)
    monkeypatch.setattr(probe, 'validate_probe_evidence', check_after_persist)
    with pytest.raises(probe.runner.GateError):
        probe.persist_and_validate_probe_evidence(evidence, valid_mapping(), tmp_path)
    saved = json.loads((tmp_path / 'probe-evidence.json').read_text())
    assert observed == [True]
    assert saved['validation_status'] == 'rejected'
    assert saved['display_cuda_ordinal'] == 7
    assert saved['torch_uuid'] == 'GPU-unit-test'
    assert 'visible CUDA logical0' in saved['validation_error']


def test_accepted_evidence_persists_completed_validation(tmp_path):
    probe.persist_and_validate_probe_evidence(valid_evidence(), valid_mapping(), tmp_path)
    assert json.loads((tmp_path / 'probe-evidence.json').read_text())['validation_status'] == 'passed'


def fixture_runtime(tmp_path, monkeypatch, physical_gpu=7):
    root = tmp_path / 'worktree'
    artifact = tmp_path / 'artifact'
    (root / 'data').mkdir(parents=True)
    (artifact / 'runtime').mkdir(parents=True)
    runtime = {'worktree': str(root), 'artifact_root': str(artifact), 'metadata_mapping_verified': True,
               'provider_ready': False, 'cuda_egl_verified': False,
               'gpu_mapping': valid_mapping(physical_gpu),
               'environment': {}}
    path = artifact / 'runtime/setup_manifest.json'
    path.write_text(json.dumps(runtime))
    state = {'run_name': 'unit-test', 'artifacts': str(artifact), 'gpu_pool': [physical_gpu],
             'max_concurrent_gpu_workers': 1, 'budget': {'max_gpu_hours': 48., 'gpu_hours_consumed': 0.,
                 'max_episode_attempts': 240, 'dispatched': 0, 'reserved': dict(probe.runner.BUCKETS)}}
    monkeypatch.setattr(probe.runner, 'read_state', lambda _: state)
    events = []
    monkeypatch.setattr(probe.runner, 'append_healthcheck_event', lambda root, event: events.append(event))
    return root, path, events


def test_busy_gpu_refuses_before_dispatch_reservation_or_flag_change(tmp_path, monkeypatch):
    root, path, events = fixture_runtime(tmp_path, monkeypatch)
    original = path.read_bytes()
    def busy(**kwargs):
        raise probe.runner.GateError('GPU7 has external compute processes')
    monkeypatch.setattr(probe.runner, 'gpu_admission', busy)
    monkeypatch.setattr(probe.subprocess, 'Popen', lambda *a, **kw: pytest.fail('must never dispatch'))
    with pytest.raises(probe.runner.GateError, match='external'):
        probe.run_probe(path, root=root)
    assert events == []
    assert path.read_bytes() == original


@pytest.mark.parametrize('valid', [True, False])
@pytest.mark.parametrize('physical_gpu', [5, 7])
def test_mock_dispatch_accounts_health_only_and_sets_readiness_only_on_valid_evidence(tmp_path, monkeypatch, valid, physical_gpu):
    root, path, events = fixture_runtime(tmp_path, monkeypatch, physical_gpu)
    admissions, waits = [], []
    def admit(**kwargs):
        admissions.append(kwargs)
        assert kwargs == {'physical_gpu': physical_gpu, 'expected_uuid': 'GPU-unit-test'}
        return {'physical_gpu': physical_gpu}
    def wait(process, timeout, **kwargs):
        waits.append(kwargs)
        assert kwargs == {'physical_gpu': physical_gpu}
        return 0
    monkeypatch.setattr(probe.runner, 'gpu_admission', admit)
    monkeypatch.setattr(probe.runner, 'wait_exclusively', wait)
    monkeypatch.setattr(probe.runner, 'terminate_owned', lambda process: None)

    def fake_popen(command, **kwargs):
        assert kwargs['start_new_session'] is True
        assert kwargs['env']['CUDA_VISIBLE_DEVICES'] == str(physical_gpu)
        assert kwargs['env']['CUDA_DEVICE_ORDER'] == 'PCI_BUS_ID'
        assert kwargs['env']['MUJOCO_EGL_DEVICE_ID'] == str(valid_mapping(physical_gpu)['egl_device_index'])
        output = Path(command[command.index('--output')+1])
        resource_id = command[command.index('--resource-id')+1]
        frame = output / 'probe-frame.png'
        frame.write_bytes(b'mock-synthetic-frame')
        evidence = {**valid_evidence(physical_gpu), 'resource_id': resource_id, 'frame_png_sha256': probe.runner.digest(frame)}
        if not valid:
            evidence['torch_uuid'] = 'GPU-wrong'
        (output / 'probe-evidence.json').write_text(json.dumps(evidence))
        return SimpleNamespace(pid=99999999)

    monkeypatch.setattr(probe.subprocess, 'Popen', fake_popen)
    if valid:
        result = probe.run_probe(path, root=root)
        assert result['event'] == 'completed'
    else:
        with pytest.raises(probe.runner.GateError, match='probe failed'):
            probe.run_probe(path, root=root)
    assert [e['event'] for e in events] == ['reserved', 'dispatched', 'completed' if valid else 'aborted']
    assert events[-1]['gpu_process_wall_seconds'] >= 0
    assert admissions and waits
    assert all(e['physical_gpu'] == physical_gpu for e in events)
    assert all(f'__gpu{physical_gpu}_cuda_egl__' in e['resource_id'] for e in events)
    assert all('attempt_id' not in e for e in events)
    runtime = json.loads(path.read_text())
    assert runtime['provider_ready'] is False
    assert runtime['cuda_egl_verified'] is valid


def test_probe_rejects_runtime_differing_from_new_gpu_authorization(tmp_path, monkeypatch):
    root, path, events = fixture_runtime(tmp_path, monkeypatch, 5)
    probe.runner.read_state(None)['gpu_pool'] = [7]
    monkeypatch.setattr(probe.runner, 'gpu_admission', lambda **kwargs: pytest.fail('authorization must gate first'))
    with pytest.raises(probe.runner.GateError):
        probe.run_probe(path, root=root)
    assert events == []


def test_direct_child_invocation_cannot_import_gpu_code_without_parent(monkeypatch, tmp_path):
    monkeypatch.delenv('QD_ED_GPU_PROBE_PARENT_PID', raising=False)
    with pytest.raises(probe.runner.GateError, match='admitted parent'):
        probe.child_probe(tmp_path / 'unused.json', tmp_path, 'no-resource')


def test_probe_cannot_consume_reserved_validation_or_formal_hours(tmp_path, monkeypatch):
    root, path, events = fixture_runtime(tmp_path, monkeypatch)
    probe.runner.read_state(None)['budget']['max_gpu_hours'] = 24.
    monkeypatch.setattr(probe.runner, 'gpu_admission', lambda **kwargs: pytest.fail('budget must gate first'))
    with pytest.raises(probe.runner.GateError, match='termination grace'):
        probe.run_probe(path, root=root)
    assert events == []
