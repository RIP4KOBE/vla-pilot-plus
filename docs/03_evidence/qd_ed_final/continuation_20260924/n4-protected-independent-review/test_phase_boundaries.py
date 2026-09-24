"""Independent synthetic-only checks for R3 commits 20b0fa7 + 04504d1 + dd15649.

All writable paths are pytest tmp_path. No actual plan/seed/outcome is loaded.
Author fixtures supply inert fake source/runtime and pure report return values;
the new admission, release and budget functions remain real.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest

V = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-n4-evaluation-runner-20260924')
PINNED = {
    'scripts/qd_ed_n4_report.py': 'd26769d73e43e6b10b8171f6930604bc510d15b26174ca3a767bcdf84a72c2fb',
    'scripts/qd_ed_n4_evaluation.py': '4e5ee7e5991870458744ccfa475ed14d5fc326b2719ade6be5c532032885d55e',
    'scripts/qd_ed_n4_evaluate.py': '7b8d470649c0f77eec57f39d4bcb745fd9e73dad385e6b2ff6322fe6abf55ff3',
    'scripts/qd_ed_final_runner.py': 'eefdc47589ac69436562bac52ec774319ecf72c65007c596d25e61f8f42c4ee8',
    'tests/test_qd_ed_n4_evaluation.py': 'bb0e56681e220de106a6f95cd402b19257710951c8b54064106c490fc3fe11ae',
}
for relative, expected in PINNED.items():
    assert hashlib.sha256((V / relative).read_bytes()).hexdigest() == expected
sys.path[:0] = [str(V / 'scripts'), str(V / 'tests')]
import test_qd_ed_n4_evaluation as fixtures
from test_qd_ed_n4_plan import fixture

evaluation = fixtures.evaluation
e, r = fixtures.e, fixtures.r


def recovery_case(evaluation, monkeypatch):
    root, _, _, runtime, _, make, state = evaluation
    plan = make('validation')
    # The complete report is an external adapter dependency, tested separately.
    # Do not fake scope/admission/budget/exposure/recovery logic here.
    monkeypatch.setattr(e, 'reviewed_promotion', lambda *a: None)
    e.allocate(plan, [], root, r)
    original = plan['episodes'][0]
    failed = fixtures.terminal(plan, original, 'eligible-parent')
    old = fixtures.terminal(plan, original, 'old-dev', budget_bucket='development',
                            gpu_process_wall_seconds=37.4 * 3600)
    old['identity'] = {**old['identity'], 'iteration': 'synthetic_prior_dev',
                       'env_seed': 50, 'policy_seed': 50, 'split': 'dev'}
    events = fixtures.group(old) + fixtures.group(failed)
    row = {**original, 'episode_key': 'eligible-recovery', 'budget_bucket': 'recovery',
           'retry_of': failed['attempt_id'], 'n4_evaluation_recovery_contract': e.binding(plan)}
    row['recovery_release'] = fixtures.save(Path(plan['artifact_root']) / 'recovery.json', {
        'schema': 'qd-ed-n4-evaluation-recovery-v1', 'retry_of': failed['attempt_id'],
        'frozen_identity': e.binding(plan),
        'original_terminal': fixtures.save(Path(plan['artifact_root']) / 'failed.json', failed),
    })
    plan['episodes'].append(row)
    (root / 'data/attempt-ledger.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in events))
    snapshot = r.budget_snapshot(events, [])
    state = copy.deepcopy(state)
    state['budget'].update(dispatched=snapshot['dispatched'], gpu_hours_consumed=snapshot['gpu_hours_consumed'])
    monkeypatch.setattr(r, 'n4_evaluation_support', lambda: e)
    return root, plan, runtime, row, events, state


def test_real_scope_own_phase_recovery_exemption_and_raw_costs(evaluation, monkeypatch):
    root, plan, runtime, row, events, state = recovery_case(evaluation, monkeypatch)
    original = copy.deepcopy((events, state))
    with fixtures.owned_scope(root, plan, runtime, [row['episode_key']]):
        permission = e.validated_budget_context(plan, runtime, row, events, [], root, r)
        with pytest.raises(r.GateError, match='termination grace'):
            r.check_budget(state, events, row, physical_gpu=3)
        assert r.check_budget(state, events, row, physical_gpu=3, evaluation_context=permission) == 1800
        e.whole_phase_budget(plan, state, events, [], row, 1800, r)
        assert e.hour_reservation_exclusion(permission, state, events, row, [], [], r) == 'validation'
    assert (events, state) == original
    assert row['budget_bucket'] == 'recovery'
    assert state['budget']['gpu_hour_reservations']['formal'] == 10.


@pytest.mark.parametrize('mutation', ['journal', 'health', 'phase', 'thread_scope'])
def test_permission_cannot_be_reused_for_another_observation(evaluation, monkeypatch, mutation):
    root, plan, runtime, row, events, state = recovery_case(evaluation, monkeypatch)
    with fixtures.owned_scope(root, plan, runtime, [row['episode_key']]):
        permission = e.validated_budget_context(plan, runtime, row, events, [], root, r)
        altered_events, altered_row, resources = copy.deepcopy(events), copy.deepcopy(row), []
        if mutation == 'journal':
            altered_events[-1]['gpu_process_wall_seconds'] += 1.
        elif mutation == 'health':
            resources = [{'resource_id': 'new-resource', 'event': 'reserved'}]
        elif mutation == 'phase':
            altered_row['split'] = 'formal'
        else:
            e._ACTIVE_SCOPE['thread'] += 1
        with pytest.raises(r.GateError, match='row/journal changed|dedicated owned supervisor'):
            e.hour_reservation_exclusion(permission, state, altered_events, altered_row, resources, [], r)


def test_complete_but_numeric_fail_never_produces_release(evaluation, monkeypatch):
    root, plan, events = fixtures.formal_promotion(evaluation, monkeypatch, numeric=False)
    before = copy.deepcopy(events)
    with pytest.raises(r.GateError, match='validation promotion incomplete/numeric failure'):
        e.prepare_reservation_release(plan, events, [], root, r,
            healthcheck_inventory=None, rationale='all sixty accepted', time_unix=1.)
    assert events == before
    assert (root / 'data/gpu-hour-reservation-ledger.jsonl').read_bytes() == b''


def test_complete_pass_cannot_release_unknown_health_cost(evaluation, monkeypatch):
    root, plan, events = fixtures.formal_promotion(evaluation, monkeypatch)
    inventory = fixtures.save(Path(plan['artifact_root']) / 'known-health.json', {
        'schema': 'qd-ed-settled-healthcheck-inventory-v1', 'resources': []})
    health = [{'resource_id': 'not-reviewed', 'event': k, 'gpu_process_wall_seconds': 3.}
              for k in ('reserved', 'dispatched', 'completed')]
    with pytest.raises(r.GateError, match='unrecognized/missing healthchecks'):
        e.prepare_reservation_release(plan, events, health, root, r,
            healthcheck_inventory=inventory, rationale='complete pass', time_unix=1.)
    assert (root / 'data/gpu-hour-reservation-ledger.jsonl').read_bytes() == b''


@pytest.mark.parametrize('registry', ['historical-exposure-inventory.jsonl', 'exposure-registry.jsonl'])
def test_hash_consistent_summary_cannot_hide_old_seed_in_empty_private_ledger(evaluation, monkeypatch, registry):
    root, _, _, _, _, make, _ = evaluation
    plan = make('validation')
    row = plan['episodes'][0]
    old = root / 'data' / registry
    old.write_text(json.dumps({'task_id': row['task_id'], 'episode_seed': row['env_seed']}) + '\n')
    ref = plan['n4_evaluation']['seed_exposure_review']
    review = r.read_json(ref['path'])
    # Keep deliberately false known_seed_intersections=[] but make every hash
    # self-consistent. Semantic raw-history checking must still reject it.
    for item in review['inputs']:
        if item['path'] == str(old):
            item['sha256'] = r.digest(old)
    plan['n4_evaluation']['seed_exposure_review'] = fixtures.save(Path(ref['path']), review)
    monkeypatch.setattr(e, 'SEED_REVIEW_SHA', plan['n4_evaluation']['seed_exposure_review']['sha256'])
    e.verify_seed_metadata(plan, root, r)
    assert (root / 'data/attempt-ledger.jsonl').read_bytes() == b''
    with pytest.raises(r.GateError, match='already exposed in reviewed history'):
        e.check_seed_exposure(plan, [], root, r)
    with pytest.raises(r.GateError, match='already exposed'):
        e.allocate(plan, [], root, r)


@pytest.mark.parametrize('kind', ['episode', 'health'])
def test_no_dispatch_yet_reservation_blocks_preparation_before_seed_read(evaluation, monkeypatch, kind):
    root, _, _, _, _, make, _ = evaluation
    plan = make('validation')
    monkeypatch.setattr(e, 'reviewed_promotion', lambda *a: None)
    events = []
    if kind == 'episode':
        events = [fixtures.group(fixtures.terminal(plan, plan['episodes'][0]))[0]]
    else:
        (root / 'data/gpu-healthcheck-ledger.jsonl').write_text(
            json.dumps({'resource_id': 'inflight', 'event': 'reserved'}) + '\n')
    original_digest = r.digest
    def no_seed_digest(path):
        if str(path) == plan['seed_plan_path']:
            pytest.fail('protected seed reached before all reservations settled')
        return original_digest(path)
    monkeypatch.setattr(r, 'digest', no_seed_digest)
    with pytest.raises(r.GateError, match='unsettled private ' + kind):
        fixtures.launch.prepare(plan, None, events, root, r)


@pytest.mark.parametrize('active', [True, False])
def test_promotion_consumes_frozen_dev_report_actual_nested_schema(evaluation, monkeypatch, active):
    import test_qd_ed_n4_report as old
    root, plan, events, computed, base, attempts = fixtures.promotion(evaluation, monkeypatch)
    runtime = evaluation[3]
    generated = [old.simple_attempt(base, runtime, row, str(i), success=row['profile'] == 'N4')
                 for i, row in enumerate(base['episodes'])]
    for attempt in generated:
        if attempt['terminal']['identity']['profile'] == 'N4':
            attempt['metrics']['qd_active_chunks'] = int(active)
            attempt['metrics']['n4']['actual_prefix_different_decisions'] = 1
    # Actual frozen summarize builds all twelve profile/cell/numeric structures.
    # Only downstream SHA-bound input completeness belongs to the new adapter.
    computed.clear()
    computed.update(old.d.summarize(base, generated), input_scope_complete=True)
    assert computed['profiles']['N4']['valid_cell_observation_summary']['qd_active_chunks'] == 4 * int(active)
    assert 'qd_active_chunks' not in computed['profiles']['N4']
    assert computed['protocol_numeric_dev_criterion'] is True
    assert computed['protocol_execution_activity_criterion'] is True
    attempts[:] = generated
    events[:] = [record for attempt in attempts for record in fixtures.group(attempt['terminal'])]
    certificate = r.read_json(plan['n4_evaluation']['promotion_certificate']['path'])
    review = r.read_json(certificate['review']['path'])
    certificate['report'] = fixtures.save(Path(certificate['report']['path']),
                                         {**computed, 'input_manifest': {'synthetic': True}})
    review['report'] = certificate['report']
    certificate['review'] = fixtures.save(Path(certificate['review']['path']), review)
    plan['n4_evaluation']['promotion_certificate'] = fixtures.save(
        Path(plan['n4_evaluation']['promotion_certificate']['path']), certificate)
    if active:
        e.reviewed_promotion(plan, events, root, r)
    else:
        with pytest.raises(r.GateError, match='lacks substantive native QD'):
            e.reviewed_promotion(plan, events, root, r)
