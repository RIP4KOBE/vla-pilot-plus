"""Separate, conditional N25 protected validation; no authority from Dev alone."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import threading
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n25_contract as dev
from scripts import qd_ed_n25_native as native
from scripts import qd_ed_n25_validation_bridge as bridge
ROOT=Path(__file__).resolve().parents[1]
RUN_DIR=dev.RUN_DIR
COHORT='N25_VALIDATION_20260930'
ARMS=('C0','Q0','N25')
FIELDS=('task_id','env_seed','policy_seed','init_index','init_row_sha256','init_file_sha256','bddl_sha256')
DEV_COMMIT=bridge.DEV_COMMIT
DEV_PLAN=RUN_DIR/'plan.frozen.v1.gpu7.json'
DEV_PLAN_SHA='1f0c94ccd3458a3a786acb9525728a1b64e3df439e4f920731f6566dd3a95eb3'
DEV_RESULT=RUN_DIR/'result-v1.json'
DEV_STATUS=RUN_DIR/'execution/supervisor-status-v1.json'
DEV_REVIEW=RUN_DIR/'validation-dev-promotion-review-v1.json'
SOURCE_REVIEW=RUN_DIR/'validation-source-review-v1.json'
AUTHORITY=RUN_DIR/'validation-adoption-v1/authority.json'
PROTOCOL=RUN_DIR/'protocol-validation-conditional-v1.md'
PROTOCOL_SHA='5ed12805f71bfb2a727af4489fd1ccc0fcb962b48641679a4ad935e935e1df35'
ROUTING_ADDENDUM=RUN_DIR/'protocol-validation-routing-addendum-v1.md'
ROUTING_SHA='42632edf9bec27791fa77e6dc163f806f0305ba9d8b60958a7de64a78caef0f0'
CAPS={'attempts':494,'gpu_hours':100.,'buckets':{'baseline':55,'development':199,'validation':180,'formal':40,'recovery':20},
 'protected_gpu_hours':{'validation':32.,'formal':12.}}
VALIDATION_PLAN=RUN_DIR/'validation-plan.frozen.v1.gpu7.json'
LIMITS={'primary_cells':60,'dispatches':62,'recoveries':2,'recoveries_per_cell':1,'gpu_hours':32.,
        'episode_timeout_seconds':1800,'cleanup_seconds':40,'physical_gpu':7}
WORKER_MARKER={'schema':'n25-validation-worker-native-binding-v1','worker_audit':dev.WORKER_CONTRACT}
GPU7_UUID=dev.GPU7_UUID
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


def original_plan():
    require(sha(DEV_PLAN)==DEV_PLAN_SHA,'N25 validation frozen Dev plan changed')
    parent=read(DEV_PLAN)
    require(parent['source_commit']==DEV_COMMIT and len(parent['code_files'])==257 and parent.get('frozen') is True
        and parent['episodes']==dev.expected_rows() and parent['phase_authorization']=={'dev':True,'validation':False,'formal':False},
        'N25 validation requires exact original complete Dev matrix/source')
    return parent


def manifest(plan,r):
    value=r['read_json'](plan['profiles_path'])
    for arm,reference in plan['candidate_profiles'].items():value['profiles'][arm]=r['expand_candidate'](arm,read_ref(reference),value['profiles']['Q0'])
    return value


def source_record(root,parent):return bridge.source_record(root,parent,PROTOCOL_SHA,ROUTING_SHA)


def dev_promotion(root,r):
    from scripts import qd_ed_n25_validation_evidence as evidence
    from scripts import qd_ed_n25_validation_recovery as recovery
    from scripts import qd_ed_n25_report as reporting
    parent=original_plan();review=read_ref(ref(DEV_REVIEW))
    require(set(review)=={'schema','disposition','dev_plan','dev_status','dev_result','dev_source_bridge','allow_validation'}
        and review['schema']=='n25-dev-promotion-review-v1' and review['disposition']=='promoted'
        and review['allow_validation'] is True and same_ref(review['dev_plan'],ref(DEV_PLAN))
        and same_ref(review['dev_status'],ref(DEV_STATUS)) and same_ref(review['dev_result'],ref(DEV_RESULT)),
        'N25 validation root review of actual Dev promotion missing')
    result=read_ref(review['dev_result']);status=read_ref(review['dev_status'])
    require(result.get('schema')=='n25-dev-cohort-result-v1' and result.get('cohort_id')==dev.COHORT
        and result.get('source_commit')==DEV_COMMIT and result.get('planned')==result.get('audited_cells')==40
        and result.get('dev_gate_promoted') is True and result.get('decision')=='ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION'
        and result.get('goal_status')=='TARGET_NOT_MET' and result.get('controller_evidence',{}).get('consistent') is True,
        'N25 validation incomplete/invalid/rejected Dev cannot promote')
    terminal=result.get('terminal_status',{})
    require(set(terminal)=={'path','sha256','content'} and same_ref({k:terminal[k] for k in ('path','sha256')},review['dev_status'])
        and terminal['content']==status and status.get('schema')=='n25-dev-supervisor-status-v1'
        and status.get('status')=='completed_all_forty_audited' and status.get('cohort_id')==dev.COHORT
        and status.get('source_commit')==DEV_COMMIT and same_ref(status.get('plan'),ref(DEV_PLAN))
        and status.get('dev_gate_promoted') is True and status.get('completed_keys')==[v['episode_key'] for v in parent['episodes']],
        'N25 validation actual terminal status differs')
    source={v['path']:v['sha256'] for v in parent['code_files']}
    reader=Path(root)/'scripts/qd_ed_n25_report.py'
    require(sha(reader)==source['scripts/qd_ed_n25_report.py'] and same_ref(result.get('reader'),ref(reader))
        and same_ref(result.get('plan'),ref(DEV_PLAN)) and result.get('source_bridge')==review['dev_source_bridge'],
        'N25 validation Dev reader/source provenance differs')
    events=r['read_events'](Path(root)/'data/attempt-ledger.jsonl')
    local=[e for e in events if e.get('identity',{}).get('iteration')==dev.COHORT]
    require(read_ref(result['ledger_snapshot'])==local,'N25 validation Dev-only terminal snapshot differs')
    evidence.historical_backend(review['dev_source_bridge'],parent,events,
        r['read_events'](Path(root)/'data/gpu-healthcheck-ledger.jsonl'),r)
    def accept(row,local):
        final=recovery.historical_dev_cell(parent,row,local,root,r);out=Path(final['output_dir'])
        report=evidence.historical_receipt(final,row,parent,ref(DEV_PLAN),r)
        counts,aux=native.from_output(row['profile'],out,report,final.get('guided_chunks'))
        return {'episode_key':row['episode_key'],'task_id':row['task_id'],'profile':row['profile'],'attempt_id':final['attempt_id'],
            'success':final['success'],'audit':ref(out/'eds_eval/decision-evidence-audit.json'),
            'worker_context':ref(out/'n23-worker-context.json'),'worker_receipt':ref(out/'eds_eval/in-worker-audit-receipt.json'),
            'attempt_result':ref(out/'attempt-result.json')},counts,aux
    rebuilt=reporting.analyze(parent,local,accept)
    require(rebuilt['dev_gate_promoted'] is True and rebuilt['audited_cells']==40 and 40<=rebuilt['dispatched']<=42
        and all(result.get(k)==v for k,v in rebuilt.items()),'N25 validation independently reconstructed Dev promotion/cost differs')
    prefix=[x['episode_key'] for x in rebuilt['accepted_cells']]
    require(result['controller_evidence']=={'completed_keys':prefix,'journal_accepted_keys':prefix,'consistent':True,'status_phase':'completed_all_forty_audited'},
        'N25 validation Dev controller disagreement')
    outcomes=[{'episode_key':x['episode_key'],'task_id':x['task_id'],'profile':x['profile'],'success':x['success'],
        'attempt_id':x['attempt_id'],'recovered':bool(next(a['terminal'].get('retry_of') for a in rebuilt['attempts'] if a['attempt_id']==x['attempt_id']))} for x in rebuilt['accepted_cells']]
    require(status['attempts']==rebuilt['attempts'] and status['outcomes']==outcomes
        and status['successes']=={a:rebuilt['counts'][a]['success'] for a in dev.ARMS}
        and status['native']==rebuilt['native'] and status['auxiliary']==rebuilt['auxiliary']
        and all(status.get(k)==v for k,v in reporting.summary(outcomes,rebuilt['attempts']).items()),
        'N25 validation all-attempt costs/native/status reconciliation differs')
    return ref(DEV_REVIEW)


def review_source(source,source_bridge,parent):
    record=read_ref(ref(SOURCE_REVIEW))
    require(record=={'schema':'n25-validation-source-review-v1','disposition':'accepted','dev_plan':ref(DEV_PLAN),
        'protocol':ref(PROTOCOL),'routing_addendum':ref(ROUTING_ADDENDUM),'source':source,'source_bridge':source_bridge,
        'runtime':{'path':parent['runtime_manifest_path'],'sha256':parent['runtime_manifest_sha256']},
        'dev_source_bridge':read_ref(ref(DEV_REVIEW))['dev_source_bridge'],'no_execution_release':True},
        'N25 validation exact root source review missing')
    return ref(SOURCE_REVIEW)


def authority(source,source_bridge,parent,state=None):
    record=read_ref(ref(AUTHORITY))
    require(set(record)=={'schema','cohort_id','seed_cohort','source','dev_review','source_review','protocol','routing_addendum','runtime','limits','caps',
        'recorded_at','authority_interpretation','validation_authorized','formal_authorized'}
        and record['schema']=='n25-validation-authority-v1' and record['cohort_id']==COHORT and record['seed_cohort'] in {'c1','c2','c3','c4'}
        and record['source']==source and record['dev_review']==ref(DEV_REVIEW)
        and record['source_review']==review_source(source,source_bridge,parent) and record['protocol']==ref(PROTOCOL)
        and record['routing_addendum']==ref(ROUTING_ADDENDUM)
        and record['runtime']=={'path':parent['runtime_manifest_path'],'sha256':parent['runtime_manifest_sha256']}
        and record['limits']==LIMITS and record['caps']==CAPS
        and all(isinstance(record[k],str) and record[k].strip() for k in ('recorded_at','authority_interpretation'))
        and record['validation_authorized'] is True and record['formal_authorized'] is False,
        'N25 separate finite validation authority missing/differs')
    if state is not None:require(state.get('n25_validation_authority')==ref(AUTHORITY),'N25 validation authority not adopted')
    return ref(AUTHORITY)


def require_budget_state(state,r):
    dev.require_budget_state(state,r)
    require(dev.budget_authority()['caps']==CAPS,'N25 validation exact494 finite caps differ')
    parent=original_plan();source,source_bridge=source_record(r['ROOT'],parent)
    authority(source,source_bridge,parent,state)


def validate_contract(plan,profiles,runtime,seeds,root,r):
    from scripts import qd_ed_n25_validation_identity as identity
    from scripts import qd_ed_n25_validation_prepare as prepare
    require(plan==read(VALIDATION_PLAN) and plan.get('frozen') is True,'N25 validation exact frozen plan missing')
    parent=original_plan();source,source_bridge=source_record(root,parent);meta=plan.get('n25_validation',{})
    require(sha(PROTOCOL)==PROTOCOL_SHA and sha(ROUTING_ADDENDUM)==ROUTING_SHA and meta.get('schema')=='n25-protected-validation-v1' and meta.get('cohort_id')==COHORT
        and meta.get('limits')==LIMITS and meta.get('protocol')==ref(PROTOCOL)
        and meta.get('routing_addendum')==ref(ROUTING_ADDENDUM)
        and meta.get('dev_review')==dev_promotion(root,r) and meta.get('source_review')==review_source(source,source_bridge,parent)
        and meta.get('authority')==authority(source,source_bridge,parent) and meta.get('source_bridge')==source_bridge,
        'N25 validation promotion/source/authority differs')
    expected=prepare.build_plan(parent,seeds,meta['seed_cohort'],source=source,source_bridge=source_bridge,
        dev_review=meta['dev_review'],source_review=meta['source_review'],authorization=meta['authority'],selection=meta['metadata_selection'])
    expected['frozen']=True
    require(plan==expected and plan['n25_cohort']==WORKER_MARKER and set(profiles['profiles'])==set(ARMS)
        and plan['phase_authorization']=={'dev':False,'validation':True,'formal':False},'N25 validation exact evaluation-only matrix differs')
    require(plan['candidate_profiles']['N25']==parent['candidate_profiles']['N25']
        and runtime==read(parent['runtime_manifest_path']),'N25 validation scientific profile/runtime changed')
    dev.validate_runtime(runtime,root,r)
    selection=identity.metadata(root,parent)
    require(identity.first_unused(*selection[:4],allow_own=True)==meta['seed_cohort'],'N25 validation first fresh cohort changed')
    state=r['read_state'](Path(root)/'research-state.yaml');require_budget_state(state,r)
    require(read_ref(state['n25_validation_authority'])['seed_cohort']==meta['seed_cohort'],'N25 validation adopted seed cohort differs')


def validate_worker_context(context,argv,root,output,plan,runtime):
    from scripts import qd_ed_final_runner as runner
    meta=plan.get('n25_validation',{});matches=[x for x in plan['episodes'] if x['episode_key']==context['episode_key']]
    require(plan.get('frozen') is True and same_ref(context['plan'],ref(VALIDATION_PLAN))
        and meta.get('schema')=='n25-protected-validation-v1' and meta.get('cohort_id')==COHORT and meta.get('limits')==LIMITS
        and plan.get('n25_cohort')==WORKER_MARKER and plan['phase_authorization']=={'dev':False,'validation':True,'formal':False}
        and context['profile'] in ARMS and len(matches)==1 and matches[0]['profile']==context['profile']
        and matches[0]['split']=='validation' and matches[0]['iteration']==COHORT and matches[0]['timeout_seconds']==1800,
        'N25 validation worker exact phase/arm/identity differs')
    require(plan['worktree']==str(root) and output==Path(plan['artifact_root']).resolve()/'attempts'/context['attempt_id']
        and context['runtime']=={'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']},
        'N25 validation worker root/runtime differs')
    command,expected=runner.build_command(plan,manifest(plan,vars(runner)),runtime,matches[0],context['attempt_id'])
    require(command[1:]==list(argv) and Path(expected).resolve()==output,'N25 validation worker original Hydra arguments differ')
    source,source_bridge=source_record(root,original_plan())
    require(context['source']==source and plan['source_commit']==source['commit'] and plan['code_files']==source['files']
        and meta['source_bridge']==source_bridge and meta['source_review']==review_source(source,source_bridge,original_plan())
        and w.cuda_binding(runtime)=={'physical_gpu':7,'uuid':GPU7_UUID,'logical_device':'cuda:0'},
        'N25 validation worker science source bridge differs')
    w.verify_source(root,source)
    return root,output,runtime


@contextmanager
def supervised_scope(plan,root,key,*,eligibility=None):
    global _SCOPE
    require(_SCOPE is None,'N25 validation nested scope')
    _SCOPE=(str(Path(root).resolve()),plan['source_commit'],key,os.getpid(),threading.get_ident(),eligibility)
    try:yield
    finally:_SCOPE=None


def require_scope(plan,root,r,row=None):
    require(_SCOPE is not None and _SCOPE[:2]==(str(Path(root).resolve()),plan['source_commit'])
        and _SCOPE[3:5]==(os.getpid(),threading.get_ident()) and (row is None or row['episode_key']==_SCOPE[2]),
        'N25 validation exact one-cell supervisor required')


def primary_row(plan,row):
    matches=[x for x in plan['episodes'] if x['episode_key']==row['episode_key']];require(len(matches)==1,'N25 validation unknown cell')
    primary=matches[0];key='n25_validation_recovery_eligibility'
    require(row==primary or (set(row)==set(primary)|{'retry_of',key} and row['budget_bucket']=='recovery'
        and {k:row[k] for k in primary if k!='budget_bucket'}=={k:v for k,v in primary.items() if k!='budget_bucket'}),
        'N25 validation recovery changed science')
    return primary


def effective_row(plan,row,events,root,r):
    from scripts import qd_ed_n25_validation_recovery as recovery
    require_scope(plan,root,r,row)
    if _SCOPE[5] is None:return row
    record=recovery.verify_eligibility(_SCOPE[5],plan,row,events,root,r)
    return {**row,'budget_bucket':'recovery','retry_of':record['primary_attempt_id'],'n25_validation_recovery_eligibility':_SCOPE[5]}


def full_capacity(state,events,resources,r):
    require_budget_state(state,r);snap=r['budget_snapshot'](events,resources)
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    dispatched=[e for e in local if e['event']=='dispatched'];primary=sum(not e.get('retry_of') for e in dispatched)
    recovered={e['attempt_id'] for e in local if e.get('retry_of')}
    spent=sum(e.get('gpu_process_wall_seconds',0.) for e in local if e['event'] in r['TERMINAL'])/3600
    require(primary<=60 and len(recovered)<=2 and len(dispatched)<=62 and spent<=32.,'N25 validation local finite cap exceeded')
    require(snap['running']==snap['gpu_healthcheck_inflight']==0 and all(g[-1]['event'] in r['TERMINAL'] for g in r['event_groups'](events).values()),
        'N25 validation unsettled reservation/worker')
    needs={'validation':60-primary,'recovery':2-len(recovered)}
    require(all(state['budget']['reserved'][b]-snap['by_bucket'][b]>=n for b,n in needs.items()),'N25 full validation/recovery capacity missing')
    formal=max(0,40-snap['by_bucket']['formal']);formal_hours=max(0.,12.-snap['gpu_hours_by_bucket']['formal'])
    require(snap['dispatched']+sum(needs.values())+formal<=494 and snap['gpu_hours_consumed']+max(0.,32.-spent)+formal_hours<=100.+1e-9,
        'N25 full remaining validation would borrow formal reserve')


def protected_budget(state,events,resources,row,timeout,r,*,plan):
    primary_row(plan,row)
    require(row['iteration']==COHORT and row['profile'] in ARMS and row['split']=='validation' and timeout==1800,'N25 validation row/timeout differs')
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    require(sum(e['event']=='dispatched' for e in local)<62
        and sum(e.get('gpu_process_wall_seconds',0.) for e in local if e['event'] in r['TERMINAL'])+1840<=32*3600,
        'N25 validation local time/dispatch ceiling')
    full_capacity(state,events,resources,r)


def read_worker_report(output,r):return dev.read_worker_report(output,r)


def accepted_cell(plan,row,events,root,r):
    from scripts import qd_ed_n25_validation_recovery as recovery
    return recovery.accepted_cell(plan,row,events,root,r)


def admission(plan,runtime,row,events,resources,root,r):
    from scripts import qd_ed_n25_validation_recovery as recovery
    primary=primary_row(plan,row);index=plan['episodes'].index(primary)
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    allowed={x['episode_key'] for x in plan['episodes'][:index]}|({row['episode_key']} if row.get('retry_of') else set())
    require(all(e.get('episode_key') in allowed for e in local),'N25 validation exact prefix required')
    for previous in plan['episodes'][:index]:accepted_cell(plan,previous,events,root,r)
    if row.get('retry_of'):recovery.verify_eligibility(row['n25_validation_recovery_eligibility'],plan,primary,events,root,r)
    return {'n25_validation_cohort_id':COHORT,'n25_validation_seed_block':row['seed_block'],'n25_validation_protocol_sha256':PROTOCOL_SHA,
        **({'n25_validation_recovery_eligibility':row['n25_validation_recovery_eligibility']} if row.get('retry_of') else {})}
