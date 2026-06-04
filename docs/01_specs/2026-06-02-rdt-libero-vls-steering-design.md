---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: feat/rdt-libero-gt-rollout-reintegration
source_commit: 360a6d052861
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/docs/docs/01_specs/2026-06-02-rdt-libero-vls-steering-design.md
summary: RDT-LIBERO VLS Steering Design
duplicate_sources: []
---

# RDT-LIBERO VLS Steering Design

Status: draft for review
Date: 2026-06-02
Scope: brainstorming and design only

This document captures the proposed design for enabling VLS steering in the
current RDT-LIBERO GT rollout integration path.

Target command:

```bash
python main.py policy.type=rdt main.use_guidance=true
```

This document does not authorize implementation. Do not proceed from this
design to writing-plans or code changes until the user explicitly says:

```text
Design approved. Proceed to writing-plans.
```

## 1. Executive Summary

The recommended first implementation is a complete RDT VLS steering path that
ports the existing `diffusion_policy_steer.py` guided-sampling structure into
RDT with only the glue code required by RDT's GT LIBERO semantics.

The current RDT path already denoises in the 128D unified action space and
decodes GT LIBERO action slots directly:

```text
[39, 40, 41, 42, 43, 44, 10] -> [dx, dy, dz, rx, ry, rz, gripper]
```

VLS steering should operate inside the RDT denoising loop, on the same 128D
latent trajectory. It should include the same first-stage components already
available in PI05/diffusion-policy steering:

- multi-particle guided sampling;
- diversity guidance before the keypoint-guidance phase;
- keypoint gradient guidance with reward-normalized sigmoid scaling;
- FKD particle resampling;
- final particle selection for execution.

The RDT-specific semantic constraint is that gradient injection is only allowed
on the translation slots:

```text
[39, 40, 41]
```

The implementation should still proceed in small deployable steps. Each step
must add one steering component, run its local tests, and satisfy an explicit
deployment gate before the next component is added. The first implementation
phase is complete only when the full RDT VLS path, including FKD, diversity, and
multi-particle selection, is wired and tested.

The final implementation success criterion is not just functional execution.
After the guided path is wired, evaluated RDT VLS steering must achieve a
success rate greater than or equal to the unguided RDT baseline:

```bash
python main.py policy.type=rdt main.use_guidance=true
```

must produce a success rate no lower than:

```bash
python main.py policy.type=rdt
```

## 2. Files Inspected And Key Findings

Primary RDT policy wrapper:

```text
core/rdt_policy_steer.py
```

Key findings:

- The unguided path is already connected to the GT LIBERO observation processor
  and action converter.
- `select_action()` currently raises `NotImplementedError` when
  `use_guidance=true`.
- `_predict_unguided()` denoises `(B, 64, 128)` samples and masks the final
  active action slots.
- `_RDTDiTAdapter` already supports expanding conditioning tensors from batch 1
  to a larger latent batch.
- Existing helper `_rdt_sample_to_trajectory_3d()` uses
  `decode_rdt_libero_action_chunk()`, which currently drops all particles except
  the first. Guided RDT must replace this helper with a batch-preserving
  RDT-specific trajectory decoder before enabling diversity, FKD, or final
  particle selection.

Current RDT observation processor:

```text
core/rdt_libero_obs_processor.py
```

Key findings:

- Expects raw LIBERO keys: `agentview_image`, `robot0_eye_in_hand_image`,
  `robot0_joint_pos`, `robot0_gripper_qpos`, and `task`.
- Maintains two-frame image history.
- Builds `state_128` and `state_mask_128` with active state slots:
  `[0, 1, 2, 3, 4, 5, 6, 10, 11]`.
- This path should not be changed for VLS steering.

Current RDT action converter:

```text
core/rdt_libero_action_converter.py
```

Key findings:

- Decodes GT LIBERO action slots:
  `[39, 40, 41, 42, 43, 44, 10]`.
- Does not apply old joint-space conversion, FK, metric scaling, or clipping.
- Binarizes gripper by sign.
- Public chunk decoder intentionally returns the first particle only.

PI05 steering reference:

```text
core/pi05_steer.py
```

Key findings:

- VLS operates on action samples, not on policy observations.
- Samples are decoded to LIBERO action semantics, converted to EE trajectories,
  scored by guidance functions, and differentiated back to the action sample.
- Adaptive sigmoid scaling and stage-level reward initialization are already
  implemented here.

Diffusion-policy steering reference:

```text
core/diffusion_policy_steer.py
```

Key findings:

- This is the closest structural match for RDT.
- Guidance is injected into `model_output` inside the scheduler denoising loop.
- After modifying `model_output`, the scheduler advances the sample with
  `scheduler.step()`.

Runtime orchestration:

```text
main.py
```

Key findings:

- VLS perception is initialized outside the policy wrapper. `main.py` builds
  the keypoint detector, segmentation/grounding components, keypoint tracker,
  VLM guidance generator, and stage recognizer.
- On every new action chunk, `main.py` obtains tracked keypoints and current
  stage guidance functions, then passes them into `policy.select_action()`.
- Action execution is also policy-agnostic: `main.py` receives an action chunk,
  applies the adapter `env_postprocessor` if present, and calls
  `adapter.step(action_chunk[0][action_executed])`.

LIBERO adapter:

```text
core/env_adapters/libero_adapter.py
```

Key findings:

- `get_policy_observation()` returns raw RDT observations for `policy.type=rdt`.
- `get_keypoint_detection_inputs()` provides RGB, depth, point cloud, and
  segmentation inputs for the shared VLS perception stack. This is independent
  from RDT policy observation processing.
