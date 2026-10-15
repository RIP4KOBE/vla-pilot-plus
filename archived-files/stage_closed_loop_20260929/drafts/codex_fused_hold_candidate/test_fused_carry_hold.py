"""Recorded milk failure, runtime precedence, fresh-evidence and native-action checks."""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from core.stage_evidence import update_stage
from core.stage_fused_carry_hold import establish_hold, REASON, audit_checks
from core.stage_grasp_guard import apply_to_action


@lru_cache(maxsize=1)
def recorded_event():
    path = Path('artifacts/stage_closed_loop_20260929/runs/codex_partial_visibility_v14_historical_initialization_online_full10/output/eds_eval/stage_events.jsonl')
    return next(e for e in map(json.loads, path.read_text().splitlines())
                if e['task_id'] == 7 and e['global_step'] == 376)


def inputs():
    event = deepcopy(recorded_event())
    state = dict(current_stage=1, guidance_requested=False, visual_hold=False,
                 completion_confirmed=False, contact_phase='contact_grace', contact_until=408)
    args = dict(observation=event['control_observation'], raw_observation=event['observation'],
                cue=event['physical_carry_evidence'], evidence=event['robot_evidence'],
                step=376, executed_gripper=event['gripper_value_used'], enabled=True)
    return state, args


def test_recorded_milk_suspension_and_carry_establish_hold_without_relabeling_unknown():
    state, args = inputs()
    original = deepcopy(args)
    assert recorded_event()['stage_after'] == 1
    assert establish_hold(state, **args)
    assert state['current_stage'] == 2 and state['visual_hold']
    assert state['visual_hold_since'] == 376 and state['guidance_requested']
    assert not state['completion_confirmed'] and state['completion_evidence_count'] == 0
    assert args == original and args['raw_observation']['grasp'] == 'unknown'


@pytest.mark.parametrize('field,value', [
    ('grasp', 'not_held'), ('grasp', 'held'), ('support', 'supported'),
    ('support', 'unknown'), ('target_visibility', 'unknown'), ('target_location', 'unknown'),
])
def test_visual_negative_or_missing_suspension_cannot_create_a_hold(field, value):
    state, args = inputs()
    args['raw_observation'][field] = value
    args['observation'][field] = value
    before = deepcopy(state)
    assert not establish_hold(state, **args) and state == before


def test_filtered_negative_cannot_be_promoted_as_a_raw_unknown():
    state, args = inputs()
    args['raw_observation']['grasp'] = 'not_held'
    assert args['observation']['grasp'] == 'unknown'
    assert not establish_hold(state, **args)


@pytest.mark.parametrize('kind', [
    'eight_steps_only', 'stale_cue', 'future_timer', 'absent_present', 'not_persistent',
    'empty_width', 'fully_open_width', 'far_target', 'low_lift', 'nonfinite_width',
    'command_open', 'command_missing', 'robot_failure', 'geometry_missing',
])
def test_missing_or_contradictory_robot_evidence_keeps_state_unchanged(kind):
    state, args = inputs()
    if kind == 'eight_steps_only': args['cue']['evidence_since'] = 368
    elif kind == 'stale_cue': args['cue']['step'] = 368
    elif kind == 'future_timer': args['cue']['evidence_since'] = 384
    elif kind == 'absent_present': args['cue']['present'] = False
    elif kind == 'not_persistent': args['cue']['persistent'] = False
    elif kind == 'empty_width': args['evidence']['width_m'] = .002
    elif kind == 'fully_open_width': args['evidence']['width_m'] = .08
    elif kind == 'far_target': args['evidence']['distance_m'] = .16
    elif kind == 'low_lift': args['cue']['target_lift_m'] = .005
    elif kind == 'nonfinite_width': args['evidence']['width_m'] = float('nan')
    elif kind == 'command_open': args['executed_gripper'] = -1.
    elif kind == 'command_missing': args['executed_gripper'] = None
    elif kind == 'robot_failure': args['evidence']['no_grasp'] = True
    elif kind == 'geometry_missing': args['evidence']['geometry'] = None
    before = deepcopy(state)
    assert not establish_hold(state, **args) and state == before


@pytest.mark.parametrize('release_key', ['empty_release_until', 'payload_release_until'])
def test_active_release_blocks_hold_but_expired_release_does_not(release_key):
    state, args = inputs()
    state[release_key] = 384
    before = deepcopy(state)
    assert not establish_hold(state, **args) and state == before
    state[release_key] = 376
    assert establish_hold(state, **args)


