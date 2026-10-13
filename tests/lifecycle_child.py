"""Owned CPU processes for lifecycle regression tests, never scientific workers."""
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from scripts.steering_process import LauncherInterrupted, worker_lifecycle

role, folder = sys.argv[1], Path(sys.argv[2])
if role == 'grandchild':
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    (folder/'grandchild.json').write_text(json.dumps({'pid': os.getpid()}))
    time.sleep(60)
elif role == 'worker':
    subprocess.Popen([sys.executable, __file__, 'grandchild', str(folder)], start_new_session=True)
    (folder/'worker.json').write_text(json.dumps({'pid': os.getpid()}))
    time.sleep(60)
elif role == 'launcher':
    with (folder/'gpu.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            with worker_lifecycle(folder, grace_seconds=.25) as owner:
                owner.spawn([sys.executable, __file__, 'worker', str(folder)])
                (folder/'status.json').write_text(json.dumps({'state':'running','partial_steps':7}))
                while not (folder/'grandchild.json').exists(): time.sleep(.01)
                (folder/'ready').write_text('ready')
                time.sleep(60)
        except LauncherInterrupted as exc:
            raise SystemExit(128+exc.signum)
