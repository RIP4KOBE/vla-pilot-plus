"""
CPU-only smoke tests for RDTSteer and RDTLiberoObsProcessor.
No real checkpoint or GPU required — uses stub RDT model.
"""
import inspect
import json
import math
import sys
from dataclasses import FrozenInstanceError, asdict, dataclass, field
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import numpy as np
import pytest
import torch
import yaml
from PIL import Image
from torch import nn


class _BaseEnvAdapter:
    pass


class _LiberoAdapter(_BaseEnvAdapter):
    def delta_actions_to_ee_trajectory(self, seq):
        start = torch.zeros(1, 3, device=seq.device, dtype=seq.dtype)
        deltas = torch.cumsum(seq[:, :3], dim=0)
        return torch.cat([start, deltas], dim=0)


@pytest.fixture(autouse=True)
def _patch_core_imports(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    saved_core_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "core" or name.startswith("core.")
    }

    monkeypatch.syspath_prepend(str(root))
    for name in list(saved_core_modules):
        monkeypatch.delitem(sys.modules, name, raising=False)

    core_pkg = ModuleType("core")
    core_pkg.__path__ = [str(root / "core")]
    monkeypatch.setitem(sys.modules, "core", core_pkg)

    env_adapters = ModuleType("core.env_adapters")
    env_adapters.BaseEnvAdapter = _BaseEnvAdapter
    monkeypatch.setitem(sys.modules, "core.env_adapters", env_adapters)

    libero_adapter = ModuleType("core.env_adapters.libero_adapter")
    libero_adapter.LiberoAdapter = _LiberoAdapter
    monkeypatch.setitem(sys.modules, "core.env_adapters.libero_adapter", libero_adapter)

    if not (root / "core" / "eds_eval_metrics.py").exists():
        eds_eval_metrics = ModuleType("core.eds_eval_metrics")

        @dataclass
        class EDSIterMetrics:
            iter_idx: int
            n_trunc_steps: int
            best_idx: int
            best_cost: float
            best_reward: float
            mean_reward: float
            reward_spread: float
            score_entropy: float
            unique_parent_ratio: float
            population_diversity: float

        @dataclass
        class EDSChunkMetrics:
            episode: int | None = None
            global_step: int | None = None
            task_id: int | None = None
            suite: str | None = None
            guidance_type: str = "eds"
            reward_mode: str = "normal"
            population_size: int = 0
            cem_iters: int = 0
            use_cem: bool = False
            temperature: float = 0.0
            eds_enter_count: int = 0
            score_call_count: int = 0
            resample_count: int = 0
            renoise_count: int = 0
            rollout_count: int = 0
            population_size_observed: int = 0
            population_shape: list[int] = field(default_factory=list)
            score_shape: list[int] = field(default_factory=list)
            initial_best_reward: float | None = None
            final_best_reward: float | None = None
            initial_mean_reward: float | None = None
            final_mean_reward: float | None = None
            reward_spread: float | None = None
            selected_reward: float | None = None
            selected_cost: float | None = None
            selected_idx: int | None = None
            score_entropy: float | None = None
            unique_parent_ratio_mean: float | None = None
            population_diversity_initial: float | None = None
            population_diversity_final: float | None = None
            target_distance_before: float | None = None
            target_distance_after: float | None = None
            action_mask_violation_max: float = 0.0
            nonfinite_count: int = 0
            select_action_latency_s: float | None = None
            eds_loop_latency_s: float | None = None
            per_iter: list[EDSIterMetrics] = field(default_factory=list)

            def to_jsonable(self):
                return asdict(self)

        eds_eval_metrics.EDSIterMetrics = EDSIterMetrics
        eds_eval_metrics.EDSChunkMetrics = EDSChunkMetrics
        monkeypatch.setitem(sys.modules, "core.eds_eval_metrics", eds_eval_metrics)

    yield

    for name in list(sys.modules):
        if (name == "core" or name.startswith("core.")) and name not in saved_core_modules:
            sys.modules.pop(name, None)


# ── Stub RDT model (replaces the real 1.2B-param checkpoint) ────────────────

class _StubDiT(nn.Module):
    """Minimal DiT stand-in: returns zeros with the correct shape."""

    def __init__(self):
        super().__init__()
        self.calls = []

    def forward(self, x, t, cond):
        action_mask = cond["action_mask"]
        self.calls.append((tuple(x.shape), tuple(action_mask.shape)))
        assert x.shape[-1] == 128
        assert action_mask.shape[-1] == 128
        return torch.zeros_like(x)


class _StubScheduler:
    """Minimal noise scheduler compatible with DPMSolverMultistepScheduler API."""

    def __init__(self, n=5):
        self.timesteps = torch.arange(n - 1, -1, -1, dtype=torch.long)
        self.alphas_cumprod = torch.linspace(0.9, 0.1, n)
        self.last_step_args = []

    def set_timesteps(self, n):
        self.timesteps = torch.arange(n - 1, -1, -1, dtype=torch.long)
        self.alphas_cumprod = torch.linspace(0.9, 0.1, n)

    def step(self, model_output, t, x_t):
        self.last_step_args.append((model_output.detach().clone(), int(t.item()) if torch.is_tensor(t) else int(t)))
        out = MagicMock()
        # Accumulate updates so guidance injections remain observable across denoising steps.
        out.prev_sample = x_t + model_output.clone()
        out.pred_original_sample = None
        return out

    def add_noise(self, original_samples, noise, timesteps):
        if torch.is_tensor(timesteps):
            scale = timesteps.to(device=original_samples.device, dtype=original_samples.dtype)
            while scale.ndim < original_samples.ndim:
                scale = scale.unsqueeze(-1)
            scale = scale / max(len(self.timesteps), 1)
        else:
            scale = float(timesteps) / max(len(self.timesteps), 1)
        return original_samples + noise * scale


class _StubRDTModel(nn.Module):
    """Minimal stand-in for RoboticDiffusionTransformerModel."""

    def __init__(self):
        super().__init__()
        self.dit = _StubDiT()
        self.noise_scheduler = _StubScheduler()
        self.encode_calls = 0

    def encode_inputs(self, state_128, state_mask_128, images, text_embeds):
        self.encode_calls += 1
        action_mask = torch.zeros_like(state_mask_128, dtype=torch.float32)
        action_mask[0, [39, 40, 41, 42, 43, 44, 10]] = 1.0
        return {
            "lang_cond": torch.zeros(1, 1, 4),
            "lang_attn_mask": torch.ones(1, 1, dtype=torch.bool),
            "img_cond": torch.zeros(1, 1, 4),
            "state_traj": torch.zeros(1, 1, 4),
            "action_mask": action_mask.unsqueeze(1),
            "ctrl_freqs": torch.tensor([20]),
            "action_indices": [39, 40, 41, 42, 43, 44, 10],
            "unified_action_dim": 128,
        }


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def stub_steer():
    from core.rdt_policy_steer import RDTSteer
    return RDTSteer(rdt_model=_StubRDTModel(), num_inference_steps=5)


@pytest.fixture
def stub_adapter():
    return _LiberoAdapter()


@pytest.fixture
def mock_batch():
    return {
        "agentview_image": _image(255, 0, 0),
        "robot0_eye_in_hand_image": _image(0, 255, 0),
        "robot0_joint_pos": np.array([0.10, -0.20, 0.80, 0.0, 0.0, 0.0, 0.04], dtype=np.float32),
        "robot0_gripper_qpos": np.array([-0.04245, 0.05185], dtype=np.float32),
        "task": "pick up the red block",
    }


def _image(red, green, blue):
    image = np.zeros((8, 8, 3), dtype=np.uint8)
    image[..., 0] = red
    image[..., 1] = green
    image[..., 2] = blue
    return image


def _raw_obs(agent_rgb=(255, 0, 0), wrist_rgb=(0, 255, 0), task="pick up the red block"):
    return {
        "agentview_image": _image(*agent_rgb),
        "robot0_eye_in_hand_image": _image(*wrist_rgb),
        "robot0_joint_pos": np.array([0.10, -0.20, 0.80, 0.0, 0.0, 0.0, 0.04], dtype=np.float32),
        "robot0_gripper_qpos": np.array([-0.04245, 0.05185], dtype=np.float32),
        "task": task,
    }


def _deterministic_diversity_sample():
    sample = torch.zeros(3, 64, 128, dtype=torch.float32)
    sample[0, :4, 39] = 0.05
    sample[1, :4, 39] = -0.10
    sample[1, :4, 40] = 0.05
    sample[2, :4, 39] = 0.20
    sample[2, :4, 40] = -0.15
    return sample


def _trajectory_spread(steer, sample):
    traj = steer._rdt_sample_to_trajectory_3d(sample)[:, 1:, :3]
    flat = traj.reshape(traj.shape[0], -1)
    return torch.pdist(flat).mean()


def _endpoint_spread(steer, sample):
    endpoints = steer._rdt_sample_to_trajectory_3d(sample)[:, -1, :3]
    return torch.pdist(endpoints).mean()


def _rollout_cond(steer):
    cond = steer._rdt_model.encode_inputs(
        torch.zeros(1, 128),
        torch.zeros(1, 128).scatter(1, torch.tensor([[0]]), 1.0),
        [],
        torch.zeros(1, 1, 4),
    )
    cond["action_mask"][0, 0, [39, 40, 41, 42, 43, 44, 10]] = 1.0
    return cond


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_instantiation(stub_steer):
    """RDTSteer has the correct interface attributes."""
    assert stub_steer.name == "rdt_steer"
    assert isinstance(stub_steer._action_chunk_horizon, int)
    assert isinstance(stub_steer.get_normalized_reward(), float)
    assert isinstance(stub_steer.get_last_scale(), float)
    stub_steer.reset()          # must not raise
    stub_steer.reset_stage()    # must not raise


def test_from_pretrained_defaults_use_model_ids():
    from core.rdt_policy_steer import RDTSteer

    signature = inspect.signature(RDTSteer.from_pretrained)

    assert signature.parameters["text_encoder"].default == "google/t5-v1_1-xxl"
    assert signature.parameters["vision_encoder"].default == "google/siglip-so400m-patch14-384"


def test_forward_shape(stub_steer, stub_adapter, mock_batch):
    """select_action with use_guidance=False returns tensor of shape (H, 7)."""
    H = 8
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"action_chunk_horizon": H},
    )
    action = stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=False,
    )
    assert action.shape == (1, H, 7), f"Expected (1, {H}, 7), got {action.shape}"
    assert not torch.isnan(action).any()
    assert stub_steer._rdt_model.encode_calls == 1


def test_lang_embed_fail_fast_rejects_stub_zero_fallback(stub_steer, stub_adapter):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"fail_on_zero_language_embedding": True},
    )

    with pytest.raises(RuntimeError, match="zero language embedding"):
        stub_steer._get_lang_embed("pick up the red block")


def test_unguided_uses_full_128d_libero_mask(stub_steer, stub_adapter, mock_batch):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"action_chunk_horizon": 8, "debug_first_step": True},
    )
    converted = stub_steer._obs_processor.process(mock_batch)
    assert converted.state_128.shape == (1, 128)
    assert converted.state_mask_128.shape == (1, 128)
    assert torch.where(converted.state_mask_128[0] > 0)[0].tolist() == [0, 1, 2, 3, 4, 5, 6, 10, 11]
    assert converted.task == "pick up the red block"

    raw = stub_steer._predict_unguided(
        converted.state_128,
        converted.state_mask_128,
        converted.images,
        torch.zeros(1, 1, 4096),
        B=1,
    )
    assert raw.shape == (1, 64, 128)
    assert stub_steer._rdt_model.dit.calls
    for latent_shape, mask_shape in stub_steer._rdt_model.dit.calls:
        assert latent_shape == (1, 64, 128)
        assert mask_shape[-1] == 128


def test_unguided_select_action_uses_single_gt_batch_not_sample_particles(stub_steer, stub_adapter, mock_batch):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 8},
    )

    stub_steer.select_action(mock_batch, generate_new_chunk=True, use_guidance=False)

    assert stub_steer._rdt_model.dit.calls
    for latent_shape, _ in stub_steer._rdt_model.dit.calls:
        assert latent_shape[0] == 1


def test_select_action_observes_every_step_but_samples_only_when_buffer_empty(stub_steer, stub_adapter):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 2},
    )

    first = _raw_obs(agent_rgb=(255, 0, 0), wrist_rgb=(0, 255, 0), task="first")
    second = _raw_obs(agent_rgb=(0, 0, 255), wrist_rgb=(255, 255, 0), task="second")
    third = _raw_obs(agent_rgb=(10, 20, 30), wrist_rgb=(40, 50, 60), task="third")

    first_chunk = stub_steer.select_action(first, generate_new_chunk=True, use_guidance=False)
    assert stub_steer._rdt_model.encode_calls == 1

    reused_chunk = stub_steer.select_action(second, generate_new_chunk=False, use_guidance=False)
    assert reused_chunk is first_chunk
    assert stub_steer._rdt_model.encode_calls == 1
    current = stub_steer._obs_processor.current()
    assert current.task == "second"
    assert current.images[0].getpixel((0, 0)) == (255, 0, 0)
    assert current.images[3].getpixel((0, 0)) == (0, 0, 255)

    new_chunk = stub_steer.select_action(third, generate_new_chunk=True, use_guidance=False)
    assert new_chunk is not first_chunk
    assert stub_steer._rdt_model.encode_calls == 2
    current = stub_steer._obs_processor.current()
    assert current.task == "third"
    assert current.images[0].getpixel((0, 0)) == (0, 0, 255)
    assert current.images[3].getpixel((0, 0)) == (10, 20, 30)


def test_select_action_generate_new_chunk_forces_refresh_with_cached_actions(stub_steer, stub_adapter):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 8},
    )

    first_chunk = stub_steer.select_action(
        _raw_obs(agent_rgb=(255, 0, 0), task="first"),
        generate_new_chunk=True,
        use_guidance=False,
    )
    assert stub_steer._rdt_model.encode_calls == 1
    assert stub_steer._cached_action_steps_remaining == 7

    refreshed_chunk = stub_steer.select_action(
        _raw_obs(agent_rgb=(0, 0, 255), task="second"),
        generate_new_chunk=True,
        use_guidance=False,
    )

    assert refreshed_chunk is not first_chunk
    assert stub_steer._rdt_model.encode_calls == 2
    assert stub_steer._cached_action_steps_remaining == 7
    assert stub_steer._obs_processor.current().task == "second"


def test_guided_select_action_samples_only_on_chunk_boundaries(stub_steer, stub_adapter):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 2},
    )
    guidance = [lambda keypoints, traj: traj[..., 0].sum()]
    keypoints = np.zeros((3, 3), dtype=np.float32)

    first = stub_steer.select_action(
        _raw_obs(task="guided-first"),
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="vls",
        vls_config={"sample_batch_size": 4},
        guidance_fns=guidance,
        keypoints=keypoints,
    )
    assert stub_steer._rdt_model.encode_calls == 1
    assert stub_steer._cached_action_steps_remaining == 1

    reused = stub_steer.select_action(
        _raw_obs(task="guided-second"),
        generate_new_chunk=False,
        use_guidance=True,
        guidance_type="vls",
        vls_config={"sample_batch_size": 4},
        guidance_fns=guidance,
        keypoints=keypoints,
    )
    assert reused is first
    assert stub_steer._rdt_model.encode_calls == 1
    assert stub_steer._cached_action_steps_remaining == 0
    assert stub_steer._obs_processor.current().task == "guided-second"

    refreshed = stub_steer.select_action(
        _raw_obs(task="guided-third"),
        generate_new_chunk=False,
        use_guidance=True,
        guidance_type="vls",
        vls_config={"sample_batch_size": 4},
        guidance_fns=guidance,
        keypoints=keypoints,
    )
    assert refreshed is not first
    assert stub_steer._rdt_model.encode_calls == 2


def test_reset_clears_action_buffer_and_observation_history(stub_steer, stub_adapter, mock_batch):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=1,
        policy_config={"action_chunk_horizon": 8},
    )
    stub_steer.select_action(mock_batch, generate_new_chunk=True, use_guidance=False)
    assert stub_steer._cached_action_chunk is not None

    stub_steer.reset()

    assert stub_steer._cached_action_chunk is None
    assert stub_steer._cached_action_steps_remaining == 0
    with pytest.raises(RuntimeError, match="before observe"):
        stub_steer._obs_processor.current()


def test_guided_select_action_uses_latent_particle_batch(stub_steer, stub_adapter, mock_batch):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 8},
    )
    action = stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="vls",
        vls_config={"sample_batch_size": 4},
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
    )

    assert tuple(action.shape) == (1, 8, 7)
    assert stub_steer._rdt_model.dit.calls
    assert any(latent_shape[0] == 4 for latent_shape, _ in stub_steer._rdt_model.dit.calls)


def test_rdt_vls_config_sample_batch_size_overrides_post_init(
    stub_steer,
    stub_adapter,
    mock_batch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=1,
        policy_config={"action_chunk_horizon": 4},
    )

    action = stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="vls",
        vls_config={"sample_batch_size": 4},
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
    )

    assert tuple(action.shape) == (1, 4, 7)
    assert any(latent_shape[0] == 4 for latent_shape, _ in stub_steer._rdt_model.dit.calls)


def test_rdt_select_action_accepts_legacy_flat_vls_kwargs(
    stub_steer,
    stub_adapter,
    mock_batch,
    monkeypatch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=1,
        policy_config={"action_chunk_horizon": 4},
    )
    captured = {}

    def fake_vls(**kwargs):
        captured.update(kwargs["vls_config"])
        return torch.zeros(1, 64, 128)

    monkeypatch.setattr(stub_steer, "_vls_guided_denoise_loop", fake_vls)

    action = stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="vls",
        guide_scale=7.5,
        sample_batch_size=4,
        use_diversity=False,
        diversity_scale=0.25,
        MCMC_steps=2,
        use_fkd=True,
        fkd_config={"resample_frequency": 3},
        sigmoid_k=5.0,
        sigmoid_x0=0.4,
        start_ratio=0.6,
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
    )

    assert tuple(action.shape) == (1, 4, 7)
    assert captured["guide_scale"] == 7.5
    assert captured["sample_batch_size"] == 4
    assert captured["use_diversity"] is False
    assert captured["diversity_scale"] == 0.25
    assert captured["MCMC_steps"] == 2
    assert captured["use_fkd"] is True
    assert captured["fkd"] == {"resample_frequency": 3}
    assert captured["sigmoid_k"] == 5.0
    assert captured["sigmoid_x0"] == 0.4
    assert captured["start_ratio"] == 0.6


def test_rdt_vls_omitted_config_falls_back_to_post_init_sample_batch_size(
    stub_steer,
    stub_adapter,
    mock_batch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )

    action = stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="vls",
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
    )

    assert tuple(action.shape) == (1, 4, 7)
    assert any(latent_shape[0] == 3 for latent_shape, _ in stub_steer._rdt_model.dit.calls)


def test_rdt_guidance_type_vls_routes_to_vls_guided_denoise_loop(
    stub_steer,
    stub_adapter,
    mock_batch,
    monkeypatch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 4},
    )
    calls = {"vls": 0, "eds": 0}

    def fake_vls(**kwargs):
        calls["vls"] += 1
        return torch.zeros(1, 64, 128)

    def fake_eds(**kwargs):
        calls["eds"] += 1
        return torch.zeros(1, 64, 128)

    monkeypatch.setattr(stub_steer, "_vls_guided_denoise_loop", fake_vls)
    monkeypatch.setattr(stub_steer, "_eds_guided_denoise_loop", fake_eds)

    action = stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="vls",
        vls_config={"sample_batch_size": 4},
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
    )

    assert tuple(action.shape) == (1, 4, 7)
    assert calls == {"vls": 1, "eds": 0}


def test_rdt_guidance_type_eds_routes_to_eds_loop(
    stub_steer,
    stub_adapter,
    mock_batch,
    monkeypatch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 4},
    )
    calls = {"vls": 0, "eds": 0}

    def fake_vls(**kwargs):
        calls["vls"] += 1
        return torch.zeros(1, 64, 128)

    def fake_eds(**kwargs):
        calls["eds"] += 1
        return torch.zeros(1, 64, 128)

    monkeypatch.setattr(stub_steer, "_vls_guided_denoise_loop", fake_vls)
    monkeypatch.setattr(stub_steer, "_eds_guided_denoise_loop", fake_eds)

    action = stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="eds",
        eds_config={"population_size": 4, "cem_iters": 1},
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
    )

    assert tuple(action.shape) == (1, 4, 7)
    assert calls == {"vls": 0, "eds": 1}


def test_rdt_guidance_type_eds_verbose_log_uses_eds_fields(
    stub_steer,
    stub_adapter,
    mock_batch,
    monkeypatch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"action_chunk_horizon": 4},
    )
    messages = []
    monkeypatch.setattr(
        "core.rdt_policy_steer.log.info",
        lambda msg, *args, **kwargs: messages.append(str(msg)),
    )

    action = stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="eds",
        eds_config={"population_size": 4, "cem_iters": 1},
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
        verbose=True,
    )

    guide_messages = [msg for msg in messages if "[RDT_GUIDE]" in msg]
    assert tuple(action.shape) == (1, 4, 7)
    assert len(guide_messages) == 1
    assert "guidance_type=eds" in guide_messages[0]
    assert "eds_population_size=4" in guide_messages[0]
    assert "eds_loop=true" in guide_messages[0]
    assert "use_diversity" not in guide_messages[0]
    assert "use_fkd" not in guide_messages[0]


def test_eds_config_defaults_match_reference_signature(stub_steer):
    cfg = stub_steer._resolve_eds_config_with_reference_defaults({})

    assert cfg.population_size == 16
    assert cfg.use_cem is False
    assert cfg.cem_iters == 20
    assert cfg.num_elites == 32
    assert cfg.temperature == 0.1
    assert cfg.renoise_t_max == 5
    assert cfg.renoise_t_min == 1
    assert cfg.use_initial_cache is False
    assert cfg.save_initial_cache is False
    assert cfg.save_ed_cache is False


def test_eds_new_strategy_defaults_preserve_p2_legacy(stub_steer):
    cfg = stub_steer._resolve_eds_config_with_reference_defaults({})

    assert cfg.parent_weighting_mode == "legacy_temperature"
    assert cfg.parent_coverage_mode == "none"
    assert cfg.parent_anchor_count == 0
    assert cfg.elite_carryover_count == 0
    assert cfg.rollout_diversity_control_mode == "fixed"
    assert cfg.rollout_diversity_scale_min == 0.0
    assert cfg.rollout_diversity_scale_max == 20.0
    assert cfg.chunk_population_mode == "fresh"
    assert cfg.chunk_memory_fraction == 0.0
    assert cfg.search_schedule_mode == "legacy_linear"
    assert cfg.adaptive_min_cem_iters == 4
    assert cfg.adaptive_early_stop_patience == 2
    assert cfg.adaptive_reward_improvement_eps == 1e-3


def test_eds_yaml_strategy_defaults_match_resolver(stub_steer):
    config_path = Path(__file__).resolve().parents[1] / "configs" / "config.yaml"
    yaml_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    yaml_eds = yaml_config["main"]["eds_config"]
    resolved = stub_steer._resolve_eds_config_with_reference_defaults({})

    fields = (
        "parent_weighting_mode",
        "parent_coverage_mode",
        "parent_anchor_count",
        "elite_carryover_count",
        "rollout_diversity_control_mode",
        "rollout_diversity_scale_min",
        "rollout_diversity_scale_max",
        "chunk_population_mode",
        "chunk_memory_fraction",
        "search_schedule_mode",
        "adaptive_min_cem_iters",
        "adaptive_early_stop_patience",
        "adaptive_reward_improvement_eps",
    )

    assert {field: yaml_eds[field] for field in fields} == {
        field: getattr(resolved, field) for field in fields
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("parent_weighting_mode", "qd"),
        ("parent_coverage_mode", "fps_action"),
        ("rollout_diversity_control_mode", "auto"),
        ("chunk_population_mode", "archive"),
        ("search_schedule_mode", "oracle"),
    ],
)
def test_eds_rejects_unknown_strategy_modes(stub_steer, field, value):
    with pytest.raises(ValueError, match=field):
        stub_steer._resolve_eds_config_with_reference_defaults({field: value})


def test_eds_config_parses_new_strategy_fields(stub_steer):
    cfg = stub_steer._resolve_eds_config_with_reference_defaults(
        {
            "population_size": 16,
            "cem_iters": 8,
            "parent_weighting_mode": "adaptive_ess",
            "selection_ess_target_ratio": 0.7,
            "selection_beta_max": 50.0,
            "selection_bisection_steps": 12,
            "parent_coverage_mode": "eef_kcenter",
            "parent_anchor_count": 4,
            "parent_anchor_reward_quantile": 0.75,
            "elite_carryover_count": 2,
            "rollout_diversity_control_mode": "adaptive_band",
            "rollout_diversity_target_ratio": 0.8,
            "rollout_diversity_band_ratio": 0.1,
            "rollout_diversity_scale_min": 0.5,
            "rollout_diversity_scale_max": 10.0,
            "rollout_diversity_decay_floor": 0.4,
            "chunk_population_mode": "warm_start_mix",
            "chunk_memory_fraction": 0.5,
            "chunk_memory_renoise_steps": 3,
            "chunk_memory_reward_guard_quantile": 0.4,
            "search_schedule_mode": "adaptive",
            "adaptive_min_cem_iters": 3,
            "adaptive_early_stop_patience": 4,
            "adaptive_reward_improvement_eps": 0.002,
        }
    )

    assert cfg.parent_weighting_mode == "adaptive_ess"
    assert cfg.selection_ess_target_ratio == 0.7
    assert cfg.selection_beta_max == 50.0
    assert cfg.selection_bisection_steps == 12
    assert cfg.parent_coverage_mode == "eef_kcenter"
    assert cfg.parent_anchor_count == 4
    assert cfg.parent_anchor_reward_quantile == 0.75
    assert cfg.elite_carryover_count == 2
    assert cfg.rollout_diversity_control_mode == "adaptive_band"
    assert cfg.rollout_diversity_target_ratio == 0.8
    assert cfg.rollout_diversity_band_ratio == 0.1
    assert cfg.rollout_diversity_scale_min == 0.5
    assert cfg.rollout_diversity_scale_max == 10.0
    assert cfg.rollout_diversity_decay_floor == 0.4
    assert cfg.chunk_population_mode == "warm_start_mix"
    assert cfg.chunk_memory_fraction == 0.5
    assert cfg.chunk_memory_renoise_steps == 3
    assert cfg.chunk_memory_reward_guard_quantile == 0.4
    assert cfg.search_schedule_mode == "adaptive"
    assert cfg.adaptive_min_cem_iters == 3
    assert cfg.adaptive_early_stop_patience == 4
    assert cfg.adaptive_reward_improvement_eps == 0.002


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("selection_bisection_steps", 1.9),
        ("selection_bisection_steps", "bad"),
        ("parent_anchor_count", True),
        ("adaptive_min_cem_iters", 1.9),
        ("selection_beta_max", "bad"),
        ("selection_beta_max", True),
    ],
)
def test_eds_config_rejects_invalid_new_numeric_types(stub_steer, field, value):
    with pytest.raises(ValueError, match=field):
        stub_steer._resolve_eds_config_with_reference_defaults({field: value})


@pytest.mark.parametrize("value", [3, 3.0, "3"])
def test_eds_config_accepts_unambiguous_integer_inputs(stub_steer, value):
    cfg = stub_steer._resolve_eds_config_with_reference_defaults(
        {"selection_bisection_steps": value}
    )

    assert cfg.selection_bisection_steps == 3
    assert type(cfg.selection_bisection_steps) is int


@pytest.mark.parametrize(
    ("config", "field"),
    [
        ({"selection_ess_target_ratio": 0.0}, "selection_ess_target_ratio"),
        ({"selection_ess_target_ratio": 1.01}, "selection_ess_target_ratio"),
        ({"selection_beta_max": 0.0}, "selection_beta_max"),
        ({"selection_beta_max": float("nan")}, "selection_beta_max"),
        ({"selection_bisection_steps": 0}, "selection_bisection_steps"),
        ({"parent_anchor_count": -1}, "parent_anchor_count"),
        ({"parent_anchor_reward_quantile": -0.01}, "parent_anchor_reward_quantile"),
        ({"parent_anchor_reward_quantile": 1.01}, "parent_anchor_reward_quantile"),
        ({"elite_carryover_count": -1}, "elite_carryover_count"),
        (
            {
                "population_size": 4,
                "elite_carryover_count": 3,
                "parent_anchor_count": 2,
            },
            "elite_carryover_count.*parent_anchor_count",
        ),
        ({"rollout_diversity_target_ratio": -0.01}, "rollout_diversity_target_ratio"),
        ({"rollout_diversity_band_ratio": float("inf")}, "rollout_diversity_band_ratio"),
        ({"rollout_diversity_scale_min": -0.01}, "rollout_diversity_scale_min"),
        ({"rollout_diversity_scale_max": float("nan")}, "rollout_diversity_scale_max"),
        (
            {"rollout_diversity_scale_min": 2.0, "rollout_diversity_scale_max": 1.0},
            "rollout_diversity_scale_min.*rollout_diversity_scale_max",
        ),
        ({"rollout_diversity_decay_floor": -0.01}, "rollout_diversity_decay_floor"),
        ({"rollout_diversity_decay_floor": 1.01}, "rollout_diversity_decay_floor"),
        ({"chunk_memory_fraction": -0.01}, "chunk_memory_fraction"),
        ({"chunk_memory_fraction": 1.0}, "chunk_memory_fraction"),
        ({"chunk_memory_renoise_steps": 0}, "chunk_memory_renoise_steps"),
        (
            {"chunk_memory_reward_guard_quantile": -0.01},
            "chunk_memory_reward_guard_quantile",
        ),
        (
            {"chunk_memory_reward_guard_quantile": 1.01},
            "chunk_memory_reward_guard_quantile",
        ),
        ({"adaptive_min_cem_iters": 0}, "adaptive_min_cem_iters"),
        (
            {"cem_iters": 3, "adaptive_min_cem_iters": 4},
            "adaptive_min_cem_iters",
        ),
        ({"adaptive_early_stop_patience": 0}, "adaptive_early_stop_patience"),
        ({"adaptive_reward_improvement_eps": -0.001}, "adaptive_reward_improvement_eps"),
        (
            {"adaptive_reward_improvement_eps": float("nan")},
            "adaptive_reward_improvement_eps",
        ),
    ],
)
def test_eds_config_rejects_invalid_new_strategy_boundaries(
    stub_steer, config, field
):
    with pytest.raises(ValueError, match=field):
        stub_steer._resolve_eds_config_with_reference_defaults(config)


def test_eds_config_keeps_short_legacy_cem_schedules_valid(stub_steer):
    cfg = stub_steer._resolve_eds_config_with_reference_defaults({"cem_iters": 1})

    assert cfg.search_schedule_mode == "legacy_linear"
    assert cfg.adaptive_min_cem_iters == 1


def test_eds_legacy_trunc_step_schedule_matches_reference_linspace(stub_steer):
    cfg = stub_steer._resolve_eds_config_with_reference_defaults(
        {
            "cem_iters": 8,
            "renoise_t_max": 5,
            "renoise_t_min": 1,
            "search_schedule_mode": "legacy_linear",
        }
    )
    expected = np.linspace(5, 1, 8).astype(int).tolist()

    actual = [
        stub_steer._eds_resolve_renoise_steps(
            cfg=cfg,
            iter_idx=iter_idx,
            reward_improvement=None,
            diversity_band_state="in_band",
            best_lineage_stable=False,
        )[0]
        for iter_idx in range(cfg.cem_iters)
    ]

    assert actual == expected


@pytest.mark.parametrize(
    (
        "iter_idx",
        "reward_improvement",
        "diversity_band_state",
        "best_lineage_stable",
        "expected_steps",
        "expected_reason",
    ),
    [
        (0, None, "in_band", False, 5, "adaptive_initial_max"),
        (1, 0.0, "below_band", False, 3, "adaptive_diversity_recovery"),
        (2, 0.1, "in_band", True, 1, "adaptive_stable_improving"),
        (3, 0.0, "in_band", False, 2, "adaptive_uncertain"),
    ],
)
def test_eds_adaptive_schedule_resolves_online_state(
    stub_steer,
    iter_idx,
    reward_improvement,
    diversity_band_state,
    best_lineage_stable,
    expected_steps,
    expected_reason,
):
    cfg = stub_steer._resolve_eds_config_with_reference_defaults(
        {
            "cem_iters": 8,
            "renoise_t_max": 5,
            "renoise_t_min": 1,
            "search_schedule_mode": "adaptive",
        }
    )

    steps, reason = stub_steer._eds_resolve_renoise_steps(
        cfg=cfg,
        iter_idx=iter_idx,
        reward_improvement=reward_improvement,
        diversity_band_state=diversity_band_state,
        best_lineage_stable=best_lineage_stable,
    )

    assert steps == expected_steps
    assert reason == expected_reason


@pytest.mark.parametrize(
    ("config", "state", "expected"),
    [
        (
            {"renoise_t_min": 1, "renoise_t_max": 2},
            {"reward_improvement": 0.0, "diversity_band_state": "below_band"},
            2,
        ),
        (
            {"renoise_t_min": 3, "renoise_t_max": 5},
            {
                "reward_improvement": 0.1,
                "diversity_band_state": "in_band",
                "best_lineage_stable": True,
            },
            3,
        ),
    ],
)
def test_eds_adaptive_schedule_clips_to_configured_renoise_bounds(
    stub_steer,
    config,
    state,
    expected,
):
    cfg = stub_steer._resolve_eds_config_with_reference_defaults(
        {
            "cem_iters": 4,
            "search_schedule_mode": "adaptive",
            **config,
        }
    )

    steps, _ = stub_steer._eds_resolve_renoise_steps(
        cfg=cfg,
        iter_idx=1,
        best_lineage_stable=state.get("best_lineage_stable", False),
        **{key: value for key, value in state.items() if key != "best_lineage_stable"},
    )

    assert steps == expected
    assert cfg.renoise_t_min <= steps <= cfg.renoise_t_max


