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



def retrieve_experiences(*, query_e_goal, query_e_obs, records):
    """Return evidence channels, never fixed-formula acceptance or task/failure gating."""
    from dataclasses import asdict
    from .experiences import artifact_ref
    result = []
    for record in records:
        value = asdict(record)
        scores = {}
        for name, query, path in (("goal_similarity", query_e_goal, record.e_goal_path),
                                  ("scene_similarity", query_e_obs, record.e_obs_path)):
            if Path(path).is_file():
                scores[name] = cosine_similarity(query, np.load(path, allow_pickle=False).astype(np.float32))
        value["retrieval_diagnostics"] = scores
        value["retrieval_is_validation"] = False
        refs = []
        for key in ("policy_gate_report_path", "multimodal_evidence_path", "candidate_manifest_path"):
            path = record.metadata.get(key)
            if path and Path(path).is_file():
                refs.append(artifact_ref(path, kind="historical_evidence"))
        value["evidence_refs"] = refs
        result.append(value)
    # Stable catalog allows pagination and independent language/vision inspection;
    # no weighted similarity formula or semantic threshold decides reuse.
    return tuple(sorted(result, key=lambda x: x["signature_id"]))
