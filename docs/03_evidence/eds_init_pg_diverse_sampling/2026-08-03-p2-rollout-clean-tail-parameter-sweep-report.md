# P2 Rollout RBF 参数 Sweep 与 Clean-Tail 补充实验报告

日期：`2026-08-03`（正式运行跨越至 `2026-08-04 UTC`）

执行状态：`Completed within approved scope`

结果 gate：`FAIL`（Phase B 为 `0/10`，未达到 `>=5/10`）

## 1. 结论摘要

本轮严格执行了已批准设计中的 `14 jobs / 140 episodes`：Phase A 包含 12 个参数 sweep jobs 与 1 个不参与 winner ranking 的 P2 baseline rerun；Phase A 全部完成并通过 audit 后，按预注册九级 tie-breaker 冻结唯一 winner manifest；Phase B 从该 manifest 自动派生，只将 `rollout_diversity_skip_final_steps` 从 `0` 改为 `1`，运行唯一 10-episode clean-tail job。没有根据中间或最终结果追加 sweep。

主要结论如下：

- P2 baseline rerun 达到 `3/10`，成功 tasks 为 `{3, 8, 9}`；12 个 sweep 中最优原始成功数为 `2/10`，因此参数 sweep 没有超过 baseline。
- Phase A 唯一 winner 为 `p2_param_rt2to1_s5_start04_skip0`：`renoise 2→1 / scale 5 / start 0.4 / iters all / skip_final 0`，成功 tasks 为 `{8, 9}`。
- Phase B clean-tail 达到 `0/10`，相对 winner 丢失 tasks `{8, 9}`。工程 gate `>=5/10` 未通过。
- clean-tail 机制按设计生效：所有 `n_trunc=1` 的 2790 个 iter 均为 0 个 RBF steps，所有 3100 个 iter 的 final-step RBF applied count 为 0，fallback 为 0。
- 相对 Phase A winner，Phase B 的最终迭代 selected trajectory-length 中位数下降 `68.0%`、selected max-step 中位数下降 `56.2%`，但 EEF direction diversity 中位数同时下降 `68.9%`、endpoint direction spread 中位数下降 `93.3%`。这不是“仅清理尾部而保留方向覆盖”，而是明显的过度收缩。
- Phase B 定性失败以错误对象/杂物交互为主（6/10），说明降低动作幅值并未解决目标身份与抓取/运输语义；按预注册 collision/push/drop composite 口径，winner 的 5/10 反而变为 Phase B 的 7/10。

## 2. 执行依据与冻结控制项

执行依据为 `docs/01_specs/2026-08-03-p2-rollout-clean-tail-parameter-sweep-design.md`，执行前状态已从 `Draft for review` 更新为 `Approved for execution`。实验矩阵、winner 规则和 validity gate 未修改。

固定协议：

- Benchmark：LIBERO-PRO `libero_object_swap`，strict perturbation；
- tasks：`0..9`；episode seeds：`[44, 235, 43, 546, 6, 621, 197, 87, 151, 548]`；
- `max_episode_steps=720`；Stage Recognition ON；Gemini grounding OFF；
- population size `16`，EDS iterations `10`，rollout iters `all`；
- initial RBF `scale=20 / start=0.8`、reward、parent weighting、memory、adaptive controller、execution horizon、RDT checkpoint 和 scheduler inference steps 均保持 P2 原值；
- Stage Recognition 使用运行时环境变量中的真实 credential。credential 未进入命令行、Hydra config、日志、manifest、报告或 Git diff。

## 3. 必要实现与测试

实现只覆盖本实验所需的 metrics、runner、report/validity 支持，并保留已有 metrics：

- `rollout_rbf_steps_by_iter`，包括 per-iter step indices/flags、final-step 标记与 fallback 标记；
- selected/population trajectory length 的 mean/P90/max 和 expansion ratio；
- selected/population max-step displacement 的 mean/P90/max 和 expansion ratio；
- `eef_direction_diversity_by_iter` 与 `endpoint_direction_spread_by_iter`；
- `chunk_boundary_action_jump`；
- `gripper_qpos_violation_count`；
- Phase A/Phase B matrix builder、断点续跑、invalid-job 检测、单 job 重试、九级 deterministic ranking、只读 winner manifest、Phase B 单字段 diff、shared2/credential/视频/strict validity 与报告 writer。

