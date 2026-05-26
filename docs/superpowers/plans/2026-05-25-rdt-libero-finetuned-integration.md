# RDT LIBERO-Finetuned Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `python main.py policy.type=rdt` run the LIBERO-finetuned RDT checkpoint on LIBERO through the existing VLS runtime and achieve non-zero success over a 10-episode evaluation.

**Architecture:** Keep `core/rdt_policy_steer.py` as the single RDT policy wrapper for unguided denoising and future VLS steering. Add LIBERO-specific observation/action processors that mirror `third_party/rdt/data/libero_vla_dataset.py`, then update the RDT policy wrapper to consume full 128D LIBERO state/action masks and decode sampled 128D chunks into LIBERO 7D OSC actions.

**Tech Stack:** Python, PyTorch, NumPy, SciPy rotations, Hydra/OmegaConf, existing LIBERO adapter, existing RDT submodule, pytest.

---

## Source Documents

Read these before executing:

```text
docs/docs/01_specs/2026-05-25-rdt-libero-finetuned-integration-design.md
docs/superpowers/specs/2026-05-20-rdt-libero-finetune-design.md
docs/superpowers/plans/2026-05-23-rdt-libero-finetune-plan.md
third_party/rdt/data/libero_vla_dataset.py
third_party/rdt/agent/libero_dataset_semantics_analysis.md
```

The semantic constants are:

```text
LIBERO_RDT_INDICES = [30, 31, 32, 33, 34, 35, 36, 37, 38, 10]
RDT active mask sorted order = [10, 30, 31, 32, 33, 34, 35, 36, 37, 38]
state/action dimension = 128
prediction horizon = 64
runtime execution horizon = 8 initially
LIBERO raw OSC action = [dx, dy, dz, drot_x, drot_y, drot_z, gripper]
LIBERO raw gripper = -1 open, +1 close
RDT right_gripper_open = 1 open, 0 closed
```

Checkpoint and encoder paths:

```text
/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-60000
/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-60000/ema/model.safetensors
/mnt/data/hf_cache/hub/models--google--t5-v1_1-xxl
/mnt/data/hf_cache/hub/models--google--siglip-so400m-patch14-384
```

## File Map

| File | Action | Responsibility |
|---|---|---|
| `core/rdt_libero_action_converter.py` | Create | Pure LIBERO action transform functions matching fine-tuning. |
| `core/rdt_libero_obs_processor.py` | Create | Convert online LIBERO observations into RDT image list, 128D state, 128D mask, and task text. |
| `core/rdt_policy_steer.py` | Modify | Keep the unified RDT policy wrapper, but make its active runtime path LIBERO-finetuned only. |
| `configs/policy.yaml` | Modify | Point `policy.type=rdt` at checkpoint-60000, EMA weights, local encoders, and LIBERO semantics. |
| `main.py` | Modify | Keep `policy.type=rdt`; pass RDT-specific checkpoint/encoder/weight fields into `RDTSteer.from_pretrained`. |
| `tests/test_rdt_libero_action_converter.py` | Create | CPU tests for action conversion, gripper convention, and 6D rotation round trip. |
| `tests/test_rdt_libero_obs_processor.py` | Create | CPU tests for online observation conversion, image history, state mask, and language fail-fast behavior. |
| `tests/test_rdt_steer.py` | Modify | Update stubs/tests for full 128D LIBERO denoising and `(1, H, 7)` output. |
| `tests/test_rdt_runtime_contract.py` | Create | File/config discovery tests for the checkpoint, encoders, and `policy.type=rdt` route. |

Do not modify:

```text
third_party/rdt/
third_party/libero/
```

---

## Task 1: Add LIBERO Action Converter Contract Tests

**Files:**
- Create: `tests/test_rdt_libero_action_converter.py`

- [ ] **Step 1.1: Write the failing action-converter tests**

Create `tests/test_rdt_libero_action_converter.py` with:

```python
import numpy as np
import pytest
import torch

from core.rdt_libero_action_converter import (
    LIBERO_RDT_INDICES,
    ACTIVE_INDICES_SORTED,
    decode_rdt_libero_action_chunk,
    libero_raw_to_rdt_action,
    map_libero_gripper_action_to_open,
    map_open_to_libero_gripper,
    ortho6d_to_rotvec,
    rdt_action_to_libero_raw,
    rotvec_to_ortho6d,
)


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
    np.testing.assert_allclose(action_128[30:33], np.array([0.025, -0.0125, 0.0125], dtype=np.float32))
    np.testing.assert_allclose(action_128[33:39], rotvec_to_ortho6d(np.array([[0.05, -0.10, 0.15]], dtype=np.float32))[0])
    assert action_128[10] == pytest.approx(1.0)

    restored = rdt_action_to_libero_raw(action_128)
    np.testing.assert_allclose(restored[:6], raw[:6], atol=1e-5)
    assert restored[6] == pytest.approx(-1.0)


def test_decode_chunk_returns_torch_1_h_7_and_clips_controller_range():
    pred = torch.zeros(2, 64, 128, dtype=torch.float32)
    pred[0, 0, 30:33] = torch.tensor([0.10, -0.10, 0.025])  # raw controller would be [2, -2, 0.5]
    pred[0, 0, 33:39] = torch.from_numpy(rotvec_to_ortho6d(np.array([[1.0, 0.0, 0.0]], dtype=np.float32))[0])
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
```

- [ ] **Step 1.2: Run the failing tests**

Run:

```bash
pytest tests/test_rdt_libero_action_converter.py -q
```

Expected: fail with an import error because `core.rdt_libero_action_converter` does not exist yet.

- [ ] **Step 1.3: Commit the failing tests**

```bash
git add tests/test_rdt_libero_action_converter.py
git commit -m "test: add rdt libero action converter contract"
```

---

## Task 2: Implement LIBERO Action Converter

**Files:**
- Create: `core/rdt_libero_action_converter.py`
- Test: `tests/test_rdt_libero_action_converter.py`

- [ ] **Step 2.1: Add the LIBERO action converter**

Create `core/rdt_libero_action_converter.py`:

```python
from __future__ import annotations

import numpy as np
import torch
from scipy.spatial.transform import Rotation as R

LIBERO_RDT_INDICES = [30, 31, 32, 33, 34, 35, 36, 37, 38, 10]
ACTIVE_INDICES_SORTED = sorted(LIBERO_RDT_INDICES)

EEF_POS_SLICE = slice(30, 33)
EEF_ROT6D_SLICE = slice(33, 39)
GRIPPER_OPEN_INDEX = 10

OSC_POS_SCALE = np.array([0.05, 0.05, 0.05], dtype=np.float32)
OSC_ROT_SCALE = np.array([0.5, 0.5, 0.5], dtype=np.float32)


def rotvec_to_ortho6d(rotvec: np.ndarray) -> np.ndarray:
    rotvec = np.asarray(rotvec, dtype=np.float32)
    original_shape = rotvec.shape[:-1]
    if rotvec.shape[-1] != 3:
        raise ValueError(f"rotvec last dim must be 3, got {rotvec.shape}")
    matrix = R.from_rotvec(rotvec.reshape(-1, 3)).as_matrix().astype(np.float32)
    ortho6d = matrix[:, :, :2].transpose(0, 2, 1).reshape(-1, 6)
    return ortho6d.reshape(original_shape + (6,))


def _normalize_vector(v: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(norm, 1e-8)


def ortho6d_to_rotmat(ortho6d: np.ndarray) -> np.ndarray:
    ortho6d = np.asarray(ortho6d, dtype=np.float32)
    original_shape = ortho6d.shape[:-1]
    if ortho6d.shape[-1] != 6:
        raise ValueError(f"ortho6d last dim must be 6, got {ortho6d.shape}")
    flat = ortho6d.reshape(-1, 6)
    x_raw = flat[:, 0:3]
    y_raw = flat[:, 3:6]
    x = _normalize_vector(x_raw)
    z = _normalize_vector(np.cross(x, y_raw))
    y = np.cross(z, x)
    matrix = np.stack([x, y, z], axis=-1)
    return matrix.reshape(original_shape + (3, 3))


def ortho6d_to_rotvec(ortho6d: np.ndarray) -> np.ndarray:
    matrix = ortho6d_to_rotmat(ortho6d)
    original_shape = matrix.shape[:-2]
    rotvec = R.from_matrix(matrix.reshape(-1, 3, 3)).as_rotvec().astype(np.float32)
    return rotvec.reshape(original_shape + (3,))


def map_libero_gripper_action_to_open(raw_gripper: np.ndarray | float) -> np.ndarray:
    raw_gripper = np.asarray(raw_gripper, dtype=np.float32)
    return np.clip((1.0 - raw_gripper) / 2.0, 0.0, 1.0).astype(np.float32)


def map_open_to_libero_gripper(open_scalar: np.ndarray | float) -> np.ndarray:
    open_scalar = np.asarray(open_scalar, dtype=np.float32)
    return np.clip(1.0 - 2.0 * open_scalar, -1.0, 1.0).astype(np.float32)


def map_libero_gripper_state(gripper_qpos: np.ndarray) -> np.ndarray:
    gripper_qpos = np.asarray(gripper_qpos, dtype=np.float32)
    if gripper_qpos.shape[-1] != 2:
        raise ValueError(f"gripper qpos last dim must be 2, got {gripper_qpos.shape}")
    width = gripper_qpos[..., 0] - gripper_qpos[..., 1]
    return np.clip(width / 0.08, 0.0, 1.0).astype(np.float32)


def libero_raw_to_rdt_action(raw_action_7d: np.ndarray) -> np.ndarray:
    raw = np.asarray(raw_action_7d, dtype=np.float32)
    if raw.shape[-1] != 7:
        raise ValueError(f"LIBERO raw action last dim must be 7, got {raw.shape}")

    flat = raw.reshape(-1, 7)
    action = np.zeros((flat.shape[0], 128), dtype=np.float32)
    action[:, EEF_POS_SLICE] = flat[:, :3] * OSC_POS_SCALE
    action[:, EEF_ROT6D_SLICE] = rotvec_to_ortho6d(flat[:, 3:6] * OSC_ROT_SCALE)
    action[:, GRIPPER_OPEN_INDEX] = map_libero_gripper_action_to_open(flat[:, 6])
    return action.reshape(raw.shape[:-1] + (128,))


def rdt_action_to_libero_raw(action_128d: np.ndarray) -> np.ndarray:
    action = np.asarray(action_128d, dtype=np.float32)
    if action.shape[-1] != 128:
        raise ValueError(f"RDT action last dim must be 128, got {action.shape}")

    flat = action.reshape(-1, 128)
    raw = np.zeros((flat.shape[0], 7), dtype=np.float32)
    raw[:, :3] = flat[:, EEF_POS_SLICE] / OSC_POS_SCALE
    raw[:, 3:6] = ortho6d_to_rotvec(flat[:, EEF_ROT6D_SLICE]) / OSC_ROT_SCALE
    raw[:, 6] = map_open_to_libero_gripper(flat[:, GRIPPER_OPEN_INDEX])
    raw[:, :6] = np.clip(raw[:, :6], -1.0, 1.0)
    raw[:, 6] = np.where(raw[:, 6] > 0.0, 1.0, -1.0).astype(np.float32)
    return raw.reshape(action.shape[:-1] + (7,))


def decode_rdt_libero_action_chunk(
    pred_actions_128: torch.Tensor,
    action_chunk_horizon: int,
) -> torch.Tensor:
    if not torch.is_tensor(pred_actions_128):
        raise TypeError(f"pred_actions_128 must be a torch.Tensor, got {type(pred_actions_128).__name__}")
    if pred_actions_128.ndim != 3 or pred_actions_128.shape[-1] != 128:
        raise ValueError(f"Expected pred_actions_128 shape (B, 64, 128), got {tuple(pred_actions_128.shape)}")
    if action_chunk_horizon < 1 or action_chunk_horizon > pred_actions_128.shape[1]:
        raise ValueError(
            f"action_chunk_horizon must be in [1, {pred_actions_128.shape[1]}], got {action_chunk_horizon}"
        )

    first_particle = pred_actions_128[0, :action_chunk_horizon].detach().cpu().float().numpy()
    raw = rdt_action_to_libero_raw(first_particle).astype(np.float32)
    return torch.from_numpy(raw).unsqueeze(0)
```

- [ ] **Step 2.2: Run action converter tests**

Run:

```bash
pytest tests/test_rdt_libero_action_converter.py -q
```

Expected: all tests pass.

- [ ] **Step 2.3: Commit the converter**

```bash
git add core/rdt_libero_action_converter.py tests/test_rdt_libero_action_converter.py
git commit -m "feat: add rdt libero action converter"
```

---

## Task 3: Add LIBERO Observation Processor Contract Tests

**Files:**
- Create: `tests/test_rdt_libero_obs_processor.py`

- [ ] **Step 3.1: Write the failing observation tests**

Create `tests/test_rdt_libero_obs_processor.py`:

```python
import numpy as np
import pytest
import torch
from PIL import Image

from core.rdt_libero_obs_processor import RDTLiberoObsProcessor


def _image_batch(red: float, green: float, blue: float) -> torch.Tensor:
    img = torch.zeros(1, 3, 8, 8, dtype=torch.float32)
    img[:, 0] = red
    img[:, 1] = green
    img[:, 2] = blue
    return img


def _obs(task: str = "pick up the mug") -> dict:
    return {
        "observation.images.image": _image_batch(1.0, 0.0, 0.0),
        "observation.images.image2": _image_batch(0.0, 1.0, 0.0),
        "observation.state": torch.tensor(
            [[0.10, -0.20, 0.80, 0.0, 0.0, 0.0, 0.04, -0.04]],
            dtype=torch.float32,
        ),
        "task": [task],
    }


def test_process_builds_training_matching_state_and_mask():
    proc = RDTLiberoObsProcessor(undo_preprocessor_flip=False)
    converted = proc.process(_obs())

    assert converted.state_128.shape == (1, 128)
    assert converted.state_mask_128.shape == (1, 128)
    assert np.where(converted.state_mask_128.numpy()[0] > 0)[0].tolist() == [10, 30, 31, 32, 33, 34, 35, 36, 37, 38]
    torch.testing.assert_close(converted.state_128[0, 30:33], torch.tensor([0.10, -0.20, 0.80]))
    torch.testing.assert_close(converted.state_128[0, 33:39], torch.tensor([1.0, 0.0, 0.0, 0.0, 1.0, 0.0]))
    assert converted.state_128[0, 10].item() == pytest.approx(1.0)
    assert converted.task == "pick up the mug"


def test_process_builds_two_frame_two_camera_history():
    proc = RDTLiberoObsProcessor(undo_preprocessor_flip=False)
    first = proc.process(_obs("first task"))

    assert len(first.images) == 6
    assert isinstance(first.images[0], Image.Image)
    assert isinstance(first.images[1], Image.Image)
    assert first.images[2] is None
    assert isinstance(first.images[3], Image.Image)
    assert isinstance(first.images[4], Image.Image)
    assert first.images[5] is None
    assert first.images[0].getpixel((0, 0)) == first.images[3].getpixel((0, 0))
    assert first.images[1].getpixel((0, 0)) == first.images[4].getpixel((0, 0))

    second_obs = _obs("second task")
    second_obs["observation.images.image"] = _image_batch(0.0, 0.0, 1.0)
    second = proc.process(second_obs)
    assert second.images[0].getpixel((0, 0)) == (255, 0, 0)
    assert second.images[3].getpixel((0, 0)) == (0, 0, 255)


def test_reset_clears_image_history():
    proc = RDTLiberoObsProcessor(undo_preprocessor_flip=False)
    proc.process(_obs())
    proc.reset()

    new_obs = _obs("new")
    new_obs["observation.images.image"] = _image_batch(0.0, 0.0, 1.0)
    converted = proc.process(new_obs)

    assert converted.images[0].getpixel((0, 0)) == (0, 0, 255)
    assert converted.images[3].getpixel((0, 0)) == (0, 0, 255)


def test_missing_wrist_camera_fails_fast():
    proc = RDTLiberoObsProcessor()
    obs = _obs()
    obs.pop("observation.images.image2")
    with pytest.raises(KeyError, match="observation.images.image2"):
        proc.process(obs)


def test_empty_language_fails_fast():
    proc = RDTLiberoObsProcessor()
    with pytest.raises(ValueError, match="empty"):
        proc.process(_obs("   "))


def test_bad_state_shape_fails_fast():
    proc = RDTLiberoObsProcessor()
    obs = _obs()
    obs["observation.state"] = torch.zeros(1, 7)
    with pytest.raises(ValueError, match="8"):
        proc.process(obs)
```

- [ ] **Step 3.2: Run the failing tests**

Run:

```bash
pytest tests/test_rdt_libero_obs_processor.py -q
```

Expected: fail with an import error because `core.rdt_libero_obs_processor` does not exist yet.

- [ ] **Step 3.3: Commit the failing tests**

```bash
git add tests/test_rdt_libero_obs_processor.py
git commit -m "test: add rdt libero observation processor contract"
```

---

## Task 4: Implement LIBERO Observation Processor

**Files:**
- Create: `core/rdt_libero_obs_processor.py`
- Test: `tests/test_rdt_libero_obs_processor.py`

- [ ] **Step 4.1: Add the observation processor**

