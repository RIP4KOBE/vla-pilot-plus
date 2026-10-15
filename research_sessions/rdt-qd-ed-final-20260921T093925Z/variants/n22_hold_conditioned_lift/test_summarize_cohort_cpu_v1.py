import copy
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('n22_report', Path(__file__).with_name('summarize_cohort_cpu_v1.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture(tasks=10, wins=None):
    wins = wins or {'N22': {0, 1, 2, 3, 4}}
    rows = [dict(task_id=t, profile=a, episode_key=f'{t}/{a}') for t in range(10) for a in m.ARMS]
    events, completed = [], []
    for row in rows[:tasks * 4]:
        event = dict(identity=dict(row, iteration=m.COHORT), episode_key=row['episode_key'],
                     attempt_id=row['episode_key'], **{k: 1 for k in m.COST_FIELDS})
        events.append(dict(event, event='dispatched'))
        events.append(dict(event, event='valid', outcome_valid=True,
                           required_cost_telemetry_complete=True, provider_token_usage_complete=True,
                           provider_usage_complete_calls=1,
                           success=row['task_id'] in wins.get(row['profile'], set())))
        completed.append(row['episode_key'])
    successes = {a: sum(t in wins.get(a, set()) for t in range(tasks)) for a in m.ARMS}
    promoted = tasks == 10 and successes['N22'] >= 5 and successes['N22'] >= max(successes[a] for a in m.ARMS[:-1])
    status = dict(status='completed_all_forty_audited' if tasks == 10 else 'rejected_numeric_futility',
                  completed_keys=completed, successes=successes, dev_gate_promoted=promoted,
                  maximum_possible_candidate_successes=successes['N22'] + 10 - tasks,
                  native={'N22': {'guided_decisions': tasks, 'parent_rounds_verified': 10 * tasks}},
                  cost_totals={a: {k: tasks for k in m.COST_FIELDS} for a in m.ARMS})
    return {'episodes': rows}, status, events


def audit(item):
    return {'accepted': True, 'evidence_complete': True}, {'path': 'fixture-only', 'sha256': 'fixture-only'}


def test_full_promotion_and_matched_comparison():
    data = fixture(wins={'N22': {0, 1, 2, 3, 4}, 'C0': {1, 2, 5}})
    out = m.analyze(*data, audit)
    assert out['decision'] == 'ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION'
    assert out['matched_task_comparisons']['C0']['gained'] == [0, 3, 4]
    assert out['matched_task_comparisons']['C0']['lost'] == [5]
    assert out['counts']['N22'] == {'audited': 10, 'success': 5}


def test_full_candidate_worse_than_control_rejected():
    assert m.analyze(*fixture(wins={'N22': set(range(5)), 'C0': set(range(6))}), audit)['decision'] == 'REJECT'


def test_numeric_futility_has_partial_denominators():
    out = m.analyze(*fixture(tasks=6, wins={'N22': set()}), audit)
    assert out['decision'] == 'REJECT'
    assert out['counts']['N22'] == {'audited': 6, 'success': 0}
    assert len(out['rows']) == 24


def test_no_premature_futility():
    with pytest.raises(ValueError, match='futility'):
        m.analyze(*fixture(tasks=5, wins={'N22': set()}), audit)


def test_running_cohort_never_reported():
    plan, status, events = fixture()
    status['status'] = 'cell_audited'
    with pytest.raises(ValueError, match='not terminal'):
        m.analyze(plan, status, events, audit)


def test_unsettled_attempt_never_reported():
    plan, status, events = fixture()
    with pytest.raises(ValueError, match='unsettled'):
        m.analyze(plan, status, events[:-1], audit)


def test_duplicate_not_hidden_by_dictionary():
    plan, status, events = fixture()
    with pytest.raises(ValueError, match='duplicate'):
        m.analyze(plan, status, events + [copy.deepcopy(events[-1])], audit)


def test_native_invalid_cannot_be_completed():
    plan, status, events = fixture()
    with pytest.raises(ValueError, match='native evidence'):
        m.analyze(plan, status, events, lambda x: ({'accepted': False}, None))


def test_cost_mismatch_not_silently_pooled():
    plan, status, events = fixture()
    events[-1]['gpu_process_wall_seconds'] = 99
    with pytest.raises(ValueError, match='cost totals'):
        m.analyze(plan, status, events, audit)


def test_promotion_flag_cannot_override_arithmetic():
    plan, status, events = fixture(wins={'N22': {0}})
    status['dev_gate_promoted'] = True
    with pytest.raises(ValueError, match='promotion conflicts'):
        m.analyze(plan, status, events, audit)


def test_timeout_unknown_tokens_remain_partial_and_invalid():
    plan, status, events = fixture(tasks=4, wins={'N22': set()})
    status.update(status='failed', dev_gate_promoted=False)
    row = plan['episodes'][16]
    event = dict(identity=dict(row, iteration=m.COHORT), episode_key=row['episode_key'],
                 attempt_id=row['episode_key'], **{k: 1 for k in m.COST_FIELDS})
    events.extend([dict(event, event='dispatched'), dict(event, event='valid',
                   outcome_valid=False, success=False, required_cost_telemetry_complete=False,
                   provider_token_usage_complete=False, provider_usage_complete_calls=0)])
    status['attempted_keys'] = status['completed_keys'][:]
    out = m.analyze(plan, status, events, audit)
    assert out['decision'] == 'INVALID_OR_INTERRUPTED'
    assert out['audited_cells'] == 16 and out['dispatched'] == 17
    assert out['provider_token_aggregate_status'] == 'partial_or_unknown'
    assert out['incomplete_token_usage_attempts'] == [{'attempt_id': row['episode_key'], 'unknown_token_calls': 1}]
    assert out['cost_totals']['C0']['provider_input_tokens'] == 5
    assert out['rows'][-1]['required_cost_telemetry_complete'] is False
    assert out['charged_attempts_not_returned_to_supervisor'] == [row['episode_key']]
    assert out['gpu_process_wall_seconds'] == 17
