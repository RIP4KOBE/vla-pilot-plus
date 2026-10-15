"""Closed N25 Dev admission; root review/adoption/release are external artifacts."""
from contextlib import contextmanager
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import threading

from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n25_native as native

ROOT=Path(__file__).resolve().parents[1]
SESSION=ROOT.parent if ROOT.name=='study_worktree' else ROOT.parents[2]
RUN_DIR=SESSION/'variants/n25_actuator_clipped_rbf'
SOURCE_PLAN=SESSION/'variants/n23_actuator_clipped_quality/plan.frozen.v2.gpu7.json'
SOURCE_PLAN_SHA='acd2b2c639f7756cdc353b6a7eea8c93a4d735a8ce6ee25838d9502c938d07f0'
PROTOCOL=RUN_DIR/'conditional-dev-controller-protocol-v1.md'
PROTOCOL_SHA='868fe8040cf5c5d9c962dd5177335f7ad78a94a17de0f60560ad489829a5b465'
OBSERVABILITY=SESSION/'variants/n23_actuator_clipped_quality/timeout-observability-addendum-v2.md'
OBSERVABILITY_SHA='fa0723919c67d0417b101be2a36d9832cfaaf15e4b1c4e0cdfbf61caa43e34c6'
FINAL_REVIEW=RUN_DIR/'final-source-runtime-review-v1.json'
AUTHORITY=RUN_DIR/'adoption-v1/authority.json'
BRIDGE=RUN_DIR/'source-equivalence-bridge-v1.json'
PHASE_A='aadec3f7435f31c60b74f709efb61427c3b829c7'
BASE='51104470983cdbafd08feb87f2f39b7553779405'
COHORT='N25_ACTUATOR_CLIPPED_RBF_DEV_20260930'
PREFLIGHT='N25_TENSOR_RESOURCE_20260930'
ARMS=('C0','Q0','N23','N25')
LIMITS={'primary_cells':40,'episode_dispatches':42,'recoveries':2,'recoveries_per_cell':1,
 'maximum_local_gpu_hours':22.,'episode_timeout_seconds':1800,'cleanup_seconds':40,'physical_gpu':7}
BASE_CAPS={'attempts':478,'gpu_hours':100.,'buckets':{'baseline':51,'development':187,'validation':180,'formal':40,'recovery':20},
 'protected_gpu_hours':{'validation':32.,'formal':12.}}
PREDECESSOR=RUN_DIR/'predecessor-review-v1.json'
BUDGET_AUTHORITY=RUN_DIR/'budget-adoption-v1/authority.json'
BACKEND_PROOF=RUN_DIR/'arithmetic-preflight/proof-v1.json'
ARITHMETIC_PROTOCOL=RUN_DIR/'independent-arithmetic-protocol-v1.md'
GPU7_UUID='GPU-48473162-9548-1a19-04aa-ea86c5349187'
GPU7_PROOF='rdt-qd-ed-final-20260921T093925Z__gpu7_cuda_egl__4fafff3673e5'
WORKER_CONTRACT={'schema':'n25-same-process-native-audit-v1','arms':list(ARMS),
 'cuda_arithmetic_arms':['N23','N25'],'other_arm_backend':'cpu','timeout_includes_audit':True,
 'profile_bound_rbf_audit':True,'witness_exact_backend':'assigned_cuda'}
EXTRA_SOURCE={f'scripts/qd_ed_n25_{name}.py' for name in ('contract','prepare','supervise','report','recovery','native','bridge','reference','backend','preflight')}
EXTRA_SOURCE|={'tests/test_qd_ed_n25_arithmetic.py','tests/test_qd_ed_n25_native.py','tests/test_qd_ed_n25_controller.py',
 'tests/test_qd_ed_n25_backend.py','tests/test_qd_ed_n25_recovery.py','tests/n25_cpu_synthetic.py'}
