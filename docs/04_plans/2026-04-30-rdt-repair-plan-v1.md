---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: feat/rdt-libero-gt-rollout-reintegration
source_commit: 360a6d052861
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/docs/docs/04_plans/2026-04-30-rdt-repair-plan-v1.md
summary: RDT-1B LIBERO Integration — Repair Plan v1
duplicate_sources:
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/docs/04_plans/2026-04-30-rdt-repair-plan-v1.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/docs/docs/04_plans/2026-04-30-rdt-repair-plan-v1.md
  - .worktrees/feat/rdt-libero-gt-rollout-integration/docs/superpowers/plans/2026-04-30-rdt-repair-plan-v1.md
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/superpowers/plans/2026-04-30-rdt-repair-plan-v1.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/docs/superpowers/plans/2026-04-30-rdt-repair-plan-v1.md
---

# RDT-1B LIBERO Integration — Repair Plan v1

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:systematic-debugging` and `superpowers:executing-plans` to implement this plan. Fix H1 only. Do NOT fix H3 in the same session. Do NOT touch `rdt_action_converter.py`, `rdt_obs_processor.py`, or `main.py`. Validate after every step.

**Input files used:**
- `docs/superpowers/analysis/2026-04-30-rdt-libero-failure-analysis.md`
- `docs/superpowers/plans/2026-04-30-rdt-debugging-plan.md`
- `docs/superpowers/evidence/round-1/summary.md`
- `docs/superpowers/evidence/round-1/stats/phase2_hypothesis_discrimination.md`
- `core/rdt_policy_steer.py` (read in full)

**Date:** 2026-04-30
**Status:** Ready for execution

---

## 1. Confirmed Root Cause

**H1 — Denoising loop initializes `x_t` in the 8D action subspace instead of the full 128D unified action space.**

### Why it is sufficiently confirmed

- `loop_comparison.py` ran both the official `real_model.step()` path and the custom `_predict_unguided()` path on an identical frozen input (same model, same weights, same conditioning, same seed).
- **Both paths produce temporally smooth trajectories** (autocorr > 0.94) — confirming this is not a "random noise" failure.
- **However, the two paths converge to different joint configurations** — mean absolute difference in normalized joint space = **0.608** (range is ±1.0).
- Specific example: joint 1 target — official normalized = **-0.660**, custom = **+0.523** (opposite sign, opposite side of joint range).
- Mechanism is directly visible in `_RDTDiTAdapter.forward` (lines 102–127):

  ```
  x_unified = zeros(B, H, 128)        ← 120 dims permanently zero
  x_unified[:, :, action_indices] = x_t[:, :, :8]   ← only 8 dims have noise
  ```

  Versus the official `RDTRunner.conditional_sample`:
  ```
  noisy_action = randn(B, pred_horizon, 128)   ← all 128 dims have Gaussian noise
  ```

- The DiT's self-attention across the 256D `[action | mask]` token at every step processes these 120 zero-valued dims differently than genuine Gaussian noise, biasing the posterior toward a wrong joint configuration.

---

## 2. Why This Should Be Fixed First

| Criterion | Assessment |
|---|---|
| **Expected value** | Highest — biased joint targets are the direct cause of wrong robot motion and step-0 action saturation. Fixing this aligns the custom loop with the certified correct inference path. |
| **Remaining ambiguity** | Lowest — the mechanism is directly observable in two lines of code, confirmed by quantitative comparison against the reference path. |
| **Independence** | This fix does not require changing image preprocessing, language embedding logic, or action conversion. It is self-contained within `rdt_policy_steer.py`. |
| **Observability** | The frozen-sample comparison (`loop_comparison.py`) provides a precise pre/post metric: mean abs diff should drop from 0.608 toward near-zero. |

H3 (image flip) is also confirmed but is secondary in severity: images are upside-down, which degrades visual conditioning, but does not cause the specific wrong-joint-configuration behavior. Fix H1 first to establish a clean baseline with correct joint targets; then fix H3 with a separate validation step.

---

## 3. Minimal Code-Change Scope

**Only `core/rdt_policy_steer.py` needs to change.** Three locations within this single file.

### Location 1 — `_predict_unguided` (line ~663–679)

**What is relevant:** The initialization of `x_t` at line 669:
```python
x_t = torch.randn(B, 64, raw_action_dim, device=device, dtype=dtype)
```
`raw_action_dim = len(cond["action_indices"]) = 8`. This creates an 8D noise tensor.

**What should change:**
- After computing `raw_action_dim`, also extract `unified_action_dim = cond.get("unified_action_dim", raw_action_dim)` and `action_indices = cond.get("action_indices", list(range(raw_action_dim)))`.
- Change the `x_t` initialization to use `unified_action_dim` (128) instead of `raw_action_dim` (8).
- After the denoising loop, project the 128D `x_t` back to the 8D subspace before returning: `x_t[:, :, action_indices][:, :, :raw_action_dim]`.

**What must remain unchanged:** The function signature, `cond = self._rdt_model.encode_inputs(...)` call, the scheduler setup, and the denoising loop body. The return shape must still be `(B, 64, 8)` so that `_postprocess_actions` receives the expected tensor.

**Stub model path guard:** The `if "action_indices" in cond` branch that falls back to `self._rdt_model.step(...)` for stub models must be preserved and still return `(B, 64, raw_action_dim)` as before (stub models do not have `unified_action_dim` in their cond dict).

---

### Location 2 — `_RDTDiTAdapter.forward` (lines ~102–127)

**What is relevant:** The inflation step and the noise_pred projection:

```python
# Inflation (line 104-105):
x_unified = torch.zeros(B, H, unified_dim, device=x_t.device, dtype=x_t.dtype)
x_unified[:, :, action_indices] = x_t[:, :, :len(action_indices)]