@pytest.mark.parametrize(
    ("iter_idx", "reward_improvement", "diversity_band_state", "match"),
    [
        (-1, None, "in_band", "iter_idx"),
        (4, None, "in_band", "iter_idx"),
        (1, float("nan"), "in_band", "reward_improvement"),
        (1, float("inf"), "in_band", "reward_improvement"),
        (1, None, "unknown", "diversity_band_state"),
        (1, None, "inside_band", "diversity_band_state"),
    ],
)
def test_eds_schedule_helper_rejects_invalid_online_state(
    stub_steer,
    iter_idx,
    reward_improvement,
    diversity_band_state,
    match,
):
    cfg = stub_steer._resolve_eds_config_with_reference_defaults(
        {"cem_iters": 4, "search_schedule_mode": "adaptive"}
    )

    with pytest.raises(ValueError, match=match):
        stub_steer._eds_resolve_renoise_steps(
            cfg=cfg,
            iter_idx=iter_idx,
            reward_improvement=reward_improvement,
            diversity_band_state=diversity_band_state,
            best_lineage_stable=False,
        )


def test_eds_typed_internal_records_preserve_tensor_plans():
    from core.rdt_policy_steer import (
        EDSChunkMemory,
        EDSParentPlan,
        EDSRolloutDiversityDecision,
    )

    elite_indices = torch.tensor([0, 1])
    parent_indices = torch.tensor([2, 3])
    plan = EDSParentPlan(
        elite_indices=elite_indices,
        offspring_parent_indices=parent_indices,
        offspring_sources=("anchor_offspring", "weighted_offspring"),
        info={"anchor_count": 1},
    )
    decision = EDSRolloutDiversityDecision(
        scale=2.0,
        enabled=True,
        reason="below_band",
        reference=0.5,
        low=0.4,
        high=0.6,
        current=0.2,
        reward_confidence=0.25,
    )
    memory = EDSChunkMemory(
        population=torch.zeros(2, 64, 128),
        costs=torch.tensor([0.1, 0.2]),
        stage=1,
        global_step=8,
    )

    assert plan.elite_indices is elite_indices
    assert plan.offspring_parent_indices is parent_indices
    assert plan.offspring_sources == ("anchor_offspring", "weighted_offspring")
    assert decision.enabled is True
    assert decision.reason == "below_band"
    with pytest.raises(FrozenInstanceError):
        plan.info = {}
    with pytest.raises(FrozenInstanceError):
        decision.scale = 0.0
    memory.stage = 2
    assert memory.stage == 2


def test_eds_chunk_memory_shift_fills_tail_from_paired_fresh_candidate(stub_steer):
    memory = torch.zeros(64, 128)
    fresh = torch.zeros(64, 128)
    memory[:, 39] = torch.arange(64, dtype=torch.float32)
    fresh[:, 39] = 1000.0 + torch.arange(64, dtype=torch.float32)

    shifted = stub_steer._eds_shift_memory_candidate(
        memory_candidate=memory,
        fresh_candidate=fresh,
        executed_steps=4,
    )

    torch.testing.assert_close(shifted[:60, 39], memory[4:, 39])
    torch.testing.assert_close(shifted[60:, 39], fresh[-4:, 39])
    assert torch.count_nonzero(shifted[60:, 39]) == 4


@pytest.mark.parametrize(("fraction", "expected"), [(0.25, 4), (0.5, 8)])
def test_eds_chunk_memory_fraction_resolves_exact_population_count(
    stub_steer, fraction, expected
):
    assert stub_steer._eds_resolve_chunk_memory_count(16, fraction) == expected


def test_eds_chunk_memory_episode_stage_and_abnormal_reset(stub_steer, monkeypatch):
    from core.rdt_policy_steer import EDSChunkMemory

    warnings = []
    monkeypatch.setattr("core.rdt_policy_steer.log.warning", warnings.append)
    memory = EDSChunkMemory(
        population=torch.zeros(2, 64, 128),
        costs=torch.zeros(2),
        stage=1,
        global_step=0,
    )

    assert stub_steer._eds_chunk_memory is None
    stub_steer._eds_chunk_memory = memory
    stub_steer.reset_stage()
    assert stub_steer._eds_chunk_memory is None
    assert stub_steer._eds_chunk_memory_reset_reason == "stage_change"
    stub_steer._eds_chunk_memory = memory
    stub_steer.reset()
    assert stub_steer._eds_chunk_memory is None
    assert stub_steer._eds_chunk_memory_reset_reason == "episode_reset"
    stub_steer._eds_chunk_memory = memory
    stub_steer.reset_eds_chunk_memory("invalid_nonfinite", warn=True)
    assert stub_steer._eds_chunk_memory is None
    assert stub_steer._eds_chunk_memory_reset_reason == "invalid_nonfinite"
    assert any("invalid_nonfinite" in warning for warning in warnings)


def test_eds_chunk_memory_score_free_denoise_matches_baseline_rollout(
    stub_steer, monkeypatch
):
    cond = _rollout_cond(stub_steer)
    noisy = torch.randn(3, 64, 128)
    score_calls = []

    def fake_score(samples, **kwargs):
        score_calls.append(samples.detach().clone())
        costs = torch.arange(samples.shape[0], dtype=samples.dtype)
        return costs, {"rewards": -costs}

    monkeypatch.setattr(stub_steer, "_eds_score_population_as_cost", fake_score)
    baseline, baseline_costs, _ = stub_steer._eds_rollout_baseline_reference(
        cond=cond,
        action_mask=cond["action_mask"],
        noisy_action=noisy.clone(),
        keypoints=None,
        guidance_fns=None,
        n_trunc_steps=2,
    )
    denoised = stub_steer._eds_denoise_noisy_population(
        cond=cond,
        action_mask=cond["action_mask"],
        noisy_action=noisy.clone(),
        n_trunc_steps=2,
    )

    torch.testing.assert_close(denoised, baseline)
    torch.testing.assert_close(baseline_costs, torch.arange(3, dtype=noisy.dtype))
    assert len(score_calls) == 1


def _eds_chunk_memory_config(**overrides):
    from core.rdt_policy_steer import _EDSConfig

    values = {
        "population_size": 16,
        "cem_iters": 1,
        "num_elites": 16,
        "chunk_population_mode": "warm_start_mix",
        "chunk_memory_fraction": 0.25,
        "chunk_memory_renoise_steps": 2,
        "chunk_memory_reward_guard_quantile": 0.25,
    }
    values.update(overrides)
    return _EDSConfig(**values)


def test_eds_chunk_memory_composes_guarded_masked_candidates_and_scores_once_each(
    stub_steer, stub_adapter, monkeypatch
):
    from core.rdt_policy_steer import EDSChunkMemory

    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=16,
        policy_config={"action_chunk_horizon": 4},
    )
    cond = _rollout_cond(stub_steer)
    fresh = torch.zeros(16, 64, 128)
    fresh[:, :, 39] = 100.0 + torch.arange(16, dtype=fresh.dtype)[:, None]
    memory = torch.zeros_like(fresh)
    memory[:, :, 39] = torch.arange(16, dtype=memory.dtype)[:, None]
    stub_steer._eds_chunk_memory = EDSChunkMemory(
        population=memory,
        costs=torch.arange(16, dtype=torch.float32),
        stage=1,
        global_step=0,
    )
    score_batch_sizes = []

    def fake_score(samples, **kwargs):
        score_batch_sizes.append(int(samples.shape[0]))
        costs = samples[:, 0, 39].detach().clone()
        return costs, {"rewards": -costs}

    def fake_denoise(**kwargs):
        adapted = kwargs["noisy_action"].clone()
        adapted[:, :, 0] = 99.0
        return adapted

    monkeypatch.setattr(
        stub_steer,
        "_eds_select_eef_kcenter",
        lambda population, rewards, count, reward_quantile: (
            torch.arange(count, device=population.device),
            {"anchor_selected_count": count},
        ),
    )
    monkeypatch.setattr(stub_steer, "_eds_renoise_reference", lambda samples, steps: samples)
    monkeypatch.setattr(stub_steer, "_eds_denoise_noisy_population", fake_denoise)
    monkeypatch.setattr(stub_steer, "_eds_score_population_as_cost", fake_score)

    population, costs, info, telemetry = (
        stub_steer._eds_compose_initial_population_from_memory(
            fresh_population=fresh,
            cond=cond,
            cfg=_eds_chunk_memory_config(),
            keypoints=None,
            guidance_fns=None,
            global_step=4,
            current_stage=1,
        )
    )

    assert population.shape == (16, 64, 128)
    assert costs.shape == (16,)
    assert info["rewards"].shape == (16,)
    assert score_batch_sizes == [16, 4]
    assert telemetry["chunk_memory_available"] is True
    assert telemetry["chunk_memory_used"] is True
    assert telemetry["chunk_memory_candidate_count"] == 4
    assert telemetry["chunk_memory_acceptance_ratio"] == 1.0
    assert telemetry["chunk_memory_source_counts"] == {"memory": 4, "fresh": 12}
    assert telemetry["particle_sources"] == ("memory",) * 4 + ("fresh",) * 12
    torch.testing.assert_close(population[:4, :60, 39], memory[:4, 4:, 39])
    torch.testing.assert_close(population[:4, 60:, 39], fresh[:4, -4:, 39])
    assert torch.count_nonzero(population[:, :, 0]) == 0


def test_eds_chunk_memory_loop_stores_cpu_state_and_reuses_source_ancestry(
    stub_steer, stub_adapter, monkeypatch, tmp_path
):
    from core.eds_mechanism_trace import save_mechanism_trace

    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 4},
    )
    cond = _rollout_cond(stub_steer)
    initial_calls = []

    def fake_initial_population(*, x_t, cond, cfg):
        base = 10.0 if not initial_calls else 100.0
        initial_calls.append(base)
        population = torch.zeros_like(x_t)
        population[:, :, 39] = base + torch.arange(4, dtype=x_t.dtype)[:, None]
        return population

    def fake_score(samples, **kwargs):
        costs = samples[:, 0, 39].detach().clone()
        return costs, {"rewards": -costs}

    monkeypatch.setattr(stub_steer, "_eds_initial_population", fake_initial_population)
    monkeypatch.setattr(stub_steer, "_eds_score_population_as_cost", fake_score)
    monkeypatch.setattr(stub_steer, "_eds_renoise_reference", lambda samples, steps: samples)
    monkeypatch.setattr(
        stub_steer,
        "_eds_denoise_noisy_population",
        lambda **kwargs: kwargs["noisy_action"],
    )
    monkeypatch.setattr(
        stub_steer,
        "_eds_rollout_reference",
        lambda **kwargs: (
            kwargs["noisy_action"],
            fake_score(kwargs["noisy_action"])[0],
            {"rewards": -fake_score(kwargs["noisy_action"])[0]},
        ),
    )
    monkeypatch.setattr(
        "core.rdt_policy_steer.torch.randint",
        lambda low, high, size, device=None: torch.arange(size[0], device=device),
    )
    cfg = _eds_chunk_memory_config(
        population_size=4,
        chunk_memory_fraction=0.5,
        use_cem=True,
        elite_carryover_count=0,
        num_elites=4,
        mechanism_pretest={
            "enabled": True,
            "first_chunk_only": False,
            "save_full_process": True,
        },
    )

    stub_steer._eds_guided_denoise_loop(
        x_t=torch.zeros(4, 64, 128),
        cond=cond,
        keypoints=None,
        guidance_fns=None,
        eds_config=cfg,
        verbose=False,
        global_step=0,
        current_stage=1,
    )
    first_memory = stub_steer._eds_chunk_memory
    assert first_memory is not None
    assert first_memory.population.device.type == "cpu"
    assert first_memory.costs.device.type == "cpu"
    assert first_memory.population.requires_grad is False
    assert first_memory.costs.requires_grad is False
    assert first_memory.global_step == 0
    assert first_memory.stage == 1

    stub_steer._eds_guided_denoise_loop(
        x_t=torch.zeros(4, 64, 128),
        cond=cond,
        keypoints=None,
        guidance_fns=None,
        eds_config=cfg,
        verbose=False,
        global_step=4,
        current_stage=1,
    )

    metrics = stub_steer.get_last_eds_metrics()
    assert metrics["chunk_population_mode"] == "warm_start_mix"
    assert metrics["chunk_memory_available"] is True
    assert metrics["chunk_memory_used"] is True
    assert metrics["chunk_memory_candidate_count"] == 2
    assert metrics["chunk_memory_source_counts"] == {"memory": 2, "fresh": 2}
    assert metrics["selected_chunk_population_source"] == "memory"
    assert metrics["chunk_to_chunk_selected_trajectory_distance"] is not None
    assert stub_steer._eds_chunk_memory.global_step == 4

    trace = stub_steer.get_last_eds_mechanism_trace()
    assert trace is not None
    save_mechanism_trace(tmp_path, trace, save_tensors=True)
    metadata = json.loads((tmp_path / "first_chunk_metadata.json").read_text())
    tensor_payload = torch.load(tmp_path / "tensors" / "mechanism_trace.pt")
    expected_fields = {
        "chunk_memory_available",
        "chunk_memory_used",
        "chunk_memory_candidate_count",
        "chunk_memory_fraction_observed",
        "chunk_memory_reset_reason",
        "chunk_memory_acceptance_ratio",
        "chunk_memory_source_counts",
        "chunk_memory_initial_best_reward",
        "chunk_fresh_initial_best_reward",
        "chunk_memory_initial_mean_reward",
        "chunk_fresh_initial_mean_reward",
        "chunk_memory_initial_diversity",
        "chunk_fresh_initial_diversity",
        "particle_sources",
        "selected_chunk_population_source",
        "chunk_to_chunk_selected_trajectory_distance",
    }
    assert expected_fields <= metadata["chunk_memory_info"].keys()
    assert metadata["chunk_memory_info"] == tensor_payload["chunk_memory_info"]
    assert metadata["chunk_memory_info"]["particle_sources"] == [
        "memory",
        "memory",
        "fresh",
        "fresh",
    ]
    assert metadata["chunk_memory_info"]["selected_chunk_population_source"] == "memory"
    tensor_stages = {stage["stage"]: stage for stage in tensor_payload["stages"]}
    assert tensor_stages["initial"]["particle_sources"] == [
        "memory",
        "memory",
        "fresh",
        "fresh",
    ]

    def assert_json_safe(value):
        assert not torch.is_tensor(value)
        if isinstance(value, dict):
            for item in value.values():
                assert_json_safe(item)
        elif isinstance(value, list):
            for item in value:
                assert_json_safe(item)
        elif isinstance(value, float):
            assert math.isfinite(value)

    assert_json_safe(metadata["chunk_memory_info"])
    assert_json_safe(tensor_payload["chunk_memory_info"])


@pytest.mark.parametrize(
    "invalid_case",
    [
        "shape",
        "nonfinite",
        "stage",
        "nonpositive_step_delta",
        "oversized_step_delta",
        "action_mask",
    ],
)
def test_eds_chunk_memory_invalid_state_warns_and_falls_back_all_fresh(
    stub_steer, monkeypatch, invalid_case
):
    from core.rdt_policy_steer import EDSChunkMemory

    cond = _rollout_cond(stub_steer)
    fresh = torch.zeros(16, 64, 128)
    fresh[:, :, 39] = torch.arange(16, dtype=fresh.dtype)[:, None]
    memory_population = fresh.clone()
    costs = torch.arange(16, dtype=torch.float32)
    stage = 1
    memory_global_step = 0
    current_global_step = 4
    if invalid_case == "shape":
        memory_population = memory_population[:-1]
    elif invalid_case == "nonfinite":
        memory_population[0, 0, 39] = float("nan")
    elif invalid_case == "stage":
        stage = 2
    elif invalid_case == "nonpositive_step_delta":
        memory_global_step = current_global_step
    elif invalid_case == "oversized_step_delta":
        current_global_step = 64
    elif invalid_case == "action_mask":
        memory_population[:, :, 0] = 1.0
    stub_steer._eds_chunk_memory = EDSChunkMemory(
        population=memory_population,
        costs=costs,
        stage=stage,
        global_step=memory_global_step,
    )
    warnings = []
    monkeypatch.setattr("core.rdt_policy_steer.log.warning", warnings.append)

    population, population_costs, population_info, telemetry = (
        stub_steer._eds_compose_initial_population_from_memory(
            fresh_population=fresh,
            cond=cond,
            cfg=_eds_chunk_memory_config(),
            keypoints=None,
            guidance_fns=None,
            global_step=current_global_step,
            current_stage=1,
        )
    )

    torch.testing.assert_close(population, fresh)
    assert population_costs is None
    assert population_info is None
    assert telemetry["chunk_memory_available"] is True
    assert telemetry["chunk_memory_used"] is False
    assert telemetry["chunk_memory_reset_reason"].startswith("invalid_memory:")
    assert stub_steer._eds_chunk_memory is None
    assert warnings and telemetry["chunk_memory_reset_reason"] in warnings[0]


def test_eds_chunk_memory_reward_guard_rejects_weak_candidates(stub_steer, monkeypatch):
    from core.rdt_policy_steer import EDSChunkMemory

    cond = _rollout_cond(stub_steer)
    fresh = torch.zeros(16, 64, 128)
    fresh[:, :, 39] = torch.arange(16, dtype=fresh.dtype)[:, None]
    memory = torch.zeros_like(fresh)
    memory[:, :, 39] = 100.0 + torch.arange(16, dtype=memory.dtype)[:, None]
    stub_steer._eds_chunk_memory = EDSChunkMemory(
        population=memory,
        costs=torch.arange(16, dtype=torch.float32),
        stage=1,
        global_step=0,
    )
    monkeypatch.setattr(
        stub_steer,
        "_eds_select_eef_kcenter",
        lambda population, rewards, count, reward_quantile: (
            torch.arange(count),
            {},
        ),
    )
    monkeypatch.setattr(stub_steer, "_eds_renoise_reference", lambda samples, steps: samples)
    monkeypatch.setattr(
        stub_steer,
        "_eds_denoise_noisy_population",
        lambda **kwargs: kwargs["noisy_action"],
    )
    monkeypatch.setattr(
        stub_steer,
        "_eds_score_population_as_cost",
        lambda samples, **kwargs: (
            samples[:, 0, 39].clone(),
            {"rewards": -samples[:, 0, 39].clone()},
        ),
    )

    population, costs, _, telemetry = (
        stub_steer._eds_compose_initial_population_from_memory(
            fresh_population=fresh,
            cond=cond,
            cfg=_eds_chunk_memory_config(),
            keypoints=None,
            guidance_fns=None,
            global_step=4,
            current_stage=1,
        )
    )

    torch.testing.assert_close(population, fresh)
    torch.testing.assert_close(costs, fresh[:, 0, 39])
    assert telemetry["chunk_memory_available"] is True
    assert telemetry["chunk_memory_used"] is False
    assert telemetry["chunk_memory_acceptance_ratio"] == 0.0
    assert telemetry["chunk_memory_source_counts"] == {"memory": 0, "fresh": 16}


@pytest.mark.parametrize(
    ("failure_site", "message"),
    [
        ("denoise", "CUDA out of memory"),
        ("scoring", "model scoring failure"),
    ],
)
def test_eds_chunk_memory_runtime_failures_propagate_without_fallback(
    stub_steer, monkeypatch, failure_site, message
):
    from core.rdt_policy_steer import EDSChunkMemory

    cond = _rollout_cond(stub_steer)
    fresh = torch.zeros(16, 64, 128)
    memory = EDSChunkMemory(
        population=torch.zeros_like(fresh),
        costs=torch.arange(16, dtype=torch.float32),
        stage=1,
        global_step=0,
    )
    stub_steer._eds_chunk_memory = memory
    monkeypatch.setattr(
        stub_steer,
        "_eds_select_eef_kcenter",
        lambda population, rewards, count, reward_quantile: (torch.arange(count), {}),
    )
    monkeypatch.setattr(stub_steer, "_eds_renoise_reference", lambda samples, steps: samples)
    failure = RuntimeError(message)
    if failure_site == "denoise":
        monkeypatch.setattr(
            stub_steer,
            "_eds_denoise_noisy_population",
            lambda **kwargs: (_ for _ in ()).throw(failure),
        )
    else:
        monkeypatch.setattr(
            stub_steer,
            "_eds_denoise_noisy_population",
            lambda **kwargs: kwargs["noisy_action"],
        )
        monkeypatch.setattr(
            stub_steer,
            "_eds_score_population_as_cost",
            lambda *args, **kwargs: (_ for _ in ()).throw(failure),
        )
    warnings = []
    monkeypatch.setattr("core.rdt_policy_steer.log.warning", warnings.append)

    with pytest.raises(RuntimeError, match=message) as exc_info:
        stub_steer._eds_compose_initial_population_from_memory(
            fresh_population=fresh,
            cond=cond,
            cfg=_eds_chunk_memory_config(),
            keypoints=None,
            guidance_fns=None,
            global_step=4,
            current_stage=1,
        )

    assert exc_info.value is failure
    assert stub_steer._eds_chunk_memory is memory
    assert warnings == []


def test_eds_chunk_memory_fresh_mode_never_composes_or_replaces_existing_state(
    stub_steer, monkeypatch
):
    from core.rdt_policy_steer import EDSChunkMemory, _EDSConfig

    cond = _rollout_cond(stub_steer)
    existing_memory = EDSChunkMemory(
        population=torch.zeros(4, 64, 128),
        costs=torch.zeros(4),
        stage=1,
        global_step=0,
    )
    stub_steer._eds_chunk_memory = existing_memory
    initial = torch.zeros(4, 64, 128)
    initial[:, :, 39] = torch.arange(4, dtype=initial.dtype)[:, None]
    monkeypatch.setattr(
        stub_steer,
        "_eds_compose_initial_population_from_memory",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("fresh mode must not read or compose chunk memory")
        ),
    )
    monkeypatch.setattr(
        stub_steer,
        "_eds_initial_population",
        lambda **kwargs: initial.clone(),
    )
    monkeypatch.setattr(
        stub_steer,
        "_eds_score_population_as_cost",
        lambda samples, **kwargs: (
            samples[:, 0, 39].clone(),
            {"rewards": -samples[:, 0, 39].clone()},
        ),
    )
    monkeypatch.setattr(stub_steer, "_eds_renoise_reference", lambda samples, steps: samples)
    monkeypatch.setattr(
        stub_steer,
        "_eds_rollout_reference",
        lambda **kwargs: (
            kwargs["noisy_action"],
            kwargs["noisy_action"][:, 0, 39].clone(),
            {"rewards": -kwargs["noisy_action"][:, 0, 39].clone()},
        ),
    )
    monkeypatch.setattr(
        "core.rdt_policy_steer.torch.randint",
        lambda low, high, size, device=None: torch.arange(size[0], device=device),
    )

    stub_steer._eds_guided_denoise_loop(
        x_t=torch.zeros_like(initial),
        cond=cond,
        keypoints=None,
        guidance_fns=None,
        eds_config=_EDSConfig(
            population_size=4,
            cem_iters=1,
            use_cem=True,
            num_elites=4,
            chunk_population_mode="fresh",
        ),
        verbose=False,
        global_step=4,
        current_stage=1,
    )

    assert stub_steer._eds_chunk_memory is existing_memory
    metrics = stub_steer.get_last_eds_metrics()
    assert metrics["chunk_population_mode"] == "fresh"
    assert metrics["chunk_memory_available"] is False
    assert metrics["chunk_memory_used"] is False
    assert metrics["selected_chunk_population_source"] == "fresh"


def test_eds_chunk_memory_initial_cache_contains_fresh_population_only(
    stub_steer, monkeypatch, tmp_path
):
    from core.rdt_policy_steer import EDSChunkMemory, _EDSConfig

    cond = _rollout_cond(stub_steer)
    fresh = torch.zeros(4, 64, 128)
    fresh[:, :, 39] = 100.0 + torch.arange(4, dtype=fresh.dtype)[:, None]
    cfg = _EDSConfig(
        population_size=4,
        cem_iters=1,
        num_elites=4,
        save_initial_cache=True,
        initial_population_cache=str(tmp_path / "initial.pt"),
        chunk_population_mode="warm_start_mix",
        chunk_memory_fraction=0.5,
    )
    monkeypatch.setattr(
        stub_steer,
        "_eds_initial_denoise_iid",
        lambda **kwargs: (fresh.clone(), {}),
    )
    generated = stub_steer._eds_initial_population(
        x_t=torch.zeros_like(fresh),
        cond=cond,
        cfg=cfg,
    )
    memory = torch.zeros_like(fresh)
    memory[:, :, 39] = torch.arange(4, dtype=memory.dtype)[:, None]
    stub_steer._eds_chunk_memory = EDSChunkMemory(
        population=memory,
        costs=torch.arange(4, dtype=torch.float32),
        stage=1,
        global_step=0,
    )
    monkeypatch.setattr(
        stub_steer,
        "_eds_select_eef_kcenter",
        lambda population, rewards, count, reward_quantile: (torch.arange(count), {}),
    )
    monkeypatch.setattr(stub_steer, "_eds_renoise_reference", lambda samples, steps: samples)
    monkeypatch.setattr(
        stub_steer,
        "_eds_denoise_noisy_population",
        lambda **kwargs: kwargs["noisy_action"],
    )
    monkeypatch.setattr(
        stub_steer,
        "_eds_score_population_as_cost",
        lambda samples, **kwargs: (
            samples[:, 0, 39].clone(),
            {"rewards": -samples[:, 0, 39].clone()},
        ),
    )

    composed, _, _, _ = stub_steer._eds_compose_initial_population_from_memory(
        fresh_population=generated,
        cond=cond,
        cfg=cfg,
        keypoints=None,
        guidance_fns=None,
        global_step=4,
        current_stage=1,
    )
    cached = torch.load(tmp_path / "initial.pt")["initial_population"]

    torch.testing.assert_close(cached, fresh)
    assert not torch.equal(composed, cached)


def _adaptive_rbf_test_config(**overrides):
    from core.rdt_policy_steer import _EDSConfig

    values = {
        "population_size": 4,
        "cem_iters": 5,
        "truncated_rollout_mode": "rbf_diverse",
        "rollout_diversity_scale": 3.25,
        "rollout_diversity_iters": "all",
        "rollout_diversity_control_mode": "adaptive_band",
        "rollout_diversity_target_ratio": 1.0,
        "rollout_diversity_band_ratio": 0.2,
        "rollout_diversity_scale_min": 0.0,
        "rollout_diversity_scale_max": 10.0,
        "rollout_diversity_decay_floor": 0.25,
    }
    values.update(overrides)
    return _EDSConfig(**values)


def test_adaptive_rbf_controller_resolves_band_states_and_positive_deficit(
    stub_steer,
):
    cfg = _adaptive_rbf_test_config()
    rewards = torch.zeros(4)

    below, below_info = stub_steer._eds_adaptive_rollout_diversity_decision(
        reference=1.0,
        current=0.4,
        rewards=rewards,
        iter_idx=0,
        cfg=cfg,
    )
    inside, inside_info = stub_steer._eds_adaptive_rollout_diversity_decision(
        reference=1.0,
        current=0.9,
        rewards=rewards,
        iter_idx=0,
        cfg=cfg,
    )
    above, above_info = stub_steer._eds_adaptive_rollout_diversity_decision(
        reference=1.0,
        current=1.3,
        rewards=rewards,
        iter_idx=0,
        cfg=cfg,
    )

    assert below.scale > 0.0
    assert below.enabled is True
    assert below.reason == "below_band"
    assert below.low == pytest.approx(0.8)
    assert below.high == pytest.approx(1.2)
    assert below.reward_confidence == 0.0
    assert below_info["adaptive_rbf_scale_requested"] == below.scale
    assert inside.scale == 0.0
    assert inside.enabled is False
    assert inside.reason == "in_band"
    assert inside_info["adaptive_rbf_band_hit"] is True
    assert above.scale == 0.0
    assert above.enabled is False
    assert above.reason == "above_band"
    assert above_info["adaptive_rbf_band_hit"] is False


@pytest.mark.parametrize(
    ("config_overrides", "current", "expected_reason", "expected_high"),
    [
        ({"rollout_diversity_target_ratio": 0.0}, 0.0, "in_band", 0.0),
        ({"rollout_diversity_target_ratio": 0.0}, 0.1, "above_band", 0.0),
        ({"rollout_diversity_band_ratio": 1.0}, 0.0, "in_band", 2.0),
        ({"rollout_diversity_band_ratio": 1.5}, 0.0, "in_band", 2.5),
    ],
)
def test_adaptive_rbf_controller_accepts_zero_lower_band_without_fallback(
    stub_steer,
    monkeypatch,
    config_overrides,
    current,
    expected_reason,
    expected_high,
):
    from core import rdt_policy_steer

    warnings = []
    monkeypatch.setattr(
        rdt_policy_steer.log,
        "warning",
        lambda message: warnings.append(str(message)),
    )

    decision, info = stub_steer._eds_adaptive_rollout_diversity_decision(
        reference=1.0,
        current=current,
        rewards=torch.zeros(4),
        iter_idx=0,
        cfg=_adaptive_rbf_test_config(**config_overrides),
    )

    assert decision.low == 0.0
    assert decision.high == pytest.approx(expected_high)
    assert decision.scale == 0.0
    assert decision.enabled is False
    assert decision.reason == expected_reason
    assert info["adaptive_rbf_fallback_used"] is False
    assert warnings == []


def test_adaptive_rbf_controller_decays_with_iteration_and_reward_confidence(
    stub_steer,
):
    cfg = _adaptive_rbf_test_config()

    early, _ = stub_steer._eds_adaptive_rollout_diversity_decision(
        reference=1.0,
        current=0.4,
        rewards=torch.zeros(4),
        iter_idx=0,
        cfg=cfg,
    )
    late, _ = stub_steer._eds_adaptive_rollout_diversity_decision(
        reference=1.0,
        current=0.4,
        rewards=torch.zeros(4),
        iter_idx=4,
        cfg=cfg,
    )
    low_confidence, _ = stub_steer._eds_adaptive_rollout_diversity_decision(
        reference=1.0,
        current=0.4,
        rewards=torch.zeros(4),
        iter_idx=0,
        cfg=cfg,
    )
    high_confidence, high_info = stub_steer._eds_adaptive_rollout_diversity_decision(
        reference=1.0,
        current=0.4,
        rewards=torch.tensor([0.0, 0.0, 0.0, 100.0]),
        iter_idx=0,
        cfg=cfg,
    )

    assert late.scale <= early.scale
    assert high_confidence.reward_confidence > low_confidence.reward_confidence
    assert high_confidence.scale <= low_confidence.scale
    assert 0.0 <= high_info["adaptive_rbf_reward_confidence"] <= 1.0


def test_adaptive_rbf_controller_explains_confidence_suppressed_zero_scale(
    stub_steer,
    monkeypatch,
):
    cfg = _adaptive_rbf_test_config(rollout_diversity_scale_min=0.0)
    monkeypatch.setattr(
        stub_steer,
        "_eds_rollout_reward_confidence",
        lambda rewards: 1.0,
    )

    decision, info = stub_steer._eds_adaptive_rollout_diversity_decision(
        reference=1.0,
        current=0.4,
        rewards=torch.arange(4, dtype=torch.float32),
        iter_idx=0,
        cfg=cfg,
    )

    assert decision.scale == 0.0
    assert decision.enabled is False
    assert decision.reason == "below_band_high_confidence"
    assert info["adaptive_rbf_trigger_reason"] == "below_band_high_confidence"


def test_adaptive_rbf_controller_explains_scale_bounds_disabled_zero_scale(
    stub_steer,
    monkeypatch,
):
    monkeypatch.setattr(
        stub_steer,
        "_eds_rollout_reward_confidence",
        lambda rewards: 1.0,
    )
    decision, info = stub_steer._eds_adaptive_rollout_diversity_decision(
        reference=1.0,
        current=0.4,
        rewards=torch.zeros(4),
        iter_idx=0,
        cfg=_adaptive_rbf_test_config(
            rollout_diversity_scale_min=0.0,
            rollout_diversity_scale_max=0.0,
        ),
    )

    assert decision.scale == 0.0
    assert decision.enabled is False
    assert decision.reason == "below_band_disabled_by_scale_bounds"
    assert info["adaptive_rbf_trigger_reason"] == (
        "below_band_disabled_by_scale_bounds"
    )


@pytest.mark.parametrize("reference", [float("nan"), 0.0, 1e-15])
def test_adaptive_rbf_controller_warns_and_uses_fixed_fallback_for_invalid_reference(
    stub_steer,
    monkeypatch,
    reference,
):
    from core import rdt_policy_steer

    warnings = []
    monkeypatch.setattr(
        rdt_policy_steer.log,
        "warning",
        lambda message: warnings.append(str(message)),
    )
    cfg = _adaptive_rbf_test_config(rollout_diversity_scale=3.25)

    decision, info = stub_steer._eds_adaptive_rollout_diversity_decision(
        reference=reference,
        current=0.2,
        rewards=torch.zeros(4),
        iter_idx=2,
        cfg=cfg,
    )

    assert decision.scale == 3.25
    assert decision.enabled is True
    assert decision.reason == "controller_fallback"
    assert info["adaptive_rbf_fallback_used"] is True
    assert "reference" in info["adaptive_rbf_fallback_reason"]
    assert info["adaptive_rbf_scale_requested"] == 3.25
    assert info["adaptive_rbf_scale_applied"] == 3.25
    assert len(warnings) == 1
    assert "iter=2" in warnings[0]
    assert "reason=" in warnings[0]
    json.dumps(info, allow_nan=False)


def test_adaptive_rbf_controller_warns_once_on_confidence_failure(
    stub_steer,
    monkeypatch,
):
    from core import rdt_policy_steer

    warnings = []
    monkeypatch.setattr(
        rdt_policy_steer.log,
        "warning",
        lambda message: warnings.append(str(message)),
    )
    monkeypatch.setattr(
        stub_steer,
        "_eds_rollout_reward_confidence",
        lambda rewards: (_ for _ in ()).throw(ValueError("confidence exploded")),
    )

    decision, info = stub_steer._eds_adaptive_rollout_diversity_decision(
        reference=1.0,
        current=0.2,
        rewards=torch.zeros(4),
        iter_idx=3,
        cfg=_adaptive_rbf_test_config(rollout_diversity_scale=2.5),
    )

    assert decision.scale == 2.5
    assert info["adaptive_rbf_fallback_used"] is True
    assert "confidence exploded" in info["adaptive_rbf_fallback_reason"]
    assert len(warnings) == 1
    assert "iter=3" in warnings[0]


