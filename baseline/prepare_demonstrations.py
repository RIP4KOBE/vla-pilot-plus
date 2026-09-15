"""Reconstruct v44 state sidecars from immutable, accepted LIBERO recordings."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import time

from .demonstration_inputs import CONTRACT, policy_image, policy_state, read_conversion, state_action_digest
from .io import digest, read_json, write_json


def exported_episodes(root):
    """Read only index/state/action columns, and verify contiguous frame order."""
    import numpy as np
    import pyarrow.parquet as pq
    pieces = {}
    for path in sorted((Path(root) / "data").glob("**/*.parquet")):
        table = pq.read_table(path, columns=["episode_index", "frame_index", "observation.state", "action"])
        episode = table["episode_index"].to_numpy()
        frame = table["frame_index"].to_numpy()
        states = np.asarray(table["observation.state"].to_pylist(), dtype=np.float32)
        actions = np.asarray(table["action"].to_pylist(), dtype=np.float32)
        for key in np.unique(episode):
            mask = episode == key
            pieces.setdefault(int(key), []).append((frame[mask], states[mask], actions[mask]))
    result = {}
    for key, chunks in pieces.items():
        indices = np.concatenate([r[0] for r in chunks])
        order = np.argsort(indices)
        if not np.array_equal(indices[order], np.arange(len(indices))):
            raise ValueError(f"episode {key} has missing or duplicate frames")
        states = np.concatenate([r[1] for r in chunks])[order]
        actions = np.concatenate([r[2] for r in chunks])[order]
        result[key] = {"frames": len(indices), "state_action_sha256": state_action_digest(states, actions)}
    return result


def match_recordings(source, state_reader=None):
    """Match full state/action sequences, never assume file or curation order."""
    import h5py
    import numpy as np
    raw_root = Path(source["root"])
    curation = read_json(raw_root.parent / "curation.json")
    if curation["curation_sha256"] != source["source_curation_sha256"]:
        raise ValueError("source curation identity changed")
    export = exported_episodes(raw_root)
    matches = {}
    for filename in curation["accepted"]:
        with h5py.File(filename, "r") as handle:
            steps = len(handle["action"])
            if str(handle.attrs["ticket_id"]) != source["source_ticket_id"]:
                raise ValueError("recording belongs to another ticket")
            if str(handle.attrs["init_state_id"]) not in source["init_state_ids"]:
                raise ValueError("recording initial state is outside the training source")
            if len(handle["observation/state"]) != steps + 1 or len(handle["simulator_state"]) != steps + 1:
                raise ValueError("recorded state/action alignment is invalid")
            states, actions = handle["observation/state"][:steps], handle["action"][:]
            if not np.isfinite(states).all() or not np.isfinite(actions).all():
                raise ValueError("recorded state/action contains nonfinite values")
            fingerprint = state_action_digest(states, actions)
            simulator_digest = hashlib_array(np.asarray(handle["simulator_state"][:steps], dtype="<f8"))
            matches.setdefault(fingerprint, []).append({"source_hdf5": filename, "frames": steps,
                                    "init_state_id": str(handle.attrs["init_state_id"]),
                                    "env_seed": int(handle.attrs.get("env_seed", 0)),
                                    "recorded_simulator_sha256": simulator_digest})
    if set(export) != set(source["episodes"]) or sum(map(len, matches.values())) != len(export):
        raise ValueError("export and accepted recordings cover different episodes")
    for candidates in matches.values():
        equivalent_error = 0.0
        policy_error = None
        if len({r["recorded_simulator_sha256"] for r in candidates}) != 1:
            with h5py.File(candidates[0]["source_hdf5"], "r") as handle:
                reference_states = np.asarray(handle["simulator_state"][:candidates[0]["frames"]], dtype=np.float64)
            for candidate in candidates[1:]:
                with h5py.File(candidate["source_hdf5"], "r") as handle:
                    states = np.asarray(handle["simulator_state"][:candidate["frames"]], dtype=np.float64)
                if states.shape != reference_states.shape or not np.isfinite(states).all():
                    raise ValueError("ambiguous duplicate state/action sequences have different simulator states")
                equivalent_error = max(equivalent_error, float(np.abs(states - reference_states).max()))
            # Repeated deterministic rollouts can differ at ~1e-11 in MuJoCo's
            # float64 state despite identical exported float32 observations.
            if equivalent_error > 1e-9:
                if state_reader is None:
                    raise ValueError("ambiguous duplicate state/action sequences have different simulator states")
                reference = state_reader(candidates[0]["source_hdf5"], candidates[0]["frames"])
                policy_error = 0.0
                for candidate in candidates[1:]:
                    state = state_reader(candidate["source_hdf5"], candidate["frames"])
                    if state.shape != reference.shape or not np.isfinite(state).all():
                        raise ValueError("duplicate recordings have different v44 policy states")
                    policy_error = max(policy_error, float(np.abs(state - reference).max()))
                if policy_error > 1e-7:
                    raise ValueError("duplicate recordings have different v44 policy states")
        # The raw dataset supplies each episode's own images. For state sidecars,
        # equivalent policy-input trajectories suffice even if object velocities differ.
        # Preserve every source episode and its training weight, without deduplication.
        copies = len(candidates)
        candidates.sort(key=lambda r: r["source_hdf5"])
        for row in candidates:
            row["equivalent_sequence_copies"] = copies
            row["equivalent_simulator_max_abs_error"] = equivalent_error
            row["equivalent_policy_state_max_abs_error"] = policy_error
    rows = []
    for index, value in sorted(export.items()):
        candidates = matches.get(value["state_action_sha256"], [])
        if not candidates:
            raise ValueError(f"export episode {index} does not exactly match an accepted recording")
        rows.append({**candidates.pop(0), **value, "episode_index": index})
    return rows


def reconstruct_policy_states(sim, robot, flat_states):
    """Same site, body quaternion and finger indices as Robosuite's sensors."""
    import numpy as np
    positions, quaternions, fingers = [], [], []
    for flat in flat_states:
        sim.set_state_from_flattened(flat)
        sim.forward()
        positions.append(np.array(sim.data.site_xpos[robot.eef_site_id]))
        quat_wxyz = np.array(sim.data.get_body_xquat(robot.robot_model.eef_name))
        quaternions.append(quat_wxyz[[1, 2, 3, 0]])
        fingers.append(np.array(sim.data.qpos[robot._ref_gripper_joint_pos_indexes]))
    return policy_state(np.asarray(positions), np.asarray(quaternions), np.asarray(fingers)).numpy()


