"""Finish unchanged-source N28 plan checks after operational alias repair; no episode release."""
from pathlib import Path
import datetime,json,os,sys,yaml
V=Path(__file__).resolve().parent;ROOT=V.parents[1]/'study_worktree';sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n28_contract as c,qd_ed_n28_prepare as prepare
from hydra import initialize_config_dir,compose
from omegaconf import OmegaConf
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
source=w.source_record(ROOT,c.source_paths(vars(r)));runtime=c.runtime_ref()
assert source==json.loads((V/'source-manifest-execution-v1.json').read_text())
c.require_state(r.read_state(ROOT/'research-state.yaml'),vars(r))
preview_path=V/'plan.preview.real-admission-v1.json';preview=w.read_ref(c.ref(preview_path))
assert preview==prepare.build_plan(source=source,root=ROOT,review=c.ref(c.FINAL_REVIEW),authority=c.ref(c.AUTHORITY),predecessor_ref=c.predecessor())
plan,manifest,rt=r.validate_plan(preview_path,root=ROOT,require_frozen=False)
commands=[]
with initialize_config_dir(config_dir=str(ROOT/'configs'),version_base=None):
 for row in plan['episodes']:
  argv,output=r.build_command(plan,manifest,rt,row,'CPU_VERIFY_'+row['episode_key'])
  config=OmegaConf.to_container(compose(config_name='config',overrides=argv[2:]),resolve=False)
  assert config['main']['eds_config']['rollout_diversity_placement']==('parent_before_renoise_v1' if row['profile']=='N28' else 'model_output')
  for item in ('perception.gemini.backend=codex_cli','perception.gemini.model=gpt-6-astra','perception.gemini.reasoning_effort=low','perception.gemini.timeout_seconds=180.0'):
   if item.endswith('180.0'):assert item in argv or item[:-2] in argv
   else:assert item in argv
  assert output==Path(plan['artifact_root'])/'attempts'/('CPU_VERIFY_'+row['episode_key'])
  assert not any('api_key=' in x or 'base_url=' in x for x in argv)
  commands.append({'episode_key':row['episode_key'],'task_id':row['task_id'],'profile':row['profile'],'argv':argv,'output_dir':str(output)})
env=r.child_environment(rt)
assert env['CUDA_VISIBLE_DEVICES']=='7' and env['MUJOCO_EGL_DEVICE_ID']=='4'
assert [(x['task_id'],x['profile']) for x in commands]==[(t,a) for t in range(4) for a in c.ARMS]
w.atomic_json(V/'real-command-composition-review-v1.json',{'schema':'n28-root-real-command-composition-v1','accepted':True,
 'source_commit':source['commit'],'preview':c.ref(preview_path),'runtime':runtime,'commands':commands,
 'actual_main_execution':False,'gpu_api_sim_calls':0,'provider_only':'codex_cli/chatgpt/current managed login',
 'gpu_environment':{k:env[k] for k in ('CUDA_VISIBLE_DEVICES','MUJOCO_EGL_DEVICE_ID','CUDA_DEVICE_ORDER','MUJOCO_GL')},
 'scope':'All16 exact real input/seed/profile/runtime argv; placeholder attempt identifiers are the only future substitution.'})
frozen_path=V/'plan.frozen.v1.gpu7.json';frozen=prepare.freeze(frozen_path,root=ROOT)
assert frozen=={**preview,'frozen':True}
with r.locked(ROOT/'data/qd-ed-state.lock'):
 state=r.read_state(ROOT/'research-state.yaml');state['current_iteration'].update(status='N28_PLAN_FROZEN_AWAITING_EXECUTION_RELEASE',
   frozen_plan=c.ref(frozen_path),command_review=c.ref(V/'real-command-composition-review-v1.json'))
 state['next_action']='Independent final release check, then run this one16-cell N28 screen with Codex-only Stage.'
 path=ROOT/'research-state.yaml';tmp=path.with_suffix('.yaml.n28-plan-tmp')
 with tmp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)
 cp_path=ROOT/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';cp=json.loads(cp_path.read_text())
 cp.update(status='N28_PLAN_FROZEN_AWAITING_EXECUTION_RELEASE',automatic_gpu_dispatch_authorized=False,automatic_gpu_dispatch_scope=None,
   n28_native_review=c.ref(V/'root-native-proof-review-v1.json'),n28_frozen_plan=c.ref(frozen_path),
   n28_command_review=c.ref(V/'real-command-composition-review-v1.json'),budget_snapshot=r.budget_snapshot(r.read_events(ROOT/'data/attempt-ledger.jsonl'),r.read_events(ROOT/'data/gpu-healthcheck-ledger.jsonl')),
   next_action=state['next_action'])
 r.durable_json(cp_path,cp)
w.atomic_json(V/'adoption-v1/root-plan-adoption-record-v1.json',{'schema':'n28-root-plan-adoption-record-v1','recorded_at':now,
 'authority':c.ref(c.AUTHORITY),'plan':c.ref(frozen_path),'command_review':c.ref(V/'real-command-composition-review-v1.json'),
 'native_review':c.ref(V/'root-native-proof-review-v1.json'),'execution_release_created':False,'gpu_dispatch':False})
print(json.dumps({'frozen_plan':c.ref(frozen_path),'verified_commands':16,'execution_release_created':False,'gpu_dispatch':False}))