PHASE_A_MANIFEST='docs/03_evidence/qd_ed_final/n25/phase-a-source-manifest-v2.json'
CONTROLLER_DELTA=EXTRA_SOURCE|{'scripts/qd_ed_final_runner.py','scripts/qd_ed_n23_worker.py',PHASE_A_MANIFEST,
 'docs/03_evidence/qd_ed_final/n25/conditional-dev-controller-protocol-v1.md',
 'docs/03_evidence/qd_ed_final/n25/independent-arithmetic-protocol-v1.md',
 'docs/03_evidence/qd_ed_final/n25/controller-contract-v1.md',
 'docs/03_evidence/qd_ed_final/n25/shared-route-insertions-v1.json'}
EXTRA_SOURCE|={p for p in CONTROLLER_DELTA if p.startswith('docs/')}
ref=lambda path:{'path':str(Path(path).resolve()),'sha256':w.sha(path)}
_SCOPE=None


def original_plan():
    w.require(w.sha(SOURCE_PLAN)==SOURCE_PLAN_SHA,'N25 frozen source plan drift')
    return w.read_ref(ref(SOURCE_PLAN))


def runtime_ref():
    plan=original_plan()
    return {'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']}


def expected_rows():
    rows=original_plan()['episodes']
    w.require(len(rows)==40 and [(x['task_id'],x['profile']) for x in rows]==[(t,a) for t in range(10) for a in ('C0','Q0','N7','N23')],
              'N25 original task-major identities differ')
    result=[]
    for t in range(10):
        for arm,source in zip(ARMS,rows[t*4:t*4+4]):
            row=copy.deepcopy(source)
            row.update(iteration=COHORT,profile=arm,episode_key=f'n25_dev_t{t:02d}_{arm.lower()}_20260930')
            w.require(row['split']==row['seed_block']=='dev' and row['timeout_seconds']==1800
                and row['budget_bucket']==('baseline' if arm=='C0' else 'development') and 'retry_of' not in row,'N25 frozen row scope differs')
            result.append(row)
    return result


def source_paths(r):
    phase_a=w.read_ref(ref(Path(r['ROOT'])/PHASE_A_MANIFEST))
    w.require(phase_a['commit']==PHASE_A,'N25 Phase A manifest differs')
    return {v['path'] for v in phase_a['files']} | r['REQUIRED_CODE'] | w.REQUIRED_SOURCE | EXTRA_SOURCE



def imports_owned(root,r):
    root=Path(root).resolve()
    for path in (__file__,w.__file__,native.__file__,r['__file__']):
        w.require(Path(path).resolve().is_relative_to(root),'N25 adjacent-worktree module shadowing')


def final_review(source,runtime,root):
    from scripts import qd_ed_n25_bridge as bridge
    from scripts import qd_ed_n25_backend as backend
    require_protocols(root)
    bound=bridge.verify(ref(BRIDGE),source,runtime,root)
    proof=backend.verify_proof(ref(BACKEND_PROOF),source,runtime,root)
    record=w.read_ref(ref(FINAL_REVIEW))
    expected={'schema':'n25-source-runtime-review-v1','disposition':'accepted','source':source,'runtime':runtime,
      'protocol':ref(PROTOCOL),'source_plan':ref(SOURCE_PLAN),'source_bridge':ref(BRIDGE),
      'predecessor':predecessor(),'backend_proof':ref(BACKEND_PROOF),
      'arithmetic_protocol':ref(ARITHMETIC_PROTOCOL),'no_gpu_release':True}
    w.require(record==expected and bound['new_source']==source and proof['accepted'] is True,'N25 final root review differs')
    return ref(FINAL_REVIEW)



