"""Bounded CPU integration; approval-shaped graph is ephemeral and non-exportable."""
import copy
import tempfile
from pathlib import Path

import pytest
from scripts import qd_ed_n23_worker as w, qd_ed_final_runner as r
from scripts import qd_ed_n36_engineering as e, qd_ed_n36_healthcheck as health
from scripts import qd_ed_n36_runner as runner, qd_ed_n36_worker as worker
from scripts import qd_ed_n36_contract as c
from n36_engineering_cpu_fixture import Graph, put, lines


@pytest.fixture(scope='module')
def graph():
    # Never retain approval-shaped fixture data in pytest basetemp or logs.
    with tempfile.TemporaryDirectory(prefix='ephemeral-engineering-', dir=Path(__file__).resolve().parents[1] / '.cpu-test-artifacts') as directory:
        with pytest.MonkeyPatch.context() as patch:
            yield Graph(Path(directory), patch)
    assert not Path(directory).exists()


@pytest.fixture
def f(graph, monkeypatch):
    graph.reset()
    graph.orchestration(monkeypatch)
    return graph


def test_accepted_health_reservation_readiness_episode_release(f, monkeypatch):
    result = f.health()
    assert result['status'] == 'VALID', result
    resources = r.read_events(f.owner / 'data/gpu-healthcheck-ledger.jsonl')
    assert [x['event'] for x in resources] == ['reserved', 'dispatched', 'completed']
    assert len(f.launches) == 1
    # Readiness negative cases share the one real settled health lifecycle.
    for fault in ('dispatch_before_reserved', 'dispatch_after_observed', 'future_completed', 'terminal_mismatch'):
        bad = copy.deepcopy(resources)
        if fault == 'dispatch_before_reserved': bad[1]['time_unix'] = bad[0]['time_unix'] - 1
        elif fault == 'dispatch_after_observed': bad[1]['time_unix'] = bad[-1]['time_unix'] + 1
        elif fault == 'future_completed': bad[-1]['time_unix'] += 1
        else: bad[-1]['provider_verified'] = False
        with pytest.raises(ValueError):
            e.validate_readiness(f.plan_ref, {'readiness': f.readiness()}, resources=bad)
    episode = f.release('episode', f.readiness())
    monkeypatch.setattr(runner, 'wait_worker', f.episode_child)
    # Private copy observes only a dead synthetic PID on restart.
    monkeypatch.setattr(runner, 'process_identity', lambda pid: {'pid': pid, 'boot_id': 'CPU_FIXTURE', 'proc_start_ticks': '1'})
    result = f.episode_run(f.plan_ref, episode, _engineering=True)
    assert result['status'] == 'PAUSED_FOR_ROOT_G3', result
    assert len(f.launches) == 2
    def exited(pid):
        raise FileNotFoundError('CPU simulated child exited')
    monkeypatch.setattr(runner, 'process_identity', exited)
    import yaml
    state_path = f.owner / 'research-state.yaml'
    state = r.read_state(state_path)
    state.update(first_C0_G3_pause=False, later_root_G3_approved=True)
    state_path.write_text(yaml.safe_dump(state))
    restarted = f.episode_run(f.plan_ref, episode, _engineering=True)
    assert restarted['status'] == 'PAUSED_FOR_ROOT_G3', restarted
    assert restarted['next_row'] is None and restarted['outcomes'] == []
    assert len(f.launches) == 2
    # Preserve the successful episode bytes for real restart crash/mismatch checks.
    f.completed_episode = {path: path.read_bytes() for parent in (f.output, f.owner / 'data')
                           for path in parent.rglob('*') if path.is_file()}
    f.completed_episode[state_path] = state_path.read_bytes()
    f.completed_episode_ref = episode


def test_public_dispatch_veto_still_unconditional(f):
    for call in (lambda: e.require_dispatch_implementation(),
                 lambda: e.execute_one(f.plan_ref, f.health_ref),
                 lambda: runner.execute_one(f.plan_ref, f.health_ref, _engineering=True),
                 lambda: health.run_healthcheck(f.plan_ref, f.health_ref, e.HEALTH_ID, timeout_seconds=20)):
        with pytest.raises(RuntimeError, match='engineering dispatch disabled'):
            call()
    assert not f.launches


