---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: feat/rdt-libero-gt-rollout-reintegration
source_commit: 360a6d052861
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/docs/docs/04_plans/2026-04-30-rdt-debugging-plan.md
summary: RDT-1B LIBERO Integration — Debugging Plan
duplicate_sources:
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/docs/04_plans/2026-04-30-rdt-debugging-plan.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/docs/docs/04_plans/2026-04-30-rdt-debugging-plan.md
  - .worktrees/feat/rdt-libero-gt-rollout-integration/docs/superpowers/plans/2026-04-30-rdt-debugging-plan.md
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/superpowers/plans/2026-04-30-rdt-debugging-plan.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/docs/superpowers/plans/2026-04-30-rdt-debugging-plan.md
---

# RDT-1B LIBERO Integration — Debugging Plan

> **For agentic workers:** This is a debugging plan, not a repair plan. Execute Phase 0 → Phase 1 → Phase 2 in order. Do not apply code changes until Phase 3 entry criteria are met. Each phase produces evidence files under `docs/superpowers/evidence/`.

**Input files used:**
- `docs/superpowers/plans/2026-04-22-rdt1b-integration.md` — original integration plan
- `docs/superpowers/analysis/2026-04-30-rdt-libero-failure-analysis.md` — failure analysis (note: lives in `analysis/`, not `plans/`)

**Symptom:** LIBERO success rate 0/10; rollout videos show random, task-unrelated motion.

---

## 1. Debugging Objective

- Determine whether the failure is caused by a denoising loop structural mismatch (8D vs 128D noise), language embedding failure, image preprocessing error, or action scaling error — in that priority order.
- Collect falsifiable evidence for each hypothesis before attempting any code change.
- Establish a reproducible single-episode debug harness to control variance.
- Identify which bugs are present simultaneously vs. which one is sufficient to explain 0/10.
- Define the minimum evidence package that justifies entering repair mode.

---

## 2. Fragile Assumptions in the Current Integration Plan

### A2.1 — Denoising latent dimensionality

**Assumption:** `x_t` can be initialized in the 8D MANISKILL action subspace and inflated to 128D by zero-padding inactive dimensions.

**Where it appears:** `core/rdt_policy_steer.py` — `_predict_unguided` and `_guided_denoise_loop`, where `raw_action_dim = len(cond["action_indices"])` (= 8) is used to initialize `x_t`.

**Why it is fragile:** `RDTRunner.conditional_sample` (the official inference path, `models/rdt_runner.py:135`) initializes `noisy_action = torch.randn(B, pred_horizon, action_dim=128)` — full 128D Gaussian noise throughout all denoising steps. The action mask is applied only at the very end. Feeding 8D noise (zero-padded to 128D) changes the self-attention pattern in the DiT at every denoising step — the model has never seen this distribution during training.

**Evidence needed:** Compare per-dimension mean and variance of the output trajectory from `real._real.step()` (official path) vs `_predict_unguided` (custom path) on the same frozen observation. If they diverge significantly, this assumption is false.

---

### A2.2 — Language embedding cache key convention

**Assumption:** Precomputed embeddings loaded from `lang_embeds/*.pt` via `load_embedded_tasks()` will be found by `get_lang_embed()`.

**Where it appears:** `core/rdt_obs_processor.py:66–98` — `load_embedded_tasks` stores by `pt_file.stem`; `get_lang_embed` looks up by `hashlib.md5(task_str.encode()).hexdigest()`.

**Why it is fragile:** These key namespaces are disjoint. Filename stems (e.g., `"pick_up_block"`) will never equal MD5 hashes (e.g., `"a3f2c1d8"`). Every call misses the cache and falls through to `_text_encoder_fn`, and if that raises, silently stores `torch.zeros(1, 1, 4096)`.

**Evidence needed:** Log `text_embed.norm()` and `text_embed.shape` after `get_lang_embed()` on the first episode step. A norm ≈ 0 confirms the zero-fallback path.

---

### A2.3 — Image orientation reaching the RDT model

**Assumption:** Images in `observation.images.image` / `observation.images.image2` are in normal (non-flipped) orientation when they reach `RDTObsProcessor`.

**Where it appears:** Implied in `core/rdt_obs_processor.py` — `_tensor_to_pil` performs no orientation correction.

