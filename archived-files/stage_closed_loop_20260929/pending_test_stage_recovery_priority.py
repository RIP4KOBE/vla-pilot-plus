from core.stage_robot_evidence import apply_recovery, enforce_recovery_priority
from core.stage_contact_handoff import apply_handoff


def test_failed_grasp_reacquisition_wins_even_inside_reopen_cooldown():
    state={'current_stage':1,'guidance_requested':False,'robot_recovery_step':288,
           'contact_until':352,'contact_phase':'contact_grace','recovery_approach_since':288}
    evidence={'no_grasp':True,'outside_goal':True,'no_grasp_reasons':['open_fingers_far_from_target']}
    apply_recovery(state,evidence,328)
    apply_handoff(state,step=328,reward=None,was_guided=False,distance=.14397,observation=None,config={})
    assert enforce_recovery_priority(state,evidence,328)
    assert state['guidance_requested'] and state['contact_phase']=='approach'
    assert state['contact_until'] is None
    assert state['robot_recovery_step']==288  # no extra physical reopen pulse


def test_persistent_empty_grasp_does_not_extend_reopening_window():
    state={'current_stage':1,'guidance_requested':True}
    evidence={'no_grasp':True,'outside_goal':True,'no_grasp_reasons':['empty_closed_fingers']}
    apply_recovery(state,evidence,0)
    assert state['empty_release_until']==16
    for step in [8,16,24,32,40,48,56]:
        apply_recovery(state,evidence,step)
        apply_handoff(state,step=step,reward=.9,was_guided=True,distance=.03,observation=None,config={})
        enforce_recovery_priority(state,evidence,step)
        assert state['guidance_requested'] and state['empty_release_until']==16


def test_non_conflicting_observations_preserve_every_state_field():
    for state,evidence in [
        ({'current_stage':1,'contact_phase':'approach','contact_until':None,'recovery_approach_since':16},
         {'no_grasp':True,'outside_goal':True}),
        ({'current_stage':1,'contact_phase':'contact_grace','contact_until':96,'guidance_requested':False},
         {'no_grasp':False,'outside_goal':True}),
        ({'current_stage':2,'contact_phase':'transport_or_completion_check'},
         {'no_grasp':True,'outside_goal':False})]:
        before=dict(state)
        assert not enforce_recovery_priority(state,evidence,40)
        assert state==before
