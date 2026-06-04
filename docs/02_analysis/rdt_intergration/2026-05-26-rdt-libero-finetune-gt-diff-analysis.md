---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: feat/rdt-libero-gt-rollout-reintegration
source_commit: 360a6d052861
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/docs/docs/02_analysis/rdt_intergration/2026-05-26-rdt-libero-finetune-gt-diff-analysis.md
summary: RDT-LIBERO Fine-Tuning GT Difference Analysis
duplicate_sources:
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/docs/02_analysis/rdt_intergration/2026-05-26-rdt-libero-finetune-gt-diff-analysis.md
---

# RDT-LIBERO Fine-Tuning GT Difference Analysis

Date: 2026-05-26

Worktree:

```text
.worktrees/feat/rdt-libero-object-ckpt
```

Ground-truth reference:

```text
third_party/Libero_RDT
https://github.com/tj-chen-1209/Libero_RDT
commit 84eaafe7df60e922be10bf3b487ad573f314feb8
```

Compared implementation:

```text
third_party/rdt
```

Scope note:

This analysis intentionally compares only fine-tuning code and training-launch evidence. Runtime / rollout / evaluation integration under `core/` was not analyzed here.

No source code was modified. The only changes made for this task were cloning the GT repo at `third_party/Libero_RDT` and writing this analysis file.

## 1. Executive Summary

The most suspicious fine-tuning difference is not a minor hyperparameter. It is a semantic change in the supervised state/action target.

GT trains LIBERO with:

- proprio input from `obs/joint_states` plus both `obs/gripper_states`
- gripper state min-max normalized using fixed raw joint limits
- raw HDF5 `actions` placed into `eef_vel_*`, `eef_angular_vel_*`, and `gripper_open` unified-vector indices
- no controller-config denormalization / scaling of action targets
- a LIBERO90-derived base checkpoint in the main full-finetune script
- precomputed T5 language embeddings in the main full-finetune script
- skipped initial still frames before sampling

My current `third_party/rdt` LIBERO fine-tuning path trains with:

- EEF position + 6D EEF rotation + one normalized gripper-open scalar as state
- controller-scaled OSC action converted to position delta + 6D rotation + mapped gripper scalar
- action targets written to `eef_pos/eef_angle/right_gripper_open` indices, not GT's `eef_vel/eef_angular_vel/gripper_open` indices
- public RDT-1B base checkpoint in the observed full training run
- mixed `libero_10,libero_object,libero_spatial,libero_goal` training, omitting `libero_90`
- online T5 tokenization in the observed full training run
- no initial still-frame skip

Under the user's rule, GT is treated as correct. Therefore, the current checkpoint should be considered trained under different semantics from the GT LIBERO RDT recipe. This could plausibly produce low offline loss while still yielding 0/10 online rollout success, because the model may have learned a different action/state contract than the one GT uses for successful LIBERO fine-tuning.

## 2. GT Implementation Summary

Primary GT files inspected:

```text
third_party/Libero_RDT/RDT_libero_finetune/finetune.sh
third_party/Libero_RDT/RDT_libero_finetune/finetune_sft.sh
third_party/Libero_RDT/RDT_libero_finetune/main.py
third_party/Libero_RDT/RDT_libero_finetune/main_sft.py
third_party/Libero_RDT/RDT_libero_finetune/train/train.py
third_party/Libero_RDT/RDT_libero_finetune/train/train_sft.py
third_party/Libero_RDT/RDT_libero_finetune/train/dataset.py
third_party/Libero_RDT/RDT_libero_finetune/train/dataset_sft.py
third_party/Libero_RDT/RDT_libero_finetune/data/hdf5_libero_dataset.py
third_party/Libero_RDT/RDT_libero_finetune/data/hdf5_libero_sft_dataset.py
third_party/Libero_RDT/RDT_libero_finetune/scripts/encode_lang_libero.py
third_party/Libero_RDT/RDT_libero_finetune/configs/base.yaml
third_party/Libero_RDT/RDT_libero_finetune/configs/finetune_datasets.json
third_party/Libero_RDT/RDT_libero_finetune/configs/dataset_stat.json
third_party/Libero_RDT/RDT_libero_finetune/configs/dataset_control_freq.json
third_party/Libero_RDT/RDT_libero_finetune/configs/state_vec.py
```

