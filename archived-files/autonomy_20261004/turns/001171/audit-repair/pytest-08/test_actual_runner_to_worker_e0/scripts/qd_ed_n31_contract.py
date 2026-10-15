"""Closed N31 Dev admission; root review/adoption/release are external artifacts."""
from contextlib import contextmanager
import copy
import datetime as dt
import json
import math
import os
from pathlib import Path
import subprocess
import threading

from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n31_native as native

ROOT=Path(__file__).resolve().parents[1]
SESSION=ROOT.parent if ROOT.name=='study_worktree' else ROOT.parents[2]
RUN_DIR=SESSION/'variants/n31_capture_dwell_proposal'
OLD_DIR=SESSION/'variants/n30_executed_progress_continuation/feedback-repair-continuation-v1'
SOURCE_PLAN=OLD_DIR/'plan.frozen.v1.gpu7.json'
SOURCE_PLAN_SHA='2221f8b1ba73cf194c0aa3040f4018acde9df7fbb4242eef9010bea144263f03'
PROTOCOL=RUN_DIR/'prospective-dev-science-protocol-v1.md'
PROTOCOL_SHA='5ca978f3610d2cb885ba9c9b006a99f515133d23960755a07e7a84ca578c5ccb'
OBSERVABILITY=SESSION/'variants/n23_actuator_clipped_quality/timeout-observability-addendum-v2.md'
OBSERVABILITY_SHA='fa0723919c67d0417b101be2a36d9832cfaaf15e4b1c4e0cdfbf61caa43e34c6'
FINAL_REVIEW=RUN_DIR/'final-source-runtime-review-v1.json'
AUTHORITY=RUN_DIR/'adoption-v1/authority.json'
BRIDGE=RUN_DIR/'source-equivalence-bridge-v1.json'
PHASE_A='d6de4b4fecc2784d1f7a6b4d4b93d451b09a79d0'
BASE='6292fc8cffad2eec0f789e023d835ad3c1df146a'
COHORT='N31_CAPTURE_DWELL_PROPOSAL_DEV_20261004'
ARMS=('C0','Q0','N31')
LIMITS={'primary_cells':30,'episode_dispatches':30,'recoveries':0,'recoveries_per_cell':0,
 'maximum_local_gpu_hours':5.0,'episode_timeout_seconds':1800,'cleanup_seconds':40,'physical_gpu':7}
PROTECTED_HOURS={'validation':32.,'formal':12.}
PREDECESSOR=OLD_DIR/'root-terminal-review-v1.json'
BUDGET_AUTHORITY=RUN_DIR/'budget-adoption-v1/authority.json'
BUDGET_REUSE=BUDGET_AUTHORITY
GPU7_UUID='GPU-48473162-9548-1a19-04aa-ea86c5349187'
GPU7_PROOF='rdt-qd-ed-final-20260921T093925Z__gpu7_cuda_egl__4fafff3673e5'
WORKER_CONTRACT={'schema':'n31-same-process-native-audit-v1','arms':list(ARMS),
 'cuda_arithmetic_arms':[],'other_arm_backend':'cpu','timeout_includes_audit':True,
 'profile_bound_capture_dwell_audit':True,'native_assignment_binary64_backend':'cpu','empty_provider_search_gate':True}
ref=lambda path:{'path':str(Path(path).resolve()),'sha256':w.sha(path)}
class ResourceBudgetIncomplete(RuntimeError):
    pass

_SCOPE=None


def original_plan():
    return json.loads((ROOT/'docs/experiments/n31/base-plan-metadata-v1.json').read_text())


def runtime_ref():
    plan=original_plan()
    return {'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']}