- `delta_actions_to_ee_trajectory()` integrates LIBERO 7D delta actions into
  EE position trajectories using the first three action dimensions.
- This trajectory function is the natural bridge from RDT decoded actions to VLS
  keypoint rewards.
- `step()` accepts the final LIBERO 7D action, applies the existing environment
  postprocessor, binarizes gripper, and forwards the action to robosuite.

Config:

```text
configs/policy.yaml
```

Key findings:

- RDT target checkpoint is `RDT-1B-LIBERO-Object`.
- `semantics: libero_gt_rollout`.
- `action_chunk_horizon: 8`.
- `num_inference_steps: null`, so the checkpoint/default scheduler setting is
  used.

## 3. Current RDT Unguided Inference Path Summary

Current unguided execution follows this path:

```text
main.py
  -> LiberoAdapter.get_policy_observation(policy_type="rdt")
  -> RDTSteer.select_action()
  -> RDTLiberoObsProcessor.observe()
  -> RDTLiberoObsProcessor.current()
  -> _RDTModelAdapter.get_text_embedding()
  -> _RDTModelAdapter.encode_inputs()
  -> RDTSteer._predict_unguided()
  -> RDT scheduler denoising over (1, 64, 128)
  -> final action mask
  -> decode_rdt_libero_action_chunk()
  -> LIBERO 7D action chunk
  -> LiberoAdapter.step()
```

Important semantic properties:

- Observation is raw LIBERO observation, not the old ManiSkill-style
  `observation.images.*` format.
- RDT model input state is 128D unified state with GT LIBERO state slots.
- RDT model output remains 128D unified action.
- The final executed action is the GT LIBERO 7D action obtained from slots
  `[39, 40, 41, 42, 43, 44, 10]`.
- The first six decoded dimensions are used as-is.
- Gripper is binarized by sign.

This path should remain unchanged when `main.use_guidance=false`.

## 4. PI05 VLS Steering Path Summary

PI05 guided sampling does the following:

```text
action sample
  -> policy/action postprocessing
  -> LIBERO action sequence
  -> EE trajectory via adapter
  -> VLS reward from keypoints/guidance functions
  -> autograd gradient back to action sample
  -> guided update of sampled action trajectory
```

Conceptual pieces worth reusing for RDT:

- stage-level reward baseline initialization;
- normalized reward for sigmoid scaling;
- adaptive guidance scale;
- trajectory-based keypoint reward;
- diversity guidance;
- FKD particle resampling;
- multi-particle execution selection.

Pieces that should not be copied literally:

- PI05 uses flow-matching time integration, while RDT uses a diffusion scheduler.
- PI05 action dimensions are already the policy action dimensions, while RDT
  actions are embedded inside a 128D unified vector.

## 5. Diffusion-Policy VLS Steering Path Summary

Diffusion-policy steering is the implementation template for RDT:

```text
sample x_t
  -> model predicts denoising output
  -> compute VLS gradient from current sample
  -> modify model output
  -> scheduler.step(model_output, t, x_t)
```

RDT should follow this pattern because RDT also uses a scheduler-based denoising
loop. The RDT work should be glue coding around this template, not a new
steering algorithm.

The important design choice is to inject VLS into the RDT model output, not
directly overwrite decoded LIBERO actions after denoising. Post-hoc modification
would break the relationship between the model's unified 128D trajectory and
the scheduler state.

Template mapping:

```text
DiffusionPolicySteer._predict_action_chunk_guided
  -> RDTSteer._predict_guided

DiffusionPolicySteer._guided_conditional_sample
  -> RDTSteer._guided_denoise_loop or _guided_conditional_sample

DiffusionPolicySteer._sample_to_trajectory_3d
  -> RDTSteer._rdt_sample_to_trajectory_3d

DiffusionPolicySteer._compute_keypoint_gradient
  -> RDTSteer._compute_keypoint_gradient

DiffusionPolicySteer._compute_diversity_gradient
  -> RDTSteer._compute_diversity_gradient

DiffusionPolicySteer FKD reward/resample block
  -> RDTSteer FKD reward/resample block with RDT slot decoding
```

## 6. Proposed RDT VLS Steering Algorithm

Guided RDT inference should use the same observation and conditioning path as
unguided RDT.

High-level algorithm, mirroring `DiffusionPolicySteer._guided_conditional_sample`:

```text
converted = RDTLiberoObsProcessor.current()
text_embeds = model_adapter.get_text_embedding(converted.task)
cond = model_adapter.encode_inputs(
    converted.state_128,
    converted.state_mask_128,
    converted.images,
    text_embeds,
)

B = sample_batch_size
x_t = randn(B, 64, 128)
scheduler.set_timesteps(num_inference_steps)
timesteps = scheduler.timesteps
start_step = resolve_start_step(timesteps, start_ratio)
fkd = maybe_init_fkd(B, timesteps, start_step, reward_fn)

for each timestep:
    model_output = dit(x_t, timestep, cond)
    # RDT checkpoint uses prediction_type="sample", so model_output is the
    # clean-action/x0 estimate. It is the preferred tensor for reward scoring.
    x0_for_reward = model_output

    if use_diversity and timestep > start_step and B > 1:
        div_grad = compute_diversity_gradient(x_t)
        div_grad = mask_to_rdt_translation_slots(div_grad)
        model_output[:, :, [39, 40, 41]] += diversity_scale * div_grad[:, :, [39, 40, 41]]

    elif keypoint guidance is available and timestep <= start_step:
        grad, reward = compute_keypoint_gradient(x_t)
        grad = mask_to_rdt_translation_slots(grad)
        scale = adaptive_guidance_scale(reward, timestep)
        model_output[:, :H, [39, 40, 41]] += sign_probe_result * scale * grad[:, :H, [39, 40, 41]]

    x_t = scheduler.step(model_output, timestep, x_t).prev_sample

    if fkd is enabled and timestep <= start_step:
        x_t, _ = fkd.resample(
            sampling_idx=int(timestep.item()),
            latents=x_t,
            x0_preds=x0_for_reward,
        )

actions_128 = x_t * action_mask
selected = select_particle_for_execution(actions_128, keypoints, guidance_fns)
actions_7d = decode_gt_libero_slots(selected)
```

