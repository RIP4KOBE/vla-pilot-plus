"""Synthetic CPU fixtures only; never uses owning state, GPU or a provider."""
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml
from scripts import qd_ed_final_runner as r, qd_ed_n23_worker as w
from scripts import qd_ed_n32_contract as c, qd_ed_n32_release as release
from scripts import qd_ed_n32_runner as adapter, qd_ed_n32_supervise as supervisor
from test_n32_release import write, journal, draft, trusted

NOW = dt.datetime(2026, 10, 4, tzinfo=dt.timezone.utc)
CAPS = {'attempts': 1800, 'gpu_hours': 224., 'buckets': {'baseline': 400, 'development': 1120, 'validation': 180, 'formal': 40, 'recovery': 60}, 'protected_gpu_hours': {'validation': 32., 'formal': 12.}}


def budget_fixture(tmp_path, events=(), resources=()):
    authority = {'caps': copy.deepcopy(CAPS), 'amendment': {'synthetic': True}, 'starts_at': '2026-10-01T00:00:00Z',
                 'coordinator_ends_at': release.COORDINATOR_END,
                 'weekly_window': {'origin_gpu_hours': 53.08404692669838, 'increment_gpu_hours': 168., 'ends_at': c.DEADLINE}}
    reference = write(tmp_path / 'authority.json', authority)
    plan = {'authority': reference, 'stop_path': str(tmp_path / 'STOP')}
    snap = r.budget_snapshot(events, resources)
    state = {'gpu_pool': [7], 'max_concurrent_gpu_workers': 1, 'n32_budget_authority': reference,
             'resource_isolation': {'status': 'ACTIVE', 'validation_status': 'PASS', 'private_budget': True},
             'budget': {**snap, 'max_episode_attempts': 1800, 'max_gpu_hours': 224., 'reserved': copy.deepcopy(CAPS['buckets']),
                        'gpu_hour_reservations': copy.deepcopy(CAPS['protected_gpu_hours']), 'amendment': authority['amendment']}}
    reservations = [{'event': 'gpu_hour_reservations_changed', 'gpu_hour_reservations': CAPS['protected_gpu_hours'], 'rationale': 'synthetic fixture only', 'time_unix': 1}]
    return plan, authority, state, reservations


def historical(seconds=3600., bucket='development', attempt='old', cohort='HISTORY', end='valid'):
    base = {'attempt_id': attempt, 'identity': {'iteration': cohort}, 'budget_bucket': bucket, 'episode_key': attempt}
    return [{**base, 'event': 'reserved'}, {**base, 'event': 'dispatched'},
            {**base, 'event': end, 'gpu_process_wall_seconds': seconds, 'outcome_valid': False}]


def health(seconds=360., cohort='HISTORY'):
    return [{'resource_id': 'probe', 'event': kind, 'cohort': cohort, 'gpu_process_wall_seconds': seconds}
            for kind in ('reserved', 'dispatched', 'completed')]


def admit(tmp_path, events=(), resources=(), change=None):
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
    assert snap['dispatched'] == 2 and snap['aborted'] == 1


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
        events = [e for i in range(400) for e in historical(0., 'baseline', f'h{i}')]
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
        if kind == 'deadline': authority['starts_at'] = '2026-10-05T00:00:00Z'
    with pytest.raises((r.GateError, ValueError)):
        admit(tmp_path, events, change=change)


@pytest.mark.parametrize('seconds,allowed', [(1840.01, True), (1839.99, False)])
def test_full_episode_weekly_and_protected_seconds(tmp_path, seconds, allowed):
    events = historical((53.08404692669838 + 168 - 44) * 3600 - seconds)
    if allowed:
        admit(tmp_path, events)
    else:
        with pytest.raises(ValueError): admit(tmp_path, events)


def test_null_retries_allowed_nonnull_forbidden_and_deterministic_ids():
    rows = c.expected_rows(); plan = {'episodes': rows, 'worktree': str(c.ROOT)}
    events = journal(rows[:1], (0,))
    for event in events: event.update(retry_of=None, recovery_of=None)
    assert supervisor.reconcile(plan, events, lambda *a: None)['next_row'] == rows[1]
    for key, value in [('retry_of', ''), ('recovery_of', 'prior'), ('attempt_id', 'random-suffix')]:
        bad = copy.deepcopy(events); bad[0][key] = value
        with pytest.raises(ValueError): supervisor.reconcile(plan, bad, lambda *a: None)


