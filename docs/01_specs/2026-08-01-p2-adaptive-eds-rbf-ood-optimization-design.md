# P2 Adaptive EDS+RBF OOD 算法优化与评测设计

日期：`2026-08-01`

修订日期：`2026-08-02`

状态：`Approved for implementation planning`

## 1. 摘要

本设计以当前 LIBERO-PRO `libero_object_swap` 上表现最好的有效配置 `p2_stage_on` 为严格基线。在不覆盖、不改写现有 P2、EDS iid、fixed RBF 和 Stage Recognition 行为的前提下，通过 config 中彼此独立的组件级 strategy mode 新增以下优化方向：

1. EDS 有效选择压力；
2. 自适应 rollout RBF；
3. diversity-aware parent resampling；
4. 跨 chunk population memory；
5. 自适应 renoise、EDS iteration 和 action execution horizon。

推荐采用“**同一主控制流 + 组件级 strategy mode + 命名实验 profile**”的方式实现。所有新增组件均由 config 显式选择；新增 mode 全部关闭或设为 legacy 时，必须精确退回 `p2_stage_on` baseline。旧配置不增加 override 时继续执行当前 legacy 路径。runner 新增独立评测 level，所有新 job 使用独立 output directory 和完整配置指纹，禁止覆盖既有 baseline 输出。

本轮正式评测延用上一轮 OOD 标准：严格 LIBERO-PRO `libero_object_swap`、同一 10 个 tasks、相同 episode seeds、每组 10 episodes、`max_episode_steps=720`、Stage Recognition ON、Gemini grounding OFF。实验严格分为两个阶段：阶段 A 先完整执行 baseline 与所有单因素组，独立判断每项算法的收益；阶段 B 只在阶段 A 报告完成后再评估最多两个兼容的集成方案。主要工程 gate 始终是同一 10 个 tasks 达到 `>=5/10`。

本设计只定义算法、配置、测试和证据要求，不实现代码，不启动实验。

## 2. 当前证据与问题定位

### 2.1 固定 P2 baseline

本轮将 `p2_stage_on` 定义为唯一行为基线。其固定配置为：

```yaml
policy.type: rdt
main.use_guidance: true
main.guidance_type: eds
main.use_vlm_stage_recognition: true
perception.gemini_grounding.enabled: false

main.eds_config:
  population_size: 16
  cem_iters: 10
  use_cem: false
  num_elites: 16
  temperature: 0.1
  renoise_t_max: 3
  renoise_t_min: 1
  initial_sampling_mode: rbf_diverse_denoise
  initial_diversity_scale: 20.0
  initial_diversity_start_ratio: 0.8
  truncated_rollout_mode: rbf_diverse
  rollout_diversity_scale: 20.0
  rollout_diversity_start_ratio: 0.6
  rollout_diversity_iters: all
  rollout_diversity_skip_final_steps: 0

backend.libero:
  suite_name: libero_object_swap
  strict_perturbations: true
  max_episode_steps: 720
```

P2 Stage ON 的现有结果为 `3/10`，成功任务是 Task 3、8、9。P2 Stage OFF 为 `0/10`。同时，P2 Stage ON 在 10/10 episode 中均于 step 16--32 首次关闭 guidance，实际行为更接近“短前缀 EDS+RBF 后切回 RDT prior”。本轮保持该阶段控制不变，以隔离 EDS+RBF 内部优化的增量效果。

参考证据：

- `docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-31-libero-pro-object-swap-vlm-stage-recognition-ablation-report.md`
- `docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-12-libero-pro-object-swap-rdt-eds-rbf-report.md`
- `docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-12-rollout-rbf-main-metrics-analysis.md`

### 2.2 已确认的机制事实

已有实验支持以下判断：

1. Initial RBF 和 rollout RBF 都能扩大 3D EEF trajectory diversity，机制无 fallback、nonfinite 或 action-mask violation。
2. RBF scale 增大时 diversity 单调提高，但 environment success 不单调提高；固定 `scale=20` 不是普适最优。
3. 普通 `libero_object` 上，固定 `rollout_diversity_iters=all` 会破坏 exploitation；严格 swap OOD 中的少量成功配置又依赖持续探索，说明需要按 population 状态动态控制 RBF，而不是简单固定开启或关闭。
4. 当前 EDS parent sampling 使用 `softmax((-cost) * temperature)`。在 `temperature=0.1` 和当前 reward 数值范围下，多个 trace 的 score entropy 接近 `log(16)`，parent sampling 接近均匀有放回采样，reward selection pressure 很弱。
5. 每个 action chunk 都重新生成 population，前一 chunk 的高质量 mode 不会显式传递到下一 chunk。
6. 当前 `renoise_t_max -> min` 和 `cem_iters=10` 是预先固定的；action chunk 固定生成并执行 8 个动作，不能在接触敏感阶段提前 replan。

### 2.3 本轮核心研究问题

本轮不再问“RBF 能否增加 diversity”，而是回答：

1. 如何让 reward 真正影响 parent survival，而不立即导致 mode collapse？
2. 如何只在 population 退化或探索不足时施加 RBF？
3. 如何同时保留高 reward elite 和多个可行 trajectory modes？
4. 如何跨 chunk 延续已发现的高质量 mode，减少控制抖动和重复搜索？
5. 如何根据当前搜索状态动态决定 restart 强度、迭代预算和闭环 replanning 频率？

## 3. 设计目标与非目标

### 3.1 目标

- 当前 legacy P2 配置和数值语义保持不变。
- 新机制只能通过显式 mode/profile 启用，不能改变默认值。
- 所有新增组件 mode 同时设为 legacy/none/fresh/fixed 时，resolved config 和执行路径必须等价于 `p2_stage_on`。
- 复用 `_eds_guided_denoise_loop()`、initial RBF、rollout RBF、trajectory projection、action mask、metrics 和 mechanism trace。
- 所有 population 始终保持 `(population_size, 64, 128)`。
- final action 仍来自 policy-denoised RDT sample，并通过现有 LIBERO decoder 执行。
- 新选择与 resampling 逻辑保持 gradient-free；adaptive RBF 仅复用既有 diversity gradient。
- 支持单因素消融与任意合法组合，不复制整套 EDS loop。
- 每项新算法必须先做单因素 OOD 测试；不得先以完整集成结果替代控制变量结论。
- runner 支持 resume、strict validity、独立输出和完整 profile/config fingerprint。
- 使用同一 10-task OOD protocol 判断是否达到 `>=5/10`。

### 3.2 非目标

- 本轮不修改 cached EPS-CoT reward、task-specific guidance 或 keypoint grounding。
- 本轮不修复 VLM Stage Recognition prompt、解析器、状态机或 premature OFF。
- 本轮不启用 Gemini grounding。
- 本轮不改变 VLS 路径。
- 本轮不改变 RDT checkpoint、128D action layout 或 diffusion scheduler 总 inference steps。
- 不将任何新机制设为默认行为。
- 不在达到 object-swap gate 前扩展到 `libero_object_task/env/temp`。

