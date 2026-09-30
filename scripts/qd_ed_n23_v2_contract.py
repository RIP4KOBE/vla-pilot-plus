#!/usr/bin/env python3
"""Prospective N23 v2: closed successor and two typed whole-episode recoveries."""
from __future__ import annotations
from contextlib import contextmanager
import json
import os
from pathlib import Path
import threading
from scripts import qd_ed_n23_dev_contract as v1
from scripts import qd_ed_n23_worker as worker

ROOT=v1.ROOT
SESSION=v1.SESSION
RUN_DIR=v1.RUN_DIR
SOURCE_PLAN=v1.SOURCE_PLAN
GPU7_RUNTIME=v1.GPU7_RUNTIME
GPU7_UUID=v1.GPU7_UUID
GPU7_PROOF=v1.GPU7_PROOF
ARMS=v1.ARMS
TASKS=v1.TASKS
AUTONOMOUS_REPLY=v1.AUTONOMOUS_REPLY
PROTOCOL=RUN_DIR/'protocol-dev-v2-prospective.md'
PROTOCOL_SHA='11a311d46f62c809160ba18b7960c6eb36ad612450601b32998a3d6e21f95e0d'
BACKEND_PROTOCOL=RUN_DIR/'backend-arithmetic-protocol-v2.md'
BACKEND_PROTOCOL_SHA='9e21c6ae1b84cd2f8d85b3c3326a9e590f3775f763d900e636d147ac2d689053'
BUDGET_AMENDMENT=SESSION/'budget-autonomous-amendment-20260930-n23-v2.md'
AMENDMENT_SHA='6a5704152a2e783b3769648e915e458d4f08e8d75f12bde47a2b95ed1ebdc7ee'
OBSERVABILITY=RUN_DIR/'timeout-observability-addendum-v2.md'
OBSERVABILITY_SHA='fa0723919c67d0417b101be2a36d9832cfaaf15e4b1c4e0cdfbf61caa43e34c6'
PREDECESSOR_REVIEW=RUN_DIR/'predecessor-review-v2.json'
FINAL_REVIEW=RUN_DIR/'final-source-runtime-review-v2.json'
COHORT='N23_CLIPPED_QUALITY_DEV_V2_20260930'
PREFLIGHT='N23_BACKEND_PREFLIGHT_V2_20260930'
ALL_PREFLIGHTS={v1.PREFLIGHT,PREFLIGHT}
ALL_COHORTS={v1.COHORT,COHORT}
LIMITS={'primary_cells':40,'dispatches':42,'recoveries':2,'recoveries_per_cell':1,'gpu_hours':22.,
        'episode_timeout_seconds':1800,'cleanup_seconds':40,'physical_gpu':7}
EXTRA_SOURCE={'scripts/qd_ed_n23_v2_contract.py','scripts/qd_ed_n23_v2_predecessor.py',
 'scripts/qd_ed_n23_v2_recovery.py','scripts/qd_ed_n23_v2_prepare.py','scripts/qd_ed_n23_v2_supervise.py',
 'scripts/qd_ed_n23_v2_backend.py','scripts/qd_ed_n23_v2_preflight_admit.py',
 'tests/test_qd_ed_n23_v2.py','experiments/iteration_023_actuator_clipped_quality/timeout-observability-addendum-v2.md','experiments/iteration_023_actuator_clipped_quality/protocol-dev-v2-prospective.md',
 'experiments/iteration_023_actuator_clipped_quality/backend-arithmetic-protocol-v2.md',
 'experiments/iteration_023_actuator_clipped_quality/budget-amendment-v2.md',
 'experiments/iteration_023_actuator_clipped_quality/closed-runtime-admission-v2.md',
 'scripts/qd_ed_n23_uuid_repair.py','tests/test_qd_ed_n23_uuid_repair.py',
 'experiments/iteration_023_actuator_clipped_quality/uuid-repair-engineering-exception-v1.md',
 'scripts/qd_ed_n23_uuid_native_repair.py','tests/test_qd_ed_n23_uuid_native_repair.py',
 'experiments/iteration_023_actuator_clipped_quality/uuid-native-repair-engineering-exception-v2.md'}
