---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: feat/rdt-libero-gt-rollout-reintegration
source_commit: 360a6d052861
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/docs/docs/02_analysis/rdt_intergration/libero/rdt_vls_steering_failure_analysis.md
summary: RDT VLS Steering Failure Analysis
duplicate_sources:
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/docs/02_analysis/rdt_intergration/libero/rdt_vls_steering_failure_analysis.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/docs/docs/02_analysis/rdt_intergration/libero/rdt_vls_steering_failure_analysis.md
---

# RDT VLS Steering Failure Analysis

**Date:** 2026-05-12
**Branch:** `feat/rdt-integration`
**Scope:** Static, code-grounded analysis of why **VLS steering** with RDT on LIBERO drives the arm in the wrong direction.
**Companion artifact:** `outputs/libero/2026-05-12_06-19-09/episode_1/episode_1_fail_agentview.mp4`
**Constraint:** Read-only analysis. No code changes, no fixes are proposed.

---

## 1. Problem statement

**Observed behavior (from rollout videos):**
With `python main.py policy.type=rdt main.guidance=true`, the Franka EEF in LIBERO **moves in a direction consistently opposite to the keypoint-indicated direction** across episodes. The arm is not random; it is *systematically wrong*.

**Inferred (NOT observed):**
- Whether the inversion is symmetric across all three world axes, or specific to one axis (e.g. only +Y/-Y).
- Whether the inversion is present at the *very first* chunk, or only after a few denoising iterations.
- Whether the *unguided* RDT+LIBERO path (`use_guidance=false`) also produces wrong-direction motion at the same magnitude (prior debug notes report low success but did not characterise *signed* direction).

These three open questions matter for ranking the candidate failure modes below. Section 8 lists the minimum evidence needed to resolve them.

**Distinction from the prior failure analysis** (`docs/superpowers/02_analysis/rdt_intergration/libero/2026-04-30-rdt-libero-failure-analysis.md`):
that document explicitly de-scoped the guidance path (its §H — "Guidance / FKD Side Effects" — concludes "this module is **not applicable** for current diagnostics" because steering was off at the time). Since then the 128D denoising bug and the LIBERO image-flip bug have been fixed (commits `7d2380c`, `4bf90b7`). The remaining steering-specific failure has not yet been audited. **This document is that audit.**

---

## 2. Scope of this analysis

**In scope:**
- The full code path from raw LIBERO observation → keypoint extraction → RDT denoising loop → keypoint gradient injection → action chunk → sim step, **restricted to the parts that influence steering direction**.
- Action / observation / coordinate / frame semantics that the steering math implicitly assumes.
- Comparison to the working baselines (`pi05_steer`, `diffusion_policy_steer`) where their steering paths diverge from RDT's.

**Explicitly out of scope:**
- Generic unguided RDT integration issues (token shapes, T5 loading, `lang_embeds/` cache key, sim/checkpoint domain gap, `_POS_SCALE` / `_ORI_SCALE` calibration, gripper sign). These are covered in `2026-04-30-rdt-libero-failure-analysis.md` and are not direct causes of *signed direction* error in the steering math.
- VLM prompt design or correctness of the *content* of generated guidance functions. We assume the VLM-generated reward function correctly encodes "EEF trajectory should approach the keypoint(s)" in the same convention pi05 / diffusion expect (which the design spec confirms — see `docs/superpowers/01_specs/2026-04-22-rdt1b-integration-design.md`, §5).
- The diagnostic probes P1–P7 added in commits `89b1dff` / `276bf4b`. They are observability instrumentation, not steering logic, and they don't change semantics.

---

## 3. Steering-relevant execution path

End-to-end call graph for one steered action chunk (file:line citations are exact):

```
LIBERO sim                            (robosuite OffScreenRenderEnv)
        │
        │  agentview/wrist images, robot0_eef_*, robot0_joint_pos, robot0_gripper_qpos
        ▼
LiberoEnv._format_raw_obs             core/env_adapters/libero_adapter.py:558-592
        │
        │  {observation.images.image, .image2, observation.robot_state}
        ▼
LiberoAdapter.get_policy_observation  core/env_adapters/libero_adapter.py:828-904
        │   ├─ env_preprocessor = PolicyProcessorPipeline([LiberoProcessorStep()])
        │   │     • images: torch.flip(dims=[2,3])  ── 180° H+W
        │   │     • robot_state → observation.state = [eef_pos, axisangle, gripper_qpos]
        │   └─ obs['task'] = [task_description]
        ▼
RDTSteer.select_action                core/rdt_policy_steer.py:673-743
        │
        ├─► RDTObsProcessor.process     core/rdt_obs_processor.py:123-238
        │     • _tensor_to_pil: if _undo_libero_flip → torch.flip(dims=[1,2])  ── undoes the 180°
        │     • _build_image_list → [ext_{t-1}, None, None, ext_t, None, None]
        │     • proprio_np (8,)  = [q0..q6, gripper_finger0_abs]
        ▼
RDTObsProcessor.get_lang_embed → text_embed (1, seq, 4096)
        │
        ▼
_guided_denoise_loop                  core/rdt_policy_steer.py:1038-1172
        │
        │  cond  = encode_inputs(...)            ── unified_action_dim=128
        │  x_t   = randn(B, 64, 128)             ── line 1081  ★ 128D unified
        │  start_t = timesteps[ int(N * start_ratio) ]
        │
        │  for t in scheduler.timesteps:
        │      noise_pred = self._dit(x_t, t, cond)            (B, 64, 128)
        │
        │      if t > start_t  and use_diversity and B > 1:
        │          div_grad = _compute_diversity_gradient(x_t)
        │              └─► _rdt_sample_to_trajectory_3d(...)   ── ★ steering core
        │          noise_pred[..., :7] += diversity_scale * div_grad[..., :7]
        │
        │      elif guidance_fns and t <= start_t:
        │          kp_grad, reward = _compute_keypoint_gradient(x_t, keypoints, guidance_fns)
        │              └─► _rdt_sample_to_trajectory_3d(...)   ── ★ steering core
        │          noise_pred[:, :H, :7] -= scale * kp_grad[:, :H, :7]
        │
        │      x_t = scheduler.step(noise_pred, t, x_t).prev_sample
        │
        │      if fkd is not None and t <= start_t:
        │          x_t, _ = fkd.resample(t, x_t, x_t)            ── uses same _rdt_sample_to_trajectory_3d
        │
        ▼
return x_t[:, :, action_indices][:, :, :8]       ── (B, 64, 8) joint-space, normalised
        │
        ▼
_postprocess_actions                   core/rdt_policy_steer.py:796-916
        │   ├─ best = actions[0][:H]                                 (H, 8)
        │   └─ rdt_chunk_to_libero_actions(chunk_np, current_joints) (H, 7) LIBERO OSC
        ▼
main.py:646-649 — `env_postprocessor` is empty for LIBERO (libero_adapter.py:754); no-op.
        │
        ▼
LiberoAdapter.step(action[0, executed])      core/env_adapters/libero_adapter.py:1468-1496
        │   ├─ action_postprocessor = no-op
        │   ├─ action[-1] = +1/-1 binary gripper
        │   └─ libero env step (OSC delta-EEF controller)
        ▼
sim physics → next observation
```

