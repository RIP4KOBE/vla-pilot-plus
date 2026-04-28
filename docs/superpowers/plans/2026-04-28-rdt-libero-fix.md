# RDT-1B LIBERO Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the RDT-1B integration so that `python main.py policy.type=rdt` produces coherent, task-aligned behavior on the LIBERO benchmark instead of random motion.

**Architecture:** Seven sequential tasks, each targeting one verified root cause. Tasks 1–3 are diagnostic/low-risk fixes with no architectural change. Task 4 fixes the proprioceptive input mismatch. Task 4.5 fixes the camera slot mismatch (ManiSkill used only the exterior camera; wrist slots must be `None`). Task 5 fixes the action output mismatch (quick bypass first, then proper FK conversion). Task 6 validates the full stack with a 10-episode LIBERO run.

**Tech Stack:** Python, PyTorch, NumPy, robosuite/MuJoCo (via LIBERO adapter), Franka Panda DH parameters (analytical FK), `core/rdt_obs_processor.py`, `core/rdt_policy_steer.py`, `core/env_adapters/libero_adapter.py`, `third_party/rdt/scripts/maniskill_model.py`.

---

## Dependency Map — What Calls What

```
main.py
  └─ RDTSteer.select_action(batch)
       ├─ RDTObsProcessor.process(batch)     ← Task 4: fix proprio
       │    ├─ get_lang_embed(task_str)       ← Task 3: fix lang embed
       │    └─ _build_image_list(...)         ← Task 4.5: fix camera slots
       ├─ _predict_unguided(...)              ← Task 5a: bypass _unformat_action_to_joint
       │    └─ _RDTModelAdapter.step()        (wraps real.step() which calls _unformat_action_to_joint)
       └─ _postprocess_actions(raw)           ← Task 5b: FK-based EEF-delta
            └─ rdt_to_libero_action(...)      (new: core/rdt_action_converter.py)
```

## File Map

| File | Action | Responsibility |
|---|---|---|
| `core/rdt_obs_processor.py` | Modify | Feed joint angles (not EEF pose) as proprio; wire adapter |
| `core/rdt_policy_steer.py` | Modify | Wire adapter to obs_processor; replace `_predict_unguided`; add action_mode flag |
| `core/rdt_action_converter.py` | Create | Franka Panda FK + incremental EEF-delta conversion |
| `third_party/rdt/scripts/maniskill_model.py` | No change | FK confirms data is Franka-compatible; no edits needed |

---

## Task 1: Diagnostic Probes

**Goal:** Run one episode and verify which of the 5 root causes are active before writing any fix.

**Files:**
- Modify (temporarily): `core/rdt_policy_steer.py`

- [ ] **Step 1.1: Add diagnostic prints to `rdt_policy_steer.py`**

Open `core/rdt_policy_steer.py`. Find `from_pretrained` at line 354 and add a print just before `create_model`:

```python
        # ── DIAGNOSTIC: verify weight loading ────────────────────────────────
        print(f"[DIAG] weight_file resolved to: {weight_file}")
        print(f"[DIAG] config_path resolved to: {config_path}")
```

Find `select_action` at line 549 and add prints at the start of the `if generate_new_chunk:` block:

```python
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
```

Find `_postprocess_actions` at line 626 and add a print at the start:

```python
    def _postprocess_actions(self, actions: Tensor) -> Tensor:
        print(f"[DIAG] actions pre-slice stats: min={actions.float().min().item():.3f}  max={actions.float().max().item():.3f}  mean={actions.float().mean().item():.3f}")
```

- [ ] **Step 1.2: Run a single 1-step diagnostic episode**

```bash
cd /home/hynx/VLA-Pilot++ && python main.py \
  env=libero \
  policy.type=rdt \
  main.use_guidance=false \
  main.episode_num=1 \
  main.sample_batch_size=1 \
  main.render=false 2>&1 | grep '\[DIAG\]' | head -20
```

Expected output (broken state, before any fix):
```
[DIAG] weight_file resolved to: /home/.../.cache/.../rdt/model.safetensors
[DIAG] proprio raw (first 8): [0.38, 0.02, 0.45, 0.0, -1.4, 0.2, 0.0, 0.01]   ← EEF pose, NOT joints
[DIAG] lang_embed norm: 12.xxxx   ← nonzero = T5 is working
[DIAG] actions pre-slice stats: min=1.83  max=3.29  mean=2.4   ← ManiSkill joint angles, NOT ∈ [-1,1]
```

**Interpret the output:**
- `weight_file resolved to: None` → Task 2 is critical (model is randomly initialized)
- `weight_file resolved to: /some/path.safetensors` → weights loaded, skip/skim Task 2
- `lang_embed norm: 0.0000` → Task 3 is critical (zero language embedding)
- `lang_embed norm: >0` → language working, skip Task 3
- `actions stats: min/max far outside [-1,1]` → Task 5 is critical (action mismatch confirmed)
- `proprio raw` has 8 values with 1st three looking like position coords (0.2–0.8) → Task 4 is needed

- [ ] **Step 1.3: Commit diagnostic probes**

```bash
git add core/rdt_policy_steer.py
git commit -m "debug: add diagnostic probes for RDT-LIBERO fix"
```

---

## Task 2: Fix Weight Loading Path

**Goal:** Ensure the checkpoint weights are actually loaded. If `weight_file=None`, the 1B-param model runs with random initialization, which alone explains entirely random behavior.

**Files:**
- Modify: `core/rdt_policy_steer.py:415–439` (the `from_pretrained` weight search block)

- [ ] **Step 2.1: Inspect the weight file structure in the local cache**

```bash
python -c "
from huggingface_hub import snapshot_download
root = snapshot_download('robotics-diffusion-transformer/maniskill-model',
    allow_patterns=['rdt/**', 'rdt/*'])
import os
for dirpath, dirnames, filenames in os.walk(os.path.join(root, 'rdt')):
    for f in filenames:
        p = os.path.join(dirpath, f)
        print(p, os.path.getsize(p) // 1024 // 1024, 'MB')
" 2>&1 | grep -v httpx | head -20
```