sha=worker.sha
ref=v1.ref
_SCOPE=None


def source_paths(r):return v1.source_paths(r)|EXTRA_SOURCE


def expected_rows():
    # Same original frozen identities and arm order, new prospective cohort/key only.
    return [{**row,'iteration':COHORT,'episode_key':row['episode_key'].replace('n23_dev_','n23v2_dev_')}
            for row in v1.expected_rows()]


def require_state(state,r):
    r['require'](state['resource_isolation']['status']=='ACTIVE'
        and state['resource_isolation']['validation_status']=='PASS' and state['resource_isolation']['private_budget'] is True
        and state['budget'].get('amendment')==r['GPU7_N23_V2_AMENDMENT']
        and state['budget']['max_episode_attempts']==478 and state['budget']['max_gpu_hours']==100.
        and state['budget']['reserved']==r['N23_BUCKETS']
        and state['budget']['gpu_hour_reservations']=={'validation':32.,'formal':12.}
        and r['authorized_gpu'](state)==7 and state.get('n23_v2_gpu7_binding')=={
            'scope':COHORT+'_and_backend_preflight_only','user_reply':AUTONOMOUS_REPLY,'selected_gpu':7,
            'addendum_path':str(PROTOCOL),'addendum_sha256':PROTOCOL_SHA},'N23 v2 adopted private budget/device differs')
    r['require'](not state.get('external_resource_hold',{}).get('do_not_auto_resume',False),'N23 v2 external hold')


def cross_version_unused(events):
    worker.require(not any(e.get('identity',{}).get('iteration') in ALL_PREFLIGHTS|ALL_COHORTS
        or e.get('n23_backend_preflight') is True for e in events),
        'N23 v1/v2 preflight or Dev already reserved; single arithmetic opportunity')


def full_capacity(state,events,resources,r,*,preflight=False):
    require_state(state,r);snap=r['budget_snapshot'](events,resources)
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    charged=[e for e in local if e['event']=='dispatched']
    spent=sum(e['gpu_process_wall_seconds'] for e in local if e['event'] in r['TERMINAL'])/3600
    remaining={b:need-sum(e['budget_bucket']==b for e in charged) for b,need in (('baseline',10),('development',30))}
    recoveries={e['attempt_id'] for e in local if e.get('retry_of')}
    worker.require(len(recoveries)<=2 and len(charged)<=42 and all(n>=0 for n in remaining.values()),'N23 v2 attempt limit exceeded')
    remaining['recovery']=2-len(recoveries)+int(preflight)
    protected_hours=sum(max(0.,h-snap['gpu_hours_by_bucket'][b]) for b,h in state['budget']['gpu_hour_reservations'].items())
    worker.require(snap['running']==snap['gpu_healthcheck_inflight']==0
        and all(g[-1]['event'] in r['TERMINAL'] for g in r['event_groups'](events).values())
        and snap['gpu_hours_consumed']+max(0.,22.-spent)+(160/3600 if preflight else 0.)+protected_hours<=100.+1e-9,
        'N23 v2 whole remaining ceiling/preflight/protected hours unavailable or owner busy')
    worker.require(all(state['budget']['reserved'][b]-snap['by_bucket'][b]>=n for b,n in remaining.items()),
        'N23 v2 full primary/recovery capacity unavailable')
    protected_attempts=sum(max(0,state['budget']['reserved'][b]-snap['by_bucket'][b]) for b in ('validation','formal'))
    worker.require(snap['dispatched']+sum(remaining.values())+protected_attempts<=478,
        'N23 v2 full matrix/recovery/preflight would borrow protected attempts')


@contextmanager
def supervised_scope(plan,root,episode_key,*,eligibility=None):
    global _SCOPE
    worker.require(_SCOPE is None,'nested N23 v2 scope')
    _SCOPE={'root':str(Path(root).resolve()),'source':plan['source_commit'],'key':episode_key,
        'pid':os.getpid(),'thread':threading.get_ident(),'eligibility':eligibility}
    try:yield
    finally:_SCOPE=None


