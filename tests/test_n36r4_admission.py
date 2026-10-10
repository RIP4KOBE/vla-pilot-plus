"""CPU-only identity boundaries; bound preparation inputs are read-only.

No model construction, runtime certification, adoption, owner journals or GPU.
The production manifest comparator and Hydra composition are not mocked.
"""
import copy
import datetime as dt
import json
from pathlib import Path

import pytest

from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n36_contract as c, qd_ed_n36_bridge as bridge
from scripts import qd_ed_n36_release as release, qd_ed_n36_supervise as supervisor
from scripts import qd_ed_n36r3_admission as gate, qd_ed_n36r4_admission as successor
from scripts import qd_ed_n36r2_admission as routing
from scripts import qd_ed_n36_accounting as accounting

PREPARATION = gate.OWNER.parent / 'autonomy_20261004/turns/001467/recovery-preparation'


def put(tmp_path, name, value):
    path = tmp_path / (name + '.json')
    path.write_text(json.dumps(value))
    return c.ref(path)


@pytest.fixture
def prepared():
    path = PREPARATION / 'plan.draft.json'
    if not path.is_file():
        pytest.skip('exact hash-bound turn 001467 preparation is not installed')
    plan = json.loads(path.read_text())
    assert plan['source']['commit'] == '80a9d945e688da17485239b3d5bb11c558c214d6'
    successor.validate_protocol(plan)
    return plan, w.read_ref(plan['runtime'])


@pytest.mark.parametrize('arm', c.ARMS)
def test_real_production_manifest_accepts_exact_successor(prepared, tmp_path, arm):
    plan, runtime = prepared
    row = next(row for row in plan['episodes'] if row['profile'] == arm)
    manifest = bridge.manifest(plan, runtime, row)
    prospective = w.read_ref(plan['prospective_manifests'][row['episode_key']])
    for key in ('argv', 'output_dir', 'row', 'resolved_config', 'composed_config_sha256', 'expected_runtime'):
        assert json.loads(json.dumps(manifest[key])) == prospective[key]
    reference = put(tmp_path, arm, manifest)
    assert bridge._verify_manifest_bound(reference, plan, runtime, row) == json.loads(json.dumps(manifest))
    assert manifest['cohort'] == c.DRAFT_N36R4_COHORT
    assert Path(manifest['output_dir']) == Path(plan['artifact_root']) / 'attempts' / row['episode_key']
    assert 'n36r4_dev_' in manifest['output_dir']
    # The actual production comparator rejects an externally rehashed mixed manifest.
    for field, value in [('cohort', c.DRAFT_N36R3_COHORT),
                         ('row', c.expected_rows(cohort=c.DRAFT_N36R3_COHORT)[c.ARMS.index(arm)]),
                         ('output_dir', manifest['output_dir'].replace('n36r4_', 'n36r3_')),
                         ('accounting', {'path': 'stale', 'sha256': c.ACCOUNTING_SHA}),
                         ('resource_routing', {**plan['resource_routing'], 'owner_root': plan['worktree']})]:
        bad = {**manifest, field: value}
        with pytest.raises(ValueError, match='external manifest differs'):
            bridge._verify_manifest_bound(put(tmp_path, 'bad-' + field, bad), plan, runtime, row)


@pytest.mark.parametrize('mutation', ['row', 'cohort', 'old_cohort_and_rows', 'accounting', 'protocol', 'owner', 'source',
                                      'stop', 'stop_authority', 'output', 'limits'])
def test_production_composition_rejects_mixed_plan(prepared, mutation):
    plan, runtime = prepared
    if mutation == 'row':
        plan['episodes'][0] = c.expected_rows(cohort=c.DRAFT_N36R3_COHORT)[0]
    elif mutation in ('cohort', 'old_cohort_and_rows'):
        plan['cohort'] = c.DRAFT_N36R3_COHORT
        if mutation == 'old_cohort_and_rows':
            plan['episodes'] = c.expected_rows(cohort=c.DRAFT_N36R3_COHORT)
    elif mutation in ('accounting', 'protocol'):
        plan[mutation] = {'path': 'not-read', 'sha256': '0' * 64}
    elif mutation == 'owner':
        plan['resource_routing']['owner_root'] = plan['worktree']
    elif mutation == 'source':
        plan['resource_routing']['source_cwd'] = str(gate.OWNER)
    elif mutation == 'stop':
        plan['stop_path'] = str(Path(plan['worktree']) / 'STOP')
    elif mutation == 'stop_authority':
        plan['stop_authority']['paths'] = [plan['stop_path']]
    elif mutation == 'output':
        plan['artifact_root'] = plan['artifact_root'].replace('001467', '001314')
    else:
        plan['limits']['episode_seconds'] = 1799
    with pytest.raises(ValueError):
        bridge.manifest(plan, runtime, plan['episodes'][0])


