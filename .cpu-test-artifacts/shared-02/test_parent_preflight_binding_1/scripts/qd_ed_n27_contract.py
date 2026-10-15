"""Closed N27 Dev admission; root review/adoption/release are external artifacts."""
from contextlib import contextmanager
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import threading

from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n27_native as native

ROOT=Path(__file__).resolve().parents[1]
SESSION=ROOT.parent if ROOT.name=='study_worktree' else ROOT.parents[2]
RUN_DIR=SESSION/'variants/n27_feasible_ray_update'
OLD_DIR=SESSION/'variants/n26_clean_output_rbf'
SOURCE_PLAN=OLD_DIR/'plan.frozen.v1.gpu7.json'
SOURCE_PLAN_SHA='cb5fbacbf1a5fe3a77bda0de98bca3b8838474fd6ede7d82319eb35326e32d24'
PROTOCOL=RUN_DIR/'phase-b-integration-protocol-v1.md'
PROTOCOL_SHA='165d4efd83a7bf86a5bc1c42c0bea31272b69a86501ee22598bd2a1c6c9fa280'
ARITHMETIC_PROTOCOL=RUN_DIR/'independent-arithmetic-protocol-v1.md'
OBSERVABILITY=SESSION/'variants/n23_actuator_clipped_quality/timeout-observability-addendum-v2.md'
OBSERVABILITY_SHA='fa0723919c67d0417b101be2a36d9832cfaaf15e4b1c4e0cdfbf61caa43e34c6'
FINAL_REVIEW=RUN_DIR/'final-source-runtime-review-v1.json'
AUTHORITY=RUN_DIR/'adoption-v1/authority.json'
BRIDGE=RUN_DIR/'source-equivalence-bridge-v1.json'
PHASE_A='bcec3e5e37ee90374c44ca794c81b86eafcb40d6'
BASE='6026794cd5d52f3a5054bf2704ebb3c516f9f47e'
COHORT='N27_FEASIBLE_RAY_SCREEN_20261001'
PREFLIGHT='N27_TENSOR_RESOURCE_20261001'
ARMS=('C0','Q0','N26','N27')
LIMITS={'primary_cells':16,'episode_dispatches':18,'recoveries':2,'recoveries_per_cell':1,
 'maximum_local_gpu_hours':9.25,'episode_timeout_seconds':1800,'cleanup_seconds':40,'physical_gpu':7}
BASE_CAPS={'attempts':522,'gpu_hours':100.,'buckets':{'baseline':62,'development':220,'validation':180,'formal':40,'recovery':20},
 'protected_gpu_hours':{'validation':32.,'formal':12.}}
PREDECESSOR=OLD_DIR/'root-terminal-review-v1.json'
BUDGET_AUTHORITY=OLD_DIR/'budget-logical-adoption-v1/authority.json'
BUDGET_REUSE=RUN_DIR/'budget-reuse-adoption-v1/authority.json'
BACKEND_PROOF=RUN_DIR/'arithmetic-preflight/proof-v1.json'
GPU7_UUID='GPU-48473162-9548-1a19-04aa-ea86c5349187'
GPU7_PROOF='rdt-qd-ed-final-20260921T093925Z__gpu7_cuda_egl__4fafff3673e5'
WORKER_CONTRACT={'schema':'n27-same-process-native-audit-v1','arms':list(ARMS),
 'cuda_arithmetic_arms':['N26','N27'],'other_arm_backend':'cpu','timeout_includes_audit':True,
 'profile_bound_rbf_audit':True,'witness_exact_backend':'assigned_cuda'}
ref=lambda path:{'path':str(Path(path).resolve()),'sha256':w.sha(path)}
_SCOPE=None


def original_plan():
    from scripts import qd_ed_n27_bridge as bridge
    return bridge.closed_records(ROOT)['plan']


def runtime_ref():
    plan=original_plan()
    return {'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']}


