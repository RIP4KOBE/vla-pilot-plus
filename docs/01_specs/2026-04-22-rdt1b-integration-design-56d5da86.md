---
date: 2026-04-22
archived_on: 2026-06-03
source_worktree: main-worktree
source_branch: chore/integrate-rdt-libero-vls
source_commit: 36b46b0d3c7b
source_path: docs/superpowers/specs/2026-04-22-rdt1b-integration-design.md
summary: RDT-1B Integration Design
duplicate_sources:
  - .worktrees/feat/rdt-libero-gt-rollout-integration/docs/superpowers/specs/2026-04-22-rdt1b-integration-design.md
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/superpowers/specs/2026-04-22-rdt1b-integration-design.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/docs/superpowers/specs/2026-04-22-rdt1b-integration-design.md
---

# RDT-1B Integration Design
**Date:** 2026-04-22
**Status:** Approved
**Approach:** Standalone Wrapper (Option A)
**Checkpoint:** `robotics-diffusion-transformer/maniskill-model`
**Backends:** LIBERO (MuJoCo) + CALVIN (PyBullet)

---

## 1. Scope & Goals

Integrate RDT-1B (Robotics Diffusion Transformer, 1.2B-param DiT) into the VLS steering pipeline as a third selectable policy (`policy.type=rdt`), alongside the existing `diffusion` and `pi05` policies.

**Success criteria:**
1. Policy selectable via config — no code edits per run.
2. Both backends complete an episode and write outputs under `outputs/TIMESTAMP/`.
3. FKD particle resampling + gradient-based guidance are both functional.
4. Four smoke tests pass without a GPU.
5. No regressions in existing `diffusion` / `pi05` policies.

**Out of scope:** Fine-tuning RDT on LIBERO/CALVIN datasets. Base-policy task success rate is expected to be low (zero-shot transfer); the steering delta is the research metric.

---

## 2. Checkpoint Selection Rationale

| Variant | Robot | Action space | Domain gap to LIBERO/CALVIN |
|---|---|---|---|
| `rdt-1b` (real-robot) | ALOHA bimanual | 14D absolute joint | HIGH |
| RoboTwin | Bimanual (no published ckpt) | 14D bimanual | HIGH |
| `maniskill-model` ✅ | Franka Panda single-arm | 6D delta EEF + gripper | MEDIUM |

**Selected:** `robotics-diffusion-transformer/maniskill-model`
- Only published single-arm checkpoint
- Action space already converted to delta EEF matching LIBERO/CALVIN convention
- `lang_embeds/` directory ships precomputed T5-XXL embeddings (eliminates 11B language model at inference time)
- SAPIEN→MuJoCo/PyBullet sim-to-sim gap is smaller than real-robot→sim

---

## 3. Architecture & Component Map

### New files

```
third_party/rdt/              ← git submodule: thu-ml/RoboticsDiffusionTransformer
core/rdt_policy_steer.py      ← RDTSteer class (main integration, ~400 lines)
core/rdt_obs_processor.py     ← RDTObsProcessor: image resize + proprio padding
tests/test_rdt_steer.py       ← 4 smoke tests (CPU-only, no real checkpoint)
```

### Modified files

```
configs/policy.yaml      ← add rdt section
main.py                  ← add elif policy_type == 'rdt' branch (~25 lines)
environment.yml          ← add diffusers scheduler dep if missing
.gitmodules              ← add third_party/rdt submodule
setup.sh                 ← add pip install -e ./third_party/rdt step
```

### Data flow

```
EnvAdapter.get_policy_observation()
        │  raw dict: {images: (B,C,H,W) tensors, state: (B,D), task: [str]}
        │
   identity preprocessor  ← main.py sets lambda x: x for rdt
        │  unchanged
        │
RDTSteer.select_action()
        │
   RDTObsProcessor
   ├─ resize images → 384×384 PIL  (static→ext, wrist→right_wrist, zeros→left_wrist)
   ├─ maintain 1-frame ring buffer for history slots (t-1)
   ├─ pad proprio: (B, env_dim) → (14,) per sample  [zeros | arm_state[:7]]
   └─ lang embed lookup: task str → cached T5-XXL tensor (lazy-compute + cache to disk)
        │
   _guided_denoise_loop()     OR     rdt_model.step()   (unguided path)
   ├─ DiT forward: (x_t, t, cond) → noise_pred          ← exposed for hooks
   ├─ DPM-Solver++ step: x_{t-1} = scheduler.step(noise_pred, t, x_t)
   ├─ [HOOK A] gradient guidance: inject grad into x_t when t ≤ start_step
   └─ [HOOK B] FKD resampling: resample B particles at configured intervals
        │  (B, 64, 14)
        │
   action postprocessor (inside RDTSteer)
   ├─ slice right-arm: [:, :, 7:14] → (B, 64, 7)
   ├─ [optional] convert rotation repr 6D → Euler RPY (config flag)
   ├─ select best particle (argmax cumulative reward) → (64, 7)
   └─ take first action_chunk_horizon steps → (H, 7)
        │
main.py → adapter.step(action)
```

