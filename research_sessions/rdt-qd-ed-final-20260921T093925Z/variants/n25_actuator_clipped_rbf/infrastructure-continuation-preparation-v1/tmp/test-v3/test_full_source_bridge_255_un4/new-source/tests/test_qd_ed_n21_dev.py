"""N21 CPU-only authorization and stop gates; never touches a GPU or provider."""
import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from scripts import qd_ed_final_runner as runner
from scripts import qd_ed_n21_dev_contract as contract


def test_n21_preserves_scientific_profile_and_matched_identities():
    source = runner.read_json(contract.SOURCE_PLAN)
    baseline = runner.read_json(source['profiles_path'])['profiles']['Q0']
    n20 = runner.read_json(runner.ROOT / 'configs/qd_ed_final/candidate_n20.json')
    n21 = runner.read_json(runner.ROOT / 'configs/qd_ed_final/candidate_n21.json')
    assert n20['profile'] == n21['profile']
    assert runner.expand_candidate('N21', n21, baseline)['resolved_eds_config'] == runner.expand_candidate('N20', n20, baseline)['resolved_eds_config']
    rows = contract.expected_rows()
    assert len(rows) == 12 and len({r['episode_key'] for r in rows}) == 12
    assert [(r['task_id'], r['profile']) for r in rows] == [(t, a) for t in contract.TASKS for a in contract.ARMS]
    for task in contract.TASKS:
        group = [r for r in rows if r['task_id'] == task]
        assert len({(r['env_seed'], r['policy_seed'], r['init_index'], r['init_row_sha256']) for r in group}) == 1


def test_n21_budget_rejects_old_authority_and_requires_exact_amendment():
    state = {'gpu_pool': [7], 'max_concurrent_gpu_workers': 1,
        'budget': {'max_episode_attempts': 395, 'max_gpu_hours': 100.,
                   'amendment': dict(runner.GPU7_N20_AMENDMENT),
                   'reserved': dict(runner.N20_BUCKETS), 'dispatched': 0,
                   'running': 0, 'gpu_hours_consumed': 0.,
                   'gpu_hour_reservations': {'validation': 32., 'formal': 12.}}}
    row = contract.expected_rows()[0]
    reservations = [{'event': 'gpu_hour_reservations_changed',
        'gpu_hour_reservations': {'validation': 32., 'formal': 12.},
        'rationale': 'synthetic approved reservation', 'time_unix': 1.}]
    with pytest.raises(runner.GateError):
        runner.check_budget(state, [], row, reservation_events=reservations)
    state['budget'].update(max_episode_attempts=398, amendment=dict(runner.GPU7_N21_AMENDMENT), reserved=dict(runner.N21_BUCKETS))
    state['n21_gpu7_binding'] = {'scope': contract.COHORT + '_only',
        'selected_gpu': 7, 'user_reply': '允许改用其他空闲 GPU'}
    assert runner.check_budget(state, [], row, reservation_events=reservations) == 1800
    bad = copy.deepcopy(state); bad['budget']['max_episode_attempts'] = 399
    with pytest.raises(runner.GateError):
        runner.check_budget(bad, [], row, reservation_events=reservations)
    bad = copy.deepcopy(state); bad['budget']['reserved']['development'] += 1
    with pytest.raises(runner.GateError):
        runner.check_budget(bad, [], row, reservation_events=reservations)


