---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: feat/rdt-libero-gt-rollout-reintegration
source_commit: 360a6d052861
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/docs/superpowers/plans/2026-05-23-rdt-libero-finetune-plan.md
summary: RDT LIBERO Fine-Tuning Implementation Plan
duplicate_sources:
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/superpowers/plans/2026-05-23-rdt-libero-finetune-plan.md
---

# RDT LIBERO Fine-Tuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a LIBERO HDF5 backend for RDT fine-tuning, initially verified on `libero_10`, then extended to train one official model over `libero_10`, `libero_object`, `libero_spatial`, and `libero_goal`.

**Architecture:** Keep all implementation inside `third_party/rdt`. Add a dedicated `data/libero_vla_dataset.py` adapter that maps LIBERO EEF observations and OSC actions into RDT's 128D right-arm unified vector, then select it through `RDT_HDF5_BACKEND=libero` from the existing HDF5 training path. Preserve RDT architecture, loss, and `configs/base.yaml`.

**Tech Stack:** Python, NumPy, h5py, SciPy rotation utilities, PyTorch, pytest, RDT `VLAConsumerDataset`, RDT `compute_dataset_stat_hdf5.py`, Accelerate/DeepSpeed fine-tuning scripts.

---

## Scope And Boundaries

Only modify files under:

```text
/home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-object-ckpt/third_party/rdt
```

Do not modify `core/`, deployment code, LIBERO benchmark rollout code, RDT loss code, `models/rdt_runner.py`, or checkpoint-affecting model architecture/configuration.

Implementation evidence should come from:

```text
third_party/rdt/README.md
third_party/rdt/data/hdf5_vla_dataset.py
third_party/rdt/data/hdf5_maniskill_dataset.py
third_party/rdt/data/compute_dataset_stat_hdf5.py
third_party/rdt/train/dataset.py
third_party/rdt/configs/state_vec.py
third_party/rdt/docs/test_6drot.py
third_party/libero/scripts/create_dataset.py
third_party/libero/libero/configs/data/default.yaml
third_party/libero/libero/libero/envs/env_wrapper.py
third_party/libero/libero/libero/envs/bddl_base_domain.py
```

Use this approved design file as the specification:

```text
docs/superpowers/specs/2026-05-20-rdt-libero-finetune-design.md
```

## File Structure

Create:

```text
third_party/rdt/data/libero_vla_dataset.py
third_party/rdt/tests/test_libero_vla_dataset.py
third_party/rdt/scripts/smoke_test_libero_dataset.py
third_party/rdt/finetune_libero.sh
```

Modify:

```text
third_party/rdt/data/hdf5_vla_dataset.py
third_party/rdt/configs/finetune_datasets.json
third_party/rdt/configs/finetune_sample_weights.json
third_party/rdt/configs/dataset_control_freq.json
```

Generated during verification:

```text
third_party/rdt/configs/dataset_stat.json
third_party/rdt/checkpoints/rdt-libero-smoke/
```

## Constants

Use these names and values in implementation and tests:

```python
LIBERO_RDT_INDICES = [30, 31, 32, 33, 34, 35, 36, 37, 38, 10]
LIBERO_SUITES = ("libero_10", "libero_object", "libero_spatial", "libero_goal")
DEFAULT_LIBERO_DATA_ROOT = "/mnt/data/hf_cache/hub"
DEFAULT_POS_SCALE = [0.05, 0.05, 0.05]
DEFAULT_ROT_SCALE = [0.5, 0.5, 0.5]
```

Mapping contract:

```text
state[30:33] = obs/ee_pos
state[33:39] = rotvec_to_ortho6d(obs/ee_ori)
state[10]    = clip((gripper_states[:, 0] - gripper_states[:, 1]) / 0.08, 0, 1)

actions[30:33] = scale_controller(raw_action[:, 0:3])
actions[33:39] = rotvec_to_ortho6d(scale_controller(raw_action[:, 3:6]))
actions[10]    = (1 - raw_action[:, 6]) / 2
```

---

### Task 1: Add LIBERO Loader Tests

**Files:**
- Create: `third_party/rdt/tests/test_libero_vla_dataset.py`

- [ ] **Step 1: Create the test file**

Create `third_party/rdt/tests/test_libero_vla_dataset.py`:

```python
import json
import os
import sys
from pathlib import Path

import h5py
import numpy as np
import pytest


RDT_ROOT = Path(__file__).resolve().parents[1]
if str(RDT_ROOT) not in sys.path:
    sys.path.insert(0, str(RDT_ROOT))


def _write_synthetic_libero_file(path, length=6, action_gripper_values=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if action_gripper_values is None:
        action_gripper_values = np.array([-1.0, 1.0, -1.0, 1.0, -1.0, 1.0], dtype=np.float64)

    with h5py.File(path, "w") as f:
        data = f.create_group("data")
        data.attrs["problem_info"] = json.dumps({
            "problem_name": "synthetic_problem",
            "domain_name": "robosuite",
            "language_instruction": "pick up the synthetic object",
        })
        data.attrs["env_args"] = json.dumps({
            "type": 1,
            "env_name": "SyntheticLiberoEnv",
            "problem_name": "synthetic_problem",
            "env_kwargs": {
                "robots": ["Panda"],
                "control_freq": 20,
                "camera_names": ["robot0_eye_in_hand", "agentview"],
                "controller_configs": {
                    "type": "OSC_POSE",
                    "input_max": 1,
                    "input_min": -1,
                    "output_max": [0.05, 0.05, 0.05, 0.5, 0.5, 0.5],
                    "output_min": [-0.05, -0.05, -0.05, -0.5, -0.5, -0.5],
                    "control_delta": True,
                },
            },
        })
        data.attrs["num_demos"] = np.int64(1)
        data.attrs["total"] = np.int64(length)

        demo = data.create_group("demo_0")
        demo.attrs["num_samples"] = np.int64(length)
        obs = demo.create_group("obs")

        actions = np.zeros((length, 7), dtype=np.float64)
        actions[:, 0:6] = np.array([0.5, -0.25, 0.25, 0.1, -0.2, 0.3], dtype=np.float64)
        actions[:, 6] = action_gripper_values[:length]

        ee_pos = np.stack([
            np.linspace(0.1, 0.2, length),
            np.linspace(-0.2, -0.1, length),
            np.linspace(0.8, 0.9, length),
        ], axis=1).astype(np.float64)
        ee_ori = np.zeros((length, 3), dtype=np.float64)
        gripper_states = np.stack([
            np.linspace(0.04, 0.00, length),
            -np.linspace(0.04, 0.00, length),
        ], axis=1).astype(np.float64)
        joint_states = np.tile(np.arange(7, dtype=np.float64), (length, 1))

        agentview = np.zeros((length, 128, 128, 3), dtype=np.uint8)
        agentview[..., 0] = 12
        agentview[..., 1] = 34
        agentview[..., 2] = 56
        wrist = np.zeros((length, 128, 128, 3), dtype=np.uint8)
        wrist[..., 0] = 90
        wrist[..., 1] = 80
        wrist[..., 2] = 70

        obs.create_dataset("agentview_rgb", data=agentview)
        obs.create_dataset("eye_in_hand_rgb", data=wrist)
        obs.create_dataset("ee_pos", data=ee_pos)
        obs.create_dataset("ee_ori", data=ee_ori)
        obs.create_dataset("ee_states", data=np.concatenate([ee_pos, ee_ori], axis=1))
        obs.create_dataset("gripper_states", data=gripper_states)
        obs.create_dataset("joint_states", data=joint_states)
        demo.create_dataset("actions", data=actions)
        demo.create_dataset("states", data=np.zeros((length, 47), dtype=np.float64))
        demo.create_dataset(
            "robot_states",
            data=np.concatenate([gripper_states, ee_pos, np.tile([[1, 0, 0, 0]], (length, 1))], axis=1),
        )
        rewards = np.zeros(length, dtype=np.uint8)
        rewards[-1] = 1
        dones = np.zeros(length, dtype=np.uint8)
        dones[-1] = 1
        demo.create_dataset("rewards", data=rewards)
        demo.create_dataset("dones", data=dones)


def _setup_env(tmp_path, monkeypatch):
    data_root = tmp_path / "hf_cache"
    _write_synthetic_libero_file(data_root / "libero_10" / "SYNTHETIC_task_demo.hdf5")
    monkeypatch.chdir(RDT_ROOT)
    monkeypatch.setenv("RDT_LIBERO_DATA_ROOT", str(data_root))
    monkeypatch.setenv("RDT_LIBERO_SUITES", "libero_10")
    return data_root


def test_rotation_helpers_round_trip_small_libero_rotvecs():
    from data.libero_vla_dataset import ortho6d_to_rotvec, rotvec_to_ortho6d

    rotvec = np.array([
        [0.0, 0.0, 0.0],
        [0.05, -0.10, 0.15],
        [-0.118214, 0.184821, -0.183750],
    ], dtype=np.float32)
    recovered = ortho6d_to_rotvec(rotvec_to_ortho6d(rotvec))
    assert np.allclose(recovered, rotvec, atol=1e-5)


def test_gripper_action_mapping_open_high():
    from data.libero_vla_dataset import map_libero_gripper_action

    raw = np.array([-1.0, 1.0], dtype=np.float32)
    mapped = map_libero_gripper_action(raw)
    assert mapped.tolist() == [1.0, 0.0]


def test_dataset_indexes_demo_records(tmp_path, monkeypatch):
    _setup_env(tmp_path, monkeypatch)

    from data.libero_vla_dataset import LiberoVLADataset

    dataset = LiberoVLADataset()
    assert len(dataset) == 1
    record = dataset.records[0]
    assert record.suite == "libero_10"
    assert record.demo_key == "demo_0"
    assert record.num_steps == 6
    assert record.instruction == "pick up the synthetic object"
    assert record.control_freq == 20
    assert dataset.get_dataset_name() == "libero_10"


def test_state_and_action_mapping_uses_rdt_6d_slots(tmp_path, monkeypatch):
    _setup_env(tmp_path, monkeypatch)

    from data.libero_vla_dataset import (
        LIBERO_RDT_INDICES,
        LiberoVLADataset,
        rotvec_to_ortho6d,
    )

    dataset = LiberoVLADataset()
    record = dataset.records[0]
    with h5py.File(record.file_path, "r") as f:
        demo = f["data/demo_0"]
        states = dataset.build_state_sequence(demo)
        actions = dataset.build_action_sequence(demo, record.controller_config)
        indicator = dataset.build_state_indicator()

    assert states.shape == (6, 128)
    assert actions.shape == (6, 128)
    assert np.where(indicator > 0)[0].tolist() == sorted(LIBERO_RDT_INDICES)
    assert np.allclose(states[0, 30:33], np.array([0.1, -0.2, 0.8], dtype=np.float32))
    assert np.allclose(states[0, 33:39], np.array([1, 0, 0, 0, 1, 0], dtype=np.float32))
    assert states[0, 10] == pytest.approx(1.0)
    assert np.allclose(actions[0, 30:33], np.array([0.025, -0.0125, 0.0125], dtype=np.float32))
    expected_rot6d = rotvec_to_ortho6d(np.array([[0.05, -0.10, 0.15]], dtype=np.float32))[0]
    assert np.allclose(actions[0, 33:39], expected_rot6d, atol=1e-6)
    assert actions[0, 10] == pytest.approx(1.0)
    assert actions[1, 10] == pytest.approx(0.0)


def test_get_item_returns_rdt_hdf5_contract(tmp_path, monkeypatch):
    _setup_env(tmp_path, monkeypatch)

    from data.libero_vla_dataset import LiberoVLADataset

    dataset = LiberoVLADataset()
    dataset.CHUNK_SIZE = 4
    dataset.IMG_HISTORY_SIZE = 2
    sample = dataset.get_item(index=0, step_id=0)

    assert sample["meta"]["dataset_name"] == "libero_10"
    assert sample["meta"]["instruction"] == "pick up the synthetic object"
    assert sample["meta"]["step_id"] == 0
    assert sample["state"].shape == (1, 128)
    assert sample["actions"].shape == (4, 128)
    assert sample["state_indicator"].shape == (128,)
    assert sample["state_std"].shape == (128,)
    assert sample["state_mean"].shape == (128,)
    assert sample["state_norm"].shape == (128,)
    assert sample["cam_high"].shape == (2, 128, 128, 3)
    assert sample["cam_right_wrist"].shape == (2, 128, 128, 3)
    assert sample["cam_left_wrist"].shape == (2, 0, 0, 0)
    assert sample["cam_high_mask"].tolist() == [False, True]
    assert sample["cam_right_wrist_mask"].tolist() == [False, True]
    assert sample["cam_left_wrist_mask"].tolist() == [False, False]


def test_state_only_returns_full_mapped_trajectory(tmp_path, monkeypatch):
    _setup_env(tmp_path, monkeypatch)

    from data.libero_vla_dataset import LiberoVLADataset

    dataset = LiberoVLADataset()
    episode = dataset.get_item(index=0, state_only=True)
    assert episode["dataset_name"] == "libero_10"
    assert episode["state"].shape == (6, 128)
    assert episode["action"].shape == (6, 128)


def test_hdf5_backend_switch_selects_libero(tmp_path, monkeypatch):
    _setup_env(tmp_path, monkeypatch)
    monkeypatch.setenv("RDT_HDF5_BACKEND", "libero")

    import importlib
    import data.hdf5_vla_dataset as hdf5_vla_dataset

    hdf5_vla_dataset = importlib.reload(hdf5_vla_dataset)
    dataset = hdf5_vla_dataset.HDF5VLADataset()
    assert dataset.get_dataset_name() == "libero_10"
```

- [ ] **Step 2: Run tests and verify the expected import failure**

Run:

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-object-ckpt/third_party/rdt
python -m pytest tests/test_libero_vla_dataset.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'data.libero_vla_dataset'
```

- [ ] **Step 3: Commit**

Do not commit in this task. Commit after Task 2 turns these tests green.

---

### Task 2: Implement The LIBERO Dataset Adapter

**Files:**
- Create: `third_party/rdt/data/libero_vla_dataset.py`
- Modify: `third_party/rdt/tests/test_libero_vla_dataset.py`

- [ ] **Step 1: Create the adapter**

Create `third_party/rdt/data/libero_vla_dataset.py`:

```python
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import h5py
import numpy as np
import yaml
from scipy.spatial.transform import Rotation as R

