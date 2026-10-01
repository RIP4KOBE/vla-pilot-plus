"""N29 population-relative proposal distance; no policy/config wiring.

Empirical spread is a local descriptive scale, not calibrated uncertainty.
Exact native arithmetic is specified in the accompanying N29 document.
"""
from typing import NamedTuple

import torch

from core.qd_feasible_ray_update import feasible_ray_update

SHAPE = (16, 8, 3)


class PopulationRelativeTrustResult(NamedTuple):
    prefix: torch.Tensor
    alpha: torch.Tensor
    beta: torch.Tensor
    radius: torch.Tensor
    operand_norms: torch.Tensor
    scaled_operand: torch.Tensor


def _finite(value: torch.Tensor, name: str) -> None:
    if not bool(torch.isfinite(value).all()):
        raise ValueError("N29 nonfinite " + name)


@torch.no_grad()
def population_relative_trust_update(
    before: torch.Tensor, operand: torch.Tensor
) -> PopulationRelativeTrustResult:
    """Cap each existing operand at the FP32 population RMS radius, then N27.

    Inputs are unchanged. Raw nonzero support must already be strictly inside
    the box. Arithmetic overflow and norm/spread underflow fail closed; casts
    may round or zero a scaled coordinate. Zero *applied* updates keep the
    original bytes through the unchanged feasible-ray helper. No exact-real
    post-cast distance bound or model/action/task guarantee is claimed.
    """
    if not isinstance(before, torch.Tensor) or not isinstance(operand, torch.Tensor):
        raise ValueError("N29 requires tensor inputs")
    if (before.layout != torch.strided or operand.layout != torch.strided
            or tuple(before.shape) != SHAPE or tuple(operand.shape) != SHAPE):
        raise ValueError("N29 requires strided (16,8,3) prefixes")
    if before.dtype not in (torch.float32, torch.bfloat16) or operand.dtype != before.dtype:
        raise ValueError("N29 requires matching FP32/BF16 dtype")
    if before.device != operand.device or before.device.type not in ("cpu", "cuda"):
        raise ValueError("N29 requires matching CPU/CUDA device")
    _finite(before, "before input")
    _finite(operand, "operand input")
    moving = operand != 0
    interior = (before > -1) & (before < 1)
    if bool((moving & ~interior).any()):
        raise ValueError("N29 raw nonzero update outside strict-interior support")

    # Freeze mean/square/sum/mean/sqrt order; do not replace with std/norm.
    b = before.detach().to(torch.float32).reshape(16, 24)
    p = operand.detach().to(torch.float32).reshape(16, 24)
    mean = b.mean(dim=0)
    _finite(mean, "population mean")
    centered = b - mean
    _finite(centered, "centered population")
    centered_square = centered * centered
    _finite(centered_square, "centered square")
    row_energy = centered_square.sum(dim=1)
    _finite(row_energy, "centered row energy")
    mean_energy = row_energy.mean()
    _finite(mean_energy, "mean centered energy")
    radius = mean_energy.sqrt()
    _finite(radius, "radius")
    if bool((centered != 0).any()) and bool(radius == 0):
        raise ValueError("N29 nonzero population spread underflow")

    operand_square = p * p
    _finite(operand_square, "operand square")
    operand_energy = operand_square.sum(dim=1)
    _finite(operand_energy, "operand row energy")
    operand_norms = operand_energy.sqrt()
    _finite(operand_norms, "operand norm")
    raw_nonzero_rows = (p != 0).any(dim=1)
    if bool((raw_nonzero_rows & (operand_norms == 0)).any()):
        raise ValueError("N29 nonzero operand norm underflow")

    positive = operand_norms > 0
    denominator = torch.where(positive, operand_norms, torch.ones_like(operand_norms))
    ratio = radius / denominator
    _finite(ratio, "radius/norm ratio")
    beta = torch.where(positive, ratio.clamp(max=1.0), torch.ones_like(operand_norms))
    scaled_fp32 = p * beta[:, None]
    _finite(scaled_fp32, "scaled FP32 operand")
    scaled_operand = scaled_fp32.reshape(SHAPE).to(dtype=before.dtype)
    _finite(scaled_operand, "scaled native operand")
    box = feasible_ray_update(before, scaled_operand)
    return PopulationRelativeTrustResult(
        box.prefix, box.alpha, beta, radius, operand_norms, scaled_operand
    )