**Why it is fragile:** `LiberoProcessorStep._process_observation` (in `third_party/lerobot/`) applies `torch.flip(img, dims=[2, 3])` to all images. This runs inside `get_policy_observation()` before the obs dict reaches `RDTSteer`. The ManiSkill SigLIP encoder was trained on upright images.

**Evidence needed:** Save `images[3]` (the `ext_now` slot) as a PNG from inside `_RDTModelAdapter.encode_inputs()` and inspect visually. If table is at top and robot base is at bottom, the assumption is false.

---

### A2.4 — OSC scaling constants for FK-derived deltas

**Assumption:** `_POS_SCALE = 0.05 m/unit` and `_ORI_SCALE = 0.5 rad/unit` correctly map FK-derived EEF deltas to LIBERO's OSC `[-1, 1]` action range.

**Where it appears:** `core/rdt_action_converter.py:44–45`.

**Why it is fragile:** These are hardcoded empirical guesses. LIBERO's actual OSC controller gain (`kp`) and action scaling may differ. If the scale is too large, every action clips to `±1.0` (robot thrashes). If too small, the robot barely moves.

**Evidence needed:** Log raw `libero_actions[0, :3]` (position deltas before clip) from `rdt_chunk_to_libero_actions`. If all values are at `±1`, scale is too large. If all values are near `0`, scale is too small or FK produces zero deltas.

---

### A2.5 — Proprio input to the RDT model is joint angles, not EEF pose

**Assumption:** `get_joint_positions()` returns actual Franka joint angles in radians suitable for `_format_joint_to_state`.

**Where it appears:** `core/rdt_obs_processor.py:150–159` — the adapter-based proprio path.

**Why it is fragile:** The fallback path (`_fallback_proprio_from_state`) uses `observation.state` which is EEF-pose based (after `LiberoProcessorStep`: `[pos(3), axisangle(3), gripper_qpos(2)]`). If `get_joint_positions()` raises and the fallback silently activates, the model receives EEF-pose values in joint-angle slots.

**Evidence needed:** Log `proprio_np` on the first step. Joint angles should be in `[-3.0, 3.0]` rad. EEF position values would be small floats in meter scale `[0.0, 1.0]`.

---

### A2.6 — `encode_inputs` replicates the pre-loop work of the official `step()`

**Assumption:** `_RDTModelAdapter.encode_inputs()` computes the same conditioning tensors as the pre-loop setup in `maniskill_model.step()`, and `_RDTDiTAdapter.forward()` replicates each denoising step of `RDTRunner.conditional_sample()`.

**Where it appears:** `core/rdt_policy_steer.py:190–288` (`_RDTModelAdapter.encode_inputs`) and `core/rdt_policy_steer.py:66–127` (`_RDTDiTAdapter.forward`).

**Why it is fragile:** The official inference path: (1) concatenates `[states | action_mask]` before passing to `adapt_conditions` (`predict_action:237`), (2) uses `state_adaptor` on `[noisy_action_128D | action_mask]` per step, (3) initializes noise in ALL 128 dimensions. Any divergence from these steps changes the distribution the DiT operates on.

**Evidence needed:** Same as A2.1 — comparing official `step()` output vs custom loop output is the single most informative test.

---

## 3. Root-Cause Hypothesis Ranking

| Priority | Hypothesis | Confirms | Weakens |
|---|---|---|---|
| 1 | Denoising loop uses 8D noise instead of 128D (H1) | Official `step()` output structured; custom loop output flat/random | Both outputs have similar temporal structure |
| 2 | Language embedding falls back to zeros (H2) | `text_embed.norm() ≈ 0`; changing task string doesn't change action | `norm > 10` and actions change with instruction |
| 3 | Input images are upside-down (H3) | Saved image shows inverted table scene | Image is correctly oriented |
| 4 | FK OSC scale wrong (H4) | All position action dims saturated at `±1` | Position dims vary smoothly, not clipped |
| 5 | Checkpoint/domain gap (H5) | Structured but wrong-task motions after fixing H1–H4 | Randomly random even after structural fixes |

**H1 is the single most likely cause of "completely random" motion.** H2 is the only other candidate that alone produces randomness across all episodes. H3–H4 degrade performance but would not produce uniformly random motion.

### H1 — Denoising loop uses 8D noise instead of 128D

**Why it matters:** The RDT DiT was trained to denoise 128D tensors. Feeding it 8D noise zero-padded to 128D creates a completely different input distribution. Self-attention over 120 zero-valued positions produces wrong attention patterns at every step.

