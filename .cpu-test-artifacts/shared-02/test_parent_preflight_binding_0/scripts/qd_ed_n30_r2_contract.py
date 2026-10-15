"""One named N30 terminal Boolean repair; old INVALID is never a scientific outcome."""
import copy,json,re
from pathlib import Path
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n30_contract as old
from scripts import qd_ed_n30_native as native
from scripts import qd_ed_n30_r2_bridge as b
ROOT=Path(__file__).resolve().parents[1]
SESSION=ROOT.parent if ROOT.name=='study_worktree' else ROOT.parents[3]
PARENT=SESSION/'variants/n30_executed_progress_continuation'
RUN_DIR=PARENT/'feedback-repair-continuation-v1'
ARTIFACT_DIR=PARENT/'artifacts'
PROTOCOL=RUN_DIR/'cpu-integration-scope-v1.md'
PROTOCOL_SHA='e76f7c36a6339fb27f1c1e418f33990ed0278cd14080a35f0012010e26034cc9'
BRIDGE=RUN_DIR/'source-history-bridge-v1.json'
FINAL_REVIEW=RUN_DIR/'final-source-runtime-review-v1.json'
AUTHORITY=RUN_DIR/'adoption-v1/authority.json'
PLAN=RUN_DIR/'plan.frozen.v1.gpu7.json'
COHORT=b.COHORT
ARMS=b.ARMS
BASE_CAPS=old.BASE_CAPS
GPU7_UUID=old.GPU7_UUID
GPU7_PROOF=old.GPU7_PROOF
WORKER_CONTRACT=old.WORKER_CONTRACT
LIMITS={'logical_cells':12,'inherited_cells':2,'new_dispatches':10,'combined_dispatches':14,'named_recoveries':1,
 'new_buckets':{'baseline':3,'development':6,'recovery':1},'combined_gpu_hours':6.,'old_gpu_seconds':b.OLD_SECONDS,
 'episode_timeout_seconds':1800,'cleanup_seconds':40,'physical_gpu':7}
ref=old.ref
ResourceBudgetIncomplete=old.ResourceBudgetIncomplete
supervised_scope=old.supervised_scope
require_scope=old.require_scope
read_worker_report=old.read_worker_report


def expected_rows(h):
    rows=[]
    for index,original in enumerate(h['plan']['episodes'][2:]):
        row=copy.deepcopy(original);row.update(iteration=COHORT,episode_key=original['episode_key'].replace('n30_dev_','n30_r2_dev_'),
            original_episode_key=original['episode_key'])
        if index==0:row.update(budget_bucket='recovery',retry_of=b.FAILED)
        rows.append(row)
    return rows


def history():return b.history(ROOT)


def runtime_ref(h):return {'path':h['plan']['runtime_manifest_path'],'sha256':h['plan']['runtime_manifest_sha256']}


def source_paths(r):return b.source_paths(r['ROOT']) | r['REQUIRED_CODE'] | w.REQUIRED_SOURCE


def require_protocol(root):
    w.require(w.sha(PROTOCOL)==PROTOCOL_SHA and (Path(root)/b.DOC/'cpu-integration-scope-v1.md').read_bytes()==PROTOCOL.read_bytes(),'r2 frozen scope drift')


def final_review(source,runtime,root):
    require_protocol(root);bound=b.build(source,runtime,root)
    w.require(w.read_ref(ref(BRIDGE))==bound,'r2 immutable history/source bridge differs')
    expected={'schema':'n30-r2-source-runtime-review-v1','disposition':'accepted','source':source,'runtime':runtime,
        'protocol':ref(PROTOCOL),'source_bridge':ref(BRIDGE),'new_tensor_preflight':False,'no_gpu_release':True}
    w.require(w.read_ref(ref(FINAL_REVIEW))==expected,'r2 root final review differs');return ref(FINAL_REVIEW)


def authority(source,runtime,root,state=None):
    obj=w.read_ref(ref(AUTHORITY))
    expected={'schema':'n30-r2-authority-v1','cohort_id':COHORT,'source':source,'runtime':runtime,'protocol':ref(PROTOCOL),
        'final_review':final_review(source,runtime,root),'source_bridge':ref(BRIDGE),'limits':LIMITS,'caps':BASE_CAPS,
        'validation_authorized':False,'formal_authorized':False}
    w.require(set(obj)==set(expected)|{'recorded_at','authority_interpretation'} and all(obj[k]==v for k,v in expected.items())
        and all(isinstance(obj[k],str) and obj[k].strip() for k in ('recorded_at','authority_interpretation')),'r2 finite authority differs')
    if state is not None:w.require(state.get('n30_r2_authority')==ref(AUTHORITY),'r2 authority not adopted')
    return ref(AUTHORITY)


