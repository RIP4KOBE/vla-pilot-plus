"""Closed N24 Dev admission; root review/adoption/release are external artifacts."""
from contextlib import contextmanager
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import threading

from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n24_native as native

ROOT=Path(__file__).resolve().parents[1]
SESSION=ROOT.parent if ROOT.name=='study_worktree' else ROOT.parents[2]
RUN_DIR=SESSION/'variants/n24_gripper_mode_parent_rescue'
SOURCE_PLAN=SESSION/'variants/n23_actuator_clipped_quality/plan.frozen.v2.gpu7.json'
SOURCE_PLAN_SHA='acd2b2c639f7756cdc353b6a7eea8c93a4d735a8ce6ee25838d9502c938d07f0'
PROTOCOL=RUN_DIR/'protocol-dev-v1.md'
PROTOCOL_SHA='77163171815bdade8d05a4010ff59aa24a4157d447d6d7fb430f3163a80c4b3b'
OBSERVABILITY=SESSION/'variants/n23_actuator_clipped_quality/timeout-observability-addendum-v2.md'
OBSERVABILITY_SHA='fa0723919c67d0417b101be2a36d9832cfaaf15e4b1c4e0cdfbf61caa43e34c6'
FINAL_REVIEW=RUN_DIR/'final-source-runtime-review-v1.json'
AUTHORITY=RUN_DIR/'adoption-v1/authority.json'
BRIDGE=RUN_DIR/'source-equivalence-bridge-v1.json'
PHASE_A='3f6db2dc3dcc8db45b66a649568b43248c8b5f0e'
BASE='51104470983cdbafd08feb87f2f39b7553779405'
COHORT='N24_GRIPPER_MODE_PARENT_RESCUE_DEV_20260930'
PREFLIGHT='N24_OPTIONAL_TENSOR_PREFLIGHT_20260930'
ARMS=('C0','Q0','N23','N24')
LIMITS={'primary_cells':40,'episode_dispatches':42,'total_dispatches':43,'recoveries':2,
 'recoveries_per_cell':1,'gpu_hours':22.,'episode_timeout_seconds':1800,'cleanup_seconds':40,
 'physical_gpu':7,'optional_preflight_attempts':1,'optional_preflight_seconds':60}
CAPS={'attempts':478,'gpu_hours':100.,'buckets':{'baseline':51,'development':187,'validation':180,'formal':40,'recovery':20},
      'protected_gpu_hours':{'validation':32.,'formal':12.}}
GPU7_UUID='GPU-48473162-9548-1a19-04aa-ea86c5349187'
GPU7_PROOF='rdt-qd-ed-final-20260921T093925Z__gpu7_cuda_egl__4fafff3673e5'
WORKER_CONTRACT={'schema':'n24-same-process-native-audit-v1','arms':list(ARMS),
    'cuda_arithmetic_arms':['N23','N24'],'other_arm_backend':'cpu','timeout_includes_audit':True,
    'profile_bound_rescue_audit':True}
EXTRA_SOURCE={'scripts/qd_ed_n24_contract.py','scripts/qd_ed_n24_prepare.py','scripts/qd_ed_n24_supervise.py',
 'scripts/qd_ed_n24_recovery.py','scripts/qd_ed_n24_report.py','scripts/qd_ed_n24_native.py',
 'scripts/qd_ed_n24_bridge.py','tests/test_qd_ed_n24_controller.py','tests/test_qd_ed_n24_recovery.py',
 'core/qd_gripper_parent_rescue.py','scripts/audit_gripper_parent_rescue.py',
 'configs/qd_ed_final/candidate_n24.json','tests/test_n24_native_loop.py','tests/test_qd_gripper_parent_rescue.py',
 'experiments/qd_ed_n24/protocol-dev-v1.md','experiments/qd_ed_n24/controller-contract-v1.md'}
CONTROLLER_DELTA={p for p in EXTRA_SOURCE if p.startswith('scripts/qd_ed_n24_') or p.startswith('tests/test_qd_ed_n24_')}
CONTROLLER_DELTA|={'scripts/qd_ed_final_runner.py','scripts/qd_ed_n23_worker.py','experiments/qd_ed_n24/controller-contract-v1.md'}
ref=lambda path:{'path':str(Path(path).resolve()),'sha256':w.sha(path)}
_SCOPE=None


