"""Physical carry evidence, bounded holds and sensor-fusion audit."""


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


MINIMUM_CARRY_STEPS = 16
REASON = 'visually_suspended_target_with_persistent_carry'


def finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def establish_hold(state, observation, raw_observation, cue, evidence, *,
                   step, executed_gripper, enabled=False):
    """Use fresh sensor agreement without converting unknown into a held label.

    Call only after a successful fresh query and ordinary semantic inference.
    Existing robot recovery, release, reward gating, and raw actions retain
    their precedence. Repeated observations cannot restart the same latch.
    """
    if (not enabled or state.get('current_stage') != 1 or
            state.get('completion_confirmed') or state.get('visual_hold') or
            active_release(state, step)):
        return False
    for value in (raw_observation, observation):
        if (not value or value.get('grasp') != 'unknown' or
                value.get('support') != 'unsupported' or
                value.get('target_visibility') not in {'clear', 'occluded'} or
                value.get('target_location') not in {'outside_goal', 'above_goal', 'inside_goal'}):
            return False
    if not cue or not evidence or evidence.get('no_grasp') is not False:
        return False
    position = (evidence.get('geometry') or {}).get('target_position')
    if not isinstance(position, (list, tuple)) or len(position) != 3 or not all(finite(v) for v in position):
        return False
    since = cue.get('evidence_since')
    if (cue.get('present') is not True or cue.get('persistent') is not True or
            cue.get('step') != step or not isinstance(since, int) or
            since < 0 or step - since < MINIMUM_CARRY_STEPS):
        return False
    width, distance, lift = evidence.get('width_m'), evidence.get('distance_m'), cue.get('target_lift_m')
    if (not all(finite(v) for v in (width, distance, lift, executed_gripper)) or
            not .005 < width < .075 or not 0 <= distance < .10 or
            lift < .03 or executed_gripper <= 0):
        return False
    state.update(current_stage=2, guidance_requested=True, visual_hold=True,
                 visual_hold_since=step, completion_evidence_count=0,
                 completion_evidence_step=None, completion_confirmed=False)
    return True


def valid_establishment_event(event):
    """Audit logged evidence independently of the mutable controller state."""
    if not (
        event.get('fused_hold_established') is True and event.get('fused_hold_enabled') is True
        and event.get('query_status') == 'ok' and event.get('query_ok') is True
        and event.get('stage_before') == 1 and event.get('stage_after') == 2
        and event.get('visual_hold') is True and event.get('guidance_after') is False
        and event.get('stage_decision_reason') == REASON
        and event.get('fused_hold_source') == 'visual_suspension_and_persistent_robot_carry'
        and event.get('fused_hold_release_active') is False
        and event.get('completion_confirmed') is False
        and event.get('completion_evidence_count') == 0
        and event.get('accepted_occluded_held') is False
    ):
        return False
    observation = event.get('observation') or {}
    if (observation != event.get('control_observation') or observation.get('grasp') != 'unknown'
            or observation.get('support') != 'unsupported'
            or observation.get('target_visibility') not in {'clear', 'occluded'}
            or observation.get('target_location') not in {'inside_goal', 'above_goal', 'outside_goal'}):
        return False
    cue, evidence = event.get('physical_carry_evidence') or {}, event.get('robot_evidence') or {}
    step, since = event.get('global_step'), cue.get('evidence_since')
    if (not isinstance(step, int) or not isinstance(since, int) or since < 0
            or step - since < MINIMUM_CARRY_STEPS or cue.get('step') != step
            or cue.get('present') is not True or cue.get('persistent') is not True
            or cue.get('refreshed') is not True or cue.get('physical_carry_hold_step') != step
            or evidence.get('no_grasp') is not False):
        return False
    width, distance, lift, command = (event.get('gripper_width_m'), event.get('target_distance_m'),
                                     cue.get('target_lift_m'), event.get('gripper_value_used'))
    position = (evidence.get('geometry') or {}).get('target_position')
    return bool(
        all(finite(v) for v in (width, distance, lift, command))
        and .005 < width < .075 and 0 <= distance < .10 and lift >= .03 and command > 0
        and evidence.get('width_m') == width and evidence.get('distance_m') == distance
        and isinstance(position, (list, tuple)) and len(position) == 3 and all(finite(v) for v in position)
        and (event.get('reward_capability') or {}).get('available') is False
    )


def audit_checks(events):
    """Zero uses remain valid evidence of a no-effect cohort, not grounds to retry."""
    established = [e for e in events if e.get('fused_hold_established') is True]
    return {
        'fused_hold_policy_logged': bool(events) and all(
            e.get('fused_hold_enabled') is True and type(e.get('fused_hold_established')) is bool for e in events),
        'fused_hold_establishment_supported_by_fresh_evidence': all(valid_establishment_event(e) for e in established),
        'fused_hold_provenance_not_claimed_without_establishment': all(
            e.get('fused_hold_source') is None for e in events if not e.get('fused_hold_established')),
    }
