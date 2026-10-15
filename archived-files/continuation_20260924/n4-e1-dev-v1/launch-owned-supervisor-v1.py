"""Root orchestration only; prepare a tracked supervisor after resource resolution."""
import argparse
import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

W = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
B = Path(__file__).resolve().parent
sys.path.insert(0, str(W / 'scripts'))
import qd_ed_final_runner as r
import qd_ed_n4e1_plan as n

parser = argparse.ArgumentParser()
parser.add_argument('--release', type=Path, required=True)
parser.add_argument('--launch-dir', type=Path, required=True)
args = parser.parse_args()
release_path = r.owned(args.release, B)
launch_dir = r.owned(args.launch_dir, B)
release = r.read_json(release_path)
plan_path = Path(release['plan']['path'])
plan = r.read_json(plan_path)
runtime = r.read_json(plan['runtime_manifest_path'])
reference = {'path': str(release_path), 'sha256': r.digest(release_path)}
n.execution_release(reference, plan_path, plan, runtime, release['episode_keys'], W, r)
with r.locked(W / 'data/qd-ed-state.lock'):
    state = r.read_state(W / 'research-state.yaml')
    r.require(not state.get('external_resource_hold', {}).get('active'), 'Unresolved external resource hold')
    r.require(not state.get('external_resource_hold', {}).get('do_not_auto_resume'), 'External do-not-resume authority unresolved')
    r.require(state['budget']['max_episode_attempts'] == 240 and state['budget']['max_gpu_hours'] == 48, 'Private study budget differs')
    r.require(state['budget']['reserved'] == {'baseline': 20, 'development': 100, 'validation': 60, 'formal': 40, 'recovery': 20}, 'Private study bucket caps differ')
    r.require(state['candidate'].get('online_dispatch_authorized') is True, 'Root state has not released dispatch')
    r.require(state['candidate'].get('active_execution_release') == reference, 'Root state release differs')

launch_dir.mkdir(parents=True, exist_ok=True)
for name in ('launch.json', 'launch-result.json', 'status.json', 'supervisor.stdout.log', 'supervisor.stderr.log'):
    r.require(not (launch_dir / name).exists(), 'Preserve prior launch evidence: ' + name)
command = [sys.executable, 'scripts/qd_ed_n4e1_supervise.py', '--plan', str(plan_path),
           '--execution-release', str(release_path), '--execution-release-sha256', reference['sha256'],
           '--status-path', str(launch_dir / 'status.json')]
for key in release['episode_keys']:
    command += ['--episode-key', key]
environment = os.environ.copy()
environment.update(CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1')
now = lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
with (launch_dir / 'supervisor.stdout.log').open('x') as stdout, (launch_dir / 'supervisor.stderr.log').open('x') as stderr:
    process = subprocess.Popen(command, cwd=W, env=environment, stdout=stdout, stderr=stderr)
    launch = {'schema': 'n4e1-owned-supervisor-launch-v1', 'command': command, 'cwd': str(W),
              'wrapper_pid': os.getpid(), 'supervisor_pid': process.pid,
              'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
              'supervisor_proc_start_ticks': Path(f'/proc/{process.pid}/stat').read_text().rsplit(')', 1)[1].split()[19],
              'start_utc': now(), 'release': reference, 'parent_CUDA_VISIBLE_DEVICES': '',
              'child_GPU_binding': 'frozen physicalGPU3/logical0/EGL0', 'episode_keys': release['episode_keys']}
    r.durable_json(launch_dir / 'launch.json', launch)
    print(json.dumps(launch), flush=True)
    def forward_signal(signum, frame):
        if process.poll() is None:
            process.send_signal(signum)
    signal.signal(signal.SIGTERM, forward_signal)
    signal.signal(signal.SIGINT, forward_signal)
    code = process.wait()
    result = {**launch, 'finished_utc': now(), 'exit_code': code}
    r.durable_json(launch_dir / 'launch-result.json', result)
    print(json.dumps({'exit_code': code, 'result': str(launch_dir / 'launch-result.json')}), flush=True)
sys.exit(code if code >= 0 else 128 - code)
