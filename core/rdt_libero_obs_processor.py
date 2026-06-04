import importlib.util
import logging
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image


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
ACTIVE_STATE_INDICES_SORTED = _ACTION_CONVERTER.ACTIVE_STATE_INDICES_SORTED
LIBERO_STATE_INDICES = _ACTION_CONVERTER.LIBERO_STATE_INDICES


AGENTVIEW_KEY = "agentview_image"
WRIST_KEY = "robot0_eye_in_hand_image"
JOINT_POS_KEY = "robot0_joint_pos"
GRIPPER_QPOS_KEY = "robot0_gripper_qpos"
TASK_KEY = "task"
GRIPPER_MIN = -0.04245
GRIPPER_MAX = 0.05185
GRIPPER_QPOS_TOLERANCE = 1e-3

_LOGGER = logging.getLogger(__name__)


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
        self._agent_history: deque[Image.Image] = deque(maxlen=2)
        self._wrist_history: deque[Image.Image] = deque(maxlen=2)
        self._state_128: torch.Tensor | None = None
        self._state_mask_128: torch.Tensor | None = None
        self._task: str | None = None
        self._debug_summary_logged = False

    def reset(self) -> None:
        self._agent_history.clear()
        self._wrist_history.clear()
        self._state_128 = None
        self._state_mask_128 = None
        self._task = None
        self._debug_summary_logged = False

    def observe(self, obs: dict[str, Any]) -> None:
        agent_now = self._image_to_pil(obs, AGENTVIEW_KEY)
        wrist_now = self._image_to_pil(obs, WRIST_KEY)
        state_128, state_mask_128 = self._build_state(obs)
        task = self._task_from_obs(obs)

        if not self._agent_history:
            self._agent_history.extend([agent_now, agent_now])
            self._wrist_history.extend([wrist_now, wrist_now])
        else:
            self._agent_history.append(agent_now)
            self._wrist_history.append(wrist_now)

        self._state_128 = state_128
        self._state_mask_128 = state_mask_128
        self._task = task
        self._log_first_observation_summary()

    def process(self, obs: dict[str, Any]) -> RDTLiberoObservation:
        self.observe(obs)
        return self.current()

    def current(self) -> RDTLiberoObservation:
        if self._state_128 is None or self._state_mask_128 is None or self._task is None:
            raise RuntimeError("RDTLiberoObsProcessor.current() called before observe()")
        if len(self._agent_history) != 2 or len(self._wrist_history) != 2:
            raise RuntimeError("RDT image history must contain exactly two frames")

        return RDTLiberoObservation(
            images=[
                self._agent_history[0].copy(),
                self._wrist_history[0].copy(),
                None,
                self._agent_history[1].copy(),
                self._wrist_history[1].copy(),
                None,
            ],
            state_128=self._state_128.clone(),
            state_mask_128=self._state_mask_128.clone(),
            task=self._task,
        )

    def _image_to_pil(self, obs: dict[str, Any], key: str) -> Image.Image:
        if key not in obs:
            raise KeyError(key)
        image = obs[key]
        if torch.is_tensor(image):
            image = image.detach().cpu().numpy()
        image = np.asarray(image)
        if image.ndim != 3 or image.shape[-1] != 3:
            raise ValueError(f"Expected {key} image with shape (H, W, 3), got {image.shape}")
        if image.dtype != np.uint8:
            raise ValueError(f"Expected {key} image dtype uint8, got {image.dtype}")
        if self.undo_preprocessor_flip:
            image = np.flip(image, axis=(0, 1)).copy()
        return Image.fromarray(image)

    def _build_state(self, obs: dict[str, Any]) -> tuple[torch.Tensor, torch.Tensor]:
        joints = np.asarray(obs[JOINT_POS_KEY], dtype=np.float32)
        gripper = np.asarray(obs[GRIPPER_QPOS_KEY], dtype=np.float32)
        if joints.shape != (7,):
            raise ValueError(f"Expected robot0_joint_pos shape (7,), got {joints.shape}")
        if gripper.shape != (2,):
            raise ValueError(f"Expected robot0_gripper_qpos shape (2,), got {gripper.shape}")
        if not np.isfinite(joints).all():
            raise ValueError("Expected robot0_joint_pos values to be finite")
        if not np.isfinite(gripper).all():
            raise ValueError("Expected robot0_gripper_qpos values to be finite")
        gripper_low = GRIPPER_MIN - GRIPPER_QPOS_TOLERANCE
        gripper_high = GRIPPER_MAX + GRIPPER_QPOS_TOLERANCE
        if np.any((gripper < gripper_low) | (gripper > gripper_high)):
            raise ValueError(
                "Expected robot0_gripper_qpos values within raw qpos range "
                f"[{GRIPPER_MIN}, {GRIPPER_MAX}]"
            )

        gripper_norm = (gripper - GRIPPER_MIN) / (GRIPPER_MAX - GRIPPER_MIN)
        proprio = np.concatenate([joints, gripper_norm], axis=0)

        state_128 = torch.zeros((1, 128), dtype=torch.float32)
        state_mask_128 = torch.zeros((1, 128), dtype=torch.float32)
        state_128[0, LIBERO_STATE_INDICES] = torch.as_tensor(proprio, dtype=torch.float32)
        state_mask_128[0, LIBERO_STATE_INDICES] = 1.0

        active = torch.where(state_mask_128[0] > 0)[0].tolist()
        if active != ACTIVE_STATE_INDICES_SORTED:
            raise ValueError(f"Unexpected RDT LIBERO state active indices: {active}")
        return state_128, state_mask_128

    def _task_from_obs(self, obs: dict[str, Any]) -> str:
        task_value = obs[TASK_KEY]
        if isinstance(task_value, (list, tuple)) and len(task_value) == 1:
            task_value = task_value[0]
        if not isinstance(task_value, str):
            raise ValueError("Expected task to be a string")
        task = task_value.strip()
        if not task:
            raise ValueError("Task string is empty")
        return task

    def _log_first_observation_summary(self) -> None:
        if not self.debug or self._debug_summary_logged:
            return

        converted = self.current()
        active = torch.where(converted.state_mask_128[0] > 0)[0].tolist()
        image_sizes = [img.size if img is not None else None for img in converted.images]
        joints = converted.state_128[0, LIBERO_STATE_INDICES[:7]]
        gripper_norm = converted.state_128[0, LIBERO_STATE_INDICES[7:]].tolist()
        _LOGGER.warning(
            "[RDT_LIBERO_OBS] task=%r image_sizes=%s state_active=%s "
            "joint_min=%.4f joint_max=%.4f gripper_norm=%s",
            converted.task,
            image_sizes,
            active,
            float(joints.min().item()),
            float(joints.max().item()),
            gripper_norm,
        )
        self._debug_summary_logged = True
