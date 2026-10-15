"""Honor existing GPU2 priority, only stopping the verified idle GPU3 queue."""
from pathlib import Path
import datetime
import json
import os
import signal
import sys
import time

W = Path('/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z')
A = Path(__file__).resolve().parents[1]
P = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
STATUS = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/n4-dev-v1/first3-status.json')
PID = 3021562
TICKS = '8671531'
BOOT = '2a1fa95f-ab0d-488c-a298-fc488ddd2af7'
sys.path.insert(0, str(W / 'scripts'))
import qd_ed_final_runner as r

OUT = A / 'resource/gpu3-priority-boundary-pause-20260924'
OUT.mkdir(exist_ok=False)
record = {'schema': 'authorized-clean-episode-boundary-pause-v1',
    'authorization': 'User selected GPU2 N1U priority and authorized pausing the other GPU3 remaining queue after its active episode; continuation keeps this priority.',
    'reason': 'Continue GPU2 research; prevent further consumption using the other worktree outdated pre-transfer bucket caps.',
    'pid': PID, 'start_ticks': TICKS, 'boot_id': BOOT,
    'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'script_sha256': r.digest(Path(__file__)), 'status': 'waiting_current_episode',
    'maximum_wait_seconds': 1800, 'active_episode_abort_allowed': False}
r.durable_json(OUT / 'status.json', record)
deadline = time.monotonic() + 1800
while time.monotonic() < deadline:
    proc = Path(f'/proc/{PID}')
    if not proc.exists():
        record.update(status='queue_already_exited', signal_sent=False)
        break
    args = (proc / 'cmdline').read_bytes().decode().split('\0')
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == BOOT
    assert (proc / 'stat').read_text().split(') ', 1)[1].split()[19] == TICKS
    assert 'scripts/qd_ed_n4_supervise.py' in args and Path(os.readlink(proc / 'cwd')) == P
    status = r.read_json(STATUS)
    if status.get('status') != 'waiting':
        time.sleep(2)
        continue
    with r.locked(W / 'data/qd-ed-state.lock'):
        events = r.read_events(W / 'data/attempt-ledger.jsonl')
        groups = r.event_groups(events)
        if any(g[-1]['event'] not in r.TERMINAL for g in groups.values()):
            continue
        snapshot = r.budget_snapshot(events, r.read_events(W / 'data/gpu-healthcheck-ledger.jsonl'))
        if snapshot['running'] or snapshot['gpu_healthcheck_inflight']:
            continue
        status = r.read_json(STATUS)
        if status.get('status') != 'waiting':
            continue
        pidfd = os.pidfd_open(PID)
        try:
            assert (proc / 'stat').read_text().split(') ', 1)[1].split()[19] == TICKS
            assert (proc / 'cmdline').read_bytes().decode().split('\0') == args
            record.update(status='boundary_pause_signal_sent', signal_sent=True,
                signal_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                snapshot=snapshot, ledger_sha256=r.digest(W / 'data/attempt-ledger.jsonl'),
                completed_keys=status.get('completed_keys', []),
                remaining_keys=[k for k in status['episode_keys'] if k not in status.get('completed_keys', [])],
                status_before_signal_sha256=r.digest(STATUS))
            r.durable_json(OUT / 'status.json', record)
            signal.pidfd_send_signal(pidfd, signal.SIGTERM)
        finally:
            os.close(pidfd)
        break
else:
    record.update(status='wait_limit_reached_no_signal', signal_sent=False)
r.durable_json(OUT / 'status.json', record)
print(json.dumps(record), flush=True)
