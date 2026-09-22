#!/usr/bin/env python3
"""Prepare isolated, local-only runtime inputs for the final QD/ED study.

No model, CUDA, simulator, or network imports. Existing inputs are read-only.
"""
from __future__ import annotations

import argparse
import ast
import csv
import ctypes
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import time


CANONICAL_CACHE = Path('/home/hynx/VLA-Pilot++/outputs/libero/2026-06-04_13-21-01')
DEPENDENCY_COMMITS = {
    'rdt': 'b896f4dcac8ed1c3fae4a056200db267607f131f',
    'lerobot': '715debf6c1723a28f1a57d4274a8c4ec35b6a417',
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint(path: Path, ownership_root: Path | None = None) -> dict:
    path = path.absolute()
    resolved = path.resolve(strict=True)
    if ownership_root is not None and not resolved.is_relative_to(ownership_root.resolve()):
        raise ValueError('Runtime input escapes its owned subtree')
    record = {'path': str(path), 'resolved_path': str(resolved),
              'size_bytes': path.stat().st_size, 'sha256': sha256(path)}
    if path.is_symlink():
        record['link_target'] = os.readlink(path)
        if ownership_root is not None:
            record['ownership_root'] = str(ownership_root.resolve())
    return record


def enumerate_egl_devices_metadata() -> list[dict]:
    """Query device metadata only: no display/context, CUDA, or rendering calls.

    Constants/signatures follow the installed OpenGL.raw.EGL EXT.device_base,
    EXT.device_drm and NV.device_cuda definitions. EGLAttrib is pointer-sized.
    """
    library = ctypes.CDLL('libEGL.so.1')
    library.eglGetProcAddress.argtypes = [ctypes.c_char_p]
    library.eglGetProcAddress.restype = ctypes.c_void_p

    def extension(name, result, args):
        address = library.eglGetProcAddress(name.encode())
        if not address:
            raise RuntimeError('Missing EGL device metadata extension: ' + name)
        return ctypes.CFUNCTYPE(result, *args)(address)

    devices_query = extension('eglQueryDevicesEXT', ctypes.c_uint,
                              [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_int)])
    attribute_query = extension('eglQueryDeviceAttribEXT', ctypes.c_uint,
                                [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_ssize_t)])
    string_query = extension('eglQueryDeviceStringEXT', ctypes.c_char_p, [ctypes.c_void_p, ctypes.c_int])
    count = ctypes.c_int()
    if not devices_query(0, None, ctypes.byref(count)) or not 0 < count.value <= 128:
        raise RuntimeError('EGL device enumeration returned no valid device count')
    handles = (ctypes.c_void_p * count.value)()
    if not devices_query(count.value, handles, ctypes.byref(count)):
        raise RuntimeError('EGL device enumeration failed')
    result = []
    for index in range(count.value):
        device = handles[index]
        extensions = (string_query(device, 0x3055) or b'').decode().split()
        row = {'egl_device_index': index, 'extensions': extensions}
        if 'EGL_NV_device_cuda' in extensions:
            ordinal = ctypes.c_ssize_t()
            row['cuda_attribute_ok'] = bool(attribute_query(device, 0x323A, ctypes.byref(ordinal)))
            row['physical_cuda_ordinal'] = ordinal.value if row['cuda_attribute_ok'] else None
        if 'EGL_EXT_device_drm' in extensions:
            row['drm_device_file'] = (string_query(device, 0x3233) or b'').decode()
            device_path = Path('/sys/class/drm') / Path(row['drm_device_file']).name / 'device'
            if device_path.exists():
                row['drm_pci_bus_id'] = device_path.resolve().name
        result.append(row)
    return result


def normalized_pci_bus_id(value: str) -> str:
    """Normalize NVIDIA's eight-digit and sysfs's four-digit PCI domains."""
    match = re.fullmatch(r'([0-9a-fA-F]+):([0-9a-fA-F]{2}):([0-9a-fA-F]{2})\.([0-7])', str(value))
    if match is None:
        raise RuntimeError('Invalid PCI bus identity')
    domain, bus, device, function = (int(part, 16) for part in match.groups())
    return f'{domain:04x}:{bus:02x}:{device:02x}.{function:x}'