from configs.state_vec import STATE_VEC_IDX_MAPPING


LIBERO_SUITES = ("libero_10", "libero_object", "libero_spatial", "libero_goal")
DEFAULT_LIBERO_DATA_ROOT = "/mnt/data/hf_cache/hub"
LIBERO_RDT_INDICES = [
    STATE_VEC_IDX_MAPPING["eef_pos_x"],
    STATE_VEC_IDX_MAPPING["eef_pos_y"],
    STATE_VEC_IDX_MAPPING["eef_pos_z"],
    STATE_VEC_IDX_MAPPING["eef_angle_0"],
    STATE_VEC_IDX_MAPPING["eef_angle_1"],
    STATE_VEC_IDX_MAPPING["eef_angle_2"],
    STATE_VEC_IDX_MAPPING["eef_angle_3"],
    STATE_VEC_IDX_MAPPING["eef_angle_4"],
    STATE_VEC_IDX_MAPPING["eef_angle_5"],
    STATE_VEC_IDX_MAPPING["right_gripper_open"],
]


@dataclass(frozen=True)
class LiberoEpisodeRecord:
    file_path: str
    suite: str
    task_name: str
    demo_key: str
    num_steps: int
    instruction: str
    control_freq: int
    controller_config: dict


def _json_attr(group, key):
    value = group.attrs[key]
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    return json.loads(value)


def _task_name_from_path(path):
    stem = Path(path).stem
    return stem[:-5] if stem.endswith("_demo") else stem


def _suite_from_env():
    raw = os[redacted env file]iron.get("RDT_LIBERO_SUITES", "libero_10")
    suites = tuple(s.strip() for s in raw.split(",") if s.strip())
    if len(suites) != 1:
        raise ValueError(
            "RDT_LIBERO_SUITES must contain exactly one suite for this fine-tuning backend. "
            "Run separate stats/training jobs for libero_10 and libero_object."
        )
    if suites[0] not in LIBERO_SUITES:
        raise ValueError("Unknown LIBERO suite: {}".format(suites[0]))
    return suites[0]


def rotvec_to_ortho6d(rotvec):
    rotvec = np.asarray(rotvec, dtype=np.float32)
    original_shape = rotvec.shape[:-1]
    matrix = R.from_rotvec(rotvec.reshape(-1, 3)).as_matrix().astype(np.float32)
    ortho6d = matrix[:, :, :2].transpose(0, 2, 1).reshape(-1, 6)
    return ortho6d.reshape(original_shape + (6,))


def _normalize_vector(v):
    norm = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(norm, 1e-8)


def ortho6d_to_rotmat(ortho6d):
    ortho6d = np.asarray(ortho6d, dtype=np.float32)
    original_shape = ortho6d.shape[:-1]
    flat = ortho6d.reshape(-1, 6)
    x_raw = flat[:, 0:3]
    y_raw = flat[:, 3:6]
    x = _normalize_vector(x_raw)
    z = _normalize_vector(np.cross(x, y_raw))
    y = np.cross(z, x)
    matrix = np.stack([x, y, z], axis=-1)
    return matrix.reshape(original_shape + (3, 3))


def ortho6d_to_rotvec(ortho6d):
    matrix = ortho6d_to_rotmat(ortho6d)
    original_shape = matrix.shape[:-2]
    rotvec = R.from_matrix(matrix.reshape(-1, 3, 3)).as_rotvec().astype(np.float32)
    return rotvec.reshape(original_shape + (3,))


def map_libero_gripper_action(raw_gripper):
    raw_gripper = np.asarray(raw_gripper, dtype=np.float32)
    return np.clip((1.0 - raw_gripper) / 2.0, 0.0, 1.0).astype(np.float32)


def map_libero_gripper_state(gripper_states):
    gripper_states = np.asarray(gripper_states, dtype=np.float32)
    width = gripper_states[..., 0] - gripper_states[..., 1]
    return np.clip(width / 0.08, 0.0, 1.0).astype(np.float32)


def _controller_scale(raw_action_6d, controller_config):
    raw_action_6d = np.asarray(raw_action_6d, dtype=np.float32)
    if controller_config.get("type") != "OSC_POSE":
        raise ValueError("Expected LIBERO OSC_POSE controller, got {}".format(controller_config.get("type")))
    if not bool(controller_config.get("control_delta")):
        raise ValueError("Expected LIBERO OSC_POSE control_delta=True")

    input_min = np.asarray(controller_config["input_min"], dtype=np.float32)
    input_max = np.asarray(controller_config["input_max"], dtype=np.float32)
    output_min = np.asarray(controller_config["output_min"], dtype=np.float32)
    output_max = np.asarray(controller_config["output_max"], dtype=np.float32)

    if input_min.ndim == 0:
        input_min = np.full(6, float(input_min), dtype=np.float32)
    if input_max.ndim == 0:
        input_max = np.full(6, float(input_max), dtype=np.float32)
    if output_min.shape != (6,) or output_max.shape != (6,):
        raise ValueError("Expected six OSC_POSE output limits, got {} and {}".format(output_min, output_max))

    clipped = np.clip(raw_action_6d, input_min, input_max)
    action_scale = np.abs(output_max - output_min) / np.abs(input_max - input_min)
    output_center = (output_max + output_min) / 2.0
    input_center = (input_max + input_min) / 2.0
    return (clipped - input_center) * action_scale + output_center


