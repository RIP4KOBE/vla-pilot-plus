from core.stage.grasp import check, filter_observation, apply_recovery


def measure(s, step, width=.001, distance=.09, command=1, outside=True):
    return check(s,step=step,width=width,distance=distance,executed_gripper=command,
                 geometry={'target_definitely_outside_goal_xy':outside})


def test_empty_fingers_revoke_occluded_hold_only_after_persistence():
    s={'visual_hold':True,'visual_hold_since':0,'current_stage':2}
    assert not measure(s,0)['no_grasp']
    evidence=measure(s,16)
    raw=dict(grasp='unknown',target_visibility='occluded',target_location='unknown',support='unknown')
    adjusted=filter_observation(raw,evidence)
    assert adjusted['grasp']=='not_held' and raw['grasp']=='unknown'
    assert adjusted['target_visibility']=='occluded' and adjusted['target_location']=='unknown'
    apply_recovery(s,evidence,16)
    assert s['current_stage']==1 and not s['visual_hold'] and s['empty_release_until']==32
    apply_recovery(s,evidence,24)
    assert s['empty_release_until']==32  # no indefinite forced-open interval


def test_empty_fingers_do_not_pull_a_possibly_placed_target_back_out():
    s={'current_stage':2}
    measure(s,0,outside=False)
    e=measure(s,32,outside=False)
    apply_recovery(s,e,32)
    assert s['current_stage']==2 and 'empty_release_until' not in s
    assert not s.get('completion_confirmed')


def test_closed_command_and_nonempty_width_are_not_failure_evidence():
    s={}
    for step in [0,16,32,64]:
        assert not measure(s,step,width=.035,distance=.07)['no_grasp']


def test_persistent_far_target_breaks_visual_unknown_deadlock():
    s={'current_stage':2}
    measure(s,0,width=.04,distance=.22)
    assert not measure(s,16,width=.04,distance=.22)['no_grasp']
    e=measure(s,24,width=.04,distance=.22)
    assert e['no_grasp_reasons']==['target_far_from_hand']
    apply_recovery(s,e,24)
    assert s['current_stage']==1 and 'empty_release_until' not in s


def test_transient_empty_width_does_not_accumulate_across_a_contact():
    s={}
    measure(s,0)
    measure(s,8,width=.02)
    assert not measure(s,16)['no_grasp']
    assert not measure(s,24)['no_grasp']
    assert measure(s,32)['no_grasp']


def test_runtime_recovers_empty_grasp_between_online_queries():
    import numpy as np
    import torch
    from types import SimpleNamespace
    from core.stage.controller import update_stage
    events=[]
    raw=dict(target_visibility='clear',target_location='outside_goal',grasp='held',
             support='unsupported',evidence='Target appears near fingers.')
    rec=SimpleNamespace(last_result={'ok':True,'observation':raw},observe_scene=lambda **kw:raw)
    runner=SimpleNamespace(config={'use_guidance':True,'stage_controller':'online'},
        policy=SimpleNamespace(_action_chunk_horizon=8,get_normalized_reward=lambda:0.,reset_stage=lambda:None),
        adapter=SimpleNamespace(get_obs=lambda:{'robot0_gripper_qpos':np.array([.0005,-.0005])},
            get_ee_pose_world=lambda:SimpleNamespace(position=np.array([0.,0.,.15])),
            get_vlm_image=lambda:np.zeros((4,4,3),dtype=np.uint8),
            get_task_description=lambda:'pick up the bbq sauce and place it in the basket'),
        stage_live_keypoints=np.array([[0.,0.,.03],[.4,.2,.05],[.6,.4,.2]]),
        keypoint_id_to_object={0:'bbq_sauce_1_main',1:'basket_1_main',2:'basket_1_main'},
        guidance_fns={1:[lambda kp,a:-(a-kp[0]).square().mean()],2:[lambda kp,a:torch.tensor(0.)]},
        gemini_stage_recognizer=rec,stage_descriptions='',init_img_with_keypoints=None,_append_stage_event=events.append)
    s=dict(current_stage=1,use_guidance=True,global_step=0)
    update_stage(runner,s,1.)
    assert s['current_stage']==2 and not s['use_guidance']
    for step in [8,16]:
        s['global_step']=step
        update_stage(runner,s,1.)
    assert events[-1]['query_status']=='not_due'
    assert s['current_stage']==1 and s['use_guidance'] and not s['visual_hold']
    assert s['empty_release_until']==32
    assert events[0]['observation']==raw and raw['grasp']=='held'
