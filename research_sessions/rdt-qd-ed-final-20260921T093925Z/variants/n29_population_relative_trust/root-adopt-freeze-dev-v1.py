"""Root adopt and freeze one exact N29 Dev screen, without execution release."""
from pathlib import Path
import datetime,json,os,sys,yaml,hashlib
V=Path(__file__).resolve().parent;ROOT=V.parents[1]/'study_worktree';sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n29_contract as c,qd_ed_n29_backend as b,qd_ed_n29_prepare as prepare
from hydra import initialize_config_dir,compose
from omegaconf import OmegaConf
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
source=w.source_record(ROOT,c.source_paths(vars(r)));runtime=c.runtime_ref()
native_review=w.read_ref(c.ref(V/'root-native-proof-review-v1.json'))
assert native_review['decision']=='ACCEPT_METERED_CUDA_POPULATION_TRUST_PROOF'
proof=b.verify_proof(c.ref(c.BACKEND_PROOF),source,runtime,ROOT)
review={'schema':'n29-source-runtime-review-v1','disposition':'accepted','source':source,'runtime':runtime,
 'protocol':c.ref(c.PROTOCOL),'source_plan':c.ref(c.SOURCE_PLAN),'source_bridge':c.ref(c.BRIDGE),'predecessor':c.predecessor(),
 'backend_proof':c.ref(c.BACKEND_PROOF),'arithmetic_protocol':c.ref(c.ARITHMETIC_PROTOCOL),'budget_reuse':c.ref(c.BUDGET_REUSE),'no_gpu_release':True}
authority={'schema':'n29-dev-authority-v1','cohort_id':c.COHORT,'source':source,'runtime':runtime,'protocol':c.ref(c.PROTOCOL),
 'final_review':None,'budget_reuse':c.ref(c.BUDGET_REUSE),'limits':c.LIMITS,'local_gpu_hours':13.5,
 'recorded_at':now,'authority_interpretation':'Root finite40-cell adoption under continuing user no-intervention delegation; not new numerical user approval. Exact original Dev identities, one GPU7 worker, no retries or protected phases.',
 'predecessor':c.predecessor(),'validation_authorized':False,'formal_authorized':False}
with r.locked(ROOT/'data/qd-ed-runner.lock',nonblocking=True):
 with r.locked(ROOT/'data/qd-ed-state.lock'):
  state=r.read_state(ROOT/'research-state.yaml');events=r.read_events(ROOT/'data/attempt-ledger.jsonl');resources=r.read_events(ROOT/'data/gpu-healthcheck-ledger.jsonl')
  b.settled_proof(proof,resources,vars(r));assert not any(e.get('identity',{}).get('iteration')==c.COHORT for e in events)
  w.atomic_json(c.FINAL_REVIEW,review);c.final_review(source,runtime,ROOT)
  authority['final_review']=c.ref(c.FINAL_REVIEW);w.atomic_json(c.AUTHORITY,authority)
  state['n29_dev_authority']=c.ref(c.AUTHORITY);state['current_iteration'].update(status='N29_PLAN_FREEZE_PREPARATION',
    arithmetic_execution_authorized=False,dev_authority_adopted=True,execution_authorized=False,native_proof_review=c.ref(V/'root-native-proof-review-v1.json'))
  state['study']['status']='N29_PLAN_FREEZE_PREPARATION_TARGET_NOT_MET';state['next_action']='Validate actual40-cell commands and freeze canonical plan; execution release remains absent.'
  c.full_capacity(state,events,resources,vars(r))
  path=ROOT/'research-state.yaml';tmp=path.with_suffix('.yaml.n29-dev-tmp')
  with tmp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
  os.replace(tmp,path)
