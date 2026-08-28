"""Deterministic failure vocabulary, signature hashing, and validated lookup."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np

from .incidents import CapabilitySignatureRecord


class FailureMode(str, Enum):
    GRASP_MISALIGNED_LATERAL = "GRASP_MISALIGNED_LATERAL"
    GRASP_MISALIGNED_DEPTH = "GRASP_MISALIGNED_DEPTH"
    GRASP_PREMATURE_CLOSE = "GRASP_PREMATURE_CLOSE"
    APPROACH_WRONG_OBJECT = "APPROACH_WRONG_OBJECT"
    APPROACH_BLOCKED = "APPROACH_BLOCKED"
    APPROACH_OVERSHOOT = "APPROACH_OVERSHOOT"
    TRANSPORT_DROPPED = "TRANSPORT_DROPPED"
    TRANSPORT_COLLISION = "TRANSPORT_COLLISION"
    PLACEMENT_OFFSET = "PLACEMENT_OFFSET"
    PLACEMENT_ORIENTATION = "PLACEMENT_ORIENTATION"
    LANGUAGE_UNGROUNDED = "LANGUAGE_UNGROUNDED"
    UNKNOWN = "UNKNOWN"


KEYWORD_MAP_VERSION = "failure-keywords-v1"
KEYWORD_MAP: tuple[tuple[FailureMode, tuple[str, ...]], ...] = (
    (FailureMode.GRASP_PREMATURE_CLOSE, ("premature close", "closed too early")),
    (FailureMode.GRASP_MISALIGNED_LATERAL, ("lateral", "side offset", "left of", "right of")),
    (FailureMode.GRASP_MISALIGNED_DEPTH, ("depth", "too shallow", "too deep")),
    (FailureMode.APPROACH_WRONG_OBJECT, ("wrong object", "incorrect object")),
    (FailureMode.APPROACH_BLOCKED, ("blocked", "occluded approach", "obstructed")),
    (FailureMode.APPROACH_OVERSHOOT, ("overshoot", "passed the target")),
    (FailureMode.TRANSPORT_DROPPED, ("dropped", "lost grasp", "slipped")),
    (FailureMode.TRANSPORT_COLLISION, ("transport collision", "collided while carrying")),
    (FailureMode.PLACEMENT_ORIENTATION, ("orientation", "rotated incorrectly")),
    (FailureMode.PLACEMENT_OFFSET, ("placement offset", "placed beside", "position offset")),
    (FailureMode.LANGUAGE_UNGROUNDED, ("ungrounded", "instruction mismatch", "language")),
)


def map_failure_text(text: str) -> FailureMode:
    normalized = " ".join(str(text).lower().split())
    for mode, keywords in KEYWORD_MAP:
        if any(keyword in normalized for keyword in keywords):
            return mode
    return FailureMode.UNKNOWN


def cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
    left = np.asarray(left, dtype=np.float32)
    right = np.asarray(right, dtype=np.float32)
    if left.shape != right.shape or left.ndim != 1:
        raise ValueError("cosine vectors must have the same one-dimensional shape")
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denominator <= 1e-12:
        return 0.0
    return float(np.dot(left, right) / denominator)


def signature_hash(
    *,
    suite: str,
    task_id: str,
    perturbation_variant: str,
    failure_mode: FailureMode,
    e_goal: np.ndarray,
    e_obs: np.ndarray,
) -> str:
    digest = hashlib.sha256()
    for value in (suite, task_id, perturbation_variant, failure_mode.value):
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    digest.update(np.asarray(e_goal, dtype=np.float16).tobytes())
    digest.update(np.asarray(e_obs, dtype=np.float16).tobytes())
    return digest.hexdigest()


@dataclass(frozen=True)
class LookupMatch:
    signature: CapabilitySignatureRecord
    similarity: float
    alpha_candidates: tuple[float, ...]


def lookup_validated_remedies(
    *,
    query_failure_mode: FailureMode,
    query_e_goal: np.ndarray,
    query_e_obs: np.ndarray,
    records: Iterable[CapabilitySignatureRecord],
    similarity_threshold: float = 0.85,
    minimum_headroom: float = 0.15,
) -> tuple[LookupMatch, ...]:
    matches = []
    for record in records:
        if record.failure_mode != query_failure_mode.value:
            continue
        if not (
            record.validated
            and record.regression_passed
            and record.trigger_recheck_passed
        ):
            continue
        if 1.0 - record.alpha_l < minimum_headroom - 1e-12:
            continue
        goal = np.load(Path(record.e_goal_path), allow_pickle=False).astype(np.float32)
        observation = np.load(Path(record.e_obs_path), allow_pickle=False).astype(np.float32)
        similarity = 0.5 * cosine_similarity(query_e_goal, goal) + 0.5 * cosine_similarity(
            query_e_obs, observation
        )
        if similarity < similarity_threshold:
            continue
        alphas = tuple(
            sorted(
                {
                    round(min(1.0, record.alpha_l + increment), 8)
                    for increment in (0.15, 0.30, 0.50)
                    if min(1.0, record.alpha_l + increment) > record.alpha_l
                }
            )
        )
        if alphas:
            matches.append(LookupMatch(record, similarity, alphas))
    matches.sort(
        key=lambda item: (-item.similarity, item.signature.signature_id)
    )
    return tuple(matches)


__all__ = [
    "FailureMode",
    "KEYWORD_MAP_VERSION",
    "LookupMatch",
    "cosine_similarity",
    "lookup_validated_remedies",
    "map_failure_text",
    "signature_hash",
]
