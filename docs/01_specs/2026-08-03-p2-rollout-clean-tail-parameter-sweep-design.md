# P2 Rollout RBF 参数 Sweep 与 Clean-Tail 补充实验设计

日期：`2026-08-03`

状态：`Approved for execution`

## 1. 摘要

本实验以 `p2_stage_on` 为唯一算法基线，在 LIBERO-PRO `libero_object_swap` OOD benchmark 的同一套 10 个 tasks 上，评估 truncated rollout 的 renoise 强度、RBF scale 和 RBF start ratio 对成功率、方向多样性及动作幅值的影响；随后只在参数 sweep 中预注册选出的唯一最优配置上增加 `rollout_diversity_skip_final_steps=1`，验证保留一个 policy-only clean denoise tail 是否能够抑制 P2 在 EDS iter 1 之后的系统性 population 扩张。

实验严格分为两个阶段：

1. **Phase A：参数 sweep。** 固定 `rollout_diversity_skip_final_steps=0`，完整运行 `renoise_t_max x rollout_diversity_scale x rollout_diversity_start_ratio` 的 12 个参数 jobs，并额外重跑 1 个原始 P2 baseline control。
2. **Phase B：clean-tail 单因素补充实验。** Phase A 全部完成并通过 validity audit 后，按本文预声明规则冻结唯一 winner；只复制该 winner 的完整配置，并将 `rollout_diversity_skip_final_steps` 从 `0` 改为 `1`，运行 1 个 clean-tail job。

正式实验共 `14 jobs / 140 episodes`。Phase B 不得与 Phase A 同时启动，也不得根据 Phase B 中间结果重新选择 winner 或追加其他 clean-tail 组合。

本轮不修改 initial RBF、EPS-CoT reward、parent weighting、population size、EDS iteration 数、Stage Recognition 或其他 P2 组件语义。重点是先获得干净的参数主效应，再单独判断 clean-tail 机制的增量效果。

## 2. 背景与问题定义

### 2.1 P2 baseline

本实验中的 `p2_stage_on` 与既有 `p2_legacy_stage_on_rerun` 语义一致：

- `population_size=16`，每个 action chunk 固定执行 10 轮 EDS refinement；
- initial sampler 使用 RBF-diverse full denoise，`scale=20`、`start_ratio=0.8`；
- truncated rollout 使用 fixed RBF，`scale=20`、`start_ratio=0.6`、`iters=all`；
- renoise schedule 为 `3 -> 1`；
- legacy parent weighting，`temperature=0.1`；
- 不使用 unchanged elite、k-center anchors、cross-chunk memory 或 adaptive search schedule；
- action execution horizon 固定为 8；
- `use_vlm_stage_recognition=true`，episode budget 为 720 steps。

既有配对结果中，P2 Stage ON 达到 `3/10`，成功 tasks 为 `{3, 8, 9}`，但没有达到 `>=5/10` 的工程目标。机制 trace 显示，原始 P2 在 iter 1 后存在系统性扩张：selected EEF trajectory length 和最大相邻位移显著高于 iter 0，中间轮次已找到的更优候选也经常在后续 rollout 中丢失。

### 2.2 Clean-tail 动机

当前 fixed rollout RBF 使用：

```text
rbf_step_count = ceil(n_trunc_steps * rollout_diversity_start_ratio)
```

原始 P2 的 `rollout_diversity_skip_final_steps=0`。当 `n_trunc_steps=2`、`start_ratio=0.6` 时，两个 denoise steps 都施加 RBF；当 `n_trunc_steps=1` 时，唯一 denoise step 也施加 RBF。因此 iter 1 之后经常没有 policy-only denoise step 将候选拉回正常的 RDT action manifold 附近。

`rollout_diversity_skip_final_steps=1` 的设计意图是保留 RBF 提供的方向和 mode coverage，同时强制每个 truncated rollout 的最后一步只使用 policy prior。对于 `n_trunc_steps=1`，这意味着该轮不施加 rollout RBF，而不是在唯一一步中同时要求 diversity 和 cleanup。

## 3. 研究问题与假设

### 3.1 主要研究问题

1. 在 P2 Stage ON 下，`renoise_t_max=3` 与 `2` 哪一个能更好平衡搜索范围和动作稳定性？
2. `rollout_diversity_scale=5/10/15` 是否能在保留方向覆盖的同时降低轨迹长度和单步位移？
3. `rollout_diversity_start_ratio=0.4/0.6` 对短 rollout 中的 RBF step 数和 OOD 成功率有何影响？
4. 在 Phase A 最优配置上增加一个 clean denoise tail，是否能进一步减少过度扩张、碰撞、目标推远和 qpos 异常，并保持或提高成功率？

