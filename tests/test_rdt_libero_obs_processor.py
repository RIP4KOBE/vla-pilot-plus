import importlib.util
import sys
from pathlib import Path

import pytest
import torch

# Load by file path to bypass core/__init__.py optional dependency side effects.
_MODULE_PATH = Path(__file__).resolve().parents[1] / "core" / "rdt_libero_obs_processor.py"
_SPEC = importlib.util.spec_from_file_location("rdt_libero_obs_processor", _MODULE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Cannot load RDT LIBERO observation processor from {_MODULE_PATH}")
_processor_module = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _processor_module
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


def _assert_pil_color(image, expected_rgb):
    from PIL import Image

    assert isinstance(image, Image.Image)
    assert image.getpixel((0, 0)) == expected_rgb


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
    _assert_pil_color(converted.images[0], (255, 0, 0))
    _assert_pil_color(converted.images[1], (0, 255, 0))
    _assert_pil_color(converted.images[3], (255, 0, 0))
    _assert_pil_color(converted.images[4], (0, 255, 0))


def test_second_call_uses_previous_and_current_frames():
    processor = RDTLiberoObsProcessor()
    first_obs = _obs()
    second_obs = _obs()
    second_obs["observation.images.image"] = _image_batch(0.0, 0.0, 1.0)
    second_obs["observation.images.image2"] = _image_batch(1.0, 1.0, 0.0)

    processor.process(first_obs)
    converted = processor.process(second_obs)

    assert len(converted.images) == 6
    _assert_pil_color(converted.images[0], (255, 0, 0))
    _assert_pil_color(converted.images[1], (0, 255, 0))
    assert converted.images[2] is None
    _assert_pil_color(converted.images[3], (0, 0, 255))
    _assert_pil_color(converted.images[4], (255, 255, 0))
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

    _assert_pil_color(converted.images[0], (0, 0, 255))
    _assert_pil_color(converted.images[1], (255, 255, 0))
    _assert_pil_color(converted.images[3], (0, 0, 255))
    _assert_pil_color(converted.images[4], (255, 255, 0))


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


def test_non_string_task_raises_value_error():
    processor = RDTLiberoObsProcessor()

    with pytest.raises(ValueError, match="task|string"):
        processor.process(_obs(task=None))


def test_bad_image_channel_shape_raises_value_error():
    processor = RDTLiberoObsProcessor()
    obs = _obs()
    obs["observation.images.image"] = torch.zeros((1, 1, 8, 8), dtype=torch.float32)

    with pytest.raises(ValueError, match=r"\(B, 3, H, W\)|3"):
        processor.process(obs)


def test_non_finite_image_raises_value_error():
    processor = RDTLiberoObsProcessor()
    obs = _obs()
    obs["observation.images.image"][0, 0, 0, 0] = torch.nan

    with pytest.raises(ValueError, match="finite"):
        processor.process(obs)


def test_image_outside_unit_range_raises_value_error():
    processor = RDTLiberoObsProcessor()
    obs = _obs()
    obs["observation.images.image"] = torch.full((1, 3, 8, 8), 255.0, dtype=torch.float32)

    with pytest.raises(ValueError, match=r"\[0, 1\]|range"):
        processor.process(obs)


def test_bad_state_shape_raises_value_error():
    processor = RDTLiberoObsProcessor()
    obs = _obs()
    obs["observation.state"] = torch.zeros((1, 7), dtype=torch.float32)

    with pytest.raises(ValueError, match="8"):
        processor.process(obs)


@pytest.mark.parametrize("batch_size", [0, 2])
def test_bad_state_batch_shape_raises_value_error(batch_size):
    processor = RDTLiberoObsProcessor()
    obs = _obs()
    obs["observation.state"] = torch.zeros((batch_size, 8), dtype=torch.float32)

    with pytest.raises(ValueError, match=r"\(1, 8\)|batch"):
        processor.process(obs)


def test_extra_state_dimension_raises_value_error():
    processor = RDTLiberoObsProcessor()
    obs = _obs()
    obs["observation.state"] = torch.zeros((1, 9), dtype=torch.float32)

    with pytest.raises(ValueError, match="8"):
        processor.process(obs)
