import pytest
import torch

from core.qd_terminal_population import TerminalPopulation


def fixture(dtype=torch.bfloat16):
    actions = torch.arange(16, dtype=dtype)[:, None, None].expand(16, 64, 128).clone()
    costs = torch.arange(1000, 1016).to(dtype)
    cells = torch.arange(16)
    return actions, costs, -costs, cells, cells.clone()


@pytest.mark.parametrize('dtype', [torch.bfloat16, torch.float32])
def test_native_first_argmin_snapshot_and_occurrence(dtype):
    values = fixture(dtype)
    saved = TerminalPopulation.capture(*values, canonical_event_sequence=711,
                                       scoring_batch_id=700, decision_id='episode0:d0')
    assert saved.select_index() == 0
    assert saved.tie_indices() == ([0, 1, 2] if dtype == torch.bfloat16 else [0])
    assert saved.occurrence_id(0) == 'episode0:d0:q711:r0'
    assert saved.costs.dtype == saved.actions.dtype == dtype
    values[0].zero_(); values[1].zero_()
    assert saved.actions[15, 0, 0] == 15 and saved.costs[0] == 1000
    assert not torch.cuda.is_initialized()


@pytest.mark.parametrize('bad', ['shape', 'dtype', 'sign', 'nonfinite', 'cell', 'parent'])
def test_corrupt_native_batch_fails(bad):
    values = list(fixture())
    if bad == 'shape': values[1] = values[1].reshape(1, 16)
    if bad == 'dtype': values[1] = values[1].float()
    if bad == 'sign': values[1] = -values[1]
    if bad == 'nonfinite': values[0][0,0,0] = float('nan')
    if bad == 'cell': values[3][0] = 16
    if bad == 'parent': values[4] = values[4].float()
    with pytest.raises((RuntimeError, FloatingPointError)):
        TerminalPopulation.capture(*values)
