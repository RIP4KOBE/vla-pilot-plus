# Test Failure Analysis: `python main.py main.use_guidance=true main.guide_scale=80`

**Run analyzed:** `outputs/libero/2026-04-21_04-09-32/`  
**Backend:** LIBERO (`libero_object` suite, pi05 policy)  
**Result:** 0/10 episodes succeeded (0.00% success rate)

---

## Executive Summary

The 0% success rate is caused by **multiple independent failure layers**, not a single root cause. Crucially, the guided run fails for the same reason as the unguided baseline (run `2026-04-21_03-01-49`, also 0%): the policy itself is not driving task success. The guidance system has its own critical bugs on top of this, meaning guidance is likely silently disabled entirely.

| Category | Severity | Finding |
|----------|----------|---------|
| Code Bug (Silent) | **Critical** | `start_time = None` — guidance conditions never fire |
| Code Bug (Explicit) | **High** | Episode 1 skipped: VLM returns `int` not `tensor` |
| Scale Mismatch | **High** | `ACTION_SCALE_POS` is 5× too small vs actual OSC controller |
| Config Issue | **High** | `sample_batch_size=1` disables FKD and diversity gradients |
| Policy Baseline | **Medium** | Pi05 also fails without guidance — 0% baseline rate |
| VLM Routing | **Low** | API calls routed through `api.poe.com`, not `api.openai.com` |

---

## Finding 1 — Critical Silent Bug: `start_time = None` Disables All Gradient Guidance

**File:** `core/pi05_steer.py:195`

```python
start_time = start_ratio if start_ratio is None else 0.8
```

**Config value:** `start_ratio: None` (from `.hydra/config.yaml` line `start_ratio: None`)

**What this evaluates to:** In YAML/OmegaConf, `None` is treated as Python `None`. The expression:
```
None if (None is None) else 0.8
= None if True else 0.8
= None
```

So `start_time = None`.

**Intended logic vs actual logic:**

| | Code (intended meaning) | Actual |
|---|---|---|
| `start_ratio=None` | Use default `0.8` | Returns `None` |
| `start_ratio=0.5` | Use `0.5` | Returns `0.8` |

The ternary is **inverted**. The correct code should be:
```python
start_time = start_ratio if start_ratio is not None else 0.8
```

**Consequence:** With `start_time = None`, the two guidance branches in the flow-matching loop become:

```python
# Line 228
if use_diversity and time > start_time and bsize > 1:
#                        ^^^^^^^^^^^^^^
#                        time (float tensor) > None → undefined/always False
#                        This branch never fires (bsize=1 anyway)

# Line 233
elif use_keypoint_guidance and time <= start_time:
#                                   ^^^^^^^^^^^^^^
#                                   tensor <= None → undefined/always False
#                                   This branch NEVER fires
```

The comparison `torch.Tensor <= None` behaves unpredictably. PyTorch tries to convert `None` to a scalar for comparison; it either raises a silent TypeError (absorbed by the `except Exception` in `_compute_keypoint_gradient` at line 404) or evaluates to False. **In either case, `_compute_keypoint_gradient` is never called.** Guidance is completely inactive regardless of `use_guidance=True`.

**Evidence:** Comparing run with guidance (04:09) vs baseline without guidance (03:01) — both produce identical 0% success. If guidance were active, the trajectories would differ.

---

## Finding 2 — Explicit Error: Episode 1 Skipped (VLM Returns `int` Not `tensor`)

**File:** `outputs/libero/2026-04-21_04-09-32/episode_1/error.txt`

```
ValueError: Guidance function validation failed for .../stage2_guidance.txt (function 0):
Function 0 returned <class 'int'>, expected torch.Tensor
```

**VLM-generated code (`episode_1/vlm_agent/stage2_guidance.txt`):**
```python
def stage2_guidance(keypoints, action_sequence):
    # No need for guidance since placement in the basket is straightforward
    return 0   # ← plain Python int, not torch.Tensor
```

