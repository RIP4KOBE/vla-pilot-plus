---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: feat/rdt-libero-gt-rollout-reintegration
source_commit: 360a6d052861
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/docs/superpowers/plans/2026-05-26-rdt-libero-gt-rollout-reintegration.md
summary: RDT-LIBERO GT Rollout Re-Integration Implementation Plan
duplicate_sources:
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/superpowers/plans/2026-05-26-rdt-libero-gt-rollout-reintegration.md
---

# RDT-LIBERO GT Rollout Re-Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-align `python main.py policy.type=rdt` with the GT `tj-chen-1209/Libero_RDT` rollout semantics so the local runtime can evaluate `/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object/ema/model.safetensors` on LIBERO Object and reach greater than `0/10` success.

**Architecture:** Keep the current unified `core/rdt_policy_steer.py` policy route and replace only project-owned RDT-LIBERO glue semantics. The RDT path will consume GT-style raw LIBERO observations, use joint+gripper state indices `[0..6,10,11]`, denoise in the full 128D RDT action space with action mask `[39..44,10]`, and execute the extracted 7D OSC action directly. Do not modify `third_party/rdt`, `third_party/libero`, or `third_party/Libero_RDT`.

**Tech Stack:** Python, PyTorch, NumPy, Pillow, Hydra/OmegaConf, pytest, LIBERO `OffScreenRenderEnv`, RDT `RDTRunner`, SigLIP, T5.

---

## Critical GT Correction

The design document separates "state mask" and "action mask". During implementation, follow the GT code exactly:

```text
state_128 contains valid state values at [0,1,2,3,4,5,6,10,11].
state_mask_128 is useful for validation and debug logging.
action_mask_128 contains valid output dimensions at [39,40,41,42,43,44,10].
RDTRunner.predict_action concatenates action_mask_128 to state_128 before state_adaptor.
```

Do not concatenate the state mask to `state_128` inside `_RDTModelAdapter.encode_inputs()`. GT `libero_rdt_model.py` passes `action_elem_mask.unsqueeze(1)` into `policy.predict_action(...)`, and `RDTRunner.predict_action()` concatenates that mask with state tokens.

## File Structure

Modify these project-owned files:

```text
configs/policy.yaml
configs/backend/libero.yaml
core/rdt_libero_action_converter.py
core/rdt_libero_obs_processor.py
core/rdt_policy_steer.py
core/env_adapters/libero_adapter.py
tests/test_rdt_runtime_contract.py
tests/test_rdt_libero_action_converter.py
tests/test_rdt_libero_obs_processor.py
tests/test_rdt_steer.py
tests/test_env_adapters_imports.py
```

Do not create a new policy file or route:

```text
core/rdt_libero_policy.py
policy.type=rdt_libero
```

Do not modify:

```text
third_party/rdt/
third_party/libero/
third_party/Libero_RDT/
```

## Task 1: Lock Config And Checkpoint Contract

**Files:**
- Modify: `tests/test_rdt_runtime_contract.py`
- Modify: `configs/policy.yaml`
- Modify: `configs/backend/libero.yaml`

- [ ] **Step 1: Replace runtime contract tests with GT checkpoint expectations**

Replace `tests/test_rdt_runtime_contract.py` with:

```python
import json
from pathlib import Path

from omegaconf import OmegaConf


GT_ROOT = Path("/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object")
GT_WEIGHT = GT_ROOT / "ema" / "model.safetensors"
T5 = Path("/mnt/data/hf_cache/hub/models--google--t5-v1_1-xxl")
SIGLIP = Path("/mnt/data/hf_cache/hub/models--google--siglip-so400m-patch14-384")
EXPECTED_IMG_HISTORY_AND_CAMERAS = [2, 3]


def test_gt_checkpoint_and_encoder_paths_exist():
    config_json = GT_ROOT / "config.json"

    assert GT_ROOT.is_dir(), f"Missing GT RDT root: {GT_ROOT}"
    assert config_json.is_file(), f"Missing GT RDT config: {config_json}"
    assert GT_WEIGHT.is_file(), f"Missing GT RDT EMA weights: {GT_WEIGHT}"
    assert T5.is_dir(), f"Missing local T5 encoder dir: {T5}"
    assert SIGLIP.is_dir(), f"Missing local SigLIP encoder dir: {SIGLIP}"


def test_gt_checkpoint_config_matches_rdt_libero_contract():
    cfg = json.loads((GT_ROOT / "config.json").read_text())

    assert cfg["pred_horizon"] == 64
    assert cfg["action_dim"] == 128
    assert cfg["state_token_dim"] == 128
    assert cfg["img_pos_embed_config"][0][1][:2] == EXPECTED_IMG_HISTORY_AND_CAMERAS
    assert cfg["lang_token_dim"] == 4096
    assert cfg["img_token_dim"] == 1152
    assert cfg["noise_scheduler"]["num_inference_timesteps"] == 5
    assert cfg["noise_scheduler"]["prediction_type"] == "sample"


def test_policy_yaml_keeps_rdt_route_and_gt_checkpoint():
    cfg = OmegaConf.load("configs/policy.yaml")

    assert cfg.type == "rdt"
    assert cfg.rdt.pretrained_path in {str(GT_ROOT), str(GT_WEIGHT)}
    assert cfg.rdt.weight_variant == "ema"
    assert cfg.rdt.text_encoder == str(T5)
    assert cfg.rdt.vision_encoder == str(SIGLIP)
    assert cfg.rdt.action_chunk_horizon == 8
    assert cfg.rdt.control_frequency == 20
    assert cfg.rdt.semantics == "libero_gt_rollout"


def test_backend_libero_matches_gt_rollout_protocol():
    cfg = OmegaConf.load("configs/backend/libero.yaml")

    assert cfg.libero.suite_name == "libero_object"
    assert cfg.libero.observation_width == 128
    assert cfg.libero.observation_height == 128
    assert cfg.libero.num_steps_wait == 5
    assert cfg.libero.max_episode_steps == 720
    assert cfg.libero.task_ids_filter is None
```