### GT Full Fine-Tune Route

The main GT full fine-tune command is in `finetune.sh`.

Key behavior:

- target suite is set by shell variable, default `libero_spatial`
- base model is `./checkpoints/rdt-finetune-1b-20251119_122234/checkpoint-65000`, described as `libero90-ckpt65k`
- uses `main.py`
- uses `--load_from_hdf5`
- uses `--image_aug`
- uses `--state_noise_snr=40`
- uses `--precomp_lang_embed`
- batch size `48`, sample batch size `32`, max steps `200000`, LR `1e-4`, BF16

Evidence:

```text
third_party/Libero_RDT/RDT_libero_finetune/finetune.sh:19
third_party/Libero_RDT/RDT_libero_finetune/finetune.sh:25-26
third_party/Libero_RDT/RDT_libero_finetune/finetune.sh:136-160
```

### GT Dataset Semantics

GT reads:

- `obs/joint_states`
- `obs/gripper_states`
- `obs/agentview_rgb`
- `obs/eye_in_hand_rgb`
- `actions`

GT builds `qpos = concat(joint_states, gripper_states)`.

Evidence:

```text
third_party/Libero_RDT/RDT_libero_finetune/data/hdf5_libero_dataset.py:185-205
```

GT skips initial still frames by finding first `qpos` whose delta from the initial `qpos` exceeds `1e-2`, then samples from `first_idx - 1` onward.

Evidence:

```text
third_party/Libero_RDT/RDT_libero_finetune/data/hdf5_libero_dataset.py:212-223
```

GT uses `state = qpos[step_id]` and `actions = actions_data[step_id:step_id+CHUNK_SIZE]`, so observation/action timing is same-index `t`.

Evidence:

```text
third_party/Libero_RDT/RDT_libero_finetune/data/hdf5_libero_dataset.py:292-300
```

GT normalizes the last two gripper state dimensions with fixed scalar limits:

```text
qpos_min = -0.04245
qpos_max = 0.05185
```

Evidence:

```text
third_party/Libero_RDT/RDT_libero_finetune/data/hdf5_libero_dataset.py:286-290
```

GT maps state to unified vector indices:

- `arm_joint_0_pos` ... `arm_joint_6_pos`
- `gripper_joint_0_pos`
- `gripper_joint_1_pos`

Evidence:

```text
third_party/Libero_RDT/RDT_libero_finetune/data/hdf5_libero_dataset.py:309-325
```

GT maps action to unified vector indices:

- `eef_vel_x`
- `eef_vel_y`
- `eef_vel_z`
- `eef_angular_vel_roll`
- `eef_angular_vel_pitch`
- `eef_angular_vel_yaw`
- `gripper_open`

Evidence:

```text
third_party/Libero_RDT/RDT_libero_finetune/data/hdf5_libero_dataset.py:327-342
```

GT image semantics:

- external camera: `agentview_rgb`
- right wrist camera: `eye_in_hand_rgb`
- left wrist camera unavailable, zero-shaped
- history order is oldest to newest
- missing history padded with first available image
- image valid mask is relative to `first_idx - 1`, not raw episode start

Evidence:

```text
third_party/Libero_RDT/RDT_libero_finetune/data/hdf5_libero_dataset.py:344-383
```

GT language semantics:

- extracts instruction from filename when no precomputed embedding exists
- if `outs/libero_embeddings/<suite>/<task>.pt` exists, uses that path as instruction
- `finetune.sh` passes `--precomp_lang_embed`
- `train/dataset.py` loads the tensor via `torch.load(content["instruction"])`

Evidence:

```text
third_party/Libero_RDT/RDT_libero_finetune/data/hdf5_libero_dataset.py:225-275
third_party/Libero_RDT/RDT_libero_finetune/finetune.sh:159
third_party/Libero_RDT/RDT_libero_finetune/train/dataset.py:412-425
third_party/Libero_RDT/RDT_libero_finetune/scripts/encode_lang_libero.py:22-128
```

### GT Training Objective And Wiring

GT `configs/base.yaml` matches the expected RDT-1B LIBERO shape:

- image history `2`
- action chunk `64`
- cameras `3`
- state/action dim `128`
- noise scheduler: DDPM train, DPM-Solver sample, `prediction_type: sample`, 1000 train timesteps, 5 inference timesteps
- EMA config present

Evidence:

```text
third_party/Libero_RDT/RDT_libero_finetune/configs/base.yaml
```

GT training loop:

- freezes T5/SigLIP under `torch.no_grad()`
- uses the last state token as the current state
- passes `action_gt=actions`
- passes `action_mask=state_elem_mask`
- uses `rdt(...)` to compute diffusion MSE loss
- updates EMA each optimization step

Evidence:

```text
third_party/Libero_RDT/RDT_libero_finetune/train/train.py:500-554
third_party/Libero_RDT/RDT_libero_finetune/models/rdt_runner.py:243-326
```

Important nuance:

`RDTRunner.compute_loss()` computes plain `F.mse_loss(pred, target)` and does not multiply the MSE by `action_mask`. The mask is concatenated into state/action tokens as a condition and is applied during conditional sampling. Thus, differences in target vector indices and differences in the mask vector are both meaningful training-distribution differences.

Evidence:

```text
third_party/Libero_RDT/RDT_libero_finetune/models/rdt_runner.py:293-324
```

## 3. My Implementation Summary

Primary files inspected:

```text
third_party/rdt/finetune_libero.sh
third_party/rdt/main.py
third_party/rdt/train/train.py
third_party/rdt/train/dataset.py
third_party/rdt/data/hdf5_vla_dataset.py
third_party/rdt/data/libero_vla_dataset.py
third_party/rdt/configs/base.yaml
third_party/rdt/configs/finetune_datasets.json
third_party/rdt/configs/finetune_sample_weights.json
third_party/rdt/configs/dataset_stat.json
third_party/rdt/configs/dataset_control_freq.json
third_party/rdt/configs/state_vec.py
```

Observed formal training launch:

```text
/mnt/data/rdt_logs/rdt-libero-full-formal-20260523-140903/run_full_training.sh
/mnt/data/rdt_logs/rdt-libero-full-formal-20260523-140903/train.log
```

The active HDF5 backend switch is:

```text
third_party/rdt/data/hdf5_vla_dataset.py:319-320
```

When `RDT_HDF5_BACKEND=libero`, training uses:

```text
third_party/rdt/data/libero_vla_dataset.py
```

My implementation builds a dynamic LIBERO index across suites from:

```text
RDT_LIBERO_DATA_ROOT
RDT_LIBERO_SUITES
```

Evidence:

```text
third_party/rdt/data/libero_vla_dataset.py:14-66
third_party/rdt/data/libero_vla_dataset.py:143-205
```

My current formal run used:

```text
RDT_LIBERO_SUITES=libero_10,libero_object,libero_spatial,libero_goal
pretrained_model_name_or_path=/mnt/data/hf_cache/hub/robotics-diffusion-transformer--rdt-1b
train_batch_size=32
sample_batch_size=64
max_train_steps=200000
image_aug=true
mixed_precision=bf16
state_noise_snr=40
report_to=tensorboard
```

Evidence:

```text
/mnt/data/rdt_logs/rdt-libero-full-formal-20260523-140903/run_full_training.sh:27-29
/mnt/data/rdt_logs/rdt-libero-full-formal-20260523-140903/run_full_training.sh:45-68
```

My state semantics:

- state active dims: `eef_pos_x/y/z`, `eef_angle_0..5`, `right_gripper_open`
- EEF orientation is converted from rotvec to 6D orthogonal representation
- gripper state is converted from two finger joint values to one normalized opening scalar