Create `core/rdt_libero_obs_processor.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import torch
from PIL import Image

from core.rdt_libero_action_converter import (
    ACTIVE_INDICES_SORTED,
    EEF_POS_SLICE,
    EEF_ROT6D_SLICE,
    GRIPPER_OPEN_INDEX,
    map_libero_gripper_state,
    rotvec_to_ortho6d,
)

AGENTVIEW_KEY = "observation.images.image"
WRIST_KEY = "observation.images.image2"
STATE_KEY = "observation.state"
TASK_KEY = "task"


@dataclass(frozen=True)
class RDTLiberoObservation:
    images: list[Image.Image | None]
    state_128: torch.Tensor
    state_mask_128: torch.Tensor
    task: str


class RDTLiberoObsProcessor:
    def __init__(self, undo_preprocessor_flip: bool = True, debug_first_step: bool = False) -> None:
        self.undo_preprocessor_flip = undo_preprocessor_flip
        self.debug_first_step = debug_first_step
        self._prev_agentview: Optional[Image.Image] = None
        self._prev_wrist: Optional[Image.Image] = None
        self._logged_first_step = False

    def reset(self) -> None:
        self._prev_agentview = None
        self._prev_wrist = None
        self._logged_first_step = False

    def process(self, obs: dict) -> RDTLiberoObservation:
        agent_now = self._image_to_pil(obs, AGENTVIEW_KEY)
        wrist_now = self._image_to_pil(obs, WRIST_KEY)

        agent_prev = self._prev_agentview if self._prev_agentview is not None else agent_now
        wrist_prev = self._prev_wrist if self._prev_wrist is not None else wrist_now
        self._prev_agentview = agent_now
        self._prev_wrist = wrist_now

        images: list[Image.Image | None] = [
            agent_prev,
            wrist_prev,
            None,
            agent_now,
            wrist_now,
            None,
        ]

        state_128, state_mask_128 = self._build_state_and_mask(obs)
        task = self._extract_task(obs)
        self._log_first_step(images, state_128, state_mask_128, task)
        return RDTLiberoObservation(
            images=images,
            state_128=state_128,
            state_mask_128=state_mask_128,
            task=task,
        )

    def _image_to_pil(self, obs: dict, key: str) -> Image.Image:
        if key not in obs:
            raise KeyError(f"Missing required LIBERO image key: {key}")
        img = obs[key]
        if not torch.is_tensor(img):
            img = torch.as_tensor(img)
        if img.ndim != 4 or img.shape[0] < 1 or img.shape[1] != 3:
            raise ValueError(f"{key} must have shape (B, 3, H, W), got {tuple(img.shape)}")
        img = img[0].detach().cpu().float()
        if not torch.isfinite(img).all():
            raise ValueError(f"{key} contains non-finite values")
        if self.undo_preprocessor_flip:
            img = torch.flip(img, dims=[1, 2])
        img = img.clamp(0.0, 1.0)
        arr = (img * 255.0).round().byte().permute(1, 2, 0).numpy()
        return Image.fromarray(arr, mode="RGB")

    def _build_state_and_mask(self, obs: dict) -> tuple[torch.Tensor, torch.Tensor]:
        if STATE_KEY not in obs:
            raise KeyError(f"Missing required LIBERO state key: {STATE_KEY}")
        state = obs[STATE_KEY]
        if not torch.is_tensor(state):
            state = torch.as_tensor(state)
        if state.ndim != 2 or state.shape[0] < 1 or state.shape[1] < 8:
            raise ValueError(f"{STATE_KEY} must have shape (B, at least 8), got {tuple(state.shape)}")
        state_np = state[0, :8].detach().cpu().float().numpy()
        if not np.isfinite(state_np).all():
            raise ValueError(f"{STATE_KEY} contains non-finite values")

        eef_pos = state_np[:3].astype(np.float32)
        eef_rotvec = state_np[3:6].astype(np.float32)
        gripper_qpos = state_np[6:8].astype(np.float32)

        state_128 = np.zeros((1, 128), dtype=np.float32)
        state_mask = np.zeros((1, 128), dtype=np.float32)
        state_128[0, EEF_POS_SLICE] = eef_pos
        state_128[0, EEF_ROT6D_SLICE] = rotvec_to_ortho6d(eef_rotvec[None])[0]
        state_128[0, GRIPPER_OPEN_INDEX] = map_libero_gripper_state(gripper_qpos[None])[0]
        state_mask[0, ACTIVE_INDICES_SORTED] = 1.0
        return torch.from_numpy(state_128), torch.from_numpy(state_mask)

    def _extract_task(self, obs: dict) -> str:
        raw_task = obs.get(TASK_KEY, [""])
        task = raw_task[0] if isinstance(raw_task, (list, tuple)) else str(raw_task)
        task = str(task)
        if not task.strip():
            raise ValueError("RDT LIBERO task instruction is empty")
        return task

    def _log_first_step(
        self,
        images: list[Image.Image | None],
        state_128: torch.Tensor,
        state_mask_128: torch.Tensor,
        task: str,
    ) -> None:
        if not self.debug_first_step or self._logged_first_step:
            return
        import logging

        active = np.where(state_mask_128.numpy()[0] > 0)[0].tolist()
        logging.getLogger("RDTLiberoObsProcessor").warning(
            "[RDT_LIBERO_OBS] images=%s state_shape=%s active=%s "
            "eef_pos=%s rot6d=%s gripper_open=%.3f task=%r",
            [None if image is None else image.size for image in images],
            tuple(state_128.shape),
            active,
            state_128[0, EEF_POS_SLICE].tolist(),
            state_128[0, EEF_ROT6D_SLICE].tolist(),
            float(state_128[0, GRIPPER_OPEN_INDEX].item()),
            task,
        )
        self._logged_first_step = True
```

- [ ] **Step 4.2: Run observation tests**

Run:

```bash
pytest tests/test_rdt_libero_obs_processor.py -q
```

Expected: all tests pass.

- [ ] **Step 4.3: Commit the processor**

```bash
git add core/rdt_libero_obs_processor.py tests/test_rdt_libero_obs_processor.py
git commit -m "feat: add rdt libero observation processor"
```

---

## Task 5: Add Runtime Contract Tests

**Files:**
- Create: `tests/test_rdt_runtime_contract.py`

- [ ] **Step 5.1: Add file/config discovery tests**

Create `tests/test_rdt_runtime_contract.py`:

```python
from pathlib import Path

from omegaconf import OmegaConf


CHECKPOINT = Path("/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-60000")
T5 = Path("/mnt/data/hf_cache/hub/models--google--t5-v1_1-xxl")
SIGLIP = Path("/mnt/data/hf_cache/hub/models--google--siglip-so400m-patch14-384")


def test_target_checkpoint_and_encoder_paths_exist():
    assert CHECKPOINT.is_dir()
    assert (CHECKPOINT / "config.json").is_file()
    assert (CHECKPOINT / "ema" / "model.safetensors").is_file()
    assert T5.is_dir()
    assert SIGLIP.is_dir()


def test_checkpoint_config_matches_rdt_libero_contract():
    import json

    cfg = json.loads((CHECKPOINT / "config.json").read_text())
    assert cfg["pred_horizon"] == 64
    assert cfg["action_dim"] == 128
    assert cfg["state_token_dim"] == 128
    assert cfg["img_pos_embed_config"][0][1][:2] == [2, 3]
    assert cfg["lang_token_dim"] == 4096
    assert cfg["img_token_dim"] == 1152


def test_policy_yaml_keeps_rdt_route_and_libero_checkpoint():
    cfg = OmegaConf.load("configs/policy.yaml")
    assert cfg.type in {"pi05", "rdt", "diffusion"}
    assert cfg.rdt.pretrained_path == str(CHECKPOINT)
    assert cfg.rdt.weight_variant == "ema"
    assert cfg.rdt.text_encoder == str(T5)
    assert cfg.rdt.vision_encoder == str(SIGLIP)
    assert cfg.rdt.semantics == "libero_finetuned"
```

- [ ] **Step 5.2: Run the failing runtime contract test**

Run:

```bash
pytest tests/test_rdt_runtime_contract.py -q
```

Expected: the first two tests pass on this machine; the `configs/policy.yaml` test fails until Task 8 updates the config.

- [ ] **Step 5.3: Commit the runtime contract test**

```bash
git add tests/test_rdt_runtime_contract.py
git commit -m "test: add rdt libero runtime contract"
```

---

## Task 6: Update RDT Policy Unit Tests For Full 128D LIBERO Path

**Files:**
- Modify: `tests/test_rdt_steer.py`

- [ ] **Step 6.1: Replace the stub model with a LIBERO-shaped stub**

