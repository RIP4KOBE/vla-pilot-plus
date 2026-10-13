from types import SimpleNamespace
import numpy as np
import torch
from core.stage_carry_hold import update
from core.stage_grasp_guard import apply_to_action


def runner_state():
    journal=[]
    runner=SimpleNamespace(
        config={'physical_carry_hold_enabled':True,'grasp_hold_max_steps':80,
                'grasp_contact_debounce_steps':0},
        adapter=SimpleNamespace(get_obs=lambda:{'robot0_gripper_qpos':np.array([.02,-.02])},
            get_task_description=lambda:'pick up the bbq sauce and place it in the basket',
            get_ee_pose_world=lambda:SimpleNamespace(position=np.array([0.,0.,.2]))),
        stage_live_keypoints=np.array([[0.,0.,.16],[.4,.2,.05],[.6,.4,.2]]),
        keypoint_id_to_object={0:'bbq_sauce_1_main',1:'basket_1_main',2:'basket_1_main'},
        _append_safety_event=journal.append)
    state=dict(visual_hold=True,visual_hold_since=0,current_stage=2,
               carry_target_initial_z=.03,episode_id=0,task_id=3)
    return runner,state,journal


def test_expired_visual_timer_does_not_drop_physically_carried_target():
    runner,state,journal=runner_state()
    ev=dict(geometry=dict(target_position=[0.,0.,.16]),width_m=.04,distance_m=.04,no_grasp=False)
    for step in [72,80]:
        update(state,step=step,evidence=ev,executed_gripper=1.)
    chunk=torch.tensor([[[.1,.2,.3,.4,.5,.6,-1.]]]);old=chunk.clone()
    result=apply_to_action(runner,state,chunk,0,80)
    assert result[0,0,-1]==1. and journal[-1]['physical_carry_hold_step']==80
    assert torch.equal(chunk,old) and torch.equal(result[...,:6],old[...,:6])
    assert not journal[-1]['goal_aligned']


def test_visual_claim_alone_does_not_block_native_regrasp_open():
    runner,state,journal=runner_state()
    chunk=torch.tensor([[[.1,.2,.3,.4,.5,.6,-1.]]]);old=chunk.clone()
    result=apply_to_action(runner,state,chunk,0,16)
    assert torch.equal(result,old) and torch.equal(chunk,old)
    assert journal[-1]['reason']=='unverified_visual_hold_preserve_policy_open'


def test_stage_update_collects_carry_between_queries_and_keeps_failure_priority():
    from core.stage_evidence import update_stage
    runner,state,journal=runner_state();events=[]
    runner.config.update(use_guidance=True,stage_controller='online')
    runner.policy=SimpleNamespace(_action_chunk_horizon=8,get_normalized_reward=lambda:0.,reset_stage=lambda:None)
    runner.guidance_fns={1:[lambda kp,a:-(a-kp[0]).square().mean()],2:[lambda kp,a:torch.tensor(0.)]}
    raw=dict(target_visibility='occluded',target_location='unknown',grasp='unknown',support='unknown',evidence='Hidden.')
    runner.gemini_stage_recognizer=SimpleNamespace(last_result={'ok':True,'observation':raw},observe_scene=lambda **kw:raw)
    runner.adapter.get_vlm_image=lambda:np.zeros((4,4,3),dtype=np.uint8)
    runner.stage_descriptions='';runner.init_img_with_keypoints=None;runner._append_stage_event=events.append
    state.update(use_guidance=False,global_step=72,last_vlm_query_step=64)
    update_stage(runner,state,1.)
    state['global_step']=80;update_stage(runner,state,1.)
    assert events[-1]['query_status']=='not_due'
    assert events[-1]['physical_carry_evidence']['refreshed']
    assert state['current_stage']==2 and not state['use_guidance']
    # A contradicted visual negative is uncertain; the prior real carry persists.
    contradicted=dict(target_visibility='clear',target_location='outside_goal',grasp='not_held',
                      support='supported',evidence='Wrong distractor remains on the floor.')
    runner.gemini_stage_recognizer=SimpleNamespace(last_result={'ok':True,'observation':contradicted},
                                                   observe_scene=lambda **kw:contradicted)
    state['global_step']=96;update_stage(runner,state,1.)
    assert state['current_stage']==2 and state['visual_hold'] and not state['use_guidance']
    assert events[-1]['observation']['grasp']=='not_held'
    assert events[-1]['control_observation']['grasp']=='unknown'
    assert events[-1]['sensor_consistency_reason']=='negative_visual_grasp_conflicts_with_measured_carry'
    # Sensor-confirmed empty grasp wins even if a prior carry cue exists.
    runner.adapter.get_obs=lambda:{'robot0_gripper_qpos':np.array([.0005,-.0005])}
    for step in [104,112,120]:
        state['global_step']=step;update_stage(runner,state,1.)
    assert state['current_stage']==1 and state['use_guidance'] and not state['visual_hold']
    assert 'physical_carry_hold_step' not in state
    assert state['empty_release_until']==136
