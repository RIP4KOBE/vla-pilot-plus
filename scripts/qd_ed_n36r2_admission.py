"""Prospective N36R2 gates. This module creates no approval or release token."""
from pathlib import Path
from scripts import qd_ed_n23_worker as w, qd_ed_n36_contract as c
from scripts import qd_ed_n36r2_draft as draft

SESSION = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z')
OWNER = Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree')
SOURCE = SESSION / 'variants/n36r2_alias_recovery_001250/implementation_worktree'
PREPARATION_ID = 'n36_healthcheck_n36r2_preparation_001276'
KIND = 'n36r2_resource_preparation_v1'
HEALTH = {'preparation_id': PREPARATION_ID, 'max_invocations': 41,
          'timeout_seconds': 20, 'cleanup_seconds': 40,
          'per_invocation_seconds': 60, 'aggregate_seconds': 1800}


def owner_root(plan):
    if c.cohort(plan) != c.DRAFT_RECOVERY_COHORT:
        return Path(plan['worktree']).resolve()
    w.require(OWNER.resolve() == OWNER and SOURCE.resolve() == SOURCE, 'N36R2 route symlink redirection')
    route = plan['resource_routing']
    expected = {'source_cwd': str(SOURCE), 'owner_root': str(OWNER.resolve()),
                'physical_gpu': 7, 'gpu_uuid': c.GPU_UUID}
    w.require(route == expected and Path(plan['worktree']).resolve() == SOURCE,
              'N36R2 private source/owner routing differs')
    return OWNER.resolve()


def validate_protocol(plan):
    value = w.read_ref(plan['protocol'])
    old_plan = w.read_ref(value['inherited_draft_plan'])
    draft.validate_protocol(old_plan)
    old = w.read_ref(old_plan['protocol'])
    ledger = w.read_ref(plan['accounting'])
    expected_ledger = {'schema': 'n36r2-prospective-accounting-v1',
        'inherited_accounting': w.read_ref(old_plan['accounting'])['inherited_accounting'],
        'preserved_attempts': draft.PRESERVED, 'caps': c.CAPS,
        'healthchecks': HEALTH, 'ledger_prefixes': ledger['ledger_prefixes'],
        'calculation': ledger['calculation'], 'automatic_recoveries': 0,
        'new_budget_authority': False, 'release_enabled': False}
    w.require(ledger == expected_ledger, 'N36R2 finite accounting differs')
    validate_calculation(ledger)
    w.require(set(ledger['ledger_prefixes']) == {
        'attempt-ledger.jsonl', 'gpu-healthcheck-ledger.jsonl', 'gpu-hour-reservation-ledger.jsonl'},
        'N36R2 all private ledger prefixes required')
    root = owner_root(plan)
    for name, anchor in ledger['ledger_prefixes'].items():
        w.require(Path(anchor['path']).resolve() == root / 'data' / name,
                  'N36R2 foreign ledger forbidden')
    expected = {'schema': 'n36r2-prospective-protocol-v1',
        'inherited_draft_plan': value['inherited_draft_plan'],
        'inherited_protocol': old['inherited_protocol'],
        'accounting': plan['accounting'], 'episodes': c.plan_rows(plan),
        'protocol_review': old_plan['protocol_review'], 'healthchecks': HEALTH,
        'resource_routing': plan['resource_routing'], 'automatic_recoveries': 0,
        'scientific_changes': False, 'release_enabled': False}
    w.require(value == expected and plan['protocol_review'] == old_plan['protocol_review'],
              'N36R2 exact prospective protocol/science')
    return value


def validate_authority(plan, authority):
    protocol = validate_protocol(plan)
    ledger = w.read_ref(plan['accounting'])
    w.require(authority['cohort'] == c.DRAFT_RECOVERY_COHORT
        and authority['protocol'] == plan['protocol']
        and authority['accounting'] == protocol['accounting']
        and authority['amendment'] == plan['accounting']
        and authority['ledger_prefixes'] == ledger['ledger_prefixes'],
        'N36R2 authority accounting/prefixes differ')


def preserve_charges(events):
    for retained in draft.PRESERVED:
        key = retained['attempt_id']
        group = [e for e in events if e.get('attempt_id') == key or e.get('episode_key') == key]
        w.require([e['event'] for e in group] == ['reserved', 'dispatched', 'aborted']
            and all(e.get('attempt_id') == e.get('episode_key') == key for e in group)
            and group[-1].get('gpu_process_wall_seconds') == retained['gpu_seconds'],
            'N36R2 both invalid attempts and costs must remain')


def resource_events(plan, resources):
    permitted = {PREPARATION_ID} | {'n36_healthcheck_' + row['episode_key'] for row in c.plan_rows(plan)}
    selected = {e['resource_id'] for e in resources if e.get('cohort') == c.DRAFT_RECOVERY_COHORT
        or e.get('kind') == KIND or str(e.get('resource_id', '')).startswith('n36_healthcheck_n36r2')}
    local = [e for e in resources if e['resource_id'] in selected]
    binding = c.operational_binding(plan)
    w.require(all(e['resource_id'] in permitted and e.get('kind') == KIND
        and all(e.get(k) == v for k, v in binding.items())
        and type(e.get('timeout_seconds')) is int and 0 < e['timeout_seconds'] <= 20
        and e.get('cleanup_seconds') == 40
        and e.get('reserved_gpu_seconds') == e['timeout_seconds'] + 40 for e in local),
        'N36R2 fresh bounded resource binding')
    return local


