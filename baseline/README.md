# π0.5 v44 / LIBERO-PRO baselines

各方法的独立实现，全部从 **`pi05_libero_finetuned_v044`** 起步，沿用该 checkpoint 的两路图像、8D state、50-step flow chunk、7D action 和原始归一化统计。训练结果是独立 artifact，不会注册到正在运行的 self-improve/replay 系统。

**2026-09-14 新增：**[Slow Loop：Always Expansion + Merge（α=0.8）](experiments/env_position20_20260910/slow_loop_expansion_a08_20260914/README.md)。单独使用 GPU4，按主实验最新 slow loop 做完整策略 SFT 与固定合并，每个任务完成后评估该任务及全部历史任务，记录成功率矩阵和遗忘指标。该方法使用独立的 `python -m baseline.slow_loop_expansion` 入口。

代码位置：

- 本地：`/Users/hengyil6/Projects/vla-pilot-plus/baseline/`
- hgpu1：`/root/vla-pilot-plus/baseline/`
- 服务器等价路径：`/shared/hengyil6/vls/repo/baseline/`
- 默认实验输出：`/shared/hengyil6/vls/baseline_runs/<run-name>/`

本目录不导入 `main.py`，不改写 `configs/`、`mode_gate/`、checkpoint、protocol、registry 或 replay 产物。直接使用服务器已安装的 LeRobot/PyTorch 环境，无需更新共享依赖。

**2026-09-08 当前实验：**见 [主实验对齐配置与运行说明](experiments/main_aligned_20260908/README.md)。本轮使用每卡 batch 4 × 梯度累积 8 = 有效 batch 32；独立进程运行训练/采集，GPU 6 保持保护。

## 方法和入口

| 配置 | 方法实现 | 训练输入 |
|---|---|---|
| `configs/clare.json` | `methods/clare.py` | 按任务提供的新示范；不读取旧示范 |
| `configs/mlr_ifa.json` | `methods/mlr_ifa.py` | 新示范 + 按字节限制的历史 latent memory |
| `configs/continual_vla_rl.json` | `methods/continual_rl.py` | LIBERO-PRO 在线交互和环境奖励 |
| `configs/rl2_vla.json` | `methods/rl2_vla.py` | 独立收集的离线 rollout、成功/失败标签 |

迁移涉及模型结构和接口调整，实验中请标注 **PI0.5/PRO adaptation**，不要标成原作者模型的原样复现。[METHODS.md](METHODS.md) 逐项列出保留机制、迁移差异和成本口径。尚未训练出的模型不能直接用于方法性能比较；`evaluate` 不指定 artifact 时明确评估原始 v44。

## 先检查配置

所有命令均在 `vla-pilot-plus` 根目录运行。

```bash
cd /root/vla-pilot-plus
/shared/hengyil6/vls/envs/vla-pilot/bin/python -m baseline --help
/shared/hengyil6/vls/envs/vla-pilot/bin/python -m baseline plan --config baseline/configs/clare.json
```

`plan` 只读配置和现有 protocol，列出确定的任务顺序，不加载模型、不创建实验目录。本地没有 checkpoint 或服务器 protocol 时，仍可查看配置和缺失路径；可用 `--checkpoint`、`--tokenizer`、`--protocol` 覆盖为本地副本。

默认种子为 `20260825`。正式比较建议另做 `20260826`、`20260827`，统一任务顺序、初始状态和预算。初始模型身份由权重、processor 和 tokenizer 文件内容校验，跨机器的目录路径本身不影响身份。

## GPU 与 replay 隔离

执行前查看 GPU 剩余显存；下面的 `7` **只是示例，使用前需重新检查**。按用户指定，允许与已有作业共用显存足够的 GPU。

```bash
nvidia-smi
export CUDA_VISIBLE_DEVICES=7
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2
export PYTHONDONTWRITEBYTECODE=1
```

命令只接受一个显式物理 GPU，并把它映射到 `cuda:0`。启动时要求至少 `gpu_min_free_mib=32768` MiB 剩余显存，允许 GPU 上已有进程。默认 `protected_gpu_indices=[6]`，保护当前 replay 所用卡。独占锁只防止本目录的两个启动器同时选中同一张卡；检查后的其他作业显存增长仍可能导致 OOM，实际所需显存也取决于方法和 batch size。

