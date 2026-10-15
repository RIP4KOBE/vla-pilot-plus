"""N27 pure pre-scheduler prefix update; deliberately not wired into policy.

A feasible box step is a proposal-space constraint, not a promise about future
scheduler outputs, decoded/executed actions, contacts or task success.
"""
from typing import NamedTuple

import torch

SHAPE = (16, 8, 3)


class FeasibleRayResult(NamedTuple):
    prefix: torch.Tensor
    alpha: torch.Tensor  # FP32, one value per particle, shape (16,)


@torch.no_grad()
def feasible_ray_update(before: torch.Tensor, operand: torch.Tensor) -> FeasibleRayResult:
    """Scale each particle's existing update by its maximal FP32 feasible ray.

    Inputs are finite matching native FP32/BF16 tensors. Nonzero operands have
    strictly interior support. Inputs/RNG are unchanged. Zero-update positions
    retain the original bytes, even exterior values and signed zero. Only moving
    coordinates receive final FP32 box correction and a cast to native dtype;
    this finite-rounding correction does not promise exact ray collinearity.
    """
    if not isinstance(before, torch.Tensor) or not isinstance(operand, torch.Tensor):
        raise ValueError("N27 requires tensor inputs")
    if (before.layout != torch.strided or operand.layout != torch.strided
            or tuple(before.shape) != SHAPE or tuple(operand.shape) != SHAPE):
        raise ValueError("N27 requires strided (16,8,3) prefixes")
    if (before.dtype not in (torch.float32, torch.bfloat16)
            or operand.dtype != before.dtype):
        raise ValueError("N27 requires matching FP32/BF16 dtype")
    if before.device != operand.device or before.device.type not in ("cpu", "cuda"):
        raise ValueError("N27 requires matching CPU/CUDA device")
    if not bool(torch.isfinite(before).all()) or not bool(torch.isfinite(operand).all()):
        raise ValueError("N27 nonfinite input")
    moving = operand != 0
    interior = (before > -1) & (before < 1)
    if bool((moving & ~interior).any()):
        raise ValueError("N27 nonzero update outside strict-interior support")

    b = before.detach().float()
    d = operand.detach().float()
    # Zero operands have no ray constraint. Their denominator is never zero;
    # unbounded positive ratios for tiny nonzero d may be +inf legitimately.
    ones = torch.ones_like(d)
    boundary = torch.where(d > 0, ones, -ones)
    denominator = torch.where(moving, d, ones)
    ratios = torch.where(moving, (boundary - b) / denominator,
                         torch.full_like(d, float("inf")))
    alpha = ratios.flatten(1).amin(dim=1).clamp(max=1.0)
    candidate = b + alpha[:, None, None] * d
    corrected = candidate.clamp(-1.0, 1.0).to(dtype=before.dtype)
    prefix = torch.where(moving, corrected, before.detach())
    return FeasibleRayResult(prefix, alpha)
