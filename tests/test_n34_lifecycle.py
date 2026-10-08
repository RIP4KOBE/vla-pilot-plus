"""N34 lifecycle/accounting on synthetic journals and Popen; no GPU dispatch.

Exercises the new runner, retaining existing accounting semantics. It does not
certify current owning balances or release authority.
"""
import copy
import datetime as dt
from pathlib import Path
import subprocess
import sys
import json
import pytest
import yaml
from scripts import qd_ed_final_runner as r, qd_ed_n23_worker as w
from scripts import qd_ed_n34_contract as c, qd_ed_n34_release as release
from scripts import qd_ed_n34_runner as adapter, qd_ed_n34_supervise as supervisor
from test_n34_production_integration import write

NOW = dt.datetime(2026, 10, 8, tzinfo=dt.timezone.utc)


CAPS = {'attempts': 1800, 'gpu_hours': 224., 'buckets': {'baseline': 400, 'development': 1120, 'validation': 180, 'formal': 40, 'recovery': 60}, 'protected_gpu_hours': {'validation': 32., 'formal': 12.}}


def budget_fixture(tmp_path, events=(), resources=()):
    authority = {'prospective_recovery': copy.deepcopy(c.REPLACEMENT), 'caps': copy.deepcopy(CAPS), 'amendment': {'synthetic': True}, 'starts_at': '2026-10-01T00:00:00Z',
                 'coordinator_ends_at': release.COORDINATOR_END,
                 'weekly_window': {'origin_gpu_hours': 53.08404692669838, 'increment_gpu_hours': 168., 'ends_at': c.DEADLINE}}
    reference = write(tmp_path / 'authority.json', authority)
    plan = {'authority': reference, 'stop_path': str(tmp_path / 'STOP')}
    snap = r.budget_snapshot(events, resources)
    state = {'gpu_pool': [7], 'max_concurrent_gpu_workers': 1, 'n34_budget_authority': reference,
             'resource_isolation': {'status': 'ACTIVE', 'validation_status': 'PASS', 'private_budget': True},
             'budget': {**snap, 'max_episode_attempts': 1800, 'max_gpu_hours': 224., 'reserved': copy.deepcopy(CAPS['buckets']),
                        'gpu_hour_reservations': copy.deepcopy(CAPS['protected_gpu_hours']), 'amendment': authority['amendment']}}
    reservations = [{'event': 'gpu_hour_reservations_changed', 'gpu_hour_reservations': CAPS['protected_gpu_hours'], 'rationale': 'synthetic fixture only', 'time_unix': 1}]
    return plan, authority, state, reservations


def historical(seconds=3600., bucket='development', attempt='old', cohort='HISTORY', end='valid'):
    base = {'attempt_id': attempt, 'identity': {'iteration': cohort}, 'budget_bucket': bucket, 'episode_key': attempt}
    return [{**base, 'event': 'reserved'}, {**base, 'event': 'dispatched'},
            {**base, 'event': end, 'gpu_process_wall_seconds': seconds, 'outcome_valid': False}]


def old_invalid(seconds=0.):
    events = []
    for episode, cohort, bucket in c.INVALID_HISTORY:
        group = historical(seconds, bucket, episode, cohort, 'valid')
        group[-1].update(success=None, required_cost_telemetry_complete=False)
        events.extend(group)
    return events


def health(seconds=360., cohort='HISTORY'):
    return [{'resource_id': 'probe', 'event': kind, 'cohort': cohort, 'gpu_process_wall_seconds': seconds}
            for kind in ('reserved', 'dispatched', 'completed')]


def admit(tmp_path, events=(), resources=(), change=None):
    events = old_invalid() + list(events)
    plan, authority, state, reservations = budget_fixture(tmp_path, events, resources)
    if change:
        change(plan, authority, state, reservations)
    return release.admission(plan, authority, state, list(events), list(resources), reservations, c.expected_rows()[0], now=NOW, gpu_idle=True)


def test_generic_historical_charges_and_health_preserved(tmp_path):
    events = historical() + historical(900, 'baseline', 'aborted', end='aborted')
    resources = health()
    snap = admit(tmp_path, events, resources)
    assert snap['gpu_hours_consumed'] == 1.35
    assert snap['gpu_hours_by_bucket']['development'] == 1.
    assert snap['gpu_healthcheck_hours'] == .1
    assert snap['gpu_hours_by_bucket']['recovery'] == .1
    assert snap['dispatched'] == 5 and snap['aborted'] == 1


