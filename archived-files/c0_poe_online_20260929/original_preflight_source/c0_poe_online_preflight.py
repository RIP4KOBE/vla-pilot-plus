#!/usr/bin/env python3
"""Prepare historical C0 for live Poe; never dispatch a GPU episode.

Credentials are loaded only by the eventual worker from a mode-0600 file.
The saved command and Hydra config contain no credential values.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import yaml

from c0_current_trace_replay import command as replay_command
from c0_trace_replay import CACHE, ORIGINAL_JOB, SEEDS, STUDY, atomic_json, digest, process_env


ROOT = STUDY / "artifacts/c0_poe_online_20260929"
CREDENTIAL = Path("/home/hynx/.config/vla-pilot/poe-stage-gpu2.key")
MODEL = "gemini-2.5-flash"


def command() -> list[str]:
    output = ROOT / "outputs/c0_poe_gemini_2_5_flash_attempt1"
    replacements = {
        "hydra.run.dir": str(output),
        "main.eds_eval.output_dir": str(output / "eds_eval"),
        "perception.gemini.backend": "openai_compatible",
    }
    result = []
    removed = 0
    for arg in replay_command():
        key, sep, value = arg.partition("=")
        if key == "+perception.gemini.replay_trace_path":
            removed += 1
            continue
        result.append(key + "=" + replacements.get(key, value) if sep else arg)
    if removed != 1:
        raise RuntimeError("Expected one historical Stage replay override")
    result += ["perception.gemini.model=" + MODEL,
               "+perception.gemini.base_url=https://api.poe.com/v1"]
    return result


def prepare() -> dict:
    previous = json.loads((STUDY / "artifacts/c0_trace_replay_20260925/current-manifest-v2.json").read_text())
    cache_hashes = {p.name: digest(p) for p in sorted(CACHE.iterdir()) if p.is_file()}
    if cache_hashes != previous["cache_sha256"]:
        raise RuntimeError("Historical reward cache changed")
    original = yaml.safe_load((ORIGINAL_JOB.parent / ".hydra/config.yaml").read_text())
    # Config-only resolution does not contact Poe or initialize a GPU worker.
    probe = subprocess.run(command() + ["--cfg", "job"], cwd=STUDY,
                           env=process_env(), text=True, capture_output=True,
                           timeout=120, check=True)
    current = yaml.safe_load(probe.stdout)
    for name in ("policy", "backend"):
        if current[name] != original[name]:
            raise RuntimeError("Historical config differs: " + name)
    eds = original["main"]["eds_config"]
    for key, value in eds.items():
        if current["main"]["eds_config"][key] != value:
            raise RuntimeError("Historical ED config differs: " + key)
    assert current["main"]["episode_seed_schedule"] == SEEDS
    assert current["main"].get("episode_policy_rng_mode", "legacy_continuous") == "legacy_continuous"
    assert current["main"]["eds_config"]["qd_archive_mode"] == "none"
    assert current["perception"]["gemini"]["api_key"] is None
    assert current["perception"]["gemini"]["model"] == MODEL
    assert not any("replay_trace_path" in x or "codex_cli" in x for x in command())
    stat = CREDENTIAL.stat()
    if stat.st_mode & 0o077:
        raise RuntimeError("Credential file permissions are too broad")
    manifest = {
        "schema": "c0-poe-online-preflight-v1", "dispatch_authorized_for_original_model_only": True,
        "ready_for_gpu": False, "blocker": "historical_poe_model_unavailable",
        "model": MODEL, "endpoint": "https://api.poe.com/v1",
        "physical_gpu": 2, "egl_device_index": 1, "episode_seeds": SEEDS,
        "episode_count": 10, "maximum_steps": 720,
        "policy_backend_match_original": True, "original_eds_fields_matched": len(eds),
        "cache_sha256": cache_hashes, "argv": command(), "cwd": str(STUDY),
        "source_sha256": {name: digest(STUDY / name) for name in (
            "main.py", "core/gemini_grounder.py", "core/rdt_policy_steer.py",
            "vlm_query/stage_template.txt", "scripts/c0_poe_online_preflight.py")},
        "credential_path_only": str(CREDENTIAL), "credential_in_command_or_config": False,
        "stage_request": {"max_tokens": 256, "temperature": 0.0,
                          "response_parser": "original_free_text_with_original_parse_fallback"},
        "replacement_model_requires_user_decision": True,
    }
    atomic_json(ROOT / "preflight.json", manifest)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "command"))
    args = parser.parse_args()
    print(json.dumps(prepare() if args.action == "prepare" else command(), indent=2))
