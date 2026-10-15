# P2 Adaptive EDS+RBF Stage A 定量与定性结果详细分析

## 1. 分析范围与结论摘要

本文分析 Stage A 的 11 个单因素 profile。实验均使用严格 LIBERO-PRO `libero_object_swap`、固定 tasks `0..9`、相同 episode seeds、每组 10 episodes、`max_episode_steps=720`、Stage Recognition ON、Gemini grounding OFF。实验输出位于：

`outputs/ood_eval/p2_adaptive_eds_rbf/stage_a/`

最重要的结论是：**五项新增组件在机制层面均按设计生效，但没有任何一个单因素提高环境成功率。** P2 baseline 为 `3/10`；最佳新增 profile `p2_divres_k2_e1` 为 `2/10`，并且成功任务集合从 baseline 的 `{3,8,9}` 改为 `{0,4}`。这说明适度 diversity-aware resampling 确实改变了可达行为 mode，却没有同时保留已有有效 mode。其余新增 profile 为 `0/10` 或 `1/10`。主要工程 gate `>=5/10` 未通过，Stage B 按预注册规则没有 eligible component，因此没有运行集成实验。

本轮最关键的诊断不是“组件没有工作”，而是以下三层结果发生了脱节：

1. 控制器/机制按目标激活；
2. EEF diversity、局部 reward 或 target distance 指标出现改善；
3. 长时域抓取、搬运、放置和 simulator success 没有随之改善。

这强烈指向当前 EPS-CoT reward、EEF trajectory descriptor、stage/guidance 时序与真实任务完成条件之间的对齐不足，而不是单纯缺少更强 diversity。

## 2. P2 Baseline 与算法变体含义

### 2.1 固定 P2 baseline

`p2_legacy_stage_on_rerun` 是本轮严格配对基线，也就是 `p2_stage_on`：

- population 为 16，EDS refinement 为 10 轮；
- initial sampler 使用 RBF-diverse denoise，`scale=20`、`start_ratio=0.8`；
- 每轮 truncated rollout 使用 fixed RBF，`scale=20`、`start_ratio=0.6`、作用于全部 EDS iterations；
- renoise 范围为 `3 -> 1`；
- parent weighting 为 legacy `softmax((-cost) * temperature)`，`temperature=0.1`；
- 不做 k-center parent coverage，不保留 unchanged elite；
- 每个 chunk 重新生成 fresh population，不使用跨 chunk memory；
- EDS 固定运行 10 轮，固定执行 8-action prefix；
- VLM Stage Recognition 开启，识别到阶段切换后按现有逻辑关闭 EDS guidance。

`use_cem=false`，因此 `num_elites=16` 不参与 CEM 截断选择；它不是“16 个 elite 都被保留”。baseline 的新增 strategy mode 均处于 legacy/off 状态。

### 2.2 全部 profile 的含义

| Profile | 组件 | 相对 baseline 的唯一改动 | 预期作用 |
|---|---|---|---|
| `p2_legacy_stage_on_rerun` | Reference | 无 | 本轮同代码、同 seeds 的 P2 对照 |
| `p2_sel_ess05` | Adaptive ESS | parent weighting 改为 `adaptive_ess`，目标 `ESS/N=0.5` | 增强 reward 选择压力，使约 8 个等效父代主导采样 |
| `p2_sel_ess07` | Adaptive ESS | 目标 `ESS/N=0.7` | 较温和选择压力，约 11.2 个等效父代 |
| `p2_adaptrbf_t08_s10` | Adaptive rollout RBF | fixed scale 20 改为 adaptive band，target ratio 0.8、max scale 10 | diversity 低于目标带时才施加较弱 RBF，高置信 reward 时抑制探索 |
| `p2_adaptrbf_t10_s20` | Adaptive rollout RBF | adaptive band，target ratio 1.0、max scale 20 | 尝试维持 initial-final diversity，保留更大的最大修正能力 |
| `p2_divres_k2_e1` | Diversity-aware resampling | 每轮保留 1 个 unchanged elite、2 个 reward-constrained EEF k-center anchors，其余 13 个 weighted offspring | 轻量保留高质量 mode 与离散 trajectory coverage |
| `p2_divres_k4_e2` | Diversity-aware resampling | 2 elites、4 anchors、10 weighted offspring | 更强的 mode preservation 和 coverage |
| `p2_memory25` | Cross-chunk memory | 下一 chunk 混入 25% 即 4/16 个经 shift、tail fill、2-step re-adaptation 的上一 chunk candidates | 延续上一 chunk 已发现的有效 mode，同时保留 12 个 fresh candidates |
| `p2_memory50` | Cross-chunk memory | memory 提高到 50% 即 8/16 | 更强时序连续性，但减少 fresh exploration |
| `p2_schedule_balanced` | Adaptive schedule | renoise 在线取 1/2/3，允许 early stop；执行 horizon 为 8/4，contact 也使用 4 | 接近目标时更频繁 replan，保持相对保守的执行开销 |
| `p2_schedule_contact` | Adaptive schedule | 同上，但执行 horizon 为 8/4/2 | 接触/夹爪切换时以 2 步 prefix 高频 replan |

