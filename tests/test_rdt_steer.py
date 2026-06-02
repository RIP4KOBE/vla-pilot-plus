"""
CPU-only smoke tests for RDTSteer and RDTLiberoObsProcessor.
No real checkpoint or GPU required — uses stub RDT model.
"""
import inspect
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import numpy as np
import pytest
import torch
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
        out.prev_sample = model_output.clone()
        out.pred_original_sample = None
        return out


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
        guidance_fns=guidance,
        keypoints=keypoints,
    )
    assert stub_steer._rdt_model.encode_calls == 1
    assert stub_steer._cached_action_steps_remaining == 1

    reused = stub_steer.select_action(
        _raw_obs(task="guided-second"),
        generate_new_chunk=False,
        use_guidance=True,
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
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
    )

    assert tuple(action.shape) == (1, 8, 7)
    assert stub_steer._rdt_model.dit.calls
    assert any(latent_shape[0] == 4 for latent_shape, _ in stub_steer._rdt_model.dit.calls)


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
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
        guide_scale=1.0,
        use_diversity=True,
        diversity_scale=1.0,
        use_fkd=True,
        fkd_config={"potential_type": "max", "lmbda": 1.0, "adaptive_resampling": False, "resample_frequency": 1},
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
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
        use_diversity=True,
        diversity_scale=1.0,
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
            use_diversity=False,
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
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
        use_diversity=False,
        use_fkd=True,
        fkd_config={
            "potential_type": "max",
            "lmbda": 1.0,
            "adaptive_resampling": False,
            "resample_frequency": 1,
        },
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
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
        use_diversity=False,
        use_fkd=True,
        fkd_config={
            "potential_type": "max",
            "lmbda": 1.0,
            "adaptive_resampling": False,
            "resample_frequency": 1,
        },
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
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
        use_diversity=False,
        use_fkd=True,
        fkd_config={
            "potential_type": "max",
            "lmbda": 1.0,
            "adaptive_resampling": False,
            "resample_frequency": 1,
        },
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


def test_model_adapter_encode_inputs_logs_gt_io_summary_once(monkeypatch):
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
    assert output.count("[RDT_GT_IO]") == 1
    assert "state_active=[0, 1, 2, 3, 4, 5, 6, 10, 11]" in output
    assert "action_indices=[39, 40, 41, 42, 43, 44, 10]" in output
    assert "image_count=6" in output
    assert "text_shape=(1, 1, 4096)" in output
    assert "image_embed_shape=(1, 6, 1152)" in output


def test_postprocess_actions_logs_numeric_summary_with_first_action(stub_steer, monkeypatch):
    import core.rdt_policy_steer as rdt_policy_steer

    info_messages = []
    monkeypatch.setattr(rdt_policy_steer.log, "info", info_messages.append)
    stub_steer._action_chunk_horizon = 2
    actions = torch.zeros(1, 64, 128)
    actions[0, :, [39, 40, 41, 42, 43, 44, 10]] = torch.tensor(
        [0.1, -0.2, 0.3, -0.4, 0.5, -0.6, 1.0]
    )

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
