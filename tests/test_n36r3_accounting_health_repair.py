"""Turn 001445 CPU fixtures only; no real owner, provider or readiness evidence."""
import copy
import json
import math
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from scripts import qd_ed_n36r3_admission as gate
from scripts import qd_ed_n36r3_preparation as prep
from scripts import qd_ed_n36r3_health as health
from scripts import qd_ed_n36_accounting as accounting
from scripts import qd_ed_n36_contract as c
from scripts import qd_ed_final_runner as r

EARLIER_ID = 'n36_healthcheck_n36r3_preparation_001314'
OLD_ID = 'n36_healthcheck_n36r3_preparation_001426'
NEW_ID = 'n36_healthcheck_n36r3_preparation_001445'
RETAINED = 75.53335346582918


@pytest.fixture
def case(tmp_path, monkeypatch):
    owner = tmp_path / 'owner'
    source = tmp_path / 'source'
    (owner / 'data').mkdir(parents=True)
    source.mkdir()
    config = 'configs/qd_ed_final/n31_dev_task_identities.json'
    (source / config).parent.mkdir(parents=True)
    (source / config).write_bytes((c.ROOT / config).read_bytes())
    monkeypatch.setattr(gate, 'OWNER', owner)
    monkeypatch.setattr(gate, 'SOURCE', source)

    def put(name, value):
        path = tmp_path / (name + '.json')
        path.write_text(json.dumps(value))
        return c.ref(path)

    events = []
    for i in range(505):
        saved = gate.previous.draft.PRESERVED[i] if i < 2 else None
        key = saved['attempt_id'] if saved else f'synthetic_{i}'
        seconds = saved['gpu_seconds'] if saved else 0.
        if i == 504:
            seconds = (75.52725286641478 - r.budget_snapshot(events)['gpu_hours_consumed']) * 3600
        base = {'attempt_id': key, 'episode_key': key,
                'budget_bucket': 'baseline' if i < 100 else 'development' if i < 500 else 'recovery'}
        events.extend([{**base, 'event': 'reserved'}, {**base, 'event': 'dispatched'},
                       {**base, 'event': 'aborted', 'gpu_process_wall_seconds': seconds}])
    resources = [{'resource_id': identity, 'event': event,
                  'gpu_process_wall_seconds': seconds}
                 for identity, seconds, terminal in [
                     (EARLIER_ID, .00305887314245 * 3600, 'aborted'),
                     (OLD_ID, 10.950214579002932, 'completed')]
                 for event in ('reserved', 'dispatched', terminal)]
    rows = {'attempt-ledger.jsonl': events, 'gpu-healthcheck-ledger.jsonl': resources,
            'gpu-hour-reservation-ledger.jsonl': []}
    anchors = {}
    for name, records in rows.items():
        path = owner / 'data' / name
        path.write_text(''.join(json.dumps(row) + '\n' for row in records))
        anchors[name] = prep.bound(path)
    snapshot = r.budget_snapshot(events, resources)
    assert snapshot['gpu_hours_consumed'] == RETAINED
    plan = {key: {'synthetic': key} for key in gate.BINDINGS}
    plan.update(cohort=c.DRAFT_N36R3_COHORT, worktree=str(source),
                episodes=c.expected_rows(cohort=c.DRAFT_N36R3_COHORT),
                source={'commit': 'synthetic-source'}, runtime={'synthetic': 'runtime'},
                resource_routing={'source_cwd': str(source), 'owner_root': str(owner),
                                  'physical_gpu': 7, 'gpu_uuid': c.GPU_UUID})
    plan['accounting'] = put('ledger', {'retained_ledger_prefix': anchors['attempt-ledger.jsonl'],
        'retained_health_ledger_prefix': anchors['gpu-healthcheck-ledger.jsonl']})
    monkeypatch.setattr(c, 'validate_n36r3_protocol', lambda p: {'accounting': p['accounting']})
    plan['b5_review'] = put('b5', {'schema': 'n36r3-independent-b5-review-v1',
        'decision': 'PASS_PREPARATION_REQUIRES_ROOT_RELEASE',
        **{k: plan[k] for k in gate.BINDINGS},
        'worker_receipts_are_future': True, 'release_enabled': False})
    adoption = put('adoption', {'schema': 'n36r3-source-adoption-v1', 'approved': True,
        'owner_root': str(owner), 'source_cwd': str(source),
        **{k: plan[k] for k in gate.BINDINGS}, 'independent_review': plan['b5_review']})
    amendment = {'schema': 'n36r3-owning-accounting-v1', 'cohort': c.DRAFT_N36R3_COHORT,
        'accounting': plan['accounting'], 'source_adoption': adoption, 'caps': c.CAPS,
        'limits': c.LIMITS, 'healthchecks': copy.deepcopy(gate.HEALTH),
        'automatic_recoveries': 0, 'ledger_prefixes': anchors, 'snapshot': snapshot,
        'arithmetic': prep.arithmetic(snapshot)}
    authority = {k: amendment[k] for k in ('cohort', 'accounting', 'source_adoption',
                                          'healthchecks', 'ledger_prefixes')}
    authority.update(protocol=plan['protocol'], amendment=put('amendment', amendment))
    review = {'ledger_prefix': anchors['attempt-ledger.jsonl'],
              'health_ledger_prefix': anchors['gpu-healthcheck-ledger.jsonl']}
    return SimpleNamespace(**locals())