---

## 4. Observation Adapter

`core/rdt_obs_processor.py` — `RDTObsProcessor`

### Image mapping

RDT expects 6 PIL images at 384×384. LIBERO and CALVIN provide 2 camera tensors.

| RDT slot | Source | Fallback |
|---|---|---|
| `ext_t` | static/agentview cam (current) → resize 384×384 | — |
| `right_wrist_t` | wrist cam (current) → resize 384×384 | — |
| `left_wrist_t` | not available | black 384×384 PIL image |
| `ext_{t-1}` | ring buffer: previous `ext_t` | duplicate `ext_t` on first step |
| `right_wrist_{t-1}` | ring buffer: previous `right_wrist_t` | duplicate on first step |
| `left_wrist_{t-1}` | not available | black image |

Camera key config (per backend):
- LIBERO: `static_cam_key = observation.images.agentview_rgb`, `wrist_cam_key = observation.images.wrist_rgb`
- CALVIN: `static_cam_key = observation.images.rgb_static`, `wrist_cam_key = observation.images.rgb_gripper`

### Proprio padding

Single-arm state → RDT's 14D bimanual format (right-arm slot, left-arm zeroed):

```
LIBERO state (9D):  [joint×7, gripper×2]
CALVIN state (15D): [EEF_pos×3, EEF_euler×3, gripper×1, joints×7, gripper_cmd×1]

rdt_proprio (14,) = [0, 0, 0, 0, 0, 0, 0,   env_state[:7]]
                     └── left arm (zeros) ──┘  └── right arm ──┘
```

`proprio_dim` is configured per backend in `configs/backend/{calvin,libero}.yaml`.

### Language embeddings

1. Load `lang_embeds/*.pt` files shipped with `maniskill-model` checkpoint at init.
2. For LIBERO/CALVIN task strings not in the cache: compute via T5-XXL on first call (lazy), persist to `data/rdt_lang_embeds/<md5_hash>.pt`.
3. If T5-XXL unavailable (CPU smoke tests): fall back to a zero tensor with a logged warning — allows tests to run without the 11B encoder.

---

## 5. Denoising Loop Surgery & Steering Hooks

`RDTSteer._guided_denoise_loop()` replaces the internal body of `RoboticDiffusionTransformerModel.step()`. The loop has **three mutually-exclusive phases** that mirror the existing `DiffusionPolicySteer._guided_conditional_sample()` exactly:

| Phase | When | What |
|---|---|---|
| **D — RBF diversity** | `t > start_step` (early, high-noise) | Push particles apart via inverse-distance potential |
| **A — Keypoint guidance** | `t ≤ start_step` (late, low-noise) | Steer trajectories toward keypoint target |
| **B — FKD resampling** | `t ≤ start_step`, after denoising step | Resample particles by reward weight |

Both D and A inject gradients into `noise_pred` (before the scheduler step), not into `x_t` directly — matching the existing diffusion policy convention.

