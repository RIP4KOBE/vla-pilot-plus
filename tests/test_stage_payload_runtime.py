import numpy as np
import torch
from types import SimpleNamespace
from core.stage.grasp import apply_to_action


def setup(enabled):
    journal=[]
    adapter=SimpleNamespace(get_obs=lambda:{'robot0_gripper_qpos':np.array([.02,-.02])},
        get_task_description=lambda:'pick up the chocolate pudding and place it in the basket',
        get_ee_pose_world=lambda:SimpleNamespace(position=np.array([-.11,.3,.20])))
    runner=SimpleNamespace(adapter=adapter,config={'payload_release_enabled':enabled,'grasp_contact_debounce_steps':0},
        keypoint_id_to_object={0:'chocolate_pudding_1_main',1:'basket_1_main',2:'basket_1_main'},
        stage_live_keypoints=np.array([[-.0678,.3037,.1666],[-.082,.1811,.027],[.0607,.3234,.139]]),
        _append_safety_event=journal.append)
    s={'visual_hold':True,'visual_hold_since':48,'current_stage':2,'episode_id':0,'task_id':8}
    return runner,s,journal


def test_payload_release_integration_preserves_arm_and_completes_open_request():
    runner,s,journal=setup(True)
    chunk=torch.tensor([[[.1,.2,.3,.4,.5,.6,-1.]]]);old=chunk.clone()
    actual=apply_to_action(runner,s,chunk,0,97)
    assert torch.equal(chunk,old) and torch.equal(actual[...,:6],old[...,:6])
    assert actual[0,0,-1]==-1.
    assert not journal[-1]['goal_aligned'] and journal[-1]['payload_aligned']
    assert journal[-1]['reason']=='allow_policy_release_payload_over_destination'
    close=chunk.clone();close[0,0,-1]=1.
    assert apply_to_action(runner,s,close,0,104)[0,0,-1]==-1.
    assert apply_to_action(runner,s,close,0,105)[0,0,-1]==1.
    assert close[0,0,-1]==1.
    assert all(x['raw_action'][:6]==x['executed_action'][:6] for x in journal)


def test_disabled_feature_retains_previous_guard_behavior():
    runner,s,journal=setup(False)
    chunk=torch.tensor([[[.1,.2,.3,.4,.5,.6,-1.]]])
    actual=apply_to_action(runner,s,chunk,0,97)
    assert actual[0,0,-1]==1.
    assert journal[-1]['reason']=='hold_visible_target_outside_destination'