def online_comparison(adapter, env, handle, frame, converted_state, cfg):
    """Refresh sensors after restoration; compare with the actual online path."""
    import cv2
    import numpy as np
    import torch
    raw = env._get_observations(force_update=True)
    taskenv = adapter._env[adapter.current_task_idx]
    taskenv._last_raw_obs = raw
    adapter._last_obs = taskenv._format_raw_obs(raw)
    online = adapter.get_policy_observation(1)
    error = float((online["observation.state"][0] - converted_state).abs().max())
    if error > 5e-6:
        raise ValueError(f"converted state differs from online input by {error}")
    result = {"frame": frame, "state_max_abs_error": error, "images": {}}
    for name, camera in (("image", "agentview_image"), ("image2", "robot0_eye_in_hand_image")):
        target = online["observation.images." + name][0].cpu()
        same = cv2.resize(raw[camera], (256, 256), interpolation=cv2.INTER_AREA)
        tensor = torch.from_numpy(same.copy()).permute(2, 0, 1).float() / 255
        corrected = policy_image(tensor, cfg["observation_height"], cfg["observation_width"])
        same_error = float((corrected - target).abs().max())
        if same_error > 1e-6:
            raise ValueError(f"converted {name} differs from the online image transform")
        stored = torch.from_numpy(handle["observation/images/" + name][frame]).permute(2, 0, 1).float() / 255
        transformed = policy_image(stored, cfg["observation_height"], cfg["observation_width"])
        result["images"][name] = {"same_render_max_abs_error": same_error,
                                  "stored_vs_rerender_mae_255": float((transformed - target).abs().mean() * 255)}
    return result


