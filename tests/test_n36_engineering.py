"""CPU-only adapter boundaries. All fixture artifacts are disabled/non-authority.

Production schema, manifest, accounting and reconciliation validators are used
without replacement. No model, provider, native runtime or device is executed.
Synthetic journals demonstrate state mechanics, not valid GPU receipts or B5.
"""
import copy
import datetime as dt
import json
from pathlib import Path

import pytest

from scripts import qd_ed_n23_worker as w, qd_ed_final_runner as r
from scripts import qd_ed_n36_engineering as e, qd_ed_n36_bridge as b
from scripts import qd_ed_n36_contract as c, qd_ed_n36_release as full
from scripts import qd_ed_n36_worker as worker, qd_ed_n36_report as reporting


def put(root, name, value):
    path = root / (name + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False))
    return {'path': str(path), 'sha256': w.sha(path)}


def ref(anchor):
    return {key: anchor[key] for key in ('path', 'sha256')}


@pytest.fixture(scope='module')
def documents(tmp_path_factory):
    root = tmp_path_factory.mktemp('engineering-disabled')
    spec = e.specification()
    original_ref = ref(spec['full_audit_view']['immutable_original_plan'])
    original = w.read_ref(original_ref)
    runtime = w.read_ref(original['runtime'])
    route = {'schema': 'n36-engineering-deployment-v1', 'source_cwd': str(e.SOURCE),
             'owner_root': str(e.OWNER), 'output_root': str(e.SESSION / 'engineering-executions' / e.EPISODE_KEY),
             'stop_authority': c.stop.binding()}
    route_ref = put(root, 'deployment-disabled-input', route)
    scope = put(root, 'scope-disabled', e.disabled_scope())
    account = put(root, 'accounting-disabled', e.disabled_accounting())
    inputs = {'run_name': 'CPU_FIXTURE_NOT_AUTHORITY',
              'runtime_inventory_path': str(e.SOURCE / 'cpu-fixture-inventory.json'),
              'runtime_inventory_sha256': '0' * 64,
              'seed_plan_path': str(e.SOURCE / 'cpu-fixture-seeds.json'),
              'seed_plan_sha256': '0' * 64, 'input_contract_label': 'input_repaired'}
    audit = {key: copy.deepcopy(original[key]) for key in ('source', 'scientific_source', 'runtime',
        'native_build', 'runtime_closure', 'controller_semantics', 'episodes', 'limits', 'worker_contract',
        'deadline', 'cohort', 'protocol', 'protocol_review', 'accounting')}
    audit.update(schema=e.AUDIT_SCHEMA, original_plan=original_ref, dispatch_authority=False,
        frozen=True, release_enabled=False, worktree=str(e.SOURCE),
        artifact_root=route['output_root'] + '/audit-only', stop_path=c.stop_path(e.SOURCE),
        stop_authority=c.stop.binding(), phase_authorization={'dev': False, 'validation': False, 'formal': False},
        expected_manifests={}, deployment=route_ref, scope=scope, attempt_identity='episode_key', **inputs)
    for index, row in enumerate(audit['episodes']):
        manifest = b.manifest(audit, runtime, row)
        audit['expected_manifests'][row['episode_key']] = put(root, f'audit-{index:02}', manifest)
    audit_ref = put(root, 'audit-disabled', audit)
    placeholder = put(root, 'missing-authority', {'disabled_fixture': True, 'release_enabled': False})
    plan = {key: copy.deepcopy(audit[key]) for key in ('source', 'scientific_source', 'runtime',
        'native_build', 'runtime_closure', 'controller_semantics', 'worker_contract', 'deadline',
        'worktree', 'stop_path', 'stop_authority', *e.RUNTIME_INPUTS)}
    plan.update(schema=e.PLAN_SCHEMA, frozen=False, release_enabled=False, cohort=e.IDENTITY,
        purpose=e.PURPOSE, episodes=[e.row()], limits=copy.deepcopy(e.LIMITS),
        phase_authorization={'engineering': False, 'dev': False, 'validation': False, 'formal': False},
        artifact_root=route['output_root'], attempt_identity='episode_key', authority=placeholder,
        b5_review=placeholder, scope=scope, accounting=account, deployment=route_ref,
        audit_plan=audit_ref, scientific_equivalence=placeholder, engineering_manifest=placeholder,
        expected_manifests={})
    manifest = b.engineering_manifest(plan, runtime, e.row())
    plan['engineering_manifest'] = put(root, 'engineering-manifest-disabled', manifest)
    plan['expected_manifests'] = {e.EPISODE_KEY: plan['engineering_manifest']}
    return plan, audit, runtime, root


@pytest.fixture
def prepared(documents):
    return copy.deepcopy(documents)


