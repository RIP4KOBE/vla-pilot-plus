"""Conditional N23 protected validation; no release without actual Dev promotion."""
from contextlib import contextmanager
import copy
import json
import math
import os
from pathlib import Path
import threading
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n23_v2_contract as dev
from scripts import qd_ed_n23_validation_bridge as bridge

ROOT=Path(__file__).resolve().parents[1]
RUN_DIR=dev.RUN_DIR
COHORT='N23_VALIDATION_20260930'
ARMS=('C0','Q0','N23')
FIELDS=('task_id','env_seed','policy_seed','init_index','init_row_sha256','init_file_sha256','bddl_sha256')
DEV_COMMIT=bridge.DEV_COMMIT
DEV_PLAN=RUN_DIR/'plan.frozen.v2.gpu7.json'
DEV_RESULT=RUN_DIR/'result-v2.json'
DEV_READER=RUN_DIR/'summarize_cohort_cpu_v2.py'
DEV_READER_SHA='d9918d9f52e4bb37c9f71e7be09af880a7b6f4723ed9a68566bfda38b363224c'
DEV_PLAN_SHA='acd2b2c639f7756cdc353b6a7eea8c93a4d735a8ce6ee25838d9502c938d07f0'
DEV_REVIEW=RUN_DIR/'validation-dev-promotion-review-v1.json'
SOURCE_REVIEW=RUN_DIR/'validation-source-review-v1.json'
PROTOCOL=RUN_DIR/'protocol-validation-conditional-v1.md'
PROTOCOL_SHA='b202e2bf03e13ea4d66fdd355f7959bbb40f264aeb3c9bd37f57959efdc63615'
VALIDATION_PLAN=RUN_DIR/'validation-plan.frozen.v1.gpu7.json'
LIMITS={'primary_cells':60,'dispatches':62,'recoveries':2,'recoveries_per_cell':1,'gpu_hours':32.,
    'episode_timeout_seconds':1800,'cleanup_seconds':40,'physical_gpu':7}
GPU7_UUID=dev.GPU7_UUID
GPU7_PROOF=dev.GPU7_PROOF
require=w.require
sha=w.sha
ref=dev.ref
read_ref=w.read_ref
read=lambda p:json.loads(Path(p).read_text())
_SCOPE=None


def same_ref(a,b):
    return isinstance(a,dict) and isinstance(b,dict) and set(a)==set(b)=={'path','sha256'} and (
        Path(a['path']).is_absolute() and Path(b['path']).is_absolute()
        and Path(a['path']).resolve()==Path(b['path']).resolve() and a['sha256']==b['sha256'])


def manifest(plan,r):
    result=r['read_json'](plan['profiles_path'])
    for arm,reference in plan['candidate_profiles'].items():
        result['profiles'][arm]=r['expand_candidate'](arm,read_ref(reference),result['profiles']['Q0'])
    return result


def source_record(root,parent):
    return bridge.source_record(root,parent,PROTOCOL_SHA)


def review_source(source,source_bridge,parent):
    record=read_ref(ref(SOURCE_REVIEW))
    require(record=={'schema':'n23-validation-source-review-v1','disposition':'accepted','dev_plan':ref(DEV_PLAN),
        'protocol':ref(PROTOCOL),'source':source,'source_bridge':source_bridge,
        'runtime':{'path':parent['runtime_manifest_path'],'sha256':parent['runtime_manifest_sha256']},
        'backend_proof':parent['n23_cohort']['backend_proof'],'no_execution_release':True},
        'validation exact source bridge/root review missing')
    return ref(SOURCE_REVIEW)


