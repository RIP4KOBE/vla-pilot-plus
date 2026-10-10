"""Prospective, externally anchored N36 release validation. Creates no authority.

DAG: inputs -> plan -> review -> detached release -> context/receipt. A plan
never contains its review/release hash. The caller supplies the release digest.
"""
from pathlib import Path
import datetime as dt
from scripts import qd_ed_final_runner as r, qd_ed_n23_worker as w
from scripts import qd_ed_n36_contract as c, qd_ed_n36_bridge as b

COORDINATOR_END = '2026-10-11T11:13:13Z'
N36R3_OWNER_ALIAS = '/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z'


def validate_plan(plan):
    if c.cohort(plan) in c.SEPARATE_HEALTH_COHORTS:
        w.require(all(plan.get(k) is not None for k in ('authority', 'b5_review', 'resource_routing')),
                  'N36R3 draft only; separate root bindings required')
        c.validate_successor_protocol(plan)
    w.require(plan['schema'] == 'n36-released-plan-v1' and plan['frozen'] is True
              and plan['release_enabled'] is True and plan['episodes'] == c.plan_rows(plan)
              and plan['limits'] == c.LIMITS and plan['worker_contract'] == c.WORKER_CONTRACT
              and plan['deadline'] == c.DEADLINE and plan['stop_path'] == c.stop_path(plan['worktree'])
              and plan['phase_authorization'] == {'dev': True, 'validation': False, 'formal': False}
              and not any(k in plan for k in ('root_review', 'execution_release'))
              and plan['attempt_identity'] == 'episode_key', 'released plan contract')
    c.validate_stop_binding(plan)
    c.operational_binding(plan)
    if c.cohort(plan) == c.DRAFT_RECOVERY_COHORT:
        from scripts.qd_ed_n36r2_admission import validate_protocol
        validate_protocol(plan)
    w.require(set(plan['expected_manifests']) == {x['episode_key'] for x in plan['episodes']}, 'all40 manifests')


def validate_release(plan_ref, release_ref):
    """Validate caller-anchored detached authority; never derive trusted hashes."""
    return verify_prospective_release(plan_ref, release_ref)


def verify_prospective_release(plan_ref, release_ref):
    """Full release closure; dispatch additionally requires locked admission."""
    plan, runtime, authority, _ = _verify_release_transaction(plan_ref, release_ref)
    return plan, runtime, authority


def validate_health_release(plan_ref, release_ref):
    return _verify_release_transaction(plan_ref, release_ref, health=True)[:3]


def _verify_release_transaction(plan_ref, release_ref, *, health=False):
    # No reusable token/cache escapes: each caller starts a new full transaction.
    with b.closure.verification_phase('release'):
        return _verify_release_contents(plan_ref, release_ref, health=health)