def expected_rows():
    tasks=json.loads((ROOT/'configs/qd_ed_final/n31_dev_task_identities.json').read_text())['tasks']
    w.require([x['task_id'] for x in tasks]==list(range(10)),'N31 ten exact tasks')
    return [{**task,'iteration':COHORT,'profile':arm,'timeout_seconds':1800,
        'episode_key':f'n31_dev_t{task["task_id"]:02d}_{arm.lower()}_20261004',
        'budget_bucket':'baseline' if arm=='C0' else 'development'} for task in tasks for arm in ARMS]


def source_paths(r):
    from scripts import qd_ed_n31_bridge as bridge
    return bridge.source_paths(Path(r['ROOT'])) | r['REQUIRED_CODE'] | w.REQUIRED_SOURCE



def imports_owned(root,r):
    root=Path(root).resolve()
    for path in (__file__,w.__file__,native.__file__,r['__file__']):
        w.require(Path(path).resolve().is_relative_to(root),'N31 adjacent-worktree module shadowing')


def final_review(source,runtime,root):
    from scripts import qd_ed_n31_bridge as bridge
    require_protocols(root)
    bound=bridge.verify(ref(BRIDGE),source,runtime,root)
    expected={'schema':'n31-source-runtime-review-v1','disposition':'accepted','source':source,'runtime':runtime,
      'protocol':ref(PROTOCOL),'source_plan':ref(SOURCE_PLAN),'source_bridge':ref(BRIDGE),
      'predecessor':predecessor(),'new_tensor_preflight':False,
      'budget_reuse':ref(BUDGET_REUSE),'no_gpu_release':True}
    w.require(w.read_ref(ref(FINAL_REVIEW))==expected and bound['new_source']==source,'N31 root source review differs')
    return ref(FINAL_REVIEW)



def authority(source,runtime,root,state=None):
    record=w.read_ref(ref(AUTHORITY));budget_reuse()
    keys={'schema','cohort_id','source','runtime','protocol','final_review','budget_reuse','limits','local_gpu_hours',
          'recorded_at','authority_interpretation','predecessor','validation_authorized','formal_authorized'}
    w.require(set(record)==keys and record['schema']=='n31-dev-authority-v1' and record['cohort_id']==COHORT
        and record['source']==source and record['runtime']==runtime and record['protocol']==ref(PROTOCOL)
        and record['final_review']==final_review(source,runtime,root) and record['limits']==LIMITS
        and record['predecessor']==predecessor() and record['budget_reuse']==ref(BUDGET_REUSE)
        and record['local_gpu_hours']==5.0
        and all(isinstance(record[k],str) and record[k].strip() for k in ('recorded_at','authority_interpretation'))
        and record['validation_authorized'] is False and record['formal_authorized'] is False,'N31 finite authority differs')
    if state is not None:w.require(state.get('n31_dev_authority')==ref(AUTHORITY),'N31 authority not adopted')
    return ref(AUTHORITY)



def require_state(state,r):
    require_budget_state(state,r)
    reference=state.get('n31_dev_authority');w.require(reference==ref(AUTHORITY),'N31 adoption missing')
    record=w.read_ref(reference);authority(record['source'],record['runtime'],Path(r['ROOT']),state)



def full_capacity(state,events,resources,r):
    require_state(state,r);snap=r['budget_snapshot'](events,resources);auth=budget_authority();caps=auth['caps'];require_window(auth)
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    charged=[e for e in local if e['event']=='dispatched'];spent=local_seconds(events,resources,r)/3600
    remaining={b:need-sum(e['budget_bucket']==b for e in charged) for b,need in (('baseline',10),('development',20))}
    w.require(len(charged)<=30 and not any(e.get('retry_of') for e in local) and all(v>=0 for v in remaining.values()),'N31 count/retry limit')
    protected_hours=sum(max(0.,h-snap['gpu_hours_by_bucket'][b]) for b,h in caps['protected_gpu_hours'].items())
    protected_attempts=sum(max(0,caps['buckets'][b]-snap['by_bucket'][b]) for b in ('validation','formal'))
    w.require(snap['running']==snap['gpu_healthcheck_inflight']==0
        and all(g[-1]['event'] in r['TERMINAL'] for g in r['event_groups'](events).values()),'N31 unsettled owner/journal')
    w.require(state['budget']['dispatched']==snap['dispatched']
        and abs(state['budget']['gpu_hours_consumed']-snap['gpu_hours_consumed'])<1e-8,'N31 state/ledger mismatch')
    w.require(spent<=5.0 and snap['gpu_hours_consumed']+protected_hours<=effective_hours(auth)+1e-9
        and all(caps['buckets'][b]-snap['by_bucket'][b]>=n for b,n in remaining.items())
        and snap['dispatched']+sum(remaining.values())+protected_attempts<=caps['attempts'],'N31 remaining attempt capacity/protected reserves do not fit')



