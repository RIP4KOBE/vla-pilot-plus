"""Opt-in two-stage pick/place controller; no simulator success labels as inputs.

The VLM reports observations, never a control command. Completion remains a
revocable visual hypothesis, not the environment's success criterion.
"""
import json
import math
import random

VERSION = "evidence_v1"
FORMAT = "stage_observation_v1"
ENUMS = {
    "target_visibility": {"clear", "occluded", "unknown"},
    "target_location": {"outside_goal", "inside_goal", "above_goal", "unknown"},
    "grasp": {"held", "not_held", "unknown"},
    "support": {"supported", "unsupported", "unknown"},
}


def parse_observation(text):
    """Strict JSON schema after lossless outer presentation decoding."""
    from core.stage_observation_json import unwrap
    text, _ = unwrap(text)
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate observation key")
            result[key] = value
        return result
    value = json.loads(text, object_pairs_hook=unique_pairs)
    if not isinstance(value, dict) or set(value) != set(ENUMS) | {"evidence"}:
        raise ValueError("observation must contain exactly the five specified fields")
    for key, choices in ENUMS.items():
        if not isinstance(value[key], str) or value[key] not in choices:
            raise ValueError("invalid observation field: " + key)
    if not isinstance(value["evidence"], str) or not value["evidence"].strip():
        raise ValueError("visual evidence is required")
    if len(value["evidence"]) > 2400:
        raise ValueError("visual evidence is too long")
    return value


def settings(config):
    values = {
        "minimum_gap": int(config.get("stage_min_query_gap_steps", 16)),
        "recheck_steps": int(config.get("stage_recheck_steps", 32)),
        "confirmation_steps": int(config.get("stage_completion_gap_steps", 16)),
    }
    if values["minimum_gap"] <= 0 or any(
            values[k] < values["minimum_gap"] for k in ("recheck_steps", "confirmation_steps")):
        raise ValueError("evidence_v1 requires positive minimum gap <= recheck/confirmation gaps")
    return values


def decide(state, observation, step, confirmation_steps=16):
    """Mutate only semantic state. Capability/master switch decide ED separately."""
    clear = observation["target_visibility"] == "clear"
    location, grasp = observation["target_location"], observation["grasp"]
    complete = (clear and location == "inside_goal" and grasp == "not_held"
                and observation["support"] == "supported")
    prior = int(state["current_stage"])
    if complete:
        last = state.get("completion_evidence_step")
        count = state.get("completion_evidence_count", 0)
        if last is None or step - last >= confirmation_steps:
            count += 1
            state["completion_evidence_step"] = step
        state["completion_evidence_count"] = count
        state["completion_confirmed"] = count >= 2
        state["current_stage"] = 0 if count >= 2 else 2
        state["guidance_requested"] = False
        return "visually_confirmed_completion" if count >= 2 else "awaiting_completion_confirmation"

    # A contradiction or an uncertain intervening observation breaks the chain.
    state["completion_evidence_count"] = 0
    state["completion_evidence_step"] = None
    state["completion_confirmed"] = False
    if clear and grasp == "held":
        state["current_stage"] = 2
        state["guidance_requested"] = True
        return "visually_held_target"
    if clear and grasp == "not_held" and location == "outside_goal":
        state["current_stage"] = 1
        state["guidance_requested"] = True
        return "target_outside_goal_reacquire"
    if clear and location in {"inside_goal", "above_goal"}:
        state["current_stage"] = 2
        state["guidance_requested"] = False
    if prior == 0:
        state["current_stage"] = 2
        state["guidance_requested"] = False
    state["uncertain_observation"] = True
    return "uncertain_preserve_nonterminal_stage"


def apply_guidance_gate(state, capabilities, master_enabled):
    stage = state["current_stage"]
    capability = capabilities.get(stage, {"available": False, "reason": "missing_stage_reward"})
    requested = state.get("guidance_requested", stage != 0)
    if not master_enabled:
        reason = "master_disabled"
    elif stage == 0:
        reason = "completion_hypothesis"
    elif not requested:
        reason = "controller_hold"
    elif not capability["available"]:
        reason = capability["reason"]
    else:
        reason = "usable_reward"
    state["use_guidance"] = reason == "usable_reward"
    state["guidance_gate_reason"] = reason
    return capability