@pytest.mark.parametrize("error", [AssertionError("bug"), RuntimeError("bug")])
def test_adaptive_rbf_controller_propagates_unknown_failures(
    stub_steer,
    monkeypatch,
    error,
):
    from core import rdt_policy_steer

    warnings = []
    monkeypatch.setattr(
        rdt_policy_steer.log,
        "warning",
        lambda message: warnings.append(str(message)),
    )

    def fail_confidence(rewards):
        raise error

    monkeypatch.setattr(
        stub_steer,
        "_eds_rollout_reward_confidence",
        fail_confidence,
    )

    with pytest.raises(type(error), match="bug"):
        stub_steer._eds_adaptive_rollout_diversity_decision(
            reference=1.0,
            current=0.2,
            rewards=torch.zeros(4),
            iter_idx=0,
            cfg=_adaptive_rbf_test_config(),
        )
    assert warnings == []


def test_adaptive_rbf_reward_confidence_is_zero_for_degenerate_rewards(stub_steer):
    confidence = stub_steer._eds_rollout_reward_confidence(torch.full((8,), 7.0))

    assert confidence == 0.0
    assert type(confidence) is float


def test_adaptive_rbf_reward_confidence_is_zero_for_single_reward(stub_steer):
    confidence = stub_steer._eds_rollout_reward_confidence(torch.tensor([7.0]))

    assert confidence == 0.0


def test_adaptive_rbf_reward_confidence_uses_torch_lower_median_for_even_sample(
    stub_steer,
):
    confidence = stub_steer._eds_rollout_reward_confidence(
        torch.tensor([0.0, 1.0, 2.0, 3.0], dtype=torch.float64)
    )

    assert confidence == pytest.approx(2.0 / (3.0 * 1.4826))


def test_adaptive_rbf_reward_confidence_is_finite_for_extreme_rewards(stub_steer):
    confidence = stub_steer._eds_rollout_reward_confidence(
        torch.tensor([-1.0e308, 0.0, 1.0e308], dtype=torch.float64)
    )

    assert type(confidence) is float
    assert math.isfinite(confidence)
    assert 0.0 <= confidence <= 1.0


@pytest.mark.parametrize(
    ("rewards", "match"),
    [
        ([0.0, 1.0], "torch.Tensor"),
        (torch.zeros(2, 2), "1-D"),
        (torch.tensor([]), "non-empty"),
        (torch.tensor([0.0, float("inf")]), "finite"),
    ],
)
def test_adaptive_rbf_reward_confidence_validates_input(stub_steer, rewards, match):
    with pytest.raises(ValueError, match=match):
        stub_steer._eds_rollout_reward_confidence(rewards)


def test_eds_config_defaults_keep_iid_initial_sampling(stub_steer):
    cfg = stub_steer._resolve_eds_config_with_reference_defaults({})

    assert cfg.initial_sampling_mode == "iid"
    assert cfg.initial_diversity_scale == 1.0
    assert cfg.initial_diversity_start_ratio is None
    assert cfg.initial_diversity_fallback == "iid"
    assert cfg.initial_cache_metadata is True


def test_eds_config_accepts_rollout_diversity_fields(stub_steer):
    cfg = stub_steer._resolve_eds_config_with_reference_defaults(
        {
            "truncated_rollout_mode": "rbf_diverse",
            "rollout_diversity_scale": 10.0,
            "rollout_diversity_start_ratio": 0.8,
            "rollout_diversity_iters": "all",
            "rollout_diversity_skip_final_steps": 0,
        }
    )

    assert cfg.truncated_rollout_mode == "rbf_diverse"
    assert cfg.rollout_diversity_scale == 10.0
    assert cfg.rollout_diversity_start_ratio == 0.8
    assert cfg.rollout_diversity_iters == "all"
    assert cfg.rollout_diversity_skip_final_steps == 0


def test_eds_config_rejects_invalid_truncated_rollout_mode(stub_steer):
    with pytest.raises(ValueError, match="truncated_rollout_mode"):
        stub_steer._resolve_eds_config_with_reference_defaults(
            {"truncated_rollout_mode": "bad"}
        )


@pytest.mark.parametrize("value", [-1, "bad", 1.5, True])
def test_eds_config_rejects_invalid_rollout_diversity_iters(stub_steer, value):
    with pytest.raises(ValueError, match="rollout_diversity_iters"):
        stub_steer._resolve_eds_config_with_reference_defaults(
            {"rollout_diversity_iters": value}
        )


def test_eds_config_rejects_invalid_cem_elites(stub_steer):
    with pytest.raises(ValueError, match="num_elites"):
        stub_steer._resolve_eds_config_with_reference_defaults(
            {"population_size": 4, "use_cem": True, "num_elites": 8}
        )


def test_eds_config_bool_string_false_resolves_false(stub_steer):
    cfg = stub_steer._resolve_eds_config_with_reference_defaults({"use_cem": "false"})

    assert cfg.use_cem is False


def test_eds_config_rejects_invalid_bool_string(stub_steer):
    with pytest.raises(ValueError, match="use_cem"):
        stub_steer._resolve_eds_config_with_reference_defaults({"use_cem": "sometimes"})


def test_eds_config_rejects_invalid_reward_mode(stub_steer):
    with pytest.raises(ValueError, match="reward_mode"):
        stub_steer._resolve_eds_config_with_reference_defaults({"reward_mode": "sparse"})


@pytest.mark.parametrize("mode", ["bad_mode", "rbf", "", "iid+rbf"])
def test_eds_config_rejects_invalid_initial_sampling_mode(stub_steer, mode):
    with pytest.raises(ValueError, match="initial_sampling_mode"):
        stub_steer._resolve_eds_config_with_reference_defaults(
            {"initial_sampling_mode": mode}
        )


@pytest.mark.parametrize("scale", [float("nan"), float("inf"), -float("inf")])
def test_eds_config_rejects_nonfinite_initial_diversity_scale(stub_steer, scale):
    with pytest.raises(ValueError, match="initial_diversity_scale"):
        stub_steer._resolve_eds_config_with_reference_defaults(
            {"initial_diversity_scale": scale}
        )


@pytest.mark.parametrize("ratio", [-0.1, 1.1, float("nan"), float("inf")])
def test_eds_config_rejects_invalid_initial_diversity_start_ratio(stub_steer, ratio):
    with pytest.raises(ValueError, match="initial_diversity_start_ratio"):
        stub_steer._resolve_eds_config_with_reference_defaults(
            {"initial_diversity_start_ratio": ratio}
        )


def test_eds_config_rejects_non_iid_initial_diversity_fallback(stub_steer):
    with pytest.raises(ValueError, match="initial_diversity_fallback"):
        stub_steer._resolve_eds_config_with_reference_defaults(
            {"initial_diversity_fallback": "raise"}
        )


@pytest.mark.parametrize("temperature", [float("nan"), float("inf")])
def test_eds_config_rejects_non_finite_temperature(stub_steer, temperature):
    with pytest.raises(ValueError, match="temperature"):
        stub_steer._resolve_eds_config_with_reference_defaults({"temperature": temperature})


def test_eds_config_rejects_nonpositive_cem_elites(stub_steer):
    with pytest.raises(ValueError, match="num_elites"):
        stub_steer._resolve_eds_config_with_reference_defaults(
            {"population_size": 4, "use_cem": True, "num_elites": 0}
        )


def test_eds_config_rejects_invalid_renoise_schedule(stub_steer):
    with pytest.raises(ValueError, match="renoise_t_min"):
        stub_steer._resolve_eds_config_with_reference_defaults(
            {"renoise_t_max": 1, "renoise_t_min": 3}
        )


def test_trajectory_reward_slice_accepts_eds(stub_steer):
    stub_steer._action_chunk_horizon = 5
    trajs = torch.zeros(2, 5, 3)
    sliced = stub_steer._trajectory_reward_slice(trajs, "eds")
    assert tuple(sliced.shape) == (2, stub_steer._action_chunk_horizon - 1, 3)


def test_eds_direct_vls_reward_scoring_converts_to_cost_when_needed(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    samples = torch.zeros(3, 64, 128)
    monkeypatch.setattr(
        stub_steer,
        "_score_particles",
        lambda samples, keypoints, guidance_fns, slice_kind: torch.tensor([1.0, 3.0, 2.0]),
    )

    costs, info = stub_steer._eds_score_population_as_cost(
        samples,
        keypoints=torch.zeros(3, 3),
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
    )

    torch.testing.assert_close(costs, torch.tensor([-1.0, -3.0, -2.0]))
    torch.testing.assert_close(info["rewards"], torch.tensor([1.0, 3.0, 2.0]))


def test_eds_renoise_reference_uses_scheduler_add_noise(stub_steer):
    population = torch.zeros(2, 64, 128)
    torch.manual_seed(0)
    renoised = stub_steer._eds_renoise_reference(population, 2)

    assert tuple(renoised.shape) == (2, 64, 128)
    assert not torch.equal(renoised, population)


def test_eds_renoise_reference_passes_batch_timesteps_and_refreshes_scheduler(stub_steer):
    class StrictAddNoiseScheduler:
        def __init__(self):
            self.timesteps = torch.tensor([99], dtype=torch.long)
            self.set_calls = 0
            self.recorded_timestep_shape = None
            self.recorded_timestep_device = None

        def set_timesteps(self, n):
            self.set_calls += 1
            self.timesteps = torch.arange(n - 1, -1, -1, dtype=torch.long)

        def add_noise(self, original_samples, noise, timesteps):
            if timesteps.ndim == 0:
                raise AssertionError("add_noise requires batch timesteps, not a scalar")
            self.recorded_timestep_shape = tuple(timesteps.shape)
            self.recorded_timestep_device = timesteps.device
            return original_samples + noise

    scheduler = StrictAddNoiseScheduler()
    stub_steer._rdt_model.noise_scheduler = scheduler
    population = torch.zeros(3, 64, 128)

    renoised = stub_steer._eds_renoise_reference(population, 2)

    assert scheduler.set_calls == 1
    assert scheduler.recorded_timestep_shape == (3,)
    assert scheduler.recorded_timestep_device == population.device
    assert tuple(renoised.shape) == (3, 64, 128)


def test_eds_initial_population_masks_cached_population(stub_steer, tmp_path):
    from core.rdt_policy_steer import _EDSConfig

    population = torch.ones(2, 64, 128)
    cache_path = tmp_path / "eds_initial.pt"
    torch.save(
        {
            "initial_population": population,
            "metadata": {
                "initial_sampling_mode": "iid",
                "initial_diversity_scale": 1.0,
                "initial_diversity_start_ratio": None,
                "initial_diversity_fallback": "iid",
            },
        },
        cache_path,
    )
    x_t = torch.zeros(2, 64, 128)
    action_mask = torch.zeros(1, 1, 128)
    action_mask[0, 0, [39, 40, 41, 42, 43, 44, 10]] = 1.0
    cond = {"action_mask": action_mask}

    cached = stub_steer._eds_initial_population(
        x_t=x_t,
        cond=cond,
        cfg=_EDSConfig(
            population_size=2,
            use_initial_cache=True,
            initial_population_cache=str(cache_path),
            save_initial_cache=True,
        ),
    )

    assert torch.count_nonzero(cached[:, :, 0]) == 0
    assert torch.count_nonzero(cached[:, :, 39]) == cached.shape[0] * cached.shape[1]
    saved = torch.load(cache_path)
    torch.testing.assert_close(saved["initial_population"], cached)


def test_eds_initial_population_iid_mode_preserves_shape_and_mask(stub_steer):
    from core.rdt_policy_steer import _EDSConfig

    x_t = torch.ones(3, 64, 128)
    action_mask = torch.zeros(1, 1, 128)
    action_mask[0, 0, [39, 40, 41, 42, 43, 44, 10]] = 1.0
    cond = {"action_mask": action_mask}

    population = stub_steer._eds_initial_population(
        x_t=x_t,
        cond=cond,
        cfg=_EDSConfig(population_size=3, initial_sampling_mode="iid"),
    )

    assert tuple(population.shape) == (3, 64, 128)
    assert torch.count_nonzero(population[:, :, 0]) == 0
    assert torch.isfinite(population).all()


def test_eds_initial_population_iid_rejects_nonfinite_after_masking(
    stub_steer, monkeypatch
):
    from core.rdt_policy_steer import _EDSConfig

    def fake_iid(*, x_t, cond, cfg):
        population = torch.zeros_like(x_t)
        population[:, :, 39] = float("nan")
        return population, {"initial_diversity_steps": 0}

    monkeypatch.setattr(stub_steer, "_eds_initial_denoise_iid", fake_iid)

    with pytest.raises(ValueError, match="EDS initial population.*finite"):
        stub_steer._eds_initial_population(
            x_t=torch.zeros(2, 64, 128),
            cond={"action_mask": torch.ones(1, 1, 128)},
            cfg=_EDSConfig(population_size=2, initial_sampling_mode="iid"),
        )


def test_eds_initial_population_rbf_validation_failure_fallbacks_to_iid(
    stub_steer, monkeypatch
):
    from core.rdt_policy_steer import _EDSConfig

    calls = {"iid": 0}

    def fake_rbf(*, x_t, cond, cfg):
        population = torch.zeros_like(x_t)
        population[:, :, 39] = float("nan")
        return population, {"initial_diversity_steps": 1}

    def fake_iid(*, x_t, cond, cfg):
        calls["iid"] += 1
        return torch.zeros_like(x_t), {"initial_diversity_steps": 0}

    monkeypatch.setattr(stub_steer, "_eds_initial_denoise_rbf_diverse", fake_rbf)
    monkeypatch.setattr(stub_steer, "_eds_initial_denoise_iid", fake_iid)

    population = stub_steer._eds_initial_population(
        x_t=torch.zeros(2, 64, 128),
        cond={"action_mask": torch.ones(1, 1, 128)},
        cfg=_EDSConfig(
            population_size=2,
            initial_sampling_mode="rbf_diverse_denoise",
        ),
    )

    assert calls["iid"] == 1
    assert torch.isfinite(population).all()
    info = stub_steer._last_eds_initial_sampler_info
    assert info["initial_diversity_fallback_used"] is True
    assert "validation" in info["initial_diversity_fallback_reason"]


def test_eds_initial_population_rbf_diverse_uses_diversity_gradient(
    stub_steer, stub_adapter, monkeypatch
):
    from core.rdt_policy_steer import _EDSConfig

    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    calls = {"diversity": 0}

    def fake_diversity(x_t):
        calls["diversity"] += 1
        grad = torch.zeros_like(x_t)
        grad[:, :4, 39] = torch.tensor([0.0, 1.0, -1.0]).view(3, 1)
        return grad

    monkeypatch.setattr(stub_steer, "_compute_diversity_gradient", fake_diversity)
    action_mask = torch.zeros(1, 1, 128)
    action_mask[0, 0, [39, 40, 41, 42, 43, 44, 10]] = 1.0

    population = stub_steer._eds_initial_population(
        x_t=torch.zeros(3, 64, 128),
        cond={"action_mask": action_mask},
        cfg=_EDSConfig(
            population_size=3,
            initial_sampling_mode="rbf_diverse_denoise",
            initial_diversity_scale=2.0,
        ),
    )

    assert calls["diversity"] > 0
    assert tuple(population.shape) == (3, 64, 128)
    assert torch.count_nonzero(population[:, :, 0]) == 0
    assert torch.count_nonzero(population[:, :4, 39]) > 0
    info = stub_steer._last_eds_initial_sampler_info
    assert info["initial_sampling_mode"] == "rbf_diverse_denoise"
    assert info["initial_diversity_steps"] > 0
    assert info["initial_diversity_fallback_used"] is False


def test_eds_mechanism_trace_records_rbf_initial_sampler_stages(
    stub_steer, stub_adapter, mock_batch, monkeypatch
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )

    def fake_diversity(x_t):
        grad = torch.zeros_like(x_t)
        grad[:, :4, 39] = torch.tensor([0.0, 1.0, -1.0]).view(3, 1)
        return grad

    monkeypatch.setattr(stub_steer, "_compute_diversity_gradient", fake_diversity)

    stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="eds",
        keypoints=np.zeros((1, 3), dtype=np.float32),
        guidance_fns=[lambda keypoints, traj: -torch.linalg.norm(traj[:, -1, :3], dim=-1).sum()],
        eds_config={
            "population_size": 3,
            "cem_iters": 1,
            "temperature": 0.1,
            "initial_sampling_mode": "rbf_diverse_denoise",
            "mechanism_pretest": {
                "enabled": True,
                "first_chunk_only": True,
                "save_single_step": True,
                "save_full_process": True,
                "save_tensors": True,
                "plot_3d": False,
                "max_full_process_iters": 1,
            },
        },
        global_step=0,
    )

    trace = stub_steer.get_last_eds_mechanism_trace()
    stages = {stage.stage for stage in trace.stages}

    assert "initial_before_diversity" in stages
    assert "initial_after_diversity_phase" in stages
    assert "initial_final" in stages
    assert trace.initial_sampler_info["initial_sampling_mode"] == "rbf_diverse_denoise"


def test_eds_initial_sampler_trace_stages_use_stage_population_rewards(
    stub_steer, stub_adapter, mock_batch, monkeypatch
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )

    def population_with_x_deltas(values):
        population = torch.zeros(3, 64, 128, dtype=torch.float32)
        population[:, :4, 39] = torch.tensor(values, dtype=torch.float32).view(3, 1)
        return population

    before_population = population_with_x_deltas([0.1, 0.2, 0.3])
    after_population = population_with_x_deltas([0.4, 0.5, 0.6])
    final_population = population_with_x_deltas([0.7, 0.8, 0.9])

    def fake_initial_population(*, x_t, cond, cfg):
        stub_steer._last_eds_initial_sampler_trace_stages = [
            ("initial_before_diversity", before_population.to(device=x_t.device, dtype=x_t.dtype)),
            (
                "initial_after_diversity_phase",
                after_population.to(device=x_t.device, dtype=x_t.dtype),
            ),
            ("initial_final", final_population.to(device=x_t.device, dtype=x_t.dtype)),
        ]
        stub_steer._last_eds_initial_sampler_info = {
            "initial_sampling_mode": "rbf_diverse_denoise",
        }
        return final_population.to(device=x_t.device, dtype=x_t.dtype)

    def reward_from_x_trajectory(keypoints, traj):
        return traj[..., 0].sum()

    monkeypatch.setattr(stub_steer, "_eds_initial_population", fake_initial_population)

    stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="eds",
        keypoints=np.zeros((1, 3), dtype=np.float32),
        guidance_fns=[reward_from_x_trajectory],
        eds_config={
            "population_size": 3,
            "cem_iters": 1,
            "temperature": 0.1,
            "initial_sampling_mode": "rbf_diverse_denoise",
            "mechanism_pretest": {
                "enabled": True,
                "first_chunk_only": True,
                "save_single_step": True,
                "save_full_process": False,
                "save_tensors": True,
                "plot_3d": False,
                "max_full_process_iters": 1,
            },
        },
        global_step=0,
    )

    trace = stub_steer.get_last_eds_mechanism_trace()
    stages = {stage.stage: stage for stage in trace.stages}
    before_stage = stages["initial_before_diversity"]
    final_stage = stages["initial_final"]

    expected_before_rewards = before_stage.trajectories[..., 0].sum(dim=1)
    expected_final_rewards = final_stage.trajectories[..., 0].sum(dim=1)

    assert not torch.allclose(before_stage.rewards, final_stage.rewards)
    torch.testing.assert_close(before_stage.rewards, expected_before_rewards)
    torch.testing.assert_close(before_stage.costs, -expected_before_rewards)
    torch.testing.assert_close(final_stage.rewards, expected_final_rewards)
    torch.testing.assert_close(final_stage.costs, -expected_final_rewards)


def test_eds_initial_eef_diversity_helpers_match_trajectory_space(
    stub_steer, stub_adapter
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    sample = _deterministic_diversity_sample()

    assert stub_steer._eds_eef_trajectory_diversity(sample) == pytest.approx(
        float(_trajectory_spread(stub_steer, sample).item())
    )
    assert stub_steer._eds_endpoint_spread(sample) == pytest.approx(
        float(_endpoint_spread(stub_steer, sample).item())
    )


def test_eds_loop_records_initial_eef_diversity_metrics(
    stub_steer, stub_adapter, mock_batch, monkeypatch
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )

    before_population = _deterministic_diversity_sample()
    after_population = before_population.clone()
    after_population[2, :4, 40] *= 2.0
    final_population = after_population.clone()
    final_population[1, :4, 39] *= 0.5

    def fake_initial_population(*, x_t, cond, cfg):
        stub_steer._last_eds_initial_sampler_trace_stages = [
            ("initial_before_diversity", before_population.to(device=x_t.device, dtype=x_t.dtype)),
            (
                "initial_after_diversity_phase",
                after_population.to(device=x_t.device, dtype=x_t.dtype),
            ),
            ("initial_final", final_population.to(device=x_t.device, dtype=x_t.dtype)),
        ]
        stub_steer._last_eds_initial_sampler_info = {
            "initial_sampling_mode": "rbf_diverse_denoise",
        }
        return final_population.to(device=x_t.device, dtype=x_t.dtype)

    monkeypatch.setattr(stub_steer, "_eds_initial_population", fake_initial_population)

    stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="eds",
        keypoints=np.zeros((1, 3), dtype=np.float32),
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        eds_config={
            "population_size": 3,
            "cem_iters": 1,
            "temperature": 0.1,
            "initial_sampling_mode": "rbf_diverse_denoise",
        },
        global_step=0,
    )

    metrics = stub_steer.get_last_eds_metrics()
    expected_after = float(_trajectory_spread(stub_steer, after_population).item())
    expected_final = float(_trajectory_spread(stub_steer, final_population).item())

    assert metrics["initial_eef_diversity_before_rbf"] == pytest.approx(
        float(_trajectory_spread(stub_steer, before_population).item())
    )
    assert metrics["initial_eef_diversity_after_rbf_phase"] == pytest.approx(expected_after)
    assert metrics["initial_eef_diversity_final"] == pytest.approx(expected_final)
    assert metrics["initial_eef_diversity_retention_ratio"] == pytest.approx(
        expected_final / expected_after
    )
    assert metrics["endpoint_spread_before_rbf"] == pytest.approx(
        float(_endpoint_spread(stub_steer, before_population).item())
    )
    assert metrics["endpoint_spread_after_rbf_phase"] == pytest.approx(
        float(_endpoint_spread(stub_steer, after_population).item())
    )
    assert metrics["endpoint_spread_final"] == pytest.approx(
        float(_endpoint_spread(stub_steer, final_population).item())
    )


def test_eds_initial_population_rbf_diverse_cache_restores_telemetry(
    stub_steer, stub_adapter, tmp_path, monkeypatch
):
    from core.rdt_policy_steer import _EDSConfig

    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )

    def fake_diversity(x_t):
        grad = torch.zeros_like(x_t)
        grad[:, :4, 39] = torch.tensor([0.0, 1.0, -1.0]).view(3, 1)
        return grad

    monkeypatch.setattr(stub_steer, "_compute_diversity_gradient", fake_diversity)
    cache_path = tmp_path / "rbf_eds_initial.pt"
    action_mask = torch.zeros(1, 1, 128)
    action_mask[0, 0, [39, 40, 41, 42, 43, 44, 10]] = 1.0
    cfg = _EDSConfig(
        population_size=3,
        initial_sampling_mode="rbf_diverse_denoise",
        initial_diversity_scale=2.0,
        save_initial_cache=True,
        initial_population_cache=str(cache_path),
    )

    stub_steer._eds_initial_population(
        x_t=torch.zeros(3, 64, 128),
        cond={"action_mask": action_mask},
        cfg=cfg,
    )
    saved_info = dict(stub_steer._last_eds_initial_sampler_info)

    restored = stub_steer._eds_initial_population(
        x_t=torch.zeros(3, 64, 128),
        cond={"action_mask": action_mask},
        cfg=_EDSConfig(
            population_size=3,
            initial_sampling_mode="rbf_diverse_denoise",
            initial_diversity_scale=2.0,
            use_initial_cache=True,
            initial_population_cache=str(cache_path),
        ),
    )

    assert tuple(restored.shape) == (3, 64, 128)
    restored_info = stub_steer._last_eds_initial_sampler_info
    for field in (
        "initial_diversity_steps",
        "initial_diversity_fallback_used",
        "initial_diversity_fallback_reason",
        "initial_diversity_grad_failure_count",
        "initial_diversity_grad_norm_mean",
        "initial_diversity_grad_norm_max",
    ):
        assert restored_info[field] == saved_info[field]
    assert restored_info["initial_diversity_steps"] > 0
    assert restored_info["initial_diversity_grad_norm_mean"] is not None
    assert restored_info["initial_diversity_grad_norm_max"] is not None


def test_eds_initial_population_rbf_diverse_warns_and_fallbacks_to_iid(
    stub_steer, monkeypatch, caplog
):
    from core import rdt_policy_steer
    from core.rdt_policy_steer import _EDSConfig

    def no_diversity(_x_t):
        return None

    monkeypatch.setattr(stub_steer, "_compute_diversity_gradient", no_diversity)
    warnings = []
    monkeypatch.setattr(
        rdt_policy_steer.log,
        "warning",
        lambda message: warnings.append(str(message)),
    )
    action_mask = torch.ones(1, 1, 128)

    population = stub_steer._eds_initial_population(
        x_t=torch.zeros(3, 64, 128),
        cond={"action_mask": action_mask},
        cfg=_EDSConfig(
            population_size=3,
            initial_sampling_mode="rbf_diverse_denoise",
        ),
    )

    assert tuple(population.shape) == (3, 64, 128)
    warning_text = "\n".join(warnings) + caplog.text
    assert "fallback" in warning_text.lower()
    assert "rbf_diverse_denoise" in warning_text
    info = stub_steer._last_eds_initial_sampler_info
    assert info["initial_diversity_fallback_used"] is True
    assert info["initial_diversity_fallback_reason"]
    assert info["initial_diversity_grad_failure_count"] == 1


def test_eds_initial_population_rbf_diverse_nonfinite_gradient_fallbacks(
    stub_steer, monkeypatch, caplog
):
    from core import rdt_policy_steer
    from core.rdt_policy_steer import _EDSConfig

    def bad_diversity(x_t):
        grad = torch.zeros_like(x_t)
        grad[0, 0, 39] = float("nan")
        return grad

    monkeypatch.setattr(stub_steer, "_compute_diversity_gradient", bad_diversity)
    warnings = []
    monkeypatch.setattr(
        rdt_policy_steer.log,
        "warning",
        lambda message: warnings.append(str(message)),
    )

    population = stub_steer._eds_initial_population(
        x_t=torch.zeros(3, 64, 128),
        cond={"action_mask": torch.ones(1, 1, 128)},
        cfg=_EDSConfig(
            population_size=3,
            initial_sampling_mode="rbf_diverse_denoise",
        ),
    )

    assert torch.isfinite(population).all()
    warning_text = "\n".join(warnings) + caplog.text
    assert "non-finite" in warning_text.lower()
    info = stub_steer._last_eds_initial_sampler_info
    assert info["initial_diversity_fallback_used"] is True
    assert info["initial_diversity_grad_failure_count"] == 1


def test_eds_initial_population_rbf_diverse_partial_failure_fallbacks_from_original(
    stub_steer, monkeypatch
):
    from core.rdt_policy_steer import _EDSConfig

    calls = {"diversity": 0}

    def delayed_failure(x_t):
        calls["diversity"] += 1
        if calls["diversity"] == 1:
            grad = torch.zeros_like(x_t)
            grad[:, :4, 39] = torch.tensor([0.0, 1.0, -1.0]).view(3, 1)
            return grad
        return None

    monkeypatch.setattr(stub_steer, "_compute_diversity_gradient", delayed_failure)
    x_t = torch.full((3, 64, 128), 0.25)
    cfg = _EDSConfig(
        population_size=3,
        initial_sampling_mode="rbf_diverse_denoise",
        initial_diversity_scale=2.0,
        initial_diversity_start_ratio=0.8,
    )
    cond = {"action_mask": torch.ones(1, 1, 128)}

    population = stub_steer._eds_initial_population(x_t=x_t, cond=cond, cfg=cfg)
    fallback_info = stub_steer._last_eds_initial_sampler_info
    iid_population = stub_steer._eds_initial_population(
        x_t=x_t,
        cond=cond,
        cfg=_EDSConfig(population_size=3, initial_sampling_mode="iid"),
    )

    assert calls["diversity"] == 2
    torch.testing.assert_close(population, iid_population)
    assert fallback_info["initial_diversity_steps"] == 0
    assert fallback_info["initial_diversity_fallback_used"] is True
    assert fallback_info["initial_diversity_grad_failure_count"] == 1


def test_eds_initial_population_rejects_cache_strategy_mismatch(stub_steer, tmp_path):
    from core.rdt_policy_steer import _EDSConfig

    cache_path = tmp_path / "eds_initial.pt"
    torch.save(
        {
            "initial_population": torch.zeros(2, 64, 128),
            "metadata": {"initial_sampling_mode": "iid"},
        },
        cache_path,
    )
    action_mask = torch.ones(1, 1, 128)

    with pytest.raises(ValueError, match="initial_population_cache.*initial_sampling_mode"):
        stub_steer._eds_initial_population(
            x_t=torch.zeros(2, 64, 128),
            cond={"action_mask": action_mask},
            cfg=_EDSConfig(
                population_size=2,
                use_initial_cache=True,
                initial_population_cache=str(cache_path),
                initial_sampling_mode="rbf_diverse_denoise",
            ),
        )


def test_eds_initial_population_warns_for_legacy_cache_without_metadata(
    stub_steer, tmp_path, monkeypatch
):
    from core import rdt_policy_steer
    from core.rdt_policy_steer import _EDSConfig

    cache_path = tmp_path / "legacy_eds_initial.pt"
    torch.save({"initial_population": torch.zeros(2, 64, 128)}, cache_path)
    action_mask = torch.ones(1, 1, 128)
    warnings = []
    monkeypatch.setattr(
        rdt_policy_steer.log,
        "warning",
        lambda message: warnings.append(str(message)),
    )

    population = stub_steer._eds_initial_population(
        x_t=torch.zeros(2, 64, 128),
        cond={"action_mask": action_mask},
        cfg=_EDSConfig(
            population_size=2,
            use_initial_cache=True,
            initial_population_cache=str(cache_path),
            initial_sampling_mode="iid",
        ),
    )

    assert tuple(population.shape) == (2, 64, 128)
    assert any("metadata" in message.lower() for message in warnings)


def test_eds_initial_population_rejects_rbf_legacy_cache_without_metadata(
    stub_steer, tmp_path
):
    from core.rdt_policy_steer import _EDSConfig

    cache_path = tmp_path / "legacy_rbf_eds_initial.pt"
    torch.save({"initial_population": torch.zeros(2, 64, 128)}, cache_path)

    with pytest.raises(ValueError, match="metadata.*rbf_diverse_denoise"):
        stub_steer._eds_initial_population(
            x_t=torch.zeros(2, 64, 128),
            cond={"action_mask": torch.ones(1, 1, 128)},
            cfg=_EDSConfig(
                population_size=2,
                use_initial_cache=True,
                initial_population_cache=str(cache_path),
                initial_sampling_mode="rbf_diverse_denoise",
            ),
        )


def test_eds_initial_population_allows_rbf_legacy_cache_when_metadata_disabled(
    stub_steer, tmp_path, monkeypatch
):
    from core import rdt_policy_steer
    from core.rdt_policy_steer import _EDSConfig

    cache_path = tmp_path / "unchecked_legacy_rbf_eds_initial.pt"
    torch.save({"initial_population": torch.ones(2, 64, 128)}, cache_path)
    warnings = []
    monkeypatch.setattr(
        rdt_policy_steer.log,
        "warning",
        lambda message: warnings.append(str(message)),
    )

    population = stub_steer._eds_initial_population(
        x_t=torch.zeros(2, 64, 128),
        cond={"action_mask": torch.ones(1, 1, 128)},
        cfg=_EDSConfig(
            population_size=2,
            use_initial_cache=True,
            initial_population_cache=str(cache_path),
            initial_sampling_mode="rbf_diverse_denoise",
            initial_cache_metadata=False,
        ),
    )

    assert tuple(population.shape) == (2, 64, 128)
    assert torch.all(population == 1)
    info = stub_steer._last_eds_initial_sampler_info
    assert info["initial_sampling_mode"] == "rbf_diverse_denoise"
    assert info["initial_diversity_fallback_used"] is False
    assert any("metadata validation is disabled" in message for message in warnings)


def test_eds_initial_population_ignores_stale_metadata_when_metadata_disabled(
    stub_steer, tmp_path, monkeypatch
):
    from core import rdt_policy_steer
    from core.rdt_policy_steer import _EDSConfig

    cache_path = tmp_path / "stale_metadata_rbf_eds_initial.pt"
    torch.save(
        {
            "initial_population": torch.ones(2, 64, 128),
            "metadata": {
                "initial_sampling_mode": "iid",
                "initial_diversity_scale": 99.0,
                "initial_diversity_start_ratio": 0.5,
                "initial_diversity_fallback": "iid",
                "initial_diversity_fallback_used": True,
                "initial_diversity_fallback_reason": "stale-cache",
            },
        },
        cache_path,
    )
    warnings = []
    monkeypatch.setattr(
        rdt_policy_steer.log,
        "warning",
        lambda message: warnings.append(str(message)),
    )

    stub_steer._eds_initial_population(
        x_t=torch.zeros(2, 64, 128),
        cond={"action_mask": torch.ones(1, 1, 128)},
        cfg=_EDSConfig(
            population_size=2,
            use_initial_cache=True,
            initial_population_cache=str(cache_path),
            initial_sampling_mode="rbf_diverse_denoise",
            initial_diversity_scale=1.0,
            initial_cache_metadata=False,
        ),
    )

    info = stub_steer._last_eds_initial_sampler_info
    assert info["initial_sampling_mode"] == "rbf_diverse_denoise"
    assert info["initial_diversity_scale"] == 1.0
    assert info["initial_diversity_start_ratio"] is None
    assert info["initial_diversity_fallback_used"] is False
    assert info["initial_diversity_fallback_reason"] is None
    assert any("metadata validation is disabled" in message for message in warnings)