@contextmanager
def supervised_scope(plan,root,episode_key):
    global _SCOPE
    w.require(_SCOPE is None,'N31 nested scope')
    _SCOPE=(str(Path(root).resolve()),plan['source_commit'],episode_key,os.getpid(),threading.get_ident())
    try:yield
    finally:_SCOPE=None


def require_scope(plan,root,r,row=None):
    w.require(_SCOPE is not None and _SCOPE[:2]==(str(Path(root).resolve()),plan['source_commit'])
        and _SCOPE[3:5]==(os.getpid(),threading.get_ident()) and (row is None or row['episode_key']==_SCOPE[2]),
        'N31 requires exact single-cell owned scope')


def primary_row(plan,row):
    w.require(row in plan['episodes'] and not any('retry' in k or 'recovery' in k for k in row),'N31 exact primary only, no retry')
    return row


def effective_row(plan,row,events,root,r):
    require_scope(plan,root,r,row);return primary_row(plan,row)


def whole_attempt_hours(state,snap,row,r):
    """Run before generic timeout truncation/reservation; preserve integer floor."""
    w.require(row.get('iteration')==COHORT and row.get('timeout_seconds')==1800 and row.get('budget_bucket') in {'baseline','development'},'N31 whole-attempt identity differs')
    auth=budget_authority();require_window(auth,1840)
    budget=state['budget'];reservations=budget.get('gpu_hour_reservations')
    w.require(reservations==PROTECTED_HOURS and snap['running']==snap['gpu_healthcheck_inflight']==0
        and budget['dispatched']==snap['dispatched'] and abs(budget['gpu_hours_consumed']-snap['gpu_hours_consumed'])<1e-8,
        'N31 unsettled or inconsistent budget cannot be resource-classified')
    protected=sum(max(0.,h-snap['gpu_hours_by_bucket'][b]) for b,h in reservations.items() if b!=row['budget_bucket'])
    available=int((effective_hours(auth)-snap['gpu_hours_consumed']-protected)*3600)-r['TERMINATION_GRACE_SECONDS']
    if available<1800:raise ResourceBudgetIncomplete('N31 full1840s global/protected reserve unavailable before reservation')


def protected_budget(state,events,resources,row,timeout,r,*,plan):
    primary_row(plan,row)
    w.require(row['iteration']==COHORT and row['profile'] in ARMS and timeout==1800,'N31 row/timeout differs')
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    w.require(sum(e['event']=='dispatched' for e in local)<30,'N31 attempt cap')
    if local_seconds(events,resources,r)+1840>5.0*3600:
        raise ResourceBudgetIncomplete('N31 local budget cannot reserve whole1840s')
    full_capacity(state,events,resources,r)
    snap=r['budget_snapshot'](events,resources)
    protected=sum(max(0.,h-snap['gpu_hours_by_bucket'][b]) for b,h in PROTECTED_HOURS.items())
    if snap['gpu_hours_consumed']+1840/3600+protected>effective_hours(budget_authority())+1e-9:
        raise ResourceBudgetIncomplete('N31 cumulative/protected capacity cannot reserve whole1840s')



