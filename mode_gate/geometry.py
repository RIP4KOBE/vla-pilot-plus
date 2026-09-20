"""Deterministic geometry scoring and safe semantic candidate selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

import numpy as np

from .types import (
    GeometryEvidence,
    CandidateEvidence,
    RoundEvidence,
    SelectedExecution,
    SemanticCandidateScore,
)


@dataclass(frozen=True)
class AxisAlignedBox:
    minimum: np.ndarray
    maximum: np.ndarray
    object_id: str = "unknown"
    exact: bool = False

    def __post_init__(self) -> None:
        minimum = np.asarray(self.minimum, dtype=np.float64)
        maximum = np.asarray(self.maximum, dtype=np.float64)
        if minimum.shape != (3,) or maximum.shape != (3,):
            raise ValueError("AABB bounds must have shape (3,)")
        if not np.isfinite(minimum).all() or not np.isfinite(maximum).all():
            raise ValueError("AABB contains non-finite values")
        if np.any(minimum >= maximum):
            raise ValueError("AABB minimum must be smaller than maximum")
        object.__setattr__(self, "minimum", minimum)
        object.__setattr__(self, "maximum", maximum)


@dataclass(frozen=True)
class GeometryContext:
    workspace: AxisAlignedBox
    obstacles: Sequence[AxisAlignedBox] = field(default_factory=tuple)
    target: AxisAlignedBox | None = None
    collision_margin_m: float = 0.03
    grasp_distance_m: float = 0.05


class GeometryScorer:
    """Score mode candidates using clone-sim when available, else ee_proxy_v1."""

    def __init__(
        self,
        context: GeometryContext,
        *,
        clone_sim_evaluator: Callable[[np.ndarray, np.ndarray], Mapping[str, object]]
        | None = None,
    ) -> None:
        self.context = context
        self.clone_sim_evaluator = clone_sim_evaluator

    def score_round(self, evidence: RoundEvidence) -> tuple[GeometryEvidence, ...]:
        return tuple(self.score_candidate(evidence, candidate) for candidate in evidence.candidates)

    def score_candidate(
        self,
        evidence: RoundEvidence,
        candidate: CandidateEvidence,
    ) -> GeometryEvidence:
        index = candidate.sample_index
        positions = np.asarray(evidence.trajectories.positions[index], dtype=np.float64)
        gripper = np.asarray(evidence.trajectories.grippers[index], dtype=np.float64)
        if self.clone_sim_evaluator is not None:
            result = dict(self.clone_sim_evaluator(positions, gripper))
            return GeometryEvidence(
                candidate_id=candidate.candidate_id,
                collision_risk=float(result["collision_risk"]),
                reachability=float(result["reachability"]),
                grasp_plausibility=float(result["grasp_plausibility"]),
                hard_safety_veto=bool(result.get("hard_safety_veto", False)),
                veto_reason=(
                    str(result["veto_reason"])
                    if result.get("veto_reason") is not None
                    else None
                ),
                method="clone_sim_v1",
            )
        return self._score_proxy(candidate.candidate_id, positions, gripper)

    def _score_proxy(
        self,
        candidate_id: str,
        positions: np.ndarray,
        gripper: np.ndarray,
    ) -> GeometryEvidence:
        workspace = self.context.workspace
        below = workspace.minimum - positions
        above = positions - workspace.maximum
        violation = np.maximum(np.maximum(below, above), 0.0)
        max_violation = float(np.linalg.norm(violation, axis=1).max())
        if max_violation > 1e-9:
            return GeometryEvidence(
                candidate_id=candidate_id,
                collision_risk=1.0,
                reachability=0.0,
                grasp_plausibility=0.0,
                hard_safety_veto=True,
                veto_reason="workspace_violation",
                method="ee_proxy_v1",
            )

        minimum_clearance = float("inf")
        penetration = False
        exact_penetration = False
        for obstacle in self.context.obstacles:
            signed = _signed_distance_points_aabb(positions, obstacle)
            minimum_clearance = min(minimum_clearance, float(signed.min()))
            if np.any(signed < 0.0):
                penetration = True
                exact_penetration = exact_penetration or obstacle.exact
        if exact_penetration:
            return GeometryEvidence(
                candidate_id=candidate_id,
                collision_risk=1.0,
                reachability=0.0,
                grasp_plausibility=0.0,
                hard_safety_veto=True,
                veto_reason="proxy_penetration",
                method="ee_proxy_v1",
            )
        if penetration:
            # Approximate object AABBs may include free space.  They can raise
            # continuous risk but cannot veto execution without an exact geom
            # bound or clone-sim collision.
            collision_risk = 1.0
        elif not np.isfinite(minimum_clearance):
            collision_risk = 0.0
        else:
            collision_risk = float(
                np.clip(
                    (self.context.collision_margin_m - minimum_clearance)
                    / self.context.collision_margin_m,
                    0.0,
                    1.0,
                )
            )

        endpoint = positions[-1]
        if self.context.target is None:
            reachability = 1.0
            grasp = 0.5
        else:
            target_distance = float(
                _signed_distance_points_aabb(endpoint[None, :], self.context.target)[0]
            )
            target_distance = max(0.0, target_distance)
            reachability = float(np.exp(-target_distance / 0.15))
            closes = bool(np.any((gripper[1:] < 0.0) & (gripper[:-1] >= 0.0)))
            proximity = float(
                np.clip(1.0 - target_distance / self.context.grasp_distance_m, 0.0, 1.0)
            )
            grasp = proximity if closes else 0.5 * proximity
        return GeometryEvidence(
            candidate_id=candidate_id,
            collision_risk=collision_risk,
            reachability=reachability,
            grasp_plausibility=grasp,
            hard_safety_veto=False,
            method="ee_proxy_v1",
        )


def select_execution_candidate(
    candidates: Sequence[CandidateEvidence],
    geometry: Sequence[GeometryEvidence],
    semantics: Sequence[SemanticCandidateScore],
    selected_candidate_id: str | None = None,
) -> SelectedExecution | None:
    """Execute the Planner's candidate choice, subject only to hard safety vetoes."""

    candidate_by_id = {item.candidate_id: item for item in candidates}
    geometry_by_id = {item.candidate_id: item for item in geometry}
    semantic_by_id = {item.candidate_id: item for item in semantics}
    expected = set(candidate_by_id)
    if set(geometry_by_id) != expected or set(semantic_by_id) != expected:
        raise ValueError("geometry and semantics must cover all candidates exactly once")
    if not any(not item.hard_safety_veto for item in geometry):
        return None
    if selected_candidate_id not in expected:
        raise ValueError("Planner must select an existing candidate when safe candidates exist")
    winner = candidate_by_id[selected_candidate_id]
    if geometry_by_id[winner.candidate_id].hard_safety_veto:
        raise ValueError("Planner selected a hard-vetoed candidate; replan, do not relabel as incapability")
    return SelectedExecution(
        candidate_id=winner.candidate_id,
        sample_index=winner.sample_index,
        sample_id=winner.sample_id,
    )