In `tests/test_rdt_steer.py`, replace `_StubDiT`, `_StubScheduler`, and `_StubRDTModel` with:

```python
class _StubDiT(nn.Module):
    def forward(self, x, t, cond):
        return torch.zeros_like(x)


class _StubScheduler:
    def __init__(self, n=5):
        self.timesteps = torch.arange(n - 1, -1, -1, dtype=torch.long)

    def set_timesteps(self, n):
        self.timesteps = torch.arange(n - 1, -1, -1, dtype=torch.long)

    def step(self, noise_pred, t, x_t):
        out = MagicMock()
        out.prev_sample = x_t * 0.0
        return out


class _StubRDTModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.dit = _StubDiT()
        self.noise_scheduler = _StubScheduler()

    def encode_inputs(self, state_128, state_mask_128, images, text_embeds):
        return {
            "lang_cond": torch.zeros(1, 1, 4),
            "lang_attn_mask": torch.ones(1, 1, dtype=torch.bool),
            "img_cond": torch.zeros(1, 1, 4),
            "state_traj": torch.zeros(1, 1, 4),
            "action_mask": state_mask_128.float().unsqueeze(1),
            "ctrl_freqs": torch.tensor([20]),
            "action_indices": [30, 31, 32, 33, 34, 35, 36, 37, 38, 10],
            "unified_action_dim": 128,
        }
```

- [ ] **Step 6.2: Update `stub_steer` fixture**

Replace the fixture with:

```python
@pytest.fixture
def stub_steer():
    from core.rdt_policy_steer import RDTSteer

    return RDTSteer(rdt_model=_StubRDTModel(), num_inference_steps=5)
```

- [ ] **Step 6.3: Update `mock_batch` fixture to match LIBERO state**

Replace the fixture with:

```python
@pytest.fixture
def mock_batch():
    B = 4
    return {
        "observation.images.image": torch.zeros(B, 3, 16, 16),
        "observation.images.image2": torch.zeros(B, 3, 16, 16),
        "observation.state": torch.tensor(
            [[0.10, -0.20, 0.80, 0.0, 0.0, 0.0, 0.04, -0.04]] * B,
            dtype=torch.float32,
        ),
        "task": ["pick up the red block"] * B,
    }
```

- [ ] **Step 6.4: Add assertions for full 128D masks and LIBERO output**

Add this test below `test_forward_shape`:

```python
def test_unguided_uses_full_128d_libero_mask(stub_steer, stub_adapter, mock_batch):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"action_chunk_horizon": 8, "debug_first_step": True},
    )
    converted = stub_steer._obs_processor.process(mock_batch)
    assert converted.state_128.shape == (1, 128)
    assert converted.state_mask_128.shape == (1, 128)
    assert torch.where(converted.state_mask_128[0] > 0)[0].tolist() == [10, 30, 31, 32, 33, 34, 35, 36, 37, 38]
    assert converted.task == "pick up the red block"

    raw = stub_steer._predict_unguided(
        converted.state_128,
        converted.state_mask_128,
        converted.images,
        torch.zeros(1, 1, 4096),
        B=2,
    )
    assert raw.shape == (2, 64, 128)
```

- [ ] **Step 6.5: Replace current guided tests with an explicit deferral test**

Replace `test_fkd_rollout` and `test_gradient_steering` with:

```python
def test_guided_rdt_libero_path_is_explicitly_deferred(stub_steer, stub_adapter, mock_batch):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"action_chunk_horizon": 8, "debug_first_step": True},
    )

    with pytest.raises(NotImplementedError, match="RDT LIBERO VLS steering"):
        stub_steer.select_action(
            mock_batch,
            generate_new_chunk=True,
            use_guidance=True,
            guidance_fns=[lambda keypoints, traj: traj.sum()],
            keypoints=np.zeros((3, 3), dtype=np.float32),
        )
```

This keeps `core/rdt_policy_steer.py` as the unified policy wrapper while making
the current implementation scope explicitly unguided.

- [ ] **Step 6.6: Run the failing RDT policy tests**

Run:

```bash
pytest tests/test_rdt_steer.py -q
```

Expected: fail until `core/rdt_policy_steer.py` is updated to import/use the new observation and action helpers.

- [ ] **Step 6.7: Commit the updated failing tests**

```bash
git add tests/test_rdt_steer.py
git commit -m "test: update rdt steer tests for libero semantics"
```

---

## Task 7: Align `core/rdt_policy_steer.py` With LIBERO-Finetuned Semantics

**Files:**
- Modify: `core/rdt_policy_steer.py`
- Test: `tests/test_rdt_steer.py`

- [ ] **Step 7.1: Replace imports and constants**

At the top of `core/rdt_policy_steer.py`, remove imports of `RDTObsProcessor` and old ManiSkill constants. Add:

```python
from core.rdt_libero_action_converter import (
    ACTIVE_INDICES_SORTED,
    LIBERO_RDT_INDICES,
    decode_rdt_libero_action_chunk,
)
from core.rdt_libero_obs_processor import RDTLiberoObsProcessor
```

Keep `_ARM_JOINTS = slice(0, 7)` only if `_rdt_sample_to_trajectory_3d` still needs a temporary fallback during the same task. Remove it before the task is complete if no code references it.

- [ ] **Step 7.2: Change `_RDTModelAdapter.encode_inputs` signature and state handling**

Replace the method signature:

```python
def encode_inputs(self, state_128: Tensor, state_mask_128: Tensor, images: list, text_embeds: Tensor) -> dict:
```

Replace the proprio/state block inside the method with:

```python
unified_action_dim = int(real.args["model"]["state_token_dim"])
if unified_action_dim != 128:
    raise ValueError(f"Expected RDT state_token_dim=128, got {unified_action_dim}")

states = state_128.to(device=device, dtype=dtype)
state_elem_mask = state_mask_128.to(device=device, dtype=dtype)
if states.shape != (1, unified_action_dim):
    raise ValueError(f"state_128 must have shape (1, 128), got {tuple(states.shape)}")
if state_elem_mask.shape != (1, unified_action_dim):
    raise ValueError(f"state_mask_128 must have shape (1, 128), got {tuple(state_elem_mask.shape)}")
active = torch.where(state_elem_mask[0] > 0)[0].detach().cpu().tolist()
if active != ACTIVE_INDICES_SORTED:
    raise ValueError(f"LIBERO active mask mismatch: expected {ACTIVE_INDICES_SORTED}, got {active}")

states = states.unsqueeze(1)
action_indices = LIBERO_RDT_INDICES
ctrl_freqs = torch.tensor([real.control_frequency], device=device)
```