def query_reason(state, gripper_command, config):
    """Pending command edges survive throttling; all stages get periodic checks."""
    cfg = settings(config)
    step = int(state.get("global_step", 0))
    opened = None if gripper_command is None or gripper_command == 0 else gripper_command < 0
    previous = state.get("prev_gripper_open")
    if opened is not None and previous is not None and previous != opened:
        state["pending_gripper_trigger"] = "gripper command opened" if opened else "gripper command closed"
    if opened is not None:
        state["prev_gripper_open"] = opened
    last = state.get("last_vlm_query_step")
    if last is not None and step - last < cfg["minimum_gap"]:
        return None
    if last is None:
        return "initial visual check"
    if state.get("pending_gripper_trigger"):
        return state["pending_gripper_trigger"]
    interval = cfg["confirmation_steps"] if (
        state.get("completion_evidence_count") == 1 or state.get("uncertain_observation")) else cfg["recheck_steps"]
    if step - last >= interval:
        return "periodic visual recheck"
    return None


def assess_reward(functions, keypoints, horizon=8):
    """Probe aggregate reward on deterministic CPU trajectories at live keypoints.

    Variation on probes is a capability test, NOT semantic correctness or a
    proof of global nonconstancy. No gradient requirement: ED can rank scores.
    Scalar zero at one optimum is allowed. Constant/nonfinite/invalid aggregate
    outputs fail closed. All probes have B=1, matching per-particle ED scoring.
    """
    import numpy as np
    import torch
    if not functions:
        return {"available": False, "reason": "missing_stage_reward"}
    py_state, np_state = random.getstate(), np.random.get_state()
    try:
        with torch.random.fork_rng(devices=[]), torch.no_grad():
            kp = torch.as_tensor(keypoints).detach().to(device="cpu", dtype=torch.float32).clone()
            if kp.ndim != 2 or kp.shape[1] != 3 or not len(kp) or not torch.isfinite(kp).all():
                return {"available": False, "reason": "invalid_keypoints"}
            offsets = torch.tensor([[0., 0., 0.], [.1, 0, 0], [-.1, 0, 0],
                                    [0, .1, 0], [0, -.1, 0], [0, 0, .1], [0, 0, -.1]])
            scores = []
            for anchor in kp:
                for offset in offsets:
                    path = (anchor + offset)[None, None, :].repeat(1, horizon, 1)
                    # Include a moving trajectory as well as static candidates.
                    for candidate in (path, path + torch.linspace(0, .07, horizon)[None, :, None]):
                        values = []
                        for _ in range(2):
                            total = 0.0
                            for fn in functions:
                                value = torch.as_tensor(fn(kp.clone(), candidate.clone()))
                                if value.numel() != 1 or not torch.isfinite(value).all():
                                    return {"available": False, "reason": "invalid_reward_output"}
                                total += float(value)
                            values.append(total)
                        if values[0] != values[1]:
                            return {"available": False, "reason": "nondeterministic_reward"}
                        scores.append(values[0])
            low, high = min(scores), max(scores)
            available = high - low > max(1e-10, 1e-6 * max(abs(low), abs(high)))
            return {"available": available, "reason": "variable_on_probes" if available else "constant_on_probes",
                    "probe_min": low, "probe_max": high, "probe_count": len(scores)}
    except Exception as exc:
        return {"available": False, "reason": "reward_probe_error", "error_type": type(exc).__name__}
    finally:
        random.setstate(py_state)
        np.random.set_state(np_state)