def test_retained_accounting_and_margin(prepared):
    plan, _ = prepared
    ledger = w.read_ref(plan['accounting'])
    authority = {'ledger_prefixes': ledger['retained_ledger_prefixes']}
    amendment = {'arithmetic': {key: ledger[key] for key in successor.ARITHMETIC_KEYS}}
    snapshot = ledger['retained_snapshot']
    successor.validate_accounting(plan, authority, amendment, snapshot)
    assert snapshot['dispatched'] == 506
    assert snapshot['gpu_hours_consumed'] == 75.60616276674473
    assert amendment['arithmetic']['hours']['retained_admission_margin'] == '0.23357169027962'
    assert gate.margin_reference(plan)['sha256'] == c.ACCOUNTING_SHA
    for field, value in [('dispatched', 505), ('reserved_attempts', 505),
                         ('gpu_hours_consumed', 75.53335346582918)]:
        with pytest.raises(ValueError, match='exact retained'):
            successor.validate_accounting(plan, authority, amendment, {**snapshot, field: value})
    for journal in gate.JOURNALS:
        bad = copy.deepcopy(authority)
        bad['ledger_prefixes'][journal]['sha256'] = '0' * 64
        with pytest.raises(ValueError, match='exact retained'):
            successor.validate_accounting(plan, bad, amendment, snapshot)
    bad = copy.deepcopy(amendment)
    bad['arithmetic']['hours']['retained_admission_margin'] = '0'
    with pytest.raises(ValueError, match='exact retained'):
        successor.validate_accounting(plan, authority, bad, snapshot)


def test_health_identity_and_owner_are_cohort_specific(prepared, tmp_path):
    plan, _ = prepared
    assert routing.owner_root(plan) == gate.OWNER
    spec = gate.identity_contract(plan)
    assert spec['health'] == successor.HEALTH and spec['kind'] == successor.KIND
    event = {**c.operational_binding(plan), 'resource_id': successor.PREPARATION_ID,
        'kind': successor.KIND, 'event': 'reserved', 'timeout_seconds': 20,
        'cleanup_seconds': 40, 'reserved_gpu_seconds': 60, 'physical_gpu': 7,
        'gpu_uuid': c.GPU_UUID, 'source_commit': plan['source']['commit'],
        'runtime': plan['runtime'], 'plan': put(tmp_path, 'plan', plan),
        'release': {'cpu_fixture': True}, 'accounting_admission': {'cpu_fixture': True}}
    assert gate.resource_events(plan, [event]) == [event]
    for field, value in [('resource_id', gate.PREPARATION_ID), ('kind', gate.KIND),
                         ('cohort', c.DRAFT_N36R3_COHORT), ('timeout_seconds', 19),
                         ('source_commit', 'stale')]:
        with pytest.raises(ValueError):
            gate.resource_events(plan, [{**event, field: value}])
    # Bound health references are required even before any current ledger is read.
    plan['b5_review'] = put(tmp_path, 'b5', {
        'schema': 'n36r4-independent-b5-review-v1',
        'decision': 'PASS_PREPARATION_REQUIRES_ROOT_RELEASE',
        **{key: plan[key] for key in gate.BINDINGS},
        'worker_receipts_are_future': True, 'release_enabled': False})
    for health in (gate.HEALTH, {**successor.HEALTH, 'preparation_id': 'arbitrary'}):
        authority = {'cohort': c.DRAFT_N36R4_COHORT, 'protocol': plan['protocol'],
                     'accounting': plan['accounting'], 'healthchecks': health}
        with pytest.raises(ValueError, match='distinct finite authority'):
            gate.validate_authority(plan, authority)