def expected_rows():
    rows=original_plan()['episodes']
    w.require(len(rows)==40 and [(x['task_id'],x['profile']) for x in rows]==[(t,a) for t in range(10) for a in ('C0','Q0','N25','N26')],
              'N27 original N26 task-major identities differ')
    result=[]
    for t in range(4):
        for arm,source in zip(ARMS,rows[t*4:t*4+4]):
            row=copy.deepcopy(source)
            row.update(iteration=COHORT,profile=arm,episode_key=f'n27_screen_t{t:02d}_{arm.lower()}_20261001')
            w.require(row['split']==row['seed_block']=='dev' and row['timeout_seconds']==1800
                and row['budget_bucket']==('baseline' if arm=='C0' else 'development') and 'retry_of' not in row,'N27 original Dev row differs')
            result.append(row)
    return result


def source_paths(r):
    from scripts import qd_ed_n27_bridge as bridge
    return bridge.source_paths(Path(r['ROOT'])) | r['REQUIRED_CODE'] | w.REQUIRED_SOURCE



def imports_owned(root,r):
    root=Path(root).resolve()
    for path in (__file__,w.__file__,native.__file__,r['__file__']):
        w.require(Path(path).resolve().is_relative_to(root),'N27 adjacent-worktree module shadowing')


def final_review(source,runtime,root):
    from scripts import qd_ed_n27_bridge as bridge
    from scripts import qd_ed_n27_backend as backend
    require_protocols(root)
    bound=bridge.verify(ref(BRIDGE),source,runtime,root)
    proof=backend.verify_proof(ref(BACKEND_PROOF),source,runtime,root)
    expected={'schema':'n27-source-runtime-review-v1','disposition':'accepted','source':source,'runtime':runtime,
      'protocol':ref(PROTOCOL),'source_plan':ref(SOURCE_PLAN),'source_bridge':ref(BRIDGE),
      'predecessor':predecessor(),'backend_proof':ref(BACKEND_PROOF),
      'arithmetic_protocol':ref(ARITHMETIC_PROTOCOL),'budget_reuse':ref(BUDGET_REUSE),'no_gpu_release':True}
    w.require(w.read_ref(ref(FINAL_REVIEW))==expected and bound['new_source']==source and proof['accepted'] is True,'N27 root source review differs')
    return ref(FINAL_REVIEW)



def authority(source,runtime,root,state=None):
    record=w.read_ref(ref(AUTHORITY));budget_reuse()
    keys={'schema','cohort_id','source','runtime','protocol','final_review','budget_reuse','limits','local_gpu_hours',
          'recorded_at','authority_interpretation','predecessor','validation_authorized','formal_authorized'}
    w.require(set(record)==keys and record['schema']=='n27-screen-authority-v1' and record['cohort_id']==COHORT
        and record['source']==source and record['runtime']==runtime and record['protocol']==ref(PROTOCOL)
        and record['final_review']==final_review(source,runtime,root) and record['limits']==LIMITS
        and record['predecessor']==predecessor() and record['budget_reuse']==ref(BUDGET_REUSE)
        and record['local_gpu_hours']==9.25
        and all(isinstance(record[k],str) and record[k].strip() for k in ('recorded_at','authority_interpretation'))
        and record['validation_authorized'] is False and record['formal_authorized'] is False,'N27 finite authority differs')
    if state is not None:w.require(state.get('n27_dev_authority')==ref(AUTHORITY),'N27 authority not adopted')
    return ref(AUTHORITY)



def require_state(state,r):
    require_budget_state(state,r)
    reference=state.get('n27_dev_authority');w.require(reference==ref(AUTHORITY),'N27 adoption missing')
    record=w.read_ref(reference);authority(record['source'],record['runtime'],Path(r['ROOT']),state)



