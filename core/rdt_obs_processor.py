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
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
from PIL import Image

RDT_IMG_SIZE = 384
_BLACK_PIL = Image.fromarray(np.zeros((RDT_IMG_SIZE, RDT_IMG_SIZE, 3), dtype=np.uint8))

_STATIC_KEY = "observation.images.image"
_WRIST_KEY = "observation.images.image2"
_STATE_KEY = "observation.state"


class RDTObsProcessor:
    """Converts the adapter's obs dict into (images, proprio, task_str) for RDT."""

    def __init__(self, lang_embed_cache_dir: str = "data/rdt_lang_embeds/"):
        self._cache_dir = Path(lang_embed_cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._lang_cache: Dict[str, torch.Tensor] = {}
        # One-frame ring buffer for history slots
        self._prev_static: Optional[Image.Image] = None
        self._prev_wrist: Optional[Image.Image] = None

    def reset(self) -> None:
        """Call at episode start to clear the frame history buffer."""
        self._prev_static = None
        self._prev_wrist = None

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
        Priority: (1) preloaded cache, (2) lazy T5-XXL compute+persist, (3) zero fallback.
        """
        key = hashlib.md5(task_str.encode()).hexdigest()
        if key not in self._lang_cache:
            try:
                embed = self._compute_t5_embed(task_str)
                self._lang_cache[key] = embed
                torch.save(embed, self._cache_dir / f"{key}.pt")
            except Exception:
                import logging
                logging.getLogger("RDTObsProcessor").warning(
                    "T5-XXL unavailable — using zero embedding for: %r", task_str
                )
                # Shape matches T5-v1_1-xxl last_hidden_state: (1, seq_len, 512)
                self._lang_cache[key] = torch.zeros(1, 1, 512)
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
        wrist_t = obs[_WRIST_KEY][0]     # (3, H, W)

        ext_now = self._tensor_to_pil(static_t)
        rw_now = self._tensor_to_pil(wrist_t)

        # History: duplicate current frame on first step
        ext_prev = self._prev_static if self._prev_static is not None else ext_now
        rw_prev = self._prev_wrist if self._prev_wrist is not None else rw_now

        # Update ring buffer
        self._prev_static = ext_now
        self._prev_wrist = rw_now

        # RDT slot order: [ext_{t-1}, rw_{t-1}, lw_{t-1}, ext_t, rw_t, lw_t]
        images = [ext_prev, rw_prev, _BLACK_PIL, ext_now, rw_now, _BLACK_PIL]

        # ── Proprio (14D bimanual, right-arm = env state[:7]) ───────────────
        state = obs[_STATE_KEY][0].detach().cpu().numpy()  # (state_dim,)
        proprio = np.zeros(14, dtype=np.float32)
        arm_dims = min(7, state.shape[0])
        proprio[7: 7 + arm_dims] = state[:arm_dims]

        # ── Task string ──────────────────────────────────────────────────────
        task_list = obs.get("task", [""])
        task_str = task_list[0] if isinstance(task_list, (list, tuple)) else str(task_list)

        return images, proprio, task_str
