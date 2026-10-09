"""Prospective N34R10 CPU contract tests; no owning data or release creation."""
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
STALE_CLOSURE = {
    'path': '/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000694/terminal-closure-v1.json',
    'sha256': 'cd6402fe26146565fbb6123888e5d73b2e65311e9c7d99da8a18aae51f23bbf4',
}


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
        assert row['episode_key'] == f'n34r10_dev_t{row["task_id"]:02d}_{row["profile"].lower()}_20261008'
        assert row['iteration'] == c.COHORT
    assert rows[0]['replacement'] == c.REPLACEMENT
    assert all(row['replacement'] is None for row in rows[1:])
    assert c.LIMITS['automatic_recoveries'] == c.WORKER_CONTRACT['automatic_recoveries'] == 0
    # Mutable consumers cannot silently rewrite future provenance defaults.
    rows[0]['replacement']['terminal_closure']['sha256'] = '0' * 64
    assert c.expected_rows()[0]['replacement'] == c.REPLACEMENT


def test_exact_tenth_recovery_authority_binding():
    assert c.COHORT == 'N34R10_OBSERVED_JAW_APPROACH_DEV_20261008'
    assert b.SCIENTIFIC_COMMIT == '71ffff1a0f70d9874b309db9ef1843c02bf17ebf'
    assert c.INVALID_HISTORY == (
        ('n34_dev_t00_c0_20261008', 'N34_OBSERVED_JAW_APPROACH_DEV_20261008', 'baseline'),
        ('n34r1_dev_t00_c0_20261008', 'N34R1_OBSERVED_JAW_APPROACH_DEV_20261008', 'recovery'),
        ('n34r2_dev_t00_c0_20261008', 'N34R2_OBSERVED_JAW_APPROACH_DEV_20261008', 'recovery'),
        ('n34r3_dev_t00_c0_20261008', 'N34R3_OBSERVED_JAW_APPROACH_DEV_20261008', 'recovery'),
        ('n34r4_dev_t00_c0_20261008', 'N34R4_OBSERVED_JAW_APPROACH_DEV_20261008', 'recovery'),
        ('n34r5_dev_t00_c0_20261008', 'N34R5_OBSERVED_JAW_APPROACH_DEV_20261008', 'recovery'),
        ('n34r6_dev_t00_c0_20261008', 'N34R6_OBSERVED_JAW_APPROACH_DEV_20261008', 'recovery'),
        ('n34r7_dev_t00_c0_20261008', 'N34R7_OBSERVED_JAW_APPROACH_DEV_20261008', 'recovery'),
        ('n34r8_dev_t00_c0_20261008', 'N34R8_OBSERVED_JAW_APPROACH_DEV_20261008', 'recovery'),
        ('n34r9_dev_t00_c0_20261008', 'N34R9_OBSERVED_JAW_APPROACH_DEV_20261008', 'recovery'),
    )
    assert c.REPLACEMENT == {
        'old_episode_key': 'n34r9_dev_t00_c0_20261008',
        'new_episode_key': 'n34r10_dev_t00_c0_20261008',
        'budget_bucket': 'recovery', 'automatic': False,
        'terminal_closure': {
            'path': '/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000704/terminal-closure-v1.json',
            'sha256': 'c27a1d6c0a041f3bdd3218525907d6c2b523e84e80076b8b37521113fc62a2f1',
        },
    }


