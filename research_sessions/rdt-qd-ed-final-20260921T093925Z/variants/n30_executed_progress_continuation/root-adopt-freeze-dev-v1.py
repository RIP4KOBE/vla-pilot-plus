"""Root finite N30 source/runtime adoption and exact Dev plan freeze; no execution."""
from pathlib import Path
import datetime,json,os,sys,yaml
V=Path(__file__).resolve().parent;ROOT=V.parents[1]/'study_worktree';sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n30_contract as c,qd_ed_n30_bridge as b,qd_ed_n30_prepare as prepare
from hydra import initialize_config_dir,compose
from omegaconf import OmegaConf
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
source=w.source_record(ROOT,c.source_paths(vars(r)));runtime=c.runtime_ref()
assert source==json.loads((V/'source-manifest-execution-v1.json').read_text())
root_source=w.read_ref(c.ref(V/'root-source-review-execution-v1.json'))
cpu_review=w.read_ref(c.ref(V/'root-phase-b-cpu-review-v1.json'))
assert root_source['decision']=='ACCEPT_SOURCE_BYTE_SCOPE' and root_source['commit']==source['commit']
assert cpu_review['disposition']=='ACCEPT_CPU_INTEGRATION_ONLY' and cpu_review['source_commit']==source['commit']
bridge=b.build(source,runtime,ROOT)
w.atomic_json(c.BRIDGE,bridge);b.verify(c.ref(c.BRIDGE),source,runtime,ROOT)
review={'schema':'n30-source-runtime-review-v1','disposition':'accepted','source':source,'runtime':runtime,
 'protocol':c.ref(c.PROTOCOL),'source_plan':c.ref(c.SOURCE_PLAN),'source_bridge':c.ref(c.BRIDGE),'predecessor':c.predecessor(),
 'new_tensor_preflight':False,'budget_reuse':c.ref(c.BUDGET_REUSE),'no_gpu_release':True}
authority={'schema':'n30-dev-authority-v1','cohort_id':c.COHORT,'source':source,'runtime':runtime,'protocol':c.ref(c.PROTOCOL),
 'final_review':None,'budget_reuse':c.ref(c.BUDGET_REUSE),'limits':c.LIMITS,'local_gpu_hours':6.,
 'recorded_at':now,'authority_interpretation':'Root finite12-cell adoption within unchanged cumulative578attempt/100GPUh caps under continuing user autonomous iteration delegation. This is not new numerical user approval and does not adopt the pending week proposal. OriginalDev identities, oneGPU7 worker, no retries, no protected phase.',
 'predecessor':c.predecessor(),'validation_authorized':False,'formal_authorized':False}
def save(state):
 path=ROOT/'research-state.yaml';tmp=path.with_suffix('.yaml.n30-adopt-tmp')
 with tmp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)
with r.locked(ROOT/'data/qd-ed-runner.lock',nonblocking=True):
 with r.locked(ROOT/'data/qd-ed-state.lock'):
  state=r.read_state(ROOT/'research-state.yaml');events=r.read_events(ROOT/'data/attempt-ledger.jsonl');resources=r.read_events(ROOT/'data/gpu-healthcheck-ledger.jsonl')
  c.require_budget_state(state,vars(r));snap=r.budget_snapshot(events,resources)
  assert snap['running']==snap['gpu_healthcheck_inflight']==0
  assert not state.get('current_owned_workers') and not state.get('active_iteration')
  assert not any(e.get('identity',{}).get('iteration')==c.COHORT for e in events)
  w.atomic_json(V/'adoption-v1/state-before-adoption-v1.json',state)
  w.atomic_json(c.FINAL_REVIEW,review);c.final_review(source,runtime,ROOT)
  authority['final_review']=c.ref(c.FINAL_REVIEW);w.atomic_json(c.AUTHORITY,authority)
  state['n30_dev_authority']=c.ref(c.AUTHORITY)
  state['previous_iteration_before_n30']=state['current_iteration']
  state['current_iteration']={'id':'N30','cohort_id':c.COHORT,'status':'N30_PLAN_FREEZE_PREPARATION','source_commit':source['commit'],
    'cpu_review':c.ref(V/'root-phase-b-cpu-review-v1.json'),'dev_authority_adopted':True,'execution_authorized':False,
    'validation_authorized':False,'formal_authorized':False}
  state['current_cpu_task']['status']='COMPLETED_ACCEPTED'
  state['current_cpu_task']['delivery']=c.ref(V/'delivery-manifest-phase-b-v1.json')
  state['prospective_iteration'].update(status='PLAN_FREEZE_PREPARATION',phase_b_source_commit=source['commit'],
    phase_b_review=c.ref(V/'root-phase-b-cpu-review-v1.json'))
  state['authorized_gpu_selection'].update(policy='N30 exact12-cell Dev only on admitted idleGPU7; one worker; no automatic fallback',root_policy_updated_at=now)
  state['study']['status']='N30_PLAN_FREEZE_PREPARATION_TARGET_NOT_MET'
  state['next_action']='Validate actual12-cell commands and freeze N30 plan; execution release remains absent; pending week budget unadopted.'
  c.full_capacity(state,events,resources,vars(r));save(state)
