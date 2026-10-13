from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.rdt_policy_steer import (
    _eds_direction_normalized_distance_components,
    _validate_direction_rbf_config,
)


CFG = {
    "direction_rbf_direction_weight": 0.6,
    "direction_rbf_shape_weight": 0.3,
    "direction_rbf_endpoint_weight": 0.1,
    "direction_rbf_endpoint_scale_m": 0.05,
    "direction_rbf_path_epsilon": 1.0e-6,
    "direction_rbf_distance_epsilon": 1.0e-6,
}


def _components(trajectories: torch.Tensor, **overrides):
    cfg = CFG | overrides
    return _eds_direction_normalized_distance_components(
        trajectories,
        direction_weight=cfg["direction_rbf_direction_weight"],
        shape_weight=cfg["direction_rbf_shape_weight"],
        endpoint_weight=cfg["direction_rbf_endpoint_weight"],
        endpoint_scale_m=cfg["direction_rbf_endpoint_scale_m"],
        path_epsilon=cfg["direction_rbf_path_epsilon"],
    )


def test_translation_and_uniform_scale_invariance_of_direction_and_shape():
    base = torch.tensor(
        [[[0.0, 0.0, 0.0], [0.02, 0.01, 0.0], [0.04, 0.03, 0.01]]]
    )
    translated = base + torch.tensor([3.0, -2.0, 7.0])
    population = torch.cat([base, translated], dim=0)
    result = _components(population)
    assert result["pairwise_direction"][0, 1].item() == pytest.approx(0.0, abs=2e-5)
    assert result["pairwise_shape"][0, 1].item() == pytest.approx(0.0, abs=2e-5)

    for scale in (0.5, 2.0, 4.0):
        scaled = torch.cat([base, base * scale], dim=0)
        result = _components(scaled)
        assert result["pairwise_direction"][0, 1].item() == pytest.approx(0.0, abs=2e-5)
        assert result["pairwise_shape"][0, 1].item() == pytest.approx(0.0, abs=2e-5)
        assert 0.0 <= result["pairwise_composite"][0, 1].item() < 0.1


def test_components_separate_direction_shape_and_bounded_endpoint():
    straight_x = torch.tensor([[0.0, 0.0, 0.0], [0.5, 0.0, 0.0], [1.0, 0.0, 0.0]])
    straight_y = torch.tensor([[0.0, 0.0, 0.0], [0.0, 0.5, 0.0], [0.0, 1.0, 0.0]])
    curved_x = torch.tensor([[0.0, 0.0, 0.0], [0.5, 0.5, 0.0], [1.0, 0.0, 0.0]])
    result = _components(torch.stack([straight_x, straight_y, curved_x]))
    assert result["pairwise_direction"][0, 1] > 0
    assert result["pairwise_shape"][0, 2] > 0
    assert torch.all(result["pairwise_endpoint"] < 1.0)
    assert torch.allclose(result["pairwise_composite"], result["pairwise_composite"].T)
    assert torch.count_nonzero(torch.diagonal(result["pairwise_composite"])) == 0


def test_zero_near_zero_and_extreme_finite_inputs_remain_finite():
    trajectories = torch.stack(
        [torch.zeros(4, 3), torch.full((4, 3), 1e-12), torch.full((4, 3), 1e4)]
    )
    result = _components(trajectories)
    assert result["zero_path"].sum().item() == 3
    for name in ("pairwise_direction", "pairwise_shape", "pairwise_endpoint", "pairwise_composite"):
        assert torch.isfinite(result[name]).all()


def test_bfloat16_descriptor_uses_finite_fp32_component_arithmetic():
    trajectories = torch.tensor(
        [[[0., 0., 0.], [.01, 0., 0.]], [[0., 0., 0.], [0., .01, 0.]]],
        dtype=torch.bfloat16,
        requires_grad=True,
    )
    result = _components(trajectories)
    assert result["pairwise_composite"].dtype == torch.float32
    result["pairwise_composite"].sum().backward()
    assert trajectories.grad is not None
    assert torch.isfinite(trajectories.grad).all()


@pytest.mark.parametrize(
    "override",
    [
        {"direction_rbf_direction_weight": -0.1},
        {"direction_rbf_direction_weight": 0.5},
        {"direction_rbf_endpoint_scale_m": 0.0},
        {"direction_rbf_path_epsilon": math.inf},
    ],
)
def test_invalid_direction_rbf_config_is_rejected(override):
    with pytest.raises(ValueError):
        _validate_direction_rbf_config(CFG | override)
