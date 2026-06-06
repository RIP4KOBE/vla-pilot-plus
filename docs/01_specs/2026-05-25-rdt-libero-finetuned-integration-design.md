---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: feat/rdt-libero-gt-rollout-reintegration
source_commit: 360a6d052861
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/docs/docs/01_specs/2026-05-25-rdt-libero-finetuned-integration-design.md
summary: RDT LIBERO-Finetuned Integration Design
duplicate_sources:
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/docs/01_specs/2026-05-25-rdt-libero-finetuned-integration-design.md
---

# RDT LIBERO-Finetuned Integration Design

Status: draft for review
Date: 2026-05-25
Scope: design only, no implementation

This document redesigns the runtime integration between the LIBERO benchmark
environment and the LIBERO-finetuned RDT-1B checkpoint:

```text
/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-60000
```

The key design decision is to align runtime inference with the LIBERO
fine-tuning pipeline, not with the older ManiSkill-checkpoint integration.

Do not proceed from this document to implementation until the user explicitly
approves it and says:

```text
Design approved. Proceed to writing-plans.
```

## 1. Goal

The final implementation should run the LIBERO-finetuned RDT checkpoint on
LIBERO benchmark tasks with semantically aligned observations, actions, and
sampling through the existing VLS runtime entrypoint:

```text
python main.py policy.type=rdt
```

The command convention is to keep `policy.type=rdt`. This design does not keep
a new policy route for LIBERO-finetuned RDT.

The primary implementation success criterion is a real LIBERO evaluation:

```text
python main.py policy.type=rdt
```

with 10 LIBERO episodes completing through the existing project output
convention, saving rollout artifacts and execution videos under a Hydra output
directory similar to:

```text
.worktrees/feat/rdt-libero-object-ckpt/outputs/libero/2026-05-19_07-55-22
```

The run should achieve a success count greater than `0/10`. Lower-level shape,
semantic, and tiny-rollout checks are prerequisites, not the final success
criterion.

This design focuses on unguided/original RDT denoising as the first debugging
step for the final RDT + VLS steering implementation. Unguided inference should
remain inside the existing steering policy implementation so that future VLS
hooks share the same model-loading, conditioning, denoising, and action-decoding
path.

## 2. Inspected Materials

Primary required materials:

```text
docs/docs/01_specs/2026-04-22-rdt1b-integration-design.md
docs/docs/04_plans/2026-04-22-rdt1b-integration.md
docs/superpowers/specs/2026-05-20-rdt-libero-finetune-design.md
docs/superpowers/plans/2026-05-23-rdt-libero-finetune-plan.md
third_party/rdt/agent/libero_dataset_semantics_analysis.md
core/rdt_obs_processor.py
core/rdt_policy_steer.py
core/rdt_action_converter.py
```

Additional files inspected to understand runtime and training paths:

```text
main.py
configs/policy.yaml
configs/config.yaml
configs/backend/libero.yaml
core/env_adapters/libero_adapter.py
third_party/rdt/data/libero_vla_dataset.py
third_party/rdt/data/hdf5_vla_dataset.py
third_party/rdt/configs/state_vec.py
third_party/rdt/configs/base.yaml
third_party/rdt/configs/dataset_stat.json
third_party/rdt/configs/dataset_control_freq.json
third_party/rdt/configs/finetune_datasets.json
third_party/rdt/configs/finetune_sample_weights.json
third_party/rdt/models/rdt_runner.py
third_party/rdt/scripts/maniskill_model.py
third_party/rdt/train/dataset.py
third_party/rdt/tests/test_libero_vla_dataset.py
third_party/lerobot/src/lerobot/processor/env_processor.py
/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-60000/config.json
/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-60000/README.md
```

Missing or unresolved paths:

```text
eval/
```

The `eval/` directory mentioned as a possible candidate does not exist in this
worktree.

## 3. Evidence Summary

### 3.1 Previous April RDT Integration

The April integration introduced a usable structure for connecting an RDT policy
to the project runtime:

```text
core/rdt_obs_processor.py
core/rdt_policy_steer.py
core/rdt_action_converter.py
configs/policy.yaml
main.py policy.type == rdt branch
tests/test_rdt_steer.py
```

Reusable architecture from that design:

```text
EnvAdapter.get_policy_observation()
-> RDT observation processor
-> RDT policy wrapper / denoising loop
-> action chunk postprocessor
-> adapter.step(single action)
```

Reusable abstractions:

```text
Policy wrapper with from_pretrained(), post_init(), select_action(), reset()
Action chunk buffering through main.py
First-step debug probes and fail-fast shape checks
RDT model loading wrapper around third_party/rdt
Image history management
Language embedding cache/reuse
CPU-only stub tests for shape/interface
```

Known failure points from the April path:

```text
ManiSkill checkpoint assumed joint-space or right-arm-only action semantics.
ManiSkill path used 8D or 14D compact actions rather than LIBERO 128D active slots.
Image mapping ignored the real LIBERO wrist camera in some paths.
Action conversion used Franka FK to convert joint predictions to LIBERO OSC actions.
VLS/guidance hooks are entangled with the policy wrapper.
Some config defaults still point to older checkpoint paths or old sampling step counts.
```

The April semantic assumptions must be discarded unless independently verified
against the LIBERO fine-tuning pipeline.

### 3.2 LIBERO Fine-Tuning Contract

The fine-tuned checkpoint was trained through the RDT HDF5 path:

```text
main.py
-> train.train()
-> VLAConsumerDataset(use_hdf5=True)
-> HDF5VLADataset.get_item()
-> HDF5VLADataset.parse_hdf5_file() or LIBERO backend equivalent
-> DataCollatorForVLAConsumerDataset
-> SigLIP + T5 encoders
-> RDTRunner.compute_loss()
```

The LIBERO loader returns the RDT HDF5 contract:

