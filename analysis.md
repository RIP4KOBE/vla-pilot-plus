# RDT-1B LIBERO Behavior Analysis

**Run:** `outputs/libero/2026-04-26_07-02-30` — 0/10 success, `use_guidance=false`

---

## 1. Reproduction & Expected Behavior

### What should happen
`python main.py policy.type=rdt` loads the ManiSkill RDT-1B checkpoint, encodes each observation (SigLIP images + T5 lang + proprio), runs 55-step DPM-Solver denoising, and sends 8-step action chunks to LIBERO. The robot should at minimum move purposefully toward the target object.

### What happens
0/10 episodes succeed. The video shows random-looking movement not aligned with the instruction. No Python exceptions are raised.

### Key observations from artifacts
- Model loaded cleanly: T5 (snapshot `3db67ab1...`), SigLIP, RDT weights — no errors
- Language embeds in `data/rdt_lang_embeds/` are non-zero, correct shape `[1, seq_len, 4096]`
- Config: `use_guidance: false`, `sample_batch_size: 20`, `action_chunk_horizon: 8`
- The only runtime log is from dinov2 and httpx — no `[RDTSteer]` output at all (guidance off, no reward logs)

---

## 2. Quick Triage Checklist (10–15 min)

Run these in order; stop at the first confirmation:

- [ ] **T1** Print one raw action vector before `adapter.step()`. Any value `|v| > 1.0` confirms action-space mismatch.
- [ ] **T2** Print `obs["observation.state"][0]` shape and values at the first step. Values in `[0.4, 0.6]` range (EEF pos) vs `[−2.6, 3.3]` (joint angles) confirm proprio format.
- [ ] **T3** Print `proprio_np` inside `RDTObsProcessor.process()` before it is returned. Check values against `DATA_STAT state_min/state_max`.
- [ ] **T4** Print the normalized proprio after `_format_joint_to_state` — expect `[-1, 1]`. Values far outside confirm normalization failure.
- [ ] **T5** Confirm weight file was actually loaded (not random init): print `real_model.policy.model.state_dict()` for one weight and verify it is not all-zeros or all-random.

---

## 3. Hypotheses (ranked by likelihood × impact)

### H1 — Action output in ManiSkill joint-angle space, LIBERO expects [-1, 1]  ★★★★★

**Confidence:** Very high (code-confirmed)

`_unformat_action_to_joint` in `maniskill_model.py:191`:
```python
joints = (joints + 1) / 2 * (self.action_max - self.action_min) + self.action_min
```
This converts the model's normalized `[-1, 1]` predictions to raw ManiSkill joint angles. Example: joint 5 action range is `[1.829, 3.291]` — these values land in LIBERO's `[-1, 1]` action space as clipped maximum velocity, producing uncontrolled movement.

`DATA_STAT['action_min']` = `[-0.747, -0.086, -0.500, -2.658, -0.575, 1.829, -2.245, -1.0]`
`DATA_STAT['action_max']` = `[0.765, 1.498, 0.468, -0.382, 0.552, 3.292, 2.576, 1.0]`

LIBERO `ACTION_LOW = -1.0`, `ACTION_HIGH = 1.0` — completely incompatible range.

**Observable signal:** Any `|action[i]| > 1.0` at the LIBERO step boundary.

**Test (no code edit):**
```bash
python -c "
import sys; sys.path.insert(0, 'third_party/rdt')
from scripts.maniskill_model import DATA_STAT
import numpy as np
amin = np.array(DATA_STAT['action_min'])
amax = np.array(DATA_STAT['action_max'])
# Simulate a normalized prediction of all zeros (model center)
action_norm = np.zeros(8)
action_denorm = (action_norm + 1) / 2 * (amax - amin) + amin
print('Denormalized zero-prediction:', np.round(action_denorm, 3))
print('Out of [-1,1] on dims:', np.where((action_denorm < -1) | (action_denorm > 1))[0])
"
```

Expected outcome: several dims outside `[-1, 1]`, confirming the mismatch.

**Root cause:** `step()` in `maniskill_model.py` always applies `_unformat_action_to_joint`. Our `_predict_unguided` is a passthrough to `real.step()`, which carries out the denormalization. The resulting actions are then directly passed to `LiberoAdapter.step()` without re-normalization.

---

### H2 — Proprioception format mismatch: LIBERO provides EEF state, RDT expects joint angles  ★★★★★

**Confidence:** Very high (code-confirmed)

`LiberoProcessorStep._process_observation()` builds `observation.state` as:
```
[eef_pos(3D), eef_axisangle(3D), gripper_qpos(2D)]  →  shape (1, 8)
```
These are Cartesian EEF coordinates + orientation (e.g., `eef_pos ≈ [0.4, 0.0, 0.5]`).

