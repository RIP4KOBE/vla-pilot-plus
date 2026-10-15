"""N9 final-population selection using projected contact-zone lateral motion."""
from __future__ import annotations

from dataclasses import dataclass

import torch

from core.qd_grasp_timing import GraspTimingSelection


MODE = "terminal_contact_sweep_v1"
CONTACT_XY_M = 0.08
CONTACT_HEIGHT_M = 0.08
MAX_REACH_LOSS_M = 0.02
SWEEP_COST_PER_M = 0.20


@dataclass(frozen=True)
class ContactSweepSelection:
    index: int
    grasp_index: int
    target_index: int | None
    reason: str
    projected_reach_m: torch.Tensor | None
    lateral_sweep_m: torch.Tensor | None
    adjusted_costs: torch.Tensor | None
    candidate_mask: torch.Tensor | None


def select_contact_sweep(grasp: GraspTimingSelection, costs: torch.Tensor,
                         projected_xyz: torch.Tensor, keypoints: torch.Tensor | None,
                         ) -> ContactSweepSelection:
    """Rerank N5's eligible set while keeping its original reach and fallback.

    Uses only the already decoded final population's canonical projection and
    the current target keypoint. The original N5 choice is always in the mask.
    """
    if grasp.target_index is None:
        return ContactSweepSelection(grasp.index, grasp.index, None,
                                     grasp.recognition_reason, None, None, None, None)
    if not isinstance(costs, torch.Tensor) or costs.shape != (16,) or not costs.is_floating_point():
        raise ValueError("N9 native costs must be a floating (16,) tensor")
    if not isinstance(projected_xyz, torch.Tensor) or projected_xyz.shape != (16, 9, 3):
        raise ValueError("N9 canonical projection must be (16,9,3)")
    if not isinstance(keypoints, torch.Tensor) or keypoints.ndim != 2 or keypoints.shape[1] != 3:
        raise ValueError("N9 current keypoints must be (K,3)")
    if not 0 <= grasp.target_index < keypoints.shape[0] or not 0 <= grasp.index < 16:
        raise ValueError("N9 target or original index is outside native population")
    for name, tensor in (("costs", costs), ("projection", projected_xyz), ("keypoints", keypoints)):
        if not tensor.is_floating_point() or not bool(torch.isfinite(tensor).all()):
            raise FloatingPointError(f"N9 {name} contains nonfinite values")
        if tensor.device != costs.device:
            raise ValueError(f"N9 {name} device differs from native costs")
    if projected_xyz.dtype != keypoints.dtype:
        raise ValueError("N9 projection and keypoint dtypes differ")
    target = keypoints[grasp.target_index].detach().float()
    projected = projected_xyz.detach().float()
    positions = projected[:, 1:9]
    reach = torch.linalg.vector_norm(positions - target, dim=-1).min(dim=1).values
    horizontal = torch.linalg.vector_norm(projected[:, :, :2] - target[:2], dim=-1)
    height = (projected[:, :, 2] - target[2]).abs()
    contact_zone = (horizontal < CONTACT_XY_M) & (height < CONTACT_HEIGHT_M)
    lateral_step = torch.linalg.vector_norm(projected[:, 1:, :2] - projected[:, :-1, :2], dim=-1)
    sweep = (lateral_step * (contact_zone[:, 1:] | contact_zone[:, :-1])).sum(dim=1)
    if not bool(torch.isfinite(reach).all()) or not bool(torch.isfinite(sweep).all()):
        raise FloatingPointError("N9 reach or lateral sweep is nonfinite")
    eligible = torch.ones(16, dtype=torch.bool, device=costs.device)
    if grasp.eligible_indices:
        eligible.zero_()
        eligible[list(grasp.eligible_indices)] = True
    mask = eligible & (reach <= reach[grasp.index] + MAX_REACH_LOSS_M)
    if not bool(mask[grasp.index]):
        raise RuntimeError("N9 original N5 choice was excluded")
    adjusted = costs.detach().float() + SWEEP_COST_PER_M * sweep
    selected = int(torch.argmin(adjusted.masked_fill(~mask, float("inf"))).item())
    return ContactSweepSelection(selected, grasp.index, grasp.target_index,
                                 "recognized_contact_zone", reach.detach().clone(),
                                 sweep.detach().clone(), adjusted.detach().clone(),
                                 mask.detach().clone())
