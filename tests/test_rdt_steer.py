"""
CPU-only smoke tests for RDTSteer and RDTObsProcessor.
No real checkpoint or GPU required — uses stub RDT model.
"""
import numpy as np
import pytest
import torch
from torch import nn
from unittest.mock import MagicMock


# ── Stub RDT model (replaces the real 1.2B-param checkpoint) ────────────────

class _StubDiT(nn.Module):
    """Minimal DiT stand-in: returns zeros with the correct shape."""
    def forward(self, x, t, cond):
        return torch.zeros_like(x)  # (B, 64, 14)


class _StubScheduler:
    """Minimal noise scheduler compatible with DPMSolverMultistepScheduler API."""

    def __init__(self, n=10):
        self.timesteps = torch.arange(n - 1, -1, -1, dtype=torch.long)
        self.alphas_cumprod = torch.linspace(0.99, 0.01, 1000)

    def set_timesteps(self, n):
        self.timesteps = torch.arange(n - 1, -1, -1, dtype=torch.long)

    def step(self, noise_pred, t, x_t):
        out = MagicMock()
        out.prev_sample = x_t * 0.9  # trivial shrink
        return out


class _StubRDTModel(nn.Module):
    """Minimal stand-in for RoboticDiffusionTransformerModel."""

    def __init__(self):
        super().__init__()
        self.dit = _StubDiT()
        self.noise_scheduler = _StubScheduler()

    def encode_inputs(self, proprio, images, text_embeds):
        return {}  # conditioning dict (opaque to the loop)

    def step(self, proprio, images, text_embeds):
        return torch.zeros(1, 64, 14)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def stub_steer():
    from core.rdt_policy_steer import RDTSteer
    return RDTSteer(rdt_model=_StubRDTModel(), num_inference_steps=10)


@pytest.fixture
def stub_adapter():
    adapter = MagicMock()
    # (T, 7) action_seq → (T+1, 3) EEF trajectory
    adapter.delta_actions_to_ee_trajectory.side_effect = (
        lambda seq: torch.zeros(seq.shape[0] + 1, 3, requires_grad=True)
    )
    return adapter


@pytest.fixture
def mock_batch():
    B = 4
    return {
        "observation.images.image": torch.zeros(B, 3, 256, 256),
        "observation.images.image2": torch.zeros(B, 3, 256, 256),
        "observation.state": torch.zeros(B, 8),
        "task": ["pick up the red block"] * B,
    }


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_instantiation(stub_steer):
    """RDTSteer has the correct interface attributes."""
    assert stub_steer.name == "rdt_steer"
    assert isinstance(stub_steer._action_chunk_horizon, int)
    assert isinstance(stub_steer.get_normalized_reward(), float)
    assert isinstance(stub_steer.get_last_scale(), float)
    stub_steer.reset()          # must not raise
    stub_steer.reset_stage()    # must not raise


def test_forward_shape(stub_steer, stub_adapter, mock_batch):
    """select_action with use_guidance=False returns tensor of shape (H, 7)."""
    H = 8
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"action_chunk_horizon": H, "lang_embed_cache_dir": "/tmp/rdt_lang"},
    )
    action = stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=False,
    )
    assert action.shape == (H, 7), f"Expected ({H}, 7), got {action.shape}"
    assert not torch.isnan(action).any()


def test_fkd_rollout(stub_steer, stub_adapter, mock_batch):
    """3-step rollout with use_fkd=True completes without error."""
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 8, "lang_embed_cache_dir": "/tmp/rdt_lang"},
    )
    guidance_fn = lambda kp, traj: traj.sum()
    kp = torch.zeros(3, 3)

    for step in range(3):
        action = stub_steer.select_action(
            mock_batch,
            generate_new_chunk=(step == 0),
            use_guidance=True,
            use_fkd=True,
            fkd_config={
                "potential_type": "max",
                "lmbda": 1.0,
                "adaptive_resampling": False,
                "resample_frequency": 2,
            },
            guidance_fns=[guidance_fn],
            keypoints=kp.numpy(),
        )
    assert isinstance(stub_steer.get_normalized_reward(), float)


def test_gradient_steering(stub_steer, stub_adapter, mock_batch):
    """Gradient guidance runs without error and updates normalized reward."""
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"action_chunk_horizon": 8, "lang_embed_cache_dir": "/tmp/rdt_lang"},
    )

    def reward_fn(keypoints, traj):
        # Simple differentiable reward: sum of trajectory positions
        return traj.sum()

    kp = np.zeros((3, 3), dtype=np.float32)
    stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        use_fkd=False,
        guidance_fns=[reward_fn],
        keypoints=kp,
        guide_scale=1.0,
        start_ratio=0.0,   # guidance from the very first step
    )
    # After one guided denoising, reward should have been computed
    # (even if zero from stub — the method must not crash and must update state)
    assert isinstance(stub_steer.get_normalized_reward(), float)