除表中单一组件外，其余配置均保持 P2 baseline，因此这些结果是组件级控制变量实验，不能把多个组件的潜在交互收益归因给任一单因素。

## 3. 实验完整性与有效性

| 检查项 | 结果 |
|---|---:|
| Stage A jobs | `11/11 done`、`11/11 valid` |
| Episodes / videos | `110/110`，均可被 ffprobe 读取 |
| EDS metric records | 2285 |
| Qualitative PNG | 14328 |
| strict perturbation / suite | `11/11 PASS` |
| algorithm fallback | 0 |
| nonfinite | 0 |
| action-mask violation | 0 |
| qpos execution error | 2，保留在失败分母中 |

两个 qpos error 分别发生于 `p2_sel_ess07` task 9 和 `p2_schedule_contact` task 5。GPU4 首轮的 native `SIGABRT` 已在 GPU2/3/5 使用相同 config、seed 和 fingerprint clean retry；这些 aborted attempts 不计入算法结果。

Stage Recognition 共 1890 次 query，其中 1471 次成功、419 次 error，错误率 `22.2%`。每个 episode 至少有一次成功 query，因此符合当前 validity gate；但该错误率可能改变 guidance OFF 时机，是所有 profile 共享但强度不完全一致的实验混杂因素。

## 4. 环境成功率与任务配对结果

| Profile | SR | 成功 tasks | 相对 baseline paired delta | Median latency | 相对 baseline |
|---|---:|---|---|---:|---:|
| `p2_legacy_stage_on_rerun` | **3/10** | 3, 8, 9 | reference | 2.443 s | 1.000x |
| `p2_sel_ess05` | 0/10 | none | +0 / -3 | 2.459 s | 1.006x |
| `p2_sel_ess07` | 0/10 | none | +0 / -3 | 2.459 s | 1.006x |
| `p2_adaptrbf_t08_s10` | 0/10 | none | +0 / -3 | 2.366 s | 0.968x |
| `p2_adaptrbf_t10_s20` | 0/10 | none | +0 / -3 | 2.422 s | 0.991x |
| `p2_divres_k2_e1` | **2/10** | 0, 4 | **+2 / -3** | 2.636 s | 1.079x |
| `p2_divres_k4_e2` | 0/10 | none | +0 / -3 | 2.551 s | 1.044x |
| `p2_memory25` | 0/10 | none | +0 / -3 | 2.530 s | 1.036x |
| `p2_memory50` | 0/10 | none | +0 / -3 | 2.559 s | 1.047x |
| `p2_schedule_balanced` | 1/10 | 8 | +0 / -2 | 2.940 s | 1.203x |
| `p2_schedule_contact` | 1/10 | 9 | +0 / -2 | 2.944 s | 1.205x |

结论很明确：没有新增 profile 达到或保持 baseline 的 `3/10`，更没有达到 `>=5/10`。`p2_divres_k2_e1` 是唯一发现 baseline 新成功任务的变体，但净成功数下降 1；两种 schedule 各保留一个 baseline success，没有发现新任务；其余七组丢失全部三个 baseline successes。

由于每个 profile 只有同一组 10 tasks 各一次 rollout，SR 的置信区间很宽，不能据此精确排序两个 0/10 变体；但在预注册工程 gate 下，任何 0/10 或 1/10 都足以判定其未优于 3/10 baseline。

## 5. P2 Baseline 的机制基准

以下为所有有 EDS guidance 的 chunk 的中位数。不同 profile 的 guided chunk 数不同，因此本节适合描述机制，不适合替代 task-paired SR：

| 指标 | P2 baseline 中位数 | 解释 |
|---|---:|---|
| Initial EEF diversity: before RBF | 0.1407 | policy denoise 早期的紧凑轨迹云 |
| Initial EEF diversity: after RBF phase | 0.4692 | initial RBF 将 diversity 放大约 3.33 倍 |
| Initial EEF diversity: final | 0.1715 | 完整 denoise 后大部分分散度被 prior 拉回 |
| Initial retention ratio | 0.3614 | final 仅保留 after-RBF diversity 的约 36% |
| Initial endpoint spread: before/after/final | 0.0650 / 0.2308 / 0.0919 | endpoint 也呈现“推开后回缩” |
| Rollout EEF diversity: before/after/final | 0.1460 / 0.3710 / 0.1565 | fixed rollout RBF 再次推开，后续 denoise 再次收缩 |
| Rollout retention ratio | 0.4209 | rollout final 保留 after-RBF diversity 的约 42% |
| Rollout endpoint spread: before/after/final | 0.0703 / 0.1833 / 0.0827 | 与 EEF diversity 一致 |
| Unique parent ratio | 0.6438 | 有放回采样后约 64% parent ID 唯一 |
| ESS ratio | 1.0000 | legacy weighting 几乎均匀 |
| Max parent probability | 0.0626 | 接近均匀分布的 `1/16=0.0625` |

定性图与这些统计一致：initial/rollout RBF 的中间图呈放射状扩散，而 final denoised population 明显回到紧凑区域。P2 的问题不是 RBF 没有产生排斥力，而是 policy prior 在后续 denoise 中消除了大部分 diversity，同时近均匀 parent weighting 没有可靠利用 reward 保存有效 mode。