Guidance start timing:

- Follow the diffusion-policy template after translating the runtime
  `start_ratio` into a scheduler timestep threshold.
- If `start_ratio` is absent, use the same style as diffusion policy:
  choose a threshold from `timesteps[len(timesteps) // 3]`.
- Diversity runs while `timestep > start_step`.
- Keypoint gradient guidance and FKD resampling run while
  `timestep <= start_step`.

Trajectory slices for rewards and gradients:

- Strictly mirror `core/diffusion_policy_steer.py` rather than inventing a new
  slicing convention.
- First decode the RDT sample to full EE trajectory shape `(B, H + 1, 3)`, where
  index 0 is the current EE pose from
  `LiberoAdapter.delta_actions_to_ee_trajectory()`.
- For keypoint gradient guidance, use the diffusion-policy code path:

```text
trajectories_3d[:, :H, :3]
```

- For FKD reward scoring, use the diffusion-policy FKD reward code path:

```text
trajectories_3d[:, 1:H, :3]
```

- For diversity guidance, use the diffusion-policy diversity code path:

```text
trajectories_3d[:, 1:, :3]
```

- Note that the FKD code comment and slice are not perfectly aligned in
  `diffusion_policy_steer.py`; this design follows the actual code slice.

Particle handling:

- RDT observation batch remains 1.
- RDT latent particle batch is `sample_batch_size`.
- `_RDTDiTAdapter` expands conditioning tensors from batch 1 to the particle
  batch as needed.
- Public final action conversion still returns a single action chunk for
  environment execution.
- If FKD reaches terminal and sorts/resamples particles, execute the first
  terminal particle, matching the current FKD convention.
- If FKD is disabled or not terminal, explicitly score final particles with the
  same VLS reward and execute the best particle. Do not silently execute
  particle 0 unless `B == 1`.

Gradient masking:

```text
allowed guided slots = [39, 40, 41]
blocked active slots = [42, 43, 44, 10]
blocked inactive slots = all others
```

This prevents VLS from accidentally changing orientation, gripper, state-like
slots, or unused unified dimensions.

Guidance sign:

- RDT uses `prediction_type="sample"`, so `model_output` is a clean action
  estimate rather than an epsilon/noise estimate.
- The implementation must not assume the diffusion-policy `-=` sign is correct.
- Before real rollout, run the sign probe in Gate 4 and set
  `sign_probe_result` to the sign that increases a synthetic reward.

FKD reward sample:

- Prefer scoring FKD rewards on `model_output`, because it is the RDT x0/clean
  action estimate for `prediction_type="sample"`.
- If the scheduler exposes an explicit predicted-original-sample tensor in its
  step output, that tensor may be compared in Gate 6.
- Use `x_t` as FKD `x0_preds` only as a documented fallback after the probe
  shows it ranks particles consistently with clean-sample scoring.

## 7. RDT Action Semantics Handling

The RDT checkpoint is assumed to emit GT LIBERO rollout actions directly inside
the 128D unified action vector.

The only valid mapping for the current checkpoint is:

```text
RDT slot 39 -> LIBERO dx
RDT slot 40 -> LIBERO dy
RDT slot 41 -> LIBERO dz
RDT slot 42 -> LIBERO rx
RDT slot 43 -> LIBERO ry
RDT slot 44 -> LIBERO rz
RDT slot 10 -> LIBERO gripper
```

The guided trajectory helper should not use the old RDT converter. It should not
perform:

- joint-space decoding;
- Franka FK;
- axis-angle conversion;
- denormalization;
- metric scaling;
- clipping.

For VLS, the decoded LIBERO action is only an intermediate differentiable view
used to compute EE position trajectory. The final executed action should still
flow through the current GT converter.

## 8. Function-By-Function Modification Design

This section should be read as a porting map from
`core/diffusion_policy_steer.py` to `core/rdt_policy_steer.py`. The goal is not
to invent a new RDT steering algorithm. The goal is to reuse the existing
diffusion-policy VLS control flow and replace only the observation/action glue
needed by RDT's 128D GT LIBERO semantics.

VLS perception interface

- Keep the existing policy-compatible perception interface.
- Do not build an RDT-specific VLS perception stack.
- `main.py` remains responsible for keypoint detection, segmentation/grounding,
  keypoint tracking, VLM guidance generation, and stage recognition.
- `LiberoAdapter.get_keypoint_detection_inputs()` remains the source of RGB,
  depth, point cloud, and segmentation inputs for VLS perception.
- `KeypointTracker.get_keypoint_positions()` remains the runtime source of
  current keypoints.
- `guidance_fns` remain the same callable interface used by PI05 and diffusion
  policy.
- RDT adaptation is only needed after perception: `RDTSteer` must consume the
  common `keypoints` and `guidance_fns` arguments and apply them to RDT's 128D
  latent action semantics.
