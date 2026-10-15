#!/usr/bin/env python3
"""Start the frozen N18 Dev cohort only after GPU3 has no compute process."""
from __future__ import annotations

import json
import fcntl
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
SESSION = HERE.parent.parent
WORKTREE = SESSION / 'study_worktree'
PLAN = HERE / 'plan.frozen.v1.json'
RELEASE = HERE / 'execution-release.v1.json'
ARTIFACTS = SESSION / 'artifacts/continuation_20260929/n18-close-then-lift-dev-v1'
LEDGER = WORKTREE / 'data/attempt-ledger.jsonl'
EVENTS = HERE / 'gpu3-wait-events.jsonl'
GPU_UUID = 'GPU-62052fa1-37e0-79dc-21aa-5c0f25c0c315'
COHORT = 'N18_CLOSE_THEN_LIFT_DEV_20260929'


def event(kind, **values):
    with EVENTS.open('a') as stream:
        stream.write(json.dumps({'time_unix': time.time(), 'event': kind, **values}, sort_keys=True) + '\n')
        stream.flush()


def cohort_dispatches():
    rows = [json.loads(line) for line in LEDGER.read_text().splitlines() if line.strip()]
    return sum(row.get('event') == 'dispatched'
               and row.get('identity', {}).get('iteration') == COHORT for row in rows)


def gpu3_free():
    gpus = subprocess.check_output(['nvidia-smi', '--query-gpu=index,uuid',
                                    '--format=csv,noheader'], text=True)
    mapping = {int(row.split(',', 1)[0].strip()): row.split(',', 1)[1].strip()
               for row in gpus.splitlines() if row.strip()}
    if mapping.get(3) != GPU_UUID:
        raise RuntimeError('GPU3 physical UUID changed')
    compute = subprocess.check_output(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid',
                                       '--format=csv,noheader'], text=True)
    return not any(row.split(',', 1)[0].strip() == GPU_UUID
                   for row in compute.splitlines() if row.strip())


def main():
    lock = (HERE / 'gpu3-wait.lock').open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    event('wait_started', gpu_uuid=GPU_UUID)
    last_busy = None
    while True:
        if cohort_dispatches():
            event('stopped_after_dispatch', dispatches=cohort_dispatches())
            return 1
        try:
            free = gpu3_free()
        except Exception as exc:
            event('probe_error', error=type(exc).__name__, detail=str(exc))
            time.sleep(30)
            continue
        if not free:
            if last_busy is not True:
                event('external_gpu3_compute_active')
            last_busy = True
            time.sleep(30)
            continue
        last_busy = False
        statuses = sorted(ARTIFACTS.glob('supervisor-status-attempt-*.json'))
        ordinal = len(statuses) + 1
        status = ARTIFACTS / f'supervisor-status-attempt-{ordinal:02d}.json'
        event('gpu3_free_supervisor_start', status=str(status))
        command = [sys.executable, 'scripts/qd_ed_n18_dev_supervise.py',
                   '--plan', str(PLAN), '--release', str(RELEASE),
                   '--status', str(status)]
        result = subprocess.run(command, cwd=WORKTREE, check=False)
        event('supervisor_exited', returncode=result.returncode,
              dispatches=cohort_dispatches(), status=str(status))
        if result.returncode == 0:
            return 0
        if cohort_dispatches():
            return result.returncode
        time.sleep(30)


if __name__ == '__main__':
    raise SystemExit(main())