def test_exact_scope_and_accounting_are_disabled():
    assert e.validate_disabled_scope(e.disabled_scope())['release_enabled'] is False
    assert e.validate_disabled_accounting(e.disabled_accounting())['root_adopted'] is False
    assert e.LIMITS['health_seconds'] + e.LIMITS['health_cleanup_seconds'] == 60
    assert e.LIMITS['episode_seconds'] + e.LIMITS['cleanup_seconds'] + 60 == 1900
    assert e.LIMITS['gpu_seconds'] + e.LIMITS['root_overhead_seconds'] == 2100
    assert e.IDENTITY not in c.IDENTITIES
    assert c.LIMITS['primary_cells'] == 40 and c.LIMITS['cohort_gpu_seconds'] == 75600


@pytest.mark.parametrize('key,value', [('max_attempts', 2), ('max_healthchecks', 2),
    ('scientific_eligible', True), ('automatic_continuation', True), ('purpose', 'dev'),
    ('health_resource_id', 'n36_healthcheck_preparation'), ('unknown', False)])
def test_scope_mutations_fail(key, value):
    bad = e.disabled_scope()
    bad['scope'][key] = value
    with pytest.raises(ValueError):
        e.validate_disabled_scope(bad)


@pytest.mark.parametrize('key,value', [('gpu_reservation_seconds', 2100), ('episode_timeout_seconds', 1799),
    ('health_cleanup_seconds', 39), ('new_attempts_max', 2), ('retained_attempts', 505),
    ('retained_admission_margin_gpu_hours', '0'), ('automatic_recoveries', 1),
    ('effective_weekly_cap_gpu_hours', '224')])
def test_accounting_mutations_fail(key, value):
    bad = e.disabled_accounting()
    bad['accounting'][key] = value
    with pytest.raises(ValueError):
        e.validate_disabled_accounting(bad)


def test_disabled_and_cross_family_entrypoints(prepared, tmp_path):
    plan, audit, _, _ = prepared
    for doc in (e.disabled_scope(), audit, plan):
        plan_ref = put(tmp_path, 'disabled', doc)
        for validate in (e.validate_release, e.validate_health_release, full.validate_release):
            with pytest.raises((ValueError, KeyError)):
                validate(plan_ref, plan_ref)
    with pytest.raises(ValueError):
        c.cohort(plan)
    old = w.read_ref(audit['original_plan'])
    with pytest.raises(ValueError):
        e.validate_plan(old)
    with pytest.raises(ValueError):
        full.validate_plan(plan)
    assert worker.release_api(put(tmp_path, 'route', plan)) is e
    with pytest.raises(ValueError):
        worker.release_api(put(tmp_path, 'scope-not-plan', e.disabled_scope()))


def test_all40_composed_and_engineering_manifest_exact(prepared):
    plan, audit, runtime, _ = prepared
    e.validate_audit_view(audit)
    assert len(audit['expected_manifests']) == 40
    assert [row['profile'] for row in audit['episodes']] == list(c.ARMS) * 10
    for row in audit['episodes']:
        result = b._verify_manifest_bound(audit['expected_manifests'][row['episode_key']], audit, runtime, row)
        assert result['schema'] == 'n36-engineering-audit-runtime-v1'
        assert result['dispatch_authority'] is False
    result = b.verify_engineering_manifest(plan['engineering_manifest'], plan, runtime, e.row())
    assert result['audit_row'] == audit['episodes'][0]
    assert result['audit_manifest'] == audit['expected_manifests'][audit['episodes'][0]['episode_key']]
    assert result['scientific_eligible'] is False
    original = b.command(audit, runtime, audit['episodes'][0])[0]
    command = b.engineering_command(plan, runtime, e.row())[0]
    changed = [old.split('=')[0] for old, new in zip(original, command) if old != new]
    assert set(changed) == set(b._ENGINEERING_ROUTES + b._ENGINEERING_IDENTITIES)


@pytest.mark.parametrize('mutation', ['empty', 'partial', 'order', 'seed', 'limit', 'worker', 'review',
    'source_alias', 'owner_alias', 'output', 'stop', 'dispatch', 'phase', 'unknown'])
def test_audit_view_rejects_science_and_route_mutations(prepared, tmp_path, mutation):
    _, audit, _, _ = prepared
    if mutation == 'empty': audit['expected_manifests'] = {}
    elif mutation == 'partial': audit['expected_manifests'].pop(audit['episodes'][-1]['episode_key'])
    elif mutation == 'order': audit['episodes'].reverse()
    elif mutation == 'seed': audit['episodes'][-1]['env_seed'] += 1
    elif mutation == 'limit': audit['limits']['episode_seconds'] = 1799
    elif mutation == 'worker': audit['worker_contract']['timeout_includes_audit'] = False
    elif mutation == 'review': audit['protocol_review']['sha256'] = '0' * 64
    elif mutation in ('source_alias', 'owner_alias', 'output'):
        route = w.read_ref(audit['deployment'])
        field = {'source_alias': 'source_cwd', 'owner_alias': 'owner_root', 'output': 'output_root'}[mutation]
        route[field] += '/.'
        audit['deployment'] = put(tmp_path, 'bad-route', route)
    elif mutation == 'stop': audit['stop_authority']['paths'].pop()
    elif mutation == 'dispatch': audit['dispatch_authority'] = True
    elif mutation == 'phase': audit['phase_authorization']['dev'] = True
    else: audit['unknown'] = False
    with pytest.raises(ValueError):
        e.validate_audit_view(audit)


