"""Read-only N30 process/scalar monitor; no tensor replay or decisions."""
from pathlib import Path
from collections import Counter
import datetime,json
V=Path(__file__).resolve().parent;W=V.parent.parents[1]/'study_worktree'
COHORT='N30_TERMINAL_BOOLEAN_REPAIR_DEV_20261003'
def read(p):return json.loads(p.read_text())
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def live(record):
 try:
  fields=Path(f"/proc/{record['pid']}/stat").read_text().rsplit(')',1)[1].split()
  return fields[0]!='Z' and fields[19]==str(record['proc_start_ticks']) and record['boot_id']==boot
 except FileNotFoundError:return False
def rows(p):
 if not p.exists():return []
 return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def tail(p):
 if not p.exists():return None
 with p.open('rb') as f:
  f.seek(0,2);length=f.tell();offset=max(0,length-65536);f.seek(offset);data=f.read()
 lines=data.splitlines()
 if offset:lines=lines[1:]
 return json.loads(lines[-1]) if lines else None
controller=read(V/'execution/controller-process-v1.json');monitor=read(V/'execution/monitor-process-v1.json')
statuspath=V/'execution/supervisor-status-v1.json';status=read(statuspath) if statuspath.exists() else {}
local=[x for x in rows(W/'data/attempt-ledger.jsonl') if x.get('identity',{}).get('iteration')==COHORT]
result={'schema':'n30-r2-root-live-observation-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'controller_pid':controller['pid'],'controller_original_live':live(controller),'monitor_original_live':live(monitor),
 'supervisor_status':status.get('status'),'completed_keys':status.get('completed_keys',[]),
 'successes':status.get('successes'),'failure':status.get('failure'),
 'exit':read(V/'execution/root-launch-result-v1.json').get('exit_code') if (V/'execution/root-launch-result-v1.json').exists() else None}
if local:
 last=local[-1];out=Path(last['output_dir']);processpath=out/'process.json'
 result['last_journal']={k:last.get(k) for k in ('event','attempt_id','episode_key','outcome_valid','success','gpu_process_wall_seconds','guided_chunks')}
 if processpath.exists():
  process=read(processpath);result['worker']={'pid':process['pid'],'original_live':live(process),'physical_gpu':last.get('physical_gpu')}
 phase=tail(out/'eds_eval/phase_timing.jsonl');metrics=rows(out/'eds_eval/eds_metrics.jsonl')
 calls=[x for x in rows(out/'eds_eval/stage_events.jsonl') if x.get('codex_logical_call_attempts',0)]
 result['last_phase']={k:phase.get(k) for k in ('global_step','name','event')} if phase else None
 result['guided_metric_rows']=len(metrics)
 progress=[m['executed_progress_continuation'] for m in metrics if 'executed_progress_continuation' in m]
 if progress:
  result['continuation_online_unverified']={'rows':len(progress),'active_rows':sum(m.get('active') is True for m in progress),
    'invalid_evidence_max':max(m.get('invalid_evidence_count',0) for m in progress),
    'reasons':dict(Counter(m.get('reason') for m in progress)),
    'interpretation':'Online scalar observations only; independent worker replay pending unless receipt accepted.'}
 result['stage']={'logical_calls':sum(x.get('codex_logical_call_attempts',0) for x in calls),
   'failed_calls':sum(x.get('codex_failed_calls',0) for x in calls),
   'usage_complete_calls':sum(x.get('codex_usage_complete_calls',0) for x in calls),
   'input_tokens':sum(x.get('codex_input_tokens',0) or 0 for x in calls),
   'output_tokens':sum(x.get('codex_output_tokens',0) or 0 for x in calls),
   'providers':sorted(set((x.get('transport',{}).get('backend'),x.get('transport',{}).get('auth_mode'),x.get('transport',{}).get('model')) for x in calls),key=repr)}
 result['receipt_exists']=(out/'eds_eval/in-worker-audit-receipt.json').exists()
 if result['receipt_exists']:
  receipt=read(out/'eds_eval/in-worker-audit-receipt.json')
  result['receipt_summary']={k:receipt.get(k) for k in ('accepted','error','failure','failure_class','n30_native_counts')}
 result['output_dir']=str(out)
with (V/'execution/root-observation-journal-v1.jsonl').open('a') as f:f.write(json.dumps(result,ensure_ascii=False,allow_nan=False)+'\n')
print(json.dumps(result,ensure_ascii=False,allow_nan=False))

