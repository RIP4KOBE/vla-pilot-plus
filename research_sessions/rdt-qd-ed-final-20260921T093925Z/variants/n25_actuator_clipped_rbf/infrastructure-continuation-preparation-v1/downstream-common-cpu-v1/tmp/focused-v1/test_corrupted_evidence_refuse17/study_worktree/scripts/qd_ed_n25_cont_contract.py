"""Exactly one named incomplete-infrastructure continuation; no generalized retry."""
import copy
import math
import os
from pathlib import Path
import threading
from contextlib import contextmanager
from scripts import qd_ed_n23_worker as w,qd_ed_n25_contract as old,qd_ed_n25_native as native
from scripts import qd_ed_n25_cont_evidence as e,qd_ed_n25_cont_bridge as bridge,qd_ed_n25_cont_seal as sealer

ROOT=Path(__file__).resolve().parents[1]
COHORT=e.COHORT;ARMS=e.ARMS;RUN_DIR=old.RUN_DIR/'infrastructure-continuation-v1'
PROTOCOL=old.RUN_DIR/'infrastructure-continuation-preparation-v1/root-implementation-protocol-v1.md'
PROTOCOL_SHA='c0c9fac3c18a920f88539c9abcf9d66359d4843d05a630f183b15845d97c59ef'
SEAL=RUN_DIR/'metadata-seal-v1.json';SEAL_REVIEW=RUN_DIR/'root-seal-review-v1.json'
FINAL_REVIEW=RUN_DIR/'final-source-runtime-review-v1.json';AUTHORITY=RUN_DIR/'adoption-v1/authority.json'
BRIDGE=RUN_DIR/'source-bridge-v1.json';PLAN=RUN_DIR/'plan.frozen.v1.gpu7.json'
CAPS={'attempts':494,'gpu_hours':100.,'buckets':{'baseline':55,'development':199,'validation':180,'formal':40,'recovery':20},
 'protected_gpu_hours':{'validation':32.,'formal':12.}}
LIMITS={'new_dispatches':22,'named_retries':1,'additional_retries':0,'combined_dispatches':42,'combined_recoveries':2,
 'episode_timeout_seconds':1800,'cleanup_seconds':40,'combined_local_gpu_hours':22.,'physical_gpu':7}
WORKER_CONTRACT=old.WORKER_CONTRACT
ref=e.ref;_SCOPE=None
read_worker_report=old.read_worker_report

def history(*,cleanup=False):
    seal=w.read_ref(ref(SEAL));review=w.read_ref(ref(SEAL_REVIEW))
    w.require(review=={'schema':'n25-continuation-root-seal-review-v1','accepted':True,'seal':ref(SEAL),
        'protocol':ref(PROTOCOL),'original_disposition':'INVALID_OR_INTERRUPTED','history_is_metadata_attestation':True,
        'historical_unknowns':e.UNKNOWN,'gpu_authorized':False},'root seal review missing/different')
    w.require(w.sha(PROTOCOL)==PROTOCOL_SHA,'continuation protocol changed')
    return sealer.verify(seal,check_cleanup=cleanup)

def rows(seal):
    result=[]
    for index,oldrow in enumerate(seal['original_rows'][18:],18):
        row=copy.deepcopy(oldrow);row.update(iteration=COHORT,episode_key=oldrow['episode_key']+'_infra1')
        if index==18:row.update(budget_bucket='recovery',retry_of=e.FAILED,n25_named_infrastructure_proof=ref(SEAL))
        result.append(row)
    w.require(len(result)==22,'22 fixed successor rows required');return result

def source_paths(r):return bridge.source_paths(Path(r['ROOT']))

def final_review(source,runtime,root):
    seal=history();b=bridge.build(source,seal,root)
    w.require(w.read_ref(ref(BRIDGE))==b,'source bridge differs')
    expected={'schema':'n25-continuation-source-runtime-review-v1','accepted':True,'source':source,'runtime':runtime,
        'protocol':ref(PROTOCOL),'seal':ref(SEAL),'root_seal_review':ref(SEAL_REVIEW),'source_bridge':ref(BRIDGE),
        'historical_backend_proof':seal['historical_backend_proof'],'no_new_preflight':True,'gpu_authorized':False}
    w.require(w.read_ref(ref(FINAL_REVIEW))==expected,'root source review differs');return ref(FINAL_REVIEW)

