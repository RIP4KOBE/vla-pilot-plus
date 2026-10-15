"""CPU-only synthetic runner interruption and frozen-config relocation probes.

All mutation is limited to tempfile directories and child processes created here.
No model, simulator, GPU command, or model provider is invoked.
"""
import argparse
import ast
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

ROOT = Path('/home/hynx/lizhuo/VLA-Pilot++')
sys.path.insert(0, str(ROOT))


def launcher(base):
    import scripts.run_steering as module
    import scripts.steering_runtime as runtime
    base = Path(base)
    module.ROOT = base
    (base / 'main.py').write_text('# synthetic CPU fixture\n')
    local_file = base / 'local.yaml'
    local_file.write_text('synthetic fixture\n')
    local = {k: str(base) for k in ('rdt_checkpoint', 'text_encoder', 'vision_encoder',
                                   'libero_root', 'libero_config', 'torch_home')}
    local.update(gpu=0, egl_device_id=0)
    module.load_local = lambda _: local
    module.load_config = lambda *a, **k: dict(backend={'libero': {'task_ids_filter': [0]}},
        main={'episode_seed_schedule': [44]}, perception={'gemini': {'model': 'synthetic', 'reasoning_effort': 'none'}})
    module.dependency_manifest = lambda _: {'synthetic': True}
    module.source_manifest = lambda: {'main.py': runtime.digest(base/'main.py')}
    module.git_commit = lambda: 'synthetic'
    module.runtime_environment = lambda _: dict(os.environ, CUDA_VISIBLE_DEVICES='')
    module.progress = lambda _: {'synthetic': True}
    def worker(*args, **kwargs):
        return subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
            cwd=base, env=kwargs['env'], stdout=kwargs['stdout'], stderr=kwargs['stderr'])
    module.subprocess = SimpleNamespace(Popen=worker, STDOUT=subprocess.STDOUT,
        check_output=lambda argv, **kw: '0' if '--query-gpu=memory.used' in argv else 'SYNTHETIC, CPU, 0')
    module.run(SimpleNamespace(local_config=str(local_file), output_dir=str(base/'run'),
                              method='eds', tasks=None, print_config=False))


def interrupted_launcher():
    with tempfile.TemporaryDirectory(prefix='steering-lifecycle-review-') as tmp:
        base = Path(tmp)
        proc = subprocess.Popen([sys.executable, __file__, '--launcher', tmp],
            env=dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1'),
            start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        worker_pid = None
        try:
            path = base/'run/status.json'
            deadline = time.monotonic()+15
            while time.monotonic() < deadline:
                if path.exists():
                    status = json.loads(path.read_text())
                    if status.get('state') == 'running':
                        worker_pid = status['pid']; break
                if proc.poll() is not None:
                    raise RuntimeError(proc.stderr.read().decode())
                time.sleep(.02)
            if worker_pid is None: raise RuntimeError('Synthetic launcher did not reach running')
            proc.terminate(); proc.wait(timeout=10)
            alive = Path(f'/proc/{worker_pid}').exists()
            with (base/'.worktrees/exp/steering-integration/gpu-0.lock').open('a+') as file:
                try:
                    fcntl.flock(file, fcntl.LOCK_EX|fcntl.LOCK_NB); lock_released=True
                except BlockingIOError:
                    lock_released=False
            return dict(scope='Actual frozen run() body; asset/GPU/config dependencies stubbed; worker is CPU sleep',
                launcher_exit_code=proc.returncode, worker_survives_launcher=alive,
                gpu_lock_released_while_worker_alive=lock_released and alive,
                saved_status=json.loads(path.read_text())['state'],
                audit_written=(base/'run/audit.json').exists())
        finally:
            if proc.poll() is None: proc.kill(); proc.wait()
            if worker_pid is not None:
                try: os.kill(worker_pid, signal.SIGTERM)
                except ProcessLookupError: pass


def relocation():
    import copy
    import yaml
    src = ROOT/'scripts/audit_steering.py'
    node = next(n for n in ast.parse(src.read_text()).body if isinstance(n, ast.FunctionDef) and n.name=='protocol_config')
    scope = dict(yaml=yaml, deepcopy=copy.deepcopy, Path=Path)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(src), 'exec'), scope)
    actual_dir = ROOT/'.worktrees/exp/steering-integration/runs/eds-common-20261013'
    manifest = json.loads((actual_dir/'manifest.json').read_text())
    config = yaml.safe_load((actual_dir/'resolved-config.yaml').read_text())
    original = scope['protocol_config'](actual_dir, manifest, config)
    with tempfile.TemporaryDirectory(prefix='steering-relocation-review-') as tmp:
        moved = Path(tmp)/actual_dir.name
        for rel in ('configs/evaluation/libero_object_swap.yaml','configs/steering/eds.yaml'):
            destination=moved/'source'/rel; destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(actual_dir/'source'/rel, destination)
        reconstructed=scope['protocol_config'](moved,manifest,config)
        return dict(original_config_matches=original==config, relocated_config_matches=reconstructed==config,
                    original_output_root=config['hydra']['run']['dir'],
                    reconstructed_output_root=reconstructed['hydra']['run']['dir'],
                    only_hydra_output_root_differs={**reconstructed, 'hydra': config['hydra']}==config,
                    scope='AST-extracted frozen protocol_config; preserved manifest/config bytes; copied two frozen YAML inputs only')


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--launcher'); parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.launcher:
        launcher(args.launcher)
    else:
        result=dict(schema='steering_final_source_review_repros_v1', lifecycle=interrupted_launcher(), relocation=relocation(),
                    cuda_visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES'), gpu_or_api_invocations=0)
        if args.output: args.output.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