不会自动选择 GPU，不会结束其他进程。`run-name` 必须是新名称；已有输出拒绝覆盖。输出目录禁止进入 `self_improve` 和模型目录。

## CLARE 与 MLR-IFA

复制 `configs/task_data.example.json` 到自己的实验配置，逐任务填写：

1. `task_key`：来自 `baseline plan` 的完整标识；
2. `root` / `repo_id`：已有的本地 LeRobot 数据集；
3. `episodes`：该任务实际对应的 episode indices，必须明确列出；
4. `init_state_ids`：这些示范实际使用的初始状态，必须全部属于该任务的 `demo_online_pool`。

这里的初始状态声明必须来自采集记录。检查器验证声明与 protocol 是否一致，不能凭空恢复一个旧数据集中未记录的 provenance。禁止把 held-out 初始状态的示范混入训练。

```bash
/shared/hengyil6/vls/envs/vla-pilot/bin/python -m baseline train \
  --config baseline/configs/clare.json \
  --task-data /absolute/path/to/task_data.json \
  --run-name clare_seed20260825

/shared/hengyil6/vls/envs/vla-pilot/bin/python -m baseline train \
  --config baseline/configs/mlr_ifa.json \
  --task-data /absolute/path/to/task_data.json \
  --run-name mlr_ifa_seed20260825
```

CLARE 先训练新 adapter，再训练该阶段的 AE discriminator，冻结历史参数。MLR-IFA 自动提取冻结的多模态 prefix tokens，训练 action expert 与辅助 IFA projection；下一任务只回放被 memory index 保留的旧记录。

每完成一阶段保存 `stage_000/` 等目录及 `latest.json`。可从**已完成阶段**继续到新的 run：

```bash
/shared/hengyil6/vls/envs/vla-pilot/bin/python -m baseline train \
  --config baseline/configs/clare.json \
  --task-data /absolute/path/to/task_data.json \
  --resume /shared/hengyil6/vls/baseline_runs/clare_seed20260825/stage_003 \
  --run-name clare_seed20260825_continue
```

已学习任务会跳过。当前不提供阶段中途 optimizer 状态恢复；阶段中断需从上一个完成的阶段重跑。MLR-IFA 的 resume 还需要保留 artifact 引用的 latent files。

恢复时检查原始权重、归一化、tokenizer、protocol 和算法设置，并拒绝改变 action horizon 或 denoising 步数。RL² 的 `trigger`、`candidates`、`compose_mean`、`compose_std` 允许作为明确的推理消融配置覆盖，结果中会保存实际配置。

## Continual VLA RL

```bash
/shared/hengyil6/vls/envs/vla-pilot/bin/python -m baseline train \
  --config baseline/configs/continual_vla_rl.json \
  --run-name continual_rl_seed20260825
```

默认在 protocol 的 `demo_online_pool` 上顺序学习 40 个任务；可重复传入 `--task-key` 做小规模试验。每个 GRPO group 使用相同环境初始状态和不同策略采样种子。全组 reward 相同时记录为无信息组，不伪造策略梯度。`groups_per_stage` 和 `group_size` 决定真实交互成本。

PI0.5 的确定性 flow ODE 没有现成 token log-probability。这里使用显式 Gaussian stochastic Euler transitions 做 on-policy GRPO，训练和评估保持相同的随机转移形式。LoRA 默认覆盖 action expert 的 attention 与 FFN projections，冻结 VLM。

## RL²-VLA

先用未修改的 v44 收集独立数据。此命令**不会读取或追加当前 replay 的快照、标签或 ledger**：

```bash
/shared/hengyil6/vls/envs/vla-pilot/bin/python -m baseline collect \
  --config baseline/configs/rl2_vla.json \
  --repeats 20 \
  --run-name rl2_offline_seed20260825
```