def test_eds_initial_population_rejects_resaving_legacy_cache_without_metadata(
    stub_steer, tmp_path
):
    from core.rdt_policy_steer import _EDSConfig

    cache_path = tmp_path / "legacy_eds_initial.pt"
    torch.save({"initial_population": torch.zeros(2, 64, 128)}, cache_path)

    with pytest.raises(ValueError, match="metadata.*save_initial_cache"):
        stub_steer._eds_initial_population(
            x_t=torch.zeros(2, 64, 128),
            cond={"action_mask": torch.ones(1, 1, 128)},
            cfg=_EDSConfig(
                population_size=2,
                use_initial_cache=True,
                save_initial_cache=True,
                initial_population_cache=str(cache_path),
                initial_sampling_mode="rbf_diverse_denoise",
            ),
        )


def test_eds_initial_population_cache_refreshes_sampler_info_after_fallback(
    stub_steer, tmp_path
):
    from core.rdt_policy_steer import _EDSConfig

    action_mask = torch.ones(1, 1, 128)
    cond = {"action_mask": action_mask}
    stub_steer._eds_initial_population(
        x_t=torch.zeros(2, 64, 128),
        cond=cond,
        cfg=_EDSConfig(
            population_size=2,
            initial_sampling_mode="rbf_diverse_denoise",
        ),
    )
    assert stub_steer._last_eds_initial_sampler_info["initial_diversity_fallback_used"] is True

    cache_path = tmp_path / "eds_initial.pt"
    torch.save(
        {
            "initial_population": torch.zeros(2, 64, 128),
            "metadata": {
                "initial_sampling_mode": "iid",
                "initial_diversity_scale": 1.0,
                "initial_diversity_start_ratio": None,
                "initial_diversity_fallback": "iid",
                "initial_diversity_steps": 0,
                "initial_diversity_fallback_used": False,
                "initial_diversity_fallback_reason": None,
            },
        },
        cache_path,
    )

    stub_steer._eds_initial_population(
        x_t=torch.zeros(2, 64, 128),
        cond=cond,
        cfg=_EDSConfig(
            population_size=2,
            use_initial_cache=True,
            initial_population_cache=str(cache_path),
            initial_sampling_mode="iid",
        ),
    )

    info = stub_steer._last_eds_initial_sampler_info
    assert info["initial_sampling_mode"] == "iid"
    assert info["initial_diversity_fallback_used"] is False
    assert info["initial_diversity_fallback_reason"] is None
    assert info["initial_sampler_latency_s"] is not None


def test_eds_initial_population_rejects_cache_diversity_scale_mismatch(
    stub_steer, tmp_path
):
    from core.rdt_policy_steer import _EDSConfig

    cache_path = tmp_path / "eds_initial.pt"
    torch.save(
        {
            "initial_population": torch.zeros(2, 64, 128),
            "metadata": {
                "initial_sampling_mode": "rbf_diverse_denoise",
                "initial_diversity_scale": 0.25,
                "initial_diversity_start_ratio": 0.5,
                "initial_diversity_fallback": "iid",
            },
        },
        cache_path,
    )

    with pytest.raises(ValueError, match="initial_diversity_scale"):
        stub_steer._eds_initial_population(
            x_t=torch.zeros(2, 64, 128),
            cond={"action_mask": torch.ones(1, 1, 128)},
            cfg=_EDSConfig(
                population_size=2,
                use_initial_cache=True,
                initial_population_cache=str(cache_path),
                initial_sampling_mode="rbf_diverse_denoise",
                initial_diversity_scale=2.0,
                initial_diversity_start_ratio=0.5,
            ),
        )


def test_eds_initial_population_rejects_malformed_cache_metadata(
    stub_steer, tmp_path
):
    from core.rdt_policy_steer import _EDSConfig

    cache_path = tmp_path / "eds_initial.pt"
    torch.save(
        {
            "initial_population": torch.zeros(2, 64, 128),
            "metadata": "bad",
        },
        cache_path,
    )

    with pytest.raises((TypeError, ValueError), match="metadata"):
        stub_steer._eds_initial_population(
            x_t=torch.zeros(2, 64, 128),
            cond={"action_mask": torch.ones(1, 1, 128)},
            cfg=_EDSConfig(
                population_size=2,
                use_initial_cache=True,
                initial_population_cache=str(cache_path),
            ),
        )


def test_eds_rollout_reference_scores_clean_denoised_population(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"action_chunk_horizon": 4},
    )
    cond = stub_steer._rdt_model.encode_inputs(
        torch.zeros(1, 128),
        torch.zeros(1, 128).scatter(1, torch.tensor([[0]]), 1.0),
        [],
        torch.zeros(1, 1, 4),
    )
    cond["action_mask"][0, 0, [39, 40, 41, 42, 43, 44, 10]] = 1.0
    noisy = torch.randn(2, 64, 128)
    score_calls = []

    def fake_score(samples, keypoints, guidance_fns, slice_kind):
        score_calls.append((tuple(samples.shape), slice_kind))
        return torch.tensor([1.0, 2.0], device=samples.device, dtype=samples.dtype)

    monkeypatch.setattr(stub_steer, "_score_particles", fake_score)

    denoised, costs, info = stub_steer._eds_rollout_reference(
        cond=cond,
        action_mask=cond["action_mask"],
        noisy_action=noisy,
        keypoints=torch.zeros(3, 3),
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        n_trunc_steps=2,
    )

    assert tuple(denoised.shape) == (2, 64, 128)
    assert score_calls[-1] == ((2, 64, 128), "eds")
    torch.testing.assert_close(costs, torch.tensor([-1.0, -2.0]))
    torch.testing.assert_close(info["rewards"], torch.tensor([1.0, 2.0]))


def test_eds_rollout_baseline_does_not_call_diversity_gradient(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    from core.rdt_policy_steer import _EDSConfig

    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    cond = _rollout_cond(stub_steer)

    def fail_diversity(_x_t):
        raise AssertionError("baseline rollout must not call diversity gradient")

    monkeypatch.setattr(stub_steer, "_compute_diversity_gradient", fail_diversity)

    _population, _costs, info = stub_steer._eds_rollout_reference(
        cond=cond,
        action_mask=cond["action_mask"],
        noisy_action=torch.zeros(3, 64, 128),
        keypoints=torch.zeros(1, 3),
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        n_trunc_steps=2,
        cfg=_EDSConfig(population_size=3, truncated_rollout_mode="baseline"),
    )

    assert info["rollout_diversity_enabled"] is False
    assert info["rollout_diversity_mode"] == "baseline"
    assert info["rollout_diversity_steps_applied"] == 0


def test_eds_rollout_rbf_diverse_applies_gradient_to_rollout_steps(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    from core.rdt_policy_steer import _EDSConfig

    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    cond = _rollout_cond(stub_steer)
    calls = []

    def fake_diversity(x_t):
        calls.append(tuple(x_t.shape))
        grad = torch.zeros_like(x_t)
        grad[:, :4, 39] = torch.tensor([0.0, 1.0, -1.0]).view(3, 1)
        return grad

    monkeypatch.setattr(stub_steer, "_compute_diversity_gradient", fake_diversity)

    population, _costs, info = stub_steer._eds_rollout_reference(
        cond=cond,
        action_mask=cond["action_mask"],
        noisy_action=torch.zeros(3, 64, 128),
        keypoints=torch.zeros(1, 3),
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        n_trunc_steps=2,
        cfg=_EDSConfig(
            population_size=3,
            truncated_rollout_mode="rbf_diverse",
            rollout_diversity_scale=2.0,
            rollout_diversity_start_ratio=0.5,
            rollout_diversity_iters="all",
        ),
        iter_idx=0,
    )

    assert calls == [(3, 64, 128)]
    assert info["rollout_diversity_enabled"] is True
    assert info["rollout_diversity_steps_applied"] == 1
    assert info["rollout_diversity_iters_applied"] == 1
    assert info["rollout_diversity_grad_norm_mean"] is not None
    assert info["eef_diversity_before_rollout"] is not None
    assert info["eef_diversity_after_rollout_final"] is not None
    assert {name for name, _stage in info["rollout_diversity_trace_stages"]} == {
        "rollout_before_diversity",
        "rollout_after_diversity_phase",
        "rollout_final",
    }
    assert torch.count_nonzero(population[:, :4, 39]) > 0
    assert torch.count_nonzero(population[:, :, 0]) == 0


def test_rollout_diversity_fixed_mode_ignores_override_exactly(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    from core.rdt_policy_steer import _EDSConfig

    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    cond = _rollout_cond(stub_steer)

    def fake_diversity(x_t):
        grad = torch.zeros_like(x_t)
        grad[:, :4, 39] = torch.tensor([0.0, 1.0, -1.0]).view(3, 1)
        return grad

    monkeypatch.setattr(stub_steer, "_compute_diversity_gradient", fake_diversity)
    cfg = _EDSConfig(
        population_size=3,
        truncated_rollout_mode="rbf_diverse",
        rollout_diversity_control_mode="fixed",
        rollout_diversity_scale=2.0,
        rollout_diversity_iters="all",
    )
    kwargs = {
        "cond": cond,
        "action_mask": cond["action_mask"],
        "noisy_action": torch.zeros(3, 64, 128),
        "keypoints": torch.zeros(1, 3),
        "guidance_fns": [lambda keypoints, traj: traj[..., 0].sum()],
        "n_trunc_steps": 1,
        "reward_mode": "normal",
        "shuffle_seed": 0,
        "cfg": cfg,
        "iter_idx": 0,
    }

    old_population, old_costs, old_info = stub_steer._eds_rollout_rbf_diverse_reference(
        **kwargs
    )
    wired_population, wired_costs, wired_info = (
        stub_steer._eds_rollout_rbf_diverse_reference(
            **kwargs,
            diversity_scale_override=-7.0,
        )
    )

    assert torch.equal(wired_population, old_population)
    assert torch.equal(wired_costs, old_costs)
    for key in (
        "rollout_diversity_enabled",
        "rollout_diversity_scale",
        "rollout_diversity_steps_applied",
        "rollout_diversity_iters_applied",
        "rollout_diversity_grad_norms",
        "rollout_diversity_fallback_used",
        "rollout_diversity_fallback_reason",
    ):
        assert wired_info[key] == old_info[key]
    assert wired_info["rollout_diversity_scale"] == 2.0


def test_adaptive_rbf_positive_and_zero_override_apply_or_skip_gradient(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    cond = _rollout_cond(stub_steer)
    calls = []

    def fake_diversity(x_t):
        calls.append(tuple(x_t.shape))
        grad = torch.zeros_like(x_t)
        grad[:, :4, 39] = torch.tensor([0.0, 1.0, -1.0]).view(3, 1)
        return grad

    monkeypatch.setattr(stub_steer, "_compute_diversity_gradient", fake_diversity)
    cfg = _adaptive_rbf_test_config(population_size=3)
    kwargs = {
        "cond": cond,
        "action_mask": cond["action_mask"],
        "noisy_action": torch.zeros(3, 64, 128),
        "keypoints": torch.zeros(1, 3),
        "guidance_fns": [lambda keypoints, traj: traj[..., 0].sum()],
        "n_trunc_steps": 1,
        "cfg": cfg,
        "iter_idx": 0,
    }

    positive_population, _positive_costs, positive_info = (
        stub_steer._eds_rollout_reference(
            **kwargs,
            diversity_scale_override=2.0,
        )
    )
    zero_population, zero_costs, zero_info = stub_steer._eds_rollout_reference(
        **kwargs,
        diversity_scale_override=0.0,
    )
    baseline_population, baseline_costs, _baseline_info = (
        stub_steer._eds_rollout_baseline_reference(**{k: v for k, v in kwargs.items() if k != "iter_idx"})
    )

    assert calls == [(3, 64, 128)]
    assert torch.count_nonzero(positive_population[:, :4, 39]) > 0
    assert positive_info["rollout_diversity_enabled"] is True
    assert positive_info["rollout_diversity_scale"] == 2.0
    assert torch.equal(zero_population, baseline_population)
    assert torch.equal(zero_costs, baseline_costs)
    assert zero_info["rollout_diversity_enabled"] is False
    assert zero_info["rollout_diversity_steps_applied"] == 0
    assert zero_info["eef_diversity_after_rollout_rbf_phase"] is None

    with pytest.raises(ValueError, match="nonnegative"):
        stub_steer._eds_rollout_reference(
            **kwargs,
            diversity_scale_override=-1.0,
        )
    with pytest.raises(ValueError, match="nonnegative"):
        stub_steer._eds_rollout_reference(
            **{
                **kwargs,
                "cfg": _adaptive_rbf_test_config(
                    population_size=3,
                    rollout_diversity_iters=0,
                ),
            },
            diversity_scale_override=-1.0,
        )


def test_eds_rollout_diversity_iters_limits_application(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    from core.rdt_policy_steer import _EDSConfig

    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    cond = _rollout_cond(stub_steer)
    calls = []

    def fake_diversity(x_t):
        calls.append(tuple(x_t.shape))
        return torch.zeros_like(x_t)

    monkeypatch.setattr(stub_steer, "_compute_diversity_gradient", fake_diversity)
    cfg = _EDSConfig(
        population_size=3,
        truncated_rollout_mode="rbf_diverse",
        rollout_diversity_iters=1,
    )

    stub_steer._eds_rollout_reference(
        cond=cond,
        action_mask=cond["action_mask"],
        noisy_action=torch.zeros(3, 64, 128),
        keypoints=torch.zeros(1, 3),
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        n_trunc_steps=1,
        cfg=cfg,
        iter_idx=0,
    )
    _population, _costs, info = stub_steer._eds_rollout_reference(
        cond=cond,
        action_mask=cond["action_mask"],
        noisy_action=torch.zeros(3, 64, 128),
        keypoints=torch.zeros(1, 3),
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        n_trunc_steps=1,
        cfg=cfg,
        iter_idx=1,
    )

    assert calls == [(3, 64, 128)]
    assert info["rollout_diversity_enabled"] is False
    assert info["rollout_diversity_steps_applied"] == 0


def test_eds_rollout_rbf_applies_when_renoise_tmax_is_one(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    from core.rdt_policy_steer import _EDSConfig

    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    cond = _rollout_cond(stub_steer)
    calls = []

    def fake_diversity(x_t):
        calls.append(tuple(x_t.shape))
        return torch.zeros_like(x_t)

    monkeypatch.setattr(stub_steer, "_compute_diversity_gradient", fake_diversity)

    _population, _costs, info = stub_steer._eds_rollout_reference(
        cond=cond,
        action_mask=cond["action_mask"],
        noisy_action=torch.zeros(3, 64, 128),
        keypoints=torch.zeros(1, 3),
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        n_trunc_steps=1,
        cfg=_EDSConfig(
            population_size=3,
            truncated_rollout_mode="rbf_diverse",
            rollout_diversity_start_ratio=0.8,
            rollout_diversity_iters="all",
            rollout_diversity_skip_final_steps=0,
        ),
        iter_idx=0,
    )

    assert calls == [(3, 64, 128)]
    assert info["rollout_diversity_steps_applied"] == 1


def test_eds_rollout_rbf_warns_and_fallbacks_to_baseline(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    from core import rdt_policy_steer
    from core.rdt_policy_steer import _EDSConfig

    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    cond = _rollout_cond(stub_steer)
    warnings = []

    monkeypatch.setattr(stub_steer, "_compute_diversity_gradient", lambda _x_t: None)
    monkeypatch.setattr(
        rdt_policy_steer.log,
        "warning",
        lambda message: warnings.append(str(message)),
    )

    population, _costs, info = stub_steer._eds_rollout_reference(
        cond=cond,
        action_mask=cond["action_mask"],
        noisy_action=torch.zeros(3, 64, 128),
        keypoints=torch.zeros(1, 3),
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        n_trunc_steps=1,
        cfg=_EDSConfig(
            population_size=3,
            truncated_rollout_mode="rbf_diverse",
            rollout_diversity_iters="all",
        ),
        iter_idx=0,
    )

    assert tuple(population.shape) == (3, 64, 128)
    assert info["rollout_diversity_fallback_used"] is True
    assert "diversity_gradient_none" in info["rollout_diversity_fallback_reason"]
    assert any("fallback to baseline" in message for message in warnings)


def test_eds_loop_uses_cond_once_and_action_population_batch(
    stub_steer,
    stub_adapter,
    mock_batch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"action_chunk_horizon": 4},
    )

    action = stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="eds",
        eds_config={"population_size": 3, "cem_iters": 1, "temperature": 0.1},
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
    )

    assert tuple(action.shape) == (1, 4, 7)
    assert stub_steer._rdt_model.encode_calls == 1
    assert stub_steer._rdt_model.dit.calls
    assert any(latent_shape[0] == 3 for latent_shape, _ in stub_steer._rdt_model.dit.calls)
    assert all(mask_shape[0] == 1 for _, mask_shape in stub_steer._rdt_model.dit.calls)


def test_eds_loop_calls_rollout_after_renoise_each_iteration(
    stub_steer,
    stub_adapter,
    mock_batch,
    monkeypatch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"action_chunk_horizon": 4},
    )
    calls = []

    def fake_renoise(population, n_trunc_steps):
        calls.append(("renoise", n_trunc_steps, tuple(population.shape)))
        return population

    def fake_rollout(**kwargs):
        calls.append(("rollout", kwargs["n_trunc_steps"], tuple(kwargs["noisy_action"].shape)))
        noisy = kwargs["noisy_action"]
        costs = torch.arange(noisy.shape[0], device=noisy.device, dtype=noisy.dtype)
        return noisy, costs, {"rewards": -costs}

    monkeypatch.setattr(stub_steer, "_eds_renoise_reference", fake_renoise)
    monkeypatch.setattr(stub_steer, "_eds_rollout_reference", fake_rollout)

    stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="eds",
        eds_config={
            "population_size": 3,
            "cem_iters": 2,
            "temperature": 0.1,
            "renoise_t_max": 3,
            "renoise_t_min": 1,
        },
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
    )

    assert calls[0][0] == "renoise"
    assert calls[1][0] == "rollout"
    assert calls[2][0] == "renoise"
    assert calls[3][0] == "rollout"
    assert calls[0][1] == calls[1][1]
    assert calls[2][1] == calls[3][1]
    assert calls[0][1] == 3
    assert calls[2][1] == 1


@pytest.mark.parametrize("bad_score", [float("nan"), float("inf")])
def test_eds_loop_rejects_nonfinite_initial_scores_before_resampling(
    stub_steer,
    stub_adapter,
    mock_batch,
    monkeypatch,
    bad_score,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"action_chunk_horizon": 4},
    )
    resample_calls = []

    def fake_score_population_as_cost(
        samples,
        *,
        keypoints,
        guidance_fns,
        reward_mode="normal",
        shuffle_seed=0,
    ):
        scores = torch.tensor([0.0, bad_score, 1.0], device=samples.device, dtype=samples.dtype)
        return scores, {"rewards": -scores}

    def fail_renoise(population, n_trunc_steps):
        resample_calls.append(tuple(population.shape))
        raise AssertionError("EDS should reject invalid scores before resampling")

    monkeypatch.setattr(stub_steer, "_eds_score_population_as_cost", fake_score_population_as_cost)
    monkeypatch.setattr(stub_steer, "_eds_renoise_reference", fail_renoise)

    with pytest.raises(ValueError, match="EDS population scores.*finite"):
        stub_steer.select_action(
            mock_batch,
            generate_new_chunk=True,
            use_guidance=True,
            guidance_type="eds",
            eds_config={"population_size": 3, "cem_iters": 1, "temperature": 0.1},
            guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
            keypoints=np.zeros((3, 3), dtype=np.float32),
        )

    assert resample_calls == []


def test_eds_sampling_probabilities_from_cost_handles_extreme_finite_costs(stub_steer):
    costs = torch.tensor([1.0e20, -1.0e20, 0.0], dtype=torch.float32)

    probabilities = stub_steer._eds_sampling_probabilities_from_cost(costs, temperature=100.0)

    assert tuple(probabilities.shape) == (3,)
    assert torch.isfinite(probabilities).all()
    assert float(probabilities.sum().item()) > 0.0
    assert int(torch.argmax(probabilities).item()) == 1


def test_adaptive_ess_probabilities_hit_target(stub_steer):
    costs = torch.tensor([-4.0, -2.0, -1.0, 0.0])

    probabilities, info = stub_steer._eds_adaptive_ess_probabilities(
        costs,
        target_ratio=0.5,
        beta_max=100.0,
        bisection_steps=24,
    )

    ess = 1.0 / probabilities.square().sum()
    assert abs(float(ess / costs.numel()) - 0.5) <= 0.03
    assert int(torch.argmax(probabilities).item()) == int(torch.argmin(costs).item())
    assert info["selection_degenerate_reward"] is False
    assert info["selection_ess"] == pytest.approx(float(ess.item()))
    assert info["selection_ess_ratio"] == pytest.approx(float((ess / costs.numel()).item()))


def test_adaptive_ess_equal_costs_return_strict_uniform(stub_steer):
    costs = torch.zeros(16)

    probabilities, info = stub_steer._eds_adaptive_ess_probabilities(
        costs,
        target_ratio=0.5,
        beta_max=100.0,
        bisection_steps=24,
    )

    assert torch.equal(probabilities, torch.full_like(costs, 1.0 / costs.numel()))
    assert info == {
        "selection_beta": 0.0,
        "selection_ess": 16.0,
        "selection_ess_ratio": 1.0,
        "selection_entropy_normalized": 1.0,
        "selection_max_probability": 1.0 / 16.0,
        "selection_degenerate_reward": True,
    }


def test_adaptive_ess_handles_extreme_finite_rewards_without_false_degeneracy(
    stub_steer,
):
    costs = torch.tensor([1.0e308, -1.0e308], dtype=torch.float64)

    probabilities, info = stub_steer._eds_adaptive_ess_probabilities(
        costs,
        target_ratio=0.5,
        beta_max=1.0e308,
        bisection_steps=24,
    )

    assert torch.isfinite(probabilities).all()
    assert int(torch.argmax(probabilities).item()) == int(torch.argmin(costs).item())
    assert info["selection_degenerate_reward"] is False
    assert all(
        math.isfinite(info[key])
        for key in (
            "selection_beta",
            "selection_ess",
            "selection_ess_ratio",
            "selection_entropy_normalized",
            "selection_max_probability",
        )
    )


def test_adaptive_ess_robust_normalize_handles_finite_extreme_outlier(stub_steer):
    rewards = torch.tensor([0.0, 2.0e-8, 4.0e-8, 1.0e308], dtype=torch.float64)

    normalized, degenerate = stub_steer._eds_robust_normalize_rewards(rewards)

    assert torch.isfinite(normalized).all()
    assert degenerate is False
    assert torch.equal(torch.argsort(normalized), torch.argsort(rewards))


def test_adaptive_ess_handles_finite_extreme_outlier(stub_steer):
    rewards = torch.tensor([0.0, 2.0e-8, 4.0e-8, 1.0e308], dtype=torch.float64)
    costs = -rewards

    probabilities, info = stub_steer._eds_adaptive_ess_probabilities(
        costs,
        target_ratio=0.5,
        beta_max=100.0,
        bisection_steps=24,
    )

    ess = 1.0 / probabilities.double().square().sum()
    assert torch.isfinite(probabilities).all()
    assert abs(float(ess / costs.numel()) - 0.5) <= 0.03
    assert int(torch.argmax(probabilities).item()) == int(torch.argmin(costs).item())
    assert info["selection_degenerate_reward"] is False
    assert all(
        math.isfinite(value)
        for key, value in info.items()
        if key != "selection_degenerate_reward"
    )


def test_adaptive_ess_safe_midpoint_with_near_float64_max_beta(
    stub_steer,
    monkeypatch,
):
    normalized_rewards = torch.tensor([0.0, 1.0e-308], dtype=torch.float64)
    monkeypatch.setattr(
        stub_steer,
        "_eds_robust_normalize_rewards",
        lambda rewards: (normalized_rewards.to(device=rewards.device), False),
    )

    probabilities, info = stub_steer._eds_adaptive_ess_probabilities(
        torch.tensor([1.0, 0.0], dtype=torch.float64),
        target_ratio=0.8,
        beta_max=1.7e308,
        bisection_steps=64,
    )

    assert torch.isfinite(probabilities).all()
    assert math.isfinite(info["selection_beta"])
    assert info["selection_beta"] <= 1.7e308
    assert info["selection_ess_ratio"] == pytest.approx(0.8, abs=0.03)
    assert all(
        math.isfinite(value)
        for key, value in info.items()
        if key != "selection_degenerate_reward"
    )


def test_adaptive_ess_target_ratio_one_returns_uniform_without_marking_degenerate(
    stub_steer,
):
    costs = torch.tensor([-4.0, -2.0, -1.0, 0.0])

    probabilities, info = stub_steer._eds_adaptive_ess_probabilities(
        costs,
        target_ratio=1.0,
        beta_max=100.0,
        bisection_steps=24,
    )

    assert torch.equal(probabilities, torch.full_like(costs, 0.25))
    assert info["selection_beta"] == 0.0
    assert info["selection_ess_ratio"] == 1.0
    assert info["selection_degenerate_reward"] is False


@pytest.mark.parametrize(
    ("costs", "overrides", "match"),
    [
        (torch.tensor([[0.0, 1.0]]), {}, "1-D"),
        (torch.tensor([]), {}, "non-empty"),
        (torch.tensor([0.0, float("nan")]), {}, "finite"),
        (torch.tensor([0.0, 1.0]), {"target_ratio": 0.0}, "target_ratio"),
        (torch.tensor([0.0, 1.0]), {"target_ratio": 1.01}, "target_ratio"),
        (torch.tensor([0.0, 1.0]), {"target_ratio": True}, "target_ratio"),
        (torch.tensor([0.0, 1.0]), {"target_ratio": "0.5"}, "target_ratio"),
        (torch.tensor([0.0, 1.0]), {"beta_max": float("inf")}, "beta_max"),
        (torch.tensor([0.0, 1.0]), {"beta_max": True}, "beta_max"),
        (torch.tensor([0.0, 1.0]), {"beta_max": "100.0"}, "beta_max"),
        (torch.tensor([0.0, 1.0]), {"bisection_steps": 0}, "bisection_steps"),
    ],
)
def test_adaptive_ess_probabilities_validate_inputs(
    stub_steer,
    costs,
    overrides,
    match,
):
    kwargs = {
        "target_ratio": 0.5,
        "beta_max": 100.0,
        "bisection_steps": 24,
    }
    kwargs.update(overrides)

    with pytest.raises(ValueError, match=match):
        stub_steer._eds_adaptive_ess_probabilities(costs, **kwargs)


def test_adaptive_ess_uses_beta_max_when_target_is_unreachable(stub_steer):
    costs = torch.tensor([-4.0, -2.0, -1.0, 0.0])

    probabilities, info = stub_steer._eds_adaptive_ess_probabilities(
        costs,
        target_ratio=0.25,
        beta_max=0.01,
        bisection_steps=24,
    )

    actual_ess = float((1.0 / probabilities.double().square().sum()).item())
    assert torch.isfinite(probabilities).all()
    assert info["selection_beta"] == pytest.approx(0.01)
    assert info["selection_ess"] == pytest.approx(actual_ess)
    assert info["selection_ess_ratio"] > 0.25


@pytest.mark.parametrize(
    ("probabilities", "selection_beta", "match"),
    [
        ([0.5, 0.5], 1.0, "torch.Tensor"),
        (torch.ones(2, 1), 1.0, "1-D"),
        (torch.tensor([]), 1.0, "non-empty"),
        (torch.tensor([1.1, -0.1]), 1.0, "non-negative"),
        (torch.tensor([0.5, 0.5]), float("inf"), "selection_beta"),
    ],
)
def test_parent_weight_selection_info_validates_inputs(
    stub_steer,
    probabilities,
    selection_beta,
    match,
):
    with pytest.raises(ValueError, match=match):
        stub_steer._eds_selection_info_from_probabilities(
            probabilities,
            selection_beta=selection_beta,
            degenerate_reward=False,
        )


def test_parent_weight_legacy_dispatch_preserves_probabilities_and_seeded_indices(
    stub_steer,
):
    costs = torch.tensor([-4.0, -2.0, -1.0, 0.0])
    cfg = stub_steer._resolve_eds_config_with_reference_defaults(
        {"parent_weighting_mode": "legacy_temperature", "temperature": 0.37}
    )
    torch.manual_seed(1234)
    legacy_probabilities = stub_steer._eds_sampling_probabilities_from_cost(
        costs,
        cfg.temperature,
    )
    legacy_indices = torch.multinomial(
        legacy_probabilities,
        64,
        replacement=True,
    )
    torch.manual_seed(1234)
    rng_state_before_dispatch = torch.get_rng_state()
    dispatched_probabilities, info = stub_steer._eds_compute_parent_weights(costs, cfg)
    rng_state_after_dispatch = torch.get_rng_state()
    dispatched_indices = torch.multinomial(
        dispatched_probabilities,
        64,
        replacement=True,
    )

    assert torch.equal(dispatched_probabilities, legacy_probabilities)
    assert info["selection_beta"] == cfg.temperature
    assert info["selection_degenerate_reward"] is False
    assert torch.equal(rng_state_after_dispatch, rng_state_before_dispatch)
    assert torch.equal(dispatched_indices, legacy_indices)


def test_parent_weight_legacy_dispatch_handles_finite_extreme_outlier(stub_steer):
    rewards = torch.tensor([0.0, 2.0e-8, 4.0e-8, 1.0e308], dtype=torch.float64)
    costs = -rewards
    cfg = stub_steer._resolve_eds_config_with_reference_defaults(
        {"parent_weighting_mode": "legacy_temperature", "temperature": 0.1}
    )
    legacy_probabilities = stub_steer._eds_sampling_probabilities_from_cost(
        costs,
        cfg.temperature,
    )

    probabilities, info = stub_steer._eds_compute_parent_weights(costs, cfg)

    assert torch.equal(probabilities, legacy_probabilities)
    assert info["selection_degenerate_reward"] is False
    assert all(
        math.isfinite(value)
        for key, value in info.items()
        if key != "selection_degenerate_reward"
    )


def test_parent_weight_legacy_dispatch_marks_equal_costs_degenerate(stub_steer):
    costs = torch.zeros(4)
    cfg = stub_steer._resolve_eds_config_with_reference_defaults(
        {"parent_weighting_mode": "legacy_temperature"}
    )

    probabilities, info = stub_steer._eds_compute_parent_weights(costs, cfg)

    assert torch.equal(probabilities, torch.full_like(costs, 0.25))
    assert info["selection_degenerate_reward"] is True


def test_parent_weight_dispatch_rejects_unknown_mode(stub_steer):
    from core.rdt_policy_steer import _EDSConfig

    cfg = _EDSConfig(parent_weighting_mode="unknown")

    with pytest.raises(ValueError, match="parent_weighting_mode"):
        stub_steer._eds_compute_parent_weights(torch.tensor([0.0, 1.0]), cfg)


def test_eds_eef_kcenter_is_best_first_unique_and_reward_guarded(
    stub_steer,
    monkeypatch,
):
    population = torch.zeros(4, 64, 128)
    rewards = torch.tensor([10.0, 9.0, 8.0, -100.0])
    features = torch.tensor([[0.0], [1.0], [2.0], [100.0]])
    monkeypatch.setattr(
        stub_steer,
        "_eds_population_to_reward_trajectories",
        lambda _population: features,
    )

    indices, info = stub_steer._eds_select_eef_kcenter(
        population,
        rewards,
        count=2,
        reward_quantile=0.5,
    )

    assert indices.tolist() == [0, 1]
    assert len(indices.unique()) == 2
    assert 3 not in indices.tolist()
    assert info == {
        "anchor_requested_count": 2,
        "anchor_selected_count": 2,
        "anchor_shortfall": 0,
        "anchor_eligible_count": 2,
        "anchor_min_pairwise_eef_distance": pytest.approx(1.0),
    }
    json.dumps(info, allow_nan=False)


@pytest.mark.parametrize(
    ("rewards", "expected_second"),
    [
        ([10.0, 8.0, 9.0], 2),
        ([10.0, 9.0, 9.0], 1),
    ],
)
def test_eds_eef_kcenter_distance_ties_prefer_reward_then_original_index(
    stub_steer,
    monkeypatch,
    rewards,
    expected_second,
):
    population = torch.zeros(3, 64, 128)
    features = torch.tensor([[0.0], [2.0], [-2.0]])
    monkeypatch.setattr(
        stub_steer,
        "_eds_population_to_reward_trajectories",
        lambda _population: features,
    )

    indices, _ = stub_steer._eds_select_eef_kcenter(
        population,
        torch.tensor(rewards),
        count=2,
        reward_quantile=0.0,
    )

    assert indices.tolist() == [0, expected_second]


def test_eds_eef_kcenter_reports_shortfall_without_selecting_ineligible_outlier(
    stub_steer,
    monkeypatch,
):
    population = torch.zeros(4, 64, 128)
    rewards = torch.tensor([10.0, 9.0, 8.0, -100.0])
    features = torch.tensor([[0.0], [1.0], [2.0], [100.0]])
    monkeypatch.setattr(
        stub_steer,
        "_eds_population_to_reward_trajectories",
        lambda _population: features,
    )

    indices, info = stub_steer._eds_select_eef_kcenter(
        population,
        rewards,
        count=4,
        reward_quantile=0.5,
    )

    assert indices.tolist() == [0, 1]
    assert info["anchor_requested_count"] == 4
    assert info["anchor_selected_count"] == 2
    assert info["anchor_shortfall"] == 2
    assert info["anchor_eligible_count"] == 2
    assert 3 not in indices.tolist()


@pytest.mark.parametrize(
    ("population", "rewards", "count", "reward_quantile", "match"),
    [
        (torch.zeros(3, 64, 128), torch.zeros(2), 1, 0.5, "same population size"),
        (torch.zeros(3, 64, 128), torch.zeros(3, 1), 1, 0.5, "1-D"),
        (
            torch.zeros(3, 64, 128),
            torch.tensor([0.0, float("nan"), 1.0]),
            1,
            0.5,
            "finite",
        ),
        (torch.zeros(3, 64, 128), torch.zeros(3), -1, 0.5, "count"),
        (torch.zeros(3, 64, 128), torch.zeros(3), 1, 1.1, "reward_quantile"),
    ],
)
def test_eds_eef_kcenter_validates_inputs(
    stub_steer,
    population,
    rewards,
    count,
    reward_quantile,
    match,
):
    with pytest.raises(ValueError, match=match):
        stub_steer._eds_select_eef_kcenter(
            population,
            rewards,
            count=count,
            reward_quantile=reward_quantile,
        )


def test_eds_eef_kcenter_rejects_nonfinite_projection(stub_steer, monkeypatch):
    monkeypatch.setattr(
        stub_steer,
        "_eds_population_to_reward_trajectories",
        lambda _population: torch.tensor([[0.0], [float("inf")]]),
    )

    with pytest.raises(ValueError, match="projection.*finite"):
        stub_steer._eds_select_eef_kcenter(
            torch.zeros(2, 64, 128),
            torch.tensor([1.0, 0.0]),
            count=1,
            reward_quantile=0.0,
        )


@pytest.mark.parametrize("nonfinite", [float("nan"), float("inf"), -float("inf")])
def test_eds_eef_kcenter_rejects_nonfinite_population_before_projection(
    stub_steer,
    monkeypatch,
    nonfinite,
):
    population = torch.zeros(2, 64, 128)
    population[0, 0, 0] = nonfinite
    projection_calls = []

    def finite_projection(_population):
        projection_calls.append(True)
        return torch.zeros(2, 1)

    monkeypatch.setattr(
        stub_steer,
        "_eds_population_to_reward_trajectories",
        finite_projection,
    )

    with pytest.raises(ValueError, match="population.*finite"):
        stub_steer._eds_select_eef_kcenter(
            population,
            torch.tensor([1.0, 0.0]),
            count=1,
            reward_quantile=0.0,
        )
    assert projection_calls == []


def test_eds_eef_kcenter_rejects_nonfinite_cdist_from_extreme_finite_projection(
    stub_steer,
    monkeypatch,
):
    extreme = torch.finfo(torch.float32).max
    monkeypatch.setattr(
        stub_steer,
        "_eds_population_to_reward_trajectories",
        lambda _population: torch.tensor([[extreme], [-extreme]]),
    )

    with pytest.raises(ValueError, match="pairwise EEF distance matrix.*finite"):
        stub_steer._eds_select_eef_kcenter(
            torch.zeros(2, 64, 128),
            torch.tensor([2.0, 1.0]),
            count=2,
            reward_quantile=0.0,
        )


def test_eds_eef_kcenter_rejects_nonfinite_selected_pdist(
    stub_steer,
    monkeypatch,
):
    extreme = torch.finfo(torch.float32).max
    monkeypatch.setattr(
        stub_steer,
        "_eds_population_to_reward_trajectories",
        lambda _population: torch.tensor([[extreme], [-extreme]]),
    )
    monkeypatch.setattr(
        torch,
        "cdist",
        lambda left, right: torch.zeros(
            left.shape[0],
            right.shape[0],
            device=left.device,
            dtype=left.dtype,
        ),
    )

    with pytest.raises(ValueError, match="selected pairwise EEF distances.*finite"):
        stub_steer._eds_select_eef_kcenter(
            torch.zeros(2, 64, 128),
            torch.tensor([2.0, 1.0]),
            count=2,
            reward_quantile=0.0,
        )


def test_eds_eef_kcenter_info_is_strict_json_safe(stub_steer, monkeypatch):
    monkeypatch.setattr(
        stub_steer,
        "_eds_population_to_reward_trajectories",
        lambda _population: torch.tensor([[0.0], [3.0], [7.0]]),
    )

    _, info = stub_steer._eds_select_eef_kcenter(
        torch.zeros(3, 64, 128),
        torch.tensor([3.0, 2.0, 1.0]),
        count=3,
        reward_quantile=0.0,
    )

    encoded = json.dumps(info, allow_nan=False)
    assert json.loads(encoded) == info


def test_eds_eef_kcenter_count_zero_returns_before_projection(stub_steer, monkeypatch):
    projection_calls = []
    monkeypatch.setattr(
        stub_steer,
        "_eds_population_to_reward_trajectories",
        lambda _population: projection_calls.append(True),
    )

    indices, info = stub_steer._eds_select_eef_kcenter(
        torch.zeros(3, 64, 128),
        torch.tensor([3.0, 2.0, 1.0]),
        count=0,
        reward_quantile=0.5,
    )

    assert indices.shape == (0,)
    assert projection_calls == []
    assert info == {
        "anchor_requested_count": 0,
        "anchor_selected_count": 0,
        "anchor_shortfall": 0,
        "anchor_eligible_count": 0,
        "anchor_min_pairwise_eef_distance": None,
    }
    json.dumps(info, allow_nan=False)


def test_eds_eef_kcenter_single_population_is_well_defined(stub_steer, monkeypatch):
    monkeypatch.setattr(
        stub_steer,
        "_eds_population_to_reward_trajectories",
        lambda _population: torch.tensor([[7.0]]),
    )

    indices, info = stub_steer._eds_select_eef_kcenter(
        torch.zeros(1, 64, 128),
        torch.tensor([5.0]),
        count=1,
        reward_quantile=1.0,
    )

    assert indices.tolist() == [0]
    assert info["anchor_eligible_count"] == 1
    assert info["anchor_min_pairwise_eef_distance"] is None
    json.dumps(info, allow_nan=False)


def test_eds_eef_kcenter_cdist_excludes_ineligible_extreme_projection(
    stub_steer,
    monkeypatch,
):
    extreme = torch.finfo(torch.float32).max
    monkeypatch.setattr(
        stub_steer,
        "_eds_population_to_reward_trajectories",
        lambda _population: torch.tensor([[0.0], [1.0], [extreme]]),
    )

    indices, info = stub_steer._eds_select_eef_kcenter(
        torch.zeros(3, 64, 128),
        torch.tensor([10.0, 9.0, -100.0]),
        count=2,
        reward_quantile=0.5,
    )

    assert indices.tolist() == [0, 1]
    assert info["anchor_eligible_count"] == 2
    assert info["anchor_min_pairwise_eef_distance"] == pytest.approx(1.0)
    json.dumps(info, allow_nan=False)


def test_eds_parent_plan_carries_elites_and_places_unique_anchors_first(
    stub_steer,
    monkeypatch,
):
    population = torch.zeros(16, 64, 128)
    costs = torch.arange(16, dtype=torch.float32)
    costs[0] = -10.0
    costs[15] = -9.0
    features = torch.arange(16, dtype=torch.float32).reshape(16, 1)
    monkeypatch.setattr(
        stub_steer,
        "_eds_population_to_reward_trajectories",
        lambda candidates: features.index_select(
            0,
            candidates[:, 0, 0].to(dtype=torch.long),
        ),
    )
    population[:, 0, 0] = torch.arange(16, dtype=population.dtype)
    cfg = stub_steer._resolve_eds_config_with_reference_defaults(
        {
            "population_size": 16,
            "elite_carryover_count": 2,
            "parent_coverage_mode": "eef_kcenter",
            "parent_anchor_count": 4,
            "parent_anchor_reward_quantile": 0.0,
        }
    )

    torch.manual_seed(17)
    plan = stub_steer._eds_select_parent_plan(population, costs, cfg)

    assert plan.elite_indices.shape == (2,)
    assert plan.elite_indices.tolist() == [0, 15]
    assert plan.offspring_parent_indices.shape == (14,)
    assert plan.offspring_sources[:4] == ("anchor_offspring",) * 4
    assert plan.offspring_sources[4:] == ("weighted_offspring",) * 10
    anchors = plan.offspring_parent_indices[:4]
    assert anchors.unique().numel() == 4
    assert set(anchors.tolist()).isdisjoint(plan.elite_indices.tolist())
    assert plan.info["elite_count"] == 2
    assert plan.info["anchor_count"] == 4
    assert plan.info["parent_count_by_source"] == {
        "elite": 2,
        "anchor_offspring": 4,
        "weighted_offspring": 10,
    }
    full_parent_indices = torch.cat(
        [plan.elite_indices, plan.offspring_parent_indices]
    )
    assert plan.info["parent_mode_coverage"] == pytest.approx(
        full_parent_indices.unique().numel() / 16.0
    )
    json.dumps(plan.info, allow_nan=False)


def test_eds_legacy_parent_plan_preserves_dispatch_indices_and_rng_order(
    stub_steer,
    monkeypatch,
):
    population = torch.zeros(4, 64, 128)
    costs = torch.tensor([-4.0, -2.0, -1.0, 0.0])
    cfg = stub_steer._resolve_eds_config_with_reference_defaults(
        {
            "population_size": 4,
            "parent_weighting_mode": "legacy_temperature",
            "temperature": 0.37,
            "parent_coverage_mode": "none",
            "elite_carryover_count": 0,
        }
    )
    old_probabilities, old_info = stub_steer._eds_compute_parent_weights(costs, cfg)
    torch.manual_seed(1234)
    old_indices = torch.multinomial(old_probabilities, 4, replacement=True)
    old_rng_state = torch.get_rng_state()

    captured = {}
    original_compute = stub_steer._eds_compute_parent_weights

    def spy_compute(current_costs, current_cfg):
        probabilities, info = original_compute(current_costs, current_cfg)
        captured["probabilities"] = probabilities
        return probabilities, info

    monkeypatch.setattr(stub_steer, "_eds_compute_parent_weights", spy_compute)
    torch.manual_seed(1234)
    plan = stub_steer._eds_select_parent_plan(population, costs, cfg)
    plan_rng_state = torch.get_rng_state()

    assert torch.equal(captured["probabilities"], old_probabilities)
    assert torch.equal(plan.offspring_parent_indices, old_indices)
    assert torch.equal(plan_rng_state, old_rng_state)
    assert plan.elite_indices.numel() == 0
    assert plan.offspring_sources == ("weighted_offspring",) * 4
    for key, value in old_info.items():
        assert plan.info[key] == value


def test_eds_parent_plan_exposes_actual_probability_and_deterministic_kind(
    stub_steer,
    monkeypatch,
):
    population = torch.zeros(4, 64, 128)
    population[:, 0, 0] = torch.arange(4, dtype=population.dtype)
    costs = torch.tensor([-4.0, -3.0, -2.0, -1.0])
    probabilities = torch.tensor([0.5, 0.3, 0.15, 0.05])
    cfg = stub_steer._resolve_eds_config_with_reference_defaults(
        {
            "population_size": 4,
            "parent_weighting_mode": "adaptive_ess",
            "parent_coverage_mode": "eef_kcenter",
            "parent_anchor_count": 1,
            "parent_anchor_reward_quantile": 0.0,
            "elite_carryover_count": 1,
        }
    )
    monkeypatch.setattr(
        stub_steer,
        "_eds_select_eef_kcenter",
        lambda *args, **kwargs: (
            torch.tensor([0]),
            {
                "anchor_requested_count": 1,
                "anchor_selected_count": 1,
                "anchor_shortfall": 0,
                "anchor_eligible_count": 3,
                "anchor_min_pairwise_eef_distance": None,
            },
        ),
    )
    monkeypatch.setattr(
        stub_steer,
        "_eds_compute_parent_weights",
        lambda *args: (
            probabilities,
            {
                "selection_beta": 2.0,
                "selection_ess": 2.0,
                "selection_ess_ratio": 0.5,
                "selection_entropy_normalized": 0.75,
                "selection_max_probability": 0.5,
                "selection_degenerate_reward": False,
            },
        ),
    )

    torch.manual_seed(7)
    plan = stub_steer._eds_select_parent_plan(population, costs, cfg)

    full_indices = torch.cat([plan.elite_indices, plan.offspring_parent_indices])
    assert plan.info["parent_selection_kinds"] == [
        "deterministic_elite",
        "deterministic_anchor",
        "adaptive_ess",
        "adaptive_ess",
    ]
    assert plan.info["parent_probabilities"][:2] == [None, None]
    assert plan.info["parent_probabilities"][2:] == pytest.approx(
        [probabilities[idx].item() for idx in full_indices[2:]]
    )


def test_eds_make_trace_stage_preserves_parent_probability_metadata(stub_steer):
    population = torch.zeros(2, 64, 128)
    stage = stub_steer._eds_make_trace_stage(
        stage="resampled",
        iter_idx=0,
        population=population,
        costs=torch.tensor([-1.0, -0.5]),
        info={"rewards": torch.tensor([1.0, 0.5])},
        parent_indices=torch.tensor([0, 1]),
        parent_ranks=torch.tensor([1, 2]),
        particle_sources=["elite", "weighted_offspring"],
        parent_probabilities=[None, 0.25],
        parent_selection_kinds=["deterministic_elite", "adaptive_ess"],
    )

    assert stage.parent_probabilities == [None, 0.25]
    assert stage.parent_selection_kinds == ["deterministic_elite", "adaptive_ess"]


def test_eds_chunk_memory_trace_reuses_composer_scores_and_retains_cpu_evidence(
    stub_steer,
    monkeypatch,
):
    from core.rdt_policy_steer import EDSChunkMemory

    cond = _rollout_cond(stub_steer)
    cfg = _eds_chunk_memory_config(
        population_size=4,
        num_elites=4,
        chunk_memory_fraction=0.5,
    )
    fresh = torch.zeros(4, 64, 128)
    fresh[:, :, 39] = 10.0 + torch.arange(4, dtype=fresh.dtype)[:, None]
    memory = torch.zeros_like(fresh)
    memory[:, :, 39] = torch.arange(4, dtype=memory.dtype)[:, None]
    stub_steer._eds_chunk_memory = EDSChunkMemory(
        population=memory,
        costs=torch.arange(4, dtype=torch.float32),
        stage=1,
        global_step=0,
    )
    monkeypatch.setattr(
        stub_steer,
        "_eds_select_eef_kcenter",
        lambda population, rewards, count, reward_quantile: (torch.arange(count), {}),
    )
    monkeypatch.setattr(stub_steer, "_eds_renoise_reference", lambda samples, steps: samples)
    monkeypatch.setattr(
        stub_steer,
        "_eds_denoise_noisy_population",
        lambda **kwargs: kwargs["noisy_action"],
    )
    score_calls = []

    def score(samples, **kwargs):
        score_calls.append(int(samples.shape[0]))
        costs = samples[:, 0, 39].clone()
        return costs, {"rewards": -costs}

    monkeypatch.setattr(stub_steer, "_eds_score_population_as_cost", score)

    _, _, _, telemetry = stub_steer._eds_compose_initial_population_from_memory(
        fresh_population=fresh,
        cond=cond,
        cfg=cfg,
        keypoints=None,
        guidance_fns=None,
        global_step=4,
        current_stage=1,
        trace_enabled=True,
    )

    assert score_calls == [4, 2]
    assert telemetry["_trace_fresh_population"].device.type == "cpu"
    assert telemetry["_trace_adapted_memory"].device.type == "cpu"
    assert telemetry["_trace_composed_population"].device.type == "cpu"
    assert telemetry["_trace_accepted_positions"] == [0, 1]
    for key in (
        "_trace_fresh_population",
        "_trace_adapted_memory",
        "_trace_composed_population",
    ):
        assert telemetry[key].requires_grad is False


def test_eds_parent_plan_warns_on_anchor_shortfall_and_returns_slots_to_weighted(
    stub_steer,
    monkeypatch,
):
    population = torch.zeros(6, 64, 128)
    population[:, 0, 0] = torch.arange(6, dtype=population.dtype)
    costs = torch.arange(6, dtype=torch.float32)
    features = torch.arange(6, dtype=torch.float32).reshape(6, 1)
    monkeypatch.setattr(
        stub_steer,
        "_eds_population_to_reward_trajectories",
        lambda candidates: features.index_select(
            0,
            candidates[:, 0, 0].to(dtype=torch.long),
        ),
    )
    warnings = []
    monkeypatch.setattr(
        "core.rdt_policy_steer.log.warning",
        lambda message, *args, **kwargs: warnings.append(str(message)),
    )
    cfg = stub_steer._resolve_eds_config_with_reference_defaults(
        {
            "population_size": 6,
            "elite_carryover_count": 1,
            "parent_coverage_mode": "eef_kcenter",
            "parent_anchor_count": 4,
            "parent_anchor_reward_quantile": 1.0,
        }
    )

    torch.manual_seed(5)
    plan = stub_steer._eds_select_parent_plan(population, costs, cfg)

    assert plan.elite_indices.tolist() == [0]
    assert plan.offspring_parent_indices.shape == (5,)
    assert plan.offspring_sources == (
        "anchor_offspring",
        "weighted_offspring",
        "weighted_offspring",
        "weighted_offspring",
        "weighted_offspring",
    )
    assert warnings and "shortfall" in warnings[0].lower()
    assert plan.info["anchor_requested_count"] == 4
    assert plan.info["anchor_count"] == 1
    assert plan.info["anchor_shortfall"] == 3
    assert plan.info["anchor_fallback_reason"] == "eligible_parent_shortfall"
    assert plan.info["parent_count_by_source"]["weighted_offspring"] == 4


def test_eds_legacy_cem_parent_plan_preserves_top_elite_randint_rng_semantics(
    stub_steer,
):
    population = torch.zeros(6, 64, 128)
    costs = torch.tensor([3.0, 0.0, 4.0, 1.0, 5.0, 2.0])
    cfg = stub_steer._resolve_eds_config_with_reference_defaults(
        {
            "population_size": 6,
            "use_cem": True,
            "num_elites": 3,
            "elite_carryover_count": 0,
            "parent_coverage_mode": "none",
        }
    )
    torch.manual_seed(91)
    elites = torch.argsort(costs)[: cfg.num_elites]
    old_indices = elites[
        torch.randint(0, cfg.num_elites, (cfg.population_size,), device=population.device)
    ]
    old_rng_state = torch.get_rng_state()

    torch.manual_seed(91)
    plan = stub_steer._eds_select_parent_plan(population, costs, cfg)
    plan_rng_state = torch.get_rng_state()

    assert torch.equal(plan.offspring_parent_indices, old_indices)
    assert torch.equal(plan_rng_state, old_rng_state)
    assert plan.offspring_sources == ("weighted_offspring",) * cfg.population_size
    assert plan.info["selection_beta"] is None
    assert plan.info["selection_ess"] is None


def test_eds_elite_loop_bypasses_mutation_scores_full_population_and_wires_metrics(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 4},
    )
    cond = _rollout_cond(stub_steer)
    initial_population = torch.zeros(4, 64, 128)
    initial_population[:, :, 39] = torch.arange(4, dtype=torch.float32)[:, None]
    score_batch_sizes = []
    rollout_batch_sizes = []
    reset_calls = []
    final_populations = []

    monkeypatch.setattr(
        stub_steer,
        "_eds_initial_population",
        lambda **kwargs: initial_population.clone(),
    )

    def fake_score(samples, **kwargs):
        score_batch_sizes.append(int(samples.shape[0]))
        costs = samples[:, 0, 39].detach().clone()
        return costs, {"rewards": -costs, "score_population_size": int(samples.shape[0])}

    def fake_renoise(offspring, n_trunc_steps):
        assert offspring.shape == (2, 64, 128)
        mutated = offspring.clone()
        mutated[:, :, 39] += 100.0
        mutated[:, :, 0] = 999.0
        return mutated

    def fake_rollout(**kwargs):
        offspring = kwargs["noisy_action"]
        rollout_batch_sizes.append(int(offspring.shape[0]))
        assert offspring.shape == (2, 64, 128)
        rolled = offspring.clone()
        rolled[:, :, 39] += 10.0
        costs, info = stub_steer._eds_score_population_as_cost(
            rolled,
            keypoints=kwargs["keypoints"],
            guidance_fns=kwargs["guidance_fns"],
            reward_mode=kwargs["reward_mode"],
            shuffle_seed=kwargs["shuffle_seed"],
        )
        info["rollout_diversity_mode"] = "baseline"
        return rolled, costs, info

    def capture_ordered(samples, costs):
        final_populations.append(samples.detach().clone())
        return samples.detach()

    monkeypatch.setattr(stub_steer, "_eds_score_population_as_cost", fake_score)
    monkeypatch.setattr(stub_steer, "_eds_renoise_reference", fake_renoise)
    monkeypatch.setattr(stub_steer, "_eds_rollout_reference", fake_rollout)
    monkeypatch.setattr(
        stub_steer,
        "_eds_adaptive_rollout_diversity_decision",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("fixed control mode must not call adaptive controller")
        ),
    )
    monkeypatch.setattr(
        stub_steer,
        "_reset_scheduler_particle_history_after_resample",
        lambda scheduler: reset_calls.append(scheduler),
    )
    monkeypatch.setattr(stub_steer, "_eds_order_candidates_by_cost", capture_ordered)
    cfg = stub_steer._resolve_eds_config_with_reference_defaults(
        {
            "population_size": 4,
            "cem_iters": 1,
            "elite_carryover_count": 2,
            "parent_coverage_mode": "eef_kcenter",
            "parent_anchor_count": 1,
            "parent_anchor_reward_quantile": 0.0,
        }
    )

    torch.manual_seed(7)
    selected = stub_steer._eds_guided_denoise_loop(
        x_t=torch.zeros_like(initial_population),
        cond=cond,
        keypoints=None,
        guidance_fns=None,
        eds_config=cfg,
        verbose=False,
        global_step=0,
        current_stage=0,
    )

    final_population = final_populations[-1]
    assert final_population.shape == (4, 64, 128)
    torch.testing.assert_close(final_population[:2], initial_population[:2])
    assert torch.all(final_population[2:, :, 39] >= 110.0)
    assert torch.count_nonzero(final_population[:, :, 0]) == 0
    assert torch.isfinite(final_population).all()
    torch.testing.assert_close(selected, initial_population[0:1])
    assert rollout_batch_sizes == [2]
    assert len(reset_calls) == 1
    assert score_batch_sizes == [4, 2, 4]

    metrics = stub_steer.get_last_eds_metrics()
    assert metrics["score_call_count"] == 3
    assert metrics["elite_carryover_count_observed"] == 2
    assert metrics["anchor_count_observed"] == 1
    assert metrics["anchor_unique_ratio"] == 1.0
    assert metrics["offspring_unique_parent_ratio"] is not None
    assert metrics["parent_count_by_source"] == {
        "elite": 2,
        "anchor_offspring": 1,
        "weighted_offspring": 1,
    }
    assert metrics["elite_survival_to_final_count"] == 2
    assert metrics["selected_parent_source"] == "elite"
    assert metrics["per_iter"][0]["elite_count"] == 2
    assert metrics["per_iter"][0]["anchor_count"] == 1
    assert metrics["adaptive_rbf_reference"] is None
    assert metrics["adaptive_rbf_active_iter_count"] == 0
    assert metrics["adaptive_rbf_particle_count"] == 0
    assert metrics["per_iter"][0]["diversity_reference"] is None
    assert metrics["per_iter"][0]["adaptive_rbf_scale_applied"] is None


