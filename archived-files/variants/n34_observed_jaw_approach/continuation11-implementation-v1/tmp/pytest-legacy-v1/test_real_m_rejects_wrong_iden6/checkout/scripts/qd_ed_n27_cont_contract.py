"""One named startup replacement, twelve untouched rows; no generic retry."""
import copy
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from scripts import qd_ed_n23_worker as w,qd_ed_n27_contract as old,qd_ed_n27_native as native
from scripts import qd_ed_n27_cont_history as h,qd_ed_n27_cont_bridge as bridge
ROOT=Path(__file__).resolve().parents[1]
COHORT=h.COHORT;ARMS=h.ARMS;CAPS=old.BASE_CAPS;WORKER_CONTRACT=old.WORKER_CONTRACT
RUN_DIR=old.RUN_DIR/'hydra-continuation-v1'
PROTOCOL=old.RUN_DIR/'hydra-config-repair-preparation-v1/root-continuation-design-v1.md'
PROTOCOL_SHA='d4316e941ed67c246823bfc7143fadf8d50e4cc86cce57b5ac55bac413a71fc0'
SEAL=RUN_DIR/'history-seal-v1.json';SEAL_REVIEW=RUN_DIR/'root-seal-review-v1.json'
BRIDGE=RUN_DIR/'source-bridge-v1.json';FINAL_REVIEW=RUN_DIR/'final-source-runtime-review-v1.json'
AUTHORITY=RUN_DIR/'adoption-v1/authority.json';PLAN=RUN_DIR/'plan.frozen.v1.gpu7.json'
LIMITS={'new_dispatches':13,'combined_dispatches':17,'named_retries':1,'additional_retries':0,
 'episode_timeout_seconds':1800,'cleanup_seconds':40,'combined_local_gpu_hours':9.25,'physical_gpu':7}
ref=h.ref;read_worker_report=old.read_worker_report;_SCOPE=None

def history():
    seal=h.verify(h.read(ref(SEAL)));review=h.read(ref(SEAL_REVIEW))
    w.require(w.sha(PROTOCOL)==PROTOCOL_SHA and (ROOT/bridge.DOC/'protocol-v1.md').read_bytes()==PROTOCOL.read_bytes(),'continuation protocol changed')
    w.require(review=={'schema':'n27-hydra-root-seal-review-v1','accepted':True,'seal':ref(SEAL),'protocol':ref(PROTOCOL),
        'root_terminal_review':seal['root_terminal_review'],'startup_classification':seal['startup_classification'],
        'original_disposition':'INVALID_OR_INTERRUPTED','old_source':seal['original_source'],
        'historical_backend_proof':seal['historical_backend_proof'],'native_receipts_attested_not_replayed':True,
        'cleanup_complete':True,'gpu_authorized':False},'exact independent root seal review required')
    # Only bounded control JSON refs are followed. Never follow nested attempt/tensor/Stage refs.
    prior=h.read(seal['original_plan']);w.require(prior==seal['original_plan_content'],'sealed plan bytes/content mismatch')
    h.read(seal['root_terminal_review']);h.read(seal['startup_classification'])
    h.read(seal['original_result']);h.read(seal['historical_backend_proof']);h.read(seal['original_source_review']);h.read(seal['original_authority'])
    return seal

def rows(seal):
    result=[]
    for index,original in enumerate(seal['original_plan_content']['episodes'][3:],3):
        row=copy.deepcopy(original);row.update(iteration=COHORT,episode_key=original['episode_key']+'_hydra1')
        if index==3:row.update(budget_bucket='recovery',retry_of=h.FAILED,n27_named_hydra_proof=ref(SEAL))
        result.append(row)
    w.require(len(result)==13,'exact thirteen remaining rows');return result

def source_paths(r):return bridge.source_paths(r['ROOT'])

def final_review(source,runtime,root):
    seal=history();expected=bridge.build(source,seal,root)
    w.require(runtime==seal['runtime'] and h.read(ref(BRIDGE))==expected,'reviewed source/runtime bridge missing')
    review={'schema':'n27-hydra-source-runtime-review-v1','accepted':True,'source':source,'runtime':runtime,'protocol':ref(PROTOCOL),
        'seal':ref(SEAL),'root_seal_review':ref(SEAL_REVIEW),'source_bridge':ref(BRIDGE),
        'historical_backend_proof':seal['historical_backend_proof'],'no_new_preflight':True,'gpu_authorized':False}
    w.require(h.read(ref(FINAL_REVIEW))==review,'exact final root source review missing');return ref(FINAL_REVIEW)

