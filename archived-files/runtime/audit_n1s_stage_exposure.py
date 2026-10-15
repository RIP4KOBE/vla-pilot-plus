"""Descriptive Stage/ED exposure from finished N1S episodes, without new gates."""
from pathlib import Path
import datetime
import hashlib
import json

A = Path(__file__).resolve().parents[1]
W = Path('/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z')
rows = []
for line in (W / 'data/attempt-ledger.jsonl').read_text().splitlines():
    e = json.loads(line)
    if e.get('identity', {}).get('iteration') != 'N1S' or e.get('outcome_valid') is not True:
        continue
    folder = Path(e['output_dir'])
    path = folder / 'eds_eval/stage_events.jsonl'
    raw = path.read_bytes()
    events = [json.loads(v) for v in raw.splitlines() if v.strip()]
    queries = [v for v in events if v.get('query_status') in {'ok','error'}]
    phase = [json.loads(v) for v in (folder / 'eds_eval/phase_timing.jsonl').read_text().splitlines()]
    steps = max(v['global_step'] + 1 for v in phase if v['name']=='adapter_step' and v['event']=='exit')
    last_query = max((v['global_step'] for v in queries), default=None)
    claims = [v['global_step'] for v in queries if v.get('query_ok') is True and v.get('parsed_stage')==0]
    guided, unguided = e['guided_chunks'], e['unguided_chunks']
    rows.append({'attempt_id':e['attempt_id'], 'profile':e['identity']['profile'],
        'task_id':e['identity']['task_id'], 'success':e['success'], 'steps':steps,
        'stage_events_sha256':hashlib.sha256(raw).hexdigest(),
        'stage_queries':len(queries), 'stage_query_errors':sum(v.get('query_ok') is not True for v in queries),
        'stage0_claim_steps':claims, 'contains_stage0_and_final_failure':bool(claims) and not e['success'],
        'last_query_step':last_query, 'steps_after_last_query':steps-last_query if last_query is not None else None,
        'guided_chunks':guided, 'unguided_chunks':unguided, 'guided_fraction':guided/(guided+unguided),
        'guidance_on_query_steps':[v['global_step'] for v in queries if v.get('parsed_guidance') is True]})
result = {'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'iteration':'N1S',
    'completed':len(rows), 'schema_success_is_not_task_success':True,
    'scope':'Descriptive common-controller behavior, not an added acceptance threshold or causal attribution to QD. Success uses the simulator; Stage0 is not a success label. Failed episodes with Stage0 predictions are reported as disagreement with the benchmark outcome.',
    'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'rows':rows}
out = A / 'analysis/n1s/stage-guidance-exposure.json'
out.parent.mkdir(parents=True, exist_ok=True)
temp = out.with_suffix('.json.tmp'); temp.write_text(json.dumps(result,indent=2)); temp.replace(out)
print(json.dumps({'completed':len(rows),'failed_episodes_with_stage0':sum(v['contains_stage0_and_final_failure'] for v in rows),
    'total_stage_queries':sum(v['stage_queries'] for v in rows), 'total_stage_errors':sum(v['stage_query_errors'] for v in rows)}))
