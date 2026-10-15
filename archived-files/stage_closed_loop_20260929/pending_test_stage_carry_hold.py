import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('candidate_carry_hold',Path(__file__).with_name('pending_stage_carry_hold.py'))
carry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(carry)


def evidence(z=.15, width=.04, distance=.05, no_grasp=False):
    return dict(geometry=dict(target_position=[0.,0.,z]),width_m=width,
                distance_m=distance,no_grasp=no_grasp)


def state():
    return dict(current_stage=2,visual_hold=True,visual_hold_since=0,carry_target_initial_z=.03)


def test_actual_carry_survives_old_timeout_but_stale_evidence_eventually_expires():
    s=state()
    assert not carry.update(s,step=72,evidence=evidence(),executed_gripper=1.)['refreshed']
    assert carry.update(s,step=80,evidence=evidence(),executed_gripper=1.)['refreshed']
    assert carry.expiry_anchor(s,{'physical_carry_hold_enabled':True})==80
    assert carry.expiry_anchor(s,{})==0  # Opt-in; historical TTL unchanged.
    for step in [88,160]:
        assert not carry.update(s,step=step,evidence=evidence(width=.08),executed_gripper=-1.)['refreshed']
    assert carry.expiry_anchor(s,{'physical_carry_hold_enabled':True})==80


@pytest.mark.parametrize('invalid',[
    evidence(z=.03), evidence(width=.001), evidence(width=.08),
    evidence(distance=.17), evidence(no_grasp=True), evidence(z=float('nan')),
    dict(geometry=None,width_m=.04,distance_m=.05,no_grasp=False),
])
def test_nearby_ground_object_empty_fingers_or_missing_measurement_cannot_renew(invalid):
    s=state()
    for step in [0,8,16,80]:
        assert not carry.update(s,step=step,evidence=invalid,executed_gripper=1.)['refreshed']
    assert 'physical_carry_hold_step' not in s


@pytest.mark.parametrize('override',[
    {'visual_hold':False}, {'current_stage':1}, {'completion_confirmed':True},
    {'empty_release_until':32}, {'payload_release_until':32},
])
def test_refresh_cannot_establish_grasp_change_stage_or_override_release(override):
    s=state();s.update(override)
    before={k:s.get(k) for k in ['visual_hold','current_stage','completion_confirmed','empty_release_until','payload_release_until']}
    for step in [0,8,16]:
        assert not carry.update(s,step=step,evidence=evidence(),executed_gripper=1.)['refreshed']
    assert before=={k:s.get(k) for k in before}


def test_gap_in_physical_evidence_restarts_confirmation():
    s=state()
    carry.update(s,step=0,evidence=evidence(),executed_gripper=1.)
    carry.update(s,step=8,evidence=evidence(),executed_gripper=-1.)
    assert not carry.update(s,step=16,evidence=evidence(),executed_gripper=1.)['refreshed']
    assert carry.update(s,step=24,evidence=evidence(),executed_gripper=1.)['refreshed']


def test_initial_target_height_is_fixed_instead_of_following_the_lift():
    s=dict(current_stage=1,visual_hold=False)
    carry.update(s,step=0,evidence=evidence(z=.2),executed_gripper=-1.)
    s.update(current_stage=2,visual_hold=True,visual_hold_since=8)
    assert not carry.update(s,step=8,evidence=evidence(z=.22),executed_gripper=1.)['present']
    carry.update(s,step=16,evidence=evidence(z=.25),executed_gripper=1.)
    assert carry.update(s,step=24,evidence=evidence(z=.25),executed_gripper=1.)['refreshed']
    assert s['carry_target_initial_z']==.2


def test_visual_false_positive_without_lift_cannot_block_policy_open():
    s=state();cfg={'physical_carry_hold_enabled':True,'grasp_hold_max_steps':80}
    for step in [0,8,16,32]:
        carry.update(s,step=step,evidence=evidence(z=.03),executed_gripper=1.)
        assert not carry.permit_hold(s,step=step,config=cfg)
    assert carry.permit_hold(s,step=32,config={})  # Disabled preserves legacy guard.


def test_confirmed_carry_can_be_protected_during_short_occlusion_not_after_failure():
    s=state();cfg={'physical_carry_hold_enabled':True,'grasp_hold_max_steps':80}
    for step in [0,8]:
        carry.update(s,step=step,evidence=evidence(),executed_gripper=1.)
    assert carry.permit_hold(s,step=16,config=cfg)
    assert not carry.permit_hold(s,step=88,config=cfg)
    s['visual_hold']=False
    carry.update(s,step=24,evidence=evidence(no_grasp=True),executed_gripper=1.)
    assert not carry.permit_hold(s,step=24,config=cfg)
    s.update(visual_hold=True,visual_hold_since=32)
    assert not carry.permit_hold(s,step=32,config=cfg)


def test_raw_negative_is_preserved_but_contradictory_control_grasp_becomes_unknown():
    s=state();raw=dict(grasp='not_held',target_visibility='clear',target_location='outside_goal',support='supported',evidence='Wrong object on floor.')
    carry.observe(s,step=0,evidence=evidence(),executed_gripper=1.)
    cue=carry.observe(s,step=8,evidence=evidence(),executed_gripper=1.)
    filtered,reason=carry.filter_observation(raw,s,cue)
    assert raw['grasp']=='not_held' and filtered['grasp']=='unknown'
    assert reason=='negative_visual_grasp_conflicts_with_measured_carry'
    assert {k:v for k,v in raw.items() if k!='grasp'}=={k:v for k,v in filtered.items() if k!='grasp'}


@pytest.mark.parametrize('override,measurement,command',[
    ({'current_stage':1},evidence(),1.),
    ({'visual_hold':False},evidence(),1.),
    ({'empty_release_until':32},evidence(),1.),
    ({'payload_release_until':32},evidence(),1.),
    ({},evidence(no_grasp=True),1.),
    ({},evidence(width=.001),1.),
    ({},evidence(),-1.),
])
def test_physical_failure_or_release_cannot_be_overruled_by_old_hold(override,measurement,command):
    s=state();s.update(override)
    raw=dict(grasp='not_held')
    carry.observe(s,step=0,evidence=measurement,executed_gripper=command)
    cue=carry.observe(s,step=8,evidence=measurement,executed_gripper=command)
    filtered,reason=carry.filter_observation(raw,s,cue)
    assert filtered==raw and reason is None
