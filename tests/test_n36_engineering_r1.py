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


PINNED_SPECIFICATION = dict(e.SPECIFICATION)


@pytest.fixture(scope='module', autouse=True)
def prospective_paths(tmp_path_factory):
    """Synthetic paths only; real committed-source checks remain active."""
    from scripts import qd_ed_n36_readiness_prepare as preparation
    root = tmp_path_factory.mktemp('SYNTHETIC-readiness-paths')
    spec = e.read(PINNED_SPECIFICATION)
    # Legacy lifecycle fixtures exercise the contract-absent branch explicitly.
    # Exact recovery bytes are covered by the isolated recovery_cpu fixtures.
    spec.pop('recovery_prefix_contract', None)
    policy = spec['runtime_binding']
    prep = e.read(policy['preparation'])
    prep['disabled_runtime_path'] = str(root / 'runtime.json')
    policy['runtime_path'] = str(root / 'ready.json')
    policy['source_record_path'] = str(root / 'source.json')
    policy['preparation'] = put(root, 'preparation', prep)
    source = b.closure.source_record(b.ROOT, b.source_paths(b.ROOT))
    source_ref = put(root, 'source', source)
    runtime = e.read(spec['canonical_runtime'])
    runtime['preparation'].update(source=source['commit'], source_record=source_ref)
    put(root, 'runtime', runtime)
    patch = pytest.MonkeyPatch()
    patch.setattr(e, 'SPECIFICATION', put(root, 'spec', spec))
    patch.setattr(e, 'HISTORICAL_SPECIFICATION', e.SPECIFICATION)
    yield
    patch.undo()


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
    runtime_path = e.read(policy['preparation'])['disabled_runtime_path']
    runtime_ref = {'path': runtime_path, 'sha256': e.w.sha(runtime_path)}
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
                   '_journal_suffixes', 'reconcile', 'validate_readiness', 'child_environment'}
    assert set(old) == set(new) - {'terminal_parent_prefix', 'validate_runtime_binding', 'preparation_health_suffix',
        '_recovery_json', '_recovery_rows', '_recovery_read', '_recovery_contract',
        '_recovery_capture', '_recovery_partition', '_recovery_specification', '_recovery_predecessors',
        '_recovery_inventory', '_recovery_inventory_previous'}
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
    preparation = e.read(policy['preparation'])
    preparation['disabled_runtime_path'] = str(tmp_path / 'runtime.json')
    policy['runtime_path'] = str(tmp_path / 'ready.json')
    policy['preparation'] = put(tmp_path, 'preparation', preparation)
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
    new = e.read(PINNED_SPECIFICATION)
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


def test_preparation_exact_two_operational_additions():
    import ast
    import subprocess
    old = ast.parse(subprocess.check_output(['git', 'show',
        'fd75477b84211707afd86bf32b8411403cbf0a1e:scripts/qd_ed_n36_engineering_r1.py'], text=True))
    node = next(n for n in old.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == 'OPERATIONAL_FILES' for t in n.targets))
    previous = ast.literal_eval(node.value.args[0])
    assert e.OPERATIONAL_FILES - previous == {'scripts/qd_ed_n36_readiness_prepare.py',
                                             'tests/test_n36_readiness_prepare.py'}
    assert previous <= e.OPERATIONAL_FILES


@pytest.mark.parametrize('foreign', [False, True])
def test_preparation_scientific_equivalence_gate(tmp_path, monkeypatch, foreign):
    paths = ['scripts/qd_ed_n36_readiness_prepare.py', 'tests/test_n36_readiness_prepare.py']
    if foreign:
        paths.append('core/codex_stage.py')
    source = {'commit': 'SYNTHETIC'}
    ref = put(tmp_path, 'equivalence', dict(schema='n36-engineering-scientific-equivalence-v1',
        base_commit=e.BASE, source=source, changed_paths=sorted(paths), scientific_changes=False))
    monkeypatch.setattr(e.subprocess, 'check_output', lambda *a, **kw: '\n'.join(paths))
    from types import SimpleNamespace
    monkeypatch.setattr(e.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=0))
    if foreign:
        with pytest.raises(ValueError, match='outside operational'):
            e.scientific_equivalence(dict(source=source, scientific_equivalence=ref))
    else:
        e.scientific_equivalence(dict(source=source, scientific_equivalence=ref))


def test_preparation_spec_amendment_only_schema_field():
    import subprocess
    before = json.loads(subprocess.check_output(['git','show',
        'fd75477b84211707afd86bf32b8411403cbf0a1e:configs/qd_ed_final/n36_engineering_r1_spec.disabled.json'], text=True))
    after = e.read(PINNED_SPECIFICATION)
    from scripts.qd_ed_n36_readiness_prepare import MEASUREMENT_CONTRACT
    assert after['runtime_binding'].pop('measurement_contract') == MEASUREMENT_CONTRACT
    assert after == before


# Reuse the complete synthetic measured chain, including real byte/hash validation.
from test_n36_readiness_prepare import measured as measured_preparation


@pytest.fixture
def preparation_history(measured_preparation, baseline, monkeypatch, request):
    import datetime as dt
    from types import SimpleNamespace
    from scripts import qd_ed_n36_readiness_prepare as preparation
    m = measured_preparation
    charge = getattr(request, 'param', 3)
    if charge != 3:
        events = e.read(m['proof']['accounting'])
        events[-1]['gpu_process_wall_seconds'] = charge
        m['proof']['accounting'] = m['save'](m['prep']['accounting_path'], events)
        m['proof_ref'] = m['save'](m['prep']['proof_path'], m['proof'])
        for name in ('readiness-preparation-ledger.jsonl', 'gpu-healthcheck-ledger.jsonl'):
            (m['root']/'data'/name).write_text(''.join(json.dumps(v)+'\n' for v in events))
    monkeypatch.setattr(preparation.time, 'time', lambda: m['now'] + 20)
    runtime = preparation.derive(m['spec'], m['source'], m['source_ref'], m['proof_ref'])
    runtime_ref = m['save'](m['spec']['runtime_binding']['runtime_path'], runtime)
    m['save'](m['prep']['acceptance_path'], dict(schema='n36-preparation-root-acceptance-v1',
        approved=True, specification=e.SPECIFICATION, proof=m['proof_ref'], runtime=runtime_ref,
        release_enabled=False, health_authorized=False, episode_authorized=False))
    inert = put(m['root'], 'inert-binding', {'SYNTHETIC':True})
    plan = dict(schema=e.PLAN_SCHEMA, cohort=e.IDENTITY, purpose=e.PURPOSE, run_name='SYNTHETIC',
        source=m['source'], scientific_source=m['source'], worktree=str(e.SOURCE), runtime=runtime_ref,
        runtime_inventory_sha256='0'*64, artifact_root=str(m['root']/'diagnostic'),
        **{key:inert for key in ('scope','accounting','audit_plan','engineering_manifest','deployment')})
    plan_ref = put(m['root'], 'engineering-plan', plan)
    issued = preparation.timestamp(m['release']['issued_at'])
    iso = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat()
    release_ref = put(m['root'], 'health-release', dict(issued_at=iso(issued+7)))
    output = Path(plan['artifact_root'])/'healthchecks'/e.HEALTH_ID
    output.mkdir(parents=True)
    (output/'probe-frame.png').write_bytes(Path(m['gpu']['frame']['path']).read_bytes())
    evidence = dict(m['gpu']['observation'], resource_id=e.HEALTH_ID, time_unix=issued+10)
    put(output, 'probe-evidence', evidence)
    common = dict(e.operational_binding(plan), resource_id=e.HEALTH_ID, kind=e.HEALTH_KIND,
        plan=plan_ref, release=release_ref, runtime=runtime_ref, source_commit=plan['source']['commit'],
        timeout_seconds=20, cleanup_seconds=40, reserved_gpu_seconds=60, physical_gpu=7,
        gpu_uuid=e.c.GPU_UUID, accounting_admission={'reserved_gpu_seconds':60},
        output_dir=str(output), source_script_sha256=e.w.sha(e.SOURCE/'scripts/qd_ed_gpu_probe.py'),
        provider_verified=True)
    health = [dict(common, event=kind, time_unix=issued+offset,
                   gpu_process_wall_seconds=2 if kind=='completed' else 0)
              for kind,offset in [('reserved',8),('dispatched',9),('completed',11)]]
    health[-1].update({k:v for k,v in evidence.items() if k != 'time_unix'})
    terminal_ref = put(output, 'healthcheck-result', health[-1])
    readiness = dict(readiness=dict(health_release=release_ref, terminal=terminal_ref))
    authority = dict(starts_at=iso(issued))
    # Detached approval/graph fixtures only; the new partition, proof derivation,
    # resource lifecycle, exact terminal, probe fields and arithmetic stay real.
    monkeypatch.setattr(e, 'validate_authority', lambda *args: baseline)
    monkeypatch.setattr(e, 'validate_health_release', lambda *args: (plan,runtime,authority))
    prep = e.read(m['proof']['accounting'])
    current = copy.deepcopy(baseline)
    current[e.JOURNALS[1]] += prep + health
    attempts = episode(plan)
    episode_release = put(m['root'], 'episode-release', dict(schema='n36-engineering-episode-release-v1',
        plan=plan_ref, issued_at=iso(issued+12)))
    for event, offset in zip(attempts,(13,14,15)):
        event.update(release=episode_release, plan_sha256=plan_ref['sha256'], time_unix=issued+offset)
    def sync():
        (m['root']/'data/gpu-healthcheck-ledger.jsonl').write_text(
            ''.join(json.dumps(v)+'\n' for v in current[e.JOURNALS[1]]))
        (m['root']/'data/readiness-preparation-ledger.jsonl').write_text(
            ''.join(json.dumps(v)+'\n' for v in prep))
    sync()
    return SimpleNamespace(m=m, plan=plan, plan_ref=plan_ref, baseline=baseline, current=current,
        prep=prep, health=health, attempts=attempts, readiness=readiness, sync=sync)


