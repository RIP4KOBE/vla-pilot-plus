"""CPU identity contracts; synthetic deployment leaves never authorize a run."""
import copy
import datetime as dt
import json
from pathlib import Path
import pytest
from scripts import qd_ed_n36_contract as c, qd_ed_n36_recovery as recovery
from scripts import qd_ed_n36_release as release, qd_ed_n36_bridge as b
from scripts import qd_ed_n36_worker as worker, qd_ed_n36_supervise as supervisor
from scripts import qd_ed_n36_accounting as accounting, qd_ed_n23_worker as w
from test_n36_release import boundary, freeze, PROTOCOL
from test_n36_composition import prospective_base, write
from test_n36_runner import budget_fixture, historical, NOW

ALLOCATION = {'path': '/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001203/recovery-preparation/attempt-allocation.draft-v1.json',
              'sha256': recovery.ALLOCATION_SHA}
REVIEW = {'path': '/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001151/protocol-root-review-v1.json',
          'sha256': c.PROTOCOL_REVIEW_SHA}


def inherit(plan, root):
    plan['cohort'] = c.RECOVERY_COHORT
    plan['episodes'] = c.plan_rows(plan)
    ledger = {'schema': 'n36r1-accounting-inheritance-v1', 'cohort': c.RECOVERY_COHORT,
              'inherited_accounting': w.read_ref(PROTOCOL)['accounting'], 'allocation': ALLOCATION,
              'preserved_attempt': recovery.PRESERVED_ATTEMPT,
              'automatic_recoveries': 0, 'new_budget_authority': False}
    plan['accounting'] = write(root/'accounting-amendment.json', ledger)
    plan['protocol_review'] = REVIEW
    protocol = {'schema': 'n36r1-operational-protocol-v1', 'cohort': c.RECOVERY_COHORT,
                'inherited_protocol': PROTOCOL, 'inherited_protocol_review': REVIEW,
                'accounting': plan['accounting'], 'allocation': ALLOCATION,
                'episodes': plan['episodes'], 'automatic_recoveries': 0, 'scientific_changes': False}
    plan['protocol'] = write(root/'protocol-amendment.json', protocol)


@pytest.fixture
def fresh(boundary):
    f = boundary
    inherit(f.plan, f.root)
    f.plan['expected_manifests'] = {row['episode_key']: write(f.root/(row['episode_key']+'.json'),
        {'row': row, 'argv': ['python', 'synthetic-main']}) for row in f.plan['episodes']}
    f.authority.update(cohort=c.RECOVERY_COHORT, protocol=f.plan['protocol'],
                       accounting=f.plan['accounting'], amendment=f.plan['accounting'])
    f.plan['authority'] = write(f.root/'authority.json', f.authority)
    return f


def test_fresh_release_all40_worker_and_old_release_rejection(fresh):
    f = fresh
    refs = freeze(f)
    plan, _, authority = release.validate_release(*refs)
    assert len(plan['episodes']) == f.calls.count('manifest') == 40
    assert authority['amendment'] == plan['accounting']
    row = plan['episodes'][3]
    context = worker.context_for(refs[0], row, refs[1])
    assert worker.validate_context(write(f.root/'context.json', context))[3] == row
    old = copy.deepcopy(f.plan)
    old.pop('cohort'); old.pop('accounting')
    old['episodes'] = c.expected_rows(); old['protocol'] = PROTOCOL
    f.plan = old
    _, old_release = freeze(f)
    # The detached release cannot transfer, even with a supported fresh row set.
    fresh_ref = write(f.root/'fresh-plan.json', plan)
    with pytest.raises(ValueError, match='external release'):
        release.validate_release(fresh_ref, old_release)


@pytest.mark.parametrize('fault', ['old_rows', 'mixed_rows', 'unknown_cohort', 'seed', 'order',
    'validation', 'formal', 'recovery', 'old_protocol', 'accounting_ref', 'review_ref',
    'authority_protocol', 'authority_accounting', 'authority_amendment', 'authority_cohort'])
