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


def valid_evidence():
    return {'schema': 'qd-ed-gpu7-context-probe-v1', 'physical_gpu': 7, 'torch_logical_device': 0,
        'torch_uuid': 'GPU-unit-test', 'torch_visible_device_count': 1, 'cuda_kernel_result': 2.,
        'display_egl_device_index': 4, 'display_cuda_ordinal': 7, 'gl_vendor': 'NVIDIA Corporation',
        'gl_renderer': 'mock NVIDIA GPU', 'gl_version': 'mock OpenGL', 'frame_shape': [64,64,3],
        'frame_dtype': 'uint8', 'frame_nonzero_values': 30, 'frame_std': 1., 'simulation_steps': 0}


@pytest.mark.parametrize('change', [
    {'torch_uuid': 'GPU-another-device'}, {'display_cuda_ordinal': 0}, {'display_egl_device_index': 0},
    {'gl_vendor': 'Mesa'}, {'frame_std': 0}, {'frame_nonzero_values': 0}, {'simulation_steps': 1},
])
def test_rejects_wrong_device_software_renderer_or_empty_frame(change):
    evidence = {**valid_evidence(), **change}
    with pytest.raises(probe.runner.GateError):
        probe.validate_probe_evidence(evidence, {'uuid': 'GPU-unit-test', 'egl_device_index': 4})


def fixture_runtime(tmp_path, monkeypatch):
    root = tmp_path / 'worktree'
    artifact = tmp_path / 'artifact'
    (root / 'data').mkdir(parents=True)
    (artifact / 'runtime').mkdir(parents=True)
    runtime = {'worktree': str(root), 'artifact_root': str(artifact), 'metadata_mapping_verified': True,
               'provider_ready': False, 'cuda_egl_verified': False,
               'gpu_mapping': {'physical_gpu': 7, 'egl_device_index': 4, 'uuid': 'GPU-unit-test'},
               'environment': {}}
    path = artifact / 'runtime/setup_manifest.json'
    path.write_text(json.dumps(runtime))
    state = {'run_name': 'unit-test', 'artifacts': str(artifact), 'gpu_pool': [7],
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
def test_mock_dispatch_accounts_health_only_and_sets_readiness_only_on_valid_evidence(tmp_path, monkeypatch, valid):
    root, path, events = fixture_runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(probe.runner, 'gpu_admission', lambda **kwargs: {'physical_gpu': 7})
    monkeypatch.setattr(probe.runner, 'wait_exclusively', lambda process, timeout: 0)
    monkeypatch.setattr(probe.runner, 'terminate_owned', lambda process: None)

    def fake_popen(command, **kwargs):
        assert kwargs['start_new_session'] is True
        assert kwargs['env']['CUDA_VISIBLE_DEVICES'] == '7'
        assert kwargs['env']['CUDA_DEVICE_ORDER'] == 'PCI_BUS_ID'
        assert kwargs['env']['MUJOCO_EGL_DEVICE_ID'] == '4'
        output = Path(command[command.index('--output')+1])
        resource_id = command[command.index('--resource-id')+1]
        frame = output / 'probe-frame.png'
        frame.write_bytes(b'mock-synthetic-frame')
        evidence = {**valid_evidence(), 'resource_id': resource_id, 'frame_png_sha256': probe.runner.digest(frame)}
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
    assert all('attempt_id' not in e for e in events)
    runtime = json.loads(path.read_text())
    assert runtime['provider_ready'] is False
    assert runtime['cuda_egl_verified'] is valid


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