```text
state:           (1, 128)
actions:         (64, 128)
state_indicator: (128,)
cam_high:        (2, H, W, 3)
cam_right_wrist: (2, H, W, 3)
cam_left_wrist:  missing/empty with mask false
language instruction
dataset_name
```

RDT model configuration remains:

```text
state_dim:          128
action_dim:         128
action_chunk_size:  64
img_history_size:   2
num_cameras:        3
lang_token_dim:     4096
img_token_dim:      1152
```

The checkpoint config confirms:

```text
action_dim: 128
pred_horizon: 64
img_pos_embed_config: [2, 3, -729]
max_lang_cond_len: 1024
noise_scheduler.num_inference_timesteps: 5
noise_scheduler.num_train_timesteps: 1000
noise_scheduler.prediction_type: sample
```

The active LIBERO RDT indices are:

```text
right_gripper_open: 10
right_eef_pos:      30, 31, 32
right_eef_angle:    33, 34, 35, 36, 37, 38
```

Canonical active index list:

```text
LIBERO_RDT_INDICES = [30, 31, 32, 33, 34, 35, 36, 37, 38, 10]
```

### 3.3 LIBERO Dataset Semantics

Observed HDF5 schema:

```text
actions:                 (T, 7), float64
obs/agentview_rgb:       (T, 128, 128, 3), uint8
obs/eye_in_hand_rgb:     (T, 128, 128, 3), uint8
obs/gripper_states:      (T, 2), float64
obs/joint_states:        (T, 7), float64
obs/ee_states:           (T, 6), float64
obs/ee_pos:              (T, 3), float64
obs/ee_ori:              (T, 3), float64
robot_states:            (T, 9), float64
states:                  simulator state, task dependent
```

Dataset metadata:

```text
controller type: OSC_POSE
control_delta: true
input_min/input_max: -1, 1
output_min/output_max position: [-0.05, 0.05]
output_min/output_max rotation: [-0.5, 0.5]
control_freq: 20
camera_names: robot0_eye_in_hand, agentview
```

Language source:

```text
json.loads(h5["data"].attrs["problem_info"])["language_instruction"]
```

Action semantics:

```text
raw_action = [dx, dy, dz, drot_x, drot_y, drot_z, gripper]
raw_action[0:3]: normalized OSC delta position command
raw_action[3:6]: normalized OSC delta rotation command
raw_action[6]:   gripper command
```

Gripper convention:

```text
LIBERO action: -1 = open, +1 = close
RDT right_gripper_open: open-high scalar in [0, 1]
```

Fine-tuning action mapping:

```text
actions[:, 30:33] = raw_action[:, 0:3] * 0.05
actions[:, 33:39] = rotvec_to_ortho6d(raw_action[:, 3:6] * 0.5)
actions[:, 10]    = (1 - raw_action[:, 6]) / 2
```

Runtime inverse mapping:

```text
raw_action[:, 0:3] = clip(pred[:, 30:33] / 0.05, -1, 1)
raw_action[:, 3:6] = clip(ortho6d_to_rotvec(pred[:, 33:39]) / 0.5, -1, 1)
raw_action[:, 6]   = clip(1 - 2 * pred[:, 10], -1, 1)
```

Fine-tuning state mapping:

```text
state[:, 30:33] = obs/ee_pos
state[:, 33:39] = rotvec_to_ortho6d(obs/ee_ori)
state[:, 10]    = clip((gripper_states[:, 0] - gripper_states[:, 1]) / 0.08, 0, 1)
```

Image mapping:

```text
cam_high        <- obs/agentview_rgb
cam_right_wrist <- obs/eye_in_hand_rgb
cam_left_wrist  <- missing/empty, mask false
```

Training image order after RDT's consumer dataset preprocessing:

```text
[cam_high t-1, cam_right_wrist t-1, cam_left_wrist t-1,
 cam_high t,   cam_right_wrist t,   cam_left_wrist t]
```

## 4. Current Runtime Mismatches

The current project-owned runtime code is structurally useful but semantically
misaligned with the LIBERO-finetuned checkpoint.

### 4.1 Observation Mismatches

Current `RDTObsProcessor` still comments and behaves like a ManiSkill-oriented
processor in several places:

```text
Only external camera history is tracked.
Wrist slots are represented as None.
LIBERO EEF mode builds only 7D proprio.
EEF position is normalized with hand-authored workspace bounds.
Rotation uses only the first rotation-matrix column, not full 6D ortho.
The active slot list is [30,31,32,33,34,35,10], not [30..38,10].
```

The fine-tuning loader did not normalize `ee_pos` into workspace-relative
coordinates. It stored physical EEF position directly in RDT slots 30:33.

The fine-tuning loader did not store only one rotation column. It stored all six
RDT EEF angle dimensions 33:39.

### 4.2 Action Mismatches

The existing `rdt_action_converter.py` is explicitly a ManiSkill joint-space
converter:

```text
RDT-ManiSkill predicts absolute joint angles.
Convert predicted joints through Franka FK.
Compute incremental EEF pose deltas.
Scale to LIBERO OSC action range.
```

This converter should not be used for the LIBERO-finetuned checkpoint. The new
checkpoint was trained directly on LIBERO delta OSC action semantics embedded in
RDT unified slots, not on absolute Franka joint predictions.

The current LIBERO EEF path in `rdt_policy_steer.py` treats the output as:

```text
[pos_x, pos_y, pos_z, angle0, angle1, angle2, gripper]
```

and assumes it is already normalized LIBERO action space. This conflicts with
fine-tuning, which stored:

```text
pos delta in physical meters
rot delta as 6D ortho representation of scaled rotvec
gripper as open-high scalar
```

### 4.3 Denoising Mismatches

The checkpoint config says the model's own inference timestep count is 5, while
the project config still sets 55. The runtime should not assume the old
ManiSkill default.

The model should sample in 128D unified action space and only decode the active
LIBERO slots after denoising. It should not denoise directly in a 7D or 8D
compact subspace unless the compact-space path is explicitly verified against
training.

