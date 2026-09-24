"""Independent CPU synthetic counterexamples; no study ledger, GPU or payloads."""
import copy
import sys
from pathlib import Path

import pytest

R4 = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-n4-runner-20260924')
sys.path.insert(0, str(R4 / 'tests'))
from test_qd_ed_n4_plan import fixture, n, r, metric, native_audit, events
from test_qd_ed_n4_report import d, simple_attempt


@pytest.mark.parametrize('defect', ['empty_identity', 'wrong_occurrence', 'zero_prefix'])
def test_original_alignment_counterexamples_rejected(defect):
    audit, m = native_audit(), metric()
    assert n.native_audit_alignment(audit, [m], require=d.require)['status'] == 'verified'
    if defect == 'empty_identity':
        m['qd_terminal_population'] = {}
        m['qd_archive_reference'] = {}
    elif defect == 'wrong_occurrence':
        m['qd_terminal_population']['selected_occurrence_id'] = 'canonical:10:15'
    else:
        audit['n4_terminal_population_audit']['decisions'][0]['actual_prefix_length'] = 0
        audit['n4_terminal_population_audit']['actual_actions_verified'] = 0
    with pytest.raises(ValueError):
        n.native_audit_alignment(audit, [m], require=d.require)


def test_difference_positions_must_match_actual_prefix_not_only_counts():
    audit = native_audit(1, 1)
    gate = audit['n4_terminal_population_audit']
    dec = gate['decisions'][0]
    dec['actual_prefix_length'] = 3
    dec['decoded_reference_first8_diff_positions'] = [[6, 0]]
    dec['decoded_reference_actual_prefix_diff_positions'] = []
    gate.update(actual_actions_verified=3, decoded_reference_actual_prefix_different_decisions=0)
    assert n.native_audit_alignment(audit, [metric()], require=d.require)['actual_prefix_different_decisions'] == 0
    dec['decoded_reference_actual_prefix_diff_positions'] = [[0, 0]]
    gate['decoded_reference_actual_prefix_different_decisions'] = 1
    with pytest.raises(ValueError, match='prefix restriction'):
        n.native_audit_alignment(audit, [metric()], require=d.require)


def test_full_1840_global_headroom_not_only_worker_timeout(monkeypatch):
    snap = {'gpu_hours_consumed': 48 - 24 - 1840 / 3600,
            'gpu_hours_by_bucket': dict.fromkeys(n.ORIGINAL_CAPS, 0.),
            'by_bucket': dict.fromkeys(n.ORIGINAL_CAPS, 0), 'dispatched': 112}
    monkeypatch.setattr(r, 'budget_snapshot', lambda *args: snap)
    state = {'budget': {'reserved': copy.deepcopy(n.ORIGINAL_CAPS),
             'gpu_hour_reservations': {'validation': 14., 'formal': 10.},
             'max_gpu_hours': 48, 'max_episode_attempts': 240}}
    n.protected_budget(state, [], [], {}, 1800, r)
    snap['gpu_hours_consumed'] += 1 / 3600
    with pytest.raises(r.GateError, match='protected 24'):
        n.protected_budget(state, [], [], {}, 1800, r)


def test_new_health_consumes_local_full_1840_headroom(fixture):
    root, plan, _, runtime, _, resources, _ = fixture
    plan['n4_cohort']['health_resources'].append({'resource_id': 'new-proof', 'scope': 'new_n4'})
    resources.append({'resource_id': 'new-proof', 'event': 'completed',
                      'gpu_process_wall_seconds': 8.5 * 3600 - 1840})
    n.admission(plan, runtime, plan['episodes'][0], [], resources, root, r)
    resources[-1]['gpu_process_wall_seconds'] += 1
    with pytest.raises(r.GateError, match='8.5-hour allowance'):
        n.admission(plan, runtime, plan['episodes'][0], [], resources, root, r)


def test_checkpoint_attempt_order_must_match_original_first3(fixture):
    root, plan, _, runtime, _, resources, attest = fixture
    journal = []
    for i, row in enumerate(plan['episodes'][:3]):
        journal += events(plan, runtime, row, 'id' + str(i))
    plan['n4_cohort']['checkpoint_release'] = attest('qd-ed-n4-checkpoint-v1',
        checks=dict.fromkeys(n.CHECKS, True), attempt_ids=['id0', 'id2', 'id1'])
    with pytest.raises(r.GateError, match='attempt linkage'):
        n.admission(plan, runtime, plan['episodes'][3], journal, resources, root, r)
    plan['n4_cohort']['checkpoint_release'] = attest('qd-ed-n4-checkpoint-v1',
        checks=dict.fromkeys(n.CHECKS, True), attempt_ids=['id0', 'id1', 'id2'])
    # All three are ordinary valid failures and no action difference: correctness remains eligible.
    n.admission(plan, runtime, plan['episodes'][3], journal, resources, root, r)


def test_partial_matrix_cannot_use_observed_success_or_activity_to_promote(fixture):
    _, plan, _, runtime, *_ = fixture
    attempts = [simple_attempt(plan, runtime, row, 'a' + str(i), success=True)
                for i, row in enumerate(plan['episodes'])]
    for item in attempts:
        if item['terminal']['identity']['profile'] == 'N4':
            item['metrics']['n4']['actual_prefix_different_decisions'] = 1
    attempts[-1]['status'] = 'pending_audit'
    report = d.summarize(plan, attempts)
    assert report['matrix'] == 'incomplete'
    assert report['protocol_numeric_dev_criterion'] is None
    assert report['protocol_execution_activity_criterion'] is None
    assert report['profiles']['N4']['success_rate'] is None
    assert report['paired_comparisons']['N4_vs_Q0']['success_delta'] is None
    assert report['phase_authorized'] is False