- [ ] **Step 2: Run the contract tests and confirm they fail on stale config**

Run:

```bash
pytest tests/test_rdt_runtime_contract.py -v
```

Expected before config edits:

```text
FAILED tests/test_rdt_runtime_contract.py::test_policy_yaml_keeps_rdt_route_and_gt_checkpoint
FAILED tests/test_rdt_runtime_contract.py::test_backend_libero_matches_gt_rollout_protocol
```

- [ ] **Step 3: Update `configs/policy.yaml` RDT defaults**

Set the `rdt` section to:

```yaml
rdt:
  pretrained_path: /mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object
  weight_variant: ema
  text_encoder: /mnt/data/hf_cache/hub/models--google--t5-v1_1-xxl
  vision_encoder: /mnt/data/hf_cache/hub/models--google--siglip-so400m-patch14-384
  num_inference_steps: null
  action_chunk_horizon: 8
  control_frequency: 20
  debug_first_step: true
  fail_on_zero_language_embedding: true
  semantics: libero_gt_rollout
```

Do not keep `undo_libero_preprocessor_flip` as a required RDT semantic option in this section. The GT path should consume raw LIBERO images.

- [ ] **Step 4: Update `configs/backend/libero.yaml` defaults**

Set:

```yaml
suite_name: libero_object
observation_width: 128
observation_height: 128
num_steps_wait: 5
max_episode_steps: 720
task_ids_filter: null
```

- [ ] **Step 5: Run the contract tests again**

Run:

```bash
pytest tests/test_rdt_runtime_contract.py -v
```

Expected:

```text
4 passed
```

- [ ] **Step 6: Commit Task 1**

```bash
git add tests/test_rdt_runtime_contract.py configs/policy.yaml configs/backend/libero.yaml
git commit -m "test: lock RDT LIBERO GT runtime contract"
```

## Task 2: Replace RDT-LIBERO Action Converter With GT Slot Extraction

**Files:**
- Modify: `tests/test_rdt_libero_action_converter.py`
- Modify: `core/rdt_libero_action_converter.py`

- [ ] **Step 1: Replace action converter tests with GT action-slot tests**

Replace `tests/test_rdt_libero_action_converter.py` with:

```python
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
    torch.testing.assert_close(decoded[..., :6], torch.tensor([0.5, -0.25, 0.125, -0.5, 0.25, -0.125]))
    assert torch.all(decoded[..., 6] == -1.0)


def test_decode_rejects_wrong_action_shape():
    with pytest.raises(ValueError, match="128"):
        decode_rdt_libero_action_chunk(torch.zeros(1, 64, 7), action_chunk_horizon=8)

    with pytest.raises(ValueError, match="64|128"):
        decode_rdt_libero_action_chunk(torch.zeros(1, 63, 128), action_chunk_horizon=8)

    with pytest.raises(ValueError, match="horizon"):
        decode_rdt_libero_action_chunk(torch.zeros(1, 64, 128), action_chunk_horizon=0)
```

- [ ] **Step 2: Run action converter tests and confirm stale converter fails**

Run:

```bash
pytest tests/test_rdt_libero_action_converter.py -v
```

Expected before implementation:

```text
FAILED tests/test_rdt_libero_action_converter.py::test_gt_state_and_action_indices_match_reference
FAILED tests/test_rdt_libero_action_converter.py::test_decode_extracts_gt_action_slots_directly
```

- [ ] **Step 3: Replace `core/rdt_libero_action_converter.py` with GT extraction logic**

Use this implementation:

```python
from __future__ import annotations

import torch


LIBERO_STATE_INDICES = [0, 1, 2, 3, 4, 5, 6, 10, 11]
LIBERO_ACTION_INDICES = [39, 40, 41, 42, 43, 44, 10]

ACTIVE_STATE_INDICES_SORTED = sorted(LIBERO_STATE_INDICES)
ACTIVE_ACTION_INDICES_SORTED = sorted(LIBERO_ACTION_INDICES)

# Backward-compatible names used by rdt_policy_steer.py.
LIBERO_RDT_INDICES = LIBERO_ACTION_INDICES
ACTIVE_INDICES_SORTED = ACTIVE_STATE_INDICES_SORTED


def _as_tensor(action_128d) -> torch.Tensor:
    if torch.is_tensor(action_128d):
        return action_128d
    return torch.as_tensor(action_128d, dtype=torch.float32)


def rdt_action_to_libero_raw(action_128d) -> torch.Tensor:
    action = _as_tensor(action_128d)
    if action.shape[-1] != 128:
        raise ValueError(f"Expected RDT action with last dimension 128, got {tuple(action.shape)}")

    decoded = action[..., LIBERO_ACTION_INDICES].clone().to(dtype=torch.float32)
    decoded[..., -1] = torch.where(
        decoded[..., -1] < 0.0,
        torch.tensor(-1.0, device=decoded.device, dtype=decoded.dtype),
        torch.tensor(1.0, device=decoded.device, dtype=decoded.dtype),
    )
    return decoded


def decode_rdt_libero_action_chunk(pred_actions_128, action_chunk_horizon: int) -> torch.Tensor:
    if not torch.is_tensor(pred_actions_128):
        raise TypeError("Expected pred_actions_128 to be a torch tensor")
    if (
        pred_actions_128.ndim != 3
        or pred_actions_128.shape[1] != 64
        or pred_actions_128.shape[2] != 128
    ):
        raise ValueError(
            f"Expected pred_actions_128 with shape (B, 64, 128), got {tuple(pred_actions_128.shape)}"
        )
    if action_chunk_horizon < 1 or action_chunk_horizon > pred_actions_128.shape[1]:
        raise ValueError("action_chunk_horizon must fit within the action chunk horizon")

    first_particle = pred_actions_128[0:1, :action_chunk_horizon, :]
    return rdt_action_to_libero_raw(first_particle).to(device=pred_actions_128.device)
```