**Confirms:** Official `step()` produces temporally structured joint trajectory; custom `_predict_unguided` produces high-variance, temporally unstructured output on the same input.

**Weakens:** Custom loop output has similar temporal structure and magnitude to official `step()` output.

---

### H2 — Language embedding falls back to zeros

**Why it matters:** Zero embedding removes all task-specific conditioning. Model produces prior-level distribution: plausible robot motions but completely task-unrelated across all episodes.

**Confirms:** `text_embed.norm() ≈ 0` in logs; two episodes with different instructions produce identical action trajectories.

**Weakens:** `norm > 10`; changing instruction produces different action output.

---

### H3 — Input images are upside-down

**Why it matters:** SigLIP encodes spatial features. Inverting the image changes the spatial layout of objects, robot, and table. The model cannot use visual conditioning to identify relevant objects or approach direction.

**Confirms:** Saved `ext_now` PIL image shows inverted scene. After flipping back, robot begins moving toward relevant objects.

**Weakens:** Image is correctly oriented.

---

### H4 — FK OSC scaling constants wrong

**Why it matters:** Even with correct joint angle predictions, wrong scaling means actions are either saturated (robot thrashes) or near-zero (robot frozen).

**Confirms:** Log shows `libero_actions[:, :3]` all at `±1.0`. After scaling adjustment, robot produces small, controlled movements.

**Weakens:** Position delta magnitudes vary within `[-0.8, 0.8]`, no saturation.

---

### H5 — Checkpoint / domain gap

**Why it matters:** ManiSkill (SAPIEN) → LIBERO (MuJoCo) is a large zero-shot transfer. Even with a correct integration, success rate may be low.

**Confirms:** After fixing H1–H4, robot moves toward relevant objects but fails to complete tasks reliably.

**Weakens:** Not applicable as a cause of completely random motion.

---

## 4. Phase-Based Debugging Plan

---

### Phase 0 — Repro and Baseline Control

**Objective:** Establish a deterministic, reproducible single-episode debug harness before adding any instrumentation.

**Concrete tasks:**

1. Confirm the exact command used to produce the 0/10 result (backend, suite, episode_num, guidance settings). Record it.
2. Set `main.episode_num=1` and `main.use_guidance=false` and `main.vls_config.sample_batch_size=1` for all diagnostic runs. This minimizes noise and speeds up iteration.
3. Confirm the conda environment is activated and the checkpoint downloads correctly (or is already cached locally). Log the exact checkpoint path.
4. Run one episode with current code and confirm the failure reproduces. Record: does the robot move at all? Does it move but ignore the task? Does it stay frozen?

**Exact evidence to collect:**
- `evidence/phase0_repro_command.txt` — the exact command and version hashes
- `evidence/phase0_single_episode_behavior.txt` — description of observed robot behavior in one episode

**Expected healthy result:** N/A — Phase 0 is not diagnostic. Success = a reproducible single-episode run that captures the failure.

**Failure signature:** Episode crashes with an exception. If so: fix the crash first (it may be masking the behavioral failure).

**Decision rule:** If a single episode runs without exception and produces random motion → proceed to Phase 1. If it crashes → investigate the exception traceback first.

**Expected output files:**
- `evidence/phase0_repro_command.txt`
- `evidence/phase0_single_episode_behavior.txt`

---

### Phase 1 — Non-Invasive Evidence Collection

**Objective:** Collect logs, saved intermediates, and controlled comparisons without modifying core inference logic. Add `log.info` statements only — no structural code changes.

**IMPORTANT:** In this phase, add only logging. Do not change any logic, data flow, or model calls.

#### Task 1.1 — Log language embedding norm and shape

**Where:** `core/rdt_policy_steer.py` — inside `select_action`, immediately after `text_embed = self._obs_processor.get_lang_embed(task_str, self.device)`.

**What to add:**
```python
log.info(f"[DIAG] text_embed: shape={text_embed.shape} norm={text_embed.norm():.6f} max={text_embed.abs().max():.6f}")
```

**Expected healthy:** `norm > 10`, `max > 0.1`, shape `(1, seq_len, 4096)` with `seq_len > 1`.

**Failure signature:** `norm ≈ 0.0`, `max ≈ 0.0`, shape `(1, 1, 4096)`.

**Evidence file:** `evidence/phase1_lang_embed_log.txt` — captured stdout/stderr from one episode run.

---

#### Task 1.2 — Save one input image to disk

