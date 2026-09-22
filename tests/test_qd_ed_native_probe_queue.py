"""CPU-only diagnostic queue tests; all GPU/native/episode entrypoints mocked."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import time

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('qd_ed_native_probe_queue',
                                             ROOT / 'scripts/qd_ed_native_probe_queue.py')
nq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nq)


def forbid(*args, **kwargs):
    raise AssertionError('unexpected episode, GPU, or network operation')


def devices(idle=None):
    return {i: {'physical_gpu': i, 'uuid': f'GPU-test-{i}', 'pci_bus_id': f'0000:{i+1:02x}:00.0',
                'memory_used_mib': 0 if i == idle else 8000,
                'compute_pids': [] if i == idle else [100+i], 'reserving_pids': []}
            for i in range(8)}


def fixture(tmp_path, monkeypatch):
    root, artifact = tmp_path / 'worktree', tmp_path / 'artifact'
    (root / 'data').mkdir(parents=True)
    (root / 'scripts').mkdir()
    (artifact / 'runtime').mkdir(parents=True)
    records = []
    for relative in sorted(nq.REQUIRED_QUEUE_CODE):
        path = root / relative
        path.write_bytes((ROOT / relative).read_bytes())
        records.append({'path': relative, 'sha256': nq.runner.digest(path)})
    state = {'run_name': 'native-unit-test', 'artifacts': str(artifact), 'gpu_pool': [7],
             'max_concurrent_gpu_workers': 1,
             'authorized_gpu_selection': {'candidate_indices': list(range(8)),
                                         'single_exclusive_worker': True,
                                         'rescan_if_unavailable': True},
             'budget': {'max_episode_attempts': 240, 'max_gpu_hours': 48,
                        'dispatched': 0, 'gpu_hours_consumed': 0,
                        'reserved': dict(nq.runner.BUCKETS)}}
    (root / 'research-state.yaml').write_text(yaml.safe_dump(state))
    row = {'episode_key': nq.RESOURCE_PREFLIGHT_KEY, 'split': 'dev', 'iteration': 'N1',
           'profile': 'C0', 'task_id': 0, 'env_seed': 1, 'policy_seed': 1, 'init_index': 0,
           'budget_bucket': 'development', 'timeout_seconds': 1800}
    config = {'frozen': 'policy-config'}
    config_path = artifact / 'policy-config.json'
    config_path.write_text(json.dumps(config))
    plan = {'source_commit': 'frozen-head', 'artifact_root': str(artifact),
            'code_files': records, 'episodes': [row],
            'diagnostic_only': {'kind': 'policy_native_diagnostic', 'scope': copy.deepcopy(nq.native.SCOPE),
                'synthetic_seed': nq.native.SYNTHETIC_SEED, 'synthetic_task': nq.native.SYNTHETIC_TASK,
                'timeout_seconds': 600, 'policy_configuration_path': str(config_path),
                'policy_configuration_sha256': nq.runner.digest(config_path)},
            'phase_authorization': {'dev': False, 'validation': False, 'formal': False}}
    path = artifact / 'diagnostic-plan.json'
    path.write_text(json.dumps(plan))
    runtime = {'gpu_mapping': {'physical_gpu': 7, 'egl_device_index': 4, 'uuid': 'GPU-test-7'}}
    monkeypatch.setattr(nq.native, 'validate_inputs', lambda p, r: (nq.runner.read_json(p), copy.deepcopy(runtime), config))
    monkeypatch.setattr(nq, 'current_head', lambda _: 'frozen-head')
    monkeypatch.setattr(nq.queue, 'inventory', lambda: devices())
    monkeypatch.setattr(nq.queue, 'bind_plan', lambda p, plan, runtime, *a, **k: (p, plan, runtime))
    monkeypatch.setattr(nq.queue, 'reservation_admission', lambda _: None)
    monkeypatch.setattr(nq.native, 'run_probe', forbid)
    monkeypatch.setattr(nq.runner, 'run_plan', forbid)
    ticks = iter(range(0, 12000, 120))
    return root, artifact, path, plan, lambda: next(ticks)


def completed(plan_path, resource_id='one-native-diagnostic'):
    plan = nq.runner.read_json(plan_path)
    return {'event': 'completed', 'resource_id': resource_id, 'kind': 'policy_native_diagnostic',
            'scope': nq.native.SCOPE, 'plan_sha256': nq.runner.digest(plan_path),
            'source_commit': plan['source_commit'], 'physical_gpu': 7}


def test_busy_wait_is_cpu_only_and_never_opens_an_episode(tmp_path, monkeypatch):
    root, artifact, path, _, clock = fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(nq.queue, 'bind_plan', forbid)
    sleeps = []
    result = nq.run_queue(path, root=root, sleep=sleeps.append, monotonic=clock, max_polls=2)
    assert result['status'] == 'waiting' and sleeps == [30]
    assert result['scientific_episodes_authorized'] is False
    assert result['scientific_episodes_dispatched'] == 0
    assert result['resource_preflight_row_only'] == 'n1_dev_t00_c0'
    assert not (root / 'data/attempt-ledger.jsonl').exists()
    assert not (root / 'data/gpu-healthcheck-ledger.jsonl').exists()
    assert nq.runner.read_json(artifact / 'runtime/native-probe-queue-status.json')['status'] == 'waiting'


def test_one_native_probe_runs_only_after_stable_idle_and_stops(tmp_path, monkeypatch):
    root, artifact, path, _, clock = fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(nq.queue, 'inventory', lambda: devices(7))
    calls = []
    def probe(p, **kwargs):
        calls.append((p, kwargs))
        return completed(p)
    monkeypatch.setattr(nq.native, 'run_probe', probe)
    sleeps = []
    result = nq.run_queue(path, root=root, sleep=sleeps.append, monotonic=clock)
    assert result['status'] == 'completed' and sleeps == [30]
    assert len(calls) == 1 and calls[0][1]['timeout_seconds'] == 600
    assert result['gpu_inventory'][7]['idle_observed_seconds'] == 120
    assert not (root / 'data/attempt-ledger.jsonl').exists()


@pytest.mark.parametrize('probe_kind', ['mapping', 'native'])
def test_any_dispatched_resource_failure_stops_without_repeat(tmp_path, monkeypatch, probe_kind):
    root, artifact, path, _, clock = fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(nq.queue, 'inventory', lambda: devices(7))
    calls = []
    def fail(*args, **kwargs):
        calls.append(probe_kind)
        ledger = root / 'data/gpu-healthcheck-ledger.jsonl'
        ledger.write_text(json.dumps({'event': 'dispatched', 'resource_id': 'new-resource'}) + '\n')
        if probe_kind == 'native':
            return {'event': 'aborted', 'resource_id': 'new-resource',
                    'reason': 'GPU7 has external compute processes'}
        raise nq.runner.GateError('GPU7 has external compute processes')
    monkeypatch.setattr(nq.queue if probe_kind == 'mapping' else nq.native,
                        'bind_plan' if probe_kind == 'mapping' else 'run_probe', fail)
    with pytest.raises(nq.runner.GateError, match='external compute'):
        nq.run_queue(path, root=root, sleep=lambda _: None, monotonic=clock)
    status = nq.runner.read_json(artifact / 'runtime/native-probe-queue-status.json')
    assert status['status'] == 'failed' and calls == [probe_kind]
    assert not (root / 'data/attempt-ledger.jsonl').exists()


def test_predispatch_admission_race_waits_without_native_or_episode_call(tmp_path, monkeypatch):
    root, artifact, path, _, clock = fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(nq.queue, 'inventory', lambda: devices(7))
    def busy(*args, **kwargs):
        raise nq.runner.GateError('GPU7 has external GPU reservations')
    monkeypatch.setattr(nq.queue, 'bind_plan', busy)
    result = nq.run_queue(path, root=root, sleep=lambda _: None, monotonic=clock, max_polls=2)
    assert result['status'] == 'waiting'
    assert not (root / 'data/gpu-healthcheck-ledger.jsonl').exists()


@pytest.mark.parametrize('change', ['source', 'phase_gate', 'head'])
def test_source_or_plan_gate_drift_fails_while_waiting_before_gpu_binding(tmp_path, monkeypatch, change):
    root, artifact, path, plan, clock = fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(nq.queue, 'bind_plan', forbid)
    def change_contract(_seconds):
        if change == 'source':
            (root / nq.SCRIPT_RELATIVE).write_text('changed queue source')
        elif change == 'phase_gate':
            plan['phase_authorization']['dev'] = True
            path.write_text(json.dumps(plan))
        else:
            monkeypatch.setattr(nq, 'current_head', lambda _: 'changed-head')
    with pytest.raises(nq.runner.GateError, match='changed'):
        nq.run_queue(path, root=root, sleep=change_contract, monotonic=clock)
    assert nq.runner.read_json(artifact / 'runtime/native-probe-queue-status.json')['status'] == 'failed'
    assert not (root / 'data/gpu-healthcheck-ledger.jsonl').exists()


@pytest.mark.parametrize('gate_value', [True, 0])
def test_scientific_authorization_must_be_explicit_boolean_false(tmp_path, monkeypatch, gate_value):
    root, artifact, path, plan, clock = fixture(tmp_path, monkeypatch)
    plan['phase_authorization']['dev'] = gate_value
    path.write_text(json.dumps(plan))
    with pytest.raises(nq.runner.GateError, match='all scientific phase gates false'):
        nq.run_queue(path, root=root, sleep=forbid, monotonic=clock)


def test_atomic_heartbeat_continues_during_blocking_native_probe(tmp_path, monkeypatch):
    root, artifact, path, _, clock = fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(nq.queue, 'inventory', lambda: devices(7))
    monkeypatch.setattr(nq, 'HEARTBEAT_SECONDS', .01)
    status_path = artifact / 'runtime/native-probe-queue-status.json'
    def probe(*args, **kwargs):
        before = nq.runner.read_json(status_path)['updated_unix']
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            time.sleep(.005)
            observed = nq.runner.read_json(status_path)
            if observed['updated_unix'] > before:
                assert observed['status'] == 'running_diagnostic'
                return completed(path, 'heartbeat-probe')
        raise AssertionError('no heartbeat while diagnostic blocked')
    monkeypatch.setattr(nq.native, 'run_probe', probe)
    assert nq.run_queue(path, root=root, sleep=lambda _: None, monotonic=clock)['status'] == 'completed'


def test_gpu7_only_authorization_ignores_other_idle_devices(tmp_path, monkeypatch):
    root, artifact, path, _, clock = fixture(tmp_path, monkeypatch)
    state_path = root / 'research-state.yaml'
    state = nq.runner.read_state(state_path)
    state['authorized_gpu_selection']['candidate_indices'] = [7]
    state_path.write_text(yaml.safe_dump(state))
    monkeypatch.setattr(nq.queue, 'inventory', lambda: devices(5))
    monkeypatch.setattr(nq.queue, 'bind_plan', forbid)
    result = nq.run_queue(path, root=root, sleep=lambda _: None, monotonic=clock, max_polls=2)
    assert result['status'] == 'waiting'
    assert result['selected_physical_gpu'] is None
    assert result['gpu_inventory'][5]['idle_stable'] is True


@pytest.mark.parametrize('change', ['scope', 'seed', 'config'])
def test_diagnostic_scope_and_configuration_are_frozen(tmp_path, monkeypatch, change):
    root, artifact, path, plan, clock = fixture(tmp_path, monkeypatch)
    if change == 'scope':
        plan['diagnostic_only']['scope']['simulation_steps'] = 1
    elif change == 'seed':
        plan['diagnostic_only']['synthetic_seed'] += 1
    else:
        Path(plan['diagnostic_only']['policy_configuration_path']).write_text('{}')
    path.write_text(json.dumps(plan))
    with pytest.raises(nq.runner.GateError, match='diagnostic scope|policy configuration'):
        nq.run_queue(path, root=root, sleep=forbid, monotonic=clock)


def test_rebound_plan_cannot_enable_scientific_episodes(tmp_path, monkeypatch):
    root, artifact, path, plan, clock = fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(nq.queue, 'inventory', lambda: devices(7))
    def rebound(*args, **kwargs):
        plan['phase_authorization']['dev'] = True
        path.write_text(json.dumps(plan))
        return path, plan, {}
    monkeypatch.setattr(nq.queue, 'bind_plan', rebound)
    with pytest.raises(nq.runner.GateError, match='scientific phase gates false'):
        nq.run_queue(path, root=root, sleep=lambda _: None, monotonic=clock)


def test_completed_resource_must_match_frozen_native_scope(tmp_path, monkeypatch):
    root, artifact, path, _, clock = fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(nq.queue, 'inventory', lambda: devices(7))
    monkeypatch.setattr(nq.native, 'run_probe', lambda *a, **k: {**completed(path), 'scope': {}})
    with pytest.raises(nq.runner.GateError, match='resource contract mismatch'):
        nq.run_queue(path, root=root, sleep=lambda _: None, monotonic=clock)


def inflight_resource(root):
    for event in ('reserved', 'dispatched'):
        nq.runner.append_healthcheck_event(root, {'resource_id': 'externally-owned-resource',
            'event': event, 'physical_gpu': 6, 'output_dir': '/external-namespace/unchanged'})


def test_inflight_journal_waits_on_cpu_without_query_dispatch_or_reconciliation(tmp_path, monkeypatch):
    root, artifact, path, _, clock = fixture(tmp_path, monkeypatch)
    inflight_resource(root)
    ledger = root / 'data/gpu-healthcheck-ledger.jsonl'
    original = ledger.read_bytes()
    monkeypatch.setattr(nq.queue, 'inventory', forbid)
    monkeypatch.setattr(nq.queue, 'bind_plan', forbid)
    monkeypatch.setattr(nq.runner, 'reconcile_ledger', forbid)
    waits = []
    result = nq.run_queue(path, root=root, sleep=waits.append, monotonic=clock, max_polls=2)
    assert result['status'] == 'waiting_journal' and waits == [30]
    assert result['scientific_episodes_dispatched'] == 0
    assert ledger.read_bytes() == original
    assert not (root / 'data/attempt-ledger.jsonl').exists()
    assert nq.runner.read_json(artifact / 'runtime/native-probe-queue-status.json')['status'] == 'waiting_journal'


def test_owner_terminal_event_allows_fresh_idle_window_then_single_native_probe(tmp_path, monkeypatch):
    root, artifact, path, _, clock = fixture(tmp_path, monkeypatch)
    inflight_resource(root)
    monkeypatch.setattr(nq.queue, 'inventory', lambda: devices(7))
    monkeypatch.setattr(nq.runner, 'reconcile_ledger', forbid)
    observed, calls = [], []
    def owner_finishes(_seconds):
        phase = nq.runner.read_json(artifact / 'runtime/native-probe-queue-status.json')['status']
        observed.append(phase)
        if phase == 'waiting_journal':
            nq.runner.append_healthcheck_event(root, {'resource_id': 'externally-owned-resource',
                'event': 'completed', 'gpu_process_wall_seconds': 1.0, 'physical_gpu': 6})
    def probe(*args, **kwargs):
        calls.append(True)
        return completed(path)
    monkeypatch.setattr(nq.native, 'run_probe', probe)
    result = nq.run_queue(path, root=root, sleep=owner_finishes, monotonic=clock)
    assert observed == ['waiting_journal', 'waiting']
    assert result['status'] == 'completed' and calls == [True]
    assert result['gpu_inventory'][7]['idle_observed_seconds'] == 120
    assert not (root / 'data/attempt-ledger.jsonl').exists()


@pytest.mark.parametrize('reason', [
    'unfinished attempt or healthcheck requires reconciliation extra',
    'native queue source HEAD changed',
])
def test_journal_wait_exception_match_is_exact_and_other_gates_still_fail(tmp_path, monkeypatch, reason):
    root, artifact, path, _, clock = fixture(tmp_path, monkeypatch)
    def rejected(*args, **kwargs):
        raise nq.runner.GateError(reason)
    monkeypatch.setattr(nq, 'waiting_gate', rejected)
    monkeypatch.setattr(nq.queue, 'inventory', forbid)
    with pytest.raises(nq.runner.GateError, match=reason):
        nq.run_queue(path, root=root, sleep=forbid, monotonic=clock)
    assert nq.runner.read_json(artifact / 'runtime/native-probe-queue-status.json')['status'] == 'failed'


def test_same_journal_error_after_resource_dispatch_still_stops(tmp_path, monkeypatch):
    root, artifact, path, _, clock = fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(nq.queue, 'inventory', lambda: devices(7))
    calls = []
    def failed_native(*args, **kwargs):
        calls.append(True)
        inflight_resource(root)
        raise nq.runner.GateError('unfinished attempt or healthcheck requires reconciliation')
    monkeypatch.setattr(nq.native, 'run_probe', failed_native)
    with pytest.raises(nq.runner.GateError, match='requires reconciliation'):
        nq.run_queue(path, root=root, sleep=lambda _: None, monotonic=clock)
    assert calls == [True]
    assert nq.runner.read_json(artifact / 'runtime/native-probe-queue-status.json')['status'] == 'failed'
