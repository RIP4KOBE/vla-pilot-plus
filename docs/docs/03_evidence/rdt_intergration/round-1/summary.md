# Phase 1 Evidence Collection — Round 1 Summary

**Date:** 2026-04-30  
**Evidence round:** 1  
**Status:** COMPLETE — repair readiness criteria met

---

## 1. Inputs Used

### Plan files
- `docs/superpowers/plans/2026-04-30-rdt-debugging-plan.md` — phase-by-phase task list
- `docs/superpowers/analysis/2026-04-30-rdt-libero-failure-analysis.md` — failure analysis

### Code files read
- `core/rdt_policy_steer.py` — `_predict_unguided`, `_RDTDiTAdapter.forward`, `_postprocess_actions`
- `core/rdt_obs_processor.py` — `process()`, `get_lang_embed()`, `load_embedded_tasks()`
- `core/rdt_action_converter.py` — `rdt_chunk_to_libero_actions`, `denormalize_rdt_joints`
- `third_party/lerobot/src/lerobot/processor/env_processor.py` — `LiberoProcessorStep._process_observation`
- `third_party/rdt/scripts/maniskill_model.py` — `MANISKILL_INDICES`, `DATA_STAT`
- `third_party/rdt/models/rdt_runner.py` — `conditional_sample`, `predict_action`

### Scripts written and run
- `docs/superpowers/evidence/round-1/stats/loop_comparison.py` — run successfully
- `docs/superpowers/evidence/round-1/images/image_check.py` — run successfully

### Checkpoint used
- `/mnt/data/hf_cache/hub/models--robotics-diffusion-transformer--maniskill-model/snapshots/9622afab.../rdt/mp_rank_00_model_states.pt`

---

## 2. Instrumentation Changes

No behavior-changing modifications were made to core inference code during evidence collection. All changes are in standalone scripts under `docs/superpowers/evidence/`.

| Location | Change | Behavior-changing? | Should revert? |
|---|---|---|---|
| `evidence/round-1/stats/loop_comparison.py` | New standalone script | No — separate file | No |
| `evidence/round-1/images/image_check.py` | New standalone script | No — separate file | No |

---

## 3. Evidence Collected

### Task 1 — Frozen repro setup

- Input: Franka home config `q=[0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785, 0.0]`, synthetic black images (384×384), task string "open the top drawer of the cabinet"
- Seed: `torch.manual_seed(42)` for proprio, `torch.manual_seed(7)` for both inference runs
- Model device: cuda
- Artifact: `stats/loop_comparison_output.txt`

### Task 2 — Language embedding evidence

| Metric | Value |
|---|---|
| task_str | "open the top drawer of the cabinet" |
| MD5 key | `43b885011c226fd0134d4078331102fa` |
| embed shape | `(1, 8, 4096)` |
| embed norm | 16.98 |
| is_zero | False |
| second task diff (first token) | 7.45 |

**Interpretation:** H2 REJECTED. T5 embeddings are real and task-specific. Cache miss on first call, then T5 succeeds. The 9 md5-named `.pt` files in `data/rdt_lang_embeds/` confirm prior runs also had real embeddings.

**Hypothesis update:** H2 (language embedding zero fallback) is NOT active in practice.

Artifact: `stats/loop_comparison_output.txt` (TASK 2 section)

---

### Task 3 — Official step() vs custom _predict_unguided() comparison

| Metric | Official `step()` | Custom `_predict_unguided()` |
|---|---|---|
| Output shape | `(1, 64, 8)` | `(1, 64, 8)` |
| Space | Denormalized (joint angles, rad) | Normalized (∈ [-1, 1]) |
| mean abs value | 0.983 | 0.585 |
| std | 1.324 | 0.612 |
| range | [-2.34, 2.59] | [-0.96, 0.61] |
| lag-1 autocorr | **0.9472** | **0.9810** |
| Has NaN/Inf | False | False |
| Mean abs diff (normalized) | — | **0.608** |

**Key finding:**
- **Neither path produces random motion** — both have very high autocorrelation (>0.9).
- The trajectories are smooth and structured but **converge to different joint configurations** (0.61 normalized mean abs diff — large).
- Joint 1: official normalized = -0.66, custom = +0.52 (opposite sign — opposite sides of the joint range).
- The custom path's target configuration is far from the LIBERO start config, causing step-0 saturation in the FK-derived actions.

**Revised H1 interpretation:**

H1 is confirmed, but the mechanism is "biased denoising posterior" not "random noise." The zero-padding of 120 inactive dimensions causes the DiT to converge to a different, wrong joint configuration. The behavior is smooth but wrong.

**Evidence supporting H1:**
- `action_indices: [0, 1, 2, 3, 4, 5, 6, 10]` — confirms 8 active dims out of 128
- `raw_action_dim=8`, `unified_action_dim=128` — confirms 120 dims are zero in custom path
- Mean abs diff 0.608 — confirms wrong joint targets

Artifacts: `stats/loop_comparison_output.txt`, `stats/loop_comparison_trajectories.pt`

---

### Task 4 — Image orientation inspection

**Source trace:** `LiberoProcessorStep._process_observation` in `third_party/lerobot/`:

```python
img = torch.flip(img, dims=[2, 3])  # Flip both H and W
```

