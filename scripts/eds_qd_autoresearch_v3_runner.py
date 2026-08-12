#!/usr/bin/env python3
"""Protocol-locked v3 runner for the H4 global-quality-anchor mechanism."""

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

import eds_qd_autoresearch_v2_runner as v2


v1 = v2.v1
qd_audit = v2.qd_audit
legacy = v2.legacy
base = v2.base

MECHANISM_LEVEL = "eds_qd_autoresearch_v3_mechanism"
BRANCH = "exp/eds-qd-autoresearch-libero-swap-ood"
PROTOCOL_COMMIT = "bdb1b161622e6289ebbd918c5ddc9f87dacc9655"
RUN_031_IMPLEMENTATION_COMMIT = "f453e645828d8076d72eee70c84669b385573b70"
RUN_032_RESULT_COMMIT = "1a29142"
RUN_032_ARTIFACT_SHA256 = (
    "31dd437c377c41af369336f6161f194012143dbcf847a2ae150ac82fdf3de24b"
)
RUN_032_PAYLOAD_SHA256 = (
    "f147193e1589b09c178706c0c94890242393e84a12fe5612b151bb7f0ab8ddf4"
)
EXPERIMENT_ROOT = Path(
    "/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood"
)
RUN_ROOT = EXPERIMENT_ROOT / "run_033_global_quality_anchor_online_mechanism"
OUTPUT_LINK = WORKTREE_ROOT / "outputs"
MANIFEST_PATH = RUN_ROOT / "manifests/mechanism_manifest.json"
ATTEMPT_LEDGER_PATH = RUN_ROOT / "manifests/episode_attempt_ledger.jsonl"
AUDIT_PATH = RUN_ROOT / "analysis/mechanism_audit.json"
RUN_032_ARTIFACT_PATH = (
    EXPERIMENT_ROOT
    / "run_032_global_quality_anchor_cpu_mechanism/analysis/mechanism_preflight.v1.json"
)
RUNTIME_CACHE_DIR = v2.RUNTIME_CACHE_DIR
RUNTIME_CACHE_MANIFEST_PATH = v2.RUNTIME_CACHE_MANIFEST_PATH
PAUSE_SENTINEL = WORKTREE_ROOT / ".autoresearch/PAUSE"
PROTECTED_UNTRACKED = "docs/01_specs/2026-08-10-eds-qd-stage-guidance-transition-design.md"
ALLOWED_STORAGE_PREFIX = v2.ALLOWED_STORAGE_PREFIX
MIN_FREE_BYTES = v2.MIN_FREE_BYTES
ALLOWED_GPU_INDICES = set(range(8))
PRIOR_GLOBAL_RESERVATIONS = 66
GLOBAL_RESERVATION_CAP = 143
GLOBAL_GPU_HOUR_CAP = 48.0
PRIOR_GPU_HOURS = 3.7471009444444445
RECOVERY_RESERVE = 19
MECHANISM_TASKS = [3, 8, 9]
MECHANISM_SEEDS = [955865, 522754, 845886]
MECHANISM_MAX_CHUNKS = 16
EXPECTED_GLOBAL_ATTEMPT_IDS = list(range(67, 73))
EXPECTED_ALGORITHM_HASHES = {
    "configs/config.yaml": "f8a9f07d52ea69ee3a69202ab5b89b4214353208ec27961ebcaef9b3d5b02d57",
    "core/qd_ed.py": "4a43cc2db1f1f87eaabf2146058347f119f6059beb4bdf2e67e36f9b6680b653",
    "core/rdt_policy_steer.py": "bdc523f602453c402aa290ed40e495952578a5e028e0c9374365161255e7cd41",
    "core/eds_eval_metrics.py": "870636edbaf1023b6c8a71f7f0778e6efa29833fc24f64b651e48714a0d61a31",
}
RUNNER_DEPENDENCY_HASHES = {
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
QD_CONFIG_FIELDS = (
    "qd_archive_mode",
    "qd_degenerate_fallback_policy",
    "qd_descriptor",
    "qd_grid_shape",
    "qd_cell_capacity",
    "qd_parent_sampling",
    "qd_global_quality_anchor_count",
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

now = v2.now
canonical = v2.canonical
sha256_bytes = v2.sha256_bytes
sha256_path = v2.sha256_path
contains_credential = v2.contains_credential
hydra_value = v2.hydra_value
checkpoint_fingerprint = v2.checkpoint_fingerprint
libero_input_fingerprint = v2.libero_input_fingerprint
gpu_reference = v2.gpu_reference
admit_gpus = v2.admit_gpus


def profiles() -> list[dict[str, Any]]:
    return [
        v1._profile(
            "p2_stage_on_abs_rbf_control",
            "control",
            qd_archive_mode="none",
            qd_global_quality_anchor_count=0,
            qd_degenerate_fallback_policy="none",
        ),
        v1._profile(
            "eds_qd_global_quality_anchor_v1",
            "candidate",
            qd_archive_mode="grid_archive",
            qd_parent_sampling="sparse_priority",
            qd_bounds_update_policy="causal_envelope_v1",
            qd_global_quality_anchor_count=1,
            qd_degenerate_fallback_policy="none",
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
        return "run_033_global_quality_anchor_online_mechanism"
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
        token.split("=", 1)[0].lstrip("+") for token in command if "=" in token
    ]
    if len(override_keys) != len(set(override_keys)):
        raise RuntimeError("v3 command contains duplicate Hydra overrides")
    if contains_credential(command):
        raise RuntimeError("v3 command contains credential material")
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
        raise ValueError("v3 runner only supports the online mechanism level")
    if episodes is not None and int(episodes) != 3:
        raise ValueError("v3 mechanism requires exactly 3 episodes per profile")
    jobs = []
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
    base.P2_TORCH_HUB_SEED = v2.base.P2_TORCH_HUB_SEED
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
        "run_031_implementation_commit": RUN_031_IMPLEMENTATION_COMMIT,
        "run_032_result_commit": RUN_032_RESULT_COMMIT,
    }


def source_fingerprints() -> dict[str, str]:
    paths = [
        *EXPECTED_ALGORITHM_HASHES,
        *RUNNER_DEPENDENCY_HASHES,
        "scripts/eds_qd_autoresearch_v3_runner.py",
        "tests/test_eds_qd_autoresearch_v3_runner.py",
    ]
    actual = {path: sha256_path(WORKTREE_ROOT / path) for path in paths}
    frozen = {**EXPECTED_ALGORITHM_HASHES, **RUNNER_DEPENDENCY_HASHES}
    if {path: actual[path] for path in frozen} != frozen:
        raise RuntimeError("algorithm/config/runner dependency differs from freeze")
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


def verified_run_032() -> dict[str, Any]:
    if (
        not RUN_032_ARTIFACT_PATH.is_file()
        or RUN_032_ARTIFACT_PATH.stat().st_mode & 0o222
        or sha256_path(RUN_032_ARTIFACT_PATH) != RUN_032_ARTIFACT_SHA256
    ):
        raise RuntimeError("immutable Run032 PASS artifact identity mismatch")
    payload = json.loads(RUN_032_ARTIFACT_PATH.read_text(encoding="utf-8"))
    if (
        payload.get("passed") is not True
        or payload.get("credential_match_count") != 0
        or payload.get("scientific_payload_sha256") != RUN_032_PAYLOAD_SHA256
    ):
        raise RuntimeError("Run032 artifact is not a clean frozen PASS")
    return {
        "path": str(RUN_032_ARTIFACT_PATH),
        "sha256": RUN_032_ARTIFACT_SHA256,
        "scientific_payload_sha256": RUN_032_PAYLOAD_SHA256,
    }


def build_manifest_payload() -> dict[str, Any]:
    jobs = build_jobs(MECHANISM_LEVEL, bind=False)
    payload = {
        "schema": "eds-qd-autoresearch-v3-mechanism-manifest-v1",
        "created_at": now(),
        "provenance": current_provenance(),
        "source_fingerprints": source_fingerprints(),
        "checkpoint_fingerprint": checkpoint_fingerprint(),
        "libero_input_fingerprint": libero_input_fingerprint(),
        "runtime_cache_fingerprint": runtime_cache_fingerprint(),
        "gpu_reference": gpu_reference(),
        "run_032_artifact": verified_run_032(),
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
                for job in jobs
            ],
        },
        "prior_global_reservations": PRIOR_GLOBAL_RESERVATIONS,
        "expected_global_attempt_ids": EXPECTED_GLOBAL_ATTEMPT_IDS,
        "global_reservation_cap": GLOBAL_RESERVATION_CAP,
        "prior_gpu_hours": PRIOR_GPU_HOURS,
        "global_gpu_hour_cap": GLOBAL_GPU_HOUR_CAP,
        "recovery_reserve": RECOVERY_RESERVE,
        "allowed_gpu_indices": sorted(ALLOWED_GPU_INDICES),
        "formal_authorized": False,
        "credential_material_present": False,
    }
    payload["payload_sha256"] = sha256_bytes(canonical(payload).encode("utf-8"))
    if contains_credential(payload):
        raise RuntimeError("Run033 manifest contains credential material")
    return payload


