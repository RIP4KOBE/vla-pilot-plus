"""Separate continuation release boundary; disabled preparation grants no authority."""
from pathlib import Path

from scripts import qd_ed_n23_worker as w, qd_ed_final_runner as r
from scripts import qd_ed_n34_contract as c, qd_ed_n34_bridge as b
from scripts import qd_ed_n34_release as old, qd_ed_n34_continuation as cc

# Only operational routing in an existing file may change. All scientific,
# policy, generic/native audit, provider and runtime code remains byte-identical.
OPERATIONAL_EDITS = {'scripts/qd_ed_n34_worker.py'}


def allowed_change(path):
    return path in OPERATIONAL_EDITS or (path.startswith('scripts/qd_ed_n34_continuation')
        and path.endswith('.py')) or (path.startswith('tests/test_n34_continuation') and path.endswith('.py'))


def source_equivalence(root, original, source):
    """Exact Git and on-disk scientific equality; new HEAD never validates old receipts."""
    root = Path(root)
    w.require(original['source']['commit'] == cc.BASE, 'base source differs')
    commit = source['commit']
    w.require(w._source_git(root, 'rev-parse', 'HEAD').decode().strip() == commit, 'new source must be HEAD')
    changed = w._source_git(root, 'diff', '--name-only', '-z', cc.BASE, commit).split(b'\0')
    w.require(all(allowed_change(p.decode()) for p in changed if p), 'non-operational committed delta')
    # Exact scientific inventory already belongs to the hash-bound original plan.
    science = original['scientific_source']
    b.closure.verify_source(root, science, commit=b.SCIENTIFIC_COMMIT)
    b.closure.verify_source(root, source)
    before = {x['path']: x['sha256'] for x in original['source']['files']}
    after = {x['path']: x['sha256'] for x in source['files']}
    w.require(len(after) == len(source['files']) and set(before) <= set(after), 'new source inventory lost files')
    w.require(all(after[p] == digest or allowed_change(p) for p, digest in before.items()),
              'scientific/policy/audit source differs from base')
    w.require(all(after.get(x['path']) == x['sha256'] for x in science['files']), 'scientific equality differs')
    w.require(b.source_paths(root) <= set(after), 'new operational closure incomplete')
    return {'schema': 'n34-continuation-scientific-equality-v1', 'base_commit': cc.BASE,
            'operational_commit': commit, 'scientific_source': science,
            'unchanged_base_files_sha256': w.canonical_sha([
                x for x in original['source']['files'] if not allowed_change(x['path'])]),
            'changed_paths': sorted(p.decode() for p in changed if p)}


def validate_authority(authority, plan):
    old.validate_caps(authority['caps'])
    w.require(authority['schema'] == 'n34-continuation-budget-authority-v1'
              and authority['approved'] is True and authority['label'] == cc.LABEL
              and authority['design'] == plan['design'] and authority['limits'] == cc.LIMITS
              and authority['ledger_prefixes'] == plan['ledger_prefixes']
              and authority['coordinator_ends_at'] == c.DEADLINE
              and authority['validation_authorized'] is False and authority['formal_authorized'] is False,
              'separate root continuation budget authority')
    window = authority['weekly_window']
    for key in ('origin_gpu_hours', 'increment_gpu_hours'):
        c.finite(window[key], key)
    w.require(window['increment_gpu_hours'] <= 168., 'weekly cap')
    w.read_ref(authority['approval_basis'])


