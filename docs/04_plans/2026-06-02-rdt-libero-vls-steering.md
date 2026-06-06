---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: feat/rdt-libero-gt-rollout-reintegration
source_commit: 360a6d052861
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/docs/superpowers/plans/2026-06-02-rdt-libero-vls-steering.md
summary: RDT-LIBERO VLS Steering Implementation Plan
duplicate_sources: []
---

# RDT-LIBERO VLS Steering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable `python main.py policy.type=rdt main.use_guidance=true` to run complete VLS steering for the GT LIBERO RDT checkpoint, with guided success rate no lower than unguided RDT.

**Architecture:** Keep `main.py` and the shared VLS perception/action execution interfaces policy-compatible. Implement RDT-specific glue inside `core/rdt_policy_steer.py`: denoise multi-particle 128D RDT latent actions, score batch-preserving decoded LIBERO EE trajectories, inject sign-probed guidance into slots `[39,40,41]`, run diversity/FKD, select one particle, and return the existing `(1,H,7)` LIBERO action chunk.

**Tech Stack:** Python, PyTorch, NumPy, pytest, Hydra/OmegaConf, diffusers scheduler API, existing `core.fkd_class.FKD`, LIBERO adapter, RDT `RDTRunner`.

---

## Source Spec

Approved design:

```text
docs/docs/01_specs/2026-06-02-rdt-libero-vls-steering-design.md
```

Do not modify:

```text
third_party/rdt/
third_party/libero/
third_party/Libero_RDT/
```

## File Structure

Modify:

```text
core/rdt_policy_steer.py
tests/test_rdt_steer.py
tests/test_rdt_runtime_contract.py
```

Run existing regression tests:

```text
tests/test_rdt_libero_action_converter.py
tests/test_rdt_libero_obs_processor.py
tests/test_policy_observation_sampling.py
tests/test_rdt_runtime_contract.py
tests/test_rdt_steer.py
```

No new runtime route, policy type, perception adapter, or action execution branch should be added.

## Implementation Notes

RDT checkpoint contract:

```text
pred_horizon = 64
unified action dim = 128
action chunk horizon = 8
prediction_type = sample
GT LIBERO action slots = [39,40,41,42,43,44,10]
VLS-guided slots = [39,40,41]
```

Trajectory slices must mirror `core/diffusion_policy_steer.py` exactly:

```text
keypoint gradient: trajectories_3d[:, :H, :3]
FKD reward:        trajectories_3d[:, 1:H, :3]
diversity:         trajectories_3d[:, 1:, :3]
```

The public `decode_rdt_libero_action_chunk()` intentionally returns only the first particle and must not be used for guided particle scoring.

## Task 1: Baseline And Stub Test Harness Updates

**Files:**
- Modify: `tests/test_rdt_steer.py`
- Modify: `tests/test_rdt_runtime_contract.py`

- [ ] **Step 1: Update the stub adapter trajectory to be differentiable**

In `tests/test_rdt_steer.py`, replace `_LiberoAdapter.delta_actions_to_ee_trajectory()` with:

```python
class _LiberoAdapter(_BaseEnvAdapter):
    def delta_actions_to_ee_trajectory(self, seq):
        start = torch.zeros(1, 3, device=seq.device, dtype=seq.dtype)
        deltas = torch.cumsum(seq[:, :3], dim=0)
        return torch.cat([start, deltas], dim=0)
```

- [ ] **Step 2: Update the stub scheduler to expose clean model output**

In `tests/test_rdt_steer.py`, replace `_StubScheduler` with:

```python
class _StubScheduler:
    """Minimal noise scheduler compatible with DPMSolverMultistepScheduler API."""

    def __init__(self, n=5):
        self.timesteps = torch.arange(n - 1, -1, -1, dtype=torch.long)
        self.alphas_cumprod = torch.linspace(0.9, 0.1, n)
        self.last_step_args = []

    def set_timesteps(self, n):
        self.timesteps = torch.arange(n - 1, -1, -1, dtype=torch.long)
        self.alphas_cumprod = torch.linspace(0.9, 0.1, n)

    def step(self, model_output, t, x_t):
        self.last_step_args.append((model_output.detach().clone(), int(t.item()) if torch.is_tensor(t) else int(t)))
        out = MagicMock()
        out.prev_sample = model_output.clone()
        return out
```

- [ ] **Step 3: Keep runtime contract test for prediction type**

Confirm `tests/test_rdt_runtime_contract.py::test_gt_checkpoint_config_matches_rdt_libero_contract` contains:

```python
assert cfg["noise_scheduler"]["prediction_type"] == "sample"
```

- [ ] **Step 4: Run baseline tests**

Run:

```bash
pytest tests/test_rdt_runtime_contract.py tests/test_rdt_steer.py -q
```

Expected before implementation:

```text
existing deferred-guidance tests still pass
```

- [ ] **Step 5: Commit Task 1**

```bash
git add tests/test_rdt_steer.py tests/test_rdt_runtime_contract.py
git commit -m "test: prepare RDT VLS steering harness"
```

## Task 2: Guided Skeleton And Chunk Cache Semantics

**Files:**
- Modify: `tests/test_rdt_steer.py`
- Modify: `core/rdt_policy_steer.py`

- [ ] **Step 1: Replace deferred-guidance tests with guided-cache tests**

In `tests/test_rdt_steer.py`, replace `test_guided_rdt_libero_path_is_explicitly_deferred`, `test_private_guided_loop_is_explicitly_deferred`, `test_select_action_generate_new_chunk_with_guidance_does_not_return_cached_actions`, and `test_select_action_guidance_request_rejects_before_cached_action_reuse` with:

```python
def test_guided_select_action_samples_only_on_chunk_boundaries(stub_steer, stub_adapter):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 2},
    )
    guidance = [lambda keypoints, traj: traj[..., 0].sum()]
    keypoints = np.zeros((3, 3), dtype=np.float32)

    first = stub_steer.select_action(
        _raw_obs(task="guided-first"),
        generate_new_chunk=True,
        use_guidance=True,
        guidance_fns=guidance,
        keypoints=keypoints,
    )
    assert stub_steer._rdt_model.encode_calls == 1
    assert stub_steer._cached_action_steps_remaining == 1

    reused = stub_steer.select_action(
        _raw_obs(task="guided-second"),
        generate_new_chunk=False,
        use_guidance=True,
        guidance_fns=guidance,
        keypoints=keypoints,
    )
    assert reused is first
    assert stub_steer._rdt_model.encode_calls == 1
    assert stub_steer._cached_action_steps_remaining == 0
    assert stub_steer._obs_processor.current().task == "guided-second"

    refreshed = stub_steer.select_action(
        _raw_obs(task="guided-third"),
        generate_new_chunk=False,
        use_guidance=True,
        guidance_fns=guidance,
        keypoints=keypoints,
    )
    assert refreshed is not first
    assert stub_steer._rdt_model.encode_calls == 2


def test_guided_select_action_uses_latent_particle_batch(stub_steer, stub_adapter, mock_batch):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 8},
    )
    action = stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
    )

    assert tuple(action.shape) == (1, 8, 7)
    assert stub_steer._rdt_model.dit.calls
    assert any(latent_shape[0] == 4 for latent_shape, _ in stub_steer._rdt_model.dit.calls)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
pytest tests/test_rdt_steer.py::test_guided_select_action_samples_only_on_chunk_boundaries tests/test_rdt_steer.py::test_guided_select_action_uses_latent_particle_batch -q
```

Expected:

```text
FAIL with NotImplementedError or missing guided methods
```

- [ ] **Step 3: Add RDT VLS constants and FKD import**

In `core/rdt_policy_steer.py`, add the FKD import near the other core imports:

```python
from core.fkd_class import FKD
```

Add these constants after `log = SteerLogger("RDTSteer")`:

```python
RDT_GUIDED_TRANSLATION_INDICES = [39, 40, 41]
RDT_GUIDED_ACTION_INDICES = [39, 40, 41, 42, 43, 44, 10]
RDT_GUIDANCE_SIGN = 1.0
```

- [ ] **Step 4: Fix chunk-cache sampling condition**

In `RDTSteer.select_action()`, replace:

```python
should_sample = (
    generate_new_chunk
    or use_guidance
    or self._cached_action_chunk is None
    or self._cached_action_steps_remaining <= 0
)
```

with:

```python
should_sample = (
    generate_new_chunk
    or self._cached_action_chunk is None
    or self._cached_action_steps_remaining <= 0
)
```

- [ ] **Step 5: Add guided branch skeleton**

In `RDTSteer.select_action()`, replace the `if use_guidance:` block with:

```python
if use_guidance:
    text_embed = self._get_lang_embed(converted.task)
    raw = self._predict_guided(
        converted.state_128,
        converted.state_mask_128,
        converted.images,
        text_embed,
        keypoints=keypoints,
        guidance_fns=guidance_fns,
        guide_scale=guide_scale,
        sigmoid_k=sigmoid_k,
        sigmoid_x0=sigmoid_x0,
        start_ratio=start_ratio,
        use_diversity=use_diversity,
        diversity_scale=diversity_scale,
        verbose=verbose,
        use_fkd=use_fkd,
        fkd_config=fkd_config,
        global_step=global_step,
        current_stage=current_stage,
    )
else:
    text_embed = self._get_lang_embed(converted.task)
    raw = self._predict_unguided(
        converted.state_128,
        converted.state_mask_128,
        converted.images,
        text_embed,
        B=1,
    )
```

- [ ] **Step 6: Add minimal `_predict_guided()` and `_guided_denoise_loop()`**

Add these methods before `_postprocess_actions()`:

```python
def _predict_guided(
    self,
    state_128: Tensor,
    state_mask_128: Tensor,
    images: list,
    text_embed: Tensor,
    *,
    keypoints: Optional[np.ndarray],
    guidance_fns: Optional[List[Callable]],
    guide_scale: float,
    sigmoid_k: float,
    sigmoid_x0: float,
    start_ratio: Optional[float],
    use_diversity: bool,
    diversity_scale: float,
    verbose: bool,
    use_fkd: bool,
    fkd_config: Optional[dict],
    global_step: int,
    current_stage: int,
) -> Tensor:
    device = self.device
    try:
        dtype = next(self._dit.parameters()).dtype
    except StopIteration:
        dtype = torch.float32

    cond = self._rdt_model.encode_inputs(state_128, state_mask_128, images, text_embed)
    unified_action_dim = int(cond["unified_action_dim"])
    if unified_action_dim != 128:
        raise ValueError(f"Expected unified action dim 128, got {unified_action_dim}")

    B = max(1, int(self._sample_batch_size))
    pred_horizon = 64
    x_t = torch.randn(B, pred_horizon, unified_action_dim, device=device, dtype=dtype)

    keypoints_tensor = None
    if keypoints is not None:
        keypoints_tensor = torch.tensor(keypoints, device=device, dtype=dtype)

    guided = self._guided_denoise_loop(
        x_t=x_t,
        cond=cond,
        keypoints=keypoints_tensor,
        guidance_fns=guidance_fns,
        guide_scale=guide_scale,
        sigmoid_k=sigmoid_k,
        sigmoid_x0=sigmoid_x0,
        start_ratio=start_ratio,
        use_diversity=use_diversity,
        diversity_scale=diversity_scale,
        verbose=verbose,
        use_fkd=use_fkd,
        fkd_config=fkd_config,
        global_step=global_step,
        current_stage=current_stage,
    )
    action_mask = cond["action_mask"].expand(guided.shape[0], pred_horizon, unified_action_dim).to(device=device, dtype=dtype)
    return (guided * action_mask).float()


def _guided_denoise_loop(
    self,
    *,
    x_t: Tensor,
    cond: dict,
    keypoints: Optional[Tensor],
    guidance_fns: Optional[List[Callable]],
    guide_scale: float,
    sigmoid_k: float,
    sigmoid_x0: float,
    start_ratio: Optional[float],
    use_diversity: bool,
    diversity_scale: float,
    verbose: bool,
    use_fkd: bool,
    fkd_config: Optional[dict],
    global_step: int,
    current_stage: int,
) -> Tensor:
    scheduler = self._noise_scheduler
    scheduler.set_timesteps(self._num_inference_steps)

    with torch.no_grad():
        for t in scheduler.timesteps:
            model_output = self._dit(x_t, t, cond)
            x_t = scheduler.step(model_output, t, x_t).prev_sample
            x_t = x_t.to(dtype=model_output.dtype)

    if x_t.shape[0] > 1:
        x_t = x_t[0:1]
    return x_t
```

- [ ] **Step 7: Run guided skeleton tests**

Run:

```bash
pytest tests/test_rdt_steer.py::test_guided_select_action_samples_only_on_chunk_boundaries tests/test_rdt_steer.py::test_guided_select_action_uses_latent_particle_batch -q
```

Expected:

```text
2 passed
```

- [ ] **Step 8: Run RDT steering regression tests**

Run:

```bash
pytest tests/test_rdt_steer.py -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 9: Commit Task 2**

```bash
git add core/rdt_policy_steer.py tests/test_rdt_steer.py
git commit -m "feat: add RDT guided denoising skeleton"
```

## Task 3: Batch-Preserving RDT Trajectory Decode

**Files:**
- Modify: `tests/test_rdt_steer.py`
- Modify: `core/rdt_policy_steer.py`

- [ ] **Step 1: Add batch-preserving decode tests**

Append these tests to `tests/test_rdt_steer.py`:

```python
def test_rdt_guidance_trajectory_preserves_particle_batch(stub_steer, stub_adapter):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    sample = torch.zeros(3, 64, 128, dtype=torch.float32)
    sample[0, :4, 39] = 1.0
    sample[1, :4, 40] = 2.0
    sample[2, :4, 41] = 3.0

    traj = stub_steer._rdt_sample_to_trajectory_3d(sample)

    assert tuple(traj.shape) == (3, 5, 3)
    torch.testing.assert_close(traj[0, -1], torch.tensor([4.0, 0.0, 0.0]))
    torch.testing.assert_close(traj[1, -1], torch.tensor([0.0, 8.0, 0.0]))
    torch.testing.assert_close(traj[2, -1], torch.tensor([0.0, 0.0, 12.0]))


def test_rdt_guidance_trajectory_gradients_flow_to_translation_slots(stub_steer, stub_adapter):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"action_chunk_horizon": 4},
    )
    sample = torch.zeros(2, 64, 128, dtype=torch.float32, requires_grad=True)

    traj = stub_steer._rdt_sample_to_trajectory_3d(sample)
    reward = traj[:, :, 0].sum()
    grad = torch.autograd.grad(reward, sample)[0]

    assert grad[:, :4, 39].abs().sum() > 0
    assert grad[:, :4, 40].abs().sum() == 0
    assert grad[:, :4, 41].abs().sum() == 0
    inactive = grad.clone()
    inactive[:, :, [39, 40, 41]] = 0
    assert inactive.abs().sum() == 0
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
pytest tests/test_rdt_steer.py::test_rdt_guidance_trajectory_preserves_particle_batch tests/test_rdt_steer.py::test_rdt_guidance_trajectory_gradients_flow_to_translation_slots -q
```

Expected:

```text
FAIL because _rdt_sample_to_trajectory_3d returns only one particle or has no gradient path
```

- [ ] **Step 3: Add batch-preserving action decode helper**

In `core/rdt_policy_steer.py`, replace `_rdt_sample_to_trajectory_3d()` with:

```python
def _decode_rdt_actions_for_guidance(self, sample: Tensor) -> Tensor:
    if sample.ndim != 3 or sample.shape[1] != 64 or sample.shape[2] != 128:
        raise ValueError(f"Expected RDT sample with shape (B, 64, 128), got {tuple(sample.shape)}")
    H = self._action_chunk_horizon
    return sample[:, :H, RDT_GUIDED_ACTION_INDICES].to(dtype=sample.dtype)


def _rdt_sample_to_trajectory_3d(self, sample: Tensor) -> Tensor:
    actions = self._decode_rdt_actions_for_guidance(sample)
    B = actions.shape[0]
    if self._adapter is None:
        return torch.zeros(
            B,
            self._action_chunk_horizon + 1,
            3,
            device=sample.device,
            dtype=sample.dtype,
        )

    trajs = []
    for b in range(B):
        traj = self._adapter.delta_actions_to_ee_trajectory(actions[b]).to(device=sample.device, dtype=sample.dtype)
        trajs.append(traj)
    return torch.stack(trajs, dim=0)