def update_stage(runner, state, gripper_command):
    """Runtime integration; every boundary logs actual effective guidance state."""
    master = bool(runner.config.get("use_guidance", True))
    cfg = settings(runner.config)
    before_stage, before_guidance = state["current_stage"], state["use_guidance"]
    reward = float(runner.policy.get_normalized_reward()) if before_guidance else None
    if reward is not None and not math.isfinite(reward):
        reward = None
    controller = runner.config.get("stage_controller", VERSION)
    distance, width, control_observation, sensor_reason = None, None, None, None
    if controller in {"contact_v2", "grasp_v3", "proprio_v4"}:
        from core.stage_contact_handoff import target_distance
        distance = target_distance(runner)
    if controller in {"grasp_v3", "proprio_v4"}:
        from core.stage_grasp_guard import check_held_observation, observed_width, update_visual_hold
        width = observed_width(runner)
        check_held_observation(state, None, step=int(state["global_step"]), executed_gripper=gripper_command,
                               width=width, distance=distance)
    robot_evidence = None
    if controller == "proprio_v4":
        from core.stage_robot_evidence import check, filter_observation, apply_recovery, target_goal_geometry, enforce_recovery_priority
        robot_evidence = check(state, step=int(state["global_step"]), width=width, distance=distance,
            executed_gripper=gripper_command, geometry=target_goal_geometry(runner))
    physical_carry_evidence = None
    if controller == 'proprio_v4' and runner.config.get('physical_carry_hold_enabled', False):
        from core.stage_carry_hold import observe as observe_physical_carry, filter_observation as filter_carry_observation, finalize as finalize_physical_carry
        physical_carry_evidence = observe_physical_carry(state, step=int(state['global_step']),
            evidence=robot_evidence, executed_gripper=gripper_command)
    capabilities = {stage: assess_reward(fns, runner.stage_live_keypoints,
                    horizon=runner.policy._action_chunk_horizon)
                    for stage, fns in runner.guidance_fns.items()}
    trigger = query_reason(state, gripper_command, runner.config) if master else None
    result, error = {}, None
    current_target_marker = None
    reason = state.get("stage_decision_reason", "initial_stage")
    if trigger:
        if state.get("vlm_query_count", 0) >= int(runner.config.get("vlm_query_limit", 50)):
            error = "stage_evidence_query_limit_exhausted"
        elif not callable(getattr(runner.gemini_stage_recognizer, "observe_scene", None)):
            error = "stage_evidence_recognizer_unavailable"
        else:
            recognizer = runner.gemini_stage_recognizer
            state["last_vlm_query_step"] = int(state["global_step"])
            state["vlm_query_count"] = state.get("vlm_query_count", 0) + 1
            if callable(getattr(recognizer, "set_trace_context", None)):
                recognizer.set_trace_context(state, trigger)
            current_rgb = runner.adapter.get_vlm_image()
            observation_options = {}
            if runner.config.get('stage_target_marker_enabled', False):
                from core.stage_target_marker import annotate, save_raw_frame
                raw_rgb = current_rgb
                current_rgb, current_target_marker = annotate(runner, raw_rgb)
                save_raw_frame(runner.config['eds_eval']['output_dir'], state, raw_rgb, current_target_marker)
                observation_options['current_target_marker'] = current_target_marker
            observation = recognizer.observe_scene(
                current_rgb=current_rgb,
                instruction=runner.adapter.get_task_description(),
                stage_descriptions=runner.stage_descriptions,
                init_img_with_keypoints=runner.init_img_with_keypoints,
                keypoint_id_to_object=runner.keypoint_id_to_object,
                trigger_reason=trigger, **observation_options)
            result = recognizer.last_result or {}
            if observation is None or not result.get("ok"):
                error = "stage_evidence_observation_failed"
            else:
                state["uncertain_observation"] = False
                control_observation = observation
                if controller in {"grasp_v3", "proprio_v4"}:
                    control_observation, sensor_reason = check_held_observation(state, observation,
                        step=int(state["global_step"]), executed_gripper=gripper_command, width=width, distance=distance)
                    if robot_evidence is not None:
                        control_observation = filter_observation(control_observation, robot_evidence)
                    if physical_carry_evidence is not None:
                        control_observation, carry_reason = filter_carry_observation(
                            control_observation, state, physical_carry_evidence)
                        if carry_reason:
                            sensor_reason = carry_reason
                    update_visual_hold(state, control_observation, int(state["global_step"]))
                reason = decide(state, control_observation, int(state["global_step"]), cfg["confirmation_steps"])
                if sensor_reason == 'unheld_above_goal_requires_reacquisition':
                    state.update(current_stage=1, guidance_requested=True)
                    reason = sensor_reason
                state["pending_gripper_trigger"] = None
    if robot_evidence is not None:
        recovery_reason = apply_recovery(state, robot_evidence, int(state["global_step"]))
        if recovery_reason:
            sensor_reason = recovery_reason
            if recovery_reason == "robot_observed_failed_grasp_reacquire":
                reason = recovery_reason
    if controller in {"contact_v2", "grasp_v3", "proprio_v4"}:
        from core.stage_contact_handoff import apply_handoff, target_distance
        apply_handoff(state, step=int(state["global_step"]), reward=reward, was_guided=before_guidance,
                      distance=distance, observation=result.get("observation"), config=runner.config)
    recovery_priority_override = False
    if robot_evidence is not None:
        recovery_priority_override = enforce_recovery_priority(state, robot_evidence, int(state['global_step']))
    if physical_carry_evidence is not None:
        physical_carry_evidence = finalize_physical_carry(state, physical_carry_evidence)
    capability = apply_guidance_gate(state, capabilities, master)
    if before_stage != state["current_stage"] or before_guidance != state["use_guidance"]:
        # Also rebase reward normalization on off->on; old reward is never evidence.
        runner.policy.reset_stage()
    state["stage_decision_reason"] = reason
    state["prev_norm_reward"] = None  # New controller does not use stale Schmitt state.
    state["last_gripper_value_used"] = gripper_command
    event = {key: state.get(key) for key in ("episode_id", "task_id", "episode_seed", "global_step", "chunk_id",
             "vlm_query_count", "completion_evidence_count", "completion_confirmed", "guidance_requested",
             "guidance_gate_reason", "stage_decision_reason")}
    event.update(controller_version=controller, stage_before=before_stage, stage_after=state["current_stage"],
                 guidance_before=before_guidance, guidance_after=state["use_guidance"],
                 reward_capability=capability, reward_capabilities=capabilities,
                 normalized_reward_diagnostic=reward, normalized_reward_used_for_decision=False,
                 trigger_reason=trigger, gripper_value_used=gripper_command,
                 gripper_source="last_executed_action", query_status="error" if error else ("ok" if trigger else "not_due"),
                 query_ok=result.get("ok"), observation=result.get("observation"), raw_response=result.get("raw_response"),
                 error=error or result.get("error"), query_latency_s=result.get("query_latency_s"),
                 current_target_marker=current_target_marker)
    if controller in {"contact_v2", "grasp_v3", "proprio_v4"}:
        event.update(contact_phase=state.get("contact_phase"), contact_until=state.get("contact_until"),
                     contact_trigger=state.get("contact_trigger"), target_distance_m=distance,
                     reward_used_for_contact_handoff=before_guidance and reward is not None)
    if controller in {"grasp_v3", "proprio_v4"}:
        event.update(gripper_width_m=width, control_observation=control_observation,
                     sensor_consistency_reason=sensor_reason, visual_hold=state.get('visual_hold'))
    if robot_evidence is not None:
        event.update(robot_evidence=robot_evidence, empty_release_until=state.get("empty_release_until"),
                     recovery_priority_override=recovery_priority_override,
                     physical_carry_evidence=physical_carry_evidence)
    for key in ("identity_memory", "identity_generated_this_query", "validation_attempts", "observation_validation_retries", "api_request_attempts", "api_sdk_retry_attempts", "api_request_counter_available", "transport", "completion_metadata"):
        if key in result:
            event[key] = result[key]
    runner._append_stage_event(event)
    if error:
        # No silent stage 1 fallback after malformed output or broken transport.
        raise RuntimeError(error)
    return state
