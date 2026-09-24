"""CPU local children only; differential oracle is the frozen f6a9ab04 source."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import core.codex_stage as current
import core.codex_stage_lifecycle as lifecycle_module
from core.codex_stage_lifecycle import StageLifecycle
from test_codex_stage import ANSWER, USAGE, events, identify

BASE = "f6a9ab04c0f184bbe2f8c837b33492835bc8fec9"
BASE_SHA = "27adf43302afc455a1b3122f267c7493c212bc83982bdaeba09d89873913da25"
REAL_POPEN = subprocess.Popen


@pytest.fixture(autouse=True)
def isolated_diagnostic_disable(monkeypatch):
    # Each test is an independent process-lifecycle scenario. Within a test,
    # repeated calls retain the production process-local disable behavior.
    monkeypatch.setattr(lifecycle_module, "_OBSERVER_DISABLED", threading.Event())


@pytest.fixture(scope="module")
def baseline():
    source = subprocess.check_output(["git", "show", f"{BASE}:core/codex_stage.py"], cwd=ROOT)
    assert hashlib.sha256(source).hexdigest() == BASE_SHA
    module = types.ModuleType("frozen_codex_stage")
    exec(compile(source, "frozen_codex_stage.py", "exec"), module.__dict__)
    return module


def recognizer(module, tmp_path, timeout=90):
    cli = tmp_path / "not-invoked-codex"
    cli.touch(exist_ok=True)
    template = tmp_path / "stage.txt"
    template.write_text("{instruction} {trigger_reason} {stage_descriptions} {keypoint_info}")
    return module.CodexStageRecognizer({
        "cli_path": str(cli), "disabled_skill_paths": ["/active/one"],
        "stage_template_path": str(template), "timeout_seconds": timeout,
    })


def stable_result(rec):
    result = dict(rec.last_result)
    result.pop("query_latency_s")
    result.pop("codex_call_latency_s")
    result["transport"] = dict(result["transport"])
    result["transport"].pop("lifecycle", None)
    return result


@pytest.mark.parametrize("scenario", [
    "success", "nonzero", "empty", "malformed", "multiple", "missing_usage",
    "unexpected_event", "unexpected_item", "timeout_empty", "timeout_started",
    "timeout_completed", "timeout_cleanup_completed", "spawn_error", "io_error",
    "oversize",
])
def test_frozen_outcomes_counters_and_invocation_are_identical(baseline, monkeypatch, tmp_path, scenario):
    outcomes, calls = [], []
    raw = b"\n".join(json.dumps(e).encode() for e in events())
    if scenario == "empty": raw = b""
    if scenario == "malformed": raw += b"\ninvalid"
    if scenario == "multiple": raw += b"\n" + raw
    if scenario == "missing_usage": raw = raw.replace(b'"input_tokens": 108', b'"input_tokens": null')
    if scenario == "unexpected_event": raw += b'\n{"type":"error","message":"SECRET"}'
    if scenario == "unexpected_item": raw += b'\n{"type":"item.completed","item":{"type":"SECRET"}}'
    if scenario == "timeout_empty": raw = b""
    if scenario in ("timeout_started", "timeout_cleanup_completed"):
        raw = b"\n".join(json.dumps(e).encode() for e in events()[:2])
    if scenario == "oversize": raw = b"x" * 129
    for mod in (baseline, current):
        stopped = []
        class Process:
            pid = 123456789
            returncode = None
            def __init__(self, command, **kwargs):
                if scenario == "spawn_error": raise OSError("SECRET")
                self.kwargs = kwargs
                self.command = command
                kwargs["stdout"].write(raw)
                kwargs["stdout"].flush()
            def communicate(self, input=None, timeout=None):
                calls.append((input, timeout, self.command, self.kwargs))
                if scenario.startswith("timeout"):
                    raise subprocess.TimeoutExpired("SECRET", timeout)
                if scenario == "io_error": raise OSError("SECRET")
                self.returncode = 7 if scenario == "nonzero" else 0
        def stop(process):
            stopped.append(process)
            if scenario == "timeout_cleanup_completed":
                process.kwargs["stdout"].write(b"\n" + b"\n".join(
                    json.dumps(e).encode() for e in events()[2:]))
                process.kwargs["stdout"].flush()
            process.returncode = -15
        monkeypatch.setattr(mod.subprocess, "Popen", Process)
        monkeypatch.setattr(mod, "_stop_owned_process", stop)
        if scenario == "oversize": monkeypatch.setattr(mod, "_MAX_EVENTS_BYTES", 128)
        rec = recognizer(mod, tmp_path)
        answer = identify(rec)
        snap = rec.api_request_counter.snapshot()
        snap.pop("call_latency_s")
        outcomes.append((answer, stable_result(rec), snap, len(stopped)))
    assert outcomes[0] == outcomes[1]
    if calls:
        assert calls[0][:2] == calls[1][:2]
        # Only existing per-call owned temporary paths differ.
        def normalized(call):
            directory = str(call[3]["cwd"])
            return [arg.replace(directory, "<temp>") for arg in call[2]]
        assert normalized(calls[0]) == normalized(calls[1])
        assert calls[0][3]["env"] == calls[1][3]["env"]
        assert all(c[3]["start_new_session"] is False and "shell" not in c[3] for c in calls)
    lc = rec.last_result["transport"]["lifecycle"]
    assert "SECRET" not in json.dumps(lc)
    assert not any(t.name == "codex-stage-lifecycle" for t in threading.enumerate())


@pytest.mark.parametrize("scenario", ["success", "nonzero", "timeout_started", "timeout_completed", "cleanup_completed"])
def test_real_children_order_timing_and_frozen_acceptance(baseline, monkeypatch, tmp_path, scenario):
    initial = "\n".join(json.dumps(e) for e in events()[:2]) + "\n"
    completion = "\n".join(json.dumps(e) for e in events()[2:]) + "\n"
    script = f"""
