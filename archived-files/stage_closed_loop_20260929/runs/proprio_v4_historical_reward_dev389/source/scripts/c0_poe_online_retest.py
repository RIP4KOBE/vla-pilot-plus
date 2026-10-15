#!/usr/bin/env python3
"""Run the user-approved Gemini-3-Flash C0 retest on physical GPU2 only."""

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

from c0_poe_online_preflight import ROOT, CREDENTIAL, command as old_command
from c0_trace_replay import CACHE, ORIGINAL_JOB, SEEDS, STUDY, atomic_json, digest, gpu_idle, process_env, utc

MODEL = "gemini-3-flash"
OUTPUT = ROOT / "outputs/c0_poe_gemini3_flash_attempt1"
MANIFEST = ROOT / "gemini3-manifest.json"


def command():
    replace = {"hydra.run.dir": str(OUTPUT), "main.eds_eval.output_dir": str(OUTPUT / "eds_eval"),
               "perception.gemini.model": MODEL}
    result = []
    for arg in old_command():
        key, sep, value = arg.partition("=")
        result.append(key + "=" + replace.get(key, value) if sep else arg)
    return result + ["+perception.gemini.capture_dir=" + str(OUTPUT / "captured_stage_inputs")]


def worker_env():
    if CREDENTIAL.stat().st_mode & 0o077:
        raise RuntimeError("Credential file is not private")
    env = process_env()
    env.update(GOOGLE_API_KEY=CREDENTIAL.read_text().strip(), OPENAI_BASE_URL="https://api.poe.com/v1")
    if not env["GOOGLE_API_KEY"]:
        raise RuntimeError("Poe credential is empty")
    return env


def rows(path):
    if not path.exists():
        return []
    result = []
    for line in path.read_text().splitlines():
        try:
            if line.strip():
                result.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # The running worker can be writing its final line.
    return result


def infrastructure_errors(events):
    # The historical parser's complete-but-malformed text fallback is retained.
    return [r for r in events if r.get("query_status") == "error" and r.get("raw_response") is None]


def prepare():
    authority = json.loads((ROOT / "authorization.json").read_text())
    if authority["model"] != MODEL or authority["physical_gpu"] != 2:
        raise RuntimeError("Model or GPU lacks user authorization")
    probe = json.loads((ROOT / "gemini3-stage-probe.json").read_text())
    if not probe.get("ok") or not probe.get("parse_ok") or probe.get("actual_model") != MODEL:
        raise RuntimeError("Exact multimodal Stage connectivity probe has not passed")
    state = yaml.safe_load((STUDY / "research-state.yaml").read_text())
    isolation = state["resource_isolation"]
    if isolation["status"] != "ACTIVE" or isolation["validation_status"] != "PASS":
        raise RuntimeError("Resource isolation is not active")
    previous = json.loads((STUDY / "artifacts/c0_trace_replay_20260925/current-manifest-v2.json").read_text())
    hashes = {p.name: digest(p) for p in sorted(CACHE.iterdir()) if p.is_file()}
    if hashes != previous["cache_sha256"]:
        raise RuntimeError("Historical reward cache differs")
    cfg_run = subprocess.run(command() + ["--cfg", "job"], cwd=STUDY, env=process_env(),
                             capture_output=True, text=True, timeout=120, check=True)
    current = yaml.safe_load(cfg_run.stdout)
    old = yaml.safe_load((ORIGINAL_JOB.parent / ".hydra/config.yaml").read_text())
    for key in ("policy", "backend"):
        if current[key] != old[key]:
            raise RuntimeError("C0 configuration differs: " + key)
    old_eds = old["main"]["eds_config"]
    if any(current["main"]["eds_config"][k] != v for k, v in old_eds.items()):
        raise RuntimeError("Historical ED settings differ")
    if current["main"].get("episode_policy_rng_mode", "continuous") != "continuous":
        raise RuntimeError("Historical continuous policy RNG changed")
    if current["main"]["episode_seed_schedule"] != SEEDS:
        raise RuntimeError("Historical seed schedule differs")
    if current["perception"]["gemini"]["api_key"] is not None:
        raise RuntimeError("Credential must not enter Hydra artifacts")
    source_files = ["main.py", "core/gemini_grounder.py", "core/poe_stage_capture.py",
                    "core/rdt_policy_steer.py", "vlm_query/stage_template.txt",
                    "scripts/c0_poe_online_retest.py", "scripts/c0_poe_online_preflight.py",
                    "scripts/c0_current_trace_replay.py", "scripts/c0_trace_replay.py"]
    data = {"schema": "c0-poe-online-retest-v1", "model": MODEL,
            "condition": "new_poe_online_model_not_strict_historical_model_reproduction",
            "argv": command(), "cwd": str(STUDY), "physical_gpu": 2, "egl_device_index": 1,
            "episode_seeds": SEEDS, "episodes": 10, "maximum_steps": 720,
            "cache_sha256": hashes, "original_eds_fields_matched": len(old_eds),
            "policy_backend_match": True, "policy_rng": "continuous",
            "stage_request": {"max_tokens": 256, "temperature": 0.0, "sdk_retries": "unchanged_default",
                              "parse_fallback": "original_stage1_guidance_on_no_resample"},
            "source_sha256": {name: digest(STUDY / name) for name in source_files},
            "authorization_sha256": digest(ROOT / "authorization.json"),
            "stage_probe_sha256": digest(ROOT / "gemini3-stage-probe.json")}
    if MANIFEST.exists() and json.loads(MANIFEST.read_text()) != data:
        raise RuntimeError("Frozen run manifest differs; preserve old evidence")
    atomic_json(MANIFEST, data)
    return data