- `RDTLiberoObsProcessor` is only for RDT policy conditioning. It should not
  replace or reshape the shared VLS perception inputs.

Guided action execution interface

- Keep the existing policy-compatible action execution interface.
- Do not add an RDT-specific execution branch in `main.py`.
- `RDTSteer.select_action()` must return the same external action chunk shape
  expected by the rollout loop: `(1, H, 7)`.
- The returned chunk must already be in LIBERO 7D action semantics:
  `[dx, dy, dz, rx, ry, rz, gripper]`.
- After guided denoising and particle selection, RDT-specific work ends at
  selecting a single `(1, 64, 128)` latent chunk and decoding it through the GT
  LIBERO action mapping.
- `main.py` may continue to call `adapter[redacted env file]_postprocessor` on the chunk if
  present.
- `main.py` should continue executing one action at a time through
  `adapter.step(action_chunk[0][action_executed])`.
- `LiberoAdapter.step()` remains responsible for final environment-facing
  processing such as gripper binarization and CPU/NumPy conversion.
- RDT must not introduce extra post-hoc action transforms, clipping, FK, or
  scaling outside the current GT converter and adapter execution path.

`RDTSteer.select_action()`

- Keep the current observation update behavior.
- Keep the current unguided branch unchanged.
- Match PI05/diffusion chunk-cache semantics: sample a new guided chunk only
  when `generate_new_chunk=true`, when no cached chunk exists, or when the cache
  is exhausted.
- Do not keep the current `or use_guidance` resampling condition. If left in
  place, RDT would regenerate a full action chunk on every environment step
  whenever guidance is enabled, while `main.py` still indexes
  `action_chunk[0][action_executed]`.
- Replace the guided `NotImplementedError` branch with a call to
  `_predict_guided()`.
- Pass through the same steering arguments already used by PI05/diffusion
  policy: `keypoints`, `guidance_fns`, `guide_scale`, `start_ratio`,
  `use_diversity`, `diversity_scale`, `use_fkd`, `fkd_config`, `global_step`,
  `current_stage`, `sigmoid_k`, and `sigmoid_x0`.
- If `use_guidance=true` but `guidance_fns` or `keypoints` are unavailable,
  follow the existing diffusion-policy behavior: guided sampling can still run,
  but keypoint/FKD reward blocks become inactive and this is logged clearly.

`RDTSteer._predict_unguided()`

- No behavior change.
- This protects the known-working path:

```bash
python main.py policy.type=rdt
```

`RDTSteer._predict_guided()`

- RDT counterpart of
  `DiffusionPolicySteer._predict_action_chunk_guided()`.
- Use the same `_RDTModelAdapter.encode_inputs()` output.
- Determine latent particle count from RDT's configured `sample_batch_size`.
- Keep policy observation sampling at batch 1; only the denoising latent batch
  has multiple particles.
- Translate `start_ratio` into the diffusion-policy-style `start_step`
  threshold used inside the scheduler loop.
- Call `_guided_denoise_loop()` with the same conceptual arguments as
  `DiffusionPolicySteer._guided_conditional_sample()`.
- After guided denoising, call `_select_particle_for_execution()` if
  `B > 1`.
- Return a single selected masked 128D action chunk for final GT LIBERO decode.

`RDTSteer._guided_denoise_loop()`

- RDT counterpart of `DiffusionPolicySteer._guided_conditional_sample()`.
- Use the same loop order:

```text
model_output = dit(x_t, t, cond)

if use_diversity and t > start_step and B > 1:
    model_output += diversity guidance
elif keypoint guidance is available and t <= start_step:
    model_output += sign-probed adaptive keypoint gradient

x_t = scheduler.step(model_output, t, x_t).prev_sample

if fkd is active and t <= start_step:
    x_t = fkd.resample(..., x0_preds=chosen_clean_action_estimate).latents
```

- The only RDT-specific difference is dimensionality:
  `model_output/sample` are `(B, 64, 128)`, and all VLS edits are masked to
  `[39, 40, 41]`.
- Because RDT uses `prediction_type="sample"`, keypoint guidance must use the
  sign established by Gate 3 instead of blindly copying diffusion-policy's
  subtraction sign.
- FKD must score the Gate 6 clean-action estimate rather than blindly passing
  the current noisy latent as `x0_preds`.
- Reward tracking, `_stage_init_reward`, `_last_normalized_reward`, and
  `_last_scale` should follow the diffusion-policy implementation.

`RDTSteer._init_fkd()`

- RDT counterpart of the FKD initialization block in
  `DiffusionPolicySteer._guided_conditional_sample()`.
- Use the same `FKD` class and the same config fields:
  `potential_type`, `lmbda`, `adaptive_resampling`, `resample_frequency`.
- `num_particles` must equal the RDT latent particle batch size.
- `timesteps` must be the RDT scheduler timesteps.
- `reward_fn(x0_preds)` must decode all RDT particles with the batch-preserving
  RDT trajectory helper, evaluate the same guidance functions, and return a
  tensor of shape `(B,)`.
- FKD reward slicing must mirror diffusion policy exactly:
  `trajectories_3d[:, 1:H, :3]`.

`RDTSteer._rdt_sample_to_trajectory_3d()`

- Should be revised for guided use.
- It should preserve batch dimension.
- It should gather GT action slots directly from the 128D sample.
- It should avoid calling `decode_rdt_libero_action_chunk()` because that helper
  intentionally keeps only the first particle.