The VLM prompt (`vlm_query/guidance_template_libero.txt`) instructs: *"For pick something into basket, just return 0"* but does **not** specify that the return value must be `torch.tensor(0.0, device=...)`. The other 9 episodes correctly return `torch.tensor(0.0, device=action_sequence.device)`, so this is a probabilistic VLM generation failure.

`guidance_utils.py:145` catches this and raises `ValueError`, which propagates to `main.py:383` (guidance loading step), causing Episode 1 to be skipped entirely with status `preparation error`.

---

## Finding 3 — Scale Mismatch: Trajectory Predictions Are 5× Too Small

**File:** `core/env_adapters/libero_adapter.py:1395`

```python
ACTION_SCALE_POS = 0.01  # meters per normalized action unit
```

**Actual LIBERO/robosuite OSC controller default** (`robosuite/controllers/osc.py`):
```python
output_max=(0.05, 0.05, 0.05, ...)  # 0.05 m per action unit for position
```

The gradient guidance uses `delta_actions_to_ee_trajectory()` to convert raw action samples into predicted 3D end-effector trajectories, then differentiates through this trajectory to produce a gradient on the action space. Because the scale is hardcoded at `0.01` instead of `0.05`:

- The predicted trajectory covers **1/5 the physical distance** of what the robot will actually move
- The reward gradient is computed against a trajectory that is 5× compressed in space
- Even if guidance were active, the gradient direction would point toward a scaled-down proxy target, not the real physical target position

**Also:** The `env_postprocessor` pipeline for LIBERO (line 752-755) applies no additional steps — zero-length `env_postprocessor_steps` — so there is no compensating transform.

---

## Finding 4 — Config Issue: `sample_batch_size=1` Disables FKD and Diversity

**Config:** `main.sample_batch_size: 1`

Two algorithm components are explicitly gated on `bsize > 1`:

**Diversity gradient** (`pi05_steer.py:412`):
```python
def _compute_diversity_gradient(self, sample, verbose=False):
    batch_size = sample.shape[0]
    if batch_size < 2 or self._adapter is None:
        return None   # ← always returns None with bsize=1
```

**FKD initialization** (`pi05_steer.py:300`):
```python
def _init_fkd(self, fkd_config, bsize, ...):
    if fkd_config is None or bsize <= 1 or ...:
        return None   # ← always returns None with bsize=1
```

With `sample_batch_size=1`, both FKD particle resampling and diversity gradient spread are disabled. The config also sets `use_fkd: true` and `use_diversity: true`, creating misleading intent vs. actual behavior. The only remaining mechanism would be the keypoint gradient — which Finding 1 shows is itself disabled.

**Additionally:** Even if `sample_batch_size` were raised to, say, 16, the FKD and diversity would compete with each other and with keypoint guidance in the single diffusion loop. The comment on line 158 describes them as mutually exclusive phases (`time > start_time` vs `time <= start_time`), but with `start_time=None` this partitioning is broken.

---

## Finding 5 — Policy Baseline: Pi05 Also Fails Without Guidance

**Run `2026-04-21_03-01-49`** (same config, `use_guidance: false`): **0/10 success**

All earlier runs (`2026-04-20_13-51-49`, `2026-04-21_03-01-49`) also show 0%. The pi05 policy cannot solve LIBERO tasks even without any guidance or steering involved. This means even if Findings 1–4 were fixed, the success rate might still be 0%.

**Potential sub-causes (require further investigation):**

### 5a. Wrong `ACTION_SCALE_POS` Affects Execution, Not Just Reward
The `ACTION_SCALE_POS=0.01` bug (Finding 3) affects the reward computation, but the actual actions sent to the environment go through `step()` with the raw policy output after unnormalization. If the unnormalized actions are reasonable but `delta_actions_to_ee_trajectory` underestimates them 5×, the **reward is computed against wrong positions** but actions executed are correct. However, this could also mean the robot takes valid steps but the guidance is incoherent.

### 5b. State Observation Format
Pi05 was trained on LIBERO 8-dim state: `[eef_pos(3), eef_quat_xyzw(4), gripper(1)]`. The LiberoAdapter at inference feeds exactly this format (per previous adapter fixes in this session). If the quaternion convention or normalization differs from training, the policy will produce consistently wrong actions even on correct tasks.