def require_state(state,r):
    h=history();budget=h['budget'];cap=state['budget'];isolation=state.get('resource_isolation',{})
    w.require(budget['schema']=='n29-finite-budget-authority-v1' and budget['caps']==BASE_CAPS
        and budget['validation_authorized'] is False and budget['formal_authorized'] is False
        and state.get('n29_budget_authority')==h['plan']['n30_cohort']['budget_reuse']
        and cap['max_episode_attempts']==578 and cap['max_gpu_hours']==100. and cap['reserved']==BASE_CAPS['buckets']
        and cap['gpu_hour_reservations']==BASE_CAPS['protected_gpu_hours'] and cap['amendment']==budget['amendment']
        and isolation.get('status')=='ACTIVE' and isolation.get('validation_status')=='PASS' and isolation.get('private_budget') is True
        and state.get('max_concurrent_gpu_workers')==1 and not state.get('external_resource_hold',{}).get('do_not_auto_resume',False)
        and r['authorized_gpu'](state)==7,'r2 current private resource/finite budget differs')
    obj=w.read_ref(ref(AUTHORITY));authority(obj['source'],obj['runtime'],r['ROOT'],state)


def local_seconds(events,resources,r):
    values=[e.get('gpu_process_wall_seconds') for e in events if e.get('identity',{}).get('iteration') in {b.OLD,b.R1,COHORT} and e['event'] in r['TERMINAL']]
    values += [e.get('gpu_process_wall_seconds') for e in resources if e.get('kind') in {'n30_resource_preparation_v1','n30_r1_resource_preparation_v1','n30_r2_resource_preparation_v1'} and e['event'] in {'completed','aborted'}]
    w.require(all(b.finite(v) for v in values),'r2 combined GPU cost unknown');return sum(values)


def full_capacity(state,events,resources,r):
    require_state(state,r);h=history();b.current_subset(h,events);snap=r['budget_snapshot'](events,resources)
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    charged=[e for e in local if e['event']=='dispatched']
    remaining={k:n-sum(e['budget_bucket']==k for e in charged) for k,n in LIMITS['new_buckets'].items()}
    w.require(len(charged)<=10 and all(n>=0 for n in remaining.values()) and snap['running']==snap['gpu_healthcheck_inflight']==0
        and all(g[-1]['event'] in r['TERMINAL'] for g in r['event_groups'](events).values()),'r2 unsettled/count limit')
    w.require(state['budget']['dispatched']==snap['dispatched'] and abs(state['budget']['gpu_hours_consumed']-snap['gpu_hours_consumed'])<1e-8,'r2 state/ledger mismatch')
    protected=sum(max(0.,v-snap['gpu_hours_by_bucket'][k]) for k,v in BASE_CAPS['protected_gpu_hours'].items())
    protected_slots=sum(max(0,BASE_CAPS['buckets'][k]-snap['by_bucket'][k]) for k in ('validation','formal'))
    w.require(all(BASE_CAPS['buckets'][k]-snap['by_bucket'][k]>=n for k,n in remaining.items())
        and snap['dispatched']+sum(remaining.values())+protected_slots<=578,'r2 finite remaining slot capacity')
    if local_seconds(events,resources,r)>21600 or snap['gpu_hours_consumed']+protected>100.+1e-9:
        raise ResourceBudgetIncomplete('r2 combined/cumulative budget exhausted')


def whole_attempt_hours(state,snap,row,r):
    w.require(row.get('iteration')==COHORT and row.get('timeout_seconds')==1800 and row.get('budget_bucket') in LIMITS['new_buckets'],'r2 whole-attempt identity')
    cap=state['budget'];res=cap.get('gpu_hour_reservations')
    w.require(res==BASE_CAPS['protected_gpu_hours'] and snap['running']==snap['gpu_healthcheck_inflight']==0
        and cap['dispatched']==snap['dispatched'] and abs(cap['gpu_hours_consumed']-snap['gpu_hours_consumed'])<1e-8,'r2 inconsistent budget')
    protected=sum(max(0.,h-snap['gpu_hours_by_bucket'][k]) for k,h in res.items() if k!=row['budget_bucket'])
    available=int((cap['max_gpu_hours']-snap['gpu_hours_consumed']-protected)*3600)-r['TERMINATION_GRACE_SECONDS']
    if available<1800:raise ResourceBudgetIncomplete('r2 cannot reserve full1840s globally before reservation')


def primary_row(plan,row):
    w.require(row in plan['episodes'],'r2 exact frozen row');return row


def effective_row(plan,row,events,root,r):
    require_scope(plan,root,r,row);return primary_row(plan,row)