def authority(source,runtime,root,state=None):
    seal=history();record=h.read(ref(AUTHORITY));budget=h.read(seal['budget_authority'])
    expected={'schema':'n27-hydra-authority-v1','cohort_id':COHORT,'source':source,'runtime':runtime,'protocol':ref(PROTOCOL),
        'seal':ref(SEAL),'final_review':final_review(source,runtime,root),'budget_authority':seal['budget_authority'],
        'caps':CAPS,'limits':LIMITS,'old_gpu_seconds':seal['old_gpu_seconds'],
        'validation_authorized':False,'formal_authorized':False}
    w.require(set(record)==set(expected)|{'recorded_at','authority_interpretation'} and all(record[k]==v for k,v in expected.items())
        and all(isinstance(record[k],str) and record[k].strip() for k in ('recorded_at','authority_interpretation'))
        and budget['caps']==CAPS,'finite unchanged authority differs')
    if state is not None:w.require(state.get('n27_hydra_continuation_authority')==ref(AUTHORITY),'new authority not adopted')
    return record

def require_state(state,r):
    record=h.read(ref(AUTHORITY));authority(record['source'],record['runtime'],Path(r['ROOT']),state)
    budget=state['budget'];adopted=h.read(record['budget_authority']);resource=state.get('resource_isolation',{})
    w.require(state.get('n26_budget_authority')==record['budget_authority'] and budget['max_episode_attempts']==522
        and budget['max_gpu_hours']==100. and budget['reserved']==CAPS['buckets'] and budget['gpu_hour_reservations']==CAPS['protected_gpu_hours']
        and budget['amendment']==adopted['amendment'] and resource.get('status')=='ACTIVE' and resource.get('validation_status')=='PASS'
        and resource.get('private_budget') is True and state.get('max_concurrent_gpu_workers')==1
        and not state.get('external_resource_hold',{}).get('do_not_auto_resume',False) and r['authorized_gpu'](state)==7,'unchanged private finite budget/resource')

def local_events(events):return [x for x in events if x.get('identity',{}).get('iteration')==COHORT]

def budget_check(state,events,resources,r,*,dispatch=False):
    seal=history();h.current_subset(seal,events,resources);snap=r['budget_snapshot'](events,resources)
    local=local_events(events);gg=r['event_groups'](local);charged=[x for x in local if x['event']=='dispatched']
    w.require(snap['running']==snap['gpu_healthcheck_inflight']==0 and all(g[-1]['event'] in r['TERMINAL'] for g in r['event_groups'](events).values()),'unsettled owner/ledger')
    w.require(state['budget']['dispatched']==snap['dispatched'] and abs(state['budget']['gpu_hours_consumed']-snap['gpu_hours_consumed'])<1e-8,'state/ledger costs differ')
    remaining={b:n-sum(x['budget_bucket']==b for x in charged) for b,n in {'baseline':3,'development':9,'recovery':1}.items()}
    vals=[g[-1].get('gpu_process_wall_seconds') for g in gg.values()]
    w.require(len(gg)<=13 and len(charged)+4<=17 and all(v>=0 for v in remaining.values()) and all(h.finite(v) for v in vals),'finite count/cost missing')
    spent=seal['old_gpu_seconds']+sum(vals);remaining_seconds=sum(remaining.values())*1840
    reserved_h=sum(max(0.,n-snap['gpu_hours_by_bucket'][b]) for b,n in CAPS['protected_gpu_hours'].items())
    reserved_n=sum(max(0,CAPS['buckets'][b]-snap['by_bucket'][b]) for b in ('validation','formal'))
    w.require(spent+remaining_seconds<=9.25*3600 and all(CAPS['buckets'][b]-snap['by_bucket'][b]>=n for b,n in remaining.items())
        and snap['dispatched']+sum(remaining.values())+reserved_n<=522
        and snap['gpu_hours_consumed']+remaining_seconds/3600+reserved_h<=100.+1e-9,'full remaining rows/protected capacity missing')
    if dispatch:w.require(sum(remaining.values())>0 and spent+1840<=9.25*3600,'next full-row capacity missing')
    return {'combined_spent_seconds':spent,'remaining':remaining}

def full_capacity(state,events,resources,r):
    require_state(state,r);return budget_check(state,events,resources,r)