```

- [ ] **Step 4: Run batch-preserving tests**

Run:

```bash
pytest tests/test_rdt_steer.py::test_rdt_guidance_trajectory_preserves_particle_batch tests/test_rdt_steer.py::test_rdt_guidance_trajectory_gradients_flow_to_translation_slots -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Run converter regression tests**

Run:

```bash
pytest tests/test_rdt_libero_action_converter.py tests/test_rdt_steer.py -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 6: Commit Task 3**

```bash
git add core/rdt_policy_steer.py tests/test_rdt_steer.py
git commit -m "feat: add batch-preserving RDT trajectory decode"
```

## Task 4: Guidance Sign Probe And Keypoint Guidance

**Files:**
- Modify: `tests/test_rdt_steer.py`
- Modify: `core/rdt_policy_steer.py`

- [ ] **Step 1: Add keypoint guidance tests**

Append these tests to `tests/test_rdt_steer.py`:

```python
def test_rdt_guidance_sign_moves_positive_x_reward_up(stub_steer, stub_adapter):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=1,
        policy_config={"action_chunk_horizon": 4},
    )
    model_output = torch.zeros(1, 64, 128)
    grad = torch.zeros_like(model_output)
    grad[:, :4, 39] = 1.0

    guided = stub_steer._apply_keypoint_guidance(model_output, grad, scale=torch.tensor(0.5))

    assert guided[:, :4, 39].sum() > model_output[:, :4, 39].sum()
    assert guided[:, :4, 40].abs().sum() == 0
    assert guided[:, :4, 42].abs().sum() == 0
    assert guided[:, :4, 10].abs().sum() == 0


def test_keypoint_gradient_uses_diffusion_policy_slice_and_masks_slots(stub_steer, stub_adapter):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"action_chunk_horizon": 4},
    )
    sample = torch.zeros(2, 64, 128)

    def reward_fn(keypoints, traj):
        assert tuple(traj.shape) == (2, 4, 3)
        return traj[..., 0].sum()

    grad, reward = stub_steer._compute_keypoint_gradient(
        sample,
        torch.zeros(3, 3),
        [reward_fn],
    )

    assert reward == 0.0
    assert grad is not None
    assert grad[:, :4, 39].abs().sum() > 0
    masked = stub_steer._mask_guidance_gradient(grad)
    assert masked[:, :4, 39].abs().sum() > 0
    assert masked[:, :4, 40].abs().sum() == 0
    assert masked[:, :4, 42].abs().sum() == 0
    assert masked[:, :4, 10].abs().sum() == 0
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
pytest tests/test_rdt_steer.py::test_rdt_guidance_sign_moves_positive_x_reward_up tests/test_rdt_steer.py::test_keypoint_gradient_uses_diffusion_policy_slice_and_masks_slots -q
```

Expected:

```text
FAIL because _apply_keypoint_guidance and _mask_guidance_gradient are missing or keypoint gradient uses the old slice
```

- [ ] **Step 3: Add gradient mask and guidance application helpers**

Add these methods before `_compute_diversity_gradient()`:

```python
def _mask_guidance_gradient(self, grad: Tensor) -> Tensor:
    masked = torch.zeros_like(grad)
    masked[:, : self._action_chunk_horizon, RDT_GUIDED_TRANSLATION_INDICES] = grad[
        :, : self._action_chunk_horizon, RDT_GUIDED_TRANSLATION_INDICES
    ]
    return masked


def _apply_keypoint_guidance(self, model_output: Tensor, kp_grad: Tensor, scale: Tensor | float) -> Tensor:
    guided = model_output.clone()
    if not torch.is_tensor(scale):
        scale = torch.tensor(scale, device=model_output.device, dtype=model_output.dtype)
    masked_grad = self._mask_guidance_gradient(kp_grad).to(device=model_output.device, dtype=model_output.dtype)
    guided[:, : self._action_chunk_horizon, RDT_GUIDED_TRANSLATION_INDICES] += (
        RDT_GUIDANCE_SIGN
        * scale
        * masked_grad[:, : self._action_chunk_horizon, RDT_GUIDED_TRANSLATION_INDICES]
    )
    return guided
```

- [ ] **Step 4: Update `_compute_keypoint_gradient()` slice**

In `_compute_keypoint_gradient()`, replace:

```python
traj_input = trajs[:, : self._action_chunk_horizon, :3]
```

with the same expression and add a comment that it mirrors diffusion policy:

```python
traj_input = trajs[:, : self._action_chunk_horizon, :3]
```

Keep the slice exactly as shown; do not change it to `1:H+1`.

- [ ] **Step 5: Run keypoint guidance tests**

Run:

```bash
pytest tests/test_rdt_steer.py::test_rdt_guidance_sign_moves_positive_x_reward_up tests/test_rdt_steer.py::test_keypoint_gradient_uses_diffusion_policy_slice_and_masks_slots -q
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Wire keypoint guidance into `_guided_denoise_loop()`**

Inside `_guided_denoise_loop()`, replace the simple no-guidance loop body with:

```python
use_keypoint_guidance = guidance_fns is not None and len(guidance_fns) > 0 and keypoints is not None
reward_history = []
start_step = self._resolve_start_step(scheduler.timesteps, start_ratio)

for i, t in enumerate(scheduler.timesteps):
    with torch.no_grad():
        model_output = self._dit(x_t, t, cond)

    if use_keypoint_guidance and int(t.item()) <= start_step:
        kp_grad, reward_value = self._compute_keypoint_gradient(
            x_t,
            keypoints,
            guidance_fns,
            verbose=(verbose and i == int(len(scheduler.timesteps) * 0.8)),
        )
        if kp_grad is not None:
            normalized_reward = self._normalized_reward_from_value(reward_value)
            reward_history.append((i, reward_value, normalized_reward))
            scale = self._adaptive_scale_for_scheduler_t(
                scheduler,
                t,
                guide_scale,
                sigmoid_k,
                sigmoid_x0,
                model_output.device,
                model_output.dtype,
            )
            model_output = self._apply_keypoint_guidance(model_output, kp_grad, scale)

    step_output = scheduler.step(model_output, t, x_t)
    x_t = step_output.prev_sample.to(dtype=model_output.dtype)

if reward_history and self._stage_init_reward is None:
    self._stage_init_reward = reward_history[-1][1]
```

Add these helpers before `_adaptive_scale()`:

```python
def _normalized_reward_from_value(self, reward_value: float) -> float:
    if self._stage_init_reward is not None and self._stage_init_reward < -1e-6:
        normalized_reward = 1.0 - (reward_value / self._stage_init_reward)
        normalized_reward = max(0.0, min(1.2, normalized_reward))
    else:
        normalized_reward = 0.0
    self._last_normalized_reward = normalized_reward
    return normalized_reward


def _resolve_start_step(self, timesteps: Tensor, start_ratio: Optional[float]) -> int:
    if start_ratio is None:
        return int(timesteps[len(timesteps) // 3].item())
    idx = int(len(timesteps) * float(start_ratio))
    idx = max(0, min(len(timesteps) - 1, idx))
    return int(timesteps[idx].item())


def _adaptive_scale_for_scheduler_t(
    self,
    scheduler,
    t: Tensor,
    guide_scale: float,
    sigmoid_k: float,
    sigmoid_x0: float,
    device: torch.device,
    dtype: torch.dtype,
) -> Tensor:
    strength = 1.0 / (1.0 + math.exp(sigmoid_k * (self._last_normalized_reward - sigmoid_x0)))
    if hasattr(scheduler, "alphas_cumprod"):
        alpha_t = scheduler.alphas_cumprod[int(t.item())].to(device=device, dtype=dtype)
    else:
        alpha_t = torch.tensor(self._current_alpha_t, device=device, dtype=dtype)
    scale = torch.tensor(float(guide_scale) * strength, device=device, dtype=dtype) * torch.sqrt(
        torch.clamp(1.0 - alpha_t, min=0.0)
    )
    self._last_scale = float(scale.detach().cpu().item())
    return scale
```

- [ ] **Step 7: Run keypoint and full RDT steer tests**

Run:

```bash
pytest tests/test_rdt_steer.py -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 8: Commit Task 4**

```bash
git add core/rdt_policy_steer.py tests/test_rdt_steer.py
git commit -m "feat: add RDT keypoint guidance"
```

## Task 5: Diversity Guidance

**Files:**
- Modify: `tests/test_rdt_steer.py`
- Modify: `core/rdt_policy_steer.py`

- [ ] **Step 1: Add diversity tests**

Append this test to `tests/test_rdt_steer.py`:

```python
def test_diversity_gradient_preserves_shape_and_translation_mask(stub_steer, stub_adapter):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    sample = torch.zeros(3, 64, 128)
    sample[1, :4, 39] = 0.1
    sample[2, :4, 40] = -0.1

    grad = stub_steer._compute_diversity_gradient(sample)
    assert grad is not None
    assert tuple(grad.shape) == (3, 64, 128)

    masked = stub_steer._mask_guidance_gradient(grad)
    assert masked[:, :4, [39, 40, 41]].abs().sum() > 0
    outside = masked.clone()
    outside[:, :, [39, 40, 41]] = 0
    assert outside.abs().sum() == 0
```

- [ ] **Step 2: Run diversity test**

Run:

```bash
pytest tests/test_rdt_steer.py::test_diversity_gradient_preserves_shape_and_translation_mask -q
```

Expected:

```text
PASS if existing _compute_diversity_gradient already uses batch-preserving trajectories after Task 3
```

- [ ] **Step 3: Wire diversity into `_guided_denoise_loop()`**

In `_guided_denoise_loop()`, before the keypoint branch, add:

```python
if use_diversity and int(t.item()) > start_step and x_t.shape[0] > 1:
    div_grad = self._compute_diversity_gradient(x_t)
    if div_grad is not None:
        masked_div = self._mask_guidance_gradient(div_grad).to(device=model_output.device, dtype=model_output.dtype)
        model_output[:, :, RDT_GUIDED_TRANSLATION_INDICES] += (
            float(diversity_scale) * masked_div[:, :, RDT_GUIDED_TRANSLATION_INDICES]
        )
elif use_keypoint_guidance and int(t.item()) <= start_step:
    kp_grad, reward_value = self._compute_keypoint_gradient(
        x_t,
        keypoints,
        guidance_fns,
        verbose=(verbose and i == int(len(scheduler.timesteps) * 0.8)),
    )
    if kp_grad is not None:
        normalized_reward = self._normalized_reward_from_value(reward_value)
        reward_history.append((i, reward_value, normalized_reward))
        scale = self._adaptive_scale_for_scheduler_t(
            scheduler,
            t,
            guide_scale,
            sigmoid_k,
            sigmoid_x0,
            model_output.device,
            model_output.dtype,
        )
        model_output = self._apply_keypoint_guidance(model_output, kp_grad, scale)