`RDTObsProcessor.process()` then fills:
```python
proprio_np[:7] = state[:7]   # interprets EEF fields as joint angles 0-6
proprio_np[7]  = state[7]    # gripper qpos[1] as gripper joint
```

`_format_joint_to_state` normalizes with ManiSkill joint stats:
```
state_min[1] = -0.080   (ManiSkill joint 1 min)
# but LIBERO eef_axisangle[0] ≈ -π ... π
```
Cartesian values like `eef_pos[0] = 0.4 m` fed into joint-angle normalizer (range `[-0.747, 0.765]`) → normalized value ≈ `0.049` (accidentally in range). But axis-angle can be `±π ≈ ±3.14`, while joint 3 range is `[-2.658, -0.387]` → normalized value ≈ `2.8` (wildly out of range).

**Observable signal:** Print `state_raw` in `encode_inputs` just before `_format_joint_to_state`. Values not in `[state_min, state_max]` confirm mismatch.

**Test:**
```bash
python -c "
import sys; sys.path.insert(0, 'third_party/rdt')
from scripts.maniskill_model import DATA_STAT
import numpy as np
smin = np.array(DATA_STAT['state_min'])
smax = np.array(DATA_STAT['state_max'])
# Simulate a LIBERO observation.state (EEF space)
libero_state = np.array([0.45, 0.02, 0.51,   # eef_pos
                          0.0, 0.0, 3.1,        # eef_axisangle (near π)
                          0.04, 0.04])           # gripper qpos
normalized = (libero_state - smin) / (smax - smin) * 2 - 1
print('Normalized LIBERO state as joint angles:', np.round(normalized, 2))
print('Values outside [-1,1]:', np.sum(np.abs(normalized) > 1), '/ 8 dims')
"
```

Expected: 3–5 dims outside `[-1, 1]`, proving the model receives garbage proprioception.

**Root cause:** LIBERO uses EEF-space observations; RDT ManiSkill was trained on raw Panda joint angles. `LiberoProcessorStep` concatenates EEF pos + axis-angle + gripper, not joint positions. `observation.state[0]` is never raw joint angles. LIBERO's `raw_obs["robot0_joint_pos"]` is available but not surfaced via `observation.state`.

---

### H3 — Domain shift: ManiSkill checkpoint never trained on LIBERO distribution  ★★★☆☆

**Confidence:** Certain (by design), but severity relative to H1/H2 is secondary

The RDT ManiSkill checkpoint was trained on ManiSkill tabletop tasks (peg insertion, object pick-and-place with a simulated xArm/Panda in a white-background scene). LIBERO uses Franka with a tabletop kitchen scene, different lighting, and task language ("pick up the alphabet soup…" vs "PegInsertion").

Even with correct normalization (fixing H1 and H2), the model may exhibit poor performance due to visual domain shift, action distribution shift, and task language shift. However, "totally random" behavior is unlikely to be caused by domain shift alone — domain shift causes **worse** task success, not random jitter.

**Observable signal:** After fixing H1+H2, if success rate is still ~0% but actions are purposeful-looking, domain shift is the residual cause.

---

### H4 — Language conditioning: LIBERO task keys not in precomputed embed cache, T5 fallback path  ★★★☆☆

**Confidence:** Medium

`data/rdt_lang_embeds/` contains 11 `.pt` files computed via full T5-XXL. These include the LIBERO task strings (verified: `08d110...` = "pick up the alphabet soup…"). However, `RDTObsProcessor` does **not** call `load_embedded_tasks` at `post_init` time — the on-disk cache is never loaded into `_lang_cache`. Every run re-encodes via `_text_encoder_fn` → `real.encode_instruction(s, device=_d)`.

This is only a bug if `encode_instruction` is slow or returns a different encoding than the cached version. Since the cached embeds have non-zero, realistic norms, and T5 is deterministic for the same input, the live encoding should match.

**Risk:** If `encode_instruction` silently returns all-zeros or fails, guidance sees a zero language condition. Add a norm print to verify.

**Test:**
```bash
python -c "
import torch
cache_dir = 'data/rdt_lang_embeds/'
import os, hashlib
task = 'pick up the alphabet soup and place it in the basket'
key = hashlib.md5(task.encode()).hexdigest()
f = os.path.join(cache_dir, f'{key}.pt')
t = torch.load(f, map_location='cpu', weights_only=True)
print(f'Cached embed: shape={t.shape}, norm={t.norm():.3f}, zeros={t.eq(0).all()}')
"
```

---

### H5 — Image preprocessing: flip applied by LiberoProcessorStep, wrong orientation fed to SigLIP  ★★☆☆☆

**Confidence:** Low–medium