- This applies a 180° rotation to all images before they reach `RDTSteer`.
- Confirmed in code — no ambiguity.

**Impact:** The ManiSkill SigLIP encoder was trained on upright SAPIEN images. All LIBERO frames arriving at the RDT model are inverted.

Artifact: `images/flip_test_synthetic.png` (visual demonstration), `images/image_check_notes.txt`

---

### Task 5 — Proprio input evidence

| Metric | Value |
|---|---|
| proprio shape | `(1, 8)` |
| values | `[0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785, 0.0]` |
| range | all ∈ [-3.0, 3.0] |
| interpretation | Valid Franka joint angles in radians + gripper |

No anomaly detected. Proprio path is correct.

---

### Task 6 — Raw action output inspection

| Metric | Value |
|---|---|
| output shape | `(8, 7)` |
| step 0 pos | `[-1.0, -1.0, 0.225]` — **saturated** |
| step 1 pos | `[0.002, 0.015, 0.020]` — tiny |
| step 2 pos | `[-0.060, 0.025, 0.001]` — tiny |
| pos abs mean | 0.120 |
| pos abs max | 1.00 |
| saturated dims | 2/24 (step 0 only) |

**Interpretation:**
- Step-0 saturation is caused by the large FK delta between the LIBERO start config and the wrong predicted config (H1 effect).
- Steps 1-7 have near-zero deltas because the predicted trajectory is nearly constant (high autocorr).
- This produces: one large move → stall → one large move → stall pattern, consistent with "random-looking" behavior.

---

## 4. Updated Root-Cause Ranking

| Rank | Hypothesis | Status | Confidence | Evidence |
|---|---|---|---|---|
| 1 | H1 — Denoising loop produces wrong joint config | **CONFIRMED** | HIGH | mean abs diff 0.608 vs official; joint 1 sign reversed |
| 2 | H3 — Image flip | **CONFIRMED** | HIGH | Source code confirms `torch.flip(dims=[2,3])` in LiberoProcessorStep |
| 3 | H4 — FK scale | MINOR | LOW | Step-0 saturation is secondary to H1 wrong targets |
| 4 | H2 — Language embedding zero | **REJECTED** | HIGH | norm=16.98, two tasks distinct |

**Mechanism chain:**
```
H1: custom x_t init (8D→128D via zero-pad)
  → biased denoising posterior
  → wrong joint config target (0.61 mean abs diff)
  → step-0 FK delta saturated, steps 1-7 near-zero
  → robot makes one wrong big move then stalls

H3: LiberoProcessorStep torch.flip(dims=[2,3])
  → upside-down images reach SigLIP encoder
  → wrong visual conditioning
  → no task-relevant visual signal

Combined effect: robot moves erratically to wrong config, never uses task-relevant workspace
```

---

## 5. Repair Readiness

**YES — repair mode is justified.**

Primary causes are identified with high confidence. No critical unknowns remain.

**Repair order:**

1. **H1 first (highest impact):** Change `_predict_unguided` to initialize `x_t` as full 128D noise, not 8D. Single-line fix.
   - After: run 1 episode to verify action distribution shifts closer to official `step()` output.
   - Check: step-0 saturation should decrease or disappear.

2. **H3 second (after H1 is validated):** Add counter-flip in `RDTObsProcessor._tensor_to_pil` or bypass `LiberoProcessorStep` image flip for the RDT code path.
   - After: save one input image and confirm correct orientation.

3. **H4 after H1+H3:** Re-evaluate `_POS_SCALE` scaling only if saturation persists after H1 fix.

**Do NOT bundle H1 and H3 fixes into a single commit.** Each must be validated independently.

---

## 6. Risks and Ambiguities

| Risk | Description |
|---|---|
| H1 fix scope | Changing `x_t` from `(B, 64, 8)` to `(B, 64, 128)` requires verifying that `_RDTDiTAdapter.forward`'s inflation step handles this correctly. If `x_t.shape[2] == unified_dim`, the inflation becomes a no-op (correct). Verify this explicitly. |
| H3 fix location | The flip is in `LiberoProcessorStep` which also processes `observation.state` (EEF pose). Adding a counter-flip in `RDTObsProcessor` is cleaner than modifying the shared preprocessor. But confirm the counter-flip is only applied to images, not proprio. |
| Action chunk stepping | The main loop may call `select_action` with `generate_new_chunk=True` every step OR every N steps. The near-zero deltas in steps 1-7 are fine for the receding-horizon case (call every step) but wrong for the chunk-replay case. Confirm `generate_new_chunk` logic in `main.py` before evaluating post-fix behavior. |
| Denormalization chain | The custom path returns NORMALIZED output; `rdt_chunk_to_libero_actions` denormalizes internally. The official `step()` returns DENORMALIZED output. These are different API contracts. Confirm that `_postprocess_actions` does NOT additionally denormalize. |

---

## 7. Recommended Next Step

**Proceed to repair planning.**

Run the repair plan prompt at:
`docs/superpowers/prompts/rdt_repair_plan_prompt.md`

Required inputs for the repair plan:
- This file (`evidence/round-1/summary.md`)
- `evidence/round-1/stats/phase2_hypothesis_discrimination.md`
- `core/rdt_policy_steer.py`
- `core/rdt_obs_processor.py`