Keep the existing image encoding and language adaptation logic, then return:

```python
return {
    "lang_cond": lang_cond,
    "lang_attn_mask": lang_attn_mask,
    "img_cond": img_cond,
    "state_traj": state_traj,
    "action_mask": state_elem_mask.unsqueeze(1),
    "ctrl_freqs": ctrl_freqs,
    "action_indices": action_indices,
    "unified_action_dim": unified_action_dim,
}
```

- [ ] **Step 7.3: Simplify `RDTSteer.__init__`**

Change the constructor signature to:

```python
def __init__(self, rdt_model, num_inference_steps: int = 5) -> None:
```

Remove `libero_mode` and any branch that selects ManiSkill semantics. Set:

```python
self._obs_processor: Optional[RDTLiberoObsProcessor] = None
```

- [ ] **Step 7.4: Update `from_pretrained` signature and weight selection**

Change the signature to:

```python
@classmethod
def from_pretrained(
    cls,
    pretrained_path: str,
    num_inference_steps: Optional[int] = None,
    vision_encoder: str = "/mnt/data/hf_cache/hub/models--google--siglip-so400m-patch14-384",
    text_encoder: str = "/mnt/data/hf_cache/hub/models--google--t5-v1_1-xxl",
    weight_variant: str = "ema",
    control_frequency: int = 20,
) -> "RDTSteer":
```

In the weight-file section, prefer the requested variant:

```python
variant_dirs = []
if weight_variant:
    variant_dirs.append(os.path.join(pretrained_path, weight_variant))
variant_dirs.append(pretrained_path)
variant_dirs.append(os.path.join(pretrained_path, "rdt"))

weight_file = None
for search_root in variant_dirs:
    if not os.path.isdir(search_root):
        continue
    for fname in ("model.safetensors", "pytorch_model.bin", "mp_rank_00_model_states.pt", "rdt-1b.pt"):
        candidate = os.path.join(search_root, fname)
        if os.path.exists(candidate):
            weight_file = candidate
            break
    if weight_file is not None:
        break
if weight_file is None:
    raise FileNotFoundError(f"No RDT weight file found for variant={weight_variant!r} under {pretrained_path}")
```

When calling `create_model`, pass local encoders and control frequency:

```python
real_model = create_model(
    args,
    pretrained=weight_file,
    pretrained_text_encoder_name_or_path=text_encoder,
    pretrained_vision_encoder_name_or_path=vision_encoder,
    control_frequency=control_frequency,
)
```

When `num_inference_steps is None`, use the checkpoint scheduler:

```python
if num_inference_steps is None:
    num_inference_steps = int(args["model"]["noise_scheduler"].get("num_inference_timesteps", 5))
```

Remove log messages that state the runtime is feeding ManiSkill 8D proprio/action. Replace them with:

```python
log.warning(
    "[RDT_LIBERO_CONFIG] checkpoint=%s weight_file=%s steps=%s active_indices=%s",
    pretrained_path,
    weight_file,
    num_inference_steps,
    LIBERO_RDT_INDICES,
)
```

- [ ] **Step 7.5: Update `post_init`**

Replace construction of `RDTObsProcessor` with:

```python
if self._obs_processor is None:
    self._obs_processor = RDTLiberoObsProcessor(
        undo_preprocessor_flip=bool(policy_config.get("undo_libero_preprocessor_flip", True)),
        debug_first_step=bool(policy_config.get("debug_first_step", False)),
    )
```

Remove `_adapter`, `_undo_libero_flip`, `_libero_eef_mode`, and `_text_encoder_fn`
writes into the old processor. Language embedding is handled by the
`RDTSteer._get_lang_embed()` helper in the next step.

- [ ] **Step 7.6: Update language embedding helper**

Add this method to `RDTSteer`:

```python
def _get_lang_embed(self, task: str) -> Tensor:
    real = None
    try:
        real = object.__getattribute__(self._rdt_model, "_real")
    except Exception:
        real = None
    if real is not None and callable(getattr(real, "encode_instruction", None)):
        embed = real.encode_instruction(task, device=str(self.device))
        return embed.float().to(self.device)
    return torch.zeros(1, 1, 4096, device=self.device)
```

The zero fallback is for CPU stub tests only. In real checkpoint runs, `real.encode_instruction` must be present.

- [ ] **Step 7.7: Update `select_action`**

Inside `if generate_new_chunk:`, replace old processor tuple unpacking with:

```python
converted = self._obs_processor.process(batch)
text_embed = self._get_lang_embed(converted.task)
```

Call the denoising paths with 128D state/mask:

```python
if use_guidance:
    raise NotImplementedError("RDT LIBERO VLS steering is deferred until unguided LIBERO semantics pass.")

raw = self._predict_unguided(
    converted.state_128,
    converted.state_mask_128,
    converted.images,
    text_embed,
    B,
)
```

The old `_guided_denoise_loop` may remain in the file as the future VLS hook,
but the active `policy.type=rdt` validation path must be unguided until the
10-episode non-zero success gate passes.

- [ ] **Step 7.8: Update `_predict_unguided`**

Replace the method signature and body with:

```python
def _predict_unguided(
    self,
    state_128: Tensor,
    state_mask_128: Tensor,
    images: list,
    text_embed: Tensor,
    B: int,
) -> Tensor:
    device = self.device
    try:
        dtype = next(self._dit.parameters()).dtype
    except StopIteration:
        dtype = torch.float32

    cond = self._rdt_model.encode_inputs(state_128, state_mask_128, images, text_embed)
    unified_action_dim = int(cond["unified_action_dim"])
    if unified_action_dim != 128:
        raise ValueError(f"Expected unified action dim 128, got {unified_action_dim}")

    pred_horizon = 64
    x_t = torch.randn(B, pred_horizon, unified_action_dim, device=device, dtype=dtype)

    scheduler = self._noise_scheduler
    scheduler.set_timesteps(self._num_inference_steps)

    with torch.no_grad():
        for t in scheduler.timesteps:
            noise_pred = self._dit(x_t, t, cond)
            x_t = scheduler.step(noise_pred, t, x_t).prev_sample
            x_t = x_t.to(dtype=dtype)

    action_mask = cond["action_mask"].expand(B, pred_horizon, unified_action_dim).to(device=device, dtype=dtype)
    return (x_t * action_mask).float()
```

- [ ] **Step 7.9: Update `_postprocess_actions`**

Replace the method body with:

```python
def _postprocess_actions(self, actions: Tensor) -> Tensor:
    if actions.ndim != 3 or actions.shape[-1] != 128:
        raise ValueError(f"RDT LIBERO postprocess expects (B, 64, 128), got {tuple(actions.shape)}")
    libero_chunk = decode_rdt_libero_action_chunk(actions, self._action_chunk_horizon)
    if not torch.isfinite(libero_chunk).all():
        raise ValueError("Decoded LIBERO action chunk contains non-finite values")
    log.warning(
        "[RDT_LIBERO_ACTION] chunk_shape=%s first=%s pos_range=(%.3f,%.3f) rot_range=(%.3f,%.3f) grip_first=%.3f",
        tuple(libero_chunk.shape),
        libero_chunk[0, 0].tolist(),
        float(libero_chunk[0, :, :3].min().item()),
        float(libero_chunk[0, :, :3].max().item()),
        float(libero_chunk[0, :, 3:6].min().item()),
        float(libero_chunk[0, :, 3:6].max().item()),
        float(libero_chunk[0, 0, 6].item()),
    )
    return libero_chunk
```

- [ ] **Step 7.10: Keep trajectory projection LIBERO-shaped**

Replace `_rdt_sample_to_trajectory_3d` with:

```python
def _rdt_sample_to_trajectory_3d(self, sample: Tensor) -> Tensor:
    libero_actions = decode_rdt_libero_action_chunk(sample, self._action_chunk_horizon)[0]
    if self._adapter is None:
        return torch.zeros(1, self._action_chunk_horizon + 1, 3, device=sample.device, dtype=sample.dtype)
    traj = self._adapter.delta_actions_to_ee_trajectory(libero_actions.to(sample.device))
    return traj.unsqueeze(0)
```

This keeps the hook shape-compatible without optimizing future VLS behavior.

- [ ] **Step 7.11: Run RDT policy tests**

Run:

```bash
pytest tests/test_rdt_steer.py tests/test_rdt_libero_action_converter.py tests/test_rdt_libero_obs_processor.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7.12: Commit policy alignment**

```bash
git add core/rdt_policy_steer.py tests/test_rdt_steer.py
git commit -m "feat: align rdt policy with libero finetuned semantics"
```

---

## Task 8: Update `main.py` And `configs/policy.yaml`

**Files:**
- Modify: `main.py`
- Modify: `configs/policy.yaml`
- Test: `tests/test_rdt_runtime_contract.py`

- [ ] **Step 8.1: Update `main.py` RDT route**

Replace the `elif policy_type == 'rdt':` branch with:

```python
elif policy_type == 'rdt':
    from core.rdt_policy_steer import RDTSteer

    raw_num_steps = type_config.get('num_inference_steps', None)
    num_steps = None if raw_num_steps is None else int(raw_num_steps)
    self.policy = RDTSteer.from_pretrained(
        pretrained_path,
        num_inference_steps=num_steps,
        vision_encoder=type_config.get(
            'vision_encoder',
            '/mnt/data/hf_cache/hub/models--google--siglip-so400m-patch14-384',
        ),
        text_encoder=type_config.get(
            'text_encoder',
            '/mnt/data/hf_cache/hub/models--google--t5-v1_1-xxl',
        ),
        weight_variant=type_config.get('weight_variant', 'ema'),
        control_frequency=int(type_config.get('control_frequency', 20)),
    )
```

Keep `policy.type=rdt`. Do not add a `rdt_libero` route.

- [ ] **Step 8.2: Update `configs/policy.yaml` RDT section**

Replace the current `rdt:` block with:

```yaml
rdt:
  pretrained_path: /mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-60000
  weight_variant: ema
  text_encoder: /mnt/data/hf_cache/hub/models--google--t5-v1_1-xxl
  vision_encoder: /mnt/data/hf_cache/hub/models--google--siglip-so400m-patch14-384
  num_inference_steps: null
  action_chunk_horizon: 8
  control_frequency: 20
  debug_first_step: true
  undo_libero_preprocessor_flip: true
  fail_on_zero_language_embedding: true
  semantics: libero_finetuned
```

- [ ] **Step 8.3: Run runtime contract tests**

Run:

```bash
pytest tests/test_rdt_runtime_contract.py -q
```

Expected: all tests pass.

- [ ] **Step 8.4: Run all RDT unit tests**

Run:

```bash
pytest tests/test_rdt_libero_action_converter.py tests/test_rdt_libero_obs_processor.py tests/test_rdt_steer.py tests/test_rdt_runtime_contract.py -q
```

Expected: all tests pass.

- [ ] **Step 8.5: Commit runtime route/config**

```bash
git add main.py configs/policy.yaml tests/test_rdt_runtime_contract.py
git commit -m "config: route rdt policy to libero finetuned checkpoint"
```

---

## Task 9: One-Sample Dataset And Online Shape Validation

**Files:**
- No source files expected.
- Use existing processors and tests.

- [ ] **Step 9.1: Validate one fine-tuning dataset sample**

Run:

```bash
PYTHONPATH=third_party/rdt python - <<'PY'
import numpy as np
from data.libero_vla_dataset import LiberoVLADataset

dataset = LiberoVLADataset(data_root="/mnt/data/hf_cache/hub", suite="libero_object")
sample = dataset.get_item(index=0, step_id=0)
print("state", sample["state"].shape, sample["state"].dtype)
print("actions", sample["actions"].shape, sample["actions"].dtype)
print("active", np.where(sample["state_indicator"] > 0)[0].tolist())
print("cam_high", sample["cam_high"].shape, sample["cam_high"].dtype, sample["cam_high"].min(), sample["cam_high"].max())
print("cam_right_wrist", sample["cam_right_wrist"].shape, sample["cam_right_wrist"].dtype)
print("instruction", sample["meta"]["instruction"])
PY
```

Expected output includes:

```text
state (1, 128) float32
actions (64, 128) float32
active [10, 30, 31, 32, 33, 34, 35, 36, 37, 38]
cam_high (2, 128, 128, 3) uint8
cam_right_wrist (2, 128, 128, 3) uint8
```

- [ ] **Step 9.2: Validate one online LIBERO observation conversion**

Run:

```bash
python - <<'PY'
import torch
from omegaconf import OmegaConf

from core.env_adapters import create_adapter
from core.rdt_libero_obs_processor import RDTLiberoObsProcessor

