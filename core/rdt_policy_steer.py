"""
RDTSteer — wraps RoboticDiffusionTransformerModel with the VLS steering interface.

Duck-typed to match DiffusionPolicySteer / PI05PolicySteer:
  post_init(), select_action(), reset(), reset_stage(),
  get_normalized_reward(), get_last_scale(), _action_chunk_horizon, name
"""
from __future__ import annotations

import math
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import torch
from torch import Tensor, nn

from core.env_adapters import BaseEnvAdapter
from core.fkd_class import FKD
from core.rdt_obs_processor import RDTObsProcessor
from utils.logging_utils import SteerLogger

log = SteerLogger("RDTSteer")

# ManiSkill checkpoint: right-arm occupies dims [7:14] of the 14D unified action.
_RIGHT_ARM = slice(7, 14)


class RDTSteer:
    """RDT-1B with VLS steering: RBF diversity + keypoint gradient + FKD resampling."""

    name = "rdt_steer"

    def __init__(self, rdt_model, num_inference_steps: int = 55) -> None:
        self._rdt_model = rdt_model
        self._num_inference_steps = num_inference_steps

        self._adapter: Optional[BaseEnvAdapter] = None
        self._obs_processor: Optional[RDTObsProcessor] = None
        self._sample_batch_size: int = 1
        self._action_chunk_horizon: int = 8
        self._lang_embed_cache_dir: str = "data/rdt_lang_embeds/"

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
        # Real RoboticDiffusionTransformerModel: .policy = RDTRunner, .policy.model = RDT DiT
        policy = getattr(model, "policy", None)
        if policy is not None and isinstance(policy, nn.Module):
            inner = getattr(policy, "model", None)
            if isinstance(inner, nn.Module):
                return inner
        # Stub model or flat structure: probe common names
        for attr in ("dit", "model", "net", "backbone", "denoiser"):
            candidate = getattr(model, attr, None)
            if isinstance(candidate, nn.Module):
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
    def from_pretrained(cls, pretrained_path: str, num_inference_steps: int = 55) -> "RDTSteer":
        """Load from a HuggingFace Hub repo ID or a local directory path."""
        rdt_root = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "third_party", "rdt",
        )
        if rdt_root not in sys.path:
            sys.path.insert(0, rdt_root)

        if not os.path.isdir(pretrained_path):
            from huggingface_hub import snapshot_download
            log.info(f"Downloading checkpoint: {pretrained_path}")
            pretrained_path = snapshot_download(repo_id=pretrained_path)

        log.info(f"Loading RDT model from: {pretrained_path}")

        try:
            from scripts.agilex_model import RoboticDiffusionTransformerModel
        except ImportError:
            raise ImportError(
                "Cannot import RoboticDiffusionTransformerModel. "
                "Ensure third_party/rdt/ is initialized: git submodule update --init"
            )

        rdt_model = RoboticDiffusionTransformerModel.from_pretrained(pretrained_path)
        instance = cls(rdt_model, num_inference_steps=num_inference_steps)

        # Load precomputed T5-XXL embeddings shipped with checkpoint
        lang_dir = Path(pretrained_path) / "lang_embeds"
        if lang_dir.exists():
            obs_proc = RDTObsProcessor(lang_embed_cache_dir=str(lang_dir))
            obs_proc.load_embedded_tasks(str(lang_dir))
            instance._obs_processor = obs_proc
            log.info(f"Loaded {len(obs_proc._lang_cache)} precomputed lang embeds")

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
        self._lang_embed_cache_dir = policy_config.get(
            "lang_embed_cache_dir", "data/rdt_lang_embeds/"
        )
        if self._obs_processor is None:
            self._obs_processor = RDTObsProcessor(
                lang_embed_cache_dir=self._lang_embed_cache_dir
            )

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
            images, proprio, task_str = self._obs_processor.process(batch)
            text_embed = self._obs_processor.get_lang_embed(task_str, self.device)
            B = self._sample_batch_size

            if use_guidance:
                raw = self._guided_denoise_loop(
                    proprio=proprio,
                    images=images,
                    text_embeds=text_embed,
                    B=B,
                    guidance_fns=guidance_fns,
                    keypoints=keypoints,
                    guide_scale=guide_scale,
                    start_ratio=start_ratio,
                    use_diversity=use_diversity,
                    diversity_scale=diversity_scale,
                    use_fkd=use_fkd,
                    fkd_config=fkd_config,
                    sigmoid_k=sigmoid_k,
                    sigmoid_x0=sigmoid_x0,
                    verbose=verbose,
                )
            else:
                raw = self._predict_unguided(proprio, images, text_embed, B)

            self._cached_action_chunk = self._postprocess_actions(raw)

        return self._cached_action_chunk

    # ── Unguided path ─────────────────────────────────────────────────────────

    def _predict_unguided(
        self,
        proprio: np.ndarray,
        images: list,
        text_embed: Tensor,
        B: int,
    ) -> Tensor:
        """
        Call RDT's step() B times, returning (B, 64, 14).
        """
        results = []
        with torch.no_grad():
            for _ in range(B):
                out = self._rdt_model.step(
                    proprio=proprio,
                    images=images,
                    text_embeds=text_embed,
                )
                if out.dim() == 2:
                    out = out.unsqueeze(0)  # ensure (1, 64, 14)
                results.append(out)
        return torch.cat(results, dim=0)  # (B, 64, 14)

    # ── Action postprocessing ─────────────────────────────────────────────────

    def _postprocess_actions(self, actions: Tensor) -> Tensor:
        """
        (B, 64, 14) → (action_chunk_horizon, 7)
        Slices right-arm, takes first H steps, uses particle 0.
        """
        right_arm = actions[:, :, _RIGHT_ARM]  # (B, 64, 7)
        best = right_arm[0]                    # (64, 7) — particle 0
        return best[: self._action_chunk_horizon]  # (H, 7)

    # ── Placeholder for Task 4 methods (added in next task) ──────────────────

    def _guided_denoise_loop(self, proprio, images, text_embeds, B, **kwargs) -> Tensor:
        """Placeholder — will be fully implemented in Task 4."""
        return self._predict_unguided(proprio, images, text_embeds, B)