def _verify_release_transaction(plan_ref, release_ref):
    plan = w.read_ref(plan_ref)
    w.require(plan.get('schema') == 'n34-continuation-plan-v1' and plan.get('frozen') is True
              and plan.get('release_enabled') is True
              and plan.get('phase_authorization') == {'dev': True, 'validation': False, 'formal': False},
              'continuation disabled: separate detached root release required')
    design, original, terminal = cc.load_design(plan['design'])
    cc.validate_shape(plan, design, original)
    expected = {'schema': 'n34-continuation-execution-release-v1', 'approved': True,
                'plan': plan_ref, 'design': plan['design'], 'label': cc.LABEL,
                'source': plan['source'], 'scientific_source': plan['scientific_source'],
                'scientific_equality': plan['scientific_equality'], 'runtime': plan['runtime'],
                'runtime_closure': plan['runtime_closure'], 'controller_semantics': plan['controller_semantics'],
                'authority': plan['authority'], 'limits': cc.LIMITS,
                'phase_authorization': plan['phase_authorization'], 'automatic_promotion': False}
    release = w.read_ref(release_ref)
    w.require(set(release) == set(expected) | {'root_review'}
              and all(release[k] == v for k, v in expected.items()), 'continuation detached release differs')
    review = w.read_ref(release['root_review'])
    w.require(review == {**expected, 'schema': 'n34-continuation-root-review-v1', 'decision': 'APPROVED',
                        'scientific_interpretation': design['scientific_interpretation'],
                        'retained_equivalence_reviewed': True, 'validation_requires_new_root_scientific_review': True},
              'continuation explicit root review differs')
    authority = w.read_ref(plan['authority'])
    validate_authority(authority, plan)
    w.require(set(plan['ledger_prefixes']) == set(terminal['ledger_prefixes'])
              and plan['ledger_prefixes']['attempt-ledger.jsonl'] == design['ledger_prefix']
              and all(plan['ledger_prefixes'][k] == {a: v[a] for a in ('bytes', 'sha256')}
                      for k, v in terminal['ledger_prefixes'].items()), 'frozen ledger anchors differ')
    w.require(all(plan[k] == original[k] for k in ('run_name', 'runtime_inventory_sha256',
              'seed_plan_sha256', 'input_contract_label')), 'original input/seed inventory differs')
    root = Path(plan['worktree']).resolve()
    w.require(root == b.ROOT.resolve(), 'actual imported continuation checkout differs')
    w.require(plan['scientific_source'] == original['scientific_source'], 'new scientific source identity differs')
    equality = source_equivalence(root, original, plan['source'])
    w.require(w.read_ref(plan['scientific_equality']) == equality, 'scientific equality attestation differs')
    b.attest_loaded(root, plan['source'])
    runtime_closure = b.closure.verify_runtime(w.read_ref(plan['runtime_closure']), plan['runtime'])
    from scripts.qd_ed_n34_controller import verify_semantics
    verify_semantics(plan['controller_semantics'], plan['runtime'], runtime_closure)
    runtime = w.read_ref(plan['runtime'])
    w.require(runtime['schema'] == 'qd-ed-runtime-setup-v1'
              and Path(runtime['worktree']).resolve() == root
              and runtime['gpu_mapping']['uuid'] == c.GPU_UUID and r.runtime_gpu(runtime) == 7
              and runtime['gpu_mapping']['egl_device_index'] == 4
              and runtime['cuda_egl_verified'] is True and runtime['provider_ready'] is True
              and runtime['stage_recovered_error_condition'] == r.E2_STAGE_CONDITION
              and runtime['frozen_stage_provider']['backend'] == 'codex_cli', 'runtime/device/provider differs')
    r.stage_overrides(runtime)
    old_runtime = w.read_ref(original['runtime'])
    w.require(runtime['frozen_stage_provider'] == old_runtime['frozen_stage_provider']
              and runtime.get('stage_engineering_condition') == old_runtime.get('stage_engineering_condition'),
              'original Stage/provider condition changed')
    r.owned(plan['artifact_root'], runtime['artifact_root'])
    w.require(Path(plan['artifact_root']).resolve() not in
              (Path(runtime['artifact_root']).resolve(), Path(original['artifact_root']).resolve()),
              'new distinct artifact directory required')
    r.verify_files(runtime['files'], allowed_roots=(str(root), runtime['worktree'], runtime['artifact_root']))
    fingerprints = {str(Path(x['path']).resolve()) for x in runtime['files']}
    for task in runtime['tasks'].values():
        actual = {str(p.resolve()) for p in Path(task['cache_dir']).rglob('*') if p.is_file()}
        w.require(actual and actual <= fingerprints, 'task cache inventory incomplete')
    r.validate_runtime_inputs(plan, runtime, b.profiles(root), root, {'artifacts': runtime['artifact_root']})
    manifests = {row['episode_key']: b._verify_manifest_bound(
        plan['expected_manifests'][row['episode_key']], plan, runtime, row) for row in plan['episodes']}
    # No legacy release validator against new HEAD; keep each historical source
    # and manifest anchored to its original plan instead.
    for name, anchor in plan['ledger_prefixes'].items():
        raw = cc.read_prefix(root / 'data' / name, anchor)
        if name == 'gpu-healthcheck-ledger.jsonl':
            w.require(plan['resource_prefix_event_count'] == len(raw.splitlines()), 'resource prefix count differs')
    retained = cc.verify_retained(design, original, terminal, root / 'data/attempt-ledger.jsonl')
    w.require(plan['retained_outcomes'] == retained, 'retained values in continuation plan differ')
    return plan, runtime, authority, manifests


def validate_release(plan_ref, release_ref):
    plan, runtime, authority, _ = _verify_release_transaction(plan_ref, release_ref)
    return plan, runtime, authority


