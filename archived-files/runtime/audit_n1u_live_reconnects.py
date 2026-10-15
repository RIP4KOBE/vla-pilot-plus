"""Read-only live call audit; writes derived evidence, never dispatches or retries."""
from pathlib import Path
import datetime
import hashlib
import json

A = Path(__file__).resolve().parents[1]
W = Path('/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z')
observations = []
for raw in (W / 'data/attempt-ledger.jsonl').read_bytes().splitlines(keepends=True):
    if not raw.endswith(b'\n'):
        continue
    dispatch = json.loads(raw)
    if dispatch.get('event') != 'dispatched' or dispatch['identity']['iteration'] != 'N1U':
        continue
    source = Path(dispatch['output_dir']) / 'eds_eval/stage_events.jsonl'
    if not source.exists():
        continue
    for line in source.read_bytes().splitlines(keepends=True):
        if not line.endswith(b'\n'):
            continue
        event = json.loads(line)
        transport = event.get('transport', {})
        if not event.get('query_ok') or not transport.get('error_events'):
            continue
        assert transport['process_returncode'] == 0
        assert transport['process_timed_out'] is False
        assert transport['event_policy'] == 'completed_reconnect_v1'
        assert transport['completed_turns'] == event['codex_usage_complete_calls'] == event['codex_logical_call_attempts'] == 1
        assert all(v['classification'] == 'numbered_reconnecting_notice' for v in transport['error_events'])
        observations.append({
            'attempt_id': dispatch['attempt_id'], 'global_step': event['global_step'],
            'source': str(source), 'event_line_sha256': hashlib.sha256(line).hexdigest(),
            'query_ok': event['query_ok'], 'error': event.get('error'),
            'query_latency_s': event['codex_call_latency_s'],
            **{k: transport[k] for k in ('process_returncode', 'process_timed_out', 'event_types', 'error_events', 'event_policy', 'completed_turns')},
            'usage_complete_calls': event['codex_usage_complete_calls'],
            'logical_call_attempts': event['codex_logical_call_attempts'],
            'input_tokens': event['codex_input_tokens'], 'output_tokens': event['codex_output_tokens'],
            'parsed_stage': event['parsed_stage'], 'parsed_guidance': event['parsed_guidance'],
        })
report = {'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'scope': 'Prospective live reconnect handling; no retrospective identification of the missing N1S error payload; not task success evidence. CLI internal HTTP retry totals remain unobserved.',
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'observations': observations}
target = A / 'analysis/n1u/live-reconnect-observations.json'
temporary = target.with_suffix('.json.tmp')
temporary.write_text(json.dumps(report, indent=2)); temporary.replace(target)
print(json.dumps({'recovered_calls': len(observations), 'last': observations[-1] if observations else None}))