### 4.4 Config Mismatches

Current `configs/policy.yaml` still points at:

```text
/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object/ema
```

The required target checkpoint is:

```text
/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-60000
```

The design should make the new path explicit during implementation. It should
also expose or document whether evaluation uses:

```text
checkpoint-60000/ema/model.safetensors
```

or:

```text
checkpoint-60000/model.safetensors
```

The recommended default is EMA, provided loading validation succeeds, because
EMA is normally the preferred evaluation weight for diffusion policies.

## 5. Proposed Architecture

Recommended direction: Alternative D, a hybrid approach.

Reuse the current unified `core/rdt_policy_steer.py` structure for unguided RDT
denoising and future VLS steering, while adding LIBERO-specific observation and
action helper modules. The LIBERO fine-tuning transforms remain the semantic
source of truth.

The project should keep the existing runtime command:

```text
python main.py policy.type=rdt
```

This keeps RDT aligned with the other steering policies:

```text
core/diffusion_policy_steer.py
core/pi05_steer.py
core/rdt_policy_steer.py
```

Each policy has one policy wrapper that owns both its unguided sampling path and
its future steering hooks.

Preferred owned files to add or modify after approval:

```text
core/rdt_policy_steer.py
core/rdt_libero_obs_processor.py
core/rdt_libero_action_converter.py
configs/policy.yaml
main.py
tests/test_rdt_libero_obs_processor.py
tests/test_rdt_libero_action_converter.py
tests/test_rdt_steer.py
```

No separate `core/rdt_libero_policy.py` file should be introduced solely for
unguided RDT denoising.

The integration is LIBERO-exclusive for the LIBERO-finetuned checkpoint. Within
the affected RDT runtime path, implementation may remove or replace
ManiSkill-specific branches, comments, constants, FK converters, and
compatibility logic wherever they conflict with LIBERO-finetuned semantics.
Preserving ManiSkill behavior is not a requirement for this work.

No direct changes should be made under:

```text
third_party/rdt/
third_party/libero/
```

If third-party code appears necessary to change, stop and ask for explicit
approval. Prefer wrappers and imports of pure transform functions over
third-party edits.

## 6. Runtime Data Flow

Recommended launch and output convention:

```text
cd .worktrees/feat/rdt-libero-object-ckpt
python main.py policy.type=rdt
```

Hydra should write outputs through the existing project convention:

```text
outputs/libero/<timestamp>/
  results.txt
  episode_1/
  episode_2/
  ...
  episode_10/
```

Episode directories should include the existing execution videos and rollout
artifacts produced by `main.py` and `TrajectoryVideoRecorder`.

Recommended runtime flow inside that command:

```text
LiberoAdapter.reset()
  -> raw LIBERO observation from OffScreenRenderEnv
  -> project-owned RDT LIBERO observation processor
     - extract agentview and eye-in-hand images
     - build two-frame camera history
     - build 128D state and state/action mask
     - encode or pass language
  -> core/rdt_policy_steer.py
     - encode SigLIP images
     - encode T5 language
     - adapt 128D state condition
     - select_action() chooses unguided or, later, steered mode
     - _predict_unguided() samples a 128D action chunk with original RDT scheduler
  -> project-owned RDT LIBERO action converter
     - decode active slots [30..38,10]
     - convert physical deltas and 6D rotation to LIBERO 7D OSC action
     - log clipping and gripper decisions
  -> main.py executes one action per environment step
```

The action chunk should be buffered by the existing main loop:

```text
generate_new_chunk when action_executed == 0
execute action_chunk[0][action_executed]
clear policy buffer on reset
discard remaining chunk if episode terminates/truncates
```

The policy wrapper should remain the single RDT runtime owner. In particular,
`select_action()`, `_predict_unguided()`, `_postprocess_actions()`,
`_RDTModelAdapter`, and `_RDTDiTAdapter` should be aligned with LIBERO-finetuned
semantics in `core/rdt_policy_steer.py`.

## 7. Observation Semantics

### 7.1 Cameras

Expected RDT cameras:

```text
num_cameras = 3
img_history_size = 2
image slots = 6
SigLIP input size = 384 x 384 after processor
```

Online mapping:

```text
cam_high        <- LIBERO agentview_image
cam_right_wrist <- LIBERO robot0_eye_in_hand_image
cam_left_wrist  <- missing, represented by None/background
```

The image list passed to the RDT image encoder should be:

```text
[high_prev, right_wrist_prev, None,
 high_now,  right_wrist_now,  None]
```

First-step history policy:

```text
high_prev        = None/background
right_wrist_prev = None/background
left_wrist_prev  = None/background
```

Rationale: during training, invalid history frames at episode start were marked
false and replaced by the RDT background image. Duplicating the current frame is
a different conditioning signal.

Image dtype/range:

```text
Online raw LIBERO image: HWC uint8 [0,255]
LeRobot-preprocessed image: BCHW float32 [0,1]
RDT processor input should be PIL RGB or equivalent uint8 RGB.
```

Preferred implementation:

```text
For RDT, either bypass LeRobot's LiberoProcessorStep image path and consume raw
adapter images, or explicitly undo the 180-degree flip before converting to PIL.
```

Important edge case:

LeRobot's `LiberoProcessorStep` flips image height and width. The fine-tuning
loader consumed HDF5 images as written, not images after this LeRobot online
flip. Therefore runtime RDT image orientation must be validated against saved
HDF5 frames or directly against a known task scene before rollout.

### 7.2 Proprioception

The fine-tuned checkpoint expects a 128D RDT state vector with only the LIBERO
active slots populated:

```text
state[30:33] = current EEF position in robot/base frame, meters
state[33:39] = rotvec_to_ortho6d(current EEF axis-angle orientation)
state[10]    = current gripper open scalar, open-high in [0,1]
```

Online source options:

Preferred:

```text
observation.state from LiberoProcessorStep:
[eef_pos(3), eef_axisangle(3), gripper_qpos(2)]
```

Equivalent fallback, if needed:

```text
adapter.get_ee_pose()
adapter._get_current_robosuite_env() for gripper qpos
```

The preferred path is `observation.state` because it mirrors the HDF5
fine-tuning fields:

```text
obs/ee_pos
obs/ee_ori
obs/gripper_states
```

Do not use joint positions as proprio for this checkpoint. Joint-state
proprioception was considered during fine-tuning design, but the implemented
LIBERO loader uses EEF position, 6D EEF orientation, and gripper open scalar.

Do not normalize EEF position with approximate workspace bounds. The training
loader stored physical EEF position directly.

### 7.3 Rotation

Fine-tuning uses:

```text
axis-angle / rotvec -> rotation matrix -> 6D ortho representation
```

The expected 6D convention is the first two rotation-matrix columns in the same
layout as `third_party/rdt/data/libero_vla_dataset.py`.

Runtime must use the same conversion in both directions:

```text
state rotvec -> ortho6d for input condition
pred ortho6d -> rotvec for LIBERO action decode
```

Do not use only the first rotation column. Do not treat the six RDT EEF angle
slots as three Euler angles.

### 7.4 Gripper State

Training gripper state:

```text
open = clip((gripper_qpos[0] - gripper_qpos[1]) / 0.08, 0, 1)
```

This should be reused online. Directly reading only one finger can work in many
states, but the two-finger width formula is the training contract and should be
the default.

### 7.5 Language

Training language is raw LIBERO task language:

```text
json.loads(h5["data"].attrs["problem_info"])["language_instruction"]
```

Online language should use:

```text
LiberoAdapter.get_task_description()
```

or the `task` list already added to the policy observation. No additional
template should be added unless the fine-tuning logs prove such a template was
used.

Text encoder:

```text
/mnt/data/hf_cache/hub/models--google--t5-v1_1-xxl
```

For real checkpoint inference, zero language embeddings should be disallowed by
default. A zero embedding fallback is acceptable only for CPU-only stub tests.

## 8. Action Semantics

### 8.1 RDT Output

The checkpoint outputs a 128D RDT unified-vector action chunk:

```text
shape: (B, 64, 128)
active action slots: [30,31,32,33,34,35,36,37,38,10]
```

The active slots mean:

```text
pred[30:33] = physical delta position command in meters
pred[33:39] = 6D ortho representation of physical delta rotation rotvec
pred[10]    = gripper open scalar
```

The model should denoise the full 128D tensor, then apply the action mask or
slot extraction after sampling. This mirrors `RDTRunner.conditional_sample`,
which samples `(batch, pred_horizon, action_dim)`.

### 8.2 Decode To LIBERO OSC Action

For a predicted action chunk `pred`:

```text
osc[:, 0:3] = clip(pred[:, 30:33] / 0.05, -1, 1)
osc[:, 3:6] = clip(ortho6d_to_rotvec(pred[:, 33:39]) / 0.5, -1, 1)
osc[:, 6]   = clip(1 - 2 * pred[:, 10], -1, 1)
```

The gripper inverse is:

```text
RDT open 1 -> LIBERO -1 open
RDT open 0 -> LIBERO +1 close
```

Recommended gripper execution:

```text
continuous = clip(1 - 2 * pred_open, -1, 1)
binary = -1 if pred_open >= 0.5 else +1
```

Log both the continuous and binary values. LIBERO demonstration actions are
binary in the gripper channel, so binary execution is likely better for smoke
rollout. Continuous execution can remain an optional debug mode if needed.

### 8.3 Clipping

Clipping should be applied only at the final LIBERO action boundary:

```text
before env.step(action)
```

The implementation should count and log clipping separately for:

```text
position dimensions
rotation dimensions
gripper dimension
```

High clipping rates should trigger warnings because saturation can hide semantic
mismatches.

Recommended warning threshold:

```text
warn if any position or rotation dimension clips on more than 25 percent of
the first action chunk
```

### 8.4 Chunk Buffering

RDT predicts 64 actions. The existing runtime executes a shorter horizon from
each chunk. Keep this configurable:

```text
checkpoint pred_horizon: 64
runtime action_chunk_horizon: default 8 for initial smoke, later tune if needed
```

The first executed action is:

```text
decoded_chunk[0]
```

Chunk buffer rules:

```text
Clear on policy.reset()
Generate a new chunk when action_executed == 0
Discard remaining actions on episode termination or truncation
Do not reuse chunk across environment resets
```

## 9. Denoising And Policy Stepping

### 9.1 RDT API

The real RDT runner exposes the useful operations through:

```text
RDTRunner.adapt_conditions()
RDTRunner.conditional_sample()
RDTRunner.predict_action()
noise_scheduler_sample
```

The current wrapper manually mirrors the denoising loop. This is acceptable for
future steering work, but the first LIBERO-finetuned smoke should prefer the
least surprising unguided path.

Recommended first implementation:

```text
Use original RDT conditioning and sampling semantics.
Avoid VLS guidance hooks.
Avoid FKD.
Avoid diversity gradients.
Sample 128D actions with the configured scheduler.
Decode only after sampling.
```

### 9.2 Sampling Steps

The checkpoint config records:

```text
noise_scheduler.num_inference_timesteps = 5
```

Implementation should either:

```text
Use the checkpoint-configured value by default
```

or:

```text
Expose an override but log when it differs from checkpoint config
```

Do not silently keep the old `55` default from the ManiSkill integration.

### 9.3 Control Frequency

The LIBERO datasets record:

```text
control_freq = 20
```

Runtime conditioning should use:

```text
ctrl_freqs = tensor([20])
```

Do not keep the `scripts/maniskill_model.py` default of 25 for LIBERO inference.

### 9.4 State And Action Mask

The action mask should activate:

```text
[30,31,32,33,34,35,36,37,38,10]
```