def admission(plan, authority, state, events, resources, reservations, row, *, now, gpu_idle):
    """Locked runner snapshot: all historical attempts and health costs stay charged."""
    from scripts.qd_ed_n31_contract import effective_hours
    validate_authority(authority, plan)
    budget, caps = state['budget'], authority['caps']
    w.require(state.get('n34_continuation_budget_authority') == plan['authority']
              and r.authorized_gpu(state) == 7 and budget['max_episode_attempts'] == caps['attempts']
              and budget['max_gpu_hours'] == caps['gpu_hours'] and budget['reserved'] == caps['buckets']
              and budget['gpu_hour_reservations'] == caps['protected_gpu_hours']
              and budget['amendment'] == authority['amendment'], 'adopted continuation authority differs')
    isolation = state.get('resource_isolation', {})
    w.require(isolation.get('status') == 'ACTIVE' and isolation.get('validation_status') == 'PASS'
              and isolation.get('private_budget') is True
              and not state.get('external_resource_hold', {}).get('do_not_auto_resume', False), 'private admission hold')
    c.require_replacement_history(events)
    groups = r.event_groups(events)
    w.require(all(g[-1]['event'] in r.TERMINAL for g in groups.values()), 'unsettled/live reservation')
    snap = r.budget_snapshot(events, resources)
    effective = effective_hours(authority)
    for hours in (caps['gpu_hours'], effective):
        w.require(r.check_budget_limits({**state, 'budget': {**budget, 'max_gpu_hours': hours}}, snap,
            row, reservations, bucket_caps=caps['buckets'], amendment=budget['amendment']) == 1800,
            'global/weekly full1840-second admission')
    local_events = [e for e in c.cohort_events(c.expected_rows(), events)
                    if e['episode_key'] in {x['episode_key'] for x in plan['episodes']}]
    # Charge every post-anchor health/preparation row, including failed/unlabelled
    # preparation. Conservative by design; never discard a cost due to its label.
    prefix_count = plan['resource_prefix_event_count']
    w.require(type(prefix_count) is int and 0 <= prefix_count <= len(resources), 'resource prefix count')
    local = r.budget_snapshot(local_events, resources[prefix_count:])
    w.require(local['gpu_healthcheck_inflight'] == 0, 'incremental resource unsettled')
    for bucket in ('baseline', 'development', 'recovery'):
        w.require(local['by_bucket'][bucket] <= cc.LIMITS[bucket], 'incremental bucket cap')
    pending_groups = cc._groups(c.expected_rows(), events)
    w.require(19 <= len(pending_groups) < 30 and row == c.expected_rows()[len(pending_groups)], 'next missing row only')
    accounted = []
    for index, group in enumerate(pending_groups):
        final = group[-1]
        w.require([e['event'] for e in group] == ['reserved', 'dispatched', 'valid']
                  and final.get('outcome_valid') is True
                  and final.get('required_cost_telemetry_complete') is True
                  and type(final.get('success')) is bool, 'invalid attempt forbids continuation/recovery')
        accounted.append(cc._outcome(c.expected_rows()[index], final,
                         'retained_legacy' if index < 19 else 'continuation'))
    w.require(cc.summarize(accounted, 'READY_FOR_ROOT_RELEASE')['candidate_upper_bound'] >= 5,
              'complete-triple futility forbids admission')
    protected = sum(max(0., h - snap['gpu_hours_by_bucket'][k]) for k, h in caps['protected_gpu_hours'].items())
    allowance = {'authority_starts_at': authority['starts_at'],
        'authority_ends_at': min(authority['coordinator_ends_at'], authority['weekly_window']['ends_at']),
        'private_budget': True, 'gpu_idle': gpu_idle, 'physical_gpu': 7, 'gpu_uuid': c.GPU_UUID,
        'live_handles': [], 'unsettled_reservations': 0,
        'global_seconds_remaining': (effective - snap['gpu_hours_consumed']) * 3600,
        'private_seconds_remaining': (caps['gpu_hours'] - snap['gpu_hours_consumed']) * 3600,
        'protected_seconds_remaining': protected * 3600,
        'incremental_seconds_remaining': 20240 - local['gpu_hours_consumed'] * 3600,
        'bucket_attempts_remaining': min(caps['buckets'][row['budget_bucket']] - snap['by_bucket'][row['budget_bucket']],
            cc.LIMITS[row['budget_bucket']] - local['by_bucket'][row['budget_bucket']]),
        'global_attempts_remaining': caps['attempts'] - snap['dispatched'],
        'protected_attempts_remaining': sum(max(0, caps['buckets'][k] - snap['by_bucket'][k]) for k in ('validation', 'formal')),
        'incremental_attempts_remaining': 11 - local['dispatched']}
    cc.guard(row, allowance, now=now, stop_path=plan['stop_path'])
    return snap