上述非目标很重要：当前 reward 和阶段识别仍是已知 confound。本轮结果只能说明本设计所列 EDS+RBF 内部优化相对当前 P2 的增量作用，不能宣称已经解决完整 steering objective。

## 4. 基线隔离与“分支评估”架构

### 4.1 可选实现方式

#### 方案 A：每个机制独立 Git branch/worktree

优点是代码物理隔离清晰；缺点是五项机制都修改 `_EDSConfig`、`_eds_guided_denoise_loop()`、metrics 和 runner，最终组合时会产生大量重复合并和行为漂移，不利于做组合消融。

#### 方案 B：单个 `algorithm_variant` 分支复制完整 EDS loop

例如为每个实验复制 `_eds_guided_denoise_loop_v2()`。短期直观，但会复制 scoring、mask、trace、fallback 和 scheduler 逻辑；baseline bugfix 很难同步，组合数量也会快速膨胀。

#### 方案 C：组件级 strategy mode + 命名 profile，推荐

保留一个 EDS loop，将变化限定在可组合的策略接口：

```text
parent weighting
parent coverage / elite carryover
rollout diversity controller
chunk population composer
search / execution scheduler
```

每个接口默认调用 legacy helper。runner 中的命名 profile 只负责生成完整配置，不在核心代码中写 method label 特判。

推荐方案 C。它提供与独立 branch 类似的实验隔离，同时允许单因素和组合评估。Git 层面只需要在当前实验 branch 上形成独立 implementation commit；算法变体由 Hydra config 和 runner profile 隔离。

### 4.2 兼容原则

必须满足以下 baseline preservation gate：

1. 不带新字段的历史 P2 config 可直接解析。
2. 所有新 mode 的默认值均选择 legacy 行为。
3. 在相同 tensor、seed 和 scheduler state 下，legacy mode 的 parent indices、population、scores、selected index 与修改前一致。
4. 新 helper 不得被 VLS 调用。
5. baseline output directory 保持只读；新 runner level 使用新 root。
6. runner 遇到已存在但 config fingerprint 不同的目录必须判 invalid 或归档，不得覆盖。

新增组件全部关闭时，P2 的显式 resolved config 应为：

```yaml
parent_weighting_mode: legacy_temperature
parent_coverage_mode: none
rollout_diversity_control_mode: fixed
chunk_population_mode: fresh
search_schedule_mode: legacy_linear
execution_horizon_mode: fixed
```

这里的“新增组件全部关闭”不代表关闭 P2 已有的 initial/rollout RBF。P2 原有 `truncated_rollout_mode=rbf_diverse`、rollout scale 20、start ratio 0.6 和 `rollout_diversity_iters=all` 仍保持不变；关闭的是本设计新增的 adaptive/coverage/memory/schedule 分支。

### 4.3 推荐策略接口

```text
_eds_compute_parent_weights(...)
_eds_select_parent_plan(...)
_eds_resolve_rollout_diversity_control(...)
_eds_compose_chunk_initial_population(...)
_eds_resolve_search_schedule(...)
_resolve_execution_horizon(...)
```

这些 helper 返回结构化 plan/info；`_eds_guided_denoise_loop()` 仍负责 population shape、mask、scheduler、score 和 trace 的统一控制。

## 5. 优化一：修正 EDS 有效选择压力

### 5.1 当前问题

当前 parent probability 为：

```python
logits = (-costs) * temperature
probabilities = softmax(logits)
```

这里的 `temperature` 实际扮演 inverse-temperature/beta 的角色。`temperature=0.1` 会缩小本来就较小的 reward spread，使 score entropy 接近最大值，EDS evolutionary resampling 很可能退化为近似均匀 bootstrap。

不应静默改变 `temperature` 的历史语义。推荐保留 legacy 路径，并新增 adaptive ESS weighting。

### 5.2 Adaptive ESS weighting

```text
rewards = -costs
z = robust_normalize(rewards)
find beta by bisection so ESS(softmax(beta * z)) / N ~= target_ratio
sample remaining parent slots from resulting probabilities
```

推荐 robust normalization 固定使用 median/MAD；MAD 退化时回退 mean/std；全部 reward 相等时使用均匀分布并记录 `degenerate_reward=true`，不能伪造 selection pressure。

ESS 定义：

```text
ESS = 1 / sum_i(p_i^2)
```

首版不直接替换 final argmin selection，只改变 iterative parent weighting。

### 5.3 新配置

| 字段 | 默认值 | 新模式推荐值 | 含义 |
|---|---|---|---|
| `parent_weighting_mode` | `legacy_temperature` | `adaptive_ess` | legacy softmax 或 ESS-controlled softmax |
| `selection_ess_target_ratio` | `0.6` | `0.5`, `0.7` | 目标 ESS/N |
| `selection_beta_max` | `100.0` | 固定 | beta 搜索上界 |
| `selection_bisection_steps` | `24` | 固定 | beta 二分次数 |

不新增另一个 `selection_enabled` flag，mode 已经表达开关。

### 5.4 Metrics

- `parent_weighting_mode`
- `selection_beta`
- `selection_ess`
- `selection_ess_ratio`
- `selection_entropy_normalized`
- `selection_max_probability`
- `selection_degenerate_reward`
- `parent_count_by_source_rank`

## 6. 优化二：从固定 RBF 改为自适应 RBF

### 6.1 目标

固定 RBF 的问题不是无法产生 diversity，而是无法判断何时已经足够。Adaptive RBF 应把 RBF 当作 population degeneracy controller：只在 EEF mode coverage 低于目标带时开启，并随 EDS iteration 和 reward confidence 衰减。

### 6.2 Diversity reference 与 target band

为避免使用跨任务不稳定的绝对米制阈值，每个 chunk 用 initial final population 建立 reference：

```text
D_ref = initial_eef_diversity_final
D_low = target_ratio * (1 - band_ratio) * D_ref
D_high = target_ratio * (1 + band_ratio) * D_ref
```

每轮 rollout 前计算 `D_current`：

- `D_current < D_low`：允许较强 RBF；
- `D_low <= D_current <= D_high`：只做维持或关闭；
- `D_current > D_high`：关闭 RBF，优先 exploitation；
- reward 出现高置信 elite 时进一步衰减；
- reward 退化且 diversity 低时允许恢复 RBF。

推荐 scale controller：

```text
deficit = clamp((D_low - D_current) / max(D_low, eps), 0, 1)
iter_decay = max(decay_floor, 1 - iter_idx / max(cem_iters - 1, 1))
confidence_decay = 1 - reward_confidence
scale = clip(scale_max * deficit * iter_decay * confidence_decay,
             scale_min, scale_max)
```

单因素 adaptive-RBF 组仍可作用于全部 particles，以隔离 controller 效果；完整集成组只对非 elite offspring 施加 RBF。

### 6.3 新配置

