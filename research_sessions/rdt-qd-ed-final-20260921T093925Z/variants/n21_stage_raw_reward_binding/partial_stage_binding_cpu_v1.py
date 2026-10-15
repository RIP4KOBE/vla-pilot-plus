"""Read completed N21 native bundles; not a complete episode validity audit."""
import hashlib,json
from pathlib import Path
import torch
here=Path(__file__).resolve().parent;w=here.parents[1]/'study_worktree'
torch.set_num_threads(1)
rows=[json.loads(x) for x in (w/'data/attempt-ledger.jsonl').open()]
rows=[x for x in rows if x.get('identity',{}).get('iteration')=='N21_STAGE_RAW_DEV_20260930' and x.get('identity',{}).get('profile')=='N21']
if not rows:
 print(json.dumps({'status':'not_started'}));raise SystemExit
out=Path(rows[-1]['output_dir']);ep=out/'eds_eval/decision_evidence/episode_000';idx=ep/'events.jsonl';checked=[]
if idx.exists():
 for line in idx.open():
  try: ref=json.loads(line)
  except json.JSONDecodeError: break
  if not any(x['event']=='terminal_population_stage_binding' for x in ref['events']):continue
  p=ep/ref['bundle'];assert hashlib.sha256(p.read_bytes()).hexdigest()==ref['sha256'];ev=torch.load(p,map_location='cpu',weights_only=True)['events'];f=next(x for x in ev if x['event']=='final_selection');b=next(x for x in ev if x['event']=='terminal_population_stage_binding')
  raw=float(f['values']['selected_raw_provider_quality']);effective=float(f['values']['selected_quality']);bound=float(b['values']['selected_raw_reward'])
  checked.append({'step':f['global_step'],'raw_reward':raw,'effective_quality':effective,'stage_bound_reward':bound,'raw_matches':raw==bound,'bonus_selected':effective!=raw})
print(json.dumps({'status':'partial_readonly','attempt':out.name,'checked_decisions':len(checked),'positive_bonus_selected':sum(x['bonus_selected'] for x in checked),'raw_binding_mismatches':[x for x in checked if not x['raw_matches']],'positive_rows':[x for x in checked if x['bonus_selected']]}))