@pytest.mark.parametrize('preparation_history', [3, 59], indirect=True)
def test_shared_partition_live_and_terminal_with_episode(preparation_history):
    f = preparation_history
    f.current[e.JOURNALS[0]] += f.attempts
    local, health = e.live_journals(f.plan, {}, *(f.current[n] for n in e.JOURNALS))
    assert local == f.attempts and health == f.health
    assert e.validate_readiness(f.plan_ref, f.readiness, resources=f.current[e.JOURNALS[1]]) == health[-1]
    global_snap = e.r.budget_snapshot(f.current[e.JOURNALS[0]], f.current[e.JOURNALS[1]])
    without_prep = e.r.budget_snapshot(f.current[e.JOURNALS[0]], f.baseline[e.JOURNALS[1]] + health)
    diagnostic = e.r.budget_snapshot(local, health)
    assert global_snap['gpu_hours_consumed'] - without_prep['gpu_hours_consumed'] == pytest.approx(f.prep[-1]['gpu_process_wall_seconds']/3600)
    assert global_snap['gpu_hours_by_bucket']['recovery'] - without_prep['gpu_hours_by_bucket']['recovery'] == pytest.approx(f.prep[-1]['gpu_process_wall_seconds']/3600)
    assert global_snap['reserved_attempts'] == without_prep['reserved_attempts'] == 508
    assert diagnostic['gpu_healthcheck_hours'] == 2/3600
    assert diagnostic['gpu_hours_consumed'] == pytest.approx(14/3600)
    # Successful health permits only the first episode reservation.
    before_episode = e.r.budget_snapshot([], health)
    assert e.headroom(without_prep, before_episode, health=False,
        margin=.23357169027962, protected=36.2408240024308155)['reserved_gpu_seconds'] == 1840
    with pytest.raises(ValueError, match='slot consumed'):
        e.headroom(global_snap, diagnostic, health=False, margin=.23357169027962, protected=0)


def test_preparation_only_is_not_health_readiness(preparation_history):
    f = preparation_history
    f.current[e.JOURNALS[1]] = f.baseline[e.JOURNALS[1]] + f.prep
    f.sync()
    assert e.live_journals(f.plan, {}, *(f.current[n] for n in e.JOURNALS)) == ([], [])
    with pytest.raises(ValueError, match='not durably settled'):
        e.validate_readiness(f.plan_ref, f.readiness, resources=f.current[e.JOURNALS[1]])


@pytest.mark.parametrize('fault', ['pending', 'unknown', 'aborted', 'overrun', 'torn', 'missing_mirror',
    'missing_journal', 'reordered', 'foreign_identity', 'foreign_kind', 'collision', 'mixed_kind',
    'replay', 'prefix', 'release', 'source', 'baseline', 'parent', 'proof', 'after_health',
    'late_time', 'extra_reservation', 'health_replay', 'terminal_substitution', 'expired', 'missing_both'])
def test_shared_partition_rejects_bad_histories_at_both_gates(preparation_history, monkeypatch, fault):
    from scripts import qd_ed_n36_readiness_prepare as preparation
    f = preparation_history
    if fault == 'missing_both': f.prep.clear()
    elif fault == 'pending': f.prep.pop()
    elif fault == 'unknown': f.prep[-1]['event'] = 'unknown'
    elif fault in ('aborted','overrun'):
        f.prep[-1].update(event='aborted', gpu_process_wall_seconds=90 if fault=='overrun' else 3,
            error='SYNTHETIC failure', exclusive=False, telemetry_complete=False,
            gpu=None, provider=None, envelope=None)
    elif fault == 'reordered': f.prep[0],f.prep[1] = f.prep[1],f.prep[0]
    elif fault == 'foreign_identity':
        for row in f.prep: row['resource_id'] = 'foreign'
    elif fault in ('foreign_kind','mixed_kind'): f.prep[1]['kind'] = e.HEALTH_KIND
    elif fault == 'collision':
        for row in f.prep: row['resource_id'] = e.HEALTH_ID
    elif fault == 'replay': f.prep.extend(copy.deepcopy(f.prep))
    elif fault in ('release','source','baseline'):
        key = 'source_record' if fault=='source' else fault
        f.prep[-1][key] = dict(f.prep[-1][key], sha256='0'*64)
    elif fault == 'parent': f.prep[-1]['parent'] = dict(f.prep[-1]['parent'], pid=999)
    elif fault == 'proof':
        proof = e.read(f.m['proof_ref']); proof['accounting']['sha256'] = '0'*64
        f.m['save'](f.m['proof_ref']['path'], proof)
    elif fault == 'late_time': f.health[0]['time_unix'] = f.prep[-1]['time_unix'] - 1
    elif fault == 'health_replay': f.health.extend(copy.deepcopy(f.health))
    elif fault == 'terminal_substitution': f.health[-1]['gpu_process_wall_seconds'] += 1
    elif fault == 'expired':
        monkeypatch.setattr(preparation.time, 'time', lambda: preparation.timestamp(f.m['release']['expires_at'])+1)
    f.current[e.JOURNALS[1]] = copy.deepcopy(f.baseline[e.JOURNALS[1]]) + f.prep + f.health
    if fault == 'prefix': f.current[e.JOURNALS[1]][0]['time_unix'] += 1
    if fault == 'extra_reservation': f.current[e.JOURNALS[2]].append({'event':'foreign'})
    if fault == 'after_health': f.current[e.JOURNALS[1]] = f.baseline[e.JOURNALS[1]] + f.health + f.prep
    f.sync()
    if fault in ('torn','missing_mirror'): f.current[e.JOURNALS[1]].pop(len(f.baseline[e.JOURNALS[1]]) + (1 if fault=='torn' else 2))
    if fault == 'missing_journal': (f.m['root']/'data/readiness-preparation-ledger.jsonl').write_text('')
    before = copy.deepcopy(f.current)
    if fault in ('aborted','overrun'):
        snapshot = e.r.budget_snapshot([], f.prep)
        assert snapshot['gpu_hours_consumed'] == (90 if fault=='overrun' else 3)/3600
        assert snapshot['gpu_healthcheck_inflight'] == 0
    if fault != 'terminal_substitution':
        with pytest.raises((ValueError,e.r.GateError,KeyError)):
            e.live_journals(f.plan, {}, *(f.current[n] for n in e.JOURNALS))
    if fault != 'extra_reservation':  # This independent reservation veto belongs to live_journals.
        with pytest.raises((ValueError,e.r.GateError,KeyError)):
            e.validate_readiness(f.plan_ref, f.readiness, resources=f.current[e.JOURNALS[1]])
    assert f.current == before  # Validation never repairs or truncates accounting.


@pytest.mark.parametrize('cap_kind', ['absolute','weekly','protected'])
def test_preparation_cost_reduces_global_headroom_not_diagnostic(preparation_history, cap_kind):
    from decimal import Decimal
    f = preparation_history
    _, health = e.live_journals(f.plan, {}, *(f.current[n] for n in e.JOURNALS))
    local = e.r.budget_snapshot([], health)
    margin = .23357169027962
    protected = 36.2408240024308155 if cap_kind=='protected' else 0
    cap = e.accounting.ABSOLUTE_HOURS if cap_kind=='absolute' else e.accounting.WEEKLY_HOURS
    # An absolute-boundary case also remains subject to the stricter weekly cap.
    snapshot = e.r.budget_snapshot([], [])
    snapshot['gpu_hours_consumed'] = float(cap - Decimal(str(margin)) - Decimal(str(protected)) - Decimal(1841)/3600)
    if cap_kind != 'absolute':
        e.headroom(snapshot, local, health=False, margin=margin, protected=protected)
    charged = e.r.budget_snapshot([], f.prep)['gpu_hours_consumed']
    snapshot['gpu_hours_consumed'] += charged
    with pytest.raises(ValueError, match='cap/protected reserves'):
        e.headroom(snapshot, local, health=False, margin=margin, protected=protected)
    assert local['gpu_healthcheck_hours'] == 2/3600 and local['reserved_attempts'] == 0


def test_preparation_history_health_handoff_uses_sole_reserved_health(preparation_history, monkeypatch):
    from scripts import qd_ed_n36_runner as runner
    f = preparation_history
    f.health[:] = f.health[:1]
    f.current[e.JOURNALS[1]] = f.baseline[e.JOURNALS[1]] + f.prep + f.health
    f.sync()
    runtime = e.read(f.plan['runtime'])
    authority = {'starts_at': f.m['release']['issued_at']}
    state = {'run_name': f.plan['run_name'], 'artifacts': runtime['artifact_root']}
    monkeypatch.setattr(e, 'validate_state', lambda *args: None)
    monkeypatch.setattr(e.r, 'runtime_gpu', lambda *args: 7)
    monkeypatch.setattr(runner, 'snapshot', lambda *args: (state, *(f.current[n] for n in e.JOURNALS)))
    binding = e.health_handoff_binding(f.plan, runtime, authority, state)
    record = f.health[0]
    result = e.validate_health_handoff(f.m['root'], f.plan_ref, record['release'], record, binding)
    assert result == (f.plan, runtime, authority)
    f.current[e.JOURNALS[1]].append(dict(record, resource_id='foreign'))
    with pytest.raises(ValueError, match='foreign resource'):
        e.validate_health_handoff(f.m['root'], f.plan_ref, record['release'], record, binding)


def test_preparation_authority_cannot_authorize_production(tmp_path):
    contract = e.read(e.specification()['runtime_binding']['accounting_contract'])
    review = e.read(contract['independent_review'])
    plan = e.read(review['actual_graph']['plan'])
    plan.update(authority=None, b5_review=None, frozen=False, release_enabled=False)
    authority = {'schema':'n36-preparation-accounting-authority-v1','approved':True}
    with pytest.raises(ValueError):
        e.validate_authority(plan, authority)
    with pytest.raises(ValueError):
        e.validate_plan_shape(plan, released=True)
    with pytest.raises(ValueError):
        e.validate_state(plan, authority, {'n36_preparation_accounting_adoption':authority})
    plan_ref = put(tmp_path, 'disabled-preparation-plan', plan)
    authority_ref = put(tmp_path, 'preparation-authority', authority)
    for validate in (e.validate_health_release, e.validate_release):
        with pytest.raises(ValueError):
            validate(plan_ref, authority_ref)


