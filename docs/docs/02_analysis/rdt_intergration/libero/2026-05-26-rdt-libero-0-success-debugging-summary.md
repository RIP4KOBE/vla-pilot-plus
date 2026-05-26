# RDT LIBERO 0/10 Success Debugging Summary

Date: 2026-05-26

Worktree:

```text
.worktrees/feat/rdt-libero-object-ckpt
```

Primary command under investigation:

```bash
CUDA_VISIBLE_DEVICES=0 /home/hynx/miniconda3/envs/vla-pilot/bin/python main.py policy.type=rdt
```

Original target checkpoint:

```text
/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-60000
```

Latest checkpoint found on 2026-05-26:

```text
/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-98000
```

## Executive Summary

The RDT LIBERO integration now runs mechanically end-to-end through the project runtime entrypoint:

```bash
python main.py policy.type=rdt
```

The adapter path loads the LIBERO-finetuned RDT checkpoint, encodes LIBERO observations, samples RDT action chunks, decodes them to LIBERO 7D OSC actions, executes rollout episodes, and saves rollout videos.

However, the success-rate gate was not met for the original checkpoint-60000:

```text
outputs/libero/2026-05-25_14-48-37/results.txt
Backend: libero
Success count: 0/10
Success rate: 0.00%
```

All 10 videos were saved:

```text
outputs/libero/2026-05-25_14-48-37/episode_1/episode_1_fail_agentview.mp4
...
outputs/libero/2026-05-25_14-48-37/episode_10/episode_10_fail_agentview.mp4
```

The current conclusion is:

1. The integration is no longer failing due to obvious shape/device/key/checkpoint errors.
2. The main observation/action interface now matches the LIBERO fine-tuning transform as closely as could be verified from local code.
3. The remaining 0/10 behavior is not explained by a single confirmed adapter bug.
4. The strongest unresolved hypotheses are checkpoint quality, training/evaluation distribution mismatch, action prediction quality, and behavior-cloning compounding error.

## Files And Components Touched During Integration

Project-owned runtime files:

```text
core/rdt_libero_action_converter.py
core/rdt_libero_obs_processor.py
core/rdt_policy_steer.py
core/env_adapters/libero_adapter.py
main.py
configs/policy.yaml
configs/backend/libero.yaml
```

Project-owned tests:

```text
tests/test_rdt_libero_action_converter.py
tests/test_rdt_libero_obs_processor.py
tests/test_rdt_steer.py
tests/test_rdt_runtime_contract.py
tests/test_env_adapters_imports.py
tests/test_policy_observation_sampling.py
```

Third-party source was inspected but not intentionally modified:

```text
third_party/rdt/data/libero_vla_dataset.py
third_party/rdt/train/dataset.py
third_party/rdt/train/train.py
third_party/rdt/train/sample.py
third_party/rdt/models/rdt_runner.py
third_party/rdt/scripts/maniskill_model.py
third_party/libero/scripts/create_dataset.py
third_party/libero/libero/lifelong/metric.py
third_party/lerobot/src/lerobot/envs/libero.py
```

Note: the parent repo status still reports nested third-party paths:

```text
 ? third_party/rdt
?? third_party/libero/
```

This means third-party cleanliness should be audited separately before merge. The reviewer saw no tracked third-party source diff in `third_party/rdt`, but this status weakens a strict "no third-party changes" audit.

## Verified Fine-Tuning Semantics

Primary source:

```text
third_party/rdt/data/libero_vla_dataset.py
```

The fine-tuning dataset maps LIBERO data into RDT as follows.

Active RDT slots:

```text
LIBERO_RDT_INDICES = [30, 31, 32, 33, 34, 35, 36, 37, 38, 10]
ACTIVE_INDICES_SORTED = [10, 30, 31, 32, 33, 34, 35, 36, 37, 38]
```

State:

```text
state[:, 30:33] = ee_pos
state[:, 33:39] = rotvec_to_ortho6d(ee_ori)
state[:, 10] = gripper_open
state/action dimension = 128
```

Action:

```text
raw LIBERO action = [dx, dy, dz, drot_x, drot_y, drot_z, gripper]
raw action[0:6] is normalized OSC_POSE command in [-1, 1]
raw action[0:3] is scaled to meters using output_max = [0.05, 0.05, 0.05]
raw action[3:6] is scaled to rotation-vector units using output_max = [0.5, 0.5, 0.5]
raw gripper = -1 open, +1 close
RDT gripper_open = (1 - raw_gripper) / 2, so 1=open and 0=closed
```

