---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: feat/rdt-libero-gt-rollout-reintegration
source_commit: 360a6d052861
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/docs/superpowers/evidence/2026-05-23-rdt-libero-finetune-evidence-report.md
summary: RDT LIBERO Fine-Tuning Evidence Report
duplicate_sources:
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/superpowers/evidence/2026-05-23-rdt-libero-finetune-evidence-report.md
---

# RDT LIBERO Fine-Tuning Evidence Report

日期: 2026-05-23
工作目录: `third_party/rdt`
验证目标: 在 conda env `rdt` 中验证当前 LIBERO single-suite fine-tuning implementation 的代码正确性、训练可运行性和语义一致性。

## 1. 环境修正结论

### 1.1 `vla-pilot` 回滚

已从 `vla-pilot` 中卸载本任务误装/误升级的 RDT 训练依赖：

```text
imgaug, deepspeed, tensorboard, scikit-image, Shapely, lazy-loader, tifffile,
msgpack, hjson, ninja, py-cpuinfo, pynvml, markdown, tensorboard-data-server,
werkzeug
```

验证命令显示这些包在 `vla-pilot` 中均为 `Package(s) not found`。同时恢复到本轮修复前观察到的核心版本：

```text
networkx       2.2
pydantic       2.12.2
pydantic_core  2.41.4
```

注意: 本次回滚基于本轮可观察到的 pip 层面修改和版本记录；仓库中没有可用于逐包校验的 `vla-pilot` lockfile。

### 1.2 `rdt` 环境修正

所有 RDT 训练与验证已切换到 conda env `rdt`。最终验证环境：

```text
python          3.10.0
numpy           1.26.4
torch           2.1.0+cu121
torchvision     0.16.0+cu121
deepspeed       0.14.2
accelerate      0.30.1
diffusers       0.27.2
transformers    4.41.0
huggingface_hub 0.25.2
imgaug          0.4.0
tensorboard     2.20.0
pytest          9.0.3
```

修复内容：

- 清理 `rdt` 中混装的 `torch-2.1.0+cu121` / `torch-2.12.0` 残留，干净重装 `torch==2.1.0+cu121` 和 `torchvision==0.16.0+cu121`。
- 将 `numpy` 从 `2.2.6` 降为 `1.26.4`，避免 PyTorch 2.1 的 NumPy 2 ABI 警告和潜在崩溃。
- 安装 `tensorboard` 与 `pytest` 到 `rdt`。
- 将 `huggingface_hub` pin 到 `0.25.2`，恢复 `diffusers==0.27.2` 需要的 `cached_download` API。
- `pip check` 结果: `No broken requirements found.`

### 1.3 脚本保护

`finetune_libero.sh` 已添加 conda env guard：

- 当前环境不是 `rdt` 时立即退出。
- `CONDA_DEFAULT_ENV=vla-pilot bash finetune_libero.sh` 验证结果为 exit code 2，并提示应激活 `rdt`。

同时移除 `CUTLASS_PATH=/path/to/cutlass` 伪默认值；未设置 CUTLASS 时 DeepSpeed 只给 warning，不再因不存在的 `CHANGELOG.md` 崩溃。

## 2. 逐任务测试结果

### Task 1: LIBERO loader tests

状态: 成功。

命令：

```bash
CUDA_VISIBLE_DEVICES=0 /home/hynx/miniconda3/envs/rdt/bin/python -m pytest \
  tests/test_libero_vla_dataset.py \
  tests/test_image_corrupt_compat.py \
  tests/test_hub_mixin_compat.py -q
```

结果：

```text
10 passed, 1 warning in 1.61s
```

覆盖点：

- LIBERO synthetic HDF5 demo indexing。
- state/action 128D slot 写入。
- 6D rotation round-trip。
- gripper open-high 映射。
- multi-demo indexing。
- image mask shape。
- imgaug / HuggingFace hub compatibility。