def require_scope(plan,root,r,row=None):
    worker.require(_SCOPE is not None and _SCOPE['root']==str(Path(root).resolve())
        and _SCOPE['source']==plan['source_commit'] and _SCOPE['pid']==os.getpid()
        and _SCOPE['thread']==threading.get_ident() and (row is None or _SCOPE['key']==row['episode_key']),
        'N23 v2 requires one-cell scoped supervisor')


def effective_row(plan,row,events,root,r):
    require_scope(plan,root,r,row)
    if _SCOPE['eligibility'] is None:return row
    from scripts import qd_ed_n23_v2_recovery as recovery
    record=recovery.verify_eligibility(_SCOPE['eligibility'],plan,row,events,root,r)
    return {**row,'budget_bucket':'recovery','retry_of':record['primary_attempt_id'],
        'n23_v2_recovery_eligibility':_SCOPE['eligibility']}


def primary_row(plan,row):
    matches=[v for v in plan['episodes'] if v['episode_key']==row['episode_key']]
    worker.require(len(matches)==1,'N23 v2 unknown scientific cell')
    primary=matches[0]
    worker.require(row==primary or (set(row)==set(primary)|{'retry_of','n23_v2_recovery_eligibility'}
        and row['budget_bucket']=='recovery' and {k:row[k] for k in primary if k!='budget_bucket'}==
        {k:v for k,v in primary.items() if k!='budget_bucket'}),'N23 v2 recovery scientific row changed')
    return primary


def protected_budget(state,events,resources,row,timeout,r,*,plan):
    primary_row(plan,row)
    worker.require(row['iteration']==COHORT and row['profile'] in ARMS and timeout==1800,'N23 v2 row/timeout differs')
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    worker.require(sum(e['event']=='dispatched' for e in local)<42
        and sum(e.get('gpu_process_wall_seconds',0.) for e in local if e['event'] in r['TERMINAL'])+1840<=22*3600,
        'N23 v2 local dispatch/hour cap')
    full_capacity(state,events,resources,r)


def validate_runtime(runtime,root,r):
    # Frozen inputs retain the pre-archive lexical prefix. Admit that prefix
    # only when it resolves to this exact owning worktree; retain every v1
    # runtime/Stage/GPU/probe check and the original strict file verifier.
    r['require'](Path(runtime['worktree']).resolve()==Path(root).resolve(),
        'N23 v2 frozen runtime worktree alias differs')
    bound=dict(r)
    def verify_runtime_files(records,*,allowed_roots):
        r['verify_files'](records,allowed_roots=(*allowed_roots,Path(runtime['worktree'])))
    bound['verify_files']=verify_runtime_files
    v1.validate_runtime(runtime,root,bound)


read_worker_report=v1.read_worker_report


SCIENTIFIC_BASE='1bcf888e88181580bfb854b2e7aa1834bf85df99'
ALLOWED_EXISTING={'scripts/qd_ed_final_runner.py','scripts/qd_ed_n23_preflight_admit.py'}


def repair_module(meta):
    """Only the two explicit historical engineering exception schemas route."""
    if isinstance(meta,dict) and meta.get('schema')=='n23-uuid-repair-binding-v1':
        from scripts import qd_ed_n23_uuid_repair as selected
    elif isinstance(meta,dict) and meta.get('schema')=='n23-uuid-native-repair-binding-v2':
        from scripts import qd_ed_n23_uuid_native_repair as selected
    else:
        raise ValueError('unrecognized N23 UUID repair authority schema')
    return selected


def source_delta(root,*,repair=None):
    if repair is not None:
        uuid_repair=repair_module(repair)
        worker.require(repair==uuid_repair.binding(),'UUID repair source scope binding differs')
        return uuid_repair.source_delta(root)
    import subprocess
    changed=set(subprocess.check_output(['git','diff','--name-only',SCIENTIFIC_BASE,'HEAD'],cwd=root,text=True).splitlines())
    worker.require(changed<=EXTRA_SOURCE|ALLOWED_EXISTING,'N23 v2 changed frozen scientific/v1 source')
    return sorted(changed)