- [ ] **Step 4: Run action converter tests**

Run:

```bash
pytest tests/test_rdt_libero_action_converter.py -v
```

Expected:

```text
5 passed
```

- [ ] **Step 5: Commit Task 2**

```bash
git add tests/test_rdt_libero_action_converter.py core/rdt_libero_action_converter.py
git commit -m "fix: decode RDT LIBERO actions with GT slots"
```

## Task 3: Replace Observation Processor With GT Raw Observation Semantics

**Files:**
- Modify: `tests/test_rdt_libero_obs_processor.py`
- Modify: `core/rdt_libero_obs_processor.py`

- [ ] **Step 1: Replace observation processor tests with raw LIBERO tests**

Replace `tests/test_rdt_libero_obs_processor.py` with:

```python
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


def test_bad_gripper_shape_raises_value_error():
    processor = RDTLiberoObsProcessor()
    obs = _obs()
    obs["robot0_gripper_qpos"] = np.zeros((1,), dtype=np.float32)

    with pytest.raises(ValueError, match="robot0_gripper_qpos"):
        processor.process(obs)


def test_empty_language_raises_value_error():
    processor = RDTLiberoObsProcessor()

    with pytest.raises(ValueError, match="empty"):
        processor.process(_obs(task=""))
```

- [ ] **Step 2: Run observation tests and confirm stale processor fails**

Run:

```bash
pytest tests/test_rdt_libero_obs_processor.py -v
```

Expected before implementation:

```text
FAILED tests/test_rdt_libero_obs_processor.py::test_process_builds_gt_joint_state_and_mask_contract
FAILED tests/test_rdt_libero_obs_processor.py::test_first_frame_history_duplicates_initial_raw_frames
```

- [ ] **Step 3: Replace `core/rdt_libero_obs_processor.py` with GT raw observation logic**

Use this implementation structure:

```python
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from typing import Any

import numpy as np
import torch
from PIL import Image

from core.rdt_libero_action_converter import (
    ACTIVE_STATE_INDICES_SORTED,
    LIBERO_STATE_INDICES,
)


AGENTVIEW_KEY = "agentview_image"
WRIST_KEY = "robot0_eye_in_hand_image"
JOINT_POS_KEY = "robot0_joint_pos"
GRIPPER_QPOS_KEY = "robot0_gripper_qpos"
TASK_KEY = "task"
GRIPPER_MIN = -0.04245
GRIPPER_MAX = 0.05185

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
        self._step = 0

    def reset(self) -> None:
        self._agent_history.clear()
        self._wrist_history.clear()
        self._state_128 = None
        self._state_mask_128 = None
        self._task = None
        self._step = 0

    def observe(self, obs: dict[str, Any]) -> None:
        agent_now = self._image_to_pil(obs, AGENTVIEW_KEY)
        wrist_now = self._image_to_pil(obs, WRIST_KEY)
        if not self._agent_history:
            self._agent_history.extend([agent_now, agent_now])
            self._wrist_history.extend([wrist_now, wrist_now])
        else:
            self._agent_history.append(agent_now)
            self._wrist_history.append(wrist_now)

        self._state_128, self._state_mask_128 = self._build_state(obs)
        self._task = self._task_from_obs(obs)

    def process(self, obs: dict[str, Any]) -> RDTLiberoObservation:
        self.observe(obs)
        converted = self.current()

        if self.debug and self._step == 0:
            _LOGGER.warning(
                "[RDT_LIBERO_OBS] task=%r state_active=%s image_modes=%s",
                converted.task,
                torch.where(converted.state_mask_128[0] > 0)[0].tolist(),
                [img.mode if img is not None else None for img in converted.images],
            )
        self._step += 1
        return converted

    def current(self) -> RDTLiberoObservation:
        if self._state_128 is None or self._state_mask_128 is None or self._task is None:
            raise RuntimeError("RDTLiberoObsProcessor.current() called before observe()")
        if len(self._agent_history) != 2 or len(self._wrist_history) != 2:
            raise RuntimeError("RDT image history must contain exactly two frames")

        return RDTLiberoObservation(
            images=[
                self._agent_history[0],
                self._wrist_history[0],
                None,
                self._agent_history[1],
                self._wrist_history[1],
                None,
            ],
            state_128=self._state_128,
            state_mask_128=self._state_mask_128,
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
```

- [ ] **Step 4: Run observation processor tests**

Run:

```bash
pytest tests/test_rdt_libero_obs_processor.py -v
```

Expected:

```text
10 passed
```

- [ ] **Step 5: Commit Task 3**

```bash
git add tests/test_rdt_libero_obs_processor.py core/rdt_libero_obs_processor.py
git commit -m "fix: build RDT LIBERO observations from GT raw state"
```

## Task 4: Expose GT Raw Observation Fields From LIBERO Adapter

**Files:**
- Modify: `tests/test_env_adapters_imports.py`
- Modify: `core/env_adapters/libero_adapter.py`

- [ ] **Step 1: Update adapter reset and backend parity tests**

In `tests/test_env_adapters_imports.py`, update `test_libero_env_reset_applies_init_state_after_reset_and_stabilizes` so the fake `_format_raw_obs` accepts the GT reset snapshot:

```python
def format_raw_obs(raw_obs, rdt_raw_obs=None):
    formatted_raw_obs.append((raw_obs, rdt_raw_obs))
    return {"formatted": raw_obs, "rdt_raw": rdt_raw_obs}

env._format_raw_obs = format_raw_obs

observation, info = env.reset(seed=123)

assert formatted_raw_obs == [("step_obs_3", "init_state_obs")]
assert observation == {"formatted": "step_obs_3", "rdt_raw": "init_state_obs"}
assert info == {"is_success": False}
```

