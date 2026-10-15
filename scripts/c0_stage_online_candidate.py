#!/usr/bin/env python3
"""Run one frozen current-source C0 Codex Stage condition on physical GPU2."""

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

from c0_current_trace_replay import command as replay_command
from c0_stage_input_capture_preflight import ROOT, STUDY, digest
from c0_stage_offline_diagnostic import CONDITIONS, OUT as OFFLINE
from c0_stage_prompt_probe import NAME as PROMPT_CONDITION, NEW_TEMPLATE
from c0_trace_replay import SEEDS, atomic_json, gpu_idle, process_env, utc


MAX_SECONDS = 6 * 3600
MAX_STALL_SECONDS = 45 * 60
ONLINE_CONDITIONS = {**CONDITIONS, PROMPT_CONDITION: (
    "json_schema_v1", "low", "completed_transport_cycles_v6")}
SOURCE_FILES = (
    "main.py", "core/gemini_grounder.py", "core/codex_stage.py",
    "core/codex_stage_policy.py", "core/rdt_policy_steer.py",
    "vlm_query/stage_template.txt",
    "vlm_query/stage_template_codex_guidance_persistence_v1.txt",
)


def run_label(condition: str, replicate: int, attempt: int = 1) -> str:
    if attempt < 1:
        raise ValueError("Online attempt must be positive")
    base = f"online_{condition}_replicate{replicate}"
    return base if attempt == 1 else f"{base}_attempt{attempt}"


def output_path(condition: str, replicate: int, attempt: int = 1) -> Path:
    return ROOT / "outputs" / run_label(condition, replicate, attempt)


def command(condition: str, replicate: int, attempt: int = 1) -> list[str]:
    if condition not in ONLINE_CONDITIONS or replicate not in (1, 2):
        raise ValueError("Unregistered C0 Stage condition or replicate")
    output = output_path(condition, replicate, attempt)
    fmt, effort, event_policy = ONLINE_CONDITIONS[condition]
    substitutions = {
        "hydra.run.dir": str(output),
        "main.eds_eval.output_dir": str(output / "eds_eval"),
        "perception.gemini.backend": "codex_cli",
    }
    args = []
    removed = 0
    replaced = set()
    for item in replay_command():
        key, sep, value = item.partition("=")
        if key == "+perception.gemini.replay_trace_path":
            removed += 1
            continue
        if sep and key in substitutions:
            args.append(key + "=" + substitutions[key])
            replaced.add(key)
        else:
            args.append(item)
    if removed != 1 or replaced != set(substitutions):
        raise RuntimeError("Frozen replay command no longer has expected Stage overrides")
    args.extend([
        "perception.gemini.model=gpt-6-astra",
        "perception.gemini.reasoning_effort=" + effort,
        "perception.gemini.timeout_seconds=180",
        "perception.gemini.output_format=" + fmt,
        "perception.gemini.event_policy=" + event_policy,
        "+perception.gemini.capture_dir=" + str(output / "captured_stage_inputs"),
        "+perception.gemini.transport_retry_count=12",
        "+perception.gemini.transport_retry_backoff_seconds=2",
    ])
    if condition == PROMPT_CONDITION:
        args.append("+perception.gemini.stage_template_path=" + str(NEW_TEMPLATE))
    return args


def selected_condition() -> str:
    selection = OFFLINE / "selection.json"
    if not selection.is_file():
        raise RuntimeError("Offline evidence has not selected a single Stage condition")
    data = json.loads(selection.read_text())
    name = data.get("condition")
    if name not in ONLINE_CONDITIONS:
        raise RuntimeError("Offline selection names an unknown Stage condition")
    if data.get("summary_sha256") != digest(OFFLINE / "screening-summary.json"):
        raise RuntimeError("Offline selection no longer matches frozen summary")
    if name == PROMPT_CONDITION:
        probe = OFFLINE.parent / "offline_prompt_probe"
        if data.get("prompt_probe_summary_sha256") != digest(probe / "summary.json"):
            raise RuntimeError("Prompt probe summary differs from frozen selection")
        coverage_file = probe / "extension-coverage.json"
        coverage = json.loads(coverage_file.read_text()) if coverage_file.exists() else {}
        if coverage.get("extension_valid_inputs") != 103 or coverage.get("extension_target_inputs") != 103:
            raise RuntimeError("Prompt probe has not covered all remaining historical Stage inputs")
    return name