收集在 `demo_online_pool` 内进行，再按初始状态分成 train/calibration/validation，同一初始状态的不同重复不会跨分组。记录策略选定 action chunk 的 latent、reward、next latent、bootstrap discount 和 episode success；若中途终止，另记录该 chunk 实际执行的步数。

```bash
/shared/hengyil6/vls/envs/vla-pilot/bin/python -m baseline train \
  --config baseline/configs/rl2_vla.json \
  --rollouts /shared/hengyil6/vls/baseline_runs/rl2_offline_seed20260825/rollouts.json \
  --run-name rl2_seed20260825
```

训练包含 QAM 的 TD/flow/adjoint objectives、独立候选成功率 verifier，以及 latent LSTM failure detector。训练分组必须同时有成功和失败 episode。默认 conformal alpha=0.1，校准至少需要 9 个成功 episode；不足会明确报错，不能拿 evaluation episode 补齐。

当前离线数据入口是本启动器采集的 π0.5 rollout，而非 BridgeV2；没有假定 LIBERO 示范自带 RL reward。若后续加入真实示范，应先导出包含正确 chunk reward、terminal 和 next latent 的相同数据契约，保留训练来源说明。

## 统一评估

```bash
# 起始模型
/shared/hengyil6/vls/envs/vla-pilot/bin/python -m baseline evaluate \
  --config baseline/configs/clare.json --run-name theta0_dev

# 已训练方法：从 artifact 自动读取配置
/shared/hengyil6/vls/envs/vla-pilot/bin/python -m baseline evaluate \
  --artifact /shared/hengyil6/vls/baseline_runs/clare_seed20260825/stage_000 \
  --split fixed_development_probe --run-name clare_stage0_dev
```

可选 split：`fixed_development_probe`、`policy_alpha_selection`、`policy_regression`。提供冻结 `experiment_plan` 时，还可用 `main_online` 配对主实验的训练池 context，该分数不能作为 held-out 结果。本入口不开放 final-sealed。`--limit 1` 用于小检查，会在摘要中明确标为 partial development check。

每个 episode 都验证 runtime suite、task、扰动类型、init-state 与 protocol 一致。`episodes.jsonl` 保留配对结果；`summary.json` 包含宏/微成功率、分任务成功率、动作步数、时间和 steering 次数。评估每个阶段的 artifact 可构造 stage × task 矩阵：

```bash
/shared/hengyil6/vls/envs/vla-pilot/bin/python -m baseline metrics /absolute/path/to/success_matrix.json
```

指标包括最终平均成功率、forgetting、backward transfer 和各阶段已学任务平均成功率；最后一项是离散阶段均值，不冒称连续训练步 AUC。

## 验证

2026-09-11 两个 RL baseline 的初始化超时修复、采集前缀复用和优化器恢复说明见 [RECOVERY_20260911.md](RECOVERY_20260911.md)。

CPU 测试不加载模型或模拟器：

```bash
mkdir -p baseline/test-results
CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 \
  /shared/hengyil6/vls/envs/vla-pilot/bin/python -m pytest baseline/tests \
  -q -p no:cacheprovider --basetemp=baseline/test-results/pytest
```

显存足够的 GPU 上的真实 v44 smoke 覆盖原始 sampler 对齐、latent 落盘、四个方法的梯度和权重恢复；可选模拟器检查最多执行 10 个动作：

```bash
CUDA_VISIBLE_DEVICES=7 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 \
  /shared/hengyil6/vls/envs/vla-pilot/bin/python -m baseline smoke \
  --config baseline/configs/clare.json --run-name v44_integration_check --with-environment
```

Smoke 使用合成训练目标，仅证明执行路径，不能报告为 baseline 性能、成功率或已完成训练。实际已执行的验证范围见 [VALIDATION.md](VALIDATION.md)。

## 冻结 v44 + VLS（第五项 baseline）

独立入口 `python -m baseline.vls` 复用项目的 VLS steering，按相同的 20 项任务、40 条固定 development probe 评估冻结 v44。它不进入上述四项训练调度，不加载自进化注册表。完整配置、预算、运行和恢复方法见 [VLS.md](VLS.md)。本轮额外评测的输出位置登记在 `experiments/env_position20_20260910/additional_evaluations.json`。
