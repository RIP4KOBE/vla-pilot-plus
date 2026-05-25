import importlib.util
from pathlib import Path

import pytest
import torch

_MODULE_PATH = Path(__file__).resolve().parents[1] / "core" / "rdt_libero_obs_processor.py"
_SPEC = importlib.util.spec_from_file_location("rdt_libero_obs_processor", _MODULE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Cannot load RDT LIBERO observation processor from {_MODULE_PATH}")
_processor_module = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_processor_module)

RDTLiberoObsProcessor = _processor_module.RDTLiberoObsProcessor


def _image_batch(red, green, blue):
    image = torch.zeros((1, 3, 8, 8), dtype=torch.float32)
    image[:, 0] = red
    image[:, 1] = green
    image[:, 2] = blue
    return image


def _obs(task="pick up the mug"):
    return {
        "observation.images.image": _image_batch(1.0, 0.0, 0.0),
        "observation.images.image2": _image_batch(0.0, 1.0, 0.0),
        "observation.state": torch.tensor(
            [[0.10, -0.20, 0.80, 0.0, 0.0, 0.0, 0.04, -0.04]],
            dtype=torch.float32,
        ),
        "task": task,
    }


def test_process_builds_state_and_mask_contract():
    processor = RDTLiberoObsProcessor()

    converted = processor.process(_obs())

    assert tuple(converted.state_128.shape) == (1, 128)
    assert tuple(converted.state_mask_128.shape) == (1, 128)
    assert torch.nonzero(converted.state_mask_128[0], as_tuple=False).flatten().tolist() == [
        10,
        30,
        31,
        32,
        33,
        34,
        35,
        36,
        37,
        38,
    ]
    torch.testing.assert_close(converted.state_128[0, 30:33], torch.tensor([0.10, -0.20, 0.80]))
    torch.testing.assert_close(
        converted.state_128[0, 33:39],
        torch.tensor([1.0, 0.0, 0.0, 0.0, 1.0, 0.0]),
    )
    assert converted.state_128[0, 10].item() == pytest.approx(1.0)


def test_process_preserves_task_string():
    processor = RDTLiberoObsProcessor()

    converted = processor.process(_obs(task="open the drawer"))

    assert converted.task == "open the drawer"


def test_first_frame_history_duplicates_current_frame():
    processor = RDTLiberoObsProcessor()
    obs = _obs()

    converted = processor.process(obs)

    assert len(converted.images) == 6
    assert converted.images[2] is None
    assert converted.images[5] is None
    torch.testing.assert_close(converted.images[0], obs["observation.images.image"])
    torch.testing.assert_close(converted.images[1], obs["observation.images.image2"])
    torch.testing.assert_close(converted.images[3], obs["observation.images.image"])
    torch.testing.assert_close(converted.images[4], obs["observation.images.image2"])


def test_second_call_uses_previous_and_current_frames():
    processor = RDTLiberoObsProcessor()
    first_obs = _obs()
    second_obs = _obs()
    second_obs["observation.images.image"] = _image_batch(0.0, 0.0, 1.0)
    second_obs["observation.images.image2"] = _image_batch(1.0, 1.0, 0.0)

    processor.process(first_obs)
    converted = processor.process(second_obs)

    assert len(converted.images) == 6
    torch.testing.assert_close(converted.images[0], first_obs["observation.images.image"])
    torch.testing.assert_close(converted.images[1], first_obs["observation.images.image2"])
    assert converted.images[2] is None
    torch.testing.assert_close(converted.images[3], second_obs["observation.images.image"])
    torch.testing.assert_close(converted.images[4], second_obs["observation.images.image2"])
    assert converted.images[5] is None


def test_reset_clears_image_history():
    processor = RDTLiberoObsProcessor()
    first_obs = _obs()
    second_obs = _obs()
    second_obs["observation.images.image"] = _image_batch(0.0, 0.0, 1.0)
    second_obs["observation.images.image2"] = _image_batch(1.0, 1.0, 0.0)

    processor.process(first_obs)
    processor.reset()
    converted = processor.process(second_obs)

    torch.testing.assert_close(converted.images[0], second_obs["observation.images.image"])
    torch.testing.assert_close(converted.images[1], second_obs["observation.images.image2"])
    torch.testing.assert_close(converted.images[3], second_obs["observation.images.image"])
    torch.testing.assert_close(converted.images[4], second_obs["observation.images.image2"])


def test_missing_wrist_image_raises_key_error():
    processor = RDTLiberoObsProcessor()
    obs = _obs()
    obs.pop("observation.images.image2")

    with pytest.raises(KeyError, match="observation.images.image2"):
        processor.process(obs)


def test_empty_language_raises_value_error():
    processor = RDTLiberoObsProcessor()

    with pytest.raises(ValueError, match="empty"):
        processor.process(_obs(task=""))


def test_bad_state_shape_raises_value_error():
    processor = RDTLiberoObsProcessor()
    obs = _obs()
    obs["observation.state"] = torch.zeros((1, 7), dtype=torch.float32)

    with pytest.raises(ValueError, match="8"):
        processor.process(obs)