# Projection (line 126):
model_output = model_output_128[:, :, action_indices][:, :, :raw_action_dim]
return model_output
```

**What should change:**

Add a dimensionality guard before the inflation step:

```
if raw_action_dim == unified_dim:
    # x_t is already in the full unified action space — no inflation needed.
    x_unified = x_t
else:
    # x_t is in the raw 8D subspace — inflate by zero-padding (backward compat for stubs).
    x_unified = zeros(B, H, unified_dim)
    x_unified[:, :, action_indices] = x_t[:, :, :len(action_indices)]
```

And a matching guard on the noise_pred projection:

```
if raw_action_dim == unified_dim:
    # Return full 128D noise_pred to match the 128D x_t in the denoising loop.
    return model_output_128
else:
    # Project back to 8D for the subspace path (backward compat).
    return model_output_128[:, :, action_indices][:, :, :raw_action_dim]
```

**What must remain unchanged:** All conditioning tensor construction (`lang_cond`, `img_cond`, `state_traj`, `action_mask`, `ctrl_freqs`), the `_b` expand helper, the `state_adaptor` call, and the `runner.model` call. The stub model fast-path at the top of `forward` must remain untouched.

**Why this guard is necessary:** With `x_t` now 128D, the existing code does `x_unified[:, :, action_indices] = x_t[:, :, :8]` — this would copy only the first 8 dims of the 128D tensor into the 8 action slots, discarding dims 8-127 (all still Gaussian noise). The guard ensures 128D `x_t` is passed through directly. Without this guard, the fix in Location 1 is incomplete and would not reproduce the official behavior.

---

### Location 3 — `_guided_denoise_loop` (line ~867)

**What is relevant:** The same `x_t` initialization bug exists here:
```python
x_t = torch.randn(B, 64, raw_action_dim, device=device, dtype=dtype)
```

**What should change:** Same pattern as Location 1 — extract `unified_action_dim` from `cond` and initialize `x_t` with 128 dims. After the loop, project back to 8D before returning.

**When to make this change:** In the same commit as Locations 1 and 2. The `_guided_denoise_loop` has the same root bug. Leaving it unfixed would mean the guided path is still broken while the unguided path is fixed — creating a confusing asymmetry.

**What must remain unchanged:** The guidance hooks (Phase D, A, B), the FKD particle filter logic, the `_compute_diversity_gradient` and `_compute_keypoint_gradient` calls. The gradient operations work on `noise_pred` (which is now 128D) — note that the gradient guidance currently modifies `noise_pred[:, :, :3]` (position dims). These dims correspond to `action_indices[:3] = [0, 1, 2]` which ARE within the first 8 action dims, so the gradient injection still targets the right dims in the 128D noise_pred.

**Caution:** In the guided path, `_rdt_sample_to_trajectory_3d` receives `x_t` and slices `_ARM_JOINTS = slice(0, 7)`. With 128D `x_t`, this slices dims 0-6 which are still the arm joints (action_indices[0:7] = [0,1,2,3,4,5,6]). This is correct — no change needed to the trajectory projection.

---

### Files NOT to touch in this repair iteration

| File | Reason |
|---|---|
| `core/rdt_obs_processor.py` | H3 fix is for a separate commit |
| `core/rdt_action_converter.py` | No change needed; H4 is secondary to H1 |
| `main.py` | No change needed |
| `configs/policy.yaml` | No change needed |
| `tests/test_rdt_steer.py` | Existing tests use stub models with `raw_action_dim = unified_action_dim` — the `else` branch in Location 2 must preserve their behavior |

---

## 4. Step-by-Step Repair Sequence

### Step 1 — Add `unified_action_dim` guard to `_RDTDiTAdapter.forward`

**Intended change:**
- In `_RDTDiTAdapter.forward`, wrap the inflation step and noise_pred projection in the `raw_action_dim == unified_dim` guard described in Location 2.

**Why necessary:** Prerequisite for Location 1 fix. Without this guard, initializing `x_t` as 128D in `_predict_unguided` would incorrectly copy only the first 8 dims back into the action slots.

**Assumptions:**
- `cond["unified_action_dim"]` is always 128 for the real model (confirmed: `unified_action_dim: 128` in loop_comparison output).
- Stub model tests reach the `else` branch (they have empty `cond`, so the early `if not cond: raise RuntimeError` is triggered before reaching this code). No stub model change needed.

**Must not change in this step:** The conditioning tensor construction, `state_adaptor` call, `runner.model` call, stub model guard.

**Immediate verification:** The existing smoke tests (`pytest tests/test_rdt_steer.py -v`) must all still pass. The stub model path is unchanged; the guard only affects the real model path.

**Artifact:** Test run output → `evidence/round-2/step1_smoke_tests.txt`

---

### Step 2 — Change `_predict_unguided` to use 128D noise

**Intended change:**
- After calling `encode_inputs`, extract `unified_action_dim = cond.get("unified_action_dim", raw_action_dim)` and `action_indices = cond.get("action_indices", list(range(raw_action_dim)))`.
- Change `x_t = torch.randn(B, 64, raw_action_dim, ...)` to `x_t = torch.randn(B, 64, unified_action_dim, ...)`.
- After the denoising loop, add the projection: `return x_t[:, :, action_indices][:, :, :raw_action_dim]`.

**Why necessary:** This is the primary fix. The denoising loop must operate in the same 128D space as the official `conditional_sample` to avoid biasing the posterior.

**Assumptions:**
- `_postprocess_actions` expects `(B, 64, 8)` — the projection at the end of `_predict_unguided` ensures this contract is preserved.
- `action_indices = [0, 1, 2, 3, 4, 5, 6, 10]` — the projection `x_t[:, :, action_indices]` yields `(B, 64, 8)`, and `[:, :, :8]` selects all 8. Verified correct in loop_comparison output.
- The `if "action_indices" not in cond` fallback branch (stub model path) can use `raw_action_dim` as `unified_action_dim` (existing behavior preserved).

**Must not change:** The stub model fallback branch (`else: _probe = self._rdt_model.step(...)`), the scheduler setup, the loop body (other than the single `x_t` initialization line).

**Immediate verification:** Run `loop_comparison.py`. The mean abs diff vs official should drop significantly from 0.608. Expected: < 0.10. If still > 0.3, the guard in Step 1 may not have triggered correctly — check `raw_action_dim` and `unified_dim` values logged.

**Artifact:** `evidence/round-2/step2_loop_comparison_output.txt`

---

### Step 3 — Apply same 128D fix to `_guided_denoise_loop`

**Intended change:**
- Same pattern: extract `unified_action_dim` and `action_indices` from `cond` after `encode_inputs`.
- Change `x_t = torch.randn(B, 64, raw_action_dim, ...)` to `x_t = torch.randn(B, 64, unified_action_dim, ...)`.
- After the loop, project back: `return x_t[:, :, action_indices][:, :, :raw_action_dim]`.
- No other changes to guidance hook logic.

**Why necessary:** Same root bug as `_predict_unguided`. The guided path would silently remain broken if only the unguided path is fixed.

**Assumptions:**
- The gradient hooks operate on `noise_pred[:, :, :3]` (first 3 dims of the 128D noise_pred). `action_indices[:3] = [0, 1, 2]` are the first three arm joints — the gradient injection still targets the correct semantic dims.
- `_rdt_sample_to_trajectory_3d` slices `_ARM_JOINTS = slice(0, 7)` — this still addresses dims 0-6 of the 128D `x_t`, which are still the arm joint dims. No change needed to trajectory projection.

**Must not change:** The three guidance hooks (Phase D, A, B), FKD initialization, `_compute_diversity_gradient`, `_compute_keypoint_gradient`, `_adaptive_scale`.

**Immediate verification:** Smoke tests still pass. Then run the guided loop with a mock guidance function and verify it doesn't crash and returns `(B, 64, 8)`.

**Artifact:** `evidence/round-2/step3_smoke_tests.txt`

---

### Step 4 — Commit

**One commit covering Steps 1–3.** Do NOT include any other changes.

Commit message should reference the specific bug: initialization in 8D subspace vs required 128D unified action space.

**Artifact:** Git commit hash → `evidence/round-2/commit_hash.txt`

---

## 5. Validation Plan

### A. Unit / Local Validation (after Steps 1–3, before commit)

1. **Smoke tests:** `pytest tests/test_rdt_steer.py -v` — all 4 tests must pass.
   - The stub model path uses empty `cond`, triggering the `raise RuntimeError` in `_RDTDiTAdapter`. The tests mock `_dit` directly — they bypass `_RDTDiTAdapter.forward` entirely. Should be unaffected.
2. **Shape check:** Call `_predict_unguided` with the real model on a synthetic input. Confirm the return shape is `(B, 64, 8)` (not 128D).

Save to: `evidence/round-2/step1_smoke_tests.txt`

---

### B. Frozen-Sample Validation (after Step 2)

**Rerun `docs/superpowers/evidence/round-1/stats/loop_comparison.py` with no other changes.**

Expected results after H1 fix:

| Metric | Pre-fix (Round 1) | Post-fix target |
|---|---|---|
| Official arm autocorr | 0.9472 | ~0.9472 (unchanged) |
| Custom arm autocorr | 0.9810 | ~0.9 (similar structure) |
| **Mean abs diff (normalized)** | **0.608** | **< 0.10** |
| Joint 1 sign (official vs custom) | opposite | same sign |
| Step-0 action saturation | 2/24 dims at ±1 | ≤ 1/24 dims (reduced) |

Save output to: `evidence/round-2/step2_loop_comparison_output.txt`

**Decision rule:** If mean abs diff > 0.3 after the fix, Step 1 guard may not have triggered. Log `raw_action_dim` and `unified_dim` at the entry of `_RDTDiTAdapter.forward` to diagnose.

---

### C. Short Rollout Validation (after commit)

Run 1 LIBERO episode (no guidance, `sample_batch_size=1`) and inspect behavior:

```bash
python main.py env=libero policy.type=rdt main.episode_num=1 main.use_guidance=false main.sample_batch_size=1
```

**Expected improvement:**
- Robot should no longer make a single large saturated move and stall.
- Robot should produce more continuous, exploratory motion toward the object region.
- Success rate may still be 0/1 (this is acceptable at this stage — H3 image flip is not yet fixed).

**Minimum bar:** Robot motion is qualitatively different from pre-fix behavior. The step-0 saturation should be reduced or absent.

Save rollout video + console output to: `evidence/round-2/rollout_h1_fixed/`

---

### D. Broader Regression Validation (after rollout check)

1. **Existing policies unaffected:** Run 1 episode with `policy.type=pi05` and confirm it completes normally. RDTSteer changes are in a separate class and cannot affect PI05 or Diffusion paths.
2. **Smoke tests:** Reconfirm all 4 `test_rdt_steer.py` tests pass.
3. **No import errors:** `python -c "from core.rdt_policy_steer import RDTSteer"` runs cleanly.

---

## 6. Success Criteria

The H1 repair is **successful** when ALL of the following are true:

1. `loop_comparison.py` (rerun with H1-fixed code) shows mean abs diff < 0.10 vs official `step()`.
2. Joint 1 normalized targets have the same sign in both paths (official and custom).
3. Step-0 action saturation drops to ≤ 1/24 dims.
4. All 4 smoke tests pass.
5. 1 LIBERO rollout shows qualitatively different (more directed) robot behavior vs the pre-fix random-stall pattern.

The H1 repair may be **successful but insufficient** (i.e., success rate remains 0) if:
- Robot moves more but still fails tasks → H3 (image flip) is still active and visual conditioning is wrong. This is expected — H3 is confirmed but not yet fixed.

**What is acceptable at this stage:**
- Success rate of 0/1 in short rollout validation.
- Step-0 action still somewhat large (FK delta from start config to first predicted config may still be non-trivial, just not as extreme as with wrong joint targets).

---

## 7. Stop-Loss Rules

| Trigger | Action |
|---|---|
| `loop_comparison.py` shows mean abs diff > 0.5 after fix | Stop. The Step 1 guard is not working. Log `raw_action_dim` and `unified_dim` at `_RDTDiTAdapter.forward` entry. Check that `cond["unified_action_dim"]` is correctly populated. |
| Smoke tests fail after change | Revert Steps 1–3. Diagnose which test fails and why. The `else` branch in Location 2 must preserve stub behavior. |
| Robot behavior is unchanged (same stall pattern) | Collect new `loop_comparison` output with logging. If the forward pass is still receiving 8D `x_t`, the guard didn't fire — add explicit assertions to verify. |
| Any crash during rollout that wasn't present before | Revert all changes. Log the full traceback. The 128D denoising loop + shape mismatch is the most likely new failure mode. |

**Revert command:** `git revert HEAD` or `git checkout HEAD core/rdt_policy_steer.py`

**When NOT to continue to H3 fix:**
- Do not fix H3 (image flip) in the same session as H1.
- Do not fix H3 if the `loop_comparison` mean abs diff is still > 0.3 after the H1 fix — the H1 fix may not be complete and conflating two changes would prevent diagnosis.

---

## 8. Next-Most-Likely Cause If This Repair Fails

If the H1 fix does not change mean abs diff significantly, investigate:

**Alternative mechanism: `encode_inputs` conditioning differs from official `predict_action`**

The custom `encode_inputs` path mirrors `predict_action:237` (`state_tokens = torch.cat([state_tokens, action_mask], dim=2)` before `adapt_conditions`). If this does not match, the visual/language/proprio conditioning itself is wrong, and the loop produces the wrong output regardless of `x_t` initialization.

**Evidence needed:**
- Compare `cond["state_traj"]` shape and norm from custom `encode_inputs` vs `state_traj` produced inside `predict_action` before the loop.
- Run official `predict_action` with a monkey-patched `conditional_sample` that logs `state_traj` values.

---

## 9. Execution Guidance for the Next Prompt

**Which files to read:**
- `core/rdt_policy_steer.py` — read in full before making any changes
- `docs/superpowers/evidence/round-1/stats/loop_comparison.py` — read to understand how to rerun validation

**Which step to implement first:**
- **Step 1** (`_RDTDiTAdapter.forward` guard) — this is the prerequisite. Without it, the Location 1 change produces wrong behavior.

**What NOT to touch:**
- `core/rdt_obs_processor.py` (H3 fix is separate)
- `core/rdt_action_converter.py`
- `main.py`
- `tests/test_rdt_steer.py` (tests should pass without modification)

**Validation that must complete before Step 2:**
- Smoke tests must pass after Step 1.
- Once Step 2 is complete: rerun `loop_comparison.py` and confirm mean abs diff < 0.10 before proceeding to Step 3 or commit.
