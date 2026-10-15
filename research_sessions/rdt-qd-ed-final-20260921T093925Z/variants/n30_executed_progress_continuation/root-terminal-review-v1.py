"""Close the original N30 engineering interruption; hashes/scalars only."""
from pathlib import Path
import collections,datetime,json,os,sys,time,subprocess
V=Path(__file__).resolve().parent;W=V.parents[1]/'study_worktree'
sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r,qd_ed_n30_contract as c,qd_ed_n23_worker as w
start=time.process_time()
read=r.read_json;ref=c.ref
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def alive(p):
 try:
  stat=Path(f"/proc/{p['pid']}/stat").read_text().rsplit(')',1)[1].split()
  return stat[0]!='Z' and stat[19]==str(p['proc_start_ticks']) and p['boot_id']==boot
 except FileNotFoundError:return False
plan=read(V/'plan.frozen.v1.gpu7.json');result=read(V/'result-v1.json');status=read(V/'execution/supervisor-status-v1.json')
source=read(V/'source-manifest-execution-v1.json')
assert source['commit']==plan['source_commit']=='4ce2b95757c1c0d662696ba19d6a9a14d2e59b49'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=W,text=True).strip()==source['commit']
assert source['files']==plan['code_files'] and len(source['files'])==439
for f in source['files']: assert w.sha(W/f['path'])==f['sha256'],f['path']
for name in ('controller-process-v1.json','monitor-process-v1.json'):
 assert not alive(read(V/'execution'/name)),name
exit_record=read(V/'execution/root-launch-result-v1.json')
assert exit_record['controller']==ref(V/'execution/controller-process-v1.json') and exit_record['exit_code']==1
events=r.read_events(W/'data/attempt-ledger.jsonl');resources=r.read_events(W/'data/gpu-healthcheck-ledger.jsonl')
local=[e for e in events if e.get('identity',{}).get('iteration')==c.COHORT]
assert local==read(V/'execution/terminal-ledger-v1.json')
groups=list(r.event_groups(local).values())
assert len(groups)==3 and [g[0]['episode_key'] for g in groups]==[x['episode_key'] for x in plan['episodes'][:3]]
assert not any(e.get('retry_of') for e in local)
accepted=[];closed=[];cost=0.;stage=collections.Counter()
for i,g in enumerate(groups):
 assert [e['event'] for e in g]==['reserved','dispatched','valid']
 e=g[-1];out=Path(e['output_dir']);row=plan['episodes'][i]
 assert read(out/'attempt-result.json')==e and result['attempts'][i]['terminal']==e
 proc=read(out/'process.json');assert not alive(proc)
 assert out.resolve().parent==(V/'artifacts/attempts').resolve()
 closed.append({'attempt_id':e['attempt_id'],'process':ref(out/'process.json'),'original_process_exited':True})
 cost+=e['gpu_process_wall_seconds']
 if i<2:
  assert c.accepted_cell(plan,row,events,W,vars(r))==e
  assert e['outcome_valid'] and e['success'] is False
  cell=result['accepted_cells'][i]
  assert cell['attempt_id']==e['attempt_id'] and cell['success']==e['success']
  for k in ('audit','worker_context','worker_receipt','attempt_result'):w.read_ref(cell[k])
  calls=[x for x in r.read_events(out/'eds_eval/stage_events.jsonl') if x.get('query_status')!='skipped']
  assert len(calls)==e['provider_logical_call_attempts'] and e['provider_failed_calls']==0
  for x in calls:
   t=x['transport'];assert (t['backend'],t['auth_mode'],t['model'])==('codex_cli','chatgpt','gpt-6-astra')
   assert x['query_status']=='ok' and x['query_ok'] is True
   assert x.get('api_request_attempts') is None and x.get('api_sdk_retry_attempts') is None
  for k in ('input_tokens','output_tokens','cached_input_tokens'):
   assert sum(x['codex_'+k] for x in calls)==e['provider_'+k]
   stage[k]+=e['provider_'+k]
  stage['logical_calls']+=len(calls)
  accepted.append(cell)
 else:
  assert e['outcome_valid'] is False and e['failure_class']=='task_failure'
  assert all(e[k]==0 for k in ('guided_chunks','unguided_chunks','model_forward_calls','rbf_gradient_calls','reward_scoring_batches','provider_logical_call_attempts'))
  error=out/'episode_1/error.txt'
  assert "UnboundLocalError: cannot access local variable 'obs' where it is not associated with a value" in error.read_text()
  assert "obs, keypoints, keypoint_tracking_snapshot, episode)" in error.read_text()
  receipt=read(out/'eds_eval/in-worker-audit-receipt.json')
  assert receipt['accepted'] is False and receipt['process_unchanged'] is True and receipt['main_exit_code']==0
  invalid={'attempt_id':e['attempt_id'],'episode_key':e['episode_key'],'identity':e['identity'],'attempt_result':ref(out/'attempt-result.json'),
    'worker_receipt':ref(out/'eds_eval/in-worker-audit-receipt.json'),'error':ref(error),'outcome_valid':False,
    'ledger_failure_class_unchanged':e['failure_class'],'root_classification':'ENGINEERING_INITIAL_OBSERVATION_UNBOUNDLOCAL',
    'model_forward_calls':0,'guided_chunks':0,'unguided_chunks':0,'provider_logical_call_attempts':0,
    'scientific_outcome':'Unknown','pre_episode_reset_and_settling_not_excluded':True}
