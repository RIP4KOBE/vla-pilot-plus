"""Closed N30 Dev admission; root review/adoption/release are external artifacts."""
from contextlib import contextmanager
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import threading

from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n30_native as native

ROOT=Path(__file__).resolve().parents[1]
SESSION=ROOT.parent if ROOT.name=='study_worktree' else ROOT.parents[2]
RUN_DIR=SESSION/'variants/n30_executed_progress_continuation'
OLD_DIR=SESSION/'variants/n29_population_relative_trust'
SOURCE_PLAN=OLD_DIR/'plan.frozen.v1.gpu7.json'
SOURCE_PLAN_SHA='151ce8fdb088012676982703aad0cbc2a9952f1f656864bb3cea58d4ca223bc0'
PROTOCOL=RUN_DIR/'execution-integration-cpu-scope-v1.md'
PROTOCOL_SHA='b909b3113984f4e3794c2a9ccd1a86ac14b2b779403aef247b9b09cf15f5acab'
OBSERVABILITY=SESSION/'variants/n23_actuator_clipped_quality/timeout-observability-addendum-v2.md'
OBSERVABILITY_SHA='fa0723919c67d0417b101be2a36d9832cfaaf15e4b1c4e0cdfbf61caa43e34c6'
FINAL_REVIEW=RUN_DIR/'final-source-runtime-review-v1.json'
AUTHORITY=RUN_DIR/'adoption-v1/authority.json'
BRIDGE=RUN_DIR/'source-equivalence-bridge-v1.json'
PHASE_A='9029b384a34343efd73b4ea02184d83c5e52de61'
BASE='d855cfd690482e018bb40ce98edec80fad9700e0'
COHORT='N30_EXECUTED_PROGRESS_CONTINUATION_DEV_20261003'
ARMS=('C0','Q0','N30')
LIMITS={'primary_cells':12,'episode_dispatches':12,'recoveries':0,'recoveries_per_cell':0,
 'maximum_local_gpu_hours':6.0,'episode_timeout_seconds':1800,'cleanup_seconds':40,'physical_gpu':7}
BASE_CAPS={'attempts':578,'gpu_hours':100.,'buckets':{'baseline':76,'development':262,'validation':180,'formal':40,'recovery':20},
 'protected_gpu_hours':{'validation':32.,'formal':12.}}
PREDECESSOR=OLD_DIR/'root-terminal-review-v1.json'
BUDGET_AUTHORITY=OLD_DIR/'budget-adoption-v1/authority.json'
BUDGET_REUSE=BUDGET_AUTHORITY
GPU7_UUID='GPU-48473162-9548-1a19-04aa-ea86c5349187'
GPU7_PROOF='rdt-qd-ed-final-20260921T093925Z__gpu7_cuda_egl__4fafff3673e5'
WORKER_CONTRACT={'schema':'n30-same-process-native-audit-v1','arms':list(ARMS),
 'cuda_arithmetic_arms':[],'other_arm_backend':'cpu','timeout_includes_audit':True,
 'profile_bound_continuation_audit':True,'native_copy_and_feedback_backend':'cpu'}
ref=lambda path:{'path':str(Path(path).resolve()),'sha256':w.sha(path)}
class ResourceBudgetIncomplete(RuntimeError):
    pass

_SCOPE=None


def original_plan():
    from scripts import qd_ed_n30_bridge as bridge
    return bridge.closed_records(ROOT)['source_plan']


def runtime_ref():
    plan=original_plan()
    return {'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']}


def expected_rows():
    from scripts import qd_ed_n30_bridge as bridge
    rows=bridge.closed_records(ROOT)['source_plan']['episodes'];result=[]
    for t in range(4):
        for arm in ARMS:
            old=rows[t*4+(0 if arm=='C0' else 1)]
            row=copy.deepcopy(old);row.update(iteration=COHORT,profile=arm,episode_key=f'n30_dev_t{t:02d}_{arm.lower()}_20261003')
            w.require(row['task_id']==t and row['split']==row['seed_block']=='dev' and row['timeout_seconds']==1800
                and row['budget_bucket']==('baseline' if arm=='C0' else 'development') and 'retry_of' not in row,'N30 original mapping differs')
            result.append(row)
    return result


def source_paths(r):
    from scripts import qd_ed_n30_bridge as bridge
    return bridge.source_paths(Path(r['ROOT'])) | r['REQUIRED_CODE'] | w.REQUIRED_SOURCE