| 字段 | 默认值 | 推荐值 | 含义 |
|---|---|---|---|
| `rollout_diversity_control_mode` | `fixed` | `adaptive_band` | 保留现有 fixed 行为或启用 controller |
| `rollout_diversity_target_ratio` | `1.0` | `0.8`, `1.0` | 相对 chunk initial final diversity 的目标 |
| `rollout_diversity_band_ratio` | `0.2` | 固定 | 目标带宽 |
| `rollout_diversity_scale_min` | `0.0` | 固定 | 自适应最小 scale |
| `rollout_diversity_scale_max` | `20.0` | `10.0`, `20.0` | 自适应最大 scale |
| `rollout_diversity_decay_floor` | `0.25` | 固定 | 后期最低 iteration 系数 |

`truncated_rollout_mode` 继续负责选择 baseline/RBF rollout；`rollout_diversity_control_mode` 只决定 RBF 已启用时使用 fixed 还是 adaptive scale，二者不冗余。

### 6.4 Fallback

Adaptive controller 计算失败、reference 非 finite 或 diversity gradient 失败时，必须 warning，并回到当前 rollout call 的 fixed/legacy baseline 路径。所有 fallback 写入 metrics；不得静默使用 scale 20。

### 6.5 Metrics

- per-iteration `diversity_reference/low/high/current`
- `adaptive_rbf_triggered`
- `adaptive_rbf_trigger_reason`
- `adaptive_rbf_scale_requested/applied`
- `adaptive_rbf_particle_count`
- `adaptive_rbf_active_iter_ratio`
- `diversity_band_hit_ratio`
- 既有 before/after/final EEF diversity 与 endpoint spread

## 7. 优化三：Diversity-Aware Resampling

### 7.1 设计原则

RBF 在连续 trajectory space 推开粒子；diversity-aware resampling 解决离散 parent survival。二者互补，不能只依靠持续增强 RBF 来补救 parent duplication。

推荐将 parent selection 分成三个来源：

1. **elite carryover**：保留最高 reward 的少量原始粒子，不经过本轮 renoise/RBF；
2. **diverse anchors**：在 reward-eligible pool 内按 3D EEF trajectory k-center/FPS 选择不同 mode；
3. **weighted offspring**：剩余 slots 按 legacy 或 adaptive-ESS probability 有放回采样，再 renoise/rollout。

这里的 FPS 只用于 EDS iterative parent coverage，与 initial oversampling/FPS 方案无关。

### 7.2 Reward-constrained k-center

```text
eligible = particles with reward >= configured quantile
anchor_0 = best reward particle
anchor_k = argmax min_distance(feature_i, selected_anchors)
tie-break by higher reward, then lower original index
```

feature 固定为与 RBF 一致的 3D EEF trajectory flatten，不新增 action-space metric。通过 reward quantile 限制 outlier，不允许纯 FPS 从最低 reward 尾部选极端轨迹。

推荐 population 16 的均衡配置：

```text
2 unchanged elites
4 unique diverse anchor parents
10 weighted offspring
```

如果 elite 同时属于 anchor，去重后补足 anchor 数。最终 population 仍为 16。

### 7.3 新配置

| 字段 | 默认值 | 推荐值 | 含义 |
|---|---|---|---|
| `parent_coverage_mode` | `none` | `eef_kcenter` | 是否增加 trajectory mode anchors |
| `parent_anchor_count` | `0` | `2`, `4` | 每轮 anchor parents 数量 |
| `parent_anchor_reward_quantile` | `0.5` | 固定 | anchor eligible reward 下界 |
| `elite_carryover_count` | `0` | `1`, `2` | 不经本轮 renoise/RBF 的 elites |

### 7.4 处理流程

为了不复制 loop，每轮形成 `EDSParentPlan`：

```text
elite_indices
anchor_parent_indices
sampled_parent_indices
offspring_slot_count
```

只有 anchors/weighted parents 生成 offspring；elite 在 rollout 后与 offspring concatenate，再统一 apply mask、score 和 trace。scheduler particle history 必须在 offspring resampling 后正确 reset；elite 不共享 scheduler history。

### 7.5 Metrics

- `elite_carryover_count_observed`
- `anchor_count_observed`
- `anchor_unique_ratio`
- `anchor_min_pairwise_eef_distance`
- `parent_mode_coverage`
- `offspring_unique_parent_ratio`
- `elite_survival_to_final`
- `selected_source = elite|anchor_offspring|weighted_offspring`

## 8. 后续独立优化：Quality-Diversity EDS（本轮排除）

> **范围声明：** 以下内容只保留为后续独立算法研究依据，不属于本轮 implementation plan、配置扩展、测试矩阵或 OOD 实验。本轮不新增 `qd_archive_mode`，不实现 archive，不生成 QD pretest/formal/integration job。后续启动 QD-ED 前必须另写独立 design、implementation plan，并以本轮最优非 QD 方法作为新 baseline。

### 8.1 理论来源与适配判断

Quality-Diversity（QD）不是单纯最大化 pairwise distance，而是在用户定义的低维 behavior descriptor（BD）空间中维护 archive，并在每个 niche/cell 内保留当前最高 reward elite。MAP-Elites 是最典型的 archive-based QD 方法；其核心目标是同时获得 coverage 和每个 niche 内的 quality，而不是只返回一个全局最优个体。

参考：

