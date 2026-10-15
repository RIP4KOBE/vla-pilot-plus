"""Unintegrated synchronous SHA-1 Git-directory blob loader.

Only reviewed immutable keys are admitted. The accepted cache MUST independently
check the returned bytes' SHA-256. This module never resolves HEAD/branches,
creates an inventory, retries, or caches admission decisions. The caller owns
fresh provenance/authority checks and a trusted quiescent local object store.
"""
from dataclasses import dataclass
import math
import os
from pathlib import Path
import re
import selectors
import stat
import subprocess
from threading import Lock
import time

MAX_OBJECT = 1024 * 1024
HEADER_CAP = 128
STDERR_CAP = 64 * 1024
SAFE_CONFIG = b'[core]\n\trepositoryformatversion = 0\n\tfilemode = true\n\tbare = true\n'


class BlobError(ValueError):
    pass


def _canonical_directory(value):
    p = Path(value)
    if str(p) != value or not p.is_absolute() or str(p) != str(p.resolve(strict=True)) or not p.is_dir():
        raise BlobError('repository directory must be canonical and existing')
    return p


@dataclass(frozen=True)
class RepositoryBinding:
    directory: str
    device: int
    inode: int
    object_device: int
    object_inode: int
    repository_identity: str
    verifier_version: str

    def __post_init__(self):
        if (type(self.directory) is not str or type(self.device) is not int
                or type(self.inode) is not int or self.device < 0 or self.inode < 1
                or type(self.object_device) is not int or self.object_device < 0
                or type(self.object_inode) is not int or self.object_inode < 1):
            raise BlobError('invalid directory identity')
        for v in (self.repository_identity, self.verifier_version):
            if type(v) is not str or re.fullmatch(r'[A-Za-z0-9_.:/-]{1,512}', v) is None:
                raise BlobError('unsupported repository/verifier key')


def _key_tuple(key):
    try:
        values = (key.repository_identity, key.commit, key.relative_path,
                  key.expected_sha256, key.declared_size, key.verifier_version)
    except AttributeError as exc:
        raise BlobError('malformed object key') from exc
    repo, commit, path, digest, size, verifier = values
    if type(size) is not int or not 0 <= size <= MAX_OBJECT:
        raise BlobError('declared object size exceeds bound')
    if type(commit) is not str or re.fullmatch(r'[0-9a-f]{40}', commit) is None:
        raise BlobError('only an exact SHA-1 commit ID is supported')
    if type(digest) is not str or re.fullmatch(r'[0-9a-f]{64}', digest) is None:
        raise BlobError('invalid expected SHA-256')
    if (type(path) is not str or not 1 <= len(path) <= 4096
            or any(re.fullmatch(r'\.?[A-Za-z0-9_][A-Za-z0-9_.-]*', part) is None
                   for part in path.split('/'))):
        raise BlobError('unsupported relative path')
    if type(repo) is not str or type(verifier) is not str:
        raise BlobError('invalid key identity')
    return values


def child_environment():
    # No inherited Git config, replace refs, credentials, alternates, dynamic
    # loader overrides or network transport. Local repo config is checked below.
    return {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C', 'LANG': 'C',
            'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
            'GIT_CONFIG_SYSTEM': '/dev/null', 'GIT_NO_REPLACE_OBJECTS': '1',
            'GIT_TERMINAL_PROMPT': '0', 'GIT_OPTIONAL_LOCKS': '0',
            'GIT_NO_LAZY_FETCH': '1', 'CUDA_VISIBLE_DEVICES': '',
            'OMP_NUM_THREADS': '2', 'OPENBLAS_NUM_THREADS': '2',
            'MKL_NUM_THREADS': '2'}


def _reap_owned(child):
    if child.poll() is not None:
        child.wait(timeout=0.25)
        return
    child.terminate()
    try:
        child.wait(timeout=0.25)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=0.75)


def _read_response(child, declared, deadline):
    header = bytearray()
    body = bytearray()  # stays empty until validated header
    size = None
    trailer = False
    stderr_bytes = 0
    with selectors.DefaultSelector() as selector:
        for stream, name in ((child.stdout, 'out'), (child.stderr, 'err')):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise BlobError('child deadline exceeded')
            for event, _ in selector.select(remaining):
                stream = event.fileobj
                if event.data == 'err':
                    cap = min(4096, STDERR_CAP - stderr_bytes + 1)
                elif size is None:
                    cap = HEADER_CAP - len(header) + 1
                else:
                    cap = min(4096, max(1, declared - len(body) + (not trailer)))
                block = os.read(stream.fileno(), cap)
                if not block:
                    selector.unregister(stream)
                    continue
                if event.data == 'err':
                    stderr_bytes += len(block)
                    if stderr_bytes > STDERR_CAP:
                        raise BlobError('stderr bound exceeded')
                    continue  # never retain/print stderr payload
                if size is None:
                    end = block.find(b'\n')
                    if end < 0:
                        header.extend(block)
                        if len(header) >= HEADER_CAP:
                            raise BlobError('header bound exceeded')
                        continue
                    header.extend(block[:end])
                    if len(header) + 1 > HEADER_CAP:
                        raise BlobError('header bound exceeded')
                    match = re.fullmatch(rb'[0-9a-f]{40} blob (0|[1-9][0-9]{0,6})', header)
                    if match is None:
                        raise BlobError('malformed/missing/non-blob response')
                    size = int(match.group(1))
                    if size != declared or size > MAX_OBJECT:
                        raise BlobError('reported blob size differs from declared bound')
                    block = block[end + 1:]
                needed = declared - len(body)
                body.extend(block[:needed])
                extra = block[needed:]
                if extra:
                    if trailer or extra != b'\n':
                        raise BlobError('excess body or invalid trailer')
                    trailer = True
        if size is None or len(body) != declared or not trailer:
            raise BlobError('short response')
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise BlobError('child deadline exceeded')
        try:
            code = child.wait(timeout=remaining)
        except subprocess.TimeoutExpired as exc:
            raise BlobError('child deadline exceeded') from exc
        if code != 0 or stderr_bytes:
            raise BlobError('child failed or emitted stderr')
    return bytes(body)


