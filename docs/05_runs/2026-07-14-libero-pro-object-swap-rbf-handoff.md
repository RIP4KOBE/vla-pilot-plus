# LIBERO-PRO object_swap RDT+EDS+RBF 实验交接报告

更新时间：2026-07-14 04:43:48 UTC

## 1. 当前任务

本 worktree 正在执行 RDT + EDS + RBF 算法变体在 LIBERO-PRO `libero_object_swap` OOD benchmark 上的新增实验。

工作目录：

```bash
/home/hynx/VLA-Pilot++/.worktrees/exp/eds-init-pg-diverse-sampling
```

当前分支与 commit：

```bash
branch: exp/eds-init-pg-diverse-sampling
HEAD: ed1faa9
```

注意：当前 worktree 有大量已实现代码、文档和 evidence 变更，不要 reset 或 checkout 覆盖。

## 2. 实验设置

Benchmark：

```text
LIBERO-PRO OOD Evaluation on libero_object_swap
suite = libero_object_swap
episodes per job = 10
strict perturbation = backend.libero.strict_perturbations=true
```

本轮不重复跑已有 baseline：

- `rdt_unguided`
- `eds_iid_baseline`

最终报告中引用已有 Level-4 对照结果：

```bash
/home/hynx/VLA-Pilot++/.worktrees/feat/rdt_ed_steering_integration/docs/03_evidence/eds_steering/level_4_vls_pi05_libero_pro_ood.md
```

本轮新增矩阵：

- `eds_rbf_init_s20_start08` initial-only: 1 job
- `eds_rbf_init_s20_start08 + rbf_rollout`: 256 jobs

Sweep 变量：

```text
renoise_t_max: [4, 3, 2, 1]
renoise_t_min: 1
rollout_diversity_scale: [5, 10, 15, 20]
rollout_diversity_start_ratio: [0.2, 0.4, 0.6, 0.8]
rollout_diversity_iters: [1, 3, 6, all]
```

固定 EDS/RBF 参数：

```text
policy.type=rdt
main.use_guidance=true
main.guidance_type=eds
main.eds_config.population_size=16
main.eds_config.cem_iters=10
main.eds_config.use_cem=false
main.eds_config.num_elites=16
main.eds_config.temperature=0.1
main.eds_config.initial_sampling_mode=rbf_diverse_denoise
main.eds_config.initial_diversity_scale=20.0
main.eds_config.initial_diversity_start_ratio=0.8
main.eds_config.truncated_rollout_mode=rbf_diverse
```

GPU 约束：

- 只使用 GPU `0,1,2,3`
- GPU `4,5,6,7` 留空，不用于本轮实验

## 3. 输出位置

新增实验输出根目录：

```bash
/home/hynx/VLA-Pilot++/.worktrees/exp/eds-init-pg-diverse-sampling/outputs/ood_eval
```

状态 CSV：

```bash
docs/03_evidence/eds_init_pg_diverse_sampling/rdt_eds_eval_status.csv
```

最终报告目标：

```bash
docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-12-libero-pro-object-swap-rdt-eds-rbf-report.md
```

最终汇总报告：

```bash
docs/03_evidence/eds_init_pg_diverse_sampling/rdt_eds_final_evaluation_report.md
```

## 4. 当前运行状态快照

快照时间：2026-07-14 04:43:48 UTC

当前 runner 当时正在运行：

```text
runner PID: 1125765
runner PGID: 1125765
elapsed: about 01:21:42
command: python scripts/rdt_eds_eval_runner.py run-level --level object_swap_ood_rbf --episodes 10 --gpus 0,1,2,3 --timeout-seconds 28800 --cached-functions-dir /home/hynx/VLA-Pilot++/outputs/libero/2026-06-04_13-21-01/episode_1/vlm_agent --offline-vlm --resume
```

Status CSV 快照：

```text
total jobs: 257
done: 204
failed: 1
running: 4
pending: 48
```

Done success 分布：

```text
0/10 success: 201 jobs
1/10 success: 3 jobs
```

当前有效非零 success jobs：

```text
level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start06_iterall: 1/10
level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start02_iterall: 1/10
level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start04_iterall: 1/10
```

当前 running jobs：

```text
GPU3 level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start08_iter1   videos=3/10 results=false
GPU2 level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start08_iter3   videos=7/10 results=false
GPU1 level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start08_iter6   videos=6/10 results=false
GPU0 level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start08_iterall videos=0/10 results=false
```

当前 failed job：

```text
level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start06_iterall
success: 1/10
failure_reason: videos 9/10
```

这个 job 曾因视频不完整被 resume 重跑，仍然没有补齐 10 个 episode videos。不要把它静默计入 valid result；最终报告里应保留明确 failure reason，除非后续决定单独再清理输出并手动重跑。

磁盘快照：

```text
outputs/ood_eval: 88G
free disk: about 83.4G
```

按当前输出增速，剩余实验大概率仍够跑完；如果后续低于 30G，再考虑清理 quarantine/中间无效输出。

## 5. 新账号接手后的第一步

