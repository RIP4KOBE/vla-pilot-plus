import json
import os
from dataclasses import dataclass
from pathlib import Path

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


def _suites_from_raw(raw):
    suites = tuple(s.strip() for s in raw.split(",") if s.strip())
    if not suites:
        raise ValueError("RDT_LIBERO_SUITES did not contain any suite names")
    duplicates = sorted({suite for suite in suites if suites.count(suite) > 1})
    if duplicates:
        raise ValueError("Duplicate LIBERO suites: {}".format(duplicates))
    return suites


def _suites_from_env():
    raw = os.environ.get("RDT_LIBERO_SUITES", "libero_10")
    return _suites_from_raw(raw)


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
        raise ValueError(
            "Expected LIBERO OSC_POSE controller, got {}".format(controller_config.get("type"))
        )
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
        raise ValueError(
            "Expected six OSC_POSE output limits, got {} and {}".format(output_min, output_max)
        )

    clipped = np.clip(raw_action_6d, input_min, input_max)
    action_scale = np.abs(output_max - output_min) / np.abs(input_max - input_min)
    output_center = (output_max + output_min) / 2.0
    input_center = (input_max + input_min) / 2.0
    return (clipped - input_center) * action_scale + output_center


class LiberoVLADataset:
    def __init__(self, data_root=None, suite=None):
        self.data_root = data_root or os.environ.get("RDT_LIBERO_DATA_ROOT", DEFAULT_LIBERO_DATA_ROOT)
        if suite is None:
            self.suites = _suites_from_env()
        elif isinstance(suite, str):
            self.suites = _suites_from_raw(suite)
        else:
            self.suites = tuple(str(s).strip() for s in suite if str(s).strip())
            if not self.suites:
                raise ValueError("No LIBERO suite names were provided")
        self.suite = self.suites[0] if len(self.suites) == 1 else None
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
            files = sorted(suite_dir.glob("*.hdf5"))
            if not files:
                raise FileNotFoundError("No LIBERO HDF5 files found in {}".format(suite_dir))
            all_files.extend((suite, file_path) for file_path in files)
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

    def __len__(self):
        return len(self.records)

    def get_dataset_name(self):
        return ",".join(self.suites)

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
        history = images[start : step_id + 1].astype(np.uint8)
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
            np.sqrt(np.mean(states**2, axis=0)).astype(np.float32),
        )

    def _padded_action_chunk(self, actions, step_id):
        chunk = actions[step_id : step_id + self.CHUNK_SIZE]
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
            cam_right_wrist, cam_right_wrist_mask = self._image_history(
                demo, "eye_in_hand_rgb", step_id
            )
            cam_left_wrist = np.zeros((self.IMG_HISTORY_SIZE, 0, 0, 0), dtype=np.uint8)
            cam_left_wrist_mask = np.zeros((self.IMG_HISTORY_SIZE,), dtype=bool)

            return {
                "meta": {
                    "dataset_name": record.suite,
                    "#steps": record.num_steps,
                    "step_id": step_id,
                    "instruction": record.instruction,
                },
                "state": states[step_id : step_id + 1].astype(np.float32),
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