Evidence:

```text
third_party/rdt/data/libero_vla_dataset.py:16-27
third_party/rdt/data/libero_vla_dataset.py:69-110
third_party/rdt/data/libero_vla_dataset.py:218-233
```

My action semantics:

- raw actions are read from `demo["actions"]`
- action first six dimensions are controller-scaled through `controller_config`
- position action fills indices `30:33`
- rotation action is rotvec-to-6D and fills indices `33:39`
- gripper action is mapped from LIBERO raw convention to `[0,1]` and fills index `10`

Evidence:

```text
third_party/rdt/data/libero_vla_dataset.py:102-140
third_party/rdt/data/libero_vla_dataset.py:235-243
```

My image semantics:

- camera names match GT: `agentview_rgb`, `eye_in_hand_rgb`, left wrist missing
- history order is oldest to newest
- missing history padded with first available image
- mask is relative to raw episode start, not GT's `first_idx - 1`

Evidence:

```text
third_party/rdt/data/libero_vla_dataset.py:245-254
third_party/rdt/data/libero_vla_dataset.py:289-315
```

My language semantics:

- dataset uses `problem_info["language_instruction"]` from the HDF5 `data` group
- observed formal run did not pass `--precomp_lang_embed`, so training used online T5 tokenization

Evidence:

```text
third_party/rdt/data/libero_vla_dataset.py:176-199
third_party/rdt/data/libero_vla_dataset.py:297-303
third_party/rdt/train/dataset.py:353-369
/mnt/data/rdt_logs/rdt-libero-full-formal-20260523-140903/run_full_training.sh:47-68
```

## 4. Difference Table

