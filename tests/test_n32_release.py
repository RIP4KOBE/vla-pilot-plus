"""Bounded synthetic release plumbing. No provider/model/simulator/GPU execution."""
import copy
import datetime as dt
import json
from pathlib import Path

import pytest
from scripts import qd_ed_n32_bridge as b, qd_ed_n32_contract as c
from scripts import qd_ed_n32_prepare as prepare, qd_ed_n32_supervise as supervisor
from scripts import qd_ed_n32_report as reporting, qd_ed_n23_worker as w


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return c.ref(path)


@pytest.fixture(scope='module')
def draft(tmp_path_factory):
    tmp = tmp_path_factory.mktemp('n32-draft')
    provider = {'backend': 'codex_cli', 'model': 'gpt-6-astra', 'auth_mode': 'chatgpt', 'reasoning_effort': 'low',
                'timeout_seconds': 180, 'cli_path': str(tmp / 'codex'), 'cli_version': '0.155.1',
                'cli_sha256': 'a' * 64, 'disabled_skill_paths': [str(tmp / 'inactive')], 'allow_recovered_error_events': True}
    provider['public_config_sha256'] = b.runner.codex_public_config_sha256(provider)
    runtime = {'tasks': {str(t): {'cache_dir': str(tmp / f'cache{t}')} for t in range(10)},
               'main_overrides': ['+main.require_task_cache_identity=true'],
               'frozen_stage_provider': provider, 'stage_engineering_condition': b.runner.n4e1_support().engineering_condition(),
               'stage_recovered_error_condition': b.runner.E2_STAGE_CONDITION,
               'gpu_mapping': {'physical_gpu': 7, 'uuid': c.GPU_UUID, 'egl_device_index': 4}}
    runtime['files'] = []
    for row in c.expected_rows()[::3]:
        task = runtime['tasks'][str(row['task_id'])]
        task.update(task_id=row['task_id'], init_index=row['init_index'],
                    init_path=str(tmp / f"init{row['task_id']}"), bddl_path=str(tmp / f"task{row['task_id']}.bddl"))
        runtime['files'].extend([{'path': task['init_path'], 'sha256': row['init_file_sha256']},
                                 {'path': task['bddl_path'], 'sha256': row['bddl_sha256']}])
    runtime_ref = write(tmp / 'runtime.json', runtime)
    files = [{'path': path, 'sha256': w.sha(b.ROOT / path)} for path in sorted(b.source_paths())]
    source = {'commit': 'a' * 40, 'files': files, 'sha256': w.canonical_sha(files)}
    with pytest.MonkeyPatch.context() as m:
        m.setattr(w, 'source_record', lambda *args: source)
        plan = prepare.prepare(tmp / 'draft', runtime_ref)
    return plan, runtime, c.ref(tmp / 'draft/plan.draft.json')


@pytest.fixture
def trusted(monkeypatch, draft):
    # Synthetic checkout only. Separate temporary-Git tests exercise source_record.
    monkeypatch.setattr(w, 'verify_source', lambda *args: None)
    return draft


def journal(rows, successes=()):
    return [dict(event=kind, identity=supervisor.c_identity(row), episode_key=row['episode_key'],
                 attempt_id=row['episode_key'], outcome_valid=True, required_cost_telemetry_complete=True,
                 success=i in successes) for i, row in enumerate(rows) for kind in ('reserved', 'dispatched', 'valid')]


def test_matrix_and_immutable_draft(draft):
    plan, runtime, _ = draft
    assert [(r['task_id'], r['profile']) for r in plan['episodes']] == [(t, a) for t in range(10) for a in c.ARMS]
    assert len(plan['expected_manifests']) == 30
    original = json.loads((b.ROOT / 'configs/qd_ed_final/n31_dev_task_identities.json').read_text())['tasks']
    for i, task in enumerate(original):
        assert all(all(row[k] == v for k, v in task.items()) for row in plan['episodes'][3*i:3*i+3])
    c.validate_draft(plan)
    with pytest.raises(ValueError, match='draft only'):
        supervisor.launch()
    with pytest.raises(ValueError, match='already exists'):
        prepare.prepare(Path(plan['artifact_root']).parent, plan['runtime'])


