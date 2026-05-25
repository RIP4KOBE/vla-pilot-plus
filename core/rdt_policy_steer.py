"""
RDTSteer — wraps RoboticDiffusionTransformerModel with the VLS steering interface.

Duck-typed to match DiffusionPolicySteer / PI05PolicySteer:
  post_init(), select_action(), reset(), reset_stage(),
  get_normalized_reward(), get_last_scale(), _action_chunk_horizon, name
"""
from __future__ import annotations

import json
import math
import os
import sys
from collections.abc import Callable
from typing import List, Optional, Tuple

import numpy as np
import torch
from torch import Tensor, nn

from core.env_adapters import BaseEnvAdapter
from core.fkd_class import FKD
from core.rdt_libero_action_converter import (
    ACTIVE_INDICES_SORTED,
    LIBERO_RDT_INDICES,
    decode_rdt_libero_action_chunk,
)
from core.rdt_libero_obs_processor import RDTLiberoObsProcessor
from utils.logging_utils import SteerLogger

log = SteerLogger("RDTSteer")


def _rdt_flat_config_to_args(flat: dict) -> dict:
    """Convert an RDTRunner-style config.json into scripts/*_model.py args."""
    img_pos = flat.get("img_pos_embed_config", [["image", [2, 3, -729]]])
    try:
        img_history_size = int(img_pos[0][1][0])
        num_cameras = int(img_pos[0][1][1])
    except Exception:
        img_history_size = 2
        num_cameras = 3

    return {
        "common": {
            "img_history_size": img_history_size,
            "action_chunk_size": int(flat["pred_horizon"]),
            "num_cameras": num_cameras,
            "state_dim": int(flat["action_dim"]),
        },
        "dataset": {
            "image_aspect_ratio": "pad",
            "tokenizer_max_length": int(flat["max_lang_cond_len"]),
        },
        "model": {
            "lang_adaptor": flat["lang_adaptor"],
            "img_adaptor": flat["img_adaptor"],
            "state_adaptor": flat["state_adaptor"],
            "lang_token_dim": int(flat["lang_token_dim"]),
            "img_token_dim": int(flat["img_token_dim"]),
            "state_token_dim": int(flat["state_token_dim"]),
            "rdt": flat["rdt"],
            "noise_scheduler": flat["noise_scheduler"],
            "ema": flat.get("ema", {}),
        },
        "_source_config": {
            "format": "hf_config_json",
            "img_cond_len": flat.get("img_cond_len"),
            "img_pos_embed_config": flat.get("img_pos_embed_config"),
            "lang_pos_embed_config": flat.get("lang_pos_embed_config"),
        },
    }


# ── Adapter for the real RoboticDiffusionTransformerModel ────────────────────

class _RDTDiTAdapter(nn.Module):
    """
    Thin nn.Module that wraps an RDTRunner and exposes the same forward
    signature that _StubDiT uses: forward(x_t, t, cond) → noise_pred.

    ``cond`` is the dict returned by ``_RDTModelAdapter.encode_inputs``.
    It carries all pre-computed conditioning tensors so we only run vision /
    language encoders once per action chunk (not once per denoising step).

    Mirrors the inner loop of RDTRunner.conditional_sample exactly.

    Dimension bridging
    ------------------
    The guided denoising loop maintains ``x_t`` in the raw robot action space
    (e.g. 8D for the ManiSkill single-arm setup).  The real RDT DiT operates in
    the 128D unified action space.  This adapter handles the lift (8→128) and
    projection (128→8) transparently:

      1. Inflate ``x_t`` into a 128D tensor using the action indices stored in
         ``cond["action_indices"]`` (set by ``_RDTModelAdapter.encode_inputs``).
      2. Call the real DiT.
      3. Project the 128D noise prediction back to the original action_dim.

    When ``cond`` is an empty dict (stub model) or ``cond["action_indices"]``
    is absent, the adapter is a no-op and lets ``x_t`` pass through unmodified —
    this preserves backward compatibility with the smoke tests.
    """

    def __init__(self, runner: nn.Module) -> None:
        super().__init__()
        self.runner = runner  # RDTRunner (nn.Module)

    def forward(self, x_t: Tensor, t: Tensor, cond: dict) -> Tensor:
        """
        x_t : (B, pred_horizon, raw_action_dim)
        t   : 0-d or (1,) LongTensor
        cond: dict (empty for stub; real keys: lang_cond, lang_attn_mask,
              img_cond, state_traj, action_mask, ctrl_freqs, action_indices,
              unified_action_dim)
        """
        # ── Stub fast-path: no conditioning means stub model ─────────────────
        if not cond:
            # This branch is only reached by tests using _StubRDTModel.
            # The stub's _StubDiT.forward handles this — this adapter is only
            # instantiated for the real model, so we should not reach here.
            raise RuntimeError(
                "_RDTDiTAdapter.forward called with empty cond; "
                "this should only happen with the stub model."
            )

        B = x_t.shape[0]
        raw_action_dim = x_t.shape[2]
        unified_dim: int = cond["unified_action_dim"]  # e.g. 128
        action_indices: list = cond["action_indices"]   # list of int indices into 128D

        # ── Expand batch=1 conditioning tensors to batch=B ───────────────────
        def _b(tensor: Tensor) -> Tensor:
            if tensor.shape[0] == 1 and B > 1:
                return tensor.expand(B, *tensor.shape[1:])
            return tensor

        lang_cond = _b(cond["lang_cond"])
        lang_attn_mask = _b(cond["lang_attn_mask"])
        img_cond = _b(cond["img_cond"])
        state_traj = _b(cond["state_traj"])
        action_mask_base = _b(cond["action_mask"])  # (B, 1, unified_dim)
        ctrl_freqs = _b(cond["ctrl_freqs"])

        # ── Lift x_t to unified action space ─────────────────────────────────
        # When x_t is already in the full 128D unified space (fixed denoising loop),
        # pass it through directly — no zero-padding inflation needed.
        # The subspace branch (raw_action_dim < unified_dim) is kept for backward
        # compatibility with any future callers that still pass 8D x_t.
        H = x_t.shape[1]
        if raw_action_dim == unified_dim:
            x_unified = x_t
        else:
            x_unified = torch.zeros(B, H, unified_dim, device=x_t.device, dtype=x_t.dtype)
            x_unified[:, :, action_indices] = x_t[:, :, :len(action_indices)]

        # ── Build state-action trajectory and call the DiT ───────────────────
        action_mask_full = action_mask_base.expand(-1, H, -1)  # (B, H, unified_dim)
        action_traj = torch.cat([x_unified, action_mask_full], dim=2)  # (B, H, unified_dim*2)
        action_traj = self.runner.state_adaptor(action_traj)
        state_action_traj = torch.cat([state_traj, action_traj], dim=1)

        if t.dim() == 0:
            t = t.unsqueeze(0)
        t = t.to(x_t.device)
        model_output_128 = self.runner.model(
            state_action_traj,
            ctrl_freqs,
            t,
            lang_cond,
            img_cond,
            lang_mask=lang_attn_mask,
        )  # (B, H, unified_dim)

        # ── Return noise_pred in the same space as the incoming x_t ──────────
        if raw_action_dim == unified_dim:
            return model_output_128
        return model_output_128[:, :, action_indices][:, :, :raw_action_dim]


