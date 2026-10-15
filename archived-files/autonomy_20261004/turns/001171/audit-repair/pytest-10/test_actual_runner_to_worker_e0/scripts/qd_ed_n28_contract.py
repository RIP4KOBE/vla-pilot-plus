"""Closed N28 Dev admission; root review/adoption/release are external artifacts."""
from contextlib import contextmanager
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import threading

from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n28_native as native

ROOT=Path(__file__).resolve().parents[1]
SESSION=ROOT.parent if ROOT.name=='study_worktree' else ROOT.parents[2]
RUN_DIR=SESSION/'variants/n28_parent_before_renoise'
OLD_DIR=SESSION/'variants/n27_feasible_ray_update'
SOURCE_PLAN=OLD_DIR/'plan.frozen.v1.gpu7.json'
SOURCE_PLAN_SHA='8632a2f39f0cde0c198f358c1b1700907707d3e0474a75df6b9296cf18f7441f'
PROTOCOL=RUN_DIR/'execution-integration-cpu-scope-v1.md'
PROTOCOL_SHA='ab228f33e752a5634103c6294cabcf126640e7ff88e90694c625f741fe96e5db'
ARITHMETIC_PROTOCOL=RUN_DIR/'independent-arithmetic-protocol-v1.md'
OBSERVABILITY=SESSION/'variants/n23_actuator_clipped_quality/timeout-observability-addendum-v2.md'
OBSERVABILITY_SHA='fa0723919c67d0417b101be2a36d9832cfaaf15e4b1c4e0cdfbf61caa43e34c6'
FINAL_REVIEW=RUN_DIR/'final-source-runtime-review-v1.json'
AUTHORITY=RUN_DIR/'adoption-v1/authority.json'
BRIDGE=RUN_DIR/'source-equivalence-bridge-v1.json'
PHASE_A='85154b4dcb43046a2fcf2df4e8179b45b58dd2b4'
BASE='e21d48ab33dbd3aca017349b6004c2ba7d981493'
COHORT='N28_PARENT_BEFORE_RENOISE_SCREEN_20261001'
PREFLIGHT='N28_TENSOR_RESOURCE_20261001'
ARMS=('C0','Q0','N27','N28')
LIMITS={'primary_cells':16,'episode_dispatches':16,'recoveries':0,'recoveries_per_cell':0,
 'maximum_local_gpu_hours':8.25,'episode_timeout_seconds':1800,'cleanup_seconds':40,'physical_gpu':7}
BASE_CAPS={'attempts':538,'gpu_hours':100.,'buckets':{'baseline':66,'development':232,'validation':180,'formal':40,'recovery':20},
 'protected_gpu_hours':{'validation':32.,'formal':12.}}
PREDECESSOR=OLD_DIR/'hydra-continuation-v1/root-terminal-review-v1.json'
BUDGET_AUTHORITY=RUN_DIR/'budget-adoption-v1/authority.json'
BUDGET_REUSE=BUDGET_AUTHORITY
BACKEND_PROOF=RUN_DIR/'arithmetic-preflight/proof-v1.json'
GPU7_UUID='GPU-48473162-9548-1a19-04aa-ea86c5349187'
GPU7_PROOF='rdt-qd-ed-final-20260921T093925Z__gpu7_cuda_egl__4fafff3673e5'
WORKER_CONTRACT={'schema':'n28-same-process-native-audit-v1','arms':list(ARMS),
 'cuda_arithmetic_arms':['N27','N28'],'other_arm_backend':'cpu','timeout_includes_audit':True,
 'profile_bound_rbf_audit':True,'witness_exact_backend':'assigned_cuda'}
ref=lambda path:{'path':str(Path(path).resolve()),'sha256':w.sha(path)}
_SCOPE=None


def original_plan():
    from scripts import qd_ed_n28_bridge as bridge
    return bridge.closed_records(ROOT)['plan']


def runtime_ref():
    plan=original_plan()
    return {'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']}


def expected_rows():
    rows=original_plan()['episodes']
    w.require(len(rows)==16 and [(x['task_id'],x['profile']) for x in rows]==[(t,a) for t in range(4) for a in ('C0','Q0','N26','N27')],
        'N28 original task-major Dev mapping differs')
    result=[]
    for t in range(4):
        for arm,old in zip(ARMS,rows[t*4:t*4+4]):
            row=copy.deepcopy(old);row.update(iteration=COHORT,profile=arm,episode_key=f'n28_screen_t{t:02d}_{arm.lower()}_20261001')
            w.require(row['split']==row['seed_block']=='dev' and row['timeout_seconds']==1800
                and row['budget_bucket']==('baseline' if arm=='C0' else 'development') and 'retry_of' not in row,'N28 source mapping differs')
            result.append(row)
    return result


