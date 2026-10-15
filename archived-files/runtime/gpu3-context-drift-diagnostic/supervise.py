"""Coordinator for one frozen observation experiment; no GPU APIs."""
import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'scripts'))
import qd_ed_final_runner as r

KEY = 'gpu3_context_drift_c0_t00'
plan_path = ROOT / 'data/qd-ed-gpu3-context-drift-plan.json'
baseline = subprocess.run(['journalctl', '-k', '-b', '--no-pager', '-o', 'json', '-n', '1'],
                          capture_output=True, text=True, timeout=10, check=True)
rows = [json.loads(line) for line in baseline.stdout.splitlines() if line.startswith('{')]
r.require(len(rows) == 1, 'kernel baseline unavailable')
cursor, boot = rows[0]['__CURSOR'], rows[0]['_BOOT_ID']
r.durable_json(FOLDER / 'kernel-baseline.json', {'cursor': cursor, 'boot_id': boot})
cmd = [str(r.PYTHON), str(ROOT / 'scripts/qd_ed_available_gpu_queue.py'), '--plan', str(plan_path),
       '--episode-key', KEY, '--poll-seconds', '30', '--idle-seconds', '120',
       '--status-path', str(FOLDER / 'queue-status.json')]
with (FOLDER / 'queue.log').open('x') as log:
    queue = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
ticks = Path(f'/proc/{queue.pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
record = {'pid': queue.pid, 'proc_start_ticks': ticks, 'argv': cmd, 'physical_gpu': 3,
          'plan_sha256': r.digest(plan_path), 'source_commit': r.read_json(plan_path)['source_commit'],
          'supervisor_pid': os.getpid(), 'supervisor_sha256': r.digest(__file__),
          'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
r.durable_json(FOLDER / 'queue-process.json', record)
print(json.dumps(record), flush=True)
last_status, stop_reason, faults = None, None, []
while queue.poll() is None:
    status_path = FOLDER / 'queue-status.json'
    if status_path.exists():
        status = r.read_json(status_path)['status']
        if status != last_status:
            print(json.dumps({'queue_status': status, 'time_unix': time.time()}), flush=True)
            last_status = status
    events = [e for e in r.read_events(ROOT / 'data/attempt-ledger.jsonl') if e.get('episode_key') == KEY]
    if events and events[-1]['event'] == 'dispatched':
        output = Path(events[0]['output_dir'])
        process_path = output / 'process.json'
        if process_path.exists():
            worker = r.read_json(process_path)
            observation_path = output / 'eds_eval/egl_context_drift.jsonl'
            observations = []
            if observation_path.exists():
                for line in observation_path.read_text().splitlines():
                    try:
                        observations.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            boundaries = {x['boundary'] for x in observations if x.get('event') == 'exit'}
            if boundaries == {'before_first_policy', 'after_first_policy', 'before_first_render'}:
                stop_reason = 'planned_stop_three_context_observations_complete'
            result = subprocess.run(['journalctl', '-k', '-b', '--no-pager', '-o', 'json', '--after-cursor', cursor],
                                    capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if not line.startswith('{'):
                        continue
                    event = json.loads(line)
                    if event.get('_BOOT_ID') != boot:
                        continue
                    cursor = event['__CURSOR']
                    message = event.get('MESSAGE', '')
                    if (message.startswith('NVRM: Xid (PCI:0000:61:00):')
                            and f"pid={worker['pid']}," in message
                            and int(event['__REALTIME_TIMESTAMP']) / 1e6 >= events[-1]['time_unix']):
                        faults.append({'message': message, 'time_unix_us': int(event['__REALTIME_TIMESTAMP'])})
                        if ': 31,' in message or ': 109,' in message:
                            stop_reason = 'owned_graphics_fault_during_context_diagnostic'
            r.durable_json(FOLDER / 'supervisor-status.json', {'time_unix': time.time(), 'boundaries': sorted(boundaries),
                'worker_pid': worker['pid'], 'faults': faults, 'stop_reason': stop_reason})
            if stop_reason:
                proc = Path(f'/proc/{queue.pid}')
                r.require(proc.stat().st_uid == os.getuid() and (proc / 'cwd').resolve() == ROOT,
                          'queue ownership changed')
                r.require((proc / 'stat').read_text().rsplit(')', 1)[1].split()[19] == ticks,
                          'queue PID was reused')
                r.durable_json(FOLDER / 'diagnostic-stop.json', {'time_unix': time.time(), 'reason': stop_reason,
                    'queue_pid': queue.pid, 'worker_pid': worker['pid'], 'observations': observations,
                    'faults': faults, 'no_automatic_retry': True})
                os.kill(queue.pid, signal.SIGTERM)
                print(json.dumps({'stop_reason': stop_reason, 'observations': observations, 'faults': faults}), flush=True)
                break
    time.sleep(2)
try:
    code = queue.wait(timeout=50)
except subprocess.TimeoutExpired:
    print(json.dumps({'cleanup': 'still_running_requires_review', 'queue_pid': queue.pid}), flush=True)
    raise SystemExit(3)
r.durable_json(FOLDER / 'supervisor-result.json', {'queue_exit_code': code, 'stop_reason': stop_reason,
    'time_unix': time.time(), 'study_complete': False})
print(json.dumps({'queue_exit_code': code, 'stop_reason': stop_reason, 'study_complete': False}), flush=True)