| Area | GT behavior | My behavior | Evidence/file paths | Risk level | Why it may cause 0/10 |
|---|---|---|---|---|---|
| State representation | Uses joint positions `arm_joint_0..6` plus two gripper joint positions, with fixed min-max gripper normalization. | Uses EEF position, EEF 6D orientation, and one normalized gripper-open scalar. | GT `data/hdf5_libero_dataset.py:286-325`; My `data/libero_vla_dataset.py:16-27,218-233`; stats probe showed GT nonzero state dims `[0..6,10,11]`, My `[10,30..38]`. | High | The model conditions on a different proprio vector than GT. If GT checkpoint success depends on joint-state conditioning, an EEF-state checkpoint is a different policy class and can fail despite low training loss. |
| Action target indices | Writes raw HDF5 action to `eef_vel_x/y/z`, `eef_angular_vel_roll/pitch/yaw`, and `gripper_open` indices. | Writes controller-scaled action to `eef_pos_x/y/z`, `eef_angle_0..5`, and `right_gripper_open`. | GT `data/hdf5_libero_dataset.py:292-342`; My `data/libero_vla_dataset.py:235-243`. | High | This is the strongest fine-tuning root-cause candidate. The supervised target vector is fundamentally different from GT, so the learned checkpoint can output the wrong dimensions/representation for successful LIBERO control. |
| Action magnitude / scaling | Uses raw HDF5 `actions` directly. No controller-config scaling. | Converts raw OSC input through `_controller_scale()` using env controller `input_min/max` and `output_min/max`. | GT `data/hdf5_libero_dataset.py:292-300,327-342`; My `data/libero_vla_dataset.py:113-140,235-243`. | High | Even if dimensions were aligned, the target units differ. GT treats actions as raw normalized OSC commands; my checkpoint learns controller-output-scaled deltas. This can explain action saturation and bad rollout behavior. |
| Rotation target | Uses raw action dims 3:6 as angular velocity / roll-pitch-yaw velocity slots. | Converts scaled rotvec action dims 3:6 into 6D rotation representation. | GT `data/hdf5_libero_dataset.py:327-342`; My `data/libero_vla_dataset.py:69-99,239-242`. | High | Rotation representation and dimensionality differ. A 3D angular command and a 6D orientation representation are not interchangeable. |
| Gripper action convention | Uses raw `actions[:,6]` directly in `gripper_open` index. | Maps raw gripper via `(1 - raw) / 2`, clipped to `[0,1]`. | GT `data/hdf5_libero_dataset.py:292-300,327-342`; My `data/libero_vla_dataset.py:102-105,242`. | High | If GT's successful policy relies on raw LIBERO gripper command convention, this can invert/shift gripper behavior. Gripper mistakes alone can produce 0/10 on pick-place tasks. |
| Gripper state convention | Keeps both gripper joint states after fixed min-max normalization. | Collapses two gripper joint states into one opening width scalar. | GT `data/hdf5_libero_dataset.py:286-290,313-319`; My `data/libero_vla_dataset.py:107-110,227-232`. | Medium / High | The proprio state distribution is different and loses asymmetric finger information. This also shifts active state dims. |
| Initial still-frame handling | Skips initial still frames by sampling only from `first_idx - 1` onward. Image masks are relative to this cap point. | Samples from raw `0..num_steps-1`; image mask is relative to raw episode start. | GT `data/hdf5_libero_dataset.py:212-223,363-383`; My `data/libero_vla_dataset.py:245-254,286-308`. | Medium | Training on many initial stationary samples can bias early actions and history masks. Probably not enough alone for 0/10, but it compounds action/state semantic mismatch. |
| Observation-action timing | Uses same-index `state[t]` and `action[t:t+horizon]`. | Also uses same-index state/action. | GT `data/hdf5_libero_dataset.py:292-300`; My `data/libero_vla_dataset.py:263-308`. | Low | No direct contradiction found. Remaining timing ambiguity is mostly about static-frame skip, not t vs t+1. |
| Camera names/order | `cam_high=agentview_rgb`, `cam_right_wrist=eye_in_hand_rgb`, `cam_left_wrist` unavailable. Consumer order is high, right wrist, left wrist. | Same camera names and order. | GT `data/hdf5_libero_dataset.py:344-383`, `train/dataset.py` image_metas order; My `data/libero_vla_dataset.py:289-315`, `train/dataset.py` image_metas order. | Low | Camera identity/order probably does not explain 0/10. |
| Image preprocessing | PIL conversion, optional pad-to-square, SigLIP processor normalization, optional image augmentation. | Same consumer preprocessing. | GT `train/dataset.py:380-410`; My `train/dataset.py:300-351`. | Low | No major image preprocessing difference found in training consumer. |
| Language source | Filename-derived instruction or precomputed embedding path under `outs/libero_embeddings/<suite>/<task>.pt`. Main GT full script passes `--precomp_lang_embed`. | HDF5 `problem_info["language_instruction"]`; observed formal run did not pass `--precomp_lang_embed`, so T5 ran online during training. | GT `data/hdf5_libero_dataset.py:225-275`, `finetune.sh:159`, `scripts/encode_lang_libero.py:22-128`; My `data/libero_vla_dataset.py:176-199,297-303`, run script `47-68`. | Medium | If instruction strings differ by scene prefix removal, punctuation, or embedding length, language conditioning may drift. Less likely than action semantics, but important because runtime uses task language. |
| Dataset selection | GT full script default is single target suite `libero_spatial` and assumes a LIBERO90 base. GT config includes `libero_90`. | Observed run mixed `libero_10,libero_object,libero_spatial,libero_goal` and omitted `libero_90`. My config also omits `libero_90`. | GT `finetune.sh:19,25-26`, `configs/finetune_datasets.json`; My run script `27-29`, My `configs/finetune_datasets.json`. | Medium / High | GT's recipe appears staged: LIBERO90 base, then suite-specific fine-tune. My run trains multi-suite from public base without LIBERO90. This can produce weaker task-specific behavior. |
| Base checkpoint | GT full script starts from `libero90-ckpt65k`. | Observed formal run starts from public `/mnt/data/hf_cache/hub/robotics-diffusion-transformer--rdt-1b`. | GT `finetune.sh:24-26,136-139`; My run script `47-50`; My `finetune_libero.sh:30,53-56`. | High | If GT performance depends on a LIBERO90-adapted base, training from generic RDT-1B can leave too large a domain gap, especially with changed state/action semantics. |
| Checkpoint loading implementation | GT manually reads checkpoint `config.json` and passes architectural kwargs to `RDTRunner.from_pretrained()`. | My `train.py` calls `RDTRunner.from_pretrained(path)` directly. | GT `train/train.py:150-180`; My `train/train.py:144-150`. | Medium | If `RDTRunner.from_pretrained()` defaults do not exactly preserve checkpoint architecture, this can create subtle config mismatch. Current checkpoints load, so this is less suspicious than target semantics. |
| LoRA | GT has LoRA-capable paths but full script uses full-parameter fine-tuning. | My compared path has no LoRA route in `main.py`; actual run is full-parameter. | GT `main.py` LoRA args and `train.py:182-208`; My `main.py` diff lacks LoRA args. | Low | Not likely for this full-parameter run. |
| Hyperparameters | GT full: batch 48, sample 32, `--precomp_lang_embed`, W&B, base `libero90-ckpt65k`. | Observed formal run: batch 32, sample 64, no precomputed language, TensorBoard, public base. | GT `finetune.sh:136-160`; My run script `45-68`. | Medium | Batch/reporting alone unlikely, but base model and language mode are meaningful. |
| Dataset statistics | GT `dataset_stat.json` has nonzero state dims matching joint/gripper state. | My `dataset_stat.json` has nonzero state dims matching EEF/6D/gripper state. | Probe over both JSON files; GT has LIBERO nonzero state dims `[0,1,2,3,4,5,6,10,11]`; My has `[10,30,31,32,33,34,35,36,37,38]`. | High | Dataset stats confirm the semantic rewrite is systemic, not isolated to one code branch. These stats affect state noise and state masking. |
| `finetune_libero.sh` defaults | GT script is a formal training launcher. | My `finetune_libero.sh` defaults to a 10-step smoke run unless env overrides are supplied. | GT `finetune.sh:82-160`; My `finetune_libero.sh:39-73`; observed run used external full script. | Low for current checkpoint | Not the cause for the observed formal checkpoint, because `/mnt/data/.../run_full_training.sh` supplied full settings. Still a reproducibility footgun. |

