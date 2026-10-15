"""Draft: permit and renew a hold only with persistent physical carry evidence.

This module cannot establish a grasp or declare completion. It only renews
an existing visual hold while the measured target is lifted, near nonempty
closed fingers. Physical failure/release evidence always takes precedence;
a conflicting visual negative is uncertain, never rewritten into held.
"""
import math


def observe(state, *, step, evidence, executed_gripper):
    geometry = (evidence or {}).get('geometry')
    position = geometry.get('target_position') if geometry else None
    width = (evidence or {}).get('width_m')
    distance = (evidence or {}).get('distance_m')
    values = [width, distance] + list(position or [])
    valid = (position is not None and len(position) == 3 and
             all(isinstance(x, (int, float)) and math.isfinite(x) for x in values))
    lift = None
    if valid:
        initial = state.setdefault('carry_target_initial_z', position[2])
        lift = position[2] - initial
    present = bool(valid and lift >= .03 and .005 < width < .075 and distance < .10
                   and executed_gripper is not None and executed_gripper > 0
                   and not evidence.get('no_grasp'))
    if present:
        since = state.setdefault('carry_evidence_since', step)
    else:
        state.pop('carry_evidence_since', None)
        since = None
    persistent = since is not None and step-since >= 8
    return dict(present=present, persistent=bool(persistent), target_lift_m=lift,
                evidence_since=since, step=step)


def active_release(state, step):
    return any(state.get(k) is not None and step < state[k]
               for k in ('empty_release_until', 'payload_release_until'))


def filter_observation(observation, state, cue):
    """Treat a visual-only contradiction as uncertain, never synthesize held.

    Requires prior Stage2 hold AND current persistent physical evidence. A
    commanded release or negative robot measurement makes cue.present false.
    """
    result = dict(observation)
    conflict = (result.get('grasp') == 'not_held' and state.get('current_stage') == 2
                and state.get('visual_hold') and cue['present'] and cue['persistent']
                and not active_release(state, cue['step']))
    if not conflict:
        return result, None
    result['grasp'] = 'unknown'
    state.pop('unheld_above_goal_since', None)
    return result, 'negative_visual_grasp_conflicts_with_measured_carry'


def finalize(state, cue):
    step = cue['step']
    eligible = (state.get('current_stage') == 2 and state.get('visual_hold') and
                not state.get('completion_confirmed') and
                not active_release(state, step))
    refreshed = bool(cue['present'] and cue['persistent'] and eligible)
    if refreshed:
        state['physical_carry_hold_step'] = step
    elif not state.get('visual_hold') or state.get('current_stage') != 2:
        state.pop('physical_carry_hold_step', None)
    return dict(cue, refreshed=refreshed, physical_carry_hold_step=state.get('physical_carry_hold_step'))


def update(state, *, step, evidence, executed_gripper):
    return finalize(state, observe(state, step=step, evidence=evidence, executed_gripper=executed_gripper))


def expiry_anchor(state, config):
    visual = state.get('visual_hold_since')
    if visual is None or not config.get('physical_carry_hold_enabled', False):
        return visual
    physical = state.get('physical_carry_hold_step')
    return max(visual, physical) if physical is not None else visual


def permit_hold(state, *, step, config):
    """A visual claim alone cannot suppress the policy's corrective OPEN."""
    if not config.get('physical_carry_hold_enabled', False):
        return True
    physical = state.get('physical_carry_hold_step')
    visual = state.get('visual_hold_since')
    return bool(state.get('visual_hold') and state.get('current_stage') == 2 and
                physical is not None and visual is not None and physical >= visual and
                0 <= step-physical < int(config.get('grasp_hold_max_steps', 80)))
