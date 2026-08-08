#!/usr/bin/env python3
"""Audit and freeze the approved 18-job EDS-QD search-budget sweep."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import stat
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

import torch


SCRIPT_DIR = Path(__file__).resolve().parent
WORKTREE_ROOT = Path(__file__).resolve().parents[1]
for import_root in (SCRIPT_DIR, WORKTREE_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import eds_qd_search_budget_sweep_runner as runner
import eds_quality_diversity_audit as prior_audit
from core.qd_ed import QDArchive, allocate_parent_slots, cell_ids


ANALYSIS_PATH = runner.EXPERIMENT_ROOT / "analysis/formal_audit.json"
REPORT_PATH = runner.EXPERIMENT_ROOT / "analysis/final_report.md"
DECISION_PATH = runner.EXPERIMENT_ROOT / "manifests/decision_manifest.json"
HISTORICAL_AUDIT_PATH = Path(
    "/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/"
    "analysis/qd_ed_formal_audit.json"
)
HISTORICAL_LABELS = {
    "uniform_expand20": "eds_quality_diversity_uniform_expand20",
    "sparse_primary": "eds_quality_diversity_sparse_primary",
}
EQUAL_BUDGET_PAIRS = (
    ((32, 25), (48, 15)),
    ((48, 20), (64, 15)),
    ((48, 25), (64, 20)),
)
RECOVERY_TIMEOUT_PROVENANCE_PATH = (
    runner.OUTPUT_TARGET
    / "stale/formal/recovery_tool_timeout_20260808T215900Z"
    / "eds_qd_uniform_expand20_p48_k20/interruption_provenance.json"
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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _finite(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    parsed = float(value)
    return parsed if math.isfinite(parsed) else None


def _median(values: Iterable[object]) -> float | None:
    parsed = [item for value in values if (item := _finite(value)) is not None]
    return float(median(parsed)) if parsed else None


def _ratio(value: object, reference: object) -> float | None:
    numerator = _finite(value)
    denominator = _finite(reference)
    if numerator is None or denominator is None or denominator == 0.0:
        return None
    return numerator / denominator


def execution_exception_audit(
    path: Path = RECOVERY_TIMEOUT_PROVENANCE_PATH,
) -> dict[str, object]:
    """Audit the documented recovery timeout without hiding physical attempts."""
    path = Path(path)
    if not path.is_file():
        return {
            "present": False,
            "passed": True,
            "path": str(path),
            "physical_episode_attempt_count": runner.ATTEMPT_CAP,
            "soft_cap_exception_attempts": 0,
            "hard_cap_passed": True,
            "user_soft_cap_override_applied": False,
            "failures": [],
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    failures: list[str] = []
    required = {
        "schema": "eds-qd-recovery-tool-timeout-v1",
        "affected_label": "eds_qd_uniform_expand20_p48_k20",
        "continuation_completed": True,
        "algorithm_or_config_change": False,
        "ledger_reserved_attempts": runner.ATTEMPT_CAP,
        "soft_cap_exception_attempts": 1,
    }
    for key, expected in required.items():
        if payload.get(key) != expected:
            failures.append(f"{key} != {expected!r}")
    physical = payload.get("actual_attempts_after_continuation")
    if physical != runner.ATTEMPT_CAP + 1:
        failures.append(
            "physical attempt count is not exactly one above the frozen cap"
        )
    if payload.get("canonical_merged_result") != "1/10":
        failures.append("canonical merged result is not 1/10")
    return {
        "present": True,
        "passed": not failures,
        "path": str(path),
        "sha256": _sha256_file(path),
        "affected_label": payload.get("affected_label"),
        "interruption": payload.get("interruption"),
        "physical_episode_attempt_count": physical,
        "soft_cap_exception_attempts": payload.get(
            "soft_cap_exception_attempts"
        ),
        "hard_cap_passed": isinstance(physical, int)
        and physical <= runner.ATTEMPT_CAP,
        "user_soft_cap_override_applied": True,
        "canonical_merged_result": payload.get("canonical_merged_result"),
        "failures": failures,
    }


def qd_mechanism_hard_gate(
    metrics: list[dict[str, Any]], profile: dict[str, object]
) -> dict[str, object]:
    """Validate accounting against each treatment's registered M and K."""
    population_size = int(profile["population_size"])
    cem_iters = int(profile["cem_iters"])
    expected_evaluations = runner.expected_evaluations(population_size, cem_iters)
    expected_score_calls = cem_iters + 1
    failures: list[str] = []
    for index, record in enumerate(metrics):
        identity = f"{record.get('episode')}/{record.get('global_step', index)}"
        if record.get("qd_archive_enabled") is not True:
            failures.append(f"{identity}: QD archive not enabled")
            continue
        if record.get("qd_evaluation_count") != expected_evaluations:
            failures.append(
                f"{identity}: complete chunk evaluation count != {expected_evaluations}"
            )
        if record.get("score_call_count") != expected_score_calls:
            failures.append(
                f"{identity}: reward call budget != {expected_score_calls}"
            )
        for key, label in (
            ("qd_accounting_violation_count", "archive accounting violation"),
            ("qd_elite_monotonicity_violation_count", "elite monotonicity violation"),
            ("qd_final_selection_mismatch_count", "final selection mismatch"),
        ):
            if record.get(key) != 0:
                failures.append(f"{identity}: {label}")
        if record.get("qd_fallback_used") is not False:
            failures.append(f"{identity}: QD fallback")
        initial = record.get("qd_initial_accounting")
        if not isinstance(initial, dict) or sum(
            int(initial.get(key, -1000000))
            for key in ("insertions", "replacements", "rejections")
        ) != population_size:
            failures.append(
                f"{identity}: initial accounting != {population_size}"
            )
        insertions = record.get("qd_archive_insertions_by_iter")
        replacements = record.get("qd_archive_replacements_by_iter")
        rejections = record.get("qd_archive_rejections_by_iter")
        if not all(
            isinstance(values, list) and len(values) == cem_iters
            for values in (insertions, replacements, rejections)
        ):
            failures.append(f"{identity}: {cem_iters} archive iterations required")
        else:
            for iteration, triple in enumerate(
                zip(insertions, replacements, rejections)
            ):
                if sum(int(value) for value in triple) != population_size:
                    failures.append(
                        f"{identity}: iter {iteration} accounting != {population_size}"
                    )
        slots = record.get("qd_parent_slots_by_cell_by_iter")
        weights = record.get("qd_parent_weights_by_cell_by_iter")
        if not isinstance(slots, list) or len(slots) != cem_iters:
            failures.append(f"{identity}: {cem_iters} parent allocations required")
            continue
        for iteration, allocation in enumerate(slots):
            if not isinstance(allocation, dict) or not allocation:
                failures.append(f"{identity}: iter {iteration} allocation missing")
                continue
            if sum(int(value) for value in allocation.values()) != population_size:
                failures.append(
                    f"{identity}: iter {iteration} slot sum != {population_size}"
                )
                continue
            counts = [int(value) for value in allocation.values()]
            if profile["qd_parent_sampling"] == "uniform_cells":
                if max(counts) - min(counts) > 1:
                    failures.append(
                        f"{identity}: iter {iteration} uniform imbalance"
                    )
                continue
            if not isinstance(weights, list) or len(weights) != cem_iters:
                failures.append(f"{identity}: sparse weights missing")
                break
            iteration_weights = weights[iteration]
            if not isinstance(iteration_weights, dict) or set(
                iteration_weights
            ) != set(allocation):
                failures.append(
                    f"{identity}: iter {iteration} sparse cell mismatch"
                )
                continue
            raw = {cell: float(iteration_weights[cell]) for cell in allocation}
            total = sum(raw.values())
            if total <= 0.0:
                failures.append(f"{identity}: iter {iteration} sparse weights invalid")
                continue
            exact = {
                cell: population_size * raw[cell] / total for cell in raw
            }
            floors = {cell: math.floor(exact[cell]) for cell in raw}
            remainder = population_size - sum(floors.values())
            deltas = {
                cell: int(allocation[cell]) - floors[cell] for cell in raw
            }
            if sum(deltas.values()) != remainder or any(
                value not in {0, 1} for value in deltas.values()
            ):
                failures.append(
                    f"{identity}: iter {iteration} largest-remainder mismatch"
                )
            selected = [
                exact[cell] - floors[cell] for cell, value in deltas.items() if value
            ]
            rejected = [
                exact[cell] - floors[cell]
                for cell, value in deltas.items()
                if not value
            ]
            if selected and rejected and min(selected) + 1e-9 < max(rejected):
                failures.append(
                    f"{identity}: iter {iteration} remainder priority mismatch"
                )
    unique = list(dict.fromkeys(failures))
    return {
        "passed": bool(metrics) and not unique,
        "active_chunk_count": len(metrics),
        "population_size": population_size,
        "cem_iters": cem_iters,
        "expected_evaluations_per_complete_chunk": expected_evaluations,
        "expected_score_calls_per_complete_chunk": expected_score_calls,
        "additional_reward_model_vlm_calls_vs_historical": 0
        if metrics and not any("reward call" in item for item in unique)
        else None,
        "failures": unique,
    }


