import numpy as np
from types import SimpleNamespace
from core.stage_release_guard import aligned_payload,apply,payload_geometry


def geometry(target=(-.0678,.3037,.1666)):
    return dict(target_position=list(target),goal_low=[-.0820,.1811,.027],goal_high=[.0607,.3234,.139])


def call(s,raw=-1.,step=97,geo=None,width=.035,distance=.05):
    return apply(s,raw,1.,'hand_center_outside',step=step,width=width,distance=distance,
                 geometry=geometry() if geo is None else geo,config={})


def test_recorded_payload_inside_while_hand_guard_blocks_policy_release():
    # Values from full online task 8 at step 96. The arm center was outside the
    # guard region; the target was inside and lifted above the basket rim.
    s={'current_stage':2,'visual_hold':True}
    assert call(s)==(-1.,'allow_policy_release_payload_over_destination')
    assert s['payload_release_until']==105
    assert call(s,raw=1.,step=104)[0]==-1.
    assert call(s,raw=1.,step=105)[0]==1.


def test_never_initiates_open_or_claims_completion():
    s={'current_stage':2,'visual_hold':True}
    assert call(s,raw=1.)[0]==1.
    assert 'payload_release_until' not in s and s['current_stage']==2


def test_outside_tabletop_and_empty_fingers_do_not_trigger_release():
    for geo in [geometry((-.14,.3,.17)),geometry((-.06,.3,.027))]:
        assert call({'current_stage':2,'visual_hold':True},geo=geo)[0]==1.
    for width in [.002,.079,None]:
        assert call({'current_stage':2,'visual_hold':True},width=width)[0]==1.
    assert call({'current_stage':1,'visual_hold':True})[0]==1.
    assert call({'current_stage':2,'visual_hold':False})[0]==1.


def test_payload_geometry_uses_instructed_target_and_translates_with_scene():
    kp=np.array([[-.0678,.3037,.1666],[-.082,.1811,.027],[.0607,.3234,.139]])
    runner=SimpleNamespace(adapter=SimpleNamespace(get_task_description=lambda:'pick up the chocolate pudding and place it in the basket'),
        keypoint_id_to_object={0:'chocolate_pudding_1_main',1:'basket_1_main',2:'basket_1_main'},stage_live_keypoints=kp)
    assert aligned_payload(payload_geometry(runner))
    runner.stage_live_keypoints=kp+np.array([1.,-2.,.5])
    assert aligned_payload(payload_geometry(runner))