def imports_owned(root,r):
    root=Path(root).resolve()
    for path in (__file__,w.__file__,native.__file__,r['__file__']):
        w.require(Path(path).resolve().is_relative_to(root),'N30 adjacent-worktree module shadowing')


def final_review(source,runtime,root):
    from scripts import qd_ed_n30_bridge as bridge
    require_protocols(root)
    bound=bridge.verify(ref(BRIDGE),source,runtime,root)
    expected={'schema':'n30-source-runtime-review-v1','disposition':'accepted','source':source,'runtime':runtime,
      'protocol':ref(PROTOCOL),'source_plan':ref(SOURCE_PLAN),'source_bridge':ref(BRIDGE),
      'predecessor':predecessor(),'new_tensor_preflight':False,
      'budget_reuse':ref(BUDGET_REUSE),'no_gpu_release':True}
    w.require(w.read_ref(ref(FINAL_REVIEW))==expected and bound['new_source']==source,'N30 root source review differs')
    return ref(FINAL_REVIEW)



def authority(source,runtime,root,state=None):
    record=w.read_ref(ref(AUTHORITY));budget_reuse()
    keys={'schema','cohort_id','source','runtime','protocol','final_review','budget_reuse','limits','local_gpu_hours',
          'recorded_at','authority_interpretation','predecessor','validation_authorized','formal_authorized'}
    w.require(set(record)==keys and record['schema']=='n30-dev-authority-v1' and record['cohort_id']==COHORT
        and record['source']==source and record['runtime']==runtime and record['protocol']==ref(PROTOCOL)
        and record['final_review']==final_review(source,runtime,root) and record['limits']==LIMITS
        and record['predecessor']==predecessor() and record['budget_reuse']==ref(BUDGET_REUSE)
        and record['local_gpu_hours']==6.0
        and all(isinstance(record[k],str) and record[k].strip() for k in ('recorded_at','authority_interpretation'))
        and record['validation_authorized'] is False and record['formal_authorized'] is False,'N30 finite authority differs')
    if state is not None:w.require(state.get('n30_dev_authority')==ref(AUTHORITY),'N30 authority not adopted')
    return ref(AUTHORITY)



def require_state(state,r):
    require_budget_state(state,r)
    reference=state.get('n30_dev_authority');w.require(reference==ref(AUTHORITY),'N30 adoption missing')
    record=w.read_ref(reference);authority(record['source'],record['runtime'],Path(r['ROOT']),state)



def full_capacity(state,events,resources,r):
    require_state(state,r);snap=r['budget_snapshot'](events,resources);caps=BASE_CAPS
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    charged=[e for e in local if e['event']=='dispatched'];spent=local_seconds(events,resources,r)/3600
    remaining={b:need-sum(e['budget_bucket']==b for e in charged) for b,need in (('baseline',4),('development',8))}
    w.require(len(charged)<=12 and not any(e.get('retry_of') for e in local) and all(v>=0 for v in remaining.values()),'N30 count/retry limit')
    protected_hours=sum(max(0.,h-snap['gpu_hours_by_bucket'][b]) for b,h in caps['protected_gpu_hours'].items())
    protected_attempts=sum(max(0,caps['buckets'][b]-snap['by_bucket'][b]) for b in ('validation','formal'))
    w.require(snap['running']==snap['gpu_healthcheck_inflight']==0
        and all(g[-1]['event'] in r['TERMINAL'] for g in r['event_groups'](events).values()),'N30 unsettled owner/journal')
    w.require(state['budget']['dispatched']==snap['dispatched']
        and abs(state['budget']['gpu_hours_consumed']-snap['gpu_hours_consumed'])<1e-8,'N30 state/ledger mismatch')
    w.require(spent<=6.0 and snap['gpu_hours_consumed']+protected_hours<=100.+1e-9
        and all(caps['buckets'][b]-snap['by_bucket'][b]>=n for b,n in remaining.items())
        and snap['dispatched']+sum(remaining.values())+protected_attempts<=578,'N30 remaining attempt capacity/protected reserves do not fit')



@contextmanager
def supervised_scope(plan,root,episode_key):
    global _SCOPE
    w.require(_SCOPE is None,'N30 nested scope')
    _SCOPE=(str(Path(root).resolve()),plan['source_commit'],episode_key,os.getpid(),threading.get_ident())
    try:yield
    finally:_SCOPE=None


def require_scope(plan,root,r,row=None):
    w.require(_SCOPE is not None and _SCOPE[:2]==(str(Path(root).resolve()),plan['source_commit'])
        and _SCOPE[3:5]==(os.getpid(),threading.get_ident()) and (row is None or row['episode_key']==_SCOPE[2]),
        'N30 requires exact single-cell owned scope')


