import importlib.util
from pathlib import Path

import pytest
import torch


_MODULE_PATH = Path(__file__).resolve().parents[1] / "core" / "rdt_libero_action_converter.py"
_SPEC = importlib.util.spec_from_file_location("rdt_libero_action_converter", _MODULE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Cannot load RDT LIBERO action converter from {_MODULE_PATH}")
_converter = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_converter)


LIBERO_STATE_INDICES = _converter.LIBERO_STATE_INDICES
LIBERO_ACTION_INDICES = _converter.LIBERO_ACTION_INDICES
ACTIVE_STATE_INDICES_SORTED = _converter.ACTIVE_STATE_INDICES_SORTED
ACTIVE_ACTION_INDICES_SORTED = _converter.ACTIVE_ACTION_INDICES_SORTED
LIBERO_RDT_INDICES = _converter.LIBERO_RDT_INDICES
ACTIVE_INDICES_SORTED = _converter.ACTIVE_INDICES_SORTED
decode_rdt_libero_action_chunk = _converter.decode_rdt_libero_action_chunk
rdt_action_to_libero_raw = _converter.rdt_action_to_libero_raw


def test_gt_state_and_action_indices_match_reference():
    assert LIBERO_STATE_INDICES == [0, 1, 2, 3, 4, 5, 6, 10, 11]
    assert ACTIVE_STATE_INDICES_SORTED == [0, 1, 2, 3, 4, 5, 6, 10, 11]
    assert LIBERO_ACTION_INDICES == [39, 40, 41, 42, 43, 44, 10]
    assert ACTIVE_ACTION_INDICES_SORTED == [10, 39, 40, 41, 42, 43, 44]
    assert LIBERO_RDT_INDICES == LIBERO_ACTION_INDICES
    assert ACTIVE_INDICES_SORTED == ACTIVE_STATE_INDICES_SORTED


def test_decode_extracts_gt_action_slots_directly():
    pred = torch.zeros(1, 64, 128, dtype=torch.float32)
    pred[0, 0, 39:45] = torch.tensor([0.11, -0.22, 0.33, -0.44, 0.55, -0.66])
    pred[0, 0, 10] = -0.01
    pred[0, 1, 39:45] = torch.tensor([-0.10, 0.20, -0.30, 0.40, -0.50, 0.60])
    pred[0, 1, 10] = 0.01

    decoded = decode_rdt_libero_action_chunk(pred, action_chunk_horizon=2)

    assert tuple(decoded.shape) == (1, 2, 7)
    torch.testing.assert_close(
        decoded[0, 0],
        torch.tensor([0.11, -0.22, 0.33, -0.44, 0.55, -0.66, -1.0]),
    )
    torch.testing.assert_close(
        decoded[0, 1],
        torch.tensor([-0.10, 0.20, -0.30, 0.40, -0.50, 0.60, 1.0]),
    )


def test_decode_ignores_old_eef_pose_slots_30_to_38():
    pred = torch.zeros(1, 64, 128, dtype=torch.float32)
    pred[0, 0, 30:39] = torch.tensor([9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0])
    pred[0, 0, 39:45] = torch.tensor([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
    pred[0, 0, 10] = 123.0

    decoded = decode_rdt_libero_action_chunk(pred, action_chunk_horizon=1)

    torch.testing.assert_close(
        decoded[0, 0],
        torch.tensor([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 1.0]),
    )


def test_rdt_action_to_libero_raw_preserves_batch_shape():
    action = torch.zeros(2, 3, 128, dtype=torch.float32)
    action[:, :, 39] = 0.5
    action[:, :, 40] = -0.25
    action[:, :, 41] = 0.125
    action[:, :, 42] = -0.5
    action[:, :, 43] = 0.25
    action[:, :, 44] = -0.125
    action[:, :, 10] = -2.0

    decoded = rdt_action_to_libero_raw(action)

    assert tuple(decoded.shape) == (2, 3, 7)
    expected_arm = torch.tensor([0.5, -0.25, 0.125, -0.5, 0.25, -0.125]).expand_as(decoded[..., :6])
    torch.testing.assert_close(decoded[..., :6], expected_arm)
    assert torch.all(decoded[..., 6] == -1.0)


def test_decode_rejects_wrong_action_shape():
    with pytest.raises(ValueError, match="128"):
        decode_rdt_libero_action_chunk(torch.zeros(1, 64, 7), action_chunk_horizon=8)

    with pytest.raises(ValueError, match="64|128"):
        decode_rdt_libero_action_chunk(torch.zeros(1, 63, 128), action_chunk_horizon=8)

    with pytest.raises(ValueError, match="batch|particle|empty"):
        decode_rdt_libero_action_chunk(torch.zeros(0, 64, 128), action_chunk_horizon=8)

    with pytest.raises(ValueError, match="horizon"):
        decode_rdt_libero_action_chunk(torch.zeros(1, 64, 128), action_chunk_horizon=0)
