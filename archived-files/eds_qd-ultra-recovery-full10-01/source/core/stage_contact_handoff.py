"""Separate reaching guidance from grasp confirmation (prospective contact).

Reward progress is used only to hand control to the learned grasp policy. It
does not mean a grasp succeeded, a stage advanced, or the task completed.
"""
import math
import re


def target_distance(runner):
    import numpy as np
    task = runner.adapter.get_task_description().lower()
    match = re.search(r"pick up (?:the )?(.+?) and place", task)
    if not match:
        return None
    target = match.group(1).replace(" ", "_")
    keys = [int(k) for k, value in runner.keypoint_id_to_object.items()
            if str(value).lower().startswith(target + "_") or str(value).lower() == target]
    if not keys:
        return None
    kp = np.asarray(runner.stage_live_keypoints)
    position = np.asarray(runner.adapter.get_ee_pose_world().position)
    distance = float(np.linalg.norm(kp[keys] - position, axis=-1).min())
    return distance if math.isfinite(distance) else None


def apply_handoff(state, *, step, reward, was_guided, distance, observation, config):
    """Keep visual stage semantics but permit a bounded unguided grasp interval."""
    previous_phase = state.get("contact_phase", "approach")
    if state["current_stage"] == 0:
        state["contact_phase"] = "visually_complete"
        state["contact_until"] = None
        return
    if state["current_stage"] == 2:
        state["contact_phase"] = "transport_or_completion_check"
        state["contact_until"] = None
        return
    if previous_phase in {"transport_or_completion_check", "visually_complete"}:
        state["contact_phase"] = "approach"
        state["recovery_approach_since"] = step
    until = state.get("contact_until")
    if until is not None and step < until:
        state["contact_phase"] = "contact_grace"
        state["guidance_requested"] = False
        return
    if until is not None:
        state["contact_until"] = None
        state["contact_phase"] = "approach"
        state["recovery_approach_since"] = step
        state["guidance_requested"] = True
        return
    since = state.get("recovery_approach_since", 0)
    minimum = int(config.get("contact_min_approach_steps", 16))
    close = (bool(config.get("contact_proximity_handoff_enabled", True)) and
             distance is not None and distance <= float(config.get("contact_distance_m", .06)))
    progressed = was_guided and reward is not None and reward >= float(config.get("contact_reward_threshold", .8))
    if config.get("contact_require_measured_proximity", False):
        progressed = progressed and distance is not None and distance <= float(config.get("contact_reward_max_distance_m", .10))
    if step - since >= minimum and (close or progressed):
        state["contact_until"] = step + int(config.get("contact_grace_steps", 64))
        state["contact_phase"] = "contact_grace"
        state["contact_trigger"] = "current_keypoint_distance" if close else "fresh_guided_reward_progress"
        state["guidance_requested"] = False
    else:
        state["contact_phase"] = "approach"
        state["guidance_requested"] = True