def validate_runtime(runtime,root,r):
    w.require(runtime==w.read_ref(runtime_ref()) and Path(runtime['worktree']).resolve()==Path(root).resolve()
        and runtime.get('schema')=='qd-ed-runtime-setup-v1' and r['runtime_gpu'](runtime)==7
        and runtime['gpu_mapping']['uuid']==GPU7_UUID and runtime['gpu_mapping']['egl_device_index']==4
        and runtime.get('cuda_egl_verified') is True and runtime.get('cuda_egl_probe',{}).get('resource_id')==GPU7_PROOF
        and runtime.get('stage_recovered_error_condition')==r['E2_STAGE_CONDITION']
        and runtime.get('stage_engineering_condition')==r['n4e1_support']().engineering_condition()
        and runtime['frozen_stage_provider'].get('allow_recovered_error_events') is True,
        'N31 frozen runtime/GPU/provider differs')
    r['verify_files'](runtime['files'],allowed_roots=(Path(root),Path(runtime['worktree']),runtime['artifact_root']))


def metadata(source,root):
    runtime=runtime_ref()
    return {'schema':'n31-capture-dwell-dev-v1','cohort_id':COHORT,'limits':LIMITS,
        'protocol':ref(PROTOCOL),'source_plan':ref(SOURCE_PLAN),'timeout_observability':ref(OBSERVABILITY),
        'final_review':final_review(source,runtime,root),'authority':authority(source,runtime,root),
        'predecessor':predecessor(),'budget_reuse':ref(BUDGET_REUSE),
        'worker_audit':WORKER_CONTRACT,'control_roles':['C0','Q0'],'early_stop':'complete_triple_success_plus_remaining_less_than5'}


def validate_contract(plan,manifest,runtime,seeds,root,r):
    imports_owned(root,r)
    source=w.source_record(root,[v['path'] for v in plan['code_files']])
    w.require(source['commit']==plan['source_commit'] and source['files']==plan['code_files']
        and source_paths(r)<={v['path'] for v in plan['code_files']},'N31 complete committed source missing')
    w.require(plan.get('n31_cohort')==metadata(source,root) and plan['episodes']==expected_rows()
        and set(plan['candidate_profiles'])=={'N31'} and set(manifest['profiles'])==set(ARMS)
        and plan.get('phase_authorization')=={'dev':True,'validation':False,'formal':False}
        and plan.get('stage_condition')==r['E2_STAGE_CONDITION']
        and all(v['resolved_eds_config'].get('executed_progress_continuation_control','none')=='none' for v in manifest['profiles'].values())
        and not any(k.startswith(('n30_', 'n7_','n9_','n11_','n17_','n18_','n19_','n20_','n21_','n22_','n23_','n24_','n25_','n26_','n27_','n28_','n29_')) for k in plan),
        'N31 closed prospective matrix/phase differs')
    for arm in ('N31',):
        path=Path(root)/f'configs/qd_ed_final/candidate_{arm.lower()}.json'
        w.require(plan['candidate_profiles'][arm]==ref(path) and str(path.relative_to(root)) in plan['scientific_config_files'],
            'N31 profile fingerprint missing')
    q0=manifest['profiles']['Q0']['resolved_eds_config'];n31=manifest['profiles']['N31']['resolved_eds_config']
    w.require(n31=={**q0,'capture_dwell_proposal_mode':'capture_dwell_proposal_v1'},'N31 sole science delta differs')
    w.require({'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']}==runtime_ref(),'N31 runtime ref differs')
    artifact=(RUN_DIR/'artifacts')
    w.require(artifact.is_symlink() and artifact.resolve()==(SESSION/'artifacts/variants/n31_capture_dwell_proposal').resolve()
        and Path(plan['artifact_root']).resolve()==artifact.resolve(),'N31 variant-owned artifact root differs')
    validate_runtime(runtime,root,r);require_state(r['read_state'](Path(root)/'research-state.yaml'),r)