@contextmanager
def supervised_scope(plan,root,episode_key):
    global _SCOPE
    w.require(_SCOPE is None,'nested continuation scope')
    _SCOPE=(str(Path(root).resolve()),plan['source_commit'],episode_key,os.getpid(),threading.get_ident())
    try:yield
    finally:_SCOPE=None

def require_scope(plan,root,r,row=None):
    w.require(_SCOPE is not None and _SCOPE[:2]==(str(Path(root).resolve()),plan['source_commit'])
        and _SCOPE[3:]==(os.getpid(),threading.get_ident()) and (row is None or _SCOPE[2]==row['episode_key']),'closed single-cell scope required')

def effective_row(plan,row,events,root,r):
    require_scope(plan,root,r,row);w.require(row in plan['episodes'],'no substituted/recovery row');return row

def check_retry(events,row,r):
    seal=history();expected=rows(seal);w.require(row in expected,'not exact fixed continuation row')
    index=expected.index(row)+3;original=seal['original_plan_content']['episodes'][index]
    keys=('split','profile','task_id','env_seed','policy_seed','init_index')
    prior=[g for g in r['event_groups'](events).values() if g[0]['identity'].get('iteration') in {h.OLD,COHORT} and all(g[0]['identity'].get(k)==original[k] for k in keys)]
    w.require(not any(x.get('n27_recovery_eligibility') or x.get('n26_recovery_eligibility') for x in (row,)),'mixed recovery marker')
    if index==3:
        w.require(len(prior)==1 and prior[0][-1]==seal['all_old_attempts'][3]['terminal'] and row['retry_of']==h.FAILED
            and row['budget_bucket']=='recovery' and row['n27_named_hydra_proof']==ref(SEAL)
            and not any(x.get('retry_of')==h.FAILED for x in events),'named startup replacement consumed/different')
    else:w.require(not prior and not row.get('retry_of'),'valid/exposed cell cannot repeat')

def protected_budget(state,events,resources,row,timeout,r,*,plan):
    w.require(row in plan['episodes'] and row['iteration']==COHORT and timeout==1800,'row/deadline differs')
    require_state(state,r);budget_check(state,events,resources,r,dispatch=True)

def metadata(source,runtime,root):
    return {'schema':'n27-hydra-continuation-v1','cohort_id':COHORT,'protocol':ref(PROTOCOL),'seal':ref(SEAL),
        'final_review':final_review(source,runtime,root),'authority':ref(AUTHORITY),'limits':LIMITS,'imported_cells':3,'dispatchable':13}

def validate_contract(plan,manifest,runtime,seeds,root,r):
    old.imports_owned(root,r)
    for module in (h,bridge):w.require(Path(module.__file__).resolve().is_relative_to(Path(root).resolve()),'continuation module shadow')
    w.require(Path(__file__).resolve().is_relative_to(Path(root).resolve()),'continuation contract shadow')
    seal=history();source=w.source_record(root,[x['path'] for x in plan['code_files']])
    w.require(source['commit']==plan['source_commit'] and source['files']==plan['code_files'] and source_paths(r)=={x['path'] for x in plan['code_files']},'committed source closure')
    prior=seal['original_plan_content'];allowed={'source_commit','code_files','episodes','n27_cohort','n27_hydra_continuation','derived_from','frozen'}
    w.require(set(plan)==set(prior)|{'n27_hydra_continuation'} and all(plan[k]==prior[k] for k in prior if k not in allowed)
        and plan['derived_from']==seal['original_plan'] and plan['episodes']==rows(seal)
        and plan['n27_cohort']=={'schema':'n27-hydra-audit-family-v1','worker_audit':WORKER_CONTRACT}
        and plan['n27_hydra_continuation']==metadata(source,seal['runtime'],root),'exact source-equivalent continuation plan')
    w.require(set(manifest['profiles'])==set(ARMS) and manifest['profiles']['N27']['resolved_eds_config']=={
        **manifest['profiles']['N26']['resolved_eds_config'],'diversity_update_mode':'feasible_ray_v1'},'science/profile equivalence')
    w.require(runtime==h.read(seal['runtime']) and Path(runtime['worktree']).resolve()==Path(root).resolve()
        and runtime.get('schema')=='qd-ed-runtime-setup-v1' and r['runtime_gpu'](runtime)==7
        and runtime['gpu_mapping']['uuid']==old.GPU7_UUID and runtime['gpu_mapping']['egl_device_index']==4
        and runtime.get('cuda_egl_verified') is True and runtime.get('cuda_egl_probe',{}).get('resource_id')==old.GPU7_PROOF
        and runtime.get('stage_recovered_error_condition')==r['E2_STAGE_CONDITION']
        and runtime.get('stage_engineering_condition')==r['n4e1_support']().engineering_condition()
        and runtime['frozen_stage_provider'].get('allow_recovered_error_events') is True,'frozen runtime/GPU/Stage differs')
    r['verify_files'](runtime['files'],allowed_roots=(Path(root),Path(runtime['worktree']),runtime['artifact_root']))
    require_state(r['read_state'](Path(root)/'research-state.yaml'),r)