```

- [ ] **Step 4: Add guided-loop diversity smoke test**

Append this test to `tests/test_rdt_steer.py`:

```python
def test_guided_loop_applies_diversity_before_keypoint_phase(stub_steer, stub_adapter, mock_batch):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    action = stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
        use_diversity=True,
        diversity_scale=1.0,
    )

    assert tuple(action.shape) == (1, 4, 7)
    assert stub_steer._rdt_model.dit.calls
```

- [ ] **Step 5: Run diversity tests**

Run:

```bash
pytest tests/test_rdt_steer.py::test_diversity_gradient_preserves_shape_and_translation_mask tests/test_rdt_steer.py::test_guided_loop_applies_diversity_before_keypoint_phase -q
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Commit Task 5**

```bash
git add core/rdt_policy_steer.py tests/test_rdt_steer.py
git commit -m "feat: add RDT diversity guidance"
```

## Task 6: FKD Reward Source And Resampling

**Files:**
- Modify: `tests/test_rdt_steer.py`
- Modify: `core/rdt_policy_steer.py`

- [ ] **Step 1: Add FKD x0 source and reward tests**

Append these tests to `tests/test_rdt_steer.py`:

```python
def test_fkd_x0_source_prefers_model_output_for_sample_prediction(stub_steer):
    model_output = torch.ones(2, 64, 128)
    x_t = torch.zeros(2, 64, 128)

    chosen, source = stub_steer._select_fkd_x0_source(model_output=model_output, step_output=None, x_t=x_t)

    assert source == "model_output"
    torch.testing.assert_close(chosen, model_output)


def test_fkd_reward_scores_all_particles_with_diffusion_policy_slice(stub_steer, stub_adapter):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    x0_preds = torch.zeros(3, 64, 128)
    x0_preds[0, :4, 39] = 1.0
    x0_preds[1, :4, 39] = 2.0
    x0_preds[2, :4, 39] = 3.0

    def reward_fn(keypoints, traj):
        assert tuple(traj.shape) == (1, 3, 3)
        return traj[..., 0].sum()

    rewards = stub_steer._score_particles(
        x0_preds,
        torch.zeros(3, 3),
        [reward_fn],
        slice_kind="fkd",
    )

    assert tuple(rewards.shape) == (3,)
    assert rewards[2] > rewards[1] > rewards[0]
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
pytest tests/test_rdt_steer.py::test_fkd_x0_source_prefers_model_output_for_sample_prediction tests/test_rdt_steer.py::test_fkd_reward_scores_all_particles_with_diffusion_policy_slice -q
```

Expected:

```text
FAIL because _select_fkd_x0_source and _score_particles are missing
```

- [ ] **Step 3: Add FKD reward helpers**

Add these methods before `_guided_denoise_loop()`:

```python
def _select_fkd_x0_source(self, *, model_output: Tensor, step_output, x_t: Tensor) -> tuple[Tensor, str]:
    if step_output is not None:
        pred_original = getattr(step_output, "pred_original_sample", None)
        if pred_original is not None:
            return pred_original, "scheduler_pred_original"
    return model_output, "model_output"


def _trajectory_reward_slice(self, trajs: Tensor, slice_kind: str) -> Tensor:
    if slice_kind == "keypoint":
        return trajs[:, : self._action_chunk_horizon, :3]
    if slice_kind == "fkd":
        return trajs[:, 1 : self._action_chunk_horizon, :3]
    if slice_kind == "diversity":
        return trajs[:, 1:, :3]
    raise ValueError(f"Unknown trajectory reward slice kind: {slice_kind}")


def _score_particles(
    self,
    samples: Tensor,
    keypoints: Optional[Tensor],
    guidance_fns: Optional[List[Callable]],
    *,
    slice_kind: str,
) -> Tensor:
    if keypoints is None or not guidance_fns:
        return torch.zeros(samples.shape[0], device=samples.device, dtype=samples.dtype)
    trajs = self._trajectory_reward_slice(self._rdt_sample_to_trajectory_3d(samples), slice_kind)
    rewards = []
    for b in range(trajs.shape[0]):
        reward = sum(fn(keypoints, trajs[b : b + 1]) for fn in guidance_fns)
        if torch.is_tensor(reward):
            rewards.append(reward.detach().to(device=samples.device, dtype=samples.dtype).reshape(()))
        else:
            rewards.append(torch.tensor(float(reward), device=samples.device, dtype=samples.dtype))
    return torch.stack(rewards)
```

- [ ] **Step 4: Add FKD initialization helper**

Add this method before `_guided_denoise_loop()`:

```python
def _init_fkd(
    self,
    *,
    B: int,
    timesteps: Tensor,
    start_step: int,
    keypoints: Optional[Tensor],
    guidance_fns: Optional[List[Callable]],
    fkd_config: Optional[dict],
    device: torch.device,
) -> Optional[FKD]:
    if fkd_config is None or B <= 1 or keypoints is None or not guidance_fns:
        return None

    def reward_fn(x0_preds: Tensor) -> Tensor:
        return self._score_particles(x0_preds, keypoints, guidance_fns, slice_kind="fkd")

    return FKD(
        potential_type=fkd_config.get("potential_type", "max"),
        lmbda=fkd_config.get("lmbda", 10.0),
        num_particles=B,
        adaptive_resampling=fkd_config.get("adaptive_resampling", True),
        resample_frequency=fkd_config.get("resample_frequency", 5),
        resampling_t_start=int(start_step),
        resampling_t_end=int(timesteps[-1].item()),
        timesteps=timesteps,
        reward_fn=reward_fn,
        reward_min_value=float("-inf"),
        device=device,
    )
```