def primary_row(plan,row):
    w.require(row in plan['episodes'] and not any('retry' in k or 'recovery' in k for k in row),'N30 exact primary only, no retry')
    return row


def effective_row(plan,row,events,root,r):
    require_scope(plan,root,r,row);return primary_row(plan,row)


def whole_attempt_hours(state,snap,row,r):
    """Run before generic timeout truncation/reservation; preserve integer floor."""
    w.require(row.get('iteration')==COHORT and row.get('timeout_seconds')==1800 and row.get('budget_bucket') in {'baseline','development'},'N30 whole-attempt identity differs')
    budget=state['budget'];reservations=budget.get('gpu_hour_reservations')
    w.require(reservations==BASE_CAPS['protected_gpu_hours'] and snap['running']==snap['gpu_healthcheck_inflight']==0
        and budget['dispatched']==snap['dispatched'] and abs(budget['gpu_hours_consumed']-snap['gpu_hours_consumed'])<1e-8,
        'N30 unsettled or inconsistent budget cannot be resource-classified')
    protected=sum(max(0.,h-snap['gpu_hours_by_bucket'][b]) for b,h in reservations.items() if b!=row['budget_bucket'])
    available=int((budget['max_gpu_hours']-snap['gpu_hours_consumed']-protected)*3600)-r['TERMINATION_GRACE_SECONDS']
    if available<1800:raise ResourceBudgetIncomplete('N30 full1840s global/protected reserve unavailable before reservation')


def protected_budget(state,events,resources,row,timeout,r,*,plan):
    primary_row(plan,row)
    w.require(row['iteration']==COHORT and row['profile'] in ARMS and timeout==1800,'N30 row/timeout differs')
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    w.require(sum(e['event']=='dispatched' for e in local)<12,'N30 attempt cap')
    if local_seconds(events,resources,r)+1840>6.0*3600:
        raise ResourceBudgetIncomplete('N30 local budget cannot reserve whole1840s')
    full_capacity(state,events,resources,r)
    snap=r['budget_snapshot'](events,resources)
    protected=sum(max(0.,h-snap['gpu_hours_by_bucket'][b]) for b,h in BASE_CAPS['protected_gpu_hours'].items())
    if snap['gpu_hours_consumed']+1840/3600+protected>100.+1e-9:
        raise ResourceBudgetIncomplete('N30 cumulative/protected capacity cannot reserve whole1840s')



def validate_runtime(runtime,root,r):
    w.require(runtime==w.read_ref(runtime_ref()) and Path(runtime['worktree']).resolve()==Path(root).resolve()
        and runtime.get('schema')=='qd-ed-runtime-setup-v1' and r['runtime_gpu'](runtime)==7
        and runtime['gpu_mapping']['uuid']==GPU7_UUID and runtime['gpu_mapping']['egl_device_index']==4
        and runtime.get('cuda_egl_verified') is True and runtime.get('cuda_egl_probe',{}).get('resource_id')==GPU7_PROOF
        and runtime.get('stage_recovered_error_condition')==r['E2_STAGE_CONDITION']
        and runtime.get('stage_engineering_condition')==r['n4e1_support']().engineering_condition()
        and runtime['frozen_stage_provider'].get('allow_recovered_error_events') is True,
        'N30 frozen runtime/GPU/provider differs')
    r['verify_files'](runtime['files'],allowed_roots=(Path(root),Path(runtime['worktree']),runtime['artifact_root']))


def metadata(source,root):
    runtime=runtime_ref()
    return {'schema':'n30-executed-progress-continuation-dev-v1','cohort_id':COHORT,'limits':LIMITS,
        'protocol':ref(PROTOCOL),'source_plan':ref(SOURCE_PLAN),'timeout_observability':ref(OBSERVABILITY),
        'final_review':final_review(source,runtime,root),'authority':authority(source,runtime,root),
        'predecessor':predecessor(),'budget_reuse':ref(BUDGET_REUSE),
        'worker_audit':WORKER_CONTRACT,'control_roles':['C0','Q0'],'early_stop':'complete_triple_success_plus_remaining_less_than3'}


