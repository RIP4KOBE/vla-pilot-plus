"""Descriptive comparison of separately reported same-seed control repeats."""
from pathlib import Path
import datetime
import itertools
import json
A=Path(__file__).resolve().parents[1]
W=Path('/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z')
groups={}
for line in (W/'data/attempt-ledger.jsonl').read_text().splitlines():
    e=json.loads(line);i=e.get('identity',{})
    if e.get('outcome_valid') is True and i.get('iteration') in ['N1S','N1T']:
        key=tuple(i[k] for k in ['profile','task_id','env_seed','policy_seed','init_index'])
        groups.setdefault(key,{})[i['iteration']]=e
rows=[]
for key,versions in groups.items():
    if set(versions)!={'N1S','N1T'}:continue
    old,new=versions['N1S'],versions['N1T']
    def load(e):return [json.loads(x) for x in (Path(e['output_dir'])/'eds_eval/stage_events.jsonl').read_text().splitlines()]
    se,te=load(old),load(new)
    def decisions(es):return [{k:e.get(k) for k in ['global_step','parsed_stage','parsed_guidance','query_status']} for e in es]
    sd,td=decisions(se),decisions(te)
    mismatch=next(({'old':a,'new':b} for a,b in itertools.zip_longest(sd,td) if a!=b),None)
    rows.append({'profile':key[0],'task_id':key[1],'old_attempt':old['attempt_id'],'new_attempt':new['attempt_id'],
        'old_success':old['success'],'new_success':new['success'],
        'stage_decision_sequence_equal':sd==td,'first_recorded_sequence_mismatch':mismatch,
        'old_stage_calls':len(se),'new_stage_calls':len(te),
        'old_guided_chunks':old['guided_chunks'],'new_guided_chunks':new['guided_chunks'],
        'new_recovered_reconnect_calls':sum(bool(e['transport'].get('error_events')) and e.get('query_ok') for e in te)})
result={'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'scope':'Descriptive same-seed repeats across separately frozen local transport acceptance conditions. Do not pool success rates. First recorded decision mismatch does not identify its cause: per-query image hashes were not retained, so equal provider inputs are not established. No new scientific gate.', 'rows':rows}
p=A/'analysis/n1t/old-new-clean-control-comparison.json';p.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'paired_repeats':len(rows),'decision_sequences_equal':sum(v['stage_decision_sequence_equal'] for v in rows),'last':rows[-1] if rows else None}))
