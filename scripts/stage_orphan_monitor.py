#!/usr/bin/env python3
"""Reattach accounting to an owned worker without inventing a lost exit status."""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import time

from stage_closed_loop_run import STUDY, ROOT, progress, audit, atomic_json, utc


def process_identity(pid):
    try:
        stat = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return {'state': stat[0], 'start_ticks': stat[19], 'wait_status': int(stat[49])}
    except FileNotFoundError:
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--pid', required=True, type=int)
    args = parser.parse_args()
    folder = ROOT/'runs'/args.name
    manifest = json.loads((folder/'manifest.json').read_text())
    assert manifest['name'] == args.name
    out = folder/'output'
    previous = json.loads((out/'status.json').read_text())
    assert previous['pid'] == args.pid and previous['status'] == 'running'
    initial = process_identity(args.pid)
    assert initial and initial['state'] != 'Z'
    command = Path(f'/proc/{args.pid}/cmdline').read_bytes().split(b'\0')
    assert b'scripts/stage_closed_loop_worker.py' in command
    assert ('main.eds_eval.job_id='+args.name).encode() in command
    anchor = datetime.datetime.fromisoformat(previous['utc']).timestamp() - previous['elapsed_seconds']
    with (STUDY/'data/qd-ed-runner.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        atomic_json(folder/'supervisor-interruption.json', dict(
            utc=utc(), previous_status=previous, worker_pid=args.pid,
            worker_start_ticks=initial['start_ticks'], monitor_pid=os.getpid(),
            reason='Conversation interruption terminated the parent supervisor; existing worker survived.',
            policy='Continue the existing worker. Never fabricate a successful exit status or rerun an episode.'))
        exit_code = None
        while True:
            identity = process_identity(args.pid)
            if identity is None or identity['start_ticks'] != initial['start_ticks']:
                break
            if identity['state'] == 'Z':
                exit_code = os.waitstatus_to_exitcode(identity['wait_status'])
                break
            info = dict(status='running', utc=utc(), pid=args.pid,
                        elapsed_seconds=time.time()-anchor, adopted_monitor=True, **progress(out))
            atomic_json(out/'status.json', info)
            print(json.dumps(info), flush=True)
            time.sleep(20)
        elapsed = time.time()-anchor
        info = dict(status='exited', utc=utc(), exit_code=exit_code,
            exit_code_observed=exit_code is not None, supervisor_interrupted=True,
            elapsed_seconds=elapsed, **progress(out))
        atomic_json(out/'status.json', info)
        atomic_json(out/'budget-charge.json', dict(episodes_started=info['started'],
            gpu_hours_upper_bound=elapsed/3600, protected_phase=False,
            upper_bound_includes_monitor_polling=True))
    result = audit(folder, manifest)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
