import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.guidance_utils import load_functions_from_txt


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
