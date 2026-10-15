"""Close the one-dispatch N30 r1 audit failure without replaying native tensors."""
from pathlib import Path
import collections,datetime,json,subprocess,sys,time
K=Path(__file__).resolve().parent;P=K.parent;W=P.parents[1]/'study_worktree'
sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n30_r1_contract as c,qd_ed_n30_r1_bridge as b
start=time.process_time();read=r.read_json;ref=c.ref
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def alive(p):
 try:
  x=Path(f"/proc/{p['pid']}/stat").read_text().rsplit(')',1)[1].split()
  return x[0]!='Z' and x[19]==str(p['proc_start_ticks']) and p['boot_id']==boot
 except FileNotFoundError:return False
source=read(K/'source-manifest-execution-v1.json');plan=read(c.PLAN)
result=read(K/'result-v1.json');status=read(K/'execution/supervisor-status-v1.json')
assert source['commit']==plan['source_commit']=='b2775fa2008a8a88e374c43a5753f8862485af1f'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=W,text=True).strip()==source['commit']
assert source['files']==plan['code_files'] and len(source['files'])==457
for f in source['files']:assert w.sha(W/f['path'])==f['sha256'],f['path']
for name in ('controller-process-v1.json','monitor-process-v1.json'):
 assert not alive(read(K/'execution'/name)),name
exit_record=read(K/'execution/root-launch-result-v1.json')
assert exit_record['exit_code']==1 and exit_record['controller']==ref(K/'execution/controller-process-v1.json')
events=r.read_events(W/'data/attempt-ledger.jsonl');resources=r.read_events(W/'data/gpu-healthcheck-ledger.jsonl')
h=c.history();b.current_subset(h,events)
local=[e for e in events if e.get('identity',{}).get('iteration')==c.COHORT]
assert [e['event'] for e in local]==['reserved','dispatched','valid']
assert [e for e in events if e.get('identity',{}).get('iteration') in {b.OLD,c.COHORT}]==read(K/'execution/terminal-ledger-v1.json')
e=local[-1];row=plan['episodes'][0];out=Path(e['output_dir'])
assert all(v['episode_key']==row['episode_key'] and v['retry_of']==b.FAILED for v in local)
assert e['attempt_id']=='rdt-qd-ed-final-20260921T093925Z__n30_r1_dev_t00_n30_20261003__2138c682c5a7'
assert e['identity']==r.episode_identity(row) and e['source_commit']==source['commit']
assert read(out/'attempt-result.json')==e and result['attempts'][-1]['terminal']==e
assert e['outcome_valid'] is False and e['success'] is False and not alive(read(out/'process.json'))
assert out.resolve().parent==(P/'artifacts/attempts').resolve()
context=read(out/'n23-worker-context.json');receipt=read(out/'eds_eval/in-worker-audit-receipt.json')
assert context['source']==receipt['source']==source and w.read_ref(context['plan'])==plan
assert receipt['context']==ref(out/'n23-worker-context.json') and receipt['accepted'] is False
assert receipt['process_unchanged'] is True and receipt['main_exit_code']==0 and receipt['worker_error_type']=='ValueError'
assert receipt['worker_cuda']['physical_gpu']==7 and receipt['worker_cuda']['physical_uuid']==c.GPU7_UUID
log=(out/'runner.log').read_text()
assert 'Episode 1 finished, success: False, steps: 720' in log and 'ValueError: N30 native: terminal feedback binding' in log
assert 'UnboundLocalError' not in log
metrics=r.read_events(out/'eds_eval/eds_metrics.jsonl');assert len(metrics)==e['guided_chunks']==24
assert e['unguided_chunks']==66
progress=[x['executed_progress_continuation'] for x in metrics]
online={'guided_chunks':24,'unguided_chunks':66,'active_insertions_unverified':sum(x['active'] for x in progress),
 'maximum_invalid_evidence_count':max(x['invalid_evidence_count'] for x in progress),
 'interpretation':'Online scalar observations only; rejected native audit prevents scientific acceptance.'}
calls=[x for x in r.read_events(out/'eds_eval/stage_events.jsonl') if x.get('query_status')!='skipped']
assert len(calls)==e['provider_logical_call_attempts']==15 and e['provider_failed_calls']==0
for x in calls:
 t=x['transport'];assert (t['backend'],t['auth_mode'],t['model'])==('codex_cli','chatgpt','gpt-6-astra')
 assert x['query_status']=='ok' and x['query_ok'] is True
 assert x.get('api_request_attempts') is None and x.get('api_sdk_retry_attempts') is None