## 5. Ranked Hypotheses For 0/10

### Hypothesis 1: The checkpoint was trained on the wrong state/action contract relative to GT

Risk: High

GT learns:

```text
state: joint_states + two gripper_states -> indices [0..6, 10, 11]
action: raw HDF5 actions -> indices [39..44, 10]
```

My current fine-tune learns:

```text
state: eef_pos + eef_rot6d + gripper_open -> indices [30..38, 10]
action: controller-scaled pos/rot6d/gripper -> indices [30..38, 10]
```

This is a direct target-distribution mismatch. It can produce low training/sample MSE in my code while producing a checkpoint that is not semantically equivalent to GT's LIBERO RDT model.

### Hypothesis 2: Training started from the wrong base model

Risk: High

GT full fine-tune starts from a LIBERO90 checkpoint:

```text
BASE_MODEL_PATH="./checkpoints/rdt-finetune-1b-20251119_122234/checkpoint-65000"
base_model_name="libero90-ckpt65k"
```

My observed formal run starts from:

```text
/mnt/data/hf_cache/hub/robotics-diffusion-transformer--rdt-1b
```

If GT's successful checkpoints rely on the LIBERO90 base to bridge domain/semantic gaps, the current run is not reproducing the GT recipe.

### Hypothesis 3: The current multi-suite training mix does not match GT's staged/suite-specific recipe

Risk: Medium / High

GT full script is suite-specific, with `dataset_name="libero_spatial"` by default and a LIBERO90-derived base. My observed run mixes:

```text
libero_10,libero_object,libero_spatial,libero_goal
```

and excludes `libero_90`.

This can dilute task-specific behavior and remove the broad LIBERO90 prior assumed by GT.

