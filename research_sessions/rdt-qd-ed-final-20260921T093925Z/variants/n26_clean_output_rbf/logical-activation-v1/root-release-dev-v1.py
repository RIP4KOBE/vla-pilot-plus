import json,sys,os,yaml
from pathlib import Path
from datetime import datetime,timezone
A=Path(__file__).resolve().parent;N26=A.parent;R=N26.parent.parent;W=R/'study_worktree'
sys.path[:0]=[str(W/'scripts'),str(W)]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n26_contract as c,qd_ed_n26_logical as logical
plan_path=N26/'plan.frozen.v1.gpu7.json'
plan=w.read_ref(c.ref(plan_path))
assert c.ref(plan_path)['sha256']=='cb5fbacbf1a5fe3a77bda0de98bca3b8838474fd6ede7d82319eb35326e32d24'
assert plan['frozen'] is True and plan['source_commit']=='6026794cd5d52f3a5054bf2704ebb3c516f9f47e'
assert plan['code_files']==w.read_ref(c.ref(N26/'source-manifest.logical-v1.json'))['files']
runtime=w.read_ref(c.runtime_ref());manifest=r.read_json(plan['profiles_path'])
for arm,reference in plan['candidate_profiles'].items():
 manifest['profiles'][arm]=r.expand_candidate(arm,w.read_ref(reference),manifest['profiles']['Q0'])
commands=[];pairs={}
for row in plan['episodes']:
 aid='root_command_review_task'+str(row['task_id'])
 command,out=r.build_command(plan,manifest,runtime,row,aid)
 values=dict(x.split('=',1) for x in command[2:])
 assert values['perception.gemini.backend']==r.hydra('codex_cli')
 assert values['perception.gemini.model']==r.hydra('gpt-6-astra')
 assert values['perception.gemini.timeout_seconds']=='180'
 assert values['perception.gemini_grounding.enabled']=='false'
 assert values['main.use_vlm_stage_recognition']=='true'
 commands.append({'episode_key':row['episode_key'],'main_argv':command})
 pairs.setdefault(row['task_id'],{})[row['profile']]=values
for task,arms in pairs.items():
 a,z=arms['N25'],arms['N26'];changed={k for k in set(a)|set(z) if a.get(k)!=z.get(k)}
 assert changed=={'main.eds_config.diversity_input_source','main.eds_eval.method_label'},changed
 assert z['main.eds_config.diversity_input_source']==r.hydra('model_output_sample_v1')
 assert a.get('main.eds_config.diversity_input_source',r.hydra('noisy_sample'))==r.hydra('noisy_sample')
env=r.child_environment(runtime);r.verify_provider(runtime,env,root=W)
assert runtime['frozen_stage_provider']['auth_mode']=='chatgpt'
assert not any(env.get(k) for k in r.codex_removed_environment())
with r.locked(W/'data/qd-ed-runner.lock',nonblocking=True):
 events=r.read_events(W/'data/attempt-ledger.jsonl');resources=r.read_events(W/'data/gpu-healthcheck-ledger.jsonl')
 state=r.read_state(W/'research-state.yaml')
 assert not any(q.get('identity',{}).get('iteration')==c.COHORT for q in events)
 c.full_capacity(state,events,resources,vars(r));logical.current_matching(events,resources)
 admission=r.gpu_admission(physical_gpu=7,expected_uuid=c.GPU7_UUID)
 review={'schema':'n26-root-dev-command-release-review-v1','accepted':True,'plan':c.ref(plan_path),
  'commands':commands,'n26_vs_n25_only_scientific_override':'main.eds_config.diversity_input_source',
  'matched_task_pairs':10,'provider_verified':'codex_cli/current-managed-chatgpt-login',
  'alternate_provider_or_account_fallback_allowed':False,'credentials_modified':False,
  'source_commit':plan['source_commit'],'actual_proof_review':c.ref(A/'root-actual-proof-review-v1.json'),
  'freeze_cli_validate_plan_completed':True,'reused_just_frozen_exact_plan':True,
  'current_matching_predecessor_journal_checked':True,'gpu_admission':admission,
  'budget_snapshot':r.budget_snapshot(events,resources),'validation_authorized':False,'formal_authorized':False,
  'reviewer':c.ref(__file__)}
 w.atomic_json(A/'root-command-release-review-v1.json',review)
 release={'schema':'n26-dev-execution-release-v1','plan':c.ref(plan_path),'source_commit':plan['source_commit'],
  'cohort_id':c.COHORT,'episode_keys':[x['episode_key'] for x in plan['episodes']],
  'authority':plan['n26_cohort']['authority'],'physical_gpu':7,'limits':c.LIMITS,
  'validation_authorized':False,'formal_authorized':False}
 w.atomic_json(N26/'execution-release-v1.json',release)
 (N26/'execution').mkdir(parents=True,exist_ok=True)
 with r.locked(W/'data/qd-ed-state.lock'):
  state=r.read_state(W/'research-state.yaml')
  state['current_iteration'].update(status='DEV_RELEASED',plan=c.ref(plan_path),
    release=c.ref(N26/'execution-release-v1.json'),execution_authorized=True)
  state['updated_at']=datetime.now(timezone.utc).isoformat()
  state['next_action']='Run one frozen N26 matched Dev cohort on GPU7 using current Codex managed login, monitor and independently review terminal before further research.'
  tmp=W/'research-state.yaml.root-n26-tmp'
  with tmp.open('w') as f:yaml.safe_dump(state,f,sort_keys=False);f.flush();os.fsync(f.fileno())
  os.replace(tmp,W/'research-state.yaml')
 print(json.dumps({'command_review':c.ref(A/'root-command-release-review-v1.json'),
  'release':c.ref(N26/'execution-release-v1.json'),'rows':len(commands),'gpu':7,'provider':'codex_cli/chatgpt'}))