**Where:** `core/rdt_policy_steer.py` or `core/rdt_obs_processor.py` — after `images` is returned from `process()` on the FIRST call only.

**What to add (first-call guard):**
```python
if not hasattr(self, '_debug_img_saved'):
    self._debug_img_saved = True
    images[3].save("/tmp/rdt_debug_ext_now.png")  # index 3 = ext_t (current frame)
    images[0].save("/tmp/rdt_debug_ext_prev.png")  # index 0 = ext_{t-1}
    log.info("[DIAG] Saved debug images to /tmp/rdt_debug_ext_*.png")
```

**Expected healthy:** Table surface at bottom of frame, robot arm visible from overhead/angled view.

**Failure signature:** Table at top, robot arm pointing down from top — 180° inverted.

**Evidence file:** `evidence/phase1_ext_now.png` — copy the saved file here.

---

#### Task 1.3 — Log proprio values on first step

**Where:** `core/rdt_obs_processor.py` — inside `process()`, after `proprio_np` is constructed.

**What to add (first-step guard):**
```python
if not hasattr(self, '_debug_proprio_logged'):
    self._debug_proprio_logged = True
    log.info(f"[DIAG] proprio_np (8D): {proprio_np.tolist()}")
    log.info(f"[DIAG] proprio source: {'adapter joints' if self._adapter is not None and hasattr(self._adapter, 'get_joint_positions') else 'obs.state fallback'}")
```

**Expected healthy:** Values in `[-3.0, 3.0]` radians (joint space). Gripper `[0, 0.04]`. Not EEF-pose values.

**Failure signature:** Values in `[0, 1]` meter scale (EEF position range) or all zeros.

**Evidence file:** Captured in `evidence/phase1_lang_embed_log.txt` (same run output).

---

#### Task 1.4 — Log raw LIBERO action values from FK converter

**Where:** `core/rdt_action_converter.py` — inside `rdt_chunk_to_libero_actions`, just before `return libero_actions`.

**What to add:**
```python
import logging
_log = logging.getLogger("rdt_action_converter")
_log.info(f"[DIAG] libero_actions[0]: pos={libero_actions[0, :3].tolist()} ori={libero_actions[0, 3:6].tolist()} grip={libero_actions[0, 6]:.4f}")
_log.info(f"[DIAG] pos abs mean={abs(libero_actions[:, :3]).mean():.4f} max={abs(libero_actions[:, :3]).max():.4f}")
```

**Expected healthy:** Position columns vary within `[-0.9, 0.9]`, not all at `±1.0`. Mean abs < 0.5.

**Failure signature:** All position columns at `±1.0` (saturation) → scale too large. All near `0.0` → scale too small or FK producing degenerate output.

**Evidence file:** `evidence/phase1_action_values_log.txt` — captured from one episode run.

---

#### Task 1.5 — Compare official `step()` vs custom loop on a single frozen observation

This is the highest-signal diagnostic. It must be run in a separate script, not during a full episode.

**Script location:** `evidence/phase1_loop_comparison.py`

**What the script does (no code — describe only):**
1. Load the RDT model (same as production).
2. Capture one observation from LIBERO (by running 1 step with zero action).
3. Call `real._real.step(proprio, images, text_embed)` — this is the official `RoboticDiffusionTransformerModel.step()` path. It runs `predict_action` → `conditional_sample` internally. Returns denormalized joint trajectory `(1, 64, 8)`.
4. Call `steer._predict_unguided(proprio, images, text_embed, B=1)` — the custom path. Returns normalized `(1, 64, 8)`.
5. For comparison: denormalize the custom output using `_unformat_action_to_joint` to put both in the same space.
6. Log per-dimension: mean, std, and temporal autocorrelation of the 64-step trajectory for both paths.

**Expected healthy (if H1 is FALSE):** Both paths produce similar per-dimension mean and std. Temporal autocorrelation is high (smooth trajectories, not independent steps).

**Failure signature (if H1 is TRUE):** Official `step()` produces structured, autocorrelated joint trajectories. Custom loop produces trajectories with low autocorrelation (each step nearly independent) and high variance relative to mean — characteristic of noisy-prior sampling rather than posterior denoising.

**Evidence file:** `evidence/phase1_loop_comparison_output.txt` — stdout from the comparison script.

---

### Phase 2 — Hypothesis Discrimination

