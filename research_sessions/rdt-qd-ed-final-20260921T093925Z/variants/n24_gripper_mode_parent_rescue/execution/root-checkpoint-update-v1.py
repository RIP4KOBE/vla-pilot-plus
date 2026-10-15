"""Coordinator progress bookkeeping only; never dispatches or changes gates."""
import datetime
import hashlib
import json
import sys
from pathlib import Path

import yaml

VARIANT = Path(__file__).resolve().parents[1]
SESSION = VARIANT.parents[1]
WORKTREE = SESSION / 'study_worktree'
RUN = 'rdt-qd-ed-final-20260921T093925Z'
COHORT = 'N24_GRIPPER_MODE_PARENT_RESCUE_DEV_20260930'
sys.path.insert(0, str(WORKTREE))
sys.path.insert(0, '/home/hynx/.codex/skills/arbor-agent-tools/scripts')
from scripts import qd_ed_final_runner as runner
import arbor_state

now = datetime.datetime.now(datetime.timezone.utc).isoformat()
status = json.loads((VARIANT / 'execution/supervisor-status-v1.json').read_text())
boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
workers = []
with runner.locked(WORKTREE / 'data/qd-ed-state.lock'):
    state = runner.read_state(WORKTREE / 'research-state.yaml')
    if state.get('current_iteration', {}).get('candidate') != 'N24':
        raise SystemExit('N24 is no longer current; no bookkeeping written')
    events = runner.read_events(WORKTREE / 'data/attempt-ledger.jsonl')
    latest = {e['attempt_id']: e for e in events
              if e.get('identity', {}).get('iteration') == COHORT}
    for attempt, event in latest.items():
        if event['event'] != 'dispatched':
            continue
        proc_file = Path(event['output_dir']) / 'process.json'
        if not proc_file.exists():
            continue
        process = json.loads(proc_file.read_text())
        stat_path = Path('/proc') / str(process['pid']) / 'stat'
        try:
            actual_start = stat_path.read_text().rsplit(')', 1)[1].split()[19]
        except FileNotFoundError:
            continue
        if str(process.get('proc_start_ticks')) != actual_start or process.get('boot_id') != boot:
            continue
        workers.append({key: process[key] for key in ('pid', 'proc_start_ticks', 'boot_id')}
                       | {'physical_gpu': 7, 'attempt_id': attempt,
                          'episode_key': event['episode_key'], 'observed_at': now})
    budget = runner.budget_snapshot(events, runner.read_events(WORKTREE / 'data/gpu-healthcheck-ledger.jsonl'))
    progress = {'current_owned_workers': workers, 'observed_at': now,
                'accepted_cells': len(status.get('completed_keys', [])),
                'successes': status.get('successes', {}),
                'accepted_cell_denominators': status.get('accepted_cell_denominators', {})}
    state['current_iteration'].update(progress)
    arbor_state.atomic_write(WORKTREE / 'research-state.yaml', yaml.safe_dump(state, sort_keys=False, allow_unicode=True))

with arbor_state.state_lock(WORKTREE, RUN):
    path = WORKTREE / '.arbor/sessions' / RUN / '.coordinator/checkpoint.json'
    checkpoint = json.loads(path.read_text())
    checkpoint.update({'updated_at': now, 'owned_gpu_workers': workers,
                       'worker_observation_at': now, 'budget_snapshot': budget,
                       'n24_accepted_cells': progress['accepted_cells'],
                       'n24_successes': progress['successes'],
                       'n24_denominators': progress['accepted_cell_denominators']})
    arbor_state.atomic_write(path, json.dumps(checkpoint, indent=2) + '\n')
print(json.dumps({'observed_at': now, 'accepted': progress['accepted_cells'],
                  'workers': workers, 'budget': budget,
                  'terminal_result_exists': (VARIANT / 'result-v1.json').exists()}))