def child_environment(plan, runtime):
    from scripts import qd_ed_final_runner as r
    env = r.child_environment(runtime)
    if c.cohort(plan) == c.DRAFT_RECOVERY_COHORT:
        owner_root(plan)
        env['PYTHONPATH'] = ':'.join(str(SOURCE / p) for p in
            ('', 'third_party/lerobot/src', 'third_party/rdt', 'third_party/libero_pro'))
        env['PYTHONNOUSERSITE'] = '1'
    return env


def independent_review(plan):
    review = w.read_ref(plan['b5_review'])
    w.require(review == {'schema': 'n36r2-independent-b5-review-v1',
        'decision': 'PASS_PREPARATION_REQUIRES_ROOT_RELEASE',
        **{key: plan[key] for key in ('source', 'scientific_source', 'protocol', 'accounting',
            'runtime', 'runtime_closure', 'native_build', 'controller_semantics', 'resource_routing')},
        'worker_receipts_are_future': True, 'release_enabled': False},
        'N36R2 independent source/runtime/accounting review required')


def validate_calculation(ledger):
    """Recompute finite planning arithmetic; live admission still rereads journals."""
    from decimal import Decimal
    value = w.read_ref(ledger['calculation'])
    snap_record = w.read_ref(value['ledger_snapshot'])
    snap = snap_record['snapshot']
    w.require(value['schema'] == 'n36r2-accounting-calculation-v1'
        and value['release_enabled'] is False and value['new_budget_authority'] is False
        and value['amendment_required'] is False
        and value['preserved_attempts'] == draft.PRESERVED
        and value['prior_accounting'] == ledger['inherited_accounting']
        and snap_record['ledger_prefixes'] == ledger['ledger_prefixes'],
        'N36R2 accounting calculation binding')
    prior = w.read_ref(value['prior_accounting'])
    w.require(value['prior_accounting']['sha256'] == c.ACCOUNTING_SHA,
              'N36R2 accounting original anchor')
    d = lambda x: Decimal(str(c.finite(x, 'planning accounting')))
    margin = d(prior['cost_reconciliation']['retained_admission_margin_gpu_hours'])
    retained = d(snap['gpu_hours_consumed'])
    effective = Decimal('53.08404692669838') + 168
    protected = {k: max(Decimal(0), d(v) - d(snap['gpu_hours_by_bucket'][k]))
                 for k, v in c.CAPS['protected_gpu_hours'].items()}
    after = retained + margin + 21
    checks = {'production_snapshot_gpu_hours':retained, 'retained_margin_gpu_hours':margin,
        'conservative_charge_gpu_hours':retained+margin, 'absolute_cap_gpu_hours':Decimal(224),
        'effective_cap_gpu_hours':effective, 'conservative_after_cohort_gpu_hours':after,
        'absolute_headroom_after_cohort_gpu_hours':Decimal(224)-after,
        'effective_headroom_after_cohort_gpu_hours':effective-after,
        'protected_validation_remaining_gpu_hours':protected['validation'],
        'protected_formal_remaining_gpu_hours':protected['formal'],
        'protected_total_remaining_gpu_hours':sum(protected.values()),
        'unprotected_effective_headroom_after_cohort_gpu_hours':effective-after-sum(protected.values())}
    w.require(all(Decimal(value['arithmetic'][key]) == expected for key, expected in checks.items())
        and checks['unprotected_effective_headroom_after_cohort_gpu_hours'] >= 0,
        'N36R2 exact finite planning arithmetic')
    w.require(value['cohort_seconds'] == {'episode':1800,'cleanup':40,'per_episode_reserved':1840,
        'cells':40,'episodes_total':73600,'healthchecks_total':1800,'contingency':200,'total':75600},
        'N36R2 finite cohort full headroom')
    w.require(snap['running'] == snap['gpu_healthcheck_inflight'] == 0,
              'N36R2 planning unsettled accounting')
    for row in value['bucket_arithmetic']:
        k = row['bucket']; addition = 10 if k == 'baseline' else 30 if k == 'development' else 0
        before = snap['by_bucket'][k]; cap = c.CAPS['buckets'][k]
        w.require(row == {'bucket':k, 'before':before, 'addition':addition,
            'after':before+addition, 'cap':cap, 'remaining_after':cap-before-addition}
            and cap-before-addition >= 0, 'N36R2 attempt arithmetic')
    w.require({row['bucket'] for row in value['bucket_arithmetic']} == set(c.CAPS['buckets'])
        and len(value['bucket_arithmetic']) == len(c.CAPS['buckets']), 'N36R2 all bucket arithmetic')
    protected_attempts = sum(max(0,c.CAPS['buckets'][k]-snap['by_bucket'][k]) for k in ('validation','formal'))
    w.require(value['attempts'] == {'before':snap['dispatched'],'addition':40,
        'after':snap['dispatched']+40,'cap':1800,'remaining':1800-snap['dispatched']-40,
        'protected_remaining':protected_attempts}
        and 1800-snap['dispatched']-40 >= protected_attempts, 'N36R2 global attempt arithmetic')
    return value