def authority(source,runtime,root,state=None):
    record=w.read_ref(ref(AUTHORITY));caps=budget_authority()
    keys={'schema','cohort_id','source','runtime','protocol','final_review','budget_authority','limits','local_gpu_hours',
          'recorded_at','authority_interpretation','validation_authorized','formal_authorized'}
    local=record.get('local_gpu_hours')
    w.require(set(record)==keys and record['schema']=='n25-dev-authority-v1' and record['cohort_id']==COHORT
        and record['source']==source and record['runtime']==runtime and record['protocol']==ref(PROTOCOL)
        and record['final_review']==final_review(source,runtime,root) and record['limits']==LIMITS
        and record['budget_authority']==ref(BUDGET_AUTHORITY)
        and type(local) in (int,float) and math.isfinite(local) and 1840/3600<=local<=22.
        and all(isinstance(record[k],str) and record[k].strip() for k in ('recorded_at','authority_interpretation'))
        and record['validation_authorized'] is False and record['formal_authorized'] is False,'N25 finite authority differs')
    if state is not None:w.require(state.get('n25_dev_authority')==ref(AUTHORITY),'N25 authority not adopted')
    return ref(AUTHORITY)



def require_state(state,r):
    require_budget_state(state,r)
    reference=state.get('n25_dev_authority');w.require(reference==ref(AUTHORITY),'N25 adoption missing')
    record=w.read_ref(reference);authority(record['source'],record['runtime'],Path(r['ROOT']),state)



def full_capacity(state,events,resources,r):
    require_state(state,r);snap=r['budget_snapshot'](events,resources);caps=budget_authority()['caps']
    from scripts import qd_ed_n25_bridge as bridge
    from scripts import qd_ed_n25_backend as backend
    bridge.settled_backend(w.read_ref(ref(BRIDGE)),events,r)
    backend.settled_proof(w.read_ref(ref(BACKEND_PROOF)),resources,r)
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    charged=[e for e in local if e['event']=='dispatched'];recoveries={e['attempt_id'] for e in local if e.get('retry_of')}
    spent=sum(e.get('gpu_process_wall_seconds',0.) for e in local if e['event'] in r['TERMINAL'])/3600
    remaining={b:need-sum(e['budget_bucket']==b for e in charged) for b,need in (('baseline',10),('development',30))}
    w.require(len(charged)<=42 and len(recoveries)<=2 and all(v>=0 for v in remaining.values()),'N25 local counts exceeded')
    remaining['recovery']=2-len(recoveries)
    protected_hours=sum(max(0.,h-snap['gpu_hours_by_bucket'][b]) for b,h in caps['protected_gpu_hours'].items())
    protected_attempts=sum(max(0,caps['buckets'][b]-snap['by_bucket'][b]) for b in ('validation','formal'))
    w.require(snap['running']==snap['gpu_healthcheck_inflight']==0
        and all(g[-1]['event'] in r['TERMINAL'] for g in r['event_groups'](events).values()),'N25 unsettled owner/journal')
    local_cap=w.read_ref(ref(AUTHORITY))['local_gpu_hours']
    w.require(spent<=local_cap and snap['gpu_hours_consumed']+max(0.,local_cap-spent)+protected_hours<=100.+1e-9
        and all(caps['buckets'][b]-snap['by_bucket'][b]>=n for b,n in remaining.items())
        and snap['dispatched']+sum(remaining.values())+protected_attempts<=caps['attempts'],
        'N25 finite remaining cohort capacity borrows protected reserves')



@contextmanager
def supervised_scope(plan,root,episode_key,*,eligibility=None):
    global _SCOPE
    w.require(_SCOPE is None,'N25 nested scope')
    _SCOPE=(str(Path(root).resolve()),plan['source_commit'],episode_key,os.getpid(),threading.get_ident(),eligibility)
    try:yield
    finally:_SCOPE=None


def require_scope(plan,root,r,row=None):
    w.require(_SCOPE is not None and _SCOPE[:2]==(str(Path(root).resolve()),plan['source_commit'])
        and _SCOPE[3:5]==(os.getpid(),threading.get_ident()) and (row is None or row['episode_key']==_SCOPE[2]),
        'N25 requires exact single-cell owned scope')