@pytest.fixture
def recovery_cpu(tmp_path):
    """AST-isolated CPU fixture: no production/native/provider module imports.

    Actual recovery and lifecycle function bodies run against temporary bytes.
    Detached release/proof/acceptance boundaries are synthetic stand-ins; this
    suite asserts those boundaries are reached, never claims graph validation.
    """
    import ast
    import datetime
    import math
    import types
    source = Path(__file__).resolve().parents[1] / 'scripts/qd_ed_n36_engineering_r1.py'
    # An isolated runner may provide the original source path explicitly.
    source = Path(globals().get('RECOVERY_CPU_SOURCE', source))
    module = ast.parse(source.read_text())
    names = {'exact', 'reference', 'read', 'specification', 'preparation_health_suffix', 'resource_events'}
    nodes = [n for n in module.body if isinstance(n, ast.FunctionDef)
             and (n.name in names or n.name.startswith('_recovery_'))]
    for node in nodes:
        node.body = [n for n in node.body if not isinstance(n, ast.ImportFrom)]
    def require(ok, label):
        if not ok:
            raise ValueError(label)
    def sha(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    def read_ref(ref):
        path = Path(ref['path'])
        require(not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest() == ref['sha256'], 'file reference hash')
        return json.loads(path.read_bytes())
    w = types.SimpleNamespace(require=require, canonical_sha=sha, read_ref=read_ref)
    env = dict(w=w, json=json, hashlib=hashlib, Path=Path,
               time=types.SimpleNamespace(time=lambda: 1000),
               HEALTH_ID='health', HEALTH_KIND='engineering_health', EPISODE_KEY='episode',
               JOURNALS=('attempt-ledger.jsonl','gpu-healthcheck-ledger.jsonl','gpu-hour-reservation-ledger.jsonl'))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), env)
    e = types.SimpleNamespace(**env)
    data = tmp_path / 'data'; data.mkdir()
    def put_doc(name, value):
        path = tmp_path / (name + '.json')
        path.write_text(json.dumps(value, sort_keys=True, allow_nan=False))
        return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    def raw(rows):
        return b''.join(json.dumps(row, sort_keys=True, allow_nan=False).encode()+b'\n' for row in rows)
    baseline = {name:[{'event':'historical', 'journal':name}] for name in env['JOURNALS']}
    baseline[env['JOURNALS'][0]] = [dict(attempt_id='historical-attempt',event=event,
        budget_bucket='baseline',gpu_process_wall_seconds=7 if event=='valid' else 0)
        for event in ('reserved','dispatched','valid')]
    baseline[env['JOURNALS'][1]] = [dict(resource_id='historical-health',kind='historical',event=event,
        gpu_process_wall_seconds=9 if event=='completed' else 0)
        for event in ('reserved','dispatched','completed')]
    original = {}
    for name, rows in baseline.items():
        payload = raw(rows); (data/name).write_bytes(payload)
        original[name] = dict(path=str(data/name), bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
    old = [dict(resource_id='old',kind='readiness_preparation',event=event,
                telemetry_complete=False if event=='aborted' else True,
                gpu_process_wall_seconds=162.0 if event=='aborted' else 0,
                provider_calls=1 if event=='aborted' else 0)
           for event in ('reserved','dispatched','aborted')]
    retained_raw = raw(old)
    retained_path = tmp_path/'retained.jsonl'; retained_path.write_bytes(retained_raw)
    raw_ref = dict(path=str(retained_path), sha256=hashlib.sha256(retained_raw).hexdigest())
    own_path = data/'readiness-preparation-ledger.jsonl'
    own_path.write_bytes(retained_raw)
    (data/env['JOURNALS'][1]).write_bytes(raw(baseline[env['JOURNALS'][1]])+retained_raw)
    observed = {}
    for name in env['JOURNALS']:
        payload=(data/name).read_bytes()
        observed[name]=dict(path=str(data/name),bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest(),prior_prefix_preserved=True)
    offset=original[env['JOURNALS'][1]]['bytes']
    segments=[]; cursor=0
    for line,row in zip(retained_raw.splitlines(keepends=True),old):
        segments.append(dict(bytes=len(line),event=row['event'],global_start_inclusive=offset+cursor,
            global_end_exclusive=offset+cursor+len(line),own_start_inclusive=cursor,
            own_end_exclusive=cursor+len(line),sha256=hashlib.sha256(line).hexdigest()))
        cursor+=len(line)
    segment=lambda path,start:dict(path=str(path),start_inclusive=start,end_exclusive=start+len(retained_raw),sha256=raw_ref['sha256'])
    amendment=put_doc('amendment',{'SYNTHETIC':True,'ledger_prefixes':original})
    snapshot=put_doc('snapshot',{'SYNTHETIC':True})
    identity=put_doc('identity',dict(resource_id='new',recovery_of='old',retained_charge_gpu_hours=162.0/3600,
                                   source={'commit':'historical-not-current'}))
    review=put_doc('review',{'SYNTHETIC':True})
    reconciliation=dict(schema='n36-recovery-binding-review-terminal-reconciliation-v1',
        review=review,live_handles=[],root_accepts_blocking_findings=True,ledger_prefixes=observed)
    contract=dict(schema='n36-failed-readiness-recovery-prefix-contract-v1',accepted_review=review,
        amendment=amendment,drafting_authority=review,full_ledgers_required_for_budget_snapshots=True,
        gpu_authorized=False,identity=identity,original_ledger_prefixes=original,
        own_journal_at_draft=dict(path=str(own_path),bytes=len(retained_raw),sha256=raw_ref['sha256']),
        predecessor=dict(consumed=True,events=['reserved','dispatched','aborted'],
            global_health_segment=segment(data/env['JOURNALS'][1],offset),kind='readiness_preparation',
            own_journal=segment(own_path,0),provider_calls_retained=1,raw_bytes=len(retained_raw),raw_sequence=raw_ref,
            resource_id='old',retained_charge_gpu_hours=162.0/3600,retained_charge_gpu_seconds=162.0,
            row_segments=segments,rows=old,telemetry_complete=False),
        production_authority=False,provider_measurement_authorized=False,read_semantics=[],release_enabled=False,
        retained_snapshot_reference=snapshot,root_observed_ledger_prefixes=observed,
        root_terminal_reconciliation=put_doc('reconciliation',reconciliation),scientific_success=False,status='SYNTHETIC',
        successor=dict(automatic_retry=False,kind='readiness_preparation',
            occurrences_in_complete_ledgers={n:0 for n in (*env['JOURNALS'],'readiness-preparation-ledger.jsonl')},
            resource_id='new',unconsumed_at_draft=True))
    source_doc={'commit':'current'}; source_ref=put_doc('source',source_doc)
    release=dict(source_record=source_ref,baseline=amendment,resource_id='new',source_cwd=str(tmp_path),
        interpreter={'SYNTHETIC':True},issued_at='1970-01-01T00:00:10+00:00',
        expires_at='1970-01-01T00:08:20+00:00',gpu_seconds=600)
    release_ref=put_doc('release',release)
    common={k:release[k] for k in ('source_record','baseline','resource_id','source_cwd','interpreter')}
    common.update(release=release_ref,parent={'pid':123},kind='readiness_preparation')
    current=[dict(common,event=event,time_unix=20+i,reserved_gpu_seconds=600,
        gpu_process_wall_seconds=2 if i==2 else 0,provider_calls=1 if i==2 else 0,
        exclusive=True,telemetry_complete=True,gpu=None,provider=None,envelope=None,process=None,
        **({'error':None} if i==2 else {})) for i,event in enumerate(('reserved','dispatched','completed'))]
    proof=dict(accounting=put_doc('accounting',current),release=release_ref)
    proof_ref=put_doc('proof',proof)
    runtime={'preparation':{'readiness_proof':proof_ref}}; runtime_ref=put_doc('runtime',runtime)
    plan=dict(source=source_doc,runtime=runtime_ref)
    plan_ref=put_doc('plan',plan)
    health=[dict(resource_id='health',kind='engineering_health',event=event,time_unix=30+i,
        timeout_seconds=20,cleanup_seconds=40,reserved_gpu_seconds=60,physical_gpu=7,gpu_uuid='synthetic',
        source_commit='current',runtime=runtime_ref,plan=plan_ref,release=release_ref,
        accounting_admission={'reserved_gpu_seconds':60},gpu_process_wall_seconds=1 if i==2 else 0)
        for i,event in enumerate(('reserved','dispatched','completed'))]
    policy=dict(resource_id='new',proof_path=proof_ref['path'])
    spec=dict(prospective_amendment=amendment,readiness_recovery=identity,retained_ledger_prefixes=original,
        retained_snapshot_reference=snapshot,runtime_binding={'source_record_path':source_ref['path'],
            'preparation':put_doc('policy',policy)},
        recovery_prefix_contract=put_doc('contract',contract))
    calls=[]
    def number(value,label):
        require(type(value) in (int,float) and math.isfinite(value) and value>=0,label)
        return value
    def closed(value,keys,label): require(set(value)==set(keys),label)
    def accepted(*args): calls.append('accepted')
    def derive(*args): calls.append('derive'); return runtime
    preparation=types.SimpleNamespace(policy=lambda spec:policy,
        journal_rows=lambda root:e._recovery_rows(own_path.read_bytes()),
        validate_release=lambda *args,**kwargs:release,owned_identity=lambda value:value,
        timestamp=lambda value:datetime.datetime.fromisoformat(value).timestamp(),
        number=number,closed=closed,pinned=lambda ref,path:read_ref(ref),derive=derive,accepted=accepted)
    env.update(AMENDMENT=amendment,SPECIFICATION=put_doc('spec',spec),preparation=preparation,
        terminal_parent_prefix=lambda:copy.deepcopy(baseline),owner_root=lambda plan:tmp_path,
        operational_binding=lambda plan:{},c=types.SimpleNamespace(GPU_UUID='synthetic',finite=number))
    # Keep the existing whole-own journal validator and pure budget state machine
    # active without importing either production module.
    runner_tree=ast.parse((source.parent/'qd_ed_final_runner.py').read_text())
    budget_env=dict(require=require,math=math,TERMINAL={'valid','aborted'},
        BUCKETS={'baseline':20,'development':100,'validation':60,'formal':40,'recovery':20})
    exec(compile(ast.Module(body=[n for n in runner_tree.body if isinstance(n,ast.FunctionDef)
        and n.name in {'event_groups','budget_snapshot'}],type_ignores=[]),
        str(source.parent/'qd_ed_final_runner.py'),'exec'),budget_env)
    e.r=types.SimpleNamespace(budget_snapshot=budget_env['budget_snapshot'],
        read_events=lambda path:e._recovery_rows(Path(path).read_bytes()))
    prepare_tree=ast.parse((source.parent/'qd_ed_n36_readiness_prepare.py').read_text())
    own_node=next(n for n in prepare_tree.body if isinstance(n,ast.FunctionDef) and n.name=='journal_rows')
    own_env=dict(e=e,Path=Path,MEASUREMENT_CONTRACT={'journal':'readiness-preparation-ledger.jsonl'})
    exec(compile(ast.Module(body=[own_node],type_ignores=[]),
        str(source.parent/'qd_ed_n36_readiness_prepare.py'),'exec'),own_env)
    preparation.journal_rows=own_env['journal_rows']
    resources=[]
    def sync():
        resources[:]=copy.deepcopy(baseline[env['JOURNALS'][1]])+copy.deepcopy(old)+copy.deepcopy(current)+copy.deepcopy(health)
        own_path.write_bytes(retained_raw+raw(current))
        (data/env['JOURNALS'][1]).write_bytes(raw(baseline[env['JOURNALS'][1]])+retained_raw+raw(current)+raw(health))
    def repin():
        spec['recovery_prefix_contract']=put_doc('contract',contract)
        env['SPECIFICATION']=put_doc('spec',spec)
        env['HISTORICAL_SPECIFICATION']=env['SPECIFICATION']
    env['HISTORICAL_SPECIFICATION'] = env['SPECIFICATION']
    sync()
    return types.SimpleNamespace(e=e,env=env,root=tmp_path,data=data,baseline=baseline,resources=resources,
        contract=contract,spec=spec,old=old,current=current,health=health,own=own_path,raw=raw,
        retained_raw=retained_raw,plan=plan,calls=calls,sync=sync,repin=repin,put=put_doc,
        preparation=preparation)


def test_recovery_cpu_positive_and_initial_use(recovery_cpu):
    f=recovery_cpu
    before=copy.deepcopy((f.resources,f.baseline))
    assert f.e.preparation_health_suffix(f.plan,f.baseline,f.resources)==f.health
    assert f.calls==['derive','accepted']
    assert (f.resources,f.baseline)==before
    assert f.resources[len(f.baseline[f.env['JOURNALS'][1]])+2]['telemetry_complete'] is False
    assert f.resources[len(f.baseline[f.env['JOURNALS'][1]])+2]['gpu_process_wall_seconds']==162.0
    # Initial absence and legitimate later presence both pass metadata/raw checks.
    f.current.clear(); f.health.clear(); f.sync()
    assert f.e.specification()==f.spec
    assert f.e.preparation_health_suffix(f.plan,f.baseline,f.resources)==[]


@pytest.mark.parametrize('fault', ['spacing','value','missing','torn','reordered','replayed','unfinished','unknown',
    'foreign','old_reuse','duplicate_successor','partial_mirror','current_spacing','health_before',
    'contract_hash','reconciliation_hash','review_hash','extra_contract_key','null_contract',
    'parsed_resources','baseline','offset','row_hash','symlink','duplicate_key','nonfinite',
    'successor_attempt','successor_reservation'])
def test_recovery_cpu_rejects_prefix_and_binding_faults(recovery_cpu,fault):
    f=recovery_cpu; global_path=f.data/f.env['JOURNALS'][1]
    if fault in ('spacing','value','missing','torn','reordered','replayed','unfinished','unknown'):
        payload=f.retained_raw
        if fault=='spacing': payload=payload.replace(b': ',b':',1)
        elif fault=='value': payload=payload.replace(b'162.0',b'163.0')
        elif fault=='missing': payload=b''
        elif fault=='torn': payload=payload[:-1]
        elif fault=='reordered': payload=b''.join(reversed(payload.splitlines(keepends=True)))
        elif fault=='replayed': payload+=payload
        elif fault=='unfinished': payload=b''.join(payload.splitlines(keepends=True)[:2])
        elif fault=='unknown': payload=payload.replace(b'aborted',b'unknown')
        f.own.write_bytes(payload+f.raw(f.current))
        global_path.write_bytes(f.raw(f.baseline[f.env['JOURNALS'][1]])+payload+f.raw(f.current)+f.raw(f.health))
    elif fault in ('foreign','old_reuse'):
        f.current[0]['resource_id']='foreign' if fault=='foreign' else 'old'; f.sync()
    elif fault=='duplicate_successor': f.current.extend(copy.deepcopy(f.current)); f.sync()
    elif fault=='partial_mirror': f.own.write_bytes(f.retained_raw+f.raw(f.current[:-1]))
    elif fault=='current_spacing': f.own.write_bytes(f.retained_raw+f.raw(f.current).replace(b': ',b':',1))
    elif fault=='health_before': f.health[0]['time_unix']=21; f.sync()
    elif fault=='contract_hash': Path(f.spec['recovery_prefix_contract']['path']).write_text('{}')
    elif fault=='reconciliation_hash': Path(f.contract['root_terminal_reconciliation']['path']).write_text('{}')
    elif fault=='review_hash': Path(f.contract['accepted_review']['path']).write_text('{}')
    elif fault=='extra_contract_key': f.contract['unknown']=True; f.repin()
    elif fault=='null_contract': f.spec['recovery_prefix_contract']=None; f.env['SPECIFICATION']=f.put('spec',f.spec)
    elif fault=='parsed_resources': f.resources.pop()
    elif fault=='baseline': f.baseline[f.env['JOURNALS'][1]][0]['event']='changed'
    elif fault=='offset': f.contract['predecessor']['global_health_segment']['start_inclusive']+=1; f.repin()
    elif fault=='row_hash': f.contract['predecessor']['row_segments'][0]['sha256']='0'*64; f.repin()
    elif fault=='symlink':
        target=f.root/'own-copy'; target.write_bytes(f.own.read_bytes()); f.own.unlink(); f.own.symlink_to(target)
    elif fault in ('duplicate_key','nonfinite'):
        extra=b'{"x":1,"x":2}\n' if fault=='duplicate_key' else b'{"x":1e999}\n'
        global_path.write_bytes(global_path.read_bytes()+extra)
    elif fault in ('successor_attempt','successor_reservation'):
        name=f.env['JOURNALS'][0 if fault=='successor_attempt' else 2]
        path=f.data/name; path.write_bytes(path.read_bytes()+f.raw([{'resource_id':'new'}]))
    with pytest.raises((ValueError,KeyError,TypeError)):
        f.e.preparation_health_suffix(f.plan,f.baseline,f.resources)


@pytest.mark.parametrize('fault', ['pending','unknown','aborted','overrun','reorder','release','source','baseline',
    'parent','extra_key','reservation','timestamp','expired','preterminal_charge','provider_calls',
    'admission_telemetry','accounting','acceptance','health_replay'])
def test_recovery_cpu_preserves_current_lifecycle_rejections(recovery_cpu,fault):
    f=recovery_cpu
    if fault=='pending': f.current.pop()
    elif fault=='unknown': f.current[-1]['event']='unknown'
    elif fault in ('aborted','overrun'):
        f.current[-1].update(event='aborted',gpu_process_wall_seconds=900 if fault=='overrun' else 2,
            telemetry_complete=False,exclusive=False)
    elif fault=='reorder': f.current[0],f.current[1]=f.current[1],f.current[0]
    elif fault in ('release','source','baseline'):
        key='source_record' if fault=='source' else fault
        f.current[-1][key]={'path':'/SYNTHETIC','sha256':'0'*64}
    elif fault=='parent': f.current[-1]['parent']={'pid':456}
    elif fault=='extra_key': f.current[-1]['unknown']=True
    elif fault=='reservation': f.current[-1]['reserved_gpu_seconds']=601
    elif fault=='timestamp': f.current[-1]['time_unix']=19
    elif fault=='expired': f.current[-1]['time_unix']=600
    elif fault=='preterminal_charge': f.current[0]['gpu_process_wall_seconds']=1
    elif fault=='provider_calls': f.current[-1]['provider_calls']=True
    elif fault=='admission_telemetry': f.current[0]['telemetry_complete']=False
    elif fault=='accounting': f.current[-1]['gpu_process_wall_seconds']=3
    elif fault=='acceptance':
        def reject(*args): raise ValueError('synthetic detached acceptance rejected')
        f.preparation.accepted=reject
    elif fault=='health_replay': f.health.extend(copy.deepcopy(f.health))
    f.sync()
    reason = {
        'pending':'unsettled/unknown/replayed', 'unknown':'unknown GPU healthcheck event',
        'aborted':'failed preparation requires', 'overrun':'failed preparation requires',
        'reorder':'illegal attempt transition', 'release':'immutable preparation release',
        'source':'immutable preparation release', 'baseline':'immutable preparation release',
        'parent':'immutable preparation parent', 'extra_key':'strict preparation event',
        'reservation':'preparation finite reservation', 'timestamp':'ordered preparation timestamps',
        'expired':'preparation release event expiry', 'preterminal_charge':'preparation preterminal evidence',
        'provider_calls':'preparation one provider call', 'admission_telemetry':'preparation admission telemetry',
        'accounting':'accepted proof exact preparation accounting',
        'acceptance':'synthetic detached acceptance rejected', 'health_replay':'engineering one-use health lifecycle'}[fault]
    with pytest.raises(ValueError, match=reason):
        f.e.preparation_health_suffix(f.plan,f.baseline,f.resources)


def test_recovery_cpu_absence_keeps_old_behavior(recovery_cpu):
    f=recovery_cpu
    del f.spec['recovery_prefix_contract']; f.env['SPECIFICATION']=f.put('spec',f.spec)
    f.env['HISTORICAL_SPECIFICATION']=f.env['SPECIFICATION']
    with pytest.raises(ValueError,match='foreign resource'):
        f.e.preparation_health_suffix(f.plan,f.baseline,f.resources)
    f.resources[:]=f.baseline[f.env['JOURNALS'][1]]+f.current+f.health
    f.own.write_bytes(f.raw(f.current))
    assert f.e.preparation_health_suffix(f.plan,f.baseline,f.resources)==f.health


def test_recovery_cpu_complete_budget_and_initial_replay(recovery_cpu):
    """Execute real pure budget/admission bodies, with synthetic authority gates."""
    import ast
    import math
    import types
    f=recovery_cpu
    source=Path(globals().get('RECOVERY_CPU_SOURCE',
        Path(__file__).resolve().parents[1]/'scripts/qd_ed_n36_engineering_r1.py'))
    runner=ast.parse((source.parent/'qd_ed_final_runner.py').read_text())
    names={'budget_snapshot','event_groups'}
    budget_env=dict(require=f.env['w'].require,math=math,TERMINAL={'valid','aborted'},
                    BUCKETS={'baseline':20,'development':100,'validation':60,'formal':40,'recovery':20})
    exec(compile(ast.Module(body=[n for n in runner.body if isinstance(n,ast.FunctionDef)
        and n.name in names],type_ignores=[]),str(source.parent/'qd_ed_final_runner.py'),'exec'),budget_env)
    snapshot=budget_env['budget_snapshot']
    retained_seconds=sum(x['gpu_process_wall_seconds'] for x in f.old)
    full=snapshot(f.baseline[f.env['JOURNALS'][0]],f.resources)
    assert full['gpu_hours_consumed']==pytest.approx((7+9+retained_seconds+2+1)/3600)
    assert full['gpu_hours_by_bucket']['recovery']==pytest.approx((9+retained_seconds+2+1)/3600)
    assert snapshot([],f.health)['gpu_hours_consumed']==pytest.approx(1/3600)
    before=copy.deepcopy(f.resources)
    f.e.preparation_health_suffix(f.plan,f.baseline,f.resources)
    assert f.resources==before
    assert snapshot(f.baseline[f.env['JOURNALS'][0]],f.resources)==full
    preparation_path=source.parent/'qd_ed_n36_readiness_prepare.py'
    tree=ast.parse(preparation_path.read_text())
    body=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='preparation_budget')
    body.body=[n for n in body.body if not isinstance(n,ast.ImportFrom)]
    authority=dict(ledger_prefixes=f.spec['retained_ledger_prefixes'],
        retained_snapshot=snapshot(*(f.baseline[n] for n in f.env['JOURNALS'][:2])),
        caps={'buckets':{},'protected_gpu_hours':{}},amendment={},margin_reference={})
    release=dict(accounting_authority={},expires_at='SYNTHETIC',gpu_seconds=600,resource_id='new')
    def state_snapshot(root,auth):
        rows=[f.e._recovery_rows((f.data/name).read_bytes()) for name in f.env['JOURNALS']]
        return {'budget':dict(snapshot(*rows[:2]),max_gpu_hours=100)},*rows
    f.e.JOURNALS=f.env['JOURNALS']
    f.e.stop=types.SimpleNamespace(check=lambda **kwargs:None)
    f.e.accounting=types.SimpleNamespace(ABSOLUTE_HOURS=100,WEEKLY_HOURS=100,retained_margin=lambda *args:0)
    f.e.r=types.SimpleNamespace(**{name:budget_env[name] for name in names},TERMINAL={'valid','aborted'},
                              check_budget_limits=lambda *args,**kwargs:1000,
                              read_events=lambda path:f.e._recovery_rows(Path(path).read_bytes()))
    initial_env=dict(e=f.e,Path=Path,json=json,owner=types.SimpleNamespace(snapshot=state_snapshot),
        validate_preparation_authority=lambda *args:authority,validate_preparation_state=lambda *args:None,
        journal_rows=f.preparation.journal_rows,number=f.preparation.number,MEASUREMENT_CONTRACT={'cleanup_seconds':40})
    exec(compile(ast.Module(body=[body],type_ignores=[]),str(preparation_path),'exec'),initial_env)
    # A valid later lifecycle is legal for readiness, but consumed for new admission.
    with pytest.raises(ValueError,match='global preparation identity replay'):
        initial_env['preparation_budget'](f.root,f.plan,authority,release)
    f.current.clear(); f.health.clear(); f.sync()
    initial=initial_env['preparation_budget'](f.root,f.plan,authority,release)
    assert initial['gpu_hours_consumed']==pytest.approx((7+9+retained_seconds)/3600)
    # Each complete journal rejects preexisting successor use before reservation.
    for name in (*f.env['JOURNALS'],'readiness-preparation-ledger.jsonl'):
        path=f.data/name; saved=path.read_bytes()
        path.write_bytes(saved+f.raw([{'resource_id':'new','kind':'readiness_preparation','event':'reserved'}]))
        with pytest.raises(ValueError): initial_env['preparation_budget'](f.root,f.plan,authority,release)
        path.write_bytes(saved)