def _verify_release_contents(plan_ref, release_ref, *, health=False):
    plan = w.read_ref(plan_ref)
    validate_plan(plan)
    n36r3 = c.cohort(plan) in c.SEPARATE_HEALTH_COHORTS
    w.require(not health or n36r3, 'separate health authority is N36R3 only')
    if n36r3:
        from scripts import qd_ed_n36r3_admission as n3
        n3.independent_review(plan)
    if c.cohort(plan) == c.DRAFT_RECOVERY_COHORT:
        from scripts.qd_ed_n36r2_admission import independent_review
        independent_review(plan)
    release = w.read_ref(release_ref)
    expected = {'schema': 'n36-execution-release-v1', 'approved': True, 'plan': plan_ref,
                'native_build':plan['native_build'], 'authority': plan['authority'], 'protocol': plan['protocol'], 'protocol_review':plan['protocol_review'],
                'source': plan['source'], 'scientific_source': plan['scientific_source'],
                'runtime_closure': plan['runtime_closure'], 'controller_semantics': plan['controller_semantics'],
                'runtime': plan['runtime'], 'limits': c.LIMITS,
                'phase_authorization': plan['phase_authorization'], **c.operational_binding(plan)}
    if health:
        expected['schema'] = n3.identity_contract(plan)['prefix'] + '-health-release-v1'
        expected['healthchecks'] = n3.identity_contract(plan)['health']
    elif n36r3:
        expected['readiness'] = release['readiness']
    w.require(set(release) == set(expected) | {'root_review'} and all(release[k] == v for k, v in expected.items()), 'external release differs')
    review = w.read_ref(release['root_review'])
    w.require(review == {**expected, 'schema': (n3.identity_contract(plan)['prefix'] + '-root-health-review-v1' if health else 'n36-root-production-review-v1'), 'decision': 'APPROVED'}, 'root review differs')
    if n36r3:
        protocol = c.validate_successor_protocol(plan)
    elif c.cohort(plan) == c.RECOVERY_COHORT:
        from scripts.qd_ed_n36_recovery import validate_protocol
        protocol = validate_protocol(plan)
    elif c.cohort(plan) == c.DRAFT_RECOVERY_COHORT:
        from scripts.qd_ed_n36r2_admission import validate_protocol
        protocol = validate_protocol(plan)
    else:
        w.require(plan['protocol']['sha256']==c.PROTOCOL_SHA, 'frozen protocol v2 only')
        protocol=w.read_ref(plan['protocol'])
        w.require(protocol['episodes']==plan['episodes'] and protocol['accounting']['sha256']==c.ACCOUNTING_SHA,'reviewed protocol identities/accounting')
        w.require(plan['protocol_review']['sha256']==c.PROTOCOL_REVIEW_SHA,'exact root protocol review')
        protocol_review=w.read_ref(plan['protocol_review'])
        w.require(protocol_review['protocol']==plan['protocol'] and protocol_review['source']==protocol['base_source']
            and protocol_review['status']=='PASS_PROTOCOL_DESIGN_FOR_ISOLATED_CPU_IMPLEMENTATION_ONLY','root protocol review binding')
        w.read_ref(protocol['accounting'])
    authority = w.read_ref(plan['authority'])
    caps = authority['caps']
    w.require(authority['schema'] == 'n36-budget-authority-v1' and authority['approved'] is True
              and authority['cohort'] == c.cohort(plan) and authority['limits'] == c.LIMITS
              and authority['validation_authorized'] is False and authority['formal_authorized'] is False
              and authority['coordinator_ends_at'] == COORDINATOR_END
              and caps['protected_gpu_hours'] == {'validation': 32., 'formal': 12.}, 'finite root budget authority')
    w.require(authority.get('automatic_recoveries')==0 and authority.get('protocol')==plan['protocol']
        and authority.get('accounting')==protocol['accounting'], 'no recovery authority; exact protocol')
    if c.cohort(plan) == c.RECOVERY_COHORT:
        from scripts.qd_ed_n36_recovery import validate_authority
        validate_authority(plan, authority)
    if c.cohort(plan) == c.DRAFT_RECOVERY_COHORT:
        from scripts.qd_ed_n36r2_admission import validate_authority
        validate_authority(plan, authority)
    if n36r3:
        n3.validate_authority(plan, authority)
    validate_caps(caps)
    window_end = dt.datetime.fromisoformat(authority['weekly_window']['ends_at'].replace('Z', '+00:00'))
    w.require(window_end.tzinfo is not None and window_end <= dt.datetime.fromisoformat(c.DEADLINE.replace('Z', '+00:00')), 'weekly authorization deadline')
    # The approval basis is an external artifact, not a generated string/hash.
    w.read_ref(authority['approval_basis'])
    for name in ('origin_gpu_hours', 'increment_gpu_hours'):
        c.finite(authority['weekly_window'][name], name)
    w.require(authority['weekly_window']['increment_gpu_hours']==168.
        and authority['weekly_window']['origin_gpu_hours']==53.08404692669838, 'unchanged dual cumulative ceilings')
    evidence = verify_audit_closure(plan)
    runtime, manifests = evidence.runtime, evidence.manifests
    if n36r3 and not health:
        n3.validate_readiness(plan_ref, release)
    return plan, runtime, authority, manifests



class AuditEvidence:
    """Immutable serialized evidence, never an admission token or shared cache.

    Properties return independent JSON copies. Consumers must reverify closure
    for each release transaction, including each worker and health entry.
    """
    __slots__ = ('_bytes',)

    def __init__(self, runtime, manifests):
        import json
        object.__setattr__(self, '_bytes', json.dumps(
            [runtime, manifests], sort_keys=True, allow_nan=False).encode())

    def __setattr__(self, name, value):
        raise AttributeError('immutable audit evidence')

    def __delattr__(self, name):
        raise AttributeError('immutable audit evidence')

    @property
    def runtime(self):
        import json
        return json.loads(self._bytes)[0]

    @property
    def manifests(self):
        import json
        return json.loads(self._bytes)[1]