The same mask was used for state and action in fine-tuning.

Open question:

The action mask order in the compact decoded view should preserve the same order
as the fine-tuning active index list. The design recommends keeping 128D tensors
until final decode to avoid compact-order mistakes.

## 10. Proposed Components

### 10.1 `core/rdt_libero_obs_processor.py`

Responsibility:

```text
Convert online LIBERO observation into RDT LIBERO-finetuned model inputs.
```

Inputs:

```text
observation.images.image or raw agentview image
observation.images.image2 or raw robot0_eye_in_hand image
observation.state = [eef_pos, axis_angle, gripper_qpos]
task = [language string]
```

Outputs:

```text
images: list of 6 PIL RGB images or None placeholders
state_128: torch.Tensor or np.ndarray, shape (1, 128)
state_mask_128: same active dimensions as training, shape (1, 128)
task_str: string
```

Required fail-fast checks:

```text
both real cameras present
images are RGB with finite values
state has at least 8 dimensions
language string is non-empty
active index list exactly matches [30..38,10]
6D rotation output shape is exactly (6,)
gripper open scalar is finite and within [0,1] after clipping
```

### 10.2 `core/rdt_libero_action_converter.py`

Responsibility:

```text
Decode 128D RDT action chunks into LIBERO 7D normalized OSC actions.
```

Inputs:

```text
pred_actions_128: torch.Tensor, shape (B, 64, 128)
action_chunk_horizon: int
```

Output:

```text
libero_action_chunk: torch.Tensor, shape (1, H, 7)
```

Pure functions should include:

```text
rotvec_to_ortho6d(rotvec)
ortho6d_to_rotvec(ortho6d)
libero_raw_to_rdt_action(raw_action_7d)
rdt_action_to_libero_raw(action_128d)
map_libero_gripper_action_to_open(raw_gripper)
map_open_to_libero_gripper(open_scalar)
```

These should match `third_party/rdt/data/libero_vla_dataset.py` exactly. Prefer
importing or copying with tests if direct import creates undesirable third-party
coupling.

### 10.3 `core/rdt_policy_steer.py`

Responsibility:

```text
Remain the unified RDT steering policy wrapper. It should load the
LIBERO-finetuned checkpoint, encode conditions, run unguided RDT sampling for
the pre-debugging path, preserve the future VLS steering extension point, and
return decoded LIBERO action chunks.
```

Public interface should remain compatible with `main.py`:

```text
from_pretrained()
post_init()
select_action()
reset()
eval()
to()
_action_chunk_horizon
```

Key internals that must be aligned with LIBERO-finetuned semantics:

```text
select_action()
_predict_unguided()
_postprocess_actions()
_RDTModelAdapter
_RDTDiTAdapter
```

Design requirements for this file:

```text
Use the checkpoint target from policy.rdt.pretrained_path.
Use RDT's 128D unified action space during sampling.
Build LIBERO 128D state and action masks with active indices [30..38,10].
Call core/rdt_libero_obs_processor.py for LIBERO observation conversion.
Call core/rdt_libero_action_converter.py for LIBERO action decode.
Keep select_action() as the shared entrypoint for unguided and future steered sampling.
Keep VLS steering hooks structurally available but disabled for unguided smoke/eval.
Remove or replace ManiSkill-specific branches where they conflict with LIBERO semantics.
```

First semantic-debugging implementation should run with:

```text
use_guidance=false
use_fkd=false
use_diversity=false or bypassed for RDT smoke
```

This is only a staging choice. The file should remain the place where future RDT
+ VLS steering is implemented, just as `core/pi05_steer.py` and
`core/diffusion_policy_steer.py` each keep unguided and guided behavior in one
policy wrapper.

### 10.4 `main.py`

Preferred route:

```text
python main.py policy.type=rdt
```

The existing `policy.type=rdt` branch should continue to instantiate
`RDTSteer` from `core/rdt_policy_steer.py`. Implementation may update the
configuration passed through that branch, but should not add a separate
unguided-only policy route or standalone `core/rdt_libero_policy.py`.

### 10.5 `configs/policy.yaml`

Proposed config shape after approval:

```yaml
rdt:
  pretrained_path: /mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-60000
  weight_variant: ema
  text_encoder: /mnt/data/hf_cache/hub/models--google--t5-v1_1-xxl
  vision_encoder: /mnt/data/hf_cache/hub/models--google--siglip-so400m-patch14-384
  num_inference_steps: null  # use checkpoint config by default
  action_chunk_horizon: 8
  control_frequency: 20
  debug_first_step: true
  fail_on_zero_language_embedding: true
  semantics: libero_finetuned
```

`semantics: libero_finetuned` is optional but useful as a fail-fast assertion.
This integration is LIBERO-exclusive, so the RDT route does not need to preserve
ManiSkill behavior in this branch.

## 11. Alternatives Considered

### Alternative A: Direct In-Place Rewrite Of Existing RDT Files

Description:

Rewrite the existing RDT runtime files directly:

```text
core/rdt_obs_processor.py
core/rdt_policy_steer.py
core/rdt_action_converter.py
```

to remove ManiSkill assumptions and replace them with LIBERO-finetuned
semantics.

Files likely affected:

```text
core/rdt_obs_processor.py
core/rdt_policy_steer.py
core/rdt_action_converter.py
configs/policy.yaml
tests/test_rdt_*.py
```

Pros:

```text
Smallest file count.
Keeps current main.py policy.type=rdt path.
Allows complete removal of conflicting ManiSkill branches in the modified path.
```

Cons:

```text
Higher risk that old comments, tests, or helper names continue to imply
ManiSkill semantics.
Harder to test observation and action transforms independently.
`rdt_action_converter.py` name/history is joint/FK-oriented and may mislead
future readers unless it is thoroughly rewritten.
```

Semantic risks:

```text
Continuing to use 7 active slots instead of 10.
Treating physical RDT output as normalized LIBERO action.
Reusing FK joint converter.
Keeping old image history duplication behavior.
Keeping old 55-step inference default.
```

Implementation complexity:

```text
Medium
```

Testing difficulty:

```text
Medium-high because tests must prove old branches are not used.
```

Rollback difficulty:

```text
Medium because old and new behavior are in the same files.
```

Expected reliability:

```text
Medium if the rewrite is strict and tests are updated.
```

Recommendation level:

```text
Acceptable, but not preferred because transform boundaries remain muddy.
```

### Alternative B: Current RDT Policy With Dedicated LIBERO Obs/Action Helpers

Description:

Keep `core/rdt_policy_steer.py` as the single RDT policy wrapper and add
dedicated helper modules:

```text
core/rdt_libero_obs_processor.py
core/rdt_libero_action_converter.py
```

`core/rdt_policy_steer.py` imports and uses these helpers from `select_action()`,
`_predict_unguided()`, `_postprocess_actions()`, `_RDTModelAdapter`, and
`_RDTDiTAdapter`.

Files likely affected:

```text
core/rdt_libero_obs_processor.py
core/rdt_libero_action_converter.py
core/rdt_policy_steer.py
configs/policy.yaml
main.py
tests/test_rdt_libero_*.py
tests/test_rdt_steer.py
```

Pros:

```text
Keeps the existing `python main.py policy.type=rdt` command.
Keeps one policy wrapper for unguided and future steered RDT behavior.
Separates pure observation/action transforms from model sampling logic.
Makes transform unit tests focused and easier to review.
Matches the structure used by pi05_steer.py and diffusion_policy_steer.py.
```

Cons:

```text
Requires careful cleanup of existing ManiSkill branches inside rdt_policy_steer.py.
Need to keep transform helpers aligned with the training loader.
```

Semantic risks:

```text
Helper code can drift from `third_party/rdt/data/libero_vla_dataset.py`.
Old rdt_policy_steer.py compact-action assumptions can remain if not removed.
```

Implementation complexity:

```text
Medium
```

Testing difficulty:

```text
Medium
```

Rollback difficulty:

```text
Medium. The route remains `policy.type=rdt`, but the affected RDT path is
LIBERO-exclusive by design.
```

Expected reliability:

```text
High if paired with training-transform reuse and route-level tests.
```

Recommendation level:

```text
Recommended as the structural base of the hybrid approach.
```

### Alternative C: Training-Pipeline Reuse / Single Source Of Truth

Description:

Reuse or import the same transform helpers from:

```text
third_party/rdt/data/libero_vla_dataset.py
```

for online conversion:

```text
rotvec_to_ortho6d
ortho6d_to_rotvec
map_libero_gripper_action
map_libero_gripper_state
controller scaling
active index list
```

Files likely affected:

```text
core/rdt_libero_obs_processor.py
core/rdt_libero_action_converter.py
core/rdt_policy_steer.py
tests/test_rdt_libero_*.py
```

Pros:

```text
Best semantic alignment.
Reduces risk of off-by-one active indices.
Makes conversion tests direct and clear.
```

Cons:

```text
Runtime code imports from third_party/rdt data path.
The training loader was designed for HDF5, not online env observations.
Need to avoid modifying third_party code.
```

Semantic risks:

```text
Direct import might accidentally depend on current working directory or RDT config files.
HDF5-specific assumptions should not leak into online runtime.
```

Implementation complexity:

```text
Low-medium
```

Testing difficulty:

```text
Low-medium
```

Rollback difficulty:

```text
Low
```

Expected reliability:

```text
High for conversion semantics.
```

Recommendation level:

```text
Recommended as a supporting tactic, not as the whole architecture.
```

### Alternative D: Hybrid Approach

Description:

Reuse the current unified `rdt_policy_steer.py` structure for unguided denoising
and future VLS steering, while adding LIBERO-specific observation/action
processors and using the LIBERO fine-tuning transforms as the semantic source of
truth.

Files likely affected:

```text
core/rdt_libero_obs_processor.py
core/rdt_libero_action_converter.py
core/rdt_policy_steer.py
configs/policy.yaml
main.py
tests/test_rdt_libero_*.py
tests/test_rdt_steer.py
```

Pros:

```text
Best balance of correctness and isolation.
Keeps third-party source untouched.
Keeps the existing `python main.py policy.type=rdt` evaluation command.
Keeps unguided denoising and future VLS steering in one RDT policy wrapper.
Allows removal of ManiSkill-specific code from the affected RDT runtime path.
Encourages focused unit tests for each semantic transform.
```

Cons:

```text
Slightly more implementation work than direct in-place patching.
Requires careful cleanup of existing rdt_policy_steer.py assumptions.
Requires route-level tests to prove `policy.type=rdt` uses LIBERO semantics.
```

Semantic risks:

```text
Image orientation still needs real online-vs-HDF5 validation.
EMA/non-EMA weight choice must be explicit.
```

Implementation complexity:

```text
Medium
```

Testing difficulty:

```text
Medium, but tests will be cleaner and more diagnostic.
```

Rollback difficulty:

```text
Medium. This branch treats the RDT route as LIBERO-exclusive, so rollback means
reverting the RDT route or restoring an older branch.
```

Expected reliability:

```text
Highest among the options.
```

Recommendation level:

```text
Strongly recommended.
```

## 12. Validation Plan

All validation commands below are proposed for later implementation/planning.
They should not be run as long jobs during this design-only stage.

### 12.1 File Discovery Validation

Purpose:

```text
Verify all required runtime assets exist before model load or rollout.
```

Check:

```text
/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-60000/config.json
/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-60000/ema/model.safetensors
/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-60000/model.safetensors
/mnt/data/hf_cache/hub/models--google--t5-v1_1-xxl
/mnt/data/hf_cache/hub/models--google--siglip-so400m-patch14-384
/mnt/data/hf_cache/hub/libero_object/*.hdf5
/mnt/data/hf_cache/hub/libero_goal/*.hdf5
/mnt/data/hf_cache/hub/libero_spatial/*.hdf5
/mnt/data/hf_cache/hub/libero_10/*.hdf5
```