This shows what files actually exist under `<snapshot>/rdt/`. Identify the exact filename and path for the weights (look for the largest file, likely `model.safetensors` or `rdt-1b.pt`).

- [ ] **Step 2.2: Patch the weight file search to handle the actual structure**

Read the current search block in `core/rdt_policy_steer.py:415–439`. Replace the weight file search block with one that walks the directory recursively and also checks the `rdt/` subdirectory correctly:

```python
        # Locate the weight file (prefer .safetensors, fall back to .pt)
        # Walk up to 2 levels deep to handle nested checkpoint layouts.
        weight_file = None
        weight_names = ("model.safetensors", "pytorch_model.bin", "rdt-1b.pt")
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
        if weight_file is None:
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
```

- [ ] **Step 2.3: Run the diagnostic again and confirm weight_file is not None**

```bash
cd /home/hynx/VLA-Pilot++ && python main.py \
  env=libero policy.type=rdt \
  main.use_guidance=false main.episode_num=1 \
  main.sample_batch_size=1 main.render=false 2>&1 | grep -E '\[DIAG\]|\[FIX2\]' | head -10
```

Expected:
```
[FIX2] weight_file = /home/.../.cache/.../rdt/model.safetensors
[DIAG] actions pre-slice stats: min=...  max=...   ← still out of range, next tasks fix this
```

- [ ] **Step 2.4: Commit**

```bash
git add core/rdt_policy_steer.py
git commit -m "fix: robust weight file search for RDT checkpoint (handles nested layouts)"
```

---

## Task 3: Fix Language Embedding

**Goal:** Ensure T5-XXL text embeddings are non-zero and reflect the actual task. Two failure modes: (a) the `_text_encoder_fn` wiring silently fails so every episode gets a zero embedding, (b) the `encode_instruction` call itself fails.

**Files:**
- Modify: `core/rdt_policy_steer.py:499–508` (the `post_init` wiring block)
- Modify: `core/rdt_obs_processor.py:57–78` (the `get_lang_embed` fallback)

- [ ] **Step 3.1: Fix the silent except in `post_init`**

In `core/rdt_policy_steer.py`, find the `post_init` method at line 480. Replace the silent `except Exception: pass` block with one that logs and falls back gracefully:

```python
        # Reuse the T5 already loaded inside the RDT model to avoid a second T5 load.
        try:
            real = object.__getattribute__(self._rdt_model, "_real")
            if callable(getattr(real, "encode_instruction", None)):
                _enc_device = str(real.device)
                def _enc_fn(s, _d=_enc_device):
                    emb = real.encode_instruction(s, device=_d)
                    # encode_instruction returns (1, seq_len, d_model); ensure float32
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
```

- [ ] **Step 3.2: Fix the zero-embedding fallback shape in `get_lang_embed`**

In `core/rdt_obs_processor.py`, the fallback zero tensor at line 77 currently uses shape `(1, 1, 4096)`. Verify the real embedding shape produced by `encode_instruction` first:

```bash
python -c "
import sys; sys.path.insert(0, 'third_party/rdt')
import yaml, torch
with open(next(__import__('pathlib').Path('.').glob('**/.cache/huggingface/hub/models--robotics-diffusion-transformer*/snapshots/*/rdt/config.yaml')), 'r') as f:
    args = yaml.safe_load(f)
print('tokenizer_max_length:', args['dataset']['tokenizer_max_length'])
print('lang_token_dim:', args['model']['lang_token_dim'])
" 2>/dev/null || echo "Could not read config, assuming 512-token 4096-dim"
```

Expected output shows `tokenizer_max_length` and `lang_token_dim`. Ensure the fallback zero tensor matches:

```python
# In core/rdt_obs_processor.py get_lang_embed, the fallback:
# T5-XXL d_model = 4096; tokenizer_max_length from config (typically 512 for RDT)
# Shape must match encode_instruction output: (1, seq_len, 4096)
self._lang_cache[key] = torch.zeros(1, 1, 4096)  # seq_len=1 is a safe minimal fallback
```

The shape `(1, 1, 4096)` is already correct in the current code. No change needed if this matches.

- [ ] **Step 3.3: Run diagnostic again and confirm embedding norm is nonzero**

```bash
cd /home/hynx/VLA-Pilot++ && python main.py \
  env=libero policy.type=rdt \
  main.use_guidance=false main.episode_num=1 \
  main.sample_batch_size=1 main.render=false 2>&1 | grep -E '\[DIAG\]|\[FIX3\]' | head -10
```

Expected:
```
[FIX3] T5 wired via real.encode_instruction
[DIAG] lang_embed norm: 23.4567    ← nonzero confirms language is active
```

If norm is still 0, investigate whether `real.encode_instruction` raises an exception or returns zeros itself:

```bash
python -c "
import sys; sys.path.insert(0,'third_party/rdt')
import yaml, torch
# minimal reproduce of encode_instruction
" 2>&1 | head -10
```

- [ ] **Step 3.4: Commit**

```bash
git add core/rdt_policy_steer.py core/rdt_obs_processor.py
git commit -m "fix: expose T5 wiring errors; ensure language embedding is non-zero"
```

---

## Task 4: Fix Proprioceptive Input

**Goal:** Replace LIBERO's EEF-pose `observation.state` (Cartesian space) with actual Franka joint angles as proprio input to RDT, which expects joint-angle conditioning.

**Why this matters:** `LiberoProcessorStep` builds `observation.state = [eef_pos(3), axis_angle(3), gripper_qpos(2)]`. RDT's `_format_joint_to_state` normalizes these values with ManiSkill joint-angle min/max, producing values as far as -3.5 (outside [-1, 1]). The model receives garbage conditioning and produces actions close to prior noise.

**Fix:** Wire `self._adapter` into `RDTObsProcessor` so it can call `get_joint_positions()` and `get_gripper_state()` directly.

**Files:**
- Modify: `core/rdt_obs_processor.py` (add `_adapter` attribute; change `process()` proprio section)
- Modify: `core/rdt_policy_steer.py` (`post_init` — set `_obs_processor._adapter = adapter`)

