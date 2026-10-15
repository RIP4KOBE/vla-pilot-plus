from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from core import stage_failed_contact_recheck as module
RUNS = Path('artifacts/stage_closed_loop_20260929/runs')
V14 = 'codex_partial_visibility_v14_historical_initialization_online_full10'
V16 = 'codex_fused_carry_v16_historical_initialization_online_full10'


def rows(name):
    return [json.loads(line) for line in (RUNS/name/'output/eds_eval/stage_events.jsonl').read_text().splitlines()]


def args(event):
    return dict(observation=deepcopy(event['control_observation']), raw_observation=deepcopy(event['observation']),
                evidence=deepcopy(event['robot_evidence']), cue=deepcopy(event['physical_carry_evidence']),
                step=event['global_step'], executed_gripper=event['gripper_value_used'],
                fresh=event['query_status'] == 'ok' and event['query_ok'] is True, enabled=True)


def state_for(event):
    return dict(current_stage=event['stage_after'], visual_hold=event['visual_hold'],
                completion_confirmed=event['completion_confirmed'], contact_until=event['contact_until'],
                contact_phase=event['contact_phase'], guidance_requested=event['guidance_requested'])


def example():
    source = {e['global_step']:e for e in rows(V16) if e['task_id'] == 9}
    return state_for(source[40]), args(source[40]), args(source[56])


def test_actual_orange_empty_then_reopened_recovers_without_relabel_or_action_command():
    state, first, second = example()
    frozen = deepcopy((first, second))
    assert module.observe(state, **first)['armed']
    result = module.observe(state, **second)
    assert result['confirmed'] and result['confirmation']['seed_step'] == 40
    assert state['current_stage'] == 1 and state['guidance_requested']
    assert state['contact_until'] is None and state['recovery_approach_since'] == 56
    assert 'empty_release_until' not in state and 'robot_recovery_step' not in state
    assert not state['completion_confirmed'] and (first, second) == frozen
    assert second['raw_observation']['grasp'] == 'unknown'


@pytest.mark.parametrize('change', ['not_fresh', 'unknown_support', 'not_fully_open', 'close_command',
                                  'held_report', 'unsupported_report', 'inside_geometry', 'missing_geometry',
                                  'nonfinite_width', 'positive_carry', 'stale_cue', 'changed_window',
                                  'transport', 'completed', 'filtered_only', 'too_soon', 'too_late'])
def test_missing_or_contradictory_confirmation_cannot_cancel_grace(change):
    state, first, second = example()
    module.observe(state, **first)
    if change == 'not_fresh': second['fresh'] = False
    elif change == 'unknown_support':
        second['observation']['support'] = second['raw_observation']['support'] = 'unknown'
    elif change == 'not_fully_open': second['evidence']['width_m'] = .074
    elif change == 'close_command': second['executed_gripper'] = 1.
    elif change == 'held_report': second['observation']['grasp'] = second['raw_observation']['grasp'] = 'held'
    elif change == 'unsupported_report': second['observation']['support'] = second['raw_observation']['support'] = 'unsupported'
    elif change == 'inside_geometry':
        geo = second['evidence']['geometry']
        geo['target_position'][:2] = [(a+b)/2 for a,b in zip(geo['goal_xy_low'], geo['goal_xy_high'])]
    elif change == 'missing_geometry': second['evidence']['geometry'] = None
    elif change == 'nonfinite_width': second['evidence']['width_m'] = float('nan')
    elif change == 'positive_carry': second['cue']['present'] = True
    elif change == 'stale_cue': second['cue']['step'] = 48
    elif change == 'changed_window': state['contact_until'] = 104
    elif change == 'transport': state['current_stage'] = 2
    elif change == 'completed': state['completion_confirmed'] = True
    elif change == 'filtered_only': second['raw_observation']['support'] = 'unknown'
    elif change == 'too_soon': second['step'] = second['cue']['step'] = 48
    elif change == 'too_late': second['step'] = second['cue']['step'] = 80
    expected = {k:state.get(k) for k in ['current_stage','completion_confirmed','contact_until','guidance_requested']}
    assert not module.observe(state, **second)['confirmed']
    assert {k:state.get(k) for k in expected} == expected


