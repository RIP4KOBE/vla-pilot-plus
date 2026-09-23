"""CPU-only queue tests: no CUDA, simulator, network, or real subprocess runs."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('qd_ed_available_gpu_queue',
                                             ROOT / 'scripts/qd_ed_available_gpu_queue.py')
queue = importlib.util.module_from_spec(spec)
spec.loader.exec_module(queue)


def state_for(artifact):
    return {'run_name': 'test', 'artifacts': str(artifact), 'gpu_pool': [7],
            'max_concurrent_gpu_workers': 1,
            'authorized_gpu_selection': {'candidate_indices': list(range(8)),
                                        'single_exclusive_worker': True,
                                        'rescan_if_unavailable': True},
            'budget': {'max_episode_attempts': 240, 'max_gpu_hours': 48,
                       'dispatched': 0, 'gpu_hours_consumed': 0,
                       'reserved': dict(queue.runner.BUCKETS)}}


def mapping(index=7):
    return {'physical_gpu': index, 'uuid': f'GPU-test-{index}', 'pci_bus_id': '0000:a1:00.0',
            'driver_version': 'test-driver', 'egl_device_index': 4,
            'metadata_mapping_verified': True, 'cuda_egl_verified': True}


def devices(idle=None):
    return {index: {'physical_gpu': index, 'uuid': f'GPU-test-{index}',
                    'pci_bus_id': f'0000:{index + 1:02x}:00.0', 'reserving_pids': [],
                    'memory_used_mib': 0 if index == idle else 8000,
                    'compute_pids': [] if index == idle else [100 + index]}
            for index in range(8)}


def fixture_queue(tmp_path, monkeypatch):
    root = tmp_path / 'worktree'
    artifact = tmp_path / 'artifact'
    (root / 'data').mkdir(parents=True)
    (root / 'scripts').mkdir()
    (root / 'scripts/qd_ed_gpu_probe.py').write_text('mock probe')
    (artifact / 'runtime').mkdir(parents=True)
    state = state_for(artifact)
    (root / 'research-state.yaml').write_text(yaml.safe_dump(state))
    row = {'episode_key': 'q0', 'split': 'dev', 'iteration': 'N1', 'profile': 'Q0',
           'task_id': 0, 'env_seed': 11, 'policy_seed': 11, 'init_index': 0,
           'budget_bucket': 'development', 'timeout_seconds': 120}
    plan = {'episodes': [row], 'phase_authorization': {'dev': True}, 'artifact_root': str(artifact),
            'code_files': [{'path': 'scripts/' + name + '.py'} for name in
                           ('qd_ed_available_gpu_queue', 'qd_ed_gpu_probe', 'qd_ed_runtime_setup')]}
    path = artifact / 'plan.json'
    path.write_text(json.dumps(plan))
    runtime = {'schema': 'qd-ed-runtime-setup-v1', 'gpu_mapping': mapping(),
               'worktree': str(root), 'artifact_root': str(artifact),
               'files': [{'path': 'immutable-task-cache', 'sha256': 'keep'}],
               'frozen_stage_provider': {'backend': 'codex_cli', 'model': 'gpt-6-astra'},
               'environment': {'LIBERO_CONFIG_PATH': 'unchanged'}, 'tasks': {'0': {'seed': 11}}}
    monkeypatch.setattr(queue.runner, 'validate_plan', lambda *a, **k: (copy.deepcopy(plan), {}, copy.deepcopy(runtime)))
    monkeypatch.setattr(queue.runner, 'verify_provider', lambda *a, **k: None)
    monkeypatch.setattr(queue.runner, 'child_environment', lambda *a, **k: {})
    monkeypatch.setattr(queue, 'inventory', lambda: devices())
    return root, artifact, path, plan, runtime, row


def forbid(*args, **kwargs):
    raise AssertionError('must not launch or allocate')


def test_busy_wait_never_creates_attempts_or_calls_gpu_context(tmp_path, monkeypatch):
    root, artifact, path, *_ = fixture_queue(tmp_path, monkeypatch)
    monkeypatch.setattr(queue, 'bind_plan', forbid)
    monkeypatch.setattr(queue.probe, 'run_probe', forbid)
    monkeypatch.setattr(queue.runner, 'run_plan', forbid)
    sleeps = []
    result = queue.run_queue(path, ['q0'], root=root, idle_seconds=0, sleep=sleeps.append, max_polls=2)
    assert result['status'] == 'waiting'
    assert sleeps == [30]
    assert result['completed_keys'] == []
    assert not (root / 'data/attempt-ledger.jsonl').exists()
    assert not (root / 'data/gpu-healthcheck-ledger.jsonl').exists()
    assert json.loads((artifact / 'runtime/available-gpu-queue-status.json').read_text())['status'] == 'waiting'


def test_inventory_joins_processes_by_uuid_and_rejects_unknown_identity():
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        value = '0, GPU-zero, 0, 0000:01:00.0\n1, GPU-one, 7, 0000:02:00.0\n' if '--query-gpu=index,uuid,memory.used,pci.bus_id' in command else 'GPU-zero, 123\n'
        return SimpleNamespace(returncode=0, stdout=value)
    observed = queue.inventory(run, reservations=lambda _: {})
    assert len(calls) == 2
    assert observed[0]['compute_pids'] == [123]
    assert queue.choose_device(observed, [0, 1], 0)['physical_gpu'] == 1
    def unknown(command, **kwargs):
        return SimpleNamespace(returncode=0, stdout='0, GPU-zero, 0, 0000:01:00.0\n' if '--query-gpu=index,uuid,memory.used,pci.bus_id' in command else 'GPU-unknown, 123\n')
    with pytest.raises(queue.runner.GateError, match='unknown GPU'):
        queue.inventory(unknown, reservations=lambda _: {})


@pytest.mark.parametrize('mutation', [
    {'candidate_indices': []}, {'candidate_indices': [True]},
    {'candidate_indices': [7, 7]}, {'single_exclusive_worker': False},
    {'rescan_if_unavailable': False},
])
def test_candidate_policy_requires_explicit_single_worker_authorization(mutation):
    state = state_for('/artifact')
    state['authorized_gpu_selection'].update(mutation)
    with pytest.raises(queue.runner.GateError):
        queue.candidate_indices(state)


def test_selects_only_idle_authorized_devices_and_prefers_current_binding():
    available = devices(5)
    available[7] = {**available[7], 'memory_used_mib': 0, 'compute_pids': []}
    assert queue.choose_device(available, [5, 7], 7)['physical_gpu'] == 7
    available[7]['compute_pids'] = [99]
    assert queue.choose_device(available, [5, 7], 7)['physical_gpu'] == 5
    available[5]['memory_used_mib'] = 1024
    assert queue.choose_device(available, [5, 7], 7) is None


def test_hardware_clone_preserves_provider_environment_and_all_scientific_inputs(tmp_path):
    metadata = tmp_path / 'new-metadata.json'
    metadata.write_text('{}')
    original = {'gpu_mapping': mapping(), 'files': [{'path': 'old-metadata'},
                 {'path': 'task-cache', 'sha256': 'input'}, {'path': 'provider-policy', 'sha256': 'provider'}],
                'egl_device_metadata_path': 'old-metadata', 'cuda_egl_probe': {'old': True},
                'cuda_egl_verified': True, 'tasks': {'0': {'seed': 123, 'cache': 'fixed'}},
                'environment': {'LIBERO_CONFIG_PATH': 'fixed'},
                'frozen_stage_provider': {'backend': 'codex_cli', 'model': 'gpt-6-astra', 'auth_mode': 'chatgpt'}}
    before = copy.deepcopy(original)
    cloned = queue.clone_runtime(original, mapping(5), metadata, None)
    assert original == before
    assert cloned['files'][:-1] == original['files'][1:]
    assert cloned['tasks'] == original['tasks']
    assert cloned['frozen_stage_provider'] == original['frozen_stage_provider']
    assert cloned['environment'] == original['environment']
    assert cloned['cuda_egl_verified'] is False
    assert 'cuda_egl_probe' not in cloned


def test_probe_reuse_requires_exact_hardware_source_ledger_and_frame(tmp_path, monkeypatch):
    root, artifact, _, _, runtime, _ = fixture_queue(tmp_path, monkeypatch)
    folder = artifact / 'runtime/probe'
    folder.mkdir()
    (folder / 'probe-frame.png').write_bytes(b'frame')
    evidence = {'resource_id': 'proof', 'frame_png_sha256': queue.runner.digest(folder / 'probe-frame.png')}
    evidence_path = folder / 'probe-evidence.json'
    evidence_path.write_text(json.dumps(evidence))
    runtime.update(cuda_egl_verified=True, cuda_egl_probe={'resource_id': 'proof',
                   'evidence_path': str(evidence_path), 'evidence_sha256': queue.runner.digest(evidence_path)})
    events = [{'event': 'completed', 'resource_id': 'proof',
               'source_script_sha256': queue.runner.digest(root / 'scripts/qd_ed_gpu_probe.py')}]
    validations = []
    monkeypatch.setattr(queue.probe, 'validate_probe_evidence', lambda *args: validations.append(args))
    assert queue.reusable_probe(runtime, mapping(), events, root=root) == runtime['cuda_egl_probe']
    assert len(validations) == 1
    for key, value in [('uuid', 'GPU-other'), ('driver_version', 'changed'),
                       ('egl_device_index', 2), ('physical_gpu', 5)]:
        assert queue.reusable_probe(runtime, {**mapping(), key: value}, events, root=root) is None
    assert queue.reusable_probe(runtime, mapping(), [{**events[0], 'source_script_sha256': 'old'}], root=root) is None
    assert queue.reusable_probe(runtime, mapping(), [{**events[0], 'event': 'aborted'}], root=root) is None
    (folder / 'probe-frame.png').write_bytes(b'modified')
    assert queue.reusable_probe(runtime, mapping(), events, root=root) is None


def test_admission_race_before_dispatch_returns_to_cpu_wait(tmp_path, monkeypatch):
    root, artifact, path, *_ = fixture_queue(tmp_path, monkeypatch)
    monkeypatch.setattr(queue, 'inventory', lambda: devices(7))
    calls = []
    def race(*args, **kwargs):
        calls.append(True)
        raise queue.runner.GateError('GPU7 has external compute processes')
    monkeypatch.setattr(queue, 'bind_plan', race)
    monkeypatch.setattr(queue.runner, 'run_plan', forbid)
    status = queue.run_queue(path, ['q0'], root=root, idle_seconds=0, sleep=lambda _: None, max_polls=2)
    assert status['status'] == 'waiting' and len(calls) == 2
    assert not (root / 'data/attempt-ledger.jsonl').exists()


@pytest.mark.parametrize('after_dispatch', ['episode', 'probe'])
def test_dispatched_failure_stops_without_retry(tmp_path, monkeypatch, after_dispatch):
    root, artifact, path, plan, runtime, row = fixture_queue(tmp_path, monkeypatch)
    monkeypatch.setattr(queue, 'inventory', lambda: devices(7))
    calls = []
    def fail(*args, **kwargs):
        calls.append(True)
        target = root / 'data' / ('attempt-ledger.jsonl' if after_dispatch == 'episode' else 'gpu-healthcheck-ledger.jsonl')
        id_key = 'attempt_id' if after_dispatch == 'episode' else 'resource_id'
        target.write_text(json.dumps({'event': 'dispatched', id_key: 'new'}) + '\n')
        raise queue.runner.GateError('GPU7 has external compute processes')
    monkeypatch.setattr(queue, 'bind_plan', fail)
    with pytest.raises(queue.runner.GateError):
        queue.run_queue(path, ['q0'], root=root, idle_seconds=0, sleep=forbid)
    status = json.loads((artifact / 'runtime/available-gpu-queue-status.json').read_text())
    assert status['status'] == 'failed' and len(calls) == 1
    assert status['completed_keys'] == []


def test_unexpected_error_stops_and_redacts_exception_body(tmp_path, monkeypatch):
    root, artifact, path, *_ = fixture_queue(tmp_path, monkeypatch)
    def fail(*args, **kwargs):
        raise ValueError('sensitive provider response')
    monkeypatch.setattr(queue, 'inventory', fail)
    with pytest.raises(ValueError):
        queue.run_queue(path, ['q0'], root=root, idle_seconds=0, sleep=forbid)
    status = (artifact / 'runtime/available-gpu-queue-status.json').read_text()
    assert 'sensitive' not in status
    assert json.loads(status)['reason'] == 'ValueError'


def test_completed_episode_records_result_and_exits(tmp_path, monkeypatch):
    root, artifact, path, plan, runtime, row = fixture_queue(tmp_path, monkeypatch)
    monkeypatch.setattr(queue, 'inventory', lambda: devices(7))
    monkeypatch.setattr(queue, 'bind_plan', lambda *a, **k: (path, plan, runtime))
    calls = []
    def run(*args, **kwargs):
        calls.append(kwargs)
        return [{'attempt_id': 'result', 'outcome_valid': True, 'success': False}]
    monkeypatch.setattr(queue.runner, 'run_plan', run)
    result = queue.run_queue(path, ['q0'], root=root, idle_seconds=0, sleep=forbid)
    assert result['status'] == 'completed'
    assert result['completed_keys'] == ['q0']
    assert result['results'][0]['success'] is False
    assert calls[0]['episode_keys'] == ['q0']


def test_episode_admission_race_after_successful_probe_can_wait(tmp_path, monkeypatch):
    root, artifact, path, plan, runtime, row = fixture_queue(tmp_path, monkeypatch)
    monkeypatch.setattr(queue, 'inventory', lambda: devices(7))
    def bind(*args, **kwargs):
        (root / 'data/gpu-healthcheck-ledger.jsonl').write_text(
            json.dumps({'event': 'dispatched', 'resource_id': 'completed-proof'}) + '\n')
        return path, plan, runtime
    monkeypatch.setattr(queue, 'bind_plan', bind)
    def race(*args, **kwargs):
        raise queue.runner.GateError('GPU7 has external compute processes')
    monkeypatch.setattr(queue.runner, 'run_plan', race)
    result = queue.run_queue(path, ['q0'], root=root, idle_seconds=0, sleep=forbid, max_polls=1)
    assert result['status'] == 'waiting'
    assert not (root / 'data/attempt-ledger.jsonl').exists()


def test_predispatch_wrapper_requires_exact_busy_reason():
    error = queue.runner.GateError('attempt stopped after failure; no automatic retry: reserved-only')
    terminal = {'event': 'aborted', 'failure_class': 'predispatch_gate',
                'reason': 'GPU5 has external compute processes'}
    assert queue.undispatched_admission_race(error, [terminal])
    assert not queue.undispatched_admission_race(error, [{**terminal, 'reason': 'Codex login failed'}])
    assert not queue.undispatched_admission_race(error, [{**terminal, 'failure_class': 'infrastructure'}])


def test_probe_admission_race_restores_previous_singleton_and_preserves_artifacts(tmp_path, monkeypatch):
    root, artifact, path, plan, runtime, row = fixture_queue(tmp_path, monkeypatch)
    events_path = artifact / 'selection.jsonl'
    monkeypatch.setattr(queue, 'current_metadata', lambda *a, **k: mapping(5))
    monkeypatch.setattr(queue, 'find_probe', lambda *a, **k: None)
    monkeypatch.setattr(queue.runner, 'gpu_admission', lambda **k: {})
    observed = []
    def race(*args, **kwargs):
        observed.append(queue.runner.read_state(root / 'research-state.yaml')['gpu_pool'])
        raise queue.runner.GateError('GPU5 has external compute processes')
    monkeypatch.setattr(queue.probe, 'run_probe', race)
    with pytest.raises(queue.runner.GateError, match='external compute'):
        queue.bind_plan(path, plan, runtime, devices(5)[5], row, events_path, root=root)
    assert observed == [[5]]
    assert queue.runner.read_state(root / 'research-state.yaml')['gpu_pool'] == [7]
    saved = list((artifact / 'runtime/resource_queue').glob('*/runtime-manifest.json'))
    assert len(saved) == 1
    assert json.loads(saved[0].read_text())['gpu_mapping']['physical_gpu'] == 5
    assert not (root / 'data/gpu-healthcheck-ledger.jsonl').exists()
    assert json.loads(path.read_text()) == plan


def test_reserved_probe_second_admission_race_unwraps_and_rescans(tmp_path, monkeypatch):
    root, artifact, path, plan, runtime, row = fixture_queue(tmp_path, monkeypatch)
    monkeypatch.setattr(queue, 'inventory', lambda: devices(5))
    monkeypatch.setattr(queue, 'current_metadata', lambda *a, **k: mapping(5))
    monkeypatch.setattr(queue, 'find_probe', lambda *a, **k: None)
    monkeypatch.setattr(queue.runner, 'gpu_admission', lambda **k: {})
    calls = []
    def reserved_then_busy(*args, **kwargs):
        calls.append(True)
        resource = 'reserved-only-' + str(len(calls))
        queue.runner.append_healthcheck_event(root, {'resource_id': resource, 'event': 'reserved'})
        queue.runner.append_healthcheck_event(root, {'resource_id': resource, 'event': 'aborted',
            'gpu_process_wall_seconds': 0, 'reason': 'GPU5 has external compute processes'})
        raise queue.runner.GateError('GPU probe failed; runtime readiness remains unchanged')
    monkeypatch.setattr(queue.probe, 'run_probe', reserved_then_busy)
    monkeypatch.setattr(queue.runner, 'run_plan', forbid)
    result = queue.run_queue(path, ['q0'], root=root, idle_seconds=0, sleep=lambda _: None, max_polls=2)
    assert result['status'] == 'waiting'
    assert len(calls) == 2
    state = queue.runner.read_state(root / 'research-state.yaml')
    assert state['gpu_pool'] == [7]
    assert state['budget']['dispatched'] == 0
    assert state['budget']['gpu_hours_consumed'] == 0
    assert not queue.probe_dispatch_ids(root)
    events = queue.runner.read_events(root / 'data/gpu-healthcheck-ledger.jsonl')
    assert [event['event'] for event in events] == ['reserved', 'aborted', 'reserved', 'aborted']
    wrapper = queue.runner.GateError('GPU probe failed; runtime readiness remains unchanged')
    assert not queue.undispatched_admission_race(wrapper, [],
        [{**events[-1], 'reason': 'probe context validation failed'}])
    assert not queue.undispatched_admission_race(wrapper, [],
        [{**events[-1], 'gpu_process_wall_seconds': 1}])


def test_hardware_plan_freeze_keeps_scientific_rows_and_records_actual_mask(tmp_path, monkeypatch):
    root, artifact, path, plan, runtime, row = fixture_queue(tmp_path, monkeypatch)
    plan.update(source_commit='frozen-source', profiles_sha256='same-profile',
                seed_plan_sha256='same-seeds', preflight_index='/old/nonhardware-preview.json')
    path.write_text(json.dumps(plan))
    original = path.read_bytes()
    proof = {'resource_id': 'verified-proof'}
    monkeypatch.setattr(queue, 'current_metadata', lambda *a, **k: mapping(5))
    monkeypatch.setattr(queue, 'find_probe', lambda *a, **k: proof)
    monkeypatch.setattr(queue.runner, 'gpu_admission', lambda **k: {})
    monkeypatch.setattr(queue.probe, 'run_probe', forbid)
    def validate(candidate, **kwargs):
        candidate = Path(candidate)
        if candidate == path:
            return plan, {}, runtime
        new_plan = json.loads(candidate.read_text())
        return new_plan, {}, json.loads(Path(new_plan['runtime_manifest_path']).read_text())
    monkeypatch.setattr(queue.runner, 'validate_plan', validate)
    new_path, new_plan, new_runtime = queue.bind_plan(path, plan, runtime, devices(5)[5], row,
                                                   artifact / 'selection.jsonl', root=root)
    assert path.read_bytes() == original
    assert new_path != path
    for key in ('source_commit', 'profiles_sha256', 'seed_plan_sha256', 'episodes', 'code_files'):
        assert new_plan[key] == plan[key]
    assert new_runtime['frozen_stage_provider'] == runtime['frozen_stage_provider']
    assert new_runtime['tasks'] == runtime['tasks']
    assert queue.runner.read_state(root / 'research-state.yaml')['gpu_pool'] == [5]
    preview = json.loads(Path(new_plan['hardware_selection']['hardware_environment_preview']).read_text())
    assert preview['environment_public']['CUDA_VISIBLE_DEVICES'] == '5'
    assert preview['parent_nonhardware_preflight_index'] == plan['preflight_index']
    assert new_plan['frozen_at']


def fake_process(proc, pid, parent, env, *, state='S', started='123'):
    folder = proc / str(pid)
    folder.mkdir()
    fields = [state, str(parent)] + ['0'] * 18
    fields[19] = started
    (folder / 'stat').write_text(f'{pid} (test process) ' + ' '.join(fields))
    if env is not None:
        (folder / 'environ').write_bytes(b'\0'.join(key.encode() + b'=' + value.encode()
                                                  for key, value in env.items()) + b'\0')


def test_uuid_reservation_detects_live_cpu_worker_without_storing_other_env(tmp_path):
    available = devices(7)
    fake_process(tmp_path, 200, 1, {'CUDA_VISIBLE_DEVICES': 'GPU-test-7',
                                    'UNRELATED_SECRET': 'never-persist-this-token'})
    reservation = queue.process_gpu_reservations(available, proc_root=tmp_path, own_pid=999)
    assert reservation[7] == [200]
    for index in available:
        available[index]['reserving_pids'] = reservation[index]
    assert not available[7]['compute_pids']
    assert queue.choose_device(available, list(range(8)), 7) is None
    serialized = json.dumps(available)
    assert 'never-persist' not in serialized
    assert 'UNRELATED_SECRET' not in serialized


def test_reservations_ignore_own_descendants_disabled_unset_dead_and_inaccessible(tmp_path):
    fake_process(tmp_path, 100, 1, {'CUDA_VISIBLE_DEVICES': 'GPU-test-7'})
    fake_process(tmp_path, 101, 100, {'CUDA_VISIBLE_DEVICES': 'GPU-test-7'})
    fake_process(tmp_path, 102, 101, {'CUDA_VISIBLE_DEVICES': 'GPU-test-7'})
    fake_process(tmp_path, 200, 1, {'CUDA_VISIBLE_DEVICES': ''})
    fake_process(tmp_path, 201, 1, {'CUDA_VISIBLE_DEVICES': '-1'})
    fake_process(tmp_path, 202, 1, {'OTHER': 'ignored'})
    fake_process(tmp_path, 203, 1, {'CUDA_VISIBLE_DEVICES': 'GPU-test-7'}, state='Z')
    fake_process(tmp_path, 204, 1, None)
    assert not any(queue.process_gpu_reservations(devices(), proc_root=tmp_path, own_pid=100).values())


def test_numeric_mask_uses_pci_order_not_nvidia_index_or_unproven_default():
    available = devices()
    available[0]['pci_bus_id'], available[7]['pci_bus_id'] = available[7]['pci_bus_id'], available[0]['pci_bus_id']
    assert queue.visible_mask_indices('0,2', 'PCI_BUS_ID', available) == {7, 2}
    assert queue.visible_mask_indices('0,2', '', available) == set()
    assert queue.visible_mask_indices('0,2', 'FASTEST_FIRST', available) == set()
    assert queue.visible_mask_indices('GPU-test-7', '', available) == {7}
    assert queue.visible_mask_indices('GPU-test-', '', available) == set()
    assert queue.visible_mask_indices('0,-1,2', 'PCI_BUS_ID', available) == {7}


def test_continuous_idle_window_resets_on_context_reservation_and_identity():
    available, windows = devices(7), {}
    queue.update_idle_windows(available, windows, 0, 120)
    queue.update_idle_windows(available, windows, 119, 120)
    assert queue.choose_device(available, list(range(8)), 7) is None
    queue.update_idle_windows(available, windows, 120, 120)
    assert queue.choose_device(available, list(range(8)), 7)['physical_gpu'] == 7
    available[7]['reserving_pids'] = [77]
    queue.update_idle_windows(available, windows, 130, 120)
    assert 7 not in windows
    available[7]['reserving_pids'] = []
    queue.update_idle_windows(available, windows, 150, 120)
    queue.update_idle_windows(available, windows, 270, 120)
    assert available[7]['idle_stable']
    available[7]['uuid'] = 'GPU-replaced'
    queue.update_idle_windows(available, windows, 280, 120)
    assert not available[7]['idle_stable']
    assert available[7]['idle_observed_seconds'] == 0
    available[7]['compute_pids'] = [88]
    queue.update_idle_windows(available, windows, 300, 120)
    assert 7 not in windows


def test_default_queue_waits_full_idle_window_before_any_binding(tmp_path, monkeypatch):
    root, artifact, path, plan, runtime, row = fixture_queue(tmp_path, monkeypatch)
    monkeypatch.setattr(queue, 'inventory', lambda: devices(7))
    monkeypatch.setattr(queue, 'bind_plan', forbid)
    ticks = iter([0, 30, 60, 90])
    status = queue.run_queue(path, ['q0'], root=root, sleep=lambda _: None,
                             monotonic=lambda: next(ticks), max_polls=4)
    assert status['status'] == 'waiting'
    assert status['idle_stability_seconds'] == 120
    assert status['gpu_inventory'][7]['idle_observed_seconds'] == 90
    assert not (root / 'data/attempt-ledger.jsonl').exists()


def test_reservation_recheck_before_dispatch_returns_to_wait(tmp_path, monkeypatch):
    root, artifact, path, plan, runtime, row = fixture_queue(tmp_path, monkeypatch)
    observed = [devices(7), devices(7)]
    observed[1][7]['reserving_pids'] = [123]
    snapshots = iter(observed)
    monkeypatch.setattr(queue, 'inventory', lambda: next(snapshots))
    monkeypatch.setattr(queue, 'bind_plan', lambda *a, **k: (path, plan, runtime))
    monkeypatch.setattr(queue.runner, 'run_plan', forbid)
    status = queue.run_queue(path, ['q0'], root=root, idle_seconds=0, sleep=forbid, max_polls=1)
    assert status['status'] == 'waiting'
    assert not (root / 'data/attempt-ledger.jsonl').exists()


@pytest.mark.parametrize('race_site', ['bind', 'run'])
def test_shared_runner_lock_waits_and_resumes_without_duplicate_dispatch(tmp_path, monkeypatch, race_site):
    root, artifact, path, plan, runtime, row = fixture_queue(tmp_path, monkeypatch)
    monkeypatch.setattr(queue, 'inventory', lambda: devices(7))
    monkeypatch.setattr(queue, 'reservation_admission', lambda *a: None)
    state_path = artifact / 'runtime/available-gpu-queue-status.json'
    held = queue.runner.locked(root / 'data/qd-ed-runner.lock', nonblocking=True)
    held.__enter__()
    calls, sleeps = [], []
    def bind(*args, **kwargs):
        calls.append('bind')
        if race_site == 'bind':
            with queue.runner.locked(root / 'data/qd-ed-runner.lock', nonblocking=True):
                pass
        return path, plan, runtime
    def run(*args, **kwargs):
        with queue.runner.locked(root / 'data/qd-ed-runner.lock', nonblocking=True):
            calls.append('dispatch')
        return [{'outcome_valid': True}]
    def sleep(seconds):
        sleeps.append(seconds)
        assert json.loads(state_path.read_text())['status'] == 'waiting_runner'
        assert 'dispatch' not in calls
        held.__exit__(None, None, None)
    monkeypatch.setattr(queue, 'bind_plan', bind)
    monkeypatch.setattr(queue.runner, 'run_plan', run)
    try:
        result = queue.run_queue(path, ['q0'], root=root, idle_seconds=0, sleep=sleep, max_polls=2)
    finally:
        if not sleeps:
            held.__exit__(None, None, None)
    assert result['status'] == 'completed'
    assert sleeps == [30] and calls.count('dispatch') == 1
    assert result['completed_keys'] == ['q0']


def test_shared_wait_distinguishes_foreign_dispatch_and_own_gpu_work(tmp_path):
    root = tmp_path / 'worktree'
    artifact = tmp_path / 'artifact'
    busy = queue.runner.LockBusyError(root / 'data/qd-ed-runner.lock')
    foreign = {'event': 'dispatched', 'output_dir': str(tmp_path / 'other-study/attempt')}
    own = {'event': 'dispatched', 'output_dir': str(artifact / 'attempt')}
    kwargs = {'root': root, 'artifact': artifact}
    assert queue.undispatched_shared_wait(busy, [foreign], [], **kwargs)
    assert queue.undispatched_shared_wait(queue.runner.GateError(queue.UNFINISHED_JOURNAL),
                                        [], [foreign], **kwargs)
    assert not queue.undispatched_shared_wait(busy, [own], [], **kwargs)
    assert not queue.undispatched_shared_wait(busy, [], [own], **kwargs)
    assert not queue.undispatched_shared_wait(busy, [{'event': 'dispatched'}], [], **kwargs)
    assert not queue.undispatched_shared_wait(queue.runner.LockBusyError(root / 'data/other.lock'),
                                            [], [], **kwargs)
    assert not queue.undispatched_shared_wait(queue.runner.GateError('frozen file changed'),
                                            [], [], **kwargs)
