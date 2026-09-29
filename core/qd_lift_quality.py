"""N18 fixed-cost close-then-lift quality on projected, policy-visible data."""

from dataclasses import dataclass

import torch
from torch import Tensor

from core.qd_executed_quality import ExecutedPrefixContract


MODE = "close_then_lift_v1"
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
        if self.target_index != 0:
            raise RuntimeError("N18 requires target keypoint zero")


def close_then_lift_bonus(projected_xyz: Tensor, keypoints: Tensor,
                          decoded_actions: Tensor, *, target_index: int) -> Tensor:
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
    if not bool(torch.isfinite(bonus).all().item()):
        raise FloatingPointError("N18 lift bonus nonfinite")
    return bonus.detach()
