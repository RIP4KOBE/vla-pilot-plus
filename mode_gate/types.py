"""Public data contracts for the trajectory mode gate.

The contracts deliberately contain no policy- or steering-specific state.  The
only policy-facing values are opaque checkpoint identifiers and executable
environment-action chunks supplied by a :class:`SteeringBlackBox` adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


class PlannerAction(str, Enum):
    CONTINUE_STEERING = "CONTINUE_STEERING"
    REQUEST_EXPANSION = "REQUEST_EXPANSION"


class ControllerStatus(str, Enum):
    STEERING_COMPLETE = "STEERING_COMPLETE"
    REQUEST_EXPANSION = "REQUEST_EXPANSION"
    ABORTED = "ABORTED"


class ControllerRoute(str, Enum):
    """Externally visible route selected by the v2 controller."""

    EXECUTE = "EXECUTE"
    RESTEER = "RE-STEER"
    EXPAND = "EXPANSION"
    ABORT = "ABORT"


class FailureTrigger(str, Enum):
    STAGNATION = "STAGNATION"
    CONTACT = "CONTACT"
    NO_SAFE_MODE = "NO_SAFE_MODE"
    TIMEOUT = "TIMEOUT"


class ControllerPhase(str, Enum):
    NORMAL_SAMPLE = "NORMAL_SAMPLE"
    ABSTRACT = "ABSTRACT"
    SCORE = "SCORE"
    EXECUTE = "EXECUTE"
    OBSERVE = "OBSERVE"
    NORMAL_CONTINUE = "NORMAL_CONTINUE"
    VERIFICATION_DUE = "VERIFICATION_DUE"
    FRESH_SAMPLE = "FRESH_SAMPLE"
    VERIFY = "VERIFY"
    RESTEER_EXECUTE = "RESTEER_EXECUTE"
    EXPAND = "EXPAND"
    ABORT = "ABORT"


@dataclass(frozen=True)
class ProgressEvidence:
    stage_id: str
    advanced: bool
    confidence: float
    source: str
    task_success: bool = False
    reward_improved: bool = False

    def __post_init__(self) -> None:
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("progress confidence must be in [0, 1]")
        if not self.source:
            raise ValueError("progress source must be non-empty")


@dataclass(frozen=True)
class SamplingCondition:
    seed: int
    retry_index: int
    guide_mult: float = 1.0
    diversity_mult: float = 1.0

    def __post_init__(self) -> None:
        if self.retry_index < 0:
            raise ValueError("retry_index must be non-negative")
        if self.guide_mult <= 0 or self.diversity_mult < 0:
            raise ValueError("sampling multipliers are out of range")


@dataclass(frozen=True)
class SamplingDiagnostics:
    ess_history: Sequence[float]
    ancestor_ids: Sequence[int]
    ess_ratio: float
    unique_ratio: float
    resample_indices: Sequence[Sequence[int]] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        ancestors = tuple(int(value) for value in self.ancestor_ids)
        if not ancestors:
            raise ValueError("ancestor_ids must be non-empty")
        if not 0.0 <= float(self.ess_ratio) <= 1.0:
            raise ValueError("ess_ratio must be in [0, 1]")
        if not 0.0 <= float(self.unique_ratio) <= 1.0:
            raise ValueError("unique_ratio must be in [0, 1]")
        if any(not np.isfinite(float(value)) for value in self.ess_history):
            raise ValueError("ess_history contains non-finite values")
        object.__setattr__(self, "ancestor_ids", ancestors)


@dataclass(frozen=True)
class SelectedExecution:
    mode_id: str
    sample_index: int
    sample_id: str

    def __post_init__(self) -> None:
        if not self.mode_id or not self.sample_id or self.sample_index < 0:
            raise ValueError("invalid selected execution")


@dataclass(frozen=True)
class GeometryEvidence:
    mode_id: str
    collision_risk: float
    reachability: float
    grasp_plausibility: float
    hard_safety_veto: bool
    veto_reason: str | None = None
    method: str = "ee_proxy_v1"

    def __post_init__(self) -> None:
        for name in ("collision_risk", "reachability", "grasp_plausibility"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        if self.hard_safety_veto and not self.veto_reason:
            raise ValueError("hard safety veto requires a reason")


@dataclass(frozen=True)
class SemanticModeScore:
    mode_id: str
    semantic_score: float
    reason: str
    predicted_failure_types: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not 0.0 <= float(self.semantic_score) <= 1.0:
            raise ValueError("semantic_score must be in [0, 1]")


@dataclass(frozen=True)
class SemanticPlan:
    mode_scores: Sequence[SemanticModeScore]
    required_trajectory_pattern: str
    observed_stage_id: str
    stage_confidence: float
    model: str
    prompt_version: str
    raw_response: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        ids = [item.mode_id for item in self.mode_scores]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("semantic plan must contain unique mode IDs")
        if not 0.0 <= float(self.stage_confidence) <= 1.0:
            raise ValueError("stage_confidence must be in [0, 1]")


@dataclass(frozen=True)
class DecisionSnapshot:
    """Immutable pointer to an exact post-failure replay state.

    Large simulator/RGB/RNG payloads live in checksummed sidecars.  The JSONL
    decision record contains this small manifest so it can be appended and
    fsynced immediately.
    """

    snapshot_id: str
    policy_id: str
    simulator_state_path: Path
    controller_state: Mapping[str, Any]
    rng_state_path: Path
    provenance: Mapping[str, Any]
    snapshot_hash: str
    observation_hash: str

    def __post_init__(self) -> None:
        if not self.snapshot_id or not self.policy_id:
            raise ValueError("snapshot_id and policy_id must be non-empty")
        if len(self.snapshot_hash) < 16 or len(self.observation_hash) < 16:
            raise ValueError("snapshot and observation hashes are required")


@dataclass(frozen=True)
class GateContext:
    context_id: str
    observation_image: np.ndarray
    task_instruction: str
    task_stage: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        image = np.asarray(self.observation_image)
        if not self.context_id:
            raise ValueError("context_id must be non-empty")
        if image.ndim != 3 or image.shape[2] not in (3, 4):
            raise ValueError(
                "observation_image must have shape (height, width, 3|4), "
                f"got {image.shape}"
            )
        object.__setattr__(self, "observation_image", image)
        object.__setattr__(self, "task_stage", str(self.task_stage))


@dataclass(frozen=True)
class SteeringSnapshot:
    checkpoint_id: str
    is_complete: bool
    execution_action_chunk: Any = field(default=None, repr=False, compare=False)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.checkpoint_id:
            raise ValueError("checkpoint_id must be non-empty")


@dataclass(frozen=True)
class ActionChunkBatch:
    """A batch in executable environment-action space, shaped ``(N, H, A)``."""

    actions: np.ndarray
    sample_ids: Sequence[str]
    context_id: str
    round_id: int
    checkpoint_id: str
    action_space: str
    coordinate_frame: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        actions = np.asarray(self.actions, dtype=np.float32)
        if actions.ndim != 3:
            raise ValueError(f"actions must have shape (N, H, A), got {actions.shape}")
        if actions.shape[0] == 0 or actions.shape[1] == 0 or actions.shape[2] < 7:
            raise ValueError(f"actions must be a non-empty 7D+ action batch, got {actions.shape}")
        if not np.isfinite(actions).all():
            raise ValueError("actions contain non-finite values")
        sample_ids = tuple(str(value) for value in self.sample_ids)
        if len(sample_ids) != actions.shape[0] or len(set(sample_ids)) != len(sample_ids):
            raise ValueError("sample_ids must be unique and match the action batch size")
        if self.round_id < 1:
            raise ValueError("round_id must start at 1")
        if not self.context_id or not self.checkpoint_id:
            raise ValueError("context_id and checkpoint_id must be non-empty")
        object.__setattr__(self, "actions", actions)
        object.__setattr__(self, "sample_ids", sample_ids)

    @property
    def sample_count(self) -> int:
        return int(self.actions.shape[0])

    @property
    def horizon(self) -> int:
        return int(self.actions.shape[1])


@dataclass(frozen=True)
class TaskSpaceTrajectoryBatch:
    """Task-space trajectories with one start point plus every action endpoint.

    Orientations use scipy's ``(x, y, z, w)`` quaternion convention.
    """

    positions: np.ndarray
    orientations: np.ndarray
    grippers: np.ndarray
    sample_ids: Sequence[str]
    frame: str = "world"

    def __post_init__(self) -> None:
        positions = np.asarray(self.positions, dtype=np.float64)
        orientations = np.asarray(self.orientations, dtype=np.float64)
        grippers = np.asarray(self.grippers, dtype=np.float64)
        if positions.ndim != 3 or positions.shape[-1] != 3:
            raise ValueError(f"positions must have shape (N, T, 3), got {positions.shape}")
        if orientations.shape != (*positions.shape[:2], 4):
            raise ValueError(
                "orientations must have shape (N, T, 4) matching positions, "
                f"got {orientations.shape}"
            )
        if grippers.shape != positions.shape[:2]:
            raise ValueError(
                f"grippers must have shape {positions.shape[:2]}, got {grippers.shape}"
            )
        if len(self.sample_ids) != positions.shape[0]:
            raise ValueError("sample_ids must match the trajectory batch size")
        if not (
            np.isfinite(positions).all()
            and np.isfinite(orientations).all()
            and np.isfinite(grippers).all()
        ):
            raise ValueError("task-space trajectories contain non-finite values")
        norms = np.linalg.norm(orientations, axis=-1, keepdims=True)
        if np.any(norms < 1e-12):
            raise ValueError("orientation contains a zero quaternion")
        object.__setattr__(self, "positions", positions)
        object.__setattr__(self, "orientations", orientations / norms)
        object.__setattr__(self, "grippers", grippers)
        object.__setattr__(self, "sample_ids", tuple(self.sample_ids))


@dataclass(frozen=True)
class ModeEvidence:
    mode_id: str
    component_index: int
    weight: float
    member_indices: np.ndarray
    representative_indices: Mapping[str, int]
    representative_sample_ids: Mapping[str, str]
    card_path: Path
    projection_unavailable: bool
    statistics: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RoundEvidence:
    context_id: str
    round_id: int
    checkpoint_id: str
    action_batch: ActionChunkBatch
    trajectories: TaskSpaceTrajectoryBatch
    normalized_positions: np.ndarray
    normalized_rotvecs: np.ndarray
    normalized_grippers: np.ndarray
    descriptors: np.ndarray
    reduced_descriptors: np.ndarray
    labels: np.ndarray
    responsibilities: np.ndarray
    modes: Sequence[ModeEvidence]
    fit_degraded: bool
    fit_metadata: Mapping[str, Any]
    sampling_diagnostics: SamplingDiagnostics | None = None


@dataclass(frozen=True)
class PlannerModeAssessment:
    mode_id: str
    behavior_interpretation: str
    task_compatibility: str
    difficulty: str
    evidence: Sequence[str]


@dataclass(frozen=True)
class PlannerDecision:
    decision: PlannerAction
    required_trajectory_pattern: str
    mode_assessments: Sequence[PlannerModeAssessment]
    supporting_mode_ids: Sequence[str]
    verifier_candidate_mode_ids: Sequence[str]
    rationale: str
    raw_response: Mapping[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class VerifierEvidence:
    mode_id: str
    task_match: str
    missing_subpatterns: Sequence[str]
    predicted_failure_types: Sequence[str]
    candidate_reward_signals: Sequence[str]
    uncertainty: float
    evidence: Sequence[str]
    raw_response: Mapping[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class ExpansionRequest:
    context_id: str
    trigger_reason: str
    missing_or_hard_pattern: str
    steering_checkpoint_id: str
    planner_decision: PlannerDecision
    verifier_evidence: Sequence[VerifierEvidence]
    artifact_manifest: Path


@dataclass(frozen=True)
class ControllerResult:
    status: ControllerStatus
    snapshot: SteeringSnapshot | None = None
    execution_action_chunk: Any = field(default=None, repr=False, compare=False)
    expansion_request: ExpansionRequest | None = None
    rounds: int = 0
    error: str | None = None