### Task 2: LIBERO dataset adapter

状态: 成功。

关键语义验证：

```text
state[30:33] = ee_pos
state[33:39] = rotvec_to_ortho6d(ee_ori)
state[10]    = gripper open scalar

actions[30:33] = normalized OSC position input scaled to +/-0.05 m
actions[33:39] = rotvec_to_ortho6d(normalized OSC rotation input scaled to +/-0.5 rad)
actions[10]    = (1 - raw_gripper) / 2
```

该实现符合设计文档的 "RDT-convention first" 方向：物理量写入 RDT EEF slots，不直接把 LIBERO normalized controller input 当作物理 state/action。

### Task 3: HDF5 backend wiring

状态: 成功。

`RDT_HDF5_BACKEND=libero` 时，现有 `data.hdf5_vla_dataset.HDF5VLADataset` 会 rebind 到 `LiberoVLADataset`。真实数据 smoke 和训练均走该路径，证明已接入 RDT 原有 `--load_from_hdf5` fine-tuning path。

### Task 4: Fine-tuning configs

状态: 成功。

JSON 验证：

```text
configs/finetune_datasets.json: ok
configs/finetune_sample_weights.json: ok
configs/dataset_control_freq.json: ok
configs/dataset_stat.json: ok
```

当前 fine-tune dataset list：

```json
["libero_10", "libero_object"]
```

当前 control frequency：

```text
libero_10     20
libero_object 20
```

说明: 四套 full LIBERO suite 的注册属于 Task 9，目前尚未启用。

### Task 5: Real dataset smoke test

状态: 成功。

命令：

```bash
CUDA_VISIBLE_DEVICES=0 /home/hynx/miniconda3/envs/rdt/bin/python \
  scripts/smoke_test_libero_dataset.py \
  --suite libero_10 \
  --data-root /mnt/data/hf_cache/hub \
  --consumer
```

结果摘要：

```text
dataset_name: libero_10
instruction: turn on the stove and put the moka pot on it
state: (1, 128) float32
actions: (64, 128) float32
active_indices: [10, 30, 31, 32, 33, 34, 35, 36, 37, 38]
cam_high: (2, 128, 128, 3) [False, True]
cam_right_wrist: (2, 128, 128, 3) [False, True]
cam_left_wrist: (2, 0, 0, 0) [False, False]
consumer.states: (2, 1, 128)
consumer.actions: (2, 64, 128)
consumer.images: (2, 6, 3, 384, 384)
```

结论: LIBERO 两路真实相机正确接入 RDT 三相机 contract，缺失 left wrist camera 通过 mask false 表示。

### Task 6: Dataset statistics

状态: 成功，但仅限 `libero_10`。

`configs/dataset_stat.json` 中存在 `libero_10`，且 `state_mean/state_std/state_min/state_max` 均为 128 维。

Active slots:

```text
active_indices     [30, 31, 32, 33, 34, 35, 36, 37, 38, 10]
active_state_mean  [-0.041613, 0.032551, 0.841278, 0.637458, -0.269382,
                    -0.144948, -0.305629, -0.634826, -0.018534, 0.71374]
active_state_std   [0.104536, 0.144215, 0.257126, 0.433547, 0.492242,
                    0.264208, 0.53798, 0.447831, 0.115191, 0.327217]
```

说明: RDT 现有 `compute_dataset_stat_hdf5.py` 只持久化 state stats；action stats 未写入 `dataset_stat.json`。

### Task 7: Fine-tuning script

状态: 成功。

验证：

```text
bash -n finetune_libero.sh: pass
wrong env guard: pass, exits before training in vla-pilot
rdt env launch: pass
single-process defaults: MASTER_ADDR/RANK/WORLD_SIZE/LOCAL_RANK provided by script
CUTLASS unset behavior: pass, DeepSpeed warning only
```

### Task 8: `libero_10` training smoke