def validate_contract(plan,manifest,runtime,seeds,root,r):
    imports_owned(root,r)
    source=w.source_record(root,[v['path'] for v in plan['code_files']])
    w.require(source['commit']==plan['source_commit'] and source['files']==plan['code_files']
        and source_paths(r)<={v['path'] for v in plan['code_files']},'N30 complete committed source missing')
    w.require(plan.get('n30_cohort')==metadata(source,root) and plan['episodes']==expected_rows()
        and set(plan['candidate_profiles'])=={'N30'} and set(manifest['profiles'])==set(ARMS)
        and plan.get('phase_authorization')=={'dev':True,'validation':False,'formal':False}
        and plan.get('stage_condition')==r['E2_STAGE_CONDITION']
        and all(v['resolved_eds_config'].get('executed_progress_continuation_control','none')=='none' for v in manifest['profiles'].values())
        and not any(k.startswith(('n7_','n9_','n11_','n17_','n18_','n19_','n20_','n21_','n22_','n23_','n24_','n25_','n26_','n27_','n28_','n29_')) for k in plan),
        'N30 closed prospective matrix/phase differs')
    for arm in ('N30',):
        path=Path(root)/f'configs/qd_ed_final/candidate_{arm.lower()}.json'
        w.require(plan['candidate_profiles'][arm]==ref(path) and str(path.relative_to(root)) in plan['scientific_config_files'],
            'N30 profile fingerprint missing')
    q0=manifest['profiles']['Q0']['resolved_eds_config'];n30=manifest['profiles']['N30']['resolved_eds_config']
    w.require(n30=={**q0,'executed_progress_continuation_mode':'executed_progress_continuation_v1'},'N30 sole science delta differs')
    w.require({'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']}==runtime_ref(),'N30 runtime ref differs')
    artifact=(RUN_DIR/'artifacts')
    w.require(artifact.is_symlink() and artifact.resolve()==(SESSION/'artifacts/variants/n30_executed_progress_continuation').resolve()
        and Path(plan['artifact_root']).resolve()==artifact.resolve(),'N30 variant-owned artifact root differs')
    validate_runtime(runtime,root,r);require_state(r['read_state'](Path(root)/'research-state.yaml'),r)


def validate_worker_context(context,argv,root,output,plan,runtime):
    w.require(plan.get('frozen') is True and plan.get('n30_cohort',{}).get('worker_audit')==WORKER_CONTRACT
        and set(plan.get('candidate_profiles',{}))=={'N30'}
        and not any(k.startswith('n') and k.split('_',1)[0][1:].isdigit() and k!='n30_cohort' for k in plan)
        and plan['worktree']==str(root) and context['profile'] in ARMS
        and output==Path(plan['artifact_root']).resolve()/'attempts'/context['attempt_id']
        and context['runtime']=={'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']},
        'N30 worker frozen plan/runtime differs')
    w.require(not any('executed_progress_continuation_control=' in arg and arg.split('=',1)[1] not in {'none','"none"'} for arg in argv), 'N30 future QD-off control not dispatched')
    rows=[r for r in plan['episodes'] if r['episode_key']==context['episode_key']]
    w.require(len(rows)==1 and rows[0]['profile']==context['profile'] and rows[0]['split']=='dev'
        and rows[0]['iteration']==COHORT and rows[0]['timeout_seconds']==1800
        and context['source']['commit']==plan['source_commit'] and context['source']['files']==plan['code_files'],
        'N30 worker row/source differs')
    w.verify_source(root,context['source'])
    w.require(w.cuda_binding(runtime)['physical_gpu']==7,'N30 worker GPU differs')
    return root,output,runtime


def read_worker_report(output,r):
    return w.verify_receipt(Path(output)/'n23-worker-context.json',r['read_json'](Path(output)/'process.json'))


