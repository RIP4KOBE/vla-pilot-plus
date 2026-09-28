"""N9's native final-population reranker and N5 fallback invariants."""
import pytest
import torch

from core.qd_contact_sweep import select_contact_sweep
from core.qd_grasp_timing import GraspTimingSelection


def grasp(index=0, eligible=(0, 1, 2), target=0):
    return GraspTimingSelection(index, 0, eligible, target,
                                'recognized_weighted_distance_template' if target is not None
                                else 'requires_single_provider', None, None, None)


def test_lateral_sweep_changes_choice_only_inside_n5_and_reach_masks():
    costs = torch.full((16,), 10., dtype=torch.float32)
    costs[0], costs[1], costs[2], costs[3] = 0., .005, -.1, -.2
    positions = torch.zeros(16, 9, 3)
    positions[:, :, 0] = .2
    # Original choice crosses the target repeatedly; candidate 1 stays near it.
    positions[0, :, 0] = torch.tensor([0., .04, -.04, .04, -.04, .04, -.04, .04, -.04])
    positions[1, :, 0] = .01
    positions[2, :, 0] = .08  # Eligible, but >.02 m worse reach.
    positions[3, :, 0] = 0.   # Better native cost, but absent from N5's eligible set.
    result = select_contact_sweep(grasp(), costs, positions, torch.zeros(1, 3))
    assert result.index == 1 and result.grasp_index == 0
    assert result.candidate_mask.tolist()[:4] == [True, True, False, False]
    assert result.lateral_sweep_m[0] > result.lateral_sweep_m[1] + .01
    assert result.projected_reach_m[1] - result.projected_reach_m[0] <= .02


def test_no_recognized_target_retains_original_n5_choice():
    result = select_contact_sweep(grasp(index=4, eligible=(), target=None),
                                  None, None, None)
    assert result.index == result.grasp_index == 4
    assert result.lateral_sweep_m is None
    assert result.reason == 'requires_single_provider'


def test_nonfinite_native_projection_fails_closed():
    positions = torch.zeros(16, 9, 3)
    positions[0, 0, 0] = float('nan')
    with pytest.raises(FloatingPointError):
        select_contact_sweep(grasp(), torch.zeros(16), positions, torch.zeros(1, 3))