def test_adaptive_rbf_loop_uses_full_parent_rewards_and_offspring_telemetry(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    from core.rdt_policy_steer import EDSParentPlan, EDSRolloutDiversityDecision

    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 4},
    )
    cond = _rollout_cond(stub_steer)
    initial_population = torch.zeros(4, 64, 128)
    initial_population[:, :, 39] = torch.arange(4, dtype=torch.float32)[:, None]
    score_calls = []
    controller_rewards = []
    diversity_batch_sizes = []
    rollout_batch_sizes = []
    rollout_overrides = []
    plan = EDSParentPlan(
        elite_indices=torch.tensor([0]),
        offspring_parent_indices=torch.tensor([1, 1, 1]),
        offspring_sources=("weighted_offspring",) * 3,
        info={
            "selection_beta": 0.0,
            "selection_ess": 4.0,
            "selection_ess_ratio": 1.0,
            "selection_entropy_normalized": 1.0,
            "selection_max_probability": 0.25,
            "selection_degenerate_reward": False,
            "elite_count": 1,
            "anchor_requested_count": 0,
            "anchor_count": 0,
            "anchor_shortfall": 0,
            "anchor_eligible_count": 3,
            "anchor_unique_ratio": None,
            "anchor_min_pairwise_eef_distance": None,
            "anchor_fallback_reason": None,
            "offspring_unique_parent_ratio": 1.0 / 3.0,
            "parent_mode_coverage": 0.5,
            "parent_count_by_source": {
                "elite": 1,
                "anchor_offspring": 0,
                "weighted_offspring": 3,
            },
        },
    )

    def fake_score(samples, **kwargs):
        score_calls.append(int(samples.shape[0]))
        costs = samples[:, 0, 39].detach().clone()
        return costs, {"rewards": -costs}

    def fake_controller(*, reference, current, rewards, iter_idx, cfg):
        controller_rewards.append(rewards.detach().clone())
        scale = 2.0 if iter_idx == 0 else 0.0
        reason = "below_band" if iter_idx == 0 else "in_band"
        decision = EDSRolloutDiversityDecision(
            scale=scale,
            enabled=scale > 0.0,
            reason=reason,
            reference=float(reference),
            low=0.8 * float(reference),
            high=1.2 * float(reference),
            current=float(current),
            reward_confidence=0.25,
        )
        return decision, {
            "diversity_reference": decision.reference,
            "diversity_band_low": decision.low,
            "diversity_band_high": decision.high,
            "diversity_current": decision.current,
            "adaptive_rbf_reward_confidence": decision.reward_confidence,
            "adaptive_rbf_scale_requested": decision.scale,
            "adaptive_rbf_scale_applied": decision.scale,
            "adaptive_rbf_active_particle_count": 0,
            "adaptive_rbf_band_hit": reason == "in_band",
            "adaptive_rbf_fallback_used": False,
            "adaptive_rbf_fallback_reason": None,
            "adaptive_rbf_trigger_reason": reason,
            "resolved_rollout_diversity_scale": decision.scale,
        }

    def fake_rollout(**kwargs):
        scale = kwargs["diversity_scale_override"]
        rollout_overrides.append(scale)
        offspring = kwargs["noisy_action"]
        rollout_batch_sizes.append(int(offspring.shape[0]))
        costs = offspring[:, 0, 39].detach().clone()
        steps = 1 if scale > 0.0 else 0
        return offspring, costs, {
            "rewards": -costs,
            "rollout_diversity_mode": "rbf_diverse",
            "rollout_diversity_enabled": steps > 0,
            "rollout_diversity_scale": scale,
            "rollout_diversity_steps_applied": steps,
            "rollout_diversity_iters_applied": steps,
            "rollout_diversity_grad_norms": [],
            "rollout_diversity_fallback_used": False,
            "rollout_diversity_fallback_reason": None,
        }

    monkeypatch.setattr(
        stub_steer,
        "_eds_initial_population",
        lambda **kwargs: initial_population.clone(),
    )
    original_eef_diversity = stub_steer._eds_eef_trajectory_diversity

    def tracked_eef_diversity(population):
        diversity_batch_sizes.append(int(population.shape[0]))
        return original_eef_diversity(population)

    monkeypatch.setattr(
        stub_steer,
        "_eds_eef_trajectory_diversity",
        tracked_eef_diversity,
    )
    monkeypatch.setattr(stub_steer, "_eds_score_population_as_cost", fake_score)
    monkeypatch.setattr(stub_steer, "_eds_select_parent_plan", lambda *args: plan)
    monkeypatch.setattr(
        stub_steer,
        "_eds_renoise_reference",
        lambda offspring, n_trunc_steps: offspring,
    )
    monkeypatch.setattr(
        stub_steer,
        "_eds_adaptive_rollout_diversity_decision",
        fake_controller,
    )
    monkeypatch.setattr(stub_steer, "_eds_rollout_reference", fake_rollout)
    cfg = _adaptive_rbf_test_config(
        cem_iters=2,
        elite_carryover_count=1,
    )

    stub_steer._eds_guided_denoise_loop(
        x_t=torch.zeros_like(initial_population),
        cond=cond,
        keypoints=None,
        guidance_fns=None,
        eds_config=cfg,
        verbose=False,
        global_step=0,
        current_stage=0,
    )

    metrics = stub_steer.get_last_eds_metrics()
    torch.testing.assert_close(
        controller_rewards[0],
        torch.tensor([-0.0, -1.0, -2.0, -3.0]),
    )
    assert rollout_batch_sizes == [3, 3]
    assert diversity_batch_sizes == [4, 3, 3]
    assert rollout_overrides == [2.0, 0.0]
    assert score_calls == [4, 4, 4]
    assert metrics["rollout_diversity_control_mode"] == "adaptive_band"
    assert metrics["adaptive_rbf_active_iter_count"] == 1
    assert metrics["adaptive_rbf_active_iter_ratio"] == pytest.approx(0.5)
    assert metrics["adaptive_rbf_band_hit_ratio"] == pytest.approx(0.5)
    assert metrics["adaptive_rbf_scale_requested_mean"] == pytest.approx(1.0)
    assert metrics["adaptive_rbf_scale_applied_mean"] == pytest.approx(1.0)
    assert metrics["adaptive_rbf_particle_count"] == 3
    assert metrics["adaptive_rbf_fallback_used"] is False
    assert metrics["per_iter"][0]["adaptive_rbf_active_particle_count"] == 3
    assert metrics["per_iter"][1]["adaptive_rbf_active_particle_count"] == 0
    assert metrics["per_iter"][1]["adaptive_rbf_band_hit"] is True


def test_adaptive_rbf_mechanism_trace_records_controller_decision(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    from core.rdt_policy_steer import EDSRolloutDiversityDecision

    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    initial = torch.zeros(3, 64, 128)
    initial[:, :, 39] = torch.arange(3, dtype=torch.float32)[:, None]
    plan = _adaptive_schedule_parent_plan([0, 1, 2])
    monkeypatch.setattr(stub_steer, "_eds_initial_population", lambda **kwargs: initial.clone())
    monkeypatch.setattr(stub_steer, "_eds_select_parent_plan", lambda *args: plan)
    monkeypatch.setattr(stub_steer, "_eds_renoise_reference", lambda samples, steps: samples)
    monkeypatch.setattr(stub_steer, "_eds_eef_trajectory_diversity", lambda population: 0.5)

    def score(samples, **kwargs):
        rewards = -samples[:, 0, 39].clone()
        return -rewards, {"rewards": rewards}

    monkeypatch.setattr(stub_steer, "_eds_score_population_as_cost", score)
    decision = EDSRolloutDiversityDecision(
        scale=7.0,
        enabled=True,
        reason="below_band",
        reference=0.5,
        low=0.4,
        high=0.6,
        current=0.2,
        reward_confidence=0.75,
    )
    monkeypatch.setattr(
        stub_steer,
        "_eds_adaptive_rollout_diversity_decision",
        lambda **kwargs: (
            decision,
            {
                "diversity_reference": 0.5,
                "diversity_band_low": 0.4,
                "diversity_band_high": 0.6,
                "diversity_current": 0.2,
                "adaptive_rbf_reward_confidence": 0.75,
                "adaptive_rbf_scale_requested": 7.0,
                "adaptive_rbf_band_hit": False,
                "adaptive_rbf_fallback_used": False,
                "adaptive_rbf_fallback_reason": None,
                "adaptive_rbf_trigger_reason": "below_band",
                "resolved_rollout_diversity_scale": 7.0,
            },
        ),
    )

    def rollout(**kwargs):
        population = kwargs["noisy_action"]
        rewards = -population[:, 0, 39].clone()
        return population, -rewards, {
            "rewards": rewards,
            "rollout_diversity_steps_applied": 1,
            "rollout_diversity_fallback_used": False,
            "rollout_diversity_fallback_reason": None,
        }

    monkeypatch.setattr(stub_steer, "_eds_rollout_reference", rollout)
    cfg = _adaptive_rbf_test_config(
        population_size=3,
        cem_iters=1,
        mechanism_pretest={
            "enabled": True,
            "first_chunk_only": True,
            "save_single_step": True,
            "save_full_process": True,
            "max_full_process_iters": 1,
        },
    )

    stub_steer._eds_guided_denoise_loop(
        x_t=torch.zeros_like(initial),
        cond=_rollout_cond(stub_steer),
        keypoints=None,
        guidance_fns=None,
        eds_config=cfg,
        verbose=False,
        global_step=0,
        current_stage=0,
    )

    trace = stub_steer.get_last_eds_mechanism_trace()
    item = trace.adaptive_rollout_info["per_iter"][0]
    assert trace.adaptive_rollout_info["enabled"] is True
    assert item == {
        "iter_idx": 0,
        "diversity_reference": 0.5,
        "diversity_current": 0.2,
        "diversity_band_low": 0.4,
        "diversity_band_high": 0.6,
        "reward_confidence": 0.75,
        "scale_requested": 7.0,
        "scale_applied": 7.0,
        "active_particle_count": 3,
        "reason": "below_band",
        "fallback_used": False,
        "fallback_reason": None,
    }


def test_baseline_rollout_with_adaptive_control_does_not_enable_adaptive_rbf_trace(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    initial = torch.zeros(3, 64, 128)
    initial[:, :, 39] = torch.arange(3, dtype=torch.float32)[:, None]
    plan = _adaptive_schedule_parent_plan([0, 1, 2])
    monkeypatch.setattr(stub_steer, "_eds_initial_population", lambda **kwargs: initial.clone())
    monkeypatch.setattr(stub_steer, "_eds_select_parent_plan", lambda *args: plan)
    monkeypatch.setattr(stub_steer, "_eds_renoise_reference", lambda samples, steps: samples)
    monkeypatch.setattr(
        stub_steer,
        "_eds_adaptive_rollout_diversity_decision",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("baseline rollout must not invoke adaptive RBF controller")
        ),
    )

    def score(samples, **kwargs):
        rewards = -samples[:, 0, 39].clone()
        return -rewards, {"rewards": rewards}

    def rollout(**kwargs):
        population = kwargs["noisy_action"]
        rewards = -population[:, 0, 39].clone()
        return population, -rewards, {"rewards": rewards}

    monkeypatch.setattr(stub_steer, "_eds_score_population_as_cost", score)
    monkeypatch.setattr(stub_steer, "_eds_rollout_reference", rollout)
    cfg = _adaptive_rbf_test_config(
        population_size=3,
        cem_iters=1,
        truncated_rollout_mode="baseline",
        rollout_diversity_control_mode="adaptive_band",
        mechanism_pretest={
            "enabled": True,
            "first_chunk_only": True,
            "save_single_step": True,
            "save_full_process": True,
            "max_full_process_iters": 1,
        },
    )

    stub_steer._eds_guided_denoise_loop(
        x_t=torch.zeros_like(initial),
        cond=_rollout_cond(stub_steer),
        keypoints=None,
        guidance_fns=None,
        eds_config=cfg,
        verbose=False,
        global_step=0,
        current_stage=0,
    )

    metrics = stub_steer.get_last_eds_metrics()
    trace = stub_steer.get_last_eds_mechanism_trace()
    assert metrics["adaptive_rbf_enabled"] is False
    assert metrics["per_iter"][0]["adaptive_rbf_enabled"] is False
    assert trace.adaptive_rollout_info == {}


@pytest.mark.parametrize(
    ("second_parent_indices", "expected_survival", "expected_ratio"),
    [
        ([1, 2, 1, 2], 2, 1.0),
        ([1, 1, 1, 1], 1, 0.5),
    ],
    ids=["both_anchor_lineages_survive", "anchor_lineages_collapse"],
)
def test_eds_tracks_unique_first_iteration_anchor_lineages_across_iterations(
    stub_steer,
    stub_adapter,
    monkeypatch,
    second_parent_indices,
    expected_survival,
    expected_ratio,
):
    from core.rdt_policy_steer import EDSParentPlan

    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 4},
    )
    initial = torch.zeros(4, 64, 128)
    initial[:, :, 39] = torch.arange(4, dtype=torch.float32)[:, None]

    def info(anchor_count, source_counts):
        return {
            "selection_beta": 0.0,
            "selection_ess": 4.0,
            "selection_ess_ratio": 1.0,
            "selection_entropy_normalized": 1.0,
            "selection_max_probability": 0.25,
            "selection_degenerate_reward": False,
            "elite_count": 1,
            "anchor_requested_count": anchor_count,
            "anchor_count": anchor_count,
            "anchor_shortfall": 0,
            "anchor_eligible_count": 3,
            "anchor_unique_ratio": 1.0 if anchor_count else None,
            "anchor_min_pairwise_eef_distance": 0.2 if anchor_count else None,
            "anchor_fallback_reason": None,
            "offspring_unique_parent_ratio": 1.0,
            "parent_mode_coverage": 1.0,
            "parent_count_by_source": source_counts,
        }

    first_plan = EDSParentPlan(
        elite_indices=torch.tensor([0]),
        offspring_parent_indices=torch.tensor([1, 2, 3]),
        offspring_sources=(
            "anchor_offspring",
            "anchor_offspring",
            "weighted_offspring",
        ),
        info=info(
            2,
            {"elite": 1, "anchor_offspring": 2, "weighted_offspring": 1},
        ),
    )
    second_indices = torch.tensor(second_parent_indices)
    second_plan = EDSParentPlan(
        elite_indices=second_indices[:1],
        offspring_parent_indices=second_indices[1:],
        offspring_sources=("weighted_offspring",) * 3,
        info=info(
            0,
            {"elite": 1, "anchor_offspring": 0, "weighted_offspring": 3},
        ),
    )
    plans = iter([first_plan, second_plan])

    def score(samples, **kwargs):
        costs = samples[:, 0, 39].clone()
        return costs, {"rewards": -costs}

    def rollout(**kwargs):
        population = kwargs["noisy_action"]
        costs = population[:, 0, 39].clone()
        return population, costs, {"rewards": -costs}

    monkeypatch.setattr(stub_steer, "_eds_initial_population", lambda **kwargs: initial.clone())
    monkeypatch.setattr(stub_steer, "_eds_select_parent_plan", lambda *args: next(plans))
    monkeypatch.setattr(stub_steer, "_eds_renoise_reference", lambda samples, steps: samples)
    monkeypatch.setattr(stub_steer, "_eds_score_population_as_cost", score)
    monkeypatch.setattr(stub_steer, "_eds_rollout_reference", rollout)
    cfg = stub_steer._resolve_eds_config_with_reference_defaults(
        {
            "population_size": 4,
            "cem_iters": 2,
            "elite_carryover_count": 1,
            "parent_coverage_mode": "eef_kcenter",
            "parent_anchor_count": 2,
            "mechanism_pretest": {
                "enabled": True,
                "first_chunk_only": True,
                "save_single_step": True,
                "save_full_process": True,
                "max_full_process_iters": 2,
            },
        }
    )

    stub_steer._eds_guided_denoise_loop(
        x_t=torch.zeros_like(initial),
        cond=_rollout_cond(stub_steer),
        keypoints=None,
        guidance_fns=None,
        eds_config=cfg,
        verbose=False,
        global_step=0,
        current_stage=0,
    )

    metrics = stub_steer.get_last_eds_metrics()
    selection_info = stub_steer.get_last_eds_mechanism_trace().selection_info
    assert metrics["initial_anchor_lineage_count"] == 2
    assert metrics["final_unique_anchor_lineage_survival_count"] == expected_survival
    assert metrics["final_unique_anchor_lineage_survival_ratio"] == pytest.approx(
        expected_ratio
    )
    assert selection_info["initial_anchor_lineage_count"] == 2
    assert selection_info["final_unique_anchor_lineage_survival_count"] == expected_survival
    assert selection_info["final_unique_anchor_lineage_survival_ratio"] == pytest.approx(
        expected_ratio
    )