def bind_gpu_metadata(devices: list[dict], gpu_rows: list[dict], physical_gpu: int) -> dict:
    if type(physical_gpu) is not int or physical_gpu < 0:
        raise RuntimeError('Physical GPU index must be a nonnegative integer')
    matches = [d for d in devices if d.get('cuda_attribute_ok') is True and d.get('physical_cuda_ordinal') == physical_gpu]
    gpus = [g for g in gpu_rows if str(g.get('index')) == str(physical_gpu)]
    if len(matches) != 1 or len(gpus) != 1:
        raise RuntimeError(f'GPU{physical_gpu} metadata mapping is absent or ambiguous')
    device, gpu = matches[0], gpus[0]
    if type(device.get('egl_device_index')) is not int or device['egl_device_index'] < 0:
        raise RuntimeError('Invalid EGL device index')
    if not str(gpu.get('uuid', '')).startswith('GPU-') or not gpu.get('driver_version'):
        raise RuntimeError('NVIDIA UUID/driver identity missing')
    normalized_pci_bus_id(gpu.get('pci_bus_id', ''))
    if device.get('drm_pci_bus_id'):
        if normalized_pci_bus_id(device['drm_pci_bus_id']) != normalized_pci_bus_id(gpu['pci_bus_id']):
            raise RuntimeError(f'EGL DRM PCI identity conflicts with physical GPU{physical_gpu}')
    result = {'physical_gpu': physical_gpu, 'egl_device_index': device['egl_device_index'],
            'uuid': gpu['uuid'], 'pci_bus_id': gpu['pci_bus_id'], 'driver_version': gpu['driver_version'],
            'drm_pci_verified': bool(device.get('drm_pci_bus_id')),
            'metadata_mapping_verified': True, 'cuda_egl_verified': False}
    if physical_gpu == 7:
        result['historical_gpu7_egl4_holds'] = device['egl_device_index'] == 4
    return result


def bind_gpu7_metadata(devices: list[dict], gpu_rows: list[dict]) -> dict:
    """Compatibility helper for historical GPU7 metadata and its tests."""
    return bind_gpu_metadata(devices, gpu_rows, 7)


def query_gpu_egl_metadata(physical_gpu: int) -> dict:
    # The NV extension reports ordinals in the process-visible CUDA namespace.
    # Enumerate without a mask; the real probe independently checks Torch UUID
    # and the current EGL display under the subsequently frozen one-GPU mask.
    if 'CUDA_VISIBLE_DEVICES' in os.environ or os.environ.get('CUDA_DEVICE_ORDER') != 'PCI_BUS_ID':
        raise RuntimeError('Metadata enumeration requires no CUDA_VISIBLE_DEVICES and CUDA_DEVICE_ORDER=PCI_BUS_ID')
    devices = enumerate_egl_devices_metadata()
    raw = subprocess.check_output(['nvidia-smi', '--query-gpu=index,uuid,pci.bus_id,driver_version',
                                   '--format=csv,noheader,nounits'], text=True, timeout=15)
    rows = [dict(zip(['index', 'uuid', 'pci_bus_id', 'driver_version'], [field.strip() for field in row]))
            for row in csv.reader(io.StringIO(raw))]
    return {**bind_gpu_metadata(devices, rows, physical_gpu), 'devices': devices,
            'created_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'metadata_cuda_ordinal_namespace': 'unmasked_pci_bus_id',
            'enumeration_only': True, 'display_or_context_calls': False,
            'allowed_egl_calls': ['eglGetProcAddress', 'eglQueryDevicesEXT', 'eglQueryDeviceAttribEXT', 'eglQueryDeviceStringEXT']}


def query_gpu7_egl_metadata() -> dict:
    return query_gpu_egl_metadata(7)


def populate_dependency(source: Path, target: Path, expected_commit: str) -> dict:
    """Export a clean exact gitlink snapshot without inheriting a .git file."""
    head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True)
    if head != expected_commit or dirty:
        raise RuntimeError('Dependency source must be clean at the exact gitlink commit')
    if target.exists() and any(target.iterdir()):
        raise FileExistsError(f'Dependency target is not empty: {target}')
    archive = subprocess.check_output(['git', '-C', str(source), 'archive', '--format=tar', head])
    target.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:') as tar:
        for member in tar.getmembers():
            parts = Path(member.name).parts
            if member.name.startswith('/') or '..' in parts or '.git' in parts or '.env' in parts:
                raise RuntimeError('Unsafe dependency archive member')
        tar.extractall(target, filter='data')
    return {'source': str(source), 'target': str(target), 'commit': head,
            'archive_sha256': hashlib.sha256(archive).hexdigest()}