def _write_json(path: Path, payload: dict[str, Any], *, immutable: bool = False) -> None:
    v2._write_json(path, payload, immutable=immutable)


def freeze_manifest() -> dict[str, Any]:
    pause_preflight()
    storage_preflight()
    verified_run_032()
    if MANIFEST_PATH.exists():
        raise RuntimeError("Run033 mechanism manifest already exists")
    payload = build_manifest_payload()
    _write_json(MANIFEST_PATH, payload, immutable=True)
    return payload


def validate_manifest() -> dict[str, Any]:
    pause_preflight()
    if not MANIFEST_PATH.is_file() or MANIFEST_PATH.stat().st_mode & 0o222:
        raise RuntimeError("immutable Run033 mechanism manifest is required")
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    stored_sha = payload.get("payload_sha256")
    unsigned = dict(payload)
    unsigned.pop("payload_sha256", None)
    if stored_sha != sha256_bytes(canonical(unsigned).encode("utf-8")):
        raise RuntimeError("Run033 manifest payload hash mismatch")
    if payload.get("schema") != "eds-qd-autoresearch-v3-mechanism-manifest-v1":
        raise RuntimeError("Run033 manifest schema mismatch")
    if payload.get("formal_authorized") is not False:
        raise RuntimeError("Run033 manifest must forbid formal")
    if payload.get("provenance") != current_provenance():
        raise RuntimeError("Run033 manifest provenance mismatch")
    if payload.get("source_fingerprints") != source_fingerprints():
        raise RuntimeError("Run033 manifest source mismatch")
    if payload.get("run_032_artifact") != verified_run_032():
        raise RuntimeError("Run033 manifest Run032 mismatch")
    if payload.get("checkpoint_fingerprint") != checkpoint_fingerprint():
        raise RuntimeError("Run033 manifest checkpoint mismatch")
    if payload.get("libero_input_fingerprint") != libero_input_fingerprint():
        raise RuntimeError("Run033 manifest LIBERO input mismatch")
    if payload.get("runtime_cache_fingerprint") != runtime_cache_fingerprint():
        raise RuntimeError("Run033 manifest runtime cache mismatch")
    if payload.get("gpu_reference") != gpu_reference():
        raise RuntimeError("Run033 manifest GPU reference mismatch")
    expected_profiles = [
        {**profile, "profile_fingerprint": profile_fingerprint(profile)}
        for profile in profiles()
    ]
    if payload.get("profiles") != expected_profiles:
        raise RuntimeError("Run033 manifest profile mismatch")
    mechanism = payload.get("mechanism", {})
    if (
        mechanism.get("tasks") != MECHANISM_TASKS
        or mechanism.get("seeds") != MECHANISM_SEEDS
        or mechanism.get("unique_cells") != 6
    ):
        raise RuntimeError("Run033 manifest matrix mismatch")
    if (
        payload.get("prior_global_reservations") != PRIOR_GLOBAL_RESERVATIONS
        or payload.get("expected_global_attempt_ids")
        != EXPECTED_GLOBAL_ATTEMPT_IDS
        or payload.get("global_reservation_cap") != GLOBAL_RESERVATION_CAP
        or payload.get("prior_gpu_hours") != PRIOR_GPU_HOURS
        or payload.get("global_gpu_hour_cap") != GLOBAL_GPU_HOUR_CAP
        or payload.get("recovery_reserve") != RECOVERY_RESERVE
    ):
        raise RuntimeError("Run033 manifest budget mismatch")
    if contains_credential(payload):
        raise RuntimeError("Run033 manifest credential scan failed")
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
    records = read_ledger(path)
    attempts = [row for row in records if row.get("record_type") == "episode_attempt"]
    ids = [row.get("attempt_id") for row in attempts]
    if ids != EXPECTED_GLOBAL_ATTEMPT_IDS[: len(ids)]:
        raise RuntimeError("Run033 attempt IDs are not contiguous from 67")
    events = [row for row in records if row.get("record_type") != "episode_attempt"]
    if [row.get("ledger_event_id") for row in events] != list(
        range(1, len(events) + 1)
    ):
        raise RuntimeError("Run033 ledger event IDs are not contiguous")
    known = {int(row["attempt_id"]) for row in attempts}
    dispatched: set[int] = set()
    for event in events:
        if (
            event.get("record_type") != "phase_dispatch"
            or not isinstance(event.get("attempt_ids"), list)
            or not set(event["attempt_ids"]) <= known
            or set(event["attempt_ids"]) & dispatched
        ):
            raise RuntimeError("invalid Run033 ledger event")
        dispatched.update(int(value) for value in event["attempt_ids"])
    return {
        "records": records,
        "attempts": attempts,
        "dispatched_attempt_ids": sorted(dispatched),
    }


