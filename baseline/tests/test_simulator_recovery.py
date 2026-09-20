import copy
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from baseline.io import read_json, write_json
from baseline import rl_recovery as recovery
from baseline.simulator_startup import ACTIVITY_PATH, failure_details, monitor_startup, startup_deadline


def wrapped_timeout():
    try:
        raise TimeoutError("baseline LIBERO initialization exceeded 600s")
    except TimeoutError:
        try:
            raise ValueError("Current sensor for observable agentview_image is invalid.") from None
        except ValueError as exc:
            return exc


def job():
    return {"owner": "continual_vla_rl", "phase": "train", "suffix": "stage_015", "name": "run",
            "pid": 12345, "gpu_index": 5, "gpu_uuid": "GPU-test", "command": ["python", "-m", "baseline"],
            "process_start_ticks": 42}


def activity(pid, **updates):
    return {"pid": pid, "operation": "initialize", "state": "running", "started_at": 100,
            "timeout_seconds": 600, **updates}


def test_wrapped_timeout_retains_cause_but_other_sensor_and_numeric_errors_do_not_retry():
    details = failure_details(wrapped_timeout())
    assert details["retryable_infrastructure_failure"] == recovery.TIMEOUT
    assert [e["error_type"] for e in details["error_chain"]] == ["ValueError", "TimeoutError"]
    for exc in (ValueError("Current sensor for observable agentview_image is invalid."),
                TimeoutError("another timeout"), FloatingPointError("non-finite loss")):
        assert failure_details(exc)["retryable_infrastructure_failure"] is None


def test_activity_records_only_bounded_scopes_and_restores_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv(ACTIVITY_PATH, "prior-scope")
    with monitor_startup(tmp_path):
        with pytest.raises(ValueError):
            with startup_deadline(600, operation="reset"):
                current = read_json(tmp_path / "simulator_activity.json")
                assert current["state"] == "running" and current["pid"] == os.getpid()
                assert current["operation"] == "reset"
                raise wrapped_timeout()
        result = read_json(tmp_path / "simulator_activity.json")
        assert result["state"] == "failed"
        assert result["retryable_infrastructure_failure"] == recovery.TIMEOUT
    assert os.environ[ACTIVITY_PATH] == "prior-scope"


def test_cli_publishes_timeout_cause_even_when_constructor_raises(tmp_path):
    from baseline.cli import _run_command
    def fail(_):
        raise wrapped_timeout()
    with pytest.raises(ValueError):
        _run_command(SimpleNamespace(command="train"), {}, None, tmp_path, fail)
    result = read_json(tmp_path / "status.json")
    assert result["status"] == "failed"
    assert result["retryable_infrastructure_failure"] == recovery.TIMEOUT


def test_watchdog_requires_expired_owned_startup_not_general_training_inactivity(tmp_path):
    work = job()
    marker = tmp_path / "simulator_activity.json"
    for data in (activity(work["pid"], state="complete"), activity(999),
                 activity(work["pid"], operation="grpo_update"), activity(work["pid"], started_at=900)):
        write_json(marker, data)
        assert recovery.timeout_failure(work, tmp_path, now=1000) is None
    write_json(marker, activity(work["pid"]))
    assert recovery.timeout_failure(work, tmp_path, now=820) is None
    assert recovery.timeout_failure(work, tmp_path, now=821)["source"] == "external_startup_watchdog"
    assert recovery.timeout_failure({**work, "owner": "rl2_vla"}, tmp_path, now=1000) is None


def test_watchdog_checks_gpu_and_process_birth_before_any_signal(tmp_path, monkeypatch):
    work = job()
    write_json(tmp_path / "simulator_activity.json", activity(work["pid"]))
    signals = []
    monkeypatch.setattr(recovery.os, "kill", lambda *args: signals.append(args))
    monkeypatch.setattr(recovery, "verified_worker", lambda _: {"start_ticks": 43})
    with pytest.raises(RuntimeError, match="protected GPU"):
        recovery.stop_timed_out_worker({**work, "gpu_index": 6}, tmp_path, [], now=1000)
    with pytest.raises(RuntimeError, match="protected GPU"):
        recovery.stop_timed_out_worker(work, tmp_path, [5], now=1000)
    with pytest.raises(RuntimeError, match="PID was reused"):
        recovery.stop_timed_out_worker(work, tmp_path, [6], now=1000)
    assert not signals
    monkeypatch.setattr(recovery, "verified_worker", lambda _: {"start_ticks": 42})
    assert recovery.stop_timed_out_worker(work, tmp_path, [6], now=1000)
    assert not recovery.stop_timed_out_worker(work, tmp_path, [6], now=1001)
    assert recovery.stop_timed_out_worker(work, tmp_path, [6], now=1030)
    assert not recovery.stop_timed_out_worker(work, tmp_path, [6], now=1100)
    assert signals == [(work["pid"], signal.SIGTERM), (work["pid"], signal.SIGKILL)]