def accepted_cell(plan,row,events,root,r):
    groups=list(r['event_groups']([e for e in events if e.get('identity',{}).get('iteration')==COHORT
        and e.get('episode_key')==row['episode_key']]).values())
    w.require(len(groups)==1 and [e['event'] for e in groups[0]]==['reserved','dispatched','valid']
        and not any(e.get('retry_of') for e in groups[0]),'N30 missing/duplicate/retry cell')
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
    primary=primary_row(plan,row);index=plan['episodes'].index(primary)
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    allowed={v['episode_key'] for v in plan['episodes'][:index]}
    w.require(all(e.get('episode_key') in allowed for e in local),'N30 exact untouched next prefix required')
    candidate_wins=0
    for j,prior in enumerate(plan['episodes'][:index]):
        final=accepted_cell(plan,prior,events,root,r)
        if prior['profile']=='N30':candidate_wins+=int(final['success'])
        if (j+1)%3==0:
            w.require(candidate_wins+4-(j+1)//3>=3,'N30 cannot dispatch after complete-triple numeric futility')
    return {'n30_cohort_id':COHORT,'n30_protocol_sha256':PROTOCOL_SHA,'n30_arm_role':'candidate' if row['profile']=='N30' else 'control'}


def require_protocols(root):
    w.require(w.sha(PROTOCOL)==PROTOCOL_SHA,'N30 frozen protocol drift')
    for name in ('execution-integration-cpu-scope-v1.md','hypothesis-and-protocol-v1.md','compute-interpretation-v1.md','root-main-observation-evidence-addendum-v1.json','root-future-qd-removal-control-cpu-addendum-v1.json'):
        w.require((Path(root)/'docs/experiments/n30'/name).read_bytes()==(RUN_DIR/name).read_bytes(),'N30 tracked protocol drift')
    w.require(w.sha(OBSERVABILITY)==OBSERVABILITY_SHA,'N30 unchanged observability drift')


def predecessor():
    from scripts import qd_ed_n30_bridge as bridge
    bridge.closed_records(ROOT)
    return ref(PREDECESSOR)


def budget_authority():
    from scripts import qd_ed_n30_bridge as bridge
    record=bridge.closed_records(ROOT)['budget_authority']
    w.require(record['schema']=='n29-finite-budget-authority-v1' and record['caps']==BASE_CAPS
        and record['validation_authorized'] is False and record['formal_authorized'] is False,'N30 unchanged cumulative caps differ')
    return record


def require_budget_state(state,r):
    authority=budget_authority();caps=authority['caps'];budget=state['budget'];resource=state.get('resource_isolation',{})
    w.require(resource.get('status')=='ACTIVE' and resource.get('validation_status')=='PASS' and resource.get('private_budget') is True
        and state.get('max_concurrent_gpu_workers')==1 and not state.get('external_resource_hold',{}).get('do_not_auto_resume',False)
        and budget.get('gpu_hour_reservations')==caps['protected_gpu_hours'] and state.get('n29_budget_authority')==ref(BUDGET_AUTHORITY)
        and budget['max_episode_attempts']==578 and budget['max_gpu_hours']==100. and budget['reserved']==caps['buckets']
        and budget['amendment']==authority['amendment'] and r['authorized_gpu'](state)==7,'N30 finite budget/resource not adopted')


def expand_candidate(candidate,baseline,r):
    path=Path(r['ROOT'])/'configs/qd_ed_final/candidate_n30.json'
    w.require(candidate==r['read_json'](path) and candidate['algorithm_contract']=='executed_progress_continuation_v1'
        and candidate['baseline_reference']=='Q0','N30 closed candidate differs')
    old=copy.deepcopy(baseline);modes={'executed_progress_continuation_mode':'executed_progress_continuation_v1'}
    w.require(candidate['profile']=={**old['restored_profile'],**modes} and candidate['baseline_provenance']=={'path':'configs/qd_ed_final/n4_observed_baseline_profiles.json','profile':'Q0.restored_profile','sha256':w.sha(Path(r['ROOT'])/'configs/qd_ed_final/n4_observed_baseline_profiles.json')},'N30 sole profile delta differs')
    w.require(candidate['only_algorithm_change']=={'executed_progress_continuation_mode':{'before':'off','after':'executed_progress_continuation_v1'}} and candidate['profile'].get('executed_progress_continuation_control','none')=='none','N30 future control is not current profile')
    old['historical_label']=candidate['label'];old['restored_profile']=copy.deepcopy(candidate['profile']);old['resolved_eds_config'].update(modes);old['static_override_values'].update({'main.eds_config.'+k:v for k,v in modes.items()})
    old['hydra_overrides']=[f'{k}={r["hydra"](v)}' for k,v in old['static_override_values'].items()]
    return old


def budget_reuse():
    budget_authority();return ref(BUDGET_AUTHORITY)


def local_seconds(events,resources,r):
    episodes=[e for e in events if e.get('identity',{}).get('iteration')==COHORT and e['event'] in r['TERMINAL']]
    health=[e for e in resources if e.get('kind')=='n30_resource_preparation_v1' and e['event'] in {'completed','aborted'}]
    values=[e.get('gpu_process_wall_seconds') for e in episodes+health]
    w.require(all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in values),'N30 local costs incomplete')
    return sum(values)


def check_retry(events,row,r):
    w.require(row.get('iteration')==COHORT and not any('retry' in k or 'recovery' in k for k in row),'N30 no retry fields')
    w.require(not any(e.get('identity',{}).get('iteration')==COHORT and e.get('episode_key')==row['episode_key'] for e in events),
        'N30 cell already reserved; no restart/retry')