`LiberoProcessorStep` flips images 180° (`torch.flip(img, dims=[2, 3])`) to match HuggingFaceVLA convention. If RDT ManiSkill was trained on non-flipped camera images, the flipped images create a visual domain mismatch. The robot's arm would appear on the wrong side, causing persistent mislocalization.

**Observable signal:** Check whether saved episode video frames look correctly oriented (arm visible, objects in frame). If the scene appears upside-down, the flip is wrong.

**Test:** Open `episode_1/episode_1_fail_agentview.mp4` visually and check orientation.

---

### H6 — Weight loading failure: checkpoint not found, model ran with random weights  ★☆☆☆☆

**Confidence:** Low (loading succeeded per log)

The log shows the checkpoint download resolved to `.../snapshots/9622afab2b7ce2312a6cf1febc526928589b77eb/rdt`. `from_pretrained` searches for `model.safetensors` or `pytorch_model.bin` in `search_dirs = [rdt_subdir, pretrained_path]`. If neither was found, `weight_file = None` and `create_model(args, pretrained=None)` → random init.

**Test:**
```bash
python -c "
import os
snap = '/mnt/data/hf_cache/hub/models--robotics-diffusion-transformer--maniskill-model/snapshots/9622afab2b7ce2312a6cf1febc526928589b77eb'
for fname in ('model.safetensors', 'pytorch_model.bin', 'rdt-1b.pt'):
    for d in [os.path.join(snap,'rdt'), snap]:
        p = os.path.join(d, fname)
        exists = os.path.exists(p)
        if exists:
            print(f'FOUND: {p} ({os.path.getsize(p)//1e6:.0f} MB)')
"
```

---

### H7 — Control frequency / action scale: 25 Hz assumed, LIBERO runs at different rate  ★★☆☆☆

**Confidence:** Low (secondary effect)

RDT embeds `ctrl_freqs = [25]` Hz as a conditioning token. LIBERO runs at whatever rate the episode loop drives. If LIBERO runs at 10 Hz, the model was trained to produce actions for 25 Hz execution but they are executed 2.5× slower — position-control commands will be too small per timestep (under-shoot), though this causes slow/weak movement rather than random movement.

---

## 4. Evidence to Collect

| Signal | Where to find it | What to look for |
|---|---|---|
| Raw action values sent to LIBERO | Add `print(action)` before `adapter.step(...)` in `main.py:708` | Any `|v| > 1.0` → H1 confirmed |
| `observation.state` shape/values | Print `obs["observation.state"][0]` in `_get_policy_observation` | EEF coords (~0.3–0.6 m) vs joint angles (~0–3 rad) |
| Normalized proprio sent to model | Print in `encode_inputs` after `_format_joint_to_state` | Values far outside `[-1, 1]` → H2 confirmed |
| Lang embed norm at inference | Print `text_embed.norm()` in `select_action` | Should be ~18–21 (matching cached); 0 → fallback triggered |
| Image orientation in video | Open `episode_1/episode_1_fail_agentview.mp4` | Scene upside-down → H5; normal → H5 ruled out |
| Weight file existence | Check `search_dirs` for weight file | Absence → H6 |
| Action output from `step()` shape | Print `out.shape` in `_predict_unguided` | `(1, 64, 8)` with values in `[action_min, action_max]` range → H1 |

---

## 5. Decision Tree / Next Actions

```
START
│
├─ T1: Print action before adapter.step() — any |v| > 1?
│   ├─ YES → H1 confirmed.
│   │         Fix: skip `_unformat_action_to_joint` or re-normalize to [-1,1].
│   │         The action returned by step() is already in ManiSkill joint space.
│   │         Option A: pass the normalized [-1,1] output directly (bypass _unformat).
│   │         Option B: re-normalize: (action - action_min) / (action_max - action_min) * 2 - 1
│   │         → After fix, continue to T2.
│   │
│   └─ NO → (unexpected) Continue to T2.
│
├─ T2: Print observation.state[0] at first step.
│   ├─ Values like [0.4, 0.0, 0.5, 0.0, 0.0, π, ...] (EEF space)?
│   │   → H2 confirmed.
│   │     Fix: use `raw_obs["robot0_joint_pos"]` (7D joint angles) instead of
│   │     the preprocessed `observation.state` (EEF). Either modify
│   │     RDTObsProcessor to extract joint_pos directly, or expose it via adapter.
│   │
│   └─ Values like [-0.3, 0.8, ...] (joint angles in radians)?
│       → H2 not the issue, continue to T3.
│
├─ T3: After fixing H1 and H2, re-run and check lang embed norm.
│   ├─ Norm ≈ 0 → language conditioning failed → fix T5/embed path.
│   └─ Norm ≈ 18–21 → language OK → continue to T4.
│
├─ T4: After H1+H2 fixes, inspect video for orientation.
│   ├─ Scene upside-down → H5: remove 180° flip for RDT path.
│   └─ Scene correct → H5 ruled out.
│
├─ T5: With H1+H2+H5 addressed, run 10 episodes.
│   ├─ Success rate > 0% → pipeline correct, residual is domain shift (H3).
│   └─ Still 0%, actions look purposeful → domain shift is primary; ManiSkill checkpoint
│       may not transfer to LIBERO without fine-tuning.
│
└─ Throughout: verify weight file found (T from Section 2, T5).
    └─ Not found → add explicit error log to from_pretrained.
```