import os, signal, sys, time
sys.stdin.read()
sys.stderr.write('SECRET STDERR\\n'); sys.stderr.flush()
print({initial!r}, end='', flush=True)
def done(*unused):
    print({completion!r}, end='', flush=True)
    sys.exit(0)
if {scenario!r} == 'cleanup_completed':
    signal.signal(signal.SIGTERM, done)
    time.sleep(60)
elif {scenario!r} == 'timeout_started':
    time.sleep(60)
else:
    time.sleep(0.04)
    print({completion!r}, end='', flush=True)
    if {scenario!r} == 'timeout_completed': time.sleep(60)
    sys.exit(7 if {scenario!r} == 'nonzero' else 0)
"""
    outcomes, procs = [], []
    for mod in (baseline, current):
        def launch(command, **kwargs):
            proc = REAL_POPEN([sys.executable, "-u", "-c", script], **kwargs)
            procs.append(proc)
            return proc
        monkeypatch.setattr(mod.subprocess, "Popen", launch)
        rec = recognizer(mod, tmp_path, timeout=0.4)
        outcomes.append((identify(rec), stable_result(rec)))
    assert outcomes[0] == outcomes[1]
    assert all(p.returncode is not None for p in procs)
    lc = rec.last_result["transport"]["lifecycle"]
    assert lc["observation_complete"] is True
    assert lc["request_started_at"] <= lc["spawn_started_at"] <= lc["spawn_returned_at"] <= lc["communicate_started_at"]
    assert lc["first_byte_observed_at"] >= lc["spawn_returned_at"]
    assert lc["process_exit_observed_at"] <= lc["observer_finished_at"]
    assert lc["returncode"] == procs[-1].returncode
    assert "SECRET" not in json.dumps(lc)
    if scenario in ("success", "nonzero"):
        assert lc["timeout_observed_at"] is None and lc["cleanup_started_at"] is None
        assert lc["complete_usage_observed"] is True
    else:
        assert lc["timeout_observed_at"] <= lc["cleanup_started_at"] <= lc["cleanup_returned_at"]
        assert rec.last_result["error"] == "codex_timeout"
        if scenario == "timeout_started":
            assert lc["first_completed_observed_at"] is None
            assert lc["complete_usage_observed"] is False
        elif scenario == "timeout_completed":
            assert lc["first_completed_observed_at"] < lc["timeout_observed_at"]
        else:
            assert lc["first_completed_observed_at"] >= lc["cleanup_started_at"]


def test_observer_is_bounded_sanitized_and_does_not_change_file_offset(tmp_path):
    path = tmp_path / "events"
    event_list = [
        {"type": "SECRET", "secret": "SECRET"},
        {"type": ["SECRET"]}, {"type": "error", "message": "SECRET"},
        {"type": "turn.failed", "error": {"message": "SECRET"}},
        {"type": "item.updated", "item": {"type": "SECRET"}},
        {"type": "item.completed", "item": {"type": "error", "message": "SECRET"}},
        {"type": "turn.completed", "usage": {**USAGE, "input_tokens": True}},
    ]
    with path.open("w+b") as f:
        f.write(("\n".join(json.dumps(e) for e in event_list) + "\nnot-json").encode())
        f.flush()
        offset = f.tell()
        observer = StageLifecycle(100000)
        observer.start(f)
        observer.finish(None)
        assert f.tell() == offset
    assert "SECRET" not in json.dumps(observer.data)
    assert [e["kind"] for e in observer.data["events"]] == [
        "other", "other", "error", "turn.failed", "item.updated", "item.completed", "turn.completed", "invalid_json"]
    assert observer.data["complete_usage_observed"] is False
    with path.open("rb") as f:
        observer = StageLifecycle(10)
        observer.start(f)
        observer.finish(None)
    assert observer.data["observer_error_category"] == "observer_byte_limit"
    assert observer.data["observation_complete"] is False


def test_observer_read_failure_cannot_change_success(monkeypatch, tmp_path):
    from test_codex_stage import make
    rec, _ = make(monkeypatch, tmp_path)
    def fail(*args): raise OSError("SECRET")
    monkeypatch.setattr(lifecycle_module.os, "pread", fail)
    assert identify(rec) == (2, False)
    lc = rec.last_result["transport"]["lifecycle"]
    assert lc["observation_complete"] is False
    assert lc["observer_error_category"] == "observer_read_failure"
    assert "SECRET" not in json.dumps(lc)


def test_observer_start_failure_cannot_change_timeout_or_cost(monkeypatch, tmp_path):
    from test_codex_stage import make
    rec, _ = make(monkeypatch, tmp_path, timeout=True)
    monkeypatch.setattr(current, "_stop_owned_process", lambda p: None)
    def fail(*args): raise RuntimeError("SECRET")
    monkeypatch.setattr(lifecycle_module.threading.Thread, "start", fail)
    assert identify(rec) == (1, True)
    assert rec.last_result["error"] == "codex_timeout"
    assert rec.last_result["codex_completed_turns"] == 1
    assert rec.last_result["codex_usage_complete_calls"] == 1
    lc = rec.last_result["transport"]["lifecycle"]
    assert lc["observation_complete"] is False
    assert lc["observer_error_category"] == "observer_start_failure"
    assert lc["first_completed_observed_at"] is None
    assert "SECRET" not in json.dumps(lc)


def test_observer_finish_failure_is_sanitized_and_event_count_is_bounded(monkeypatch):
    observer = StageLifecycle(1000)
    monkeypatch.setattr(lifecycle_module, "_MAX_OBSERVATIONS", 2)
    for _ in range(3): observer._line(b'{"type":"thread.started"}', time.monotonic())
    assert len(observer.data["events"]) == 2
    assert observer.data["observer_error_category"] == "observer_event_limit"
    class BadReturnCode:
        @property
        def returncode(self): raise RuntimeError("SECRET")
    observer.finish(BadReturnCode())
    assert observer.data["observer_error_category"] == "observer_finish_failure"
    assert observer.data["observation_complete"] is False
    assert "SECRET" not in json.dumps(observer.data)


@pytest.mark.parametrize("fault", ["constructor", "after_spawn", "finish", "snapshot"])
def test_all_diagnostic_hook_failures_preserve_original_success_and_stop_worker(monkeypatch, tmp_path, fault):
    from test_codex_stage import make
    rec, calls = make(monkeypatch, tmp_path)
    original = current.StageLifecycle
    if fault == "constructor":
        def fail(*args): raise RuntimeError("SECRET")
        monkeypatch.setattr(current, "StageLifecycle", fail)
    else:
        class Faulty(original):
            def mark(self, name):
                if fault == "after_spawn" and name == "spawn_returned_at":
                    raise RuntimeError("SECRET")
                super().mark(name)
            def finish(self, process):
                if fault == "finish": raise RuntimeError("SECRET")
                super().finish(process)
            @property
            def data(self):
                if fault == "snapshot": raise RuntimeError("SECRET")
                return super().data
        monkeypatch.setattr(current, "StageLifecycle", Faulty)
    assert identify(rec) == (2, False)
    assert calls[0].prompt and calls[0].timeout == 90
    assert rec.last_result["codex_completed_turns"] == 1
    assert rec.last_result["codex_usage_complete_calls"] == 1
    assert rec.last_result["codex_failed_calls"] == 0
    lc = rec.last_result["transport"]["lifecycle"]
    assert lc["observation_complete"] is False
    assert "SECRET" not in json.dumps(lc)
    assert not any(t.name == "codex-stage-lifecycle" for t in threading.enumerate())


def test_blocked_observer_has_bounded_finish_stable_snapshot_and_disables_future_calls(monkeypatch, tmp_path):
    from test_codex_stage import make
    entered, release = threading.Event(), threading.Event()
    real_pread = os.pread
    seen = []
    def blocked(fd, *args):
        seen.append(fd)
        entered.set()
        assert release.wait(3)
        return real_pread(fd, *args)
    monkeypatch.setattr(lifecycle_module.os, "pread", blocked)
    rec, _ = make(monkeypatch, tmp_path)
    original_start = StageLifecycle.start
    def wait_for_read(self, f):
        original_start(self, f)
        if not lifecycle_module._OBSERVER_DISABLED.is_set():
            assert entered.wait(1)
    monkeypatch.setattr(StageLifecycle, "start", wait_for_read)
    try:
        start = time.monotonic()
        assert identify(rec) == (2, False)
        assert time.monotonic() - start < 1
        first = rec.last_result["transport"]["lifecycle"]
        frozen = json.dumps(first, sort_keys=True)
        assert first["observer_error_category"] == "observer_join_timeout"
        assert first["observation_complete"] is False
        assert lifecycle_module._OBSERVER_DISABLED.is_set()
        assert len(seen) == 1
        fd = seen[0]
        os.fstat(fd)  # Dedicated dup still owns the unlinked file, not a reused fd.
        assert identify(rec) == (2, False)
        assert rec.last_result["transport"]["lifecycle"]["observer_error_category"] == "prior_observer_timeout"
        assert rec.last_result["codex_failed_calls"] == 0
        assert rec.api_request_counter.snapshot()["logical_call_attempts"] == 2
        assert len(seen) == 1
    finally:
        release.set()
        for thread in threading.enumerate():
            if thread.name == "codex-stage-lifecycle": thread.join(timeout=2)
    assert len(seen) == 1  # No final/second read after the blocked read returns.
    assert json.dumps(first, sort_keys=True) == frozen
    with pytest.raises(OSError): os.fstat(fd)
    assert not any(t.name == "codex-stage-lifecycle" for t in threading.enumerate())


def test_real_timeout_keeps_group_cleans_descendant_and_leaves_foreign(monkeypatch, tmp_path):
    child_info = tmp_path / "child-info.json"
    script = f"""
