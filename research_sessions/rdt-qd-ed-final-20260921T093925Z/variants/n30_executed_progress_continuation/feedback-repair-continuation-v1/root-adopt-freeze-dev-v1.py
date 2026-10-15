"""Root freezes the exact ten-cell repair after accepted source adoption; no launch."""
from pathlib import Path
import copy,datetime,json,os,sys,yaml
K=Path(__file__).resolve().parent;P=K.parent;ROOT=P.parents[1]/'study_worktree'
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w
from scripts import qd_ed_n30_r2_contract as c,qd_ed_n30_r2_bridge as b,qd_ed_n30_r2_prepare as prepare
from hydra import initialize_config_dir,compose
from omegaconf import OmegaConf
now=datetime.datetime.now(datetime.timezone.utc).isoformat();h=c.history()
source=w.source_record(ROOT,c.source_paths(vars(r)));runtime=c.runtime_ref(h)
assert source==r.read_json(K/'source-manifest-execution-v1.json')
adoption=w.read_ref(c.ref(K/'root-owning-source-adoption-v1.json'))
assert adoption['commit']==source['commit'] and adoption['gpu_dispatched'] is False
assert w.read_ref(c.ref(K/'root-cpu-integration-review-v1.json'))['source_commit']==source['commit']
assert len(c.expected_rows(h))==10 and h['review']['audited_cells']==2
assert abs(h['old_seconds']-1445.4208934970666)<1e-8
bridge=b.build(source,runtime,ROOT);w.atomic_json(c.BRIDGE,bridge)
final={'schema':'n30-r2-source-runtime-review-v1','disposition':'accepted','source':source,'runtime':runtime,
 'protocol':c.ref(c.PROTOCOL),'source_bridge':c.ref(c.BRIDGE),'new_tensor_preflight':False,'no_gpu_release':True}
w.atomic_json(c.FINAL_REVIEW,final);c.final_review(source,runtime,ROOT)
authority={'schema':'n30-r2-authority-v1','cohort_id':c.COHORT,'source':source,'runtime':runtime,'protocol':c.ref(c.PROTOCOL),
 'final_review':c.ref(c.FINAL_REVIEW),'source_bridge':c.ref(c.BRIDGE),'limits':c.LIMITS,'caps':c.BASE_CAPS,
 'validation_authorized':False,'formal_authorized':False,'recorded_at':now,
 'authority_interpretation':'Root finite engineering continuation under continuing user autonomy: exact once-linked terminal-Boolean-audit-error recovery plus9original unrun cells,2original valid controls inherited with original source; all4previousdispatch costs and both invalid outcomes preserved. A separately frozen prospective root exception to r1 no-additional-retry, never old-controller resumption or retroactive authority modification. No new numerical budget approval, no pending-week adoption. Combined original+new6GPUh, current578attempt/100GPUh caps and protected reserves unchanged; N30 science and3/4gate unchanged.'}
w.atomic_json(c.AUTHORITY,authority)
def save(state):
 temp=ROOT/'research-state.yaml.n30-r2-freeze-tmp'
 with temp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(temp,ROOT/'research-state.yaml')
with r.locked(ROOT/'data/qd-ed-runner.lock',nonblocking=True),r.locked(ROOT/'data/qd-ed-state.lock'):
 state=r.read_state(ROOT/'research-state.yaml');events=r.read_events(ROOT/'data/attempt-ledger.jsonl');resources=r.read_events(ROOT/'data/gpu-healthcheck-ledger.jsonl')
 snap=r.budget_snapshot(events,resources);before=copy.deepcopy(state['budget'])
 assert snap['dispatched']==399 and snap['running']==snap['gpu_healthcheck_inflight']==0
 assert not state.get('active_iteration') and not state.get('current_owned_workers') and not state.get('active_controller')
 assert not any(e.get('identity',{}).get('iteration')==c.COHORT for e in events)
 w.atomic_json(K/'adoption-v1/state-before-adoption-v1.json',state)
 state['n30_r2_authority']=c.ref(c.AUTHORITY)
 state['previous_execution_before_n30_r2']=state['current_iteration']
 state['current_iteration']={'id':'N30','cohort_id':c.COHORT,'status':'N30_R2_PLAN_PREPARATION',
  'source_commit':source['commit'],'original_cohort':b.OLD,'original_review':c.ref(P/'root-terminal-review-v1.json'),
  'cpu_review':c.ref(K/'root-cpu-integration-review-v1.json'),'dev_authority_adopted':True,
  'execution_authorized':False,'validation_authorized':False,'formal_authorized':False,'inherited_cells':2}
 state['study']['status']='N30_R2_PLAN_PREPARATION_TARGET_NOT_MET'
 state['prospective_iteration'].update(status='R2_PLAN_PREPARATION',gpu_execution_authorized=False)
 state['next_action']='Verify exact10real repair commands and freeze plan; only new finite release can launch; original cohort remains closed.'
 c.full_capacity(state,events,resources,vars(r));assert state['budget']==before;save(state)
