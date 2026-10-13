import copy
import torch
from test_stage_payload_runtime import setup
from core.stage_grasp_guard import apply_to_action


def test_passthrough_preserves_every_action_component_and_logs_suppressed_hold():
    runner,state,journal = setup(False)
    runner.config['grasp_action_guard_enabled'] = False
    chunk = torch.tensor([[[.1,.2,.3,.4,.5,.6,-1.]]])
    expected = chunk.clone()
    actual = apply_to_action(runner,state,chunk,0,97)
    assert torch.equal(actual,expected) and torch.equal(chunk,expected)
    assert journal[-1]['reason'] == 'policy_gripper_passthrough'
    assert not journal[-1]['override']
    assert journal[-1]['proposed_gripper_command'] == 1.
    assert journal[-1]['proposed_gripper_reason'] == 'hold_visible_target_outside_destination'


def test_passthrough_does_not_force_release_dwell_over_native_close():
    runner,state,journal = setup(True)
    runner.config['grasp_action_guard_enabled'] = False
    opening = torch.tensor([[[.1,.2,.3,.4,.5,.6,-1.]]])
    apply_to_action(runner,state,opening,0,97)
    closing = opening.clone()
    closing[0,0,-1] = 1.
    actual = apply_to_action(runner,state,closing,0,104)
    assert torch.equal(actual,closing)
    assert journal[-1]['proposed_gripper_command'] == -1.
    assert journal[-1]['proposed_gripper_reason'] == 'complete_policy_requested_payload_release'
    assert not journal[-1]['override']


def test_default_and_explicit_enabled_behavior_remain_identical():
    r1,s1,j1 = setup(True)
    r2,s2,j2 = setup(True)
    r2.config['grasp_action_guard_enabled'] = True
    for step,raw in [(97,-1.),(104,1.),(105,1.)]:
        chunk = torch.tensor([[[.1,.2,.3,.4,.5,.6,raw]]])
        assert torch.equal(apply_to_action(r1,s1,chunk,0,step),apply_to_action(r2,s2,chunk,0,step))
        assert s1 == s2 and j1 == j2
