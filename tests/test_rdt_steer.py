"""
CPU-only smoke tests for RDTSteer and RDTObsProcessor.
No real checkpoint or GPU required — uses stub RDT model.
"""
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import numpy as np
import pytest
import torch
from torch import nn


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_core_pkg = ModuleType("core")
_core_pkg.__path__ = [str(Path(__file__).resolve().parents[1] / "core")]
sys.modules.setdefault("core", _core_pkg)

_env_adapters = ModuleType("core.env_adapters")


class _BaseEnvAdapter:
    pass


class _LiberoAdapter(_BaseEnvAdapter):
    pass


_env_adapters.BaseEnvAdapter = _BaseEnvAdapter
sys.modules.setdefault("core.env_adapters", _env_adapters)

_libero_adapter = ModuleType("core.env_adapters.libero_adapter")
_libero_adapter.LiberoAdapter = _LiberoAdapter
sys.modules.setdefault("core.env_adapters.libero_adapter", _libero_adapter)


# ── Stub RDT model (replaces the real 1.2B-param checkpoint) ────────────────

class _StubDiT(nn.Module):
    """Minimal DiT stand-in: returns zeros with the correct shape."""
    def forward(self, x, t, cond):
        return torch.zeros_like(x)


class _StubScheduler:
    """Minimal noise scheduler compatible with DPMSolverMultistepScheduler API."""

    def __init__(self, n=5):
        self.timesteps = torch.arange(n - 1, -1, -1, dtype=torch.long)

    def set_timesteps(self, n):
        self.timesteps = torch.arange(n - 1, -1, -1, dtype=torch.long)

    def step(self, noise_pred, t, x_t):
        out = MagicMock()
        out.prev_sample = x_t * 0.0
        return out


class _StubRDTModel(nn.Module):
    """Minimal stand-in for RoboticDiffusionTransformerModel."""

    def __init__(self):
        super().__init__()
        self.dit = _StubDiT()
        self.noise_scheduler = _StubScheduler()

    def encode_inputs(self, state_128, state_mask_128, images, text_embeds):
        return {
            "lang_cond": torch.zeros(1, 1, 4),
            "lang_attn_mask": torch.ones(1, 1, dtype=torch.bool),
            "img_cond": torch.zeros(1, 1, 4),
            "state_traj": torch.zeros(1, 1, 4),
            "action_mask": state_mask_128.float().unsqueeze(1),
            "ctrl_freqs": torch.tensor([20]),
            "action_indices": [30, 31, 32, 33, 34, 35, 36, 37, 38, 10],
            "unified_action_dim": 128,
        }


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def stub_steer():
    from core.rdt_policy_steer import RDTSteer
    return RDTSteer(rdt_model=_StubRDTModel(), num_inference_steps=5)


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
        "observation.images.image": torch.zeros(B, 3, 16, 16),
        "observation.images.image2": torch.zeros(B, 3, 16, 16),
        "observation.state": torch.tensor(
            [[0.10, -0.20, 0.80, 0.0, 0.0, 0.0, 0.04, -0.04]] * B,
            dtype=torch.float32,
        ),
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
    assert action.shape == (1, H, 7), f"Expected (1, {H}, 7), got {action.shape}"
    assert not torch.isnan(action).any()


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
    assert torch.where(converted.state_mask_128[0] > 0)[0].tolist() == [10, 30, 31, 32, 33, 34, 35, 36, 37, 38]
    assert converted.task == "pick up the red block"

    raw = stub_steer._predict_unguided(
        converted.state_128,
        converted.state_mask_128,
        converted.images,
        torch.zeros(1, 1, 4096),
        B=2,
    )
    assert raw.shape == (2, 64, 128)


def test_guided_rdt_libero_path_is_explicitly_deferred(stub_steer, stub_adapter, mock_batch):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"action_chunk_horizon": 8, "debug_first_step": True},
    )

    with pytest.raises(NotImplementedError, match="RDT LIBERO VLS steering"):
        stub_steer.select_action(
            mock_batch,
            generate_new_chunk=True,
            use_guidance=True,
            guidance_fns=[lambda keypoints, traj: traj.sum()],
            keypoints=np.zeros((3, 3), dtype=np.float32),
        )