@pytest.fixture
def recovery_multi_cpu(recovery_cpu):
    """Two charged aborted lifecycles, immutable bytes, no real evidence reads."""
    f = recovery_cpu
    first = copy.deepcopy(f.contract.pop('predecessor'))
    second = copy.deepcopy(first)
    second['resource_id'] = 'old-two'
    for row in second['rows']:
        row['resource_id'] = 'old-two'
    second['rows'][-1].update(gpu_process_wall_seconds=81.0, provider_calls=None)
    second.update(retained_charge_gpu_seconds=81.0, retained_charge_gpu_hours=81.0/3600,
                  provider_calls_retained=None)
    payload = f.raw(second['rows'])
    path = f.root / 'second-retained.jsonl'; path.write_bytes(payload)
    second['raw_sequence'] = dict(path=str(path), sha256=hashlib.sha256(payload).hexdigest())
    second['raw_bytes'] = len(payload)
    start = len(f.retained_raw)
    offset = f.contract['original_ledger_prefixes'][f.env['JOURNALS'][1]]['bytes']
    for key, begin in [('own_journal', start), ('global_health_segment', offset+start)]:
        second[key].update(start_inclusive=begin, end_exclusive=begin+len(payload),
                           sha256=second['raw_sequence']['sha256'])
    second['row_segments'] = []
    cursor = start
    for row, line in zip(second['rows'], payload.splitlines(keepends=True)):
        second['row_segments'].append(dict(bytes=len(line), event=row['event'],
            global_start_inclusive=offset+cursor, global_end_exclusive=offset+cursor+len(line),
            own_start_inclusive=cursor, own_end_exclusive=cursor+len(line),
            sha256=hashlib.sha256(line).hexdigest()))
        cursor += len(line)
    f.contract.update(schema='n36-failed-readiness-recovery-prefix-contract-v2',
                      predecessors=[first, second])
    identity = f.e.read(f.contract['identity'])
    identity.update(recovery_of=['old', 'old-two'], retained_charge_gpu_hours=162.0/3600+81.0/3600)
    f.contract['identity'] = f.spec['readiness_recovery'] = f.put('multi-identity', identity)
    f.retained_raw += payload
    f.old.extend(second['rows'])
    f.contract['own_journal_at_draft'].update(bytes=len(f.retained_raw),
        sha256=hashlib.sha256(f.retained_raw).hexdigest())
    observed = f.contract['root_observed_ledger_prefixes']
    prefix = f.raw(f.baseline[f.env['JOURNALS'][1]])+f.retained_raw
    observed[f.env['JOURNALS'][1]].update(bytes=len(prefix), sha256=hashlib.sha256(prefix).hexdigest())
    reconciliation = f.e.read(f.contract['root_terminal_reconciliation'])
    reconciliation['ledger_prefixes'] = observed
    f.contract['root_terminal_reconciliation'] = f.put('multi-reconciliation', reconciliation)
    def sync():
        f.resources[:] = copy.deepcopy(f.baseline[f.env['JOURNALS'][1]]+f.old+f.current+f.health)
        f.own.write_bytes(f.retained_raw+f.raw(f.current))
        (f.data/f.env['JOURNALS'][1]).write_bytes(prefix+f.raw(f.current)+f.raw(f.health))
    f.sync = sync
    f.sync(); f.repin()
    return f


