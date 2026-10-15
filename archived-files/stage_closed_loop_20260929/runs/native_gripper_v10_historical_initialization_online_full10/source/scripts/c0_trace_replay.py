#!/usr/bin/env python3
"""Fail-closed historical C0 Stage trace replay on the owned GPU2 budget."""

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

from c0_codex_repro import (
    ORIGINAL_JOB, PYTHON, SEEDS, atomic_json, digest,
    episode_started, gpu_idle, utc,
)

STUDY = Path("/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z")
LEGACY = Path("/home/hynx/VLA-Pilot++/.worktrees/exp/eds-quality-diversity")
ARTIFACT = STUDY / "artifacts/c0_trace_replay_20260925"
TRACE = Path(
    "/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/"
    "outputs/formal/p2_stage_on_abs_rbf_control/eds_eval/stage_events.jsonl"
)
CACHE = STUDY / "artifacts/c0_codex_repro_20260925/cache/cached_functions"
MAX_SECONDS = 9.5 * 3600


def process_env() -> dict:
    env = os.environ.copy()
    env.update(CUDA_VISIBLE_DEVICES="2", MUJOCO_EGL_DEVICE_ID="1", MUJOCO_GL="egl",
               PYOPENGL_PLATFORM="egl", JOBLIB_MULTIPROCESSING="0",
               LIBERO_CONFIG_PATH=str(LEGACY / ".libero_config"),
               OPENAI_API_KEY="REDACTED")
    for key in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "OPENAI_BASE_URL", "AZURE_OPENAI_BASE_URL"):
        env.pop(key, None)
    return env


def command() -> list[str]:
    original = json.loads(ORIGINAL_JOB.read_text())["execution_record"]["normalized_command"]
    assert original[:6] == ["conda", "run", "-n", "vla-pilot", "python", "main.py"]
    replacements = {
        "hydra.run.dir": str(ARTIFACT / "outputs/legacy"),
        "main.eds_eval.output_dir": str(ARTIFACT / "outputs/legacy/eds_eval"),
        "main.cached_functions_dir": str(CACHE),
    }
    overrides = []
    for item in original[6:]:
        key, sep, value = item.partition("=")
        assert sep
        overrides.append(key + "=" + replacements.get(key, value))
    overrides += [
        "+perception.gemini.backend=trace_replay",
        "+perception.gemini.replay_trace_path=" + str(TRACE),
    ]
    return [str(PYTHON), "main.py", *overrides]


def prepare() -> dict:
    assert ORIGINAL_JOB.is_file() and TRACE.is_file() and CACHE.is_dir()
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=LEGACY, text=True).strip() == "53187e6ea8b69e9f830c10be0bc25757db5d2794"
    rows = [json.loads(x) for x in TRACE.read_text().splitlines() if x.strip()]
    assert len(rows) == 127
    assert all(row["raw_response"] is not None for row in rows)
    assert [(x["task_id"], x["episode_seed"]) for x in rows if x["vlm_query_count"] == 1] == list(enumerate(SEEDS))
    content = {
        "schema": "c0-trace-replay-v1", "original_manifest_sha256": digest(ORIGINAL_JOB),
        "historical_trace_sha256": digest(TRACE), "historical_trace_rows": len(rows),
        "historical_stage_error_rows": sum(x["query_status"] == "error" for x in rows),
        "historical_source_commit": "53187e6ea8b69e9f830c10be0bc25757db5d2794",
        "source_sha256": {name: digest(LEGACY / name) for name in (
            "main.py", "core/gemini_grounder.py", "core/trace_replay_stage.py", "core/rdt_policy_steer.py")},
        "cache_sha256": {p.name: digest(p) for p in sorted(CACHE.iterdir()) if p.is_file()},
        "argv": command(), "cwd": str(LEGACY), "physical_gpu": 2,
        "egl_device_index": 1, "episode_seeds": SEEDS,
        "budget_max_gpu_seconds": MAX_SECONDS, "budget_max_attempts": 10,
        "purpose": "Recorded Poe/Gemini replies isolate Stage-vs-runtime effects; not a live Poe reproduction.",
    }
    path = ARTIFACT / "manifest.json"
    if path.exists():
        if json.loads(path.read_text()) != content:
            raise RuntimeError("Frozen trace-replay manifest differs")
    else:
        atomic_json(path, content)
    return content


