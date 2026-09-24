"""Independent CPU fake-process regression of the two initial observer defects."""
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
import pytest

S = Path("/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-stage-lifecycle-20260924")
for rel, sha in {
    "core/codex_stage.py": "beaf6386e5edd449ddf8df610bf25d08e34d42b3bc7e9e5d2c1418a244206960",
    "core/codex_stage_lifecycle.py": "de10576f89368b81c03b7b8d1d7c04e757a394d8b0b4974515c0b08e606d00e6",
}.items():
    assert hashlib.sha256((S/rel).read_bytes()).hexdigest() == sha
sys.path[:0] = [str(S), str(S/"tests")]
from test_codex_stage import make, identify, module
import core.codex_stage_lifecycle as lc

@pytest.mark.parametrize("fault", ["constructor", "after_spawn", "finish", "snapshot"])
@pytest.mark.parametrize("timeout", [False, True])
def test_hook_fault_preserves_acceptance_count_and_cleanup(monkeypatch, tmp_path, fault, timeout):
    rec, calls = make(monkeypatch, tmp_path, timeout=timeout)
    stopped = []
    monkeypatch.setattr(module, "_stop_owned_process", lambda p: stopped.append(p))
    class Broken(lc.StageLifecycle):
        def __init__(self, *args):
            if fault == "constructor": raise RuntimeError("DIAGNOSTIC_PRIVATE_PAYLOAD")
            super().__init__(*args)
        def mark(self, name):
            if fault == "after_spawn" and name == "spawn_returned_at":
                raise RuntimeError("DIAGNOSTIC_PRIVATE_PAYLOAD")
            super().mark(name)
        def finish(self, process):
            if fault == "finish": raise RuntimeError("DIAGNOSTIC_PRIVATE_PAYLOAD")
            super().finish(process)
        @property
        def data(self):
            if fault == "snapshot": raise RuntimeError("DIAGNOSTIC_PRIVATE_PAYLOAD")
            return super().data
    monkeypatch.setattr(module, "StageLifecycle", Broken)
    assert identify(rec) == ((1, True) if timeout else (2, False))
    assert len(calls) == 1 and calls[0].timeout == 90 and calls[0].prompt
    assert stopped == ([calls[0]] if timeout else [])
    assert rec.last_result["codex_completed_turns"] == 1
    assert rec.last_result["codex_usage_complete_calls"] == 1
    assert rec.last_result["codex_failed_calls"] == int(timeout)
    assert rec.last_result["codex_input_tokens"] == 108
    observation = rec.last_result["transport"]["lifecycle"]
    assert observation["observation_complete"] is False
    assert "DIAGNOSTIC_PRIVATE_PAYLOAD" not in json.dumps(observation)
    if timeout: assert rec.last_result["error"] == "codex_timeout"
    assert not any(t.name == "codex-stage-lifecycle" for t in threading.enumerate())

def test_blocked_pread_is_bounded_single_owned_fd_and_permanent_disable(monkeypatch, tmp_path):
    # Independent descriptor test: close/reuse the original fd before unblocking.
    monkeypatch.setattr(lc, "_OBSERVER_DISABLED", threading.Event())
    monkeypatch.setattr(lc, "_OBSERVER_SLOT", threading.BoundedSemaphore(1))
    entered, released = threading.Event(), threading.Event()
    original_pread = os.pread
    reads = []
    def blocked(fd, count, offset):
        reads.append(fd); entered.set()
        assert released.wait(3)
        return original_pread(fd, count, offset)
    monkeypatch.setattr(lc.os, "pread", blocked)
    source = tmp_path/"first"; source.write_bytes(b'{"type":"turn.started"}\n')
    f = source.open("rb")
    observer = lc.StageLifecycle(4096)
    observer.start(f)
    assert entered.wait(1)
    dupfd = reads[0]
    assert dupfd != f.fileno()
    before = time.monotonic()
    observer.finish(None)
    assert time.monotonic()-before < 1
    snapshot = observer.data; frozen = json.dumps(snapshot, sort_keys=True)
    assert snapshot["observer_error_category"] == "observer_join_timeout"
    assert not snapshot["observation_complete"]
    assert lc._OBSERVER_DISABLED.is_set()
    f.close()
    replacement = tmp_path/"replacement"; replacement.write_bytes(b"PRIVATE_REUSED_FD")
    with replacement.open("rb") as another:
        second = lc.StageLifecycle(4096); second.start(another); second.finish(None)
        assert second.data["observer_error_category"] == "prior_observer_timeout"
        assert second._fd is None and second._thread is None
    released.set(); observer._thread.join(timeout=2)
    assert not observer._thread.is_alive() and len(reads) == 1
    with pytest.raises(OSError): os.fstat(dupfd)
    assert json.dumps(snapshot, sort_keys=True) == frozen
    # Disable remains even after the formerly blocked worker has ended.
    with source.open("rb") as later:
        third = lc.StageLifecycle(4096); third.start(later)
        assert third.data["observer_error_category"] == "prior_observer_timeout"
        assert third._thread is None