def adapter_geometry_scorer(adapter: object, context_metadata: Mapping[str, object]) -> GeometryScorer:
    bounds = context_metadata.get("workspace_bounds")
    if bounds is None:
        bounds = ((-1.0, -1.0, 0.0), (1.0, 1.0, 1.5))
    minimum, maximum = bounds  # type: ignore[misc]
    obstacles = tuple(
        AxisAlignedBox(
            np.asarray(item["minimum"]),
            np.asarray(item["maximum"]),
            str(item.get("object_id", "obstacle")),
            bool(item.get("exact", False)),
        )
        for item in context_metadata.get("obstacle_aabbs", ())  # type: ignore[union-attr]
    )
    target_value = context_metadata.get("target_aabb")
    target = None
    if target_value is not None:
        target = AxisAlignedBox(
            np.asarray(target_value["minimum"]),  # type: ignore[index]
            np.asarray(target_value["maximum"]),  # type: ignore[index]
            str(target_value.get("object_id", "target")),  # type: ignore[union-attr]
            bool(target_value.get("exact", False)),  # type: ignore[union-attr]
        )
    evaluator = getattr(adapter, "evaluate_candidate_geometry", None)
    return GeometryScorer(
        GeometryContext(
            workspace=AxisAlignedBox(np.asarray(minimum), np.asarray(maximum), "workspace"),
            obstacles=obstacles,
            target=target,
        ),
        clone_sim_evaluator=evaluator if callable(evaluator) else None,
    )


def _signed_distance_points_aabb(points: np.ndarray, box: AxisAlignedBox) -> np.ndarray:
    """Positive outside distance and negative inside penetration depth."""

    points = np.asarray(points, dtype=np.float64)
    outside = np.maximum(np.maximum(box.minimum - points, points - box.maximum), 0.0)
    outside_distance = np.linalg.norm(outside, axis=1)
    inside = np.all((points >= box.minimum) & (points <= box.maximum), axis=1)
    if np.any(inside):
        face_distance = np.minimum(points[inside] - box.minimum, box.maximum - points[inside])
        outside_distance[inside] = -face_distance.min(axis=1)
    return outside_distance


__all__ = [
    "AxisAlignedBox",
    "GeometryContext",
    "GeometryScorer",
    "adapter_geometry_scorer",
    "select_execution_candidate",
]
