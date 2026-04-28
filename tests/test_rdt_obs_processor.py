"""Unit tests for RDTObsProcessor._build_image_list — no GPU or model required."""
import numpy as np
import pytest
from PIL import Image

from core.rdt_obs_processor import RDTObsProcessor, RDT_IMG_SIZE


def _dummy_frame(color=(0, 0, 0)) -> Image.Image:
    arr = np.full((RDT_IMG_SIZE, RDT_IMG_SIZE, 3), color, dtype=np.uint8)
    return Image.fromarray(arr)


def test_build_image_list_has_six_slots():
    result = RDTObsProcessor._build_image_list(_dummy_frame(), _dummy_frame())
    assert len(result) == 6


def test_exterior_slots_are_real_images():
    """Slots 0 (ext_prev) and 3 (ext_now) must be PIL Images."""
    result = RDTObsProcessor._build_image_list(_dummy_frame(), _dummy_frame())
    assert isinstance(result[0], Image.Image), "Slot 0 must be a PIL Image"
    assert isinstance(result[3], Image.Image), "Slot 3 must be a PIL Image"


def test_wrist_slots_are_none():
    """Slots 1, 2, 4, 5 must be None (ManiSkill was trained on cam_high only)."""
    result = RDTObsProcessor._build_image_list(_dummy_frame(), _dummy_frame())
    for slot in (1, 2, 4, 5):
        assert result[slot] is None, f"Slot {slot} must be None, got {result[slot]}"


def test_prev_and_now_not_swapped():
    """ext_prev → slot 0, ext_now → slot 3 (order must not be reversed)."""
    prev = _dummy_frame(color=(255, 0, 0))
    now = _dummy_frame(color=(0, 255, 0))
    result = RDTObsProcessor._build_image_list(prev, now)
    assert result[0].getpixel((0, 0))[:3] == (255, 0, 0), "Slot 0 should be ext_prev"
    assert result[3].getpixel((0, 0))[:3] == (0, 255, 0), "Slot 3 should be ext_now"
