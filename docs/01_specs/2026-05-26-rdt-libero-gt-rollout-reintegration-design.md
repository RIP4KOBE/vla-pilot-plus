---
date: 2026-05-26
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: feat/rdt-libero-gt-rollout-reintegration
source_commit: 360a6d052861
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/docs/docs/01_specs/2026-05-26-rdt-libero-gt-rollout-reintegration-design.md
summary: RDT-LIBERO GT Rollout Re-Integration Design
duplicate_sources:
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/docs/01_specs/2026-05-26-rdt-libero-gt-rollout-reintegration-design.md
---

# RDT-LIBERO GT Rollout Re-Integration Design

Status: draft for review
Date: 2026-05-26
Scope: design only

This document proposes a minimal re-integration of RDT-1B into the current
LIBERO evaluation runtime by aligning project-owned glue code with the
ground-truth rollout behavior from:

```text
third_party/Libero_RDT
```

The target checkpoint is:

```text
/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object/ema/model.safetensors
```

The target entrypoint remains:

```bash
python main.py policy.type=rdt
```

This design only covers unguided/original RDT denoising. VLS steering is out of
scope for this stage, but the policy wrapper should remain the unified location
for both unguided RDT and future RDT + VLS steering.

Do not proceed from this design to implementation until the user explicitly
approves it and says:

```text
Design approved. Proceed to writing-plans.
```

## 1. Goal

The goal is to run the GT LIBERO-finetuned RDT checkpoint through the existing
project runtime and obtain non-zero success on LIBERO Object rollouts:

```bash
python main.py policy.type=rdt
```

The primary implementation success criterion is:

```text
10 LIBERO episodes complete through the existing Hydra output convention,
execution videos and rollout outputs are saved under outputs/libero/<timestamp>,
and the success count is greater than 0/10.
```

Lower-level shape, semantic, and tiny-rollout checks are prerequisites. They are
not sufficient by themselves.

## 2. Inspected Materials

Required design and analysis documents:

```text
docs/docs/01_specs/2026-05-25-rdt-libero-finetuned-integration-design.md
docs/docs/02_analysis/rdt_intergration/2026-05-26-rdt-libero-finetune-gt-diff-analysis.md
docs/docs/02_analysis/rdt_intergration/2026-05-26-rdt-libero-rollout-gt-diff-analysis.md
```

GT rollout and model files:

```text
third_party/Libero_RDT/RDT_libero_finetune/libero_eval/libero_rdt_model.py
third_party/Libero_RDT/RDT_libero_finetune/libero_eval/libero_rdt_eval_with_eef_tracking.py
third_party/Libero_RDT/RDT_libero_finetune/libero_eval/config/eval_config_with_eef.yaml
third_party/Libero_RDT/RDT_libero_finetune/eval_fast/rdt_policy.py
third_party/Libero_RDT/RDT_libero_finetune/configs/state_vec.py
third_party/Libero_RDT/RDT_libero_finetune/models/rdt_runner.py
```

Current project runtime files:

```text
main.py
configs/config.yaml
configs/policy.yaml
configs/backend/libero.yaml
core/rdt_libero_obs_processor.py
core/rdt_libero_action_converter.py
core/rdt_policy_steer.py
core/env_adapters/libero_adapter.py
```

Checkpoint files inspected:

```text
/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object/config.json
/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object/ema/model.safetensors
```

No runtime code, config, checkpoint, or third-party source was modified while
preparing this design.

## 3. Core Diagnosis

The current integration can run mechanically, load checkpoints, produce videos,
and pass basic shape checks, but it still gets 0/10. The strongest evidence from
the GT comparison is that the current project is using the wrong RDT semantic
slots for both proprio conditioning and action decoding.

GT rollout uses:

```text
State input:
  robot0_joint_pos[7] + robot0_gripper_qpos[2]
  RDT state indices: [0,1,2,3,4,5,6,10,11]

Action output:
  EEF OSC velocity/action + gripper
  RDT action indices: [39,40,41,42,43,44,10]
```

Current project runtime still uses:

```text
State input:
  EEF position + EEF axis-angle / 6D rotation + one gripper-open scalar
  RDT state indices: [30,31,32,33,34,35,36,37,38,10]

Action output:
  reads [30,31,32,33,34,35,36,37,38,10]
  converts 6D rotation to rotvec
  divides by OSC position/rotation scales
  clips
```

This is not a small scale mismatch. It is a different state/action contract. If
the checkpoint was trained and evaluated like the GT project, the current
runtime is conditioning on off-contract state tokens and executing actions
decoded from unrelated RDT output slots.

## 4. Recommended Architecture

Use a minimal GT-semantic replacement in the existing project-owned RDT path:

```text
main.py
  -> policy.type=rdt
  -> RDTSteer.from_pretrained(...)
  -> LiberoAdapter.reset(...)
  -> Main._run_episode(...)
  -> RDTSteer.select_action(...)
  -> RDTLiberoObsProcessor
  -> RDT denoising in rdt_policy_steer.py
  -> RDTLiberoActionConverter
  -> LiberoAdapter.step(...)
```

Keep:

```text
core/rdt_policy_steer.py
core/rdt_libero_obs_processor.py
core/rdt_libero_action_converter.py
core/env_adapters/libero_adapter.py
python main.py policy.type=rdt
```

Do not add:

```text
core/rdt_libero_policy.py
policy.type=rdt_libero
new standalone unguided RDT evaluation script
```

The project should not preserve ManiSkill-specific branches or compatibility
logic inside the modified RDT-LIBERO path if that logic conflicts with GT
LIBERO-finetuned semantics.

## 5. Runtime Data Flow

The intended runtime data flow is:

```text
LIBERO raw observation
  keys:
    agentview_image
    robot0_eye_in_hand_image
    robot0_joint_pos
    robot0_gripper_qpos
    task / task_name / task language

RDTLiberoObsProcessor
  images:
    [agentview_t-1, wrist_t-1, None,
     agentview_t,   wrist_t,   None]
  state:
    9D joint+gripper proprio -> 128D RDT state
  masks:
    state mask [0..6,10,11]

RDTSteer._predict_unguided
  language embedding
  SigLIP image embedding
  128D state token
  128D action mask [39..44,10]
  DPM-Solver sampling, 5 inference steps

RDTLiberoActionConverter
  128D action chunk -> 7D LIBERO OSC action chunk
  extract [39,40,41,42,43,44,10]
  binarize gripper

LiberoAdapter.step
  env.step(7D action)
```

## 6. Observation Semantics

### 6.1 Camera Keys And Order

Use GT camera keys:

```text
agentview_image
robot0_eye_in_hand_image
```

Use GT camera order per history frame:

```text
[agentview, wrist, None]
```

Use two history frames, oldest to newest:

```text
[agentview_old, wrist_old, None, agentview_new, wrist_new, None]
```

The third camera slot is intentionally missing and should be represented as
`None`. The image encoder wrapper replaces it with a SigLIP-mean background
image, matching GT behavior.

### 6.2 Image Dtype, Range, And Preprocessing

Use raw LIBERO image arrays as the semantic source:

```text
layout: HWC
dtype: uint8
range: [0, 255]
color: RGB as returned by LIBERO
env render size: 128 x 128
```

Convert raw arrays to PIL images, then let the SigLIP image processor perform
normalization and resizing. Do not pre-normalize to `[0,1]` for the RDT path.
Do not use RGB/BGR conversion.

If an image is non-square, pad to square using the SigLIP image mean background,
as GT does. For the default 128x128 LIBERO images, padding should be a no-op.

### 6.3 Image Orientation

GT uses raw `agentview_image` and `robot0_eye_in_hand_image` arrays from LIBERO.
The RDT path should avoid relying on the current LeRobot-style flip and
`undo_libero_preprocessor_flip` round trip.

Preferred design:

```text
LiberoAdapter keeps or exposes raw LIBERO image arrays for RDT.
RDTLiberoObsProcessor consumes raw image arrays directly.
Visualization-specific flips remain separate from policy input.
```