@pytest.mark.parametrize('index', [1, 2, 3, 4, 39])
def test_non_c0_manifest_corruption_rejected_by_production_comparator(prepared, tmp_path, index):
    _, audit, runtime, _ = prepared
    row = audit['episodes'][index]
    manifest = w.read_ref(audit['expected_manifests'][row['episode_key']])
    manifest['resolved_config']['nonprogress_tangent_mode'] = 'tampered'
    bad = put(tmp_path, 'bad-non-c0', manifest)
    with pytest.raises(ValueError, match='external manifest differs'):
        b._verify_manifest_bound(bad, audit, runtime, row)


@pytest.mark.parametrize('mutation', ['profile', 'task', 'seed', 'init', 'key', 'iteration', 'timeout', 'extra'])
def test_exact_mapping_only(prepared, mutation):
    plan, _, runtime, _ = prepared
    row = e.row()
    fields = {'profile': ('profile', 'Q0'), 'task': ('task_id', 1), 'seed': ('env_seed', 7),
              'init': ('init_index', 1), 'key': ('episode_key', 'n36r4_dev_t00_c0_001467'),
              'iteration': ('iteration', c.DRAFT_N36R4_COHORT), 'timeout': ('timeout_seconds', 1799),
              'extra': ('retry_of', None)}
    key, value = fields[mutation]
    row[key] = value
    with pytest.raises(ValueError):
        b.engineering_command(plan, runtime, row)


@pytest.mark.parametrize('key,value', [('cohort', c.DRAFT_N36R4_COHORT), ('purpose', 'dev'),
    ('scientific_eligible', True), ('output_dir', '/old-output'), ('argv', ['python', 'bypass']),
    ('scope', {'path': '/stale', 'sha256': '0' * 64})])
def test_extra_engineering_manifest_exact(prepared, tmp_path, key, value):
    plan, _, runtime, _ = prepared
    doc = w.read_ref(plan['engineering_manifest'])
    doc[key] = value
    with pytest.raises(ValueError, match='engineering external manifest differs'):
        b.verify_engineering_manifest(put(tmp_path, 'changed', doc), plan, runtime, e.row())


def test_closure_rejects_real_stale_source_without_bypass(prepared):
    _, audit, _, _ = prepared
    # Real source closure rejects a stale original inventory; it cannot certify
    # the new adapter, or reach any model/runtime input verification.
    with pytest.raises(ValueError):
        full.verify_audit_closure(audit)


def test_audit_evidence_immutable_and_detached_copies():
    result = full.AuditEvidence({'version': [1]}, {'one': {'argv': ['original']}})
    result.runtime['version'].append(2)
    result.manifests['one']['argv'][0] = 'changed'
    assert result.runtime == {'version': [1]}
    assert result.manifests == {'one': {'argv': ['original']}}
    with pytest.raises(AttributeError): result._bytes = b'changed'


def episode_fixture(plan):
    row = e.row()
    base = {**e.operational_binding(plan), 'attempt_id': e.EPISODE_KEY, 'episode_key': e.EPISODE_KEY,
            'identity': e._identity(row), 'budget_bucket': 'baseline', 'replacement': None,
            'plan_sha256': '0' * 64, 'release': {'disabled_fixture': True},
            'source_commit': plan['source']['commit'], 'runtime_manifest_sha256': plan['runtime']['sha256'],
            'runtime_inventory_sha256': plan['runtime_inventory_sha256'],
            'init_row_sha256': row['init_row_sha256'], 'output_dir': plan['artifact_root'] + '/attempts/' + e.EPISODE_KEY,
            'physical_gpu': 7, 'ledger_prefix': {'disabled_fixture': True}, 'context': {'disabled_fixture': True},
            'reserved_gpu_seconds': 1840, 'accounting_admission': {'reserved_gpu_seconds': 1840},
            'time_unix': 100, 'timeout_seconds': 1800, 'gpu_process_wall_seconds': 1800,
            'outcome_valid': True, 'required_cost_telemetry_complete': True, 'success': False}
    return [{**base, 'event': kind} for kind in ('reserved', 'dispatched', 'valid')]


@pytest.mark.parametrize('length,status', [(0, 'READY_FOR_ROOT_RELEASE'), (1, 'LIVE_OR_UNSETTLED'),
                                         (2, 'LIVE_OR_UNSETTLED'), (3, 'PAUSED_FOR_ROOT_G3')])
def test_one_use_reconstruction_ignores_pause_flags(prepared, length, status):
    plan, _, _, _ = prepared
    plan['first_C0_G3_pause'] = False
    plan['later_root_G3_approved'] = True
    events = episode_fixture(plan)[:length]
    verified = []
    result = e.reconcile(plan, events, lambda row, final: verified.append(final))
    assert result['status'] == status
    assert result['scope_exhausted'] == bool(length)
    assert result['continuation_authorized'] is False
    assert (result['next_row'] is None) == bool(length)
    assert len(verified) == (1 if length == 3 else 0)
    assert result['outcomes'] == []  # never a matched control


