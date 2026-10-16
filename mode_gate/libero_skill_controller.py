"""Deterministic, pose-feedback LIBERO skill execution with scratch-data IK checks.

All scene/kinematic queries are collection-only. Live simulator joint positions
are never assigned by this module: recorded seven-dimensional OSC actions are
the only source of physical motion.
"""
from __future__ import annotations

import numpy as np
from scipy.spatial.transform import Rotation

from .skill_collection import SkillControlFailure


def _wxyz(matrix):
    q = Rotation.from_matrix(matrix).as_quat()
    return q[[3, 0, 1, 2]].tolist()


def _matrix(quaternion):
    return Rotation.from_quat(np.asarray(quaternion)[[1, 2, 3, 0]]).as_matrix()


def _bounded_norm(vector, maximum):
    return vector * min(1.0, maximum / max(float(np.linalg.norm(vector)), 1e-12))


def damped_ik_delta(jacobian, cartesian_delta, *, damping, max_joint_step):
    jacobian = np.asarray(jacobian, dtype=float)
    delta = jacobian.T @ np.linalg.solve(
        jacobian @ jacobian.T + damping * damping * np.eye(6), cartesian_delta)
    if not np.isfinite(delta).all():
        raise SkillControlFailure("nonfinite inverse-kinematics solution")
    return _bounded_norm(delta, max_joint_step)


def inverse_action_scaling(delta, controller):
    low, high = np.asarray(controller.output_min), np.asarray(controller.output_max)
    input_low, input_high = np.asarray(controller.input_min), np.asarray(controller.input_max)
    if low.shape != (6,) or high.shape != (6,) or np.any(high <= low):
        raise SkillControlFailure("unsupported OSC scaling; refusing guessed action units")
    return np.clip((delta - low) / (high - low) * (input_high - input_low) + input_low,
                   input_low, input_high)