def original_plan():
    w.require(w.sha(SOURCE_PLAN)==SOURCE_PLAN_SHA,'N24 frozen source plan drift')
    return w.read_ref(ref(SOURCE_PLAN))


def runtime_ref():
    plan=original_plan()
    return {'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']}


def expected_rows():
    rows=original_plan()['episodes']
    w.require(len(rows)==40 and [(x['task_id'],x['profile']) for x in rows]==[(t,a) for t in range(10) for a in ('C0','Q0','N7','N23')],
              'N24 original task-major identities differ')
    result=[]
    for t in range(10):
        for arm,source in zip(ARMS,rows[t*4:t*4+4]):
            row=copy.deepcopy(source)
            row.update(iteration=COHORT,profile=arm,episode_key=f'n24_dev_t{t:02d}_{arm.lower()}_20260930')
            w.require(row['split']==row['seed_block']=='dev' and row['timeout_seconds']==1800
                and row['budget_bucket']==('baseline' if arm=='C0' else 'development') and 'retry_of' not in row,'N24 frozen row scope differs')
            result.append(row)
    return result


def source_paths(r):
    return {v['path'] for v in original_plan()['code_files']} | r['REQUIRED_CODE'] | w.REQUIRED_SOURCE | EXTRA_SOURCE


def imports_owned(root,r):
    root=Path(root).resolve()
    for path in (__file__,w.__file__,native.__file__,r['__file__']):
        w.require(Path(path).resolve().is_relative_to(root),'N24 adjacent-worktree module shadowing')


def final_review(source,runtime,root):
    from scripts import qd_ed_n24_bridge as bridge
    w.require(w.sha(PROTOCOL)==PROTOCOL_SHA and w.sha(OBSERVABILITY)==OBSERVABILITY_SHA
        and w.sha(Path(root)/'experiments/qd_ed_n24/protocol-dev-v1.md')==PROTOCOL_SHA,'N24 immutable protocols differ')
    bound=bridge.verify(ref(BRIDGE),source,runtime,root)
    record=w.read_ref(ref(FINAL_REVIEW))
    expected={'schema':'n24-source-runtime-review-v1','disposition':'accepted','source':source,'runtime':runtime,
        'protocol':ref(PROTOCOL),'source_plan':ref(SOURCE_PLAN),'source_bridge':ref(BRIDGE),
        'native_preflight':{'required':False,'proof':None},'no_gpu_release':True}
    w.require(record==expected and bound['new_source']==source,'N24 final root source/runtime review differs')
    return ref(FINAL_REVIEW)


def authority(source,runtime,root,state=None):
    record=w.read_ref(ref(AUTHORITY))
    keys={'schema','cohort_id','source','runtime','protocol','final_review','limits','caps','recorded_at',
          'authority_interpretation','validation_authorized','formal_authorized'}
    w.require(set(record)==keys and record['schema']=='n24-dev-authority-v1' and record['cohort_id']==COHORT
        and record['source']==source and record['runtime']==runtime and record['protocol']==ref(PROTOCOL)
        and record['final_review']==final_review(source,runtime,root) and record['limits']==LIMITS and record['caps']==CAPS
        and all(isinstance(record[k],str) and record[k].strip() for k in ('recorded_at','authority_interpretation'))
        and record['validation_authorized'] is False and record['formal_authorized'] is False,'N24 finite authority differs')
    if state is not None:w.require(state.get('n24_dev_authority')==ref(AUTHORITY),'N24 authority not adopted')
    return ref(AUTHORITY)


def require_state(state,r):
    budget=state['budget'];resource=state['resource_isolation']
    w.require(resource['status']=='ACTIVE' and resource['validation_status']=='PASS' and resource['private_budget'] is True
        and budget.get('amendment')==r['GPU7_N23_V2_AMENDMENT']
        and budget['max_episode_attempts']==478 and budget['max_gpu_hours']==100.
        and budget['reserved']==CAPS['buckets'] and budget['gpu_hour_reservations']==CAPS['protected_gpu_hours']
        and r['authorized_gpu'](state)==7 and not state.get('external_resource_hold',{}).get('do_not_auto_resume',False),
        'N24 private resource/budget/device/hold differs')
    reference=state.get('n24_dev_authority');w.require(reference==ref(AUTHORITY),'N24 adoption missing')
    record=w.read_ref(reference)
    authority(record['source'],record['runtime'],Path(r['ROOT']),state)


