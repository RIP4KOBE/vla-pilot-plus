"""Weak human-demo support matching for the same exact decision snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import h5py
import numpy as np

from .incidents import IncidentMemory, VerifierLabelRecord
from .io_utils import sha256_file


@dataclass(frozen=True)
class DemoMatchResult:
    matched: bool
    confidence: float
    mean_position_distance_m: float
    gripper_switch_phase_error: float
    mode_index: int | None
    label_attached: bool
    reason: str


def attach_demo_match_label(
    memory: IncidentMemory,
    *,
    record_id: str,
    demo_path: Path,
    label_version: str,
    candidate_target_object_id: str | None = None,
    demo_target_object_id: str | None = None,
    max_position_distance_m: float = 0.03,
    max_switch_phase_error: float = 0.15,
) -> DemoMatchResult:
    """Attach a 0.25-weight weak target only when all frozen rules pass."""

    decisions = [
        item
        for item in memory.decisions.iter_valid()
        if item.get("record_id") == record_id
    ]
    if len(decisions) != 1:
        raise KeyError(f"expected one verifier decision {record_id!r}")
    decision = decisions[0]
    provenance = decision.get("provenance", {})
    analysis_path = Path(str(provenance.get("round_analysis_path", "")))
    if not analysis_path.is_file():
        raise FileNotFoundError(analysis_path)
    expected_digest = provenance.get("round_analysis_sha256")
    if expected_digest and sha256_file(analysis_path) != expected_digest:
        raise ValueError("round analysis checksum mismatch")

    demo_path = Path(demo_path)
    with h5py.File(demo_path, "r") as demo:
        if str(demo.attrs.get("snapshot_id", "")) != str(decision["snapshot_id"]):
            return _no_match("demo_does_not_start_from_exact_decision_snapshot")
        demo_positions = _resample(np.asarray(demo["ee_position"], dtype=np.float64))
        demo_gripper = np.asarray(demo["action"][:, 6], dtype=np.float64)
        demo_target_object_id = demo_target_object_id or str(
            demo.attrs.get("target_object_id", "")
        )
    candidate_target_object_id = candidate_target_object_id or str(
        provenance.get("target_object_id", "")
    )
    if (
        not candidate_target_object_id
        or candidate_target_object_id != demo_target_object_id
    ):
        return _no_match("nearest_target_object_id_mismatch")

    with np.load(analysis_path, allow_pickle=False) as analysis:
        positions = np.asarray(analysis["positions"], dtype=np.float64)
        grippers = np.asarray(analysis["grippers"], dtype=np.float64)
        medoids = np.asarray(analysis["medoid_indices"], dtype=np.int64)
    best: tuple[float, float, int] | None = None
    demo_switch = _first_switch_phase(demo_gripper)
    for mode_index, sample_index in enumerate(medoids):
        candidate_positions = _resample(positions[int(sample_index)])
        distance = float(
            np.linalg.norm(candidate_positions - demo_positions, axis=1).mean()
        )
        switch_error = abs(
            _first_switch_phase(grippers[int(sample_index)]) - demo_switch
        )
        value = (distance, switch_error, mode_index)
        if best is None or value < best:
            best = value
    if best is None:
        return _no_match("analysis_has_no_medoid")
    distance, switch_error, mode_index = best
    if distance > max_position_distance_m or switch_error > max_switch_phase_error:
        return DemoMatchResult(
            False,
            0.0,
            distance,
            switch_error,
            mode_index,
            False,
            "trajectory_threshold_failed",
        )
    confidence = min(
        1.0,
        max(0.0, 1.0 - distance / max_position_distance_m),
        max(0.0, 1.0 - switch_error / max_switch_phase_error),
    )
    branches = 100
    successes = int(round(confidence * branches))
    label = VerifierLabelRecord(
        record_id=record_id,
        label_version=label_version,
        source="demo_match",
        branches=branches,
        successes=successes,
        p_expansion=1.0 - successes / branches,
        policy_id=str(decision["policy_id"]),
        snapshot_hash=str(decision["snapshot_hash"]),
        verifier_feature_path=str(decision["verifier_feature_path"]),
        data_split="train",
        weak=True,
        weight=0.25,
    )
    attached = memory.attach_label(label)
    return DemoMatchResult(
        True,
        confidence,
        distance,
        switch_error,
        mode_index,
        attached,
        "matched_weak_support",
    )


def _resample(positions: np.ndarray, phases: int = 20) -> np.ndarray:
    positions = np.asarray(positions, dtype=np.float64)
    if positions.ndim != 2 or positions.shape[1] != 3 or len(positions) < 2:
        raise ValueError("trajectory positions must have shape (T>=2, 3)")
    source = np.linspace(0.0, 1.0, len(positions))
    target = np.linspace(0.0, 1.0, phases)
    return np.column_stack(
        [np.interp(target, source, positions[:, axis]) for axis in range(3)]
    )


def _first_switch_phase(gripper: np.ndarray) -> float:
    gripper = np.asarray(gripper, dtype=np.float64).reshape(-1)
    if len(gripper) < 2:
        return 1.0
    switches = np.flatnonzero(np.signbit(gripper[1:]) != np.signbit(gripper[:-1]))
    return 1.0 if not len(switches) else float((switches[0] + 1) / (len(gripper) - 1))


def _no_match(reason: str) -> DemoMatchResult:
    return DemoMatchResult(False, 0.0, float("inf"), float("inf"), None, False, reason)


__all__ = ["DemoMatchResult", "attach_demo_match_label"]
