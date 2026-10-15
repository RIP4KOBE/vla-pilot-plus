import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('prospective_handoff', Path(__file__).with_name('stage_contact_handoff.py'))
handoff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handoff)


def decision(*, reward, distance, proximity=True, stage=1):
    state = dict(current_stage=stage, guidance_requested=True, contact_phase='approach')
    config = dict(contact_proximity_handoff_enabled=proximity,
                  contact_require_measured_proximity=True,
                  contact_reward_max_distance_m=.10)
    handoff.apply_handoff(state, step=24, reward=reward, was_guided=True,
                         distance=distance, observation=None, config=config)
    return state


def test_recorded_bbq_step24_keeps_reaching_when_progress_is_below_threshold():
    state = decision(reward=.7972222222222223, distance=.05585495434406292, proximity=False)
    assert state['guidance_requested'] is True
    assert state['contact_phase'] == 'approach'


def test_current_proximity_behavior_is_preserved_when_enabled():
    state = decision(reward=.7972222222222223, distance=.05585495434406292)
    assert state['guidance_requested'] is False
    assert state['contact_trigger'] == 'current_keypoint_distance'


def test_reward_progress_still_allows_grasp_handoff_at_measured_proximity():
    state = decision(reward=.85, distance=.08, proximity=False)
    assert state['guidance_requested'] is False
    assert state['contact_trigger'] == 'fresh_guided_reward_progress'
    assert state['contact_until'] == 88


def test_large_reward_without_measured_proximity_does_not_handoff():
    assert decision(reward=.95, distance=.16, proximity=False)['guidance_requested'] is True


def test_semantic_transport_does_not_reenter_reaching():
    state = decision(reward=None, distance=.03, proximity=False, stage=2)
    assert state['current_stage'] == 2
    assert state['contact_phase'] == 'transport_or_completion_check'
