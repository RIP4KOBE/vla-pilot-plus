#!/usr/bin/env python3
"""Budget-gated GPU2 replay to capture exact historical C0 Stage inputs."""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import time

import yaml

from c0_current_trace_replay import atomic_json, episode_started, gpu_idle, utc
from c0_stage_input_capture_audit import audit
from c0_stage_input_capture_preflight import (
    CAPTURE, MANIFEST, OUTPUT, ROOT, STUDY, command, digest,
)
from c0_trace_replay import process_env


APPROVAL = ROOT / "authorization.json"
MAX_SECONDS = 3600
MAX_STALL_SECONDS = 1200


def attempts_started() -> int:
    """Charge started episodes, including one that failed before metadata flush."""
    folders = sum(path.is_dir() for path in OUTPUT.glob("episode_*")) if OUTPUT.is_dir() else 0
    return max(folders, episode_started(OUTPUT))


def admission() -> dict:
    if not MANIFEST.is_file() or not APPROVAL.is_file():
        raise RuntimeError("Capture requires frozen preflight and a user budget authorization")
    manifest = json.loads(MANIFEST.read_text())
    approval = json.loads(APPROVAL.read_text())
    if (approval.get("approved_by_user") is not True or
            approval.get("approved_total_attempt_cap") != 298 or
            approval.get("maximum_new_diagnostic_episodes") != 40 or
            approval.get("protected_validation_formal_attempts_unchanged") != 100 or
            approval.get("protected_validation_formal_gpu_hours_unchanged") != 24.0 or
            approval.get("manifest_sha256") != digest(MANIFEST)):
        raise RuntimeError("Capture approval does not match the frozen proposed budget")
    proposal = STUDY / approval.get("proposal_path", "")
    if not proposal.is_file() or approval.get("proposal_sha256") != digest(proposal):
        raise RuntimeError("Approved budget proposal has changed")
    if manifest.get("argv") != command() or manifest.get("physical_gpu") != 2:
        raise RuntimeError("Capture command differs from frozen preflight")
    if any(digest(STUDY / name) != value for name, value in manifest["source_sha256"].items()):
        raise RuntimeError("Capture source differs from frozen preflight")
    state = yaml.safe_load((STUDY / "research-state.yaml").read_text())
    budget = state["budget"]
    if (budget.get("max_episode_attempts") != 298 or budget.get("max_gpu_hours") != 48.0
            or budget.get("reserved", {}).get("validation") != 60
            or budget.get("reserved", {}).get("formal") != 40
            or budget.get("gpu_hour_reservations", {}).get("validation") != 14.0
            or budget.get("gpu_hour_reservations", {}).get("formal") != 10.0
            or state.get("resource_isolation", {}).get("status") != "ACTIVE"
            or state.get("resource_isolation", {}).get("validation_status") != "PASS"):
        raise RuntimeError("GPU2 study budget/isolation differs from approved amendment")
    previous = budget.get("current_c0_trace_replay_approval_20260928", {})
    used = previous.get("effective_dispatched_after_run")
    used_gpu_hours = previous.get("effective_gpu_hours_consumed_upper_bound_after_run")
    if (used != 158 or used_gpu_hours is None or
            budget["max_episode_attempts"] - used - 100 < 10 or
            budget["max_gpu_hours"] - float(used_gpu_hours) - 24.0 < 1.0):
        raise RuntimeError("Insufficient unprotected GPU2 budget for ten-episode capture")
    if OUTPUT.exists() or CAPTURE.exists():
        raise RuntimeError("Capture output already exists; no overwrite")
    if not gpu_idle():
        raise RuntimeError("Physical GPU2 is not idle")
    return {"manifest": manifest, "approval": approval}


def run() -> None:
    checked = admission()
    with (STUDY / "data/qd-ed-runner.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        admission()
        OUTPUT.mkdir(parents=True)
        atomic_json(OUTPUT / "dispatch.json", {
            "utc": utc(), "argv": command(),
            "manifest_sha256": digest(MANIFEST),
            "approval_sha256": digest(APPROVAL),
            "physical_gpu": 2,
        })
        start = time.monotonic()
        last_count = 0
        last_progress = start
        proc = None
        try:
            with (OUTPUT / "console.log").open("w") as logfile:
                proc = subprocess.Popen(command(), cwd=STUDY, env=process_env(),
                                        stdout=logfile, stderr=subprocess.STDOUT,
                                        start_new_session=True)
                while proc.poll() is None:
                    count = attempts_started()
                    if count > 10:
                        raise RuntimeError("Capture exceeded ten started episodes")
                    if count > last_count:
                        last_count, last_progress = count, time.monotonic()
                        print(f"{utc()} Stage capture started {count}/10", flush=True)
                    atomic_json(OUTPUT / "status.json", {
                        "status": "running", "utc": utc(), "pid": proc.pid,
                        "episode_started": count,
                        "elapsed_seconds": time.monotonic() - start,
                    })
                    if time.monotonic() - start > MAX_SECONDS or time.monotonic() - last_progress > MAX_STALL_SECONDS:
                        raise RuntimeError("Capture time or progress watchdog exceeded")
                    time.sleep(10)
        finally:
            if proc is not None and proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=15)
            elapsed = time.monotonic() - start
            atomic_json(OUTPUT / "status.json", {
                "status": "exited", "utc": utc(),
                "pid": proc.pid if proc is not None else None,
                "exit_code": proc.returncode if proc is not None else None,
                "episode_started": attempts_started(),
                "elapsed_seconds": elapsed,
            })
            atomic_json(OUTPUT / "budget-charge.json", {
                "schema": "c0-stage-capture-charge-v1",
                "approved_total_attempt_cap": checked["approval"]["approved_total_attempt_cap"],
                "primary_episodes_started": attempts_started(),
                "gpu_hours_upper_bound": elapsed / 3600.0,
                "audit_valid": False,
            })
        result = audit()
        atomic_json(OUTPUT / "budget-charge.json", {
            "schema": "c0-stage-capture-charge-v1",
            "approved_total_attempt_cap": checked["approval"]["approved_total_attempt_cap"],
            "primary_episodes_started": attempts_started(),
            "gpu_hours_upper_bound": elapsed / 3600.0,
            "audit_valid": result["valid"],
        })
        print(json.dumps(result, indent=2), flush=True)
        if proc.returncode != 0 or not result["valid"]:
            raise RuntimeError("Stage capture replay diverged; preserve evidence and stop")


if __name__ == "__main__":
    run()