### 3.2 假设

- H1：相较原始 P2 的 `scale=20`，中等 `scale=10/15` 能显著降低 selected trajectory length 和 max-step displacement，而不会完全消除方向 diversity。
- H2：`renoise_t_max=3` 提供更强的首轮探索，`renoise_t_max=2` 更接近局部 refinement；两者对 success 与 safety 的影响需要由同一任务集配对确定。
- H3：Phase B 的 clean-tail 配置应显著降低 iter 1 后的 population/selected-action expansion，并减少碰撞型失败。
- H4：如果 clean-tail 降低绝对 EEF pairwise distance，但 normalized direction diversity 保持，则应解释为成功限制幅值，而不是 diversity mechanism 失效。

## 4. 实验控制原则

### 4.1 两阶段隔离

Phase A 只测试以下三个变量：

```yaml
renoise_t_max: [3, 2]
rollout_diversity_scale: [5, 10, 15]
rollout_diversity_start_ratio: [0.4, 0.6]
```

Phase A 的所有 12 个 sweep jobs 必须固定：

```yaml
renoise_t_min: 1
rollout_diversity_skip_final_steps: 0
```

Phase B 只允许一个变量变化：

```yaml
rollout_diversity_skip_final_steps: 0 -> 1
```

Phase B 的 `renoise_t_max`、scale、start ratio、seed、task 顺序和其他全部配置必须逐字段复制 Phase A winner。

### 4.2 P2 baseline rerun

Phase A 额外运行一次原始 P2 baseline，用于控制当前代码版本、当前 runner、VLM stage query 波动和基础设施变化：

```yaml
renoise_t_max: 3
renoise_t_min: 1
rollout_diversity_scale: 20
rollout_diversity_start_ratio: 0.6
rollout_diversity_iters: all
rollout_diversity_skip_final_steps: 0
```

该 control 参与报告中的 baseline 对比，但不进入 Phase A winner 候选集合。Phase B winner 必须从 12 个 sweep jobs 中选出，避免把“原始 P2 + clean tail”与“前三个参数最优 + clean tail”混为一谈。

### 4.3 不允许的变更

本轮不得同时修改：

- initial RBF scale 或 start ratio；
- `rollout_diversity_iters=all`；
- parent weighting、ESS、k-center、elite carryover；
- cross-chunk memory；
- adaptive RBF controller 或 adaptive search schedule；
- population size、CEM iterations 或 execution horizon；
- EPS-CoT reward、VLM prompt、Stage Recognition state machine；
- RDT checkpoint、scheduler inference steps、128D action layout。

任何上述变更都需要新的设计和独立消融，不得加入本轮结果驱动的追加 sweep。

## 5. 固定实验设置

### 5.1 Benchmark

| 项目 | 固定设置 |
|---|---|
| Benchmark | LIBERO-PRO OOD Evaluation |
| Suite | `libero_object_swap` |
| Strict perturbation | `backend.libero.strict_perturbations=true` |
| Tasks / episodes per job | 同一套 10 tasks，每个 task 1 episode |
| Max episode steps | `720` |
| Root seed | `0` |
| Policy | 与 P2 Stage ON 既有实验相同的 RDT EMA checkpoint |
| Guidance | EDS + cached EPS-CoT reward |
| Stage Recognition | ON |
| Gemini grounding | OFF |
| Action horizon | `8` |

沿用既有配对 episode seeds：

| Task | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Episode seed | 44 | 235 | 43 | 546 | 6 | 621 | 197 | 87 | 151 | 548 |

每个 job 必须在 metadata 中实际记录 task/episode seed，不得仅依赖设计文档声明。

### 5.2 固定 EDS 与 initial sampler

```yaml
population_size: 16
cem_iters: 10
use_cem: false
num_elites: 16
temperature: 0.1

initial_sampling_mode: rbf_diverse_denoise
initial_diversity_scale: 20.0
initial_diversity_start_ratio: 0.8

truncated_rollout_mode: rbf_diverse
rollout_diversity_control_mode: fixed
rollout_diversity_iters: all

parent_weighting_mode: legacy_temperature
parent_coverage_mode: none
elite_carryover_count: 0
chunk_population_mode: fresh
search_schedule_mode: legacy_linear
```