def source_paths(r):
    from scripts import qd_ed_n28_bridge as bridge
    return bridge.source_paths(Path(r['ROOT'])) | r['REQUIRED_CODE'] | w.REQUIRED_SOURCE



def imports_owned(root,r):
    root=Path(root).resolve()
    for path in (__file__,w.__file__,native.__file__,r['__file__']):
        w.require(Path(path).resolve().is_relative_to(root),'N28 adjacent-worktree module shadowing')


def final_review(source,runtime,root):
    from scripts import qd_ed_n28_bridge as bridge
    from scripts import qd_ed_n28_backend as backend
    require_protocols(root)
    bound=bridge.verify(ref(BRIDGE),source,runtime,root)
    proof=backend.verify_proof(ref(BACKEND_PROOF),source,runtime,root)
    expected={'schema':'n28-source-runtime-review-v1','disposition':'accepted','source':source,'runtime':runtime,
      'protocol':ref(PROTOCOL),'source_plan':ref(SOURCE_PLAN),'source_bridge':ref(BRIDGE),
      'predecessor':predecessor(),'backend_proof':ref(BACKEND_PROOF),
      'arithmetic_protocol':ref(ARITHMETIC_PROTOCOL),'budget_reuse':ref(BUDGET_REUSE),'no_gpu_release':True}
    w.require(w.read_ref(ref(FINAL_REVIEW))==expected and bound['new_source']==source and proof['accepted'] is True,'N28 root source review differs')
    return ref(FINAL_REVIEW)



def authority(source,runtime,root,state=None):
    record=w.read_ref(ref(AUTHORITY));budget_reuse()
    keys={'schema','cohort_id','source','runtime','protocol','final_review','budget_reuse','limits','local_gpu_hours',
          'recorded_at','authority_interpretation','predecessor','validation_authorized','formal_authorized'}
    w.require(set(record)==keys and record['schema']=='n28-screen-authority-v1' and record['cohort_id']==COHORT
        and record['source']==source and record['runtime']==runtime and record['protocol']==ref(PROTOCOL)
        and record['final_review']==final_review(source,runtime,root) and record['limits']==LIMITS
        and record['predecessor']==predecessor() and record['budget_reuse']==ref(BUDGET_REUSE)
        and record['local_gpu_hours']==8.25
        and all(isinstance(record[k],str) and record[k].strip() for k in ('recorded_at','authority_interpretation'))
        and record['validation_authorized'] is False and record['formal_authorized'] is False,'N28 finite authority differs')
    if state is not None:w.require(state.get('n28_dev_authority')==ref(AUTHORITY),'N28 authority not adopted')
    return ref(AUTHORITY)



def require_state(state,r):
    require_budget_state(state,r)
    reference=state.get('n28_dev_authority');w.require(reference==ref(AUTHORITY),'N28 adoption missing')
    record=w.read_ref(reference);authority(record['source'],record['runtime'],Path(r['ROOT']),state)



def full_capacity(state,events,resources,r):
    require_state(state,r);snap=r['budget_snapshot'](events,resources);caps=BASE_CAPS
    from scripts import qd_ed_n28_backend as backend
    backend.settled_proof(w.read_ref(ref(BACKEND_PROOF)),resources,r)
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    charged=[e for e in local if e['event']=='dispatched'];spent=local_seconds(events,resources,r)/3600
    remaining={b:need-sum(e['budget_bucket']==b for e in charged) for b,need in (('baseline',4),('development',12))}
    w.require(len(charged)<=16 and not any(e.get('retry_of') for e in local) and all(v>=0 for v in remaining.values()),'N28 count/retry limit')
    protected_hours=sum(max(0.,h-snap['gpu_hours_by_bucket'][b]) for b,h in caps['protected_gpu_hours'].items())
    protected_attempts=sum(max(0,caps['buckets'][b]-snap['by_bucket'][b]) for b in ('validation','formal'))
    w.require(snap['running']==snap['gpu_healthcheck_inflight']==0
        and all(g[-1]['event'] in r['TERMINAL'] for g in r['event_groups'](events).values()),'N28 unsettled owner/journal')
    w.require(state['budget']['dispatched']==snap['dispatched']
        and abs(state['budget']['gpu_hours_consumed']-snap['gpu_hours_consumed'])<1e-8,'N28 state/ledger mismatch')
    w.require(spent<=8.25 and snap['gpu_hours_consumed']+max(0.,8.25-spent)+protected_hours<=100.+1e-9
        and all(caps['buckets'][b]-snap['by_bucket'][b]>=n for b,n in remaining.items())
        and snap['dispatched']+sum(remaining.values())+protected_attempts<=538,'N28 finite full screen exceeds protected capacity')



