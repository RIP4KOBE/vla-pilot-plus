"""Prospective N34R1 CPU contract tests; no owning data or release creation."""
import copy
from collections import Counter
import datetime as dt
import json
from pathlib import Path

import pytest

from scripts import qd_ed_final_runner as r, qd_ed_n34_contract as c
from scripts import qd_ed_n34_release as release, qd_ed_n34_supervise as s
from scripts import qd_ed_n34_bridge as b, qd_ed_n34_report as report
from test_n34_lifecycle import budget_fixture, old_invalid
from test_n34_production_integration import journal, allowance

NOW = dt.datetime(2026, 10, 8, tzinfo=dt.timezone.utc)


def plan():
    return {'worktree': str(c.ROOT), 'episodes': c.expected_rows()}


def test_fresh_matrix_identical_science_and_exact_mapping():
    tasks = json.loads((c.ROOT / 'configs/qd_ed_final/n31_dev_task_identities.json').read_text())['tasks']
    rows = c.expected_rows()
    assert len({row['episode_key'] for row in rows}) == 30
    assert [(x['task_id'], x['profile']) for x in rows] == [(i, a) for i in range(10) for a in c.ARMS]
    assert Counter(x['budget_bucket'] for x in rows) == {'baseline': 9, 'development': 20, 'recovery': 1}
    for row in rows:
        assert all(row[k] == v for k, v in tasks[row['task_id']].items())
        assert row['episode_key'] == f'n34r1_dev_t{row["task_id"]:02d}_{row["profile"].lower()}_20261008'
        assert row['iteration'] == c.COHORT
    assert rows[0]['replacement'] == c.REPLACEMENT
    assert all(row['replacement'] is None for row in rows[1:])
    assert c.LIMITS['automatic_recoveries'] == c.WORKER_CONTRACT['automatic_recoveries'] == 0
    # Mutable consumers cannot silently rewrite future provenance defaults.
    rows[0]['replacement']['terminal_closure']['sha256'] = '0' * 64
    assert c.expected_rows()[0]['replacement'] == c.REPLACEMENT


