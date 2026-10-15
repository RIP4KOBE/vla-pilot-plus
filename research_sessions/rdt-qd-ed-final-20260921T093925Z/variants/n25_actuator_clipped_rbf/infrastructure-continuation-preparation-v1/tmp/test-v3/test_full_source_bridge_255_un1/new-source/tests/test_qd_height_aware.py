import pytest
import torch

from core.qd_ed import height_aware_descriptor, qd_descriptor, freeze_bounds, cell_ids


def test_height_aware_descriptor_separates_vertical_approaches_collapsed_by_xy():
    trajectories = torch.zeros(16, 9, 3, dtype=torch.bfloat16)
    trajectories[:, 8, 0] = torch.tensor([.02, .02, .04, .04] * 4).bfloat16()
    trajectories[:, 8, 2] = torch.tensor([-.12, -.04, .04, .12] * 4).bfloat16()
    target = torch.zeros(1, 3, dtype=torch.bfloat16)
    old = qd_descriptor(trajectories, target)
    new = height_aware_descriptor(trajectories, target)
    assert old[0].tolist() == old[1].tolist()
    assert new[0, 0] == new[1, 0] and new[0, 1] < new[1, 1]
    assert new.dtype == torch.float32 and new.shape == (16, 2)
    bounds = freeze_bounds(new, quantiles=(.05, .95), expand_fraction=.1, min_axis_span_m=.08)
    ids, _ = cell_ids(new, bounds, (4, 4))
    assert ids[0] != ids[1]


def test_height_aware_descriptor_fails_closed_on_nonfinite_projection():
    trajectories = torch.zeros(16, 9, 3)
    trajectories[0, 8, 2] = float('nan')
    with pytest.raises(FloatingPointError):
        height_aware_descriptor(trajectories, torch.zeros(1, 3))
