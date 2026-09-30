"""N18 fixed-cost close-then-lift quality on projected, policy-visible data."""

from dataclasses import dataclass

import torch
from torch import Tensor

from core.qd_executed_quality import ExecutedPrefixContract


MODE = "close_then_lift_v1"
HOLD_MODE = "close_hold_then_lift_v1"
LIFT_MODES = frozenset({MODE, HOLD_MODE})
CONTACT_RADIUS_M = 0.04
LIFT_CAP_M = 0.05


@dataclass(frozen=True)
class LiftAfterCloseContract:
    base: ExecutedPrefixContract
    mode: str = MODE

    @property
    def target_index(self):
        return self.base.target_index

    @property
    def identity(self):
        return self.base.identity

    def validate(self, providers):
        self.base.validate(providers)
        if self.mode not in LIFT_MODES:
            raise RuntimeError("Unsupported lift quality mode")
        if self.target_index != 0:
            raise RuntimeError("N18 requires target keypoint zero")


def close_then_lift_bonus(projected_xyz: Tensor, keypoints: Tensor,
                          decoded_actions: Tensor, *, target_index: int) -> Tensor:
    return _lift_bonus(projected_xyz, keypoints, decoded_actions,
                       target_index=target_index, require_hold=False)


def close_hold_then_lift_bonus(projected_xyz: Tensor, keypoints: Tensor,
                               decoded_actions: Tensor, *, target_index: int) -> Tensor:
    """Credit lift only when the first eligible close is held through action eight."""
    return _lift_bonus(projected_xyz, keypoints, decoded_actions,
                       target_index=target_index, require_hold=True)


def _lift_bonus(projected_xyz: Tensor, keypoints: Tensor, decoded_actions: Tensor,
                *, target_index: int, require_hold: bool) -> Tensor:
    if not torch.is_tensor(projected_xyz) or projected_xyz.ndim != 3 or tuple(projected_xyz.shape[1:]) != (9, 3):
        raise ValueError("N18 projection must be B×9×3")
    batch = projected_xyz.shape[0]
    if batch < 1 or not torch.is_tensor(decoded_actions) or tuple(decoded_actions.shape) != (batch, 8, 7):
        raise ValueError("N18 decoded actions must be B×8×7")
    if not torch.is_tensor(keypoints) or keypoints.ndim != 2 or keypoints.shape[1] != 3:
        raise ValueError("N18 keypoints must be K×3")
    if target_index != 0 or keypoints.shape[0] <= target_index:
        raise ValueError("N18 target identity differs")
    if not all(torch.isfinite(value).all().item() for value in (projected_xyz, keypoints, decoded_actions)):
        raise FloatingPointError("N18 inputs contain nonfinite values")
    grip = decoded_actions[:, :, 6]
    if not bool(((grip == -1) | (grip == 1)).all().item()):
        raise ValueError("N18 gripper commands must be deployed binary values")
    xyz = projected_xyz.detach().float()
    target = keypoints[target_index].detach().float().to(xyz)
    distance = torch.linalg.vector_norm(xyz[:, 1:, :] - target.view(1, 1, 3), dim=2)
    eligible = (distance <= CONTACT_RADIUS_M) & (grip > 0)
    first = eligible.int().argmax(dim=1)
    contact_z = xyz[torch.arange(batch, device=xyz.device), first + 1, 2]
    lift = (xyz[:, 8, 2] - contact_z).clamp(min=0.0, max=LIFT_CAP_M)
    bonus = torch.where(eligible.any(dim=1), lift.square(), torch.zeros_like(lift))
    if require_hold:
        # A later reclose cannot erase an earlier release after first contact.
        suffix = torch.arange(8, device=grip.device).view(1, 8) >= first.view(-1, 1)
        holds_to_end = ((grip > 0) | ~suffix).all(dim=1)
        bonus = torch.where(holds_to_end, bonus, torch.zeros_like(bonus))
    if not bool(torch.isfinite(bonus).all().item()):
        raise FloatingPointError("N18 lift bonus nonfinite")
    return bonus.detach()
