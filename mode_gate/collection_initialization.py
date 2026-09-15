"""Explicit, versioned initial-state revisions for offline demonstrations only.

Support-height preparation edits separate scratch MjData, never a live episode.
An authorized revision replaces in-memory catalog rows before reset; recorded
demonstrations still evolve exclusively through the existing OSC action path.
Original benchmark assets, held-out states and existing demonstrations stay intact.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path

import numpy as np


SCHEMA = "offline-demo-initialization-revision-v1"
VALIDATION_LIMITS = {
    "max_object_penetration_m": 0.002,
    "max_robot_object_penetration_m": 0.0005,
    "max_linear_velocity_m_s": 0.01,
    "max_angular_velocity_rad_s": 0.05,
    "max_robot_joint_velocity_rad_s": 0.02,
}
MAX_PRESERVED_REGION_XY_DRIFT_M = 0.005  # bounded normal settling, never a manual XY edit


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def state_sha256(state):
    return hashlib.sha256(np.asarray(state, dtype="<f8").tobytes()).hexdigest()


def _descendant(model, body, root):
    while body:
        if body == root:
            return True
        body = int(model.body_parentid[body])
    return body == root


def _parts(wrapper):
    import mujoco

    env = getattr(wrapper, "env", wrapper)
    model, data = wrapper.sim.model._model, wrapper.sim.data._data
    objects = {}
    for names in env.parsed_problem["objects"].values():
        for name in names:
            obj = env.get_object(name)
            joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, obj.joints[-1])
            if joint < 0 or int(model.jnt_type[joint]) != int(mujoco.mjtJoint.mjJNT_FREE):
                raise ValueError("initialization revision only supports free objects")
            body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, obj.root_body)
            if body < 0:
                raise ValueError("object body is not resolvable")
            geoms = [g for g in range(model.ngeom) if _descendant(model, int(model.geom_bodyid[g]), body)
                     and (model.geom_contype[g] or model.geom_conaffinity[g])]
            if not geoms:
                raise ValueError("object has no collision geometry")
            objects[name] = (joint, geoms)
    return env, model, data, objects


def _bounds(model, data, geom):
    rotation = data.geom_xmat[geom].reshape(3, 3)
    size = model.geom_size[geom]
    kind = int(model.geom_type[geom])
    if kind == 6:  # box
        extent = np.abs(rotation) @ size
    elif kind == 2:  # sphere
        extent = np.full(3, size[0])
    elif kind == 3:  # capsule
        extent = np.abs(rotation[:, 2]) * size[1] + size[0]
    elif kind == 4:  # ellipsoid
        extent = np.sqrt((rotation**2) @ (size**2))
    elif kind == 5:  # cylinder
        extent = np.abs(rotation[:, 2]) * size[1] + np.sqrt(np.maximum(0, 1 - rotation[:, 2]**2)) * size[0]
    else:
        raise ValueError(f"unsupported collision geometry {kind}; do not guess support height")
    return data.geom_xpos[geom] - extent, data.geom_xpos[geom] + extent


def _static_fixture_parts(env, model, name):
    import mujoco

    root = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
    obj = env.get_object(name)
    if root < 0 and obj is not None:
        root = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, obj.root_body)
    if root < 0:
        # Arena workspace names can differ from the actual MuJoCo body name.
        # BDDL region sites are attached to that body; resolve, never guess an alias.
        sites = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, key)
            for key, region in env.parsed_problem["regions"].items() if region.get("target") == name]
        roots = {int(model.site_bodyid[s]) for s in sites if s >= 0}
        if len(roots) == 1:
            root = roots.pop()
    if root <= 0 or any(_descendant(model, root, int(body)) for body in model.jnt_bodyid):
        raise ValueError("fixture support must be resolvable and static")
    geoms = {g for g in range(model.ngeom) if _descendant(model, int(model.geom_bodyid[g]), root)
        and not any(_descendant(model, int(model.geom_bodyid[g]), int(body)) for body in model.jnt_bodyid)
        and (model.geom_contype[g] or model.geom_conaffinity[g])}
    if not geoms:
        raise ValueError("fixture support has no static collision geometry")
    return root, geoms


def prepare_supported_state(wrapper, source_state, *, clearance_m=0.002, max_raise_m=0.10):
    """Return an un-settled candidate; caller must validate normal dynamics.