def audit() -> dict:
    out = ARTIFACT / "outputs/legacy"
    events_path = out / "eds_eval/stage_events.jsonl"
    metadata_path = out / "eds_eval/episode_metadata.jsonl"
    result_path = out / "results.txt"
    status_path = out / "status.json"
    expected = [json.loads(x) for x in TRACE.read_text().splitlines() if x.strip()]
    actual = [json.loads(x) for x in events_path.read_text().splitlines() if x.strip()] if events_path.exists() else []
    metadata = [json.loads(x) for x in metadata_path.read_text().splitlines() if x.strip()] if metadata_path.exists() else []
    fields = ("episode_id", "task_id", "episode_seed", "global_step", "chunk_id",
              "trigger_reason", "stage_before", "stage_after", "guidance_before",
              "guidance_after", "query_status", "query_ok", "raw_response",
              "parsed_stage", "parsed_guidance", "error")
    matching_prefix = 0
    first_mismatch = None
    for index, (old, now) in enumerate(zip(expected, actual)):
        differences = {key: [old.get(key), now.get(key)] for key in fields if old.get(key) != now.get(key)}
        if differences:
            first_mismatch = {"index": index, "differences": differences}
            break
        matching_prefix += 1
    successes = []
    videos = []
    video_hashes_equal = []
    first_particle_hashes_equal = []
    for index in range(10):
        paths = list((out / f"episode_{index + 1}").glob("*agentview.mp4"))
        videos.append(len(paths))
        if any("success" in path.name for path in paths):
            successes.append(index)
        original_videos = list((ORIGINAL_JOB.parent / f"episode_{index + 1}").glob("*agentview.mp4"))
        video_hashes_equal.append(
            len(paths) == len(original_videos) == 1
            and paths[0].name == original_videos[0].name
            and digest(paths[0]) == digest(original_videos[0])
        )
        particle_rel = (f"eds_eval/qualitative/episode_{index:03d}/chunk_000000/"
                        "single_step_inner_loop/single_step_particles.csv")
        current_particles = out / particle_rel
        original_particles = ORIGINAL_JOB.parent / particle_rel
        first_particle_hashes_equal.append(
            current_particles.is_file() and original_particles.is_file()
            and digest(current_particles) == digest(original_particles)
        )
    status = json.loads(status_path.read_text()) if status_path.exists() else {}
    score = re.search(r"Success count:\s*(\d+)/10", result_path.read_text()) if result_path.exists() else None
    result = {
        "audited_utc": utc(), "historical_events": len(expected), "replay_events": len(actual),
        "matching_event_prefix": matching_prefix, "first_event_mismatch": first_mismatch,
        "metadata_rows": len(metadata), "videos_per_episode": videos,
        "video_sha256_equal_by_task": video_hashes_equal,
        "first_particle_sha256_equal_by_task": first_particle_hashes_equal,
        "success_task_ids": successes, "success_count": len(successes),
        "reported_success_count": int(score.group(1)) if score else None,
        "status": status, "valid_full_replay": (
            status.get("exit_code") == 0 and len(actual) == len(expected)
            and matching_prefix == len(expected) and len(metadata) == 10
            and videos == [1] * 10 and score is not None
            and all(video_hashes_equal) and all(first_particle_hashes_equal)
            and int(score.group(1)) == len(successes)
            and [(x["task_id"], x["episode_seed"]) for x in metadata] == list(enumerate(SEEDS))
        ),
    }
    atomic_json(out / "audit.json", result)
    return result


def run() -> None:
    prepare()
    out = ARTIFACT / "outputs/legacy"
    if out.exists() and any(out.iterdir()):
        raise RuntimeError("Trace replay output exists; no overwrite")
    if not gpu_idle():
        raise RuntimeError("Physical GPU2 is not idle")
    lock_path = STUDY / "data/qd-ed-runner.lock"
    with lock_path.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        out.mkdir(parents=True)
        atomic_json(out / "dispatch.json", {"argv": command(), "utc": utc(), "manifest_sha256": digest(ARTIFACT / "manifest.json")})
        started = time.monotonic()
        last_count = 0
        last_progress = started
        with (out / "console.log").open("w") as logfile:
            proc = subprocess.Popen(command(), cwd=LEGACY, env=process_env(), stdout=logfile,
                                    stderr=subprocess.STDOUT, start_new_session=True)
            try:
                while proc.poll() is None:
                    count = episode_started(out)
                    if count > last_count:
                        last_count = count
                        last_progress = time.monotonic()
                        print(f"{utc()} trace replay episode started {count}/10", flush=True)
                    atomic_json(out / "status.json", {"status": "running", "pid": proc.pid,
                                "utc": utc(), "episode_started": count,
                                "elapsed_seconds": time.monotonic() - started})
                    if time.monotonic() - started > MAX_SECONDS or time.monotonic() - last_progress > 3600:
                        os.killpg(proc.pid, signal.SIGTERM)
                        proc.wait(timeout=15)
                        raise RuntimeError("Trace replay budget/watchdog exceeded")
                    time.sleep(15)
            finally:
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGTERM)
                    proc.wait(timeout=15)
        atomic_json(out / "status.json", {"status": "exited", "pid": proc.pid,
                    "exit_code": proc.returncode, "utc": utc(),
                    "episode_started": episode_started(out),
                    "elapsed_seconds": time.monotonic() - started})
        result = audit()
        print(json.dumps(result, indent=2), flush=True)
        if proc.returncode != 0 or not result["valid_full_replay"]:
            raise RuntimeError("Historical Stage replay diverged or failed; inspect audit and console")


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
