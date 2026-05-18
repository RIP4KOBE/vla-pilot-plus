# Round-4 Action Chain Probe Report

**Date**: 2026-05-11  
**Branch**: `feat/rdt-integration`  
**Commit**: `276bf4b` (P5-P7 probes, revert after capture)  
**Task**: Isolate unhealthy boundary between RDT denoise output and LIBERO OSC action  
**Outcome**: Two independent root causes confirmed — both contribute to 0/10 failure

---

## Evidence Artifacts

| File | Description |
|------|-------------|
| `20260511_action_probes.log` | P5/P6/P7 log, 3 trigger steps (0, 10, 20) |
| `20260511_P5_chunk_np_step{0,10,20}.npy` | Raw RDT denoiser output (H=8, dim=8) |
| `20260511_P6_q_sequence_step{0,10,20}.npy` | Denormalized joint sequence (H+1=9, dim=7) |
| `20260511_P6_eef_pos_step{0,10,20}.npy` | FK EEF positions (H+1=9, dim=3) |
| `20260511_P6_eef_traj3d_step{0,10,20}.png` | 3D EEF trajectory visualization |
| `20260511_P7_libero_chunk_step{0,10,20}.npy` | Final LIBERO OSC action chunk (H=8, dim=7) |

---

## Probe Summary Table

### P5 — RDT chunk_np (denoiser output, before conversion)

| Step | arm range | arm_std | arm_step_diff_max | grip range | grip_sign_changes | OOR count |
|------|-----------|---------|-------------------|------------|-------------------|-----------|
| 0    | [-0.94, 0.17] | 0.37 | 0.012 ✓ | [-0.97, -0.95] | 0 ✗ | 0 ✓ |
| 10   | [-0.96, 0.09] | 0.41 | 0.008 ✓ | [-1.00, -1.00] | 0 ✗ | 1 ⚠ |
| 20   | [-0.82, 0.53] | 0.46 | 0.006 ✓ | [-1.008, -1.008] | 0 ✗ | **8** ✗ |

**Verdict**: PARTIALLY UNHEALTHY
- ✓ Arm: within-chunk smoothness OK; std non-trivial; digits mostly in [-1,1]
- ✗ **Gripper: stuck at -0.95 → -1.008 across all 20+ env steps** — zero sign transitions
- ✗ OOR count grows over episode (0 → 1 → 8) — denoiser diverging in later steps

### P6 — FK chain + denormalization

| Step | q0_match | q_step_diff_max | q_clip | rot_ortho_err | **pre_clip_pos_max** | pre_clip_ori_max | pos_step_diff_max |
|------|----------|-----------------|--------|---------------|----------------------|------------------|-------------------|
| 0    | 0.00 ✓   | 0.65 rad ⚠      | 0 ✓    | 3.4e-16 ✓     | **1.90** ✗           | 1.37 ⚠           | 9.7 cm ⚠          |
| 10   | 0.00 ✓   | 0.24 rad ✓      | 0 ✓    | 4.1e-16 ✓     | **1.09** ⚠           | 0.76 ✓           | 5.8 cm ⚠          |
| 20   | 0.00 ✓   | 0.47 rad ⚠      | 0 ✓    | 8.5e-16 ✓     | **6.19** ✗✗          | 2.30 ✗           | **31.6 cm** ✗✗    |

**Verdict**: UNHEALTHY (F-1 POS_SCALE audit hypothesis confirmed)
- ✓ FK math: q0_match=0, rotation matrices orthogonal, no Franka limit violations
- ✗ **pre_clip_pos_max consistently > 1.0** — RDT plans EEF moves up to 31 cm/step; LIBERO clips to ±5 cm
- ✗ ORI_SCALE also saturated at steps 0 and 20
- ⚠ q_step_diff_max=0.65 rad at step 0 (~37°/step) — large but consistent with RDT planning big moves

### P7 — Final LIBERO action (post-conversion)

| Step | pos_sat_rate | ori_sat_rate | pos_z_first10_mean | grip range | grip_sign_changes |
|------|-------------|-------------|-------------------|------------|-------------------|
| 0    | 4.2% ⚠       | 4.2% ⚠       | **-0.118** ✓ (down) | [0.95, 0.97] ✗ | 0 ✗ |
| 10   | 4.2% ⚠       | 0.0% ✓       | -0.052 ✓ (down)   | [1.00, 1.008 OOR] ✗ | 0 ✗ |
| 20   | 8.3% ⚠       | 4.2% ⚠       | **+0.117** ✗ (up)  | [1.008 OOR] ✗ | 0 ✗ |

**Step 0 first action decoded**: `[-0.39, 0.18, -1.0, 0.34, +1.0, 0.16, +0.95]`
- `pos[2] = -1.0`: z saturated to max descent (-5 cm/step) — clipped from actual -9.7 cm
- `ori[1] = +1.0`: y-rotation saturated — clipped from actual 1.37 × ORI_SCALE
- `grip = +0.95`: **LIBERO closes gripper at step 0**, before any contact with object

**Verdict**: UNHEALTHY — inherits both P5 and P6 failures
- ✗ Gripper command +0.95 → +1.008 from step 0 onward; never opens
- ✗ POS/ORI saturation propagated from P6 scale mismatch
- ✗ Step 20 grip OOR > 1.0 — downstream LIBERO clip behavior undefined