`num_elites=16` 在 `use_cem=false` 下不表示 16 个 elite 被保留；本轮仍不启用 deterministic elite carryover。

### 5.3 Stage Recognition

保持既有 P2 Stage ON 的 VLM model、temperature、query limit、cached guidance、trigger 和 fallback 语义。API credential 只能通过进程环境变量注入，不得写入 Hydra config、overrides、runner manifest、日志、报告或 Git。

由于 Stage Recognition 使用外部 API，即使 temperature 为 0，也必须记录：

- query success/error/parse-failure count；
- first guidance-OFF step；
- guidance OFF/ON transitions；
- 实际 guided chunk count；
- query latency。

这些字段用于识别 stage 时序差异造成的实验混杂，不用于事后排除失败 episode。

## 6. Phase A 参数 Sweep

### 6.1 矩阵规模

```text
2 renoise_t_max
x 3 rollout scales
x 2 start ratios
= 12 sweep jobs
```

加上 1 个 P2 baseline rerun：

```text
Phase A = 13 jobs = 130 episodes
```

### 6.2 Job 命名

```text
p2_param_rt{3|2}to1_s{5|10|15}_start{04|06}_skip0
p2_stage_on_baseline_rerun_rt3to1_s20_start06_skip0
```

例如：

```text
p2_param_rt3to1_s10_start04_skip0
p2_param_rt2to1_s15_start06_skip0
```

### 6.3 Start Ratio 的离散语义

Phase A 未启用 clean-tail，因此 `0.4` 与 `0.6` 并非完全等价：

| `n_trunc_steps` | start 0.4 | start 0.6 |
|---:|---:|---:|
| 3 | 2 RBF steps | 2 RBF steps |
| 2 | 1 RBF step | 2 RBF steps |
| 1 | 1 RBF step | 1 RBF step |

因此：

- 对 `rt3->1`，start ratio 的差异主要作用于中间的 `n_trunc=2` iterations；
- 对 `rt2->1`，差异主要作用于首个 `n_trunc=2` iteration；
- 在 `n_trunc=1` 的后期，两者都让唯一 denoise step 使用 RBF。

报告必须基于实际 `rollout_rbf_steps_by_iter` 解释 start ratio，不能把名义浮点配置直接当作连续强度。

## 7. Phase A Winner 选择与冻结

### 7.1 Eligibility

进入 winner ranking 的 job 必须：

- 完成 10/10 episodes；
- 有可解析的 `results.txt`；
- 有 10 个可读 episode videos；
- strict perturbation 和 suite 均验证通过；
- Hydra config/overrides、metrics、qualitative artifacts、job log 完整；
- 无普通 LIBERO fallback；
- 无 silent algorithm fallback；
- nonfinite count 为 0；
- action-mask violation 为 0。

P2 baseline rerun 只作为 control，不参与 ranking。

### 7.2 预声明排序规则

对 12 个 eligible sweep jobs 按以下顺序排序，直到产生唯一 winner：

1. success count 降序；
2. 对 P2 baseline 成功 tasks `{3, 8, 9}` 的保留数降序；
3. execution/qpos error episode 数升序；
4. collision/push/drop 失败 episode 数升序，分类规则必须在看结果前固定；
5. `selected_max_step_displacement` 的跨 chunk P95 升序；
6. `selected_trajectory_length` 的跨 chunk P95 升序；
7. `eef_direction_diversity_final` 中位数降序；
8. `select_action_latency_s` 中位数升序；
9. method label 字典序升序，作为最终确定性 tie-breaker。

不得使用单个好看视频、单个 chunk 的 reward、未预声明指标或 Phase B 结果重新选择 winner。

### 7.3 Immutable Winner Manifest

Phase A 全部完成后生成只读 winner manifest，至少记录：

- 12 个 candidate jobs 的状态和 ranking 字段；
- winner method label；
- winner 完整 Hydra overrides；
- `results.txt`、metrics 和 config 的 checksum；
- ranking rule version；
- 生成时间和 source report path；
- Phase B 唯一允许变化的字段。

Phase B runner 必须读取 manifest 生成 job，禁止手工重新录入 winner 参数。

## 8. Phase B Clean-Tail 单因素实验

### 8.1 唯一改动

```yaml
rollout_diversity_skip_final_steps: 0 -> 1
```

其余字段逐项继承 Phase A winner。命名：

