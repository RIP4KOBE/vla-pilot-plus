# RDT-1B LIBERO Integration — Debugging Analysis

**Symptom:** `python main.py policy.type=rdt` runs without error, produces 10 episodes, 0/10 success. Robot actions appear completely random and task-unrelated.

**Context:** RDT-1B `robotics-diffusion-transformer/maniskill-model` was trained on the ManiSkill benchmark with a specific robot and action convention. LIBERO uses a Franka Panda arm with OSC (Operational Space Control) delta-EEF actions. The integration bridges these two worlds — and currently does so incorrectly in at least two critical ways.

---

## Root Causes (Highest Confidence)

### 1. Action Space Mismatch — Domain Incompatibility (P0)

**The core problem:** RDT-ManiSkill outputs **absolute joint-angle trajectories** in ManiSkill's joint space. LIBERO expects **normalized EEF-delta actions** from an OSC controller.

| | RDT-ManiSkill output | LIBERO expectation |
|---|---|---|
| Format | Absolute joint angles | EEF deltas (dx, dy, dz, droll, dpitch, dyaw, gripper) |
| Range | ManiSkill joint space (e.g. arm_j5: [1.83, 3.29] rad) | Normalized [-1.0, 1.0] |
| Dimension | 8D (7 joints + 1 gripper) | 7D |
| Control type | Joint-space position | OSC (Cartesian space) |

Trace: `_unformat_action_to_joint` denormalizes from ManiSkill `action_min/action_max` (values like 1.83–3.29 rad for joint 5) → values are sent to LIBERO's OSC controller → clamped to ±1 → extreme random-direction movements.

**Where to look:**
- `third_party/rdt/scripts/maniskill_model.py:193` — `_unformat_action_to_joint` applies `action_min/action_max` from `DATA_STAT`
- `core/rdt_policy_steer.py:626–633` — `_postprocess_actions` takes the first 7 dims (joints 0–6) of the already-joint-space output
- `core/env_adapters/libero_adapter.py:336–340` — `ACTION_DIM=7`, `ACTION_LOW=-1.0`, `ACTION_HIGH=1.0`
- `core/env_adapters/libero_adapter.py:1352` — adapter explicitly declares `'type': 'delta_ee_pose'`

**Quick verification:** Add `print("action_out:", action_chunk[0][0])` right before `self.adapter.step(...)` in `main.py:708`. Any values consistently outside [-1, 1] confirm this.

---

### 2. Proprioceptive State Mismatch — Wrong Coordinate Frame (P0)

**The core problem:** LIBERO's `observation.state` is EEF pose in Cartesian space. RDT's `_format_joint_to_state` treats it as joint angles in ManiSkill joint space.

**What LIBERO provides** (`LiberoProcessorStep`, `lerobot/processor/env_processor.py:68–75`):
```
observation.state = [eef_pos(3), eef_axisangle(3), gripper_qpos(2)]  # 8D Cartesian
```

**What RDT expects** (`_format_joint_to_state`, `maniskill_model.py:154–185`):
```
joints = [arm_joint_0..6(7), gripper(1)]  # 8D joint-angle space
```

Both happen to be 8D, so no dimension error is raised — but the semantics are completely wrong. The normalization then applies ManiSkill joint-angle min/max values (`DATA_STAT['state_min/max']`) to LIBERO EEF values:

Example: ManiSkill joint 5 range is [1.831, 3.290] rad (both positive). If LIBERO's EEF axis-angle component at that slot is 0.0 (neutral rotation), the normalized value becomes:
```
(0.0 - 1.831) / (3.290 - 1.831) * 2 - 1 ≈ -3.51   # far outside [-1, 1]
```

Out-of-distribution proprio conditioning → the model's denoising process has no meaningful state to condition on → actions are essentially prior samples = random.

**Where to look:**
- `core/env_adapters/libero_adapter.py:751–753` — `LiberoProcessorStep()` builds EEF-space state
- `third_party/rdt/scripts/maniskill_model.py:165–184` — normalization assumes joint-angle inputs
- `third_party/rdt/scripts/maniskill_model.py:28` — `DATA_STAT` encodes ManiSkill-specific ranges

**Quick verification:** Add `print("proprio_raw:", proprio, "normalized:", (proprio - model.state_min) / (model.state_max - model.state_min) * 2 - 1)` inside `step()`. Expect values far outside [-1, 1] for LIBERO inputs.

---

## Secondary Issues (Medium Confidence)

### 3. Missing Left-Wrist Camera (P1)

RDT expects 3 cameras per timestep × 2 history frames = 6 images. `RDTObsProcessor` provides:
```
[ext_{t-1}, rw_{t-1}, BLACK, ext_t, rw_t, BLACK]
```

The 3rd slot (left wrist) is always `_BLACK_PIL` (`core/rdt_obs_processor.py:129`). The model was trained with three real cameras. A permanently blank camera view degrades conditioning, though it is unlikely to explain completely random behavior by itself. During training, the `num_cameras: 3` config means the vision encoder always processed 3 views — feeding black images for one entire camera slot produces out-of-distribution visual features.

**Where to look:** `core/rdt_obs_processor.py:21,129` — `_BLACK_PIL` always fills left-wrist slot.

---

### 4. Language Embedding Path — Potential Zero Fallback (P1)