def validate_parent_allocation_replay(
    record: dict[str, Any], profile: dict[str, object]
) -> dict[str, object]:
    """Recompute bounds, archive visits, and every deterministic allocation."""
    population_size = int(profile["population_size"])
    cem_iters = int(profile["cem_iters"])
    failures: list[str] = []
    stream = record.get("shadow_qd_candidate_stream")
    if not isinstance(stream, list) or len(stream) != cem_iters + 1:
        return {
            "passed": False,
            "failures": [
                f"candidate stream must contain initial + {cem_iters} iterations"
            ],
        }
    checksum = hashlib.sha256(_canonical(stream).encode()).hexdigest()
    if checksum != record.get("shadow_qd_observer_checksum"):
        failures.append("candidate stream checksum mismatch")
    if [item.get("iter_idx") for item in stream if isinstance(item, dict)] != list(
        range(-1, cem_iters)
    ):
        failures.append("candidate stream iteration identity mismatch")
        return {"passed": False, "failures": failures}
    try:
        initial_descriptors = torch.tensor(
            stream[0]["descriptors_xy_m"], dtype=torch.float32
        )
        bounds = prior_audit._profile_bounds(profile, initial_descriptors)
    except (KeyError, TypeError, ValueError, FloatingPointError) as exc:
        return {
            "passed": False,
            "failures": [f"initial bounds replay failed: {type(exc).__name__}"],
        }
    try:
        observed_bounds = torch.tensor(
            record.get("qd_bounds_xy_m"), dtype=torch.float32
        )
    except (TypeError, ValueError):
        observed_bounds = torch.empty(0)
    if observed_bounds.shape != (2, 2) or not torch.equal(
        observed_bounds, torch.stack((bounds.lo, bounds.hi))
    ):
        failures.append("fixed bounds values do not match initial-population replay")
    if record.get("qd_bounds_source_initial_checksum") != bounds.checksum:
        failures.append("fixed bounds checksum mismatch")
    archive = QDArchive(grid_shape=profile["qd_grid_shape"])

    def update(group: dict[str, Any], source_iter: int) -> None:
        descriptors = torch.tensor(group["descriptors_xy_m"], dtype=torch.float32)
        rewards = torch.tensor(group["rewards"], dtype=torch.float32)
        if descriptors.shape != (population_size, 2) or rewards.shape != (
            population_size,
        ):
            raise ValueError("candidate group shape mismatch")
        mapped, _ = cell_ids(descriptors, bounds, profile["qd_grid_shape"])
        actions = (
            torch.arange(population_size * 2, dtype=torch.float32).reshape(
                population_size, 2
            )
            + 10000.0 * (source_iter + 1)
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
        update(stream[0], -1)
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        return {
            "passed": False,
            "failures": [f"initial archive replay failed: {type(exc).__name__}"],
        }
    observed_slots = record.get("qd_parent_slots_by_cell_by_iter")
    observed_weights = record.get("qd_parent_weights_by_cell_by_iter")
    if not isinstance(observed_slots, list) or len(observed_slots) != cem_iters:
        failures.append(f"{cem_iters} observed parent slot allocations required")
        return {"passed": False, "failures": failures}
    if not isinstance(observed_weights, list) or len(observed_weights) != cem_iters:
        failures.append(f"{cem_iters} observed parent weight allocations required")
        return {"passed": False, "failures": failures}
    replay_rows = []
    for iteration in range(cem_iters):
        allocation = allocate_parent_slots(
            archive,
            population_size=population_size,
            sampling=str(profile["qd_parent_sampling"]),
            sparse_exponent=float(profile.get("qd_sparse_exponent", 1.0)),
            run_seed=int(profile.get("seed", 0)),
            episode=int(record.get("episode", 0)),
            global_step=int(record.get("global_step", 0)),
            iter_idx=iteration,
        )
        expected_slots = {
            str(cell): int(value) for cell, value in allocation.slot_counts.items()
        }
        expected_weights = {
            str(cell): float(value) for cell, value in allocation.weights.items()
        }
        if observed_slots[iteration] != expected_slots:
            failures.append(f"iter {iteration} exact parent slots mismatch")
        actual_weights = observed_weights[iteration]
        if (
            not isinstance(actual_weights, dict)
            or set(actual_weights) != set(expected_weights)
            or any(
                not math.isclose(
                    float(actual_weights[cell]),
                    expected_weights[cell],
                    rel_tol=0.0,
                    abs_tol=1e-12,
                )
                for cell in expected_weights
            )
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
            update(stream[iteration + 1], iteration)
        except (KeyError, TypeError, ValueError, RuntimeError) as exc:
            failures.append(
                f"iter {iteration} archive replay failed: {type(exc).__name__}"
            )
            break
    return {
        "passed": not failures,
        "stream_checksum": checksum,
        "bounds_checksum": bounds.checksum,
        "replay": replay_rows,
        "failures": list(dict.fromkeys(failures)),
    }


def _configure_prior_audit() -> None:
    prior_audit.runner = runner
    prior_audit.OUTPUT_TARGET = runner.OUTPUT_TARGET
    prior_audit.EXPERIMENT_ROOT = runner.EXPERIMENT_ROOT
    prior_audit.WORKTREE_ROOT = WORKTREE_ROOT
    prior_audit.qd_mechanism_hard_gate = qd_mechanism_hard_gate
    prior_audit.validate_parent_allocation_replay = validate_parent_allocation_replay


def expected_attempt_cells() -> tuple[
    set[tuple[str, int, int]], set[tuple[str, int, int]]
]:
    formal = {
        (str(profile["label"]), task, runner.EPISODE_SEEDS[task])
        for profile in runner.formal_profiles()
        for task in range(10)
    }
    return formal, set()


def _historical_references() -> tuple[dict[str, dict[str, Any]], dict[str, object]]:
    payload = json.loads(HISTORICAL_AUDIT_PATH.read_text(encoding="utf-8"))
    jobs = {str(job["label"]): job for job in payload["jobs"]}
    references = {
        family: jobs[label] for family, label in HISTORICAL_LABELS.items()
    }
    return references, {
        "path": str(HISTORICAL_AUDIT_PATH),
        "sha256": _sha256_file(HISTORICAL_AUDIT_PATH),
        "cross_run_comparison_only": True,
        "not_a_contemporaneous_control": True,
    }


def _mechanism_summary(metrics: list[dict[str, Any]]) -> dict[str, object]:
    active = sum(
        any(int(value) > 0 for value in record.get("qd_archive_replacements_by_iter", []))
        for record in metrics
    )
    replacements = sum(
        sum(int(value) for value in record.get("qd_archive_replacements_by_iter", []))
        for record in metrics
    )
    evaluated = sum(int(record.get("qd_evaluation_count", 0)) for record in metrics)
    return {
        "replacement_active_chunk_ratio": active / len(metrics) if metrics else None,
        "replacement_count": replacements,
        "candidate_evaluation_count": evaluated,
        "complete_chunk_count": len(metrics),
    }


def _historical_comparison(
    job: dict[str, Any], historical: dict[str, Any]
) -> dict[str, object]:
    current_metrics = job["metric_summary"]
    prior_metrics = historical["metric_summary"]
    current_tasks = set(job.get("success_tasks", []))
    prior_tasks = set(historical.get("success_tasks", []))
    historical_mechanism = historical.get("mechanism_comparison", {})
    gained = sorted(current_tasks - prior_tasks)
    lost = sorted(prior_tasks - current_tasks)
    return {
        "historical_label": historical["label"],
        "historical_population_size": 16,
        "historical_cem_iters": 10,
        "historical_success_count": historical.get("success_count"),
        "gained_tasks": gained,
        "lost_tasks": lost,
        "retained_tasks": sorted(current_tasks & prior_tasks),
        "paired_gained_minus_lost": len(gained) - len(lost),
        "coverage_delta": (
            (_finite(current_metrics.get("coverage_median")) or 0.0)
            - (_finite(prior_metrics.get("coverage_median")) or 0.0)
        ),
        "spread_ratio": _ratio(
            current_metrics.get("endpoint_xy_spread_median"),
            prior_metrics.get("endpoint_xy_spread_median"),
        ),
        "replacement_active_ratio_delta": (
            (_finite(job.get("replacement_active_chunk_ratio")) or 0.0)
            - (
                _finite(
                    historical_mechanism.get("replacement_active_chunk_ratio")
                )
                or 0.0
            )
        ),
        "turnover_delta": (
            (_finite(current_metrics.get("turnover_median")) or 0.0)
            - (_finite(prior_metrics.get("turnover_median")) or 0.0)
        ),
        "overflow_p95_delta": (
            (_finite(current_metrics.get("overflow_p95")) or 0.0)
            - (_finite(prior_metrics.get("overflow_p95")) or 0.0)
        ),
        "archive_best_reward_delta": (
            (_finite(current_metrics.get("global_best_reward_median")) or 0.0)
            - (_finite(prior_metrics.get("global_best_reward_median")) or 0.0)
        ),
        "selection_latency_ratio": _ratio(
            current_metrics.get("selection_latency_p95_s"),
            prior_metrics.get("selection_latency_p95_s"),
        ),
        "cross_run_background_only": True,
    }


def _job_wall_time(output_dir: Path) -> dict[str, float | None]:
    start = output_dir / "job_manifest.json"
    end = output_dir / "results.txt"
    if not start.is_file() or not end.is_file():
        return {"job_wall_time_s": None, "episode_wall_time_mean_s": None}
    duration = max(0.0, end.stat().st_mtime - start.stat().st_mtime)
    return {"job_wall_time_s": duration, "episode_wall_time_mean_s": duration / 10.0}


def _gates(job: dict[str, Any], historical: dict[str, Any]) -> dict[str, object]:
    task = job.get("success_count", 0) >= 5
    safety_checks = {
        "qpos_execution_error_episodes_eq_0": job.get(
            "execution_qpos_error_episodes"
        )
        == 0,
        "nonfinite_eq_0": job.get("nonfinite_count") == 0,
        "action_mask_violation_eq_0": job.get("action_mask_violation_count") == 0,
        "algorithm_fallback_eq_0": job.get("qd_fallback_count") == 0,
        "collision_composite_le_historical_family": job.get(
            "collision_push_drop_wrong_object", math.inf
        )
        <= historical.get("collision_push_drop_wrong_object", -math.inf),
    }
    return {
        "validity": {
            "passed": job.get("valid") is True,
            "failures": job.get("validity_failures", []),
        },
        "task": {
            "passed": task,
            "threshold": "success_count >= 5/10",
            "failures": [] if task else ["success_count < 5"],
        },
        "mechanism_hard": job.get("mechanism_hard", {"passed": False}),
        "safety": {
            "passed": all(safety_checks.values()),
            "checks": safety_checks,
            "failures": [key for key, passed in safety_checks.items() if not passed],
            "historical_comparison_only": True,
        },
    }


def rank_candidates(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def descending(value: object) -> float:
        parsed = _finite(value)
        return -parsed if parsed is not None else math.inf

    def ascending(value: object) -> float:
        parsed = _finite(value)
        return parsed if parsed is not None else math.inf

    eligible = [
        row
        for row in jobs
        if row.get("valid") is True
        and row.get("gates", {}).get("task", {}).get("passed") is True
        and row.get("gates", {}).get("safety", {}).get("passed") is True
    ]
    ordered = sorted(
        eligible,
        key=lambda row: (
            descending(row.get("success_count")),
            descending(row.get("historical_paired_gained_minus_lost")),
            ascending(row.get("candidates_per_success")),
            ascending(row.get("selection_latency_p95_s")),
            descending(row.get("replacement_active_chunk_ratio")),
            descending(row.get("archive_best_reward_delta_vs_historical")),
            str(row.get("label", "")),
        ),
    )
    return [{**row, "rank": index} for index, row in enumerate(ordered, 1)]


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, object]:
    successes = [float(row["success_count"]) for row in rows]
    rewards = [
        row.get("metric_summary", {}).get("global_best_reward_median") for row in rows
    ]
    replacements = [row.get("replacement_active_chunk_ratio") for row in rows]
    latencies = [row.get("selection_latency_p95_s") for row in rows]
    return {
        "job_count": len(rows),
        "mean_success_count": mean(successes) if successes else None,
        "median_archive_best_reward": _median(rewards),
        "median_replacement_active_ratio": _median(replacements),
        "median_selection_latency_p95_s": _median(latencies),
    }


def parameter_effects(jobs: list[dict[str, Any]]) -> dict[str, object]:
    expected = {
        (family, population_size, cem_iters)
        for family in runner.FAMILIES
        for population_size in runner.POPULATION_SIZES
        for cem_iters in runner.CEM_ITERS
    }
    observed = {
        (str(job["family"]), int(job["population_size"]), int(job["cem_iters"]))
        for job in jobs
        if job.get("valid") is True
    }
    complete = observed == expected
    families: dict[str, object] = {}
    for family in runner.FAMILIES:
        family_rows = [row for row in jobs if row.get("family") == family]
        families[family] = {
            "by_population_size": {
                str(value): _aggregate(
                    [
                        row
                        for row in family_rows
                        if row.get("population_size") == value
                    ]
                )
                for value in runner.POPULATION_SIZES
            },
            "by_cem_iters": {
                str(value): _aggregate(
                    [row for row in family_rows if row.get("cem_iters") == value]
                )
                for value in runner.CEM_ITERS
            },
            "response_surface": {
                f"p{row['population_size']}_k{row['cem_iters']}": {
                    "valid": row.get("valid"),
                    "success_count": row.get("success_count"),
                    "candidate_evaluations_per_chunk": row.get(
                        "candidate_evaluations_per_chunk"
                    ),
                    "replacement_active_chunk_ratio": row.get(
                        "replacement_active_chunk_ratio"
                    ),
                    "archive_best_reward": row.get("metric_summary", {}).get(
                        "global_best_reward_median"
                    ),
                    "selection_latency_p95_s": row.get(
                        "selection_latency_p95_s"
                    ),
                }
                for row in family_rows
            },
        }
    equal_pairs = []
    by_key = {
        (str(row["family"]), int(row["population_size"]), int(row["cem_iters"])): row
        for row in jobs
    }
    for family in runner.FAMILIES:
        for left_key, right_key in EQUAL_BUDGET_PAIRS:
            left = by_key.get((family, *left_key))
            right = by_key.get((family, *right_key))
            equal_pairs.append(
                {
                    "family": family,
                    "left": f"p{left_key[0]}_k{left_key[1]}",
                    "right": f"p{right_key[0]}_k{right_key[1]}",
                    "left_valid": left is not None and left.get("valid") is True,
                    "right_valid": right is not None and right.get("valid") is True,
                    "evaluation_ratio": runner.expected_evaluations(*left_key)
                    / runner.expected_evaluations(*right_key),
                    "success_delta_left_minus_right": (
                        int(left["success_count"]) - int(right["success_count"])
                        if left is not None and right is not None
                        else None
                    ),
                    "best_reward_delta_left_minus_right": (
                        (_finite(left["metric_summary"].get("global_best_reward_median")) or 0.0)
                        - (_finite(right["metric_summary"].get("global_best_reward_median")) or 0.0)
                        if left is not None and right is not None
                        else None
                    ),
                    "selection_latency_ratio_left_over_right": (
                        _ratio(
                            left.get("selection_latency_p95_s"),
                            right.get("selection_latency_p95_s"),
                        )
                        if left is not None and right is not None
                        else None
                    ),
                }
            )
    return {
        "estimable": complete,
        "reason": "complete valid 2x3x3 grids"
        if complete
        else "one or more registered cells are missing or invalid; no imputation",
        "families": families,
        "equal_budget_pairs": equal_pairs,
    }


def _gpu_audit() -> dict[str, object]:
    paths = sorted((runner.EXPERIMENT_ROOT / "manifests").glob("gpu_*.json"))
    failures: list[str] = []
    records = []
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            failures.append(f"{path}: {type(exc).__name__}")
            continue
        selected = payload.get("selected_gpu_indices", [])
        if not isinstance(selected, list) or not set(selected) <= set(
            runner.ALLOWED_GPU_INDICES
        ):
            failures.append(f"{path}: selected GPU outside 0..7")
        records.append(
            {
                "path": str(path),
                "sha256": _sha256_file(path),
                "selected_gpu_indices": selected,
                "runner_exit_code": payload.get("runner_exit_code"),
            }
        )
    if not any("formal_dispatch" in row["path"] for row in records):
        failures.append("formal dispatch GPU provenance missing")
    return {"passed": not failures, "records": records, "failures": failures}


def _classify_job(job: dict[str, Any]) -> str:
    if job.get("valid") is True:
        return "valid"
    if int(job.get("accepted_episode_count", 0)) < 10:
        return "incomplete"
    if job.get("error_evidence"):
        return "failed"
    return "invalid"


def audit_formal() -> dict[str, object]:
    _configure_prior_audit()
    credential = prior_audit.scan_credentials(
        [runner.EXPERIMENT_ROOT, WORKTREE_ROOT]
    )
    historical, historical_source = _historical_references()
    jobs: list[dict[str, Any]] = []
    for frozen_job in runner.build_jobs(runner.FORMAL_LEVEL, 10):
        audited, metrics = prior_audit.audit_job(
            frozen_job, credential_passed=bool(credential["passed"])
        )
        audited.update(
            {
                "family": frozen_job["family"],
                "population_size": frozen_job["population_size"],
                "cem_iters": frozen_job["cem_iters"],
                "num_elites": frozen_job["num_elites"],
                "candidate_evaluations_per_chunk": frozen_job[
                    "expected_evaluations_per_complete_chunk"
                ],
            }
        )
        audited.update(_mechanism_summary(metrics))
        audited.update(_job_wall_time(Path(audited["output_dir"])))
        if audited.get("mechanism_hard", {}).get("passed") is not True:
            audited["validity_failures"] = list(
                dict.fromkeys(
                    [
                        *audited.get("validity_failures", []),
                        "mechanism hard gate failed",
                    ]
                )
            )
            audited["valid"] = False
        family_reference = historical[str(frozen_job["family"])]
        comparison = _historical_comparison(audited, family_reference)
        audited["historical_family_comparison"] = comparison
        audited["historical_paired_gained_minus_lost"] = comparison[
            "paired_gained_minus_lost"
        ]
        audited["archive_best_reward_delta_vs_historical"] = comparison[
            "archive_best_reward_delta"
        ]
        audited["selection_latency_p95_s"] = audited["metric_summary"].get(
            "selection_latency_p95_s"
        )
        evaluated = _finite(audited.get("candidate_evaluation_count"))
        successes = int(audited.get("success_count", 0))
        audited["candidates_per_success"] = (
            evaluated / successes if evaluated is not None and successes > 0 else None
        )
        audited["gates"] = _gates(audited, family_reference)
        audited["status"] = _classify_job(audited)
        jobs.append(audited)
    ranking = rank_candidates(jobs)
    ranked_labels = {str(row["label"]): int(row["rank"]) for row in ranking}
    for job in jobs:
        job["rank"] = ranked_labels.get(str(job["label"]))
    formal_cells, preflight_cells = expected_attempt_cells()
    ledger = prior_audit.audit_attempt_ledger(
        runner.ATTEMPT_LEDGER_PATH,
        expected_formal=formal_cells,
        expected_preflight=preflight_cells,
        cap=runner.ATTEMPT_CAP,
        recovery_limit=runner.RECOVERY_ATTEMPT_LIMIT,
    )
    execution_exception = execution_exception_audit()
    if execution_exception["present"]:
        reserved_attempts = int(ledger["actual_episode_attempt_count"])
        ledger_structure_passed = bool(ledger["passed"])
        ledger["ledger_reserved_episode_attempt_count"] = reserved_attempts
        ledger["actual_episode_attempt_count"] = execution_exception[
            "physical_episode_attempt_count"
        ]
        ledger["soft_cap_exception_attempts"] = execution_exception[
            "soft_cap_exception_attempts"
        ]
        ledger["hard_cap_passed"] = execution_exception["hard_cap_passed"]
        ledger["user_soft_cap_override_applied"] = execution_exception[
            "user_soft_cap_override_applied"
        ]
        ledger["ledger_structure_passed"] = ledger_structure_passed
        if execution_exception["hard_cap_passed"] is not True:
            ledger["failures"] = list(
                dict.fromkeys(
                    [
                        *ledger.get("failures", []),
                        "physical episode attempts exceed frozen cap by 1 after "
                        "outer tool timeout continuation",
                    ]
                )
            )
        ledger["passed"] = (
            ledger_structure_passed
            and execution_exception["passed"] is True
            and execution_exception["hard_cap_passed"] is True
        )
    storage = runner.storage_preflight()
    gpu = _gpu_audit()
    completed = sum(int(job.get("accepted_episode_count", 0)) for job in jobs)
    status_counts = dict(
        (status, sum(job["status"] == status for job in jobs))
        for status in ("valid", "failed", "invalid", "incomplete")
    )
    eligible = [row for row in ranking]
    decision = (
        f"winner:{eligible[0]['label']}"
        if eligible
        else "no_configuration_passed_task_and_safety_gates"
    )
    payload: dict[str, object] = {
        "schema": "eds-qd-search-budget-sweep-formal-audit-v1",
        "created_at": _now(),
        "fixed_task_set_engineering_evidence_only": True,
        "jobs": jobs,
        "job_status_counts": status_counts,
        "ranking": [
            {
                "rank": row["rank"],
                "label": row["label"],
                "success_count": row["success_count"],
                "historical_paired_gained_minus_lost": row[
                    "historical_paired_gained_minus_lost"
                ],
                "candidates_per_success": row["candidates_per_success"],
            }
            for row in ranking
        ],
        "winner": eligible[0]["label"] if eligible else None,
        "decision": decision,
        "any_passed_5_of_10_gate": any(
            job["gates"]["task"]["passed"] is True for job in jobs
        ),
        "completion": {
            "status": "complete"
            if completed == runner.FORMAL_EPISODE_COUNT
            else "incomplete",
            "formal_job_count": len(jobs),
            "formal_expected_episodes": runner.FORMAL_EPISODE_COUNT,
            "formal_accepted_episodes": completed,
            "formal_missing_episodes": runner.FORMAL_EPISODE_COUNT - completed,
        },
        "parameter_effects": parameter_effects(jobs),
        "attempt_ledger": ledger,
        "credential_audit": credential,
        "storage_audit": storage,
        "gpu_audit": gpu,
        "execution_exception_audit": execution_exception,
        "historical_source": historical_source,
        "run_manifest": {
            "path": str(runner.RUN_MANIFEST_PATH),
            "sha256": _sha256_file(runner.RUN_MANIFEST_PATH),
        },
        "num_elites_no_op_audit": {
            "path": str(runner.NO_OP_AUDIT_PATH),
            "sha256": _sha256_file(runner.NO_OP_AUDIT_PATH),
        },
    }
    if prior_audit._contains_credential(payload):
        raise RuntimeError("formal audit contains credential material")
    ANALYSIS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ANALYSIS_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return payload


def _fmt(value: object, digits: int = 3) -> str:
    parsed = _finite(value)
    return "—" if parsed is None else f"{parsed:.{digits}f}"


def _gate(value: object) -> str:
    return "PASS" if value is True else "FAIL"


def render_report(analysis: dict[str, Any]) -> str:
    jobs = analysis["jobs"]
    completion = analysis["completion"]
    ledger = analysis["attempt_ledger"]
    lines = [
        "# EDS-QD 搜索预算 Sweep 最终报告",
        "",
        "> 18 个候选共享固定的 10-task Object-Swap 集；结果是工程 gate 证据，不代表统计显著性或 held-out 泛化。历史 p16_k10 仅作跨轮背景比较。",
        "",
        "## 执行摘要",
        "",
        f"- Completion：`{completion['status']}`，jobs `18`，accepted episodes `{completion['formal_accepted_episodes']}/180`。",
        f"- Attempts：physical `{ledger.get('actual_episode_attempt_count')}/{runner.ATTEMPT_CAP}`；ledger reserved `{ledger.get('ledger_reserved_episode_attempt_count', ledger.get('reserved_attempt_count'))}`；recovery `{ledger.get('recovery_attempts')}`；hard cap `{_gate(ledger.get('hard_cap_passed', ledger.get('passed')))}`；user soft override `{ledger.get('user_soft_cap_override_applied', False)}`。",
        f"- Decision：`{analysis['decision']}`；存在 5/10 配置：`{analysis['any_passed_5_of_10_gate']}`。",
        f"- Credential / storage / GPU audit：`{_gate(analysis['credential_audit']['passed'])}` / `{_gate(analysis['storage_audit'] is not None)}` / `{_gate(analysis['gpu_audit']['passed'])}`。",
        f"- Execution exception：`{analysis['execution_exception_audit'].get('present')}`；provenance `{analysis['execution_exception_audit'].get('path')}`；audit `{_gate(analysis['execution_exception_audit'].get('passed'))}`。",
        "",
        "## 18-job 定量结果与 gates",
        "",
        "| Job | Status | Success | Tasks | Task | Mechanism | Safety | Eval/chunk | Candidates/success | Select P95 s |",
        "| --- | --- | ---: | --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for job in jobs:
        lines.append(
            f"| `{job['label']}` | {job['status']} | {job['success_count']}/10 | {job['success_tasks']} | {_gate(job['gates']['task']['passed'])} | {_gate(job['mechanism_hard']['passed'])} | {_gate(job['gates']['safety']['passed'])} | {job['candidate_evaluations_per_chunk']} | {_fmt(job['candidates_per_success'], 0)} | {_fmt(job['selection_latency_p95_s'])} |"
        )
    lines.extend(
        [
            "",
            "## Task-level outcome",
            "",
            "| Task | " + " | ".join(f"`{job['label']}`" for job in jobs) + " |",
            "| ---: | " + " | ".join("---" for _ in jobs) + " |",
        ]
    )
    for task in range(10):
        lines.append(
            f"| {task} | "
            + " | ".join(job["task_outcomes"].get(str(task), "—") for job in jobs)
            + " |"
        )
    lines.extend(
        [
            "",
            "## QD mechanism 与历史同-family 背景",
            "",
            "| Job | Coverage | Spread m | Replacement-active | Turnover | Overflow P95 | Best reward | Δbest vs history |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for job in jobs:
        metric = job["metric_summary"]
        comparison = job["historical_family_comparison"]
        lines.append(
            f"| `{job['label']}` | {_fmt(metric.get('coverage_median'))} | {_fmt(metric.get('endpoint_xy_spread_median'))} | {_fmt(job.get('replacement_active_chunk_ratio'))} | {_fmt(metric.get('turnover_median'))} | {_fmt(metric.get('overflow_p95'))} | {_fmt(metric.get('global_best_reward_median'), 6)} | {_fmt(comparison.get('archive_best_reward_delta'), 6)} |"
        )
    effects = analysis["parameter_effects"]
    lines.extend(
        [
            "",
            "## 参数主效应与等预算 breadth/depth",
            "",
            f"完整 grid 可估计：`{effects['estimable']}`；{effects['reason']}。主效应为描述性均值，不把不同总候选预算误作单参数因果效应。",
            "",
            "| Family | Factor | Level | Mean success | Replacement-active median | Select P95 median s |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for family, family_result in effects["families"].items():
        for factor, values in (
            ("population_size", family_result["by_population_size"]),
            ("cem_iters", family_result["by_cem_iters"]),
        ):
            for level, row in values.items():
                lines.append(
                    f"| {family} | {factor} | {level} | {_fmt(row['mean_success_count'])} | {_fmt(row['median_replacement_active_ratio'])} | {_fmt(row['median_selection_latency_p95_s'])} |"
                )
    lines.extend(
        [
            "",
            "### 近似等预算配对",
            "",
            "| Family | Left | Right | Eval ratio L/R | Δsuccess L-R | Δbest reward L-R | Latency ratio L/R |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in effects["equal_budget_pairs"]:
        lines.append(
            f"| {row['family']} | {row['left']} | {row['right']} | {_fmt(row['evaluation_ratio'])} | {_fmt(row['success_delta_left_minus_right'], 0)} | {_fmt(row['best_reward_delta_left_minus_right'], 6)} | {_fmt(row['selection_latency_ratio_left_over_right'])} |"
        )
    lines.extend(
        [
            "",
            "## Safety、latency 与失败审计",
            "",
            "| Job | qpos | collision composite | nonfinite | mask | fallback | Job wall s | Episode wall mean s | Failure taxonomy |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for job in jobs:
        taxonomy = ", ".join(
            f"{key}:{value}"
            for key, value in sorted(job["failure_taxonomy_counts"].items())
        )
        lines.append(
            f"| `{job['label']}` | {job['execution_qpos_error_episodes']} | {job['collision_push_drop_wrong_object']} | {job['nonfinite_count']} | {job['action_mask_violation_count']} | {job['qd_fallback_count']} | {_fmt(job['job_wall_time_s'], 1)} | {_fmt(job['episode_wall_time_mean_s'], 1)} | {taxonomy or '—'} |"
        )
    lines.extend(
        [
            "",
            "## 排名与结论",
            "",
        ]
    )
    if analysis["ranking"]:
        for row in analysis["ranking"]:
            lines.append(
                f"{row['rank']}. `{row['label']}` — {row['success_count']}/10；历史 paired gained-minus-lost {row['historical_paired_gained_minus_lost']}。"
            )
    else:
        lines.append("无 valid 且同时通过 task/safety gates 的候选。")
    lines.extend(
        [
            "",
            "## 证据局限",
            "",
            "- 每配置仅 10 个固定 tasks，各一个 episode；18 候选 winner selection 存在选择偏差，不能解释为统计显著。",
            "- 本轮没有 contemporaneous control/reference；历史差异可能混入跨轮基础设施、API 与时序波动。",
            "- population 与 iterations 改变总候选数；仅等预算配对适合谨慎讨论 breadth/depth，其余响应面是描述性结果。",
            "- 失败 taxonomy 优先依据错误栈和 telemetry；无明确因果证据的未完成轨迹保守标为 timeout，不以成功率反推原因。",
            "- Raw videos、metrics、trace 与 QD qualitative artifacts 保留在每个 job 输出目录，未补跑或追加 winner confirmation。",
            "",
        ]
    )
    return "\n".join(lines)


def _freeze_text(text: str, path: Path) -> dict[str, str]:
    sidecar = path.with_suffix(path.suffix + ".sha256")
    if path.exists() or path.is_symlink() or sidecar.exists() or sidecar.is_symlink():
        raise FileExistsError(path)
    if prior_audit._contains_credential(text):
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


def freeze_decision_manifest(
    payload: dict[str, Any], path: Path = DECISION_PATH
) -> dict[str, Any]:
    return prior_audit.freeze_decision_manifest(payload, path)


def verify_decision_manifest(path: Path = DECISION_PATH) -> dict[str, Any]:
    return prior_audit.verify_decision_manifest(path)


def _decision_payload(
    analysis: dict[str, Any], report: dict[str, str]
) -> dict[str, object]:
    run_manifest = json.loads(runner.RUN_MANIFEST_PATH.read_text(encoding="utf-8"))
    return {
        "schema": "eds-qd-search-budget-sweep-decision-manifest-v1",
        "created_at": _now(),
        "decision": analysis["decision"],
        "winner": analysis["winner"],
        "any_passed_5_of_10_gate": analysis["any_passed_5_of_10_gate"],
        "provenance": run_manifest["provenance"],
        "matrix": {
            "formal_job_count": 18,
            "formal_episode_count": 180,
            "preflight_episode_count": 0,
            "families": list(runner.FAMILIES),
            "population_sizes": list(runner.POPULATION_SIZES),
            "cem_iters": list(runner.CEM_ITERS),
            "num_elites": runner.NUM_ELITES,
        },
        "completion": analysis["completion"],
        "attempt_ledger": analysis["attempt_ledger"],
        "job_status_counts": analysis["job_status_counts"],
        "jobs": [
            {
                key: job.get(key)
                for key in (
                    "label",
                    "family",
                    "population_size",
                    "cem_iters",
                    "status",
                    "valid",
                    "validity_failures",
                    "success_count",
                    "success_tasks",
                    "task_outcomes",
                    "failure_taxonomy_counts",
                    "error_evidence",
                    "mechanism_hard",
                    "gates",
                    "metric_summary",
                    "replacement_active_chunk_ratio",
                    "candidate_evaluation_count",
                    "candidates_per_success",
                    "historical_family_comparison",
                    "config_fingerprint",
                    "code_state_sha256",
                    "checksums",
                )
            }
            for job in analysis["jobs"]
        ],
        "ranking": analysis["ranking"],
        "parameter_effects": analysis["parameter_effects"],
        "credential_audit": analysis["credential_audit"],
        "storage_audit": analysis["storage_audit"],
        "gpu_audit": analysis["gpu_audit"],
        "historical_source": analysis["historical_source"],
        "evidence": {
            "run_manifest": analysis["run_manifest"],
            "num_elites_no_op_audit": analysis["num_elites_no_op_audit"],
            "formal_audit": {
                "path": str(ANALYSIS_PATH),
                "sha256": _sha256_file(ANALYSIS_PATH),
            },
            "final_report": report,
        },
        "no_additional_experiment_jobs": True,
        "historical_comparison_is_not_contemporaneous_control": True,
    }


def freeze_outputs() -> dict[str, object]:
    analysis = json.loads(ANALYSIS_PATH.read_text(encoding="utf-8"))
    report = _freeze_text(render_report(analysis), REPORT_PATH)
    manifest = freeze_decision_manifest(_decision_payload(analysis, report))
    verify_decision_manifest(DECISION_PATH)
    return {
        "decision": manifest["decision"],
        "manifest": str(DECISION_PATH),
        "report": report,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=("audit-formal", "freeze-decision", "verify-decision")
    )
    args = parser.parse_args()
    if args.command == "audit-formal":
        payload = audit_formal()
        print(json.dumps({"decision": payload["decision"], "path": str(ANALYSIS_PATH)}))
        return 0
    if args.command == "freeze-decision":
        print(json.dumps(freeze_outputs(), indent=2))
        return 0
    payload = verify_decision_manifest()
    print(json.dumps({"verified": True, "decision": payload["decision"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
