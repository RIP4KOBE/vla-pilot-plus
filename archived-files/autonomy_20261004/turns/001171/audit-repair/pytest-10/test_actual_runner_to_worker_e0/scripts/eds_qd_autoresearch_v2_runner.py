#!/usr/bin/env python3
"""Protocol-locked v2 runner for H2 online mechanism preflight only."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
WORKTREE_ROOT = SCRIPT_DIR.parent
for import_root in (SCRIPT_DIR, WORKTREE_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import eds_qd_autoresearch_runner as v1
import eds_quality_diversity_audit as qd_audit
import eds_quality_diversity_runner as legacy
import rdt_eds_eval_runner as base


MECHANISM_LEVEL = "eds_qd_autoresearch_v2_mechanism"
BRANCH = "exp/eds-qd-autoresearch-libero-swap-ood"
PROTOCOL_COMMIT = "73724cec4d8c60096e5c6baed46274c7098964a3"
RECOVERY_PROTOCOL_COMMIT = "70678d207d7196f4b6ae9adfb524b67970dce047"
LEDGER_RECOVERY_PROTOCOL_COMMIT = "27fc65c56347a1ee94353511a1d2cf9da3be65a1"
HEALTH_INCIDENT_RESULT_COMMIT = "f189621"
RUN_021_IMPLEMENTATION_COMMIT = "f010e8e4ff1f129e12499b1e0f8d284f505f7455"
RUN_022_RESULT_COMMIT = "8fde5676fc28ef643c2ccb81ef40707350f7bd32"
RUN_022_ARTIFACT_SHA256 = (
    "320fabf54847c77d944ed0ff5bdc2c530331c765d3bcfbef2aa5173c46279bac"
)
EXPERIMENT_ROOT = Path(
    "/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood"
)
RUN_ROOT = EXPERIMENT_ROOT / "run_023_reward_degenerate_online_mechanism"
OUTPUT_LINK = WORKTREE_ROOT / "outputs"
MANIFEST_V1_PATH = RUN_ROOT / "manifests/mechanism_manifest.json"
MANIFEST_V1_SHA256 = (
    "d51a44042357b129595cc220faeecd5a9029f2424e0b803711a32ed31a8ec718"
)
MANIFEST_V2_PATH = RUN_ROOT / "manifests/mechanism_manifest.v2.json"
MANIFEST_V2_SHA256 = (
    "8e47ebb3ddcdf4f9b3657d5585902b303d35fa2162e597e2faf1b7d87805d2df"
)
MANIFEST_PATH = RUN_ROOT / "manifests/mechanism_manifest.v3.json"
ATTEMPT_LEDGER_PATH = RUN_ROOT / "manifests/episode_attempt_ledger.jsonl"
AUDIT_PATH = RUN_ROOT / "analysis/mechanism_audit.json"
RUN_022_ARTIFACT_PATH = (
    EXPERIMENT_ROOT
    / "run_022_reward_degenerate_mechanism_preflight/analysis/mechanism_preflight.v1.json"
)
RUNTIME_CACHE_DIR = (
    EXPERIMENT_ROOT / "run_010_causal_envelope_candidate/runtime_cache/cached_functions"
)
RUNTIME_CACHE_MANIFEST_PATH = (
    EXPERIMENT_ROOT / "run_010_causal_envelope_candidate/runtime_cache/provenance.json"
)
PAUSE_SENTINEL = WORKTREE_ROOT / ".autoresearch/PAUSE"
PROTECTED_UNTRACKED = "docs/01_specs/2026-08-10-eds-qd-stage-guidance-transition-design.md"
ALLOWED_STORAGE_PREFIX = Path("/mnt/data/shared2/zhuoli/vla-pilot-plus-plus")
MIN_FREE_BYTES = 50 * 1024**3
ALLOWED_GPU_INDICES = set(range(8))
PRIOR_GLOBAL_RESERVATIONS = 54
GLOBAL_RESERVATION_CAP = 143
GLOBAL_GPU_HOUR_CAP = 48.0
PRIOR_GPU_HOURS = 2.934766777777778
MECHANISM_TASKS = [2, 3, 9]
MECHANISM_SEEDS = [932032, 615132, 718536]
MECHANISM_MAX_CHUNKS = 16
VOID_GLOBAL_ATTEMPT_IDS = list(range(55, 61))
EXPECTED_GLOBAL_ATTEMPT_IDS = list(range(61, 67))
GLOBAL_RESERVATIONS_BEFORE_RECOVERY = 60
EXPECTED_ALGORITHM_HASHES = {
    "configs/config.yaml": "c5844368c803f97540775365a1d5f3211997e6d77f6a0f0f581ffdf0cad63acc",
    "core/qd_ed.py": "1516bb75c3a5dc3894792d6b8f5daf7f777c48b7d58ea96496da47a986a970b9",
    "core/rdt_policy_steer.py": "890068dd804d38771608dbaafd5e38b70a14252f86d7e352b19fa477aca6159e",
    "core/eds_eval_metrics.py": "cbe31284abf40e4d8ebc54c78b8c534f946e2e1df60f0eab8f898f77b834a450",
}
QD_CONFIG_FIELDS = (
    "qd_archive_mode",
    "qd_degenerate_fallback_policy",
    "qd_descriptor",
    "qd_grid_shape",
    "qd_cell_capacity",
    "qd_parent_sampling",
    "qd_sparse_exponent",
    "qd_bounds_quantiles",
    "qd_bounds_expand_fraction",
    "qd_min_axis_span_m",
    "qd_bounds_update_policy",
    "qd_overflow_policy",
    "qd_tie_break",
    "qd_metrics_observer",
)
_BASE_BUILD_MAIN_COMMAND = v1._BASE_BUILD_MAIN_COMMAND
_BASE_STAGE_DIR = v1._BASE_STAGE_DIR


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def contains_credential(value: Any) -> bool:
    return v1.contains_credential(value)


def hydra_value(value: Any) -> str:
    return v1.hydra_value(value)


def profiles() -> list[dict[str, Any]]:
    return [
        v1._profile(
            "p2_stage_on_abs_rbf_control",
            "control",
            qd_archive_mode="none",
            qd_degenerate_fallback_policy="none",
        ),
        v1._profile(
            "eds_qd_reward_degenerate_control_fallback_v1",
            "candidate",
            qd_archive_mode="grid_archive",
            qd_parent_sampling="sparse_priority",
            qd_bounds_update_policy="causal_envelope_v1",
            qd_degenerate_fallback_policy="control_v1",
        ),
    ]


def profile_fingerprint(profile: dict[str, Any]) -> str:
    excluded = {"method", "label", "role", "job_id", "level", "formal_label"}
    payload = {
        "profile": {
            key: value for key, value in profile.items() if key not in excluded
        },
        "suite": "libero_object_swap",
        "strict_perturbations": True,
        "mechanism_tasks": MECHANISM_TASKS,
        "mechanism_seeds": MECHANISM_SEEDS,
        "max_chunks": MECHANISM_MAX_CHUNKS,
    }
    return sha256_bytes(canonical(payload).encode("utf-8"))


def stage_dir(level: Any) -> str:
    if str(level) == MECHANISM_LEVEL:
        return "run_023_reward_degenerate_online_mechanism"
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
    command.append(
        "main.episode_seed_schedule=" + hydra_value(prepared["episode_seeds"])
    )
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
        token.split("=", 1)[0].lstrip("+")
        for token in command
        if "=" in token
    ]
    if len(override_keys) != len(set(override_keys)):
        raise RuntimeError("v2 command contains duplicate Hydra overrides")
    if contains_credential(command):
        raise RuntimeError("v2 command contains credential material")
    return command


def _bind_job(job: dict[str, Any]) -> dict[str, Any]:
    if MANIFEST_PATH.is_file():
        if MANIFEST_PATH.stat().st_mode & 0o222:
            raise RuntimeError("mechanism manifest must be immutable")
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
    if level != MECHANISM_LEVEL:
        raise ValueError("v2 runner only supports the online mechanism level")
    if episodes is not None and int(episodes) != 3:
        raise ValueError("v2 mechanism requires exactly 3 episodes per profile")
    jobs: list[dict[str, Any]] = []
    for profile in profiles():
        formal_label = str(profile["label"])
        label = f"mechanism__{formal_label}"
        job = {
            **profile,
            "formal_label": formal_label,
            "method": label,
            "label": label,
            "job_id": f"{MECHANISM_LEVEL}_libero_object_swap_{label}",
            "level": MECHANISM_LEVEL,
            "suite": "libero_object_swap",
            "episodes": 3,
            "task_ids_filter": list(MECHANISM_TASKS),
            "episode_seeds": list(MECHANISM_SEEDS),
            "max_chunks": MECHANISM_MAX_CHUNKS,
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
    base.P2_LEVELS = set(base.P2_LEVELS) | {MECHANISM_LEVEL}
    base.P2_ALLOWED_GPUS = {str(index) for index in ALLOWED_GPU_INDICES}
    base.P2_REQUIRED_MOUNT = Path("/mnt/data/shared2")
    base.P2_TORCH_HUB_SEED = (
        Path("/mnt/data/shared2/zhuoli/output/p2_direction_normalized_rbf")
        / "runtime_cache/formal/p2_stage_on_dirnorm_rbf_global_w0_e025/xdg/torch/hub"
    )
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
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=WORKTREE_ROOT,
        text=True,
    ).strip()
    if branch != BRANCH:
        raise RuntimeError(f"unexpected branch: {branch}")
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=WORKTREE_ROOT, text=True
    ).strip()
    with configured_base():
        code_state = base._p2_code_state_sha256()
    return {
        "branch": branch,
        "code_commit": head,
        "code_state_sha256": code_state,
        "protocol_commit": PROTOCOL_COMMIT,
        "recovery_protocol_commit": RECOVERY_PROTOCOL_COMMIT,
        "ledger_recovery_protocol_commit": LEDGER_RECOVERY_PROTOCOL_COMMIT,
        "health_incident_result_commit": HEALTH_INCIDENT_RESULT_COMMIT,
        "run_021_implementation_commit": RUN_021_IMPLEMENTATION_COMMIT,
        "run_022_result_commit": RUN_022_RESULT_COMMIT,
    }


def source_fingerprints() -> dict[str, str]:
    paths = [
        *EXPECTED_ALGORITHM_HASHES,
        "scripts/eds_qd_autoresearch_v2_runner.py",
        "tests/test_eds_qd_autoresearch_v2_runner.py",
    ]
    actual = {path: sha256_path(WORKTREE_ROOT / path) for path in paths}
    if {
        path: actual[path] for path in EXPECTED_ALGORITHM_HASHES
    } != EXPECTED_ALGORITHM_HASHES:
        raise RuntimeError("algorithm/config source differs from run_021 freeze")
    return actual


def checkpoint_fingerprint() -> dict[str, Any]:
    return v1.checkpoint_fingerprint()


def libero_input_fingerprint() -> dict[str, Any]:
    return v1.libero_input_fingerprint()


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


def gpu_reference() -> dict[str, Any]:
    return v1.load_gpu_reference()


def _verified_run_022() -> dict[str, Any]:
    if (
        not RUN_022_ARTIFACT_PATH.is_file()
        or RUN_022_ARTIFACT_PATH.stat().st_mode & 0o222
        or sha256_path(RUN_022_ARTIFACT_PATH) != RUN_022_ARTIFACT_SHA256
    ):
        raise RuntimeError("immutable run_022 PASS artifact identity mismatch")
    payload = json.loads(RUN_022_ARTIFACT_PATH.read_text(encoding="utf-8"))
    if payload.get("passed") is not True or payload.get("credential_match_count") != 0:
        raise RuntimeError("run_022 artifact is not a clean PASS")
    return {
        "path": str(RUN_022_ARTIFACT_PATH),
        "sha256": RUN_022_ARTIFACT_SHA256,
        "scientific_payload_sha256": payload["scientific_payload_sha256"],
    }


def _verified_parent_manifest() -> dict[str, Any]:
    if (
        not MANIFEST_V1_PATH.is_file()
        or MANIFEST_V1_PATH.stat().st_mode & 0o222
        or sha256_path(MANIFEST_V1_PATH) != MANIFEST_V1_SHA256
    ):
        raise RuntimeError("immutable mechanism manifest v1 identity mismatch")
    payload = json.loads(MANIFEST_V1_PATH.read_text(encoding="utf-8"))
    if (
        payload.get("schema")
        != "eds-qd-autoresearch-v2-mechanism-manifest-v1"
        or payload.get("formal_authorized") is not False
        or contains_credential(payload)
    ):
        raise RuntimeError("mechanism manifest v1 is not a clean frozen parent")
    return {
        "path": str(MANIFEST_V1_PATH.resolve(strict=True)),
        "sha256": MANIFEST_V1_SHA256,
        "payload_sha256": payload["payload_sha256"],
    }


def _verified_parent_manifest_v2() -> dict[str, Any]:
    if (
        not MANIFEST_V2_PATH.is_file()
        or MANIFEST_V2_PATH.stat().st_mode & 0o222
        or sha256_path(MANIFEST_V2_PATH) != MANIFEST_V2_SHA256
    ):
        raise RuntimeError("immutable mechanism manifest v2 identity mismatch")
    payload = json.loads(MANIFEST_V2_PATH.read_text(encoding="utf-8"))
    if (
        payload.get("schema")
        != "eds-qd-autoresearch-v2-mechanism-manifest-v2"
        or payload.get("formal_authorized") is not False
        or payload.get("parent_manifest_v1") != _verified_parent_manifest()
        or contains_credential(payload)
    ):
        raise RuntimeError("mechanism manifest v2 is not a clean frozen parent")
    return {
        "path": str(MANIFEST_V2_PATH.resolve(strict=True)),
        "sha256": MANIFEST_V2_SHA256,
        "payload_sha256": payload["payload_sha256"],
    }


def build_manifest_payload() -> dict[str, Any]:
    unbound_jobs = build_jobs(MECHANISM_LEVEL, bind=False)
    payload = {
        "schema": "eds-qd-autoresearch-v2-mechanism-manifest-v3",
        "created_at": now(),
        "provenance": current_provenance(),
        "parent_manifest_v1": _verified_parent_manifest(),
        "parent_manifest_v2": _verified_parent_manifest_v2(),
        "source_fingerprints": source_fingerprints(),
        "checkpoint_fingerprint": checkpoint_fingerprint(),
        "libero_input_fingerprint": libero_input_fingerprint(),
        "runtime_cache_fingerprint": runtime_cache_fingerprint(),
        "gpu_reference": gpu_reference(),
        "run_022_artifact": {
            "path": str(RUN_022_ARTIFACT_PATH),
            "sha256": RUN_022_ARTIFACT_SHA256,
        },
        "suite": "libero_object_swap",
        "strict_perturbations": True,
        "max_episode_steps": 720,
        "profiles": [
            {**profile, "profile_fingerprint": profile_fingerprint(profile)}
            for profile in profiles()
        ],
        "mechanism": {
            "tasks": list(MECHANISM_TASKS),
            "seeds": list(MECHANISM_SEEDS),
            "max_chunks": MECHANISM_MAX_CHUNKS,
            "profiles": [profile["label"] for profile in profiles()],
            "unique_cells": 6,
            "jobs": [
                {
                    "job_id": job["job_id"],
                    "formal_label": job["formal_label"],
                    "config_fingerprint": profile_fingerprint(
                        next(
                            profile
                            for profile in profiles()
                            if profile["label"] == job["formal_label"]
                        )
                    ),
                    "command_sha256": sha256_bytes(
                        canonical(build_main_command(job)).encode("utf-8")
                    ),
                }
                for job in unbound_jobs
            ],
        },
        "prior_global_reservations": PRIOR_GLOBAL_RESERVATIONS,
        "expected_global_attempt_ids": EXPECTED_GLOBAL_ATTEMPT_IDS,
        "void_pre_dispatch_attempt_ids": VOID_GLOBAL_ATTEMPT_IDS,
        "global_reservations_before_recovery": GLOBAL_RESERVATIONS_BEFORE_RECOVERY,
        "recovery_slots_consumed": 6,
        "recovery_slots_remaining": 13,
        "global_reservation_cap": GLOBAL_RESERVATION_CAP,
        "prior_gpu_hours": PRIOR_GPU_HOURS,
        "global_gpu_hour_cap": GLOBAL_GPU_HOUR_CAP,
        "allowed_gpu_indices": sorted(ALLOWED_GPU_INDICES),
        "formal_authorized": False,
        "credential_material_present": False,
    }
    payload["payload_sha256"] = sha256_bytes(canonical(payload).encode("utf-8"))
    if contains_credential(payload):
        raise RuntimeError("mechanism manifest contains credential material")
    return payload


def _write_json(path: Path, payload: dict[str, Any], *, immutable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    if immutable:
        path.chmod(0o444)


def freeze_manifest() -> dict[str, Any]:
    pause_preflight()
    storage_preflight()
    _verified_run_022()
    _verified_parent_manifest()
    _verified_parent_manifest_v2()
    if MANIFEST_PATH.exists():
        raise RuntimeError("mechanism manifest already exists")
    payload = build_manifest_payload()
    _write_json(MANIFEST_PATH, payload, immutable=True)
    return payload


def validate_manifest() -> dict[str, Any]:
    pause_preflight()
    if not MANIFEST_PATH.is_file() or MANIFEST_PATH.stat().st_mode & 0o222:
        raise RuntimeError("immutable mechanism manifest is required")
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    stored_sha = payload.get("payload_sha256")
    unsigned = dict(payload)
    unsigned.pop("payload_sha256", None)
    if stored_sha != sha256_bytes(canonical(unsigned).encode("utf-8")):
        raise RuntimeError("mechanism manifest payload hash mismatch")
    if payload.get("schema") != "eds-qd-autoresearch-v2-mechanism-manifest-v3":
        raise RuntimeError("mechanism manifest schema mismatch")
    if payload.get("formal_authorized") is not False:
        raise RuntimeError("mechanism manifest must forbid formal")
    if payload.get("provenance") != current_provenance():
        raise RuntimeError("mechanism manifest provenance mismatch")
    if payload.get("parent_manifest_v1") != _verified_parent_manifest():
        raise RuntimeError("mechanism manifest parent mismatch")
    if payload.get("parent_manifest_v2") != _verified_parent_manifest_v2():
        raise RuntimeError("mechanism manifest v2 parent mismatch")
    if payload.get("source_fingerprints") != source_fingerprints():
        raise RuntimeError("mechanism manifest source mismatch")
    if payload.get("mechanism", {}).get("tasks") != MECHANISM_TASKS:
        raise RuntimeError("mechanism manifest task mismatch")
    if payload.get("mechanism", {}).get("seeds") != MECHANISM_SEEDS:
        raise RuntimeError("mechanism manifest seed mismatch")
    if payload.get("mechanism", {}).get("unique_cells") != 6:
        raise RuntimeError("mechanism manifest cell-count mismatch")
    _verified_run_022()
    if contains_credential(payload):
        raise RuntimeError("mechanism manifest credential scan failed")
    return payload


def validate_credential() -> dict[str, Any]:
    value = os.environ.get("OPENAI_API_KEY", "").strip()
    if not value or value.lower() == "dummy":
        raise RuntimeError("Stage credential must come from runtime environment")
    return {"present": True, "source": "environment", "value_logged": False}


def read_attempts(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def global_ledger_state(path: Path) -> dict[str, Any]:
    records = read_attempts(path)
    attempts = [
        row
        for row in records
        if row.get("record_type", "episode_attempt") == "episode_attempt"
    ]
    ids = [row.get("attempt_id") for row in attempts]
    if ids != list(range(55, 55 + len(attempts))):
        raise RuntimeError("run_023 attempt IDs are not contiguous from global offset 55")
    events = [row for row in records if row not in attempts]
    if [row.get("ledger_event_id") for row in events] != list(
        range(1, len(events) + 1)
    ):
        raise RuntimeError("run_023 ledger event IDs are not contiguous")
    known = {int(row["attempt_id"]) for row in attempts}
    void_ids: set[int] = set()
    dispatched_ids: set[int] = set()
    for event in events:
        record_type = event.get("record_type")
        event_ids = event.get("attempt_ids")
        if (
            record_type not in {"reservation_void", "phase_dispatch"}
            or not isinstance(event_ids, list)
            or not event_ids
            or any(isinstance(value, bool) or not isinstance(value, int) for value in event_ids)
            or not set(event_ids) <= known
        ):
            raise RuntimeError("invalid run_023 ledger event")
        if record_type == "reservation_void":
            if set(event_ids) & dispatched_ids:
                raise RuntimeError("dispatched reservations cannot be voided")
            void_ids.update(event_ids)
        else:
            if set(event_ids) & (void_ids | dispatched_ids):
                raise RuntimeError("void or dispatched reservations cannot be dispatched")
            dispatched_ids.update(event_ids)
    return {
        "records": records,
        "attempts": attempts,
        "void_attempt_ids": sorted(void_ids),
        "dispatched_attempt_ids": sorted(dispatched_ids),
    }


def append_global_ledger_event(path: Path, event: dict[str, Any]) -> dict[str, Any]:
    state = global_ledger_state(path)
    prepared = {
        "ledger_event_id": 1
        + sum(
            row.get("record_type", "episode_attempt") != "episode_attempt"
            for row in state["records"]
        ),
        "created_at": now(),
        **event,
    }
    if contains_credential(prepared):
        raise RuntimeError("attempt ledger event contains credential material")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical(prepared) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        return global_ledger_state(path)
    except Exception:
        raise RuntimeError("run_023 ledger event failed post-append validation")


def prepare_recovery_ledger(path: Path) -> dict[str, Any]:
    state = global_ledger_state(path)
    ids = [int(row["attempt_id"]) for row in state["attempts"]]
    if ids != VOID_GLOBAL_ATTEMPT_IDS:
        raise RuntimeError("recovery requires only preserved attempt IDs 55-60")
    if state["dispatched_attempt_ids"]:
        raise RuntimeError("preserved attempts unexpectedly reached dispatch")
    if not state["void_attempt_ids"]:
        state = append_global_ledger_event(
            path,
            {
                "record_type": "reservation_void",
                "phase": MECHANISM_LEVEL,
                "attempt_ids": VOID_GLOBAL_ATTEMPT_IDS,
                "reason": "pre_dispatch_global_offset_ledger_helper_failure",
                "protocol_commit": LEDGER_RECOVERY_PROTOCOL_COMMIT,
            },
        )
    if state["void_attempt_ids"] != VOID_GLOBAL_ATTEMPT_IDS:
        raise RuntimeError("preserved attempts are not exactly void IDs 55-60")
    return state


def reserve_attempts(
    path: Path,
    records: list[dict[str, Any]],
    *,
    recovery_of_attempt_ids: list[int] | None = None,
) -> list[dict[str, Any]]:
    state = global_ledger_state(path)
    existing = state["attempts"]
    if PRIOR_GLOBAL_RESERVATIONS + len(existing) + len(records) > GLOBAL_RESERVATION_CAP:
        raise RuntimeError("global episode-attempt hard cap would be exceeded")

    def identity(record: dict[str, Any]) -> tuple[Any, ...]:
        return tuple(
            record.get(key)
            for key in (
                "phase",
                "formal_label",
                "task_id",
                "episode_seed",
                "config_fingerprint",
            )
        )

    active_existing = [
        record
        for record in existing
        if int(record["attempt_id"]) not in state["void_attempt_ids"]
    ]
    old_ids = {identity(record) for record in active_existing}
    new_ids = [identity(record) for record in records]
    if len(new_ids) != len(set(new_ids)):
        raise RuntimeError("duplicate attempt identity in reservation")
    if old_ids & set(new_ids):
        raise RuntimeError("same-cell recovery requires a protocol amendment")
    if recovery_of_attempt_ids is not None:
        if recovery_of_attempt_ids != VOID_GLOBAL_ATTEMPT_IDS:
            raise RuntimeError("recovery must map exactly to void IDs 55-60")
        parents = {int(record["attempt_id"]): record for record in existing}
        if any(
            identity(record) != identity(parents[parent_id])
            for record, parent_id in zip(
                records, recovery_of_attempt_ids, strict=True
            )
        ):
            raise RuntimeError("recovery cells differ from void parent identities")
    prepared = [
        {
            "attempt_id": PRIOR_GLOBAL_RESERVATIONS + len(existing) + offset,
            "record_type": "episode_attempt",
            "started_at": now(),
            **(
                {"recovery_of_attempt_id": recovery_of_attempt_ids[offset - 1]}
                if recovery_of_attempt_ids is not None
                else {}
            ),
            **record,
        }
        for offset, record in enumerate(records, start=1)
    ]
    if any(contains_credential(record) for record in prepared):
        raise RuntimeError("attempt records contain credential material")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for record in prepared:
            handle.write(canonical(record) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    global_ledger_state(path)
    return prepared


def attempt_records(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_label = {profile["label"]: profile for profile in profiles()}
    records: list[dict[str, Any]] = []
    for job in jobs:
        for episode, (task, seed) in enumerate(
            zip(job["task_ids_filter"], job["episode_seeds"], strict=True)
        ):
            records.append(
                {
                    "phase": MECHANISM_LEVEL,
                    "label": job["label"],
                    "formal_label": job["formal_label"],
                    "episode": episode,
                    "task_id": int(task),
                    "episode_seed": int(seed),
                    "config_fingerprint": profile_fingerprint(
                        by_label[job["formal_label"]]
                    ),
                    "code_state_sha256": job["execution_record"][
                        "code_state_sha256"
                    ],
                }
            )
    return records


def admit_gpus(**kwargs: Any) -> dict[str, Any]:
    return v1.admit_gpus(**kwargs)


def _select_gpus(admission: dict[str, Any], requested: str) -> list[str]:
    eligible = [str(value) for value in admission["eligible_gpu_indices"]]
    selected = eligible[:2] if requested == "auto" else [
        item.strip() for item in requested.split(",") if item.strip()
    ]
    if not selected or len(selected) != len(set(selected)) or len(selected) > 2:
        raise RuntimeError("selected GPU list must contain one or two unique devices")
    if not set(selected) <= set(eligible):
        raise RuntimeError("selected GPU failed admission")
    return selected


def run_mechanism(*, gpus: str, timeout_seconds: int) -> int:
    manifest = validate_manifest()
    storage_preflight()
    legacy.validate_runtime_cache(
        target=RUNTIME_CACHE_DIR,
        manifest_path=RUNTIME_CACHE_MANIFEST_PATH,
    )
    prepare_recovery_ledger(ATTEMPT_LEDGER_PATH)
    validate_credential()
    with configured_base():
        if not base._poe_healthcheck():
            raise RuntimeError("real pre-reservation Stage/Poe health check failed")
    jobs = build_jobs(MECHANISM_LEVEL)
    reference = manifest["gpu_reference"]
    admission = admit_gpus(
        reference_peak_vram_mib=float(reference["reference_peak_vram_mib"])
    )
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
        RUN_ROOT / "manifests" / f"gpu_{MECHANISM_LEVEL}_{int(time.time())}.json",
        admission,
    )
    attempts = reserve_attempts(
        ATTEMPT_LEDGER_PATH,
        attempt_records(jobs),
        recovery_of_attempt_ids=VOID_GLOBAL_ATTEMPT_IDS,
    )
    if [record["attempt_id"] for record in attempts] != EXPECTED_GLOBAL_ATTEMPT_IDS:
        raise RuntimeError("mechanism recovery attempt IDs differ from frozen 61-66")
    append_global_ledger_event(
        ATTEMPT_LEDGER_PATH,
        {
            "record_type": "phase_dispatch",
            "phase": MECHANISM_LEVEL,
            "attempt_ids": EXPECTED_GLOBAL_ATTEMPT_IDS,
            "selected_gpu_indices": [int(value) for value in selected],
        },
    )
    pause_preflight()
    with configured_base():
        original_healthcheck = base._poe_healthcheck
        base._poe_healthcheck = lambda: True
        try:
            return base.run_level(
                MECHANISM_LEVEL,
                3,
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


def _finite(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _common_metric_failures(record: dict[str, Any], identity: str) -> list[str]:
    failures: list[str] = []
    if (
        record.get("search_evaluation_count") != 176
        or record.get("score_call_count") != 11
    ):
        failures.append(f"{identity}: search/call accounting mismatch")
    if record.get("nonfinite_count") != 0:
        failures.append(f"{identity}: nonfinite telemetry")
    if not _finite(record.get("action_mask_violation_max")) or float(
        record["action_mask_violation_max"]
    ) > 1.0e-8:
        failures.append(f"{identity}: action-mask violation")
    if int(record.get("gripper_qpos_violation_count", 0)) != 0:
        failures.append(f"{identity}: qpos violation")
    return failures


def candidate_metric_gate(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    failures: list[str] = []
    fallback_count = 0
    active_count = 0
    per_task: dict[str, dict[str, int]] = {}
    if not metrics:
        failures.append("candidate metrics missing")
    for index, record in enumerate(metrics):
        identity = f"{record.get('episode')}/{record.get('global_step', index)}"
        failures.extend(_common_metric_failures(record, identity))
        if record.get("qd_archive_enabled") is not True:
            failures.append(f"{identity}: candidate QD not configured")
        if record.get("qd_degenerate_fallback_policy") != "control_v1":
            failures.append(f"{identity}: candidate fallback policy mismatch")
        task_key = str(record.get("task_id", "unknown"))
        per_task.setdefault(task_key, {"fallback": 0, "active_qd": 0})
        if record.get("qd_degenerate_fallback_used") is True:
            fallback_count += 1
            per_task[task_key]["fallback"] += 1
            if record.get("qd_archive_active_for_chunk") is not False:
                failures.append(f"{identity}: fallback archive remained active")
            if record.get("qd_degenerate_fallback_reason") != "initial_rewards_exactly_equal":
                failures.append(f"{identity}: fallback reason mismatch")
            if not _finite(record.get("qd_degenerate_reward_value")):
                failures.append(f"{identity}: fallback reward value is not finite")
            if record.get("qd_evaluation_count") != 0:
                failures.append(f"{identity}: fallback QD evaluations are not zero")
            if record.get("selected_chunk_population_source") == "qd_archive":
                failures.append(f"{identity}: fallback selected from QD archive")
            if record.get("qd_selected_action_fingerprint") is not None:
                failures.append(f"{identity}: fallback retained QD fingerprint")
        else:
            active_count += 1
            per_task[task_key]["active_qd"] += 1
            if record.get("qd_archive_active_for_chunk") is not True:
                failures.append(f"{identity}: active QD archive flag missing")
            if record.get("qd_evaluation_count") != 176:
                failures.append(f"{identity}: active QD evaluation mismatch")
            if record.get("selected_chunk_population_source") != "qd_archive":
                failures.append(f"{identity}: active QD selected source mismatch")
            if not record.get("qd_selected_action_fingerprint"):
                failures.append(f"{identity}: active QD fingerprint missing")
            if record.get("qd_selected_action_fingerprint") != record.get(
                "qd_global_best_action_fingerprint"
            ):
                failures.append(f"{identity}: active QD global fingerprint mismatch")
            for field in (
                "qd_accounting_violation_count",
                "qd_elite_monotonicity_violation_count",
                "qd_final_selection_mismatch_count",
            ):
                if record.get(field) != 0:
                    failures.append(f"{identity}: active QD {field} nonzero")
    if fallback_count == 0:
        failures.append("candidate missing fallback record")
    if active_count == 0:
        failures.append("candidate missing active QD record")
    return {
        "passed": not failures,
        "fallback_record_count": fallback_count,
        "active_qd_record_count": active_count,
        "per_task_mode_counts": per_task,
        "failures": list(dict.fromkeys(failures)),
    }


def control_metric_gate(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    failures: list[str] = []
    if not metrics:
        failures.append("control metrics missing")
    for index, record in enumerate(metrics):
        identity = f"{record.get('episode')}/{record.get('global_step', index)}"
        failures.extend(_common_metric_failures(record, identity))
        if record.get("qd_archive_enabled") is not False:
            failures.append(f"{identity}: control QD must be disabled")
        if record.get("qd_archive_active_for_chunk") is not False:
            failures.append(f"{identity}: control QD archive active")
        if record.get("qd_degenerate_fallback_used") is not False:
            failures.append(f"{identity}: control fallback used")
        if record.get("qd_evaluation_count") != 0:
            failures.append(f"{identity}: control QD evaluations nonzero")
        if record.get("qd_selected_action_fingerprint") is not None:
            failures.append(f"{identity}: control QD fingerprint present")
    return {"passed": not failures, "failures": list(dict.fromkeys(failures))}


def _read_metrics(job: dict[str, Any]) -> list[dict[str, Any]]:
    with configured_base():
        output = base._output_dir(job)
    path = output / "eds_eval/eds_metrics.jsonl"
    return base._read_jsonl(path) if path.is_file() else []


def _artifact_inventory(root: Path) -> dict[str, Any]:
    return v1.artifact_inventory(root)


def _credential_tree_audit(root: Path) -> dict[str, Any]:
    return v1.credential_tree_audit(root)


def _job_evidence(job: dict[str, Any]) -> dict[str, Any]:
    with configured_base():
        output = base._output_dir(job)
        validity = base._p2_job_validity(job)
    metrics = _read_metrics(job)
    outcomes = base._p2_episode_outcomes(output, int(job["episodes"]))
    parsed = base._parse_results_file(output / "results.txt")
    classifications = qd_audit._classify_failures(outcomes, metrics, output)
    telemetry = qd_audit._telemetry_counts(metrics)
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
        "telemetry_counts": telemetry,
        "credential_audit": _credential_tree_audit(output),
        "artifact_inventory": _artifact_inventory(output),
        "metrics": metrics,
    }


def _metric_values(metrics: list[dict[str, Any]], field: str) -> list[float]:
    values: list[float] = []
    for record in metrics:
        value = record.get(field)
        candidates = value if isinstance(value, list) else [value]
        values.extend(float(item) for item in candidates if _finite(item))
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
    state = global_ledger_state(ATTEMPT_LEDGER_PATH)
    attempts = [
        record
        for record in state["attempts"]
        if int(record["attempt_id"]) not in state["void_attempt_ids"]
    ]
    failures: list[str] = []
    ids = [int(record["attempt_id"]) for record in attempts]
    if ids != EXPECTED_GLOBAL_ATTEMPT_IDS:
        failures.append("attempt IDs differ from frozen recovery 61-66")
    if state["void_attempt_ids"] != VOID_GLOBAL_ATTEMPT_IDS:
        failures.append("void attempt IDs differ from frozen 55-60")
    if state["dispatched_attempt_ids"] != EXPECTED_GLOBAL_ATTEMPT_IDS:
        failures.append("dispatched attempt IDs mismatch")
    expected = {
        (job["formal_label"], int(task), int(seed))
        for job in build_jobs(MECHANISM_LEVEL, bind=False)
        for task, seed in zip(job["task_ids_filter"], job["episode_seeds"], strict=True)
    }
    actual = {
        (record.get("formal_label"), int(record["task_id"]), int(record["episode_seed"]))
        for record in attempts
    }
    if actual != expected:
        failures.append("attempt cells differ from frozen matrix")
    if PRIOR_GLOBAL_RESERVATIONS + len(state["attempts"]) != 66:
        failures.append("global reservation accounting is not 66")
    return {
        "passed": not failures,
        "new_reserved_count": len(state["attempts"]),
        "scientific_recovery_count": len(attempts),
        "global_reserved_count": PRIOR_GLOBAL_RESERVATIONS + len(state["attempts"]),
        "attempt_ids": ids,
        "failures": failures,
    }


def audit_mechanism() -> dict[str, Any]:
    manifest = validate_manifest()
    jobs = build_jobs(MECHANISM_LEVEL)
    evidence = [_job_evidence(job) for job in jobs]
    control = next(item for item in evidence if item["formal_label"] == profiles()[0]["label"])
    candidate = next(item for item in evidence if item["formal_label"] == profiles()[1]["label"])
    failures: list[str] = []
    for item in evidence:
        if item["valid"] is not True:
            failures.append(f"invalid job {item['formal_label']}: {item['failure_reason']}")
        if item["credential_audit"]["passed"] is not True:
            failures.append(f"credential audit failed for {item['formal_label']}")
    control_gate = control_metric_gate(control["metrics"])
    candidate_gate = candidate_metric_gate(candidate["metrics"])
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
        failures.append("one or more jobs produced a disallowed safety outcome")
    for item in evidence:
        telemetry = item["telemetry_counts"]
        if (
            telemetry.get("nonfinite_count")
            or telemetry.get("action_mask_violation_count")
            or telemetry.get("execution_qpos_error_episodes")
            or telemetry.get("qd_fallback_count")
        ):
            failures.append(f"{item['formal_label']}: legacy safety fallback telemetry nonzero")
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
    attempts = _attempt_audit()
    failures.extend(attempts["failures"])
    status = _status_summary()
    cumulative_gpu_hours = (
        PRIOR_GPU_HOURS + float(status["gpu_hours"])
        if _finite(status.get("gpu_hours"))
        else None
    )
    if cumulative_gpu_hours is None or cumulative_gpu_hours > GLOBAL_GPU_HOUR_CAP:
        failures.append("global GPU-hour cap accounting failed")
    root_credentials = _credential_tree_audit(RUN_ROOT)
    failures.extend(root_credentials["failures"])
    payload = {
        "schema": "eds-qd-autoresearch-v2-mechanism-audit-v1",
        "created_at": now(),
        "manifest_path": str(MANIFEST_PATH),
        "manifest_sha256": sha256_path(MANIFEST_PATH),
        "manifest_payload_sha256": manifest["payload_sha256"],
        "jobs": [
            {key: value for key, value in item.items() if key != "metrics"}
            for item in evidence
        ],
        "task_outcomes": {
            item["formal_label"]: item["outcomes"] for item in evidence
        },
        "failure_classification_by_task": {
            item["formal_label"]: item["failure_classification_by_task"]
            for item in evidence
        },
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
        "formal_authorized": False,
    }
    if contains_credential(payload):
        raise RuntimeError("mechanism audit contains credential material")
    _write_json(AUDIT_PATH, payload, immutable=True)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("print-plan")
    subparsers.add_parser("freeze-manifest")
    subparsers.add_parser("validate-manifest")
    run_parser = subparsers.add_parser("run-mechanism")
    run_parser.add_argument("--gpus", default="auto")
    run_parser.add_argument("--timeout-seconds", type=int, default=28800)
    subparsers.add_parser("audit-mechanism")
    args = parser.parse_args()
    if args.command == "print-plan":
        print(json.dumps(build_jobs(MECHANISM_LEVEL, bind=False), indent=2, sort_keys=True))
        return 0
    if args.command == "freeze-manifest":
        payload = freeze_manifest()
        print(json.dumps({"passed": True, "payload_sha256": payload["payload_sha256"]}))
        return 0
    if args.command == "validate-manifest":
        payload = validate_manifest()
        print(json.dumps({"passed": True, "payload_sha256": payload["payload_sha256"]}))
        return 0
    if args.command == "run-mechanism":
        return run_mechanism(gpus=args.gpus, timeout_seconds=args.timeout_seconds)
    if args.command == "audit-mechanism":
        payload = audit_mechanism()
        print(json.dumps({"passed": payload["passed"], "hard_failures": payload["hard_failures"]}))
        return 0 if payload["passed"] else 1
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