def dev_promotion(root,r):
    from scripts import qd_ed_n23_validation_evidence as evidence
    from scripts import qd_ed_n23_validation_recovery as recovery
    from scripts import qd_ed_n23_v2_supervise as supervision
    review=read_ref(ref(DEV_REVIEW));parent=read(DEV_PLAN)
    require(sha(DEV_PLAN)==DEV_PLAN_SHA and sha(DEV_READER)==DEV_READER_SHA,
        'validation frozen Dev plan/actual result reader changed')
    require(set(review)=={'schema','disposition','dev_plan','dev_status','dev_result','backend_proof','allow_validation'}
        and review['schema']=='n23-dev-promotion-review-v1' and review['disposition']=='promoted'
        and review['allow_validation'] is True and review['dev_plan']==ref(DEV_PLAN)
        and review['dev_result']==ref(DEV_RESULT),'validation actual root Dev promotion required')
    status=read_ref(review['dev_status']);result=read_ref(review['dev_result'])
    require(parent['source_commit']==DEV_COMMIT and parent['episodes']==dev.expected_rows()
        and parent.get('frozen') is True and parent['phase_authorization']=={'dev':True,'validation':False,'formal':False},
        'validation actual original forty-cell Dev plan differs')
    require(result.get('schema')=='n23-dev-cohort-result-v2' and result.get('cohort_id')==dev.COHORT
        and result.get('source_commit')==DEV_COMMIT and same_ref(result.get('plan'),review['dev_plan'])
        and result.get('reader')==ref(DEV_READER) and result.get('planned')==result.get('audited_cells')==40
        and result.get('dev_gate_promoted') is True
        and result.get('decision')=='ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION'
        and result.get('goal_status')=='TARGET_NOT_MET','validation terminal Dev result is not complete promotion')
    status_ref=result.get('terminal_status',{})
    require(set(status_ref)=={'path','sha256','content'} and same_ref({k:status_ref[k] for k in ('path','sha256')},review['dev_status'])
        and status_ref['content']==status and status.get('schema')=='n23-dev-supervisor-status-v2'
        and status.get('cohort_id')==dev.COHORT and status.get('status')=='completed_all_forty_audited'
        and status.get('dev_gate_promoted') is True and status.get('completed_keys')==[v['episode_key'] for v in parent['episodes']],
        'validation terminal Dev status/source differs')
    events=r['read_events'](Path(root)/'data/attempt-ledger.jsonl')
    local=[v for v in events if v.get('identity',{}).get('iteration')==dev.COHORT]
    snapshot=result['ledger_snapshot']
    require(snapshot==ref(snapshot['path']) and r['read_events'](snapshot['path'])==local,
        'validation Dev-only ledger snapshot differs')
    require(result.get('backend_proof')==review['backend_proof']==parent['n23_cohort']['backend_proof'],
        'validation actual arithmetic proof binding differs')
    evidence.historical_backend(review['backend_proof'],parent,events,r)
    charged=[v for v in local if v['event']=='dispatched']
    require(40<=len(charged)<=42 and result.get('dispatched')==len(charged),'validation Dev attempt denominator differs')
    accepted=result.get('accepted_cells',[])
    require(len(accepted)==40 and [v['episode_key'] for v in accepted]==[v['episode_key'] for v in parent['episodes']],
        'validation Dev accepted cells missing/order differs')
    counts={a:0 for a in dev.ARMS};guided=parents=0;expected_outcomes=[];attempts=[]
    native_totals={'N7':{'guided_decisions':0,'parent_rounds_verified':0},
        'N23':{'guided_decisions':0,'parent_rounds_verified':0,**{k:0 for k in supervision.NATIVE_FIELDS}}}
    aux_totals={k:0 for k in supervision.AUX_FIELDS}
    for row,entry in zip(parent['episodes'],accepted):
        final=recovery.historical_dev_cell(parent,row,events,root,r)
        out=Path(final['output_dir'])
        expected={'episode_key':row['episode_key'],'task_id':row['task_id'],'profile':row['profile'],
            'attempt_id':final['attempt_id'],'success':final['success'],
            'audit':ref(out/'eds_eval/decision-evidence-audit.json'),'worker_context':ref(out/'n23-worker-context.json'),
            'worker_receipt':ref(out/'eds_eval/in-worker-audit-receipt.json'),'attempt_result':ref(out/'attempt-result.json')}
        require(entry==expected and read_ref(entry['attempt_result'])==final,'validation reviewed Dev cell association differs')
        report=evidence.historical_receipt(final,row,parent,review['dev_plan'],r)
        native,aux=supervision.native_counts(final,row,report)
        if row['profile'] in native_totals:
            for key,value in native.items():native_totals[row['profile']][key]+=value
        for key,value in aux.items():aux_totals[key]+=value
        if row['profile']=='N23':guided+=native['guided_decisions'];parents+=native['parent_rounds_verified']
        counts[row['profile']]+=int(final['success'] is True)
        expected_outcomes.append({'task_id':row['task_id'],'profile':row['profile'],'success':final['success'],
            'attempt_id':final['attempt_id'],'recovered':final.get('retry_of') is not None})
    for event in local:
        if event['event'] in r['TERMINAL']:
            row=next(v for v in parent['episodes'] if v['episode_key']==event['episode_key'])
            attempts.append(supervision.attempt_record(event,row))
    require(result['counts']=={a:{'audited':10,'success':v} for a,v in counts.items()}
        and status['successes']==counts and status['outcomes']==expected_outcomes
        and counts['N23']>=5 and counts['N23']>=max(counts[a] for a in dev.ARMS[:-1])
        and guided>0 and parents>0 and status['native']['N23']['guided_decisions']==guided
        and status['native']['N23']['parent_rounds_verified']==parents,'validation Dev aggregate/native promotion differs')
    require(result['attempts']==attempts
        and [v['terminal'] for v in status['attempts']]==[v['terminal'] for v in attempts],
        'validation all charged Dev attempts not retained')
    summary=supervision.summarize(expected_outcomes,attempts)
    require(all(status.get(k)==v and result.get(k)==v for k,v in summary.items())
        and result.get('native')==status.get('native')==native_totals
        and all(set(obj.get('auxiliary',{}))==set(aux_totals) and all(math.isclose(obj['auxiliary'][k],v,
            rel_tol=1e-9,abs_tol=1e-8) for k,v in aux_totals.items()) for obj in (status,result)),
        'validation Dev cost/native/denominator aggregation differs')
    return ref(DEV_REVIEW)