- [ ] **Step 4.1: Add `_adapter` to `RDTObsProcessor.__init__`**

In `core/rdt_obs_processor.py`, find the `__init__` method at line 31. After the existing attributes, add:

```python
        # Optional env adapter for direct joint-angle access (bypasses EEF-pose obs.state).
        self._adapter = None
```

- [ ] **Step 4.2: Replace the proprio block in `RDTObsProcessor.process()`**

In `core/rdt_obs_processor.py`, find the `process()` method. Replace the entire `# ── Proprio` block (currently lines 131–143) with:

```python
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

        proprio = torch.from_numpy(proprio_np).unsqueeze(0)  # (1, 8)
```

- [ ] **Step 4.3: Add `_fallback_proprio_from_state` helper**

Still in `core/rdt_obs_processor.py`, add this helper method after `process()`:

```python
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
```

- [ ] **Step 4.4: Wire the adapter in `RDTSteer.post_init`**

In `core/rdt_policy_steer.py`, find `post_init` at line 480. After `if self._obs_processor is None: ...` block (around line 493), add one line:

```python
        # Wire adapter for direct joint-angle proprio (Task 4 fix).
        self._obs_processor._adapter = self._adapter
```

- [ ] **Step 4.5: Run diagnostic and confirm proprio looks like joint angles**

```bash
cd /home/hynx/VLA-Pilot++ && python main.py \
  env=libero policy.type=rdt \
  main.use_guidance=false main.episode_num=1 \
  main.sample_batch_size=1 main.render=false 2>&1 | grep '\[FIX4\]' | head -5
```

Expected: `[FIX4] proprio joints (first 4): [-0.002, 0.15, 0.01, -2.54]`
(Franka Panda home config: j0≈0, j1≈0.15, j2≈0, j3≈-2.54, j4≈0, j5≈2.8, j6≈0.8)

Joint values in range approximately:
- j3 should be around -2.5 (negative — matches ManiSkill DATA_STAT range [-2.66, -0.39])
- j5 should be around 2.8 (positive — matches ManiSkill DATA_STAT range [1.83, 3.29])

If the joints look roughly like this, the proprioceptive fix is working.

- [ ] **Step 4.6: Run `tests/test_rdt_steer.py` to confirm no regression**

```bash
cd /home/hynx/VLA-Pilot++ && python -m pytest tests/test_rdt_steer.py -v 2>&1 | tail -10
```