@pytest.mark.parametrize('change', [dict(current_stage=0), dict(current_stage=2),
                                   dict(completion_confirmed=True), dict(visual_hold=True)])
def test_existing_transport_or_completion_is_not_restarted(change):
    state, args = inputs()
    state.update(change)
    before = deepcopy(state)
    assert not establish_hold(state, **args) and state == before


def test_disabled_default_preserves_the_original_state():
    state, args = inputs()
    args.pop('enabled')
    before = deepcopy(state)
    assert not establish_hold(state, **args) and state == before


def runtime(enabled=True):
    event = deepcopy(recorded_event())
    evidence = event['robot_evidence']
    position = np.array(evidence['geometry']['target_position'])
    goal = evidence['geometry']
    points = np.array([position, goal['goal_xy_low'] + [.05], goal['goal_xy_high'] + [.20]])
    raw = deepcopy(event['observation'])
    events, resets, safety = [], [], []
    runner = SimpleNamespace(
        config=dict(use_guidance=True, stage_controller='proprio_v4', physical_carry_hold_enabled=True,
                    stage_accept_occluded_held=True, stage_fused_carry_hold_enabled=enabled,
                    stage_preserve_reward_reference_on_guidance_toggle=True,
                    contact_proximity_handoff_enabled=False, contact_require_measured_proximity=True,
                    grasp_action_guard_enabled=False, payload_release_enabled=True, grasp_hold_max_steps=160),
        policy=SimpleNamespace(_action_chunk_horizon=8, get_normalized_reward=lambda:0.,
                               reset_stage=lambda:resets.append('stage'),
                               reset_eds_chunk_memory=lambda reason:resets.append(reason)),
        adapter=SimpleNamespace(
            get_obs=lambda:{'robot0_gripper_qpos':np.array([evidence['width_m']/2,-evidence['width_m']/2])},
            get_ee_pose_world=lambda:SimpleNamespace(position=position+np.array([0.,0.,evidence['distance_m']])),
            get_task_description=lambda:'pick up the milk and place it in the basket',
            get_vlm_image=lambda:np.zeros((4,4,3), dtype=np.uint8)),
        stage_live_keypoints=points,
        keypoint_id_to_object={0:'milk_1_main',1:'basket_1_main',2:'basket_1_main'},
        guidance_fns={1:[lambda kp,a:-(a-kp[0]).square().mean()],2:[lambda kp,a:torch.tensor(0.)]},
        gemini_stage_recognizer=SimpleNamespace(last_result={'ok':True,'observation':raw},
                                                observe_scene=lambda **kw:raw),
        stage_descriptions='', init_img_with_keypoints=None,
        _append_stage_event=events.append, _append_safety_event=safety.append)
    state = dict(current_stage=1, use_guidance=False, guidance_requested=False, global_step=376,
                 last_vlm_query_step=360, uncertain_observation=True, contact_phase='contact_grace',
                 contact_until=408, visual_hold=False, carry_evidence_since=360,
                 carry_target_initial_z=position[2]-event['physical_carry_evidence']['target_lift_m'],
                 episode_id=0, task_id=7)
    return runner, state, events, resets, safety, raw


def test_runtime_establishment_and_grace_expiry_do_not_restart_approach_ed():
    for enabled in (False, True):
        runner, state, events, resets, _, raw = runtime(enabled)
        original = deepcopy(raw)
        update_stage(runner, state, 1.)
        assert events[-1]['fused_hold_established'] is enabled
        assert events[-1]['observation'] == events[-1]['control_observation'] == original
        assert not events[-1]['accepted_occluded_held']
        if enabled:
            assert state['current_stage'] == 2 and state['visual_hold']
            assert state['contact_until'] is None and not state['use_guidance']
            assert events[-1]['stage_decision_reason'] == REASON
            assert events[-1]['fused_hold_source'] == 'visual_suspension_and_persistent_robot_carry'
            assert events[-1]['fused_hold_release_active'] is False
            assert events[-1]['physical_carry_evidence']['refreshed']
            assert resets == ['stage']
        state['global_step'] = 408
        raw['support'] = 'unknown'
        update_stage(runner, state, -1.)
        assert state['current_stage'] == (2 if enabled else 1)
        assert state['use_guidance'] is (not enabled)
        assert not state['completion_confirmed']
        assert not events[-1]['fused_hold_established']


