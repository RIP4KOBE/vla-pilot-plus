# P2 Adaptive EDS+RBF LIBERO-PRO Object-Swap 最终报告

## 1. 最终结论

本轮已完整部署并验证五项组件级优化，完成 6 个 mechanism pretest profiles、11 个 Stage A 单因素正式 jobs、资格冻结和最终 evidence audit。Stage A 为 `11/11 done`、`11/11 valid`，覆盖同一套 LIBERO-PRO `libero_object_swap` tasks `0..9`，共 `110/110` 个可读视频。

主要工程 gate **未通过**：P2 baseline `p2_legacy_stage_on_rerun` 为 `3/10`，最佳新增单因素 `p2_divres_k2_e1` 为 `2/10`，没有 profile 达到要求的 `>=5/10`。按预注册资格规则，五个组件均不具备进入 Stage B 的资格，因此 immutable manifest 将两个 integration slots 标记为 `not_eligible`，Stage B 合法 job 数为 `0`；没有根据结果临时组合参数或追加 sweep。

## 2. 实验设置

| 项目 | 设置 |
|---|---|
| Benchmark | LIBERO-PRO `libero_object_swap`，strict perturbation |
| Tasks | 固定 `0..9`，每个 profile 10 episodes |
| Episode limit | `backend.libero.max_episode_steps=720` |
| Policy | RDT，`/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object`，EMA weights |
| Stage Recognition | ON |
| Gemini grounding | OFF，Hydra 中 API key 为 `null` |
| P2 baseline | RBF initial s20/start0.8 + fixed rollout RBF + Stage Recognition |
| Stage A | 11 个单因素 jobs |
| Stage B | 0 jobs，两个 slots 均 `not_eligible` |
| GPUs | 首轮 2、3、4、5；GPU4 native abort 后 clean retries 仅使用 2、3、5 |
| 输出 | `outputs/ood_eval/p2_adaptive_eds_rbf`，软链接到 shared2 |

## 3. 算法交付

五项组件均作为独立 strategy mode 接入同一 `_eds_guided_denoise_loop()`，没有复制主循环；全部新增模式关闭或设为 legacy 时回退到 `p2_stage_on` 行为。

1. **Adaptive ESS parent weighting**：通过二分搜索调节 selection beta，使父代权重达到目标 ESS ratio，并记录实际 ESS、beta 和退化状态。
2. **Adaptive rollout RBF controller**：根据 rollout diversity retention 的在线状态调节 RBF scale，保留 fixed controller 作为 baseline。
3. **Diversity-aware resampling**：reward-constrained EEF k-center anchors、elite carryover 与 weighted parents 共同组成下一代。
4. **Cross-chunk population memory**：上一 chunk 候选 shift、fresh-tail fill、renoise/denoise、reward guard 后与 fresh population 混合，并在 episode/stage/guidance 变化时清理。
5. **Adaptive search schedule**：在线解析 renoise steps、early-stop 条件与执行 prefix horizon，legacy 模式保持固定迭代和执行长度。

未实现 QD-ED、MAP-Elites、新 reward、task-specific reward、Gemini grounding、VLS 路径改动、RDT action layout/checkpoint/scheduler step 改动，符合批准边界。

## 4. 测试结果

| 验证 | 结果 |
|---|---|
| 核心合并回归 | `672 passed in 143.87s` |
| Runner 全回归 | `228 passed in 88.41s` |
| Obs/stage ancillary 回归 | `52 passed in 17.75s` |
| 最终 validity 反例矩阵 | `16 passed` |
| `py_compile` | PASS |
| `git diff --check` | PASS |

最终 validity hardening 采用 TDD，新增拒绝重复 metric/stage identities、`bool`/float/越界 metric identity、坏 JSON、`null`、JSON array，并让无效 reset evidence 优先于 missing evidence 判为 FAIL。P2 strict reader 不再静默跳过损坏 JSONL 行。

## 5. Mechanism Pretest

6 个代表性 profiles 在 tasks 0/8 上共运行 12 episodes，`6/6 valid`、`12/12` 视频、`140/140` 必需 qualitative artifacts 可读，整体机制 gate 为 PASS。

| 机制 | 关键证据 | Gate |
|---|---|---|
| Adaptive ESS | 150 iterations，target 0.5，median absolute error `0.000005` | PASS |
| Adaptive RBF | 460 active iterations，使用大量不同 applied scales | PASS |
| k-center + elite | 40/40 iterations 精确为 2 elite + 4 anchors + 10 weighted | PASS |
| Population memory | 2/2 首个 eligible chunks 使用 memory；EDS-enabled stage reset `4/4` exact-step | PASS |
| Adaptive schedule | renoise `{2,3}`，horizon `{2,4,8}` | PASS |
| Safety | fallback=0、nonfinite=0、mask violation=0 | PASS |

