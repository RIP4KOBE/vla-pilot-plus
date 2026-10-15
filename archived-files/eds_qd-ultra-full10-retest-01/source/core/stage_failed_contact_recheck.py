"""Prospective recovery after an observed empty closure and verified reopening.

This cancels a stale contact grace, never relabels an observation, declares
completion, or changes a gripper command. It is disabled unless explicitly enabled.
"""
from copy import deepcopy
import math

KEY = 'failed_contact_recheck_pending'
REASON = 'confirmed_empty_grasp_reopened_outside_goal'
MIN_STEPS = 16
MAX_STEPS = 32


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def outside_geometry(evidence):
    geometry = (evidence or {}).get('geometry') or {}
    position = geometry.get('target_position')
    low, high = geometry.get('goal_xy_low'), geometry.get('goal_xy_high')
    if not (isinstance(position, (list, tuple)) and len(position) == 3
            and isinstance(low, (list, tuple)) and len(low) == 2
            and isinstance(high, (list, tuple)) and len(high) == 2
            and all(finite(v) for v in [*position, *low, *high])
            and all(a <= b for a, b in zip(low, high))):
        return False
    outside = any(position[i] < low[i] - .02 or position[i] > high[i] + .02 for i in range(2))
    return bool(outside and evidence.get('outside_goal') is True
                and geometry.get('target_definitely_outside_goal_xy') is True)


def supported_outside(observation):
    return bool(observation and observation.get('support') == 'supported'
                and observation.get('target_location') == 'outside_goal'
                and observation.get('target_visibility') in {'clear', 'occluded'})


def observe(state, *, observation, raw_observation, evidence, cue, step,
            executed_gripper, fresh=False, enabled=False):
    trace = dict(enabled=bool(enabled), armed=False, seed_step=None,
                 confirmed=False, confirmation=None)
    if not enabled:
        return trace
    until = state.get('contact_until')
    width = (evidence or {}).get('width_m')
    distance = (evidence or {}).get('distance_m')
    eligible = (state.get('current_stage') == 1 and not state.get('completion_confirmed')
                and not state.get('visual_hold') and state.get('contact_phase') == 'contact_grace'
                and isinstance(until, int) and step < until and outside_geometry(evidence)
                and finite(width) and 0 <= width <= .10 and finite(distance) and distance >= 0
                and finite(executed_gripper) and cue and cue.get('step') == step
                and cue.get('present') is False and cue.get('persistent') is False)
    contradicts = fresh and raw_observation and (
        raw_observation.get('grasp') == 'held' or raw_observation.get('support') == 'unsupported'
        or raw_observation.get('target_location') in {'inside_goal', 'above_goal'})
    if not eligible or contradicts:
        state.pop(KEY, None)
        return trace
    pending = state.get(KEY)
    if pending and (pending['until'] != until or not 0 <= step - pending['step'] <= MAX_STEPS):
        state.pop(KEY, None)
        pending = None
    aligned_reports = fresh and raw_observation == observation and supported_outside(raw_observation)
    if (aligned_reports and raw_observation.get('target_visibility') == 'clear'
            and raw_observation.get('grasp') == 'not_held' and width < .005 and executed_gripper > 0):
        pending = dict(step=step, until=until)
        state[KEY] = pending
    elif (pending and aligned_reports and raw_observation.get('grasp') in {'unknown', 'not_held'}
          and width > .075 and executed_gripper < 0 and MIN_STEPS <= step - pending['step'] <= MAX_STEPS):
        trace.update(confirmed=True, confirmation=dict(seed_step=pending['step'],
            contact_until=until, confirmation_step=step, age_steps=step - pending['step']))
        state.pop(KEY, None)
        state.update(contact_until=None, contact_phase='approach', recovery_approach_since=step,
                     contact_close_until=None, guidance_requested=True,
                     completion_evidence_count=0, completion_evidence_step=None)
        return trace
    trace.update(armed=pending is not None, seed_step=pending['step'] if pending else None)
    return trace


def audit_checks(events):
    """Replay decision bookkeeping only from recorded controller inputs.

    Actual ED execution, reward contract, source provenance, and raw actions
    have separate whole-run checks. Zero uses cannot count as a performance gain.
    """
    all_logged = bool(events)
    provenance = True
    final_gate = True
    states = {}
    for event in events:
        trace = event.get('failed_contact_recheck')
        all_logged &= isinstance(trace, dict) and trace.get('enabled') is True
        if not isinstance(trace, dict):
            provenance = False
            continue
        identity = (event.get('episode_id'), event.get('task_id'))
        state = states.setdefault(identity, {})
        confirmation = trace.get('confirmation') or {}
        # A confirmed row records the post-recovery state. Reconstruct only its
        # pre-recovery grace window; the seed must still exist from earlier rows.
        state.update(current_stage=event.get('stage_after'),
                     completion_confirmed=event.get('completion_confirmed'),
                     visual_hold=event.get('visual_hold'),
                     contact_phase='contact_grace' if trace.get('confirmed') else event.get('contact_phase'),
                     contact_until=confirmation.get('contact_until') if trace.get('confirmed') else event.get('contact_until'))
        expected = observe(state, observation=deepcopy(event.get('control_observation')),
            raw_observation=deepcopy(event.get('observation')),
            evidence=deepcopy(event.get('robot_evidence')), cue=deepcopy(event.get('physical_carry_evidence')),
            step=event.get('global_step'), executed_gripper=event.get('gripper_value_used'),
            fresh=event.get('query_status') == 'ok' and event.get('query_ok') is True, enabled=True)
        provenance &= trace == expected
        if trace.get('confirmed'):
            final_gate &= (event.get('stage_before') == event.get('stage_after') == 1
                and event.get('query_status') == 'ok' and event.get('guidance_after') is True
                and event.get('contact_phase') == 'approach' and event.get('contact_until') is None
                and event.get('completion_confirmed') is False
                and event.get('stage_decision_reason') == REASON
                and event.get('reward_reference_reset') is False
                and (event.get('reward_capability') or {}).get('available') is True)
    return dict(failed_contact_recheck_logged=bool(all_logged),
                failed_contact_recheck_temporal_provenance=bool(provenance),
                failed_contact_recheck_effective_gate=bool(final_gate))
