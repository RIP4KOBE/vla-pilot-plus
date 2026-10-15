"""Track initial resumption of the unchanged GPU2 study after resource isolation."""
import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

X = Path('/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z')
D = Path(__file__).resolve().parent
R = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z/runtime/n1w-gpu2-independent-v1')
sys.path.insert(0, str(X / 'scripts'))
import qd_ed_final_runner as r

authorization = r.read_json(R / 'resumption-authorization.json')
assert authorization['status'] == 'authorized'
assert r.digest(D / 'authorization.json') == '4026c141ff9bd06f31734c0a43122327b359c35bd847670f641961df9ce81f47'
assert r.digest(D / 'migration-validation.json') == authorization['resource_isolation_validation']['sha256']
assert r.digest(authorization['plan']['path']) == authorization['plan']['sha256']
with r.locked(X / 'data/qd-ed-state.lock'):
    state = r.read_state(X / 'research-state.yaml')
    assert state['resource_isolation']['status'] == 'ACTIVE'
    assert state['resource_isolation']['validation_status'] == 'PASS'
    assert state['execution_migration']['same_study_budget'] is False
    assert not state['external_resource_hold']['active']
    assert state['gpu_pool'] == [2] and state['max_concurrent_gpu_workers'] == 1
    assert state['budget']['max_episode_attempts'] == 250 and state['budget']['max_gpu_hours'] == 48
    assert state['budget']['n1w_authorization'] == authorization['original_cohort_authorization']
for name in ('launch.json', 'launch-result.json', 'status.json', 'supervisor.stdout.log', 'supervisor.stderr.log'):
    assert not (R / name).exists(), 'Preserve prior launch evidence'
command = [sys.executable, 'scripts/qd_ed_n1v_supervise.py', '--plan', authorization['plan']['path'], '--status', str(R / 'status.json')]
env = os.environ.copy()
env.update(CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1')
now = lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
with (R / 'supervisor.stdout.log').open('x') as stdout, (R / 'supervisor.stderr.log').open('x') as stderr:
    process = subprocess.Popen(command, cwd=X, env=env, stdout=stdout, stderr=stderr)
    record = {'schema': 'independent-gpu2-owned-supervisor-launch-v1', 'command': command,
              'cwd': str(X), 'wrapper_pid': os.getpid(), 'supervisor_pid': process.pid,
              'supervisor_proc_start_ticks': Path(f'/proc/{process.pid}/stat').read_text().rsplit(')', 1)[1].split()[19],
              'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(), 'start_utc': now(),
              'resumption_authorization': {'path': str(R / 'resumption-authorization.json'), 'sha256': r.digest(R / 'resumption-authorization.json')},
              'source_commit': authorization['source_commit'], 'parent_CUDA_VISIBLE_DEVICES': '',
              'physical_gpu': 2, 'child_GPU_binding': 'unchanged frozen GPU2 runtime'}
    r.durable_json(R / 'launch.json', record)
    print(json.dumps(record), flush=True)
    def forward(signum, frame):
        if process.poll() is None:
            process.send_signal(signum)
    signal.signal(signal.SIGTERM, forward)
    signal.signal(signal.SIGINT, forward)
    code = process.wait()
    r.durable_json(R / 'launch-result.json', {**record, 'exit_code': code, 'finished_utc': now()})
    print(json.dumps({'exit_code': code, 'result': str(R / 'launch-result.json')}), flush=True)
sys.exit(code if code >= 0 else 128 - code)
