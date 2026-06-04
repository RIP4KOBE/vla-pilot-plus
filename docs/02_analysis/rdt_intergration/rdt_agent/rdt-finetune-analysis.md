---
archived_on: 2026-06-04
source_worktree: .worktrees/feat/rdt-libero-dataset_finetune
source_branch: feat/rdt-libero-object-ckpt
source_commit: 1be4afbf17ea
source_path: .worktrees/feat/rdt-libero-dataset_finetune/third_party/rdt/agent/finetune_analysis.md
summary: RDT Fine-Tuning Analysis
duplicate_sources: []
---

# RDT Fine-Tuning Analysis

This document traces what happens when running:

```bash
source finetune.sh
```

from the RDT project root.

## 1. Executive Summary

The actual fine-tuning entrypoint is `finetune.sh`, which launches:

```bash
deepspeed --hostfile=hostfile.txt main.py ...
```

`main.py` parses command-line arguments and calls `train.train(args, logger)`. `train.train()` loads `configs/base.yaml`, initializes Accelerate/DeepSpeed, builds frozen T5 and SigLIP encoders, builds or loads `RDTRunner`, creates HDF5-backed datasets, wraps them in dataloaders, and runs the training loop.

Because `finetune.sh` passes `--load_from_hdf5`, data goes through:

```text
VLAConsumerDataset
-> HDF5VLADataset
-> parse_hdf5_file()
-> DataCollatorForVLAConsumerDataset
```

Each HDF5 sample is expected to become:

```text
state: (1, 128)
actions: (64, 128)
3 cameras x 2 history frames
language instruction or precomputed language embedding
state/action validity mask
```

The model trains a diffusion objective over action chunks. With the default config, the prediction target is the clean action sample `x0`, not noise.

## 2. Entry Point

`finetune.sh` sets:

```bash
export NCCL_IB_HCA=...
export NCCL_IB_DISABLE=0
export NCCL_SOCKET_IFNAME=bond0
export NCCL_DEBUG=INFO
export NCCL_NVLS_ENABLE=0

export TEXT_ENCODER_NAME="google/t5-v1_1-xxl"
export VISION_ENCODER_NAME="google/siglip-so400m-patch14-384"
export OUTPUT_DIR="./checkpoints/rdt-finetune-1b"
export CFLAGS="-I/usr/include"
export LDFLAGS="-L/usr/lib/x86_64-linux-gnu"
export CUTLASS_PATH="/path/to/cutlass"
export WANDB_PROJECT="robotics_diffusion_transformer"
```

Current script does not set:

```text
CUDA_VISIBLE_DEVICES
PYTHONPATH
HF_HOME
explicit LIBERO data root
WANDB_ENTITY
WANDB_NAME
```

Final command:

```bash
deepspeed --hostfile=hostfile.txt main.py \
    --deepspeed="./configs/zero2.json" \
    --pretrained_model_name_or_path="robotics-diffusion-transformer/rdt-1b" \
    --pretrained_text_encoder_name_or_path=$TEXT_ENCODER_NAME \
    --pretrained_vision_encoder_name_or_path=$VISION_ENCODER_NAME \
    --output_dir=$OUTPUT_DIR \
    --train_batch_size=32 \
    --sample_batch_size=64 \
    --max_train_steps=200000 \
    --checkpointing_period=1000 \
    --sample_period=500 \
    --checkpoints_total_limit=40 \
    --lr_scheduler="constant" \
    --learning_rate=1e-4 \
    --mixed_precision="bf16" \
    --dataloader_num_workers=8 \
    --image_aug \
    --dataset_type="finetune" \
    --state_noise_snr=40 \
    --load_from_hdf5 \
    --report_to=wandb
```

Entrypoint chain:

```text
finetune.sh
└── deepspeed --hostfile=hostfile.txt main.py
    ├── main.parse_args()
    └── train.train(args, logger)
```

## 3. Config / Args

Argument parsing is pure argparse in `main.py::parse_args()`. There is no Hydra or dataclass config system.

Default config path:

```python
--config_path default="configs/base.yaml"
```

Since `finetune.sh` does not override it, `train.train()` reads `configs/base.yaml`:

```python
with open(args.config_path, "r") as fp:
    config = yaml.safe_load(fp)
```

Important config values:

```text
common.img_history_size = 2
common.action_chunk_size = 64
common.num_cameras = 3
common.state_dim = 128
dataset.image_aspect_ratio = pad
dataset.tokenizer_max_length = 1024
model.lang_token_dim = 4096
model.img_token_dim = 1152
model.state_token_dim = 128
model.rdt.hidden_size = 2048
model.rdt.depth = 28
model.rdt.num_heads = 32
model.noise_scheduler.num_train_timesteps = 1000
model.noise_scheduler.num_inference_timesteps = 5
model.noise_scheduler.prediction_type = sample
```

Key argument flow:

| CLI argument | Consumed by | Effect |
|---|---|---|
| `--deepspeed` | `Accelerator(DeepSpeedPlugin(...))` | Enables DeepSpeed ZeRO-2 |
| `--mixed_precision=bf16` | `Accelerator`, `weight_dtype` | Casts model/encoder inputs to bf16 |
| `--pretrained_model_name_or_path` | `RDTRunner.from_pretrained()` | Loads pretrained RDT weights |
| `--pretrained_text_encoder_name_or_path` | `T5Embedder` | Loads T5 tokenizer/encoder |
| `--pretrained_vision_encoder_name_or_path` | `SiglipVisionTower` | Loads SigLIP processor/encoder |
| `--load_from_hdf5` | `VLAConsumerDataset` | Instantiates `HDF5VLADataset` |
| `--dataset_type=finetune` | `VLAConsumerDataset` | Reads `configs/finetune_datasets.json` |
| `--image_aug` | `VLAConsumerDataset.__getitem__` | Enables random visual augmentation |
| `--state_noise_snr=40` | `VLAConsumerDataset.__getitem__` | Adds Gaussian noise to state |
| `--report_to=wandb` | `Accelerator` | Initializes wandb tracker |

## 4. Dataset Path

Dataset creation happens in `train/train.py`:

```python
train_dataset = VLAConsumerDataset(
    config=config["dataset"],
    tokenizer=tokenizer,
    image_processor=image_processor,
    num_cameras=config["common"]["num_cameras"],
    img_history_size=config["common"]["img_history_size"],
    dataset_type=args.dataset_type,
    image_aug=args.image_aug,
    cond_mask_prob=args.cond_mask_prob,
    cam_ext_mask_prob=args.cam_ext_mask_prob,
    state_noise_snr=args.state_noise_snr,
    use_hdf5=args.load_from_hdf5,
    use_precomp_lang_embed=args.precomp_lang_embed,
)
```

`VLAConsumerDataset.__init__()` loads:

```text
configs/dataset_control_freq.json
configs/finetune_datasets.json
configs/dataset_stat.json
```

Because `use_hdf5=True`, it creates:

```python
self.hdf5_dataset = HDF5VLADataset()
```

Current template `data/hdf5_vla_dataset.py` scans:

```python
HDF5_DIR = "data/datasets/agilex/rdt_data/"
self.DATASET_NAME = "agilex"
for root, _, files in os.walk(HDF5_DIR):
    for filename in fnmatch.filter(files, "*.hdf5"):
        self.file_paths.append(os.path.join(root, filename))
```

For LIBERO, this class should be changed to point to the converted LIBERO data and set `DATASET_NAME` to a name registered in the config JSON files.

Important behavior:

- `HDF5VLADataset.__len__()` returns number of episode files.
- `VLAConsumerDataset.__len__()` returns `len(self.hdf5_dataset)` in HDF5 mode.
- `VLAConsumerDataset.__getitem__(index)` ignores the index for HDF5 and calls `self.hdf5_dataset.get_item()`.
- `HDF5VLADataset.get_item(index=None)` randomly samples an episode using episode-length weights, then samples a random timestep inside `parse_hdf5_file()`.

So a training sample corresponds to:

```text
one episode
+ one sampled timestep t
+ image history window ending at t
+ current state at t
+ action chunk actions[t : t + 64]
```

## 5. Single Sample Contract

`HDF5VLADataset.parse_hdf5_file()` must return:

| key | shape | semantic meaning |
|---|---:|---|
| `meta.dataset_name` | str | Dataset name used for control freq/stat lookup |
| `meta.instruction` | str | Natural-language instruction or `.pt` lang embedding path |
| `meta.step_id` | int | Sampled timestep |
| `state` | `(1, 128)` | Current state/proprio in unified RDT vector |
| `actions` | `(64, 128)` | Future action chunk in unified RDT vector |
| `state_indicator` | `(128,)` | Active dimensions in state/action vector |
| `state_std` | `(128,)` | Episode state std, used for state noise |
| `state_mean` | `(128,)` | Episode state mean |
| `state_norm` | `(128,)` | Episode RMS norm, used by sampling eval |
| `cam_high` | `(2, H, W, 3)` | External camera history |
| `cam_high_mask` | `(2,)` | External camera history validity |
| `cam_right_wrist` | `(2, H, W, 3)` | Right wrist camera history |
| `cam_right_wrist_mask` | `(2,)` | Right wrist validity |
| `cam_left_wrist` | `(2, H, W, 3)` | Left wrist camera history |
| `cam_left_wrist_mask` | `(2,)` | Left wrist validity |

The wrapper `VLAConsumerDataset.__getitem__()` converts this to:

```python
data_dict["states"]
data_dict["actions"]
data_dict["state_elem_mask"]
data_dict["state_norm"]
data_dict["images"]
data_dict["input_ids"] or data_dict["lang_embed"]
data_dict["ctrl_freq"]
data_dict["data_idx"]
```

Image preprocessing:

```text
HWC uint8 image
-> PIL.Image
-> optional ColorJitter/corruption
-> optional square padding
-> SiglipImageProcessor.preprocess()
-> CHW float tensor
```

Image order:

```text
for each history timestep i in [0, 1]:
    cam_high[i]
    cam_right_wrist[i]
    cam_left_wrist[i]
```

## 6. Dataloader / Collate

Train DataLoader:

```python
DataLoader(
    train_dataset,
    batch_size=args.train_batch_size,  # 32
    shuffle=True,
    collate_fn=data_collator,
    num_workers=args.dataloader_num_workers,  # 8
    pin_memory=True,
    persistent_workers=True,
)
```

There is no explicit `DistributedSampler`; `accelerator.prepare()` wraps the dataloaders for distributed execution.

`DataCollatorForVLAConsumerDataset.__call__()`:

- stacks `states`, `actions`, `state_elem_mask`, `state_norm`, `images`;
- pads variable-length language `input_ids`;
- builds `lang_attn_mask`;
- pads precomputed language embeddings when `--precomp_lang_embed` is enabled.

Final batch schema:

| batch key | shape | dtype | Used by |
|---|---:|---|---|
| `images` | `(B, 6, C, H, W)` | float tensor | SigLIP vision encoder |
| `states` | `(B, 1, 128)` | float tensor | RDT state condition |
| `actions` | `(B, 64, 128)` | float tensor | Diffusion training target |
| `state_elem_mask` | `(B, 128)` | float tensor after cast | RDT state/action validity condition |
| `state_norm` | `(B, 128)` | float tensor | Sampling eval L2 normalization |
| `ctrl_freqs` | `(B,)` | tensor | RDT control frequency embedding |
| `input_ids` | `(B, L)` | long tensor | T5 encoder |
| `lang_attn_mask` | `(B, L)` | bool tensor | T5/RDT language mask |
| `lang_embeds` | `(B, L, 4096)` | float tensor | Used if `--precomp_lang_embed` |
| `data_indices` | list length B | int list | Sampling eval logging |

## 7. Batch To RDT Forward

In `train/train.py`, each batch is processed as:

```python
images = batch["images"].to(dtype=weight_dtype)
states = batch["states"].to(dtype=weight_dtype)
states = states[:, -1:, :]
actions = batch["actions"].to(dtype=weight_dtype)
state_elem_mask = batch["state_elem_mask"].to(dtype=weight_dtype)
ctrl_freqs = batch["ctrl_freqs"]
```

Vision path:

```python
batch_size, _, C, H, W = images.shape
image_embeds = vision_encoder(images.reshape(-1, C, H, W)).detach()
image_embeds = image_embeds.reshape((batch_size, -1, vision_encoder.hidden_size))
```

Shape:

```text
images: (B, 6, C, H, W)
-> (B*6, C, H, W)
-> SigLIP
-> (B*6, num_patches, 1152)
-> (B, 6*num_patches, 1152)
```

Language path:

```python
text_embeds = batch["lang_embeds"].to(dtype=weight_dtype) \
    if args.precomp_lang_embed \
    else text_encoder(
        input_ids=batch["input_ids"],
        attention_mask=lang_attn_mask,
    )["last_hidden_state"].detach()
```

Shape:

```text
text_embeds: (B, L, 4096)
lang_attn_mask: (B, L)
```

RDT call:

```python
loss = rdt(
    lang_tokens=text_embeds,
    lang_attn_mask=lang_attn_mask,
    img_tokens=image_embeds,
    state_tokens=states,
    action_gt=actions,
    action_mask=state_elem_mask.unsqueeze(1),
    ctrl_freqs=ctrl_freqs,
)
```

## 8. Loss Path

`RDTRunner.compute_loss()`:

```python
noise = torch.randn(action_gt.shape)
timesteps = torch.randint(0, self.num_train_timesteps, (batch_size,))
noisy_action = self.noise_scheduler.add_noise(action_gt, noise, timesteps)

state_action_traj = torch.cat([state_tokens, noisy_action], dim=1)
action_mask = action_mask.expand(-1, state_action_traj.shape[1], -1)
state_action_traj = torch.cat([state_action_traj, action_mask], dim=2)

lang_cond, img_cond, state_action_traj = self.adapt_conditions(
    lang_tokens, img_tokens, state_action_traj
)

pred = self.model(
    state_action_traj,
    ctrl_freqs,
    timesteps,
    lang_cond,
    img_cond,
    lang_mask=lang_attn_mask,
)
```

Shapes:

```text
action_gt: (B, 64, 128)
noise: (B, 64, 128)
noisy_action: (B, 64, 128)
state_tokens: (B, 1, 128)
state_action_traj before mask concat: (B, 65, 128)
action_mask expanded: (B, 65, 128)
state_action_traj after mask concat: (B, 65, 256)
state_action_traj after adaptor: (B, 65, 2048)
pred: (B, 64, 128)
```

Target:

```python
if prediction_type == "sample":
    target = action_gt
elif prediction_type == "epsilon":
    target = noise
```

Default config uses:

```text
prediction_type = sample
```

So the model predicts clean denoised action samples.

Current loss:

```python
loss = F.mse_loss(pred, target)
```

Important: `state_elem_mask` is not used to weight/mask this training loss. It is only appended to model input. Sampling evaluation does use the mask when computing reported metrics.

## 9. Model And Checkpoint Loading

`train.train()` loads encoders:

```python
text_embedder = T5Embedder(...)
vision_encoder = SiglipVisionTower(...)
```

Both encoders are used under `torch.no_grad()` and are not included in the optimizer.

RDT loading:

```python
if args.pretrained_model_name_or_path is not None and not os.path.isfile(...):
    rdt = RDTRunner.from_pretrained(args.pretrained_model_name_or_path)
else:
    rdt = RDTRunner(...)
```

Current `finetune.sh` uses a Hugging Face repo id, so it loads via `RDTRunner.from_pretrained("robotics-diffusion-transformer/rdt-1b")`.

If a local `.pt` file is passed instead, code later does:

```python
checkpoint = torch.load(args.pretrained_model_name_or_path)
rdt.module.load_state_dict(checkpoint["module"])
```

Module summary:

| Module | Class | Trainable | Input | Output |
|---|---|---:|---|---|
| Text encoder | `T5EncoderModel` via `T5Embedder` | No | `input_ids`, `attention_mask` | `(B, L, 4096)` |
| Vision encoder | `SiglipVisionModel` via `SiglipVisionTower` | No | `(B*6, C, H, W)` | `(B*6, P, 1152)` |
| Language adaptor | `RDTRunner.lang_adaptor` | Yes | `(B, L, 4096)` | `(B, L, 2048)` |
| Image adaptor | `RDTRunner.img_adaptor` | Yes | `(B, 6P, 1152)` | `(B, 6P, 2048)` |
| State/action adaptor | `RDTRunner.state_adaptor` | Yes | `(B, 65, 256)` | `(B, 65, 2048)` |
| Transformer | `RDT` | Yes | state/action tokens + conditions | `(B, 64, 128)` |

Optimizer:

```python
params_to_optimize = rdt.parameters()
optimizer = torch.optim.AdamW(params_to_optimize, ...)
```