def test_prefix_append_allowed_rewrite_rejected(tmp_path):
    path = tmp_path / 'ledger'; path.write_bytes(b'old\n')
    anchor = adapter.journal_prefix(path)
    path.write_bytes(b'old\nnew\n'); release.prefix(path, anchor)
    path.write_bytes(b'bad\nnew\n')
    with pytest.raises(ValueError): release.prefix(path, anchor)


@pytest.fixture
def lifecycle(tmp_path, monkeypatch):
    tmp_path = tmp_path / 'study_worktree'
    tmp_path.mkdir()
    rows = c.expected_rows()
    monkeypatch.setattr(c, 'expected_rows', lambda root=None: rows)
    plan, authority, state, reservations = budget_fixture(tmp_path)
    plan['stop_path'] = c.stop_path(tmp_path)
    Path(plan['stop_path']).parent.mkdir()
    plan.update(worktree=str(tmp_path), artifact_root=str(tmp_path / 'artifacts/n32'), episodes=rows,
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
        write(output / 'eds_eval/n32-worker-receipt.json', {'synthetic_only': True})
        process.returncode = 0
        return 0
    monkeypatch.setattr(r, 'wait_exclusively', wait)
    return tmp_path, plan, plan_ref, release_ref


def test_reserve_dispatch_terminal_and_resume_next(lifecycle):
    root, plan, plan_ref, release_ref = lifecycle
    first = adapter.execute_one(plan_ref, release_ref)
    assert first['status'] == 'VALID'
    events = r.read_events(root / 'data/attempt-ledger.jsonl')
    assert [e['event'] for e in events] == ['reserved', 'dispatched', 'valid']
    assert all(e['attempt_id'] == plan['episodes'][0]['episode_key'] for e in events)
    before = copy.deepcopy(events)
    assert adapter.execute_one(plan_ref, release_ref)['status'] == 'VALID'
    assert r.read_events(root / 'data/attempt-ledger.jsonl')[:3] == before
    assert r.read_state(root / 'research-state.yaml')['budget']['dispatched'] == 2
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
    assert len(r.read_events(root / 'data/attempt-ledger.jsonl')) == 3


def test_live_unknown_never_signalled_or_restarted(lifecycle, monkeypatch):
    root, plan, plan_ref, release_ref = lifecycle
    def unknown(*args, **kwargs): raise KeyboardInterrupt('synthetic controller interruption')
    monkeypatch.setattr(r, 'wait_exclusively', unknown)
    monkeypatch.setattr(adapter, 'cleanup_owned', lambda *a: pytest.fail('must not signal unknown/live episode'))
    with pytest.raises(KeyboardInterrupt): adapter.execute_one(plan_ref, release_ref)
    Path(plan['stop_path']).touch()
    assert adapter.execute_one(plan_ref, release_ref)['status'] == 'LIVE_OR_UNSETTLED'
    assert [e['event'] for e in r.read_events(root / 'data/attempt-ledger.jsonl')] == ['reserved', 'dispatched']


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
    assert r.read_events(root / 'data/attempt-ledger.jsonl') == []


@pytest.fixture
def release_chain(trusted, tmp_path, monkeypatch):
    """Test only root document validation; dependency gates are spied separately."""
    plan, runtime, _ = copy.deepcopy(trusted)
    plan.update(schema='n32-released-plan-v1', frozen=True, release_enabled=True, attempt_identity='episode_key',
                phase_authorization={'dev': True, 'validation': False, 'formal': False})
    plan.pop('root_review'); plan.pop('execution_release')
    runtime.update(schema='qd-ed-runtime-setup-v1', worktree=plan['worktree'], artifact_root=str(tmp_path),
                   cuda_egl_verified=True, provider_ready=True)
    plan['artifact_root'] = str(tmp_path / 'prospective-artifacts')
    for task in runtime['tasks'].values():
        cache = tmp_path / ('cache' + str(task['task_id'])); cache.mkdir()
        cache_file = cache / 'metadata.json'; cache_file.write_text('{}')
        task['cache_dir'] = str(cache)
        runtime['files'].append(c.ref(cache_file))
    plan['runtime'] = write(tmp_path / 'runtime.json', runtime)
    protocol = {'schema': 'n32-production-protocol-v1', 'cohort': c.COHORT, 'episodes': plan['episodes'],
                'limits': c.LIMITS, 'worker_contract': c.WORKER_CONTRACT, 'attempt_identity': 'episode_key', 'deadline': c.DEADLINE,
                'promotion': {'all_valid_cells': 30, 'n32_min_successes': 5, 'matched_controls_required': True},
                'futility': 'complete_valid_triples_only', 'validation_authorized': False, 'formal_authorized': False}
    plan['protocol'] = write(tmp_path / 'protocol.json', protocol)
    _, authority, _, _ = budget_fixture(tmp_path)
    authority.update(schema='n32-budget-authority-v1', approved=True, cohort=c.COHORT, limits=c.LIMITS,
                     validation_authorized=False, formal_authorized=False,
                     approval_basis=write(tmp_path / 'approval.json', {'synthetic_only': True}))
    plan['authority'] = write(tmp_path / 'authority.json', authority)
    plan_ref = write(tmp_path / 'plan.json', plan)
    expected = {'schema': 'n32-execution-release-v1', 'approved': True, 'plan': plan_ref,
                'authority': plan['authority'], 'protocol': plan['protocol'], 'source': plan['source'],
                'runtime': plan['runtime'], 'limits': c.LIMITS, 'phase_authorization': plan['phase_authorization']}
    review = write(tmp_path / 'review.json', {**expected, 'schema': 'n32-root-production-review-v1', 'decision': 'APPROVED'})
    released = {**expected, 'root_review': review}
    release_ref = write(tmp_path / 'release.json', released)
    seen = []
    monkeypatch.setattr(r, 'verify_files', lambda *args, **kwargs: seen.append('files'))
    monkeypatch.setattr(r, 'validate_runtime_inputs', lambda *args: seen.append('generic-runtime'))
    def check(reference, p, runtime, row):
        assert reference == p['expected_manifests'][row['episode_key']]
        seen.append(row['episode_key'])
    monkeypatch.setattr(release.b, 'verify_manifest', check)
    return plan, plan_ref, release_ref, seen


def test_detached_release_dag_all30_and_generic_gates(release_chain):
    plan, plan_ref, release_ref, seen = release_chain
    assert release.validate_release(plan_ref, release_ref)[0] == plan
    assert seen == ['files', 'generic-runtime'] + [row['episode_key'] for row in plan['episodes']]
    assert 'root_review' not in plan and 'execution_release' not in plan
    assert w.read_ref(w.read_ref(release_ref)['root_review'])['plan'] == plan_ref


@pytest.mark.parametrize('fault', ['release_hash', 'plan_bytes', 'review_bytes', 'protocol_bytes', 'authority_bytes', 'approval_bytes',
                                    'source', 'runtime_bytes', 'schema', 'draft', 'identity', 'manifest_coverage', 'runtime_checkout',
                                    'disabled', 'phase', 'review_plan', 'cache_missing', 'generic_runtime', 'manifest_tamper'])
def test_release_boundary_tamper(release_chain, monkeypatch, fault):
    plan, plan_ref, release_ref, seen = release_chain
    released = w.read_ref(release_ref)
    if fault == 'release_hash': release_ref['sha256'] = '0'*64
    elif fault.endswith('_bytes'):
        reference = {'plan_bytes': plan_ref, 'review_bytes': released['root_review'], 'protocol_bytes': plan['protocol'],
                     'authority_bytes': plan['authority'], 'approval_bytes': w.read_ref(plan['authority'])['approval_basis'],
                     'runtime_bytes': plan['runtime']}[fault]
        Path(reference['path']).write_text('{}')
    elif fault in ('schema', 'draft', 'identity', 'manifest_coverage', 'phase'):
        if fault == 'schema': plan['schema'] = 'other'
        if fault == 'draft': plan['frozen'] = False
        if fault == 'identity': plan['attempt_identity'] = 'random-suffix'
        if fault == 'manifest_coverage': plan['expected_manifests'].pop(next(iter(plan['expected_manifests'])))
        if fault == 'phase': plan['phase_authorization']['validation'] = True
        with pytest.raises(ValueError): release.validate_plan(plan)
        return
    elif fault == 'disabled':
        released['approved'] = False; release_ref = write(Path(release_ref['path']), released)
    elif fault == 'review_plan':
        review = w.read_ref(released['root_review']); review['plan'] = plan['runtime']
        released['root_review'] = write(Path(released['root_review']['path']), review)
        release_ref = write(Path(release_ref['path']), released)
    elif fault == 'cache_missing':
        runtime = w.read_ref(plan['runtime'])
        Path(next(iter(runtime['tasks'].values()))['cache_dir'], 'metadata.json').unlink()
    elif fault == 'runtime_checkout':
        # Hash-rebound runtime still cannot name an adjacent checkout.
        real_read = w.read_ref
        def read(reference):
            data = real_read(reference)
            if reference == plan['runtime']: data['worktree'] = '/synthetic/foreign'
            return data
        monkeypatch.setattr(w, 'read_ref', read)
    else:
        def fail(*args, **kwargs): raise ValueError('synthetic trust gate rejected')
        if fault == 'source': monkeypatch.setattr(w, 'verify_source', fail)
        if fault == 'generic_runtime': monkeypatch.setattr(r, 'validate_runtime_inputs', fail)
        if fault == 'manifest_tamper': monkeypatch.setattr(release.b, 'verify_manifest', fail)
    with pytest.raises((ValueError, r.GateError, FileNotFoundError)):
        release.validate_release(plan_ref, release_ref)


def test_real_cpu_child_cleanup_identity_guard(tmp_path):
    # Only our new, CPU sleeping subprocess; no shell/group/foreign signalling.
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], cwd=tmp_path)
    identity = adapter.process_identity(child.pid)
    try:
        with pytest.raises(ValueError, match='identity changed'):
            adapter.cleanup_owned(child, {**identity, 'proc_start_ticks': 'wrong'})
        assert child.poll() is None
        adapter.cleanup_owned(child, identity)
        assert child.poll() is not None
    finally:
        if child.poll() is None:
            child.terminate(); child.wait(timeout=5)