def full_capacity(state,events,resources,r):
    require_state(state,r);snap=r['budget_snapshot'](events,resources)
    from scripts import qd_ed_n24_bridge as bridge
    bridge.settled_backend(w.read_ref(ref(BRIDGE)),events,r)
    local=[e for e in events if e.get('identity',{}).get('iteration') in {COHORT,PREFLIGHT}]
    preflight=[e for e in local if e.get('identity',{}).get('iteration')==PREFLIGHT]
    # No optional tensor preflight is authorized by this source-equivalence path.
    w.require(not preflight,'N24 optional tensor preflight needs a separate prospective implementation/release')
    charged=[e for e in local if e['event']=='dispatched']
    recoveries={e['attempt_id'] for e in local if e.get('retry_of')}
    spent=sum(e.get('gpu_process_wall_seconds',0.) for e in local if e['event'] in r['TERMINAL'])/3600
    remaining={b:need-sum(e['budget_bucket']==b for e in charged) for b,need in (('baseline',10),('development',30))}
    w.require(len(charged)<=42 and len(recoveries)<=2 and all(v>=0 for v in remaining.values()),'N24 local counts exceeded')
    remaining['recovery']=2-len(recoveries)
    protected_hours=sum(max(0.,h-snap['gpu_hours_by_bucket'][b]) for b,h in CAPS['protected_gpu_hours'].items())
    protected_attempts=sum(max(0,CAPS['buckets'][b]-snap['by_bucket'][b]) for b in ('validation','formal'))
    w.require(snap['running']==snap['gpu_healthcheck_inflight']==0
        and all(g[-1]['event'] in r['TERMINAL'] for g in r['event_groups'](events).values()),'N24 unsettled owner/journal')
    w.require(snap['gpu_hours_consumed']+max(0.,22.-spent)+protected_hours<=100.+1e-9
        and all(CAPS['buckets'][b]-snap['by_bucket'][b]>=n for b,n in remaining.items())
        and snap['dispatched']+sum(remaining.values())+protected_attempts<=478,'N24 full remaining cohort borrows protected reserves')


@contextmanager
def supervised_scope(plan,root,episode_key,*,eligibility=None):
    global _SCOPE
    w.require(_SCOPE is None,'N24 nested scope')
    _SCOPE=(str(Path(root).resolve()),plan['source_commit'],episode_key,os.getpid(),threading.get_ident(),eligibility)
    try:yield
    finally:_SCOPE=None


def require_scope(plan,root,r,row=None):
    w.require(_SCOPE is not None and _SCOPE[:2]==(str(Path(root).resolve()),plan['source_commit'])
        and _SCOPE[3:5]==(os.getpid(),threading.get_ident()) and (row is None or row['episode_key']==_SCOPE[2]),
        'N24 requires exact single-cell owned scope')


def primary_row(plan,row):
    matches=[v for v in plan['episodes'] if v['episode_key']==row['episode_key']]
    w.require(len(matches)==1,'N24 unknown scientific cell');primary=matches[0]
    w.require(row==primary or (set(row)==set(primary)|{'retry_of','n24_recovery_eligibility'} and row['budget_bucket']=='recovery'
        and {k:row[k] for k in primary if k!='budget_bucket'}=={k:v for k,v in primary.items() if k!='budget_bucket'}),
        'N24 recovery row changed science')
    return primary


def effective_row(plan,row,events,root,r):
    require_scope(plan,root,r,row)
    if _SCOPE[5] is None:return row
    from scripts import qd_ed_n24_recovery as recovery
    record=recovery.verify_eligibility(_SCOPE[5],plan,row,events,root,r)
    return {**row,'budget_bucket':'recovery','retry_of':record['primary_attempt_id'],'n24_recovery_eligibility':_SCOPE[5]}


