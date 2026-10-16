"""Dependency-inversion boundaries used by the trajectory mode gate."""

from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from .types import (
    ActionChunkBatch,
    GateContext,
    RoundEvidence,
    SteeringSnapshot,
    TaskSpaceTrajectoryBatch,
)


@runtime_checkable
class SteeringBlackBox(Protocol):
    def advance(self, context: GateContext) -> SteeringSnapshot:
        """Advance by one native steering iteration without exposing internals."""

    def sample(
        self,
        snapshot: SteeringSnapshot,
        context: GateContext,
        count: int,
    ) -> ActionChunkBatch:
        """Return one finite batch sampled under the unchanged context."""


@runtime_checkable
class TrajectoryProjector(Protocol):
    def project(
        self,
        batch: ActionChunkBatch,
        context: GateContext,
    ) -> TaskSpaceTrajectoryBatch:
        """Project environment actions without stepping an environment."""