If the implementation keeps the current tensor path temporarily, it must include
a pixel parity probe proving the final PIL image passed to SigLIP is identical
to GT raw `Image.fromarray(raw_obs[key])`.

### 6.4 Image History Handling

GT updates image history after every `env.step`. Current runtime updates RDT
history only when a new action chunk is generated. That creates chunk-spaced
history, which is a semantic mismatch.

Required design:

```text
The RDT image history buffer must update every environment step.
At each new RDT inference, the two history frames must be the two most recent
environment observations, not the two most recent action-chunk observations.
```

First inference should duplicate the initial image into both history slots:

```text
agentview_history = [initial_agentview, initial_agentview]
wrist_history     = [initial_wrist, initial_wrist]
```

GT nuance:

```text
GT initializes history and proprio from the set_init_state observation, then
performs 5 no-op settle steps without refreshing history immediately before the
first policy call.
```

Recommendation: copy this GT behavior first for parity. If implementation
friction is high, make the reset observation timing explicit in debug logs and
run a one-task A/B probe later.

### 6.5 State Source And Layout

Use GT proprio:

```text
robot0_joint_pos      shape (7,)
robot0_gripper_qpos   shape (2,)
proprio               shape (9,)
```

Format into 128D RDT state:

```text
state_128 = zeros(128)
state_128[0:7] = robot0_joint_pos

gripper_min = -0.04245
gripper_max = 0.05185
normalized_gripper = (robot0_gripper_qpos - gripper_min) / (gripper_max - gripper_min)

state_128[10] = normalized_gripper[0]
state_128[11] = normalized_gripper[1]
```

State mask:

```text
state_mask_128[0:7] = 1
state_mask_128[10] = 1
state_mask_128[11] = 1
```

Do not use EEF position, EEF quaternion, EEF axis-angle, EEF 6D rotation, or a
single gripper-open scalar for the GT RDT path.

### 6.6 Language Conditioning

GT language behavior:

```text
task_name = basename(bddl_file).replace(".bddl", "")
if outs/libero_embeddings/<suite>/<task_name>.pt exists:
  load precomputed embedding
else:
  instruction = task_name-derived language string
  encode live with T5
```

For current project integration:

```text
Use task language from the LIBERO benchmark only if it is proven equivalent to
GT's task-name-derived instruction for all selected tasks.
Cache T5 embeddings per task string.
Fail fast on empty instruction or zero embedding.
```

For the GT checkpoint and standard `libero_object`, live T5 encoding is
acceptable if no local precomputed embedding exists.

## 7. Action Semantics

### 7.1 RDT Output Layout

GT action slots:

```text
eef_vel_x                  39
eef_vel_y                  40
eef_vel_z                  41
eef_angular_vel_roll       42
eef_angular_vel_pitch      43
eef_angular_vel_yaw        44
gripper_open               10
```

The converter should decode:

```text
action_7d = action_128d[..., [39,40,41,42,43,44,10]]
```

Do not decode `[30..38]` for the GT path.

### 7.2 Action Chunk Length And Reuse

GT config:

```text
RDT pred_horizon: 64
exec_horizon: 8
```

The runtime should:

```text
sample one 64-step action chunk
execute chunk indices 0..7
then re-infer
clear cached chunk on reset/task change
discard remaining chunk actions on episode termination
```

### 7.3 Scaling And Clipping

GT does not apply metric position scaling, rotation conversion, or action
denormalization. It sends the extracted 7D action directly to `env.step()` after
gripper binarization.

Therefore the GT RDT path should remove:

```text
OSC_POS_SCALE division
OSC_ROT_SCALE division
6D rotation -> rotvec conversion
raw[:6] clipping as normal behavior
```

If clipping is kept as a defensive guard, it must be logged as a warning with
per-dimension saturation counters. Silent clipping can hide semantic bugs.

### 7.4 Gripper Convention

GT action postprocessing:

```text
if gripper_value < 0:
  gripper_action = -1
else:
  gripper_action = +1
```