def test_recovery_multi_cpu_preserves_both_costs_and_unknowns(recovery_multi_cpu):
    f = recovery_multi_cpu
    before = {p: p.read_bytes() for p in f.data.iterdir()}
    assert f.e.specification() == f.spec
    assert f.e.preparation_health_suffix(f.plan, f.baseline, f.resources) == f.health
    snap = f.e.r.budget_snapshot(f.baseline[f.env['JOURNALS'][0]], f.resources)
    assert snap['gpu_hours_consumed'] == pytest.approx((7+9+162+81+2+1)/3600)
    assert f.old[-1]['provider_calls'] is None
    assert f.old[-1]['telemetry_complete'] is False
    assert {p: p.read_bytes() for p in f.data.iterdir()} == before
    # The unchanged initial-use gate still rejects replay and retains both costs.
    test_recovery_cpu_complete_budget_and_initial_replay(f)


@pytest.mark.parametrize('fault', ['missing_first', 'missing_second', 'reverse', 'duplicate',
    'second_bytes', 'second_own_offset', 'second_global_offset', 'second_row_offset', 'second_row_hash',
    'second_charge', 'aggregate_charge', 'telemetry', 'provider_unknown', 'consumed_successor',
    'foreign', 'first_replay', 'second_replay', 'truncated_own', 'original_offset', 'observed_offset',
    'identity_order', 'raw_hash'])
def test_recovery_multi_cpu_rejects_faults(recovery_multi_cpu, fault):
    f = recovery_multi_cpu
    predecessors = f.contract['predecessors']
    second = predecessors[1]
    if fault == 'missing_first': predecessors.pop(0)
    elif fault == 'missing_second': predecessors.pop()
    elif fault == 'reverse': predecessors.reverse()
    elif fault == 'duplicate': predecessors.append(copy.deepcopy(second))
    elif fault == 'second_bytes':
        f.own.write_bytes(f.own.read_bytes().replace(b'81.0', b'82.0'))
    elif fault == 'second_own_offset': second['own_journal']['start_inclusive'] = 0
    elif fault == 'second_global_offset': second['global_health_segment']['start_inclusive'] += 1
    elif fault == 'second_row_offset': second['row_segments'][0]['own_start_inclusive'] = 0
    elif fault == 'second_row_hash': second['row_segments'][0]['sha256'] = '0'*64
    elif fault == 'second_charge': second['retained_charge_gpu_seconds'] = 0
    elif fault in ('aggregate_charge', 'identity_order'):
        identity = f.e.read(f.contract['identity'])
        if fault == 'aggregate_charge': identity['retained_charge_gpu_hours'] = 81.0/3600
        else: identity['recovery_of'].reverse()
        f.spec['readiness_recovery'] = f.contract['identity'] = f.put('multi-identity', identity)
    elif fault == 'telemetry': second['telemetry_complete'] = True
    elif fault == 'provider_unknown': second['provider_calls_retained'] = 0
    elif fault == 'consumed_successor': f.contract['successor']['resource_id'] = 'old-two'
    elif fault in ('foreign', 'first_replay', 'second_replay'):
        f.current[0]['resource_id'] = {'foreign':'foreign', 'first_replay':'old', 'second_replay':'old-two'}[fault]
        f.sync()
    elif fault == 'truncated_own': f.own.write_bytes(f.own.read_bytes()[:len(f.retained_raw)-1])
    elif fault == 'original_offset': f.contract['original_ledger_prefixes'][f.env['JOURNALS'][1]]['bytes'] += 1
    elif fault == 'observed_offset': f.contract['root_observed_ledger_prefixes'][f.env['JOURNALS'][1]]['bytes'] -= 1
    elif fault == 'raw_hash': second['raw_sequence']['sha256'] = '0'*64
    f.repin()
    with pytest.raises((ValueError, KeyError, TypeError)):
        f.e.preparation_health_suffix(f.plan, f.baseline, f.resources)