详细证据见 `2026-08-02-p2-adaptive-eds-rbf-pretest-report.md`。

## 6. Stage A 完整结果

| Profile | 单因素 | SR | 成功 tasks | Median latency (s) | Metrics | PNG | Valid |
|---|---|---:|---|---:|---:|---:|---|
| `p2_legacy_stage_on_rerun` | P2 baseline | **3/10** | 3, 8, 9 | 2.443 | 128 | 1300 | PASS |
| `p2_sel_ess05` | ESS target 0.5 | 0/10 | none | 2.459 | 191 | 1320 | PASS |
| `p2_sel_ess07` | ESS target 0.7 | 0/10 | none | 2.459 | 150 | 1320 | PASS |
| `p2_adaptrbf_t08_s10` | adaptive RBF 0.8/10 | 0/10 | none | 2.366 | 296 | 1240 | PASS |
| `p2_adaptrbf_t10_s20` | adaptive RBF 1.0/20 | 0/10 | none | 2.422 | 266 | 1248 | PASS |
| `p2_divres_k2_e1` | k-center 2 + elite 1 | **2/10** | 0, 4 | 2.636 | 192 | 1320 | PASS |
| `p2_divres_k4_e2` | k-center 4 + elite 2 | 0/10 | none | 2.551 | 118 | 1320 | PASS |
| `p2_memory25` | memory 25% | 0/10 | none | 2.530 | 210 | 1310 | PASS |
| `p2_memory50` | memory 50% | 0/10 | none | 2.559 | 235 | 1310 | PASS |
| `p2_schedule_balanced` | adaptive balanced prefix | 1/10 | 8 | 2.940 | 209 | 1320 | PASS |
| `p2_schedule_contact` | adaptive contact prefix | 1/10 | 9 | 2.944 | 290 | 1320 | PASS |

总计：`11/11` valid jobs、`110/110` ffprobe-readable videos、`2285` metrics records、`14328` qualitative PNGs。所有方法的 median latency 都低于 `1.5x` baseline gate。

### 6.1 Task-paired 对比

| Profile | T0 | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `p2_legacy_stage_on_rerun` | F | F | F | S | F | F | F | F | S | S |
| `p2_divres_k2_e1` | S | F | F | F | S | F | F | F | F | F |
| `p2_schedule_balanced` | F | F | F | F | F | F | F | F | S | F |
| `p2_schedule_contact` | F | F | F | F | F | F | F | F | F | S |
| 其余 7 profiles | F | F | F | F | F | F | F | F | F | F |

`p2_divres_k2_e1` 的重要信号是成功集合从 baseline 的 `{3,8,9}` 变为 `{0,4}`：coverage 确实改变了可发现行为，但没有保留原有成功模式，paired delta 为 `+2/-3`，净成功数反而下降 1。

## 7. 组件分析

- **Adaptive ESS**：控制器精确命中 0.5/0.7 target，但两组均为 0/10。当前 reward 排序质量不足时，单纯校准选择压力不能修复错误父代偏好。
- **Adaptive RBF**：scale 确实逐 chunk/iteration 自适应，且没有增加 median latency，但 0/10 说明“保住 EEF diversity”本身没有转化为可完成的抓取与放置序列。
- **Diversity-aware resampling**：k2/e1 是唯一发现两个 baseline 新任务的组件；k4/e2 降至 0/10，显示 coverage 过强会进一步牺牲 reward/prior feasibility。它是本轮最有研究价值的信号，但尚非收益方案。
- **Population memory**：25%/50% memory 大量被接受并实际使用，仍均为 0/10。跨 chunk 延续错误 mode 的风险超过了连续性收益。
- **Adaptive schedule**：两组分别保留 baseline 的 task 8 或 task 9，但没有新增净成功，且 latency 约增加 20%。当前距离/夹爪启发式不足以可靠判断何时应加密 replanning。

## 8. Stage B 与冻结 Manifest

预注册规则要求单因素 SR 高于 baseline，或 SR 相同且主机制改善、无新增 paired regression、延迟不超过 1.5x。五个组件的最佳 Stage A SR 分别为 0、0、2、0、1，均低于 baseline 3/10，因此：

| Integration slot | 状态 | 原因 |
|---|---|---|
| `p2_integrated_full` | `not_eligible` | 没有 Stage A 组件满足资格规则 |
| `p2_integrated_minimal` | `not_eligible` | 不存在两个 eligible components |

Immutable manifest：`p2_adaptive_eds_rbf_integration_manifest.json`，SHA256 `e29547879aadc3ea151ce79405f66a401a3d060b0eb09a972b6bea90861b8c17`。`stage_b/run_manifest.csv` 只有 header、0 个 jobs，这是预注册规则的正确执行结果，不是漏跑。