Expected: all tests still pass (stub adapter doesn't call `get_joint_positions`, so no change).

- [ ] **Step 4.7: Commit**

```bash
git add core/rdt_obs_processor.py core/rdt_policy_steer.py
git commit -m "fix: use Franka joint angles as RDT proprio input (was EEF pose from observation.state)"
```

---

## Task 4.5: Fix Camera Slot Mismatch

**Goal:** The ManiSkill checkpoint was trained with ONLY `cam_high` (exterior camera). Both wrist camera slots (`cam_right_wrist`, `cam_left_wrist`) were always `np.zeros((H, 0, 0, 0))` — empty — during training. At inference, `maniskill_model.py` substitutes `background_image` (SigLIP mean color) when an image is `None`. The current code sends real wrist images to slots 1 and 4 (completely out-of-distribution) and `_BLACK_PIL` to slots 2 and 5 (bypasses the model's intended None→background substitution path). Both are wrong.

**Fix:** Pass `None` for all four wrist slots so the model substitutes its own background image — matching the training distribution exactly.

**Where this was discovered:** `third_party/rdt/data/hdf5_maniskill_dataset.py:221–226` shows `"cam_left_wrist": np.zeros((IMG_HISTORY_SIZE, 0, 0, 0))` for every sample, and `maniskill_model.py:step()` has `if image is None: image = Image.fromarray(background_image)`.

**Files:**
- Modify: `core/rdt_obs_processor.py` (replace image list construction; remove dead wrist-history code)
- Create: `tests/test_rdt_obs_processor.py`

- [ ] **Step 4.5.1: Replace the image-list block in `RDTObsProcessor.process()`**

In `core/rdt_obs_processor.py`, the entire `# ── Images` block currently reads (lines 114–131):

```python
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
```

Replace the entire block with:

```python
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
```

Also remove the `_prev_wrist` attribute from `__init__` and `reset()`. In `__init__` (line 38–39), remove:
```python
        self._prev_wrist: Optional[Image.Image] = None
```

In `reset()` (line 44–47), remove:
```python
        self._prev_wrist = None
```

- [ ] **Step 4.5.2: Add the `_build_image_list()` static method**

In `core/rdt_obs_processor.py`, add this method to `RDTObsProcessor` immediately after `reset()`:

```python
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
```

- [ ] **Step 4.5.3: Run a single episode and confirm None slots**

```bash
cd /home/hynx/VLA-Pilot++ && python main.py \
  env=libero policy.type=rdt \
  main.use_guidance=false main.episode_num=1 \
  main.sample_batch_size=1 main.render=false 2>&1 | grep '\[FIX4.5\]' | head -3
```

Expected:
```
[FIX4.5] image slots: ['Image', 'None', 'None', 'Image', 'None', 'None']
```

If you see `'JpegImageFile'` or similar subclass names, that's also fine — the important thing is that slots 1, 2, 4, 5 show `'None'`.

Remove the `print("[FIX4.5]...")` line from `process()` after confirming.

- [ ] **Step 4.5.4: Write unit tests for `_build_image_list`**

Create `tests/test_rdt_obs_processor.py`:

```python
"""Unit tests for RDTObsProcessor._build_image_list — no GPU or model required."""
import numpy as np
import pytest
from PIL import Image

from core.rdt_obs_processor import RDTObsProcessor, RDT_IMG_SIZE


def _dummy_frame(color=(0, 0, 0)) -> Image.Image:
    arr = np.full((RDT_IMG_SIZE, RDT_IMG_SIZE, 3), color, dtype=np.uint8)
    return Image.fromarray(arr)


def test_build_image_list_has_six_slots():
    result = RDTObsProcessor._build_image_list(_dummy_frame(), _dummy_frame())
    assert len(result) == 6


def test_exterior_slots_are_real_images():
    """Slots 0 (ext_prev) and 3 (ext_now) must be PIL Images."""
    result = RDTObsProcessor._build_image_list(_dummy_frame(), _dummy_frame())
    assert isinstance(result[0], Image.Image), "Slot 0 must be a PIL Image"
    assert isinstance(result[3], Image.Image), "Slot 3 must be a PIL Image"


def test_wrist_slots_are_none():
    """Slots 1, 2, 4, 5 must be None (ManiSkill was trained on cam_high only)."""
    result = RDTObsProcessor._build_image_list(_dummy_frame(), _dummy_frame())
    for slot in (1, 2, 4, 5):
        assert result[slot] is None, f"Slot {slot} must be None, got {result[slot]}"


def test_prev_and_now_not_swapped():
    """ext_prev → slot 0, ext_now → slot 3 (order must not be reversed)."""
    prev = _dummy_frame(color=(255, 0, 0))
    now = _dummy_frame(color=(0, 255, 0))
    result = RDTObsProcessor._build_image_list(prev, now)
    assert result[0].getpixel((0, 0))[:3] == (255, 0, 0), "Slot 0 should be ext_prev"
    assert result[3].getpixel((0, 0))[:3] == (0, 255, 0), "Slot 3 should be ext_now"
```

- [ ] **Step 4.5.5: Run the new tests**

```bash
cd /home/hynx/VLA-Pilot++ && python -m pytest tests/test_rdt_obs_processor.py -v
```

Expected:
```
tests/test_rdt_obs_processor.py::test_build_image_list_has_six_slots  PASSED
tests/test_rdt_obs_processor.py::test_exterior_slots_are_real_images  PASSED
tests/test_rdt_obs_processor.py::test_wrist_slots_are_none            PASSED
tests/test_rdt_obs_processor.py::test_prev_and_now_not_swapped        PASSED
```

- [ ] **Step 4.5.6: Commit**

```bash
git add core/rdt_obs_processor.py tests/test_rdt_obs_processor.py
git commit -m "fix: pass None to wrist camera slots (ManiSkill checkpoint trained on cam_high only)"
```

---

## Task 5: Fix Action Output

### Task 5a — Quick Fix: Bypass `_unformat_action_to_joint`

**Goal:** Make `_predict_unguided` use the same denoising loop as the guided path, which naturally returns normalized output in [-1, 1] without going through `_unformat_action_to_joint`. This is the fastest path to in-range actions.

**Why this is correct:** The guided denoising loop in `_guided_denoise_loop` already returns `x_t` in normalized space (the DiT adapter processes the unified-space output and returns raw-action-dim values before any denormalization). The unguided path currently goes through `real.step()` → `_unformat_action_to_joint`, which maps normalized values back to ManiSkill joint-angle space (roughly 1.8–3.3 rad for some joints). Sending those values to LIBERO's [-1, 1] OSC controller causes random extreme motion.

**Files:**
- Modify: `core/rdt_policy_steer.py:599–622` (`_predict_unguided`)

- [ ] **Step 5a.1: Replace `_predict_unguided` to use the denoising loop directly**

In `core/rdt_policy_steer.py`, find `_predict_unguided` at line 599. Replace the entire method with:

```python
    def _predict_unguided(
        self,
        proprio,
        images: list,
        text_embed: Tensor,
        B: int,
    ) -> Tensor:
        """
        Run the denoising loop without guidance hooks.

        Returns (B, 64, raw_action_dim) in NORMALIZED space ∈ [-1, 1].
        Does NOT apply _unformat_action_to_joint so values stay in range
        for LIBERO's OSC controller (which expects actions ∈ [-1, 1]).
        """
        device = self.device
        try:
            dtype = next(self._dit.parameters()).dtype
        except StopIteration:
            dtype = torch.float32

        cond = self._rdt_model.encode_inputs(proprio, images, text_embed)
        raw_action_dim = len(cond["action_indices"])  # 8 for ManiSkill
        x_t = torch.randn(B, 64, raw_action_dim, device=device, dtype=dtype)

        scheduler = self._noise_scheduler
        scheduler.set_timesteps(self._num_inference_steps)

        with torch.no_grad():
            for t in scheduler.timesteps:
                noise_pred = self._dit(x_t, t, cond)
                x_t = scheduler.step(noise_pred, t, x_t).prev_sample

        return x_t  # (B, 64, 8) normalized ∈ [-1, 1]
```

- [ ] **Step 5a.2: Fix `_postprocess_actions` to include the gripper dimension**

Currently `_postprocess_actions` slices `_ARM_JOINTS = slice(0, 7)`, dropping the 8th dimension (gripper). LIBERO's 7D action is `[dx, dy, dz, droll, dpitch, dyaw, gripper]` — the gripper is the 7th element (index 6). RDT's 8D output has the gripper at index 7. Fix: map RDT's gripper (dim 7) to LIBERO's last dim (dim 6).

Replace `_postprocess_actions` at line 626:

```python
    def _postprocess_actions(self, actions: Tensor) -> Tensor:
        """
        (B, 64, 8) normalized → (1, H, 7) for LIBERO.

        RDT output layout: [j0, j1, j2, j3, j4, j5, j6, gripper]  (8D)
        LIBERO action layout: [dx, dy, dz, drx, dry, drz, gripper] (7D)

        For the normalized-bypass path (Task 5a) and the FK path (Task 5b):
        - First 6 dims will be replaced by FK-derived EEF delta in Task 5b.
        - Gripper: RDT dim 7 maps directly to LIBERO dim 6 (already in [-1, 1]).
        """
        best = actions[0]  # (64, 8) — particle 0 (FKD puts best first)
        chunk = best[: self._action_chunk_horizon]  # (H, 8)

        # Build 7D LIBERO action: dims 0-5 from RDT dims 0-5 (joint → EEF proxy),
        # dim 6 (gripper) from RDT dim 7.
        libero_action = torch.cat([chunk[:, :6], chunk[:, 7:8]], dim=1)  # (H, 7)

        print(f"[FIX5a] action chunk stats: min={libero_action.float().min().item():.3f}  "
              f"max={libero_action.float().max().item():.3f}")
        return libero_action.unsqueeze(0).float()  # (1, H, 7)
```

- [ ] **Step 5a.3: Run diagnostic to verify actions are now in [-1, 1]**

```bash
cd /home/hynx/VLA-Pilot++ && python main.py \
  env=libero policy.type=rdt \
  main.use_guidance=false main.episode_num=1 \
  main.sample_batch_size=1 main.render=false 2>&1 | grep '\[FIX5a\]' | head -5
```

Expected: `[FIX5a] action chunk stats: min=-0.8xx  max=0.7xx`

Values should now be solidly within [-1, 1]. This confirms the action-range fix is working.

- [ ] **Step 5a.4: Run 5 episodes and observe qualitative behavior**

```bash
cd /home/hynx/VLA-Pilot++ && python main.py \
  env=libero policy.type=rdt \
  main.use_guidance=false main.episode_num=5 \
  main.sample_batch_size=1 main.render=false 2>&1 | tail -5
```

Check `outputs/libero/<TIMESTAMP>/results.txt` and watch episode videos. If success rate > 0/5, even 1/5, Task 5a already produces useful behavior and Task 5b becomes an optional refinement. If still 0/5 but the arm is now moving coherently (toward objects, in task-relevant directions), proceed to Task 5b.

- [ ] **Step 5a.5: Commit**

```bash
git add core/rdt_policy_steer.py
git commit -m "fix: _predict_unguided uses denoising loop directly; gripper dim wired correctly"
```

---

### Task 5b — Proper Fix: Franka FK–Based EEF-Delta Conversion

**Goal:** Replace the semantic mismatch in Task 5a (treating joint-angle dimensions as EEF-delta dimensions) with a proper conversion using Franka Panda forward kinematics. This converts RDT's predicted joint-angle trajectory to an incremental EEF-delta action chunk that correctly drives LIBERO's OSC controller.

**Why the DATA_STAT ranges imply Franka Panda:**
All 7 DATA_STAT joint ranges are subsets of Franka Panda URDF limits with matching sign conventions (j3 is entirely negative, j5 is entirely positive ≥ 1.83 rad), confirming the ManiSkill training data came from a Franka robot. FK using Franka DH parameters will therefore be accurate.

**Files:**
- Create: `core/rdt_action_converter.py`
- Modify: `core/rdt_policy_steer.py` (`_postprocess_actions`)

- [ ] **Step 5b.1: Create `core/rdt_action_converter.py`**

```python
"""
rdt_action_converter.py — Convert RDT joint-space predictions to LIBERO EEF-delta actions.

RDT-ManiSkill predicts absolute joint angles (after denormalization) for a Franka Panda arm.
LIBERO uses OSC (Operational Space Control): 7D EEF-delta [dx, dy, dz, drx, dry, drz, gripper].

Conversion pipeline:
  1. Denormalize RDT normalized output ∈ [-1,1] → actual joint angles (radians).
  2. Compute Franka FK for consecutive predicted joint configs.
  3. Convert incremental EEF-pose differences to LIBERO OSC action vectors.
"""
from __future__ import annotations
from typing import Tuple

import numpy as np

# ── Franka Panda DH parameters ────────────────────────────────────────────────
# Source: Franka Panda technical specifications, modified DH convention.
# [a (m), d (m), alpha (rad)] — theta_i = q_i (no constant offset for joints 0–6).
_FRANKA_DH = [
    (0,        0.333,   0.0),           # joint 1
    (0,        0.0,    -np.pi / 2),     # joint 2
    (0,        0.316,   np.pi / 2),     # joint 3
    (0.0825,   0.0,     np.pi / 2),     # joint 4
    (-0.0825,  0.384,  -np.pi / 2),     # joint 5
    (0,        0.0,     np.pi / 2),     # joint 6
    (0.088,    0.0,     np.pi / 2),     # joint 7
    (0,        0.107,   0.0),           # flange (fixed, theta=0)
]

# Franka Panda joint limits (URDF) — used to clip RDT predictions.
FRANKA_Q_MIN = np.array([-2.8973, -1.7628, -2.8973, -3.0718, -2.8973, -0.0175, -2.8973])
FRANKA_Q_MAX = np.array([ 2.8973,  1.7628,  2.8973, -0.0698,  2.8973,  3.7525,  2.8973])

# RDT DATA_STAT — the training data normalization constants.
# action_min/max for the 7 arm joints (dim 7 = gripper, handled separately).
RDT_ACTION_MIN = np.array([-0.7472, -0.0863, -0.4995, -2.6584, -0.5751,  1.8291, -2.2452])
RDT_ACTION_MAX = np.array([ 0.7655,  1.4984,  0.4679, -0.3818,  0.5517,  3.2916,  2.5758])

# LIBERO OSC action scale (empirical from LIBERO/robosuite docs).
# OSC maps action ∈ [-1, 1] to:
#   position delta: ±0.05 m  per unit (kp ≈ 150, action_scale ≈ 0.05)
#   orientation delta: ±0.5 rad per unit
_POS_SCALE = 0.05   # m per unit action
_ORI_SCALE = 0.5    # rad per unit action


def _dh_matrix(a: float, d: float, alpha: float, theta: float) -> np.ndarray:
    """Compute a 4x4 homogeneous DH transformation matrix."""
    ct, st = np.cos(theta), np.sin(theta)
    ca, sa = np.cos(alpha), np.sin(alpha)
    return np.array([
        [ct, -st * ca,  st * sa, a * ct],
        [st,  ct * ca, -ct * sa, a * st],
        [0.0,       sa,       ca,      d],
        [0.0,      0.0,      0.0,    1.0],
    ])


def franka_fk_pose(q: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute Franka Panda forward kinematics.

    Args:
        q: (7,) joint angles in radians.

    Returns:
        pos: (3,) EEF position in robot base frame (meters).
        rot: (3, 3) EEF rotation matrix in robot base frame.
    """
    T = np.eye(4)
    for i, (a, d, alpha) in enumerate(_FRANKA_DH[:7]):
        T = T @ _dh_matrix(a, d, alpha, float(q[i]))
    # Flange (fixed transformation, theta=0)
    a, d, alpha = _FRANKA_DH[7]
    T = T @ _dh_matrix(a, d, alpha, 0.0)
    return T[:3, 3].copy(), T[:3, :3].copy()


def _rot_to_axisangle(R: np.ndarray) -> np.ndarray:
    """Convert a 3x3 rotation matrix to a 3D axis-angle vector."""
    cos_angle = np.clip((np.trace(R) - 1.0) / 2.0, -1.0, 1.0)
    angle = float(np.arccos(cos_angle))
    if abs(angle) < 1e-7:
        return np.zeros(3)
    axis = np.array([R[2, 1] - R[1, 2],
                     R[0, 2] - R[2, 0],
                     R[1, 0] - R[0, 1]], dtype=np.float64)
    axis /= (2.0 * np.sin(angle) + 1e-9)
    return axis * angle


def denormalize_rdt_joints(x_norm: np.ndarray) -> np.ndarray:
    """
    Denormalize RDT's 7D joint output from [-1, 1] to actual joint angles (radians).

    Uses DATA_STAT action_min/max from maniskill_model.py (proven Franka-compatible).
    Clips to Franka URDF limits to prevent extrapolation.

    Args:
        x_norm: (7,) normalized joint values ∈ [-1, 1].

    Returns:
        (7,) joint angles in radians, clipped to Franka limits.
    """
    joints = (x_norm + 1.0) / 2.0 * (RDT_ACTION_MAX - RDT_ACTION_MIN) + RDT_ACTION_MIN
    return np.clip(joints, FRANKA_Q_MIN, FRANKA_Q_MAX)


def rdt_chunk_to_libero_actions(
    rdt_normalized_chunk: np.ndarray,   # (H, 8) normalized RDT output ∈ [-1, 1]
    current_joints: np.ndarray,         # (7,) current Franka joint angles from adapter
) -> np.ndarray:
    """
    Convert an RDT action chunk to LIBERO OSC EEF-delta actions.

    Steps:
      1. Denormalize RDT joints using DATA_STAT.
      2. Compute FK for the current config and each predicted config.
      3. Compute INCREMENTAL EEF deltas (each step relative to the previous).
      4. Scale position and orientation deltas to LIBERO's [-1, 1] action space.
      5. Append RDT's gripper dimension (already in [-1, 1]).

    The incremental formulation means:
      - Step 0 moves from current EEF to predicted EEF[0].
      - Step i moves from predicted EEF[i-1] to predicted EEF[i].
    This correctly drives LIBERO's receding-horizon OSC controller.

    Args:
        rdt_normalized_chunk: (H, 8) where columns 0-6 are arm joints, column 7 is gripper.
        current_joints: (7,) current joint angles in radians.

    Returns:
        (H, 7) LIBERO action chunk: [dx, dy, dz, drx, dry, drz, gripper] each ∈ [-1, 1].
    """
    H = rdt_normalized_chunk.shape[0]

    # Denormalize arm joints; gripper is already in [-1, 1] per DATA_STAT.
    arm_norm = rdt_normalized_chunk[:, :7]   # (H, 7)
    gripper   = rdt_normalized_chunk[:, 7]   # (H,)  already ∈ [-1, 1]

    # FK for each step.
    # q_sequence[0] = current; q_sequence[1..H] = predicted.
    q_sequence = [current_joints.copy()]
    for i in range(H):
        q_sequence.append(denormalize_rdt_joints(arm_norm[i]))

    poses = [franka_fk_pose(q) for q in q_sequence]  # list of (pos, rot)

    # Incremental EEF deltas.
    libero_actions = np.zeros((H, 7), dtype=np.float32)
    for i in range(H):
        pos_prev, rot_prev = poses[i]
        pos_curr, rot_curr = poses[i + 1]

        delta_pos = pos_curr - pos_prev                        # (3,) meters
        delta_rot_mat = rot_curr @ rot_prev.T                  # rotation from prev→curr
        delta_axisangle = _rot_to_axisangle(delta_rot_mat)    # (3,) axis-angle

        # Normalize to LIBERO [-1, 1] scale.
        action_pos = np.clip(delta_pos / _POS_SCALE, -1.0, 1.0)
        action_ori = np.clip(delta_axisangle / _ORI_SCALE, -1.0, 1.0)

        # LIBERO gripper: -1 = open, +1 = close.
        # RDT gripper_open: high value = open. Negate to match LIBERO convention.
        action_gripper = float(-gripper[i])

        libero_actions[i] = np.concatenate([action_pos, action_ori, [action_gripper]])

    return libero_actions
```

- [ ] **Step 5b.2: Write a unit test for the FK converter**

Create `tests/test_rdt_action_converter.py`:

```python
"""
Unit tests for core/rdt_action_converter.py.
All CPU-only, no GPU or checkpoint required.
"""
import numpy as np
import pytest
from core.rdt_action_converter import (
    franka_fk_pose,
    denormalize_rdt_joints,
    rdt_chunk_to_libero_actions,
    FRANKA_Q_MIN,
    FRANKA_Q_MAX,
    RDT_ACTION_MIN,
    RDT_ACTION_MAX,
)


def test_fk_at_zero_joints():
    """FK at all-zero joints should return a non-zero EEF position."""
    q = np.zeros(7)
    pos, rot = franka_fk_pose(q)
    assert pos.shape == (3,)
    assert rot.shape == (3, 3)
    # EEF should be above the base, not at origin
    assert abs(pos[2]) > 0.1, f"Expected z > 0.1, got {pos[2]}"


def test_fk_rotation_is_orthogonal():
    """Rotation matrix must be orthogonal (R.T @ R ≈ I)."""
    q = np.array([0.1, -0.5, 0.2, -2.0, 0.1, 2.5, 0.3])
    _, rot = franka_fk_pose(q)
    residual = np.max(np.abs(rot.T @ rot - np.eye(3)))
    assert residual < 1e-6, f"Rotation not orthogonal: residual={residual}"


def test_fk_different_configs_differ():
    """Two different joint configs must produce different EEF positions."""
    q1 = np.zeros(7)
    q2 = np.array([0.5, 0.2, -0.3, -1.5, 0.1, 2.0, 0.8])
    pos1, _ = franka_fk_pose(q1)
    pos2, _ = franka_fk_pose(q2)
    assert np.linalg.norm(pos1 - pos2) > 0.01


def test_denormalize_identity_endpoints():
    """Normalized +1 should denormalize to action_max, -1 to action_min."""
    ones = np.ones(7)
    result_max = denormalize_rdt_joints(ones)
    np.testing.assert_allclose(result_max, np.clip(RDT_ACTION_MAX, FRANKA_Q_MIN, FRANKA_Q_MAX),
                               atol=1e-5)

    neg_ones = -np.ones(7)
    result_min = denormalize_rdt_joints(neg_ones)
    np.testing.assert_allclose(result_min, np.clip(RDT_ACTION_MIN, FRANKA_Q_MIN, FRANKA_Q_MAX),
                               atol=1e-5)


def test_chunk_output_shape():
    """rdt_chunk_to_libero_actions must return (H, 7)."""
    H = 8
    rdt_chunk = np.random.uniform(-0.5, 0.5, (H, 8)).astype(np.float32)
    current_q = np.array([0.0, 0.15, 0.0, -2.54, 0.0, 2.80, 0.78])
    result = rdt_chunk_to_libero_actions(rdt_chunk, current_q)
    assert result.shape == (H, 7), f"Expected ({H}, 7), got {result.shape}"


def test_chunk_output_in_range():
    """All LIBERO actions must be clipped to [-1, 1]."""
    H = 8
    rdt_chunk = np.random.uniform(-1.0, 1.0, (H, 8)).astype(np.float32)
    current_q = np.array([0.0, 0.15, 0.0, -2.54, 0.0, 2.80, 0.78])
    result = rdt_chunk_to_libero_actions(rdt_chunk, current_q)
    assert np.all(result >= -1.0) and np.all(result <= 1.0), \
        f"Actions out of [-1,1]: min={result.min():.3f} max={result.max():.3f}"


def test_zero_motion_chunk_near_zero_delta():
    """Constant predicted config = current config → EEF delta ≈ zero."""
    current_q = np.array([0.0, 0.15, 0.0, -2.54, 0.0, 2.80, 0.78])
    # Normalized value that denormalizes back to approximately current_q
    # (reverse the denormalization for joint 0 which has range [-0.747, 0.765])
    # Use zero action (normalized midpoint ≈ stationary near rest config)
    H = 4
    rdt_chunk = np.zeros((H, 8), dtype=np.float32)
    # Set arm joints to the normalized value of current_q[0..6]
    for j in range(7):
        from core.rdt_action_converter import RDT_ACTION_MIN, RDT_ACTION_MAX
        norm_val = (current_q[j] - RDT_ACTION_MIN[j]) / (RDT_ACTION_MAX[j] - RDT_ACTION_MIN[j]) * 2 - 1
        rdt_chunk[:, j] = np.clip(norm_val, -1.0, 1.0)
    result = rdt_chunk_to_libero_actions(rdt_chunk, current_q)
    # All steps should be near-zero (same config, no motion)
    assert np.all(np.abs(result[:, :6]) < 0.05), \
        f"Expected near-zero EEF deltas, got max={np.abs(result[:, :6]).max():.4f}"
```

- [ ] **Step 5b.3: Run the tests — they should all pass**

```bash
cd /home/hynx/VLA-Pilot++ && python -m pytest tests/test_rdt_action_converter.py -v
```

Expected:
```
tests/test_rdt_action_converter.py::test_fk_at_zero_joints          PASSED
tests/test_rdt_action_converter.py::test_fk_rotation_is_orthogonal  PASSED
tests/test_rdt_action_converter.py::test_fk_different_configs_differ PASSED
tests/test_rdt_action_converter.py::test_denormalize_identity_endpoints PASSED
tests/test_rdt_action_converter.py::test_chunk_output_shape          PASSED
tests/test_rdt_action_converter.py::test_chunk_output_in_range       PASSED
tests/test_rdt_action_converter.py::test_zero_motion_chunk_near_zero_delta PASSED
```

If `test_zero_motion_chunk_near_zero_delta` fails, check whether the current joint config falls outside RDT's DATA_STAT action range — the test may need a different `current_q`.

- [ ] **Step 5b.4: Integrate FK conversion into `_postprocess_actions`**

In `core/rdt_policy_steer.py`, replace `_postprocess_actions` again (superseding the Task 5a version):

```python
    def _postprocess_actions(self, actions: Tensor) -> Tensor:
        """
        (B, 64, 8) normalized → (1, H, 7) LIBERO EEF-delta using Franka FK.

        If the adapter provides joint positions, uses FK-based EEF-delta conversion.
        Falls back to the normalized-bypass (Task 5a) approach when the adapter
        is unavailable (e.g. in unit tests using stub models).
        """
        from core.rdt_action_converter import rdt_chunk_to_libero_actions

        best = actions[0]  # (64, 8) — particle 0
        chunk_np = best[: self._action_chunk_horizon].detach().cpu().float().numpy()  # (H, 8)

        if self._adapter is not None and hasattr(self._adapter, 'get_joint_positions'):
            try:
                current_joints = self._adapter.get_joint_positions().astype(np.float64)  # (7,)
                libero_chunk = rdt_chunk_to_libero_actions(chunk_np, current_joints)  # (H, 7)
                result = torch.from_numpy(libero_chunk).unsqueeze(0).float()  # (1, H, 7)
                print(f"[FIX5b] FK action: min={libero_chunk.min():.3f}  max={libero_chunk.max():.3f}")
                return result
            except Exception as exc:
                print(f"[FIX5b] WARNING: FK conversion failed ({exc}), falling back to bypass")

        # Fallback: normalized bypass (Task 5a)
        libero_action = torch.cat(
            [torch.from_numpy(chunk_np[:, :6]), torch.from_numpy(chunk_np[:, 7:8])], dim=1
        )
        return libero_action.unsqueeze(0).float()  # (1, H, 7)
```

Also add `import numpy as np` at the top of `rdt_policy_steer.py` if not already present (it is: already imported on line 10).

- [ ] **Step 5b.5: Confirm existing RDT smoke tests still pass**

```bash
cd /home/hynx/VLA-Pilot++ && python -m pytest tests/test_rdt_steer.py tests/test_rdt_action_converter.py -v 2>&1 | tail -15
```

Expected: all pass. The stub model path will fall through to the bypass fallback in `_postprocess_actions` since `self._adapter` is a `MagicMock`.

- [ ] **Step 5b.6: Commit**

```bash
git add core/rdt_action_converter.py tests/test_rdt_action_converter.py core/rdt_policy_steer.py
git commit -m "feat: Franka FK-based RDT→LIBERO action conversion (rdt_action_converter.py)"
```

---

## Task 6: End-to-End Evaluation

**Goal:** Run 10 LIBERO episodes with all fixes applied. Verify success rate is > 0 and actions are qualitatively coherent. Also confirm the other two policies (`diffusion`, `pi05`) show no regression.

**Files:** None (evaluation only).

- [ ] **Step 6.1: Remove all `[DIAG]`/`[FIX]` diagnostic prints**

These prints are noisy and go to stdout (not Hydra log). Remove them now that debugging is complete.

In `core/rdt_policy_steer.py`, remove the five `print("[DIAG..."])` and `print("[FIX...]")` lines added during Tasks 1–5. In `core/rdt_obs_processor.py`, remove the `print("[FIX4]...")` line.

After cleanup, verify no `[DIAG]` or `[FIX]` prints remain:
```bash
grep -n '\[DIAG\]\|\[FIX\]' core/rdt_policy_steer.py core/rdt_obs_processor.py
```
Expected: no output.

- [ ] **Step 6.2: Run 10 LIBERO episodes (no guidance, single particle)**

```bash
cd /home/hynx/VLA-Pilot++ && python main.py \
  env=libero \
  policy.type=rdt \
  main.use_guidance=false \
  main.episode_num=10 \
  main.sample_batch_size=1 \
  main.render=false 2>&1 | tail -5
```

```bash
cat outputs/libero/$(ls -t outputs/libero/ | head -1)/results.txt
```

**Interpret results:**
- `0/10` success but robot moves coherently toward objects → FK is working, model may need task-specific embeddings
- `>0/10` success → fixes are effective, RDT is producing useful actions
- `0/10` and still random motion → recheck `[FIX5b]` prints (were they falling back to bypass?) and verify FK computation

- [ ] **Step 6.3: Check qualitative behavior in episode videos**

```bash
ls outputs/libero/$(ls -t outputs/libero/ | head -1)/episode_1/
```

Watch `episode_1_fail_agentview.mp4` (or success video). Look for:
- **Good sign**: arm moves toward objects, makes grasping attempts, even if clumsy
- **Bad sign**: random oscillation, arm thrashes, stays in place

If behavior is coherent but success rate is 0, the FK conversion is working — the model is producing plausible motion for a ManiSkill task, but there is still a distribution gap between ManiSkill and LIBERO tasks. This is expected and would require fine-tuning to fix fully.

- [ ] **Step 6.4: Regression check — verify `pi05` policy still works**

```bash
cd /home/hynx/VLA-Pilot++ && python main.py \
  env=libero \
  policy.type=pi05 \
  main.use_guidance=false \
  main.episode_num=3 \
  main.sample_batch_size=1 \
  main.render=false 2>&1 | tail -5
```

Expected: pi05 runs without error and shows success rate > 0 (its prior baseline). If it errors, the RDT changes broke something shared — investigate immediately.

- [ ] **Step 6.5: Final commit**

```bash
git add core/rdt_obs_processor.py core/rdt_policy_steer.py
git commit -m "fix: remove diagnostic prints; RDT-LIBERO integration complete"
```

---

## Self-Review Checklist

**Spec coverage (from `docs/analysis.md`):**

| Issue from analysis | Task that fixes it |
|---|---|
| Weight file path resolution may yield None | Task 2 |
| Zero language embedding (silent except) | Task 3 |
| Proprioceptive EEF pose fed as joint angles | Task 4 |
| `_predict_unguided` goes through `_unformat_action_to_joint` → out-of-range actions | Task 5a |
| Gripper dimension missing from LIBERO action | Task 5a (postprocess fix) |
| Actions semantically wrong (joint space ≠ EEF delta) | Task 5b |
| Camera slot mismatch (real wrist images in slots 1/4 that were always None in training; `_BLACK_PIL` bypasses model's background substitution) | Task 4.5 |

**Placeholder scan:** No TBD/TODO/placeholder in any code block. All methods are complete.

**Type consistency:**
- `proprio` in `RDTObsProcessor.process()` returns `torch.Tensor (1, 8)` → consumed by `_rdt_model.encode_inputs(proprio, ...)` → `joints = proprio.to(device).unsqueeze(0)` → shape `(1, 1, 8)` ✓
- `_postprocess_actions(actions: Tensor)` receives `(B, 64, 8)` from both `_predict_unguided` (Task 5a) and `_guided_denoise_loop` (unchanged) ✓
- `rdt_chunk_to_libero_actions(chunk_np, current_joints)`: chunk_np is `(H, 8)` numpy float32; current_joints is `(7,)` from `get_joint_positions()` ✓
- `rdt_action_converter` tests import `franka_fk_pose`, `denormalize_rdt_joints`, `rdt_chunk_to_libero_actions` — all defined in the same file ✓
- `_fallback_proprio_from_state` is defined as a method on `RDTObsProcessor` and called from `process()` ✓