def require_budget_state(state,r):
    dev.require_state(state,r)
    value=state.get('n23_validation_authorization',{})
    require(set(value)=={'schema','cohort_id','seed_cohort','protocol_sha256','dev_review','source_review','run_once','physical_gpu'}
        and value['schema']=='n23-validation-authorization-v1' and value['cohort_id']==COHORT
        and value['seed_cohort'] in {'c1','c2','c3','c4'} and value['protocol_sha256']==PROTOCOL_SHA
        and value['run_once'] is True and value['physical_gpu']==7,'separate N23 validation authorization missing')


def validate_contract(plan,profiles,runtime,seeds,root,r):
    from scripts import qd_ed_n23_validation_identity as identity
    from scripts import qd_ed_n23_validation_prepare as prepare
    require(plan==read(VALIDATION_PLAN),'validation requires exact frozen plan')
    parent=read(DEV_PLAN);source,source_bridge=source_record(root,parent);meta=plan.get('n23_validation',{})
    require(sha(PROTOCOL)==PROTOCOL_SHA and meta.get('schema')=='n23-protected-validation-v1'
        and meta.get('cohort_id')==COHORT and meta.get('limits')==LIMITS and meta.get('protocol')==ref(PROTOCOL)
        and meta.get('dev_review')==dev_promotion(root,r)
        and meta.get('source_review')==review_source(source,source_bridge,parent)
        and meta.get('source_bridge')==source_bridge
        and meta.get('backend_proof')==parent['n23_cohort']['backend_proof']
        and meta.get('worker_audit')==w.WORKER_CONTRACT,'validation promotion/source/proof gate differs')
    expected=prepare.build_plan(parent,seeds,meta['seed_cohort'],source=source,source_bridge=source_bridge,
        dev_review=meta['dev_review'],source_review=meta['source_review'],selection=meta['metadata_selection'])
    expected['frozen']=True
    require(plan==expected,'validation differs from exact parent plus permitted evaluation fields')
    require(plan['source_commit']==source['commit'] and plan['code_files']==source['files']
        and plan.get('n23_cohort') is None and set(plan['candidate_profiles'])=={'N23'}
        and plan['phase_authorization']=={'dev':False,'validation':True,'formal':False}
        and set(profiles['profiles'])==set(ARMS)
        and plan['episodes']==identity.rows_for(seeds,meta['seed_cohort']),'validation closed matrix/profile/phase differs')
    for key in ('profiles_path','profiles_sha256','runtime_manifest_path','runtime_manifest_sha256',
                'runtime_inventory_path','runtime_inventory_sha256','seed_plan_path','seed_plan_sha256','artifact_root'):
        require(plan[key]==parent[key],'validation scientific/runtime fingerprint differs')
    require(plan['candidate_profiles']['N23']==parent['candidate_profiles']['N23']
        and runtime==read(parent['runtime_manifest_path']),'validation exact scientific candidate/runtime differs')
    dev.validate_runtime(runtime,root,r)
    selection=identity.metadata(root,parent)
    require(identity.first_unused(*selection[:4],allow_own=True)==meta['seed_cohort'],'validation fresh cohort changed')
    state=r['read_state'](Path(root)/'research-state.yaml');require_budget_state(state,r)
    auth=state['n23_validation_authorization']
    require(all(auth[k]==meta[k] for k in ('seed_cohort','dev_review','source_review')),
        'validation state authorization differs from plan')