@pytest.mark.parametrize('fault', [None, 'science', 'limits', 'amendment', 'old_identity',
    'lineage', 'spec_hash', 'policy_hash', 'old_path', 'extra_key', 'v1'])
def test_recovery_prospective_cpu_specification(recovery_multi_cpu, fault):
    f = recovery_multi_cpu
    # Synthetic immutable historical specification; only operational references may move.
    historical = copy.deepcopy(f.spec)
    historical['scope'] = {'threshold': 0.7}
    historical['runtime_binding'].update(runtime_path='/synthetic/old-runtime', source_record_path='/synthetic/old-source')
    historical['runtime_binding']['preparation'] = f.put('historical-policy',
        {'resource_id':'old-two', 'proof_path':'/synthetic/old-proof', 'previous_specification':{}, 'deadline':'unchanged'})
    historical['readiness_recovery'] = f.put('historical-identity', {'resource_id':'old-two'})
    historical['recovery_prefix_contract'] = f.put('historical-contract', {'historical':True})
    historical_ref = f.put('historical-spec', historical)
    f.spec['scope'] = historical['scope'].copy()
    f.spec['runtime_binding']['runtime_path'] = '/synthetic/new-runtime'
    policy = f.e.read(f.spec['runtime_binding']['preparation'])
    policy['previous_specification'] = historical_ref
    policy['deadline'] = 'unchanged'
    if fault == 'science': f.spec['scope']['threshold'] = 0.8
    elif fault == 'limits': f.spec['runtime_binding']['measurement_contract'] = {'cleanup_seconds':0}
    elif fault == 'amendment': f.spec['prospective_amendment'] = f.put('foreign-amendment', {})
    elif fault == 'old_identity': policy['resource_id'] = 'old-two'
    elif fault == 'lineage': policy['previous_specification'] = f.put('foreign-spec', {})
    elif fault == 'extra_key': f.spec['approval'] = True
    elif fault == 'v1':
        f.contract['schema'] = 'n36-failed-readiness-recovery-prefix-contract-v1'
        f.contract['predecessor'] = f.contract.pop('predecessors')[0]
    f.spec['runtime_binding']['preparation'] = f.put('fresh-policy', policy)
    f.repin()
    f.env['HISTORICAL_SPECIFICATION'] = historical_ref
    if fault == 'spec_hash': f.env['SPECIFICATION']['sha256'] = '0'*64
    elif fault == 'policy_hash': Path(f.spec['runtime_binding']['preparation']['path']).write_text('{}')
    elif fault == 'old_path': f.env['SPECIFICATION']['path'] = historical_ref['path']
    if fault is None:
        before = Path(historical_ref['path']).read_bytes()
        assert f.e.specification() == f.spec
        assert Path(historical_ref['path']).read_bytes() == before
    else:
        with pytest.raises((ValueError, KeyError, TypeError)):
            f.e.specification()


def test_recovery_prospective_cpu_process_selection(recovery_cpu):
    import ast
    import types
    f = recovery_cpu
    source = Path(globals().get('RECOVERY_CPU_SOURCE',
        Path(__file__).resolve().parents[1]/'scripts/qd_ed_n36_engineering_r1.py'))
    tree = ast.parse(source.read_text())
    assignment = next(n for n in tree.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'SPECIFICATION' for t in n.targets))
    historical = f.env['SPECIFICATION']
    selected = {'path':'/synthetic/fresh.json', 'sha256':'1'*64}
    for environ, expected in [({}, historical),
            ({'QD_ED_N36_R1_SPECIFICATION':json.dumps(selected)}, selected)]:
        env = dict(os=types.SimpleNamespace(environ=environ), json=json,
                   HISTORICAL_SPECIFICATION=historical)
        exec(compile(ast.Module(body=[assignment], type_ignores=[]), str(source), 'exec'), env)
        assert env['SPECIFICATION'] == expected
    child = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'child_environment')
    env = dict(owner_root=lambda plan:None, r=types.SimpleNamespace(child_environment=lambda rt:
        {'QD_ED_N36_R1_SPECIFICATION':'foreign environment mutation'}),
        SOURCE=f.root, SPECIFICATION=selected, reference=f.e.reference, json=json)
    exec(compile(ast.Module(body=[child], type_ignores=[]), str(source), 'exec'), env)
    assert json.loads(env['child_environment']({}, {})['QD_ED_N36_R1_SPECIFICATION']) == selected


PROPOSED_SCOPE_SPECIFICATION = {
    'path': '/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001808/disabled-binding-refresh/specification.prospective-disabled-v1.json',
    'sha256': 'd983afb6285c19f7b720b0313316cfb6fc686c5c53dcfe94bac852c09f6d2e6a'}


def test_exact_proposed_scope_policy_retains_unassigned_recovery_block(monkeypatch):
    from scripts import qd_ed_n36_readiness_prepare as preparation
    spec = e.read(PROPOSED_SCOPE_SPECIFICATION)
    # Actual proposed bytes and owning approvals, no policy/allowlist mocks.
    assert preparation.policy(spec)['resource_id'] is None
    monkeypatch.setattr(e, 'SPECIFICATION', PROPOSED_SCOPE_SPECIFICATION)
    monkeypatch.setattr(e, 'HISTORICAL_SPECIFICATION', PINNED_SPECIFICATION)
    with pytest.raises(ValueError, match='prospective specification lineage'):
        e._recovery_specification(spec)


@pytest.fixture
def prospective_scope_cpu(recovery_multi_cpu):
    """Real 001808 composition + isolated synthetic recovery, never live proof.

    The exact proposed specification/authority path is exercised by both real
    admission functions. Only recovery/accounting fixture bytes are substituted,
    identically in both projections, to avoid reading any owning journal.
    """
    f = recovery_multi_cpu
    synthetic = copy.deepcopy(f.spec)
    f.spec.clear()
    f.spec.update(e.read(PROPOSED_SCOPE_SPECIFICATION))
    historical = e.read(PINNED_SPECIFICATION)
    for key in ('prospective_amendment', 'retained_ledger_prefixes', 'retained_snapshot_reference'):
        historical[key] = f.spec[key] = synthetic[key]
    for key in ('readiness_recovery', 'recovery_prefix_contract'):
        f.spec[key] = synthetic[key]
    f.historical = f.put('SYNTHETIC-scope-historical-spec', historical)
    prep = e.read(f.spec['runtime_binding']['preparation'])
    prep.update(resource_id='new', previous_specification=f.historical)
    f.spec['runtime_binding']['preparation'] = f.put('SYNTHETIC-scope-preparation', prep)
    f.repin()
    f.env['HISTORICAL_SPECIFICATION'] = f.historical
    # Admission starts before any successor measurement or engineering health.
    f.current.clear()
    f.health.clear()
    f.sync()
    return f


@pytest.mark.parametrize('fault', [None, 'extra_path', 'omitted_path', 'duplicate_path',
    'expanded_amendment', 'extra_amendment_key', 'scope_authority', 'repair_authority',
    'wrapper_hash', 'scope_hash', 'old_amendment', 'source_path', 'source_hash',
    'science', 'accounting', 'measurement_limits', 'release', 'old_resource',
    'historical_proof', 'policy_deadline'])
def test_prospective_scope_actual_composition_admission(prospective_scope_cpu, monkeypatch, fault):
    f = prospective_scope_cpu
    binding = f.spec['runtime_binding']
    amendment = f.e.read(binding['amendment'])
    if fault == 'extra_path': binding['source_change_allowlist'].append('scripts/unapproved.py')
    elif fault == 'omitted_path': binding['source_change_allowlist'].remove('scripts/qd_ed_n36_source.py')
    elif fault == 'duplicate_path': binding['source_change_allowlist'].append(binding['source_change_allowlist'][0])
    elif fault == 'expanded_amendment':
        for key in ('new_allowed_entrypoints', 'exact_source_change_allowlist'):
            amendment[key].append('scripts/unapproved.py')
        binding['source_change_allowlist'].append('scripts/unapproved.py')
    elif fault == 'extra_amendment_key': amendment['approved'] = True
    elif fault == 'scope_authority':
        scope = f.e.read(amendment['approved_prospective_scope'])
        scope['additional_allowed_source_paths'].append('scripts/unapproved.py')
        amendment['approved_prospective_scope'] = f.put('SYNTHETIC-forged-scope', scope)
    elif fault == 'repair_authority':
        authority = f.e.read(binding['repair_authority'])
        authority['source_base'] = '0' * 40
        binding['repair_authority'] = f.put('SYNTHETIC-forged-authority', authority)
    elif fault == 'scope_hash': amendment['approved_prospective_scope']['sha256'] = '0' * 64
    elif fault == 'source_path': amendment['source']['path'] = '/synthetic/foreign-source.json'
    elif fault == 'source_hash': amendment['source']['sha256'] = '0' * 64
    elif fault == 'science': f.spec['scope']['episode']['policy_seed'] += 1
    elif fault == 'accounting': f.spec['retained_snapshot']['gpu_hours_consumed'] = 0
    elif fault == 'measurement_limits': binding['measurement_contract']['provider_calls'] = 2
    elif fault == 'release': f.spec['release_enabled'] = True
    if fault in ('old_resource', 'historical_proof', 'policy_deadline'):
        prep = f.e.read(binding['preparation'])
        historical = f.e.read(f.historical)
        old_prep = f.e.read(historical['runtime_binding']['preparation'])
        if fault == 'old_resource': prep['resource_id'] = old_prep['resource_id']
        elif fault == 'historical_proof': prep['proof_path'] = old_prep['proof_path']
        else: prep['deadline'] = '2099-01-01T00:00:00Z'
        binding['preparation'] = f.put('SYNTHETIC-mutated-preparation', prep)
    binding['amendment'] = f.put('SYNTHETIC-scope-composition', amendment)
    if fault == 'wrapper_hash': binding['amendment']['sha256'] = '0' * 64
    elif fault == 'old_amendment': binding['amendment'] = amendment['previous_runtime_amendment']
    f.repin()
    f.env['HISTORICAL_SPECIFICATION'] = f.historical
    monkeypatch.setattr(e, 'SPECIFICATION', f.env['SPECIFICATION'])
    monkeypatch.setattr(e, 'HISTORICAL_SPECIFICATION', f.historical)
    monkeypatch.setattr(e, 'AMENDMENT', f.env['AMENDMENT'])
    before = {path: path.read_bytes() for path in f.data.iterdir()}
    if fault is None:
        assert e.specification() == f.spec
        assert not f.spec['scope']['scientific_eligible']
        assert not f.spec['release_enabled']
        assert f.old[-1]['provider_calls'] is None
    else:
        with pytest.raises((ValueError, FileNotFoundError)):
            e.specification()
    assert {path: path.read_bytes() for path in f.data.iterdir()} == before