def validate_worker_context(context,argv,root,output,plan,runtime):
    w.require(plan.get('frozen') is True and plan.get('n31_cohort',{}).get('worker_audit')==WORKER_CONTRACT
        and set(plan.get('candidate_profiles',{}))=={'N31'}
        and not any(k.startswith('n') and k.split('_',1)[0][1:].isdigit() and k!='n31_cohort' for k in plan)
        and plan['worktree']==str(root) and context['profile'] in ARMS
        and output==Path(plan['artifact_root']).resolve()/'attempts'/context['attempt_id']
        and context['runtime']=={'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']},
        'N31 worker frozen plan/runtime differs')
    w.require(not any('executed_progress_continuation_control=' in arg and arg.split('=',1)[1] not in {'none','"none"'} for arg in argv), 'N31 future QD-off control not dispatched')
    rows=[r for r in plan['episodes'] if r['episode_key']==context['episode_key']]
    w.require(len(rows)==1 and rows[0]['profile']==context['profile'] and rows[0]['split']=='dev'
        and rows[0]['iteration']==COHORT and rows[0]['timeout_seconds']==1800
        and context['source']['commit']==plan['source_commit'] and context['source']['files']==plan['code_files'],
        'N31 worker row/source differs')
    w.verify_source(root,context['source'])
    from scripts import qd_ed_final_runner as runner
    w.require(Path(runner.__file__).resolve().is_relative_to(Path(root).resolve()),'N31 worker runner ownership')
    profile_path=runner.owned(plan['profiles_path'],root)
    manifest=w.read_ref({'path':str(profile_path),'sha256':plan['profiles_sha256']})
    w.require(set(manifest['profiles'])=={'C0','Q0'},'N31 baseline profile set')
    candidate_ref=plan['candidate_profiles']['N31'];candidate_path=runner.owned(candidate_ref['path'],root)
    candidate=w.read_ref(candidate_ref)
    w.require(candidate_path==Path(root)/'configs/qd_ed_final/candidate_n31.json','N31 candidate path')
    manifest['profiles']['N31']=runner.expand_candidate('N31',candidate,manifest['profiles']['Q0'])
    command,expected_output=runner.build_command(plan,manifest,runtime,rows[0],context['attempt_id'])
    w.require(command[1:]==list(argv) and expected_output==output,'N31 exact arm command differs even without guided work')
    w.require(w.cuda_binding(runtime)['physical_gpu']==7,'N31 worker GPU differs')
    return root,output,runtime


def read_worker_report(output,r):
    return w.verify_receipt(Path(output)/'n23-worker-context.json',r['read_json'](Path(output)/'process.json'))


def accepted_cell(plan,row,events,root,r):
    groups=list(r['event_groups']([e for e in events if e.get('identity',{}).get('iteration')==COHORT
        and e.get('episode_key')==row['episode_key']]).values())
    w.require(len(groups)==1 and [e['event'] for e in groups[0]]==['reserved','dispatched','valid']
        and not any(e.get('retry_of') for e in groups[0]),'N31 missing/duplicate/retry cell')
    final=groups[0][-1]
    w.require(final.get('outcome_valid') is True and final.get('required_cost_telemetry_complete') is True,'N31 invalid cannot count')
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
        'N31 terminal source/plan/runtime/profile/identity differs')
    r['owned'](final['output_dir'],plan['artifact_root'])
    w.require(w.read_ref(context['plan'])==plan and w.read_ref(ref(output/'attempt-result.json'))==final
        and final.get('n23_worker_receipt')==ref(output/'eds_eval/in-worker-audit-receipt.json'),'N31 accepted identity differs')
    report=read_worker_report(output,r);w.require(type(final.get('guided_chunks')) is int,'N31 guided count unknown')
    native.from_output(row['profile'],output,report,final['guided_chunks']);return final


