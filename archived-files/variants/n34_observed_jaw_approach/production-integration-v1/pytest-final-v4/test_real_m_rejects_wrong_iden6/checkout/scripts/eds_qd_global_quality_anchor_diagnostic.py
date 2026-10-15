#!/usr/bin/env python3
"""Read-only allocation reconstruction for the H4-v3 quality anchor."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.qd_ed import QDArchive, QDArchiveEntry, allocate_parent_slots


SECRET_PATTERNS = (
    re.compile(r"sk-poe-[A-Za-z0-9_-]{12,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
)
GRID_SHAPE = (4, 4)
RUN_SEED = 0
SPARSE_EXPONENT = 1.0


@dataclass(frozen=True)
class InputSpec:
    path: Path
    sha256: str
    row_count: int


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _finite_number(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def _integer(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, int)


def _slot_map(value: Any) -> dict[int, int] | None:
    if not isinstance(value, dict):
        return None
    result: dict[int, int] = {}
    for key, count in value.items():
        try:
            cell = int(key)
        except (TypeError, ValueError):
            return None
        if str(cell) != str(key) or cell < 0 or cell >= 16:
            return None
        if not _integer(count) or count < 0:
            return None
        result[cell] = int(count)
    return result


def _reward_map(value: Any) -> dict[int, float] | None:
    if not isinstance(value, dict) or not value:
        return None
    result: dict[int, float] = {}
    for key, reward in value.items():
        try:
            cell = int(key)
        except (TypeError, ValueError):
            return None
        if str(cell) != str(key) or cell < 0 or cell >= 16:
            return None
        if not _finite_number(reward):
            return None
        result[cell] = float(reward)
    return result


def _visit_vector(value: Any) -> list[int] | None:
    if not isinstance(value, list) or len(value) != 16:
        return None
    if any(not _integer(item) or item < 0 for item in value):
        return None
    return [int(item) for item in value]


def _unique_best_cell(rewards: dict[int, float]) -> int | None:
    best_reward = max(rewards.values())
    cells = [cell for cell, reward in rewards.items() if reward == best_reward]
    return cells[0] if len(cells) == 1 else None


def build_synthetic_archive(
    rewards: dict[int, float], visits: list[int]
) -> QDArchive:
    archive = QDArchive(grid_shape=GRID_SHAPE)
    for sequence, cell in enumerate(sorted(rewards)):
        reward = float(rewards[cell])
        archive.entries[cell] = QDArchiveEntry(
            action=torch.tensor([float(cell)], dtype=torch.float32),
            reward=reward,
            cost=-reward,
            descriptor_xy_m=torch.tensor(
                [float(cell % 4), float(cell // 4)], dtype=torch.float32
            ),
            fingerprint=f"synthetic-cell-{cell:02d}",
            source_iter=-1,
            parent_cell_id=None,
            insert_sequence=sequence,
        )
    archive.cumulative_visits = torch.tensor(visits, dtype=torch.long)
    return archive


def reconstruct_transition(
    *,
    rewards: dict[int, float],
    visits: list[int],
    observed_slots: dict[int, int],
    episode: int,
    global_step: int,
    iter_idx: int,
) -> dict[str, Any]:
    occupied = set(rewards)
    if set(observed_slots) != occupied:
        raise ValueError("observed slot cells do not equal occupied reward cells")
    if sum(observed_slots.values()) != 16:
        raise ValueError("observed slots do not sum to 16")
    if any((visits[cell] <= 0) for cell in occupied):
        raise ValueError("occupied cell has nonpositive cumulative visits")
    if any(visits[cell] != 0 for cell in set(range(16)) - occupied):
        raise ValueError("unoccupied cell has nonzero cumulative visits")
    best_cell = _unique_best_cell(rewards)
    if best_cell is None:
        raise ValueError("maximum reward is not unique")

    archive = build_synthetic_archive(rewards, visits)
    baseline = allocate_parent_slots(
        archive,
        population_size=16,
        sampling="sparse_priority",
        sparse_exponent=SPARSE_EXPONENT,
        run_seed=RUN_SEED,
        episode=episode,
        global_step=global_step,
        iter_idx=iter_idx,
    )
    baseline_slots = {int(cell): int(count) for cell, count in baseline.slot_counts.items()}

    sparse = allocate_parent_slots(
        archive,
        population_size=15,
        sampling="sparse_priority",
        sparse_exponent=SPARSE_EXPONENT,
        run_seed=RUN_SEED,
        episode=episode,
        global_step=global_step,
        iter_idx=iter_idx,
    )
    sparse_slots = {int(cell): int(count) for cell, count in sparse.slot_counts.items()}
    candidate_slots = dict(sparse_slots)
    candidate_slots[best_cell] += 1
    baseline_covered = sum(count > 0 for count in baseline_slots.values())
    candidate_covered = sum(count > 0 for count in candidate_slots.values())
    return {
        "global_best_cell": best_cell,
        "global_best_reward": rewards[best_cell],
        "observed_slots": observed_slots,
        "baseline_slots": baseline_slots,
        "baseline_exact_match": baseline_slots == observed_slots,
        "baseline_global_best_slots": baseline_slots[best_cell],
        "candidate_dedicated_anchor_slots": 1,
        "candidate_sparse_slots": sparse_slots,
        "candidate_total_slots": candidate_slots,
        "candidate_sparse_slot_sum": sum(sparse_slots.values()),
        "candidate_total_slot_sum": sum(candidate_slots.values()),
        "candidate_global_best_slots": candidate_slots[best_cell],
        "baseline_covered_cells": baseline_covered,
        "candidate_covered_cells": candidate_covered,
        "coverage_retention": (
            float(candidate_covered / baseline_covered) if baseline_covered else None
        ),
    }


def _read_rows(spec: InputSpec) -> list[dict[str, Any]]:
    if sha256_file(spec.path) != spec.sha256:
        raise ValueError(f"input checksum mismatch: {spec.path}")
    rows: list[dict[str, Any]] = []
    with spec.path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{spec.path}:{line_number} is not an object")
            rows.append(row)
    if len(rows) != spec.row_count:
        raise ValueError(f"input row-count mismatch: {spec.path}")
    return rows


def analyze(
    *,
    inputs: list[InputSpec],
    core_qd: Path,
    core_qd_sha256: str,
    design: Path,
    design_sha256: str,
) -> dict[str, Any]:
    if sha256_file(core_qd) != core_qd_sha256:
        raise ValueError("production QD source checksum mismatch")
    if sha256_file(design) != design_sha256:
        raise ValueError("v3 design checksum mismatch")
    torch_rng_before = torch.random.get_rng_state().clone()
    exclusions: Counter[str] = Counter()
    records: list[dict[str, Any]] = []
    input_records: list[dict[str, Any]] = []

    for spec in inputs:
        rows = _read_rows(spec)
        input_records.append(
            {
                "path": str(spec.path.resolve()),
                "sha256": spec.sha256,
                "row_count": spec.row_count,
            }
        )
        for row_index, row in enumerate(rows):
            rewards_by_iter = row.get("qd_per_cell_elite_reward_by_iter")
            visits_by_iter = row.get("qd_cumulative_cell_visits_by_iter")
            slots_by_iter = row.get("qd_parent_slots_by_cell_by_iter")
            if not all(
                isinstance(value, list)
                for value in (rewards_by_iter, visits_by_iter, slots_by_iter)
            ):
                exclusions["missing_iteration_series"] += 1
                continue
            task_id = row.get("task_id")
            episode = row.get("episode")
            global_step = row.get("global_step")
            if not all(_integer(value) for value in (task_id, episode, global_step)):
                exclusions["invalid_coordinates"] += 1
                continue
            for iter_idx in range(1, 10):
                if any(
                    len(value) <= iter_idx
                    for value in (rewards_by_iter, visits_by_iter, slots_by_iter)
                ):
                    exclusions["short_iteration_series"] += 1
                    continue
                rewards = _reward_map(rewards_by_iter[iter_idx - 1])
                visits = _visit_vector(visits_by_iter[iter_idx - 1])
                observed = _slot_map(slots_by_iter[iter_idx])
                if rewards is None or visits is None or observed is None:
                    exclusions["invalid_transition_fields"] += 1
                    continue
                if _unique_best_cell(rewards) is None:
                    exclusions["nonunique_maximum_reward"] += 1
                    continue
                try:
                    result = reconstruct_transition(
                        rewards=rewards,
                        visits=visits,
                        observed_slots=observed,
                        episode=int(episode),
                        global_step=int(global_step),
                        iter_idx=iter_idx,
                    )
                except ValueError as exc:
                    exclusions[f"invalid:{exc}"] += 1
                    continue
                records.append(
                    {
                        "source_path": str(spec.path.resolve()),
                        "source_row_index": row_index,
                        "source_row_sha256": canonical_sha256(row),
                        "task_id": int(task_id),
                        "episode": int(episode),
                        "global_step": int(global_step),
                        "iter_idx": iter_idx,
                        **result,
                    }
                )

    torch_rng_unchanged = torch.equal(torch_rng_before, torch.random.get_rng_state())
    by_task: dict[int, dict[str, int | float]] = {}
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[int(record["task_id"])].append(record)
    for task_id, task_records in sorted(grouped.items()):
        omissions = sum(
            int(record["baseline_global_best_slots"] == 0)
            for record in task_records
        )
        by_task[task_id] = {
            "valid_transitions": len(task_records),
            "baseline_global_best_zero_slot_count": omissions,
            "baseline_global_best_zero_slot_ratio": omissions / len(task_records),
        }

    valid_count = len(records)
    baseline_exact = sum(int(record["baseline_exact_match"]) for record in records)
    baseline_omissions = sum(
        int(record["baseline_global_best_slots"] == 0) for record in records
    )
    candidate_omissions = sum(
        int(record["candidate_global_best_slots"] == 0) for record in records
    )
    retention_values = sorted(
        float(record["coverage_retention"])
        for record in records
        if record["coverage_retention"] is not None
    )
    median_retention = (
        retention_values[len(retention_values) // 2]
        if len(retention_values) % 2 == 1
        else (
            retention_values[len(retention_values) // 2 - 1]
            + retention_values[len(retention_values) // 2]
        )
        / 2.0
        if retention_values
        else None
    )
    tasks_over_gate = sum(
        int(
            int(values["valid_transitions"]) >= 20
            and float(values["baseline_global_best_zero_slot_ratio"]) >= 0.20
        )
        for values in by_task.values()
    )
    all_candidate_accounting = all(
        record["candidate_dedicated_anchor_slots"] == 1
        and record["candidate_sparse_slot_sum"] == 15
        and record["candidate_total_slot_sum"] == 16
        and record["candidate_global_best_slots"] >= 1
        for record in records
    )
    gates = {
        "minimum_300_valid_transitions": valid_count >= 300,
        "minimum_3_tasks": len(by_task) >= 3,
        "baseline_reconstruction_exact": valid_count > 0 and baseline_exact == valid_count,
        "baseline_omission_ratio_at_least_0_25": (
            valid_count > 0 and baseline_omissions / valid_count >= 0.25
        ),
        "minimum_two_tasks_over_omission_gate": tasks_over_gate >= 2,
        "candidate_one_plus_fifteen_accounting": (
            valid_count > 0 and all_candidate_accounting
        ),
        "candidate_zero_global_best_omissions": (
            valid_count > 0 and candidate_omissions == 0
        ),
        "median_coverage_retention_at_least_0_85": (
            median_retention is not None and median_retention >= 0.85
        ),
        "torch_global_rng_unchanged": torch_rng_unchanged,
    }
    payload: dict[str, Any] = {
        "schema_version": 1,
        "experiment_id": "run_030_global_quality_anchor_diagnostic",
        "hypothesis_id": "H4-v3",
        "analysis_mode": "read_only_zero_episode_production_allocator_reconstruction",
        "inputs": input_records,
        "production_qd_source": {
            "path": str(core_qd.resolve()),
            "sha256": core_qd_sha256,
        },
        "v3_design": {
            "path": str(design.resolve()),
            "sha256": design_sha256,
        },
        "frozen_allocator": {
            "run_seed": RUN_SEED,
            "sparse_exponent": SPARSE_EXPONENT,
            "baseline_population_size": 16,
            "candidate_dedicated_anchor_slots": 1,
            "candidate_sparse_slots": 15,
        },
        "metrics": {
            "valid_transition_count": valid_count,
            "task_count": len(by_task),
            "by_task": by_task,
            "baseline_exact_reconstruction_count": baseline_exact,
            "baseline_global_best_zero_slot_count": baseline_omissions,
            "baseline_global_best_zero_slot_ratio": (
                baseline_omissions / valid_count if valid_count else None
            ),
            "candidate_global_best_zero_slot_count": candidate_omissions,
            "coverage_retention_median": median_retention,
            "tasks_over_omission_gate": tasks_over_gate,
            "excluded_transition_counts": dict(sorted(exclusions.items())),
        },
        "online_feature_exclusions": [
            "future observations",
            "episode success",
            "environment evaluator state",
            "task identity as allocator input",
            "validation outcome",
            "formal outcome",
        ],
        "records": records,
        "gates": gates,
        "passed": all(gates.values()),
        "online_episode_attempts": 0,
        "gpu_hours": 0.0,
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    payload["credential_match_count"] = sum(
        len(pattern.findall(serialized)) for pattern in SECRET_PATTERNS
    )
    if payload["credential_match_count"]:
        raise RuntimeError("strict credential scan failed")
    payload["analysis_sha256"] = canonical_sha256(payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        action="append",
        nargs=3,
        metavar=("PATH", "SHA256", "ROWS"),
        required=True,
    )
    parser.add_argument("--core-qd", type=Path, required=True)
    parser.add_argument("--core-qd-sha256", required=True)
    parser.add_argument("--design", type=Path, required=True)
    parser.add_argument("--design-sha256", required=True)
    parser.add_argument("--owned-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    owned_root = args.owned_root.resolve()
    output = args.output.resolve()
    try:
        output.relative_to(owned_root)
    except ValueError as exc:
        raise ValueError("output must be below the owned artifact root") from exc
    specs = [
        InputSpec(Path(path).resolve(), sha256, int(rows))
        for path, sha256, rows in args.input
    ]
    payload = analyze(
        inputs=specs,
        core_qd=args.core_qd.resolve(),
        core_qd_sha256=args.core_qd_sha256,
        design=args.design.resolve(),
        design_sha256=args.design_sha256,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.chmod(output, 0o444)
    print(
        json.dumps(
            {
                "output": str(output),
                "passed": payload["passed"],
                "analysis_sha256": payload["analysis_sha256"],
                "valid_transitions": payload["metrics"]["valid_transition_count"],
                "baseline_omission_ratio": payload["metrics"][
                    "baseline_global_best_zero_slot_ratio"
                ],
                "coverage_retention_median": payload["metrics"][
                    "coverage_retention_median"
                ],
            },
            sort_keys=True,
        )
    )
    return 0 if payload["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
