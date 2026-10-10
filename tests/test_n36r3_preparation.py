"""CPU-only boundary fixtures; no production G3 evidence is manufactured."""
import copy
import json
import pytest
from scripts import qd_ed_n36_contract as c, qd_ed_n36_supervise as s
from scripts import qd_ed_n36r3_preparation as p


def plan_and_events(count=1):
    rows = c.expected_rows(cohort=c.DRAFT_N36R3_COHORT)
    plan = {'schema': 'n36-release-draft-v1', 'frozen': False, 'release_enabled': False,
            'cohort': c.DRAFT_N36R3_COHORT, 'episodes': rows, 'worktree': str(c.ROOT)}
    events = []
    for row in rows[:count]:
        base = {'attempt_id': row['episode_key'], 'episode_key': row['episode_key'],
                'identity': s.c_identity(row), 'budget_bucket': row['budget_bucket'],
                'replacement': None}
        events.extend([{**base, 'event': 'reserved'}, {**base, 'event': 'dispatched'},
                       {**base, 'event': 'valid', 'outcome_valid': True,
                        'required_cost_telemetry_complete': True, 'success': False}])
    return plan, events


def test_pause_reverifies_terminal_on_every_restart_and_no_override():
    plan, events = plan_and_events()
    seen = []
    for _ in range(2):
        plan['G3_approved'] = True  # Untrusted fields cannot waive the boundary.
        result = s.reconcile(plan, events, lambda row, final: seen.append(final))
        assert result['status'] == 'PAUSED_FOR_ROOT_G3' and result['next_row'] is None
        assert result['terminal'] == events[-1] and len(result['outcomes']) == 1
    assert len(seen) == 2


def test_first_primary_ready_live_and_invalid_remain_distinct():
    plan, events = plan_and_events()
    assert s.reconcile(plan, [], lambda *a: None)['next_row']['profile'] == 'C0'
    assert s.reconcile(plan, events[:-1], lambda *a: None)['status'] == 'LIVE_OR_UNSETTLED'
    def reject(*args):
        raise ValueError('actual receipt invalid')
    assert s.reconcile(plan, events, reject)['status'] == 'INVALID_STOP'
    events[-1]['event'] = 'aborted'
    assert s.reconcile(plan, events, lambda *a: None)['status'] == 'INVALID_STOP'


def test_later_dispatch_and_forged_release_rejected():
    plan, events = plan_and_events(2)
    with pytest.raises(ValueError, match='first C0 root boundary'):
        s.reconcile(plan, events, lambda *a: None)
    plan.update(schema='n36-released-plan-v1', frozen=True, release_enabled=True)
    from scripts import qd_ed_n36_release as release
    with pytest.raises(ValueError, match='draft only'):
        release.validate_plan(plan)


def test_pause_scope_preserves_old_cohorts():
    for selected in c.IDENTITIES:
        rows = c.expected_rows(cohort=selected)
        assert s.first_c0_boundary(rows[0]) is (selected == c.DRAFT_N36R3_COHORT)
        assert not any(s.first_c0_boundary(row) for row in rows[1:])


def test_launch_stops_on_pause_without_second_call(monkeypatch):
    from scripts import qd_ed_n36_runner as runner
    calls = []
    def execute(*args):
        calls.append(args)
        return {'status': 'PAUSED_FOR_ROOT_G3'}
    monkeypatch.setattr(runner, 'execute_one', execute)
    assert runner.launch('plan', 'release')['status'] == 'PAUSED_FOR_ROOT_G3'
    assert len(calls) == 1


def test_exact_finite_arithmetic_and_unchanged_reserves():
    snap = {'gpu_hours_consumed': 75.52725286641478,
            'by_bucket': {'baseline': 100, 'development': 400, 'recovery': 5,
                          'validation': 0, 'formal': 0}}
    result = p.arithmetic(snap)
    assert result['hours']['conservative_before'] == '75.76082455669440'
    assert result['hours']['conservative_after'] == '96.76082455669440'
    assert result['hours']['unprotected_effective_after'] == '80.32322237000398'
    assert result['seconds']['episodes_total'] + result['seconds']['health_total'] + 200 == 75600
    assert result['health']['maximum_full_reservations'] == 30
    assert result['prospective_attempts'] == 545 and result['remaining_attempts'] == 1255
    assert result['buckets']['validation']['remaining'] == 180
    assert result['current_headroom'] is None and result['automatic_recoveries'] == 0


def test_bound_input_tampering_rejected(tmp_path):
    path = tmp_path / 'input.json'
    path.write_text('{}')
    reference = p.bound(path)
    assert p.read(reference) == {}
    path.write_text('{"release_enabled":true}')
    with pytest.raises(ValueError, match='binding changed'):
        p.read(reference)


def test_snapshot_binds_all_current_bytes_and_rejects_cost_drift(tmp_path, monkeypatch):
    data = tmp_path / 'data'
    data.mkdir()
    events = [{'attempt_id': 'old', 'event': event, 'budget_bucket': 'baseline',
               'gpu_process_wall_seconds': 1} for event in ('reserved', 'dispatched', 'valid')]
    for name, rows in [('attempt-ledger.jsonl', events), ('gpu-healthcheck-ledger.jsonl', []),
                       ('gpu-hour-reservation-ledger.jsonl', [])]:
        (data / name).write_text(''.join(json.dumps(x)+'\n' for x in rows))
    review = {'ledger_prefix': p.bound(data/'attempt-ledger.jsonl'),
              'health_ledger_prefix': p.bound(data/'gpu-healthcheck-ledger.jsonl')}
    snapshot = {'dispatched': 505, 'reserved_attempts': 505,
                'gpu_hours_consumed': 75.52725286641478, 'running': 0, 'gpu_healthcheck_inflight': 0}
    monkeypatch.setattr(p.r, 'budget_snapshot', lambda *a: copy.deepcopy(snapshot))
    result = p.ledger_snapshot(tmp_path, review)
    assert len(result['ledger_prefixes']) == 3
    assert result['reservation_reconciliation_required']
    snapshot['gpu_hours_consumed'] = 75.5
    with pytest.raises(ValueError, match='accounting differs'):
        p.ledger_snapshot(tmp_path, review)
    (data/'attempt-ledger.jsonl').write_text('{}\n')
    with pytest.raises(ValueError, match='prefix changed'):
        p.ledger_snapshot(tmp_path, review)
