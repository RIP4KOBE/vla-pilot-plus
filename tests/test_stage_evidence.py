import ast
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import numpy as np
import pytest
import torch

from core.stage.controller import (parse_observation, decide, apply_guidance_gate,
    query_reason, assess_reward, settings, update_stage)
from core.gemini_grounder import create_gemini_stage_recognizer

ROOT = Path(__file__).resolve().parents[1]


def obs(**kwargs):
    return dict(target_visibility="clear", target_location="inside_goal",
                grasp="not_held", support="supported", evidence="visible placement", **kwargs)


def state(**kwargs):
    result = dict(current_stage=1, use_guidance=True, global_step=0, vlm_query_count=0)
    result.update(kwargs)
    return result


def outside():
    value = obs(); value["target_location"] = "outside_goal"
    return value


def reward(kp, path):
    return -(path - kp[0]).square().sum()


def zero(kp, path):
    return torch.tensor(0.)


def test_completion_needs_two_time_separated_observations_and_is_revocable():
    s = state()
    decide(s, obs(), 16)
    assert s["current_stage"] == 2 and not s["completion_confirmed"]
    decide(s, obs(), 16)
    decide(s, obs(), 24)
    assert s["completion_evidence_count"] == 1
    decide(s, obs(), 32)
    assert s["current_stage"] == 0 and s["completion_confirmed"]
    decide(s, outside(), 64)
    assert s["current_stage"] == 1 and s["guidance_requested"]
    assert not s["completion_confirmed"]


@pytest.mark.parametrize("field,value", [("target_visibility", "occluded"),
    ("target_location", "above_goal"), ("grasp", "held"), ("grasp", "unknown"), ("support", "unknown")])
def test_ambiguous_or_suspended_object_never_completes(field, value):
    observation = obs(); observation[field] = value
    s = state()
    for step in (0, 32, 64):
        decide(s, observation, step)
    assert s["current_stage"] != 0 and not s["completion_confirmed"]


def test_uncertainty_breaks_completion_confirmation_chain():
    s = state(); decide(s, obs(), 0)
    uncertain = obs(); uncertain["target_visibility"] = "occluded"
    decide(s, uncertain, 16); decide(s, obs(), 32)
    assert s["completion_evidence_count"] == 1 and s["current_stage"] != 0


def test_command_edges_survive_throttling_and_guidance_off_gets_rechecks():
    s = state(use_guidance=False, prev_gripper_open=True, last_vlm_query_step=0, global_step=8)
    assert query_reason(s, 1., {}) is None
    s["global_step"] = 16
    assert query_reason(s, 1., {}) == "gripper command closed"
    s.update(last_vlm_query_step=16, pending_gripper_trigger=None, current_stage=0, global_step=48)
    assert query_reason(s, 1., {}) == "periodic visual recheck"


@pytest.mark.parametrize("functions,expected", [([], False), ([zero], False),
    ([lambda k, p: torch.tensor(5.)], False), ([reward], True),
    ([reward, lambda k, p: -reward(k, p)], False),
    ([lambda k, p: torch.tensor(float('nan'))], False),
    ([lambda k, p: torch.zeros(3)], False),
    ([lambda k, p: torch.rand(())], False)])
def test_aggregate_reward_capability(functions, expected):
    rng = torch.get_rng_state().clone()
    result = assess_reward(functions, [[0., 0., 0.], [.3, .1, .2]])
    assert result["available"] is expected
    assert torch.equal(rng, torch.get_rng_state())


def test_zero_at_optimum_is_not_mistaken_for_constant_reward():
    assert reward(torch.zeros(1, 3), torch.zeros(1, 8, 3)) == 0
    assert assess_reward([reward], [[0., 0., 0.]])["available"]


def test_guidance_gate_respects_master_missing_constant_and_valid_stage2():
    s = state(current_stage=2, guidance_requested=True)
    apply_guidance_gate(s, {2: {"available": False, "reason": "constant_on_probes"}}, True)
    assert not s["use_guidance"]
    apply_guidance_gate(s, {2: {"available": True}}, True)
    assert s["use_guidance"]
    apply_guidance_gate(s, {2: {"available": True}}, False)
    assert not s["use_guidance"]


@pytest.mark.parametrize("text", ["stage 0\nguidance: no", "{}", "null",
    '{"target_visibility":"clear","target_visibility":"unknown"}',
    json.dumps(dict(obs(), guidance=True)), json.dumps(dict(obs(), grasp="yes"))])
def test_invalid_observation_has_no_legacy_fallback(text):
    with pytest.raises(ValueError):
        parse_observation(text)


