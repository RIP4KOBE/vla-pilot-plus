---
archived_on: 2026-06-04
source_worktree: .worktrees/feat/rdt-libero-dataset_finetune
source_branch: feat/rdt-libero-object-ckpt
source_commit: 1be4afbf17ea
source_path: .worktrees/feat/rdt-libero-dataset_finetune/third_party/rdt/agent/overview.md
summary: RDT Project Overview
duplicate_sources: []
---

# RDT Project Overview

This repository is the PyTorch implementation of RDT-1B, a Vision-Language-Action diffusion transformer for robot imitation learning. The model consumes a language instruction, RGB image history from multiple cameras, and the current robot state, then predicts a chunk of future robot actions.

Core task shape:

```text
language instruction
+ image history: 2 timesteps x 3 cameras
+ current proprio/state vector
-> predict 64 future actions
```

The default configuration lives in `configs/base.yaml`:

```text
img_history_size = 2
num_cameras = 3
action_chunk_size = 64
state_dim = 128
model hidden_size = 2048
model depth = 28
model num_heads = 32
noise scheduler = DDPM train, DPM-Solver sample
```

## Main Directories

`main.py`

Training entrypoint. It parses command-line arguments and calls `train.train(args, logger)`.

`train/`

Training, dataset wrapper, collator, sampling/evaluation utilities.

- `train/train.py`: builds encoders, model, optimizer, datasets, dataloaders, and runs the training loop.
- `train/dataset.py`: wraps either producer-consumer buffer data or HDF5 data into RDT-ready samples and batches.
- `train/sample.py`: runs diffusion sampling on validation batches and logs sample MSE/L2 metrics.

`models/`

RDT model code.

- `models/rdt_runner.py`: top-level train/inference wrapper around the diffusion transformer. Handles condition adapters, diffusion schedulers, training loss, and action sampling.
- `models/rdt/model.py`: core RDT transformer. It embeds timestep/control frequency, attends over language/image conditions, and outputs action chunks.
- `models/multimodal_encoder/t5_encoder.py`: T5 text encoder wrapper.
- `models/multimodal_encoder/siglip_encoder.py`: SigLIP vision encoder wrapper.

`data/`

Dataset loaders and preprocessing.

- `data/hdf5_vla_dataset.py`: fine-tuning HDF5 adapter. This is the main file to modify when adapting LIBERO or another robot dataset.
- `data/vla_dataset.py` and `data/producer.py`: pretraining-style producer/consumer pipeline for TFDS/OpenX-style datasets.
- `data/compute_dataset_stat_hdf5.py`: dataset statistics helper for HDF5 fine-tuning data.

`configs/`

RDT-wide configuration and dataset metadata.

- `configs/base.yaml`: shared model/data constants.
- `configs/state_vec.py`: maps robot physical quantities into the 128-dimensional unified state/action vector.
- `configs/finetune_datasets.json`: fine-tuning dataset names.
- `configs/finetune_sample_weights.json`: fine-tuning dataset sampling weights.
- `configs/dataset_control_freq.json`: control frequency per dataset.
- `configs/dataset_stat.json`: per-dataset state statistics used by `VLAConsumerDataset`.

## Training Data Flow

Fine-tuning with `--load_from_hdf5` follows this path:

```text
main.py
-> train.train()
-> VLAConsumerDataset(... use_hdf5=True ...)
-> HDF5VLADataset.get_item()
-> HDF5VLADataset.parse_hdf5_file()
-> DataCollatorForVLAConsumerDataset
-> train loop
```

`HDF5VLADataset` samples one episode and one timestep, then returns:

```text
meta:
  dataset_name
  instruction
  step_id
state: (1, 128)
actions: (64, 128)
state_indicator: (128,)
state_mean/std/norm: (128,)
cam_high: (2, H, W, 3)
cam_right_wrist: (2, H, W, 3)
cam_left_wrist: (2, H, W, 3)
camera masks: (2,)
```

`VLAConsumerDataset` then:

- applies optional state noise;
- optionally masks state/action-validity conditions;
- pads invalid/missing images with SigLIP mean background;
- applies image augmentation when `--image_aug` is set;
- converts images from HWC uint8 arrays to SigLIP-preprocessed CHW tensors;
- tokenizes language with T5 tokenizer, unless `--precomp_lang_embed` is enabled.

`DataCollatorForVLAConsumerDataset` stacks samples into a batch:

```text
images: (B, 6, C, H, W)
states: (B, 1, 128)
actions: (B, 64, 128)
state_elem_mask: (B, 128)
state_norm: (B, 128)
input_ids: (B, L) or lang_embeds: (B, L, 4096)
lang_attn_mask: (B, L)
ctrl_freqs: (B,)
```

The image order is:

```text
for each history timestep:
  cam_high
  cam_right_wrist
  cam_left_wrist
```

## Model Flow

The training loop in `train/train.py` sends:

```text
batch["images"] -> SigLIP vision encoder -> image tokens
batch["input_ids"] -> T5 encoder -> language tokens
batch["states"][:, -1:, :] -> current state condition
batch["actions"] -> diffusion clean target
batch["state_elem_mask"] -> validity condition appended to state/action tokens
```

`RDTRunner.compute_loss()`:

1. Samples Gaussian noise with the same shape as actions: `(B, 64, 128)`.
2. Samples random diffusion timesteps.
3. Adds noise to ground-truth actions with the DDPM scheduler.
4. Concatenates current state token and noisy action sequence.
5. Concatenates the action/state validity mask along the feature dimension.
6. Projects language, image, and state/action tokens into the RDT hidden size.
7. Calls `RDT.forward()`.
8. Computes MSE loss between predicted action samples and ground-truth actions.

Because `configs/base.yaml` sets `prediction_type: sample`, the model is trained to predict denoised actions directly, not noise.

## Unified State/Action Vector

RDT uses a fixed 128-dimensional vector for robot state and action. Important ranges from `configs/state_vec.py`:

```text
0-14     right arm joints + gripper
15-29    right joint velocities
30-44    right EEF pose / velocity
50-64    left arm joints + gripper
65-79    left joint velocities
80-94    left EEF pose / velocity
100-102  base velocity
103-127  reserved
```

For a single-arm robot, the README recommends filling the right-arm portion of the unified vector.

## Current Adaptation Hotspots

For LIBERO/object fine-tuning, the most important files are:

1. `data/hdf5_vla_dataset.py`
   - map LIBERO HDF5 fields to RDT sample keys;
   - map LIBERO state/action to 128-dimensional state/action vectors;
   - build image history and camera masks;
   - handle action chunk padding near episode ends.

2. `configs/finetune_datasets.json`
   - register the LIBERO dataset name returned in `meta["dataset_name"]`.

3. `configs/dataset_control_freq.json`
   - add the LIBERO control frequency.

4. `configs/dataset_stat.json`
   - add state statistics for the LIBERO dataset.

5. `models/rdt_runner.py`
   - inspect or modify loss behavior. Current training loss is unmasked MSE over all 128 dimensions.

## Key Risk

`state_elem_mask` is passed into the model as a condition, but the training loss in `RDTRunner.compute_loss()` currently uses:

```python
loss = F.mse_loss(pred, target)
```

This does not mask invalid action dimensions. If LIBERO only occupies a small subset of the 128-dimensional vector, the many inactive zero dimensions can dilute the useful action loss. This is one of the first places to audit if fine-tuning looks unstable or underfits active action dimensions.
