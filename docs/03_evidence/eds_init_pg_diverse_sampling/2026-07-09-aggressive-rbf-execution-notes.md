# RBF+EDS Aggressive Sweep Execution Notes

时间：2026-07-09

## 运行上下文

- Worktree: `/home/hynx/VLA-Pilot++/.worktrees/exp/eds-init-pg-diverse-sampling`
- Branch: `exp/eds-init-pg-diverse-sampling`
- Base commit at execution start: `ed1faa9f7486d5916377844f66318a30bc9302a0`
- Guidance cache: `/home/hynx/VLA-Pilot++/outputs/libero/2026-06-04_13-21-01/episode_1/vlm_agent`
- Final report: `docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-09-aggressive-rbf-parameter-sweep.md`
- Status CSV: `docs/03_evidence/eds_init_pg_diverse_sampling/rdt_eds_eval_status.csv`

## 执行命令

初始化状态表：

```bash
python scripts/rdt_eds_eval_runner.py init \
  --level level2 \
  --episodes 3 \
  --offline-vlm \
  --cached-functions-dir /home/hynx/VLA-Pilot++/outputs/libero/2026-06-04_13-21-01/episode_1/vlm_agent
```

首次按设计尝试 8 卡并行：

```bash
python scripts/rdt_eds_eval_runner.py run-level \
  --level level2 \
  --episodes 3 \
  --gpus 0,1,2,3,4,5,6,7 \
  --timeout-seconds 28800 \
  --cached-functions-dir /home/hynx/VLA-Pilot++/outputs/libero/2026-06-04_13-21-01/episode_1/vlm_agent \
  --offline-vlm
```

最终完成实验的命令：

```bash
python scripts/rdt_eds_eval_runner.py run-level \
  --level level2 \
  --episodes 3 \
  --gpus 0 \
  --timeout-seconds 28800 \
  --cached-functions-dir /home/hynx/VLA-Pilot++/outputs/libero/2026-06-04_13-21-01/episode_1/vlm_agent \
  --offline-vlm \
  --resume
```

最终报告刷新命令：

```bash
python scripts/rdt_eds_eval_runner.py write-aggressive-rbf-report --episodes 3
```

## 运行中遇到的问题

第一次 8 卡并行运行期间，部分 Python 进程和一次 `nvidia-smi` 查询进入 NVIDIA driver wait 状态。该轮只产生了部分 metrics，未产生完整 `results.txt`，因此不作为最终算法结果。部分输出已归档到：

`outputs/rdt_eds_eval_stalled_20260709_165621`

第二次 8 卡并行运行中，仅 `rbf_s10_start06` 完整成功；其余 job 在 CUDA/EGL 初始化阶段失败，典型错误包括：

- `CUDA driver initialization failed`
- `RuntimeError: No CUDA GPUs are available`
- `ImportError: Cannot initialize a EGL device display`
- `/dev/dri/renderD*` permission denied

进一步 probe 显示，当时只有 GPU0 可以完成 `torch.cuda.init()`，GPU1-7 均无法初始化 CUDA runtime。因此最终采用 GPU0 单卡 `--resume` 顺序补跑所有未完成 job。该路径通过了 LIBERO env、RDT model、EDS loop 和 qualitative artifact 保存。

## Runner 适配

为便于后续复现和定位 GPU/EGL 问题，`scripts/rdt_eds_eval_runner.py` 增加了运行时日志：

- `CUDA_DEVICE_ORDER=PCI_BUS_ID`
- `CUDA_VISIBLE_DEVICES=<gpu>`
- `MUJOCO_EGL_DEVICE_ID=<mapped-id>`
- 每个 job 日志中的 `Runtime:` 行

这属于实验 runner 的 host/runtime 可观测性与适配，不改变 EDS/RBF 算法逻辑。

## 最终完成状态

8 个 level2 aggressive sweep job 均完成：

- `iid_baseline`: 0/3
- `rbf_s1_start_null`: 0/3
- `rbf_s5_start06`: 0/3
- `rbf_s10_start06`: 0/3
- `rbf_s20_start06`: 0/3
- `rbf_s5_start08`: 0/3
- `rbf_s10_start08`: 0/3
- `rbf_s20_start08`: 1/3

`rbf_s20_start08` 的 metrics 记录数为 77，而不是 90；原因是该 run 有 1 个 episode 成功提前结束。状态表显示该 job `exit_code=0`、`videos=3`、`qualitative_png=144`，因此视为完整 run。

## 最终报告关键信息

- Final report verdict: `pass`
- Safety gate: 全部通过，无 fallback、无 grad failure、无 nonfinite、无 action mask violation
- Mechanism gate: aggressive RBF 配置全部通过
- Utility gate: 除 `rbf_s20_start08` 外均通过；`rbf_s20_start08` 的 utility gate 因 target distance/reward 阈值判定为 fail，但该 run 是唯一取得 1/3 成功率的配置
- 最强 diversity 配置：`rbf_s20_start08`
  - `initial_eef_diversity_final=0.156`
  - `endpoint_spread_final=0.082`
  - `success=1/3`

## Fresh Verification

完成后执行：

```bash
python -m py_compile scripts/rdt_eds_eval_runner.py
python scripts/rdt_eds_eval_runner.py write-aggressive-rbf-report --episodes 3
```

并用结构化校验脚本确认：

- 8 个 job 状态均为 `done`
- 8 个 job exit code 均为 0
- 每个 job 均有 `results.txt`
- 每个 job 均有非空 `eds_eval/eds_metrics.jsonl`
- 每个 job 均有 3 个视频
- 每个 job 均有 144 个 qualitative PNG
- RBF job 均无 fallback、grad failure、nonfinite