### Hypothesis 4: Language conditioning differs from GT

Risk: Medium

GT full script uses precomputed T5 embeddings derived from filename-extracted task instructions. My observed run uses online tokenization of HDF5 `problem_info["language_instruction"]`.

This may be benign if strings match exactly, but it is a real difference. It should be verified with exact token/embedding comparisons per task.

### Hypothesis 5: My training includes initial still frames that GT skips

Risk: Medium

GT computes `first_idx` from qpos movement and samples from `first_idx - 1`. My code samples from the raw episode start. This can increase stationary prefixes and change image-history masks. It is probably not sufficient alone to explain 0/10, but it can worsen early rollout behavior.

### Hypothesis 6: Checkpoint config loading differs

Risk: Medium / Low

GT explicitly reads checkpoint `config.json` and passes architecture fields into `RDTRunner.from_pretrained()`. My code relies on plain `RDTRunner.from_pretrained(path)`.

Because current checkpoints load and shape-check, this is less suspicious than data semantics, but it is worth verifying exact loaded `img_pos_embed_config`, `img_cond_len`, `pred_horizon`, and token dimensions against GT.

## 6. Top 5 Most Suspicious Fine-Tuning Differences

1. **Action target semantics changed from GT raw HDF5 action in velocity indices to controller-scaled EEF pose/6D rotation indices.**
2. **State conditioning changed from GT joint/gripper state to EEF pose/6D rotation plus scalar gripper-open.**
3. **Observed formal training started from public RDT-1B instead of GT's LIBERO90 checkpoint-65000.**
4. **Observed formal training omitted `libero_90` and mixed four suites instead of following GT's LIBERO90-base then suite-specific fine-tune pattern.**
5. **Observed formal training did not use GT's precomputed language embedding path.**

## 7. Concrete Next Verification Commands Or Probes

These are proposed read-only probes. They should not modify source code.

### Probe 1: Compare active dimensions from config stats

Purpose: confirm that GT and my dataset statistics encode different state contracts.

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-object-ckpt
/home/hynx/miniconda3/envs/vla-pilot/bin/python - <<'PY'
import json
from pathlib import Path

for label, path in [
    ("GT", "third_party/Libero_RDT/RDT_libero_finetune/configs/dataset_stat.json"),
    ("MY", "third_party/rdt/configs/dataset_stat.json"),
]:
    data = json.loads(Path(path).read_text())
    print(label)
    for suite in ["libero_90", "libero_10", "libero_object", "libero_spatial", "libero_goal"]:
        if suite not in data:
            print(" ", suite, "MISSING")
            continue
        std = data[suite]["state_std"]
        active = [i for i, x in enumerate(std) if abs(x) > 1e-8]
        print(" ", suite, active)
