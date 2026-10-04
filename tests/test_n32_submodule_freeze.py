"""Local Git fixtures only; no model, simulator, provider or device execution."""
import copy
from pathlib import Path
import subprocess

import pytest

from scripts import qd_ed_n23_worker as w

RDT = 'third_party/rdt/scripts/maniskill_model.py'


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args]).decode().strip()


def commit(root):
    git(root, 'add', '.')
    git(root, '-c', 'user.name=CPU Test', '-c', 'user.email=cpu@example.invalid',
        'commit', '-qm', 'fixture')
    return git(root, 'rev-parse', 'HEAD')


@pytest.fixture
def repo(tmp_path, monkeypatch):
    root = tmp_path / 'super'; root.mkdir()
    git(root, 'init', '-q')
    (root / 'file.py').write_text('VALUE = 1\n')
    database = root / '.git/modules/third_party/rdt'
    database.parent.mkdir(parents=True)
    git(root, 'init', '-q', '--bare', str(database))
    source = tmp_path / 'objects'; source.mkdir()
    git(source, 'init', '-q')
    (source / 'scripts').mkdir()
    (source / 'scripts/maniskill_model.py').write_text('PIN = 1\n')
    pin = commit(source)
    (source / 'scripts/maniskill_model.py').write_text('PIN = 2\n')
    other = commit(source)
    # Local push populates fixture objects; production never fetches or pushes.
    git(source, 'push', '-q', str(database), 'HEAD:refs/heads/main')
    git(root, '--git-dir=' + str(database), 'symbolic-ref', 'HEAD', 'refs/heads/main')
    git(root, 'update-index', '--add', '--cacheinfo', '160000,' + pin + ',third_party/rdt')
    git(root, 'add', 'file.py')
    git(root, '-c', 'user.name=CPU Test', '-c', 'user.email=cpu@example.invalid',
        'commit', '-qm', 'super fixture')
    path = root / RDT; path.parent.mkdir(parents=True)
    path.write_text('PIN = 1\n')
    monkeypatch.setattr(w, 'REQUIRED_SOURCE', {'file.py', RDT})
    return root, path, database, pin, other


def test_pinned_roundtrip_ignores_unrelated_database_head(repo):
    root, path, database, pin, other = repo
    assert git(root, '--git-dir=' + str(database), 'rev-parse', 'HEAD') == other != pin
    record = w.source_record(root, w.REQUIRED_SOURCE)
    assert set(record) == {'commit', 'files', 'sha256'}
    assert all(set(row) == {'path', 'sha256'} for row in record['files'])
    assert w.verify_source(root, record) == record['sha256']
    assert next(row['sha256'] for row in record['files'] if row['path'] == RDT) == w.sha(path)


@pytest.mark.parametrize('fault', ['missing', 'modified', 'wrong_pin', 'symlink', 'parent_symlink',
                                   'missing_database', 'missing_object', 'unknown', 'regular_modified'])
def test_source_failures(repo, fault):
    root, path, database, pin, other = repo
    record = w.source_record(root, w.REQUIRED_SOURCE)
    if fault == 'missing': path.unlink()
    elif fault == 'modified': path.write_text('tampered\n')
    elif fault == 'wrong_pin': path.write_text('PIN = 2\n')  # valid local HEAD, wrong pinned bytes
    elif fault == 'symlink':
        target = root / 'copy.py'; target.write_bytes(path.read_bytes())
        path.unlink(); path.symlink_to(target)
    elif fault == 'parent_symlink':
        target = path.parent.with_name('copy'); path.parent.rename(target)
        path.parent.symlink_to(target, target_is_directory=True)
    elif fault == 'missing_database': database.rename(database.with_name('absent'))
    elif fault == 'missing_object':
        database.rename(database.with_name('absent'))
        git(root, 'init', '-q', '--bare', str(database))
    elif fault == 'unknown':
        extra = root / 'third_party/rdt/scripts/unknown.py'; extra.write_text('unknown\n')
        record['files'].append({'path': str(extra.relative_to(root)), 'sha256': w.sha(extra)})
        record['sha256'] = w.canonical_sha(record['files'])
    elif fault == 'regular_modified': (root / 'file.py').write_text('VALUE = 2\n')
    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        w.verify_source(root, record)