状态: 成功。

#### One-step fine-tune

命令：

```bash
CUDA_VISIBLE_DEVICES=0 conda run -n rdt bash -lc '
  unset CUTLASS_PATH;
  RDT_LIBERO_SUITES=libero_10 \
  OUTPUT_DIR=./checkpoints/rdt-libero-smoke-rdt-env \
  MAX_TRAIN_STEPS=1 \
  TRAIN_BATCH_SIZE=1 \
  SAMPLE_BATCH_SIZE=1 \
  SAMPLE_PERIOD=-1 \
  REPORT_TO=tensorboard \
  DATALOADER_NUM_WORKERS=2 \
  ./finetune_libero.sh'
```

结果：

```text
Num examples = 500
Total optimization steps = 1
final loss = 0.0009
checkpoint saved: checkpoints/rdt-libero-smoke-rdt-env
```

TensorBoard scalars：

```text
loss [(1, 0.0009)]
lr   [(1, 0.0001)]
```

#### 10-step sampled fine-tune

命令：

```bash
CUDA_VISIBLE_DEVICES=0 conda run -n rdt bash -lc '
  unset CUTLASS_PATH;
  NCCL_DEBUG=WARN \
  RDT_LIBERO_SUITES=libero_10 \
  OUTPUT_DIR=./checkpoints/rdt-libero-smoke-sampled-rdt-env \
  MAX_TRAIN_STEPS=10 \
  TRAIN_BATCH_SIZE=1 \
  SAMPLE_BATCH_SIZE=1 \
  SAMPLE_PERIOD=5 \
  REPORT_TO=tensorboard \
  DATALOADER_NUM_WORKERS=2 \
  ./finetune_libero.sh'
```

结果：

```text
Num examples = 500
Total optimization steps = 10
step 5  overall_avg_sample_mse = 0.0711, overall_avg_sample_l2err = 0.6482
step 10 overall_avg_sample_mse = 0.0661, overall_avg_sample_l2err = 0.3264
final loss = 0.016968
checkpoint saved: checkpoints/rdt-libero-smoke-sampled-rdt-env
```

Checkpoint 落盘：

```text
checkpoints/rdt-libero-smoke-rdt-env/pytorch_model.bin
checkpoints/rdt-libero-smoke-rdt-env/ema/model.safetensors
checkpoints/rdt-libero-smoke-sampled-rdt-env/pytorch_model.bin
checkpoints/rdt-libero-smoke-sampled-rdt-env/ema/model.safetensors
```

训练质量解释：

- 10-step smoke 的 loss 不构成收敛证明。
- sample MSE 从 step 5 的 `0.0711` 到 step 10 的 `0.0661` 有轻微下降，L2 error 从 `0.6482` 到 `0.3264` 明显下降。
- 该结果足以证明数据、模型、优化器、DeepSpeed、采样评估和 checkpoint 保存路径整体联通；不足以证明 rollout 成功率。

## 3. 整体实现评估

当前 implementation 在代码 contract 层面是正确的：

- LIBERO HDF5 task/demo 结构可索引。
- RDT 128D state/action contract 保持不变。
- active state/action slots 与 `configs/state_vec.py` 的 right EEF + right gripper slots 对齐。
- two-camera LIBERO input 被映射到 RDT high/right_wrist；left_wrist 缺失以 zero-shape + mask false 表示。
- 使用 RDT 原有 `VLAConsumerDataset`、collator、SigLIP/T5 encoder、RDT runner 和 DeepSpeed fine-tuning path，没有改模型架构。

当前 implementation 在语义层面基本符合设计预期：

- EEF proprioception 取自 `obs/ee_pos` / `obs/ee_ori`，没有退回 joint proprioception。
- LIBERO OSC_POSE normalized action 被转换为 controller physical output units 后写入 RDT EEF slots。
- gripper convention 从 LIBERO `-1=open, +1=close` 映射为 RDT open-high `[1=open, 0=close]`。
- rotation 使用 rotvec <-> 6D first-two-columns convention，round-trip 单测通过。