def test_release_rejects_cross_binding_even_with_new_synthetic_review(fresh, fault):
    f = fresh
    if fault == 'old_rows': f.plan['episodes'] = c.expected_rows()
    elif fault == 'mixed_rows': f.plan['episodes'][0] = c.expected_rows()[0]
    elif fault == 'unknown_cohort': f.plan['cohort'] = 'N36R2_UNAPPROVED'
    elif fault == 'seed': f.plan['episodes'][0]['policy_seed'] += 1
    elif fault == 'order': f.plan['episodes'].reverse()
    elif fault in ('validation', 'formal'): f.plan['phase_authorization'][fault] = True
    elif fault == 'recovery': f.plan['limits']['automatic_recoveries'] = 1
    elif fault == 'old_protocol': f.plan['protocol'] = PROTOCOL
    elif fault == 'accounting_ref': f.plan['accounting'] = w.read_ref(PROTOCOL)['accounting']
    elif fault == 'review_ref': f.plan['protocol_review'] = PROTOCOL
    elif fault.startswith('authority_'):
        key = fault.removeprefix('authority_')
        f.authority[key] = c.COHORT if key == 'cohort' else PROTOCOL
        f.plan['authority'] = write(f.root/'authority.json', f.authority)
    with pytest.raises((ValueError, KeyError)):
        release.validate_release(*freeze(f))


@pytest.mark.parametrize('fault', ['science', 'self_expected_hash', 'allocation', 'inherited_protocol',
                                  'inherited_accounting', 'charge', 'automatic_recovery', 'new_budget'])
def test_structural_amendment_cannot_rewrite_science_or_cost(fresh, fault):
    f = fresh
    protocol = w.read_ref(f.plan['protocol'])
    ledger = w.read_ref(f.plan['accounting'])
    if fault == 'science': protocol['scientific_contract'] = {'threshold': 0}
    elif fault == 'self_expected_hash':
        protocol['expected_protocol_sha256'] = 'a'*64
    elif fault == 'allocation': protocol['allocation'] = PROTOCOL
    elif fault == 'inherited_protocol':
        counterfeit = w.read_ref(PROTOCOL); counterfeit['scientific_contract'] = {}
        protocol['inherited_protocol'] = write(f.root/'counterfeit.json', counterfeit)
    elif fault == 'inherited_accounting': ledger['inherited_accounting'] = PROTOCOL
    elif fault == 'charge': ledger['preserved_attempt']['gpu_seconds'] = 0
    elif fault == 'automatic_recovery': ledger['automatic_recoveries'] = 1
    elif fault == 'new_budget': ledger['new_budget_authority'] = True
    f.plan['accounting'] = write(f.root/'accounting-amendment.json', ledger)
    protocol['accounting'] = f.plan['accounting']
    f.plan['protocol'] = write(f.root/'protocol-amendment.json', protocol)
    with pytest.raises((ValueError, KeyError)):
        recovery.validate_protocol(f.plan)


def journal(plan, outcomes):
    events = []
    for row, success in zip(plan['episodes'], outcomes):
        base = {**c.operational_binding(plan), 'attempt_id': row['episode_key'],
                'episode_key': row['episode_key'], 'identity': supervisor.c_identity(row),
                'budget_bucket': row['budget_bucket'], 'replacement': None}
        events += [{**base, 'event': 'reserved'}, {**base, 'event': 'dispatched'},
                   {**base, 'event': 'valid', 'success': success, 'outcome_valid': True,
                    'required_cost_telemetry_complete': True}]
    return events


def test_fresh_controller_history_futility_and_all40(fresh):
    plan = {k: v for k, v in fresh.plan.items() if k != 'schema'}
    old = historical(recovery.PRESERVED_ATTEMPT['gpu_seconds'], 'baseline',
                     recovery.PRESERVED_ATTEMPT['attempt_id'], c.COHORT, 'aborted')
    for event in old:
        event.update(identity=supervisor.c_identity(c.expected_rows()[0]), replacement=None)
    def reconcile(outcomes):
        return supervisor.reconcile(plan, old+journal(plan, outcomes), lambda *args: None)
    assert reconcile([])['next_row'] == plan['episodes'][0]
    assert reconcile([False]*20)['status'] == 'READY_FOR_ROOT_RELEASE'
    assert reconcile([False]*23)['next_row']['profile'] == 'N36'
    assert reconcile([False]*24)['status'] == 'NUMERIC_FUTILITY'
    assert reconcile([True]*39)['next_row'] == plan['episodes'][-1]
    assert reconcile([True]*40)['status'] == 'COMPLETE'
    assert c.cohort_events(c.expected_rows(), old) == old