def predecessor_review():
    from scripts import qd_ed_n23_v2_predecessor as predecessor
    reference=ref(PREDECESSOR_REVIEW);review=predecessor.gate(reference)
    worker.require(review['source_plan']==ref(SOURCE_PLAN),'N23 v2 predecessor plan differs')
    return reference


def final_review(source, runtime_ref,*,repair=None):
    if repair is not None:
        uuid_repair=repair_module(repair)
        worker.require(repair==uuid_repair.binding(),'UUID repair review binding differs')
        return uuid_repair.final_review(source,runtime_ref)
    reference = ref(FINAL_REVIEW); review = worker.read_ref(reference)
    worker.require(sha(PROTOCOL) == PROTOCOL_SHA and sha(BACKEND_PROTOCOL) == BACKEND_PROTOCOL_SHA
                   and sha(BUDGET_AMENDMENT) == AMENDMENT_SHA and sha(OBSERVABILITY)==OBSERVABILITY_SHA, 'N23 frozen protocols/amendment differ')
    worker.require(review == {'schema': 'n23-final-source-runtime-review-v2', 'disposition': 'accepted',
        'source': source, 'runtime': runtime_ref, 'dev_protocol': ref(PROTOCOL),
        'backend_protocol': ref(BACKEND_PROTOCOL), 'amendment': ref(BUDGET_AMENDMENT), 'timeout_observability':ref(OBSERVABILITY),
        'no_gpu_release': True}, 'N23 root final source/runtime review missing or differs')
    return reference


def backend_proof(reference, source, root, r):
    r['require'](isinstance(reference, dict) and set(reference) == {'plan', 'report', 'attempt_id'},
                 'N23 actual backend proof is missing')
    from scripts import qd_ed_n23_v2_backend as backend
    plan = worker.read_ref(reference['plan']); worker.read_ref(reference['report'])
    r['require'](plan['runtime'] == ref(GPU7_RUNTIME) and plan['source'] == source
                 and plan['predecessor_review'] == predecessor_review(), 'N23 preflight runtime/source/predecessor differs')
    events = r['read_events'](Path(root) / 'data/attempt-ledger.jsonl')
    if plan.get('uuid_repair') is not None:
        uuid_repair=repair_module(plan['uuid_repair'])
        terminal=uuid_repair.verify_lineage(plan,reference,events,source,r)
        r['require'](backend.verify_preflight_proof(reference['plan']['path'],reference['report']['path'],terminal,source)
            ==reference['report'],'UUID repair backend proof hash differs')
        return reference
    local = [e for e in events if e.get('identity', {}).get('iteration') in ALL_PREFLIGHTS
             or e.get('n23_backend_preflight') is True]
    r['require'](all(e.get('identity',{}).get('iteration')==PREFLIGHT for e in local),'N23 v2 backend cannot reuse/retry v1 preflight')
    r['require'](len({e['attempt_id'] for e in local}) == 1
                 and local[0]['event'] == 'reserved' and local[-1]['event'] == 'valid'
                 and local[-1]['attempt_id'] == reference['attempt_id']
                 and local[-1].get('n23_final_review') == final_review(source, ref(GPU7_RUNTIME))
                 and len([e for e in local if e['event'] == 'dispatched']) == 1,
                 'N23 proof requires its single actual recovery ledger attempt')
    r['require'](backend.verify_preflight_proof(reference['plan']['path'], reference['report']['path'],
                                               local[-1], source) == reference['report'],
                 'N23 backend proof hash differs')
    return reference