def prepare_task(source, cfg, protocol, destination):
    import h5py
    import numpy as np
    import torch
    from .environment import make_environment, reset_environment
    protocol.validate_training_source(source)
    destination = Path(destination)
    manifest_path = destination / "manifest.json"
    reference = {"contract": CONTRACT, "manifest": str(manifest_path.resolve())}
    if manifest_path.exists():
        result = {**source, "policy_input": {**reference, "sha256": digest(manifest_path)}}
        read_conversion(result, cfg)
        return result
    temporary = destination.with_name(destination.name + ".partial")
    temporary.mkdir(parents=True, exist_ok=False)
    task = protocol.tasks[source["task_key"]]
    curation = read_json(Path(source["root"]).parent / "curation.json")
    with h5py.File(next(iter(curation["accepted"])), "r") as handle:
        initial_state = str(handle.attrs["init_state_id"])
        initial_seed = int(handle.attrs.get("env_seed", 0))
    if initial_state not in source["init_state_ids"]:
        raise ValueError("initial demonstration is outside the training source")
    context = {**{k: task[k] for k in ("task_key", "runtime_suite", "suite", "task_id", "task_index", "perturbation_variant")},
               "init_state_id": initial_state, "seed": initial_seed, "split": source["split"]}
    adapter = make_environment({**cfg, "device": "cpu"}, context)
    comparisons, records, all_states = [], [], []
    try:
        reset_environment(adapter, context)
        wrapper = adapter._get_current_robosuite_env()
        env = getattr(wrapper, "env", wrapper)
        sim, robot = env.sim, env.robots[0]
        expected_flat_size = len(sim.get_state().flatten())
        if len(robot._ref_gripper_joint_pos_indexes) != 2:
            raise ValueError("v44 LIBERO input requires two gripper positions")
        cached_states = {}
        def state_reader(filename, frames):
            if filename not in cached_states:
                with h5py.File(filename, "r") as handle:
                    flat = np.asarray(handle["simulator_state"][:frames], dtype=np.float64)
                if flat.shape != (frames, expected_flat_size) or not np.isfinite(flat).all():
                    raise ValueError("recorded simulator state differs from the task model")
                cached_states[filename] = reconstruct_policy_states(sim, robot, flat)
            return cached_states[filename]
        rows = match_recordings(source, state_reader=state_reader)
        for episode_number, row in enumerate(rows):
            with h5py.File(row["source_hdf5"], "r") as handle:
                flat_states = np.asarray(handle["simulator_state"][:row["frames"]], dtype=np.float64)
                if flat_states.shape != (row["frames"], expected_flat_size) or not np.isfinite(flat_states).all():
                    raise ValueError("recorded simulator state differs from the task model")
                # Forward kinematics only: no policy, rendering or robot actions.
                converted = torch.from_numpy(state_reader(row["source_hdf5"], row["frames"]))
                ee_error = float(np.abs(converted[:, :3].numpy() - handle["ee_position"][:row["frames"]]).max())
                if ee_error > .01:
                    raise ValueError(f"recorded and reconstructed end-effector positions differ by {ee_error} m")
                if episode_number == 0:
                    for frame in sorted({0, row["frames"] // 2, row["frames"] - 1}):
                        sim.set_state_from_flattened(flat_states[frame])
                        sim.forward()
                        comparisons.append(online_comparison(adapter, env, handle, frame, converted[frame], cfg))
                filename = f"episode_{row['episode_index']:06d}.npy"
                np.save(temporary / filename, converted.numpy(), allow_pickle=False)
                records.append({**row, "states_path": str((destination / filename).resolve()),
                                "states_sha256": digest(temporary / filename),
                                "simulator_states_sha256": hashlib_array(flat_states),
                                "reconstructed_vs_recorded_ee_max_abs_m": ee_error})
                all_states.append(converted.numpy())
                print(f"prepared {source['task_key']} episode {episode_number + 1}/{len(rows)} ({row['frames']} frames)", flush=True)
    finally:
        adapter.close()
    state_array = np.concatenate(all_states)
    manifest = {"contract": CONTRACT, "task_key": source["task_key"],
                "raw_root": str(Path(source["root"]).resolve()),
                "source_curation_sha256": source["source_curation_sha256"],
                "source_info_sha256": digest(Path(source["root"]) / "meta/info.json"),
                "height": cfg["observation_height"], "width": cfg["observation_width"],
                "state_convention": "eef_xyz_axisangle_two_finger_positions",
                "image_transform": "uint8_area_resize_then_flip_height_and_width",
                "actions": "unchanged; full state/action arrays matched to exported episode indices",
                "checkpoint_normalization": "unchanged v44 processors",
                "episodes": records, "frames": len(state_array),
                "state_statistics": {"min": state_array.min(0).tolist(), "max": state_array.max(0).tolist(),
                                     "mean": state_array.mean(0).tolist(), "std": state_array.std(0).tolist()},
                "validation": {"passed": True, "observables_force_update": True,
                               "comparisons": comparisons, "policy_loaded": False, "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES")},
                "created_at": datetime.now(timezone.utc).isoformat()}
    write_json(temporary / "manifest.json", manifest)
    temporary.rename(destination)
    return {**source, "policy_input": {**reference, "sha256": digest(manifest_path)}}


def hashlib_array(array):
    import hashlib
    return hashlib.sha256(array.tobytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    args = parser.parse_args()
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", LP_NUM_THREADS="1")
    from .config import cpu_environment, load_config
    from .experiment import task_order
    from .protocol import Protocol
    cpu_environment()
    cfg = load_config(args.config)
    if cfg.get("demonstration_contract") != CONTRACT:
        raise ValueError("input preparation requires an explicit corrected demonstration contract")
    root = Path(cfg["output_root"])
    if "self_improve" in root.resolve().parts or "models" in root.resolve().parts:
        raise ValueError("derived inputs must be in baseline outputs")
    protocol = Protocol(cfg["protocol"])
    order = task_order(cfg, protocol)
    results, started = [], time.monotonic()
    status_path = root / "preparation_status.json"
    try:
        for index, key in enumerate(order):
            write_json(status_path, {"status": "PREPARING", "tasks_completed": len(results), "tasks_planned": len(order), "current_task": key})
            sources = read_json(args.source_dir / f"demonstrations_{index:03d}.json")["tasks"]
            if len(sources) != 1 or sources[0]["task_key"] != key:
                raise ValueError("demonstration source order differs from the frozen task selection")
            converted = prepare_task(sources[0], cfg, protocol, root / "policy_inputs" / f"task_{index:03d}")
            results.append(converted)
            write_json(root / "prepared_sources" / f"demonstrations_{index:03d}.json",
                       {"schema_version": "baseline-task-data-v1", "tasks": [converted]})
        write_json(root / "prepared_sources/all_tasks.json", {"schema_version": "baseline-task-data-v1", "tasks": results})
        write_json(status_path, {"status": "COMPLETE", "tasks_completed": len(results), "tasks_planned": len(order),
                                 "seconds": time.monotonic() - started, "contract": CONTRACT})
    except Exception as exc:
        write_json(status_path, {"status": "FAILED", "tasks_completed": len(results), "tasks_planned": len(order),
                                 "error": str(exc), "error_type": type(exc).__name__})
        raise


if __name__ == "__main__":
    main()
