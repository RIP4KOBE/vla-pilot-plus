#!/usr/bin/env python3
"""Run041 replay for an exact quality lane plus non-evicting secondary lane."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch


REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_SCRIPT = REPO_ROOT / "scripts/eds_qd_within_cell_aliasing_diagnostic.py"
BASE_SPEC = importlib.util.spec_from_file_location("run040_aliasing_replay", BASE_SCRIPT)
assert BASE_SPEC is not None and BASE_SPEC.loader is not None
base = importlib.util.module_from_spec(BASE_SPEC)
sys.modules[BASE_SPEC.name] = base
BASE_SPEC.loader.exec_module(base)

EXPECTED_ALIAS = {
    "candidate_stream_count": 264,
    "candidate_count": 4224,
    "colliding_cell_count": 1019,
    "candidates_in_colliding_cells": 2750,
    "collision_candidate_ratio": 0.6510416666666666,
    "top_two_direction_distance_median": 0.3616701662540436,
    "top_two_shape_distance_median": 0.2500861983348702,
    "top_two_reward_gap_median": 0.0126953125,
}


@dataclass(frozen=True)
class ProtectedParentAllocation:
    parent_fingerprints: tuple[str, ...]
    total_cell_counts: dict[int, int]
    sparse_cell_counts: dict[int, int]
    secondary_sparse_slots: int
    anchor_fingerprint: str
    final_fingerprint: str


class ProtectedArchive:
    def __init__(self) -> None:
        self.quality = base.ReplayArchive(capacity=1)
        self.secondary: dict[int, base.ReplayEntry] = {}

    def _all_entries(self) -> list[base.ReplayEntry]:
        return [
            *[entry for entries in self.quality.entries.values() for entry in entries],
            *self.secondary.values(),
        ]

    def _select_secondary(
        self, *, pool: list[base.ReplayEntry], bounds: base.QDBounds
    ) -> None:
        grouped: dict[int, list[base.ReplayEntry]] = {}
        if pool:
            assigned = base._cell_ids(
                torch.stack([entry.descriptor for entry in pool]), bounds
            )
            for entry, cell in zip(pool, assigned, strict=True):
                grouped.setdefault(cell, []).append(entry)
        selected: dict[int, base.ReplayEntry] = {}
        for cell, quality_entries in sorted(self.quality.entries.items()):
            quality = quality_entries[0]
            alternatives = [
                entry
                for entry in grouped.get(cell, [])
                if entry.fingerprint != quality.fingerprint
            ]
            if alternatives:
                selected[cell] = base._sort_unique(alternatives, 1)[0]
        self.secondary = selected

    def update(
        self,
        *,
        entries: list[base.ReplayEntry],
        cell_ids: list[int],
        bounds: base.QDBounds,
    ) -> base.ReplayUpdateSummary:
        pool = [*self._all_entries(), *entries]
        summary = self.quality.update(entries=entries, cell_ids=cell_ids)
        self._select_secondary(pool=pool, bounds=bounds)
        return summary

    def rebin(self, *, bounds: base.QDBounds) -> base.ReplayRebinSummary:
        pool = self._all_entries()
        targets = {
            entry.fingerprint: base._cell_ids(
                entry.descriptor.reshape(1, 2), bounds
            )[0]
            for entry in [
                entry
                for entries in self.quality.entries.values()
                for entry in entries
            ]
        }
        summary = self.quality.rebin(entry_target_cells=targets)
        self._select_secondary(pool=pool, bounds=bounds)
        return summary


def allocate_protected_parents(
    archive: ProtectedArchive,
    *,
    run_seed: int,
    episode: int,
    global_step: int,
    iter_idx: int,
) -> ProtectedParentAllocation:
    quality_allocation = base.allocate_top2_parents(
        archive.quality,
        run_seed=run_seed,
        episode=episode,
        global_step=global_step,
        iter_idx=iter_idx,
    )
    anchor_cell, _, anchor_entry = archive.quality.global_best()
    fingerprints = [anchor_entry.fingerprint]
    secondary_slots = 0
    for cell in sorted(quality_allocation.sparse_cell_counts):
        count = int(quality_allocation.sparse_cell_counts[cell])
        options = [archive.quality.entries[cell][0]]
        if cell in archive.secondary:
            options.append(archive.secondary[cell])
        start = base._rotation_start(
            run_seed=run_seed,
            episode=episode,
            global_step=global_step,
            iter_idx=iter_idx,
            cell=cell,
            size=len(options),
        )
        for offset in range(count):
            slot = (start + offset) % len(options)
            fingerprints.append(options[slot].fingerprint)
            secondary_slots += int(slot == 1)
    if len(fingerprints) != 16 or fingerprints[0] != archive.quality.entries[anchor_cell][0].fingerprint:
        raise RuntimeError("protected parent accounting failed")
    return ProtectedParentAllocation(
        parent_fingerprints=tuple(fingerprints),
        total_cell_counts=quality_allocation.total_cell_counts,
        sparse_cell_counts=quality_allocation.sparse_cell_counts,
        secondary_sparse_slots=secondary_slots,
        anchor_fingerprint=anchor_entry.fingerprint,
        final_fingerprint=archive.quality.global_best()[2].fingerprint,
    )


def _quality_identity(
    comparator: base.ReplayArchive, candidate: ProtectedArchive
) -> bool:
    if set(comparator.entries) != set(candidate.quality.entries):
        return False
    for cell in comparator.entries:
        left = comparator.entries[cell][0]
        right = candidate.quality.entries[cell][0]
        if left.fingerprint != right.fingerprint or left.reward != right.reward:
            return False
    return torch.equal(comparator.visits, candidate.quality.visits)


def _secondary_violations(candidate: ProtectedArchive) -> list[str]:
    violations: list[str] = []
    if not set(candidate.secondary).issubset(set(candidate.quality.entries)):
        violations.append("secondary_cell_without_quality")
    for cell, secondary in candidate.secondary.items():
        if secondary.fingerprint == candidate.quality.entries[cell][0].fingerprint:
            violations.append("secondary_duplicates_quality")
    return violations


def analyze_trace(spec: base.InputSpec) -> dict[str, Any]:
    alias = base.analyze_trace(spec)
    trace = torch.load(spec.path, map_location="cpu", weights_only=False)
    metadata = trace["metadata"]
    qd = trace["qd_info"]
    streams = {int(record["iter_idx"]): record for record in qd["shadow_qd_candidate_stream"]}
    stages: dict[int, dict[str, Any]] = {}
    for stage in trace["stages"]:
        if stage.get("stage") == "initial":
            stages[-1] = stage
        elif stage.get("stage") == "full_process_after_rollout":
            stages[int(stage["iter_idx"])] = stage
    comparator = base.ReplayArchive(capacity=1)
    candidate = ProtectedArchive()
    episode = int(metadata["episode"])
    global_step = int(metadata["global_step"])
    quality_mismatches: list[str] = []
    allocation_mismatches: list[str] = []
    secondary_violations: list[str] = []
    secondary_slots = sparse_slots = 0
    allocation_count = 0
    coverage_retention: list[float] = []
    secondary_cell_snapshots = 0
    quality_cell_snapshots = 0

    for iter_idx in range(-1, 10):
        if iter_idx >= 0:
            comparator_allocation = base.allocate_top2_parents(
                comparator,
                run_seed=base.RUN_SEED,
                episode=episode,
                global_step=global_step,
                iter_idx=iter_idx,
            )
            candidate_allocation = allocate_protected_parents(
                candidate,
                run_seed=base.RUN_SEED,
                episode=episode,
                global_step=global_step,
                iter_idx=iter_idx,
            )
            if (
                comparator_allocation.total_cell_counts
                != candidate_allocation.total_cell_counts
            ):
                allocation_mismatches.append(f"iter{iter_idx}:cell_counts")
            if sum(candidate_allocation.total_cell_counts.values()) != 16:
                allocation_mismatches.append(f"iter{iter_idx}:total")
            comparator_covered = sum(
                count > 0 for count in comparator_allocation.total_cell_counts.values()
            )
            candidate_covered = sum(
                count > 0 for count in candidate_allocation.total_cell_counts.values()
            )
            coverage_retention.append(candidate_covered / comparator_covered)
            if (
                candidate_allocation.anchor_fingerprint
                != comparator.global_best()[2].fingerprint
                or candidate_allocation.final_fingerprint
                != comparator.global_best()[2].fingerprint
            ):
                allocation_mismatches.append(f"iter{iter_idx}:anchor_or_final")
            allocation_count += 1
            sparse_slots += 15
            secondary_slots += candidate_allocation.secondary_sparse_slots

        entries, _ = base._entries(stage=stages[iter_idx], record=streams[iter_idx])
        bounds = base._bounds(
            qd["qd_bounds_xy_m"]
            if iter_idx == -1
            else qd["qd_bounds_xy_m_by_iter"][iter_idx]
        )
        assigned = base._cell_ids(
            torch.stack([entry.descriptor for entry in entries]), bounds
        )
        if iter_idx >= 0 and bool(qd["qd_bounds_expanded_by_iter"][iter_idx]):
            comparator_targets = {
                entry.fingerprint: base._cell_ids(
                    entry.descriptor.reshape(1, 2), bounds
                )[0]
                for values in comparator.entries.values()
                for entry in values
            }
            comparator.rebin(entry_target_cells=comparator_targets)
            candidate.rebin(bounds=bounds)
            if not _quality_identity(comparator, candidate):
                quality_mismatches.append(f"iter{iter_idx}:rebin")

        visits = torch.bincount(torch.tensor(assigned), minlength=base.CELL_COUNT)
        comparator.visits += visits
        candidate.quality.visits += visits
        comparator.update(entries=entries, cell_ids=assigned)
        candidate.update(entries=entries, cell_ids=assigned, bounds=bounds)
        if not _quality_identity(comparator, candidate):
            quality_mismatches.append(f"iter{iter_idx}:update")
        secondary_violations.extend(
            f"iter{iter_idx}:{violation}"
            for violation in _secondary_violations(candidate)
        )
        quality_cell_snapshots += len(candidate.quality.entries)
        secondary_cell_snapshots += len(candidate.secondary)

    return {
        "path": str(spec.path),
        "sha256": spec.sha256,
        "task_id": int(metadata["task_id"]),
        "episode": episode,
        "global_step": global_step,
        "candidate_stream_count": alias["streams"],
        "candidate_count": alias["candidates"],
        "colliding_cell_count": alias["colliding_cells"],
        "candidates_in_colliding_cells": alias["colliding_candidates"],
        "top_two_direction_distances": alias["top_two_direction_distances"],
        "top_two_shape_distances": alias["top_two_shape_distances"],
        "top_two_reward_gaps": alias["top_two_reward_gaps"],
        "capacity_one_mismatches": alias["capacity_one_mismatches"],
        "quality_mismatches": quality_mismatches,
        "allocation_mismatches": allocation_mismatches,
        "secondary_violations": secondary_violations,
        "allocation_count": allocation_count,
        "sparse_slots": sparse_slots,
        "secondary_slots": secondary_slots,
        "coverage_retention": coverage_retention,
        "quality_cell_snapshots": quality_cell_snapshots,
        "secondary_cell_snapshots": secondary_cell_snapshots,
    }


def analyze(
    *,
    input_manifest: Path,
    parent_analyzer: Path,
    parent_analyzer_sha256: str,
    core_qd: Path,
    core_qd_sha256: str,
    core_rdt: Path,
    core_rdt_sha256: str,
    design: Path,
    design_sha256: str,
) -> dict[str, Any]:
    bindings = (
        (input_manifest, "2cd1f8249daebbbba69b650b5a61c89c879fa6605177f151bff4edaea7fb96e2", "input manifest"),
        (parent_analyzer, parent_analyzer_sha256, "parent analyzer"),
        (core_qd, core_qd_sha256, "production QD"),
        (core_rdt, core_rdt_sha256, "production RDT"),
        (design, design_sha256, "v5 design"),
    )
    for path, expected, label in bindings:
        if base.sha256_file(path) != expected:
            raise ValueError(f"{label} checksum mismatch")
    torch_before = torch.random.get_rng_state().clone()
    python_before = random.getstate()
    _, specs = base.load_input_specs(input_manifest)
    results = [analyze_trace(spec) for spec in specs]

    def flatten(key: str) -> list[float]:
        return [value for result in results for value in result[key]]

    candidate_streams = sum(result["candidate_stream_count"] for result in results)
    candidates = sum(result["candidate_count"] for result in results)
    colliding_cells = sum(result["colliding_cell_count"] for result in results)
    colliding_candidates = sum(
        result["candidates_in_colliding_cells"] for result in results
    )
    sparse_slots = sum(result["sparse_slots"] for result in results)
    secondary_slots = sum(result["secondary_slots"] for result in results)
    metrics = {
        "trace_count": len(results),
        "candidate_stream_count": candidate_streams,
        "candidate_count": candidates,
        "colliding_cell_count": colliding_cells,
        "candidates_in_colliding_cells": colliding_candidates,
        "collision_candidate_ratio": colliding_candidates / candidates,
        "top_two_direction_distance_median": base._median(
            flatten("top_two_direction_distances")
        ),
        "top_two_shape_distance_median": base._median(
            flatten("top_two_shape_distances")
        ),
        "top_two_reward_gap_median": base._median(flatten("top_two_reward_gaps")),
        "capacity_one_mismatch_count": sum(
            len(result["capacity_one_mismatches"]) for result in results
        ),
        "protected_quality_mismatch_count": sum(
            len(result["quality_mismatches"]) for result in results
        ),
        "allocation_mismatch_count": sum(
            len(result["allocation_mismatches"]) for result in results
        ),
        "secondary_violation_count": sum(
            len(result["secondary_violations"]) for result in results
        ),
        "allocation_count": sum(result["allocation_count"] for result in results),
        "sparse_slot_count": sparse_slots,
        "secondary_sparse_slot_count": secondary_slots,
        "secondary_sparse_slot_ratio": secondary_slots / sparse_slots,
        "coverage_retention_median": base._median(flatten("coverage_retention")),
        "quality_cell_snapshots": sum(
            result["quality_cell_snapshots"] for result in results
        ),
        "secondary_cell_snapshots": sum(
            result["secondary_cell_snapshots"] for result in results
        ),
    }
    alias_reproduced = all(
        metrics[key] == expected for key, expected in EXPECTED_ALIAS.items()
    )
    gates = {
        "input_and_source_bindings_exact": len(specs) == 24,
        "run040_alias_metrics_exact": alias_reproduced,
        "capacity_one_saved_replay_exact": metrics["capacity_one_mismatch_count"] == 0,
        "protected_quality_identity_exact": metrics["protected_quality_mismatch_count"] == 0,
        "allocation_and_anchor_final_identity_exact": metrics["allocation_mismatch_count"] == 0,
        "secondary_role_integrity": metrics["secondary_violation_count"] == 0,
        "all_240_allocations_observed": metrics["allocation_count"] == 240,
        "secondary_sparse_ratio_at_least_0_20": metrics["secondary_sparse_slot_ratio"] >= 0.20,
        "coverage_retention_exactly_1": metrics["coverage_retention_median"] == 1.0,
        "torch_global_rng_unchanged": torch.equal(torch_before, torch.random.get_rng_state()),
        "python_global_rng_unchanged": python_before == random.getstate(),
    }
    payload: dict[str, Any] = {
        "schema_version": 1,
        "experiment_id": "run_041_protected_quality_lane_diagnostic",
        "hypothesis_id": "H5-v5",
        "analysis_mode": "read_only_zero_episode_protected_quality_secondary_replay",
        "source_bindings": {
            label: {"path": str(path.resolve()), "sha256": expected}
            for path, expected, label in bindings
        },
        "frozen_mechanism": {
            "quality": "capacity_one_exact",
            "secondary_per_quality_cell": 1,
            "secondary_visits": 0,
            "secondary_can_create_cell": False,
            "secondary_can_evict_quality": False,
            "secondary_can_anchor_or_execute": False,
            "parent_allocation": "one_quality_anchor_plus_production_sparse15_then_stateless_within_cell_rotation",
        },
        "metrics": metrics,
        "traces": [
            {
                key: value
                for key, value in result.items()
                if key
                not in {
                    "top_two_direction_distances",
                    "top_two_shape_distances",
                    "top_two_reward_gaps",
                    "coverage_retention",
                }
            }
            for result in results
        ],
        "gates": gates,
        "passed": all(gates.values()),
        "online_episode_attempts": 0,
        "gpu_hours": 0.0,
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    payload["credential_match_count"] = sum(
        len(pattern.findall(serialized)) for pattern in base.SECRET_PATTERNS
    )
    if payload["credential_match_count"]:
        raise RuntimeError("strict credential scan failed")
    payload["analysis_sha256"] = base.canonical_sha256(payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--parent-analyzer", type=Path, required=True)
    parser.add_argument("--parent-analyzer-sha256", required=True)
    parser.add_argument("--core-qd", type=Path, required=True)
    parser.add_argument("--core-qd-sha256", required=True)
    parser.add_argument("--core-rdt", type=Path, required=True)
    parser.add_argument("--core-rdt-sha256", required=True)
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
    payload = analyze(
        input_manifest=args.input_manifest.resolve(),
        parent_analyzer=args.parent_analyzer.resolve(),
        parent_analyzer_sha256=args.parent_analyzer_sha256,
        core_qd=args.core_qd.resolve(),
        core_qd_sha256=args.core_qd_sha256,
        core_rdt=args.core_rdt.resolve(),
        core_rdt_sha256=args.core_rdt_sha256,
        design=args.design.resolve(),
        design_sha256=args.design_sha256,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.chmod(output, 0o444)
    print(json.dumps({"output": str(output), "passed": payload["passed"], "analysis_sha256": payload["analysis_sha256"], **payload["metrics"]}, sort_keys=True))
    return 0 if payload["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