def check_retry(events,row,r):
    h=history();b.current_subset(h,events);rows=expected_rows(h)
    w.require(row in rows,'r2 fixed scientific mapping differs')
    fields=('split','profile','task_id','env_seed','policy_seed','init_index')
    prior=[e for e in events if e.get('identity',{}).get('iteration') in {b.OLD,b.R1,COHORT}
        and all(e.get('identity',{}).get(k)==row[k] for k in fields)]
    if row==rows[0]:
        w.require(not any(e.get('retry_of')==b.FAILED for e in events),'r2 named recovery already reserved in any cohort')
        w.require(row['retry_of']==b.FAILED and row['budget_bucket']=='recovery'
            and prior==[e for e in h['events'] if e['attempt_id'] in {b.ORIGINAL_FAILED,b.FAILED}],'r2 sole named recovery consumed or changed')
    else:w.require(not prior and not row.get('retry_of'),'r2 suffix previously reserved/no retry')


def protected_budget(state,events,resources,row,timeout,r,*,plan):
    primary_row(plan,row);w.require(timeout==1800,'r2 fixed timeout')
    full_capacity(state,events,resources,r)
    if local_seconds(events,resources,r)+1840>21600:raise ResourceBudgetIncomplete('r2 combined local budget cannot reserve1840s')
    whole_attempt_hours(state,r['budget_snapshot'](events,resources),row,r)


def metadata(source,root,h):
    runtime=runtime_ref(h)
    return {'schema':'n30-r2-cohort-v1','cohort_id':COHORT,'limits':LIMITS,'protocol':ref(PROTOCOL),
        'original_plan':h['review']['plan'],'original_review':{'path':str(PARENT/'root-terminal-review-v1.json'),'sha256':b.REVIEW_SHA},
        'source_bridge':ref(BRIDGE),'final_review':final_review(source,runtime,root),'authority':authority(source,runtime,root),
        'worker_audit':WORKER_CONTRACT,'original_disposition':'INVALID_OR_INTERRUPTED','r1_review':h['r1_review_ref'],'repair_review':h['repair_review_ref'],'r1_disposition':'INVALID_OR_INTERRUPTED'}


def validate_runtime(runtime,root,r,h):
    w.require(runtime==w.read_ref(runtime_ref(h)) and Path(runtime['worktree']).resolve()==Path(root).resolve()
        and runtime['schema']=='qd-ed-runtime-setup-v1' and r['runtime_gpu'](runtime)==7
        and runtime['gpu_mapping']['uuid']==GPU7_UUID and runtime['gpu_mapping']['egl_device_index']==4
        and runtime.get('cuda_egl_verified') is True and runtime.get('cuda_egl_probe',{}).get('resource_id')==GPU7_PROOF
        and runtime.get('stage_recovered_error_condition')==r['E2_STAGE_CONDITION']
        and runtime.get('stage_engineering_condition')==r['n4e1_support']().engineering_condition()
        and runtime['frozen_stage_provider'].get('allow_recovered_error_events') is True,'r2 frozen runtime differs')
    r['verify_files'](runtime['files'],allowed_roots=(Path(root),Path(runtime['worktree']),runtime['artifact_root']))


def imports_owned(root,r):
    for path in (__file__,b.__file__,b.original.__file__,old.__file__,native.__file__,w.__file__,r['__file__']):
        w.require(Path(path).resolve().is_relative_to(Path(root).resolve()),'r2 imported module shadow')


def validate_contract(plan,manifest,runtime,seeds,root,r):
    imports_owned(root,r)
    h=history();source=w.source_record(root,[v['path'] for v in plan['code_files']])
    w.require(source['commit']==plan['source_commit'] and source['files']==plan['code_files'] and source_paths(r)=={v['path'] for v in plan['code_files']},'r2 committed source closure')
    w.require(plan.get('n30_r2_cohort')==metadata(source,root,h) and plan['episodes']==expected_rows(h)
        and not any(re.fullmatch(r'n[0-9]+_.*',k) and k!='n30_r2_cohort' for k in plan)
        and set(plan['candidate_profiles'])=={'N30'} and set(manifest['profiles'])==set(ARMS)
        and plan['phase_authorization']=={'dev':True,'validation':False,'formal':False}
        and plan['stage_condition']==r['E2_STAGE_CONDITION'],'r2 matrix/markers/phase')
    profile=Path(root)/'configs/qd_ed_final/candidate_n30.json'
    w.require(plan['candidate_profiles']['N30']==ref(profile) and str(profile.relative_to(root)) in plan['scientific_config_files']
        and manifest['profiles']['N30']['resolved_eds_config']=={**manifest['profiles']['Q0']['resolved_eds_config'],'executed_progress_continuation_mode':'executed_progress_continuation_v1'}
        and all(v['resolved_eds_config'].get('executed_progress_continuation_control','none')=='none' for v in manifest['profiles'].values()),'r2 unchanged science/future control closed')
    w.require({'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']}==runtime_ref(h)
        and ARTIFACT_DIR.is_symlink() and Path(plan['artifact_root']).resolve()==ARTIFACT_DIR.resolve()
        ==(SESSION/'artifacts/variants/n30_executed_progress_continuation').resolve(),'r2 runtime/storage')
    validate_runtime(runtime,root,r,h);require_state(r['read_state'](Path(root)/'research-state.yaml'),r)


