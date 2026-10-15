#!/usr/bin/env python3
"""C0 on GPU2 with new per-episode Poe guidance and live Stage, no old cache."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import shutil
import subprocess

import yaml

import c0_poe_online_retest as runner
from c0_trace_replay import STUDY, SEEDS, atomic_json, digest, process_env, utc

ROOT = STUDY / "artifacts/c0_poe_fresh_20260929"
OUTPUT = ROOT / "outputs/c0_poe_fresh_attempt1"
MANIFEST = ROOT / "manifest.json"
REFERENCE = STUDY / "artifacts/c0_poe_online_20260929/gemini3-manifest.json"
MODEL = "gemini-3-flash"
ENDPOINT = "https://api.poe.com/v1"
GPU_UUID = "GPU-a5d6a5f8-b6df-7f3a-c3dc-19734c41ec0e"
original_audit = runner.audit


def command():
    previous = json.loads(REFERENCE.read_text())
    replacements = {
        "main.cached_functions_dir": "null",
        "hydra.run.dir": str(OUTPUT),
        "main.eds_eval.output_dir": str(OUTPUT / "eds_eval"),
        "+perception.gemini.capture_dir": str(OUTPUT / "captured_stage_inputs"),
    }
    result = []
    for arg in previous["argv"]:
        key, sep, value = arg.partition("=")
        result.append(key + "=" + replacements.get(key, value) if sep else arg)
    return result + ["perception.vlm_agent.model=" + MODEL,
                     "perception.vlm_agent.base_url=" + ENDPOINT]


def worker_env():
    env = process_env()
    credential = runner.CREDENTIAL
    if credential.stat().st_mode & 0o077:
        raise RuntimeError("Credential file must be private")
    key = credential.read_text().strip()
    if not key:
        raise RuntimeError("Empty credential")
    env.update(OPENAI_API_KEY=key, GOOGLE_API_KEY=key, OPENAI_BASE_URL=ENDPOINT)
    return env


def flatten(value, prefix=""):
    if isinstance(value, dict):
        result = {}
        for key, sub in value.items():
            result.update(flatten(sub, prefix + "." + key if prefix else key))
        return result
    return {prefix: value}


def prepare():
    previous = json.loads(REFERENCE.read_text())
    authority = json.loads((ROOT / "authorization.json").read_text())
    if authority["episodes"] != 10 or authority["physical_gpu"] != 2 or authority["model"] != MODEL:
        raise RuntimeError("Authorization does not match")
    isolation = yaml.safe_load((STUDY / "research-state.yaml").read_text())["resource_isolation"]
    if isolation["status"] != "ACTIVE" or isolation["validation_status"] != "PASS":
        raise RuntimeError("Resource isolation not active")
    for name, fingerprint in previous["source_sha256"].items():
        if digest(STUDY / name) != fingerprint:
            raise RuntimeError("Reference source changed: " + name)
    resolved = subprocess.run(command() + ["--cfg", "job"], cwd=STUDY, env=process_env(),
                              capture_output=True, text=True, timeout=120, check=True)
    current = yaml.safe_load(resolved.stdout)
    old = yaml.safe_load((runner.OUTPUT / ".hydra/config.yaml").read_text()) if runner.OUTPUT != OUTPUT else yaml.safe_load(
        (STUDY / "artifacts/c0_poe_online_20260929/outputs/c0_poe_gemini3_flash_attempt1/.hydra/config.yaml").read_text())
    allowed = {"main.cached_functions_dir", "main.eds_eval.output_dir", "perception.gemini.capture_dir",
               "perception.vlm_agent.model", "perception.vlm_agent.base_url"}
    cf, of = flatten(current), flatten(old)
    changes = {k: {"before": of.get(k), "after": cf.get(k)} for k in set(cf) | set(of) if cf.get(k) != of.get(k)}
    unexpected = set(changes) - allowed
    if unexpected:
        raise RuntimeError("Unexpected configuration differences: " + repr(sorted(unexpected)))
    assert current["main"]["cached_functions_dir"] is None
    assert current["main"]["episode_seed_schedule"] == SEEDS
    assert current["main"].get("episode_policy_rng_mode", "continuous") == "continuous"
    assert current["main"]["eds_config"]["qd_archive_mode"] == "none"
    assert current["main"]["episode_num"] == 10
    assert current["backend"]["libero"]["max_episode_steps"] == 720
    assert current["seed"] == 0
    for section in ("gemini", "vlm_agent"):
        assert current["perception"][section]["model"] == MODEL
        assert current["perception"][section]["base_url"] == ENDPOINT
        assert current["perception"][section].get("api_key") is None
    gpu = subprocess.check_output(["nvidia-smi", "-i", "2", "--query-gpu=uuid", "--format=csv,noheader"], text=True).strip()
    if gpu != GPU_UUID:
        raise RuntimeError("Physical GPU2 identity changed")
    files = sorted(set(previous["source_sha256"]) | {
        "vlm_query/vlm_agent.py", "vlm_query/guidance_template.txt",
        "vlm_query/guidance_template_libero.txt", "utils/guidance_utils.py",
        "scripts/c0_poe_fresh_retest.py"})
    manifest = {"schema": "c0-poe-fresh-v1", "model": MODEL, "physical_gpu": 2,
        "gpu_uuid": GPU_UUID, "argv": command(), "cwd": str(STUDY),
        "episodes": 10, "episode_seeds": SEEDS, "policy_rng": "continuous",
        "historical_generation_cache_used": False, "stage_replay_used": False,
        "config_changes_from_cached_condition": changes,
        "generation_request": {"temperature": current["perception"]["vlm_agent"]["temperature"],
            "max_completion_tokens": current["perception"]["vlm_agent"]["max_completion_tokens"],
            "stream": True, "generation_scope": "once per episode, fresh image/instruction/keypoints"},
        "stage_request": previous["stage_request"],
        "source_sha256": {name: digest(STUDY / name) for name in files},
        "authorization_sha256": digest(ROOT / "authorization.json"),
        "reference_manifest_sha256": digest(REFERENCE)}
    if MANIFEST.exists() and json.loads(MANIFEST.read_text()) != manifest:
        raise RuntimeError("Frozen manifest differs; preserve prior evidence")
    atomic_json(MANIFEST, manifest)
    (ROOT / "resolved-config.yaml").write_text(resolved.stdout)
    for name in files:
        dest = ROOT / "frozen_source" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and digest(dest) != digest(STUDY / name):
            raise RuntimeError("Frozen source differs: " + name)
        if not dest.exists():
            shutil.copy2(STUDY / name, dest)
    return manifest


def audit():
    result = original_audit()
    problems = result["problems"]
    generations = []
    for task in range(10):
        folder = OUTPUT / f"episode_{task + 1}" / "vlm_agent"
        record = {"task_id": task, "directory": str(folder)}
        try:
            meta = json.loads((folder / "metadata.json").read_text())
            required = [folder / name for name in ("prompt.txt", "query_img.png", "output_raw.txt", "metadata.json")]
            required += [folder / f"stage{s}_guidance.txt" for s in range(1, meta["num_stages"] + 1)]
            record["num_stages"] = meta["num_stages"]
            record["sha256"] = {p.name: digest(p) for p in required}
            record["task_prompt"] = next((line for line in (folder / "prompt.txt").read_text().splitlines() if line.startswith("Query Task:")), None)
            for p in required:
                if p.name.endswith("_guidance.txt"):
                    tree = ast.parse(p.read_text())
                    if not any(isinstance(node, ast.FunctionDef) for node in tree.body):
                        problems.append(f"task_{task}_no_functions_{p.name}")
            if not record["task_prompt"]:
                problems.append(f"task_{task}_missing_instruction")
        except (OSError, KeyError, ValueError, SyntaxError) as exc:
            problems.append(f"task_{task}_generation_incomplete_{type(exc).__name__}")
        generations.append(record)
    manifest = json.loads(MANIFEST.read_text())
    changed = [name for name, h in manifest["source_sha256"].items() if digest(STUDY / name) != h]
    if changed:
        problems.append("frozen_source_changed")
    config = yaml.safe_load((OUTPUT / ".hydra/config.yaml").read_text())
    if config["main"]["cached_functions_dir"] is not None:
        problems.append("unexpected_cache_use")
    log = (OUTPUT / "console.log").read_text(errors="replace")
    if "Using cached guidance functions from:" in log:
        problems.append("cache_load_logged")
    secret = runner.CREDENTIAL.read_bytes().strip()
    leaks = []
    for path in ROOT.rglob("*"):
        if path.is_file() and path.suffix in (".json", ".yaml", ".yml", ".log", ".txt", ".md", ".py"):
            if secret and secret in path.read_bytes():
                leaks.append(str(path.relative_to(ROOT)))
    if leaks:
        problems.append("credential_leak_in_artifact")
    result.update(valid=not problems, generations=generations,
                  historical_generation_cache_used=False, changed_source_files=changed,
                  credential_leak_files=leaks)
    atomic_json(OUTPUT / "audit.json", result)
    return result


def configure_runner():
    runner.OUTPUT = OUTPUT
    runner.MANIFEST = MANIFEST
    runner.prepare = prepare
    runner.worker_env = worker_env
    runner.audit = audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "audit", "progress"))
    args = parser.parse_args()
    configure_runner()
    if args.action == "run":
        runner.run()
    else:
        value = {"prepare": prepare, "audit": audit, "progress": runner.progress}[args.action]()
        print(json.dumps(value, indent=2, ensure_ascii=False))