- [ ] **Step 5: Wire FKD into `_guided_denoise_loop()`**

Before the loop in `_guided_denoise_loop()`, add:

```python
fkd = self._init_fkd(
    B=x_t.shape[0],
    timesteps=scheduler.timesteps,
    start_step=start_step,
    keypoints=keypoints,
    guidance_fns=guidance_fns,
    fkd_config=fkd_config if use_fkd else None,
    device=x_t.device,
)
last_fkd = None
```

Inside the loop, replace the scheduler step and FKD tail with:

```python
step_output = scheduler.step(model_output, t, x_t)
x0_for_reward, fkd_source = self._select_fkd_x0_source(
    model_output=model_output,
    step_output=step_output,
    x_t=x_t,
)
x_t = step_output.prev_sample.to(dtype=model_output.dtype)

if fkd is not None and int(t.item()) <= start_step:
    x_t, _ = fkd.resample(
        sampling_idx=int(t.item()),
        latents=x_t,
        x0_preds=x0_for_reward,
    )
    last_fkd = fkd
```

Return `x_t` for now. Selection is added in Task 7.

- [ ] **Step 6: Run FKD tests**

Run:

```bash
pytest tests/test_rdt_steer.py::test_fkd_x0_source_prefers_model_output_for_sample_prediction tests/test_rdt_steer.py::test_fkd_reward_scores_all_particles_with_diffusion_policy_slice -q
```

Expected:

```text
2 passed
```

- [ ] **Step 7: Run steering tests**

Run:

```bash
pytest tests/test_rdt_steer.py -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 8: Commit Task 6**

```bash
git add core/rdt_policy_steer.py tests/test_rdt_steer.py
git commit -m "feat: add RDT FKD reward resampling"
```

## Task 7: Final Particle Selection

**Files:**
- Modify: `tests/test_rdt_steer.py`
- Modify: `core/rdt_policy_steer.py`

- [ ] **Step 1: Add particle selection tests**

Append these tests to `tests/test_rdt_steer.py`:

```python
def test_select_particle_uses_best_reward_when_fkd_not_terminal(stub_steer, stub_adapter):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    samples = torch.zeros(3, 64, 128)
    samples[0, :4, 39] = 1.0
    samples[1, :4, 39] = 3.0
    samples[2, :4, 39] = 2.0

    selected = stub_steer._select_particle_for_execution(
        samples,
        keypoints=torch.zeros(3, 3),
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        fkd=None,
    )

    assert tuple(selected.shape) == (1, 64, 128)
    torch.testing.assert_close(selected[0, :4, 39], torch.full((4,), 3.0))


def test_select_particle_keeps_first_when_single_particle(stub_steer, stub_adapter):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=1,
        policy_config={"action_chunk_horizon": 4},
    )
    samples = torch.zeros(1, 64, 128)
    samples[0, :4, 39] = 5.0

    selected = stub_steer._select_particle_for_execution(
        samples,
        keypoints=torch.zeros(3, 3),
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        fkd=None,
    )

    torch.testing.assert_close(selected, samples)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
pytest tests/test_rdt_steer.py::test_select_particle_uses_best_reward_when_fkd_not_terminal tests/test_rdt_steer.py::test_select_particle_keeps_first_when_single_particle -q
```

Expected:

```text
FAIL because _select_particle_for_execution is missing
```

- [ ] **Step 3: Add `_select_particle_for_execution()`**

Add this method before `_postprocess_actions()`:

```python
def _select_particle_for_execution(
    self,
    samples: Tensor,
    *,
    keypoints: Optional[Tensor],
    guidance_fns: Optional[List[Callable]],
    fkd: Optional[FKD],
) -> Tensor:
    if samples.shape[0] == 1:
        return samples
    if fkd is not None and fkd.reached_terminal:
        return samples[0:1]
    rewards = self._score_particles(samples, keypoints, guidance_fns, slice_kind="fkd")
    best_idx = int(torch.argmax(rewards).item())
    return samples[best_idx : best_idx + 1]
```

- [ ] **Step 4: Wire selection into `_predict_guided()`**

In `_guided_denoise_loop()`, return both selected samples and the FKD object:

```python
return self._select_particle_for_execution(
    x_t,
    keypoints=keypoints,
    guidance_fns=guidance_fns,
    fkd=last_fkd,
)
```

Keep the return type as a tensor. Do not return `last_fkd` to callers.

- [ ] **Step 5: Run selection tests**

Run:

```bash
pytest tests/test_rdt_steer.py::test_select_particle_uses_best_reward_when_fkd_not_terminal tests/test_rdt_steer.py::test_select_particle_keeps_first_when_single_particle -q
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Run all RDT tests**

Run:

```bash
pytest tests/test_rdt_libero_action_converter.py tests/test_rdt_libero_obs_processor.py tests/test_policy_observation_sampling.py tests/test_rdt_runtime_contract.py tests/test_rdt_steer.py -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 7: Commit Task 7**

```bash
git add core/rdt_policy_steer.py tests/test_rdt_steer.py
git commit -m "feat: select guided RDT particle for execution"
```

## Task 8: Integrated Guided Runtime Instrumentation

**Files:**
- Modify: `tests/test_rdt_steer.py`
- Modify: `core/rdt_policy_steer.py`

- [ ] **Step 1: Add integrated guided action smoke test**

Append this test to `tests/test_rdt_steer.py`:

```python
def test_integrated_guided_select_action_with_diversity_fkd_and_selection(stub_steer, stub_adapter, mock_batch):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 4},
    )
    action = stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
        guide_scale=1.0,
        use_diversity=True,
        diversity_scale=1.0,
        use_fkd=True,
        fkd_config={"potential_type": "max", "lmbda": 1.0, "adaptive_resampling": False, "resample_frequency": 1},
    )

    assert tuple(action.shape) == (1, 4, 7)
    assert torch.isfinite(action).all()
    assert stub_steer.get_last_scale() >= 0.0
