"""Robot observation checks for uncertain visual grasp reports.

No simulator success, contact, grasp, or attachment predicates are read. The
same tracked keypoints used by ED and measured finger positions supply negative
grasp evidence. This module never declares task completion.
"""
import re
import numpy as np


def target_goal_geometry(runner):
    match = re.search(r"pick up (?:the )?(.+?) and place", runner.adapter.get_task_description().lower())
    if not match:
        return None
    name = match.group(1).replace(' ', '_')
    mapping = runner.keypoint_id_to_object
    target = [int(k) for k, v in mapping.items() if str(v).lower().startswith(name+'_')]
    goal = [int(k) for k, v in mapping.items() if 'basket' in str(v).lower()]
    if not target or len(goal) < 2:
        return None
    points = np.asarray(runner.stage_live_keypoints, dtype=float)
    if not np.isfinite(points[target+goal]).all():
        return None
    center = points[target].mean(0)
    low, high = points[goal, :2].min(0), points[goal, :2].max(0)
    # Expanded goal bounds make this conservative: a target near the rim does
    # not trigger blind reacquisition merely because the fingers are empty.
    outside = bool(np.any(center[:2] < low-.02) or np.any(center[:2] > high+.02))
    return dict(target_position=center.tolist(), goal_xy_low=low.tolist(), goal_xy_high=high.tolist(),
                target_definitely_outside_goal_xy=outside)


def check(state, *, step, width, distance, executed_gripper, geometry):
    """Require persistent observations; a command alone is never grasp truth."""
    conditions = {
        'empty_closed_fingers': (width is not None and width < .005 and executed_gripper is not None
                                 and executed_gripper > 0),
        'target_far_from_hand': distance is not None and distance > .16,
        'open_fingers_far_from_target': (width is not None and width > .075 and distance is not None
                                         and distance > .10),
    }
    evidence = []
    for name, present in conditions.items():
        key = 'robot_evidence_since_'+name
        if not present:
            state.pop(key, None)
            continue
        since = state.setdefault(key, step)
        minimum = 24 if name == 'target_far_from_hand' else 16
        if step-since >= minimum:
            evidence.append(name)
    outside = bool(geometry and geometry['target_definitely_outside_goal_xy'])
    return dict(no_grasp_reasons=evidence, no_grasp=bool(evidence),
                outside_goal=outside, geometry=geometry, width_m=width, distance_m=distance)


def filter_observation(observation, evidence):
    result = dict(observation)
    if evidence['no_grasp']:
        # Do not invent visibility, support, or location facts.
        result['grasp'] = 'not_held'
    return result


def apply_recovery(state, evidence, step):
    if not evidence['no_grasp']:
        return None
    state['visual_hold'] = False
    state['visual_hold_since'] = None
    state['contact_close_until'] = None
    if not evidence['outside_goal']:
        return 'negative_grasp_evidence_preserve_location_uncertainty'
    state.update(current_stage=1, guidance_requested=True, completion_evidence_count=0,
                 completion_evidence_step=None, completion_confirmed=False)
    # A physical empty closure needs reopening before another grasp can work.
    # Each recovery pulse is bounded; persistent evidence cannot extend it.
    last = state.get('robot_recovery_step')
    if last is None or step-last >= 64:
        state['robot_recovery_step'] = step
        state['contact_until'] = None
        state['contact_phase'] = 'approach'
        state['recovery_approach_since'] = step
        if 'empty_closed_fingers' in evidence['no_grasp_reasons']:
            state['empty_release_until'] = step+16
    return 'robot_observed_failed_grasp_reacquire'


def enforce_recovery_priority(state, evidence, step):
    """Resolve only an actual grace-vs-failure conflict after contact handoff.

    Leave all non-conflicting state and the physical reopening cooldown intact.
    This avoids restarting the approach clock on every far-from-target sample.
    """
    conflict=(evidence and evidence['no_grasp'] and evidence['outside_goal']
              and state.get('current_stage')==1 and state.get('contact_phase')=='contact_grace')
    if not conflict:
        return False
    state.update(contact_until=None,contact_phase='approach',recovery_approach_since=step,
                 guidance_requested=True)
    return True