def admission(plan,runtime,row,events,resources,root,r):
    primary=primary_row(plan,row);index=plan['episodes'].index(primary)
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    allowed={v['episode_key'] for v in plan['episodes'][:index]}
    w.require(all(e.get('episode_key') in allowed for e in local),'N31 exact untouched next prefix required')
    candidate_wins=0
    for j,prior in enumerate(plan['episodes'][:index]):
        final=accepted_cell(plan,prior,events,root,r)
        if prior['profile']=='N31':candidate_wins+=int(final['success'])
        if (j+1)%3==0:
            w.require(candidate_wins+10-(j+1)//3>=5,'N31 cannot dispatch after complete-triple numeric futility')
    return {'n31_cohort_id':COHORT,'n31_protocol_sha256':PROTOCOL_SHA,'n31_arm_role':'candidate' if row['profile']=='N31' else 'control'}


def require_protocols(root):
    w.require(w.sha(PROTOCOL)==PROTOCOL_SHA,'N31 frozen Dev protocol drift')
    for inside,outside in [('docs/experiments/n31_phase_c_protocol.md','cpu-phase-c-native-runtime-v1.md'),
            ('docs/experiments/n31_dev_protocol.md','prospective-dev-science-protocol-v1.md'),
            ('configs/qd_ed_final/n31_dev_task_identities.json','dev-task-identities-v1.json')]:
        w.require((Path(root)/inside).read_bytes()==(RUN_DIR/outside).read_bytes(),'N31 tracked protocol drift')
    w.require(w.sha(OBSERVABILITY)==OBSERVABILITY_SHA,'N31 unchanged observability drift')


def predecessor():
    from scripts import qd_ed_n31_bridge as bridge
    bridge.closed_records(ROOT)
    return ref(PREDECESSOR)


def budget_authority():
    record=w.read_ref(ref(BUDGET_AUTHORITY));caps=record.get('caps',{})
    w.require(record.get('schema')=='n31-approved-budget-authority-v1' and record.get('approved') is True
        and record.get('cohort_id')==COHORT and record.get('validation_authorized') is False
        and record.get('formal_authorized') is False and isinstance(record.get('approval_basis'),str)
        and bool(record['approval_basis'].strip()) and caps.get('protected_gpu_hours')==PROTECTED_HOURS,
        'N31 missing actual adopted budget; drafts/alternatives not authority')
    amendment=record.get('amendment')
    w.require(isinstance(amendment,dict) and set(amendment)=={'approval','proposal','previous_authority','history_boundary'}
        and all(isinstance(amendment[k],dict) and set(amendment[k])=={'path','sha256'}
                and Path(amendment[k]['path']).is_absolute()
                and len(amendment[k]['sha256'])==64 for k in ('approval','proposal','previous_authority'))
        and amendment['history_boundary']=={'dispatched':403,'gpu_hours_consumed':53.80872756284531},
        'N31 structured budget provenance/history missing')
    for key in ('approval','previous_authority'): w.read_ref(amendment[key])
    proposal=amendment['proposal'];path=Path(proposal['path'])
    w.require(path.is_file() and not path.is_symlink() and path.stat().st_size<=2*1024*1024
        and w.sha(path)==proposal['sha256'],'N31 proposal bytes/hash differs')
    pair=(caps.get('attempts'),caps.get('gpu_hours'))
    alternatives={(598,100.):{'baseline':84,'development':274,'validation':180,'formal':40,'recovery':20},
                  (1800,224.):{'baseline':400,'development':1120,'validation':180,'formal':40,'recovery':60}}
    w.require(pair in alternatives and caps.get('buckets')==alternatives[pair], 'N31 exact alternative buckets differ')
    if pair==(1800,224.):
        w.require(record.get('weekly_window')=={'origin_gpu_hours':53.08404692669838,'increment_gpu_hours':168.,
            'ends_at':'2026-10-10T17:42:00Z'}, 'N31 weekly origin/increment/window drift')
    else: w.require(record.get('weekly_window') is None,'N31 finite authority has no weekly extension')
    return record


def effective_hours(authority):
    caps=authority['caps'];window=authority.get('weekly_window')
    return min(caps['gpu_hours'],window['origin_gpu_hours']+window['increment_gpu_hours']) if window else caps['gpu_hours']


def require_window(authority,seconds=0):
    window=authority.get('weekly_window')
    if window:
        end=dt.datetime.fromisoformat(window['ends_at'].replace('Z','+00:00'))
        if dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=seconds)>end:
            raise ResourceBudgetIncomplete('N31 adopted weekly window cannot cover next complete attempt')