@pytest.mark.parametrize('fault', ['spoof_iteration', 'unknown_key', 'old_key', 'bucket', 'replacement',
                                  'retry_of', 'recovery_of', 'protocol', 'accounting', 'protocol_review'])
def test_fresh_event_binding_fail_closed(fresh, fault):
    plan = {k: v for k, v in fresh.plan.items() if k != 'schema'}
    events = journal(plan, [True])
    if fault == 'spoof_iteration': events[0]['identity']['iteration'] = c.COHORT
    elif fault == 'unknown_key': events[0]['attempt_id'] = 'n36r1_dev_spoof'
    elif fault == 'old_key': events[0]['attempt_id'] = c.expected_rows()[0]['episode_key']
    elif fault == 'bucket': events[0]['budget_bucket'] = 'recovery'
    else: events[0][fault] = 'spoof'
    with pytest.raises(ValueError): supervisor.reconcile(plan, events, lambda *args: None)


def test_fresh_real_composed_manifests_and_disabled_draft(prospective_base, tmp_path):
    plan, runtime, _ = copy.deepcopy(prospective_base)
    old_manifests = [w.read_ref(plan['expected_manifests'][r['episode_key']])
                     for r in plan['episodes']]
    inherit(plan, tmp_path)
    plan['expected_manifests'] = {}
    for row, old in zip(plan['episodes'], old_manifests):
        manifest = b.manifest(plan, runtime, row)
        assert manifest['protocol'] == plan['protocol']
        assert manifest['accounting'] == plan['accounting']
        assert row['episode_key'] in ' '.join(manifest['argv'])
        # Only the operational run ID/output paths change, including mechanism logging.
        normalized = json.loads(json.dumps(old['resolved_config']).replace(
            old['row']['episode_key'], row['episode_key']))
        assert w.canonical_sha(manifest['resolved_config']) == w.canonical_sha(normalized)
        if row['profile'] in ('N34', 'N36'):
            assert manifest['expected_runtime']['binding']['run_id'] == row['episode_key']
        reference = write(tmp_path/(row['episode_key']+'.json'), manifest)
        plan['expected_manifests'][row['episode_key']] = reference
        assert b._verify_manifest_bound(reference, plan, runtime, row) == json.loads(json.dumps(manifest))
    c.validate_draft(plan)
    with pytest.raises(ValueError): c.require_release(plan)
    row = plan['episodes'][0]
    bad = copy.deepcopy(w.read_ref(plan['expected_manifests'][row['episode_key']]))
    bad['accounting'] = PROTOCOL
    with pytest.raises(ValueError, match='external manifest'):
        b._verify_manifest_bound(write(tmp_path/'bad.json', bad), plan, runtime, row)
    with pytest.raises(ValueError): b.command(plan, runtime, c.expected_rows()[0])


def test_prepare_emits_disabled_fresh_draft_only(fresh, monkeypatch):
    from scripts import qd_ed_n36_prepare as prepare
    f = fresh
    monkeypatch.setattr(b.closure, 'source_record', lambda *args: f.plan['source'])
    monkeypatch.setattr(b, 'manifest', lambda plan, runtime, row:
                        {**c.operational_binding(plan), 'row': row, 'synthetic_only': True})
    plan = prepare.prepare(f.root/'disabled-draft', f.plan['runtime'],
        runtime_closure_ref=f.plan['runtime_closure'], controller_semantics_ref=f.plan['controller_semantics'],
        native_build_ref=f.plan['native_build'], recovery_protocol_ref=f.plan['protocol'])
    c.validate_draft(plan)
    assert plan['episodes'] == c.expected_rows(cohort=c.RECOVERY_COHORT)
    assert len(plan['expected_manifests']) == 40
    assert not plan['release_enabled'] and not plan['frozen']
    assert plan['root_review'] is plan['execution_release'] is plan['authority'] is None
    assert plan['phase_authorization'] == dict(dev=False, validation=False, formal=False)