preview=prepare.build_plan(source=source,root=ROOT,enabled=True);preview['frozen']=False
preview_path=K/'plan.preview.real-admission-v1.json';w.atomic_json(preview_path,preview)
plan,manifest,rt=r.validate_plan(preview_path,root=ROOT,require_frozen=False)
assert plan['episodes']==c.expected_rows(h)
assert plan['episodes'][0]['retry_of']=='rdt-qd-ed-final-20260921T093925Z__n30_r1_dev_t00_n30_20261003__2138c682c5a7' and plan['episodes'][0]['budget_bucket']=='recovery'
assert sum(row['budget_bucket']=='baseline' for row in plan['episodes'])==3
assert sum(row['budget_bucket']=='development' for row in plan['episodes'])==6
assert sum(bool(row.get('retry_of')) for row in plan['episodes'])==1
commands=[]
with initialize_config_dir(config_dir=str(ROOT/'configs'),version_base=None):
 for index,row in enumerate(plan['episodes']):
  original=h['plan']['episodes'][index+2]
  assert all(row[k]==original[k] for k in ('task_id','env_seed','policy_seed','init_index','init_row_sha256','split','seed_block','profile'))
  r.check_retry(events,row)
  argv,output=r.build_command(plan,manifest,rt,row,'CPU_VERIFY_'+row['episode_key'])
  config=OmegaConf.to_container(compose(config_name='config',overrides=argv[2:]),resolve=False);eds=config['main']['eds_config']
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
  commands.append({'episode_key':row['episode_key'],'original_episode_key':row['original_episode_key'],'task_id':row['task_id'],
   'profile':row['profile'],'budget_bucket':row['budget_bucket'],'retry_of':row.get('retry_of'),'argv':argv,'output_dir':str(output)})
env=r.child_environment(rt);assert env['CUDA_VISIBLE_DEVICES']=='7' and env['MUJOCO_EGL_DEVICE_ID']=='4'
w.atomic_json(K/'real-command-composition-review-v1.json',{'schema':'n30-r2-root-real-command-review-v1','at':now,'accepted':True,
 'source_commit':source['commit'],'preview':c.ref(preview_path),'runtime':runtime,'commands':commands,
 'original_control_source':b.OLD_SOURCE,'inherited_control_attempts':[x['cell']['attempt_id'] for x in h['imports']],
 'all_original_scientific_identities_preserved':True,'gpu_api_sim_calls':0,'actual_main_execution':False,
 'provider_only':'codex_cli/chatgpt/current managed login','gpu_environment':{k:env[k] for k in ('CUDA_VISIBLE_DEVICES','MUJOCO_EGL_DEVICE_ID','CUDA_DEVICE_ORDER','MUJOCO_GL')}})
frozen=prepare.freeze(c.PLAN,root=ROOT);assert frozen=={**preview,'frozen':True}
with r.locked(ROOT/'data/qd-ed-state.lock'):
 state=r.read_state(ROOT/'research-state.yaml')
 state['current_iteration'].update(status='N30_R2_PLAN_FROZEN_AWAITING_RELEASE',frozen_plan=c.ref(c.PLAN),
  command_review=c.ref(K/'real-command-composition-review-v1.json'))
 state['next_action']='Fresh GPU7/currentCodex login/source/resource review, then launch one finite N30 repair continuation; target not met.'
 save(state)
 cp_path=ROOT/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';cp=r.read_json(cp_path)
 cp.update(status='N30_R2_PLAN_FROZEN_AWAITING_RELEASE',phase='REVIEW',automatic_gpu_dispatch_authorized=False,
  automatic_gpu_dispatch_scope=None,n30_r2_frozen_plan=c.ref(c.PLAN),n30_r2_authority=c.ref(c.AUTHORITY),
  n30_r2_command_review=c.ref(K/'real-command-composition-review-v1.json'),budget_snapshot=snap,next_action=state['next_action'])
 r.durable_json(cp_path,cp)
w.atomic_json(K/'adoption-v1/root-plan-adoption-record-v1.json',{'schema':'n30-r2-root-plan-adoption-v1','at':now,'plan':c.ref(c.PLAN),
 'authority':c.ref(c.AUTHORITY),'command_review':c.ref(K/'real-command-composition-review-v1.json'),
 'source_bridge':c.ref(c.BRIDGE),'new_dispatches':10,'inherited_valid_cells':2,'original_costs_retained':True,
 'execution_release_created':False,'gpu_dispatch':False,'budget_changed':False})
print(json.dumps({'frozen_plan':c.ref(c.PLAN),'real_commands_verified':10,'new_gpu_dispatch':False}))

