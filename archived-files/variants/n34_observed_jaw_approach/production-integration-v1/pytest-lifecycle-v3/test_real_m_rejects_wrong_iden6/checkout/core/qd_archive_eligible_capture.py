"""N32 CPU-only, decision-local eligible-parent selection. No runtime hooks.

Inputs are an occupied-cell snapshot and the existing N31 canonical cache, bound
by the caller to one decision. No projection, provider, RNG or scoring calls are
made. Missing canonical evidence is an error, never geometric ineligibility.
Packet/provider/target binding remains the future native adapter's obligation.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

import torch
from torch import Tensor

from .qd_capture_dwell_proposal import capture_dwell_proposal, _same_native_bytes
from .qd_ed import QDArchiveEntry, fingerprint_action


class AssociationError(ValueError):
    """Absent, malformed or contradictory native evidence; abort opportunity."""


@dataclass(frozen=True)
class CanonicalCache:
    decision_id: tuple[int, int, int]  # episode, stage, step
    entries: Sequence[Mapping]


@dataclass(frozen=True)
class ParentEvidence:
    cell_id: int
    source_iter: int
    fingerprint: str
    matching_occurrences: tuple[int, ...]
    association: str
    reason: str
    arrival_index: int | None
    eligible: bool


@dataclass(frozen=True)
class EligibleSelection:
    candidate: Tensor | None
    selected: ParentEvidence | None
    parents: tuple[ParentEvidence, ...]  # all occupied cells, in cell order


def _require(condition, message):
    if not condition:
        raise AssociationError(message)


def _tensor(value, shape, name, dtype=None):
    _require(isinstance(value, Tensor) and tuple(value.shape) == shape,
             f"missing/malformed {name}")
    _require(value.device.type == "cpu", f"{name}: CPU implementation only")
    _require(value.is_floating_point() and bool(torch.isfinite(value).all()),
             f"nonfinite/nonfloating {name}")
    if dtype is not None:
        _require(value.dtype == dtype, f"{name} native dtype mismatch")
    return value


def _exact(a, b):
    return (a.dtype == b.dtype and a.shape == b.shape and a.device == b.device
            and _same_native_bytes(a, b))


def _decision(value):
    return (isinstance(value, tuple) and len(value) == 3
            and all(type(v) is int and v >= 0 for v in value))


@torch.no_grad()
def select_eligible_parent(
    occupied: Mapping[int, QDArchiveEntry],
    cache: CanonicalCache,
    *,
    decision_id: tuple[int, int, int],
    iteration: int,
    action_mask: Tensor,
    target: Tensor | None,
    hand_quaternion_xyzw: Tensor | None,
    gripper_qpos: Tensor | None,
    target_recognized: bool,
) -> EligibleSelection:
    """Rank changed N31 proposals by (-ordinary reward, fingerprint, cell).

    Accept only the complete preceding canonical batches (initial -1 through
    iteration-1), 16 rows each, <=176 occurrences. Duplicates are compared in
    native dtype/shape/bytes, including quality, cost, projection and both
    source/cast origins. All occupied parents are checked before returning;
    a bad lower-ranked parent cannot be hidden by an eligible global best.

    A missing projection raises with its supplied status (including Unknown).
    Valid helper abstentions retain their exact reason. The returned candidate
    is a new tensor; archive/cache/mask are never mutated. This function does
    not substitute slot15 or assert any unique ancestral lineage.
    """
    _require(_decision(decision_id) and _decision(cache.decision_id)
             and decision_id == cache.decision_id, "decision identity mismatch")
    _require(type(iteration) is int and 0 <= iteration < 10, "opportunity iteration")
    _require(0 < len(occupied) <= 16 and all(type(c) is int and 0 <= c < 16
             for c in occupied), "occupied current archive must contain 1..16 cells")
    _require(len(cache.entries) == 16 * (iteration + 1), "incomplete canonical cache")
    dtype = action_mask.dtype if isinstance(action_mask, Tensor) else None
    _require(dtype in (torch.float32, torch.bfloat16), "native FP32/BF16 mask required")
    _tensor(action_mask, (1, 1, 128), "action mask", dtype)
    expected = torch.zeros_like(action_mask)
    expected[:, :, [10, 39, 40, 41, 42, 43, 44]] = 1
    _require(_exact(action_mask, expected), "active mask differs from N31")
    for value, size, name in ((target, 3, "target"),
                              (hand_quaternion_xyzw, 4, "hand quaternion"),
                              (gripper_qpos, 2, "gripper qpos")):
        if value is not None:
            _tensor(value, (size,), name)

    # Validate the cache envelope, not any historical payload or external store.
    for occurrence, row in enumerate(cache.entries):
        _require(all(type(row.get(k)) is int for k in ("occurrence", "iteration", "row"))
                 and row["occurrence"] == occurrence
                 and row["iteration"] == occurrence // 16 - 1
                 and row["row"] == occurrence % 16, "canonical occurrence order")
        _tensor(row.get("plan"), (64, 128), "canonical plan", dtype)
        _require(row.get("fingerprint") == fingerprint_action(row["plan"]),
                 "canonical fingerprint mismatch")

    parents, candidates = [], []
    for cell, entry in sorted(occupied.items()):
        _require(type(entry.source_iter) is int and -1 <= entry.source_iter < iteration,
                 "archive source_iter outside current decision cache")
        _tensor(entry.action, (64, 128), "archive action", dtype)
        _require(entry.fingerprint == fingerprint_action(entry.action), "archive fingerprint mismatch")
        _require(math.isfinite(entry.reward) and math.isfinite(entry.cost), "archive quality/cost nonfinite")
        matches = [row for row in cache.entries
                   if row["iteration"] == entry.source_iter
                   and row["fingerprint"] == entry.fingerprint
                   and _exact(row["plan"], entry.action)]
        _require(bool(matches), "archive source absent from canonical cache")
        first = matches[0]
        for row in matches:
            status = row.get("projection_status", "Unknown_missing_status")
            _require(row.get("projection") is not None,
                     f"missing canonical projection: {status}")
            _require(status == "original_canonical", f"canonical projection status: {status}")
            for key, shape in (("quality", ()), ("cost", ()), ("projection", (8, 3)),
                               ("cast_origin", (3,))):
                _tensor(row.get(key), shape, key, dtype)
            _tensor(row.get("source_origin"), (3,), "source_origin")
            _require(_exact(row["source_origin"].to(dtype), row["cast_origin"]),
                     "source/cast origin mismatch")
            _require(_exact(row["cost"], -row["quality"]), "canonical cost != -quality")
            _require(float(row["quality"]) == entry.reward and float(row["cost"]) == entry.cost,
                     "archive quality/cost disagreement")
            for key in ("quality", "cost", "projection", "source_origin", "cast_origin"):
                _require(_exact(first[key], row[key]), f"contradictory duplicate {key}")
        _require(_exact(entry.action * action_mask[0], entry.action), "archive plan violates mask")
        result = capture_dwell_proposal(
            entry.action, first["projection"], target=target,
            hand_quaternion_xyzw=hand_quaternion_xyzw, gripper_qpos=gripper_qpos,
            target_recognized=target_recognized)
        record = ParentEvidence(
            cell, entry.source_iter, entry.fingerprint,
            tuple(row["occurrence"] for row in matches),
            "unique_occurrence" if len(matches) == 1 else "identical_content_multiple_occurrences",
            result.reason, result.arrival_index, result.changed)
        parents.append(record)
        if result.changed:
            _require(_exact(result.candidate * action_mask[0], result.candidate),
                     "candidate violates mask")
            candidates.append(((-entry.reward, entry.fingerprint, cell), record, result.candidate))
    if not candidates:
        return EligibleSelection(None, None, tuple(parents))
    _, selected, candidate = min(candidates, key=lambda item: item[0])
    return EligibleSelection(candidate, selected, tuple(parents))