def test_retry_restores_committed_group_and_bounds_repeated_failures(tmp_path):
    work = job()
    output = tmp_path / work["name"]; output.mkdir()
    write_json(output / "status.json", {"status": "failed", **failure_details(wrapped_timeout())})
    checkpoint = output / "continual_optimizer_checkpoint.pt"
    checkpoint.write_bytes(b"atomic-checkpoint-fixture")
    info = checkpoint.stat()
    progress = {"task_key": "task16", "groups_completed": 31,
                "checkpoint_size": info.st_size, "checkpoint_mtime_ns": info.st_mtime_ns}
    write_json(checkpoint.with_suffix(".progress.json"), progress)
    item = {"state": "FAILED", "tasks_completed": 15, "current_task": "task16", "error": "exit 1"}
    state = {"methods": {work["owner"]: item}}
    for attempt in range(1, 5):
        item.update(state="FAILED", error="exit 1")
        assert recovery.retry_failed_startup(state, work, tmp_path) == (attempt <= 3)
        assert item["simulator_recovery"]["retries_without_progress"] == attempt
    assert item["state"] == "FAILED"
    assert "exhausted" in item["error"]
    assert item["tasks_completed"] == 15 and item["optimizer_resume"] == str(checkpoint)
    write_json(checkpoint.with_suffix(".progress.json"), {**progress, "groups_completed": 32})
    assert recovery.retry_failed_startup(state, work, tmp_path)
    assert item["simulator_recovery"]["retries_without_progress"] == 1
    # A sidecar from a different checkpoint must not authorize recovery.
    checkpoint.write_bytes(b"changed")
    item.update(state="FAILED", error="exit 1")
    assert not recovery.retry_failed_startup(state, work, tmp_path)


def test_selective_resume_keeps_retired_and_completed_methods_unchanged():
    state = {"methods": {"clare": {"state": "FAILED", "error": "retired"},
                         "mlr_ifa": {"state": "COMPLETE"}, "rl2_vla": {"state": "RUNNING"},
                         "continual_vla_rl": {"state": "FAILED", "tasks_completed": 15, "error": "timeout"}}}
    before = copy.deepcopy(state)
    recovery.prepare_resume(state, {"rl2_vla"}, ["continual_vla_rl"])
    for owner in ("clare", "mlr_ifa", "rl2_vla"):
        assert state["methods"][owner] == before["methods"][owner]
    assert state["methods"]["continual_vla_rl"] == {"state": "QUEUED", "tasks_completed": 15}


@pytest.mark.skipif(not Path("/proc/self/stat").exists(), reason="Linux worker identity uses /proc")
def test_real_stuck_child_is_killed_without_signaling_its_parent(tmp_path):
    # Simulate a native render call that ignores Python's soft timeout and TERM.
    code = '''import json,os,signal,sys,time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
with open(sys.argv[1], "w") as f:
 json.dump(dict(pid=os.getpid(), operation="initialize", state="running", started_at=0, timeout_seconds=600), f)
while True: time.sleep(1)
'''
    marker = tmp_path / "simulator_activity.json"
    command = [sys.executable, "-u", "-c", code, str(marker)]
    child = subprocess.Popen(command, env={**os.environ, "CUDA_VISIBLE_DEVICES": "GPU-test"}, start_new_session=True)
    try:
        deadline = time.monotonic() + 10
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(.02)
        assert marker.exists()
        work = {**job(), "pid": child.pid, "command": command}
        work["process_start_ticks"] = recovery.verified_worker(work)["start_ticks"]
        assert recovery.stop_timed_out_worker(work, tmp_path, [6], now=1000)
        assert child.poll() is None
        assert recovery.stop_timed_out_worker(work, tmp_path, [6], now=1031)
        assert child.wait(timeout=10) == -signal.SIGKILL
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