def authority(source,runtime,root,state=None):
    record=w.read_ref(ref(AUTHORITY));seal=history();cap=record.get('remaining_local_gpu_hours')
    keys={'schema','cohort_id','source','runtime','protocol','seal','final_review','existing_budget_authority','caps','limits',
        'original_local_gpu_hours','old_gpu_seconds','remaining_local_gpu_hours','recorded_at','authority_interpretation','validation_authorized','formal_authorized'}
    w.require(set(record)==keys and record['schema']=='n25-continuation-authority-v1' and record['cohort_id']==COHORT
        and record['source']==source and record['runtime']==runtime and record['protocol']==ref(PROTOCOL)
        and record['seal']==ref(SEAL) and record['final_review']==final_review(source,runtime,root)
        and record['caps']==CAPS and record['limits']==LIMITS and record['original_local_gpu_hours']==22.
        and record['old_gpu_seconds']==e.OLD_SECONDS and type(cap) in (int,float) and math.isfinite(cap)
        and 1840/3600<=cap<=22-e.OLD_SECONDS/3600 and record['validation_authorized'] is False and record['formal_authorized'] is False
        and all(isinstance(record[k],str) and record[k].strip() for k in ('recorded_at','authority_interpretation')),'finite continuation authority differs')
    original_authority=w.read_ref(seal['old_authority']);budget=w.read_ref(record['existing_budget_authority'])
    w.require(record['existing_budget_authority']==original_authority['budget_authority'] and budget['caps']==CAPS,'old adopted finite budget changed')
    if state is not None:w.require(state.get('n25_continuation_authority')==ref(AUTHORITY),'new authority not adopted')
    return record

def require_state(state,r):
    rec=w.read_ref(ref(AUTHORITY));authority(rec['source'],rec['runtime'],Path(r['ROOT']),state)
    budget=state['budget'];existing=w.read_ref(rec['existing_budget_authority']);resource=state['resource_isolation']
    w.require(state.get('n25_budget_authority')==rec['existing_budget_authority']
        and budget['max_episode_attempts']==494 and budget['max_gpu_hours']==100.
        and budget['reserved']==CAPS['buckets'] and budget['gpu_hour_reservations']==CAPS['protected_gpu_hours']
        and budget['amendment']==existing['amendment'] and resource.get('status')=='ACTIVE' and resource.get('validation_status')=='PASS'
        and resource.get('private_budget') is True and state.get('max_concurrent_gpu_workers')==1
        and not state.get('external_resource_hold',{}).get('do_not_auto_resume',False) and r['authorized_gpu'](state)==7,'unchanged private budget/resource policy required')

def local_events(events):return [x for x in events if x.get('identity',{}).get('iteration')==COHORT]

def budget_check(state,events,resources,r,record,*,dispatch=False):
    seal=history();old_events=[x for x in events if x.get('identity',{}).get('iteration')==e.OLD]
    w.require(old_events==w.read_ref(seal['old_ledger']),'old ledger changed/later original reservation')
    from scripts import qd_ed_n25_backend as backend
    backend.settled_proof(w.read_ref(seal['historical_backend_proof']),resources,r)
    local=local_events(events);gg=r['event_groups'](local);snap=r['budget_snapshot'](events,resources)
    w.require(snap['running']==snap['gpu_healthcheck_inflight']==0 and all(g[-1]['event'] in r['TERMINAL'] for g in r['event_groups'](events).values()),'unsettled worker/ledger')
    charged=[x for x in local if x['event']=='dispatched'];used={b:sum(x['budget_bucket']==b for x in charged) for b in CAPS['buckets']}
    needs={'baseline':5-used['baseline'],'development':16-used['development'],'recovery':1-used['recovery']}
    spent=sum(x.get('gpu_process_wall_seconds',0.) for x in local if x['event'] in r['TERMINAL'])
    w.require(len(gg)<=22 and len(charged)+19<=42 and used['recovery']<=1 and all(n>=0 for n in needs.values()),'combined attempt/bucket bound')
    reserve_h=sum(max(0.,h-snap['gpu_hours_by_bucket'][b]) for b,h in CAPS['protected_gpu_hours'].items())
    reserve_n=sum(max(0,CAPS['buckets'][b]-snap['by_bucket'][b]) for b in ('validation','formal'))
    cap=record['remaining_local_gpu_hours']*3600
    w.require(spent<=cap and e.OLD_SECONDS+spent<=22*3600
        and all(CAPS['buckets'][b]-snap['by_bucket'][b]>=n for b,n in needs.items())
        and snap['dispatched']+sum(needs.values())+reserve_n<=494,'finite slots/local time exhausted')
    w.require(snap['gpu_hours_consumed']+max(0.,cap-spent)/3600+reserve_h<=100.+1e-9,'local cap borrows protected cumulative hours')
    if dispatch:w.require(spent+1840<=cap and snap['gpu_hours_consumed']+1840/3600+reserve_h<=100.+1e-9,'full1840 per-dispatch capacity missing')
    return {'spent_seconds':spent,'remaining_slots':needs}

