"""Public runtime metadata only; no prompts/images/tensor/native replay output."""
import json,datetime
from pathlib import Path
C=Path(__file__).resolve().parent;W=C.parents[2]/'study_worktree'
cohort='N25_ACTUATOR_CLIPPED_RBF_DEV_INFRA_CONTINUATION_V1_20260930'
out={'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
for name in ['controller-process-v1.json','supervisor-status-v1.json']:
 p=C/'execution'/name
 if p.exists():
  v=json.loads(p.read_text());out[name]={k:v[k] for k in ['process','status','counts_success','failure_class','failure'] if k in v}
  if 'completed_keys' in v:out[name]['accepted_new_cells']=len(v['completed_keys'])
events=[json.loads(line) for line in (W/'data/attempt-ledger.jsonl').read_text().splitlines() if line.strip()]
own=[x for x in events if x.get('identity',{}).get('iteration')==cohort]
out['dispatches']=sum(x['event']=='dispatched' for x in own)
if own:
 v=own[-1];out['latest_ledger']={k:v[k] for k in ['event','attempt_id','episode_key','outcome_valid','success','reason','gpu_process_wall_seconds'] if k in v}
 folder=Path(v['output_dir'])
 p=folder/'process.json'
 if p.exists():
  proc=json.loads(p.read_text());out['worker']={k:proc[k] for k in ['pid','proc_start_ticks','boot_id'] if k in proc}
 p=folder/'eds_eval/stage_events.jsonl'
 if p.exists():
  calls=[]
  for line in p.read_text().splitlines():
   try:x=json.loads(line)
   except json.JSONDecodeError:continue
   if x.get('codex_logical_call_attempts',0):calls.append(x)
  pairs=[]
  for x in calls:
   t=x.get('transport',{});pair=[t.get(k) for k in ['backend','auth_mode','model','reasoning_effort']]
   if pair not in pairs:pairs.append(pair)
  out['stage']={'logical_calls':sum(x.get('codex_logical_call_attempts',0) for x in calls),
    'completed_calls':sum(x.get('codex_completed_turns',0) for x in calls),'failed_calls':sum(x.get('codex_failed_calls',0) for x in calls),
    'usage_complete_calls':sum(x.get('codex_usage_complete_calls',0) for x in calls),'last_global_step':calls[-1].get('global_step') if calls else None,'observed_transport_pairs':pairs}
 out['native_receipt_present']=(folder/'eds_eval/in-worker-audit-receipt.json').is_file()
p=C/'result-v1.json'
if p.exists():
 v=json.loads(p.read_text());out['terminal']={k:v.get(k) for k in ['decision','audited_cells','counts','new_dispatched','unknown_token_calls','all_attempt_token_usage_complete']}
print(json.dumps(out,ensure_ascii=False))
