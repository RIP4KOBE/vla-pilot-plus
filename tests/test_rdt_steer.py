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
from torch import nn


class _BaseEnvAdapter:
    pass


class _LiberoAdapter(_BaseEnvAdapter):
    def delta_actions_to_ee_trajectory(self, seq):
        return torch.zeros(seq.shape[0] + 1, 3, requires_grad=True)


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
    return _LiberoAdapter()


@pytest.fixture
def mock_batch():
    B = 1
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
    assert stub_steer._rdt_model.dit.calls
    for latent_shape, mask_shape in stub_steer._rdt_model.dit.calls:
        assert latent_shape == (2, 64, 128)
        assert mask_shape[-1] == 128


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


def test_private_guided_loop_is_explicitly_deferred(stub_steer):
    with pytest.raises(NotImplementedError, match="RDT LIBERO VLS steering"):
        stub_steer._guided_denoise_loop()


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


def test_text_encoder_cache_root_normalizes_to_model_id():
    from core.rdt_policy_steer import _normalize_text_encoder_path

    assert _normalize_text_encoder_path("/mnt/data/hf_cache/hub/models--google--t5-v1_1-xxl") == "google/t5-v1_1-xxl"
    assert _normalize_text_encoder_path("google/t5-v1_1-xxl") == "google/t5-v1_1-xxl"


def test_vision_encoder_cache_root_resolves_snapshot(tmp_path):
    from core.rdt_policy_steer import _resolve_vision_encoder_path

    cache_root = tmp_path / "models--google--siglip-so400m-patch14-384"
    valid_snapshot = cache_root / "snapshots" / "abc123"
    valid_snapshot.mkdir(parents=True)
    (valid_snapshot / "config.json").write_text("{}", encoding="utf-8")
    (valid_snapshot / "preprocessor_config.json").write_text("{}", encoding="utf-8")

    assert _resolve_vision_encoder_path(str(cache_root)) == str(valid_snapshot)
    assert _resolve_vision_encoder_path("google/siglip-so400m-patch14-384") == "google/siglip-so400m-patch14-384"


def test_vision_encoder_cache_root_fails_fast_when_snapshot_missing(tmp_path):
    from core.rdt_policy_steer import _resolve_vision_encoder_path

    cache_root = tmp_path / "models--google--siglip-so400m-patch14-384"
    (cache_root / "snapshots" / "abc123").mkdir(parents=True)

    with pytest.raises(FileNotFoundError, match="preprocessor_config.json.*config.json"):
        _resolve_vision_encoder_path(str(cache_root))