def attempts_started(output: Path) -> int:
    directories = sum(path.is_dir() for path in output.glob("episode_*")) if output.is_dir() else 0
    metadata = output / "eds_eval/episode_metadata.jsonl"
    rows = sum(bool(line.strip()) for line in metadata.open()) if metadata.exists() else 0
    return max(directories, rows)


def stage_errors_seen(output: Path) -> int:
    path = output / "eds_eval/stage_events.jsonl"
    if not path.is_file():
        return 0
    count = 0
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue  # A writer may still be completing the final line.
        if row.get("query_status") == "error":
            count += 1
    return count


def prepare(condition: str, replicate: int, attempt: int = 1) -> dict:
    if selected_condition() != condition:
        raise RuntimeError("Requested condition differs from offline selection")
    if replicate == 2:
        previous = list((ROOT / "outputs").glob(
            f"online_{condition}_replicate1*/online-audit.json"))
        if not any((lambda result: result.get("valid") is True and
                    result.get("success_count", 0) >= 3)(json.loads(path.read_text()))
                   for path in previous):
            raise RuntimeError("First replicate did not pass the 3/10 advancement gate")
    output = output_path(condition, replicate, attempt)
    manifest = output.parent / f"{run_label(condition, replicate, attempt)}_manifest.json"
    data = {
        "schema": "c0-stage-online-candidate-v1",
        "condition": condition, "replicate": replicate, "attempt": attempt,
        "physical_gpu": 2, "egl_device_index": 1,
        "episode_seeds": SEEDS, "maximum_episodes": 10,
        "model": "gpt-6-astra", "output_format": ONLINE_CONDITIONS[condition][0],
        "reasoning_effort": ONLINE_CONDITIONS[condition][1],
        "event_policy": ONLINE_CONDITIONS[condition][2],
        "offline_selection_sha256": digest(OFFLINE / "selection.json"),
        "source_sha256": {name: digest(STUDY / name) for name in SOURCE_FILES},
        "argv": command(condition, replicate, attempt),
        "cwd": str(STUDY), "output": str(output),
        "max_seconds": MAX_SECONDS,
    }
    if manifest.exists():
        if json.loads(manifest.read_text()) != data:
            raise RuntimeError("Frozen online manifest differs from current inputs")
    else:
        atomic_json(manifest, data)
    probe = subprocess.run(command(condition, replicate, attempt) + ["--cfg", "job"],
                           cwd=STUDY, env=process_env(), text=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                           timeout=120, check=False)
    if probe.returncode != 0:
        raise RuntimeError("Hydra online config rejected: " + probe.stderr[-1200:])
    return data


def audit(condition: str, replicate: int, attempt: int = 1) -> dict:
    output = output_path(condition, replicate, attempt)
    metadata_file = output / "eds_eval/episode_metadata.jsonl"
    events_file = output / "eds_eval/stage_events.jsonl"
    status_file = output / "status.json"
    result_file = output / "results.txt"
    metadata = [json.loads(line) for line in metadata_file.read_text().splitlines() if line.strip()] if metadata_file.exists() else []
    events = [json.loads(line) for line in events_file.read_text().splitlines() if line.strip()] if events_file.exists() else []
    status = json.loads(status_file.read_text()) if status_file.exists() else {}
    match = re.search(r"Success count:\s*(\d+)/10", result_file.read_text()) if result_file.exists() else None
    videos = []
    successes = []
    for task_id in range(10):
        files = list((output / f"episode_{task_id + 1}").glob("*agentview.mp4"))
        videos.append(len(files))
        if any("success" in file.name for file in files):
            successes.append(task_id)
    errors = [{"task_id": row.get("task_id"), "step": row.get("global_step"),
               "error": row.get("error"), "query_status": row.get("query_status")}
              for row in events if row.get("query_status") != "ok" or row.get("query_ok") is not True]
    problems = []
    if status.get("exit_code") != 0:
        problems.append("process_nonzero_exit")
    if [(row.get("task_id"), row.get("episode_seed")) for row in metadata] != list(enumerate(SEEDS)):
        problems.append("task_seed_metadata_incomplete_or_wrong")
    if videos != [1] * 10:
        problems.append("video_coverage_incomplete")
    if not events:
        problems.append("missing_stage_events")
    if errors:
        problems.append("stage_infrastructure_or_parse_errors")
    if match is None or int(match.group(1)) != len(successes):
        problems.append("reported_score_differs")
    result = {
        "schema": "c0-stage-online-audit-v1", "utc": utc(),
        "condition": condition, "replicate": replicate, "attempt": attempt,
        "valid": not problems, "problems": problems,
        "success_count": len(successes), "success_task_ids": successes,
        "reported_success_count": int(match.group(1)) if match else None,
        "metadata_rows": len(metadata), "stage_event_count": len(events),
        "stage_errors": errors, "videos_per_episode": videos,
        "status": status,
    }
    atomic_json(output / "online-audit.json", result)
    return result