There is no LoRA, no adapter-only finetune, and no explicit freezing inside `RDTRunner`.

## 10. Training Loop

Step accounting:

- `global_step` counts optimizer sync steps.
- `max_train_steps=200000` is the stopping condition.
- `num_train_epochs` is derived from dataloader length and max steps.
- Gradient accumulation is controlled by `Accelerator(... gradient_accumulation_steps=args.gradient_accumulation_steps)`.

Training operations:

```text
for epoch:
  for batch:
    with accelerator.accumulate(rdt):
      encode images with SigLIP under no_grad
      encode language with T5 under no_grad
      compute diffusion loss
      accelerator.backward(loss)
      clip gradients if sync step
      optimizer.step()
      lr_scheduler.step()
      optimizer.zero_grad()

    ema_model.step(...)

    if sync step:
      global_step += 1
      save checkpoint every checkpointing_period
      run sample eval every sample_period
      log loss/lr
```

Checkpoint save:

```python
save_path = os.path.join(args.output_dir, f"checkpoint-{global_step}")
accelerator.save_state(save_path)
accelerator.save_model(ema_rdt, os.path.join(save_path, "ema"))
```

Final save:

```python
accelerator.unwrap_model(rdt).save_pretrained(args.output_dir)
accelerator.save_model(ema_rdt, os.path.join(args.output_dir, "ema"))
```

Resume:

```python
accelerator.load_state(os.path.join(args.output_dir, path))
```

If that fails, it tries to load:

```text
checkpoint-*/pytorch_model/mp_rank_00_model_states.pt
```

and then loads EMA from:

```text
checkpoint-*/ema/model.safetensors
```

## 11. Full Call Graph

```text
finetune.sh
└── deepspeed --hostfile=hostfile.txt main.py
    ├── main.parse_args()
    │   └── argparse + LOCAL_RANK environment override
    └── train.train(args, logger)
        ├── yaml.safe_load(configs/base.yaml)
        ├── Accelerator(DeepSpeedPlugin(configs/zero2.json), bf16, wandb)
        ├── T5Embedder(...)
        │   └── AutoTokenizer + T5EncoderModel.eval()
        ├── SiglipVisionTower(...)
        │   └── SiglipImageProcessor + SiglipVisionModel.eval()
        ├── RDTRunner.from_pretrained("robotics-diffusion-transformer/rdt-1b")
        │   ├── RDT(...)
        │   ├── language/image/state adaptors
        │   └── DDPM + DPM-Solver schedulers
        ├── VLAConsumerDataset(... use_hdf5=True ...)
        │   └── HDF5VLADataset()
        │       ├── scan HDF5 files
        │       ├── parse_hdf5_file_state_only()
        │       └── get_item()
        │           └── parse_hdf5_file()
        ├── DataCollatorForVLAConsumerDataset
        ├── DataLoader(train/sample)
        ├── accelerator.prepare(...)
        ├── optional resume/local .pt load
        └── training loop
            ├── batch -> SigLIP/T5
            ├── RDTRunner.compute_loss()
            │   ├── sample diffusion timestep
            │   ├── add_noise(action_gt)
            │   ├── adapt conditions
            │   ├── RDT.forward()
            │   └── MSE(pred, action_gt)
            ├── backward / clip / optimizer / scheduler
            ├── sample eval
            └── checkpoint save
```

## 12. Semantic Data Flow

```text
LIBERO raw data
  -> converted HDF5 episodes
      -> data/hdf5_vla_dataset.py::HDF5VLADataset
          -> sample dict
              state: (1, 128)
              actions: (64, 128)
              images: 3 cameras x 2 history frames
              instruction
              state_indicator
          -> train/dataset.py::VLAConsumerDataset.__getitem__
              image pad/preprocess
              language tokenize or embedding load
              optional state noise / condition masking
          -> DataCollatorForVLAConsumerDataset
              stack/pad into batch
          -> train.py loop
              images -> SigLIP -> visual tokens
              input_ids -> T5 -> language tokens
              states -> state condition
              actions -> clean diffusion target
          -> RDTRunner.compute_loss()
              noisy action + state + validity mask
          -> RDT.forward()
              timestep/frequency/state/action tokens
              alternating language/image cross-attention
          -> pred actions: (B, 64, 128)
          -> MSE loss
          -> optimizer update
```