@contextmanager
def supervised_scope(plan,root,episode_key):
    global _SCOPE
    w.require(_SCOPE is None,'N28 nested scope')
    _SCOPE=(str(Path(root).resolve()),plan['source_commit'],episode_key,os.getpid(),threading.get_ident())
    try:yield
    finally:_SCOPE=None


def require_scope(plan,root,r,row=None):
    w.require(_SCOPE is not None and _SCOPE[:2]==(str(Path(root).resolve()),plan['source_commit'])
        and _SCOPE[3:5]==(os.getpid(),threading.get_ident()) and (row is None or row['episode_key']==_SCOPE[2]),
        'N28 requires exact single-cell owned scope')


def primary_row(plan,row):
    w.require(row in plan['episodes'] and not any('retry' in k or 'recovery' in k for k in row),'N28 exact primary only, no retry')
    return row


def effective_row(plan,row,events,root,r):
    require_scope(plan,root,r,row);return primary_row(plan,row)


def protected_budget(state,events,resources,row,timeout,r,*,plan):
    primary_row(plan,row)
    w.require(row['iteration']==COHORT and row['profile'] in ARMS and timeout==1800,'N28 row/timeout differs')
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    w.require(sum(e['event']=='dispatched' for e in local)<16 and local_seconds(events,resources,r)+1840<=8.25*3600,
        'N28 local cap reached; incomplete is INVALID')
    full_capacity(state,events,resources,r)



def validate_runtime(runtime,root,r):
    w.require(runtime==w.read_ref(runtime_ref()) and Path(runtime['worktree']).resolve()==Path(root).resolve()
        and runtime.get('schema')=='qd-ed-runtime-setup-v1' and r['runtime_gpu'](runtime)==7
        and runtime['gpu_mapping']['uuid']==GPU7_UUID and runtime['gpu_mapping']['egl_device_index']==4
        and runtime.get('cuda_egl_verified') is True and runtime.get('cuda_egl_probe',{}).get('resource_id')==GPU7_PROOF
        and runtime.get('stage_recovered_error_condition')==r['E2_STAGE_CONDITION']
        and runtime.get('stage_engineering_condition')==r['n4e1_support']().engineering_condition()
        and runtime['frozen_stage_provider'].get('allow_recovered_error_events') is True,
        'N28 frozen runtime/GPU/provider differs')
    r['verify_files'](runtime['files'],allowed_roots=(Path(root),Path(runtime['worktree']),runtime['artifact_root']))


def metadata(source,root):
    runtime=runtime_ref()
    return {'schema':'n28-parent-before-renoise-screen-v1','cohort_id':COHORT,'limits':LIMITS,
        'protocol':ref(PROTOCOL),'source_plan':ref(SOURCE_PLAN),'timeout_observability':ref(OBSERVABILITY),
        'final_review':final_review(source,runtime,root),'authority':authority(source,runtime,root),
        'predecessor':predecessor(),'budget_reuse':ref(BUDGET_REUSE),
        'worker_audit':WORKER_CONTRACT,'n27_role':'control_only_no_promotion','early_stop':'none_full_sixteen_required'}


def validate_contract(plan,manifest,runtime,seeds,root,r):
    imports_owned(root,r)
    source=w.source_record(root,[v['path'] for v in plan['code_files']])
    w.require(source['commit']==plan['source_commit'] and source['files']==plan['code_files']
        and source_paths(r)<={v['path'] for v in plan['code_files']},'N28 complete committed source missing')
    w.require(plan.get('n28_cohort')==metadata(source,root) and plan['episodes']==expected_rows()
        and set(plan['candidate_profiles'])=={'N27','N28'} and set(manifest['profiles'])==set(ARMS)
        and plan.get('phase_authorization')=={'dev':True,'validation':False,'formal':False}
        and plan.get('stage_condition')==r['E2_STAGE_CONDITION']
        and not any(k.startswith(('n7_','n9_','n11_','n17_','n18_','n19_','n20_','n21_','n22_','n23_','n24_','n25_','n26_','n27_')) for k in plan),
        'N28 closed prospective matrix/phase differs')
    for arm in ('N27','N28'):
        path=Path(root)/f'configs/qd_ed_final/candidate_{arm.lower()}.json'
        w.require(plan['candidate_profiles'][arm]==ref(path) and str(path.relative_to(root)) in plan['scientific_config_files'],
            'N28 profile fingerprint missing')
    n27=manifest['profiles']['N27']['resolved_eds_config'];n28=manifest['profiles']['N28']['resolved_eds_config']
    w.require(n28=={**n27,'rollout_diversity_placement':'parent_before_renoise_v1'},'N28 sole science delta differs')
    w.require({'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']}==runtime_ref(),'N28 runtime ref differs')
    artifact=(RUN_DIR/'artifacts')
    w.require(artifact.is_symlink() and artifact.resolve()==(SESSION/'artifacts/variants/n28_parent_before_renoise').resolve()
        and Path(plan['artifact_root']).resolve()==artifact.resolve(),'N28 variant-owned artifact root differs')
    validate_runtime(runtime,root,r);require_state(r['read_state'](Path(root)/'research-state.yaml'),r)


