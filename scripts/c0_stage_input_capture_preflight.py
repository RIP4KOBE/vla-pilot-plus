#!/usr/bin/env python3
"""Freeze the proposed GPU2 C0 replay that captures exact Stage request inputs.

This script only prepares and checks a command. It never dispatches episodes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from c0_current_trace_replay import command as current_replay_command
from c0_trace_replay import CACHE, ORIGINAL_JOB, SEEDS, STUDY, TRACE, process_env

ROOT = STUDY / "artifacts/c0_online_stage_diagnostic_20260928"
OUTPUT = ROOT / "outputs/capture_replay"
CAPTURE = ROOT / "captured_stage_inputs"
MANIFEST = STUDY / "docs/03_evidence/c0_online_stage_diagnostic/capture-preflight-v2-20260928.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command() -> list[str]:
    result = []
    replaced = set()
    mapping = {
        "hydra.run.dir": str(OUTPUT),
        "main.eds_eval.output_dir": str(OUTPUT / "eds_eval"),
        "perception.gemini.backend": "trace_replay_capture",
    }
    for item in current_replay_command():
        key, sep, value = item.partition("=")
        if sep and key in mapping:
            result.append(key + "=" + mapping[key])
            replaced.add(key)
        else:
            result.append(item)
    if replaced != set(mapping):
        raise RuntimeError(f"Missing required C0 overrides: {set(mapping) - replaced}")
    result.append("+perception.gemini.capture_dir=" + str(CAPTURE))
    return result


def preflight() -> dict:
    if OUTPUT.exists() or CAPTURE.exists():
        raise RuntimeError("Capture output already exists; never overwrite")
    prior = json.loads((STUDY / "artifacts/c0_trace_replay_20260925/outputs/current/audit.json").read_text())
    if not prior.get("valid_full_replay") or prior.get("success_task_ids") != [3, 8, 9]:
        raise RuntimeError("Current-source C0 historical replay has not passed")
    if not all(path.is_file() for path in (TRACE, ORIGINAL_JOB, CACHE / "output_raw.txt")):
        raise RuntimeError("Historical C0 inputs are missing")
    source = {
        name: digest(STUDY / name) for name in (
            "main.py", "core/gemini_grounder.py", "core/trace_replay_stage.py",
            "core/stage_capture_trace_replay.py", "core/rdt_policy_steer.py",
        )
    }
    data = {
        "schema": "c0-stage-input-capture-preflight-v2",
        "status": "READY_FOR_BUDGET_REVIEW_NO_GPU_DISPATCH",
        "purpose": "Capture exact Stage inputs on the historically matched C0 trajectory",
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=STUDY, text=True).strip(),
        "source_sha256": source,
        "historical_trace_sha256": digest(TRACE),
        "original_job_sha256": digest(ORIGINAL_JOB),
        "cache_sha256": {path.name: digest(path) for path in sorted(CACHE.iterdir()) if path.is_file()},
        "argv": command(), "cwd": str(STUDY),
        "physical_gpu": 2, "egl_device_index": 1,
        "episode_seeds": SEEDS, "maximum_episodes": 10,
        "capture_dir": str(CAPTURE), "output_dir": str(OUTPUT),
        "observed_prior_replay_gpu_hours": 0.2708537829358344,
        "current_unprotected_episode_balance": 0,
        "dispatch_authorized": False,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    if MANIFEST.exists() and json.loads(MANIFEST.read_text()) != data:
        raise RuntimeError("Frozen capture preflight differs; preserve old version")
    MANIFEST.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return data


def hydra_check() -> None:
    args = command() + ["--cfg", "job"]
    proc = subprocess.run(args, cwd=STUDY, env=process_env(),
                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                          text=True, timeout=120, check=False)
    if proc.returncode != 0:
        raise RuntimeError("Hydra capture config failed: " + proc.stderr[-1000:])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("command", "preflight"))
    args = parser.parse_args()
    if args.action == "command":
        print(json.dumps(command(), indent=2))
    else:
        hydra_check()
        print(json.dumps(preflight(), indent=2))


if __name__ == "__main__":
    main()