def test_fresh_episode_predispatch_abort_and_exhaustion(f):
    # Health/device/import evidence is simulated; admission, runner, accounting,
    # durable writes and reconciliation are the real integrated implementations.
    episode = f.accepted_episode()
    restore = f.saved_cpu_state()
    ledger = f.owner / 'data/attempt-ledger.jsonl'
    output = f.output / 'attempts' / e.EPISODE_KEY
    for fault in ('stop_after_reserved', 'stop_after_dispatched', 'popen_failure'):
        restore()
        calls = []
        original_append = r.append_event_locked
        def append_then_stop(root, event):
            original_append(root, event)
            if event['event'] == {'stop_after_reserved': 'reserved',
                                  'stop_after_dispatched': 'dispatched'}.get(fault):
                Path(c.stop.STOP_PATHS[0]).touch()
        def fail_before_child(*args, **kwargs):
            calls.append('simulated Popen failure; no child created')
            raise OSError('CPU simulated pre-child launch failure')
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(r, 'append_event_locked', append_then_stop)
            patch.setattr(runner.subprocess, 'Popen', fail_before_child)
            if fault == 'popen_failure':
                result = f.episode_run(f.plan_ref, episode, _engineering=True)
                assert result['status'] == 'INVALID_STOP'
                terminal = result['terminal']
                assert terminal['event'] == 'aborted'
                assert terminal['outcome_valid'] is False and terminal['success'] is None
                assert terminal['retryable_infrastructure'] is False
                assert terminal['required_cost_telemetry_complete'] is False
                assert terminal['gpu_process_wall_seconds'] == 0.  # simulated clock
                assert w.read_ref(c.ref(output / 'attempt-result.json')) == terminal
                assert calls == ['simulated Popen failure; no child created']
            else:
                with pytest.raises(ValueError, match='STOP'):
                    f.episode_run(f.plan_ref, episode, _engineering=True)
                assert calls == []
                assert not (output / 'attempt-result.json').exists()
        events = r.read_events(ledger)
        local = events[len(f.baseline[e.JOURNALS[0]]):]
        expected = {'stop_after_reserved': ['reserved'],
                    'stop_after_dispatched': ['reserved', 'dispatched'],
                    'popen_failure': ['reserved', 'dispatched', 'aborted']}[fault]
        assert [event['event'] for event in local] == expected
        assert local[0]['reserved_gpu_seconds'] == 1840
        assert local[0]['accounting_admission']['reserved_gpu_seconds'] == 1840
        assert not f.launches and not (output / 'process.json').exists()
        # Remove the triggering STOP: exhaustion must survive independently.
        Path(c.stop.STOP_PATHS[0]).unlink(missing_ok=True)
        before = {path: path.read_bytes() for parent in (f.owner, f.output)
                  for path in parent.rglob('*') if path.is_file()}
        restarted = f.episode_run(f.plan_ref, episode, _engineering=True)
        # Even an aborted pre-child launch has no process identity artifact;
        # existing_handles conservatively classifies it UNKNOWN on restart.
        assert restarted['status'] == 'LIVE_OR_UNSETTLED'
        assert restarted['scope_exhausted'] is True
        assert restarted['continuation_authorized'] is False
        assert restarted['scientific_eligible'] is False
        assert restarted['next_row'] is None and restarted['outcomes'] == []
        assert not f.launches
        assert before == {path: path.read_bytes() for parent in (f.owner, f.output)
                          for path in parent.rglob('*') if path.is_file()}
    with pytest.raises(RuntimeError, match='engineering dispatch disabled'):
        e.require_dispatch_implementation()