The current adapter also binarizes the last action dimension before converting to
NumPy. That is compatible if the converter already produces `-1` or `+1`.

Open question:

```text
Whether -1 is "open" and +1 is "close" should be verified against LIBERO env
behavior and dataset actions, but the implementation should preserve GT's
thresholding exactly first.
```

## 8. Denoising And Model Inference

Keep denoising inside:

```text
core/rdt_policy_steer.py
```

The important functions/classes to align are:

```text
select_action()
_predict_unguided()
_postprocess_actions()
_RDTModelAdapter
_RDTDiTAdapter
```

### 8.1 Sampling

Use the checkpoint config:

```text
action_dim: 128
pred_horizon: 64
num_inference_timesteps: 5
prediction_type: sample
beta_schedule: squaredcos_cap_v2
clip_sample: false
control_frequency: 20
dtype: bfloat16
```

The current custom denoising loop can be reused if it is numerically equivalent
to `RDTRunner.predict_action`. The priority bug is mask semantics, not the loop
structure.

### 8.2 Distinct State Mask And Action Mask

The state mask and action mask must be different:

```text
state_mask active indices:
  [0,1,2,3,4,5,6,10,11]

action_mask active indices:
  [39,40,41,42,43,44,10]
```

Current code reuses the state mask as the action mask. That must be changed for
GT alignment.

### 8.3 Unguided Batch Size

GT samples one action trajectory per vector environment. For the unguided
single-env current runtime, the effective RDT sample batch should be:

```text
B = 1
```

The current `main.vls_config.sample_batch_size=20` is a VLS steering setting. It should not
affect unguided GT parity. Future VLS steering can re-enable particle sampling
after the unguided path succeeds.

### 8.4 Model Loading

The target checkpoint identity is the exact file:

```text
/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object/ema/model.safetensors
```

The config should come from:

```text
/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object/config.json
```

Acceptable implementation designs:

```text
Option 1:
  policy.rdt.pretrained_path points to the model root
  policy.rdt.weight_variant is ema
  logs show exact loaded weight:
    /mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object/ema/model.safetensors

Option 2:
  policy.rdt.pretrained_path points directly to ema/model.safetensors
  loader derives model root from the file path and reads parent config.json
```

The debug log must report:

```text
config path
weight file
state/action indices
num inference steps
control frequency
dtype/device
```

## 9. LIBERO Evaluation Protocol

### 9.1 Suite And Task Selection

The GT checkpoint is LIBERO-Object. The default target suite should be:

```text
libero_object
```

For the 10-episode success gate, use the current project convention:

```text
main.episode_num = 10
backend.libero.task_ids_filter = null
```

This evaluates the 10 tasks in LIBERO Object once each through the current
serial runtime.

### 9.2 Environment Setup

Match GT as closely as possible:

```text
OffScreenRenderEnv(
  bddl_file_name=<task bddl>,
  camera_heights=128,
  camera_widths=128,
)
```

For unguided RDT, policy input does not need depth or segmentation. Existing VLS
visualization/perception paths can keep their own needs separate.

### 9.3 Reset And Init States

GT practical evaluation uses:

```text
env.reset()
obs = env.set_init_state(init_states_batch)
for _ in range(5):
  env.step(np.zeros((env_num, 7), dtype=np.float32))
```

Current project creates one `LiberoEnv` per task with `episode_index=0`. For the
10-task, one-episode-per-task gate, this is acceptable as a first pass. If later
running multiple episodes per task, init states should advance as:

```text
init_state_id = episode_index % num_init_states
```

### 9.4 Max Episode Length

GT uses:

```text
MAX_EPISODE_STEPS = 720
```

The RDT-LIBERO GT path should use 720 for the success gate. A shorter horizon can
turn weak-but-correct behavior into measured failure.

### 9.5 Success Detection And Outputs

Keep the current project output convention:

```text
outputs/libero/<timestamp>/
  .hydra/
  episode_*/
  results.txt
  execution videos
```

Success detection can remain based on LIBERO `check_success()` surfaced through
the adapter. The design does not require adopting GT's exact CSV/video writer.