Update `test_libero_backend_config_defaults_match_eval_parity`:

```python
assert libero_config["max_episode_steps"] == 720
```

- [ ] **Step 2: Add a raw RDT key formatting test**

Append this test to `tests/test_env_adapters_imports.py`:

```python
def test_libero_env_format_raw_obs_includes_gt_rdt_raw_keys():
    script = r'''
import builtins
import sys
import types

libero = types.ModuleType("libero")
libero_libero = types.ModuleType("libero.libero")
libero_envs = types.ModuleType("libero.libero[redacted env file]s")
libero_libero.benchmark = object()
libero_libero.get_libero_path = lambda name: "/tmp"
libero_envs.OffScreenRenderEnv = object
sys.modules["libero"] = libero
sys.modules["libero.libero"] = libero_libero
sys.modules["libero.libero[redacted env file]s"] = libero_envs

original_import = builtins.__import__

def guarded_import(name, *args, **kwargs):
    if name == "lerobot" or name.startswith("lerobot."):
        raise ModuleNotFoundError("No module named 'lerobot'", name="lerobot")
    return original_import(name, *args, **kwargs)

builtins.__import__ = guarded_import

import numpy as np
import core[redacted env file]_adapters.libero_adapter as adapter

env = adapter.LiberoEnv.__new__(adapter.LiberoEnv)
env.camera_name = ["agentview_image", "robot0_eye_in_hand_image"]
env.camera_name_mapping = {
    "agentview_image": "image",
    "robot0_eye_in_hand_image": "image2",
}

class FakeController:
    ee_ori_mat = np.eye(3)

class FakeRobot:
    controller = FakeController()

class FakeInner:
    robots = [FakeRobot()]

env._env = FakeInner()

post_settle = {
    "agentview_image": np.zeros((2, 2, 3), dtype=np.uint8),
    "robot0_eye_in_hand_image": np.ones((2, 2, 3), dtype=np.uint8) * 2,
    "robot0_eef_pos": np.zeros(3, dtype=np.float32),
    "robot0_eef_quat": np.array([0, 0, 0, 1], dtype=np.float32),
    "robot0_gripper_qpos": np.array([0.1, 0.2], dtype=np.float32),
    "robot0_gripper_qvel": np.zeros(2, dtype=np.float32),
    "robot0_joint_pos": np.arange(7, dtype=np.float32),
    "robot0_joint_vel": np.zeros(7, dtype=np.float32),
}
rdt_source = {
    **post_settle,
    "agentview_image": np.ones((2, 2, 3), dtype=np.uint8) * 9,
    "robot0_eye_in_hand_image": np.ones((2, 2, 3), dtype=np.uint8) * 8,
    "robot0_joint_pos": np.arange(7, dtype=np.float32) + 10,
    "robot0_gripper_qpos": np.array([-0.04245, 0.05185], dtype=np.float32),
}

obs = env._format_raw_obs(post_settle, rdt_raw_obs=rdt_source)

assert obs["agentview_image"].dtype == np.uint8
assert obs["robot0_eye_in_hand_image"].dtype == np.uint8
assert obs["agentview_image"][0, 0, 0] == 9
assert obs["robot0_eye_in_hand_image"][0, 0, 0] == 8
np.testing.assert_allclose(obs["robot0_joint_pos"], np.arange(7, dtype=np.float32) + 10)
np.testing.assert_allclose(obs["robot0_gripper_qpos"], np.array([-0.04245, 0.05185], dtype=np.float32))
'''
    result = _run_python(script)

    assert result.returncode == 0, result.stderr
```

- [ ] **Step 3: Run adapter tests and confirm failures**

Run:

```bash
pytest tests/test_env_adapters_imports.py -v
```

Expected before implementation:

```text
FAILED tests/test_env_adapters_imports.py::test_libero_env_reset_applies_init_state_after_reset_and_stabilizes
FAILED tests/test_env_adapters_imports.py::test_libero_env_format_raw_obs_includes_gt_rdt_raw_keys
FAILED tests/test_env_adapters_imports.py::test_libero_backend_config_defaults_match_eval_parity
```

- [ ] **Step 4: Modify `_format_raw_obs` to preserve raw RDT keys**

Change the signature:

```python
def _format_raw_obs(self, raw_obs: dict[str, Any], rdt_raw_obs: dict[str, Any] | None = None) -> dict[str, Any]:
```

After the existing LeRobot image and `observation.robot_state` construction, add:

```python
        rdt_source = rdt_raw_obs if rdt_raw_obs is not None else raw_obs
        observation["agentview_image"] = np.asarray(rdt_source["agentview_image"], dtype=np.uint8).copy()
        observation["robot0_eye_in_hand_image"] = np.asarray(
            rdt_source["robot0_eye_in_hand_image"], dtype=np.uint8
        ).copy()
        observation["robot0_joint_pos"] = np.asarray(rdt_source["robot0_joint_pos"], dtype=np.float32).copy()
        observation["robot0_gripper_qpos"] = np.asarray(
            rdt_source["robot0_gripper_qpos"], dtype=np.float32
        ).copy()
```

Do not remove the existing LeRobot-style keys because PI05 and other project paths may still need them.

- [ ] **Step 5: Modify `LiberoEnv.reset` to pass the GT pre-settle snapshot to RDT keys**

Replace the reset body around `set_init_state` and no-op settle with:

```python
        raw_obs = self._env.reset()
        rdt_initial_raw_obs = raw_obs
        if self.init_states and self._init_states is not None:
            rdt_initial_raw_obs = self._env.set_init_state(self._init_states[self._init_state_id])
            raw_obs = rdt_initial_raw_obs

        for _ in range(self.num_steps_wait):
            raw_obs, _, _, _ = self._env.step(get_libero_dummy_action())

        observation = self._format_raw_obs(raw_obs, rdt_raw_obs=rdt_initial_raw_obs)
```

This matches GT's first RDT observation timing while preserving the post-settle env state.

- [ ] **Step 6: Run adapter tests**

Run:

```bash
pytest tests/test_env_adapters_imports.py -v
```

Expected:

```text
all tests in tests/test_env_adapters_imports.py pass
```

- [ ] **Step 7: Commit Task 4**

```bash
git add tests/test_env_adapters_imports.py core/env_adapters/libero_adapter.py
git commit -m "fix: expose GT raw LIBERO observations for RDT"
```

## Task 5: Align RDTSteer Masks, History Updates, Unguided Batch Size, And Checkpoint Resolution

**Files:**
- Modify: `tests/test_rdt_steer.py`
- Modify: `core/rdt_policy_steer.py`

- [ ] **Step 1: Update the RDT steer stub to GT raw observations and GT action mask**

In `tests/test_rdt_steer.py`, replace `_StubRDTModel.encode_inputs` with:

```python
    def encode_inputs(self, state_128, state_mask_128, images, text_embeds):
        action_mask = torch.zeros_like(state_mask_128)
        action_mask[:, [39, 40, 41, 42, 43, 44, 10]] = 1.0
        return {
            "lang_cond": torch.zeros(1, 1, 4),
            "lang_attn_mask": torch.ones(1, 1, dtype=torch.bool),
            "img_cond": torch.zeros(1, 1, 4),
            "state_traj": torch.zeros(1, 1, 4),
            "action_mask": action_mask.float().unsqueeze(1),
            "ctrl_freqs": torch.tensor([20]),
            "action_indices": [39, 40, 41, 42, 43, 44, 10],
            "unified_action_dim": 128,
        }
```

Replace `mock_batch` with GT raw keys:

```python
@pytest.fixture
def mock_batch():
    B = 1
    image = np.zeros((16, 16, 3), dtype=np.uint8)
    wrist = np.ones((16, 16, 3), dtype=np.uint8)
    return {
        "agentview_image": image,
        "robot0_eye_in_hand_image": wrist,
        "robot0_joint_pos": np.array([0.10, -0.20, 0.80, 0.0, 0.1, -0.1, 0.2], dtype=np.float32),
        "robot0_gripper_qpos": np.array([-0.04245, 0.05185], dtype=np.float32),
        "task": ["pick up the red block"] * B,
    }
```

- [ ] **Step 2: Replace the unguided mask test with GT masks**

Replace `test_unguided_uses_full_128d_libero_mask` with:

```python
def test_unguided_uses_gt_state_and_action_masks(stub_steer, stub_adapter, mock_batch):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=20,
        policy_config={"action_chunk_horizon": 8, "debug_first_step": True},
    )
    converted = stub_steer._obs_processor.process(mock_batch)
    assert converted.state_128.shape == (1, 128)
    assert converted.state_mask_128.shape == (1, 128)
    assert torch.where(converted.state_mask_128[0] > 0)[0].tolist() == [0, 1, 2, 3, 4, 5, 6, 10, 11]
    assert converted.task == "pick up the red block"

    raw = stub_steer._predict_unguided(
        converted.state_128,
        converted.state_mask_128,
        converted.images,
        torch.zeros(1, 1, 4096),
        B=1,
    )
    assert raw.shape == (1, 64, 128)
    assert stub_steer._rdt_model.dit.calls
    for latent_shape, mask_shape in stub_steer._rdt_model.dit.calls:
        assert latent_shape == (1, 64, 128)
        assert mask_shape == (1, 1, 128)
```

- [ ] **Step 3: Add a test proving unguided select_action ignores VLS sample_batch_size**

Append:

```python
def test_select_action_unguided_uses_single_particle(stub_steer, stub_adapter, mock_batch):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=20,
        policy_config={"action_chunk_horizon": 8},
    )

    action = stub_steer.select_action(mock_batch, generate_new_chunk=True, use_guidance=False)

    assert action.shape == (1, 8, 7)
    for latent_shape, _ in stub_steer._rdt_model.dit.calls:
        assert latent_shape[0] == 1
```

- [ ] **Step 4: Add a test proving history updates on cached chunk calls**

Append:

```python
def test_select_action_observes_every_step_while_reusing_cached_chunk(stub_steer, stub_adapter, mock_batch):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=1,
        policy_config={"action_chunk_horizon": 8},
    )

    first = mock_batch
    second = dict(mock_batch)
    second["agentview_image"] = np.ones((16, 16, 3), dtype=np.uint8) * 5
    second["robot0_eye_in_hand_image"] = np.ones((16, 16, 3), dtype=np.uint8) * 6

    stub_steer.select_action(first, generate_new_chunk=True, use_guidance=False)
    calls_after_first = len(stub_steer._rdt_model.dit.calls)
    stub_steer.select_action(second, generate_new_chunk=False, use_guidance=False)

    assert len(stub_steer._rdt_model.dit.calls) == calls_after_first
    current = stub_steer._obs_processor.current()
    assert current.images[3].getpixel((0, 0)) == (5, 5, 5)
    assert current.images[4].getpixel((0, 0)) == (6, 6, 6)
```

- [ ] **Step 5: Add checkpoint file resolution tests**

Append:

```python
def test_rdt_checkpoint_file_path_resolves_model_root_and_weight(tmp_path):
    from core.rdt_policy_steer import _resolve_rdt_checkpoint_paths

    root = tmp_path / "RDT-1B-LIBERO-Object"
    weight = root / "ema" / "model.safetensors"
    root.mkdir()
    (root / "config.json").write_text("{}", encoding="utf-8")
    weight.parent.mkdir()
    weight.write_bytes(b"fake")

    resolved_root, resolved_weight = _resolve_rdt_checkpoint_paths(str(weight), "ema")

    assert resolved_root == str(root)
    assert resolved_weight == str(weight)


def test_rdt_checkpoint_root_path_resolves_ema_safetensors(tmp_path):
    from core.rdt_policy_steer import _resolve_rdt_checkpoint_paths

    root = tmp_path / "RDT-1B-LIBERO-Object"
    weight = root / "ema" / "model.safetensors"
    root.mkdir()
    (root / "config.json").write_text("{}", encoding="utf-8")
    weight.parent.mkdir()
    weight.write_bytes(b"fake")

    resolved_root, resolved_weight = _resolve_rdt_checkpoint_paths(str(root), "ema")

    assert resolved_root == str(root)
    assert resolved_weight == str(weight)
```

- [ ] **Step 6: Run RDT steer tests and confirm stale failures**

Run:

```bash
pytest tests/test_rdt_steer.py -v
```

Expected before implementation:

```text
FAILED tests/test_rdt_steer.py::test_unguided_uses_gt_state_and_action_masks
FAILED tests/test_rdt_steer.py::test_select_action_unguided_uses_single_particle
FAILED tests/test_rdt_steer.py::test_select_action_observes_every_step_while_reusing_cached_chunk
FAILED tests/test_rdt_steer.py::test_rdt_checkpoint_file_path_resolves_model_root_and_weight
```

- [ ] **Step 7: Add `_resolve_rdt_checkpoint_paths` to `core/rdt_policy_steer.py`**

Add near `_rdt_weight_search_dirs`:

```python
def _resolve_rdt_checkpoint_paths(pretrained_path: str, weight_variant: Optional[str]) -> tuple[str, str]:
    path = Path(pretrained_path)
    if path.is_file():
        if path.name not in {"model.safetensors", "pytorch_model.bin", "mp_rank_00_model_states.pt", "rdt-1b.pt"}:
            raise FileNotFoundError(f"Unsupported RDT checkpoint file: {pretrained_path}")
        model_root = path.parent.parent if path.parent.name in {"ema", "rdt"} else path.parent
        return str(model_root), str(path)

    if not path.is_dir():
        raise FileNotFoundError(f"RDT checkpoint path is not local: {pretrained_path}")

    weight_names = (
        "model.safetensors",
        "pytorch_model.bin",
        "mp_rank_00_model_states.pt",
        "rdt-1b.pt",
    )
    for search_root in _rdt_weight_search_dirs(str(path), weight_variant):
        search_path = Path(search_root)
        if not search_path.is_dir():
            continue
        for fname in weight_names:
            candidate = search_path / fname
            if candidate.is_file():
                return str(path), str(candidate)

    raise FileNotFoundError(
        f"No RDT weight file found for variant {weight_variant!r} under {pretrained_path}"
    )
```

Then update `from_pretrained()` so local file paths are not passed to `snapshot_download`. Use:

```python
        path_obj = Path(pretrained_path)
        if not path_obj.exists():
            from huggingface_hub import snapshot_download
            ...

        model_root, weight_file = _resolve_rdt_checkpoint_paths(pretrained_path, weight_variant)
        pretrained_path = model_root
```

Use `weight_file` returned by the helper and remove the duplicate local `weight_names` search block.

- [ ] **Step 8: Update imports in `core/rdt_policy_steer.py`**

Change the action converter import to:

```python
from core.rdt_libero_action_converter import (
    ACTIVE_STATE_INDICES_SORTED,
    LIBERO_ACTION_INDICES,
    decode_rdt_libero_action_chunk,
)
```

- [ ] **Step 9: Update `_RDTModelAdapter.encode_inputs` for GT masks**

Inside `_RDTModelAdapter.encode_inputs`, replace the active mask check and state token construction with:

```python
        active_state = torch.where(state_elem_mask[0] > 0)[0].detach().cpu().tolist()
        if active_state != ACTIVE_STATE_INDICES_SORTED:
            raise ValueError(
                f"LIBERO state mask mismatch: expected {ACTIVE_STATE_INDICES_SORTED}, got {active_state}"
            )

        states = states.unsqueeze(1)

        action_elem_mask = torch.zeros(
            (1, unified_action_dim),
            device=device,
            dtype=dtype,
        )
        action_elem_mask[:, LIBERO_ACTION_INDICES] = 1
        action_indices = LIBERO_ACTION_INDICES
        ctrl_freqs = torch.tensor([real.control_frequency], device=device)
```

When adapting conditions, concatenate action mask, not state mask:

```python
        state_tokens = torch.cat([states, action_elem_mask.unsqueeze(1)], dim=2)
        lang_cond, img_cond, state_traj = real.policy.adapt_conditions(
            text_embeds, image_embeds, state_tokens
        )
```

Return:

```python
            "action_mask": action_elem_mask.unsqueeze(1),
            "action_indices": action_indices,
```

Update the one-time log to include both:

```python
                f"state_active={active_state} "
                f"action_active={LIBERO_ACTION_INDICES} "
```

- [ ] **Step 10: Update `RDTSteer.select_action` to observe every step and use B=1 unguided**

In `select_action()`, before the `if generate_new_chunk:` block, add:

```python
        if self._obs_processor is None:
            raise RuntimeError("RDTSteer.post_init must be called before select_action")
        self._obs_processor.observe(batch)
```

Then inside `if generate_new_chunk:`, replace `converted = self._obs_processor.process(batch)` with:

```python
            converted = self._obs_processor.current()
```

Replace:

```python
            B = self._sample_batch_size
```

with:

```python
            B = self._sample_batch_size if use_guidance else 1
```