def test_accepted_context_cross_family_rejection(f):
    episode = f.accepted_episode()
    context = worker.context_for(f.plan_ref, e.row(), episode)
    reference = f.doc('fixture-accepted-context', context)
    assert worker.validate_context(reference)[0] == context
    # No launch admission is certified: its public veto remains unconditional.
    with pytest.raises(RuntimeError, match='engineering dispatch disabled'):
        worker.validate_context(reference, admission=True)
    before = {path: path.read_bytes() for parent in (f.owner, f.output)
              for path in parent.rglob('*') if path.is_file()}
    launches = list(f.launches)
    cases = []
    ordinary = {key: value for key, value in context.items()
                if key not in ('purpose', 'scope', 'audit_plan')}
    ordinary['schema'] = 'n36-worker-context-v1'
    cases.append(('ordinary-context-engineering-release', ordinary, 'worker context/release family cross-use'))
    cases.append(('health-release-in-episode-context', {**context, 'release': f.health_ref}, 'release fields'))
    cases.append(('audit-plan-in-operational-context', {**context, 'plan': f.plan['audit_plan']},
                  'unsupported worker release schema'))
    for key in ('purpose', 'scope', 'audit_plan'):
        value = copy.deepcopy(context)
        value[key] = 'CPU_FOREIGN_FAMILY' if key != 'audit_plan' else f.plan_ref
        cases.append(('foreign-' + key, value, 'engineering context bindings'))
    for name, value, reason in cases:
        with pytest.raises(ValueError, match=reason):
            worker.validate_context(f.doc('fixture-cross-family-' + name, value))
        assert f.launches == launches
        assert before == {path: path.read_bytes() for parent in (f.owner, f.output)
                          for path in parent.rglob('*') if path.is_file()}
    assert worker.validate_context(reference)[0] == context


def test_f1_reacquired_handoff_rejects_foreign_resource_before_output(f, monkeypatch):
    def reserve_then_corrupt(*args, **kwargs):
        result = f.reserve(*args, **kwargs)
        record = result[0]
        r.append_healthcheck_event(f.owner, {**record, 'resource_id': 'CPU_FOREIGN_RESOURCE'})
        return result
    monkeypatch.setattr(f.api, 'reserve_health_handoff', reserve_then_corrupt)
    with pytest.raises(ValueError, match='sole health identity'):
        f.health()
    resources = r.read_events(f.owner / 'data/gpu-healthcheck-ledger.jsonl')
    assert len([x for x in resources if x['resource_id'] == e.HEALTH_ID]) == 1
    assert resources[0]['event'] == 'reserved'
    assert not f.launches and not f.output.exists()
    with pytest.raises(ValueError):
        f.reserve(f.plan_ref, f.health_ref, e.HEALTH_ID, timeout_seconds=20)
    assert r.read_events(f.owner / 'data/gpu-healthcheck-ledger.jsonl') == resources


def test_f1_live_snapshot_mutation_matrix_under_real_locks(f):
    import yaml
    record, binding = f.reserve(f.plan_ref, f.health_ref, e.HEALTH_ID, timeout_seconds=20)
    state_path = f.owner / 'research-state.yaml'
    state_bytes = state_path.read_bytes()
    ledger_bytes = {name: (f.owner / 'data' / name).read_bytes() for name in e.JOURNALS}
    def check():
        with r.locked(f.owner / 'data/qd-ed-runner.lock', nonblocking=True):
            return e.validate_health_handoff(f.owner, f.plan_ref, f.health_ref, record, binding)
    assert check()[0] == f.plan
    mutations = ['foreign_attempt', 'foreign_health_completed', 'foreign_reservation', 'same_id_replay',
                 'health_dispatched', 'changed_record', 'state_hold', 'state_private', 'state_adoption',
                 'state_run', 'state_artifacts', 'state_gpu', 'state_other']
    for fault in mutations:
        try:
            state = yaml.safe_load(state_bytes)
            if fault.startswith('state_'):
                if fault == 'state_hold': state['external_resource_hold'] = {'do_not_auto_resume': True}
                elif fault == 'state_private': state['resource_isolation']['private_budget'] = False
                elif fault == 'state_adoption': state['n36_engineering_budget_authority']['sha256'] = '0'*64
                elif fault == 'state_run': state['run_name'] = 'foreign'
                elif fault == 'state_artifacts': state['artifacts'] += '/foreign'
                elif fault == 'state_gpu': state['gpu_pool'] = [0]
                else: state['unrelated_edit_during_handoff'] = True
                state_path.write_text(yaml.safe_dump(state))
            elif fault == 'foreign_attempt':
                r.append_event(f.owner, {'attempt_id': 'CPU_FOREIGN', 'event': 'reserved'})
            elif fault == 'foreign_reservation':
                lines(f.owner / 'data' / e.JOURNALS[2], [*f.baseline[e.JOURNALS[2]], {'event': 'foreign'}])
            elif fault == 'foreign_health_completed':
                for event in ('reserved', 'dispatched', 'completed'):
                    r.append_healthcheck_event(f.owner, {**record, 'resource_id': 'CPU_FOREIGN',
                        'event': event, 'gpu_process_wall_seconds': 0.})
            else:
                values = [record]
                if fault == 'same_id_replay': values.append(record)
                elif fault == 'health_dispatched': values.append({**record, 'event': 'dispatched'})
                else: values = [{**record, 'admission': {'changed': True}}]
                lines(f.owner / 'data' / e.JOURNALS[1], values)
            with pytest.raises((ValueError, r.GateError), match='engineering|duplicate'):
                check()
            assert not f.launches and not f.output.exists(), fault
        finally:
            state_path.write_bytes(state_bytes)
            for name, data in ledger_bytes.items():
                (f.owner / 'data' / name).write_bytes(data)
    assert r.read_events(f.owner / 'data' / e.JOURNALS[1]) == [record]
    assert check()[0] == f.plan


