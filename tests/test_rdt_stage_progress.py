"""CPU coverage for the shared outer reward and truthful VLS observations."""
import json
import random
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from test_rdt_steer import _patch_core_imports, stub_steer, stub_adapter, mock_batch


@pytest.fixture(autouse=True)
def preserve_rng():
    assert not torch.cuda.is_initialized()
    py, np_state, cpu = random.getstate(), np.random.get_state(), torch.get_rng_state()
    yield
    random.setstate(py)
    np.random.set_state(np_state)
    torch.set_rng_state(cpu)
    assert not torch.cuda.is_initialized()


def prepare(steer, adapter, batch_size=4):
    steer.post_init(adapter=adapter, postprocessor=lambda x: x,
                   sample_batch_size=batch_size, policy_config={"action_chunk_horizon": 8})


def reward(kp, path):
    return -(path - kp[0]).square().sum()


def sample(steer, batch, **overrides):
    cfg = dict(sample_batch_size=4, use_diversity=True, diversity_scale=1.,
               guide_scale=1., start_ratio=.4, use_fkd=True,
               fkd=dict(potential_type="max", lmbda=1., adaptive_resampling=False,
                        resample_frequency=1))
    cfg.update(overrides)
    return steer.select_action(batch, generate_new_chunk=True, use_guidance=True,
        guidance_type="vls", vls_config=cfg, keypoints=np.zeros((1, 3), dtype=np.float32),
        guidance_fns=[reward])


def test_shared_getter_preserves_eds_reference_rng_and_counters(stub_steer):
    p = stub_steer
    p._stage_reward_guidance_type = "eds"
    p._stage_init_reward, p._last_normalized_reward = -5., .875
    p._vls_stage_progress = .2
    before, rng = p.get_episode_compute_counters(), torch.get_rng_state()
    assert p.get_stage_reward() == p.get_normalized_reward() == .875
    assert p.get_last_vls_metrics() is None
    assert p._stage_init_reward == -5.
    assert before == p.get_episode_compute_counters()
    assert torch.equal(rng, torch.get_rng_state())
    p.reset_stage()
    assert p._stage_init_reward is None
    assert p.get_stage_reward() == .875  # accepted stale-value semantics; Stage gates freshness


def test_outer_selected_reference_is_independent_and_resets(stub_steer, monkeypatch):
    p = stub_steer
    p._stage_reward_guidance_type = "vls"
    p._stage_init_reward, p._last_raw_reward, p._last_normalized_reward = -80., -20., .75
    p._vls_metrics_work = {}
    values = iter([torch.tensor([-10., -2.]), torch.tensor([-8., -.2])])
    calls = []
    def score(samples, *args, **kwargs):
        calls.append(len(samples))
        return next(values)
    monkeypatch.setattr(p, "_score_particles", score)
    particles = torch.arange(2 * 64 * 128, dtype=torch.float32).reshape(2, 64, 128)
    for expected in (0., .9):
        selected = p._select_particle_for_execution(particles, keypoints=torch.zeros(1, 3),
                                                   guidance_fns=[reward], fkd=None)
        assert torch.equal(selected, particles[1:2])
        assert p.get_stage_reward() == pytest.approx(expected)
    assert calls == [2, 2]  # reuse argmax score; no extra final score call
    assert p._vls_stage_reward_reference == -2.
    assert (p._stage_init_reward, p._last_raw_reward, p.get_normalized_reward()) == (-80., -20., .75)
    p.reset_stage()
    assert p.get_stage_reward() is None
    assert p._vls_stage_reward_reference is None and p._stage_init_reward is None
    p.reset()
    assert p.get_last_vls_metrics() is None and p.get_stage_reward() == 0.


@pytest.mark.parametrize("terminal", [False, True])
def test_unscored_selection_gets_one_outer_score_without_changing_choice(stub_steer, monkeypatch, terminal):
    p = stub_steer
    p._vls_metrics_work = {}
    population = torch.randn(3 if terminal else 1, 64, 128)
    calls = []
    def score(selected, *args, **kwargs):
        calls.append(selected.clone())
        return torch.tensor([-3.])
    monkeypatch.setattr(p, "_score_particles", score)
    result = p._select_particle_for_execution(population, keypoints=torch.zeros(1, 3),
        guidance_fns=[reward], fkd=SimpleNamespace(reached_terminal=True) if terminal else None)
    assert len(calls) == 1 and torch.equal(calls[0], population[:1])
    assert torch.equal(result, population[:1])
    assert p._vls_metrics_work["selection"]["score_source"] == "extra_selected_score"