---

## 3D Trajectory Analysis (PNGs)

| Step | Start pos | End pos | Δx | Δz | Shape |
|------|-----------|---------|----|----|-------|
| 0 | (-0.017, 0.591, 0.320) | (-0.014, 0.601, 0.225) | ~0 | -9.5 cm | Smooth diagonal descent — coherent but too fast |
| 10 | (-0.084, 0.594, 0.281) | (-0.140, 0.591, 0.260) | -5.6 cm | -2 cm | One large jump + end-cluster (near mode collapse) |
| 20 | (+0.162, 0.584, 0.318) | (-0.148, 0.614, 0.372) | **-31 cm** | +5 cm | **Single massive horizontal sweep — physically impossible** |

The step 20 trajectory directly visualizes `pre_clip_pos_max=6.19`: RDT plans a 31 cm horizontal sweep in 8 control steps. After LIBERO clip, arm executes saturated lateral motion at max speed with gripper closed — completely incoherent with the pick task.

---

## Decision Tree Result

```
P5 健康?
└─ ❌ Gripper locked at -0.95~-1.008 (close) — no transitions in 20+ steps
   ↳ LOCATE: RDT denoising stage / training distribution level
   ↳ NK: not a conversion bug — chunk_np[:, 7] is already negative before converter

P6 健康?
└─ ❌ pre_clip_pos_max = 1.90 / 1.09 / 6.19 — POS_SCALE=0.05 m wrong by 4-6×
   ↳ LOCATE: Conversion stage — _POS_SCALE parameter mismatch
   ↳ FK math itself is correct (DH, normalization, q0 sanity all pass)

P7 健康?
└─ ❌ Inherits both:
   - POS/ORI saturation from P6
   - Gripper stuck close from P5
   - Step 20 grip=+1.008 OOR propagated from P5 OOR=8
```

---

## Root Cause Summary

### Root Cause A — Gripper Semantic Stuck (P5-level: RDT denoising)

**Observation**: `chunk_np[:, 7]` = -0.95 to -1.008 at all env steps 0, 10, 20.  
**Effect**: After converter negation `(-gripper[i])`, LIBERO receives "+0.95 close" from step 0.  
**Impact on task**: Gripper closes before any approach → cannot form a grasp → 0/10 certainty.

**This is a task-level veto condition**: even with correct POS_SCALE, a persistently closed gripper prevents picking up any object.

Unresolved sub-hypotheses (require round-5 probe):

| ID | Hypothesis | Test |
|----|-----------|------|
| A1 | Gripper output sign is inverted in RDT vs converter assumption | Dump DATA_STAT action_min/max dim 7; compare to ManiSkill training encoding |
| A2 | ManiSkill ckpt training tasks biased toward closed gripper; fails to generalize | Check RDT training task distribution gripper statistics |
| A3 | proprio[7]=0.0387 still semantically off vs training (e.g. RDT trained on binary 0/1, not continuous [0, 0.04]) | Verify ManiSkill gripper action space normalization bounds |

### Root Cause B — POS_SCALE Clipping (P6-level: Conversion)

**Observation**: `pre_clip_pos_max` = 1.90/1.09/6.19 across three trigger steps.  
**Meaning**: `_POS_SCALE = 0.05 m/unit` underestimates RDT's planning scale by ~4-6×.

| Step | RDT intended Δpos | LIBERO envelope | Clip ratio |
|------|-------------------|-----------------|------------|
| 0 | 9.7 cm | 5 cm | 1.9× → ~50% info lost |
| 10 | 5.5 cm | 5 cm | 1.1× → ~9% info lost |
| 20 | 31 cm | 5 cm | **6.2× → ~84% info lost** |

**Estimated correction**: `_POS_SCALE ≈ 0.10–0.20 m/unit`  
- Targeting 95% of Δpos within [-0.7, 0.7] action range: `_POS_SCALE = median_Δpos / 0.5`
- Step 0 median estimate: ~5 cm → `_POS_SCALE = 0.10 m`

**However**: Fixing POS_SCALE alone cannot fix 0/10 while Root Cause A persists.

---

## Intervention Priority

1. **Root Cause A first** (gripper semantic — task-level veto)
   - Inspect `DATA_STAT.action_min/max` dimension 7 in `maniskill_model.py`
   - Verify whether converter negation convention matches RDT training encoding
   - Consider: P8/P9/P10 probes (round-5) for targeted gripper investigation

2. **Root Cause B second** (POS_SCALE — precision issue)
   - Change `_POS_SCALE = 0.05` → `0.10` in `core/rdt_action_converter.py`
   - Re-run baseline; if gripper also fixed, should observe ≥1/10 success

---

## Remaining Unknowns

| ID | Unknown | Priority |
|----|---------|----------|
| U1 | Gripper sign convention in RDT output | **HIGH** — blocks all progress |
| U2 | Whether arm state at step 20 (x=+0.16) is physically reachable | MEDIUM |
| U3 | Effect of POS_SCALE fix on trajectory quality independent of gripper | LOW (won't resolve without gripper fix) |
| U4 | LIBERO behavior when gripper command > 1.0 (OOR) | LOW |
