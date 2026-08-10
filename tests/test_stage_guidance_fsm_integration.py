from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


import main


class _Policy:
    def __init__(self):
        self.reset_stage_calls = 0
        self.reset_memory_reasons = []

    def get_normalized_reward(self):
        return 0.0

    def reset_stage(self):
        self.reset_stage_calls += 1

    def reset_eds_chunk_memory(self, reason):
        self.reset_memory_reasons.append(reason)


class _Adapter:
    def get_vlm_image(self):
        return np.zeros((2, 2, 3), dtype=np.uint8)

    def get_task_description(self):
        return "move the object"


class _ErrorRecognizer:
    config = {}

    def __init__(self):
        self.last_result = None

    def identify_stage_and_guidance(self, **kwargs):
        self.last_result = {
            "ok": False,
            "parse_ok": False,
            "raw_response": None,
            "parsed_stage": 1,
            "parsed_guidance": True,
            "evidence": "",
            "error": "service unavailable",
            "query_latency_s": 0.1,
        }
        return 1, True


class _AdversarialRecognizer:
    config = {}

    def __init__(self):
        self.last_result = None

    def identify_stage_and_guidance(self, **kwargs):
        self.last_result = {
            "ok": True,
            "parse_ok": True,
            "raw_response": "stage 0 guidance no",
            "parsed_stage": 0,
            "parsed_guidance": False,
            "evidence": "shadow only",
            "error": None,
            "query_latency_s": 0.1,
        }
        return 0, False


def _runner(tmp_path, recognizer):
    runner = main.Main.__new__(main.Main)
    runner.config = {
        "vlm_query_limit": 50,
        "eds_eval": {"output_dir": str(tmp_path)},
    }
    runner.output_dir = str(tmp_path)
    runner.policy = _Policy()
    runner.adapter = _Adapter()
    runner.gemini_stage_recognizer = recognizer
    runner.stage_descriptions = "Stage 1 grasp Stage 2 place"
    runner.init_img_with_keypoints = np.zeros((2, 2, 3), dtype=np.uint8)
    runner.keypoint_id_to_object = {0: "target", 1: "destination"}
    runner.guidance_fns = {1: [object()], 2: []}
    return runner


def _state():
    return {
        "prev_norm_reward": 0.0,
        "prev_gripper_open": True,
        "current_stage": 1,
        "use_guidance": True,
        "vlm_query_count": 0,
        "episode_id": 0,
        "task_id": 0,
        "global_step": 3,
        "chunk_id": 1,
        "episode_seed": 44,
        "previous_gripper_value": -1.0,
        "first_gripper_value": 1.0,
        "last_gripper_value": 1.0,
    }


def test_vlm_error_in_physical_mode_holds_state_and_action(tmp_path):
    runner = _runner(tmp_path, _ErrorRecognizer())
    action = torch.zeros((1, 8, 7))

    state = runner._update_stage(
        _state(), 1.0, 0.8, 0.6, advisory_only=True
    )

    assert state["current_stage"] == 1
    assert state["use_guidance"] is True
    assert runner.policy.reset_stage_calls == 0
    assert runner.policy.reset_memory_reasons == []
    assert torch.equal(action, torch.zeros_like(action))
    event = json.loads((tmp_path / "stage_events.jsonl").read_text().splitlines()[0])
    assert event["query_status"] == "error"
    assert event["advisory_only"] is True
    assert event["stage_after"] == event["stage_before"]


def test_vlm_shadow_replay_cannot_change_state_or_reset_control(tmp_path):
    runner = _runner(tmp_path, _AdversarialRecognizer())
    before = _state()

    after = runner._update_stage(
        dict(before), 1.0, 0.8, 0.6, advisory_only=True
    )

    assert after["current_stage"] == before["current_stage"]
    assert after["use_guidance"] == before["use_guidance"]
    assert after["last_vlm_advisory"]["parsed_stage"] == 0
    assert after["last_vlm_advisory"]["parsed_guidance"] is False
    assert runner.policy.reset_stage_calls == 0
    assert runner.policy.reset_memory_reasons == []


def test_fsm_transition_invalidates_remaining_chunk_and_both_memories():
    policy = _Policy()
    old_chunk = torch.ones((1, 8, 7))

    chunk, action_index = main._invalidate_chunk_for_fsm_transition(
        policy=policy,
        action_chunk=old_chunk,
        action_executed=3,
        state_before="GRASP_VERIFY",
        state_after="TRANSPORT",
    )

    assert chunk is None
    assert action_index == 0
    assert policy.reset_stage_calls == 1
    assert policy.reset_memory_reasons == ["physical_fsm_transition"]


def test_transition_mode_validation_accepts_only_frozen_paths():
    assert main._stage_transition_mode("legacy_vlm") == "legacy_vlm"
    assert main._stage_transition_mode("physical_fsm_v1") == "physical_fsm_v1"
    try:
        main._stage_transition_mode("physical_fsm_v2")
    except ValueError as exc:
        assert "legacy_vlm" in str(exc)
        assert "physical_fsm_v1" in str(exc)
    else:
        raise AssertionError("unsupported transition mode was accepted")
