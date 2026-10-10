"""One-use N36 engineering diagnostic, separate from scientific cohort authority.

This module consumes external, hash-bound approvals. It never creates an
approval, adopts source/accounting, or supplies a continuation/retry entrypoint.
Disabled scope/accounting and the full audit view do not authorize execution.
Dispatch is also hard-disabled in this partial implementation: the complete
released engineering lifecycle still needs CPU integration verification. There
is no plan flag, approval field, environment variable or retry that lifts it.
"""
import datetime as dt
import json
from pathlib import Path
import subprocess
from decimal import Decimal

from scripts import qd_ed_n23_worker as w, qd_ed_final_runner as r
from scripts import qd_ed_n36_contract as c, qd_ed_n36_stop as stop
from scripts import qd_ed_n36_bridge as b, qd_ed_n36_release as full
from scripts import qd_ed_n36_accounting as accounting
from scripts.qd_ed_n36r2_admission import OWNER, SESSION

BASE = '813f25bc89a3920149739a2bf957b2e1b3db29c4'
SOURCE = SESSION / 'variants/n36_engineering_adapter_001482/implementation_worktree'
PREPARATION = OWNER.parent / 'autonomy_20261004/turns/001479/bounded-engineering-preparation'
SPECIFICATION = {'path': str(PREPARATION / 'engineering-adapter-spec-v1.json'),
                 'sha256': '9df1dbbbe985df1d02e88770356b59e47d346a9f546629e0d7262cb9e51ecd15'}
IDENTITY = 'N36_ENGINEERING_C0_TASK0_001479'
EPISODE_KEY = 'n36_engineering_t00_c0_001479'
HEALTH_ID = 'n36_healthcheck_engineering_t00_c0_001479'
HEALTH_KIND = 'n36_engineering_resource_preparation_v1'
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
    'scripts/qd_ed_n36_engineering.py', 'scripts/qd_ed_n36_release.py',
    'scripts/qd_ed_n36_bridge.py', 'scripts/qd_ed_n36_worker.py',
    'scripts/qd_ed_n36_runner.py', 'scripts/qd_ed_n36_healthcheck.py',
    'scripts/qd_ed_n36_report.py', 'tests/test_n36_engineering.py'})


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
    return read(SPECIFICATION)


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
          'snapshot': retained['retained_snapshot'], 'arithmetic': spec['accounting_proposal'],
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
    exact(snap, retained['retained_snapshot'], 'whole retained snapshot')
    w.require(snap['reserved_attempts'] == snap['dispatched'] == 506
              and snap['gpu_hours_consumed'] == 75.60616276674473
              and all(g[-1]['event'] in r.TERMINAL for g in r.event_groups(baseline[JOURNALS[0]]).values()),
              'retained charges/unsettled attempts')
    margin = accounting.retained_margin(OWNER, authority['margin_reference'])
    w.require(Decimal(str(margin)) == Decimal('0.23357169027962'), 'unchanged retained margin')
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
            validate_readiness(plan_ref, release)
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


def live_journals(plan, authority, events, resources, reservations):
    baseline = validate_authority(plan, authority)
    return _journal_suffixes(plan, baseline, events, resources, reservations)


def _journal_suffixes(plan, baseline, events, resources, reservations):
    # Pure comparison after live authority/prefix validation; no admission token.
    suffix = {}
    for name, current in zip(JOURNALS, (events, resources, reservations)):
        old = baseline[name]
        exact(current[:len(old)], old, 'engineering retained prefix snapshot')
        suffix[name] = current[len(old):]
    w.require(not suffix[JOURNALS[2]], 'engineering foreign reservation suffix')
    local = episode_events(plan, suffix[JOURNALS[0]])
    health = resource_events(plan, suffix[JOURNALS[1]])
    if local:
        w.require(health and health[-1]['event'] == 'completed'
                  and health[-1]['time_unix'] <= local[0]['time_unix'],
                  'engineering health must finish before sole episode reservation')
    return local, health


def reconcile(plan, events, verify_terminal, *, live_handles=()):
    """A reservation exhausts the scope forever, independently of pause flags."""
    require_row(plan['episodes'][0])
    w.require(plan['episodes'] == [row()], 'engineering single row reconciliation')
    local = [event for event in events if event.get('cohort') == IDENTITY
             or event.get('identity', {}).get('iteration') == IDENTITY
             or str(event.get('attempt_id', '')).startswith('n36_engineering_')
             or str(event.get('episode_key', '')).startswith('n36_engineering_')]
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



def require_dispatch_implementation():
    """A code-level veto, not an authority that root records can override.

    Remove only in a subsequent reviewed implementation after the remaining
    released-lifecycle and deep-closure CPU verification gaps are addressed.
    """
    raise RuntimeError('engineering dispatch disabled: released lifecycle and deep-closure verification incomplete')

def launch_guard(plan, authority, *, need=1840, now=None):
    require_dispatch_implementation()
    owner_root(plan)
    c.validate_stop_binding(plan)
    now = now or dt.datetime.now(dt.timezone.utc)
    w.require(dt.datetime.fromisoformat(authority['starts_at'].replace('Z', '+00:00')) <= now,
              'engineering authority has not started')
    stop.check(now=now, ends_at=authority['weekly_window']['ends_at'], need=need)


def validate_state(plan, authority, state):
    w.require(state.get('canonical_worktree') == str(OWNER) and state.get('worktree') == str(OWNER),
              'engineering exact owning state route')
    w.require(state.get('n36_engineering_budget_authority') == plan['authority'],
              'engineering state adoption missing')
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
    return env


def reserve_health(plan_ref, release_ref, resource_id, *, timeout_seconds):
    """Consume the sole health slot durably under both existing runner locks."""
    import os
    import time
    from scripts import qd_ed_n36_runner as runner
    require_dispatch_implementation()
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
            return record


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
    group = [event for event in resources if event.get('resource_id') == HEALTH_ID
             or event.get('cohort') == IDENTITY or event.get('kind') == HEALTH_KIND]
    resource_events(plan, group)
    w.require([event['event'] for event in group] == ['reserved', 'dispatched', 'completed']
              and group[-1] == terminal, 'engineering health not durably settled')
    evidence = r.read_json(output / 'probe-evidence.json')
    observed = c.finite(evidence['time_unix'], 'engineering health observation time')
    completed = c.finite(terminal['time_unix'], 'engineering health completion time')
    starts = dt.datetime.fromisoformat(authority['starts_at'].replace('Z', '+00:00')).timestamp()
    end = dt.datetime.fromisoformat(c.DEADLINE.replace('Z', '+00:00')).timestamp()
    w.require(starts <= group[0]['time_unix'] <= observed <= completed <= min(end, dt.datetime.now(dt.timezone.utc).timestamp()),
              'engineering fresh health authority timestamps')
    w.require(evidence['resource_id'] == HEALTH_ID and w.sha(output / 'probe-frame.png') == evidence['frame_png_sha256']
              and all(terminal.get(key) == value for key, value in evidence.items() if key != 'time_unix'),
              'engineering health evidence binding')
    probe.validate_probe_evidence(evidence, runtime['gpu_mapping'])
    return terminal


def execute_one(plan_ref, release_ref):
    require_dispatch_implementation()
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