counts={a:{'audited':sum(v['profile']==a for v in accepted),'success':sum(v['profile']==a and v['success'] for v in accepted)} for a in c.ARMS}
assert counts==result['counts'] and result['dispatched']==3 and result['audited_cells']==2
assert status['completed_keys']==[v['episode_key'] for v in accepted] and status['status']=='failed'
assert result['decision']=='INVALID_OR_INTERRUPTED' and result['controller_evidence']['consistent']
assert not result['dev_gate_promoted'] and not result['validation_authorized'] and not result['formal_authorized']
assert abs(cost-1090.1433259700425)<1e-8 and abs(c.local_seconds(events,resources,vars(r))-cost)<1e-8
snap=r.budget_snapshot(events,resources)
assert snap['dispatched']==398 and snap['running']==snap['gpu_healthcheck_inflight']==0
review={'schema':'n30-root-terminal-review-v1','reviewed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'decision':'INVALID_OR_INTERRUPTED','scientific_outcome':'Unknown','interpretation':'Original N30 stopped on a pre-first-decision engineering error; no algorithm rejection or success evidence.',
 'source_commit':source['commit'],'source':ref(V/'source-manifest-execution-v1.json'),'source_files_rehashed':439,
 'plan':ref(V/'plan.frozen.v1.gpu7.json'),'result':ref(V/'result-v1.json'),'terminal_ledger':ref(V/'execution/terminal-ledger-v1.json'),
 'controller':ref(V/'execution/controller-process-v1.json'),'monitor':ref(V/'execution/monitor-process-v1.json'),'controller_exit':ref(V/'execution/root-launch-result-v1.json'),
 'controller_original_process_exited':True,'monitor_original_process_exited':True,'worker_original_processes_exited':closed,
 'dispatched':3,'audited_cells':2,'counts':counts,'accepted_cells':accepted,'invalid_attempts':[invalid],
 'episode_gpu_seconds_observed':cost,'local_gpu_hours_observed':cost/3600,'gpu_preparation_seconds':0.,
 'unrun_original_primary_cells':9,'valid_candidate_episodes':0,'retry_count':0,
 'stage':dict(stage),'provider':'codex_cli/chatgpt/current managed login/gpt-6-astra','http_requests':None,'http_retries':None,
 'root_tensor_replay':False,'receipt_verification':'Current old source and original same-worker receipts independently rehashed before source adoption; no new arithmetic replay.',
 'original_ledger_modified':False,'new_gpu_release':False,'validation_authorized':False,'formal_authorized':False,
 'goal_status':'TARGET_NOT_MET','budget_snapshot':snap,'cpu_seconds':time.process_time()-start}
with (V/'root-terminal-review-v1.json').open('x') as f:json.dump(review,f,indent=2);f.write('\n')
print(json.dumps({k:review[k] for k in ('decision','dispatched','counts','local_gpu_hours_observed','stage','cpu_seconds')}))

