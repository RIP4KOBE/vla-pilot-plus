---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: feat/rdt-libero-gt-rollout-reintegration
source_commit: 360a6d052861
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/docs/docs/02_analysis/rdt_intergration/libero/2026-04-30-rdt-libero-failure-analysis.md
summary: RDT-1B LIBERO Integration — Failure Analysis
duplicate_sources:
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/docs/02_analysis/rdt_intergration/libero/2026-04-30-rdt-libero-failure-analysis.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/docs/docs/02_analysis/rdt_intergration/libero/2026-04-30-rdt-libero-failure-analysis.md
  - .worktrees/feat/rdt-libero-gt-rollout-integration/docs/superpowers/analysis/2026-04-30-rdt-libero-failure-analysis.md
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/superpowers/analysis/2026-04-30-rdt-libero-failure-analysis.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/docs/superpowers/analysis/2026-04-30-rdt-libero-failure-analysis.md
---

# RDT-1B LIBERO Integration — Failure Analysis

**Date:** 2026-04-30
**Branch:** `feat/rdt-integration`
**Symptom:** 0/10 success on LIBERO; robot motion appears random and task-unrelated.
**Prior debugging:** Proprio fixed (EEF→joint angles), FK converter added, wrist cameras set to `None`.

---

## 1. Intended Architecture (Summary)

The integration wraps `RoboticDiffusionTransformerModel` (a plain Python object from `scripts/maniskill_model.py`) in two thin layers:

- `_RDTModelAdapter` — gives it a `nn.Module`-compatible interface and exposes `encode_inputs()` / `dit` / `noise_scheduler`.
- `RDTSteer` — duck-typed VLS interface (`select_action`, `post_init`, `reset`, …).

**Data flow:**

```
get_policy_observation()          # LIBERO adapter
        │  {images (B,C,H,W), state (B,8), task [str]}
        │  (identity preprocessor — no LeRobot processing)
        │
RDTObsProcessor.process()
  ├─ static cam tensor → PIL resize 384×384 (ring-buffer for t-1)
  ├─ wrist slots → None  (ManiSkill trained on cam_high only)
  ├─ get_joint_positions() → 8D proprio [7 joints + gripper]
  └─ get_lang_embed() → T5-XXL embedding (md5-keyed cache)
        │
_predict_unguided()
  ├─ encode_inputs(): images → SigLIP, proprio → _format_joint_to_state (128D),
  │                   language → already-encoded tensor
  ├─ x_t = randn(B, 64, raw_action_dim=8)
  └─ denoising loop: _RDTDiTAdapter.forward(x_t, t, cond) × N steps
        │  (B, 64, 8) normalized ∈ [-1, 1]
        │
_postprocess_actions()
  ├─ particle 0: (64, 8) → slice [:H, :]
  └─ rdt_chunk_to_libero_actions():
       denormalize joints → Franka FK → EEF Δ → OSC scale → (H, 7)
        │
adapter.step(action[0][step_idx])    # 7D OSC action to LIBERO
```

**Key confirmed fact:** RDT-ManiSkill outputs **absolute Franka joint angles** (7 joints + gripper_open), not delta EEF. The design spec's "6D delta EEF + gripper" description was inaccurate. The FK-based converter is conceptually appropriate for this output format.

---

## 2. Failure Symptom Interpretation

**Symptom:** 0/10 success, motion is random and task-unrelated across all episodes.

"Random / task-unrelated in every episode" strongly implies one of two mechanisms — and typically the simplest one:

| Hypothesis | Why it matches "random in every episode" | Why domain gap alone doesn't |
|---|---|---|
| Denoising loop operates out-of-distribution | DiT produces approximately prior-level noise for every input → no task structure in output | Domain gap degrades quality, not task-relevance |
| Language conditioning = zeros | Model receives no language signal → uniform prior over actions → no task structure | Same as above |
| Image conditioning broken (flip) | Visual features meaningless → partial conditioning loss | Produces wrong-direction motions, not random ones |
| Action-space conversion wrong | Wrong controller inputs even if denoising is correct | Would produce structured but wrong motions |

A model trained on pick-and-place tasks should produce at least *plausible robot movements* (even if wrong task) unless its conditioning signal is corrupted or the noise it is denoising is out-of-distribution. "Completely random" points at the conditioning or the loop structure, not just the domain.

