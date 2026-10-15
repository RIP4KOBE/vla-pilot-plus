"""N22 runtime plumbing uses synthetic outcomes; no GPU/provider/simulator calls."""
import copy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from scripts import qd_ed_final_runner as runner
from scripts import qd_ed_n22_dev_contract as contract


def authority():
    return {'gpu_pool': [7], 'max_concurrent_gpu_workers': 1,
        'resource_isolation': {'status': 'ACTIVE', 'validation_status': 'PASS', 'private_budget': True},
        'budget': {'max_episode_attempts': 438, 'max_gpu_hours': 100.,
                   'amendment': dict(runner.GPU7_N22_AMENDMENT),
                   'reserved': dict(runner.N22_BUCKETS), 'dispatched': 0,
                   'running': 0, 'gpu_hours_consumed': 0.,
                   'gpu_hour_reservations': {'validation': 32., 'formal': 12.}},
        'n22_gpu7_binding': {'scope': contract.COHORT + '_only',
            'selected_gpu': 7, 'user_reply': contract.AUTONOMOUS_REPLY,
            'addendum_path': str(contract.GPU7_ADDENDUM),
            'addendum_sha256': contract.sha(contract.GPU7_ADDENDUM)}}


def reservation():
    return [{'event': 'gpu_hour_reservations_changed',
        'gpu_hour_reservations': {'validation': 32., 'formal': 12.},
        'rationale': 'synthetic reservation', 'time_unix': 1.}]