@pytest.mark.parametrize('fault', ['old_key', 'old_cohort', 'bucket', 'task', 'retry', 'recovery', 'replacement', 'closure'])
def test_admission_and_manifest_reject_noncontract_rows(tmp_path, fault):
    row = c.expected_rows()[0]
    if fault == 'old_key': row['episode_key'] = c.OLD_EPISODE
    if fault == 'old_cohort': row['iteration'] = c.OLD_COHORT
    if fault == 'bucket': row['budget_bucket'] = 'baseline'
    if fault == 'task': row['task_id'] = 1
    if fault == 'retry': row['retry_of'] = c.OLD_EPISODE
    if fault == 'recovery': row['recovery_of'] = c.OLD_EPISODE
    if fault == 'replacement': row['replacement'] = None
    if fault == 'closure': row['replacement']['terminal_closure']['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='exact N34R1'):
        c.pre_dispatch(row, allowance(), now=NOW, stop_path=tmp_path / 'STOP')
    with pytest.raises(ValueError, match='exact fresh N34 matrix'):
        b.command({**plan(), 'episodes': [row]}, {}, row)


@pytest.mark.parametrize('event_index', [0, 1, 2])
@pytest.mark.parametrize('fault', ['bucket', 'replacement', 'retry_of', 'recovery_of', 'old_key', 'old_cohort'])
def test_every_lifecycle_event_binds_accounting_and_provenance(event_index, fault):
    events = journal(c.expected_rows()[:1], True)
    event = events[event_index]
    if fault == 'bucket': event['budget_bucket'] = 'baseline'
    if fault == 'replacement': event['replacement']['old_episode_key'] = 'arbitrary'
    if fault in ('retry_of', 'recovery_of'): event[fault] = c.OLD_EPISODE
    if fault == 'old_key': event['episode_key'] = c.OLD_EPISODE
    if fault == 'old_cohort': event['identity']['iteration'] = c.OLD_COHORT
    with pytest.raises(ValueError):
        s.reconcile(plan(), events, lambda *a: None)


def test_no_replacement_on_any_other_row():
    events = journal(c.expected_rows()[:2], True)
    for event in events[3:]:
        event.update(budget_bucket='recovery', replacement=copy.deepcopy(c.REPLACEMENT))
    with pytest.raises(ValueError, match='accounting/replacement'):
        s.reconcile(plan(), events, lambda *a: None)


@pytest.mark.parametrize('fault', ['duplicate_terminal', 'duplicate_attempt', 'missing_cell'])
def test_duplicate_and_noncontiguous_outcomes_rejected(fault):
    events = journal(c.expected_rows()[:2], True)
    if fault == 'duplicate_terminal': events.append(copy.deepcopy(events[-1]))
    if fault == 'duplicate_attempt': events.extend(copy.deepcopy(events[:3]))
    if fault == 'missing_cell': events = events[3:]
    if fault == 'duplicate_terminal':
        assert s.reconcile(plan(), events, lambda *a: None)['status'] == 'INVALID_STOP'
    else:
        with pytest.raises(ValueError): s.reconcile(plan(), events, lambda *a: None)
    if fault != 'missing_cell':
        with pytest.raises(r.GateError): r.budget_snapshot(events)


def test_exact_accounting_and_old_invalid_is_never_carried(tmp_path):
    old = old_invalid(1800.)
    before = copy.deepcopy(old)
    rows = c.expected_rows()
    events = old + journal(rows, True)
    fresh = r.budget_snapshot(c.cohort_events(rows, events))
    assert fresh['dispatched'] == fresh['valid'] == 30
    assert fresh['by_bucket'] == dict(baseline=9, development=20, recovery=1, validation=0, formal=0)
    total = r.budget_snapshot(events)
    assert total['dispatched'] == 31 and total['invalid'] == 1
    assert total['by_bucket']['baseline'] == 10 and total['by_bucket']['recovery'] == 1
    assert total['gpu_hours_consumed'] == pytest.approx(1830 / 3600)
    assert old == before and events[:3] == before
    assert s.reconcile(plan(), old, lambda *a: None)['next_row'] == rows[0]
    result = s.reconcile(plan(), events, lambda *a: None)
    assert result['status'] == 'COMPLETE' and len(result['outcomes']) == 30
    assert all(o['episode_key'] != c.OLD_EPISODE for o in result['outcomes'])
    assert report.summary(result, events)['charges_and_health_events_preserved'] == events
    p, authority, state, reservations = budget_fixture(tmp_path, old)
    snap = release.admission(p, authority, state, old, [], reservations, rows[0], now=NOW, gpu_idle=True)
    assert snap['invalid'] == 1 and snap['gpu_hours_consumed'] == .5


@pytest.mark.parametrize('fault', ['missing_old', 'old_success', 'old_valid', 'old_bucket', 'authority', 'unauthorized', 'next', 'misbucket'])
def test_real_accounting_admission_rejects_replacement_abuse(tmp_path, fault):
    events = old_invalid(1800.)
    if fault == 'missing_old': events = []
    if fault == 'old_success': events[-1]['success'] = False
    if fault == 'old_valid': events[-1]['outcome_valid'] = True
    if fault == 'old_bucket': events[-1]['budget_bucket'] = 'recovery'
    if fault == 'misbucket':
        events += journal(c.expected_rows()[:1], True)
        events[-1]['budget_bucket'] = 'baseline'
    p, authority, state, reservations = budget_fixture(tmp_path, events)
    if fault == 'authority': authority.pop('prospective_recovery')
    if fault == 'unauthorized': authority['prospective_recovery']['old_episode_key'] = 'other'
    row = c.expected_rows()[1 if fault in ('next', 'misbucket') else 0]
    with pytest.raises((ValueError, r.GateError)):
        release.admission(p, authority, state, events, [], reservations, row, now=NOW, gpu_idle=True)


def test_promotion_and_futility_unchanged():
    rows = c.expected_rows()
    for count in (16, 17):
        assert s.reconcile(plan(), journal(rows[:count]), lambda *a: None)['next_row'] == rows[count]
    assert s.reconcile(plan(), journal(rows[:18]), lambda *a: None)['status'] == 'NUMERIC_FUTILITY'
    for n34_successes, controls, passes in [(5, 5, True), (5, 6, False), (4, 4, False), (10, 10, True)]:
        events = journal(rows, True)
        for event in events:
            identity = event['identity']
            event['success'] = identity['task_id'] < (n34_successes if identity['profile'] == 'N34' else controls)
        result = s.reconcile(plan(), events, lambda *a: None)
        summary = report.summary(result, events)
        assert summary['prospective_dev_necessary_gate_met'] is passes
        assert not summary['validation_authorized'] and not summary['formal_authorized']


def test_shared_runtime_gate_accepts_only_exact_recovery_and_keeps_seed_audit(tmp_path, monkeypatch):
    """Real shared input validator, synthetic file digests for frozen task bytes."""
    rows = c.expected_rows()
    root = tmp_path / 'worktree'
    root.mkdir()
    tasks_path = root / 'configs/qd_ed_final/n31_dev_task_identities.json'
    tasks_path.parent.mkdir(parents=True)
    tasks_path.write_bytes((c.ROOT / 'configs/qd_ed_final/n31_dev_task_identities.json').read_bytes())
    runtime = {'environment': {'LIBERO_CONFIG_PATH': str(tmp_path / 'libero')}, 'tasks': {}}
    hashes = {}
    for row in rows[::3]:
        tid = row['task_id']
        task = {'init_index': 0, 'cache_dir': str(tmp_path / f'cache{tid}'),
                'bddl_path': str(tmp_path / f'task{tid}.bddl'), 'init_path': str(tmp_path / f'init{tid}')}
        runtime['tasks'][str(tid)] = task
        hashes[task['bddl_path']] = row['bddl_sha256']
        hashes[task['init_path']] = row['init_file_sha256']
    digest = r.digest
    monkeypatch.setattr(r, 'digest', lambda path: hashes[str(path)] if str(path) in hashes else digest(path))
    inventory = {'schema': 'qd-ed-runtime-inventory-v1', 'checkpoint': [], 'hf_encoders': [],
                 'dinov2': {'weights': []}, 'libero_tasks': [
                     {'task_id': row['task_id'], 'used_init_index': 0, 'used_init_row_sha256': row['init_row_sha256']}
                     for row in rows[::3]]}
    seeds = {'schema': 'qd-ed-frozen-seed-plan-v1', 'run_name': 'synthetic', 'blocks': {'dev': rows[::3]}}
    p = {'schema': 'n34-released-plan-v1', 'episodes': rows, 'worktree': str(root),
         'run_name': 'synthetic', 'input_contract_label': 'input_repaired'}
    for label, value in [('runtime_inventory', inventory), ('seed_plan', seeds)]:
        path = root / (label + '.json')
        path.write_text(json.dumps(value))
        p[label + '_path'] = str(path)
        p[label + '_sha256'] = digest(path)
    def validate():
        return r.validate_runtime_inputs(p, runtime, {'profiles': {a: {} for a in c.ARMS}}, root,
                                        {'artifacts': str(tmp_path)}, require_frozen=False)
    assert validate() == seeds
    p['episodes'][1]['budget_bucket'] = 'recovery'
    with pytest.raises(ValueError, match='exact N34R1'): validate()
    p['episodes'] = c.expected_rows()
    # The exception does not skip the subsequent frozen seed audit.
    seeds['blocks']['dev'][0]['policy_seed'] += 1
    seed_path = Path(p['seed_plan_path'])
    seed_path.write_text(json.dumps(seeds))
    p['seed_plan_sha256'] = digest(seed_path)
    with pytest.raises(r.GateError, match='policy_seed'): validate()


def test_historical_preparation_costs_global_but_not_new_cohort(tmp_path):
    from test_n34_lifecycle import health
    old = old_invalid()
    resources = health(18000., c.OLD_COHORT)
    for event in resources: event['kind'] = 'n34_resource_preparation_v1'
    p, authority, state, reservations = budget_fixture(tmp_path, old, resources)
    snap = release.admission(p, authority, state, old, resources, reservations,
                             c.expected_rows()[0], now=NOW, gpu_idle=True)
    assert snap['gpu_hours_consumed'] == 5.
    for event in resources: event.update(cohort=c.COHORT, kind='n34r1_resource_preparation_v1')
    with pytest.raises(ValueError, match='cohort_seconds_remaining'):
        release.admission(p, authority, state, old, resources, reservations,
                          c.expected_rows()[0], now=NOW, gpu_idle=True)


def test_all_thirty_admissions_follow_exact_task_major_accounting(tmp_path):
    rows = c.expected_rows()
    events = old_invalid(1800.)
    for index, row in enumerate(rows):
        p, authority, state, reservations = budget_fixture(tmp_path, events)
        snap = release.admission(p, authority, state, events, [], reservations,
                                 row, now=NOW, gpu_idle=True)
        assert snap['dispatched'] == index + 1  # old invalid remains charged
        events.extend(journal([row], True))
    p, authority, state, reservations = budget_fixture(tmp_path, events)
    with pytest.raises(ValueError, match='next fresh contiguous row'):
        release.admission(p, authority, state, events, [], reservations,
                          rows[0], now=NOW, gpu_idle=True)
    assert r.budget_snapshot(events)['by_bucket'] == dict(
        baseline=10, development=20, recovery=1, validation=0, formal=0)