def full_capacity(state,events,resources,r):
    require_state(state,r);snap=r['budget_snapshot'](events,resources);caps=BASE_CAPS
    from scripts import qd_ed_n27_backend as backend
    backend.settled_proof(w.read_ref(ref(BACKEND_PROOF)),resources,r)
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    charged=[e for e in local if e['event']=='dispatched'];recoveries={e['attempt_id'] for e in local if e.get('retry_of')}
    spent=local_seconds(events,resources,r)/3600
    remaining={b:need-sum(e['budget_bucket']==b for e in charged) for b,need in (('baseline',4),('development',12))}
    w.require(len(charged)<=18 and len(recoveries)<=2 and all(v>=0 for v in remaining.values()),'N27 local count exceeded')
    remaining['recovery']=2-len(recoveries)
    protected_hours=sum(max(0.,h-snap['gpu_hours_by_bucket'][b]) for b,h in caps['protected_gpu_hours'].items())
    protected_attempts=sum(max(0,caps['buckets'][b]-snap['by_bucket'][b]) for b in ('validation','formal'))
    w.require(snap['running']==snap['gpu_healthcheck_inflight']==0
        and all(g[-1]['event'] in r['TERMINAL'] for g in r['event_groups'](events).values()),'N27 unsettled owner/journal')
    w.require(state['budget']['dispatched']==snap['dispatched']
        and abs(state['budget']['gpu_hours_consumed']-snap['gpu_hours_consumed'])<1e-8,'N27 state/ledger cost mismatch')
    w.require(spent<=9.25 and snap['gpu_hours_consumed']+max(0.,9.25-spent)+protected_hours<=100.+1e-9
        and all(caps['buckets'][b]-snap['by_bucket'][b]>=n for b,n in remaining.items())
        and snap['dispatched']+sum(remaining.values())+protected_attempts<=522,
        'N27 finite screen capacity borrows protected reserves')



@contextmanager
def supervised_scope(plan,root,episode_key,*,eligibility=None):
    global _SCOPE
    w.require(_SCOPE is None,'N27 nested scope')
    _SCOPE=(str(Path(root).resolve()),plan['source_commit'],episode_key,os.getpid(),threading.get_ident(),eligibility)
    try:yield
    finally:_SCOPE=None


def require_scope(plan,root,r,row=None):
    w.require(_SCOPE is not None and _SCOPE[:2]==(str(Path(root).resolve()),plan['source_commit'])
        and _SCOPE[3:5]==(os.getpid(),threading.get_ident()) and (row is None or row['episode_key']==_SCOPE[2]),
        'N27 requires exact single-cell owned scope')


def primary_row(plan,row):
    matches=[v for v in plan['episodes'] if v['episode_key']==row['episode_key']]
    w.require(len(matches)==1,'N27 unknown scientific cell');primary=matches[0]
    w.require(row==primary or (set(row)==set(primary)|{'retry_of','n27_recovery_eligibility'} and row['budget_bucket']=='recovery'
        and {k:row[k] for k in primary if k!='budget_bucket'}=={k:v for k,v in primary.items() if k!='budget_bucket'}),
        'N27 recovery row changed science')
    return primary


def effective_row(plan,row,events,root,r):
    require_scope(plan,root,r,row)
    if _SCOPE[5] is None:return row
    from scripts import qd_ed_n27_recovery as recovery
    record=recovery.verify_eligibility(_SCOPE[5],plan,row,events,root,r)
    return {**row,'budget_bucket':'recovery','retry_of':record['primary_attempt_id'],'n27_recovery_eligibility':_SCOPE[5]}


def protected_budget(state,events,resources,row,timeout,r,*,plan):
    primary_row(plan,row)
    w.require(row['iteration']==COHORT and row['profile'] in ARMS and timeout==1800,'N27 row/timeout differs')
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    w.require(sum(e['event']=='dispatched' for e in local)<18
        and local_seconds(events,resources,r)+1840<=9.25*3600,'N27 local cap; incomplete is INVALID')
    full_capacity(state,events,resources,r)