def test_deep_closure_corruption_both_release_families(f):
    # Rehash only fixture document DAGs so semantic mutations get past outer
    # reference equality. Never rehash corrupted source/native/runtime bytes.
    import json
    originals = {p: p.read_bytes() for p in f.docs.glob('*.json')}
    episode = f.release('episode', {'health_release': f.health_ref, 'terminal': f.health_ref})
    originals.update({p: p.read_bytes() for p in f.docs.glob('*.json') if p not in originals})
    targets = {
        'NON_C0': Path(f.audit['expected_manifests'][f.audit['episodes'][1]['episode_key']]['path']),
        'source': f.source / 'main.py',
        'runtime': Path(f.closure['modules']['robosuite.controllers.osc']['path']),
        'native': Path(w.read_ref(f.native_ref)['libraries'][0]['path']),
        'controller': Path(f.controller_ref['path']),
        'runtime_closure': Path(f.closure_ref['path']),
    }
    for fault, path in targets.items():
        before = path.read_bytes()
        try:
            if fault in ('source', 'runtime', 'native'):
                path.write_bytes(before + b'\nCPU MUTATION\n')
                refs = (f.plan_ref, f.health_ref, episode)
            else:
                doc = json.loads(before)
                if fault == 'NON_C0': doc['resolved_config']['nonprogress_tangent_mode'] = 'CORRUPT'
                elif fault == 'controller': doc['instance']['control_delta'] = False
                else: doc['required_after'].append('unbound.module')
                put(path, doc)
                cache = {}
                def refresh(value):
                    if isinstance(value, dict):
                        if set(value) == {'path', 'sha256'} and Path(value['path']).parent == f.docs:
                            p = Path(value['path'])
                            if p not in cache:
                                cache[p] = put(p, refresh(json.loads(p.read_text())))
                            return cache[p]
                        return {key: refresh(v) for key, v in value.items()}
                    return [refresh(v) for v in value] if isinstance(value, list) else value
                refs = tuple(refresh(ref) for ref in (f.plan_ref, f.health_ref, episode))
            for validate, release_ref in ((e.validate_health_release, refs[1]), (e.validate_release, refs[2])):
                with pytest.raises((ValueError, r.GateError), match={
                    'NON_C0': 'external manifest differs', 'source': 'uncommitted source bytes',
                    'runtime': 'runtime source bytes differ', 'native': 'native binary bytes/path',
                    'controller': 'OSC normalized', 'runtime_closure': 'runtime modules required'}[fault]):
                    validate(refs[0], release_ref)
        finally:
            path.write_bytes(before)
            for doc_path, data in originals.items():
                doc_path.write_bytes(data)


