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

# ManiSkill checkpoint outputs 8 DOF (7 right-arm joints + 1 gripper).
_ARM_JOINTS = slice(0, 7)


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
    (e.g. 14D for the ManiSkill two-arm setup).  The real RDT DiT operates in
    the 128D unified action space.  This adapter handles the lift (14→128) and
    projection (128→14) transparently:

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

        # ── Inflate raw x_t (B, H, raw_dim) → unified (B, H, unified_dim) ───
        H = x_t.shape[1]
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

        # ── Project back to raw action dim ────────────────────────────────────
        model_output = model_output_128[:, :, action_indices][:, :, :raw_action_dim]
        return model_output


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
    def encode_inputs(self, proprio, images, text_embeds: Tensor) -> dict:
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

        # ── Proprioception encoding ───────────────────────────────────────────
        joints = proprio.to(device).unsqueeze(0)          # (1, 1, 8)
        states, state_elem_mask = real._format_joint_to_state(joints)
        states = states.to(device, dtype=dtype)
        state_elem_mask = state_elem_mask.to(device, dtype=dtype)
        states = states[:, -1:, :]                        # (1, 1, 128)
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

        # Recover which unified-action indices this model uses so the DiT
        # adapter can inflate raw-action x_t to the full unified space.
        unified_action_dim: int = real.args["model"]["state_token_dim"]
        # action_indices are the positions in the unified vector that correspond
        # to the raw robot joints.  They are stored on the real model as the
        # attribute built during _format_joint_to_state/_unformat_action_to_joint.
        # We derive them from state_elem_mask (1 where the joint is present).
        action_indices: list = state_elem_mask[0].nonzero(as_tuple=True)[0].tolist()

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
    def from_pretrained(
        cls,
        pretrained_path: str,
        num_inference_steps: int = 55,
        vision_encoder: str = "google/siglip-so400m-patch14-384",
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
            from scripts.maniskill_model import (
                RoboticDiffusionTransformerModel,
                create_model,
            )
        except ImportError:
            raise ImportError(
                "Cannot import RoboticDiffusionTransformerModel. "
                "Ensure third_party/rdt/ is initialized: git submodule update --init"
            )

        # Weights are in a `rdt/` subdirectory of the HF snapshot; check both
        # the repo root and the subfolder so local paths still work.
        rdt_subdir = os.path.join(pretrained_path, "rdt")
        search_dirs = [rdt_subdir, pretrained_path] if os.path.isdir(rdt_subdir) else [pretrained_path]

        # Load the model config that ships with the checkpoint
        config_path = None
        for d in search_dirs:
            candidate = os.path.join(d, "config.yaml")
            if os.path.exists(candidate):
                config_path = candidate
                break
        if config_path is None:
            # Fall back to the bundled base config inside the submodule
            config_path = os.path.join(rdt_root, "configs", "base.yaml")
        with open(config_path, "r") as f:
            args = yaml.safe_load(f)

        # Locate the weight file (prefer .safetensors, fall back to .pt/.bin)
        weight_file = None
        weight_names = (
            "model.safetensors",
            "pytorch_model.bin",
            "rdt-1b.pt",
            "mp_rank_00_model_states.pt",  # DeepSpeed checkpoint format
        )
        for search_root in (pretrained_path, os.path.join(pretrained_path, "rdt")):
            if not os.path.isdir(search_root):
                continue
            for fname in weight_names:
                candidate = os.path.join(search_root, fname)
                if os.path.exists(candidate):
                    weight_file = candidate
                    break
            if weight_file is not None:
                break
        # Walk one additional level for nested checkpoints
        if weight_file is None and os.path.isdir(pretrained_path):
            for entry in os.scandir(pretrained_path):
                if entry.is_dir():
                    for fname in weight_names:
                        candidate = os.path.join(entry.path, fname)
                        if os.path.exists(candidate):
                            weight_file = candidate
                            break
                if weight_file is not None:
                    break
        if weight_file is None:
            raise FileNotFoundError(
                f"No weight file found under {pretrained_path}. "
                f"Looked for: {weight_names}. "
                f"Run: ls -R {pretrained_path}"
            )
        log.info(f"Using weight file: {weight_file}")
        print(f"[FIX2] weight_file = {weight_file}")

        # ── DIAGNOSTIC: verify weight loading ────────────────────────────────
        print(f"[DIAG] weight_file resolved to: {weight_file}")
        print(f"[DIAG] config_path resolved to: {config_path}")
        # ─────────────────────────────────────────────────────────────────────

        # ``create_model`` constructs RoboticDiffusionTransformerModel and
        # calls load_pretrained_weights when pretrained is not None.
        # Force local-cache-only for the sub-model loads (T5, SigLIP) — both
        # are already cached and HF_ENDPOINT may point to a mirror with SSL issues.
        _prev_offline = os.environ.get("HF_HUB_OFFLINE")
        os.environ["HF_HUB_OFFLINE"] = "1"
        try:
            real_model = create_model(
                args,
                pretrained=weight_file,
                pretrained_text_encoder_name_or_path="google/t5-v1_1-xxl",
                pretrained_vision_encoder_name_or_path=vision_encoder,
            )
        finally:
            if _prev_offline is None:
                os.environ.pop("HF_HUB_OFFLINE", None)
            else:
                os.environ["HF_HUB_OFFLINE"] = _prev_offline

        # Wrap in the adapter that provides encode_inputs + nn.Module interface.
        rdt_model = _RDTModelAdapter(real_model)

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
        # Wire adapter for direct joint-angle proprio (Task 4 fix).
        self._obs_processor._adapter = self._adapter
        # Reuse the T5 already loaded inside the RDT model to avoid a second T5 load.
        # _RDTModelAdapter wraps the real model; real.encode_instruction uses real.text_model.
        try:
            real = object.__getattribute__(self._rdt_model, "_real")
            if callable(getattr(real, "encode_instruction", None)):
                # Use the device the text_model is already on; "cpu" causes a device
                # mismatch because real.text_model is moved to CUDA during reset().
                _enc_device = str(real.device)
                def _enc_fn(s, _d=_enc_device):
                    emb = real.encode_instruction(s, device=_d)
                    return emb.float().cpu()
                self._obs_processor._text_encoder_fn = _enc_fn
                log.info("Language encoder: reusing RDT model's T5")
                print("[FIX3] T5 wired via real.encode_instruction")
            else:
                log.warning("encode_instruction not found on real model — will lazy-load T5")
                print("[FIX3] WARNING: encode_instruction missing, falling back to lazy T5 load")
        except Exception as exc:
            log.warning(f"T5 wiring failed ({exc}), falling back to lazy T5 load")
            print(f"[FIX3] WARNING: T5 wiring failed: {exc}")

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
            # ── DIAGNOSTIC ───────────────────────────────────────────────────
            if isinstance(proprio, torch.Tensor):
                _p = proprio.detach().cpu().float().numpy().ravel()
            else:
                _p = proprio.ravel()
            print(f"[DIAG] proprio raw (first 8): {_p[:8].tolist()}")
            print(f"[DIAG] lang_embed norm: {text_embed.float().norm().item():.4f}")
            # ─────────────────────────────────────────────────────────────────
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
        # step() applies _unformat_action_to_joint → ManiSkill joint angles.
        # Re-normalize back to [-1, 1] so both guided and unguided paths match.
        # Fallback for stub models that have no action_min/action_max.
        a_min = getattr(self._rdt_model, "action_min", None)
        a_max = getattr(self._rdt_model, "action_max", None)
        results = []
        with torch.no_grad():
            for _ in range(B):
                out = self._rdt_model.step(
                    proprio=proprio,
                    images=images,
                    text_embeds=text_embed,
                )
                if out.dim() == 2:
                    out = out.unsqueeze(0)  # ensure (1, pred_horizon, 8)
                if a_min is not None and a_max is not None:
                    out = (out - a_min) / (a_max - a_min) * 2 - 1
                results.append(out)
        return torch.cat(results, dim=0)  # (B, 64, 8)

    # ── Action postprocessing ─────────────────────────────────────────────────

    def _postprocess_actions(self, actions: Tensor) -> Tensor:
        """
        (B, 64, 8) → (action_chunk_horizon, 7)
        Slices arm joints (0:7), takes first H steps, uses particle 0.
        """
        print(f"[DIAG] actions pre-slice stats: min={actions.float().min().item():.3f}  max={actions.float().max().item():.3f}  mean={actions.float().mean().item():.3f}")
        arm_joints = actions[:, :, _ARM_JOINTS]  # (B, 64, 7)
        best = arm_joints[0]                      # (64, 7) — particle 0
        return best[: self._action_chunk_horizon].unsqueeze(0).float()  # (1, H, 7)

    # ── Trajectory projection (shared by diversity and guidance hooks) ────────

    def _rdt_sample_to_trajectory_3d(self, sample: Tensor) -> Tensor:
        """
        (1, 64, 14) → (1, H+1, 3) via adapter.delta_actions_to_ee_trajectory.
        Slices right-arm, takes action_chunk_horizon steps, projects to 3D EEF.
        """
        action_seq = sample[0, : self._action_chunk_horizon, _ARM_JOINTS]  # (H, 7)
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

        # Stub models return {} from encode_inputs — fall back to 14 (the stub step() shape)
        if "action_indices" in cond:
            raw_action_dim = len(cond["action_indices"])
        else:
            _probe = self._rdt_model.step(proprio=proprio, images=images, text_embeds=text_embeds)
            raw_action_dim = _probe.shape[-1]
        x_t = torch.randn(B, 64, raw_action_dim, device=device, dtype=dtype)

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

        return x_t  # (B, 64, 14)