def validate_worker_context(context,argv,root,output,plan,runtime):
    meta=plan.get('n27_hydra_continuation',{})
    w.require(plan.get('frozen') is True and plan.get('n27_cohort')=={'schema':'n27-hydra-audit-family-v1','worker_audit':WORKER_CONTRACT}
        and meta.get('schema')=='n27-hydra-continuation-v1' and meta.get('cohort_id')==COHORT and meta.get('protocol',{}).get('sha256')==PROTOCOL_SHA
        and set(plan.get('candidate_profiles',{}))=={'N26','N27'} and not any(k.startswith(('n23_','n24_','n25_','n26_')) for k in plan)
        and plan['worktree']==str(root) and context['profile'] in ARMS
        and output==Path(plan['artifact_root']).resolve()/'attempts'/context['attempt_id']
        and context['runtime']=={'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']},'continuation worker plan/runtime')
    matches=[x for x in plan['episodes'] if x['episode_key']==context['episode_key']]
    w.require(len(matches)==1 and matches[0]['iteration']==COHORT and matches[0]['profile']==context['profile']
        and matches[0]['split']=='dev' and matches[0]['timeout_seconds']==1800 and context['source']['commit']==plan['source_commit']
        and context['source']['files']==plan['code_files'],'worker row/source differs')
    w.verify_source(root,context['source']);w.require(w.cuda_binding(runtime)['physical_gpu']==7,'GPU7 only')
    return root,output,runtime

def accepted_cell(plan,row,events,root,r):
    own=list(r['event_groups']([x for x in local_events(events) if x['episode_key']==row['episode_key']]).values())
    w.require(len(own)==1 and [x['event'] for x in own[0]]==['reserved','dispatched','valid'],'single valid new attempt required')
    final=own[0][-1];out=Path(final['output_dir']);context=h.read(ref(out/'n23-worker-context.json'))
    w.require(final.get('outcome_valid') is True and final.get('required_cost_telemetry_complete') is True and type(final.get('success')) is bool
        and final['identity']==r['episode_identity'](row) and final.get('retry_of')==row.get('retry_of') and final['budget_bucket']==row['budget_bucket']
        and final['source_commit']==plan['source_commit'] and final['plan_sha256']==w.sha(PLAN)
        and final['profile_manifest_sha256']==plan['profiles_sha256'] and final['runtime_manifest_sha256']==plan['runtime_manifest_sha256']
        and final['runtime_inventory_sha256']==plan['runtime_inventory_sha256'] and final['init_row_sha256']==row['init_row_sha256']
        and context['plan']==ref(PLAN) and h.read(context['plan'])==plan and h.read(ref(out/'attempt-result.json'))==final
        and final.get('n23_worker_receipt')==ref(out/'eds_eval/in-worker-audit-receipt.json'),'new terminal/plan/receipt binding')
    report=read_worker_report(out,r);w.require(type(final.get('guided_chunks')) is int,'guided count unknown')
    # Profile-bound gate remains required even with zero guided work; no marker downgrade.
    native.from_output(row['profile'],out,report,final['guided_chunks']);return final

def admission(plan,runtime,row,events,resources,root,r):
    index=plan['episodes'].index(row);local=local_events(events);allowed={x['episode_key'] for x in plan['episodes'][:index]}
    w.require(all(x['episode_key'] in allowed for x in local),'exact untouched suffix/no resume past invalid')
    for previous in plan['episodes'][:index]:accepted_cell(plan,previous,events,root,r)
    return {'n27_hydra_continuation_id':COHORT,'n27_original_logical_index':3+index,'n27_prefix_seal':ref(SEAL),
        **({'n27_named_hydra_proof':ref(SEAL)} if index==0 else {})}