def verify_audit_closure(plan):
    """Full source/runtime/native/all-manifest closure; grants no dispatch.

    The caller separately verifies its authority family. The engineering audit
    view remains disabled and cannot be passed through validate_plan.
    """
    if plan.get('schema') == 'n36-engineering-audit-view-v1':
        from scripts.qd_ed_n36_engineering_api import for_plan
        validate_audit_view = for_plan(plan).validate_audit_view
        validate_audit_view(plan)
    w.require(plan['episodes'] == c.plan_rows(plan)
              and len(plan['episodes']) == 40
              and set(plan['expected_manifests']) == {row['episode_key'] for row in plan['episodes']},
              'all40 audit manifest coverage')
    w.require(Path(plan['worktree']).resolve() == b.ROOT.resolve(), 'actual imported checkout differs')
    with b.closure.verification_phase('source_closure'):
        b.verify_sources(plan)
    b.attest_loaded(plan['worktree'], plan['source'])
    with b.closure.verification_phase('runtime_closure'):
        runtime_closure = b.closure.verify_runtime(w.read_ref(plan['runtime_closure']), plan['runtime'])
    from scripts.qd_ed_n34_controller import verify_semantics
    verify_semantics(plan['controller_semantics'], plan['runtime'], runtime_closure)
    w.require(b.source_paths(plan['worktree']) <= {x['path'] for x in plan['source']['files']}, 'source inventory incomplete')
    from scripts.qd_ed_n36_build import manifest as validate_native_build
    validate_native_build(plan['native_build'])
    runtime = w.read_ref(plan['runtime'])
    w.require(runtime['schema'] == 'qd-ed-runtime-setup-v1'
              and Path(runtime['worktree']).resolve() == Path(plan['worktree']).resolve()
              and runtime['gpu_mapping']['uuid'] == c.GPU_UUID and r.runtime_gpu(runtime) == 7
              and runtime['gpu_mapping']['egl_device_index'] == 4
              and runtime['cuda_egl_verified'] is True and runtime['provider_ready'] is True
              and runtime['stage_recovered_error_condition'] == r.E2_STAGE_CONDITION
              and runtime['frozen_stage_provider']['backend'] == 'codex_cli', 'runtime checkout/device/provider')
    r.stage_overrides(runtime)
    r.owned(plan['artifact_root'], runtime['artifact_root'])
    w.require(Path(plan['artifact_root']).resolve() != Path(runtime['artifact_root']).resolve(), 'distinct N36 artifact directory required')
    # Use the same inventory/checkpoint/task/seed validators as the generic runner.
    state_view = {'artifacts': runtime['artifact_root']}
    # The runtime worktree alias was checked above to resolve to this checkout.
    # Preserve its frozen lexical paths while retaining both containment checks.
    with b.closure.verification_phase('runtime_files'):
        r.verify_files(runtime['files'], allowed_roots=(plan['worktree'], runtime['worktree'], runtime['artifact_root']))
    fingerprints = {str(Path(x['path']).resolve()) for x in runtime['files']}
    for task in runtime['tasks'].values():
        cache = Path(task['cache_dir'])
        actual = {str(p.resolve()) for p in cache.rglob('*') if p.is_file()}
        w.require(actual and actual <= fingerprints, 'task cache inventory incomplete')
    with b.closure.verification_phase('runtime_inputs'):
        r.validate_runtime_inputs(plan, runtime, b.profiles(plan['worktree']), Path(plan['worktree']), state_view)
    manifests = {}
    with b.closure.verification_phase('all_manifests'):
        for row in plan['episodes']:
            manifests[row['episode_key']] = b._verify_manifest_bound(
                plan['expected_manifests'][row['episode_key']], plan, runtime, row)
    return AuditEvidence(runtime, manifests)

def validate_caps(caps):
    """Accept only explicit root caps, never copy a predecessor's stale balances."""
    w.require(caps == c.CAPS, 'N36 unchanged root caps/protected reserves')
    buckets = caps['buckets']
    w.require(set(buckets) == {'baseline', 'development', 'validation', 'formal', 'recovery'}
              and all(type(v) is int and v >= 0 for v in buckets.values())
              and type(caps['attempts']) is int and caps['attempts'] == sum(buckets.values())
              and buckets['validation'] >= 180 and buckets['formal'] >= 40
              and caps['protected_gpu_hours'] == {'validation': 32., 'formal': 12.}, 'root caps/protected reserves')
    w.require(c.finite(caps['gpu_hours'], 'private GPU-hour cap') >= 44., 'protected GPU-hour cap')