class BoundedGitBlobLoader:
    """One child/miss; explicit SHA-1 Git directory only, no fallback. Reentry refused.

    This binds canonical directory inode and minimal supported config, not a
    hostile concurrently mutated filesystem. Ordinary worktrees/common-dir
    discovery, alternates, promisor repos and arbitrary Git config are unsupported.
    """
    def __init__(self, binding, allowlist, *, git_executable='/usr/bin/git', timeout=5.0):
        if type(binding) is not RepositoryBinding:
            raise BlobError('explicit repository binding required')
        if (type(timeout) not in (float, int) or isinstance(timeout, bool)
                or not math.isfinite(timeout) or not 0 < timeout <= 5):
            raise BlobError('deadline must be finite and at most five seconds')
        if type(allowlist) not in (tuple, list) or len(allowlist) > 2048:
            raise BlobError('explicit bounded allowlist required')
        keys = tuple(_key_tuple(k) for k in allowlist)
        if len(set(keys)) != len(keys):
            raise BlobError('duplicate allowed key')
        if any(k[0] != binding.repository_identity or k[5] != binding.verifier_version for k in keys):
            raise BlobError('key/repository/verifier mismatch')
        executable = Path(git_executable)
        if (not executable.is_absolute() or str(executable.resolve(strict=True)) != str(executable)
                or not stat.S_ISREG(executable.stat().st_mode) or not os.access(executable, os.X_OK)):
            raise BlobError('canonical local Git executable required')
        self.binding, self.allowed = binding, frozenset(keys)
        self.executable, self.timeout = str(executable), float(timeout)
        self.spawn_count = 0
        self._lock = Lock()

    def _repository(self):
        repo = _canonical_directory(self.binding.directory)
        st = repo.stat()
        if (st.st_dev, st.st_ino) != (self.binding.device, self.binding.inode):
            raise BlobError('repository directory identity changed')
        for part in ('objects', 'refs'):
            p = repo / part
            if p.is_symlink() or not p.is_dir():
                raise BlobError('unsupported repository structure')
        objects = (repo / 'objects').stat()
        if (objects.st_dev, objects.st_ino) != (self.binding.object_device, self.binding.object_inode):
            raise BlobError('object-directory identity changed')
        config = repo / 'config'
        if config.is_symlink() or not config.is_file() or config.stat().st_size > 4096:
            raise BlobError('unsupported repository config')
        with config.open('rb') as handle:
            data = handle.read(4097)
        # Both bare values supported; no config includes, helpers or remotes.
        if len(data) > 4096:
            raise BlobError('repository config bound exceeded')
        lines = data.splitlines()
        if not lines or lines[0] != b'[core]':
            raise BlobError('unsupported repository config')
        fields = {}
        for line in lines[1:]:
            match = re.fullmatch(rb'\s*(repositoryformatversion|filemode|bare|logallrefupdates) = (0|true|false)', line)
            if match is None or match.group(1) in fields:
                raise BlobError('unsupported repository config')
            fields[match.group(1)] = match.group(2)
        if (fields.get(b'repositoryformatversion') != b'0'
                or any(fields.get(k) not in (b'true', b'false') for k in (b'bare', b'filemode'))
                or fields.get(b'logallrefupdates', b'false') not in (b'true', b'false')):
            raise BlobError('unsupported repository config')
        for part in ('objects/info/alternates', 'objects/info/http-alternates', 'shallow'):
            if os.path.lexists(repo / part):
                raise BlobError('alternate/shallow repository unsupported')
        return repo

    def __call__(self, key):
        if not self._lock.acquire(blocking=False):
            raise BlobError('concurrent/reentrant load forbidden')
        child = None
        try:
            values = _key_tuple(key)
            if values not in self.allowed:
                raise BlobError('object is not explicitly allowlisted')
            repo = self._repository()
            request = (values[1] + '^{commit}:' + values[2] + '\n').encode('ascii')
            argv = [self.executable, '--no-replace-objects', '--git-dir=' + str(repo),
                    '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
                    '-c', 'protocol.allow=never', '-c', 'core.attributesFile=/dev/null',
                    'cat-file', '--batch']
            deadline = time.monotonic() + self.timeout
            child = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, cwd=str(repo), env=child_environment(),
                                     shell=False, close_fds=True, bufsize=0)
            self.spawn_count += 1
            # <=4150 bytes: nonblocking input avoids a malicious child filling
            # stdout instead of consuming stdin; no blocking writer thread.
            os.set_blocking(child.stdin.fileno(), False)
            written = os.write(child.stdin.fileno(), request)
            if written != len(request):
                raise BlobError('short request write')
            child.stdin.close()
            return _read_response(child, values[4], deadline)
        finally:
            try:
                if child is not None:
                    try:
                        _reap_owned(child)
                    finally:
                        for stream in (child.stdin, child.stdout, child.stderr):
                            if stream is not None:
                                stream.close()
            finally:
                self._lock.release()