preview=prepare.build_plan(source=source,root=ROOT,review=c.ref(c.FINAL_REVIEW),authority=c.ref(c.AUTHORITY),predecessor_ref=c.predecessor())
path=V/'plan.preview.real-admission-v1.json';w.atomic_json(path,preview)
plan,manifest,rt=r.validate_plan(path,root=ROOT,require_frozen=False)
commands=[]
with initialize_config_dir(config_dir=str(ROOT/'configs'),version_base=None):
 for row in plan['episodes']:
  argv,output=r.build_command(plan,manifest,rt,row,'CPU_VERIFY_'+row['episode_key'])
  config=OmegaConf.to_container(compose(config_name='config',overrides=argv[2:]),resolve=False)
  eds=config['main']['eds_config']
  assert eds['executed_progress_continuation_mode']==('executed_progress_continuation_v1' if row['profile']=='N30' else 'off')
  assert eds['executed_progress_continuation_control']=='none'
  assert eds['qd_archive_mode']==('none' if row['profile']=='C0' else 'grid_archive')
  assert eds['qd_parent_sampling']==('uniform_cells' if row['profile']=='C0' else 'sparse_priority')
  assert eds['rollout_diversity_placement']=='model_output' and eds['diversity_update_mode']=='legacy_additive'
  for item in ('perception.gemini.backend=codex_cli','perception.gemini.model=gpt-6-astra','perception.gemini.reasoning_effort=low'):
   assert item in argv
  assert 'perception.gemini.timeout_seconds=180' in argv or 'perception.gemini.timeout_seconds=180.0' in argv
  assert output==Path(plan['artifact_root'])/'attempts'/('CPU_VERIFY_'+row['episode_key'])
  assert not any('api_key=' in x or 'base_url=' in x for x in argv)
  commands.append({'episode_key':row['episode_key'],'task_id':row['task_id'],'profile':row['profile'],'argv':argv,'output_dir':str(output)})
env=r.child_environment(rt)
assert env['CUDA_VISIBLE_DEVICES']=='7' and env['MUJOCO_EGL_DEVICE_ID']=='4'
assert [(x['task_id'],x['profile']) for x in commands]==[(t,a) for t in range(4) for a in c.ARMS]
w.atomic_json(V/'real-command-composition-review-v1.json',{'schema':'n30-root-real-command-composition-v1','accepted':True,
 'source_commit':source['commit'],'preview':c.ref(path),'runtime':runtime,'commands':commands,
 'actual_main_execution':False,'gpu_api_sim_calls':0,'provider_only':'codex_cli/chatgpt/current managed login',
 'gpu_environment':{k:env[k] for k in ('CUDA_VISIBLE_DEVICES','MUJOCO_EGL_DEVICE_ID','CUDA_DEVICE_ORDER','MUJOCO_GL')},
 'scope':'All12 exact realDev input/seed/profile/runtime argv; placeholder attempt identifiers only.'})
frozen_path=V/'plan.frozen.v1.gpu7.json';frozen=prepare.freeze(frozen_path,root=ROOT)
assert frozen=={**preview,'frozen':True}
with r.locked(ROOT/'data/qd-ed-state.lock'):
 state=r.read_state(ROOT/'research-state.yaml')
 state['current_iteration'].update(status='N30_PLAN_FROZEN_AWAITING_EXECUTION_RELEASE',frozen_plan=c.ref(frozen_path),
   command_review=c.ref(V/'real-command-composition-review-v1.json'))
 state['next_action']='Final resource/login/source review, then one12-cell N30 Dev screen with Codex-onlyStage; target not met.'
 save(state)
 cp_path=ROOT/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';cp=json.loads(cp_path.read_text())
 cp.update(status='N30_PLAN_FROZEN_AWAITING_EXECUTION_RELEASE',phase='REVIEW',automatic_gpu_dispatch_authorized=False,
   automatic_gpu_dispatch_scope=None,inflight_executor=None,inflight_executors=[],executor_task=None,
   n30_phase_b_review=c.ref(V/'root-phase-b-cpu-review-v1.json'),n30_frozen_plan=c.ref(frozen_path),
   n30_command_review=c.ref(V/'real-command-composition-review-v1.json'),budget_snapshot=snap,next_action=state['next_action'])
 r.durable_json(cp_path,cp)
w.atomic_json(V/'adoption-v1/root-plan-adoption-record-v1.json',{'schema':'n30-root-plan-adoption-record-v1','recorded_at':now,
 'authority':c.ref(c.AUTHORITY),'plan':c.ref(frozen_path),'command_review':c.ref(V/'real-command-composition-review-v1.json'),
 'cpu_review':c.ref(V/'root-phase-b-cpu-review-v1.json'),'execution_release_created':False,'gpu_dispatch':False,'budget_changed':False})
print(json.dumps({'frozen_plan':c.ref(frozen_path),'verified_commands':12,'execution_release_created':False,'gpu_dispatch':False}))

