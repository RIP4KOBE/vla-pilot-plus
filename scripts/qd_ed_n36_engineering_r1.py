"""Prospective R1 fork of the frozen parent engineering adapter.

Parent source remains unchanged; only exact amended terminal history is admitted.
One-use N36 engineering diagnostic, separate from scientific cohort authority.

This module consumes external, hash-bound approvals. It never creates an
approval, adopts source/accounting, or supplies a continuation/retry entrypoint.
Disabled scope/accounting and the full audit view do not authorize execution.
Dispatch requires the complete detached release, source/runtime closure,
owning-state adoption and bounded one-use admission below. CPU verification
does not create those authorities or establish scientific success.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from decimal import Decimal

from scripts import qd_ed_n23_worker as w, qd_ed_final_runner as r
from scripts import qd_ed_n36_contract as c, qd_ed_n36_stop as stop
from scripts import qd_ed_n36_bridge as b, qd_ed_n36_release as full
from scripts import qd_ed_n36_accounting as accounting
from scripts.qd_ed_n36r2_admission import OWNER, SESSION

BASE = 'b8d6b98164f24a599a9aa1fa6ce862b12cb2fcf6'
SOURCE = SESSION / 'variants/n36_engineering_adapter_001482/implementation_worktree'
PREPARATION = OWNER.parent / 'autonomy_20261004/turns/001479/bounded-engineering-preparation'
# Existing lexical mapping bound by the 001352 owner-alias repair authority
# (ae1cf552f52c9083fff2b0bb98c076d86d03b12993725e08ae2812e5d6084a78).
# This is route provenance only, never engineering adoption or dispatch authority.
OWNER_ROUTE_MAPPING = {
    'path': str(OWNER.parent / 'autonomy_20261004/turns/001352/owner-alias-repair/alias-evidence-v1.json'),
    'sha256': '70097b35181e55589df8bb053857b11840f08542fb8ed8bec57635ba493b22a2'}
HISTORICAL_OWNER = '/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z'
HISTORICAL_SPECIFICATION = {'path': '/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001730/recovery-prefix-contract/engineering-r1-spec.canonical-prospective-disabled-v2.json', 'sha256': '6eab17b8f8701ccea6cb5e9eb21f787873ec1d79d6612d775446ceb570e8dce1'}
# Exact engineering admission, not source adoption or measurement authority.
# Neither document binds this module's new commit, avoiding a source hash cycle.
INVENTORY_AMENDMENT = {
    'path': str(OWNER.parent / 'autonomy_20261004/turns/001834/prospective-runtime-inventory-amendment-v1.json'),
    'sha256': '77ac3358be8ba46b068f6f826c0dbcc8b23a7a43b3e816001c750318aa337fc4'}
INVENTORY_AUTHORITY = {
    'path': str(OWNER.parent / 'autonomy_20261004/turns/001835/engineering-repair/authority-v1.json'),
    'sha256': 'e85daf0801b9b9b4ff94cbc6df6d27191bd0318981c65acb2b002cd07405f7e7'}
# Selection is process-stable and inherited by children; it is never authority.
# Every release/scope/accounting reference must bind this exact selected digest.
SPECIFICATION = json.loads(os.environ.get('QD_ED_N36_R1_SPECIFICATION',
                                         json.dumps(HISTORICAL_SPECIFICATION)))

AMENDMENT = {'path': '/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001616/prospective-recovery-amendment-v1.json', 'sha256': 'fe3c11c3a4be56f74149dc7e21a59eef59611478841d0fa8993bc79f8760e5ba'}
IDENTITY = 'N36_ENGINEERING_R1_C0_TASK0_001616'
EPISODE_KEY = 'n36_engineering_r1_t00_c0_001616'
HEALTH_ID = 'n36_healthcheck_engineering_r1_t00_c0_001616'
HEALTH_KIND = "n36_engineering_r1_resource_preparation_v1"
PURPOSE = 'engineering_diagnostic_only'
PLAN_SCHEMA = 'n36-engineering-execution-plan-v1'
AUDIT_SCHEMA = 'n36-engineering-audit-view-v1'
CONTEXT_SCHEMA = 'n36-engineering-worker-context-v1'
LIMITS = {'attempts': 1, 'healthchecks': 1, 'episode_seconds': 1800,
          'cleanup_seconds': 40, 'health_seconds': 20, 'health_cleanup_seconds': 40,
          'gpu_seconds': 1900, 'health_aggregate_seconds': 60, 'root_overhead_seconds': 200,
          'wall_seconds': 2100, 'automatic_recoveries': 0}
JOURNALS = ('attempt-ledger.jsonl', 'gpu-healthcheck-ledger.jsonl', 'gpu-hour-reservation-ledger.jsonl')
BINDINGS = ('scope', 'accounting', 'audit_plan', 'engineering_manifest', 'source',
            'scientific_source', 'scientific_equivalence', 'runtime', 'runtime_closure',
            'native_build', 'controller_semantics', 'deployment')
RUNTIME_INPUTS = ('run_name', 'runtime_inventory_path', 'runtime_inventory_sha256',
                  'seed_plan_path', 'seed_plan_sha256', 'input_contract_label')
# Changes outside these operational files require a different specification.
OPERATIONAL_FILES = frozenset({
    'scripts/qd_ed_n36_readiness_prepare.py', 'tests/test_n36_readiness_prepare.py',
    'scripts/qd_ed_n36_engineering_r1.py', 'scripts/qd_ed_n36_engineering_api.py',
    'configs/qd_ed_final/n36_engineering_r1_spec.disabled.json', 'tests/test_n36_engineering_r1.py', 'scripts/qd_ed_n36_release.py',
    'scripts/qd_ed_n36_bridge.py', 'scripts/qd_ed_n36_worker.py',
    'scripts/qd_ed_n36_runner.py', 'scripts/qd_ed_n36_healthcheck.py',
    'scripts/qd_ed_n36_report.py', 'tests/test_n36_engineering.py', 'tests/test_n36_stop_guard.py',
    'tests/test_n36_engineering_integration.py', 'tests/n36_engineering_cpu_fixture.py'})


def exact(actual, expected, label):
    # Canonical JSON equality also distinguishes bool/int/float and rejects NaN.
    w.require(w.canonical_sha(actual) == w.canonical_sha(expected), label)


def reference(value):
    w.require(isinstance(value, dict) and set(value) == {'path', 'sha256'}
              and isinstance(value['path'], str) and Path(value['path']).is_absolute()
              and str(Path(value['path'])) == value['path']
              and isinstance(value['sha256'], str) and len(value['sha256']) == 64
              and all(x in '0123456789abcdef' for x in value['sha256']), 'engineering exact reference')
    return value


def read(reference_value):
    return w.read_ref(reference(reference_value))


def specification():
    spec = _recovery_json(_recovery_read(SPECIFICATION))
    _recovery_specification(spec)
    exact(spec['prospective_amendment'], AMENDMENT, 'R1 pinned amendment')
    read(AMENDMENT)
    recovery = _recovery_contract(spec)
    if recovery is not None:
        # Preparation admission also reads this specification under its operation
        # lock. Validate retained bytes before spending; successor absence in the
        # attempt/health/own journals remains the existing initial-use gate.
        root = Path(_recovery_predecessors(recovery)[0]['own_journal']['path']).parent
        _recovery_capture(recovery, root)
    return spec


def validate_runtime_binding(plan):
    """Exact baseline projection or externally accepted measured preparation.

    Neither branch grants health/episode authority. Readiness proof references
    the immutable baseline/final source, never its own derived runtime hash.
    """
    from scripts import qd_ed_n36_readiness_prepare as preparation_api
    spec = specification()
    policy = spec['runtime_binding']
    preparation = preparation_api.policy(spec)
    reference(plan['runtime'])
    w.require(plan['runtime']['path'] in (policy['runtime_path'], preparation['disabled_runtime_path'])
              and str(Path(plan['runtime']['path']).resolve()) == plan['runtime']['path'],
              'R1 canonical runtime reference path')
    runtime = read(plan['runtime'])
    template = read(spec['canonical_runtime'])
    source_ref = reference(runtime['preparation']['source_record'])
    w.require(source_ref['path'] == policy['source_record_path'], 'R1 exact source record path')
    source = read(source_ref)
    exact(source, plan['source'], 'R1 runtime source record binding')
    exact(source, plan['scientific_source'], 'R1 runtime scientific source binding')
    root = Path(__file__).resolve().parents[1]
    exact(sorted(x['path'] for x in source['files']), sorted(b.source_paths(root)),
          'R1 complete runtime source inventory')
    b.closure.verify_source(root, source)
    w.require(subprocess.run(['git', '--no-replace-objects', '-C', str(root),
                             'merge-base', '--is-ancestor', policy['source_base'], source['commit']],
                            check=False, capture_output=True).returncode == 0,
              'R1 runtime source ancestry')
    changed = subprocess.check_output(['git', '--no-replace-objects', '-C', str(root),
        'diff', '--name-only', policy['source_base'], source['commit'], '--'], text=True).splitlines()
    w.require(set(changed) <= set(policy['source_change_allowlist']) <= (OPERATIONAL_FILES | preparation_api.NEW_FILES),
              'R1 runtime repair source allowlist')
    template['preparation']['source'] = source['commit']
    template['preparation']['source_record'] = source_ref
    if plan['runtime']['path'] == policy['runtime_path']:
        w.require(plan['worktree'] == str(SOURCE) == str(root), 'R1 measured deployed checkout')
        b.attest_loaded(root, source)
        proof_ref = runtime['preparation'].get('readiness_proof')
        template = preparation_api.derive(spec, source, source_ref, proof_ref)
        preparation_api.accepted(spec, proof_ref, plan['runtime'])
    exact(runtime, template, 'R1 exact prospective runtime derivation')
    r.verify_files(runtime['files'], allowed_roots=(runtime['worktree'], runtime['artifact_root']))
    return runtime


def terminal_parent_prefix():
    """Read exact bytes, never infer permission by filtering old identities.

    This is historical evidence only. Every new event is checked separately;
    no historical outcome is replayed or subtracted from global accounting.
    """
    from scripts import qd_ed_n36_engineering as parent
    amendment = read(AMENDMENT)
    terminal = read(amendment['parent_terminal'])
    parent_plan = read(amendment['parent_plan'])
    spec = specification()
    exact(spec['retained_ledger_prefixes'], amendment['ledger_prefixes'], 'R1 amended prefixes')
    exact(terminal['ledger_prefixes'], amendment['ledger_prefixes'], 'R1 terminal prefixes')
    exact(parent_plan['cohort'], parent.IDENTITY, 'R1 parent identity')
    baseline = {}
    for name in JOURNALS:
        anchor = amendment['ledger_prefixes'][name]
        path = Path(anchor['path'])
        full.prefix(path, anchor)
        with path.open('rb') as stream:
            data = stream.read(anchor['bytes'])
        w.require(len(data) == anchor['bytes']
                  and hashlib.sha256(data).hexdigest() == anchor['sha256'],
                  'R1 historical ledger prefix changed during read')
        w.require(data.endswith(b'\n'), 'R1 complete journal prefix')
        baseline[name] = [json.loads(line) for line in data.splitlines() if line.strip()]
    groups = r.event_groups(baseline[JOURNALS[0]])
    w.require(all(group[-1]['event'] in r.TERMINAL for group in groups.values()),
              'R1 live parent attempt')
    old = [event for event in baseline[JOURNALS[0]]
           if str(event.get('attempt_id', '')).startswith('n36_engineering_')
           or str(event.get('cohort', '')).startswith('N36_ENGINEERING')]
    exact(old, terminal['episode_events'], 'R1 known parent terminal events only')
    parent.episode_events(parent_plan, old)
    w.require(old and old[-1]['event'] == 'aborted'
              and terminal['classification'] == 'INVALID'
              and terminal['scientific_eligible'] is False,
              'R1 exact terminal parent failure')
    health_groups = {}
    for event in baseline[JOURNALS[1]]:
        health_groups.setdefault(event['resource_id'], []).append(event)
    w.require(all(group[-1]['event'] in ('completed', 'aborted')
                  for group in health_groups.values()), 'R1 live parent health')
    snapshot = r.budget_snapshot(baseline[JOURNALS[0]], baseline[JOURNALS[1]])
    exact(snapshot, spec['retained_snapshot'], 'R1 charged terminal snapshot')
    return baseline


def row():
    return specification()['scope']['episode']


def disabled_scope():
    """Pure disabled document; not a release or authority factory."""
    return {'schema': 'n36-engineering-scope-v1', 'specification': dict(SPECIFICATION),
            'scope': specification()['scope'], 'release_enabled': False}


def disabled_accounting():
    spec = specification()
    return {'schema': 'n36-engineering-accounting-v1', 'specification': dict(SPECIFICATION),
            'accounting': spec['accounting_proposal'],
            'retained_ledger_prefixes': spec['retained_ledger_prefixes'],
            'retained_snapshot_reference': spec['retained_snapshot_reference'],
            'release_enabled': False, 'root_adopted': False}


def validate_disabled_scope(document):
    exact(document, disabled_scope(), 'exact disabled engineering scope')
    return document


def validate_disabled_accounting(document):
    exact(document, disabled_accounting(), 'exact disabled engineering accounting')
    return document



def validate_scope_reference(value):
    w.require(reference(value)['sha256'] == w.canonical_sha(disabled_scope()),
              'pinned engineering scope canonical bytes')
    return validate_disabled_scope(read(value))


def validate_accounting_reference(value):
    w.require(reference(value)['sha256'] == w.canonical_sha(disabled_accounting()),
              'pinned engineering accounting canonical bytes')
    return validate_disabled_accounting(read(value))

def require_row(value):
    exact(value, row(), 'exact engineering task0/C0 row')


def deployment(plan):
    value = read(plan['deployment'])
    w.require(set(value) == {'schema', 'source_cwd', 'owner_root', 'output_root', 'stop_authority'}
              and value['schema'] == 'n36-engineering-deployment-v1'
              and value['source_cwd'] == str(SOURCE) and value['owner_root'] == str(OWNER)
              and value['stop_authority'] == stop.binding(), 'engineering lexical deployment')
    output = Path(value['output_root'])
    # New execution space, never a checkout or historical evidence directory.
    # The exact leaf is separately bound in B5 and all root approvals.
    parent = SESSION / 'engineering-executions'
    w.require(output.is_absolute() and str(output) == value['output_root']
              and output.parent == parent and output.name == EPISODE_KEY
              and output.resolve() == output and not output.is_symlink()
              and SOURCE.resolve() == SOURCE and OWNER.resolve() == OWNER,
              'engineering isolated output/source/owner route')
    return value


def owner_root(plan):
    deployment(plan)
    w.require(plan['worktree'] == str(SOURCE), 'engineering source cwd')
    return OWNER


def operational_binding(plan):
    w.require(plan.get('schema') == PLAN_SCHEMA and plan.get('cohort') == IDENTITY
              and plan.get('purpose') == PURPOSE, 'engineering operational identity')
    return {'cohort': IDENTITY, 'purpose': PURPOSE, 'scope': plan['scope'],
            'accounting': plan['accounting'], 'audit_plan': plan['audit_plan'],
            'engineering_manifest': plan['engineering_manifest'], 'deployment': plan['deployment'],
            'scientific_eligible': False, 'matched_improvement_eligible': False,
            'promotion_eligible': False, 'continuation_authorized': False}


def validate_audit_view(plan, *, require_manifests=True):
    """Keep all forty scientific rows and gates in a disabled audit-only view."""
    spec = specification()
    validate_runtime_binding(plan)
    original_ref = {k: spec['full_audit_view']['immutable_original_plan'][k] for k in ('path', 'sha256')}
    original = read(original_ref)
    fields = {'schema', 'original_plan', 'dispatch_authority', 'frozen', 'release_enabled',
              'worktree', 'artifact_root', 'source', 'scientific_source', 'runtime', 'native_build',
              'runtime_closure', 'controller_semantics', 'episodes', 'limits', 'worker_contract',
              'deadline', 'stop_path', 'stop_authority', 'phase_authorization', 'expected_manifests',
              'cohort', 'protocol', 'protocol_review', 'accounting', 'deployment', 'scope',
              'attempt_identity', *RUNTIME_INPUTS}
    w.require(set(plan) == fields and plan['schema'] == AUDIT_SCHEMA
              and plan['dispatch_authority'] is False and plan['release_enabled'] is False
              and plan['frozen'] is True and plan['attempt_identity'] == 'episode_key',
              'disabled full audit view fields')
    exact(plan['original_plan'], original_ref, 'immutable original plan anchor')
    for key in ('cohort', 'episodes', 'limits', 'worker_contract', 'deadline', 'protocol', 'protocol_review', 'accounting'):
        exact(plan[key], original[key], 'immutable audit science: ' + key)
    exact(plan['episodes'], c.expected_rows(SOURCE, cohort=c.DRAFT_N36R4_COHORT), 'full audit matrix')
    w.require(plan['limits'] == c.LIMITS and plan['worker_contract'] == c.WORKER_CONTRACT
              and plan['protocol_review']['sha256'] == c.PROTOCOL_REVIEW_SHA, 'full audit gates')
    validate_scope_reference(plan['scope'])
    route = deployment(plan)
    w.require(plan['worktree'] == str(SOURCE) and plan['artifact_root'] == str(Path(route['output_root']) / 'audit-only')
              and plan['phase_authorization'] == {'dev': False, 'validation': False, 'formal': False},
              'audit-only routing/phase')
    c.validate_stop_binding(plan)
    keys = {x['episode_key'] for x in plan['episodes']}
    w.require(set(plan['expected_manifests']) == keys if require_manifests else
              set(plan['expected_manifests']) <= keys, 'all40 engineering audit manifests')
    w.require(plan['source'] == plan['scientific_source'], 'single reviewed adapter source')
    for key in ('runtime', 'native_build', 'runtime_closure', 'controller_semantics', 'protocol', 'protocol_review', 'accounting'):
        reference(plan[key])
    return plan


def audit_mapping(plan, audit, engineering_row):
    require_row(engineering_row)
    validate_plan_shape(plan)
    exact(audit, read(plan['audit_plan']), 'hash-bound full audit view differs')
    validate_audit_view(audit)
    w.require(plan['schema'] == PLAN_SCHEMA and plan['episodes'] == [row()]
              and plan['cohort'] == IDENTITY and plan['purpose'] == PURPOSE,
              'separate engineering plan identity')
    original = audit['episodes'][0]
    exact({**original, 'iteration': IDENTITY, 'episode_key': EPISODE_KEY}, engineering_row,
          'only audited task0/C0 identity may map to engineering')
    for key in ('scope', 'deployment', 'source', 'scientific_source', 'runtime', 'runtime_closure',
                'native_build', 'controller_semantics', 'worktree', *RUNTIME_INPUTS):
        exact(plan[key], audit[key], 'engineering/audit binding: ' + key)
    w.require(plan['artifact_root'] == deployment(plan)['output_root'], 'engineering output binding')
    return original


def validate_plan_shape(plan, *, released=False):
    """Closed schema also used by disabled command/manifest preparation."""
    fields = {'schema', 'frozen', 'release_enabled', 'cohort', 'purpose', 'episodes',
              'limits', 'worker_contract', 'deadline', 'stop_path', 'stop_authority',
              'phase_authorization', 'attempt_identity', 'worktree', 'artifact_root',
              'authority', 'b5_review', 'expected_manifests', *BINDINGS, *RUNTIME_INPUTS}
    w.require(set(plan) == fields and plan['schema'] == PLAN_SCHEMA
              and type(plan['frozen']) is bool and type(plan['release_enabled']) is bool
              and plan['frozen'] is plan['release_enabled']
              and (not released or plan['release_enabled'] is True)
              and plan['cohort'] == IDENTITY and plan['purpose'] == PURPOSE,
              'distinct released engineering plan required')
    validate_runtime_binding(plan)
    exact(plan['limits'], LIMITS, 'engineering finite limits')
    exact(plan['episodes'], [row()], 'one engineering episode')
    exact(plan['worker_contract'], c.WORKER_CONTRACT, 'unchanged worker gates')
    w.require(plan['deadline'] == c.DEADLINE and plan['attempt_identity'] == 'episode_key'
              and plan['phase_authorization'] == {'engineering': plan['release_enabled'], 'dev': False, 'validation': False, 'formal': False}
              and (plan['expected_manifests'] == {EPISODE_KEY: plan['engineering_manifest']}
                   or (not released and plan['release_enabled'] is False and plan['expected_manifests'] == {})),
              'engineering phase/manifest authority')
    owner_root(plan)
    c.validate_stop_binding(plan)
    validate_scope_reference(plan['scope'])
    validate_accounting_reference(plan['accounting'])
    return plan


def validate_plan(plan):
    validate_plan_shape(plan, released=True)
    audit_mapping(plan, read(plan['audit_plan']), row())
    return plan


def scientific_equivalence(plan):
    evidence = read(plan['scientific_equivalence'])
    command = ['git', '-C', str(SOURCE), 'diff', '--name-only', BASE, plan['source']['commit'], '--']
    changed = subprocess.check_output(command, text=True).splitlines()
    w.require(set(changed) <= OPERATIONAL_FILES, 'scientific source changed outside operational adapter')
    w.require(subprocess.run(['git', '-C', str(SOURCE), 'merge-base', '--is-ancestor', BASE,
                             plan['source']['commit']], check=False, capture_output=True).returncode == 0,
              'adapter source base ancestry')
    exact(evidence, {'schema': 'n36-engineering-scientific-equivalence-v1', 'base_commit': BASE,
          'source': plan['source'], 'changed_paths': sorted(changed), 'scientific_changes': False},
          'exact reviewed scientific equivalence')


def review_bindings(plan):
    return {key: plan[key] for key in BINDINGS}


def validate_authority(plan, authority):
    """Validate separate approvals and retained prefixes, never write owner state."""
    validate_plan(plan)
    bindings = review_bindings(plan)
    exact(read(plan['b5_review']), {'schema': 'n36-engineering-independent-b5-review-v1',
          'decision': 'PASS_PREPARATION_REQUIRES_ROOT_RELEASE', **bindings,
          'worker_receipts_are_future': True, 'release_enabled': False}, 'exact independent engineering B5')
    fixed = {'schema': 'n36-engineering-budget-authority-v1', 'approved': True,
             'cohort': IDENTITY, 'purpose': PURPOSE, **bindings, 'b5_review': plan['b5_review'],
             'caps': c.CAPS, 'limits': LIMITS, 'automatic_recoveries': 0,
             'validation_authorized': False, 'formal_authorized': False,
             'coordinator_ends_at': c.DEADLINE}
    variable = {'starts_at', 'weekly_window', 'approval_basis', 'protocol_acceptance',
                'source_adoption', 'amendment', 'ledger_prefixes', 'margin_reference'}
    w.require(set(authority) == set(fixed) | variable, 'engineering authority fields')
    for key, value in fixed.items():
        exact(authority[key], value, 'engineering authority binding: ' + key)
    full.validate_caps(authority['caps'])
    window = authority['weekly_window']
    exact(window, {'origin_gpu_hours': 53.08404692669838, 'increment_gpu_hours': 168.,
                   'ends_at': c.DEADLINE}, 'unchanged weekly cap/deadline')
    starts = dt.datetime.fromisoformat(authority['starts_at'].replace('Z', '+00:00'))
    w.require(starts.tzinfo is not None and starts < dt.datetime.fromisoformat(c.DEADLINE.replace('Z', '+00:00')),
              'engineering authority start')
    read(authority['approval_basis'])
    exact(read(authority['protocol_acceptance']), {
          'schema': 'n36-engineering-root-protocol-acceptance-v1', 'approved': True,
          **bindings, 'b5_review': plan['b5_review'], 'limits': LIMITS}, 'root engineering protocol acceptance')
    exact(read(authority['source_adoption']), {
          'schema': 'n36-engineering-source-adoption-v1', 'approved': True, **bindings,
          'b5_review': plan['b5_review'], 'protocol_acceptance': authority['protocol_acceptance'],
          'owner_root': str(OWNER), 'source_cwd': str(SOURCE)}, 'root engineering source adoption')
    scientific_equivalence(plan)
    spec = specification()
    exact(authority['ledger_prefixes'], spec['retained_ledger_prefixes'], 'all three retained engineering prefixes')
    retained = read({key: spec['retained_snapshot_reference'][key] for key in ('path', 'sha256')})
    amendment = read(authority['amendment'])
    exact(amendment, {'schema': 'n36-engineering-owning-accounting-v1', 'approved': True,
          **bindings, 'source_adoption': authority['source_adoption'], 'caps': c.CAPS,
          'limits': LIMITS, 'ledger_prefixes': authority['ledger_prefixes'],
          'snapshot': spec['retained_snapshot'], 'arithmetic': spec['accounting_proposal'],
          'margin_reference': authority['margin_reference'], 'automatic_recoveries': 0},
          'owning engineering accounting adoption')
    baseline = {}
    for name in JOURNALS:
        anchor = authority['ledger_prefixes'][name]
        path = OWNER / 'data' / name
        w.require(anchor['path'] == str(path), 'engineering owner prefix route')
        full.prefix(path, anchor)
        with path.open('rb') as stream:
            baseline[name] = [json.loads(line) for line in stream.read(anchor['bytes']).splitlines() if line.strip()]
    snap = r.budget_snapshot(baseline[JOURNALS[0]], baseline[JOURNALS[1]])
    exact(snap, spec['retained_snapshot'], 'whole retained snapshot')
    w.require(snap['reserved_attempts'] == snap['dispatched'] == 507
              and snap['gpu_hours_consumed'] == 75.64264702604362
              and all(g[-1]['event'] in r.TERMINAL for g in r.event_groups(baseline[JOURNALS[0]]).values()),
              'retained charges/unsettled attempts')
    margin = accounting.retained_margin(OWNER, authority['margin_reference'])
    w.require(Decimal(str(margin)) == Decimal('0.23357169027962'), 'unchanged retained margin')
    exact(baseline, terminal_parent_prefix(), 'R1 authority terminal parent prefix')
    return baseline


def _verify_release_transaction(plan_ref, release_ref, *, health=False):
    with b.closure.verification_phase('engineering_release'):
        plan = validate_plan(read(plan_ref))
        authority = read(plan['authority'])
        validate_authority(plan, authority)
        release = read(release_ref)
        kind = 'health' if health else 'episode'
        expected = {'schema': 'n36-engineering-' + kind + '-release-v1', 'approved': True,
                    'plan': plan_ref, 'authority': plan['authority'], 'b5_review': plan['b5_review'],
                    **review_bindings(plan), 'limits': LIMITS, 'purpose': PURPOSE,
                    'issued_at': release.get('issued_at')}
        if not health:
            expected['readiness'] = release.get('readiness')
        w.require(set(release) == set(expected) | {'root_review'}, 'engineering detached release fields')
        exact({k: release[k] for k in expected}, expected, 'engineering detached release differs')
        exact(read(release['root_review']), {**expected,
              'schema': 'n36-engineering-root-' + kind + '-review-v1', 'decision': 'APPROVED'},
              'engineering root review differs')
        issued = dt.datetime.fromisoformat(release['issued_at'].replace('Z', '+00:00'))
        starts = dt.datetime.fromisoformat(authority['starts_at'].replace('Z', '+00:00'))
        end = dt.datetime.fromisoformat(c.DEADLINE.replace('Z', '+00:00'))
        w.require(issued.tzinfo is not None and starts <= issued <= dt.datetime.now(dt.timezone.utc)
                  and (end - issued).total_seconds() >= 2100, 'engineering release full 2100-second envelope')
        audit = read(plan['audit_plan'])
        evidence = full.verify_audit_closure(audit)
        runtime = evidence.runtime
        mapping = audit_mapping(plan, audit, row())
        manifest = b.verify_engineering_manifest(plan['engineering_manifest'], plan, runtime, row(), audit=audit)
        w.require(evidence.manifests[mapping['episode_key']]['row'] == mapping, 'verified audit row binding')
        if not health:
            terminal = validate_readiness(plan_ref, release)
            w.require(terminal['time_unix'] <= issued.timestamp(),
                      'engineering episode release predates settled health')
        return plan, runtime, authority, {EPISODE_KEY: manifest}


def validate_engineering_release(plan_ref, release_ref):
    return _verify_release_transaction(plan_ref, release_ref)[:3]


def validate_engineering_health_release(plan_ref, release_ref):
    return _verify_release_transaction(plan_ref, release_ref, health=True)[:3]


validate_release = validate_engineering_release
validate_health_release = validate_engineering_health_release


def _identity(value):
    return {key: value[key] for key in ('split', 'iteration', 'profile', 'task_id', 'env_seed', 'policy_seed', 'init_index')}


def episode_events(plan, events):
    """Every supplied event is a prospective suffix, never a historical filter."""
    binding = operational_binding(plan)
    selected = row()
    immutable = ('attempt_id', 'episode_key', 'identity', 'budget_bucket', 'replacement',
                 'plan_sha256', 'release', 'source_commit', 'runtime_manifest_sha256',
                 'runtime_inventory_sha256', 'init_row_sha256', 'output_dir', 'physical_gpu',
                 'ledger_prefix', 'context', 'reserved_gpu_seconds', 'accounting_admission', *binding)
    for event in events:
        w.require(event.get('attempt_id') == event.get('episode_key') == EPISODE_KEY
                  and event.get('identity') == _identity(selected), 'engineering journal identity')
        exact(event.get('identity'), _identity(selected), 'engineering exact typed journal identity')
        c.event_binding(selected, event)
        for key, value in binding.items():
            exact(event.get(key), value, 'engineering journal binding: ' + key)
        w.require(event.get('source_commit') == plan['source']['commit']
                  and event.get('runtime_manifest_sha256') == plan['runtime']['sha256']
                  and event.get('runtime_inventory_sha256') == plan['runtime_inventory_sha256']
                  and event.get('init_row_sha256') == selected['init_row_sha256']
                  and event.get('output_dir') == str(Path(plan['artifact_root']) / 'attempts' / EPISODE_KEY)
                  and type(event.get('physical_gpu')) is int and event['physical_gpu'] == 7
                  and type(event.get('reserved_gpu_seconds')) is int and event['reserved_gpu_seconds'] == 1840
                  and event.get('accounting_admission', {}).get('reserved_gpu_seconds') == 1840,
                  'engineering episode full reservation binding')
    if events:
        w.require(all(all(key in event and event[key] == events[0][key] for key in immutable)
                      for event in events), 'engineering episode lifecycle binding changed')
        kinds = [event['event'] for event in events]
        w.require(kinds in (['reserved'], ['reserved', 'dispatched'],
                            ['reserved', 'dispatched', 'valid'], ['reserved', 'dispatched', 'aborted']),
                  'engineering one-use episode lifecycle/replay')
        if 'dispatched' in kinds:
            w.require(type(events[1].get('timeout_seconds')) is int and events[1]['timeout_seconds'] == 1800,
                      'engineering exact dispatched timeout')
        if kinds[-1] in r.TERMINAL:
            w.require(c.finite(events[-1]['gpu_process_wall_seconds'], 'engineering episode charge') <= 1840,
                      'engineering episode exceeds reservation')
    return events


def resource_events(plan, events):
    binding = operational_binding(plan)
    for event in events:
        w.require(event.get('resource_id') == HEALTH_ID and event.get('kind') == HEALTH_KIND,
                  'engineering sole health identity')
        for key, value in binding.items():
            exact(event.get(key), value, 'engineering health binding: ' + key)
        exact({key: event.get(key) for key in ('timeout_seconds', 'cleanup_seconds', 'reserved_gpu_seconds', 'physical_gpu', 'gpu_uuid')},
              {'timeout_seconds': 20, 'cleanup_seconds': 40, 'reserved_gpu_seconds': 60,
               'physical_gpu': 7, 'gpu_uuid': c.GPU_UUID}, 'engineering health full reservation')
        w.require(event.get('source_commit') == plan['source']['commit'] and event.get('runtime') == plan['runtime']
                  and read(event['plan']) == plan
                  and event['accounting_admission']['reserved_gpu_seconds'] == 60, 'engineering health source/plan')
    if events:
        immutable = ('plan', 'release', 'source_commit', 'runtime', 'accounting_admission', *binding)
        w.require(all(all(key in event and event[key] == events[0][key] for key in immutable) for event in events),
                  'engineering health lifecycle binding changed')
        kinds = [event['event'] for event in events]
        w.require(kinds in (['reserved'], ['reserved', 'dispatched'], ['reserved', 'aborted'],
                            ['reserved', 'dispatched', 'completed'], ['reserved', 'dispatched', 'aborted']),
                  'engineering one-use health lifecycle/replay')
        if kinds[-1] in ('completed', 'aborted'):
            w.require(c.finite(events[-1]['gpu_process_wall_seconds'], 'engineering health charge') <= 60,
                      'engineering health exceeds reservation')
    return events


def _recovery_json(data):
    """Strict JSON for captured recovery evidence, including nested duplicate keys."""
    def pairs(items):
        result = {}
        for key, value in items:
            w.require(key not in result, 'duplicate recovery JSON key')
            result[key] = value
        return result
    value = json.loads(data, object_pairs_hook=pairs)
    w.canonical_sha(value)  # Reject nonfinite numbers, including exponent overflow.
    return value


def _recovery_rows(data):
    w.require(not data or data.endswith(b'\n'), 'torn recovery journal')
    rows = [_recovery_json(line) for line in data.splitlines()]
    w.require(all(isinstance(row, dict) for row in rows), 'malformed recovery row')
    return rows


def _recovery_read(ref):
    reference(ref)
    path = Path(ref['path'])
    w.require(path.is_file() and not path.is_symlink(), 'recovery reference path')
    data = path.read_bytes()
    w.require(hashlib.sha256(data).hexdigest() == ref['sha256'], 'recovery reference hash')
    return data


def _recovery_inventory(spec, historical):
    """Admit one pinned inventory correction while comparing the entire baseline.

    The old runtime stays immutable. This checks source bytes, not readiness,
    adoption, native success, or permission to consume any additional budget.
    """
    if ('canonical_inventory_amendment' not in spec
            and spec.get('canonical_runtime') == historical.get('canonical_runtime')):
        return False
    ref = reference(spec['canonical_inventory_amendment'])
    # Both existing owner/shared lexical routes may refer to the same evidence.
    w.require(ref['sha256'] == INVENTORY_AMENDMENT['sha256']
              and Path(ref['path']).resolve() == Path(INVENTORY_AMENDMENT['path']).resolve(),
              'pinned canonical inventory amendment')
    amendment = _recovery_json(_recovery_read(ref))
    authority = _recovery_json(_recovery_read(INVENTORY_AUTHORITY))
    exact(authority['amendment'], INVENTORY_AMENDMENT, 'inventory engineering authority')
    exact(amendment['authority'], {k: authority['authority'][k] for k in ('path', 'sha256')},
          'inventory owning authority')
    owning = _recovery_read(amendment['authority'])
    exact(len(owning), authority['authority']['bytes'], 'inventory authority bytes')
    exact(amendment['old_canonical_runtime'], historical['canonical_runtime'],
          'inventory immutable old canonical reference')
    old_ref = reference(historical['canonical_runtime'])
    new_ref = reference(spec['canonical_runtime'])
    w.require(Path(new_ref['path']).resolve() != Path(old_ref['path']).resolve()
              and new_ref['sha256'] != old_ref['sha256'], 'fresh canonical inventory document')
    old = _recovery_json(_recovery_read(old_ref))
    new = _recovery_json(_recovery_read(new_ref))
    before, after = amendment['change']['before'], amendment['change']['after']
    matches = [i for i, row in enumerate(old['files']) if row['path'] == before['path']]
    w.require(len(matches) == 1, 'unique amended inventory row')
    index = matches[0]
    exact(old['files'][index], before, 'inventory exact old hash and size')
    expected = json.loads(json.dumps(old))
    expected['files'][index] = after
    exact(new, expected, 'inventory exact one-row delta and immutable runtime')
    # Check both the recorded deployed bytes (read-only) and this validator's
    # checkout; no other inventory inputs or protected datasets are opened here.
    for path in (Path(after['path']), Path(__file__).resolve().with_name('qd_ed_n36_source.py')):
        w.require(path.is_file() and not path.is_symlink(), 'inventory source file path')
        data = path.read_bytes()
        w.require(len(data) == after['size_bytes']
                  and hashlib.sha256(data).hexdigest() == after['sha256'],
                  'inventory actual reviewed source bytes')
    w.require(str(Path(after['path']).resolve()) == after['resolved_path'],
              'inventory source resolved path')
    w.require(new['cuda_egl_verified'] is new['provider_ready'] is False
              and new['gpu_mapping']['cuda_egl_verified'] is False
              and new['preparation']['runtime_ready'] is False
              and new['preparation']['release_enabled'] is False,
              'inventory baseline remains disabled')
    return True


def _recovery_inventory_previous(spec, previous_ref, historical):
    """Validate a new derived snapshot without relabelling the historical spec."""
    reference(previous_ref)
    w.require(Path(previous_ref['path']).resolve() != Path(HISTORICAL_SPECIFICATION['path']).resolve(),
              'inventory previous snapshot must be a new document')
    previous = _recovery_json(_recovery_read(previous_ref))
    expected = json.loads(json.dumps(historical))
    expected['canonical_runtime'] = spec['canonical_runtime']
    expected['prospective_inventory_derivation'] = {
        'historical_original': HISTORICAL_SPECIFICATION,
        'amendment': spec['canonical_inventory_amendment'],
        'scope': 'New disabled prospective snapshot; historical original is unchanged and not represented as amended.'}
    exact(previous, expected, 'inventory previous snapshot immutable projection')


def _recovery_specification(spec):
    """Allow only prospective operational rebinding of the immutable old spec."""
    if SPECIFICATION == HISTORICAL_SPECIFICATION:
        return
    w.require(SPECIFICATION['path'] != HISTORICAL_SPECIFICATION['path'],
              'prospective specification must use new evidence path')
    historical = _recovery_json(_recovery_read(HISTORICAL_SPECIFICATION))
    projected = json.loads(json.dumps(spec))
    inventory_amended = _recovery_inventory(spec, historical)
    if inventory_amended:
        projected.pop('canonical_inventory_amendment')
        projected['canonical_runtime'] = historical['canonical_runtime']
    for key in ('readiness_recovery', 'recovery_prefix_contract'):
        reference(spec[key])
        w.require(spec[key]['path'] != historical[key]['path'], 'fresh recovery evidence path')
        projected[key] = historical[key]
    for key in ('preparation', 'runtime_path', 'source_record_path'):
        projected['runtime_binding'][key] = historical['runtime_binding'][key]
    if spec['runtime_binding'].get('amendment') != historical['runtime_binding'].get('amendment'):
        from scripts import qd_ed_n36_readiness_prepare as preparation_api
        # Validate the owning scope and its exact composition before projecting
        # only these two operational fields. All scientific/accounting fields,
        # repair authority, base, limits and recovery checks remain immutable.
        preparation_api.policy(spec)
        amendment = _recovery_json(_recovery_read(spec['runtime_binding']['amendment']))
        exact(amendment['schema'], 'n36-disabled-source-scope-composition-v1',
              'prospective scope composition required')
        exact(amendment['previous_runtime_amendment'], historical['runtime_binding']['amendment'],
              'historical scope amendment lineage')
        for key in ('amendment', 'source_change_allowlist'):
            projected['runtime_binding'][key] = historical['runtime_binding'][key]
    exact(projected, historical, 'immutable scientific and accounting specification')
    w.require(spec['runtime_binding']['preparation']['path'] !=
              historical['runtime_binding']['preparation']['path'], 'fresh preparation policy path')
    policy = _recovery_json(_recovery_read(spec['runtime_binding']['preparation']))
    old_policy = _recovery_json(_recovery_read(historical['runtime_binding']['preparation']))
    for key in ('runtime_path', 'source_record_path'):
        w.require(spec['runtime_binding'][key] != historical['runtime_binding'][key],
                  'fresh runtime evidence path')
    projected_policy = dict(policy)
    if inventory_amended:
        exact(policy['baseline'], spec['canonical_runtime'], 'inventory preparation baseline')
        projected_policy['baseline'] = old_policy['baseline']
    for key in old_policy:
        if key.endswith('_path'):
            w.require(policy[key] != old_policy[key], 'fresh preparation output path')
        if key.endswith('_path') or key in ('previous_specification', 'resource_id'):
            projected_policy[key] = old_policy[key]
    exact(projected_policy, old_policy, 'immutable preparation policy limits')
    if inventory_amended:
        _recovery_inventory_previous(spec, policy['previous_specification'], historical)
    else:
        exact(policy['previous_specification'], HISTORICAL_SPECIFICATION, 'prospective specification lineage')
    w.require(policy['resource_id'] != old_policy['resource_id'], 'consumed pinned preparation identity')
    contract = _recovery_contract(spec)
    w.require(contract['schema'] in ('n36-failed-readiness-recovery-prefix-contract-v2',
                                    'n36-readiness-recovery-prefix-contract-v3'),
              'prospective multi-predecessor contract required')


def _recovery_predecessors(contract):
    return (contract['predecessors'] if contract['schema'] in (
                'n36-failed-readiness-recovery-prefix-contract-v2',
                'n36-readiness-recovery-prefix-contract-v3')
            else [contract['predecessor']])


def _recovery_contract(spec):
    if 'recovery_prefix_contract' not in spec:
        return None
    contract = _recovery_json(_recovery_read(spec['recovery_prefix_contract']))
    keys = ('accepted_review amendment drafting_authority full_ledgers_required_for_budget_snapshots '
            'gpu_authorized identity original_ledger_prefixes own_journal_at_draft predecessor '
            'production_authority provider_measurement_authorized read_semantics release_enabled '
            'retained_snapshot_reference root_observed_ledger_prefixes root_terminal_reconciliation '
            'schema scientific_success status successor').split()
    w.require(isinstance(contract, dict), 'recovery contract object')
    explicit_terminal = contract.get('schema') == 'n36-readiness-recovery-prefix-contract-v3'
    multi = explicit_terminal or contract.get('schema') == 'n36-failed-readiness-recovery-prefix-contract-v2'
    if multi:
        keys[keys.index('predecessor')] = 'predecessors'
    w.require(isinstance(contract, dict) and set(contract) == set(keys), 'closed recovery contract')
    exact(contract['schema'], 'n36-readiness-recovery-prefix-contract-v3' if explicit_terminal else
          ('n36-failed-readiness-recovery-prefix-contract-v2' if multi else
           'n36-failed-readiness-recovery-prefix-contract-v1'), 'recovery schema')
    for key in ('gpu_authorized', 'production_authority', 'provider_measurement_authorized',
                'release_enabled', 'scientific_success'):
        exact(contract[key], False, 'historical recovery is not authority')
    exact(contract['full_ledgers_required_for_budget_snapshots'], True, 'complete recovery budgets')
    exact(contract['amendment'], AMENDMENT, 'original recovery amendment')
    exact(contract['identity'], spec['readiness_recovery'], 'bound recovery identity')
    exact(contract['original_ledger_prefixes'], spec['retained_ledger_prefixes'], 'original recovery offsets')
    amendment = _recovery_json(_recovery_read(AMENDMENT))
    exact(contract['original_ledger_prefixes'], amendment['ledger_prefixes'], 'unchanged amendment offsets')
    exact(contract['retained_snapshot_reference'], spec['retained_snapshot_reference'], 'original recovery snapshot')
    identity = _recovery_json(_recovery_read(contract['identity']))
    reconciliation = _recovery_json(_recovery_read(contract['root_terminal_reconciliation']))
    exact(reconciliation['schema'], 'n36-recovery-binding-review-terminal-reconciliation-v1',
          'root recovery reconciliation schema')
    exact({k: reconciliation['review'][k] for k in ('path', 'sha256')},
          contract['accepted_review'], 'root accepted recovery review')
    _recovery_read(contract['accepted_review'])
    exact(reconciliation['live_handles'], [], 'historically reconciled handles')
    exact(reconciliation['root_accepts_blocking_findings'], True, 'root recovery findings')
    exact(reconciliation['ledger_prefixes'], contract['root_observed_ledger_prefixes'], 'root recovery anchors')
    predecessors, successor = _recovery_predecessors(contract), contract['successor']
    w.require(isinstance(predecessors, list) and predecessors, 'nonempty retained predecessors')
    ids = []
    for predecessor in predecessors:
        predecessor_keys = set((
            'consumed events global_health_segment kind own_journal provider_calls_retained '
            'raw_bytes raw_sequence resource_id retained_charge_gpu_hours '
            'retained_charge_gpu_seconds row_segments rows telemetry_complete').split())
        if explicit_terminal:
            predecessor_keys.add('terminal_status')
        w.require(isinstance(predecessor, dict) and set(predecessor) == predecessor_keys, 'closed predecessor')
        rid = predecessor['resource_id']
        w.require(isinstance(rid, str) and rid and rid not in ids
                  and rid not in (successor['resource_id'], HEALTH_ID, EPISODE_KEY),
                  'distinct consumed predecessor identities')
        ids.append(rid)
        exact(predecessor['kind'], 'readiness_preparation', 'predecessor kind')
        # v1/v2 remain abort-only. v3 explicitly binds each consumed terminal;
        # completed history is retained accounting, never successor readiness.
        terminal_status = predecessor['terminal_status'] if explicit_terminal else 'aborted'
        w.require(terminal_status in ('aborted', 'completed'), 'retained terminal status')
        exact(predecessor['events'], ['reserved', 'dispatched', terminal_status], 'terminal predecessor order')
        exact(predecessor['consumed'], True, 'consumed predecessor')
        exact(predecessor['telemetry_complete'], terminal_status == 'completed', 'retained terminal telemetry semantics')
    exact(successor, dict(automatic_retry=False, kind='readiness_preparation',
        occurrences_in_complete_ledgers={name: 0 for name in (*JOURNALS, 'readiness-preparation-ledger.jsonl')},
        resource_id=identity['resource_id'], unconsumed_at_draft=True), 'explicit recovery successor')
    w.require(isinstance(successor['resource_id'], str) and successor['resource_id']
              and successor['resource_id'] not in (HEALTH_ID, EPISODE_KEY), 'separate successor identity')
    exact(identity['recovery_of'], ids if multi else ids[0], 'explicit recovery predecessors')
    exact(identity['retained_charge_gpu_hours'],
          sum(p['retained_charge_gpu_hours'] for p in predecessors) if multi else
          predecessors[0]['retained_charge_gpu_hours'], 'retained identity charge')
    policy = _recovery_json(_recovery_read(spec['runtime_binding']['preparation']))
    exact(policy['resource_id'], successor['resource_id'], 'bound recovery policy successor')
    # identity.source is historical provenance. Current source is validated later.
    return contract


def _recovery_capture(contract, root):
    """Capture and authenticate raw journals; caller holds owner operation lock.

    Recheck captures before returning. This does not grant readiness or require
    the successor to stay absent after its separately authorized initial use.
    """
    predecessors = _recovery_predecessors(contract)
    identity = contract['successor']['resource_id']
    captures = {}
    for name in (*JOURNALS, 'readiness-preparation-ledger.jsonl'):
        path = root / name
        w.require(path.is_file() and not path.is_symlink(), 'recovery journal path')
        captures[name] = path.read_bytes()
    for name in JOURNALS:
        data = captures[name]
        for anchors in (contract['original_ledger_prefixes'], contract['root_observed_ledger_prefixes']):
            anchor = anchors[name]
            w.require(anchor['path'] == str(root / name) and type(anchor['bytes']) is int
                      and 0 <= anchor['bytes'] <= len(data), 'recovery anchor route/offset')
            prefix = data[:anchor['bytes']]
            w.require(hashlib.sha256(prefix).hexdigest() == anchor['sha256'], 'recovery anchor bytes')
            w.require(not prefix or prefix.endswith(b'\n'), 'torn recovery anchor')
    own = captures['readiness-preparation-ledger.jsonl']
    global_raw = captures[JOURNALS[1]]
    offset = contract['original_ledger_prefixes'][JOURNALS[1]]['bytes']
    own_offset, retained_all = 0, []
    for predecessor in predecessors:
        raw = _recovery_read(predecessor['raw_sequence'])
        w.require(type(predecessor['raw_bytes']) is int and len(raw) == predecessor['raw_bytes'],
                  'recovery retained raw length')
        for segment, name, begin in ((predecessor['own_journal'], 'readiness-preparation-ledger.jsonl', own_offset),
                                    (predecessor['global_health_segment'], JOURNALS[1], offset)):
            exact(segment, dict(path=str(root / name), start_inclusive=begin,
                  end_exclusive=begin + len(raw), sha256=predecessor['raw_sequence']['sha256']),
                  'exact predecessor segment')
            w.require(captures[name][begin:begin+len(raw)] == raw, 'exact retained predecessor bytes')
        lines = raw.splitlines(keepends=True)
        w.require(len(lines) == len(predecessor['row_segments']) == 3, 'three retained raw rows')
        cursor = 0
        for line, event, segment in zip(lines, predecessor['events'], predecessor['row_segments']):
            exact(segment, dict(bytes=len(line), event=event, global_end_exclusive=offset+cursor+len(line),
                global_start_inclusive=offset+cursor, own_end_exclusive=own_offset+cursor+len(line),
                own_start_inclusive=own_offset+cursor, sha256=hashlib.sha256(line).hexdigest()), 'retained row offsets/hash')
            cursor += len(line)
        retained = _recovery_rows(raw)
        exact(retained, predecessor['rows'], 'typed retained predecessor rows')
        exact([row['event'] for row in retained], predecessor['events'], 'retained event sequence')
        w.require(all(row['resource_id'] == predecessor['resource_id'] and
                      row['kind'] == predecessor['kind'] for row in retained), 'retained row identity')
        terminal = retained[-1]
        if contract['schema'] == 'n36-readiness-recovery-prefix-contract-v3':
            exact(terminal['event'], predecessor['terminal_status'], 'retained terminal status binding')
            exact(terminal['telemetry_complete'], predecessor['terminal_status'] == 'completed',
                  'retained terminal telemetry semantics')
            if predecessor['terminal_status'] == 'completed':
                w.require(type(terminal['provider_calls']) is int and terminal['provider_calls'] == 1,
                          'completed retained provider call')
        exact(terminal['telemetry_complete'], predecessor['telemetry_complete']
              if contract['schema'] == 'n36-readiness-recovery-prefix-contract-v3' else False,
              'retained terminal telemetry')
        exact(terminal['provider_calls'], predecessor['provider_calls_retained'], 'retained provider calls')
        exact(terminal['gpu_process_wall_seconds'], predecessor['retained_charge_gpu_seconds'], 'retained seconds')
        exact(terminal['gpu_process_wall_seconds'] / 3600, predecessor['retained_charge_gpu_hours'], 'retained hours')
        w.require(type(terminal['gpu_process_wall_seconds']) in (int, float)
                  and terminal['gpu_process_wall_seconds'] > 0, 'positive retained charge')
        retained_all.extend(retained)
        own_offset += len(raw)
        offset += len(raw)
    exact(contract['own_journal_at_draft'], dict(path=str(root / 'readiness-preparation-ledger.jsonl'),
          bytes=own_offset, sha256=hashlib.sha256(own[:own_offset]).hexdigest()), 'historical own anchor')
    # The observed health anchor must end exactly after every retained lifecycle.
    exact(contract['root_observed_ledger_prefixes'][JOURNALS[1]]['bytes'], offset,
          'complete observed predecessor prefix')
    parsed = {name: _recovery_rows(data) for name, data in captures.items()}
    for name in (JOURNALS[0], JOURNALS[2]):
        w.require(not any(value in (row.get('resource_id'), row.get('attempt_id'), row.get('episode_key'))
                          for row in parsed[name] for value in [identity, *(p['resource_id'] for p in predecessors)]),
                  'recovery identity outside resource journals')
    historical = _recovery_rows(global_raw[:contract['original_ledger_prefixes'][JOURNALS[1]]['bytes']])
    w.require(not any(value in (row.get('resource_id'), row.get('attempt_id'), row.get('episode_key'))
                      for row in historical
                      for value in [identity, *(p['resource_id'] for p in predecessors)]),
              'recovery identity in original history')
    current_raw = own[own_offset:]
    tail = global_raw[offset:]
    w.require(tail[:len(current_raw)] == current_raw, 'raw current preparation mirror equality')
    current = _recovery_rows(current_raw)
    current_mirror, health = [], []
    for row in _recovery_rows(tail):
        pair = (row.get('resource_id'), row.get('kind'))
        if pair == (identity, 'readiness_preparation'):
            w.require(not health, 'recovery preparation before health')
            current_mirror.append(row)
        elif pair == (HEALTH_ID, HEALTH_KIND):
            health.append(row)
        else:
            raise ValueError('foreign resource identity outside retained recovery partition')
    exact(current, current_mirror, 'complete current preparation mirror')
    exact(parsed['readiness-preparation-ledger.jsonl'], retained_all + current, 'complete own partition')
    for name, data in captures.items():
        w.require((root / name).read_bytes() == data, 'recovery journal changed during capture')
    return parsed, _recovery_rows(tail), current


def _recovery_partition(plan, spec, policy, baseline, resources):
    """Partition authenticated bytes without changing any budget ledger input."""
    contract = _recovery_contract(spec)
    if contract is None:
        return resources[len(baseline[JOURNALS[1]]):], None
    exact(baseline, terminal_parent_prefix(), 'recovery original terminal baseline')
    exact(policy['resource_id'], contract['successor']['resource_id'], 'recovery policy successor')
    root = owner_root(plan) / 'data'
    parsed, tail, current = _recovery_capture(contract, root)
    exact(resources, parsed[JOURNALS[1]], 'complete resource capture equality')
    for name in JOURNALS:
        exact(parsed[name][:len(baseline[name])], baseline[name], 'recovery baseline capture')
    return tail, (parsed['readiness-preparation-ledger.jsonl'], current)


def preparation_health_suffix(plan, baseline, resources):
    """One strict partition for admission and terminal readiness; never rebases costs.

    Only health rows leave this gate. Callers still charge the original complete
    resources to global snapshots. Failed/pending preparation is a consumed
    identity and a veto, never an implicit recovery or readiness certificate.
    """
    from scripts import qd_ed_n36_readiness_prepare as preparation
    spec = specification()
    policy = preparation.policy(spec)
    identity = policy['resource_id']
    old = baseline[JOURNALS[1]]
    exact(resources[:len(old)], old, 'R1 readiness terminal parent prefix')
    historical = [*baseline[JOURNALS[0]], *old]
    w.require(identity not in (HEALTH_ID, EPISODE_KEY)
              and not any(identity in (x.get('resource_id'), x.get('attempt_id'), x.get('episode_key'))
                          for x in historical), 'preparation identity collision with retained history')
    suffix, captured_own = _recovery_partition(plan, spec, policy, baseline, resources)
    prep, health = [], []
    for event in suffix:
        pair = (event.get('resource_id'), event.get('kind'))
        if pair == (identity, 'readiness_preparation'):
            w.require(not health, 'preparation must precede health reservation')
            prep.append(event)
        elif pair == (HEALTH_ID, HEALTH_KIND):
            health.append(event)
        else:
            raise ValueError('foreign resource identity/kind in strict suffix')
    own = preparation.journal_rows(owner_root(plan))
    if captured_own is not None:
        # Keep the existing whole-own lifecycle/budget validator active, then
        # compare its read to the authenticated capture before partitioning.
        exact(own, captured_own[0], 'complete preparation journal capture equality')
        own = captured_own[1]
    exact(own, prep, 'exact preparation journal/mirror suffix equality')
    if not prep:
        w.require(not health, 'health requires accepted preparation history')
        return resource_events(plan, health)
    kinds = [event.get('event') for event in prep]
    w.require(kinds in (['reserved', 'aborted'], ['reserved', 'dispatched', 'aborted'],
                         ['reserved', 'dispatched', 'completed']),
              'unsettled/unknown/replayed preparation lifecycle')
    source_ref = prep[0]['source_record']
    exact(read(source_ref), plan['source'], 'preparation current source')
    w.require(source_ref['path'] == spec['runtime_binding']['source_record_path'], 'preparation source path')
    # Historical release validity is evidence only. Successful readiness below
    # rechecks present freshness through derive; this call never grants dispatch.
    release = preparation.validate_release(prep[0]['release'], spec, plan['source'], source_ref,
                                           now=prep[0]['time_unix'])
    common = {key: release[key] for key in
              ('source_record', 'baseline', 'resource_id', 'source_cwd', 'interpreter')}
    common['release'] = prep[0]['release']
    parent = preparation.owned_identity(prep[0]['parent'])
    last = preparation.timestamp(release['issued_at'])
    for event in prep:
        terminal = event['event'] in ('completed', 'aborted')
        preparation.closed(event, (*common, 'event', 'time_unix', 'reserved_gpu_seconds',
            'gpu_process_wall_seconds', 'provider_calls', 'exclusive', 'telemetry_complete',
            'gpu', 'provider', 'kind', 'envelope', 'process', 'parent',
            *(['error'] if terminal else [])), 'strict preparation event')
        exact({key: event[key] for key in common}, common, 'immutable preparation release/source/baseline')
        exact(event['parent'], parent, 'immutable preparation parent')
        exact(event['reserved_gpu_seconds'], release['gpu_seconds'], 'preparation finite reservation')
        when = preparation.number(event['time_unix'], 'preparation event time')
        w.require(last < when <= time.time(), 'ordered preparation timestamps')
        if not terminal or event['event'] == 'completed':
            w.require(when < preparation.timestamp(release['expires_at']), 'preparation release event expiry')
        last = when
        charge = preparation.number(event['gpu_process_wall_seconds'], 'full actual preparation charge')
        w.require(type(event['provider_calls']) is int and 0 <= event['provider_calls'] <= 1,
                  'preparation one provider call')
        if not terminal:
            exact([charge, event['provider_calls'], event['gpu'], event['provider'], event['envelope'], event['process']],
                  [0, 0, None, None, None, None], 'preparation preterminal evidence')
            w.require(event['exclusive'] is True and event['telemetry_complete'] is True,
                      'preparation admission telemetry')
    terminal = prep[-1]
    if kinds[-1] == 'aborted':
        # Full finite overrun remains in the generic global snapshot. There is
        # intentionally no cap/truncation, identity reset, or retry branch here.
        if 'dispatched' in kinds:
            w.require(terminal['gpu_process_wall_seconds'] >= terminal['time_unix'] - prep[1]['time_unix'],
                      'failed preparation full elapsed charge')
        else:
            exact(terminal['gpu_process_wall_seconds'], 0, 'no-dispatch preparation charge')
        raise ValueError('failed preparation requires separate bounded root reconciliation; no readiness')
    runtime = read(plan['runtime'])
    proof_ref = runtime['preparation']['readiness_proof']
    proof = preparation.pinned(proof_ref, policy['proof_path'])
    exact(read(proof['accounting']), prep, 'accepted proof exact preparation accounting')
    exact(proof['release'], common['release'], 'accepted proof release')
    expected = preparation.derive(spec, plan['source'], source_ref, proof_ref)
    exact(runtime, expected, 'accepted preparation exact runtime')
    preparation.accepted(spec, proof_ref, plan['runtime'])
    if health:
        w.require(terminal['time_unix'] < preparation.number(health[0]['time_unix'], 'health reservation time'),
                  'preparation must finish before health reservation')
    return resource_events(plan, health)


def live_journals(plan, authority, events, resources, reservations):
    baseline = validate_authority(plan, authority)
    return _journal_suffixes(plan, baseline, events, resources, reservations)


def _journal_suffixes(plan, baseline, events, resources, reservations):
    # Pure comparison after live authority/prefix validation; no admission token.
    exact(baseline, terminal_parent_prefix(), 'R1 exact terminal baseline required')
    suffix = {}
    for name, current in zip(JOURNALS, (events, resources, reservations)):
        old = baseline[name]
        exact(current[:len(old)], old, 'engineering retained prefix snapshot')
        suffix[name] = current[len(old):]
    w.require(not suffix[JOURNALS[2]], 'engineering foreign reservation suffix')
    local = episode_events(plan, suffix[JOURNALS[0]])
    health = preparation_health_suffix(plan, baseline, resources)
    if local:
        w.require(health and health[-1]['event'] == 'completed'
                  and health[-1]['time_unix'] <= local[0]['time_unix'],
                  'engineering health must finish before sole episode reservation')
        release = read(local[0]['release'])
        w.require(release['schema'] == 'n36-engineering-episode-release-v1'
                  and read(release['plan']) == plan
                  and local[0]['plan_sha256'] == release['plan']['sha256'],
                  'engineering episode journal release/plan binding')
        issued = dt.datetime.fromisoformat(release['issued_at'].replace('Z', '+00:00'))
        times = [c.finite(event['time_unix'], 'engineering episode event time') for event in local]
        end = dt.datetime.fromisoformat(c.DEADLINE.replace('Z', '+00:00'))
        w.require(issued.tzinfo is not None and health[-1]['time_unix'] <= issued.timestamp()
                  <= times[0] and times == sorted(times)
                  and times[-1] <= min(end.timestamp(), dt.datetime.now(dt.timezone.utc).timestamp()),
                  'engineering episode prospective lifecycle timestamps')
    return local, health


def reconcile(plan, events, verify_terminal, *, live_handles=()):
    """A reservation exhausts the scope forever, independently of pause flags."""
    require_row(plan['episodes'][0])
    w.require(plan['episodes'] == [row()], 'engineering single row reconciliation')
    baseline = terminal_parent_prefix()
    old = baseline[JOURNALS[0]]
    exact(events[:len(old)], old, 'R1 exact terminal parent prefix required')
    local = events[len(old):]
    episode_events(plan, local)
    result = {'purpose': PURPOSE, 'scope_exhausted': bool(local), 'continuation_authorized': False,
              'scientific_eligible': False, 'next_row': None, 'outcomes': []}
    if live_handles or (local and local[-1]['event'] not in r.TERMINAL):
        return {**result, 'status': 'LIVE_OR_UNSETTLED'}
    if not local:
        return {**result, 'status': 'READY_FOR_ROOT_RELEASE', 'next_row': row()}
    final = local[-1]
    if final['event'] != 'valid':
        return {**result, 'status': 'INVALID_STOP', 'terminal': final}
    try:
        w.require(final.get('outcome_valid') is True and final.get('required_cost_telemetry_complete') is True
                  and type(final.get('success')) is bool, 'engineering valid terminal gates')
        verify_terminal(row(), final)
    except (ValueError, KeyError, IndexError, TypeError, OSError, RuntimeError, ArithmeticError) as exc:
        return {**result, 'status': 'INVALID_STOP', 'terminal': final, 'reason': str(exc)}
    return {**result, 'status': 'PAUSED_FOR_ROOT_G3', 'terminal': final}



def launch_guard(plan, authority, *, need=1840, now=None):
    validate_plan_shape(plan, released=True)
    owner_root(plan)
    c.validate_stop_binding(plan)
    now = now or dt.datetime.now(dt.timezone.utc)
    w.require(dt.datetime.fromisoformat(authority['starts_at'].replace('Z', '+00:00')) <= now,
              'engineering authority has not started')
    stop.check(now=now, ends_at=authority['weekly_window']['ends_at'], need=need)


def validate_owner_route(state):
    """Preserve historical spelling; neither resolution nor state grants a route."""
    w.require(state.get('canonical_worktree') == str(OWNER),
              'engineering owning state canonical worktree differs')
    lexical = state.get('worktree')
    w.require(lexical in (str(OWNER), HISTORICAL_OWNER),
              'engineering owning state lexical worktree differs')
    if lexical == HISTORICAL_OWNER:
        mapping = read(OWNER_ROUTE_MAPPING)
        w.require(mapping.get('schema') == 'n36r3-owner-alias-evidence-v1'
                  and mapping.get('lexical_worktree') == HISTORICAL_OWNER
                  and mapping.get('canonical_worktree') == str(OWNER)
                  and mapping.get('resolved_worktree') == str(OWNER)
                  and mapping.get('samefile') is True,
                  'engineering authorized owner mapping differs')
        alias = Path(lexical)
        try:
            matches = (alias.resolve(strict=True) == OWNER
                       and alias.is_dir() and alias.samefile(OWNER))
        except (OSError, RuntimeError):
            matches = False
        w.require(matches, 'engineering owning state alias identity differs')


def validate_state(plan, authority, state):
    validate_owner_route(state)
    w.require(state.get('n36_engineering_budget_authority') == plan['authority'],
              'engineering state adoption missing')
    validate_private_budget(authority, state)


def validate_private_budget(authority, state):
    """Shared unchanged private caps/isolation checks, without adoption semantics."""
    caps, budget = authority['caps'], state['budget']
    full.validate_caps(caps)
    w.require(r.authorized_gpu(state) == 7 and budget['max_episode_attempts'] == caps['attempts']
              and budget['max_gpu_hours'] == caps['gpu_hours'] and budget['reserved'] == caps['buckets']
              and budget['gpu_hour_reservations'] == caps['protected_gpu_hours']
              and budget['amendment'] == authority['amendment'], 'engineering owning budget differs')
    isolation = state.get('resource_isolation', {})
    w.require(isolation.get('status') == 'ACTIVE' and isolation.get('validation_status') == 'PASS'
              and isolation.get('private_budget') is True
              and not state.get('external_resource_hold', {}).get('do_not_auto_resume', False),
              'engineering private resource admission')


def headroom(snap, local, *, health, margin, protected):
    """Unchanged global gates AND one-use diagnostic bounds; no global mutation."""
    need = 60 if health else 1840
    w.require(Decimal(str(margin)) == Decimal('0.23357169027962'), 'engineering retained margin required')
    result = accounting.headroom(snap, local, retained_margin_hours=margin,
                                 protected_hours=protected, healthcheck=health, need=need)
    w.require(accounting.seconds(local['gpu_hours_consumed']) + need <= 1900,
              'engineering 1900-second GPU scope cap')
    w.require(accounting.seconds(local['gpu_healthcheck_hours']) + (60 if health else 0) <= 60,
              'engineering 60-second health cap')
    w.require(local['reserved_attempts'] == 0, 'engineering attempt slot consumed')
    # Before health, reserve room for the full episode too; root overhead is
    # wall-only and is never counted toward available GPU capacity.
    if health:
        charge = accounting.seconds(snap['gpu_hours_consumed']) + accounting.seconds(margin)
        reserved = accounting.seconds(protected)
        w.require(min(accounting.ABSOLUTE_HOURS, accounting.WEEKLY_HOURS) * 3600 - charge - reserved >= 1900,
                  'engineering full health plus episode headroom')
    return result


def admission(plan, authority, state, events, resources, reservations, selected, *, now, gpu_idle, release_refs=None):
    require_row(selected)
    w.require(release_refs is not None and gpu_idle is True, 'engineering detached admission and idle device')
    verified, _, approved = validate_release(*release_refs)
    exact(verified, plan, 'engineering admission plan changed')
    exact(approved, authority, 'engineering admission authority changed')
    local, health = live_journals(plan, authority, events, resources, reservations)
    w.require(not local and health and health[-1]['event'] == 'completed', 'engineering one-use/health readiness')
    validate_readiness(release_refs[0], read(release_refs[1]), resources=resources)
    validate_state(plan, authority, state)
    w.require(all(group[-1]['event'] in r.TERMINAL for group in r.event_groups(events).values()),
              'engineering unsettled global attempts')
    snap = r.budget_snapshot(events, resources)
    for cap in (224., float(accounting.WEEKLY_HOURS)):
        effective_state = {**state, 'budget': {**state['budget'], 'max_gpu_hours': cap}}
        w.require(r.check_budget_limits(effective_state, snap, selected, reservations,
                  bucket_caps=c.CAPS['buckets'], amendment=authority['amendment']) == 1800,
                  'engineering full 1840-second global admission')
    protected = sum(max(0., hours - snap['gpu_hours_by_bucket'][key])
                    for key, hours in c.CAPS['protected_gpu_hours'].items())
    reservation = headroom(snap, r.budget_snapshot(local, health), health=False,
        margin=accounting.retained_margin(OWNER, authority['margin_reference']), protected=protected)
    launch_guard(plan, authority, now=now)
    return {**snap, 'n36_reservation': reservation}


def child_environment(plan, runtime):
    owner_root(plan)
    env = r.child_environment(runtime)
    env['PYTHONPATH'] = ':'.join(str(SOURCE / p) for p in
                               ('', 'third_party/lerobot/src', 'third_party/rdt', 'third_party/libero_pro'))
    env['PYTHONNOUSERSITE'] = '1'
    env['QD_ED_N36_R1_SPECIFICATION'] = json.dumps(reference(SPECIFICATION), sort_keys=True)
    return env


def reserve_health(plan_ref, release_ref, resource_id, *, timeout_seconds):
    return reserve_health_handoff(plan_ref, release_ref, resource_id,
                                  timeout_seconds=timeout_seconds)[0]


def health_handoff_binding(plan, runtime, authority, state):
    """Local comparison digest, never a dispatch or reusable admission token."""
    return w.canonical_sha([plan, runtime, authority, state])


def validate_health_handoff(root, plan_ref, release_ref, record, binding):
    """Caller holds runner lock; recheck the spent admission under state lock.

    Failure leaves the original reservation unsettled. No output, second
    reservation, device observation or child work belongs in this check.
    """
    from scripts import qd_ed_n36_runner as runner
    with r.locked(root / 'data/qd-ed-state.lock'):
        plan, runtime, authority = validate_health_release(plan_ref, release_ref)
        w.require(owner_root(plan) == root, 'engineering health owner changed')
        state, events, resources, reservations = runner.snapshot(root, authority)
        local, health = live_journals(plan, authority, events, resources, reservations)
        validate_state(plan, authority, state)
        w.require(not local and len(health) == 1 and record['event'] == 'reserved',
                  'engineering health handoff requires sole original reservation')
        exact(health, [record], 'engineering health handoff reservation changed')
        w.require(state['run_name'] == plan['run_name'] and state['artifacts'] == runtime['artifact_root'],
                  'engineering owning run identity')
        w.require(health_handoff_binding(plan, runtime, authority, state) == binding,
                  'engineering health handoff bindings/state changed')
        w.require(all(group[-1]['event'] in r.TERMINAL for group in r.event_groups(events).values()),
                  'engineering health global unsettled attempt')
        r.runtime_gpu(runtime, state)
        return plan, runtime, authority


def reserve_health_handoff(plan_ref, release_ref, resource_id, *, timeout_seconds):
    """Consume the sole health slot durably under both existing runner locks."""
    import os
    from scripts import qd_ed_n36_runner as runner
    w.require(resource_id == HEALTH_ID and type(timeout_seconds) is int and timeout_seconds == 20,
              'engineering sole 20-second health probe')
    runner.source_execution.active()
    plan, runtime, authority = validate_health_release(plan_ref, release_ref)
    runner.source_execution.attest(SOURCE, plan['source'], read(plan['runtime_closure']),
        binding=runner.worker.runtime_receipt_binding(release_ref, plan, w.process_identity(), 'runtime_before'))
    root = owner_root(plan)
    with r.locked(root / 'data/qd-ed-runner.lock', nonblocking=True):
        with r.locked(root / 'data/qd-ed-state.lock'):
            plan, runtime, authority = validate_health_release(plan_ref, release_ref)
            state, events, resources, reservations = runner.snapshot(root, authority)
            local, health = live_journals(plan, authority, events, resources, reservations)
            validate_state(plan, authority, state)
            w.require(not local and not health, 'engineering health/episode identity consumed forever')
            w.require(state['run_name'] == plan['run_name'] and state['artifacts'] == runtime['artifact_root'],
                      'engineering owning run identity')
            w.require(all(group[-1]['event'] in r.TERMINAL for group in r.event_groups(events).values()),
                      'engineering health global unsettled attempt')
            output = Path(plan['artifact_root'])
            w.require(not output.is_symlink() and (not output.exists() or (output.is_dir() and not any(output.iterdir()))),
                      'engineering new empty output root required')
            w.require(not runner.existing_handles(plan, events), 'engineering orphan output')
            snap = r.budget_snapshot(events, resources)
            for cap in (224., float(accounting.WEEKLY_HOURS)):
                effective_state = {**state, 'budget': {**state['budget'], 'max_gpu_hours': cap}}
                w.require(r.check_budget_limits(effective_state, snap, row(), reservations,
                    bucket_caps=c.CAPS['buckets'], amendment=authority['amendment']) == 1800,
                    'engineering full prospective episode headroom')
            protected = sum(max(0., hours - snap['gpu_hours_by_bucket'][key])
                            for key, hours in c.CAPS['protected_gpu_hours'].items())
            reservation = headroom(snap, r.budget_snapshot(local, health), health=True,
                margin=accounting.retained_margin(root, authority['margin_reference']), protected=protected)
            launch_guard(plan, authority, need=2100)
            device = runner.device_check()
            launch_guard(plan, authority, need=2100)
            record = {**operational_binding(plan), 'resource_id': resource_id, 'event': 'reserved',
                      'kind': HEALTH_KIND, 'plan': plan_ref, 'release': release_ref,
                      'source_commit': plan['source']['commit'], 'runtime': plan['runtime'],
                      'physical_gpu': 7, 'gpu_uuid': c.GPU_UUID, 'timeout_seconds': 20,
                      'cleanup_seconds': 40, 'reserved_gpu_seconds': 60,
                      'accounting_admission': reservation, 'admission': device, 'time_unix': time.time()}
            r.budget_snapshot(events, [*resources, record])
            with (root / 'data/gpu-healthcheck-ledger.jsonl').open('a') as stream:
                stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + '\n')
                stream.flush(); os.fsync(stream.fileno())
            r.sync_state_from_journal(root, events)
            # Bind the post-sync state, including accounting updates made by
            # this reservation, before releasing either lock.
            binding = health_handoff_binding(plan, runtime, authority,
                                            r.read_state(root / 'research-state.yaml'))
            return record, binding


def validate_readiness(plan_ref, release_record, *, resources=None):
    from scripts import qd_ed_gpu_probe as probe
    ready = release_record['readiness']
    w.require(isinstance(ready, dict) and set(ready) == {'health_release', 'terminal'}, 'engineering readiness fields')
    plan, runtime, authority = validate_health_release(plan_ref, ready['health_release'])
    terminal = read(ready['terminal'])
    output = Path(plan['artifact_root']) / 'healthchecks' / HEALTH_ID
    w.require(terminal['output_dir'] == str(output) and ready['terminal']['path'] == str(output / 'healthcheck-result.json')
              and terminal['plan'] == plan_ref and terminal['release'] == ready['health_release']
              and terminal['source_commit'] == plan['source']['commit'] and terminal['runtime'] == plan['runtime']
              and terminal['event'] == 'completed' and terminal.get('provider_verified') is True
              and terminal['source_script_sha256'] == w.sha(SOURCE / 'scripts/qd_ed_gpu_probe.py'),
              'engineering terminal readiness binding')
    # Validate terminal fields using the same strict lifecycle validator below;
    # the real durable sequence, never a synthetic prefix, is mandatory here.
    if resources is None:
        resources = r.read_events(OWNER / 'data/gpu-healthcheck-ledger.jsonl')
    baseline = terminal_parent_prefix()
    group = preparation_health_suffix(plan, baseline, resources)
    w.require([event['event'] for event in group] == ['reserved', 'dispatched', 'completed']
              and group[-1] == terminal, 'engineering health not durably settled')
    evidence = r.read_json(output / 'probe-evidence.json')
    observed = c.finite(evidence['time_unix'], 'engineering health observation time')
    completed = c.finite(terminal['time_unix'], 'engineering health completion time')
    starts = dt.datetime.fromisoformat(authority['starts_at'].replace('Z', '+00:00')).timestamp()
    end = dt.datetime.fromisoformat(c.DEADLINE.replace('Z', '+00:00')).timestamp()
    dispatched = c.finite(group[1]['time_unix'], 'engineering health dispatch time')
    reserved = c.finite(group[0]['time_unix'], 'engineering health reservation time')
    issued = dt.datetime.fromisoformat(read(ready['health_release'])['issued_at'].replace('Z', '+00:00')).timestamp()
    w.require(starts <= issued <= reserved <= dispatched <= observed <= completed <= min(end, dt.datetime.now(dt.timezone.utc).timestamp()),
              'engineering fresh health authority timestamps')
    w.require(evidence['resource_id'] == HEALTH_ID and w.sha(output / 'probe-frame.png') == evidence['frame_png_sha256']
              and all(terminal.get(key) == value for key, value in evidence.items() if key != 'time_unix'),
              'engineering health evidence binding')
    probe.validate_probe_evidence(evidence, runtime['gpu_mapping'])
    return terminal


def execute_one(plan_ref, release_ref):
    from scripts.qd_ed_n36_runner import execute_one as run_reserved_episode
    return run_reserved_episode(plan_ref, release_ref, _engineering=True)



def main():
    """Explicit one-shot engineering entry; no loop, retry or adoption command."""
    import argparse
    import sys
    w.require('_n36_source_bootstrap' in sys.modules, 'engineering source-only bootstrap required')
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('plan', 'plan-sha256', 'release', 'release-sha256'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    result = execute_one({'path': args.plan, 'sha256': args.plan_sha256},
                         {'path': args.release, 'sha256': args.release_sha256})
    print(result['status'])
    return 0 if result['status'] == 'PAUSED_FOR_ROOT_G3' else 1


if __name__ == '__main__':
    raise SystemExit(main())
