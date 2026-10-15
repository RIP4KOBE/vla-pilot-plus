#!/usr/bin/env python3
"""Read-only Run040 replay for endpoint-XY within-cell aliasing."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import torch
from torch import Tensor

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.qd_ed import (  # noqa: E402
    QDArchive,
    QDArchiveEntry,
    QDBounds,
    allocate_parent_slots,
    cell_ids as production_cell_ids,
    fingerprint_action,
)


GRID_SHAPE = (4, 4)
CELL_COUNT = 16
RUN_SEED = 0
PATH_EPSILON = 1.0e-6
SECRET_PATTERNS = (
    re.compile(r"sk-poe-[A-Za-z0-9_-]{12,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
)


@dataclass(frozen=True)
class InputSpec:
    path: Path
    size_bytes: int
    sha256: str
    streams: int


@dataclass(frozen=True)
class ReplayEntry:
    action: Tensor
    reward: float
    cost: float
    descriptor: Tensor
    fingerprint: str


@dataclass(frozen=True)
class ReplayUpdateSummary:
    insertions: int
    replacements: int
    rejections: int
    total: int
    accepted_fingerprints: tuple[str, ...]


@dataclass(frozen=True)
class ReplayRebinSummary:
    occupied_before: int
    occupied_after: int
    collisions: int
    visit_sum_before: int
    visit_sum_after: int


@dataclass(frozen=True)
class Top2ParentAllocation:
    parent_fingerprints: tuple[str, ...]
    total_cell_counts: dict[int, int]
    sparse_cell_counts: dict[int, int]
    anchor_count: int
    sparse_count: int
    secondary_sparse_slots: int


@dataclass(frozen=True)
class CollisionMetrics:
    colliding_cells: int
    colliding_candidates: int
    top_two_direction_distances: list[float]
    top_two_shape_distances: list[float]
    top_two_reward_gaps: list[float]


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


def _finite_tensor(value: Any, *, name: str, shape0: int | None = None) -> Tensor:
    if not torch.is_tensor(value) or not bool(torch.isfinite(value).all().item()):
        raise ValueError(f"{name} must be a finite tensor")
    if shape0 is not None and (value.ndim == 0 or value.shape[0] != shape0):
        raise ValueError(f"{name} has the wrong candidate count")
    return value.detach().cpu()


def _finite_floats(values: Any, *, name: str, count: int) -> list[float]:
    if not isinstance(values, list) or len(values) != count:
        raise ValueError(f"{name} has the wrong candidate count")
    result: list[float] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} contains a nonnumber")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"{name} contains a nonfinite value")
        result.append(number)
    return result


def _sort_unique(entries: Iterable[ReplayEntry], capacity: int) -> list[ReplayEntry]:
    by_fingerprint: dict[str, ReplayEntry] = {}
    for entry in entries:
        prior = by_fingerprint.get(entry.fingerprint)
        if prior is None or (-entry.reward, entry.fingerprint) < (
            -prior.reward,
            prior.fingerprint,
        ):
            by_fingerprint[entry.fingerprint] = entry
    return sorted(
        by_fingerprint.values(), key=lambda entry: (-entry.reward, entry.fingerprint)
    )[:capacity]


class ReplayArchive:
    def __init__(self, *, capacity: int) -> None:
        if capacity not in {1, 2}:
            raise ValueError("replay capacity must be 1 or 2")
        self.capacity = capacity
        self.entries: dict[int, list[ReplayEntry]] = {}
        self.visits = torch.zeros(CELL_COUNT, dtype=torch.long)

    def quality_entries(self) -> dict[int, ReplayEntry]:
        return {cell: entries[0] for cell, entries in sorted(self.entries.items())}

    def global_best(self) -> tuple[int, int, ReplayEntry]:
        candidates = [
            (cell, slot, entry)
            for cell, entries in self.entries.items()
            for slot, entry in enumerate(entries)
        ]
        if not candidates:
            raise RuntimeError("replay archive is empty")
        return min(
            candidates,
            key=lambda item: (
                -item[2].reward,
                item[2].fingerprint,
                item[0],
                item[1],
            ),
        )

    def update(
        self, *, entries: list[ReplayEntry], cell_ids: list[int]
    ) -> ReplayUpdateSummary:
        if len(entries) != len(cell_ids) or not entries:
            raise ValueError("replay update fields must be nonempty and aligned")
        grouped: dict[int, list[ReplayEntry]] = defaultdict(list)
        for entry, cell in zip(entries, cell_ids, strict=True):
            if cell < 0 or cell >= CELL_COUNT:
                raise ValueError("replay cell outside 4x4 grid")
            grouped[int(cell)].append(entry)

        insertions = replacements = rejections = 0
        accepted: list[str] = []
        for cell in sorted(grouped):
            candidates = sorted(
                grouped[cell], key=lambda entry: (-entry.reward, entry.fingerprint)
            )
            incumbent = self.entries.get(cell, [])
            if self.capacity == 1:
                winner = candidates[0]
                should_write = not incumbent or (
                    winner.reward > incumbent[0].reward
                    or (
                        winner.reward == incumbent[0].reward
                        and winner.fingerprint < incumbent[0].fingerprint
                    )
                )
                if should_write:
                    insertions += int(not incumbent)
                    replacements += int(bool(incumbent))
                    self.entries[cell] = [winner]
                    accepted.append(winner.fingerprint)
                    rejections += len(candidates) - 1
                else:
                    rejections += len(candidates)
            else:
                kept = _sort_unique([*incumbent, *candidates], self.capacity)
                kept_fingerprints = {entry.fingerprint for entry in kept}
                accepted.extend(
                    entry.fingerprint
                    for entry in candidates
                    if entry.fingerprint in kept_fingerprints
                )
                if not incumbent:
                    insertions += len(kept)
                else:
                    replacements += len(
                        set(entry.fingerprint for entry in kept)
                        - set(entry.fingerprint for entry in incumbent)
                    )
                self.entries[cell] = kept
                rejections += max(0, len(candidates) - len(set(accepted)))
        return ReplayUpdateSummary(
            insertions=insertions,
            replacements=replacements,
            rejections=rejections,
            total=len(entries),
            accepted_fingerprints=tuple(sorted(set(accepted))),
        )

    def rebin(
        self, *, entry_target_cells: dict[str, int]
    ) -> ReplayRebinSummary:
        occupied_before = len(self.entries)
        visit_sum_before = int(self.visits.sum().item())
        remapped_visits = torch.zeros_like(self.visits)
        regrouped: dict[int, list[ReplayEntry]] = defaultdict(list)
        for old_cell in sorted(self.entries):
            old_entries = self.entries[old_cell]
            quality_target = int(entry_target_cells[old_entries[0].fingerprint])
            remapped_visits[quality_target] += self.visits[old_cell]
            for entry in old_entries:
                target = int(entry_target_cells[entry.fingerprint])
                if target < 0 or target >= CELL_COUNT:
                    raise ValueError("rebin target outside 4x4 grid")
                regrouped[target].append(entry)
        self.entries = {
            cell: _sort_unique(entries, self.capacity)
            for cell, entries in sorted(regrouped.items())
        }
        self.visits = remapped_visits
        visit_sum_after = int(self.visits.sum().item())
        if visit_sum_before != visit_sum_after:
            raise RuntimeError("replay rebin failed to preserve visits")
        occupied_after = len(self.entries)
        return ReplayRebinSummary(
            occupied_before=occupied_before,
            occupied_after=occupied_after,
            collisions=occupied_before - occupied_after,
            visit_sum_before=visit_sum_before,
            visit_sum_after=visit_sum_after,
        )


def _production_archive(archive: ReplayArchive) -> QDArchive:
    production = QDArchive(grid_shape=GRID_SHAPE)
    for sequence, (cell, entry) in enumerate(archive.quality_entries().items()):
        production.entries[cell] = QDArchiveEntry(
            action=entry.action,
            reward=entry.reward,
            cost=entry.cost,
            descriptor_xy_m=entry.descriptor,
            fingerprint=entry.fingerprint,
            source_iter=-1,
            parent_cell_id=None,
            insert_sequence=sequence,
        )
    production.cumulative_visits = archive.visits.clone()
    return production


def _rotation_start(
    *, run_seed: int, episode: int, global_step: int, iter_idx: int, cell: int, size: int
) -> int:
    material = f"{run_seed}:{episode}:{global_step}:{iter_idx}:{cell}:top2"
    return int.from_bytes(hashlib.sha256(material.encode("ascii")).digest()[:8], "big") % size


def allocate_top2_parents(
    archive: ReplayArchive,
    *,
    run_seed: int,
    episode: int,
    global_step: int,
    iter_idx: int,
) -> Top2ParentAllocation:
    production = _production_archive(archive)
    allocation = allocate_parent_slots(
        production,
        population_size=16,
        sampling="sparse_priority",
        sparse_exponent=1.0,
        run_seed=run_seed,
        episode=episode,
        global_step=global_step,
        iter_idx=iter_idx,
        global_quality_anchor_count=1,
    )
    anchor_cell = allocation.global_quality_anchor_cell_id
    if anchor_cell is None:
        raise RuntimeError("top2 allocation omitted global anchor")
    fingerprints = [archive.entries[anchor_cell][0].fingerprint]
    secondary = 0
    for cell in sorted(allocation.sparse_slot_counts):
        entries = archive.entries[cell]
        count = int(allocation.sparse_slot_counts[cell])
        start = _rotation_start(
            run_seed=run_seed,
            episode=episode,
            global_step=global_step,
            iter_idx=iter_idx,
            cell=cell,
            size=len(entries),
        )
        for offset in range(count):
            slot = (start + offset) % len(entries)
            fingerprints.append(entries[slot].fingerprint)
            secondary += int(slot == 1)
    if len(fingerprints) != 16:
        raise RuntimeError("top2 allocation did not produce 16 parents")
    return Top2ParentAllocation(
        parent_fingerprints=tuple(fingerprints),
        total_cell_counts={
            int(cell): int(count) for cell, count in allocation.slot_counts.items()
        },
        sparse_cell_counts={
            int(cell): int(count)
            for cell, count in allocation.sparse_slot_counts.items()
        },
        anchor_count=1,
        sparse_count=15,
        secondary_sparse_slots=secondary,
    )


def stream_collision_metrics(
    *,
    trajectories: Tensor,
    rewards: list[float],
    fingerprints: list[str],
    cell_ids: list[int],
) -> CollisionMetrics:
    trajectories = _finite_tensor(trajectories, name="trajectories")
    if trajectories.ndim != 3 or trajectories.shape[-1] < 3:
        raise ValueError("trajectories must have shape (population,time,>=3)")
    count = trajectories.shape[0]
    if not (len(rewards) == len(fingerprints) == len(cell_ids) == count):
        raise ValueError("collision fields are not aligned")
    xyz = trajectories[..., :3].float()
    steps = xyz[:, 1:] - xyz[:, :-1]
    path_length = torch.linalg.vector_norm(steps, dim=-1).sum(dim=-1)
    denominator = path_length + PATH_EPSILON
    direction = (xyz[:, -1] - xyz[:, 0]) / denominator[:, None]
    shape = (xyz[:, 1:] - xyz[:, :1]) / denominator[:, None, None]
    horizon = max(int(shape.shape[1]), 1)
    grouped: dict[int, list[int]] = defaultdict(list)
    for index, cell in enumerate(cell_ids):
        grouped[int(cell)].append(index)
    direction_distances: list[float] = []
    shape_distances: list[float] = []
    reward_gaps: list[float] = []
    colliding_candidates = 0
    for indices in grouped.values():
        if len(indices) < 2:
            continue
        colliding_candidates += len(indices)
        ordered = sorted(indices, key=lambda idx: (-rewards[idx], fingerprints[idx]))
        first, second = ordered[:2]
        direction_distances.append(
            0.5 * float(torch.linalg.vector_norm(direction[first] - direction[second]))
        )
        shape_distances.append(
            0.5
            * float(
                torch.linalg.vector_norm((shape[first] - shape[second]).reshape(-1))
            )
            / math.sqrt(horizon)
        )
        reward_gaps.append(float(rewards[first] - rewards[second]))
    return CollisionMetrics(
        colliding_cells=len(direction_distances),
        colliding_candidates=colliding_candidates,
        top_two_direction_distances=direction_distances,
        top_two_shape_distances=shape_distances,
        top_two_reward_gaps=reward_gaps,
    )


def _bounds(value: Any) -> QDBounds:
    tensor = torch.tensor(value, dtype=torch.float32)
    if tensor.shape != (2, 2) or not bool(torch.isfinite(tensor).all().item()):
        raise ValueError("QD bounds must have finite shape (2,2)")
    if not bool(((tensor[1] - tensor[0]) > 0).all().item()):
        raise ValueError("QD bounds spans must be positive")
    return QDBounds(lo=tensor[0], hi=tensor[1], checksum="run040-replay")


def _cell_ids(descriptors: Tensor, bounds: QDBounds) -> list[int]:
    assigned, _ = production_cell_ids(descriptors.float(), bounds, GRID_SHAPE)
    return [int(value) for value in assigned.tolist()]


def _entries(
    *, stage: dict[str, Any], record: dict[str, Any]
) -> tuple[list[ReplayEntry], Tensor]:
    actions = _finite_tensor(stage.get("actions"), name="stage actions", shape0=16)
    trajectories = _finite_tensor(
        stage.get("trajectories"), name="stage trajectories", shape0=16
    )
    costs = _finite_tensor(stage.get("costs"), name="stage costs", shape0=16).reshape(-1)
    rewards = _finite_floats(record.get("rewards"), name="record rewards", count=16)
    descriptors = torch.tensor(record.get("descriptors_xy_m"), dtype=torch.float32)
    if descriptors.shape != (16, 2) or not bool(torch.isfinite(descriptors).all().item()):
        raise ValueError("record descriptors must have finite shape (16,2)")
    fingerprints = record.get("fingerprints")
    if not isinstance(fingerprints, list) or len(fingerprints) != 16:
        raise ValueError("record fingerprints must contain 16 values")
    canonical = [fingerprint_action(action) for action in actions]
    if canonical != fingerprints:
        raise ValueError("trace action fingerprints do not match shadow stream")
    entries = [
        ReplayEntry(
            action=actions[index].clone(),
            reward=rewards[index],
            cost=float(costs[index]),
            descriptor=descriptors[index].clone(),
            fingerprint=str(fingerprints[index]),
        )
        for index in range(16)
    ]
    return entries, trajectories


def load_input_specs(manifest_path: Path) -> tuple[dict[str, Any], list[InputSpec]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = Path(manifest["artifact_root"]).resolve()
    specs: list[InputSpec] = []
    for item in manifest.get("traces", []):
        path = (root / item["path"]).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError("trace path escapes artifact root") from exc
        spec = InputSpec(
            path=path,
            size_bytes=int(item["size_bytes"]),
            sha256=str(item["sha256"]),
            streams=int(item["streams"]),
        )
        if path.stat().st_size != spec.size_bytes:
            raise ValueError(f"input size mismatch: {path}")
        if sha256_file(path) != spec.sha256:
            raise ValueError(f"input checksum mismatch: {path}")
        specs.append(spec)
    if len(specs) != int(manifest["trace_count"]):
        raise ValueError("manifest trace-count mismatch")
    if sum(spec.size_bytes for spec in specs) != int(manifest["total_size_bytes"]):
        raise ValueError("manifest byte-count mismatch")
    if sum(spec.streams for spec in specs) != int(manifest["candidate_stream_count"]):
        raise ValueError("manifest stream-count mismatch")
    return manifest, specs


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    tensor = torch.tensor(values, dtype=torch.float64)
    return float(torch.quantile(tensor, 0.5).item())


def _reward_map(archive: ReplayArchive) -> dict[str, float]:
    return {
        str(cell): float(entry.reward)
        for cell, entry in archive.quality_entries().items()
    }


def _maps_equal(left: dict[str, float], right: Any) -> bool:
    if not isinstance(right, dict) or set(left) != set(right):
        return False
    return all(float(left[key]) == float(right[key]) for key in left)


def analyze_trace(spec: InputSpec) -> dict[str, Any]:
    trace = torch.load(spec.path, map_location="cpu", weights_only=False)
    if not isinstance(trace, dict):
        raise ValueError("mechanism trace must be a dictionary")
    metadata = trace.get("metadata") or {}
    qd = trace.get("qd_info") or {}
    required_qd = (
        qd.get("qd_archive_active_for_chunk") is True
        and qd.get("qd_cell_capacity") == 1
        and qd.get("qd_descriptor") == "target_relative_endpoint_xy"
        and qd.get("qd_grid_shape") == [4, 4]
        and qd.get("qd_bounds_update_policy") == "causal_envelope_v1"
    )
    if not required_qd:
        raise ValueError("trace does not satisfy frozen active-QD profile")
    streams = qd.get("shadow_qd_candidate_stream")
    if not isinstance(streams, list) or len(streams) != spec.streams:
        raise ValueError("trace shadow stream count mismatch")
    by_iter = {int(record["iter_idx"]): record for record in streams}
    if set(by_iter) != set(range(-1, 10)):
        raise ValueError("trace must contain streams -1 and 0..9")
    stages: dict[int, dict[str, Any]] = {}
    for stage in trace.get("stages", []):
        if stage.get("stage") == "initial":
            stages[-1] = stage
        elif stage.get("stage") == "full_process_after_rollout":
            index = int(stage["iter_idx"])
            if index in stages:
                raise ValueError("duplicate aligned trace stage")
            stages[index] = stage
    if set(stages) != set(range(-1, 10)):
        raise ValueError("trace stages do not align with streams")
    episode = int(metadata.get("episode"))
    global_step = int(metadata.get("global_step"))
    bounds_by_iter = qd.get("qd_bounds_xy_m_by_iter")
    expanded_by_iter = qd.get("qd_bounds_expanded_by_iter")
    if not isinstance(bounds_by_iter, list) or len(bounds_by_iter) != 10:
        raise ValueError("trace has invalid per-iteration bounds")
    if not isinstance(expanded_by_iter, list) or len(expanded_by_iter) != 10:
        raise ValueError("trace has invalid bounds expansion flags")

    cap1 = ReplayArchive(capacity=1)
    cap2 = ReplayArchive(capacity=2)
    collision_cells = collision_candidates = candidates = 0
    direction_distances: list[float] = []
    shape_distances: list[float] = []
    reward_gaps: list[float] = []
    capacity_one_mismatches: list[str] = []
    capacity_two_mismatches: list[str] = []
    allocations = 0
    sparse_slots = secondary_slots = 0
    coverage_retention: list[float] = []

    for iter_idx in range(-1, 10):
        if iter_idx >= 0:
            base_allocation = allocate_top2_parents(
                cap1,
                run_seed=RUN_SEED,
                episode=episode,
                global_step=global_step,
                iter_idx=iter_idx,
            )
            top2_allocation = allocate_top2_parents(
                cap2,
                run_seed=RUN_SEED,
                episode=episode,
                global_step=global_step,
                iter_idx=iter_idx,
            )
            baseline_covered = sum(
                count > 0 for count in base_allocation.total_cell_counts.values()
            )
            candidate_covered = sum(
                count > 0 for count in top2_allocation.total_cell_counts.values()
            )
            coverage_retention.append(candidate_covered / baseline_covered)
            allocations += 1
            sparse_slots += top2_allocation.sparse_count
            secondary_slots += top2_allocation.secondary_sparse_slots

        record = by_iter[iter_idx]
        entries, trajectories = _entries(stage=stages[iter_idx], record=record)
        active_bounds = _bounds(
            qd["qd_bounds_xy_m"] if iter_idx == -1 else bounds_by_iter[iter_idx]
        )
        assigned = _cell_ids(
            torch.stack([entry.descriptor for entry in entries]), active_bounds
        )
        collision = stream_collision_metrics(
            trajectories=trajectories,
            rewards=[entry.reward for entry in entries],
            fingerprints=[entry.fingerprint for entry in entries],
            cell_ids=assigned,
        )
        candidates += len(entries)
        collision_cells += collision.colliding_cells
        collision_candidates += collision.colliding_candidates
        direction_distances.extend(collision.top_two_direction_distances)
        shape_distances.extend(collision.top_two_shape_distances)
        reward_gaps.extend(collision.top_two_reward_gaps)

        if iter_idx >= 0 and bool(expanded_by_iter[iter_idx]):
            for archive, label in ((cap1, "cap1"), (cap2, "cap2")):
                targets = {
                    entry.fingerprint: _cell_ids(
                        entry.descriptor.reshape(1, 2), active_bounds
                    )[0]
                    for cell_entries in archive.entries.values()
                    for entry in cell_entries
                }
                summary = archive.rebin(entry_target_cells=targets)
                if label == "cap1":
                    saved_before = int(
                        qd["qd_archive_rebin_visit_sum_before_by_iter"][iter_idx]
                    )
                    saved_after = int(
                        qd["qd_archive_rebin_visit_sum_after_by_iter"][iter_idx]
                    )
                    saved_collisions = int(
                        qd["qd_archive_rebin_collisions_by_iter"][iter_idx]
                    )
                    if (
                        summary.visit_sum_before != saved_before
                        or summary.visit_sum_after != saved_after
                        or summary.collisions != saved_collisions
                    ):
                        capacity_one_mismatches.append(
                            f"iter{iter_idx}:rebin_{label}"
                        )

        visits = torch.bincount(torch.tensor(assigned), minlength=CELL_COUNT)
        cap1.visits += visits
        cap2.visits += visits
        update1 = cap1.update(entries=entries, cell_ids=assigned)
        cap2.update(entries=entries, cell_ids=assigned)

        if iter_idx == -1:
            saved_accounting = qd.get("qd_initial_accounting") or {}
            if len(cap1.entries) != int(qd.get("qd_initial_occupied_cells")):
                capacity_one_mismatches.append("initial:occupied")
        else:
            saved_accounting = {
                "insertions": qd["qd_archive_insertions_by_iter"][iter_idx],
                "replacements": qd["qd_archive_replacements_by_iter"][iter_idx],
                "rejections": qd["qd_archive_rejections_by_iter"][iter_idx],
                "total": 16,
            }
            if len(cap1.entries) != int(qd["qd_occupied_cells_by_iter"][iter_idx]):
                capacity_one_mismatches.append(f"iter{iter_idx}:occupied")
            if not _maps_equal(
                _reward_map(cap1), qd["qd_per_cell_elite_reward_by_iter"][iter_idx]
            ):
                capacity_one_mismatches.append(f"iter{iter_idx}:reward_map")
            saved_best = float(qd["qd_archive_best_reward_by_iter"][iter_idx])
            if cap1.global_best()[2].reward != saved_best:
                capacity_one_mismatches.append(f"iter{iter_idx}:best_reward")
            saved_visits = torch.tensor(
                qd["qd_cumulative_cell_visits_by_iter"][iter_idx], dtype=torch.long
            )
            if not torch.equal(cap1.visits, saved_visits):
                capacity_one_mismatches.append(f"iter{iter_idx}:visits")
        if any(
            int(saved_accounting.get(key, -1)) != int(getattr(update1, key))
            for key in ("insertions", "replacements", "rejections", "total")
        ):
            capacity_one_mismatches.append(f"iter{iter_idx}:update_accounting")

        cap1_quality_fingerprints = {
            entry.fingerprint for entry in cap1.quality_entries().values()
        }
        cap2_fingerprints = {
            entry.fingerprint
            for cell_entries in cap2.entries.values()
            for entry in cell_entries
        }
        if not cap1_quality_fingerprints.issubset(cap2_fingerprints):
            capacity_two_mismatches.append(f"iter{iter_idx}:quality_retention")
        if cap1.global_best()[2].fingerprint != cap2.global_best()[2].fingerprint:
            capacity_two_mismatches.append(f"iter{iter_idx}:global_best_retention")
        if any(
            len(cell_entries) > 2
            or len({entry.fingerprint for entry in cell_entries}) != len(cell_entries)
            for cell_entries in cap2.entries.values()
        ):
            capacity_two_mismatches.append(f"iter{iter_idx}:capacity_or_duplicate")

    return {
        "path": str(spec.path),
        "sha256": spec.sha256,
        "task_id": int(metadata.get("task_id")),
        "episode": episode,
        "global_step": global_step,
        "streams": spec.streams,
        "candidates": candidates,
        "colliding_cells": collision_cells,
        "colliding_candidates": collision_candidates,
        "top_two_direction_distances": direction_distances,
        "top_two_shape_distances": shape_distances,
        "top_two_reward_gaps": reward_gaps,
        "allocation_count": allocations,
        "sparse_slots": sparse_slots,
        "secondary_slots": secondary_slots,
        "coverage_retention": coverage_retention,
        "capacity_one_mismatches": capacity_one_mismatches,
        "capacity_two_mismatches": capacity_two_mismatches,
    }


def summarize_mismatch_counts(trace_results: list[dict[str, Any]]) -> dict[str, int]:
    capacity_one = sum(
        len(result["capacity_one_mismatches"]) for result in trace_results
    )
    capacity_two_retention = sum(
        sum(
            mismatch.endswith(("quality_retention", "global_best_retention"))
            for mismatch in result["capacity_two_mismatches"]
        )
        for result in trace_results
    )
    capacity_two_integrity = sum(
        sum(
            mismatch.endswith("capacity_or_duplicate")
            for mismatch in result["capacity_two_mismatches"]
        )
        for result in trace_results
    )
    return {
        "capacity_one_exact_mismatch_count": capacity_one,
        "capacity_two_retention_mismatch_count": capacity_two_retention,
        "capacity_two_integrity_mismatch_count": capacity_two_integrity,
    }


def analyze(
    *,
    input_manifest: Path,
    core_qd: Path,
    core_qd_sha256: str,
    core_rdt: Path,
    core_rdt_sha256: str,
    design: Path,
    design_sha256: str,
) -> dict[str, Any]:
    for path, expected, label in (
        (core_qd, core_qd_sha256, "production QD source"),
        (core_rdt, core_rdt_sha256, "production RDT source"),
        (design, design_sha256, "v4 design"),
    ):
        if sha256_file(path) != expected:
            raise ValueError(f"{label} checksum mismatch")
    torch_before = torch.random.get_rng_state().clone()
    python_before = random.getstate()
    manifest, specs = load_input_specs(input_manifest)
    trace_results = [analyze_trace(spec) for spec in specs]

    streams = sum(result["streams"] for result in trace_results)
    candidates = sum(result["candidates"] for result in trace_results)
    colliding_cells = sum(result["colliding_cells"] for result in trace_results)
    colliding_candidates = sum(
        result["colliding_candidates"] for result in trace_results
    )
    direction = [
        value
        for result in trace_results
        for value in result["top_two_direction_distances"]
    ]
    shape = [
        value
        for result in trace_results
        for value in result["top_two_shape_distances"]
    ]
    reward_gap = [
        value
        for result in trace_results
        for value in result["top_two_reward_gaps"]
    ]
    coverage = [
        value for result in trace_results for value in result["coverage_retention"]
    ]
    sparse_slots = sum(result["sparse_slots"] for result in trace_results)
    secondary_slots = sum(result["secondary_slots"] for result in trace_results)
    mismatch_counts = summarize_mismatch_counts(trace_results)
    metrics = {
        "trace_count": len(trace_results),
        "candidate_stream_count": streams,
        "candidate_count": candidates,
        "colliding_cell_count": colliding_cells,
        "candidates_in_colliding_cells": colliding_candidates,
        "collision_candidate_ratio": colliding_candidates / candidates,
        "top_two_direction_distance_median": _median(direction),
        "top_two_shape_distance_median": _median(shape),
        "top_two_reward_gap_median": _median(reward_gap),
        **mismatch_counts,
        "allocation_count": sum(result["allocation_count"] for result in trace_results),
        "sparse_slot_count": sparse_slots,
        "secondary_sparse_slot_count": secondary_slots,
        "secondary_sparse_slot_ratio": secondary_slots / sparse_slots,
        "xy_cell_coverage_retention_median": _median(coverage),
    }
    gates = {
        "input_bindings_exact": (
            len(specs) == int(manifest["trace_count"])
            and streams == int(manifest["candidate_stream_count"])
        ),
        "minimum_200_streams": streams >= 200,
        "minimum_3000_candidates": candidates >= 3000,
        "minimum_500_colliding_cells": colliding_cells >= 500,
        "collision_candidate_ratio_at_least_0_40": (
            metrics["collision_candidate_ratio"] >= 0.40
        ),
        "top_two_direction_median_at_least_0_20": (
            metrics["top_two_direction_distance_median"] >= 0.20
        ),
        "top_two_shape_median_at_least_0_15": (
            metrics["top_two_shape_distance_median"] >= 0.15
        ),
        "top_two_reward_gap_median_at_most_0_02": (
            metrics["top_two_reward_gap_median"] <= 0.02
        ),
        "capacity_one_exact_replay": (
            mismatch_counts["capacity_one_exact_mismatch_count"] == 0
        ),
        "capacity_two_quality_and_global_best_retention": (
            mismatch_counts["capacity_two_retention_mismatch_count"] == 0
        ),
        "capacity_two_capacity_and_fingerprint_integrity": (
            mismatch_counts["capacity_two_integrity_mismatch_count"] == 0
        ),
        "secondary_sparse_slot_ratio_at_least_0_20": (
            metrics["secondary_sparse_slot_ratio"] >= 0.20
        ),
        "coverage_retention_median_at_least_0_85": (
            metrics["xy_cell_coverage_retention_median"] >= 0.85
        ),
        "torch_global_rng_unchanged": torch.equal(
            torch_before, torch.random.get_rng_state()
        ),
        "python_global_rng_unchanged": python_before == random.getstate(),
    }
    payload: dict[str, Any] = {
        "schema_version": 1,
        "experiment_id": "run_040_within_cell_aliasing_diagnostic",
        "hypothesis_id": "H5-v4",
        "analysis_mode": "read_only_zero_episode_capacity1_exact_replay_capacity2_counterfactual",
        "input_manifest": {
            "path": str(input_manifest.resolve()),
            "sha256": sha256_file(input_manifest),
        },
        "source_bindings": {
            "core_qd": {"path": str(core_qd.resolve()), "sha256": core_qd_sha256},
            "core_rdt": {"path": str(core_rdt.resolve()), "sha256": core_rdt_sha256},
            "design": {"path": str(design.resolve()), "sha256": design_sha256},
        },
        "frozen_counterfactual": {
            "grid_shape": [4, 4],
            "capacity": 2,
            "quality_order": ["reward_desc", "fingerprint_asc"],
            "global_quality_anchor_count": 1,
            "sparse_slots": 15,
            "population_size": 16,
            "run_seed": RUN_SEED,
            "within_cell_rotation": "sha256_start_then_round_robin",
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
            for result in trace_results
        ],
        "excluded_features": [
            "video and success labels",
            "episode outcomes",
            "future observations",
            "evaluator state",
            "validation outcomes",
            "formal outcomes",
        ],
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
    parser.add_argument("--input-manifest", type=Path, required=True)
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
    print(
        json.dumps(
            {
                "output": str(output),
                "passed": payload["passed"],
                "analysis_sha256": payload["analysis_sha256"],
                **payload["metrics"],
            },
            sort_keys=True,
        )
    )
    return 0 if payload["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