class LiberoVLADataset:
    def __init__(self, data_root=None, suite=None):
        self.data_root = data_root or os[redacted env file]iron.get("RDT_LIBERO_DATA_ROOT", DEFAULT_LIBERO_DATA_ROOT)
        self.suite = suite or _suite_from_env()
        with open("configs/base.yaml", "r") as f:
            config = yaml.safe_load(f)
        self.CHUNK_SIZE = int(config["common"]["action_chunk_size"])
        self.IMG_HISTORY_SIZE = int(config["common"]["img_history_size"])
        self.STATE_DIM = int(config["common"]["state_dim"])
        self.records = self._build_index()
        lengths = np.asarray([record.num_steps for record in self.records], dtype=np.float64)
        self.episode_sample_weights = lengths / lengths.sum()

    def _hdf5_files(self):
        suite_dir = Path(self.data_root) / self.suite
        files = sorted(suite_dir.glob("*.hdf5"))
        if not files:
            raise FileNotFoundError("No LIBERO HDF5 files found in {}".format(suite_dir))
        return files

    def _build_index(self):
        records = []
        for file_path in self._hdf5_files():
            with h5py.File(file_path, "r") as f:
                data = f["data"]
                problem_info = _json_attr(data, "problem_info")
                env_args = _json_attr(data, "env_args")
                env_kwargs = env_args["env_kwargs"]
                controller_config = env_kwargs["controller_configs"]
                demo_keys = sorted(
                    [key for key in data.keys() if key.startswith("demo_")],
                    key=lambda key: int(key.split("_")[-1]),
                )
                for demo_key in demo_keys:
                    num_steps = int(data[demo_key]["actions"].shape[0])
                    if num_steps < 1:
                        continue
                    records.append(
                        LiberoEpisodeRecord(
                            file_path=str(file_path),
                            suite=self.suite,
                            task_name=_task_name_from_path(file_path),
                            demo_key=demo_key,
                            num_steps=num_steps,
                            instruction=problem_info["language_instruction"],
                            control_freq=int(env_kwargs.get("control_freq", 20)),
                            controller_config=controller_config,
                        )
                    )
        if not records:
            raise RuntimeError("No LIBERO demos indexed from {}".format(Path(self.data_root) / self.suite))
        return records

    def __len__(self):
        return len(self.records)

    def get_dataset_name(self):
        return self.suite

    def build_state_indicator(self):
        indicator = np.zeros((self.STATE_DIM,), dtype=np.float32)
        indicator[LIBERO_RDT_INDICES] = 1.0
        return indicator

    def build_state_sequence(self, demo):
        if "obs/ee_pos" in demo:
            ee_pos = demo["obs/ee_pos"][:].astype(np.float32)
        else:
            ee_pos = demo["obs/ee_states"][:, :3].astype(np.float32)
        if "obs/ee_ori" in demo:
            ee_ori = demo["obs/ee_ori"][:].astype(np.float32)
        else:
            ee_ori = demo["obs/ee_states"][:, 3:6].astype(np.float32)
        gripper_open = map_libero_gripper_state(demo["obs/gripper_states"][:])

        state = np.zeros((ee_pos.shape[0], self.STATE_DIM), dtype=np.float32)
        state[:, 30:33] = ee_pos
        state[:, 33:39] = rotvec_to_ortho6d(ee_ori)
        state[:, 10] = gripper_open
        return state

    def build_action_sequence(self, demo, controller_config):
        raw_actions = demo["actions"][:].astype(np.float32)
        scaled_osc = _controller_scale(raw_actions[:, :6], controller_config)

        action = np.zeros((raw_actions.shape[0], self.STATE_DIM), dtype=np.float32)
        action[:, 30:33] = scaled_osc[:, :3]
        action[:, 33:39] = rotvec_to_ortho6d(scaled_osc[:, 3:6])
        action[:, 10] = map_libero_gripper_action(raw_actions[:, 6])
        return action

    def _image_history(self, demo, key, step_id):
        images = demo["obs/{}".format(key)]
        start = max(0, step_id - self.IMG_HISTORY_SIZE + 1)
        history = images[start:step_id + 1].astype(np.uint8)
        valid_len = history.shape[0]
        if valid_len < self.IMG_HISTORY_SIZE:
            pad = np.repeat(history[:1], self.IMG_HISTORY_SIZE - valid_len, axis=0)
            history = np.concatenate([pad, history], axis=0)
        mask = np.array([False] * (self.IMG_HISTORY_SIZE - valid_len) + [True] * valid_len, dtype=bool)
        return history, mask

    def _state_stats(self, states):
        return (
            np.std(states, axis=0).astype(np.float32),
            np.mean(states, axis=0).astype(np.float32),
            np.sqrt(np.mean(states ** 2, axis=0)).astype(np.float32),
        )

    def _padded_action_chunk(self, actions, step_id):
        chunk = actions[step_id:step_id + self.CHUNK_SIZE]
        if chunk.shape[0] == 0:
            raise ValueError("Cannot build an empty action chunk")
        if chunk.shape[0] < self.CHUNK_SIZE:
            pad = np.repeat(chunk[-1:], self.CHUNK_SIZE - chunk.shape[0], axis=0)
            chunk = np.concatenate([chunk, pad], axis=0)
        return chunk.astype(np.float32)

    def get_item(self, index=None, state_only=False, step_id=None):
        if index is None:
            index = int(np.random.choice(np.arange(len(self.records)), p=self.episode_sample_weights))
        record = self.records[index]
        with h5py.File(record.file_path, "r") as f:
            demo = f["data/{}".format(record.demo_key)]
            states = self.build_state_sequence(demo)
            actions = self.build_action_sequence(demo, record.controller_config)
            if state_only:
                return {
                    "dataset_name": record.suite,
                    "state": states,
                    "action": actions,
                }
            if step_id is None:
                step_id = int(np.random.randint(0, record.num_steps))

            state_std, state_mean, state_norm = self._state_stats(states)
            cam_high, cam_high_mask = self._image_history(demo, "agentview_rgb", step_id)
            cam_right_wrist, cam_right_wrist_mask = self._image_history(demo, "eye_in_hand_rgb", step_id)
            cam_left_wrist = np.zeros((self.IMG_HISTORY_SIZE, 0, 0, 0), dtype=np.uint8)
            cam_left_wrist_mask = np.zeros((self.IMG_HISTORY_SIZE,), dtype=bool)

            return {
                "meta": {
                    "dataset_name": record.suite,
                    "#steps": record.num_steps,
                    "step_id": step_id,
                    "instruction": record.instruction,
                },
                "state": states[step_id:step_id + 1].astype(np.float32),
                "state_std": state_std,
                "state_mean": state_mean,
                "state_norm": state_norm,
                "actions": self._padded_action_chunk(actions, step_id),
                "state_indicator": self.build_state_indicator(),
                "cam_high": cam_high,
                "cam_high_mask": cam_high_mask,
                "cam_left_wrist": cam_left_wrist,
                "cam_left_wrist_mask": cam_left_wrist_mask,
                "cam_right_wrist": cam_right_wrist,
                "cam_right_wrist_mask": cam_right_wrist_mask,
            }
```

- [ ] **Step 2: Run tests and observe backend-switch failure**

Run:

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-object-ckpt/third_party/rdt
python -m pytest tests/test_libero_vla_dataset.py -q
```

Expected:

```text
1 failed, 6 passed
```

The expected failing test is:

```text
test_hdf5_backend_switch_selects_libero
```

- [ ] **Step 3: Commit the adapter and passing direct-loader tests**

Run:

```bash
git add data/libero_vla_dataset.py tests/test_libero_vla_dataset.py
git commit -m "feat: add LIBERO VLA HDF5 adapter"
```

---

### Task 3: Wire The Existing HDF5 Entry Point

**Files:**
- Modify: `third_party/rdt/data/hdf5_vla_dataset.py`
- Modify: `third_party/rdt/tests/test_libero_vla_dataset.py`

- [ ] **Step 1: Add backend rebinding to the existing entry point**

In `third_party/rdt/data/hdf5_vla_dataset.py`, insert this block immediately before the existing `if __name__ == "__main__":` block:

```python
if os[redacted env file]iron.get("RDT_HDF5_BACKEND", "").lower() == "libero":
    from data.libero_vla_dataset import LiberoVLADataset as HDF5VLADataset
```

- [ ] **Step 2: Run the backend-switch test**

Run:

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-object-ckpt/third_party/rdt
python -m pytest tests/test_libero_vla_dataset.py::test_hdf5_backend_switch_selects_libero -q
```

Expected:

```text
1 passed
```

- [ ] **Step 3: Run all loader tests**

Run:

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-object-ckpt/third_party/rdt
python -m pytest tests/test_libero_vla_dataset.py -q
```

