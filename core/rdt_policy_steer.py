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

    # ── Trajectory projection (shared by diversity and guidance hooks) ────────

    def _rdt_sample_to_trajectory_3d(self, sample: Tensor) -> Tensor:
        """
        (1, 64, 14) → (1, H+1, 3) via adapter.delta_actions_to_ee_trajectory.
        Slices right-arm, takes action_chunk_horizon steps, projects to 3D EEF.
        """
        action_seq = sample[0, : self._action_chunk_horizon, _RIGHT_ARM]  # (H, 7)
        traj = self._adapter.delta_actions_to_ee_trajectory(action_seq)   # (H+1, 3)
        return traj.unsqueeze(0)  # (1, H+1, 3)

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

        x_t = torch.randn(B, 64, 14, device=device, dtype=dtype)

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
                    noise_pred[:, :, 7:10] = noise_pred[:, :, 7:10] + diversity_scale * div_grad[:, :, 7:10]

            # ── HOOK A: Keypoint gradient guidance (late phase: t ≤ start_t) ──
            elif guidance_fns and keypoints_tensor is not None and t_val <= start_t:
                kp_grad, reward_val = self._compute_keypoint_gradient(
                    x_t, keypoints_tensor, guidance_fns, verbose=verbose
                )
                if kp_grad is not None:
                    scale = self._adaptive_scale(reward_val, guide_scale, sigmoid_k, sigmoid_x0)
                    noise_pred = noise_pred.clone()
                    noise_pred[:, : self._action_chunk_horizon, 7:10] = (
                        noise_pred[:, : self._action_chunk_horizon, 7:10]
                        - scale * kp_grad[:, : self._action_chunk_horizon, 7:10]
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

        return x_t  # (B, 64, 14)