**Ranked by probability:**

1. Custom denoising loop operates on 8D noise (out-of-distribution for the 128D-trained DiT) — **Critical**
2. Language embeddings silently fall back to zeros — **Critical**
3. Input images are upside-down from `LiberoProcessorStep` — **High**
4. FK scaling constants wrong → saturated actions — **Medium**
5. Checkpoint/domain gap — **Low for this specific symptom**

---

## 3. Root-Cause Analysis by Module

### A. Checkpoint / Task / Domain Compatibility

**Failure mode:** ManiSkill checkpoint trained in SAPIEN/Isaac-Gym on pick-and-place tasks. LIBERO uses MuJoCo with different visual appearance, table layout, and object geometry.

**Why it could look random:** It cannot by itself cause *completely* random motion. The model has absorbed task structure. Domain gap degrades precision and generalization, but the robot should still move toward plausible targets.

**Evidence to collect:** After fixing the denoising loop (bug #1 below), does the robot at least move toward a relevant region of the scene, even if it fails? If yes: domain gap is the ceiling, not a random-motion cause.

**Priority: Medium.** Caps success rate at low values; not the cause of the observed randomness.

---

### B. RDT Model Loading Path

**Failure mode:** The HF path `robotics-diffusion-transformer/maniskill-model/rdt` is split into `repo_id=.../maniskill-model` and `subdir=rdt`. `snapshot_download` uses `allow_patterns=["rdt/**", "rdt/*"]`. If `lang_embeds/` lives at the **repo root** (not inside `rdt/`), it is excluded from the download.

**Effect:** `lang_dir = Path(pretrained_path) / "lang_embeds"` does not exist → `_obs_processor` not initialized in `from_pretrained` → `post_init` creates a fresh one without preloaded embeddings. Not fatal: T5 will be computed on demand. However, if the config YAML or weight file is also at the repo root, loading would fail entirely.

**Additional risk:** `action_chunk_size` in the loaded config must equal the hardcoded `64` in the denoising loops. Verify with: `log.info(f"pred_horizon={real.policy.pred_horizon}")` after model load.

**Priority: Low-Medium.** Doesn't directly cause random actions, but worth verifying.

---

### C. Observation Processing (`RDTObsProcessor`)

#### C1 — Image orientation (HIGH RISK)

`LiberoProcessorStep._process_observation` (in `third_party/lerobot/`) flips all images 180°:
```python
img = torch.flip(img, dims=[2, 3])  # flip both H and W
```

This runs inside `get_policy_observation()` **before** the observation reaches `RDTSteer`. The RDT model's `encode_inputs` therefore receives upside-down images. The ManiSkill SigLIP encoder was not trained on inverted images.

**Why it produces task-irrelevance:** Visual conditioning is severely degraded — the model cannot identify relevant objects or spatial relationships. This doesn't produce completely random motion (language still guides somewhat), but it is a strong contributing factor.

**Evidence:** Save `ext_now` from `RDTObsProcessor.process()` as a PNG and visually inspect. If the table is at the top and the sky/ceiling is at the bottom, the flip is happening.

**Priority: High.** Independent of the denoising bug.

#### C2 — Wrist camera slots

Already fixed (pass `None` → SigLIP background substitute, matching training). Not a current issue.

#### C3 — Proprio format

`get_joint_positions()` returns 8D `[q0...q6, gripper]` in radians. `_fallback_proprio_from_state` uses `observation.state` which is EEF-pose based (8D: `[pos(3), axisangle(3), gripper_qpos(2)]`). If `get_joint_positions()` fails silently (exception caught), the fallback feeds EEF-pose data into joint-angle slots → garbage conditioning.

**Evidence:** Log `proprio_np` on first step. Joint angles should be in `[-3.0, 3.0]` rad. EEF position values would be in `[0.0, 1.0]` meters.

**Priority: Medium.** Likely working correctly, but worth a one-line log.

---

### D. Language Conditioning Path

#### D1 — Cache key mismatch (confirmed, minor impact)

`load_embedded_tasks` stores embeddings keyed by `pt_file.stem` (e.g., `"pick_up_block"`).
`get_lang_embed` looks up by `hashlib.md5(task_str.encode()).hexdigest()` (e.g., `"a3f2c1..."`).

**These keys never match.** Preloaded embeddings from the checkpoint's `lang_embeds/` directory are silently ignored on every call. The code always falls through to `_text_encoder_fn` or the zero fallback.

This is a confirmed bug in `core/rdt_obs_processor.py:82`. Not immediately fatal if `_text_encoder_fn` works, but the preloaded embeddings are wasted.

#### D2 — Zero embedding fallback (CRITICAL)

```python
# core/rdt_obs_processor.py:93–97
except Exception:
    logging.getLogger("RDTObsProcessor").warning(
        "T5-XXL unavailable — using zero embedding for: %r", task_str)
    self._lang_cache[key] = torch.zeros(1, 1, 4096)
```

If `_text_encoder_fn` raises **for any reason**, the model receives a zero tensor as its language conditioning. A zero embedding completely removes task information — the model cannot distinguish between different task instructions. This produces uniform-prior behavior that appears random across all episodes.

**Failure path:** `_enc_fn` (wired in `post_init`) calls `real.encode_instruction(s, device=_enc_device)` where `_enc_device = str(real.device)` captured at construction time. If `real.text_model` is on CPU but `_enc_device = "cuda"`, or if a tensor dtype/shape mismatch occurs inside T5 encoding, the exception is silently swallowed.

**The warning is only shown once** (first call), then every subsequent call returns the cached zeros without warning.

**Evidence to collect:** Immediately:
```python
# In _predict_unguided, after text_embed = ...:
log.info(f"text_embed: shape={text_embed.shape} norm={text_embed.norm():.4f}")
```
A norm ≈ 0 confirms the zero fallback is active.

**Priority: Critical.** Zero language conditioning → completely task-unrelated behavior in all episodes.

---

### E. Inference / Denoising Loop

**This is the highest-priority bug, confirmed by direct source comparison.**

#### E1 — x_t dimensionality mismatch (CRITICAL)

**Official `rdt_runner.py:conditional_sample` (lines 135–137):**
```python
noisy_action = torch.randn(
    size=(state_traj.shape[0], self.pred_horizon, self.action_dim), ...)
# action_dim = 128  ← the full unified action space
```

The official denoising loop operates on a **128D noise tensor** throughout all steps. The `action_mask` (which zeros out the 120 inactive dimensions) is applied **only at the very end**:
```python
# Line 160 — AFTER the loop:
noisy_action = noisy_action * action_mask
```

**Custom `_predict_unguided` (core/rdt_policy_steer.py:663–679):**
```python
raw_action_dim = len(cond["action_indices"])  # = 8  (MANISKILL_INDICES has 8 entries)
x_t = torch.randn(B, 64, raw_action_dim, ...)  # (B, 64, 8)
```

Then `_RDTDiTAdapter.forward()` inflates x_t to 128D:
```python
x_unified = torch.zeros(B, H, unified_dim, ...)  # (B, 64, 128) — 120 dims are ZERO
x_unified[:, :, action_indices] = x_t           # fill 8 positions with noise
action_traj = torch.cat([x_unified, action_mask_full], dim=2)  # (B, 64, 256)
```

**The mismatch:** The DiT was trained to denoise tensors where ALL 128 action dimensions contain Gaussian noise at step 0, converging to a valid trajectory. The custom loop feeds a tensor where **120 of the 128 action dimensions are permanently zero throughout every denoising step** — not Gaussian noise, not converging to anything.

The DiT's self-attention couples all 128 dimensions. Having 120 zero-valued positions instead of noisy ones creates a completely different attention pattern from training. The model cannot correctly denoise the 8 active dimensions under this condition. The predicted noise for those 8 positions is approximately drawn from the prior (unstructured) rather than the posterior conditioned on the task.

**This is sufficient by itself to produce 0/10 success with actions that appear random.**

The fix is straightforward: initialize `x_t = torch.randn(B, 64, 128)` (full unified space), apply the mask at the end of the loop, then extract the 8 active dimensions when projecting back to joint space.

#### E2 — Final action masking not applied

The official loop ends with `noisy_action = noisy_action * action_mask`. The custom loop does not apply this. After the loop, the 128D x_t has values in all 120 inactive dimensions (whatever the DiT predicted there, possibly garbage). The projection `model_output_128[:, :, action_indices][:, :, :raw_action_dim]` in `_RDTDiTAdapter.forward()` extracts only the 8 active dimensions, so the inactive dimensions don't directly corrupt the final output — but they do corrupt it *through the self-attention during denoising*.

#### E3 — `state_tokens` construction is correct (verified)

`predict_action` (line 237) does: `state_tokens = torch.cat([state_tokens, action_mask], dim=2)` before calling `adapt_conditions`. Our `encode_inputs` does the equivalent:
```python
state_tokens = torch.cat([states, state_elem_mask.unsqueeze(1)], dim=2)
```
where `state_elem_mask.unsqueeze(1)` == `action_mask`. This is correct.

**Priority: Critical. This is the primary root cause.**

---

### F. Action Extraction and Environment Control

#### F1 — Output action space is absolute joint angles (verified correct)

`MANISKILL_INDICES` in `maniskill_model.py`:
```python
MANISKILL_INDICES = [
    STATE_VEC_IDX_MAPPING[f"right_arm_joint_{i}_pos"] for i in range(7)
] + [STATE_VEC_IDX_MAPPING["right_gripper_open"]]
```

The model outputs **absolute Franka joint angles** (7 dims in rad, 1 gripper_open). The FK-based conversion in `rdt_action_converter.py` is the right approach.

#### F2 — DATA_STAT values match (verified correct)

Comparing `rdt_action_converter.py:RDT_ACTION_MIN/MAX` with `maniskill_model.py:DATA_STAT`:
```
Converter: [-0.7472, -0.0863, -0.4995, -2.6584, -0.5751,  1.8291, -2.2452]
Real model: [-0.7472, -0.0863, -0.4995, -2.6584, -0.5751,  1.8291, -2.2452]  ✓
```
Match to 4+ significant figures. Denormalization is correct.

#### F3 — FK scaling constants (needs verification)

`_POS_SCALE = 0.05` m/unit and `_ORI_SCALE = 0.5` rad/unit are hardcoded assumptions about LIBERO's OSC controller gain. If LIBERO's actual `kp` values differ, FK-derived deltas would be over- or under-scaled:
- Too large: every action clips to `±1` → robot thrashes
- Too small: robot barely moves → appears frozen

**Evidence:** Log `libero_actions[0]` (first H steps) from `rdt_chunk_to_libero_actions`. If the position columns (dims 0–2) are all `±1.0`, scaling is too large.

#### F4 — Gripper sign convention

`action_gripper = float(-gripper[i])` assumes LIBERO convention is `+1=close, -1=open` (robosuite standard). RDT's `gripper_open` is `+1=open`. Negation is correct for the standard convention.

**Priority: Medium overall.** FK approach is correct; scaling constants need empirical verification.

---

### G. `main.py` / Pipeline Wiring

**No bugs found.**

- `_postprocess_actions` returns `(1, H, 7)`. `action_chunk[0][action_executed]` gives `(7,)`. Correct.
- `env_postprocessor` is empty (no-op) and applied twice (main.py + adapter.step). No effect.
- `generate_new_chunk = (action_executed == 0)` correctly triggers new denoising on chunk boundaries.

---

### H. Guidance / FKD Side Effects

Guidance is disabled (`use_guidance=False`) in the failing experiments. The `_predict_unguided` path is entirely independent of FKD and gradient hooks. Guidance bugs cannot cause the observed unguided failure. This module is **not applicable** for current diagnostics.

---

## 4. Top 5 Most Likely Root Causes

### #1 — Denoising loop uses 8D noise instead of 128D noise

**Files:** `core/rdt_policy_steer.py:663–679` (`_predict_unguided`), `core/rdt_policy_steer.py:100–127` (`_RDTDiTAdapter.forward`).

**Why it is likely:** Confirmed by direct source comparison with `rdt_runner.py:conditional_sample`. The model expects 128D Gaussian noise as input throughout the denoising loop. Feeding 8D noise zero-padded to 128D creates an out-of-distribution input pattern that the DiT cannot correctly denoise. Produces near-random output in all cases.

**Quick evidence:** Compare `real._real.step(proprio, images, text_embed)` (official path) output structure to `_predict_unguided` output. If official path produces structured joint trajectories and custom path produces noisy/flat ones, this is the bug.

---

### #2 — Language embeddings silently fall back to zeros

**Files:** `core/rdt_obs_processor.py:77–98`, `core/rdt_policy_steer.py:531–549`.

**Why it is likely:** `except Exception` silently replaces T5 embedding with zeros on any encoder failure. Cache key mismatch (md5 vs stem) means preloaded embeddings are always missed. If T5 encoding fails (device mismatch, shape error, memory), all 10 episodes get zero language conditioning.

**Quick evidence:** Log `text_embed.norm()` after `get_lang_embed`. Zero norm confirms this is active.

---

### #3 — Input images are upside-down from LiberoProcessorStep

**Files:** `third_party/lerobot/src/lerobot/processor/env_processor.py:58–61`, `core/rdt_obs_processor.py`.

**Why it is likely:** `LiberoProcessorStep` flips images 180° before they reach `RDTObsProcessor`. ManiSkill checkpoint was not trained on inverted images. Visual conditioning would be severely degraded.

**Quick evidence:** Save one PIL image from `images[3]` (the `ext_now` slot) inside `encode_inputs` and visually inspect. Upside-down table confirms the bug.

---

### #4 — FK OSC scaling constants don't match LIBERO's controller

**Files:** `core/rdt_action_converter.py:44–45`.

**Why it is likely:** `_POS_SCALE` and `_ORI_SCALE` are empirical guesses. Mismatched scaling causes either frozen robot (too small) or thrashing/clipping behavior (too large). Neither produces task success.

**Quick evidence:** Log raw `libero_actions` from `rdt_chunk_to_libero_actions`. Saturated `±1` in position dims → scale too large. Near-zero values across all steps → scale too small.

---

### #5 — Checkpoint / domain gap (acknowledged)

**Why it is likely:** Even with a perfect integration, ManiSkill (SAPIEN) → LIBERO (MuJoCo) is a substantial zero-shot transfer. Different objects, visual scene, table layout, and background. This caps performance but does not cause completely random motion once the integration bugs are fixed.

---

## 5. Debugging Checklist in Execution Order

### Must-Check Before More Experiments

#### Check 1 — Language embedding is non-zero

**What to inspect:**
```python
# In _predict_unguided, after the text_embed line:
log.info(f"text_embed: shape={text_embed.shape} norm={text_embed.norm():.4f} max={text_embed.abs().max():.4f}")
```

**Expected:** `shape=(1, seq_len, 4096)`, `norm > 10`, `max > 0.1`.

**Failure signature:** `norm ≈ 0.0`, or `shape=(1, 1, 4096)` with `seq_len=1`.

**Conclusion:** If near-zero → zero fallback is active. Fix the `_enc_fn` device handling and remove the silent `except Exception` (replace with explicit error logging + re-raise). After fix, rerun.

---

#### Check 2 — Compare official `step()` vs custom loop on one observation

**What to inspect:** Freeze one observation. Call both:
```python
# (a) Official path
official_out = real._real.step(proprio, images, text_embed)  # (1, 64, 8) after _unformat
# (b) Custom path
custom_out = steer._predict_unguided(proprio, images, text_embed, B=1)  # (1, 64, 8) normalized
```
Log per-dimension mean and std across the 64 timesteps for both.

**Expected:** Official path: structured variation across timesteps (joints smoothly change), low std in the first 20 steps (slow movement). Custom path should produce a similar distribution after fixing the 128D noise bug.

**Failure signature:** Official path has structured temporal profiles; custom path has random-looking flat spectra (each timestep independent of neighbors), or very similar std across all 64 timesteps (no denoising happening).

**Conclusion:** If they diverge → denoising loop bug confirmed. The fix is in `_predict_unguided` and `_RDTDiTAdapter.forward`.

---

#### Check 3 — Inspect input image orientation

**What to inspect:** In `_RDTModelAdapter.encode_inputs`, before the image encoding loop:
```python
if images[3] is not None:
    images[3].save("/tmp/rdt_debug_ext_now.png")
```
Open the PNG.

**Expected:** Normal tabletop scene — table surface at bottom half, robot arm visible from an overhead or angled third-person view.

**Failure signature:** Image is upside-down — table at top, robot arm pointing down from the top.

**Conclusion:** If upside-down → `LiberoProcessorStep` flip must be undone before images reach RDT. Options: (a) apply a reverse flip in `_tensor_to_pil`, or (b) bypass `env_preprocessor`'s image flip for the `rdt` policy type by not calling `LiberoProcessorStep` when `policy.type=rdt`.

---

#### Check 4 — Raw LIBERO action values are in valid range

**What to inspect:** In `rdt_action_converter.py:rdt_chunk_to_libero_actions`, before returning:
```python
print(f"FK actions[0]: pos={libero_actions[0, :3]} ori={libero_actions[0, 3:6]} grip={libero_actions[0, 6]:.3f}")
print(f"pos magnitudes: {np.abs(libero_actions[:, :3]).mean():.4f}")
```

**Expected:** Position deltas small (mean magnitude `< 0.5`), not all clipped at `±1`. Gripper value changes slowly.

**Failure signature:** All position columns at `±1.0` (clipped) → scale too large. All near `0.0` → scale too small or FK producing no delta. NaN/Inf → numerical issue in FK.

**Conclusion:** If saturated → adjust `_POS_SCALE` and `_ORI_SCALE`. If NaN → check `_rot_to_axisangle` for degenerate rotation matrices.

---

#### Check 5 — Proprio joint angles are in expected range

**What to inspect:** In `RDTObsProcessor.process()`, after building `proprio_np`:
```python
log.info(f"proprio: {proprio_np}")
```

**Expected:** First 7 values in `[-3.0, 3.0]` rad (Franka limits), changing by `< 0.1 rad` between steps. 8th value (gripper) in `[0, 0.04]`.

**Failure signature:** Values in `[0, 1]` meters (EEF position range) or all zeros → fallback to `observation.state` (EEF-based) is being triggered.

**Conclusion:** If EEF-like → `get_joint_positions()` is failing silently or returning wrong values. Check the robosuite `robot._joint_positions` accessor.

---

### Secondary Checks

#### Check 6 — `action_indices` are the 8 MANISKILL_INDICES

```python
log.info(f"action_indices: {cond['action_indices']}")
```
Expected: 8 integers in `[0, 127]`, stable across calls.

---

#### Check 7 — Instruction change changes action trajectory

Run two episodes with completely different task strings, same initial state, same random seed. Log `_predict_unguided` output for both.

**Expected:** Outputs differ across the 64-step horizon.
**Failure signature:** Outputs identical (or correlated) → language conditioning not reaching the model.

---

#### Check 8 — `_enc_fn` can be called in isolation

After `post_init`, immediately call:
```python
test_embed = obs_proc._text_encoder_fn("pick up the red block")
log.info(f"T5 test: shape={test_embed.shape} norm={test_embed.norm():.4f}")
```
Expected: `shape=(1, seq_len, 4096)`, `norm > 5`.

---

## 6. Minimal Evidence Package

### Must Collect

| # | Evidence | How to collect | What it proves |
|---|---|---|---|
| 1 | `text_embed.norm()` and shape | One log line in `_predict_unguided` | Whether language conditioning is active or zero |
| 2 | Official `step()` vs custom loop output comparison | Freeze one obs; call both; log temporal stats | Whether denoising loop is the primary bug |
| 3 | One saved input image | `images[3].save("/tmp/rdt_debug.png")` in `encode_inputs` | Whether images are upside-down |
| 4 | First 5 raw LIBERO actions from `rdt_chunk_to_libero_actions` | Log in action converter | Whether OSC values are in range or saturated |
| 5 | `proprio_np` on first step | One log line in `process()` | Whether joint angles are in radian range |

### Nice to Have

| # | Evidence | Value |
|---|---|---|
| 6 | Does changing instruction change the output? | Confirms language conditioning end-to-end |
| 7 | Swapping `ext_prev` ↔ `ext_now` — does it change output? | Tests temporal slot sensitivity |
| 8 | `real.policy.pred_horizon` value after model load | Confirms 64 is the right horizon to hardcode |
| 9 | `_enc_fn` test call result (Check 8 above) | Confirms T5 wiring is working before running full episode |
| 10 | FK delta magnitudes (`delta_pos` in meters before scaling) | Helps calibrate `_POS_SCALE` |

---

## 7. Decision Tree

```
Is text_embed.norm() ≈ 0?
│
├── YES → Language conditioning is broken.
│         Check: does _enc_fn raise? (add explicit try/except logging)
│         Fix: ensure real.text_model is on CUDA before encode_instruction is called.
│         After fix: if still 0/10, continue below.
│
└── NO →
     Does official step() produce structured (temporally coherent) output?
     │
     ├── NO → Model not loaded correctly.
     │         Check: weight_file path, config_path, _unformat_action_to_joint output.
     │         Fix: verify checkpoint structure matches expectations.
     │
     └── YES →
          Does custom _predict_unguided produce similar output to official step()?
          │
          ├── NO (custom is random/unstructured) → Denoising loop is the primary bug.
          │         Fix: initialize x_t as (B, 64, 128) full Gaussian noise.
          │               Extract 8D only after loop: x_t[:, :, action_indices].
          │               Apply action_mask at end of loop.
          │         After fix: rerun experiments.
          │
          └── YES →
               Are input images upside-down?
               │
               ├── YES → Image flip bug from LiberoProcessorStep.
               │         Fix: reverse flip in _tensor_to_pil, or bypass LiberoProcessorStep
               │               image flip when policy.type=rdt.
               │
               └── NO →
                    Are raw LIBERO actions saturated at ±1?
                    │
                    ├── YES → OSC scaling constants are too large.
                    │         Fix: reduce _POS_SCALE (try 0.01–0.03) and/or _ORI_SCALE.
                    │
                    └── NO →
                         Run 10 episodes. If still 0/10 with plausible-looking motion:
                         → Primary limitation is checkpoint/domain gap.
                           Steering and guidance delta is the research metric.
                           Consider RDT fine-tuning on LIBERO demonstrations.
```

---

## 8. Final Diagnosis Summary

### Most probable failure mechanism

The custom denoising loop (`_predict_unguided`, `_guided_denoise_loop`) initializes noise in the 8D action subspace `(B, 64, 8)` and inflates to the 128D unified space by zero-padding the 120 inactive dimensions. The RDT DiT was trained on—and `conditional_sample` uses—full 128D Gaussian noise at step 0, with the action mask applied **only at the end** of the loop. The self-attention in the DiT couples all 128 dimensions at every step. Feeding it a tensor where 120 of 128 action dimensions are permanently zero (not noisy) throughout every denoising step creates an out-of-distribution input pattern the model has never seen during training. The result is that the model cannot correctly denoise the 8 active dimensions, producing outputs approximately drawn from the prior rather than the posterior conditioned on the task — manifesting as random-looking actions across all episodes.

**Source confirmation:** `rdt_runner.py:135–137` (official `conditional_sample`) clearly initializes `noisy_action = torch.randn(..., self.action_dim)` where `action_dim = 128`, not 8. `rdt_runner.py:52–54` confirms `state_adaptor` uses `in_features = state_token_dim * 2 = 256` (state + mask), which is also why the custom `encode_inputs` state_tokens construction is correct.

A secondary, independent issue is the silent language embedding zero-fallback which would compound the failure even after fixing the denoising loop.

### Most important next 3 debugging actions

1. **Verify language embeddings are non-zero** (1 log line, ~5 minutes): eliminates language conditioning as a confounding variable before deeper investigation.

2. **Compare official `step()` output to custom loop output on one frozen observation** (10–15 minutes): definitively confirms or falsifies the 128D-vs-8D denoising loop bug with zero code changes.

3. **Inspect one input image before SigLIP encoding** (5 minutes): confirms or rules out the LiberoProcessorStep image flip issue, which is an independent bug with significant impact on visual conditioning.

### What NOT to spend time on yet

- Tuning `_POS_SCALE`, `_ORI_SCALE`, or gripper sign conventions — downstream of the denoising bug; cannot be calibrated until the loop produces sensible joint trajectories.
- Steering parameters, FKD configuration, or guidance tuning — unguided inference must produce structured outputs first.
- Replacing the checkpoint or adding fine-tuning data — domain gap is not the cause of completely random motion; it will only become the relevant factor after integration bugs are resolved.
- Rewriting the action converter — the DATA_STAT values are verified correct, the FK approach is conceptually appropriate, and the conversion won't matter until denoising produces valid joint angles.
