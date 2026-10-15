"""CPU-only content/loader identity checks for the frozen RDT steering assets.

No model imports, deserialization, downloads, subprocesses, or CUDA/API use.
The default tolerates existing bytecode and unrelated documentation/weights.
Use clean_distribution only when validating a newly assembled DINO source pack.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

DEFAULT_MANIFEST = Path(__file__).with_name('steering_model_assets_manifest.json')
ROOT_KEYS = ('rdt_checkpoint', 'text_encoder', 'vision_encoder', 'torch_home')
DINO_PREFIX = 'hub/facebookresearch_dinov2_main/'
REQUIRED = {
    'rdt_checkpoint': ('config.json', 'ema/model.safetensors'),
    'text_encoder': ('config.json', 'pytorch_model.bin', 'spiece.model',
                     'tokenizer_config.json', 'special_tokens_map.json'),
    'vision_encoder': ('config.json', 'preprocessor_config.json', 'model.safetensors'),
    'torch_home': (DINO_PREFIX + 'hubconf.py', 'hub/checkpoints/dinov2_vitb14_pretrain.pth'),
}


class ModelAssetsError(ValueError):
    """Expected identity or actual loader selection differs."""


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def _relative(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or '..' in path.parts or str(path) != value:
        raise ModelAssetsError(f'Invalid manifest relative path: {value!r}')
    return value


def _check_file(path, expected, label):
    if not path.is_file():
        raise ModelAssetsError(f'Missing required file: {label}')
    if path.stat().st_size != expected['bytes']:
        raise ModelAssetsError(f'Size mismatch: {label}')
    actual = digest(path)
    if actual != expected['sha256']:
        raise ModelAssetsError(f'SHA256 mismatch: {label}')
    return {'bytes': expected['bytes'], 'sha256': actual}


def _first_file(paths):
    return next((p for p in paths if p.is_file()), None)


def _require_selected(selected, expected, label):
    # Compare lexical absolute names, not resolve(): a shadow symlink still
    # changes the selected loader filename/format even if content is shared.
    if selected != expected:
        name = 'none' if selected is None else str(selected)
        raise ModelAssetsError(f'Loader selection differs for {label}: {name}')
    return str(selected)


def _selections(roots, entries):
    rdt = roots['rdt_checkpoint']
    search_dirs = [rdt / 'ema', rdt / 'rdt/ema', rdt, rdt / 'rdt']
    names = ('model.safetensors', 'pytorch_model.bin', 'mp_rank_00_model_states.pt', 'rdt-1b.pt')
    weight = _first_file(p / name for p in search_dirs for name in names)
    config_dirs = []
    # Matches core/rdt_policy_steer.py config_search_dirs construction.
    for directory in search_dirs:
        config_dirs.append(directory)
        if directory.parent not in config_dirs:
            config_dirs.append(directory.parent)
    # The actual RDT config resolver uses exists(), including a bad directory.
    config = next((p / name for p in config_dirs for name in ('config.yaml', 'config.json')
                   if (p / name).exists()), None)
    selected = {
        'rdt_weight': _require_selected(weight, rdt / 'ema/model.safetensors', 'RDT weight'),
        'rdt_config': _require_selected(config, rdt / 'config.json', 'RDT config'),
    }
    # Fixed Transformers 4.53.3, use_safetensors=None, installed safetensors.
    hf_names = ('model.safetensors', 'model.safetensors.index.json',
                'pytorch_model.bin', 'pytorch_model.bin.index.json')
    for key, expected_name in (('text_encoder', 'pytorch_model.bin'),
                               ('vision_encoder', 'model.safetensors')):
        folder = roots[key]
        selected[key + '_weight'] = _require_selected(
            _first_file(folder / name for name in hf_names), folder / expected_name, key)
        # Unsupported profile guard: PEFT can redirect loading when installed.
        # The accepted environment does not contain PEFT; no redirect is claimed here.
        if (folder / 'adapter_config.json').exists():
            raise ModelAssetsError(f'Unexpected loader input: {key}/adapter_config.json')
    for name in ('tokenizer.json', 'added_tokens.json'):
        if (roots['text_encoder'] / name).exists() and ('text_encoder', name) not in entries:
            raise ModelAssetsError(f'Unexpected tokenizer input: text_encoder/{name}')
    return selected


def verify_model_assets(local, manifest_path=None, *, repository_root=None, clean_distribution=False):
    """Hash expected files and check actual selection, accepting HF blob symlinks.

    local is the already parsed machine config; CLI YAML parsing is separate.
    Omit manifest_path to use the checked-in expected identity beside this module.
    repository_root optionally checks the three embedded normalization sources.
    Large weights are read sequentially but never deserialized.
    """
    manifest_path = DEFAULT_MANIFEST if manifest_path is None else Path(manifest_path)
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get('schema') != 'steering_model_identity_v1':
        raise ModelAssetsError('Unsupported model identity manifest schema')
    roots = {key: Path(local[key]).expanduser().resolve() for key in ROOT_KEYS}
    for key, folder in roots.items():
        if not folder.is_dir():
            raise ModelAssetsError(f'Missing logical root: {key}')
    for key in ('text_encoder', 'vision_encoder'):
        if (roots[key] / 'snapshots').is_dir():
            raise ModelAssetsError(f'Use an explicit snapshot directory: {key}')
    entries = {}
    for item in manifest['files']:
        key, name = item['root'], _relative(item['path'])
        if key not in roots or (key, name) in entries:
            raise ModelAssetsError(f'Unknown root or duplicate manifest entry: {key}/{name}')
        if not isinstance(item['bytes'], int) or item['bytes'] < 0 or not re.fullmatch('[0-9a-f]{64}', item['sha256']):
            raise ModelAssetsError(f'Invalid size or SHA256: {key}/{name}')
        entries[key, name] = item
    for key, names in REQUIRED.items():
        for name in names:
            if (key, name) not in entries:
                raise ModelAssetsError(f'Manifest omits required loader input: {key}/{name}')
    selected = _selections(roots, entries)
    dino = roots['torch_home'] / DINO_PREFIX
    expected_dino = {name[len(DINO_PREFIX):] for key, name in entries
                     if key == 'torch_home' and name.startswith(DINO_PREFIX)}
    actual_dino = {p.relative_to(dino).as_posix(): p for p in dino.rglob('*') if p.is_file() or p.is_symlink()}
    bytecode = [name for name in actual_dino if name.endswith(('.pyc', '.pyo'))]
    # New importable source can shadow a hashed module. Unused docs and existing
    # pycache are compatible with the current cache and are not default failures.
    extra_importable = [name for name in actual_dino.keys() - expected_dino
                        if name.endswith(('.py', '.so', '.pyd'))
                        or (name.endswith(('.pyc', '.pyo')) and '__pycache__' not in PurePosixPath(name).parts)
                        or (actual_dino[name].is_symlink() and actual_dino[name].is_dir())]
    if extra_importable:
        raise ModelAssetsError(f'Unexpected DINO importable source: {sorted(extra_importable)[0]}')
    if clean_distribution:
        if actual_dino.keys() != expected_dino or any(p.is_symlink() for p in actual_dino.values()):
            raise ModelAssetsError('Clean DINO distribution requires exact regular-file set without bytecode/symlinks')
    files = []
    for (key, name), item in sorted(entries.items()):
        checked = _check_file(roots[key] / name, item, f'{key}/{name}')
        files.append({'root': key, 'path': name, **checked})
    normalization = []
    if repository_root is not None:
        repository_root = Path(repository_root)
        for item in manifest.get('repository_contract', {}).get('normalization_files', []):
            name = _relative(item['path'])
            normalization.append({'path': name, **_check_file(repository_root / name, item, f'repository/{name}')})
    return {
        'schema': 'steering_model_verification_v1', 'valid': True,
        'verifier_sha256': digest(Path(__file__)),
        'expected_manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
        'files_checked': len(files), 'bytes_hashed': sum(row['bytes'] for row in files),
        'files': files, 'selected': selected, 'normalization_files': normalization,
        'normalization_checked': repository_root is not None,
        'clean_distribution': clean_distribution, 'dino_bytecode_files_observed': len(bytecode),
        'limitations': [
            'Existing bytecode is tolerated and not attested; source hashes and loader selection do not prove which bytecode the interpreter read.',
            'Content identity does not establish upstream public availability or revision provenance.',
            'Assets must remain unchanged after verification; no model execution or inference equivalence is tested.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-config', required=True)
    parser.add_argument('--manifest', default=str(DEFAULT_MANIFEST),
                        help='Expected identity JSON; defaults to the checked-in manifest')
    parser.add_argument('--repository-root')
    parser.add_argument('--clean-distribution', action='store_true')
    parser.add_argument('--report', help='New JSON report file; never overwrites')
    args = parser.parse_args()
    text = Path(args.local_config).read_text()
    try:
        local = json.loads(text)
    except json.JSONDecodeError:
        import yaml
        local = yaml.safe_load(text)
    if args.repository_root:
        local = dict(local)
        for key in ROOT_KEYS:
            p = Path(local[key]).expanduser()
            if not p.is_absolute():
                local[key] = str(Path(args.repository_root) / p)
    try:
        result = verify_model_assets(local, args.manifest, repository_root=args.repository_root,
                                     clean_distribution=args.clean_distribution)
    except ModelAssetsError as exc:
        result = {'schema': 'steering_model_verification_v1', 'valid': False, 'error': str(exc)}
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.report:
        with Path(args.report).open('x') as out:
            out.write(encoded)
    print(json.dumps({key: value for key, value in result.items() if key != 'files'}), flush=True)
    return 0 if result['valid'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
