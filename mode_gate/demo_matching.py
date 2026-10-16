"""Demonstration–candidate comparison, as evidence for Planner interpretation."""
from dataclasses import dataclass
from pathlib import Path
import h5py
import numpy as np
from .incidents import IncidentMemory
from .io_utils import sha256_file
from .experiences import artifact_ref

@dataclass(frozen=True)
class DemoMatchResult:
    comparisons: tuple[dict, ...]
    same_snapshot: bool
    native_success: bool
    evidence_id: str
    label_attached: bool = False
    reason: str = "comparison_only_planner_decides_label"

def compare_demo_candidates(memory: IncidentMemory, *, record_id: str, demo_path: Path, **metadata) -> DemoMatchResult:
    decision = next((x for x in memory.decisions.iter_valid() if x["record_id"] == record_id), None)
    if decision is None:
        raise KeyError(record_id)
    source = Path(decision["provenance"]["round_analysis_path"])
    expected = decision["provenance"].get("round_analysis_sha256")
    if expected and sha256_file(source) != expected:
        raise ValueError("candidate evidence changed")
    with h5py.File(demo_path, "r") as demo:
        demo_positions = _resample(np.asarray(demo["ee_position"]))
        demo_gripper = np.asarray(demo["action"][:, 6])
        same_snapshot = str(demo.attrs.get("snapshot_id", "")) == decision["snapshot_id"]
        success = bool(demo.attrs.get("simulator_success", False))
    with np.load(source, allow_pickle=False) as data:
        positions, grippers = data["positions"], data["grippers"]
        ids = data["candidate_ids"].tolist()
    comparisons = tuple({
        "candidate_id": str(ids[i]), "sample_index": i,
        "mean_position_distance_m": float(np.linalg.norm(_resample(path) - demo_positions, axis=1).mean()),
        "gripper_switch_phase_error": abs(_first_switch_phase(grippers[i]) - _first_switch_phase(demo_gripper)),
    } for i, path in enumerate(positions))
    fact = memory.record_fact(
        episode_id=str(decision["provenance"].get("episode_id", "")),
        context_id=record_id, kind="demo_candidate_comparison", payload={
            "demo": artifact_ref(demo_path, kind="demonstration"),
            "candidates": artifact_ref(source, kind="predicted_candidates"),
            "same_snapshot": same_snapshot, "native_success": success,
            "comparisons": list(comparisons), "all_candidates_compared": len(comparisons),
            "limitation": "phase alignment is descriptive, not proof of executable recovery; differing initial states are flagged"})
    return DemoMatchResult(comparisons, same_snapshot, success, fact["event_id"])

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