@pytest.mark.parametrize('field', ['path', 'sha256', 'both'])
def test_stale_terminal_closure_rejected_by_rows_events_and_authority(tmp_path, field):
    replacement = copy.deepcopy(c.REPLACEMENT)
    for key in ('path', 'sha256') if field == 'both' else (field,):
        replacement['terminal_closure'][key] = STALE_CLOSURE[key]
    row = c.expected_rows()[0]
    row['replacement'] = replacement
    with pytest.raises(ValueError, match='exact N34R10'):
        c.require_row(row)
    events = journal(c.expected_rows()[:1], True)
    events[-1]['replacement'] = replacement
    with pytest.raises(ValueError, match='accounting/replacement'):
        s.reconcile(plan(), events, lambda *a: None)
    history = old_invalid()
    p, authority, state, reservations = budget_fixture(tmp_path, history)
    authority['prospective_recovery'] = replacement
    with pytest.raises(ValueError, match='explicit root recovery authority'):
        release.admission(p, authority, state, history, [], reservations,
                          c.expected_rows()[0], now=NOW, gpu_idle=True)


@pytest.mark.parametrize('prefix,cohort', [
    ('n34', 'N34_OBSERVED_JAW_APPROACH_DEV_20261008'),
    ('n34r1', 'N34R1_OBSERVED_JAW_APPROACH_DEV_20261008'),
    ('n34r2', 'N34R2_OBSERVED_JAW_APPROACH_DEV_20261008'),
    ('n34r3', 'N34R3_OBSERVED_JAW_APPROACH_DEV_20261008'),
    ('n34r4', 'N34R4_OBSERVED_JAW_APPROACH_DEV_20261008'),
    ('n34r5', 'N34R5_OBSERVED_JAW_APPROACH_DEV_20261008'),
    ('n34r6', 'N34R6_OBSERVED_JAW_APPROACH_DEV_20261008'),
    ('n34r7', 'N34R7_OBSERVED_JAW_APPROACH_DEV_20261008'),
    ('n34r8', 'N34R8_OBSERVED_JAW_APPROACH_DEV_20261008'),
    ('n34r9', 'N34R9_OBSERVED_JAW_APPROACH_DEV_20261008'),
])
@pytest.mark.parametrize('index', range(30))
def test_every_stale_row_rejected(index, prefix, cohort):
    p = plan()
    row = p['episodes'][index]
    row['episode_key'] = row['episode_key'].replace('n34r10_', prefix + '_')
    row['iteration'] = cohort
    with pytest.raises(ValueError, match='exact N34R10'):
        c.require_row(row)
    with pytest.raises(ValueError, match='exact task-major matrix'):
        s.reconcile(p, [], lambda *a: None)


@pytest.mark.parametrize('history_index', range(10))
@pytest.mark.parametrize('fault', ['missing', 'bucket', 'cohort', 'success', 'valid', 'telemetry', 'unknown_cost'])
def test_each_invalid_history_is_required_and_never_repaired(history_index, fault):
    events = old_invalid(900.)
    start = history_index * 3
    terminal = events[start + 2]
    if fault == 'missing': del events[start:start + 3]
    if fault == 'bucket': terminal['budget_bucket'] = 'development'
    if fault == 'cohort': terminal['identity'] = {'iteration': c.COHORT}
    if fault == 'success': terminal['success'] = False
    if fault == 'valid': terminal['outcome_valid'] = True
    if fault == 'telemetry': terminal['required_cost_telemetry_complete'] = True
    if fault == 'unknown_cost': terminal['gpu_process_wall_seconds'] = None
    before = copy.deepcopy(events)
    with pytest.raises(ValueError):
        c.require_replacement_history(events)
    assert events == before


