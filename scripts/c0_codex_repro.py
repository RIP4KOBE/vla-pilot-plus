#!/usr/bin/env python3
"""Owned, C0-only Codex source comparison. Never resumes old QD runners."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone


STUDY = Path(__file__).resolve().parents[1]
LEGACY = STUDY.parent / "eds-quality-diversity"
ARTIFACT = STUDY / "artifacts" / "c0_codex_repro_20260925"
ORIGINAL_JOB = Path(
    "/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/"
    "outputs/formal/p2_stage_on_abs_rbf_control/job_manifest.json"
)
ORIGINAL_CACHE = Path(
    "/home/hynx/VLA-Pilot++/outputs/libero/2026-06-04_13-21-01/episode_1/vlm_agent"
)
CACHE_FILES = (
    "metadata.json", "output_raw.txt", "prompt.txt", "query_img.png",
    "stage1_guidance.txt", "stage2_guidance.txt",
)
LEGACY_COMMIT = "53187e6ea8b69e9f830c10be0bc25757db5d2794"
CURRENT_COMMIT = "77761b4cda78ac3b6762a6aa60f97b07fde7c1dc"
SEEDS = [44, 235, 43, 546, 6, 621, 197, 87, 151, 548]
PYTHON = Path("/home/hynx/miniconda3/envs/vla-pilot/bin/python")
CLI = shutil.which("codex")
GPU_HOUR_CAP = 11.5126573231


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    temp.replace(path)


def revision(root: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def metadata() -> dict:
    job = json.loads(ORIGINAL_JOB.read_text())
    original = job["execution_record"]
    assert original["git_revision"] == LEGACY_COMMIT
    settings = original["job_semantics"]
    assert settings["suite"] == "libero_object_swap"
    assert settings["task_ids_filter"] == list(range(10))
    assert settings["episode_seeds"] == SEEDS
    assert settings["seed"] == 0
    assert settings["qd_archive_mode"] == "none"
    assert settings["max_episode_steps"] == 720
    assert settings["stage_recognition_enabled"] is True
    assert revision(LEGACY) == LEGACY_COMMIT
    assert revision(STUDY) == CURRENT_COMMIT
    assert CLI and PYTHON.is_file()
    assert digest(LEGACY / "vlm_query/stage_template.txt") == digest(STUDY / "vlm_query/stage_template.txt")
    for name in ("gemini_grounder.py", "codex_stage.py", "codex_stage_policy.py"):
        assert digest(LEGACY / "core" / name) == digest(STUDY / "core" / name), name
    return job


def prepare() -> dict:
    job = metadata()
    cache = ARTIFACT / "cache" / "cached_functions"
    cache.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name in CACHE_FILES:
        source = ORIGINAL_CACHE / name
        destination = cache / name
        if not destination.exists():
            shutil.copy2(source, destination)
        if digest(source) != digest(destination):
            raise RuntimeError("Historical cache copy differs: " + name)
        hashes[name] = digest(source)
    libero_config = LEGACY / ".libero_config" / "config.yaml"
    for line in libero_config.read_text().splitlines():
        if ": " in line:
            role, path = line.split(": ", 1)
            candidate = Path(path)
            # Evaluation loads assets, BDDL and init states, not demonstration datasets.
            if role != "datasets" and not candidate.exists():
                raise RuntimeError("Missing historical LIBERO input: " + str(candidate))
    config = {
        "schema": "c0-codex-repro-v1", "created_utc": utc(),
        "legacy_source_commit": LEGACY_COMMIT,
        "current_source_commit": CURRENT_COMMIT,
        "original_job_manifest": str(ORIGINAL_JOB),
        "original_job_sha256": digest(ORIGINAL_JOB),
        "stage_template_sha256": digest(STUDY / "vlm_query/stage_template.txt"),
        "cache_source": str(ORIGINAL_CACHE), "cache_sha256": hashes,
        "libero_config": str(libero_config),
        "libero_config_sha256": digest(libero_config),
        "codex_cli": str(Path(CLI).resolve()),
        "codex_cli_version": subprocess.check_output([CLI, "--version"], text=True).strip(),
        "stage_model": "gpt-6-astra", "stage_reasoning_effort": "low",
        "stage_format": "json_schema_v1",
        "stage_event_policy": "completed_known_startup_warnings_combo_v5",
        "stage_timeout_seconds": 180, "stage_query_limit": 50,
        "stage_min_query_gap_steps": 0,
        "physical_gpu": 2, "egl_device_index": 1,
        "episode_seeds": SEEDS, "gpu_hour_cap_for_this_study": GPU_HOUR_CAP,
        "transport_source_sha256": {name: digest(STUDY / "core" / name) for name in
            ("gemini_grounder.py", "codex_stage.py", "codex_stage_policy.py")},
        "legacy_adapter_main_sha256": digest(LEGACY / "main.py"),
        "current_main_sha256": digest(STUDY / "main.py"),
        "legacy_policy_sha256": digest(LEGACY / "core/rdt_policy_steer.py"),
        "current_policy_sha256": digest(STUDY / "core/rdt_policy_steer.py"),
    }
    manifest = ARTIFACT / "manifest.json"
    if manifest.exists():
        old = json.loads(manifest.read_text())
        for key, value in config.items():
            if key != "created_utc" and old.get(key) != value:
                raise RuntimeError("Frozen C0 manifest changed: " + key)
        return old
    atomic_json(manifest, config)
    return config


def command(arm: str) -> tuple[list[str], Path]:
    if arm not in ("legacy", "current"):
        raise ValueError(arm)
    original = metadata()["execution_record"]["normalized_command"]
    assert original[:6] == ["conda", "run", "-n", "vla-pilot", "python", "main.py"]
    root = LEGACY if arm == "legacy" else STUDY
    output = ARTIFACT / "outputs" / arm
    replaces = {
        "hydra.run.dir": str(output),
        "main.eds_eval.output_dir": str(output / "eds_eval"),
        "main.cached_functions_dir": str(ARTIFACT / "cache" / "cached_functions"),
    }
    overrides = []
    for item in original[6:]:
        key, sep, value = item.partition("=")
        assert sep, item
        overrides.append(key + "=" + replaces.get(key, value))
    prefix = "+" if arm == "legacy" else ""
    overrides.extend([
        prefix + "perception.gemini.backend=codex_cli",
        "perception.gemini.model=gpt-6-astra",
        prefix + "perception.gemini.reasoning_effort=low",
        prefix + "perception.gemini.timeout_seconds=180",
        prefix + "perception.gemini.output_format=json_schema_v1",
        prefix + "perception.gemini.event_policy=completed_known_startup_warnings_combo_v5",
    ])
    if arm == "current":
        overrides.extend([
            "+main.stage_min_query_gap_steps=0",
            "main.eds_config.qd_degenerate_fallback_policy=none",
            "main.eds_config.qd_secondary_lane_mode=none",
            "main.eds_config.qd_global_quality_anchor_count=0",
            "main.eds_config.qd_bounds_update_policy=fixed_initial",
        ])
    return [str(PYTHON), "main.py", *overrides], root


def process_env() -> dict:
    env = os.environ.copy()
    env.update(CUDA_VISIBLE_DEVICES="2", MUJOCO_EGL_DEVICE_ID="1", MUJOCO_GL="egl",
               PYOPENGL_PLATFORM="egl", JOBLIB_MULTIPROCESSING="0",
               LIBERO_CONFIG_PATH=str(LEGACY / ".libero_config"),
               OPENAI_API_KEY="REDACTED")
    for key in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "OPENAI_BASE_URL", "AZURE_OPENAI_BASE_URL"):
        env.pop(key, None)
    return env


def gpu_idle() -> bool:
    raw = subprocess.check_output([
        "nvidia-smi", "--query-gpu=index,memory.used,utilization.gpu",
        "--format=csv,noheader,nounits"], text=True)
    for line in raw.splitlines():
        fields = [x.strip() for x in line.split(",")]
        if fields[0] == "2":
            return int(fields[1]) < 1024 and int(fields[2]) == 0
    return False


def episode_started(output: Path) -> int:
    path = output / "eds_eval/episode_metadata.jsonl"
    if not path.exists():
        return 0
    return sum(bool(line.strip()) for line in path.open())


def audit(arm: str) -> dict:
    output = ARTIFACT / "outputs" / arm
    result_path = output / "results.txt"
    metadata_path = output / "eds_eval/episode_metadata.jsonl"
    events_path = output / "eds_eval/stage_events.jsonl"
    result = {"arm": arm, "audited_utc": utc(), "valid": False, "reasons": []}
    if not result_path.exists() or not metadata_path.exists() or not events_path.exists():
        result["reasons"].append("missing_required_artifact")
        atomic_json(output / "audit.json", result)
        return result
    score = re.search(r"Success count:\s*(\d+)/10", result_path.read_text())
    if score is None:
        result["reasons"].append("missing_ten_task_score")
    metadata = [json.loads(line) for line in metadata_path.read_text().splitlines() if line.strip()]
    events = [json.loads(line) for line in events_path.read_text().splitlines() if line.strip()]
    result["metadata_rows"] = len(metadata)
    result["stage_events"] = len(events)
    if len(metadata) != 10:
        result["reasons"].append("episode_count_not_ten")
    if [(row.get("task_id"), row.get("episode_seed")) for row in metadata] != list(enumerate(SEEDS)):
        result["reasons"].append("task_seed_order_differs")
    errors = [row for row in events if row.get("query_status") == "error" or
              (row.get("query_status") == "ok" and row.get("query_ok") is not True)]
    result["stage_error_events"] = len(errors)
    if errors:
        result["reasons"].append("stage_error_events")
    videos = []
    successes = []
    for index in range(1, 11):
        episode_dir = output / f"episode_{index}"
        found = list(episode_dir.glob("*success*agentview.mp4")) + list(episode_dir.glob("*fail*agentview.mp4"))
        videos.append(len(found))
        if any("success" in path.name for path in found):
            successes.append(index - 1)
        if (episode_dir / "error.txt").exists():
            result["reasons"].append(f"episode_{index}_error")
    result["videos_per_episode"] = videos
    if videos != [1] * 10:
        result["reasons"].append("video_coverage_incomplete")
    result["success_task_ids"] = successes
    result["success_count"] = len(successes)
    if score and int(score.group(1)) != len(successes):
        result["reasons"].append("score_video_disagreement")
    result["valid"] = not result["reasons"]
    atomic_json(output / "audit.json", result)
    return result


def run(arm: str) -> None:
    prepare()
    output = ARTIFACT / "outputs" / arm
    if output.exists() and any(output.iterdir()):
        raise RuntimeError("Output already exists; no overwrite or implicit resume: " + str(output))
    if arm == "current" and not audit("legacy")["valid"]:
        raise RuntimeError("Historical-source C0 must be valid before current-source C0")
    previous_seconds = 0.0
    if arm == "current":
        previous = json.loads((ARTIFACT / "outputs/legacy/status.json").read_text())
        if previous.get("status") != "exited" or previous.get("exit_code") != 0:
            raise RuntimeError("Historical-source C0 has no valid terminal process")
        previous_seconds = float(previous["elapsed_seconds"])
    if previous_seconds >= GPU_HOUR_CAP * 3600:
        raise RuntimeError("C0 GPU-hour allocation is depleted")
    if not gpu_idle():
        raise RuntimeError("Physical GPU2 is not idle")
    lock_path = STUDY / "data/qd-ed-runner.lock"
    with lock_path.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        args, root = command(arm)
        output.mkdir(parents=True)
        atomic_json(output / "dispatch.json", {
            "arm": arm, "started_utc": utc(), "argv": args, "cwd": str(root),
            "manifest_sha256": digest(ARTIFACT / "manifest.json"),
        })
        started = time.monotonic()
        last_episode = 0
        last_episode_time = started
        with (output / "console.log").open("w") as logfile:
            proc = subprocess.Popen(args, cwd=root, env=process_env(),
                                    stdout=logfile, stderr=subprocess.STDOUT,
                                    start_new_session=True)
            try:
                while proc.poll() is None:
                    elapsed = time.monotonic() - started
                    count = episode_started(output)
                    if count > last_episode:
                        last_episode = count
                        last_episode_time = time.monotonic()
                        print(f"{utc()} {arm} episode started {count}/10", flush=True)
                    atomic_json(output / "status.json", {
                        "arm": arm, "status": "running", "pid": proc.pid,
                        "utc": utc(), "episode_started": count,
                        "elapsed_seconds": elapsed,
                    })
                    if elapsed + previous_seconds > GPU_HOUR_CAP * 3600 or time.monotonic() - last_episode_time > 3600:
                        os.killpg(proc.pid, signal.SIGTERM)
                        proc.wait(timeout=15)
                        atomic_json(output / "status.json", {
                            "arm": arm, "status": "watchdog_stop", "exit_code": proc.returncode,
                            "utc": utc(), "episode_started": episode_started(output),
                            "elapsed_seconds": time.monotonic() - started,
                            "previous_gpu_seconds": previous_seconds,
                        })
                        raise RuntimeError("C0 budget or one-episode watchdog reached")
                    time.sleep(15)
            finally:
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait()
            atomic_json(output / "status.json", {
                "arm": arm, "status": "exited", "exit_code": proc.returncode,
                "utc": utc(), "episode_started": episode_started(output),
                "elapsed_seconds": time.monotonic() - started,
            })
            print(f"{utc()} {arm} exited {proc.returncode}", flush=True)
            if proc.returncode != 0:
                raise RuntimeError("C0 cohort failed; inspect console.log")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "command", "run", "audit"))
    parser.add_argument("--arm", choices=("legacy", "current"), default="legacy")
    args = parser.parse_args()
    if args.action == "prepare":
        print(json.dumps(prepare(), indent=2))
    elif args.action == "command":
        prepare()
        argv, cwd = command(args.arm)
        print(json.dumps({"argv": argv, "cwd": str(cwd)}, indent=2))
    elif args.action == "audit":
        print(json.dumps(audit(args.arm), indent=2))
    else:
        run(args.arm)


if __name__ == "__main__":
    main()
