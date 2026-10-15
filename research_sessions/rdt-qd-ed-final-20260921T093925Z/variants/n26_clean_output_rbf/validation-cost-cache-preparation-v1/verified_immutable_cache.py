"""Unwired cache for allowlisted immutable source objects; performs no I/O.

A trusted adapter supplies *bounded* bytes reads. This class bounds admitted
objects, not allocations or side effects inside an arbitrary loader callback.
It must not represent live admission/state/process/budget/provider/GPU checks.
"""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import PurePosixPath
import re
from threading import Lock


class CacheError(ValueError):
    pass


class CacheBusy(RuntimeError):
    """A callback is in progress: concurrent and reentrant access is refused."""


def _text(value, name, maximum):
    if (type(value) is not str or not value or len(value) > maximum
            or value != value.strip() or "\0" in value):
        raise CacheError(f"invalid {name}")


def _limit(value, name, maximum):
    if type(value) is not int or not 1 <= value <= maximum:
        raise CacheError(f"invalid {name}")


@dataclass(frozen=True, slots=True)
class ObjectKey:
    repository_identity: str
    commit: str
    relative_path: str
    expected_sha256: str
    declared_size: int
    verifier_version: str

    def __post_init__(self):
        _text(self.repository_identity, "repository identity", 1024)
        _text(self.verifier_version, "verifier version", 512)
        if type(self.commit) is not str or re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", self.commit) is None:
            raise CacheError("commit must be an exact lowercase object ID")
        if type(self.expected_sha256) is not str or re.fullmatch(r"[0-9a-f]{64}", self.expected_sha256) is None:
            raise CacheError("expected SHA-256 must be exact lowercase hex")
        _text(self.relative_path, "relative path", 4096)
        path = PurePosixPath(self.relative_path)
        if (path.is_absolute() or "\\" in self.relative_path
                or any(part in ("", ".", "..") for part in self.relative_path.split("/"))
                or path.as_posix() != self.relative_path):
            raise CacheError("relative path must be canonical and traversal-free")
        if type(self.declared_size) is not int or self.declared_size < 0:
            raise CacheError("declared size must be a nonnegative integer")


@dataclass(frozen=True, slots=True)
class CacheStats:
    requests: int
    hits: int
    load_attempts: int
    verified_loads: int
    failed_loads: int
    rejected_before_load: int
    retained_objects: int
    retained_bytes: int
    loader_returned_bytes: int


class VerifiedImmutableCache:
    """Synchronous, no eviction, no persistent state, exact bytes only.

    The allowlist is copied. Oversubscription of the retained-byte cap in the
    allowlist is permitted, but a miss that cannot fit is refused *before* I/O.
    Busy refusals do not enter counters: they cannot acquire the state lock.
    loader_returned_bytes counts observed bytes even on verification failure;
    it is cumulative traffic, not a bound on callback allocations or I/O.
    """

    def __init__(self, allowlist, *, max_entries=2048,
                 max_object_bytes=1024 * 1024, max_retained_bytes=64 * 1024 * 1024):
        _limit(max_entries, "entry cap", 2048)
        _limit(max_object_bytes, "object cap", 1024 * 1024)
        _limit(max_retained_bytes, "retained-byte cap", 64 * 1024 * 1024)
        if type(allowlist) not in (list, tuple) or len(allowlist) > max_entries:
            raise CacheError("allowlist must be a bounded list or tuple")
        if any(type(key) is not ObjectKey for key in allowlist):
            raise CacheError("allowlist contains a non-ObjectKey")
        if len(set(allowlist)) != len(allowlist):
            raise CacheError("duplicate allowlist key")
        if any(key.declared_size > max_object_bytes for key in allowlist):
            raise CacheError("declared object exceeds per-object cap")
        self._allowed = frozenset(allowlist)
        self._max_object_bytes = max_object_bytes
        self._max_retained_bytes = max_retained_bytes
        self._cache = {}
        self._lock = Lock()
        self._requests = self._hits = self._load_attempts = 0
        self._verified_loads = self._failed_loads = self._rejected = 0
        self._retained_bytes = self._returned_bytes = 0

    def get(self, key, loader):
        if not self._lock.acquire(blocking=False):
            raise CacheBusy("reentrant or concurrent access is forbidden")
        try:
            self._requests += 1
            if type(key) is not ObjectKey or key not in self._allowed:
                self._rejected += 1
                raise CacheError("key is not explicitly allowlisted")
            if not callable(loader):
                self._rejected += 1
                raise CacheError("a trusted bounded loader is required")
            if key in self._cache:
                self._hits += 1
                return self._cache[key]
            if (key.declared_size > self._max_object_bytes
                    or self._retained_bytes + key.declared_size > self._max_retained_bytes):
                self._rejected += 1
                raise CacheError("declared object cannot fit retained capacity")
            self._load_attempts += 1
            try:
                value = loader(key)
                if type(value) is not bytes:
                    raise CacheError("loader must return immutable bytes, not a decision or view")
                self._returned_bytes += len(value)
                if (len(value) != key.declared_size or len(value) > self._max_object_bytes
                        or self._retained_bytes + len(value) > self._max_retained_bytes):
                    raise CacheError("actual byte length violates declared size or capacity")
                if sha256(value).hexdigest() != key.expected_sha256:
                    raise CacheError("object SHA-256 mismatch")
            except BaseException:
                self._failed_loads += 1
                raise
            self._cache[key] = value
            self._retained_bytes += len(value)
            self._verified_loads += 1
            return value
        finally:
            self._lock.release()

    def stats(self):
        if not self._lock.acquire(blocking=False):
            raise CacheBusy("cannot snapshot during a loader callback")
        try:
            return CacheStats(self._requests, self._hits, self._load_attempts,
                              self._verified_loads, self._failed_loads, self._rejected,
                              len(self._cache), self._retained_bytes, self._returned_bytes)
        finally:
            self._lock.release()