This keeps VLS particle count available for future guided RDT while matching GT for unguided rollout.

- [ ] **Step 11: Run RDT steer tests**

Run:

```bash
pytest tests/test_rdt_steer.py -v
```

Expected:

```text
all tests in tests/test_rdt_steer.py pass
```

- [ ] **Step 12: Commit Task 5**

```bash
git add tests/test_rdt_steer.py core/rdt_policy_steer.py
git commit -m "fix: align RDT policy masks and checkpoint loading with GT"
```

## Task 6: Run Focused Unit Suite And Fix Contract Drift

**Files:**
- Modify only files touched in Tasks 1-5 if a test exposes a mismatch.

- [ ] **Step 1: Run focused RDT and LIBERO unit tests**

Run:

```bash
pytest \
  tests/test_rdt_runtime_contract.py \
  tests/test_rdt_libero_action_converter.py \
  tests/test_rdt_libero_obs_processor.py \
  tests/test_rdt_steer.py \
  tests/test_env_adapters_imports.py \
  -v
```

Expected:

```text
all selected tests pass
```

- [ ] **Step 2: If `test_env_adapters_imports.py` reports legacy max step expectations, update the assertions**

Every LIBERO GT parity assertion should expect:

```python
assert libero_config["max_episode_steps"] == 720
```

Every fake config that is intentionally testing pass-through may keep `600` as the value it passes in. Only the default backend parity test must use `720`.

- [ ] **Step 3: If tests import removed action helper names, update those tests instead of restoring old semantics**

Remove imports and tests for:

```text
rotvec_to_ortho6d
ortho6d_to_rotvec
libero_raw_to_rdt_action
map_libero_gripper_action_to_open
map_open_to_libero_gripper
```

These are EEF/6D-rotation semantics and should not remain in GT rollout tests.

- [ ] **Step 4: Run focused tests again**

Run:

```bash
pytest \
  tests/test_rdt_runtime_contract.py \
  tests/test_rdt_libero_action_converter.py \
  tests/test_rdt_libero_obs_processor.py \
  tests/test_rdt_steer.py \
  tests/test_env_adapters_imports.py \
  -v
```

Expected:

```text
all selected tests pass
```

- [ ] **Step 5: Commit Task 6 if Step 2 or Step 3 changed files**

```bash
git add tests core configs
git commit -m "test: stabilize RDT LIBERO GT contract tests"
```

Skip this commit if Task 6 made no file changes.

## Task 7: Add Lightweight Runtime Probes For First RDT Chunk

**Files:**
- Modify: `core/rdt_libero_obs_processor.py`
- Modify: `core/rdt_libero_action_converter.py`
- Modify: `core/rdt_policy_steer.py`

- [ ] **Step 1: Add first-step observation summaries**

In `RDTLiberoObsProcessor.process()` or `current()`, keep one first-step warning behind `debug_first_step`:

```python
        if self.debug and self._step == 0:
            _LOGGER.warning(
                "[RDT_LIBERO_OBS] task=%r image_sizes=%s state_active=%s "
                "joint_min=%.4f joint_max=%.4f gripper_norm=%s",
                self._task,
                [img.size if img is not None else None for img in images],
                torch.where(self._state_mask_128[0] > 0)[0].tolist(),
                float(self._state_128[0, :7].min().item()),
                float(self._state_128[0, :7].max().item()),
                [
                    float(self._state_128[0, 10].item()),
                    float(self._state_128[0, 11].item()),
                ],
            )
```

- [ ] **Step 2: Add action chunk numeric summary**

In `decode_rdt_libero_action_chunk()`, do not log by default. In `RDTSteer._postprocess_actions()`, keep the existing log but ensure it reports:

```python
        log.info(
            f"Decoded LIBERO GT action chunk: shape={tuple(decoded.shape)} "
            f"min={float(decoded.min().item()):.4f} max={float(decoded.max().item()):.4f} "
            f"first={decoded[0, 0].detach().cpu().tolist()}"
        )
```

- [ ] **Step 3: Add mask and checkpoint logging**

In `RDTSteer.from_pretrained()` after resolving `weight_file`, log:

```python
        log.warning(
            f"[RDT_GT_CKPT] model_root={pretrained_path} weight_file={weight_file} "
            f"variant={weight_variant}"
        )
```

In `_RDTModelAdapter.encode_inputs()`, log once:

```python
                f"[RDT_GT_IO] state_active={active_state} "
                f"action_active={LIBERO_ACTION_INDICES} "
                f"images={len(images)} text_shape={tuple(text_embeds.shape)} "
                f"image_embeds={tuple(image_embeds.shape)}"
```

- [ ] **Step 4: Run focused tests to ensure probes do not break CPU path**

Run:

```bash
pytest tests/test_rdt_steer.py tests/test_rdt_libero_obs_processor.py -v
```

Expected:

```text
all selected tests pass
```

- [ ] **Step 5: Commit Task 7**

```bash
git add core/rdt_libero_obs_processor.py core/rdt_policy_steer.py
git commit -m "chore: log first RDT LIBERO GT observation and action chunk"
```

## Task 8: Run Mechanical Model-Load Smoke Check

**Files:**
- No planned source edits.

- [ ] **Step 1: Run a config composition check**

Run:

```bash
python - <<'PY'
from hydra import compose, initialize
from omegaconf import OmegaConf

with initialize(version_base=None, config_path="configs"):
    cfg = compose(config_name="config", overrides=["policy.type=rdt"])

print(OmegaConf.to_yaml(cfg.policy.rdt, resolve=True))
print(OmegaConf.to_yaml(cfg.backend.libero, resolve=True))
assert cfg.policy.type == "rdt"
assert cfg.backend.libero.suite_name == "libero_object"
assert cfg.backend.libero.max_episode_steps == 720
PY
```

