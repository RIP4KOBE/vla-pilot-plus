# P2 Adaptive EDS+RBF Stage A 单因素 OOD 实验报告

## 1. 实验概览

- Benchmark：LIBERO-PRO `libero_object_swap`，strict perturbation 开启。
- 任务：固定 task IDs `0..9`，每个 profile 各运行 10 episodes，`max_episode_steps=720`。
- Baseline：`p2_legacy_stage_on_rerun`，即 `p2_stage_on`。
- 方法：11 个预注册单因素 profiles，不在 Stage A 组合组件。
- Stage Recognition：ON；Gemini grounding：OFF。
- 输出根目录：`outputs/ood_eval/p2_adaptive_eds_rbf/stage_a/`。
- Manifest：`outputs/ood_eval/p2_adaptive_eds_rbf/stage_a/run_manifest.csv`。
- 最终状态：`11/11 done`、`11/11 valid`、`110/110` videos。
- Safety：所有 jobs 均为 strict/suite verified，fallback=0、nonfinite=0、action-mask violation=0。另有 2 个 qpos execution errors，均按失败保留在 10-task 分母中，详见第 5 节。

GPU 2、3、4、5 用于首轮并行。GPU4 上四个彼此不同的 profile 均在约 3 至 4 条 metrics 后发生无 Python traceback 的 `SIGABRT/exit=134`；失败原件归档于 `outputs/ood_eval/p2_adaptive_eds_rbf/attempts/stage_a_gpu4_native_aborts_20260802T180321Z/`。四组随后只在 GPU2、3、5 以相同 config、seed 和 code-state fingerprint clean resume，并全部通过。GPU4 失败不计作算法结果。

## 2. 完整结果

| Profile | 单因素 | SR | 成功 tasks | Median latency (s) | 相对 baseline | Metrics | PNG | Wall-clock (s) | Valid |
|---|---|---:|---|---:|---:|---:|---:|---:|---|
| `p2_legacy_stage_on_rerun` | legacy baseline | 3/10 | 3, 8, 9 | 2.443 | 1.000x | 128 | 1300 | 1737 | PASS |
| `p2_sel_ess05` | adaptive ESS target 0.5 | 0/10 | none | 2.459 | 1.006x | 191 | 1320 | 2389 | PASS |
| `p2_sel_ess07` | adaptive ESS target 0.7 | 0/10 | none | 2.459 | 1.006x | 150 | 1320 | 2176 | PASS |
| `p2_adaptrbf_t08_s10` | adaptive rollout RBF t=0.8/s=10 | 0/10 | none | 2.366 | 0.968x | 296 | 1240 | 2854 | PASS |
| `p2_adaptrbf_t10_s20` | adaptive rollout RBF t=1.0/s=20 | 0/10 | none | 2.422 | 0.991x | 266 | 1248 | 2448 | PASS |
| `p2_divres_k2_e1` | k-center 2 + elite 1 | 2/10 | 0, 4 | 2.636 | 1.079x | 192 | 1320 | 2062 | PASS |
| `p2_divres_k4_e2` | k-center 4 + elite 2 | 0/10 | none | 2.551 | 1.044x | 118 | 1320 | 1887 | PASS |
| `p2_memory25` | 25% cross-chunk memory | 0/10 | none | 2.530 | 1.036x | 210 | 1310 | 2261 | PASS |
| `p2_memory50` | 50% cross-chunk memory | 0/10 | none | 2.559 | 1.047x | 235 | 1310 | 2635 | PASS |
| `p2_schedule_balanced` | adaptive search + balanced prefix | 1/10 | 8 | 2.940 | 1.203x | 209 | 1320 | 2507 | PASS |
| `p2_schedule_contact` | adaptive search + contact prefix | 1/10 | 9 | 2.944 | 1.205x | 290 | 1320 | 2949 | PASS |

## 3. Task-paired outcomes

`S` 表示成功，`F` 表示失败。每列对应同一 LIBERO-PRO task 和相同 seed。