Expected:

```text
7 passed
```

- [ ] **Step 4: Commit**

Run:

```bash
git add data/hdf5_vla_dataset.py tests/test_libero_vla_dataset.py
git commit -m "feat: select LIBERO backend for HDF5 fine-tuning"
```

---

### Task 4: Register LIBERO Fine-Tuning Configs

**Files:**
- Modify: `third_party/rdt/configs/finetune_datasets.json`
- Modify: `third_party/rdt/configs/finetune_sample_weights.json`
- Modify: `third_party/rdt/configs/dataset_control_freq.json`

- [ ] **Step 1: Replace the fine-tune dataset list**

Replace `third_party/rdt/configs/finetune_datasets.json` with:

```json
[
    "libero_10",
    "libero_object"
]
```

- [ ] **Step 2: Replace the fine-tune sample weights**

Replace `third_party/rdt/configs/finetune_sample_weights.json` with:

```json
{
    "libero_10": 100,
    "libero_object": 100
}
```

- [ ] **Step 3: Add LIBERO control frequencies**

In `third_party/rdt/configs/dataset_control_freq.json`, change the final entries from:

```json
    "calvin": 30,
    "bridgev2": 5
}
```

to:

```json
    "calvin": 30,
    "bridgev2": 5,
    "libero_10": 20,
    "libero_object": 20
}
```

- [ ] **Step 4: Validate JSON**

Run:

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-object-ckpt/third_party/rdt
python -m json.tool configs/finetune_datasets.json >/tmp/rdt_finetune_datasets.json
python -m json.tool configs/finetune_sample_weights.json >/tmp/rdt_finetune_sample_weights.json
python -m json.tool configs/dataset_control_freq.json >/tmp/rdt_dataset_control_freq.json
```

Expected:

```text
No output and exit code 0 for all three commands.
```

- [ ] **Step 5: Commit**

Run:

```bash
git add configs/finetune_datasets.json configs/finetune_sample_weights.json configs/dataset_control_freq.json
git commit -m "config: register LIBERO fine-tuning datasets"
```

---

### Task 5: Add Dataset Smoke-Test Script

**Files:**
- Create: `third_party/rdt/scripts/smoke_test_libero_dataset.py`

- [ ] **Step 1: Create the smoke script**

Create `third_party/rdt/scripts/smoke_test_libero_dataset.py`:

```python
import argparse
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch
import yaml


RDT_ROOT = Path(__file__).resolve().parents[1]
if str(RDT_ROOT) not in sys.path:
    sys.path.insert(0, str(RDT_ROOT))


class SmokeTokenizer:
    pad_token_id = 0

    def __call__(self, text, return_tensors="pt", padding="longest", truncation=False):
        token_ids = [1] + [min(1000, ord(ch)) for ch in text[:64]]
        return SimpleNamespace(input_ids=torch.tensor([token_ids], dtype=torch.long))


class SmokeImageProcessor:
    image_mean = [0.5, 0.5, 0.5]
    size = {"height": 384, "width": 384}

    def preprocess(self, image, return_tensors="pt"):
        image = image.resize((384, 384))
        array = np.asarray(image).astype(np.float32) / 255.0
        tensor = torch.from_numpy(array).permute(2, 0, 1)
        return {"pixel_values": tensor.unsqueeze(0)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default=os[redacted env file]iron.get("RDT_LIBERO_SUITES", "libero_10"))
    parser.add_argument("--data-root", default=os[redacted env file]iron.get("RDT_LIBERO_DATA_ROOT", "/mnt/data/hf_cache/hub"))
    parser.add_argument("--index", type=int, default=0)
    parser.add_argument("--step-id", type=int, default=0)
    parser.add_argument("--consumer", action="store_true")
    args = parser.parse_args()

    os[redacted env file]iron["RDT_HDF5_BACKEND"] = "libero"
    os[redacted env file]iron["RDT_LIBERO_SUITES"] = args.suite
    os[redacted env file]iron["RDT_LIBERO_DATA_ROOT"] = args.data_root

    from data.hdf5_vla_dataset import HDF5VLADataset

    dataset = HDF5VLADataset()
    sample = dataset.get_item(index=args.index, step_id=args.step_id)
    print("dataset_name:", sample["meta"]["dataset_name"])
    print("instruction:", sample["meta"]["instruction"])
    print("state:", sample["state"].shape, sample["state"].dtype)
    print("actions:", sample["actions"].shape, sample["actions"].dtype)
    print("active_indices:", np.where(sample["state_indicator"] > 0)[0].tolist())
    print("cam_high:", sample["cam_high"].shape, sample["cam_high_mask"].tolist())
    print("cam_right_wrist:", sample["cam_right_wrist"].shape, sample["cam_right_wrist_mask"].tolist())
    print("cam_left_wrist:", sample["cam_left_wrist"].shape, sample["cam_left_wrist_mask"].tolist())
    assert sample["state"].shape == (1, 128)
    assert sample["actions"].shape == (64, 128)
    assert np.where(sample["state_indicator"] > 0)[0].tolist() == [10, 30, 31, 32, 33, 34, 35, 36, 37, 38]
    assert sample["cam_high"].shape[0] == 2
    assert sample["cam_right_wrist"].shape[0] == 2
    assert sample["cam_left_wrist"].shape == (2, 0, 0, 0)

    if args.consumer:
        with open("configs/base.yaml", "r") as f:
            config = yaml.safe_load(f)
        from train.dataset import DataCollatorForVLAConsumerDataset, VLAConsumerDataset

        consumer = VLAConsumerDataset(
            config=config["dataset"],
            tokenizer=SmokeTokenizer(),
            image_processor=SmokeImageProcessor(),
            num_cameras=config["common"]["num_cameras"],
            img_history_size=config["common"]["img_history_size"],
            image_size=None,
            auto_adjust_image_brightness=False,
            image_aug=False,
            dataset_type="finetune",
            cond_mask_prob=0.0,
            cam_ext_mask_prob=-1.0,
            state_noise_snr=None,
            use_hdf5=True,
            use_precomp_lang_embed=False,
        )
        batch = DataCollatorForVLAConsumerDataset(SmokeTokenizer())([consumer[0], consumer[1]])
        print("consumer.states:", tuple(batch["states"].shape))
        print("consumer.actions:", tuple(batch["actions"].shape))
        print("consumer.images:", tuple(batch["images"].shape))
        assert tuple(batch["states"].shape) == (2, 1, 128)
        assert tuple(batch["actions"].shape) == (2, 64, 128)
        assert tuple(batch["images"].shape[:2]) == (2, 6)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the loader-only smoke test on `libero_10`**