Expected output:

```text
PASS/FAIL per file or directory
checkpoint config summary
weight variant selected
number of HDF5 task files per suite
```

### 12.2 One-Sample Shape Validation

Purpose:

```text
Verify one dataset sample and one online env observation convert to the same RDT
input contract.
```

Dataset sample checks:

```text
state shape: (1, 128)
actions shape: (64, 128)
state_indicator active indices: [10,30,31,32,33,34,35,36,37,38]
cam_high shape: (2, H, W, 3), uint8
cam_right_wrist shape: (2, H, W, 3), uint8
cam_left_wrist shape: empty or None-equivalent
language non-empty
```

Online observation checks:

```text
image list length: 6
image slot order matches training
state_128 shape: (1,128)
state_mask active indices match training
task string equals adapter task description
```

### 12.3 Semantic Numeric Validation

Purpose:

```text
Detect plausible-shape but wrong-unit bugs.
```

Observation checks:

```text
image min/max in [0,255] before PIL or [0,1] before conversion
EEF position in plausible LIBERO workspace, not normalized by hand
axis-angle finite and plausible
ortho6d columns finite and not all zero
gripper open scalar in [0,1]
```

Action checks:

```text
pred[30:33] physical delta magnitude
pred[33:39] converts to finite rotvec
pred[10] open scalar range
decoded OSC action in [-1,1]
position clipping frequency
rotation clipping frequency
gripper threshold decisions
```

### 12.4 Conversion Tests

Purpose:

```text
Validate both directions:
LIBERO raw observation -> RDT input
RDT output action chunk -> LIBERO OSC action
```

Required cases:

```text
deterministic synthetic input
one real HDF5 sample
one real online env observation
comparison against fine-tuning transform where possible
```

Synthetic tests:

```text
raw gripper -1 -> RDT open 1
raw gripper +1 -> RDT open 0
raw pos action [1,-1,0] -> RDT pos [0.05,-0.05,0]
raw rot action [1,0,0] -> rotvec [0.5,0,0] -> ortho6d -> inverse -> raw [1,0,0]
```

### 12.5 Gripper Convention Tests

Purpose:

```text
Prevent open/close inversion.
```

Must test:

```text
dataset raw -1 maps to RDT open 1
dataset raw +1 maps to RDT open 0
RDT open 1 decodes to LIBERO -1
RDT open 0 decodes to LIBERO +1
open threshold 0.5 is documented and logged
online gripper state from qpos width maps open-high
```

### 12.6 Tiny Rollout Smoke Test

Purpose:

```text
After implementation approval, run one tiny rollout to verify mechanical
end-to-end behavior before full benchmark evaluation.
```

Recommended smoke:

```text
suite: libero_object
task_id: 0
episodes: 1
max steps: small cap, for example 20 to 50
policy: rdt
checkpoint: checkpoint-60000
use_guidance: false
use_fkd: false
debug_first_step: true
```

Command convention:

```text
python main.py policy.type=rdt main.use_guidance=false main.vls_config.use_fkd=false
```

Logs to capture:

```text
checkpoint path and weight variant
encoder paths
checkpoint config summary
first-step image order/shape/range
first-step state active slots
language string and embedding shape/norm
first action chunk active-slot summary
decoded first 5 LIBERO actions
gripper continuous and binary commands
clipping counters
termination/truncation reason
output directory path
saved video path
```

Expected output convention:

```text
outputs/libero/<timestamp>/results.txt
outputs/libero/<timestamp>/episode_1/
outputs/libero/<timestamp>/episode_1/<execution video or rollout artifact>
```

### 12.7 Ten-Episode Evaluation Gate

Purpose:

```text
Verify the integration achieves non-trivial LIBERO benchmark performance, not
only shape correctness.
```

Required command:

```text
python main.py policy.type=rdt
```

Recommended initial unguided-debug overrides, if needed:

```text
python main.py policy.type=rdt main.use_guidance=false main.vls_config.use_fkd=false
```

Expected behavior:

```text
10 LIBERO episodes complete.
results.txt is written under outputs/libero/<timestamp>/.
episode directories are written for all attempted episodes.
execution videos or rollout videos are saved through the existing video recorder.
success count is greater than 0/10.
```

If the run remains at `0/10`, implementation is not complete unless logs show
the failures are task-difficulty related after observation/action semantics have
been verified. Adapter or semantic bugs are the primary suspicion until proven
otherwise.

### 12.8 Regression And Non-Regression

Purpose:

```text
Ensure the LIBERO-finetuned RDT path uses the intended route and does not modify
third-party source.
```

Checks:

```text
No changes under third_party/rdt unless explicitly approved
No changes under third_party/libero unless explicitly approved
Old ManiSkill-specific RDT tests are removed, replaced, or clearly marked as obsolete
New LIBERO RDT tests prove the correct route is used
main.py routes policy.type=rdt to core/rdt_policy_steer.py
core/rdt_policy_steer.py uses LIBERO obs/action helper modules
```

## 13. Debug Instrumentation

Add lightweight instrumentation guarded by a debug flag:

```text
debug_first_step: true
```

Instrumentation should be emitted from the existing `policy.type=rdt` runtime
path, primarily through `core/rdt_policy_steer.py` and its LIBERO-specific
obs/action helpers. It should integrate with the existing `main.py` output
directory and video recorder rather than creating a separate evaluation script.

First step only:

```text
policy route and checkpoint path
Hydra output directory
image slot names and source cameras
image shapes, dtype, min/max, mean
whether LeRobot flip was bypassed or undone
state_128 active indices and values
state units summary
language string
language embedding shape, dtype, norm
action chunk shape
predicted active slot min/max/mean
decoded OSC first action and first 5 actions
gripper open scalar, continuous command, binary command
position/rotation clipping counters
buffer reset message
episode directory and video artifact path when available
```