def _run_adaptive_rbf_gradient_fallback_loop(
    stub_steer,
    stub_adapter,
    monkeypatch,
    *,
    initial_reference,
):
    from core import rdt_policy_steer
    from core.rdt_policy_steer import EDSParentPlan

    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    cond = _rollout_cond(stub_steer)
    initial_population = torch.zeros(3, 64, 128)
    initial_population[:, :, 39] = torch.arange(3, dtype=torch.float32)[:, None]
    warnings = []
    rollout_infos = []
    plan = EDSParentPlan(
        elite_indices=torch.empty(0, dtype=torch.long),
        offspring_parent_indices=torch.arange(3),
        offspring_sources=("weighted_offspring",) * 3,
        info={
            "selection_beta": 0.0,
            "selection_ess": 3.0,
            "selection_ess_ratio": 1.0,
            "selection_entropy_normalized": 1.0,
            "selection_max_probability": 1.0 / 3.0,
            "selection_degenerate_reward": False,
            "elite_count": 0,
            "anchor_requested_count": 0,
            "anchor_count": 0,
            "anchor_shortfall": 0,
            "anchor_eligible_count": 3,
            "anchor_unique_ratio": None,
            "anchor_min_pairwise_eef_distance": None,
            "anchor_fallback_reason": None,
            "offspring_unique_parent_ratio": 1.0,
            "parent_mode_coverage": 1.0,
            "parent_count_by_source": {
                "elite": 0,
                "anchor_offspring": 0,
                "weighted_offspring": 3,
            },
        },
    )

    def fake_score(samples, **kwargs):
        costs = samples[:, 0, 39].detach().clone()
        return costs, {"rewards": -costs}

    monkeypatch.setattr(
        rdt_policy_steer.log,
        "warning",
        lambda message: warnings.append(str(message)),
    )
    monkeypatch.setattr(
        stub_steer,
        "_eds_initial_population",
        lambda **kwargs: initial_population.clone(),
    )
    monkeypatch.setattr(stub_steer, "_eds_score_population_as_cost", fake_score)
    monkeypatch.setattr(stub_steer, "_eds_select_parent_plan", lambda *args: plan)
    monkeypatch.setattr(
        stub_steer,
        "_eds_renoise_reference",
        lambda offspring, n_trunc_steps: offspring,
    )
    diversity_values = iter([float(initial_reference), 0.0])
    monkeypatch.setattr(
        stub_steer,
        "_eds_eef_trajectory_diversity",
        lambda samples: next(diversity_values),
    )
    monkeypatch.setattr(stub_steer, "_compute_diversity_gradient", lambda samples: None)
    rollout_reference = stub_steer._eds_rollout_reference

    def capture_rollout_info(**kwargs):
        population, costs, info = rollout_reference(**kwargs)
        rollout_infos.append(dict(info))
        return population, costs, info

    monkeypatch.setattr(stub_steer, "_eds_rollout_reference", capture_rollout_info)

    stub_steer._eds_guided_denoise_loop(
        x_t=torch.zeros_like(initial_population),
        cond=cond,
        keypoints=None,
        guidance_fns=None,
        eds_config=_adaptive_rbf_test_config(
            population_size=3,
            cem_iters=1,
            rollout_diversity_scale=2.5,
        ),
        verbose=False,
        global_step=0,
        current_stage=0,
    )

    return stub_steer.get_last_eds_metrics(), warnings, rollout_infos


def test_adaptive_rbf_loop_preserves_controller_and_gradient_fallback_reasons(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    metrics, warnings, rollout_infos = _run_adaptive_rbf_gradient_fallback_loop(
        stub_steer,
        stub_adapter,
        monkeypatch,
        initial_reference=0.0,
    )

    assert metrics["adaptive_rbf_fallback_used"] is True
    assert "reference" in metrics["adaptive_rbf_fallback_reason"]
    assert metrics["rollout_diversity_fallback_used"] is True
    assert "diversity_gradient_none" in metrics["rollout_diversity_fallback_reason"]
    assert metrics["per_iter"][0]["adaptive_rbf_scale_requested"] == 2.5
    assert metrics["per_iter"][0]["adaptive_rbf_scale_applied"] == 0.0
    assert metrics["adaptive_rbf_active_iter_count"] == 0
    assert metrics["adaptive_rbf_particle_count"] == 0
    assert rollout_infos[0]["rollout_diversity_scale"] == 2.5
    assert len(warnings) == 2
    assert any("controller fixed-scale fallback" in message for message in warnings)
    assert any("rollout diversity fallback to baseline" in message for message in warnings)


def test_adaptive_rbf_valid_controller_gradient_fallback_preserves_attempted_scale(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    metrics, warnings, rollout_infos = _run_adaptive_rbf_gradient_fallback_loop(
        stub_steer,
        stub_adapter,
        monkeypatch,
        initial_reference=1.0,
    )

    iter_metrics = metrics["per_iter"][0]
    assert metrics["adaptive_rbf_fallback_used"] is False
    assert metrics["adaptive_rbf_fallback_reason"] is None
    assert metrics["rollout_diversity_fallback_used"] is True
    assert "diversity_gradient_none" in metrics["rollout_diversity_fallback_reason"]
    assert iter_metrics["adaptive_rbf_trigger_reason"] == "below_band"
    assert iter_metrics["adaptive_rbf_scale_requested"] > 0.0
    assert iter_metrics["resolved_rollout_diversity_scale"] == (
        iter_metrics["adaptive_rbf_scale_requested"]
    )
    assert iter_metrics["adaptive_rbf_scale_applied"] == 0.0
    assert iter_metrics["adaptive_rbf_active_particle_count"] == 0
    assert metrics["adaptive_rbf_active_iter_count"] == 0
    assert metrics["adaptive_rbf_particle_count"] == 0
    assert rollout_infos[0]["rollout_diversity_scale"] == (
        iter_metrics["adaptive_rbf_scale_requested"]
    )
    assert len(warnings) == 1
    assert "rollout diversity fallback to baseline" in warnings[0]


def test_eds_legacy_parent_loop_preserves_seeded_final_population(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 4},
    )
    cond = _rollout_cond(stub_steer)
    initial_population = torch.zeros(4, 64, 128)
    initial_population[:, :, 39] = torch.tensor([0.0, 1.0, 2.0, 3.0])[:, None]
    captured_final = []

    def fake_score(samples, **kwargs):
        costs = samples[:, 0, 39].detach().clone()
        return costs, {"rewards": -costs}

    def fake_renoise(samples, n_trunc_steps):
        result = samples.clone()
        result[:, :, 39] += torch.randn_like(result[:, :, 39])
        return result

    def fake_rollout(**kwargs):
        result = kwargs["noisy_action"].clone()
        result[:, :, 39] += 0.25
        costs, info = fake_score(result)
        return result, costs, info

    def capture_ordered(samples, costs):
        captured_final.append(samples.detach().clone())
        return samples.detach()

    monkeypatch.setattr(
        stub_steer,
        "_eds_initial_population",
        lambda **kwargs: initial_population.clone(),
    )
    monkeypatch.setattr(stub_steer, "_eds_score_population_as_cost", fake_score)
    monkeypatch.setattr(stub_steer, "_eds_renoise_reference", fake_renoise)
    monkeypatch.setattr(stub_steer, "_eds_rollout_reference", fake_rollout)
    monkeypatch.setattr(stub_steer, "_eds_order_candidates_by_cost", capture_ordered)
    cfg = stub_steer._resolve_eds_config_with_reference_defaults(
        {
            "population_size": 4,
            "cem_iters": 1,
            "temperature": 0.37,
            "elite_carryover_count": 0,
            "parent_coverage_mode": "none",
        }
    )

    initial_costs, _ = fake_score(initial_population)
    probabilities, _ = stub_steer._eds_compute_parent_weights(initial_costs, cfg)
    torch.manual_seed(44)
    old_indices = torch.multinomial(probabilities, 4, replacement=True)
    expected_final = fake_renoise(initial_population[old_indices], 5)
    expected_final, expected_costs, _ = fake_rollout(noisy_action=expected_final)
    expected_selected = expected_final[torch.argmin(expected_costs) : torch.argmin(expected_costs) + 1]

    torch.manual_seed(44)
    selected = stub_steer._eds_guided_denoise_loop(
        x_t=torch.zeros_like(initial_population),
        cond=cond,
        keypoints=None,
        guidance_fns=None,
        eds_config=cfg,
        verbose=False,
        global_step=0,
        current_stage=0,
    )

    torch.testing.assert_close(captured_final[-1], expected_final)
    torch.testing.assert_close(selected, expected_selected)


@pytest.mark.parametrize("use_cem", [False, True], ids=["weighted", "cem"])
def test_eds_legacy_parent_complete_loop_reuses_scores_and_preserves_rng_exact(
    stub_steer,
    stub_adapter,
    monkeypatch,
    use_cem,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 4},
    )
    cond = _rollout_cond(stub_steer)
    initial_population = torch.zeros(4, 64, 128)
    initial_population[:, :, 39] = torch.tensor([0.0, 1.0, 2.0, 3.0])[:, None]
    cfg = stub_steer._resolve_eds_config_with_reference_defaults(
        {
            "population_size": 4,
            "cem_iters": 2,
            "temperature": 0.37,
            "use_cem": use_cem,
            "num_elites": 2,
            "elite_carryover_count": 0,
            "parent_coverage_mode": "none",
        }
    )

    def score_with_rng(samples, calls):
        calls.append(int(samples.shape[0]))
        torch.rand((), device=samples.device)
        costs = samples[:, 0, 39].detach().clone()
        return costs, {"rewards": -costs}

    def renoise_with_rng(samples, n_trunc_steps):
        result = samples.clone()
        result[:, :, 39] += torch.randn_like(result[:, :, 39])
        return result

    def rollout_with_score(samples, calls):
        result = samples.clone()
        result[:, :, 39] += 0.25
        costs, info = score_with_rng(result, calls)
        return result, costs, info

    torch.manual_seed(101)
    expected_score_calls = []
    expected_population = initial_population.clone()
    expected_costs, _ = score_with_rng(expected_population, expected_score_calls)
    expected_parent_indices = []
    for n_trunc_steps in (5, 1):
        if use_cem:
            cem_elites = torch.argsort(expected_costs)[: cfg.num_elites]
            parent_indices = cem_elites[
                torch.randint(0, cfg.num_elites, (cfg.population_size,))
            ]
        else:
            probabilities, _ = stub_steer._eds_compute_parent_weights(
                expected_costs,
                cfg,
            )
            parent_indices = torch.multinomial(
                probabilities,
                cfg.population_size,
                replacement=True,
            )
        expected_parent_indices.append(parent_indices.clone())
        expected_population = expected_population.index_select(0, parent_indices)
        expected_population = renoise_with_rng(expected_population, n_trunc_steps)
        expected_population, expected_costs, _ = rollout_with_score(
            expected_population,
            expected_score_calls,
        )
    expected_best_idx = int(torch.argmin(expected_costs).item())
    expected_selected = expected_population[expected_best_idx : expected_best_idx + 1]
    expected_rng_state = torch.get_rng_state()

    actual_score_calls = []
    actual_parent_indices = []
    captured_final = []

    monkeypatch.setattr(
        stub_steer,
        "_eds_initial_population",
        lambda **kwargs: initial_population.clone(),
    )
    monkeypatch.setattr(
        stub_steer,
        "_eds_score_population_as_cost",
        lambda samples, **kwargs: score_with_rng(samples, actual_score_calls),
    )
    monkeypatch.setattr(stub_steer, "_eds_renoise_reference", renoise_with_rng)
    monkeypatch.setattr(
        stub_steer,
        "_eds_rollout_reference",
        lambda **kwargs: rollout_with_score(
            kwargs["noisy_action"],
            actual_score_calls,
        ),
    )
    original_select_parent_plan = stub_steer._eds_select_parent_plan

    def capture_parent_plan(population, costs, current_cfg):
        plan = original_select_parent_plan(population, costs, current_cfg)
        actual_parent_indices.append(plan.offspring_parent_indices.detach().clone())
        return plan

    monkeypatch.setattr(stub_steer, "_eds_select_parent_plan", capture_parent_plan)
    monkeypatch.setattr(
        stub_steer,
        "_eds_order_candidates_by_cost",
        lambda samples, costs: captured_final.append(samples.detach().clone()) or samples.detach(),
    )

    torch.manual_seed(101)
    selected = stub_steer._eds_guided_denoise_loop(
        x_t=torch.zeros_like(initial_population),
        cond=cond,
        keypoints=None,
        guidance_fns=None,
        eds_config=cfg,
        verbose=False,
        global_step=0,
        current_stage=0,
    )
    actual_rng_state = torch.get_rng_state()

    assert expected_score_calls == [4, 4, 4]
    assert actual_score_calls == expected_score_calls
    metrics = stub_steer.get_last_eds_metrics()
    assert metrics["score_call_count"] == 3
    assert metrics["search_schedule_mode"] == "legacy_linear"
    assert metrics["eds_iters_executed"] == cfg.cem_iters
    assert metrics["early_stop_used"] is False
    assert metrics["early_stop_reason"] is None
    assert [item["n_trunc_steps"] for item in metrics["per_iter"]] == [5, 1]
    assert [item["resolved_renoise_reason"] for item in metrics["per_iter"]] == [
        "legacy_linear",
        "legacy_linear",
    ]
    assert len(actual_parent_indices) == len(expected_parent_indices) == 2
    for actual, expected in zip(actual_parent_indices, expected_parent_indices):
        assert torch.equal(actual, expected)
    assert torch.equal(actual_rng_state, expected_rng_state)
    torch.testing.assert_close(captured_final[-1], expected_population)
    torch.testing.assert_close(selected, expected_selected)


@pytest.mark.parametrize(
    ("full_parent_indices", "current_best_idx", "previous_best_idx", "expected"),
    [
        (torch.tensor([0, 1, 2]), 0, 0, True),
        (torch.tensor([1, 0, 2]), 0, 0, False),
        (torch.tensor([0, 3, 1, 2]), 0, 0, True),
        (torch.tensor([0, 3, 1, 2]), 2, 0, False),
    ],
    ids=["zero_elite_stable", "zero_elite_unstable", "elite_stable", "elite_unstable"],
)
def test_eds_early_stop_lineage_maps_full_parent_indices(
    stub_steer,
    full_parent_indices,
    current_best_idx,
    previous_best_idx,
    expected,
):
    assert stub_steer._eds_best_lineage_is_stable(
        full_parent_indices=full_parent_indices,
        current_best_idx=current_best_idx,
        previous_best_idx=previous_best_idx,
    ) is expected


def _adaptive_schedule_parent_plan(parent_indices):
    from core.rdt_policy_steer import EDSParentPlan

    parent_indices = torch.as_tensor(parent_indices, dtype=torch.long)
    population_size = int(parent_indices.numel())
    return EDSParentPlan(
        elite_indices=torch.empty(0, dtype=torch.long),
        offspring_parent_indices=parent_indices,
        offspring_sources=("weighted_offspring",) * population_size,
        info={
            "selection_beta": 0.0,
            "selection_ess": float(population_size),
            "selection_ess_ratio": 1.0,
            "selection_entropy_normalized": 1.0,
            "selection_max_probability": 1.0 / float(population_size),
            "selection_degenerate_reward": False,
            "elite_count": 0,
            "anchor_requested_count": 0,
            "anchor_count": 0,
            "anchor_shortfall": 0,
            "anchor_eligible_count": population_size,
            "anchor_unique_ratio": None,
            "anchor_min_pairwise_eef_distance": None,
            "anchor_fallback_reason": None,
            "offspring_unique_parent_ratio": (
                float(parent_indices.unique().numel()) / float(population_size)
            ),
            "parent_mode_coverage": (
                float(parent_indices.unique().numel()) / float(population_size)
            ),
            "parent_count_by_source": {
                "elite": 0,
                "anchor_offspring": 0,
                "weighted_offspring": population_size,
            },
        },
    )


