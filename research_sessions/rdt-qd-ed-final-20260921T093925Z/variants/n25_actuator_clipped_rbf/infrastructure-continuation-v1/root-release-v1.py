"""Inspect all successor commands and issue one finite GPU7 release."""
import sys,json,datetime,yaml
from pathlib import Path
C=Path(__file__).resolve().parent;W=C.parents[2]/'study_worktree'
sys.path.insert(0,str(W/'scripts'));sys.path.insert(0,str(W));sys.path.insert(0,'/home/hynx/.codex/skills/arbor-agent-tools/scripts')
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n25_cont_contract as c,qd_ed_n25_supervise as oldsuper
import arbor_state

plan=w.read_ref(c.ref(c.PLAN));seal=c.history(cleanup=True);prior=w.read_ref(seal['original_plan'])
runtime=w.read_ref(seal['runtime']);manifest=r.read_json(plan['profiles_path'])
for arm,reference in plan['candidate_profiles'].items():
 manifest['profiles'][arm]=r.expand_candidate(arm,w.read_ref(reference),manifest['profiles']['Q0'])
commands=[]
for index,row in enumerate(plan['episodes'],18):
 aid='root_review_only_'+row['episode_key']
 new,out=r.build_command(plan,manifest,runtime,row,aid)
 old,oldout=r.build_command(prior,manifest,runtime,prior['episodes'][index],aid)
 assert new==old and out==oldout
 values=dict(x.split('=',1) for x in new[2:])
 assert values['perception.gemini.backend']==r.hydra('codex_cli')
 assert values['perception.gemini.model']==r.hydra('gpt-6-astra')
 assert values['perception.gemini.timeout_seconds']=='180'
 assert values['perception.gemini_grounding.enabled']=='false'
 assert values['main.use_vlm_stage_recognition']=='true'
 commands.append({'episode_key':row['episode_key'],'original_logical_index':index,'main_command':new,'identical_to_original_scientific_command':True})
env=r.child_environment(runtime);r.verify_provider(runtime,env,root=W)
assert not any(env.get(k) for k in r.codex_removed_environment())
assert runtime['frozen_stage_provider']['auth_mode']=='chatgpt'
oldsuper.device_check()
with r.locked(W/'data/qd-ed-runner.lock',nonblocking=True):
 with r.locked(W/'data/qd-ed-state.lock'):
  state=r.read_state(W/'research-state.yaml');events=r.read_events(W/'data/attempt-ledger.jsonl')
  assert not c.local_events(events)
  c.full_capacity(state,events,r.read_events(W/'data/gpu-healthcheck-ledger.jsonl'),vars(r))
  inspection={'schema':'n25-continuation-root-command-review-v1','accepted':True,'plan':c.ref(c.PLAN),'commands':commands,'all22_scientific_commands_identical_to_original':True,'codex_managed_login_verified':True,'alternate_provider_account_fallback':False,'saved_credentials_modified':False,'gpu':7,'validation_authorized':False,'formal_authorized':False}
  w.atomic_json(C/'root-command-review-v1.json',inspection)
  release={'schema':'n25-continuation-execution-release-v1','plan':c.ref(c.PLAN),'source_commit':plan['source_commit'],'cohort_id':c.COHORT,'authority':c.ref(c.AUTHORITY),'seal':c.ref(c.SEAL),'episode_keys':[x['episode_key'] for x in plan['episodes']],'limits':c.LIMITS,'physical_gpu':7,'one_launch':True,'validation_authorized':False,'formal_authorized':False}
  w.atomic_json(C/'execution-release-v1.json',release)
  now=datetime.datetime.now(datetime.timezone.utc).isoformat()
  state['current_iteration'].update(status='INFRASTRUCTURE_CONTINUATION_RELEASED',execution_authorized=True,next_gpu_execution_authorized=True,continuation_plan=c.ref(c.PLAN),continuation_release=c.ref(C/'execution-release-v1.json'),current_owned_workers=[])
  state['updated_at']=now;state['next_action']='Run exactly one N25 infrastructure continuation on GPU7 using current Codex managed chatgpt login; monitor, independently review terminal, then steer research from valid evidence.'
  arbor_state.atomic_write(W/'research-state.yaml',yaml.safe_dump(state,sort_keys=False,allow_unicode=True))
run='rdt-qd-ed-final-20260921T093925Z'
with arbor_state.state_lock(W,run):
 p=W/'.arbor/sessions'/run/'.coordinator/checkpoint.json';cp=json.loads(p.read_text())
 cp.update(status='N25_INFRASTRUCTURE_CONTINUATION_RELEASED',phase='DISPATCH',updated_at=now,active_controller=None,in_flight_executor=None,automatic_gpu_dispatch_authorized=True,n25_continuation_plan=c.ref(c.PLAN),n25_continuation_release=c.ref(C/'execution-release-v1.json'),target_met=False,target_achieved=False,next_action=state['next_action'])
 arbor_state.atomic_write(p,json.dumps(cp,indent=2)+'\n')
print(json.dumps({'release':c.ref(C/'execution-release-v1.json'),'command_review':c.ref(C/'root-command-review-v1.json'),'rows':len(commands),'provider':'codex_cli/chatgpt','gpu':7,'worker_not_yet_started':True}))
