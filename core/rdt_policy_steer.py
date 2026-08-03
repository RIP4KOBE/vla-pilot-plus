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
import re
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from numbers import Integral, Real
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import torch
from torch import Tensor, nn

from core.eds_eval_metrics import EDSChunkMetrics, EDSIterMetrics
from core.eds_mechanism_trace import EDSMechanismTrace, EDSParticleStage
from core.env_adapters import BaseEnvAdapter
from core.fkd_class import FKD
from core.rdt_libero_action_converter import (
    ACTIVE_ACTION_INDICES_SORTED,
    ACTIVE_INDICES_SORTED,
    LIBERO_RDT_INDICES,
    decode_rdt_libero_action_chunk,
    rdt_action_to_libero_raw,
)
from core.rdt_libero_obs_processor import RDTLiberoObsProcessor
from utils.logging_utils import SteerLogger

log = SteerLogger("RDTSteer")

RDT_GUIDED_TRANSLATION_INDICES = [39, 40, 41]
RDT_GUIDED_ACTION_INDICES = [39, 40, 41, 42, 43, 44, 10]
RDT_GUIDANCE_SIGN = 1.0
RDT_DIVERSITY_SIGN = -1.0
EDS_INITIAL_SAMPLING_MODES = {"iid", "rbf_diverse_denoise"}
EDS_TRUNCATED_ROLLOUT_MODES = {"baseline", "rbf_diverse"}


@dataclass(frozen=True)
class _EDSConfig:
    population_size: int = 16
    use_cem: bool = False
    cem_iters: int = 20
    num_elites: int = 32
    temperature: float = 0.1
    renoise_t_max: int = 5
    renoise_t_min: int = 1
    initial_population_cache: Optional[str] = None
    ed_population_cache: Optional[str] = None
    use_initial_cache: bool = False
    save_initial_cache: bool = False
    save_ed_cache: bool = False
    reward_mode: str = "normal"
    shuffle_seed: int = 0
    mechanism_pretest: Optional[dict] = None
    initial_sampling_mode: str = "iid"
    initial_diversity_scale: float = 1.0
    initial_diversity_start_ratio: Optional[float] = None
    initial_diversity_fallback: str = "iid"
    initial_cache_metadata: bool = True
    truncated_rollout_mode: str = "baseline"
    rollout_diversity_scale: float = 1.0
    rollout_diversity_start_ratio: float = 0.8
    rollout_diversity_iters: int | str = 0
    rollout_diversity_skip_final_steps: int = 0
    parent_weighting_mode: str = "legacy_temperature"
    selection_ess_target_ratio: float = 0.6
    selection_beta_max: float = 100.0
    selection_bisection_steps: int = 24
    parent_coverage_mode: str = "none"
    parent_anchor_count: int = 0
    parent_anchor_reward_quantile: float = 0.5
    elite_carryover_count: int = 0
    rollout_diversity_control_mode: str = "fixed"
    rollout_diversity_target_ratio: float = 1.0
    rollout_diversity_band_ratio: float = 0.2
    rollout_diversity_scale_min: float = 0.0
    rollout_diversity_scale_max: float = 20.0
    rollout_diversity_decay_floor: float = 0.25
    chunk_population_mode: str = "fresh"
    chunk_memory_fraction: float = 0.0
    chunk_memory_renoise_steps: int = 2
    chunk_memory_reward_guard_quantile: float = 0.25
    search_schedule_mode: str = "legacy_linear"
    adaptive_min_cem_iters: int = 4
    adaptive_early_stop_patience: int = 2
    adaptive_reward_improvement_eps: float = 1e-3


@dataclass(frozen=True)
class EDSParentPlan:
    elite_indices: Tensor
    offspring_parent_indices: Tensor
    offspring_sources: tuple[str, ...]
    info: dict


@dataclass(frozen=True)
class EDSRolloutDiversityDecision:
    scale: float
    enabled: bool
    reason: str
    reference: float
    low: float
    high: float
    current: float
    reward_confidence: float


@dataclass
class EDSChunkMemory:
    population: Tensor
    costs: Tensor
    stage: int
    global_step: int


def _safe_initial_sampler_int(value) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return 0


def _safe_initial_sampler_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        value_f = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return value_f if math.isfinite(value_f) else None


def _safe_initial_sampler_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    if isinstance(value, int) and not isinstance(value, bool):
        return value == 1 if value in {0, 1} else False
    if isinstance(value, float):
        try:
            if math.isfinite(value) and value in {0.0, 1.0}:
                return bool(value)
        except (TypeError, ValueError, OverflowError):
            return False
    return False


def _safe_initial_sampler_mode(value, fallback: str) -> str:
    if isinstance(value, str) and value in EDS_INITIAL_SAMPLING_MODES:
        return value
    return fallback


def _safe_initial_sampler_float_field(
    info: Mapping,
    field_name: str,
    fallback,
) -> Optional[float]:
    if field_name in info:
        return _safe_initial_sampler_float(info.get(field_name))
    return _safe_initial_sampler_float(fallback)


def _populate_initial_sampler_metrics(
    metrics: EDSChunkMetrics,
    cfg: _EDSConfig,
    info: Optional[Mapping],
) -> None:
    initial_sampler_info = info if isinstance(info, Mapping) else {}
    metrics.initial_sampling_mode = _safe_initial_sampler_mode(
        initial_sampler_info.get("initial_sampling_mode"),
        cfg.initial_sampling_mode,
    )
    metrics.initial_diversity_scale = _safe_initial_sampler_float_field(
        initial_sampler_info,
        "initial_diversity_scale",
        cfg.initial_diversity_scale,
    )
    metrics.initial_diversity_start_ratio = _safe_initial_sampler_float_field(
        initial_sampler_info,
        "initial_diversity_start_ratio",
        cfg.initial_diversity_start_ratio,
    )
    metrics.initial_diversity_steps = _safe_initial_sampler_int(
        initial_sampler_info.get("initial_diversity_steps")
    )
    metrics.initial_diversity_grad_norm_mean = _safe_initial_sampler_float(
        initial_sampler_info.get("initial_diversity_grad_norm_mean")
    )
    metrics.initial_diversity_grad_norm_max = _safe_initial_sampler_float(
        initial_sampler_info.get("initial_diversity_grad_norm_max")
    )
    metrics.initial_diversity_grad_failure_count = _safe_initial_sampler_int(
        initial_sampler_info.get("initial_diversity_grad_failure_count")
    )
    metrics.initial_diversity_fallback_used = _safe_initial_sampler_bool(
        initial_sampler_info.get("initial_diversity_fallback_used")
    )
    fallback_reason = initial_sampler_info.get("initial_diversity_fallback_reason")
    metrics.initial_diversity_fallback_reason = (
        str(fallback_reason) if fallback_reason is not None else None
    )
    metrics.initial_sampler_latency_s = _safe_initial_sampler_float(
        initial_sampler_info.get("initial_sampler_latency_s")
    )


def _parse_eds_bool(value, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    raise ValueError(
        f"EDS {field_name} must be a bool or one of true/false, 1/0, yes/no"
    )


def _parse_eds_int(value, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"EDS {field_name} must be an integer, not a bool")
    if isinstance(value, str):
        try:
            return int(value.strip())
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"EDS {field_name} must be an integer") from exc
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        value_f = float(value)
        if math.isfinite(value_f) and value_f.is_integer():
            return int(value_f)
    raise ValueError(f"EDS {field_name} must be an integer")


def _parse_eds_float(value, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"EDS {field_name} must be a number, not a bool")
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"EDS {field_name} must be a number") from exc


def _parse_eds_rollout_diversity_iters(value) -> int | str:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "all":
            return "all"
        try:
            parsed = int(normalized)
        except ValueError as exc:
            raise ValueError(
                "EDS rollout_diversity_iters must be 0, a positive int, or 'all'"
            ) from exc
        value = parsed
    if isinstance(value, bool):
        raise ValueError("EDS rollout_diversity_iters must not be a bool")
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise ValueError(
                "EDS rollout_diversity_iters must be 0, a positive int, or 'all'"
            )
        value = int(value)
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(
            "EDS rollout_diversity_iters must be 0, a positive int, or 'all'"
        ) from exc
    if parsed < 0:
        raise ValueError("EDS rollout_diversity_iters must be >= 0 or 'all'")
    return parsed


def _resolve_vls_config(vls_config: Optional[dict], *, default_sample_batch_size: int) -> dict:
    cfg = dict(vls_config or {})
    cfg.setdefault("sample_batch_size", default_sample_batch_size)
    cfg.setdefault("guide_scale", 1.0)
    cfg.setdefault("sigmoid_k", 12.0)
    cfg.setdefault("sigmoid_x0", 0.7)
    cfg.setdefault("start_ratio", None)
    cfg.setdefault("use_diversity", True)
    cfg.setdefault("diversity_scale", 1.0)
    cfg.setdefault("MCMC_steps", 4)
    cfg.setdefault("use_fkd", False)
    cfg.setdefault("fkd", None)
    return cfg


def _merge_legacy_vls_kwargs(vls_config: Optional[dict], **legacy_kwargs) -> dict:
    """Merge legacy flat VLS kwargs over the preferred grouped vls_config."""
    cfg = dict(vls_config or {})
    for field, value in legacy_kwargs.items():
        if value is None:
            continue
        if field == "fkd_config":
            cfg["fkd"] = value
        else:
            cfg[field] = value
    return cfg


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


