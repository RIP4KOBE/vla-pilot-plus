"""Passive LIBERO physics witness; never returned to the policy or Stage model."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def _finite_list(value):
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    array = np.asarray(value)
    if array.dtype.kind not in "biufc" or not np.isfinite(array).all():
        raise ValueError("passive physics witness contains nonfinite or nonnumeric values")
    return array.astype(np.float64).tolist()


def physics_snapshot(adapter, tracker, *, global_step, action, stage, guided, success):
    """Copy only values from the just-completed real environment step."""
    worlds = getattr(adapter, "_env", None)
    if not isinstance(worlds, (tuple, list)) or len(worlds) != 1:
        raise ValueError("passive physics requires exactly one LIBERO environment")
    control = worlds[0]._env
    underlying = control.env
    sim = control.sim
    body_ids = underlying.obj_body_id
    if not isinstance(body_ids, dict) or not body_ids:
        raise ValueError("passive physics object-body mapping absent")
    objects = {}
    for name, body_id in sorted(body_ids.items()):
        objects[str(name)] = {
            "xyz": _finite_list(sim.data.body_xpos[body_id]),
            "wxyz": _finite_list(sim.data.body_xquat[body_id]),
        }
    contacts = []
    for index in range(int(sim.data.ncon)):
        contact = sim.data.contact[index]
        geoms = (int(contact.geom1), int(contact.geom2))
        body_pair = (int(sim.model.geom_bodyid[geoms[0]]), int(sim.model.geom_bodyid[geoms[1]]))
        contacts.append({
            "geom_names": [sim.model.geom_id2name(geom) for geom in geoms],
            "body_names": [sim.model.body_id2name(body) for body in body_pair],
            "distance": float(contact.dist),
        })
    get_target = getattr(tracker, "get_object_name_by_keypoint", None)
    target_name = get_target(0) if callable(get_target) else None
    get_snapshot = getattr(tracker, "execution_feedback_tracking_snapshot", None)
    tracking = get_snapshot() if callable(get_snapshot) else None
    target_state = tracking.get("targets", {}).get(0, tracking.get("targets", {}).get("0")) if isinstance(tracking, dict) else None
    target_valid = target_state == {"valid": True, "status": "tracked"}
    sent_action = action.detach().cpu().numpy() if hasattr(action, "detach") else np.asarray(action)
    if tuple(sent_action.shape) != (7,):
        raise ValueError("passive physics sent action must be 7D")
    return {
        "schema": "n17-passive-physics-step-v1",
        "global_step": int(global_step),
        "stage": int(stage),
        "guided": bool(guided),
        "sent_action": _finite_list(sent_action),
        "sim_time": float(sim.data.time),
        "object_bodies": objects,
        "contacts_at_action_boundary": contacts,
        "target_object_name": None if target_name is None else str(target_name),
        "target_tracker_valid": bool(target_valid),
        "target_tracker_instance_id": tracking.get("instance_id") if target_valid else None,
        "target_tracker_generation": tracking.get("generation") if target_valid else None,
        "success": bool(success),
    }


class PassivePhysicsTrace:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raise FileExistsError(self.path)
        self.path.touch()
        self.count = 0

    def record(self, adapter, tracker, *, global_step, action, stage, guided, success):
        if int(global_step) != self.count:
            raise ValueError("passive physics step index gap")
        row = physics_snapshot(adapter, tracker, global_step=global_step,
                               action=action, stage=stage, guided=guided, success=success)
        with self.path.open("a", encoding="utf-8") as stream:
            json.dump(row, stream, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
        self.count += 1