def test_monitor_timeout_not_success_or_immediate_signal(lifecycle, monkeypatch):
    root, plan, plan_ref, release_ref = lifecycle
    def unknown(*args, **kwargs): raise subprocess.TimeoutExpired(['nvidia-smi'], 15)
    monkeypatch.setattr(r, 'wait_exclusively', unknown)
    monkeypatch.setattr(adapter, 'cleanup_owned', lambda *a: pytest.fail('monitor failure alone cannot signal'))
    result = adapter.execute_one(plan_ref, release_ref)
    assert result['status'] == 'INVALID_STOP' and result['terminal']['success'] is None
    assert result['terminal']['gpu_process_wall_seconds'] > 0


def test_orphan_future_output_blocks_dispatch(lifecycle, monkeypatch):
    root, plan, plan_ref, release_ref = lifecycle
    output = Path(w.read_ref(plan['expected_manifests'][plan['episodes'][15]['episode_key']])['output_dir'])
    output.mkdir(parents=True)
    monkeypatch.setattr(adapter, 'device_check', lambda: pytest.fail('orphan must block probe/dispatch'))
    assert adapter.execute_one(plan_ref, release_ref)['status'] == 'LIVE_OR_UNSETTLED'
    assert r.read_events(root / 'data/attempt-ledger.jsonl') == []