@pytest.mark.parametrize('fault', ['hash', 'aggregate', 'commit', 'omit', 'extra_field'])
def test_record_tampering(repo, fault):
    root, *_ = repo
    record = copy.deepcopy(w.source_record(root, w.REQUIRED_SOURCE))
    if fault == 'hash':
        record['files'][0]['sha256'] = '0' * 64
        record['sha256'] = w.canonical_sha(record['files'])
    elif fault == 'aggregate': record['sha256'] = '0' * 64
    elif fault == 'commit': record['commit'] = '0' * 40
    elif fault == 'omit': record['files'] = [x for x in record['files'] if x['path'] != RDT]
    else: record['submodule_head'] = 'arbitrary'
    with pytest.raises(ValueError): w.verify_source(root, record)


def test_wrong_root_does_not_inherit_parent_git(repo):
    root, *_ = repo
    record = w.source_record(root, w.REQUIRED_SOURCE)
    child = root / 'wrong-root'; child.mkdir()
    for row in record['files']:
        path = child / row['path']; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((root / row['path']).read_bytes())
    with pytest.raises(ValueError, match='repository root differs'):
        w.verify_source(child, record)


def test_changed_superproject_gitlink_rejects_old_record(repo):
    root, path, database, pin, other = repo
    record = w.source_record(root, w.REQUIRED_SOURCE)
    git(root, 'update-index', '--cacheinfo', '160000,' + other + ',third_party/rdt')
    git(root, '-c', 'user.name=CPU Test', '-c', 'user.email=cpu@example.invalid',
        'commit', '-qm', 'different gitlink')
    with pytest.raises(ValueError, match='uncommitted'): w.verify_source(root, record)
    path.write_text('PIN = 2\n')
    with pytest.raises(ValueError, match='source bytes differ'): w.verify_source(root, record)


def test_regular_files_keep_original_schema(repo, monkeypatch):
    root, *_ = repo
    monkeypatch.setattr(w, 'REQUIRED_SOURCE', {'file.py'})
    files = [{'path': 'file.py', 'sha256': w.sha(root / 'file.py')}]
    record = {'commit': git(root, 'rev-parse', 'HEAD'), 'files': files, 'sha256': w.canonical_sha(files)}
    assert w.source_record(root, ['file.py']) == record
    assert w.verify_source(root, record) == record['sha256']


def test_linked_worktree_uses_common_pinned_objects(repo):
    root, path, database, pin, other = repo
    linked = root.parent / 'linked'
    git(root, 'worktree', 'add', '-q', '--detach', str(linked), 'HEAD')
    local = linked / RDT; local.parent.mkdir(parents=True, exist_ok=True)
    local.write_bytes(path.read_bytes())
    record = w.source_record(linked, w.REQUIRED_SOURCE)
    assert record == w.source_record(root, w.REQUIRED_SOURCE)
    assert w.verify_source(linked, record) == record['sha256']
    local.write_text('PIN = 2\n')
    # Correct bytes in another worktree cannot rescue wrong local bytes.
    with pytest.raises(ValueError, match='uncommitted'): w.verify_source(linked, record)


def test_committed_symlink_cannot_be_materialized_as_regular(repo, monkeypatch):
    root, *_ = repo
    link = root / 'link.py'; link.symlink_to('file.py')
    commit(root)
    link.unlink(); link.write_text('file.py')
    monkeypatch.setattr(w, 'REQUIRED_SOURCE', {'link.py'})
    with pytest.raises(ValueError, match='not regular'): w.source_record(root, {'link.py'})


def test_pin_must_be_commit_not_tree(repo):
    root, path, database, pin, other = repo
    tree = git(root, '--git-dir=' + str(database), 'rev-parse', pin + '^{tree}')
    git(root, 'update-index', '--cacheinfo', '160000,' + tree + ',third_party/rdt')
    git(root, '-c', 'user.name=CPU Test', '-c', 'user.email=cpu@example.invalid',
        'commit', '-qm', 'invalid gitlink object type')
    with pytest.raises(ValueError, match='pin not a commit'):
        w.source_record(root, w.REQUIRED_SOURCE)