```python
def _guided_denoise_loop(
    self, proprio, images, text_embeds, *,
    guidance_fns=None, keypoints=None,
    guide_scale=1.0, start_ratio=0.7,
    use_diversity=True, diversity_scale=1.0,
    use_fkd=False, fkd_config=None,
    MCMC_steps=4, sigmoid_k=12.0, sigmoid_x0=0.7,
) -> Tensor:  # (B, 64, 14)

    cond = self._rdt_model.encode_inputs(proprio, images, text_embeds)
    x_t  = torch.randn(B, 64, 14, device=device, dtype=dtype)

    scheduler = self._rdt_model.noise_scheduler
    scheduler.set_timesteps(self._num_inference_steps)
    start_step = int(self._num_inference_steps * (start_ratio or 0.7))

    fkd = FKD(**fkd_config, reward_fn=fkd_reward_fn) if (use_fkd and B > 1) else None

    for i, t in enumerate(scheduler.timesteps):

        # Baseline noise prediction (no grad)
        with torch.no_grad():
            noise_pred = self._rdt_model.dit(x_t, t, cond)

        # HOOK D — RBF diversity (early denoising: t > start_step)
        if use_diversity and t > start_step and B > 1:
            div_grad = self._compute_diversity_gradient(x_t)
            if div_grad is not None:
                noise_pred[:, :, :3] += diversity_scale * div_grad[:, :, :3]

        # HOOK A — Keypoint gradient guidance (late denoising: t <= start_step)
        elif guidance_fns and keypoints is not None and t <= start_step:
            kp_grad, reward = self._compute_keypoint_gradient(x_t, keypoints, guidance_fns)
            if kp_grad is not None:
                scale = self._adaptive_scale(reward, guide_scale, sigmoid_k, sigmoid_x0)
                noise_pred[:, :action_chunk_horizon, :3] -= scale * kp_grad[:, :action_chunk_horizon, :3]

        # Standard denoising step (uses modified noise_pred)
        x_t = scheduler.step(noise_pred, t, x_t).prev_sample

        # HOOK B — FKD resampling (late denoising only, after denoising step)
        if fkd is not None and t <= start_step:
            x_t, _ = fkd.resample(int(t.item()), x_t, x_t)

    # Record init reward baseline for adaptive scaling (first chunk only)
    if self._stage_init_reward is None and hasattr(self, '_last_raw_reward'):
        self._stage_init_reward = self._last_raw_reward

    return x_t
```

### Trajectory projection helper

Both hooks D and A require projecting the action tensor to 3D EEF positions (for gradient computation). `RDTSteer._rdt_sample_to_trajectory_3d(x_t)`:

```
x_t: (B, 64, 14)
  → slice right-arm [:, :, 7:14]   (B, 64, 7)
  → [rotation conversion if needed]
  → adapter.delta_actions_to_ee_trajectory(action_seq)  → (B, T, 3) EEF positions
```

This reuses the same `adapter.delta_actions_to_ee_trajectory()` call that `DiffusionPolicySteer._sample_to_trajectory_3d()` uses — no new adapter API needed.

**`self._rdt_model.dit`:** The DiT score network inside `RoboticDiffusionTransformerModel`. Its exact attribute name (`dit`, `model`, `net`) is verified by inspecting the loaded checkpoint in the first implementation task; a `getattr` probe with fallbacks is used.

### Action postprocessing (inside RDTSteer)

```
(B, 64, 14)
  → [:, :, 7:14]                         (B, 64, 7)   right-arm slice
  → [if action_rotation_repr == '6d']    convert dims 3:6 from 6D→Euler RPY
  → select best particle:
      if guidance active → argmax(FKD cumulative reward tracked per particle)
      else               → particle 0 (all particles are equally valid without guidance)
  → [:action_chunk_horizon]              (H, 7)       execute window
```

`action_rotation_repr` is a config flag (default `euler`); actual value confirmed against checkpoint output in implementation and documented.

---

## 6. RDTSteer Public Interface

`RDTSteer` is a plain Python class (no LeRobot inheritance). It exposes the same duck-typed interface `main.py` calls on all policies:

| Method / attribute | Purpose |
|---|---|
| `from_pretrained(path) → RDTSteer` | Load checkpoint from HF Hub or local path |
| `post_init(adapter, postprocessor, sample_batch_size, policy_config)` | Wire steering components after load |
| `to(device) → self` | Move model to GPU |
| `eval() → self` | Set eval mode |
| `reset()` | Clear action cache + reward state (per episode) |
| `reset_stage()` | Clear stage-specific reward baseline |
| `get_normalized_reward() → float` | Last step reward ∈ [0, 1] |
| `get_last_scale() → float` | Last guidance scale applied |
| `select_action(batch, **kwargs) → Tensor` | Main inference entry point (matches existing signature exactly) |
| `_action_chunk_horizon: int` | Read by main.py for chunking logic |
| `name: str = "rdt_steer"` | Policy name tag |

---

## 7. Config Changes

### `configs/policy.yaml` (addition)

```yaml
rdt:
  pretrained_path: robotics-diffusion-transformer/maniskill-model
  num_inference_steps: 55
  action_chunk_horizon: 8
  static_cam_key: observation.images.agentview_rgb   # LIBERO default
  wrist_cam_key:  observation.images.wrist_rgb
  proprio_dim: 9                                      # LIBERO: 9 | CALVIN: 15
  lang_embed_cache_dir: data/rdt_lang_embeds/
  action_rotation_repr: euler                         # euler | 6d
```

