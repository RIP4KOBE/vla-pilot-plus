"""Compatibility installation must be exact, idempotent, and refuse unknown bytes."""
import difflib
import json
from pathlib import Path

import pytest

from scripts import steering_dependency_compat as compat


@pytest.fixture
def vendor(tmp_path, monkeypatch):
    root = tmp_path / 'env/robosuite'
    root.mkdir(parents=True)
    patches = tmp_path / 'patches'
    patches.mkdir()
    files = {}
    for index in range(2):
        name = f'file{index}.py'
        old = b'value = 1\r\n'
        new = b'value = 2\n'
        (root / name).write_bytes(old)
        patch = ''.join(difflib.unified_diff(old.decode().replace('\r\n', '\n').splitlines(True),
            new.decode().splitlines(True), fromfile='a/' + name, tofile='b/' + name)).encode()
        (patches / (name + '.patch')).write_bytes(patch)
        files[name] = {'upstream_sha256': compat.digest(old), 'patched_sha256': compat.digest(new),
                       'patch': name + '.patch', 'patch_sha256': compat.digest(patch)}
    manifest = patches / 'manifest.json'
    manifest.write_text(json.dumps({'version': '1.4.0', 'files': files}))
    monkeypatch.setattr(compat, 'MANIFEST', manifest)
    monkeypatch.setattr(compat, 'package_location', lambda: (root, '1.4.0'))
    monkeypatch.setattr(compat.sys, 'prefix', str(root.parent))
    return root, manifest


def test_installs_exact_bytes_and_second_install_is_read_only(vendor):
    root, _ = vendor
    first = compat.install_runtime_compat()
    assert first['valid'] and len(first['updated_files']) == 2
    stamps = [(p.stat().st_mtime_ns, p.read_bytes()) for p in sorted(root.glob('*.py'))]
    assert compat.install_runtime_compat()['updated_files'] == []
    assert stamps == [(p.stat().st_mtime_ns, p.read_bytes()) for p in sorted(root.glob('*.py'))]
    assert compat.verify_runtime_compat()['valid']


def test_unknown_second_input_never_partially_patches_first(vendor):
    root, _ = vendor
    (root / 'file1.py').write_text('user_change = True\n')
    before = (root / 'file0.py').read_bytes()
    with pytest.raises(ValueError, match='Unknown Robosuite file'):
        compat.install_runtime_compat()
    assert (root / 'file0.py').read_bytes() == before


def test_verification_rejects_unpatched_and_tampered_files(vendor):
    root, _ = vendor
    with pytest.raises(ValueError, match='compatibility is missing or changed'):
        compat.verify_runtime_compat()
    compat.install_runtime_compat()
    (root / 'file1.py').write_text('value = 3\n')
    with pytest.raises(ValueError, match='compatibility is missing or changed'):
        compat.verify_runtime_compat()


def test_other_distribution_version_is_not_patched(vendor, monkeypatch):
    root, _ = vendor
    monkeypatch.setattr(compat, 'package_location', lambda: (root, '1.5.0'))
    with pytest.raises(ValueError, match='Expected robosuite 1.4.0'):
        compat.install_runtime_compat()


def test_install_cannot_modify_another_environment(vendor, monkeypatch):
    root, _ = vendor
    monkeypatch.setattr(compat.sys, 'prefix', str(root / 'other-env'))
    with pytest.raises(ValueError, match='outside the active Python environment'):
        compat.install_runtime_compat()


def test_modified_patch_is_rejected(vendor):
    root, manifest = vendor
    (manifest.parent / 'file0.py.patch').write_text('changed patch\n')
    with pytest.raises(ValueError, match='patch/file identity differs'):
        compat.install_runtime_compat()
    assert (root / 'file0.py').read_bytes() == b'value = 1\r\n'


def test_wrong_output_hash_is_rejected_before_install(vendor):
    root, manifest = vendor
    data = json.loads(manifest.read_text())
    data['files']['file1.py']['patched_sha256'] = '0' * 64
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='Unexpected compatibility output'):
        compat.install_runtime_compat()
    assert all(p.read_bytes() == b'value = 1\r\n' for p in root.glob('*.py'))


def test_source_freeze_includes_dependency_patches(tmp_path, monkeypatch):
    from scripts import steering_runtime
    monkeypatch.setattr(steering_runtime, 'ROOT', tmp_path)
    (tmp_path / 'main.py').write_text('')
    (tmp_path / 'scripts').mkdir()
    patch = tmp_path / 'scripts/compat.patch'
    patch.write_text('first')
    manifest = steering_runtime.source_manifest()
    assert 'scripts/compat.patch' in manifest
    patch.write_text('changed')
    assert not steering_runtime.source_unchanged(manifest)


def test_audit_requires_compatibility_receipt_for_new_runtime_only(tmp_path):
    from scripts.audit_steering import runtime_compatibility_checks
    assert runtime_compatibility_checks(tmp_path, {}, {}) == {}
    path = tmp_path / 'source/scripts/steering_runtime.py'
    path.parent.mkdir(parents=True)
    path.write_text('from scripts.steering_dependency_compat import verify_runtime_compat\n')
    assert runtime_compatibility_checks(tmp_path, {}, {}) == {'runtime_dependency_compatibility': False}


def test_audit_binds_compatibility_receipt_and_patch_bytes(vendor, tmp_path):
    from scripts.audit_steering import runtime_compatibility_checks
    root, manifest = vendor
    receipt = compat.install_runtime_compat()
    specification = json.loads(manifest.read_text())
    specification['distribution'] = 'robosuite'
    folder = tmp_path / 'run'
    bundle = folder / 'source/scripts/dependency_patches'
    bundle.mkdir(parents=True)
    recipe = bundle / 'robosuite-1.4.0.json'
    recipe.write_text(json.dumps(specification))
    source = {'scripts/dependency_patches/robosuite-1.4.0.json': compat.digest(recipe.read_bytes())}
    receipt['manifest_sha256'] = compat.digest(recipe.read_bytes())
    for row in specification['files'].values():
        patch = bundle / row['patch']
        patch.write_bytes((manifest.parent / row['patch']).read_bytes())
        source['scripts/dependency_patches/' + row['patch']] = compat.digest(patch.read_bytes())
    environment = {'runtime_compatibility': receipt}
    assert runtime_compatibility_checks(folder, {'source_sha256': source}, environment)['runtime_dependency_compatibility']
    (bundle / 'file0.py.patch').write_text('tampered')
    assert not runtime_compatibility_checks(folder, {'source_sha256': source}, environment)['runtime_dependency_compatibility']
