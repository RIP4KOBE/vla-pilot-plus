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
               VLA_LIBERO_ROOT=str(local['libero_root']),
               TORCH_HOME=str(local['torch_home']), JOBLIB_MULTIPROCESSING='0',
               PYTHONUNBUFFERED='1', TOKENIZERS_PARALLELISM='false',
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
               VLA_STEERING_ALLOCATOR_GIB=str(local.get('allocator_limit_gib', 48)))
    paths = [str(ROOT), str(local['libero_root']), str(ROOT / 'third_party/rdt'),
             str(ROOT / 'third_party/lerobot/src')]
    # Do not inherit a PYTHONPATH that can silently import a research checkout.
    env['PYTHONPATH'] = os.pathsep.join(paths)
    return env


METHODS = ('vls', 'eds', 'eds_qd')


def _merge_profile(base, changes, prefix=''):
    """Profiles override declared settings; misspelled/new settings fail visibly."""
    for name, value in changes.items():
        if name not in base:
            # This optional adapter override makes the effective VLS scale explicit.
            if prefix + name != 'backend.libero.task_guide_scales':
                raise ValueError(f'Unknown steering profile setting: {prefix}{name}')
        if isinstance(value, dict):
            if not isinstance(base.get(name), dict):
                raise ValueError(f'Expected a mapping for {prefix}{name}')
            _merge_profile(base[name], value, prefix + name + '.')
        else:
            base[name] = value


def load_config(local, *, method, output_dir, tasks=None):
    if method not in METHODS:
        raise ValueError(f'Unknown steering method {method!r}; expected {METHODS}')
    cfg = yaml.safe_load((ROOT / 'configs/evaluation/libero_object_swap.yaml').read_text())
    profile = yaml.safe_load((ROOT / f'configs/steering/{method}.yaml').read_text())
    _merge_profile(cfg, profile)
    expected_guidance = 'vls' if method == 'vls' else 'eds'
    expected_archive = 'grid_archive' if method == 'eds_qd' else 'none'
    if (cfg['main']['guidance_type'] != expected_guidance or
            cfg['main']['eds_config']['qd_archive_mode'] != expected_archive):
        raise ValueError('Steering method and effective algorithm/archive settings disagree')
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
    scales = cfg['backend']['libero'].get('task_guide_scales')
    if scales is not None:
        if len(scales) != len(all_tasks):
            raise ValueError('Task guide scales must cover the full declared task list')
        scale_by_task = dict(zip(all_tasks, scales))
        cfg['backend']['libero']['task_guide_scales'] = [scale_by_task[t] for t in tasks]
    cfg['steering']['method'] = method
    cfg['main']['eds_eval'].update(method_label=method, job_id=out.parent.name)
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
                     if p.is_file() and p.suffix in ('.py', '.yaml', '.txt', '.json', '.patch')
                     and '__pycache__' not in p.parts and p.name not in ('local.yaml',))
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(set(paths))}


def source_unchanged(manifest):
    return source_manifest() == manifest


def evaluation_directory(folder, manifest=None):
    """Shared logs live under evaluation; old immutable cohorts remain readable."""
    folder = Path(folder)
    if manifest is None:
        path = folder / 'manifest.json'
        manifest = json.loads(path.read_text()) if path.exists() else {}
    relative = Path(manifest.get('evaluation_directory', 'output/eds_eval'))
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Evaluation directory must be relative to its cohort')
    target = (folder / relative).resolve()
    if not target.is_relative_to(folder.resolve()):
        raise ValueError('Evaluation directory escapes its cohort')
    return target


def git_commit():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()


def dependency_manifest(local):
    """Record actual assets and imported dependency revisions before loading CUDA."""
    import importlib.metadata
    from scripts.steering_dependency_compat import verify_runtime_compat
    runtime_compatibility = verify_runtime_compat()
    from scripts.prepare_steering_assets import verify_libero, verify_rng, verify_libero_paths
    from scripts.steering_model_assets import verify_model_assets
    packages = {}
    for name in ('torch', 'torchvision', 'numpy', 'transformers', 'diffusers', 'mujoco',
                 'robosuite', 'hydra-core', 'openai', 'lerobot'):
        packages[name] = importlib.metadata.version(name)
    model_assets = verify_model_assets(local, repository_root=ROOT)
    submodules = {}
    revisions = {'rdt': 'b896f4dcac8ed1c3fae4a056200db267607f131f',
                 'lerobot': '715debf6c1723a28f1a57d4274a8c4ec35b6a417'}
    for name, expected in revisions.items():
        path = ROOT / 'third_party' / name
        submodules[name] = {
            'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=path, text=True).strip(),
            'dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=path, text=True)),
        }
        if submodules[name]['commit'] != expected or submodules[name]['dirty']:
            raise ValueError(f'Runtime vendor {name} must match the clean pinned revision {expected}')
    # A shared environment can contain stale duplicate dist-info directories.
    # Record actual imported modules in a separate CPU process, so this check
    # cannot advance the policy worker's RNG or initialize its CUDA context.
    code = '''import importlib, json, hashlib
from pathlib import Path
names = ['torch', 'torchvision', 'numpy', 'transformers', 'diffusers', 'accelerate',
         'einops', 'gymnasium', 'PIL', 'psutil', 'mujoco', 'hydra', 'openai', 'cv2', 'lerobot']
result = {}
for name in names:
    module = importlib.import_module(name)
    path = Path(module.__file__).resolve()
    result[name] = {'module_version': str(getattr(module, '__version__', 'not_exported')),
                    'file': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
import torch
assert not torch.cuda.is_initialized()
print(json.dumps(result))
'''
    env = runtime_environment(local)
    env['CUDA_VISIBLE_DEVICES'] = ''
    imported = subprocess.check_output([sys.executable, '-c', code], cwd=ROOT,
                                       env=env, text=True)
    imported_packages = json.loads(imported.splitlines()[-1])
    return {'python': sys.version, 'packages': packages, 'submodules': submodules,
            'runtime_compatibility': runtime_compatibility,
            'imported_packages': imported_packages,
            'package_scope': 'distribution metadata and CPU-imported module entrypoints; not a full dependency tree hash',
            'codex_cli': subprocess.check_output(['codex', '--version'], text=True).strip(),
            'libero': verify_libero(Path(local['libero_root'])),
            'libero_paths': verify_libero_paths(local),
            'rng': verify_rng(ROOT / 'tests/fixtures/steering_rng'),
            'model_assets': model_assets}


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