The log shows T5-XXL HTTP requests during model load (hf-mirror), suggesting T5 is downloaded fresh. The `_text_encoder_fn` wiring in `post_init` (`core/rdt_policy_steer.py:499–508`) tries to reuse the real model's `encode_instruction`. If this wiring fails silently (the `except Exception: pass` at line 507), the fallback path in `get_lang_embed` calls `_compute_t5_embed` which loads T5 again from scratch.

More importantly: if any exception occurs during T5 encoding at episode time, the fallback `torch.zeros(1, 1, 4096)` is returned — a zero language embedding gives the model no task signal, making all tasks look identical (and meaningless).

**Where to look:**
- `core/rdt_obs_processor.py:57–78` — `get_lang_embed` fallback returns zeros
- `core/rdt_policy_steer.py:499–508` — `_text_encoder_fn` wiring has a silent `except` that discards failures
- The main log only has 26 lines (all model loading) — zero lines from the episode loop itself, which means either the logger is misconfigured for this module, or the episode-level output is being suppressed

**Quick verification:** Add `print("lang_embed norm:", text_embed.norm().item())` in `select_action`. A value of 0.0 confirms the zero fallback is active.

---

### 5. Checkpoint Weight Loading Path (P1)

`from_pretrained` resolves `robotics-diffusion-transformer/maniskill-model/rdt` as a 3-part path, splitting it to `repo_id="robotics-diffusion-transformer/maniskill-model"` and `subdir="rdt"`. It then sets `pretrained_path = snapshot_root/rdt/` and searches for weight files in:
1. `pretrained_path/rdt/` (i.e. `snapshot/rdt/rdt/` — a double-`rdt` path that likely doesn't exist)
2. `pretrained_path/` (i.e. `snapshot/rdt/` — correct)

The search order (`rdt_subdir = os.path.join(pretrained_path, "rdt")`) means it checks the double-nested path first. If `snapshot/rdt/rdt/model.safetensors` doesn't exist, it falls back to `snapshot/rdt/model.safetensors`, which should be correct. But verify this is working — if `weight_file = None`, `create_model(args, pretrained=None, ...)` skips loading weights entirely, producing a randomly-initialized 1B parameter model.

**Where to look:**
- `core/rdt_policy_steer.py:416–439` — checkpoint path resolution and weight file search
- The log shows no "Loading weights from ..." message (only 26 httpx/dinov2 lines), which is suspicious — `load_pretrained_weights` prints this message. Either the logger level doesn't capture it, or `pretrained=None` was passed.

**Quick verification:** Add `print("weight_file:", weight_file)` before `create_model(...)` in `from_pretrained`. If `None`, the model is randomly initialized.

---

## Architecture-Level Issues (Fundamental Incompatibility)

### 6. ManiSkill vs LIBERO Embodiment Gap

Even if all implementation bugs were fixed, the RDT-ManiSkill checkpoint has a fundamental incompatibility with LIBERO:

- **Robot embodiment**: ManiSkill uses specific robots (e.g., WidowX); LIBERO uses Franka Panda
- **Action convention**: ManiSkill uses joint-space absolute actions; LIBERO uses EEF delta (OSC)
- **Normalization statistics**: `DATA_STAT` in `maniskill_model.py:28` is hard-coded for ManiSkill joint ranges
- **Task distribution**: ManiSkill manipulation tasks differ significantly from LIBERO tabletop tasks

The checkpoint was not fine-tuned on LIBERO data. Even a correctly implemented integration may perform poorly due to distribution shift. Random behavior, however, is caused by the implementation bugs above — not the distribution shift alone.

---

## Debugging Checklist (Priority Order)

```
[ ] 1. Verify weight loading: print weight_file path before create_model(); 
        check it's not None and the file exists on disk.

[ ] 2. Verify action values: print action sent to adapter.step() for first 5 steps.
        Expected (working): values ∈ [-1, 1]. 
        Actual (broken): values in joint-angle space (roughly -3 to 3 for some joints).

[ ] 3. Verify proprio normalization: print raw observation.state and
        _format_joint_to_state output. Expect out-of-[-1,1] values confirming #2 above.

[ ] 4. Verify language embedding: print text_embed.norm(). 
        Zero → zero fallback active; nonzero → T5 encoding working.

[ ] 5. Check episode-level logging: the main log only has 26 lines with no episode-step 
        output. Either SteerLogger level isn't captured by Hydra's file handler, 
        or print statements are needed for debugging.
```

---

## Recommended Fix Path

**If the goal is to get RDT working with LIBERO, at minimum you need:**

1. **Replace `_unformat_action_to_joint` denormalization** with denormalization into LIBERO EEF-delta space, OR implement an action conversion layer (joint-angle → EEF delta via FK/IK).

2. **Replace proprio input** with LIBERO joint angles (use `observation.joints.pos` directly instead of `observation.state` EEF) and either (a) re-encode using LIBERO-specific normalization statistics or (b) accept that ManiSkill normalization will be wrong until fine-tuned.

3. **Verify weight loading** to rule out random initialization.

4. **Add a second real camera** or accept performance degradation from the blank left-wrist slot.

A simpler short-term diagnostic: run RDT on ManiSkill (its native environment) first to confirm the checkpoint itself works correctly before debugging the LIBERO adaptation layer.