## 6. 首 Chunk 严格配对机制结果

下表对每个 task 的第一个 EDS chunk 取值，再在 10 个固定 tasks 上求中位数；相较“所有 guided chunks”更适合公平比较组件初始作用。`reward gain = final_best - initial_best`；`target improvement = target_before - target_after`，正值表示指标改善。

| Profile | Init final div. | Rollout before/after/final | Retention | Reward gain | Target improve | Unique parent | ESS | Max p |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| baseline | 0.1641 | 0.1437 / 0.3664 / 0.1488 | 0.4075 | +0.0164 | +0.0459 | 0.650 | 1.000 | 0.0628 |
| ESS05 | 0.1659 | 0.1380 / 0.3609 / 0.1519 | 0.4159 | +0.0207 | +0.0815 | 0.503 | 0.500 | 0.2293 |
| ESS07 | 0.1636 | 0.1453 / 0.3682 / 0.1533 | 0.4170 | +0.0252 | +0.0864 | 0.575 | 0.700 | 0.1579 |
| Adaptive RBF 0.8/10 | 0.1643 | 0.1432 / 0.0460 / 0.0504 | 1.0000* | -0.0154 | -0.0464 | 0.650 | 1.000 | 0.0625 |
| Adaptive RBF 1.0/20 | 0.1669 | 0.1355 / 0.0827 / 0.0518 | 1.0000* | -0.0156 | -0.0444 | 0.650 | 1.000 | 0.0625 |
| k2/e1 | 0.1638 | 0.1443 / 0.3697 / 0.1590 | 0.4298 | **+0.0320** | **+0.1213** | 0.670 | 1.000 | 0.0628 |
| k4/e2 | 0.1657 | 0.1502 / 0.3642 / 0.1551 | 0.4290 | +0.0313 | **+0.1219** | 0.700 | 1.000 | 0.0628 |
| memory25 | 0.1632 | 0.1522 / 0.3655 / 0.1521 | 0.4125 | +0.0157 | +0.0376 | 0.650 | 1.000 | 0.0628 |
| memory50 | 0.1662 | 0.1448 / 0.3633 / 0.1512 | 0.4126 | +0.0206 | +0.0464 | 0.647 | 1.000 | 0.0628 |
| schedule balanced | 0.1627 | 0.1429 / 0.3618 / 0.1509 | 0.4151 | +0.0234 | +0.0645 | 0.628 | 1.000 | 0.0628 |
| schedule contact | 0.1616 | 0.1415 / 0.3632 / 0.1502 | 0.4133 | +0.0240 | +0.0879 | 0.650 | 1.000 | 0.0628 |

`*` Adaptive RBF 的 retention median 为 1.0 不能解释为“完美保留 baseline 级 diversity”。其 after/final 绝对值只有约 0.046--0.052，远低于 baseline 的 0.366/0.149；部分 iteration 未启用 RBF或 diversity phase 与 local final step 重合，使 ratio 失去单独解释价值。

最值得注意的是，ESS、k-center 和 schedule 的首 chunk reward/target proxy 多数优于 baseline，但环境 SR 反而更低。尤其 k2/e1 的 reward gain 和 target improvement 约为 baseline 的 2 倍以上，却只得到不同的 2/10 success。这是当前 reward/target proxy 与长时域 task completion 不充分对齐的最强定量证据。

## 7. Adaptive ESS 结果

### 7.1 定量结果

| Profile | Median beta | ESS/N | Max parent p | Unique parent | Degenerate iterations | SR |
|---|---:|---:|---:|---:|---:|---:|
| baseline | legacy | 1.000 | 0.0626 | 0.6438 | 0 | 3/10 |
| ESS05 | 1.280 | 0.500 | 0.2183 | 0.5000 | 110 | 0/10 |
| ESS07 | 0.752 | 0.700 | 0.1481 | 0.5688 | 0 | 0/10 |

ESS controller 精确命中两个 target，证明实现正确。ESS05 将最大父代概率提高到约 21.8%，unique parent ratio 降至 0.5；ESS07 较温和，但也明显高于 baseline 的选择压力。两组均 0/10，因此失败不能归因于“ESS 没有真正改变采样”。

### 7.2 定性解释

`selection/parent_source_trajectories_3d.png` 显示 ESS profile 的 16 个 offspring 全来自 weighted sampling；轨迹在空间上仍可分散，但 lineage 更重复。`parent_rank_and_probability.csv` 能看到高概率父代被多次抽取。ESS05 的 110 个 degenerate reward iterations 还说明相当一部分轮次缺少可分辨 reward spread，此时要求更强选择压力并不能产生更多有效信息。

结论：当前瓶颈不是选择压力太弱这么简单。当 reward ranking 含噪、退化或只反映局部 EEF 接近度时，增强压力会更快复制错误父代，并牺牲 baseline 偶然保留的可行 mode。ESS05 比 ESS07 更集中，但两者同为 0/10，说明只调 ESS target 不足以修复 selection objective。

## 8. Adaptive Rollout RBF 结果

### 8.1 控制器激活统计