def test_live_completed_process_never_restarted(lifecycle, monkeypatch):
    root, plan, plan_ref, release_ref = lifecycle
    assert adapter.execute_one(plan_ref, release_ref)['status'] == 'VALID'
    monkeypatch.setattr(adapter, 'process_identity', lambda pid: {'pid': pid, 'boot_id': 'synthetic-boot', 'proc_start_ticks': '123'})
    assert adapter.execute_one(plan_ref, release_ref)['status'] == 'LIVE_OR_UNSETTLED'
    assert len(r.read_events(root / 'data/attempt-ledger.jsonl')) == 3


@pytest.mark.parametrize('key', ['attempt_id', 'identity', 'episode_key', 'budget_bucket', 'plan_sha256', 'release', 'source_commit',
                                'runtime_manifest_sha256', 'runtime_inventory_sha256', 'init_row_sha256', 'output_dir', 'physical_gpu',
                                'ledger_prefix', 'context'])
def test_each_lifecycle_binding_immutable(lifecycle, key):
    root, plan, plan_ref, release_ref = lifecycle
    assert adapter.execute_one(plan_ref, release_ref)['status'] == 'VALID'
    events = r.read_events(root / 'data/attempt-ledger.jsonl')
    plan['schema'] = 'n32-released-plan-v1'
    events[1][key] = 'tampered'
    with pytest.raises((ValueError, TypeError, AttributeError)):
        supervisor.reconcile(plan, events, lambda *a: None)