def validate_worker_context(context,argv,root,output,plan,runtime):
    w.require(plan.get('frozen') is True and plan.get('n28_cohort',{}).get('worker_audit')==WORKER_CONTRACT
        and set(plan.get('candidate_profiles',{}))=={'N27','N28'}
        and not any(k.startswith(('n25_','n26_','n27_','n23_','n24_')) for k in plan)
        and plan['worktree']==str(root) and context['profile'] in ARMS
        and output==Path(plan['artifact_root']).resolve()/'attempts'/context['attempt_id']
        and context['runtime']=={'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']},
        'N28 worker frozen plan/runtime differs')
    rows=[r for r in plan['episodes'] if r['episode_key']==context['episode_key']]
    w.require(len(rows)==1 and rows[0]['profile']==context['profile'] and rows[0]['split']=='dev'
        and rows[0]['iteration']==COHORT and rows[0]['timeout_seconds']==1800
        and context['source']['commit']==plan['source_commit'] and context['source']['files']==plan['code_files'],
        'N28 worker row/source differs')
    w.verify_source(root,context['source'])
    w.require(w.cuda_binding(runtime)['physical_gpu']==7,'N28 worker GPU differs')
    return root,output,runtime


def read_worker_report(output,r):
    return w.verify_receipt(Path(output)/'n23-worker-context.json',r['read_json'](Path(output)/'process.json'))


def accepted_cell(plan,row,events,root,r):
    groups=list(r['event_groups']([e for e in events if e.get('identity',{}).get('iteration')==COHORT
        and e.get('episode_key')==row['episode_key']]).values())
    w.require(len(groups)==1 and [e['event'] for e in groups[0]]==['reserved','dispatched','valid']
        and not any(e.get('retry_of') for e in groups[0]),'N28 missing/duplicate/retry cell')
    final=groups[0][-1]
    w.require(final.get('outcome_valid') is True and final.get('required_cost_telemetry_complete') is True,'N28 invalid cannot count')
    output=Path(final['output_dir']);context=w.read_ref(ref(output/'n23-worker-context.json'))
    w.require(final.get('identity')==r['episode_identity'](row) and final.get('episode_key')==row['episode_key']
        and final.get('source_commit')==plan['source_commit'] and final.get('plan_sha256')==context['plan']['sha256']
        and final.get('profile_manifest_sha256')==plan['profiles_sha256']
        and final.get('runtime_manifest_sha256')==plan['runtime_manifest_sha256']
        and final.get('runtime_inventory_sha256')==plan['runtime_inventory_sha256']
        and final.get('init_row_sha256')==row['init_row_sha256'] and final.get('physical_gpu')==7,
        'N28 terminal source/plan/runtime/profile/identity differs')
    r['owned'](final['output_dir'],plan['artifact_root'])
    w.require(w.read_ref(context['plan'])==plan and w.read_ref(ref(output/'attempt-result.json'))==final
        and final.get('n23_worker_receipt')==ref(output/'eds_eval/in-worker-audit-receipt.json'),'N28 accepted identity differs')
    report=read_worker_report(output,r);w.require(type(final.get('guided_chunks')) is int,'N28 guided count unknown')
    native.from_output(row['profile'],output,report,final['guided_chunks']);return final


def admission(plan,runtime,row,events,resources,root,r):
    primary=primary_row(plan,row);index=plan['episodes'].index(primary)
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    allowed={v['episode_key'] for v in plan['episodes'][:index]}
    w.require(all(e.get('episode_key') in allowed for e in local),'N28 exact untouched next prefix required')
    for prior in plan['episodes'][:index]:accepted_cell(plan,prior,events,root,r)
    return {'n28_cohort_id':COHORT,'n28_protocol_sha256':PROTOCOL_SHA,'n28_arm_role':'candidate' if row['profile']=='N28' else 'control'}


