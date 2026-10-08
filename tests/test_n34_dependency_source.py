"""Exact local Git objects and inert module origins; no dependency imports/runs."""
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from scripts import qd_ed_n34_source as source, qd_ed_n34_bridge as bridge
from scripts import qd_ed_n23_worker as w
from test_n32_submodule_freeze import repo, git, commit


LEROBOT_FILES = {
    'src/lerobot/__init__.py': 'PIN = 1\n',
    'src/lerobot/processor/env_processor.py': 'VALUE = 1\n',
    'configs/policy.yaml': 'value: 1\n',
    'configs/policy.yml': 'value: 1\n',
    'configs/policy.json': '{"value": 1}\n',
}
LIBERO_FILES = {
    'libero/libero/__init__.py': 'PIN = 1\n',
    'libero/libero/envs/env_wrapper.py': 'VALUE = 1\n',
    'libero/configs/config.yaml': 'value: 1\n',
}


def write_files(root, files):
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data)


@pytest.fixture
def dependencies(repo, tmp_path):
    root, *_ = repo
    objects = tmp_path / 'lerobot-objects'
    objects.mkdir()
    git(objects, 'init', '-q')
    write_files(objects, {**LEROBOT_FILES, 'weights.bin': 'not source\n'})
    pin = commit(objects)
    write_files(objects, {'src/lerobot/__init__.py': 'PIN = 2\n',
                          'src/lerobot/unpinned.py': 'UNPINNED = True\n'})
    other = commit(objects)
    database = root / '.git/modules' / source.LEROBOT
    git(root, 'init', '-q', '--bare', str(database))
    git(objects, 'push', '-q', str(database), 'HEAD:refs/heads/main')
    git(root, '--git-dir=' + str(database), 'symbolic-ref', 'HEAD', 'refs/heads/main')
    git(root, 'update-index', '--add', '--cacheinfo', '160000,' + pin + ',' + source.LEROBOT)
    write_files(root / source.LIBERO, LIBERO_FILES)
    write_files(root, {'configs/qd_ed_final/candidate_n34.json': '{}\n'})
    write_files(root / source.LEROBOT, LEROBOT_FILES)
    commit(root)
    return root, database, pin, other


def test_complete_dependency_inventory_uses_pins_not_heads_or_globs(dependencies):
    root, database, pin, other = dependencies
    assert git(root, '--git-dir=' + str(database), 'rev-parse', 'HEAD') == other != pin
    expected = ({source.LEROBOT + '/' + p for p in LEROBOT_FILES}
                | {source.LIBERO + '/' + p for p in LIBERO_FILES}
                | {source.RDT + '/scripts/maniskill_model.py'})
    assert source.dependency_paths(root) == expected
    record = source.source_record(root, expected)
    source.verify_source(root, record)
    (root / source.LEROBOT / 'src/lerobot/__init__.py').unlink()
    assert source.dependency_paths(root) == expected  # absent bytes cannot shrink the inventory
    with pytest.raises(ValueError, match='missing or linked'):
        source.source_record(root, expected)


@pytest.mark.parametrize('dependency,relative', [
    (source.LEROBOT, 'src/lerobot/processor/env_processor.py'),
    (source.LIBERO, 'libero/libero/envs/env_wrapper.py'),
])
@pytest.mark.parametrize('fault', ['bytes', 'missing', 'symlink', 'parent_symlink', 'unpinned'])
def test_dependency_source_fail_closed(dependencies, dependency, relative, fault):
    root, *_ = dependencies
    paths = source.dependency_paths(root)
    path = root / dependency / relative
    if fault == 'bytes':
        path.write_text('WRONG = True\n')
    elif fault == 'missing':
        path.unlink()
    elif fault == 'symlink':
        path.unlink()
        path.symlink_to(root / 'file.py')
    elif fault == 'parent_symlink':
        target = path.parent.with_name('moved')
        path.parent.rename(target)
        path.parent.symlink_to(target, target_is_directory=True)
    elif fault == 'unpinned':
        path = root / dependency / 'unpinned.py'
        path.write_text('UNPINNED = True\n')
        assert str(path.relative_to(root)) not in source.dependency_paths(root)
        paths.add(str(path.relative_to(root)))
    with pytest.raises(ValueError):
        source.source_record(root, paths)