def module(name, monkeypatch):
    monkeypatch.syspath_prepend(str(runner.ROOT / 'scripts'))
    spec = importlib.util.spec_from_file_location(name + '_test', runner.ROOT / 'scripts' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_exact_original_ten_task_quadruples_and_n21_ablation_routing():
    rows = contract.expected_rows()
    assert len(rows) == 40 and len({row['episode_key'] for row in rows}) == 40
    assert [(r['task_id'], r['profile']) for r in rows] == [(t, a) for t in range(10) for a in contract.ARMS]
    assert sum(r['budget_bucket'] == 'baseline' for r in rows) == 10
    assert sum(r['budget_bucket'] == 'development' for r in rows) == 30
    source = runner.read_json(contract.SOURCE_PLAN)
    seeds = runner.read_json(source['seed_plan_path'])['blocks']['dev']
    for row in rows:
        original = seeds[row['task_id']]
        for key in ('task_id', 'env_seed', 'policy_seed', 'init_index', 'init_row_sha256',
                    'init_file_sha256', 'bddl_sha256'):
            assert row[key] == original[key]
        assert row['split'] == row['seed_block'] == 'dev'
        assert row['timeout_seconds'] == 1800
        assert 'retry_of' not in row
    plan = {'candidate_profiles': {'N21': {}, 'N22': {}}}
    assert runner.is_n22_plan(plan) and not runner.is_n21_plan(plan)
    assert runner.is_n21_plan(source) and not runner.is_n22_plan(source)
    plan['n21_cohort'] = {}  # stale metadata is rejected by N22, not misrouted to N21 scope.
    assert not runner.is_n21_plan(plan)


def test_scope_is_shared_with_runner_and_not_n21():
    support = runner.n22_support()
    plan = {'source_commit': 'synthetic'}
    with support.supervised_scope(plan, runner.ROOT, 'test-cell'):
        support.require_scope(plan, runner.ROOT, vars(runner), {'episode_key': 'test-cell'})
        with pytest.raises(runner.GateError):
            runner.n21_support().require_scope(plan, runner.ROOT, vars(runner))
    with pytest.raises(runner.GateError):
        support.require_scope(plan, runner.ROOT, vars(runner))


@pytest.mark.parametrize('change', ['attempt_cap', 'bucket', 'gpu', 'cohort', 'reply', 'hours', 'reserves', 'old_amendment'])
def test_exact_budget_and_authority_reject_wrong_amendments(change):
    state = authority(); row = contract.expected_rows()[0]
    assert runner.check_budget(state, [], row, reservation_events=reservation()) == 1800
    if change == 'attempt_cap': state['budget']['max_episode_attempts'] = 439
    if change == 'bucket': state['budget']['reserved']['development'] = 158
    if change == 'gpu': state['gpu_pool'] = [3]
    if change == 'cohort': row = {**row, 'iteration': 'N21_STAGE_RAW_DEV_20260930'}
    if change == 'reply': state['n22_gpu7_binding']['user_reply'] = 'different'
    if change == 'hours': state['budget']['max_gpu_hours'] = 101
    if change == 'reserves': state['budget']['gpu_hour_reservations']['formal'] = 11.
    if change == 'old_amendment': state['budget']['amendment'] = dict(runner.GPU7_N21_AMENDMENT)
    with pytest.raises(runner.GateError):
        runner.check_budget(state, [], row, reservation_events=reservation())


def test_local_attempt_hour_cap_and_protected_hours(monkeypatch):
    rows = contract.expected_rows(); plan = {'episodes': rows}; state = authority()
    r = dict(vars(runner))
    r['budget_snapshot'] = lambda *_: {'gpu_hours_consumed': 0., 'gpu_hours_by_bucket': {}}
    contract.protected_budget(state, [], [], rows[0], 1800, r, plan=plan)
    events = [{'identity': {'iteration': contract.COHORT}, 'event': 'dispatched'}] * 40
    with pytest.raises(runner.GateError, match='local dispatch'):
        contract.protected_budget(state, events, [], rows[0], 1800, r, plan=plan)
    events = [{'identity': {'iteration': contract.COHORT}, 'event': 'valid',
               'gpu_process_wall_seconds': 21 * 3600 - 1839}]
    with pytest.raises(runner.GateError, match='local dispatch'):
        contract.protected_budget(state, events, [], rows[0], 1800, r, plan=plan)
    r['budget_snapshot'] = lambda *_: {'gpu_hours_consumed': 56., 'gpu_hours_by_bucket': {}}
    with pytest.raises(runner.GateError, match='protected GPU'):
        contract.protected_budget(state, [], [], rows[0], 1800, r, plan=plan)
    with pytest.raises(runner.GateError, match='timeout'):
        contract.protected_budget(state, [], [], rows[0], 1799, r, plan=plan)


def terminal_prefix(tmp_path, count, successes=()):
    events = []
    for index, row in enumerate(contract.expected_rows()[:count]):
        output = tmp_path / str(index); (output / 'eds_eval').mkdir(parents=True)
        runner.durable_json(output / 'eds_eval/decision-evidence-audit.json', {'accepted': True, 'evidence_complete': True})
        events.append({'identity': runner.episode_identity(row), 'episode_key': row['episode_key'],
                       'event': 'valid', 'outcome_valid': True,
                       'success': row['profile'] == 'N22' and row['task_id'] in successes,
                       'output_dir': str(output)})
    return events


def test_admission_has_no_task0_veto_but_requires_prefix_audits_no_retry_and_futility(tmp_path):
    rows = contract.expected_rows(); plan = {'episodes': rows, 'n22_cohort': {'protocol': {'sha256': 'test'}}}
    events = terminal_prefix(tmp_path, 24)
    assert contract.admission(plan, {}, rows[4], events[:4], [], tmp_path, vars(runner))['n22_cohort_id'] == contract.COHORT
    assert contract.admission(plan, {}, rows[2], events[:2], [], tmp_path, vars(runner))['n22_arm_role'] == 'ablation_control_only'
    with pytest.raises(runner.GateError, match='numeric futility'):
        contract.admission(plan, {}, rows[24], events, [], tmp_path, vars(runner))
    with pytest.raises(runner.GateError, match='cannot be retried'):
        contract.admission(plan, {}, rows[0], events[:1], [], tmp_path, vars(runner))
    with pytest.raises(runner.GateError, match='all be valid'):
        contract.admission(plan, {}, rows[4], events[:3], [], tmp_path, vars(runner))
    bad = copy.deepcopy(events[:4]); bad[1]['outcome_valid'] = False
    with pytest.raises(runner.GateError, match='all be valid'):
        contract.admission(plan, {}, rows[4], bad, [], tmp_path, vars(runner))
    runner.durable_json(Path(events[0]['output_dir']) / 'eds_eval/decision-evidence-audit.json', {'accepted': False, 'evidence_complete': True})
    with pytest.raises(runner.GateError, match='independently audited'):
        contract.admission(plan, {}, rows[4], events[:4], [], tmp_path, vars(runner))


@pytest.mark.parametrize('case,expected_count,expected_status,promoted', [
    ('all_fail', 24, 'rejected_numeric_futility', False),
    ('task0_fail_later_five', 40, 'completed_all_forty_audited', True),
    ('equal_controls', 40, 'completed_all_forty_audited', True),
    ('inferior_control', 40, 'completed_all_forty_audited', False),
    ('zero_bonus', 40, 'completed_all_forty_audited', True),
    ('no_guided', 40, 'completed_all_forty_audited', False),
    ('invalid', 7, 'failed', False),
    ('audit_failure', 4, 'failed', False),
    ('compute_failure', 4, 'failed', False),
    ('inactive_qd', 4, 'failed', False),
])
def test_supervisor_stop_branches_and_no_new_mechanism_veto(
    tmp_path, monkeypatch, case, expected_count, expected_status, promoted,
):
    supervisor = module('qd_ed_n22_dev_supervise', monkeypatch)
    r = supervisor.runner; c = supervisor.contract
    plan = {'source_commit': 'synthetic', 'artifact_root': str(tmp_path), 'episodes': c.expected_rows()}
    monkeypatch.setattr(r, 'validate_plan', lambda *a, **k: (plan, {}, {}))
    monkeypatch.setattr(supervisor, 'release_check', lambda *a: None)
    monkeypatch.setattr(supervisor.queue, 'inventory', lambda: {7: {'uuid': c.GPU7_UUID}})
    monkeypatch.setattr(supervisor.queue, 'reservation_admission', lambda *_: None)
    monkeypatch.setattr(r, 'gpu_admission', lambda **_: None)
    monkeypatch.setattr(r, 'n22_support', lambda: c)
    monkeypatch.setattr(c, 'RUN_DIR', tmp_path / 'variant')
    called = []
    def run(*args, episode_keys, root, **kwargs):
        row = next(x for x in plan['episodes'] if x['episode_key'] == episode_keys[0])
        c.require_scope(plan, root, vars(r), row); called.append(row)
        output = tmp_path / ('attempt' + str(len(called))); (output / 'eds_eval').mkdir(parents=True)
        metric = {'qd_archive_active_for_chunk': not (case == 'inactive_qd' and row['profile'] == 'N22'),
                  'qd_quality_mode': 'close_hold_then_lift_v1' if row['profile'] == 'N22' else 'close_then_lift_v1',
                  'score_call_count': 11, 'search_evaluation_count': 176,
                  'resample_count': 10, 'renoise_count': 10, 'rollout_count': 10}
        (output / 'eds_eval/eds_metrics.jsonl').write_text('' if case == 'no_guided' else json.dumps(metric) + '\n')
        success = False if case == 'all_fail' else row['task_id'] in {1,2,3,4,5} if row['profile'] == 'N22' else (
            row['task_id'] < (6 if case == 'inferior_control' else 5) if case in {'equal_controls','inferior_control'} else False)
        return [{'event': 'valid', 'outcome_valid': not (case == 'invalid' and len(called) == 7),
                 'success': success, 'output_dir': str(output), 'attempt_id': output.name,
                 **{key: 1 for key in supervisor.COST_FIELDS}}]
    monkeypatch.setattr(r, 'run_plan', run)
    def audit(*args):
        arm = called[-1]['profile']
        report = {'accepted': not (case == 'audit_failure' and arm == 'N22'), 'evidence_complete': True}
        if case != 'no_guided':
            report['n22_hold_lift_quality_audit' if arm == 'N22' else 'n18_lift_quality_audit'] = {
                'score_batches_verified': 10 if case == 'compute_failure' and arm == 'N22' else 11,
                'candidate_scores_verified': 176,
                'positive_bonus_candidates': 0 if case == 'zero_bonus' else 1,
                'rank_changed_batches': 0 if case == 'zero_bonus' else 1}
            report['n5_grasp_timing_audit'] = {'checked_decisions': 1, 'parent_rounds_verified': 10}
        return report
    monkeypatch.setattr(supervisor.audit, 'audit_episode', audit)
    status = tmp_path / 'new/status.json'
    monkeypatch.setattr(sys, 'argv', ['supervisor', '--plan', str(tmp_path / 'plan'),
                                    '--release', str(tmp_path / 'release'), '--status', str(status)])
    if expected_status == 'failed':
        with pytest.raises(r.GateError): supervisor.main()
    else: supervisor.main()
    result = r.read_json(status)
    assert result['status'] == expected_status
    assert len(called) == expected_count
    assert result['dev_gate_promoted'] is promoted
    assert result['n21_role'] == 'ablation_control_only_no_promotion'
    assert len({x['episode_key'] for x in called}) == len(called)
    if case == 'all_fail': assert result['maximum_possible_candidate_successes'] == 4
    if case == 'zero_bonus': assert result['candidate_ranking_change_observed'] is False
    with pytest.raises(r.GateError, match='cannot resume'): supervisor.main()


@pytest.mark.parametrize('phase,disposition,state,valid,cause,expected', [
    ('dev', 'rejected', 'rejected_task0_necessary_gate', True, False, True),
    ('dev', 'rejected', 'completed_all_twelve_audited', True, False, True),
    ('dev', 'rejected', 'started', True, False, False),
    ('dev', 'rejected', 'failed', False, False, False),
    ('dev', 'invalid_resolved', 'failed', False, False, False),
    ('dev', 'invalid_resolved', 'failed', False, True, True),
    ('validation', 'rejected', '', True, False, True),
    ('validation', 'invalid_resolved', '', False, True, True),
])
def test_predecessor_review_distinguishes_numeric_rejection_and_resolved_invalid(
    tmp_path, monkeypatch, phase, disposition, state, valid, cause, expected,
):
    source = tmp_path / 'n21-plan.json'; runner.durable_json(source, {'artifact_root': str(tmp_path)})
    status = tmp_path / 'terminal.json'
    payload = ({'status': state, 'dev_gate_promoted': False} if phase == 'dev' else {
        'schema': 'n21-validation-aggregate-disposition-v1', 'cohort_id': 'frozen-n21-validation',
        'aggregate_only': True, 'terminal': True, 'gate_passed': False, 'outcome_valid': valid})
    runner.durable_json(status, payload)
    path = tmp_path / 'review.json'
    review = {'schema': 'n22-n21-prerequisite-v1',
        'source_plan': {'path': str(source), 'sha256': runner.digest(source)},
        'source_status': {'path': str(status), 'sha256': runner.digest(status)},
        'phase': phase, 'disposition': disposition, 'allow_n22': True,
        'cause_resolved': cause, 'rationale': 'synthetic audited root review'}
    runner.durable_json(path, review)
    monkeypatch.setattr(contract, 'SESSION', tmp_path)
    monkeypatch.setattr(contract, 'SOURCE_PLAN', source)
    monkeypatch.setattr(contract, 'PREDECESSOR_REVIEW', path)
    if expected:
        assert contract.predecessor_review(vars(runner)) == {'path': str(path), 'sha256': runner.digest(path)}
        if phase == 'validation':
            payload['per_task_outcomes'] = []
            runner.durable_json(status, payload)
            review['source_status']['sha256'] = runner.digest(status)
            runner.durable_json(path, review)
            with pytest.raises(runner.GateError, match='aggregate'): contract.predecessor_review(vars(runner))
        else:
            payload['dev_gate_promoted'] = True
            runner.durable_json(status, payload)
            with pytest.raises(runner.GateError, match='hash/path'): contract.predecessor_review(vars(runner))
    else:
        with pytest.raises(runner.GateError): contract.predecessor_review(vars(runner))


def test_pure_build_and_full_cohort_contract_without_runtime_dispatch(monkeypatch):
    prepare = module('qd_ed_n22_dev_prepare', monkeypatch)
    r = prepare.runner; c = prepare.contract
    review = {'path': str(c.PREDECESSOR_REVIEW), 'sha256': 'test-review'}
    monkeypatch.setattr(c, 'predecessor_review', lambda *_: review)
    monkeypatch.setattr(prepare, 'committed_record', lambda relative, head: {
        'path': relative, 'sha256': runner.digest(runner.ROOT / relative)})
    monkeypatch.setattr(prepare.queue, 'inventory', lambda: pytest.fail('pure build touched GPU metadata'))
    plan = prepare.build_plan()
    assert len(plan['episodes']) == 40
    assert plan['n22_cohort']['early_stop'] == 'numeric_futility_after_complete_task_quadruple'
    assert plan['n22_cohort']['predecessor_review'] == review
    assert not runner.is_n21_plan(plan) and runner.is_n22_plan(plan)
    assert 'n21_cohort' not in plan and 'n21_gpu7_binding' not in plan
    assert plan['phase_authorization'] == {'dev': True, 'validation': False, 'formal': False}
    base = runner.read_json(plan['profiles_path'])
    manifest = copy.deepcopy(base)
    manifest['profiles'] = {key: manifest['profiles'][key] for key in ('C0', 'Q0')}
    for arm in ('N21', 'N22'):
        candidate = runner.read_json(plan['candidate_profiles'][arm]['path'])
        manifest['profiles'][arm] = r.expand_candidate(arm, candidate, manifest['profiles']['Q0'])
    state = authority()
    runtime = r.read_json(c.GPU7_RUNTIME)
    scope = dict(vars(r)); scope['read_state'] = lambda *_: copy.deepcopy(state)
    c.validate_contract(plan, manifest, runtime, {}, runner.ROOT, scope)
    bad = copy.deepcopy(plan); bad['episodes'][0]['policy_seed'] += 1
    with pytest.raises(r.GateError, match='matched matrix'):
        c.validate_contract(bad, manifest, runtime, {}, runner.ROOT, scope)
    bad = copy.deepcopy(plan); bad['n21_cohort'] = {}
    with pytest.raises(r.GateError, match='matched matrix'):
        c.validate_contract(bad, manifest, runtime, {}, runner.ROOT, scope)
    bad = copy.deepcopy(plan); bad['phase_authorization']['validation'] = True
    with pytest.raises(r.GateError, match='phase gate'):
        c.validate_contract(bad, manifest, runtime, {}, runner.ROOT, scope)
    bad = copy.deepcopy(plan)
    bad['code_files'] = [record for record in bad['code_files'] if record['path'] != 'tests/test_qd_hold_lift_quality.py']
    with pytest.raises(r.GateError, match='fingerprints incomplete'):
        c.validate_contract(bad, manifest, runtime, {}, runner.ROOT, scope)


def test_release_is_exact_and_keeps_protected_phases_closed(tmp_path, monkeypatch):
    supervisor = module('qd_ed_n22_dev_supervise', monkeypatch)
    plan = {'source_commit': 'test', 'episodes': contract.expected_rows()}
    plan_path = tmp_path / 'plan.json'; runner.durable_json(plan_path, plan)
    release = {'schema': 'n22-dev-execution-release-v1', 'plan_path': str(plan_path.resolve()),
        'plan_sha256': runner.digest(plan_path), 'source_commit': 'test',
        'cohort_id': contract.COHORT, 'episode_keys': [r['episode_key'] for r in plan['episodes']],
        'physical_gpu': 7, 'validation_authorized': False, 'formal_authorized': False}
    path = tmp_path / 'release.json'; runner.durable_json(path, release)
    supervisor.release_check(path, plan_path, plan)
    release['formal_authorized'] = True; runner.durable_json(path, release)
    with pytest.raises(supervisor.runner.GateError): supervisor.release_check(path, plan_path, plan)


def test_prepare_rejects_capacity_or_isolation_before_any_gpu_read(tmp_path, monkeypatch):
    prepare = module('qd_ed_n22_dev_prepare', monkeypatch)
    r = prepare.runner
    monkeypatch.setattr(prepare, 'OUTPUT', tmp_path / 'not-frozen.json')
    monkeypatch.setattr(r, 'read_events', lambda *_: [])
    monkeypatch.setattr(prepare.queue, 'inventory', lambda: pytest.fail('rejected state reached GPU metadata'))
    state = authority(); state['budget']['max_episode_attempts'] = 398
    monkeypatch.setattr(r, 'read_state', lambda *_: state)
    with pytest.raises(r.GateError, match='capacity'): prepare.main()
    state = authority(); state['resource_isolation']['status'] = 'HOLD'
    with pytest.raises(r.GateError, match='authority differs'): prepare.main()
