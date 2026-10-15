#!/usr/bin/env python3
"""Protocol-locked paired Dev-A runner for the v3 global-quality anchor."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
WORKTREE_ROOT = SCRIPT_DIR.parent
for import_root in (SCRIPT_DIR, WORKTREE_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import eds_qd_autoresearch_v3_runner as mechanism


v2 = mechanism.v2
v1 = mechanism.v1
base = mechanism.base
legacy = mechanism.legacy
qd_audit = mechanism.qd_audit

DEV_A_LEVEL = "eds_qd_autoresearch_v3_dev_a"
BRANCH = "exp/eds-qd-autoresearch-libero-swap-ood"
PROTOCOL_COMMIT = "fa51d5db5133602ab8e19cb8215b0d96c2b11de6"
RUN_033_RESULT_COMMIT = "c67a82bfb461a841fb92ed48167a81f5630b7cc4"
EXPERIMENT_ROOT = mechanism.EXPERIMENT_ROOT
RUN_ROOT = EXPERIMENT_ROOT / "run_034_global_quality_anchor_dev_a"
OUTPUT_LINK = WORKTREE_ROOT / "outputs"
MANIFEST_PATH = RUN_ROOT / "manifests/dev_a_manifest.json"
ATTEMPT_LEDGER_PATH = RUN_ROOT / "manifests/episode_attempt_ledger.jsonl"
AUDIT_PATH = RUN_ROOT / "analysis/dev_a_audit.json"
RUN_033_AUDIT_PATH = (
    EXPERIMENT_ROOT
    / "run_033_global_quality_anchor_online_mechanism/analysis/mechanism_audit.json"
)
RUN_033_AUDIT_SHA256 = (
    "b5f4c671d28bcec039f0b3ad6536ab1191fcad6c4f8c843926e66e3612acf96b"
)
RUNTIME_CACHE_DIR = mechanism.RUNTIME_CACHE_DIR
RUNTIME_CACHE_MANIFEST_PATH = mechanism.RUNTIME_CACHE_MANIFEST_PATH
DINOV2_TORCH_HUB_SEED = mechanism.DINOV2_TORCH_HUB_SEED
PAUSE_SENTINEL = WORKTREE_ROOT / ".autoresearch/PAUSE"
PROTECTED_UNTRACKED = "docs/01_specs/2026-08-10-eds-qd-stage-guidance-transition-design.md"
ALLOWED_STORAGE_PREFIX = mechanism.ALLOWED_STORAGE_PREFIX
MIN_FREE_BYTES = mechanism.MIN_FREE_BYTES
ALLOWED_GPU_INDICES = set(range(8))
PRIOR_GLOBAL_RESERVATIONS = 78
GLOBAL_RESERVATION_CAP = 143
PRIOR_GPU_HOURS = 4.183103444444445
GLOBAL_GPU_HOUR_CAP = 48.0
RECOVERY_SLOTS_REMAINING = 13
DEV_A_TASKS = [0, 1, 2, 4, 6, 7]
DEV_A_SEEDS = [307995, 262892, 731741, 14859, 648306, 960581]
DEV_A_MAX_CHUNKS = 16
EXPECTED_GLOBAL_ATTEMPT_IDS = list(range(79, 91))
EXPECTED_ALGORITHM_HASHES = dict(mechanism.EXPECTED_ALGORITHM_HASHES)
EXPECTED_DEPENDENCY_HASHES = {
    "scripts/eds_qd_autoresearch_v3_runner.py": (
        "4feefcd165ddf4073a8ff23c4a993a1c4b801bd01a83e5b7cd622a2b1ae19ea0"
    ),
    "scripts/eds_qd_autoresearch_v2_runner.py": (
        "799fa07ea33af682f40c7d45cc75a443d94ee4de283d833813eec773a4676626"
    ),
    "scripts/eds_qd_autoresearch_runner.py": (
        "6ba743a67d220eb38bce10e9748245de9699ba277e7c51db4daf46234bc1f202"
    ),
    "scripts/eds_quality_diversity_audit.py": (
        "7384ffdde3d5e22f650e27463f7aa7cad40d86627e4113aca0faf9ab0f084d6f"
    ),
    "scripts/rdt_eds_eval_runner.py": (
        "16c7b2cbc16da33b8792198b7ec6717e1a34a159e2a88634c83e52dce5cc311c"
    ),
}
QD_CONFIG_FIELDS = mechanism.QD_CONFIG_FIELDS
_BASE_BUILD_MAIN_COMMAND = mechanism._BASE_BUILD_MAIN_COMMAND
_BASE_STAGE_DIR = mechanism._BASE_STAGE_DIR

now = mechanism.now
canonical = mechanism.canonical
sha256_bytes = mechanism.sha256_bytes
sha256_path = mechanism.sha256_path
contains_credential = mechanism.contains_credential
hydra_value = mechanism.hydra_value
checkpoint_fingerprint = mechanism.checkpoint_fingerprint
libero_input_fingerprint = mechanism.libero_input_fingerprint
gpu_reference = mechanism.gpu_reference
admit_gpus = mechanism.admit_gpus


def profiles() -> list[dict[str, Any]]:
    return [dict(profile) for profile in mechanism.profiles()]


def profile_fingerprint(profile: dict[str, Any]) -> str:
    excluded = {"method", "label", "role", "job_id", "level", "formal_label"}
    payload = {
        "profile": {key: value for key, value in profile.items() if key not in excluded},
        "suite": "libero_object_swap",
        "strict_perturbations": True,
        "dev_a_tasks": DEV_A_TASKS,
        "dev_a_seeds": DEV_A_SEEDS,
        "max_chunks": DEV_A_MAX_CHUNKS,
    }
    return sha256_bytes(canonical(payload).encode("utf-8"))


def stage_dir(level: Any) -> str:
    if str(level) == DEV_A_LEVEL:
        return "run_034_global_quality_anchor_dev_a"
    return _BASE_STAGE_DIR(level)


def build_main_command(
    job: dict[str, Any],
    gpu: str = "0",
    timeout_seconds: int = 28800,
    **kwargs: Any,
) -> list[str]:
    prepared = dict(job)
    prepared.setdefault("p2_output_real_root", str(EXPERIMENT_ROOT))
    with configured_base():
        command = _BASE_BUILD_MAIN_COMMAND(
            prepared,
            gpu,
            timeout_seconds,
            **kwargs,
        )
    command.append("main.episode_seed_schedule=" + hydra_value(prepared["episode_seeds"]))
    command.extend(
        [
            "main.eds_config.initial_diversity_descriptor_mode="
            + str(prepared["initial_diversity_descriptor_mode"]),
            "main.eds_config.rollout_diversity_descriptor_mode="
            + str(prepared["rollout_diversity_descriptor_mode"]),
            "main.eds_eval.max_visual_chunks_per_episode=2",
            "main.keypoint_detection_max_attempts=3",
        ]
    )
    command.extend(
        f"main.eds_config.{field}={hydra_value(prepared[field])}"
        for field in QD_CONFIG_FIELDS
    )
    override_keys = [
        token.split("=", 1)[0].lstrip("+") for token in command if "=" in token
    ]
    if len(override_keys) != len(set(override_keys)):
        raise RuntimeError("Dev-A command contains duplicate Hydra overrides")
    if contains_credential(command):
        raise RuntimeError("Dev-A command contains credential material")
    return command


def _bind_job(job: dict[str, Any]) -> dict[str, Any]:
    if MANIFEST_PATH.is_file():
        if MANIFEST_PATH.stat().st_mode & 0o222:
            raise RuntimeError("Dev-A manifest must be immutable")
        job = {
            **job,
            "manifest_path": str(MANIFEST_PATH.resolve(strict=True)),
            "manifest_sha256": sha256_path(MANIFEST_PATH),
        }
    with configured_base():
        return base._bind_p2_execution_context(
            job,
            real_root=EXPERIMENT_ROOT,
            cached_functions_dir=str(RUNTIME_CACHE_DIR),
            offline_vlm=False,
            storage_enforced=True,
            git_revision=base._git_head_revision(),
            code_state_sha256=base._p2_code_state_sha256(),
        )


def build_jobs(
    level: str,
    episodes: int | None = None,
    *,
    bind: bool = True,
    **_: Any,
) -> list[dict[str, Any]]:
    if level != DEV_A_LEVEL:
        raise ValueError("v3 Dev-A runner supports only the Dev-A level")
    if episodes is not None and int(episodes) != 6:
        raise ValueError("v3 Dev-A requires exactly six episodes per profile")
    jobs = []
    for profile in profiles():
        formal_label = str(profile["label"])
        label = f"dev_a__{formal_label}"
        job = {
            **profile,
            "formal_label": formal_label,
            "method": label,
            "label": label,
            "job_id": f"{DEV_A_LEVEL}_libero_object_swap_{label}",
            "level": DEV_A_LEVEL,
            "suite": "libero_object_swap",
            "episodes": 6,
            "task_ids_filter": list(DEV_A_TASKS),
            "episode_seeds": list(DEV_A_SEEDS),
            "max_chunks": DEV_A_MAX_CHUNKS,
        }
        jobs.append(_bind_job(job) if bind else job)
    return jobs


def gpu_probe(gpu: str) -> tuple[str, str]:
    index = int(gpu)
    if index not in ALLOWED_GPU_INDICES:
        return "busy", "GPU index is outside authorized 0-7"
    reference = gpu_reference()
    device = next(
        (item for item in legacy.gpu_snapshot() if int(item["index"]) == index),
        None,
    )
    reasons = legacy._gpu_snapshot_failure(
        device,
        index=index,
        required_free=float(reference["required_free_vram_mib"]),
        allow_external_compute=False,
    )
    return ("busy", "; ".join(reasons)) if reasons else ("idle", "admitted")


def configure_base() -> None:
    base.P2_OUTPUT_ROOT = OUTPUT_LINK
    base.P2_STATUS_ROOT = OUTPUT_LINK
    base.P2_EXPECTED_OUTPUT_TARGET = EXPERIMENT_ROOT
    base.P2_ALLOWED_OUTPUT_PREFIX = ALLOWED_STORAGE_PREFIX
    base.P2_MIN_FREE_BYTES = MIN_FREE_BYTES
    base.P2_LEVELS = set(base.P2_LEVELS) | {DEV_A_LEVEL}
    base.P2_ALLOWED_GPUS = {str(index) for index in ALLOWED_GPU_INDICES}
    base.P2_REQUIRED_MOUNT = Path("/mnt/data/shared2")
    base.P2_TORCH_HUB_SEED = DINOV2_TORCH_HUB_SEED
    base.build_jobs = build_jobs
    base.build_main_command = build_main_command
    base._p2_stage_dir = stage_dir
    base._p2_gpu_probe = gpu_probe


@contextmanager
def configured_base():
    names = (
        "P2_OUTPUT_ROOT",
        "P2_STATUS_ROOT",
        "P2_EXPECTED_OUTPUT_TARGET",
        "P2_ALLOWED_OUTPUT_PREFIX",
        "P2_MIN_FREE_BYTES",
        "P2_LEVELS",
        "P2_ALLOWED_GPUS",
        "P2_REQUIRED_MOUNT",
        "P2_TORCH_HUB_SEED",
        "build_jobs",
        "build_main_command",
        "_p2_stage_dir",
        "_p2_gpu_probe",
    )
    saved = {name: getattr(base, name) for name in names}
    configure_base()
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(base, name, value)


def pause_preflight() -> None:
    if PAUSE_SENTINEL.exists():
        raise RuntimeError(f"autoresearch paused by sentinel: {PAUSE_SENTINEL}")


def storage_preflight() -> dict[str, Any]:
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    return v1.storage_preflight(
        experiment_root=EXPERIMENT_ROOT,
        output_link=OUTPUT_LINK,
        allowed_prefix=ALLOWED_STORAGE_PREFIX,
        minimum_free_bytes=MIN_FREE_BYTES,
    )


def current_provenance() -> dict[str, Any]:
    status = subprocess.check_output(
        ["git", "status", "--short"], cwd=WORKTREE_ROOT, text=True
    ).splitlines()
    unexpected = [
        line
        for line in status
        if not line.endswith(PROTECTED_UNTRACKED) and not line.endswith(" outputs")
    ]
    if unexpected:
        raise RuntimeError("worktree must be committed: " + "; ".join(unexpected))
    branch = subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=WORKTREE_ROOT, text=True
    ).strip()
    if branch != BRANCH:
        raise RuntimeError(f"unexpected branch: {branch}")
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=WORKTREE_ROOT, text=True
    ).strip()
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", RUN_033_RESULT_COMMIT, head],
        cwd=WORKTREE_ROOT,
        check=False,
    )
    if ancestor.returncode != 0:
        raise RuntimeError("Run033 result commit is not an ancestor")
    with configured_base():
        code_state = base._p2_code_state_sha256()
    return {
        "branch": branch,
        "code_commit": head,
        "code_state_sha256": code_state,
        "protocol_commit": PROTOCOL_COMMIT,
        "run_033_result_commit": RUN_033_RESULT_COMMIT,
    }


def source_fingerprints() -> dict[str, str]:
    paths = [
        *EXPECTED_ALGORITHM_HASHES,
        *EXPECTED_DEPENDENCY_HASHES,
        "scripts/eds_qd_autoresearch_v3_dev_runner.py",
        "tests/test_eds_qd_autoresearch_v3_dev_runner.py",
    ]
    actual = {path: sha256_path(WORKTREE_ROOT / path) for path in paths}
    frozen = {**EXPECTED_ALGORITHM_HASHES, **EXPECTED_DEPENDENCY_HASHES}
    if {path: actual[path] for path in frozen} != frozen:
        raise RuntimeError("Dev-A algorithm/config/dependency differs from freeze")
    return actual


def runtime_cache_fingerprint() -> dict[str, Any]:
    validated = legacy.validate_runtime_cache(
        target=RUNTIME_CACHE_DIR,
        manifest_path=RUNTIME_CACHE_MANIFEST_PATH,
    )
    return {
        "path": str(RUNTIME_CACHE_DIR.resolve(strict=True)),
        "manifest_sha256": sha256_path(RUNTIME_CACHE_MANIFEST_PATH),
        "aggregate_sha256": sha256_bytes(canonical(validated).encode("utf-8")),
    }


def dinov2_seed_fingerprint() -> dict[str, Any]:
    paths = {
        "hubconf.py": DINOV2_TORCH_HUB_SEED / "facebookresearch_dinov2_main/hubconf.py",
        "checkpoint": DINOV2_TORCH_HUB_SEED / "checkpoints/dinov2_vitb14_pretrain.pth",
        "trusted_list": DINOV2_TORCH_HUB_SEED / "trusted_list",
    }
    if any(not path.is_file() for path in paths.values()):
        raise RuntimeError("audited DINOv2 seed is incomplete")
    return {
        "root": str(DINOV2_TORCH_HUB_SEED.resolve(strict=True)),
        "files": {name: sha256_path(path) for name, path in paths.items()},
    }


def verified_run_033() -> dict[str, Any]:
    if (
        not RUN_033_AUDIT_PATH.is_file()
        or RUN_033_AUDIT_PATH.stat().st_mode & 0o222
        or sha256_path(RUN_033_AUDIT_PATH) != RUN_033_AUDIT_SHA256
    ):
        raise RuntimeError("immutable Run033 audit identity mismatch")
    payload = json.loads(RUN_033_AUDIT_PATH.read_text(encoding="utf-8"))
    task = payload.get("task_success_summary", {})
    if (
        payload.get("passed") is not True
        or payload.get("hard_failures") != []
        or task.get("candidate_success_tasks") != [9]
        or task.get("gained_tasks") != [9]
        or task.get("lost_tasks") != []
        or payload.get("formal_authorized") is not False
    ):
        raise RuntimeError("Run033 audit is not the frozen promotion PASS")
    return {
        "path": str(RUN_033_AUDIT_PATH),
        "sha256": RUN_033_AUDIT_SHA256,
        "candidate_success_tasks": [9],
        "candidate_minus_control": 1,
        "hard_failures": [],
    }


def _write_json(path: Path, payload: dict[str, Any], *, immutable: bool = False) -> None:
    v2._write_json(path, payload, immutable=immutable)


def build_manifest_payload() -> dict[str, Any]:
    jobs = build_jobs(DEV_A_LEVEL, bind=False)
    payload = {
        "schema": "eds-qd-autoresearch-v3-dev-a-manifest-v1",
        "created_at": now(),
        "provenance": current_provenance(),
        "source_fingerprints": source_fingerprints(),
        "checkpoint_fingerprint": checkpoint_fingerprint(),
        "libero_input_fingerprint": libero_input_fingerprint(),
        "runtime_cache_fingerprint": runtime_cache_fingerprint(),
        "dinov2_seed_fingerprint": dinov2_seed_fingerprint(),
        "gpu_reference": gpu_reference(),
        "run_033_audit": verified_run_033(),
        "suite": "libero_object_swap",
        "strict_perturbations": True,
        "max_episode_steps": 720,
        "profiles": [
            {**profile, "profile_fingerprint": profile_fingerprint(profile)}
            for profile in profiles()
        ],
        "dev_a": {
            "tasks": DEV_A_TASKS,
            "seeds": DEV_A_SEEDS,
            "unique_cells": 12,
            "candidate_minimum_successes": 3,
            "candidate_minimum_delta_over_control": 1,
            "lost_control_success_tasks_allowed": 0,
            "jobs": [
                {
                    "job_id": job["job_id"],
                    "formal_label": job["formal_label"],
                    "config_fingerprint": profile_fingerprint(
                        next(p for p in profiles() if p["label"] == job["formal_label"])
                    ),
                    "command_sha256": sha256_bytes(
                        canonical(build_main_command(job)).encode("utf-8")
                    ),
                }
                for job in jobs
            ],
        },
        "prior_global_reservations": PRIOR_GLOBAL_RESERVATIONS,
        "expected_global_attempt_ids": EXPECTED_GLOBAL_ATTEMPT_IDS,
        "global_reservation_cap": GLOBAL_RESERVATION_CAP,
        "prior_gpu_hours": PRIOR_GPU_HOURS,
        "global_gpu_hour_cap": GLOBAL_GPU_HOUR_CAP,
        "recovery_slots_remaining": RECOVERY_SLOTS_REMAINING,
        "allowed_gpu_indices": sorted(ALLOWED_GPU_INDICES),
        "validation_authorized": False,
        "formal_authorized": False,
        "credential_material_present": False,
    }
    payload["payload_sha256"] = sha256_bytes(canonical(payload).encode("utf-8"))
    if contains_credential(payload):
        raise RuntimeError("Dev-A manifest contains credential material")
    return payload


def freeze_manifest() -> dict[str, Any]:
    pause_preflight()
    storage_preflight()
    verified_run_033()
    if ATTEMPT_LEDGER_PATH.exists():
        raise RuntimeError("Dev-A attempt ledger must not exist at manifest freeze")
    if MANIFEST_PATH.exists():
        raise RuntimeError("Dev-A manifest already exists")
    payload = build_manifest_payload()
    _write_json(MANIFEST_PATH, payload, immutable=True)
    return payload


def validate_manifest() -> dict[str, Any]:
    pause_preflight()
    if not MANIFEST_PATH.is_file() or MANIFEST_PATH.stat().st_mode & 0o222:
        raise RuntimeError("immutable Dev-A manifest is required")
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    stored_sha = payload.get("payload_sha256")
    unsigned = dict(payload)
    unsigned.pop("payload_sha256", None)
    if stored_sha != sha256_bytes(canonical(unsigned).encode("utf-8")):
        raise RuntimeError("Dev-A manifest payload hash mismatch")
    if payload.get("schema") != "eds-qd-autoresearch-v3-dev-a-manifest-v1":
        raise RuntimeError("Dev-A manifest schema mismatch")
    if payload.get("validation_authorized") is not False or payload.get(
        "formal_authorized"
    ) is not False:
        raise RuntimeError("Dev-A manifest must forbid validation/formal")
    checks = {
        "provenance": current_provenance(),
        "source_fingerprints": source_fingerprints(),
        "checkpoint_fingerprint": checkpoint_fingerprint(),
        "libero_input_fingerprint": libero_input_fingerprint(),
        "runtime_cache_fingerprint": runtime_cache_fingerprint(),
        "dinov2_seed_fingerprint": dinov2_seed_fingerprint(),
        "gpu_reference": gpu_reference(),
        "run_033_audit": verified_run_033(),
    }
    for key, expected in checks.items():
        if payload.get(key) != expected:
            raise RuntimeError(f"Dev-A manifest {key} mismatch")
    expected_profiles = [
        {**profile, "profile_fingerprint": profile_fingerprint(profile)}
        for profile in profiles()
    ]
    if payload.get("profiles") != expected_profiles:
        raise RuntimeError("Dev-A manifest profile mismatch")
    dev = payload.get("dev_a", {})
    if (
        dev.get("tasks") != DEV_A_TASKS
        or dev.get("seeds") != DEV_A_SEEDS
        or dev.get("unique_cells") != 12
        or dev.get("candidate_minimum_successes") != 3
        or dev.get("candidate_minimum_delta_over_control") != 1
        or dev.get("lost_control_success_tasks_allowed") != 0
    ):
        raise RuntimeError("Dev-A manifest matrix/gate mismatch")
    if (
        payload.get("prior_global_reservations") != PRIOR_GLOBAL_RESERVATIONS
        or payload.get("expected_global_attempt_ids") != EXPECTED_GLOBAL_ATTEMPT_IDS
        or payload.get("global_reservation_cap") != GLOBAL_RESERVATION_CAP
        or payload.get("prior_gpu_hours") != PRIOR_GPU_HOURS
        or payload.get("global_gpu_hour_cap") != GLOBAL_GPU_HOUR_CAP
        or payload.get("recovery_slots_remaining") != RECOVERY_SLOTS_REMAINING
    ):
        raise RuntimeError("Dev-A manifest budget mismatch")
    if contains_credential(payload):
        raise RuntimeError("Dev-A manifest credential scan failed")
    return payload


def validate_credential() -> dict[str, Any]:
    value = os.environ.get("OPENAI_API_KEY", "").strip()
    if not value or value.lower() == "dummy":
        raise RuntimeError("Stage credential must come from runtime environment")
    return {"present": True, "source": "environment", "value_logged": False}


def read_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def ledger_state(path: Path) -> dict[str, Any]:
    rows = read_ledger(path)
    attempts = [row for row in rows if row.get("record_type") == "episode_attempt"]
    if [row.get("attempt_id") for row in attempts] != EXPECTED_GLOBAL_ATTEMPT_IDS[: len(attempts)]:
        raise RuntimeError("Dev-A attempt IDs are not contiguous from 79")
    events = [row for row in rows if row.get("record_type") != "episode_attempt"]
    if [row.get("ledger_event_id") for row in events] != list(range(1, len(events) + 1)):
        raise RuntimeError("Dev-A ledger event IDs are not contiguous")
    known = {int(row["attempt_id"]) for row in attempts}
    dispatched: set[int] = set()
    for event in events:
        ids = event.get("attempt_ids")
        if (
            event.get("record_type") != "phase_dispatch"
            or not isinstance(ids, list)
            or not ids
            or not set(ids) <= known
            or set(ids) & dispatched
        ):
            raise RuntimeError("invalid Dev-A ledger event")
        dispatched.update(int(value) for value in ids)
    return {"rows": rows, "attempts": attempts, "dispatched_attempt_ids": sorted(dispatched)}


def reserve_attempts(path: Path, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if path.exists():
        raise RuntimeError("Dev-A ledger already exists; same-cell retry needs protocol")
    if len(records) != 12:
        raise RuntimeError("Dev-A requires exactly 12 reservations")
    identities = [
        (
            row.get("formal_label"),
            row.get("task_id"),
            row.get("episode_seed"),
            row.get("config_fingerprint"),
        )
        for row in records
    ]
    if len(identities) != len(set(identities)):
        raise RuntimeError("duplicate Dev-A reservation identity")
    if PRIOR_GLOBAL_RESERVATIONS + len(records) > GLOBAL_RESERVATION_CAP:
        raise RuntimeError("global reservation cap would be exceeded")
    prepared = [
        {
            "attempt_id": PRIOR_GLOBAL_RESERVATIONS + offset,
            "record_type": "episode_attempt",
            "started_at": now(),
            **row,
        }
        for offset, row in enumerate(records, start=1)
    ]
    if any(contains_credential(row) for row in prepared):
        raise RuntimeError("Dev-A attempt records contain credential material")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        for row in prepared:
            handle.write(canonical(row) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    ledger_state(path)
    return prepared


def append_dispatch_event(path: Path, attempt_ids: list[int], gpus: list[int]) -> dict[str, Any]:
    state = ledger_state(path)
    if state["dispatched_attempt_ids"]:
        raise RuntimeError("Dev-A dispatch already recorded")
    event = {
        "ledger_event_id": 1,
        "record_type": "phase_dispatch",
        "created_at": now(),
        "phase": DEV_A_LEVEL,
        "attempt_ids": list(attempt_ids),
        "selected_gpu_indices": list(gpus),
    }
    if contains_credential(event):
        raise RuntimeError("Dev-A dispatch event contains credential material")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical(event) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return ledger_state(path)


def attempt_records(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_label = {profile["label"]: profile for profile in profiles()}
    rows = []
    for job in jobs:
        for episode, (task, seed) in enumerate(
            zip(job["task_ids_filter"], job["episode_seeds"], strict=True)
        ):
            rows.append(
                {
                    "phase": DEV_A_LEVEL,
                    "label": job["label"],
                    "formal_label": job["formal_label"],
                    "episode": episode,
                    "task_id": int(task),
                    "episode_seed": int(seed),
                    "config_fingerprint": profile_fingerprint(by_label[job["formal_label"]]),
                    "code_state_sha256": job["execution_record"]["code_state_sha256"],
                }
            )
    return rows


def _select_gpus(admission: dict[str, Any], requested: str) -> list[str]:
    eligible = [str(value) for value in admission["eligible_gpu_indices"]]
    selected = (
        eligible[:2]
        if requested == "auto"
        else [item.strip() for item in requested.split(",") if item.strip()]
    )
    if not selected or len(selected) != len(set(selected)) or len(selected) > 2:
        raise RuntimeError("selected GPU list must contain one or two unique devices")
    if not set(selected) <= set(eligible):
        raise RuntimeError("selected GPU failed admission")
    return selected


def run_dev_a(*, gpus: str, timeout_seconds: int) -> int:
    manifest = validate_manifest()
    storage_preflight()
    legacy.validate_runtime_cache(
        target=RUNTIME_CACHE_DIR,
        manifest_path=RUNTIME_CACHE_MANIFEST_PATH,
    )
    validate_credential()
    with configured_base():
        if not base._poe_healthcheck():
            raise RuntimeError("real pre-reservation Stage/Poe health check failed")
    jobs = build_jobs(DEV_A_LEVEL)
    reference = manifest["gpu_reference"]
    admission = admit_gpus(reference_peak_vram_mib=float(reference["reference_peak_vram_mib"]))
    selected = _select_gpus(admission, gpus)
    immediate = legacy.gpu_snapshot()
    by_index = {int(item["index"]): item for item in immediate}
    for gpu in selected:
        reasons = legacy._gpu_snapshot_failure(
            by_index.get(int(gpu)),
            index=int(gpu),
            required_free=float(reference["required_free_vram_mib"]),
            allow_external_compute=False,
        )
        if reasons:
            raise RuntimeError(f"GPU {gpu} failed immediate snapshot: {reasons}")
    admission["dispatch_snapshot"] = immediate
    admission["selected_gpu_indices"] = [int(value) for value in selected]
    _write_json(
        RUN_ROOT / "manifests" / f"gpu_{DEV_A_LEVEL}_{int(time.time())}.json",
        admission,
    )
    attempts = reserve_attempts(ATTEMPT_LEDGER_PATH, attempt_records(jobs))
    if [row["attempt_id"] for row in attempts] != EXPECTED_GLOBAL_ATTEMPT_IDS:
        raise RuntimeError("Dev-A attempt IDs differ from frozen 79-90")
    append_dispatch_event(
        ATTEMPT_LEDGER_PATH,
        EXPECTED_GLOBAL_ATTEMPT_IDS,
        [int(value) for value in selected],
    )
    pause_preflight()
    with configured_base():
        original_healthcheck = base._poe_healthcheck
        base._poe_healthcheck = lambda: True
        try:
            return base.run_level(
                DEV_A_LEVEL,
                6,
                ",".join(selected),
                timeout_seconds,
                resume=False,
                cached_functions_dir=str(RUNTIME_CACHE_DIR),
                offline_vlm=False,
                manifest_path=str(MANIFEST_PATH),
                gpu_poll_interval_s=30.0,
            )
        finally:
            base._poe_healthcheck = original_healthcheck


def _read_metrics(job: dict[str, Any]) -> list[dict[str, Any]]:
    with configured_base():
        output = base._output_dir(job)
    path = output / "eds_eval/eds_metrics.jsonl"
    return base._read_jsonl(path) if path.is_file() else []


def _job_evidence(job: dict[str, Any]) -> dict[str, Any]:
    with configured_base():
        output = base._output_dir(job)
        validity = base._p2_job_validity(job)
    metrics = _read_metrics(job)
    outcomes = base._p2_episode_outcomes(output, int(job["episodes"]))
    parsed = base._parse_results_file(output / "results.txt")
    classifications = qd_audit._classify_failures(outcomes, metrics, output)
    return {
        "formal_label": job["formal_label"],
        "label": job["label"],
        "output": str(output),
        "valid": validity["valid"],
        "failure_reason": validity["failure_reason"],
        "success_count": parsed.get("success"),
        "outcomes": {
            str(task): outcomes.get(episode, "unknown")
            for episode, task in enumerate(job["task_ids_filter"])
        },
        "failure_classification_by_task": {
            str(task): classifications.get(episode, "unknown")
            for episode, task in enumerate(job["task_ids_filter"])
        },
        "telemetry_counts": qd_audit._telemetry_counts(metrics),
        "credential_audit": v1.credential_tree_audit(output),
        "artifact_inventory": v1.artifact_inventory(output),
        "metrics": metrics,
    }


def _metric_values(metrics: list[dict[str, Any]], field: str) -> list[float]:
    values = []
    for record in metrics:
        value = record.get(field)
        candidates = value if isinstance(value, list) else [value]
        values.extend(float(item) for item in candidates if mechanism._finite(item))
    return values


def _status_summary() -> dict[str, Any]:
    path = RUN_ROOT / "run_manifest.csv"
    if not path.is_file():
        return {"path": str(path), "rows": [], "gpu_hours": None}
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    walls = []
    for row in rows:
        try:
            value = float(row.get("wall_clock_s", ""))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and value >= 0:
            walls.append(value)
    return {
        "path": str(path),
        "sha256": sha256_path(path),
        "rows": rows,
        "gpu_hours": sum(walls) / 3600.0,
    }


def _attempt_audit() -> dict[str, Any]:
    state = ledger_state(ATTEMPT_LEDGER_PATH)
    failures = []
    ids = [int(row["attempt_id"]) for row in state["attempts"]]
    if ids != EXPECTED_GLOBAL_ATTEMPT_IDS:
        failures.append("Dev-A attempt IDs differ from frozen 79-90")
    if state["dispatched_attempt_ids"] != EXPECTED_GLOBAL_ATTEMPT_IDS:
        failures.append("Dev-A dispatched attempt IDs mismatch")
    expected = {
        (job["formal_label"], int(task), int(seed))
        for job in build_jobs(DEV_A_LEVEL, bind=False)
        for task, seed in zip(job["task_ids_filter"], job["episode_seeds"], strict=True)
    }
    actual = {
        (row.get("formal_label"), int(row["task_id"]), int(row["episode_seed"]))
        for row in state["attempts"]
    }
    if actual != expected:
        failures.append("Dev-A attempt cells differ from frozen matrix")
    if PRIOR_GLOBAL_RESERVATIONS + len(state["attempts"]) != 90:
        failures.append("global reservation accounting is not 90")
    return {
        "passed": not failures,
        "new_reserved_count": len(state["attempts"]),
        "global_reserved_count": PRIOR_GLOBAL_RESERVATIONS + len(state["attempts"]),
        "attempt_ids": ids,
        "failures": failures,
    }


def dev_a_task_gate(task_summary: dict[str, Any]) -> dict[str, Any]:
    failures = []
    if task_summary.get("candidate_success_count", 0) < 3:
        failures.append("candidate Dev-A success count is below 3/6")
    if task_summary.get("candidate_minus_control", -6) < 1:
        failures.append("candidate Dev-A improvement is below +1")
    if task_summary.get("lost_tasks"):
        failures.append("candidate lost one or more control-success tasks")
    return {"passed": not failures, "failures": failures}


def audit_dev_a() -> dict[str, Any]:
    manifest = validate_manifest()
    evidence = [_job_evidence(job) for job in build_jobs(DEV_A_LEVEL)]
    control = next(item for item in evidence if item["formal_label"] == profiles()[0]["label"])
    candidate = next(item for item in evidence if item["formal_label"] == profiles()[1]["label"])
    failures: list[str] = []
    for item in evidence:
        if item["valid"] is not True:
            failures.append(f"invalid job {item['formal_label']}: {item['failure_reason']}")
        if item["credential_audit"]["passed"] is not True:
            failures.append(f"credential audit failed for {item['formal_label']}")
    control_gate = mechanism.control_metric_gate(control["metrics"])
    candidate_gate = mechanism.candidate_metric_gate(candidate["metrics"])
    failures.extend(control_gate["failures"])
    failures.extend(candidate_gate["failures"])
    disallowed = {
        "qpos/execution error",
        "target pushed away",
        "target dropped after grasp",
        "basket displaced/collision",
        "clutter swept/wrong-object interaction",
    }
    safety = {
        item["formal_label"]: [
            value
            for value in item["failure_classification_by_task"].values()
            if value in disallowed
        ]
        for item in evidence
    }
    if any(safety.values()):
        failures.append("one or more Dev-A jobs produced a disallowed safety outcome")
    candidate_latency = v1.percentile(
        _metric_values(candidate["metrics"], "select_action_latency_s"), 0.95
    )
    control_latency = v1.percentile(
        _metric_values(control["metrics"], "select_action_latency_s"), 0.95
    )
    latency_ratio = (
        candidate_latency / control_latency
        if candidate_latency is not None
        and control_latency is not None
        and control_latency > 0
        else None
    )
    if latency_ratio is None or latency_ratio > 1.25:
        failures.append("candidate selection latency exceeds control 1.25x")
    task_summary = mechanism.task_success_summary(control["outcomes"], candidate["outcomes"])
    task_gate = dev_a_task_gate(task_summary)
    failures.extend(task_gate["failures"])
    attempts = _attempt_audit()
    failures.extend(attempts["failures"])
    status = _status_summary()
    cumulative_gpu_hours = (
        PRIOR_GPU_HOURS + float(status["gpu_hours"])
        if mechanism._finite(status.get("gpu_hours"))
        else None
    )
    if cumulative_gpu_hours is None or cumulative_gpu_hours > GLOBAL_GPU_HOUR_CAP:
        failures.append("global GPU-hour cap accounting failed")
    root_credentials = v1.credential_tree_audit(RUN_ROOT)
    failures.extend(root_credentials["failures"])
    payload = {
        "schema": "eds-qd-autoresearch-v3-dev-a-audit-v1",
        "created_at": now(),
        "manifest_path": str(MANIFEST_PATH),
        "manifest_sha256": sha256_path(MANIFEST_PATH),
        "manifest_payload_sha256": manifest["payload_sha256"],
        "run_033_audit": verified_run_033(),
        "jobs": [
            {key: value for key, value in item.items() if key != "metrics"}
            for item in evidence
        ],
        "task_outcomes": {item["formal_label"]: item["outcomes"] for item in evidence},
        "task_success_summary": task_summary,
        "task_gate": task_gate,
        "control_metric_gate": control_gate,
        "candidate_metric_gate": candidate_gate,
        "safety_outcomes": safety,
        "candidate_selection_latency_p95_s": candidate_latency,
        "control_selection_latency_p95_s": control_latency,
        "candidate_to_control_latency_ratio": latency_ratio,
        "attempt_ledger": attempts,
        "status": status,
        "prior_gpu_hours": PRIOR_GPU_HOURS,
        "cumulative_gpu_hours": cumulative_gpu_hours,
        "run_root_credential_audit": root_credentials,
        "hard_failures": list(dict.fromkeys(failures)),
        "passed": not failures,
        "validation_authorized": not failures,
        "formal_authorized": False,
    }
    if contains_credential(payload):
        raise RuntimeError("Dev-A audit contains credential material")
    _write_json(AUDIT_PATH, payload, immutable=True)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("print-plan")
    subparsers.add_parser("freeze-manifest")
    subparsers.add_parser("validate-manifest")
    run_parser = subparsers.add_parser("run-dev-a")
    run_parser.add_argument("--gpus", default="auto")
    run_parser.add_argument("--timeout-seconds", type=int, default=28800)
    subparsers.add_parser("audit-dev-a")
    args = parser.parse_args()
    if args.command == "print-plan":
        print(json.dumps(build_jobs(DEV_A_LEVEL, bind=False), indent=2, sort_keys=True))
        return 0
    if args.command == "freeze-manifest":
        payload = freeze_manifest()
        print(json.dumps({"passed": True, "payload_sha256": payload["payload_sha256"]}))
        return 0
    if args.command == "validate-manifest":
        payload = validate_manifest()
        print(json.dumps({"passed": True, "payload_sha256": payload["payload_sha256"]}))
        return 0
    if args.command == "run-dev-a":
        return run_dev_a(gpus=args.gpus, timeout_seconds=args.timeout_seconds)
    if args.command == "audit-dev-a":
        payload = audit_dev_a()
        print(json.dumps({"passed": payload["passed"], "hard_failures": payload["hard_failures"]}))
        return 0 if payload["passed"] else 1
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