@pytest.mark.parametrize("failure", ["nonfinite", "exception", "missing"])
def test_invalid_new_outer_score_does_not_change_selected_action(stub_steer, monkeypatch, failure):
    p = stub_steer
    p._stage_reward_guidance_type = "vls"
    p._vls_stage_progress = .95
    p._vls_stage_reward_reference = -7.
    p._last_normalized_reward = .99
    p._vls_metrics_work = {}
    def score(*args, **kwargs):
        if failure == "exception":
            raise ValueError("unscorable")
        return torch.tensor([float("nan")])
    monkeypatch.setattr(p, "_score_particles", score)
    particle = torch.zeros(1, 64, 128)
    result = p._select_particle_for_execution(particle, keypoints=torch.zeros(1, 3),
        guidance_fns=[] if failure == "missing" else [reward], fkd=None)
    assert result is particle
    assert p.get_stage_reward() is None and p._vls_stage_reward_reference == -7.
    assert not p._vls_metrics_work["selection"]["score_valid"]
    assert p.get_normalized_reward() == .99


def test_real_vls_loop_observes_gradients_rbf_fkd_selection_and_cache(stub_steer, stub_adapter, mock_batch):
    p = stub_steer
    prepare(p, stub_adapter)
    action = sample(p, mock_batch)
    metrics = p.get_last_vls_metrics()
    json.dumps(metrics, allow_nan=False)
    assert action.shape == (1, 8, 7)
    assert metrics["schema"] == "rdt_vls_metrics_v1"
    assert metrics["sample_batch_size_observed"] == 4
    assert metrics["denoising_steps_executed"] == 5
    assert metrics["gradient"]["attempted"] == metrics["gradient"]["applied"] == 3
    assert metrics["rbf"]["attempted"] == metrics["rbf"]["applied"] == 2
    assert all(event["norm"] > 0 for event in metrics["gradient"]["events"])
    fkd = metrics["fkd"]["diagnostics"]
    assert fkd["calls"] == fkd["score_opportunities"] == fkd["actual_resamples"] == 2
    assert all(len(e["parent_indices"]) == 4 for e in fkd["events"])
    assert metrics["selection"]["source"] == "reward_argmax"
    assert len(metrics["selection"]["action_chunk_fingerprint"]) == 64
    assert metrics["outer_reward"]["reference"] == metrics["selection"]["raw_score"]
    assert p.get_stage_reward() == 0.
    assert metrics["compute_delta"]["model_forward_calls"] == 5
    assert metrics["compute_delta"]["model_batch_rows"] == 20
    assert metrics["compute_delta"]["guided_chunks"] == 1
    before, rng = p.get_episode_compute_counters(), torch.get_rng_state()
    cached = p.select_action(mock_batch, generate_new_chunk=False, use_guidance=True)
    assert cached is action and before == p.get_episode_compute_counters()
    metrics["gradient"]["events"].clear()
    assert p.get_last_vls_metrics()["gradient"]["events"]
    assert torch.equal(rng, torch.get_rng_state())
    p.select_action(mock_batch, generate_new_chunk=True, use_guidance=False)
    assert p.get_last_vls_metrics() is None


def test_actual_gradient_zero_at_optimum_is_valid_observation(stub_steer, stub_adapter):
    p = stub_steer
    prepare(p, stub_adapter)
    p._vls_metrics_work = {"gradient": dict(zero=0, nonfinite=0, exception=0, unavailable=0, events=[])}
    grad, value = p._compute_keypoint_gradient(torch.zeros(2, 64, 128), torch.zeros(1, 3), [reward])
    assert value == 0 and grad is not None and not grad.any()
    assert p._vls_metrics_work["gradient"]["zero"] == 1
    assert p._vls_metrics_work["gradient"]["nonfinite"] == 0


@pytest.mark.parametrize("adaptive", [False, True])
def test_fkd_diagnostics_preserve_rng_and_equal_particle_actions(adaptive):
    from core.fkd_class import FKD
    population = torch.ones(4, 2, 3)
    def run(record):
        with torch.random.fork_rng(devices=[]):
            torch.random.default_generator.manual_seed(811)
            fkd = FKD(potential_type="max", lmbda=1., num_particles=4,
                adaptive_resampling=adaptive, resample_frequency=1,
                resampling_t_start=2, resampling_t_end=0, timesteps=[2, 1, 0],
                reward_fn=lambda x: torch.zeros(4), reward_min_value=float("-inf"),
                device="cpu", record_diagnostics=record)
            outputs = [fkd.resample(sampling_idx=t, latents=population, x0_preds=population)[0] for t in [2, 1, 0]]
            return outputs, torch.get_rng_state(), fkd.get_diagnostics()
    plain, rng0, _ = run(False)
    observed, rng1, diag = run(True)
    assert all(torch.equal(a, b) for a, b in zip(plain, observed))
    assert torch.equal(rng0, rng1)
    assert diag["actual_resamples"] == (1 if adaptive else 3)
    assert diag["ess_skips"] == (2 if adaptive else 0)
    assert diag["score_opportunities"] == 3
    assert all(torch.equal(item, population) for item in observed)