@pytest.mark.parametrize('kind', ['reserved', 'dispatched', 'health_reserved', 'health_dispatched', 'unknown_episode', 'unknown_health'])
def test_unsettled_or_unknown_never_zero_cost(tmp_path, kind):
    events, resources = [], []
    if kind in ('reserved', 'dispatched'):
        events = historical()[:1 if kind == 'reserved' else 2]
    elif kind.startswith('health_'):
        resources = health()[:1 if kind == 'health_reserved' else 2]
    elif kind == 'unknown_episode':
        events = historical(); events[-1]['gpu_process_wall_seconds'] = None
    else:
        resources = health(); resources[-1].pop('gpu_process_wall_seconds')
    with pytest.raises((r.GateError, ValueError)):
        admit(tmp_path, events, resources)


@pytest.mark.parametrize('kind', ['bucket', 'global', 'protected_attempts', 'private', 'hold', 'state_cost', 'reservations', 'STOP', 'deadline', 'weekly', 'cohort'])
def test_admission_boundaries(tmp_path, kind):
    events = []
    if kind == 'bucket':
        events = [e for i in range(60) for e in historical(0., 'recovery', f'h{i}')]
    if kind == 'global':
        events = [e for i in range(1800) for e in historical(0., 'development', f'h{i}')]
    if kind == 'protected_attempts':
        events = [e for i in range(1580) for e in historical(0., 'recovery', f'h{i}')]
    if kind == 'weekly':
        events = historical((53.08404692669838 + 168 - 44) * 3600 - 1839.)
    if kind == 'cohort':
        events = historical(18000 - 1839, cohort=c.COHORT)
    def change(plan, authority, state, reservations):
        if kind == 'private': state['resource_isolation']['private_budget'] = False
        if kind == 'hold': state['external_resource_hold'] = {'do_not_auto_resume': True}
        if kind == 'state_cost': state['budget']['gpu_hours_consumed'] += 1
        if kind == 'reservations': reservations.clear()
        if kind == 'STOP': Path(plan['stop_path']).touch()
        if kind == 'deadline': authority['starts_at'] = '2026-10-09T00:00:00Z'
    with pytest.raises((r.GateError, ValueError)):
        admit(tmp_path, events, change=change)


@pytest.mark.parametrize('seconds,allowed', [(1840.01, True), (1839.99, False)])
def test_full_episode_weekly_and_protected_seconds(tmp_path, seconds, allowed):
    events = historical((53.08404692669838 + 168 - 44) * 3600 - seconds)
    if allowed:
        admit(tmp_path, events)
    else:
        with pytest.raises(ValueError): admit(tmp_path, events)