```

- [ ] **Step 2: Add one-time guided debug log**

In `_predict_guided()`, after `B` is computed, add:

```python
if verbose:
    log.info(
        f"[RDT_GUIDE] enabled=true B={B} H={self._action_chunk_horizon} "
        f"pred_horizon=64 guided_slots={RDT_GUIDED_TRANSLATION_INDICES} "
        f"action_slots={RDT_GUIDED_ACTION_INDICES} "
        f"guidance_sign={RDT_GUIDANCE_SIGN} prediction_type=sample "
        f"use_diversity={use_diversity} use_fkd={use_fkd}"
    )
```

- [ ] **Step 3: Add numerical guardrails**

At the end of `_guided_denoise_loop()`, before selection, add:

```python
if not torch.isfinite(x_t).all():
    raise ValueError("Guided RDT latent contains non-finite values")
```

In `_compute_keypoint_gradient()`, after `grad` is computed, add:

```python
if not torch.isfinite(grad).all():
    return None, reward_scalar
```

- [ ] **Step 4: Run integrated smoke test**

Run:

```bash
pytest tests/test_rdt_steer.py::test_integrated_guided_select_action_with_diversity_fkd_and_selection -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Run full local regression suite**

Run:

```bash
pytest tests/test_rdt_libero_action_converter.py tests/test_rdt_libero_obs_processor.py tests/test_policy_observation_sampling.py tests/test_rdt_runtime_contract.py tests/test_rdt_steer.py -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 6: Commit Task 8**

```bash
git add core/rdt_policy_steer.py tests/test_rdt_steer.py
git commit -m "test: cover integrated RDT VLS steering"
```

## Task 9: Runtime Smoke And Final Success Evaluation

**Files:**
- No code files modified
- Read outputs under: `outputs/libero/`

- [ ] **Step 1: Run unguided RDT baseline**

Run:

```bash
python main.py policy.type=rdt main.use_guidance=false
```

Expected:

```text
RDT checkpoint loads
LIBERO rollout starts
outputs are written under the Hydra output directory
success count or success rate is visible in logs/results
```

Record:

```text
unguided_success_count =
unguided_episode_count =
unguided_success_rate = unguided_success_count / unguided_episode_count
unguided_output_dir =
```

- [ ] **Step 2: Run guided RDT VLS**

Run:

```bash
python main.py policy.type=rdt main.use_guidance=true
```

Expected:

```text
RDT checkpoint loads
shared VLS perception produces keypoints and guidance functions
guided branch logs [RDT_GUIDE]
rollout reaches LiberoAdapter.step()
outputs are written under the Hydra output directory
success count or success rate is visible in logs/results
```

Record:

```text
guided_success_count =
guided_episode_count =
guided_success_rate = guided_success_count / guided_episode_count
guided_output_dir =
```

- [ ] **Step 3: Compare guided and unguided success**

Run this comparison manually from the recorded values:

```text
guided_success_rate >= unguided_success_rate
```

Expected:

```text
true
```

- [ ] **Step 4: If guided is worse, tune only existing VLS config knobs**

Use Hydra overrides rather than code changes for first tuning pass:

```bash
python main.py policy.type=rdt main.use_guidance=true main.vls_config.guide_scale=20.0
python main.py policy.type=rdt main.use_guidance=true main.vls_config.guide_scale=40.0
python main.py policy.type=rdt main.use_guidance=true main.vls_config.diversity_scale=5.0
python main.py policy.type=rdt main.use_guidance=true main.vls_config.use_fkd=false
```

Expected:

```text
at least one guided configuration reaches guided_success_rate >= unguided_success_rate
```

- [ ] **Step 5: Commit final implementation if success criterion is met**

```bash
git status --short
git add core/rdt_policy_steer.py tests/test_rdt_steer.py
git commit -m "feat: enable RDT LIBERO VLS steering"
```

## Final Verification

Run:

```bash
pytest tests/test_rdt_libero_action_converter.py \
       tests/test_rdt_libero_obs_processor.py \
       tests/test_policy_observation_sampling.py \
       tests/test_rdt_runtime_contract.py \
       tests/test_rdt_steer.py -q
```

Expected:

```text
all tests pass
```

Run:

```bash
python main.py policy.type=rdt
python main.py policy.type=rdt main.use_guidance=true
```

Expected:

```text
guided_success_rate >= unguided_success_rate
```

## Self-Review

Spec coverage:

```text
Gate 0 covered by Task 1.
Gate 1 covered by Task 2.
Gate 2 covered by Task 3.
Gate 3 and Gate 4 covered by Task 4.
Gate 5 covered by Task 5.
Gate 6 and Gate 7 covered by Task 6.
Gate 8 covered by Task 7.
Gate 9 covered by Task 8.
Gate 10 and Gate 11 covered by Task 9.
```

Type consistency:

```text
All new RDT helpers operate on torch.Tensor.
Guided samples keep shape (B, 64, 128) until particle selection.
Selected guided samples keep shape (1, 64, 128).
Public action chunks keep shape (1, H, 7).
```

Scope:

```text
No third_party modifications.
No main.py policy-specific execution branch.
No RDT-specific VLS perception adapter.
No new policy route.
```