def test_exact_retained_accounting_and_finite_arithmetic(case):
    f = case
    assert gate.validate_authority(f.plan, f.authority) == f.rows
    assert prep.ledger_snapshot(f.owner, f.review)['snapshot'] == f.snapshot
    result = prep.arithmetic(f.snapshot)
    assert result['hours']['retained'] == '75.53335346582918'
    assert result['hours']['conservative_after'] == '96.76692515610880'
    assert result['hours']['unprotected_effective_after'] == '80.31712177058958'
    assert (result['retained_attempts'], result['prospective_attempts']) == (505, 545)
    assert result['seconds']['cohort_total'] == 75600
    assert result['health']['max_invocations'] == 41
    assert result['health']['aggregate_seconds'] == 1800
    assert result['current_headroom'] is None


@pytest.mark.parametrize('amount', [75.52725286641478, 75.53031173955723, math.nextafter(RETAINED, math.inf), 76.0])
def test_stale_or_mismatched_accounting_rejected(case, monkeypatch, amount):
    f = case
    stale = {**f.snapshot, 'gpu_hours_consumed': amount}
    with pytest.raises(ValueError, match='retained charge differs'):
        prep.arithmetic(stale)
    f.amendment['snapshot'] = stale
    f.authority['amendment'] = f.put('mismatch', f.amendment)
    with pytest.raises(ValueError, match='exact costs required'):
        gate.validate_authority(f.plan, f.authority)
    monkeypatch.setattr(r, 'budget_snapshot', lambda *a: stale)
    with pytest.raises(ValueError, match='accounting differs'):
        prep.ledger_snapshot(f.owner, f.review)
    with pytest.raises(ValueError, match='exact costs required'):
        gate.validate_authority(f.plan, f.authority)


@pytest.mark.parametrize('journal', sorted(gate.JOURNALS))
def test_all_three_prefixes_remain_strict(case, journal):
    f = case
    anchor = f.authority['ledger_prefixes'][journal]
    anchor['sha256'] = '0' * 64
    # Keep amendment and authority equal so rejection exercises the real prefix gate.
    f.authority['amendment'] = f.put('bad-prefix', f.amendment)
    with pytest.raises(ValueError, match='prefix'):
        gate.validate_authority(f.plan, f.authority)


@pytest.mark.parametrize('identity', [EARLIER_ID, OLD_ID, 'n36_healthcheck_n36r3_arbitrary'])
def test_old_or_arbitrary_authority_identity_rejected(case, identity):
    f = case
    f.authority['healthchecks'] = {**gate.HEALTH, 'preparation_id': identity}
    with pytest.raises(ValueError, match='distinct finite authority'):
        gate.validate_authority(f.plan, f.authority)
    with pytest.raises(ValueError, match='finite health binding'):
        gate.resource_events(f.plan, [{'resource_id': identity, 'kind': gate.KIND}])


@pytest.mark.parametrize('binding', ['source', 'runtime'])
def test_source_runtime_adoption_stays_exact(case, binding):
    case.plan[binding] = {'changed': True}
    with pytest.raises(ValueError, match='exact independent source review'):
        gate.validate_authority(case.plan, case.authority)


