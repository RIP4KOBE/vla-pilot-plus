import json
import sys
from pathlib import Path

import h5py
import numpy as np
import pytest


RDT_ROOT = Path(__file__).resolve().parents[1]
if str(RDT_ROOT) not in sys.path:
    sys.path.insert(0, str(RDT_ROOT))


def _write_synthetic_libero_file(path, length=6, action_gripper_values=None, num_demos=1):
    path.parent.mkdir(parents=True, exist_ok=True)
    if action_gripper_values is None:
        action_gripper_values = np.where(np.arange(length) % 2 == 0, -1.0, 1.0).astype(np.float64)
    else:
        action_gripper_values = np.asarray(action_gripper_values, dtype=np.float64)
        assert len(action_gripper_values) >= length, "action_gripper_values must cover every timestep"

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
        data.attrs["num_demos"] = np.int64(num_demos)
        data.attrs["total"] = np.int64(length * num_demos)

        for demo_idx in range(num_demos):
            demo = data.create_group(f"demo_{demo_idx}")
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


def _expected_libero_active_indices():
    from configs.state_vec import STATE_VEC_IDX_MAPPING

    names = [
        "right_gripper_open",
        "right_eef_pos_x",
        "right_eef_pos_y",
        "right_eef_pos_z",
        "right_eef_angle_0",
        "right_eef_angle_1",
        "right_eef_angle_2",
        "right_eef_angle_3",
        "right_eef_angle_4",
        "right_eef_angle_5",
    ]
    return sorted({STATE_VEC_IDX_MAPPING[name] for name in names})


def _setup_env(tmp_path, monkeypatch):
    data_root = tmp_path / "hf_cache"
    _write_synthetic_libero_file(data_root / "libero_10" / "SYNTHETIC_task_demo.hdf5", num_demos=2)
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
    assert len(dataset) == 2
    assert sorted(record.demo_key for record in dataset.records) == ["demo_0", "demo_1"]
    records_by_key = {record.demo_key: record for record in dataset.records}
    for demo_key in ("demo_0", "demo_1"):
        record = records_by_key[demo_key]
        assert record.suite == "libero_10"
        assert record.num_steps == 6
        assert record.instruction == "pick up the synthetic object"
        assert record.control_freq == 20
    assert dataset.get_dataset_name() == "libero_10"


def test_state_and_action_mapping_uses_rdt_6d_slots(tmp_path, monkeypatch):
    _setup_env(tmp_path, monkeypatch)

    from configs.state_vec import STATE_VEC_IDX_MAPPING
    from data.libero_vla_dataset import (
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
    expected_active_indices = _expected_libero_active_indices()
    assert expected_active_indices == [10, 30, 31, 32, 33, 34, 35, 36, 37, 38]
    assert np.where(indicator > 0)[0].tolist() == expected_active_indices
    right_arm_joint_pos_indices = [STATE_VEC_IDX_MAPPING[f"right_arm_joint_{idx}_pos"] for idx in range(7)]
    assert np.allclose(states[0, right_arm_joint_pos_indices], np.zeros(7, dtype=np.float32))
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
    assert sample["cam_high"][-1, 0, 0].tolist() == [12, 34, 56]
    assert sample["cam_right_wrist"][-1, 0, 0].tolist() == [90, 80, 70]
    assert sample["actions"][0, 30] == pytest.approx(0.025)
    assert sample["actions"][0, 10] == pytest.approx(1.0)


def test_get_item_pads_near_end_action_chunk(tmp_path, monkeypatch):
    _setup_env(tmp_path, monkeypatch)

    from data.libero_vla_dataset import LiberoVLADataset

    dataset = LiberoVLADataset()
    dataset.CHUNK_SIZE = 4
    sample = dataset.get_item(index=0, step_id=4)

    active_indices = _expected_libero_active_indices()
    assert sample["actions"].shape == (4, 128)
    assert sample["actions"][0, 10] == pytest.approx(1.0)
    assert sample["actions"][1, 10] == pytest.approx(0.0)
    assert np.allclose(sample["actions"][2:, active_indices], sample["actions"][1, active_indices])


def test_state_only_returns_full_mapped_trajectory(tmp_path, monkeypatch):
    _setup_env(tmp_path, monkeypatch)

    from data.libero_vla_dataset import LiberoVLADataset

    dataset = LiberoVLADataset()
    episode = dataset.get_item(index=0, state_only=True)
    assert episode["dataset_name"] == "libero_10"
    assert episode["state"].shape == (6, 128)
    assert episode["action"].shape == (6, 128)
    assert np.allclose(episode["state"][0, 30:33], np.array([0.1, -0.2, 0.8], dtype=np.float32))
    assert episode["state"][0, 10] == pytest.approx(1.0)
    assert episode["action"][0, 30] == pytest.approx(0.025)
    assert episode["action"][1, 10] == pytest.approx(0.0)


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


def test_dataset_accepts_future_libero_suite_names(tmp_path, monkeypatch):
    data_root = tmp_path / "hf_cache"
    _write_synthetic_libero_file(data_root / "libero_90" / "SYNTHETIC_90_demo.hdf5")
    monkeypatch.chdir(RDT_ROOT)
    monkeypatch.setenv("RDT_LIBERO_DATA_ROOT", str(data_root))
    monkeypatch.setenv("RDT_LIBERO_SUITES", "libero_90")

    from data.libero_vla_dataset import LiberoVLADataset

    dataset = LiberoVLADataset()
    assert len(dataset) == 1
    assert dataset.get_dataset_name() == "libero_90"
    sample = dataset.get_item(index=0, step_id=0)
    assert sample["meta"]["dataset_name"] == "libero_90"
    assert sample["state"].shape == (1, 128)
    assert sample["actions"].shape == (64, 128)


def test_hdf5_backend_switch_selects_libero(tmp_path, monkeypatch):
    _setup_env(tmp_path, monkeypatch)
    monkeypatch.setenv("RDT_HDF5_BACKEND", "libero")

    import importlib

    module_name = "data.hdf5_vla_dataset"
    previous_module = sys.modules.pop(module_name, None)
    data_package = sys.modules.get("data")
    had_package_attr = data_package is not None and hasattr(data_package, "hdf5_vla_dataset")
    previous_package_attr = getattr(data_package, "hdf5_vla_dataset", None) if had_package_attr else None

    try:
        hdf5_vla_dataset = importlib.import_module(module_name)
        dataset = hdf5_vla_dataset.HDF5VLADataset()
        assert dataset.get_dataset_name() == "libero_10"
    finally:
        sys.modules.pop(module_name, None)
        if previous_module is not None:
            sys.modules[module_name] = previous_module
        data_package = sys.modules.get("data")
        if data_package is not None:
            if had_package_attr:
                setattr(data_package, "hdf5_vla_dataset", previous_package_attr)
            elif hasattr(data_package, "hdf5_vla_dataset"):
                delattr(data_package, "hdf5_vla_dataset")