PY
```

Expected if current analysis is correct:

```text
GT LIBERO active state dims: [0,1,2,3,4,5,6,10,11]
MY LIBERO active state dims: [10,30,31,32,33,34,35,36,37,38]
```

### Probe 2: Same HDF5 sample, GT-style target vs my target

Purpose: quantify one real sample's target-vector difference without training.

Suggested output:

- step id
- nonzero state dims and values
- nonzero action dims and values
- action magnitude ranges
- gripper value before/after mapping

Use one file from:

```text
/mnt/data/hf_cache/hub/libero_spatial/*.hdf5
```

The probe should implement only the two transformations already present in:

```text
GT: third_party/Libero_RDT/RDT_libero_finetune/data/hdf5_libero_dataset.py
MY: third_party/rdt/data/libero_vla_dataset.py
```

Do not write outputs except terminal logs.

### Probe 3: Verify language string and embedding equivalence

Purpose: determine whether GT filename-derived instruction equals my HDF5 `problem_info["language_instruction"]`.

Suggested checks:

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-object-ckpt
/home/hynx/miniconda3/envs/vla-pilot/bin/python - <<'PY'
import glob, json, os, h5py

def gt_extract(path):
    task_name = os.path.basename(path).replace("_demo.hdf5", "")
    if task_name and task_name[0].isupper():
        scene_pos = task_name.find("SCENE")
        if scene_pos != -1:
            language_part = task_name[scene_pos + (8 if "SCENE10" in task_name else 7):]
            return language_part.replace("_", " ").strip()
    return task_name.replace("_", " ").strip()

for path in sorted(glob.glob("/mnt/data/hf_cache/hub/libero_10/*.hdf5"))[:10]:
    with h5py.File(path, "r") as f:
        attr = f["data"].attrs["problem_info"]
        if isinstance(attr, bytes):
            attr = attr.decode("utf-8")
        my_instr = json.loads(attr)["language_instruction"]
    print(os.path.basename(path))
    print("  GT:", gt_extract(path))
    print("  MY:", my_instr)
    print("  same:", gt_extract(path) == my_instr)
PY
```

### Probe 4: Check for GT precomputed language embeddings

Purpose: verify whether the GT-required embedding files exist for every intended suite/task.

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-object-ckpt/third_party/Libero_RDT/RDT_libero_finetune
find outs/libero_embeddings -type f -name '*.pt' | sort | wc -l
find outs/libero_embeddings -maxdepth 2 -type f -name 'task_instruction_mapping.txt' -print
```

If embeddings are absent, reproducing GT `finetune.sh` with `--precomp_lang_embed` would fail unless embeddings are generated first.

### Probe 5: Check base checkpoint lineage

Purpose: determine whether the currently trained checkpoint is from public RDT-1B or a LIBERO90 checkpoint.

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-object-ckpt
cat /mnt/data/rdt_logs/rdt-libero-full-formal-20260523-140903/run_full_training.sh
cat /mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-98000/README.md
cat /mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-98000/config.json
```

The important field is the original `pretrained_model_name_or_path` and whether it matches GT's `libero90-ckpt65k`.

### Probe 6: Offline low-loss sanity by semantic family

Purpose: determine whether low sample MSE is only low under my transform, not GT transform.

Run two offline prediction probes on the same HDF5 samples:

1. Use my current transform and measure predicted-vs-target error at my active dims.
2. Use GT transform and measure predicted-vs-target error at GT active dims.

Expected if the current root cause is correct:

- my-transform error may be low
- GT-transform error should be high or produce active-dim mismatch

### Probe 7: Confirm action saturation source

Purpose: determine if saturation originates in the checkpoint's learned target distribution.

For a batch of validation HDF5 samples, log:

- predicted action active dims before any runtime conversion
- min/max per active dimension
- percentage of values near `-1` or `1`
- compare to raw HDF5 action distribution under GT action dims
- compare to my scaled action distribution under my action dims

If predictions match my scaled distribution but not GT raw action distribution, that supports Hypothesis 1.

## 8. Current Best Root-Cause Assessment

The most likely fine-tuning-side root cause for 0/10 is:

```text
The checkpoint was trained with a non-GT LIBERO state/action schema.
```

Specifically, my fine-tuning implementation converted LIBERO into an EEF pose / 6D rotation / controller-scaled action problem. GT fine-tuning treats LIBERO as joint-state conditioning plus raw OSC action prediction in velocity-style unified-vector slots.

This difference is large enough to explain:

- low offline training/sample MSE
- mechanically valid RDT checkpoint loading
- correct tensor shapes
- successful rollout artifact generation
- but 0/10 benchmark success

The second most likely root cause is:

```text
The observed formal run started from public RDT-1B instead of GT's LIBERO90 checkpoint.
```

That likely compounds the state/action semantic mismatch and removes GT's assumed LIBERO prior.

## 9. What Was Not Changed

No source code was modified.

Not modified:

```text
third_party/rdt/**
third_party/libero/**
core/**
configs/**
runtime/evaluation integration code
checkpoint files
```

Created:

```text
third_party/Libero_RDT
docs/docs/02_analysis/rdt_intergration/2026-05-26-rdt-libero-finetune-gt-diff-analysis.md
```