| Profile | Iter records | Active | Active ratio | Applied scale median / p90 / max | SR |
|---|---:|---:|---:|---:|---:|
| t0.8 / s10 | 2960 | 1877 | 63.4% | 0.203 / 0.798 / 2.356 | 0/10 |
| t1.0 / s20 | 2660 | 2158 | 81.1% | 0.965 / 2.056 / 6.133 | 0/10 |

t0.8/s10 的 trigger 以 `below_band` 1877 次为主，另有 `below_band_high_confidence` 475、`in_band` 517、`above_band` 91；t1.0/s20 有 `below_band` 2158、`below_band_high_confidence` 219、`in_band` 279、`above_band` 4。控制器能够检测 diversity collapse，也确实输出大量不同 scale。

但实际 scale 比 fixed baseline 的 20 小一个至两个数量级。所有 guided chunks 的 rollout EEF after/final 中位数分别为：

- t0.8/s10：`0.0459 / 0.0519`；
- t1.0/s20：`0.0754 / 0.0456`；
- fixed baseline：`0.3710 / 0.1565`。

这说明当前公式中的 deficit、iteration decay 和 reward-confidence decay 相乘后过于保守。它能识别“低于目标带”，却没有施加足以恢复绝对 diversity 的 RBF；有时高 confidence 又将 scale 直接压到 0，而当前 confidence 本身来自尚未证明与环境成功对齐的 reward。

### 8.2 定性证据

代表性 `reward_diversity_schedule.png` 中，diversity 在第 1--2 轮已跌破目标带，但 scale 仍因 high-confidence gating 为 0；第 3--5 轮 scale 仅逐步升至约 0.18、0.40、0.71，随后再次归零，最终 diversity 继续下降。t0.8/s10 的 20 个可视化 chunks 均没有 `Rollout_RBF_diversity` PNG，因为 trace 记录的首轮 scale 为 0；t1.0/s20 仅 2/20 个 chunks 的首轮启用了 RBF，共生成 6 张该类 PNG。这不是输出缺失，而是定性地揭示 controller 在被重点追踪的首轮经常关闭 RBF。

结论：自适应方向本身可行，但当前 controller 把“避免过度探索”推得太远，变成了明显弱于 fixed P2 的 rollout diversity intervention。更严重的是，它依赖 reward confidence 抑制 RBF，而本轮结果恰好表明 reward confidence 未必对应任务可行性。

## 9. Diversity-Aware Resampling 结果

### 9.1 定量结果

| Profile | Anchors / elites | Anchor min distance | Unique parent | Selected source | Elite survival >0 | Anchor lineage survival >0 | SR |
|---|---:|---:|---:|---|---:|---:|---:|
| k2/e1 | 2 / 1 | 0.1542 | 0.6667 | elite 167/192 (87.0%) | 35/192 (18.2%) | 70/192 (36.5%) | 2/10 |
| k4/e2 | 4 / 2 | 0.0887 | 0.6929 | elite 110/118 (93.2%) | 21/118 (17.8%) | 65/118 (55.1%) | 0/10 |

k4/e2 的 anchor min distance 更小并不表示 k-center 失效，而是同一有限 eligible pool 中要求放入更多 anchors，后加入的 anchor 必然更接近已有中心。两个 profile 都提高了 parent coverage；k4/e2 的 anchor lineage survival 更高，但 final selected trajectory 反而更常来自 elite，且 SR 降到 0。

### 9.2 定性证据

`parent_source_trajectories_3d.png` 清晰显示 k2/e1 在主体 weighted-offspring 云之外保留一个 unchanged elite，并从 reward-eligible pool 产生两个空间分离的 anchor offspring。某个代表 chunk 的 10 轮累计 composition 为 10 elite、20 anchor offspring、130 weighted offspring，anchor pairwise distance 为 0.201；但该 chunk 最终选中 elite，elite 和 anchor lineage 均未存活到 final population 的有效选择中。

k2/e1 成功 tasks 0、4，而 baseline 成功 tasks 3、8、9。这是本轮唯一明确的正向 qualitative signal：parent coverage 确实打开了不同动作模式，且其中两个模式能完成原 baseline 无法完成的任务。它同时也暴露了问题：现有 resampling 没有“既保留 baseline mode，又探索新 mode”的稳定能力。

结论：k2/e1 是最值得继续研究的组件，但不能称为当前收益方案。k4/e2 预留 6/16 固定来源 slots 后，仅剩 10 个 weighted offspring，覆盖强度过大；anchors 多数承担探索，却很少成为最终选择。下一版若继续，应优先改善 anchor/elite 的质量约束和跨轮 survival，而不是继续增加 anchor 数。

## 10. Cross-Chunk Population Memory 结果

### 10.1 定量结果

| Profile | Available / used chunks | Acceptance median | Memory fraction | Memory reward - fresh | Memory diversity - fresh | Selected memory | SR |
|---|---:|---:|---:|---:|---:|---:|---:|
| memory25 | 171 / 171 | 1.0 | 0.25 | -0.00198 | -0.1311 | 33/210 (15.7%) | 0/10 |
| memory50 | 185 / 183 | 1.0 | 0.50 | -0.00177 | -0.1294 | 88/235 (37.4%) | 0/10 |

