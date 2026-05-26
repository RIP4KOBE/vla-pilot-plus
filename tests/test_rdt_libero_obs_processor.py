import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest
import torch


_MODULE_PATH = Path(__file__).resolve().parents[1] / "core" / "rdt_libero_obs_processor.py"
_SPEC = importlib.util.spec_from_file_location("rdt_libero_obs_processor", _MODULE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Cannot load RDT LIBERO observation processor from {_MODULE_PATH}")
_processor_module = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _processor_module
_SPEC.loader.exec_module(_processor_module)


RDTLiberoObsProcessor = _processor_module.RDTLiberoObsProcessor
GRIPPER_MIN = _processor_module.GRIPPER_MIN
GRIPPER_MAX = _processor_module.GRIPPER_MAX


def _image(red, green, blue):
    image = np.zeros((8, 8, 3), dtype=np.uint8)
    image[..., 0] = red
    image[..., 1] = green
    image[..., 2] = blue
    return image


def _obs(task="pick up the mug"):
    return {
        "agentview_image": _image(255, 0, 0),
        "robot0_eye_in_hand_image": _image(0, 255, 0),
        "robot0_joint_pos": np.array([0.0, 0.1, 0.2, 0.3, -0.1, -0.2, -0.3], dtype=np.float32),
        "robot0_gripper_qpos": np.array([GRIPPER_MIN, GRIPPER_MAX], dtype=np.float32),
        "task": task,
    }


def _assert_pil_color(image, expected_rgb):
    from PIL import Image

    assert isinstance(image, Image.Image)
    assert image.getpixel((0, 0)) == expected_rgb


def test_process_builds_gt_joint_state_and_mask_contract():
    processor = RDTLiberoObsProcessor()

    converted = processor.process(_obs())

    assert tuple(converted.state_128.shape) == (1, 128)
    assert tuple(converted.state_mask_128.shape) == (1, 128)
    assert torch.nonzero(converted.state_mask_128[0], as_tuple=False).flatten().tolist() == [
        0,
        1,
        2,
        3,
        4,
        5,
        6,
        10,
        11,
    ]
    torch.testing.assert_close(
        converted.state_128[0, :7],
        torch.tensor([0.0, 0.1, 0.2, 0.3, -0.1, -0.2, -0.3]),
    )
    assert converted.state_128[0, 10].item() == pytest.approx(0.0)
    assert converted.state_128[0, 11].item() == pytest.approx(1.0)


def test_process_preserves_task_string():
    processor = RDTLiberoObsProcessor()

    converted = processor.process(_obs(task="open the drawer"))

    assert converted.task == "open the drawer"


def test_debug_first_step_logs_observation_summary_once(caplog):
    processor = RDTLiberoObsProcessor(debug_first_step=True)

    with caplog.at_level("WARNING"):
        processor.process(_obs(task="pick up the mug"))
        processor.process(_obs(task="open the drawer"))

    messages = [record.getMessage() for record in caplog.records if "[RDT_LIBERO_OBS]" in record.getMessage()]
    assert len(messages) == 1
    message = messages[0]
    assert "task='pick up the mug'" in message
    assert "image_sizes=[(8, 8), (8, 8), None, (8, 8), (8, 8), None]" in message
    assert "state_active=[0, 1, 2, 3, 4, 5, 6, 10, 11]" in message
    assert "joint_min=-0.3000" in message
    assert "joint_max=0.3000" in message
    assert "gripper_norm=[0.0, 1.0]" in message


def test_first_frame_history_duplicates_initial_raw_frames():
    processor = RDTLiberoObsProcessor()

    converted = processor.process(_obs())

    assert len(converted.images) == 6
    _assert_pil_color(converted.images[0], (255, 0, 0))
    _assert_pil_color(converted.images[1], (0, 255, 0))
    assert converted.images[2] is None
    _assert_pil_color(converted.images[3], (255, 0, 0))
    _assert_pil_color(converted.images[4], (0, 255, 0))
    assert converted.images[5] is None


def test_second_call_uses_adjacent_previous_and_current_frames():
    processor = RDTLiberoObsProcessor()
    first_obs = _obs()
    second_obs = _obs()
    second_obs["agentview_image"] = _image(0, 0, 255)
    second_obs["robot0_eye_in_hand_image"] = _image(255, 255, 0)

    processor.process(first_obs)
    converted = processor.process(second_obs)

    _assert_pil_color(converted.images[0], (255, 0, 0))
    _assert_pil_color(converted.images[1], (0, 255, 0))
    assert converted.images[2] is None
    _assert_pil_color(converted.images[3], (0, 0, 255))
    _assert_pil_color(converted.images[4], (255, 255, 0))
    assert converted.images[5] is None


def test_observe_updates_history_without_rebuilding_chunk():
    processor = RDTLiberoObsProcessor()
    first_obs = _obs()
    second_obs = _obs()
    third_obs = _obs()
    second_obs["agentview_image"] = _image(0, 0, 255)
    second_obs["robot0_eye_in_hand_image"] = _image(255, 255, 0)
    third_obs["agentview_image"] = _image(10, 20, 30)
    third_obs["robot0_eye_in_hand_image"] = _image(40, 50, 60)

    processor.process(first_obs)
    processor.observe(second_obs)
    converted = processor.process(third_obs)

    _assert_pil_color(converted.images[0], (0, 0, 255))
    _assert_pil_color(converted.images[1], (255, 255, 0))
    _assert_pil_color(converted.images[3], (10, 20, 30))
    _assert_pil_color(converted.images[4], (40, 50, 60))


def test_failed_observe_does_not_mutate_history():
    processor = RDTLiberoObsProcessor()
    first = _obs()
    processor.process(first)

    bad = _obs()
    bad["agentview_image"] = _image(0, 0, 255)
    bad["robot0_eye_in_hand_image"] = _image(255, 255, 0)
    bad["robot0_joint_pos"] = np.zeros((8,), dtype=np.float32)

    with pytest.raises(ValueError, match="robot0_joint_pos"):
        processor.observe(bad)

    current = processor.current()
    _assert_pil_color(current.images[0], (255, 0, 0))
    _assert_pil_color(current.images[3], (255, 0, 0))


def test_current_returns_copies_not_internal_references():
    processor = RDTLiberoObsProcessor()
    processor.process(_obs())

    converted = processor.current()
    converted.state_128[0, 0] = 999.0
    converted.state_mask_128[0, 0] = 0.0
    converted.images[0].putpixel((0, 0), (1, 2, 3))

    fresh = processor.current()
    assert fresh.state_128[0, 0].item() != pytest.approx(999.0)
    assert fresh.state_mask_128[0, 0].item() == pytest.approx(1.0)
    _assert_pil_color(fresh.images[0], (255, 0, 0))


def test_reset_clears_history_and_duplicates_new_initial_frame():
    processor = RDTLiberoObsProcessor()
    processor.process(_obs())
    processor.reset()
    obs = _obs()
    obs["agentview_image"] = _image(0, 0, 255)
    obs["robot0_eye_in_hand_image"] = _image(255, 255, 0)

    converted = processor.process(obs)

    _assert_pil_color(converted.images[0], (0, 0, 255))
    _assert_pil_color(converted.images[3], (0, 0, 255))
    _assert_pil_color(converted.images[1], (255, 255, 0))
    _assert_pil_color(converted.images[4], (255, 255, 0))


def test_missing_raw_wrist_image_raises_key_error():
    processor = RDTLiberoObsProcessor()
    obs = _obs()
    obs.pop("robot0_eye_in_hand_image")

    with pytest.raises(KeyError, match="robot0_eye_in_hand_image"):
        processor.process(obs)


def test_bad_image_dtype_raises_value_error():
    processor = RDTLiberoObsProcessor()
    obs = _obs()
    obs["agentview_image"] = obs["agentview_image"].astype(np.float32)

    with pytest.raises(ValueError, match="uint8"):
        processor.process(obs)


def test_bad_joint_shape_raises_value_error():
    processor = RDTLiberoObsProcessor()
    obs = _obs()
    obs["robot0_joint_pos"] = np.zeros((8,), dtype=np.float32)

    with pytest.raises(ValueError, match="robot0_joint_pos"):
        processor.process(obs)


def test_nan_joint_pos_raises_value_error():
    processor = RDTLiberoObsProcessor()
    obs = _obs()
    obs["robot0_joint_pos"][0] = np.nan

    with pytest.raises(ValueError, match="robot0_joint_pos"):
        processor.process(obs)


def test_inf_joint_pos_raises_value_error():
    processor = RDTLiberoObsProcessor()
    obs = _obs()
    obs["robot0_joint_pos"][0] = np.inf

    with pytest.raises(ValueError, match="robot0_joint_pos"):
        processor.process(obs)


def test_bad_gripper_shape_raises_value_error():
    processor = RDTLiberoObsProcessor()
    obs = _obs()
    obs["robot0_gripper_qpos"] = np.zeros((1,), dtype=np.float32)

    with pytest.raises(ValueError, match="robot0_gripper_qpos"):
        processor.process(obs)


def test_nan_gripper_qpos_raises_value_error():
    processor = RDTLiberoObsProcessor()
    obs = _obs()
    obs["robot0_gripper_qpos"][0] = np.nan

    with pytest.raises(ValueError, match="robot0_gripper_qpos"):
        processor.process(obs)


def test_out_of_range_gripper_qpos_raises_value_error():
    processor = RDTLiberoObsProcessor()
    obs = _obs()
    obs["robot0_gripper_qpos"] = np.array([-1.0, 1.0], dtype=np.float32)

    with pytest.raises(ValueError, match="robot0_gripper_qpos"):
        processor.process(obs)


def test_empty_language_raises_value_error():
    processor = RDTLiberoObsProcessor()

    with pytest.raises(ValueError, match="empty"):
        processor.process(_obs(task=""))