def test_recognizer_uses_fact_prompt_captures_images_and_rejects_bad_reply(monkeypatch, tmp_path):
    import core.gemini_grounder as grounder
    requests = []
    def create(**kw):
        requests.append(kw)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(outside())))])
    monkeypatch.setattr(grounder, "_make_client", lambda _: SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    rec = create_gemini_stage_recognizer(dict(output_format="stage_observation_v1", capture_dir=str(tmp_path/'capture')))
    result = rec.observe_scene(current_rgb=np.zeros((4, 4, 3), dtype=np.uint8),
        init_img_with_keypoints=np.zeros((4, 4, 3), dtype=np.uint8), instruction="put target in basket",
        stage_descriptions="UNTRUSTED_OLD_STAGE_COMMANDS", trigger_reason="TRIGGER_MEANS_GRASPED")
    text = json.dumps(requests)
    assert "UNTRUSTED_OLD_STAGE_COMMANDS" not in text and "TRIGGER_MEANS_GRASPED" not in text
    assert result == outside() and rec.last_result["ok"]
    assert requests[0]['max_tokens'] == 2048
    assert (tmp_path/'capture/request_0000/image_02.png').is_file()
    rec._request_stage_response = lambda content: "stage 0\nguidance: no"
    assert rec.observe_scene(current_rgb=np.zeros((4,4,3),dtype=np.uint8),
        instruction="put target in basket", stage_descriptions="") is None
    assert not rec.last_result["ok"]


def test_explicit_length_finish_rejects_even_syntactically_valid_json(monkeypatch):
    import core.gemini_grounder as grounder
    response = SimpleNamespace(choices=[SimpleNamespace(finish_reason='length',
        message=SimpleNamespace(content=json.dumps(obs())))])
    monkeypatch.setattr(grounder, '_make_client', lambda _: SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: response))))
    rec = create_gemini_stage_recognizer({'output_format': 'stage_observation_v1'})
    assert rec.observe_scene(current_rgb=np.zeros((4,4,3),dtype=np.uint8),
                             instruction='put target in basket', stage_descriptions='') is None
    assert rec.last_result['completion_metadata']['finish_reason'] == 'length'
    assert not rec.last_result['ok']


def test_probe_cannot_enable_reward_with_invalid_live_keypoints():
    assert not assess_reward([reward], [[float('nan'), 0., 0.]])['available']
    assert not assess_reward([reward], None)['available']


def fake_runner(observations):
    events, resets = [], []
    iterator = iter(observations)
    rec = SimpleNamespace()
    def observe_scene(**kwargs):
        observation = next(iterator)
        rec.last_result = {"ok": observation is not None, "observation": observation}
        return observation
    rec.observe_scene = observe_scene
    return SimpleNamespace(config={"use_guidance": True}, stage_live_keypoints=np.zeros((1, 3)),
        policy=SimpleNamespace(_action_chunk_horizon=8, get_normalized_reward=lambda: .99,
                               reset_stage=lambda: resets.append(1)),
        guidance_fns={1: [reward], 2: [zero]}, gemini_stage_recognizer=rec,
        adapter=SimpleNamespace(get_vlm_image=lambda: np.zeros((4,4,3),dtype=np.uint8),
                                get_task_description=lambda: "put target in basket"),
        stage_descriptions="old instructions", init_img_with_keypoints=None, keypoint_id_to_object={},
        _append_stage_event=events.append, events=events, resets=resets)


def test_runtime_failed_grasp_after_guidance_off_reenables_valid_ed():
    runner = fake_runner([outside()])
    s = state(current_stage=2, use_guidance=False, global_step=64, last_vlm_query_step=32)
    update_stage(runner, s, -1.)
    assert s["current_stage"] == 1 and s["use_guidance"]
    assert runner.events[0]["normalized_reward_diagnostic"] is None
    assert len(runner.resets) == 1


def test_runtime_stage2_zero_reward_stays_off_but_queries_continue():
    held = obs(); held.update(grasp="held", support="unsupported", target_location="outside_goal")
    runner = fake_runner([held, outside()]); s = state()
    update_stage(runner, s, 1.)
    assert s["current_stage"] == 2 and not s["use_guidance"]
    assert runner.events[0]["guidance_gate_reason"] == "constant_on_probes"
    s["global_step"] = 32; update_stage(runner, s, 1.)
    assert s["current_stage"] == 1 and s["use_guidance"]
    assert s["vlm_query_count"] == 2


def test_runtime_malformed_reply_and_query_exhaustion_are_audited_errors():
    runner = fake_runner([None])
    with pytest.raises(RuntimeError, match="observation_failed"):
        update_stage(runner, state(), -1.)
    assert runner.events[0]["query_status"] == "error"
    runner.config["vlm_query_limit"] = 0
    with pytest.raises(RuntimeError, match="query_limit"):
        update_stage(runner, state(), -1.)


def test_runtime_master_disabled_never_queries_or_enables_ed():
    runner = fake_runner([]); runner.config["use_guidance"] = False
    s = state(); update_stage(runner, s, None)
    assert not s["use_guidance"] and s["vlm_query_count"] == 0


def method(name):
    tree = ast.parse((ROOT/'main.py').read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Main')
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    ns = {"Optional": Optional, "np": np, "log": logging.getLogger(__name__)}
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'main.py', 'exec'), ns)
    return ns[name]


def test_real_main_dispatch_and_last_executed_gripper_with_partial_chunk():
    runner = fake_runner([outside()]); runner.config['stage_controller'] = 'evidence'
    s = state(); method('_update_stage')(runner, s, None, .8, .6)
    assert s['use_guidance'] and runner.events[0]['controller_version'] == 'evidence'
    chunk = torch.zeros(1, 8, 7); chunk[0, 0, -1] = -1; chunk[0, 3, -1] = .8; chunk[0, 7, -1] = -.7
    runner._get_gripper_value = lambda action, index: float(action[0, index, -1])
    # Only a prefix of four actions actually executed; neither first nor last is correct.
    assert method('_stage_gripper_value')(runner, chunk, 0, .8) == .8
    runner.config['stage_controller'] = 'legacy'
    assert method('_stage_gripper_value')(runner, chunk, 0, .8) == -1.


def test_frozen_legacy_update_body_is_preserved():
    frozen = ROOT/'tests/fixtures/stage/legacy_stage_method.py.txt'
    def node(path):
        cls = next(n for n in ast.parse(path.read_text()).body if isinstance(n, ast.ClassDef) and n.name=='Main')
        return next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name=='_update_stage')
    old, new = node(frozen), node(ROOT/'main.py')
    del new.body[1]  # The only addition is the explicitly versioned dispatch.
    assert ast.dump(old) == ast.dump(new)
