"""CPU-only prospective recovery tests. No releases, device or model execution."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts import qd_ed_n36_engineering as parent
from scripts import qd_ed_n36_engineering_r1 as e
from scripts import qd_ed_n36_engineering_api as routing
from scripts import qd_ed_n36_bridge as b, qd_ed_n36_worker as worker
from scripts.qd_ed_n36_dino import DinoSources
from test_n36_engineering import documents as parent_documents, put


@pytest.fixture(scope='module')
def baseline():
    return e.terminal_parent_prefix()


@pytest.fixture(scope='module')
def documents(tmp_path_factory):
    plan, audit, _, _ = parent_documents.__wrapped__(tmp_path_factory)
    plan, audit = copy.deepcopy((plan, audit))
    root = tmp_path_factory.mktemp('r1-disabled')
    route = e.read(plan['deployment'])
    route.update(source_cwd=str(e.SOURCE), output_root=str(e.SESSION / 'engineering-executions' / e.EPISODE_KEY))
    policy = e.specification()['runtime_binding']
    runtime_ref = {'path': policy['runtime_path'], 'sha256': e.w.sha(policy['runtime_path'])}
    source = e.read({'path': policy['source_record_path'], 'sha256': e.w.sha(policy['source_record_path'])})
    common = dict(worktree=str(e.SOURCE), runtime=runtime_ref, source=source, scientific_source=source,
                  deployment=put(root, 'route', route), scope=put(root, 'scope', e.disabled_scope()))
    audit.update(common, artifact_root=route['output_root'] + '/audit-only', expected_manifests={})
    runtime = e.read(audit['runtime'])
    for i, row in enumerate(audit['episodes']):
        audit['expected_manifests'][row['episode_key']] = put(root, f'audit-{i}', b.manifest(audit, runtime, row))
    plan.update(common, cohort=e.IDENTITY, episodes=[e.row()], artifact_root=route['output_root'],
                accounting=put(root, 'accounting', e.disabled_accounting()),
                audit_plan=put(root, 'audit', audit), expected_manifests={})
    manifest = b.engineering_manifest(plan, runtime, e.row())
    plan['engineering_manifest'] = put(root, 'manifest', manifest)
    plan['expected_manifests'] = {e.EPISODE_KEY: plan['engineering_manifest']}
    return plan, audit, runtime


def episode(plan):
    row = e.row()
    base = {**e.operational_binding(plan), 'attempt_id': e.EPISODE_KEY, 'episode_key': e.EPISODE_KEY,
            'identity': e._identity(row), 'budget_bucket': 'baseline', 'replacement': None,
            'plan_sha256': '0' * 64, 'release': {'disabled_fixture': True},
            'source_commit': plan['source']['commit'], 'runtime_manifest_sha256': plan['runtime']['sha256'],
            'runtime_inventory_sha256': plan['runtime_inventory_sha256'],
            'init_row_sha256': row['init_row_sha256'], 'output_dir': plan['artifact_root'] + '/attempts/' + e.EPISODE_KEY,
            'physical_gpu': 7, 'ledger_prefix': {'disabled_fixture': True}, 'context': {'disabled_fixture': True},
            'reserved_gpu_seconds': 1840, 'accounting_admission': {'reserved_gpu_seconds': 1840},
            'time_unix': 100, 'timeout_seconds': 1800, 'gpu_process_wall_seconds': 12,
            'outcome_valid': True, 'required_cost_telemetry_complete': True, 'success': False}
    return [{**base, 'event': kind} for kind in ('reserved', 'dispatched', 'valid')]


def test_exact_terminal_history_retains_charges_and_parent_exhaustion(baseline):
    amendment = e.read(e.AMENDMENT)
    old_plan = e.read(amendment['parent_plan'])
    old = baseline[e.JOURNALS[0]]
    result = parent.reconcile(old_plan, old, lambda *args: pytest.fail('parent invalid outcome replay'))
    assert result['status'] == 'INVALID_STOP' and result['scope_exhausted']
    assert result['next_row'] is None and result['outcomes'] == []
    snap = e.r.budget_snapshot(old, baseline[e.JOURNALS[1]])
    assert snap['reserved_attempts'] == snap['dispatched'] == 507
    assert snap['gpu_hours_consumed'] == 75.64264702604362
    assert snap['gpu_healthcheck_hours'] == .24847032518900042
    assert old[-1]['required_cost_telemetry_complete'] is False
    assert e.disabled_accounting()['accounting']['retained_admission_margin_gpu_hours'] == '0.23357169027962'
    assert e.disabled_accounting()['root_adopted'] is False


@pytest.mark.parametrize('length,status', [(0, 'READY_FOR_ROOT_RELEASE'), (1, 'LIVE_OR_UNSETTLED'),
    (2, 'LIVE_OR_UNSETTLED'), (3, 'PAUSED_FOR_ROOT_G3')])
def test_fresh_one_use_and_no_parent_outcome_replay(documents, baseline, length, status):
    plan = documents[0]
    checked = []
    result = e.reconcile(plan, baseline[e.JOURNALS[0]] + episode(plan)[:length], lambda row, final: checked.append(final))
    assert result['status'] == status
    assert result['scope_exhausted'] == bool(length)
    assert (result['next_row'] is None) == bool(length)
    assert len(checked) == (length == 3)
    assert result['outcomes'] == [] and not result['scientific_eligible']
    assert not result['continuation_authorized']


@pytest.mark.parametrize('mutation', ['absent', 'truncated', 'tampered', 'live_parent', 'foreign_parent',
    'unknown_suffix', 'foreign_live_suffix', 'old_replay', 'r1_replay'])
def test_history_and_suffix_fail_closed(documents, baseline, mutation):
    plan = documents[0]
    events = copy.deepcopy(baseline[e.JOURNALS[0]])
    if mutation == 'absent': events = []
    elif mutation == 'truncated': events.pop()
    elif mutation == 'tampered': events[-1]['gpu_process_wall_seconds'] = 0
    elif mutation == 'live_parent': events[-1]['event'] = 'dispatched'
    elif mutation == 'foreign_parent': events[-1]['attempt_id'] = 'foreign'
    elif mutation == 'unknown_suffix': events.append({'event': 'aborted', 'attempt_id': 'unknown'})
    elif mutation == 'foreign_live_suffix': events.append({'event': 'reserved', 'attempt_id': 'foreign'})
    elif mutation == 'old_replay': events += copy.deepcopy(events[-3:])
    else: events += episode(plan) * 2
    with pytest.raises(ValueError):
        e.reconcile(plan, events, lambda *args: pytest.fail('must not replay'))


def test_invalid_r1_and_live_handle_never_continue(documents, baseline):
    plan = documents[0]
    old = baseline[e.JOURNALS[0]]
    events = episode(plan)
    events[-1]['event'] = 'aborted'
    result = e.reconcile(plan, old + events, lambda *args: pytest.fail('invalid replay'))
    assert result['status'] == 'INVALID_STOP' and result['next_row'] is None
    result = e.reconcile(plan, old, lambda *args: None, live_handles=[{'unknown': True}])
    assert result['status'] == 'LIVE_OR_UNSETTLED' and result['next_row'] is None


@pytest.mark.parametrize('journal', e.JOURNALS)
def test_exact_byte_proof_required_even_when_parsed_history_unchanged(tmp_path, monkeypatch, journal):
    amendment = e.read(e.AMENDMENT)
    spec = e.specification()
    anchor = amendment['ledger_prefixes'][journal]
    path = tmp_path / journal
    path.write_bytes(b' ' + Path(anchor['path']).read_bytes())
    anchor['path'] = str(path)  # retain the original hash/size: lexical data is not proof
    terminal = e.read(amendment['parent_terminal'])
    terminal['ledger_prefixes'] = copy.deepcopy(amendment['ledger_prefixes'])
    amendment['parent_terminal'] = put(tmp_path, 'terminal', terminal)
    spec['retained_ledger_prefixes'] = amendment['ledger_prefixes']
    amendment_ref = put(tmp_path, 'amendment', amendment)
    spec['prospective_amendment'] = amendment_ref
    monkeypatch.setattr(e, 'AMENDMENT', amendment_ref)
    monkeypatch.setattr(e, 'SPECIFICATION', put(tmp_path, 'spec', spec))
    with pytest.raises(ValueError, match='historical ledger prefix changed'):
        e.terminal_parent_prefix()


@pytest.mark.parametrize('journal', e.JOURNALS)
def test_foreign_suffix_all_journals_rejected(documents, baseline, journal):
    current = copy.deepcopy(baseline)
    current[journal].append({'event': 'reserved', 'attempt_id': 'foreign', 'resource_id': 'foreign'})
    with pytest.raises(ValueError):
        e._journal_suffixes(documents[0], baseline, *(current[name] for name in e.JOURNALS))


def test_exact_empty_suffix_admissible(documents, baseline):
    assert e._journal_suffixes(documents[0], baseline, *(baseline[n] for n in e.JOURNALS)) == ([], [])


def test_original_science_and_full_audit_preserved(documents):
    plan, audit, runtime = documents
    original = e.audit_mapping(plan, audit, e.row())
    assert {**original, 'iteration': e.IDENTITY, 'episode_key': e.EPISODE_KEY} == e.row()
    assert len(audit['expected_manifests']) == 40
    old = b.command(audit, runtime, original)[0]
    new = b.engineering_command(plan, runtime, e.row())[0]
    assert {a.split('=')[0] for a, v in zip(old, new) if a != v} == set(b._ENGINEERING_ROUTES + b._ENGINEERING_IDENTITIES)
    assert b.verify_engineering_manifest(plan['engineering_manifest'], plan, runtime, e.row())['scientific_eligible'] is False
    assert routing.for_plan(plan) is e and routing.for_plan(audit) is e


@pytest.mark.parametrize('field,value', [('task_id', 1), ('profile', 'Q0'), ('env_seed', 0),
    ('policy_seed', 0), ('init_index', 1), ('timeout_seconds', 1799), ('iteration', parent.IDENTITY),
    ('episode_key', parent.EPISODE_KEY), ('budget_bucket', 'recovery')])
def test_recovery_science_mutations_rejected(documents, field, value):
    plan, audit, _ = documents
    row = e.row()
    row[field] = value
    with pytest.raises(ValueError): e.audit_mapping(plan, audit, row)


def test_disabled_and_cross_family_plans_rejected(documents, tmp_path):
    plan, audit, _ = documents
    e.validate_plan_shape(plan)
    ref = put(tmp_path, 'disabled', plan)
    assert worker.release_api(ref) is e
    for api in (parent, e):
        with pytest.raises(ValueError): api.validate_release(ref, ref)
    bad = {**plan, 'cohort': 'N36_ENGINEERING_UNKNOWN'}
    with pytest.raises(ValueError): routing.for_plan(bad)
    bad = {**audit, 'scope': put(tmp_path, 'foreign-scope', {'specification': {'path': '/foreign', 'sha256': '0'*64}})}
    with pytest.raises(ValueError): routing.for_plan(bad)


def test_real_dino_consumer_canonical_reference_and_unchanged_bytes():
    reference = e.read(e.specification()['runtime_binding']['historical_specification'])['canonical_runtime']
    before = Path(reference['path']).read_bytes()
    consumer = DinoSources(reference)
    assert len(consumer.files) == 157
    alias = e.read(e.read(e.AMENDMENT)['parent_plan'])['runtime']
    assert alias['sha256'] == reference['sha256'] and alias['path'] != reference['path']
    with pytest.raises(ImportError, match='manifest path not canonical'): DinoSources(alias)
    assert Path(reference['path']).read_bytes() == before
    assert hashlib.sha256(before).hexdigest() == reference['sha256']


def test_real_dino_synthetic_source_bytes_and_alias(tmp_path):
    home = tmp_path / 'torch'
    root = home / 'hub/facebookresearch_dinov2_main'
    files = []
    for name in ('hubconf.py', 'dinov2/__init__.py'):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# synthetic CPU source\n')
        files.append(dict(path=str(path), resolved_path=str(path), sha256=e.w.sha(path), size_bytes=path.stat().st_size))
    ref = put(tmp_path, 'runtime', dict(schema='qd-ed-runtime-setup-v1', environment={'TORCH_HOME': str(home)}, files=files))
    consumer = DinoSources(ref)
    consumer.check_file('hubconf.py', str(root / 'hubconf.py'))
    alias = tmp_path / 'alias.json'
    alias.symlink_to(ref['path'])
    with pytest.raises(ImportError, match='not canonical'): DinoSources({**ref, 'path': str(alias)})
    (root / 'hubconf.py').write_text('# tampered\n')
    with pytest.raises(ImportError, match='source bytes differ'): consumer.check_file('hubconf.py', str(root / 'hubconf.py'))


def test_plan_runtime_alias_rejected_before_dispatch(documents):
    plan, audit, _ = copy.deepcopy(documents)
    alias = e.read(e.read(e.AMENDMENT)['parent_plan'])['runtime']
    plan['runtime'] = audit['runtime'] = alias
    with pytest.raises(ValueError, match='canonical runtime'): e.validate_plan_shape(plan)
    with pytest.raises(ValueError, match='canonical runtime'): e.validate_audit_view(audit)


def test_parent_source_and_shared_safety_predicates_unchanged():
    import ast
    parent_path = Path(parent.__file__)
    assert e.w.sha(parent_path) == 'd93eed25e93fb4a211180cc9abdc76d767ca278a7663dbedd1f29aee53874af1'
    def functions(path):
        return {node.name: ast.dump(node, include_attributes=False)
                for node in ast.parse(Path(path).read_text()).body if isinstance(node, ast.FunctionDef)}
    old, new = functions(parent_path), functions(e.__file__)
    intentional = {'specification', 'validate_audit_view', 'validate_plan_shape', 'validate_authority',
                   '_journal_suffixes', 'reconcile', 'validate_readiness'}
    assert set(old) == set(new) - {'terminal_parent_prefix', 'validate_runtime_binding'}
    for name in old.keys() - intentional:
        assert new[name] == old[name], name
    assert e.LIMITS == parent.LIMITS
    assert e.c.WORKER_CONTRACT == parent.c.WORKER_CONTRACT


@pytest.mark.parametrize('mutation', ['old_identity', 'old_kind', 'replay', 'short_timeout', 'short_cleanup', 'excess_cost'])
def test_fresh_health_is_distinct_and_one_use(documents, tmp_path, mutation):
    plan = documents[0]
    plan_ref = put(tmp_path, 'health-disabled-plan', plan)
    base = {**e.operational_binding(plan), 'resource_id': e.HEALTH_ID, 'kind': e.HEALTH_KIND,
            'source_commit': plan['source']['commit'], 'runtime': plan['runtime'], 'plan': plan_ref,
            'release': {'disabled_fixture': True}, 'timeout_seconds': 20, 'cleanup_seconds': 40,
            'reserved_gpu_seconds': 60, 'physical_gpu': 7, 'gpu_uuid': e.c.GPU_UUID,
            'accounting_admission': {'reserved_gpu_seconds': 60}, 'gpu_process_wall_seconds': 10}
    events = [{**base, 'event': kind} for kind in ('reserved', 'dispatched', 'completed')]
    assert e.resource_events(plan, events) == events
    if mutation == 'old_identity': events[0]['resource_id'] = parent.HEALTH_ID
    elif mutation == 'old_kind': events[0]['kind'] = parent.HEALTH_KIND
    elif mutation == 'replay': events += copy.deepcopy(events)
    elif mutation == 'short_timeout': events[0]['timeout_seconds'] = 19
    elif mutation == 'short_cleanup': events[0]['cleanup_seconds'] = 39
    else: events[-1]['gpu_process_wall_seconds'] = 61
    with pytest.raises(ValueError): e.resource_events(plan, events)


def test_r1_non_c0_manifest_still_verified(documents, tmp_path):
    _, audit, runtime = documents
    row = audit['episodes'][1]
    manifest = e.read(audit['expected_manifests'][row['episode_key']])
    manifest['resolved_config']['nonprogress_tangent_mode'] = 'tampered'
    with pytest.raises(ValueError, match='external manifest differs'):
        b._verify_manifest_bound(put(tmp_path, 'corrupt-q0', manifest), audit, runtime, row)


def test_terminal_report_hash_cannot_be_substituted(tmp_path, monkeypatch):
    amendment = e.read(e.AMENDMENT)
    spec = e.specification()
    terminal_ref = amendment['parent_terminal']
    forged = e.read(terminal_ref)
    forged['classification'] = 'VALID'
    path = tmp_path / 'forged-terminal.json'
    path.write_text(json.dumps(forged))
    amendment['parent_terminal'] = {**terminal_ref, 'path': str(path)}
    amref = put(tmp_path, 'amendment', amendment)
    spec['prospective_amendment'] = amref
    monkeypatch.setattr(e, 'AMENDMENT', amref)
    monkeypatch.setattr(e, 'SPECIFICATION', put(tmp_path, 'spec', spec))
    with pytest.raises(ValueError, match='hash/path differs'): e.terminal_parent_prefix()


def test_health_alone_does_not_remove_retained_cost_or_allow_second_use(baseline):
    snap = e.r.budget_snapshot(baseline[e.JOURNALS[0]], baseline[e.JOURNALS[1]])
    local = {'gpu_hours_consumed': 60 / 3600, 'gpu_healthcheck_hours': 60 / 3600, 'reserved_attempts': 0}
    kw = dict(margin=.23357169027962, protected=36.2408240024308155)
    assert e.headroom(snap, local, health=False, **kw)['reserved_gpu_seconds'] == 1840
    with pytest.raises(ValueError): e.headroom(snap, local, health=True, **kw)
    with pytest.raises(ValueError): e.headroom(snap, {**local, 'reserved_attempts': 1}, health=False, **kw)
    with pytest.raises(ValueError): e.headroom(snap, local, health=False, margin=0, protected=kw['protected'])


def test_prospective_binding_accepts_exact_committed_source(documents):
    plan, audit, runtime = documents
    assert e.validate_runtime_binding(plan) == runtime
    e.validate_plan_shape(plan)
    e.validate_audit_view(audit)
    template = e.read(e.specification()['canonical_runtime'])
    expected = copy.deepcopy(runtime)
    for name in ('source', 'source_record'):
        expected['preparation'][name] = template['preparation'][name]
    assert expected == template
    assert runtime['cuda_egl_verified'] is runtime['provider_ready'] is False
    assert runtime['preparation']['runtime_ready'] is False


@pytest.mark.parametrize('mutation', ['runtime_hash', 'unapproved_path', 'source_ref_hash',
    'source_ref_path', 'source_commit', 'source_file_hash', 'source_file_missing',
    'runtime_file_hash', 'readiness', 'provider_readiness', 'mapping_readiness',
    'preparation_readiness', 'extra_field', 'provider', 'authority_hash'])
def test_prospective_runtime_mutations_rejected(documents, tmp_path, monkeypatch, mutation):
    plan, _, runtime = copy.deepcopy(documents)
    spec = e.specification()
    policy = spec['runtime_binding']
    # Test-only fixed paths: production authority/template validators stay active.
    policy['runtime_path'] = str(tmp_path / 'runtime.json')
    policy['source_record_path'] = str(tmp_path / 'source.json')
    source = copy.deepcopy(plan['source'])
    if mutation == 'source_commit': source['commit'] = '0' * 40
    if mutation == 'source_file_hash': source['files'][0]['sha256'] = '0' * 64
    if mutation == 'source_file_missing': source['files'].pop()
    source_ref = put(tmp_path, 'source', source)
    plan['source'] = plan['scientific_source'] = source
    runtime['preparation']['source'] = source['commit']
    runtime['preparation']['source_record'] = source_ref
    if mutation == 'source_ref_hash': source_ref['sha256'] = '0' * 64
    if mutation == 'source_ref_path': source_ref['path'] = '/unapproved-source.json'
    if mutation == 'runtime_file_hash': runtime['files'][0]['sha256'] = '0' * 64
    if mutation == 'readiness': runtime['cuda_egl_verified'] = True
    if mutation == 'provider_readiness': runtime['provider_ready'] = True
    if mutation == 'mapping_readiness': runtime['gpu_mapping']['cuda_egl_verified'] = True
    if mutation == 'preparation_readiness': runtime['preparation']['runtime_ready'] = True
    if mutation == 'extra_field': runtime['unapproved'] = True
    if mutation == 'provider': runtime['frozen_stage_provider']['backend'] = 'unapproved'
    if mutation == 'authority_hash': policy['repair_authority']['sha256'] = '0' * 64
    plan['runtime'] = put(tmp_path, 'runtime', runtime)
    if mutation == 'runtime_hash': plan['runtime']['sha256'] = '0' * 64
    if mutation == 'unapproved_path': plan['runtime'] = put(tmp_path, 'other', runtime)
    monkeypatch.setattr(e, 'SPECIFICATION', put(tmp_path, 'spec', spec))
    with pytest.raises(ValueError): e.validate_runtime_binding(plan)


def test_prospective_spec_preserves_all_other_contract_fields():
    new = e.specification()
    old = e.read(new['runtime_binding']['historical_specification'])
    assert {k: v for k, v in new.items() if k not in ('runtime_binding', 'canonical_runtime')} == {
        k: v for k, v in old.items() if k != 'canonical_runtime'}
    assert json.loads(Path('configs/qd_ed_final/n36_engineering_r1_spec.disabled.json').read_text()) == new


def test_altered_local_source_file_rejected(documents):
    path = Path(e.__file__).resolve().parents[1] / 'configs/qd_ed_final/n36_engineering_r1_spec.disabled.json'
    before = path.read_bytes()
    try:
        path.write_bytes(before + b'\n')
        with pytest.raises(ValueError, match='uncommitted source bytes'):
            e.validate_runtime_binding(documents[0])
    finally:
        path.write_bytes(before)


def test_enabled_prospective_plan_without_separate_gates_fails(documents, tmp_path):
    plan, _, _ = copy.deepcopy(documents)
    plan.update(frozen=True, release_enabled=True)
    plan['phase_authorization']['engineering'] = True
    # Shape alone is not approval. Both real release entrypoints must reject it.
    e.validate_plan_shape(plan, released=True)
    plan_ref = put(tmp_path, 'enabled-without-authority', plan)
    missing_release = put(tmp_path, 'no-release', {'approved': False})
    for validator in (e.validate_health_release, e.validate_release):
        with pytest.raises(ValueError, match='independent engineering B5'):
            validator(plan_ref, missing_release)


def test_stale_readiness_source_rejected(documents, tmp_path, monkeypatch):
    plan, _, runtime = documents
    plan_ref = put(tmp_path, 'readiness-plan', plan)
    health_ref = put(tmp_path, 'health-release-fixture', {'disabled_fixture': True})
    output = Path(plan['artifact_root']) / 'healthchecks' / e.HEALTH_ID
    terminal = dict(output_dir=str(output), plan=plan_ref, release=health_ref,
                    source_commit='0' * 40, runtime=plan['runtime'], event='completed',
                    provider_verified=True)
    terminal_ref = {'path': str(output / 'healthcheck-result.json'), 'sha256': '0' * 64}
    original_read = e.read
    monkeypatch.setattr(e, 'validate_health_release', lambda *a: (plan, runtime, {}))
    monkeypatch.setattr(e, 'read', lambda ref: terminal if ref == terminal_ref else original_read(ref))
    with pytest.raises(ValueError, match='terminal readiness binding'):
        e.validate_readiness(plan_ref, {'readiness': {'health_release': health_ref, 'terminal': terminal_ref}}, resources=[])