def validate_contract(plan, manifest, runtime, seeds, root, r):
    source = worker.source_record(root, [v['path'] for v in plan['code_files']])
    meta = plan.get('n23_cohort', {})
    if meta.get('uuid_repair') is not None:source_delta(root,repair=meta['uuid_repair'])
    else:source_delta(root)
    r['require'](sha(Path(root) / 'experiments/iteration_023_actuator_clipped_quality/protocol-dev-v2-prospective.md') == PROTOCOL_SHA
        and sha(Path(root) / 'experiments/iteration_023_actuator_clipped_quality/backend-arithmetic-protocol-v2.md') == BACKEND_PROTOCOL_SHA
        and sha(Path(root) / 'experiments/iteration_023_actuator_clipped_quality/budget-amendment-v2.md') == AMENDMENT_SHA
        and sha(Path(root) / 'experiments/iteration_023_actuator_clipped_quality/timeout-observability-addendum-v2.md')==OBSERVABILITY_SHA,
        'N23 tracked protocols or amendment differ')
    r['require'](source['commit'] == plan['source_commit'] and source['files'] == plan['code_files']
        and source_paths(r) <= {v['path'] for v in plan['code_files']}, 'N23 complete sorted committed source differs')
    r['require'](meta == {'schema': 'n23-clipped-quality-dev-v2', 'cohort_id': COHORT, 'limits': LIMITS,
        'n7_role': 'ablation_control_only_no_promotion', 'predecessor_review': predecessor_review(),
        'budget_amendment': ref(BUDGET_AMENDMENT), 'protocol': ref(PROTOCOL), 'source_plan': ref(SOURCE_PLAN),
        'final_review': final_review(source, ref(GPU7_RUNTIME),repair=meta['uuid_repair']) if meta.get('uuid_repair') is not None else final_review(source,ref(GPU7_RUNTIME)),
        'worker_audit': worker.WORKER_CONTRACT, 'timeout_observability':ref(OBSERVABILITY),
        'early_stop': 'numeric_futility_after_complete_task_quadruple',
        'backend_proof': backend_proof(meta.get('backend_proof'), source, root, r),
        **({'uuid_repair':meta['uuid_repair']} if meta.get('uuid_repair') is not None else {})},
        'N23 prospective cohort, source review or backend proof differs')
    if meta.get('uuid_repair') is not None:
        r['require'](worker.read_ref(meta['backend_proof']['plan']).get('uuid_repair')==meta['uuid_repair'],
            'UUID repair Dev/backend provenance differs')
    r['require'](plan['episodes'] == expected_rows() and set(plan['candidate_profiles']) == {'N7', 'N23'}
        and set(manifest['profiles']) == set(ARMS)
        and plan.get('phase_authorization') == {'dev': True, 'validation': False, 'formal': False}
        and plan.get('stage_condition') == r['E2_STAGE_CONDITION']
        and not any(plan.get(k) is not None for k in ('n7_cohort','n9_cohort','n11_cohort','n17_passive_physics',
             'n18_cohort','n19_cohort','n20_cohort','n21_cohort','n22_cohort','n7_validation',
             'n7_validation_continuation','n7_passive_diagnostic','n7_e2_passive_diagnostic')),
        'N23 closed matrix/profile/phase gate differs')
    for arm in ('N7', 'N23'):
        path = Path(root) / f'configs/qd_ed_final/candidate_{arm.lower()}.json'
        r['require'](plan['candidate_profiles'][arm] == ref(path) and str(path.relative_to(root)) in plan['scientific_config_files'],
                     'N23 scientific profile fingerprint differs')
    n7 = manifest['profiles']['N7']['resolved_eds_config']; n23 = manifest['profiles']['N23']['resolved_eds_config']
    r['require'](n23 == {**n7, 'qd_quality_mode': 'actuator_clipped_provider_v1'}
        and n7 == {**manifest['profiles']['Q0']['resolved_eds_config'],
                   'qd_descriptor': 'target_xy_quadrant_signed_height_v1',
                   'qd_final_selection_mode': 'terminal_grasp_proximity_v1'}, 'N23 sole quality delta differs')
    r['require'](plan['runtime_manifest_path'] == str(GPU7_RUNTIME)
                 and plan['runtime_manifest_sha256'] == sha(GPU7_RUNTIME), 'N23 runtime reference differs')
    validate_runtime(runtime, root, r)
    state=r['read_state'](Path(root) / 'research-state.yaml');require_state(state,r)
    if meta.get('uuid_repair') is not None:
        uuid_repair=repair_module(meta['uuid_repair'])
        uuid_repair.authority(meta['uuid_repair'],source,ref(GPU7_RUNTIME),state)