| Profile | T0 | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 | 相对 baseline |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `p2_legacy_stage_on_rerun` | F | F | F | S | F | F | F | F | S | S | reference |
| `p2_sel_ess05` | F | F | F | F | F | F | F | F | F | F | +0 / -3 |
| `p2_sel_ess07` | F | F | F | F | F | F | F | F | F | F | +0 / -3 |
| `p2_adaptrbf_t08_s10` | F | F | F | F | F | F | F | F | F | F | +0 / -3 |
| `p2_adaptrbf_t10_s20` | F | F | F | F | F | F | F | F | F | F | +0 / -3 |
| `p2_divres_k2_e1` | S | F | F | F | S | F | F | F | F | F | +2 / -3 |
| `p2_divres_k4_e2` | F | F | F | F | F | F | F | F | F | F | +0 / -3 |
| `p2_memory25` | F | F | F | F | F | F | F | F | F | F | +0 / -3 |
| `p2_memory50` | F | F | F | F | F | F | F | F | F | F | +0 / -3 |
| `p2_schedule_balanced` | F | F | F | F | F | F | F | F | S | F | +0 / -2 |
| `p2_schedule_contact` | F | F | F | F | F | F | F | F | F | S | +0 / -2 |

没有单因素达到或超过 baseline 的 3/10。`p2_divres_k2_e1` 获得了 baseline 未成功的 tasks 0 和 4，但同时丢失 tasks 3、8、9，净 paired delta 为 -1，不能按预注册规则解释为收益。

## 4. 机制与代价

| Component | Profile | 观测机制指标 | 结论 |
|---|---|---|---|
| Adaptive ESS | `p2_sel_ess05` | median ESS ratio `0.500000` | 控制器命中 target，但 SR 从 3/10 降至 0/10。 |
| Adaptive ESS | `p2_sel_ess07` | median ESS ratio `0.700000` | 控制器命中 target，但 SR 从 3/10 降至 0/10。 |
| Adaptive RBF | `p2_adaptrbf_t08_s10` | 296 条 scale records；287 个 active chunks；287 个 active distinct scales；median `0.300` | scale 自适应生效、延迟未增加，但无 task 成功。全部 records 含 288 个 distinct values，其中一个来自 inactive chunk。 |
| Adaptive RBF | `p2_adaptrbf_t10_s20` | 266 条 records / 266 个 active chunks / 266 个 distinct scales；median `1.024` | 更强 controller 同样生效，但无 task 成功。 |
| Diversity resampling | `p2_divres_k2_e1` | median anchors=2、elites=1 | 唯一获得两个新 tasks 的组件，但 paired regression 更大。 |
| Diversity resampling | `p2_divres_k4_e2` | median anchors=4、elites=2 | 更强 coverage 没有转化为成功，说明 coverage 强度可能破坏 reward/prior 平衡。 |
| Population memory | `p2_memory25` | available/used chunks `171/171`；acceptance median=1.0 | memory 大量实际进入 population，但 SR 为 0/10。 |
| Population memory | `p2_memory50` | available/used chunks `185/183`；acceptance median=1.0 | 更高 memory 比例未改善 SR，并增加约 4.7% median latency。 |
| Adaptive schedule | `p2_schedule_balanced` | horizons `{4,8}`；renoise `{1,2,3}` | task 8 成功，但丢失 baseline tasks 3、9。 |
| Adaptive schedule | `p2_schedule_contact` | horizons `{2,4,8}`；renoise `{1,2,3}` | task 9 成功，但丢失 baseline tasks 3、8，延迟约 +20.5%。 |

所有单因素 median latency 均低于预注册的 `1.5x baseline` 上限，因此资格淘汰不是由延迟导致，而是由 SR 和 paired regression 导致。

### 4.1 Stage Recognition reliability

| Profile | Queries | OK | Error | Error rate |
|---|---:|---:|---:|---:|
| `p2_legacy_stage_on_rerun` | 127 | 107 | 20 | 15.7% |
| `p2_sel_ess05` | 148 | 114 | 34 | 23.0% |
| `p2_sel_ess07` | 147 | 113 | 34 | 23.1% |
| `p2_adaptrbf_t08_s10` | 203 | 151 | 52 | 25.6% |
| `p2_adaptrbf_t10_s20` | 172 | 143 | 29 | 16.9% |
| `p2_divres_k2_e1` | 139 | 107 | 32 | 23.0% |
| `p2_divres_k4_e2` | 135 | 111 | 24 | 17.8% |
| `p2_memory25` | 161 | 121 | 40 | 24.8% |
| `p2_memory50` | 213 | 155 | 58 | 27.2% |
| `p2_schedule_balanced` | 200 | 152 | 48 | 24.0% |
| `p2_schedule_contact` | 245 | 197 | 48 | 19.6% |
| **Total** | **1890** | **1471** | **419** | **22.2%** |