def test_invalid_and_terminal_before_artifact_stop(prepared):
    plan, _, _, _ = prepared
    events = episode_fixture(plan)
    def missing_artifact(*args):
        raise FileNotFoundError('CPU fixture crash after journal before terminal artifact')
    result = e.reconcile(plan, events, missing_artifact)
    assert result['status'] == 'INVALID_STOP' and result['next_row'] is None
    events[-1]['event'] = 'aborted'
    result = e.reconcile(plan, events, lambda *args: pytest.fail('invalid cannot verify'))
    assert result['status'] == 'INVALID_STOP' and result['scope_exhausted'] is True
    events[-1]['event'] = 'valid'
    assert e.reconcile(plan, events, lambda *args: None, live_handles=[{'unknown': True}])['status'] == 'LIVE_OR_UNSETTLED'


@pytest.mark.parametrize('mutation', ['replay', 'missing_reserved', 'foreign', 'binding', 'short', 'cost', 'retry'])
def test_one_use_episode_mutations(prepared, mutation):
    plan, _, _, _ = prepared
    events = episode_fixture(plan)
    if mutation == 'replay': events += copy.deepcopy(events)
    elif mutation == 'missing_reserved': events = events[1:]
    elif mutation == 'foreign': events[0]['attempt_id'] += '_second'
    elif mutation == 'binding': events[-1]['scope'] = {'disabled_fixture': True}
    elif mutation == 'short': events[0]['reserved_gpu_seconds'] = 1839
    elif mutation == 'cost': events[-1]['gpu_process_wall_seconds'] = 1841
    else: events[0]['retry_of'] = 'old'
    with pytest.raises(ValueError): e.episode_events(plan, events)


def health_fixture(plan, root):
    reference = put(root, 'disabled-journal-plan', plan)
    base = {**e.operational_binding(plan), 'resource_id': e.HEALTH_ID, 'kind': e.HEALTH_KIND,
            'source_commit': plan['source']['commit'], 'runtime': plan['runtime'], 'plan': reference,
            'release': {'disabled_fixture': True}, 'timeout_seconds': 20, 'cleanup_seconds': 40,
            'reserved_gpu_seconds': 60, 'physical_gpu': 7, 'gpu_uuid': c.GPU_UUID,
            'accounting_admission': {'reserved_gpu_seconds': 60}, 'gpu_process_wall_seconds': 60}
    return [{**base, 'event': kind} for kind in ('reserved', 'dispatched', 'completed')]


@pytest.mark.parametrize('mutation', ['none', 'reserved', 'aborted', 'replay', 'alias', 'kind', 'timeout', 'cleanup', 'cost', 'scope'])
def test_one_use_health_journal(prepared, tmp_path, mutation):
    plan, _, _, _ = prepared
    events = health_fixture(plan, tmp_path)
    if mutation == 'reserved': events = events[:1]
    elif mutation == 'aborted': events[-1]['event'] = 'aborted'
    elif mutation == 'replay': events += copy.deepcopy(events)
    elif mutation == 'alias': events[0]['resource_id'] = 'n36_healthcheck_' + e.EPISODE_KEY
    elif mutation == 'kind': events[0]['kind'] = 'n36r4_resource_preparation_v1'
    elif mutation == 'timeout': events[0]['timeout_seconds'] = 19
    elif mutation == 'cleanup': events[0]['cleanup_seconds'] = 39
    elif mutation == 'cost': events[-1]['gpu_process_wall_seconds'] = 61
    elif mutation == 'scope': events[-1]['scope'] = {'disabled_fixture': True}
    if mutation in ('none', 'reserved', 'aborted'):
        assert e.resource_events(plan, events) == events
    else:
        with pytest.raises(ValueError): e.resource_events(plan, events)


def test_headroom_exact_global_and_scope_boundaries():
    snapshot = {'gpu_hours_consumed': 75.60616276674473, 'running': 0, 'gpu_healthcheck_inflight': 0}
    local = {'gpu_hours_consumed': 0, 'gpu_healthcheck_hours': 0, 'reserved_attempts': 0}
    kwargs = {'margin': .23357169027962, 'protected': 36.2408240024308155}
    assert e.headroom(snapshot, local, health=True, **kwargs)['reserved_gpu_seconds'] == 60
    used = {**local, 'gpu_hours_consumed': 60 / 3600, 'gpu_healthcheck_hours': 60 / 3600}
    assert e.headroom(snapshot, used, health=False, **kwargs)['reserved_gpu_seconds'] == 1840
    for bad in ({**used, 'reserved_attempts': 1}, {**used, 'gpu_hours_consumed': 61 / 3600},
                {**used, 'gpu_healthcheck_hours': 61 / 3600}):
        with pytest.raises(ValueError): e.headroom(snapshot, bad, health=False, **kwargs)
    with pytest.raises(ValueError): e.headroom(snapshot, local, health=False, margin=0, protected=kwargs['protected'])
    with pytest.raises(ValueError): e.headroom(snapshot, used, health=True, **kwargs)
    with pytest.raises(ValueError):
        e.headroom({**snapshot, 'gpu_hours_consumed': 220.8}, local, health=False, **kwargs)