@pytest.mark.parametrize('fault', ['database', 'object', 'wrong_head_bytes', 'gitlink', 'tree_pin'])
def test_lerobot_object_trust_failures(dependencies, fault):
    root, database, pin, other = dependencies
    paths = source.dependency_paths(root)
    if fault in ('database', 'object'):
        database.rename(database.with_name('absent'))
        if fault == 'object':
            git(root, 'init', '-q', '--bare', str(database))
    elif fault == 'wrong_head_bytes':
        (root / source.LEROBOT / 'src/lerobot/__init__.py').write_text('PIN = 2\n')
    else:
        new_pin = (other if fault == 'gitlink' else
                   git(root, '--git-dir=' + str(database), 'rev-parse', pin + '^{tree}'))
        git(root, 'update-index', '--cacheinfo', '160000,' + new_pin + ',' + source.LEROBOT)
        commit(root)
    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        source.source_record(root, paths)


@pytest.mark.parametrize('dependency,relative,module', [
    (source.LEROBOT, 'src/lerobot/processor/env_processor.py', 'lerobot.processor.env_processor'),
    (source.LIBERO, 'libero/libero/envs/env_wrapper.py', 'libero.libero.envs.env_wrapper'),
])
def test_loaded_checkout_modules_require_frozen_inventory(dependencies, monkeypatch, dependency, relative, module):
    root, *_ = dependencies
    name = dependency + '/' + relative
    record = source.source_record(root, source.dependency_paths(root))
    monkeypatch.setattr(source, 'sys', SimpleNamespace(modules={
        module: SimpleNamespace(__file__=str(root / name))}))
    assert source.attest_loaded(root, record)[module]['path'] == name
    record['files'] = [row for row in record['files'] if row['path'] != name]
    record['sha256'] = w.canonical_sha(record['files'])
    source.verify_source(root, record)  # a self-consistent subset still cannot attest this import
    with pytest.raises(ValueError, match='loaded source not frozen'):
        source.attest_loaded(root, record)


@pytest.mark.parametrize('dependency', [source.LEROBOT, source.LIBERO])
def test_bridge_rejects_rehashed_missing_dependency_inventory(dependencies, monkeypatch, dependency):
    root, *_ = dependencies
    monkeypatch.setattr(bridge.helpers, 'source_paths', lambda _: {'file.py'})
    monkeypatch.setattr(bridge, 'scientific_paths', lambda _: {'file.py'})
    monkeypatch.setattr(bridge, 'SCIENTIFIC_COMMIT', git(root, 'rev-parse', 'HEAD'))
    paths = bridge.source_paths(root)
    assert source.dependency_paths(root) <= paths
    record = source.source_record(root, paths)
    plan = {'worktree': str(root), 'source': record,
            'scientific_source': source.source_record(root, {'file.py'})}
    bridge.verify_sources(plan)
    record['files'] = [row for row in record['files'] if not row['path'].startswith(dependency + '/')]
    record['sha256'] = w.canonical_sha(record['files'])
    with pytest.raises(ValueError, match='operational source closure incomplete'):
        bridge.verify_sources(plan)


def test_linked_worktree_uses_registered_objects_and_local_bytes(dependencies):
    root, _, _, _ = dependencies
    linked = root.parent / 'linked-dependencies'
    git(root, 'worktree', 'add', '-q', '--detach', str(linked), 'HEAD')
    paths = source.dependency_paths(linked)
    for name in paths:
        path = linked / name
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((root / name).read_bytes())
    assert source.source_record(linked, paths) == source.source_record(root, paths)
    (linked / source.LEROBOT / 'src/lerobot/__init__.py').write_text('PIN = 2\n')
    with pytest.raises(ValueError, match='uncommitted source bytes'):
        source.source_record(linked, paths)


@pytest.mark.parametrize('relative', ['../file.py', '/file.py', 'third_party/lerobot/../file.py', './file.py'])
def test_unsafe_source_paths_still_rejected(dependencies, relative):
    root, *_ = dependencies
    with pytest.raises(ValueError, match='unsafe source path'):
        source.source_record(root, {relative})


def test_unapproved_submodule_rejected(dependencies):
    root, *_ = dependencies
    with pytest.raises(ValueError, match='unapproved'):
        source.submodule_paths(root, 'third_party/unknown')
