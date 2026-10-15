import numpy as np
import torch
from types import SimpleNamespace
from core.stage_grasp_guard import goal_alignment, update_visual_hold, guard_command, check_held_observation


def test_open_is_delayed_only_for_held_target_outside_goal():
    s={}; update_visual_hold(s,dict(target_visibility='clear',grasp='held'),64)
    actual,reason=guard_command(s,-1.,step=72,aligned=False,distance=.04,config={})
    assert actual==1. and reason.startswith('hold_visible')
    actual,_=guard_command(s,-1.,step=80,aligned=True,distance=.04,config={})
    assert actual==-1.


def test_empty_grasp_reopen_has_a_bounded_window_and_respects_goal_release():
    s={'empty_release_until':32}
    assert guard_command(s,1.,step=16,aligned=False,distance=.1,config={})[0]==-1.
    assert guard_command(s,1.,step=24,aligned=True,distance=.1,config={})[0]==1.
    assert guard_command(s,1.,step=32,aligned=False,distance=.1,config={})[0]==1.


def test_explicit_failed_grasp_cancels_hold_and_timeout_is_bounded():
    s={};update_visual_hold(s,dict(target_visibility='clear',grasp='held'),10)
    update_visual_hold(s,dict(target_visibility='clear',grasp='not_held'),32)
    assert guard_command(s,-1.,step=32,aligned=False,distance=.2,config={})[0]==-1.
    update_visual_hold(s,dict(target_visibility='clear',grasp='held'),40)
    update_visual_hold(s,dict(target_visibility='clear',grasp='held'),56)
    assert guard_command(s,-1.,step=200,aligned=False,distance=.2,config={})[0]==-1.


def test_contact_debounce_does_not_claim_visual_hold_and_expires():
    s={}
    guard_command(s,1.,step=16,aligned=False,distance=.04,config={})
    assert guard_command(s,-1.,step=20,aligned=False,distance=.04,config={})[0]==1.
    assert not s.get('visual_hold')
    assert guard_command(s,-1.,step=32,aligned=False,distance=.04,config={})[0]==-1.


def test_release_geometry_uses_basket_extent_not_distance_to_target():
    kp=np.array([[0.,0.,0.],[.4,.2,.05],[.6,.4,.2]])
    mapping={0:'bbq_sauce_1_main',1:'basket_1_main',2:'basket_1_main'}
    assert goal_alignment([.5,.3,.3],kp,mapping)[0]
    assert not goal_alignment([.3,.3,.3],kp,mapping)[0]
    assert not goal_alignment([.5,.3,.3],kp,{0:'bbq_sauce_1_main'})[0]


def test_visual_held_claim_is_not_accepted_against_sustained_proprioceptive_contradiction():
    s={};o=dict(target_visibility='clear',grasp='held',target_location='above_goal',support='unsupported')
    result,reason=check_held_observation(s,o,step=0,executed_gripper=-1.,width=.08,distance=.14)
    assert result['grasp']=='held'
    result,reason=check_held_observation(s,o,step=16,executed_gripper=-1.,width=.08,distance=.14)
    assert result['grasp']=='not_held' and reason.startswith('held_veto')
    assert o['grasp']=='held'  # raw evidence must not be rewritten
    result,reason=check_held_observation(s,o,step=48,executed_gripper=-1.,width=.08,distance=.14)
    assert result['target_location']=='above_goal' and reason.startswith('unheld_above')


def test_open_command_alone_is_not_grasp_truth():
    s={};o=dict(target_visibility='clear',grasp='held',target_location='outside_goal')
    for step in (0,32):
        result,reason=check_held_observation(s,o,step=step,executed_gripper=-1.,width=.04,distance=.04)
    assert result['grasp']=='held' and reason is None


def test_runtime_action_guard_preserves_arm_and_cached_policy_chunk():
    from core.stage_grasp_guard import apply_to_action
    journal=[]
    adapter=SimpleNamespace(get_obs=lambda:{'robot0_gripper_qpos':np.array([.02,-.02])},
        get_task_description=lambda:'pick up the bbq sauce and place it in the basket',
        get_ee_pose_world=lambda:SimpleNamespace(position=np.array([0.,0.,.1])))
    runner=SimpleNamespace(adapter=adapter,config={},keypoint_id_to_object={0:'bbq_sauce_1_main',1:'basket_1_main',2:'basket_1_main'},
        stage_live_keypoints=np.array([[0.,0.,.07],[.4,.2,.05],[.6,.4,.2]]),_append_safety_event=journal.append)
    chunk=torch.tensor([[[.1,.2,.3,.4,.5,.6,-1.]]]); original=chunk.clone()
    s={'visual_hold':True,'visual_hold_since':0,'episode_id':0,'task_id':3}
    actual=apply_to_action(runner,s,chunk,0,8)
    assert torch.equal(original,chunk)
    assert torch.equal(actual[...,:6],chunk[...,:6]) and actual[0,0,-1]==1
    assert journal[0]['override'] and journal[0]['executed_action'][-1]==1