Run:

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-object-ckpt/third_party/rdt
python scripts/smoke_test_libero_dataset.py --suite libero_10 --data-root /mnt/data/hf_cache/hub --index 0 --step-id 0
```

Expected output includes:

```text
dataset_name: libero_10
state: (1, 128) float32
actions: (64, 128) float32
active_indices: [10, 30, 31, 32, 33, 34, 35, 36, 37, 38]
cam_left_wrist: (2, 0, 0, 0) [False, False]
```

- [ ] **Step 3: Commit**

Run:

```bash
git add scripts/smoke_test_libero_dataset.py
git commit -m "test: add LIBERO dataset smoke script"
```

---

### Task 6: Compute Dataset Statistics Through RDT's HDF5 Path

**Files:**
- Generated: `third_party/rdt/configs/dataset_stat.json`

- [ ] **Step 1: Compute `libero_10` stats**

Run:

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-object-ckpt/third_party/rdt
RDT_HDF5_BACKEND=libero \
RDT_LIBERO_DATA_ROOT=/mnt/data/hf_cache/hub \
RDT_LIBERO_SUITES=libero_10 \
python -m data.compute_dataset_stat_hdf5 --save_path configs/dataset_stat.json
```

Expected output includes:

```text
Processing libero_10 dataset
All datasets have been processed.
```

- [ ] **Step 2: Verify stats contain active LIBERO slots**

Run:

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-object-ckpt/third_party/rdt
python - <<'PY'
import json
with open("configs/dataset_stat.json", "r") as f:
    stats = json.load(f)
entry = stats["libero_10"]
assert len(entry["state_mean"]) == 128
assert len(entry["state_std"]) == 128
active = [10, 30, 31, 32, 33, 34, 35, 36, 37, 38]
print("active_mean", [round(entry["state_mean"][i], 6) for i in active])
print("active_std", [round(entry["state_std"][i], 6) for i in active])
PY
```

Expected output includes two printed lists named:

```text
active_mean
active_std
```

- [ ] **Step 3: Run the consumer smoke test after stats exist**

Run:

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-object-ckpt/third_party/rdt
python scripts/smoke_test_libero_dataset.py --suite libero_10 --data-root /mnt/data/hf_cache/hub --consumer
```

Expected output includes:

```text
consumer.states: (2, 1, 128)
consumer.actions: (2, 64, 128)
consumer.images: (2, 6
```

- [ ] **Step 4: Commit stats**

Run:

```bash
git add configs/dataset_stat.json
git commit -m "data: compute LIBERO-10 RDT dataset stats"
```

---

### Task 7: Add LIBERO Fine-Tuning Script

**Files:**
- Create: `third_party/rdt/finetune_libero.sh`

- [ ] **Step 1: Create the script**

Create `third_party/rdt/finetune_libero.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

export NCCL_IB_DISABLE="${NCCL_IB_DISABLE:-0}"
export NCCL_DEBUG="${NCCL_DEBUG:-INFO}"
export NCCL_NVLS_ENABLE="${NCCL_NVLS_ENABLE:-0}"

export RDT_HDF5_BACKEND="${RDT_HDF5_BACKEND:-libero}"
export RDT_LIBERO_DATA_ROOT="${RDT_LIBERO_DATA_ROOT:-/mnt/data/hf_cache/hub}"
export RDT_LIBERO_SUITES="${RDT_LIBERO_SUITES:-libero_10}"

export TEXT_ENCODER_NAME="${TEXT_ENCODER_NAME:-/mnt/data/hf_cache/hub/models--google--t5-v1_1-xxl}"
export VISION_ENCODER_NAME="${VISION_ENCODER_NAME:-/mnt/data/hf_cache/hub/models--google--siglip-so400m-patch14-384}"
export RDT_MODEL_NAME="${RDT_MODEL_NAME:-/mnt/data/hf_cache/hub/models--robotics-diffusion-transformer/rdt-1b}"
export OUTPUT_DIR="${OUTPUT_DIR:-./checkpoints/rdt-libero-${RDT_LIBERO_SUITES}}"
export CUTLASS_PATH="${CUTLASS_PATH:-/path/to/cutlass}"
export CFLAGS="${CFLAGS:--I/usr/include}"
export LDFLAGS="${LDFLAGS:--L/usr/lib/x86_64-linux-gnu}"
export WANDB_PROJECT="${WANDB_PROJECT:-robotics_diffusion_transformer_libero}"

TRAIN_BATCH_SIZE="${TRAIN_BATCH_SIZE:-2}"
SAMPLE_BATCH_SIZE="${SAMPLE_BATCH_SIZE:-2}"
MAX_TRAIN_STEPS="${MAX_TRAIN_STEPS:-10}"
CHECKPOINTING_PERIOD="${CHECKPOINTING_PERIOD:-1000}"
SAMPLE_PERIOD="${SAMPLE_PERIOD:-5}"
GRADIENT_ACCUMULATION_STEPS="${GRADIENT_ACCUMULATION_STEPS:-1}"
DATALOADER_NUM_WORKERS="${DATALOADER_NUM_WORKERS:-2}"
REPORT_TO="${REPORT_TO:-tensorboard}"
MIXED_PRECISION="${MIXED_PRECISION:-bf16}"
LEARNING_RATE="${LEARNING_RATE:-1e-4}"

mkdir -p "$OUTPUT_DIR"

accelerate launch main.py \
    --deepspeed="./configs/zero2.json" \
    --pretrained_model_name_or_path="$RDT_MODEL_NAME" \
    --pretrained_text_encoder_name_or_path="$TEXT_ENCODER_NAME" \
    --pretrained_vision_encoder_name_or_path="$VISION_ENCODER_NAME" \
    --output_dir="$OUTPUT_DIR" \
    --train_batch_size="$TRAIN_BATCH_SIZE" \
    --sample_batch_size="$SAMPLE_BATCH_SIZE" \
    --max_train_steps="$MAX_TRAIN_STEPS" \
    --checkpointing_period="$CHECKPOINTING_PERIOD" \
    --sample_period="$SAMPLE_PERIOD" \
    --checkpoints_total_limit=4 \
    --gradient_accumulation_steps="$GRADIENT_ACCUMULATION_STEPS" \
    --lr_scheduler="constant" \
    --learning_rate="$LEARNING_RATE" \
    --mixed_precision="$MIXED_PRECISION" \
    --dataloader_num_workers="$DATALOADER_NUM_WORKERS" \
    --dataset_type="finetune" \
    --state_noise_snr=40 \
    --load_from_hdf5 \
    --report_to="$REPORT_TO"
```

- [ ] **Step 2: Make it executable**

Run:

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-object-ckpt/third_party/rdt
chmod +x finetune_libero.sh
```

- [ ] **Step 3: Check shell syntax**

Run:

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-object-ckpt/third_party/rdt
bash -n finetune_libero.sh
```

Expected:

```text
No output and exit code 0.
```

- [ ] **Step 4: Commit**

Run:

```bash
git add finetune_libero.sh
git commit -m "script: add LIBERO fine-tuning entry point"
```

---

### Task 8: Run Training Smoke Test On `libero_10`

**Files:**
- Uses: `third_party/rdt/finetune_libero.sh`
- Uses: `third_party/rdt/configs/dataset_stat.json`
- Generated: `third_party/rdt/checkpoints/rdt-libero-smoke/`

- [ ] **Step 1: Run a one-step smoke fine-tune**

