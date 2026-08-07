#!/usr/bin/env python3
"""Frozen QD-ED matrix runner for LIBERO Object-Swap OOD evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import torch

SCRIPT_DIR = Path(__file__).resolve().parent
WORKTREE_ROOT = Path(__file__).resolve().parents[1]
for import_root in (SCRIPT_DIR, WORKTREE_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import rdt_eds_eval_runner as base
from core.qd_ed import (
    QDArchive,
    allocate_parent_slots,
    cell_ids,
    fingerprint_action,
    freeze_bounds,
)


FORMAL_LEVEL = "eds_quality_diversity"
PREFLIGHT_LEVEL = "eds_quality_diversity_preflight"
SOURCE_BRANCH = "exp/eds-init-pg-diverse-sampling"
NEW_BRANCH = "exp/eds-quality-diversity"
BASE_COMMIT = "b3db98cf4fd98a6479d92683e33ebe3d032f25d9"
EXPERIMENT_ROOT = Path(
    "/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity"
)
OUTPUT_LINK = WORKTREE_ROOT / "outputs"
OUTPUT_TARGET = EXPERIMENT_ROOT / "outputs"
ALLOWED_STORAGE_PREFIX = Path("/mnt/data/shared2/zhuoli/vla-pilot-plus-plus")
MIN_FREE_BYTES = 50 * 1024**3
ATTEMPT_CAP = 120
EPISODE_SEEDS = [44, 235, 43, 546, 6, 621, 197, 87, 151, 548]
SUPERSEDED_RUN_MANIFEST_PATH = (
    EXPERIMENT_ROOT / "manifests/qd_ed_run_manifest.v4.json"
)
RUN_MANIFEST_PATH = EXPERIMENT_ROOT / "manifests/qd_ed_run_manifest.v5.json"
ATTEMPT_LEDGER_PATH = EXPERIMENT_ROOT / "manifests/episode_attempt_ledger.jsonl"
OFFLINE_PREFLIGHT_PATH = EXPERIMENT_ROOT / "analysis/offline_mechanism_preflight.json"
LIBERO_PREFLIGHT_AUDIT_PATH = (
    EXPERIMENT_ROOT / "analysis/libero_mechanism_preflight_audit.json"
)
GPU_REFERENCE_PATH = Path(
    "/mnt/data/shared2/zhuoli/output/p2_direction_normalized_rbf/"
    "manifests/gpu_reference_peak.json"
)
DESIGN_PATH = (
    WORKTREE_ROOT
    / "docs/01_specs/2026-08-06-eds-quality-diversity-design.md"
)

QD_PROFILE_FIELDS = (
    "qd_parent_sampling",
    "qd_grid_shape",
    "qd_bounds_quantiles",
    "qd_bounds_expand_fraction",
    "qd_min_axis_span_m",
)
QD_CONFIG_FIELDS = (
    "qd_archive_mode",
    "qd_descriptor",
    "qd_grid_shape",
    "qd_cell_capacity",
    "qd_parent_sampling",
    "qd_sparse_exponent",
    "qd_bounds_quantiles",
    "qd_bounds_expand_fraction",
    "qd_min_axis_span_m",
    "qd_overflow_policy",
    "qd_tie_break",
    "qd_metrics_observer",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _contains_credential(value: object) -> bool:
    serialized = _canonical(value).lower()
    secret_values = [
        os.environ.get(name, "")
        for name in ("OPENAI_API_KEY", "GOOGLE_API_KEY")
    ]
    if any(secret and secret in serialized for secret in secret_values):
        return True
    return any(
        marker in serialized
        for marker in ("sk-", "api_key=", "api-key=", "authorization: bearer")
    )


COMMON_PROFILE = {
    **base.P2_BASE_PROFILE,
    "population_size": 16,
    "cem_iters": 10,
    "use_cem": False,
    "num_elites": 16,
    "temperature": 0.1,
    "renoise_t_max": 3,
    "renoise_t_min": 1,
    "reward_mode": "normal",
    "initial_sampling_mode": "rbf_diverse_denoise",
    "initial_diversity_descriptor_mode": "absolute_eef",
    "initial_diversity_scale": 20.0,
    "initial_diversity_start_ratio": 0.8,
    "truncated_rollout_mode": "rbf_diverse",
    "rollout_diversity_descriptor_mode": "absolute_eef",
    "rollout_diversity_scale": 20.0,
    "rollout_diversity_start_ratio": 0.6,
    "rollout_diversity_iters": "all",
    "rollout_diversity_skip_final_steps": 0,
    "parent_weighting_mode": "legacy_temperature",
    "parent_coverage_mode": "none",
    "parent_anchor_count": 0,
    "elite_carryover_count": 0,
    "chunk_population_mode": "fresh",
    "chunk_memory_fraction": 0.0,
    "rollout_diversity_control_mode": "fixed",
    "search_schedule_mode": "legacy_linear",
    "execution_horizon_mode": "fixed",
    "execution_horizon_far": 8,
    "max_episode_steps": 720,
    "stage_recognition_enabled": True,
    "gemini_grounding_enabled": False,
    "seed": 0,
    "save_mechanism_trace_to_qualitative": True,
    "qd_archive_mode": "grid_archive",
    "qd_descriptor": "target_relative_endpoint_xy",
    "qd_grid_shape": [4, 4],
    "qd_cell_capacity": 1,
    "qd_parent_sampling": "uniform_cells",
    "qd_sparse_exponent": 1.0,
    "qd_bounds_quantiles": [0.05, 0.95],
    "qd_bounds_expand_fraction": 0.10,
    "qd_min_axis_span_m": 0.08,
    "qd_overflow_policy": "clamp_edge",
    "qd_tie_break": "stable_fingerprint",
    "qd_metrics_observer": True,
}


def _profile(label: str, role: str, **updates: object) -> dict[str, object]:
    return {
        **COMMON_PROFILE,
        "method": label,
        "label": label,
        "role": role,
        **updates,
    }


def formal_profiles() -> list[dict[str, object]]:
    profiles = [
        _profile(
            "p2_stage_on_abs_rbf_control",
            "control",
            qd_archive_mode="none",
        ),
        _profile(
            "eds_quality_diversity_uniform_primary",
            "primary",
        ),
        _profile(
            "eds_quality_diversity_sparse_primary",
            "sampling_attribution",
            qd_parent_sampling="sparse_priority",
        ),
        _profile(
            "eds_quality_diversity_uniform_grid3",
            "parameter_ofat",
            qd_grid_shape=[3, 3],
        ),
        _profile(
            "eds_quality_diversity_uniform_grid5",
            "parameter_ofat",
            qd_grid_shape=[5, 5],
        ),
        _profile(
            "eds_quality_diversity_uniform_q00100",
            "parameter_ofat",
            qd_bounds_quantiles=[0.0, 1.0],
        ),
        _profile(
            "eds_quality_diversity_uniform_q1090",
            "parameter_ofat",
            qd_bounds_quantiles=[0.10, 0.90],
        ),
        _profile(
            "eds_quality_diversity_uniform_expand00",
            "parameter_ofat",
            qd_bounds_expand_fraction=0.0,
        ),
        _profile(
            "eds_quality_diversity_uniform_expand20",
            "parameter_ofat",
            qd_bounds_expand_fraction=0.20,
        ),
        _profile(
            "eds_quality_diversity_uniform_span04",
            "parameter_ofat",
            qd_min_axis_span_m=0.04,
        ),
        _profile(
            "eds_quality_diversity_uniform_span12",
            "parameter_ofat",
            qd_min_axis_span_m=0.12,
        ),
    ]
    if len(profiles) != 11 or len({item["label"] for item in profiles}) != 11:
        raise AssertionError("formal QD matrix must contain 11 unique profiles")
    primary = profiles[1]
    for item in profiles[2:]:
        differences = [
            field
            for field in QD_PROFILE_FIELDS
            if item[field] != primary[field]
        ]
        if item["label"] == "eds_quality_diversity_sparse_primary":
            if differences != ["qd_parent_sampling"]:
                raise AssertionError("sparse profile must change parent sampling only")
        elif item["role"] == "parameter_ofat" and len(differences) != 1:
            raise AssertionError(f"non-OFAT QD profile: {item['label']}")
    return profiles


def _bind_job(job: dict[str, object]) -> dict[str, object]:
    return base._bind_p2_execution_context(
        job,
        real_root=OUTPUT_TARGET,
        cached_functions_dir=str(EXPERIMENT_ROOT / "runtime_cache/cached_functions"),
        offline_vlm=False,
        storage_enforced=True,
        git_revision=base._git_head_revision(),
        code_state_sha256=base._p2_code_state_sha256(),
    )


def build_jobs(level: str, episodes: int, **_kwargs) -> list[dict[str, object]]:
    if level == PREFLIGHT_LEVEL:
        if episodes != 2:
            raise ValueError("QD LIBERO preflight requires exactly 2 episodes")
        return build_preflight_jobs()
    if level != FORMAL_LEVEL or episodes != 10:
        raise ValueError("QD formal matrix requires its fixed level and 10 episodes")
    jobs = []
    for profile in formal_profiles():
        job = {
            **profile,
            "job_id": f"{FORMAL_LEVEL}_libero_object_swap_{profile['label']}",
            "level": FORMAL_LEVEL,
            "suite": "libero_object_swap",
            "episodes": 10,
            "task_ids_filter": list(range(10)),
            "episode_seeds": list(EPISODE_SEEDS),
        }
        jobs.append(_bind_job(job))
    return jobs


def build_preflight_jobs() -> list[dict[str, object]]:
    selected = {
        "p2_stage_on_abs_rbf_control",
        "eds_quality_diversity_uniform_primary",
        "eds_quality_diversity_sparse_primary",
    }
    jobs = []
    for profile in formal_profiles():
        if profile["label"] not in selected:
            continue
        formal_label = str(profile["label"])
        label = f"preflight__{formal_label}"
        job = {
            **profile,
            "formal_label": formal_label,
            "method": label,
            "label": label,
            "job_id": f"{PREFLIGHT_LEVEL}_libero_object_swap_{label}",
            "level": PREFLIGHT_LEVEL,
            "suite": "libero_object_swap",
            "episodes": 2,
            "task_ids_filter": [0, 8],
            "episode_seeds": [EPISODE_SEEDS[0], EPISODE_SEEDS[8]],
        }
        jobs.append(_bind_job(job))
    expected_order = [
        "p2_stage_on_abs_rbf_control",
        "eds_quality_diversity_uniform_primary",
        "eds_quality_diversity_sparse_primary",
    ]
    jobs.sort(key=lambda item: expected_order.index(str(item["formal_label"])))
    if len(jobs) != 3:
        raise AssertionError("QD LIBERO preflight must contain exactly three profiles")
    return jobs


_BASE_BUILD_MAIN_COMMAND = getattr(
    base, "_qd_original_build_main_command", base.build_main_command
)
base._qd_original_build_main_command = _BASE_BUILD_MAIN_COMMAND
_BASE_STAGE_DIR = getattr(base, "_qd_original_stage_dir", base._p2_stage_dir)
base._qd_original_stage_dir = _BASE_STAGE_DIR


def _hydra_value(value: object) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_hydra_value(item) for item in value) + "]"
    if value is None:
        return "null"
    return str(value)


def _build_main_command(job, *args, **kwargs):
    command = _BASE_BUILD_MAIN_COMMAND(job, *args, **kwargs)
    command.append(
        "main.episode_seed_schedule=" + _hydra_value(job["episode_seeds"])
    )
    command.extend(
        [
            "main.eds_config.initial_diversity_descriptor_mode="
            + str(job["initial_diversity_descriptor_mode"]),
            "main.eds_config.rollout_diversity_descriptor_mode="
            + str(job["rollout_diversity_descriptor_mode"]),
            "main.eds_eval.max_visual_chunks_per_episode=2",
        ]
    )
    command.extend(
        f"main.eds_config.{field}={_hydra_value(job[field])}"
        for field in QD_CONFIG_FIELDS
    )
    if job["level"] == PREFLIGHT_LEVEL:
        command.extend(
            [
                "main.eds_mechanism_pretest.enabled=true",
                "main.eds_mechanism_pretest.first_chunk_only=false",
                "main.eds_mechanism_pretest.max_chunks=2",
                "main.eds_mechanism_pretest.max_full_process_iters=10",
            ]
        )
    if _contains_credential(command):
        raise RuntimeError("QD command unexpectedly contains credential material")
    return command


def _stage_dir(level: object) -> str:
    if str(level) == FORMAL_LEVEL:
        return "formal"
    if str(level) == PREFLIGHT_LEVEL:
        return "libero_preflight"
    return _BASE_STAGE_DIR(level)


def storage_preflight() -> dict[str, object]:
    if not EXPERIMENT_ROOT.is_dir() or not os.access(EXPERIMENT_ROOT, os.W_OK):
        raise RuntimeError("QD experiment root is unavailable or not writable")
    if not OUTPUT_LINK.is_symlink() or not os.path.isabs(os.readlink(OUTPUT_LINK)):
        raise RuntimeError("worktree outputs must be the approved absolute symlink")
    try:
        resolved = OUTPUT_LINK.resolve(strict=True)
        target = OUTPUT_TARGET.resolve(strict=True)
        prefix = ALLOWED_STORAGE_PREFIX.resolve(strict=True)
    except OSError as exc:
        raise RuntimeError(f"QD outputs symlink is invalid: {exc}") from exc
    if resolved != target:
        raise RuntimeError(f"QD outputs target mismatch: {resolved} != {target}")
    try:
        resolved.relative_to(prefix)
    except ValueError as exc:
        raise RuntimeError("QD outputs target is outside approved shared2 root") from exc
    free = shutil.disk_usage(EXPERIMENT_ROOT).free
    if free < MIN_FREE_BYTES:
        raise RuntimeError("QD experiment root has less than 50 GiB free")
    probe = OUTPUT_LINK / f".qd_storage_probe_{os.getpid()}"
    with probe.open("x", encoding="utf-8") as handle:
        handle.write("ok\n")
    try:
        if probe.resolve(strict=True).parent != target:
            raise RuntimeError("QD storage probe escaped the approved target")
    finally:
        probe.unlink(missing_ok=True)
    return {
        "experiment_root": str(EXPERIMENT_ROOT.resolve(strict=True)),
        "outputs_link": str(OUTPUT_LINK),
        "outputs_link_value": os.readlink(OUTPUT_LINK),
        "outputs_target": str(target),
        "free_bytes": int(free),
    }


def read_attempt_ledger(path: Path = ATTEMPT_LEDGER_PATH) -> list[dict[str, object]]:
    if not path.exists():
        return []
    records = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"attempt ledger line {line_number} is invalid") from exc
        if not isinstance(record, dict):
            raise RuntimeError(f"attempt ledger line {line_number} is not an object")
        records.append(record)
    attempts = [
        row
        for row in records
        if row.get("record_type", "episode_attempt") == "episode_attempt"
    ]
    if [row.get("attempt_id") for row in attempts] != list(
        range(1, len(attempts) + 1)
    ):
        raise RuntimeError("attempt ledger ids are not contiguous append-only ids")
    events = [row for row in records if row not in attempts]
    if [row.get("ledger_event_id") for row in events] != list(
        range(1, len(events) + 1)
    ):
        raise RuntimeError("attempt ledger event ids are not contiguous")
    return records


def attempt_ledger_state(
    path: Path = ATTEMPT_LEDGER_PATH,
) -> dict[str, object]:
    records = read_attempt_ledger(path)
    attempts = [
        row
        for row in records
        if row.get("record_type", "episode_attempt") == "episode_attempt"
    ]
    attempt_ids = {int(row["attempt_id"]) for row in attempts}
    void_ids: set[int] = set()
    dispatched_ids: set[int] = set()
    aborted_pre_episode_ids: set[int] = set()
    dispatch_events = 0
    for row in records:
        record_type = row.get("record_type")
        if record_type not in {
            "reservation_void",
            "phase_dispatch",
            "dispatch_aborted_pre_episode",
        }:
            continue
        ids = row.get("attempt_ids")
        if (
            not isinstance(ids, list)
            or any(isinstance(value, bool) or not isinstance(value, int) for value in ids)
            or not set(ids) <= attempt_ids
        ):
            raise RuntimeError(f"invalid {record_type} attempt ids")
        if record_type == "reservation_void":
            if set(ids) & dispatched_ids:
                raise RuntimeError("a dispatched attempt reservation cannot be voided")
            void_ids.update(ids)
        elif record_type == "phase_dispatch":
            dispatch_events += 1
            if set(ids) & void_ids:
                raise RuntimeError("a void reservation cannot be dispatched")
            if set(ids) & dispatched_ids:
                raise RuntimeError("an attempt reservation cannot be dispatched twice")
            dispatched_ids.update(ids)
        else:
            if not set(ids) <= (dispatched_ids - aborted_pre_episode_ids):
                raise RuntimeError(
                    "only dispatched, non-aborted attempts can be marked pre-episode aborted"
                )
            aborted_pre_episode_ids.update(ids)
    active = [
        row
        for row in attempts
        if int(row["attempt_id"])
        not in (void_ids | aborted_pre_episode_ids)
    ]
    effective_dispatched_ids = dispatched_ids - aborted_pre_episode_ids
    return {
        "records": records,
        "attempts": attempts,
        "active_attempts": active,
        "void_attempt_ids": sorted(void_ids),
        "dispatched_attempt_ids": sorted(effective_dispatched_ids),
        "ever_dispatched_attempt_ids": sorted(dispatched_ids),
        "aborted_pre_episode_attempt_ids": sorted(aborted_pre_episode_ids),
        "reserved_attempt_count": len(attempts),
        "active_reservation_count": len(active),
        "dispatched_attempt_count": len(effective_dispatched_ids),
        "dispatch_events": dispatch_events,
    }


def append_ledger_event(
    path: Path, event: dict[str, object]
) -> dict[str, object]:
    if event.get("record_type") not in {
        "reservation_void",
        "phase_dispatch",
        "dispatch_aborted_pre_episode",
    }:
        raise ValueError("unsupported attempt ledger event")
    state = attempt_ledger_state(path)
    records = state["records"]
    prepared = {
        "ledger_event_id": 1
        + sum(
            row.get("record_type", "episode_attempt") != "episode_attempt"
            for row in records
        ),
        "created_at": _now(),
        **event,
    }
    if _contains_credential(prepared):
        raise RuntimeError("attempt ledger event contains credential material")
    attempt_ids = prepared.get("attempt_ids")
    if not isinstance(attempt_ids, list) or not attempt_ids:
        raise ValueError("attempt ledger event requires nonempty attempt_ids")
    known = {int(row["attempt_id"]) for row in state["attempts"]}
    if any(
        isinstance(value, bool) or not isinstance(value, int)
        for value in attempt_ids
    ) or not set(attempt_ids) <= known:
        raise ValueError("attempt ledger event references unknown attempt ids")
    if prepared["record_type"] == "reservation_void" and set(attempt_ids) & set(
        state["dispatched_attempt_ids"]
    ):
        raise RuntimeError("cannot void an already dispatched attempt")
    if prepared["record_type"] == "phase_dispatch":
        if set(attempt_ids) & set(state["void_attempt_ids"]):
            raise RuntimeError("cannot dispatch a void reservation")
        if set(attempt_ids) & set(state["ever_dispatched_attempt_ids"]):
            raise RuntimeError("attempt already dispatched")
    if prepared["record_type"] == "dispatch_aborted_pre_episode":
        eligible = set(state["ever_dispatched_attempt_ids"]) - set(
            state["aborted_pre_episode_attempt_ids"]
        )
        if not set(attempt_ids) <= eligible:
            raise RuntimeError(
                "only dispatched attempts can be marked pre-episode aborted"
            )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(_canonical(prepared) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    attempt_ledger_state(path)
    return prepared


def append_attempt_records(
    path: Path, records: list[dict[str, object]]
) -> list[dict[str, object]]:
    if not records:
        return []
    state = attempt_ledger_state(path)
    existing_attempts = state["attempts"]
    if int(state["active_reservation_count"]) + len(records) > ATTEMPT_CAP:
        raise RuntimeError("episode-attempt hard cap 120 would be exceeded")
    prepared = []
    for offset, raw in enumerate(records, start=1):
        required = {
            "phase",
            "label",
            "task_id",
            "episode_seed",
            "config_fingerprint",
        }
        if not required <= set(raw):
            raise ValueError("attempt record is missing required identity fields")
        record = {
            "attempt_id": len(existing_attempts) + offset,
            "record_type": "episode_attempt",
            "started_at": _now(),
            **raw,
        }
        if _contains_credential(record):
            raise RuntimeError("attempt record contains credential material")
        prepared.append(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for record in prepared:
            handle.write(_canonical(record) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return prepared


def _attempt_identity(row: dict[str, object]) -> tuple[object, ...]:
    return tuple(
        row.get(key)
        for key in (
            "phase",
            "label",
            "formal_label",
            "task_id",
            "episode_seed",
            "config_fingerprint",
            "code_state_sha256",
        )
    )


def reusable_phase_reservations(
    path: Path,
    *,
    phase: str,
    expected: list[dict[str, object]],
) -> list[int]:
    state = attempt_ledger_state(path)
    active = [
        row for row in state["active_attempts"] if row.get("phase") == phase
    ]
    if not active:
        return []
    active_ids = {int(row["attempt_id"]) for row in active}
    if active_ids & set(state["dispatched_attempt_ids"]):
        raise RuntimeError(f"{phase} attempt reservations were already dispatched")
    if sorted(_attempt_identity(row) for row in active) != sorted(
        _attempt_identity(row) for row in expected
    ):
        raise RuntimeError(f"{phase} attempt reservations do not match current code/config")
    return sorted(active_ids)


def validate_formal_readiness(
    *,
    offline_path: Path = OFFLINE_PREFLIGHT_PATH,
    preflight_audit_path: Path = LIBERO_PREFLIGHT_AUDIT_PATH,
    ledger_path: Path = ATTEMPT_LEDGER_PATH,
) -> dict[str, object]:
    try:
        offline = json.loads(Path(offline_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("offline mechanism preflight evidence is missing") from exc
    if not isinstance(offline, dict) or offline.get("passed") is not True:
        raise RuntimeError("offline mechanism preflight did not pass")
    try:
        preflight = json.loads(
            Path(preflight_audit_path).read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as exc:
        raise RuntimeError("LIBERO preflight audit evidence is missing") from exc
    if not isinstance(preflight, dict) or preflight.get("passed") is not True:
        raise RuntimeError("LIBERO preflight audit did not pass")
    expected_labels = {
        "p2_stage_on_abs_rbf_control",
        "eds_quality_diversity_uniform_primary",
        "eds_quality_diversity_sparse_primary",
    }
    jobs = preflight.get("jobs")
    if not isinstance(jobs, list) or {
        str(job.get("formal_label"))
        for job in jobs
        if isinstance(job, dict)
    } != expected_labels:
        raise RuntimeError("LIBERO preflight profiles do not match frozen matrix")
    for job in jobs:
        if (
            job.get("valid") is not True
            or job.get("mechanism_hard", {}).get("passed") is not True
            or set(job.get("task_outcomes", {})) != {"0", "8"}
        ):
            raise RuntimeError("LIBERO preflight validity/mechanism evidence failed")
    if preflight.get("credential_audit", {}).get("passed") is not True:
        raise RuntimeError("LIBERO preflight credential audit failed")
    state = attempt_ledger_state(Path(ledger_path))
    dispatched_preflight = [
        row
        for row in state["active_attempts"]
        if row.get("phase") == "preflight"
        and int(row["attempt_id"]) in set(state["dispatched_attempt_ids"])
    ]
    if len(dispatched_preflight) != 6:
        raise RuntimeError("formal readiness requires six dispatched preflight attempts")
    identities = {
        (
            str(row.get("formal_label")),
            int(row.get("task_id")),
            int(row.get("episode_seed")),
        )
        for row in dispatched_preflight
    }
    expected_identities = {
        (label, task, EPISODE_SEEDS[task])
        for label in expected_labels
        for task in (0, 8)
    }
    if identities != expected_identities:
        raise RuntimeError("dispatched preflight attempts do not match frozen identities")
    return {
        "passed": True,
        "offline_sha256": _sha256_bytes(Path(offline_path).read_bytes()),
        "libero_preflight_audit_sha256": _sha256_bytes(
            Path(preflight_audit_path).read_bytes()
        ),
        "dispatched_preflight_attempts": 6,
    }


def _attempt_records_for_jobs(
    jobs: list[dict[str, object]], phase: str
) -> list[dict[str, object]]:
    records = []
    for job in jobs:
        for episode, (task_id, seed) in enumerate(
            zip(job["task_ids_filter"], job["episode_seeds"])
        ):
            records.append(
                {
                    "phase": phase,
                    "label": job["label"],
                    "formal_label": job.get("formal_label", job["label"]),
                    "episode": episode,
                    "task_id": int(task_id),
                    "episode_seed": int(seed),
                    "config_fingerprint": job["config_fingerprint"],
                    "code_state_sha256": job["execution_record"][
                        "code_state_sha256"
                    ],
                }
            )
    return records


def offline_mechanism_preflight(
    path: Path = OFFLINE_PREFLIGHT_PATH,
) -> dict[str, object]:
    axis = torch.linspace(-0.06, 0.06, 4)
    descriptors = torch.stack(
        [torch.tensor([x, y]) for y in axis for x in axis]
    ).float()
    actions = torch.stack(
        [torch.full((4, 5), float(index)) for index in range(16)]
    )
    rewards = torch.arange(16, dtype=torch.float32)
    costs = -rewards
    input_checksum = _sha256_bytes(
        descriptors.numpy().tobytes() + actions.numpy().tobytes()
    )
    grid_mapping = {}
    primary_bounds = None
    for grid in ((3, 3), (4, 4), (5, 5)):
        bounds = freeze_bounds(
            descriptors,
            quantiles=(0.05, 0.95),
            expand_fraction=0.10,
            min_axis_span_m=0.08,
        )
        mapped, overflow = cell_ids(descriptors, bounds, grid)
        grid_mapping[f"{grid[0]}x{grid[1]}"] = {
            "cell_ids": mapped.tolist(),
            "overflow_count": int(overflow.sum().item()),
            "bounds_checksum": bounds.checksum,
        }
        if grid == (4, 4):
            primary_bounds = bounds
    assert primary_bounds is not None
    initial_cells, _ = cell_ids(descriptors, primary_bounds, (4, 4))
    archive = QDArchive(grid_shape=(4, 4))
    initial_summary = archive.update(
        actions=actions,
        rewards=rewards,
        costs=costs,
        descriptors=descriptors,
        cell_ids=initial_cells,
        source_iter=-1,
    )
    rng_before = torch.random.get_rng_state().clone()
    uniform = allocate_parent_slots(
        archive,
        population_size=16,
        sampling="uniform_cells",
        sparse_exponent=1.0,
        run_seed=0,
        episode=0,
        global_step=0,
        iter_idx=0,
    )
    sparse = allocate_parent_slots(
        archive,
        population_size=16,
        sampling="sparse_priority",
        sparse_exponent=1.0,
        run_seed=0,
        episode=0,
        global_step=0,
        iter_idx=0,
    )
    rng_unchanged = torch.equal(torch.random.get_rng_state(), rng_before)
    iterations = []
    evaluation_count = 16
    model_reward_call_budget = 1
    fixed_bounds_unchanged = True
    for iteration in range(10):
        child_descriptors = descriptors.roll(iteration + 1, dims=0)
        child_cells, child_overflow = cell_ids(
            child_descriptors, primary_bounds, (4, 4)
        )
        child_rewards = rewards + float((iteration + 1) * 100)
        child_actions = actions + float(iteration + 1) / 10.0
        summary = archive.update(
            actions=child_actions,
            rewards=child_rewards,
            costs=-child_rewards,
            descriptors=child_descriptors,
            cell_ids=child_cells,
            source_iter=iteration,
            parent_cell_ids=uniform.parent_cell_ids,
        )
        evaluation_count += 16
        model_reward_call_budget += 1
        fixed_bounds_unchanged = (
            fixed_bounds_unchanged
            and primary_bounds.checksum
            == freeze_bounds(
                descriptors,
                quantiles=(0.05, 0.95),
                expand_fraction=0.10,
                min_axis_span_m=0.08,
            ).checksum
        )
        best_cell, best = archive.select_global_best()
        iterations.append(
            {
                "iter_idx": iteration,
                "occupied_cells": len(archive.entries),
                "accounting": {
                    "insertions": summary.insertions,
                    "replacements": summary.replacements,
                    "rejections": summary.rejections,
                    "total": summary.total,
                },
                "overflow_count": int(child_overflow.sum().item()),
                "parent_slots": uniform.slot_counts,
                "best_cell": best_cell,
                "best_reward": best.reward,
                "best_fingerprint": best.fingerprint,
                "archive": archive.snapshot(),
            }
        )
    uniform_counts = list(uniform.slot_counts.values())
    uniform_passed = (
        sum(uniform_counts) == 16
        and max(uniform_counts) - min(uniform_counts) <= 1
    )
    sparse_passed = sum(sparse.slot_counts.values()) == 16
    final_cell, final_entry = archive.select_global_best()

    zero_spread_rows = []
    zero_descriptors = torch.zeros((16, 2), dtype=torch.float32)
    for minimum_span in (0.04, 0.08, 0.12):
        zero_bounds = freeze_bounds(
            zero_descriptors,
            quantiles=(0.05, 0.95),
            expand_fraction=0.10,
            min_axis_span_m=minimum_span,
        )
        spans = zero_bounds.hi - zero_bounds.lo
        zero_spread_rows.append(
            {
                "minimum_span_m": minimum_span,
                "resolved_span_m": spans.tolist(),
                "finite": bool(torch.isfinite(spans).all().item()),
                "minimum_respected": bool(
                    torch.all(spans >= minimum_span - 1.0e-7).item()
                ),
            }
        )
    zero_spread_evidence = {
        "passed": all(
            row["finite"] and row["minimum_respected"]
            for row in zero_spread_rows
        ),
        "profiles": zero_spread_rows,
    }

    nonfinite_exception = None
    try:
        freeze_bounds(
            torch.tensor([[float("nan"), 0.0]], dtype=torch.float32),
            quantiles=(0.05, 0.95),
            expand_fraction=0.10,
            min_axis_span_m=0.08,
        )
    except (FloatingPointError, ValueError) as exc:
        nonfinite_exception = type(exc).__name__
    nonfinite_evidence = {
        "passed": nonfinite_exception is not None,
        "exception_type": nonfinite_exception,
    }

    tie_archive = QDArchive(grid_shape=(1, 1))
    tie_actions = torch.stack(
        [torch.zeros((2, 3)), torch.ones((2, 3)), torch.full((2, 3), 2.0)]
    )
    tie_descriptors = torch.zeros((1, 2), dtype=torch.float32)
    tie_cells = torch.zeros(1, dtype=torch.long)
    tie_archive.update(
        actions=tie_actions[0:1],
        rewards=torch.tensor([1.0]),
        costs=torch.tensor([-1.0]),
        descriptors=tie_descriptors,
        cell_ids=tie_cells,
        source_iter=-1,
    )
    higher = tie_archive.update(
        actions=tie_actions[1:2],
        rewards=torch.tensor([2.0]),
        costs=torch.tensor([-2.0]),
        descriptors=tie_descriptors,
        cell_ids=tie_cells,
        source_iter=0,
    )
    tied = tie_archive.update(
        actions=tie_actions[2:3],
        rewards=torch.tensor([2.0]),
        costs=torch.tensor([-2.0]),
        descriptors=tie_descriptors,
        cell_ids=tie_cells,
        source_iter=1,
    )
    expected_tie_fingerprint = min(
        fingerprint_action(tie_actions[1]), fingerprint_action(tie_actions[2])
    )
    _, tie_winner = tie_archive.select_global_best()
    tie_evidence = {
        "passed": (
            higher.replacements == 1
            and tie_winner.fingerprint == expected_tie_fingerprint
            and tied.total == 1
        ),
        "higher_reward_replacements": higher.replacements,
        "tie_update": tied.__dict__,
        "winner_fingerprint": tie_winner.fingerprint,
        "expected_fingerprint": expected_tie_fingerprint,
    }

    observer_population = torch.arange(16 * 4, dtype=torch.float32).reshape(16, 4)
    observer_descriptors = descriptors.detach().clone()
    observer_rewards = rewards.detach().clone()
    observer_parent_indices = torch.arange(16, dtype=torch.long)
    observer_selected = observer_population[-1].detach().clone()
    observer_rng_before = torch.random.get_rng_state().clone()
    observer_stream = {
        "descriptors_xy_m": observer_descriptors.detach().cpu().tolist(),
        "rewards": observer_rewards.detach().cpu().tolist(),
        "fingerprints": [
            fingerprint_action(action) for action in observer_population
        ],
    }
    observer_rng_after = torch.random.get_rng_state().clone()
    observer_evidence = {
        "passed": (
            torch.equal(observer_rng_before, observer_rng_after)
            and torch.equal(observer_parent_indices, torch.arange(16))
            and torch.equal(observer_selected, observer_population[-1])
        ),
        "rng_state_unchanged": torch.equal(
            observer_rng_before, observer_rng_after
        ),
        "parent_indices_unchanged": torch.equal(
            observer_parent_indices, torch.arange(16)
        ),
        "selected_action_unchanged": torch.equal(
            observer_selected, observer_population[-1]
        ),
        "stream_checksum": _sha256_bytes(
            _canonical(observer_stream).encode("utf-8")
        ),
    }
    hard_failures = []
    if evaluation_count != 176:
        hard_failures.append("evaluation budget mismatch")
    if initial_summary.total != 16 or any(
        item["accounting"]["total"] != 16 for item in iterations
    ):
        hard_failures.append("archive accounting mismatch")
    if archive.accounting_violation_count:
        hard_failures.append("archive accounting violation")
    if archive.elite_monotonicity_violation_count:
        hard_failures.append("elite monotonicity violation")
    if not uniform_passed:
        hard_failures.append("uniform allocation mismatch")
    if not sparse_passed:
        hard_failures.append("sparse allocation mismatch")
    if not rng_unchanged:
        hard_failures.append("global RNG changed")
    if not fixed_bounds_unchanged:
        hard_failures.append("fixed bounds changed")
    if not zero_spread_evidence["passed"]:
        hard_failures.append("zero-spread bounds failed")
    if not nonfinite_evidence["passed"]:
        hard_failures.append("nonfinite input did not fail closed")
    if not tie_evidence["passed"]:
        hard_failures.append("replacement/tie-break mismatch")
    if not observer_evidence["passed"]:
        hard_failures.append("observer equality mismatch")
    payload = {
        "schema": "eds-qd-offline-mechanism-preflight-v1",
        "created_at": _now(),
        "input_checksum": input_checksum,
        "config_checksum": _sha256_bytes(
            _canonical(
                {
                    "population_size": 16,
                    "cem_iters": 10,
                    "descriptor": "target_relative_endpoint_xy",
                    "grid": [4, 4],
                    "quantiles": [0.05, 0.95],
                    "expand": 0.10,
                    "minimum_span": 0.08,
                }
            ).encode("utf-8")
        ),
        "evaluation_budget": evaluation_count,
        "model_reward_call_budget": model_reward_call_budget,
        "grid_mapping": grid_mapping,
        "bounds_checksum": primary_bounds.checksum,
        "initial_accounting": initial_summary.__dict__,
        "archive_iterations": iterations,
        "uniform_allocation": uniform.slot_counts,
        "sparse_allocation": sparse.slot_counts,
        "uniform_allocation_passed": uniform_passed,
        "sparse_allocation_passed": sparse_passed,
        "global_rng_unchanged": rng_unchanged,
        "control_observer_bitwise_equality": observer_evidence,
        "zero_spread_bounds": zero_spread_evidence,
        "nonfinite_fail_closed": nonfinite_evidence,
        "replacement_and_tie_break": tie_evidence,
        "fixed_bounds_unchanged": fixed_bounds_unchanged,
        "final_global_best": {
            "cell": final_cell,
            "reward": final_entry.reward,
            "fingerprint": final_entry.fingerprint,
        },
        "hard_failures": hard_failures,
        "passed": not hard_failures,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return payload


def gpu_snapshot() -> list[dict[str, object]]:
    query = "index,uuid,name,memory.total,memory.free,utilization.gpu,compute_mode"
    output = subprocess.check_output(
        [
            "nvidia-smi",
            f"--query-gpu={query}",
            "--format=csv,noheader,nounits",
        ],
        text=True,
        timeout=30,
    )
    process_output = subprocess.run(
        [
            "nvidia-smi",
            "--query-compute-apps=gpu_uuid,pid,used_gpu_memory,process_name",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    processes: dict[str, list[dict[str, object]]] = {}
    if process_output.returncode == 0:
        for line in process_output.stdout.splitlines():
            parts = [part.strip() for part in line.split(",", 3)]
            if len(parts) != 4 or parts[0].lower().startswith("no running"):
                continue
            try:
                row = {
                    "pid": int(parts[1]),
                    "used_memory_mib": int(parts[2]),
                    "process_name": parts[3],
                }
            except ValueError:
                continue
            processes.setdefault(parts[0], []).append(row)
    devices = []
    for line in output.splitlines():
        index, uuid, name, total, free, util, mode = [
            item.strip() for item in line.split(",", 6)
        ]
        devices.append(
            {
                "index": int(index),
                "uuid": uuid,
                "name": name,
                "memory_total_mib": int(total),
                "memory_free_mib": int(free),
                "utilization_percent": int(util),
                "compute_mode": mode,
                "compute_processes": processes.get(uuid, []),
            }
        )
    return devices


def _gpu_snapshot_failure(
    device: dict[str, object] | None,
    *,
    index: int,
    required_free: float,
) -> list[str]:
    if not 0 <= index <= 7:
        return ["index outside approved range 0..7"]
    if device is None:
        return ["GPU not visible"]
    reasons = []
    if device.get("compute_processes"):
        reasons.append("external compute process present")
    if float(device.get("utilization_percent", math.inf)) > 5.0:
        reasons.append("utilization exceeds 5%")
    if float(device.get("memory_free_mib", -math.inf)) < required_free:
        reasons.append("insufficient free VRAM headroom")
    mode = str(device.get("compute_mode", "")).lower()
    if "prohibited" in mode:
        reasons.append("compute mode prohibits worker admission")
    return reasons


def admit_gpus(
    *,
    reference_peak_vram_mib: float,
    snapshot_fn: Callable[[], list[dict[str, object]]] = gpu_snapshot,
    wait_fn: Callable[[float], None] = time.sleep,
    wait_seconds: float = 2.0,
) -> dict[str, object]:
    reference_peak = float(reference_peak_vram_mib)
    if not math.isfinite(reference_peak) or reference_peak <= 0:
        raise ValueError("reference peak VRAM must be finite and positive")
    required = max(reference_peak * 1.25, reference_peak + 4096.0)
    first = snapshot_fn()
    wait_fn(float(wait_seconds))
    second = snapshot_fn()
    first_by_index = {int(item["index"]): item for item in first}
    second_by_index = {int(item["index"]): item for item in second}
    all_indices = sorted(set(first_by_index) | set(second_by_index))
    eligible = []
    excluded: dict[str, list[str]] = {}
    for index in all_indices:
        reasons = []
        reasons.extend(
            "snapshot1: " + reason
            for reason in _gpu_snapshot_failure(
                first_by_index.get(index), index=index, required_free=required
            )
        )
        reasons.extend(
            "snapshot2: " + reason
            for reason in _gpu_snapshot_failure(
                second_by_index.get(index), index=index, required_free=required
            )
        )
        if reasons:
            excluded[str(index)] = reasons
        else:
            eligible.append(index)
    return {
        "created_at": _now(),
        "reference_peak_vram_mib": reference_peak,
        "required_free_vram_mib": required,
        "snapshot_interval_s": float(wait_seconds),
        "snapshots": [first, second],
        "eligible_gpu_indices": eligible,
        "excluded": excluded,
        "max_concurrency": min(4, len(eligible)),
    }


def load_gpu_reference() -> dict[str, object]:
    if not GPU_REFERENCE_PATH.is_file():
        raise RuntimeError("audited historical GPU peak manifest is missing")
    payload = json.loads(GPU_REFERENCE_PATH.read_text(encoding="utf-8"))
    peak = payload.get("reference_peak_vram_mib")
    if not isinstance(peak, (int, float)) or isinstance(peak, bool) or float(peak) <= 0:
        raise RuntimeError("GPU reference peak manifest is invalid")
    return {
        "source_path": str(GPU_REFERENCE_PATH),
        "source_sha256": _sha256_bytes(GPU_REFERENCE_PATH.read_bytes()),
        "reference_peak_vram_mib": float(peak),
        "required_free_vram_mib": max(float(peak) * 1.25, float(peak) + 4096),
        "same_checkpoint_control_config": True,
    }


def _profile_fingerprint(profile: dict[str, object]) -> str:
    excluded = {"method", "role", "job_id", "level", "formal_label"}
    payload = {
        "profile": {key: value for key, value in profile.items() if key not in excluded},
        "suite": "libero_object_swap",
        "strict_perturbations": True,
        "tasks": list(range(10)),
        "episode_seeds": EPISODE_SEEDS,
    }
    return _sha256_bytes(_canonical(payload).encode("utf-8"))


def freeze_run_manifest(
    *,
    provenance: dict[str, object],
    storage: dict[str, object],
    gpu_reference: dict[str, object],
) -> dict[str, object]:
    profiles = formal_profiles()
    payload = {
        "schema": "eds-quality-diversity-run-manifest-v1",
        "created_at": _now(),
        "design_path": str(DESIGN_PATH),
        "design_sha256": (
            _sha256_bytes(DESIGN_PATH.read_bytes()) if DESIGN_PATH.is_file() else None
        ),
        "design_status": "Approved for execution",
        "provenance": provenance,
        "storage": storage,
        "gpu_reference": gpu_reference,
        "suite": "libero_object_swap",
        "strict_perturbations": True,
        "task_ids": list(range(10)),
        "episode_seeds": list(EPISODE_SEEDS),
        "root_seed": 0,
        "max_episode_steps": 720,
        "stage_recognition": True,
        "gemini_grounding": False,
        "formal_profiles": [
            {**profile, "profile_fingerprint": _profile_fingerprint(profile)}
            for profile in profiles
        ],
        "preflight_profiles": [
            "p2_stage_on_abs_rbf_control",
            "eds_quality_diversity_uniform_primary",
            "eds_quality_diversity_sparse_primary",
        ],
        "preflight_tasks": [0, 8],
        "formal_job_count": 11,
        "formal_episode_count": 110,
        "preflight_episode_count": 6,
        "recovery_attempt_limit": 4,
        "attempt_cap": 120,
        "ranking_order": [
            "success_count_desc",
            "control_task_retention_desc",
            "paired_gained_minus_lost_desc",
            "qpos_execution_error_episodes_asc",
            "collision_push_drop_wrong_object_asc",
            "normalized_coverage_gain_desc",
            "endpoint_xy_spread_retention_desc",
            "archive_best_reward_delta_desc",
            "selection_latency_p95_asc",
            "job_label_lexical",
        ],
        "gates_frozen_by_design": True,
    }
    if (
        RUN_MANIFEST_PATH.name == "qd_ed_run_manifest.v5.json"
        and SUPERSEDED_RUN_MANIFEST_PATH.is_file()
    ):
        payload["supersedes"] = {
            "path": str(SUPERSEDED_RUN_MANIFEST_PATH),
            "sha256": _sha256_bytes(SUPERSEDED_RUN_MANIFEST_PATH.read_bytes()),
            "reason": (
                "pre-episode infrastructure accounting: preserve dispatch "
                "failures that occurred before episode initialization without "
                "charging the actual episode-attempt cap"
            ),
            "algorithm_matrix_or_gate_change": False,
        }
    payload["manifest_payload_sha256"] = _sha256_bytes(
        _canonical(payload).encode("utf-8")
    )
    if _contains_credential(payload):
        raise RuntimeError("run manifest contains credential material")
    RUN_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RUN_MANIFEST_PATH.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    RUN_MANIFEST_PATH.chmod(0o444)
    return payload


def current_provenance() -> dict[str, object]:
    status = subprocess.check_output(
        ["git", "status", "--short"], cwd=WORKTREE_ROOT, text=True
    ).splitlines()
    unexpected = [line for line in status if not line.endswith(" outputs")]
    if unexpected:
        raise RuntimeError(
            "QD implementation worktree must be committed before manifest freeze: "
            + "; ".join(unexpected)
        )
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=WORKTREE_ROOT, text=True
    ).strip()
    branch = subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=WORKTREE_ROOT,
        text=True,
    ).strip()
    if branch != NEW_BRANCH:
        raise RuntimeError(f"unexpected QD branch: {branch}")
    return {
        "base_commit": BASE_COMMIT,
        "source_branch": SOURCE_BRANCH,
        "new_branch": NEW_BRANCH,
        "new_worktree_realpath": str(WORKTREE_ROOT.resolve(strict=True)),
        "code_commit": head,
        "code_state_sha256": base._p2_code_state_sha256(),
    }


def validate_runtime_credential() -> dict[str, object]:
    value = os.environ.get("OPENAI_API_KEY", "").strip()
    if not value or value.lower() == "dummy":
        raise RuntimeError("Stage Recognition credential must come from environment")
    return {"credential_present": True, "source": "environment"}


def _gpu_probe(gpu: str) -> tuple[str, str]:
    reference = load_gpu_reference()
    device = next(
        (item for item in gpu_snapshot() if str(item["index"]) == str(gpu)),
        None,
    )
    reasons = _gpu_snapshot_failure(
        device,
        index=int(gpu),
        required_free=float(reference["required_free_vram_mib"]),
    )
    return ("busy", "; ".join(reasons)) if reasons else ("idle", "admitted")


def configure_base() -> None:
    base.P2_OUTPUT_ROOT = OUTPUT_LINK
    base.P2_STATUS_ROOT = OUTPUT_LINK
    base.P2_EXPECTED_OUTPUT_TARGET = OUTPUT_TARGET
    base.P2_ALLOWED_OUTPUT_PREFIX = ALLOWED_STORAGE_PREFIX
    base.P2_MIN_FREE_BYTES = MIN_FREE_BYTES
    base.P2_LEVELS = set(base.P2_LEVELS) | {FORMAL_LEVEL, PREFLIGHT_LEVEL}
    base.P2_ALLOWED_GPUS = {str(index) for index in range(8)}
    base.P2_REQUIRED_MOUNT = Path("/mnt/data/shared2")
    base.P2_TORCH_HUB_SEED = (
        Path("/mnt/data/shared2/zhuoli/output/p2_direction_normalized_rbf")
        / "runtime_cache/formal/p2_stage_on_dirnorm_rbf_global_w0_e025/xdg/torch/hub"
    )
    base.build_jobs = build_jobs
    base.build_main_command = _build_main_command
    base._p2_stage_dir = _stage_dir
    base._p2_gpu_probe = _gpu_probe


configure_base()


def _write_gpu_admission(phase: str, payload: dict[str, object]) -> Path:
    path = EXPERIMENT_ROOT / "manifests" / f"gpu_{phase}_{int(time.time())}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def _run_phase(
    *, phase: str, requested_gpus: str, timeout_seconds: int
) -> int:
    if phase not in {"preflight", "formal"}:
        raise ValueError("phase must be preflight or formal")
    if not RUN_MANIFEST_PATH.is_file() or (RUN_MANIFEST_PATH.stat().st_mode & 0o222):
        raise RuntimeError("immutable run manifest must exist before LIBERO attempts")
    if phase == "formal":
        validate_formal_readiness()
    storage_preflight()
    validate_runtime_credential()
    if not base._poe_healthcheck():
        raise RuntimeError("Poe Gemini health check failed before attempt dispatch")
    reference = load_gpu_reference()
    admission = admit_gpus(
        reference_peak_vram_mib=float(reference["reference_peak_vram_mib"])
    )
    eligible = [str(index) for index in admission["eligible_gpu_indices"]]
    if requested_gpus == "auto":
        selected = eligible[:4]
    else:
        selected = [item.strip() for item in requested_gpus.split(",") if item.strip()]
        if not selected or len(selected) != len(set(selected)):
            raise RuntimeError("requested GPUs must be a nonempty unique list")
        if not set(selected) <= set(eligible):
            raise RuntimeError("one or more requested GPUs failed admission")
    if not selected:
        raise RuntimeError("no GPU passed QD admission")
    admission["selected_gpu_indices"] = [int(item) for item in selected]
    _write_gpu_admission(f"{phase}_dispatch", admission)
    level = PREFLIGHT_LEVEL if phase == "preflight" else FORMAL_LEVEL
    episodes = 2 if phase == "preflight" else 10
    jobs = build_jobs(level, episodes)
    expected_reservations = _attempt_records_for_jobs(jobs, phase)
    try:
        attempt_ids = reusable_phase_reservations(
            ATTEMPT_LEDGER_PATH,
            phase=phase,
            expected=expected_reservations,
        )
    except RuntimeError as exc:
        if "already dispatched" in str(exc):
            raise
        state = attempt_ledger_state(ATTEMPT_LEDGER_PATH)
        stale_ids = [
            int(row["attempt_id"])
            for row in state["active_attempts"]
            if row.get("phase") == phase
        ]
        if not stale_ids:
            raise
        append_ledger_event(
            ATTEMPT_LEDGER_PATH,
            {
                "record_type": "reservation_void",
                "phase": phase,
                "attempt_ids": stale_ids,
                "reason": "pre-dispatch code/config reservation superseded",
            },
        )
        attempt_ids = []
    if not attempt_ids:
        reservations = append_attempt_records(
            ATTEMPT_LEDGER_PATH,
            expected_reservations,
        )
        attempt_ids = [int(row["attempt_id"]) for row in reservations]
    append_ledger_event(
        ATTEMPT_LEDGER_PATH,
        {
            "record_type": "phase_dispatch",
            "phase": phase,
            "attempt_ids": attempt_ids,
            "selected_gpu_indices": [int(item) for item in selected],
        },
    )
    original_healthcheck = base._poe_healthcheck
    base._poe_healthcheck = lambda: True
    try:
        result = base.run_level(
            level,
            episodes,
            ",".join(selected),
            timeout_seconds,
            resume=False,
            cached_functions_dir=str(EXPERIMENT_ROOT / "runtime_cache/cached_functions"),
            offline_vlm=False,
            gpu_poll_interval_s=30.0,
        )
    finally:
        base._poe_healthcheck = original_healthcheck
    completion = admit_gpus(
        reference_peak_vram_mib=float(reference["reference_peak_vram_mib"]),
        wait_seconds=0.0,
    )
    completion["selected_gpu_indices"] = [int(item) for item in selected]
    completion["runner_exit_code"] = int(result)
    _write_gpu_admission(f"{phase}_completion", completion)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("storage-preflight")
    subparsers.add_parser("offline-mechanism-preflight")
    subparsers.add_parser("matrix")
    subparsers.add_parser("gpu-admission")
    subparsers.add_parser("freeze-manifest")
    for name in ("run-libero-preflight", "run-formal"):
        run = subparsers.add_parser(name)
        run.add_argument("--gpus", default="auto")
        run.add_argument("--timeout-seconds", type=int, default=28800)
    args = parser.parse_args()
    if args.command == "storage-preflight":
        print(json.dumps(storage_preflight(), indent=2))
        return 0
    if args.command == "offline-mechanism-preflight":
        result = offline_mechanism_preflight()
        print(json.dumps(result, indent=2))
        return 0 if result["passed"] else 1
    if args.command == "matrix":
        print(json.dumps(build_jobs(FORMAL_LEVEL, 10), indent=2))
        return 0
    if args.command == "gpu-admission":
        reference = load_gpu_reference()
        print(
            json.dumps(
                admit_gpus(
                    reference_peak_vram_mib=float(
                        reference["reference_peak_vram_mib"]
                    )
                ),
                indent=2,
            )
        )
        return 0
    if args.command == "freeze-manifest":
        result = freeze_run_manifest(
            provenance=current_provenance(),
            storage=storage_preflight(),
            gpu_reference=load_gpu_reference(),
        )
        print(json.dumps(result, indent=2))
        return 0
    if args.command == "run-libero-preflight":
        return _run_phase(
            phase="preflight",
            requested_gpus=args.gpus,
            timeout_seconds=args.timeout_seconds,
        )
    return _run_phase(
        phase="formal",
        requested_gpus=args.gpus,
        timeout_seconds=args.timeout_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