最终相关回归命令覆盖 runner、metrics、RDT steering、Stage Recognition、mechanism trace/visualization 以及 LIBERO action/observation adapter，结果为：

- `pytest`：`749 passed, 1 warning`，耗时 `152.64s`；唯一 warning 为第三方 NetworkX 的 `utcfromtimestamp` 弃用提示；
- `python -m py_compile`：通过；
- `git diff --check`：通过。

测试覆盖了设计要求中的 12+1 矩阵、baseline 排除、九级 tie-breaker、immutable manifest、Phase B 单字段变化、skip=1 final denoise、`n_trunc=1` 零 RBF 且非 fallback、resume/invalid、shared2 realpath/symlink、strict/video/credential scan 和 report writer。

## 4. 存储与可恢复性

- 真实产物根目录：`/mnt/data/shared2/zhuoli/output/p2_rollout_clean_tail_sweep`；
- worktree 兼容路径：`outputs/ood_eval/p2_rollout_clean_tail_sweep`；
- 兼容路径是指向上述 shared2 目标的绝对软链接；`readlink -f` 返回同一 shared2 路径；
- 目标位于 `/dev/sdc1` 的 ext4 可写挂载；最终复核时可用空间约 `4732 GiB`，高于 50 GiB gate；
- probe file 写入与 realpath 检查已验证实际落盘 shared2；videos、qualitative artifacts、metrics、Hydra、logs、manifests、runner state 与 runtime cache 均在 shared2；
- 没有覆盖或移动既有正式输出。一次未产生 episode 的启动期 artifact 与一次同配置保守重试的旧输出均安全归档在 `stale/phase_a/`。

## 5. Phase A 结果

以下 P95 与 direction median 使用预注册 ranking 口径：每个 EDS chunk 的最后一个 iter 值。`Retain` 是相对 baseline 成功 tasks `{3,8,9}` 的保留数，`C/P/D` 是预注册 collision/push/drop composite 计数。

| Rank | Job | rt | Scale | Start | Success tasks | SR | Retain | qpos/error | C/P/D | Max-step P95 | Length P95 | Direction median | Latency median (s) |
| ---: | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `p2_param_rt2to1_s5_start04_skip0` | 2→1 | 5 | 0.4 | `[8, 9]` | 2/10 | 2 | 0 | 5 | 0.01605 | 0.10162 | 3.5444 | 2.037 |
| 2 | `p2_param_rt2to1_s5_start06_skip0` | 2→1 | 5 | 0.6 | `[5, 8]` | 2/10 | 1 | 0 | 4 | 0.01611 | 0.10536 | 3.6297 | 2.031 |
| 3 | `p2_param_rt3to1_s5_start06_skip0` | 3→1 | 5 | 0.6 | `[9]` | 1/10 | 1 | 0 | 6 | 0.01564 | 0.10387 | 3.5600 | 2.517 |
| 4 | `p2_param_rt3to1_s15_start06_skip0` | 3→1 | 15 | 0.6 | `[8]` | 1/10 | 1 | 0 | 6 | 0.03495 | 0.19209 | 3.8547 | 2.496 |
| 5 | `p2_param_rt3to1_s5_start04_skip0` | 3→1 | 5 | 0.4 | `[9]` | 1/10 | 1 | 0 | 7 | 0.01511 | 0.10241 | 3.5340 | 2.456 |
| 6 | `p2_param_rt3to1_s10_start06_skip0` | 3→1 | 10 | 0.6 | `[8]` | 1/10 | 1 | 0 | 7 | 0.02775 | 0.15355 | 3.8120 | 2.512 |
| 7 | `p2_param_rt2to1_s10_start06_skip0` | 2→1 | 10 | 0.6 | `[5]` | 1/10 | 0 | 0 | 6 | 0.02581 | 0.15526 | 3.8332 | 2.048 |
| 8 | `p2_param_rt3to1_s10_start04_skip0` | 3→1 | 10 | 0.4 | `[7]` | 1/10 | 0 | 0 | 8 | 0.02615 | 0.14810 | 3.7635 | 2.461 |
| 9 | `p2_param_rt2to1_s15_start06_skip0` | 2→1 | 15 | 0.6 | `[]` | 0/10 | 0 | 0 | 8 | 0.03608 | 0.21501 | 3.8456 | 2.031 |
| 10 | `p2_param_rt2to1_s15_start04_skip0` | 2→1 | 15 | 0.4 | `[]` | 0/10 | 0 | 0 | 9 | 0.03389 | 0.21165 | 3.8621 | 2.025 |
| 11 | `p2_param_rt3to1_s15_start04_skip0` | 3→1 | 15 | 0.4 | `[]` | 0/10 | 0 | 0 | 9 | 0.03630 | 0.21653 | 3.8350 | 2.463 |
| 12 | `p2_param_rt2to1_s10_start04_skip0` | 2→1 | 10 | 0.4 | `[]` | 0/10 | 0 | 1 | 6 | 0.02863 | 0.15131 | 3.7992 | 2.017 |
| excluded | `p2_stage_on_baseline_rerun_rt3to1_s20_start06_skip0` | 3→1 | 20 | 0.6 | `[3, 8, 9]` | 3/10 | 3 | 0 | 5 | 0.03875 | 0.21200 | 3.8558 | 2.495 |