---

## 6. Appendix: Commands

```bash
# A1: Confirm action denorm range mismatch
python -c "
import sys; sys.path.insert(0, 'third_party/rdt')
from scripts.maniskill_model import DATA_STAT
import numpy as np
amin = np.array(DATA_STAT['action_min'])
amax = np.array(DATA_STAT['action_max'])
for v in [-1.0, 0.0, 1.0]:
    d = (v + 1)/2 * (amax - amin) + amin
    print(f'norm={v:+.1f} → denorm={np.round(d,3)}')
print('LIBERO expects all in [-1,1]; ManiSkill denorm maps outside for most dims')
"

# A2: Confirm LIBERO observation.state is EEF space
python -c "
from lerobot.processor.env_processor import LiberoProcessorStep
import inspect
src = inspect.getsource(LiberoProcessorStep._process_observation)
# Look for what gets concatenated into observation.state
import re
cats = re.findall(r'cat\(.*?\)', src, re.DOTALL)
print('State components:', cats)
"

# A3: Check weight file is found
python -c "
import os
snap = '/mnt/data/hf_cache/hub/models--robotics-diffusion-transformer--maniskill-model/snapshots/9622afab2b7ce2312a6cf1febc526928589b77eb'
for d in [os.path.join(snap,'rdt'), snap]:
    for f in ('model.safetensors','pytorch_model.bin','rdt-1b.pt'):
        p = os.path.join(d, f)
        if os.path.exists(p):
            print(f'FOUND {p} ({os.path.getsize(p)//1e6:.0f}MB)')
"

# A4: Verify cached lang embed norm for a LIBERO task
python -c "
import torch, os, hashlib
task = 'pick up the alphabet soup and place it in the basket'
key = hashlib.md5(task.encode()).hexdigest()
f = f'data/rdt_lang_embeds/{key}.pt'
if os.path.exists(f):
    t = torch.load(f, map_location='cpu', weights_only=True)
    print(f'shape={t.shape}, norm={t.norm():.3f}')
else:
    print('NOT FOUND — T5 will be called live')
"

# A5: Simulate proprio normalization with LIBERO EEF values
python -c "
import sys; sys.path.insert(0, 'third_party/rdt')
from scripts.maniskill_model import DATA_STAT
import numpy as np
smin = np.array(DATA_STAT['state_min'])
smax = np.array(DATA_STAT['state_max'])
# Typical LIBERO EEF state: pos + axisangle + gripper
libero = np.array([0.45, 0.02, 0.51, 0.0, 0.0, 3.14, 0.04, 0.04])
norm = (libero - smin) / (smax - smin) * 2 - 1
print('LIBERO state as joint-angle normalized:', np.round(norm, 2))
print('Out-of-range dims:', np.where(np.abs(norm) > 1.5)[0])
"

# A6: Check whether image flip is visible in episode video
# (manual — open the video file)
ls outputs/libero/2026-04-26_07-02-30/episode_1/
# Then: mpv outputs/libero/2026-04-26_07-02-30/episode_1/episode_1_fail_agentview.mp4

# A7: Check LIBERO robot0_joint_pos key availability
python -c "
import sys
# The raw obs dict has 'robot0_joint_pos' — verify it exists
# This requires actually instantiating the env, but we can check the adapter code
import inspect
from core.env_adapters.libero_adapter import LiberoAdapter
src = inspect.getsource(LiberoAdapter._format_raw_obs)
print('robot0_joint_pos in raw obs:', 'robot0_joint_pos' in src)
"
```

---

## Summary

The two near-certain root causes of random behavior are:

1. **H1 (Action space):** `real.step()` → `_unformat_action_to_joint` → ManiSkill joint angles → LIBERO clips/saturates → uncontrolled movement.
2. **H2 (Proprio format):** LIBERO `observation.state` = EEF cartesian, but RDT normalizes with joint-angle statistics → completely wrong model conditioning.

Both are detectable with a single print statement each and fixable without changing the model or third-party code. Domain shift (H3) is a real constraint but cannot explain the degree of randomness observed — it would degrade performance, not produce erratic jitter.

The prioritized fix sequence: **H1 → H2 → verify lang embed → check image flip → measure domain shift**.
