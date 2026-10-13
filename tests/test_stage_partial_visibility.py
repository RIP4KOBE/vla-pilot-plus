"""Regression for the recorded held+occluded integration failure."""
from copy import deepcopy
import importlib.util
import itertools
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from core.stage_evidence import decide, held_observation_is_usable, update_stage
from core.stage_grasp_guard import update_visual_hold

ROOT=Path.cwd()


def observation(**changes):
    value=dict(target_visibility='occluded',target_location='outside_goal',grasp='held',
               support='unsupported',evidence='The bottle is partly obscured, visibly suspended between fingers.')
    value.update(changes)
    return value


def test_recorded_bbq_held_observation_enters_transport_without_claiming_completion():
    path=Path(__file__).resolve().parent / 'fixtures/stage/occluded_held.jsonl'
    event=next(json.loads(s) for s in path.read_text().splitlines()
               if json.loads(s)['task_id']==3 and json.loads(s)['global_step']==80)
    assert event['stage_after']==1 and event['control_observation']['grasp']=='held'
    original=deepcopy(event['control_observation'])
    state={'current_stage':1,'guidance_requested':False}
    decide(state,original,80,accept_occluded_held=True)
    update_visual_hold(state,original,80,accept_occluded_held=True)
    assert state['current_stage']==2 and state['visual_hold']
    assert not state['completion_confirmed'] and state['completion_evidence_count']==0
    assert original==event['control_observation']


@pytest.mark.parametrize('visibility,grasp,support',itertools.product(
    ['clear','occluded','unknown'],['held','not_held','unknown'],['supported','unsupported','unknown']))
def test_observation_contract_and_latch_agree(visibility,grasp,support):
    o=observation(target_visibility=visibility,grasp=grasp,support=support)
    s={'current_stage':1}
    decide(s,o,16,accept_occluded_held=True)
    update_visual_hold(s,o,16,accept_occluded_held=True)
    expected=grasp=='held' and (visibility=='clear' or (visibility=='occluded' and support=='unsupported'))
    assert (s['current_stage']==2)==expected
    assert bool(s.get('visual_hold'))==expected
    assert not s['completion_confirmed']


def test_completion_still_requires_clear_supported_released_target_twice():
    s={'current_stage':1}
    for step in (0,16,32):
        decide(s,observation(target_location='inside_goal',grasp='not_held',support='supported'),
               step,accept_occluded_held=True)
        assert not s['completion_confirmed']
    complete=observation(target_visibility='clear',target_location='inside_goal',grasp='not_held',support='supported')
    decide(s,complete,48,accept_occluded_held=True)
    assert not s['completion_confirmed']
    decide(s,complete,64,accept_occluded_held=True)
    assert s['completion_confirmed'] and s['current_stage']==0
    decide(s,observation(),80,accept_occluded_held=True)
    assert not s['completion_confirmed'] and s['current_stage']==2


def test_disabled_flag_keeps_previous_partial_visibility_behavior():
    s={'current_stage':1};o=observation()
    decide(s,o,16);update_visual_hold(s,o,16)
    assert s['current_stage']==1 and not s.get('visual_hold')


def runtime(empty=False):
    events=[];resets=[];o=observation()
    runner=SimpleNamespace(config={'use_guidance':True,'stage_controller':'online',
        'stage_accept_occluded_held':True,'stage_preserve_reward_reference_on_guidance_toggle':True,
        'contact_proximity_handoff_enabled':False,'physical_carry_hold_enabled':True},
        policy=SimpleNamespace(_action_chunk_horizon=8,get_normalized_reward=lambda:0.,reset_stage=lambda:resets.append(1),
                               reset_eds_chunk_memory=lambda reason:None),
        guidance_fns={1:[lambda kp,a:-(a-kp[0]).square().mean()],2:[lambda kp,a:torch.tensor(0.)]},
        adapter=SimpleNamespace(get_obs=lambda:{'robot0_gripper_qpos':np.array([.0005,-.0005] if empty else [.02,-.02])},
            get_task_description=lambda:'pick up the bbq sauce and place it in the basket',
            get_ee_pose_world=lambda:SimpleNamespace(position=np.array([0.,0.,.2])),
            get_vlm_image=lambda:np.zeros((4,4,3),dtype=np.uint8)),
        stage_live_keypoints=np.array([[0.,0.,.16],[.4,.2,.05],[.6,.4,.2]]),
        keypoint_id_to_object={0:'bbq_sauce_1_main',1:'basket_1_main',2:'basket_1_main'},
        gemini_stage_recognizer=SimpleNamespace(last_result={'ok':True,'observation':o},observe_scene=lambda **kw:o),
        stage_descriptions='',init_img_with_keypoints=None,_append_stage_event=events.append)
    state=dict(current_stage=1,use_guidance=False,global_step=80,last_vlm_query_step=64,
        uncertain_observation=True,contact_phase='contact_grace',contact_until=96,
        visual_hold=False,carry_target_initial_z=.03,episode_id=0,task_id=3)
    if empty:state['robot_evidence_since_empty_closed_fingers']=64
    return runner,state,events,resets


def test_real_controller_does_not_reenable_reaching_ed_on_carried_target_at_grace_expiry():
    runner,state,events,resets=runtime()
    update_stage(runner,state,1.)
    assert state['current_stage']==2 and state['visual_hold'] and not state['use_guidance']
    assert events[-1]['accepted_occluded_held'] and state['contact_until'] is None
    state['global_step']=96;update_stage(runner,state,1.)
    assert state['current_stage']==2 and not state['use_guidance']
    assert events[-1]['physical_carry_evidence']['refreshed'] and resets==[1]


def test_persistent_measured_failed_grasp_still_overrides_partial_visual_hold():
    runner,state,events,_=runtime(empty=True)
    update_stage(runner,state,1.)
    assert events[-1]['observation']['grasp']=='held'
    assert events[-1]['control_observation']['grasp']=='not_held'
    assert not events[-1]['accepted_occluded_held']
    assert state['current_stage']==1 and state['use_guidance'] and not state['visual_hold']
    assert events[-1]['recovery_priority_override'] is False