memory candidates 的 best reward 中位数略差于 fresh，EEF diversity 则低约 0.13；但 reward guard 的 acceptance median 仍为 1.0，表明 guard 对陈旧、低多样性的 memory 过于宽松。比例从 25% 增至 50% 后，所有 guided chunks 的 initial-final diversity 从 baseline `0.1715` 降到 `0.1523` 和 `0.1228`，retention 从 `0.3614` 降到 `0.3217` 和 `0.2626`。

### 10.2 定性证据

`fresh_vs_memory_trajectories_3d.png` 中 fresh population 覆盖较宽，而 adapted memory 形成靠近上一 selected mode 的紧密轨迹束。代表性的 memory50 chunk 中，8 个 memory candidates 的 diversity 为 0.0201，8 个 fresh candidates 为 0.1534；memory best reward `-0.0240` 也差于 fresh 的 `-0.0129`，但 8 个 memory 仍全部被接受，最终选择来自 fresh。

结论：当前 memory 更像“高接受率的陈旧 mode 注入”，而不是“高质量 mode 延续”。它占用 fresh population slots、降低 initial diversity，并可能把上一 chunk 的局部错误带入新 observation。50% 比 25% 更明显，说明问题主要是 acceptance/quality gate，而非 memory 数量不足。

## 11. Adaptive Search 与 Execution Schedule 结果

### 11.1 定量结果

| Profile | Early stop | Renoise iteration counts | Execution horizons | SR | Latency delta |
|---|---:|---|---|---:|---:|
| balanced | 0/209 chunks | t1=5, t2=1871, t3=214 | h4=142, h8=67 | 1/10 (task 8) | +20.3% |
| contact | 0/290 chunks | t1=7, t2=2596, t3=297 | h2=86, h4=100, h8=104 | 1/10 (task 9) | +20.5% |

两个 profile 的每个 EDS call 都完整运行 10 iterations，adaptive early-stop 从未触发。renoise 也几乎退化为“首轮 t3，之后 t2”：`uncertain` 是绝大多数迭代的 trigger，真正进入 `stable_improving -> t1` 或 diversity recovery 的次数极少。因此这两组实验的主要实际变量不是节省 EDS 迭代或精细自适应 renoise，而是执行 4/2 步后更频繁闭环重规划。

### 11.2 定性证据

`reward_diversity_schedule.png` 显示代表 chunk 中 best reward 会改善，但 mean reward 并不同步，diversity 也有波动；schedule 仍在首轮 t3 后长期选择 t2。contact profile 的 horizon 可视化确认远距离为 8，接近或接触阶段会切到 4/2，但这使 EDS/VLM 调用更频繁，并把 median selection latency 提高约 20%。

balanced 只保留 baseline task 8，contact 只保留 task 9；已有视频还显示成功通常发生在 guidance 关闭后的放置阶段。缩短 execution prefix 没有稳定解决抓取到放置的跨阶段转换，反而增加了接受 stage-recognition query error 和局部 steering 抖动的机会。

结论：当前 state features 和阈值不足以判断何时需要 t1、early stop 或接触级 replan。算法实现可用，但实际策略主要落在 t2 和短 horizon，增加开销且没有净成功收益。

## 12. Qualitative Artifacts 全量审计与失败类型

### 12.1 Artifact 覆盖

每个 profile 对 10 episodes 各保存两个代表 chunks，通常为 chunk 0 和 chunk 8，共 20 个 visual chunks。常规每个 chunk 包含：

- Initial RBF before/after/final EEF 3D、endpoint scatter、pairwise-distance histogram；
- Rollout RBF before/after/final 对比；
- `single_step_inner_loop` 的 initial、scored、resampled、renoised、rollout population；
- `full_eds_process` 的 10 轮 population/best trajectory、reward/diversity/distance curves；
- overlay、CSV、JSON、NPZ/PT mechanism trace。

各 profile PNG 总数为：baseline 1300；ESS05/07、k2/e1、k4/e2、balanced/contact 各 1320；adaptive t0.8/s10 为 1240；adaptive t1.0/s20 为 1248；memory25/50 各 1310。差异来自组件专属图和 adaptive RBF 首轮 scale=0 时不生成 rollout-RBF 图，不是 invalid evidence。

专属定性证据包括：

- ESS/k-center：parent rank/probability、elite/anchor survival、parent-source 3D；
- memory：fresh vs adapted-memory 3D 和 acceptance JSON；
- adaptive RBF/schedule：per-iteration adaptive decisions 和 reward-diversity-schedule 图。

### 12.2 环境视频中的共同失败类型

对 baseline、新增成功组及 task-paired 失败视频的复核显示：

1. 未建立稳定抓取，夹爪接近但没有夹住目标；
2. 抓取后掉落，或接触时把物体推离可抓区域；
3. 搬运/放置时机械臂、夹爪与篮筐干涉；
4. 末端轨迹或最后画面接近目标，但 simulator success predicate 未满足；
5. guidance/stage 切换后，抓取阶段形成的局部优势没有稳定传递到放置阶段。

task 3 的 adaptive-RBF 失败末帧在视觉上接近篮筐，但环境仍判失败。这与首 chunk reward/target 指标改善却 SR 下降的统计相互印证：EEF-space 几何接近不包含 grasp stability、物体是否仍被持有、碰撞、正确 release 时机和最终谓词。

