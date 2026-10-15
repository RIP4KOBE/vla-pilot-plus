"""All inputs are synthetic in-memory bytes; no filesystem loaders exist."""
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
from threading import Event, Thread

import pytest

from verified_immutable_cache import CacheBusy, CacheError, ObjectKey, VerifiedImmutableCache


def key(payload=b"abcd", **changes):
    return replace(ObjectKey("synthetic-repository-A", "1" * 40, "scripts/example.py",
                             sha256(payload).hexdigest(), len(payload), "source-bridge-v1"), **changes)


def never(_):
    pytest.fail("loader was called despite a pre-load refusal or hit")


def test_verified_hit_immutable_snapshot_and_counts():
    payload = b"abcd"
    k = key(payload)
    cache = VerifiedImmutableCache([k])
    calls = []
    assert cache.get(k, lambda actual: calls.append(actual) or payload) is payload
    assert cache.get(k, never) is payload
    assert calls == [k]
    stats = cache.stats()
    assert (stats.requests, stats.hits, stats.load_attempts, stats.verified_loads,
            stats.failed_loads, stats.rejected_before_load, stats.retained_objects,
            stats.retained_bytes, stats.loader_returned_bytes) == (2, 1, 1, 1, 0, 0, 1, 4, 4)
    with pytest.raises(FrozenInstanceError):
        stats.hits = 8
    with pytest.raises(TypeError):
        payload[0] = 1
    with pytest.raises(FrozenInstanceError):
        k.commit = "HEAD"


@pytest.mark.parametrize("change", [
    {"commit": "HEAD"}, {"commit": "main"}, {"commit": "a" * 39}, {"commit": "A" * 40},
    {"relative_path": "../file"}, {"relative_path": "a/../file"}, {"relative_path": "/file"},
    {"relative_path": "./file"}, {"relative_path": "a//file"}, {"relative_path": "file/"},
    {"relative_path": "a\\file"}, {"relative_path": "a\0file"}, {"relative_path": ""},
    {"expected_sha256": "a" * 63}, {"expected_sha256": "G" * 64},
    {"declared_size": -1}, {"declared_size": True},
    {"repository_identity": ""}, {"verifier_version": " "},
])
def test_invalid_key_refused(change):
    with pytest.raises(CacheError):
        key(**change)


def test_exact_64_hex_commit_allowed():
    k = key(commit="a" * 64)
    assert VerifiedImmutableCache([k]).get(k, lambda _: b"abcd") == b"abcd"


def test_unknown_and_live_decision_keys_refused_before_callback():
    k = key()
    cache = VerifiedImmutableCache([k])
    for unknown in (replace(k, repository_identity="other"), "budget", "HEAD", {"admission": True}):
        with pytest.raises(CacheError):
            cache.get(unknown, never)
    assert cache.stats().load_attempts == 0
    assert cache.stats().rejected_before_load == 4


@pytest.mark.parametrize("bad", [b"xxxx", b"abc", b"abcde", bytearray(b"abcd"),
                                  memoryview(b"abcd"), {"admission": True}, True, None])
def test_failed_value_not_retained_and_retry_not_poisoned(bad):
    k = key()
    cache = VerifiedImmutableCache([k], max_object_bytes=4, max_retained_bytes=4)
    with pytest.raises(CacheError):
        cache.get(k, lambda _: bad)
    before = cache.stats()
    assert (before.failed_loads, before.retained_bytes, before.retained_objects) == (1, 0, 0)
    assert cache.get(k, lambda _: b"abcd") == b"abcd"
    assert cache.get(k, never) == b"abcd"
    after = cache.stats()
    assert (after.requests, after.hits, after.load_attempts, after.verified_loads,
            after.failed_loads, after.retained_bytes) == (3, 1, 2, 1, 1, 4)
    assert after.loader_returned_bytes == 4 + (len(bad) if type(bad) is bytes else 0)


def test_callback_exception_not_cached():
    cache = VerifiedImmutableCache([key()])
    def failing(_):
        raise OSError("synthetic loader failure")
    with pytest.raises(OSError, match="synthetic"):
        cache.get(key(), failing)
    assert cache.get(key(), lambda _: b"abcd") == b"abcd"
    assert cache.stats().failed_loads == 1


def test_capacity_before_second_callback_and_hits_still_work():
    first, second = key(), key(relative_path="second.py")
    cache = VerifiedImmutableCache([first, second], max_object_bytes=4, max_retained_bytes=4)
    assert cache.get(first, lambda _: b"abcd") == b"abcd"
    with pytest.raises(CacheError, match="capacity"):
        cache.get(second, never)
    assert cache.get(first, never) == b"abcd"
    stats = cache.stats()
    assert (stats.load_attempts, stats.rejected_before_load, stats.retained_bytes) == (1, 1, 4)