- Mouret and Clune, [*Illuminating Search Spaces by Mapping Elites*](https://arxiv.org/abs/1504.04909)
- Cully and Demiris, [*Quality and Diversity Optimization: A Unifying Modular Framework*](https://arxiv.org/abs/1708.09251)

QD 与当前 EDS 的接口天然对应：

| QD 概念 | 当前 EDS 对应项 |
|---|---|
| solution/genotype | `(64, 128)` RDT action sample |
| fitness/quality | `_eds_score_population_as_cost()` 的 reward |
| behavior descriptor | 由 `_rdt_sample_to_trajectory_3d()` 构造的低维 EEF descriptor |
| archive elite | 每个 descriptor cell 内最高 reward action |
| mutation operator | 现有 resample -> renoise -> truncated denoise rollout |
| final output | archive 中全局最高 reward action |

因此 QD-ED 不需要改变 RDT policy、reward function 或 diffusion mutation operator；它主要替换 EDS 的 parent survival/resampling 机制。理论上，它能够阻止所有 lineage 在多轮 resampling 中集中到同一个 behavior mode，并通过 archive 中的 stepping stones 探索当前 reward landscape 的多个局部区域。

### 8.2 对当前 P2 OOD 性能的潜在作用

QD-ED 对当前 P2 有合理的正向假设：

1. 当前 softmax selection pressure 很弱，但有放回采样仍可能重复 parent；QD 按 cell 保留 elite，可避免不同 approach modes 在后续 iteration 中被随机丢失。
2. P2 使用固定强 rollout RBF 持续生成多样 children，但当前 EDS 没有长期保存“每个 mode 中最好动作”的结构；QD archive 可以把 RBF 产生的 diversity 转化为可继承的 niche elites。
3. swap OOD 可能存在 deceptive/local reward landscape，例如从不同侧面接近同一目标、绕开 clutter 或 basket。单一全局 reward 排名可能过早集中，QD 更有机会保留后续可用的 stepping stones。
4. 单个 chunk 的预算约为 initial 16 candidates 加 10 轮、每轮 16 children，约 176 次已有 reward evaluation。4x4 archive 只有 16 cells，计算预算在机制上足以产生 archive turnover，不需要额外 policy denoise。

但收益不能保证，且上限受以下事实限制：

- P2 Stage ON 通常只在 episode 开头 2--4 个 chunks 运行 EDS，QD 的实际作用窗口较短；
- 当前 reward/cached guidance 不适配所有 swap task，QD 只能更充分搜索当前 reward，不能修正错误 objective；
- descriptor 如果与真正成功行为不对齐，archive 会浪费 slots 保存“不同但无用”的动作；
- `population_size=16` 很小，过细 cell 划分会导致 archive 稀疏；
- 当前 action scoring horizon 只有 8 steps，QD 不能直接优化完整抓取后运输和放置结果。

结论：QD-ED 理论上有可能提高 P2 的 OOD 成功率，尤其适合解决“RBF 生成了 mode，但 EDS 多轮迭代没有持续保留 mode”的问题；其潜力高于继续增大固定 RBF scale，但不应预期它单独解决所有失败或必然将 `3/10` 提升到 `5/10`。

### 8.3 MVP Behavior Descriptor

首版 descriptor 必须低维、可解释、在一个 chunk 内固定边界。推荐：

```text
b(a) = [endpoint_x - target_x,
        endpoint_y - target_y]
```

即 target-relative EEF endpoint XY。理由：

- 它直接表示从目标不同侧面接近的 behavior mode；
- 不把完整 `H*3` trajectory 离散成高维 cell；
- 不把 target distance 本身作为主要 BD，减少 quality 与 diversity 维度重复；
- 4x4 grid 正好最多 16 cells，与 population size 对齐。

每个 chunk 在 initial population 上计算 descriptor 的 `q05/q95` robust bounds，向两侧扩展 10%，并以 initial median 为中心将每轴 span 扩展到至少 `0.08 m`，随后在该 chunk 的所有 EDS iterations 中固定 bounds。禁止每轮重算边界，否则同一 cell 的语义会漂移。超出边界的 descriptor 进入相应 edge cell，同时记录 overflow ratio。

最小物理 span 是必要的防伪约束：如果直接把一个已经坍塌、仅有毫米级差异的 population 自适应拉伸到 4x4 网格，occupancy 会虚高，但 absolute EEF diversity 并未改善。正式分析必须同时报告 archive coverage、绝对 endpoint spread 和 bounds；不能单凭 occupied cells 宣称 QD 增加了行为覆盖。`0.08 m` 先在 mechanism pretest 中做“是否覆盖有效工作区而不大量 overflow”的校准，只允许在正式 Stage A 前冻结一次，且必须写入 manifest。

首版不使用 Z 轴或 3D 4x4x4 grid，因为 64 cells 相对 16-particle population 和短 EDS budget 过于稀疏。Z/trajectory-shape descriptor 只作为后续实验候选。

### 8.4 QD Archive 数据结构

每个 `select_action` chunk 创建一个 archive：

```text
cell_id -> {
    action: Tensor[64, 128],
    reward: scalar,
    descriptor: Tensor[2],
    source_iter: int,
    parent_cell: optional cell_id,
}
```

MVP 每 cell 只保留 1 个 elite。archive 默认只在当前 chunk 的 10 个 EDS iterations 内持久化；不与跨-chunk memory 混为同一个状态。后续集成组可以用 memory candidates 初始化新 chunk archive，但 archive cell 本身仍按 chunk 重建。

### 8.5 QD-ED 单步流程

```text
fresh P2 initial population
  -> score reward and compute BD
  -> fill/replace archive cells

for EDS iter i:
  -> sample N parent slots from occupied cells
  -> use existing renoise schedule
  -> use existing fixed P2 RBF truncated rollout
  -> score children and compute BD
  -> child replaces cell elite only when reward is higher
  -> keep archive across iterations

return global highest-reward archive elite
```

为了维持 exploitation，设计两个单因素 parent samplers：

- `uniform_cells`：100% parent slots 在 occupied cells 间近似均匀分配；
- `quality_mix25`：75% uniform-cell parents，25% 从 archive top-quality cells 采样。

同一 cell 被分配多个 offspring slots 是允许的；这些 offspring 通过独立 renoise noise 产生不同 children。archive 占用 cell 少于 2 或 descriptor 无效时，该 iteration 必须 warning 并回到 P2 legacy resampling，同时记录 fallback。

### 8.6 新配置与互斥规则

| 字段 | 默认值 | 推荐测试值 | 含义 |
|---|---|---|---|
| `qd_archive_mode` | `none` | `grid_archive` | 是否启用 QD archive |
| `qd_descriptor` | `target_relative_endpoint_xy` | 固定 | behavior descriptor |
| `qd_grid_shape` | `[4, 4]` | 固定 | 2D cell 数量 |
| `qd_cell_capacity` | `1` | 固定 | 每 cell elite 数 |
| `qd_parent_sampling` | `uniform_cells` | `uniform_cells`, `quality_mix25` | archive parent 分配 |
| `qd_quality_parent_fraction` | `0.25` | 固定 | mix 模式的 quality fraction |
| `qd_bounds_quantiles` | `[0.05, 0.95]` | 固定 | chunk-local robust bounds |
| `qd_min_axis_span_m` | `0.08` | pretest 后冻结 | 防止微小差异被网格归一化成虚假 coverage |

首版互斥规则：

```text
qd_archive_mode=grid_archive requires:
  parent_weighting_mode=legacy_temperature
  parent_coverage_mode=none
  elite_carryover_count=0
```

原因是 QD archive 已同时定义 parent sampling、niche coverage 和 per-cell elitism。若同时启用 adaptive ESS 或 k-center anchors，将无法判断收益来自 QD archive 还是额外 selection pressure。Adaptive RBF、chunk memory 和 adaptive schedule 与 QD 在后续集成阶段可以组合。

### 8.7 QD Metrics 与可视化

- `qd_archive_enabled`
- `qd_descriptor`
- `qd_occupied_cells`
- `qd_coverage_ratio`
- `qd_cell_occupancy_entropy`
- `qd_archive_insertions/replacements/rejections`
- `qd_archive_turnover_ratio`
- `qd_parent_cell_unique_ratio`
- `qd_bounds_xy`、`qd_descriptor_overflow_ratio`
- `qd_endpoint_spread_abs_m`
- `qd_selected_cell`
- `qd_selected_cell_reward`
- `qd_best_reward`
- `qd_fallback_used/reason`
- per-iteration 4x4 archive heatmap
- trajectories colored by cell
- cell occupancy/elite reward curve

经典 QD-score 需要非负或统一 offset 才便于跨 chunk 比较；当前 reward 多为负值，因此 MVP 不用未经校准的 reward sum 作为主指标。主机制指标使用 coverage、archive turnover、global best reward 和 environment success。

### 8.8 与 Diversity-Aware Resampling 的区别与联系

| 维度 | Diversity-Aware Resampling | QD-ED |
|---|---|---|
| 状态范围 | 每轮重新选择，无状态 | archive 跨 EDS iterations 持久化 |
| diversity 表达 | 完整 EEF trajectory 的连续 pairwise distance | 低维 BD 的离散 cells |
| quality 约束 | reward quantile 后选 k-center anchors | 每个 cell 内只保留最高 reward elite |
| parent 构成 | elite + anchors + weighted offspring | occupied-cell elites 产生 offspring |
| 对 softmax 的关系 | 可与 adaptive ESS 组合 | 首版替换 weighting/coverage 两个环节 |
| mode 保留强度 | 中等，下一轮可能重新丢失 | 强，cell elite 显式保留到 chunk 结束 |
| 描述符敏感性 | 较低 | 高，BD/cell 边界决定探索方向 |
| 小 population 适配 | 较好 | 需控制为小 archive，例如 4x4 |
| 工程复杂度 | 低到中 | 中到高 |
| 典型风险 | anchors 仍可能被 rollout 改写 | 保存低价值 niches、archive 稀疏 |

二者的联系是：都试图把 EEF-space diversity 从“瞬时粒子距离”变成 parent survival 约束，并可共享 trajectory projection、distance/descriptor、reward、trace 和 qualitative 工具。Diversity-Aware Resampling 可以看作轻量、archive-free 的局部 QD 近似；QD-ED 则进一步加入明确 niche、跨 iteration memory 和 per-niche competition。

### 8.9 哪个更适合当前 P2

对于当前 P2 的第一版工程落地，**Diversity-Aware Resampling 更适合作为优先实现的低风险默认候选**：它直接复用现有 3D EEF distance，不需要选择 cell 边界，且在 16-particle、短 guidance window 下更节省样本。

**QD-ED 是更高潜力但更高方差的独立候选**：如果 OOD 失败确实来自多个 approach niches 中的 deceptive local optima，archive persistence 理论上比 k-center anchors 更强；如果 BD 与成功无关，QD 会比 k-center 更差。

后续独立 QD 评测不应先验宣称某一个“绝对更优”。届时应以本轮最优非 QD 方法为 baseline，使用相同 seeds 对 QD archive 做单因素比较；只有 QD 同时满足 coverage/turnover 机制 gate 且 SR 不低于 baseline 时，才讨论与其他组件集成。本轮不执行这项比较。

## 9. 优化四：跨 Chunk Population Memory

### 9.1 目标

将上一 chunk 已发现的 selected/elite/diverse modes 作为下一 chunk 的部分 warm start，同时保留足够 fresh policy samples 适应新 observation。memory 只在同一 episode 内存在，不写入通用 initial population cache。

### 9.2 Memory 内容

每个完成的 EDS chunk 保存 detached state：

```text
final population
final scores/rewards
selected index
elite and anchor indices
current stage
guidance state
executed action count
episode/task identity
```

默认只保留最近一个 chunk，避免形成长期陈旧 archive。

### 9.3 Warm-start composition

下一 chunk 仍先生成完整 fresh policy population，再进行 composition：

1. 从上一 chunk 取 selected、top elite 和 diverse anchors；
2. 按本 chunk 实际执行步数左移 64-step RDT sample；
3. 尾部使用 fresh sample 对应部分填充，不使用全零动作；
4. apply action mask；
5. 以 `memory_renoise_steps` 做 forward noise + current-condition truncated denoise；
6. 取 `K_memory` memory candidates，与 `N-K_memory` fresh RBF candidates 合并；
7. 统一 score 后进入 EDS loop。

推荐首版 `K_memory=4/16`；`8/16` 作为更强 memory 单因素。

### 9.4 Reset 与失效条件

下列情况必须清空 memory：

- episode/task reset；
- Stage Recognition 改变 stage；
- guidance OFF 后重新 ON；
- memory 非 finite 或 shape/mask 不匹配；
- previous chunk execution error；
- observation/state jump 超过现有可验证阈值；
- memory score 全部显著差于 fresh population。

失效应记录 reason。正常 episode reset 不输出 warning；异常失效必须 warning。

### 9.5 Cache 兼容

- `use_initial_cache/save_initial_cache` 只作用于 fresh base population；
- memory composition 位于 cache load/generation 之后；
- memory 不写入 initial cache；
- metrics 和 config fingerprint 必须记录 memory mode；
- baseline `chunk_population_mode=fresh` 时不得创建或读取 memory。

### 9.6 新配置

| 字段 | 默认值 | 推荐值 | 含义 |
|---|---|---|---|
| `chunk_population_mode` | `fresh` | `warm_start_mix` | legacy fresh 或跨 chunk 混合 |
| `chunk_memory_fraction` | `0.0` | `0.25`, `0.5` | memory population 比例 |
| `chunk_memory_renoise_steps` | `2` | 固定 | 在当前 cond 下重适配强度 |
| `chunk_memory_reward_guard_quantile` | `0.25` | 固定 | memory 明显劣于 fresh 时拒绝 |

### 9.7 Metrics

- `chunk_memory_available/used`
- `chunk_memory_candidate_count`
- `chunk_memory_fraction_observed`
- `chunk_memory_reset_reason`
- `chunk_memory_acceptance_ratio`
- memory/fresh initial reward 与 diversity
- final selected candidate source
- chunk-to-chunk selected trajectory distance

## 10. 优化五：自适应 Renoise、Iteration 与 Execution Horizon

### 10.1 Ownership 边界

Renoise 和 EDS iteration 属于 `core/rdt_policy_steer.py`；execution horizon 属于 `main.py` 的环境闭环。不得通过改变 `_action_chunk_horizon=8` 来实现短执行，否则会改变 RDT decode、trajectory scoring 和已有 metrics。推荐始终生成/score 8-step action chunk，只动态决定本 chunk 执行前 2、4 或 8 个动作后重新规划。

### 10.2 Adaptive renoise

保留 P2 的允许范围 `1..3`，根据当前搜索状态选择：

```text
t=3: diversity below band and reward has no clear improving mode
t=2: default uncertain/local exploration
t=1: stable elite, reward improving, diversity inside band
```

决定因素只使用已有在线量：reward improvement、robust best-vs-population margin、EEF diversity band、selected-mode stability。不得读取 simulator success oracle。

### 10.3 Adaptive EDS iterations

最大值仍为 `cem_iters=10`。推荐：

- `min_iters=4`；
- best reward improvement 小于阈值持续 `patience=2`；
- selected mode 连续稳定；
- diversity 已进入 target band；
- 满足全部条件后 early stop；
- 若 reward 仍改善或 diversity 失控，最多运行 10 轮。

这里的 EDS iteration 数与 `rollout_diversity_iters` 不同，metrics 命名必须明确区分。

### 10.4 Adaptive execution horizon

推荐 stage/distance-aware prefix execution：

| 条件 | 执行步数 |
|---|---:|
| guidance ON 且距 scoring target 较远 | 8 |
| 接近 target 或即将发生 gripper transition | 4 |
| gripper close/open 附近、接触敏感或 reward 快速变化 | 2 |
| guidance OFF 且无交互事件 | 8 |

首版阈值使用当前 EDS target distance 与 gripper edge signal，并记录触发原因。Stage Recognition 切换后的第一个 chunk 强制最多执行 4 步，减少错误 stage 决策的开环影响。

### 10.5 新配置

EDS config：

| 字段 | 默认值 | 推荐值 | 含义 |
|---|---|---|---|
| `search_schedule_mode` | `legacy_linear` | `adaptive` | 固定 linspace 或在线 schedule |
| `adaptive_min_cem_iters` | `4` | 固定 | 最少 EDS iterations |
| `adaptive_early_stop_patience` | `2` | 固定 | plateau patience |
| `adaptive_reward_improvement_eps` | `1e-3` | 预检校准 | reward 改善阈值 |

Main config：

| 字段 | 默认值 | 推荐值 | 含义 |
|---|---|---|---|
| `execution_horizon_mode` | `fixed` | `adaptive_prefix` | 固定执行 8 步或动态执行前缀 |
| `execution_horizon_far` | `8` | 固定 | 远距离执行数 |
| `execution_horizon_near` | `4` | 固定 | 接近交互区执行数 |
| `execution_horizon_contact` | `2` | 固定 | 接触/夹爪切换附近执行数 |
| `execution_near_distance` | `0.08` | mechanism pretest 校准 | near 阈值，米 |
| `execution_contact_distance` | `0.04` | mechanism pretest 校准 | contact 阈值，米 |

### 10.6 Metrics

- per-iteration `resolved_renoise_steps` 和 trigger reason
- `eds_iters_executed`
- `early_stop_used/reason`
- `execution_horizon_resolved`
- execution-horizon trigger reason
- replans per episode
- action chunks interrupted at 2/4/8
- select latency、episode wall-clock 与 API query latency分别统计

## 11. 完整集成算法

本轮集成采用 coverage-aware parent-selection backend：adaptive ESS weighting + reward-constrained k-center + elite carryover。所有组成模块必须先在 Stage A 中独立验证，不能在首轮单因素实验中叠加。

推荐数据流：

```text
fresh initial population via existing RBF initial sampler
  -> optional cross-chunk memory composition
  -> action mask + initial scoring
  -> for EDS iter:
       compute adaptive ESS parent weights
       build elite + diverse anchors + weighted offspring plan
       resolve adaptive renoise for offspring
       renoise offspring
       resolve adaptive RBF scale from diversity band/reward confidence
       rollout offspring; elites bypass this iteration's perturbation
       concatenate elites + offspring
       action mask + score
       update memory candidates / metrics
       adaptive early-stop check
  -> final argmax reward selection
  -> save chunk memory
  -> main resolves execution prefix 2/4/8
  -> execute prefix and replan
```

Stage B 只有在对应单因素机制 gate 通过后才能组合其他组件。任何集成配置都必须先写入不可变 integration manifest；禁止先看集成结果再更换组成模块。

所有 adaptive decision 都必须写入 mechanism trace，使结果可以解释为具体控制决策，而不是只看到最终 SR。

## 12. 代码插入点

### 12.1 `core/rdt_policy_steer.py`

- 扩展 `_EDSConfig` 和 `_resolve_eds_config_with_reference_defaults()`。
- 保留 `_eds_sampling_probabilities_from_cost()` 作为 legacy helper。
- 新增 adaptive ESS weighting helper。
- 将 parent resampling 抽为返回 `EDSParentPlan` 的 helper。
- 在 `_eds_guided_denoise_loop()` 中组合 elite/offspring，不复制完整 loop。
- 为 rollout RBF 增加 fixed/adaptive controller dispatch。
- 在 initial population 后增加可选 memory composer。
- 增加 episode/stage reset 时的 memory reset hook。
- 将固定 trunc schedule resolution 抽为 legacy/adaptive helper。

### 12.2 `main.py`

- 保留 `_action_chunk_horizon=8`。
- 每个新 chunk 解析 `execution_horizon_resolved`。
- 当 `action_executed == resolved_horizon` 时 replan，而不是永久改变 action chunk shape。
- stage/guidance change 时通知 policy reset chunk memory。
- trace 每个 chunk 的 horizon 和 trigger reason。

### 12.3 Metrics 与 trace

- `core/eds_eval_metrics.py`：增加 selection、coverage、memory、adaptive schedule 字段。
- `core/eds_mechanism_trace.py`：增加 parent source、anchor、elite、memory source、adaptive decision 信息。
- qualitative visualization 区分：legacy/fresh、memory、elite、anchor、weighted offspring。

### 12.4 Runner

扩展 `scripts/rdt_eds_eval_runner.py`：

- 新 Stage A level：`p2_adaptive_eds_rbf_stage_a`；
- 新 Stage B level：`p2_adaptive_eds_rbf_stage_b`，从 immutable integration manifest 读取最多两个 profile；
- 新 pretest level：`p2_adaptive_eds_rbf_pretest`；
- 独立 method registry；
- Stage A matrix count test 固定为 11；Stage B registry 最多生成 2 个 manifest 中已声明的集成 job；
- Hydra overrides 全量写出新 mode；
- resume validity 检查 config fingerprint；
- baseline/new profiles 均使用新 output root，避免引用旧输出造成 horizon/API 环境差异；
- GPU 首选池固定为 `[2, 3, 4, 5]`，优先调度其中空闲设备；全部繁忙时等待，不得未经批准扩展到 GPU 0、1、6、7。

## 13. 实验矩阵

### 13.1 固定条件

| 项目 | 设置 |
|---|---|
| Benchmark | LIBERO-PRO OOD |
| Suite | `libero_object_swap` |
| Strict perturbation | `true` |
| Tasks | 固定 0--9 |
| Episodes per job | 10 |
| Max steps | 720 |
| Root seed | 0 |
| Episode seeds | 与 Stage Recognition A/B 报告中的 10 个 seeds 精确配对 |
| Stage Recognition | ON |
| Gemini grounding | OFF |
| Cached guidance | 与 P2 Stage ON 相同 |
| Initial RBF | scale 20, start 0.8 |
| GPUs | 优先使用 `[2, 3, 4, 5]` 中的空闲 GPU；无空闲则等待，其他 GPU 需显式批准 |

API credential 只能通过运行时环境变量注入，禁止写入 config、log、manifest、report 或 Git。runner 必须执行不回显 credential 的健康检查。

### 13.2 阶段 A：单因素正式实验

| Label | Weighting | Adaptive RBF | Resampling | Memory | Adaptive schedule | 目的 |
|---|---|---|---|---|---|---|
| `p2_legacy_stage_on_rerun` | legacy | fixed P2 | none | fresh | legacy | 本轮严格配对 `p2_stage_on` baseline |
| `p2_sel_ess05` | ESS 0.5 | fixed P2 | none | fresh | legacy | 单测较强选择压力 |
| `p2_sel_ess07` | ESS 0.7 | fixed P2 | none | fresh | legacy | 单测较保守选择压力 |
| `p2_adaptrbf_t08_s10` | legacy | target 0.8, max 10 | none | fresh | legacy | 单测保守 adaptive RBF |
| `p2_adaptrbf_t10_s20` | legacy | target 1.0, max 20 | none | fresh | legacy | 单测均衡 adaptive RBF |
| `p2_divres_k2_e1` | legacy | fixed P2 | k-center 2, elite 1 | fresh | legacy | 单测轻量 mode preservation |
| `p2_divres_k4_e2` | legacy | fixed P2 | k-center 4, elite 2 | fresh | legacy | 单测强 mode preservation |
| `p2_memory25` | legacy | fixed P2 | none | 25% | legacy | 单测保守跨 chunk warm start |
| `p2_memory50` | legacy | fixed P2 | none | 50% | legacy | 单测强 memory |
| `p2_schedule_balanced` | legacy | fixed P2 | none | fresh | adaptive 8/4 | 单测自适应搜索与保守执行 |
| `p2_schedule_contact` | legacy | fixed P2 | none | fresh | adaptive 8/4/2 | 单测接触阶段高频 replan |

Stage A 固定规模：`11 jobs x 10 episodes = 110 episodes`。11 组全部执行，不根据早期 success 临时裁剪。每个单因素组只修改表中对应组件，其他新增 strategy mode 必须使用 P2 legacy/off 值。

### 13.3 阶段 B：预注册集成实验

Stage A 全部完成并生成单因素报告后，最多运行 2 个集成 job：

| Slot | 组成规则 | 目的 |
|---|---|---|
| `p2_integrated_full` | 每类选择一个通过资格 gate 且相互兼容的最佳设置 | 检查全部合格组件的叠加收益 |
| `p2_integrated_minimal` | 只组合两个表现最好的兼容单因素 | 判断完整堆叠是否产生干扰 |

单因素进入集成的资格规则必须在读取 Stage B 结果前确定：job 有效且无 silent fallback，并满足以下至少一项：

1. SR 高于本轮 `p2_legacy_stage_on_rerun`；
2. SR 不低于 baseline，同时对应主机制指标显著改善、没有新增 task-level regression，且 median latency 不超过 baseline 的 1.5 倍。

若多个设置同时合格，先按 paired success 增量排序，再按该组件的主机制指标、median latency 和配置复杂度依次 tie-break。Stage B 启动前必须保存包含具体 overrides、Stage A 证据和选择理由的 `integration_manifest.json`，之后不得依据 Stage B 中间结果换参。

Stage B 最大规模：`2 jobs x 10 episodes = 20 episodes`；连同 Stage A，正式实验上限为 `13 jobs / 130 episodes`。如果某个 slot 没有满足资格的组件，应在 manifest 中记为 `not_eligible`，不得用较差参数补足数量。

### 13.4 为什么需要本轮 baseline rerun

不能只引用历史 P2 `3/10`：Stage Recognition 使用外部 API，运行时间、query 成功率和阶段切换具有额外波动。本轮 baseline 必须与新 profile 使用同一代码 revision、runner、seed、720-step budget 和 validity logic 重跑。历史 `3/10` 只作为 sanity reference。

## 14. 测试与执行流程

### 14.1 Unit tests

至少覆盖：

- legacy config 默认值与历史解析；
- legacy parent indices 数值回归；
- adaptive ESS 达到目标且 reward 排序单调；
- equal reward 退化路径；
- adaptive RBF target-band decision；
- k-center anchors 唯一、reward guard 和 deterministic tie-break；
- elite bypass renoise/RBF；
- memory shift/pad/mask/reset/cache compatibility；
- adaptive renoise resolution 和 early stop；
- execution prefix 2/4/8 不改变 action chunk shape；
- VLS path 不进入新 helper；
- runner Stage A matrix 数量为 11、Stage B 数量不超过 2，且 integration manifest 不可变；
- resume、config fingerprint、strict validity 和 report writer。

### 14.2 Mechanism pretest

先选取每条 strategy 分支的一个代表配置：baseline、ESS、adaptive RBF、k-center、memory、adaptive schedule，在 Task `[0, 8]` 各跑 1 episode，共 `6 profiles x 2 tasks = 12 episodes`。预检只验证分支和观测机制，不纳入正式 SR，也不能用于删除 Stage A 的合法组别。

必须确认：

- adaptive ESS 的实际 ESS/N 与 target 一致；
- adaptive RBF scale 至少出现两个不同值，且不是始终 20；
- anchor/elite 数量与 source trace 正确；
- 第二个 chunk 起 memory 实际使用；
- stage change 时 memory reset；
- renoise/iteration/horizon 至少有一次动态变化；
- 0 nonfinite、0 mask violation、0 silent fallback；
- qualitative 图能区分 fresh/memory/elite/anchor/offspring。

预检失败只阻止对应代码错误进入正式实验；不得根据 Task 0/8 是否成功选择性删除合法 profile。Stage A 结束并生成 integration manifest 后，对每个 Stage B 集成 profile 再用 Task `[0, 8]` 做相同机制预检，确认组件实际激活且没有互斥配置泄漏。

### 14.3 Formal OOD evaluation

机制 gate 通过后，通过可断点续跑 runner 将 Stage A 全部 11 jobs 排队执行，不做结果驱动的提前淘汰。完成 Stage A 报告、资格判定和 immutable integration manifest 后，再运行最多 2 个 Stage B jobs。

runner 优先使用 `[2, 3, 4, 5]` 中当前空闲 GPU，最多 4 个并发 job；这些 GPU 全部繁忙时等待，不抢占既有任务，也不自动使用 GPU 0、1、6、7。单个 job 失败不停止剩余任务。

## 15. 输出、证据与报告

### 15.1 输出目录

```text
outputs/ood_eval/p2_adaptive_eds_rbf/
  stage_a/<method_label>/
  stage_b/<method_label>/
  pretest/<method_label>/
```

home 根盘当前只剩约 `56 GiB`，且现有 worktree `outputs` 已占约 `130 GiB`。本轮正式实验按历史 Level-4 job 均值约 `431.6 MiB/job` 估算，13 个正式 job 约 `5.48 GiB`，加入 50% 余量约 `8.22 GiB`；容量理论上够，但根盘使用率已达 87%，不适合继续承载长期实验 artifact。实际数据目录采用：

```text
/mnt/data/shared2/hynx/VLA-Pilot++/eds-init-pg-diverse-sampling/
  outputs/ood_eval/p2_adaptive_eds_rbf/
```

worktree 中保留兼容路径，并将它建立为指向上述真实目录的软链接：

```text
outputs/ood_eval/p2_adaptive_eds_rbf
  -> /mnt/data/shared2/hynx/VLA-Pilot++/eds-init-pg-diverse-sampling/outputs/ood_eval/p2_adaptive_eds_rbf
```

runner 启动前必须检查链接目标可写、剩余空间至少 `20 GiB`、链接没有悬空且目标不位于 home 根文件系统。不得移动或覆盖既有 `outputs/ood_eval` 内容。

每个 job 必须保存：

- `results.txt`
- `.hydra/config.yaml`
- `.hydra/overrides.yaml`
- `job_manifest.json`
- `config_fingerprint.txt`
- 10 个 episode videos
- `eds_eval/eds_metrics.jsonl`
- stage events JSONL
- qualitative artifacts
- mechanism traces for configured chunks
- runner/job logs
- `failure_reason.json`，若失败或 invalid

禁止写入或覆盖：

```text
outputs/ood_eval/stage_recognition_ablation/
outputs/ood_eval/level4_libero_object_swap_*/
```

### 15.2 Evidence 目录

最终报告保存到：

```text
docs/03_evidence/eds_init_pg_diverse_sampling/
  2026-08-02-p2-adaptive-eds-rbf-object-swap-report.md
```

执行日志索引、失败清单和聚合 CSV 同样保存到该 evidence tree，不把大视频复制进 docs。

### 15.3 报告内容

最终报告至少包含：

1. Stage A 11 jobs 与 Stage B 最多 2 jobs 的完整状态表；
2. baseline、所有单因素和预注册集成 profile SR；
3. task-level paired outcome；
4. selection ESS/beta/entropy 分析；
5. adaptive RBF scale 与 band-hit 分析；
6. elite/anchor survival 和 selected source；
7. memory acceptance、reset 和 chunk consistency；
8. renoise/iteration/horizon 分布；
9. grasp/transport/place 可见失败分类；
10. latency、API query、replan 次数和总 wall-clock；
11. fallback、nonfinite、mask、qpos execution error；
12. 代表性成功/失败 qualitative case；
13. 是否达到 `>=5/10` 的明确 gate 结论。

## 16. Validity 与成功判据

### 16.1 Job validity

complete job 必须满足：

- `results.txt` 可解析；
- 10 个 task/episode 均有成功或失败记录；
- 10 个视频均存在且 ffprobe 可读；
- strict perturbation 和 suite 写入 Hydra config/overrides；
- resolved profile 与 config fingerprint 一致；
- Stage Recognition ON 且至少有成功 query trace；
- Gemini grounding OFF；
- metrics、qualitative 和新机制 telemetry 完整；
- 未退回普通 LIBERO；
- credential 未序列化。

### 16.2 主成功判据

至少一个有效的新算法 profile（Stage A 单因素或 Stage B 集成）同时满足：

1. success `>=5/10`；
2. 结果有效且不存在 silent fallback；
3. 不以 dropped episode、少视频或执行错误排除失败样本。

“同一套 10 tasks 达到 `>=5/10`”是主要工程 gate。相对本轮 `p2_legacy_stage_on_rerun` 的 paired success 增量、历史 P2 的 `3/10` 与置信区间均作为重要次级证据，但不得替代该绝对 gate。

### 16.3 机制与安全 gate

- adaptive-ESS 组的 ESS target error median `<=0.1`；
- adaptive-RBF 组不能 100% iterations 固定使用同一 scale；
- k-center 组的 elite/anchor source 均在 trace 中实际出现；
- memory 或集成 profile 中声明的 source 必须在 trace 中实际出现；
- adaptive schedule 至少解析出两种 renoise 或 execution horizon；
- initial/rollout RBF fallback count 为 0；若非 0，必须逐项解释；
- nonfinite count 为 0；
- max action-mask violation 为 0；
- select-action median latency不超过本轮 P2 baseline 的 1.5 倍，P95 不超过 2 倍；
- qpos range execution errors 保留在失败分母并单独报告。

### 16.4 解释限制

10 个固定 tasks 只用于工程 gate，不支持统计显著性结论。达到 `>=5/10` 后，下一步才是扩大 seed 并验证 `libero_object_task/env/temp`。若未达到目标，但某单因素明显改善 selection/memory/diversity 指标，也不能绕过 environment success 宣称算法成功。

## 17. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| selection pressure 过强 | 快速 mode collapse | ESS target、elite/anchor coverage、单因素 0.5/0.7 |
| adaptive RBF controller 振荡 | scale 在相邻 iter 激烈变化 | target band、iteration decay、记录 scale history |
| diverse anchors 选中 outlier | reward/feasibility下降 | reward quantile guard、best-first tie-break |
| elite 永久占位 | population 难以跳出局部最优 | elite 上限 1--2，不超过 population 的 1/8 |
| memory 陈旧 | 新 observation 下动作不适配 | shift+fresh tail+renoise+reward guard+reset |
| memory 泄漏跨 episode/stage | 无效实验或错误行为 | reset tests、episode/task/stage identity check |
| early stop 过早 | 错过后期优质 mode | min 4 iters、patience 2、full trace |
| execution horizon 过短 | replanning/API latency增加 | 2/4 仅交互区，分开统计 API 与 policy latency |
| Stage Recognition 波动 | 掩盖算法差异 | 同 seeds、P2 baseline rerun、stage-event paired audit |
| 已知 reward 不匹配 | 优化错误 objective | 本轮明确限制结论，后续单独做 task-specific reward |
| 输出覆盖既有实验 | 丢失 baseline evidence | 新 root、fingerprint、fail-on-mismatch、resume validation |

## 18. MVP 与实施顺序

推荐实施顺序不是按实验结果逐步删配置，而是按依赖关系构建：

1. baseline preservation tests 和新 config mode；
2. adaptive ESS weighting；
3. parent plan、diverse anchors 和 elite carryover；
4. adaptive RBF controller；
5. chunk memory；
6. adaptive search schedule；
7. main execution prefix；
8. metrics/trace/visualization；
9. runner、resume、validity 和 report writer；
10. 所有 strategy 分支的 mechanism pretest；
11. Stage A 全部 11 个 single-factor formal jobs；
12. Stage A 分析、资格判定与 integration manifest；
13. Stage B 集成预检与最多 2 个 formal jobs。

MVP 不做：

- world-model/simulator candidate rollout；
- task-specific reward 修复；
- orientation/gripper-aware RBF distance；
- 多 episode 长期 memory；
- learned adaptive controller；
- 自动贝叶斯参数搜索；
- QD archive、MAP-Elites 或其他 archive-based parent selection；这些内容留待后续独立评测。

## 19. 已确认设计决定

本设计按以下已确认决策执行：

1. P2 baseline 指 `p2_stage_on`，而不是 P2 Stage OFF；
2. Stage Recognition、cached reward 和 grounding 本轮保持不变；
3. 使用组件级 strategy mode；所有新增 mode 取 legacy/off 时必须数值与行为回退到 `p2_stage_on`；
4. 先完成 11 组单因素 Stage A，再依据预声明资格规则运行最多 2 组集成 Stage B；
5. Stage A formal jobs 全部执行，不依据预检 success 做结果导向裁剪；
6. QD-ED 不进入本轮实现或实验，后续另立 design/plan 独立评测；
7. 优先使用 `[2, 3, 4, 5]` 中的空闲 GPU，全部繁忙时等待；
8. 正式实验 artifact 写入 `/mnt/data/shared2`，worktree 通过软链接保留原输出路径；
9. 主要工程 gate 为同一 10 tasks 达到 `>=5/10`。

已批准的 implementation plan 保存于：

```text
docs/04_plans/2026-08-02-p2-adaptive-eds-rbf-ood-optimization.md
```

下一步按该计划使用 subagent-driven development 完成代码修改、机制预检、Stage A、manifest 冻结、Stage B 和最终报告。