def _run_eds_adaptive_schedule_case(
    *,
    steer,
    adapter,
    monkeypatch,
    reward_sequences,
    parent_indices,
    diversity_values,
    min_iters=2,
    patience=2,
    trace_enabled=False,
):
    steer.post_init(
        adapter=adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    initial_population = torch.zeros(3, 64, 128)
    initial_population[:, :, 39] = torch.arange(3, dtype=torch.float32)[:, None]
    initial_rewards = torch.tensor([1.0, 0.0, -1.0])
    rollout_rewards = iter(torch.tensor(item, dtype=torch.float32) for item in reward_sequences)
    plans = iter(_adaptive_schedule_parent_plan(item) for item in parent_indices)
    eef_diversities = iter(float(item) for item in diversity_values)
    renoise_steps = []

    def fake_initial_score(samples, **kwargs):
        rewards = initial_rewards.to(device=samples.device, dtype=samples.dtype)
        return -rewards, {"rewards": rewards}

    def fake_rollout(**kwargs):
        population = kwargs["noisy_action"]
        rewards = next(rollout_rewards).to(
            device=population.device,
            dtype=population.dtype,
        )
        return population, -rewards, {"rewards": rewards}

    monkeypatch.setattr(
        steer,
        "_eds_initial_population",
        lambda **kwargs: initial_population.clone(),
    )
    monkeypatch.setattr(steer, "_eds_score_population_as_cost", fake_initial_score)
    monkeypatch.setattr(
        steer,
        "_eds_select_parent_plan",
        lambda population, costs, cfg: next(plans),
    )
    monkeypatch.setattr(
        steer,
        "_eds_renoise_reference",
        lambda population, n_trunc_steps: (
            renoise_steps.append(int(n_trunc_steps)) or population
        ),
    )
    monkeypatch.setattr(steer, "_eds_rollout_reference", fake_rollout)
    monkeypatch.setattr(
        steer,
        "_eds_eef_trajectory_diversity",
        lambda population: next(eef_diversities),
    )
    cfg = steer._resolve_eds_config_with_reference_defaults(
        {
            "population_size": 3,
            "cem_iters": len(reward_sequences),
            "elite_carryover_count": 0,
            "parent_coverage_mode": "none",
            "search_schedule_mode": "adaptive",
            "adaptive_min_cem_iters": min_iters,
            "adaptive_early_stop_patience": patience,
            "adaptive_reward_improvement_eps": 1e-3,
            "rollout_diversity_target_ratio": 1.0,
            "rollout_diversity_band_ratio": 0.2,
            "mechanism_pretest": {
                "enabled": trace_enabled,
                "first_chunk_only": True,
                "save_single_step": True,
                "save_full_process": True,
                "save_tensors": True,
                "plot_3d": False,
                "max_full_process_iters": len(reward_sequences),
            },
        }
    )

    selected = steer._eds_guided_denoise_loop(
        x_t=torch.zeros_like(initial_population),
        cond=_rollout_cond(steer),
        keypoints=None,
        guidance_fns=None,
        eds_config=cfg,
        verbose=False,
        global_step=0,
        current_stage=0,
    )
    return selected, steer.get_last_eds_metrics(), steer.get_last_eds_artifacts(), renoise_steps


def test_eds_adaptive_early_stop_requires_all_conditions_and_keeps_final_outputs(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    selected, metrics, artifacts, renoise_steps = _run_eds_adaptive_schedule_case(
        steer=stub_steer,
        adapter=stub_adapter,
        monkeypatch=monkeypatch,
        reward_sequences=[[1.0, 0.0, -1.0]] * 5,
        parent_indices=[[0, 1, 2]] * 5,
        diversity_values=[1.0] * 6,
    )

    assert metrics["eds_iters_executed"] == 2
    assert metrics["early_stop_used"] is True
    assert metrics["early_stop_reason"] == "adaptive_plateau_stable_in_band"
    assert metrics["reward_plateau_count"] == 2
    assert len(metrics["per_iter"]) == len(artifacts["per_iter"]) == 2
    assert renoise_steps == [5, 2]
    assert metrics["per_iter"][0]["resolved_renoise_reason"] == "adaptive_initial_max"
    assert metrics["per_iter"][1]["resolved_renoise_reason"] == "adaptive_uncertain"
    assert metrics["selected_idx"] is not None
    assert metrics["selected_reward"] == pytest.approx(1.0)
    assert metrics["nonfinite_count"] == 0
    assert metrics["action_mask_violation_max"] == 0.0
    assert tuple(selected.shape) == (1, 64, 128)
    assert torch.isfinite(selected).all()


def test_eds_adaptive_early_stop_trace_matches_executed_iterations(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    _, metrics, artifacts, _ = _run_eds_adaptive_schedule_case(
        steer=stub_steer,
        adapter=stub_adapter,
        monkeypatch=monkeypatch,
        reward_sequences=[[1.0, 0.0, -1.0]] * 5,
        parent_indices=[[0, 1, 2]] * 5,
        diversity_values=[1.0] * 6,
        trace_enabled=True,
    )
    trace = stub_steer.get_last_eds_mechanism_trace()
    full_process_stages = [
        stage
        for stage in trace.stages
        if stage.stage == "full_process_after_rollout"
    ]

    assert metrics["eds_iters_executed"] == 2
    assert len(artifacts["per_iter"]) == 2
    assert [stage.iter_idx for stage in full_process_stages] == [0, 1]
    assert trace.search_schedule_info["enabled"] is True
    assert trace.search_schedule_info["eds_iters_executed"] == 2
    assert trace.search_schedule_info["stable_lineage_count"] == 2
    assert len(trace.search_schedule_info["per_iter"]) == 2
    assert trace.search_schedule_info["per_iter"][1]["best_lineage_stable"] is True
    assert metrics["stable_lineage_count"] == 2
    assert metrics["per_iter"][1]["stable_lineage_count"] == 2


def test_eds_adaptive_full_budget_is_not_labeled_early_stop(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    _, metrics, artifacts, renoise_steps = _run_eds_adaptive_schedule_case(
        steer=stub_steer,
        adapter=stub_adapter,
        monkeypatch=monkeypatch,
        reward_sequences=[[1.0, 0.0, -1.0]] * 4,
        parent_indices=[[0, 1, 2]] * 4,
        diversity_values=[1.0] * 5,
        min_iters=4,
        patience=2,
    )

    assert metrics["eds_iters_executed"] == 4
    assert metrics["early_stop_used"] is False
    assert metrics["early_stop_reason"] is None
    assert len(metrics["per_iter"]) == len(artifacts["per_iter"]) == 4
    assert len(renoise_steps) == 4


def test_eds_adaptive_early_stop_requires_consecutive_stable_lineage(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    _, metrics, _, _ = _run_eds_adaptive_schedule_case(
        steer=stub_steer,
        adapter=stub_adapter,
        monkeypatch=monkeypatch,
        reward_sequences=[[1.0, 0.0, -1.0]] * 5,
        parent_indices=[
            [1, 0, 2],
            [0, 1, 2],
            [1, 0, 2],
            [0, 1, 2],
            [1, 0, 2],
        ],
        diversity_values=[1.0] * 6,
        min_iters=2,
        patience=2,
    )

    assert metrics["eds_iters_executed"] == 5
    assert metrics["early_stop_used"] is False
    assert metrics["early_stop_reason"] is None


def test_eds_adaptive_early_stop_integrates_real_parent_plan_and_eef_projection(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 4},
    )
    cond = _rollout_cond(stub_steer)
    initial_population = torch.zeros(4, 64, 128)
    initial_population[1, :, 39] = 0.01
    initial_population[2, :, 40] = -0.02
    initial_population[3, :, 39] = 0.03
    initial_population = stub_steer._apply_action_mask(initial_population, cond)
    keypoints = torch.zeros(1, 3)
    guidance_fns = [
        lambda target, traj: -torch.linalg.norm(
            traj[:, -1, :3] - target[0, :3],
            dim=-1,
        ).sum()
    ]
    expected_initial_eef_diversity = stub_steer._eds_eef_trajectory_diversity(
        initial_population
    )

    def score_with_real_projection(samples):
        return stub_steer._eds_score_population_as_cost(
            samples,
            keypoints=keypoints,
            guidance_fns=guidance_fns,
            reward_mode="normal",
            shuffle_seed=0,
        )

    def identity_rollout(**kwargs):
        population = kwargs["noisy_action"]
        costs, info = score_with_real_projection(population)
        return population, costs, info

    monkeypatch.setattr(
        stub_steer,
        "_eds_initial_population",
        lambda **kwargs: initial_population.clone(),
    )
    monkeypatch.setattr(
        stub_steer,
        "_eds_renoise_reference",
        lambda population, n_trunc_steps: population,
    )
    monkeypatch.setattr(stub_steer, "_eds_rollout_reference", identity_rollout)
    cfg = stub_steer._resolve_eds_config_with_reference_defaults(
        {
            "population_size": 4,
            "cem_iters": 4,
            "elite_carryover_count": 1,
            "parent_coverage_mode": "none",
            "search_schedule_mode": "adaptive",
            "adaptive_min_cem_iters": 2,
            "adaptive_early_stop_patience": 2,
            "adaptive_reward_improvement_eps": 1e-3,
            "rollout_diversity_target_ratio": 1.0,
            "rollout_diversity_band_ratio": 1.0,
        }
    )

    torch.manual_seed(73)
    selected = stub_steer._eds_guided_denoise_loop(
        x_t=torch.zeros_like(initial_population),
        cond=cond,
        keypoints=keypoints,
        guidance_fns=guidance_fns,
        eds_config=cfg,
        verbose=False,
        global_step=0,
        current_stage=0,
    )
    metrics = stub_steer.get_last_eds_metrics()

    assert expected_initial_eef_diversity > 0.0
    assert metrics["initial_eef_diversity_final"] == pytest.approx(
        expected_initial_eef_diversity
    )
    assert metrics["eds_iters_executed"] == 2
    assert metrics["early_stop_used"] is True
    assert metrics["early_stop_reason"] == "adaptive_plateau_stable_in_band"
    assert [item["elite_count"] for item in metrics["per_iter"]] == [1, 1]
    assert metrics["elite_carryover_count_observed"] == 1
    assert metrics["score_call_count"] == 5
    assert metrics["selected_reward"] == pytest.approx(0.0)
    assert tuple(selected.shape) == (1, 64, 128)
    assert torch.isfinite(selected).all()


@pytest.mark.parametrize(
    (
        "reward_sequences",
        "parent_indices",
        "diversity_values",
        "min_iters",
        "expected_iters",
        "expected_early_stop",
    ),
    [
        (
            [[1.1, 0.0, -1.0], [1.2, 0.0, -1.0], [1.3, 0.0, -1.0], [1.4, 0.0, -1.0], [1.5, 0.0, -1.0]],
            [[0, 1, 2]] * 5,
            [1.0] * 6,
            2,
            5,
            False,
        ),
        (
            [[1.0, 0.0, -1.0]] * 5,
            [[1, 0, 2]] * 5,
            [1.0] * 6,
            2,
            5,
            False,
        ),
        (
            [[1.0, 0.0, -1.0]] * 5,
            [[0, 1, 2]] * 5,
            [1.0] + [0.1] * 5,
            2,
            5,
            False,
        ),
        (
            [[1.0, 0.0, -1.0]] * 5,
            [[0, 1, 2]] * 5,
            [1.0] * 6,
            4,
            4,
            True,
        ),
    ],
    ids=["reward_improving", "unstable_lineage", "out_of_band", "min_iters"],
)
def test_eds_adaptive_early_stop_conditions_independently_gate_break(
    stub_steer,
    stub_adapter,
    monkeypatch,
    reward_sequences,
    parent_indices,
    diversity_values,
    min_iters,
    expected_iters,
    expected_early_stop,
):
    _, metrics, artifacts, renoise_steps = _run_eds_adaptive_schedule_case(
        steer=stub_steer,
        adapter=stub_adapter,
        monkeypatch=monkeypatch,
        reward_sequences=reward_sequences,
        parent_indices=parent_indices,
        diversity_values=diversity_values,
        min_iters=min_iters,
    )

    assert metrics["eds_iters_executed"] == expected_iters
    assert metrics["early_stop_used"] is expected_early_stop
    assert len(metrics["per_iter"]) == len(artifacts["per_iter"]) == expected_iters
    assert len(renoise_steps) == expected_iters


def test_eds_zero_elite_anchor_loop_reuses_rollout_scores(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 4},
    )
    initial_population = torch.zeros(4, 64, 128)
    initial_population[:, :, 39] = torch.arange(4, dtype=torch.float32)[:, None]
    score_calls = []

    def fake_score(samples, **kwargs):
        score_calls.append(int(samples.shape[0]))
        costs = samples[:, 0, 39].detach().clone()
        return costs, {"rewards": -costs}

    def fake_rollout(**kwargs):
        population = kwargs["noisy_action"]
        costs, info = fake_score(population)
        return population, costs, info

    monkeypatch.setattr(
        stub_steer,
        "_eds_initial_population",
        lambda **kwargs: initial_population.clone(),
    )
    monkeypatch.setattr(stub_steer, "_eds_score_population_as_cost", fake_score)
    monkeypatch.setattr(
        stub_steer,
        "_eds_renoise_reference",
        lambda population, n_trunc_steps: population,
    )
    monkeypatch.setattr(stub_steer, "_eds_rollout_reference", fake_rollout)
    cfg = stub_steer._resolve_eds_config_with_reference_defaults(
        {
            "population_size": 4,
            "cem_iters": 1,
            "elite_carryover_count": 0,
            "parent_coverage_mode": "eef_kcenter",
            "parent_anchor_count": 1,
            "parent_anchor_reward_quantile": 0.0,
        }
    )

    stub_steer._eds_guided_denoise_loop(
        x_t=torch.zeros_like(initial_population),
        cond=_rollout_cond(stub_steer),
        keypoints=None,
        guidance_fns=None,
        eds_config=cfg,
        verbose=False,
        global_step=0,
        current_stage=0,
    )

    assert score_calls == [4, 4]
    assert stub_steer.get_last_eds_metrics()["score_call_count"] == 2


def test_eds_chunk_parent_metrics_aggregate_across_all_iterations(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    from core.rdt_policy_steer import EDSParentPlan

    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 4},
    )
    initial_population = torch.zeros(4, 64, 128)
    initial_population[:, :, 39] = torch.arange(4, dtype=torch.float32)[:, None]

    def plan_info(
        *,
        anchor_count,
        anchor_min_distance,
        offspring_unique_ratio,
        parent_mode_coverage,
        source_counts,
    ):
        return {
            "selection_beta": 0.1,
            "selection_ess": 4.0,
            "selection_ess_ratio": 1.0,
            "selection_entropy_normalized": 1.0,
            "selection_max_probability": 0.25,
            "selection_degenerate_reward": False,
            "elite_count": 1,
            "anchor_requested_count": anchor_count,
            "anchor_count": anchor_count,
            "anchor_shortfall": 0,
            "anchor_eligible_count": 3,
            "anchor_unique_ratio": 1.0 if anchor_count else None,
            "anchor_min_pairwise_eef_distance": anchor_min_distance,
            "anchor_fallback_reason": None,
            "offspring_unique_parent_ratio": offspring_unique_ratio,
            "parent_mode_coverage": parent_mode_coverage,
            "parent_count_by_source": source_counts,
        }

    plans = iter(
        [
            EDSParentPlan(
                elite_indices=torch.tensor([0]),
                offspring_parent_indices=torch.tensor([1, 2, 2]),
                offspring_sources=(
                    "anchor_offspring",
                    "anchor_offspring",
                    "weighted_offspring",
                ),
                info=plan_info(
                    anchor_count=2,
                    anchor_min_distance=2.0,
                    offspring_unique_ratio=2.0 / 3.0,
                    parent_mode_coverage=0.75,
                    source_counts={
                        "elite": 1,
                        "anchor_offspring": 2,
                        "weighted_offspring": 1,
                    },
                ),
            ),
            EDSParentPlan(
                elite_indices=torch.tensor([0]),
                offspring_parent_indices=torch.tensor([1, 2, 3]),
                offspring_sources=(
                    "anchor_offspring",
                    "weighted_offspring",
                    "weighted_offspring",
                ),
                info=plan_info(
                    anchor_count=1,
                    anchor_min_distance=5.0,
                    offspring_unique_ratio=1.0,
                    parent_mode_coverage=1.0,
                    source_counts={
                        "elite": 1,
                        "anchor_offspring": 1,
                        "weighted_offspring": 2,
                    },
                ),
            ),
            EDSParentPlan(
                elite_indices=torch.tensor([0]),
                offspring_parent_indices=torch.tensor([0, 0, 0]),
                offspring_sources=("weighted_offspring",) * 3,
                info=plan_info(
                    anchor_count=0,
                    anchor_min_distance=None,
                    offspring_unique_ratio=1.0 / 3.0,
                    parent_mode_coverage=0.25,
                    source_counts={
                        "elite": 1,
                        "anchor_offspring": 0,
                        "weighted_offspring": 3,
                    },
                ),
            ),
        ]
    )

    score_call_count = []

    def fake_score(samples, **kwargs):
        score_call_count.append(int(samples.shape[0]))
        if len(score_call_count) == 4:
            costs = torch.tensor([3.0, 2.0, 1.0, 0.0])
        else:
            costs = samples[:, 0, 39].detach().clone()
        return costs, {"rewards": -costs}

    def fake_rollout(**kwargs):
        population = kwargs["noisy_action"]
        costs = population[:, 0, 39].detach().clone()
        return population, costs, {"rewards": -costs}

    monkeypatch.setattr(
        stub_steer,
        "_eds_initial_population",
        lambda **kwargs: initial_population.clone(),
    )
    monkeypatch.setattr(stub_steer, "_eds_score_population_as_cost", fake_score)
    monkeypatch.setattr(
        stub_steer,
        "_eds_select_parent_plan",
        lambda population, costs, cfg: next(plans),
    )
    monkeypatch.setattr(
        stub_steer,
        "_eds_renoise_reference",
        lambda population, n_trunc_steps: population,
    )
    monkeypatch.setattr(stub_steer, "_eds_rollout_reference", fake_rollout)
    cfg = stub_steer._resolve_eds_config_with_reference_defaults(
        {
            "population_size": 4,
            "cem_iters": 3,
            "elite_carryover_count": 1,
            "parent_coverage_mode": "eef_kcenter",
            "parent_anchor_count": 2,
        }
    )

    stub_steer._eds_guided_denoise_loop(
        x_t=torch.zeros_like(initial_population),
        cond=_rollout_cond(stub_steer),
        keypoints=None,
        guidance_fns=None,
        eds_config=cfg,
        verbose=False,
        global_step=0,
        current_stage=0,
    )

    metrics = stub_steer.get_last_eds_metrics()
    assert metrics["parent_mode_coverage"] == pytest.approx(2.0 / 3.0)
    assert metrics["parent_count_by_source"] == {
        "elite": 3,
        "anchor_offspring": 3,
        "weighted_offspring": 6,
    }
    assert metrics["offspring_unique_parent_ratio"] == pytest.approx(2.0 / 3.0)
    assert metrics["anchor_unique_ratio"] == pytest.approx(1.0)
    assert metrics["anchor_min_pairwise_eef_distance"] == pytest.approx(2.0)
    assert metrics["anchor_count_observed"] == 2
    assert metrics["elite_carryover_count_observed"] == 1
    assert metrics["selected_parent_source"] == "weighted_offspring"
    json.dumps(metrics, allow_nan=False)


def test_eds_elite_survival_counts_first_iteration_elites_anywhere_in_final_population(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    from core.rdt_policy_steer import EDSParentPlan

    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 4},
    )
    initial_population = torch.zeros(4, 64, 128)
    initial_population[:, :, 39] = torch.tensor([10.0, 20.0, 30.0, 40.0])[:, None]

    def make_plan(elite_indices, offspring_indices, parent_mode_coverage):
        return EDSParentPlan(
            elite_indices=torch.tensor(elite_indices),
            offspring_parent_indices=torch.tensor(offspring_indices),
            offspring_sources=("weighted_offspring",) * 2,
            info={
                "selection_beta": 0.1,
                "selection_ess": 4.0,
                "selection_ess_ratio": 1.0,
                "selection_entropy_normalized": 1.0,
                "selection_max_probability": 0.25,
                "selection_degenerate_reward": False,
                "elite_count": 2,
                "anchor_requested_count": 0,
                "anchor_count": 0,
                "anchor_shortfall": 0,
                "anchor_eligible_count": 2,
                "anchor_unique_ratio": None,
                "anchor_min_pairwise_eef_distance": None,
                "anchor_fallback_reason": None,
                "offspring_unique_parent_ratio": 1.0,
                "parent_mode_coverage": parent_mode_coverage,
                "parent_count_by_source": {
                    "elite": 2,
                    "anchor_offspring": 0,
                    "weighted_offspring": 2,
                },
            },
        )

    plans = iter(
        [
            make_plan([0, 1], [2, 3], 1.0),
            make_plan([2, 3], [0, 2], 0.75),
        ]
    )
    captured_final = []

    def fake_score(samples, **kwargs):
        costs = samples[:, 0, 39].detach().clone()
        return costs, {"rewards": -costs}

    def fake_rollout(**kwargs):
        population = kwargs["noisy_action"]
        costs = population[:, 0, 39].detach().clone()
        return population, costs, {"rewards": -costs}

    monkeypatch.setattr(
        stub_steer,
        "_eds_initial_population",
        lambda **kwargs: initial_population.clone(),
    )
    monkeypatch.setattr(stub_steer, "_eds_score_population_as_cost", fake_score)
    monkeypatch.setattr(
        stub_steer,
        "_eds_select_parent_plan",
        lambda population, costs, cfg: next(plans),
    )
    monkeypatch.setattr(
        stub_steer,
        "_eds_renoise_reference",
        lambda population, n_trunc_steps: population,
    )
    monkeypatch.setattr(stub_steer, "_eds_rollout_reference", fake_rollout)
    monkeypatch.setattr(
        stub_steer,
        "_eds_order_candidates_by_cost",
        lambda samples, costs: captured_final.append(samples.detach().clone()) or samples.detach(),
    )
    cfg = stub_steer._resolve_eds_config_with_reference_defaults(
        {
            "population_size": 4,
            "cem_iters": 2,
            "elite_carryover_count": 2,
        }
    )

    stub_steer._eds_guided_denoise_loop(
        x_t=torch.zeros_like(initial_population),
        cond=_rollout_cond(stub_steer),
        keypoints=None,
        guidance_fns=None,
        eds_config=cfg,
        verbose=False,
        global_step=0,
        current_stage=0,
    )

    torch.testing.assert_close(
        captured_final[-1][:, 0, 39],
        torch.tensor([30.0, 40.0, 10.0, 30.0]),
    )
    assert stub_steer.get_last_eds_metrics()["elite_survival_to_final_count"] == 1


@pytest.mark.parametrize("include_after_rbf", [True, False])
def test_eds_elite_rollout_diversity_metrics_use_full_population(
    stub_steer,
    stub_adapter,
    monkeypatch,
    include_after_rbf,
):
    from core.rdt_policy_steer import EDSParentPlan

    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 4},
    )
    initial_population = torch.zeros(4, 64, 128)
    initial_population[:, :, 39] = torch.tensor([100.0, 1.0, 2.0, 3.0])[:, None]
    plan = EDSParentPlan(
        elite_indices=torch.tensor([0]),
        offspring_parent_indices=torch.tensor([1, 2, 3]),
        offspring_sources=("weighted_offspring",) * 3,
        info={
            "selection_beta": 0.1,
            "selection_ess": 4.0,
            "selection_ess_ratio": 1.0,
            "selection_entropy_normalized": 1.0,
            "selection_max_probability": 0.25,
            "selection_degenerate_reward": False,
            "elite_count": 1,
            "anchor_requested_count": 0,
            "anchor_count": 0,
            "anchor_shortfall": 0,
            "anchor_eligible_count": 3,
            "anchor_unique_ratio": None,
            "anchor_min_pairwise_eef_distance": None,
            "anchor_fallback_reason": None,
            "offspring_unique_parent_ratio": 1.0,
            "parent_mode_coverage": 1.0,
            "parent_count_by_source": {
                "elite": 1,
                "anchor_offspring": 0,
                "weighted_offspring": 3,
            },
        },
    )
    diversity_batch_sizes = []
    endpoint_batch_sizes = []

    def marker_sum(population):
        return float(population[:, 0, 39].sum().item())

    def fake_eef_diversity(population):
        diversity_batch_sizes.append(int(population.shape[0]))
        return marker_sum(population)

    def fake_endpoint_spread(population):
        endpoint_batch_sizes.append(int(population.shape[0]))
        return 1000.0 + marker_sum(population)

    def fake_score(samples, **kwargs):
        costs = torch.arange(
            samples.shape[0],
            device=samples.device,
            dtype=samples.dtype,
        )
        return costs, {"rewards": -costs}

    def fake_rollout(**kwargs):
        before = kwargs["noisy_action"].clone()
        after = before.clone()
        after[:, :, 39] = torch.tensor([10.0, 20.0, 30.0])[:, None]
        final = before.clone()
        final[:, :, 39] = torch.tensor([4.0, 5.0, 6.0])[:, None]
        trace_stages = [("rollout_before_diversity", before)]
        if include_after_rbf:
            trace_stages.append(("rollout_after_diversity_phase", after))
        trace_stages.append(("rollout_final", final))
        info = {
            "rewards": -torch.arange(3, dtype=final.dtype),
            "rollout_diversity_enabled": True,
            "rollout_diversity_mode": "rbf_diverse",
            "rollout_diversity_steps_applied": 1,
            "rollout_diversity_iters_applied": 1,
            "eef_diversity_before_rollout": 6.0,
            "eef_diversity_after_rollout_rbf_phase": (
                60.0 if include_after_rbf else None
            ),
            "eef_diversity_after_rollout_final": 15.0,
            "eef_diversity_rollout_retention_ratio": (
                0.25 if include_after_rbf else None
            ),
            "endpoint_spread_before_rollout": 1006.0,
            "endpoint_spread_after_rollout_rbf_phase": (
                1060.0 if include_after_rbf else None
            ),
            "endpoint_spread_after_rollout_final": 1015.0,
            "rollout_diversity_trace_stages": trace_stages,
        }
        costs = torch.arange(3, dtype=final.dtype)
        return final, costs, info

    monkeypatch.setattr(
        stub_steer,
        "_eds_initial_population",
        lambda **kwargs: initial_population.clone(),
    )
    monkeypatch.setattr(stub_steer, "_eds_score_population_as_cost", fake_score)
    monkeypatch.setattr(
        stub_steer,
        "_eds_select_parent_plan",
        lambda population, costs, cfg: plan,
    )
    monkeypatch.setattr(
        stub_steer,
        "_eds_renoise_reference",
        lambda population, n_trunc_steps: population,
    )
    monkeypatch.setattr(stub_steer, "_eds_rollout_reference", fake_rollout)
    monkeypatch.setattr(
        stub_steer,
        "_eds_eef_trajectory_diversity",
        fake_eef_diversity,
    )
    monkeypatch.setattr(stub_steer, "_eds_endpoint_spread", fake_endpoint_spread)
    cfg = stub_steer._resolve_eds_config_with_reference_defaults(
        {
            "population_size": 4,
            "cem_iters": 1,
            "elite_carryover_count": 1,
        }
    )

    stub_steer._eds_guided_denoise_loop(
        x_t=torch.zeros_like(initial_population),
        cond=_rollout_cond(stub_steer),
        keypoints=None,
        guidance_fns=None,
        eds_config=cfg,
        verbose=False,
        global_step=0,
        current_stage=0,
    )

    metrics = stub_steer.get_last_eds_metrics()
    assert metrics["eef_diversity_before_rollout"] == pytest.approx(106.0)
    assert metrics["eef_diversity_after_rollout_final"] == pytest.approx(115.0)
    assert metrics["endpoint_spread_before_rollout"] == pytest.approx(1106.0)
    assert metrics["endpoint_spread_after_rollout_final"] == pytest.approx(1115.0)
    if include_after_rbf:
        assert metrics["eef_diversity_after_rollout_rbf_phase"] == pytest.approx(160.0)
        assert metrics["eef_diversity_rollout_retention_ratio"] == pytest.approx(
            115.0 / 160.0
        )
        assert metrics["endpoint_spread_after_rollout_rbf_phase"] == pytest.approx(
            1160.0
        )
    else:
        assert metrics["eef_diversity_after_rollout_rbf_phase"] is None
        assert metrics["eef_diversity_rollout_retention_ratio"] is None
        assert metrics["endpoint_spread_after_rollout_rbf_phase"] is None
    assert diversity_batch_sizes and set(diversity_batch_sizes) == {4}
    assert endpoint_batch_sizes and set(endpoint_batch_sizes) == {4}


def test_eds_config_rejects_elite_carryover_equal_to_population(stub_steer):
    with pytest.raises(ValueError, match="elite_carryover_count.*population_size"):
        stub_steer._resolve_eds_config_with_reference_defaults(
            {
                "population_size": 4,
                "elite_carryover_count": 4,
                "parent_anchor_count": 0,
            }
        )


def test_eds_make_trace_stage_records_and_validates_particle_sources(stub_steer):
    population = torch.zeros(2, 64, 128)
    costs = torch.tensor([0.0, 1.0])

    stage = stub_steer._eds_make_trace_stage(
        stage="after_rollout",
        iter_idx=0,
        population=population,
        costs=costs,
        info={"rewards": -costs},
        particle_sources=("elite", "weighted_offspring"),
    )

    assert stage.particle_sources == ["elite", "weighted_offspring"]
    with pytest.raises(ValueError, match="particle_sources.*population"):
        stub_steer._eds_make_trace_stage(
            stage="bad",
            iter_idx=0,
            population=population,
            costs=costs,
            info={"rewards": -costs},
            particle_sources=("elite",),
        )


def test_eds_elite_trace_wires_full_and_offspring_particle_sources(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 4},
    )
    cond = _rollout_cond(stub_steer)
    initial_population = torch.zeros(4, 64, 128)
    initial_population[:, :, 39] = torch.arange(4, dtype=torch.float32)[:, None]

    def fake_score(samples, **kwargs):
        costs = samples[:, 0, 39].detach().clone()
        return costs, {"rewards": -costs}

    def fake_rollout(**kwargs):
        rolled = kwargs["noisy_action"].clone()
        rolled[:, :, 39] += 10.0
        costs, info = fake_score(rolled)
        info["rollout_diversity_trace_stages"] = [("rollout_final", rolled)]
        return rolled, costs, info

    monkeypatch.setattr(
        stub_steer,
        "_eds_initial_population",
        lambda **kwargs: initial_population.clone(),
    )
    monkeypatch.setattr(stub_steer, "_eds_score_population_as_cost", fake_score)
    monkeypatch.setattr(
        stub_steer,
        "_eds_renoise_reference",
        lambda offspring, n_trunc_steps: offspring,
    )
    monkeypatch.setattr(stub_steer, "_eds_rollout_reference", fake_rollout)
    cfg = stub_steer._resolve_eds_config_with_reference_defaults(
        {
            "population_size": 4,
            "cem_iters": 1,
            "elite_carryover_count": 2,
            "parent_coverage_mode": "eef_kcenter",
            "parent_anchor_count": 1,
            "parent_anchor_reward_quantile": 0.0,
            "mechanism_pretest": {
                "enabled": True,
                "first_chunk_only": True,
                "save_full_process": True,
                "max_full_process_iters": 1,
            },
        }
    )

    torch.manual_seed(3)
    stub_steer._eds_guided_denoise_loop(
        x_t=torch.zeros_like(initial_population),
        cond=cond,
        keypoints=None,
        guidance_fns=None,
        eds_config=cfg,
        verbose=False,
        global_step=0,
        current_stage=0,
    )

    trace = stub_steer.get_last_eds_mechanism_trace()
    assert trace is not None
    by_stage = {stage.stage: stage for stage in trace.stages}
    full_sources = [
        "elite",
        "elite",
        "anchor_offspring",
        "weighted_offspring",
    ]
    for stage_name in ("resampled", "after_rollout", "full_process_after_rollout"):
        stage = by_stage[stage_name]
        assert stage.particle_sources == full_sources
        assert len(stage.particle_sources) == stage.actions.shape[0] == 4
    for stage_name in ("renoised", "rollout_final"):
        stage = by_stage[stage_name]
        assert stage.particle_sources == [
            "anchor_offspring",
            "weighted_offspring",
        ]
        assert len(stage.particle_sources) == stage.actions.shape[0] == 2
    assert by_stage["initial"].particle_sources is None


def test_adaptive_ess_loop_records_per_iter_and_chunk_selection_metrics(
    stub_steer,
    stub_adapter,
    mock_batch,
    monkeypatch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 4},
    )
    costs = torch.tensor([-4.0, -2.0, -1.0, 0.0])

    def fake_score_population_as_cost(
        samples,
        *,
        keypoints,
        guidance_fns,
        reward_mode="normal",
        shuffle_seed=0,
    ):
        current_costs = costs.to(device=samples.device, dtype=samples.dtype)
        return current_costs, {"rewards": -current_costs}

    def fake_rollout(**kwargs):
        population = kwargs["noisy_action"]
        current_costs = costs.to(device=population.device, dtype=population.dtype)
        return population, current_costs, {"rewards": -current_costs}

    monkeypatch.setattr(
        stub_steer,
        "_eds_score_population_as_cost",
        fake_score_population_as_cost,
    )
    monkeypatch.setattr(
        stub_steer,
        "_eds_renoise_reference",
        lambda population, n_trunc_steps: population,
    )
    monkeypatch.setattr(stub_steer, "_eds_rollout_reference", fake_rollout)

    stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="eds",
        eds_config={
            "population_size": 4,
            "cem_iters": 2,
            "parent_weighting_mode": "adaptive_ess",
            "selection_ess_target_ratio": 0.5,
            "selection_beta_max": 100.0,
            "selection_bisection_steps": 24,
        },
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
    )

    metrics = stub_steer.get_last_eds_metrics()
    assert metrics["parent_weighting_mode"] == "adaptive_ess"
    assert len(metrics["per_iter"]) == 2
    for item in metrics["per_iter"]:
        assert item["selection_ess_ratio"] == pytest.approx(0.5, abs=0.03)
        assert item["selection_beta"] > 0.0
        assert item["selection_ess"] is not None
        assert item["selection_entropy_normalized"] is not None
        assert item["selection_max_probability"] is not None
        assert item["selection_degenerate_reward"] is False
    assert metrics["selection_beta_mean"] == pytest.approx(
        sum(item["selection_beta"] for item in metrics["per_iter"]) / 2.0
    )
    assert metrics["selection_ess_mean"] == pytest.approx(
        sum(item["selection_ess"] for item in metrics["per_iter"]) / 2.0
    )
    assert metrics["selection_ess_ratio_mean"] == pytest.approx(0.5, abs=0.03)
    assert metrics["selection_entropy_normalized_mean"] == pytest.approx(
        sum(item["selection_entropy_normalized"] for item in metrics["per_iter"])
        / 2.0
    )
    assert metrics["selection_max_probability_mean"] == pytest.approx(
        sum(item["selection_max_probability"] for item in metrics["per_iter"])
        / 2.0
    )
    assert metrics["selection_degenerate_reward_count"] == 0


@pytest.mark.parametrize(
    ("scores", "match"),
    [
        ([0.0, 1.0, 2.0], "torch.Tensor"),
        (torch.zeros(3, 1), "1-D"),
        (torch.zeros(2), "length"),
    ],
)
def test_eds_validate_population_scores_rejects_invalid_shape_or_length(
    stub_steer,
    scores,
    match,
):
    with pytest.raises(ValueError, match=match):
        stub_steer._eds_validate_population_scores(scores, expected_size=3)


@pytest.mark.parametrize("nonfinite", [float("nan"), float("inf"), float("-inf")])
def test_eds_rewards_from_info_rejects_nonfinite_rewards(stub_steer, nonfinite):
    costs = torch.tensor([0.0, 1.0, 2.0])
    rewards = torch.tensor([0.0, nonfinite, -2.0])

    with pytest.raises(ValueError, match="rewards must be finite"):
        stub_steer._eds_rewards_from_info(costs, {"rewards": rewards})


def test_eds_loop_cem_resamples_elites_then_renoises_and_rolls_out(
    stub_steer,
    stub_adapter,
    mock_batch,
    monkeypatch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"action_chunk_horizon": 4},
    )
    calls = []

    def fake_initial_population(*, x_t, cond, cfg):
        population = torch.zeros_like(x_t)
        markers = torch.arange(population.shape[0], device=population.device, dtype=population.dtype)
        population[:, :, 39] = markers[:, None]
        return population

    def fake_score_population_as_cost(
        samples,
        *,
        keypoints,
        guidance_fns,
        reward_mode="normal",
        shuffle_seed=0,
    ):
        costs = torch.tensor([3.0, 0.0, 1.0, 2.0], device=samples.device, dtype=samples.dtype)
        return costs, {"rewards": -costs}

    def fake_renoise(population, n_trunc_steps):
        markers = set(population[:, 0, 39].detach().cpu().tolist())
        calls.append(("renoise", n_trunc_steps, tuple(population.shape), markers))
        assert markers <= {1.0, 2.0}
        return population

    def fake_rollout(**kwargs):
        noisy = kwargs["noisy_action"]
        calls.append(("rollout", kwargs["n_trunc_steps"], tuple(noisy.shape)))
        costs = torch.arange(noisy.shape[0], device=noisy.device, dtype=noisy.dtype)
        return noisy, costs, {"rewards": -costs}

    monkeypatch.setattr(stub_steer, "_eds_initial_population", fake_initial_population)
    monkeypatch.setattr(stub_steer, "_eds_score_population_as_cost", fake_score_population_as_cost)
    monkeypatch.setattr(stub_steer, "_eds_renoise_reference", fake_renoise)
    monkeypatch.setattr(stub_steer, "_eds_rollout_reference", fake_rollout)

    action = stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="eds",
        eds_config={
            "population_size": 4,
            "cem_iters": 1,
            "use_cem": True,
            "num_elites": 2,
        },
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
    )

    assert tuple(action.shape) == (1, 4, 7)
    assert calls[0][0] == "renoise"
    assert calls[1][0] == "rollout"
    assert calls[0][1] == calls[1][1]
    metrics = stub_steer.get_last_eds_metrics()
    assert len(metrics["per_iter"]) == 1
    assert metrics["per_iter"][0]["selection_beta"] is None
    assert metrics["per_iter"][0]["selection_ess"] is None
    assert metrics["per_iter"][0]["selection_ess_ratio"] is None
    assert metrics["per_iter"][0]["selection_entropy_normalized"] is None
    assert metrics["per_iter"][0]["selection_max_probability"] is None
    assert metrics["selection_beta_mean"] is None
    assert metrics["selection_ess_mean"] is None
    assert metrics["selection_ess_ratio_mean"] is None
    assert metrics["selection_entropy_normalized_mean"] is None
    assert metrics["selection_max_probability_mean"] is None
    assert metrics["selection_degenerate_reward_count"] == 0


def test_eds_loop_caches_visualization_candidates_best_first(
    stub_steer,
    stub_adapter,
    mock_batch,
    monkeypatch,
    tmp_path,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"action_chunk_horizon": 4},
    )

    def fake_score(samples, keypoints, guidance_fns, slice_kind):
        return torch.tensor([1.0, 3.0, 2.0], device=samples.device, dtype=samples.dtype)

    def fake_rollout(**kwargs):
        noisy = kwargs["noisy_action"]
        population = torch.zeros_like(noisy)
        population[:, :, 39] = torch.tensor([10.0, 20.0, 30.0], device=noisy.device, dtype=noisy.dtype)[:, None]
        costs = -fake_score(population, kwargs["keypoints"], kwargs["guidance_fns"], "eds")
        return population, costs, {"rewards": -costs}

    def fake_decode(actions):
        candidates = torch.zeros(
            actions.shape[0],
            stub_steer._action_chunk_horizon,
            7,
            device=actions.device,
            dtype=actions.dtype,
        )
        candidates[:, :, 0] = actions[:, 0:1, 39]
        return candidates.detach()

    monkeypatch.setattr(stub_steer, "_score_particles", fake_score)
    monkeypatch.setattr(stub_steer, "_eds_rollout_reference", fake_rollout)
    monkeypatch.setattr(stub_steer, "_decode_visualization_action_candidates", fake_decode)
    ed_cache_path = tmp_path / "eds_population.pt"

    action = stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="eds",
        eds_config={
            "population_size": 3,
            "cem_iters": 1,
            "temperature": 0.1,
            "save_ed_cache": True,
            "ed_population_cache": str(ed_cache_path),
        },
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
    )
    candidates = stub_steer.get_last_visualization_action_candidates()

    assert tuple(action.shape) == (1, 4, 7)
    assert candidates is not None
    assert tuple(candidates.shape) == (3, 4, 7)
    torch.testing.assert_close(candidates[:, 0, 0], torch.tensor([20.0, 30.0, 10.0]))
    torch.testing.assert_close(action[0, :, 0], candidates[0, :, 0])
    saved = torch.load(ed_cache_path)
    assert tuple(saved["ed_population"].shape) == (3, 64, 128)
    torch.testing.assert_close(
        torch.sort(saved["ed_population"][:, 0, 39]).values,
        torch.tensor([10.0, 20.0, 30.0]),
    )


def test_eds_loop_records_deployment_counters(stub_steer, stub_adapter, mock_batch):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )

    stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="eds",
        eds_config={"population_size": 3, "cem_iters": 2, "temperature": 0.1},
        guidance_fns=[lambda keypoints, traj: torch.sum(traj[:, -1, 0])],
        keypoints=np.array([[0.0, 0.0, 0.0]], dtype=np.float32),
    )

    metrics = stub_steer.get_last_eds_metrics()
    artifacts = stub_steer.get_last_eds_artifacts()

    assert metrics is not None
    assert metrics["eds_enter_count"] == 1
    assert metrics["score_call_count"] == 3
    assert metrics["resample_count"] == 2
    assert metrics["renoise_count"] == 2
    assert metrics["rollout_count"] == 2
    assert metrics["population_shape"] == [3, 64, 128]
    assert metrics["score_shape"] == [3]
    assert metrics["population_size_observed"] == 3
    assert metrics["nonfinite_count"] == 0
    assert metrics["selected_idx"] == int(torch.argmin(artifacts["final_scores"]).item())


def test_eds_loop_records_initial_sampler_metrics(
    stub_steer, stub_adapter, mock_batch, monkeypatch
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )

    def fake_diversity(x_t):
        grad = torch.zeros_like(x_t)
        grad[:, :4, 39] = torch.tensor([0.0, 1.0, -1.0]).view(3, 1)
        return grad

    monkeypatch.setattr(stub_steer, "_compute_diversity_gradient", fake_diversity)

    stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="eds",
        eds_config={
            "population_size": 3,
            "cem_iters": 1,
            "temperature": 0.1,
            "initial_sampling_mode": "rbf_diverse_denoise",
            "initial_diversity_scale": 1.0,
        },
        guidance_fns=[lambda keypoints, traj: torch.sum(traj[:, -1, 0])],
        keypoints=np.array([[0.0, 0.0, 0.0]], dtype=np.float32),
    )

    metrics = stub_steer.get_last_eds_metrics()

    assert metrics["initial_sampling_mode"] == "rbf_diverse_denoise"
    assert metrics["initial_diversity_steps"] > 0
    assert metrics["initial_diversity_fallback_used"] is False
    assert metrics["initial_sampler_latency_s"] is not None


def test_eds_loop_tolerates_malformed_initial_sampler_metrics(
    stub_steer, stub_adapter, mock_batch, monkeypatch
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )

    def fake_initial_population(*, x_t, cond, cfg):
        stub_steer._last_eds_initial_sampler_info = {
            "initial_sampling_mode": "bogus",
            "initial_diversity_scale": "bad",
            "initial_diversity_start_ratio": float("nan"),
            "initial_diversity_steps": None,
            "initial_diversity_grad_failure_count": "bad",
            "initial_diversity_grad_norm_mean": "bad",
            "initial_diversity_grad_norm_max": float("nan"),
            "initial_diversity_fallback_used": 10**10000,
            "initial_sampler_latency_s": "bad",
        }
        return x_t

    monkeypatch.setattr(stub_steer, "_eds_initial_population", fake_initial_population)

    stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="eds",
        eds_config={
            "population_size": 3,
            "cem_iters": 1,
            "temperature": 0.1,
            "initial_sampling_mode": "rbf_diverse_denoise",
        },
        guidance_fns=[lambda keypoints, traj: torch.sum(traj[:, -1, 0])],
        keypoints=np.array([[0.0, 0.0, 0.0]], dtype=np.float32),
    )

    metrics = stub_steer.get_last_eds_metrics()

    assert metrics["initial_sampling_mode"] == "rbf_diverse_denoise"
    assert metrics["initial_diversity_scale"] is None
    assert metrics["initial_diversity_start_ratio"] is None
    assert metrics["initial_diversity_steps"] == 0
    assert metrics["initial_diversity_grad_failure_count"] == 0
    assert metrics["initial_diversity_grad_norm_mean"] is None
    assert metrics["initial_diversity_grad_norm_max"] is None
    assert metrics["initial_diversity_fallback_used"] is False
    assert metrics["initial_sampler_latency_s"] is None


def test_eds_zero_reward_records_no_reward_spread(stub_steer, stub_adapter, mock_batch):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )

    stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="eds",
        eds_config={
            "population_size": 3,
            "cem_iters": 1,
            "temperature": 0.1,
            "reward_mode": "zero",
        },
        guidance_fns=[lambda keypoints, traj: torch.sum(traj[:, -1, 0])],
        keypoints=np.array([[0.0, 0.0, 0.0]], dtype=np.float32),
    )

    metrics = stub_steer.get_last_eds_metrics()

    assert metrics is not None
    assert metrics["reward_mode"] == "zero"
    assert metrics["initial_best_reward"] == 0.0
    assert metrics["final_best_reward"] == 0.0
    assert metrics["reward_spread"] == 0.0


def test_eds_artifacts_are_decoded_action_candidates(stub_steer, stub_adapter, mock_batch):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )

    stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="eds",
        eds_config={"population_size": 3, "cem_iters": 1, "temperature": 0.1},
        guidance_fns=[lambda keypoints, traj: torch.sum(traj[:, -1, 0])],
        keypoints=np.array([[0.0, 0.0, 0.0]], dtype=np.float32),
    )

    artifacts = stub_steer.get_last_eds_artifacts()

    assert artifacts is not None
    assert tuple(artifacts["initial_actions"].shape) == (3, 4, 7)
    assert tuple(artifacts["final_actions"].shape) == (3, 4, 7)
    assert tuple(artifacts["final_scores"].shape) == (3,)
    assert artifacts["initial_actions"].shape[-1] == 7
    assert artifacts["final_actions"].shape[-1] != 128
    assert len(artifacts["per_iter"]) == 1
    assert tuple(artifacts["per_iter"][0]["actions"].shape) == (3, 4, 7)
    assert tuple(artifacts["per_iter"][0]["scores"].shape) == (3,)