def test_scientific_aggregator_rejects_engineering(prepared):
    plan, _, _, _ = prepared
    events = episode_fixture(plan)
    result = e.reconcile(plan, events, lambda *args: None)
    with pytest.raises(ValueError, match='ineligible'):
        reporting.summary(result, events)
    with pytest.raises(ValueError, match='ineligible'):
        reporting.summary({'status': 'COMPLETE', 'outcomes': []}, events)


def test_bound_scope_accounting_file_digests(prepared, tmp_path):
    plan, _, _, _ = prepared
    e.validate_scope_reference(plan['scope'])
    e.validate_accounting_reference(plan['accounting'])
    changed = e.disabled_scope()
    changed['scope']['episode']['policy_seed'] += 1
    with pytest.raises(ValueError, match='pinned'):
        e.validate_scope_reference(put(tmp_path, 'changed-scope', changed))
    # Same semantics with different bytes is not the pinned document.
    path = tmp_path / 'whitespace.json'
    path.write_text(json.dumps(e.disabled_accounting(), indent=2))
    with pytest.raises(ValueError, match='pinned'):
        e.validate_accounting_reference(c.ref(path))
    expected = e.SPECIFICATION.copy()
    e.disabled_scope()['specification']['sha256'] = '0' * 64
    assert e.SPECIFICATION == expected


@pytest.mark.parametrize('mutation', ['none', 'prefix', 'foreign_attempt', 'foreign_health', 'foreign_reservation',
                                      'health_after_attempt', 'aborted_health', 'unsettled_health'])
def test_live_suffixes_exact_and_no_foreign_accounting(prepared, tmp_path, mutation):
    plan, _, _, _ = prepared
    # Small synthetic baseline; validate_authority separately requires the real
    # pinned 506-attempt snapshot. This exercises its exact suffix comparator.
    old = {'event': 'historical-fixture'}
    baseline = {name: [old.copy()] for name in e.JOURNALS}
    local = episode_fixture(plan)
    health = health_fixture(plan, tmp_path)
    for event in health: event['time_unix'] = 90
    # The suffix validator also binds the detached plan and prospective time.
    # This disabled fixture is never submitted to release/admission validators.
    plan_ref = put(tmp_path, 'suffix-disabled-plan', plan)
    release_ref = put(tmp_path, 'suffix-disabled-release', {
        'schema': 'n36-engineering-episode-release-v1', 'plan': plan_ref,
        'issued_at': '1970-01-01T00:01:35+00:00', 'release_enabled': False})
    for event in local:
        event.update(release=release_ref, plan_sha256=plan_ref['sha256'])
    events, resources, reservations = [old.copy(), *local], [old.copy(), *health], [old.copy()]
    if mutation == 'prefix': events[0]['event'] = 'rewritten'
    elif mutation == 'foreign_attempt': events.append({**local[0], 'attempt_id': 'foreign'})
    elif mutation == 'foreign_health': resources.append({**health[0], 'resource_id': 'foreign'})
    elif mutation == 'foreign_reservation': reservations.append({'event': 'new-reservation'})
    elif mutation == 'health_after_attempt': resources[-1]['time_unix'] = 101
    elif mutation == 'aborted_health': resources[-1]['event'] = 'aborted'
    elif mutation == 'unsettled_health': resources.pop()
    if mutation == 'none':
        assert e._journal_suffixes(plan, baseline, events, resources, reservations) == (local, health)
    else:
        with pytest.raises(ValueError): e._journal_suffixes(plan, baseline, events, resources, reservations)