def repin_terminal_partition(f):
    """Build authenticated SYNTHETIC bytes, including deliberately invalid rows."""
    offset = f.contract['original_ledger_prefixes'][f.env['JOURNALS'][1]]['bytes']
    retained = b''
    f.old.clear()
    for i, predecessor in enumerate(f.contract['predecessors']):
        payload = f.raw(predecessor['rows'])
        path = f.root / f'terminal-retained-{i}.jsonl'
        path.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        predecessor.update(raw_bytes=len(payload), raw_sequence=dict(path=str(path), sha256=digest))
        start = len(retained)
        for key, begin in [('own_journal', start), ('global_health_segment', offset + start)]:
            predecessor[key].update(start_inclusive=begin, end_exclusive=begin + len(payload), sha256=digest)
        predecessor['row_segments'] = []
        cursor = start
        for row, line in zip(predecessor['rows'], payload.splitlines(keepends=True)):
            predecessor['row_segments'].append(dict(bytes=len(line), event=row['event'],
                global_start_inclusive=offset + cursor, global_end_exclusive=offset + cursor + len(line),
                own_start_inclusive=cursor, own_end_exclusive=cursor + len(line),
                sha256=hashlib.sha256(line).hexdigest()))
            cursor += len(line)
        retained += payload
        f.old.extend(predecessor['rows'])
    f.retained_raw = retained
    f.contract['own_journal_at_draft'].update(bytes=len(retained), sha256=hashlib.sha256(retained).hexdigest())
    prefix = f.raw(f.baseline[f.env['JOURNALS'][1]]) + retained
    observed = f.contract['root_observed_ledger_prefixes']
    observed[f.env['JOURNALS'][1]].update(bytes=len(prefix), sha256=hashlib.sha256(prefix).hexdigest())
    reconciliation = f.e.read(f.contract['root_terminal_reconciliation'])
    reconciliation['ledger_prefixes'] = observed
    f.contract['root_terminal_reconciliation'] = f.put('terminal-reconciliation', reconciliation)
    identity = f.e.read(f.contract['identity'])
    identity.update(recovery_of=[p['resource_id'] for p in f.contract['predecessors']],
        retained_charge_gpu_hours=sum(p['retained_charge_gpu_hours'] for p in f.contract['predecessors']))
    f.contract['identity'] = f.spec['readiness_recovery'] = f.put('terminal-identity', identity)
    def sync():
        f.resources[:] = copy.deepcopy(f.baseline[f.env['JOURNALS'][1]] + f.old + f.current + f.health)
        f.own.write_bytes(f.retained_raw + f.raw(f.current))
        (f.data / f.env['JOURNALS'][1]).write_bytes(prefix + f.raw(f.current) + f.raw(f.health))
    f.sync = sync
    f.sync()
    f.repin()


@pytest.fixture
def recovery_terminal_cpu(recovery_multi_cpu):
    """Two aborted/incomplete and one completed/complete, with all costs retained."""
    f = recovery_multi_cpu
    f.contract['schema'] = 'n36-readiness-recovery-prefix-contract-v3'
    for p in f.contract['predecessors']:
        p['terminal_status'] = 'aborted'
    completed = copy.deepcopy(f.contract['predecessors'][-1])
    completed.update(resource_id='old-three', terminal_status='completed',
        events=['reserved', 'dispatched', 'completed'], telemetry_complete=True,
        provider_calls_retained=1, retained_charge_gpu_seconds=234.72371816635132,
        retained_charge_gpu_hours=234.72371816635132 / 3600)
    for row in completed['rows']:
        row['resource_id'] = completed['resource_id']
    completed['rows'][-1].update(event='completed', telemetry_complete=True,
        provider_calls=1, gpu_process_wall_seconds=completed['retained_charge_gpu_seconds'])
    f.contract['predecessors'].append(completed)
    repin_terminal_partition(f)
    return f


def test_recovery_terminal_cpu_partition_and_budget(recovery_terminal_cpu):
    f = recovery_terminal_cpu
    before = {p: p.read_bytes() for p in f.data.iterdir()}
    assert f.e.specification() == f.spec
    assert f.e.preparation_health_suffix(f.plan, f.baseline, f.resources) == f.health
    assert f.calls == ['derive', 'accepted']
    terminals = f.old[2::3]
    assert [r['event'] for r in terminals] == ['aborted', 'aborted', 'completed']
    assert [r['telemetry_complete'] for r in terminals] == [False, False, True]
    assert terminals[1]['provider_calls'] is None
    assert {p: p.read_bytes() for p in f.data.iterdir()} == before
    # Full-budget accounting, fresh admission and successor replay checks use
    # the same production function bodies for all three retained lifecycles.
    test_recovery_cpu_complete_budget_and_initial_replay(f)


@pytest.mark.parametrize('fault', ['missing_status', 'unknown_status', 'false_status',
    'false_events', 'false_telemetry', 'bool_as_int', 'abort_complete', 'raw_status',
    'raw_telemetry', 'raw_bool_as_int', 'unknown_provider', 'bool_provider',
    'uncharged', 'negative_charge', 'false_charge', 'duplicate_identity',
    'missing_raw_row', 'reordered_raw_rows', 'extra_raw_row', 'legacy_v2', 'unknown_schema'])
def test_recovery_terminal_cpu_semantics(recovery_terminal_cpu, fault):
    f = recovery_terminal_cpu
    completed = f.contract['predecessors'][-1]
    terminal = completed['rows'][-1]
    rebuild = False
    if fault == 'missing_status': completed.pop('terminal_status')
    elif fault == 'unknown_status': completed['terminal_status'] = 'valid'
    elif fault == 'false_status': completed['terminal_status'] = 'aborted'
    elif fault == 'false_events': completed['events'][-1] = 'aborted'
    elif fault == 'false_telemetry': completed['telemetry_complete'] = False
    elif fault == 'bool_as_int': completed['telemetry_complete'] = 1
    elif fault == 'abort_complete': f.contract['predecessors'][0]['telemetry_complete'] = True
    elif fault == 'raw_status': terminal['event'] = 'aborted'; rebuild = True
    elif fault == 'raw_telemetry': terminal['telemetry_complete'] = False; rebuild = True
    elif fault == 'raw_bool_as_int': terminal['telemetry_complete'] = 1; rebuild = True
    elif fault in ('unknown_provider', 'bool_provider'):
        terminal['provider_calls'] = completed['provider_calls_retained'] = None if fault == 'unknown_provider' else True
        rebuild = True
    elif fault in ('uncharged', 'negative_charge'):
        charge = 0.0 if fault == 'uncharged' else -1.0
        terminal['gpu_process_wall_seconds'] = completed['retained_charge_gpu_seconds'] = charge
        completed['retained_charge_gpu_hours'] = charge / 3600
        rebuild = True
    elif fault == 'false_charge': completed['retained_charge_gpu_seconds'] = 0.0
    elif fault == 'duplicate_identity': completed['resource_id'] = 'old'
    elif fault == 'missing_raw_row': completed['rows'].pop(1); rebuild = True
    elif fault == 'reordered_raw_rows': completed['rows'].reverse(); rebuild = True
    elif fault == 'extra_raw_row': completed['rows'].append(copy.deepcopy(terminal)); rebuild = True
    elif fault == 'legacy_v2':
        f.contract['schema'] = 'n36-failed-readiness-recovery-prefix-contract-v2'
        for p in f.contract['predecessors']: p.pop('terminal_status')
    elif fault == 'unknown_schema': f.contract['schema'] = 'n36-readiness-recovery-prefix-contract-v4'
    if rebuild: repin_terminal_partition(f)
    else: f.repin()
    with pytest.raises(ValueError):
        f.e.specification()


@pytest.mark.parametrize('fault', ['missing_first', 'missing_second', 'reverse', 'duplicate',
    'second_bytes', 'second_own_offset', 'second_global_offset', 'second_row_offset', 'second_row_hash',
    'second_charge', 'aggregate_charge', 'telemetry', 'provider_unknown', 'consumed_successor',
    'foreign', 'first_replay', 'second_replay', 'truncated_own', 'original_offset', 'observed_offset',
    'identity_order', 'raw_hash'])
def test_recovery_terminal_cpu_partition_faults(recovery_terminal_cpu, fault):
    test_recovery_multi_cpu_rejects_faults(recovery_terminal_cpu, fault)


@pytest.mark.parametrize('fault', ['pending', 'aborted', 'reorder', 'release', 'source',
    'reservation', 'preterminal_charge', 'provider_calls', 'admission_telemetry',
    'accounting', 'acceptance', 'health_replay'])
def test_recovery_terminal_cpu_successor_gates(recovery_terminal_cpu, fault):
    test_recovery_cpu_preserves_current_lifecycle_rejections(recovery_terminal_cpu, fault)