```text
<phase_a_winner_label>_cleantail_skip1
```

Phase B 规模：

```text
1 job = 10 episodes
```

总实验规模：

```text
13 Phase A jobs + 1 Phase B job
= 14 jobs / 140 episodes
```

### 8.2 Clean-Tail 预期 step mask

| `n_trunc_steps` | start 0.4 | start 0.6 |
|---:|---:|---:|
| 3 | 2 RBF + 1 clean | 2 RBF + 1 clean |
| 2 | 1 RBF + 1 clean | 1 RBF + 1 clean |
| 1 | 0 RBF + 1 clean | 0 RBF + 1 clean |

Phase B 中，最后一个 local denoise step 必须在每轮 trace 中明确标记为 `rbf_applied=false`。`n_trunc=1` 时 `rollout_diversity_steps_applied=0` 是预期语义，不应被误判为 fallback。

## 9. Metrics 设计

### 9.1 保留全部现有 Metrics

继续记录已有：

- initial/rollout EEF diversity before、after phase、final 和 retention；
- endpoint spread before、after phase、final；
- per-iteration best/mean reward、target distance、score entropy；
- population diversity、parent rank、unique parent ratio；
- initial/rollout fallback、nonfinite 和 action-mask violation；
- initial sampler、EDS loop 和 total `select_action` latency；
- Stage Recognition query、transition 和 guidance ON/OFF 指标；
- per-task success、episode steps 和 failure reason。

### 9.2 新增幅值与方向 Metrics

为回答“保留 mode diversity 但限制动作幅度”，必须新增：

| Metric | 计算方式 / 含义 |
|---|---|
| `rollout_rbf_steps_by_iter` | 每轮实际 RBF step indices、count 和 final-step flag |
| `selected_trajectory_length_by_iter` | selected EEF trajectory 相邻点距离之和 |
| `population_trajectory_length_mean/p90/max_by_iter` | population 路径长度分布 |
| `selected_max_step_displacement_by_iter` | selected trajectory 最大相邻 EEF 位移 |
| `population_max_step_mean/p90/max_by_iter` | population 单步位移分布 |
| `trajectory_length_expansion_ratio_by_iter` | 相对 iter 0 selected/population length 的比值 |
| `max_step_expansion_ratio_by_iter` | 相对 iter 0 max-step 的比值 |
| `eef_direction_diversity_by_iter` | 对相对起点的 EEF displacement 归一化后计算 pairwise direction spread |
| `endpoint_direction_spread_by_iter` | normalized endpoint displacement 的角度/余弦分散度 |
| `chunk_boundary_action_jump` | 当前 selected first action 与上一 chunk 最后执行 action 的 translation 差 |
| `gripper_qpos_violation_count` | observation qpos 超出 nominal range/容差的次数 |

方向指标必须对近零 displacement 使用显式 epsilon 和 valid-count；无有效方向样本时记录 warning/invalid metric，不得静默填 0。

### 9.3 聚合方式

每个 job 同时报告：

- all guided chunks 的 mean、median、P90、P95 和 max；
- EDS iter 0、1、last 的配对变化；
- success episodes 与 failure episodes 的分层统计；
- task-level paired delta；
- guidance 首次关闭前后的统计边界。

Stage ON 会改变实际 EDS chunk 数，因此不同 job 的 raw chunk count 必须一并报告，不能仅比较未经加权的全局均值。

## 10. Qualitative Artifacts 与失败分类

### 10.1 每个正式 Job

沿用前一轮 P2 OOD 实验的完整 artifact 标准：

- 10 个 per-episode videos；
- 每个被跟踪 chunk 的 initial RBF before/after/final；
- rollout RBF before/after/final；
- 10 轮 population cloud 和 selected trajectory；
- reward、target distance、absolute diversity 曲线；
- trajectory length、max-step 和 direction diversity 曲线；
- final selected vs initial best；
- Stage/guidance timeline；
- Hydra config、overrides、metrics JSONL、results 和完整 log。

Phase A winner 与 Phase B clean-tail 必须额外生成相同坐标轴、相同视角、相同 chunk 的 side-by-side 对比图。

### 10.2 预声明失败类别

视频主失败类型固定为：

1. no target acquisition；
2. target pushed away；
3. target dropped after grasp；
4. basket displaced/collision；
5. clutter swept/wrong-object interaction；
6. unstable transport；
7. placement/release failure；
8. premature guidance OFF；
9. guidance oscillation；
10. qpos/execution error；
11. timeout without task completion。

