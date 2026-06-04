---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: feat/rdt-libero-gt-rollout-reintegration
source_commit: 360a6d052861
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/docs/docs/02_analysis/rdt_intergration/libero/2026-05-11-rdt-libero-observation-semantic-chain.md
summary: RDT-LIBERO Observation Semantic Chain — Source-Level Audit
duplicate_sources:
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/docs/02_analysis/rdt_intergration/libero/2026-05-11-rdt-libero-observation-semantic-chain.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/docs/docs/02_analysis/rdt_intergration/libero/2026-05-11-rdt-libero-observation-semantic-chain.md
---

# RDT-LIBERO Observation Semantic Chain — Source-Level Audit

**Date:** 2026-05-11
**Branch:** `feat/rdt-integration`
**Scope:** Observation path only. Action / converter / denoising / control logic explicitly out of scope.
**Companion docs:** `2026-05-09-rdt-libero-system-map-and-instrumentation.md`, `2026-05-09-rdt-libero-debug-status-review.md`

**Purpose:** Reconstruct, at the source level, the entire observation flow from the raw LIBERO simulator output through `RDTObsProcessor` to the inputs that `RoboticDiffusionTransformerModel.step()` / `_RDTModelAdapter.encode_inputs()` actually consume. Discriminate **FACT / INFERENCE / HYPOTHESIS / UNKNOWN** at every boundary so we can avoid hallucinating semantics during downstream debugging.

**Constraint:** No code changes, no fix proposals. This document is a read-only audit anchored in `file:line` citations.

---

# A. LIBERO Observation Source Map

## A.1 Which `LiberoEnv` is actually used

The repo contains **two** `LiberoEnv` class definitions:

- [`third_party/lerobot/src/lerobot/envs/libero.py:98`](../../../../third_party/lerobot/src/lerobot/envs/libero.py#L98) — LeRobot upstream variant. Returns nested `{"pixels": {...}, "robot_state": {...}}`.
- [`core/env_adapters/libero_adapter.py:383`](../../../../core/env_adapters/libero_adapter.py#L383) — **the in-tree variant actually used by `LiberoAdapter`**.

**FACT — only the in-tree variant matters at runtime.** `LiberoAdapter._env[idx]` is built from `OffScreenRenderEnv(**env_args)` at `libero_adapter.py:540`, and that `OffScreenRenderEnv` resolves to `libero.libero[redacted env file]s.OffScreenRenderEnv` from the conda site-packages.

## A.2 Raw observation from `OffScreenRenderEnv.step()`

Evidence: keys read in [`libero_adapter.py:558-592`](../../../../core/env_adapters/libero_adapter.py#L558-L592) plus `env_wrapper.py:277` (`_get_observations()`) in the conda-installed `libero` package.

| Field | Source | Shape | dtype | Semantics | Status |
|---|---|---|---|---|---|
| `agentview_image` | MuJoCo offscreen render | `(H, W, 3)` | `uint8` | Main view RGB | **FACT** (libero_adapter.py:564) |
| `robot0_eye_in_hand_image` | MuJoCo offscreen render | `(H, W, 3)` | `uint8` | Wrist camera RGB | **FACT** (libero_adapter.py:564) |
| `robot0_eef_pos` | controller readback | `(3,)` | `float64` | EEF position (m), world frame ≈ robot base frame (LIBERO places base at world origin) | **FACT** (libero_adapter.py:576, :911-913) |
| `robot0_eef_quat` | controller readback | `(4,)` | `float64` | EEF orientation quaternion, **xyzw** order (downstream `LiberoProcessorStep` treats `quat[:,3]` as `w` — env_processor.py:121) | **FACT for ordering** |
| `robot0_gripper_qpos` | sim.qpos | `(2,)` | `float64` | Two finger joint positions (m); per-finger Franka range ≈ `[0, 0.04]` | **FACT(shape)**; range is **INFERENCE** anchored by RDT `DATA_STAT` |
| `robot0_gripper_qvel` | sim.qvel | `(2,)` | `float64` | Finger velocities | **FACT(shape)** |
| `robot0_joint_pos` | sim.qpos | `(7,)` | `float64` | 7 Franka arm joint angles (radians) | **FACT(shape)**; unit-radians is **INFERENCE** (MuJoCo Franka convention) |
| `robot0_joint_vel` | sim.qvel | `(7,)` | `float64` | Joint velocities | **FACT(shape)** |

**Controller readback fields** (read directly by `LiberoAdapter`, *not* via `raw_obs`):
- `_env.robots[0].controller.ee_pos`, `controller.ee_ori_mat`, `robot._joint_positions` — see [`libero_adapter.py:888-925`](../../../../core/env_adapters/libero_adapter.py#L888-L925).

## A.3 MuJoCo image orientation — UNKNOWN at source

**FACT — there are flips downstream:**
- `LiberoProcessorStep._process_observation` applies `torch.flip(img, dims=[2,3])` (180° H+W flip) and the docstring calls it "the HuggingFaceVLA/libero camera orientation convention" ([env_processor.py:54-61](../../../../third_party/lerobot/src/lerobot/processor/env_processor.py#L54-L61)).
- `LiberoEnv.render()` does `image[::-1, ::-1]` for visualization ([libero_adapter.py:513](../../../../core/env_adapters/libero_adapter.py#L513)).

**UNKNOWN:** Whether the raw MuJoCo `sim.render()` returns the image upside-down, rotated 180°, or upright. `robosuite/utils/camera_utils.py:103` only inverts in the segmentation path; the RGB path has no in-source comment. Every downstream flip is justified by convention rather than a source-level statement of the upstream orientation.

## A.4 `LiberoEnv._format_raw_obs` output (what `LiberoAdapter` sees)

Source: [`libero_adapter.py:558-592`](../../../../core/env_adapters/libero_adapter.py#L558-L592). This is the **flat** dict that becomes `self._last_obs`:

```python
{
  "observation.images.image"  : torch.Tensor (1, 3, H, W) float32 in [0, 1],   # agentview
  "observation.images.image2" : torch.Tensor (1, 3, H, W) float32 in [0, 1],   # wrist
  "observation.robot_state"   : nested dict (torch tensors, leading batch dim 1):
       {"eef":    {"pos":  (1, 3) f64,
                   "quat": (1, 4) f64,   # xyzw — INFERENCE from LiberoProcessorStep usage
                   "mat":  (1, 3, 3) f64},
        "gripper": {"qpos": (1, 2) f64, "qvel": (1, 2) f64},
        "joints":  {"pos":  (1, 7) f64, "vel":  (1, 7) f64}}
}
```

Conversions:
- Image: `numpy (H,W,3) uint8 → torch.from_numpy().unsqueeze(0).permute(0,3,1,2).contiguous().float() / 255.0` (libero_adapter.py:567-571). **FACT**.
- Robot state: `_convert_nested_dict` wraps each numpy array as `torch tensor` and `unsqueeze(0)` (libero_adapter.py:60-78).
- Camera mapping: `agentview_image → "image"`, `robot0_eye_in_hand_image → "image2"` (libero_adapter.py:422-427). **FACT**.

## A.5 After `env_preprocessor` (`LiberoProcessorStep`)

Source: [`env_processor.py:49-82`](../../../../third_party/lerobot/src/lerobot/processor/env_processor.py#L49-L82).

```python
{
  "observation.images.image"  : (1, 3, H, W) float32 in [0,1]   # flipped 180°
  "observation.images.image2" : (1, 3, H, W) float32 in [0,1]   # flipped 180°
  "observation.state"         : (1, 8) float32 = [eef_pos(3), eef_axisangle(3), gripper_qpos(2)]
  "task"                      : List[str]                       # injected by get_policy_observation
}
```

- **FACT:** `observation.robot_state` is **deleted**, replaced by `observation.state` (env_processor.py:63-81).
- **FACT:** `observation.state` is **EEF pose + gripper qpos**, **not joint angles**; axis-angle is computed by `_quat2axisangle` (env_processor.py:115-154).
- **FACT:** Flip operates on `(B,C,H,W)` along `dims=[2,3]` (= H and W simultaneously).

---

# B. RDT Policy Expected Observation Map

## B.1 Official inference entry — `RoboticDiffusionTransformerModel.step(proprio, images, text_embeds)`

Source: [`third_party/rdt/scripts/maniskill_model.py:197-277`](../../../../third_party/rdt/scripts/maniskill_model.py#L197-L277).

### B.1.a `proprio`

| Property | Value | Evidence |
|---|---|---|
| Shape (entry) | `(1, 8)` | **FACT** — `eval_rdt_maniskill.py:101,125`: `proprio = obs['agent']['qpos'][:, :-1]` over ManiSkill Franka 9-qpos (7 arm + 2 fingers), slicing the last → `(B, 8)` |
| Internal shape after `unsqueeze(0)` | `(1, 1, 8)` | **FACT** — `maniskill_model.py:257`'s comment `(1, 1, 14)` is stale; the actual `_format_joint_to_state` input is `(1, 1, 8)` because `state_min/max` are length-8 |
| dtype | bf16 (after `.to(device, dtype=dtype)`) | **FACT** |
| Semantics of each dim | `[0..6]`: 7 Franka arm joint angles (rad); `[7]`: **finger-0** qpos `qpos[0]` ∈ `[0, 0.04]` m | **FACT** — `qpos[:, :-1]` keeps the first 8 of 9 dims; index 10 in `STATE_VEC_IDX_MAPPING` is `right_gripper_open` aliased to `right_gripper_joint_0_pos` (state_vec.py:11-17) |
| Numerical range (`DATA_STAT`) | 7-arm: per-joint training min/max; gripper: `[0.0, 0.04]` | **FACT** — `maniskill_model.py:28` |

**Internal transform** (`_format_joint_to_state`, maniskill_model.py:154-185):
1. `(joints - state_min) / (state_max - state_min) * 2 - 1` → normalize to `[-1, 1]`
2. Scatter into 128-D unified state vector at `MANISKILL_INDICES = [0,1,2,3,4,5,6,10]`
3. Emit `state_elem_mask` `(1, 128)` with 1s at those indices

### B.1.b `images`

| Property | Value | Evidence |
|---|---|---|
| Type | Python `list` length 6, each element `PIL.Image.Image` or `None` | **FACT** — `maniskill_model.py:219-249` iterates `for image in images` |
| Slot order | `[ext_{t-1}, right_wrist_{t-1}, left_wrist_{t-1}, ext_t, right_wrist_t, left_wrist_t]` | **FACT** — `eval_rdt_maniskill.py:110-116` `for window_img in obs_window: image_arrs.append(window_img); append(None); append(None)`, with `obs_window = deque(maxlen=2)` |
| History length | `img_history_size = 2` | **FACT** — `maniskill_model.py:64-65` |
| Camera count | `num_cameras = 3` (ext / right_wrist / left_wrist) | **FACT** (shape-only); ManiSkill checkpoint trained with cam_high only — wrist slots always empty per code comment |
| Per-image processing | Optional resize → `expand2square` padding with `image_mean*255` background → `image_processor.preprocess` (SigLIP-so400m-patch14-384) | **FACT** — `maniskill_model.py:234-249` |
| `None` slot | Replaced with `background_image` = solid `image_mean*255` | **FACT** — `maniskill_model.py:211-223` |
| Final tensor into `vision_model` | `(6, C, 384, 384)` bf16 | **FACT** — `maniskill_model.py:251-253` |

### B.1.c `text_embeds`

| Property | Value | Evidence |
|---|---|---|
| Shape | `(1, seq_len, 4096)` | **FACT** — T5-v1_1-XXL `last_hidden_state` (maniskill_model.py:142-152); d_model = 4096 |
| dtype | cast bf16 on entry to `step` | **FACT** — `maniskill_model.py:263` |
| Content | T5 **last_hidden_state** (token-level), not pooled | **FACT** |
| `lang_attn_mask` | All-ones of `text_embeds.shape[:2]`, generated inside `step` | **FACT** — `maniskill_model.py:267-269` |

## B.2 Training-path assumptions (corollary)

Not directly opened in this round. The shared constants `DATA_STAT` and `MANISKILL_INDICES` between training and inference imply training-time proprio was also `qpos[:, :-1]` of ManiSkill Franka 9-qpos. **INFERENCE**.

## B.3 Official vs custom-integration entry divergence

| Aspect | Official `RoboticDiffusionTransformerModel.step()` | Custom `_RDTModelAdapter.encode_inputs()` + `_predict_unguided` |
|---|---|---|
| Entry | `step(proprio, images, text_embeds)` does encode + denoise + denormalize in one | `encode_inputs(...)` only encodes; denoise loop separated in `RDTSteer._predict_unguided` |
| `proprio` shape | `(1, 8)`, internal `unsqueeze(0)` → `(1, 1, 8)` (maniskill_model.py:257) | Same — `rdt_policy_steer.py:259` (comment correctly says `(1, 1, 8)`) |
| `images` expectation | Length-6 PIL list, `_build_image_list` slot order | Identical; preprocessing block mirrors `maniskill_model.py:219-249` (`rdt_policy_steer.py:228-254`) |
| `text_embeds` expectation | `(1, seq, 4096)` | Same; `RDTObsProcessor.get_lang_embed` calls `real.encode_instruction` (`rdt_policy_steer.py:567-577`) |

**Key takeaway:** The (proprio, images, text_embeds) **interface itself does not bifurcate** between official and integration paths. All divergence is downstream of `encode_inputs` (denoising / post-processing — out of scope here).

---

# C. Observation Transformation Path

## C.1 End-to-end flow

```
robosuite OffScreenRenderEnv  (raw_obs dict, mostly numpy)
        │
        ▼
LiberoEnv._format_raw_obs       ── libero_adapter.py:558
   • numpy (H,W,3) uint8 → torch (1,3,H,W) float32 [0,1]
   • robot_state nested dict, all unsqueeze(0)
        │
        ▼
LiberoAdapter.step caches → self._last_obs    ── libero_adapter.py:1439
        │
        ▼
LiberoAdapter.get_policy_observation         ── libero_adapter.py:828
   • obs["task"] = [task_desc] * sample_num
   • env_preprocessor (LiberoProcessorStep):
        ─ images: torch.flip(dims=[2,3])  (180°)
        ─ robot_state → observation.state  (1, 8) = [eef_pos(3), axisangle(3), gripper_qpos(2)]
   • optional batch expansion
        │  obs dict
        ▼
RDTSteer.select_action(obs, generate_new_chunk=...)   ── rdt_policy_steer.py:622
        │
        ▼
RDTObsProcessor.process(obs)                  ── rdt_obs_processor.py:123
        │
        ▼
(images: list[6 PIL], proprio: torch(1,8), task_str: str)
        │
        ▼
get_lang_embed(task_str, device)              ── rdt_obs_processor.py:81
        │
        ▼
text_embed: torch (1, seq, 4096)
        │
        ▼
_RDTModelAdapter.encode_inputs(proprio, images, text_embed)   ── rdt_policy_steer.py:198
   • image_processor.preprocess + SigLIP encode
   • _format_joint_to_state on proprio
   • adapt_conditions
        │
        ▼
cond dict feeding the denoising loop  (out of scope this round)
```

## C.2 `RDTObsProcessor.process` step-by-step

Source: [`core/rdt_obs_processor.py:123-181`](../../../../core/rdt_obs_processor.py#L123-L181).

### C.2.1 Static camera

| Step | Code | Input | Output | Notes |
|---|---|---|---|---|
| 1. Take batch 0 | `static_t = obs[_STATIC_KEY][0]` (line 139) | `(B, 3, H, W) float32 [0,1]` | `(3, H, W)` | `_STATIC_KEY = "observation.images.image"` |
| 2. Undo flip (LIBERO only) | `_tensor_to_pil` runs `torch.flip(img, dims=[1,2])` (line 119) | `(3, H, W)` | `(3, H, W)` rotated back 180° | Gated by `_undo_libero_flip`, set in `RDTSteer.post_init:557-558` iff adapter is `LiberoAdapter` |
| 3. → uint8 numpy → PIL | `(img.clamp(0,1)*255).byte().permute(1,2,0).numpy() → Image.fromarray(...)` (line 120) | `(3, H, W) float` | `PIL Image (H, W, 3) uint8` | clamp + scale + channel-last reorder |
| 4. Resize | `.resize((384, 384), BILINEAR)` (line 121) | any PIL size | `(384, 384) PIL` | `RDT_IMG_SIZE = 384` |
| 5. Ring buffer | `ext_prev = self._prev_static if not None else ext_now`; `self._prev_static = ext_now` (lines 144, 147) | — | `ext_prev`, `ext_now` | First step: `ext_prev = ext_now` (self-duplication) |
| 6. Build list | `_build_image_list(ext_prev, ext_now)` → `[ext_prev, None, None, ext_now, None, None]` (lines 68, 149) | 2 PIL frames | length-6 list | Wrist slots forced `None` |

### C.2.2 Wrist camera — explicit discard

**FACT:** `observation.images.image2` is **never read**; slots 1, 2, 4, 5 are unconditionally `None` (`rdt_obs_processor.py:67-68`). Justification in the comment: "ManiSkill checkpoint was trained with cam_high only".

Downstream `_RDTModelAdapter.encode_inputs` replaces `None` with a `image_mean × 255` solid background (`rdt_policy_steer.py:230-231`).

### C.2.3 Proprio (8D)

Source: [`rdt_obs_processor.py:151-175`](../../../../core/rdt_obs_processor.py#L151-L175).

| Step | Code | Behavior | Source |
|---|---|---|---|
| Primary path gate | `if self._adapter and hasattr(adapter, 'get_joint_positions')` (line 155) | Use adapter direct-read | `_adapter` injected at `RDTSteer.post_init:555` |
| Joints | `joint_pos = self._adapter.get_joint_positions()` | `(7,) float64` Franka joints (rad) | libero_adapter.py:916-925: `robot._joint_positions.copy()` |
| Gripper raw | `gripper_raw = self._adapter.get_gripper_state()` | `float`, **sum of two finger qpos** | libero_adapter.py:927-942: `sum(gripper_qpos)` |
| Gripper scale | `gripper_val = float(gripper_raw) / 2.0`; `np.clip(gripper_val, 0.0, 0.04)` | sum/2 used as single-finger-equivalent | rdt_obs_processor.py:161-164 |
| Assemble | `proprio_np = np.zeros(8, f32)`; `[:7] = joint_pos[:7]`; `[7] = gripper_val` | `(8,) float32` | rdt_obs_processor.py:162-164 |
| → torch | `torch.from_numpy(proprio_np).unsqueeze(0)` | `(1, 8) torch` | rdt_obs_processor.py:175 |

**Fallback path** (`_fallback_proprio_from_state`, lines 183-195):
- Triggers only if `_adapter is None` or `get_joint_positions()` raises.
- Reads first 8 dims of `obs["observation.state"][0]`.
- ⚠️ Semantics: `observation.state` is `[eef_pos(3), axisangle(3), gripper_qpos(2)]` — meters/radians of EEF, NOT joint angles. Falling back here silently feeds EEF-pose values into the joint-angle slots of `_format_joint_to_state`.
- Under the live path the adapter is wired, so this should not trigger — but there is no runtime log confirming it.

### C.2.4 Task string

```python
task_list = obs.get("task", [""])
task_str = task_list[0] if isinstance(task_list, (list, tuple)) else str(task_list)
```

Origin: `LiberoAdapter.get_policy_observation:844-845` sets `obs["task"] = [self._env[idx].task_description] * sample_num`.

### C.2.5 Language embed

Source: [`rdt_obs_processor.py:81-114`](../../../../core/rdt_obs_processor.py#L81-L114).

- Priority: (1) preloaded cache → (2) `_text_encoder_fn` (wired in `RDTSteer.post_init:573-576` to `real.encode_instruction`) → (3) on-demand T5 load → (4) `torch.zeros(1, 1, 4096)` fail-safe.
- Output: `(1, seq_len, 4096)` `float32` on CPU; cast to device + bf16 inside `encode_inputs`.

### C.2.6 Final inputs to RDT (`encode_inputs`)

```
images   : list[6] of (PIL.Image 384×384 RGB | None)
proprio  : torch.Tensor (1, 8) float32   ← encode_inputs does unsqueeze(0) → (1, 1, 8) internally
text_emb : torch.Tensor (1, seq, 4096) float32 (CPU; cast to device+bf16 internally)
```

---

# D. Semantic Alignment Check

| Item | LIBERO source semantics | RDT expected semantics | Current processor mapping | Evidence | Status |
|---|---|---|---|---|---|
| **Image semantics (static)** | `agentview_image`: MuJoCo `agentview` RGB, LIBERO table-front oblique top-down | ManiSkill `cam_high`: SAPIEN top-oblique exterior camera | Take `observation.images.image[0]` as ext-camera | libero_adapter.py:564,422-425; rdt_obs_processor.py:139 | **PARTIAL** — both are "exterior top-down", but scene content, camera pose, renderer (MuJoCo vs SAPIEN), table appearance, training object set differ. **FACT-supported content-level MISMATCH** (domain gap). |
| **Image shape/layout** | `(H,W,3) uint8` from MuJoCo → adapter to `(1, 3, H, W) float32 [0,1]` → preprocessor preserves shape | `encode_inputs` expects PIL; internal `image_processor.preprocess` emits `(3, 384, 384)` bf16 | obs_processor clamp+permute+scale → PIL, resize to 384×384 | libero_adapter.py:567-569; rdt_obs_processor.py:120-121; rdt_policy_steer.py:248-254 | **MATCH** |
| **Image normalization range** | adapter emits `[0,1]` float32 | `image_processor.preprocess` internally normalizes from `0..255` uint8 PIL using SigLIP mean/std | obs_processor `clamp(0,1)*255 → uint8 PIL` rescales back into `[0,255]` for SigLIP | rdt_obs_processor.py:120 | **MATCH (on paper)** — only synthetic round-trip validated; live MuJoCo render not saved (audit doc F-3) |
| **Image orientation** | LiberoProcessorStep already `flip(dims=[2,3])` on `(B,C,H,W)` (180°) | RDT trained on upright SAPIEN exterior frames | `_undo_libero_flip=True` → `_tensor_to_pil` re-flips `(C,H,W)` along `dims=[1,2]` | env_processor.py:54-61; rdt_obs_processor.py:118-121; rdt_policy_steer.py:557-558 | **MATCH (synthetic)** — `h3_image_check` proves `flip∘flip=identity` on black image; **UNKNOWN on live frame** (F-3) |
| **Image batch dimension** | `(B, C, H, W)` after preprocessor | encode_inputs receives list of PIL (no batch); particle batch is on `x_t` in denoise loop | obs_processor uses `obs[_STATIC_KEY][0]` → drops batch dim; all particles share one frame | rdt_obs_processor.py:139 | **MATCH on shape**, **PARTIAL on multi-particle semantics** — all `sample_batch_size` particles condition on the same single frame (typical), but the batch dim of obs isn't propagated into the vision encoder |
| **Image history (`img_history_size=2`)** | LIBERO emits only current frame; no t-1 history | RDT expects `[ext_{t-1}, …, ext_t, …]` 6-slot list | obs_processor uses `_prev_static` ring buffer; first step `ext_prev = ext_now` | rdt_obs_processor.py:38, 144-147 | **PARTIAL** — first-step self-duplication is a common RDT data-pipeline fallback; **INFERENCE on whether ManiSkill training did exactly this**; UNKNOWN |
| **Wrist camera** | `observation.images.image2` always present | ManiSkill checkpoint trained with wrist slots empty (per comment) | obs_processor discards `image2`; slots 1,2,4,5 = `None` → encode_inputs substitutes SigLIP image_mean background | rdt_obs_processor.py:67-68; rdt_policy_steer.py:230-231 | **MATCH (on paper)** — comment-anchored; whether training-time wrist slot was image_mean / zeros / true black is **HYPOTHESIS** until the dataset preprocessing scripts are read |
| **Proprio semantics — arm joints** | `robot._joint_positions[:7]` (rad), Franka 7-DoF | `right_arm_joint_{0..6}_pos` (rad), Franka 7-DoF | adapter direct-read `robot._joint_positions.copy()`; obs_processor uses `[:7]` | libero_adapter.py:916-925; rdt_obs_processor.py:157,163; state_vec.py:1-8 | **MATCH (paper)** — both are Franka 7-DoF radians. Whether LIBERO and ManiSkill share identical joint zero/sign conventions is **UNKNOWN** (no per-joint zero-pose comparison evidence) |
| **Proprio semantics — gripper** | `robot0_gripper_qpos` `(2,)`: two Franka fingers, each ∈ `[0, 0.04]` m; `get_gripper_state()` = sum | RDT proprio[7] = `right_gripper_open` aliased to `right_gripper_joint_0_pos` (finger-0), ∈ `[0, 0.04]` per `DATA_STAT`; training uses `qpos[:, :-1]` of 9-qpos | obs_processor: `gripper_raw / 2`, clip to `[0, 0.04]` | rdt_obs_processor.py:161-164; state_vec.py:11-17; maniskill_model.py:28; eval_rdt_maniskill.py:101 | **PARTIAL — formula differs semantically** — official: `qpos[0]`; integration: `(qpos[0]+qpos[1]) / 2`. If Franka fingers are mimic-coupled (likely), values ≈ identical → **INFERENCE on equivalence**. **FACT that the formulas are different**; **HYPOTHESIS that the numeric result is close** |
| **Proprio dtype/shape** | adapter returns `np.float64 (7,)` + `float` scalar; obs_processor casts to float32 | `(1, 8) float32` into `encode_inputs` → internal `unsqueeze(0)` + cast bf16 | matches | rdt_obs_processor.py:162-175 | **MATCH** |
| **Proprio normalization** | LIBERO emits raw physical units (no normalization) | `_format_joint_to_state` does `(x - state_min)/(state_max - state_min)*2 - 1` with `DATA_STAT` | `encode_inputs` calls `real._format_joint_to_state(joints)`, reusing constants | rdt_policy_steer.py:260; maniskill_model.py:172 | **MATCH** — assumes LIBERO joint zero coincides with ManiSkill training zero; numerically plausible (state_min ≈ Franka joint limits) but not source-verified. **INFERENCE on shared zero-pose convention** |
| **EE-related semantics** | LiberoProcessorStep writes EEF axis-angle into `observation.state[3:6]` | RDT 8D proprio contains **no** EEF dims (EEF lives at indices 30-32 in state_vec but not in `MANISKILL_INDICES`) | obs_processor does NOT read `observation.state` on primary path; EEF info is dropped | rdt_obs_processor.py:155-164 | **MATCH (intentional discard)** — but if fallback triggers, `observation.state[:8]` is incorrectly fed as joints (meters/rad EEF in joint slots). **FACT-supported risk** conditional on fallback |
| **Observation batching** | Preprocessor output has batch dim 1; `get_policy_observation(sample_num)` can expand | RDTObsProcessor takes `[0]` (drops batch); encode_inputs is batch-free for images; denoise loop introduces particle batch via `x_t` | obs_processor uses only batch-0 frame + single proprio as condition for all particles | rdt_obs_processor.py:139,175; rdt_policy_steer.py:259 | **MATCH (intentional)** |
| **Time dimension in proprio** | LIBERO provides no history (per-step independent) | `_format_joint_to_state` accepts `(B, N, 8)` but `step` slices `states[:, -1:, :]` → N=1 | obs_processor emits `(1, 8)`; encode_inputs `unsqueeze(0)` → `(1, 1, 8)`, N=1 | rdt_obs_processor.py:175; rdt_policy_steer.py:259-263; maniskill_model.py:260 | **MATCH** |
| **Language token shape** | LIBERO `task_description` is a string, from `task.language` or BDDL | T5-XXL `last_hidden_state` `(1, seq, 4096)` bf16 | `RDTObsProcessor.get_lang_embed` → `real.encode_instruction(task_str)` yields matching shape | rdt_obs_processor.py:81-102; rdt_policy_steer.py:567-577; maniskill_model.py:142-152 | **MATCH** |
| **Language semantics** | LIBERO instruction strings (e.g. "pick up the alphabet soup and place it in the basket") | Trained on ManiSkill prompts (e.g. "Grasp a red cube and move it to a target goal position.") | LIBERO string flows through the same T5 verbatim | eval_rdt_maniskill.py:46-52 vs LIBERO BDDL `:language` field | **PARTIAL** — same encoder, but training/test vocabulary and structure differ → content domain gap. **FACT-supported as content gap**; shape-aligned |
| **Missing-field handling — proprio** | adapter always returns joint_pos/gripper_state unless internal exception | RDT requires 8D proprio | obs_processor `try/except` falls back to EEF-pose values (semantics broken) | rdt_obs_processor.py:155-172 | **PARTIAL — silent failure mode** — fallback keeps program running but swaps semantics without warning. **FACT-supported risk**; no runtime log indicates whether it fires |
| **Missing-field handling — image** | adapter always provides image / image2 | RDT accepts `None` (substitutes image_mean background) | image2 explicitly None; image has no fallback | rdt_obs_processor.py:139, 68 | **MATCH for current path** — missing image would `KeyError` at `obs[_STATIC_KEY]` (no graceful path) |
| **Missing-field handling — language** | adapter always populates `task_description` | RDT requires non-zero embedding | get_lang_embed exception path returns `torch.zeros(1, 1, 4096)` (degenerate — bf16 matmul becomes 0) | rdt_obs_processor.py:95-101 | **PARTIAL — silent failure mode** — the inline comment itself flags "wrong dim here causes mat-mul mismatch". Live audit shows `norm=16.98` (Fact 4), so not triggered in evidence runs — but no live instrumented confirmation |

---

# E. Evidence Gaps / Risk Points

## E.1 FACT-supported concerns

1. **Wrist camera dropped vs training-time wrist behavior** — Code drops `image2` and substitutes the SigLIP image_mean background (rdt_obs_processor.py:67-68; rdt_policy_steer.py:230-231). **FACT** for current runtime behavior; **HYPOTHESIS** for whether training-time wrist slots used the same image_mean tensor. `hdf5_maniskill_dataset.py` / preprocess scripts not opened this round.

2. **Proprio fallback semantics broken** — `_fallback_proprio_from_state` reads EEF-pose components from `observation.state[:8]` as joint angles (rdt_obs_processor.py:185-195). **FACT** that the path exists; **FACT** that it shouldn't trigger when adapter is wired; **UNKNOWN** whether it has silently triggered in any past episode — no logs.

3. **Gripper proprio formula differs from official** — Official: `qpos[0]` (finger-0). Integration: `(qpos[0]+qpos[1])/2`. **FACT** (code-readable); equivalence under symmetric-finger assumption is **HYPOTHESIS**.

4. **Image-flip fix validated only on synthetic** — H3 was confirmed via synthetic black-image round-trip (audit doc Fact 3); the flip is invariant on flat color. **FACT** that no live MuJoCo frame has been saved post-H3 for visual inspection. **FACT-supported concern**.

5. **`observation.state` remains in obs dict outside of fallback** — LiberoProcessorStep writes EEF pose under that key (env_processor.py:81). The current obs_processor reads it only in the fallback, but the key is still present and anything else downstream could mis-read it. **FACT**; latent risk.

## E.2 Mere hypotheses (need data to confirm)

1. **LIBERO Franka and ManiSkill Franka share identical joint zero / sign / order** — Numerically `state_min/max` look like reasonable Franka joint limits, but per-joint comparison evidence is absent.

2. **LIBERO MuJoCo `agentview` render is close to ManiSkill SAPIEN `cam_high` training distribution** — Renderer + scene differences; cannot be assessed from source.

3. **`_prev_static` first-step self-duplication matches training-time t-1 padding policy** — RDT training likely had real t-1 frames; whether self-duplication is the documented fallback isn't confirmed in dataset scripts.

4. **Franka fingers in LIBERO are mimic-coupled (always symmetric)** — Common URDF practice, but not confirmed in LIBERO/MuJoCo XML source.

## E.3 UNKNOWN due to missing evidence

1. **Raw MuJoCo `sim.render()` orientation** — Whether the upstream image is upside-down, rotated, or upright is undocumented in source comments. The entire flip chain's correctness depends on resolving this.

2. **Live `encode_instruction` output `seq_len`** — Only round-1 synthetic measured `norm=16.98`; the exact sequence length is not in the audit table.

3. **Whether `LiberoAdapter.get_joint_positions()` ever transiently fails between steps** — No try/except trigger logs.

4. **Live `task_description` strings actually fed to T5** — Need to dump BDDL `:language` per task; semantic distance from ManiSkill prompts is currently impressionistic.

5. ~~`observation.images.image[0]` layout after batch slicing~~ — Resolved: `LiberoEnv._format_raw_obs:569` does `permute(0,3,1,2)`, so it is `(1, C, H, W)`; `[0]` → `(C, H, W)`. **FACT**, not UNKNOWN. Retained here only as a note that this was previously ambiguous.

---

## Pointers for follow-up

- The two semantically-actionable inconsistencies on the observation chain are: **(a)** the gripper-proprio formula divergence (§C.2.3 / §D row "gripper"); **(b)** the image-flip not yet verified on a live frame (§E.1.4). Everything else is either MATCH or content-domain gap (out of reach without retraining/finetuning).
- To upgrade §E.1.1 (wrist slot content) from HYPOTHESIS toward FACT, read `third_party/rdt/data/hdf5_maniskill_dataset.py` and `data/preprocess_scripts/` for the wrist-slot fill convention at training time.
- To upgrade §E.2.4 (mimic-coupled fingers) toward FACT, inspect the LIBERO/MuJoCo Franka gripper XML (e.g. `panda_gripper.xml` in the conda libero package) for `<joint>` / `<equality>` definitions.
- Live instrumentation L2 in the companion audit doc (§E.1 of `2026-05-09-rdt-libero-system-map-and-instrumentation.md`) already proposes logging `proprio_np` and `source flag` at `rdt_obs_processor.py:175`, which would close §E.1.2 (fallback never triggered) and partially §D row "Proprio normalization" (live numeric range).