### 5.1 参数主效应

每个 cell 仅有 10 episodes，以下是工程描述性主效应，不作统计显著性声明。

| 因子 | 水平 | 平均成功数/10 | 平均 C/P/D | 平均 Length P95 | 平均 Max-step P95 | 平均 Direction median |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `renoise_t_max` | 2 | 0.833 | 6.33 | 0.15670 | 0.02610 | 3.7524 |
| `renoise_t_max` | 3 | 0.833 | 7.17 | 0.15276 | 0.02598 | 3.7265 |
| scale | 5 | 1.500 | 5.50 | 0.10332 | 0.01573 | 3.5670 |
| scale | 10 | 0.750 | 6.75 | 0.15206 | 0.02709 | 3.8020 |
| scale | 15 | 0.250 | 8.00 | 0.20882 | 0.03531 | 3.8494 |
| start | 0.4 | 0.667 | 7.33 | 0.15527 | 0.02602 | 3.7231 |
| start | 0.6 | 1.000 | 6.17 | 0.15419 | 0.02606 | 3.7559 |

`renoise_t_max=2/3` 的平均成功数相同；`rt=2` 的主要优势是 median action selection latency 从约 2.484s 降到 2.031s，并略少 composite failures。最清晰的主效应来自 scale：从 5 增至 15 虽提升方向 diversity，却同步放大 length/max-step、增加碰撞/推远/掉落并降低成功数。start 0.6 的均值稍好，但 winner 的 0.4 在相同 2/10 下保留了两个 baseline tasks，因此按预注册规则胜出。

### 5.2 Winner 决策与不可变 manifest

九级 tie-breaker 顺序为：success count 降序、baseline task retention 降序、execution/qpos error 升序、collision/push/drop 升序、final max-step P95 升序、final trajectory-length P95 升序、normalized direction diversity 降序、selection latency 升序、label 字典序。winner 与第二名均为 2/10，但第 2 级 retention 为 `2 > 1`，因此 winner 在第 2 级已确定。

P2 baseline rerun 明确排除在 ranking 之外。manifest 位于 `/mnt/data/shared2/zhuoli/output/p2_rollout_clean_tail_sweep/manifests/phase_a_winner_manifest.json`，权限为 `0444`；manifest 内部 canonical payload hash 为 `cc6217385c7c4b1b8f2065a4bd98dcb8411853e4ef9462a612d6834a3bc67866`，完整文件 SHA-256 为 `528162d4434019cae58cdcc9224059363542169fc8cfd471e304a0e556d6569f`。winner evidence checksums 在加载 manifest 时已复核。

## 6. Phase B 单因素结果

manifest 派生的唯一 Phase B job 为 `p2_param_rt2to1_s5_start04_skip0_cleantail_skip1`。与 winner 的完整 profile diff 恰好为：

```text
rollout_diversity_skip_final_steps: 0 -> 1
```

其余 profile 字段、tasks、seeds、benchmark 与代码状态均一致。结果为 `0/10`，10 个 episodes 均完成并有可读视频。

机制 gate 全部满足：

- 310 个 EDS chunks，共 3100 个 iter；
- 每个 chunk 的 iter 0 为 `n_trunc=2`，只在 step 0 施加 RBF；
- 2790 个 `n_trunc=1` iter 全部为 `step_count=0`；
- `final_step_rbf_applied=0`，`fallback=0`；
- nonfinite、action-mask violation、qpos violation 均为 0。

因此 Phase B 失败不是配置未生效，而是该 clean-tail 语义在 `renoise 2→1` 下使 90% iter 完全没有 rollout RBF，过度削弱了方向搜索。