Image history:

```text
history size = 2
camera slots = 3
training image order:
  [cam_high_prev, cam_right_wrist_prev, cam_left_wrist_prev,
   cam_high_now,  cam_right_wrist_now,  cam_left_wrist_now]
```

For LIBERO fine-tuning, `cam_left_wrist` is invalid and is represented by background image in the RDT consumer.

## Runtime Architecture After Integration

The runtime still uses the existing policy route:

```bash
python main.py policy.type=rdt
```

No `core/rdt_libero_policy.py` was created. The unified policy remains:

```text
core/rdt_policy_steer.py
```

The key runtime path is:

```text
main.py
  -> RDTSteer.from_pretrained(...)
  -> RDTSteer.post_init(...)
  -> RDTSteer.select_action(...)
  -> RDTLiberoObsProcessor.process(...)
  -> RDTSteer._get_lang_embed(...)
  -> RDTSteer._predict_unguided(...)
  -> RDTSteer._postprocess_actions(...)
  -> decode_rdt_libero_action_chunk(...)
  -> LiberoAdapter.step(...)
```

Guided RDT/VLS steering is explicitly deferred. Current validation uses unguided RDT denoising only.

## Unit And Contract Tests

Focused verification command:

```bash
pytest \
  tests/test_rdt_libero_action_converter.py \
  tests/test_rdt_libero_obs_processor.py \
  tests/test_rdt_steer.py \
  tests/test_rdt_runtime_contract.py \
  tests/test_env_adapters_imports.py \
  tests/test_policy_observation_sampling.py \
  -q
```

Fresh result after implementation:

```text
50 passed in 14.95s
```

The tests cover:

1. RDT active index contract.
2. Gripper open/close inverse mapping.
3. Rotation-vector to ortho6D and back.
4. LIBERO raw action to 128D RDT action.
5. 128D RDT action chunk to LIBERO 7D action.
6. Observation conversion into 128D state and mask.
7. Image history reset behavior.
8. Missing camera, empty language, and bad state fail-fast checks.
9. RDT policy stub path using full 128D state/action masks.
10. `policy.type=rdt` config and checkpoint/encoder path discovery.

## Action Converter Probe

Final reviewer ran an action-transform comparison against the fine-tuning dataset code:

```text
converter_vs_train_max_abs 0.0
```

Interpretation:

The project-owned action converter matches `third_party/rdt/data/libero_vla_dataset.py` for the tested transform path.

## Denoising Loop Probe

The custom unguided denoising loop in `core/rdt_policy_steer.py` was compared against upstream `RDTRunner.conditional_sample` on the same LIBERO-format sample.

Result:

```text
max_abs_diff 0.0
mean_abs_diff 0.0
```

Interpretation:

The hand-mirrored denoising loop is not the observed root cause of 0/10. It numerically matches the upstream sampling loop for the tested setup.

## Image Orientation And History Debugging

### Orientation

The online LIBERO processor receives images after `LiberoProcessorStep`, which flips height and width. RDT fine-tuning HDF5 images are in the original stored orientation. Therefore `RDTLiberoObsProcessor` supports:

```yaml
undo_libero_preprocessor_flip: true
```

Evidence:

```text
/tmp/hdf5_alphabet_agent0.png
/tmp/hdf5_alphabet_wrist0.png
/tmp/online_rdt_slot3.png
/tmp/online_rdt_slot4.png
/tmp/online_rdt_noundo_slot3.png
/tmp/online_rdt_noundo_slot4.png
```

Finding:

`undo_libero_preprocessor_flip=true` matched the HDF5 orientation. `false` produced rotated images and was treated as wrong.

### History Reset

Training-time image history behavior:

```text
At first timestep, missing previous frames are invalid and are replaced by background image by the consumer.
```

The initial implementation duplicated current images into previous slots. This was later changed so that after reset:

```text
first processed obs images:
  [None, None, None, agent_now, wrist_now, None]

second processed obs images:
  [agent_prev, wrist_prev, None, agent_now, wrist_now, None]
```

Commit:

```text
ee80b46 Align RDT LIBERO reset image history
```

Relevant tests:

```text
tests/test_rdt_libero_obs_processor.py
```

Result after the reset-history fix:

```text
16 passed in tests/test_rdt_libero_obs_processor.py
50 passed in the focused RDT/LIBERO suite
```

## Reset And Environment Parity Debugging

The LIBERO adapter was aligned with official LIBERO reset/eval behavior:

1. Apply benchmark init state after reset.
2. Execute reset-settle dummy actions.
3. Clear RDT observation/action chunk buffers on policy reset.
4. Forward max episode steps.
5. Use 600 max steps in local config for the tested default run.

Relevant code:

```text
core/env_adapters/libero_adapter.py
configs/backend/libero.yaml
```

Important nuance:

Two no-op conventions exist:

```text
third_party/libero/libero/lifelong/metric.py uses zero dummy action:
  [0, 0, 0, 0, 0, 0, 0]

third_party/lerobot/src/lerobot/envs/libero.py uses open-gripper dummy:
  [0, 0, 0, 0, 0, 0, -1]
```

Final reviewer probe:

```text
zero dummy reset-settle gripper_open ~= 0.5169
open dummy reset-settle gripper_open ~= 0.8485
first HDF5 demos are around 0.90
```

An open-gripper reset ablation was run by monkey-patching `get_libero_dummy_action()` to return `[0,0,0,0,0,0,-1]`.

Result:

```text
outputs/libero/2026-05-25_14-47-04
Success count: 0/1
Success rate: 0.00%
```

Interpretation:

The zero dummy gripper state remains semantically suspicious because it differs from the fine-tuning demo initial gripper-open distribution. But switching to open-gripper reset did not rescue the first task in a one-episode ablation, so this is not a confirmed single-line fix.

## Online Initial State Versus HDF5 First State

Task: alphabet soup, LIBERO object task 0.

Online after official reset plus five no-op steps:

```text
gripper_open 0.5168961
eef_pos [-0.152159, -0.006591, 0.248694]
rot6d [0.997474, -0.005279, -0.070829, -0.005443, -0.999983, -0.002126]
```

HDF5 first training observation:

```text
ee_pos[0] [-0.134612, -0.031594, 0.260872]
ee_ori[0] [3.134159, -0.044648, -0.065001]
gripper_qpos [0.036104, -0.036299]
first raw action [0.2464, -0.5170, 0.0161, 0.0, 0.0182, -0.0, -1.0]
```

Position difference:

```text
online - HDF5 = [-0.017547, 0.025003, -0.012179]
```

Interpretation:

The online reset state is close but not identical to the first supervised fine-tuning observation. This could contribute to distribution shift, but by itself does not prove the adapter is wrong.

## Dataset Timing Analysis

Primary source:

```text
third_party/libero/scripts/create_dataset.py
```

Findings:

1. `create_dataset.py` records observations after stepping the environment with an expert action.
2. It stores same-index `actions[j]`.
3. It skips `cap_index = 5`.
4. Therefore the first HDF5 sample is after some initial expert motion, not simply benchmark reset plus five no-op steps.

Interpretation:

The policy is asked online to start from an official eval reset state, while training samples begin after the demonstration capture skip. This is a plausible train/eval distribution mismatch.

This mismatch is not obviously fixable in the adapter without changing the evaluation protocol, because the final goal is to run the benchmark environment, not replay training demos.

## Checkpoint And Training Evidence

Run directory:

```text
/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903
```

Checkpoint-60000 config:

```text
pred_horizon = 64
action_dim = 128
state_token_dim = 128
img history/cameras = [2, 3]
lang_token_dim = 4096
img_token_dim = 1152
noise_scheduler.num_inference_timesteps = 5
prediction_type = sample
```

TensorBoard/hparams evidence found during debugging:

```text
/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/logs/roboticDiffusionTransformer/1779545462.0929868/hparams.yml
```

Observed:

```text
dataset_type: finetune
load_from_hdf5: true
sample_period: 500
training included libero_10, libero_object, libero_spatial, libero_goal
```

Sample MSE evidence:

```text
step 60000 libero_object_sample_mse ~= 0.0034
step 60000 overall sample mse ~= 0.0040
near-best overall sample MSE around checkpoint-72000
training later continued beyond checkpoint-77000
```

Important nuance:

The training sampler metrics were reported on the non-EMA model, while runtime default used EMA weights. A non-EMA checkpoint-60000 ablation was run.

Result:

```text
outputs/libero/2026-05-25_14-39-36
Success count: 0/1
Success rate: 0.00%
```

Checkpoint-72000 EMA ablation:

```text
outputs/libero/2026-05-25_14-40-45
Success count: 0/1
Success rate: 0.00%
```

Interpretation:

The EMA-vs-non-EMA question and one near-best checkpoint did not produce a quick success improvement.

## Offline Action Quality Probes