### 5c. VLM Keypoint Index Misalignment
Episode 2 guidance uses `keypoints[0]` (cream_cheese_1_main). However, keypoint indices are assigned by DINOv2 feature clustering and may differ per episode. If the guidance correctly identifies cream_cheese at index 0 in the **query image** but the tracker drifts and cream_cheese moves to index 2 by step 50, the gradient pulls the gripper toward the wrong object.

---

## Finding 6 — VLM API Routed Through Poe Proxy

**From `main.log`:**
```
HTTP Request: POST https://api.poe.com/v1/chat/completions "HTTP/1.1 200 OK"
```

**Config says:**
```yaml
vlm_agent:
  base_url: null
  model: gpt-4o
```

The request goes to `api.poe.com` (a third-party proxy), not `api.openai.com`. This is determined by the `OPENAI_API_KEY` or `base_url` in `.env`, not by the config file shown. Poe proxies may:
- Return GPT-4o outputs with slightly different behavior (e.g., more likely to generate `return 0` vs `return torch.tensor(0.0, ...)`)
- Have different rate limits, context handling, or system prompt injection

This is a low-severity finding but worth noting as a non-standard VLM configuration.

---

## Finding 7 — VLM Stage2 Functions Are Universally Trivial

Across all episodes that successfully loaded guidance, the stage2 function always returns zero:

- Episode 1: `return 0` (crashes)
- Episodes 2–10: `return torch.tensor(0.0, device=action_sequence.device)`

This is by design (the prompt says "for pick-into-basket, just return 0"), but it means **stage 2 has no guidance**. If the policy fails to grasp at stage 1, stage 2 provides no corrective signal. The guidance only acts during stage 1 (grasping), and only when the stage recognizer correctly identifies the stage — which itself depends on the reward being positive (which depends on Finding 3).

---

## Summary: Complete Failure Chain

```
python main.py main.use_guidance=true main.guide_scale=80
      │
      ├─► Episode 1 preparation error
      │     VLM generates `return 0` (int) in stage2_guidance.txt
      │     guidance_utils.py:145 raises ValueError → episode skipped
      │
      └─► Episodes 2–10: guidance silently disabled, policy runs unguided
            │
            ├─► start_ratio=None → start_time=None (pi05_steer.py:195, INVERTED TERNARY)
            │     time <= None → always False → _compute_keypoint_gradient never called
            │     time > None → always False → diversity gradient never applied
            │
            ├─► sample_batch_size=1 → FKD returns None (needs >1 particles)
            │     use_fkd=true is set but has zero effect
            │
            ├─► ACTION_SCALE_POS=0.01 vs OSC controller 0.05 (5× mismatch)
            │     If guidance WERE active, reward gradients computed against wrong scale
            │
            └─► Pi05 baseline policy: 0% without guidance (same as guided run)
                  Root cause unclear: may be action scale, state format, or model checkpoint issue
```

---

## Required Fixes (in priority order)

1. **Fix `start_time` ternary** (`pi05_steer.py:195`):
   ```python
   # Wrong:
   start_time = start_ratio if start_ratio is None else 0.8
   # Correct:
   start_time = start_ratio if start_ratio is not None else 0.8
   ```

2. **Fix `ACTION_SCALE_POS`** (`libero_adapter.py:1395`):
   ```python
   ACTION_SCALE_POS = 0.05  # Match robosuite OSC controller default output_max
   ```

3. **Increase `sample_batch_size`** to enable FKD/diversity (e.g., 10–20).

4. **Fix VLM prompt** (`guidance_template_libero.txt`) to require `torch.tensor` return:
   ```
   For tasks where no stage 2 guidance is needed, return:
       return torch.tensor(0.0, device=action_sequence.device)
   Never return a plain Python int like `return 0`.
   ```

5. **Debug pi05 policy baseline** independently (run 10 episodes with `use_guidance=false` and verbose action logging to verify the robot is physically moving toward objects).