stage={'logical_calls':len(calls),'failed_calls':0}
for key in ('input_tokens','output_tokens','cached_input_tokens'):
 assert sum(x['codex_'+key] for x in calls)==e['provider_'+key]
 stage[key]=e['provider_'+key]
accepted=[x['cell'] for x in h['imports']]
assert result['accepted_cells']==accepted and result['audited_cells']==2 and result['new_dispatched']==1 and result['all_dispatched']==4
assert status['completed_keys']==[v['episode_key'] for v in accepted] and status['status']=='failed'
assert result['decision']=='INVALID_OR_INTERRUPTED' and result['controller_evidence']['consistent']
assert not result['dev_gate_promoted'] and not result['validation_authorized'] and not result['formal_authorized']
cost=e['gpu_process_wall_seconds'];assert abs(cost-355.2775675270241)<1e-8
old_review=w.read_ref(ref(P/'root-terminal-review-v1.json'));combined=old_review['episode_gpu_seconds_observed']+cost
assert abs(c.local_seconds(events,resources,vars(r))-combined)<1e-8
snap=r.budget_snapshot(events,resources);assert snap['dispatched']==399 and snap['running']==snap['gpu_healthcheck_inflight']==0
review={'schema':'n30-r1-root-terminal-review-v1','reviewed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'decision':'INVALID_OR_INTERRUPTED','root_classification':'NATIVE_AUDIT_TERMINAL_FEEDBACK_BINDING_FAILURE',
 'scientific_outcome':'Unknown','interpretation':'Completed720steps with rawtaskfailure; rejected mechanism audit means no accepted N30 episode. Root cause pending bounded diagnosis.',
 'source_commit':source['commit'],'source':ref(K/'source-manifest-execution-v1.json'),'source_files_rehashed':457,
 'plan':ref(c.PLAN),'result':ref(K/'result-v1.json'),'terminal_ledger':ref(K/'execution/terminal-ledger-v1.json'),
 'controller':ref(K/'execution/controller-process-v1.json'),'monitor':ref(K/'execution/monitor-process-v1.json'),
 'controller_exit':ref(K/'execution/root-launch-result-v1.json'),'controller_original_process_exited':True,
 'monitor_original_process_exited':True,'worker_process':ref(out/'process.json'),'worker_original_process_exited':True,
 'new_dispatched':1,'combined_dispatched':4,'audited_cells':2,'counts':result['counts'],'accepted_cells':accepted,
 'invalid_attempt':{'attempt_id':e['attempt_id'],'attempt_result':ref(out/'attempt-result.json'),
  'receipt':ref(out/'eds_eval/in-worker-audit-receipt.json'),'context':ref(out/'n23-worker-context.json'),
  'runner_log':ref(out/'runner.log'),'ledger_failure_class_unchanged':e.get('failure_class'),'retry_of':b.FAILED,
  'outcome_valid':False,'main_exit_code':0,'raw_task_success':False,'raw_steps':720,'online_unverified':online},
 'new_episode_gpu_seconds':cost,'combined_episode_gpu_seconds':combined,'combined_gpu_hours':combined/3600,
 'gpu_preparation_seconds':0.,'unrun_original_primary_cells':9,'valid_candidate_episodes':0,
 'new_stage':stage,'old_stage':old_review['stage'],'provider':'codex_cli/chatgpt/current managed login/gpt-6-astra',
 'http_requests':None,'http_retries':None,'root_tensor_replay':False,'original_closure':ref(P/'root-terminal-review-v1.json'),
 'history_bridge':ref(c.BRIDGE),'receipt_verification':'Original controls trusted through closed old-HEAD review and bounded hash-verified metadata bridge; new receipt is rejected and not relabeled.',
 'original_ledger_modified':False,'new_gpu_release':False,'validation_authorized':False,'formal_authorized':False,
 'goal_status':'TARGET_NOT_MET','budget_snapshot':snap,'cpu_seconds':time.process_time()-start}
with (K/'root-terminal-review-v1.json').open('x') as f:json.dump(review,f,indent=2);f.write('\n')
print(json.dumps({x:review[x] for x in ('decision','root_classification','counts','new_episode_gpu_seconds','combined_gpu_hours','new_stage','cpu_seconds')}))