One caution: auto-reset inside the inner env after terminal success can make
debugging harder. It is not the top suspected cause of 0/10, but terminal info
must be preserved before any reset.

## 10. Proposed Component Responsibilities

### 10.1 core/rdt_libero_obs_processor.py

Responsibility:

```text
Convert current LIBERO raw observation information into GT-compatible RDT inputs.
```

Required semantics:

```text
input images from raw LIBERO camera keys
step-spaced two-frame history
raw joint_pos + gripper_qpos state
128D state indices [0..6,10,11]
state mask [0..6,10,11]
task string validation
first-step debug summaries
```

Remove or stop using for the RDT path:

```text
EEF pose state
axis-angle state
6D rotation state
single gripper-open state scalar
undoing LeRobot image flip as a core semantic dependency
```

### 10.2 core/rdt_libero_action_converter.py

Responsibility:

```text
Convert GT RDT 128D action chunks into LIBERO 7D OSC env actions.
```

Required semantics:

```text
GT action indices [39,40,41,42,43,44,10]
extract direct action values
gripper threshold <0 -> -1 else +1
return (1, H, 7) action chunk
```

Remove or stop using for the GT path:

```text
rotvec_to_ortho6d action target logic
ortho6d_to_rotvec action decoding
OSC_POS_SCALE division
OSC_ROT_SCALE division
reading [30..38] action slots
```

### 10.3 core/rdt_policy_steer.py

Responsibility:

```text
Unified RDT policy wrapper for unguided denoising now and future VLS steering.
```

Required changes by function/class:

```text
select_action():
  consume GT-compatible converted observation
  keep guidance disabled for this stage
  cache and reuse 8 decoded actions per chunk

_predict_unguided():
  run 128D denoising
  use B=1 for unguided parity
  mask final action with GT action mask

_postprocess_actions():
  call GT-compatible action converter
  log first chunk stats

_RDTModelAdapter:
  build state tokens with state mask
  build action mask separately from state mask
  report exact active state/action indices

_RDTDiTAdapter:
  keep RDTRunner-equivalent denoising behavior
  do not project into old EEF-pose action subspace
```

### 10.4 core/env_adapters/libero_adapter.py

Responsibility:

```text
Expose LIBERO raw observation fields needed by RDT while preserving existing
adapter responsibilities for reset, step, video, and VLS utilities.
```

Required RDT support:

```text
raw agentview_image
raw robot0_eye_in_hand_image
raw robot0_joint_pos
raw robot0_gripper_qpos
task name / instruction
step-spaced observation history update hook or raw observation access
max episode length 720 for RDT GT eval
```

The adapter may continue supporting other policy observation formats, but the
RDT path should not depend on `LiberoProcessorStep` generating EEF-pose
`observation.state`.

### 10.5 configs/policy.yaml

The RDT default should target the GT checkpoint identity:

```text
/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object/ema/model.safetensors
```

or the root path plus `weight_variant=ema`, as long as logs prove the exact EMA
file was loaded.

Keep:

```text
policy.type=rdt
action_chunk_horizon=8
control_frequency=20
num_inference_steps=null
fail_on_zero_language_embedding=true
```

Remove or deprecate:

```text
undo_libero_preprocessor_flip as a required RDT semantic knob
old local checkpoint path as the default for GT re-integration
```

### 10.6 configs/backend/libero.yaml

For GT checkpoint validation:

```text
suite_name: libero_object
observation_width: 128
observation_height: 128
num_steps_wait: 5
max_episode_steps: 720
task_ids_filter: null
```

## 11. Alternatives Considered

### Alternative A: Minimal GT-semantic replacement in existing files

Description:

```text
Keep current policy.type=rdt route and current files, but replace RDT-LIBERO
observation/action semantics with GT semantics.
```

Likely affected files:

```text
core/rdt_libero_obs_processor.py
core/rdt_libero_action_converter.py
core/rdt_policy_steer.py
core/env_adapters/libero_adapter.py
configs/policy.yaml
configs/backend/libero.yaml
```

Pros:

```text
Preserves current entrypoint.
Preserves output/video convention.
Keeps future VLS steering in same wrapper.
Removes the dominant semantic mismatch.
```

Cons:

```text
Requires careful removal of old EEF-pose assumptions.
Current adapter preprocessing path is shared with other policies, so RDT needs a
clear raw-observation path.
```

Risk:

```text
Medium implementation risk, high expected reliability if parity probes pass.
```

Recommendation level:

```text
Recommended.
```

### Alternative B: Directly reuse GT eval/model code

Description:

```text
Import or shell out to GT Libero_RDT evaluation logic and bypass current project
policy wrapper.
```

Pros:

```text
Maximum semantic parity.
Good as an independent checkpoint/runtime sanity probe.
```

Cons:

```text
Does not preserve python main.py policy.type=rdt.
Does not integrate with current output/video/VLS runtime.
Introduces brittle third-party import paths.
```

Risk:

```text
Low semantic risk, high integration risk.
```

Recommendation level:

```text
Use only as a verification probe, not as the project integration.
```

### Alternative C: New clean core/rdt_libero_policy.py route

Description:

```text
Add a separate LIBERO-only RDT policy and route.
```

Pros:

```text
Could isolate the GT semantics from old code.
```

Cons:

```text
Violates the preferred architecture.
Splits unguided RDT from future VLS steering.
Creates a second policy route to maintain.
```

Risk:

```text
Medium semantic risk, medium rollback difficulty.
```

Recommendation level:

```text
Not recommended.
```

## 12. Validation Plan

### 12.1 File Discovery Validation

Purpose:

```text
Verify required paths before model or env work.
```

Checks:

```text
GT checkpoint file exists
GT config.json exists
T5 encoder path exists
SigLIP encoder path exists and resolves to a snapshot
LIBERO Object data/suite paths exist
current RDT integration files exist
GT reference files exist
```

Expected result:

```text
Clear pass/fail report with missing paths listed explicitly.
```

### 12.2 Index Contract Validation

Purpose:

```text
Prevent silent state/action slot mismatches.
```

Expected constants:

```text
GT state indices:  [0,1,2,3,4,5,6,10,11]
GT action indices: [39,40,41,42,43,44,10]
```

Fail if:

```text
RDT state mask equals action mask
RDT action converter reads [30..38]
RDT observation processor writes EEF pose slots [30..38]
```

### 12.3 One-Sample Observation Validation

Purpose:

```text
Validate one online LIBERO observation before model inference.
```

Checks:

```text
agentview image shape, dtype, min/max
wrist image shape, dtype, min/max
history length and order
joint_pos shape (7,)
gripper_qpos shape (2,)
state_128 shape (1,128)
state active indices [0..6,10,11]
language string non-empty
```

### 12.4 Action Conversion Validation

Purpose:

```text
Validate RDT 128D output to LIBERO 7D action conversion.
```

Use deterministic synthetic input:

```text
set only indices [39,40,41,42,43,44,10]
verify output action is exactly those first six values plus thresholded gripper
verify indices [30..38] have no effect
```

### 12.5 GT Parity Action Probe

Purpose:

```text
Compare current project wrapper against GT wrapper on identical inputs.
```

Procedure:

```text
load exact same checkpoint
use same raw LIBERO observation
use same task language embedding
fix torch seed before sampling
compare:
  GT extracted 7D chunk
  project raw 128D chunk
  project decoded 7D chunk
```

Expected result:

```text
Project decoded 7D actions should match GT extraction within numerical tolerance
when both wrappers use the same model, seed, observation, and language.
```

### 12.6 Tiny Rollout Smoke Test

Purpose:

```text
Validate end-to-end mechanics after semantic fixes.
```

Design:

```text
suite: libero_object
task_ids_filter: [0]
episodes: 1
checkpoint: /mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object/ema/model.safetensors
use_guidance: false
max_episode_steps: 720
save video
log first-step observation and first action chunk summaries
```

This is a post-approval implementation validation. It should not be run during
design-only review.

### 12.7 Final Success Gate