def test_runtime_requires_a_fresh_successful_query_and_master_permission():
    for kind in ('not_due', 'master_off', 'query_error'):
        runner, state, events, _, _, _ = runtime()
        if kind == 'not_due': state['last_vlm_query_step'] = 368
        if kind == 'master_off': runner.config['use_guidance'] = False
        if kind == 'query_error':
            runner.gemini_stage_recognizer.last_result = {'ok':False}
            runner.gemini_stage_recognizer.observe_scene = lambda **kw:None
            with pytest.raises(RuntimeError, match='observation_failed'):
                update_stage(runner, state, 1.)
        else:
            update_stage(runner, state, 1.)
        assert not state['visual_hold'] and state['current_stage'] == 1
        assert not events[-1]['fused_hold_established']


def test_runtime_measured_failure_and_release_keep_precedence():
    runner, state, events, _, _, _ = runtime()
    runner.adapter.get_obs = lambda:{'robot0_gripper_qpos':np.array([.0005,-.0005])}
    runner.stage_live_keypoints[1:, :2] += .5
    state['robot_evidence_since_empty_closed_fingers'] = 360
    update_stage(runner, state, 1.)
    assert events[-1]['robot_evidence']['no_grasp']
    assert state['current_stage'] == 1 and state['use_guidance'] and not state['visual_hold']
    assert not events[-1]['fused_hold_established']
    runner, state, events, _, _, _ = runtime()
    state['payload_release_until'] = 384
    update_stage(runner, state, 1.)
    assert not events[-1]['fused_hold_established'] and events[-1]['fused_hold_release_active']


def test_runtime_keeps_two_separated_visual_completion_confirmations():
    runner, state, events, _, _, raw = runtime()
    raw.update(target_visibility='clear', target_location='inside_goal', grasp='not_held', support='supported')
    update_stage(runner, state, -1.)
    assert not state['completion_confirmed'] and state['current_stage'] == 2
    assert not events[-1]['fused_hold_established']
    state['global_step'] = 392
    update_stage(runner, state, -1.)
    assert state['completion_confirmed'] and state['current_stage'] == 0
    assert not events[-1]['fused_hold_established']


def test_sensor_fusion_never_overrides_the_native_seven_dimensional_action():
    runner, state, _, _, safety, _ = runtime()
    update_stage(runner, state, 1.)
    chunk = torch.tensor([[[.1,.2,.3,.4,.5,.6,-1.]]])
    original = chunk.clone()
    result = apply_to_action(runner, state, chunk, 0, 376)
    assert torch.equal(chunk, original) and torch.equal(result, original)
    assert not safety[-1]['override'] and safety[-1]['executed_action'] == safety[-1]['raw_action']


@pytest.mark.parametrize('corruption', [
    'stale_query', 'fabricated_held', 'missing_suspension', 'completion', 'release',
    'short_carry', 'robot_failure', 'open_command', 'wrong_origin', 'ed_active',
])
def test_audit_rejects_unsupported_or_misreported_establishment(corruption):
    runner, state, events, _, _, _ = runtime()
    update_stage(runner, state, 1.)
    assert all(audit_checks(events).values())
    event = deepcopy(events[-1])
    if corruption == 'stale_query': event['query_status'] = 'not_due'
    elif corruption == 'fabricated_held': event['control_observation']['grasp'] = 'held'
    elif corruption == 'missing_suspension': event['observation']['support'] = 'unknown'
    elif corruption == 'completion': event['completion_confirmed'] = True
    elif corruption == 'release': event['fused_hold_release_active'] = True
    elif corruption == 'short_carry': event['physical_carry_evidence']['evidence_since'] = 368
    elif corruption == 'robot_failure': event['robot_evidence']['no_grasp'] = True
    elif corruption == 'open_command': event['gripper_value_used'] = -1.
    elif corruption == 'wrong_origin': event['fused_hold_source'] = 'explicit_visual_held'
    elif corruption == 'ed_active': event['guidance_after'] = True
    assert not all(audit_checks([event]).values())


def test_archived_helper_audits_without_an_installed_production_module(tmp_path):
    import importlib.util
    import shutil
    import core.stage_fused_carry_hold as candidate
    path = tmp_path / 'archived_fused_hold.py'
    shutil.copy2(candidate.__file__, path)
    spec = importlib.util.spec_from_file_location('archived_fused_hold', path)
    archived = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(archived)
    runner, state, events, _, _, _ = runtime()
    update_stage(runner, state, 1.)
    assert all(archived.audit_checks(events).values())


def test_audit_preserves_valid_no_effect_cohorts():
    runner, state, events, _, _, _ = runtime()
    state['last_vlm_query_step'] = 368
    update_stage(runner, state, 1.)
    assert not events[-1]['fused_hold_established']
    assert all(audit_checks(events).values())
