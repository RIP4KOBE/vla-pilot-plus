"""Read a small operational summary; no model, simulator, CUDA or new API calls."""
from pathlib import Path
import datetime,json
V=Path(__file__).resolve().parent;ROOT=V.parents[1]/'study_worktree'
COHORT='N29_POPULATION_RELATIVE_TRUST_DEV_20261001'
s=json.loads((V/'execution/supervisor-status-v1.json').read_text())
local=[e for line in (ROOT/'data/attempt-ledger.jsonl').read_text().splitlines() if line.strip() for e in [json.loads(line)] if e.get('identity',{}).get('iteration')==COHORT]
last=local[-1] if local else {}
out={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':s['status'],'audited_cells':len(s['completed_keys']),'successes':s['successes'],'latest_episode':last.get('episode_key'),'latest_event':last.get('event'),'result_exists':(V/'result-v1.json').exists()}
if last:
    p=Path(last['output_dir']);f=p/'eds_eval/stage_events.jsonl'
    events=[]
    if f.exists():
        lines=f.read_text().splitlines()
        for line in lines:
            try:e=json.loads(line)
            except json.JSONDecodeError:continue
            if e.get('query_status')!='skipped':events.append(e)
    out.update(current_stage_calls=len(events),current_stage_errors=sum(e.get('query_ok') is not True for e in events),current_provider_bindings=sorted({str(e.get('transport',{}).get('backend'))+'/'+str(e.get('transport',{}).get('auth_mode')) for e in events}),last_stage_global_step=events[-1].get('global_step') if events else None)
    if (p/'process.json').exists():
        proc=json.loads((p/'process.json').read_text());out['worker_pid']=proc['pid']
    if last.get('event') in {'valid','aborted'}:out.update(latest_outcome_valid=last.get('outcome_valid'),latest_success=last.get('success'))
if s.get('failure'):out['failure']=s['failure']
print(json.dumps(out))
