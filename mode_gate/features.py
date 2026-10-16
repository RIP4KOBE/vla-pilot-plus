"""Task-keypoint ordering for steering, independent of the verifier."""
import re
from typing import Mapping, Sequence
import numpy as np

def select_task_keypoints(
    positions: np.ndarray,
    *,
    instruction: str,
    mask_ids: Sequence[int] | np.ndarray | None = None,
    keypoint_to_object: Mapping[int, str] | None = None,
    limit: int = 8,
) -> np.ndarray:
    """Put instruction-mentioned objects first, then use stable object IDs."""

    values = np.asarray(positions, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 3:
        raise ValueError("keypoint positions must have shape (J, 3)")
    if limit < 1:
        raise ValueError("keypoint limit must be positive")
    ids = (
        np.arange(len(values), dtype=np.int64)
        if mask_ids is None
        else np.asarray(mask_ids, dtype=np.int64)
    )
    if ids.shape != (len(values),):
        raise ValueError("mask_ids must align with keypoint positions")
    mapping = {
        int(key): str(name) for key, name in (keypoint_to_object or {}).items()
    }
    normalized_instruction = _normalize_object_text(instruction)
    instruction_tokens = set(normalized_instruction.split())
    ranked = []
    for index, (position, segment_id) in enumerate(zip(values, ids)):
        if not np.isfinite(position).all():
            continue
        object_name = mapping.get(index, mapping.get(int(segment_id), ""))
        normalized_name = _normalize_object_text(object_name)
        object_tokens = [token for token in normalized_name.split() if len(token) > 1]
        mentioned = bool(
            normalized_name
            and (
                normalized_name in normalized_instruction
                or (object_tokens and all(token in instruction_tokens for token in object_tokens))
            )
        )
        ranked.append(
            (
                0 if mentioned else 1,
                normalized_name,
                int(segment_id),
                index,
                position,
            )
        )
    ranked.sort(key=lambda item: item[:4])
    if not ranked:
        return np.empty((0, 3), dtype=np.float64)
    return np.stack([item[4] for item in ranked[:limit]], axis=0)


def _normalize_object_text(value: str) -> str:
    return " ".join(
        re.findall(r"[a-z0-9]+", str(value).lower().replace("_", " "))
    )