- It should return `(B, H + 1, 3)` EE trajectories by using
  `LiberoAdapter.delta_actions_to_ee_trajectory()` per particle or an equivalent
  batch-preserving wrapper.
- This helper only returns the full trajectory. Each caller is responsible for
  applying the same slice used by its diffusion-policy counterpart.

`RDTSteer._compute_keypoint_gradient()`

- RDT counterpart of `DiffusionPolicySteer._compute_keypoint_gradient()`.
- Should compute gradient with respect to the 128D `x_t` sample.
- Should feed guidance functions the diffusion-policy keypoint slice:
  `trajectories_3d[:, :H, :3]`.
- Should normalize gradient as PI05/diffusion-policy do.
- Should mask the final gradient to translation slots only.
- Should update `_last_raw_reward` and `_last_normalized_reward` for debug.

`RDTSteer._compute_diversity_gradient()`

- RDT counterpart of `DiffusionPolicySteer._compute_diversity_gradient()`.
- Should use batch-preserving decoded EE trajectories.
- Should use the diffusion-policy diversity slice:
  `trajectories_3d[:, 1:, :3]`.
- Should return a gradient shaped like `(B, 64, 128)`.
- Should only be injected into `[39, 40, 41]`.
- Should no-op when `B <= 1`, matching existing diffusion/PI05 behavior.

`RDTSteer._select_particle_for_execution()`

- New RDT glue helper required because final environment execution is a single
  action chunk.
- If `B == 1`, select particle 0.
- If FKD reached terminal and the FKD implementation has already sorted or
  concentrated high-reward particles, select particle 0 and log that FKD
  terminal selection was used.
- Otherwise, score every final particle with the same VLS reward used by FKD
  and select the best particle explicitly.
- Return a `(1, 64, 128)` tensor so the existing final postprocess shape remains
  stable.

`core/rdt_libero_action_converter.py`

- No public behavior change.
- Existing converter tests should continue to describe final execution
  semantics.

`core/policy_observation_sampling.py`

- No change recommended.
- RDT observation sample count should remain 1.
- Multi-particle VLS is implemented as a latent denoising batch inside
  `RDTSteer`, not as duplicated raw environment observations.

## 9. Runtime Data Flow For Guided RDT

Expected runtime flow for:

```bash
python main.py policy.type=rdt main.use_guidance=true
```

Detailed flow:

```text
main.py rollout loop
  -> observe environment
  -> shared VLS perception/tracker path updates keypoints
  -> adapter.get_policy_observation(policy_type="rdt", sample_num=1)
  -> tracker/stage logic provides keypoints and guidance functions
  -> RDTSteer.select_action(use_guidance=true)
  -> RDTLiberoObsProcessor.observe()
  -> RDTLiberoObsProcessor.current()
  -> RDT text embedding
  -> RDT image/state/action conditioning
  -> RDT guided denoising over B latent 128D action particles
  -> diversity guidance before keypoint phase
  -> VLS reward from decoded LIBERO EE trajectories
  -> keypoint gradient injection only into slots [39, 40, 41]
  -> FKD particle resampling during keypoint phase
  -> final particle selection for execution
  -> final 128D action mask
  -> GT LIBERO action converter
  -> action chunk shape (1, H, 7)
  -> optional shared adapter[redacted env file]_postprocessor
  -> adapter.step()
```

The policy observation does not directly affect VLS beyond determining the
policy's conditional action distribution. VLS operates on the policy's sampled
action trajectory during denoising.

Perception and policy conditioning are separate interfaces:

```text
VLS perception input:
  adapter.get_keypoint_detection_inputs()
  -> keypoint detector / tracker / stage recognizer
  -> keypoints + guidance_fns
  -> policy.select_action(...)

RDT policy input:
  adapter.get_policy_observation(policy_type="rdt")
  -> RDTLiberoObsProcessor
  -> RDT state/image/language conditioning
```

RDT does not need a special VLS perception adapter unless the generic
`LiberoAdapter.get_keypoint_detection_inputs()` contract is broken. The current
design assumes that contract is preserved.

Action execution also remains a shared interface:

```text
RDT guided denoising
  -> select one particle
  -> decode GT LIBERO 7D action chunk
  -> return action_chunk with shape (1, H, 7)
  -> main.py optional env_postprocessor
  -> adapter.step(single 7D action)
```

RDT-specific adaptation happens before the returned action chunk. Once
`select_action()` returns, the existing rollout loop should treat RDT guided
actions the same way it treats PI05 or diffusion-policy action chunks.

## 10. Testing And Validation Plan

The first implementation phase includes the full VLS feature set, but it should
be deployed through small gates. Each gate must pass before the next gate starts.

Gate 0: baseline regression guard

- Implementation slice: no new code yet; establish the baseline.
- Test method:

```bash
pytest tests/test_rdt_libero_action_converter.py \
       tests/test_rdt_libero_obs_processor.py \
       tests/test_policy_observation_sampling.py \
       tests/test_rdt_runtime_contract.py -q
```

- Pass criterion: all selected baseline tests pass.
- Deployment criterion: current unguided RDT semantics are documented as the
  protected baseline.

Gate 1: guided skeleton using diffusion-policy control flow

- Implementation slice: replace guided `NotImplementedError` with
  `_predict_guided()` and `_guided_denoise_loop()` shaped like
  `DiffusionPolicySteer._predict_action_chunk_guided()` and
  `_guided_conditional_sample()`, but without enabling nonzero guidance yet.
  Fix RDT chunk-cache semantics at the same time.
- Test method: mock RDT model/scheduler test with `use_guidance=true` across
  repeated calls where `generate_new_chunk` is true once and false afterward.