def primary_row(plan,row):
    matches=[v for v in plan['episodes'] if v['episode_key']==row['episode_key']]
    w.require(len(matches)==1,'N25 unknown scientific cell');primary=matches[0]
    w.require(row==primary or (set(row)==set(primary)|{'retry_of','n25_recovery_eligibility'} and row['budget_bucket']=='recovery'
        and {k:row[k] for k in primary if k!='budget_bucket'}=={k:v for k,v in primary.items() if k!='budget_bucket'}),
        'N25 recovery row changed science')
    return primary


def effective_row(plan,row,events,root,r):
    require_scope(plan,root,r,row)
    if _SCOPE[5] is None:return row
    from scripts import qd_ed_n25_recovery as recovery
    record=recovery.verify_eligibility(_SCOPE[5],plan,row,events,root,r)
    return {**row,'budget_bucket':'recovery','retry_of':record['primary_attempt_id'],'n25_recovery_eligibility':_SCOPE[5]}


def protected_budget(state,events,resources,row,timeout,r,*,plan):
    primary_row(plan,row)
    w.require(row['iteration']==COHORT and row['profile'] in ARMS and timeout==1800,'N25 row/timeout differs')
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    cap=w.read_ref(ref(AUTHORITY))['local_gpu_hours']
    w.require(sum(e['event']=='dispatched' for e in local)<42
        and sum(e.get('gpu_process_wall_seconds',0.) for e in local if e['event'] in r['TERMINAL'])+1840<=cap*3600,
        'N25 local attempt/hour cap: incomplete, never numeric rejection')
    full_capacity(state,events,resources,r)



def validate_runtime(runtime,root,r):
    w.require(runtime==w.read_ref(runtime_ref()) and Path(runtime['worktree']).resolve()==Path(root).resolve()
        and runtime.get('schema')=='qd-ed-runtime-setup-v1' and r['runtime_gpu'](runtime)==7
        and runtime['gpu_mapping']['uuid']==GPU7_UUID and runtime['gpu_mapping']['egl_device_index']==4
        and runtime.get('cuda_egl_verified') is True and runtime.get('cuda_egl_probe',{}).get('resource_id')==GPU7_PROOF
        and runtime.get('stage_recovered_error_condition')==r['E2_STAGE_CONDITION']
        and runtime.get('stage_engineering_condition')==r['n4e1_support']().engineering_condition()
        and runtime['frozen_stage_provider'].get('allow_recovered_error_events') is True,
        'N25 frozen runtime/GPU/provider differs')
    r['verify_files'](runtime['files'],allowed_roots=(Path(root),Path(runtime['worktree']),runtime['artifact_root']))


def metadata(source,root):
    runtime=runtime_ref()
    return {'schema':'n25-actuator-clipped-rbf-dev-v1','cohort_id':COHORT,'limits':LIMITS,
        'protocol':ref(PROTOCOL),'source_plan':ref(SOURCE_PLAN),'timeout_observability':ref(OBSERVABILITY),
        'final_review':final_review(source,runtime,root),'authority':authority(source,runtime,root),
        'worker_audit':WORKER_CONTRACT,'n23_role':'ablation_control_only_no_promotion',
        'early_stop':'numeric_futility_after_complete_task_quadruple'}


def validate_contract(plan,manifest,runtime,seeds,root,r):
    imports_owned(root,r)
    source=w.source_record(root,[v['path'] for v in plan['code_files']])
    w.require(source['commit']==plan['source_commit'] and source['files']==plan['code_files']
        and source_paths(r)<={v['path'] for v in plan['code_files']},'N25 complete committed source missing')
    w.require(plan.get('n25_cohort')==metadata(source,root) and plan['episodes']==expected_rows()
        and set(plan['candidate_profiles'])=={'N23','N25'} and set(manifest['profiles'])==set(ARMS)
        and plan.get('phase_authorization')=={'dev':True,'validation':False,'formal':False}
        and plan.get('stage_condition')==r['E2_STAGE_CONDITION']
        and not any(k.startswith(('n7_','n9_','n11_','n17_','n18_','n19_','n20_','n21_','n22_','n23_','n24_')) for k in plan),
        'N25 closed prospective matrix/phase differs')
    for arm in ('N23','N25'):
        path=Path(root)/f'configs/qd_ed_final/candidate_{arm.lower()}.json'
        w.require(plan['candidate_profiles'][arm]==ref(path) and str(path.relative_to(root)) in plan['scientific_config_files'],
            'N25 profile fingerprint missing')
    n23=manifest['profiles']['N23']['resolved_eds_config'];n25=manifest['profiles']['N25']['resolved_eds_config']
    w.require(n25=={**n23,'initial_diversity_descriptor_mode':native.MODE,'rollout_diversity_descriptor_mode':native.MODE},'N25 sole science delta differs')
    w.require({'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']}==runtime_ref(),'N25 runtime ref differs')
    validate_runtime(runtime,root,r);require_state(r['read_state'](Path(root)/'research-state.yaml'),r)