每个 episode 只指定一个 primary failure，可附 secondary tags。分类表必须在 Phase A winner ranking 前完成，避免根据 clean-tail 结果调整分类口径。

## 11. Storage 与软链接

### 11.1 实际存储位置

所有大体积实验产物实际保存到：

```text
/mnt/data/shared2/zhuoli/output/p2_rollout_clean_tail_sweep
```

包括：

- job output directories；
- videos；
- qualitative PNG/NPZ/PT；
- metrics、Hydra config 和 overrides；
- runner logs、manifests、retry/failure records；
- Phase A ranking data 和 immutable winner manifest；
- 临时实验缓存及报告生成中间文件。

worktree 中的路径：

```text
/home/hynx/VLA-Pilot++/.worktrees/exp/eds-init-pg-diverse-sampling/outputs/ood_eval/p2_rollout_clean_tail_sweep
```

必须是指向上述 shared2 目录的软链接，不能是真实输出目录。

设计文档和最终 Markdown evidence report 体积很小，继续保存在 Git 管理的 `docs/` 中；报告中的 output 链接统一使用 worktree 软链接路径，便于现有 runner 和审查工具兼容。

### 11.2 Storage Preflight

当前 `/mnt/data/shared2/zhuoli/output` 尚未创建。正式运行前必须：

1. 检查 `/mnt/data/shared2/zhuoli` 可写；
2. 安全创建 `/mnt/data/shared2/zhuoli/output/p2_rollout_clean_tail_sweep`；
3. 确认 shared2 可用空间不少于 `50 GiB`；
4. 确认 worktree link path 不存在真实文件/目录；若已存在，禁止覆盖并先人工审计；
5. 创建绝对软链接并用 `readlink -f` 验证目标；
6. 创建最小 probe file 验证从软链接写入的数据实际落在 shared2，然后删除 probe；
7. 确认 runner 的所有 output/log/cache 参数均在软链接根目录下。

不得把既有 `outputs/ood_eval` 内容移动到 shared2，也不得覆盖任何历史实验目录。

## 12. GPU、Runner 与 Resume

### 12.1 GPU

- 优先使用 GPU `2、3、4、5` 中当前空闲的设备；
- 最多 4 个并行 workers；
- 启动前检查显存、利用率和现有进程，不抢占其他任务；
- Phase A 的 13 个 jobs 可在空闲 GPU 上并行；
- Phase B 只能在 Phase A 完成并冻结 winner 后启动。

### 12.2 Runner

复用或扩展现有 `scripts/rdt_eds_eval_runner.py`，不得使用一次性散乱 shell 命令。Runner 必须支持：

- `--resume`；
- Phase A 13-job manifest；
- Phase A candidate-only winner ranking；
- immutable winner manifest；
- Phase B 从 winner manifest 自动派生；
- 单 job failure 不终止整个 Phase A；
- retry 与明确 failure reason；
- output validity audit；
- symlink root 与真实 shared2 target 双重记录。

已经 complete 且 validity 全部通过的 job 不得重复运行。Exit code 为 0 但结果、视频、strict config 或 artifacts 不完整时仍判定为 invalid。

## 13. Validity Gate

每个 complete job 必须满足：

- `results.txt` 可解析；
- 10/10 episodes 均有有效结果；
- 10 个视频均可被 `ffprobe` 读取；
- `.hydra/config.yaml` 和 `.hydra/overrides.yaml` 存在；
- strict LIBERO-PRO perturbation 与 `libero_object_swap` suite 已验证；
- EDS metrics、Stage events、qualitative artifacts 和 logs 完整；
- 配置中的 task order、episode seeds、720-step budget 和 P2 固定项正确；
- 无普通 LIBERO fallback；
- nonfinite count 为 0；
- action-mask violation 为 0；
- API credential 未出现在任何序列化文件中；
- output realpath 位于 `/mnt/data/shared2/zhuoli/output/p2_rollout_clean_tail_sweep`。

Phase B 还必须验证：

- job config 除 `rollout_diversity_skip_final_steps` 外与 winner 完全一致；
- 每轮最后一个 denoise step 无 RBF；
- `n_trunc=1` 时 RBF step count 为 0；
- 0 RBF steps 不被记录为 fallback。

## 14. 成功判据与分析计划

### 14.1 主要工程 Gate

```text
同一套 10 个 libero_object_swap tasks 达到 >=5/10。
```

同时报告：