def full_capacity(state,events,resources,r):
    require_state(state,r);return budget_check(state,events,resources,r,w.read_ref(ref(AUTHORITY)))

@contextmanager
def supervised_scope(plan,root,episode_key):
    global _SCOPE
    w.require(_SCOPE is None,'nested continuation scope')
    _SCOPE=(str(Path(root).resolve()),plan['source_commit'],episode_key,os.getpid(),threading.get_ident())
    try:yield
    finally:_SCOPE=None

def require_scope(plan,root,r,row=None):
    w.require(_SCOPE is not None and _SCOPE[:2]==(str(Path(root).resolve()),plan['source_commit'])
        and _SCOPE[3:]==(os.getpid(),threading.get_ident()) and (row is None or row['episode_key']==_SCOPE[2]),'closed single-cell continuation scope required')

def effective_row(plan,row,events,root,r):
    require_scope(plan,root,r,row);w.require(row in plan['episodes'],'no replacement or recovery row');return row

def check_retry(events,row,r):
    seal=history();expected=rows(seal);w.require(row in expected,'not exact22 row')
    index=expected.index(row)+18;oldrow=seal['original_rows'][index]
    scientific=lambda x:{k:x[k] for k in ('split','profile','task_id','env_seed','policy_seed','init_index')}
    prior=[g for g in r['event_groups'](events).values() if g[0]['identity']['iteration'] in {e.OLD,COHORT} and scientific(g[0]['identity'])==scientific(e.identity(oldrow))]
    if index==18:
        w.require(row['retry_of']==e.FAILED and row['budget_bucket']=='recovery' and row['n25_named_infrastructure_proof']==ref(SEAL)
            and len(prior)==1 and prior[0][-1]==seal['all_old_attempts'][18]['terminal'],'only exact named first retry allowed')
    else:w.require(not prior and not row.get('retry_of'),'scientific cell exposed/repeated')
    if index==18:w.require(not any(x.get('retry_of')==e.FAILED for x in events),'named opportunity already consumed')


def protected_budget(state,events,resources,row,timeout,r,*,plan):
    w.require(row in plan['episodes'] and row['iteration']==COHORT and timeout==1800,'continuation row/deadline differs')
    require_state(state,r);budget_check(state,events,resources,r,w.read_ref(ref(AUTHORITY)),dispatch=True)

def validate_contract(plan,manifest,runtime,seeds,root,r):
    old.imports_owned(root,r)
    w.require(Path(__file__).resolve().is_relative_to(Path(root).resolve()),'continuation module shadowing')
    seal=history();source=w.source_record(root,[x['path'] for x in plan['code_files']])
    w.require(source['commit']==plan['source_commit'] and source['files']==plan['code_files'] and set(x['path'] for x in plan['code_files'])==source_paths(r),'complete committed source required')
    w.require(plan['episodes']==rows(seal) and plan['n25_infrastructure_continuation']==metadata(source,seal['runtime'],root)
        and plan['n25_cohort']=={'schema':'n25-continuation-audit-family-v1','worker_audit':WORKER_CONTRACT}
        and plan['phase_authorization']=={'dev':True,'validation':False,'formal':False},'exact continuation matrix/metadata differs')
    prior=w.read_ref(seal['original_plan']);allowed={'source_commit','code_files','episodes','n25_cohort','n25_infrastructure_continuation','derived_from','frozen'}
    w.require(set(plan)==set(prior)|{'n25_infrastructure_continuation'}
        and all(plan[k]==prior[k] for k in prior if k not in allowed),'original plan/runtime/science changed')
    for a in ('N23','N25'):w.require(w.sha(plan['candidate_profiles'][a]['path'])==plan['candidate_profiles'][a]['sha256'],'profile bytes changed')
    old.validate_runtime(runtime,root,r);require_state(r['read_state'](Path(root)/'research-state.yaml'),r)

