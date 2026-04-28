"""
RDTObsProcessor — converts adapter obs dict to RDT model inputs.

Expected obs dict keys (both LIBERO and CALVIN after env_preprocessor):
  observation.images.image  : (B, 3, H, W) float [0,1]  static/agentview
  observation.images.image2 : (B, 3, H, W) float [0,1]  wrist camera
  observation.state         : (B, state_dim) float
  task                      : List[str]
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import torch
from PIL import Image

RDT_IMG_SIZE = 384
_BLACK_PIL = Image.fromarray(np.zeros((RDT_IMG_SIZE, RDT_IMG_SIZE, 3), dtype=np.uint8))

_STATIC_KEY = "observation.images.image"
_WRIST_KEY = "observation.images.image2"
_STATE_KEY = "observation.state"
_JOINT_POS_KEY = "observation.joint_pos"
_GRIPPER_QPOS_KEY = "observation.gripper_qpos"


class RDTObsProcessor:
    """Converts the adapter's obs dict into (images, proprio, task_str) for RDT."""

    def __init__(self, lang_embed_cache_dir: str = "data/rdt_lang_embeds/"):
        self._cache_dir = Path(lang_embed_cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._lang_cache: Dict[str, torch.Tensor] = {}
        # One-frame ring buffer for exterior camera history (wrist slots are always None)
        self._prev_static: Optional[Image.Image] = None
        # Optional: callable(task_str) -> Tensor(1, seq_len, hidden_dim), avoids re-loading T5
        self._text_encoder_fn: Optional[Callable[[str], torch.Tensor]] = None
        # Optional env adapter for direct joint-angle access (bypasses EEF-pose obs.state).
        self._adapter = None

    def reset(self) -> None:
        """Call at episode start to clear the frame history buffer."""
        self._prev_static = None

    @staticmethod
    def _build_image_list(
        ext_prev: "Image.Image",
        ext_now: "Image.Image",
    ) -> list:
        """
        Build the 6-image list for RDT inference.

        Slot order: [ext_{t-1}, right_wrist_{t-1}, left_wrist_{t-1},
                     ext_t,     right_wrist_t,      left_wrist_t]

        The ManiSkill checkpoint was trained with cam_high only; wrist slots
        were always empty (np.zeros(..., 0, 0, 0)) during training.  Passing
        None causes maniskill_model.step() to substitute the SigLIP background
        image — the correct in-distribution input for this checkpoint.
        """
        return [ext_prev, None, None, ext_now, None, None]

    def load_embedded_tasks(self, embed_dir: str) -> None:
        """
        Load precomputed T5-XXL embeddings from the checkpoint's lang_embeds/ dir.
        Files are named <task_key>.pt where task_key is the md5 of the task string,
        or any arbitrary stem — we load all .pt files keyed by stem.
        """
        for pt_file in Path(embed_dir).glob("*.pt"):
            self._lang_cache[pt_file.stem] = torch.load(
                pt_file, map_location="cpu", weights_only=True
            )

    def get_lang_embed(self, task_str: str, device: torch.device) -> torch.Tensor:
        """
        Return a T5-XXL embedding tensor for task_str.
        Priority: (1) preloaded cache, (2) _text_encoder_fn (reuses loaded T5), (3) fresh T5 load, (4) zero fallback.
        """
        key = hashlib.md5(task_str.encode()).hexdigest()
        if key not in self._lang_cache:
            try:
                if self._text_encoder_fn is not None:
                    embed = self._text_encoder_fn(task_str).cpu()
                else:
                    embed = self._compute_t5_embed(task_str)
                self._lang_cache[key] = embed
                torch.save(embed, self._cache_dir / f"{key}.pt")
            except Exception:
                import logging
                logging.getLogger("RDTObsProcessor").warning(
                    "T5-XXL unavailable — using zero embedding for: %r", task_str
                )
                # T5-v1_1-xxl d_model=4096; wrong dim here causes mat-mul mismatch
                self._lang_cache[key] = torch.zeros(1, 1, 4096)
        return self._lang_cache[key].to(device)

    @staticmethod
    def _compute_t5_embed(task_str: str) -> torch.Tensor:
        from transformers import T5EncoderModel, T5Tokenizer

        tokenizer = T5Tokenizer.from_pretrained("google/t5-v1_1-xxl")
        model = T5EncoderModel.from_pretrained("google/t5-v1_1-xxl")
        model.eval()
        tokens = tokenizer(task_str, return_tensors="pt", padding=True, truncation=True)
        with torch.no_grad():
            embed = model(**tokens).last_hidden_state  # (1, seq_len, 512)
        return embed.cpu()

    @staticmethod
    def _tensor_to_pil(img: torch.Tensor) -> Image.Image:
        """(C, H, W) float [0,1] → PIL Image resized to RDT_IMG_SIZE."""
        arr = (img.detach().cpu().clamp(0.0, 1.0) * 255).byte().permute(1, 2, 0).numpy()
        return Image.fromarray(arr).resize((RDT_IMG_SIZE, RDT_IMG_SIZE), Image.BILINEAR)

    def process(self, obs: dict) -> Tuple[List[Image.Image], np.ndarray, str]:
        """
        Convert adapter obs dict → RDT input tuple.

        Returns
        -------
        images : list of 6 PIL images
            [ext_{t-1}, right_wrist_{t-1}, left_wrist_{t-1},
             ext_t,     right_wrist_t,     left_wrist_t]
        proprio : np.ndarray shape (14,)
            Bimanual state: left-arm zeros, right-arm = env_state[:7]
        task_str : str
            Instruction string (first element of batch)
        """
        # ── Images ──────────────────────────────────────────────────────────
        # obs tensors are (B, C, H, W) — take batch index 0
        static_t = obs[_STATIC_KEY][0]   # (3, H, W)

        ext_now = self._tensor_to_pil(static_t)

        # History: duplicate current frame on first step
        ext_prev = self._prev_static if self._prev_static is not None else ext_now

        # Update ring buffer (exterior only — wrist slots are always None)
        self._prev_static = ext_now

        images = self._build_image_list(ext_prev, ext_now)
        print(f"[FIX4.5] image slots: {[type(img).__name__ if img is not None else 'None' for img in images]}")

        # ── Proprio (8D: 7 arm joints + 1 gripper) ──────────────────────────
        # Use adapter's direct joint accessors when available (LIBERO/CALVIN),
        # which give actual Franka joint angles that match RDT's training space.
        # Fall back to observation.state when no adapter is wired.
        if self._adapter is not None and hasattr(self._adapter, 'get_joint_positions'):
            try:
                joint_pos = self._adapter.get_joint_positions()  # (7,) Franka joints, radians
                gripper_raw = self._adapter.get_gripper_state()  # sum of 2 finger qpos ≈ [0, 0.08]
                # RDT DATA_STAT gripper range: [0.0, 0.04] (per-finger width).
                # get_gripper_state() returns sum of two fingers → divide by 2.
                gripper_val = float(gripper_raw) / 2.0
                proprio_np = np.zeros(8, dtype=np.float32)
                proprio_np[:7] = joint_pos[:7].astype(np.float32)
                proprio_np[7] = np.clip(gripper_val, 0.0, 0.04)
                print(f"[FIX4] proprio joints (first 4): {proprio_np[:4].tolist()}")
            except Exception as exc:
                print(f"[FIX4] WARNING: adapter joint read failed ({exc}), using obs.state fallback")
                proprio_np = self._fallback_proprio_from_state(obs)
        else:
            proprio_np = self._fallback_proprio_from_state(obs)

        # Return (1, 8) tensor — step() / encode_inputs() do unsqueeze(0) → (1, 1, 8)
        proprio = torch.from_numpy(proprio_np).unsqueeze(0)

        # ── Task string ──────────────────────────────────────────────────────
        task_list = obs.get("task", [""])
        task_str = task_list[0] if isinstance(task_list, (list, tuple)) else str(task_list)

        return images, proprio, task_str

    def _fallback_proprio_from_state(self, obs: dict) -> np.ndarray:
        """Use observation.state when no adapter is available (legacy path)."""
        state_raw = obs[_STATE_KEY][0]
        if isinstance(state_raw, torch.Tensor):
            state = state_raw.detach().cpu().numpy()
        else:
            state = np.asarray(state_raw, dtype=np.float32)
        proprio_np = np.zeros(8, dtype=np.float32)
        arm_dims = min(7, state.shape[0])
        proprio_np[:arm_dims] = state[:arm_dims]
        if state.shape[0] >= 8:
            proprio_np[7] = state[7]
        return proprio_np
