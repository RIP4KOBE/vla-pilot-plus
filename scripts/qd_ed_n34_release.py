"""Prospective, externally anchored N34 release validation. Creates no authority.

DAG: inputs -> plan -> review -> detached release -> context/receipt. A plan
never contains its review/release hash. The caller supplies the release digest.
"""
from pathlib import Path
import datetime as dt
from scripts import qd_ed_final_runner as r, qd_ed_n23_worker as w
from scripts import qd_ed_n34_contract as c, qd_ed_n34_bridge as b

COORDINATOR_END = '2026-10-11T11:13:13Z'


def validate_plan(plan):
    w.require(plan['schema'] == 'n34-released-plan-v1' and plan['frozen'] is True
              and plan['release_enabled'] is True and plan['episodes'] == c.expected_rows(plan['worktree'])
              and plan['limits'] == c.LIMITS and plan['worker_contract'] == c.WORKER_CONTRACT
              and plan['deadline'] == c.DEADLINE and plan['stop_path'] == c.stop_path(plan['worktree'])
              and plan['phase_authorization'] == {'dev': True, 'validation': False, 'formal': False}
              and not any(k in plan for k in ('root_review', 'execution_release'))
              and plan['attempt_identity'] == 'episode_key', 'released plan contract')
    w.require(set(plan['expected_manifests']) == {x['episode_key'] for x in plan['episodes']}, 'all30 manifests')


def validate_release(plan_ref, release_ref):
    """Validate caller-anchored detached authority; never derive trusted hashes."""
    return verify_prospective_release(plan_ref, release_ref)


def verify_prospective_release(plan_ref, release_ref):
    """Full release closure; dispatch additionally requires locked admission."""
    plan, runtime, authority, _ = _verify_release_transaction(plan_ref, release_ref)
    return plan, runtime, authority


def _verify_release_transaction(plan_ref, release_ref):
    # No reusable token/cache escapes: each caller starts a new full transaction.
    with b.closure.verification_phase('release'):
        return _verify_release_contents(plan_ref, release_ref)


def _verify_release_contents(plan_ref, release_ref):
    plan = w.read_ref(plan_ref)
    validate_plan(plan)
    release = w.read_ref(release_ref)
    expected = {'schema': 'n34-execution-release-v1', 'approved': True, 'plan': plan_ref,
                'authority': plan['authority'], 'protocol': plan['protocol'],
                'source': plan['source'], 'scientific_source': plan['scientific_source'],
                'runtime_closure': plan['runtime_closure'], 'controller_semantics': plan['controller_semantics'],
                'runtime': plan['runtime'], 'limits': c.LIMITS,
                'phase_authorization': plan['phase_authorization']}
    w.require(set(release) == set(expected) | {'root_review'} and all(release[k] == v for k, v in expected.items()), 'external release differs')
    review = w.read_ref(release['root_review'])
    w.require(review == {**expected, 'schema': 'n34-root-production-review-v1', 'decision': 'APPROVED'}, 'root review differs')
    protocol = w.read_ref(plan['protocol'])
    w.require(protocol == {'schema': 'n34-production-protocol-v1', 'cohort': c.COHORT,
              'episodes': plan['episodes'], 'limits': c.LIMITS, 'worker_contract': c.WORKER_CONTRACT,
              'attempt_identity': 'episode_key', 'deadline': c.DEADLINE,
              'promotion': {'all_valid_cells': 30, 'n34_min_successes': 5, 'at_least_both_controls': True, 'matched_controls_required': True},
              'futility': 'complete_valid_triples_only', 'validation_authorized': False, 'formal_authorized': False}, 'protocol differs')
    authority = w.read_ref(plan['authority'])
    caps = authority['caps']
    w.require(authority['schema'] == 'n34-budget-authority-v1' and authority['approved'] is True
              and authority['cohort'] == c.COHORT and authority['limits'] == c.LIMITS
              and authority['validation_authorized'] is False and authority['formal_authorized'] is False
              and authority['coordinator_ends_at'] == COORDINATOR_END
              and caps['protected_gpu_hours'] == {'validation': 32., 'formal': 12.}, 'finite root budget authority')
    w.require(authority.get('prospective_recovery') == c.REPLACEMENT, 'explicit root recovery authority')
    w.read_ref(c.REPLACEMENT['terminal_closure'])
    validate_caps(caps)
    window_end = dt.datetime.fromisoformat(authority['weekly_window']['ends_at'].replace('Z', '+00:00'))
    w.require(window_end.tzinfo is not None and window_end <= dt.datetime.fromisoformat(c.DEADLINE.replace('Z', '+00:00')), 'weekly authorization deadline')
    # The approval basis is an external artifact, not a generated string/hash.
    w.read_ref(authority['approval_basis'])
    for name in ('origin_gpu_hours', 'increment_gpu_hours'):
        c.finite(authority['weekly_window'][name], name)
    w.require(authority['weekly_window']['increment_gpu_hours'] <= 168., 'weekly ceiling')
    w.require(Path(plan['worktree']).resolve() == b.ROOT.resolve(), 'actual imported checkout differs')
    with b.closure.verification_phase('source_closure'):
        b.verify_sources(plan)
    b.attest_loaded(plan['worktree'], plan['source'])
    with b.closure.verification_phase('runtime_closure'):
        runtime_closure = b.closure.verify_runtime(w.read_ref(plan['runtime_closure']), plan['runtime'])
    from scripts.qd_ed_n34_controller import verify_semantics
    verify_semantics(plan['controller_semantics'], plan['runtime'], runtime_closure)
    w.require(b.source_paths(plan['worktree']) <= {x['path'] for x in plan['source']['files']}, 'source inventory incomplete')
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
    w.require(Path(plan['artifact_root']).resolve() != Path(runtime['artifact_root']).resolve(), 'distinct N34 artifact directory required')
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
    return plan, runtime, authority, manifests