def validate_runtime(runtime,root,r):
    w.require(runtime==w.read_ref(runtime_ref()) and Path(runtime['worktree']).resolve()==Path(root).resolve()
        and runtime.get('schema')=='qd-ed-runtime-setup-v1' and r['runtime_gpu'](runtime)==7
        and runtime['gpu_mapping']['uuid']==GPU7_UUID and runtime['gpu_mapping']['egl_device_index']==4
        and runtime.get('cuda_egl_verified') is True and runtime.get('cuda_egl_probe',{}).get('resource_id')==GPU7_PROOF
        and runtime.get('stage_recovered_error_condition')==r['E2_STAGE_CONDITION']
        and runtime.get('stage_engineering_condition')==r['n4e1_support']().engineering_condition()
        and runtime['frozen_stage_provider'].get('allow_recovered_error_events') is True,
        'N27 frozen runtime/GPU/provider differs')
    r['verify_files'](runtime['files'],allowed_roots=(Path(root),Path(runtime['worktree']),runtime['artifact_root']))


def metadata(source,root):
    runtime=runtime_ref()
    return {'schema':'n27-feasible-ray-screen-v1','cohort_id':COHORT,'limits':LIMITS,
        'protocol':ref(PROTOCOL),'source_plan':ref(SOURCE_PLAN),'timeout_observability':ref(OBSERVABILITY),
        'final_review':final_review(source,runtime,root),'authority':authority(source,runtime,root),
        'predecessor':predecessor(),'budget_reuse':ref(BUDGET_REUSE),
        'worker_audit':WORKER_CONTRACT,'n26_role':'control_only_no_promotion','early_stop':'none_full_sixteen_required'}


def validate_contract(plan,manifest,runtime,seeds,root,r):
    imports_owned(root,r)
    source=w.source_record(root,[v['path'] for v in plan['code_files']])
    w.require(source['commit']==plan['source_commit'] and source['files']==plan['code_files']
        and source_paths(r)<={v['path'] for v in plan['code_files']},'N27 complete committed source missing')
    w.require(plan.get('n27_cohort')==metadata(source,root) and plan['episodes']==expected_rows()
        and set(plan['candidate_profiles'])=={'N26','N27'} and set(manifest['profiles'])==set(ARMS)
        and plan.get('phase_authorization')=={'dev':True,'validation':False,'formal':False}
        and plan.get('stage_condition')==r['E2_STAGE_CONDITION']
        and not any(k.startswith(('n7_','n9_','n11_','n17_','n18_','n19_','n20_','n21_','n22_','n23_','n24_','n25_','n26_')) for k in plan),
        'N27 closed prospective matrix/phase differs')
    for arm in ('N26','N27'):
        path=Path(root)/f'configs/qd_ed_final/candidate_{arm.lower()}.json'
        w.require(plan['candidate_profiles'][arm]==ref(path) and str(path.relative_to(root)) in plan['scientific_config_files'],
            'N27 profile fingerprint missing')
    n26=manifest['profiles']['N26']['resolved_eds_config'];n27=manifest['profiles']['N27']['resolved_eds_config']
    w.require(n27=={**n26,'diversity_update_mode':'feasible_ray_v1'},'N27 sole science delta differs')
    w.require({'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']}==runtime_ref(),'N27 runtime ref differs')
    validate_runtime(runtime,root,r);require_state(r['read_state'](Path(root)/'research-state.yaml'),r)


def validate_worker_context(context,argv,root,output,plan,runtime):
    w.require(plan.get('frozen') is True and plan.get('n27_cohort',{}).get('worker_audit')==WORKER_CONTRACT
        and set(plan.get('candidate_profiles',{}))=={'N26','N27'}
        and not any(k.startswith(('n25_','n26_','n23_','n24_')) for k in plan)
        and plan['worktree']==str(root) and context['profile'] in ARMS
        and output==Path(plan['artifact_root']).resolve()/'attempts'/context['attempt_id']
        and context['runtime']=={'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']},
        'N27 worker frozen plan/runtime differs')
    rows=[r for r in plan['episodes'] if r['episode_key']==context['episode_key']]
    w.require(len(rows)==1 and rows[0]['profile']==context['profile'] and rows[0]['split']=='dev'
        and rows[0]['iteration']==COHORT and rows[0]['timeout_seconds']==1800
        and context['source']['commit']==plan['source_commit'] and context['source']['files']==plan['code_files'],
        'N27 worker row/source differs')
    w.verify_source(root,context['source'])
    w.require(w.cuda_binding(runtime)['physical_gpu']==7,'N27 worker GPU differs')
    return root,output,runtime