def _dedupe_ordered(paths: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        deduped.append(path)
    return deduped


def _rdt_weight_search_dirs(pretrained_path: str, weight_variant: Optional[str]) -> list[str]:
    dirs = []
    if weight_variant:
        dirs.extend(
            [
                os.path.join(pretrained_path, weight_variant),
                os.path.join(pretrained_path, "rdt", weight_variant),
            ]
        )
    dirs.extend([pretrained_path, os.path.join(pretrained_path, "rdt")])
    return _dedupe_ordered(dirs)


def _resolve_rdt_weight_file(pretrained_path: str, weight_variant: Optional[str]) -> tuple[str, str]:
    """Return ``(weight_file, checkpoint_root)`` for a local RDT checkpoint."""
    path = Path(pretrained_path)
    weight_names = (
        "model.safetensors",
        "pytorch_model.bin",
        "mp_rank_00_model_states.pt",
        "rdt-1b.pt",
    )

    if path.is_file():
        if path.name not in weight_names and path.suffix not in {".safetensors", ".bin", ".pt"}:
            raise FileNotFoundError(f"Unsupported RDT checkpoint file: {pretrained_path}")
        checkpoint_root = path.parent
        if weight_variant and checkpoint_root.name == weight_variant:
            checkpoint_root = checkpoint_root.parent
        return str(path), str(checkpoint_root)

    weight_search_dirs = _rdt_weight_search_dirs(str(path), weight_variant)
    for search_root in weight_search_dirs:
        search_path = Path(search_root)
        if not search_path.is_dir():
            continue
        for fname in weight_names:
            candidate = search_path / fname
            if candidate.is_file():
                return str(candidate), str(path)

    raise FileNotFoundError(
        f"No RDT weight file found for variant '{weight_variant}' under {pretrained_path}. "
        f"Searched: {weight_search_dirs}. Looked for: {weight_names}."
    )


def _resolve_rdt_checkpoint_paths(pretrained_path: str, weight_variant: Optional[str]) -> tuple[str, str]:
    """Return ``(checkpoint_root, weight_file)`` for smoke checks and callers."""
    weight_file, checkpoint_root = _resolve_rdt_weight_file(pretrained_path, weight_variant)
    return checkpoint_root, weight_file


def _looks_like_local_path(path: str) -> bool:
    return path.startswith(("/", "./", "../", "~"))


def _normalize_local_path(label: str, path: str) -> str:
    if not _looks_like_local_path(path):
        return path
    expanded = Path(path).expanduser()
    if not expanded.exists():
        raise FileNotFoundError(f"Missing RDT {label} path: {path}")
    return str(expanded)


def _normalize_text_encoder_path(text_encoder: str) -> str:
    text_encoder = _normalize_local_path("text encoder", text_encoder)
    if Path(text_encoder).name == "models--google--t5-v1_1-xxl":
        return _resolve_hf_cache_snapshot(
            "T5 cache root",
            text_encoder,
            required_files=("config.json",),
        )
    return text_encoder


def _rdt_text_encoder_arg_and_load_path(text_encoder: str) -> tuple[str, Optional[str]]:
    """Return ``(rdt_model_arg, hf_loader_path)`` for the T5 encoder.

    RDT's T5Embedder asserts the symbolic model id, while Transformers can be
    redirected to a local snapshot through the temporary from_pretrained patch.
    """
    resolved = _normalize_text_encoder_path(text_encoder)
    if _looks_like_local_path(resolved):
        return "google/t5-v1_1-xxl", resolved
    return resolved, None


def _resolve_hf_cache_snapshot(label: str, cache_root: str, required_files: tuple[str, ...]) -> str:
    root = Path(cache_root)
    snapshots_dir = root / "snapshots"
    if not snapshots_dir.is_dir():
        raise FileNotFoundError(f"Cannot resolve {label} {cache_root}: missing snapshots directory")

    valid_snapshots = []
    for snapshot in snapshots_dir.iterdir():
        if not snapshot.is_dir():
            continue
        if all((snapshot / required_file).is_file() for required_file in required_files):
            valid_snapshots.append(snapshot)
    if not valid_snapshots:
        required = " and ".join(required_files)
        raise FileNotFoundError(f"Cannot resolve {label} {cache_root}: no snapshot contains {required}")

    valid_snapshots.sort(key=lambda path: (path.stat().st_mtime, path.name), reverse=True)
    return str(valid_snapshots[0])


def _resolve_vision_encoder_path(vision_encoder: str) -> str:
    vision_encoder = _normalize_local_path("vision encoder", vision_encoder)
    if Path(vision_encoder).name != "models--google--siglip-so400m-patch14-384":
        return vision_encoder

    return _resolve_hf_cache_snapshot(
        "SigLIP cache root",
        vision_encoder,
        required_files=("preprocessor_config.json", "config.json"),
    )


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
        action_mask = torch.zeros(
            (1, unified_action_dim),
            device=device,
            dtype=dtype,
        )
        action_mask[0, action_indices] = 1.0
        action_active = torch.where(action_mask[0] > 0)[0].detach().cpu().tolist()
        if action_active != ACTIVE_ACTION_INDICES_SORTED:
            raise ValueError(
                f"LIBERO action mask mismatch: expected {ACTIVE_ACTION_INDICES_SORTED}, got {action_active}"
            )
        ctrl_freqs = torch.tensor([real.control_frequency], device=device)

        # ── Language ─────────────────────────────────────────────────────────
        text_embeds = text_embeds.to(device, dtype=dtype)
        lang_attn_mask = torch.ones(
            text_embeds.shape[:2], dtype=torch.bool, device=device
        )

        # ── Adapt to RDTRunner hidden size ────────────────────────────────────
        state_tokens = torch.cat([states, action_mask.unsqueeze(1)], dim=2)
        lang_cond, img_cond, state_traj = real.policy.adapt_conditions(
            text_embeds, image_embeds, state_tokens
        )

        return {
            "lang_cond": lang_cond,
            "lang_attn_mask": lang_attn_mask,
            "img_cond": img_cond,
            "state_traj": state_traj,
            "action_mask": action_mask.unsqueeze(1),  # (1, 1, unified_action_dim)
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
    """RDT-1B LIBERO policy wrapper with unguided action chunk inference."""

    name = "rdt_steer"

    def __init__(self, rdt_model, num_inference_steps: int = 5) -> None:
        self._rdt_model = rdt_model
        self._num_inference_steps = num_inference_steps
        self._device = torch.device("cpu")

        self._adapter: Optional[BaseEnvAdapter] = None
        self._obs_processor: Optional[RDTLiberoObsProcessor] = None
        self._sample_batch_size: int = 1
        self._action_chunk_horizon: int = 8
        self._fail_on_zero_language_embedding = False

        self._cached_action_chunk: Optional[Tensor] = None
        self._last_normalized_reward: float = 0.0
        self._last_scale: float = 0.0
        self._stage_init_reward: Optional[float] = None
        self._last_raw_reward: float = 0.0
        self._current_alpha_t: float = 0.5
        self._cached_action_steps_remaining: int = 0
        self._debug_first_step = False
        self._action_summary_logged = False
        self._last_visualization_action_candidates: Optional[Tensor] = None
        self._last_eds_metrics: Optional[dict] = None
        self._last_eds_artifacts: Optional[dict] = None
        self._last_eds_initial_sampler_info: Optional[dict] = None
        self._last_eds_mechanism_trace: Optional[EDSMechanismTrace] = None
        self._eds_chunk_memory: Optional[EDSChunkMemory] = None
        self._eds_chunk_memory_reset_reason: Optional[str] = None

        # Locate the inner DiT score network once at construction.
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
        # Stub model or flat structure: check common names.
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
        vision_encoder: str = "google/siglip-so400m-patch14-384",
        text_encoder: str = "google/t5-v1_1-xxl",
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

        is_local_checkpoint_path = _looks_like_local_path(pretrained_path)
        path_obj = Path(pretrained_path).expanduser() if is_local_checkpoint_path else Path(pretrained_path)
        if is_local_checkpoint_path:
            if not path_obj.exists():
                raise FileNotFoundError(f"Missing RDT checkpoint path: {pretrained_path}")
            pretrained_path = str(path_obj)
        if path_obj.suffix in {".safetensors", ".bin", ".pt"} and not path_obj.is_file():
            raise FileNotFoundError(f"Missing RDT checkpoint file: {pretrained_path}")

        if not os.path.isdir(pretrained_path) and not path_obj.is_file():
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

        weight_file, checkpoint_root = _resolve_rdt_weight_file(pretrained_path, weight_variant)
        weight_search_dirs = _rdt_weight_search_dirs(checkpoint_root, weight_variant)
        log.warning(
            f"[RDT_GT_CKPT] model_root={checkpoint_root} "
            f"weight_file={weight_file} variant={weight_variant}"
        )
        log.info(f"Using weight file: {weight_file}")

        try:
            import yaml
            from scripts.maniskill_model import create_model
        except ImportError:
            raise ImportError(
                "Cannot import RoboticDiffusionTransformerModel. "
                "Ensure third_party/rdt/ is initialized: git submodule update --init"
            )

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
            "pretrained_path": checkpoint_root,
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

        text_encoder, text_encoder_load_path = _rdt_text_encoder_arg_and_load_path(text_encoder)
        vision_encoder = _resolve_vision_encoder_path(vision_encoder)

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
                if (
                    text_encoder_load_path is not None
                    and args
                    and args[0] == "google/t5-v1_1-xxl"
                    and getattr(_orig, "__self__", None) in {_T5E, _AT}
                ):
                    args = (text_encoder_load_path, *args[1:])
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
        self._fail_on_zero_language_embedding = bool(
            policy_config.get("fail_on_zero_language_embedding", False)
        )
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
        self._debug_first_step = debug_first_step
        self._action_summary_logged = False
        log.info(
            f"post_init wired: adapter={type(self._adapter).__name__}, "
            f"undo_libero_flip={self._obs_processor.undo_preprocessor_flip}, "
            f"sample_batch_size={self._sample_batch_size}, "
            f"action_chunk_horizon={self._action_chunk_horizon}, "
            f"fail_on_zero_language_embedding={self._fail_on_zero_language_embedding}"
        )

    def _get_lang_embed(self, task: str) -> Tensor:
        real = None
        try:
            real = object.__getattribute__(self._rdt_model, "_real")
        except Exception:
            real = None
        if real is not None and callable(getattr(real, "encode_instruction", None)):
            embed = real.encode_instruction(task, device=str(self.device))
            embed = embed.float().to(self.device)
        else:
            embed = torch.zeros(1, 1, 4096, device=self.device)

        if self._fail_on_zero_language_embedding:
            finite = torch.isfinite(embed).all()
            max_abs = embed.detach().abs().max()
            if not bool(finite.item()) or float(max_abs.item()) <= 1e-8:
                raise RuntimeError(
                    f"RDT zero language embedding for task {task!r}; "
                    "check text encoder loading or disable fail_on_zero_language_embedding."
                )

        return embed

    def to(self, device) -> "RDTSteer":
        self._device = torch.device(device)
        if isinstance(self._rdt_model, nn.Module):
            self._rdt_model = self._rdt_model.to(device)
        self._dit = self._find_dit(self._rdt_model)
        return self

    def eval(self) -> "RDTSteer":
        if isinstance(self._rdt_model, nn.Module):
            self._rdt_model.eval()
        return self

    def reset(self) -> None:
        self.reset_eds_chunk_memory("episode_reset")
        self._cached_action_chunk = None
        self._cached_action_steps_remaining = 0
        self._stage_init_reward = None
        self._last_normalized_reward = 0.0
        self._last_scale = 0.0
        self._last_raw_reward = 0.0
        self._current_alpha_t = 0.5
        self._action_summary_logged = False
        self._last_visualization_action_candidates = None
        self._last_eds_metrics = None
        self._last_eds_artifacts = None
        self._last_eds_initial_sampler_info = None
        self._last_eds_mechanism_trace = None
        if self._obs_processor is not None:
            self._obs_processor.reset()

    def reset_stage(self) -> None:
        self.reset_eds_chunk_memory("stage_change")
        self._stage_init_reward = None

    def reset_eds_chunk_memory(self, reason: str, *, warn: bool = False) -> None:
        self._eds_chunk_memory = None
        self._eds_chunk_memory_reset_reason = str(reason)
        if warn:
            log.warning(f"EDS chunk population memory reset: reason={reason}")

    def get_normalized_reward(self) -> float:
        return self._last_normalized_reward

    def get_last_scale(self) -> float:
        return self._last_scale

    def get_last_visualization_action_candidates(self) -> Optional[Tensor]:
        if self._last_visualization_action_candidates is None:
            return None
        return self._last_visualization_action_candidates.clone()

    def get_last_eds_metrics(self) -> Optional[dict]:
        if self._last_eds_metrics is None:
            return None
        return dict(self._last_eds_metrics)

    def get_last_eds_artifacts(self) -> Optional[dict]:
        if self._last_eds_artifacts is None:
            return None
        return dict(self._last_eds_artifacts)

    def get_last_eds_mechanism_trace(self) -> Optional[EDSMechanismTrace]:
        return self._last_eds_mechanism_trace

    @property
    def device(self) -> torch.device:
        try:
            return next(self._dit.parameters()).device
        except StopIteration:
            return self._device

    # ── Inference entry point ─────────────────────────────────────────────────

    def select_action(
        self,
        batch: dict,
        generate_new_chunk: bool = False,
        use_guidance: bool = False,
        keypoints: Optional[np.ndarray] = None,
        guidance_fns: Optional[List[Callable]] = None,
        guidance_type: str = "vls",
        vls_config: Optional[dict] = None,
        eds_config: Optional[dict] = None,
        guide_scale: Optional[float] = None,
        sample_batch_size: Optional[int] = None,
        use_diversity: Optional[bool] = None,
        diversity_scale: Optional[float] = None,
        MCMC_steps: Optional[int] = None,
        use_fkd: Optional[bool] = None,
        fkd_config: Optional[dict] = None,
        sigmoid_k: Optional[float] = None,
        sigmoid_x0: Optional[float] = None,
        start_ratio: Optional[float] = None,
        verbose: bool = False,
        global_step: int = 0,
        current_stage: int = 1,
    ) -> Tensor:
        if self._obs_processor is None:
            raise RuntimeError("RDTSteer.post_init must be called before select_action")

        self._obs_processor.observe(batch)
        should_sample = (
            generate_new_chunk
            or self._cached_action_chunk is None
            or self._cached_action_steps_remaining <= 0
        )

        if should_sample:
            self._last_visualization_action_candidates = None
            self._last_eds_metrics = None
            self._last_eds_artifacts = None
            self._last_eds_mechanism_trace = None
            converted = self._obs_processor.current()

            if use_guidance:
                text_embed = self._get_lang_embed(converted.task)
                merged_vls_config = _merge_legacy_vls_kwargs(
                    vls_config,
                    guide_scale=guide_scale,
                    sample_batch_size=sample_batch_size,
                    use_diversity=use_diversity,
                    diversity_scale=diversity_scale,
                    MCMC_steps=MCMC_steps,
                    use_fkd=use_fkd,
                    fkd_config=fkd_config,
                    sigmoid_k=sigmoid_k,
                    sigmoid_x0=sigmoid_x0,
                    start_ratio=start_ratio,
                )
                raw = self._predict_guided(
                    converted.state_128,
                    converted.state_mask_128,
                    converted.images,
                    text_embed,
                    keypoints=keypoints,
                    guidance_fns=guidance_fns,
                    guidance_type=guidance_type,
                    vls_config=merged_vls_config,
                    eds_config=eds_config,
                    verbose=verbose,
                    global_step=global_step,
                    current_stage=current_stage,
                )
            else:
                text_embed = self._get_lang_embed(converted.task)
                raw = self._predict_unguided(
                    converted.state_128,
                    converted.state_mask_128,
                    converted.images,
                    text_embed,
                    B=1,
                )

            self._cached_action_chunk = self._postprocess_actions(raw)
            self._cached_action_steps_remaining = self._cached_action_chunk.shape[1]

        self._cached_action_steps_remaining = max(0, self._cached_action_steps_remaining - 1)
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

    # ── Guided path ──────────────────────────────────────────────────────────

    def _predict_guided(
        self,
        state_128: Tensor,
        state_mask_128: Tensor,
        images: list,
        text_embed: Tensor,
        *,
        keypoints: Optional[np.ndarray],
        guidance_fns: Optional[List[Callable]],
        guidance_type: str,
        vls_config: Optional[dict],
        eds_config: Optional[dict],
        verbose: bool,
        global_step: int,
        current_stage: int,
    ) -> Tensor:
        device = self.device
        try:
            dtype = next(self._dit.parameters()).dtype
        except StopIteration:
            dtype = torch.float32

        cond = self._rdt_model.encode_inputs(state_128, state_mask_128, images, text_embed)
        unified_action_dim = int(cond["unified_action_dim"])
        if unified_action_dim != 128:
            raise ValueError(f"Expected unified action dim 128, got {unified_action_dim}")

        guidance_type = str(guidance_type or "vls").lower()
        if guidance_type not in {"vls", "eds"}:
            raise ValueError(
                f"Unsupported RDT guidance_type={guidance_type!r}; expected 'vls' or 'eds'"
            )

        resolved_vls_config = _resolve_vls_config(
            vls_config,
            default_sample_batch_size=self._sample_batch_size,
        )
        resolved_eds_config = None
        if guidance_type == "vls":
            B = max(1, int(resolved_vls_config["sample_batch_size"]))
        else:
            resolved_eds_config = self._resolve_eds_config_with_reference_defaults(eds_config)
            B = max(1, int(resolved_eds_config.population_size))

        if verbose:
            log_message = (
                f"[RDT_GUIDE] enabled=true guidance_type={guidance_type} "
                f"B={B} H={self._action_chunk_horizon} "
                f"pred_horizon=64 guided_slots={RDT_GUIDED_TRANSLATION_INDICES} "
                f"action_slots={RDT_GUIDED_ACTION_INDICES} "
                f"guidance_sign={RDT_GUIDANCE_SIGN} prediction_type=sample "
            )
            if guidance_type == "vls":
                log.info(
                    log_message
                    + f"use_diversity={resolved_vls_config['use_diversity']} "
                    + f"use_fkd={resolved_vls_config['use_fkd']}"
                )
            else:
                log.info(
                    log_message
                    + f"eds_population_size={resolved_eds_config.population_size} eds_loop=true"
                )
        pred_horizon = 64
        x_t = torch.randn(B, pred_horizon, unified_action_dim, device=device, dtype=dtype)

        keypoints_tensor = None
        if keypoints is not None:
            keypoints_tensor = torch.tensor(keypoints, device=device, dtype=dtype)

        if guidance_type == "vls":
            guided = self._vls_guided_denoise_loop(
                x_t=x_t,
                cond=cond,
                keypoints=keypoints_tensor,
                guidance_fns=guidance_fns,
                vls_config=resolved_vls_config,
                verbose=verbose,
                global_step=global_step,
                current_stage=current_stage,
            )
        else:
            guided = self._eds_guided_denoise_loop(
                x_t=x_t,
                cond=cond,
                keypoints=keypoints_tensor,
                guidance_fns=guidance_fns,
                eds_config=resolved_eds_config,
                verbose=verbose,
                global_step=global_step,
                current_stage=current_stage,
            )
        action_mask = cond["action_mask"].expand(guided.shape[0], pred_horizon, unified_action_dim).to(device=device, dtype=dtype)
        return (guided * action_mask).float()

    def _select_fkd_x0_source(self, *, model_output: Tensor, step_output, x_t: Tensor) -> tuple[Tensor, str]:
        if step_output is not None:
            pred_original = getattr(step_output, "pred_original_sample", None)
            if pred_original is not None:
                return pred_original, "scheduler_pred_original"
        return model_output, "model_output"

    def _reset_scheduler_particle_history_after_resample(self, scheduler) -> None:
        model_outputs = getattr(scheduler, "model_outputs", None)
        if isinstance(model_outputs, list):
            scheduler.model_outputs = [None] * len(model_outputs)
        if hasattr(scheduler, "lower_order_nums"):
            scheduler.lower_order_nums = 0

    def _fkd_resample_changed_particles(self, before: Tensor, after: Tensor) -> bool:
        return after is not before

    def _trajectory_reward_slice(self, trajs: Tensor, slice_kind: str) -> Tensor:
        if slice_kind == "keypoint":
            return trajs[:, : self._action_chunk_horizon, :3]
        if slice_kind == "fkd":
            return trajs[:, 1 : self._action_chunk_horizon, :3]
        if slice_kind == "eds":
            return trajs[:, 1 : self._action_chunk_horizon, :3]
        if slice_kind == "diversity":
            return trajs[:, 1:, :3]
        raise ValueError(f"Unknown trajectory reward slice kind: {slice_kind}")

    def _score_particles(
        self,
        samples: Tensor,
        keypoints: Optional[Tensor],
        guidance_fns: Optional[List[Callable]],
        *,
        slice_kind: str,
    ) -> Tensor:
        if keypoints is None or not guidance_fns:
            return torch.zeros(samples.shape[0], device=samples.device, dtype=samples.dtype)
        trajs = self._trajectory_reward_slice(self._rdt_sample_to_trajectory_3d(samples), slice_kind)
        rewards = []
        for b in range(trajs.shape[0]):
            reward = sum(fn(keypoints, trajs[b : b + 1]) for fn in guidance_fns)
            if torch.is_tensor(reward):
                rewards.append(reward.detach().to(device=samples.device, dtype=samples.dtype).reshape(()))
            else:
                rewards.append(torch.tensor(float(reward), device=samples.device, dtype=samples.dtype))
        return torch.stack(rewards)

    def _init_fkd(
        self,
        *,
        B: int,
        timesteps: Tensor,
        start_step: int,
        keypoints: Optional[Tensor],
        guidance_fns: Optional[List[Callable]],
        fkd_config: Optional[dict],
        device: torch.device,
    ) -> Optional[FKD]:
        if fkd_config is None or B <= 1 or keypoints is None or not guidance_fns:
            return None

        def reward_fn(x0_preds: Tensor) -> Tensor:
            return self._score_particles(x0_preds, keypoints, guidance_fns, slice_kind="fkd")

        return FKD(
            potential_type=fkd_config.get("potential_type", "max"),
            lmbda=fkd_config.get("lmbda", 10.0),
            num_particles=B,
            adaptive_resampling=fkd_config.get("adaptive_resampling", True),
            resample_frequency=fkd_config.get("resample_frequency", 5),
            resampling_t_start=int(start_step),
            resampling_t_end=int(timesteps[-1].item()),
            timesteps=timesteps,
            reward_fn=reward_fn,
            reward_min_value=float("-inf"),
            device=device,
        )

    def _vls_guided_denoise_loop(
        self,
        *,
        x_t: Tensor,
        cond: dict,
        keypoints: Optional[Tensor],
        guidance_fns: Optional[List[Callable]],
        vls_config: dict,
        verbose: bool,
        global_step: int,
        current_stage: int,
    ) -> Tensor:
        guide_scale = float(vls_config.get("guide_scale", 1.0))
        sigmoid_k = float(vls_config.get("sigmoid_k", 12.0))
        sigmoid_x0 = float(vls_config.get("sigmoid_x0", 0.7))
        start_ratio = vls_config.get("start_ratio", None)
        use_diversity = bool(vls_config.get("use_diversity", True))
        diversity_scale = float(vls_config.get("diversity_scale", 1.0))
        MCMC_steps = int(vls_config.get("MCMC_steps", 4))
        use_fkd = bool(vls_config.get("use_fkd", False))
        fkd_config = vls_config.get("fkd", None)
        scheduler = self._noise_scheduler
        scheduler.set_timesteps(self._num_inference_steps)

        use_keypoint_guidance = guidance_fns is not None and len(guidance_fns) > 0 and keypoints is not None
        reward_history = []
        start_step = self._resolve_start_step(scheduler.timesteps, start_ratio)
        terminal_t = int(scheduler.timesteps[-1].item())
        fkd = self._init_fkd(
            B=x_t.shape[0],
            timesteps=scheduler.timesteps,
            start_step=start_step,
            keypoints=keypoints,
            guidance_fns=guidance_fns,
            fkd_config=fkd_config if use_fkd else None,
            device=x_t.device,
        )

        for i, t in enumerate(scheduler.timesteps):
            with torch.no_grad():
                model_output = self._dit(x_t, t, cond)

            if use_diversity and int(t.item()) > start_step and x_t.shape[0] > 1:
                div_grad = self._compute_diversity_gradient(x_t)
                if div_grad is not None:
                    masked_div = self._mask_guidance_gradient(div_grad).to(device=model_output.device, dtype=model_output.dtype)
                    model_output[:, :, RDT_GUIDED_TRANSLATION_INDICES] += (
                        RDT_DIVERSITY_SIGN
                        * float(diversity_scale)
                        * masked_div[:, :, RDT_GUIDED_TRANSLATION_INDICES]
                    )
            elif use_keypoint_guidance and int(t.item()) <= start_step:
                kp_grad, reward_value = self._compute_keypoint_gradient(
                    x_t,
                    keypoints,
                    guidance_fns,
                    verbose=(verbose and i == int(len(scheduler.timesteps) * 0.8)),
                )
                if kp_grad is not None:
                    normalized_reward = self._normalized_reward_from_value(reward_value)
                    reward_history.append((i, reward_value, normalized_reward))
                    scale = self._adaptive_scale_for_scheduler_t(
                        scheduler,
                        t,
                        guide_scale,
                        sigmoid_k,
                        sigmoid_x0,
                        model_output.device,
                        model_output.dtype,
                    )
                    model_output = self._apply_keypoint_guidance(model_output, kp_grad, scale)

            step_output = scheduler.step(model_output, t, x_t)
            x0_for_reward, _ = self._select_fkd_x0_source(
                model_output=model_output,
                step_output=step_output,
                x_t=x_t,
            )
            x_t = step_output.prev_sample.to(dtype=model_output.dtype)

            if fkd is not None and int(t.item()) <= start_step and int(t.item()) != terminal_t:
                before_resample = x_t
                x_t, _ = fkd.resample(
                    sampling_idx=int(t.item()),
                    latents=x_t,
                    x0_preds=x0_for_reward,
                )
                if self._fkd_resample_changed_particles(before_resample, x_t):
                    self._reset_scheduler_particle_history_after_resample(scheduler)

        if reward_history and self._stage_init_reward is None:
            self._stage_init_reward = reward_history[-1][1]

        if not torch.isfinite(x_t).all():
            raise ValueError("Guided RDT latent contains non-finite values")

        selected = self._select_particle_for_execution(
            x_t,
            keypoints=keypoints,
            guidance_fns=guidance_fns,
            fkd=fkd,
        )
        ordered_candidates = self._order_particles_for_visualization(
            x_t,
            keypoints=keypoints,
            guidance_fns=guidance_fns,
            fkd=fkd,
        )
        self._last_visualization_action_candidates = self._decode_visualization_action_candidates(
            ordered_candidates
        )
        return selected

    def _expand_action_mask_for_population(self, action_mask: Tensor, population: Tensor) -> Tensor:
        return action_mask.expand(population.shape[0], population.shape[1], population.shape[2]).to(
            device=population.device,
            dtype=population.dtype,
        )

    def _apply_action_mask(self, actions: Tensor, cond: dict) -> Tensor:
        action_mask = self._expand_action_mask_for_population(cond["action_mask"], actions)
        return actions * action_mask

    def _eds_score_population_as_cost(
        self,
        samples: Tensor,
        *,
        keypoints: Optional[Tensor],
        guidance_fns: Optional[List[Callable]],
        reward_mode: str = "normal",
        shuffle_seed: int = 0,
    ) -> tuple[Tensor, dict]:
        reward_mode = str(reward_mode or "normal")
        valid_modes = {"normal", "zero", "shuffled_keypoints", "inverted"}
        if reward_mode not in valid_modes:
            raise ValueError(f"Unsupported EDS reward_mode={reward_mode!r}")

        scoring_keypoints = keypoints
        if (
            reward_mode == "shuffled_keypoints"
            and keypoints is not None
            and keypoints.shape[0] > 1
        ):
            generator = torch.Generator(device=keypoints.device)
            generator.manual_seed(int(shuffle_seed))
            perm = torch.randperm(
                keypoints.shape[0],
                generator=generator,
                device=keypoints.device,
            )
            scoring_keypoints = keypoints.index_select(0, perm)

        rewards = self._score_particles(
            samples,
            scoring_keypoints,
            guidance_fns,
            slice_kind="eds",
        )
        if reward_mode == "zero":
            rewards = torch.zeros_like(rewards)
        elif reward_mode == "inverted":
            rewards = -rewards
        costs = -rewards
        return costs.detach(), {"rewards": rewards.detach()}

    def _save_eds_population_cache(self, population: Tensor, cache_path: Optional[str], *, label: str) -> None:
        if cache_path is None:
            raise ValueError(f"EDS {label} save requires a cache path")
        path = Path(cache_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({label: population.detach().cpu()}, path)

    def _save_eds_initial_population_cache(
        self,
        population: Tensor,
        cfg: _EDSConfig,
        info: dict,
    ) -> None:
        if cfg.initial_population_cache is None:
            raise ValueError("EDS initial_population save requires a cache path")
        path = Path(cfg.initial_population_cache)
        path.parent.mkdir(parents=True, exist_ok=True)
        metadata = self._eds_initial_cache_metadata(cfg, info)
        torch.save(
            {"initial_population": population.detach().cpu(), "metadata": metadata},
            path,
        )

    def _eds_validate_population_scores(self, scores: Tensor, expected_size: int) -> Tensor:
        if not torch.is_tensor(scores):
            raise ValueError("EDS population scores must be a torch.Tensor")
        if scores.ndim != 1:
            raise ValueError(
                f"EDS population scores must be 1-D with length {expected_size}, got shape {tuple(scores.shape)}"
            )
        if scores.shape[0] != int(expected_size):
            raise ValueError(
                f"EDS population scores length {scores.shape[0]} != expected {int(expected_size)}"
            )
        if not torch.isfinite(scores).all():
            raise ValueError("EDS population scores must be finite")
        return scores.detach()

    def _eds_sampling_probabilities_from_cost(self, costs: Tensor, temperature: float) -> Tensor:
        if not torch.is_tensor(costs):
            raise ValueError("EDS sampling costs must be a torch.Tensor")
        if costs.ndim != 1:
            raise ValueError(f"EDS sampling costs must be 1-D, got shape {tuple(costs.shape)}")
        if costs.numel() == 0:
            raise ValueError("EDS sampling costs must be non-empty")
        if not torch.isfinite(costs).all():
            raise ValueError("EDS sampling costs must be finite")
        if not math.isfinite(float(temperature)) or float(temperature) <= 0.0:
            raise ValueError("EDS sampling temperature must be finite and positive")

        logits = (-costs.detach()).to(dtype=torch.float64) * float(temperature)
        probabilities = torch.softmax(logits, dim=0).to(device=costs.device, dtype=torch.float32)
        probability_mass = probabilities.sum()
        if (
            not torch.isfinite(probabilities).all()
            or not torch.isfinite(probability_mass)
            or float(probability_mass.detach().cpu().item()) <= 0.0
        ):
            raise ValueError("EDS sampling probabilities must be finite with positive mass")
        return probabilities / probability_mass

    def _eds_robust_normalize_rewards(self, rewards: Tensor) -> tuple[Tensor, bool]:
        if not torch.is_tensor(rewards):
            raise ValueError("EDS rewards must be a torch.Tensor")
        if rewards.ndim != 1:
            raise ValueError(f"EDS rewards must be 1-D, got shape {tuple(rewards.shape)}")
        if rewards.numel() == 0:
            raise ValueError("EDS rewards must be non-empty")
        if not torch.isfinite(rewards).all():
            raise ValueError("EDS rewards must be finite")

        detached_rewards = rewards.detach().to(dtype=torch.float64)
        magnitude = detached_rewards.abs().max().clamp_min(1.0)
        scaled_rewards = detached_rewards / magnitude
        scaled_threshold = 1e-8 / magnitude
        median = scaled_rewards.median()
        mad = (scaled_rewards - median).abs().median()
        scale = 1.4826 * mad
        if bool((scale <= scaled_threshold).item()):
            scale = scaled_rewards.std(unbiased=False)
        if not torch.isfinite(scale) or bool((scale <= scaled_threshold).item()):
            return torch.zeros_like(detached_rewards), True

        normalized_rewards = (scaled_rewards - median) / scale
        normalized_rewards = torch.nan_to_num(
            normalized_rewards,
            nan=0.0,
            posinf=torch.finfo(torch.float64).max,
            neginf=torch.finfo(torch.float64).min,
        )
        if not torch.isfinite(normalized_rewards).all():
            raise ValueError("EDS normalized rewards must be finite")
        return normalized_rewards, False

    def _eds_rollout_reward_confidence(self, rewards: Tensor) -> float:
        if not torch.is_tensor(rewards):
            raise ValueError("EDS rollout rewards must be a torch.Tensor")
        if rewards.ndim != 1:
            raise ValueError(
                f"EDS rollout rewards must be 1-D, got shape {tuple(rewards.shape)}"
            )
        if rewards.numel() == 0:
            raise ValueError("EDS rollout rewards must be non-empty")
        if not rewards.dtype.is_floating_point:
            raise ValueError("EDS rollout rewards must be floating-point")
        if not torch.isfinite(rewards).all():
            raise ValueError("EDS rollout rewards must be finite")

        eps = 1e-12
        detached_rewards = rewards.detach().to(dtype=torch.float64)
        magnitude = detached_rewards.abs().max().clamp_min(1.0)
        scaled_rewards = detached_rewards / magnitude
        scaled_eps = torch.tensor(
            eps,
            device=scaled_rewards.device,
            dtype=scaled_rewards.dtype,
        ) / magnitude
        reward_median = scaled_rewards.median()
        mad = (scaled_rewards - reward_median).abs().median()
        scale = 1.4826 * mad
        if bool((scale <= scaled_eps).item()):
            scale = scaled_rewards.std(unbiased=False)
        if not torch.isfinite(scale) or bool((scale <= scaled_eps).item()):
            return 0.0

        denominator = torch.maximum(3.0 * scale, scaled_eps)
        confidence = ((scaled_rewards.max() - reward_median) / denominator).clamp(
            0.0,
            1.0,
        )
        confidence_value = float(confidence.detach().cpu().item())
        if not math.isfinite(confidence_value):
            raise ValueError("EDS rollout reward confidence must be finite")
        return confidence_value

    def _eds_resolve_renoise_steps(
        self,
        *,
        cfg: _EDSConfig,
        iter_idx: int,
        reward_improvement: Optional[float],
        diversity_band_state: str,
        best_lineage_stable: bool,
    ) -> tuple[int, str]:
        if (
            isinstance(iter_idx, bool)
            or not isinstance(iter_idx, Integral)
            or not 0 <= int(iter_idx) < int(cfg.cem_iters)
        ):
            raise ValueError("EDS iter_idx must be an integer in [0, cem_iters)")
        if reward_improvement is not None and (
            isinstance(reward_improvement, bool)
            or not isinstance(reward_improvement, Real)
            or not math.isfinite(float(reward_improvement))
        ):
            raise ValueError("EDS reward_improvement must be None or finite")
        if diversity_band_state not in {"below_band", "in_band", "above_band"}:
            raise ValueError(
                "EDS diversity_band_state must be below_band, in_band, or above_band"
            )
        if cfg.search_schedule_mode == "legacy_linear":
            schedule = np.linspace(
                cfg.renoise_t_max,
                cfg.renoise_t_min,
                cfg.cem_iters,
            ).astype(int)
            raw_steps = int(schedule[int(iter_idx)])
            reason = "legacy_linear"
        elif int(iter_idx) == 0:
            raw_steps = int(cfg.renoise_t_max)
            reason = "adaptive_initial_max"
        elif (
            diversity_band_state == "below_band"
            and (
                reward_improvement is None
                or float(reward_improvement)
                <= float(cfg.adaptive_reward_improvement_eps)
            )
        ):
            raw_steps = 3
            reason = "adaptive_diversity_recovery"
        elif (
            diversity_band_state == "in_band"
            and bool(best_lineage_stable)
            and reward_improvement is not None
            and float(reward_improvement)
            > float(cfg.adaptive_reward_improvement_eps)
        ):
            raw_steps = 1
            reason = "adaptive_stable_improving"
        else:
            raw_steps = 2
            reason = "adaptive_uncertain"

        return (
            int(max(cfg.renoise_t_min, min(raw_steps, cfg.renoise_t_max))),
            reason,
        )

    def _eds_best_lineage_is_stable(
        self,
        *,
        full_parent_indices: Tensor,
        current_best_idx: int,
        previous_best_idx: int,
    ) -> bool:
        if not torch.is_tensor(full_parent_indices) or full_parent_indices.ndim != 1:
            raise ValueError("EDS full_parent_indices must be a 1-D tensor")
        current_idx = int(current_best_idx)
        if current_idx < 0 or current_idx >= int(full_parent_indices.numel()):
            raise ValueError("EDS current best index is outside full parent mapping")
        return bool(
            int(full_parent_indices[current_idx].detach().cpu().item())
            == int(previous_best_idx)
        )

    def _eds_diversity_band_state(
        self,
        *,
        reference: Optional[float],
        current: float,
        cfg: _EDSConfig,
    ) -> str:
        if (
            reference is None
            or not math.isfinite(float(reference))
            or float(reference) < 0.0
            or not math.isfinite(float(current))
            or float(current) < 0.0
        ):
            raise ValueError(
                "EDS diversity reference/current must be finite and nonnegative"
            )
        low = max(
            0.0,
            float(cfg.rollout_diversity_target_ratio)
            * (1.0 - float(cfg.rollout_diversity_band_ratio))
            * float(reference),
        )
        high = (
            float(cfg.rollout_diversity_target_ratio)
            * (1.0 + float(cfg.rollout_diversity_band_ratio))
            * float(reference)
        )
        if not math.isfinite(low) or not math.isfinite(high) or high < low:
            raise ValueError("EDS diversity reference does not define a valid band")
        if float(current) < low:
            return "below_band"
        if float(current) <= high:
            return "in_band"
        return "above_band"

    def _eds_adaptive_rollout_diversity_decision(
        self,
        *,
        reference: float,
        current: float,
        rewards: Tensor,
        iter_idx: int,
        cfg: _EDSConfig,
    ) -> tuple[EDSRolloutDiversityDecision, dict]:
        eps = 1e-12
        try:
            if (
                isinstance(reference, bool)
                or not isinstance(reference, Real)
                or not math.isfinite(float(reference))
                or float(reference) <= eps
            ):
                raise ValueError(
                    "adaptive diversity reference must be finite and greater than eps"
                )
            if (
                isinstance(current, bool)
                or not isinstance(current, Real)
                or not math.isfinite(float(current))
                or float(current) < 0.0
            ):
                raise ValueError(
                    "adaptive diversity current value must be finite and nonnegative"
                )

            reference_value = float(reference)
            current_value = float(current)
            raw_low = (
                float(cfg.rollout_diversity_target_ratio)
                * (1.0 - float(cfg.rollout_diversity_band_ratio))
                * reference_value
            )
            high = (
                float(cfg.rollout_diversity_target_ratio)
                * (1.0 + float(cfg.rollout_diversity_band_ratio))
                * reference_value
            )
            if (
                not math.isfinite(raw_low)
                or not math.isfinite(high)
            ):
                raise ValueError(
                    "adaptive diversity reference does not define a valid finite band"
                )
            low = max(0.0, raw_low)
            if high < low:
                raise ValueError(
                    "adaptive diversity reference does not define an ordered band"
                )

            confidence = self._eds_rollout_reward_confidence(rewards)
            if current_value < low:
                deficit = min(max((low - current_value) / max(low, eps), 0.0), 1.0)
                iter_decay = max(
                    float(cfg.rollout_diversity_decay_floor),
                    1.0
                    - float(iter_idx)
                    / float(max(int(cfg.cem_iters) - 1, 1)),
                )
                raw_scale = (
                    float(cfg.rollout_diversity_scale_max)
                    * deficit
                    * iter_decay
                    * (1.0 - confidence)
                )
                requested_scale = min(
                    max(raw_scale, float(cfg.rollout_diversity_scale_min)),
                    float(cfg.rollout_diversity_scale_max),
                )
                if requested_scale > 0.0:
                    reason = "below_band"
                elif float(cfg.rollout_diversity_scale_max) <= 0.0:
                    reason = "below_band_disabled_by_scale_bounds"
                elif confidence >= 1.0:
                    reason = "below_band_high_confidence"
                else:
                    reason = "below_band_disabled_by_scale_bounds"
            elif current_value <= high:
                requested_scale = 0.0
                reason = "in_band"
            else:
                requested_scale = 0.0
                reason = "above_band"

            if not math.isfinite(requested_scale):
                raise ValueError("adaptive diversity requested scale must be finite")
            decision = EDSRolloutDiversityDecision(
                scale=float(requested_scale),
                enabled=bool(requested_scale > 0.0),
                reason=reason,
                reference=reference_value,
                low=float(low),
                high=float(high),
                current=current_value,
                reward_confidence=float(confidence),
            )
            info = {
                "diversity_reference": decision.reference,
                "diversity_band_low": decision.low,
                "diversity_band_high": decision.high,
                "diversity_current": decision.current,
                "adaptive_rbf_reward_confidence": decision.reward_confidence,
                "adaptive_rbf_scale_requested": decision.scale,
                "adaptive_rbf_scale_applied": decision.scale,
                "adaptive_rbf_active_particle_count": 0,
                "adaptive_rbf_band_hit": decision.reason == "in_band",
                "adaptive_rbf_fallback_used": False,
                "adaptive_rbf_fallback_reason": None,
                "adaptive_rbf_trigger_reason": decision.reason,
                "resolved_rollout_diversity_scale": decision.scale,
            }
            return decision, info
        except (ValueError, ArithmeticError) as exc:
            fallback_reason = f"{type(exc).__name__}: {exc}"
            log.warning(
                "EDS adaptive RBF controller fixed-scale fallback: "
                f"iter={int(iter_idx)} reason={fallback_reason}"
            )
            fallback_scale = float(cfg.rollout_diversity_scale)

            def finite_or_zero(value) -> float:
                try:
                    value_f = float(value)
                except (TypeError, ValueError, OverflowError):
                    return 0.0
                return value_f if math.isfinite(value_f) else 0.0

            decision = EDSRolloutDiversityDecision(
                scale=fallback_scale,
                enabled=bool(fallback_scale > 0.0),
                reason="controller_fallback",
                reference=finite_or_zero(reference),
                low=0.0,
                high=0.0,
                current=finite_or_zero(current),
                reward_confidence=0.0,
            )
            return decision, {
                "diversity_reference": (
                    finite_or_zero(reference)
                    if finite_or_zero(reference) > 0.0
                    else None
                ),
                "diversity_band_low": None,
                "diversity_band_high": None,
                "diversity_current": finite_or_zero(current),
                "adaptive_rbf_reward_confidence": 0.0,
                "adaptive_rbf_scale_requested": fallback_scale,
                "adaptive_rbf_scale_applied": fallback_scale,
                "adaptive_rbf_active_particle_count": 0,
                "adaptive_rbf_band_hit": False,
                "adaptive_rbf_fallback_used": True,
                "adaptive_rbf_fallback_reason": fallback_reason,
                "adaptive_rbf_trigger_reason": "controller_fallback",
                "resolved_rollout_diversity_scale": fallback_scale,
            }

    def _eds_selection_info_from_probabilities(
        self,
        probabilities: Tensor,
        *,
        selection_beta: float,
        degenerate_reward: bool,
    ) -> dict:
        if not torch.is_tensor(probabilities):
            raise ValueError("EDS selection probabilities must be a torch.Tensor")
        if probabilities.ndim != 1:
            raise ValueError(
                f"EDS selection probabilities must be 1-D, got shape {tuple(probabilities.shape)}"
            )
        if probabilities.numel() == 0:
            raise ValueError("EDS selection probabilities must be non-empty")
        if (
            isinstance(selection_beta, bool)
            or not isinstance(selection_beta, Real)
            or not math.isfinite(float(selection_beta))
        ):
            raise ValueError("EDS selection_beta must be a finite number")

        probabilities64 = probabilities.detach().to(dtype=torch.float64)
        if not torch.isfinite(probabilities64).all():
            raise ValueError("EDS selection probabilities must be finite")
        if bool((probabilities64 < 0.0).any().item()):
            raise ValueError("EDS selection probabilities must be non-negative")
        probability_mass = probabilities64.sum()
        if not torch.isfinite(probability_mass) or float(probability_mass.item()) <= 0.0:
            raise ValueError("EDS selection probabilities must be finite with positive mass")
        probabilities64 = probabilities64 / probability_mass
        population_size = probabilities64.numel()
        ess = 1.0 / probabilities64.square().sum()
        entropy = -(
            probabilities64 * torch.log(probabilities64.clamp_min(1e-300))
        ).sum()
        entropy_normalized = (
            entropy / math.log(population_size)
            if population_size > 1
            else torch.ones((), device=probabilities64.device, dtype=torch.float64)
        )
        info = {
            "selection_beta": float(selection_beta),
            "selection_ess": float(ess.item()),
            "selection_ess_ratio": float((ess / population_size).item()),
            "selection_entropy_normalized": float(entropy_normalized.item()),
            "selection_max_probability": float(probabilities64.max().item()),
            "selection_degenerate_reward": bool(degenerate_reward),
        }
        if not all(
            math.isfinite(value)
            for key, value in info.items()
            if key != "selection_degenerate_reward"
        ):
            raise ValueError("EDS selection telemetry must be finite")
        return info

    def _eds_adaptive_ess_probabilities(
        self,
        costs: Tensor,
        target_ratio: float,
        beta_max: float,
        bisection_steps: int,
    ) -> tuple[Tensor, dict]:
        if not torch.is_tensor(costs):
            raise ValueError("EDS sampling costs must be a torch.Tensor")
        if costs.ndim != 1:
            raise ValueError(f"EDS sampling costs must be 1-D, got shape {tuple(costs.shape)}")
        if costs.numel() == 0:
            raise ValueError("EDS sampling costs must be non-empty")
        if not torch.isfinite(costs).all():
            raise ValueError("EDS sampling costs must be finite")
        if isinstance(target_ratio, bool) or not isinstance(target_ratio, Real):
            raise ValueError("EDS target_ratio must be a real number in (0, 1]")
        target_ratio_value = float(target_ratio)
        if (
            not math.isfinite(target_ratio_value)
            or target_ratio_value <= 0.0
            or target_ratio_value > 1.0
        ):
            raise ValueError("EDS target_ratio must be finite and in (0, 1]")
        if isinstance(beta_max, bool) or not isinstance(beta_max, Real):
            raise ValueError("EDS beta_max must be a real number")
        beta_max_value = float(beta_max)
        if not math.isfinite(beta_max_value) or beta_max_value <= 0.0:
            raise ValueError("EDS beta_max must be finite and positive")
        if (
            isinstance(bisection_steps, bool)
            or not isinstance(bisection_steps, Integral)
            or int(bisection_steps) <= 0
        ):
            raise ValueError("EDS bisection_steps must be a positive integer")

        normalized_rewards, degenerate_reward = self._eds_robust_normalize_rewards(
            -costs.detach().to(dtype=torch.float64)
        )
        population_size = costs.numel()
        uniform = torch.full(
            (population_size,),
            1.0 / population_size,
            device=costs.device,
            dtype=torch.float32,
        )
        if degenerate_reward or target_ratio_value == 1.0:
            return uniform, self._eds_selection_info_from_probabilities(
                uniform,
                selection_beta=0.0,
                degenerate_reward=degenerate_reward,
            )

        def probabilities_at_beta(beta: float) -> Tensor:
            centered_rewards = normalized_rewards - normalized_rewards.max()
            logits = (centered_rewards * beta).clamp(
                min=torch.finfo(torch.float64).min,
                max=0.0,
            )
            return torch.softmax(logits, dim=0)

        def ess_ratio(probabilities: Tensor) -> float:
            ess = 1.0 / probabilities.square().sum()
            return float((ess / population_size).item())

        high_probabilities = probabilities_at_beta(beta_max_value)
        if ess_ratio(high_probabilities) > target_ratio_value:
            selected_beta = beta_max_value
            selected_probabilities64 = high_probabilities
        else:
            minimum_positive_beta = math.nextafter(0.0, 1.0)
            log_beta_low = math.log(minimum_positive_beta)
            log_beta_high = math.log(beta_max_value)
            for _ in range(int(bisection_steps)):
                log_beta_mid = log_beta_low + (log_beta_high - log_beta_low) * 0.5
                beta_mid = min(
                    beta_max_value,
                    max(minimum_positive_beta, math.exp(log_beta_mid)),
                )
                mid_probabilities = probabilities_at_beta(beta_mid)
                if ess_ratio(mid_probabilities) > target_ratio_value:
                    log_beta_low = log_beta_mid
                else:
                    log_beta_high = log_beta_mid
            selected_log_beta = log_beta_low + (
                log_beta_high - log_beta_low
            ) * 0.5
            selected_beta = min(
                beta_max_value,
                max(minimum_positive_beta, math.exp(selected_log_beta)),
            )
            selected_probabilities64 = probabilities_at_beta(selected_beta)

        probabilities = selected_probabilities64.to(
            device=costs.device,
            dtype=torch.float32,
        )
        probabilities = probabilities / probabilities.sum()
        return probabilities, self._eds_selection_info_from_probabilities(
            probabilities,
            selection_beta=selected_beta,
            degenerate_reward=False,
        )

    def _eds_compute_parent_weights(
        self,
        costs: Tensor,
        cfg: _EDSConfig,
    ) -> tuple[Tensor, dict]:
        if cfg.parent_weighting_mode == "legacy_temperature":
            probabilities = self._eds_sampling_probabilities_from_cost(
                costs,
                cfg.temperature,
            )
            _, degenerate_reward = self._eds_robust_normalize_rewards(
                -costs.detach().to(dtype=torch.float64)
            )
            return probabilities, self._eds_selection_info_from_probabilities(
                probabilities,
                selection_beta=cfg.temperature,
                degenerate_reward=degenerate_reward,
            )
        if cfg.parent_weighting_mode == "adaptive_ess":
            return self._eds_adaptive_ess_probabilities(
                costs,
                target_ratio=cfg.selection_ess_target_ratio,
                beta_max=cfg.selection_beta_max,
                bisection_steps=cfg.selection_bisection_steps,
            )
        raise ValueError(
            f"Unsupported EDS parent_weighting_mode: {cfg.parent_weighting_mode!r}"
        )

    def _eds_empty_initial_sampler_info(self, cfg: _EDSConfig) -> dict:
        return {
            "initial_sampling_mode": cfg.initial_sampling_mode,
            "initial_diversity_scale": float(cfg.initial_diversity_scale),
            "initial_diversity_start_ratio": cfg.initial_diversity_start_ratio,
            "initial_diversity_steps": 0,
            "initial_diversity_grad_norm_mean": None,
            "initial_diversity_grad_norm_max": None,
            "initial_diversity_grad_failure_count": 0,
            "initial_diversity_fallback_used": False,
            "initial_diversity_fallback_reason": None,
            "initial_sampler_latency_s": None,
        }

    def _eds_initial_cache_metadata(self, cfg: _EDSConfig, info: dict) -> dict:
        return {
            "initial_sampling_mode": cfg.initial_sampling_mode,
            "initial_diversity_scale": float(cfg.initial_diversity_scale),
            "initial_diversity_start_ratio": cfg.initial_diversity_start_ratio,
            "initial_diversity_fallback": cfg.initial_diversity_fallback,
            "initial_diversity_steps": int(info.get("initial_diversity_steps", 0)),
            "initial_diversity_grad_failure_count": int(
                info.get("initial_diversity_grad_failure_count", 0)
            ),
            "initial_diversity_grad_norm_mean": info.get(
                "initial_diversity_grad_norm_mean"
            ),
            "initial_diversity_grad_norm_max": info.get(
                "initial_diversity_grad_norm_max"
            ),
            "initial_diversity_fallback_used": bool(
                info.get("initial_diversity_fallback_used", False)
            ),
            "initial_diversity_fallback_reason": info.get(
                "initial_diversity_fallback_reason"
            ),
        }

    def _eds_validate_initial_cache_metadata(self, metadata: Mapping | None, cfg: _EDSConfig) -> None:
        if not cfg.initial_cache_metadata:
            log.warning(
                "EDS initial_population_cache metadata validation is disabled; "
                "initial sampler cache telemetry will use the current config "
                f"initial_sampling_mode={cfg.initial_sampling_mode}"
            )
            return
        if metadata is None:
            if cfg.initial_sampling_mode != "iid":
                raise ValueError(
                    "EDS initial_population_cache metadata is required for "
                    f"initial_sampling_mode={cfg.initial_sampling_mode}; "
                    "save_initial_cache cannot mint metadata for a legacy cache; "
                    "regenerate the cache with metadata or use a matching cache strategy."
                )
            log.warning(
                "EDS initial_population_cache has no metadata; assuming legacy cache "
                f"for initial_sampling_mode={cfg.initial_sampling_mode}"
            )
            return
        if not isinstance(metadata, Mapping):
            raise TypeError(
                "EDS initial_population_cache metadata must be a mapping, "
                f"got {type(metadata).__name__}"
            )

        expected = {
            "initial_sampling_mode": cfg.initial_sampling_mode,
            "initial_diversity_scale": float(cfg.initial_diversity_scale),
            "initial_diversity_start_ratio": cfg.initial_diversity_start_ratio,
            "initial_diversity_fallback": cfg.initial_diversity_fallback,
        }
        for field, expected_value in expected.items():
            if field not in metadata:
                continue
            cached_value = metadata.get(field)
            if cached_value != expected_value:
                raise ValueError(
                    f"EDS initial_population_cache {field} mismatch: "
                    f"cache={cached_value!r} config={expected_value!r}"
                )

        missing = [field for field in expected if field not in metadata]
        if missing:
            raise ValueError(
                "EDS initial_population_cache metadata missing required field: "
                f"{missing[0]}"
            )

    def _eds_initial_sampler_info_from_cache_metadata(
        self,
        cfg: _EDSConfig,
        metadata: Mapping | None,
        *,
        latency_s: float,
        trust_metadata: bool = True,
    ) -> dict:
        info = self._eds_empty_initial_sampler_info(cfg)
        if trust_metadata and isinstance(metadata, Mapping):
            for field in (
                "initial_sampling_mode",
                "initial_diversity_scale",
                "initial_diversity_start_ratio",
                "initial_diversity_steps",
                "initial_diversity_grad_failure_count",
                "initial_diversity_grad_norm_mean",
                "initial_diversity_grad_norm_max",
                "initial_diversity_fallback_used",
                "initial_diversity_fallback_reason",
            ):
                if field in metadata:
                    info[field] = metadata[field]
        info["initial_sampler_latency_s"] = float(latency_s)
        return info

    def _eds_initial_denoise_iid(
        self,
        *,
        x_t: Tensor,
        cond: dict,
        cfg: _EDSConfig,
    ) -> tuple[Tensor, dict]:
        del cfg
        population = x_t
        scheduler = self._noise_scheduler
        scheduler.set_timesteps(self._num_inference_steps)
        with torch.no_grad():
            for t in scheduler.timesteps:
                model_output = self._dit(population, t, cond)
                population = scheduler.step(
                    model_output,
                    t,
                    population,
                ).prev_sample.to(dtype=x_t.dtype)
        return population, {"initial_diversity_steps": 0}

    def _eds_initial_validate_population(
        self,
        population: Tensor,
        *,
        cond: dict,
        cfg: _EDSConfig,
        expected_shape: tuple[int, int, int],
    ) -> None:
        if not torch.is_tensor(population):
            raise TypeError("EDS initial population must be a torch.Tensor")
        expected = (
            int(cfg.population_size),
            int(expected_shape[1]),
            int(expected_shape[2]),
        )
        if tuple(population.shape) != expected:
            raise ValueError(
                f"EDS initial population shape {tuple(population.shape)} != {expected}"
            )
        if not torch.isfinite(population).all():
            raise ValueError("EDS initial population must be finite")
        mask_violation = self._eds_action_mask_violation(population, cond)
        if mask_violation > 1e-6:
            raise ValueError(
                "EDS initial population violates action mask: "
                f"max_violation={mask_violation:.6g}"
            )

    def _eds_initial_fallback_to_iid(
        self,
        *,
        x_t: Tensor,
        cond: dict,
        cfg: _EDSConfig,
        reason: str,
        grad_failure_count: int = 0,
        step_idx: Optional[int] = None,
        timestep: Optional[int] = None,
        partial_population: Optional[Tensor] = None,
    ) -> tuple[Tensor, dict]:
        details = []
        if step_idx is not None:
            details.append(f"step={int(step_idx)}")
        if timestep is not None:
            details.append(f"timestep={int(timestep)}")
        if partial_population is not None:
            details.append(f"partial_population_shape={tuple(partial_population.shape)}")
            details.append(
                "partial_population_finite="
                f"{bool(torch.isfinite(partial_population).all().item())}"
            )
        detail_text = " " + " ".join(details) if details else ""
        log.warning(
            "EDS initial sampler fallback to iid: "
            f"initial_sampling_mode={cfg.initial_sampling_mode} reason={reason} "
            f"population_shape={tuple(x_t.shape)}{detail_text}"
        )
        self._last_eds_initial_sampler_trace_stages = []
        population, info = self._eds_initial_denoise_iid(x_t=x_t, cond=cond, cfg=cfg)
        info = {**self._eds_empty_initial_sampler_info(cfg), **info}
        info["initial_diversity_fallback_used"] = True
        info["initial_diversity_fallback_reason"] = reason
        info["initial_diversity_grad_failure_count"] = int(grad_failure_count)
        return population, info

    def _eds_initial_denoise_rbf_diverse(
        self,
        *,
        x_t: Tensor,
        cond: dict,
        cfg: _EDSConfig,
    ) -> tuple[Tensor, dict]:
        if x_t.shape[0] <= 1:
            return self._eds_initial_fallback_to_iid(
                x_t=x_t,
                cond=cond,
                cfg=cfg,
                reason="population_size<=1",
            )

        population = x_t
        trace_stages: list[tuple[str, Tensor]] = [
            ("initial_before_diversity", population.detach())
        ]
        recorded_after_diversity = False
        scheduler = self._noise_scheduler
        scheduler.set_timesteps(self._num_inference_steps)
        start_step = self._resolve_start_step(
            scheduler.timesteps,
            cfg.initial_diversity_start_ratio,
        )
        grad_norms: list[float] = []
        grad_failures = 0
        diversity_steps = 0

        for i, t in enumerate(scheduler.timesteps):
            if int(t.item()) <= start_step and diversity_steps > 0 and not recorded_after_diversity:
                trace_stages.append(("initial_after_diversity_phase", population.detach()))
                recorded_after_diversity = True

            with torch.no_grad():
                model_output = self._dit(population, t, cond)

            if int(t.item()) > start_step:
                div_grad = self._compute_diversity_gradient(population)
                if div_grad is None:
                    grad_failures += 1
                    return self._eds_initial_fallback_to_iid(
                        x_t=x_t,
                        cond=cond,
                        cfg=cfg,
                        reason=f"diversity_gradient_none_at_step={i}_t={int(t.item())}",
                        grad_failure_count=grad_failures,
                        step_idx=i,
                        timestep=int(t.item()),
                        partial_population=population,
                    )
                if not torch.isfinite(div_grad).all():
                    grad_failures += 1
                    return self._eds_initial_fallback_to_iid(
                        x_t=x_t,
                        cond=cond,
                        cfg=cfg,
                        reason=f"non-finite_diversity_gradient_at_step={i}_t={int(t.item())}",
                        grad_failure_count=grad_failures,
                        step_idx=i,
                        timestep=int(t.item()),
                        partial_population=population,
                    )

                masked_div = self._mask_guidance_gradient(div_grad).to(
                    device=model_output.device,
                    dtype=model_output.dtype,
                )
                grad_norms.append(float(masked_div.detach().norm().cpu().item()))
                model_output[:, :, RDT_GUIDED_TRANSLATION_INDICES] += (
                    RDT_DIVERSITY_SIGN
                    * float(cfg.initial_diversity_scale)
                    * masked_div[:, :, RDT_GUIDED_TRANSLATION_INDICES]
                )
                diversity_steps += 1

            if not torch.isfinite(model_output).all():
                return self._eds_initial_fallback_to_iid(
                    x_t=x_t,
                    cond=cond,
                    cfg=cfg,
                    reason=f"non-finite_model_output_at_step={i}_t={int(t.item())}",
                    step_idx=i,
                    timestep=int(t.item()),
                    partial_population=population,
                )
            population = scheduler.step(model_output, t, population).prev_sample.to(
                dtype=x_t.dtype
            )
            if not torch.isfinite(population).all():
                return self._eds_initial_fallback_to_iid(
                    x_t=x_t,
                    cond=cond,
                    cfg=cfg,
                    reason=f"non-finite_population_at_step={i}_t={int(t.item())}",
                    step_idx=i,
                    timestep=int(t.item()),
                    partial_population=population,
                )

        info = self._eds_empty_initial_sampler_info(cfg)
        info["initial_diversity_steps"] = diversity_steps
        info["initial_diversity_grad_failure_count"] = grad_failures
        if grad_norms:
            info["initial_diversity_grad_norm_mean"] = float(sum(grad_norms) / len(grad_norms))
            info["initial_diversity_grad_norm_max"] = float(max(grad_norms))
        if diversity_steps > 0 and not recorded_after_diversity:
            trace_stages.append(("initial_after_diversity_phase", population.detach()))
        trace_stages.append(("initial_final", population.detach()))
        self._last_eds_initial_sampler_trace_stages = trace_stages
        return population, info

    def _eds_initial_population(self, *, x_t: Tensor, cond: dict, cfg: _EDSConfig) -> Tensor:
        start = time.perf_counter()
        self._last_eds_initial_sampler_info = self._eds_empty_initial_sampler_info(cfg)
        self._last_eds_initial_sampler_trace_stages = []
        if cfg.use_initial_cache:
            if cfg.initial_population_cache is None:
                raise ValueError("EDS use_initial_cache=true requires initial_population_cache")
            cache_path = Path(cfg.initial_population_cache)
            cached_payload = torch.load(cache_path, map_location=x_t.device)
            metadata = None
            cached = cached_payload
            if isinstance(cached_payload, dict) and "initial_population" in cached_payload:
                cached = cached_payload["initial_population"]
                metadata = cached_payload.get("metadata")
            self._eds_validate_initial_cache_metadata(metadata, cfg)
            if metadata is None and cfg.save_initial_cache:
                raise ValueError(
                    "EDS initial_population_cache metadata is required when "
                    "save_initial_cache=true; refusing to mint metadata for legacy cache"
                )
            if not torch.is_tensor(cached):
                raise TypeError("Cached EDS initial_population must be a torch.Tensor")
            expected = (cfg.population_size, x_t.shape[1], x_t.shape[2])
            if tuple(cached.shape) != expected:
                raise ValueError(
                    f"Cached EDS initial_population shape {tuple(cached.shape)} != {expected}"
                )
            population = self._apply_action_mask(cached.to(device=x_t.device, dtype=x_t.dtype), cond)
            self._eds_initial_validate_population(
                population,
                cond=cond,
                cfg=cfg,
                expected_shape=tuple(x_t.shape),
            )
            info = self._eds_initial_sampler_info_from_cache_metadata(
                cfg,
                metadata,
                latency_s=time.perf_counter() - start,
                trust_metadata=cfg.initial_cache_metadata,
            )
            self._last_eds_initial_sampler_info = info
            if cfg.save_initial_cache:
                self._save_eds_initial_population_cache(
                    population,
                    cfg,
                    info,
                )
            return population

        if cfg.initial_sampling_mode == "iid":
            population, info = self._eds_initial_denoise_iid(x_t=x_t, cond=cond, cfg=cfg)
        elif cfg.initial_sampling_mode == "rbf_diverse_denoise":
            population, info = self._eds_initial_denoise_rbf_diverse(
                x_t=x_t,
                cond=cond,
                cfg=cfg,
            )
        else:
            raise ValueError(f"Unsupported EDS initial_sampling_mode={cfg.initial_sampling_mode!r}")
        population = self._apply_action_mask(population, cond)
        try:
            self._eds_initial_validate_population(
                population,
                cond=cond,
                cfg=cfg,
                expected_shape=tuple(x_t.shape),
            )
        except (TypeError, ValueError) as exc:
            if cfg.initial_sampling_mode != "rbf_diverse_denoise":
                raise
            population, info = self._eds_initial_fallback_to_iid(
                x_t=x_t,
                cond=cond,
                cfg=cfg,
                reason=f"validation_failed: {exc}",
                partial_population=population,
            )
            population = self._apply_action_mask(population, cond)
            self._eds_initial_validate_population(
                population,
                cond=cond,
                cfg=cfg,
                expected_shape=tuple(x_t.shape),
            )
        info = {**self._eds_empty_initial_sampler_info(cfg), **info}
        info["initial_sampler_latency_s"] = float(time.perf_counter() - start)
        self._last_eds_initial_sampler_info = info
        if cfg.save_initial_cache:
            self._save_eds_initial_population_cache(
                population,
                cfg,
                info,
            )
        return population

    def _eds_renoise_reference(self, population_trajectories: Tensor, t: int) -> Tensor:
        scheduler = self._noise_scheduler
        if not hasattr(scheduler, "add_noise"):
            raise RuntimeError("EDS requires a scheduler with add_noise()")
        scheduler.set_timesteps(self._num_inference_steps)
        t = int(max(1, min(t, len(scheduler.timesteps))))
        noise = torch.randn_like(population_trajectories)
        selected_timestep = scheduler.timesteps[-t].to(device=population_trajectories.device)
        timesteps = selected_timestep.reshape(1).expand(population_trajectories.shape[0])
        return scheduler.add_noise(population_trajectories, noise, timesteps)

    def _eds_shift_memory_candidate(
        self,
        *,
        memory_candidate: Tensor,
        fresh_candidate: Tensor,
        executed_steps: int,
    ) -> Tensor:
        if (
            not torch.is_tensor(memory_candidate)
            or not torch.is_tensor(fresh_candidate)
            or memory_candidate.ndim != 2
            or tuple(memory_candidate.shape) != tuple(fresh_candidate.shape)
        ):
            raise ValueError(
                "EDS chunk memory and paired fresh candidate must have matching 2-D shapes"
            )
        if (
            isinstance(executed_steps, bool)
            or not isinstance(executed_steps, Integral)
            or int(executed_steps) <= 0
            or int(executed_steps) >= int(memory_candidate.shape[0])
        ):
            raise ValueError(
                "EDS chunk memory executed_steps must be in (0, action_horizon)"
            )
        executed_steps = int(executed_steps)
        return torch.cat(
            [memory_candidate[executed_steps:], fresh_candidate[-executed_steps:]],
            dim=0,
        )

    @staticmethod
    def _eds_resolve_chunk_memory_count(
        population_size: int,
        fraction: float,
    ) -> int:
        return max(
            0,
            min(int(population_size), int(round(int(population_size) * float(fraction)))),
        )

    def _eds_empty_chunk_memory_info(self, cfg: _EDSConfig) -> dict:
        return {
            "chunk_memory_available": False,
            "chunk_memory_used": False,
            "chunk_memory_candidate_count": 0,
            "chunk_memory_fraction_observed": 0.0,
            "chunk_memory_reset_reason": self._eds_chunk_memory_reset_reason,
            "chunk_memory_acceptance_ratio": None,
            "chunk_memory_source_counts": {
                "memory": 0,
                "fresh": int(cfg.population_size),
            },
            "chunk_memory_initial_best_reward": None,
            "chunk_fresh_initial_best_reward": None,
            "chunk_memory_initial_mean_reward": None,
            "chunk_fresh_initial_mean_reward": None,
            "chunk_memory_initial_diversity": None,
            "chunk_fresh_initial_diversity": None,
            "particle_sources": ("fresh",) * int(cfg.population_size),
            "previous_selected_population": None,
            "precomputed_score_call_count": 0,
        }

    @staticmethod
    def _eds_apply_chunk_memory_metrics(
        metrics: EDSChunkMetrics,
        telemetry: dict,
    ) -> None:
        for field_name in (
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
        ):
            if field_name in telemetry:
                setattr(metrics, field_name, telemetry[field_name])

    def _eds_chunk_selected_trajectory_distance(
        self,
        previous_selected: Optional[Tensor],
        current_selected: Tensor,
    ) -> Optional[float]:
        if previous_selected is None:
            return None
        previous_trajectory = self._eds_population_to_reward_trajectories(
            previous_selected
        )
        current_trajectory = self._eds_population_to_reward_trajectories(
            current_selected
        )
        if (
            previous_trajectory.shape[0] != 1
            or current_trajectory.shape[0] != 1
            or previous_trajectory.numel() != current_trajectory.numel()
            or not torch.isfinite(previous_trajectory).all()
            or not torch.isfinite(current_trajectory).all()
        ):
            return None
        distance = torch.linalg.norm(
            previous_trajectory.detach().reshape(-1).float()
            - current_trajectory.detach().reshape(-1).float()
        )
        if not torch.isfinite(distance):
            return None
        return float(distance.detach().cpu().item())

    def _eds_compose_initial_population_from_memory(
        self,
        *,
        fresh_population: Tensor,
        cond: dict,
        cfg: _EDSConfig,
        keypoints: Optional[Tensor],
        guidance_fns: Optional[List[Callable]],
        global_step: int,
        current_stage: int,
        trace_enabled: bool = False,
    ) -> tuple[Tensor, Optional[Tensor], Optional[dict], dict]:
        telemetry = self._eds_empty_chunk_memory_info(cfg)
        memory = self._eds_chunk_memory
        if memory is None:
            return fresh_population, None, None, telemetry
        telemetry["chunk_memory_available"] = True

        def fallback(reason: str):
            self.reset_eds_chunk_memory(reason, warn=True)
            telemetry["chunk_memory_reset_reason"] = reason
            return fresh_population, None, None, telemetry

        try:
            expected_shape = (int(cfg.population_size), 64, 128)
            if tuple(fresh_population.shape) != expected_shape:
                raise ValueError(
                    f"fresh_shape={tuple(fresh_population.shape)} expected={expected_shape}"
                )
            if not torch.isfinite(fresh_population).all():
                raise ValueError("fresh_population_nonfinite")
            if not torch.is_tensor(memory.population) or tuple(memory.population.shape) != expected_shape:
                memory_shape = (
                    tuple(memory.population.shape)
                    if torch.is_tensor(memory.population)
                    else type(memory.population).__name__
                )
                raise ValueError(f"memory_shape={memory_shape} expected={expected_shape}")
            if not torch.is_tensor(memory.costs) or tuple(memory.costs.shape) != (
                int(cfg.population_size),
            ):
                memory_cost_shape = (
                    tuple(memory.costs.shape)
                    if torch.is_tensor(memory.costs)
                    else type(memory.costs).__name__
                )
                raise ValueError(
                    f"memory_cost_shape={memory_cost_shape} expected={(int(cfg.population_size),)}"
                )
            if not torch.isfinite(memory.population).all() or not torch.isfinite(memory.costs).all():
                raise ValueError("memory_nonfinite")
            if (
                isinstance(memory.stage, bool)
                or not isinstance(memory.stage, Integral)
                or int(memory.stage) != int(current_stage)
            ):
                raise ValueError(
                    f"memory_stage={memory.stage} current_stage={current_stage}"
                )
            if isinstance(memory.global_step, bool) or not isinstance(memory.global_step, Integral):
                raise ValueError(f"memory_global_step={memory.global_step!r}")
            executed_steps = int(global_step) - int(memory.global_step)
            if executed_steps <= 0 or executed_steps >= 64:
                raise ValueError(f"executed_steps={executed_steps} outside (0, 64)")

            memory_population = memory.population.to(
                device=fresh_population.device,
                dtype=fresh_population.dtype,
            )
            memory_costs = memory.costs.to(
                device=fresh_population.device,
                dtype=fresh_population.dtype,
            )
            if self._eds_action_mask_violation(memory_population, cond) > 0.0:
                raise ValueError("memory_action_mask_violation")
            candidate_count = self._eds_resolve_chunk_memory_count(
                int(cfg.population_size),
                float(cfg.chunk_memory_fraction),
            )
            telemetry["chunk_memory_candidate_count"] = candidate_count
            if candidate_count == 0:
                return fresh_population, None, None, telemetry

            selected_indices, _ = self._eds_select_eef_kcenter(
                memory_population,
                -memory_costs,
                count=candidate_count,
                reward_quantile=0.0,
            )
            if int(selected_indices.numel()) != candidate_count:
                raise ValueError(
                    "memory_candidate_selection_shortfall="
                    f"{int(selected_indices.numel())}/{candidate_count}"
                )
            selected_memory = memory_population.index_select(0, selected_indices)
            shifted_memory = torch.stack(
                [
                    self._eds_shift_memory_candidate(
                        memory_candidate=selected_memory[idx],
                        fresh_candidate=fresh_population[idx],
                        executed_steps=executed_steps,
                    )
                    for idx in range(candidate_count)
                ],
                dim=0,
            )
            shifted_memory = self._apply_action_mask(shifted_memory, cond)
            adapted_memory = self._eds_renoise_reference(
                shifted_memory,
                int(cfg.chunk_memory_renoise_steps),
            )
            adapted_memory = self._eds_denoise_noisy_population(
                cond=cond,
                action_mask=cond["action_mask"],
                noisy_action=adapted_memory,
                n_trunc_steps=int(cfg.chunk_memory_renoise_steps),
            )
            adapted_memory = self._apply_action_mask(adapted_memory, cond)
            if tuple(adapted_memory.shape) != (candidate_count, 64, 128):
                raise ValueError(
                    f"adapted_memory_shape={tuple(adapted_memory.shape)} "
                    f"expected={(candidate_count, 64, 128)}"
                )
            if not torch.isfinite(adapted_memory).all():
                raise ValueError("adapted_memory_nonfinite")

            fresh_costs, fresh_info = self._eds_score_population_as_cost(
                fresh_population,
                keypoints=keypoints,
                guidance_fns=guidance_fns,
                reward_mode=cfg.reward_mode,
                shuffle_seed=cfg.shuffle_seed,
            )
            fresh_costs = self._eds_validate_population_scores(
                fresh_costs,
                int(cfg.population_size),
            )
            memory_candidate_costs, memory_info = self._eds_score_population_as_cost(
                adapted_memory,
                keypoints=keypoints,
                guidance_fns=guidance_fns,
                reward_mode=cfg.reward_mode,
                shuffle_seed=cfg.shuffle_seed,
            )
            memory_candidate_costs = self._eds_validate_population_scores(
                memory_candidate_costs,
                candidate_count,
            )
            fresh_rewards = self._eds_rewards_from_info(fresh_costs, fresh_info)
            memory_rewards = self._eds_rewards_from_info(
                memory_candidate_costs,
                memory_info,
            )
            reward_threshold = torch.quantile(
                fresh_rewards.float(),
                float(cfg.chunk_memory_reward_guard_quantile),
            ).to(device=memory_rewards.device, dtype=memory_rewards.dtype)
            accepted_mask = memory_rewards >= reward_threshold
            accepted_positions = torch.nonzero(
                accepted_mask,
                as_tuple=False,
            ).reshape(-1)

            population = fresh_population.clone()
            population_costs = fresh_costs.clone()
            population_rewards = fresh_rewards.clone()
            particle_sources = ["fresh"] * int(cfg.population_size)
            if accepted_positions.numel() > 0:
                population.index_copy_(
                    0,
                    accepted_positions.to(device=population.device),
                    adapted_memory.index_select(0, accepted_positions),
                )
                population_costs.index_copy_(
                    0,
                    accepted_positions.to(device=population_costs.device),
                    memory_candidate_costs.index_select(0, accepted_positions),
                )
                population_rewards.index_copy_(
                    0,
                    accepted_positions.to(device=population_rewards.device),
                    memory_rewards.index_select(0, accepted_positions),
                )
                for position in accepted_positions.detach().cpu().tolist():
                    particle_sources[int(position)] = "memory"
            population = self._apply_action_mask(population, cond)
            accepted_count = int(accepted_positions.numel())
            previous_best_idx = int(torch.argmin(memory_costs).item())
            telemetry.update(
                {
                    "chunk_memory_used": accepted_count > 0,
                    "chunk_memory_fraction_observed": float(
                        accepted_count / int(cfg.population_size)
                    ),
                    "chunk_memory_acceptance_ratio": float(
                        accepted_count / candidate_count
                    ),
                    "chunk_memory_source_counts": {
                        "memory": accepted_count,
                        "fresh": int(cfg.population_size) - accepted_count,
                    },
                    "chunk_memory_initial_best_reward": float(
                        memory_rewards.max().detach().cpu().item()
                    ),
                    "chunk_fresh_initial_best_reward": float(
                        fresh_rewards.max().detach().cpu().item()
                    ),
                    "chunk_memory_initial_mean_reward": float(
                        memory_rewards.mean().detach().cpu().item()
                    ),
                    "chunk_fresh_initial_mean_reward": float(
                        fresh_rewards.mean().detach().cpu().item()
                    ),
                    "chunk_memory_initial_diversity": self._eds_eef_trajectory_diversity(
                        adapted_memory
                    ),
                    "chunk_fresh_initial_diversity": self._eds_eef_trajectory_diversity(
                        fresh_population
                    ),
                    "particle_sources": tuple(particle_sources),
                    "previous_selected_population": memory_population[
                        previous_best_idx : previous_best_idx + 1
                    ].detach(),
                    "precomputed_score_call_count": 2,
                }
            )
            if trace_enabled:
                telemetry.update(
                    {
                        "_trace_fresh_population": fresh_population.detach().cpu().clone(),
                        "_trace_fresh_costs": fresh_costs.detach().cpu().clone(),
                        "_trace_fresh_rewards": fresh_rewards.detach().cpu().clone(),
                        "_trace_adapted_memory": adapted_memory.detach().cpu().clone(),
                        "_trace_adapted_memory_costs": memory_candidate_costs.detach().cpu().clone(),
                        "_trace_adapted_memory_rewards": memory_rewards.detach().cpu().clone(),
                        "_trace_composed_population": population.detach().cpu().clone(),
                        "_trace_composed_costs": population_costs.detach().cpu().clone(),
                        "_trace_composed_rewards": population_rewards.detach().cpu().clone(),
                        "_trace_accepted_positions": [
                            int(position)
                            for position in accepted_positions.detach().cpu().tolist()
                        ],
                    }
                )
            return (
                population,
                population_costs,
                {"rewards": population_rewards},
                telemetry,
            )
        except (TypeError, ValueError, ArithmeticError) as exc:
            return fallback(f"invalid_memory: {exc}")

    def _eds_rollout_reference(
        self,
        *,
        cond: dict,
        action_mask: Tensor,
        noisy_action: Tensor,
        keypoints: Optional[Tensor],
        guidance_fns: Optional[List[Callable]],
        n_trunc_steps: int,
        reward_mode: str = "normal",
        shuffle_seed: int = 0,
        cfg: Optional[_EDSConfig] = None,
        iter_idx: int = 0,
        diversity_scale_override: float | None = None,
    ) -> tuple[Tensor, Tensor, dict]:
        if (
            cfg is not None
            and cfg.rollout_diversity_control_mode == "adaptive_band"
            and diversity_scale_override is not None
            and (
                isinstance(diversity_scale_override, bool)
                or not isinstance(diversity_scale_override, Real)
                or not math.isfinite(float(diversity_scale_override))
                or float(diversity_scale_override) < 0.0
            )
        ):
            raise ValueError(
                "EDS adaptive rollout diversity scale override must be finite and nonnegative"
            )
        if cfg is not None and self._eds_should_apply_rollout_diversity(cfg, iter_idx):
            return self._eds_rollout_rbf_diverse_reference(
                cond=cond,
                action_mask=action_mask,
                noisy_action=noisy_action,
                keypoints=keypoints,
                guidance_fns=guidance_fns,
                n_trunc_steps=n_trunc_steps,
                reward_mode=reward_mode,
                shuffle_seed=shuffle_seed,
                cfg=cfg,
                iter_idx=iter_idx,
                diversity_scale_override=diversity_scale_override,
            )
        return self._eds_rollout_baseline_reference(
            cond=cond,
            action_mask=action_mask,
            noisy_action=noisy_action,
            keypoints=keypoints,
            guidance_fns=guidance_fns,
            n_trunc_steps=n_trunc_steps,
            reward_mode=reward_mode,
            shuffle_seed=shuffle_seed,
            cfg=cfg,
        )

    def _eds_rollout_baseline_reference(
        self,
        *,
        cond: dict,
        action_mask: Tensor,
        noisy_action: Tensor,
        keypoints: Optional[Tensor],
        guidance_fns: Optional[List[Callable]],
        n_trunc_steps: int,
        reward_mode: str = "normal",
        shuffle_seed: int = 0,
        cfg: Optional[_EDSConfig] = None,
    ) -> tuple[Tensor, Tensor, dict]:
        x_t = self._eds_denoise_noisy_population(
            cond=cond,
            action_mask=action_mask,
            noisy_action=noisy_action,
            n_trunc_steps=n_trunc_steps,
        )
        costs, info = self._eds_score_population_as_cost(
            x_t,
            keypoints=keypoints,
            guidance_fns=guidance_fns,
            reward_mode=reward_mode,
            shuffle_seed=shuffle_seed,
        )
        info = {**self._eds_empty_rollout_diversity_info(cfg), **info}
        return x_t, costs, info

    def _eds_denoise_noisy_population(
        self,
        *,
        cond: dict,
        action_mask: Tensor,
        noisy_action: Tensor,
        n_trunc_steps: int,
    ) -> Tensor:
        scheduler = self._noise_scheduler
        scheduler.set_timesteps(self._num_inference_steps)
        n_trunc_steps = int(max(1, min(n_trunc_steps, len(scheduler.timesteps))))
        x_t = noisy_action
        mask = self._expand_action_mask_for_population(action_mask, x_t)

        with torch.no_grad():
            for t in scheduler.timesteps[-n_trunc_steps:]:
                model_output = self._dit(x_t, t, cond)
                x_t = scheduler.step(model_output, t, x_t).prev_sample.to(dtype=noisy_action.dtype)

        x_t = x_t * mask
        return x_t

    def _eds_should_apply_rollout_diversity(self, cfg: _EDSConfig, iter_idx: int) -> bool:
        if cfg.truncated_rollout_mode != "rbf_diverse":
            return False
        iters = cfg.rollout_diversity_iters
        if iters == "all":
            return True
        try:
            return int(iter_idx) < int(iters)
        except (TypeError, ValueError, OverflowError):
            return False

    def _eds_rollout_diversity_step_mask(
        self,
        cfg: _EDSConfig,
        rollout_timesteps: Tensor,
        local_step: int,
    ) -> bool:
        if rollout_timesteps.numel() == 0:
            return False
        step_count = int(math.ceil(float(rollout_timesteps.numel()) * float(cfg.rollout_diversity_start_ratio)))
        step_count = max(0, min(int(rollout_timesteps.numel()), step_count))
        if local_step >= step_count:
            return False
        skip_final = int(max(0, cfg.rollout_diversity_skip_final_steps))
        if skip_final > 0 and local_step >= int(rollout_timesteps.numel()) - skip_final:
            return False
        return True

    def _eds_empty_rollout_diversity_info(self, cfg: Optional[_EDSConfig]) -> dict:
        mode = cfg.truncated_rollout_mode if cfg is not None else "baseline"
        scale = cfg.rollout_diversity_scale if cfg is not None else None
        start_ratio = cfg.rollout_diversity_start_ratio if cfg is not None else None
        return {
            "rollout_diversity_enabled": False,
            "rollout_diversity_mode": mode,
            "rollout_diversity_scale": scale,
            "rollout_diversity_start_ratio": start_ratio,
            "rollout_diversity_iters_applied": 0,
            "rollout_diversity_steps_applied": 0,
            "rollout_diversity_grad_norms": [],
            "rollout_diversity_grad_norm_mean": None,
            "rollout_diversity_grad_norm_max": None,
            "rollout_diversity_fallback_used": False,
            "rollout_diversity_fallback_reason": None,
            "eef_diversity_before_rollout": None,
            "eef_diversity_after_rollout_rbf_phase": None,
            "eef_diversity_after_rollout_final": None,
            "eef_diversity_rollout_retention_ratio": None,
            "endpoint_spread_before_rollout": None,
            "endpoint_spread_after_rollout_rbf_phase": None,
            "endpoint_spread_after_rollout_final": None,
            "rollout_diversity_trace_stages": [],
        }

    def _eds_rollout_fallback_to_baseline(
        self,
        *,
        reason: str,
        iter_idx: int,
        step_idx: Optional[int],
        timestep: Optional[int],
        cfg: _EDSConfig,
        cond: dict,
        action_mask: Tensor,
        noisy_action: Tensor,
        keypoints: Optional[Tensor],
        guidance_fns: Optional[List[Callable]],
        n_trunc_steps: int,
        reward_mode: str,
        shuffle_seed: int,
        attempted_diversity_scale: float | None = None,
    ) -> tuple[Tensor, Tensor, dict]:
        detail = []
        if step_idx is not None:
            detail.append(f"step={int(step_idx)}")
        if timestep is not None:
            detail.append(f"timestep={int(timestep)}")
        detail_text = " " + " ".join(detail) if detail else ""
        log.warning(
            "EDS rollout diversity fallback to baseline: "
            f"reason={reason} iter={int(iter_idx)} n_trunc_steps={int(n_trunc_steps)} "
            f"population_shape={tuple(noisy_action.shape)}{detail_text}"
        )
        population, costs, info = self._eds_rollout_baseline_reference(
            cond=cond,
            action_mask=action_mask,
            noisy_action=noisy_action,
            keypoints=keypoints,
            guidance_fns=guidance_fns,
            n_trunc_steps=n_trunc_steps,
            reward_mode=reward_mode,
            shuffle_seed=shuffle_seed,
            cfg=cfg,
        )
        info["rollout_diversity_mode"] = cfg.truncated_rollout_mode
        if attempted_diversity_scale is not None:
            info["rollout_diversity_scale"] = float(attempted_diversity_scale)
        info["rollout_diversity_fallback_used"] = True
        info["rollout_diversity_fallback_reason"] = reason
        return population, costs, info

    def _eds_rollout_rbf_diverse_reference(
        self,
        *,
        cond: dict,
        action_mask: Tensor,
        noisy_action: Tensor,
        keypoints: Optional[Tensor],
        guidance_fns: Optional[List[Callable]],
        n_trunc_steps: int,
        reward_mode: str,
        shuffle_seed: int,
        cfg: _EDSConfig,
        iter_idx: int,
        diversity_scale_override: float | None = None,
    ) -> tuple[Tensor, Tensor, dict]:
        scheduler = self._noise_scheduler
        scheduler.set_timesteps(self._num_inference_steps)
        n_trunc_steps = int(max(1, min(n_trunc_steps, len(scheduler.timesteps))))
        rollout_timesteps = scheduler.timesteps[-n_trunc_steps:]
        x_t = noisy_action
        mask = self._expand_action_mask_for_population(action_mask, x_t)
        info = self._eds_empty_rollout_diversity_info(cfg)
        info["rollout_diversity_mode"] = cfg.truncated_rollout_mode
        actual_scale = float(cfg.rollout_diversity_scale)
        if (
            cfg.rollout_diversity_control_mode == "adaptive_band"
            and diversity_scale_override is not None
        ):
            if (
                isinstance(diversity_scale_override, bool)
                or not isinstance(diversity_scale_override, Real)
                or not math.isfinite(float(diversity_scale_override))
                or float(diversity_scale_override) < 0.0
            ):
                raise ValueError(
                    "EDS adaptive rollout diversity scale override must be finite and nonnegative"
                )
            actual_scale = float(diversity_scale_override)
        info["rollout_diversity_scale"] = actual_scale
        before_population = x_t.detach()
        after_rbf_population: Optional[Tensor] = None
        grad_norms: list[float] = []
        steps_applied = 0

        if actual_scale > 0.0 and x_t.shape[0] <= 1:
            return self._eds_rollout_fallback_to_baseline(
                reason="population_size<=1",
                iter_idx=iter_idx,
                step_idx=None,
                timestep=None,
                cfg=cfg,
                cond=cond,
                action_mask=action_mask,
                noisy_action=noisy_action,
                keypoints=keypoints,
                guidance_fns=guidance_fns,
                n_trunc_steps=n_trunc_steps,
                reward_mode=reward_mode,
                shuffle_seed=shuffle_seed,
                attempted_diversity_scale=actual_scale,
            )

        for local_step, t in enumerate(rollout_timesteps):
            with torch.no_grad():
                model_output = self._dit(x_t, t, cond)

            applied_this_step = False
            if actual_scale > 0.0 and self._eds_rollout_diversity_step_mask(
                cfg,
                rollout_timesteps,
                local_step,
            ):
                div_grad = self._compute_diversity_gradient(x_t)
                if div_grad is None:
                    return self._eds_rollout_fallback_to_baseline(
                        reason=f"diversity_gradient_none_at_step={local_step}_t={int(t.item())}",
                        iter_idx=iter_idx,
                        step_idx=local_step,
                        timestep=int(t.item()),
                        cfg=cfg,
                        cond=cond,
                        action_mask=action_mask,
                        noisy_action=noisy_action,
                        keypoints=keypoints,
                        guidance_fns=guidance_fns,
                        n_trunc_steps=n_trunc_steps,
                        reward_mode=reward_mode,
                        shuffle_seed=shuffle_seed,
                        attempted_diversity_scale=actual_scale,
                    )
                if not torch.isfinite(div_grad).all():
                    return self._eds_rollout_fallback_to_baseline(
                        reason=f"non-finite_diversity_gradient_at_step={local_step}_t={int(t.item())}",
                        iter_idx=iter_idx,
                        step_idx=local_step,
                        timestep=int(t.item()),
                        cfg=cfg,
                        cond=cond,
                        action_mask=action_mask,
                        noisy_action=noisy_action,
                        keypoints=keypoints,
                        guidance_fns=guidance_fns,
                        n_trunc_steps=n_trunc_steps,
                        reward_mode=reward_mode,
                        shuffle_seed=shuffle_seed,
                        attempted_diversity_scale=actual_scale,
                    )
                masked_div = self._mask_guidance_gradient(div_grad).to(
                    device=model_output.device,
                    dtype=model_output.dtype,
                )
                grad_norms.append(float(masked_div.detach().norm().cpu().item()))
                model_output[:, :, RDT_GUIDED_TRANSLATION_INDICES] += (
                    RDT_DIVERSITY_SIGN
                    * actual_scale
                    * masked_div[:, :, RDT_GUIDED_TRANSLATION_INDICES]
                )
                steps_applied += 1
                applied_this_step = True

            if not torch.isfinite(model_output).all():
                return self._eds_rollout_fallback_to_baseline(
                    reason=f"non-finite_model_output_at_step={local_step}_t={int(t.item())}",
                    iter_idx=iter_idx,
                    step_idx=local_step,
                    timestep=int(t.item()),
                    cfg=cfg,
                    cond=cond,
                    action_mask=action_mask,
                    noisy_action=noisy_action,
                    keypoints=keypoints,
                    guidance_fns=guidance_fns,
                    n_trunc_steps=n_trunc_steps,
                    reward_mode=reward_mode,
                    shuffle_seed=shuffle_seed,
                    attempted_diversity_scale=actual_scale,
                )
            x_t = scheduler.step(model_output, t, x_t).prev_sample.to(dtype=noisy_action.dtype)
            if applied_this_step:
                after_rbf_population = x_t.detach()
            if not torch.isfinite(x_t).all():
                return self._eds_rollout_fallback_to_baseline(
                    reason=f"non-finite_population_at_step={local_step}_t={int(t.item())}",
                    iter_idx=iter_idx,
                    step_idx=local_step,
                    timestep=int(t.item()),
                    cfg=cfg,
                    cond=cond,
                    action_mask=action_mask,
                    noisy_action=noisy_action,
                    keypoints=keypoints,
                    guidance_fns=guidance_fns,
                    n_trunc_steps=n_trunc_steps,
                    reward_mode=reward_mode,
                    shuffle_seed=shuffle_seed,
                    attempted_diversity_scale=actual_scale,
                )

        x_t = x_t * mask
        if after_rbf_population is not None:
            after_rbf_population = after_rbf_population * mask
        final_population = x_t.detach()
        costs, score_info = self._eds_score_population_as_cost(
            x_t,
            keypoints=keypoints,
            guidance_fns=guidance_fns,
            reward_mode=reward_mode,
            shuffle_seed=shuffle_seed,
        )
        info.update(score_info)
        info["rollout_diversity_enabled"] = steps_applied > 0
        info["rollout_diversity_iters_applied"] = 1 if steps_applied > 0 else 0
        info["rollout_diversity_steps_applied"] = int(steps_applied)
        info["rollout_diversity_grad_norms"] = grad_norms
        if grad_norms:
            info["rollout_diversity_grad_norm_mean"] = float(sum(grad_norms) / len(grad_norms))
            info["rollout_diversity_grad_norm_max"] = float(max(grad_norms))
        info["eef_diversity_before_rollout"] = self._eds_eef_trajectory_diversity(
            before_population * mask
        )
        info["endpoint_spread_before_rollout"] = self._eds_endpoint_spread(
            before_population * mask
        )
        if after_rbf_population is not None:
            info["eef_diversity_after_rollout_rbf_phase"] = (
                self._eds_eef_trajectory_diversity(after_rbf_population)
            )
            info["endpoint_spread_after_rollout_rbf_phase"] = self._eds_endpoint_spread(
                after_rbf_population
            )
        info["eef_diversity_after_rollout_final"] = self._eds_eef_trajectory_diversity(
            final_population
        )
        info["endpoint_spread_after_rollout_final"] = self._eds_endpoint_spread(
            final_population
        )
        after_diversity = info["eef_diversity_after_rollout_rbf_phase"]
        if after_diversity is not None and after_diversity > 1e-12:
            info["eef_diversity_rollout_retention_ratio"] = (
                info["eef_diversity_after_rollout_final"] / after_diversity
            )
        trace_stages: list[tuple[str, Tensor]] = [
            ("rollout_before_diversity", before_population * mask),
        ]
        if after_rbf_population is not None:
            trace_stages.append(("rollout_after_diversity_phase", after_rbf_population))
        trace_stages.append(("rollout_final", final_population))
        info["rollout_diversity_trace_stages"] = trace_stages
        return x_t, costs, info

    def _eds_order_candidates_by_cost(self, samples: Tensor, costs: Tensor) -> Tensor:
        if samples.shape[0] <= 1:
            return samples.detach()
        order = torch.argsort(costs.detach())
        return samples.index_select(0, order.to(device=samples.device)).detach()

    def _eds_update_guidance_metadata_from_cost(self, best_cost: Tensor | float, costs: Tensor) -> None:
        if torch.is_tensor(best_cost):
            best_cost_value = float(best_cost.detach().cpu().item())
        else:
            best_cost_value = float(best_cost)
        best_reward = -best_cost_value
        self._last_raw_reward = best_reward
        if self._stage_init_reward is None:
            self._stage_init_reward = best_reward
        self._normalized_reward_from_value(best_reward)
        if torch.is_tensor(costs) and costs.numel() > 0:
            rewards = -costs.detach()
            spread = rewards.max() - rewards.mean()
            self._last_scale = float(torch.clamp(spread, min=0.0).cpu().item())
        else:
            self._last_scale = 0.0

    def _eds_population_diversity(self, population: Tensor) -> float:
        if population.shape[0] <= 1:
            return 0.0
        flat = population.detach().reshape(population.shape[0], -1).float()
        distances = torch.pdist(flat, p=2)
        if distances.numel() == 0:
            return 0.0
        return float(distances.mean().detach().cpu().item())

    def _eds_eef_trajectory_diversity(self, population: Tensor) -> float:
        if population.shape[0] <= 1:
            return 0.0
        trajs = self._rdt_sample_to_trajectory_3d(population)
        if trajs.ndim < 3 or trajs.shape[1] <= 1:
            return 0.0
        flat = trajs[:, 1:, :3].detach().reshape(trajs.shape[0], -1).float()
        distances = torch.pdist(flat, p=2)
        if distances.numel() == 0:
            return 0.0
        mean_distance = distances.mean()
        if not torch.isfinite(mean_distance):
            return 0.0
        return float(mean_distance.detach().cpu().item())

    def _eds_endpoint_spread(self, population: Tensor) -> float:
        if population.shape[0] <= 1:
            return 0.0
        trajs = self._rdt_sample_to_trajectory_3d(population)
        if trajs.ndim < 3 or trajs.shape[1] == 0:
            return 0.0
        endpoints = trajs[:, -1, :3].detach().float()
        distances = torch.pdist(endpoints, p=2)
        if distances.numel() == 0:
            return 0.0
        mean_distance = distances.mean()
        if not torch.isfinite(mean_distance):
            return 0.0
        return float(mean_distance.detach().cpu().item())

    def _eds_record_initial_eef_diversity_metrics(
        self,
        metrics: EDSChunkMetrics,
        *,
        population: Tensor,
        cond: dict,
    ) -> None:
        initial_stage_populations: dict[str, Tensor] = {}
        for stage_name, stage_population in getattr(
            self,
            "_last_eds_initial_sampler_trace_stages",
            [],
        ):
            if stage_name not in {
                "initial_before_diversity",
                "initial_after_diversity_phase",
            }:
                continue
            initial_stage_populations[stage_name] = self._apply_action_mask(
                stage_population.to(device=population.device, dtype=population.dtype),
                cond,
            )

        before_population = initial_stage_populations.get("initial_before_diversity")
        after_population = initial_stage_populations.get("initial_after_diversity_phase")
        if before_population is not None:
            metrics.initial_eef_diversity_before_rbf = self._eds_eef_trajectory_diversity(
                before_population
            )
            metrics.endpoint_spread_before_rbf = self._eds_endpoint_spread(
                before_population
            )
        if after_population is not None:
            metrics.initial_eef_diversity_after_rbf_phase = (
                self._eds_eef_trajectory_diversity(after_population)
            )
            metrics.endpoint_spread_after_rbf_phase = self._eds_endpoint_spread(
                after_population
            )

        metrics.initial_eef_diversity_final = self._eds_eef_trajectory_diversity(
            population
        )
        metrics.endpoint_spread_final = self._eds_endpoint_spread(population)
        after_diversity = metrics.initial_eef_diversity_after_rbf_phase
        if after_diversity is not None and after_diversity > 1e-12:
            metrics.initial_eef_diversity_retention_ratio = (
                metrics.initial_eef_diversity_final / after_diversity
            )

    def _eds_rollout_info_with_full_population_diversity(
        self,
        info: Mapping,
        *,
        elite_population: Tensor,
        offspring_before_rollout: Tensor,
        offspring_after_rollout: Tensor,
        cond: dict,
    ) -> dict:
        if elite_population.shape[0] == 0:
            return dict(info)

        full_info = dict(info)
        trace_stages = {
            str(stage_name): stage_population
            for stage_name, stage_population in info.get(
                "rollout_diversity_trace_stages",
                [],
            )
            if torch.is_tensor(stage_population)
        }

        def full_population(offspring_population: Tensor) -> Tensor:
            offspring_population = offspring_population.to(
                device=elite_population.device,
                dtype=elite_population.dtype,
            )
            combined = torch.cat(
                [elite_population, offspring_population],
                dim=0,
            )
            return self._apply_action_mask(combined, cond)

        before_population = None
        if (
            info.get("eef_diversity_before_rollout") is not None
            or info.get("endpoint_spread_before_rollout") is not None
        ):
            before_population = full_population(
                trace_stages.get(
                    "rollout_before_diversity",
                    offspring_before_rollout,
                )
            )
        after_population = None
        if (
            info.get("eef_diversity_after_rollout_rbf_phase") is not None
            or info.get("endpoint_spread_after_rollout_rbf_phase") is not None
        ):
            after_stage = trace_stages.get("rollout_after_diversity_phase")
            if after_stage is not None:
                after_population = full_population(after_stage)
        final_population = None
        if (
            info.get("eef_diversity_after_rollout_final") is not None
            or info.get("endpoint_spread_after_rollout_final") is not None
        ):
            final_population = full_population(
                trace_stages.get("rollout_final", offspring_after_rollout)
            )

        if info.get("eef_diversity_before_rollout") is not None:
            full_info["eef_diversity_before_rollout"] = (
                self._eds_eef_trajectory_diversity(before_population)
                if before_population is not None
                else None
            )
        if info.get("endpoint_spread_before_rollout") is not None:
            full_info["endpoint_spread_before_rollout"] = (
                self._eds_endpoint_spread(before_population)
                if before_population is not None
                else None
            )
        if info.get("eef_diversity_after_rollout_rbf_phase") is not None:
            full_info["eef_diversity_after_rollout_rbf_phase"] = (
                self._eds_eef_trajectory_diversity(after_population)
                if after_population is not None
                else None
            )
        if info.get("endpoint_spread_after_rollout_rbf_phase") is not None:
            full_info["endpoint_spread_after_rollout_rbf_phase"] = (
                self._eds_endpoint_spread(after_population)
                if after_population is not None
                else None
            )
        if info.get("eef_diversity_after_rollout_final") is not None:
            full_info["eef_diversity_after_rollout_final"] = (
                self._eds_eef_trajectory_diversity(final_population)
                if final_population is not None
                else None
            )
        if info.get("endpoint_spread_after_rollout_final") is not None:
            full_info["endpoint_spread_after_rollout_final"] = (
                self._eds_endpoint_spread(final_population)
                if final_population is not None
                else None
            )

        if info.get("eef_diversity_rollout_retention_ratio") is not None:
            after_diversity = full_info.get(
                "eef_diversity_after_rollout_rbf_phase"
            )
            final_diversity = full_info.get("eef_diversity_after_rollout_final")
            full_info["eef_diversity_rollout_retention_ratio"] = (
                float(final_diversity) / float(after_diversity)
                if after_diversity is not None
                and final_diversity is not None
                and float(after_diversity) > 1e-12
                else None
            )
        return full_info

    def _eds_update_rollout_diversity_metrics(
        self,
        metrics: EDSChunkMetrics,
        info: Mapping,
        cfg: _EDSConfig,
        grad_norms: list[float],
    ) -> None:
        metrics.rollout_diversity_mode = str(
            info.get("rollout_diversity_mode", cfg.truncated_rollout_mode)
        )
        metrics.rollout_diversity_scale = float(cfg.rollout_diversity_scale)
        metrics.rollout_diversity_start_ratio = float(cfg.rollout_diversity_start_ratio)
        steps_applied = _safe_initial_sampler_int(
            info.get("rollout_diversity_steps_applied")
        )
        iters_applied = _safe_initial_sampler_int(
            info.get("rollout_diversity_iters_applied")
        )
        if steps_applied > 0:
            metrics.rollout_diversity_enabled = True
        metrics.rollout_diversity_steps_applied += steps_applied
        metrics.rollout_diversity_iters_applied += iters_applied
        for value in info.get("rollout_diversity_grad_norms", []) or []:
            value_f = _safe_initial_sampler_float(value)
            if value_f is not None:
                grad_norms.append(value_f)
        fallback_used = _safe_initial_sampler_bool(
            info.get("rollout_diversity_fallback_used")
        )
        if fallback_used:
            metrics.rollout_diversity_fallback_used = True
            reason = info.get("rollout_diversity_fallback_reason")
            metrics.rollout_diversity_fallback_reason = (
                str(reason) if reason is not None else "unknown"
            )
        if metrics.eef_diversity_before_rollout is None:
            metrics.eef_diversity_before_rollout = _safe_initial_sampler_float(
                info.get("eef_diversity_before_rollout")
            )
        if metrics.eef_diversity_after_rollout_rbf_phase is None:
            metrics.eef_diversity_after_rollout_rbf_phase = _safe_initial_sampler_float(
                info.get("eef_diversity_after_rollout_rbf_phase")
            )
        if metrics.eef_diversity_after_rollout_final is None:
            metrics.eef_diversity_after_rollout_final = _safe_initial_sampler_float(
                info.get("eef_diversity_after_rollout_final")
            )
        if metrics.eef_diversity_rollout_retention_ratio is None:
            metrics.eef_diversity_rollout_retention_ratio = _safe_initial_sampler_float(
                info.get("eef_diversity_rollout_retention_ratio")
            )
        if metrics.endpoint_spread_before_rollout is None:
            metrics.endpoint_spread_before_rollout = _safe_initial_sampler_float(
                info.get("endpoint_spread_before_rollout")
            )
        if metrics.endpoint_spread_after_rollout_rbf_phase is None:
            metrics.endpoint_spread_after_rollout_rbf_phase = _safe_initial_sampler_float(
                info.get("endpoint_spread_after_rollout_rbf_phase")
            )
        if metrics.endpoint_spread_after_rollout_final is None:
            metrics.endpoint_spread_after_rollout_final = _safe_initial_sampler_float(
                info.get("endpoint_spread_after_rollout_final")
            )

    def _eds_score_entropy(self, costs: Tensor, temperature: float) -> float:
        probabilities = self._eds_sampling_probabilities_from_cost(costs, temperature)
        entropy = -(probabilities * torch.log(probabilities.clamp_min(1e-12))).sum()
        return float(entropy.detach().cpu().item())

    def _eds_target_distance(self, samples: Tensor, keypoints: Optional[Tensor], idx: int) -> Optional[float]:
        if keypoints is None or keypoints.numel() == 0 or keypoints.shape[-1] < 3:
            return None
        trajs = self._trajectory_reward_slice(
            self._rdt_sample_to_trajectory_3d(samples),
            "eds",
        )
        if trajs.shape[1] == 0:
            return None
        selected_final = trajs[int(idx), -1, :3]
        target = keypoints.reshape(-1, keypoints.shape[-1])[0, :3].to(
            device=selected_final.device,
            dtype=selected_final.dtype,
        )
        distance = torch.linalg.norm(selected_final - target)
        return float(distance.detach().cpu().item())

    def _eds_action_mask_violation(self, population: Tensor, cond: dict) -> float:
        mask = self._expand_action_mask_for_population(cond["action_mask"], population)
        violation = torch.abs(population * (1.0 - mask)).max()
        return float(violation.detach().cpu().item())

    def _eds_rewards_from_info(self, costs: Tensor, info: dict) -> Tensor:
        rewards = info.get("rewards") if isinstance(info, dict) else None
        if not torch.is_tensor(rewards) or rewards.shape != costs.shape:
            rewards = -costs
        resolved_rewards = rewards.detach().to(
            device=costs.device,
            dtype=costs.dtype,
        )
        if not torch.isfinite(resolved_rewards).all():
            raise ValueError("EDS rewards must be finite")
        return resolved_rewards

    def _eds_pretest_enabled(self, cfg: _EDSConfig, global_step: int) -> bool:
        pretest = cfg.mechanism_pretest
        if not isinstance(pretest, dict) or not bool(pretest.get("enabled", False)):
            return False
        if bool(pretest.get("first_chunk_only", True)) and int(global_step) != 0:
            return False
        return True

    def _eds_population_to_reward_trajectories(self, population: Tensor) -> Tensor:
        return self._trajectory_reward_slice(
            self._rdt_sample_to_trajectory_3d(population),
            "eds",
        )

    def _eds_select_eef_kcenter(
        self,
        population: Tensor,
        rewards: Tensor,
        count: int,
        reward_quantile: float,
    ) -> tuple[Tensor, dict]:
        if not torch.is_tensor(population) or population.ndim < 1:
            raise ValueError("EDS k-center population must be a batched torch.Tensor")
        if not torch.is_tensor(rewards):
            raise ValueError("EDS k-center rewards must be a torch.Tensor")
        if rewards.ndim != 1:
            raise ValueError("EDS k-center rewards must be 1-D")
        population_size = int(population.shape[0])
        if rewards.shape[0] != population_size:
            raise ValueError("EDS k-center population and rewards must have the same population size")
        if population_size == 0:
            raise ValueError("EDS k-center population must be non-empty")
        if not torch.isfinite(population).all():
            raise ValueError("EDS k-center population must be finite")
        if not torch.isfinite(rewards).all():
            raise ValueError("EDS k-center rewards must be finite")
        if isinstance(count, bool) or not isinstance(count, Integral) or int(count) < 0:
            raise ValueError("EDS k-center count must be a non-negative integer")
        if isinstance(reward_quantile, bool) or not isinstance(reward_quantile, Real):
            raise ValueError("EDS k-center reward_quantile must be a real number in [0, 1]")
        reward_quantile_value = float(reward_quantile)
        if not math.isfinite(reward_quantile_value) or not 0.0 <= reward_quantile_value <= 1.0:
            raise ValueError("EDS k-center reward_quantile must be finite and in [0, 1]")
        if int(count) == 0:
            return torch.empty(
                0,
                device=population.device,
                dtype=torch.long,
            ), {
                "anchor_requested_count": 0,
                "anchor_selected_count": 0,
                "anchor_shortfall": 0,
                "anchor_eligible_count": 0,
                "anchor_min_pairwise_eef_distance": None,
            }

        projection = self._eds_population_to_reward_trajectories(population)
        if not torch.is_tensor(projection) or projection.ndim < 1:
            raise ValueError("EDS k-center EEF projection must be a batched torch.Tensor")
        if projection.shape[0] != population_size:
            raise ValueError("EDS k-center EEF projection must preserve population size")
        projection = projection.detach().reshape(population_size, -1).float()
        if projection.shape[1] == 0 or not torch.isfinite(projection).all():
            raise ValueError("EDS k-center EEF projection must be non-empty and finite")

        selection_rewards = rewards.detach().to(
            device=projection.device,
            dtype=torch.float64,
        )
        threshold = torch.quantile(selection_rewards, reward_quantile_value)
        eligible_indices = torch.nonzero(
            selection_rewards >= threshold,
            as_tuple=False,
        ).reshape(-1)
        eligible_projection = projection.index_select(0, eligible_indices)
        eligible_rewards = selection_rewards.index_select(0, eligible_indices)
        selected_positions: list[int] = []
        selected_count = min(int(count), int(eligible_indices.numel()))
        if selected_count > 0:
            best_reward = eligible_rewards.max()
            best_positions = torch.nonzero(
                eligible_rewards == best_reward,
                as_tuple=False,
            ).reshape(-1)
            best_original_indices = eligible_indices.index_select(0, best_positions)
            selected_positions.append(
                int(best_positions[torch.argmin(best_original_indices)].item())
            )

        distances = torch.cdist(eligible_projection, eligible_projection)
        if not torch.isfinite(distances).all():
            raise ValueError("EDS k-center pairwise EEF distance matrix must be finite")
        while len(selected_positions) < selected_count:
            selected_tensor = torch.tensor(
                selected_positions,
                device=eligible_indices.device,
                dtype=torch.long,
            )
            eligible_positions = torch.arange(
                eligible_indices.numel(),
                device=eligible_indices.device,
            )
            remaining_positions = eligible_positions[
                ~torch.isin(eligible_positions, selected_tensor)
            ]
            min_distances = distances.index_select(0, remaining_positions).index_select(
                1,
                selected_tensor.to(device=distances.device),
            ).min(dim=1).values
            max_distance = min_distances.max()
            distance_tied_positions = remaining_positions[min_distances == max_distance]
            tied_rewards = eligible_rewards.index_select(0, distance_tied_positions)
            max_reward = tied_rewards.max()
            reward_tied_positions = distance_tied_positions[tied_rewards == max_reward]
            reward_tied_original_indices = eligible_indices.index_select(
                0,
                reward_tied_positions,
            )
            selected_positions.append(
                int(
                    reward_tied_positions[
                        torch.argmin(reward_tied_original_indices)
                    ].item()
                )
            )

        selected_position_tensor = torch.tensor(
            selected_positions,
            device=eligible_indices.device,
            dtype=torch.long,
        )
        selected_indices = eligible_indices.index_select(
            0,
            selected_position_tensor,
        ).to(device=population.device)
        min_pairwise_distance = None
        if selected_indices.numel() > 1:
            selected_projection = eligible_projection.index_select(
                0,
                selected_position_tensor.to(device=eligible_projection.device),
            )
            pairwise = torch.pdist(selected_projection, p=2)
            if not torch.isfinite(pairwise).all():
                raise ValueError("EDS k-center selected pairwise EEF distances must be finite")
            min_pairwise_distance = float(pairwise.min().detach().cpu().item())

        info = {
            "anchor_requested_count": int(count),
            "anchor_selected_count": int(selected_indices.numel()),
            "anchor_shortfall": int(count) - int(selected_indices.numel()),
            "anchor_eligible_count": int(eligible_indices.numel()),
            "anchor_min_pairwise_eef_distance": min_pairwise_distance,
        }
        return selected_indices, info

    def _eds_select_parent_plan(
        self,
        population: Tensor,
        costs: Tensor,
        cfg: _EDSConfig,
    ) -> EDSParentPlan:
        if not torch.is_tensor(population) or population.ndim < 1:
            raise ValueError("EDS parent population must be a batched torch.Tensor")
        population_size = int(population.shape[0])
        if population_size != int(cfg.population_size):
            raise ValueError(
                "EDS parent population size "
                f"{population_size} != configured population_size {cfg.population_size}"
            )
        costs = self._eds_validate_population_scores(costs, population_size)
        if costs.device != population.device:
            raise ValueError("EDS parent population and costs must be on the same device")

        elite_count = int(cfg.elite_carryover_count)
        if elite_count < 0 or elite_count > population_size:
            raise ValueError("EDS elite_carryover_count must be in [0, population_size]")
        if elite_count:
            elite_indices = torch.argsort(costs, stable=True)[:elite_count]
        else:
            elite_indices = torch.empty(
                0,
                device=population.device,
                dtype=torch.long,
            )

        anchor_requested_count = (
            int(cfg.parent_anchor_count)
            if cfg.parent_coverage_mode == "eef_kcenter"
            else 0
        )
        offspring_count = population_size - elite_count
        if anchor_requested_count > offspring_count:
            raise ValueError(
                "EDS parent_anchor_count cannot exceed non-elite offspring slots"
            )

        anchor_indices = torch.empty(
            0,
            device=population.device,
            dtype=torch.long,
        )
        anchor_info = {
            "anchor_requested_count": anchor_requested_count,
            "anchor_selected_count": 0,
            "anchor_shortfall": 0,
            "anchor_eligible_count": population_size - elite_count,
            "anchor_min_pairwise_eef_distance": None,
        }
        if anchor_requested_count:
            non_elite_mask = torch.ones(
                population_size,
                device=population.device,
                dtype=torch.bool,
            )
            non_elite_mask[elite_indices] = False
            non_elite_indices = torch.nonzero(
                non_elite_mask,
                as_tuple=False,
            ).reshape(-1)
            candidate_population = population.index_select(0, non_elite_indices)
            candidate_rewards = -costs.index_select(0, non_elite_indices)
            relative_anchor_indices, anchor_info = self._eds_select_eef_kcenter(
                candidate_population,
                candidate_rewards,
                count=anchor_requested_count,
                reward_quantile=cfg.parent_anchor_reward_quantile,
            )
            anchor_indices = non_elite_indices.index_select(
                0,
                relative_anchor_indices,
            )

        anchor_count = int(anchor_indices.numel())
        anchor_shortfall = anchor_requested_count - anchor_count
        anchor_fallback_reason = None
        if anchor_shortfall:
            anchor_fallback_reason = "eligible_parent_shortfall"
            log.warning(
                "EDS parent anchor shortfall: "
                f"requested={anchor_requested_count} selected={anchor_count} "
                f"eligible={anchor_info['anchor_eligible_count']}; "
                "returning missing slots to weighted sampling"
            )

        weighted_count = offspring_count - anchor_count
        selection_info = {
            "selection_beta": None,
            "selection_ess": None,
            "selection_ess_ratio": None,
            "selection_entropy_normalized": None,
            "selection_max_probability": None,
            "selection_degenerate_reward": False,
        }
        weighted_indices = torch.empty(
            0,
            device=population.device,
            dtype=torch.long,
        )
        weighted_probabilities: list[float] = []
        weighted_selection_kind = (
            "cem_uniform" if cfg.use_cem else str(cfg.parent_weighting_mode)
        )
        if weighted_count > 0:
            if cfg.use_cem:
                cem_elites = torch.argsort(costs)[: cfg.num_elites]
                sampled_elite_offsets = torch.randint(
                    0,
                    cfg.num_elites,
                    (weighted_count,),
                    device=population.device,
                )
                weighted_indices = cem_elites.index_select(
                    0,
                    sampled_elite_offsets,
                )
                weighted_probabilities = [
                    1.0 / float(cfg.num_elites)
                    for _ in range(weighted_count)
                ]
            else:
                probabilities, selection_info = self._eds_compute_parent_weights(
                    costs,
                    cfg,
                )
                weighted_indices = torch.multinomial(
                    probabilities,
                    weighted_count,
                    replacement=True,
                )
                weighted_probabilities = [
                    float(probabilities[int(parent_idx)].detach().cpu().item())
                    for parent_idx in weighted_indices.detach().cpu().tolist()
                ]

        offspring_parent_indices = torch.cat(
            [anchor_indices, weighted_indices],
            dim=0,
        )
        if offspring_parent_indices.shape != (offspring_count,):
            raise ValueError(
                "EDS parent plan produced invalid offspring parent shape "
                f"{tuple(offspring_parent_indices.shape)} != {(offspring_count,)}"
            )
        offspring_sources = (
            ("anchor_offspring",) * anchor_count
            + ("weighted_offspring",) * weighted_count
        )
        offspring_unique_parent_ratio = (
            float(offspring_parent_indices.unique().numel()) / float(offspring_count)
            if offspring_count > 0
            else None
        )
        full_parent_indices = torch.cat(
            [elite_indices, offspring_parent_indices],
            dim=0,
        )
        parent_mode_coverage = (
            float(full_parent_indices.unique().numel()) / float(population_size)
        )
        parent_probabilities: list[float | None] = (
            [None] * elite_count
            + [None] * anchor_count
            + weighted_probabilities
        )
        parent_selection_kinds = (
            ["deterministic_elite"] * elite_count
            + ["deterministic_anchor"] * anchor_count
            + [weighted_selection_kind] * weighted_count
        )
        info = {
            **selection_info,
            "elite_count": elite_count,
            "anchor_requested_count": anchor_requested_count,
            "anchor_count": anchor_count,
            "anchor_shortfall": anchor_shortfall,
            "anchor_eligible_count": int(anchor_info["anchor_eligible_count"]),
            "anchor_unique_ratio": 1.0 if anchor_count > 0 else None,
            "anchor_min_pairwise_eef_distance": anchor_info[
                "anchor_min_pairwise_eef_distance"
            ],
            "anchor_fallback_reason": anchor_fallback_reason,
            "offspring_unique_parent_ratio": offspring_unique_parent_ratio,
            "parent_mode_coverage": parent_mode_coverage,
            "parent_count_by_source": {
                "elite": elite_count,
                "anchor_offspring": anchor_count,
                "weighted_offspring": weighted_count,
            },
            "parent_probabilities": parent_probabilities,
            "parent_selection_kinds": parent_selection_kinds,
        }
        return EDSParentPlan(
            elite_indices=elite_indices,
            offspring_parent_indices=offspring_parent_indices,
            offspring_sources=offspring_sources,
            info=info,
        )

    def _eds_infer_scoring_keypoint_indices(
        self,
        guidance_fns: Optional[List[Callable]],
        keypoints: Optional[Tensor],
    ) -> list[int] | None:
        if keypoints is None or keypoints.ndim == 0:
            return None
        keypoint_count = int(keypoints.reshape(-1, keypoints.shape[-1]).shape[0])
        if keypoint_count <= 0:
            return None

        indices: list[int] = []
        for fn in guidance_fns or []:
            source = getattr(fn, "_guidance_source_text", None)
            if not isinstance(source, str):
                original = getattr(fn, "_guidance_original_func", None)
                source = getattr(original, "_guidance_source_text", None)
            if not isinstance(source, str):
                continue

            for pattern in (
                r"target_idx\s*=\s*torch\.tensor\(\s*\[\s*(\d+)\s*\]",
                r"target_idx\s*=\s*(\d+)",
                r"keypoints\s*\[\s*torch\.tensor\(\s*\[\s*(\d+)\s*\]",
                r"keypoints\s*\[\s*(\d+)\s*\]",
            ):
                for match in re.finditer(pattern, source):
                    idx = int(match.group(1))
                    if 0 <= idx < keypoint_count and idx not in indices:
                        indices.append(idx)

        if indices:
            return indices
        return [0] if keypoint_count > 0 else None

    def _eds_make_trace_stage(
        self,
        *,
        stage: str,
        iter_idx: int,
        population: Tensor,
        costs: Tensor,
        info: dict,
        parent_indices: Optional[Tensor] = None,
        parent_ranks: Optional[Tensor] = None,
        reward_before_rollout: Optional[Tensor] = None,
        reward_after_rollout: Optional[Tensor] = None,
        renoise_delta_norm: Optional[Tensor] = None,
        rollout_delta_norm: Optional[Tensor] = None,
        particle_sources: Optional[tuple[str, ...] | list[str]] = None,
        parent_probabilities: Optional[list[float | None] | tuple[float | None, ...]] = None,
        parent_selection_kinds: Optional[list[str] | tuple[str, ...]] = None,
    ) -> EDSParticleStage:
        serialized_particle_sources = None
        if particle_sources is not None:
            if len(particle_sources) != int(population.shape[0]):
                raise ValueError(
                    "EDS trace particle_sources length "
                    f"{len(particle_sources)} != population size {population.shape[0]}"
                )
            serialized_particle_sources = [str(source) for source in particle_sources]
        serialized_parent_probabilities = None
        if parent_probabilities is not None:
            if len(parent_probabilities) != int(population.shape[0]):
                raise ValueError(
                    "EDS trace parent_probabilities length "
                    f"{len(parent_probabilities)} != population size {population.shape[0]}"
                )
            serialized_parent_probabilities = [
                None if value is None else float(value)
                for value in parent_probabilities
            ]
        serialized_parent_selection_kinds = None
        if parent_selection_kinds is not None:
            if len(parent_selection_kinds) != int(population.shape[0]):
                raise ValueError(
                    "EDS trace parent_selection_kinds length "
                    f"{len(parent_selection_kinds)} != population size {population.shape[0]}"
                )
            serialized_parent_selection_kinds = [
                str(value) for value in parent_selection_kinds
            ]
        rewards = self._eds_rewards_from_info(costs, info)
        return EDSParticleStage(
            stage=stage,
            iter_idx=int(iter_idx),
            actions=population.detach().cpu(),
            trajectories=self._eds_population_to_reward_trajectories(population).detach().cpu(),
            rewards=rewards.detach().cpu(),
            costs=costs.detach().cpu(),
            parent_indices=parent_indices.detach().cpu() if parent_indices is not None else None,
            parent_ranks=parent_ranks.detach().cpu() if parent_ranks is not None else None,
            reward_before_rollout=(
                reward_before_rollout.detach().cpu()
                if reward_before_rollout is not None
                else None
            ),
            reward_after_rollout=(
                reward_after_rollout.detach().cpu()
                if reward_after_rollout is not None
                else None
            ),
            renoise_delta_norm=(
                renoise_delta_norm.detach().cpu()
                if renoise_delta_norm is not None
                else None
            ),
            rollout_delta_norm=(
                rollout_delta_norm.detach().cpu()
                if rollout_delta_norm is not None
                else None
            ),
            particle_sources=serialized_particle_sources,
            parent_probabilities=serialized_parent_probabilities,
            parent_selection_kinds=serialized_parent_selection_kinds,
        )

    def _eds_guided_denoise_loop(
        self,
        *,
        x_t: Tensor,
        cond: dict,
        keypoints: Optional[Tensor],
        guidance_fns: Optional[List[Callable]],
        eds_config: _EDSConfig,
        verbose: bool,
        global_step: int,
        current_stage: int,
    ) -> Tensor:
        cfg = eds_config
        loop_start = time.perf_counter()
        adaptive_rbf_enabled = (
            cfg.truncated_rollout_mode == "rbf_diverse"
            and cfg.rollout_diversity_control_mode == "adaptive_band"
        )
        metrics = EDSChunkMetrics(
            guidance_type="eds",
            reward_mode=cfg.reward_mode,
            population_size=cfg.population_size,
            cem_iters=cfg.cem_iters,
            use_cem=cfg.use_cem,
            temperature=cfg.temperature,
            eds_enter_count=1,
            parent_weighting_mode=cfg.parent_weighting_mode,
            parent_coverage_mode=cfg.parent_coverage_mode,
            rollout_diversity_control_mode=cfg.rollout_diversity_control_mode,
            chunk_population_mode=cfg.chunk_population_mode,
            search_schedule_mode=cfg.search_schedule_mode,
            adaptive_rbf_enabled=adaptive_rbf_enabled,
        )
        artifact_iters: list[dict] = []
        action_mask = cond["action_mask"]
        trace_enabled = self._eds_pretest_enabled(cfg, global_step)
        trace_stages: list[EDSParticleStage] = []
        rollout_diversity_grad_norms: list[float] = []

        population = self._eds_initial_population(x_t=x_t, cond=cond, cfg=cfg)
        initial_sampler_info = getattr(self, "_last_eds_initial_sampler_info", None) or {}
        _populate_initial_sampler_metrics(
            metrics,
            cfg,
            initial_sampler_info,
        )
        population = self._apply_action_mask(population, cond)
        chunk_population_sources = ("fresh",) * int(cfg.population_size)
        initial_trace_particle_sources = None
        previous_selected_population = None
        precomputed_population_scores = None
        precomputed_population_info = None
        chunk_memory_info: dict = {}
        initial_score_call_count = 1
        if cfg.chunk_population_mode == "warm_start_mix":
            (
                population,
                precomputed_population_scores,
                precomputed_population_info,
                chunk_memory_info,
            ) = self._eds_compose_initial_population_from_memory(
                fresh_population=population,
                cond=cond,
                cfg=cfg,
                keypoints=keypoints,
                guidance_fns=guidance_fns,
                global_step=global_step,
                current_stage=current_stage,
                trace_enabled=trace_enabled,
            )
            self._eds_apply_chunk_memory_metrics(metrics, chunk_memory_info)
            chunk_population_sources = tuple(chunk_memory_info["particle_sources"])
            initial_trace_particle_sources = chunk_population_sources
            previous_selected_population = chunk_memory_info[
                "previous_selected_population"
            ]
            initial_score_call_count = max(
                1,
                int(chunk_memory_info["precomputed_score_call_count"]),
            )
        self._eds_record_initial_eef_diversity_metrics(
            metrics,
            population=population,
            cond=cond,
        )

        if precomputed_population_scores is None:
            population_scores, population_info = self._eds_score_population_as_cost(
                population,
                keypoints=keypoints,
                guidance_fns=guidance_fns,
                reward_mode=cfg.reward_mode,
                shuffle_seed=cfg.shuffle_seed,
            )
        else:
            population_scores = precomputed_population_scores
            population_info = precomputed_population_info or {}
        population_scores = self._eds_validate_population_scores(
            population_scores,
            cfg.population_size,
        )
        population_rewards = self._eds_rewards_from_info(population_scores, population_info)
        adaptive_diversity_reference = metrics.initial_eef_diversity_final
        initial_best_idx = int(torch.argmin(population_scores).item())
        max_action_mask_violation = self._eds_action_mask_violation(population, cond)

        metrics.score_call_count = initial_score_call_count
        metrics.population_size_observed = int(population.shape[0])
        metrics.population_shape = list(population.shape)
        metrics.score_shape = list(population_scores.shape)
        metrics.initial_best_reward = float(
            population_rewards[initial_best_idx].detach().cpu().item()
        )
        metrics.initial_mean_reward = float(population_rewards.mean().detach().cpu().item())
        metrics.population_diversity_initial = self._eds_population_diversity(population)
        metrics.target_distance_before = self._eds_target_distance(
            population,
            keypoints,
            initial_best_idx,
        )
        initial_action_candidates = self._decode_visualization_action_candidates(
            population
        ).detach().cpu()
        if trace_enabled:
            memory_trace_specs = (
                (
                    "memory_fresh_initial",
                    "_trace_fresh_population",
                    "_trace_fresh_costs",
                    "_trace_fresh_rewards",
                    None,
                ),
                (
                    "memory_adapted_candidates",
                    "_trace_adapted_memory",
                    "_trace_adapted_memory_costs",
                    "_trace_adapted_memory_rewards",
                    None,
                ),
                (
                    "memory_composed_initial",
                    "_trace_composed_population",
                    "_trace_composed_costs",
                    "_trace_composed_rewards",
                    initial_trace_particle_sources,
                ),
            )
            if all(
                population_key in chunk_memory_info
                and costs_key in chunk_memory_info
                and rewards_key in chunk_memory_info
                for _, population_key, costs_key, rewards_key, _ in memory_trace_specs
            ):
                for (
                    stage_name,
                    population_key,
                    costs_key,
                    rewards_key,
                    stage_sources,
                ) in memory_trace_specs:
                    stage_population = chunk_memory_info[population_key].to(
                        device=population.device,
                        dtype=population.dtype,
                    )
                    stage_costs = chunk_memory_info[costs_key].to(
                        device=population.device,
                        dtype=population_scores.dtype,
                    )
                    stage_rewards = chunk_memory_info[rewards_key].to(
                        device=population.device,
                        dtype=population_rewards.dtype,
                    )
                    if stage_sources is None:
                        source = (
                            "memory"
                            if stage_name == "memory_adapted_candidates"
                            else "fresh"
                        )
                        stage_sources = (source,) * int(stage_population.shape[0])
                    trace_stages.append(
                        self._eds_make_trace_stage(
                            stage=stage_name,
                            iter_idx=0,
                            population=stage_population,
                            costs=stage_costs,
                            info={"rewards": stage_rewards},
                            particle_sources=stage_sources,
                        )
                    )
            for stage_name, stage_population in getattr(
                self,
                "_last_eds_initial_sampler_trace_stages",
                [],
            ):
                stage_population = self._apply_action_mask(
                    stage_population.to(device=population.device, dtype=population.dtype),
                    cond,
                )
                if (
                    stage_name == "initial_final"
                    and stage_population.shape == population.shape
                    and torch.equal(stage_population.detach(), population.detach())
                ):
                    stage_scores = population_scores
                    stage_info = population_info
                else:
                    stage_scores, stage_info = self._eds_score_population_as_cost(
                        stage_population,
                        keypoints=keypoints,
                        guidance_fns=guidance_fns,
                        reward_mode=cfg.reward_mode,
                        shuffle_seed=cfg.shuffle_seed,
                    )
                    stage_scores = self._eds_validate_population_scores(
                        stage_scores,
                        cfg.population_size,
                    )
                trace_stages.append(
                    self._eds_make_trace_stage(
                        stage=stage_name,
                        iter_idx=0,
                        population=stage_population,
                        costs=stage_scores,
                        info=stage_info,
                    )
                )
            trace_stages.append(
                self._eds_make_trace_stage(
                    stage="initial",
                    iter_idx=0,
                    population=population,
                    costs=population_scores,
                    info=population_info,
                    particle_sources=initial_trace_particle_sources,
                )
            )
            trace_stages.append(
                self._eds_make_trace_stage(
                    stage="scored",
                    iter_idx=0,
                    population=population,
                    costs=population_scores,
                    info=population_info,
                    particle_sources=initial_trace_particle_sources,
                )
            )

        trunc_step_schedule = np.linspace(
            cfg.renoise_t_max,
            cfg.renoise_t_min,
            cfg.cem_iters,
        ).astype(int)

        last_particle_sources = tuple("initial" for _ in range(cfg.population_size))
        first_elite_population: Optional[Tensor] = None
        parent_mode_coverages: list[float] = []
        offspring_unique_parent_ratios: list[float] = []
        anchor_unique_ratios: list[float] = []
        anchor_min_pairwise_distances: list[float] = []
        cumulative_parent_count_by_source: dict[str, int] = {}
        elite_count_observed = int(cfg.elite_carryover_count)
        anchor_count_observed = 0
        adaptive_current_values: list[float] = []
        adaptive_requested_scales: list[float] = []
        adaptive_applied_scales: list[float] = []
        adaptive_decision_count = 0
        adaptive_active_iter_count = 0
        adaptive_band_hit_count = 0
        adaptive_previous_best_idx = initial_best_idx
        adaptive_previous_best_reward = float(
            population_rewards[initial_best_idx].detach().cpu().item()
        )
        adaptive_reward_improvement: Optional[float] = None
        adaptive_diversity_band_state = "in_band"
        adaptive_best_lineage_stable = False
        adaptive_reward_plateau_count = 0
        adaptive_stable_lineage_count = 0
        selection_trace_iters: list[dict] = []
        adaptive_rollout_trace_iters: list[dict] = []
        anchor_lineage_ids: Optional[Tensor] = None

        for i in range(cfg.cem_iters):
            if cfg.search_schedule_mode == "legacy_linear":
                n_trunc_steps = int(trunc_step_schedule[i])
                resolved_renoise_reason = "legacy_linear"
            else:
                n_trunc_steps, resolved_renoise_reason = (
                    self._eds_resolve_renoise_steps(
                        cfg=cfg,
                        iter_idx=i,
                        reward_improvement=adaptive_reward_improvement,
                        diversity_band_state=adaptive_diversity_band_state,
                        best_lineage_stable=adaptive_best_lineage_stable,
                    )
                )
            parent_source_scores = population_scores
            parent_source_rewards = population_rewards
            plan = self._eds_select_parent_plan(
                population,
                population_scores,
                cfg,
            )
            selection_info = None if cfg.use_cem else plan.info
            unique_parent_ratio = plan.info["offspring_unique_parent_ratio"]
            elite_count = int(plan.elite_indices.numel())
            offspring_count = int(plan.offspring_parent_indices.numel())
            elite_population = population.index_select(0, plan.elite_indices)
            offspring = population.index_select(0, plan.offspring_parent_indices)
            if i == 0:
                first_elite_population = elite_population.detach()
            if tuple(offspring.shape) != (offspring_count, 64, 128):
                raise ValueError(
                    "EDS offspring population must have shape "
                    f"{(offspring_count, 64, 128)}, got {tuple(offspring.shape)}"
                )
            full_parent_indices = torch.cat(
                [plan.elite_indices, plan.offspring_parent_indices],
                dim=0,
            )
            full_particle_sources = (
                ("elite",) * elite_count + plan.offspring_sources
            )
            parent_index_values = full_parent_indices.detach().cpu().tolist()
            full_chunk_population_sources = tuple(
                chunk_population_sources[int(parent_idx)]
                for parent_idx in parent_index_values
            )
            parent_mode_coverages.append(float(plan.info["parent_mode_coverage"]))
            offspring_unique_parent_ratio = plan.info[
                "offspring_unique_parent_ratio"
            ]
            if offspring_unique_parent_ratio is not None:
                offspring_unique_parent_ratios.append(
                    float(offspring_unique_parent_ratio)
                )
            anchor_count = int(plan.info["anchor_count"])
            anchor_unique_ratio = plan.info["anchor_unique_ratio"]
            if anchor_count > 0 and anchor_unique_ratio is not None:
                anchor_unique_ratios.append(float(anchor_unique_ratio))
            anchor_min_distance = plan.info["anchor_min_pairwise_eef_distance"]
            if anchor_count > 0 and anchor_min_distance is not None:
                anchor_min_pairwise_distances.append(float(anchor_min_distance))
            elite_count_observed = max(elite_count_observed, elite_count)
            anchor_count_observed = max(anchor_count_observed, anchor_count)
            for source, source_count in plan.info["parent_count_by_source"].items():
                cumulative_parent_count_by_source[str(source)] = (
                    cumulative_parent_count_by_source.get(str(source), 0)
                    + int(source_count)
                )
            metrics.resample_count += 1

            parent_indices_for_scores = full_parent_indices.to(
                device=parent_source_scores.device
            )
            full_parent_rewards = parent_source_rewards.index_select(
                0,
                parent_indices_for_scores,
            )
            full_parent_costs = parent_source_scores.index_select(
                0,
                parent_indices_for_scores,
            )
            parent_rank_order = torch.argsort(parent_source_rewards, descending=True)
            parent_source_ranks = torch.empty_like(parent_rank_order)
            parent_source_ranks[parent_rank_order] = torch.arange(
                1,
                parent_rank_order.numel() + 1,
                device=parent_source_ranks.device,
                dtype=parent_source_ranks.dtype,
            )
            full_parent_ranks = parent_source_ranks.index_select(
                0,
                parent_indices_for_scores.to(device=parent_source_ranks.device),
            )
            offspring_parent_rewards = full_parent_rewards[elite_count:]
            offspring_parent_ranks = full_parent_ranks[elite_count:]
            full_parent_probabilities = list(
                plan.info.get("parent_probabilities", [None] * cfg.population_size)
            )
            full_parent_selection_kinds = list(
                plan.info.get(
                    "parent_selection_kinds",
                    [
                        (
                            "deterministic_elite"
                            if source == "elite"
                            else "deterministic_anchor"
                            if source == "anchor_offspring"
                            else "cem_uniform"
                            if cfg.use_cem
                            else str(cfg.parent_weighting_mode)
                        )
                        for source in full_particle_sources
                    ],
                )
            )
            if (
                len(full_parent_probabilities) != cfg.population_size
                or len(full_parent_selection_kinds) != cfg.population_size
            ):
                raise ValueError("EDS parent trace metadata must match population size")
            if i == 0 and anchor_count > 0:
                anchor_lineage_ids = torch.full(
                    (cfg.population_size,),
                    -1,
                    device=full_parent_indices.device,
                    dtype=torch.long,
                )
                anchor_lineage_ids[
                    elite_count : elite_count + anchor_count
                ] = torch.arange(
                    anchor_count,
                    device=full_parent_indices.device,
                    dtype=torch.long,
                )
                metrics.initial_anchor_lineage_count = anchor_count
            elif i > 0 and anchor_lineage_ids is not None:
                anchor_lineage_ids = anchor_lineage_ids.index_select(
                    0,
                    full_parent_indices.to(device=anchor_lineage_ids.device),
                )
            offspring_parent_probabilities = full_parent_probabilities[elite_count:]
            offspring_parent_selection_kinds = full_parent_selection_kinds[elite_count:]
            selection_trace_enabled = (
                cfg.parent_weighting_mode != "legacy_temperature"
                or cfg.parent_coverage_mode != "none"
                or elite_count > 0
            )
            if trace_enabled and selection_trace_enabled:
                selection_trace_iters.append(
                    {
                        "iter_idx": i,
                        "selection_beta": plan.info.get("selection_beta"),
                        "selection_ess": plan.info.get("selection_ess"),
                        "selection_ess_ratio": plan.info.get("selection_ess_ratio"),
                        "selection_population_size": cfg.population_size,
                        "selection_entropy_normalized": plan.info.get(
                            "selection_entropy_normalized"
                        ),
                        "selection_max_probability": plan.info.get(
                            "selection_max_probability"
                        ),
                        "selection_degenerate_reward": plan.info.get(
                            "selection_degenerate_reward", False
                        ),
                        "parent_indices": [
                            int(value)
                            for value in full_parent_indices.detach().cpu().tolist()
                        ],
                        "parent_ranks": [
                            int(value)
                            for value in full_parent_ranks.detach().cpu().tolist()
                        ],
                        "parent_sources": list(full_particle_sources),
                        "parent_probabilities": full_parent_probabilities,
                        "parent_selection_kinds": full_parent_selection_kinds,
                        "anchor_lineage_ids": (
                            [
                                int(value)
                                for value in anchor_lineage_ids.detach().cpu().tolist()
                            ]
                            if anchor_lineage_ids is not None
                            else None
                        ),
                        "parent_count_by_source": dict(
                            plan.info["parent_count_by_source"]
                        ),
                        "parent_mode_coverage": plan.info.get(
                            "parent_mode_coverage"
                        ),
                        "offspring_unique_parent_ratio": plan.info.get(
                            "offspring_unique_parent_ratio"
                        ),
                        "anchor_min_pairwise_eef_distance": plan.info.get(
                            "anchor_min_pairwise_eef_distance"
                        ),
                    }
                )
            resampled_population = torch.cat([elite_population, offspring], dim=0)
            if trace_enabled and i == 0:
                trace_stages.append(
                    self._eds_make_trace_stage(
                        stage="resampled",
                        iter_idx=i,
                        population=resampled_population,
                        costs=full_parent_costs,
                        info={"rewards": full_parent_rewards},
                        parent_indices=full_parent_indices,
                        parent_ranks=full_parent_ranks,
                        particle_sources=full_particle_sources,
                        parent_probabilities=full_parent_probabilities,
                        parent_selection_kinds=full_parent_selection_kinds,
                    )
                )

            offspring_before_renoise = offspring
            offspring = self._eds_renoise_reference(offspring, n_trunc_steps)
            if tuple(offspring.shape) != (offspring_count, 64, 128):
                raise ValueError(
                    "EDS renoised offspring must have shape "
                    f"{(offspring_count, 64, 128)}, got {tuple(offspring.shape)}"
                )
            renoise_delta_norm = (
                offspring - offspring_before_renoise
            ).reshape(offspring_count, -1).norm(dim=1)
            if trace_enabled and i == 0:
                renoise_costs, renoise_info = self._eds_score_population_as_cost(
                    offspring,
                    keypoints=keypoints,
                    guidance_fns=guidance_fns,
                    reward_mode=cfg.reward_mode,
                    shuffle_seed=cfg.shuffle_seed,
                )
                renoise_costs = self._eds_validate_population_scores(
                    renoise_costs,
                    offspring_count,
                )
                trace_stages.append(
                    self._eds_make_trace_stage(
                        stage="renoised",
                        iter_idx=i,
                        population=offspring,
                        costs=renoise_costs,
                        info=renoise_info,
                        parent_indices=plan.offspring_parent_indices,
                        parent_ranks=offspring_parent_ranks,
                        reward_before_rollout=offspring_parent_rewards,
                        renoise_delta_norm=renoise_delta_norm,
                        particle_sources=plan.offspring_sources,
                        parent_probabilities=offspring_parent_probabilities,
                        parent_selection_kinds=offspring_parent_selection_kinds,
                    )
                )
            metrics.renoise_count += 1
            self._reset_scheduler_particle_history_after_resample(self._noise_scheduler)
            offspring_before_rollout = offspring
            controller_decision: Optional[EDSRolloutDiversityDecision] = None
            controller_info: dict = {}
            if (
                cfg.truncated_rollout_mode == "rbf_diverse"
                and cfg.rollout_diversity_control_mode == "adaptive_band"
                and self._eds_should_apply_rollout_diversity(cfg, i)
            ):
                current_diversity = self._eds_eef_trajectory_diversity(offspring)
                controller_decision, controller_info = (
                    self._eds_adaptive_rollout_diversity_decision(
                        reference=adaptive_diversity_reference,
                        current=current_diversity,
                        rewards=parent_source_rewards,
                        iter_idx=i,
                        cfg=cfg,
                    )
                )

            rollout_kwargs = {
                "cond": cond,
                "action_mask": action_mask,
                "noisy_action": offspring,
                "keypoints": keypoints,
                "guidance_fns": guidance_fns,
                "n_trunc_steps": n_trunc_steps,
                "reward_mode": cfg.reward_mode,
                "shuffle_seed": cfg.shuffle_seed,
                "cfg": cfg,
                "iter_idx": i,
            }
            if controller_decision is not None:
                rollout_kwargs["diversity_scale_override"] = controller_decision.scale
            offspring, rollout_scores, rollout_info = self._eds_rollout_reference(
                **rollout_kwargs
            )
            if tuple(offspring.shape) != (offspring_count, 64, 128):
                raise ValueError(
                    "EDS rollout offspring must have shape "
                    f"{(offspring_count, 64, 128)}, got {tuple(offspring.shape)}"
                )
            rollout_scores = self._eds_validate_population_scores(
                rollout_scores,
                offspring_count,
            )
            metrics.score_call_count += 1
            if controller_decision is not None:
                applied_steps = _safe_initial_sampler_int(
                    rollout_info.get("rollout_diversity_steps_applied")
                )
                applied_scale = (
                    float(controller_decision.scale)
                    if controller_decision.scale > 0.0 and applied_steps > 0
                    else 0.0
                )
                active_particle_count = offspring_count if applied_scale > 0.0 else 0
                controller_info["adaptive_rbf_scale_applied"] = applied_scale
                controller_info[
                    "adaptive_rbf_active_particle_count"
                ] = active_particle_count
                rollout_info = {**rollout_info, **controller_info}

                adaptive_decision_count += 1
                current_value = _safe_initial_sampler_float(
                    controller_info.get("diversity_current")
                )
                if current_value is not None:
                    adaptive_current_values.append(current_value)
                requested_scale = _safe_initial_sampler_float(
                    controller_info.get("adaptive_rbf_scale_requested")
                )
                if requested_scale is not None:
                    adaptive_requested_scales.append(requested_scale)
                adaptive_applied_scales.append(applied_scale)
                if active_particle_count > 0:
                    adaptive_active_iter_count += 1
                    metrics.adaptive_rbf_particle_count = max(
                        metrics.adaptive_rbf_particle_count,
                        active_particle_count,
                    )
                if controller_info.get("adaptive_rbf_band_hit") is True:
                    adaptive_band_hit_count += 1
                if metrics.adaptive_rbf_reference is None:
                    metrics.adaptive_rbf_reference = _safe_initial_sampler_float(
                        controller_info.get("diversity_reference")
                    )
                    metrics.adaptive_rbf_band_low = _safe_initial_sampler_float(
                        controller_info.get("diversity_band_low")
                    )
                    metrics.adaptive_rbf_band_high = _safe_initial_sampler_float(
                        controller_info.get("diversity_band_high")
                    )
                if _safe_initial_sampler_bool(
                    controller_info.get("adaptive_rbf_fallback_used")
                ):
                    metrics.adaptive_rbf_fallback_used = True
                    if metrics.adaptive_rbf_fallback_reason is None:
                        fallback_reason = controller_info.get(
                            "adaptive_rbf_fallback_reason"
                        )
                        metrics.adaptive_rbf_fallback_reason = (
                            str(fallback_reason)
                            if fallback_reason is not None
                            else "unknown"
                        )
            if elite_count > 0:
                rollout_info = self._eds_rollout_info_with_full_population_diversity(
                    rollout_info,
                    elite_population=elite_population,
                    offspring_before_rollout=offspring_before_rollout,
                    offspring_after_rollout=offspring,
                    cond=cond,
                )
            self._eds_update_rollout_diversity_metrics(
                metrics,
                rollout_info,
                cfg,
                rollout_diversity_grad_norms,
            )
            if (
                trace_enabled
                and adaptive_rbf_enabled
            ):
                adaptive_rollout_trace_iters.append(
                    {
                        "iter_idx": i,
                        "diversity_reference": _safe_initial_sampler_float(
                            rollout_info.get("diversity_reference")
                        ),
                        "diversity_current": _safe_initial_sampler_float(
                            rollout_info.get("diversity_current")
                        ),
                        "diversity_band_low": _safe_initial_sampler_float(
                            rollout_info.get("diversity_band_low")
                        ),
                        "diversity_band_high": _safe_initial_sampler_float(
                            rollout_info.get("diversity_band_high")
                        ),
                        "reward_confidence": _safe_initial_sampler_float(
                            rollout_info.get("adaptive_rbf_reward_confidence")
                        ),
                        "scale_requested": _safe_initial_sampler_float(
                            rollout_info.get("adaptive_rbf_scale_requested")
                        ),
                        "scale_applied": _safe_initial_sampler_float(
                            rollout_info.get("adaptive_rbf_scale_applied")
                        ),
                        "active_particle_count": _safe_initial_sampler_int(
                            rollout_info.get("adaptive_rbf_active_particle_count")
                        ),
                        "reason": (
                            str(rollout_info["adaptive_rbf_trigger_reason"])
                            if rollout_info.get("adaptive_rbf_trigger_reason")
                            is not None
                            else "not_scheduled"
                        ),
                        "fallback_used": _safe_initial_sampler_bool(
                            rollout_info.get("adaptive_rbf_fallback_used")
                        ),
                        "fallback_reason": (
                            str(rollout_info["adaptive_rbf_fallback_reason"])
                            if rollout_info.get("adaptive_rbf_fallback_reason")
                            is not None
                            else None
                        ),
                    }
                )
            metrics.rollout_count += 1
            rollout_delta_norm = (
                offspring - offspring_before_rollout
            ).reshape(offspring_count, -1).norm(dim=1)

            population = torch.cat([elite_population, offspring], dim=0)
            population = self._apply_action_mask(population, cond)
            chunk_population_sources = full_chunk_population_sources
            if tuple(population.shape) != (cfg.population_size, 64, 128):
                raise ValueError(
                    "EDS population must have shape "
                    f"{(cfg.population_size, 64, 128)}, got {tuple(population.shape)}"
                )
            if elite_count > 0:
                population_scores, full_score_info = self._eds_score_population_as_cost(
                    population,
                    keypoints=keypoints,
                    guidance_fns=guidance_fns,
                    reward_mode=cfg.reward_mode,
                    shuffle_seed=cfg.shuffle_seed,
                )
                population_scores = self._eds_validate_population_scores(
                    population_scores,
                    cfg.population_size,
                )
                metrics.score_call_count += 1
                rollout_nonreward_info = {
                    key: value
                    for key, value in rollout_info.items()
                    if key != "rewards"
                }
                population_info = {**rollout_nonreward_info, **full_score_info}
            else:
                population_scores = rollout_scores
                population_info = rollout_info
            population_rewards = self._eds_rewards_from_info(
                population_scores,
                population_info,
            )

            if trace_enabled:
                if i == 0:
                    for stage_name, stage_population in rollout_info.get(
                        "rollout_diversity_trace_stages",
                        [],
                    ):
                        stage_population = self._apply_action_mask(
                            stage_population.to(
                                device=population.device,
                                dtype=population.dtype,
                            ),
                            cond,
                        )
                        if (
                            stage_name == "rollout_final"
                            and stage_population.shape == offspring.shape
                            and torch.equal(
                                stage_population.detach(),
                                self._apply_action_mask(offspring, cond).detach(),
                            )
                        ):
                            stage_scores = rollout_scores
                            stage_info = rollout_info
                        else:
                            stage_scores, stage_info = self._eds_score_population_as_cost(
                                stage_population,
                                keypoints=keypoints,
                                guidance_fns=guidance_fns,
                                reward_mode=cfg.reward_mode,
                                shuffle_seed=cfg.shuffle_seed,
                            )
                            stage_scores = self._eds_validate_population_scores(
                                stage_scores,
                                offspring_count,
                            )
                        trace_stages.append(
                            self._eds_make_trace_stage(
                                stage=stage_name,
                                iter_idx=i,
                                population=stage_population,
                                costs=stage_scores,
                                info=stage_info,
                                parent_indices=plan.offspring_parent_indices,
                                parent_ranks=offspring_parent_ranks,
                                reward_before_rollout=offspring_parent_rewards,
                                renoise_delta_norm=renoise_delta_norm,
                                particle_sources=plan.offspring_sources,
                                parent_probabilities=offspring_parent_probabilities,
                                parent_selection_kinds=offspring_parent_selection_kinds,
                            )
                        )
                    zero_elite_delta = torch.zeros(
                        elite_count,
                        device=population.device,
                        dtype=renoise_delta_norm.dtype,
                    )
                    full_renoise_delta_norm = torch.cat(
                        [zero_elite_delta, renoise_delta_norm],
                        dim=0,
                    )
                    full_rollout_delta_norm = torch.cat(
                        [zero_elite_delta, rollout_delta_norm],
                        dim=0,
                    )
                    trace_stages.append(
                        self._eds_make_trace_stage(
                            stage="after_rollout",
                            iter_idx=i,
                            population=population,
                            costs=population_scores,
                            info=population_info,
                            parent_indices=full_parent_indices,
                            parent_ranks=full_parent_ranks,
                            reward_before_rollout=full_parent_rewards,
                            reward_after_rollout=population_rewards,
                            renoise_delta_norm=full_renoise_delta_norm,
                            rollout_delta_norm=full_rollout_delta_norm,
                            particle_sources=full_particle_sources,
                            parent_probabilities=full_parent_probabilities,
                            parent_selection_kinds=full_parent_selection_kinds,
                        )
                    )
                if bool(cfg.mechanism_pretest.get("save_full_process", True)):
                    max_full_process_iters = int(
                        cfg.mechanism_pretest.get("max_full_process_iters", cfg.cem_iters)
                    )
                    if i < max_full_process_iters:
                        trace_stages.append(
                            self._eds_make_trace_stage(
                                stage="full_process_after_rollout",
                                iter_idx=i,
                                population=population,
                                costs=population_scores,
                                info=population_info,
                                parent_indices=full_parent_indices,
                                parent_ranks=full_parent_ranks,
                                particle_sources=full_particle_sources,
                                parent_probabilities=full_parent_probabilities,
                                parent_selection_kinds=full_parent_selection_kinds,
                            )
                        )
            iter_best_idx = int(torch.argmin(population_scores).item())
            iter_best_reward_value = float(
                population_rewards[iter_best_idx].detach().cpu().item()
            )
            adaptive_iteration_improvement: Optional[float] = None
            adaptive_iteration_lineage_stable = False
            adaptive_iteration_diversity_state = "unknown"
            if cfg.search_schedule_mode == "adaptive":
                adaptive_iteration_improvement = (
                    iter_best_reward_value - adaptive_previous_best_reward
                )
                adaptive_iteration_lineage_stable = (
                    self._eds_best_lineage_is_stable(
                        full_parent_indices=full_parent_indices,
                        current_best_idx=iter_best_idx,
                        previous_best_idx=adaptive_previous_best_idx,
                    )
                )
                adaptive_iteration_diversity_state = (
                    self._eds_diversity_band_state(
                        reference=adaptive_diversity_reference,
                        current=self._eds_eef_trajectory_diversity(population),
                        cfg=cfg,
                    )
                )
                if (
                    abs(adaptive_iteration_improvement)
                    <= float(cfg.adaptive_reward_improvement_eps)
                ):
                    adaptive_reward_plateau_count += 1
                else:
                    adaptive_reward_plateau_count = 0
                if adaptive_iteration_lineage_stable:
                    adaptive_stable_lineage_count += 1
                else:
                    adaptive_stable_lineage_count = 0
            iter_reward_spread = population_rewards.max() - population_rewards.mean()
            metrics.per_iter.append(
                EDSIterMetrics(
                    iter_idx=i,
                    n_trunc_steps=n_trunc_steps,
                    best_idx=iter_best_idx,
                    best_cost=float(population_scores[iter_best_idx].detach().cpu().item()),
                    best_reward=iter_best_reward_value,
                    mean_reward=float(population_rewards.mean().detach().cpu().item()),
                    reward_spread=float(iter_reward_spread.detach().cpu().item()),
                    score_entropy=self._eds_score_entropy(population_scores, cfg.temperature),
                    unique_parent_ratio=unique_parent_ratio,
                    population_diversity=self._eds_population_diversity(population),
                    selection_beta=(
                        selection_info["selection_beta"]
                        if selection_info is not None
                        else None
                    ),
                    selection_ess=(
                        selection_info["selection_ess"]
                        if selection_info is not None
                        else None
                    ),
                    selection_ess_ratio=(
                        selection_info["selection_ess_ratio"]
                        if selection_info is not None
                        else None
                    ),
                    selection_entropy_normalized=(
                        selection_info["selection_entropy_normalized"]
                        if selection_info is not None
                        else None
                    ),
                    selection_max_probability=(
                        selection_info["selection_max_probability"]
                        if selection_info is not None
                        else None
                    ),
                    selection_degenerate_reward=(
                        selection_info["selection_degenerate_reward"]
                        if selection_info is not None
                        else False
                    ),
                    elite_count=elite_count,
                    anchor_count=int(plan.info["anchor_count"]),
                    anchor_min_pairwise_eef_distance=plan.info[
                        "anchor_min_pairwise_eef_distance"
                    ],
                    diversity_reference=_safe_initial_sampler_float(
                        rollout_info.get("diversity_reference")
                    ),
                    diversity_band_low=_safe_initial_sampler_float(
                        rollout_info.get("diversity_band_low")
                    ),
                    diversity_band_high=_safe_initial_sampler_float(
                        rollout_info.get("diversity_band_high")
                    ),
                    diversity_current=_safe_initial_sampler_float(
                        rollout_info.get("diversity_current")
                    ),
                    adaptive_rbf_reward_confidence=_safe_initial_sampler_float(
                        rollout_info.get("adaptive_rbf_reward_confidence")
                    ),
                    adaptive_rbf_scale_requested=_safe_initial_sampler_float(
                        rollout_info.get("adaptive_rbf_scale_requested")
                    ),
                    adaptive_rbf_scale_applied=_safe_initial_sampler_float(
                        rollout_info.get("adaptive_rbf_scale_applied")
                    ),
                    adaptive_rbf_active_particle_count=_safe_initial_sampler_int(
                        rollout_info.get("adaptive_rbf_active_particle_count")
                    ),
                    adaptive_rbf_band_hit=(
                        bool(rollout_info["adaptive_rbf_band_hit"])
                        if "adaptive_rbf_band_hit" in rollout_info
                        else None
                    ),
                    adaptive_rbf_fallback_used=_safe_initial_sampler_bool(
                        rollout_info.get("adaptive_rbf_fallback_used")
                    ),
                    adaptive_rbf_fallback_reason=(
                        str(rollout_info["adaptive_rbf_fallback_reason"])
                        if rollout_info.get("adaptive_rbf_fallback_reason") is not None
                        else None
                    ),
                    adaptive_rbf_enabled=adaptive_rbf_enabled,
                    resolved_rollout_diversity_scale=_safe_initial_sampler_float(
                        rollout_info.get("resolved_rollout_diversity_scale")
                    ),
                    adaptive_rbf_trigger_reason=(
                        str(rollout_info["adaptive_rbf_trigger_reason"])
                        if rollout_info.get("adaptive_rbf_trigger_reason") is not None
                        else None
                    ),
                    resolved_renoise_reason=resolved_renoise_reason,
                    reward_improvement=adaptive_iteration_improvement,
                    diversity_band_state=adaptive_iteration_diversity_state,
                    best_lineage_stable=adaptive_iteration_lineage_stable,
                    stable_lineage_count=adaptive_stable_lineage_count,
                )
            )
            last_particle_sources = full_particle_sources
            max_action_mask_violation = max(
                max_action_mask_violation,
                self._eds_action_mask_violation(population, cond),
            )
            artifact_iters.append(
                {
                    "iter_idx": i,
                    "actions": self._decode_visualization_action_candidates(population).detach().cpu(),
                    "scores": population_scores.detach().cpu(),
                }
            )
            metrics.eds_iters_executed = i + 1
            if cfg.search_schedule_mode == "adaptive":
                adaptive_previous_best_idx = iter_best_idx
                adaptive_previous_best_reward = iter_best_reward_value
                adaptive_reward_improvement = adaptive_iteration_improvement
                adaptive_diversity_band_state = adaptive_iteration_diversity_state
                adaptive_best_lineage_stable = adaptive_iteration_lineage_stable
                metrics.reward_plateau_count = adaptive_reward_plateau_count
                metrics.stable_lineage_count = adaptive_stable_lineage_count
                if (
                    metrics.eds_iters_executed >= cfg.adaptive_min_cem_iters
                    and metrics.eds_iters_executed < cfg.cem_iters
                    and adaptive_iteration_improvement is not None
                    and abs(adaptive_iteration_improvement)
                    <= float(cfg.adaptive_reward_improvement_eps)
                    and adaptive_reward_plateau_count
                    >= cfg.adaptive_early_stop_patience
                    and adaptive_stable_lineage_count
                    >= cfg.adaptive_early_stop_patience
                    and adaptive_iteration_diversity_state == "in_band"
                ):
                    metrics.early_stop_used = True
                    metrics.early_stop_reason = "adaptive_plateau_stable_in_band"
                    break

        if anchor_lineage_ids is not None:
            surviving_anchor_lineages = anchor_lineage_ids[
                anchor_lineage_ids >= 0
            ].unique()
            metrics.final_unique_anchor_lineage_survival_count = int(
                surviving_anchor_lineages.numel()
            )
            if metrics.initial_anchor_lineage_count > 0:
                metrics.final_unique_anchor_lineage_survival_ratio = float(
                    metrics.final_unique_anchor_lineage_survival_count
                    / metrics.initial_anchor_lineage_count
                )

        metrics.nonfinite_count = int(
            (~torch.isfinite(population)).sum().detach().cpu().item()
        )
        if not torch.isfinite(population).all():
            raise ValueError("EDS-guided RDT latent contains non-finite values")

        best_idx = int(torch.argmin(population_scores).item())
        selected = population[best_idx : best_idx + 1]
        final_rewards = self._eds_rewards_from_info(population_scores, population_info)
        final_reward_spread = final_rewards.max() - final_rewards.mean()
        metrics.final_best_reward = float(final_rewards[best_idx].detach().cpu().item())
        metrics.final_mean_reward = float(final_rewards.mean().detach().cpu().item())
        metrics.reward_spread = float(final_reward_spread.detach().cpu().item())
        metrics.selected_idx = best_idx
        metrics.selected_cost = float(population_scores[best_idx].detach().cpu().item())
        metrics.selected_reward = float(final_rewards[best_idx].detach().cpu().item())
        metrics.selected_chunk_population_source = chunk_population_sources[best_idx]
        metrics.chunk_to_chunk_selected_trajectory_distance = (
            self._eds_chunk_selected_trajectory_distance(
                previous_selected_population,
                selected,
            )
        )
        metrics.population_diversity_final = self._eds_population_diversity(population)
        metrics.target_distance_after = self._eds_target_distance(population, keypoints, best_idx)
        metrics.action_mask_violation_max = max_action_mask_violation
        if parent_mode_coverages:
            metrics.parent_mode_coverage = float(
                sum(parent_mode_coverages) / len(parent_mode_coverages)
            )
            metrics.elite_carryover_count_observed = elite_count_observed
            metrics.anchor_count_observed = anchor_count_observed
            metrics.anchor_unique_ratio = (
                float(sum(anchor_unique_ratios) / len(anchor_unique_ratios))
                if anchor_unique_ratios
                else None
            )
            metrics.anchor_min_pairwise_eef_distance = (
                float(min(anchor_min_pairwise_distances))
                if anchor_min_pairwise_distances
                else None
            )
            metrics.offspring_unique_parent_ratio = (
                float(
                    sum(offspring_unique_parent_ratios)
                    / len(offspring_unique_parent_ratios)
                )
                if offspring_unique_parent_ratios
                else None
            )
            metrics.parent_count_by_source = dict(cumulative_parent_count_by_source)
            metrics.selected_parent_source = last_particle_sources[best_idx]
            if first_elite_population is not None and first_elite_population.shape[0] > 0:
                masked_first_elites = self._apply_action_mask(
                    first_elite_population,
                    cond,
                )
                elite_matches = torch.eq(
                    masked_first_elites[:, None],
                    population[None, :],
                ).reshape(
                    masked_first_elites.shape[0],
                    population.shape[0],
                    -1,
                ).all(dim=2)
                metrics.elite_survival_to_final_count = int(
                    elite_matches.any(dim=1).sum().detach().cpu().item()
                )
        metrics.eds_loop_latency_s = float(time.perf_counter() - loop_start)
        if rollout_diversity_grad_norms:
            metrics.rollout_diversity_grad_norm_mean = float(
                sum(rollout_diversity_grad_norms) / len(rollout_diversity_grad_norms)
            )
            metrics.rollout_diversity_grad_norm_max = float(max(rollout_diversity_grad_norms))
        if adaptive_decision_count > 0:
            metrics.adaptive_rbf_current_mean = (
                float(sum(adaptive_current_values) / len(adaptive_current_values))
                if adaptive_current_values
                else None
            )
            metrics.adaptive_rbf_active_iter_count = adaptive_active_iter_count
            metrics.adaptive_rbf_active_iter_ratio = float(
                adaptive_active_iter_count / adaptive_decision_count
            )
            metrics.adaptive_rbf_band_hit_ratio = float(
                adaptive_band_hit_count / adaptive_decision_count
            )
            metrics.adaptive_rbf_scale_requested_mean = (
                float(
                    sum(adaptive_requested_scales)
                    / len(adaptive_requested_scales)
                )
                if adaptive_requested_scales
                else None
            )
            metrics.adaptive_rbf_scale_applied_mean = float(
                sum(adaptive_applied_scales) / len(adaptive_applied_scales)
            )
        if metrics.per_iter:
            metrics.score_entropy = metrics.per_iter[-1].score_entropy
            metrics.unique_parent_ratio_mean = float(
                sum(item.unique_parent_ratio for item in metrics.per_iter)
                / len(metrics.per_iter)
            )
            selection_metrics = [
                item for item in metrics.per_iter if item.selection_beta is not None
            ]
            if selection_metrics:
                selection_metric_count = len(selection_metrics)
                metrics.selection_beta_mean = float(
                    sum(item.selection_beta for item in selection_metrics)
                    / selection_metric_count
                )
                metrics.selection_ess_mean = float(
                    sum(item.selection_ess for item in selection_metrics)
                    / selection_metric_count
                )
                metrics.selection_ess_ratio_mean = float(
                    sum(item.selection_ess_ratio for item in selection_metrics)
                    / selection_metric_count
                )
                metrics.selection_entropy_normalized_mean = float(
                    sum(
                        item.selection_entropy_normalized
                        for item in selection_metrics
                    )
                    / selection_metric_count
                )
                metrics.selection_max_probability_mean = float(
                    sum(item.selection_max_probability for item in selection_metrics)
                    / selection_metric_count
                )
                metrics.selection_degenerate_reward_count = sum(
                    int(item.selection_degenerate_reward)
                    for item in selection_metrics
                )
        else:
            metrics.score_entropy = self._eds_score_entropy(population_scores, cfg.temperature)

        if cfg.chunk_population_mode == "warm_start_mix":
            self._eds_chunk_memory = EDSChunkMemory(
                population=population.detach().cpu().clone(),
                costs=population_scores.detach().cpu().clone(),
                stage=int(current_stage),
                global_step=int(global_step),
            )
            self._eds_chunk_memory_reset_reason = None

        self._last_eds_metrics = metrics.to_jsonable()
        self._last_eds_artifacts = {
            "initial_actions": initial_action_candidates,
            "final_actions": self._decode_visualization_action_candidates(population).detach().cpu(),
            "final_scores": population_scores.detach().cpu(),
            "selected_idx": best_idx,
            "per_iter": artifact_iters,
        }
        if trace_enabled:
            rollout_diversity_info = {
                key: value
                for key, value in self._last_eds_metrics.items()
                if key.startswith("rollout_diversity_")
                or key.startswith("eef_diversity_")
                or key.startswith("endpoint_spread_after_rollout")
                or key.startswith("endpoint_spread_before_rollout")
            }
            chunk_memory_trace_info = {}
            if cfg.chunk_population_mode == "warm_start_mix":
                chunk_memory_metric_fields = (
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
                    "selected_chunk_population_source",
                    "chunk_to_chunk_selected_trajectory_distance",
                )
                chunk_memory_trace_info = {
                    key: self._last_eds_metrics.get(key)
                    for key in chunk_memory_metric_fields
                }
                chunk_memory_trace_info["enabled"] = bool(
                    chunk_memory_info.get("chunk_memory_candidate_count", 0)
                )
                chunk_memory_trace_info["accepted_positions"] = list(
                    chunk_memory_info.get("_trace_accepted_positions", [])
                )
                chunk_memory_trace_info["particle_sources"] = list(
                    initial_trace_particle_sources or ()
                )
            selection_trace_info = {}
            if selection_trace_iters:
                selection_trace_info = {
                    "enabled": True,
                    "parent_weighting_mode": cfg.parent_weighting_mode,
                    "parent_coverage_mode": cfg.parent_coverage_mode,
                    "per_iter": selection_trace_iters,
                    "parent_count_by_source": dict(
                        metrics.parent_count_by_source
                    ),
                    "anchor_unique_ratio": metrics.anchor_unique_ratio,
                    "anchor_min_pairwise_eef_distance": (
                        metrics.anchor_min_pairwise_eef_distance
                    ),
                    "elite_survival_to_final_count": (
                        metrics.elite_survival_to_final_count
                    ),
                    "initial_anchor_lineage_count": (
                        metrics.initial_anchor_lineage_count
                    ),
                    "final_unique_anchor_lineage_survival_count": (
                        metrics.final_unique_anchor_lineage_survival_count
                    ),
                    "final_unique_anchor_lineage_survival_ratio": (
                        metrics.final_unique_anchor_lineage_survival_ratio
                    ),
                    "selected_parent_source": metrics.selected_parent_source,
                }
            adaptive_rollout_trace_info = {}
            if (
                adaptive_rbf_enabled
                and adaptive_rollout_trace_iters
            ):
                adaptive_rollout_trace_info = {
                    "enabled": True,
                    "rollout_diversity_control_mode": (
                        cfg.rollout_diversity_control_mode
                    ),
                    "per_iter": adaptive_rollout_trace_iters,
                    "fallback_used": metrics.adaptive_rbf_fallback_used,
                    "fallback_reason": metrics.adaptive_rbf_fallback_reason,
                }
            search_schedule_trace_info = {}
            if cfg.search_schedule_mode == "adaptive":
                search_schedule_trace_info = {
                    "enabled": True,
                    "search_schedule_mode": cfg.search_schedule_mode,
                    "eds_iters_executed": metrics.eds_iters_executed,
                    "early_stop_used": metrics.early_stop_used,
                    "early_stop_reason": metrics.early_stop_reason,
                    "reward_plateau_count": metrics.reward_plateau_count,
                    "stable_lineage_count": metrics.stable_lineage_count,
                    "per_iter": [
                        {
                            key: item.get(key)
                            for key in (
                                "iter_idx",
                                "n_trunc_steps",
                                "resolved_renoise_reason",
                                "best_reward",
                                "mean_reward",
                                "population_diversity",
                                "diversity_band_low",
                                "diversity_band_high",
                                "reward_improvement",
                                "diversity_band_state",
                                "best_lineage_stable",
                                "stable_lineage_count",
                            )
                        }
                        for item in self._last_eds_metrics["per_iter"]
                    ],
                }
            self._last_eds_mechanism_trace = EDSMechanismTrace(
                suite=None,
                task_id=None,
                episode=None,
                global_step=int(global_step),
                reward_mode=cfg.reward_mode,
                population_size=cfg.population_size,
                cem_iters=cfg.cem_iters,
                use_cem=cfg.use_cem,
                keypoints=keypoints.detach().cpu() if keypoints is not None else None,
                scoring_keypoint_indices=self._eds_infer_scoring_keypoint_indices(
                    guidance_fns,
                    keypoints,
                ),
                stages=trace_stages,
                selected_idx=best_idx,
                initial_sampler_info=dict(initial_sampler_info),
                rollout_diversity_info=rollout_diversity_info,
                selection_info=selection_trace_info,
                adaptive_rollout_info=adaptive_rollout_trace_info,
                chunk_memory_info=chunk_memory_trace_info,
                search_schedule_info=search_schedule_trace_info,
            )
        else:
            self._last_eds_mechanism_trace = None
        self._eds_update_guidance_metadata_from_cost(
            population_scores[best_idx],
            population_scores,
        )
        ordered_candidates = self._eds_order_candidates_by_cost(population, population_scores)
        self._last_visualization_action_candidates = self._decode_visualization_action_candidates(
            ordered_candidates
        )
        if cfg.save_ed_cache:
            self._save_eds_population_cache(
                population,
                cfg.ed_population_cache,
                label="ed_population",
            )
        return selected

    def _select_particle_for_execution(
        self,
        samples: Tensor,
        *,
        keypoints: Optional[Tensor],
        guidance_fns: Optional[List[Callable]],
        fkd: Optional[FKD],
    ) -> Tensor:
        if samples.shape[0] == 1:
            return samples
        if fkd is not None and fkd.reached_terminal:
            return samples[0:1]
        rewards = self._score_particles(samples, keypoints, guidance_fns, slice_kind="fkd")
        best_idx = int(torch.argmax(rewards).item())
        return samples[best_idx : best_idx + 1]

    def _order_particles_for_visualization(
        self,
        samples: Tensor,
        *,
        keypoints: Optional[Tensor],
        guidance_fns: Optional[List[Callable]],
        fkd: Optional[FKD],
    ) -> Tensor:
        if samples.shape[0] <= 1:
            return samples.detach()
        if fkd is not None and fkd.reached_terminal:
            return samples.detach()

        rewards = self._score_particles(samples, keypoints, guidance_fns, slice_kind="fkd")
        best_idx = int(torch.argmax(rewards).item())
        if best_idx == 0:
            return samples.detach()

        remaining = [idx for idx in range(samples.shape[0]) if idx != best_idx]
        order = torch.tensor([best_idx, *remaining], device=samples.device, dtype=torch.long)
        return samples.index_select(0, order).detach()

    def _decode_visualization_action_candidates(self, actions: Tensor) -> Tensor:
        if actions.ndim != 3 or tuple(actions.shape[1:]) != (64, 128):
            raise ValueError(f"Expected actions with shape (B, 64, 128), got {tuple(actions.shape)}")
        decoded = rdt_action_to_libero_raw(actions[:, : self._action_chunk_horizon, :])
        if not torch.isfinite(decoded).all():
            raise ValueError("Decoded RDT visualization candidates contain non-finite values")
        return decoded.detach()

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
        if self._debug_first_step and not self._action_summary_logged:
            log.info(
                f"[RDT_GT_ACTION] shape={tuple(decoded.shape)} "
                f"min={float(decoded.min().item()):.4f} "
                f"max={float(decoded.max().item()):.4f} "
                f"first_decoded_action={decoded[0, 0].detach().cpu().tolist()}"
            )
            self._action_summary_logged = True
        return decoded

    # ── Trajectory projection (shared by diversity and guidance hooks) ────────

    def _decode_rdt_actions_for_guidance(self, sample: Tensor) -> Tensor:
        if sample.ndim != 3 or sample.shape[1] != 64 or sample.shape[2] != 128:
            raise ValueError(f"Expected RDT sample with shape (B, 64, 128), got {tuple(sample.shape)}")
        H = self._action_chunk_horizon
        return sample[:, :H, RDT_GUIDED_ACTION_INDICES].to(dtype=sample.dtype)

    def _rdt_sample_to_trajectory_3d(self, sample: Tensor) -> Tensor:
        actions = self._decode_rdt_actions_for_guidance(sample)
        B = actions.shape[0]
        if self._adapter is None:
            return torch.zeros(
                B,
                self._action_chunk_horizon + 1,
                3,
                device=sample.device,
                dtype=sample.dtype,
            )

        trajs = []
        for b in range(B):
            traj = self._adapter.delta_actions_to_ee_trajectory(actions[b]).to(device=sample.device, dtype=sample.dtype)
            trajs.append(traj)
        return torch.stack(trajs, dim=0)

    # ── Gradient helpers ──────────────────────────────────────────────────────

    def _mask_guidance_gradient(self, grad: Tensor) -> Tensor:
        masked = torch.zeros_like(grad)
        masked[:, : self._action_chunk_horizon, RDT_GUIDED_TRANSLATION_INDICES] = grad[
            :, : self._action_chunk_horizon, RDT_GUIDED_TRANSLATION_INDICES
        ]
        return masked

    def _apply_keypoint_guidance(self, model_output: Tensor, kp_grad: Tensor, scale: Tensor | float) -> Tensor:
        guided = model_output.clone()
        if not torch.is_tensor(scale):
            scale = torch.tensor(scale, device=model_output.device, dtype=model_output.dtype)
        masked_grad = self._mask_guidance_gradient(kp_grad).to(device=model_output.device, dtype=model_output.dtype)
        guided[:, : self._action_chunk_horizon, RDT_GUIDED_TRANSLATION_INDICES] += (
            RDT_GUIDANCE_SIGN
            * scale
            * masked_grad[:, : self._action_chunk_horizon, RDT_GUIDED_TRANSLATION_INDICES]
        )
        return guided

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
                # Mirrors core/diffusion_policy_steer.py keypoint gradient slice.
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
                if not torch.isfinite(grad).all():
                    log.warning(
                        f"Keypoint gradient contained non-finite values; skipping guidance for reward={reward_scalar:.6f}"
                    )
                    return None, reward_scalar
                g_norm = torch.norm(grad).item()
                normalized = grad / (g_norm + 1e-8) if g_norm > 1e-8 else grad

                if verbose:
                    log.info(f"reward={reward_scalar:.4f}, norm_r={norm_r:.3f}")

                return normalized, reward_scalar
        except Exception as exc:
            log.warning(f"Keypoint gradient failed: {exc}")
            return None, 0.0

    def _normalized_reward_from_value(self, reward_value: float) -> float:
        if self._stage_init_reward is not None and self._stage_init_reward < -1e-6:
            normalized_reward = 1.0 - (reward_value / self._stage_init_reward)
            normalized_reward = max(0.0, min(1.2, normalized_reward))
        else:
            normalized_reward = 0.0
        self._last_normalized_reward = normalized_reward
        return normalized_reward

    def _resolve_start_step(self, timesteps: Tensor, start_ratio: Optional[float]) -> int:
        if start_ratio is None:
            return int(timesteps[len(timesteps) // 3].item())
        idx = int(len(timesteps) * float(start_ratio))
        idx = max(0, min(len(timesteps) - 1, idx))
        return int(timesteps[idx].item())

    def _resolve_eds_config_with_reference_defaults(self, eds_config: Optional[dict]) -> _EDSConfig:
        cfg = dict(eds_config or {})
        cem_iters = int(cfg.get("cem_iters", 20))
        resolved = _EDSConfig(
            population_size=int(cfg.get("population_size", 16)),
            use_cem=_parse_eds_bool(cfg.get("use_cem", False), "use_cem"),
            cem_iters=cem_iters,
            num_elites=int(cfg.get("num_elites", 32)),
            temperature=float(cfg.get("temperature", 0.1)),
            renoise_t_max=int(cfg.get("renoise_t_max", 5)),
            renoise_t_min=int(cfg.get("renoise_t_min", 1)),
            initial_population_cache=cfg.get("initial_population_cache", None),
            ed_population_cache=cfg.get("ed_population_cache", None),
            use_initial_cache=_parse_eds_bool(
                cfg.get("use_initial_cache", False), "use_initial_cache"
            ),
            save_initial_cache=_parse_eds_bool(
                cfg.get("save_initial_cache", False), "save_initial_cache"
            ),
            save_ed_cache=_parse_eds_bool(cfg.get("save_ed_cache", False), "save_ed_cache"),
            reward_mode=str(cfg.get("reward_mode", "normal")),
            shuffle_seed=int(cfg.get("shuffle_seed", 0)),
            mechanism_pretest=cfg.get("mechanism_pretest", None),
            initial_sampling_mode=str(cfg.get("initial_sampling_mode", "iid")),
            initial_diversity_scale=float(cfg.get("initial_diversity_scale", 1.0)),
            initial_diversity_start_ratio=(
                None
                if cfg.get("initial_diversity_start_ratio", None) is None
                else float(cfg.get("initial_diversity_start_ratio"))
            ),
            initial_diversity_fallback=str(cfg.get("initial_diversity_fallback", "iid")),
            initial_cache_metadata=_parse_eds_bool(
                cfg.get("initial_cache_metadata", True), "initial_cache_metadata"
            ),
            truncated_rollout_mode=str(cfg.get("truncated_rollout_mode", "baseline")),
            rollout_diversity_scale=float(cfg.get("rollout_diversity_scale", 1.0)),
            rollout_diversity_start_ratio=float(
                cfg.get("rollout_diversity_start_ratio", 0.8)
            ),
            rollout_diversity_iters=_parse_eds_rollout_diversity_iters(
                cfg.get("rollout_diversity_iters", 0)
            ),
            rollout_diversity_skip_final_steps=int(
                cfg.get("rollout_diversity_skip_final_steps", 0)
            ),
            parent_weighting_mode=str(
                cfg.get("parent_weighting_mode", "legacy_temperature")
            ),
            selection_ess_target_ratio=_parse_eds_float(
                cfg.get("selection_ess_target_ratio", 0.6),
                "selection_ess_target_ratio",
            ),
            selection_beta_max=_parse_eds_float(
                cfg.get("selection_beta_max", 100.0), "selection_beta_max"
            ),
            selection_bisection_steps=_parse_eds_int(
                cfg.get("selection_bisection_steps", 24),
                "selection_bisection_steps",
            ),
            parent_coverage_mode=str(cfg.get("parent_coverage_mode", "none")),
            parent_anchor_count=_parse_eds_int(
                cfg.get("parent_anchor_count", 0), "parent_anchor_count"
            ),
            parent_anchor_reward_quantile=_parse_eds_float(
                cfg.get("parent_anchor_reward_quantile", 0.5),
                "parent_anchor_reward_quantile",
            ),
            elite_carryover_count=_parse_eds_int(
                cfg.get("elite_carryover_count", 0), "elite_carryover_count"
            ),
            rollout_diversity_control_mode=str(
                cfg.get("rollout_diversity_control_mode", "fixed")
            ),
            rollout_diversity_target_ratio=_parse_eds_float(
                cfg.get("rollout_diversity_target_ratio", 1.0),
                "rollout_diversity_target_ratio",
            ),
            rollout_diversity_band_ratio=_parse_eds_float(
                cfg.get("rollout_diversity_band_ratio", 0.2),
                "rollout_diversity_band_ratio",
            ),
            rollout_diversity_scale_min=_parse_eds_float(
                cfg.get("rollout_diversity_scale_min", 0.0),
                "rollout_diversity_scale_min",
            ),
            rollout_diversity_scale_max=_parse_eds_float(
                cfg.get("rollout_diversity_scale_max", 20.0),
                "rollout_diversity_scale_max",
            ),
            rollout_diversity_decay_floor=_parse_eds_float(
                cfg.get("rollout_diversity_decay_floor", 0.25),
                "rollout_diversity_decay_floor",
            ),
            chunk_population_mode=str(cfg.get("chunk_population_mode", "fresh")),
            chunk_memory_fraction=_parse_eds_float(
                cfg.get("chunk_memory_fraction", 0.0), "chunk_memory_fraction"
            ),
            chunk_memory_renoise_steps=_parse_eds_int(
                cfg.get("chunk_memory_renoise_steps", 2),
                "chunk_memory_renoise_steps",
            ),
            chunk_memory_reward_guard_quantile=_parse_eds_float(
                cfg.get("chunk_memory_reward_guard_quantile", 0.25),
                "chunk_memory_reward_guard_quantile",
            ),
            search_schedule_mode=str(
                cfg.get("search_schedule_mode", "legacy_linear")
            ),
            adaptive_min_cem_iters=_parse_eds_int(
                cfg.get("adaptive_min_cem_iters", min(4, cem_iters)),
                "adaptive_min_cem_iters",
            ),
            adaptive_early_stop_patience=_parse_eds_int(
                cfg.get("adaptive_early_stop_patience", 2),
                "adaptive_early_stop_patience",
            ),
            adaptive_reward_improvement_eps=_parse_eds_float(
                cfg.get("adaptive_reward_improvement_eps", 1e-3),
                "adaptive_reward_improvement_eps",
            ),
        )
        if resolved.population_size <= 0:
            raise ValueError("EDS population_size must be positive")
        if resolved.cem_iters <= 0:
            raise ValueError("EDS cem_iters must be positive")
        if not math.isfinite(resolved.temperature) or resolved.temperature <= 0:
            raise ValueError("EDS temperature must be finite and positive")
        if resolved.renoise_t_max <= 0 or resolved.renoise_t_min <= 0:
            raise ValueError("EDS renoise_t_max and renoise_t_min must be positive")
        if resolved.renoise_t_min > resolved.renoise_t_max:
            raise ValueError("EDS renoise_t_min must be <= renoise_t_max")
        if resolved.reward_mode not in {"normal", "zero", "shuffled_keypoints", "inverted"}:
            raise ValueError(
                "EDS reward_mode must be one of normal, zero, shuffled_keypoints, inverted"
            )
        if resolved.initial_sampling_mode not in {"iid", "rbf_diverse_denoise"}:
            raise ValueError(
                "EDS initial_sampling_mode must be one of iid, rbf_diverse_denoise"
            )
        if not math.isfinite(resolved.initial_diversity_scale):
            raise ValueError("EDS initial_diversity_scale must be finite")
        if resolved.initial_diversity_start_ratio is not None:
            ratio = float(resolved.initial_diversity_start_ratio)
            if not math.isfinite(ratio) or ratio < 0.0 or ratio > 1.0:
                raise ValueError(
                    "EDS initial_diversity_start_ratio must be None or a finite value in [0, 1]"
                )
        if resolved.initial_diversity_fallback != "iid":
            raise ValueError("EDS initial_diversity_fallback MVP only supports iid")
        if resolved.truncated_rollout_mode not in EDS_TRUNCATED_ROLLOUT_MODES:
            raise ValueError(
                "EDS truncated_rollout_mode must be one of baseline, rbf_diverse"
            )
        if not math.isfinite(resolved.rollout_diversity_scale):
            raise ValueError("EDS rollout_diversity_scale must be finite")
        rollout_ratio = float(resolved.rollout_diversity_start_ratio)
        if not math.isfinite(rollout_ratio) or rollout_ratio < 0.0 or rollout_ratio > 1.0:
            raise ValueError(
                "EDS rollout_diversity_start_ratio must be a finite value in [0, 1]"
            )
        if resolved.rollout_diversity_skip_final_steps < 0:
            raise ValueError("EDS rollout_diversity_skip_final_steps must be >= 0")
        if resolved.parent_weighting_mode not in {
            "legacy_temperature",
            "adaptive_ess",
        }:
            raise ValueError(
                "EDS parent_weighting_mode must be one of legacy_temperature, adaptive_ess"
            )
        if resolved.parent_coverage_mode not in {"none", "eef_kcenter"}:
            raise ValueError(
                "EDS parent_coverage_mode must be one of none, eef_kcenter"
            )
        if resolved.rollout_diversity_control_mode not in {
            "fixed",
            "adaptive_band",
        }:
            raise ValueError(
                "EDS rollout_diversity_control_mode must be one of fixed, adaptive_band"
            )
        if resolved.chunk_population_mode not in {"fresh", "warm_start_mix"}:
            raise ValueError(
                "EDS chunk_population_mode must be one of fresh, warm_start_mix"
            )
        if resolved.search_schedule_mode not in {"legacy_linear", "adaptive"}:
            raise ValueError(
                "EDS search_schedule_mode must be one of legacy_linear, adaptive"
            )
        if (
            not math.isfinite(resolved.selection_ess_target_ratio)
            or resolved.selection_ess_target_ratio <= 0.0
            or resolved.selection_ess_target_ratio > 1.0
        ):
            raise ValueError("EDS selection_ess_target_ratio must be in (0, 1]")
        if (
            not math.isfinite(resolved.selection_beta_max)
            or resolved.selection_beta_max <= 0.0
        ):
            raise ValueError("EDS selection_beta_max must be finite and positive")
        if resolved.selection_bisection_steps <= 0:
            raise ValueError("EDS selection_bisection_steps must be positive")
        if resolved.parent_anchor_count < 0:
            raise ValueError("EDS parent_anchor_count must be >= 0")
        if (
            not math.isfinite(resolved.parent_anchor_reward_quantile)
            or resolved.parent_anchor_reward_quantile < 0.0
            or resolved.parent_anchor_reward_quantile > 1.0
        ):
            raise ValueError("EDS parent_anchor_reward_quantile must be in [0, 1]")
        if resolved.elite_carryover_count < 0:
            raise ValueError("EDS elite_carryover_count must be >= 0")
        if resolved.elite_carryover_count >= resolved.population_size:
            raise ValueError(
                "EDS elite_carryover_count must be less than population_size"
            )
        if (
            resolved.elite_carryover_count + resolved.parent_anchor_count
            > resolved.population_size
        ):
            raise ValueError(
                "EDS elite_carryover_count + parent_anchor_count must be <= population_size"
            )
        if (
            not math.isfinite(resolved.rollout_diversity_target_ratio)
            or resolved.rollout_diversity_target_ratio < 0.0
        ):
            raise ValueError(
                "EDS rollout_diversity_target_ratio must be finite and >= 0"
            )
        if (
            not math.isfinite(resolved.rollout_diversity_band_ratio)
            or resolved.rollout_diversity_band_ratio < 0.0
        ):
            raise ValueError(
                "EDS rollout_diversity_band_ratio must be finite and >= 0"
            )
        if (
            not math.isfinite(resolved.rollout_diversity_scale_min)
            or resolved.rollout_diversity_scale_min < 0.0
        ):
            raise ValueError(
                "EDS rollout_diversity_scale_min must be finite and nonnegative"
            )
        if (
            not math.isfinite(resolved.rollout_diversity_scale_max)
            or resolved.rollout_diversity_scale_max < 0.0
        ):
            raise ValueError(
                "EDS rollout_diversity_scale_max must be finite and nonnegative"
            )
        if resolved.rollout_diversity_scale_min > resolved.rollout_diversity_scale_max:
            raise ValueError(
                "EDS rollout_diversity_scale_min must be <= rollout_diversity_scale_max"
            )
        if (
            not math.isfinite(resolved.rollout_diversity_decay_floor)
            or resolved.rollout_diversity_decay_floor < 0.0
            or resolved.rollout_diversity_decay_floor > 1.0
        ):
            raise ValueError("EDS rollout_diversity_decay_floor must be in [0, 1]")
        if (
            not math.isfinite(resolved.chunk_memory_fraction)
            or resolved.chunk_memory_fraction < 0.0
            or resolved.chunk_memory_fraction >= 1.0
        ):
            raise ValueError("EDS chunk_memory_fraction must be in [0, 1)")
        if resolved.chunk_memory_renoise_steps <= 0:
            raise ValueError("EDS chunk_memory_renoise_steps must be positive")
        if (
            not math.isfinite(resolved.chunk_memory_reward_guard_quantile)
            or resolved.chunk_memory_reward_guard_quantile < 0.0
            or resolved.chunk_memory_reward_guard_quantile > 1.0
        ):
            raise ValueError(
                "EDS chunk_memory_reward_guard_quantile must be in [0, 1]"
            )
        if not 1 <= resolved.adaptive_min_cem_iters <= resolved.cem_iters:
            raise ValueError(
                "EDS adaptive_min_cem_iters must be in [1, cem_iters]"
            )
        if resolved.adaptive_early_stop_patience <= 0:
            raise ValueError("EDS adaptive_early_stop_patience must be positive")
        if (
            not math.isfinite(resolved.adaptive_reward_improvement_eps)
            or resolved.adaptive_reward_improvement_eps < 0.0
        ):
            raise ValueError(
                "EDS adaptive_reward_improvement_eps must be finite and >= 0"
            )
        if resolved.use_cem and resolved.num_elites > resolved.population_size:
            raise ValueError(
                "EDS num_elites must be <= population_size when use_cem=true"
            )
        if resolved.use_cem and resolved.num_elites <= 0:
            raise ValueError("EDS num_elites must be positive when use_cem=true")
        return resolved

    def _adaptive_scale_for_scheduler_t(
        self,
        scheduler,
        t: Tensor,
        guide_scale: float,
        sigmoid_k: float,
        sigmoid_x0: float,
        device: torch.device,
        dtype: torch.dtype,
    ) -> Tensor:
        strength = 1.0 / (1.0 + math.exp(sigmoid_k * (self._last_normalized_reward - sigmoid_x0)))
        if hasattr(scheduler, "alphas_cumprod"):
            alpha_t = scheduler.alphas_cumprod[int(t.item())].to(device=device, dtype=dtype)
        else:
            alpha_t = torch.tensor(self._current_alpha_t, device=device, dtype=dtype)
        scale = torch.tensor(float(guide_scale) * strength, device=device, dtype=dtype) * torch.sqrt(
            torch.clamp(1.0 - alpha_t, min=0.0)
        )
        self._last_scale = float(scale.detach().cpu().item())
        return scale

    def _adaptive_scale(
        self, reward: float, guide_scale: float, sigmoid_k: float, sigmoid_x0: float
    ) -> float:
        """Sigmoid-gated guidance strength * sqrt(1-alpha_t) scaling."""
        strength = 1.0 / (1.0 + math.exp(sigmoid_k * (self._last_normalized_reward - sigmoid_x0)))
        alpha_t = self._current_alpha_t
        scale = guide_scale * strength * math.sqrt(max(0.0, 1.0 - float(alpha_t)))
        self._last_scale = scale
        return scale