@pytest.mark.parametrize('identity,reused,error', [
    (EARLIER_ID, False, 'health replay forbidden'),
    (OLD_ID, False, 'health replay forbidden'),
    ('n36_healthcheck_n36r3_arbitrary', False, 'one preparation'),
    (NEW_ID, True, 'health replay forbidden'),
    (NEW_ID, False, 'CPU_STOP_BEFORE_BUDGET_DEVICE_OR_WRITE'),
])
def test_reservation_routing_and_no_replay(case, monkeypatch, identity, reused, error):
    f = case
    assert gate.PREPARATION_ID == gate.HEALTH['preparation_id'] == NEW_ID
    history = f.resources + ([{'resource_id': NEW_ID}] if reused else [])
    monkeypatch.setattr(health.release, 'validate_health_release',
                        lambda *a: (f.plan, {'artifact_root': 'synthetic'}, f.authority))
    monkeypatch.setattr(r, 'locked', lambda *a, **kw: nullcontext())
    monkeypatch.setattr(health.adapter, 'snapshot', lambda *a: (
        {'run_name': 'synthetic', 'artifacts': 'synthetic'}, f.events, history, []))
    f.plan['run_name'] = 'synthetic'
    monkeypatch.setattr(gate, 'live_journals', lambda *a: ([], []))
    monkeypatch.setattr(health.release, 'validate_state', lambda *a: None)
    monkeypatch.setattr(health.adapter, 'existing_handles', lambda *a: [])
    monkeypatch.setattr(health.supervisor, 'reconcile',
                        lambda *a, **kw: {'next_row': f.plan['episodes'][0], 'outcomes': []})
    def stop(*a, **kw):
        raise ValueError('CPU_STOP_BEFORE_BUDGET_DEVICE_OR_WRITE')
    monkeypatch.setattr(r, 'check_budget_limits', stop)
    plan_ref = f.put('route-plan', f.plan)
    before = {name: (f.owner / 'data' / name).read_bytes() for name in gate.JOURNALS}
    with pytest.raises(ValueError, match=error):
        accounting.reserve_healthcheck(plan_ref, {}, identity, timeout_seconds=20)
    assert before == {name: (f.owner / 'data' / name).read_bytes() for name in gate.JOURNALS}


def test_new_identity_suffix_preserves_old_charged_prefix(case):
    f = case
    record = {**c.operational_binding(f.plan), 'resource_id': NEW_ID, 'kind': gate.KIND,
        'event': 'reserved', 'timeout_seconds': 20, 'cleanup_seconds': 40,
        'reserved_gpu_seconds': 60, 'physical_gpu': 7, 'gpu_uuid': c.GPU_UUID,
        'source_commit': f.plan['source']['commit'], 'runtime': f.plan['runtime'],
        'plan': f.put('resource-plan', f.plan), 'release': {'synthetic': 'release'},
        'accounting_admission': {'synthetic': True}}
    assert gate.resource_events(f.plan, [record]) == [record]
    assert gate.live_journals(f.plan, f.authority, f.events,
                              f.resources + [record], []) == ([], [record])
    assert r.budget_snapshot(f.events, f.resources)['gpu_hours_consumed'] == RETAINED
    for key in ('source_commit', 'runtime'):
        changed = {**record, key: 'different'}
        with pytest.raises(ValueError, match='health source/authority differs'):
            gate.resource_events(f.plan, [changed])


@pytest.mark.parametrize('field', ['dispatched', 'reserved_attempts'])
def test_attempt_count_mismatch_rejected(case, monkeypatch, field):
    f = case
    bad = {**f.snapshot, field: 504}
    f.amendment['snapshot'] = bad
    f.authority['amendment'] = f.put('bad-count', f.amendment)
    monkeypatch.setattr(r, 'budget_snapshot', lambda *a: bad)
    with pytest.raises(ValueError, match='exact costs required'):
        gate.validate_authority(f.plan, f.authority)
    with pytest.raises(ValueError, match='accounting differs'):
        prep.ledger_snapshot(f.owner, f.review)


def test_episode_admission_uses_verified_suffix_but_retains_global_charge(case, monkeypatch):
    f = case
    release = health.release
    f.authority.update(automatic_recoveries=0, caps=c.CAPS,
        weekly_window={'origin_gpu_hours': 53.08404692669838, 'increment_gpu_hours': 168.})
    monkeypatch.setattr(gate, 'validate_readiness', lambda *a, **kw: None)
    monkeypatch.setattr(release, 'validate_state', lambda *a: None)
    monkeypatch.setattr(health.supervisor, 'reconcile',
                        lambda *a, **kw: {'next_row': f.plan['episodes'][0]})
    monkeypatch.setattr(r, 'check_budget_limits', lambda *a, **kw: 1800)
    monkeypatch.setattr(gate, 'margin_reference', lambda *a: {})
    monkeypatch.setattr(accounting, 'retained_margin', lambda *a: .23357169027962)
    def stop(snapshot, cohort, **kw):
        assert snapshot['gpu_hours_consumed'] == RETAINED
        assert snapshot['gpu_healthcheck_hours'] == (.00305887314245 + 10.950214579002932 / 3600)
        assert cohort['gpu_healthcheck_hours'] == cohort['gpu_hours_consumed'] == 0
        raise ValueError('CPU_STOP_AFTER_COHORT_ACCOUNTING')
    monkeypatch.setattr(accounting, 'headroom', stop)
    state = {'budget': {'amendment': f.authority['amendment']}}
    with pytest.raises(ValueError, match='CPU_STOP_AFTER_COHORT_ACCOUNTING'):
        release.admission(f.plan, f.authority, state, f.events, f.resources, [],
            f.plan['episodes'][0], now=None, gpu_idle=False,
            release_refs=({}, f.put('synthetic-release', {})))