## 7. Task-Level SR 对比

| Task | Seed | P2 baseline | Phase A winner | Phase B clean-tail |
| ---: | ---: | --- | --- | --- |
| 0 | 44 | fail | fail | fail |
| 1 | 235 | fail | fail | fail |
| 2 | 43 | fail | fail | fail |
| 3 | 546 | success | fail | fail |
| 4 | 6 | fail | fail | fail |
| 5 | 621 | fail | fail | fail |
| 6 | 197 | fail | fail | fail |
| 7 | 87 | fail | fail | fail |
| 8 | 151 | success | success | fail |
| 9 | 548 | success | success | fail |
| **总计** | — | **3/10** | **2/10** | **0/10** |

Phase A winner 相比 baseline 没有新增成功 task，只保留 `{8,9}` 并丢失 task 3；Phase B 再丢失 `{8,9}`。所以任何轨迹稳定性改善都没有转化为 task-level SR 收益。

## 8. Trajectory、Max-Step 与 Direction Diversity

下表统一使用每个 EDS chunk 的最终 iter；P95/median 在 chunks 上聚合。Expansion ratio 相对该 chunk 的 iter 0。

| Metric | P2 baseline | Phase A winner | Phase B clean-tail | Phase B vs winner |
| --- | ---: | ---: | ---: | ---: |
| selected trajectory length median | 0.09255 | 0.07076 | 0.02262 | -68.0% |
| selected trajectory length P95 | 0.21200 | 0.10162 | 0.07257 | -28.6% |
| population trajectory mean median | 0.14178 | 0.06757 | 0.02113 | -68.7% |
| population trajectory mean P95 | 0.15178 | 0.08113 | 0.06744 | -16.9% |
| selected max-step median | 0.01463 | 0.01098 | 0.00481 | -56.2% |
| selected max-step P95 | 0.03875 | 0.01605 | 0.00981 | -38.9% |
| population max-step mean median | 0.02411 | 0.01054 | 0.00430 | -59.2% |
| population max-step mean P95 | 0.02596 | 0.01184 | 0.00927 | -21.7% |
| selected length expansion median | 1.401 | 1.453 | 0.504 | -65.3% |
| population length expansion median | 2.103 | 1.466 | 0.636 | -56.6% |
| selected max-step expansion median | 1.524 | 1.491 | 0.703 | -52.8% |
| population max-step expansion median | 2.476 | 1.471 | 0.778 | -47.1% |
| EEF direction diversity median | 3.8558 | 3.5444 | 1.1039 | -68.9% |
| endpoint direction spread median | 1.0136 | 0.8336 | 0.0556 | -93.3% |

Phase A winner 已将 baseline 的 absolute trajectory 与 max-step 明显压低，同时只中度降低方向覆盖；这是 scale 5 的主要机制收益。Phase B 则把 final expansion ratios 全部压到 1 以下，但方向 diversity 与 endpoint spread 的跌幅远大于期望。H3 中“抑制扩张”成立，H4 所要求的“normalized direction diversity 保持”不成立；综合 SR，应判定 clean-tail 对该短 rollout 过强。

Chunk-boundary action jump 中位数从 baseline `1.4116` 降至 winner `0.9535`，Phase B 进一步降至 `0.1035`（相对 winner `-89.1%`）。这再次表明动作变平滑，但“更平滑”没有等价于“更正确”。

## 9. 失败类型与定性证据

每个 episode 均用相同时间坐标的 agent-view contact sheet 复核。primary failure counts 为：

| Primary outcome | P2 baseline | Phase A winner | Phase B clean-tail |
| --- | ---: | ---: | ---: |
| success | 3 | 2 | 0 |
| no target acquisition | 2 | 3 | 3 |
| target pushed away | 2 | 2 | 0 |
| target dropped after grasp | 0 | 2 | 1 |
| basket displaced/collision | 2 | 1 | 0 |
| clutter swept/wrong-object interaction | 1 | 0 | 6 |

Phase B 确实减少了大幅推远和篮筐位移的 primary failures，但错误对象/杂物交互从 0 增至 6。按设计中 composite categories（包含 wrong-object interaction、push、drop、basket collision），baseline/winner/Phase B 分别为 `5/5/7`。这说明 clean-tail 主要改变了失败形态，而非解决目标语义、抓取稳定性或放置条件。

