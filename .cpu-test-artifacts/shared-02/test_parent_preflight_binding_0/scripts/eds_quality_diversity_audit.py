#!/usr/bin/env python3
"""Strict audit, frozen gates, ranking, and immutable decision for QD-ED."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import re
import stat
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Callable, Iterable

import torch

SCRIPT_DIR = Path(__file__).resolve().parent
WORKTREE_ROOT = Path(__file__).resolve().parents[1]
for import_root in (SCRIPT_DIR, WORKTREE_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import eds_quality_diversity_runner as runner
from core.eds_eval_metrics import wilson_ci
from core.qd_ed import (
    QDArchive,
    QDBounds,
    allocate_parent_slots,
    cell_ids,
    freeze_bounds,
)


OUTPUT_TARGET = runner.OUTPUT_TARGET
EXPERIMENT_ROOT = runner.EXPERIMENT_ROOT
ANALYSIS_PATH = EXPERIMENT_ROOT / "analysis/qd_ed_formal_audit.json"
PREFLIGHT_AUDIT_PATH = EXPERIMENT_ROOT / "analysis/libero_mechanism_preflight_audit.json"
DECISION_PATH = EXPERIMENT_ROOT / "manifests/qd_ed_decision_manifest.json"
CONTACT_SHEET_ROOT = EXPERIMENT_ROOT / "analysis/qualitative_contact_sheets"
REPORT_PATH = (
    WORKTREE_ROOT
    / "docs/03_evidence/eds_init_pg_diverse_sampling/"
    "2026-08-06-eds-quality-diversity-report.md"
)

FAILURE_CATEGORIES = (
    "no target acquisition",
    "target pushed away",
    "target dropped after grasp",
    "basket displaced/collision",
    "clutter swept/wrong-object interaction",
    "unstable transport",
    "placement/release failure",
    "premature guidance OFF",
    "guidance oscillation",
    "qpos/execution error",
    "timeout without completion",
)
COLLISION_COMPOSITE = {
    "target pushed away",
    "target dropped after grasp",
    "basket displaced/collision",
    "clutter swept/wrong-object interaction",
}
TEXT_SCAN_SUFFIXES = {
    ".json",
    ".jsonl",
    ".txt",
    ".log",
    ".yaml",
    ".yml",
    ".md",
    ".csv",
    ".sha256",
    ".py",
    ".sh",
}


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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _contains_credential(value: object) -> bool:
    serialized = _canonical(value).lower()
    secrets = [
        os.environ.get(name, "").strip().lower()
        for name in ("OPENAI_API_KEY", "GOOGLE_API_KEY")
    ]
    return (
        any(secret and secret in serialized for secret in secrets)
        or re.search(r"(?<![a-z0-9_])sk-[a-z0-9_-]{16,}", serialized) is not None
        or any(
            marker in serialized
            for marker in ("api_key=", "api-key=", "authorization: bearer")
        )
    )


def _read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.is_file():
        return [], [f"missing JSONL: {path}"]
    records: list[dict[str, Any]] = []
    failures: list[str] = []
    for number, line in enumerate(
        path.read_text(encoding="utf-8", errors="strict").splitlines(), 1
    ):
        if not line.strip():
            failures.append(f"blank JSONL record: {path}:{number}")
            continue
        try:
            record = json.loads(line)
        except ValueError as exc:
            failures.append(f"invalid JSONL: {path}:{number}: {exc}")
            continue
        if not isinstance(record, dict):
            failures.append(f"non-object JSONL record: {path}:{number}")
            continue
        records.append(record)
    return records, failures


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _median(values: Iterable[object]) -> float | None:
    finite = [item for value in values if (item := _finite_number(value)) is not None]
    return float(median(finite)) if finite else None


def _percentile(values: Iterable[object], quantile: float) -> float | None:
    finite = sorted(
        item for value in values if (item := _finite_number(value)) is not None
    )
    if not finite:
        return None
    position = (len(finite) - 1) * float(quantile)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return float(finite[lower])
    fraction = position - lower
    return float(finite[lower] * (1.0 - fraction) + finite[upper] * fraction)


def _profile_bounds(profile: dict[str, object], descriptors: torch.Tensor) -> QDBounds:
    return freeze_bounds(
        descriptors,
        quantiles=profile["qd_bounds_quantiles"],
        expand_fraction=float(profile["qd_bounds_expand_fraction"]),
        min_axis_span_m=float(profile["qd_min_axis_span_m"]),
    )


def replay_shadow_archive(
    stream: list[dict[str, object]], profile: dict[str, object]
) -> dict[str, object]:
    """Replay top-1 archive over a detached control stream for one QD profile."""
    if not stream or stream[0].get("iter_idx") != -1:
        raise ValueError("shadow stream must begin with initial iteration -1")
    if [record.get("iter_idx") for record in stream] != list(range(-1, len(stream) - 1)):
        raise ValueError("shadow stream iterations must be contiguous -1..K-1")
    initial = torch.tensor(stream[0].get("descriptors_xy_m"), dtype=torch.float32)
    bounds = _profile_bounds(profile, initial)
    archive: dict[int, dict[str, object]] = {}
    timeline: list[dict[str, object]] = []
    total_insertions = total_replacements = total_rejections = 0
    overflow_ratios: list[float] = []
    evaluation_count = 0

    for record in stream:
        descriptors = torch.tensor(record.get("descriptors_xy_m"), dtype=torch.float32)
        rewards = record.get("rewards")
        fingerprints = record.get("fingerprints")
        if (
            descriptors.ndim != 2
            or descriptors.shape[1] != 2
            or not isinstance(rewards, list)
            or not isinstance(fingerprints, list)
            or len(rewards) != descriptors.shape[0]
            or len(fingerprints) != descriptors.shape[0]
        ):
            raise ValueError("invalid shadow candidate record")
        parsed_rewards = [_finite_number(value) for value in rewards]
        if any(value is None for value in parsed_rewards) or any(
            not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]+|[A-Za-z0-9]+", value)
            for value in fingerprints
        ):
            raise ValueError("invalid shadow reward or fingerprint")
        mapped, overflow = cell_ids(descriptors, bounds, profile["qd_grid_shape"])
        batch: dict[int, list[dict[str, object]]] = {}
        for index, cell in enumerate(mapped.tolist()):
            batch.setdefault(int(cell), []).append(
                {
                    "reward": float(parsed_rewards[index]),
                    "fingerprint": str(fingerprints[index]),
                    "descriptor_xy_m": [float(value) for value in descriptors[index].tolist()],
                    "source_iter": int(record["iter_idx"]),
                }
            )
        insertions = replacements = rejections = 0
        for cell in sorted(batch):
            candidates = sorted(
                batch[cell], key=lambda item: (-float(item["reward"]), str(item["fingerprint"]))
            )
            winner = candidates[0]
            incumbent = archive.get(cell)
            better = incumbent is None or (
                float(winner["reward"]) > float(incumbent["reward"])
                or (
                    float(winner["reward"]) == float(incumbent["reward"])
                    and str(winner["fingerprint"]) < str(incumbent["fingerprint"])
                )
            )
            if better:
                if incumbent is None:
                    insertions += 1
                else:
                    replacements += 1
                archive[cell] = winner
                rejections += len(candidates) - 1
            else:
                rejections += len(candidates)
        count = int(descriptors.shape[0])
        if insertions + replacements + rejections != count:
            raise RuntimeError("shadow archive update accounting mismatch")
        evaluation_count += count
        total_insertions += insertions
        total_replacements += replacements
        total_rejections += rejections
        overflow_ratio = float(overflow.sum().item() / count)
        overflow_ratios.append(overflow_ratio)
        descriptors_in_archive = torch.tensor(
            [archive[cell]["descriptor_xy_m"] for cell in sorted(archive)],
            dtype=torch.float32,
        )
        spread = (
            float(torch.pdist(descriptors_in_archive).mean().item())
            if descriptors_in_archive.shape[0] >= 2
            else 0.0
        )
        timeline.append(
            {
                "iter_idx": int(record["iter_idx"]),
                "occupied_cells": len(archive),
                "coverage_ratio": len(archive)
                / int(profile["qd_grid_shape"][0] * profile["qd_grid_shape"][1]),
                "endpoint_xy_spread_m": spread,
                "best_reward": max(float(item["reward"]) for item in archive.values()),
                "overflow_ratio": overflow_ratio,
                "insertions": insertions,
                "replacements": replacements,
                "rejections": rejections,
            }
        )

    final = timeline[-1]
    return {
        "bounds_xy_m": [bounds.lo.tolist(), bounds.hi.tolist()],
        "bounds_source_initial_checksum": bounds.checksum,
        "grid_shape": list(profile["qd_grid_shape"]),
        "evaluation_count": evaluation_count,
        "occupied_cells": len(archive),
        "coverage_ratio": final["coverage_ratio"],
        "endpoint_xy_spread_m": final["endpoint_xy_spread_m"],
        "best_reward": final["best_reward"],
        "overflow_ratio_p95": _percentile(overflow_ratios, 0.95),
        "insertion_count": total_insertions,
        "replacement_count": total_replacements,
        "rejection_count": total_rejections,
        "archive": {str(cell): archive[cell] for cell in sorted(archive)},
        "timeline": timeline,
    }


def qd_mechanism_hard_gate(
    metrics: list[dict[str, Any]], profile: dict[str, object]
) -> dict[str, object]:
    failures: list[str] = []
    for index, record in enumerate(metrics):
        identity = f"{record.get('episode')}/{record.get('global_step', index)}"
        if record.get("qd_archive_enabled") is not True:
            failures.append(f"{identity}: QD archive not enabled")
            continue
        if record.get("qd_evaluation_count") != 176:
            failures.append(f"{identity}: complete chunk evaluation count != 176")
        if record.get("score_call_count") != 11:
            failures.append(f"{identity}: reward call budget != 11")
        if record.get("qd_accounting_violation_count") != 0:
            failures.append(f"{identity}: archive accounting violation")
        if record.get("qd_elite_monotonicity_violation_count") != 0:
            failures.append(f"{identity}: elite monotonicity violation")
        if record.get("qd_final_selection_mismatch_count") != 0:
            failures.append(f"{identity}: final selection mismatch")
        if record.get("qd_fallback_used") is not False:
            failures.append(f"{identity}: QD fallback")
        initial = record.get("qd_initial_accounting")
        if not isinstance(initial, dict) or sum(
            int(initial.get(key, -1000))
            for key in ("insertions", "replacements", "rejections")
        ) != 16:
            failures.append(f"{identity}: initial accounting != 16")
        insertions = record.get("qd_archive_insertions_by_iter")
        replacements = record.get("qd_archive_replacements_by_iter")
        rejections = record.get("qd_archive_rejections_by_iter")
        if not all(isinstance(value, list) and len(value) == 10 for value in (insertions, replacements, rejections)):
            failures.append(f"{identity}: ten archive iterations required")
        else:
            for iteration, triple in enumerate(zip(insertions, replacements, rejections)):
                if sum(int(value) for value in triple) != 16:
                    failures.append(f"{identity}: iter {iteration} accounting != 16")
        slots = record.get("qd_parent_slots_by_cell_by_iter")
        weights = record.get("qd_parent_weights_by_cell_by_iter")
        if not isinstance(slots, list) or len(slots) != 10:
            failures.append(f"{identity}: ten parent allocations required")
            continue
        for iteration, allocation in enumerate(slots):
            if not isinstance(allocation, dict) or sum(int(value) for value in allocation.values()) != 16:
                failures.append(f"{identity}: iter {iteration} slot sum != 16")
                continue
            counts = [int(value) for value in allocation.values()]
            if profile["qd_parent_sampling"] == "uniform_cells":
                if max(counts) - min(counts) > 1:
                    failures.append(f"{identity}: iter {iteration} uniform imbalance")
            else:
                if not isinstance(weights, list) or len(weights) != 10:
                    failures.append(f"{identity}: sparse weights missing")
                    break
                iteration_weights = weights[iteration]
                if set(iteration_weights) != set(allocation):
                    failures.append(f"{identity}: iter {iteration} sparse cell mismatch")
                    continue
                raw = {cell: float(iteration_weights[cell]) for cell in allocation}
                total = sum(raw.values())
                exact = {cell: 16.0 * raw[cell] / total for cell in raw}
                floors = {cell: math.floor(exact[cell]) for cell in raw}
                remainder = 16 - sum(floors.values())
                extras = sum(int(allocation[cell]) - floors[cell] for cell in raw)
                if extras != remainder or any(int(allocation[cell]) - floors[cell] not in {0, 1} for cell in raw):
                    failures.append(f"{identity}: iter {iteration} largest-remainder mismatch")
                selected_fractions = sorted(
                    (exact[cell] - floors[cell] for cell in raw if int(allocation[cell]) > floors[cell]),
                    reverse=True,
                )
                rejected_fractions = sorted(
                    (exact[cell] - floors[cell] for cell in raw if int(allocation[cell]) == floors[cell]),
                    reverse=True,
                )
                if selected_fractions and rejected_fractions and min(selected_fractions) + 1e-9 < max(rejected_fractions):
                    failures.append(f"{identity}: iter {iteration} remainder priority mismatch")
    unique = list(dict.fromkeys(failures))
    return {
        "passed": bool(metrics) and not unique,
        "active_chunk_count": len(metrics),
        "additional_reward_model_vlm_calls_vs_control": 0 if metrics and not any("reward call" in item for item in unique) else None,
        "failures": unique,
    }


def validate_parent_allocation_replay(
    record: dict[str, Any], profile: dict[str, object]
) -> dict[str, object]:
    """Recompute archive visits and exact deterministic parent allocation."""
    failures: list[str] = []
    stream = record.get("shadow_qd_candidate_stream")
    if not isinstance(stream, list) or len(stream) != 11:
        return {"passed": False, "failures": ["candidate stream must contain initial + 10 iterations"]}
    checksum = hashlib.sha256(_canonical(stream).encode()).hexdigest()
    if checksum != record.get("shadow_qd_observer_checksum"):
        failures.append("candidate stream checksum mismatch")
    if [item.get("iter_idx") for item in stream if isinstance(item, dict)] != list(range(-1, 10)):
        failures.append("candidate stream iteration identity mismatch")
        return {"passed": False, "failures": failures}
    try:
        initial_descriptors = torch.tensor(
            stream[0]["descriptors_xy_m"], dtype=torch.float32
        )
        bounds = _profile_bounds(profile, initial_descriptors)
    except (KeyError, TypeError, ValueError, FloatingPointError) as exc:
        failures.append(f"initial bounds replay failed: {type(exc).__name__}")
        return {"passed": False, "failures": failures}
    observed_bounds = record.get("qd_bounds_xy_m")
    try:
        observed_bounds_tensor = torch.tensor(observed_bounds, dtype=torch.float32)
    except (TypeError, ValueError):
        observed_bounds_tensor = torch.empty(0)
    expected_bounds_tensor = torch.stack((bounds.lo, bounds.hi))
    if observed_bounds_tensor.shape != (2, 2) or not torch.equal(
        observed_bounds_tensor, expected_bounds_tensor
    ):
        failures.append("fixed bounds values do not match initial-population replay")
    if record.get("qd_bounds_source_initial_checksum") != bounds.checksum:
        failures.append("fixed bounds checksum mismatch")

    archive = QDArchive(grid_shape=profile["qd_grid_shape"])

    def update_archive(group: dict[str, Any], source_iter: int) -> None:
        descriptors = torch.tensor(group["descriptors_xy_m"], dtype=torch.float32)
        rewards = torch.tensor(group["rewards"], dtype=torch.float32)
        if descriptors.shape != (16, 2) or rewards.shape != (16,):
            raise ValueError("each candidate stream group must contain 16 candidates")
        mapped, _ = cell_ids(descriptors, bounds, profile["qd_grid_shape"])
        actions = (
            torch.arange(32, dtype=torch.float32).reshape(16, 2)
            + 1000.0 * (source_iter + 1)
        )
        archive.update(
            actions=actions,
            rewards=rewards,
            costs=-rewards,
            descriptors=descriptors,
            cell_ids=mapped,
            source_iter=source_iter,
        )

    try:
        update_archive(stream[0], -1)
    except (KeyError, TypeError, ValueError, FloatingPointError, RuntimeError) as exc:
        failures.append(f"initial archive replay failed: {type(exc).__name__}")
        return {"passed": False, "failures": failures}
    observed_slots = record.get("qd_parent_slots_by_cell_by_iter")
    observed_weights = record.get("qd_parent_weights_by_cell_by_iter")
    if not isinstance(observed_slots, list) or len(observed_slots) != 10:
        failures.append("ten observed parent slot allocations required")
        return {"passed": False, "failures": failures}
    if not isinstance(observed_weights, list) or len(observed_weights) != 10:
        failures.append("ten observed parent weight allocations required")
        return {"passed": False, "failures": failures}
    replay_rows = []
    for iteration in range(10):
        allocation = allocate_parent_slots(
            archive,
            population_size=16,
            sampling=str(profile["qd_parent_sampling"]),
            sparse_exponent=float(profile.get("qd_sparse_exponent", 1.0)),
            run_seed=int(profile.get("seed", 0)),
            episode=int(record.get("episode", 0)),
            global_step=int(record.get("global_step", 0)),
            iter_idx=iteration,
        )
        expected_slots = {
            str(cell): int(value)
            for cell, value in allocation.slot_counts.items()
        }
        expected_weights = {
            str(cell): float(value)
            for cell, value in allocation.weights.items()
        }
        actual_slots = observed_slots[iteration]
        actual_weights = observed_weights[iteration]
        if actual_slots != expected_slots:
            failures.append(f"iter {iteration} exact parent slots mismatch")
        if not isinstance(actual_weights, dict) or set(actual_weights) != set(expected_weights) or any(
            not math.isclose(
                float(actual_weights[cell]),
                expected_weights[cell],
                rel_tol=0.0,
                abs_tol=1.0e-12,
            )
            for cell in expected_weights
        ):
            failures.append(f"iter {iteration} inverse-visitation weights mismatch")
        replay_rows.append(
            {
                "iter_idx": iteration,
                "expected_slots": expected_slots,
                "expected_weights": expected_weights,
                "cumulative_visits": archive.cumulative_visits.tolist(),
            }
        )
        try:
            update_archive(stream[iteration + 1], iteration)
        except (KeyError, TypeError, ValueError, FloatingPointError, RuntimeError) as exc:
            failures.append(f"iter {iteration} archive replay failed: {type(exc).__name__}")
            break
    return {
        "passed": not failures,
        "stream_checksum": checksum,
        "bounds_checksum": bounds.checksum,
        "replay": replay_rows,
        "failures": list(dict.fromkeys(failures)),
    }


def compare_mechanism(
    candidate_metrics: list[dict[str, Any]],
    control_metrics: list[dict[str, Any]],
    profile: dict[str, object],
) -> dict[str, object]:
    controls = {
        (record.get("episode"), record.get("global_step")): record
        for record in control_metrics
        if record.get("shadow_qd_observer_enabled") is True
    }
    coverage_delta: list[float] = []
    spread_ratio: list[float] = []
    best_delta: list[float] = []
    overflow: list[float] = []
    pairs: list[dict[str, object]] = []
    replacement_active = 0
    for record in candidate_metrics:
        key = (record.get("episode"), record.get("global_step"))
        control = controls.get(key)
        if control is None:
            continue
        shadow = replay_shadow_archive(control["shadow_qd_candidate_stream"], profile)
        candidate_coverage = _finite_number((record.get("qd_coverage_ratio_by_iter") or [None])[-1])
        candidate_spread = _finite_number((record.get("qd_archive_endpoint_xy_spread_m_by_iter") or [None])[-1])
        candidate_best = _finite_number((record.get("qd_archive_best_reward_by_iter") or [None])[-1])
        if None in (candidate_coverage, candidate_spread, candidate_best):
            continue
        shadow_spread = float(shadow["endpoint_xy_spread_m"])
        ratio = (
            float(candidate_spread / shadow_spread)
            if shadow_spread > 0.0
            else (1.0 if candidate_spread == 0.0 else math.inf)
        )
        delta_coverage = float(candidate_coverage - float(shadow["coverage_ratio"]))
        delta_best = float(candidate_best - float(shadow["best_reward"]))
        coverage_delta.append(delta_coverage)
        spread_ratio.append(ratio)
        best_delta.append(delta_best)
        chunk_overflow = [
            float(value)
            for value in record.get("qd_descriptor_overflow_ratio_by_iter", [])
            if _finite_number(value) is not None
        ]
        overflow.extend(chunk_overflow)
        active = any(int(value) > 0 for value in record.get("qd_archive_replacements_by_iter", []))
        replacement_active += int(active)
        pairs.append(
            {
                "episode": key[0],
                "global_step": key[1],
                "candidate_coverage": candidate_coverage,
                "shadow_coverage": shadow["coverage_ratio"],
                "normalized_coverage_delta": delta_coverage,
                "candidate_endpoint_xy_spread_m": candidate_spread,
                "shadow_endpoint_xy_spread_m": shadow_spread,
                "endpoint_xy_spread_ratio": ratio,
                "candidate_archive_best_reward": candidate_best,
                "shadow_archive_best_reward": shadow["best_reward"],
                "archive_best_reward_delta": delta_best,
                "replacement_active": active,
                "shadow_replay_checksum": hashlib.sha256(_canonical(shadow).encode()).hexdigest(),
            }
        )
    return {
        "paired_count": len(pairs),
        "candidate_chunk_count": len(candidate_metrics),
        "unpaired_candidate_chunk_count": len(candidate_metrics) - len(pairs),
        "normalized_final_coverage_delta_median": _median(coverage_delta),
        "endpoint_xy_spread_ratio_median": _median(spread_ratio),
        "archive_best_reward_delta_median": _median(best_delta),
        "replacement_active_chunk_ratio": (
            replacement_active / len(candidate_metrics) if candidate_metrics else None
        ),
        "descriptor_overflow_ratio_p95": _percentile(overflow, 0.95),
        "pairs": pairs,
    }


def evaluate_candidate_gates(
    candidate: dict[str, Any], control: dict[str, Any]
) -> dict[str, object]:
    candidate_tasks = set(candidate.get("success_tasks", []))
    control_tasks = set(control.get("success_tasks", []))
    gained = sorted(candidate_tasks - control_tasks)
    lost = sorted(control_tasks - candidate_tasks)
    retained = sorted(candidate_tasks & control_tasks)
    task_failures = []
    if candidate.get("success_count", 0) < 5:
        task_failures.append("success_count < 5")
    if candidate.get("success_count", 0) < control.get("success_count", 0):
        task_failures.append("success_count < control")
    if len(gained) < len(lost):
        task_failures.append("paired gained_tasks < lost_tasks")
    mechanism = candidate.get("mechanism_comparison", {})
    claim_checks = {
        "normalized_final_coverage_delta_median_ge_0.05": (
            _finite_number(mechanism.get("normalized_final_coverage_delta_median")) is not None
            and float(mechanism["normalized_final_coverage_delta_median"]) >= 0.05
        ),
        "endpoint_xy_spread_ratio_median_ge_0.90": (
            _finite_number(mechanism.get("endpoint_xy_spread_ratio_median")) is not None
            and float(mechanism["endpoint_xy_spread_ratio_median"]) >= 0.90
        ),
        "archive_best_reward_delta_median_ge_0": (
            _finite_number(mechanism.get("archive_best_reward_delta_median")) is not None
            and float(mechanism["archive_best_reward_delta_median"]) >= 0.0
        ),
        "replacement_active_chunk_ratio_ge_0.50": (
            _finite_number(mechanism.get("replacement_active_chunk_ratio")) is not None
            and float(mechanism["replacement_active_chunk_ratio"]) >= 0.50
        ),
        "descriptor_overflow_ratio_p95_le_0.25": (
            _finite_number(mechanism.get("descriptor_overflow_ratio_p95")) is not None
            and float(mechanism["descriptor_overflow_ratio_p95"]) <= 0.25
        ),
    }
    safety_checks = {
        "qpos_execution_error_episodes_eq_0": candidate.get("execution_qpos_error_episodes") == 0,
        "collision_composite_le_control": candidate.get("collision_push_drop_wrong_object", math.inf)
        <= control.get("collision_push_drop_wrong_object", -math.inf),
        "nonfinite_eq_0": candidate.get("nonfinite_count") == 0,
        "action_mask_violation_eq_0": candidate.get("action_mask_violation_count") == 0,
        "algorithm_fallback_eq_0": candidate.get("qd_fallback_count") == 0,
    }
    validity_passed = candidate.get("valid") is True
    hard_passed = candidate.get("mechanism_hard", {}).get("passed") is True
    task_passed = not task_failures
    claim_passed = bool(claim_checks) and all(claim_checks.values())
    safety_passed = all(safety_checks.values())
    return {
        "validity": {"passed": validity_passed, "failures": candidate.get("validity_failures", [])},
        "paired": {
            "gained_tasks": gained,
            "lost_tasks": lost,
            "retained_control_tasks": retained,
            "gained_minus_lost": len(gained) - len(lost),
        },
        "task": {"passed": task_passed, "failures": task_failures},
        "mechanism_hard": candidate.get("mechanism_hard", {"passed": False}),
        "mechanism_claim": {
            "passed": claim_passed,
            "checks": claim_checks,
            "failures": [key for key, passed in claim_checks.items() if not passed],
        },
        "safety": {
            "passed": safety_passed,
            "checks": safety_checks,
            "failures": [key for key, passed in safety_checks.items() if not passed],
        },
        "all_passed": validity_passed and task_passed and hard_passed and claim_passed and safety_passed,
    }


def rank_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def desc(value: object) -> float:
        parsed = _finite_number(value)
        return -parsed if parsed is not None else math.inf

    def asc(value: object) -> float:
        parsed = _finite_number(value)
        return parsed if parsed is not None else math.inf

    ordered = sorted(
        (row for row in candidates if row.get("valid") is True),
        key=lambda row: (
            desc(row.get("success_count")),
            desc(row.get("control_task_retention")),
            desc(row.get("paired_gained_minus_lost")),
            asc(row.get("execution_qpos_error_episodes")),
            asc(row.get("collision_push_drop_wrong_object")),
            desc(row.get("normalized_coverage_gain")),
            desc(row.get("endpoint_xy_spread_retention")),
            desc(row.get("archive_best_reward_delta")),
            asc(row.get("selection_latency_p95_s")),
            str(row.get("label", "")),
        ),
    )
    return [{**row, "rank": rank} for rank, row in enumerate(ordered, 1)]


def audit_attempt_ledger(
    path: Path,
    *,
    expected_formal: set[tuple[str, int, int]],
    expected_preflight: set[tuple[str, int, int]],
    cap: int,
    recovery_limit: int = runner.RECOVERY_ATTEMPT_LIMIT,
) -> dict[str, object]:
    records, failures = _read_jsonl(path)
    attempts = [
        row
        for row in records
        if row.get("record_type", "episode_attempt") == "episode_attempt"
    ]
    events = [row for row in records if row not in attempts]
    ids = [row.get("attempt_id") for row in attempts]
    if ids != list(range(1, len(attempts) + 1)):
        failures.append("attempt ids are not contiguous")
    event_ids = [row.get("ledger_event_id") for row in events]
    if event_ids != list(range(1, len(events) + 1)):
        failures.append("attempt event ids are not contiguous")
    known_ids = {int(row["attempt_id"]) for row in attempts if isinstance(row.get("attempt_id"), int)}
    void_ids: set[int] = set()
    dispatched_ids: set[int] = set()
    aborted_pre_episode_ids: set[int] = set()
    for event in events:
        event_type = event.get("record_type")
        event_attempt_ids = event.get("attempt_ids")
        if event_type not in {
            "reservation_void",
            "phase_dispatch",
            "dispatch_aborted_pre_episode",
        }:
            failures.append(f"unknown attempt ledger event: {event_type}")
            continue
        if not isinstance(event_attempt_ids, list) or not set(event_attempt_ids) <= known_ids:
            failures.append(f"invalid {event_type} attempt ids")
            continue
        if event_type == "reservation_void":
            if set(event_attempt_ids) & dispatched_ids:
                failures.append("dispatched reservations were voided")
            void_ids.update(int(value) for value in event_attempt_ids)
        elif event_type == "phase_dispatch":
            if set(event_attempt_ids) & (void_ids | dispatched_ids):
                failures.append("void/dispatched reservation was dispatched again")
            dispatched_ids.update(int(value) for value in event_attempt_ids)
        else:
            if not set(event_attempt_ids) <= (
                dispatched_ids - aborted_pre_episode_ids
            ):
                failures.append("non-dispatched attempt marked pre-episode aborted")
            aborted_pre_episode_ids.update(
                int(value) for value in event_attempt_ids
            )
    active = [
        row
        for row in attempts
        if int(row["attempt_id"])
        not in (void_ids | aborted_pre_episode_ids)
    ]
    effective_dispatched_ids = dispatched_ids - aborted_pre_episode_ids
    dispatched = [
        row
        for row in active
        if int(row["attempt_id"]) in effective_dispatched_ids
    ]
    if len(dispatched) > cap:
        failures.append(f"actual episode-attempt cap exceeded: {len(dispatched)} > {cap}")
    undispatched = sorted(
        int(row["attempt_id"])
        for row in active
        if int(row["attempt_id"]) not in dispatched_ids
    )
    if undispatched:
        failures.append("active reservations were not dispatched: " + ",".join(map(str, undispatched)))
    actual_formal = {
        (str(row.get("formal_label", row.get("label"))), int(row.get("task_id")), int(row.get("episode_seed")))
        for row in active
        if row.get("phase") == "formal"
        and isinstance(row.get("task_id"), int)
        and isinstance(row.get("episode_seed"), int)
    }
    actual_preflight = {
        (str(row.get("formal_label", row.get("label"))), int(row.get("task_id")), int(row.get("episode_seed")))
        for row in active
        if row.get("phase") == "preflight"
        and isinstance(row.get("task_id"), int)
        and isinstance(row.get("episode_seed"), int)
    }
    if actual_formal != expected_formal:
        failures.append("formal ledger cells do not match frozen matrix")
    if actual_preflight != expected_preflight:
        failures.append("preflight ledger cells do not match frozen matrix")
    identities = [
        (
            row.get("phase"),
            row.get("formal_label", row.get("label")),
            row.get("task_id"),
            row.get("episode_seed"),
        )
        for row in dispatched
    ]
    retries = len(identities) - len(set(identities))
    if retries > recovery_limit:
        failures.append(
            f"recovery attempts exceed {recovery_limit}: {retries}"
        )
    return {
        "passed": not failures,
        "attempt_count": len(dispatched),
        "actual_episode_attempt_count": len(dispatched),
        "reserved_attempt_count": len(attempts),
        "void_reservation_count": len(void_ids),
        "aborted_pre_episode_count": len(aborted_pre_episode_ids),
        "raw_ledger_record_count": len(records),
        "formal_unique_cells": len(actual_formal),
        "preflight_unique_cells": len(actual_preflight),
        "recovery_attempts": retries,
        "failures": list(dict.fromkeys(failures)),
        "records": records,
    }


def _walk(value: object) -> Iterable[tuple[str, object]]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key), item
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _telemetry_counts(metrics: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "nonfinite_count": 0,
        "action_mask_violation_count": 0,
        "qd_fallback_count": 0,
        "execution_qpos_error_episodes": 0,
    }
    qpos_episodes: set[int] = set()
    for record in metrics:
        for key, value in _walk(record):
            if key in {"nonfinite_count", "direction_rbf_nonfinite_count"} and isinstance(value, int) and not isinstance(value, bool):
                counts["nonfinite_count"] += max(0, value)
            if key == "action_mask_violation_max" and _finite_number(value) is not None and float(value) > 1e-8:
                counts["action_mask_violation_count"] += 1
            if key == "qd_fallback_used" and value is True:
                counts["qd_fallback_count"] += 1
            if key == "gripper_qpos_violation_count" and isinstance(value, int) and value > 0 and isinstance(record.get("episode"), int):
                qpos_episodes.add(int(record["episode"]))
    counts["execution_qpos_error_episodes"] = len(qpos_episodes)
    return counts


def _outcomes(output_dir: Path, episodes: int) -> tuple[dict[int, str], list[str], list[Path]]:
    failures: list[str] = []
    outcomes: dict[int, str] = {}
    videos: list[Path] = []
    hashes: set[str] = set()
    for episode in range(episodes):
        found = list((output_dir / f"episode_{episode + 1}").glob("*.mp4"))
        if len(found) != 1:
            failures.append(f"episode {episode} video count {len(found)} != 1")
            continue
        video = found[0]
        videos.append(video)
        digest = _sha256_file(video)
        if digest in hashes:
            failures.append(f"episode {episode} duplicate video checksum")
        hashes.add(digest)
        if "_success_" in video.name:
            outcomes[episode] = "success"
        elif "_fail_" in video.name:
            outcomes[episode] = "fail"
        else:
            failures.append(f"episode {episode} video outcome suffix missing")
    return outcomes, failures, videos


def _classify_failures(
    outcomes: dict[int, str], metrics: list[dict[str, Any]], output_dir: Path
) -> dict[int, str]:
    by_episode: dict[int, list[dict[str, Any]]] = {}
    for record in metrics:
        if isinstance(record.get("episode"), int):
            by_episode.setdefault(int(record["episode"]), []).append(record)
    episode_ids = set(outcomes)
    for error_path in output_dir.glob("episode_*/error.txt"):
        match = re.fullmatch(r"episode_(\d+)", error_path.parent.name)
        if match and int(match.group(1)) > 0:
            episode_ids.add(int(match.group(1)) - 1)
    result: dict[int, str] = {}
    for episode in sorted(episode_ids):
        outcome = outcomes.get(episode, "fail")
        if outcome == "success":
            result[episode] = "success"
            continue
        episode_records = by_episode.get(episode, [])
        error_path = output_dir / f"episode_{episode + 1}" / "error.txt"
        error_text = (
            error_path.read_text(encoding="utf-8", errors="replace").lower()
            if error_path.is_file()
            else ""
        )

        def positive_key(*tokens: str) -> bool:
            for record in episode_records:
                for key, value in _walk(record):
                    normalized = key.lower().replace("-", "_")
                    if not any(token in normalized for token in tokens):
                        continue
                    if value is True or (
                        _finite_number(value) is not None and float(value) > 0.0
                    ):
                        return True
            return False

        if error_text and (
            "traceback" in error_text
            or "error during episode execution" in error_text
            or "exception" in error_text
        ):
            result[episode] = "qpos/execution error"
        elif positive_key("qpos"):
            result[episode] = "qpos/execution error"
        elif positive_key("wrong_object"):
            result[episode] = "clutter swept/wrong-object interaction"
        elif positive_key("collision"):
            result[episode] = "basket displaced/collision"
        elif positive_key("drop"):
            result[episode] = "target dropped after grasp"
        elif positive_key("push"):
            result[episode] = "target pushed away"
        else:
            result[episode] = "timeout without completion"
    return result


def _execution_error_episode_count(
    telemetry: dict[str, int], classifications: dict[int, str]
) -> int:
    return max(
        int(telemetry.get("execution_qpos_error_episodes", 0)),
        sum(value == "qpos/execution error" for value in classifications.values()),
    )


def _qualitative_failures(output_dir: Path, episodes: int, *, qd: bool) -> list[str]:
    failures = []
    for episode in range(episodes):
        root = output_dir / "eds_eval/qualitative" / f"episode_{episode:03d}"
        chunks = [path for path in root.glob("chunk_*") if path.is_dir()]
        if not chunks:
            failures.append(f"episode {episode} qualitative chunks missing")
            continue
        if not qd:
            continue
        required = {
            "qd_archive_heatmap_initial.png",
            "qd_archive_heatmap_iter_001.png",
            "qd_archive_heatmap_iter_005.png",
            "qd_archive_heatmap_iter_010.png",
            "qd_archive_trajectories_initial.png",
            "qd_archive_trajectories_iter_001.png",
            "qd_archive_trajectories_iter_005.png",
            "qd_archive_trajectories_iter_010.png",
            "qd_archive_timeline.json",
        }
        for chunk in chunks:
            names = {path.name for path in chunk.iterdir() if path.is_file() and path.stat().st_size > 0}
            missing = sorted(required - names)
            if missing:
                failures.append(f"episode {episode}/{chunk.name} QD qualitative missing: {','.join(missing)}")
    return failures


def _job_checksums(output_dir: Path) -> dict[str, str]:
    checksums: dict[str, str] = {}
    accepted = {
        "results.txt",
        "config_fingerprint.txt",
        "job_manifest.json",
        "config.yaml",
        "overrides.yaml",
        "hydra.yaml",
        "eds_metrics.jsonl",
        "episode_metadata.jsonl",
        "stage_events.jsonl",
        "main.log",
        "error.txt",
    }
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        if path.name in accepted or path.suffix in {".mp4", ".npz", ".png"}:
            checksums[path.relative_to(output_dir).as_posix()] = _sha256_file(path)
    log_path = output_dir.parent.parent / "runner_logs" / output_dir.parent.name / f"{output_dir.name}.log"
    if log_path.is_file():
        checksums[f"runner_log:{log_path.name}"] = _sha256_file(log_path)
    return checksums


def _error_evidence(output_dir: Path, episodes: int) -> list[dict[str, object]]:
    evidence: list[dict[str, object]] = []
    exception_pattern = re.compile(
        r"(?m)^([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception)):\s*(.*)$"
    )
    for episode in range(episodes):
        path = output_dir / f"episode_{episode + 1}" / "error.txt"
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        matches = list(exception_pattern.finditer(text))
        exception_type = matches[-1].group(1) if matches else "execution_error"
        message = matches[-1].group(2).strip() if matches else ""
        evidence.append(
            {
                "episode": episode,
                "path": str(path),
                "sha256": _sha256_file(path),
                "exception_type": exception_type,
                "message": message[:240],
                "qpos_related": "qpos" in text.lower(),
            }
        )
    return evidence


def _metric_summary(metrics: list[dict[str, Any]], stages: list[dict[str, Any]]) -> dict[str, object]:
    final_values = lambda key: [record.get(key, [None])[-1] if isinstance(record.get(key), list) and record.get(key) else None for record in metrics]
    selected_cells = Counter(
        str(record["qd_selected_cell"])
        for record in metrics
        if record.get("qd_selected_cell") is not None
    )
    per_cell_rewards: dict[str, list[float]] = {}
    for record in metrics:
        per_iter = record.get("qd_per_cell_elite_reward_by_iter")
        if not isinstance(per_iter, list) or not per_iter or not isinstance(per_iter[-1], dict):
            continue
        for cell, value in per_iter[-1].items():
            parsed = _finite_number(value)
            if parsed is not None:
                per_cell_rewards.setdefault(str(cell), []).append(float(parsed))
    return {
        "selection_latency_p95_s": _percentile((record.get("select_action_latency_s") for record in metrics), 0.95),
        "qd_archive_update_latency_p95_s": _percentile((record.get("qd_archive_update_latency_s") for record in metrics), 0.95),
        "qd_parent_allocation_latency_p95_s": _percentile((record.get("qd_parent_allocation_latency_s") for record in metrics), 0.95),
        "eds_loop_latency_p95_s": _percentile((record.get("eds_loop_latency_s") for record in metrics), 0.95),
        "stage_query_latency_p95_s": _percentile((record.get("query_latency_s") for record in stages), 0.95),
        "endpoint_xy_spread_median": _median(final_values("qd_archive_endpoint_xy_spread_m_by_iter")),
        "coverage_median": _median(final_values("qd_coverage_ratio_by_iter")),
        "turnover_median": _median(value for record in metrics for value in record.get("qd_archive_turnover_ratio_by_iter", [])),
        "overflow_p95": _percentile((value for record in metrics for value in record.get("qd_descriptor_overflow_ratio_by_iter", [])), 0.95),
        "eef_direction_diversity_median": _median(final_values("eef_direction_diversity_by_iter")),
        "trajectory_length_median": _median(final_values("selected_trajectory_length_by_iter")),
        "max_step_median": _median(final_values("selected_max_step_displacement_by_iter")),
        "chunk_boundary_jump_p95": _percentile((record.get("chunk_boundary_action_jump") for record in metrics), 0.95),
        "global_best_reward_median": _median(
            record.get("qd_selected_reward") for record in metrics
        ),
        "selected_cell_counts": dict(sorted(selected_cells.items())),
        "per_cell_elite_reward_median": {
            cell: _median(values) for cell, values in sorted(per_cell_rewards.items())
        },
    }


def _bind_frozen_job_identity_for_audit(job: dict[str, object]) -> None:
    """Use the dispatch identity while revalidating current matrix semantics."""
    manifest_path = runner.base._output_dir(job) / "job_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, RecursionError):
        return
    if not isinstance(manifest, dict):
        return
    execution_record = manifest.get("execution_record")
    config_fingerprint = manifest.get("config_fingerprint")
    if not isinstance(execution_record, dict) or not isinstance(
        config_fingerprint, str
    ):
        return
    job["execution_record"] = execution_record
    job["config_fingerprint"] = config_fingerprint


def audit_job(
    job: dict[str, object],
    *,
    credential_passed: bool,
    base_validity_fn: Callable[[dict[str, object]], dict[str, object]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with runner.configured_base():
        output_dir = runner.base._output_dir(job)
        _bind_frozen_job_identity_for_audit(job)
        if base_validity_fn is None:
            base_validity = runner.base._p2_job_validity(
                job, allow_identical_overrides=True
            )
        else:
            base_validity = base_validity_fn(job)
    failures = [] if base_validity.get("valid") is True else [str(base_validity.get("failure_reason", "base validity failed"))]
    try:
        output_dir.resolve(strict=True).relative_to(OUTPUT_TARGET.resolve(strict=True))
    except (OSError, ValueError):
        failures.append("output realpath outside approved QD shared2 root")
    metrics, metric_failures = _read_jsonl(output_dir / "eds_eval/eds_metrics.jsonl")
    stages, stage_failures = _read_jsonl(output_dir / "eds_eval/stage_events.jsonl")
    metadata, metadata_failures = _read_jsonl(output_dir / "eds_eval/episode_metadata.jsonl")
    failures.extend(metric_failures + stage_failures + metadata_failures)
    episodes = int(job["episodes"])
    outcomes, video_failures, videos = _outcomes(output_dir, episodes)
    failures.extend(video_failures)
    expected_metadata = {
        (episode, int(task), int(seed))
        for episode, (task, seed) in enumerate(zip(job["task_ids_filter"], job["episode_seeds"]))
    }
    actual_metadata = {
        (record.get("episode_id"), record.get("task_id"), record.get("episode_seed"))
        for record in metadata
    }
    if actual_metadata != expected_metadata:
        failures.append("episode task/seed metadata mismatch")
    command = job["execution_record"]["normalized_command"]
    if "backend.libero.strict_perturbations=true" not in command:
        failures.append("strict perturbation not verified in frozen command")
    if "backend.libero.suite_name=libero_object_swap" not in command:
        failures.append("suite not verified in frozen command")
    if any(record.get("initial_diversity_descriptor_mode") != "absolute_eef" or record.get("rollout_diversity_descriptor_mode") != "absolute_eef" for record in metrics):
        failures.append("initial/rollout descriptor is not absolute_eef")
    qd = job["qd_archive_mode"] == "grid_archive"
    failures.extend(_qualitative_failures(output_dir, episodes, qd=qd))
    if qd and any(record.get("qd_archive_enabled") is not True for record in metrics):
        failures.append("QD metric enablement mismatch")
    if not qd and any(record.get("qd_archive_enabled") is not False for record in metrics):
        failures.append("control unexpectedly enabled QD archive")
    if any(record.get("shadow_qd_observer_enabled") is not True or not record.get("shadow_qd_candidate_stream") for record in metrics):
        failures.append("shadow observer stream missing")
    telemetry = _telemetry_counts(metrics)
    if telemetry["nonfinite_count"]:
        failures.append("nonfinite telemetry")
    if telemetry["action_mask_violation_count"]:
        failures.append("action-mask violation telemetry")
    if qd and telemetry["qd_fallback_count"]:
        failures.append("QD fallback telemetry")
    if not credential_passed:
        failures.append("credential scan failed")
    classifications = _classify_failures(outcomes, metrics, output_dir)
    error_evidence = _error_evidence(output_dir, episodes)
    success_tasks = sorted(
        int(job["task_ids_filter"][episode])
        for episode, outcome in outcomes.items()
        if outcome == "success"
    )
    collision_count = sum(
        category in COLLISION_COMPOSITE for category in classifications.values()
    )
    lower, upper = wilson_ci(len(success_tasks), episodes) if episodes else (0.0, 0.0)
    unique_failures = list(dict.fromkeys(item for item in failures if item))
    summary = _metric_summary(metrics, stages)
    hard = qd_mechanism_hard_gate(metrics, job) if qd else {
        "passed": bool(metrics) and all(record.get("score_call_count") == 11 for record in metrics),
        "active_chunk_count": len(metrics),
        "failures": [] if metrics and all(record.get("score_call_count") == 11 for record in metrics) else ["control reward call budget mismatch"],
    }
    allocation_replays = []
    if qd:
        for record in metrics:
            replay = validate_parent_allocation_replay(record, job)
            allocation_replays.append(
                {
                    "episode": record.get("episode"),
                    "global_step": record.get("global_step"),
                    **replay,
                }
            )
            if not replay["passed"]:
                hard["failures"].extend(
                    f"{record.get('episode')}/{record.get('global_step')}: {failure}"
                    for failure in replay["failures"]
                )
        hard["failures"] = list(dict.fromkeys(hard["failures"]))
        hard["passed"] = bool(metrics) and not hard["failures"]
        hard["exact_parent_allocation_replay_passed"] = bool(
            allocation_replays
        ) and all(row["passed"] for row in allocation_replays)
    return ({
        "label": job["label"],
        "formal_label": job.get("formal_label", job["label"]),
        "role": job["role"],
        "phase": "preflight" if job["level"] == runner.PREFLIGHT_LEVEL else "formal",
        "output_dir": str(output_dir),
        "execution_status": (
            "artifacts_present" if output_dir.exists() else "not_dispatched"
        ),
        "valid": not unique_failures,
        "validity_failures": unique_failures,
        "base_validity": base_validity,
        "accepted_episode_count": len(outcomes),
        "success_count": len(success_tasks),
        "success_rate": len(success_tasks) / episodes if episodes else None,
        "wilson_95": [lower, upper],
        "success_tasks": success_tasks,
        "task_outcomes": {str(job["task_ids_filter"][episode]): outcome for episode, outcome in sorted(outcomes.items())},
        "failure_taxonomy": {str(job["task_ids_filter"][episode]): category for episode, category in sorted(classifications.items())},
        "failure_taxonomy_counts": dict(Counter(classifications.values())),
        "error_evidence": error_evidence,
        "collision_push_drop_wrong_object": collision_count,
        **telemetry,
        "execution_qpos_error_episodes": _execution_error_episode_count(
            telemetry, classifications
        ),
        "metrics_record_count": len(metrics),
        "stage_event_count": len(stages),
        "video_count": len(videos),
        "config_fingerprint": job["config_fingerprint"],
        "code_state_sha256": job["execution_record"]["code_state_sha256"],
        "mechanism_hard": hard,
        "parent_allocation_replays": allocation_replays,
        "metric_summary": summary,
        **summary,
        "checksums": _job_checksums(output_dir),
    }, metrics)


def scan_credentials(roots: list[Path]) -> dict[str, object]:
    findings: list[dict[str, str]] = []
    secret_values = [
        value.encode()
        for name in ("OPENAI_API_KEY", "GOOGLE_API_KEY")
        if (value := os.environ.get(name, "").strip())
    ]
    patterns = [
        re.compile(rb"\bsk-[A-Za-z0-9_-]{16,}\b"),
        re.compile(rb"(?i)\bapi[_-]?key\s*[:=]\s*[\"']?[A-Za-z0-9_-]{16,}"),
        re.compile(rb"(?i)authorization:\s*bearer\s+[A-Za-z0-9._-]{16,}"),
    ]
    for root in roots:
        if not root.exists():
            continue
        paths = [root] if root.is_file() else root.rglob("*")
        for path in paths:
            if not path.is_file() or path.is_symlink() or path.suffix.lower() not in TEXT_SCAN_SUFFIXES:
                continue
            try:
                data = path.read_bytes().lower()
            except OSError:
                findings.append({"path": str(path), "reason": "unreadable"})
                continue
            if any(secret.lower() in data for secret in secret_values):
                findings.append({"path": str(path), "reason": "environment credential value"})
            elif "tests" not in path.parts and any(
                pattern.search(data) for pattern in patterns
            ):
                findings.append({"path": str(path), "reason": "credential-like marker"})
    return {"passed": not findings, "finding_count": len(findings), "findings": findings}


def _ffmpeg_frame(video: Path, time_s: float):
    from PIL import Image

    result = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            f"{float(time_s):.3f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "pipe:1",
        ],
        capture_output=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0 or not result.stdout:
        raise RuntimeError("ffmpeg frame extraction failed")
    with Image.open(io.BytesIO(result.stdout)) as image:
        return image.convert("RGB")


def generate_contact_sheets(
    analysis: dict[str, Any],
    *,
    output_root: Path = CONTACT_SHEET_ROOT,
    tasks: Iterable[int] = range(10),
    times_s: Iterable[float] = (1.0, 3.0, 5.0),
    frame_fn: Callable[[Path, float], Any] = _ffmpeg_frame,
) -> dict[str, object]:
    """Create immutable same-task/same-seed sheets at fixed video timestamps."""
    from PIL import Image, ImageDraw, ImageOps

    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=False)
    jobs = list(analysis.get("jobs", []))
    if not jobs:
        raise ValueError("contact sheets require audited jobs")
    sheet_rows = []
    failures: list[str] = []
    tile_width, frame_height, annotation_height = 320, 240, 70
    columns = min(4, len(jobs))
    rows = int(math.ceil(len(jobs) / columns))
    for task in tasks:
        task_id = int(task)
        if not 0 <= task_id < 10:
            raise ValueError("contact sheet task must be in 0..9")
        for raw_time in times_s:
            time_s = float(raw_time)
            if not math.isfinite(time_s) or time_s < 0.0:
                raise ValueError("contact sheet time must be finite and nonnegative")
            canvas = Image.new(
                "RGB",
                (columns * tile_width, rows * (frame_height + annotation_height)),
                color=(16, 16, 16),
            )
            draw = ImageDraw.Draw(canvas)
            sources = []
            for index, job in enumerate(jobs):
                row, column = divmod(index, columns)
                x = column * tile_width
                y = row * (frame_height + annotation_height)
                output_dir = Path(str(job.get("output_dir", "")))
                videos = list(
                    (output_dir / f"episode_{task_id + 1}").glob("*.mp4")
                )
                frame_error = None
                if len(videos) == 1:
                    video = videos[0]
                    try:
                        frame = frame_fn(video, time_s)
                        frame = ImageOps.fit(
                            frame.convert("RGB"),
                            (tile_width, frame_height),
                        )
                    except Exception as exc:
                        frame_error = type(exc).__name__
                        frame = Image.new(
                            "RGB", (tile_width, frame_height), color=(80, 0, 0)
                        )
                else:
                    video = None
                    frame_error = f"video_count_{len(videos)}"
                    frame = Image.new(
                        "RGB", (tile_width, frame_height), color=(80, 0, 0)
                    )
                canvas.paste(frame, (x, y))
                outcome = job.get("task_outcomes", {}).get(str(task_id), "missing")
                taxonomy = job.get("failure_taxonomy", {}).get(str(task_id), "—")
                label = str(job.get("label", "unknown"))
                annotation = (
                    f"{label[:43]}\n"
                    f"task={task_id} seed={runner.EPISODE_SEEDS[task_id]} t={time_s:.1f}s "
                    f"outcome={outcome}\n{str(taxonomy)[:75]}"
                )
                draw.multiline_text(
                    (x + 4, y + frame_height + 3),
                    annotation,
                    fill=(240, 240, 240),
                    spacing=2,
                )
                if frame_error is not None:
                    failures.append(
                        f"task {task_id} time {time_s} {label}: {frame_error}"
                    )
                sources.append(
                    {
                        "label": label,
                        "video": str(video) if video is not None else None,
                        "video_sha256": (
                            _sha256_file(video) if video is not None else None
                        ),
                        "outcome": outcome,
                        "failure_taxonomy": taxonomy,
                        "frame_error": frame_error,
                    }
                )
            sheet_path = output_root / f"task_{task_id:02d}_t_{time_s:06.2f}s.png"
            if sheet_path.exists() or sheet_path.is_symlink():
                raise FileExistsError(sheet_path)
            canvas.save(sheet_path, format="PNG")
            sheet_rows.append(
                {
                    "task_id": task_id,
                    "episode_seed": runner.EPISODE_SEEDS[task_id],
                    "time_s": time_s,
                    "path": str(sheet_path),
                    "sha256": _sha256_file(sheet_path),
                    "sources": sources,
                }
            )
    payload = {
        "schema": "eds-quality-diversity-contact-sheets-v1",
        "created_at": _now(),
        "same_absolute_time_coordinates": True,
        "job_count": len(jobs),
        "sheet_count": len(sheet_rows),
        "sheets": sheet_rows,
        "failures": failures,
        "passed": not failures,
    }
    index = output_root / "contact_sheet_index.json"
    with index.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    payload["index_path"] = str(index)
    payload["index_sha256"] = _sha256_file(index)
    return payload


def _expected_attempt_cells() -> tuple[set[tuple[str, int, int]], set[tuple[str, int, int]]]:
    formal = {
        (str(profile["label"]), task, runner.EPISODE_SEEDS[task])
        for profile in runner.formal_profiles()
        for task in range(10)
    }
    preflight = {
        (label, task, runner.EPISODE_SEEDS[task])
        for label in (
            "p2_stage_on_abs_rbf_control",
            "eds_quality_diversity_uniform_primary",
            "eds_quality_diversity_sparse_primary",
        )
        for task in (0, 8)
    }
    return formal, preflight


def audit_preflight() -> dict[str, object]:
    credential = scan_credentials([EXPERIMENT_ROOT, WORKTREE_ROOT])
    jobs = []
    error_evidence: list[dict[str, object]] = []
    for job in runner.build_preflight_jobs():
        audited, _ = audit_job(job, credential_passed=bool(credential["passed"]))
        jobs.append(audited)
        output_dir = Path(str(audited["output_dir"]))
        for episode in range(1, int(job["episodes"]) + 1):
            error_path = output_dir / f"episode_{episode}" / "error.txt"
            if not error_path.is_file():
                continue
            text = error_path.read_text(encoding="utf-8", errors="replace")
            error_evidence.append(
                {
                    "label": job["label"],
                    "episode": episode - 1,
                    "path": str(error_path),
                    "sha256": _sha256_file(error_path),
                    "missing_runtime_cache": (
                        "cached_functions_dir does not exist" in text
                    ),
                    "api_authentication_error": (
                        "401" in text or "authentication" in text.lower()
                    ),
                }
            )
    failures = []
    for job in jobs:
        if not job["valid"]:
            failures.append(f"{job['label']}: invalid")
        if not job["mechanism_hard"]["passed"]:
            failures.append(f"{job['label']}: mechanism hard gate failed")
    payload = {
        "schema": "eds-quality-diversity-libero-preflight-audit-v1",
        "created_at": _now(),
        "jobs": jobs,
        "credential_audit": credential,
        "infrastructure_failure": {
            "classification": "missing_shared2_runtime_guidance_cache",
            "affected_episode_attempts": sum(
                row["missing_runtime_cache"] is True for row in error_evidence
            ),
            "policy_rollout_started": any(
                int(job["metrics_record_count"]) > 0 for job in jobs
            ),
            "api_authentication_error_detected": any(
                row["api_authentication_error"] is True for row in error_evidence
            ),
            "evidence": error_evidence,
        },
        "failures": failures,
        "passed": not failures,
    }
    PREFLIGHT_AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREFLIGHT_AUDIT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return payload


def audit_formal() -> dict[str, object]:
    credential = scan_credentials([EXPERIMENT_ROOT, WORKTREE_ROOT])
    audited_jobs: list[dict[str, Any]] = []
    metrics_by_label: dict[str, list[dict[str, Any]]] = {}
    for job in runner.build_jobs(runner.FORMAL_LEVEL, 10):
        audited, metrics = audit_job(job, credential_passed=bool(credential["passed"]))
        audited_jobs.append(audited)
        metrics_by_label[str(job["label"])] = metrics
    control = audited_jobs[0]
    control_metrics = metrics_by_label[str(control["label"])]
    candidates = []
    profile_by_label = {str(profile["label"]): profile for profile in runner.formal_profiles()}
    for candidate in audited_jobs[1:]:
        label = str(candidate["label"])
        comparison = compare_mechanism(metrics_by_label[label], control_metrics, profile_by_label[label])
        candidate["mechanism_comparison"] = comparison
        gates = evaluate_candidate_gates(candidate, control)
        candidate["gates"] = gates
        candidate["control_task_retention"] = len(gates["paired"]["retained_control_tasks"])
        candidate["paired_gained_minus_lost"] = gates["paired"]["gained_minus_lost"]
        candidate["normalized_coverage_gain"] = comparison["normalized_final_coverage_delta_median"]
        candidate["endpoint_xy_spread_retention"] = comparison["endpoint_xy_spread_ratio_median"]
        candidate["archive_best_reward_delta"] = comparison["archive_best_reward_delta_median"]
        candidates.append(candidate)
    ranking = rank_candidates(candidates)
    ranked_by_label = {str(row["label"]): row for row in ranking}
    audited_jobs = [control] + [
        ranked_by_label.get(str(job["label"]), job) for job in audited_jobs[1:]
    ]
    eligible = [row for row in ranking if row.get("gates", {}).get("all_passed") is True]
    recommended = eligible[0]["label"] if eligible else None
    formal_cells, preflight_cells = _expected_attempt_cells()
    ledger = audit_attempt_ledger(
        runner.ATTEMPT_LEDGER_PATH,
        expected_formal=formal_cells,
        expected_preflight=preflight_cells,
        cap=runner.ATTEMPT_CAP,
        recovery_limit=runner.RECOVERY_ATTEMPT_LIMIT,
    )
    storage = runner.storage_preflight()
    preflight_payload = json.loads(PREFLIGHT_AUDIT_PATH.read_text(encoding="utf-8"))
    formal_completed = int(ledger["formal_unique_cells"])
    formal_missing = 110 - formal_completed
    completion = {
        "status": "complete" if formal_missing == 0 else "incomplete",
        "preflight_passed": preflight_payload.get("passed") is True,
        "formal_dispatch_status": (
            "completed"
            if formal_missing == 0
            else "not_dispatched_preflight_gate_failed"
            if formal_completed == 0 and preflight_payload.get("passed") is not True
            else "partially_completed"
        ),
        "formal_expected_episodes": 110,
        "formal_completed_episodes": formal_completed,
        "formal_missing_episodes": formal_missing,
        "required_preflight_recovery_attempts": 6,
        "available_recovery_slots": runner.RECOVERY_ATTEMPT_LIMIT,
        "projected_total_attempts_if_full_preflight_recovery_and_formal_ran": 122,
        "attempt_cap": runner.ATTEMPT_CAP,
        "blocker": (
            None
            if formal_missing == 0
            else "formal matrix has not completed"
            if preflight_payload.get("passed") is True
            else "LIBERO mechanism preflight has not passed"
        ),
    }
    payload = {
        "schema": "eds-quality-diversity-formal-audit-v1",
        "created_at": _now(),
        "fixed_task_set_evidence_only": True,
        "jobs": audited_jobs,
        "ranking": [{"rank": row["rank"], "label": row["label"], "all_gates_passed": row["gates"]["all_passed"]} for row in ranking],
        "recommended_label": recommended,
        "decision": recommended or "no_adoption_keep_p2_stage_on_abs_rbf_control",
        "completion": completion,
        "ranking_status": (
            "complete_valid_candidates"
            if len(ranking) == 10
            else "not_evaluable_incomplete_or_invalid_candidates"
        ),
        "attempt_ledger": ledger,
        "credential_audit": credential,
        "storage_audit": storage,
        "run_manifest_sha256": _sha256_file(runner.RUN_MANIFEST_PATH),
        "offline_preflight_sha256": _sha256_file(runner.OFFLINE_PREFLIGHT_PATH),
        "libero_preflight_audit_sha256": _sha256_file(PREFLIGHT_AUDIT_PATH),
    }
    payload["qualitative_contact_sheets"] = generate_contact_sheets(payload)
    if _contains_credential(payload):
        raise RuntimeError("formal audit contains credential material")
    ANALYSIS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ANALYSIS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return payload


def freeze_decision_manifest(payload: dict[str, Any], path: Path = DECISION_PATH) -> dict[str, Any]:
    path = Path(path)
    sidecar = path.with_suffix(path.suffix + ".sha256")
    if path.exists() or path.is_symlink() or sidecar.exists() or sidecar.is_symlink():
        raise FileExistsError(path)
    if _contains_credential(payload):
        raise ValueError("decision manifest contains credential material")
    frozen = dict(payload)
    frozen.pop("canonical_manifest_checksum", None)
    frozen["canonical_manifest_checksum"] = hashlib.sha256(
        _canonical(frozen).encode()
    ).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(frozen, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    file_digest = _sha256_file(path)
    with sidecar.open("x", encoding="ascii") as handle:
        handle.write(f"{file_digest}  {path.name}\n")
        handle.flush()
        os.fsync(handle.fileno())
    path.chmod(0o444)
    sidecar.chmod(0o444)
    return frozen


def freeze_report(text: str, path: Path = REPORT_PATH) -> dict[str, str]:
    path = Path(path)
    sidecar = path.with_suffix(path.suffix + ".sha256")
    if path.exists() or path.is_symlink() or sidecar.exists() or sidecar.is_symlink():
        raise FileExistsError(path)
    if _contains_credential(text):
        raise ValueError("final report contains credential material")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(text)
        if not text.endswith("\n"):
            handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    digest = _sha256_file(path)
    with sidecar.open("x", encoding="ascii") as handle:
        handle.write(f"{digest}  {path.name}\n")
        handle.flush()
        os.fsync(handle.fileno())
    path.chmod(0o444)
    sidecar.chmod(0o444)
    return {"path": str(path), "sha256": digest, "sidecar": str(sidecar)}


def verify_decision_manifest(path: Path = DECISION_PATH) -> dict[str, Any]:
    path = Path(path)
    sidecar = path.with_suffix(path.suffix + ".sha256")
    if stat.S_IMODE(path.stat().st_mode) & 0o222 or stat.S_IMODE(sidecar.stat().st_mode) & 0o222:
        raise ValueError("decision manifest or checksum sidecar is writable")
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = payload.get("canonical_manifest_checksum")
    content = dict(payload)
    content.pop("canonical_manifest_checksum", None)
    if expected != hashlib.sha256(_canonical(content).encode()).hexdigest():
        raise ValueError("decision manifest canonical checksum mismatch")
    recorded_file_hash = sidecar.read_text(encoding="ascii").split()[0]
    if recorded_file_hash != _sha256_file(path):
        raise ValueError("decision manifest file checksum mismatch")
    if _contains_credential(payload):
        raise ValueError("decision manifest contains credential material")
    return payload


def decision_payload(analysis: dict[str, Any]) -> dict[str, Any]:
    run_manifest = json.loads(runner.RUN_MANIFEST_PATH.read_text(encoding="utf-8"))
    jobs = analysis["jobs"]
    return {
        "schema": "eds-quality-diversity-decision-manifest-v1",
        "created_at": _now(),
        "provenance": run_manifest["provenance"],
        "run_manifest": {
            "path": str(runner.RUN_MANIFEST_PATH),
            "sha256": _sha256_file(runner.RUN_MANIFEST_PATH),
        },
        "profiles": run_manifest["formal_profiles"],
        "matrix": {
            "formal_job_count": 11,
            "formal_unique_episodes": 110,
            "preflight_unique_episodes": 6,
            "formal_completed_episodes": analysis.get("completion", {}).get(
                "formal_completed_episodes"
            ),
            "formal_missing_episodes": analysis.get("completion", {}).get(
                "formal_missing_episodes"
            ),
            "ofat_complete": len(run_manifest["formal_profiles"]) == 11,
        },
        "completion": analysis.get("completion", {}),
        "attempts": analysis["attempt_ledger"],
        "task_level_results": {job["label"]: job["task_outcomes"] for job in jobs},
        "failure_taxonomy": {job["label"]: job["failure_taxonomy"] for job in jobs},
        "jobs": [
            {
                key: job.get(key)
                for key in (
                    "label", "role", "execution_status", "valid", "validity_failures", "success_count",
                    "success_rate", "wilson_95", "success_tasks", "failure_taxonomy_counts",
                    "error_evidence",
                    "execution_qpos_error_episodes", "collision_push_drop_wrong_object",
                    "nonfinite_count", "action_mask_violation_count", "qd_fallback_count",
                    "mechanism_hard", "mechanism_comparison", "gates", "metric_summary",
                    "config_fingerprint", "code_state_sha256", "checksums",
                )
            }
            for job in jobs
        ],
        "ranking": analysis["ranking"],
        "ranking_status": analysis.get("ranking_status"),
        "recommended_for_adoption": analysis["recommended_label"] is not None,
        "recommended_label": analysis["recommended_label"],
        "decision": analysis["decision"],
        "credential_audit": analysis["credential_audit"],
        "storage_audit": analysis["storage_audit"],
        "analysis_artifacts": {
            "formal_audit": {"path": str(ANALYSIS_PATH), "sha256": _sha256_file(ANALYSIS_PATH)},
            "offline_preflight": {"path": str(runner.OFFLINE_PREFLIGHT_PATH), "sha256": _sha256_file(runner.OFFLINE_PREFLIGHT_PATH)},
            "libero_preflight": {"path": str(PREFLIGHT_AUDIT_PATH), "sha256": _sha256_file(PREFLIGHT_AUDIT_PATH)},
            **(
                {
                    "final_report": {
                        "path": str(REPORT_PATH),
                        "sha256": _sha256_file(REPORT_PATH),
                    }
                }
                if REPORT_PATH.is_file()
                else {}
            ),
        },
        "qualitative_contact_sheets": analysis.get(
            "qualitative_contact_sheets", {}
        ),
    }


def _fmt(value: object, digits: int = 3) -> str:
    parsed = _finite_number(value)
    return "—" if parsed is None else f"{parsed:.{digits}f}"


def _pass(value: object) -> str:
    return "PASS" if value is True else "FAIL"


def render_report(
    analysis: dict[str, Any], *, provenance: dict[str, object]
) -> str:
    """Render the frozen, complete-table report without making repository writes."""
    jobs = list(analysis.get("jobs", []))
    completion = analysis.get("completion", {})
    ledger = analysis.get("attempt_ledger", {})
    formal_completed = completion.get("formal_completed_episodes", 0)
    preflight_passed = completion.get("preflight_passed") is True
    lines = [
        "# EDS Quality-Diversity / LIBERO Object-Swap OOD 最终报告",
        "",
        "> 本报告只描述预注册的 10 个固定 Object-Swap tasks 上的 paired engineering evidence；不宣称统计显著性、总体泛化或 QD 理论普遍成立。",
        "",
        "## 执行与 provenance",
        "",
        f"- Base commit：`{provenance.get('base_commit', '—')}`；QD code commit：`{provenance.get('code_commit', '—')}`。",
        f"- Decision：`{analysis.get('decision', '—')}`。",
        f"- Completion：`{completion.get('status', '—')}`；mechanism preflight：`{_pass(preflight_passed)}`；formal：`{formal_completed}/110`（`{completion.get('formal_dispatch_status', '—')}`）。",
        f"- Stop reason：{completion.get('blocker', '—')}。",
        f"- Attempts：实际 episode attempts `{ledger.get('actual_episode_attempt_count', ledger.get('attempt_count', '—'))}/{runner.ATTEMPT_CAP}`；recovery `{ledger.get('recovery_attempts', '—')}`；pre-episode aborted `{ledger.get('aborted_pre_episode_count', '—')}`；ledger `{_pass(ledger.get('passed'))}`。",
        f"- Storage：`{analysis.get('storage_audit', {}).get('outputs_target', '—')}`；credential scan `{_pass(analysis.get('credential_audit', {}).get('passed'))}`。",
        "",
        "## 11-job 完整结果",
        "",
        "| Job | Execution | Valid | Success | SR | Wilson 95% | qpos | collision composite |",
        "| --- | --- | --- | ---: | ---: | --- | ---: | ---: |",
    ]
    for job in jobs:
        ci = job.get("wilson_95") or [None, None]
        dispatched = job.get("execution_status") != "not_dispatched"
        lines.append(
            f"| `{job.get('label')}` | {job.get('execution_status', '—')} | {_pass(job.get('valid'))} | {job.get('success_count', '—') if dispatched else '—'}/10 | {_fmt(job.get('success_rate')) if dispatched else '—'} | [{_fmt(ci[0])}, {_fmt(ci[1])}] | {job.get('execution_qpos_error_episodes', '—') if dispatched else '—'} | {job.get('collision_push_drop_wrong_object', '—') if dispatched else '—'} |"
        )
    lines.extend(
        [
            "",
            "## Task-level paired outcome",
            "",
            "| Task | " + " | ".join(f"`{job.get('label')}`" for job in jobs) + " |",
            "| ---: | " + " | ".join("---" for _ in jobs) + " |",
        ]
    )
    for task in range(10):
        lines.append(
            f"| {task} | "
            + " | ".join(str(job.get("task_outcomes", {}).get(str(task), "—")) for job in jobs)
            + " |"
        )
    lines.extend(
        [
            "",
            "## 机制与三类 gates",
            "",
            f"LIBERO mechanism preflight：`{_pass(preflight_passed)}`；formal：`{formal_completed}/110`。下表严格使用冻结阈值；validity、task、mechanism hard/claim 与 safety 任一失败即不得 adoption。",
            "",
            "| Candidate | Task | Mechanism hard | Mechanism claim | Safety | All | Δcoverage median | spread ratio | Δbest reward | replacement-active | overflow P95 |",
            "| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for job in jobs[1:]:
        gates = job.get("gates", {})
        mechanism = job.get("mechanism_comparison", {})
        lines.append(
            f"| `{job.get('label')}` | {_pass(gates.get('task', {}).get('passed'))} | {_pass(gates.get('mechanism_hard', {}).get('passed'))} | {_pass(gates.get('mechanism_claim', {}).get('passed'))} | {_pass(gates.get('safety', {}).get('passed'))} | {_pass(gates.get('all_passed'))} | {_fmt(mechanism.get('normalized_final_coverage_delta_median'))} | {_fmt(mechanism.get('endpoint_xy_spread_ratio_median'))} | {_fmt(mechanism.get('archive_best_reward_delta_median'))} | {_fmt(mechanism.get('replacement_active_chunk_ratio'))} | {_fmt(mechanism.get('descriptor_overflow_ratio_p95'))} |"
        )
    lines.extend(
        [
            "",
            "### Paired gained/lost/retained tasks",
            "",
            "| Candidate | Gained | Lost | Retained control | Δ(gained-lost) |",
            "| --- | --- | --- | --- | ---: |",
        ]
    )
    for job in jobs[1:]:
        paired = job.get("gates", {}).get("paired", {})
        lines.append(
            f"| `{job.get('label')}` | {paired.get('gained_tasks', [])} | {paired.get('lost_tasks', [])} | {paired.get('retained_control_tasks', [])} | {paired.get('gained_minus_lost', '—')} |"
        )
    primary = next(
        (job for job in jobs if job.get("label") == "eds_quality_diversity_uniform_primary"),
        jobs[1] if len(jobs) > 1 else {},
    )
    lines.extend(
        [
            "",
            "## 单因素主效应",
            "",
            "以下均相对 uniform primary；sparse 行只归因 parent sampler，其余为预注册 OFAT。",
            "",
            "| Job | Factor | Δsuccess | Δcoverage gain | Δspread retention | Δbest reward |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    factors = {
        "eds_quality_diversity_sparse_primary": "parent sampling",
        "eds_quality_diversity_uniform_grid3": "grid 3x3",
        "eds_quality_diversity_uniform_grid5": "grid 5x5",
        "eds_quality_diversity_uniform_q00100": "quantiles .00/.100",
        "eds_quality_diversity_uniform_q1090": "quantiles .10/.90",
        "eds_quality_diversity_uniform_expand00": "expand .00",
        "eds_quality_diversity_uniform_expand20": "expand .20",
        "eds_quality_diversity_uniform_span04": "min span .04 m",
        "eds_quality_diversity_uniform_span12": "min span .12 m",
    }
    primary_mechanism = primary.get("mechanism_comparison", {})
    for job in jobs[1:]:
        if job.get("label") == primary.get("label"):
            continue
        mechanism = job.get("mechanism_comparison", {})
        if job.get("execution_status") == "not_dispatched":
            lines.append(
                f"| `{job.get('label')}` | {factors.get(str(job.get('label')), 'registered candidate')} | — | — | — | — |"
            )
            continue
        lines.append(
            f"| `{job.get('label')}` | {factors.get(str(job.get('label')), 'registered candidate')} | {_fmt((_finite_number(job.get('success_count')) or 0) - (_finite_number(primary.get('success_count')) or 0), 0)} | {_fmt((_finite_number(mechanism.get('normalized_final_coverage_delta_median')) or 0) - (_finite_number(primary_mechanism.get('normalized_final_coverage_delta_median')) or 0))} | {_fmt((_finite_number(mechanism.get('endpoint_xy_spread_ratio_median')) or 0) - (_finite_number(primary_mechanism.get('endpoint_xy_spread_ratio_median')) or 0))} | {_fmt((_finite_number(mechanism.get('archive_best_reward_delta_median')) or 0) - (_finite_number(primary_mechanism.get('archive_best_reward_delta_median')) or 0))} |"
        )
    lines.extend(
        [
            "",
            "## Archive、几何与 parent allocation",
            "",
            "| Job | Active chunks | Exact replay | Coverage median | Turnover median | Overflow P95 | Endpoint spread m | EEF direction diversity | Global-best reward median |",
            "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for job in jobs:
        metrics = job.get("metric_summary", {})
        hard = job.get("mechanism_hard", {})
        exact_replay = (
            _pass(hard.get("exact_parent_allocation_replay_passed"))
            if job.get("role") != "control"
            else "—"
        )
        lines.append(
            f"| `{job.get('label')}` | {hard.get('active_chunk_count', '—')} | {exact_replay} | {_fmt(metrics.get('coverage_median'))} | {_fmt(metrics.get('turnover_median'))} | {_fmt(metrics.get('overflow_p95'))} | {_fmt(metrics.get('endpoint_xy_spread_median'))} | {_fmt(metrics.get('eef_direction_diversity_median'))} | {_fmt(metrics.get('global_best_reward_median'))} |"
        )
    lines.extend(
        [
            "",
            "### Selected cells 与 per-cell final elite reward median",
            "",
            "以下 cell reward 只在同一 job/chunk 定义下作为 archive 证据，不解释为跨 task 可比的经典 QD-score。",
            "",
            "| Job | Selected-cell counts | Per-cell elite reward median |",
            "| --- | --- | --- |",
        ]
    )
    for job in jobs[1:]:
        metrics = job.get("metric_summary", {})
        selected = ", ".join(
            f"{cell}:{count}"
            for cell, count in metrics.get("selected_cell_counts", {}).items()
        ) or "—"
        rewards = ", ".join(
            f"{cell}:{_fmt(value)}"
            for cell, value in metrics.get("per_cell_elite_reward_median", {}).items()
        ) or "—"
        lines.append(f"| `{job.get('label')}` | {selected} | {rewards} |")
    lines.extend(
        [
            "",
            "## Failure taxonomy",
            "",
            "| Job | Categories |",
            "| --- | --- |",
        ]
    )
    for job in jobs:
        categories = ", ".join(
            f"{key}: {value}"
            for key, value in sorted(job.get("failure_taxonomy_counts", {}).items())
        ) or "—"
        lines.append(f"| `{job.get('label')}` | {categories} |")
    lines.extend(
        [
            "",
            "### Failed / invalid / execution-error evidence",
            "",
            "| Job | Valid | Error episodes | Exception types | Validity reason |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for job in jobs:
        errors = job.get("error_evidence", [])
        episodes = [row.get("episode") for row in errors]
        exception_types = sorted(
            {str(row.get("exception_type", "execution_error")) for row in errors}
        )
        failures = "; ".join(
            str(item) for item in job.get("validity_failures", [])
        )
        failures = failures.replace("|", "\\|")[:1000] or "—"
        lines.append(
            f"| `{job.get('label')}` | {_pass(job.get('valid'))} | {episodes or '—'} | {exception_types or '—'} | {failures} |"
        )
    lines.extend(
        [
            "",
            "## Latency 与定性证据",
            "",
            "| Job | Selection P95 s | QD update P95 s | Parent allocation P95 s | EDS loop P95 s | Stage P95 s |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for job in jobs:
        metrics = job.get("metric_summary", {})
        lines.append(
            f"| `{job.get('label')}` | {_fmt(metrics.get('selection_latency_p95_s'))} | {_fmt(metrics.get('qd_archive_update_latency_p95_s'))} | {_fmt(metrics.get('qd_parent_allocation_latency_p95_s'))} | {_fmt(metrics.get('eds_loop_latency_p95_s'))} | {_fmt(metrics.get('stage_query_latency_p95_s'))} |"
        )
    lines.extend(
        [
            "",
            "### 轨迹几何",
            "",
            "| Job | Trajectory length median m | Max-step median m | Chunk-boundary jump P95 |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for job in jobs:
        metrics = job.get("metric_summary", {})
        lines.append(
            f"| `{job.get('label')}` | {_fmt(metrics.get('trajectory_length_median'))} | {_fmt(metrics.get('max_step_median'))} | {_fmt(metrics.get('chunk_boundary_jump_p95'))} |"
        )
    contact = analysis.get("qualitative_contact_sheets", {})
    lines.extend(
        [
            "",
            f"- Raw qualitative heatmaps/trajectories：各 job 的 `eds_eval/qualitative/episode_*/chunk_*/`。",
            f"- 同时间坐标 contact sheets：`{CONTACT_SHEET_ROOT}`；生成 `{contact.get('sheet_count', '—')}` 张，审计 `{_pass(contact.get('passed'))}`。失败项来自 invalid grid5 缺失/损坏视频，保留红色占位而未伪造画面。",
            "- 自动 failure taxonomy 对无明确 telemetry 的失败保守标为 `timeout without completion`；视觉复核注释单独保留，不把未观察到的因果机制写成事实。",
            "",
            "## Ranking 与结论",
            "",
        ]
    )
    for row in analysis.get("ranking", []):
        lines.append(
            f"{row.get('rank')}. `{row.get('label')}` — all gates `{row.get('all_gates_passed')}`"
        )
    lines.extend(
        [
            "",
            f"最终 decision：`{analysis.get('decision', '—')}`。Gate 失败不构成追加实验或改变冻结参数的授权。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=("audit-preflight", "audit-formal", "freeze-decision", "verify-decision"),
    )
    args = parser.parse_args()
    if args.command == "audit-preflight":
        payload = audit_preflight()
        print(json.dumps({"passed": payload["passed"], "path": str(PREFLIGHT_AUDIT_PATH)}))
        return 0 if payload["passed"] else 1
    if args.command == "audit-formal":
        payload = audit_formal()
        print(json.dumps({"decision": payload["decision"], "path": str(ANALYSIS_PATH)}))
        return 0
    if args.command == "freeze-decision":
        analysis = json.loads(ANALYSIS_PATH.read_text(encoding="utf-8"))
        run_manifest = json.loads(
            runner.RUN_MANIFEST_PATH.read_text(encoding="utf-8")
        )
        report = freeze_report(
            render_report(analysis, provenance=run_manifest["provenance"])
        )
        frozen = freeze_decision_manifest(decision_payload(analysis))
        print(
            json.dumps(
                {
                    "decision": frozen["decision"],
                    "path": str(DECISION_PATH),
                    "report": report,
                }
            )
        )
        return 0
    verify_decision_manifest()
    print(json.dumps({"verified": True, "path": str(DECISION_PATH)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