@pytest.mark.parametrize('task0_success,audit_ok,expected', [
    (False, True, 'rejected_task0_necessary_gate'),
    (True, True, 'completed_all_twelve_audited'),
    (True, False, 'failed'),
])
def test_n21_supervisor_stops_after_task0_failure_or_invalid_audit(
    tmp_path, monkeypatch, task0_success, audit_ok, expected,
):
    monkeypatch.syspath_prepend(str(runner.ROOT / 'scripts'))
    spec = importlib.util.spec_from_file_location('n21_test_supervisor', runner.ROOT / 'scripts/qd_ed_n21_dev_supervise.py')
    supervisor = importlib.util.module_from_spec(spec); spec.loader.exec_module(supervisor)
    r = supervisor.runner; c = supervisor.contract
    plan = {'source_commit': 'synthetic', 'artifact_root': str(tmp_path),
            'episodes': c.expected_rows()}
    monkeypatch.setattr(r, 'validate_plan', lambda *a, **k: (plan, {}, {}))
    monkeypatch.setattr(supervisor, 'release_check', lambda *a: None)
    monkeypatch.setattr(supervisor.queue, 'inventory', lambda: {7: {'uuid': 'test'}})
    monkeypatch.setattr(supervisor.queue, 'reservation_admission', lambda *_: None)
    monkeypatch.setattr(r, 'gpu_admission', lambda **_: None)
    monkeypatch.setattr(r, 'n21_support', lambda: c)
    monkeypatch.setattr(c, 'RUN_DIR', tmp_path / 'variant')
    called = []
    def run(*args, episode_keys, root, **kwargs):
        row = next(x for x in plan['episodes'] if x['episode_key'] == episode_keys[0])
        c.require_scope(plan, root, vars(r), row)
        called.append(row)
        output = tmp_path / ('attempt' + str(len(called)))
        (output / 'eds_eval').mkdir(parents=True)
        (output / 'eds_eval/eds_metrics.jsonl').write_text('{}\n')
        success = row['profile'] == 'N21' and (task0_success if row['task_id'] == 0 else True)
        return [{'event': 'valid', 'outcome_valid': True, 'success': success,
                 'output_dir': str(output), 'attempt_id': output.name}]
    monkeypatch.setattr(r, 'run_plan', run)
    def audit(*args):
        return {'accepted': audit_ok or called[-1]['profile'] != 'N21', 'evidence_complete': True,
                'n18_lift_quality_audit': {'score_batches_verified': 11, 'candidate_scores_verified': 176,
                    'positive_bonus_candidates': 1, 'rank_changed_batches': 1},
                'n5_grasp_timing_audit': {'checked_decisions': 1}}
    monkeypatch.setattr(supervisor.audit, 'audit_episode', audit)
    status = tmp_path / 'new/status.json'
    monkeypatch.setattr(sys, 'argv', ['supervisor', '--plan', str(tmp_path / 'plan'),
                                    '--release', str(tmp_path / 'release'), '--status', str(status)])
    if audit_ok:
        supervisor.main()
    else:
        with pytest.raises(r.GateError, match='native evidence failed'):
            supervisor.main()
    result = r.read_json(status)
    assert result['status'] == expected
    assert len(called) == (12 if task0_success and audit_ok else 3)
    assert len({x['episode_key'] for x in called}) == len(called)
    assert result.get('dev_gate_promoted', False) is (task0_success and audit_ok)


def test_n21_direct_later_task_admission_requires_task0_success_and_audit(tmp_path):
    rows = contract.expected_rows()
    plan = {'episodes': rows, 'n21_cohort': {'protocol': {'sha256': 'test'}}}
    events = []
    for index, row in enumerate(rows[:3]):
        output = tmp_path / str(index); (output / 'eds_eval').mkdir(parents=True)
        runner.durable_json(output / 'eds_eval/decision-evidence-audit.json', {'accepted': True, 'evidence_complete': True})
        events.append({'episode_key': row['episode_key'], 'event': 'valid', 'outcome_valid': True,
                       'success': False, 'output_dir': str(output)})
    with pytest.raises(runner.GateError, match='task0 failure'):
        contract.admission(plan, {}, rows[3], events, [], tmp_path, vars(runner))
    events[-1]['success'] = True
    assert contract.admission(plan, {}, rows[3], events, [], tmp_path, vars(runner))['n21_cohort_id'] == contract.COHORT
    runner.durable_json(Path(events[-1]['output_dir']) / 'eds_eval/decision-evidence-audit.json', {'accepted': False, 'evidence_complete': True})
    with pytest.raises(runner.GateError, match='audited task0'):
        contract.admission(plan, {}, rows[3], events, [], tmp_path, vars(runner))