def test_disabled_default_never_changes_state():
    state, first, _ = example()
    initial = deepcopy(state)
    first.pop('enabled')
    assert not module.observe(state, **first)['confirmed'] and state == initial


@pytest.mark.parametrize('name', [V14, V16])
def test_saved_success_trajectories_have_no_recovery_but_three_failures_qualify(name):
    # Eligibility only: after a hypothetical intervention, the old continuation
    # is not a counterfactual rollout and cannot predict success.
    histories = rows(name)
    first_hits = {}
    for task in [1,3,6,8,9]:
        state = {}
        for event in histories:
            if event['task_id'] != task: continue
            state.update(state_for(event))
            trace = module.observe(state, **args(event))
            if trace['confirmed']:
                first_hits[task] = event['global_step']
                break
    assert first_hits == {1:64,6:360,9:56}


def test_recorded_pudding_negative_alone_does_not_force_recovery():
    state = {}
    traces = {}
    for event in rows(V16):
        if event['task_id'] != 8 or not 48 <= event['global_step'] <= 80: continue
        state.update(state_for(event))
        traces[event['global_step']] = module.observe(state, **args(event))
    assert traces[48]['armed']
    assert not any(x['confirmed'] for x in traces.values())


def test_lift_between_reports_invalidates_previous_failed_attempt():
    state, first, second = example()
    module.observe(state, **first)
    middle = deepcopy(first)
    middle.update(step=48, fresh=False, observation=None, raw_observation=None)
    middle['cue'].update(step=48, present=True)
    module.observe(state, **middle)
    assert not module.observe(state, **second)['confirmed']


def runtime(enabled=True, missing_reward=False):
    from types import SimpleNamespace
    import numpy as np
    import torch
    source = {e['global_step']:e for e in rows(V16) if e['task_id'] == 9}
    current = {'event':source[40]}
    logs, resets, safety = [], [], []
    runner = SimpleNamespace(
        config=dict(use_guidance=True, stage_controller='proprio_v4', physical_carry_hold_enabled=True,
            stage_accept_occluded_held=True, stage_fused_carry_hold_enabled=True,
            stage_failed_contact_recheck_enabled=enabled, grasp_action_guard_enabled=False,
            stage_preserve_reward_reference_on_guidance_toggle=True,
            contact_proximity_handoff_enabled=False, contact_require_measured_proximity=True),
        policy=SimpleNamespace(_action_chunk_horizon=8, get_normalized_reward=lambda:0.,
            reset_stage=lambda:resets.append('stage'), reset_eds_chunk_memory=lambda why:resets.append(why)),
        adapter=SimpleNamespace(
            get_obs=lambda:{'robot0_gripper_qpos':np.array([current['event']['gripper_width_m']/2,
                                                        -current['event']['gripper_width_m']/2])},
            get_ee_pose_world=lambda:SimpleNamespace(position=np.array(current['event']['robot_evidence']['geometry']['target_position'])+np.array([0.,0.,current['event']['target_distance_m']])),
            get_task_description=lambda:'pick up the orange juice and place it in the basket',
            get_vlm_image=lambda:np.zeros((4,4,3),dtype=np.uint8)),
        keypoint_id_to_object={0:'orange_juice_1_main',1:'basket_1_main',2:'basket_1_main'},
        guidance_fns={1:[lambda kp,a:torch.tensor(0.)] if missing_reward else [lambda kp,a:-(a-kp[0]).square().mean()],
                      2:[lambda kp,a:torch.tensor(0.)]},
        stage_descriptions='', init_img_with_keypoints=None,
        _append_stage_event=logs.append, _append_safety_event=safety.append)
    recognizer = SimpleNamespace(last_result=None)
    def observe(**kwargs):
        raw = deepcopy(current['event']['observation'])
        recognizer.last_result = dict(ok=True, observation=raw)
        return raw
    recognizer.observe_scene = observe
    runner.gemini_stage_recognizer = recognizer
    state = dict(current_stage=1,use_guidance=False,guidance_requested=False,global_step=40,
        last_vlm_query_step=24,uncertain_observation=True,contact_phase='contact_grace',
        contact_until=88,visual_hold=False,completion_confirmed=False,episode_id=9,task_id=9)
    def select(step):
        current['event'] = source[step]
        geometry = current['event']['robot_evidence']['geometry']
        runner.stage_live_keypoints = np.array([geometry['target_position'],
            geometry['goal_xy_low']+[.0],geometry['goal_xy_high']+[.10]])
        state['global_step'] = step
    select(40)
    return runner,state,logs,resets,safety,select,source


