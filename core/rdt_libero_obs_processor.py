from __future__ import annotations

import importlib.util
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image


AGENTVIEW_KEY = "observation.images.image"
WRIST_KEY = "observation.images.image2"
STATE_KEY = "observation.state"
TASK_KEY = "task"

_LOGGER = logging.getLogger(__name__)


def _load_action_converter():
    module_path = Path(__file__).with_name("rdt_libero_action_converter.py")
    spec = importlib.util.spec_from_file_location("_rdt_libero_action_converter", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load RDT LIBERO action converter from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_ACTION_CONVERTER = _load_action_converter()
ACTIVE_INDICES_SORTED = _ACTION_CONVERTER.ACTIVE_INDICES_SORTED
rotvec_to_ortho6d = _ACTION_CONVERTER.rotvec_to_ortho6d
map_libero_gripper_state = _ACTION_CONVERTER.map_libero_gripper_state


@dataclass
class RDTLiberoObservation:
    images: list[Image.Image | None]
    state_128: torch.Tensor
    state_mask_128: torch.Tensor
    task: str


class RDTLiberoObsProcessor:
    def __init__(
        self,
        undo_preprocessor_flip: bool = False,
        debug: bool = False,
        debug_first_step: bool | None = None,
    ) -> None:
        self.undo_preprocessor_flip = undo_preprocessor_flip
        self.debug = debug if debug_first_step is None else debug_first_step
        self._agent_prev: Image.Image | None = None
        self._wrist_prev: Image.Image | None = None
        self._step = 0

    def reset(self) -> None:
        self._agent_prev = None
        self._wrist_prev = None
        self._step = 0

    def process(self, obs: dict[str, Any]) -> RDTLiberoObservation:
        agent_now = self._image_to_pil(obs, AGENTVIEW_KEY)
        wrist_now = self._image_to_pil(obs, WRIST_KEY)
        state_128, state_mask_128 = self._build_state(obs)
        task = self._task(obs)

        agent_prev = self._agent_prev
        wrist_prev = self._wrist_prev
        images = [agent_prev, wrist_prev, None, agent_now, wrist_now, None]

        self._agent_prev = agent_now
        self._wrist_prev = wrist_now

        if self.debug and self._step == 0:
            _LOGGER.debug(
                "Processed first LIBERO observation: task=%r, state_shape=%s",
                task,
                tuple(state_128.shape),
            )
        self._step += 1

        return RDTLiberoObservation(
            images=images,
            state_128=state_128,
            state_mask_128=state_mask_128,
            task=task,
        )

    def _image_to_pil(self, obs: dict[str, Any], key: str) -> Image.Image:
        if key not in obs:
            raise KeyError(key)

        image = obs[key]
        if not torch.is_tensor(image):
            image = torch.as_tensor(image)
        if image.ndim != 4 or image.shape[0] != 1 or image.shape[1] != 3:
            raise ValueError(f"Expected {key} image tensor with shape (B, 3, H, W)")
        if not torch.isfinite(image).all():
            raise ValueError(f"Expected {key} image tensor to contain only finite values")
        if torch.any((image < 0.0) | (image > 1.0)):
            raise ValueError(f"Expected {key} image tensor values in range [0, 1]")
        if self.undo_preprocessor_flip:
            image = torch.flip(image, dims=(-2, -1))
        image = image[0].detach().cpu().to(dtype=torch.float32)
        image_np = (image.permute(1, 2, 0).numpy() * 255.0).round().astype(np.uint8)
        return Image.fromarray(image_np)

    def _build_state(self, obs: dict[str, Any]) -> tuple[torch.Tensor, torch.Tensor]:
        state = obs[STATE_KEY]
        if not torch.is_tensor(state):
            state = torch.as_tensor(state)
        if state.ndim != 2 or tuple(state.shape) != (1, 8):
            raise ValueError("Expected observation.state with shape (1, 8) for online batch")

        state_head = state[0].detach().cpu().to(dtype=torch.float32)
        eef_pos = state_head[:3]
        axis_angle = state_head[3:6].numpy()
        gripper_qpos = state_head[6:8].numpy()

        state_128 = torch.zeros((1, 128), dtype=torch.float32)
        state_mask_128 = torch.zeros((1, 128), dtype=torch.float32)
        state_128[0, 30:33] = eef_pos
        state_128[0, 33:39] = torch.as_tensor(rotvec_to_ortho6d(axis_angle), dtype=torch.float32)
        state_128[0, 10] = float(map_libero_gripper_state(gripper_qpos))
        state_mask_128[0, ACTIVE_INDICES_SORTED] = 1.0
        return state_128, state_mask_128

    def _task(self, obs: dict[str, Any]) -> str:
        task_value = obs[TASK_KEY]
        if isinstance(task_value, (list, tuple)) and len(task_value) == 1:
            task_value = task_value[0]
        if not isinstance(task_value, str):
            raise ValueError("Expected task to be a string")

        task = task_value.strip()
        if not task:
            raise ValueError("Task string is empty")
        return task