def task_identity(bddl: Path, task_id: int) -> dict:
    text = bddl.read_text()
    interests = re.search(r'\(:obj_of_interest\s+(.*?)\n\s*\)', text, re.S)
    if interests is None:
        raise ValueError('BDDL has no object identity')
    target, basket = interests.group(1).strip().split()
    if basket != 'basket_1':
        raise ValueError('Only frozen object-to-basket tasks are supported')
    name = target.removesuffix('_1')
    return {'task_id': task_id, 'task_name': bddl.stem,
            'expected_target_object': target + '_main',
            'expected_basket_object': basket + '_main',
            'target_description': name.replace('_', ' '), 'init_index': 0}


def prepare_task_cache(source: Path, canonical: Path, target: Path, identity: dict) -> dict:
    """Retain canonical reward bytes; bind only cached Stage text identity."""
    metadata = json.loads((source / 'metadata.json').read_text())
    if metadata.get('key_points_objects_map', {}).get('0') != identity['expected_target_object']:
        raise ValueError('Historical per-task cache identity does not match BDDL')
    target.mkdir(parents=True, exist_ok=False)
    for name in ['stage1_guidance.txt', 'stage2_guidance.txt']:
        shutil.copyfile(canonical / name, target / name)
    for name in ['prompt.txt', 'query_img.png']:
        shutil.copyfile(source / name, target / name)
    metadata['qd_ed_task_identity'] = identity
    metadata['qd_ed_provenance'] = {
        'metadata_source': str(source), 'reward_source': str(canonical),
        'source_metadata_sha256': sha256(source / 'metadata.json'),
        'source_output_sha256': sha256(source / 'output_raw.txt'),
        'identity_only_engineering_repair': True,
        'initial_keypoints_are_historical_provenance_only': True,
    }
    (target / 'metadata.json').write_text(json.dumps(metadata, indent=2, sort_keys=True) + '\n')
    output = (canonical / 'output_raw.txt').read_text()
    lines = []
    for line in output.splitlines(keepends=True):
        if line.startswith('# Stage '):
            line = line.replace('alphabet soup can', identity['target_description'])
            line = line.replace('(keypoint 1)', '(basket keypoints in the current mapping)')
        lines.append(line)
    (target / 'output_raw.txt').write_text(''.join(lines))
    return {**identity, 'cache_dir': str(target), 'source_cache': str(source),
            'stage_description_policy': 'canonical template; target identity replaced; basket uses live mapping',
            'canonical_reward_sha256': {n: sha256(target / n) for n in ['stage1_guidance.txt', 'stage2_guidance.txt']}}


def verify_manifest(manifest: dict) -> None:
    for item in manifest['files']:
        path = Path(item['path'])
        if item.get('resolved_path', str(path.resolve())) != str(path.resolve()):
            raise RuntimeError(f'Runtime input symlink resolution changed: {path}')
        if 'link_target' in item and (not path.is_symlink() or os.readlink(path) != item['link_target']):
            raise RuntimeError(f'Runtime input symlink changed: {path}')
        if 'ownership_root' in item and not path.resolve().is_relative_to(Path(item['ownership_root']).resolve()):
            raise RuntimeError(f'Runtime input escaped its owned subtree: {path}')
        if not path.is_file() or path.stat().st_size != item['size_bytes'] or sha256(path) != item['sha256']:
            raise RuntimeError(f'Runtime input identity changed: {path}')