Only raise free objects above their BDDL-designated static support. Preserve
all XY positions, orientations, robot state and physics. No task-specific
object name, table height or successful goal pose is encoded here.
"""
    import mujoco

    if not 0 < clearance_m <= 0.01 or not clearance_m < max_raise_m <= 0.10:
        raise ValueError("support correction limits are outside the bounded preparation range")
    env, model, _, objects = _parts(wrapper)
    source = np.asarray(source_state, dtype=np.float64)
    if source.shape != (1 + model.nq + model.nv + model.na,) or not np.isfinite(source).all():
        raise ValueError("source state does not match the simulator topology")
    scratch = mujoco.MjData(model)
    scratch.time = source[0]
    scratch.qpos[:] = source[1:1 + model.nq]
    scratch.qvel[:] = source[1 + model.nq:1 + model.nq + model.nv]
    scratch.act[:] = source[1 + model.nq + model.nv:]
    mujoco.mj_forward(model, scratch)
    fixtures = {name for names in env.parsed_problem["fixtures"].values() for name in names}
    supports = {}
    for clause in env.parsed_problem["initial_state"]:
        if len(clause) == 3 and clause[0].lower() == "on" and clause[1] in objects:
            region = env.parsed_problem["regions"].get(clause[2], {})
            if region.get("target") in fixtures:
                supports[clause[1]] = region["target"]
    if set(supports) != set(objects):
        raise ValueError("all revised objects must have a disclosed static-support On predicate")
    corrections = []
    for name, (joint, geoms) in objects.items():
        bounds = [_bounds(model, scratch, g) for g in geoms]
        low = np.min([x[0] for x in bounds], axis=0)
        high = np.max([x[1] for x in bounds], axis=0)
        root = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, supports[name])
        if root < 0:
            raise ValueError("static support body is not resolvable")
        tops = []
        for geom in range(model.ngeom):
            if not _descendant(model, int(model.geom_bodyid[geom]), root):
                continue
            if not (model.geom_contype[geom] or model.geom_conaffinity[geom]):
                continue
            if int(model.geom_type[geom]) != 6:
                raise ValueError("support preparation requires explicit box collision geometry")
            lo, hi = _bounds(model, scratch, geom)
            if np.all(high[:2] > lo[:2]) and np.all(low[:2] < hi[:2]):
                tops.append(float(hi[2]))
        if not tops:
            raise ValueError("object has no collision support beneath its footprint")
        lift = max(0., max(tops) + clearance_m - float(low[2]))
        if lift > max_raise_m:
            raise ValueError("required support correction exceeds the preparation bound")
        if lift:
            address = int(model.jnt_qposadr[joint])
            scratch.qpos[address + 2] += lift
            corrections.append({"object": name, "raise_z_m": lift,
                "support_top_z_m": max(tops), "original_bottom_z_m": float(low[2])})
            mujoco.mj_forward(model, scratch)
    candidate = source.copy()
    candidate[1:1 + model.nq] = scratch.qpos
    return candidate, corrections


def prepare_object_stack_state(wrapper, source_state, *, clearance_m=0.002, max_vertical_shift_m=0.20):
    """Project object-on-object starts onto their prescribed support in scratch data.

    Unlike the raise-only static-support repair, this can lower a floating object.
    Only Z coordinates of a BDDL-declared stack and its free support chain may
    change; source XY, orientation, robot state and physics are preserved. The candidate is
    not a usable revision until a separate environment settles and validates it.
    """
    import mujoco

    if not 0 < clearance_m <= 0.01 or not clearance_m < max_vertical_shift_m <= 0.20:
        raise ValueError("stack correction limits are outside the bounded preparation range")
    env, model, _, objects = _parts(wrapper)
    source = np.asarray(source_state, dtype=np.float64)
    if source.shape != (1 + model.nq + model.nv + model.na,) or not np.isfinite(source).all():
        raise ValueError("source state does not match the simulator topology")
    scratch = mujoco.MjData(model)
    scratch.time = source[0]
    scratch.qpos[:] = source[1:1 + model.nq]
    scratch.qvel[:] = source[1 + model.nq:1 + model.nq + model.nv]
    scratch.act[:] = source[1 + model.nq + model.nv:]
    mujoco.mj_forward(model, scratch)
    fixtures = {name for names in env.parsed_problem["fixtures"].values() for name in names}
    supports = {}
    for clause in env.parsed_problem["initial_state"]:
        if len(clause) == 3 and clause[0].lower() == "on" and clause[1] in objects:
            support = clause[2] if clause[2] in objects else env.parsed_problem["regions"].get(clause[2], {}).get("target")
            if support not in objects and support not in fixtures:
                continue
            if clause[1] in supports:
                raise ValueError("stacked object has ambiguous supports")
            supports[clause[1]] = support
    selected = {name for name, support in supports.items() if support in objects}
    if not selected:
        raise ValueError("no object-on-object initial support is declared")
    pending_ancestors = list(selected)
    while pending_ancestors:
        name = pending_ancestors.pop()
        if name not in supports:
            raise ValueError("stack has no declared fixture support")
        support = supports[name]
        if support in objects and support not in selected:
            selected.add(support)
            pending_ancestors.append(support)
    corrections, pending = [], {name: supports[name] for name in sorted(selected)}
    while pending:
        ready = [name for name, support in pending.items() if support not in pending]
        if not ready:
            raise ValueError("cyclic object support is not a valid initialization")
        for name in ready:
            support = pending.pop(name)
            joint, geoms = objects[name]
            bounds = [_bounds(model, scratch, g) for g in geoms]
            low = np.min([x[0] for x in bounds], axis=0)
            high = np.max([x[1] for x in bounds], axis=0)
            tops = []
            if support in objects:
                support_geoms = objects[support][1]
            else:
                _, support_geoms = _static_fixture_parts(env, model, support)
            for geom in support_geoms:
                if int(model.geom_type[geom]) != 6:
                    raise ValueError("stack support requires explicit box collision geometry")
                lo, hi = _bounds(model, scratch, geom)
                if np.all(high[:2] > lo[:2]) and np.all(low[:2] < hi[:2]):
                    tops.append(float(hi[2]))
            if not tops:
                raise ValueError("stacked object has no support beneath its footprint")
            shift = max(tops) + clearance_m - float(low[2])
            if abs(shift) > max_vertical_shift_m:
                raise ValueError("required stack correction exceeds the preparation bound")
            scratch.qpos[int(model.jnt_qposadr[joint]) + 2] += shift
            corrections.append({"object": name, "support": support, "shift_z_m": shift,
                "support_top_z_m": max(tops), "original_bottom_z_m": float(low[2])})
            mujoco.mj_forward(model, scratch)
    candidate = source.copy()
    candidate[1:1 + model.nq] = scratch.qpos
    return candidate, corrections


def prepare_fixture_site_state(wrapper, source_state, *, site_offsets_xy,
                               clearance_m=0.002, footprint_margin_m=0.005,
                               max_translation_m=0.75):
    """Prepare selected starts on BDDL fixture sites in separate scratch data.

    Explicitly supplied offsets use the named site's local XY frame. Only the
    selected free-object XYZ coordinates may change; orientation, robot state,
    fixture geometry and all other source fields are preserved. This is an
    offline asset builder, never an action or live collection reset hook. Its
    output still requires normal settling and native initial-predicate checks.
    """
    import mujoco

    if (not site_offsets_xy or not 0 < clearance_m <= 0.01
            or not 0 < footprint_margin_m <= 0.02
            or not clearance_m < max_translation_m <= 0.75):
        raise ValueError("fixture-site correction limits are outside the bounded preparation range")
    env, model, _, objects = _parts(wrapper)
    source = np.asarray(source_state, dtype=np.float64)
    if source.shape != (1 + model.nq + model.nv + model.na,) or not np.isfinite(source).all():
        raise ValueError("source state does not match the simulator topology")
    if not set(site_offsets_xy) <= objects.keys():
        raise ValueError("fixture-site revision must select declared free objects")
    scratch = mujoco.MjData(model)
    scratch.time = source[0]
    scratch.qpos[:] = source[1:1 + model.nq]
    scratch.qvel[:] = source[1 + model.nq:1 + model.nq + model.nv]
    scratch.act[:] = source[1 + model.nq + model.nv:]
    mujoco.mj_forward(model, scratch)
    fixtures = {name for names in env.parsed_problem["fixtures"].values() for name in names}

    def projected_bounds(geoms, position, rotation):
        # Conservatively project every collision AABB into the support frame.
        # Unlike overlap of world AABBs, containment cannot accept a bowl beyond
        # the edge of a rotated cabinet. Unsupported geometry fails in _bounds.
        corners = []
        for geom in geoms:
            low, high = _bounds(model, scratch, geom)
            corners.extend([np.array([x, y, z]) for x in [low[0], high[0]]
                for y in [low[1], high[1]] for z in [low[2], high[2]]])
        local = (np.asarray(corners) - position) @ rotation
        return local.min(axis=0), local.max(axis=0)

    corrections = []
    for name, offset in site_offsets_xy.items():
        offset = np.asarray(offset, dtype=np.float64)
        if offset.shape != (2,) or not np.isfinite(offset).all() or np.max(np.abs(offset)) > 0.025:
            raise ValueError("fixture-site offset is invalid or exceeds 25 mm")
        clauses = [c for c in env.parsed_problem["initial_state"]
            if len(c) == 3 and c[0].lower() == "on" and c[1] == name]
        if len(clauses) != 1:
            raise ValueError("revised object must have one unambiguous initial On predicate")
        region_name = clauses[0][2]
        region = env.parsed_problem["regions"].get(region_name, {})
        if region.get("target") not in fixtures or region.get("ranges"):
            raise ValueError("fixture-site correction requires a named static-fixture region")
        root, support_geoms = _static_fixture_parts(env, model, region["target"])
        site = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, region_name)
        if (site < 0 or int(model.site_type[site]) != int(mujoco.mjtGeom.mjGEOM_BOX)
                or not _descendant(model, int(model.site_bodyid[site]), root)
                or any(_descendant(model, int(model.site_bodyid[site]), int(body)) for body in model.jnt_bodyid)):
            raise ValueError("fixture site must be a resolvable static box")
        rotation, position = scratch.site_xmat[site].reshape(3, 3), scratch.site_xpos[site].copy()
        if not np.allclose(rotation[:, 2], [0, 0, 1], atol=1e-8):
            raise ValueError("fixture site must be horizontal and upright")
        joint, geoms = objects[name]
        address = int(model.jnt_qposadr[joint])
        original = scratch.qpos[address:address + 3].copy()
        scratch.qpos[address:address + 2] = (position + rotation @ np.r_[offset, 0.])[:2]
        mujoco.mj_forward(model, scratch)
        low, high = projected_bounds(geoms, position, rotation)
        if (np.any(low[:2] < -model.site_size[site, :2] + footprint_margin_m)
                or np.any(high[:2] > model.site_size[site, :2] - footprint_margin_m)):
            raise ValueError("object collision footprint lies outside its prescribed site")
        supports = []
        for geom in sorted(support_geoms):
            if int(model.geom_type[geom]) != int(mujoco.mjtGeom.mjGEOM_BOX):
                raise ValueError("fixture-site support requires explicit box collision geometry")
            axes = scratch.geom_xmat[geom].reshape(3, 3)
            vertical = int(np.argmax(np.abs(axes[2])))
            if not np.isclose(abs(axes[2, vertical]), 1., atol=1e-8, rtol=0):
                continue  # Do not treat a tilted wall as a horizontal support.
            horizontal = [axis for axis in range(3) if axis != vertical]
            lo, hi = projected_bounds(geoms, scratch.geom_xpos[geom], axes)
            size = model.geom_size[geom, horizontal]
            if (np.all(lo[horizontal] >= -size + footprint_margin_m)
                    and np.all(hi[horizontal] <= size - footprint_margin_m)):
                top = float(scratch.geom_xpos[geom, 2] + model.geom_size[geom, vertical])
                supports.append((top, geom))
        if not supports:
            raise ValueError("object has no complete physical fixture support beneath its footprint")
        top, support_geom = max(supports)
        bottom = min(float(_bounds(model, scratch, geom)[0][2]) for geom in geoms)
        scratch.qpos[address + 2] += top + clearance_m - bottom
        translation = scratch.qpos[address:address + 3] - original
        if np.linalg.norm(translation) > max_translation_m:
            raise ValueError("required fixture-site translation exceeds the preparation bound")
        mujoco.mj_forward(model, scratch)
        corrections.append({"object": name, "predicate": clauses[0], "site": region_name,
            "site_position": position.tolist(), "site_rotation": rotation.tolist(),
            "site_half_size": model.site_size[site].tolist(), "site_local_offset_xy_m": offset.tolist(),
            "source_position": original.tolist(), "candidate_position": scratch.qpos[address:address + 3].tolist(),
            "translation_m": translation.tolist(), "support_top_z_m": top,
            "support_geom": mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, support_geom)})
    candidate = source.copy()
    candidate[1:1 + model.nq] = scratch.qpos
    return candidate, corrections


def _preserved_region_specs(wrapper, samples, *, source_state=None):
    """Allow only disclosed, unchanged out-of-region source XY on static fixtures.

    This is not a predicate override: native outcomes remain false in provenance.
    Object-on-object and articulated-site predicates can never be excluded.
    """
    env, model, data, objects = _parts(wrapper)
    fixtures = {n for names in env.parsed_problem["fixtures"].values() for n in names}
    declared = {tuple(c) for c in env.parsed_problem["initial_state"]}
    result = {}
    for sample in samples:
        clause = tuple(sample["predicate"])
        if clause not in declared or len(clause) != 3 or clause[0].lower() != "on" or clause[1] not in objects:
            raise ValueError("preserved sampling must name a declared free-object region predicate")
        key = " ".join(clause)
        if key in result:
            raise ValueError("duplicate preserved region sampling")
        region = env.parsed_problem["regions"].get(clause[2], {})
        if region.get("target") not in fixtures or not region.get("ranges"):
            raise ValueError("only static rectangular fixture regions may preserve source sampling")
        root, support_geoms = _static_fixture_parts(env, model, region["target"])
        if not np.allclose(data.xmat[root].reshape(3, 3), np.eye(3), atol=1e-8):
            raise ValueError("preserved sampling requires an axis-aligned static fixture")
        xy = np.asarray(sample["source_xy"], dtype=np.float64)
        ranges = np.asarray(region["ranges"], dtype=np.float64)
        if xy.shape != (2,) or not np.isfinite(xy).all() or ranges.ndim != 2 or ranges.shape[1] != 4 or not np.isfinite(ranges).all():
            raise ValueError("preserved sampling has invalid source XY or region bounds")
        local_xy = xy - data.xpos[root, :2]
        if np.any(np.all(local_xy >= ranges[:, :2], axis=1) & np.all(local_xy <= ranges[:, 2:], axis=1)):
            raise ValueError("source XY is inside its region; no sampling discrepancy may be waived")
        address = int(model.jnt_qposadr[objects[clause[1]][0]])
        if source_state is not None and not np.array_equal(xy, np.asarray(source_state)[1 + address:3 + address]):
            raise ValueError("preserved sampling source XY differs from original catalog")
        result[key] = {"address": address, "source_xy": xy, "object_geoms": set(objects[clause[1]][1]),
            "support_geoms": support_geoms, "support": region["target"]}
    return result


def validate_initial_state(wrapper, *, limits=None, preserved_region_sampling=()):
    """Read-only physical readiness check before recording/planning starts."""
    import mujoco

    limits = dict(VALIDATION_LIMITS if limits is None else limits)
    if limits != VALIDATION_LIMITS:
        raise ValueError("unknown initialization validation limits")
    env, model, data, objects = _parts(wrapper)
    if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
        raise ValueError("initialization contains non-finite simulator state")
    object_geoms = {g for _, geoms in objects.values() for g in geoms}
    robot_geoms = set()
    robot = wrapper.robots[0]
    for name in [*robot.robot_model.contact_geoms, *robot.gripper.contact_geoms]:
        index = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name)
        if index >= 0:
            robot_geoms.add(index)
    issues, min_distance = [], 0.
    for contact in data.contact[:data.ncon]:
        a, b = int(contact.geom1), int(contact.geom2)
        if a not in object_geoms and b not in object_geoms:
            continue
        distance = float(contact.dist)
        if not np.isfinite(distance):
            raise ValueError("initialization contains a non-finite contact distance")
        min_distance = min(min_distance, distance)
        bound = limits["max_robot_object_penetration_m"] if a in robot_geoms or b in robot_geoms else limits["max_object_penetration_m"]
        if distance < -bound:
            issues.append({"geom_ids": [a, b], "distance_m": distance})
    max_linear = max_angular = 0.
    for joint, _ in objects.values():
        address = int(model.jnt_dofadr[joint])
        max_linear = max(max_linear, float(np.linalg.norm(data.qvel[address:address + 3])))
        max_angular = max(max_angular, float(np.linalg.norm(data.qvel[address + 3:address + 6])))
    max_robot = float(np.max(np.abs(data.qvel[np.asarray(robot.controller.qvel_index)])))
    predicates = {" ".join(c): bool(env._eval_predicate(c)) for c in env.parsed_problem["initial_state"]}
    preserved = {}
    for key, spec in _preserved_region_specs(wrapper, preserved_region_sampling).items():
        xy = data.qpos[spec["address"]:spec["address"] + 2]
        drift = float(np.linalg.norm(xy - spec["source_xy"]))
        support_contact = False
        for contact in data.contact[:data.ncon]:
            a, b = int(contact.geom1), int(contact.geom2)
            if a in spec["support_geoms"] and b in spec["object_geoms"] and contact.frame[2] > .5:
                support_contact = True
            if b in spec["support_geoms"] and a in spec["object_geoms"] and contact.frame[2] < -.5:
                support_contact = True
        preserved[key] = {"native_predicate": predicates[key], "source_xy": spec["source_xy"].tolist(),
            "current_xy": xy.tolist(), "horizontal_drift_m": drift,
            "max_horizontal_drift_m": MAX_PRESERVED_REGION_XY_DRIFT_M,
            "physical_support_contact": support_contact, "support": spec["support"]}
        if drift > MAX_PRESERVED_REGION_XY_DRIFT_M or not support_contact:
            issues.append({"preserved_region_sampling_not_physically_ready": key})
    result = {"min_object_contact_distance_m": min_distance, "max_linear_velocity_m_s": max_linear,
        "max_angular_velocity_rad_s": max_angular, "max_robot_joint_velocity_rad_s": max_robot,
        "initial_predicates": predicates, "limits": limits, "task_already_successful": bool(wrapper.check_success())}
    if preserved:
        result["preserved_source_region_sampling"] = preserved
    if (issues or max_linear > limits["max_linear_velocity_m_s"]
            or max_angular > limits["max_angular_velocity_rad_s"]
            or max_robot > limits["max_robot_joint_velocity_rad_s"]
            or not all(value for key, value in predicates.items() if key not in preserved)
            or result["task_already_successful"]):
        raise ValueError("initialization is not physically ready: " + json.dumps({**result, "collisions": issues}))
    return result


@dataclass
class CollectionInitializationRevision:
    metadata: dict
    init_ids: set[str]
    preserved_regions: dict[str, list] = field(default_factory=dict)

    def validate(self, adapter, init_id):
        if str(init_id) not in self.init_ids:
            return None
        validation = validate_initial_state(adapter._get_current_robosuite_env(),
            preserved_region_sampling=self.preserved_regions.get(str(init_id), ()))
        return {**self.metadata, "init_state_id": str(init_id), "readiness": validation}


def activate_collection_revision(adapter, *, ticket, ticket_path, manifest, offline_root):
    """Bind a user-authorized ticket-local revision before any reset is called."""
    ticket_path = Path(ticket_path)
    revision_path = ticket_path.parent / "initialization_revision.json"
    if not revision_path.exists():
        return None
    if offline_root is None:
        raise ValueError("collection initialization revisions cannot alter online/evaluation environments")
    revision = json.loads(revision_path.read_text())
    expected = {"schema_version": SCHEMA, "requested_by": "user", "scope": "offline_demonstration_only",
        "ticket_id": ticket.ticket_id, "ticket_sha256": file_sha256(ticket_path),
        "task_id": ticket.task_id, "suite": ticket.suite, "perturbation_variant": ticket.perturbation_variant}
    if any(revision.get(k) != v for k, v in expected.items()):
        raise ValueError("initialization revision is not authorized for this ticket")
    if not isinstance(revision.get("revision"), str) or not revision["revision"].strip():
        raise ValueError("initialization revision must have an explicit version")
    matches = [t for t in manifest["tasks"] if (t["suite"], t["task_id"], t["perturbation_variant"])
               == (ticket.suite, ticket.task_id, ticket.perturbation_variant)]
    if len(matches) != 1:
        raise ValueError("initialization revision task is ambiguous")
    entries = revision["entries"]
    ids = {str(e["init_state_id"]) for e in entries}
    legal = {str(x) for x in matches[0]["splits"]["demo_online_pool"]}
    if not ids or len(ids) != len(entries) or not ids <= legal.intersection(map(str, ticket.init_state_ids)):
        raise ValueError("initialization revision must not touch held-out or unselected states")
    environment = adapter._env[adapter.current_task_idx]
    if environment.task_id != int(matches[0]["task_index"]):
        raise ValueError("initialization revision does not match the active simulator task")
    if (file_sha256(environment.init_states_file) != revision["source_catalog_sha256"]
            or file_sha256(environment.bddl_file_name) != revision["bddl_sha256"]):
        raise ValueError("initialization source assets changed")
    path = (ticket_path.parent / revision["states_file"]).resolve()
    if not path.is_relative_to(ticket_path.parent.resolve()) or file_sha256(path) != revision["states_sha256"]:
        raise ValueError("initialization revision state file is untrusted or changed")
    catalog = np.asarray(environment._init_states).copy()
    preserved_regions = {}
    with np.load(path, allow_pickle=False) as archive:
        for entry in entries:
            index = int(entry["init_state_id"])
            if not 0 <= index < len(catalog):
                raise ValueError("initialization revision row is out of range")
            state = np.asarray(archive[entry["state_key"]], dtype=np.float64)
            if (state.shape != catalog[index].shape or not np.isfinite(state).all()
                    or state_sha256(catalog[index]) != entry["source_state_sha256"]
                    or state_sha256(state) != entry["revised_state_sha256"]):
                raise ValueError("initialization catalog row or revision payload changed")
            samples = entry.get("preserved_region_sampling", [])
            if samples:
                _preserved_region_specs(adapter._get_current_robosuite_env(), samples, source_state=catalog[index])
                preserved_regions[str(index)] = samples
            catalog[index] = state
    # This is a private in-memory *catalog*, not sim.data or a global asset.
    # The unchanged normal reset path loads the selected row at attempt start.
    environment._init_states = catalog
    return CollectionInitializationRevision({"revision": revision["revision"],
        "scope": revision["scope"], "revision_manifest_sha256": file_sha256(revision_path),
        "states_sha256": revision["states_sha256"], "source_catalog_sha256": revision["source_catalog_sha256"],
        "bddl_sha256": revision["bddl_sha256"]}, ids, preserved_regions)