def progress():
    events = rows(OUTPUT / "eds_eval/stage_events.jsonl")
    metas = rows(OUTPUT / "eds_eval/episode_metadata.jsonl")
    videos = list(OUTPUT.glob("episode_*/*agentview.mp4"))
    return {"started": max(len(metas), len(list(OUTPUT.glob("episode_*")))),
            "completed": len(videos), "successes": sum("success" in p.name for p in videos),
            "stage_events": len(events), "infrastructure_errors": len(infrastructure_errors(events)),
            "last_task": events[-1].get("task_id") if events else None,
            "last_step": events[-1].get("global_step") if events else None}


def audit():
    events = rows(OUTPUT / "eds_eval/stage_events.jsonl")
    queries = [e for e in events if e.get("query_status") in ("ok", "error")]
    metas = rows(OUTPUT / "eds_eval/episode_metadata.jsonl")
    status = json.loads((OUTPUT / "status.json").read_text())
    problems = []
    if status.get("exit_code") != 0:
        problems.append("worker_not_successfully_exited")
    if [(r.get("task_id"), r.get("episode_seed")) for r in metas] != list(enumerate(SEEDS)):
        problems.append("task_seed_metadata_incomplete_or_changed")
    if not queries or infrastructure_errors(events):
        problems.append("missing_or_failed_live_stage_service")
    successes, videos = [], []
    for task in range(10):
        folder = OUTPUT / f"episode_{task + 1}"
        found = list(folder.glob("*agentview.mp4"))
        videos.append(len(found))
        if any("success" in f.name for f in found):
            successes.append(task)
        if (folder / "error.txt").exists():
            problems.append(f"episode_{task}_error")
    if videos != [1] * 10:
        problems.append("video_coverage_incomplete")
    result_path = OUTPUT / "results.txt"
    match = re.search(r"Success count:\s*(\d+)/10", result_path.read_text()) if result_path.exists() else None
    if match is None or int(match.group(1)) != len(successes):
        problems.append("final_score_missing_or_inconsistent")
    for index, event in enumerate(queries):
        folder = OUTPUT / "captured_stage_inputs" / f"request_{index:04d}"
        try:
            meta = json.loads((folder / "metadata.json").read_text())
            parts = json.loads((folder / "parts.json").read_text())
            images = [digest(folder / p["file"]) for p in parts if p["type"] == "image_url"]
            fingerprint = {"prompt_sha256": digest(folder / "prompt.txt"), "image_png_sha256": images}
            if (event.get("transport", {}).get("request_fingerprint") != fingerprint or
                    meta.get("raw_response") != event.get("raw_response") or len(images) != 2 or
                    any(meta["context"].get(k) != event.get(k) for k in
                        ("task_id", "episode_seed", "global_step", "chunk_id"))):
                problems.append(f"capture_mismatch_{index}")
        except (OSError, KeyError, ValueError):
            problems.append(f"capture_invalid_{index}")
    captures = len(list((OUTPUT / "captured_stage_inputs").glob("request_*")))
    if captures != len(queries):
        problems.append("capture_count_mismatch")
    result = {"utc": utc(), "valid": not problems, "problems": problems,
              "model": MODEL, "success_count": len(successes), "success_task_ids": successes,
              "metadata_rows": len(metas), "stage_events": len(events), "stage_queries": len(queries),
              "complete_response_parse_fallbacks": sum(not e.get("query_ok") for e in queries),
              "infrastructure_errors": len(infrastructure_errors(events)), "captures": captures,
              "videos_per_episode": videos, "status": status}
    atomic_json(OUTPUT / "audit.json", result)
    return result


def run():
    manifest = prepare()
    if OUTPUT.exists():
        raise RuntimeError("Output already exists; no overwrite or implicit rerun")
    with (STUDY / "data/qd-ed-runner.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if not gpu_idle():
            raise RuntimeError("GPU2 is busy")
        OUTPUT.mkdir(parents=True)
        atomic_json(OUTPUT / "dispatch.json", {"utc": utc(), "manifest_sha256": digest(MANIFEST)})
        started = time.monotonic()
        proc = None
        try:
            with (OUTPUT / "console.log").open("w") as stream:
                proc = subprocess.Popen(manifest["argv"], cwd=STUDY, env=worker_env(),
                                        stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
                while proc.poll() is None:
                    info = progress()
                    atomic_json(OUTPUT / "status.json", {"status": "running", "utc": utc(),
                                "pid": proc.pid, "elapsed_seconds": time.monotonic()-started, **info})
                    print(json.dumps({"utc": utc(), **info}), flush=True)
                    if info["infrastructure_errors"] or info["started"] > 10:
                        raise RuntimeError("Infrastructure error or excess episodes; preserve incomplete run")
                    if time.monotonic() - started > 9 * 3600:
                        raise RuntimeError("Nine-hour hung-process watchdog exceeded")
                    time.sleep(30)
        finally:
            if proc is not None and proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=15)
            elapsed = time.monotonic() - started
            atomic_json(OUTPUT / "status.json", {"status": "exited", "utc": utc(),
                "pid": proc.pid if proc else None, "exit_code": proc.returncode if proc else None,
                "elapsed_seconds": elapsed, **progress()})
            atomic_json(OUTPUT / "budget-charge.json", {"episodes_started": progress()["started"],
                        "gpu_hours_upper_bound": elapsed / 3600, "protected_phase": False})
        result = audit()
        print(json.dumps(result, indent=2), flush=True)
        if not result["valid"]:
            raise RuntimeError("C0 online cohort is invalid; no algorithm advancement")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("prepare", "run", "audit", "progress"))
    args = p.parse_args()
    if args.action == "run":
        run()
    else:
        print(json.dumps({"prepare": prepare, "audit": audit, "progress": progress}[args.action](), indent=2))
