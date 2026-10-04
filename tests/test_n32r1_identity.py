"""CPU-only identity recovery regressions using synthetic in-memory history."""
import copy
import json

import pytest

from scripts import qd_ed_n32_contract as c, qd_ed_n32_release as release
from scripts import qd_ed_n32_supervise as supervisor, qd_ed_n32_report as reporting
from test_n32_production import admit, historical
from test_n32_release import journal


OLD_COHORT = 'N32_ARCHIVE_ELIGIBLE_CAPTURE_DEV_20261004'


def old_rows():
    tasks = json.loads((c.ROOT / 'configs/qd_ed_final/n31_dev_task_identities.json').read_text())['tasks']
    return [{**task, 'iteration': OLD_COHORT, 'profile': arm, 'timeout_seconds': 1800,
             'episode_key': f'n32_dev_t{task["task_id"]:02d}_{arm.lower()}_20261004',
             'budget_bucket': 'baseline' if arm == 'C0' else 'development'}
            for task in tasks for arm in ('C0', 'Q0', 'N32')]


def test_fixed_fresh_identities_preserve_all_other_row_fields():
    rows, old = c.expected_rows(), old_rows()
    assert c.COHORT == 'N32R1_ARCHIVE_ELIGIBLE_CAPTURE_DEV_20261004'
    assert rows == c.expected_rows() and len(rows) == 30
    assert len({row['episode_key'] for row in rows}) == 30
    assert {row['episode_key'] for row in rows}.isdisjoint(row['episode_key'] for row in old)
    for row, prior in zip(rows, old):
        assert row['iteration'] == c.COHORT != prior['iteration']
        assert row['episode_key'] == f'n32r1_dev_t{row["task_id"]:02d}_{row["profile"].lower()}_20261004'
        assert {k: v for k, v in row.items() if k not in ('iteration', 'episode_key')} == {
            k: v for k, v in prior.items() if k not in ('iteration', 'episode_key')}
    assert sum(row['budget_bucket'] == 'baseline' for row in rows) == 10
    assert sum(row['budget_bucket'] == 'development' for row in rows) == 20
    assert c.LIMITS['automatic_recoveries'] == 0
    assert c.DEADLINE == '2026-10-10T17:42:00Z'


@pytest.mark.parametrize('old_terminal', ['invalid', 'valid'])
def test_old_events_never_supply_new_accepted_cells(old_terminal):
    rows = c.expected_rows()
    plan = {'episodes': rows, 'worktree': str(c.ROOT)}
    # Also challenge isolation with a hypothetical fully successful old matrix.
    old = journal(old_rows(), range(30)) if old_terminal == 'valid' else journal(old_rows()[:1])
    if old_terminal == 'invalid':
        old[-1]['outcome_valid'] = False
    before = copy.deepcopy(old)
    verified = []
    result = supervisor.reconcile(plan, old, lambda *args: pytest.fail('old cell reached verifier'))
    assert result['outcomes'] == [] and result['next_row'] == rows[0]
    assert result['status'] == 'READY_FOR_ROOT_RELEASE'
    report = reporting.summary(result, old)
    assert all(cell[arm] == 'Unknown' for cell in report['matrix'] for arm in c.ARMS)
    assert report['prospective_dev_necessary_gate_met'] is False
    assert report['charges_and_health_events_preserved'] == before
    mixed = old + journal(rows[:1], (0,))
    result = supervisor.reconcile(plan, mixed, lambda row, final: verified.append(row))
    assert verified == [rows[0]] and len(result['outcomes']) == 1
    assert result['next_row'] == rows[1]
    assert old == before


def test_old_invalid_c0_charge_remains_global_not_new_primary(tmp_path, monkeypatch):
    hours = 0.19622250473834962
    # The ledger records completed invalid outcomes as event=valid/outcome_valid=False.
    events = historical(hours * 3600, 'baseline', old_rows()[0]['episode_key'], OLD_COHORT)
    before = copy.deepcopy(events)
    observed = []
    guard = c.pre_dispatch

    def capture(row, allowance, **kwargs):
        observed.append(copy.deepcopy(allowance))
        return guard(row, allowance, **kwargs)

    monkeypatch.setattr(c, 'pre_dispatch', capture)
    snap = admit(tmp_path, events)
    assert snap['dispatched'] == 1 and snap['invalid'] == 1
    assert snap['by_bucket']['baseline'] == 1
    assert snap['gpu_hours_consumed'] == pytest.approx(hours)
    assert snap['gpu_hours_by_bucket']['baseline'] == pytest.approx(hours)
    allowance = observed[0]
    assert allowance['global_attempts_remaining'] == 1799
    assert allowance['bucket_attempts_remaining']['baseline'] == 399
    assert allowance['cohort_attempts_remaining'] == 30
    assert allowance['cohort_seconds_remaining'] == 18000
    assert allowance['private_seconds_remaining'] == pytest.approx((224 - hours) * 3600)
    assert events == before


@pytest.mark.parametrize('identity', ['cohort', 'episode_key', 'both'])
def test_release_rejects_old_identity_without_relaxing_validation(identity):
    rows = c.expected_rows()
    plan = {'schema': 'n32-released-plan-v1', 'frozen': True, 'release_enabled': True,
            'episodes': rows, 'worktree': str(c.ROOT), 'limits': c.LIMITS,
            'worker_contract': c.WORKER_CONTRACT, 'deadline': c.DEADLINE,
            'stop_path': c.stop_path(), 'phase_authorization': {'dev': True, 'validation': False, 'formal': False},
            'attempt_identity': 'episode_key', 'expected_manifests': {row['episode_key']: {} for row in rows}}
    release.validate_plan(plan)
    for row, prior in zip(rows, old_rows()):
        if identity in ('cohort', 'both'):
            row['iteration'] = prior['iteration']
        if identity in ('episode_key', 'both'):
            row['episode_key'] = prior['episode_key']
    with pytest.raises(ValueError, match='released plan contract'):
        release.validate_plan(plan)