def test_exact_config_and_unchanged_controls(trusted):
    plan, runtime, _ = trusted
    before = json.loads((b.ROOT / 'configs/qd_ed_final/n4_observed_baseline_profiles.json').read_text())
    profiles = b.profiles()
    for arm in ('C0', 'Q0'):
        assert profiles['profiles'][arm] == before['profiles'][arm]
    for row in plan['episodes'][:3]:
        manifest = b.verify_manifest(plan['expected_manifests'][row['episode_key']], plan, runtime, row)
        config, resolved = b.compose_launch(manifest['argv'])
        assert json.loads(json.dumps(resolved)) == manifest['resolved_config']
        assert config['backend']['libero']['max_episode_steps'] == 720
        assert config['seed'] == row['policy_seed']
        assert config['backend']['libero']['task_ids_filter'] == [row['task_id']]
        for value in ('backend=codex_cli', 'model=gpt-6-astra', 'reasoning_effort=low', 'timeout_seconds=180'):
            assert 'perception.gemini.' + value in manifest['argv']
        assert resolved['capture_dwell_proposal_mode'] == 'off'
        assert resolved['executed_progress_continuation_mode'] == 'off'
        assert resolved['archive_eligible_capture_mode'] == (b.MODE if row['profile'] == 'N32' else 'off')
        if row['profile'] == 'N32':
            import hashlib
            assert manifest['expected_runtime']['config_sha256'] == hashlib.sha256(json.dumps(resolved, sort_keys=True, allow_nan=False).encode()).hexdigest()
            assert manifest['expected_runtime']['binding'] == {'task_id': 0, 'run_id': row['episode_key'], 'source_commit': 'a'*40}
    paths = b.source_paths()
    assert {'scripts/qd_ed_n32_worker.py', 'scripts/qd_ed_n32_supervise.py', 'scripts/qd_ed_n31_native.py',
            'core/qd_archive_eligible_runtime.py', 'main.py', 'configs/config.yaml'} <= paths


@pytest.mark.parametrize('fault', ['manifest', 'missing', 'config', 'row', 'source', 'runtime', 'command'])
def test_external_tamper(trusted, tmp_path, fault):
    plan, runtime, _ = copy.deepcopy(trusted)
    row = plan['episodes'][2]
    reference = plan['expected_manifests'][row['episode_key']]
    actual = w.read_ref(reference)
    if fault == 'missing':
        reference = {'path': str(tmp_path / 'missing'), 'sha256': 'a'*64}
    elif fault == 'manifest':
        reference = {**reference, 'sha256': 'b'*64}
    else:
        if fault == 'config': actual['resolved_config']['cem_iters'] = 9
        if fault == 'row': actual['row']['task_id'] = 1
        if fault == 'source': actual['source']['commit'] = 'b'*40
        if fault == 'runtime': runtime['tasks']['0']['cache_dir'] += 'changed'
        if fault == 'command': actual['argv'].append('seed=123')
        reference = write(tmp_path / 'tampered.json', actual)
    with pytest.raises((ValueError, KeyError)):
        b.verify_manifest(reference, plan, runtime, row)


@pytest.mark.parametrize('count,status', [(0, 'READY_FOR_ROOT_RELEASE'), (17, 'READY_FOR_ROOT_RELEASE'), (18, 'NUMERIC_FUTILITY')])
def test_complete_triple_futility(draft, count, status):
    plan, _, _ = draft
    result = supervisor.reconcile(plan, journal(plan['episodes'][:count]), lambda *args: None)
    assert result['status'] == status
    report = reporting.summary(result, [])
    assert report['matrix'][9]['N32'] == 'Unknown'
    assert report['http_counters'] == 'Unknown' and report['validation_authorized'] is False


@pytest.mark.parametrize('fault', ['invalid', 'receipt', 'duplicate', 'reorder', 'replay', 'retry', 'live', 'foreign_live'])
def test_reconciliation_stops(trusted, fault):
    plan, _, _ = trusted
    events = journal(plan['episodes'][:2])
    verify = lambda *args: None
    live = []
    if fault == 'invalid': events[-1]['outcome_valid'] = False
    if fault == 'receipt':
        def verify(*args): raise ValueError('receipt differs')
    if fault == 'duplicate': events += events[3:]
    if fault == 'reorder': events = events[3:] + events[:3]
    if fault == 'replay': events += events[:3]
    if fault == 'retry': events[0]['retry_of'] = 'old'
    if fault == 'live': events.pop()
    if fault == 'foreign_live': live = ['pending']
    if fault in {'reorder', 'replay', 'retry'}:
        with pytest.raises(ValueError): supervisor.reconcile(plan, events, verify)
    else:
        result = supervisor.reconcile(plan, events, verify, live_handles=live)
        assert result['next_row'] is None
        assert result['status'] == ('INVALID_STOP' if fault in {'invalid', 'receipt', 'duplicate'} else 'LIVE_OR_UNSETTLED')
        if fault == 'invalid': assert result['charged_events'] == events


def allowance():
    return {'authority_starts_at': '2026-10-04T00:00:00Z', 'authority_ends_at': c.DEADLINE,
            'private_budget': True, 'gpu_idle': True, 'physical_gpu': 7, 'gpu_uuid': c.GPU_UUID,
            'live_handles': [], 'unsettled_reservations': 0, 'global_seconds_remaining': 1000000,
            'private_seconds_remaining': 20000, 'cohort_seconds_remaining': 18000,
            'protected_seconds_remaining': 44*3600, 'bucket_attempts_remaining': {'baseline': 10, 'development': 20},
            'global_attempts_remaining': 200, 'cohort_attempts_remaining': 30, 'protected_attempts_remaining': 100}


