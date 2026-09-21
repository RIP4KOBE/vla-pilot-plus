import importlib.util
from pathlib import Path

import torch

SPEC = importlib.util.spec_from_file_location('behavior_diagnostic', Path(__file__).parents[1] / 'scripts/qd_ed_executable_behavior_diagnostic.py')
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def test_zero_gripper_matches_deployed_decoder():
    action = torch.zeros(64, 128)
    action[1, 10] = -0.01
    assert MOD.gripper_sequence(action) == (1, -1, 1, 1, 1, 1, 1, 1)


def test_equal_reward_incumbent_loss_identifies_fingerprint_tie():
    incumbent = {'cell': 0, 'reward': 1, 'fingerprint': 'b', 'gripper': (-1,) * 8}
    candidate = {'cell': 0, 'reward': 1, 'fingerprint': 'a', 'gripper': (1,) * 8}
    archive = {0: incumbent}
    events = MOD.update_archive(archive, [candidate])
    assert archive[0] is candidate
    assert len(events) == 1 and events[0]['kind'] == 'incumbent_displaced'


def test_lower_reward_distinct_action_is_rejected_without_false_success_claim():
    incumbent = {'cell': 0, 'reward': 1, 'fingerprint': 'b', 'gripper': (-1,) * 8}
    candidate = {'cell': 0, 'reward': 0, 'fingerprint': 'a', 'gripper': (1,) * 8}
    archive = {0: incumbent}
    events = MOD.update_archive(archive, [candidate])
    assert archive[0] is incumbent
    assert len(events) == 1 and events[0]['kind'] == 'candidate_rejected'