cfg = OmegaConf.load("configs/backend/libero.yaml")
adapter = create_adapter("libero", OmegaConf.to_container(cfg.libero, resolve=True))
adapter.reset(seed=0)
obs = adapter.get_policy_observation(sample_num=1)
converted = RDTLiberoObsProcessor(debug_first_step=True).process(obs)
print("images", [None if img is None else img.size for img in converted.images])
print("state", tuple(converted.state_128.shape), converted.state_128.dtype)
print("mask", torch.where(converted.state_mask_128[0] > 0)[0].tolist())
print("task", converted.task)
print("state_active", converted.state_128[0, torch.where(converted.state_mask_128[0] > 0)[0]].tolist())
PY
```

Expected output includes:

```text
images [(256, 256), (256, 256), None, (256, 256), (256, 256), None]
state (1, 128) torch.float32
mask [10, 30, 31, 32, 33, 34, 35, 36, 37, 38]
```

- [ ] **Step 9.3: Commit only if validation required code fixes**

If the commands expose code issues, fix them in the smallest owned file and run:

```bash
pytest tests/test_rdt_libero_action_converter.py tests/test_rdt_libero_obs_processor.py tests/test_rdt_steer.py tests/test_rdt_runtime_contract.py -q
```

Then commit:

```bash
git add core/rdt_libero_action_converter.py core/rdt_libero_obs_processor.py core/rdt_policy_steer.py tests
git commit -m "fix: pass rdt libero shape validation"
```

---

## Task 10: Checkpoint Load Smoke

**Files:**
- No source files expected.

- [ ] **Step 10.1: Run a load-only policy smoke test**

Run:

```bash
python - <<'PY'
from core.rdt_policy_steer import RDTSteer

policy = RDTSteer.from_pretrained(
    "/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-60000",
    num_inference_steps=None,
    weight_variant="ema",
    text_encoder="/mnt/data/hf_cache/hub/models--google--t5-v1_1-xxl",
    vision_encoder="/mnt/data/hf_cache/hub/models--google--siglip-so400m-patch14-384",
    control_frequency=20,
)
policy.to("cuda")
policy.eval()
print("loaded", policy.name, policy._num_inference_steps, policy._action_chunk_horizon)
PY
```

Expected output includes:

```text
loaded rdt_steer 5 8
```

If CUDA memory is insufficient, rerun with `policy.to("cpu")` only to confirm construction and config parsing. Do not treat CPU construction as rollout readiness.

- [ ] **Step 10.2: Commit only if load smoke required fixes**

If code changes were required:

```bash
git add core/rdt_policy_steer.py configs/policy.yaml main.py
git commit -m "fix: load libero finetuned rdt checkpoint"
```

---

## Task 11: Tiny Unguided Rollout Smoke

**Files:**
- No source files expected unless the smoke exposes bugs.

- [ ] **Step 11.1: Run one short unguided episode through `main.py`**

Run:

```bash
python main.py policy.type=rdt main.episode_num=1 main.max_episode_steps=50 main.use_guidance=false main.use_fkd=false main.use_diversity=false
```

Expected:

```text
outputs/libero/<timestamp>/results.txt exists
outputs/libero/<timestamp>/episode_1/ exists
episode_1 contains a saved fail or success rollout video artifact
logs include [RDT_LIBERO_OBS]
logs include [RDT_LIBERO_ACTION]
no shape/device/key errors occur
```

- [ ] **Step 11.2: Inspect the result artifact**

Run:

```bash
ls -R outputs/libero | tail -80
```

Expected: the newest timestamp directory contains `results.txt` and `episode_1`.

- [ ] **Step 11.3: Commit only if tiny rollout required fixes**

If code changes were required:

```bash
git add core/rdt_libero_action_converter.py core/rdt_libero_obs_processor.py core/rdt_policy_steer.py main.py configs/policy.yaml tests
git commit -m "fix: pass rdt libero tiny rollout smoke"
```

---

## Task 12: Ten-Episode Success Gate

**Files:**
- No source files expected unless the gate exposes semantic bugs.

- [ ] **Step 12.1: Run the required 10-episode evaluation**

Run:

```bash
python main.py policy.type=rdt
```

Expected:

```text
10 LIBERO episodes complete
outputs/libero/<timestamp>/results.txt exists
episode directories are written
execution videos or rollout videos are saved
Success count is greater than 0/10
```

- [ ] **Step 12.2: Report result**

Run:

```bash
tail -40 outputs/libero/$(ls -1 outputs/libero | sort | tail -1)/results.txt
```

Expected: `Success count: N/10` where `N > 0`.

- [ ] **Step 12.3: If the run remains 0/10, classify the failure before changing code**

Use the first-step logs and saved video to classify:

```text
mechanical failure: shape/device/key/checkpoint error
observation semantic failure: cameras wrong, image upside down, language empty, state values implausible
action semantic failure: gripper inverted, position/rotation saturated, action dimension wrong
policy failure despite plausible semantics: task difficulty or checkpoint quality
```

Only make another code change when the failure is in the first three categories.

- [ ] **Step 12.4: Final verification**

Run:

```bash
pytest tests/test_rdt_libero_action_converter.py tests/test_rdt_libero_obs_processor.py tests/test_rdt_steer.py tests/test_rdt_runtime_contract.py -q
git status --short
git diff --check
```

Expected:

```text
pytest passes
git diff --check reports no whitespace errors
no modified files under third_party/rdt or third_party/libero
```

---

## Implementation Notes

Keep these choices fixed unless new evidence contradicts them:

```text
Use `policy.type=rdt`, not a new policy route.
Do not create `core/rdt_libero_policy.py`.
Do not modify third-party RDT or LIBERO source.
Do not preserve ManiSkill branches in the active RDT runtime path.
Use EMA weights from checkpoint-60000/ema/model.safetensors.
Use checkpoint scheduler timesteps by default; checkpoint config currently says 5.
Use two online cameras: observation.images.image and observation.images.image2.
Undo the LiberoProcessorStep 180-degree flip before SigLIP preprocessing.
Build first-step image history by repeating the current frame.
Keep the left wrist slot as None so RDT's inference wrapper substitutes the SigLIP background image.
Build state_128 from observation.state = [eef_pos(3), axis_angle(3), gripper_qpos(2)].
Decode action_128 into LIBERO normalized OSC action using the inverse of the fine-tuning transform.
Let LiberoAdapter.step binarize the gripper command.
```

## Success Criteria

The implementation is complete only when:

```text
All RDT LIBERO unit tests pass.
One dataset sample validates against the fine-tuning transform.
One online observation validates against the runtime processor.
The checkpoint loads through `policy.type=rdt` with EMA weights.
A tiny unguided rollout writes outputs and a video artifact.
`python main.py policy.type=rdt` runs 10 LIBERO episodes and reports Success count greater than 0/10.
No third-party source files are modified.
```