Expected:

```text
The printed policy.rdt section points to /mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object and max_episode_steps is 720.
```

- [ ] **Step 2: Run a local checkpoint resolution check without loading the 2.3GB model**

Run:

```bash
python - <<'PY'
from core.rdt_policy_steer import _resolve_rdt_checkpoint_paths

root, weight = _resolve_rdt_checkpoint_paths(
    "/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object",
    "ema",
)
print(root)
print(weight)
assert root == "/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object"
assert weight == "/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object/ema/model.safetensors"
PY
```

Expected:

```text
/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object
/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object/ema/model.safetensors
```

- [ ] **Step 3: Run a model-load import smoke only if GPU memory is available**

Check:

```bash
nvidia-smi
```

If there is enough free GPU memory for RDT + T5/SigLIP, run:

```bash
python - <<'PY'
from core.rdt_policy_steer import RDTSteer

policy = RDTSteer.from_pretrained(
    "/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object",
    text_encoder="/mnt/data/hf_cache/hub/models--google--t5-v1_1-xxl",
    vision_encoder="/mnt/data/hf_cache/hub/models--google--siglip-so400m-patch14-384",
    weight_variant="ema",
    control_frequency=20,
)
print("loaded", type(policy).__name__, policy._action_chunk_horizon)
PY
```

Expected:

```text
loaded RDTSteer 8
```

If CUDA memory is insufficient, record the `nvidia-smi` output and skip this step. Do not start a long rollout as a substitute.

- [ ] **Step 4: Commit Task 8 only if source files changed during smoke fixes**

```bash
git add core tests configs
git commit -m "fix: pass RDT GT mechanical smoke checks"
```

Skip this commit if Task 8 made no file changes.

## Task 9: Tiny Rollout Smoke Test

**Files:**
- No planned source edits.

- [ ] **Step 1: Run one task, one episode, unguided**

Run:

```bash
python main.py \
  policy.type=rdt \
  backend.libero.suite_name=libero_object \
  backend.libero.task_ids_filter='[0]' \
  main.episode_num=1 \
  main.use_guidance=false \
  main.debug_draw_trajectory=false
```

Expected:

```text
The command completes one LIBERO rollout.
An outputs/libero/<timestamp>/ directory is created.
results.txt contains Success count: 0/1 or Success count: 1/1.
A video artifact is saved for the episode.
Logs include [RDT_GT_CKPT], [RDT_GT_IO], and Decoded LIBERO GT action chunk.
```

- [ ] **Step 2: If the rollout crashes, classify the failure before editing**

Use this classification:

```text
Missing key / bad shape:
  return to Task 3 or Task 4.

Checkpoint/config loading error:
  return to Task 5.

CUDA memory failure:
  close competing GPU processes or run on a different GPU.

LIBERO environment/reset failure:
  inspect core/env_adapters/libero_adapter.py reset path and init states.

Rollout completes but fails task:
  proceed to Step 3; task failure is allowed for the one-episode smoke.
```

- [ ] **Step 3: Record the output directory**

Run:

```bash
ls -td outputs/libero/* | head -1
tail -50 "$(ls -td outputs/libero/* | head -1)/results.txt"
```

Expected:

```text
The latest output directory is printed and results.txt is readable.
```

- [ ] **Step 4: Commit only if a crash fix changed source**

```bash
git add core tests configs
git commit -m "fix: pass one-episode RDT LIBERO smoke rollout"
```

Skip this commit if no source files changed.

## Task 10: Ten-Episode Success Gate

**Files:**
- No planned source edits.

- [ ] **Step 1: Run the required command**

Run:

```bash
python main.py policy.type=rdt
```

Expected:

```text
10 LIBERO Object episodes complete.
outputs/libero/<timestamp>/results.txt is written.
Videos are saved under episode output directories.
```

- [ ] **Step 2: Check success count**

Run:

```bash
LATEST="$(ls -td outputs/libero/* | head -1)"
echo "$LATEST"
cat "$LATEST/results.txt"
```

Expected implementation success:

```text
Success count: N/10
```

where `N > 0`.

- [ ] **Step 3: If success is still 0/10, collect non-invasive evidence**

Run:

```bash
LATEST="$(ls -td outputs/libero/* | head -1)"
find "$LATEST" -maxdepth 2 -type f | sort
rg -n "RDT_GT|Decoded LIBERO GT action chunk|Success count" "$LATEST" -S || true
```

Then inspect the first failure video and action summaries. Do not change state/action semantics without comparing one identical observation against the GT wrapper.

- [ ] **Step 4: Commit final source state if the gate passes**

```bash
git status --short
git add core tests configs docs/superpowers/plans/2026-05-26-rdt-libero-gt-rollout-reintegration.md
git commit -m "fix: align RDT LIBERO rollout with GT semantics"
```

Only commit the plan file with source if the implementation was completed in the same branch. If the plan was already committed separately, do not add it again.

## Completion Checklist

- [ ] `pytest tests/test_rdt_runtime_contract.py -v` passes.
- [ ] `pytest tests/test_rdt_libero_action_converter.py -v` passes.
- [ ] `pytest tests/test_rdt_libero_obs_processor.py -v` passes.
- [ ] `pytest tests/test_rdt_steer.py -v` passes.
- [ ] `pytest tests/test_env_adapters_imports.py -v` passes.
- [ ] `python main.py policy.type=rdt backend.libero.task_ids_filter='[0]' main.episode_num=1 main.use_guidance=false main.debug_draw_trajectory=false` completes mechanically.
- [ ] `python main.py policy.type=rdt` completes 10 LIBERO Object episodes.
- [ ] Latest `outputs/libero/<timestamp>/results.txt` reports success greater than `0/10`.
- [ ] `git diff -- third_party/rdt third_party/libero third_party/Libero_RDT` is empty.