def validate_worker_context(context,main_argv,root):
    from scripts import qd_ed_final_runner as runner
    require(set(context)=={'schema','attempt_id','episode_key','profile','output_dir','worktree','main_argv','plan','runtime','source'}
        and context['schema']=='n23-metered-worker-context-v1','validation worker context schema differs')
    plan=read_ref(context['plan']);runtime=read_ref(context['runtime']);out=Path(context['output_dir']).resolve()
    require(context['main_argv']==list(main_argv) and main_argv[0]==str(Path(root).resolve()/'main.py')
        and Path(context['worktree']).resolve()==Path(root).resolve() and plan['worktree']==str(Path(root).resolve())
        and out==Path(plan['artifact_root']).resolve()/'attempts'/context['attempt_id']
        and context['plan']==ref(VALIDATION_PLAN) and context['runtime']=={
            'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']},
        'validation worker command/root/plan differs')
    meta=plan.get('n23_validation',{});rows=[v for v in plan['episodes'] if v['episode_key']==context['episode_key']]
    require(meta.get('schema')=='n23-protected-validation-v1' and meta.get('cohort_id')==COHORT
        and meta.get('limits')==LIMITS and meta.get('worker_audit')==w.WORKER_CONTRACT
        and context['profile'] in ARMS and plan['phase_authorization']=={'dev':False,'validation':True,'formal':False}
        and len(rows)==1 and rows[0]['profile']==context['profile'] and rows[0]['split']=='validation'
        and rows[0]['iteration']==COHORT and rows[0]['timeout_seconds']==1800,'validation worker frozen scope differs')
    command,expected_output=runner.build_command(plan,manifest(plan,vars(runner)),runtime,rows[0],context['attempt_id'])
    require(command[1:]==list(main_argv) and Path(expected_output).resolve()==out,
        'validation worker complete frozen command differs')
    require(context['source']['files']==plan['code_files'] and context['source']['commit']==plan['source_commit'],
        'validation worker source differs')
    w.verify_source(root,context['source'])
    source,source_bridge=source_record(root,read(DEV_PLAN))
    require(context['source']==source and meta['source_bridge']==source_bridge
        and meta['source_review']==review_source(source,source_bridge,read(DEV_PLAN))
        and w.cuda_binding(runtime)=={'physical_gpu':7,'uuid':GPU7_UUID,'logical_device':'cuda:0'},
        'validation worker exact science bridge/runtime differs')
    return Path(root).resolve(),out,runtime


@contextmanager
def supervised_scope(plan,root,key,*,eligibility=None):
    global _SCOPE
    require(_SCOPE is None,'nested validation scope')
    _SCOPE={'root':str(Path(root).resolve()),'source':plan['source_commit'],'key':key,
        'pid':os.getpid(),'thread':threading.get_ident(),'eligibility':eligibility}
    try:yield
    finally:_SCOPE=None


def require_scope(plan,root,r,row=None):
    require(_SCOPE is not None and _SCOPE['root']==str(Path(root).resolve()) and _SCOPE['source']==plan['source_commit']
        and _SCOPE['pid']==os.getpid() and _SCOPE['thread']==threading.get_ident()
        and (row is None or row['episode_key']==_SCOPE['key']),'validation one-cell supervisor required')


