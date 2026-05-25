import importlib.util
from pathlib import Path

import numpy as np
import pytest
import torch

_MODULE_PATH = Path(__file__).resolve().parents[1] / "core" / "rdt_libero_action_converter.py"
_SPEC = importlib.util.spec_from_file_location("rdt_libero_action_converter", _MODULE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Cannot load RDT LIBERO action converter from {_MODULE_PATH}")
_converter = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_converter)

LIBERO_RDT_INDICES = _converter.LIBERO_RDT_INDICES
ACTIVE_INDICES_SORTED = _converter.ACTIVE_INDICES_SORTED
decode_rdt_libero_action_chunk = _converter.decode_rdt_libero_action_chunk
libero_raw_to_rdt_action = _converter.libero_raw_to_rdt_action
map_libero_gripper_action_to_open = _converter.map_libero_gripper_action_to_open
map_open_to_libero_gripper = _converter.map_open_to_libero_gripper
ortho6d_to_rotvec = _converter.ortho6d_to_rotvec
rdt_action_to_libero_raw = _converter.rdt_action_to_libero_raw
rotvec_to_ortho6d = _converter.rotvec_to_ortho6d


def test_active_indices_match_finetuning_contract():
    assert LIBERO_RDT_INDICES == [30, 31, 32, 33, 34, 35, 36, 37, 38, 10]
    assert ACTIVE_INDICES_SORTED == [10, 30, 31, 32, 33, 34, 35, 36, 37, 38]


def test_gripper_mapping_is_exact_inverse_at_endpoints():
    raw = np.array([-1.0, 1.0, 0.0], dtype=np.float32)
    opened = map_libero_gripper_action_to_open(raw)
    np.testing.assert_allclose(opened, np.array([1.0, 0.0, 0.5], dtype=np.float32))

    restored = map_open_to_libero_gripper(opened)
    np.testing.assert_allclose(restored, raw)


def test_rotvec_ortho6d_roundtrip_small_rotation():
    rotvec = np.array([[0.05, -0.10, 0.15], [0.0, 0.0, 0.0]], dtype=np.float32)
    ortho6d = rotvec_to_ortho6d(rotvec)
    recovered = ortho6d_to_rotvec(ortho6d)
    np.testing.assert_allclose(recovered, rotvec, atol=1e-6)


def test_raw_action_roundtrip_matches_training_transform():
    raw = np.array([0.5, -0.25, 0.25, 0.1, -0.2, 0.3, -1.0], dtype=np.float32)
    action_128 = libero_raw_to_rdt_action(raw)

    assert action_128.shape == (128,)
    np.testing.assert_allclose(
        action_128[30:33], np.array([0.025, -0.0125, 0.0125], dtype=np.float32)
    )
    np.testing.assert_allclose(
        action_128[33:39],
        rotvec_to_ortho6d(np.array([[0.05, -0.10, 0.15]], dtype=np.float32))[0],
    )
    assert action_128[10] == pytest.approx(1.0)

    restored = rdt_action_to_libero_raw(action_128)
    np.testing.assert_allclose(restored[:6], raw[:6], atol=1e-5)
    assert restored[6] == pytest.approx(-1.0)


def test_decode_chunk_returns_torch_1_h_7_and_clips_controller_range():
    pred = torch.zeros(2, 64, 128, dtype=torch.float32)
    pred[0, 0, 30:33] = torch.tensor([0.10, -0.10, 0.025])
    pred[0, 0, 33:39] = torch.from_numpy(
        rotvec_to_ortho6d(np.array([[1.0, 0.0, 0.0]], dtype=np.float32))[0]
    )
    pred[0, 0, 10] = 1.0

    decoded = decode_rdt_libero_action_chunk(pred, action_chunk_horizon=8)

    assert tuple(decoded.shape) == (1, 8, 7)
    assert decoded.dtype == torch.float32
    assert torch.all(decoded <= 1.0)
    assert torch.all(decoded >= -1.0)
    torch.testing.assert_close(decoded[0, 0, :3], torch.tensor([1.0, -1.0, 0.5]))
    assert decoded[0, 0, 6].item() == pytest.approx(-1.0)


def test_decode_rejects_wrong_action_shape():
    with pytest.raises(ValueError, match="128"):
        decode_rdt_libero_action_chunk(torch.zeros(1, 64, 7), action_chunk_horizon=8)

    with pytest.raises(ValueError, match="64|128"):
        decode_rdt_libero_action_chunk(torch.zeros(1, 63, 128), action_chunk_horizon=8)