- 是否保留 P2 baseline 成功 tasks `{3,8,9}`；
- 是否发现新的成功 tasks；
- Phase A winner 相对 baseline rerun 的 paired delta；
- Phase B clean-tail 相对 Phase A winner 的 paired delta。

### 14.2 Mechanism/Safety Gate

Phase B 相对 Phase A winner 期望满足：

- iter 1 selected trajectory length expansion 明显下降；
- iter 1 selected max-step expansion 明显下降；
- population length/max-step P95 不劣化；
- normalized EEF direction diversity 至少保留 winner 的主要水平；
- target pushed away、drop、basket collision、clutter sweep 不增加，理想情况下减少；
- qpos/execution error 为 0；
- selected reward 和 final target distance 不发生明显系统性退化。

由于每个配置只有 10 个 episodes，本轮结论属于工程 gate 和任务级配对证据，不宣称统计显著性。成功率相同的配置必须依据预声明 tie-breaker 排序，禁止事后挑选。

## 15. 报告与交付物

最终报告建议路径：

```text
docs/03_evidence/eds_init_pg_diverse_sampling/
2026-08-03-p2-rollout-clean-tail-parameter-sweep-report.md
```

报告至少包含：

1. benchmark、policy、strict perturbation、任务与 seed；
2. shared2 实际存储路径和 worktree 软链接验证；
3. Phase A 13 个 jobs 的完整结果和 validity；
4. 三个 sweep 参数的主效应与交互分析；
5. start ratio 到实际 RBF step mask 的映射；
6. Phase A winner ranking 和 immutable manifest；
7. Phase B clean-tail 与 winner 的逐 task A/B；
8. absolute diversity、direction diversity、trajectory length、max-step 和 latency 分析；
9. 所有视频失败分类及代表性定性对比；
10. P2 historical `3/10`、本轮 baseline rerun、Phase A winner 和 Phase B 的完整 SR 表；
11. 是否达到 `>=5/10`，以及是否值得继续进行算法机制修改或多 seed 复验；
12. failed/invalid jobs、fallback、qpos error 和残余风险。

最终运行摘要必须确认：

- `14/14` jobs 均为 complete，或有明确 failure reason；
- Phase A winner 只从 12 个 sweep jobs 中选择；
- Phase B 只运行 winner 的 `skip0 -> skip1` 单因素变体；
- 所有 complete jobs 有 10 个视频；
- 所有真实输出均位于 shared2；
- runner/main 实验进程已结束；
- 最终报告已生成且引用路径可访问。

## 16. 风险与解释边界

1. **Stage Recognition 外部 API 波动。** 相同 seed 不保证 stage query 完全一致，必须联合报告 first-OFF step、guided chunks 和 query errors。
2. **参数 winner 的小样本不稳定。** `n=10` 的 winner 可能受单 task 随机性影响；达到 gate 后仍建议多 seed 复验。
3. **降低 scale 可能减少 mode coverage。** 必须同时看 normalized direction diversity，不能只看绝对轨迹长度。
4. **Clean-tail 可能过度回归 prior。** 如果动作幅值下降但新成功 mode 消失，应判为 safety/exploration trade-off，而不是无条件成功。
5. **qpos 越界并非 RBF 的直接 gripper-channel 修改。** RBF 只直接作用 translation；qpos error 可能由碰撞动力学、observation tolerance 或 stage 时序间接引起，需单独记录。
6. **Start ratio 是离散 step mask。** 其效果依赖 `n_trunc_steps`，不能按连续超参数解释。
7. **磁盘路径风险。** worktree 输出只能是软链接；任何写入 home 实体目录的 runner 配置都必须在正式运行前修复。

## 17. 审查决策点

本设计请求确认以下内容：

1. Phase A 按 12 个参数 jobs 加 1 个 P2 baseline rerun执行；
2. Phase A 所有 jobs 固定 `skip_final_steps=0`；
3. Phase B 仅对 Phase A winner 设置 `skip_final_steps=1`；
4. P2 baseline rerun 不参与 winner ranking；
5. winner 使用本文预声明的九级 tie-breaker；
6. 正式总规模为 `14 jobs / 140 episodes`；
7. 大体积输出实际保存到 `/mnt/data/shared2/zhuoli/output/p2_rollout_clean_tail_sweep`，worktree 只保留软链接；
8. 在正式运行前补齐幅值、方向和 clean-tail step-mask metrics，不修改 P2 算法核心语义。