**Objective:** Use the evidence from Phase 1 to determine which root cause(s) are primary, and confirm no false positives.

**Do not perform Phase 2 until all Phase 1 tasks are complete.**

#### Task 2.1 — Interpret H1 (denoising loop)

**Input:** `evidence/phase1_loop_comparison_output.txt`

**Decision:**
- If official `step()` produces structured trajectories AND custom loop produces random-like ones → **H1 confirmed as primary cause.** Proceed to Phase 3.
- If both produce random-like trajectories → **model loading is broken** (H1 not the issue, look at checkpoint loading).
- If both produce structured trajectories → **H1 is NOT the cause.** Check H2 and H3 next.

---

#### Task 2.2 — Interpret H2 (language embedding)

**Input:** `evidence/phase1_lang_embed_log.txt`

**Decision:**
- `norm ≈ 0` → **H2 confirmed.** Even after fixing H1, this must also be fixed.
- `norm > 10` → **H2 rejected.** Language conditioning is working.

**Cross-check:** If H2 is confirmed AND H1 is also confirmed: both bugs are present simultaneously. They must be fixed independently.

---

#### Task 2.3 — Interpret H3 (image orientation)

**Input:** `evidence/phase1_ext_now.png`

**Decision:**
- Image is upside-down → **H3 confirmed.** Note as a required fix alongside H1/H2.
- Image is correctly oriented → **H3 rejected.**

---

#### Task 2.4 — Interpret H4 (action scaling)

**Input:** `evidence/phase1_action_values_log.txt`

**Decision:**
- Position dims saturated at `±1` → **H4 confirmed.** Action scaling is wrong. Quantify: compute the actual `delta_pos` magnitudes (in meters) before the clip in the FK converter to determine the correct scale.
- Dims varying within `(-0.9, 0.9)` → **H4 rejected** for now. (May still need tuning after H1 fix changes action distribution.)

---

#### Task 2.5 — Write hypothesis discrimination summary

After completing Tasks 2.1–2.4, write a hypothesis discrimination summary to:

`evidence/phase2_hypothesis_discrimination.md`

Format:
```
H1 (denoising loop):  [CONFIRMED | REJECTED | UNKNOWN]  — evidence: ...
H2 (lang embedding):  [CONFIRMED | REJECTED | UNKNOWN]  — evidence: ...
H3 (image flip):      [CONFIRMED | REJECTED | UNKNOWN]  — evidence: ...
H4 (FK scale):        [CONFIRMED | REJECTED | UNKNOWN]  — evidence: ...
Primary cause:        [H1 | H2 | H3 | H4 | unknown]
Ready for repair:     [YES | NO]  — missing evidence: ...
```

---

### Phase 3 — Entry Criteria for Repair

**Objective:** Define when it is justified to begin writing code changes. No code changes before these criteria are met.

**All of the following must be true before starting repair:**

1. Phase 1 tasks 1.1–1.4 are complete and logged in `evidence/`.
2. Phase 1 task 1.5 comparison script has been run and output saved.
3. `evidence/phase2_hypothesis_discrimination.md` exists and has at least 3 of 4 hypotheses evaluated as CONFIRMED or REJECTED (not UNKNOWN).
4. The primary root cause is identified — at minimum, H1 status must be determined.
5. If H1 is CONFIRMED: the fix strategy (128D noise initialization) has been reviewed for any downstream shape effects on `_postprocess_actions` and `_rdt_sample_to_trajectory_3d`.
6. If H2 is CONFIRMED: the zero-fallback trigger has been identified (which exception is swallowed) and the fix is scoped.

**If any of these criteria are not met:** Return to Phase 1 or Phase 2 and collect the missing evidence.

---

## 5. Ordered Debugging Checklist