## 13. LIBERO-RDT Adapter Risk Checklist

| Check | Code location | Expected format | Common failure | Verification |
|---|---|---|---|---|
| Dataset name | `train/dataset.py` | In `finetune_datasets.json`, `dataset_control_freq.json`, `dataset_stat.json` | `KeyError` | Print `content["dataset_name"]` |
| HDF5 extension | `data/hdf5_vla_dataset.py` | Template scans `*.hdf5` | LIBERO `.h5` ignored | Print `len(file_paths)` |
| State shape | adapter return | `(1,128)` | raw LIBERO state returned unpadded | assert shape |
| Action shape | adapter return | `(64,128)` | action chunk wrong length or dim | assert shape |
| Active dims | `state_indicator` | `(128,)`, 1 on active dims | mask mismatches action dims | print nonzero indices |
| Single-arm placement | `configs/state_vec.py` | right-arm/eef slots preferred | filled left-arm slots | inspect active index names |
| Image shape | adapter return | `(2,H,W,3)` uint8 | CHW passed as HWC | save debug image |
| Image color | adapter return | RGB expected by PIL/SigLIP | BGR from OpenCV | save image, inspect colors |
| Camera order | `train/dataset.py` | high, right wrist, left wrist | wrist swapped | dump camera thumbnails |
| Episode boundary | adapter action chunk | pad within episode only | crosses episode end | assert source episode id constant |
| Language | `meta["instruction"]` | natural string or `.pt` path with `--precomp_lang_embed` | path tokenized as text | print token length |
| Dataset stats | `configs/dataset_stat.json` | has LIBERO state mean | missing stat key | load sample through `VLAConsumerDataset` |
| Loss masking | `models/rdt_runner.py` | current loss unmasked | invalid dims dominate MSE | compare masked/unmasked loss |
| Control frequency | `dataset_control_freq.json` | numeric frequency | missing or wrong value | print `ctrl_freqs` batch |
| Dtype/device | train loop | tensors compatible with bf16/CUDA | CPU or int tensors in model | print dtype/device first batch |

## 14. Suggested Debug Hooks

Recommended temporary prints:

1. In `HDF5VLADataset.__init__()`:

```python
print(f"[RDT_DEBUG] num files: {len(self.file_paths)}")
print(f"[RDT_DEBUG] first files: {self.file_paths[:3]}")
print(f"[RDT_DEBUG] episode lens min/max: {np.min(episode_lens)}, {np.max(episode_lens)}")
```

2. Before `parse_hdf5_file()` returns:

```python
print("[RDT_DEBUG] sample",
      "step=", step_id,
      "state=", state.shape, state.dtype,
      "actions=", actions.shape, actions.dtype,
      "active_dims=", np.where(state_indicator > 0)[0].tolist(),
      "action_minmax=", float(actions.min()), float(actions.max()))
```

3. Before `VLAConsumerDataset.__getitem__()` returns:

```python
print("[RDT_DEBUG] dataset item",
      data_dict["dataset_name"],
      data_dict["states"].shape,
      data_dict["actions"].shape,
      len(preprocessed_images),
      preprocessed_images[0].shape)
```

4. On the first training batch in `train.train()`:

```python
print("[RDT_DEBUG] batch schema", {
    k: (v.shape, v.dtype, v.device) if hasattr(v, "shape") else type(v)
    for k, v in batch.items()
})
```

## 15. Recommendations

For LIBERO adaptation, modify and verify in this order:

1. `data/hdf5_vla_dataset.py`
   - make file discovery robust;
   - return the exact RDT sample contract;
   - assert every shape at return time.

2. Config JSON files
   - register the LIBERO dataset name everywhere `VLAConsumerDataset` expects it.

3. One-sample smoke test
   - instantiate `HDF5VLADataset`;
   - call `get_item()`;
   - verify state/action/image/language shapes.

4. Batch smoke test
   - instantiate `VLAConsumerDataset`;
   - create a DataLoader with batch size 2;
   - inspect batch schema.

5. One-step training smoke test
   - run with `--max_train_steps=1 --sample_period=-1`;
   - confirm no NaN and no shape/device mismatch.

6. Consider masked training loss
   - if LIBERO uses only a small subset of the 128 action dimensions, audit `RDTRunner.compute_loss()` and consider applying `state_elem_mask` to the MSE reduction.