def test_empty_value_is_a_real_cache_hit():
    cache = VerifiedImmutableCache([key(b"")])
    assert cache.get(key(b""), lambda _: b"") == b""
    assert cache.get(key(b""), never) == b""
    assert (cache.stats().retained_objects, cache.stats().hits) == (1, 1)


@pytest.mark.parametrize("limits", [{"max_entries": 0}, {"max_entries": 2049},
    {"max_object_bytes": 1048577}, {"max_retained_bytes": 67108865},
    {"max_retained_bytes": True}, {"max_object_bytes": 0}])
def test_limit_enlargement_or_invalid_type_rejected(limits):
    with pytest.raises(CacheError):
        VerifiedImmutableCache([key()], **limits)


def test_finite_allowlist_entries_object_limits_and_copy():
    first, second = key(), key(relative_path="second.py")
    for allowed in ((k for k in [first]), {first}, [first, first], ["HEAD"]):
        with pytest.raises(CacheError):
            VerifiedImmutableCache(allowed)
    with pytest.raises(CacheError):
        VerifiedImmutableCache([first, second], max_entries=1)
    with pytest.raises(CacheError):
        VerifiedImmutableCache([first], max_object_bytes=3)
    mutable = [first]
    cache = VerifiedImmutableCache(mutable)
    mutable.append(second)
    with pytest.raises(CacheError):
        cache.get(second, never)


@pytest.mark.parametrize("difference", [
    {"repository_identity": "synthetic-repository-B"}, {"commit": "2" * 40},
    {"relative_path": "other.py"}, {"verifier_version": "bridge-v2"},
])
def test_identity_fields_do_not_alias(difference):
    first, other = key(), key(**difference)
    cache = VerifiedImmutableCache([first, other])
    calls = []
    for k in (first, other):
        cache.get(k, lambda actual: calls.append(actual) or b"abcd")
    assert calls == [first, other]
    assert cache.stats().retained_objects == 2
    assert cache.get(first, never) == cache.get(other, never)


def test_digest_and_size_are_part_of_exact_identity():
    keys = [key(b"abcd"), key(b"wxyz"), key(b"abc")]
    cache = VerifiedImmutableCache(keys)
    for k, value in zip(keys, (b"abcd", b"wxyz", b"abc"), strict=True):
        assert cache.get(k, lambda _, v=value: v) == value
    assert cache.stats().retained_objects == 3


def test_reentrant_load_refused_without_poisoning_retry():
    first, second = key(), key(relative_path="second.py")
    cache = VerifiedImmutableCache([first, second], max_retained_bytes=4)
    def nested(_):
        return cache.get(second, never)
    with pytest.raises(CacheBusy):
        cache.get(first, nested)
    assert (cache.stats().failed_loads, cache.stats().retained_bytes) == (1, 0)
    assert cache.get(second, lambda _: b"abcd") == b"abcd"
    with pytest.raises(CacheError, match="capacity"):
        cache.get(first, never)


def test_caught_reentry_does_not_reserve_or_bypass_capacity():
    first, second = key(), key(relative_path="second.py")
    cache = VerifiedImmutableCache([first, second], max_retained_bytes=4)
    def nested(_):
        with pytest.raises(CacheBusy):
            cache.get(second, never)
        with pytest.raises(CacheBusy):
            cache.stats()
        return b"abcd"
    assert cache.get(first, nested) == b"abcd"
    with pytest.raises(CacheError):
        cache.get(second, never)
    assert cache.stats().retained_bytes == 4


def test_concurrent_callback_is_not_invoked():
    first, second = key(), key(relative_path="second.py")
    cache = VerifiedImmutableCache([first, second])
    entered, release = Event(), Event()
    values, errors = [], []
    def loader(_):
        entered.set()
        if not release.wait(2):
            raise RuntimeError("synthetic synchronization timed out")
        return b"abcd"
    def work():
        try:
            values.append(cache.get(first, loader))
        except BaseException as exc:
            errors.append(exc)
    thread = Thread(target=work)
    thread.start()
    try:
        assert entered.wait(2)
        with pytest.raises(CacheBusy):
            cache.get(second, never)
    finally:
        release.set()
        thread.join(3)
    assert not thread.is_alive() and not errors and values == [b"abcd"]
    assert cache.get(second, lambda _: b"abcd") == b"abcd"
    assert cache.stats().load_attempts == 2


def test_non_callable_not_admitted():
    cache = VerifiedImmutableCache([key()])
    with pytest.raises(CacheError):
        cache.get(key(), None)
    assert cache.stats().rejected_before_load == 1