def prefix(path, expected):
    import hashlib
    path = Path(path)
    w.require(not path.is_symlink() and path.is_file(), 'ledger prefix path')
    with path.open('rb') as stream:
        data = stream.read(expected['bytes'])
    w.require(len(data) == expected['bytes'] and hashlib.sha256(data).hexdigest() == expected['sha256'], 'historical ledger prefix changed')


def admission(plan, authority, state, events, resources, reservations, row, *, now, gpu_idle, release_refs=None):
    """Caller holds normal runner/state locks; all balances come from journals."""
    selected = c.cohort(plan)
    c.require_row(row, plan.get('worktree', c.ROOT), cohort=selected)
    if selected in c.SEPARATE_HEALTH_COHORTS:
        from scripts import qd_ed_n36r3_admission as n3
        n3_local, n3_health = n3.live_journals(plan, authority, events, resources, reservations)
        w.require(release_refs is not None, 'N36R3 detached release required')
        n3.validate_readiness(release_refs[0], w.read_ref(release_refs[1]), resources=resources)
    if selected == c.RECOVERY_COHORT:
        from scripts.qd_ed_n36_recovery import validate_authority, preserve_charge
        validate_authority(plan, authority)
        preserve_charge(events)
    if selected == c.DRAFT_RECOVERY_COHORT:
        from scripts.qd_ed_n36r2_admission import validate_authority, preserve_charges
        validate_authority(plan, authority)
        preserve_charges(events)
    w.require(authority.get('automatic_recoveries')==0, 'zero automatic recoveries')
    w.require(authority['weekly_window']['origin_gpu_hours']==53.08404692669838
        and authority['weekly_window']['increment_gpu_hours']==168., 'exact dual cumulative caps')
    from scripts import qd_ed_n36_supervise as supervisor
    rows = c.plan_rows(plan)
    w.require(plan.get('episodes', rows) == rows, 'admission exact cohort rows')
    # Accounting continuity only; runner separately reverifies native terminals.
    reconciliation_plan = plan if selected in c.SEPARATE_HEALTH_COHORTS else {
        **c.operational_binding(plan), 'episodes': rows, 'worktree': str(plan.get('worktree', c.ROOT))}
    reconciled = supervisor.reconcile(reconciliation_plan, events, lambda *args: None)
    w.require(reconciled['next_row'] == row, 'accounting requires next fresh contiguous row')
    validate_state(plan, authority, state)
    caps, budget = authority['caps'], state['budget']
    # Generic accounting deliberately preserves unknown durations as errors.
    snap = r.budget_snapshot(events, resources)
    groups = r.event_groups(events)
    w.require(all(g[-1]['event'] in r.TERMINAL for g in groups.values()), 'unsettled reservation or live process')
    timeout = r.check_budget_limits(state, snap, row, reservations, bucket_caps=caps['buckets'], amendment=budget['amendment'])
    w.require(timeout == 1800, 'full1840s admission')
    window = authority['weekly_window']
    from scripts.qd_ed_n31_contract import effective_hours
    effective = effective_hours(authority)
    effective_state = {**state, 'budget': {**budget, 'max_gpu_hours': effective}}
    w.require(r.check_budget_limits(effective_state, snap, row, reservations,
              bucket_caps=caps['buckets'], amendment=budget['amendment']) == 1800, 'weekly full1840s admission')
    protected = sum(max(0., h - snap['gpu_hours_by_bucket'][k]) for k, h in caps['protected_gpu_hours'].items())
    local = c.cohort_events(rows, events)
    local_ids = {e['resource_id'] for e in resources if e.get('cohort') == selected
                 or (selected == c.COHORT and e.get('kind') == 'n36_resource_preparation_v1')}
    local_resources = [e for e in resources if e['resource_id'] in local_ids]
    if selected == c.RECOVERY_COHORT:
        from scripts.qd_ed_n36_recovery import resource_events
        local_resources = resource_events(plan, resources)
    if selected in c.SEPARATE_HEALTH_COHORTS:
        # Retained health remains globally charged; only the verified suffix
        # belongs to this newly authorized finite cohort.
        local, local_resources = n3_local, n3_health
    if selected == c.DRAFT_RECOVERY_COHORT:
        from scripts.qd_ed_n36r2_admission import resource_events
        local_resources = resource_events(plan, resources)
    w.require(not any(e['event']=='aborted' for e in local_resources),
              'N36 healthcheck invalidity stop; no automatic replay')
    cohort = r.budget_snapshot(local, local_resources)
    w.require(all(cohort['by_bucket'][k] <= c.LIMITS[k] for k in ('baseline', 'development', 'recovery')),
              'N36 bucket ceilings')
    w.require(cohort['by_bucket'][row['budget_bucket']] < c.LIMITS[row['budget_bucket']], 'N36 bucket exhausted')
    from scripts import qd_ed_n36_accounting as accounting
    from scripts.qd_ed_n36r2_admission import owner_root
    accounting_root = owner_root(plan)
    margin_ref = (authority['accounting'] if selected == c.COHORT else
                  n3.margin_reference(plan) if selected in c.SEPARATE_HEALTH_COHORTS else
                  w.read_ref(authority['accounting'])['inherited_accounting'])
    margin = accounting.retained_margin(accounting_root, margin_ref)
    reservation=accounting.headroom(snap,cohort,retained_margin_hours=margin,protected_hours=protected)
    allowance = {'authority_starts_at': authority['starts_at'],
                 'authority_ends_at': min(authority['coordinator_ends_at'], window['ends_at']),
                 'private_budget': True, 'gpu_idle': gpu_idle, 'physical_gpu': 7, 'gpu_uuid': c.GPU_UUID,
                 'live_handles': [], 'unsettled_reservations': 0,
                 'global_seconds_remaining': (effective - snap['gpu_hours_consumed'] - margin) * 3600,
                 'private_seconds_remaining': (caps['gpu_hours'] - snap['gpu_hours_consumed'] - margin) * 3600,
                 'protected_seconds_remaining': protected * 3600,
                 'cohort_seconds_remaining': c.LIMITS['cohort_gpu_seconds'] - cohort['gpu_hours_consumed'] * 3600,
                 'bucket_attempts_remaining': {k: v - snap['by_bucket'][k] for k, v in caps['buckets'].items()},
                 'global_attempts_remaining': caps['attempts'] - snap['dispatched'],
                 'protected_attempts_remaining': sum(max(0, caps['buckets'][k] - snap['by_bucket'][k]) for k in ('validation', 'formal')),
                 'cohort_attempts_remaining': 40 - cohort['reserved_attempts']}
    w.require(cohort['gpu_healthcheck_hours']*3600 <= c.LIMITS['healthcheck_seconds'], 'bounded cumulative healthcheck allowance')
    c.validate_stop_binding(plan)
    if selected == c.DRAFT_RECOVERY_COHORT:
        allowance.update(n36r2_plan=plan, n36r2_authority=authority, n36r2_release_refs=release_refs)
    if selected in c.SEPARATE_HEALTH_COHORTS:
        key = c.IDENTITIES[selected][0]
        allowance.update({key + '_plan': plan, key + '_authority': authority,
                          key + '_release_refs': release_refs})
    c.pre_dispatch(row, allowance, now=now, stop_path=plan['stop_path'], cohort=selected)
    return {**snap, "n36_reservation":reservation}