def protected_budget(state,events,resources,row,timeout,r,*,plan):
    primary_row(plan,row)
    w.require(row['iteration']==COHORT and row['profile'] in ARMS and timeout==1800,'N24 row/timeout differs')
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    w.require(sum(e['event']=='dispatched' for e in local)<42
        and sum(e.get('gpu_process_wall_seconds',0.) for e in local if e['event'] in r['TERMINAL'])+1840<=22*3600,
        'N24 local attempt/hour limit')
    full_capacity(state,events,resources,r)


def validate_runtime(runtime,root,r):
    w.require(runtime==w.read_ref(runtime_ref()) and Path(runtime['worktree']).resolve()==Path(root).resolve()
        and runtime.get('schema')=='qd-ed-runtime-setup-v1' and r['runtime_gpu'](runtime)==7
        and runtime['gpu_mapping']['uuid']==GPU7_UUID and runtime['gpu_mapping']['egl_device_index']==4
        and runtime.get('cuda_egl_verified') is True and runtime.get('cuda_egl_probe',{}).get('resource_id')==GPU7_PROOF
        and runtime.get('stage_recovered_error_condition')==r['E2_STAGE_CONDITION']
        and runtime.get('stage_engineering_condition')==r['n4e1_support']().engineering_condition()
        and runtime['frozen_stage_provider'].get('allow_recovered_error_events') is True,
        'N24 frozen runtime/GPU/provider differs')
    r['verify_files'](runtime['files'],allowed_roots=(Path(root),Path(runtime['worktree']),runtime['artifact_root']))


def metadata(source,root):
    runtime=runtime_ref()
    return {'schema':'n24-gripper-parent-rescue-dev-v1','cohort_id':COHORT,'limits':LIMITS,
        'protocol':ref(PROTOCOL),'source_plan':ref(SOURCE_PLAN),'timeout_observability':ref(OBSERVABILITY),
        'final_review':final_review(source,runtime,root),'authority':authority(source,runtime,root),
        'worker_audit':WORKER_CONTRACT,'n23_role':'ablation_control_only_no_promotion',
        'early_stop':'numeric_futility_after_complete_task_quadruple'}


def validate_contract(plan,manifest,runtime,seeds,root,r):
    imports_owned(root,r)
    source=w.source_record(root,[v['path'] for v in plan['code_files']])
    w.require(source['commit']==plan['source_commit'] and source['files']==plan['code_files']
        and source_paths(r)<={v['path'] for v in plan['code_files']},'N24 complete committed source missing')
    w.require(plan.get('n24_cohort')==metadata(source,root) and plan['episodes']==expected_rows()
        and set(plan['candidate_profiles'])=={'N23','N24'} and set(manifest['profiles'])==set(ARMS)
        and plan.get('phase_authorization')=={'dev':True,'validation':False,'formal':False}
        and plan.get('stage_condition')==r['E2_STAGE_CONDITION']
        and not any(k.startswith(('n7_','n9_','n11_','n17_','n18_','n19_','n20_','n21_','n22_','n23_')) for k in plan),
        'N24 closed prospective matrix/phase differs')
    for arm in ('N23','N24'):
        path=Path(root)/f'configs/qd_ed_final/candidate_{arm.lower()}.json'
        w.require(plan['candidate_profiles'][arm]==ref(path) and str(path.relative_to(root)) in plan['scientific_config_files'],
            'N24 profile fingerprint missing')
    n23=manifest['profiles']['N23']['resolved_eds_config'];n24=manifest['profiles']['N24']['resolved_eds_config']
    w.require(n24=={**n23,'qd_gripper_rescue_mode':native.MODE},'N24 sole science delta differs')
    w.require({'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']}==runtime_ref(),'N24 runtime ref differs')
    validate_runtime(runtime,root,r);require_state(r['read_state'](Path(root)/'research-state.yaml'),r)


