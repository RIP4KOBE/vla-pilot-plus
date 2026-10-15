"""Read-only compact N22 progress from its own ledger and event stream."""
import json
import time
from collections import Counter
from pathlib import Path

here = Path(__file__).resolve().parent
root = here.parents[1] / 'study_worktree'
rows = [json.loads(x) for x in (root / 'data/attempt-ledger.jsonl').open()]
rows = [x for x in rows if x.get('identity', {}).get('iteration') == 'N22_HOLD_LIFT_DEV_20260930']
last = rows[-1] if rows else {}
terminal = [x for x in rows if x.get('event') in ('valid', 'aborted')]
totals = {arm: {'completed': 0, 'success': 0, 'invalid': 0} for arm in ('C0', 'Q0', 'N21', 'N22')}
for row in terminal:
    arm = totals[row['identity']['profile']]
    arm['completed'] += 1
    arm['success'] += int(row.get('success') is True)
    arm['invalid'] += int(row.get('outcome_valid') is not True)
result = {'time_unix': time.time(), 'last_event': last.get('event'),
          'episode_key': last.get('episode_key'), 'outcomes_before_native_audit': totals,
          'last_terminal': [{'episode': x['episode_key'], 'event': x['event'],
                             'success': x.get('success'), 'outcome_valid': x.get('outcome_valid')}
                            for x in terminal[-4:]]}
if last.get('output_dir'):
    path = Path(last['output_dir']) / 'eds_eval/decision_evidence/episode_000/events.jsonl'
    if path.exists():
        lines = path.read_text().splitlines()
        if lines:
            result['last_native_event'] = json.loads(lines[-1])['events'][-1]
            result['evidence_age_s'] = round(time.time() - path.stat().st_mtime)
status = here / 'execution/supervisor-status-gpu7-v1.json'
if status.exists():
    state = json.loads(status.read_text())
    result['supervisor'] = {key: state.get(key) for key in ('status', 'successes', 'native',
                           'last_attempt', 'physical_gpu', 'dev_gate_promoted', 'reason', 'detail')}
    result['supervisor']['audited_cells'] = len(state.get('completed_keys', []))
print(json.dumps(result))
