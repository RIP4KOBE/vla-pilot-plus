"""N5's pure last-population consumer, using an already computed projection."""
from __future__ import annotations

from dataclasses import dataclass

import torch


MODE = "terminal_grasp_proximity_v1"
ABSOLUTE_REACH_M = 0.06
RELATIVE_REACH_M = 0.03


@dataclass(frozen=True)
class GraspTimingSelection:
    index: int
    native_argmin_index: int
    eligible_indices: tuple[int, ...]
    target_index: int | None
    recognition_reason: str
    best_reach_m: float | None
    projected_distances_m: torch.Tensor | None
    positive_commands: torch.Tensor | None


def select_grasp_timing(terminal, projected_xyz, decoded_actions, keypoints, *,
                        target_index: int | None, recognition_reason: str) -> GraspTimingSelection:
    """Choose first native minimum cost among close positive-command candidates.

    The caller owns source recognition and must pass the already computed final
    canonical projection. Unsupported provider semantics use N4's native argmin.
    Invalid native associations fail closed rather than falling back.
    """
    reference = terminal.select_index()
    if target_index is None:
        if not isinstance(recognition_reason, str) or not recognition_reason:
            raise ValueError("N5 fallback requires a recognition reason")
        return GraspTimingSelection(reference, reference, (), None, recognition_reason,
                                    None, None, None)
    if type(target_index) is not int or target_index < 0:
        raise ValueError("N5 target index invalid")
    if not isinstance(keypoints, torch.Tensor) or keypoints.ndim != 2 or keypoints.shape[1] != 3:
        raise ValueError("N5 keypoints must have shape (K,3)")
    if target_index >= keypoints.shape[0]:
        raise ValueError("N5 target index outside keypoints")
    if not isinstance(projected_xyz, torch.Tensor) or projected_xyz.shape != (16, 9, 3):
        raise ValueError("N5 projection must be (16,9,3)")
    if not isinstance(decoded_actions, torch.Tensor) or decoded_actions.shape != (16, 8, 7):
        raise ValueError("N5 decoded actions must be (16,8,7)")
    for name, value in (("keypoints", keypoints), ("projection", projected_xyz),
                        ("decoded actions", decoded_actions)):
        if not value.is_floating_point() or not bool(torch.isfinite(value).all()):
            raise FloatingPointError(f"N5 {name} nonfinite/nonfloating")
        if value.device != terminal.actions.device:
            raise ValueError(f"N5 {name} device differs from native population")
    if projected_xyz.dtype != terminal.actions.dtype or keypoints.dtype != terminal.actions.dtype:
        raise ValueError("N5 projection/keypoint dtype differs from native population")
    grip = decoded_actions[:, :, 6]
    if not bool(((grip == -1) | (grip == 1)).all()):
        raise ValueError("N5 decoded gripper commands must be binary")
    distances = torch.linalg.vector_norm(
        projected_xyz[:, 1:9, :].detach().float()
        - keypoints[target_index].detach().float(), dim=-1)
    if not bool(torch.isfinite(distances).all()):
        raise FloatingPointError("N5 distances nonfinite")
    best_reach = distances.min()
    close = (distances <= ABSOLUTE_REACH_M) & (distances <= best_reach + RELATIVE_REACH_M)
    eligible = ((grip > 0) & close).any(dim=1)
    indices = tuple(int(i) for i in torch.nonzero(eligible, as_tuple=False).reshape(-1).tolist())
    if indices:
        masked_costs = terminal.costs.masked_fill(~eligible, float("inf"))
        chosen = int(torch.argmin(masked_costs).item())
    else:
        chosen = reference
    return GraspTimingSelection(chosen, reference, indices, target_index,
                                recognition_reason, float(best_reach.item()),
                                distances.detach().clone(), (grip > 0).detach().clone())