★ The **steering core** is `_rdt_sample_to_trajectory_3d` (`rdt_policy_steer.py:920-927`), called by both gradient hooks and FKD. This is the single point that converts the raw denoising-loop state `x_t` into the 3D EEF trajectory tensor that guidance functions evaluate. **Every signed steering signal in the system passes through this function.**

---

## 4. Steering-critical representation and convention checks

For each stage where steering-relevant semantics are crossed, the four columns are: *representation* (what tensor shape/dtype), *expected semantics* (what the math assumes), *actual code behavior* (what the code does), and *possible mismatch*.

### 4.1 LIBERO raw image orientation

| | |
|---|---|
| Representation | `agentview_image`: `numpy (H,W,3) uint8`, MuJoCo render at offscreen camera `agentview` |
| Expected semantics | Upright RGB of the LIBERO tabletop scene |
| Actual code behavior | `LiberoEnv.render()` (libero_adapter.py:513) does `image[::-1, ::-1]` for *visualization*; `_format_raw_obs` (line 558) emits the **un-flipped** MuJoCo tensor under `observation.images.image`; downstream `LiberoProcessorStep._process_observation` (env_processor.py:59) applies `torch.flip(dims=[2,3])` (180°). `_tensor_to_pil` in RDTObsProcessor (line 119) re-flips by `dims=[1,2]` when `_undo_libero_flip=True` (set in `RDTSteer.post_init` line 609 iff adapter is `LiberoAdapter`). |
| Possible mismatch | `flip ∘ flip = identity` on the (C,H,W) tensor → the image arriving at RDT's SigLIP encoder *should* match the raw MuJoCo orientation. Prior round-3 H3 evidence verified this synthetically. **But:** the prior observation-chain audit (`2026-05-11-rdt-libero-observation-semantic-chain.md` §E.1.4) explicitly flags this as "MATCH (synthetic) — UNKNOWN on live frame". If the raw MuJoCo render is itself upside-down (UNKNOWN per §A.3 of that doc), the current double-flip leaves it upside-down anyway. |

**Steering-relevance:** Image orientation only affects how RDT's vision encoder conditions denoising. A mis-oriented image degrades conditioning quality but does **not directly invert the steering vector**, because (a) the steering vector is computed from keypoints and the 3D trajectory in world frame, not from image pixels, and (b) the gradient direction comes from the spatial relation between trajectory and keypoint, not from the visual features.

### 4.2 Keypoint representation

| | |
|---|---|
| Representation | `keypoints: np.ndarray (N, 3) float32` in **world frame** (= robot base frame in LIBERO; `LiberoAdapter.get_robot_base_pose` returns the world origin, libero_adapter.py:953-961) |
| Expected semantics | 3D world positions of task-relevant points, tracked through the episode |
| Actual code behavior | `KeypointTracker.get_keypoint_positions()` (keypoint_tracker.py:146-182) returns world positions, computed by transforming each stored *local-frame* offset through the current object pose. Initial 3D positions come from `_depth_to_pointcloud` (libero_adapter.py:1257-1305) followed by `np.flipud(points)` to align with image-coordinate origin (line 1385). The point cloud is in **world frame** before the flipud (no axis swap, only a row-reverse to flip the pixel/Y indexing). |
| Possible mismatch | None of the keypoint construction inverts a *world axis*. The flipud aligns pixel indices to a top-left origin convention for keypoint *picking*; world (x,y,z) values are not negated by it. So `keypoints[N, 3]` are valid world coords. |

**Steering-relevance:** Keypoints are not the source of a sign-inversion. (Sub-pixel offsets in the 2D click-back-projection step are possible, but those would not produce a *consistent opposite-direction* macro behavior.)

### 4.3 RDT denoising-loop state `x_t` — what does each column at indices 0..6 mean?

