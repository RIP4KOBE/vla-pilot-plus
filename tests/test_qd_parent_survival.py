import pytest
import torch

from core.qd_ed import select_parent_survivor_slots


def test_four_survivors_rank_quality_and_keep_distinct_cells():
    rewards = torch.tensor([0.2, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3,
                            0.1, 0.0, -0.1, -0.2, -0.3, -0.4, -0.5, -0.6])
    cells = torch.tensor([1, 2, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15])
    assert select_parent_survivor_slots(rewards, cells, 4) == (1, 3, 4, 5)
    assert select_parent_survivor_slots(rewards, cells, 0) == ()
    assert select_parent_survivor_slots(torch.zeros(16), torch.zeros(16, dtype=torch.long), 4) == (0,)


def test_survivor_selection_fails_closed_on_bad_input():
    for count in (True, -1, 1, 5):
        with pytest.raises(ValueError):
            select_parent_survivor_slots(torch.zeros(16), torch.arange(16), count)
    with pytest.raises(FloatingPointError):
        select_parent_survivor_slots(torch.full((16,), float('nan')), torch.arange(16), 4)
    with pytest.raises(ValueError):
        select_parent_survivor_slots(torch.zeros(15), torch.arange(15), 4)
