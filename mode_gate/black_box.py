"""Thin adapters that turn public steering calls into the black-box protocol."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import numpy as np

from .types import ActionChunkBatch, GateContext, SteeringSnapshot


@dataclass(frozen=True)
class BlackBoxSample:
    candidates: Any
    execution_action_chunk: Any
    is_complete: bool = True
    checkpoint_id: str | None = None
    metadata: dict[str, Any] | None = None


class OneShotSteeringBlackBox:
    """Adapt an externally supplied sampling callback as an opaque operation."""

    def __init__(
        self,
        sample_count: int,
        sampler: Callable[[GateContext, int], BlackBoxSample],
        *,
        action_space: str,
        coordinate_frame: str,
    ) -> None:
        self._sample_count = int(sample_count)
        self._sampler = sampler
        self._action_space = action_space
        self._coordinate_frame = coordinate_frame
        self._round_id = 0
        self._buffer: tuple[SteeringSnapshot, np.ndarray] | None = None

    def advance(self, context: GateContext) -> SteeringSnapshot:
        self._round_id += 1
        result = self._sampler(context, self._sample_count)
        candidates = _as_numpy_actions(result.candidates)
        if candidates.shape[0] != self._sample_count:
            raise ValueError(
                "steering black box returned "
                f"{candidates.shape[0]} candidates; expected exactly {self._sample_count}"
            )
        checkpoint_id = result.checkpoint_id or (
            f"{context.context_id}-round-{self._round_id:03d}-{uuid4().hex[:8]}"
        )
        snapshot = SteeringSnapshot(
            checkpoint_id=checkpoint_id,
            is_complete=bool(result.is_complete),
            execution_action_chunk=result.execution_action_chunk,
            metadata=result.metadata or {},
        )
        self._buffer = (snapshot, candidates)
        return snapshot

    def sample(
        self,
        snapshot: SteeringSnapshot,
        context: GateContext,
        count: int,
    ) -> ActionChunkBatch:
        if count != self._sample_count:
            raise ValueError(
                f"this black-box snapshot was sampled for {self._sample_count}, got {count}"
            )
        if self._buffer is None or self._buffer[0].checkpoint_id != snapshot.checkpoint_id:
            raise ValueError("sample() must use the most recent advance() snapshot")
        candidates = self._buffer[1]
        return ActionChunkBatch(
            actions=candidates.copy(),
            sample_ids=tuple(
                f"{context.context_id}-r{self._round_id:03d}-s{index:03d}"
                for index in range(count)
            ),
            context_id=context.context_id,
            round_id=self._round_id,
            checkpoint_id=snapshot.checkpoint_id,
            action_space=self._action_space,
            coordinate_frame=self._coordinate_frame,
            metadata={"black_box_adapter": type(self).__name__},
        )


def _as_numpy_actions(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "float"):
        value = value.float()
    if hasattr(value, "numpy"):
        value = value.numpy()
    actions = np.asarray(value, dtype=np.float32)
    if actions.ndim == 2:
        actions = actions[None, ...]
    if actions.ndim != 3:
        raise ValueError(f"candidate actions must have shape (N, H, A), got {actions.shape}")
    return actions
