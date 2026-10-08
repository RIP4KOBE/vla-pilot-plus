"""Patch closure regressions using local Git and inert module origins only."""
from types import SimpleNamespace

import pytest

from scripts import qd_ed_n34_bridge as bridge, qd_ed_n34_source as source
from scripts import qd_ed_n23_worker as w
from test_n32_submodule_freeze import git, commit


PATCHES = {'patches/__init__.py', 'patches/light.py', 'patches/nested/helper.py'}


@pytest.fixture
def patch_repo(tmp_path, monkeypatch):
    root = tmp_path / 'checkout'
    root.mkdir()
    git(root, 'init', '-q')
    for name in PATCHES | {'file.py', 'configs/qd_ed_final/candidate_n34.json',
                           'patches/README.md'}:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{}\n' if name.endswith('.json') else '# inert fixture\n')
    head = commit(root)
    monkeypatch.setattr(bridge.helpers, 'source_paths', lambda _: {'file.py'})
    monkeypatch.setattr(source, 'dependency_paths', lambda _: set())
    monkeypatch.setattr(bridge, 'scientific_paths', lambda _: {'file.py'})
    monkeypatch.setattr(bridge, 'SCIENTIFIC_COMMIT', head)
    monkeypatch.setattr(source, 'sys', SimpleNamespace(modules={
        'patches': SimpleNamespace(__file__=str(root / 'patches/__init__.py')),
        'patches.light': SimpleNamespace(__file__=str(root / 'patches/light.py')),
    }))
    return root


def test_patch_closure_roundtrip_and_loaded_origins(patch_repo):
    root = patch_repo
    paths = bridge.source_paths(root)
    assert paths == PATCHES | {'file.py', 'configs/qd_ed_final/candidate_n34.json'}
    record = source.source_record(root, paths)
    source.verify_source(root, record)
    assert bridge.attest_loaded(root, record) == {
        name: {'path': relative, 'sha256': w.sha(root / relative)}
        for name, relative in [('patches', 'patches/__init__.py'),
                               ('patches.light', 'patches/light.py')]
    }


@pytest.mark.parametrize('relative', sorted(PATCHES))
@pytest.mark.parametrize('fault', ['missing', 'modified', 'staged', 'symlink'])
def test_patch_bytes_fail_closed(patch_repo, relative, fault):
    root = patch_repo
    record = source.source_record(root, bridge.source_paths(root))
    path = root / relative
    if fault == 'missing':
        path.unlink()
    elif fault == 'symlink':
        path.unlink()
        path.symlink_to(root / 'file.py')
    else:
        path.write_text('# changed fixture\n')
        if fault == 'staged':
            git(root, 'add', relative)
    assert PATCHES <= bridge.source_paths(root)
    for check in (lambda: source.source_record(root, bridge.source_paths(root)),
                  lambda: source.verify_source(root, record)):
        with pytest.raises(ValueError, match='missing or linked|uncommitted source bytes'):
            check()


@pytest.mark.parametrize('staged', [False, True])
def test_new_uncommitted_patch_rejected(patch_repo, staged):
    root = patch_repo
    relative = 'patches/nested/uncommitted.py'
    (root / relative).write_text('# new fixture\n')
    if staged:
        git(root, 'add', relative)
    paths = bridge.source_paths(root)
    assert relative in paths
    with pytest.raises(ValueError):
        source.source_record(root, paths)


@pytest.mark.parametrize('relative', ['patches/__init__.py', 'patches/light.py'])
def test_rehashed_patch_omission_rejected(patch_repo, relative):
    root = patch_repo
    record = source.source_record(root, bridge.source_paths(root))
    plan = {'worktree': str(root), 'source': record,
            'scientific_source': source.source_record(root, {'file.py'})}
    bridge.verify_sources(plan)
    record['files'] = [row for row in record['files'] if row['path'] != relative]
    record['sha256'] = w.canonical_sha(record['files'])
    source.verify_source(root, record)
    with pytest.raises(ValueError, match='operational source closure incomplete'):
        bridge.verify_sources(plan)
    with pytest.raises(ValueError, match='loaded source not frozen'):
        bridge.attest_loaded(root, record)


@pytest.mark.parametrize('relative', ['patches/__init__.py', 'patches/light.py'])
def test_loaded_patch_modified_after_record_rejected(patch_repo, relative):
    root = patch_repo
    record = source.source_record(root, bridge.source_paths(root))
    (root / relative).write_text('# changed after freeze\n')
    with pytest.raises(ValueError, match='loaded source not frozen'):
        bridge.attest_loaded(root, record)