@pytest.mark.parametrize('fault', [None, 'cohort', 'protocol', 'accounting', 'protocol_review', 'old_id', 'kind'])
def test_healthcheck_history_uses_fresh_identity_and_refs(fresh, fault):
    plan = fresh.plan
    base = {**c.operational_binding(plan), 'resource_id': 'n36_healthcheck_n36r1_preparation_001203',
            'kind': 'n36r1_resource_preparation_v1'}
    events = [{**base, 'event': kind} for kind in ('reserved', 'dispatched', 'completed')]
    if fault == 'old_id': events[0]['resource_id'] = 'n36_healthcheck_preparation'
    elif fault: events[0][fault] = 'spoof'
    if fault:
        with pytest.raises(ValueError): recovery.resource_events(plan, events)
    else:
        old = {'cohort': c.COHORT, 'kind': 'n36_resource_preparation_v1',
               'resource_id': 'n36_healthcheck_preparation'}
        assert recovery.resource_events(plan, [old, *events]) == events


@pytest.mark.parametrize('fault', [None, 'old_row', 'missing_charge', 'changed_charge', 'amendment',
                                  'protected', 'recovery', 'STOP', 'deadline'])
def test_fresh_admission_preserves_failed_charge_and_gates(fresh, tmp_path, monkeypatch, fault):
    # Never let this fixture create the production session STOP.
    paths = (str(tmp_path/'owner_STOP'), str(tmp_path/'STOP'))
    monkeypatch.setattr(c.stop, 'STOP_PATHS', paths)
    monkeypatch.setattr(c, 'stop_path', lambda root=c.ROOT: paths[1])
    old = historical(recovery.PRESERVED_ATTEMPT['gpu_seconds'], 'baseline',
                     recovery.PRESERVED_ATTEMPT['attempt_id'], c.COHORT, 'aborted')
    plan, authority, state, reservations = budget_fixture(tmp_path, old)
    plan.update(c.operational_binding(fresh.plan), episodes=fresh.plan['episodes'], worktree=str(c.ROOT))
    authority.update(cohort=c.RECOVERY_COHORT, protocol=plan['protocol'], accounting=plan['accounting'],
                     amendment=plan['accounting'])
    state['budget']['amendment'] = plan['accounting']
    row = plan['episodes'][0]
    inherited = w.read_ref(plan['accounting'])['inherited_accounting']
    def margin(root, reference):
        assert reference == inherited
        return .23357169027962
    monkeypatch.setattr(accounting, 'retained_margin', margin)
    if fault == 'old_row': row = c.expected_rows()[0]
    elif fault == 'missing_charge': old.clear()
    elif fault == 'changed_charge': old[-1]['gpu_process_wall_seconds'] = 0
    elif fault == 'amendment': authority['amendment'] = PROTOCOL
    elif fault == 'protected': state['budget']['gpu_hour_reservations']['validation'] = 0
    elif fault == 'recovery': authority['automatic_recoveries'] = 1
    elif fault == 'STOP': Path(plan['stop_path']).touch()
    now = dt.datetime.fromisoformat(c.DEADLINE.replace('Z', '+00:00')) if fault == 'deadline' else NOW
    def admit():
        return release.admission(plan, authority, state, old, [], reservations, row, now=now, gpu_idle=True)
    if fault is not None:
        with pytest.raises((ValueError, release.r.GateError)): admit()
    else:
        result = admit()
        assert result['dispatched'] == result['aborted'] == 1
        assert result['gpu_hours_consumed'] == pytest.approx(86.40354533703066/3600)
        assert result['n36_reservation']['reserved_gpu_seconds'] == 1840
        assert result['n36_reservation']['cohort_charged_gpu_hours'] == 0