### CALVIN overrides (via Hydra CLI or task config)

CALVIN uses different camera keys and a 15D proprio. Override via CLI:

```bash
python main.py env=calvin policy.type=rdt \
  policy.rdt.static_cam_key=observation.images.rgb_static \
  policy.rdt.wrist_cam_key=observation.images.rgb_gripper \
  policy.rdt.proprio_dim=15
```

Or add to `configs/task/calvin/*.yaml`:

```yaml
# @package _global_
policy:
  rdt:
    static_cam_key: observation.images.rgb_static
    wrist_cam_key:  observation.images.rgb_gripper
    proprio_dim: 15
```

### `main.py` change (single elif block)

```python
elif policy_type == 'rdt':
    from core.rdt_policy_steer import RDTSteer
    self.policy = RDTSteer.from_pretrained(pretrained_path)
    self.policy_preprocessor = lambda x: x   # RDTSteer owns obs preprocessing
    self.policy_postprocessor = lambda x: x  # RDTSteer owns action postprocessing
```

`post_init` and all subsequent `main.py` code are unchanged — the duck-typed interface handles it.

---

## 8. Tests

`tests/test_rdt_steer.py` — all four tests run on CPU, no real checkpoint required.

| Test | Verifies | Mock strategy |
|---|---|---|
| `test_instantiation` | `RDTSteer` can be constructed; has `name`, `_action_chunk_horizon`, `get_normalized_reward()`, `reset()` | Patch `RDTSteer._rdt_model` with a tiny stub |
| `test_forward_shape` | `select_action(mock_batch, use_guidance=False)` returns `(H, 7)` | Stub DiT returns `randn(B, 64, 14)`; CPU |
| `test_fkd_rollout` | 3-step loop with `use_fkd=True, B=4`; no crash; `get_normalized_reward()` is a float | Mock reward fn returns scalar; CPU |
| `test_gradient_steering` | `use_guidance=True` with mock keypoints + guidance fn; `get_normalized_reward() != 0` after one step | Autograd works on CPU; mock reward returns `x0_pred.sum()` |

Mock DiT stub (shared fixture):
```python
class _StubDiT(nn.Module):
    def forward(self, x, t, cond):
        return torch.zeros_like(x)  # valid noise_pred shape

class _StubRDT:
    dit = _StubDiT()
    noise_scheduler = DDPMScheduler(num_train_timesteps=10)
    def encode_inputs(self, proprio, images, text_embeds):
        return {}
    def step(self, proprio, images, text_embeds):
        return torch.zeros(1, 64, 14)
```

---

## 9. Dependency Notes

| Dep | Already in env? | Action |
|---|---|---|
| `diffusers` (DPM-Solver++ scheduler) | Likely yes (used by lerobot) | Confirm in environment.yml; add if missing |
| `huggingface_hub` | Yes | — |
| `Pillow` | Yes | — |
| `transformers` (T5-XXL, SigLIP) | Yes | — |
| RDT source (`third_party/rdt/`) | No | Add as git submodule |
| T5-XXL weights (11B) | No | Lazy-load only when computing new lang embeds; not needed for smoke tests |

PyTorch version: RDT requires 2.1.0 in its README but uses standard APIs (`nn.Module`, `autograd`, `torch.randn`). Existing env uses a newer torch; compatibility will be confirmed in Task 1 of the implementation plan.

---

## 10. Run Commands

```bash
# CALVIN
python main.py main.use_guidance=true env=calvin task=drawer_open policy.type=rdt

# LIBERO
python main.py main.use_guidance=true env=libero backend.libero.suite_name=libero_goal policy.type=rdt

# No guidance (baseline)
python main.py env=libero policy.type=rdt main.use_guidance=false

# Smoke test
python -m pytest tests/test_rdt_steer.py -v
```

---

## 11. Open Questions (Resolved During Implementation)

1. **Exact attribute name of DiT inside `RoboticDiffusionTransformerModel`** — probe with `getattr` in Task 1, document actual name.
2. **ManiSkill action rotation representation** — whether dims 3:6 of the right-arm output are Euler RPY or 6D rotation; inspect actual checkpoint output in Task 3.
3. **Gripper channel in ManiSkill output** — confirm dim 13 (right-arm slot index 6) contains gripper command; validate sign convention against LIBERO/CALVIN.
4. **PyTorch version compatibility** — run a minimal RDT forward pass in the existing conda env in Task 2 and document any required patches.