保留判断：

- RDT 原始 loss 仍对 128D action tensor 计算，当前 implementation 依赖 inactive dims 为 0 来降低无效维影响；尚未单独审计/修改 action loss mask。
- LIBERO action slot 表示的是 delta OSC physical command，不是绝对 future EEF pose。该语义与设计一致，但后续 deployment 必须做 inverse mapping 才能 `env.step()`。

## 4. 风险与不确定性

- 尚未做 LIBERO simulator rollout，因此没有 success rate、task completion 或 closed-loop 稳定性证据。
- 当前训练和 stats 只覆盖 `libero_10`；`libero_object/libero_spatial/libero_goal` 未完成 full-suite stats 和训练验证。
- `finetune_datasets.json` 当前只列 `libero_10` 和 `libero_object`；Task 9 前不能视作 full LIBERO official training 配置。
- 当前 `LiberoVLADataset` 要求 `RDT_LIBERO_SUITES` 只包含一个 suite；multi-suite indexing 还未实现。
- `dataset_stat.json` 只有 state stats；action distribution 未持久化为 stats 文件。
- `torch==2.1.0+cu121` 在当前机器上建议显式设置 `CUDA_VISIBLE_DEVICES=0` 运行；未验证多 GPU fine-tuning。
- DeepSpeed 仍有非阻塞 warning: 缺少 libaio、CUTLASS 未设置、sparse_attn 对 torch 2.1 未完全声明兼容、triton 2.1 未被该 DeepSpeed 版本标为已知兼容。
- `vla-pilot` 回滚已按可观察包状态完成，但没有 lockfile 证明它与断链前环境逐字节一致。

## 5. 一致性检查

与设计文档一致：

- 使用 `RDT_HDF5_BACKEND=libero` 接入现有 HDF5 path。
- 保留 RDT architecture、128D state/action、3-camera contract 和 `configs/base.yaml`。
- 使用 right EEF pos + 6D rotation + right gripper-open slots。
- normalized OSC action 转 physical controller output units。
- 初始验证使用 `libero_10`。

与计划/设计存在的受控偏差：

- `finetune_libero.sh` 额外加入 conda env guard，强制使用 `rdt`，防止再次污染 `vla-pilot`。
- `CUTLASS_PATH` 不再默认成 `/path/to/cutlass`，因为该伪路径会导致 DeepSpeed 0.14.2 导入失败。
- `RDT_MODEL_NAME` 默认指向本机实际缓存 `/mnt/data/hf_cache/hub/robotics-diffusion-transformer--rdt-1b`。
- 为当前环境增加了兼容性修复和 pins: `numpy==1.26.4`, `huggingface_hub==0.25.2`, clean `torch==2.1.0+cu121`。
- Task 9 中的 four-suite indexing/config/stats/training 尚未执行。

## 6. 结论

单一数据集 `libero_10` fine-tuning smoke 已成功：

- 代码单测通过。
- 真实 LIBERO HDF5 loader/consumer smoke 通过。
- `rdt` conda env 中 one-step 与 10-step sampled training 均成功。
- loss、sample MSE、checkpoint 和 TensorBoard event 均有落盘证据。

是否可以进入 Task 9：

- 可以进入 Task 9 的实现工作，当前没有代码级或环境级阻塞。
- 不建议直接把当前结果解读为 full LIBERO training 质量已可靠；Task 9 前仍需完成 multi-suite indexing、四套 suite stats、四套 suite consumer smoke、四套 suite training smoke。

仍存在的主要隐患：

- 无 rollout success rate。
- full-suite 数据和 stats 未验证。
- 128D loss mask / inactive dims 语义仍需在扩大训练前审计。
- deployment inverse action mapping 尚未实现。
