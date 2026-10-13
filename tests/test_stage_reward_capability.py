"""Score-only EDS and differentiable VLS capabilities share Stage semantics."""
import random
import numpy as np
import pytest
import torch

from core.stage_evidence import assess_reward, assess_reward_gradient, update_stage
from test_stage_evidence import fake_runner, outside, reward, state


@pytest.mark.parametrize("fn, reason", [
    (lambda k, p: reward(k, p).detach(), "reward_gradient_disconnected"),
    (lambda k, p: torch.round(p * 100).sum(), "reward_gradient_zero_on_probes"),
    (lambda k, p: torch.sqrt(p.square()).sum(), "reward_gradient_nonfinite"),
])
def test_variable_but_unusable_gradient_remains_valid_for_eds(fn, reason):
    assert assess_reward([fn], [[0., 0., 0.]])["available"]
    result = assess_reward_gradient([fn], [[0., 0., 0.]])
    assert not result["available"] and result["reason"] == reason


def test_zero_at_optimum_does_not_disable_vls():
    result = assess_reward_gradient([reward], [[0., 0., 0.]])
    assert result["available"]
    assert 0 < result["nonzero_probe_count"] < result["probe_count"]


def test_reward_of_fixed_initial_point_is_not_a_controllable_gradient():
    def initial_point_only(kp, path):
        return -(path[:, 0] - kp[0]).square().sum()
    assert assess_reward([initial_point_only], [[0., 0., 0.]])["available"]
    result = assess_reward_gradient([initial_point_only], [[0., 0., 0.]])
    assert not result["available"]
    assert result["reason"] == "reward_gradient_zero_on_probes"


def test_gradient_probe_restores_python_numpy_torch_rng():
    py, np_state, cpu = random.getstate(), np.random.get_state(), torch.get_rng_state()
    def fn(k, p):
        ignored = random.random() + np.random.random() + torch.rand(()).item()
        return reward(k, p) + ignored * 0
    assert assess_reward_gradient([fn], [[0., 0., 0.]])["available"]
    assert py == random.getstate()
    actual = np.random.get_state()
    assert np_state[0] == actual[0] and np.array_equal(np_state[1], actual[1]) and np_state[2:] == actual[2:]
    assert torch.equal(cpu, torch.get_rng_state())


@pytest.mark.parametrize("method", ["eds", "vls"])
def test_gradient_capability_only_gates_vls(method):
    runner = fake_runner([outside()])
    runner.policy_type = "rdt"
    runner.config["guidance_type"] = method
    runner.guidance_fns[1] = [lambda k, p: reward(k, p).detach()]
    s = state()
    update_stage(runner, s, -1.)
    capability = runner.events[0]["reward_capability"]
    assert s["use_guidance"] is (method == "eds")
    if method == "vls":
        assert capability["reason"] == "reward_gradient_disconnected"
    else:
        assert "gradient" not in capability


def test_eds_never_calls_gradient_capability(monkeypatch):
    runner = fake_runner([outside()])
    runner.policy_type = "rdt"
    runner.config["guidance_type"] = "eds"
    monkeypatch.setattr("core.stage_evidence.assess_reward_gradient", lambda *args, **kw: pytest.fail("EDS gradient probe"))
    update_stage(runner, state(), -1.)


@pytest.mark.parametrize("outer, internal, expected", [(.9, .1, "contact_grace"),
    (.1, .9, "approach"), (None, .9, "approach")])
def test_contact_decision_reads_only_common_outer_progress(outer, internal, expected):
    runner = fake_runner([outside()])
    runner.policy_type = "rdt"
    runner.config.update(guidance_type="vls", stage_controller="contact",
        contact_proximity_handoff_enabled=False, stage_preserve_reward_reference_on_guidance_toggle=True)
    runner.policy.get_stage_reward = lambda: outer
    runner.policy._last_normalized_reward = internal
    runner.policy.get_normalized_reward = lambda: pytest.fail("internal gradient reward leaked to Stage")
    runner.policy.reset_eds_chunk_memory = lambda reason: None
    s = state(global_step=32)
    update_stage(runner, s, -1.)
    assert s["contact_phase"] == expected
    assert runner.events[0]["normalized_reward_diagnostic"] == outer
    assert not runner.events[0]["reward_reference_reset"]
    assert runner.events[0]["reward_capability"]["gradient"]["available"]


def test_unguided_boundary_does_not_read_stale_outer_reward():
    runner = fake_runner([outside()])
    runner.config.update(stage_controller="contact", contact_proximity_handoff_enabled=False)
    runner.policy.get_stage_reward = lambda: pytest.fail("stale progress read")
    s = state(global_step=32, use_guidance=False)
    update_stage(runner, s, -1.)
    assert s["contact_phase"] == "approach"
    assert runner.events[0]["normalized_reward_diagnostic"] is None
