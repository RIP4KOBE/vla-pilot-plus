"""Optional gripper release guard, using perceived goal geometry and visual facts.

This optional intervention must be explicitly enabled.
It preserves arm actions and delays an OPEN command outside the destination
after a visually confirmed grasp, with a bounded timeout and failed-grasp exit.
"""
import numpy as np


def observed_width(runner):
    qpos = runner.adapter.get_obs().get('robot0_gripper_qpos')
    if qpos is None:
        return None
    if hasattr(qpos, 'detach'):
        qpos = qpos.detach().cpu().numpy()
    qpos = np.asarray(qpos, dtype=float).reshape(-1)
    if len(qpos) != 2 or not np.isfinite(qpos).all():
        return None
    return float(np.abs(qpos).sum())


def apply_to_action(runner, state, chunk, index, step):
    from core.stage_contact_handoff import target_distance
    raw_action = chunk[0][index]
    raw_list = raw_action.detach().cpu().tolist() if hasattr(raw_action, 'detach') else raw_action.tolist()
    position = runner.adapter.get_ee_pose_world().position
    aligned, geometry = goal_alignment(position, runner.stage_live_keypoints, runner.keypoint_id_to_object)
    distance = target_distance(runner)
    command, reason = guard_command(state, float(raw_list[-1]), step=step, aligned=aligned,
                                     distance=distance, config=runner.config)
    payload = None
    payload_aligned = False
    if runner.config.get('payload_release_enabled', False):
        from core.stage_release_guard import payload_geometry, aligned_payload, apply
        payload = payload_geometry(runner)
        payload_aligned = aligned_payload(payload, runner.config.get('payload_release_margin_m', .005))
        command, reason = apply(state, float(raw_list[-1]), command, reason, step=step,
            width=observed_width(runner), distance=distance, geometry=payload, config=runner.config)
    proposed_command, proposed_reason = command, reason
    if not runner.config.get('grasp_action_guard_enabled', True):
        command, reason = float(raw_list[-1]), 'policy_gripper_passthrough'
    executed_list = list(raw_list); executed_list[-1] = command
    if command != raw_list[-1]:
        chunk = chunk.clone() if hasattr(chunk, 'clone') else np.array(chunk, copy=True)
        chunk[0][index][-1] = command
    runner._append_safety_event(dict(event='stage_grasp_guard_action', episode=state.get('episode_id'),
        task_id=state.get('task_id'), global_step=step, raw_action=raw_list, executed_action=executed_list,
        override=command != raw_list[-1], reason=reason, goal_aligned=aligned, goal_geometry=geometry,
        proposed_gripper_command=proposed_command, proposed_gripper_reason=proposed_reason,
        target_distance_m=distance, visual_hold=bool(state.get('visual_hold')),
        gripper_width_m=observed_width(runner), payload_geometry=payload,
        payload_aligned=payload_aligned, payload_release_until=state.get('payload_release_until'),
        semantic_stage=state.get('current_stage'), visual_hold_since=state.get('visual_hold_since'),
        physical_carry_hold_step=state.get('physical_carry_hold_step')))
    return chunk


def check_held_observation(state, observation, *, step, executed_gripper, width, distance):
    """Veto a held claim contradicted by sustained open fingers far from target.

    Uses robot proprioception and tracked keypoints only, never environment
    success/contact/attachment truth. Keep the raw VLM observation separately.
    """
    if executed_gripper is not None and executed_gripper < 0:
        if state.get('open_command_since') is None:
            state['open_command_since'] = step
    else:
        state['open_command_since'] = None
    result = dict(observation) if observation else None
    if result is None:
        return result, None
    since = state.get('open_command_since')
    contradiction = (since is not None and step-since >= 16 and width is not None and width >= .075
                     and distance is not None and distance > .10)
    reason = None
    if contradiction and result['grasp'] == 'held':
        result['grasp'] = 'not_held'
        reason = 'held_veto_open_fingers_far_from_target'
    # An unheld target remaining above the goal for two queries can be stranded
    # on the rim. Permit one settling interval before attempting reacquisition.
    if (result['target_visibility']=='clear' and result['grasp']=='not_held'
            and result['target_location']=='above_goal'):
        first = state.get('unheld_above_goal_since')
        if first is None:
            state['unheld_above_goal_since'] = step
        elif step-first >= 32:
            reason = 'unheld_above_goal_requires_reacquisition'
    else:
        state['unheld_above_goal_since'] = None
    return result, reason


def goal_alignment(position, keypoints, mapping, margin=.015):
    indices = [int(k) for k, name in mapping.items() if 'basket' in str(name).lower()]
    if not indices:
        return False, None
    points = np.asarray(keypoints, dtype=float)[indices]
    p = np.asarray(position, dtype=float)
    if not np.isfinite(points).all() or not np.isfinite(p).all():
        return False, None
    low, high = points[:, :2].min(0), points[:, :2].max(0)
    center = (low + high) / 2
    half_width = np.clip((high-low)/2-margin, .025, .075)
    offset = np.abs(p[:2]-center)
    return bool(np.all(offset <= half_width)), {'center_xy':center.tolist(), 'offset_xy':offset.tolist(),
                                                 'half_width_xy':half_width.tolist()}


def update_visual_hold(state, observation, step, *, accept_occluded_held=False):
    from core.stage_evidence import held_observation_is_usable
    if not observation:
        return
    if held_observation_is_usable(observation, accept_occluded_held):
        # Re-observation does not extend the same latch forever.
        if not state.get('visual_hold'):
            state['visual_hold_since'] = step
        state['visual_hold'] = True
    elif observation.get('target_visibility') == 'clear' and observation['grasp'] == 'not_held':
        state['visual_hold'] = False
        state['visual_hold_since'] = None


def guard_command(state, raw, *, step, aligned, distance, config):
    maximum = int(config.get('grasp_hold_max_steps', 160))
    debounce = int(config.get('grasp_contact_debounce_steps', 16))
    hold_since = state.get('visual_hold_since')
    if config.get('physical_carry_hold_enabled', False):
        from core.stage_carry_hold import expiry_anchor
        hold_since = expiry_anchor(state, config)
    if hold_since is not None and step-hold_since >= maximum:
        state['visual_hold'] = False
        state['visual_hold_since'] = None
        state['grasp_guard_expired'] = True
    if aligned:
        state['contact_close_until'] = None
        return raw, 'destination_aligned'
    release_until = state.get('empty_release_until')
    if release_until is not None and step < release_until:
        state['previous_raw_gripper'] = raw
        state['contact_close_until'] = None
        return -1., 'reopen_after_observed_empty_grasp'
    # A short command debounce is not treated as evidence of a successful grasp.
    previous = state.get('previous_raw_gripper')
    near = distance is not None and distance <= float(config.get('grasp_contact_distance_m', .10))
    if raw > 0 and (previous is None or previous <= 0) and near:
        state['contact_close_until'] = step+debounce
    state['previous_raw_gripper'] = raw
    if raw < 0 and state.get('visual_hold'):
        if config.get('physical_carry_hold_enabled', False):
            from core.stage_carry_hold import permit_hold
            if not permit_hold(state, step=step, config=config):
                return raw, 'unverified_visual_hold_preserve_policy_open'
        return 1., 'hold_visible_target_outside_destination'
    until = state.get('contact_close_until')
    if raw < 0 and until is not None and step < until:
        return 1., 'brief_contact_close_debounce'
    return raw, 'policy_command'