def validate_worker_context(context,argv,root,output,plan,runtime):
    w.require(plan.get('frozen') is True and plan.get('n24_cohort',{}).get('worker_audit')==WORKER_CONTRACT
        and plan['worktree']==str(root) and context['profile'] in ARMS
        and output==Path(plan['artifact_root']).resolve()/'attempts'/context['attempt_id']
        and context['runtime']=={'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']},
        'N24 worker frozen plan/runtime differs')
    rows=[r for r in plan['episodes'] if r['episode_key']==context['episode_key']]
    w.require(len(rows)==1 and rows[0]['profile']==context['profile'] and rows[0]['split']=='dev'
        and rows[0]['iteration']==COHORT and rows[0]['timeout_seconds']==1800
        and context['source']['commit']==plan['source_commit'] and context['source']['files']==plan['code_files'],
        'N24 worker row/source differs')
    w.verify_source(root,context['source'])
    w.require(w.cuda_binding(runtime)['physical_gpu']==7,'N24 worker GPU differs')
    return root,output,runtime


def read_worker_report(output,r):
    return w.verify_receipt(Path(output)/'n23-worker-context.json',r['read_json'](Path(output)/'process.json'))


def accepted_cell(plan,row,events,root,r):
    from scripts import qd_ed_n24_recovery as recovery
    groups=list(r['event_groups']([e for e in events if e.get('identity',{}).get('iteration')==COHORT
        and e.get('episode_key')==row['episode_key']]).values())
    w.require(1<=len(groups)<=2,'N24 missing/duplicate cell')
    first=groups[0][-1];w.require(groups[0][0].get('retry_of') is None and first['event'] in r['TERMINAL'],'N24 primary unsettled')
    final=first
    if len(groups)==2:
        final=groups[1][-1];reference=groups[1][0].get('n24_recovery_eligibility')
        w.require(first.get('outcome_valid') is False and final.get('retry_of')==first['attempt_id']
            and final['budget_bucket']=='recovery' and reference is not None,'N24 first-valid lineage differs')
        boundary=next(i for i,e in enumerate(events) if e['attempt_id']==final['attempt_id'])
        recovery.verify_eligibility(reference,plan,row,events[:boundary],root,r)
    w.require(final['event']=='valid' and final.get('outcome_valid') is True
        and final.get('required_cost_telemetry_complete') is True,'N24 invalid primary/recovery cannot count')
    context=w.read_ref(ref(Path(final['output_dir'])/'n23-worker-context.json'))
    recovery.terminal_binding(final,row,plan,context['plan'],r)
    w.require(w.read_ref(context['plan'])==plan and w.read_ref(ref(Path(final['output_dir'])/'attempt-result.json'))==final
        and final.get('n23_worker_receipt')==ref(Path(final['output_dir'])/'eds_eval/in-worker-audit-receipt.json'),
        'N24 accepted terminal/plan/receipt differs')
    report=read_worker_report(final['output_dir'],r)
    w.require(type(final.get('guided_chunks')) is int,'N24 accepted guided count missing')
    native.from_output(row['profile'],final['output_dir'],report,final['guided_chunks'])
    return final


def admission(plan,runtime,row,events,resources,root,r):
    primary=primary_row(plan,row);index=plan['episodes'].index(primary)
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    allowed={v['episode_key'] for v in plan['episodes'][:index]}|({row['episode_key']} if row.get('retry_of') else set())
    w.require(all(e.get('episode_key') in allowed for e in local),'N24 exact prefix required')
    successes=sum(int(accepted_cell(plan,prior,events,root,r)['success'] is True) for prior in plan['episodes'][:index]
                  if prior['profile']=='N24')
    for prior in plan['episodes'][:index]:
        if prior['profile']!='N24':accepted_cell(plan,prior,events,root,r)
    if row.get('retry_of'):
        from scripts import qd_ed_n24_recovery as recovery
        recovery.verify_eligibility(row['n24_recovery_eligibility'],plan,primary,events,root,r)
    w.require(successes+10-index//4>=5,'N24 complete-quadruple numeric futility')
    return {'n24_cohort_id':COHORT,'n24_protocol_sha256':PROTOCOL_SHA,
        'n24_arm_role':'candidate' if row['profile']=='N24' else 'ablation_control_only' if row['profile']=='N23' else 'control',
        **({'n24_recovery_eligibility':row['n24_recovery_eligibility']} if row.get('retry_of') else {})}