def validate_caps(caps):
    """Accept only explicit root caps, never copy a predecessor's stale balances."""
    w.require(caps == c.CAPS, 'N34R11 unchanged root caps/protected reserves')
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


def admission(plan, authority, state, events, resources, reservations, row, *, now, gpu_idle):
    """Caller holds normal runner/state locks; all balances come from journals."""
    c.require_row(row)
    w.require(authority.get('prospective_recovery') == c.REPLACEMENT, 'explicit root recovery authority')
    c.require_replacement_history(events)
    from scripts import qd_ed_n34_supervise as supervisor
    rows = c.expected_rows()
    # Accounting continuity only; runner separately reverifies native terminals.
    reconciled = supervisor.reconcile({'episodes': rows, 'worktree': str(c.ROOT)}, events, lambda *args: None)
    w.require(reconciled['next_row'] == row, 'accounting requires next fresh contiguous row')
    caps, budget = authority['caps'], state['budget']
    validate_caps(caps)
    w.require(state.get('n34_budget_authority') == plan['authority'] and r.authorized_gpu(state) == 7
              and budget['max_episode_attempts'] == caps['attempts'] and budget['max_gpu_hours'] == caps['gpu_hours']
              and budget['reserved'] == caps['buckets'] and budget['gpu_hour_reservations'] == caps['protected_gpu_hours']
              and budget['amendment'] == authority['amendment'], 'adopted state authority differs')
    isolation = state.get('resource_isolation', {})
    w.require(isolation.get('status') == 'ACTIVE' and isolation.get('validation_status') == 'PASS'
              and isolation.get('private_budget') is True
              and not state.get('external_resource_hold', {}).get('do_not_auto_resume', False), 'private resource admission')
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
    local_ids = {e['resource_id'] for e in resources if e.get('cohort') == c.COHORT
                 or e.get('kind') == 'n34r11_resource_preparation_v1'}
    local_resources = [e for e in resources if e['resource_id'] in local_ids]
    cohort = r.budget_snapshot(local, local_resources)
    w.require(all(cohort['by_bucket'][k] <= c.LIMITS[k] for k in ('baseline', 'development', 'recovery')),
              'N34R11 bucket ceilings')
    w.require(cohort['by_bucket'][row['budget_bucket']] < c.LIMITS[row['budget_bucket']], 'N34R11 bucket exhausted')
    allowance = {'authority_starts_at': authority['starts_at'],
                 'authority_ends_at': min(authority['coordinator_ends_at'], window['ends_at']),
                 'private_budget': True, 'gpu_idle': gpu_idle, 'physical_gpu': 7, 'gpu_uuid': c.GPU_UUID,
                 'live_handles': [], 'unsettled_reservations': 0,
                 'global_seconds_remaining': (effective - snap['gpu_hours_consumed']) * 3600,
                 'private_seconds_remaining': (caps['gpu_hours'] - snap['gpu_hours_consumed']) * 3600,
                 'protected_seconds_remaining': protected * 3600,
                 'cohort_seconds_remaining': 18000 - cohort['gpu_hours_consumed'] * 3600,
                 'bucket_attempts_remaining': {k: v - snap['by_bucket'][k] for k, v in caps['buckets'].items()},
                 'global_attempts_remaining': caps['attempts'] - snap['dispatched'],
                 'protected_attempts_remaining': sum(max(0, caps['buckets'][k] - snap['by_bucket'][k]) for k in ('validation', 'formal')),
                 'cohort_attempts_remaining': 30 - cohort['dispatched']}
    c.pre_dispatch(row, allowance, now=now, stop_path=plan['stop_path'])
    return snap