def require_protocols(root):
    w.require(w.sha(PROTOCOL)==PROTOCOL_SHA,'N28 frozen protocol drift')
    for name,path in (('execution-integration-cpu-scope-v1.md',PROTOCOL),('independent-arithmetic-protocol-v1.md',ARITHMETIC_PROTOCOL)):
        w.require((Path(root)/'experiments/qd_ed_n28'/name).read_bytes()==Path(path).read_bytes(),'N28 tracked protocol drift')
    w.require(w.sha(OBSERVABILITY)==OBSERVABILITY_SHA,'N28 unchanged observability drift')


def predecessor():
    from scripts import qd_ed_n28_bridge as bridge
    bridge.closed_records(ROOT)
    return ref(PREDECESSOR)


def budget_authority():
    record=w.read_ref(ref(BUDGET_AUTHORITY))
    w.require(set(record)=={'schema','caps','protocol','predecessor','limits','local_gpu_hours','amendment','recorded_at',
        'authority_interpretation','validation_authorized','formal_authorized'} and record['schema']=='n28-finite-budget-authority-v1'
        and record['caps']==BASE_CAPS and record['protocol']==ref(PROTOCOL) and record['predecessor']==predecessor()
        and record['limits']==LIMITS and record['local_gpu_hours']==8.25 and isinstance(record['amendment'],dict)
        and bool(record['amendment']) and record['validation_authorized'] is False and record['formal_authorized'] is False
        and all(isinstance(record[k],str) and record[k].strip() for k in ('recorded_at','authority_interpretation')),
        'N28 finite budget amendment missing/different')
    return record


def require_budget_state(state,r):
    authority=budget_authority();caps=authority['caps'];budget=state['budget'];resource=state.get('resource_isolation',{})
    w.require(resource.get('status')=='ACTIVE' and resource.get('validation_status')=='PASS' and resource.get('private_budget') is True
        and state.get('max_concurrent_gpu_workers')==1 and not state.get('external_resource_hold',{}).get('do_not_auto_resume',False)
        and budget.get('gpu_hour_reservations')==caps['protected_gpu_hours'] and state.get('n28_budget_authority')==ref(BUDGET_AUTHORITY)
        and budget['max_episode_attempts']==538 and budget['max_gpu_hours']==100. and budget['reserved']==caps['buckets']
        and budget['amendment']==authority['amendment'] and r['authorized_gpu'](state)==7,'N28 finite budget/resource not adopted')


def expand_candidate(candidate,baseline,r):
    path=Path(r['ROOT'])/'configs/qd_ed_final/candidate_n28.json'
    w.require(candidate==r['read_json'](path) and candidate['algorithm_contract']=='n28_parent_before_renoise_v1'
        and candidate['baseline_reference']=='N27','N28 closed candidate differs')
    parent=Path(r['ROOT'])/'configs/qd_ed_final/candidate_n27.json'
    w.require(candidate['parent_candidate']=={'path':'configs/qd_ed_final/candidate_n27.json','sha256':w.sha(parent)},'N28 parent differs')
    old=r['read_json'](parent);modes={'rollout_diversity_placement':'parent_before_renoise_v1'}
    w.require(candidate['profile']=={**old['profile'],**modes} and candidate['only_algorithm_change']=={
        'rollout_diversity_placement':{'before':'model_output','after':'parent_before_renoise_v1'}},'N28 sole science delta differs')
    result=r['expand_candidate']('N27',old,baseline)
    result['resolved_eds_config'].update(modes);result['static_override_values'].update({'main.eds_config.'+k:v for k,v in modes.items()})
    result['hydra_overrides']=[f'{k}={r["hydra"](v)}' for k,v in result['static_override_values'].items()]
    return result


def budget_reuse():
    budget_authority();return ref(BUDGET_AUTHORITY)


def local_seconds(events,resources,r):
    episodes=[e for e in events if e.get('identity',{}).get('iteration')==COHORT and e['event'] in r['TERMINAL']]
    health=[e for e in resources if e.get('kind')=='n28_tensor_arithmetic_v1' and e['event'] in {'completed','aborted'}]
    values=[e.get('gpu_process_wall_seconds') for e in episodes+health]
    w.require(all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in values),'N28 local costs incomplete')
    return sum(values)


def check_retry(events,row,r):
    w.require(row.get('iteration')==COHORT and not any('retry' in k or 'recovery' in k for k in row),'N28 no retry fields')
    w.require(not any(e.get('identity',{}).get('iteration')==COHORT and e.get('episode_key')==row['episode_key'] for e in events),
        'N28 cell already reserved; no restart/retry')