Offline HDF5 probe on alphabet soup demo with EMA checkpoint-60000 showed poor first-action matching.

Example:

```text
step 0 predicted raw approx:
  [0.2612, 0.0705, -0.0696, -0.0198, 0.0217, -0.0680, -1]

step 0 ground truth raw:
  [0.2464, -0.5170, 0.0161, 0, 0.0182, 0, -1]

RMSE6 ~= 0.244
```

The `y` component mismatch was especially large.

Chunk-offset probe:

```text
step0: best predicted index for same-time was 0; pred index best matching gt0 was 6 but weak
step5: best same-time pred index 15; pred0 best future offset 15
step20: best same-time pred index 2; pred0 best future offset 2
step60: best same-time pred index 4; pred0 best future offset 5
step100: best same-time pred index 2
```

Interpretation:

No clean fixed "execute chunk index k first" correction was supported. The action quality looked weak or inconsistent, not simply shifted by one stable offset.

## Language Conditioning Probe

Same observation with different instructions produced nonzero but small action differences. Empty language produced similar actions.

Interpretation:

The model is not completely ignoring language, but language conditioning appears weak in this probe. This could matter for multi-task LIBERO object performance.

## Runtime Evaluation Runs And Results

### Full 10-Episode Gate Before Latest Reset-History Fix

Command:

```bash
CUDA_VISIBLE_DEVICES=0 /home/hynx/miniconda3/envs/vla-pilot/bin/python main.py policy.type=rdt
```

Output:

```text
outputs/libero/2026-05-25_13-59-01
Success count: 0/10
Success rate: 0.00%
```

### One-Episode Horizon-64 Ablation

Command:

```bash
CUDA_VISIBLE_DEVICES=0 /home/hynx/miniconda3/envs/vla-pilot/bin/python main.py \
  policy.type=rdt \
  policy.rdt.action_chunk_horizon=64 \
  main.episode_num=1 \
  main.sample_batch_size=1 \
  main.debug_draw_trajectory=false \
  main.use_guidance=false \
  main.use_fkd=false \
  main.use_diversity=false \
  'backend.libero.task_ids_filter=[0]'
```

Output:

```text
outputs/libero/2026-05-25_14-16-28
Success count: 0/1
Success rate: 0.00%
```

### One-Episode After Reset-History Fix

Command:

```bash
CUDA_VISIBLE_DEVICES=0 /home/hynx/miniconda3/envs/vla-pilot/bin/python main.py \
  policy.type=rdt \
  main.episode_num=1 \
  main.debug_draw_trajectory=false \
  main.use_guidance=false \
  main.use_fkd=false \
  main.use_diversity=false \
  main.sample_batch_size=1 \
  'backend.libero.task_ids_filter=[0]'
```

Output:

```text
outputs/libero/2026-05-25_14-22-18
Success count: 0/1
Success rate: 0.00%
```

Video/contact sheet evidence:

```text
/tmp/rdt_historyfix/ep1.jpg
```

Observation:

The policy was active but drifted toward the basket region rather than acquiring the target object.

### Non-EMA Checkpoint-60000 Ablation

Command:

```bash
CUDA_VISIBLE_DEVICES=0 /home/hynx/miniconda3/envs/vla-pilot/bin/python main.py \
  policy.type=rdt \
  policy.rdt.weight_variant=null \
  main.episode_num=1 \
  main.debug_draw_trajectory=false \
  main.use_guidance=false \
  main.use_fkd=false \
  main.use_diversity=false \
  main.sample_batch_size=1 \
  'backend.libero.task_ids_filter=[0]'
```

Output:

```text
outputs/libero/2026-05-25_14-39-36
Success count: 0/1
Success rate: 0.00%
```

### Checkpoint-72000 EMA Ablation

Command:

```bash
CUDA_VISIBLE_DEVICES=0 /home/hynx/miniconda3/envs/vla-pilot/bin/python main.py \
  policy.type=rdt \
  policy.rdt.pretrained_path=/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-72000 \
  main.episode_num=1 \
  main.debug_draw_trajectory=false \
  main.use_guidance=false \
  main.use_fkd=false \
  main.use_diversity=false \
  main.sample_batch_size=1 \
  'backend.libero.task_ids_filter=[0]'
```

Output:

```text
outputs/libero/2026-05-25_14-40-45
Success count: 0/1
Success rate: 0.00%
```

### Open-Gripper Reset Ablation

Method:

Monkey-patch `get_libero_dummy_action()` to return:

```python
[0, 0, 0, 0, 0, 0, -1]
```

Output:

```text
outputs/libero/2026-05-25_14-47-04
Success count: 0/1
Success rate: 0.00%
```

### Fresh Required 10-Episode Gate On Current HEAD

Command:

```bash
CUDA_VISIBLE_DEVICES=0 /home/hynx/miniconda3/envs/vla-pilot/bin/python main.py policy.type=rdt
```

Output:

```text
outputs/libero/2026-05-25_14-48-37
Success count: 0/10
Success rate: 0.00%
```

Artifacts:

```text
outputs/libero/2026-05-25_14-48-37/episode_1/episode_1_fail_agentview.mp4
outputs/libero/2026-05-25_14-48-37/episode_2/episode_2_fail_agentview.mp4
outputs/libero/2026-05-25_14-48-37/episode_3/episode_3_fail_agentview.mp4
outputs/libero/2026-05-25_14-48-37/episode_4/episode_4_fail_agentview.mp4
outputs/libero/2026-05-25_14-48-37/episode_5/episode_5_fail_agentview.mp4
outputs/libero/2026-05-25_14-48-37/episode_6/episode_6_fail_agentview.mp4
outputs/libero/2026-05-25_14-48-37/episode_7/episode_7_fail_agentview.mp4
outputs/libero/2026-05-25_14-48-37/episode_8/episode_8_fail_agentview.mp4
outputs/libero/2026-05-25_14-48-37/episode_9/episode_9_fail_agentview.mp4
outputs/libero/2026-05-25_14-48-37/episode_10/episode_10_fail_agentview.mp4
```

## Final Reviewer Findings

Reviewer found no hard remaining bug in:

1. Image history/order.
2. Image orientation.
3. 128D state/action slot mapping.
4. Action scaling.
5. Gripper inverse mapping.
6. `policy.type=rdt` route.
7. Chunk buffering.
8. Reset buffer clearing.

Reviewer highlighted one important remaining adapter-semantic concern:

```text
reset-settle dummy action leaves gripper half-open under zero dummy action,
whereas demos start closer to fully open.
```

But the open-gripper ablation remained 0/1, so this is not a confirmed root cause.

Reviewer also noted:

```text
get_policy_observation() still writes diagnostic probe logs under docs/superpowers/...
```

This is not likely to cause 0/10, but it makes eval non-clean and should be removed or gated before final merge.

## Current Working Hypotheses

### Hypothesis 1: Checkpoint Action Quality Is Insufficient

Evidence:

1. Offline first-action prediction did not match HDF5 ground truth well.
2. Chunk-offset probe did not show a simple recoverable temporal offset.
3. Online rollouts execute plausible-shaped actions but do not reliably acquire objects.

Status:

Strong hypothesis.

### Hypothesis 2: Train/Eval Initial-State Distribution Mismatch

Evidence:

1. HDF5 first samples are after expert motion and capture skip.
2. Official eval starts from benchmark init states plus reset-settle no-ops.
3. Online initial EEF pose and gripper open differ from HDF5 first supervised observation.

Status:

Plausible hypothesis.

### Hypothesis 3: Reset Gripper Convention Hurts Conditioning

Evidence:

1. Zero dummy reset produces gripper_open ~= 0.5169.
2. Demos appear closer to open ~= 0.90.
3. RDT conditions directly on gripper_open in slot 10.

Counter-evidence:

1. Open-gripper reset ablation still produced 0/1.
2. Official LIBERO lifelong metric uses zero dummy action.

Status:

Plausible but not sufficient alone.

### Hypothesis 4: EMA / Checkpoint Selection

Evidence:

1. Training sample MSE metrics were non-EMA.
2. Runtime default uses EMA.

Counter-evidence:

1. checkpoint-60000 non-EMA ablation produced 0/1.
2. checkpoint-72000 EMA ablation produced 0/1.

Status:

Not ruled out globally, but the tested ablations did not improve success.

### Hypothesis 5: Language Conditioning Weakness

Evidence:

1. Different instructions changed actions only modestly in the probe.
2. Empty language produced similar actions.

Status:

Plausible contributor, especially across multi-task suites.

## Recommended Next Analyses

1. Evaluate latest checkpoint-98000 through the same `policy.type=rdt` route.
2. Run offline prediction probes on checkpoint-98000:
   - same HDF5 sample as checkpoint-60000
   - compare first-action RMSE
   - compare action chunk alignment
   - compare language sensitivity