def prepare(worktree: Path, artifact_root: Path, dependency_source: Path) -> dict:
    worktree, artifact_root = worktree.resolve(), artifact_root.resolve()
    runtime = artifact_root / 'runtime'
    manifest_path = runtime / 'setup_manifest.json'
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text())
        if existing['worktree'] != str(worktree):
            raise RuntimeError('Runtime manifest belongs to another worktree')
        verify_manifest(existing)
        return existing
    if runtime.exists():
        raise FileExistsError('Uncommitted runtime setup directory already exists; inspect before recovery')
    runtime.mkdir(parents=True)
    deps = [populate_dependency(dependency_source / name, worktree / 'third_party' / name, commit)
            for name, commit in DEPENDENCY_COMMITS.items()]
    lib = worktree / 'third_party/libero_pro/libero/libero'
    for name in ['bddl_files', 'init_files']:
        shutil.copytree(lib / name / 'libero_object_swap', runtime / 'libero_inputs' / name / 'libero_object_swap')
    (runtime / 'datasets').mkdir()
    config = {'benchmark_root': str(lib), 'assets': str(lib / 'assets'),
              'bddl_files': str(runtime / 'libero_inputs/bddl_files'),
              'init_states': str(runtime / 'libero_inputs/init_files'), 'datasets': str(runtime / 'datasets')}
    config_dir = runtime / 'libero_config'
    config_dir.mkdir()
    # JSON is also valid YAML, and avoids adding an import-time dependency.
    (config_dir / 'config.yaml').write_text(json.dumps(config, indent=2, sort_keys=True) + '\n')
    tree = ast.parse((lib / 'benchmark/libero_suite_task_map.py').read_text())
    task_names = ast.literal_eval(tree.body[0].value)['libero_object_swap']
    tasks = {}
    canonical = CANONICAL_CACHE / 'episode_1/vlm_agent'
    for index, name in enumerate(task_names):
        bddl = runtime / 'libero_inputs/bddl_files/libero_object_swap' / (name + '.bddl')
        init = runtime / 'libero_inputs/init_files/libero_object_swap' / (name + '.pruned_init')
        identity = task_identity(bddl, index)
        task = prepare_task_cache(CANONICAL_CACHE / f'episode_{index+1}/vlm_agent', canonical,
                                  runtime / 'guidance' / f'task_{index}', identity)
        tasks[str(index)] = {**task, 'bddl_path': str(bddl), 'init_path': str(init)}
    hub = Path('/home/hynx/.cache/torch/hub')
    hub_target = runtime / 'torch/hub'
    shutil.copytree(hub / 'facebookresearch_dinov2_main', hub_target / 'facebookresearch_dinov2_main',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.git'))
    (hub_target / 'checkpoints').mkdir()
    shutil.copyfile(hub / 'checkpoints/dinov2_vitb14_pretrain.pth', hub_target / 'checkpoints/dinov2_vitb14_pretrain.pth')
    shutil.copyfile(hub / 'trusted_list', hub_target / 'trusted_list')
    files = sorted(p for p in runtime.rglob('*') if p.is_file())
    # Include exact populated source and benchmark assets to bind runtime dependencies.
    for dep in deps:
        files.extend(sorted(p for p in Path(dep['target']).rglob('*') if p.is_file()))
    files.extend(sorted(p for p in lib.rglob('*') if p.is_file() and '__pycache__' not in p.parts))
    ownership_roots = [runtime, *(Path(dep['target']) for dep in deps), lib]
    records = [fingerprint(p, next(owner for owner in ownership_roots if p.absolute().is_relative_to(owner))) for p in files]
    manifest = {'schema': 'qd-ed-runtime-setup-v1', 'worktree': str(worktree),
                'artifact_root': str(artifact_root), 'dependencies': deps, 'tasks': tasks,
                'files': records,
                'environment': {'LIBERO_CONFIG_PATH': str(config_dir), 'TORCH_HOME': str(runtime / 'torch'),
                    'PYTHONPATH': ':'.join(str(worktree / p) for p in ['third_party/lerobot/src', 'third_party/rdt', 'third_party/libero_pro']),
                    'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
                    'PYTHONDONTWRITEBYTECODE': '1'},
                'main_overrides': ['+main.require_task_cache_identity=true'],
                'controls_label_suffix': '_input_repaired', 'cuda_egl_verified': False,
                'provider_ready': False,
                'frozen_stage_provider': {'base_url': 'https://api.poe.com/v1', 'model': 'gemini-2.5-flash',
                                          'credential_env_name': 'OPENAI_API_KEY'},
                'provider_note': 'Runtime injected provider does not match frozen endpoint; root awaits explicit user decision. Never redirect an existing credential to a different endpoint.'}
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--worktree', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--artifact-root', type=Path, required=True)
    parser.add_argument('--dependency-source', type=Path, default=Path('/home/hynx/VLA-Pilot++/third_party'))
    args = parser.parse_args()
    result = prepare(args.worktree, args.artifact_root, args.dependency_source)
    print(json.dumps({'manifest': str(args.artifact_root / 'runtime/setup_manifest.json'),
                      'tasks': len(result['tasks']), 'files': len(result['files'])}))