def validate_state(plan, authority, state):
    """Shared owning state gate for independent health and episode transactions."""
    if c.cohort(plan) in c.SEPARATE_HEALTH_COHORTS:
        from scripts.qd_ed_n36r3_admission import owner_root
        owner = owner_root(plan)
        lexical = state.get('worktree')
        w.require(state.get('canonical_worktree') == str(owner), 'N36R3 owning state canonical worktree differs')
        w.require(lexical in (str(owner), N36R3_OWNER_ALIAS), 'N36R3 owning state worktree differs')
        if lexical == N36R3_OWNER_ALIAS:
            # Admit only the historical spelling, without rewriting state or routing.
            # Recheck live identity each time; cached alias evidence is not authority.
            alias = Path(lexical)
            try:
                matches = alias.resolve(strict=True) == owner and alias.is_dir() and alias.samefile(owner)
            except (OSError, RuntimeError):
                matches = False
            w.require(matches, 'N36R3 owning state alias identity differs')
    caps, budget = authority['caps'], state['budget']
    validate_caps(caps)
    w.require(state.get('n36_budget_authority') == plan['authority'] and r.authorized_gpu(state) == 7
              and budget['max_episode_attempts'] == caps['attempts'] and budget['max_gpu_hours'] == caps['gpu_hours']
              and budget['reserved'] == caps['buckets'] and budget['gpu_hour_reservations'] == caps['protected_gpu_hours']
              and budget['amendment'] == authority['amendment'], 'adopted state authority differs')
    isolation = state.get('resource_isolation', {})
    w.require(isolation.get('status') == 'ACTIVE' and isolation.get('validation_status') == 'PASS'
              and isolation.get('private_budget') is True
              and not state.get('external_resource_hold', {}).get('do_not_auto_resume', False), 'private resource admission')
