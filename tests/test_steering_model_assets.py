"""Synthetic CPU identity tests: no real cache/model imports or weight loading."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

MODULE = Path(__file__).resolve().parents[1] / 'scripts/steering_model_assets.py'
spec = importlib.util.spec_from_file_location('steering_model_assets', MODULE)
assets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assets)


@pytest.fixture
def asset_pack(tmp_path):
    local = {key: str(tmp_path / key) for key in assets.ROOT_KEYS}
    files = []
    for key, names in assets.REQUIRED.items():
        for name in names:
            path = Path(local[key]) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(('accepted:' + key + '/' + name).encode())
            files.append({'root': key, 'path': name, 'bytes': path.stat().st_size,
                          'sha256': assets.digest(path)})
    for name in ('dinov2/__init__.py', 'dinov2/hub/backbones.py', 'LICENSE'):
        relative = assets.DINO_PREFIX + name
        path = Path(local['torch_home']) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(('source:' + name).encode())
        files.append({'root': 'torch_home', 'path': relative, 'bytes': path.stat().st_size,
                      'sha256': assets.digest(path)})
    repo = tmp_path / 'repo'
    source = repo / 'third_party/rdt/scripts/maniskill_model.py'
    source.parent.mkdir(parents=True)
    source.write_text('DATA_STAT = {}\n')
    manifest = {'schema': 'steering_model_identity_v1', 'files': files,
                'repository_contract': {'normalization_files': [
                    {'path': source.relative_to(repo).as_posix(), 'bytes': source.stat().st_size,
                     'sha256': assets.digest(source)}]}}
    manifest_path = tmp_path / 'expected.json'
    manifest_path.write_text(json.dumps(manifest))
    return local, manifest_path, repo


def verify(pack, **kwargs):
    local, manifest, repo = pack
    return assets.verify_model_assets(local, manifest, repository_root=repo, **kwargs)


def write_extra(pack, key, relative, data=b'shadow'):
    path = Path(pack[0][key]) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_valid_pack_reports_every_hashed_file_and_source(asset_pack):
    result = verify(asset_pack)
    assert result['valid']
    assert result['files_checked'] == 15
    assert result['normalization_checked']
    assert len(result['normalization_files']) == 1
    assert result['expected_manifest_sha256'] == assets.digest(asset_pack[1])
    assert result['selected']['rdt_config'].endswith('rdt_checkpoint/config.json')
    assert result['selected']['text_encoder_weight'].endswith('text_encoder/pytorch_model.bin')


@pytest.mark.parametrize('key,name', [
    ('rdt_checkpoint', 'ema/model.safetensors'),
    ('text_encoder', 'pytorch_model.bin'),
    ('vision_encoder', 'model.safetensors'),
    ('torch_home', assets.DINO_PREFIX + 'dinov2/hub/backbones.py'),
])
def test_same_size_corruption_fails_hash(asset_pack, key, name):
    path = Path(asset_pack[0][key]) / name
    data = path.read_bytes()
    path.write_bytes(bytes([data[0] ^ 1]) + data[1:])
    with pytest.raises(assets.ModelAssetsError, match='SHA256 mismatch'):
        verify(asset_pack)


@pytest.mark.parametrize('relative', ['ema/config.yaml', 'ema/config.json', 'config.yaml'])
def test_rdt_config_shadow_is_rejected(asset_pack, relative):
    write_extra(asset_pack, 'rdt_checkpoint', relative)
    with pytest.raises(assets.ModelAssetsError, match='Loader selection differs for RDT config'):
        verify(asset_pack)


def test_directory_at_rdt_config_priority_is_not_silently_skipped(asset_pack):
    (Path(asset_pack[0]['rdt_checkpoint']) / 'ema/config.yaml').mkdir()
    with pytest.raises(assets.ModelAssetsError, match='Loader selection differs for RDT config'):
        verify(asset_pack)


@pytest.mark.parametrize('relative', ['model.safetensors', 'model.safetensors.index.json'])
def test_t5_safetensors_shadow_is_rejected(asset_pack, relative):
    write_extra(asset_pack, 'text_encoder', relative)
    with pytest.raises(assets.ModelAssetsError, match='Loader selection differs for text_encoder'):
        verify(asset_pack)


@pytest.mark.parametrize('key,name', [
    ('text_encoder', 'special_tokens_map.json'),
    ('text_encoder', 'spiece.model'),
    ('torch_home', assets.DINO_PREFIX + 'hubconf.py'),
    ('torch_home', assets.DINO_PREFIX + 'dinov2/hub/backbones.py'),
    ('torch_home', 'hub/checkpoints/dinov2_vitb14_pretrain.pth'),
])
def test_missing_required_tokenizer_or_dino_input_fails(asset_pack, key, name):
    (Path(asset_pack[0][key]) / name).unlink()
    with pytest.raises(assets.ModelAssetsError, match='Missing required file'):
        verify(asset_pack)


@pytest.mark.parametrize('relative', ['tokenizer.json', 'added_tokens.json', 'adapter_config.json'])
def test_extra_hf_loader_inputs_fail(asset_pack, relative):
    write_extra(asset_pack, 'text_encoder', relative)
    with pytest.raises(assets.ModelAssetsError, match='Unexpected .*input'):
        verify(asset_pack)


def test_hf_snapshot_symlink_to_blob_outside_root_passes(asset_pack, tmp_path):
    snapshot = Path(asset_pack[0]['text_encoder'])
    original = snapshot / 'pytorch_model.bin'
    blob = tmp_path / 'blobs' / 'sha256'
    blob.parent.mkdir()
    original.rename(blob)
    original.symlink_to(blob)
    assert verify(asset_pack)['valid']
    blob.unlink()
    with pytest.raises(assets.ModelAssetsError):
        verify(asset_pack)


def test_shadow_symlink_is_rejected_even_if_target_is_accepted_bin(asset_pack):
    root = Path(asset_pack[0]['text_encoder'])
    (root / 'model.safetensors').symlink_to(root / 'pytorch_model.bin')
    with pytest.raises(assets.ModelAssetsError, match='Loader selection differs'):
        verify(asset_pack)


def test_current_bytecode_docs_and_unused_weights_are_compatible(asset_pack):
    write_extra(asset_pack, 'torch_home', assets.DINO_PREFIX + '__pycache__/hubconf.cpython-312.pyc')
    write_extra(asset_pack, 'torch_home', assets.DINO_PREFIX + 'LOCAL_NOTES.md')
    for name in ('pytorch_model.bin', 'ema/pytorch_model.bin', 'rdt/ema/model.safetensors',
                 'rdt/ema/config.yaml', 'scheduler.bin', 'README.md'):
        write_extra(asset_pack, 'rdt_checkpoint', name)
    write_extra(asset_pack, 'vision_encoder', 'pytorch_model.bin')
    result = verify(asset_pack)
    assert result['valid'] and result['dino_bytecode_files_observed'] == 1
    assert 'not attested' in result['limitations'][0]
    with pytest.raises(assets.ModelAssetsError, match='Clean DINO distribution'):
        verify(asset_pack, clean_distribution=True)


def test_clean_distribution_is_optional_and_passes_clean_pack(asset_pack):
    assert verify(asset_pack, clean_distribution=True)['valid']


@pytest.mark.parametrize('relative', ['dinov2/hub/backbones/__init__.py', 'dinov2/evil.so',
                                     'dinov2/hub/backbones/__init__.pyc'])
def test_extra_importable_source_cannot_shadow_hashed_dino(asset_pack, relative):
    write_extra(asset_pack, 'torch_home', assets.DINO_PREFIX + relative)
    with pytest.raises(assets.ModelAssetsError, match='Unexpected DINO importable source'):
        verify(asset_pack)


def test_extra_dino_directory_symlink_cannot_shadow_module(asset_pack, tmp_path):
    external = tmp_path / 'external_package'
    external.mkdir()
    (external / '__init__.py').write_text('shadow = True\n')
    link = Path(asset_pack[0]['torch_home']) / assets.DINO_PREFIX / 'dinov2/hub/backbones'
    link.symlink_to(external, target_is_directory=True)
    with pytest.raises(assets.ModelAssetsError, match='Unexpected DINO importable source'):
        verify(asset_pack)


def test_normalization_source_change_fails(asset_pack):
    source = asset_pack[2] / 'third_party/rdt/scripts/maniskill_model.py'
    source.write_bytes(b'd' + source.read_bytes()[1:])
    with pytest.raises(assets.ModelAssetsError, match='SHA256 mismatch: repository/'):
        verify(asset_pack)


@pytest.mark.parametrize('bad_path', ['../outside', '/absolute', 'a/../b'])
def test_manifest_cannot_escape_logical_root(asset_pack, bad_path):
    path = asset_pack[1]
    data = json.loads(path.read_text())
    data['files'][0]['path'] = bad_path
    path.write_text(json.dumps(data))
    with pytest.raises(assets.ModelAssetsError, match='Invalid manifest relative path'):
        verify(asset_pack)


def test_duplicate_or_omitted_required_entry_is_not_a_valid_manifest(asset_pack):
    path = asset_pack[1]
    data = json.loads(path.read_text())
    original = data['files'][:]
    data['files'].append(data['files'][0])
    path.write_text(json.dumps(data))
    with pytest.raises(assets.ModelAssetsError, match='duplicate manifest entry'):
        verify(asset_pack)
    data['files'] = original[1:]
    path.write_text(json.dumps(data))
    with pytest.raises(assets.ModelAssetsError, match='Manifest omits required'):
        verify(asset_pack)


def test_cache_root_is_not_an_explicit_snapshot(asset_pack):
    (Path(asset_pack[0]['text_encoder']) / 'snapshots').mkdir()
    with pytest.raises(assets.ModelAssetsError, match='explicit snapshot'):
        verify(asset_pack)


def test_verifier_does_not_import_model_runtime():
    # Use a fresh interpreter so this remains meaningful when the repository's
    # other tests have already imported Torch in the pytest process.
    code = ('import runpy,sys; '
            f'runpy.run_path({str(MODULE)!r}, run_name="asset_probe"); '
            'assert not ({"torch","transformers","dinov2","core.rdt_policy_steer"} & sys.modules.keys())')
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_default_manifest_is_used_when_not_overridden(asset_pack, monkeypatch):
    local, expected, repo = asset_pack
    monkeypatch.setattr(assets, 'DEFAULT_MANIFEST', expected)
    result = assets.verify_model_assets(local, repository_root=repo)
    assert result['valid']
    assert result['expected_manifest_sha256'] == assets.digest(expected)