def validate_worker_context(context,argv,root,output,plan,runtime):
    w.require(plan.get('frozen') is True and plan.get('n25_cohort',{}).get('worker_audit')==WORKER_CONTRACT
        and plan['worktree']==str(root) and context['profile'] in ARMS
        and output==Path(plan['artifact_root']).resolve()/'attempts'/context['attempt_id']
        and context['runtime']=={'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']},
        'N25 worker frozen plan/runtime differs')
    rows=[r for r in plan['episodes'] if r['episode_key']==context['episode_key']]
    w.require(len(rows)==1 and rows[0]['profile']==context['profile'] and rows[0]['split']=='dev'
        and rows[0]['iteration']==COHORT and rows[0]['timeout_seconds']==1800
        and context['source']['commit']==plan['source_commit'] and context['source']['files']==plan['code_files'],
        'N25 worker row/source differs')
    w.verify_source(root,context['source'])
    w.require(w.cuda_binding(runtime)['physical_gpu']==7,'N25 worker GPU differs')
    return root,output,runtime


def read_worker_report(output,r):
    return w.verify_receipt(Path(output)/'n23-worker-context.json',r['read_json'](Path(output)/'process.json'))


def accepted_cell(plan,row,events,root,r):
    from scripts import qd_ed_n25_recovery as recovery
    groups=list(r['event_groups']([e for e in events if e.get('identity',{}).get('iteration')==COHORT
        and e.get('episode_key')==row['episode_key']]).values())
    w.require(1<=len(groups)<=2,'N25 missing/duplicate cell')
    first=groups[0][-1];w.require(groups[0][0].get('retry_of') is None and first['event'] in r['TERMINAL'],'N25 primary unsettled')
    final=first
    if len(groups)==2:
        final=groups[1][-1];reference=groups[1][0].get('n25_recovery_eligibility')
        w.require(first.get('outcome_valid') is False and final.get('retry_of')==first['attempt_id']
            and final['budget_bucket']=='recovery' and reference is not None,'N25 first-valid lineage differs')
        boundary=next(i for i,e in enumerate(events) if e['attempt_id']==final['attempt_id'])
        recovery.verify_eligibility(reference,plan,row,events[:boundary],root,r)
    w.require(final['event']=='valid' and final.get('outcome_valid') is True
        and final.get('required_cost_telemetry_complete') is True,'N25 invalid primary/recovery cannot count')
    context=w.read_ref(ref(Path(final['output_dir'])/'n23-worker-context.json'))
    recovery.terminal_binding(final,row,plan,context['plan'],r)
    w.require(w.read_ref(context['plan'])==plan and w.read_ref(ref(Path(final['output_dir'])/'attempt-result.json'))==final
        and final.get('n23_worker_receipt')==ref(Path(final['output_dir'])/'eds_eval/in-worker-audit-receipt.json'),
        'N25 accepted terminal/plan/receipt differs')
    report=read_worker_report(final['output_dir'],r)
    w.require(type(final.get('guided_chunks')) is int,'N25 accepted guided count missing')
    native.from_output(row['profile'],final['output_dir'],report,final['guided_chunks'])
    return final