@pytest.mark.parametrize('fault,reason', [
    ('identity', 'generic terminal identity/cost'),
    ('episode_key', 'generic terminal identity/cost'),
    ('attempt_id', 'generic terminal identity/cost'),
    ('replacement', 'accounting/replacement'),
    ('context', 'terminal context binding'),
    ('none', 'process context/release binding'),
])
def test_parent_terminal_rejects_stale_n34r9_bindings(tmp_path, monkeypatch, fault, reason):
    from scripts import qd_ed_n34_worker as worker
    from test_n34_production_integration import write
    row = c.expected_rows()[0]
    plan_ref, release_ref = {'sha256': 'a' * 64}, {'sha256': 'b' * 64}
    p = {'source': {'commit': 'c' * 40}, 'runtime': {'sha256': 'd' * 64},
         'runtime_inventory_sha256': 'e' * 64,
         'expected_manifests': {row['episode_key']: write(tmp_path / 'manifest.json',
                                                       {'output_dir': str(tmp_path)})}}
    monkeypatch.setattr(release, 'validate_release', lambda *a: (p, {}, {}))
    context = {'plan': plan_ref, 'release': release_ref, 'episode_key': row['episode_key']}
    if fault == 'context': context['episode_key'] = c.OLD_EPISODE
    context_ref = write(tmp_path / 'n34-worker-context.json', context)
    # An empty process binding deliberately stops the valid identity case before
    # receipt/native audits; stale identities must fail earlier in the parent.
    write(tmp_path / 'process.json', {})
    terminal = journal([row], True)[-1]
    terminal.update(source_commit=p['source']['commit'], plan_sha256=plan_ref['sha256'],
                    runtime_manifest_sha256=p['runtime']['sha256'], init_row_sha256=row['init_row_sha256'],
                    physical_gpu=7, output_dir=str(tmp_path), context=context_ref,
                    release=release_ref, runtime_inventory_sha256=p['runtime_inventory_sha256'])
    if fault == 'identity': terminal['identity']['iteration'] = c.OLD_COHORT
    if fault in ('episode_key', 'attempt_id'): terminal[fault] = c.OLD_EPISODE
    if fault == 'replacement': terminal['replacement']['terminal_closure'] = STALE_CLOSURE
    with pytest.raises(ValueError, match=reason):
        worker.verify_terminal(plan_ref, row, terminal, release_ref)


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
    with pytest.raises(ValueError, match='exact N34R10'):
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
    assert total['dispatched'] == 40 and total['invalid'] == 10
    assert total['by_bucket']['baseline'] == 10 and total['by_bucket']['recovery'] == 10
    assert total['gpu_hours_consumed'] == pytest.approx(18030 / 3600)
    assert old == before and events[:30] == before
    assert s.reconcile(plan(), old, lambda *a: None)['next_row'] == rows[0]
    result = s.reconcile(plan(), events, lambda *a: None)
    assert result['status'] == 'COMPLETE' and len(result['outcomes']) == 30
    assert all(o['episode_key'] not in {h[0] for h in c.INVALID_HISTORY} for o in result['outcomes'])
    assert report.summary(result, events)['charges_and_health_events_preserved'] == events
    p, authority, state, reservations = budget_fixture(tmp_path, old)
    snap = release.admission(p, authority, state, old, [], reservations, rows[0], now=NOW, gpu_idle=True)
    assert snap['invalid'] == 10 and snap['gpu_hours_consumed'] == 5.0


@pytest.mark.parametrize('fault', ['missing_old', 'old_success', 'old_valid', 'old_bucket', 'authority', 'unauthorized', 'next', 'misbucket'])
def test_real_accounting_admission_rejects_replacement_abuse(tmp_path, fault):
    events = old_invalid(1800.)
    if fault == 'missing_old': events = []
    if fault == 'old_success': events[-1]['success'] = False
    if fault == 'old_valid': events[-1]['outcome_valid'] = True
    if fault == 'old_bucket': events[-1]['budget_bucket'] = 'baseline'
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
    with pytest.raises(ValueError, match='exact N34R10'): validate()
    p['episodes'] = c.expected_rows()
    # The exception does not skip the subsequent frozen seed audit.
    seeds['blocks']['dev'][0]['policy_seed'] += 1
    seed_path = Path(p['seed_plan_path'])
    seed_path.write_text(json.dumps(seeds))
    p['seed_plan_sha256'] = digest(seed_path)
    with pytest.raises(r.GateError, match='policy_seed'): validate()


