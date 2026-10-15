"""Synthetic repositories/fake children only; no actual historical objects."""
from dataclasses import replace
from hashlib import sha256
import importlib.util
import os
from pathlib import Path
import selectors
import subprocess
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import bounded_git_blob as b

HERE = Path(__file__).resolve().parent
CACHE_PATH = HERE.parent / 'validation-cost-cache-preparation-v1/verified_immutable_cache.py'
CACHE_SHA = 'f580ea88186b82364f14c4e8b2afbfa613e38a3a89683b0e2103fbe2e360675a'
GIT = '/usr/bin/git'
PYTHON = str(Path(sys.executable).resolve())
REAL_POPEN = subprocess.Popen
PAYLOAD = b'abc'
SPAWNED = []


def setup_git(args, cwd, content=b''):
    # Bound even setup child output; fixture setup is part of test time.
    child = REAL_POPEN([GIT] + args, cwd=cwd, env={**b.child_environment(),
        'GIT_AUTHOR_NAME': 'synthetic', 'GIT_AUTHOR_EMAIL': 'fixture.invalid',
        'GIT_COMMITTER_NAME': 'synthetic', 'GIT_COMMITTER_EMAIL': 'fixture.invalid',
        'GIT_AUTHOR_DATE': '2000-01-01T00:00:00Z', 'GIT_COMMITTER_DATE': '2000-01-01T00:00:00Z'},
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    SPAWNED.append(child)
    child.stdin.write(content)
    child.stdin.close()
    out = bytearray()
    deadline = time.monotonic() + 3
    try:
        with selectors.DefaultSelector() as sel:
            sel.register(child.stdout, selectors.EVENT_READ, True)
            sel.register(child.stderr, selectors.EVENT_READ, False)
            while sel.get_map():
                left = deadline - time.monotonic()
                if left <= 0:
                    raise RuntimeError('fixture Git timeout')
                for key, _ in sel.select(left):
                    data = os.read(key.fileobj.fileno(), 4096)
                    if not data:
                        sel.unregister(key.fileobj)
                    elif key.data:
                        out.extend(data)
                        if len(out) > 65536:
                            raise RuntimeError('fixture Git output bound')
                    else:
                        raise RuntimeError('fixture Git stderr')
        if child.wait(timeout=max(.01, deadline - time.monotonic())):
            raise RuntimeError('fixture Git exit')
        return bytes(out).strip()
    finally:
        b._reap_owned(child)
        child.stdout.close()
        child.stderr.close()


def key(initial_commit, **kw):
    values = dict(repository_identity='synthetic-repo-v1', commit=initial_commit,
        relative_path='file.txt', expected_sha256=sha256(PAYLOAD).hexdigest(),
        declared_size=len(PAYLOAD), verifier_version='synthetic-verifier-v1')
    values.update(kw)
    return SimpleNamespace(**values)


def load_cache():
    data = CACHE_PATH.read_bytes()
    assert sha256(data).hexdigest() == CACHE_SHA
    spec = importlib.util.spec_from_loader('accepted_cache', loader=None)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    exec(compile(data, str(CACHE_PATH), 'exec'), module.__dict__)
    return module


class LoaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures = HERE / 'fixtures'
        fixtures.mkdir(exist_ok=True)
        cls.fixture_run = fixtures / ('run-' + str(time.time_ns()))
        cls.fixture_run.mkdir()
        template = cls.fixture_run / 'empty-template'
        template.mkdir()
        cls.repo = cls.fixture_run / 'repo.git'
        setup_git(['init', '--quiet', '--bare', '--object-format=sha1', '--template='+str(template), str(cls.repo)], cls.fixture_run)
        blob = setup_git(['--git-dir='+str(cls.repo), 'hash-object', '-w', '--stdin'], cls.fixture_run, PAYLOAD)
        tree = setup_git(['--git-dir='+str(cls.repo), 'mktree'], cls.fixture_run, b'100644 blob '+blob+b'\tfile.txt\n')
        cls.commit = setup_git(['--git-dir='+str(cls.repo), 'commit-tree', tree.decode(), '-m', 'synthetic'], cls.fixture_run).decode()
        st, ob = cls.repo.stat(), (cls.repo / 'objects').stat()
        cls.binding = b.RepositoryBinding(str(cls.repo), st.st_dev, st.st_ino,
            ob.st_dev, ob.st_ino, 'synthetic-repo-v1', 'synthetic-verifier-v1')

    def loader(self, obj=None, **kw):
        obj = obj or key(self.commit)
        return b.BoundedGitBlobLoader(self.binding, [obj], **kw)

    def fake(self, mode):
        def launch(argv, **kw):
            self.assertEqual(argv[0], GIT)
            self.assertFalse(kw['shell'])
            self.assertEqual(kw['cwd'], str(self.repo))
            self.assertEqual(kw['env']['GIT_CONFIG_GLOBAL'], '/dev/null')
            self.assertEqual(kw['env']['GIT_NO_LAZY_FETCH'], '1')
            proc = REAL_POPEN([PYTHON, '-I', '-B', str(HERE / 'fake_child.py'), mode], **kw)
            SPAWNED.append(proc)
            return proc
        return patch.object(b.subprocess, 'Popen', launch)

    def test_real_local_git_and_cache_warm_hit(self):
        cachemod = load_cache()
        obj = cachemod.ObjectKey(**vars(key(self.commit)))
        loader = self.loader(obj)
        cache = cachemod.VerifiedImmutableCache([obj])
        self.assertEqual(cache.get(obj, loader), PAYLOAD)
        self.assertEqual(cache.get(obj, loader), PAYLOAD)
        self.assertEqual(loader.spawn_count, 1)
        self.assertEqual(cache.stats().hits, 1)
        self.assertEqual(cache.stats().verified_loads, 1)

    def test_cache_independently_rejects_digest(self):
        cachemod = load_cache()
        obj = cachemod.ObjectKey(**vars(key(self.commit, expected_sha256='0'*64)))
        loader = self.loader(obj)
        cache = cachemod.VerifiedImmutableCache([obj])
        with self.assertRaisesRegex(cachemod.CacheError, 'SHA-256'):
            cache.get(obj, loader)
        self.assertEqual(cache.stats().retained_objects, 0)
        self.assertEqual(loader.spawn_count, 1)

    def test_real_missing_object(self):
        obj = key('0'*40)
        loader = self.loader(obj)
        with self.assertRaises(b.BlobError):
            loader(obj)
        self.assertEqual(loader.spawn_count, 1)

    def test_nonbare_config_supported(self):
        p = self.repo / 'config'
        old = p.read_bytes()
        try:
            p.write_bytes(old.replace(b'bare = true', b'bare = false'))
            self.assertEqual(self.loader()(key(self.commit)), PAYLOAD)
        finally:
            p.write_bytes(old)

    def test_config_include_rejected_before_spawn(self):
        p = self.repo / 'config'
        old = p.read_bytes()
        try:
            p.write_bytes(old+b'[include]\n\tpath = /unauthorized\n')
            loader = self.loader()
            with self.assertRaises(b.BlobError):
                loader(key(self.commit))
            self.assertEqual(loader.spawn_count, 0)
        finally:
            p.write_bytes(old)

    def test_repository_inode_mismatch(self):
        loader = b.BoundedGitBlobLoader(replace(self.binding, inode=self.binding.inode+1), [key(self.commit)])
        with self.assertRaises(b.BlobError):
            loader(key(self.commit))
        self.assertEqual(loader.spawn_count, 0)

    def test_objects_inode_mismatch(self):
        loader = b.BoundedGitBlobLoader(replace(self.binding, object_inode=self.binding.object_inode+1), [key(self.commit)])
        with self.assertRaises(b.BlobError):
            loader(key(self.commit))
        self.assertEqual(loader.spawn_count, 0)

    def test_alternate_rejected(self):
        info = self.repo / 'objects/info'
        p = info / 'alternates'
        p.write_bytes(b'/unauthorized\n')
        try:
            loader = self.loader()
            with self.assertRaises(b.BlobError):
                loader(key(self.commit))
            self.assertEqual(loader.spawn_count, 0)
        finally:
            p.unlink()

    def test_reentrant_rejected_and_no_poison(self):
        loader = self.loader()
        loader._lock.acquire()
        try:
            with self.assertRaisesRegex(b.BlobError, 'reentrant'):
                loader(key(self.commit))
        finally:
            loader._lock.release()
        self.assertEqual(loader(key(self.commit)), PAYLOAD)
        self.assertEqual(loader.spawn_count, 1)

    def test_failure_does_not_implicitly_retry_or_poison(self):
        loader = self.loader()
        with self.fake('short'), self.assertRaises(b.BlobError):
            loader(key(self.commit))
        self.assertEqual(loader.spawn_count, 1)
        with self.fake('good'):
            self.assertEqual(loader(key(self.commit)), PAYLOAD)
        self.assertEqual(loader.spawn_count, 2)

    def test_unallowlisted_pre_spawn(self):
        loader = self.loader()
        with self.assertRaises(b.BlobError):
            loader(key(self.commit, relative_path='other.txt'))
        self.assertEqual(loader.spawn_count, 0)

    def test_request_exact_and_environment_not_inherited(self):
        original = b._read_response
        seen = []
        def inspect(child, size, deadline):
            seen.append(size)
            return original(child, size, deadline)
        with patch.dict(os.environ, {'GIT_DIR': '/not-allowed', 'GIT_ALTERNATE_OBJECT_DIRECTORIES': '/not-allowed', 'LD_PRELOAD': '/not-allowed'}):
            with patch.object(b, '_read_response', inspect):
                self.assertEqual(self.loader()(key(self.commit)), PAYLOAD)
        self.assertEqual(seen, [3])


    def test_dotfile_path_supported(self):
        obj = key(self.commit, relative_path='.github/.gitignore')
        with self.fake('good'):
            self.assertEqual(self.loader(obj)(obj), PAYLOAD)

    def test_maximum_body_success(self):
        payload = b'x' * b.MAX_OBJECT
        obj = key(self.commit, declared_size=len(payload), expected_sha256=sha256(payload).hexdigest())
        with self.fake('maximum'):
            self.assertEqual(self.loader(obj)(obj), payload)

    def test_noncanonical_repository_rejected(self):
        binding = replace(self.binding, directory=str(self.repo)+'/../repo.git')
        loader = b.BoundedGitBlobLoader(binding, [key(self.commit)])
        with self.assertRaises(b.BlobError):
            loader(key(self.commit))
        self.assertEqual(loader.spawn_count, 0)

    def test_repo_symlink_rejected(self):
        alias = self.fixture_run / 'alias.git'
        alias.symlink_to(self.repo, target_is_directory=True)
        try:
            loader = b.BoundedGitBlobLoader(replace(self.binding, directory=str(alias)), [key(self.commit)])
            with self.assertRaises(b.BlobError):
                loader(key(self.commit))
            self.assertEqual(loader.spawn_count, 0)
        finally:
            alias.unlink()

    def test_declared_overflow_at_call_pre_spawn(self):
        loader = self.loader()
        with self.assertRaises(b.BlobError):
            loader(key(self.commit, declared_size=b.MAX_OBJECT+1))
        self.assertEqual(loader.spawn_count, 0)

    def test_oversized_config_pre_spawn(self):
        p = self.repo / 'config'
        old = p.read_bytes()
        try:
            p.write_bytes(b'x' * 4097)
            loader = self.loader()
            with self.assertRaises(b.BlobError):
                loader(key(self.commit))
            self.assertEqual(loader.spawn_count, 0)
        finally:
            p.write_bytes(old)

    def test_exact_request_bytes(self):
        obj = key(self.commit)
        loader = self.loader(obj)
        old_write = b.os.write
        sent = []
        def capture(fd, value):
            sent.append(value)
            return old_write(fd, value)
        with self.fake('good'), patch.object(b.os, 'write', capture):
            self.assertEqual(loader(obj), PAYLOAD)
        self.assertEqual(sent, [(self.commit+'^{commit}:file.txt\n').encode('ascii')])


def response_test(mode, success=False):
    def run(self):
        obj = key(self.commit, declared_size=0, expected_sha256=sha256(b'').hexdigest()) if mode == 'empty' else key(self.commit)
        loader = self.loader(obj, timeout=.15 if mode in ('timeout', 'ignore-term', 'closed-pipes') else 2)
        before = len(SPAWNED)
        started = time.monotonic()
        with self.fake(mode):
            if success:
                self.assertEqual(loader(obj), b'' if mode == 'empty' else PAYLOAD)
            else:
                with self.assertRaises(b.BlobError):
                    loader(obj)
        self.assertEqual(loader.spawn_count, 1)
        self.assertEqual(len(SPAWNED), before+1)
        self.assertIsNotNone(SPAWNED[-1].poll())
        self.assertTrue(SPAWNED[-1].stdout.closed)
        self.assertTrue(SPAWNED[-1].stderr.closed)
        self.assertLess(time.monotonic()-started, 3)
    return run

for mode in ('good','split','empty','missing','type','size','mismatch','leading-zero','bad-oid',
             'header','short','no-trailer','bad-trailer','excess','later-excess','stderr',
             'stderr-overflow','nonzero','timeout','ignore-term','closed-pipes'):
    setattr(LoaderTests, 'test_response_'+mode.replace('-', '_'), response_test(mode, mode in ('good','split','empty')))


def invalid_key_test(change):
    def run(self):
        with self.assertRaises(b.BlobError):
            self.loader(key(self.commit, **change))
    return run

for i, change in enumerate([
    {'declared_size': 1048577}, {'declared_size': -1}, {'declared_size': True},
    {'commit': 'HEAD'}, {'commit': 'a'*64}, {'commit': 'A'*40},
    {'relative_path': '../x'}, {'relative_path': '/x'}, {'relative_path': 'a//b'},
    {'relative_path': 'a:b'}, {'relative_path': 'x\nother'}, {'relative_path': '-x'},
    {'relative_path': 'a\\b'}, {'relative_path': 'a/./b'}, {'relative_path': 'a space'},
    {'repository_identity': 'different'}, {'verifier_version': 'different'},
    {'expected_sha256': 'x'*64},
]):
    setattr(LoaderTests, 'test_invalid_key_%02d'%i, invalid_key_test(change))


def invalid_timeout_test(value):
    def run(self):
        with self.assertRaises(b.BlobError):
            self.loader(timeout=value)
    return run

for i, value in enumerate([0, -1, 5.01, float('inf'), float('nan'), True]):
    setattr(LoaderTests, 'test_invalid_deadline_%02d'%i, invalid_timeout_test(value))
