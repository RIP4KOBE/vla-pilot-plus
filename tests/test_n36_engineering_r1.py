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
                   '_journal_suffixes', 'reconcile', 'validate_readiness'}
    assert set(old) == set(new) - {'terminal_parent_prefix', 'validate_runtime_binding', 'preparation_health_suffix'}
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
