"""Bounded CPU repair tests. Synthetic authority never authorizes production."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import qd_ed_n23_worker as w, qd_ed_n34_source as source
from scripts import qd_ed_n34_bridge as b, qd_ed_n34_worker as worker
from scripts import qd_ed_n34_release as release
from test_n32_submodule_freeze import repo, git, commit
from test_n34_dependency_source import dependencies
from test_n34_release_boundary import fixture, write, consume, BoundaryReached


def legacy_record(root, paths):
    """Previous per-file object algorithm, only on small temporary repositories."""
    revision = git(root, 'rev-parse', 'HEAD')
    files = []
    for relative in sorted(set(paths)):
        submodule = next((s for s in source.PINNED_SUBMODULES if relative.startswith(s + '/')), None)
        if submodule:
            pin, database = source.submodule_pin(root, submodule, revision)
            mode, kind, blob = w._source_entry(root, pin, relative[len(submodule)+1:], database)
            assert mode in ('100644', '100755') and kind == 'blob'
            data = w._source_git(root, 'cat-file', 'blob', blob, database=database)
        else:
            data = w._committed_source(root, revision, relative)
        assert data == (root / relative).read_bytes()
        files.append({'path': relative, 'sha256': hashlib.sha256(data).hexdigest()})
    return {'commit': revision, 'files': files, 'sha256': w.canonical_sha(files)}


def test_equivalent_records_constant_git_calls(dependencies, monkeypatch):
    root, *_ = dependencies
    for i in range(40):
        (root / f'file{i}.py').write_bytes(b'\0binary\n' + str(i).encode())
    (root / 'file39.py').chmod(0o755)
    commit(root)
    small = {'file.py'} | source.dependency_paths(root)
    large = small | {f'file{i}.py' for i in range(40)}
    old = legacy_record(root, large)
    original = source.subprocess.check_output
    calls = []
    def counted(command, **kwargs):
        assert '--no-replace-objects' in command
        assert kwargs['env']['GIT_NO_LAZY_FETCH'] == '1'
        calls.append(command)
        return original(command, **kwargs)
    monkeypatch.setattr(source.subprocess, 'check_output', counted)
    source.source_record(root, small)
    small_count = len(calls)
    calls.clear()
    assert source.source_record(root, large) == old
    assert len(calls) == small_count == 14  # 2 root + 3*2 tree/batch + 2*3 pin
    assert sum(cmd[-2:] == ['cat-file', '--batch'] for cmd in calls) == 3
    print(f'Equivalent canonical records; {len(small)} and {len(large)} files: {small_count} git calls each, 3 blob batches.')


@pytest.mark.parametrize('relative', ['file.py', source.LEROBOT + '/src/lerobot/__init__.py'])
def test_next_source_transaction_rechecks_bytes(dependencies, relative):
    root, *_ = dependencies
    record = source.source_record(root, [relative])
    source.verify_source(root, record)
    (root / relative).write_text('CHANGED = True\n')
    with pytest.raises(ValueError, match='uncommitted source bytes'):
        source.verify_source(root, record)


@pytest.mark.parametrize('fault', ['id', 'type', 'size', 'content', 'truncated', 'trailing', 'missing'])
def test_batch_protocol_rejects_tampering(repo, monkeypatch, fault):
    root, *_ = repo
    original = source.subprocess.check_output
    def corrupt(command, **kw):
        raw = original(command, **kw)
        if command[-2:] != ['cat-file', '--batch']:
            return raw
        header, body = raw.split(b'\n', 1)
        oid, kind, size = header.split()
        if fault == 'id': oid = b'0' * len(oid)
        if fault == 'type': kind = b'tree'
        if fault == 'size': size = str(int(size) + 1).encode()
        if fault == 'content': body = b'X' + body[1:]
        if fault == 'truncated': body = body[:-1]
        if fault == 'trailing': body += b'extra'
        if fault == 'missing': return oid + b' missing\n'
        return b' '.join((oid, kind, size)) + b'\n' + body
    monkeypatch.setattr(source.subprocess, 'check_output', corrupt)
    with pytest.raises(ValueError, match='source Git'):
        source.source_record(root, ['file.py'])


@pytest.mark.parametrize('fault', ['mode', 'type', 'path'])
def test_tree_entry_rejects_tampering(repo, monkeypatch, fault):
    root, *_ = repo
    original = w._source_git
    def corrupt(root, *args, **kw):
        raw = original(root, *args, **kw)
        if args[:3] == ('ls-tree', '-r', '-z'):
            if fault == 'mode': raw = raw.replace(b'100644 blob', b'120000 blob')
            if fault == 'type': raw = raw.replace(b'100644 blob', b'160000 commit')
            if fault == 'path': raw = raw.replace(b'\tfile.py\0', b'\tother.py\0')
        return raw
    monkeypatch.setattr(w, '_source_git', corrupt)
    with pytest.raises(ValueError, match='source Git'):
        source.source_record(root, ['file.py'])


def context_ref(f):
    row = f.plan['episodes'][0]
    return write(f.root / 'context.json', {'schema': 'n34-worker-context-v1',
        'plan': f.plan_ref, 'release': f.release_ref, 'expected_manifest': f.plan['expected_manifests'][row['episode_key']],
        'episode_key': row['episode_key'], 'attempt_id': row['episode_key'],
        'main_argv': ['synthetic-main'], 'worker_contract': worker.c.WORKER_CONTRACT})


def test_context_one_full_closure_all_rows_each_call(fixture):
    f = fixture
    ref = context_ref(f)
    for _ in range(2):
        f.calls.clear()
        worker.validate_context(ref)
        assert f.calls.count('sources') == f.calls.count('runtime') == 1
        assert f.calls.count('loaded') == f.calls.count('controller') == 1
        assert f.calls.count('files') == f.calls.count('inputs') == 1
        assert f.calls.count('manifest') == 30


@pytest.mark.parametrize('fault', ['source', 'runtime', 'unselected_manifest', 'detached'])
def test_new_context_transaction_rejects_changed_bytes(fixture, fault):
    f = fixture
    ref = context_ref(f)
    worker.validate_context(ref)
    path = {'source': f.source_file, 'runtime': Path(f.plan['runtime']['path']),
            'unselected_manifest': Path(f.plan['expected_manifests'][f.plan['episodes'][-1]['episode_key']]['path']),
            'detached': Path(f.release_ref['path'])}[fault]
    if fault == 'detached': path.unlink()
    else: path.write_text('{}')
    with pytest.raises(ValueError):
        worker.validate_context(ref)


def test_main_rechecks_after_gate_without_duplicate_worker_check(fixture, monkeypatch):
    f = fixture
    with pytest.raises(BoundaryReached):
        consume(f, 'worker_main', monkeypatch)
    assert f.calls.count('sources') == f.calls.count('runtime') == 2
    assert f.calls.count('manifest') == 60


def test_gate_mutation_rejected_before_dispatch(fixture, monkeypatch):
    f = fixture
    ref = context_ref(f)
    monkeypatch.setattr(worker.sys, 'argv', ['worker', '--context', ref['path'], '--context-sha256', ref['sha256']])
    class Gate:
        def read(self, size):
            assert f.calls.count('manifest') == 30
            f.source_file.write_text('modified while waiting')
            return b'G'
    monkeypatch.setattr(worker.sys, 'stdin', SimpleNamespace(buffer=Gate()))
    monkeypatch.setattr(worker.w, 'process_identity', lambda: pytest.fail('dispatch reached'))
    with pytest.raises(ValueError, match='synthetic source differs'):
        worker.main()


def test_standalone_manifest_validates_every_call(fixture, monkeypatch):
    f = fixture
    row = f.plan['episodes'][0]
    ref = f.plan['expected_manifests'][row['episode_key']]
    # Restore the real row checker; only expensive environment leaves are synthetic.
    monkeypatch.setattr(b, '_verify_manifest_bound', REAL_MANIFEST_ROW)
    monkeypatch.setattr(b, 'manifest', lambda *a: w.read_ref(ref))
    for _ in range(2): b.verify_manifest(ref, f.plan, f.runtime, row)
    assert f.calls.count('sources') == f.calls.count('runtime') == 2
    f.source_file.write_text('changed')
    with pytest.raises(ValueError, match='synthetic source differs'):
        b.verify_manifest(ref, f.plan, f.runtime, row)


REAL_MANIFEST_ROW = b._verify_manifest_bound


def test_unselected_manifest_semantics_checked(fixture, monkeypatch):
    f = fixture
    expected = {row['episode_key']: w.read_ref(f.plan['expected_manifests'][row['episode_key']]) for row in f.plan['episodes']}
    monkeypatch.setattr(b, '_verify_manifest_bound', REAL_MANIFEST_ROW)
    monkeypatch.setattr(b, 'manifest', lambda plan, runtime, row: expected[row['episode_key']])
    worker.validate_context(context_ref(f))
    expected[f.plan['episodes'][-1]['episode_key']]['argv'] = ['different']
    with pytest.raises(ValueError, match='external manifest/config/task/source differs'):
        worker.validate_context(context_ref(f))


def test_phase_begin_precedes_expensive_check_and_failure_is_reported(fixture, monkeypatch, capsys):
    f = fixture
    def fail(plan):
        events = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
        assert [(e['phase'], e['event']) for e in events][-1] == ('source_closure', 'begin')
        raise ValueError('phase test')
    monkeypatch.setattr(b, 'verify_sources', fail)
    with pytest.raises(ValueError, match='phase test'):
        release.validate_release(f.plan_ref, f.release_ref)
    events = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert [(e['phase'], e['event']) for e in events] == [('source_closure', 'failed'), ('release', 'failed')]
    assert all(e['elapsed_seconds'] >= 0 and 'accepted' not in e for e in events)


def test_runtime_and_loaded_bytes_rechecked(tmp_path, monkeypatch):
    path = tmp_path / 'runtime.py'; path.write_text('VALUE = 1\n')
    ref = {'test_only': True}
    closure = {'schema': 'n34-runtime-source-closure-v1', 'runtime': ref,
        'modules': {'synthetic': {'path': str(path), 'sha256': w.sha(path)}},
        'required_after': ['synthetic'],
        'interpreter': {'path': str(Path(source.sys.executable).resolve()),
                        'sha256': w.sha(Path(source.sys.executable).resolve()), 'version': source.sys.version},
        'versions': {k: 'test' for k in ('python', 'torch', 'libero', 'robosuite', 'mujoco')},
        'distribution_versions': {k: 'test' for k in ('torch', 'numpy', 'robosuite', 'mujoco', 'transformers')}}
    monkeypatch.setattr(source.importlib.metadata, 'version', lambda _: 'test')
    source.verify_runtime(closure, ref)
    module = SimpleNamespace(__file__=str(path))
    monkeypatch.setattr(source, 'sys', SimpleNamespace(modules={'synthetic': module},
        executable=source.sys.executable, version=source.sys.version))
    source.attest_runtime(closure, ref, after=True)
    wrong = tmp_path / 'wrong.py'; wrong.write_text('OTHER = 1\n')
    module.__file__ = str(wrong)
    with pytest.raises(ValueError, match='loaded runtime not frozen'):
        source.attest_runtime(closure, ref, after=True)
    path.write_text('VALUE = 2\n')
    with pytest.raises(ValueError, match='runtime source bytes differ'):
        source.verify_runtime(closure, ref)