@pytest.mark.parametrize('fault', ['none', 'terminal_release', 'terminal_context', 'terminal_inventory', 'process_release', 'process_context',
                                    'terminal_attempt', 'context_attempt', 'context_manifest', 'context_argv', 'context_release', 'output'])
def test_released_worker_terminal_bindings(tmp_path, monkeypatch, fault):
    worker = adapter.worker
    row = c.expected_rows()[2]
    output = tmp_path / 'artifacts' / row['episode_key']
    runtime = {'gpu_mapping': {'physical_gpu': 7, 'uuid': c.GPU_UUID}}
    runtime_ref = write(tmp_path / 'runtime.json', runtime)
    manifest = {'row': row, 'output_dir': str(output), 'argv': [sys.executable, 'main.py'], 'expected_runtime': {}}
    manifest_ref = write(tmp_path / 'manifest.json', manifest)
    plan = {'source': {'commit': 'a'*40}, 'episodes': [row], 'expected_manifests': {row['episode_key']: manifest_ref},
            'runtime': runtime_ref, 'worktree': str(tmp_path), 'runtime_inventory_sha256': 'c'*64}
    plan_ref = write(tmp_path / 'plan.json', plan)
    release_ref = write(tmp_path / 'release.json', {'synthetic_only': True})
    context = worker.context_for(plan_ref, row, release_ref)
    context_path = output / 'n32-worker-context.json'
    context_ref = write(context_path, context)
    process = {'pid': 123, 'proc_start_ticks': '456', 'boot_id': 'synthetic', 'attempt_id': row['episode_key'],
               'context': context_ref, 'release': release_ref}
    process_path = output / 'process.json'; write(process_path, process)
    terminal = {'identity': supervisor.c_identity(row), 'episode_key': row['episode_key'], 'attempt_id': row['episode_key'],
                'source_commit': 'a'*40, 'plan_sha256': plan_ref['sha256'], 'runtime_manifest_sha256': runtime_ref['sha256'],
                'runtime_inventory_sha256': 'c'*64, 'init_row_sha256': row['init_row_sha256'], 'physical_gpu': 7,
                'output_dir': str(output), 'outcome_valid': True, 'required_cost_telemetry_complete': True,
                'success': False, 'gpu_process_wall_seconds': 2., 'guided_chunks': 1, 'context': context_ref,
                'release': release_ref, 'n32_worker_receipt': {}}
    def validate(p, rel):
        assert p == plan_ref
        w.require(rel == release_ref, 'unexpected root release')
        return plan, runtime, {}
    monkeypatch.setattr(release, 'validate_release', validate)
    monkeypatch.setattr(worker.b, 'verify_manifest', lambda *a: manifest)
    monkeypatch.setattr(worker.b, 'profiles', lambda *a: {'profiles': {'N32': {}}})
    monkeypatch.setattr(worker, 'native_counts', lambda *a: ({}, {}))
    monkeypatch.setattr(r, 'validate_result', lambda *a: {'success': False, 'required_cost_telemetry_complete': True})
    def receipt(context_ref, receipt_ref, record):
        worker.validate_context(context_ref)
        return {'accepted': True}
    monkeypatch.setattr(worker, 'verify_receipt', receipt)
    if fault.startswith('terminal_'):
        terminal[{'terminal_release': 'release', 'terminal_context': 'context', 'terminal_inventory': 'runtime_inventory_sha256', 'terminal_attempt': 'attempt_id'}[fault]] = 'tampered'
    elif fault.startswith('process_'):
        process[fault.removeprefix('process_')] = 'tampered'; write(process_path, process)
    elif fault.startswith('context_'):
        context[{'context_attempt': 'attempt_id', 'context_manifest': 'expected_manifest', 'context_argv': 'main_argv', 'context_release': 'release'}[fault]] = 'tampered'
        # Rebind lower-layer hashes to show semantic checks still fail closed.
        context_ref = write(context_path, context); terminal['context'] = context_ref
        process['context'] = context_ref; write(process_path, process)
    elif fault == 'output': terminal['output_dir'] = str(tmp_path / 'foreign')
    if fault == 'none':
        assert worker.verify_terminal(plan_ref, row, terminal, release_ref)['accepted']
    else:
        with pytest.raises((ValueError, TypeError, KeyError)):
            worker.verify_terminal(plan_ref, row, terminal, release_ref)