def admission(plan,runtime,row,events,resources,root,r):
    primary=primary_row(plan,row);index=plan['episodes'].index(primary)
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    allowed={v['episode_key'] for v in plan['episodes'][:index]}|({row['episode_key']} if row.get('retry_of') else set())
    w.require(all(e.get('episode_key') in allowed for e in local),'N25 exact prefix required')
    successes=sum(int(accepted_cell(plan,prior,events,root,r)['success'] is True) for prior in plan['episodes'][:index]
                  if prior['profile']=='N25')
    for prior in plan['episodes'][:index]:
        if prior['profile']!='N25':accepted_cell(plan,prior,events,root,r)
    if row.get('retry_of'):
        from scripts import qd_ed_n25_recovery as recovery
        recovery.verify_eligibility(row['n25_recovery_eligibility'],plan,primary,events,root,r)
    w.require(successes+10-index//4>=5,'N25 complete-quadruple numeric futility')
    return {'n25_cohort_id':COHORT,'n25_protocol_sha256':PROTOCOL_SHA,
        'n25_arm_role':'candidate' if row['profile']=='N25' else 'ablation_control_only' if row['profile']=='N23' else 'control',
        **({'n25_recovery_eligibility':row['n25_recovery_eligibility']} if row.get('retry_of') else {})}


def require_protocols(root):
    for path,expected in ((PROTOCOL,PROTOCOL_SHA),(OBSERVABILITY,OBSERVABILITY_SHA)):
        w.require(w.sha(path)==expected,'N25 immutable protocol changed')
    for name,path in (('conditional-dev-controller-protocol-v1.md',PROTOCOL),
                      ('independent-arithmetic-protocol-v1.md',ARITHMETIC_PROTOCOL)):
        w.require((Path(root)/'docs/03_evidence/qd_ed_final/n25'/name).read_bytes()==Path(path).read_bytes(),
                  'N25 tracked protocol differs')


def predecessor():
    record=w.read_ref(ref(PREDECESSOR))
    w.require(set(record)=={'schema','source_commit','dev_result','dev_root_review','disposition','validation_review','allow_n25'}
        and record['schema']=='n25-predecessor-review-v1' and record['source_commit']=='3b7afa02757eb3519d95547e4b6e6e939f7068f2'
        and record['allow_n25'] is True,'N25 exact predecessor review missing')
    dev=w.read_ref(record['dev_result']);review=w.read_ref(record['dev_root_review'])
    source=w.read_ref(review['source'])
    w.require(dev.get('source_commit')==record['source_commit'] and review.get('result')==record['dev_result']
        and review.get('schema')=='n24-root-terminal-review-v2'
        and review.get('decision')=='ACCEPT_TERMINAL_RECONSTRUCTION'
        and source.get('commit')==record['source_commit'] and len(source.get('files',[]))==230
        and source.get('sha256')==w.canonical_sha(source['files']) and review.get('source_files_verified')==230
        and review.get('cohort_disposition')==dev.get('decision')
        and review.get('accepted_cells')==dev.get('audited_cells')
        and review.get('counts')==dev.get('counts') and review.get('native')==dev.get('native')
        and review.get('plan')==dev.get('plan') and review.get('ledger')==dev.get('ledger_snapshot')
        and dev.get('controller_evidence',{}).get('consistent') is True,
        'N25 predecessor source/result root reconstruction differs')
    if record['disposition']=='VALID_DEV_REJECTION':
        w.require(dev.get('decision') in {'REJECT','REJECT_NUMERIC_FUTILITY'} and dev.get('dev_gate_promoted') is False
            and record['validation_review'] is None,'N25 predecessor not valid Dev rejection')
    else:
        w.require(record['disposition']=='VALID_VALIDATION_REJECTION' and dev.get('dev_gate_promoted') is True
            and dev.get('decision')=='ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION'
            and dev.get('audited_cells')==40,'N25 predecessor not promoted full Dev')
        validation=w.read_ref(record['validation_review'])
        w.require(validation=={'schema':'n25-predecessor-validation-aggregate-review-v1','dev_result':record['dev_result'],
            'source_commit':record['source_commit'],'all_cells_native_valid':True,'decision':'REJECT',
            'protected_per_task_results_consulted_for_n25':False},'N25 validation aggregate rejection missing')
    return ref(PREDECESSOR)


def budget_authority():
    record=w.read_ref(ref(BUDGET_AUTHORITY));caps=record.get('caps',{})
    w.require(set(record)=={'schema','cohort_id','caps','amendment','amendment_document','predecessor','recorded_at','authority_interpretation'}
        and record['schema']=='n25-finite-budget-authority-v1' and record['cohort_id']==COHORT
        and record['predecessor']==predecessor() and set(caps)==set(BASE_CAPS), 'N25 explicit finite budget authority missing')
    w.require(caps['gpu_hours']==100. and caps['protected_gpu_hours']==BASE_CAPS['protected_gpu_hours']
        and set(caps['buckets'])==set(BASE_CAPS['buckets'])
        and all(type(v) is int and v>=0 for v in caps['buckets'].values())
        and all(caps['buckets'][b]==BASE_CAPS['buckets'][b] for b in ('validation','formal','recovery'))
        and all(caps['buckets'][b]>=BASE_CAPS['buckets'][b] for b in ('baseline','development'))
        and type(caps['attempts']) is int and caps['attempts']==sum(caps['buckets'].values())
        and all(isinstance(record[k],str) and record[k].strip() for k in ('amendment','recorded_at','authority_interpretation')),
        'N25 finite caps/protected reserves differ')
    document=record['amendment_document'];w.require(set(document)=={'path','sha256'} and w.sha(document['path'])==document['sha256'],
        'N25 finite amendment document drift')
    return record


def require_budget_state(state,r):
    authority=budget_authority();caps=authority['caps'];budget=state['budget']
    resource=state.get('resource_isolation',{})
    w.require(resource.get('status')=='ACTIVE' and resource.get('validation_status')=='PASS'
        and resource.get('private_budget') is True and state.get('max_concurrent_gpu_workers')==1
        and not state.get('external_resource_hold',{}).get('do_not_auto_resume',False)
        and budget.get('gpu_hour_reservations')==caps['protected_gpu_hours']
        and state.get('n25_budget_authority')==ref(BUDGET_AUTHORITY)
        and budget['max_episode_attempts']==caps['attempts'] and budget['max_gpu_hours']==100.
        and budget['reserved']==caps['buckets'] and budget['amendment']==authority['amendment']
        and r['authorized_gpu'](state)==7,'N25 exact finite budget not adopted')


def expand_candidate(candidate,baseline,r):
    path=Path(r['ROOT'])/'configs/qd_ed_final/candidate_n25.json'
    w.require(candidate==r['read_json'](path) and candidate['algorithm_contract']=='n25_actuator_clipped_eef_rbf_v1'
        and candidate['baseline_reference']=='N23','N25 closed candidate differs')
    parent=candidate['parent_candidate'];parent_path=Path(r['ROOT'])/'configs/qd_ed_final/candidate_n23.json'
    w.require(parent=={'path':'configs/qd_ed_final/candidate_n23.json','sha256':w.sha(parent_path)},'N25 parent differs')
    old=r['read_json'](parent_path)
    modes={'initial_diversity_descriptor_mode':native.MODE,'rollout_diversity_descriptor_mode':native.MODE}
    w.require(candidate['profile']=={**old['profile'],**modes} and candidate['only_algorithm_change']=={
        k:{'before':'absolute_eef','after':v} for k,v in modes.items()},'N25 scientific delta differs')
    result=r['expand_candidate']('N23',old,baseline)
    result['historical_label']='N25';result['restored_profile']=copy.deepcopy(candidate['profile'])
    for k,v in modes.items():result['resolved_eds_config'][k]=v;result['static_override_values']['main.eds_config.'+k]=v
    result['hydra_overrides']=[f'{k}={r["hydra"](v)}' for k,v in result['static_override_values'].items()]
    return result
