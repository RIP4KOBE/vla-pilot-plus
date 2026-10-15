import pytest
import torch

from core.qd_ed import (cell_ids, direction_height_descriptor,
                        freeze_direction_height_bounds, height_aware_descriptor,
                        qd_descriptor)


def test_direction_height_exact_quadrants_height_bins_and_reference_modes():
    t = torch.zeros(16, 9, 3, dtype=torch.bfloat16)
    t[:, 8, 0] = torch.tensor([-.04, -.04, .04, .04] * 4).bfloat16()
    t[:, 8, 1] = torch.tensor([-.04, .04, -.04, .04] * 4).bfloat16()
    t[:, 8, 2] = torch.tensor([-.12] * 4 + [-.04] * 4 + [.04] * 4 + [.12] * 4).bfloat16()
    target = torch.zeros(1, 3, dtype=torch.bfloat16)
    old, n6 = qd_descriptor(t, target), height_aware_descriptor(t, target)
    n7 = direction_height_descriptor(t, target)
    assert n7.dtype == torch.float32 and n7.shape == (16, 2)
    assert n7[:4, 0].tolist() == [0., 1., 2., 3.]
    assert old[0, 0] == old[1, 0] and n6[0, 0] == n6[1, 0]
    bounds = freeze_direction_height_bounds(n7, quantiles=(.05, .95),
        expand_fraction=.1, min_axis_span_m=.08)
    assert bounds.lo[0] == -.5 and bounds.hi[0] == 3.5
    ids, overflow = cell_ids(n7, bounds, (4, 4))
    assert ids.shape == overflow.shape == (16,)
    assert ids[0] % 4 == 0 and ids[1] % 4 == 1
    assert ids[0] // 4 < ids[4] // 4


def test_direction_height_exact_zero_and_bad_inputs():
    t = torch.zeros(16, 9, 3)
    d = direction_height_descriptor(t, torch.zeros(1, 3))
    assert torch.equal(d[:, 0], torch.full((16,), 3.))
    with pytest.raises(ValueError):
        freeze_direction_height_bounds(torch.tensor([[1.5, 0.]]),
            quantiles=(.05, .95), expand_fraction=.1, min_axis_span_m=.08)
    t[0, 8, 2] = float('nan')
    with pytest.raises(FloatingPointError):
        direction_height_descriptor(t, torch.zeros(1, 3))