def run(condition: str, replicate: int, attempt: int = 1) -> dict:
    manifest = prepare(condition, replicate, attempt)
    output = output_path(condition, replicate, attempt)
    if output.exists() or not gpu_idle():
        raise RuntimeError("Online output already exists or physical GPU2 is busy")
    with (STUDY / "data/qd-ed-runner.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if output.exists() or not gpu_idle():
            raise RuntimeError("Online output appeared or physical GPU2 became busy")
        output.mkdir(parents=True)
        atomic_json(output / "dispatch.json", {"utc": utc(), "argv": manifest["argv"],
                     "manifest_sha256": digest(output.parent / f"{run_label(condition, replicate, attempt)}_manifest.json")})
        started = time.monotonic()
        last_count = 0
        last_progress = started
        proc = None
        try:
            with (output / "console.log").open("w") as stream:
                proc = subprocess.Popen(command(condition, replicate, attempt), cwd=STUDY,
                                        env=process_env(), stdout=stream,
                                        stderr=subprocess.STDOUT, start_new_session=True)
                while proc.poll() is None:
                    count = attempts_started(output)
                    if count > 10:
                        raise RuntimeError("Online run exceeded ten episodes")
                    if stage_errors_seen(output):
                        raise RuntimeError("Online Stage service/parse error; preserve invalid run")
                    if count > last_count:
                        print(f"{utc()} {condition} replicate {replicate} attempt {attempt}: "
                              f"{count}/10 started", flush=True)
                        last_count, last_progress = count, time.monotonic()
                    atomic_json(output / "status.json", {"status": "running", "utc": utc(),
                        "pid": proc.pid, "episode_started": count,
                        "elapsed_seconds": time.monotonic() - started})
                    if time.monotonic() - started > MAX_SECONDS or time.monotonic() - last_progress > MAX_STALL_SECONDS:
                        raise RuntimeError("Online run exceeded time/progress watchdog")
                    time.sleep(15)
        finally:
            if proc is not None and proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=15)
            elapsed = time.monotonic() - started
            atomic_json(output / "status.json", {"status": "exited", "utc": utc(),
                "pid": proc.pid if proc is not None else None,
                "exit_code": proc.returncode if proc is not None else None,
                "episode_started": attempts_started(output), "elapsed_seconds": elapsed})
            atomic_json(output / "budget-charge.json", {
                "schema": "c0-stage-online-charge-v1",
                "primary_episodes_started": attempts_started(output),
                "gpu_hours_upper_bound": elapsed / 3600.0,
                "audit_valid": False})
        result = audit(condition, replicate, attempt)
        atomic_json(output / "budget-charge.json", {
            "schema": "c0-stage-online-charge-v1",
            "primary_episodes_started": attempts_started(output),
            "gpu_hours_upper_bound": elapsed / 3600.0,
            "audit_valid": result["valid"]})
        print(json.dumps(result, indent=2), flush=True)
        if not result["valid"]:
            raise RuntimeError("Online C0 candidate is invalid; preserve evidence")
        return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "run", "audit"))
    parser.add_argument("--condition", required=True, choices=tuple(ONLINE_CONDITIONS))
    parser.add_argument("--replicate", type=int, default=1, choices=(1, 2))
    parser.add_argument("--attempt", type=int, default=1)
    args = parser.parse_args()
    if args.action == "prepare":
        print(json.dumps(prepare(args.condition, args.replicate, args.attempt), indent=2))
    elif args.action == "audit":
        print(json.dumps(audit(args.condition, args.replicate, args.attempt), indent=2))
    else:
        run(args.condition, args.replicate, args.attempt)


if __name__ == "__main__":
    main()
