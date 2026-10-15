"""Read-only live N23 progress; public counters only, no raw Stage responses."""
import json,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]/'study_worktree'
COHORT='N23_CLIPPED_QUALITY_DEV_V2_20260930'

def lines(path):
    if not path.exists():return []
    raw=path.read_bytes()
    raw=raw[:raw.rfind(b'\n')+1]
    return [json.loads(v) for v in raw.splitlines() if v.strip()]

status_path=HERE/'execution/supervisor-status-gpu7-v2.json'
status=json.loads(status_path.read_text()) if status_path.exists() else {}
events=[v for v in lines(ROOT/'data/attempt-ledger.jsonl') if v.get('identity',{}).get('iteration')==COHORT]
groups={}
for e in events:groups.setdefault(e['attempt_id'],[]).append(e)
current=[]
for group in groups.values():
    e=group[-1]
    if e['event'] in {'valid','aborted'}:continue
    p=Path(e['output_dir']);pr=p/'process.json'
    process=json.loads(pr.read_text()) if pr.exists() else {}
    pid=process.get('pid');alive=False
    if pid:
        try:
            fields=(Path('/proc')/str(pid)/'stat').read_text().rsplit(') ',1)[1].split()
            alive=(fields[19]==str(process.get('proc_start_ticks')) and fields[0]!='Z'
                and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==process.get('boot_id'))
        except (FileNotFoundError,IndexError):pass
    stage=lines(p/'eds_eval/stage_events.jsonl');metrics=lines(p/'eds_eval/eds_metrics.jsonl')
    phases=lines(p/'eds_eval/phase_timing.jsonl')
    calls=[v for v in stage if v.get('codex_logical_call_attempts',0)>0]
    steps=[v.get('global_step') for v in stage+metrics+phases if type(v.get('global_step')) is int]
    current.append({'attempt_id':e['attempt_id'],'profile':e['identity']['profile'],'task':e['identity']['task_id'],
        'pid':pid,'identity_alive':alive,'gpu':e.get('physical_gpu'),'wall_seconds':round(time.time()-process['time_unix'],1) if process.get('time_unix') else None,
        'last_observed_step':max(steps) if steps else None,'guided_records':len(metrics),
        'stage_logical_calls':sum(v.get('codex_logical_call_attempts',0) for v in stage),
        'stage_completed_turns':sum(v.get('codex_completed_turns',0) for v in stage),
        'stage_failed_calls':sum(v.get('codex_failed_calls',0) for v in stage),
        'providers':sorted({(v.get('transport') or {}).get('backend','unknown') for v in calls}),
        'auth_modes':sorted({(v.get('transport') or {}).get('auth_mode','unknown') for v in calls})})
print(json.dumps({'status':status.get('status'),'completed_cells':len(status.get('completed_keys',[])),
    'successes':status.get('successes'),'denominators':status.get('accepted_cell_denominators'),
    'dispatched':sum(e['event']=='dispatched' for e in events),'current':current,
    'failure_class':status.get('failure_class'),'dev_gate_promoted':status.get('dev_gate_promoted')},ensure_ascii=False))