def test_clock_and_headroom_edges(f):
    import datetime as dt
    import math
    from decimal import Decimal
    end = dt.datetime.fromisoformat(c.DEADLINE.replace('Z', '+00:00'))
    for need in (2100, 1840, 60):
        f.guard(f.plan, f.authority, need=need, now=end - dt.timedelta(seconds=need))
        with pytest.raises(ValueError, match='full work headroom'):
            f.guard(f.plan, f.authority, need=need, now=end - dt.timedelta(seconds=need, microseconds=-1))
    margin = .23357169027962
    local = {'gpu_hours_consumed': 0., 'gpu_healthcheck_hours': 0., 'reserved_attempts': 0}
    snap = {'gpu_hours_consumed': 75.60616276674473, 'running': 0, 'gpu_healthcheck_inflight': 0}
    assert e.headroom(snap, local, health=True, margin=margin, protected=44.)['reserved_gpu_seconds'] == 60
    used = {**local, 'gpu_hours_consumed': 60/3600, 'gpu_healthcheck_hours': 60/3600}
    assert e.headroom(snap, used, health=False, margin=margin, protected=44.)['reserved_gpu_seconds'] == 1840
    with pytest.raises(ValueError, match='1900-second'):
        e.headroom(snap, {**used, 'gpu_hours_consumed': (60+1e-8)/3600}, health=False, margin=margin, protected=44.)
    # Adjacent representable floats bracket the precise Decimal weekly/protected
    # boundary; report this separately from exact wall-time boundaries.
    for health_mode, need in ((True, 1900), (False, 1840)):
        edge = float(e.accounting.WEEKLY_HOURS - Decimal(str(margin)) - Decimal('44') - Decimal(need)/3600)
        while Decimal(str(edge))*3600 + Decimal(str(margin))*3600 + Decimal('44')*3600 + need > e.accounting.WEEKLY_HOURS*3600:
            edge = math.nextafter(edge, -math.inf)
        e.headroom({**snap, 'gpu_hours_consumed': edge}, local, health=health_mode, margin=margin, protected=44.)
        with pytest.raises(ValueError, match='weekly|full health plus episode'):
            e.headroom({**snap, 'gpu_hours_consumed': math.nextafter(edge, math.inf)}, local,
                       health=health_mode, margin=margin, protected=44.)


def test_restart_crashes_and_terminal_receipt_mismatch(f, monkeypatch):
    if not hasattr(f, 'completed_episode'):
        pytest.skip('positive lifecycle must complete first; no synthetic success substitute')
    def exited(pid):
        raise FileNotFoundError('CPU simulated child exited')
    monkeypatch.setattr(runner, 'process_identity', exited)
    def restore():
        f.reset()
        for path, data in f.completed_episode.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        # Restart occurs after the saved observations, never at reset's earlier clock.
        f.clock = max(event.get('time_unix', 0) for name in e.JOURNALS[:2]
                      for event in r.read_events(f.owner / 'data' / name)) + 1
    episode = f.completed_episode_ref
    path = f.owner / 'data/attempt-ledger.jsonl'
    for fault, status in [('reservation', 'LIVE_OR_UNSETTLED'), ('dispatched', 'LIVE_OR_UNSETTLED'),
                          ('terminal_before_artifact', 'INVALID_STOP'), ('receipt_mismatch', 'INVALID_STOP'),
                          ('abort', 'INVALID_STOP')]:
        restore()
        events = r.read_events(path)
        if fault in ('reservation', 'dispatched'):
            lines(path, events[:-2] if fault == 'reservation' else events[:-1])
        elif fault == 'terminal_before_artifact':
            (f.output / 'attempts' / e.EPISODE_KEY / 'attempt-result.json').unlink()
        elif fault == 'receipt_mismatch':
            receipt = f.output / 'attempts' / e.EPISODE_KEY / 'eds_eval/n36-worker-receipt.json'
            value = w.read_ref(c.ref(receipt))
            value['process_unchanged'] = False
            ref = put(receipt, value)
            events[-1]['n36_worker_receipt'] = ref
            lines(path, events)
            put(f.output / 'attempts' / e.EPISODE_KEY / 'attempt-result.json', events[-1])
        else:
            events[-1].update(event='aborted', outcome_valid=False)
            lines(path, events)
            put(f.output / 'attempts' / e.EPISODE_KEY / 'attempt-result.json', events[-1])
        result = f.episode_run(f.plan_ref, episode, _engineering=True)
        assert result['status'] == status, (fault, result)
        assert result['next_row'] is None and not f.launches