- Pass criterion:
  - guided branch runs without `NotImplementedError`;
  - `select_action()` accepts the same `keypoints` and `guidance_fns`
    arguments used by PI05/diffusion policy;
  - no RDT-specific perception branch is needed in `main.py`;
  - guided RDT calls `_predict_guided()` only on chunk boundaries, not on every
    environment step while `use_guidance=true`;
  - cached action chunk identity is preserved between non-boundary calls;
  - `_cached_action_steps_remaining` decreases consistently with
    `main.py`'s `action_executed` indexing;
  - latent sample shape is `(B, 64, 128)`;
  - final selected output shape is `(1, 64, 128)` before decode;
  - decoded action chunk shape is `(1, H, 7)`;
  - unguided tests from Gate 0 still pass.
- Deployment criterion: `main.use_guidance=true` can enter the RDT guided path
  in a mocked test without changing observation semantics.

Gate 2: batch-preserving RDT trajectory decode

- Implementation slice: add the RDT guided trajectory helper that gathers
  `[39, 40, 41, 42, 43, 44, 10]` for every particle and converts all particles
  to EE trajectories.
- Diffusion-policy reference: `_sample_to_trajectory_3d(sample)` preserves
  `sample.shape[0]`, applies `_postprocessor(sample)` to the whole batch, loops
  over particles, converts each action sequence to an EE trajectory, and stacks
  the result.
- Test method: synthetic `(B, 64, 128)` sample with `B > 1`.
- Pass criterion:
  - trajectory output shape is `(B, H + 1, 3)`;
  - particle identity is preserved;
  - each particle's trajectory changes only when that particle's
    `[39,40,41]` slots change;
  - the helper does not call `decode_rdt_libero_action_chunk()` or any API that
    drops the batch dimension;
  - gripper binarization does not participate in the differentiable trajectory
    path;
  - gradients from a simple trajectory reward flow back to slots `[39,40,41]`;
  - public `decode_rdt_libero_action_chunk()` behavior remains unchanged.
- Deployment criterion: all future VLS components can score all particles
  without the old first-particle drop.

Gate 3: RDT guidance sign probe

- Implementation slice: add a local probe around a single guided denoising step
  before committing to `+=` or `-=` for RDT. This is required because the RDT
  checkpoint uses `prediction_type="sample"`, so `model_output` is a clean
  action estimate rather than epsilon/noise.
- Test method: synthetic reward that prefers positive x-motion, evaluated with
  the diffusion-policy keypoint slice `trajectories_3d[:, :H, :3]`.
- Pass criterion:
  - both candidate signs are tested under the same mocked model/scheduler
    state;
  - the selected sign increases the synthetic reward relative to no guidance;
  - the selected sign is recorded in the implementation as an explicit constant
    or helper, not left implicit by copying diffusion-policy `-=`;
  - the probe fails if reward moves in the wrong direction.
- Deployment criterion: RDT guidance sign is established before keypoint
  guidance is enabled.

Gate 4: keypoint gradient guidance

- Implementation slice: port
  `DiffusionPolicySteer._compute_keypoint_gradient()` to RDT, with sign-probed
  gradient injection into `model_output[:, :H, [39,40,41]]`.
- Test method: synthetic reward that prefers positive x-motion, plus a second
  reward that prefers negative x-motion. Both tests use the strict
  diffusion-policy keypoint slice `trajectories_3d[:, :H, :3]`.
- Pass criterion:
  - gradient is finite and nonzero on `[39,40,41]`;
  - injected gradient is zero outside `[39,40,41]`;
  - reward-normalized sigmoid scaling updates `_last_normalized_reward` and
    `_last_scale`;
  - one guided denoising step changes the model output in the reward-improving
    direction for both synthetic rewards.
- Deployment criterion: RDT keypoint steering is active and measurable in a
  mock guided rollout.

Gate 5: diversity guidance

- Implementation slice: port
  `DiffusionPolicySteer._compute_diversity_gradient()` to RDT trajectory space.
- Test method: multi-particle synthetic samples with overlapping trajectories.
- Pass criterion:
  - diversity gradient shape is `(B, 64, 128)`;
  - diversity update is applied only while `timestep > start_step`;
  - update touches only `[39,40,41]`;
  - no-op behavior is correct when `B <= 1` or `use_diversity=false`.
- Deployment criterion: early denoising steps can diversify RDT particles before
  keypoint steering begins.

Gate 6: FKD x0/reward-sample selection

- Implementation slice: choose which tensor FKD should score as `x0_preds`.
  Candidate priority is:
  `model_output` because RDT `prediction_type="sample"`, scheduler explicit
  predicted-original sample if available, then `x_t` only as fallback.
- Test method: fake particles where `model_output` and `x_t` rank particles
  differently, plus an RDT scheduler-step mock that exposes any available
  predicted-original field.
- Pass criterion:
  - implementation documents which tensor is used for FKD reward scoring;
  - for the current RDT checkpoint, `model_output` is the default FKD
    `x0_preds` unless a scheduler-provided clean sample is proven better;
  - `x_t` is not used as `x0_preds` silently;
  - final particle ranking follows the chosen clean-action estimate.
- Deployment criterion: FKD rewards are computed on a semantically clean RDT
  action estimate, not accidentally on noisy latent state.

Gate 7: FKD particle resampling

- Implementation slice: port the FKD reward/resample block from
  `DiffusionPolicySteer._guided_conditional_sample()` with RDT trajectory
  decoding, the Gate 6 `x0_preds` choice, and the strict diffusion-policy FKD
  reward slice `trajectories_3d[:, 1:H, :3]`.