def primary_row(plan,row):
    matches=[v for v in plan['episodes'] if v['episode_key']==row['episode_key']]
    require(len(matches)==1,'validation unknown cell');primary=matches[0]
    require(row==primary or (set(row)==set(primary)|{'retry_of','n23_validation_recovery_eligibility'}
        and row['budget_bucket']=='recovery'
        and {k:v for k,v in row.items() if k not in {'budget_bucket','retry_of','n23_validation_recovery_eligibility'}}
            =={k:v for k,v in primary.items() if k!='budget_bucket'}),'validation recovery changed scientific identity')
    return primary


def effective_row(plan,row,events,root,r):
    from scripts import qd_ed_n23_validation_recovery as recovery
    require_scope(plan,root,r,row)
    if _SCOPE['eligibility'] is None:return row
    record=recovery.verify_eligibility(_SCOPE['eligibility'],plan,row,events,root,r)
    return {**row,'budget_bucket':'recovery','retry_of':record['primary_attempt_id'],
        'n23_validation_recovery_eligibility':_SCOPE['eligibility']}


def full_capacity(state,events,resources,r):
    require_budget_state(state,r);snap=r['budget_snapshot'](events,resources)
    local=[v for v in events if v.get('identity',{}).get('iteration')==COHORT]
    dispatched=[v for v in local if v['event']=='dispatched']
    primary=sum(not v.get('retry_of') for v in dispatched);recovered={v['attempt_id'] for v in local if v.get('retry_of')}
    spent=sum(v.get('gpu_process_wall_seconds',0.) for v in local if v['event'] in r['TERMINAL'])/3600.
    require(primary<=60 and len(recovered)<=2 and len(dispatched)<=62,'validation finite attempt cap exceeded')
    require(snap['running']==snap['gpu_healthcheck_inflight']==0
        and all(g[-1]['event'] in r['TERMINAL'] for g in r['event_groups'](events).values()),
        'validation unfinished owned process/reservation')
    needs={'validation':60-primary,'recovery':2-len(recovered)}
    require(all(state['budget']['reserved'][b]-snap['by_bucket'][b]>=n for b,n in needs.items()),
        'validation full primary/recovery capacity unavailable')
    formal=max(0,state['budget']['reserved']['formal']-snap['by_bucket']['formal'])
    formal_hours=max(0.,12.-snap['gpu_hours_by_bucket']['formal'])
    require(snap['dispatched']+sum(needs.values())+formal<=478
        and snap['gpu_hours_consumed']+max(0.,32.-spent)+formal_hours<=100.+1e-9,
        'validation whole remaining matrix/local ceiling would borrow formal reserve')


def protected_budget(state,events,resources,row,timeout,r,*,plan):
    primary_row(plan,row)
    require(row['iteration']==COHORT and row['profile'] in ARMS and row['split']=='validation' and timeout==1800,
        'validation row/timeout differs')
    local=[v for v in events if v.get('identity',{}).get('iteration')==COHORT]
    require(sum(v['event']=='dispatched' for v in local)<62
        and sum(v.get('gpu_process_wall_seconds',0.) for v in local if v['event'] in r['TERMINAL'])+1840<=32*3600,
        'validation local dispatch/hour ceiling')
    full_capacity(state,events,resources,r)


def read_worker_report(output,r):return dev.read_worker_report(output,r)


def accepted_cell(plan,row,events,root,r):
    from scripts import qd_ed_n23_validation_recovery as recovery
    return recovery.accepted_cell(plan,row,events,root,r)


def admission(plan,runtime,row,events,resources,root,r):
    from scripts import qd_ed_n23_validation_recovery as recovery
    primary=primary_row(plan,row);index=plan['episodes'].index(primary)
    local=[v for v in events if v.get('identity',{}).get('iteration')==COHORT]
    allowed={v['episode_key'] for v in plan['episodes'][:index]}|({row['episode_key']} if row.get('retry_of') else set())
    require(all(v.get('episode_key') in allowed for v in local),'validation exact primary/recovery prefix required')
    for previous in plan['episodes'][:index]:accepted_cell(plan,previous,events,root,r)
    if row.get('retry_of'):recovery.verify_eligibility(row['n23_validation_recovery_eligibility'],plan,primary,events,root,r)
    return {'n23_validation_cohort_id':COHORT,'n23_validation_seed_block':row['seed_block'],
        'n23_validation_protocol_sha256':PROTOCOL_SHA,
        **({'n23_validation_recovery_eligibility':row['n23_validation_recovery_eligibility']} if row.get('retry_of') else {})}