| | |
|---|---|
| Representation | `x_t: torch.Tensor (B, 64, 128)` — particle batch × prediction horizon × unified action vector |
| Expected semantics (per RDT) | At full denoising (t→0), `x_0[:, :, MANISKILL_INDICES]` is a sequence of **normalised absolute Franka joint angles + gripper_open ∈ [-1, 1]**. The denormalisation `(x+1)/2 * (action_max-action_min) + action_min` yields absolute joint angles in radians (see `_unformat_action_to_joint` in third_party/rdt/scripts/maniskill_model.py:187-195). |
| Actual code behavior | Exactly as above: `_predict_unguided` and `_guided_denoise_loop` both project back via `x_t[:, :, action_indices][:, :, :8]` (rdt_policy_steer.py:792, 1172). The action_indices come from `state_elem_mask.nonzero(...)` in `encode_inputs` (rdt_policy_steer.py:285). Concretely, `MANISKILL_INDICES = [STATE_VEC_IDX_MAPPING[f"right_arm_joint_{i}_pos"] for i in range(7)] + [STATE_VEC_IDX_MAPPING["right_gripper_open"]] = [0, 1, 2, 3, 4, 5, 6, 10]` (third_party/rdt/scripts/maniskill_model.py:14-18; third_party/rdt/configs/state_vec.py:3-11,17). |
| Possible mismatch | The **first 7 unified indices** correspond to `arm_joint_0_pos` … `arm_joint_6_pos`. So `x_t[..., 0:7]` *does* address the right-arm joints (after denoising). Concretely, `x_t[..., 0]` is the normalised target for joint 0 (base yaw), `x_t[..., 1]` is joint 1 (shoulder pitch), and `x_t[..., 2]` is joint 2. These are **joint angles**, not Cartesian deltas, not deltas of any kind, not EEF positions — *absolute* joint positions in normalised space. |

**This is the central semantic fact for the bug analysis below.** The steering code in `_rdt_sample_to_trajectory_3d` then re-interprets `x_t[..., 0:3]` as if it were a delta-EEF position in world frame; see §4.5.

### 4.4 LIBERO action semantics (what the `LiberoAdapter.step` actually consumes)