| # | Task | Why now | What to inspect | Healthy signal | Failure signal | Next action | Save to |
|---|---|---|---|---|---|---|---|
| 1 | Repro single episode without guidance | Establish baseline | Run with `episode_num=1 use_guidance=false sample_batch_size=1` | Episode completes, random motion confirmed | Crash/exception | Fix crash; then proceed | `evidence/phase0_repro_command.txt` |
| 2 | Log `text_embed.norm()` | Fastest way to rule out H2 | Add 1 log line, run 1 episode | `norm > 10` | `norm ≈ 0` | If 0: investigate `_enc_fn`; if OK: proceed | `evidence/phase1_lang_embed_log.txt` |
| 3 | Save input image | Rule out H3 before investing in loop comparison | Check image orientation in `/tmp/rdt_debug_ext_now.png` | Upright tabletop scene | Inverted/upside-down | If inverted: note as required fix; proceed to #4 | `evidence/phase1_ext_now.png` |
| 4 | Log proprio values | Confirm the joint-angle path is active | `proprio_np.tolist()` on first step | Values in `[-3.0, 3.0]` rad | Meter-scale EEF values | If EEF: investigate adapter `get_joint_positions()` fallback | `evidence/phase1_lang_embed_log.txt` |
| 5 | Log raw FK action values | Rule out H4 scale saturation | `libero_actions[0, :3]` from converter | Position dims vary, not all `±1` | All position dims at `±1` | If saturated: note scale is wrong; proceed to #6 | `evidence/phase1_action_values_log.txt` |
| 6 | Run official `step()` vs custom loop comparison | Definitive H1 test | Per-dimension stats of 64-step output trajectory for both paths | Both have similar autocorrelated structure | Official structured, custom random | If diverge: H1 confirmed; enter Phase 3 | `evidence/phase1_loop_comparison_output.txt` |
| 7 | Write hypothesis discrimination summary | Consolidate evidence before repair | Review all evidence files | 3+ hypotheses evaluated | Still unknowns | If all clear: proceed to repair plan | `evidence/phase2_hypothesis_discrimination.md` |

---

## 6. Minimal Evidence Package

### Mandatory (must exist before repair)

| Evidence item | File location | Required for |
|---|---|---|
| Language embedding norm on first episode step | `evidence/phase1_lang_embed_log.txt` | Confirm/reject H2 |
| One saved input image (ext_now) | `evidence/phase1_ext_now.png` | Confirm/reject H3 |
| Raw LIBERO action values from FK converter | `evidence/phase1_action_values_log.txt` | Confirm/reject H4 |
| Official step() vs custom loop comparison output | `evidence/phase1_loop_comparison_output.txt` | Confirm/reject H1 |
| Hypothesis discrimination summary | `evidence/phase2_hypothesis_discrimination.md` | Entry criteria for Phase 3 |

### Optional (increases diagnostic confidence)

| Evidence item | File location | Value |
|---|---|---|
| Two episodes with different instructions — do outputs differ? | `evidence/opt_instruction_sensitivity.txt` | Confirms H2 end-to-end |
| `real.policy.pred_horizon` value after model load | `evidence/opt_model_config.txt` | Confirms hardcoded `64` is correct |
| `cond["action_indices"]` values logged | `evidence/opt_action_indices.txt` | Confirms 8D subspace is correct |
| `delta_pos` in meters before clip in FK converter | `evidence/opt_fk_raw_deltas.txt` | Quantifies correct `_POS_SCALE` |

---

## 7. Repair Readiness Criteria

Do not begin the repair plan until all of the following are satisfied:

- [ ] `evidence/phase1_loop_comparison_output.txt` exists and H1 status is determined.
- [ ] `evidence/phase1_lang_embed_log.txt` exists and H2 status is determined.
- [ ] `evidence/phase1_ext_now.png` exists and H3 status is determined.
- [ ] `evidence/phase1_action_values_log.txt` exists and H4 status is determined.
- [ ] `evidence/phase2_hypothesis_discrimination.md` exists and identifies the primary cause.
- [ ] For any CONFIRMED hypothesis: the minimal fix is identified and its scope is bounded (i.e., it does not require touching more than 2 files per hypothesis).

**Trigger phrase:** Once this checklist is complete, run the prompt at:
`docs/superpowers/prompts/rdt_repair_plan_prompt.md`

---

## 8. Risk Controls and Stop-Loss Rules

### What must NOT be changed during evidence collection (Phase 0–2)

- `core/rdt_policy_steer.py` — no logic changes, only `log.info` additions
- `core/rdt_obs_processor.py` — no logic changes, only `log.info` and first-call-guarded saves
- `core/rdt_action_converter.py` — no logic changes, only diagnostic logging
- `configs/policy.yaml` — do not change model path or inference steps
- `main.py` — do not change the policy wiring

### What must NOT be fixed in the same iteration

- Do not fix H1 and H2 simultaneously in one commit. Fix the highest-priority confirmed hypothesis first, run 1 episode to validate, then fix the next.
- Do not adjust `_POS_SCALE`/`_ORI_SCALE` (H4) while the denoising loop (H1) is still wrong — action values will be meaningless until H1 is fixed.
- Do not change the language embedding path (H2 fix) while also changing the image preprocessing (H3 fix) — both affect model conditioning and changes would be confounded.