def read_worker_report(output,r):
    return w.verify_receipt(Path(output)/'n23-worker-context.json',r['read_json'](Path(output)/'process.json'))


def accepted_cell(plan,row,events,root,r):
    from scripts import qd_ed_n27_recovery as recovery
    groups=list(r['event_groups']([e for e in events if e.get('identity',{}).get('iteration')==COHORT
        and e.get('episode_key')==row['episode_key']]).values())
    w.require(1<=len(groups)<=2,'N27 missing/duplicate cell')
    first=groups[0][-1];w.require(groups[0][0].get('retry_of') is None and first['event'] in r['TERMINAL'],'N27 primary unsettled')
    final=first
    if len(groups)==2:
        final=groups[1][-1];reference=groups[1][0].get('n27_recovery_eligibility')
        w.require(first.get('outcome_valid') is False and final.get('retry_of')==first['attempt_id']
            and final['budget_bucket']=='recovery' and reference is not None,'N27 first-valid lineage differs')
        boundary=next(i for i,e in enumerate(events) if e['attempt_id']==final['attempt_id'])
        recovery.verify_eligibility(reference,plan,row,events[:boundary],root,r)
    w.require(final['event']=='valid' and final.get('outcome_valid') is True
        and final.get('required_cost_telemetry_complete') is True,'N27 invalid primary/recovery cannot count')
    context=w.read_ref(ref(Path(final['output_dir'])/'n23-worker-context.json'))
    recovery.terminal_binding(final,row,plan,context['plan'],r)
    w.require(w.read_ref(context['plan'])==plan and w.read_ref(ref(Path(final['output_dir'])/'attempt-result.json'))==final
        and final.get('n23_worker_receipt')==ref(Path(final['output_dir'])/'eds_eval/in-worker-audit-receipt.json'),
        'N27 accepted terminal/plan/receipt differs')
    report=read_worker_report(final['output_dir'],r)
    w.require(type(final.get('guided_chunks')) is int,'N27 accepted guided count missing')
    native.from_output(row['profile'],final['output_dir'],report,final['guided_chunks'])
    return final


def admission(plan,runtime,row,events,resources,root,r):
    primary=primary_row(plan,row);index=plan['episodes'].index(primary)
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    allowed={v['episode_key'] for v in plan['episodes'][:index]}|({row['episode_key']} if row.get('retry_of') else set())
    w.require(all(e.get('episode_key') in allowed for e in local),'N27 exact prefix required')
    for prior in plan['episodes'][:index]:accepted_cell(plan,prior,events,root,r)
    if row.get('retry_of'):
        from scripts import qd_ed_n27_recovery as recovery
        recovery.verify_eligibility(row['n27_recovery_eligibility'],plan,primary,events,root,r)
    return {'n27_cohort_id':COHORT,'n27_protocol_sha256':PROTOCOL_SHA,
        'n27_arm_role':'candidate' if row['profile']=='N27' else 'control',
        **({'n27_recovery_eligibility':row['n27_recovery_eligibility']} if row.get('retry_of') else {})}


def require_protocols(root):
    w.require(w.sha(PROTOCOL)==PROTOCOL_SHA,'N27 protocol drift')
    for name,path in (('phase-b-integration-protocol-v1.md',PROTOCOL),('independent-arithmetic-protocol-v1.md',ARITHMETIC_PROTOCOL)):
        w.require((Path(root)/'experiments/qd_ed_n27'/name).read_bytes()==Path(path).read_bytes(),'N27 tracked protocol drift')
    w.require(w.sha(OBSERVABILITY)==OBSERVABILITY_SHA,'N27 unchanged timeout observability drift')


def predecessor():
    from scripts import qd_ed_n27_bridge as bridge
    bridge.closed_records(ROOT)
    return ref(PREDECESSOR)


