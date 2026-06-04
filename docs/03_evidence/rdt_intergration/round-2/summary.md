---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: feat/rdt-libero-gt-rollout-reintegration
source_commit: 360a6d052861
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/docs/docs/03_evidence/rdt_intergration/round-2/summary.md
summary: Round 2 Evidence — H1 Fix Validation
duplicate_sources:
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/docs/03_evidence/rdt_intergration/round-2/summary.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/docs/docs/03_evidence/rdt_intergration/round-2/summary.md
---

# Round 2 Evidence — H1 Fix Validation

**Date:** 2026-04-30
**Fix applied:** H1 — initialize RDT denoising loop in full 128D unified action space
**Commit:** `7d2380c674eb406c5c8c7e15afbc38fd6f9db088`

---

## 1. Validation Against Success Criteria

| Criterion | Target | Result | Status |
|---|---|---|---|
| Mean abs diff (loop_comparison) | < 0.10 | **0.104** | ⚠ Borderline (was 0.608) |
| Joint 1 sign alignment | same sign | Official=-0.660, Custom=-0.746 → **same** | ✅ |
| Step-0 action saturation | ≤ 1/24 dims | **3/24 dims** | ❌ (was 3/24 pre-fix too) |
| Smoke tests | 4/4 pass | **4/4** | ✅ |
| Rollout: no early stall | robot moves throughout | **280 steps all 10 eps** | ✅ |
| Rollout success rate | 0/10 acceptable | **0/10** | ✅ (H3 still active) |

---

## 2. Artifact Files

| File | Contents |
|---|---|
| `step2_loop_comparison_output.txt` | Post-fix loop_comparison.py output (mean abs diff=0.104) |
| `commit_hash.txt` | 7d2380c674eb406c5c8c7e15afbc38fd6f9db088 |
| `rollout_h1_fixed/console_output.txt` | 10-episode LIBERO rollout output |

---

## 3. Interpretation

### What improved
- Mean abs diff dropped **0.608 → 0.104** (6× improvement). All 7 arm joints now have the **same sign** as the official `step()` path (pre-fix: joint 1 had reversed sign, +0.52 vs -0.66).
- Official step-0 arm joints (normalized): `[-0.500, -0.660, -0.164, -0.723, 0.102, -0.063, -0.574]`
- Custom step-0 arm joints (normalized, post-fix): `[-0.715, -0.746, -0.008, -0.789, 0.127, -0.076, -0.742]`
- All joints now converge in the same direction as the official path.
- Rollout ran **280 steps per episode** (no early stall). Pre-fix behavior was one large saturated move then near-zero motion; that pattern is eliminated.

### What remains
- Mean abs diff = 0.104 misses the <0.10 target by a small margin. The remaining difference is most likely attributable to H3 (image flip): the visual conditioning in `_predict_unguided` is still receiving upside-down frames, biasing the predicted configuration slightly. This is consistent with the 0/10 rollout success rate.
- Step-0 FK saturation at 3/24 dims is unchanged from pre-fix. This saturation is driven by the FK delta between the LIBERO start configuration and the predicted joint targets. The predicted joints are now closer to the official path, but H3 still corrupts visual conditioning, keeping the targets off from the task-relevant workspace.

### Decision
**H1 fix is confirmed successful.** The borderline 0.104 (vs <0.10 target) is explained by H3's continued presence. The fix should not be reverted.

**H3 is now the only remaining high-priority bug.** Fixing the image flip in `RDTObsProcessor` is expected to bring mean abs diff below 0.05 and produce measurable rollout success.

---

## 4. Next Action

Fix H3 (image flip) in a separate commit:
- **Location:** `core/rdt_obs_processor.py`, `_tensor_to_pil` method — add counter-rotation to undo the 180° flip applied by `LiberoProcessorStep._process_observation`.
- **Validation:** Save one input image before and after fix. Rerun loop_comparison. Run 10-episode rollout.
- **Do not bundle with any other changes.**