## 9. 定性失败与共同干扰

- 主要失败包括：未形成抓取、抓取后掉落或推离、机械臂/夹爪与篮筐干涉、接近目标但未触发 simulator success predicate。
- Adaptive RBF 在部分末帧上看似接近目标，仍未完成环境 success，说明 EEF-space diversity/reward 缺少 grasp stability 与 task completion 信息。
- 两个 episode 出现 gripper qpos 越界：ESS07 task 9 和 schedule-contact task 5；两者均保留在 10-task 分母中。
- Stage Recognition 共 1890 次 queries，1471 OK、419 error，error rate `22.2%`。每个 episode 至少有一次成功 query，满足 validity gate，但 query error 会影响 guidance 开关时序，是后续必须单独解决的共同干扰因素。

## 10. Validity 与 Safety Audit

| Gate | 结果 |
|---|---|
| strict LIBERO-PRO / suite verified | `11/11` PASS |
| Results / Hydra / overrides / logs | `11/11` complete |
| 视频 | `110/110` 可读 |
| 普通 LIBERO fallback | 0 |
| Algorithm silent fallback | 0 |
| Nonfinite | 0 |
| Action-mask violation | 0 |
| Credential serialization | 0 |
| Final failed/invalid jobs | 0 |
| qpos execution errors | 2，均计入失败分母 |

GPU4 首轮出现 4 个无 Python traceback 的 `SIGABRT/exit=134`，跨越四种不同 profile；原件保存在 `attempts/stage_a_gpu4_native_aborts_20260802T180321Z/`。相同 config、seed、experiment fingerprint 在 GPUs 2/3/5 clean resume 后均通过，因此这些归档尝试不计作算法结果，也没有被删除。

## 11. Provenance

Stage A 和 immutable manifest 在冻结 experiment code-state `e7931dc95b5ed6f525ef86f83778fb93677a749cb08fa18db626d1f24eeabb7f` 下完成独立 audit。实验结束后只修改了 runner validity/report 层，增加 fail-closed identity、strict JSONL 和 reset-evidence 校验；算法实现、Hydra 配置和既有输出均未改变或重跑。

因此当前 runner 会按预期拒绝把旧 manifest 当成“当前代码生成”的 manifest。冻结 manifest 没有被重写；本报告引用的是 validator hardening 前已完成并记录的 experiment-state audit：11 个 Stage A evidence 全部 valid、110 个视频可读、strict/suite/credential gate PASS、Stage B job 数为 0。

## 12. Storage 与进程

真实输出：

`/mnt/data/shared2/hynx/VLA-Pilot++/eds-init-pg-diverse-sampling/outputs/ood_eval/p2_adaptive_eds_rbf`

Worktree 兼容链接：

`outputs/ood_eval/p2_adaptive_eds_rbf -> /mnt/data/shared2/hynx/VLA-Pilot++/eds-init-pg-diverse-sampling/outputs/ood_eval/p2_adaptive_eds_rbf`

收尾检查时 shared2 约剩余 `3.6 TiB`，远高于 20 GiB gate；没有遗留当前 worktree 的 runner/main experiment process。

## 13. Gate 与下一步

| Gate | 要求 | 最佳结果 | 状态 |
|---|---:|---:|---|
| 主要工程 gate | `>=5/10` | baseline `3/10`；最佳新增 `2/10` | **FAIL** |

当前批准矩阵已经完整执行，但 Goal 的成功条件没有实现，因此不能标记为 complete。下一步需要新的、先验注册的算法假设和用户 approval；不应在本轮结果上临时拼接 `k2/e1 + schedule` 或追加 sweep。优先建议围绕 reward/selection 与 stage reliability 的耦合问题提出新设计，因为现有结果已经表明：机制多样性增加和控制器激活都是真实的，但当前 reward 无法稳定识别并保留可完成整段任务的 mode。

## 14. Evidence Index

- 机器可读 CSV：`2026-08-02-p2-adaptive-eds-rbf-object-swap-results.csv`
- 机器可读 JSON：`2026-08-02-p2-adaptive-eds-rbf-object-swap-results.json`
- Test report：`2026-08-02-p2-adaptive-eds-rbf-test-report.md`
- Mechanism report：`2026-08-02-p2-adaptive-eds-rbf-pretest-report.md`
- Stage A report：`2026-08-02-p2-adaptive-eds-rbf-stage-a-report.md`
- Integration manifest：`p2_adaptive_eds_rbf_integration_manifest.json`
- Pretest audit：`docs/05_runs/2026-08-02-task12-p2-mechanism-pretest-audit.md`