def budget_authority():
    from scripts import qd_ed_n27_bridge as bridge
    record=bridge.closed_records(ROOT)['budget']
    w.require(record.get('caps')==BASE_CAPS,'N27 existing finite caps differ')
    return record


def require_budget_state(state,r):
    authority=budget_authority();budget_reuse();caps=authority['caps'];budget=state['budget']
    resource=state.get('resource_isolation',{})
    w.require(resource.get('status')=='ACTIVE' and resource.get('validation_status')=='PASS'
        and resource.get('private_budget') is True and state.get('max_concurrent_gpu_workers')==1
        and not state.get('external_resource_hold',{}).get('do_not_auto_resume',False)
        and budget.get('gpu_hour_reservations')==caps['protected_gpu_hours']
        and state.get('n26_budget_authority')==ref(BUDGET_AUTHORITY)
        and state.get('n27_budget_reuse_authority')==ref(BUDGET_REUSE)
        and budget['max_episode_attempts']==caps['attempts'] and budget['max_gpu_hours']==100.
        and budget['reserved']==caps['buckets'] and budget['amendment']==authority['amendment']
        and r['authorized_gpu'](state)==7,'N27 exact finite budget not adopted')


def expand_candidate(candidate,baseline,r):
    path=Path(r['ROOT'])/'configs/qd_ed_final/candidate_n27.json'
    w.require(candidate==r['read_json'](path) and candidate['algorithm_contract']=='n27_feasible_ray_update_v1'
        and candidate['baseline_reference']=='N26','N27 closed candidate differs')
    parent=candidate['parent_candidate'];parent_path=Path(r['ROOT'])/'configs/qd_ed_final/candidate_n26.json'
    w.require(parent=={'path':'configs/qd_ed_final/candidate_n26.json','sha256':w.sha(parent_path)},'N27 parent differs')
    old=r['read_json'](parent_path);modes={'diversity_update_mode':'feasible_ray_v1'}
    w.require(candidate['profile']=={**old['profile'],**modes} and candidate['only_algorithm_change']=={
        k:{'before':'legacy_additive','after':v} for k,v in modes.items()},'N27 scientific delta differs')
    result=r['expand_candidate']('N26',old,baseline)
    result['historical_label']='N27';result['restored_profile']=copy.deepcopy(candidate['profile'])
    for k,v in modes.items():result['resolved_eds_config'][k]=v;result['static_override_values']['main.eds_config.'+k]=v
    result['hydra_overrides']=[f'{k}={r["hydra"](v)}' for k,v in result['static_override_values'].items()]
    return result


def budget_reuse():
    record=w.read_ref(ref(BUDGET_REUSE))
    keys={'schema','existing_budget_authority','caps','protocol','predecessor','local_gpu_hours','limits',
          'recorded_at','authority_interpretation','validation_authorized','formal_authorized'}
    w.require(set(record)==keys and record['schema']=='n27-finite-budget-reuse-v1'
        and record['existing_budget_authority']==ref(BUDGET_AUTHORITY) and record['caps']==BASE_CAPS
        and record['protocol']==ref(PROTOCOL) and record['predecessor']==predecessor()
        and record['local_gpu_hours']==9.25 and record['limits']==LIMITS
        and record['validation_authorized'] is False and record['formal_authorized'] is False
        and all(isinstance(record[k],str) and record[k].strip() for k in ('recorded_at','authority_interpretation')),
        'N27 root finite reuse authority absent/different')
    return ref(BUDGET_REUSE)


def local_seconds(events,resources,r):
    episodes=[e for e in events if e.get('identity',{}).get('iteration')==COHORT and e['event'] in r['TERMINAL']]
    health=[e for e in resources if e.get('kind')=='n27_tensor_arithmetic_v1' and e['event'] in {'completed','aborted'}]
    values=[e.get('gpu_process_wall_seconds') for e in episodes+health]
    w.require(all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in values),'N27 local costs incomplete')
    return sum(values)
