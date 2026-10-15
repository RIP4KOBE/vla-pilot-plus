"""N5 selection tests using native terminal rows and projected eight-step actions."""
import pytest
import torch

from core.qd_grasp_timing import select_grasp_timing
from core.qd_terminal_population import TerminalPopulation


@pytest.mark.parametrize("dtype", [torch.float32, torch.bfloat16])
def test_close_command_must_coincide_with_competitive_reach(dtype):
    actions = torch.zeros(16, 64, 128, dtype=dtype)
    costs = torch.full((16,), 2., dtype=dtype)
    costs[0], costs[1], costs[2] = 0., 1., -1.
    cells = torch.arange(16, dtype=torch.long)
    terminal = TerminalPopulation.capture(actions, costs, -costs, cells, cells)
    projected = torch.zeros(16, 9, 3, dtype=dtype)
    projected[:, :, 0] = .2
    projected[0, 4, 0] = .02  # Best reach has an open command.
    projected[1, 4, 0] = .045  # Close command at a competitive approach.
    projected[2, 4, 0] = .08  # Better native cost, but closes too far away.
    projected[3, 4, 0] = .03  # Close approach and positive command occur at different times.
    decoded = torch.zeros(16, 8, 7)
    decoded[:, :, 6] = -1
    decoded[1, 3, 6] = 1
    decoded[2, 3, 6] = 1
    decoded[3, 0, 6] = 1
    result = select_grasp_timing(terminal, projected, decoded,
                                 torch.zeros(1, 3, dtype=dtype), target_index=0,
                                 recognition_reason="recognized_weighted_distance_template")
    assert result.native_argmin_index == 2
    assert result.eligible_indices == (1,)
    assert result.index == 1
    assert result.projected_distances_m.shape == (16, 8)


def test_unsupported_semantics_falls_back_and_invalid_native_data_fails_closed():
    actions = torch.zeros(16, 64, 128)
    costs = torch.arange(16, dtype=torch.float32)
    cells = torch.arange(16, dtype=torch.long)
    terminal = TerminalPopulation.capture(actions, costs, -costs, cells, cells)
    fallback = select_grasp_timing(terminal, None, None, None, target_index=None,
                                   recognition_reason="requires_single_provider")
    assert fallback.index == 0 and fallback.target_index is None
    projected = torch.zeros(16, 9, 3)
    decoded = torch.zeros(16, 8, 7)
    decoded[:, :, 6] = -1
    decoded[1, 0, 6] = float("nan")
    with pytest.raises(FloatingPointError):
        select_grasp_timing(terminal, projected, decoded, torch.zeros(1, 3),
                            target_index=0, recognition_reason="recognized_weighted_distance_template")