| | |
|---|---|
| Representation | `action: torch.Tensor (7,)` per step |
| Expected semantics | LIBERO OSC: `action[:3]` = normalised delta EEF position in *world frame* (∈[-1,1], scaled internally by the controller); `action[3:6]` = normalised delta EEF orientation (axis-angle); `action[6]` = gripper command (binarised in `LiberoAdapter.step` line 1479 to ±1). See `LiberoAdapter.get_action_space_info` (line 1391-1404) and `delta_actions_to_ee_trajectory` docstring (line 1411-1422). |
| Actual code behavior | `_postprocess_actions` (rdt_policy_steer.py:796-916) takes the **denoised 8D joint chunk** `(H, 8)`, calls `rdt_chunk_to_libero_actions(chunk, current_joints)` which does: *denormalise* joint columns → *Franka FK* on `current_joints` and on each predicted joint config → take *consecutive pose differences* → scale by `_POS_SCALE=0.05` / `_ORI_SCALE=0.5` → clip to `[-1, 1]` (core/rdt_action_converter.py:118-258). Output is `(H, 7)` LIBERO OSC delta-EEF, fed straight to `adapter.step` (no further postprocessing — `LiberoAdapter`'s `env_postprocessor` is empty, libero_adapter.py:755). |
| Possible mismatch | The **executed** action chain is internally consistent: RDT outputs joints → FK → OSC delta-EEF. The action that drives the sim is correctly typed. Where the inconsistency lives is in the **steering** path, which evaluates a 3D trajectory derived directly from the unfinished `x_t` *without* going through this FK chain. See §4.5. |

### 4.5 RDT steering trajectory — `_rdt_sample_to_trajectory_3d`

This is the function under user-selected line 746 (`_predict_unguided`) and the immediately following block. The exact body:

```python
# rdt_policy_steer.py:920-927
_ARM_JOINTS = slice(0, 7)         # rdt_policy_steer.py:29

def _rdt_sample_to_trajectory_3d(self, sample: Tensor) -> Tensor:
    action_seq = sample[0, : self._action_chunk_horizon, _ARM_JOINTS]  # (H, 7)
    traj = self._adapter.delta_actions_to_ee_trajectory(action_seq)    # (H+1, 3)
    return traj.unsqueeze(0)                                            # (1, H+1, 3)
```

| | |
|---|---|
| Representation | Input: a denoising-loop state `sample: (B, 64, 128)` (with `B=1` per the callers' slicing). Output: `(1, H+1, 3)` 3D positions. |
| Expected semantics (used by the guidance reward) | "3D EEF trajectory in world frame, starting at the current EEF pose, evolving over `H` action steps." The VLM-generated reward functions consume a `(B, T, 3)` tensor (utils/guidance_utils.py:131-134 — validation uses `trajectory: (1, 10, 3)`) and assume world-frame positions, identical to what pi05 and diffusion policies supply. |
| Actual code behavior | (1) Slice `sample[0, :H, 0:7]` — picks `x_t` at the unified-vector indices that *do* correspond to right-arm joints (per §4.3). (2) Pass to `LiberoAdapter.delta_actions_to_ee_trajectory(action_sequence)`. (3) That function does (libero_adapter.py:1406-1455): `start_pos = get_ee_pose_world().position; delta_positions = action_sequence[:, :3] * 0.01; trajectory = [start_pos] + start_pos + cumsum(delta_positions)`. |
| Possible mismatch | **The function `delta_actions_to_ee_trajectory` interprets `action_sequence[:, :3]` as a delta EEF position in world frame.** But `sample[0, :, 0:3]` is the noisy x_t at the unified-vector positions for `right_arm_joint_0_pos`, `right_arm_joint_1_pos`, `right_arm_joint_2_pos` — i.e. **(noisy) normalised absolute Franka joint angles for joints 0, 1, 2**. There is no semantic relationship between these joint values and Cartesian world deltas. The "trajectory" computed by this code path is therefore **geometrically meaningless**: it cumulatively sums noisy joint-angle values, multiplies by 0.01 m/unit, and adds to the current EEF position. |

This single mismatch is the **earliest steering-specific semantic violation** in the system. Everything downstream of it (the gradient, the FKD reward, the diversity potential) inherits the violation.

### 4.6 Comparison: how `pi05_steer` and `diffusion_policy_steer` avoid this

Both baseline policies define their own `_sample_to_trajectory_3d` that **first runs the action postprocessor** to convert the raw denoising-loop sample into the LIBERO 7D OSC delta-EEF format, *then* hands the result to `delta_actions_to_ee_trajectory`:

```python
# core/pi05_steer.py:331-355
def _sample_to_trajectory_3d(self, sample: Tensor) -> Tensor:
    actions = self._postprocessor(sample).to(device, dtype)         # ← sample → LIBERO action
    action_transition = {"action": actions}
    if hasattr(self._adapter, 'env_postprocessor'):
        action_transition = self._adapter[redacted env file]_postprocessor(action_transition)
    actions = action_transition["action"]
    ...
    traj = self._adapter.delta_actions_to_ee_trajectory(actions.squeeze(0)[:H])
```

```python
# core/diffusion_policy_steer.py:415-432
def _sample_to_trajectory_3d(self, sample: Tensor) -> Tensor:
    ...
    actions = self._postprocessor(sample).to(device, dtype)         # ← same idea
    ...
    traj = self._adapter.delta_actions_to_ee_trajectory(action_seq)
```

In both baselines the value handed to `delta_actions_to_ee_trajectory` has already been mapped into LIBERO OSC delta-EEF format, which is what the function expects. **In RDT this conversion is skipped**, because:

- The RDT `postprocessor` in `main.py:172-173` is set to `lambda x: x` (identity). RDT owns its own postprocessing internally via `_postprocess_actions`, which is *not* called inside the denoising loop — only after.
- The naive substitution `sample[..., 0:7]` looks like the equivalent slice of a 7-DoF action chunk, but it is a slice of the *joint-space* representation of the unfinished denoising state. The semantics are not interchangeable with `pi05`'s sample (which is already in delta-EEF normalised form coming out of pi05's flow-matching model).

### 4.7 Gradient injection into `noise_pred`

| | |
|---|---|
| Representation | `noise_pred: (B, 64, 128)`; gradient added at indices `0:7` only |
| Expected semantics | "Classifier guidance: shift the noise prediction so that, after the scheduler step, the denoised joint chunk approaches a higher-reward configuration." For the RDT-ManiSkill model, indices `0:7` of the unified vector are the active joint dimensions (§4.3), so writing the gradient there is at least *targeting the right tensor positions*. |
| Actual code behavior | `_compute_keypoint_gradient` (rdt_policy_steer.py:968-1024): autograd through `_rdt_sample_to_trajectory_3d` → reward → `grad = ∂reward/∂x_t`. Then `noise_pred[:, :H, :7] -= scale * kp_grad[:, :H, :7]` (line 1153-1156). |
| Possible mismatch | Because the trajectory is geometrically meaningless (§4.5), `grad` is the gradient of *the wrong objective*. Concretely, with the reward decomposed as `r ≈ -‖(start_pos + 0.01·cumsum(x_t[:, :, 0:3])[-1]) - keypoint‖²`, the gradient w.r.t. `x_t[:, t, 0:3]` is approximately `2·(target − start − 0.01·cumsum) / 0.01` in each axis. The autograd will push `x_t` at unified indices 0/1/2 in the *world-axis direction* of `keypoint − start_pos`. After the scheduler step, the denoised values for `right_arm_joint_0_pos / _1_pos / _2_pos` are biased in this world-axis direction *as if* they were Cartesian deltas. These are then denormalised to real joint angles and passed through Franka FK, which produces an EEF motion related to keypoint direction only by the local Franka Jacobian J(q) — there is no reason for the resulting EEF velocity to be aligned with `keypoint − start_pos`, and in many configurations it can be (close to) *anti-parallel*. |

### 4.8 Diversity hook (`_compute_diversity_gradient`)

Same routing as 4.7: `noise_pred[:, :, :7] += diversity_scale * div_grad[:, :, :7]` (rdt_policy_steer.py:1143). The diversity potential is an inverse-distance repulsion in the (fake) 3D trajectory space (rdt_policy_steer.py:931-966). Because the trajectory is meaningless, the diversity term scatters particles in a non-physical direction. In a *single-particle* setting (`B=1`) this hook is inactive (line 937 short-circuits) and is not the cause of the directional error.

### 4.9 FKD reward function

`_fkd_reward_fn` (rdt_policy_steer.py:1098-1108) also evaluates `_rdt_sample_to_trajectory_3d` on the noisy `x_t` and sums VLM-generated rewards. It inherits the same semantic mismatch as §4.5 — but it only affects *particle resampling*, not the gradient direction. With single-particle inference it has no effect.

### 4.10 Coordinate / frame / handedness review

| Stage | Frame | Convention | Notes |
|---|---|---|---|
| Raw EEF | World frame | Robot base = world origin in LIBERO (libero_adapter.py:953-961) | Right-handed (MuJoCo) |
| Keypoints | World frame | Same as EEF | Right-handed |
| RDT joint targets | Joint space | Franka radians, RDT `DATA_STAT`-normalised to [-1,1] | n/a |
| `delta_actions_to_ee_trajectory` "delta" | World frame | OSC convention (action[:3] = world delta) | Right-handed (libero_adapter.py:1413-1422) |
| Steering "trajectory" (RDT path) | **Nonexistent / undefined** | The function reads `action_sequence[:, :3]` as world deltas, but the input is joint-space; the resulting "trajectory" lives in a fictitious frame | This is the bug |

There are no left/right handedness or quaternion-order issues between keypoint and EEF frames in the LIBERO adapter that would by themselves produce a sign flip on a single axis.

---

## 5. Candidate failure modes

Each candidate is graded *directly evidenced* | *plausible but unconfirmed* | *weak/low-priority*, with concrete file:line references.

### FM-1. Steering trajectory is computed from joint-space `x_t` while the adapter assumes delta-EEF actions

- **Title:** `_rdt_sample_to_trajectory_3d` passes joint-space `x_t` slices into `delta_actions_to_ee_trajectory`, which interprets them as world-frame delta-EEF positions.
- **Code locations:** `core/rdt_policy_steer.py:29` (`_ARM_JOINTS = slice(0,7)`), `core/rdt_policy_steer.py:920-927` (the body), `core/env_adapters/libero_adapter.py:1406-1455` (`delta_actions_to_ee_trajectory` and its semantics), `core/rdt_policy_steer.py:1081` (x_t initialised at unified-dim 128), `core/rdt_policy_steer.py:988-1014` (autograd through the bad trajectory).
- **Why it could cause "motion opposite to keypoint direction":** The gradient `∂reward/∂x_t[..., 0:3]` is computed as if `x_t[..., 0..2]` were the next three Cartesian delta-EEF components. After subtraction from `noise_pred`, the denoised values at unified indices 0/1/2 — which are `right_arm_joint_{0,1,2}_pos` — get biased *as if they were Cartesian world deltas*. When these biased joint targets are subsequently denormalised and fed through Franka FK, the resulting EEF motion depends on the Jacobian J(q) at the current pose. For a Franka in a typical LIBERO start pose, the dominant column of J(q) for joint 0 (base yaw) is approximately *orthogonal* to the +X direction (it rotates around base-Z), and for joint 1 (shoulder pitch) the dominant EEF velocity direction can have **opposite sign on the X axis** relative to an increment in joint angle. The net Jacobian-mediated EEF response can therefore be **systematically anti-aligned** with the keypoint direction the guidance "thought" it was steering toward. This is one mechanism (other Jacobian-induced sign flips are possible too) by which a *consistent* opposite-direction error can arise from what is, in the trajectory-space view, a "correct" gradient direction.
- **Repository evidence:** **directly evidenced.** Lines cited above are unambiguous. The baseline policies (`pi05_steer._sample_to_trajectory_3d`, `diffusion_policy_steer._sample_to_trajectory_3d`) explicitly call `self._postprocessor(sample)` *before* `delta_actions_to_ee_trajectory`; RDT does not (it can't: its postprocessor is identity since RDT does its FK-based conversion only in `_postprocess_actions`, which is outside the denoising loop and isn't differentiable through FK in any case).
- **Assumptions required to hold for this to be the dominant cause:** (a) The RDT-LIBERO unguided baseline is *not* itself moving systematically in the wrong direction at the same magnitude; if it were, then this guidance-only mechanism would be a secondary contributor to a primary unguided bug. (b) The VLM-generated reward function correctly attempts to attract the trajectory to the keypoint (i.e. doesn't return a *repulsive* potential by mistake).
- **Relation to user hypothesis #2:** This is *exactly* user hypothesis 2, expressed precisely: not only does `delta_actions_to_ee_trajectory` assume delta-EEF semantics (the user is correct that RDT outputs EEF deltas? — actually no, RDT outputs *joints*; so the actual mismatch is **even more severe** than the user described). The function is being fed joint angles where it expects world-frame deltas. Hypothesis 2 is **supported and refined**: the action type that `delta_actions_to_ee_trajectory` expects is "world-frame delta EEF" (not "joint deltas"), and RDT's pre-postprocessing output is "absolute normalised joint angles". The two are not even comparable, and pi05's `_postprocessor` does the necessary bridging.

### FM-2. Image orientation residual / mis-orientation reaching SigLIP

- **Title:** Image arriving at RDT's vision encoder may still be in an unexpected orientation.
- **Code locations:** `third_party/lerobot/src/lerobot/processor/env_processor.py:54-61` (180° flip in LiberoProcessorStep); `core/rdt_obs_processor.py:118-121` (un-flip in `_tensor_to_pil`); `core/rdt_policy_steer.py:608-609` (gates the un-flip on `isinstance(adapter, LiberoAdapter)`); `core/env_adapters/libero_adapter.py:1380-1386` (note: `flipud` in `get_keypoint_detection_inputs` is on a *separate* code path — for the keypoint detector, not for RDT's observation stream).
- **Why it could cause "motion opposite to keypoint direction":** Image conditioning influences which action distribution the model samples from. A flipped image could correlate with mirrored action statistics, especially in a model that has learned end-effector-to-image correspondence. But this effect (a) is a *quality / distribution* effect, not a sign-controlled effect, and (b) it does not interact with the gradient direction — the gradient is in trajectory space, not image space.
- **Repository evidence:** **plausible but unconfirmed.** Commit `4bf90b7` documents the fix; the prior observation-chain audit confirmed the synthetic `flip∘flip=identity`. The remaining unknown is whether the raw MuJoCo render is itself upside-down (`2026-05-11-rdt-libero-observation-semantic-chain.md` §A.3). If it is, the current chain would still feed an upside-down image to SigLIP — but again, this would not produce a sign-locked direction inversion in the steering gradient.
- **Assumptions required:** that the visual conditioning has enough influence on action selection to flip steering direction. There is no positive evidence for this in the codebase.
- **Relation to user hypothesis #1:** This is exactly user hypothesis 1. The image-flip hypothesis is **plausible but does not explain consistent opposite-direction steering**, because the steering gradient is computed entirely in world / trajectory space and never touches the image. The image-flip would degrade *conditioning quality* (the baseline action sampled by RDT before steering), not invert the *guidance vector*. If the unguided rollout direction is also reversed, the image-flip hypothesis would gain support; if only the *guided* rollout is reversed, FM-1 (joint-vs-EEF semantic mismatch) is far better aligned with the symptom.

### FM-3. `_postprocessor` is identity for RDT, breaking the steering API contract

- **Title:** `main.py:172-173` sets `policy_preprocessor = policy_postprocessor = lambda x: x` for RDT, while `pi05` and `diffusion` populate these via `make_pre_post_processors`. Inside `_compute_keypoint_gradient` and `_compute_diversity_gradient`, RDT never calls a postprocessor before `delta_actions_to_ee_trajectory`.
- **Code locations:** `main.py:170-189`; `core/rdt_policy_steer.py:920-927`; `core/pi05_steer.py:336-349`; `core/diffusion_policy_steer.py:420-432`.
- **Why it could cause "motion opposite to keypoint direction":** Same root cause as FM-1, expressed at the *integration-architecture* level. FM-1 is "the function passes the wrong tensor type"; FM-3 is "the policy wiring loses the conversion step that pi05/diffusion get for free". They are not independent failure modes; FM-3 *is* the structural condition that allows FM-1 to occur.
- **Repository evidence:** **directly evidenced.**
- **Relation to user hypotheses:** Refinement of #2.

### FM-4. Gradient injection writes to indices `0:7` while the unified-vector arm joints live at `MANISKILL_INDICES=[0,1,2,3,4,5,6,10]`

- **Title:** The slice `noise_pred[..., :7]` skips index 10 (the gripper, `right_gripper_open`).
- **Code locations:** `core/rdt_policy_steer.py:1143` (diversity), `core/rdt_policy_steer.py:1153-1156` (keypoint); `third_party/rdt/scripts/maniskill_model.py:14-18` (MANISKILL_INDICES = [0..6, 10]); `core/rdt_policy_steer.py:285` (action_indices recovered via `nonzero`).
- **Why it could cause "motion opposite to keypoint direction":** It cannot, directly. Indices `0:7` of the 128-D unified vector *are* the right-arm joints (per §4.3), so the gradient *is* being written to the joint-space positions that matter for arm motion. The gripper at index 10 is *also* an active dimension that the gradient does not touch; that means gripper denoising is not affected by guidance, which is benign for steering direction. The only relevance: if a future model variant placed arm joints at non-contiguous indices, the `slice(0,7)` would silently break — *for that variant*, not this one.
- **Repository evidence:** **weak / low-priority.** Not a current cause.
- **Relation to user hypotheses:** none.

### FM-5. Reward sign convention swap

- **Title:** The keypoint guidance subtracts the reward gradient from `noise_pred`; pi05 does the same. If the VLM has generated a reward where *higher = farther from target* (a "cost"), the sign would be inverted.
- **Code locations:** `core/rdt_policy_steer.py:1153-1156`; `core/pi05_steer.py:276`; `vlm_query/vlm_agent.py` (out of scope per §2, but it would be the source of any sign convention).
- **Why it could cause "motion opposite to keypoint direction":** If `reward = +‖traj_end − keypoint‖²` (high = bad), then `∂reward/∂x_t` points *away from* keypoint, and subtracting it from `noise_pred` (which is the correct guidance update when reward = log p(y|x), i.e. high = good) pushes denoised x toward the bad direction.
- **Repository evidence:** **plausible but unconfirmed at the code level.** The same sign convention is shared with pi05, which works. Unless the VLM is producing systematically different rewards for the RDT runs (which is unlikely — the same agent generates them), this is not the cause.
- **Relation to user hypotheses:** none.

### FM-6. RDT vs pi05 prior bias mismatch hidden behind guidance

- **Title:** Even with `use_guidance=true`, if the *unguided* RDT prior is moving the EEF in a wrong direction (per the prior 2026-04-30 failure analysis, ManiSkill→LIBERO domain gap is substantial), the steering gradient is added to that wrong baseline. If the gradient's effective direction is small relative to the prior's wrong direction, the rollout is dominated by the prior. The user's symptom would then be the *unguided behaviour leaking through*.
- **Code locations:** Conceptual; the `_dit(x_t, t, cond)` baseline is unaffected by guidance until the gradient hook fires. The guidance gain is gated by `start_ratio` (default 0.7) and decays via `_adaptive_scale` (rdt_policy_steer.py:1026-1034).
- **Why it could cause the symptom:** A consistent prior direction caused by ManiSkill checkpoint biases (e.g. a Franka home-pose attractor that moves the EEF in a specific direction) would appear as "consistent opposite to keypoint" if the keypoint is consistently on the *other* side of the Franka workspace from the prior's pull.
- **Repository evidence:** **plausible but unconfirmed.** The 2026-04-30 analysis ranked domain gap as Priority Low for the *random* failure mode but did not analyse signed direction.
- **Relation to user hypotheses:** none; this is an alternative explanation that does not require any code-level bug.

---

## 6. Evaluation of the two primary user hypotheses

### 6.1 Image unflip / mirrored keypoint hypothesis (user H1)

**User's claim:** "During RDT integration, I may have unflipped the image observations obtained from LIBERO, causing the keypoint position to appear mirrored in image coordinates."

**Where this could happen in code:**
1. `core/rdt_obs_processor.py:118-121` (`_tensor_to_pil` undoes the LiberoProcessorStep flip — controlled by `_undo_libero_flip`).
2. `third_party/lerobot/src/lerobot/processor/env_processor.py:54-61` (LiberoProcessorStep does the original 180° flip).
3. `core/env_adapters/libero_adapter.py:1380-1386` (keypoint detector path, separate from RDT obs path).

**Analysis:**
- The image flip and its undo only affect what reaches RDT's SigLIP vision encoder. They do **not** affect keypoint positions. Keypoints come from `KeypointTracker.get_keypoint_positions()` which returns world-frame 3D positions reconstructed from depth (libero_adapter.py:1257-1305) and tracked through object pose. No image-flip operation in the codebase mutates 3D world coordinates.
- The keypoint *detector* path (`get_keypoint_detection_inputs`) does `np.flipud(points)` — but only to align *pixel indexing* between rgb / depth / pointcloud, not to invert world axes. World `(x,y,z)` values are not negated.
- For a *consistent opposite-direction* steering error to come from this hypothesis, the image-flip would have to *flip the sign of the gradient vector*, but the gradient is computed in world coordinates from world-frame keypoints and a (faulty but world-frame) "trajectory". Even an upside-down image cannot do that.

**Verdict on H1: weakened by code evidence.** The image-flip path could degrade conditioning quality but cannot mechanistically invert the world-frame steering vector. The hypothesis is plausible as a *contributor* to general failure quality, not as the source of *consistent opposite-direction* steering.

### 6.2 `_rdt_sample_to_trajectory_3d` / action semantics mismatch hypothesis (user H2)

**User's claim:** "In `_rdt_sample_to_trajectory_3d`, the use of `self._adapter.delta_actions_to_ee_trajectory(action_seq)` may be semantically incorrect for RDT, because RDT directly outputs end-effector delta actions (similar to pi0.5), rather than the kind of joint action sequence this conversion may assume."

**Refined analysis based on code evidence:**

The user's framing has the action types *inverted*. The actual situation:

| Aspect | Statement in code |
|---|---|
| `delta_actions_to_ee_trajectory` expects | **world-frame delta EEF + delta orientation + gripper** (libero_adapter.py:1411-1422, OSC convention) |
| pi05's denoising output (before postprocessor) | already in delta-EEF-style format (the postprocessor converts to LIBERO 7D action) |
| diffusion policy's denoising output | same — postprocessor maps to LIBERO action |
| RDT's denoising output (raw `x_t` at unified indices 0..6 after full denoising) | **absolute normalised Franka joint angles** ∈ [-1,1] (third_party/rdt/scripts/maniskill_model.py:154-195) |
| RDT's *final* LIBERO action (after `_postprocess_actions`) | LIBERO 7D OSC delta-EEF (derived via FK from the joint angles) |

So:
- The **adapter function expects delta-EEF** ✓ (user H2 partially correct).
- **RDT does not output delta-EEF**; it outputs absolute joint angles ✗ (user said "similar to pi0.5", but the relevant point is that *inside the denoising loop*, RDT's intermediate state `x_t` is in joint space, not EEF space).
- pi05 and diffusion get away with `delta_actions_to_ee_trajectory(sample-after-postprocessor)` because their post-processor converts the sample into LIBERO action form *before* the trajectory projection.
- RDT's `_rdt_sample_to_trajectory_3d` skips that conversion (and indeed *cannot* easily perform it — the FK-based converter is not differentiable in `chunk_np` and operates on numpy, not torch tensors).

**Repository evidence pattern:**
- pi05 trajectory path: `core/pi05_steer.py:336-349` — explicit `actions = self._postprocessor(sample)` before `delta_actions_to_ee_trajectory`.
- diffusion trajectory path: `core/diffusion_policy_steer.py:420-432` — same pattern.
- RDT trajectory path: `core/rdt_policy_steer.py:920-927` — no postprocessor call; raw `x_t` slice fed directly.

**Verdict on H2: directly supported and refined by code evidence.** The semantic mismatch is real; the precise mismatch is *joint-space x_t vs world-frame delta-EEF expectation*, not "joint actions vs delta-EEF actions" as the user phrased it. This mismatch propagates a coherent but geometrically meaningless gradient back into the denoising state, and the Jacobian-mediated downstream effect on EEF motion can plausibly produce a *systematic* direction error — including, for many Franka poses, a direction that is anti-parallel to the intended one.

---

## 7. Ranked list of most plausible steering-specific root causes

Ordering by *directness of code evidence* and *mechanistic match to the symptom* (consistent opposite-direction motion under guidance):

1. **FM-1 / FM-3 (same root cause, two views): semantic mismatch in `_rdt_sample_to_trajectory_3d`.** Directly evidenced by side-by-side comparison with `pi05_steer._sample_to_trajectory_3d` and `diffusion_policy_steer._sample_to_trajectory_3d`. The function passes joint-space `x_t` slices into an adapter that interprets them as world-frame delta-EEF deltas. The downstream gradient is mathematically well-defined but geometrically meaningless, and Jacobian-mediated coupling can produce a *consistent* signed direction error. This is the single most likely cause of the observed symptom.

2. **FM-6: unguided RDT prior already moves in the wrong direction.** Plausible but unconfirmed; requires a side-by-side comparison of guided vs unguided rollouts. If the unguided baseline already moves the wrong way, then FM-1's contribution is on top of that, and a different intervention (checkpoint, fine-tuning) is needed.

3. **FM-2: image orientation residual.** Plausible degradation source for *conditioning quality*. Mechanistically cannot by itself flip the *signed direction* of a world-frame gradient.

4. **FM-5: reward sign convention.** Same code-level sign convention as pi05, which works; unlikely to differ for RDT runs given the VLM agent is identical.

5. **FM-4: gradient slice mismatch.** Not currently a bug given `MANISKILL_INDICES[0:7] == [0..6]`; low priority.

---

## 8. Unknowns and evidence gaps

Things that cannot be resolved from static reading alone:

1. **Whether the unguided RDT+LIBERO rollout produces the same opposite-direction motion.** Needed to discriminate FM-1 from FM-6. *Investigation strategy*: run one episode with `use_guidance=false` from the same initial state and check the direction of the first 20–30 EEF position deltas relative to the would-be keypoint.

2. **Whether the gradient written into `noise_pred[..., :7]` actually changes the final denoised joint angles in any consistent direction.** *Investigation strategy*: at one fixed `x_t` and one fixed reward, log (a) the raw `kp_grad[:, :H, 0:3]`, (b) the difference `denoised_joint_after_guidance - denoised_joint_without_guidance` at unified indices 0/1/2, and (c) the resulting EEF position delta after one full chunk execution. A *consistent* relationship across multiple frozen states would localise the bug to the gradient-injection layer.

3. **Whether the start-pose Franka Jacobian J(q) at LIBERO's typical home pose actually has the sign structure that turns a "world +X" gradient into a "world −X" EEF motion via joint 1.** *Investigation strategy*: at a frozen `current_joints`, compute J(q) (via `franka_fk_pose` numerically perturbed) and check the column for joint 1 — its top component (∂eef_x / ∂q_1) sign tells whether a positive joint-1 bias moves the EEF +X or −X.

4. **Whether the live LIBERO image arriving at SigLIP is in fact upright (still UNKNOWN from prior audits — see `2026-05-11-rdt-libero-observation-semantic-chain.md` §E.3.1).** *Investigation strategy*: save one `images[3]` PIL from `_RDTModelAdapter.encode_inputs` and visually compare with the agentview MP4. Independent of the steering bug; informative for FM-2.

5. **Whether the VLM-generated reward function for a representative failing task actually encodes "minimise distance to keypoint" (rather than e.g. "minimise some weighted product" with a sign quirk).** *Investigation strategy*: open `episode_1/vlm_agent/.../stage1_guidance.txt` and read the function. Out of scope per §2 but worth a quick visual check.

None of these checks require code modification — only inspection and logging.

---

## 9. Suggested follow-up debug directions

Without proposing code patches, the investigation strategy with the highest information gain is:

1. **First: discriminate FM-1 from FM-6.** Run a single rollout with `policy.type=rdt main.use_guidance=false` from the same seed / task that produced the failing video. If the unguided EEF *already* moves in the opposite direction of the keypoint, the dominant problem is the *prior* (FM-6) and steering math fixes alone will not be enough. If the unguided EEF moves randomly or weakly but not consistently in the wrong direction, FM-1 (the steering math) is the dominant cause.

2. **Second: confirm the semantic mismatch is the gradient driver.** With guidance on, log `kp_grad[0, 0, 0:3]` (the gradient pushed into the joint-0/1/2 noise prediction) and `keypoint - current_eef` in world frame for one frame. Per the analysis in §4.7, these vectors should be *parallel* (with a positive proportionality up to the FK chain factor). If they are *parallel*, the gradient really is acting as a "Cartesian world delta" written into joint space — that is the smoking gun for FM-1/FM-3. The *consistent opposite-direction EEF motion* is then determined by the local sign of the Franka Jacobian; documenting that sign at the home pose closes the chain.

3. **Third: rule out FM-5 by inspecting one VLM-generated reward.** A quick read of `stage1_guidance.txt` confirms whether the function returns a (higher = better) reward or a (higher = worse) cost. The gradient sign convention in `_compute_keypoint_gradient` matches the pi05/diffusion convention, so as long as the VLM convention is uniform across policies, FM-5 is excluded.

4. **Fourth, only after the above:** revisit FM-2 (image orientation residual). It is on the same code path that was patched in commit `4bf90b7` and only matters for *conditioning quality*. It does not have a mechanism that flips world-frame steering signs.

**Note on the user-highlighted line 746 (`_predict_unguided`):** that function is *not* the steering path. It runs only when `use_guidance=false`. The steering-specific behaviour lives in `_guided_denoise_loop` (rdt_policy_steer.py:1038) and `_rdt_sample_to_trajectory_3d` (line 920). The selection of line 746 in the editor may have been a navigation choice rather than a code-pointer, but it is worth noting that `_predict_unguided` and `_guided_denoise_loop` are independent paths and the latter is the one being exercised in the failing experiment.

---

## Appendix A. Concrete sketch of the joint→EEF anti-alignment mechanism (for §4.7 / FM-1)

This appendix is a mechanism sketch, not a proof. It is intended only to motivate *why* the symptom can be **consistent**, not just "noisy".

With `reward = -‖p_H − k‖²` for keypoint `k` and trajectory end `p_H = p_0 + 0.01·Σ_{t=0..H-1} x_t[..., t, 0:3]`:

```
∂reward / ∂x_t[..., t, j]  =  2·(k_j − p_{H,j}) · 0.01     for j ∈ {0,1,2}, all t<H
```

So the gradient at unified indices 0/1/2 (which are the noise-prediction slots for `right_arm_joint_0_pos / _1_pos / _2_pos`) is proportional to `(k − p_0)_j`. The guidance update `noise_pred -= scale·grad` shifts the predicted `x_0` at those slots in the direction `+(k − p_0)`. After denormalisation, this corresponds to a joint-angle bias `Δq_j ∝ (k − p_0)_j · (action_max_j − action_min_j) / 2` for j ∈ {0,1,2}, with the *units of `(k − p_0)_j`* being metres but the *units of `Δq_j`* being radians — a categorical type error.

The resulting EEF velocity at the home pose is:

```
v_eef  ≈  J(q_home) · [Δq_0, Δq_1, Δq_2, 0, 0, 0, 0]ᵀ
```

For a Franka at typical LIBERO start configurations (q_1 ≈ -0.785 rad shoulder-down, q_3 ≈ -2.4 rad elbow-bent), the three columns of J(q) corresponding to joints 0, 1, 2 have sign structure that mixes world axes nontrivially:
- Column 0 (J·∂q_0 = base yaw): moves EEF mostly in world ±Y (perpendicular to forward), with sign depending on which side of base-X the EEF currently is.
- Column 1 (∂q_1 = shoulder pitch): moves EEF mostly in world ±X and ±Z. For a forward-reaching pose, increasing q_1 typically *pulls the EEF back* (in −X), opposite to the direction of an increase in target world-X.
- Column 2 (∂q_2 = elbow): also mixes world axes; sign depends on configuration.

The key qualitative point: **with `(k − p_0)` in world +X, the guidance writes positive Δq_1; the column-1 Jacobian at the home pose maps positive Δq_1 to negative world-X EEF velocity. The EEF therefore moves in −X while the keypoint is at +X.** This is a *deterministic*, *configuration-dependent* sign flip — fully consistent with the user's "consistently opposite across episodes" symptom, provided the start pose stays near the LIBERO home configuration (which it does — LIBERO resets to a fixed home each episode).

This is one of several possible sign-flip mechanisms induced by the type confusion in §4.5. The exact axis of the inversion depends on the specific Franka configuration; a consistent home pose is what makes it look consistent across episodes. A definitive check (per §8 item 3) is to compute the column-1 sign of J(q) at the LIBERO home pose using the existing `franka_fk_pose` (rdt_action_converter.py:68-86).

---

## End