### When to revert and reassess

- If a fix makes behavior worse (e.g., robot was previously frozen but now thrashes after H4 fix) → revert and reassess the scaling direction.
- If fixing H1 does not improve behavior at all (robot still appears random) → collect new evidence before proceeding. H2 or H3 may be the dominant cause.
- If more than 2 sequential single-hypothesis fixes do not improve behavior → stop automatic execution and request human review.

### When NOT to continue with automatic execution

- If `evidence/phase2_hypothesis_discrimination.md` shows all 4 hypotheses as UNKNOWN → stop. Evidence collection failed. Add more explicit logging and re-run Phase 1.
- If official `step()` itself produces random-looking trajectories → model loading is broken. This is outside the scope of the current debugging plan. Stop and investigate checkpoint loading before proceeding.
- If the episode crashes in Phase 0 with an unhandled exception → fix the crash explicitly before all other diagnostics.

---

## 9. Suggested Next Prompts

### Prompt A — Execute Phase 1 evidence collection

> **Context:** Use this prompt after Phase 0 reproduces the failure.
>
> **Read:**
> - `docs/superpowers/plans/2026-04-30-rdt-debugging-plan.md` (this file) — Phase 1 tasks 1.1–1.5
> - `docs/superpowers/analysis/2026-04-30-rdt-libero-failure-analysis.md` — for module context
> - `core/rdt_policy_steer.py`, `core/rdt_obs_processor.py`, `core/rdt_action_converter.py` — files to add logging to
>
> **Task:** Add non-invasive diagnostic logging as specified in Phase 1. Write the comparison script to `evidence/phase1_loop_comparison.py`. Run the single-episode debug harness and the comparison script. Save all output files to `docs/superpowers/evidence/`.
>
> **Write:**
> - `docs/superpowers/evidence/phase1_lang_embed_log.txt`
> - `docs/superpowers/evidence/phase1_ext_now.png`
> - `docs/superpowers/evidence/phase1_action_values_log.txt`
> - `docs/superpowers/evidence/phase1_loop_comparison_output.txt`
>
> **Constraint:** Add only logging. Do not change any inference logic.
>
> **Save to:** `docs/superpowers/prompts/rdt_phase1_evidence_collection_prompt.md`

---

### Prompt B — Update analysis after evidence collection

> **Context:** Use this prompt after all Phase 1 evidence files exist.
>
> **Read:**
> - `docs/superpowers/analysis/2026-04-30-rdt-libero-failure-analysis.md`
> - All files in `docs/superpowers/evidence/phase1_*.txt` and `phase1_*.png`
>
> **Task:** Write `docs/superpowers/evidence/phase2_hypothesis_discrimination.md` evaluating each hypothesis (H1–H4) as CONFIRMED, REJECTED, or UNKNOWN based on the collected evidence. Identify the primary cause. State whether repair readiness criteria are met.
>
> **Write:**
> - `docs/superpowers/evidence/phase2_hypothesis_discrimination.md`

---

### Prompt C — Generate repair plan after evidence is sufficient

> **Context:** Use this prompt only when `evidence/phase2_hypothesis_discrimination.md` confirms repair readiness criteria are met.
>
> **Read:**
> - `docs/superpowers/plans/2026-04-30-rdt-debugging-plan.md` — section 7 (repair readiness criteria)
> - `docs/superpowers/evidence/phase2_hypothesis_discrimination.md` — confirmed hypotheses
> - `docs/superpowers/analysis/2026-04-30-rdt-libero-failure-analysis.md` — Section 3 per-module analysis
> - `docs/superpowers/plans/2026-04-22-rdt1b-integration.md` — original integration plan for context
> - `core/rdt_policy_steer.py`, `core/rdt_obs_processor.py`, `core/rdt_action_converter.py` — files to repair
>
> **Task:** Write a repair plan that fixes only the CONFIRMED hypotheses, one per task, with a validation step (run 1 episode) after each fix. Do not bundle multiple fixes. Include rollback instructions for each fix.
>
> **Write:**
> - `docs/superpowers/plans/2026-04-30-rdt-repair-plan.md`
>
> **Save to:** `docs/superpowers/prompts/rdt_repair_plan_prompt.md`