class _RDTModelAdapter(nn.Module):
    """
    Wraps ``RoboticDiffusionTransformerModel`` (a plain Python object) and gives
    it the interface expected by ``RDTSteer._find_dit`` and the guided loop:

      * ``self.dit``      – an ``_RDTDiTAdapter`` (nn.Module)
      * ``self.noise_scheduler``  – exposed as ``noise_scheduler_sample`` on .policy
      * ``encode_inputs`` – encodes vision/language/proprio once; returns cond dict
      * ``step``          – passthrough to the underlying model's ``step()``
    """

    def __init__(self, real_model) -> None:
        super().__init__()
        # Store as a regular attribute (not registered parameter) because the
        # real model is not an nn.Module.
        object.__setattr__(self, "_real", real_model)
        # Register the DiT adapter so .parameters() / .to() / .eval() work.
        self.dit = _RDTDiTAdapter(real_model.policy)
        # Expose a noise_scheduler attribute pointing at the inference scheduler
        # so _noise_scheduler property on RDTSteer finds it.
        self.noise_scheduler = real_model.policy.noise_scheduler_sample

    # ── nn.Module device / dtype management ──────────────────────────────────

    def to(self, *args, **kwargs):
        # Move registered nn.Module children (i.e. self.dit)
        super().to(*args, **kwargs)
        real = object.__getattribute__(self, "_real")
        # Move the non-Module sub-components of the real model
        for attr in ("policy", "vision_model", "text_model"):
            comp = getattr(real, attr, None)
            if comp is not None and isinstance(comp, nn.Module):
                comp.to(*args, **kwargs)
        # Update device attribute on the real model if it tracks one
        if args and isinstance(args[0], (str, torch.device)):
            real.device = torch.device(args[0])
        elif "device" in kwargs:
            real.device = torch.device(kwargs["device"])
        return self

    def eval(self):
        super().eval()
        real = object.__getattribute__(self, "_real")
        for attr in ("policy", "vision_model", "text_model"):
            comp = getattr(real, attr, None)
            if comp is not None and isinstance(comp, nn.Module):
                comp.eval()
        return self

    def train(self, mode: bool = True):
        super().train(mode)
        real = object.__getattribute__(self, "_real")
        for attr in ("policy", "vision_model", "text_model"):
            comp = getattr(real, attr, None)
            if comp is not None and isinstance(comp, nn.Module):
                comp.train(mode)
        return self

    # ── Inference helpers ─────────────────────────────────────────────────────

    @torch.no_grad()
    def encode_inputs(self, state_128: Tensor, state_mask_128: Tensor, images: list, text_embeds: Tensor) -> dict:
        """
        Encode vision and language once before the denoising loop.
        Returns a conditioning dict that _RDTDiTAdapter.forward() unpacks.

        Mirrors the pre-loop work in RoboticDiffusionTransformerModel.step().
        """
        real = object.__getattribute__(self, "_real")
        device = real.device
        dtype = real.dtype

        # ── Image encoding ────────────────────────────────────────────────────
        import numpy as np
        from PIL import Image as PILImage
        from torchvision import transforms as T

        background_color = np.array(
            [int(x * 255) for x in real.image_processor.image_mean],
            dtype=np.uint8,
        ).reshape(1, 1, 3)
        background_image = np.ones(
            (
                real.image_processor.size["height"],
                real.image_processor.size["width"],
                3,
            ),
            dtype=np.uint8,
        ) * background_color

        image_tensor_list = []
        for img in images:
            if img is None:
                img = PILImage.fromarray(background_image)
            if real.image_size is not None:
                img = T.Resize(real.image_size)(img)
            if real.args["dataset"].get("image_aspect_ratio", "pad") == "pad":

                def _expand2square(pil_img, bg):
                    w, h = pil_img.size
                    if w == h:
                        return pil_img
                    side = max(w, h)
                    result = PILImage.new(pil_img.mode, (side, side), bg)
                    result.paste(pil_img, ((side - w) // 2, (side - h) // 2))
                    return result

                img = _expand2square(
                    img,
                    tuple(int(x * 255) for x in real.image_processor.image_mean),
                )
            img = real.image_processor.preprocess(img, return_tensors="pt")[
                "pixel_values"
            ][0]
            image_tensor_list.append(img)

        image_tensor = torch.stack(image_tensor_list, dim=0).to(device, dtype=dtype)
        image_embeds = real.vision_model(image_tensor).detach()
        image_embeds = image_embeds.reshape(-1, real.vision_model.hidden_size).unsqueeze(0)

        # ── LIBERO 128D state encoding ────────────────────────────────────────
        unified_action_dim = int(real.args["model"]["state_token_dim"])
        if unified_action_dim != 128:
            raise ValueError(f"Expected RDT state_token_dim=128, got {unified_action_dim}")

        states = state_128.to(device=device, dtype=dtype)
        state_elem_mask = state_mask_128.to(device=device, dtype=dtype)
        if states.shape != (1, unified_action_dim):
            raise ValueError(f"state_128 must have shape (1, 128), got {tuple(states.shape)}")
        if state_elem_mask.shape != (1, unified_action_dim):
            raise ValueError(f"state_mask_128 must have shape (1, 128), got {tuple(state_elem_mask.shape)}")
        active = torch.where(state_elem_mask[0] > 0)[0].detach().cpu().tolist()
        if active != ACTIVE_INDICES_SORTED:
            raise ValueError(f"LIBERO active mask mismatch: expected {ACTIVE_INDICES_SORTED}, got {active}")

        states = states.unsqueeze(1)
        action_indices = LIBERO_RDT_INDICES
        ctrl_freqs = torch.tensor([real.control_frequency], device=device)

        # ── Language ─────────────────────────────────────────────────────────
        text_embeds = text_embeds.to(device, dtype=dtype)
        lang_attn_mask = torch.ones(
            text_embeds.shape[:2], dtype=torch.bool, device=device
        )

        # ── Adapt to RDTRunner hidden size ────────────────────────────────────
        state_tokens = torch.cat([states, state_elem_mask.unsqueeze(1)], dim=2)
        lang_cond, img_cond, state_traj = real.policy.adapt_conditions(
            text_embeds, image_embeds, state_tokens
        )

        if not getattr(self, "_io_probe_logged", False):
            self._io_probe_logged = True
            log.warning(
                f"[RDT_IO_PROBE] images={len(images)} "
                f"state_128_shape={tuple(state_128.shape)} "
                f"text_shape={tuple(text_embeds.shape)} "
                f"image_embeds={tuple(image_embeds.shape)} "
                f"state_tokens={tuple(state_tokens.shape)} "
                f"lang_cond={tuple(lang_cond.shape)} "
                f"img_cond={tuple(img_cond.shape)} "
                f"state_traj={tuple(state_traj.shape)} "
                f"action_mask={tuple(state_elem_mask.unsqueeze(1).shape)} "
                f"ctrl_freqs={tuple(ctrl_freqs.shape)} "
                f"action_indices={action_indices}"
            )

        return {
            "lang_cond": lang_cond,
            "lang_attn_mask": lang_attn_mask,
            "img_cond": img_cond,
            "state_traj": state_traj,
            "action_mask": state_elem_mask.unsqueeze(1),  # (1, 1, unified_action_dim)
            "ctrl_freqs": ctrl_freqs,
            "action_indices": action_indices,
            "unified_action_dim": unified_action_dim,
        }

    def step(self, proprio, images, text_embeds):
        """Passthrough to the underlying real model's step()."""
        real = object.__getattribute__(self, "_real")
        return real.step(proprio, images, text_embeds)

    @property
    def action_min(self) -> Tensor:
        return object.__getattribute__(self, "_real").action_min

    @property
    def action_max(self) -> Tensor:
        return object.__getattribute__(self, "_real").action_max


class RDTSteer:
    """RDT-1B with VLS steering: RBF diversity + keypoint gradient + FKD resampling."""

    name = "rdt_steer"

    def __init__(self, rdt_model, num_inference_steps: int = 5) -> None:
        self._rdt_model = rdt_model
        self._num_inference_steps = num_inference_steps

        self._adapter: Optional[BaseEnvAdapter] = None
        self._obs_processor: Optional[RDTLiberoObsProcessor] = None
        self._sample_batch_size: int = 1
        self._action_chunk_horizon: int = 8

        self._cached_action_chunk: Optional[Tensor] = None
        self._last_normalized_reward: float = 0.0
        self._last_scale: float = 0.0
        self._stage_init_reward: Optional[float] = None
        self._last_raw_reward: float = 0.0
        self._current_alpha_t: float = 0.5

        # Probe inner DiT score network once at construction.
        self._dit: nn.Module = self._find_dit(rdt_model)

    # ── Construction ─────────────────────────────────────────────────────────

    @staticmethod
    def _find_dit(model) -> nn.Module:
        """Return the inner DiT score network (handles both real and stub models)."""
        log.info(f"[_find_dit] input model type: {type(model).__name__}")
        # Real RoboticDiffusionTransformerModel: .policy = RDTRunner, .policy.model = RDT DiT
        policy = getattr(model, "policy", None)
        if policy is not None and isinstance(policy, nn.Module):
            inner = getattr(policy, "model", None)
            if isinstance(inner, nn.Module):
                log.info(f"[_find_dit] branch 1 hit (model.policy.model): returning {type(inner).__name__}")
                return inner
        # Stub model or flat structure: probe common names
        for attr in ("dit", "model", "net", "backbone", "denoiser"):
            candidate = getattr(model, attr, None)
            if isinstance(candidate, nn.Module):
                log.info(f"[_find_dit] branch 2 hit (model.{attr}): returning {type(candidate).__name__}")
                return candidate
        raise AttributeError(
            f"Cannot locate DiT score network in RDT model. "
            f"Attributes: {[a for a in dir(model) if not a.startswith('_')]}"
        )

    @property
    def _noise_scheduler(self):
        """Return inference-time noise scheduler (handles both real and stub models)."""
        # Real RoboticDiffusionTransformerModel: policy.noise_scheduler_sample
        policy = getattr(self._rdt_model, "policy", None)
        if policy is not None:
            sched = getattr(policy, "noise_scheduler_sample", None)
            if sched is not None:
                return sched
        # Stub model has noise_scheduler directly on it
        return getattr(self._rdt_model, "noise_scheduler", None)

    @classmethod
    def from_pretrained(
        cls,
        pretrained_path: str,
        num_inference_steps: Optional[int] = None,
        vision_encoder: str = "/mnt/data/hf_cache/hub/models--google--siglip-so400m-patch14-384",
        text_encoder: str = "/mnt/data/hf_cache/hub/models--google--t5-v1_1-xxl",
        weight_variant: str = "ema",
        control_frequency: int = 20,
    ) -> "RDTSteer":
        """Load from a HuggingFace Hub repo ID or a local directory path.

        ``RoboticDiffusionTransformerModel`` is a plain Python object (not an
        nn.Module) and has no ``from_pretrained`` classmethod.  The correct
        loading pattern is:

          1. If ``pretrained_path`` is an HF Hub repo ID, download the full
             snapshot with ``snapshot_download`` first.
          2. Load config from ``<checkpoint>/config.yaml``.
          3. Call ``create_model(args, pretrained=<weight_file>)`` from
             ``scripts/maniskill_model.py``.
          4. Wrap the resulting plain-object model in ``_RDTModelAdapter`` so
             that it exposes the ``encode_inputs`` / DiT adapter interface that
             the guided denoising loop expects.
        """
        rdt_root = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "third_party", "rdt",
        )
        if rdt_root not in sys.path:
            sys.path.insert(0, rdt_root)

        if not os.path.isdir(pretrained_path):
            from huggingface_hub import snapshot_download
            # Support "namespace/repo/subdir" — split off the subdir so the
            # repo_id stays a valid 2-segment HF identifier.
            parts = pretrained_path.split("/", 2)
            if len(parts) == 3:
                repo_id, subdir = "/".join(parts[:2]), parts[2]
                log.info(f"Downloading checkpoint: {repo_id} (subdir: {subdir})")
                snapshot_root = snapshot_download(
                    repo_id=repo_id,
                    allow_patterns=[f"{subdir}/**", f"{subdir}/*"],
                )
                pretrained_path = os.path.join(snapshot_root, subdir)
            else:
                log.info(f"Downloading checkpoint: {pretrained_path}")
                pretrained_path = snapshot_download(repo_id=pretrained_path)

        log.info(f"Loading RDT model from: {pretrained_path}")

        try:
            import yaml
            from scripts.maniskill_model import create_model
        except ImportError:
            raise ImportError(
                "Cannot import RoboticDiffusionTransformerModel. "
                "Ensure third_party/rdt/ is initialized: git submodule update --init"
            )

        weight_names = (
            "model.safetensors",
            "pytorch_model.bin",
            "mp_rank_00_model_states.pt",
            "rdt-1b.pt",
        )
        weight_search_dirs = [
            os.path.join(pretrained_path, weight_variant),
            pretrained_path,
            os.path.join(pretrained_path, "rdt"),
        ]
        weight_file = None
        for search_root in weight_search_dirs:
            if not os.path.isdir(search_root):
                continue
            for fname in weight_names:
                candidate = os.path.join(search_root, fname)
                if os.path.exists(candidate):
                    weight_file = candidate
                    break
            if weight_file is not None:
                break
        if weight_file is None:
            raise FileNotFoundError(
                f"No RDT weight file found for variant '{weight_variant}' under {pretrained_path}. "
                f"Searched: {weight_search_dirs}. Looked for: {weight_names}."
            )
        log.info(f"Using weight file: {weight_file}")

        # Load the model config that ships with the checkpoint. Some HF repos
        # place RDTRunner-style config.json at the repo root while the actual
        # weights live in an `ema/` subdirectory; include parent dirs too.
        config_path = None
        config_kind = None
        config_search_dirs = []
        for d in weight_search_dirs:
            config_search_dirs.append(d)
            parent = os.path.dirname(d)
            if parent and parent not in config_search_dirs:
                config_search_dirs.append(parent)
        for d in config_search_dirs:
            candidate = os.path.join(d, "config.yaml")
            if os.path.exists(candidate):
                config_path = candidate
                config_kind = "yaml"
                break
            candidate = os.path.join(d, "config.json")
            if os.path.exists(candidate):
                config_path = candidate
                config_kind = "json"
                break
        if config_path is None:
            # Fall back to the bundled base config inside the submodule
            config_path = os.path.join(rdt_root, "configs", "base.yaml")
            config_kind = "yaml"
            log.warning(f"[FALLBACK] checkpoint has no config.yaml — using bundled: {config_path}")
        else:
            log.info(f"Using config: {config_path}")
        with open(config_path, "r") as f:
            if config_kind == "json":
                flat_config = json.load(f)
                args = _rdt_flat_config_to_args(flat_config)
            else:
                args = yaml.safe_load(f)
                flat_config = None
        args.setdefault("_source_config", {})
        args["_source_config"].update({
            "path": config_path,
            "kind": config_kind,
            "pretrained_path": pretrained_path,
        })

        assert args["common"]["state_dim"] == args["model"]["state_token_dim"], (
            "RDT config mismatch: common.state_dim must equal model.state_token_dim"
        )
        assert args["model"]["state_token_dim"] == 128, (
            "Current RDT integration assumes the 128D unified RDT state/action space"
        )
        assert args["common"]["img_history_size"] == 2, (
            "Current RDT observation processor builds exactly 2 image history frames"
        )
        assert args["common"]["num_cameras"] == 3, (
            "Current RDT observation processor builds 3 camera slots per history frame"
        )
        assert args["dataset"]["tokenizer_max_length"] == args["model"].get(
            "max_lang_cond_len", args["dataset"]["tokenizer_max_length"]
        )
        log.warning(
            f"[RDT_CKPT_CONFIG] source={config_path} kind={config_kind} "
            f"state_dim={args['common']['state_dim']} "
            f"pred_horizon={args['common']['action_chunk_size']} "
            f"img_history={args['common']['img_history_size']} "
            f"num_cameras={args['common']['num_cameras']} "
            f"tokenizer_max_length={args['dataset']['tokenizer_max_length']} "
            f"lang_token_dim={args['model']['lang_token_dim']} "
            f"img_token_dim={args['model']['img_token_dim']} "
            f"state_token_dim={args['model']['state_token_dim']} "
            f"scheduler={args['model']['noise_scheduler']}"
        )
        if num_inference_steps is None:
            num_inference_steps = int(args["model"]["noise_scheduler"].get("num_inference_timesteps", 5))
        log.warning(
            f"[RDT_LIBERO_CONFIG] checkpoint={pretrained_path} "
            f"variant={weight_variant} weight_file={weight_file} "
            f"steps={num_inference_steps} control_frequency={control_frequency} "
            f"active_indices={ACTIVE_INDICES_SORTED}"
        )

        # ``create_model`` constructs RoboticDiffusionTransformerModel and
        # calls load_pretrained_weights when pretrained is not None.
        # Force local-cache-only for the sub-model loads (T5, SigLIP) — both
        # are already cached and HF_ENDPOINT may point to a mirror with SSL issues.
        #
        # NOTE: setting `HF_HUB_OFFLINE=1` here is NOT sufficient — huggingface_hub
        # snapshots the env var at module-import time, and `refs/main` may have
        # advanced upstream (e.g. T5-v1_1-xxl's main commit added safetensors),
        # so transformers will re-resolve the ref and try to download the new
        # weights even if a complete older snapshot exists locally. We instead
        # monkey-patch each `from_pretrained` to force `local_files_only=True`
        # for the duration of the create_model call.
        import functools as _functools
        _patch_targets = []
        from transformers import T5EncoderModel as _T5E, AutoTokenizer as _AT, AutoConfig as _AC
        _patch_targets.extend([_T5E, _AT, _AC])
        try:
            from transformers import SiglipImageProcessor as _SIP
            _patch_targets.append(_SIP)
        except ImportError:
            pass
        try:
            from transformers import SiglipVisionModel as _SVM
            _patch_targets.append(_SVM)
        except ImportError:
            pass

        _originals = {}
        for _cls in _patch_targets:
            _orig = _cls.from_pretrained
            _originals[_cls] = _orig

            @_functools.wraps(_orig)
            def _wrapped(*args, _orig=_orig, **kwargs):
                kwargs.setdefault("local_files_only", True)
                return _orig(*args, **kwargs)
            _cls.from_pretrained = _wrapped
        log.info(
            f"Forcing local_files_only=True for {len(_patch_targets)} from_pretrained call sites "
            f"({[c.__name__ for c in _patch_targets]})"
        )

        # Also disable transformers' background "auto safetensors conversion".
        # When loading a .bin checkpoint, transformers spawns a daemon thread
        # that scans the hub for community-submitted refs/pr/* containing a
        # .safetensors port and downloads it for future fast-loading. For
        # large models (T5-v1_1-xxl: 44 GB) this saturates the network and
        # competes with online API calls (Gemini / OpenAI VLM) during the
        # episode. The flag is checked via os.getenv() at call time, so
        # setting it here is sufficient.
        # Source: transformers/modeling_utils.py:607-613 `can_auto_convert`.
        _prev_disable_conv = os.environ.get("DISABLE_SAFETENSORS_CONVERSION")
        os.environ["DISABLE_SAFETENSORS_CONVERSION"] = "1"
        log.info("DISABLE_SAFETENSORS_CONVERSION=1 (suppresses background PR-safetensors prefetch)")

        try:
            real_model = create_model(
                args,
                pretrained=weight_file,
                pretrained_text_encoder_name_or_path=text_encoder,
                pretrained_vision_encoder_name_or_path=vision_encoder,
                control_frequency=control_frequency,
            )
        finally:
            for _cls, _orig in _originals.items():
                _cls.from_pretrained = _orig
            if _prev_disable_conv is None:
                os.environ.pop("DISABLE_SAFETENSORS_CONVERSION", None)
            else:
                os.environ["DISABLE_SAFETENSORS_CONVERSION"] = _prev_disable_conv

        # Wrap in the adapter that provides encode_inputs + nn.Module interface.
        rdt_model = _RDTModelAdapter(real_model)

        # ── Sub-model load report ───────────────────────────────────────────
        def _summarize(m):
            try:
                p = next(m.parameters())
                return f"device={p.device}, dtype={p.dtype}, params={sum(x.numel() for x in m.parameters())/1e6:.1f}M"
            except StopIteration:
                return "no parameters"
        log.info(f"  text_model (T5):     {_summarize(real_model.text_model)}")
        log.info(f"  vision_model (SigLIP): {_summarize(real_model.vision_model)}, image_size={real_model.image_processor.size}")
        log.info(f"  policy (RDTRunner):  {_summarize(real_model.policy)}, weight_file={os.path.basename(weight_file)}")
        log.info(f"  state_min/max device={real_model.state_min.device} (must match policy device after .to)")

        instance = cls(rdt_model, num_inference_steps=num_inference_steps)

        log.info("RDT-1B loaded successfully")
        return instance

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def post_init(
        self,
        adapter: BaseEnvAdapter,
        postprocessor: Callable,
        sample_batch_size: int,
        policy_config: dict,
    ) -> None:
        self._adapter = adapter
        self._sample_batch_size = sample_batch_size
        self._action_chunk_horizon = policy_config.get("action_chunk_horizon", 8)
        if self._obs_processor is None:
            undo_flip = bool(policy_config.get("undo_libero_preprocessor_flip", True))
            debug_first_step = bool(policy_config.get("debug_first_step", False))
            try:
                self._obs_processor = RDTLiberoObsProcessor(
                    undo_preprocessor_flip=undo_flip,
                    debug_first_step=debug_first_step,
                )
            except TypeError:
                self._obs_processor = RDTLiberoObsProcessor(
                    undo_preprocessor_flip=undo_flip,
                    debug=debug_first_step,
                )
        log.info(
            f"post_init wired: adapter={type(self._adapter).__name__}, "
            f"undo_libero_flip={self._obs_processor.undo_preprocessor_flip}, "
            f"sample_batch_size={self._sample_batch_size}, "
            f"action_chunk_horizon={self._action_chunk_horizon}"
        )

    def _get_lang_embed(self, task: str) -> Tensor:
        real = None
        try:
            real = object.__getattribute__(self._rdt_model, "_real")
        except Exception:
            real = None
        if real is not None and callable(getattr(real, "encode_instruction", None)):
            embed = real.encode_instruction(task, device=str(self.device))
            return embed.float().to(self.device)
        return torch.zeros(1, 1, 4096, device=self.device)

    def to(self, device) -> "RDTSteer":
        if isinstance(self._rdt_model, nn.Module):
            self._rdt_model = self._rdt_model.to(device)
        self._dit = self._find_dit(self._rdt_model)
        return self

    def eval(self) -> "RDTSteer":
        if isinstance(self._rdt_model, nn.Module):
            self._rdt_model.eval()
        return self

    def reset(self) -> None:
        self._cached_action_chunk = None
        self._stage_init_reward = None
        self._last_normalized_reward = 0.0
        self._last_scale = 0.0
        self._last_raw_reward = 0.0
        self._current_alpha_t = 0.5
        if self._obs_processor is not None:
            self._obs_processor.reset()

    def reset_stage(self) -> None:
        self._stage_init_reward = None

    def get_normalized_reward(self) -> float:
        return self._last_normalized_reward

    def get_last_scale(self) -> float:
        return self._last_scale

    @property
    def device(self) -> torch.device:
        try:
            return next(self._dit.parameters()).device
        except StopIteration:
            return torch.device("cpu")

    # ── Inference entry point ─────────────────────────────────────────────────

    def select_action(
        self,
        batch: dict,
        generate_new_chunk: bool = False,
        use_guidance: bool = False,
        keypoints: Optional[np.ndarray] = None,
        guidance_fns: Optional[List[Callable]] = None,
        guide_scale: float = 1.0,
        sigmoid_k: float = 12.0,
        sigmoid_x0: float = 0.7,
        start_ratio: Optional[float] = None,
        use_diversity: bool = True,
        diversity_scale: float = 1.0,
        MCMC_steps: int = 4,
        verbose: bool = False,
        use_fkd: bool = False,
        fkd_config: Optional[dict] = None,
        global_step: int = 0,
        current_stage: int = 1,
    ) -> Tensor:
        if generate_new_chunk:
            if self._obs_processor is None:
                raise RuntimeError("RDTSteer.post_init must be called before select_action")
            converted = self._obs_processor.process(batch)
            text_embed = self._get_lang_embed(converted.task)
            B = self._sample_batch_size

            if use_guidance:
                raise NotImplementedError(
                    "RDT LIBERO VLS steering is deferred until unguided LIBERO semantics pass."
                )
            else:
                raw = self._predict_unguided(
                    converted.state_128,
                    converted.state_mask_128,
                    converted.images,
                    text_embed,
                    B,
                )

            self._cached_action_chunk = self._postprocess_actions(raw)

        return self._cached_action_chunk

    # ── Unguided path ─────────────────────────────────────────────────────────

    def _predict_unguided(
        self,
        state_128: Tensor,
        state_mask_128: Tensor,
        images: list,
        text_embed: Tensor,
        B: int,
    ) -> Tensor:
        """
        Run the denoising loop without guidance hooks in the full LIBERO 128D space.
        """
        device = self.device
        try:
            dtype = next(self._dit.parameters()).dtype
        except StopIteration:
            dtype = torch.float32

        cond = self._rdt_model.encode_inputs(state_128, state_mask_128, images, text_embed)
        unified_action_dim = int(cond["unified_action_dim"])
        if unified_action_dim != 128:
            raise ValueError(f"Expected unified action dim 128, got {unified_action_dim}")
        pred_horizon = 64
        x_t = torch.randn(B, pred_horizon, unified_action_dim, device=device, dtype=dtype)

        scheduler = self._noise_scheduler
        scheduler.set_timesteps(self._num_inference_steps)

        with torch.no_grad():
            for t in scheduler.timesteps:
                noise_pred = self._dit(x_t, t, cond)
                x_t = scheduler.step(noise_pred, t, x_t).prev_sample
                x_t = x_t.to(dtype=dtype)

        action_mask = cond["action_mask"].expand(B, pred_horizon, unified_action_dim).to(device=device, dtype=dtype)
        return (x_t * action_mask).float()

    # ── Action postprocessing ─────────────────────────────────────────────────

    def _postprocess_actions(self, actions: Tensor) -> Tensor:
        """
        (B, 64, 128) LIBERO RDT action space -> (1, H, 7) LIBERO raw actions.
        """
        if actions.ndim != 3 or tuple(actions.shape[1:]) != (64, 128):
            raise ValueError(f"Expected actions with shape (B, 64, 128), got {tuple(actions.shape)}")
        decoded = decode_rdt_libero_action_chunk(actions, self._action_chunk_horizon)
        if not torch.isfinite(decoded).all():
            raise ValueError("Decoded LIBERO action chunk contains non-finite values")
        log.info(
            f"Decoded LIBERO action chunk: shape={tuple(decoded.shape)} "
            f"min={float(decoded.min().item()):.4f} max={float(decoded.max().item()):.4f}"
        )
        return decoded

    # ── Trajectory projection (shared by diversity and guidance hooks) ────────

    def _rdt_sample_to_trajectory_3d(self, sample: Tensor) -> Tensor:
        """
        (1, 64, 128) -> (1, H+1, 3) via adapter.delta_actions_to_ee_trajectory.
        """
        libero_actions = decode_rdt_libero_action_chunk(sample, self._action_chunk_horizon)[0]
        if self._adapter is None:
            return torch.zeros(
                1,
                self._action_chunk_horizon + 1,
                3,
                device=sample.device,
                dtype=sample.dtype,
            )
        traj = self._adapter.delta_actions_to_ee_trajectory(libero_actions.to(sample.device))
        return traj.unsqueeze(0)

    # ── Gradient helpers ──────────────────────────────────────────────────────

    def _compute_diversity_gradient(self, x_t: Tensor) -> Optional[Tensor]:
        """
        RBF inverse-distance potential on 3D EEF trajectories.
        Pushes particles apart. Returns normalized gradient or None if B < 2.
        """
        B = x_t.shape[0]
        if B < 2 or self._adapter is None:
            return None

        try:
            with torch.enable_grad():
                x_grad = x_t.detach().requires_grad_(True)
                trajs = torch.cat(
                    [self._rdt_sample_to_trajectory_3d(x_grad[b: b + 1]) for b in range(B)],
                    dim=0,
                )  # (B, H+1, 3)
                pos = trajs[:, 1:, :3]      # skip start point → (B, H, 3)
                flat = pos.reshape(B, -1)   # (B, H*3)

                sq_dist = torch.sum(
                    (flat.unsqueeze(1) - flat.unsqueeze(0)) ** 2, dim=2
                )  # (B, B)
                mask = ~torch.eye(B, dtype=torch.bool, device=x_t.device)
                dist = torch.sqrt(sq_dist + 1e-6)
                inv_dist = (1.0 / (dist + 1e-6)) * mask.float()
                potential = inv_dist.sum()

                grads = torch.autograd.grad(potential, x_grad, create_graph=False, allow_unused=True)
                grad = grads[0]
                if grad is None:
                    return None
                g_norm = torch.norm(grad).item()
                return grad / (g_norm + 1e-8) if g_norm > 1e-8 else grad
        except Exception as exc:
            log.warning(f"Diversity gradient failed: {exc}")
            return None

    def _compute_keypoint_gradient(
        self,
        x_t: Tensor,
        keypoints: Tensor,
        guidance_fns: List[Callable],
        verbose: bool = False,
    ) -> Tuple[Optional[Tensor], float]:
        """
        Keypoint-based gradient guidance.
        1. Project x_t → 3D EEF trajectory.
        2. Evaluate sum of guidance_fns(keypoints, trajectory).
        3. Backprop → normalized gradient w.r.t. x_t.
        Returns (normalized_grad, raw_reward_scalar).
        """
        if not guidance_fns or self._adapter is None:
            return None, 0.0

        try:
            with torch.enable_grad():
                x_grad = x_t.detach().requires_grad_(True)
                trajs = torch.cat(
                    [self._rdt_sample_to_trajectory_3d(x_grad[b: b + 1]) for b in range(x_grad.shape[0])],
                    dim=0,
                )  # (B, H+1, 3)
                traj_input = trajs[:, : self._action_chunk_horizon, :3]  # (B, H, 3)

                reward = sum(fn(keypoints, traj_input) for fn in guidance_fns)

                if isinstance(reward, (int, float)):
                    return None, float(reward)
                if not hasattr(reward, "requires_grad") or not reward.requires_grad:
                    return None, float(reward.item())

                reward_scalar = float(reward.sum().item())
                self._last_raw_reward = reward_scalar

                # Update normalised reward relative to stage baseline
                if self._stage_init_reward is not None and self._stage_init_reward < -1e-6:
                    norm_r = 1.0 - reward_scalar / self._stage_init_reward
                    norm_r = max(0.0, min(1.2, norm_r))
                else:
                    norm_r = 0.0
                self._last_normalized_reward = norm_r

                grad = torch.autograd.grad(
                    reward.sum(), x_grad, create_graph=False, retain_graph=False
                )[0]
                g_norm = torch.norm(grad).item()
                normalized = grad / (g_norm + 1e-8) if g_norm > 1e-8 else grad

                if verbose:
                    log.info(f"reward={reward_scalar:.4f}, norm_r={norm_r:.3f}")

                return normalized, reward_scalar
        except Exception as exc:
            log.warning(f"Keypoint gradient failed: {exc}")
            return None, 0.0

    def _adaptive_scale(
        self, reward: float, guide_scale: float, sigmoid_k: float, sigmoid_x0: float
    ) -> float:
        """Sigmoid-gated guidance strength * sqrt(1-alpha_t) scaling."""
        strength = 1.0 / (1.0 + math.exp(sigmoid_k * (self._last_normalized_reward - sigmoid_x0)))
        alpha_t = self._current_alpha_t
        scale = guide_scale * strength * math.sqrt(max(0.0, 1.0 - float(alpha_t)))
        self._last_scale = scale
        return scale

    # ── Guided denoising loop ─────────────────────────────────────────────────

    def _guided_denoise_loop(
        self,
        proprio: np.ndarray,
        images: list,
        text_embeds: Tensor,
        B: int,
        guidance_fns: Optional[List[Callable]],
        keypoints: Optional[np.ndarray],
        guide_scale: float,
        start_ratio: Optional[float],
        use_diversity: bool,
        diversity_scale: float,
        use_fkd: bool,
        fkd_config: Optional[dict],
        sigmoid_k: float,
        sigmoid_x0: float,
        verbose: bool,
    ) -> Tensor:  # (B, 64, 14)
        """
        Three-phase denoising loop:
          D (t > start_t) : RBF diversity gradient  → noise_pred[:,:,:3]
          A (t ≤ start_t) : Keypoint guidance grad  → noise_pred[:,:H,:3]
          B (t ≤ start_t) : FKD resampling          → x_t after scheduler.step
        D and A are mutually exclusive (if/elif).
        """
        device = self.device
        try:
            dtype = next(self._dit.parameters()).dtype
        except StopIteration:
            dtype = torch.float32

        cond = self._rdt_model.encode_inputs(proprio, images, text_embeds)

        # Stub models return {} from encode_inputs — fall back to 14 (the stub step() shape)
        if "action_indices" in cond:
            raw_action_dim = len(cond["action_indices"])
            action_indices = cond["action_indices"]
            unified_action_dim = cond["unified_action_dim"]
        else:
            _probe = self._rdt_model.step(proprio=proprio, images=images, text_embeds=text_embeds)
            raw_action_dim = _probe.shape[-1]
            action_indices = list(range(raw_action_dim))
            unified_action_dim = raw_action_dim
        x_t = torch.randn(B, 64, unified_action_dim, device=device, dtype=dtype)

        scheduler = self._noise_scheduler
        scheduler.set_timesteps(self._num_inference_steps)
        timesteps = scheduler.timesteps

        start_idx = int(self._num_inference_steps * (start_ratio if start_ratio is not None else 0.7))
        start_idx = min(start_idx, len(timesteps) - 1)
        start_t = int(timesteps[start_idx].item())

        keypoints_tensor = None
        if keypoints is not None:
            keypoints_tensor = torch.tensor(keypoints, device=device, dtype=dtype)

        # Init FKD particle filter
        fkd = None
        if use_fkd and fkd_config is not None and B > 1 and guidance_fns and keypoints_tensor is not None:
            def _fkd_reward_fn(x0: Tensor) -> Tensor:
                rs = []
                for b in range(B):
                    traj = self._rdt_sample_to_trajectory_3d(x0[b: b + 1])
                    with torch.no_grad():
                        r = sum(
                            float(fn(keypoints_tensor, traj[:, : self._action_chunk_horizon, :3]).sum())
                            for fn in guidance_fns
                        )
                    rs.append(r)
                return torch.tensor(rs, dtype=dtype, device=device)

            fkd = FKD(
                potential_type=fkd_config.get("potential_type", "max"),
                lmbda=float(fkd_config.get("lmbda", 10.0)),
                num_particles=B,
                adaptive_resampling=bool(fkd_config.get("adaptive_resampling", True)),
                resample_frequency=int(fkd_config.get("resample_frequency", 5)),
                resampling_t_start=start_t,
                resampling_t_end=int(timesteps[-1].item()),
                timesteps=timesteps,
                reward_fn=_fkd_reward_fn,
                reward_min_value=float("-inf"),
                device=device,
            )

        reward_history: list = []

        for i, t in enumerate(timesteps):
            t_val = int(t.item())

            # Update alpha_t for adaptive_scale
            if hasattr(scheduler, "alphas_cumprod"):
                idx = min(t_val, len(scheduler.alphas_cumprod) - 1)
                self._current_alpha_t = float(scheduler.alphas_cumprod[idx])

            # Baseline noise prediction (no grad)
            with torch.no_grad():
                noise_pred = self._dit(x_t, t, cond)  # (B, 64, 14)

            # ── HOOK D: RBF diversity (early phase: t > start_t) ─────────────
            if use_diversity and t_val > start_t and B > 1:
                div_grad = self._compute_diversity_gradient(x_t)
                if div_grad is not None:
                    noise_pred = noise_pred.clone()
                    noise_pred[:, :, :7] = noise_pred[:, :, :7] + diversity_scale * div_grad[:, :, :7]

            # ── HOOK A: Keypoint gradient guidance (late phase: t ≤ start_t) ──
            elif guidance_fns and keypoints_tensor is not None and t_val <= start_t:
                kp_grad, reward_val = self._compute_keypoint_gradient(
                    x_t, keypoints_tensor, guidance_fns, verbose=verbose
                )
                if kp_grad is not None:
                    scale = self._adaptive_scale(reward_val, guide_scale, sigmoid_k, sigmoid_x0)
                    noise_pred = noise_pred.clone()
                    noise_pred[:, : self._action_chunk_horizon, :7] = (
                        noise_pred[:, : self._action_chunk_horizon, :7]
                        - scale * kp_grad[:, : self._action_chunk_horizon, :7]
                    )
                    reward_history.append((i, reward_val, self._last_normalized_reward))

            # Standard denoising step
            x_t = scheduler.step(noise_pred, t, x_t).prev_sample

            # ── HOOK B: FKD resampling (late phase only, after scheduler step) ─
            if fkd is not None and t_val <= start_t:
                x_t, _ = fkd.resample(sampling_idx=t_val, latents=x_t, x0_preds=x_t)

        # Set stage baseline from the first chunk's final reward
        if reward_history and self._stage_init_reward is None:
            self._stage_init_reward = reward_history[-1][1]
            log.info(f"Stage init_reward set: {self._stage_init_reward:.6f}")

        # Project from unified 128D back to the raw 8D action subspace for postprocessing.
        return x_t[:, :, action_indices][:, :, :raw_action_dim]
