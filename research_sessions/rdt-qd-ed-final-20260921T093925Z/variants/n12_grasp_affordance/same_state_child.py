#!/usr/bin/env python3
"""GPU3-only, bounded task3 same-state diagnostic; never computes official SR."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import time

import numpy as np
from omegaconf import OmegaConf


CONTROLLER_FIELDS = ("goal_pos", "goal_ori", "ee_pos", "ee_ori_mat", "joint_pos", "joint_vel", "initial_joint")
RAW_FIELDS = ("agentview_image", "robot0_eye_in_hand_image", "robot0_eef_pos", "robot0_eef_quat",
              "robot0_gripper_qpos", "robot0_gripper_qvel", "robot0_joint_pos", "robot0_joint_vel")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def numeric(value):
    array = np.asarray(value)
    if array.dtype.kind not in "biufc" or not np.isfinite(array).all():
        raise ValueError("nonfinite or nonnumeric simulator record")
    return array.astype(np.float64).tolist()


def array_identity(value):
    array = np.ascontiguousarray(np.asarray(value))
    if array.dtype.kind not in "biufc" or not np.isfinite(array).all():
        raise ValueError("nonfinite or nonnumeric simulator array")
    return {"shape": list(array.shape), "dtype": str(array.dtype),
            "sha256": hashlib.sha256(array.tobytes()).hexdigest()}


def snapshot(env):
    control = env._env
    underlying = control.env
    sim = control.sim
    raw = underlying._get_observations()
    if not set(RAW_FIELDS) <= set(raw):
        raise ValueError("required raw observation missing")
    controller = control.robots[0].controller
    controller_record = {field: (None if getattr(controller, field, None) is None
                                 else array_identity(getattr(controller, field))) for field in CONTROLLER_FIELDS}
    object_pose = {}
    for name, body_id in sorted(underlying.obj_body_id.items()):
        object_pose[name] = {"xyz": numeric(sim.data.body_xpos[body_id]),
                             "wxyz": numeric(sim.data.body_xquat[body_id])}
    contacts = []
    for index in range(int(sim.data.ncon)):
        contact = sim.data.contact[index]
        contacts.append({"geom1": sim.model.geom_id2name(contact.geom1),
                         "geom2": sim.model.geom_id2name(contact.geom2),
                         "distance": float(contact.dist)})
    return {
        "sim_state": array_identity(control.get_sim_state()),
        "raw_observations": {field: array_identity(raw[field]) for field in RAW_FIELDS},
        "controller": controller_record,
        "timestep": int(underlying.timestep),
        "sim_time": float(sim.data.time),
        "success": bool(control.check_success()),
        "object_pose": object_pose,
        "eef_xyz": numeric(raw["robot0_eef_pos"]),
        "gripper_qpos": numeric(raw["robot0_gripper_qpos"]),
        "contacts": contacts,
    }


def sent_actions(rows, expected):
    if len(rows) != expected:
        raise ValueError(f"action count {len(rows)} != {expected}")
    actions = []
    for row in rows:
        action = np.asarray(row, dtype=np.float32)
        if action.shape != (7,) or not np.isfinite(action).all() or action[6] not in (-1, 1):
            raise ValueError("invalid recorded action")
        actions.append(action)
    return actions


def run_actions(env, actions, cap):
    trace = [snapshot(env)]
    for action in actions:
        if cap["transitions"] >= 96:
            raise RuntimeError("diagnostic transition cap reached")
        env._env.step(action)
        cap["transitions"] += 1
        trace.append(snapshot(env))
        if trace[-1]["success"]:
            break
    return trace


def same_trace(left, right):
    return len(left) == len(right) and all(a == b for a, b in zip(left, right))


def write_result(path, payload):
    with path.open("x") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: same_state_child.py PLAN")
    plan_path = Path(sys.argv[1]).resolve()
    plan = json.loads(plan_path.read_text())
    if plan["schema"] != "n12-task3-same-state-plan-v1" or plan["approved"] is not True:
        raise RuntimeError("diagnostic plan is not user-approved/released")
    if digest(Path(__file__)) != plan["child_sha256"]:
        raise RuntimeError("diagnostic child source changed")
    if digest(Path(plan["source_config"])) != plan["source_config_sha256"]:
        raise RuntimeError("source config changed")
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "3" or os.environ.get("MUJOCO_GL") != "egl":
        raise RuntimeError("only GPU3 EGL is authorized")
    if os.environ.get("MUJOCO_EGL_DEVICE_ID") != str(plan["egl_device_index"]):
        raise RuntimeError("EGL mapping differs from frozen GPU3 plan")
    workspace = Path(plan["study_worktree"])
    sys.path.insert(0, str(workspace))
    from core.env_adapters.libero_adapter import LiberoAdapter

    cfg = OmegaConf.load(plan["source_config"])
    if list(cfg.backend.libero.task_ids_filter) != [3] or cfg.backend.libero.num_steps_wait != 5:
        raise RuntimeError("task3 source condition changed")
    if plan["env_seed"] != 851784825 or plan["init_index"] != 0:
        raise RuntimeError("diagnostic identity changed")
    source_actions = sent_actions(plan["replay_actions"], 16)
    selected_actions = sent_actions(plan["selected_actions"], 8)
    alternate_actions = sent_actions(plan["alternative_actions"], 8)
    if all(np.array_equal(a, b) for a, b in zip(selected_actions, alternate_actions)):
        raise RuntimeError("no action contrast")
    output = Path(plan["output_dir"])
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    env_config = OmegaConf.to_container(cfg.backend.libero, resolve=True)
    adapter = LiberoAdapter(None, env_config, device="cuda")
    cap = {"resets": 0, "settling_steps": 0, "transitions": 0}
    payload = {"schema": "n12-task3-same-state-result-v1", "diagnostic_only": True,
               "official_task_success_rate": None, "attempt_id": plan["attempt_id"],
               "source_bundle_sha256": plan["source_bundle_sha256"], "task_id": 3,
               "seed": plan["env_seed"], "selected_index": plan["selected_index"],
               "alternative_index": plan["alternative_index"]}
    try:
        initial = None
        prefix_reference = None
        selected_reference = None
        branches = []
        for branch in ("selected_dry_a", "selected_dry_b", "selected", "alternative"):
            if cap["resets"] >= 4:
                raise RuntimeError("reset cap reached")
            env = adapter._env[0]
            env.reset(seed=plan["env_seed"])
            cap["resets"] += 1
            cap["settling_steps"] += int(env.num_steps_wait)
            if cap["settling_steps"] > 40:
                raise RuntimeError("settling cap reached")
            beginning = snapshot(env)
            if initial is None:
                initial = beginning
            elif beginning != initial:
                payload.update(status="INFEASIBLE_STATE_RESTORE", reason="initial reset differs")
                break
            prefix = run_actions(env, source_actions, cap)
            if len(prefix) != 17:
                payload.update(status="INFEASIBLE_STATE_RESTORE", reason="source prefix terminated early")
                break
            if prefix_reference is None:
                prefix_reference = prefix
            elif not same_trace(prefix, prefix_reference):
                payload.update(status="INFEASIBLE_STATE_RESTORE", reason="replayed source prefix differs")
                break
            historic = plan["historic_step15_observation"]
            if prefix[-1]["eef_xyz"] != historic["eef_xyz"] or prefix[-1]["gripper_qpos"] != historic["gripper_qpos"]:
                payload.update(status="INFEASIBLE_STATE_RESTORE", reason="replay differs from original step15 observation")
                break
            actions = alternate_actions if branch == "alternative" else selected_actions
            trace = run_actions(env, actions, cap)
            if branch == "selected_dry_a":
                selected_reference = trace
            elif branch in ("selected_dry_b", "selected") and not same_trace(trace, selected_reference):
                payload.update(status="INFEASIBLE_STATE_RESTORE", reason="selected dry/contrast branch differs")
                break
            branches.append({"name": branch, "trace": trace})
        else:
            payload["status"] = "COMPLETED_CONTRAST"
        payload.update(initial=initial, replay_prefix=prefix_reference, branches=branches,
                       selected_actions=plan["selected_actions"], alternative_actions=plan["alternative_actions"],
                       resource_counts=cap, diagnostic_wall_seconds=time.monotonic()-started)
        write_result(output / "result.json", payload)
    finally:
        for env in adapter._env:
            env.close()
    print(json.dumps({"result": str(output / "result.json"), "status": payload.get("status")}))


if __name__ == "__main__":
    main()