Warnings:

```text
missing camera key
empty language
zero language embedding in real inference
wrong action dimension
wrong active index list
non-finite state or action values
6D rotation inverse failure
high clipping/saturation rate
unexpected control frequency
```

Avoid excessive logs during full rollout. Only first-step summaries should be
on by default in debug mode.

## 14. Risk Analysis

| Risk | Why It Matters | Early Detection | Mitigation | Blocks Implementation |
|---|---|---|---|---|
| Missing rotation slots 36:38 | Model was trained with full 6D rotation | Active-index unit test | Use `[30..38,10]` exactly | Yes |
| Treating physical action slots as normalized LIBERO actions | Causes oversized or wrong commands | Synthetic inverse conversion test | Decode with `/0.05`, 6D inverse, `/0.5` | Yes |
| Gripper inversion | Robot opens when it should close or vice versa | Endpoint tests | Use affine inverse `1 - 2 * open` | Yes |
| Image order mismatch | Policy conditions on wrong camera/time | First-step image log and saved frames | Match training order exactly | Yes |
| Image orientation mismatch | Visual observations out of distribution | Compare online frame to HDF5-like frame | Bypass or undo LeRobot flip | Yes |
| Hand-normalized EEF position | State distribution differs from training | Numeric state summary | Use raw meters from `observation.state` | Yes |
| Using joint FK converter | Applies wrong action semantics | Code-route test | New LIBERO action converter | Yes |
| Control frequency 25 instead of 20 | RDT conditions on wrong environment rate | Config log/assert | Set LIBERO control freq 20 | Yes |
| Wrong checkpoint path | Evaluates stale model | File discovery report | Use checkpoint-60000 path | Yes |
| EMA/non-EMA ambiguity | Different model quality | Weight variant log | Default EMA, configurable fallback | No |
| Zero language fallback | Removes task conditioning | Embedding norm check | Fail in real inference | Yes |
| Excess clipping hides semantic bugs | Rollout moves but semantics wrong | Clipping counter | Warn/fail above threshold | No |
| Chunk reused across reset | First actions from stale episode | Reset buffer log | Clear policy buffer on reset | Yes |
| Tiny rollout succeeds mechanically but behavior is wrong | False confidence | Numeric action and video logs | Inspect first chunk and gripper behavior | No |

## 15. Open Questions

These should be resolved before full benchmark evaluation:

1. Which weight variant should be used for evaluation?

Recommended default:

```text
checkpoint-60000/ema/model.safetensors
```

Validation:

```text
Load both EMA and non-EMA in a file-discovery/model-load smoke if memory allows.
Pick EMA unless loading fails or training notes say otherwise.
```

2. Should the runtime import transform helpers from `third_party/rdt/data/libero_vla_dataset.py`?

Recommendation:

```text
Reuse exact code where import is clean; otherwise copy small pure functions and
test against the training helper output.
```

3. Is online image orientation exactly the same as fine-tuning HDF5 images?

Validation:

```text
Save agentview and wrist frames before/after LeRobot preprocessing and visually
compare with a dataset frame from the same task family.
```

4. Does `observation.state` quaternion-to-axis-angle convention match HDF5 `ee_ori`?

Evidence:

```text
Both use robot EEF quaternion converted to axis-angle.
```

Validation:

```text
Compare online `observation.state[3:6]` to adapter.get_ee_pose() converted with
the same scipy/RDT utility for one reset state.
```

5. Does full-suite fine-tuning imply one shared dataset stat distribution for
all suites or per-suite stats only?

Evidence:

```text
dataset_stat.json contains per-suite entries for libero_10, libero_object,
libero_spatial, and libero_goal.
```

Runtime recommendation:

```text
Do not apply dataset-stat normalization to action outputs. For state input,
match the training loader's direct 128D state token convention.
```

6. Should `action_chunk_horizon` remain 8?

Recommendation:

```text
Use 8 for initial smoke because it limits stale open-loop execution. Tune only
after semantics are verified.
```

## 16. Success Criteria For Implementation

Primary implementation success criterion:

```text
Running `python main.py policy.type=rdt` for a 10-episode LIBERO evaluation
completes successfully and achieves a success rate greater than 0/10.
```

The completed run must use the existing VLS project output convention:

```text
outputs/libero/<timestamp>/results.txt
outputs/libero/<timestamp>/episode_*/
saved execution videos or rollout videos
```

The integration must not remain stuck at `0/10` because of adapter, observation,
action, checkpoint-loading, or semantic conversion bugs.

Prerequisites before the 10-episode gate:

```text
Checkpoint discovery passes for checkpoint-60000.
RDT config is parsed and logged.
Encoder paths are found.
policy.type=rdt routes through core/rdt_policy_steer.py.
The policy samples a `(1, 64, 128)` or equivalent full 128D action chunk.
The active action mask is exactly `[30,31,32,33,34,35,36,37,38,10]`.
Online observation conversion matches the fine-tuning state/action semantics.
Image ordering matches training.
Action decoding produces `(1, H, 7)` LIBERO OSC actions.
Gripper endpoint tests pass.
No third-party source is modified.
One tiny unguided LIBERO rollout runs without shape/device/semantic assertion failures.
```

Implementation should not be called complete merely because shapes line up or a
tiny rollout runs mechanically. It must also pass the semantic numeric checks
and the 10-episode non-zero-success rollout gate.

## 17. Decision Gate

Recommended decision:

```text
Proceed with Alternative D:
reuse core/rdt_policy_steer.py as the unified RDT policy path, add LIBERO
observation/action helpers, and use the LIBERO fine-tuning transforms as the
semantic source of truth.
```

Do not start writing-plans or implementation from this design until explicit
approval is given:

```text
Design approved. Proceed to writing-plans.
```