class LiberoSkillController:
    def __init__(self, adapter, config):
        import mujoco

        self.mujoco, self.adapter, self.config = mujoco, adapter, config
        self.wrapper = adapter._get_current_robosuite_env()
        self.env = getattr(self.wrapper, "env", self.wrapper)
        self.sim = self.wrapper.sim
        self.model = self.sim.model._model
        self.robot = self.wrapper.robots[0]
        self.osc = self.robot.controller
        if not getattr(self.osc, "use_delta", False) or int(self.osc.control_dim) != 6:
            raise SkillControlFailure("skill collector requires six-dimensional delta OSC")
        self.scratch = mujoco.MjData(self.model)
        self.qpos_indices = np.asarray(self.osc.qpos_index, dtype=int)
        self.qvel_indices = np.asarray(self.osc.qvel_index, dtype=int)
        self.robot_geoms = self._geom_ids(self.robot.robot_model.contact_geoms)
        self.finger_geoms = self._geom_ids(self.robot.gripper.contact_geoms)
        self.robot_geoms |= self.finger_geoms
        self.object_geoms = {}
        self.object_bodies = {}
        self.references = {}
        self.joints = {}
        self._index_scene()
        self.held_object = None

    def _geom_ids(self, names):
        return {int(self.sim.model.geom_name2id(name)) for name in names}

    def _body_descendant(self, child, parent):
        while child:
            if child == parent:
                return True
            child = int(self.model.body_parentid[child])
        return child == parent

    def _index_scene(self):
        problem = self.env.parsed_problem
        objects = [name for group in (problem.get("objects", {}), problem.get("fixtures", {}))
                   for names in group.values() for name in names]
        self.objects = {}
        self.unresolved_static_fixtures = []
        self.references["ee"] = ("site", int(self.sim.model.site_name2id(self.osc.eef_name)))
        for name in objects:
            obj = self.env.get_object(name)
            if obj is None:
                # LIBERO represents its arena table as a BDDL fixture but not
                # as a MujocoObject. Resolve its body through the arena API.
                arena = getattr(self.env.model, "mujoco_arena", None)
                bodies = [value for key, value in vars(arena).items()
                          if key.endswith("_body") and hasattr(value, "get") and value.get("name")] if arena else []
                matching = [value for value in bodies if value.get("name") == name]
                resolved = matching or (bodies if len(bodies) == 1 else [])
                if len(resolved) != 1:
                    self.unresolved_static_fixtures.append(name)
                    continue
                root_name = resolved[0].get("name")
            else:
                root_name = obj.root_body
            body = int(self.sim.model.body_name2id(root_name))
            self.object_bodies[name] = body
            geoms = {i for i in range(self.model.ngeom)
                     if self._body_descendant(int(self.model.geom_bodyid[i]), body)}
            self.object_geoms[name] = geoms
            self.objects[name] = {"body": root_name, "reference": f"body:{root_name}",
                "contact_geoms": [self.sim.model.geom_id2name(i) for i in sorted(geoms)],
                "geometry": [{"name": self.sim.model.geom_id2name(i),
                    "position": self.sim.data.geom_xpos[i].tolist(),
                    "quaternion_wxyz": _wxyz(self.sim.data.geom_xmat[i].reshape(3, 3)),
                    "size": self.model.geom_size[i].tolist(), "type": int(self.model.geom_type[i])}
                    for i in sorted(geoms)]}
            for i in range(self.model.nbody):
                if self._body_descendant(i, body):
                    self.references[f"body:{self.sim.model.body_id2name(i)}"] = ("body", i)
            for i in range(self.model.nsite):
                if self._body_descendant(int(self.model.site_bodyid[i]), body):
                    self.references[f"site:{self.sim.model.site_id2name(i)}"] = ("site", i)
            for i in range(self.model.njnt):
                if self._body_descendant(int(self.model.jnt_bodyid[i]), body) and int(self.model.jnt_type[i]) in {2, 3}:
                    self.joints[self.sim.model.joint_id2name(i)] = (i, name)
        # BDDL target regions may be sites on the table rather than on objects.
        for name, region in problem.get("regions", {}).items():
            candidates = [name, f"{region.get('target', '')}_{name}"]
            for candidate in candidates:
                try:
                    site = int(self.sim.model.site_name2id(candidate))
                except ValueError:
                    continue
                self.references[f"site:{candidate}"] = ("site", site)

    def _pose(self, reference):
        kind, index = self.references[reference]
        data = self.sim.data._data
        if kind == "body":
            return data.xpos[index].copy(), data.xmat[index].reshape(3, 3).copy()
        return data.site_xpos[index].copy(), data.site_xmat[index].reshape(3, 3).copy()

    def predicate(self, clause):
        return bool(self.env._eval_predicate(list(clause)))

    def scene(self):
        references = {}
        for name in self.references:
            pos, rotation = self._pose(name)
            references[name] = {"position": pos.tolist(), "quaternion_wxyz": _wxyz(rotation)}
            kind, idx = self.references[name]
            if kind == "site":
                references[name]["half_size"] = self.model.site_size[idx].tolist()
        joints = {}
        for name, (index, obj) in self.joints.items():
            joints[name] = {"object": obj, "type": "hinge" if int(self.model.jnt_type[index]) == 3 else "slide",
                "qpos": self._joint_position(index), "range": self.model.jnt_range[index].tolist(),
                "axis_world": self.sim.data._data.xaxis[index].tolist(),
                "anchor_world": self.sim.data._data.xanchor[index].tolist()}
        clauses = self.env.parsed_problem["goal_state"] + self.env.parsed_problem.get("initial_state", [])
        available = []
        for clause in clauses:
            if clause[0].lower() not in {"on", "in", "open", "close", "turnon", "turnoff"}:
                continue
            if list(clause) not in available:
                available.append(list(clause))
            if clause[0].lower() in {"open", "close", "turnon", "turnoff"}:
                inverse = {"open": "close", "close": "open", "turnon": "turnoff", "turnoff": "turnon"}[clause[0].lower()]
                inverse_clause = [inverse, *clause[1:]]
                if inverse_clause not in available:
                    available.append(inverse_clause)
        gripper_geometry = [{"name": self.sim.model.geom_id2name(idx),
            "position_world_m": self.sim.data.geom_xpos[idx].tolist(),
            "quaternion_wxyz": _wxyz(self.sim.data.geom_xmat[idx].reshape(3, 3)),
            "size": self.model.geom_size[idx].tolist(), "type": int(self.model.geom_type[idx])}
            for idx in sorted(self.finger_geoms)]
        return {"schema_version": "libero-skill-scene-v1", "instruction": self.adapter.get_task_description(),
            "references": references, "objects": self.objects, "joints": joints,
            "unresolved_static_fixtures": self.unresolved_static_fixtures,
            "goal_predicates": self.env.parsed_problem["goal_state"], "available_predicates": available,
            "predicate_values": {" ".join(value): self.predicate(value) for value in available},
            "robot_joint_positions": self.adapter.get_joint_positions().tolist(),
            "robot_joint_names": [self.sim.model.joint_id2name(int(self.model.dof_jntid[idx])) for idx in self.qvel_indices],
            "robot_joint_ranges": [self.model.jnt_range[int(self.model.dof_jntid[idx])].tolist() for idx in self.qvel_indices],
            "gripper_contact_geometry": gripper_geometry,
            "gripper_contact_groups": self.robot.gripper.important_geoms,
            "task_success": bool(self.wrapper.check_success()), "pose_input_role": "privileged_collection_only"}

    def _joint_position(self, index):
        return float(self.sim.data.qpos[int(self.model.jnt_qposadr[index])])

    def _contacts(self, data, allowed_objects):
        allowed = set().union(*(self.object_geoms[name] for name in allowed_objects)) if allowed_objects else set()
        held = self.object_geoms.get(self.held_object, set())
        issues = []
        for contact in data.contact[:data.ncon]:
            if contact.dist >= -self.config.collision_penetration_m:
                continue
            a, b = int(contact.geom1), int(contact.geom2)
            if a not in self.robot_geoms and b not in self.robot_geoms and a not in held and b not in held:
                continue
            if ((a in self.finger_geoms and b in allowed | held)
                    or (b in self.finger_geoms and a in allowed | held)
                    or (a in held and b in allowed) or (b in held and a in allowed)):
                continue
            issues.append([self.sim.model.geom_id2name(a), self.sim.model.geom_id2name(b), float(contact.dist)])
        return issues

    def _check_ik_motion(self, delta, allowed):
        self.osc.update(force=True)
        dq = damped_ik_delta(self.osc.J_full, delta, damping=self.config.ik_damping,
                            max_joint_step=self.config.max_joint_step_rad)
        q = self.sim.data.qpos[self.qpos_indices].copy()
        for i, velocity_index in enumerate(self.qvel_indices):
            joint = int(self.model.dof_jntid[velocity_index])
            if self.model.jnt_limited[joint] and not self.model.jnt_range[joint, 0] <= q[i] + dq[i] <= self.model.jnt_range[joint, 1]:
                raise SkillControlFailure(f"IK preview reaches a robot joint limit: "
                    f"{self.sim.model.joint_id2name(joint)} current={q[i]:.6f}, "
                    f"proposed={q[i] + dq[i]:.6f}, range={self.model.jnt_range[joint].tolist()}")
        # Forward kinematics/contact prediction on separate MjData. This does
        # not assign qpos, free joints, or success state in the live simulator.
        self.scratch.qpos[:] = self.sim.data.qpos
        self.scratch.qvel[:] = self.sim.data.qvel
        self.scratch.mocap_pos[:] = self.sim.data.mocap_pos
        self.scratch.mocap_quat[:] = self.sim.data.mocap_quat
        for fraction in (0.33, 0.67, 1.0):
            self.scratch.qpos[self.qpos_indices] = q + fraction * dq
            self.mujoco.mj_forward(self.model, self.scratch)
            issues = self._contacts(self.scratch, allowed)
            if issues:
                raise SkillControlFailure(f"predicted forbidden collision: {issues[:3]}")

    def _servo(self, target_pos, target_rot, gripper, allowed):
        pos, rotation = self._pose("ee")
        translation = _bounded_norm(target_pos - pos, self.config.max_cartesian_step_m)
        angle = _bounded_norm(Rotation.from_matrix(target_rot @ rotation.T).as_rotvec(),
                              self.config.max_rotation_step_rad)
        delta = np.concatenate((translation, angle))
        self._check_ik_motion(delta, allowed)
        action = np.concatenate((inverse_action_scaling(delta, self.osc), [gripper])).astype(np.float32)
        return action

    def _grasped(self, name):
        return bool(self.env._check_grasp(self.robot.gripper, self.env.get_object(name)))

    def execute(self, plan, session):
        start_steps = len(session.writer.actions)
        for index, skill in enumerate(plan.skills):
            if session._task_success():
                return
            position, rotation = self._pose("ee")
            target_pos, target_rot = position.copy(), rotation.copy()
            if skill.operation == "move":
                ref_pos, ref_rot = self._pose(skill.reference)
                target_pos = ref_pos + ref_rot @ np.asarray(skill.offset_m)
                if skill.orientation_wxyz is not None:
                    target_rot = _matrix(skill.orientation_wxyz)
            gripper = session.gripper if skill.gripper == "keep" else (1.0 if skill.gripper == "close" else -1.0)
            if gripper < 0:
                self.held_object = None
            if skill.operation == "articulate":
                joint_index, _ = self.joints[skill.joint]
                joint_start = self._joint_position(joint_index)
                axis = self.sim.data._data.xaxis[joint_index].copy()
                anchor = self.sim.data._data.xanchor[joint_index].copy()
                excursion = float(skill.joint_target) - joint_start
            best_error, stagnant = float("inf"), 0
            for step in range(skill.max_steps):
                if len(session.writer.actions) - start_steps >= self.config.max_attempt_steps:
                    raise SkillControlFailure("automatic attempt reached its policy-step bound")
                if skill.until_predicate is not None and self.predicate(skill.until_predicate):
                    break
                if skill.operation == "articulate":
                    current = self._joint_position(joint_index)
                    if abs(float(skill.joint_target) - current) < 0.015:
                        break
                    # Track the joint through a short physical arc/slide. The
                    # target never jumps directly to a distant final pose.
                    ahead = np.clip(current - joint_start + np.sign(excursion) *
                                    (0.07 if int(self.model.jnt_type[joint_index]) == 3 else 0.008),
                                    min(0., excursion), max(0., excursion))
                    if int(self.model.jnt_type[joint_index]) == 3:
                        turn = Rotation.from_rotvec(axis * ahead).as_matrix()
                        target_pos, target_rot = anchor + turn @ (position - anchor), turn @ rotation
                    else:
                        target_pos = position + axis * ahead
                    error = abs(float(skill.joint_target) - current)
                else:
                    pos, rot = self._pose("ee")
                    pos_error = float(np.linalg.norm(target_pos - pos))
                    rot_error = float(np.linalg.norm(Rotation.from_matrix(target_rot @ rot.T).as_rotvec()))
                    error = pos_error + 0.05 * rot_error
                    if skill.operation == "move" and pos_error <= self.config.position_tolerance_m and rot_error <= self.config.orientation_tolerance_rad:
                        if skill.grasp_object is None or self._grasped(skill.grasp_object):
                            break
                    if skill.operation == "gripper" and step >= 12:
                        if skill.grasp_object is None or self._grasped(skill.grasp_object):
                            if skill.grasp_object:
                                self.held_object = skill.grasp_object
                            break
                if skill.operation in {"move", "articulate"}:
                    stagnant = 0 if error < best_error - 0.0005 else stagnant + 1
                    best_error = min(best_error, error)
                    if stagnant >= self.config.stagnation_steps:
                        raise SkillControlFailure(f"skill {index + 1} stalled before completion")
                action = self._servo(target_pos, target_rot, gripper, skill.allow_contact_objects)
                session.execute_action(action)
                yield {"index": index + 1, "description_zh": skill.description_zh, "step": step + 1}
                if session._task_success():
                    return
                if session.terminal_state == "invalid":
                    raise SkillControlFailure("LIBERO terminal/timeout without success")
                issues = self._contacts(self.sim.data._data, skill.allow_contact_objects)
                if issues:
                    raise SkillControlFailure(f"observed forbidden collision: {issues[:3]}")
                if self.held_object and not self._grasped(self.held_object):
                    raise SkillControlFailure(f"lost grasp of {self.held_object}")
            else:
                raise SkillControlFailure(f"skill {index + 1} reached its step limit")
        if not session._task_success():
            raise SkillControlFailure("skill sequence ended without LIBERO-PRO success")
