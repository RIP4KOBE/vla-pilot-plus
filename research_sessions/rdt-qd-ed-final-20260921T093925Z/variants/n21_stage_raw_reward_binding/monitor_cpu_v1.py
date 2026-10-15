"""Read-only concise status; safe before first evidence file exists."""
import json,time
from pathlib import Path
here=Path(__file__).resolve().parent;w=here.parents[1]/'study_worktree'
rows=[json.loads(line) for line in (w/'data/attempt-ledger.jsonl').open()]
rows=[row for row in rows if row.get('identity',{}).get('iteration')=='N21_STAGE_RAW_DEV_20260930']
last=rows[-1] if rows else {};out=Path(last.get('output_dir',str(here/'not-started')))
result={'time_unix':time.time(),'last_event':last.get('event'),'episode_key':last.get('episode_key'),'completed':[{'episode':r['episode_key'],'event':r['event'],'success':r.get('success'),'outcome_valid':r.get('outcome_valid')} for r in rows if r['event'] in ('valid','aborted')]}
p=out/'eds_eval/decision_evidence/episode_000/events.jsonl'
if p.exists():
 refs=[json.loads(x) for x in p.open()]
 if refs: result.update(last_native_event=refs[-1]['events'][-1],evidence_age_s=round(time.time()-p.stat().st_mtime))
s=here/'execution/supervisor-status-gpu7-v1.json'
if s.exists(): result['supervisor']=json.loads(s.read_text())
print(json.dumps(result,ensure_ascii=False))