@pytest.mark.parametrize('cohort,kind', [
    ('N34_OBSERVED_JAW_APPROACH_DEV_20261008', 'n34_resource_preparation_v1'),
    ('N34R1_OBSERVED_JAW_APPROACH_DEV_20261008', 'n34r1_resource_preparation_v1'),
    ('N34R2_OBSERVED_JAW_APPROACH_DEV_20261008', 'n34r2_resource_preparation_v1'),
    ('N34R3_OBSERVED_JAW_APPROACH_DEV_20261008', 'n34r3_resource_preparation_v1'),
    ('N34R4_OBSERVED_JAW_APPROACH_DEV_20261008', 'n34r4_resource_preparation_v1'),
    ('N34R5_OBSERVED_JAW_APPROACH_DEV_20261008', 'n34r5_resource_preparation_v1'),
    ('N34R6_OBSERVED_JAW_APPROACH_DEV_20261008', 'n34r6_resource_preparation_v1'),
    ('N34R7_OBSERVED_JAW_APPROACH_DEV_20261008', 'n34r7_resource_preparation_v1'),
    ('N34R8_OBSERVED_JAW_APPROACH_DEV_20261008', 'n34r8_resource_preparation_v1'),
    ('N34R9_OBSERVED_JAW_APPROACH_DEV_20261008', 'n34r9_resource_preparation_v1'),
])
@pytest.mark.parametrize('tag', ['cohort', 'kind', 'both'])
def test_historical_preparation_costs_global_but_not_new_cohort(tmp_path, cohort, kind, tag):
    from test_n34_lifecycle import health
    old = old_invalid()
    resources = health(18000., cohort)
    for event in resources: event['kind'] = kind
    p, authority, state, reservations = budget_fixture(tmp_path, old, resources)
    snap = release.admission(p, authority, state, old, resources, reservations,
                             c.expected_rows()[0], now=NOW, gpu_idle=True)
    assert snap['gpu_hours_consumed'] == 5.
    for event in resources:
        if tag in ('cohort', 'both'): event['cohort'] = c.COHORT
        if tag in ('kind', 'both'): event['kind'] = 'n34r10_resource_preparation_v1'
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
        assert snap['dispatched'] == index + 10  # all ten old invalids remain charged
        events.extend(journal([row], True))
    p, authority, state, reservations = budget_fixture(tmp_path, events)
    with pytest.raises(ValueError, match='next fresh contiguous row'):
        release.admission(p, authority, state, events, [], reservations,
                          rows[0], now=NOW, gpu_idle=True)
    assert r.budget_snapshot(events)['by_bucket'] == dict(
        baseline=10, development=20, recovery=10, validation=0, formal=0)


@pytest.mark.parametrize('history_index,reason', [
    (3, 'missing torch.utils.serialization runtime coverage'),
    (4, 'missing lazy OpenGL conversion-handler runtime coverage'),
    (5, 'missing lazy OpenGL conversion-handler runtime coverage'),
    (6, 'missing lazy Numba JIT dependency runtime coverage'),
    (7, 'missing lazy SentencePiece protobuf runtime coverage'),
    (8, 'unbound DINOv2 dynamic imports'),
    (9, 'unbound PIL._imagingmath runtime dependency'),
])
def test_computed_control_remains_invalid_unknown_and_charged(tmp_path, history_index, reason):
    events = old_invalid(900.)
    events[history_index * 3 + 2].update(
        computed_success=True,
        invalid_reason=reason,
        http_counters='Unknown',
    )
    before = copy.deepcopy(events)
    c.require_replacement_history(events)
    result = s.reconcile(plan(), events, lambda *a: pytest.fail('historical result reused'))
    summary = report.summary(result, events)
    assert result['outcomes'] == [] and result['next_row'] == c.expected_rows()[0]
    assert summary['matrix'][0] == {'task_id': 0, 'C0': 'Unknown', 'Q0': 'Unknown', 'N34': 'Unknown'}
    assert summary['http_counters'] == 'Unknown'
    assert summary['prospective_dev_necessary_gate_met'] is False
    assert summary['charges_and_health_events_preserved'] == before
    p, authority, state, reservations = budget_fixture(tmp_path, events)
    snap = release.admission(p, authority, state, events, [], reservations,
                             c.expected_rows()[0], now=NOW, gpu_idle=True)
    assert snap['invalid'] == 10 and snap['valid'] == 0
    assert snap['gpu_hours_consumed'] == 2.5
    assert events == before


