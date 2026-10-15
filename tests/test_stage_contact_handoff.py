from types import SimpleNamespace
import numpy as np
from core.stage_contact_handoff import apply_handoff, target_distance


def update(s, step, reward=None, guided=True, distance=None):
    apply_handoff(s, step=step, reward=reward, was_guided=guided, distance=distance,
                  observation=None, config={})


def test_near_target_stops_reaching_without_claiming_grasp_or_completion():
    s={'current_stage':1,'guidance_requested':True}
    update(s,24,.9)
    assert s['current_stage']==1 and not s['guidance_requested']
    assert s['contact_until']==88
    # A fresh VLM outside/not-held observation during the window must not
    # immediately re-enable reaching while the policy is trying to grasp.
    s['guidance_requested']=True; update(s,40,guided=False)
    assert not s['guidance_requested']
    update(s,88,guided=False)
    assert s['guidance_requested']
    update(s,96,.99,distance=.01)
    assert s['guidance_requested']  # recovery gets at least 16 approach steps
    update(s,104,.9)
    assert not s['guidance_requested']


def test_stale_reward_cannot_retrigger_contact_grace():
    s={'current_stage':1,'guidance_requested':True}
    update(s,32,.99,guided=False)
    assert s['guidance_requested'] and s['contact_phase']=='approach'


def test_visual_held_and_later_drop_override_contact_window():
    s={'current_stage':1};update(s,24,.9)
    s.update(current_stage=2,guidance_requested=True);update(s,40,guided=False)
    assert s['contact_until'] is None
    s.update(current_stage=1,guidance_requested=True);update(s,56,guided=False,distance=.001)
    assert s['guidance_requested'] and s['recovery_approach_since']==56


def test_distance_uses_instruction_identity_not_fixed_keypoint_zero():
    runner=SimpleNamespace(adapter=SimpleNamespace(
        get_task_description=lambda:'pick up the salad dressing and place it in the basket',
        get_ee_pose_world=lambda:SimpleNamespace(position=np.array([0.,0.,0.]))),
        keypoint_id_to_object={0:'basket_1_main',1:'salad_dressing_1_main'},
        stage_live_keypoints=np.array([[1.,1.,1.],[.03,0.,0.]]))
    assert abs(target_distance(runner)-.03)<1e-8


def test_grasp_v3_cannot_handoff_on_predicted_progress_while_physically_far():
    s={'current_stage':1,'guidance_requested':True}
    apply_handoff(s,step=32,reward=.99,was_guided=True,distance=.28,observation=None,
                  config={'contact_require_measured_proximity':True})
    assert s['guidance_requested'] and s['contact_phase']=='approach'