def test_first_c0_g3_is_not_waivable():
    rows = c.expected_rows(cohort=c.DRAFT_N36R4_COHORT)
    plan = {'cohort': c.DRAFT_N36R4_COHORT, 'episodes': rows, 'first_C0_G3_pause': False}
    row = rows[0]
    base = {'attempt_id': row['episode_key'], 'episode_key': row['episode_key'],
            'identity': supervisor.c_identity(row), 'budget_bucket': row['budget_bucket'],
            'replacement': None, 'outcome_valid': True, 'required_cost_telemetry_complete': True,
            'success': False}
    events = [{**base, 'event': event} for event in ('reserved', 'dispatched', 'valid')]
    result = supervisor.reconcile(plan, events, lambda *args: None)
    assert result['status'] == 'PAUSED_FOR_ROOT_G3' and result['next_row'] is None
    assert supervisor.first_c0_boundary(c.expected_rows(cohort=c.DRAFT_N36R3_COHORT)[0])


def test_bare_successor_and_old_allowance_never_authorize(prepared):
    plan, _ = prepared
    with pytest.raises(ValueError, match='separate root bindings'):
        release.validate_plan(plan)
    with pytest.raises(ValueError, match='separate root bindings'):
        c.pre_dispatch(plan['episodes'][0], {'n36r3_release_refs': ({}, {})},
            now=dt.datetime.now(dt.timezone.utc), stop_path=plan['stop_path'], cohort=c.DRAFT_N36R4_COHORT)


def test_health_aggregate_and_full_attempt_bounds_stay_unchanged():
    snapshot = {'gpu_hours_consumed': 75.60616276674473, 'running': 0, 'gpu_healthcheck_inflight': 0}
    local = {'gpu_hours_consumed': 1741 / 3600, 'gpu_healthcheck_hours': 1741 / 3600}
    with pytest.raises(ValueError, match='cumulative healthcheck bound'):
        accounting.headroom(snapshot, local, retained_margin_hours=.23357169027962,
            protected_hours=36.2408240024308155, healthcheck=True, need=60)
    with pytest.raises(ValueError, match='bounded full reservation'):
        accounting.headroom(snapshot, local, retained_margin_hours=.23357169027962,
            protected_hours=36.2408240024308155, need=1839)


def test_full_manifest_gate_still_rejects_stale_source(prepared, tmp_path):
    plan, runtime = prepared
    row = plan['episodes'][0]
    reference = put(tmp_path, 'prospective', bridge.manifest(plan, runtime, row))
    # Real source verification must fail before runtime acceptance: these bound
    # drafts predate this repair. No source/runtime/native audit is patched out.
    with pytest.raises(ValueError, match='uncommitted source bytes|source bytes/commit differ'):
        bridge.verify_manifest(reference, plan, runtime, row)


def test_health_output_must_route_to_exact_resource(prepared, tmp_path, monkeypatch):
    plan, runtime = prepared
    terminal = {'output_dir': plan['artifact_root'] + '/healthchecks/' + gate.PREPARATION_ID,
                'resource_id': successor.PREPARATION_ID}
    record = {'readiness': {'health_release': {'cpu_fixture': True},
                           'terminal': put(tmp_path, 'wrong-output', terminal)}}
    monkeypatch.setattr(release, 'validate_health_release', lambda *args: (plan, runtime, {}))
    with pytest.raises(ValueError, match='exact health output routing'):
        gate.validate_readiness({}, record)


def test_old_release_cannot_be_relabelled_as_successor_allowance(monkeypatch):
    previous = {'cohort': c.DRAFT_N36R3_COHORT,
                'episodes': c.expected_rows(cohort=c.DRAFT_N36R3_COHORT)}
    authority = {'cohort': c.DRAFT_N36R3_COHORT}
    monkeypatch.setattr(release, 'validate_release', lambda *args: (previous, {}, authority))
    allowance = {'n36r4_plan': previous, 'n36r4_authority': authority,
                 'n36r4_release_refs': ({}, {})}
    with pytest.raises(ValueError, match='detached release differs'):
        c.pre_dispatch(c.expected_rows(cohort=c.DRAFT_N36R4_COHORT)[0], allowance,
            now=dt.datetime.now(dt.timezone.utc), stop_path=c.stop_path(), cohort=c.DRAFT_N36R4_COHORT)