import json, os, subprocess, sys, time
sys.stdin.read()
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
with open({str(child_info)!r}, 'w') as f: json.dump([child.pid, os.getpgrp()], f)
time.sleep(60)
"""
    foreign = REAL_POPEN([sys.executable, "-c", "import time; time.sleep(60)"])
    own = []
    def launch(command, **kwargs):
        p = REAL_POPEN([sys.executable, "-u", "-c", script], **kwargs)
        own.append(p)
        return p
    monkeypatch.setattr(current.subprocess, "Popen", launch)
    try:
        rec = recognizer(current, tmp_path, timeout=0.4)
        assert identify(rec) == (1, True)
        assert rec.last_result["error"] == "codex_timeout"
        child_pid, group = json.loads(child_info.read_text())
        assert group == os.getpgrp()
        assert own[0].returncode is not None
        assert foreign.poll() is None
        try:
            child = current.psutil.Process(child_pid)
            assert not child.is_running() or child.status() == current.psutil.STATUS_ZOMBIE
        except current.psutil.NoSuchProcess:
            pass
        assert not any(t.name == "codex-stage-lifecycle" for t in threading.enumerate())
    finally:
        foreign.terminate()
        foreign.wait(timeout=3)
        for p in own:
            if p.poll() is None:
                p.kill()
                p.wait(timeout=3)
