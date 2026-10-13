"""Run one immutable online steering cohort with progress and a separate validity audit."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.steering_runtime import (atomic_json, dependency_manifest, digest, git_commit, load_config, load_local,
    rows, runtime_environment, source_manifest, source_unchanged, utc, METHODS, evaluation_directory)


def progress(folder):
    out = Path(folder) / 'output'
    evaluation = evaluation_directory(folder)
    episodes = rows(evaluation / 'episode_compute.jsonl')
    events = rows(evaluation / 'stage_events.jsonl')
    videos = list(out.glob('episode_*/*agentview.mp4'))
    return {'completed': sum(r.get('outcome') == 'completed' for r in episodes),
            'errors': sum(r.get('outcome') != 'completed' for r in episodes),
            'successes': sum('_success' in p.name for p in videos),
            'task_id': events[-1].get('task_id') if events else None,
            'step': events[-1].get('global_step') if events else None,
            'stage_queries': sum(r.get('query_status') in ('ok', 'error') for r in events)}


def run(args):
    local = load_local(args.local_config)
    folder = Path(args.output_dir).resolve()
    tasks = None if args.tasks is None else [int(t) for t in args.tasks.split(',')]
    cfg = load_config(local, method=args.method, output_dir=folder / 'output', tasks=tasks)
    if args.print_config:
        print(yaml.safe_dump(cfg, sort_keys=False))
        return 0
    if folder.exists():
        raise RuntimeError('Run directory exists; inspect its status or use a new explicit run id')
    lock_dir = ROOT / '.worktrees/exp/steering-integration'
    lock_dir.mkdir(parents=True, exist_ok=True)
    with (lock_dir / f"gpu-{local['gpu']}.lock").open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        gpu = subprocess.check_output(['nvidia-smi', '-i', str(local['gpu']),
            '--query-gpu=uuid,name,memory.used', '--format=csv,noheader,nounits'], text=True).strip()
        if int(gpu.rsplit(',', 1)[1].strip()) > 512:
            raise RuntimeError('Selected GPU is not idle; no other processes will be stopped')
        folder.mkdir(parents=True)
        (folder / 'output').mkdir()
        local_snapshot = {key: local[key] for key in ('gpu', 'egl_device_id', 'rdt_checkpoint',
            'text_encoder', 'vision_encoder', 'libero_root', 'libero_config', 'torch_home')}
        local_snapshot['allocator_limit_gib'] = local.get('allocator_limit_gib', 48)
        local_snapshot_path = folder / 'local-config.yaml'
        local_snapshot_path.write_text(yaml.safe_dump(local_snapshot, sort_keys=True))
        preflight_status = {'state': 'preflight', 'started_at': utc(),
                            'launcher_pid': os.getpid(), 'run_dir': str(folder),
                            'planned': len(cfg['backend']['libero']['task_ids_filter']),
                            'scientific_tasks_started': 0}
        atomic_json(folder / 'status.json', preflight_status)
        print(json.dumps({'state': 'verifying_assets', 'run': str(folder)}), flush=True)
        try:
            atomic_json(folder / 'environment.json', dependency_manifest(local))
        except Exception as exc:
            preflight_status.update(state='preflight_failed', completed_at=utc(),
                                    error_type=type(exc).__name__, error=str(exc))
            atomic_json(folder / 'status.json', preflight_status)
            raise
        config_path = folder / 'resolved-config.yaml'
        config_path.write_text(yaml.safe_dump(cfg, sort_keys=False))
        source = source_manifest()
        for path in source:
            dest = folder / 'source' / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / path, dest)
        manifest = {'schema': 'steering_cohort_v2', 'created_at': utc(), 'method': args.method,
                    'evaluation_directory': 'output/evaluation',
                    'code_root': str(ROOT), 'commit': git_commit(), 'source_sha256': source,
                    'config_sha256': digest(config_path), 'local_config_sha256': digest(local_snapshot_path),
                    'input_local_config_sha256': digest(args.local_config),
                    'environment_sha256': digest(folder / 'environment.json'),
                    'gpu': gpu, 'physical_gpu': local['gpu'], 'egl_device_id': local['egl_device_id'],
                    'tasks': cfg['backend']['libero']['task_ids_filter'],
                    'seeds': cfg['main']['episode_seed_schedule'], 'provider': 'codex_cli',
                    'model': cfg['perception']['gemini']['model'],
                    'reasoning_effort': cfg['perception']['gemini']['reasoning_effort'],
                    'fresh_reward': True, 'online_stage': True}
        atomic_json(folder / 'manifest.json', manifest)
        cmd = [sys.executable, str(ROOT / 'scripts/steering_worker.py'), str(config_path)]
        gpu_now = subprocess.check_output(['nvidia-smi', '-i', str(local['gpu']),
            '--query-gpu=memory.used', '--format=csv,noheader,nounits'], text=True).strip()
        if int(gpu_now) > 512:
            preflight_status.update(state='preflight_failed', completed_at=utc(),
                                    error='Selected GPU became occupied during asset verification')
            atomic_json(folder / 'status.json', preflight_status)
            raise RuntimeError(preflight_status['error'])
        with (folder / 'console.log').open('w') as logfile:
            proc = subprocess.Popen(cmd, cwd=ROOT, env=runtime_environment(local),
                                    stdout=logfile, stderr=subprocess.STDOUT)
            status = {'state': 'running', 'pid': proc.pid, 'started_at': utc(), 'argv': cmd,
                      'launcher_pid': os.getpid(), 'run_dir': str(folder),
                      'planned': len(manifest['tasks'])}
            atomic_json(folder / 'status.json', status)
            previous = None
            while proc.poll() is None:
                now = progress(folder)
                atomic_json(folder / 'progress.json', dict(updated_at=utc(), **now))
                if now != previous:
                    print(json.dumps(dict(run=str(folder), **now)), flush=True)
                    previous = now
                time.sleep(5)
            status.update(exit_code=proc.returncode, completed_at=utc(),
                          source_unchanged=source_unchanged(source), state='finished')
            atomic_json(folder / 'status.json', status)
            atomic_json(folder / 'progress.json', dict(updated_at=utc(), **progress(folder)))
        from scripts.audit_steering import audit
        result = audit(folder, exit_code=proc.returncode)
        result['checks']['runtime_source_unchanged'] = status['source_unchanged']
        result['valid'] = all(result['checks'].values())
        atomic_json(folder / 'audit.json', result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return 0 if result['valid'] else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--method', choices=METHODS, default='eds')
    parser.add_argument('--local-config', required=True)
    parser.add_argument('--output-dir', required=True, help='New immutable run directory')
    parser.add_argument('--tasks', help='Comma-separated ids; default is all ten tasks')
    parser.add_argument('--print-config', action='store_true', help='Resolve configuration without GPU/API work')
    args = parser.parse_args()
    return run(args)


if __name__ == '__main__':
    raise SystemExit(main())
