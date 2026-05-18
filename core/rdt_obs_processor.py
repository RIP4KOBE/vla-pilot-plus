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
        # Exterior camera history (wrist slots are always None for ManiSkill RDT).
        self._prev_static: Optional[Image.Image] = None
        self._current_static: Optional[Image.Image] = None
        # Optional: callable(task_str) -> Tensor(1, seq_len, hidden_dim), avoids re-loading T5
        self._text_encoder_fn: Optional[Callable[[str], torch.Tensor]] = None
        # Optional env adapter for direct joint-angle access (bypasses EEF-pose obs.state).
        self._adapter = None
        # LiberoProcessorStep._process_observation applies torch.flip(dims=[2,3]) to all frames
        # before they reach this processor. Set True for LIBERO to undo the 180° rotation so
        # images arrive right-side-up at the ManiSkill SigLIP encoder.
        self._undo_libero_flip: bool = False
        self._gripper_branch_probe_seen: set[str] = set()

    def reset(self) -> None:
        """Call at episode start to clear the frame history buffer."""
        self._prev_static = None
        self._current_static = None

    def update_image_history(self, obs: dict) -> None:
        """Advance the exterior camera history using the latest policy observation."""
        static_t = obs[_STATIC_KEY][0]   # (3, H, W)
        ext_now = self._tensor_to_pil(static_t)
        self._prev_static = self._current_static
        self._current_static = ext_now

    @staticmethod
    def _build_image_list(
        ext_prev: Optional["Image.Image"],
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
        import logging

        key = hashlib.md5(task_str.encode()).hexdigest()
        branch = "cache_hit" if key in self._lang_cache else None
        if key not in self._lang_cache:
            try:
                if self._text_encoder_fn is not None:
                    branch = "text_encoder_fn"
                    embed = self._text_encoder_fn(task_str).cpu()
                else:
                    branch = "fresh_t5"
                    embed = self._compute_t5_embed(task_str)
                self._lang_cache[key] = embed
                torch.save(embed, self._cache_dir / f"{key}.pt")
            except Exception:
                branch = "zero_fallback"
                logging.getLogger("RDTObsProcessor").warning(
                    "T5-XXL unavailable — using zero embedding for: %r", task_str
                )
                # T5-v1_1-xxl d_model=4096; wrong dim here causes mat-mul mismatch
                self._lang_cache[key] = torch.zeros(1, 1, 4096)
        embed = self._lang_cache[key]
        if not hasattr(self, "_lang_branch_probe_seen"):
            self._lang_branch_probe_seen = set()
        if key not in self._lang_branch_probe_seen:
            logging.getLogger("RDTObsProcessor").warning(
                "[LANG_BRANCH_PROBE] branch=%s key=%s shape=%s dtype=%s norm=%.6f task=%r",
                branch,
                key,
                tuple(embed.shape) if hasattr(embed, "shape") else None,
                getattr(embed, "dtype", None),
                float(embed.norm().item()) if torch.is_tensor(embed) else float("nan"),
                task_str,
            )
            self._lang_branch_probe_seen.add(key)
        return embed.to(device)

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

    def _tensor_to_pil(self, img: torch.Tensor) -> Image.Image:
        """(C, H, W) float [0,1] → PIL Image resized to RDT_IMG_SIZE."""
        if self._undo_libero_flip:
            img = torch.flip(img, dims=[1, 2])
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
        proprio : torch.Tensor shape (1, 8)
            ManiSkill state: 7 Franka joints + single-finger gripper opening.
        task_str : str
            Instruction string (first element of batch)
        """
        # ── Images ──────────────────────────────────────────────────────────
        # The caller should advance history every env step. Keep this fallback
        # for direct unit-test / one-shot process() calls.
        if self._current_static is None:
            self.update_image_history(obs)

        ext_now = self._current_static
        if ext_now is None:
            raise RuntimeError("RDT image history was not initialized")
        ext_prev = self._prev_static
        images = self._build_image_list(ext_prev, ext_now)

        # ── Proprio (8D: 7 arm joints + 1 gripper) ──────────────────────────
        # Use adapter's direct joint accessors when available (LIBERO/CALVIN),
        # which give actual Franka joint angles that match RDT's training space.
        # Fall back to observation.state when no adapter is wired.
        if self._adapter is not None and hasattr(self._adapter, 'get_joint_positions'):
            try:
                joint_pos = self._adapter.get_joint_positions()  # (7,) Franka joints, radians

                # Gripper: RDT's ManiSkill checkpoint trained with proprio[7] =
                # right_gripper_joint_0_pos (a *single* finger qpos in [0, 0.04]).
                # LIBERO's two Franka fingers are modeled with OPPOSITE-SIGN qpos
                # (e.g. [+0.0387, -0.0387] when open), so the previous formula
                # `sum(qpos)/2` collapsed the open/closed signal to ~0 — round-3
                # probe confirmed this fact-supported bug. Read finger-0 qpos
                # directly from the sim and take abs() to recover the
                # training-time signal. Fall back to the averaged sum for
                # non-LIBERO adapters that don't expose the robosuite handle.
                gripper_val = None
                if hasattr(self._adapter, '_get_current_robosuite_env'):
                    try:
                        _renv = self._adapter._get_current_robosuite_env()
                        _robot = _renv.robots[0]
                        _jid0 = _renv.sim.model.joint_name2id(_robot.gripper.joints[0])
                        _qpos_addr0 = int(_renv.sim.model.jnt_qposadr[_jid0])
                        _finger0 = float(_renv.sim.data.qpos[_qpos_addr0])
                        gripper_val = abs(_finger0)
                        if "sim_qpos_addr" not in self._gripper_branch_probe_seen:
                            self._gripper_branch_probe_seen.add("sim_qpos_addr")
                            import logging
                            logging.getLogger("RDTObsProcessor").warning(
                                "[GRIPPER_BRANCH_PROBE] branch=sim_qpos_addr joint=%s jid=%s qpos_addr=%s finger0=%.6f gripper_val=%.6f",
                                _robot.gripper.joints[0], _jid0, _qpos_addr0, _finger0, gripper_val,
                            )
                    except Exception as exc:
                        if self._undo_libero_flip:
                            raise RuntimeError(
                                "RDT LIBERO gripper qpos_addr read failed; refusing to fallback "
                                "to adapter.get_gripper_state()"
                            ) from exc
                        gripper_val = None
                if gripper_val is None:
                    gripper_raw = self._adapter.get_gripper_state()
                    gripper_val = abs(float(gripper_raw)) / 2.0
                    if "adapter_fallback" not in self._gripper_branch_probe_seen:
                        self._gripper_branch_probe_seen.add("adapter_fallback")
                        import logging
                        logging.getLogger("RDTObsProcessor").warning(
                            "[GRIPPER_BRANCH_PROBE] branch=adapter_fallback gripper_raw=%.6f gripper_val=%.6f",
                            float(gripper_raw), gripper_val,
                        )

                proprio_np = np.zeros(8, dtype=np.float32)
                proprio_np[:7] = joint_pos[:7].astype(np.float32)
                proprio_np[7] = np.clip(gripper_val, 0.0, 0.04)
            except Exception as exc:
                if self._undo_libero_flip:
                    raise RuntimeError(
                        "RDT LIBERO proprio construction failed; refusing to fallback "
                        "from joint-space proprio to EEF-pose observation.state"
                    ) from exc
                import logging
                logging.getLogger("RDTObsProcessor").warning(
                    "adapter joint read failed (%s), using obs.state fallback", exc
                )
                proprio_np = self._fallback_proprio_from_state(obs)
        else:
            proprio_np = self._fallback_proprio_from_state(obs)

        # Return (1, 8) tensor — step() / encode_inputs() do unsqueeze(0) → (1, 1, 8)
        proprio = torch.from_numpy(proprio_np).unsqueeze(0)

        # ── Task string ──────────────────────────────────────────────────────
        task_list = obs.get("task", [""])
        task_str = task_list[0] if isinstance(task_list, (list, tuple)) else str(task_list)
        if not task_str.strip():
            raise RuntimeError("RDT task instruction is empty")

        # ── DIAGNOSTIC PROBE P3: RDTObsProcessor.process output (revert via git revert HEAD) ──
        if not getattr(self, '_diag_p3_done', False):
            try:
                from pathlib import Path as _P
                _lp = _P(__file__).resolve().parents[1] / "docs/superpowers/03_evidence/rdt_intergration/round-3/20260511_obs_probes.log"
                _lp.parent.mkdir(parents=True, exist_ok=True)
                _save_now = _lp.parent / "20260511_ext_now_step0.png"
                _save_prev = _lp.parent / "20260511_ext_prev_step0.png"
                if images[3] is not None:
                    images[3].save(str(_save_now))
                if images[0] is not None:
                    images[0].save(str(_save_prev))
                _source = "adapter" if (self._adapter is not None and
                                        hasattr(self._adapter, 'get_joint_positions')) else "fallback"
                _slot_pattern = [type(im).__name__ if im is not None else 'None' for im in images]
                with open(_lp, "a") as _f:
                    _f.write(
                        f"[P3 process_output] len_images={len(images)} "
                        f"slot_pattern={_slot_pattern} "
                        f"ext_now_size={images[3].size if images[3] is not None else None} "
                        f"ext_now_mode={images[3].mode if images[3] is not None else None} "
                        f"ext_prev_is_ext_now={images[0] is images[3]} "
                        f"proprio_shape={tuple(proprio.shape)} "
                        f"proprio={[float(x) for x in proprio.flatten()]} "
                        f"proprio_source={_source} "
                        f"undo_libero_flip={self._undo_libero_flip} "
                        f"task_str_len={len(task_str)} "
                        f"task_str={task_str!r} "
                        f"ext_now_saved={str(_save_now)} "
                        f"ext_prev_saved={str(_save_prev)}\n"
                    )
            except Exception as _e:
                import logging
                logging.getLogger("RDTObsProcessor").warning(f"[P3] probe failed: {_e}")
            self._diag_p3_done = True
        # ── END P3 ─────────────────────────────────────────────────────────────

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