Run:

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-object-ckpt/third_party/rdt
RDT_LIBERO_SUITES=libero_10 \
OUTPUT_DIR=./checkpoints/rdt-libero-smoke \
MAX_TRAIN_STEPS=1 \
TRAIN_BATCH_SIZE=1 \
SAMPLE_BATCH_SIZE=1 \
SAMPLE_PERIOD=-1 \
REPORT_TO=tensorboard \
./finetune_libero.sh
```

Expected:

```text
Training starts, loads the pretrained checkpoint, consumes LIBERO HDF5 batches, and exits after 1 step without shape, dtype, device, or NaN errors.
```

- [ ] **Step 2: Run a short sampled smoke fine-tune**

Run:

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-object-ckpt/third_party/rdt
RDT_LIBERO_SUITES=libero_10 \
OUTPUT_DIR=./checkpoints/rdt-libero-smoke-sampled \
MAX_TRAIN_STEPS=10 \
TRAIN_BATCH_SIZE=1 \
SAMPLE_BATCH_SIZE=1 \
SAMPLE_PERIOD=5 \
REPORT_TO=tensorboard \
./finetune_libero.sh
```

Expected:

```text
Training logs loss and sample metrics, including overall_avg_sample_mse, without modifying RDT loss code.
```

- [ ] **Step 3: Record verification result**

Append a short dated note to `third_party/rdt/agent/libero_dataset_semantics_analysis.md`:

```markdown

## 2026-05-23 RDT LIBERO Loader Smoke Result

`libero_10` loader, statistics generation, and short RDT fine-tuning were verified through the RDT HDF5 path. Training used `RDT_HDF5_BACKEND=libero`, `RDT_LIBERO_SUITES=libero_10`, and `--load_from_hdf5`. Verification was limited to dataset handling, statistics, and RDT fine-tuning; LIBERO benchmark rollout code was not touched.
```

- [ ] **Step 4: Commit the note**

Run:

```bash
git add agent/libero_dataset_semantics_analysis.md
git commit -m "docs: record LIBERO RDT smoke verification"
```

---

### Task 9: Enable Four-Suite Official LIBERO Training

**Status:** Wait for approval. Do not execute this task until Tasks 1-8 have been implemented, tested, debugged, and explicitly approved by the user.

**Files:**
- Modify: `third_party/rdt/data/libero_vla_dataset.py`
- Modify: `third_party/rdt/tests/test_libero_vla_dataset.py`
- Modify: `third_party/rdt/configs/finetune_datasets.json`
- Modify: `third_party/rdt/configs/finetune_sample_weights.json`
- Modify: `third_party/rdt/configs/dataset_control_freq.json`
- Generated: `third_party/rdt/configs/dataset_stat.json`
- Generated: `third_party/rdt/checkpoints/rdt-libero-four-suite-smoke/`

- [ ] **Step 1: Add a multi-suite indexing test**

Append this test to `third_party/rdt/tests/test_libero_vla_dataset.py`:

```python
def test_dataset_indexes_multiple_libero_suites(tmp_path, monkeypatch):
    data_root = tmp_path / "hf_cache"
    _write_synthetic_libero_file(data_root / "libero_10" / "SYNTHETIC_10_demo.hdf5")
    _write_synthetic_libero_file(data_root / "libero_object" / "SYNTHETIC_object_demo.hdf5")
    _write_synthetic_libero_file(data_root / "libero_spatial" / "SYNTHETIC_spatial_demo.hdf5")
    _write_synthetic_libero_file(data_root / "libero_goal" / "SYNTHETIC_goal_demo.hdf5")
    monkeypatch.chdir(RDT_ROOT)
    monkeypatch.setenv("RDT_LIBERO_DATA_ROOT", str(data_root))
    monkeypatch.setenv("RDT_LIBERO_SUITES", "libero_10,libero_object,libero_spatial,libero_goal")

    from data.libero_vla_dataset import LiberoVLADataset

    dataset = LiberoVLADataset()
    assert len(dataset) == 4
    assert dataset.get_dataset_name() == "libero_10,libero_object,libero_spatial,libero_goal"
    assert [record.suite for record in dataset.records] == [
        "libero_10",
        "libero_object",
        "libero_spatial",
        "libero_goal",
    ]

    sample = dataset.get_item(index=2, step_id=0)
    assert sample["meta"]["dataset_name"] == "libero_spatial"
    assert sample["state"].shape == (1, 128)
    assert sample["actions"].shape == (64, 128)
```

- [ ] **Step 2: Run the new test and verify it fails**

Run:

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-object-ckpt/third_party/rdt
python -m pytest tests/test_libero_vla_dataset.py::test_dataset_indexes_multiple_libero_suites -q
```

Expected:

```text
ValueError: RDT_LIBERO_SUITES must contain exactly one suite
```

- [ ] **Step 3: Replace the single-suite env parser**

In `third_party/rdt/data/libero_vla_dataset.py`, replace:

```python
def _suite_from_env():
    raw = os[redacted env file]iron.get("RDT_LIBERO_SUITES", "libero_10")
    suites = tuple(s.strip() for s in raw.split(",") if s.strip())
    if len(suites) != 1:
        raise ValueError(
            "RDT_LIBERO_SUITES must contain exactly one suite for this fine-tuning backend. "
            "Run separate stats/training jobs for libero_10 and libero_object."
        )
    if suites[0] not in LIBERO_SUITES:
        raise ValueError("Unknown LIBERO suite: {}".format(suites[0]))
    return suites[0]
```

with:

```python
def _suites_from_env():
    raw = os[redacted env file]iron.get("RDT_LIBERO_SUITES", "libero_10")
    suites = tuple(s.strip() for s in raw.split(",") if s.strip())
    if not suites:
        raise ValueError("RDT_LIBERO_SUITES did not contain any suite names")
    unknown = sorted(set(suites) - set(LIBERO_SUITES))
    if unknown:
        raise ValueError("Unknown LIBERO suites: {}".format(unknown))
    return suites
```

- [ ] **Step 4: Replace the dataset constructor and file discovery**

In `third_party/rdt/data/libero_vla_dataset.py`, replace the constructor, `_hdf5_files`, `_build_index`, and `get_dataset_name` methods with:

```python
    def __init__(self, data_root=None, suite=None):
        self.data_root = data_root or os[redacted env file]iron.get("RDT_LIBERO_DATA_ROOT", DEFAULT_LIBERO_DATA_ROOT)
        if suite is None:
            self.suites = _suites_from_env()
        elif isinstance(suite, str):
            self.suites = tuple(s.strip() for s in suite.split(",") if s.strip())
        else:
            self.suites = tuple(suite)
        unknown = sorted(set(self.suites) - set(LIBERO_SUITES))
        if unknown:
            raise ValueError("Unknown LIBERO suites: {}".format(unknown))

        with open("configs/base.yaml", "r") as f:
            config = yaml.safe_load(f)
        self.CHUNK_SIZE = int(config["common"]["action_chunk_size"])
        self.IMG_HISTORY_SIZE = int(config["common"]["img_history_size"])
        self.STATE_DIM = int(config["common"]["state_dim"])
        self.records = self._build_index()
        lengths = np.asarray([record.num_steps for record in self.records], dtype=np.float64)
        self.episode_sample_weights = lengths / lengths.sum()

    def _hdf5_files(self):
        all_files = []
        for suite in self.suites:
            suite_dir = Path(self.data_root) / suite
            suite_files = sorted(suite_dir.glob("*.hdf5"))
            if not suite_files:
                raise FileNotFoundError("No LIBERO HDF5 files found in {}".format(suite_dir))
            all_files.extend((suite, file_path) for file_path in suite_files)
        return all_files

    def _build_index(self):
        records = []
        for suite, file_path in self._hdf5_files():
            with h5py.File(file_path, "r") as f:
                data = f["data"]
                problem_info = _json_attr(data, "problem_info")
                env_args = _json_attr(data, "env_args")
                env_kwargs = env_args["env_kwargs"]
                controller_config = env_kwargs["controller_configs"]
                demo_keys = sorted(
                    [key for key in data.keys() if key.startswith("demo_")],
                    key=lambda key: int(key.split("_")[-1]),
                )
                for demo_key in demo_keys:
                    num_steps = int(data[demo_key]["actions"].shape[0])
                    if num_steps < 1:
                        continue
                    records.append(
                        LiberoEpisodeRecord(
                            file_path=str(file_path),
                            suite=suite,
                            task_name=_task_name_from_path(file_path),
                            demo_key=demo_key,
                            num_steps=num_steps,
                            instruction=problem_info["language_instruction"],
                            control_freq=int(env_kwargs.get("control_freq", 20)),
                            controller_config=controller_config,
                        )
                    )
        if not records:
            raise RuntimeError("No LIBERO demos indexed from {}".format(self.data_root))
        return records

    def get_dataset_name(self):
        return ",".join(self.suites)