- Test method: fake reward function that assigns known rewards to particles.
- Pass criterion:
  - `FKD` initializes with `num_particles == B`;
  - reward function returns shape `(B,)`;
  - resampling runs only while `timestep <= start_step`;
  - high-reward particles are preferentially retained or sorted according to
    the configured FKD potential;
  - no FKD path is entered when `B <= 1`, `use_fkd=false`, or `fkd_config=None`.
- Deployment criterion: RDT guided sampling can resample particles using the
  same FKD mechanism as diffusion-policy steering.

Gate 8: final multi-particle selection

- Implementation slice: add `_select_particle_for_execution()`.
- Test method: synthetic final particles with known final rewards.
- Pass criterion:
  - `B == 1` selects particle 0;
  - terminal FKD path selects the FKD-leading particle;
  - non-terminal or FKD-disabled path explicitly scores particles and selects
    the best reward;
  - final selected tensor shape is `(1, 64, 128)`.
- Deployment criterion: environment execution never silently depends on an
  arbitrary first particle when `B > 1`.

Gate 9: integrated guided select_action smoke

- Implementation slice: connect all guided components through
  `RDTSteer.select_action()`.
- Test method: mocked policy/adaptor smoke test with `use_guidance=true`,
  `use_diversity=true`, `use_fkd=true`, and `sample_batch_size > 1`.
- Pass criterion:
  - no `NotImplementedError`;
  - diversity, keypoint guidance, FKD, and selection logs each appear when their
    conditions are active;
  - output action chunk shape is `(1, H, 7)`;
  - returned action chunk can pass through the existing
    `adapter[redacted env file]_postprocessor` call;
  - `action_chunk[0][action_executed]` has shape `(7,)` and can be passed to
    `adapter.step()` without a policy-specific branch;
  - no NaN or Inf in latent, gradient, reward, or decoded action;
  - Gate 0 regression tests still pass.
- Deployment criterion: the full RDT VLS path is locally deployable in a mocked
  runtime.

Gate 10: tiny LIBERO runtime smoke

- Implementation slice: no new code; run a short real-runtime smoke after all
  unit gates pass.
- Test method: run the target command with the smallest practical LIBERO rollout
  settings available in the repo.
- Pass criterion:
  - process initializes the RDT checkpoint;
  - guided branch is used;
  - shared VLS perception produces keypoints and guidance functions through the
    existing adapter/tracker/guidance pipeline;
  - rollout reaches `LiberoAdapter.step()`;
  - no RDT-specific action execution path is used after `select_action()`
    returns;
  - output directories/videos/logs follow the existing Hydra convention;
  - logs show nonzero keypoint reward tracking and no numerical guardrail
    failures.
- Deployment criterion: `python main.py policy.type=rdt main.use_guidance=true`
  is considered deployed for functional runtime use. Task success rate is a
  later evaluation metric, not the gate for wiring correctness.

Gate 11: final guided-vs-unguided success-rate evaluation

- Implementation slice: no new code; run paired evaluations after Gate 10
  confirms functional runtime deployment.
- Test method:

```bash
python main.py policy.type=rdt
python main.py policy.type=rdt main.use_guidance=true
```

- Pass criterion:
  - both runs use the same backend, LIBERO suite/task set, episode count, random
    seed policy, checkpoint, and output conventions;
  - unguided RDT success rate is recorded as the baseline;
  - guided RDT VLS steering success rate is recorded with VLS enabled;
  - guided success rate is greater than or equal to unguided success rate.
- Deployment criterion: implementation is considered successful only if guided
  RDT VLS steering is not worse than unguided RDT denoising on the matched
  evaluation setup.

## 11. Debug Instrumentation Plan

Add one-time guided-mode logs:

```text
[RDT_GUIDE] enabled=true
[RDT_GUIDE] B=<sample_batch_size> H=8 pred_horizon=64 num_timesteps=...
[RDT_GUIDE] guided_slots=[39,40,41] action_slots=[39,40,41,42,43,44,10]
[RDT_GUIDE] start_step=... use_diversity=... use_fkd=...
[RDT_GUIDE] guidance_sign=<+1|-1> prediction_type=sample
[RDT_GUIDE] fkd_x0_source=<model_output|scheduler_pred_original|x_t_fallback>
[RDT_GUIDE] chunk_cache=<new|cached> steps_remaining=...
[RDT_GUIDE] particle_selection=<fkd_terminal|best_reward|single>
```

Add per-chunk summary logs:

```text
raw_reward
normalized_reward
guide_scale
adaptive_scale
grad_norm
diversity_grad_norm
fkd_resample_count
fkd_x0_source
selected_particle
selected_particle_reward
decoded_action_min_max
translation_action_min_max
```

Add guardrail warnings:

- `use_guidance=true` but no guidance functions are available.
- `sample_batch_size <= 1` while diversity or FKD is requested.
- FKD is requested but `fkd_config` is missing.
- guided RDT regenerates a chunk while `generate_new_chunk=false`.
- FKD attempts to score `x_t` as `x0_preds` without the Gate 6 fallback proof.
- gradient contains NaN or Inf.
- decoded action magnitude is unexpectedly large.
- final particle selection falls back to particle 0 for any reason other than
  `B == 1` or terminal FKD ordering.

## 12. Risk Table

