from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import qd_ed_final_report as report


def plan():
    return {'run_name': 'test', 'episodes': [dict(split='dev', iteration='1', profile=p,
            task_id=t, env_seed=100+t, policy_seed=100+t, init_index=0)
            for t in range(2) for p in ['N1', 'C0']]}


def attempt(row, name, success=False, valid=True, infra=False, retry_of=None):
    base = {'attempt_id': name, 'identity': row, 'retry_of': retry_of}
    return [{**base, 'event': 'reserved'}, {**base, 'event': 'dispatched'},
            {**base, 'event': 'aborted' if infra else 'valid', 'success': success,
             'outcome_valid': valid, 'required_cost_telemetry_complete': valid,
             'retryable_infrastructure': infra}]


def test_incomplete_evidence_cannot_shrink_denominator_or_create_comparison():
    p = plan(); rows = p['episodes']
    result = report.summarize(p, attempt(rows[0], 'a', success=True), 'dev', '1')
    assert result['profiles']['N1']['expected'] == 2
    assert result['profiles']['N1']['success_rate'] is None
    assert not result['comparisons']['N1_vs_C0']['matched_and_complete']


def test_algorithm_failure_remains_in_denominator_and_invalidates_safety():
    p = plan(); events = []
    for i, row in enumerate(p['episodes']):
        events += attempt(row, str(i), success=i == 0, valid=i != 2)
    result = report.summarize(p, events, 'dev', '1')
    assert result['profiles']['N1']['success_rate'] == .5
    assert result['profiles']['N1']['failure_count'] == 1
    assert not result['profiles']['N1']['outcome_valid']
    assert result['comparisons']['N1_vs_C0']['success_delta'] == 1


def test_infrastructure_recovery_counts_two_dispatches_but_one_scientific_sample():
    p = plan(); row = p['episodes'][0]
    events = attempt(row, 'a', infra=True) + attempt(row, 'b', success=True, retry_of='a')
    result = report.summarize(p, events, 'dev', '1')
    assert result['profiles']['N1']['success_count'] == 1
    assert result['profiles']['N1']['dispatched_attempts'] == 2
    assert result['samples'][0]['attempt_ids'] == ['a', 'b']


def test_failed_task_cannot_be_replaced_by_a_successful_retry():
    p = plan(); row = p['episodes'][0]
    events = attempt(row, 'a', valid=False) + attempt(row, 'b', success=True, retry_of='a')
    with pytest.raises(report.runner.GateError, match='cannot be replaced'):
        report.summarize(p, events, 'dev', '1')


def test_recovery_without_link_and_mutated_identity_are_rejected():
    p = plan(); row = p['episodes'][0]
    with pytest.raises(report.runner.GateError, match='unlinked'):
        report.summarize(p, attempt(row, 'a', infra=True) + attempt(row, 'b'), 'dev', '1')
    events = attempt(row, 'a')
    events[-1]['identity'] = {**row, 'task_id': 1}
    with pytest.raises(report.runner.GateError, match='identity changed'):
        report.summarize(p, events, 'dev', '1')


def test_unplanned_same_phase_attempt_cannot_be_hidden_from_report():
    p = plan(); row = {**p['episodes'][0], 'env_seed': 999}
    with pytest.raises(report.runner.GateError, match='unplanned scientific sample'):
        report.summarize(p, attempt(row, 'a', success=True), 'dev', '1')