def validate_worker_context(context,argv,root,output,plan,runtime):
    w.require(plan.get('frozen') is True and plan.get('n30_r2_cohort',{}).get('worker_audit')==WORKER_CONTRACT
        and set(plan.get('candidate_profiles',{}))=={'N30'} and not any(re.fullmatch(r'n[0-9]+_.*',k) and k!='n30_r2_cohort' for k in plan)
        and plan['worktree']==str(root) and context['profile'] in ARMS
        and output==Path(plan['artifact_root']).resolve()/'attempts'/context['attempt_id']
        and context['runtime']=={'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']},'r2 worker plan/runtime/output')
    w.require(not any('executed_progress_continuation_control=' in arg and arg.split('=',1)[1] not in {'none','"none"'} for arg in argv),'r2 QD-off not released')
    rows=[row for row in plan['episodes'] if row['episode_key']==context['episode_key']]
    w.require(len(rows)==1 and rows[0]['profile']==context['profile'] and rows[0]['split']=='dev' and rows[0]['iteration']==COHORT
        and rows[0]['timeout_seconds']==1800 and context['source']['commit']==plan['source_commit'] and context['source']['files']==plan['code_files'],'r2 worker row/source')
    w.verify_source(root,context['source']);w.require(w.cuda_binding(runtime)['physical_gpu']==7,'r2 worker device');return root,output,runtime


def accepted_cell(plan,row,events,root,r):
    groups=list(r['event_groups']([e for e in events if e.get('identity',{}).get('iteration')==COHORT
        and e.get('episode_key')==row['episode_key']]).values())
    w.require(len(groups)==1 and [e['event'] for e in groups[0]]==['reserved','dispatched','valid']
        and all(e.get('retry_of')==row.get('retry_of') for e in groups[0]),'N30 missing/duplicate/retry cell')
    final=groups[0][-1]
    w.require(final.get('outcome_valid') is True and final.get('required_cost_telemetry_complete') is True,'N30 invalid cannot count')
    output=Path(final['output_dir']);context=w.read_ref(ref(output/'n23-worker-context.json'))
    w.require(context.get('attempt_id')==final.get('attempt_id') and context.get('episode_key')==row['episode_key']
        and context.get('profile')==row['profile'] and Path(context['output_dir']).resolve()==output.resolve()
        and context['source']['commit']==plan['source_commit'] and context['source']['files']==plan['code_files']
        and final.get('identity')==r['episode_identity'](row) and final.get('episode_key')==row['episode_key']
        and final.get('source_commit')==plan['source_commit'] and final.get('plan_sha256')==context['plan']['sha256']
        and final.get('profile_manifest_sha256')==plan['profiles_sha256']
        and final.get('runtime_manifest_sha256')==plan['runtime_manifest_sha256']
        and final.get('runtime_inventory_sha256')==plan['runtime_inventory_sha256']
        and final.get('init_row_sha256')==row['init_row_sha256'] and final.get('physical_gpu')==7,
        'N30 terminal source/plan/runtime/profile/identity differs')
    r['owned'](final['output_dir'],plan['artifact_root'])
    w.require(w.read_ref(context['plan'])==plan and w.read_ref(ref(output/'attempt-result.json'))==final
        and final.get('n23_worker_receipt')==ref(output/'eds_eval/in-worker-audit-receipt.json'),'N30 accepted identity differs')
    report=read_worker_report(output,r);w.require(type(final.get('guided_chunks')) is int,'N30 guided count unknown')
    native.from_output(row['profile'],output,report,final['guided_chunks']);return final


def admission(plan,runtime,row,events,resources,root,r):
    from scripts.qd_ed_n30_report import futile
    primary_row(plan,row);h=history();b.current_subset(h,events);index=plan['episodes'].index(row)
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    allowed={v['episode_key'] for v in plan['episodes'][:index]}
    w.require(all(e.get('episode_key') in allowed for e in local),'r2 untouched next prefix only')
    accepted=[x['cell'] for x in h['imports']]
    for prior in plan['episodes'][:index]:
        final=accepted_cell(plan,prior,events,root,r)
        accepted.append({'profile':prior['profile'],'task_id':prior['task_id'],'success':final['success']})
        w.require(not futile(accepted),'r2 dispatch after mathematical futility')
    return {'n30_r2_cohort_id':COHORT,'n30_r2_protocol_sha256':PROTOCOL_SHA,
        'n30_original_episode_key':row['original_episode_key'],'n30_original_source_commit':b.OLD_SOURCE}
