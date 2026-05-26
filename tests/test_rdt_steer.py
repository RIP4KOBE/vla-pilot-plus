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


def test_resolve_rdt_weight_file_accepts_direct_safetensors(tmp_path):
    from core.rdt_policy_steer import _resolve_rdt_weight_file

    weight = tmp_path / "model.safetensors"
    weight.write_bytes(b"stub")

    resolved, checkpoint_root = _resolve_rdt_weight_file(str(weight), "ema")

    assert resolved == str(weight)
    assert checkpoint_root == str(tmp_path)


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


def test_text_encoder_cache_root_normalizes_to_model_id():
    from core.rdt_policy_steer import _normalize_text_encoder_path

    assert _normalize_text_encoder_path("/mnt/data/hf_cache/hub/models--google--t5-v1_1-xxl") == "google/t5-v1_1-xxl"
    assert _normalize_text_encoder_path("google/t5-v1_1-xxl") == "google/t5-v1_1-xxl"


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