def test_authority_adoption_and_full_snapshot_mutations(f):
    # Full accepted fixture authority, including all three retained prefixes,
    # is validated before mutating one bound component at a time.
    assert e.validate_authority(f.plan, f.authority) == f.baseline
    for fault in ('caps', 'binding', 'prefix', 'weekly', 'adoption', 'snapshot'):
        authority = copy.deepcopy(f.authority)
        if fault == 'caps': authority['caps']['gpu_hours'] += 1
        elif fault == 'binding': authority['runtime']['sha256'] = '0'*64
        elif fault == 'prefix': authority['ledger_prefixes'][e.JOURNALS[0]]['sha256'] = '0'*64
        elif fault == 'weekly': authority['weekly_window']['increment_gpu_hours'] += 1
        elif fault == 'adoption':
            value = w.read_ref(authority['source_adoption'])
            value['owner_root'] += '/foreign'
            authority['source_adoption'] = f.doc('fixture-bad-adoption', value)
        else:
            value = w.read_ref(authority['amendment'])
            value['snapshot']['reserved_attempts'] -= 1
            authority['amendment'] = f.doc('fixture-bad-snapshot', value)
        with pytest.raises(ValueError, match='engineering|weekly'):
            e.validate_authority(f.plan, authority)


def test_public_reservation_and_guard_veto(f):
    for call in (lambda: e.reserve_health(f.plan_ref, f.health_ref, e.HEALTH_ID, timeout_seconds=20),
                 lambda: e.reserve_health_handoff(f.plan_ref, f.health_ref, e.HEALTH_ID, timeout_seconds=20),
                 lambda: e.launch_guard(f.plan, f.authority)):
        with pytest.raises(RuntimeError, match='engineering dispatch disabled'):
            call()
    assert not f.launches
    assert r.read_events(f.owner / 'data/gpu-healthcheck-ledger.jsonl') == []


def test_predispatch_health_abort_cross_release_and_issuance_edges(f, monkeypatch):
    import datetime as dt
    from scripts import qd_ed_n36_release as full
    def stop_after_reserve(*args, **kwargs):
        result = f.reserve(*args, **kwargs)
        Path(c.stop.STOP_PATHS[0]).touch()
        return result
    monkeypatch.setattr(f.api, 'reserve_health_handoff', stop_after_reserve)
    result = f.health()
    assert result['status'] == 'INVALID_STOP'
    resources = r.read_events(f.owner / 'data/gpu-healthcheck-ledger.jsonl')
    assert [event['event'] for event in resources] == ['reserved', 'aborted']
    assert not f.launches and resources[-1]['gpu_process_wall_seconds'] == 0.
    episode = f.release('episode', f.readiness())
    with pytest.raises(ValueError, match='terminal readiness binding'):
        e.validate_release(f.plan_ref, episode)
    for validate, release in ((e.validate_health_release, episode), (e.validate_release, f.health_ref),
                              (full.validate_release, episode)):
        with pytest.raises(ValueError, match='release fields|release differs|unsupported N36 cohort'):
            validate(f.plan_ref, release)
    Path(c.stop.STOP_PATHS[0]).unlink()
    with pytest.raises(ValueError, match='consumed forever'):
        f.reserve(f.plan_ref, f.health_ref, e.HEALTH_ID, timeout_seconds=20)
    assert r.read_events(f.owner / 'data/gpu-healthcheck-ledger.jsonl') == resources
    assert not f.launches
    # Exact detached-release issuance window, followed by one microsecond short.
    saved = {p: p.read_bytes() for p in f.docs.glob('*.json')}
    previous = f.clock
    end = dt.datetime.fromisoformat(c.DEADLINE.replace('Z', '+00:00'))
    try:
        for offset, accepted in ((dt.timedelta(seconds=2100), True),
                                 (dt.timedelta(seconds=2100, microseconds=-1), False)):
            issued = end - offset
            f.clock = issued.timestamp()
            ref = f.release('health', issued_at=issued.isoformat())
            if accepted:
                assert e.validate_health_release(f.plan_ref, ref)[0] == f.plan
            else:
                with pytest.raises(ValueError, match='2100-second envelope'):
                    e.validate_health_release(f.plan_ref, ref)
    finally:
        f.clock = previous
        for path, data in saved.items():
            path.write_bytes(data)