## 13. 跨组件综合判断

### 13.1 为什么机制改善没有转化为 SR

第一，当前 reward 的可辨识性和任务对齐不足。baseline parent distribution 几乎均匀，说明 reward spread 小；ESS 增压后只是更有力地放大现有排序。k-center 取得更好的首 chunk reward/target progress 仍未提高 SR，证明局部 score 不是可靠的全任务质量函数。

第二，trajectory descriptor 只覆盖 3D EEF 几何。RBF、k-center 和 diversity metrics 都无法直接区分稳定抓取与空手轨迹、是否夹持目标、碰撞风险、gripper release 时机和 object-in-receptacle predicate。更高 EEF diversity 可以扩展行为，却不能保证扩展的是可执行且任务相关的行为。

第三，policy prior 在 denoise 中持续收缩 diversity。固定 RBF 能强行推开轨迹，但 final 只保留约 36%--42%；adaptive RBF 当前响应太弱。单纯继续增加 RBF 又可能破坏动作可行性，必须与质量约束和 mode survival 联合设计。

第四，跨 chunk/stage 的闭环状态不足。memory 延续的是旧 action trajectories，而不是被验证的 object-interaction state；schedule 增加 replanning，却依赖有 22.2% query error 的 stage signal 和有限的 distance/gripper heuristic。因此局部优化不能可靠穿过抓取、搬运、放置阶段。

### 13.2 哪些结果仍有研究价值

1. `p2_divres_k2_e1` 是唯一产生两个 baseline 新成功任务的变体，证明离散 parent coverage 能改变可达 mode；这是最强的正信号。
2. ESS controller 命中目标，适合作为可控工具保留，但必须先提升 reward calibration 或增加 quality guard，不能直接以 0.5/0.7 替换 baseline。
3. Adaptive RBF 能在线识别 collapse，但 scale law 过弱且过度依赖 reward confidence；需要重新定义最小有效干预和 controller evaluation metric。
4. Memory 的诊断非常清楚：guard 需要同时约束 reward、diversity、stage consistency 和新 observation 下的可行性。
5. Schedule 的主要收益假设尚未被真正测试，因为 early stop 没触发、t1 几乎不用；下一版需先让状态分类覆盖预期工作区间，再做 OOD SR 测试。

### 13.3 为什么在 P2 上增加机制反而降低成功率

“机制没有收益”不等于“机制是 no-op”。只有新增逻辑不改变 population、随机数消耗、selected action、执行 horizon 和后续 observation 时，成功率才理论上应保持不变。本轮四类机制都通过 mechanism gate，说明它们确实主动改变了 P2 的搜索或控制分布；当这些变化依赖不充分对齐的 reward、EEF descriptor 或 stage signal 时，完全可能破坏 P2 原本脆弱的三个成功轨迹。

即使 task ID 和 root seed 相同，不同 strategy 也会改变 multinomial 调用、parent 数量和后续 RNG 消耗。机器人接触过程又具有强非线性，早期一个很小的动作差异就可能改变是否抓住、是否碰撞和后续 observation。因此“同 seed”并不等于各 profile 之间拥有逐 latent、逐 action 的严格反事实配对。

此外，每个 profile 只包含固定 10 tasks 各一次 rollout。`3/10` 与 `0/10--2/10` 的二项置信区间高度重叠，当前证据足以说明新增设置没有通过工程 gate，但不足以断言其真实期望成功率一定严格更低。以下分析给出的是由机制 trace、paired regression 和定性结果共同支持的高可信失败路径，仍需要多 seeds 和更细子消融确认因果强度。

#### 13.3.1 Adaptive ESS：放大错误排序并减少 lineage coverage

P2 baseline 的 parent weighting 几乎均匀：ESS ratio 约为 `1.0`、最大 parent probability 为 `0.0626`，接近 `1/16`。这虽然意味着 reward 选择压力较弱，却也提供了一种隐式鲁棒性：当 EPS-CoT reward 含噪、退化或只描述局部 EEF 接近度时，近均匀采样不会过度相信某个可能错误的高分候选，仍能保留多个 policy-prior modes。

Adaptive ESS 会先 robust-normalize rewards，再通过 beta 二分强制达到目标 ESS。这个过程关心相对排序而不是原始 reward spread 的绝对可信度。即使候选之间只有很小且主要来自噪声的差异，normalization 仍可能把差异放大到足以产生 `ESS/N=0.5` 或 `0.7` 的集中分布。随后 `torch.multinomial(..., replacement=True)` 会重复抽取高概率父代，使同一局部 mode 被多轮复制。

| 设置 | ESS/N | Max parent probability | Unique parent ratio | Degenerate iterations | SR |
|---|---:|---:|---:|---:|---:|
| P2 baseline | 1.000 | 0.0626 | 0.6438 | 0 | 3/10 |
| ESS05 | 0.500 | 0.2183 | 0.5000 | 110 | 0/10 |
| ESS07 | 0.700 | 0.1481 | 0.5688 | 0 | 0/10 |