def reserve_attempts(path: Path, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    state = ledger_state(path)
    if state["records"]:
        raise RuntimeError("Run033 ledger already contains reservations")
    if len(records) != 6:
        raise RuntimeError("Run033 requires exactly six reservation records")
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
        raise RuntimeError("duplicate Run033 reservation identity")
    if PRIOR_GLOBAL_RESERVATIONS + len(records) > GLOBAL_RESERVATION_CAP:
        raise RuntimeError("global episode-attempt cap would be exceeded")
    prepared = [
        {
            "attempt_id": PRIOR_GLOBAL_RESERVATIONS + offset,
            "record_type": "episode_attempt",
            "started_at": now(),
            **record,
        }
        for offset, record in enumerate(records, start=1)
    ]
    if any(contains_credential(row) for row in prepared):
        raise RuntimeError("Run033 attempt records contain credential material")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        for row in prepared:
            handle.write(canonical(row) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    ledger_state(path)
    return prepared


def append_dispatch_event(
    path: Path,
    attempt_ids: list[int],
    selected_gpu_indices: list[int],
) -> dict[str, Any]:
    state = ledger_state(path)
    if state["dispatched_attempt_ids"]:
        raise RuntimeError("Run033 dispatch already recorded")
    event = {
        "ledger_event_id": 1,
        "record_type": "phase_dispatch",
        "created_at": now(),
        "phase": MECHANISM_LEVEL,
        "attempt_ids": list(attempt_ids),
        "selected_gpu_indices": list(selected_gpu_indices),
    }
    if contains_credential(event):
        raise RuntimeError("Run033 dispatch event contains credential material")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical(event) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return ledger_state(path)


def attempt_records(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_label = {profile["label"]: profile for profile in profiles()}
    records = []
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
                    "code_state_sha256": job["execution_record"]["code_state_sha256"],
                }
            )
    return records


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


def run_mechanism(*, gpus: str, timeout_seconds: int) -> int:
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
    attempts = reserve_attempts(ATTEMPT_LEDGER_PATH, attempt_records(jobs))
    if [row["attempt_id"] for row in attempts] != EXPECTED_GLOBAL_ATTEMPT_IDS:
        raise RuntimeError("Run033 attempt IDs differ from frozen 67-72")
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
    failures = []
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
    activation_count = 0
    rescue_count = 0
    per_task: dict[str, dict[str, int]] = {}
    if not metrics:
        failures.append("candidate metrics missing")
    expected_sources = {
        "elite": 0,
        "anchor_offspring": 0,
        "weighted_offspring": 0,
        "qd_global_quality_anchor_offspring": 10,
        "qd_archive_offspring": 150,
    }
    for index, record in enumerate(metrics):
        identity = f"{record.get('episode')}/{record.get('global_step', index)}"
        failures.extend(_common_metric_failures(record, identity))
        task = str(record.get("task_id", "unknown"))
        per_task.setdefault(task, {"records": 0, "activations": 0, "rescues": 0})
        per_task[task]["records"] += 1
        if record.get("qd_archive_enabled") is not True or record.get(
            "qd_archive_active_for_chunk"
        ) is not True:
            failures.append(f"{identity}: candidate QD archive inactive")
        if record.get("qd_degenerate_fallback_policy") != "none" or record.get(
            "qd_degenerate_fallback_used"
        ) is not False:
            failures.append(f"{identity}: candidate fallback contract mismatch")
        if record.get("qd_global_quality_anchor_count") != 1:
            failures.append(f"{identity}: candidate configured count mismatch")
        activations = record.get("qd_global_quality_anchor_activation_count")
        if activations != 10:
            failures.append(f"{identity}: candidate anchor activation mismatch")
        else:
            activation_count += 10
            per_task[task]["activations"] += 10
        rescues = record.get("qd_global_quality_anchor_rescue_count")
        if isinstance(rescues, bool) or not isinstance(rescues, int) or not 0 <= rescues <= 10:
            failures.append(f"{identity}: candidate rescue count invalid")
            rescues = 0
        rescue_count += int(rescues)
        per_task[task]["rescues"] += int(rescues)
        fields = (
            record.get("qd_global_quality_anchor_cell_by_iter"),
            record.get("qd_global_quality_anchor_fingerprint_by_iter"),
            record.get("qd_global_quality_anchor_rescued_by_iter"),
            record.get("qd_sparse_parent_slots_by_cell_by_iter"),
            record.get("qd_parent_slots_by_cell_by_iter"),
        )
        if any(not isinstance(value, list) or len(value) != 10 for value in fields):
            failures.append(f"{identity}: candidate per-iteration telemetry incomplete")
        else:
            cells, fingerprints, rescued_flags, sparse_maps, total_maps = fields
            observed_rescues = 0
            for iteration, (cell, fingerprint, rescued, sparse, total) in enumerate(
                zip(cells, fingerprints, rescued_flags, sparse_maps, total_maps, strict=True)
            ):
                prefix = f"{identity}/{iteration}"
                if not isinstance(cell, int) or not fingerprint:
                    failures.append(f"{prefix}: anchor identity missing")
                    continue
                if not isinstance(sparse, dict) or sum(sparse.values()) != 15:
                    failures.append(f"{prefix}: sparse slots mismatch")
                    continue
                if not isinstance(total, dict) or sum(total.values()) != 16:
                    failures.append(f"{prefix}: total slots mismatch")
                    continue
                sparse_count = sparse.get(str(cell))
                total_count = total.get(str(cell))
                if not isinstance(sparse_count, int) or total_count != sparse_count + 1:
                    failures.append(f"{prefix}: anchor total is not sparse plus one")
                expected_rescued = sparse_count == 0
                if rescued is not expected_rescued:
                    failures.append(f"{prefix}: rescue flag mismatch")
                observed_rescues += int(expected_rescued)
            if observed_rescues != rescues:
                failures.append(f"{identity}: rescue aggregate mismatch")
        if record.get("qd_evaluation_count") != 176:
            failures.append(f"{identity}: candidate QD evaluation mismatch")
        if record.get("selected_chunk_population_source") != "qd_archive":
            failures.append(f"{identity}: candidate selected source mismatch")
        if not record.get("qd_selected_action_fingerprint") or record.get(
            "qd_selected_action_fingerprint"
        ) != record.get("qd_global_best_action_fingerprint"):
            failures.append(f"{identity}: candidate final fingerprint mismatch")
        if record.get("parent_count_by_source") != expected_sources:
            failures.append(f"{identity}: candidate parent source accounting mismatch")
        for field in (
            "qd_accounting_violation_count",
            "qd_elite_monotonicity_violation_count",
            "qd_final_selection_mismatch_count",
        ):
            if record.get(field) != 0:
                failures.append(f"{identity}: candidate {field} nonzero")
    if metrics and rescue_count == 0:
        failures.append("candidate observed no real rescue")
    return {
        "passed": not failures,
        "record_count": len(metrics),
        "activation_count": activation_count,
        "rescue_count": rescue_count,
        "rescue_rate": rescue_count / activation_count if activation_count else None,
        "per_task": per_task,
        "failures": list(dict.fromkeys(failures)),
    }


def control_metric_gate(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    failures = []
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


def task_success_summary(
    control_outcomes: dict[str, str],
    candidate_outcomes: dict[str, str],
) -> dict[str, Any]:
    control = sorted(int(task) for task, value in control_outcomes.items() if value == "success")
    candidate = sorted(
        int(task) for task, value in candidate_outcomes.items() if value == "success"
    )
    control_set, candidate_set = set(control), set(candidate)
    return {
        "control_success_tasks": control,
        "candidate_success_tasks": candidate,
        "gained_tasks": sorted(candidate_set - control_set),
        "lost_tasks": sorted(control_set - candidate_set),
        "retained_tasks": sorted(control_set & candidate_set),
        "control_success_count": len(control),
        "candidate_success_count": len(candidate),
        "candidate_minus_control": len(candidate) - len(control),
        "gap_to_five": max(0, 5 - len(candidate)),
    }


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
        "credential_audit": v1.credential_tree_audit(output),
        "artifact_inventory": v1.artifact_inventory(output),
        "metrics": metrics,
    }


def _metric_values(metrics: list[dict[str, Any]], field: str) -> list[float]:
    values = []
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
    state = ledger_state(ATTEMPT_LEDGER_PATH)
    failures = []
    ids = [int(row["attempt_id"]) for row in state["attempts"]]
    if ids != EXPECTED_GLOBAL_ATTEMPT_IDS:
        failures.append("attempt IDs differ from frozen 67-72")
    if state["dispatched_attempt_ids"] != EXPECTED_GLOBAL_ATTEMPT_IDS:
        failures.append("dispatched attempt IDs mismatch")
    expected = {
        (job["formal_label"], int(task), int(seed))
        for job in build_jobs(MECHANISM_LEVEL, bind=False)
        for task, seed in zip(job["task_ids_filter"], job["episode_seeds"], strict=True)
    }
    actual = {
        (row.get("formal_label"), int(row["task_id"]), int(row["episode_seed"]))
        for row in state["attempts"]
    }
    if actual != expected:
        failures.append("attempt cells differ from frozen matrix")
    return {
        "passed": not failures,
        "new_reserved_count": len(state["attempts"]),
        "global_reserved_count": PRIOR_GLOBAL_RESERVATIONS + len(state["attempts"]),
        "attempt_ids": ids,
        "failures": failures,
    }


def audit_mechanism() -> dict[str, Any]:
    manifest = validate_manifest()
    evidence = [_job_evidence(job) for job in build_jobs(MECHANISM_LEVEL)]
    control = next(item for item in evidence if item["formal_label"] == profiles()[0]["label"])
    candidate = next(item for item in evidence if item["formal_label"] == profiles()[1]["label"])
    failures = []
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
    task_summary = task_success_summary(control["outcomes"], candidate["outcomes"])
    if task_summary["lost_tasks"]:
        failures.append("candidate lost one or more control-success tasks")
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
    root_credentials = v1.credential_tree_audit(RUN_ROOT)
    failures.extend(root_credentials["failures"])
    payload = {
        "schema": "eds-qd-autoresearch-v3-mechanism-audit-v1",
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
        "task_success_summary": task_summary,
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
        raise RuntimeError("Run033 audit contains credential material")
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