def test_accounted_probe_required_before_reservation(lifecycle, monkeypatch):
    root, plan, plan_ref, release_ref = lifecycle
    def missing(*args): raise ValueError('missing accounted CUDA/EGL proof')
    monkeypatch.setattr(adapter, 'check_probe', missing)
    with pytest.raises(ValueError, match='proof'): adapter.execute_one(plan_ref, release_ref)
    assert r.read_events(root / 'data/attempt-ledger.jsonl') == []


def test_local_health_charge_counts_toward_cohort_ceiling(tmp_path):
    events = historical(16000., cohort=c.COHORT)
    resources = [{**e, 'kind': 'n32_resource_preparation_v1'} for e in health(161.)]
    with pytest.raises(ValueError, match='cohort_seconds_remaining'):
        admit(tmp_path, events, resources)
    resources = [{**e, 'kind': 'n32_resource_preparation_v1'} for e in health(159.)]
    admit(tmp_path, events, resources)


def test_monitor_query_is_capped_at_remaining_episode_time(monkeypatch):
    seen = []
    monkeypatch.setattr(adapter.time, 'monotonic', lambda: 1899.75)
    def query(command, **kwargs):
        seen.append(kwargs['timeout'])
        return subprocess.CompletedProcess(command, 0, stdout='')
    monkeypatch.setattr(adapter.subprocess, 'run', query)
    def wait(process, timeout, *, physical_gpu, monitor):
        assert timeout == .25
        monitor(process, .25)
        return 0
    monkeypatch.setattr(r, 'wait_exclusively', wait)
    assert adapter.wait_worker(object(), 100., {}) == 0
    assert seen == [.25]


@pytest.mark.parametrize('fault', ['none', 'missing', 'pid', 'proc_start_ticks', 'boot_id', 'attempt_id', 'context', 'release'])
def test_child_requires_parent_dispatch_record_before_main(tmp_path, fault):
    context_ref = write(tmp_path / 'context.json', {'synthetic_only': True})
    release_ref = write(tmp_path / 'release.json', {'synthetic_only': True})
    context = {'attempt_id': 'episode-key', 'release': release_ref}
    identity = {'pid': 123, 'proc_start_ticks': '456', 'boot_id': 'synthetic'}
    record = {**identity, 'attempt_id': context['attempt_id'], 'context': context_ref, 'release': release_ref}
    if fault not in ('none', 'missing'): record[fault] = 'tampered'
    if fault != 'missing': write(tmp_path / 'process.json', record)
    if fault == 'none':
        adapter.worker.verify_dispatch_record(context_ref, context, tmp_path, identity)
    else:
        with pytest.raises((ValueError, FileNotFoundError)):
            adapter.worker.verify_dispatch_record(context_ref, context, tmp_path, identity)


@pytest.mark.parametrize('fault', ['missing', 'malformed', 'different'])
def test_resume_requires_matching_terminal_artifact(lifecycle, fault):
    root, plan, plan_ref, release_ref = lifecycle
    terminal = adapter.execute_one(plan_ref, release_ref)['terminal']
    path = Path(terminal['output_dir']) / 'attempt-result.json'
    if fault == 'missing': path.unlink()
    if fault == 'malformed': path.write_text('{')
    if fault == 'different': write(path, {**terminal, 'success': not terminal['success']})
    result = adapter.execute_one(plan_ref, release_ref)
    assert result['status'] == 'INVALID_STOP'
    assert len(r.read_events(root / 'data/attempt-ledger.jsonl')) == 3
    assert r.read_state(root / 'research-state.yaml')['budget']['gpu_hours_consumed'] > 0
