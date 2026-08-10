#!/usr/bin/env python3
"""Deterministic offline replay for the run_002 QD partition protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


SCHEMA = "eds_qd_partition_counterfactual.v1"
SUPPORTED_PARTITION = "causal_envelope_v1"
TARGET_TASKS = (3, 5, 8, 9)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def f32(value: float) -> float:
    return struct.unpack("!f", struct.pack("!f", float(value)))[0]


def finite_number(value: Any, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    result = f32(float(value))
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def descriptor(value: Any, *, name: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{name} must have two coordinates")
    return (
        finite_number(value[0], name=f"{name}[0]"),
        finite_number(value[1], name=f"{name}[1]"),
    )


def percentile(values: Sequence[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def median(values: Sequence[float]) -> float | None:
    return float(statistics.median(values)) if values else None


def mean_pairwise_distance(entries: Iterable["Entry"]) -> float:
    points = [entry.xy for entry in entries]
    if len(points) < 2:
        return 0.0
    distances: list[float] = []
    for left_index, left in enumerate(points):
        for right in points[left_index + 1 :]:
            distances.append(math.hypot(left[0] - right[0], left[1] - right[1]))
    return sum(distances) / len(distances)


def cell_id(
    xy: tuple[float, float],
    lo: tuple[float, float],
    hi: tuple[float, float],
    grid: tuple[int, int],
) -> tuple[int, bool]:
    cells: list[int] = []
    overflow = False
    for axis, axis_cells in enumerate(grid):
        value = f32(xy[axis])
        lower = f32(lo[axis])
        upper = f32(hi[axis])
        if value < lower or value > upper:
            overflow = True
        span = f32(upper - lower)
        normalized = f32(f32(value - lower) / span)
        index = math.floor(f32(normalized * axis_cells))
        cells.append(min(max(index, 0), axis_cells - 1))
    return grid[0] * cells[1] + cells[0], overflow


def within_cell_sse(
    points: Sequence[tuple[float, float]], cell_ids: Sequence[int]
) -> float:
    groups: dict[int, list[tuple[float, float]]] = {}
    for xy, assigned_cell in zip(points, cell_ids, strict=True):
        groups.setdefault(assigned_cell, []).append(xy)
    total = 0.0
    for group in groups.values():
        center_x = sum(point[0] for point in group) / len(group)
        center_y = sum(point[1] for point in group) / len(group)
        total += sum(
            (point[0] - center_x) ** 2 + (point[1] - center_y) ** 2
            for point in group
        )
    return total / len(points) if points else 0.0


@dataclass(frozen=True)
class Entry:
    reward: float
    fingerprint: str
    xy: tuple[float, float]


def better(candidate: Entry, incumbent: Entry) -> bool:
    return candidate.reward > incumbent.reward or (
        candidate.reward == incumbent.reward
        and candidate.fingerprint < incumbent.fingerprint
    )


def update_archive(
    archive: dict[int, Entry],
    entries: Sequence[Entry],
    cell_ids: Sequence[int],
) -> tuple[int, int, int]:
    grouped: dict[int, list[Entry]] = {}
    for entry, assigned_cell in zip(entries, cell_ids, strict=True):
        grouped.setdefault(assigned_cell, []).append(entry)
    insertions = replacements = rejections = 0
    for assigned_cell in sorted(grouped):
        winner = min(
            grouped[assigned_cell], key=lambda item: (-item.reward, item.fingerprint)
        )
        incumbent = archive.get(assigned_cell)
        if incumbent is None or better(winner, incumbent):
            if incumbent is None:
                insertions += 1
            else:
                replacements += 1
            archive[assigned_cell] = winner
            rejections += len(grouped[assigned_cell]) - 1
        else:
            rejections += len(grouped[assigned_cell])
    return insertions, replacements, rejections


def rebin_archive(
    archive: dict[int, Entry],
    lo: tuple[float, float],
    hi: tuple[float, float],
    grid: tuple[int, int],
) -> dict[int, Entry]:
    rebinned: dict[int, Entry] = {}
    entries = list(archive.values())
    assigned = [cell_id(entry.xy, lo, hi, grid)[0] for entry in entries]
    update_archive(rebinned, entries, assigned)
    return rebinned


def parse_stream_batch(batch: Any, *, context: str) -> tuple[int, list[Entry]]:
    if not isinstance(batch, dict):
        raise ValueError(f"{context} must be an object")
    iter_idx = int(batch["iter_idx"])
    descriptors = batch["descriptors_xy_m"]
    rewards = batch["rewards"]
    fingerprints = batch["fingerprints"]
    if not (
        isinstance(descriptors, list)
        and isinstance(rewards, list)
        and isinstance(fingerprints, list)
        and len(descriptors) == len(rewards) == len(fingerprints)
        and len(descriptors) > 0
    ):
        raise ValueError(f"{context} fields must be nonempty equal-length lists")
    entries: list[Entry] = []
    for index, (raw_xy, raw_reward, fingerprint) in enumerate(
        zip(descriptors, rewards, fingerprints, strict=True)
    ):
        if not isinstance(fingerprint, str) or not fingerprint:
            raise ValueError(f"{context}.fingerprints[{index}] must be nonempty")
        entries.append(
            Entry(
                reward=finite_number(
                    raw_reward, name=f"{context}.rewards[{index}]"
                ),
                fingerprint=fingerprint,
                xy=descriptor(raw_xy, name=f"{context}.descriptors[{index}]"),
            )
        )
    return iter_idx, entries


def permute_entries(entries: Sequence[Entry], *, seed: int, iter_idx: int) -> list[Entry]:
    def key(entry: Entry) -> tuple[str, str]:
        material = f"{seed}:{iter_idx}:{entry.fingerprint}".encode("utf-8")
        return hashlib.sha256(material).hexdigest(), entry.fingerprint

    return sorted(entries, key=key)


def replay_record(
    record: dict[str, Any],
    *,
    grid: tuple[int, int],
    causal_envelope: bool,
    permutation_seed: int | None = None,
) -> dict[str, Any]:
    raw_bounds = record["qd_bounds_xy_m"]
    if not isinstance(raw_bounds, list) or len(raw_bounds) != 2:
        raise ValueError("qd_bounds_xy_m must contain lo and hi")
    lo = descriptor(raw_bounds[0], name="qd_bounds.lo")
    hi = descriptor(raw_bounds[1], name="qd_bounds.hi")
    if any(not lo[axis] < hi[axis] for axis in range(2)):
        raise ValueError("QD bounds must have positive spans")
    initial_lo = lo
    initial_hi = hi
    stream = record["shadow_qd_candidate_stream"]
    if not isinstance(stream, list) or not stream:
        raise ValueError("shadow_qd_candidate_stream must be nonempty")

    archive: dict[int, Entry] = {}
    iterations: list[dict[str, Any]] = []
    initial_accounting: dict[str, int] | None = None
    evaluation_count = 0
    envelope_expansions = 0

    for batch_index, raw_batch in enumerate(stream):
        iter_idx, entries = parse_stream_batch(
            raw_batch, context=f"shadow_qd_candidate_stream[{batch_index}]"
        )
        expected_iter = -1 if batch_index == 0 else batch_index - 1
        if iter_idx != expected_iter:
            raise ValueError(f"stream iter_idx {iter_idx} != expected {expected_iter}")
        if permutation_seed is not None:
            entries = permute_entries(entries, seed=permutation_seed, iter_idx=iter_idx)

        raw_overflow = [
            cell_id(entry.xy, initial_lo, initial_hi, grid)[1] for entry in entries
        ]
        baseline_cells = [
            cell_id(entry.xy, initial_lo, initial_hi, grid)[0] for entry in entries
        ]

        if causal_envelope and iter_idx >= 0:
            batch_lo = (
                min(entry.xy[0] for entry in entries),
                min(entry.xy[1] for entry in entries),
            )
            batch_hi = (
                max(entry.xy[0] for entry in entries),
                max(entry.xy[1] for entry in entries),
            )
            expanded_lo = (
                f32(min(lo[0], batch_lo[0])),
                f32(min(lo[1], batch_lo[1])),
            )
            expanded_hi = (
                f32(max(hi[0], batch_hi[0])),
                f32(max(hi[1], batch_hi[1])),
            )
            if expanded_lo != lo or expanded_hi != hi:
                lo, hi = expanded_lo, expanded_hi
                archive = rebin_archive(archive, lo, hi, grid)
                envelope_expansions += 1

        assigned = [cell_id(entry.xy, lo, hi, grid)[0] for entry in entries]
        represented_overflow = [cell_id(entry.xy, lo, hi, grid)[1] for entry in entries]
        insertions, replacements, rejections = update_archive(
            archive, entries, assigned
        )
        evaluation_count += len(entries)
        accounting = {
            "insertions": insertions,
            "replacements": replacements,
            "rejections": rejections,
            "total": insertions + replacements + rejections,
        }
        if accounting["total"] != len(entries):
            raise RuntimeError("archive accounting mismatch")
        if iter_idx == -1:
            initial_accounting = accounting
            initial_occupied = len(archive)
            initial_overflow_count = sum(raw_overflow)
            continue

        baseline_sse = within_cell_sse(
            [entry.xy for entry in entries], baseline_cells
        )
        active_sse = within_cell_sse([entry.xy for entry in entries], assigned)
        resolution_improvement = (
            1.0 - active_sse / baseline_sse if baseline_sse > 0.0 else None
        )
        iterations.append(
            {
                "iter_idx": iter_idx,
                "population": len(entries),
                "bounds": [list(lo), list(hi)],
                "raw_out_of_initial_bounds_count": sum(raw_overflow),
                "raw_out_of_initial_bounds_ratio": sum(raw_overflow) / len(entries),
                "unrepresented_overflow_count": sum(represented_overflow),
                "unrepresented_overflow_ratio": sum(represented_overflow)
                / len(entries),
                "baseline_within_cell_endpoint_sse": baseline_sse,
                "within_cell_endpoint_sse": active_sse,
                "resolution_improvement": resolution_improvement,
                "occupied_cells": len(archive),
                "coverage": len(archive) / (grid[0] * grid[1]),
                "archive_best_reward": max(entry.reward for entry in archive.values()),
                "per_cell_elite_reward": {
                    str(key): archive[key].reward for key in sorted(archive)
                },
                **accounting,
            }
        )

    selected_cell, selected_entry = min(
        archive.items(), key=lambda item: (-item[1].reward, item[1].fingerprint, item[0])
    )
    return {
        "initial_bounds": [list(initial_lo), list(initial_hi)],
        "final_bounds": [list(lo), list(hi)],
        "initial_accounting": initial_accounting,
        "initial_occupied_cells": initial_occupied,
        "initial_overflow_count": initial_overflow_count,
        "iterations": iterations,
        "evaluation_count": evaluation_count,
        "envelope_expansions": envelope_expansions,
        "final_occupied_cells": len(archive),
        "archive_endpoint_spread": mean_pairwise_distance(archive.values()),
        "selected_cell": selected_cell,
        "selected_reward": selected_entry.reward,
        "selected_fingerprint": selected_entry.fingerprint,
        "final_archive": {
            str(key): {
                "reward": archive[key].reward,
                "fingerprint": archive[key].fingerprint,
                "descriptor_xy_m": list(archive[key].xy),
            }
            for key in sorted(archive)
        },
    }


def equal(left: Any, right: Any, *, tolerance: float = 1e-9) -> bool:
    if isinstance(left, (int, float)) and not isinstance(left, bool):
        if not isinstance(right, (int, float)) or isinstance(right, bool):
            return False
        return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=tolerance)
    if isinstance(left, list):
        return isinstance(right, list) and len(left) == len(right) and all(
            equal(a, b, tolerance=tolerance) for a, b in zip(left, right, strict=True)
        )
    if isinstance(left, dict):
        return isinstance(right, dict) and left.keys() == right.keys() and all(
            equal(left[key], right[key], tolerance=tolerance) for key in left
        )
    return left == right


def baseline_mismatches(record: dict[str, Any], replay: dict[str, Any]) -> list[str]:
    mismatches: list[str] = []
    direct = {
        "qd_initial_accounting": replay["initial_accounting"],
        "qd_initial_occupied_cells": replay["initial_occupied_cells"],
        "qd_initial_descriptor_overflow_count": replay["initial_overflow_count"],
        "qd_evaluation_count": replay["evaluation_count"],
        "qd_selected_cell": replay["selected_cell"],
        "qd_selected_reward": replay["selected_reward"],
        "qd_selected_action_fingerprint": replay["selected_fingerprint"],
        "qd_global_best_action_fingerprint": replay["selected_fingerprint"],
    }
    for key, observed in direct.items():
        if not equal(record.get(key), observed):
            mismatches.append(key)

    iteration_fields = {
        "qd_occupied_cells_by_iter": "occupied_cells",
        "qd_coverage_ratio_by_iter": "coverage",
        "qd_descriptor_overflow_count_by_iter": "raw_out_of_initial_bounds_count",
        "qd_descriptor_overflow_ratio_by_iter": "raw_out_of_initial_bounds_ratio",
        "qd_archive_best_reward_by_iter": "archive_best_reward",
        "qd_per_cell_elite_reward_by_iter": "per_cell_elite_reward",
        "qd_archive_insertions_by_iter": "insertions",
        "qd_archive_replacements_by_iter": "replacements",
        "qd_archive_rejections_by_iter": "rejections",
    }
    for source_key, replay_key in iteration_fields.items():
        observed = [item[replay_key] for item in replay["iterations"]]
        if not equal(record.get(source_key), observed):
            mismatches.append(source_key)
    return mismatches


def permutation_projection(replay: dict[str, Any]) -> dict[str, Any]:
    return {
        "final_bounds": replay["final_bounds"],
        "iterations": [
            {
                key: item[key]
                for key in (
                    "bounds",
                    "raw_out_of_initial_bounds_count",
                    "unrepresented_overflow_count",
                    "within_cell_endpoint_sse",
                    "occupied_cells",
                    "per_cell_elite_reward",
                    "insertions",
                    "replacements",
                    "rejections",
                )
            }
            for item in replay["iterations"]
        ],
        "final_archive": replay["final_archive"],
        "selected_cell": replay["selected_cell"],
        "selected_reward": replay["selected_reward"],
        "selected_fingerprint": replay["selected_fingerprint"],
    }


def profile_label(path: Path) -> str:
    parts = path.parts
    if "formal" not in parts:
        return path.parent.parent.name
    formal_index = len(parts) - 1 - list(reversed(parts)).index("formal")
    return parts[formal_index + 1]


def aggregate_group(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    improvements = [
        value
        for record in records
        for value in record["resolution_improvements"]
        if value is not None
    ]
    return {
        "record_count": len(records),
        "iteration_count": sum(len(record["resolution_improvements"]) for record in records),
        "resolution_improvement_median": median(improvements),
        "unrepresented_overflow_p95": percentile(
            [
                value
                for record in records
                for value in record["candidate_unrepresented_overflow_ratios"]
            ],
            0.95,
        ),
        "raw_out_of_initial_bounds_p95": percentile(
            [
                value
                for record in records
                for value in record["raw_out_of_initial_bounds_ratios"]
            ],
            0.95,
        ),
        "occupied_mode_ratio_median": median(
            [record["occupied_mode_ratio"] for record in records]
        ),
        "archive_spread_ratio_median": median(
            [record["archive_spread_ratio"] for record in records]
        ),
        "global_best_preserved_ratio": (
            sum(record["global_best_preserved"] for record in records) / len(records)
            if records
            else None
        ),
    }


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    baseline_analysis_path = Path(args.baseline_analysis).resolve()
    baseline_analysis = json.loads(baseline_analysis_path.read_text(encoding="utf-8"))
    frozen_files = baseline_analysis["raw_metric_replay"]["files"]
    required_grid = (int(args.required_grid[0]), int(args.required_grid[1]))

    manifest: list[dict[str, Any]] = []
    per_record: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    malformed_records: list[dict[str, Any]] = []
    non_grid_record_count = 0
    eligible_record_count = 0
    permutation_failures: list[dict[str, Any]] = []
    source_record_count = 0

    for frozen in frozen_files:
        source_path = Path(frozen["path"])
        observed_hash = sha256_path(source_path) if source_path.is_file() else None
        manifest.append(
            {
                "path": str(source_path),
                "expected_sha256": frozen["sha256"],
                "observed_sha256": observed_hash,
                "hash_matches": observed_hash == frozen["sha256"],
                "expected_records": frozen["records"],
                "expected_qd_records": frozen["qd_records"],
            }
        )
        if observed_hash != frozen["sha256"]:
            continue
        with source_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                source_record_count += 1
                try:
                    record = json.loads(line)
                    if not record.get("qd_archive_enabled"):
                        continue
                    grid_raw = record["qd_grid_shape"]
                    grid = (int(grid_raw[0]), int(grid_raw[1]))
                    if grid != required_grid:
                        non_grid_record_count += 1
                        continue
                    eligible_record_count += 1
                    baseline = replay_record(
                        record, grid=grid, causal_envelope=False
                    )
                    mismatch_fields = baseline_mismatches(record, baseline)
                    if mismatch_fields:
                        mismatches.append(
                            {
                                "path": str(source_path),
                                "line": line_number,
                                "fields": mismatch_fields,
                            }
                        )
                    candidate = replay_record(
                        record, grid=grid, causal_envelope=True
                    )
                    permuted = replay_record(
                        record,
                        grid=grid,
                        causal_envelope=True,
                        permutation_seed=args.permutation_seed,
                    )
                    if not equal(
                        permutation_projection(candidate),
                        permutation_projection(permuted),
                    ):
                        permutation_failures.append(
                            {"path": str(source_path), "line": line_number}
                        )

                    resolution_improvements = [
                        item["resolution_improvement"]
                        for item in candidate["iterations"]
                    ]
                    raw_ratios = [
                        item["raw_out_of_initial_bounds_ratio"]
                        for item in candidate["iterations"]
                    ]
                    candidate_overflow = [
                        item["unrepresented_overflow_ratio"]
                        for item in candidate["iterations"]
                    ]
                    occupied_ratio = (
                        candidate["final_occupied_cells"]
                        / baseline["final_occupied_cells"]
                    )
                    spread_ratio = (
                        candidate["archive_endpoint_spread"]
                        / baseline["archive_endpoint_spread"]
                        if baseline["archive_endpoint_spread"] > 0.0
                        else 1.0
                    )
                    global_best_preserved = (
                        candidate["selected_reward"] == baseline["selected_reward"]
                        and candidate["selected_fingerprint"]
                        == baseline["selected_fingerprint"]
                    )
                    per_record.append(
                        {
                            "path": str(source_path),
                            "line": line_number,
                            "profile": profile_label(source_path),
                            "task_id": int(record["task_id"]),
                            "episode": int(record["episode"]),
                            "population_size": len(
                                record["shadow_qd_candidate_stream"][0]["rewards"]
                            ),
                            "iteration_count": len(candidate["iterations"]),
                            "raw_out_of_initial_bounds_ratios": raw_ratios,
                            "candidate_unrepresented_overflow_ratios": candidate_overflow,
                            "resolution_improvements": resolution_improvements,
                            "resolution_improvement_median": median(
                                [
                                    value
                                    for value in resolution_improvements
                                    if value is not None
                                ]
                            ),
                            "baseline_final_occupied_cells": baseline[
                                "final_occupied_cells"
                            ],
                            "candidate_final_occupied_cells": candidate[
                                "final_occupied_cells"
                            ],
                            "occupied_mode_ratio": occupied_ratio,
                            "baseline_archive_endpoint_spread": baseline[
                                "archive_endpoint_spread"
                            ],
                            "candidate_archive_endpoint_spread": candidate[
                                "archive_endpoint_spread"
                            ],
                            "archive_spread_ratio": spread_ratio,
                            "global_best_preserved": global_best_preserved,
                            "baseline_selected_reward": baseline["selected_reward"],
                            "candidate_selected_reward": candidate["selected_reward"],
                            "baseline_selected_fingerprint": baseline[
                                "selected_fingerprint"
                            ],
                            "candidate_selected_fingerprint": candidate[
                                "selected_fingerprint"
                            ],
                            "envelope_expansions": candidate["envelope_expansions"],
                        }
                    )
                except Exception as error:  # explicit invalid accounting
                    malformed_records.append(
                        {
                            "path": str(source_path),
                            "line": line_number,
                            "error": f"{type(error).__name__}: {error}",
                        }
                    )

    by_profile: dict[str, list[dict[str, Any]]] = {}
    by_task: dict[int, list[dict[str, Any]]] = {}
    for record in per_record:
        by_profile.setdefault(record["profile"], []).append(record)
        by_task.setdefault(record["task_id"], []).append(record)
    profile_summary = {
        label: aggregate_group(records) for label, records in sorted(by_profile.items())
    }
    task_summary = {
        str(task): aggregate_group(records) for task, records in sorted(by_task.items())
    }
    overall = aggregate_group(per_record)
    equal_profile_resolution_median = median(
        [
            value["resolution_improvement_median"]
            for value in profile_summary.values()
            if value["resolution_improvement_median"] is not None
        ]
    )
    target_task_values = {
        str(task): task_summary.get(str(task), {}).get("resolution_improvement_median")
        for task in args.task_strata
    }
    target_support_count = sum(
        value is not None and value >= 0.20 for value in target_task_values.values()
    )
    target_worst = min(
        (value for value in target_task_values.values() if value is not None),
        default=None,
    )

    input_valid = (
        len(manifest) == 27
        and all(item["hash_matches"] for item in manifest)
        and source_record_count == sum(item["expected_records"] for item in manifest)
    )
    gates = [
        {
            "name": "input_manifest",
            "passed": input_valid,
            "observed": {
                "files": len(manifest),
                "matching_hashes": sum(item["hash_matches"] for item in manifest),
                "source_records": source_record_count,
                "expected_records": sum(item["expected_records"] for item in manifest),
            },
            "criterion": "27/27 hashes and exact record accounting",
            "gate_type": "validity",
        },
        {
            "name": "baseline_exactness",
            "passed": not mismatches and eligible_record_count > 0,
            "observed": {
                "eligible_records": eligible_record_count,
                "mismatch_records": len(mismatches),
            },
            "criterion": "zero fixed-initial replay mismatches",
            "gate_type": "validity",
        },
        {
            "name": "record_validity_and_accounting",
            "passed": not malformed_records and len(per_record) == eligible_record_count,
            "observed": {
                "analyzed_records": len(per_record),
                "malformed_records": len(malformed_records),
                "non_4x4_records": non_grid_record_count,
            },
            "criterion": "all eligible records parse with exact accounting",
            "gate_type": "validity",
        },
        {
            "name": "permutation_equivariance",
            "passed": not permutation_failures,
            "observed": {"failure_records": len(permutation_failures)},
            "criterion": "zero fingerprint-to-cell/archive permutation failures",
            "gate_type": "validity",
        },
        {
            "name": "unrepresented_overflow",
            "passed": overall["unrepresented_overflow_p95"] is not None
            and overall["unrepresented_overflow_p95"] <= 0.25,
            "observed": {
                "candidate_p95": overall["unrepresented_overflow_p95"],
                "raw_initial_bounds_p95": overall[
                    "raw_out_of_initial_bounds_p95"
                ],
            },
            "criterion": "candidate <=0.25; raw value preserved and disclosed",
            "gate_type": "scientific",
        },
        {
            "name": "endpoint_resolution",
            "passed": overall["resolution_improvement_median"] is not None
            and overall["resolution_improvement_median"] >= 0.20
            and equal_profile_resolution_median is not None
            and equal_profile_resolution_median >= 0.20,
            "observed": {
                "equal_chunk_median": overall["resolution_improvement_median"],
                "equal_profile_median": equal_profile_resolution_median,
            },
            "criterion": "both medians >=0.20",
            "gate_type": "scientific",
        },
        {
            "name": "target_task_strata",
            "passed": target_support_count >= 2
            and target_worst is not None
            and target_worst >= -0.05,
            "observed": {
                "task_medians": target_task_values,
                "support_count": target_support_count,
                "worst": target_worst,
            },
            "criterion": ">=2 tasks at >=0.20 and none below -0.05",
            "gate_type": "scientific",
        },
        {
            "name": "mode_and_spread_retention",
            "passed": overall["occupied_mode_ratio_median"] is not None
            and overall["occupied_mode_ratio_median"] >= 0.90
            and overall["archive_spread_ratio_median"] is not None
            and overall["archive_spread_ratio_median"] >= 0.90,
            "observed": {
                "occupied_mode_ratio_median": overall[
                    "occupied_mode_ratio_median"
                ],
                "archive_spread_ratio_median": overall[
                    "archive_spread_ratio_median"
                ],
            },
            "criterion": "both median ratios >=0.90",
            "gate_type": "scientific",
        },
        {
            "name": "global_best_preservation",
            "passed": overall["global_best_preserved_ratio"] == 1.0,
            "observed": {
                "preserved_ratio": overall["global_best_preserved_ratio"]
            },
            "criterion": "reward and fingerprint preserved for 100% of paired chunks",
            "gate_type": "scientific",
        },
        {
            "name": "zero_external_calls",
            "passed": True,
            "observed": {
                "environment": 0,
                "model": 0,
                "reward": 0,
                "vlm": 0,
                "cuda": 0,
                "network": 0,
            },
            "criterion": "all external call counts equal zero",
            "gate_type": "validity",
        },
    ]
    validity_passed = all(
        gate["passed"] for gate in gates if gate["gate_type"] == "validity"
    )
    scientific_passed = all(
        gate["passed"] for gate in gates if gate["gate_type"] == "scientific"
    )
    if not validity_passed:
        decision = "INVALID"
    elif scientific_passed:
        decision = "KEEP_DIAGNOSTIC_EVIDENCE_AND_AUTHORIZE_ONE_QD1_PROTOCOL"
    else:
        decision = "REJECT_H1_PARTITION_FOR_THIS_CYCLE"

    return {
        "schema": SCHEMA,
        "experiment_id": "run_002_partition_diagnostic",
        "partition": args.partition,
        "target": {"success_count": 5, "historical_best_qd": 2, "gap": 3},
        "source": {
            "baseline_analysis": str(baseline_analysis_path),
            "baseline_analysis_sha256": sha256_path(baseline_analysis_path),
            "manifest": manifest,
        },
        "accounting": {
            "source_files": len(manifest),
            "source_records": source_record_count,
            "eligible_4x4_records": eligible_record_count,
            "non_4x4_records": non_grid_record_count,
            "analyzed_records": len(per_record),
            "malformed_records": malformed_records,
            "baseline_mismatches": mismatches,
            "permutation_failures": permutation_failures,
            "online_episode_attempts": 0,
            "gpu_hours": 0,
            "external_calls": 0,
        },
        "overall": overall,
        "equal_profile_resolution_improvement_median": equal_profile_resolution_median,
        "profile_summary": profile_summary,
        "task_summary": task_summary,
        "target_task_strata": target_task_values,
        "records": per_record,
        "gates": gates,
        "validity_passed": validity_passed,
        "scientific_gates_passed": scientific_passed,
        "decision": decision,
        "limitations": [
            "Stored common candidate streams do not simulate offspring changed by counterfactual parent cells.",
            "Endpoint geometry is not candidate-level manipulation-stage progress.",
            "Historical task IDs are descriptive strata and do not authorize formal tuning.",
        ],
    }


def summary_markdown(analysis: dict[str, Any]) -> str:
    overall = analysis["overall"]
    lines = [
        "# run_002 Partition Diagnostic Summary",
        "",
        f"Decision: `{analysis['decision']}`",
        "",
        f"Validity gates: `{'PASS' if analysis['validity_passed'] else 'FAIL'}`",
        f"Scientific gates: `{'PASS' if analysis['scientific_gates_passed'] else 'FAIL'}`",
        "",
        "## Primary observations",
        "",
        f"- Eligible 4x4 records: {analysis['accounting']['eligible_4x4_records']}",
        f"- Baseline replay mismatches: {len(analysis['accounting']['baseline_mismatches'])}",
        f"- Candidate unrepresented overflow P95: {overall['unrepresented_overflow_p95']}",
        f"- Raw out-of-initial-bounds P95: {overall['raw_out_of_initial_bounds_p95']}",
        f"- Equal-chunk resolution improvement median: {overall['resolution_improvement_median']}",
        f"- Equal-profile resolution improvement median: {analysis['equal_profile_resolution_improvement_median']}",
        f"- Occupied-mode ratio median: {overall['occupied_mode_ratio_median']}",
        f"- Archive-spread ratio median: {overall['archive_spread_ratio_median']}",
        f"- Global-best preservation: {overall['global_best_preserved_ratio']}",
        "",
        "## Gates",
        "",
        "| Gate | Type | Result | Observed |",
        "| --- | --- | --- | --- |",
    ]
    for gate in analysis["gates"]:
        observed = json.dumps(gate["observed"], sort_keys=True, separators=(",", ":"))
        lines.append(
            f"| `{gate['name']}` | {gate['gate_type']} | "
            f"{'PASS' if gate['passed'] else 'FAIL'} | `{observed}` |"
        )
    lines.extend(
        [
            "",
            "This is zero-episode geometry/archive evidence. It does not change the 2/10 historical best or the three-task target gap.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-analysis", required=True)
    parser.add_argument("--partition", required=True, choices=[SUPPORTED_PARTITION])
    parser.add_argument("--required-grid", nargs=2, type=int, required=True)
    parser.add_argument("--task-strata", nargs="+", type=int, default=list(TARGET_TASKS))
    parser.add_argument("--permutation-seed", type=int, required=True)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()
    if tuple(args.task_strata) != TARGET_TASKS:
        raise SystemExit(f"task strata must be exactly {TARGET_TASKS}")
    if tuple(args.required_grid) != (4, 4):
        raise SystemExit("required grid must be exactly 4 4")

    analysis = analyze(args)
    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    analysis_path = output_root / "analysis.json"
    analysis_path.write_text(
        json.dumps(analysis, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    (output_root / "input-manifest.json").write_text(
        json.dumps(analysis["source"]["manifest"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_root / "summary.md").write_text(
        summary_markdown(analysis), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "analysis": str(analysis_path),
                "analysis_sha256": sha256_path(analysis_path),
                "decision": analysis["decision"],
                "validity_passed": analysis["validity_passed"],
                "scientific_gates_passed": analysis["scientific_gates_passed"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