Command:

```bash
python main.py policy.type=rdt
```

Expected result:

```text
10 LIBERO Object episodes complete.
outputs/libero/<timestamp>/results.txt is written.
execution videos are saved.
Success count is greater than 0/10.
```

## 13. Debug Instrumentation

Add lightweight first-step debug logs behind an RDT debug flag.

Observation logs:

```text
raw image keys present
image shapes, dtype, min/max
image history frame ids or hashes
state source keys present
joint_pos summary
gripper_qpos summary before and after normalization
state active indices
language string and embedding shape
```

Inference logs:

```text
config path
weight file
state indices
action indices
state mask active indices
action mask active indices
image embedding shape
text embedding shape
num inference steps
control frequency
dtype/device
```

Action logs:

```text
raw 128D action chunk shape
extracted 7D action chunk shape
first action numeric values
gripper raw value and binarized command
min/max per action dimension
clipping/saturation counter if clipping exists
cached chunk reset on env reset
```

Avoid excessive logs during full rollout. First step and first chunk per episode
are enough by default.

## 14. Risks

| Risk | Why it matters | Early detection | Mitigation | Blocks implementation? |
|---|---|---|---|---|
| Wrong RDT state indices remain | Model conditions on off-contract proprio | Index contract validation | Fail fast if active state indices are not `[0..6,10,11]` | Yes |
| Wrong action slots remain | Env executes unrelated model outputs | Synthetic action conversion test | Decode only `[39..44,10]` | Yes |
| State mask reused as action mask | Denoising targets wrong dimensions | Log both masks and assert they differ as expected | Build explicit action mask | Yes |
| Image history is chunk-spaced | Temporal conditioning differs from GT | Log image hashes per inference | Update history every env step | Yes |
| Image orientation mismatch | Policy sees flipped images | Pixel parity probe vs raw GT image | Bypass LeRobot flip for RDT raw path | Yes |
| Wrong checkpoint file loaded | Evaluates different weights than target | Log exact weight path | Require exact EMA file or root+variant resolution | Yes |
| Reset/no-op observation timing differs | First chunk distribution shift | Log pre/post-settle image/state source | Initially copy GT timing | No, but high priority |
| Max episode length too short | Correct policy may fail by truncation | Log truncation step | Use 720 for RDT GT eval | No |
| Gripper convention inverted | Grasp/open actions fail | Gripper probe and videos | Preserve GT threshold first, then verify semantics | Yes if unresolved after first smoke |
| Existing PI05/Diffusion paths break | Shared adapter changes can regress other policies | Run route-specific smoke checks | Keep RDT raw path additive or gated | No for RDT, but must avoid broad regression |

## 15. Open Questions

1. Reset observation timing:

```text
Should the project exactly copy GT's "history from set_init_state before no-op"
behavior, or use the post-settle observation?
```

Recommendation:

```text
Copy GT first, then relax only if parity probes show no difference.
```

2. Language source:

```text
Are all current `task.language` strings identical to GT's BDDL-filename-derived
instructions for the selected LIBERO Object tasks?
```

Recommendation:

```text
Run a string parity probe before rollout. Use GT extraction if there is any
difference.
```

3. Gripper semantics:

```text
Does `-1` mean open and `+1` mean close in the exact LIBERO env/controller path?
```

Recommendation:

```text
Preserve GT thresholding exactly for checkpoint parity, then validate with a
small no-model gripper action probe if behavior looks inverted.
```

## 16. Decision

Recommended approach:

```text
Implement Alternative A: minimal GT-semantic replacement in the existing RDT
route.
```

This preserves:

```text
python main.py policy.type=rdt
current Hydra output convention
current video/result saving
rdt_policy_steer.py as the unified RDT policy wrapper
project-owned wrapper/adaptor boundaries
```

It replaces:

```text
EEF-pose state semantics
6D-rotation action decoding
old [30..38,10] action slots
state mask reused as action mask
chunk-spaced image history
local fine-tuned checkpoint default
```

The design should be considered ready for a writing-plan only after explicit
approval.
