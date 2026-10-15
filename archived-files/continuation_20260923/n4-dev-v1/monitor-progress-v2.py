"""Read only own N4 progress and an explicitly selected new launch directory."""
import argparse
import collections
import datetime
import json
from pathlib import Path
import time

parser = argparse.ArgumentParser()
parser.add_argument('--launch-dir', type=Path, required=True)
args = parser.parse_args()
W = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
result = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
status = args.launch_dir / 'status.json'
if status.exists():
    state = json.loads(status.read_text())
    result['supervisor'] = {k: state.get(k) for k in ['status', 'current_episode_key', 'completed_keys', 'selected_physical_gpu', 'reason']}
    result['GPU3_admission'] = [{k: d.get(k) for k in ['physical_gpu', 'memory_used_mib', 'idle_observed_seconds', 'idle_stable']} for d in state.get('gpu_inventory', []) if d.get('physical_gpu') == 3]
groups = collections.OrderedDict()
for line in (W / 'data/attempt-ledger.jsonl').read_bytes().split(b'\n')[:-1]:
    event = json.loads(line)
    if event.get('identity', {}).get('iteration') == 'N4_TERMINAL_POPULATION_DEV_20260924':
        groups.setdefault(event['attempt_id'], []).append(event)
result['N4_attempts'] = []
for events in groups.values():
    event = events[-1]
    item = {k: event.get(k) for k in ['attempt_id', 'episode_key', 'event', 'physical_gpu', 'gpu_process_wall_seconds', 'outcome_valid', 'success']}
    dispatch = next((e for e in events if e['event'] == 'dispatched'), None)
    if event['event'] not in ['valid', 'invalid', 'aborted'] and dispatch:
        item['elapsed_since_dispatch_s'] = round(time.time() - dispatch['time_unix'], 1)
    output = Path(event['output_dir'])
    if (output / 'process.json').exists():
        process = json.loads((output / 'process.json').read_text())
        item['pid'] = process['pid']
        item['pid_exists'] = Path('/proc', str(process['pid'])).exists()
    metrics = output / 'eds_eval/eds_metrics.jsonl'
    if metrics.exists():
        records = metrics.read_bytes().split(b'\n')[:-1]
        item['guided_metrics_records'] = len(records)
        if records:
            item['latest_guided_global_step'] = json.loads(records[-1]).get('global_step')
    audit = output / 'eds_eval/decision-evidence-audit.json'
    if audit.exists():
        data = json.loads(audit.read_text())
        item['audit'] = {k: data.get(k) for k in ['accepted', 'evidence_complete', 'errors']}
    result['N4_attempts'].append(item)
exit_result = args.launch_dir / 'launch-result.json'
if exit_result.exists():
    result['supervisor_exit'] = json.loads(exit_result.read_text())['exit_code']
print(json.dumps(result, indent=2))
