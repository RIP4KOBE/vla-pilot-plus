"""Run PI05 + VLS on standard LIBERO Object, using the shared online controller."""
from pathlib import Path
import argparse
import fcntl
import json
import os
import shutil
import subprocess
import sys
import time
import yaml
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.pi05_runtime import load_local, load_config, environment_receipt
from scripts.steering_runtime import atomic_json, digest, source_manifest, source_unchanged, git_commit, runtime_environment, utc
from scripts.steering_process import worker_lifecycle, LauncherInterrupted
from scripts.run_steering import progress


def run(args):
    local = load_local(args.local_config)
    folder = Path(args.output_dir).resolve()
    tasks = [int(t) for t in args.tasks.split(',')] if args.tasks else None
    cfg = load_config(local, folder/'output', tasks)
    if args.print_config:
        print(yaml.safe_dump(cfg,sort_keys=False)); return 0
    if folder.exists():
        raise FileExistsError('Use a new output directory; previous attempts are immutable')
    lock_dir = ROOT/'.worktrees/exp/steering-integration'
    lock_dir.mkdir(parents=True,exist_ok=True)
    with (lock_dir/f"gpu-{local['gpu']}.lock").open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        def gpu_idle():
            line = subprocess.check_output(['nvidia-smi','-i',str(local['gpu']),
                '--query-gpu=uuid,name,memory.used','--format=csv,noheader,nounits'],text=True).strip()
            if int(line.rsplit(',',1)[1]) > 512:
                raise RuntimeError('GPU is occupied; no other process will be stopped')
            return line
        gpu = gpu_idle()
        folder.mkdir(parents=True)
        with worker_lifecycle(folder) as owner:
            status = dict(state='preflight',started_at=utc(),launcher_pid=os.getpid(),run_dir=str(folder),
                          planned=len(cfg['backend']['libero']['task_ids_filter']))
            atomic_json(folder/'status.json',status)
            print(json.dumps(status),flush=True)
            try:
                receipt = environment_receipt(local)
                env = runtime_environment(local)
                env.update(OMP_NUM_THREADS='4',MKL_NUM_THREADS='4')
                # The mapper checks CUDA identity and EGL UUID binding in a child,
                # before the scientific worker initializes any random stream.
                mapping = subprocess.check_output([sys.executable,str(ROOT/'scripts/list_steering_devices.py'),
                    '--gpu',str(local['gpu'])],env={**env,'CUDA_VISIBLE_DEVICES':''},text=True)
                receipt['device_mapping'] = json.loads(mapping)
                if receipt['device_mapping']['egl_device_id'] != local['egl_device_id']:
                    raise ValueError('GPU/EGL mapping mismatch')
                atomic_json(folder/'environment.json',receipt)
                (folder/'resolved-config.yaml').write_text(yaml.safe_dump(cfg,sort_keys=False))
                (folder/'local-config.yaml').write_text(yaml.safe_dump(local,sort_keys=True))
                source = source_manifest()
                for path in source:
                    dest = folder/'source'/path; dest.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(ROOT/path,dest)
                manifest = dict(schema='pi05_vls_cohort_v1',created_at=utc(),method='vls',policy='pi05',
                    benchmark='libero_object',evaluation_directory='output/evaluation',code_root=str(ROOT),
                    commit=git_commit(),source_sha256=source,config_sha256=digest(folder/'resolved-config.yaml'),
                    local_config_sha256=digest(folder/'local-config.yaml'),environment_sha256=digest(folder/'environment.json'),
                    gpu=gpu,physical_gpu=local['gpu'],egl_device_id=local['egl_device_id'],
                    tasks=cfg['backend']['libero']['task_ids_filter'],seeds=cfg['main']['episode_seed_schedule'],
                    provider='codex_cli',model='gpt-6-astra',reasoning_effort='ultra',fresh_reward=True,online_stage=True)
                atomic_json(folder/'manifest.json',manifest)
                if args.preflight:
                    status.update(state='preflight_pass',completed_at=utc(),scientific_tasks_started=0)
                    atomic_json(folder/'status.json',status)
                    print(json.dumps(status),flush=True); return 0
                gpu_idle()
            except Exception as exc:
                status.update(state='preflight_failed',completed_at=utc(),error=str(exc))
                atomic_json(folder/'status.json',status); raise
            cmd = [sys.executable,str(ROOT/'scripts/steering_worker.py'),str(folder/'resolved-config.yaml')]
            with (folder/'console.log').open('x') as log:
                proc = owner.spawn(cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
                status.update(state='running',pid=proc.pid,argv=cmd)
                atomic_json(folder/'status.json',status)
                previous = None
                while proc.poll() is None:
                    now = progress(folder)
                    atomic_json(folder/'progress.json',dict(updated_at=utc(),**now))
                    if now != previous:
                        print(json.dumps(now),flush=True); previous = now
                    time.sleep(5)
            status.update(state='finished',exit_code=proc.returncode,completed_at=utc(),source_unchanged=source_unchanged(source))
            atomic_json(folder/'status.json',status)
            atomic_json(folder/'progress.json',dict(updated_at=utc(),**progress(folder)))
            from scripts.audit_pi05 import audit
            result = audit(folder)
            atomic_json(folder/'audit.json',result)
            print(json.dumps(result,ensure_ascii=False),flush=True)
            return 0 if result['valid'] else 2


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--local-config',required=True)
    p.add_argument('--output-dir',required=True)
    p.add_argument('--tasks',help='Sorted task ids; omitted means all ten, one episode each')
    p.add_argument('--print-config',action='store_true',help='CPU configuration preview only')
    p.add_argument('--preflight',action='store_true',help='Verify assets, dependencies and device identity; no model/API/episode')
    args = p.parse_args()
    try: return run(args)
    except LauncherInterrupted as exc: return 128+exc.signum

if __name__=='__main__':
    raise SystemExit(main())
