"""Portable configuration, environment and provenance for RDT steering."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.codex_only_runtime import validate_config, worker_environment


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def load_local(path):
    local = yaml.safe_load(Path(path).read_text())
    required = ('gpu', 'egl_device_id', 'rdt_checkpoint', 'text_encoder',
                'vision_encoder', 'libero_root', 'libero_config', 'torch_home')
    if not isinstance(local, dict) or any(k not in local for k in required):
        raise ValueError('Local config requires: ' + ', '.join(required))
    for key in required[2:]:
        p = Path(local[key]).expanduser()
        if not p.is_absolute():
            p = ROOT / p
        local[key] = str(p.resolve())
        if not p.is_dir():
            raise ValueError(f'Missing local directory: {key}={p}')
    if int(local['gpu']) < 0 or int(local['egl_device_id']) < 0:
        raise ValueError('GPU and EGL identifiers must be nonnegative')
    return local


def runtime_environment(local, base=None):
    env = worker_environment(base)
    # Diagnostics must be opt-in, never inherited from a developer's shell.
    for key in ('QD_ED_CUDA_EGL_SERIALIZE', 'QD_ED_RENDER_LIFETIME',
                'QD_ED_MUJOCO_PHASE_DIAGNOSTICS'):
        env.pop(key, None)
    env.update(CUDA_VISIBLE_DEVICES=str(local['gpu']), CUDA_DEVICE_ORDER='PCI_BUS_ID',
               MUJOCO_EGL_DEVICE_ID=str(local['egl_device_id']),
               MUJOCO_GL='egl', PYOPENGL_PLATFORM='egl',
               LIBERO_CONFIG_PATH=str(local['libero_config']),
               TORCH_HOME=str(local['torch_home']), JOBLIB_MULTIPROCESSING='0',
               PYTHONUNBUFFERED='1', TOKENIZERS_PARALLELISM='false',
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
               VLA_STEERING_ALLOCATOR_GIB=str(local.get('allocator_limit_gib', 48)))
    paths = [str(ROOT), str(local['libero_root']), str(ROOT / 'third_party/rdt'),
             str(ROOT / 'third_party/lerobot/src')]
    # Do not inherit a PYTHONPATH that can silently import a research checkout.
    env['PYTHONPATH'] = os.pathsep.join(paths)
    return env


def load_config(local, *, method, output_dir, tasks=None):
    if method != 'eds':
        raise ValueError('EDS migration is being verified; other modes are not yet released')
    cfg = yaml.safe_load((ROOT / 'configs/evaluation/libero_object_swap.yaml').read_text())
    all_tasks = cfg['backend']['libero']['task_ids_filter']
    seeds = dict(zip(all_tasks, cfg['main']['episode_seed_schedule']))
    tasks = all_tasks if tasks is None else list(tasks)
    if not tasks or len(tasks) != len(set(tasks)) or any(t not in seeds for t in tasks):
        raise ValueError('Tasks must be distinct LIBERO object-swap ids from 0 to 9')
    tasks = sorted(tasks)
    out = Path(output_dir).resolve()
    cfg['main'].update(episode_num=len(tasks), episode_start_index=0,
                       episode_seed_schedule=[seeds[t] for t in tasks])
    cfg['backend']['libero']['task_ids_filter'] = tasks
    cfg['steering']['method'] = method
    cfg['main']['eds_eval'].update(method_label=method, job_id=out.name)
    cfg['main']['episode_rng_fixture_manifest'] = str(ROOT / cfg['main']['episode_rng_fixture_manifest'])
    cfg['perception']['vlm_agent']['query_template_dir'] = str(ROOT / 'vlm_query/target_distance')
    cfg['policy']['rdt'].update(pretrained_path=local['rdt_checkpoint'],
                               text_encoder=local['text_encoder'], vision_encoder=local['vision_encoder'])
    cfg['hydra']['run']['dir'] = str(out)
    validate_config(cfg)
    return cfg


def source_manifest():
    paths = [ROOT / 'main.py']
    for folder in ('core', 'utils', 'vlm_query', 'scripts', 'configs'):
        paths.extend(p for p in (ROOT / folder).rglob('*')
                     if p.is_file() and p.suffix in ('.py', '.yaml', '.txt', '.json')
                     and '__pycache__' not in p.parts and p.name not in ('local.yaml',))
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(set(paths))}


def source_unchanged(manifest):
    return all((ROOT / path).is_file() and digest(ROOT / path) == sha
               for path, sha in manifest.items())


def git_commit():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()


def dependency_manifest(local):
    """Record actual assets and imported dependency revisions before loading CUDA."""
    import importlib.metadata
    from scripts.prepare_steering_assets import verify_libero, verify_rng, model_files
    packages = {}
    for name in ('torch', 'torchvision', 'numpy', 'transformers', 'diffusers', 'mujoco',
                 'robosuite', 'hydra-core', 'openai', 'lerobot'):
        packages[name] = importlib.metadata.version(name)
    model_paths = model_files(Path(local['rdt_checkpoint']), Path(local['text_encoder']),
                              Path(local['vision_encoder']), Path(local['torch_home']))
    submodules = {}
    for name in ('rdt', 'lerobot'):
        path = ROOT / 'third_party' / name
        submodules[name] = {
            'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=path, text=True).strip(),
            'dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=path, text=True)),
        }
    return {'python': sys.version, 'packages': packages, 'submodules': submodules,
            'codex_cli': subprocess.check_output(['codex', '--version'], text=True).strip(),
            'libero': verify_libero(Path(local['libero_root'])),
            'rng': verify_rng(ROOT / 'tests/fixtures/steering_rng'),
            'models': [{'path': str(p), 'sha256': digest(p), 'bytes': p.stat().st_size}
                       for p in model_paths]}


def rows(path):
    path = Path(path)
    result = []
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError:
                # A concurrently written final line is not a completed event.
                continue
    return result