定性证据位于 shared2 的 `analysis/contact_sheets/<job>/`；完整逐 episode 分类位于 `analysis/failure_classifications.json` 与 `analysis/phase_b_failure_classifications.json`。Phase B 的主要可见模式包括：目标未稳定获取 3、邻近物体被扫动或错误物体被运输 6、目标到达篮筐边缘后掉落 1。collision/push/drop/qpos 之外，没有证据把单一 episode 的 primary failure 归因为 Stage guidance premature-OFF；但 Stage 的 OFF→ON 反转仍提示存在 guidance oscillation 风险。

## 10. Latency 与 Stage Recognition

| Method | EDS action latency median / P95 (s) | Stage events | Query OK / error | Stage query latency median / P95 (s) | Guidance ON→OFF / OFF→ON |
| --- | ---: | ---: | ---: | ---: | ---: |
| P2 baseline | 2.495 / 2.594 | 127 | 107 / 20 | 4.140 / 5.247 | 32 / 22 |
| Phase A winner | 2.037 / 2.173 | 130 | 103 / 27 | 4.236 / 5.328 | 28 / 19 |
| Phase B clean-tail | 1.871 / 1.941 | 92 | 78 / 14 | 4.174 / 5.212 | 24 / 16 |

winner 相对 baseline 降低 action selection latency；Phase B 相对 winner 再降低约 `8.2%`，符合 RBF step 减少的预期。Stage API latency 三组相近，parse/query error 通过既有 fail-safe 处理并保留在完整 stage events 中；它们未触发 validity failure，但仍是复现实验的外部服务噪声。credential health check 通过且未回显 token。

## 11. Validity Audit

最终逐 job 重审结果：

- Phase A：`13/13 valid`，`130/130 episodes`，`130/130 readable videos`；
- Phase B：`1/1 valid`，`10/10 episodes`，`10/10 readable videos`；
- 总计：`14/14 valid`，`140/140 episodes`，`140/140 readable videos`；
- 所有 jobs 均有可解析 `results.txt`、Hydra config/overrides、EDS metrics、Stage events、qualitative artifacts、main/runner logs、strict suite evidence；
- 所有正式 jobs 均为 0 nonfinite、0 action-mask violation、无普通 LIBERO fallback、credential scan 通过，且 output realpath 在 shared2 目标下；
- Phase A 的 `p2_param_rt2to1_s10_start04_skip0` 在 task 4 记录到 1 个可复现 qpos/execution error。该项按已批准 tie-breaker 计数，不是设计中的 Phase A hard-invalid gate；同配置保守重试复现后保留正式结果，且该 job 最终 rank 12；
- 正式 failed/invalid jobs：`0`。`failures/` 中的历史 runner ledger 和 `stale/` 中的启动/重试 artifact 不是最终 formal job 状态；最终 `run_manifest.csv` 均为 `done, valid=True`。

主要审计文件：

- `analysis/phase_a_audit.json`；
- `analysis/phase_b_audit.json`；
- `analysis/final_analysis.json`；
- `analysis/retry_attempts.json`；
- `manifests/phase_a_winner_manifest.json`。

## 12. 最终判断、风险与建议

同一套 10 个 `libero_object_swap` tasks **未达到 `>=5/10`**。最佳正式原始成功数仍是 P2 baseline rerun 的 `3/10`；Phase A winner 为 `2/10`，Phase B clean-tail 为 `0/10`。本轮没有运行任何未批准的结果驱动额外 sweep。

尚存风险：

- 每个配置只有 10 个固定 tasks/episodes，winner 对离散 task identity 敏感，不能解释为统计显著优势；
- Stage Recognition 依赖外部 API，存在可见 parse/query error 与 OFF→ON 反转；
- Phase B 的 `renoise 2→1 + skip_final=1` 使后 9/10 iter 完全无 rollout RBF，clean-tail 与短 rollout schedule 存在结构性交互；
- wrong-object interaction 成为 Phase B 主导失败，表明继续只调 rollout 幅值难以解决目标身份、接触与放置语义。

建议下一步不要把本轮结果当作自动追加 sweep 的授权。若另行批准新设计，优先将“方向覆盖保留”作为硬机制 gate，并针对目标身份/接触语义设计正交诊断；任何新 clean-tail 方案应避免在 `n_trunc=1` 的绝大多数 iter 中完全关闭 rollout diversity，同时继续使用相同 tasks/seeds 和独立预注册 ranking。
