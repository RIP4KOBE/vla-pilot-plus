import sys
from pathlib import Path

import torch
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.guidance_utils import UnsafeGuidanceCode, load_functions_from_txt


def test_load_functions_accepts_numeric_zero_guidance(tmp_path):
    guidance_path = tmp_path / "stage2_guidance.txt"
    guidance_path.write_text(
        "def stage2_guidance(keypoints, trajectory_3d):\n"
        "    return 0\n",
        encoding="utf-8",
    )

    functions = load_functions_from_txt(str(guidance_path), validate=True)

    trajectory = torch.randn(1, 10, 3, dtype=torch.float64)
    keypoints = torch.randn(4, 3, dtype=torch.float64)
    result = functions[0](keypoints, trajectory)

    assert isinstance(result, torch.Tensor)
    assert result.device == trajectory.device
    assert result.dtype == trajectory.dtype
    assert result.shape == torch.Size([])
    assert result.item() == 0.0


def test_guidance_ast_accepts_tensor_expression_program(tmp_path):
    guidance_path = tmp_path / "stage1_guidance.txt"
    guidance_path.write_text(
        "num_stages = 1\n"
        "def stage1_guidance(keypoints, action_sequence):\n"
        "    T = action_sequence.shape[1]\n"
        "    steps = torch.arange(T, device=action_sequence.device)\n"
        "    weights = torch.where(steps >= int(0.7 * T), "
        "torch.tensor(3.0, device=action_sequence.device), "
        "torch.tensor(1.0, device=action_sequence.device))\n"
        "    target = keypoints[torch.tensor([1], dtype=torch.long, "
        "device=keypoints.device)][0]\n"
        "    reward = -(torch.norm(action_sequence - target, dim=-1) ** 2 "
        "* weights).sum(dim=1)\n"
        "    return reward.mean()\n",
        encoding="utf-8",
    )

    function = load_functions_from_txt(str(guidance_path), validate=True)[0]
    keypoints = torch.randn(4, 3)
    trajectory = torch.randn(2, 10, 3, requires_grad=True)
    reward = function(keypoints, trajectory)
    reward.backward()

    assert reward.ndim == 0
    assert trajectory.grad is not None


@pytest.mark.parametrize(
    "payload",
    [
        "import os\ndef stage1_guidance(keypoints, action_sequence):\n    return 0\n",
        "def stage1_guidance(keypoints, action_sequence):\n"
        "    return open('/tmp/pwned', 'w')\n",
        "def stage1_guidance(keypoints, action_sequence):\n"
        "    for item in action_sequence:\n        pass\n    return 0\n",
        "def stage1_guidance(keypoints, action_sequence):\n"
        "    return torch.save(action_sequence, '/tmp/pwned')\n",
        "def stage1_guidance(keypoints, action_sequence):\n"
        "    return action_sequence.__class__\n",
    ],
)
def test_guidance_ast_rejects_side_effects(payload, tmp_path):
    guidance_path = tmp_path / "stage1_guidance.txt"
    guidance_path.write_text(payload, encoding="utf-8")

    with pytest.raises(UnsafeGuidanceCode):
        load_functions_from_txt(str(guidance_path), validate=False)
