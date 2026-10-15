#!/usr/bin/env python3
"""Record the single owned GPU3 supervisor after its immutable launch."""
import json
import os
from pathlib import Path
import sys
import tempfile
import yaml

W = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
B = Path(__file__).resolve().parent
L = B / 'remaining9-v1'
D = B / 'first3-release-v1'
sys.path.insert(0, str(W / 'scripts'))
import qd_ed_final_runner as r


def ref(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': r.digest(path)}


launch = r.read_json(L / 'launch.json')
assert launch['release'] == ref(D / 'remaining9-execution-release.json')
assert launch['boot_id'] == Path('/proc/sys/kernel/random/boot_id').read_text().strip()
pid = launch['supervisor_pid']
assert Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19] == launch['supervisor_proc_start_ticks']
with r.locked(W / 'data/qd-ed-state.lock'):
    path = W / 'research-state.yaml'
    state = r.read_state(path)
    assert state['candidate']['active_execution_release'] == launch['release']
    assert state['candidate']['status'] == 'N4E1_DEV_REMAINING9_RELEASED'
    state['candidate']['status'] = 'N4E1_DEV_REMAINING9_SUPERVISOR_RUNNING'
    state['resource_isolation']['owned_supervisor'] = {
        'pid': pid, 'launch': ref(L / 'launch.json'), 'status_path': str(L / 'status.json'),
        'launch_result_path': str(L / 'launch-result.json'), 'terminal_status': 'RUNNING',
    }
    handle, temporary = tempfile.mkstemp(prefix='.research-state.n4e1-', suffix='.yaml', dir=W)
    try:
        with os.fdopen(handle, 'w') as stream:
            yaml.safe_dump(state, stream, sort_keys=False, allow_unicode=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        descriptor = os.open(W, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
print(json.dumps({'status': state['candidate']['status'], 'supervisor_pid': pid,
                  'launch': ref(L / 'launch.json')}))