3. Quantify online action saturation:
   - per-dimension min/max before clip
   - clipping frequency
   - gripper close/open switching rate
4. Compare rollout video trajectories against HDF5 expert trajectories:
   - EEF xy path
   - z descent timing
   - gripper close timing
5. Consider training/eval bridge tests:
   - replay HDF5 initial state into online env
   - start evaluation from a recorded demo state if feasible
   - ask whether policy can continue a training demo state before requiring benchmark reset success
6. Remove or gate diagnostic probe file writes in `core/env_adapters/libero_adapter.py`.

## Latest Checkpoint Discovery On 2026-05-26

Command:

```bash
find /mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903 \
  -maxdepth 1 -type d -name 'checkpoint-*' | sort -V | tail -20
```

Latest discovered checkpoint:

```text
/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-98000
```

Files present:

```text
/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-98000/README.md
/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-98000/config.json
/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-98000/ema/model.safetensors
/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-98000/model.safetensors
/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-98000/optimizer.bin
/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-98000/pytorch_model.bin
/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-98000/random_states_0.pkl
/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-98000/scheduler.bin
```

Checkpoint modification time:

```text
2026-05-26 03:12:37 +0000 checkpoint-98000
```

## Latest Checkpoint Re-Test Result

Runtime config was updated to use:

```yaml
policy:
  rdt:
    pretrained_path: /mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-98000
    weight_variant: ema
```

Evaluation command:

```bash
CUDA_VISIBLE_DEVICES=0 /home/hynx/miniconda3/envs/vla-pilot/bin/python main.py policy.type=rdt
```

Output directory:

```text
outputs/libero/2026-05-26_03-24-48
```

Startup evidence:

```text
Loading RDT policy from /mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-98000
Using RDT weight file: /mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-98000/ema/model.safetensors
Using RDT config file: /mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-98000/config.json
post_init wired: adapter=LiberoAdapter, undo_libero_flip=True, sample_batch_size=20, action_chunk_horizon=8, fail_on_zero_language_embedding=True
RDT_IO_PROBE images=6 state_128_shape=(1, 128) text_shape=(1, 12, 4096) image_embeds=(1, 4374, 1152) ...
```

Final `results.txt`:

```text
Backend: libero
Success count: 0/10
Success rate: 0.00%
```

The run produced 10 saved episode videos, all marked as failures:

```text
outputs/libero/2026-05-26_03-24-48/episode_1/episode_1_fail_agentview.mp4
outputs/libero/2026-05-26_03-24-48/episode_2/episode_2_fail_agentview.mp4
outputs/libero/2026-05-26_03-24-48/episode_3/episode_3_fail_agentview.mp4
outputs/libero/2026-05-26_03-24-48/episode_4/episode_4_fail_agentview.mp4
outputs/libero/2026-05-26_03-24-48/episode_5/episode_5_fail_agentview.mp4
outputs/libero/2026-05-26_03-24-48/episode_6/episode_6_fail_agentview.mp4
outputs/libero/2026-05-26_03-24-48/episode_7/episode_7_fail_agentview.mp4
outputs/libero/2026-05-26_03-24-48/episode_8/episode_8_fail_agentview.mp4
outputs/libero/2026-05-26_03-24-48/episode_9/episode_9_fail_agentview.mp4
outputs/libero/2026-05-26_03-24-48/episode_10/episode_10_fail_agentview.mp4
```

Runtime observation:

1. The latest checkpoint loaded and executed through `main.py policy.type=rdt` without shape, device, checkpoint, or adapter crashes.
2. It did not improve the benchmark success count relative to checkpoint-60000.
3. Decoded action chunks frequently touched the `-1.0000` or `1.0000` bounds during rollout, which remains a suspicious behavioral signal even though the converter parity probe matched the fine-tuning transform.
4. The result does not satisfy the primary implementation success criterion of greater than `0/10`.

## Current Bottom Line After Latest-Checkpoint Re-Test

As of checkpoint-60000, checkpoint-72000, and checkpoint-98000 plus the tested ablations, the integration is mechanically operational but behaviorally unsuccessful:

```text
mechanical rollout: pass
video/output artifact generation: pass
shape/device/checkpoint load: pass
10-episode non-zero success criterion: fail, 0/10
```

Replacing checkpoint-60000 with the latest discovered checkpoint-98000 did not improve success rate. The most likely remaining causes are no longer simple runtime wiring failures; they are likely in the training/evaluation semantic bridge, checkpoint behavioral quality, or a subtler online-vs-HDF5 distribution mismatch.