每个 profile 的每个 episode 至少有一次成功 query，因此满足当前 validity gate；但 22.2% 的 query error 可能改变 stage/guidance 时序，是跨方法比较的重要共同干扰因素。错误返回时现有 stage recognizer 可能采用 fallback 解析结果，该行为与 EDS strategy fallback 分开统计，不应被表中的 algorithm fallback=0 掩盖。

## 5. Qualitative failure review

对 baseline、`p2_divres_k2_e1`、两个 schedule profiles 的成功视频，以及 task 3 上 ESS/adaptive-RBF/k-center/memory/schedule 的失败视频末帧进行了人工复核：

- baseline 在 tasks 3、8、9 成功；task 0 运行至 step 719 后仍未完成放置，task 4 中目标物被推倒或掉落。
- `p2_divres_k2_e1` 在 tasks 0、4 成功，说明适度 k-center/elite 能发现 baseline 未覆盖的有效行为；但它没有保留 baseline 的三个成功任务。
- 失败形态包括未形成抓取、抓取后物体掉落或被推离、机械臂/夹爪与篮筐干涉、到达目标附近但未满足环境 success predicate。
- task 3 中 adaptive-RBF 的末帧看似接近或进入篮筐但仍被环境判失败，提示仅依赖末端空间 reward/可视接近度不足以保证 task completion。
- schedule 的成功仍发生在 guidance 已关闭后的放置阶段；adaptive prefix 没有稳定修复跨 stage 的抓取到放置转换。
- 两个 episode 因 gripper qpos 超出 RDT obs processor 的 raw range 而提前结束：`p2_sel_ess07` 的 task 9 / episode 10 / seed 548，以及 `p2_schedule_contact` 的 task 5 / episode 6 / seed 621。两者均计为失败，未从分母排除；对应证据分别位于 `episode_10/error.txt` 和 `episode_6/error.txt`。

这些观察只用于解释失败类别，不替代 simulator success flag。

## 6. Stage B eligibility

预注册资格要求：job valid、无 silent fallback，且相对 baseline 要么 SR 更高，要么 SR 相同且主机制指标改善、无新增 paired regression、median latency 不超过 1.5x baseline。

| Component family | Best Stage A profile | Eligibility | 原因 |
|---|---|---|---|
| Adaptive ESS | `p2_sel_ess05` / `p2_sel_ess07` | NOT ELIGIBLE | 0/10 < 3/10。 |
| Adaptive rollout RBF | `p2_adaptrbf_t08_s10` / `p2_adaptrbf_t10_s20` | NOT ELIGIBLE | 0/10 < 3/10。 |
| Diversity-aware resampling | `p2_divres_k2_e1` | NOT ELIGIBLE | 2/10 < 3/10，且 paired regression 3 tasks。 |
| Population memory | `p2_memory25` / `p2_memory50` | NOT ELIGIBLE | 0/10 < 3/10。 |
| Adaptive schedule | `p2_schedule_balanced` / `p2_schedule_contact` | NOT ELIGIBLE | 1/10 < 3/10。 |

因此 `p2_integrated_full` 与 `p2_integrated_minimal` 均无可合法选择的组件。Stage B manifest 必须记录 `not_eligible`，不得根据结果临时放宽规则或组合 `p2_divres_k2_e1` 与 schedule。

## 7. 结论

1. 五项组件都通过 mechanism activation 与安全检查，但没有任何单因素提高同一套 10 tasks 的 SR。
2. 当前 Stage A 最佳仍是 P2 legacy baseline `3/10`；主要工程 gate `>=5/10` 未达到。
3. `p2_divres_k2_e1` 显示行为覆盖可改变成功 task 集合，但还没有稳定的质量选择压力来保留 baseline successes。
4. 按预注册规则不存在 Stage B eligible integration，下一步应冻结空集 manifest，而不是进行结果驱动组合。
5. 若要继续追求 `>=5/10`，需要超出当前批准计划的新算法假设或新的预注册实验；在获得 approval 前不应追加 sweep。

## 8. Evidence paths

- Stage A outputs：`outputs/ood_eval/p2_adaptive_eds_rbf/stage_a/`
- Runner logs：`outputs/ood_eval/p2_adaptive_eds_rbf/runner_logs/stage_a/`
- GPU4 aborted attempts：`outputs/ood_eval/p2_adaptive_eds_rbf/attempts/stage_a_gpu4_native_aborts_20260802T180321Z/`
- Mechanism pretest report：`docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-02-p2-adaptive-eds-rbf-pretest-report.md`