```

- [ ] **Step 5: Run all loader tests**

Run:

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-object-ckpt/third_party/rdt
python -m pytest tests/test_libero_vla_dataset.py -q
```

Expected:

```text
8 passed
```

- [ ] **Step 6: Register the four official training suites**

Replace `third_party/rdt/configs/finetune_datasets.json` with:

```json
[
    "libero_10",
    "libero_object",
    "libero_spatial",
    "libero_goal"
]
```

Replace `third_party/rdt/configs/finetune_sample_weights.json` with:

```json
{
    "libero_10": 100,
    "libero_object": 100,
    "libero_spatial": 100,
    "libero_goal": 100
}
```

In `third_party/rdt/configs/dataset_control_freq.json`, ensure all four entries exist:

```json
    "libero_10": 20,
    "libero_object": 20,
    "libero_spatial": 20,
    "libero_goal": 20
```

- [ ] **Step 7: Validate the updated JSON configs**

Run:

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-object-ckpt/third_party/rdt
python -m json.tool configs/finetune_datasets.json >/tmp/rdt_finetune_datasets.json
python -m json.tool configs/finetune_sample_weights.json >/tmp/rdt_finetune_sample_weights.json
python -m json.tool configs/dataset_control_freq.json >/tmp/rdt_dataset_control_freq.json
```

Expected:

```text
No output and exit code 0 for all three commands.
```

- [ ] **Step 8: Compute stats once per suite**

Run:

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-object-ckpt/third_party/rdt
for suite in libero_10 libero_object libero_spatial libero_goal; do
  RDT_HDF5_BACKEND=libero \
  RDT_LIBERO_DATA_ROOT=/mnt/data/hf_cache/hub \
  RDT_LIBERO_SUITES="$suite" \
  python -m data.compute_dataset_stat_hdf5 --save_path configs/dataset_stat.json
done
```

Expected output includes one processing line per suite:

```text
Processing libero_10 dataset
Processing libero_object dataset
Processing libero_spatial dataset
Processing libero_goal dataset
```

- [ ] **Step 9: Verify all four stats entries exist**

Run:

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-object-ckpt/third_party/rdt
python - <<'PY'
import json
suites = ["libero_10", "libero_object", "libero_spatial", "libero_goal"]
with open("configs/dataset_stat.json", "r") as f:
    stats = json.load(f)
missing = [suite for suite in suites if suite not in stats]
assert not missing, missing
for suite in suites:
    assert len(stats[suite]["state_mean"]) == 128
    assert len(stats[suite]["state_std"]) == 128
print("verified_stats", suites)
PY
```

Expected:

```text
verified_stats ['libero_10', 'libero_object', 'libero_spatial', 'libero_goal']
```

- [ ] **Step 10: Smoke-test one multi-suite consumer batch**

Run:

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-object-ckpt/third_party/rdt
python scripts/smoke_test_libero_dataset.py \
  --suite libero_10,libero_object,libero_spatial,libero_goal \
  --data-root /mnt/data/hf_cache/hub \
  --consumer
```

Expected output includes:

```text
consumer.states: (2, 1, 128)
consumer.actions: (2, 64, 128)
consumer.images: (2, 6
```

- [ ] **Step 11: Run a four-suite training smoke test**

Run:

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-object-ckpt/third_party/rdt
RDT_LIBERO_SUITES=libero_10,libero_object,libero_spatial,libero_goal \
OUTPUT_DIR=./checkpoints/rdt-libero-four-suite-smoke \
MAX_TRAIN_STEPS=10 \
TRAIN_BATCH_SIZE=1 \
SAMPLE_BATCH_SIZE=1 \
SAMPLE_PERIOD=5 \
REPORT_TO=tensorboard \
./finetune_libero.sh
```

Expected:

```text
Training uses records from the four requested suites and logs loss plus overall_avg_sample_mse without shape, dtype, device, or NaN errors.
```

- [ ] **Step 12: Commit full-suite support**

Run:

```bash
git add data/libero_vla_dataset.py tests/test_libero_vla_dataset.py \
  configs/finetune_datasets.json configs/finetune_sample_weights.json \
  configs/dataset_control_freq.json configs/dataset_stat.json
git commit -m "feat: support four-suite LIBERO fine-tuning"
```

---

## Final Verification Checklist

Run these before calling implementation complete:

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-object-ckpt/third_party/rdt
python -m pytest tests/test_libero_vla_dataset.py -q
python -m json.tool configs/finetune_datasets.json >/tmp/rdt_finetune_datasets.json
python -m json.tool configs/finetune_sample_weights.json >/tmp/rdt_finetune_sample_weights.json
python -m json.tool configs/dataset_control_freq.json >/tmp/rdt_dataset_control_freq.json
RDT_HDF5_BACKEND=libero RDT_LIBERO_SUITES=libero_10 python scripts/smoke_test_libero_dataset.py --consumer
bash -n finetune_libero.sh
```

Expected:

```text
All pytest tests pass.
All JSON validation commands exit 0.
The consumer smoke test prints batch shapes for states/actions/images.
The shell syntax check exits 0.
```

## Notes For Execution

- Use `libero_10` first because it is fully downloaded.
- Do not execute Task 9 until the user explicitly approves it after Tasks 1-8 are implemented, tested, and debugged.
- Use Task 9, after approval, for official four-suite training over `libero_10`, `libero_object`, `libero_spatial`, and `libero_goal`.
- Compute stats once per suite before the four-suite training run.
- Do not change `configs/base.yaml`.
- Do not change `models/rdt_runner.py`.
- Do not change loss masking or introduce a new loss term.
- Do not touch code outside `third_party/rdt` without explicit approval.
- Monitor fine-tuning with `loss` and `overall_avg_sample_mse`, matching the RDT README guidance.