| Risk | Why It Matters | Mitigation |
| --- | --- | --- |
| Wrong action slots | Would steer the wrong semantic dimensions | Hard-mask to `[39,40,41]` and log active slots |
| Wrong scheduler sign | Reward may decrease instead of increase | Synthetic reward probe before rollout |
| RDT sample prediction misread | RDT `model_output` is x0/clean action, not epsilon | Gate 3 establishes sign and logs `prediction_type=sample` |
| Non-differentiable decode | VLS gradient could become zero | Use direct gather for position slots |
| Public converter drops batch | Multi-particle guidance would silently use particle 0 | Use internal batch-preserving guided decode |
| Guided cache mismatch | Regenerating chunks every step breaks action_chunk execution semantics | Gate 1 verifies PI05/diffusion-style chunk caching |
| Action scale too large | Could destabilize LIBERO rollout | Debug min/max and start with conservative scale |
| Observation batching confusion | Duplicating raw obs is unnecessary and risky | Keep RDT observation sample count at 1 |
| FKD integration bug | Could resample the wrong tensor or timestep | Port diffusion-policy FKD block directly and unit-test fake rewards |
| FKD scores noisy latent | Reward ranking may prefer noisy particles instead of clean action estimates | Gate 6 chooses `model_output` or scheduler clean estimate as `x0_preds` |
| Particle selection ambiguity | Executing particle 0 can waste multi-particle steering | Add explicit best-reward selection when FKD is not terminal |
| Rotation/gripper corruption | VLS should not change these dimensions | Mask gradients to translation slots only |
| Silent unguided fallback | User may think guidance is active when it is not | Warn clearly when guidance is unavailable |

## 13. Open Questions And Concrete Probes

Decision: Should the first implementation support FKD?

Answer: yes. The first implementation phase should include FKD, ported from
`diffusion_policy_steer.py`, with gate-by-gate validation.

Decision: Should RDT use multiple latent particles immediately?

Answer: yes. Multi-particle sampling is part of the first implementation phase,
but observation sampling remains batch 1. The particle batch exists only inside
RDT denoising.

Decision: Should guided RDT resample every step while `use_guidance=true`?

Answer: no. Guided RDT should match PI05/diffusion chunk-cache semantics. It
should generate a new guided chunk only on `generate_new_chunk=true`, missing
cache, or exhausted cache. The current `or use_guidance` condition in RDT is a
known implementation hazard and must be removed or guarded.

Decision: Can batch-preserving trajectory decode reuse
`decode_rdt_libero_action_chunk()`?

Answer: no. That public converter intentionally selects the first particle for
execution. Guided scoring must use a separate batch-preserving gather of
`[39,40,41,42,43,44,10]`, while final execution may continue using the public
converter after particle selection.

How diffusion-policy handles this:

- Diffusion policy does not have an RDT-style first-particle converter.
- Its `_sample_to_trajectory_3d(sample)` postprocesses the entire batch, loops
  over each particle, converts each action sequence to an EE trajectory, and
  returns a stacked `(B, T + 1, 3)` tensor.
- Therefore the RDT equivalent should mimic that batch-preserving structure,
  but replace `_postprocessor(sample)` with a batch-preserving RDT GT LIBERO
  slot gather.

Decision: Should reward evaluate `traj[:, :H]` or `traj[:, 1:H+1]`?

Answer: strictly follow `diffusion_policy_steer.py` code. Do not use a single
new convention for all guidance components.

- Keypoint gradient guidance uses `trajectories_3d[:, :H, :3]`.
- FKD reward scoring uses `trajectories_3d[:, 1:H, :3]`.
- Diversity guidance uses `trajectories_3d[:, 1:, :3]`.

The RDT implementation should preserve these slices exactly, substituting
`H = self._action_chunk_horizon`.

Question: Is the guidance sign correct for the RDT scheduler?

Probe: use a synthetic reward that rewards positive x motion. Confirm that one
guided denoising run increases decoded `dx` or the resulting EE x trajectory
relative to unguided.

Question: Which tensor should FKD score as `x0_preds`?

Recommendation: score `model_output` first, because RDT uses
`prediction_type="sample"` and the model output is trained against clean action.
If the scheduler exposes a better predicted-original-sample tensor, compare it
in Gate 6. Use current `x_t` only as an explicit fallback after proving it ranks
particles consistently.

Question: How should `start_ratio` map to RDT scheduler timesteps?

Probe: compare the translated RDT `start_step` against diffusion-policy's
`t > start_step` and `t <= start_step` branching. The implementation should keep
the diffusion-policy branch structure after the one-time `start_ratio` to
`start_step` translation.

Question: Should decoded action be clipped?

Recommendation: no clipping in the first design, because GT rollout converter
does not clip the first six dimensions. Add debug magnitude logs instead.

## 14. Clear Decision Gate

Recommended decision:

```text
Implement complete first-phase RDT VLS steering.
Use core/diffusion_policy_steer.py as the algorithmic template.
Restrict changes to RDT-specific glue code and GT LIBERO semantics.
Include keypoint guidance, diversity, FKD, and multi-particle selection.
Fix guided chunk-cache semantics before enabling runtime guidance.
Use batch-preserving RDT trajectory decode for all particle scoring.
Establish RDT guidance sign with a prediction_type=sample probe.
Choose FKD x0 reward source explicitly, preferring clean action estimates.
Validate each component through the gates in Section 10 before moving to the next.
Treat implementation as successful only when guided RDT success rate is no lower than unguided RDT success rate.
Preserve unguided RDT path.
Preserve GT LIBERO observation and action semantics.
```

Do not proceed to writing-plans or implementation until explicit approval:

```text
Design approved. Proceed to writing-plans.
```