@pytest.fixture
def lifecycle(tmp_path, monkeypatch):
    tmp_path = tmp_path / 'study_worktree'
    tmp_path.mkdir()
    rows = c.expected_rows()
    monkeypatch.setattr(c, 'expected_rows', lambda root=None: rows)
    plan, authority, state, reservations = budget_fixture(tmp_path, old_invalid())
    plan['stop_path'] = c.stop_path(tmp_path)
    Path(plan['stop_path']).parent.mkdir()
    plan.update(worktree=str(tmp_path), artifact_root=str(tmp_path / 'artifacts/n34'), episodes=rows,
                run_name='synthetic', source={'commit': 'a'*40}, runtime={'path': str(tmp_path / 'runtime'), 'sha256': 'b'*64},
                runtime_inventory_sha256='c'*64, expected_manifests={})
    for row in rows:
        output = Path(plan['artifact_root']) / 'attempts' / row['episode_key']
        plan['expected_manifests'][row['episode_key']] = write(tmp_path / 'manifests' / (row['episode_key'] + '.json'),
            {'row': row, 'output_dir': str(output), 'argv': [sys.executable, 'main.py']})
    state.update(run_name='synthetic', artifacts=str(tmp_path / 'artifacts'))
    runtime = {'artifact_root': state['artifacts'], 'gpu_mapping': {'physical_gpu': 7, 'egl_device_index': 4}, 'frozen_stage_provider': {'backend': 'codex_cli'}}
    (tmp_path / 'data').mkdir()
    for name in ('attempt-ledger.jsonl', 'gpu-healthcheck-ledger.jsonl'):
        (tmp_path / 'data' / name).write_text('')
    (tmp_path / 'data/attempt-ledger.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in old_invalid()))
    (tmp_path / 'data/gpu-hour-reservation-ledger.jsonl').write_text(json.dumps(reservations[0]) + '\n')
    (tmp_path / 'research-state.yaml').write_text(yaml.safe_dump(state))
    authority['ledger_prefixes'] = {name: adapter.journal_prefix(tmp_path / 'data' / name) for name in ('attempt-ledger.jsonl', 'gpu-healthcheck-ledger.jsonl')}
    plan_ref = write(tmp_path / 'plan.json', plan)
    release_ref = write(tmp_path / 'release.json', {'synthetic_only': True})
    monkeypatch.setattr(release, 'validate_release', lambda *a: (plan, runtime, authority))
    monkeypatch.setattr(adapter, 'device_check', lambda: {'synthetic_only': True})
    monkeypatch.setattr(adapter, 'check_probe', lambda *a: None)
    monkeypatch.setattr(r, 'child_environment', lambda runtime: {})
    monkeypatch.setattr(r, 'verify_provider', lambda *a, **kw: None)
    monkeypatch.setattr(r, 'stage_condition', lambda runtime: 'synthetic')
    monkeypatch.setattr(adapter.b, 'profiles', lambda root: {'profiles': {a: {} for a in c.ARMS}})
    monkeypatch.setattr(r, 'validate_result', lambda *a: {'outcome_valid': True, 'required_cost_telemetry_complete': True, 'success': True})
    monkeypatch.setattr(adapter.worker, 'verify_terminal', lambda *a: None)
    monkeypatch.setattr(adapter.worker, 'c', c)
    created = []
    class FakeProcess:
        pid = 90001
        def __init__(self, *args, **kwargs):
            self.returncode = None
            created.append(self)
            self.stdin = self
            self.command = args[0]
        def write(self, data): assert data == b'G'
        def flush(self): pass
        def close(self): pass
        def poll(self): return self.returncode
        def wait(self, timeout): self.returncode = 0; return 0
    monkeypatch.setattr(adapter.subprocess, 'Popen', FakeProcess)
    def identity(pid):
        if created and created[-1].returncode is not None:
            raise FileNotFoundError('synthetic exited process')
        return {'pid': pid, 'proc_start_ticks': '123', 'boot_id': 'synthetic-boot'}
    monkeypatch.setattr(adapter, 'process_identity', identity)
    def wait(process, timeout, **kwargs):
        assert 0 < timeout <= 1800
        context = w.read_ref({'path': process.command[-3], 'sha256': process.command[-1]})
        row = next(x for x in rows if x['episode_key'] == context['episode_key'])
        output = Path(w.read_ref(plan['expected_manifests'][row['episode_key']])['output_dir'])
        record = json.loads((output / 'process.json').read_text())
        assert record['attempt_id'] == context['attempt_id'] == row['episode_key']
        assert record['release'] == context['release'] == release_ref
        assert record['context'] == {'path': process.command[-3], 'sha256': process.command[-1]}
        write(output / 'eds_eval/n34-worker-receipt.json', {'synthetic_only': True})
        process.returncode = 0
        return 0
    monkeypatch.setattr(r, 'wait_exclusively', wait)
    return tmp_path, plan, plan_ref, release_ref


def test_reserve_dispatch_terminal_and_resume_next(lifecycle):
    root, plan, plan_ref, release_ref = lifecycle
    first = adapter.execute_one(plan_ref, release_ref)
    assert first['status'] == 'VALID'
    events = r.read_events(root / 'data/attempt-ledger.jsonl')
    assert events[:9] == old_invalid()
    assert [e['event'] for e in events[9:]] == ['reserved', 'dispatched', 'valid']
    assert all(e['attempt_id'] == plan['episodes'][0]['episode_key'] for e in events[9:])
    assert all(e['replacement'] == c.REPLACEMENT and e['budget_bucket'] == 'recovery' for e in events[9:])
    before = copy.deepcopy(events)
    assert adapter.execute_one(plan_ref, release_ref)['status'] == 'VALID'
    assert r.read_events(root / 'data/attempt-ledger.jsonl')[:12] == before
    assert r.read_state(root / 'research-state.yaml')['budget']['dispatched'] == 5
    assert not (root / 'driver.lock').exists() and not (root / 'coordinator.lease').exists()


@pytest.mark.parametrize('fault', ['receipt', 'telemetry', 'worker_exit'])
def test_invalid_charged_stop_no_retry(lifecycle, monkeypatch, fault):
    root, plan, plan_ref, release_ref = lifecycle
    def fail(*args, **kwargs): raise ValueError('synthetic invalid evidence')
    if fault == 'receipt': monkeypatch.setattr(adapter.worker, 'verify_terminal', fail)
    elif fault == 'telemetry': monkeypatch.setattr(r, 'validate_result', fail)
    else:
        def wait(process, *args, **kwargs): process.returncode = 2; return 2
        monkeypatch.setattr(r, 'wait_exclusively', wait)
    result = adapter.execute_one(plan_ref, release_ref)
    assert result['status'] == 'INVALID_STOP'
    terminal = result['terminal']
    assert terminal['success'] is None and terminal['task_failure'] is False and terminal['gpu_process_wall_seconds'] > 0
    assert adapter.execute_one(plan_ref, release_ref)['status'] == 'INVALID_STOP'
    assert len(r.read_events(root / 'data/attempt-ledger.jsonl')) == 12


def test_live_unknown_never_signalled_or_restarted(lifecycle, monkeypatch):
    root, plan, plan_ref, release_ref = lifecycle
    def unknown(*args, **kwargs): raise KeyboardInterrupt('synthetic controller interruption')
    monkeypatch.setattr(r, 'wait_exclusively', unknown)
    monkeypatch.setattr(adapter, 'cleanup_owned', lambda *a: pytest.fail('must not signal unknown/live episode'))
    with pytest.raises(KeyboardInterrupt): adapter.execute_one(plan_ref, release_ref)
    Path(plan['stop_path']).touch()
    assert adapter.execute_one(plan_ref, release_ref)['status'] == 'LIVE_OR_UNSETTLED'
    assert [e['event'] for e in r.read_events(root / 'data/attempt-ledger.jsonl')[9:]] == ['reserved', 'dispatched']


def test_timeout_exact_owned_cleanup_retains_charge(lifecycle, monkeypatch):
    root, plan, plan_ref, release_ref = lifecycle
    def timeout(*args, **kwargs): raise subprocess.TimeoutExpired('owned episode', 1800)
    seen = []
    def cleanup(process, identity):
        seen.append(identity); process.returncode = -9
    monkeypatch.setattr(r, 'wait_exclusively', timeout)
    monkeypatch.setattr(adapter, 'cleanup_owned', cleanup)
    result = adapter.execute_one(plan_ref, release_ref)
    assert result['status'] == 'INVALID_STOP' and seen == [{'pid': 90001, 'proc_start_ticks': '123', 'boot_id': 'synthetic-boot'}]
    assert result['terminal']['gpu_process_wall_seconds'] > 0


@pytest.mark.parametrize('kind', ['file', 'symlink', 'dangling_symlink'])
def test_stop_before_dispatch_no_device_probe(lifecycle, monkeypatch, kind):
    root, plan, plan_ref, release_ref = lifecycle
    stop = root.parent / 'autonomy_20261004/STOP'
    assert plan['stop_path'] == str(stop)
    stop.parent.mkdir(exist_ok=True)
    if kind == 'file':
        stop.touch()
    else:
        target = root / 'stop-target'
        if kind == 'symlink': target.touch()
        stop.symlink_to(target)
    monkeypatch.setattr(adapter, 'device_check', lambda: pytest.fail('STOP must precede device probe'))
    monkeypatch.setattr(adapter.subprocess, 'Popen', lambda *a, **kw: pytest.fail('STOP must prevent dispatch'))
    with pytest.raises(ValueError, match='STOP'): adapter.execute_one(plan_ref, release_ref)
    assert r.read_events(root / 'data/attempt-ledger.jsonl') == old_invalid()


def test_explicit_caps_do_not_inherit_old_private_budget():
    caps={'attempts':393,'gpu_hours':100.,'buckets':{'baseline':28,'development':125,'validation':180,'formal':40,'recovery':20},
          'protected_gpu_hours':{'validation':32.,'formal':12.}}
    with pytest.raises(ValueError, match='unchanged root caps'): release.validate_caps(caps)
    release.validate_caps(copy.deepcopy(c.CAPS))
    caps['buckets']['formal']=39;caps['attempts']-=1
    with pytest.raises(ValueError,match='protected'):release.validate_caps(caps)