def test_eds_mechanism_pretest_trace_records_single_step_stages(
    stub_steer, stub_adapter, mock_batch
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 8},
    )

    stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="eds",
        keypoints=np.zeros((1, 3), dtype=np.float32),
        guidance_fns=[
            lambda keypoints, traj: -torch.linalg.norm(
                traj[:, -1, :3] - keypoints[0, :3],
                dim=-1,
            ).sum()
        ],
        eds_config={
            "population_size": 3,
            "cem_iters": 2,
            "temperature": 0.1,
            "mechanism_pretest": {
                "enabled": True,
                "first_chunk_only": True,
                "save_single_step": True,
                "save_full_process": True,
                "save_tensors": True,
                "plot_3d": False,
                "max_full_process_iters": 2,
            },
        },
        global_step=0,
    )

    trace = stub_steer.get_last_eds_mechanism_trace()

    assert trace is not None
    assert trace.global_step == 0
    assert trace.population_size == 3
    assert trace.reward_mode == "normal"
    assert {stage.stage for stage in trace.stages} >= {
        "initial",
        "scored",
        "resampled",
        "renoised",
        "after_rollout",
    }
    resampled = next(stage for stage in trace.stages if stage.stage == "resampled")
    assert resampled.parent_indices is not None
    assert resampled.parent_ranks is not None
    assert tuple(resampled.parent_ranks.shape) == (3,)


def test_eds_mechanism_pretest_first_chunk_only_skips_later_chunks(
    stub_steer, stub_adapter, mock_batch
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 8},
    )

    stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="eds",
        keypoints=np.zeros((1, 3), dtype=np.float32),
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        eds_config={
            "population_size": 3,
            "cem_iters": 1,
            "temperature": 0.1,
            "mechanism_pretest": {"enabled": True, "first_chunk_only": True},
        },
        global_step=8,
    )

    assert stub_steer.get_last_eds_mechanism_trace() is None


def test_eds_infers_scoring_keypoint_index_from_guidance_source(stub_steer):
    def guidance(keypoints, trajectory):
        return trajectory[..., 0].sum()

    guidance._guidance_source_text = """
def stage1_guidance(keypoints, action_sequence):
    target_idx = torch.tensor([2], dtype=torch.long, device=keypoints.device)
    target_pos = keypoints[target_idx][0]
    return -torch.norm(action_sequence - target_pos, dim=-1).mean()
"""

    indices = stub_steer._eds_infer_scoring_keypoint_indices(
        [guidance],
        torch.zeros(4, 3),
    )

    assert indices == [2]


def test_rdt_guidance_type_invalid_raises_clear_error(stub_steer, stub_adapter, mock_batch):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"action_chunk_horizon": 4},
    )

    with pytest.raises(ValueError, match="Unsupported RDT guidance_type"):
        stub_steer.select_action(
            mock_batch,
            generate_new_chunk=True,
            use_guidance=True,
            guidance_type="bad",
            guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
            keypoints=np.zeros((3, 3), dtype=np.float32),
        )


def test_integrated_guided_select_action_with_diversity_fkd_and_selection(
    stub_steer,
    stub_adapter,
    mock_batch,
    monkeypatch,
):
    diversity_calls = []
    fkd_inits = []
    selection_shapes = []
    original_diversity = stub_steer._compute_diversity_gradient
    original_init_fkd = stub_steer._init_fkd
    original_select = stub_steer._select_particle_for_execution

    def spy_diversity(x_t):
        diversity_calls.append(tuple(x_t.shape))
        return original_diversity(x_t)

    def spy_init_fkd(**kwargs):
        fkd = original_init_fkd(**kwargs)
        fkd_inits.append((kwargs["B"], fkd is not None))
        return fkd

    def spy_select(samples, *, keypoints, guidance_fns, fkd):
        selected = original_select(samples, keypoints=keypoints, guidance_fns=guidance_fns, fkd=fkd)
        selection_shapes.append((tuple(samples.shape), tuple(selected.shape), fkd is not None))
        return selected

    monkeypatch.setattr(stub_steer, "_compute_diversity_gradient", spy_diversity)
    monkeypatch.setattr(stub_steer, "_init_fkd", spy_init_fkd)
    monkeypatch.setattr(stub_steer, "_select_particle_for_execution", spy_select)
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 4},
    )
    action = stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="vls",
        vls_config={
            "sample_batch_size": 4,
            "guide_scale": 1.0,
            "use_diversity": True,
            "diversity_scale": 1.0,
            "use_fkd": True,
            "fkd": {
                "potential_type": "max",
                "lmbda": 1.0,
                "adaptive_resampling": False,
                "resample_frequency": 1,
            },
        },
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
    )

    assert tuple(action.shape) == (1, 4, 7)
    assert torch.isfinite(action).all()
    assert stub_steer.get_last_scale() >= 0.0
    assert diversity_calls
    assert diversity_calls[-1] == (4, 64, 128)
    assert fkd_inits and fkd_inits[-1] == (4, True)
    assert selection_shapes and selection_shapes[-1] == ((4, 64, 128), (1, 64, 128), True)


def test_guided_loop_applies_diversity_before_keypoint_phase(stub_steer, stub_adapter, mock_batch, monkeypatch):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    initial_sample = _deterministic_diversity_sample()
    expected_grad = stub_steer._mask_guidance_gradient(
        stub_steer._compute_diversity_gradient(initial_sample)
    )

    def deterministic_randn(*shape, **kwargs):
        assert shape == (3, 64, 128)
        return initial_sample.to(
            device=kwargs.get("device", initial_sample.device),
            dtype=kwargs.get("dtype", initial_sample.dtype),
        ).clone()

    monkeypatch.setattr(torch, "randn", deterministic_randn)

    action = stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="vls",
        vls_config={
            "sample_batch_size": 3,
            "use_diversity": True,
            "diversity_scale": 1.0,
        },
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
    )

    assert tuple(action.shape) == (1, 4, 7)
    assert stub_steer._rdt_model.dit.calls
    first_model_output, first_t = stub_steer._rdt_model.noise_scheduler.last_step_args[0]
    assert first_t == 4
    assert first_model_output[:, :4, [39, 40, 41]].abs().sum() > 0
    inactive = first_model_output.clone()
    inactive[:, :, [39, 40, 41]] = 0
    assert inactive.abs().sum() == 0
    torch.testing.assert_close(
        first_model_output[:, :4, [39, 40, 41]],
        -expected_grad[:, :4, [39, 40, 41]],
    )


def test_guided_denoise_loop_raises_on_nonfinite_latent_before_selection(
    stub_steer,
    stub_adapter,
    mock_batch,
    monkeypatch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=1,
        policy_config={"action_chunk_horizon": 4},
    )

    def inf_step(model_output, t, x_t):
        out = MagicMock()
        out.prev_sample = torch.full_like(x_t, float("inf"))
        out.pred_original_sample = None
        return out

    def fail_select(*args, **kwargs):
        raise AssertionError("selection should not run with a non-finite guided latent")

    monkeypatch.setattr(stub_steer._noise_scheduler, "step", inf_step)
    monkeypatch.setattr(stub_steer, "_select_particle_for_execution", fail_select)

    with pytest.raises(ValueError, match="Guided RDT latent contains non-finite values"):
        stub_steer.select_action(
            mock_batch,
            generate_new_chunk=True,
            use_guidance=True,
            guidance_type="vls",
            vls_config={"sample_batch_size": 1, "use_diversity": False},
        )


def test_guided_loop_calls_fkd_resample_when_enabled(stub_steer, stub_adapter, mock_batch, monkeypatch):
    init_kwargs = []
    calls = []

    class _SpyFKD:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.reached_terminal = False
            init_kwargs.append(kwargs)

        def resample(self, *, sampling_idx, latents, x0_preds):
            calls.append({
                "sampling_idx": sampling_idx,
                "latents_shape": tuple(latents.shape),
                "x0_shape": tuple(x0_preds.shape),
                "latents_dtype": latents.dtype,
                "x0_dtype": x0_preds.dtype,
            })
            return latents, None

    monkeypatch.setattr("core.rdt_policy_steer.FKD", _SpyFKD)
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )

    action = stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="vls",
        vls_config={
            "sample_batch_size": 3,
            "use_diversity": False,
            "use_fkd": True,
            "fkd": {
                "potential_type": "max",
                "lmbda": 1.0,
                "adaptive_resampling": False,
                "resample_frequency": 1,
            },
        },
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
    )

    assert tuple(action.shape) == (1, 4, 7)
    assert len(init_kwargs) == 1
    assert init_kwargs[0]["num_particles"] == 3
    assert init_kwargs[0]["resampling_t_start"] == 3
    terminal_t = int(stub_steer._noise_scheduler.timesteps[-1].item())
    assert init_kwargs[0]["resampling_t_end"] == terminal_t
    assert calls
    assert all(call["sampling_idx"] <= 3 for call in calls)
    assert all(call["sampling_idx"] != terminal_t for call in calls)
    assert all(call["latents_shape"] == (3, 64, 128) for call in calls)
    assert all(call["x0_shape"] == (3, 64, 128) for call in calls)
    assert all(call["latents_dtype"] == torch.float32 for call in calls)
    assert all(call["x0_dtype"] == torch.float32 for call in calls)


def test_guided_loop_caches_visualization_candidates(stub_steer, stub_adapter, mock_batch):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )

    action = stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="vls",
        vls_config={"sample_batch_size": 3, "use_diversity": False, "use_fkd": False},
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
    )

    candidates = stub_steer.get_last_visualization_action_candidates()

    assert tuple(action.shape) == (1, 4, 7)
    assert candidates is not None
    assert tuple(candidates.shape) == (3, 4, 7)
    candidates.add_(1.0)
    fresh_candidates = stub_steer.get_last_visualization_action_candidates()
    assert fresh_candidates is not None
    assert not torch.equal(candidates, fresh_candidates)


def test_visualization_particles_are_ordered_with_best_first(stub_steer, stub_adapter, monkeypatch):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    samples = torch.zeros(3, 64, 128, dtype=torch.float32)
    samples[0, :, 39] = 10.0
    samples[1, :, 39] = 20.0
    samples[2, :, 39] = 30.0

    monkeypatch.setattr(
        stub_steer,
        "_score_particles",
        lambda *args, **kwargs: torch.tensor([0.0, 3.0, 1.0]),
    )

    ordered = stub_steer._order_particles_for_visualization(
        samples,
        keypoints=None,
        guidance_fns=None,
        fkd=None,
    )

    torch.testing.assert_close(ordered[0], samples[1])
    torch.testing.assert_close(ordered[1], samples[0])
    torch.testing.assert_close(ordered[2], samples[2])


def test_guided_loop_real_fkd_resample_resets_scheduler_history(stub_steer, stub_adapter, mock_batch, monkeypatch):
    reset_calls = []
    original_reset = stub_steer._reset_scheduler_particle_history_after_resample

    def spy_reset(scheduler):
        if getattr(scheduler, "last_step_args", None):
            reset_calls.append(scheduler.last_step_args[-1][1])
        elif hasattr(scheduler, "timesteps"):
            step_index = getattr(scheduler, "_step_index", 0)
            reset_calls.append(int(scheduler.timesteps[step_index].item()))
        else:
            reset_calls.append(None)
        original_reset(scheduler)

    monkeypatch.setattr(stub_steer, "_reset_scheduler_particle_history_after_resample", spy_reset)
    torch.manual_seed(0)
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    scheduler = stub_steer._noise_scheduler
    scheduler.model_outputs = [torch.ones(3, 64, 128), torch.ones(3, 64, 128) * 2]
    scheduler.lower_order_nums = 2

    action = stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="vls",
        vls_config={
            "sample_batch_size": 3,
            "use_diversity": False,
            "use_fkd": True,
            "fkd": {
                "potential_type": "max",
                "lmbda": 1.0,
                "adaptive_resampling": False,
                "resample_frequency": 1,
            },
        },
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
    )

    terminal_t = int(stub_steer._noise_scheduler.timesteps[-1].item())
    assert tuple(action.shape) == (1, 4, 7)
    assert reset_calls
    assert terminal_t not in reset_calls
    assert scheduler.model_outputs == [None, None]
    assert scheduler.lower_order_nums == 0


def test_guided_loop_does_not_reset_scheduler_history_when_fkd_noops(
    stub_steer,
    stub_adapter,
    mock_batch,
    monkeypatch,
):
    calls = []

    class _NoopFKD:
        def __init__(self, **kwargs):
            self.reached_terminal = False

        def resample(self, *, sampling_idx, latents, x0_preds):
            calls.append(sampling_idx)
            return latents, None

    monkeypatch.setattr("core.rdt_policy_steer.FKD", _NoopFKD)
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    scheduler = stub_steer._noise_scheduler
    scheduler.model_outputs = [torch.ones(3, 64, 128), torch.ones(3, 64, 128) * 2]
    scheduler.lower_order_nums = 2
    scheduler._step_index = 99

    stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="vls",
        vls_config={
            "sample_batch_size": 3,
            "use_diversity": False,
            "use_fkd": True,
            "fkd": {
                "potential_type": "max",
                "lmbda": 1.0,
                "adaptive_resampling": False,
                "resample_frequency": 1,
            },
        },
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
    )

    assert calls
    assert scheduler.model_outputs[0] is not None
    assert scheduler.model_outputs[1] is not None
    assert scheduler.lower_order_nums == 2
    assert scheduler._step_index == 99


def test_fkd_resample_resets_multistep_scheduler_history(stub_steer):
    class _StatefulScheduler:
        def __init__(self):
            self.model_outputs = [torch.ones(2, 64, 128), torch.ones(2, 64, 128) * 2]
            self.lower_order_nums = 2
            self._step_index = 3

    scheduler = _StatefulScheduler()

    stub_steer._reset_scheduler_particle_history_after_resample(scheduler)

    assert scheduler.model_outputs == [None, None]
    assert scheduler.lower_order_nums == 0
    assert scheduler._step_index == 3


def test_rdt_guidance_trajectory_preserves_particle_batch(stub_steer, stub_adapter):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    sample = torch.zeros(3, 64, 128, dtype=torch.float32)
    sample[0, :4, 39] = 1.0
    sample[1, :4, 40] = 2.0
    sample[2, :4, 41] = 3.0

    traj = stub_steer._rdt_sample_to_trajectory_3d(sample)

    assert tuple(traj.shape) == (3, 5, 3)
    torch.testing.assert_close(traj[0, -1], torch.tensor([4.0, 0.0, 0.0]))
    torch.testing.assert_close(traj[1, -1], torch.tensor([0.0, 8.0, 0.0]))
    torch.testing.assert_close(traj[2, -1], torch.tensor([0.0, 0.0, 12.0]))


def test_rdt_guidance_trajectory_gradients_flow_to_translation_slots(stub_steer, stub_adapter):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"action_chunk_horizon": 4},
    )
    sample = torch.zeros(2, 64, 128, dtype=torch.float32, requires_grad=True)

    traj = stub_steer._rdt_sample_to_trajectory_3d(sample)
    reward = traj[:, :, 0].sum()
    grad = torch.autograd.grad(reward, sample)[0]

    assert grad[:, :4, 39].abs().sum() > 0
    assert grad[:, :4, 40].abs().sum() == 0
    assert grad[:, :4, 41].abs().sum() == 0
    inactive = grad.clone()
    inactive[:, :, [39, 40, 41]] = 0
    assert inactive.abs().sum() == 0


def test_rdt_guidance_sign_moves_positive_x_reward_up(stub_steer, stub_adapter):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=1,
        policy_config={"action_chunk_horizon": 4},
    )
    model_output = torch.zeros(1, 64, 128)
    grad = torch.zeros_like(model_output)
    grad[:, :4, 39] = 1.0

    guided = stub_steer._apply_keypoint_guidance(model_output, grad, scale=torch.tensor(0.5))

    assert guided[:, :4, 39].sum() > model_output[:, :4, 39].sum()
    assert guided[:, :4, 40].abs().sum() == 0
    assert guided[:, :4, 42].abs().sum() == 0
    assert guided[:, :4, 10].abs().sum() == 0


def test_keypoint_gradient_uses_diffusion_policy_slice_and_masks_slots(stub_steer, stub_adapter):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"action_chunk_horizon": 4},
    )
    sample = torch.zeros(2, 64, 128)

    def reward_fn(keypoints, traj):
        assert tuple(traj.shape) == (2, 4, 3)
        return traj[..., 0].sum()

    grad, reward = stub_steer._compute_keypoint_gradient(
        sample,
        torch.zeros(3, 3),
        [reward_fn],
    )

    assert reward == 0.0
    assert grad is not None
    assert grad[:, :4, 39].abs().sum() > 0
    masked = stub_steer._mask_guidance_gradient(grad)
    assert masked[:, :4, 39].abs().sum() > 0
    assert masked[:, :4, 40].abs().sum() == 0
    assert masked[:, :4, 42].abs().sum() == 0
    assert masked[:, :4, 10].abs().sum() == 0


def test_nonfinite_keypoint_gradient_warns_and_returns_none(stub_steer, stub_adapter, monkeypatch):
    warnings = []
    monkeypatch.setattr(
        "core.rdt_policy_steer.log.warning",
        lambda msg, *args, **kwargs: warnings.append(str(msg)),
    )
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=1,
        policy_config={"action_chunk_horizon": 4},
    )
    sample = torch.zeros(1, 64, 128)

    def reward_fn(keypoints, traj):
        return traj[..., 0].sum() / traj.new_tensor(0.0)

    grad, reward = stub_steer._compute_keypoint_gradient(
        sample,
        torch.zeros(3, 3),
        [reward_fn],
    )

    assert grad is None
    assert not np.isfinite(reward)
    assert any("non-finite" in msg.lower() and "reward=" in msg.lower() for msg in warnings)


def test_diversity_gradient_preserves_shape_and_translation_mask(stub_steer, stub_adapter):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    sample = _deterministic_diversity_sample()

    grad = stub_steer._compute_diversity_gradient(sample)
    assert grad is not None
    assert tuple(grad.shape) == (3, 64, 128)

    masked = stub_steer._mask_guidance_gradient(grad)
    assert masked[:, :4, [39, 40, 41]].abs().sum() > 0
    outside = masked.clone()
    outside[:, :, [39, 40, 41]] = 0
    assert outside.abs().sum() == 0

    step_size = 0.05
    base_spread = _trajectory_spread(stub_steer, sample)
    negative_step_spread = _trajectory_spread(stub_steer, sample - step_size * masked)
    positive_step_spread = _trajectory_spread(stub_steer, sample + step_size * masked)
    assert negative_step_spread > base_spread
    assert negative_step_spread > positive_step_spread


def test_parameterless_stub_tracks_requested_device(stub_steer):
    assert stub_steer.device == torch.device("cpu")

    stub_steer.to("meta")

    assert stub_steer.device == torch.device("meta")


def test_weight_search_dirs_include_nested_variant_and_are_deduped(tmp_path):
    from core.rdt_policy_steer import _rdt_weight_search_dirs

    dirs = _rdt_weight_search_dirs(str(tmp_path), "ema")

    assert dirs == [
        str(tmp_path / "ema"),
        str(tmp_path / "rdt" / "ema"),
        str(tmp_path),
        str(tmp_path / "rdt"),
    ]
    assert len(dirs) == len(set(dirs))


def test_resolve_rdt_weight_file_prefers_root_variant_safetensors(tmp_path):
    from core.rdt_policy_steer import _resolve_rdt_weight_file

    root = tmp_path / "RDT-1B-LIBERO-Object"
    ema = root / "ema"
    ema.mkdir(parents=True)
    weight = ema / "model.safetensors"
    weight.write_bytes(b"stub")

    resolved, checkpoint_root = _resolve_rdt_weight_file(str(root), "ema")

    assert resolved == str(weight)
    assert checkpoint_root == str(root)


def test_resolve_rdt_checkpoint_paths_returns_root_then_weight(tmp_path):
    from core.rdt_policy_steer import _resolve_rdt_checkpoint_paths

    root = tmp_path / "RDT-1B-LIBERO-Object"
    ema = root / "ema"
    ema.mkdir(parents=True)
    weight = ema / "model.safetensors"
    weight.write_bytes(b"stub")

    checkpoint_root, resolved = _resolve_rdt_checkpoint_paths(str(root), "ema")

    assert checkpoint_root == str(root)
    assert resolved == str(weight)


def test_resolve_rdt_weight_file_accepts_direct_safetensors(tmp_path):
    from core.rdt_policy_steer import _resolve_rdt_weight_file

    weight = tmp_path / "model.safetensors"
    weight.write_bytes(b"stub")

    resolved, checkpoint_root = _resolve_rdt_weight_file(str(weight), "ema")

    assert resolved == str(weight)
    assert checkpoint_root == str(tmp_path)


def test_from_pretrained_logs_resolved_checkpoint_before_model_import(monkeypatch, tmp_path):
    import core.rdt_policy_steer as rdt_policy_steer

    RDTSteer = rdt_policy_steer.RDTSteer
    warning_messages = []
    monkeypatch.setattr(rdt_policy_steer.log, "warning", warning_messages.append)

    root = tmp_path / "RDT-1B-LIBERO-Object"
    ema = root / "ema"
    ema.mkdir(parents=True)
    weight = ema / "model.safetensors"
    weight.write_bytes(b"stub")

    real_import = __import__

    def _fail_yaml_import(name, *args, **kwargs):
        if name == "yaml":
            raise ImportError("stop before heavyweight model import")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _fail_yaml_import)

    with pytest.raises(ImportError, match="RoboticDiffusionTransformerModel"):
        RDTSteer.from_pretrained(str(root), weight_variant="ema")

    output = "\n".join(warning_messages)
    assert "[RDT_GT_CKPT]" in output
    assert f"model_root={root}" in output
    assert f"weight_file={weight}" in output
    assert "variant=ema" in output


def test_from_pretrained_missing_absolute_path_fails_without_snapshot_download(monkeypatch, tmp_path):
    from core.rdt_policy_steer import RDTSteer

    calls = []
    hub_module = ModuleType("huggingface_hub")

    def _snapshot_download(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("snapshot_download should not be called for missing local paths")

    hub_module.snapshot_download = _snapshot_download
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub_module)

    missing_root = tmp_path / "missing_rdt_root"
    with pytest.raises(FileNotFoundError, match="Missing RDT checkpoint path"):
        RDTSteer.from_pretrained(str(missing_root), weight_variant="ema")

    assert calls == []


def test_model_adapter_encode_inputs_appends_gt_action_mask_tokens():
    from core.rdt_policy_steer import _RDTModelAdapter

    class _FakeImageProcessor:
        image_mean = [0.5, 0.5, 0.5]
        size = {"height": 8, "width": 8}

        def preprocess(self, img, return_tensors):
            assert return_tensors == "pt"
            return {"pixel_values": torch.zeros(1, 3, 8, 8)}

    class _FakeVision(nn.Module):
        hidden_size = 1152

        def forward(self, image_tensor):
            return torch.zeros(image_tensor.shape[0], 1, self.hidden_size)

    class _FakePolicy(nn.Module):
        def __init__(self):
            super().__init__()
            self.noise_scheduler_sample = _StubScheduler()
            self.captured_state_tokens = None

        def adapt_conditions(self, text_embeds, image_embeds, state_tokens):
            self.captured_state_tokens = state_tokens.detach().clone()
            return (
                torch.zeros(1, 1, 4),
                torch.zeros(1, 1, 4),
                torch.zeros(1, 1, 4),
            )

    class _FakeReal:
        def __init__(self):
            self.device = torch.device("cpu")
            self.dtype = torch.float32
            self.image_processor = _FakeImageProcessor()
            self.image_size = None
            self.args = {
                "dataset": {"image_aspect_ratio": "pad"},
                "model": {"state_token_dim": 128},
            }
            self.vision_model = _FakeVision()
            self.text_model = nn.Identity()
            self.policy = _FakePolicy()
            self.control_frequency = 20

    real = _FakeReal()
    adapter = _RDTModelAdapter(real)
    state_128 = torch.zeros(1, 128)
    state_mask_128 = torch.zeros(1, 128)
    state_mask_128[0, [0, 1, 2, 3, 4, 5, 6, 10, 11]] = 1.0
    images = [Image.fromarray(_image(1, 2, 3)) for _ in range(6)]

    cond = adapter.encode_inputs(state_128, state_mask_128, images, torch.ones(1, 1, 4096))

    captured = real.policy.captured_state_tokens
    assert captured is not None
    assert tuple(captured.shape) == (1, 1, 256)
    appended_mask = captured[0, 0, 128:]
    assert torch.where(appended_mask > 0)[0].tolist() == [10, 39, 40, 41, 42, 43, 44]
    assert cond["action_indices"] == [39, 40, 41, 42, 43, 44, 10]
    assert torch.where(cond["action_mask"][0, 0] > 0)[0].tolist() == [10, 39, 40, 41, 42, 43, 44]


def test_model_adapter_encode_inputs_does_not_emit_unconditional_io_summary(monkeypatch):
    import core.rdt_policy_steer as rdt_policy_steer

    _RDTModelAdapter = rdt_policy_steer._RDTModelAdapter
    warning_messages = []
    monkeypatch.setattr(rdt_policy_steer.log, "warning", warning_messages.append)

    class _FakeImageProcessor:
        image_mean = [0.5, 0.5, 0.5]
        size = {"height": 8, "width": 8}

        def preprocess(self, img, return_tensors):
            assert return_tensors == "pt"
            return {"pixel_values": torch.zeros(1, 3, 8, 8)}

    class _FakeVision(nn.Module):
        hidden_size = 1152

        def forward(self, image_tensor):
            return torch.zeros(image_tensor.shape[0], 1, self.hidden_size)

    class _FakePolicy(nn.Module):
        def __init__(self):
            super().__init__()
            self.noise_scheduler_sample = _StubScheduler()

        def adapt_conditions(self, text_embeds, image_embeds, state_tokens):
            return (
                torch.zeros(1, 1, 4),
                torch.zeros(1, 1, 4),
                torch.zeros(1, 1, 4),
            )

    class _FakeReal:
        def __init__(self):
            self.device = torch.device("cpu")
            self.dtype = torch.float32
            self.image_processor = _FakeImageProcessor()
            self.image_size = None
            self.args = {
                "dataset": {"image_aspect_ratio": "pad"},
                "model": {"state_token_dim": 128},
            }
            self.vision_model = _FakeVision()
            self.text_model = nn.Identity()
            self.policy = _FakePolicy()
            self.control_frequency = 20

    adapter = _RDTModelAdapter(_FakeReal())
    state_128 = torch.zeros(1, 128)
    state_mask_128 = torch.zeros(1, 128)
    state_mask_128[0, [0, 1, 2, 3, 4, 5, 6, 10, 11]] = 1.0
    images = [Image.fromarray(_image(1, 2, 3)) for _ in range(6)]

    adapter.encode_inputs(state_128, state_mask_128, images, torch.ones(1, 1, 4096))
    adapter.encode_inputs(state_128, state_mask_128, images, torch.ones(1, 1, 4096))

    output = "\n".join(warning_messages)
    assert "[RDT_GT_IO]" not in output


def test_postprocess_actions_logs_numeric_summary_only_when_debug_enabled(stub_steer, monkeypatch):
    import core.rdt_policy_steer as rdt_policy_steer

    info_messages = []
    monkeypatch.setattr(rdt_policy_steer.log, "info", info_messages.append)
    stub_steer._action_chunk_horizon = 2
    actions = torch.zeros(1, 64, 128)
    actions[0, :, [39, 40, 41, 42, 43, 44, 10]] = torch.tensor(
        [0.1, -0.2, 0.3, -0.4, 0.5, -0.6, 1.0]
    )

    decoded = stub_steer._postprocess_actions(actions)

    assert "[RDT_GT_ACTION]" not in "\n".join(info_messages)

    stub_steer._debug_first_step = True
    decoded = stub_steer._postprocess_actions(actions)

    output = "\n".join(info_messages)
    assert "[RDT_GT_ACTION]" in output
    assert "shape=(1, 2, 7)" in output
    assert "min=" in output
    assert "max=" in output
    assert f"first_decoded_action={decoded[0, 0].detach().cpu().tolist()}" in output


def test_text_encoder_cache_root_normalizes_to_model_id():
    from core.rdt_policy_steer import _normalize_text_encoder_path

    assert _normalize_text_encoder_path("google/t5-v1_1-xxl") == "google/t5-v1_1-xxl"


def test_text_encoder_cache_root_resolves_snapshot(tmp_path):
    from core.rdt_policy_steer import _normalize_text_encoder_path

    cache_root = tmp_path / "models--google--t5-v1_1-xxl"
    valid_snapshot = cache_root / "snapshots" / "abc123"
    valid_snapshot.mkdir(parents=True)
    (valid_snapshot / "config.json").write_text("{}", encoding="utf-8")

    assert _normalize_text_encoder_path(str(cache_root)) == str(valid_snapshot)


def test_rdt_text_encoder_arg_preserves_gt_model_id_with_local_snapshot(tmp_path):
    from core.rdt_policy_steer import _rdt_text_encoder_arg_and_load_path

    cache_root = tmp_path / "models--google--t5-v1_1-xxl"
    valid_snapshot = cache_root / "snapshots" / "abc123"
    valid_snapshot.mkdir(parents=True)
    (valid_snapshot / "config.json").write_text("{}", encoding="utf-8")

    model_arg, load_path = _rdt_text_encoder_arg_and_load_path(str(cache_root))

    assert model_arg == "google/t5-v1_1-xxl"
    assert load_path == str(valid_snapshot)


def test_text_encoder_tilde_cache_root_expands_before_snapshot_resolution(monkeypatch, tmp_path):
    from core.rdt_policy_steer import _normalize_text_encoder_path

    monkeypatch.setenv("HOME", str(tmp_path))
    cache_root = tmp_path / "models--google--t5-v1_1-xxl"
    valid_snapshot = cache_root / "snapshots" / "abc123"
    valid_snapshot.mkdir(parents=True)
    (valid_snapshot / "config.json").write_text("{}", encoding="utf-8")

    assert _normalize_text_encoder_path("~/models--google--t5-v1_1-xxl") == str(valid_snapshot)


def test_text_encoder_local_tilde_path_expands_before_return(monkeypatch, tmp_path):
    from core.rdt_policy_steer import _normalize_text_encoder_path

    monkeypatch.setenv("HOME", str(tmp_path))
    local_encoder = tmp_path / "encoders" / "custom-t5"
    local_encoder.mkdir(parents=True)

    assert _normalize_text_encoder_path("~/encoders/custom-t5") == str(local_encoder)


def test_vision_encoder_cache_root_resolves_snapshot(tmp_path):
    from core.rdt_policy_steer import _resolve_vision_encoder_path

    cache_root = tmp_path / "models--google--siglip-so400m-patch14-384"
    valid_snapshot = cache_root / "snapshots" / "abc123"
    valid_snapshot.mkdir(parents=True)
    (valid_snapshot / "config.json").write_text("{}", encoding="utf-8")
    (valid_snapshot / "preprocessor_config.json").write_text("{}", encoding="utf-8")

    assert _resolve_vision_encoder_path(str(cache_root)) == str(valid_snapshot)
    assert _resolve_vision_encoder_path("google/siglip-so400m-patch14-384") == "google/siglip-so400m-patch14-384"


def test_vision_encoder_tilde_cache_root_expands_before_snapshot_resolution(monkeypatch, tmp_path):
    from core.rdt_policy_steer import _resolve_vision_encoder_path

    monkeypatch.setenv("HOME", str(tmp_path))
    cache_root = tmp_path / "models--google--siglip-so400m-patch14-384"
    valid_snapshot = cache_root / "snapshots" / "abc123"
    valid_snapshot.mkdir(parents=True)
    (valid_snapshot / "config.json").write_text("{}", encoding="utf-8")
    (valid_snapshot / "preprocessor_config.json").write_text("{}", encoding="utf-8")

    assert _resolve_vision_encoder_path("~/models--google--siglip-so400m-patch14-384") == str(valid_snapshot)


def test_vision_encoder_local_tilde_path_expands_before_return(monkeypatch, tmp_path):
    from core.rdt_policy_steer import _resolve_vision_encoder_path

    monkeypatch.setenv("HOME", str(tmp_path))
    local_encoder = tmp_path / "encoders" / "custom-siglip"
    local_encoder.mkdir(parents=True)

    assert _resolve_vision_encoder_path("~/encoders/custom-siglip") == str(local_encoder)


def test_vision_encoder_cache_root_fails_fast_when_snapshot_missing(tmp_path):
    from core.rdt_policy_steer import _resolve_vision_encoder_path

    cache_root = tmp_path / "models--google--siglip-so400m-patch14-384"
    (cache_root / "snapshots" / "abc123").mkdir(parents=True)

    with pytest.raises(FileNotFoundError, match="preprocessor_config.json.*config.json"):
        _resolve_vision_encoder_path(str(cache_root))


def test_fkd_x0_source_prefers_model_output_for_sample_prediction(stub_steer):
    model_output = torch.ones(2, 64, 128)
    x_t = torch.zeros(2, 64, 128)

    chosen, source = stub_steer._select_fkd_x0_source(model_output=model_output, step_output=None, x_t=x_t)

    assert source == "model_output"
    torch.testing.assert_close(chosen, model_output)


def test_fkd_reward_scores_all_particles_with_diffusion_policy_slice(stub_steer, stub_adapter):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    x0_preds = torch.zeros(3, 64, 128)
    x0_preds[0, :4, 39] = 1.0
    x0_preds[1, :4, 39] = 2.0
    x0_preds[2, :4, 39] = 3.0

    def reward_fn(keypoints, traj):
        assert tuple(traj.shape) == (1, 3, 3)
        return traj[..., 0].sum()

    rewards = stub_steer._score_particles(
        x0_preds,
        torch.zeros(3, 3),
        [reward_fn],
        slice_kind="fkd",
    )

    assert tuple(rewards.shape) == (3,)
    assert rewards[2] > rewards[1] > rewards[0]


def test_select_particle_uses_best_reward_when_fkd_not_terminal(stub_steer, stub_adapter):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    samples = torch.zeros(3, 64, 128)
    samples[0, :4, 39] = 1.0
    samples[1, :4, 39] = 3.0
    samples[2, :4, 39] = 2.0

    selected = stub_steer._select_particle_for_execution(
        samples,
        keypoints=torch.zeros(3, 3),
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        fkd=None,
    )

    assert tuple(selected.shape) == (1, 64, 128)
    torch.testing.assert_close(selected[0, :4, 39], torch.full((4,), 3.0))


def test_select_particle_keeps_first_when_single_particle(stub_steer, stub_adapter):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=1,
        policy_config={"action_chunk_horizon": 4},
    )
    samples = torch.zeros(1, 64, 128)
    samples[0, :4, 39] = 5.0

    selected = stub_steer._select_particle_for_execution(
        samples,
        keypoints=torch.zeros(3, 3),
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        fkd=None,
    )

    torch.testing.assert_close(selected, samples)