@pytest.mark.parametrize('control', ['C0', 'Q0'])
def test_promotion_must_match_each_control_independently(control):
    events = journal(c.expected_rows(), True)
    for event in events:
        identity = event['identity']
        event['success'] = identity['task_id'] < (6 if identity['profile'] == control else 5)
    result = s.reconcile(plan(), events, lambda *a: None)
    assert result['status'] == 'COMPLETE'
    assert report.summary(result, events)['prospective_dev_necessary_gate_met'] is False


@pytest.mark.parametrize('index', range(30))
@pytest.mark.parametrize('fault', ['bucket', 'replacement'])
def test_every_cell_enforces_exact_bucket_and_replacement(index, fault):
    row = c.expected_rows()[index]
    if fault == 'bucket':
        row['budget_bucket'] = 'baseline' if index == 0 else 'recovery'
    else:
        row['replacement'] = None if index == 0 else copy.deepcopy(c.REPLACEMENT)
    with pytest.raises(ValueError, match='exact N34R10'):
        c.require_row(row)
    events = journal(c.expected_rows()[:index + 1], True)
    events[-1][fault if fault == 'replacement' else 'budget_bucket'] = row[
        fault if fault == 'replacement' else 'budget_bucket']
    with pytest.raises(ValueError, match='accounting/replacement'):
        s.reconcile(plan(), events, lambda *a: None)


@pytest.mark.parametrize('end', ['valid', 'aborted'])
def test_all_invalid_costs_and_unknowns_retained_without_rewriting(end):
    events = old_invalid()
    for index in range(10):
        terminal = events[index * 3 + 2]
        terminal.update(event=end, gpu_process_wall_seconds=100. + index,
                        computed_success=True, http_counters='Unknown',
                        cost_detail={'unknown_fields': ['provider_tokens'], 'attempt': index})
    before = copy.deepcopy(events)
    c.require_replacement_history(events)
    snap = r.budget_snapshot(events)
    assert snap['dispatched'] == 10 and snap['valid'] == 0
    assert snap['invalid'] == (10 if end == 'valid' else 0)
    assert snap['aborted'] == (10 if end == 'aborted' else 0)
    assert snap['gpu_hours_consumed'] == pytest.approx(sum(range(100, 110)) / 3600)
    assert snap['gpu_hours_by_bucket']['baseline'] == pytest.approx(100 / 3600)
    assert snap['gpu_hours_by_bucket']['recovery'] == pytest.approx(sum(range(101, 110)) / 3600)
    result = s.reconcile(plan(), events, lambda *a: pytest.fail('invalid history reused'))
    summary = report.summary(result, events)
    assert result['outcomes'] == [] and result['next_row'] == c.expected_rows()[0]
    assert summary['charges_and_health_events_preserved'] == before == events
    assert summary['prospective_dev_necessary_gate_met'] is False


def test_invalid_sixth_triple_cannot_trigger_numeric_futility_or_retry():
    events = journal(c.expected_rows()[:18])
    events[-1].update(outcome_valid=False, success=None,
                      required_cost_telemetry_complete=False)
    result = s.reconcile(plan(), events, lambda *a: None)
    assert result['status'] == 'INVALID_STOP' and result['next_row'] is None
    assert len(result['outcomes']) == 17
    summary = report.summary(result, events)
    assert summary['automatic_recoveries'] == 0
    assert summary['matrix'][5]['N34'] == 'Unknown'
    assert summary['prospective_dev_necessary_gate_met'] is False
