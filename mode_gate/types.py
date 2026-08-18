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