def metadata(source,runtime,root):
    return {'schema':'n25-infrastructure-continuation-v1','cohort_id':COHORT,'protocol':ref(PROTOCOL),'seal':ref(SEAL),
        'final_review':final_review(source,runtime,root),'authority':ref(AUTHORITY),'limits':LIMITS,
        'historical_unknowns':e.UNKNOWN,'imports':18,'dispatchable':22}

def validate_worker_context(context,argv,root,output,plan,runtime):
    w.require(plan.get('frozen') is True and plan['n25_cohort']['worker_audit']==WORKER_CONTRACT
        and plan['n25_infrastructure_continuation']['schema']=='n25-infrastructure-continuation-v1'
        and plan['n25_infrastructure_continuation']['protocol']['sha256']==PROTOCOL_SHA
        and plan['worktree']==str(root) and context['profile'] in ARMS
        and output==Path(plan['artifact_root']).resolve()/'attempts'/context['attempt_id']
        and context['runtime']=={'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']},'continuation worker context differs')
    matches=[x for x in plan['episodes'] if x['episode_key']==context['episode_key']]
    w.require(len(matches)==1 and matches[0]['iteration']==COHORT and matches[0]['profile']==context['profile']
        and matches[0]['split']=='dev' and matches[0]['timeout_seconds']==1800 and context['source']['commit']==plan['source_commit']
        and context['source']['files']==plan['code_files'],'continuation worker scientific row/source differs')
    w.verify_source(root,context['source']);w.require(w.cuda_binding(runtime)['physical_gpu']==7,'GPU7 worker required')
    return root,output,runtime

def accepted_cell(plan,row,events,root,r):
    own=list(r['event_groups']([x for x in local_events(events) if x['episode_key']==row['episode_key']]).values())
    w.require(len(own)==1 and [x['event'] for x in own[0]]==['reserved','dispatched','valid'],'single settled new attempt required')
    final=own[0][-1]
    w.require(final['outcome_valid'] is True and final['required_cost_telemetry_complete'] is True
        and final['identity']==r['episode_identity'](row) and final['retry_of']==row.get('retry_of')
        and final['source_commit']==plan['source_commit'] and final['plan_sha256']==w.sha(plan['_path'])
        and final['profile_manifest_sha256']==plan['profiles_sha256'] and final['runtime_manifest_sha256']==plan['runtime_manifest_sha256']
        and final['runtime_inventory_sha256']==plan['runtime_inventory_sha256'] and final['init_row_sha256']==row['init_row_sha256'],'new accepted gate/identity missing')
    out=Path(final['output_dir']);context=w.read_ref(ref(out/'n23-worker-context.json'))
    frozen={k:v for k,v in plan.items() if k!='_path'}
    w.require(w.read_ref(context['plan'])==frozen and w.read_ref(ref(out/'attempt-result.json'))==final
        and final['n23_worker_receipt']==ref(out/'eds_eval/in-worker-audit-receipt.json'),'new receipt/terminal plan differs')
    report=old.read_worker_report(out,r);native.from_output(row['profile'],out,report,final.get('guided_chunks'))
    return final

def admission(plan,runtime,row,events,resources,root,r):
    seal=history();index=plan['episodes'].index(row)
    allowed={x['episode_key'] for x in plan['episodes'][:index]}
    w.require(all(x['episode_key'] in allowed for x in local_events(events)),'exact new prefix; no resume past invalid')
    valid=[accepted_cell({**plan,'_path':_plan_path(plan)},x,events,root,r) for x in plan['episodes'][:index]]
    n=18+index;wins=seal['counts']['N25']['success']+sum(x['success'] is True and x['identity']['profile']=='N25' for x in valid)
    w.require(wins+10-n//4>=5,'complete original quadruple futility already reached')
    return {'n25_continuation_id':COHORT,'n25_original_logical_index':18+index,'n25_original_cohort':e.OLD,
        'n25_continuation_protocol_sha256':PROTOCOL_SHA,'n25_prefix_seal':ref(SEAL),'n25_historical_unknowns':e.UNKNOWN}

def _plan_path(plan):
    w.require(w.read_ref(ref(PLAN))==plan,'plan must be exact frozen continuation');return str(PLAN)