preview=prepare.build_plan(source=source,root=ROOT,review=c.ref(c.FINAL_REVIEW),authority=c.ref(c.AUTHORITY),predecessor_ref=c.predecessor())
preview_path=V/'plan.preview.real-admission-v1.json';w.atomic_json(preview_path,preview)
plan,manifest,rt=r.validate_plan(preview_path,root=ROOT,require_frozen=False)
commands=[]
with initialize_config_dir(config_dir=str(ROOT/'configs'),version_base=None):
 for row in plan['episodes']:
  argv,output=r.build_command(plan,manifest,rt,row,'CPU_VERIFY_'+row['episode_key'])
  config=OmegaConf.to_container(compose(config_name='config',overrides=argv[2:]),resolve=False)
  assert config['main']['eds_config']['rollout_diversity_placement']==('parent_before_renoise_v1' if row['profile'] in ('N28','N29') else 'model_output')
  if row['profile'] in ('N28','N29'):
   assert config['main']['eds_config']['diversity_update_mode']==('population_relative_trust_v1' if row['profile']=='N29' else 'feasible_ray_v1')
  for item in ('perception.gemini.backend=codex_cli','perception.gemini.model=gpt-6-astra','perception.gemini.reasoning_effort=low','perception.gemini.timeout_seconds=180.0'):
   if item.endswith('180.0'):assert item in argv or item[:-2] in argv
   else:assert item in argv
  assert output==Path(plan['artifact_root'])/'attempts'/('CPU_VERIFY_'+row['episode_key'])
  assert not any('api_key=' in x or 'base_url=' in x for x in argv)
  commands.append({'episode_key':row['episode_key'],'task_id':row['task_id'],'profile':row['profile'],'argv':argv,'output_dir':str(output)})
env=r.child_environment(rt)
assert env['CUDA_VISIBLE_DEVICES']=='7' and env['MUJOCO_EGL_DEVICE_ID']=='4'
assert [(x['task_id'],x['profile']) for x in commands]==[(t,a) for t in range(10) for a in c.ARMS]
w.atomic_json(V/'real-command-composition-review-v1.json',{'schema':'n29-root-real-command-composition-v1','accepted':True,
 'source_commit':source['commit'],'preview':c.ref(preview_path),'runtime':runtime,'commands':commands,
 'actual_main_execution':False,'gpu_api_sim_calls':0,'provider_only':'codex_cli/chatgpt/current managed login',
 'gpu_environment':{k:env[k] for k in ('CUDA_VISIBLE_DEVICES','MUJOCO_EGL_DEVICE_ID','CUDA_DEVICE_ORDER','MUJOCO_GL')},
 'scope':'All40 exact real input/seed/profile/runtime argv; placeholder attempt identifiers are the only future substitution.'})
frozen_path=V/'plan.frozen.v1.gpu7.json';frozen=prepare.freeze(frozen_path,root=ROOT)
assert frozen=={**preview,'frozen':True}
with r.locked(ROOT/'data/qd-ed-state.lock'):
 state=r.read_state(ROOT/'research-state.yaml');state['current_iteration'].update(status='N29_PLAN_FROZEN_AWAITING_EXECUTION_RELEASE',
   frozen_plan=c.ref(frozen_path),command_review=c.ref(V/'real-command-composition-review-v1.json'))
 state['next_action']='Independent final release check, then run this one40-cell N29 screen with Codex-only Stage.'
 path=ROOT/'research-state.yaml';tmp=path.with_suffix('.yaml.n29-plan-tmp')
 with tmp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)
 cp_path=ROOT/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';cp=json.loads(cp_path.read_text())
 cp.update(status='N29_PLAN_FROZEN_AWAITING_EXECUTION_RELEASE',automatic_gpu_dispatch_authorized=False,automatic_gpu_dispatch_scope=None,
   n29_native_review=c.ref(V/'root-native-proof-review-v1.json'),n29_frozen_plan=c.ref(frozen_path),
   n29_command_review=c.ref(V/'real-command-composition-review-v1.json'),budget_snapshot=r.budget_snapshot(r.read_events(ROOT/'data/attempt-ledger.jsonl'),r.read_events(ROOT/'data/gpu-healthcheck-ledger.jsonl')),
   next_action=state['next_action'])
 r.durable_json(cp_path,cp)
w.atomic_json(V/'adoption-v1/root-plan-adoption-record-v1.json',{'schema':'n29-root-plan-adoption-record-v1','recorded_at':now,
 'authority':c.ref(c.AUTHORITY),'plan':c.ref(frozen_path),'command_review':c.ref(V/'real-command-composition-review-v1.json'),
 'native_review':c.ref(V/'root-native-proof-review-v1.json'),'execution_release_created':False,'gpu_dispatch':False})
print(json.dumps({'frozen_plan':c.ref(frozen_path),'verified_commands':40,'execution_release_created':False,'gpu_dispatch':False}))

