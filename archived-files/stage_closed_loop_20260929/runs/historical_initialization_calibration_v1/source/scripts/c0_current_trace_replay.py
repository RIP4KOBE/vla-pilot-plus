#!/usr/bin/env python3
"""Prepared current-source C0 trace comparison; dispatch needs budget approval."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import yaml

from c0_trace_replay import (
    ARTIFACT, CACHE, ORIGINAL_JOB, PYTHON, SEEDS, STUDY, TRACE, atomic_json,
    command as historical_command, digest, episode_started, gpu_idle,
    process_env, utc,
)

OUTPUT = ARTIFACT / "outputs/current"
MANIFEST = ARTIFACT / "current-manifest-v2.json"
APPROVAL = ARTIFACT / "current-budget-approval.json"
MAX_SECONDS = 9 * 3600


def command() -> list[str]:
    args = historical_command()
    replace = {
        "hydra.run.dir": str(OUTPUT),
        "main.eds_eval.output_dir": str(OUTPUT / "eds_eval"),
    }
    result = args[:2]
    for item in args[2:]:
        key, sep, value = item.partition("=")
        if key == "+perception.gemini.backend":
            key = "perception.gemini.backend"
        result.append(key + "=" + replace.get(key, value) if sep else item)
    result += [
        "+main.stage_min_query_gap_steps=0",
        "main.eds_config.qd_degenerate_fallback_policy=none",
        "main.eds_config.qd_secondary_lane_mode=none",
        "main.eds_config.qd_global_quality_anchor_count=0",
        "main.eds_config.qd_bounds_update_policy=fixed_initial",
    ]
    return result


def prepare() -> dict:
    old = json.loads((ARTIFACT / "outputs/legacy/audit.json").read_text())
    if not old["valid_full_replay"] or old["success_task_ids"] != [3, 8, 9]:
        raise RuntimeError("Historical-source Stage replay has not passed")
    if digest(STUDY / "core/trace_replay_stage.py") != digest(
            Path("/home/hynx/VLA-Pilot++/.worktrees/exp/eds-quality-diversity/core/trace_replay_stage.py")):
        raise RuntimeError("Stage replay adapters differ between source trees")
    if not TRACE.is_file() or not CACHE.is_dir() or not ORIGINAL_JOB.is_file():
        raise RuntimeError("Historical C0 inputs unavailable")
    data = {
        "schema": "c0-current-trace-replay-v2",
        "purpose": "Deterministic current-source comparison against the exact historical C0 trajectory",
        "current_source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=STUDY, text=True).strip(),
        "current_source_sha256": {name: digest(STUDY / name) for name in (
            "main.py", "core/gemini_grounder.py", "core/trace_replay_stage.py",
            "core/rdt_policy_steer.py")},
        "historical_trace_sha256": digest(TRACE),
        "original_manifest_sha256": digest(ORIGINAL_JOB),
        "cache_sha256": {p.name: digest(p) for p in sorted(CACHE.iterdir()) if p.is_file()},
        "argv": command(), "cwd": str(STUDY), "physical_gpu": 2,
        "egl_device_index": 1, "episode_seeds": SEEDS,
        "required_approved_attempt_cap": 258,
        "gpu_hour_cap_unchanged": 48.0,
        "protected_validation_formal_attempts_unchanged": 100,
        "protected_validation_formal_gpu_hours_unchanged": 24.0,
        "max_process_seconds": MAX_SECONDS,
    }
    if MANIFEST.exists():
        if json.loads(MANIFEST.read_text()) != data:
            raise RuntimeError("Frozen current-source replay manifest differs")
    else:
        atomic_json(MANIFEST, data)
    return data


def audit() -> dict:
    old = [json.loads(x) for x in TRACE.read_text().splitlines() if x.strip()]
    event_path = OUTPUT / "eds_eval/stage_events.jsonl"
    rows = [json.loads(x) for x in event_path.read_text().splitlines() if x.strip()] if event_path.exists() else []
    keys = ("episode_id", "task_id", "episode_seed", "global_step", "chunk_id",
            "trigger_reason", "stage_before", "stage_after", "guidance_before",
            "guidance_after", "query_status", "query_ok", "raw_response",
            "parsed_stage", "parsed_guidance", "error")
    mismatch = None
    for i, (a, b) in enumerate(zip(old, rows)):
        delta = {key: [a.get(key), b.get(key)] for key in keys if a.get(key) != b.get(key)}
        if delta:
            mismatch = {"event_index": i, "differences": delta}
            break
    metadata_path = OUTPUT / "eds_eval/episode_metadata.jsonl"
    metadata = [json.loads(x) for x in metadata_path.read_text().splitlines() if x.strip()] if metadata_path.exists() else []
    videos = []
    success = []
    video_equal = []
    particle_equal = []
    for i in range(10):
        current = list((OUTPUT / f"episode_{i + 1}").glob("*agentview.mp4"))
        reference = list((ORIGINAL_JOB.parent / f"episode_{i + 1}").glob("*agentview.mp4"))
        videos.append(len(current))
        if any("success" in p.name for p in current):
            success.append(i)
        video_equal.append(len(current) == len(reference) == 1 and
                           current[0].name == reference[0].name and
                           digest(current[0]) == digest(reference[0]))
        rel = (f"eds_eval/qualitative/episode_{i:03d}/chunk_000000/"
               "single_step_inner_loop/single_step_particles.csv")
        a, b = OUTPUT / rel, ORIGINAL_JOB.parent / rel
        particle_equal.append(a.is_file() and b.is_file() and digest(a) == digest(b))
    status_path = OUTPUT / "status.json"
    status = json.loads(status_path.read_text()) if status_path.exists() else {}
    results_path = OUTPUT / "results.txt"
    match = re.search(r"Success count:\s*(\d+)/10", results_path.read_text()) if results_path.exists() else None
    valid = (status.get("exit_code") == 0 and len(rows) == len(old) and mismatch is None
             and len(metadata) == 10 and videos == [1] * 10
             and all(video_equal) and all(particle_equal) and success == [3, 8, 9]
             and [(x["task_id"], x["episode_seed"]) for x in metadata] == list(enumerate(SEEDS))
             and match is not None and int(match.group(1)) == len(success))
    report = {"audited_utc": utc(), "valid_full_replay": valid,
              "historical_events": len(old), "current_events": len(rows),
              "first_event_mismatch": mismatch, "metadata_rows": len(metadata),
              "videos_per_episode": videos, "video_sha256_equal_by_task": video_equal,
              "first_particle_sha256_equal_by_task": particle_equal,
              "success_task_ids": success, "success_count": len(success),
              "reported_success_count": int(match.group(1)) if match else None,
              "status": status}
    atomic_json(OUTPUT / "audit.json", report)
    return report


def run() -> None:
    prepare()
    if not APPROVAL.is_file():
        raise RuntimeError("Current C0 replay requires the proposed cap increase approval")
    approval = json.loads(APPROVAL.read_text())
    if approval.get("approved_global_attempt_cap") != 258 or approval.get("approved_by_user") is not True:
        raise RuntimeError("Current C0 replay budget approval is insufficient")
    if (approval.get("plan_sha256") != digest(STUDY / approval["plan"]) or
            approval.get("frozen_manifest_sha256") != digest(MANIFEST)):
        raise RuntimeError("Approved plan or frozen manifest hash differs")
    state = yaml.safe_load((STUDY / "research-state.yaml").read_text())
    budget = state["budget"]
    if (budget["max_episode_attempts"] != 258 or budget["max_gpu_hours"] != 48.0 or
            budget["reserved"]["validation"] != 60 or
            budget["reserved"]["formal"] != 40 or
            budget["gpu_hour_reservations"]["validation"] != 14.0 or
            budget["gpu_hour_reservations"]["formal"] != 10.0 or
            state["resource_isolation"]["status"] != "ACTIVE" or
            state["resource_isolation"]["validation_status"] != "PASS"):
        raise RuntimeError("Owned study budget/isolation differs from approved amendment")
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise RuntimeError("Output already exists; no overwrite")
    if not gpu_idle():
        raise RuntimeError("Physical GPU2 is not idle")
    with (STUDY / "data/qd-ed-runner.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        OUTPUT.mkdir(parents=True)
        atomic_json(OUTPUT / "dispatch.json", {"argv": command(), "utc": utc(),
                    "manifest_sha256": digest(MANIFEST), "approval_sha256": digest(APPROVAL)})
        start = time.monotonic()
        last_count = 0
        last_progress = start
        with (OUTPUT / "console.log").open("w") as logfile:
            proc = subprocess.Popen(command(), cwd=STUDY, env=process_env(),
                                    stdout=logfile, stderr=subprocess.STDOUT,
                                    start_new_session=True)
            try:
                while proc.poll() is None:
                    count = episode_started(OUTPUT)
                    if count > last_count:
                        last_count = count
                        last_progress = time.monotonic()
                        print(f"{utc()} current-source replay started {count}/10", flush=True)
                    atomic_json(OUTPUT / "status.json", {"status": "running", "pid": proc.pid,
                                "utc": utc(), "episode_started": count,
                                "elapsed_seconds": time.monotonic() - start})
                    if time.monotonic() - start > MAX_SECONDS or time.monotonic() - last_progress > 3600:
                        os.killpg(proc.pid, signal.SIGTERM)
                        proc.wait(timeout=15)
                        raise RuntimeError("Budget or per-episode watchdog exceeded")
                    time.sleep(15)
            finally:
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGTERM)
                    proc.wait(timeout=15)
        atomic_json(OUTPUT / "status.json", {"status": "exited", "pid": proc.pid,
                    "exit_code": proc.returncode, "utc": utc(),
                    "episode_started": episode_started(OUTPUT),
                    "elapsed_seconds": time.monotonic() - start})
        report = audit()
        print(json.dumps(report, indent=2), flush=True)
        if proc.returncode != 0 or not report["valid_full_replay"]:
            raise RuntimeError("Current-source replay diverged; inspect audit and console")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "command", "run", "audit"))
    args = parser.parse_args()
    if args.action == "prepare":
        print(json.dumps(prepare(), indent=2))
    elif args.action == "command":
        print(json.dumps(command(), indent=2))
    elif args.action == "audit":
        print(json.dumps(audit(), indent=2))
    else:
        run()


if __name__ == "__main__":
    main()