ESS05 的最大父代概率约为 baseline 的 3.5 倍，unique parent ratio 降到 0.5；110 个 degenerate iterations 又说明不少轮次没有可辨别的 reward 信息。RBF 可以把同一父代的 offspring 在连续 EEF 空间推开，但无法恢复已经在离散 parent selection 中丢失的语义行为 mode。结果是 Adaptive ESS 更精确地优化了一个尚未与抓取放置成功充分对齐的排序，并牺牲了 baseline 偶然保留的可行轨迹。

#### 13.3.2 Diversity-Aware Resampling：有限 population 中的 coverage 与质量是零和交换

Diversity-aware resampling 不是在 baseline 的 16 个候选之外额外增加探索，而是在固定 `N=16` 内重分配 slots：

- k2/e1：1 个 unchanged elite、2 个 anchor offspring、13 个 weighted offspring；
- k4/e2：2 个 unchanged elites、4 个 anchor offspring、10 个 weighted offspring。

它可能通过四条路径降低成功率：

1. **占用 fresh weighted offspring 预算。** k4/e2 将 `6/16` slots 固定给 elite/anchor，只留下 10 个 slots 进行原 P2 weighted mutation，减少 policy-prior exploration。
2. **冻结局部 false-positive elite。** unchanged elite 绕过本轮 renoise 和 rollout RBF；如果 reward 把空抓、碰撞或不稳定持物轨迹评为高分，该错误 mode 会被确定性保留。
3. **EEF coverage 不等于任务 coverage。** k-center 只使用 3D EEF trajectory distance。在空间上最远的轨迹可能是错误方向、空手移动或不可稳定执行的 outlier。`reward_quantile=0.5` 只把 anchors 限制在 reward 较高的一半，并不能保证 grasp feasibility。
4. **新 mode 缺少可靠 survival signal。** k2/e1 的 anchor lineage 仅在约 36.5% records 中有正存活，最终选择又高度偏向 elite。系统能够产生新轨迹，但当前 reward 无法稳定识别哪些 mode 值得跨轮保留。

k2/e1 成功 tasks `{0,4}`，同时丢失 baseline 的 `{3,8,9}`。这不是“所有行为都变差”，而是 trajectory coverage 移到了另一组区域：它打开了两个新有效 mode，却没有保住 P2 原有 mode。k4/e2 更强的 coverage 占用进一步减少 exploitation budget，最终变为 `0/10`。因此该机制的主要问题不是 k-center 没有工作，而是固定 population 下缺少“baseline mode protection + task-aware anchor quality + reliable final survival”的联合约束。

#### 13.3.3 Cross-Chunk Population Memory：把局部错误变成跨 chunk 相关错误

P2 每个 chunk 都从当前 observation 生成完整 fresh population。它缺少显式连续性，但每次拥有 16 个新的 policy samples，上一 chunk 的错误不会被结构化继承。Memory 模式则会把上一 chunk population 左移、使用 fresh tail 填充，再做 2-step renoise/denoise，并用其中一部分替换当前 fresh population。

当前 reward guard 只要求 memory candidate 的 reward 不低于 fresh population 的第 25 百分位。它不检查 memory 是否比对应 fresh candidate 更好，也不约束 diversity、grasp state、object attachment、碰撞风险或当前 observation 下的 stage consistency。因此门槛明显过宽：

| 设置 | Acceptance median | Memory reward - fresh | Memory diversity - fresh | Initial-final diversity | SR |
|---|---:|---:|---:|---:|---:|
| P2 baseline | N/A | N/A | N/A | 0.1715 | 3/10 |
| memory25 | 1.0 | -0.00198 | -0.1311 | 0.1523 | 0/10 |
| memory50 | 1.0 | -0.00177 | -0.1294 | 0.1228 | 0/10 |

Memory candidates 的 reward 略差且 diversity 显著低于 fresh，却几乎全部被接受。25% memory 只保留 12 个 fresh slots，50% memory 只保留 8 个；它们不是扩容，而是直接减少当前 observation 下的 fresh exploration。2-step re-adaptation 还面临两难：强度不足时保留旧 condition 下的陈旧轨迹，强度过大时又被当前 prior 拉回，仍无法保证保留的是正确交互状态。

更关键的是误差相关性。若上一 chunk 选择了错误接近方向、空抓或即将掉落的 mode，下一 chunk 会显式继承它，使原本可以独立恢复的 fresh searches 变成连续的同 mode 失败。当前 memory 因而更接近“高接受率的陈旧 mode 注入”，尚不是“验证过的高质量 mode 延续”。

#### 13.3.4 Adaptive Search 与 Execution Schedule：后期持续强 mutation，并打断 8-step 时间一致性

这两个 profile 同时改变了 renoise schedule 和 execution horizon，因此下降不能被唯一归因于其中一个子组件。

P2 legacy 使用 `3 -> 1` linear renoise，后半段会大量进入 `t=1`，逐步从探索转向低强度 refinement。Adaptive schedule 的实际运行却几乎退化为首轮 `t=3`、其余轮次长期 `t=2`：

| 设置 | Early stop | Renoise counts | Horizon counts | SR |
|---|---:|---|---|---:|
| balanced | 0/209 | t1=5, t2=1871, t3=214 | h4=142, h8=67 | 1/10 |
| contact | 0/290 | t1=7, t2=2596, t3=297 | h2=86, h4=100, h8=104 | 1/10 |