def accepted_cell(plan,row,events,root,r):
    """A primary or its sole typed recovery may contribute one scientific cell."""
    from scripts import qd_ed_n23_v2_recovery as recovery
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT and e.get('episode_key')==row['episode_key']]
    groups=list(r['event_groups'](local).values())
    worker.require(1<=len(groups)<=2,'N23 v2 scientific cell missing or duplicated')
    first=groups[0][-1]
    worker.require(groups[0][0].get('retry_of') is None and first['event'] in r['TERMINAL'], 'N23 v2 primary unsettled')
    if len(groups)==1:
        final=first
    else:
        final=groups[1][-1];reference=groups[1][0].get('n23_v2_recovery_eligibility')
        worker.require(first.get('outcome_valid') is False and final.get('retry_of')==first['attempt_id']
            and final['budget_bucket']=='recovery' and reference is not None,'N23 v2 cell is not its one typed recovery')
        boundary=next(i for i,e in enumerate(events) if e['attempt_id']==final['attempt_id'])
        before=events[:boundary]
        # Eligibility is revalidated against the pre-recovery prefix, so no second attempt can authorize itself.
        record=worker.read_ref(reference)
        recovery.verify_eligibility(reference,plan,row,before,root,r)
        worker.require(record['primary_attempt_id']==first['attempt_id'],'N23 v2 retry lineage differs')
    worker.require(final['event']=='valid' and final.get('outcome_valid') is True and final.get('required_cost_telemetry_complete') is True,
        'N23 v2 no accepted scientific cell; invalid primary/recovery stops advancement')
    context=worker.read_ref(ref(Path(final['output_dir'])/'n23-worker-context.json'))
    recovery.terminal_binding(final,row,plan,context['plan'],r)
    worker.require(worker.read_ref(context['plan'])==plan and final.get('n23_worker_receipt')==
        ref(Path(final['output_dir'])/'eds_eval/in-worker-audit-receipt.json'),'N23 v2 accepted cell receipt/plan differs')
    report=read_worker_report(final['output_dir'],r)
    worker.require(report.get('accepted') is True and report.get('evidence_complete') is True,'N23 v2 native audit incomplete')
    return final


def admission(plan,runtime,row,events,resources,root,r):
    primary=primary_row(plan,row);index=plan['episodes'].index(primary)
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    previous={v['episode_key'] for v in plan['episodes'][:index]}
    allowed=previous|({row['episode_key']} if row.get('retry_of') else set())
    worker.require(all(e.get('episode_key') in allowed for e in local),'N23 v2 exact primary/recovery prefix required')
    successes=0
    for prior in plan['episodes'][:index]:
        final=accepted_cell(plan,prior,events,root,r)
        if prior['profile']=='N23':successes+=int(final['success'] is True)
    if row.get('retry_of'):
        from scripts import qd_ed_n23_v2_recovery as recovery
        recovery.verify_eligibility(row['n23_v2_recovery_eligibility'],plan,primary,events,root,r)
    worker.require(successes+10-index//4>=5,'N23 v2 complete-quadruple numeric futility')
    result={'n23_cohort_id':COHORT,'n23_protocol_sha256':PROTOCOL_SHA,
        'n23_timeout_observability_sha256':OBSERVABILITY_SHA,
        'n23_arm_role':'ablation_control_only' if row['profile']=='N7' else 'candidate' if row['profile']=='N23' else 'control'}
    if row.get('retry_of'):result['n23_v2_recovery_eligibility']=row['n23_v2_recovery_eligibility']
    return result