@pytest.mark.parametrize('name', e.JOURNALS)
def test_retained_prefix_bytes_never_mutated(tmp_path, name):
    import hashlib
    path = tmp_path / name
    content = b'{"cpu_fixture":true}\n'
    path.write_bytes(content)
    anchor = {'path': str(path), 'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()}
    full.prefix(path, anchor)
    with path.open('ab') as stream: stream.write(b'{"prospective_suffix":true}\n')
    full.prefix(path, anchor)
    path.write_bytes(b'X' + path.read_bytes()[1:])
    with pytest.raises(ValueError): full.prefix(path, anchor)


@pytest.mark.parametrize('crash', ['reserved', 'dispatched', 'terminal_before_artifact', 'valid', 'aborted'])
def test_actual_journal_primitives_charge_once_and_restart_stop(prepared, tmp_path, crash):
    """Real locks/fsync/journal/state/terminal artifact, synthetic outcome only.

    This does not run execute_one or replace its production release/receipt
    validators. The callback checks local artifact equality, not GPU validity.
    """
    import yaml
    plan, _, _, _ = prepared
    root = tmp_path / 'owner-fixture'
    (root / 'data').mkdir(parents=True)
    for name in e.JOURNALS: (root / 'data' / name).write_text('')
    (root / 'research-state.yaml').write_text(yaml.safe_dump({'budget': {}}))
    events = episode_fixture(plan)
    length = {'reserved': 1, 'dispatched': 2}.get(crash, 3)
    if crash == 'aborted':
        events[-1].update(event='aborted', outcome_valid=False, success=None)
    with r.locked(root / 'data/qd-ed-runner.lock', nonblocking=True):
        with r.locked(root / 'data/qd-ed-state.lock'):
            for event in events[:length]: r.append_event_locked(root, event)
            if crash in ('valid', 'aborted'):
                w.atomic_json(root / 'terminal.json', events[-1])
    retained = r.read_events(root / 'data/attempt-ledger.jsonl')
    snap = r.budget_snapshot(retained)
    assert snap['reserved_attempts'] == 1 and snap['dispatched'] == (length >= 2)
    assert snap['gpu_hours_consumed'] == (0.5 if length == 3 else 0)
    def verify_local_artifact(row, terminal):
        assert json.loads((root / 'terminal.json').read_text()) == terminal
    result = e.reconcile(plan, retained, verify_local_artifact)
    expected = ('LIVE_OR_UNSETTLED' if length < 3 else
                'PAUSED_FOR_ROOT_G3' if crash == 'valid' else 'INVALID_STOP')
    assert result['status'] == expected and result['next_row'] is None
    assert result['scope_exhausted'] is True and result['continuation_authorized'] is False
    # Replaying the first reservation cannot debit a second episode or restart.
    with r.locked(root / 'data/qd-ed-state.lock'):
        with pytest.raises(r.GateError): r.append_event_locked(root, events[0])
    assert r.read_events(root / 'data/attempt-ledger.jsonl') == retained


@pytest.mark.parametrize('ending', ['reserved', 'dispatched', 'completed', 'aborted'])
def test_actual_health_journal_primitives_preserve_spent_slot(prepared, tmp_path, ending):
    import yaml
    plan, _, _, _ = prepared
    root = tmp_path / 'health-owner-fixture'
    (root / 'data').mkdir(parents=True)
    for name in e.JOURNALS: (root / 'data' / name).write_text('')
    (root / 'research-state.yaml').write_text(yaml.safe_dump({'budget': {}}))
    events = health_fixture(plan, tmp_path)
    length = {'reserved': 1, 'dispatched': 2}.get(ending, 3)
    if ending == 'aborted': events[-1]['event'] = 'aborted'
    for event in events[:length]: r.append_healthcheck_event(root, event)
    retained = r.read_events(root / 'data/gpu-healthcheck-ledger.jsonl')
    assert e.resource_events(plan, retained) == retained
    snap = r.budget_snapshot([], retained)
    assert snap['gpu_healthcheck_inflight'] == (length < 3)
    assert snap['gpu_hours_consumed'] == (60 / 3600 if length == 3 else 0)
    with pytest.raises(r.GateError): r.append_healthcheck_event(root, events[0])
    assert r.read_events(root / 'data/gpu-healthcheck-ledger.jsonl') == retained


@pytest.mark.parametrize('kind', ['legacy_context_engineering_plan', 'engineering_context_legacy_plan', 'unknown_field'])
def test_worker_schema_cross_use_rejected_before_authority(prepared, tmp_path, kind):
    plan, audit, _, _ = prepared
    context = {'schema': e.CONTEXT_SCHEMA, 'plan': put(tmp_path, 'plan-disabled', plan),
               'release': plan['authority'], 'expected_manifest': plan['engineering_manifest'],
               'episode_key': e.EPISODE_KEY, 'attempt_id': e.EPISODE_KEY,
               'main_argv': [], 'worker_contract': c.WORKER_CONTRACT,
               'purpose': e.PURPOSE, 'scope': plan['scope'], 'audit_plan': plan['audit_plan']}
    if kind == 'legacy_context_engineering_plan':
        context['schema'] = 'n36-worker-context-v1'
    elif kind == 'engineering_context_legacy_plan':
        context['plan'] = audit['original_plan']
    else: context['unknown'] = True
    with pytest.raises(ValueError): worker.validate_context(put(tmp_path, 'context-disabled', context))


@pytest.mark.parametrize('mutation', ['unknown', 'purpose', 'cohort', 'boolean_task', 'limit', 'phase', 'released_flag',
                                      'scope_hash', 'accounting_hash', 'output', 'old_manifest'])
def test_disabled_command_rejects_mixed_execution_shape(prepared, mutation):
    plan, _, runtime, _ = prepared
    if mutation == 'unknown': plan['extra_field'] = 'not allowed'
    elif mutation == 'purpose': plan['purpose'] = 'dev'
    elif mutation == 'cohort': plan['cohort'] = c.DRAFT_N36R4_COHORT
    elif mutation == 'boolean_task': plan['episodes'][0]['task_id'] = False
    elif mutation == 'limit': plan['limits']['wall_seconds'] = 1900
    elif mutation == 'phase': plan['phase_authorization']['dev'] = True
    elif mutation == 'released_flag': plan['release_enabled'] = True
    elif mutation == 'scope_hash': plan['scope']['sha256'] = '0' * 64
    elif mutation == 'accounting_hash': plan['accounting']['sha256'] = '0' * 64
    elif mutation == 'output': plan['artifact_root'] = str(e.SOURCE)
    elif mutation == 'old_manifest': plan['expected_manifests'] = {'old_key': plan['engineering_manifest']}
    with pytest.raises(ValueError): b.engineering_command(plan, runtime, e.row())


def test_explicit_audit_argument_cannot_replace_hash_anchor(prepared):
    plan, audit, runtime, _ = prepared
    audit['expected_manifests'][audit['episodes'][-1]['episode_key']]['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='hash-bound full audit view'):
        b.engineering_command(plan, runtime, e.row(), audit=audit)


def test_disabled_artifacts_cannot_override_source_startup_or_released_schema(prepared, tmp_path):
    from scripts import qd_ed_n36_runner as runner, qd_ed_n36_healthcheck as healthcheck
    plan, _, _, _ = prepared
    plan['root_G3_approved'] = True
    plan['implementation_approved'] = True
    reference = put(tmp_path, 'still-disabled', plan)
    for call in (lambda: e.execute_one(reference, reference),
                 lambda: runner.execute_one(reference, reference, _engineering=True),
                 lambda: e.reserve_health(reference, reference, e.HEALTH_ID, timeout_seconds=20),
                 lambda: healthcheck.run_healthcheck(reference, reference, e.HEALTH_ID, timeout_seconds=20),
                 lambda: e.launch_guard(plan, {})):
        with pytest.raises((RuntimeError, ValueError), match='source-only startup absent|distinct released engineering plan required'):
            call()


# G1 fixtures exercise only route/state gates, without production plans or journals.
ACTUAL_HISTORICAL_OWNER = '/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z'
ACTUAL_CANONICAL_OWNER = ('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/'
    'eds-qd-autoresearch-libero-swap-ood/research_sessions/'
    'rdt-qd-ed-final-20260921T093925Z/study_worktree')


@pytest.fixture
def owner_route_state():
    caps = copy.deepcopy(c.CAPS)
    plan = {'authority': {'path': '/synthetic/not-an-approval.json', 'sha256': '0' * 64}}
    authority = {'caps': caps, 'amendment': {'synthetic': True}}
    state = {'worktree': ACTUAL_HISTORICAL_OWNER, 'canonical_worktree': ACTUAL_CANONICAL_OWNER,
             'n36_engineering_budget_authority': copy.deepcopy(plan['authority']),
             'gpu_pool': [7], 'max_concurrent_gpu_workers': 1,
             'budget': {'max_episode_attempts': caps['attempts'], 'max_gpu_hours': caps['gpu_hours'],
                        'reserved': copy.deepcopy(caps['buckets']),
                        'gpu_hour_reservations': copy.deepcopy(caps['protected_gpu_hours']),
                        'amendment': copy.deepcopy(authority['amendment'])},
             'resource_isolation': {'status': 'ACTIVE', 'validation_status': 'PASS', 'private_budget': True}}
    return plan, authority, state


def check_owner_route(fixture):
    before = copy.deepcopy(fixture)
    try:
        return e.validate_state(*fixture)
    finally:
        assert fixture == before


@pytest.mark.parametrize('spelling', ['historical', 'canonical'])
def test_owner_route_actual_strings_and_pinned_mapping(owner_route_state, spelling):
    assert str(e.OWNER) == ACTUAL_CANONICAL_OWNER
    assert e.HISTORICAL_OWNER == ACTUAL_HISTORICAL_OWNER
    assert e.OWNER_ROUTE_MAPPING == {
        'path': str(e.OWNER.parent / 'autonomy_20261004/turns/001352/owner-alias-repair/alias-evidence-v1.json'),
        'sha256': '70097b35181e55589df8bb053857b11840f08542fb8ed8bec57635ba493b22a2'}
    if spelling == 'canonical':
        owner_route_state[2]['worktree'] = ACTUAL_CANONICAL_OWNER
    assert check_owner_route(owner_route_state) is None


@pytest.mark.parametrize('field', ['worktree', 'canonical_worktree'])
@pytest.mark.parametrize('fault', ['absent', 'null', 'foreign', 'normalized', 'other-alias'])
def test_owner_route_rejects_foreign_lexical_strings(owner_route_state, tmp_path, field, fault):
    state = owner_route_state[2]
    other = tmp_path / 'unlisted-alias'
    other.symlink_to(e.OWNER, target_is_directory=True)
    if fault == 'absent':
        del state[field]
    else:
        state[field] = {'null': None, 'foreign': str(e.SOURCE),
                        'normalized': state[field] + '/.', 'other-alias': str(other)}[fault]
    with pytest.raises(ValueError, match='owning state .* worktree differs'):
        check_owner_route(owner_route_state)


@pytest.mark.parametrize('fault', ['absent', 'tampered', 'foreign-lexical', 'foreign-canonical',
                                  'foreign-resolved', 'samefile', 'schema', 'malformed-reference'])
def test_owner_route_mapping_rejections(owner_route_state, tmp_path, monkeypatch, fault):
    # Synthetic mapping only: no production binding or authority is created.
    mapping = {'schema': 'n36r3-owner-alias-evidence-v1',
               'lexical_worktree': ACTUAL_HISTORICAL_OWNER,
               'canonical_worktree': ACTUAL_CANONICAL_OWNER,
               'resolved_worktree': ACTUAL_CANONICAL_OWNER, 'samefile': True}
    if fault.startswith('foreign-'):
        field = {'foreign-lexical': 'lexical_worktree', 'foreign-canonical': 'canonical_worktree',
                 'foreign-resolved': 'resolved_worktree'}[fault]
        mapping[field] = str(e.SOURCE)
    elif fault == 'samefile':
        mapping['samefile'] = 1
    elif fault == 'schema':
        mapping['schema'] = 'foreign-schema'
    binding = put(tmp_path, 'synthetic-owner-mapping', mapping)
    if fault == 'absent':
        Path(binding['path']).unlink()
    elif fault == 'tampered':
        Path(binding['path']).write_text('{}')
    elif fault == 'malformed-reference':
        del binding['sha256']
    monkeypatch.setattr(e, 'OWNER_ROUTE_MAPPING', binding)
    with pytest.raises(ValueError, match='reference|authorized owner mapping differs'):
        check_owner_route(owner_route_state)


@pytest.mark.parametrize('fault', ['dangling', 'retargeted', 'regular-file', 'loop', 'samefile-error'])
def test_owner_route_live_identity_rechecked(owner_route_state, tmp_path, monkeypatch, fault):
    owner = tmp_path / 'owner'
    owner.mkdir()
    alias = tmp_path / 'historical-alias'
    alias.symlink_to(owner, target_is_directory=True)
    monkeypatch.setattr(e, 'OWNER', owner)
    monkeypatch.setattr(e, 'HISTORICAL_OWNER', str(alias))
    mapping = {'schema': 'n36r3-owner-alias-evidence-v1', 'lexical_worktree': str(alias),
               'canonical_worktree': str(owner), 'resolved_worktree': str(owner), 'samefile': True}
    monkeypatch.setattr(e, 'OWNER_ROUTE_MAPPING', put(tmp_path, 'synthetic-owner-mapping', mapping))
    owner_route_state[2].update(worktree=str(alias), canonical_worktree=str(owner))
    check_owner_route(owner_route_state)
    alias.unlink()
    if fault == 'dangling':
        alias.symlink_to(tmp_path / 'absent')
    elif fault == 'retargeted':
        alias.symlink_to(tmp_path, target_is_directory=True)
    elif fault == 'regular-file':
        alias.write_text('not a directory')
    elif fault == 'loop':
        alias.symlink_to(alias)
    else:
        alias.symlink_to(owner, target_is_directory=True)
        def stat_error(*args):
            raise OSError('synthetic identity error')
        monkeypatch.setattr(Path, 'samefile', stat_error)
    with pytest.raises(ValueError, match='alias identity differs'):
        check_owner_route(owner_route_state)


@pytest.mark.parametrize('fault', ['adoption', 'caps', 'gpu', 'workers', 'attempts', 'hours',
                                  'reserved', 'protected', 'amendment', 'isolation', 'hold'])
def test_owner_route_preserves_state_gates(owner_route_state, fault):
    plan, authority, state = owner_route_state
    if fault == 'adoption':
        del state['n36_engineering_budget_authority']
    elif fault == 'caps':
        authority['caps']['attempts'] += 1
    elif fault == 'gpu':
        state['gpu_pool'] = [0]
    elif fault == 'workers':
        state['max_concurrent_gpu_workers'] = 2
    elif fault in ('attempts', 'hours'):
        state['budget'][{'attempts': 'max_episode_attempts', 'hours': 'max_gpu_hours'}[fault]] += 1
    elif fault in ('reserved', 'protected', 'amendment'):
        state['budget'][{'reserved': 'reserved', 'protected': 'gpu_hour_reservations',
                         'amendment': 'amendment'}[fault]] = {}
    elif fault == 'isolation':
        state['resource_isolation']['private_budget'] = False
    else:
        state['external_resource_hold'] = {'do_not_auto_resume': True}
    with pytest.raises((ValueError, r.GateError)):
        check_owner_route(owner_route_state)


def test_owner_route_admission_does_not_supply_released_plan(owner_route_state):
    check_owner_route(owner_route_state)
    with pytest.raises((RuntimeError, ValueError), match='source-only startup absent|distinct released engineering plan required'):
        e.launch_guard(owner_route_state[0], owner_route_state[1])