@pytest.mark.parametrize('fault', ['partial_mirror', 'current_spacing', 'health_before',
    'successor_attempt', 'successor_reservation', 'duplicate_successor'])
def test_recovery_terminal_cpu_mirror_gates(recovery_terminal_cpu, fault):
    test_recovery_cpu_rejects_prefix_and_binding_faults(recovery_terminal_cpu, fault)


@pytest.mark.parametrize('fault', [None, 'science', 'limits', 'amendment', 'old_identity',
    'lineage', 'spec_hash', 'policy_hash', 'old_path', 'extra_key'])
def test_recovery_terminal_cpu_prospective_specification(recovery_terminal_cpu, fault):
    test_recovery_prospective_cpu_specification(recovery_terminal_cpu, fault)


@pytest.fixture
def inventory_admission_cpu(prospective_scope_cpu, monkeypatch):
    """Exact real inventory/authority, synthetic recovery and new snapshot only."""
    f = prospective_scope_cpu
    f.historical_doc = e.read(f.historical)
    f.inventory_amendment = e.read(e.INVENTORY_AMENDMENT)
    f.spec['canonical_inventory_amendment'] = dict(e.INVENTORY_AMENDMENT)
    old = e.read(f.historical_doc['canonical_runtime'])
    amended = copy.deepcopy(old)
    change = f.inventory_amendment['change']
    index = next(i for i, row in enumerate(old['files']) if row == change['before'])
    amended['files'][index] = change['after']
    f.spec['canonical_runtime'] = f.put('SYNTHETIC-prospective-canonical', amended)
    previous = copy.deepcopy(f.historical_doc)
    previous['canonical_runtime'] = f.spec['canonical_runtime']
    previous['prospective_inventory_derivation'] = dict(
        historical_original=f.historical, amendment=f.spec['canonical_inventory_amendment'],
        scope='New disabled prospective snapshot; historical original is unchanged and not represented as amended.')
    prep = e.read(f.spec['runtime_binding']['preparation'])
    prep.update(baseline=f.spec['canonical_runtime'],
                previous_specification=f.put('SYNTHETIC-derived-previous-spec', previous))
    f.spec['runtime_binding']['preparation'] = f.put('SYNTHETIC-inventory-policy', prep)
    f.repin()
    monkeypatch.setattr(e, 'SPECIFICATION', f.env['SPECIFICATION'])
    monkeypatch.setattr(e, 'HISTORICAL_SPECIFICATION', f.historical)
    monkeypatch.setattr(e, 'AMENDMENT', f.env['AMENDMENT'])
    f.inventory_index = index
    return f


@pytest.mark.parametrize('fault', [None, 'amendment_hash', 'amendment_bytes', 'amendment_path',
    'authority_bytes', 'owning_authority_bytes', 'missing_amendment', 'old_runtime_hash',
    'new_runtime_hash', 'old_row', 'wrong_new_hash', 'wrong_new_size', 'extra_row',
    'omitted_row', 'reordered_rows', 'second_delta', 'extra_runtime_key', 'runtime_protocol',
    'runtime_ready', 'provider_ready', 'release_ready', 'local_source_bytes', 'recorded_source_bytes',
    'science', 'accounting', 'protocol', 'limits', 'release', 'extra_spec_key',
    'policy_baseline', 'policy_deadline', 'previous_science', 'previous_accounting',
    'previous_lineage', 'previous_amendment', 'previous_extra_key', 'previous_no_derivation',
    'previous_historical', 'previous_hash'])
def test_inventory_admission_exact_delta_and_projection(inventory_admission_cpu, monkeypatch, fault):
    f = inventory_admission_cpu
    runtime = e.read(f.spec['canonical_runtime'])
    prep = e.read(f.spec['runtime_binding']['preparation'])
    previous = e.read(prep['previous_specification'])
    before = {Path(ref['path']): Path(ref['path']).read_bytes() for ref in (
        e.INVENTORY_AMENDMENT, e.INVENTORY_AUTHORITY, f.historical,
        f.historical_doc['canonical_runtime'])}
    journals = {p: p.read_bytes() for p in f.data.iterdir()}
    if fault == 'amendment_hash': f.spec['canonical_inventory_amendment']['sha256'] = '0' * 64
    elif fault == 'amendment_path':
        f.spec['canonical_inventory_amendment'] = f.put('SYNTHETIC-relocated-amendment', f.inventory_amendment)
    elif fault == 'missing_amendment': f.spec.pop('canonical_inventory_amendment')
    elif fault == 'old_runtime_hash': f.historical_doc['canonical_runtime']['sha256'] = '0' * 64
    elif fault == 'new_runtime_hash': f.spec['canonical_runtime']['sha256'] = '0' * 64
    elif fault == 'old_row': runtime['files'][f.inventory_index] = f.inventory_amendment['change']['before']
    elif fault == 'wrong_new_hash': runtime['files'][f.inventory_index]['sha256'] = '0' * 64
    elif fault == 'wrong_new_size': runtime['files'][f.inventory_index]['size_bytes'] += 1
    elif fault == 'extra_row': runtime['files'].append(runtime['files'][0])
    elif fault == 'omitted_row': runtime['files'].pop(0)
    elif fault == 'reordered_rows': runtime['files'].reverse()
    elif fault == 'second_delta': runtime['files'][0]['sha256'] = '0' * 64
    elif fault == 'extra_runtime_key': runtime['approved'] = True
    elif fault == 'runtime_protocol': runtime['stage_condition'] = 'changed'
    elif fault == 'runtime_ready': runtime['preparation']['runtime_ready'] = True
    elif fault == 'provider_ready': runtime['provider_ready'] = True
    elif fault == 'release_ready': runtime['preparation']['release_enabled'] = True
    elif fault == 'science': f.spec['scope']['episode']['policy_seed'] += 1
    elif fault == 'accounting': f.spec['retained_snapshot']['gpu_hours_consumed'] = 0
    elif fault == 'protocol': f.spec['unchanged_files_and_rules'] = []
    elif fault == 'limits': f.spec['runtime_binding']['measurement_contract']['provider_calls'] = 2
    elif fault == 'release': f.spec['release_enabled'] = True
    elif fault == 'extra_spec_key': f.spec['approved'] = True
    elif fault == 'policy_baseline': prep['baseline'] = f.historical_doc['canonical_runtime']
    elif fault == 'policy_deadline': prep['deadline'] = '2099-01-01T00:00:00Z'
    elif fault == 'previous_science': previous['scope']['episode']['policy_seed'] += 1
    elif fault == 'previous_accounting': previous['retained_snapshot']['gpu_hours_consumed'] = 0
    elif fault == 'previous_lineage': previous['prospective_inventory_derivation']['historical_original'] = {}
    elif fault == 'previous_amendment': previous['prospective_inventory_derivation']['amendment']['sha256'] = '0' * 64
    elif fault == 'previous_extra_key': previous['approved'] = True
    elif fault == 'previous_no_derivation': previous.pop('prospective_inventory_derivation')
    elif fault == 'previous_historical': prep['previous_specification'] = f.historical
    elif fault == 'previous_hash': prep['previous_specification']['sha256'] = '0' * 64
    if fault in ('amendment_bytes', 'authority_bytes', 'owning_authority_bytes',
                 'local_source_bytes', 'recorded_source_bytes'):
        targets = dict(amendment_bytes=e.INVENTORY_AMENDMENT['path'],
            authority_bytes=e.INVENTORY_AUTHORITY['path'],
            owning_authority_bytes=f.inventory_amendment['authority']['path'],
            local_source_bytes=str(Path(e.__file__).with_name('qd_ed_n36_source.py')),
            recorded_source_bytes=f.inventory_amendment['change']['after']['path'])
        target = Path(targets[fault]).resolve()
        real_read = Path.read_bytes
        monkeypatch.setattr(Path, 'read_bytes', lambda path:
            real_read(path) + b' ' if path.resolve() == target else real_read(path))
    # Mutated documents receive honest fresh hashes; rejection must be semantic.
    if fault not in ('new_runtime_hash',):
        f.spec['canonical_runtime'] = f.put('SYNTHETIC-mutated-runtime', runtime)
        if fault != 'policy_baseline': prep['baseline'] = f.spec['canonical_runtime']
        previous['canonical_runtime'] = f.spec['canonical_runtime']
    if fault not in ('previous_historical', 'previous_hash'):
        prep['previous_specification'] = f.put('SYNTHETIC-mutated-previous', previous)
    f.spec['runtime_binding']['preparation'] = f.put('SYNTHETIC-mutated-policy', prep)
    if fault == 'old_runtime_hash':
        f.historical = f.put('SYNTHETIC-mutated-history', f.historical_doc)
        monkeypatch.setattr(e, 'HISTORICAL_SPECIFICATION', f.historical)
    f.repin()
    monkeypatch.setattr(e, 'SPECIFICATION', f.env['SPECIFICATION'])
    if fault is None:
        assert e.specification() == f.spec
        assert f.spec['release_enabled'] is False
        assert f.spec['scope']['scientific_eligible'] is False
        assert f.old[-1]['provider_calls'] is None
    else:
        with pytest.raises((ValueError, KeyError, FileNotFoundError)):
            e.specification()
    # Read through the unpatched method to check no historical bytes were written.
    reader = real_read if fault in ('amendment_bytes', 'authority_bytes', 'owning_authority_bytes',
                                   'local_source_bytes', 'recorded_source_bytes') else Path.read_bytes
    assert {p: reader(p) for p in before} == before
    assert {p: reader(p) for p in journals} == journals


def test_inventory_admission_actual_v4_projection(monkeypatch):
    """Read-only static admission, not full graph, ledger, native or release proof."""
    path = Path(e.INVENTORY_AUTHORITY['path']).parent.parent / 'composition-v4/specification.prospective-disabled-v4.json'
    # Pin the observed v4 input; passing this projection is not graph admission.
    ref = dict(path=str(path), sha256='bd00228581595d848e5fea70691454fd35c3a8f7d5210d27d2b874580e5dcbeb')
    monkeypatch.setattr(e, 'SPECIFICATION', ref)
    monkeypatch.setattr(e, 'HISTORICAL_SPECIFICATION', PINNED_SPECIFICATION)
    spec = e._recovery_json(e._recovery_read(ref))
    e._recovery_specification(spec)
    assert spec['gpu_authorized'] is spec['release_enabled'] is False