@pytest.mark.parametrize('fault', ['none', 'stop', 'deadline', 'authority', 'nan', 'private', 'global', 'cohort', 'protected', 'bucket', 'attempt', 'reserve_attempt', 'device', 'live', 'reservation'])
def test_finite_admission(draft, tmp_path, fault):
    plan, _, _ = draft
    a = allowance()
    now = dt.datetime(2026, 10, 4, 16, tzinfo=dt.timezone.utc)
    stop = tmp_path / 'autonomy_20261004/STOP'
    if fault == 'stop': stop.parent.mkdir(); stop.touch()
    if fault == 'deadline': now = dt.datetime(2026, 10, 10, 17, 12, tzinfo=dt.timezone.utc)
    if fault == 'authority': a['authority_ends_at'] = '2026-10-04T16:00:30Z'
    if fault == 'nan': a['global_seconds_remaining'] = float('nan')
    if fault == 'private': a['private_seconds_remaining'] = 1839
    if fault == 'global': a['global_seconds_remaining'] = 1839
    if fault == 'cohort': a['cohort_seconds_remaining'] = 1839
    if fault == 'protected': a['global_seconds_remaining'] = a['protected_seconds_remaining'] + 1839
    if fault == 'bucket': a['bucket_attempts_remaining']['baseline'] = 0
    if fault == 'attempt': a['cohort_attempts_remaining'] = 0
    if fault == 'reserve_attempt': a['global_attempts_remaining'] = 100
    if fault == 'device': a['physical_gpu'] = 6
    if fault == 'live': a['live_handles'] = ['pid']
    if fault == 'reservation': a['unsettled_reservations'] = 1
    if fault == 'none': assert c.pre_dispatch(plan['episodes'][0], a, now=now, stop_path=stop) == 1840
    else:
        with pytest.raises(ValueError): c.pre_dispatch(plan['episodes'][0], a, now=now, stop_path=stop)


def test_source_requires_committed_bytes(tmp_path, monkeypatch):
    import subprocess
    monkeypatch.setattr(w, 'REQUIRED_SOURCE', {'file.py'})
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    (tmp_path / 'file.py').write_text('VALUE = 1\n')
    subprocess.run(['git', '-C', str(tmp_path), 'add', 'file.py'], check=True)
    subprocess.run(['git', '-C', str(tmp_path), '-c', 'user.name=CPU Test', '-c', 'user.email=cpu@example.invalid', 'commit', '-qm', 'fixture'], check=True)
    source = w.source_record(tmp_path, {'file.py'})
    w.verify_source(tmp_path, source)
    (tmp_path / 'file.py').write_text('VALUE = 2\n')
    with pytest.raises(ValueError, match='uncommitted'): w.verify_source(tmp_path, source)


def test_loaded_checkout_rejection(draft, monkeypatch, tmp_path):
    import sys
    from types import SimpleNamespace
    plan, _, _ = draft
    monkeypatch.setitem(sys.modules, 'scripts.foreign', SimpleNamespace(__file__=str(tmp_path / 'foreign.py')))
    with pytest.raises(ValueError, match='adjacent checkout'): b.attest_loaded(b.ROOT, plan['source'])


def test_full_matrix_gate_only_and_controls(draft):
    plan, _, _ = draft
    for candidate, control, gate in ((5, 4, True), (5, 6, False), (10, 10, True)):
        wins = [3*t+2 for t in range(candidate)] + [3*t for t in range(control)]
        events = journal(plan['episodes'], wins)
        result = supervisor.reconcile(plan, events, lambda *args: None)
        report = reporting.summary(result, events)
        assert result['status'] == 'COMPLETE'
        assert report['prospective_dev_necessary_gate_met'] is gate
        assert not report['validation_authorized'] and not report['release_enabled']
        assert report['charges_and_health_events_preserved'] == events


@pytest.mark.parametrize('field', ['init_index', 'task_id', 'bddl_hash'])
def test_task_runtime_binding_before_execution(trusted, field):
    plan, runtime, _ = copy.deepcopy(trusted)
    task = runtime['tasks']['0']
    if field == 'bddl_hash':
        next(r for r in runtime['files'] if r['path'] == task['bddl_path'])['sha256'] = 'b'*64
    else:
        task[field] += 1
    with pytest.raises(ValueError): b.manifest(plan, runtime, plan['episodes'][2])


def test_resume_and_stop_composition(draft, tmp_path, monkeypatch):
    plan, _, _ = copy.deepcopy(draft)
    stop = tmp_path / 'autonomy_20261004/STOP'
    plan['stop_path'] = str(stop)
    monkeypatch.setattr(c, 'stop_path', lambda *_: str(stop))
    now = dt.datetime(2026, 10, 4, 16, tzinfo=dt.timezone.utc)
    events = journal(plan['episodes'][:3], [2])
    seen = []
    result = supervisor.next_dispatch(plan, events, lambda r, f: seen.append(r['episode_key']), allowance(), now=now)
    assert len(seen) == 3 and result['next_row'] == plan['episodes'][3]
    stop.parent.mkdir(); stop.touch()
    with pytest.raises(ValueError, match='STOP'):
        supervisor.next_dispatch(plan, events, lambda *args: None, allowance(), now=now)
    # A live handle is reconciled without trying admission, dispatch or signalling.
    result = supervisor.next_dispatch(plan, events, lambda *args: None, allowance(), now=now, live_handles=['live'])
    assert result['status'] == 'LIVE_OR_UNSETTLED' and result['next_row'] is None