def test_runtime_recheck_wins_grace_without_resetting_reward_stage_or_overriding_actions():
    import numpy as np
    from core.stage_evidence import update_stage
    from core.stage_grasp_guard import apply_to_action
    for enabled in [False,True]:
        runner,state,logs,resets,safety,select,source = runtime(enabled)
        for step in [40,48,56]:
            select(step)
            update_stage(runner,state,source[step]['gripper_value_used'])
        assert state['current_stage'] == 1 and state['use_guidance'] is enabled
        assert logs[-1]['reward_reference_reset'] is False
        assert resets == (['guidance_change'] if enabled else [])
        assert logs[-1]['observation'] == source[56]['observation']
        assert not state['completion_confirmed']
        action=np.array([[[.1,.2,.3,.4,.5,.6,-1.]]])
        np.testing.assert_equal(apply_to_action(runner,state,action.copy(),0,56),action)
        assert not safety[-1]['override']
        if enabled:
            assert logs[-1]['failed_contact_recheck']['confirmed']
            assert state['contact_until'] is None
            assert all(module.audit_checks(logs).values())


def test_runtime_reward_capability_remains_the_final_gate():
    from core.stage_evidence import update_stage
    runner,state,logs,_,_,select,source = runtime(missing_reward=True)
    for step in [40,48,56]:
        select(step);update_stage(runner,state,source[step]['gripper_value_used'])
    assert logs[-1]['failed_contact_recheck']['confirmed']
    assert state['guidance_requested'] and not state['use_guidance']
    assert state['guidance_gate_reason'] == 'constant_on_probes'


@pytest.mark.parametrize('corruption', ['missing_seed','wrong_seed','fake_open_width','recovery_gate_off',
                                      'reference_reset','wrong_reason','rewritten_raw','forged_confirmation'])
def test_audit_rejects_broken_provenance_or_control_outcome(corruption):
    from core.stage_evidence import update_stage
    runner,state,logs,_,_,select,source = runtime()
    for step in [40,48,56]:
        select(step);update_stage(runner,state,source[step]['gripper_value_used'])
    assert all(module.audit_checks(logs).values())
    altered=deepcopy(logs)
    if corruption == 'missing_seed': altered=altered[1:]
    elif corruption == 'wrong_seed': altered[-1]['failed_contact_recheck']['confirmation']['seed_step']=32
    elif corruption == 'fake_open_width': altered[-1]['robot_evidence']['width_m']=.04
    elif corruption == 'recovery_gate_off': altered[-1]['guidance_after']=False
    elif corruption == 'reference_reset': altered[-1]['reward_reference_reset']=True
    elif corruption == 'wrong_reason': altered[-1]['stage_decision_reason']='other'
    elif corruption == 'rewritten_raw': altered[-1]['observation']['grasp']='held'
    elif corruption == 'forged_confirmation': altered[1]['failed_contact_recheck']['confirmed']=True
    assert not all(module.audit_checks(altered).values())