进入 worktree：

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/exp/eds-init-pg-diverse-sampling
```

先检查是否已有 runner/main.py 正在运行，避免启动重复实验：

```bash
ps -eo pid,ppid,pgid,stat,etime,cmd | rg 'rdt_eds_eval_runner|python main.py|conda run -n vla-pilot' | rg -v rg || true
```

如果能看到 `scripts/rdt_eds_eval_runner.py run-level --level object_swap_ood_rbf ... --gpus 0,1,2,3 ... --resume`，说明实验还在跑。此时不要再启动新 runner，只需要监控状态。

如果没有 runner/main.py 进程，使用下面命令恢复：

```bash
python scripts/rdt_eds_eval_runner.py run-level \
  --level object_swap_ood_rbf \
  --episodes 10 \
  --gpus 0,1,2,3 \
  --timeout-seconds 28800 \
  --cached-functions-dir /home/hynx/VLA-Pilot++/outputs/libero/2026-06-04_13-21-01/episode_1/vlm_agent \
  --offline-vlm \
  --resume
```

`--resume` 会跳过已经 valid 的 job，并继续 pending/invalid/running-stale job。

## 6. 监控命令

查看状态 CSV：

```bash
python - <<'PY'
import csv
from collections import Counter
from pathlib import Path

rows = list(csv.DictReader(open('docs/03_evidence/eds_init_pg_diverse_sampling/rdt_eds_eval_status.csv')))
print('status', dict(Counter(r.get('status','') for r in rows)))
print('done_success_counts', dict(Counter(r.get('success_count','') for r in rows if r.get('status') == 'done')))

root = Path('outputs/ood_eval')
for r in rows:
    if r.get('status') == 'running':
        d = root / r['job_id']
        print('running', r.get('gpu'), r['job_id'], 'videos', sum(1 for _ in d.glob('episode_*/*.mp4')), 'results', (d / 'results.txt').exists())

for r in rows:
    if r.get('status') == 'failed':
        print('failed', r.get('gpu'), r['job_id'], r.get('success_count'), r.get('failure_reason'))
PY
```

查看磁盘：

```bash
du -sh outputs/ood_eval
df -h .
```

查看 GPU：

```bash
nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv,noheader,nounits
```

## 7. 剩余工作

从快照看，剩余：

```text
running: 4 jobs
pending: 48 jobs
failed: 1 known invalid job
```

主要剩余是 `rt1to1` 的后半段 sweep：

```text
renoise_t_max=1
rollout_diversity_scale: current at 5, then 10/15/20
rollout_diversity_start_ratio: continuing from 0.8 for scale=5, then later scales
rollout_diversity_iters: [1, 3, 6, all]
```

让 runner 跑到满足：

```text
done + failed = 257
running = 0
pending = 0
```

如果出现新的 failed/invalid job，不要停掉全部实验；记录 failure reason，让 runner 继续剩余 jobs。

## 8. 完成后生成报告

全部 job 都 done/failed 后，生成 object_swap OOD RBF 报告：

```bash
python scripts/rdt_eds_eval_runner.py write-object-swap-ood-rbf-report --episodes 10
```

生成最终汇总报告：

```bash
python scripts/rdt_eds_eval_runner.py write-final-report
```

预期报告路径：

```bash
docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-12-libero-pro-object-swap-rdt-eds-rbf-report.md
docs/03_evidence/eds_init_pg_diverse_sampling/rdt_eds_final_evaluation_report.md
```

报告必须包含：

- 新增 257-job 矩阵的完整结果表
- 引用的 `rdt_unguided` / `eds_iid_baseline` Level-4 baseline
- Top-K RBF rollout 参数
- strict perturbation validity gate
- failed/invalid job 列表和 failure reason
- qualitative artifact / video / metrics 完整性统计

## 9. 完成前验证

确认无遗留 runner/main.py：

```bash
ps -eo pid,ppid,pgid,stat,etime,cmd | rg 'rdt_eds_eval_runner|python main.py|conda run -n vla-pilot' | rg -v rg || true
```

确认 complete jobs 有 `results.txt`、10 个视频、Hydra config、strict perturbation override。runner 的 validity gate 会在 status/report 中检查这些条件。

建议至少跑 runner/report 相关测试：

```bash
pytest tests/test_eds_eval_runner.py -q
```

如果时间允许，再跑相关回归测试：

```bash
pytest \
  tests/test_rdt_steer.py \
  tests/test_eds_eval_metrics.py \
  tests/test_eds_eval_runner.py \
  tests/test_eds_mechanism_pretest_vis.py \
  tests/test_main_rdt_startup.py \
  -q
```

## 10. 已知注意事项

1. 当前 runner 是在 Codex exec session 中启动的。如果切换账号后进程消失，不要惊慌，直接用 `--resume` 命令恢复。
2. 不要启动重复 runner。一定先 `ps` 检查。
3. GPU 限制仍是只用 `0,1,2,3`。
4. 已知 failed job `rt4to1_rollrbf_s5_start06_iterall` 的问题是视频不完整 `9/10`，最终报告要显式写出，不能计入 valid success。
5. Status CSV 可能在 runner 被打断时留下 stale `running` 行；`--resume` 会重新验证 output dir 并继续。
6. 当前结果中有效非零 success 仍然很少，最终分析时要区分 valid success 与 invalid success。