def require_budget_state(state,r):
    authority=budget_authority();caps=authority['caps'];budget=state['budget'];resource=state.get('resource_isolation',{})
    w.require(resource.get('status')=='ACTIVE' and resource.get('validation_status')=='PASS' and resource.get('private_budget') is True
        and state.get('max_concurrent_gpu_workers')==1 and not state.get('external_resource_hold',{}).get('do_not_auto_resume',False)
        and budget.get('gpu_hour_reservations')==caps['protected_gpu_hours'] and state.get('n31_budget_authority')==ref(BUDGET_AUTHORITY)
        and budget['max_episode_attempts']==caps['attempts'] and budget['max_gpu_hours']==caps['gpu_hours']
        and budget['reserved']==caps['buckets'] and budget['amendment']==authority['amendment']
        and budget['dispatched']>=403 and budget['gpu_hours_consumed']>=53.80872756284531
        and r['authorized_gpu'](state)==7,'N31 actual finite budget/resource/history not adopted')


def expand_candidate(candidate,baseline,r):
    path=Path(r['ROOT'])/'configs/qd_ed_final/candidate_n31.json'
    w.require(candidate==r['read_json'](path) and candidate['algorithm_contract']=='capture_dwell_proposal_v1'
        and candidate['baseline_reference']=='Q0','N31 closed candidate differs')
    old=copy.deepcopy(baseline);modes={'capture_dwell_proposal_mode':'capture_dwell_proposal_v1'}
    w.require(candidate['profile']=={**old['restored_profile'],**modes} and candidate['baseline_provenance']=={
        'path':'configs/qd_ed_final/n4_observed_baseline_profiles.json','profile':'Q0.restored_profile',
        'sha256':w.sha(Path(r['ROOT'])/'configs/qd_ed_final/n4_observed_baseline_profiles.json')}
        and candidate['only_algorithm_change']=={'capture_dwell_proposal_mode':{'before':'off','after':'capture_dwell_proposal_v1'}},'N31 sole profile delta')
    old['historical_label']=candidate['label'];old['restored_profile']=copy.deepcopy(candidate['profile'])
    old['resolved_eds_config'].update(modes);old['static_override_values'].update({'main.eds_config.'+k:v for k,v in modes.items()})
    old['hydra_overrides']=[f'{k}={r["hydra"](v)}' for k,v in old['static_override_values'].items()]
    return old


def budget_reuse():
    budget_authority();return ref(BUDGET_AUTHORITY)


def local_seconds(events,resources,r):
    episodes=[e for e in events if e.get('identity',{}).get('iteration')==COHORT and e['event'] in r['TERMINAL']]
    health=[e for e in resources if e.get('kind')=='n31_resource_preparation_v1' and e['event'] in {'completed','aborted'}]
    values=[e.get('gpu_process_wall_seconds') for e in episodes+health]
    w.require(all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in values),'N31 local costs incomplete')
    return sum(values)


def check_retry(events,row,r):
    w.require(row.get('iteration')==COHORT and not any('retry' in k or 'recovery' in k for k in row),'N31 no retry fields')
    w.require(not any(e.get('identity',{}).get('iteration')==COHORT and e.get('episode_key')==row['episode_key'] for e in events),
        'N31 cell already reserved; no restart/retry')