这意味着预期的“稳定后减少搜索并 early-stop”没有发生。后期持续使用 `t=2`，相较 baseline 的 `t=1` 保持了更强 mutation/reconstruction，可能反复破坏已经形成的精细抓取、夹爪时序或接触轨迹；所有 EDS calls 又都运行满 10 轮，没有获得计算或稳定性补偿。

Execution horizon 从固定 8 变为 8/4 或 8/4/2 也会主动改变闭环：

1. RDT 生成的 8-step chunk 具有时间一致性，执行 2/4 步后重规划会丢弃已经规划好的 close、lift 或 release 后续动作。
2. 新 observation 下重新采样可能改变抓取意图，引入 EEF 或 gripper command 抖动。
3. 短 horizon 增加 EDS 和 Stage Recognition 调用次数；本轮 Stage Recognition query error rate 为 `22.2%`，更频繁查询扩大了错误 stage/guidance 时序的暴露面。
4. contact/near 决策依赖 target distance 和 gripper-transition proxy；若 EEF distance 未反映真实物体持有状态，会过早进入短 horizon。

两组 profile 的 metric records 为 209 和 290，显著高于 baseline 的 128，median selection latency 也增加约 20%。balanced 只保留 baseline task 8，contact 只保留 task 9。说明更频繁 replanning 并未稳定修复跨阶段控制，反而可能打断 P2 原有完整 action chunk，并在 guidance 关闭前重复施加不充分对齐的 steering。

#### 13.3.5 统一失败链路与后续验证要求

四类机制的共同失败链路可以概括为：

```text
不充分对齐的 reward / EEF descriptor / stage proxy
        -> ESS 放大错误排序
        -> k-center/elite 重分配有限 population slots
        -> memory 跨 chunk 延续局部错误
        -> schedule 更频繁地重新应用上述决策
        -> P2 原本偶然保留的 policy-prior 可行轨迹被替换或打断
        -> environment success 下降
```

若要把这些解释提升为严格因果结论，下一轮至少需要：

1. 每 task 增加多个 seeds，并报告 task-stratified paired confidence interval；
2. 冻结 initial latent/cache 和 VLM Stage Recognition responses，减少 profile 间随机流与 API 波动；
3. 将 schedule 拆成 `adaptive-renoise only`、`early-stop only` 和 `adaptive-horizon only`；
4. 将 resampling 拆成 `elite-only`、`k-center-only`、`k2/e1`，验证主要伤害来自哪一类 slot；
5. memory guard 至少比较 memory 与被替换 fresh candidate，并联合约束 reward、diversity、stage consistency 和 object-interaction state；
6. ESS 仅在 reward spread/confidence 通过校准 gate 时启用，退化或低置信轮次保留 P2 近均匀分布。

## 14. 最终结论

| 问题 | 结论 |
|---|---|
| 五项算法是否部署并生效？ | 是，mechanism metrics、专属 trace 和 qualitative artifacts 均证明生效。 |
| 是否有新增 profile 优于 P2 baseline？ | 否。baseline `3/10`，最佳新增 k2/e1 `2/10`。 |
| 是否达到主要工程 gate `>=5/10`？ | 否。 |
| 哪个方向最有潜力？ | 轻量 diversity-aware resampling，因为它唯一解锁两个新 tasks；但必须解决 baseline mode preservation 和最终质量选择。 |
| 哪些当前设置应直接保留为默认？ | 都不应。legacy P2 仍是本轮最佳。 |
| 是否应直接组合多个失败单因素？ | 不应。本轮预注册资格不满足，Stage B 为空是正确结果。 |
| 当前最主要瓶颈？ | reward/EEF proxy 与抓取放置成功不对齐，以及跨 chunk/stage 的质量状态不足。 |

下一步不宜继续盲目增强 diversity 或扩大同类 sweep。更合理的方向是先建立能识别 grasp stability、object transport、release 和 task predicate progress 的阶段化质量信号，再以轻量 k-center/elite preservation 为载体测试选择与 coverage；同时独立提高 Stage Recognition reliability。任何新算法应重新预注册，并继续使用同一 10-task paired gate，以避免从本轮结果中事后挑选组合。

## 15. Evidence Index

- 最终报告：`2026-08-02-p2-adaptive-eds-rbf-object-swap-report.md`
- Stage A 汇总：`2026-08-02-p2-adaptive-eds-rbf-stage-a-report.md`
- 机器可读结果：`2026-08-02-p2-adaptive-eds-rbf-object-swap-results.csv`
- 机器可读结果：`2026-08-02-p2-adaptive-eds-rbf-object-swap-results.json`
- Mechanism pretest：`2026-08-02-p2-adaptive-eds-rbf-pretest-report.md`
- Stage A outputs：`outputs/ood_eval/p2_adaptive_eds_rbf/stage_a/`
- Runner logs：`outputs/ood_eval/p2_adaptive_eds_rbf/runner_logs/stage_a/`
- Frozen integration manifest：`p2_adaptive_eds_rbf_integration_manifest.json`
