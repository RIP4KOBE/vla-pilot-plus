# EDS Quality-Diversity（QD-ED）算法优化与 LIBERO Object-Swap OOD 实验设计

日期：`2026-08-06`

状态：`Approved for execution`

执行修订（`2026-08-07`）：用户明确授权把本文所有设置视为可为完成任务而放宽的软设置。为保留 6 个已审计的 shared2 guidance-cache 基础设施失败 attempts，并原样重跑固定的 `3 profiles × 2 tasks` mechanism preflight，本次仅将 same-config recovery slots 从 `4` 放宽为 `6`、全阶段 actual episode-attempt cap 从 `120` 放宽为 `122`。该修订覆盖下文仍保留的原始 `4/120` 预注册文本；不改变 QD 算法、11-job 矩阵、tasks/seeds、配置、gates、ranking、GPU admission、validity 或 storage 规则，也不授权新增配置或 outcome。

执行修订（`2026-08-07`，GPU 迁移）：用户明确要求停止本实验使用 GPU 3/4，将全部剩余 preflight 与 formal jobs 固定在 GPU 5，并明确授权与 GPU 5 上的外部 compute 进程共用以提高利用率。迁移时两个 task-0 preflight episodes 已初始化但未完成，另四个 reservations 经产物审计确认未进入 episode；因此 same-cell recovery allowance 从 `6` 放宽为 `8`，actual episode-attempt cap 从 `122` 放宽为 `124`，以便在 GPU 5 完整重跑固定的 `3 profiles × 2 tasks` 后仍执行原定 110 个 formal episodes。GPU 5 admission 继续强制两次快照、至少 `max(1.25× historical peak, peak+4096 MiB)` 的空闲显存和非 prohibited compute mode，但按本次明确授权不因外部 compute process 或利用率拒绝共置。该修订不改变 QD 算法、11-job 矩阵、tasks/seeds、配置、validity、gates、ranking、credential 或 shared2 storage 规则，不授权新增配置或 outcome。

## 1. 摘要

本阶段以 `p2_stage_on_abs_rbf_control` 为唯一算法基线，把当前 EDS 每轮基于 reward softmax 的有放回 parent resampling，替换为一个可落地、config-controlled 的 Quality-Diversity archive。QD-ED 在每个 `select_action` chunk 内按低维 behavior descriptor（BD）划分 cell，在每个 cell 中持续保留 reward 最高的 action elite，并从已占用 cells 均匀或稀疏优先地产生下一轮 offspring。最终仍只执行 archive 中 reward 最高的单个 action。

本轮只改变 EDS 的 parent survival/resampling 机制，不改变：

- RDT policy、checkpoint、action layout 或 diffusion scheduler；
- initial 与 rollout 的 absolute-EEF RBF descriptor、guidance scale 或 step mask；
- reward、keypoints、Stage Recognition 或 grounding；
- population size、EDS iterations、renoise schedule 或 execution horizon。

正式实验继续使用与 P2 Direction-Normalized RBF 实验完全相同的 LIBERO-PRO `libero_object_swap` benchmark、strict perturbation、tasks `0..9`、episode seeds、720-step budget、Stage Recognition ON、Gemini grounding OFF 和视频/审计标准。预注册矩阵为：

1. `p2_stage_on_abs_rbf_control` contemporaneous control；
2. `eds_quality_diversity_uniform_primary` primary QD treatment；
3. `eds_quality_diversity_sparse_primary` inverse-visitation sparse-priority attribution treatment；
4. 8 个只改变 grid、bounds quantiles、expand fraction 或 minimum axis span 中单一因素的 uniform-cell parameter jobs。

正式矩阵共 `11 jobs / 110 unique formal episodes`。完整实验 episode-attempt ledger 同时计数 6 个 LIBERO mechanism-preflight episodes、110 个 formal episodes 和最多 4 个同配置基础设施恢复 attempts，hard cap 为 120。未使用的恢复预算不得用于增加 QD 参数、descriptor、reward、top-N archive 或其他实验。

## 2. 阶段隔离、Branch 与 Worktree 前置条件

EDS Quality-Diversity 属于 P2 之后的独立算法优化阶段。实现、测试、preflight、正式实验和报告不得继续直接写入当前 P2 implementation worktree。本文档批准后必须先冻结一个包含已审计 `p2_stage_on_abs_rbf_control` 的 clean base commit，再从该 commit 新建独立 branch 和 worktree：

```text
source branch:   exp/eds-init-pg-diverse-sampling
new branch:      exp/eds-quality-diversity
new worktree:    /home/hynx/VLA-Pilot++/.worktrees/exp/eds-quality-diversity
```

执行约束：

1. 本设计文档和作为基线的 P2 代码必须先进入一个明确 commit；不得从含未提交修改的索引或工作区复制代码到新 worktree。
2. 创建 worktree 时必须把 `base_commit`、source branch、new branch 和 new worktree realpath 写入 EDS Quality-Diversity run manifest。
3. 新 worktree 创建后首先执行 `git status --short --branch`，要求没有非预期修改。
4. 所有 QD core、config、metrics、runner、tests 和报告实现 commit 只进入 `exp/eds-quality-diversity`。
5. 不得在当前 P2 worktree 中实现 QD 后再把文件手工复制过去；不得把 P2 未提交实验产物混入 EDS Quality-Diversity branch。
6. P2 output、manifest 和报告保持只读；EDS Quality-Diversity 使用独立 shared2 experiment root，不覆盖或续写任何 P2 job。

建议的创建命令只可在 base commit 已冻结且目标路径/branch 不存在时执行：

```bash
git worktree add \
  -b exp/eds-quality-diversity \
  /home/hynx/VLA-Pilot++/.worktrees/exp/eds-quality-diversity \
  <AUDITED_P2_BASE_COMMIT>
```

`<AUDITED_P2_BASE_COMMIT>` 必须替换为实际完整 commit SHA，并记录到 manifest；禁止以未解析的工作树状态作为 provenance。

## 3. 基线与问题定义

### 3.1 唯一算法基线

本轮 control 必须逐字段复现 `p2_stage_on_abs_rbf_control`：

```yaml
population_size: 16
cem_iters: 10
use_cem: false
num_elites: 16
temperature: 0.1

initial_sampling_mode: rbf_diverse_denoise
initial_diversity_descriptor_mode: absolute_eef
initial_diversity_scale: 20.0
initial_diversity_start_ratio: 0.8

truncated_rollout_mode: rbf_diverse
rollout_diversity_descriptor_mode: absolute_eef
renoise_t_max: 3
renoise_t_min: 1
rollout_diversity_scale: 20.0
rollout_diversity_start_ratio: 0.6
rollout_diversity_iters: all
rollout_diversity_skip_final_steps: 0

parent_weighting_mode: legacy_temperature
parent_coverage_mode: none
elite_carryover_count: 0
chunk_population_mode: fresh
rollout_diversity_control_mode: fixed
search_schedule_mode: legacy_linear
execution_horizon_mode: fixed
execution_horizon_far: 8

qd_archive_mode: none
```

control 不启用 Direction-Normalized RBF、adaptive ESS、k-center anchors、elite carryover、chunk memory、adaptive RBF、adaptive schedule 或 clean tail。历史 Direction-Normalized winner、parameter winner 和其他 P2 treatments 只可作为背景证据，不进入本轮 formal ranking。

### 3.2 当前 EDS 的局限

当前 P2 在每个 EDS iteration 中根据全局 reward 构造 softmax probabilities，再有放回采样 `M=16` 个 parents。即使 RBF rollout 产生多个不同 approach modes，后续 resampling 仍可能：

- 重复抽取少数高概率 parent；
- 丢失 reward 尚未最高、但代表不同接近方向的 stepping stone；
- 让 population 多轮后集中到同一个局部 behavior mode；
- 无法保证某个已经发现的 mode 中的 best action 跨 iteration 存活。

QD-ED 的目标不是继续增大 pairwise RBF distance，而是把 RBF 已生成的差异转化为有状态的 niche survival：不同 cell 之间竞争 coverage，同一 cell 内只按 quality 竞争。

### 3.3 研究问题

1. chunk-local QD archive 能否比 P2 softmax resampling 保留更多已发现的 endpoint-approach cells？
2. cell 内 elitism 能否在维持 behavior coverage 的同时保持或提高 best reward？
3. uniform-cell sampling 和 sparse-priority sampling 哪一个更适合 `M=16`、`K=10` 的短预算 EDS？
4. archive coverage 是否对应真实的米制 endpoint spread，而不是 adaptive grid 对毫米级差异的虚假放大？
5. QD 机制改善能否转化为同一 10 个 swap tasks 上不低于 control 且达到 `>=5/10` 的成功率？

### 3.4 预注册假设

- **H1 — Archive correctness。** 每个 cell 的 elite reward 跨 iteration 单调不下降；final selected action 必须等于 archive 全局最高 reward elite。
- **H2 — Mode retention。** QD treatment 相对使用相同 discretization profile 的 control metrics-only shadow archive，paired median normalized final coverage 至少提高 0.05，同时绝对 endpoint-XY spread 至少保留 control 的 90%。
- **H3 — Parent ecology。** uniform treatment 对 occupied cells 的 parent slots 分配差不超过 1；sparse treatment 的 allocation 与累计 cell visitation 呈预注册的反向优先关系。
- **H4 — Fixed compute。** 每个完整 EDS chunk 仍为 16 个 initial evaluations 加 10 轮、每轮 16 个 child evaluations；QD 不增加 diffusion rollout、reward evaluation 或 VLM query 数量。
- **H5 — Task adoption。** 至少一个 valid QD treatment 达到 `>=5/10`，success count 不低于 contemporaneous control，并通过 mechanism 与 safety gates。

H1/H3/H4 是实现语义 hard gates；H2 是 QD mechanism claim gate；H5 是工程 adoption gate。H2 通过而 H5 失败时，只能报告 archive 机制成立、任务收益未成立。

## 4. QD-ED 数学定义

### 4.1 Solution、quality 与 mutation

对当前 steering chunk：

```text
solution/genotype a: Tensor[64, 128] RDT action sample
quality R(a; c):     当前 _eds_score_population_as_cost() 对应的 reward = -cost
mutation:            现有 parent -> renoise -> truncated diffusion denoise
population M:        16
EDS iterations K:    10
```

QD 不新增 reward，也不使用 task success、未来 observation 或 simulator privileged state 选择 archive elite。所有 cell 内比较只使用当前 P2 已有 reward。

### 4.2 Behavior descriptor

使用现有 differentiable adapter 将 action 转为 EEF translation trajectory：

```text
P(a) = [p_0, p_1, ..., p_H],  p_t in R^3
```

令当前 guidance target 为与 `_eds_target_distance()` 一致的第一个 3D keypoint：

```text
t = reshape(keypoints)[0, :3]
```

MVP behavior descriptor 固定为 target-relative endpoint XY：

```text
b(a) = [p_H,x - t_x,
        p_H,y - t_y]
```

选择该 BD 的原因：

- 它直接表示从目标不同侧面接近的 behavior mode；
- 维度足够低，可在 16-particle budget 下形成有效 cell occupancy；
- 与现有 EEF trajectory 和 target coordinate frame 一致；
- quality 仍由完整 guidance reward 决定，BD 不替代 reward；
- 不把完整 `H*3` trajectory 离散为高维、极稀疏 archive。

本轮不使用 Z、direction-normalized shape、gripper、rotation、trajectory length 或 task-specific semantic BD。缺失、shape 错误或 nonfinite target/trajectory descriptor 必须显式记录；正式 QD job 中发生 QD descriptor fallback 即 invalid。

### 4.3 Chunk-local fixed bounds 与预注册参数 profiles

每个新的 EDS chunk 只用 initial population 的 16 个 descriptors 冻结 grid bounds。对每个轴 `d in {x,y}`，令 profile 给定 lower/upper quantiles `(q_lo, q_hi)`、expand fraction `rho` 和 minimum axis span `s_min`：

```text
Qlo_d = quantile(b[:, d], q_lo)
Qhi_d = quantile(b[:, d], q_hi)
raw_span_d = Qhi_d - Qlo_d

lo_d = Qlo_d - rho * raw_span_d
hi_d = Qhi_d + rho * raw_span_d
```

如果 `hi_d - lo_d < s_min`，则以 initial median 为中心扩展到 `s_min`：

```text
center_d = median(b[:, d])
lo_d = center_d - 0.5 * s_min
hi_d = center_d + 0.5 * s_min
```

边界一旦由 initial population 冻结，在该 chunk 的全部 10 个 EDS iterations 中不得重算。这样同一 cell 的语义不会随 population 漂移。

primary profile 固定为：

```yaml
qd_grid_shape: [4, 4]
qd_bounds_quantiles: [0.05, 0.95]
qd_bounds_expand_fraction: 0.10
qd_min_axis_span_m: 0.08
```

parameter sweep 只允许使用以下预注册取值：

| 因素 | 取值 | Primary |
| --- | --- | --- |
| Grid | `[3,3]`, `[4,4]`, `[5,5]` | `[4,4]` |
| Bounds quantiles | `[0.00,1.00]`, `[0.05,0.95]`, `[0.10,0.90]` | `[0.05,0.95]` |
| Expand fraction | `0.00`, `0.10`, `0.20` | `0.10` |
| Minimum axis span | `0.04 m`, `0.08 m`, `0.12 m` | `0.08 m` |

正式矩阵采用 one-factor-at-a-time sweep：每个 parameter job 相对 primary 只改变一个值。不得根据 preflight 或正式结果生成组合 profile。

设 grid 为 `[G_x,G_y]`，cell index 统一计算为：

```text
u_x = (b_x - lo_x) / (hi_x - lo_x)
u_y = (b_y - lo_y) / (hi_y - lo_y)
cell_x = clamp(floor(G_x * u_x), 0, G_x - 1)
cell_y = clamp(floor(G_y * u_y), 0, G_y - 1)
cell_id = G_x * cell_y + cell_x
```

超出 bounds 的 descriptor clamp 到对应 edge cell，并增加 overflow counter；不得在 iteration 中扩展或重算 bounds。所有 coverage 指标必须除以 `G_x * G_y`，并与米制 endpoint spread、实际 bounds 和 overflow 联合报告，防止不同 grid size 或很小物理 span 产生虚假 coverage。

### 4.4 Archive entry 与 replacement

每个 `select_action` chunk 创建独立 archive：

```text
cell_id -> {
    action: Tensor[64, 128],
    reward: scalar,
    cost: scalar,
    descriptor_xy_m: Tensor[2],
    action_fingerprint: sha256,
    source_iter: int,              # initial = -1
    parent_cell_id: optional int,
    insert_sequence: int,
}
```

本轮每 cell capacity 固定为 1。对一个新 candidate：

1. 空 cell：插入；
2. occupied cell 且 candidate reward 更高：替换；
3. reward 更低：拒绝；
4. reward 完全相等：在 incumbent 与 candidate 的 canonical float32 action fingerprint 中保留字典序更小者。

fingerprint tie-break 只处理精确 reward tie，不能用 label、task outcome、candidate index 或 wall-clock 顺序打破平局。更新必须对 population permutation equivariant。

archive action 必须 `detach`，不得保留 autograd graph。archive 只在当前 chunk 的 10 个 EDS iterations 内持久化；episode 下一 chunk 必须用 fresh initial population 和 fresh archive，不启用跨-chunk memory。

### 4.5 Uniform-cell parent allocation

设当前 occupied cell 数为 `C`，下一轮需要 `M=16` 个 parent slots。`uniform_cells` 使用整数均衡分配：

```text
base = floor(M / C)
remainder = M mod C
```

每个 occupied cell 先获得 `base` 个 slots，余下 `remainder` 个 slots 按独立 local generator 产生的 deterministic cell permutation 各增加 1。local generator seed 必须由 run seed、episode、chunk global step 和 EDS iteration 确定，不得消费或改变 policy/diffusion 的 global RNG stream。

因此每轮：

```text
max(parent_slots_per_cell) - min(parent_slots_per_cell) <= 1
```

同一 cell 的多个 slots 使用同一个 elite action，但后续独立 renoise noise 可以产生不同 children。

### 4.6 Sparse-priority parent allocation

`sparse_priority` 用累计 cell visitation 优先探索较少被评估的 occupied cells。令：

```text
v_c = 从 initial population 到当前 iteration 为止，映射到 cell c 的全部 evaluated candidates 数
alpha = 1.0
s_c = (v_c + 1)^(-alpha)
p_c = s_c / sum_j s_j
```

将 `M * p_c` 通过 largest-remainder apportionment 转为总和严格等于 16 的整数 slots：先取 floor，再把剩余 slots 分给 fractional remainder 最大的 cells；精确 tie 使用与 uniform sampler 相同的 deterministic local cell permutation。

这里的“稀疏”指累计 evaluated visitation 较少，而不是根据 reward、空 cell 的未知 action 或 grid 几何距离虚构 parent。只能从 occupied cells 采样；archive 中尚不存在 elite 的空 cell不能作为 parent。

本轮固定 `alpha=1.0`，不做结果驱动 sweep。sparse treatment 仍保留每个 occupied cell 的 elite，即使某轮没有为该 cell 分配 offspring slot，该 elite 也不会从 archive 消失。

### 4.7 单个 steering chunk 的完整流程

```text
Input: policy pi_vla, reward R(a; c), descriptor b(a)

1. 使用 P2 absolute-RBF initial sampler 生成 M=16 个 actions
2. 使用当前 P2 reward 评估 16 个 actions
3. 按 job 的预注册 discretization profile 从 initial descriptors 冻结 bounds
4. 用 initial actions 填充/替换 archive A

5. for k = 1..K, K=10:
     a. 从 A 的 occupied cells 产生恰好 M=16 个 parent slots
        - uniform_cells，或
        - sparse_priority
     b. 沿用 P2 legacy_linear schedule 确定 renoise steps
     c. 对 16 个 parents 执行现有 renoise
     d. 对 16 个 offspring 执行现有 absolute-RBF truncated denoise
     e. 使用当前 P2 reward 评估全部 16 个 children
     f. 使用 fixed bounds 计算 child cell
     g. 按 cell 内 reward 更新 archive；archive 不因当前 population 被覆盖

6. selected = archive 中 reward 全局最高的 elite
7. 执行 selected 的固定前 8 个 actions
```

QD mode 不再调用 legacy reward-softmax parent selection；`parent_weighting_mode=legacy_temperature` 只作为基线兼容配置保留，不能与 QD parent allocation 混合。control 的 `qd_archive_mode=none` 必须继续调用原始 `_eds_select_parent_plan()`，固定输入下保持 bitwise backward compatibility。

### 4.8 Degenerate 与 failure 语义

- `C=1` 时允许从唯一 occupied cell 产生 16 个 offspring，并记录 coverage collapse；不得伪造第二个 cell。
- descriptor nonfinite、bounds nonfinite/zero-span、archive accounting mismatch、空 archive 或 final best 不一致时必须 fail closed。
- production 可保留显式 legacy fallback 作为运行安全措施，但必须记录 `qd_fallback_used/reason`；任何 formal QD episode 出现该 fallback 都使 job invalid。
- archive reward、cost 和 action 必须 finite；出现 nonfinite 不得以 `-inf` 或默认 cell 静默吞掉。
- edge clamp 合法但必须记录 overflow；overflow 不是 fallback。
- cell capacity、grid shape、descriptor 或 bounds 不得在 iteration 中自适应变化。

## 5. Config 与实现边界

### 5.1 新配置字段

新增字段必须进入 `_EDSConfig`、Hydra config、resolved config、metrics 和 job manifest：

| 字段 | Legacy 默认 | 本轮合法 treatment 值 | 含义 |
| --- | --- | --- | --- |
| `qd_archive_mode` | `none` | `grid_archive` | QD 机制总开关 |
| `qd_descriptor` | `target_relative_endpoint_xy` | 固定 | behavior descriptor |
| `qd_grid_shape` | `[4, 4]` | `[3,3]`, `[4,4]`, `[5,5]` | 2D grid |
| `qd_cell_capacity` | `1` | 固定 | 每 cell elite 数 |
| `qd_parent_sampling` | `uniform_cells` | `uniform_cells`, `sparse_priority` | parent allocation |
| `qd_sparse_exponent` | `1.0` | 固定 | inverse-visitation exponent |
| `qd_bounds_quantiles` | `[0.05, 0.95]` | `[0,1]`, `[.05,.95]`, `[.10,.90]` | initial bounds quantiles |
| `qd_bounds_expand_fraction` | `0.10` | `0`, `.10`, `.20` | quantile bounds 两侧扩展比例 |
| `qd_min_axis_span_m` | `0.08` | `.04`, `.08`, `.12` | 每轴最小物理 span |
| `qd_overflow_policy` | `clamp_edge` | 固定 | bounds 外 cell 处理 |
| `qd_tie_break` | `stable_fingerprint` | 固定 | exact reward tie 语义 |
| `qd_metrics_observer` | `false` | formal profiles 为 `true` | 不影响 selection 的 shadow metrics |

`qd_archive_mode=none` 时，除 `qd_metrics_observer` 的 detached 观测外，所有 QD 参数必须被 legacy algorithm branch 忽略。observer 不得调用 reward、改变 RNG、改变 tensor、选择 parent 或增加 model inference；目标测试必须证明 control selected action 与 observer OFF bitwise 相同。

### 5.2 互斥规则

首版 `qd_archive_mode=grid_archive` 要求：

```yaml
use_cem: false
parent_weighting_mode: legacy_temperature
parent_coverage_mode: none
elite_carryover_count: 0
chunk_population_mode: fresh
rollout_diversity_control_mode: fixed
search_schedule_mode: legacy_linear
execution_horizon_mode: fixed
```

以下组合必须 config validation 失败，而不是定义隐式优先级：

- QD + adaptive ESS；
- QD + k-center/diversity-aware parent coverage；
- QD + elite carryover；
- QD + cross-chunk population memory；
- QD + adaptive rollout RBF；
- QD + adaptive search/execution horizon；
- QD + Direction-Normalized RBF；
- QD + 未在预注册取值表中的 grid、quantiles、expand fraction、minimum span 或 `cell_capacity != 1`。

### 5.3 预期代码组织

建议新增/扩展以下组件，但不得复制第二套 policy：

```text
core/rdt_policy_steer.py
  _eds_qd_descriptor(...)
  _eds_qd_freeze_bounds(...)
  _eds_qd_cell_ids(...)
  _eds_qd_update_archive(...)
  _eds_qd_allocate_parent_slots(...)
  _eds_qd_select_global_best(...)

core/eds_eval_metrics.py
  QD archive、parent ecology、fallback 与 latency metrics

utils/eds_eval_vis.py
  profile-specific occupancy/elite-reward heatmap、cell-colored trajectories

scripts/eds_quality_diversity_runner.py
  固定 formal/preflight matrix、resume、attempt ledger、shared2/GPU admission

scripts/eds_quality_diversity_audit.py
  validity、mechanism/safety gates、ranking、manifest 与报告
```

可以将 archive 定义为小型 dataclass/helper module，但核心 `_eds_guided_denoise_loop()` 仍是唯一 EDS 主控制流。禁止：

- 创建 `rdt_policy_steer_qd.py` 并复制整个 policy；
- 在 core 中根据 job label 分支；
- 在 runner monkeypatch selection；
- 复用 Direction-Normalized descriptor 作为 QD BD；
- 在 archive 中保存带 autograd graph 的 tensor；
- 为 QD 增加额外 rollout、reward call 或 VLM call。

### 5.4 本轮不允许同时修改

本阶段不得修改：

- initial/rollout absolute-RBF distance、scale、sign、gradient normalization 或 start ratio；
- `renoise_t_max/min`、rollout iters、skip-final steps；
- population size 16、EDS iterations 10、temperature 或 reward；
- Stage Recognition prompt、query cadence、Gemini grounding；
- action execution horizon 8、RDT checkpoint、scheduler inference steps；
- 预注册范围之外的 grid、BD、bounds、capacity、sparse exponent；
- task matrix、seeds、gates、ranking 或 retry cap。

任何上述变更都要求先修订本文并重新批准；正式结果不能作为追加实验授权。

## 6. Metrics、Trace 与定性证据

### 6.1 必需 QD metrics

每个 EDS chunk 以及每个 iteration 至少记录：

```text
qd_archive_enabled
qd_descriptor
qd_grid_shape
qd_cell_capacity
qd_parent_sampling
qd_bounds_xy_m
qd_bounds_source_initial_checksum
qd_initial_occupied_cells
qd_occupied_cells_by_iter
qd_coverage_ratio_by_iter
qd_cell_occupancy_entropy_by_iter
qd_cumulative_cell_visits_by_iter
qd_descriptor_overflow_count/ratio_by_iter
qd_archive_insertions/replacements/rejections_by_iter
qd_archive_turnover_ratio_by_iter
qd_per_cell_elite_reward_by_iter
qd_archive_best_reward_by_iter
qd_archive_mean_elite_reward_by_iter
qd_parent_slots_by_cell_by_iter
qd_parent_covered_cell_ratio_by_iter
qd_parent_cell_unique_ratio_by_iter
qd_selected_cell
qd_selected_reward
qd_selected_action_fingerprint
qd_global_best_action_fingerprint
qd_archive_endpoint_xy_spread_m_by_iter
qd_fallback_used/reason
qd_accounting_violation_count
qd_elite_monotonicity_violation_count
qd_final_selection_mismatch_count
qd_archive_update_latency_s
qd_parent_allocation_latency_s
```

每 iteration 必须满足：

```text
children_evaluated
  = insertions + replacements + rejections
  = 16
```

initial archive 另行记录 16 个 initial candidates 的同类 accounting。指标必须区分真实 QD archive 与 control 的 `shadow_qd_*` observer，禁止把 observer 当作启用 QD。

### 6.2 保留的 P2 metrics

继续记录并按 job/task 对比：

- reward best/mean/spread 与 selected cost；
- parent lineage、unique parent ratio 和 resample count；
- EEF trajectory diversity、endpoint spread、direction diversity；
- selected/population trajectory length、max-step、expansion ratio；
- chunk-boundary action jump；
- RBF steps、gradient failure、nonfinite 和 action-mask violation；
- target distance、collision/push/drop/wrong-object/qpos evidence；
- Stage query、ON/OFF transition、selection latency 和 action latency。

### 6.3 Shadow observer

为各 parameter profile 提供公平机制参照，`qd_metrics_observer=true` 在 detached metrics state 中保存 control 已经评估的 initial/child descriptor、reward、iteration 和 fingerprint stream；audit 再分别使用每个 treatment 的相同 grid/bounds profile 重放 top-1 shadow archive。observer 与 audit replay 绝不参与 parent selection 或 final action selection。observer：

- 不新增 reward/model/VLM call；
- 不消费任何 RNG；
- 不保存 autograd graph；
- 不改变 baseline tensor、cost、parent indices 或 selected action；
- 不在 core 中根据 job label 选择 discretization；
- metrics 使用 `shadow_qd_` 前缀。

所有 formal profiles 都启用 observer，以便审计 observer overhead 和一致性；control observer OFF/ON bitwise equality是正式启动前 hard gate。每个 QD job 的 mechanism comparison 必须使用由 control stream 和该 job 完全相同 discretization profile 重放得到的 matching shadow archive。

### 6.4 定性产物

每个 formal episode 必须保存：

- 完整可读落盘视频；
- initial、iter 1、iter 5、iter 10 的 profile-specific grid occupancy/elite-reward heatmap；
- EEF XY/XZ/3D trajectories，按 cell 着色并标出 target；
- selected cell、global-best lineage 和 replacement timeline；
- control、primary/sparse 和 parameter jobs 的同 task/seed contact sheet；
- failure taxonomy annotation 和关键接触帧。

经典 QD-score 不作为本轮主指标。当前 reward 可能为负且不同 chunk 的 reward offset 不统一，未经校准的 cell reward sum 不可跨 task/chunk解释。主机制指标使用 coverage、物理 spread、turnover、best reward 和 environment success。

## 7. TDD、回归与 Mechanism Preflight

### 7.1 Config 与 legacy 回归测试

- 所有 QD 字段默认解析正确，invalid enum/shape/capacity/bounds/exponent 被拒绝；
- 互斥组合 fail fast；
- `qd_archive_mode=none`、observer OFF 对固定 seed/input 与 P2 baseline bitwise 一致；
- observer ON/OFF 的 parent indices、RNG state、model outputs 和 selected action bitwise 一致；
- core 中不存在 job-label 分支；
- resolved config、Hydra overrides 和 job manifest 完整记录 QD 字段。

### 7.2 Descriptor 与 grid 单元测试

- target-relative endpoint XY 数值与 adapter trajectory、keypoint frame 一致；
- 所有预注册 quantiles、expand fractions、minimum spans 与 3x3/4x4/5x5 cell mapping 精确；
- bounds 在 iteration 中不可变；
- lower/upper edge、exact upper bound、overflow clamp 的 cell id 正确；
- descriptor/cell mapping permutation equivariant；
- zero-spread initial population 在每个预注册 `s_min` 下均得到有限 bounds；
- nonfinite/missing target、trajectory 或 bounds fail closed。

### 7.3 Archive 单元测试

- empty-cell insertion、higher-reward replacement、lower-reward rejection；
- exact tie 使用 stable fingerprint；
- 每 cell 始终最多 1 个 elite；
- per-cell reward 单调不下降；
- archive 跨 iteration 保留、跨 chunk 重置；
- archive tensor detached 且无 graph/memory leak；
- update accounting 精确；
- final output 是 archive global best；
- candidate permutation 不改变 archive 内容和 final best。

### 7.4 Parent allocation 单元测试

- uniform slots 总和为 16，occupied cells 间差不超过 1；
- sparse weights 精确为 `(visits+1)^-1`；
- largest-remainder slots 总和为 16，低 visitation cell 获得不低于高 visitation cell 的 allocation；
- tie-break deterministic；
- sampler 只返回 occupied cell elites；
- local generator 不改变 global RNG；
- `C=1`、`C=16`、overflow-heavy 和 reward-tie cases 均有限且确定。

### 7.5 Loop、metrics、runner 与 audit 测试

- 每个完整 QD chunk 为 `16 + 10*16 = 176` evaluations；
- QD 不增加 diffusion rollout、reward/VLM calls；
- initial 与 rollout descriptor 均保持 `absolute_eef`；
- action mask 仅允许既有 RBF 修改有效 horizon XYZ；
- trace/metrics JSON serializable，fingerprint/checksum 稳定；
- formal matrix 精确为 11 jobs/110 episodes，8 个 parameter jobs 均为相对 primary 的单因素变化；
- tasks、seeds、Stage、strict perturbation 与 control 完全相同；
- per-job resume、valid skip、independent failure、same-config retry；
- preflight/formal/retry 共用 append-only attempt ledger，hard cap 120；
- `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/` realpath、worktree `outputs` 绝对软链接、ffprobe、Hydra、credential scan；
- deterministic candidate ranking、immutable decision manifest 和 report tables。

至少运行：

```text
tests/test_qd_ed_archive.py
tests/test_eds_quality_diversity_runner.py
tests/test_eds_quality_diversity_audit.py
tests/test_rdt_steer.py
tests/test_eds_eval_metrics.py
tests/test_eds_eval_runner.py
tests/test_main_rdt_startup.py
tests/test_env_adapters_imports.py
tests/test_direction_normalized_rbf.py
```

最后必须通过完整相关回归、受影响 Python 文件的 `py_compile` 和 `git diff --check`。任一目标测试、完整相关回归或 mechanism preflight 未通过时不得启动正式实验。

### 7.6 Offline mechanism preflight

使用 deterministic stub population 和 synthetic trajectories 验证：

1. 16 candidates 在 3x3/4x4/5x5 profiles 中映射到预期 cells；
2. 同 cell reward replacement 与 tie-break；
3. archive 在 10 iterations 中持久化；
4. uniform 和 sparse slot allocation；
5. fixed bounds、overflow、zero-spread、nonfinite；
6. final global-best checksum；
7. control observer ON/OFF bitwise equality；
8. evaluation/model-call budget 不增加。

输出 machine-readable JSON，包含 input/config checksum、per-iteration archive state、parent slots、rewards、fingerprints、accounting 和 RNG-state evidence。

### 7.7 LIBERO mechanism preflight

正式矩阵前运行 3 个 profiles：control、QD uniform primary、QD sparse primary；每个 profile 固定 tasks `[0, 8]` 各 1 episode，`max_chunks=2`、qualitative tensors/video/heatmap ON。该 6-episode preflight 不计入 110 个 formal episodes，但计入全阶段 120-attempt hard cap，只验证：

- strict `libero_object_swap` 与 Stage health；
- target-relative BD frame 和米制 bounds；
- archive insert/replace/retain、parent slots 和 final best；
- 0 nonfinite、0 mask violation、0 fallback；
- artifact、video、shared2、GPU 与 credential pipeline。

preflight success/failure outcome 不得用于删除 treatment、调整预注册 grid/bounds profiles、sparse exponent、formal tasks 或 gates。只允许修复实现/runner bug并在剩余 attempt budget 内重新运行相同 preflight。

## 8. 固定 Benchmark 与执行设置

| 项目 | 固定值 |
| --- | --- |
| Benchmark | LIBERO-PRO OOD Evaluation |
| Suite | `libero_object_swap` |
| Strict perturbation | `true` |
| Tasks | `0..9`，每 task 1 episode |
| Episode seeds | `[44, 235, 43, 546, 6, 621, 197, 87, 151, 548]` |
| Root seed | `0` |
| Max episode steps | `720` |
| Stage Recognition | ON，credential 仅由环境变量注入 |
| Gemini grounding | OFF |
| Rendering/video | ON |
| Action execution horizon | `8` |
| Population / EDS iterations | `16 / 10` |
| Initial/rollout RBF | P2 absolute EEF，scale 均为 20 |

每个 job 必须使用同一 checkpoint、task order、task-seed mapping、Hydra base config 和 Stage settings。不得因历史 control 为 `3/10` 或 `4/10` 而跳过 contemporaneous control；历史结果只作为稳定性背景，不替代本轮 paired baseline。

## 9. 正式实验矩阵与 Attempts

### 9.1 十一个预注册 jobs

所有 QD jobs 共同固定 `M=16`、`K=10`、`alpha=1.0`、absolute-RBF P2 mutation/search budget、target-relative endpoint XY、capacity 1、edge clamp 和 stable-fingerprint tie-break。

| Job | Parent sampling | Grid | Quantiles | Expand | Min span | 角色 |
| --- | --- | --- | --- | ---: | ---: | --- |
| `p2_stage_on_abs_rbf_control` | legacy reward softmax | n/a | n/a | n/a | n/a | contemporaneous baseline |
| `eds_quality_diversity_uniform_primary` | uniform | 4x4 | .05/.95 | .10 | .08 m | primary QD reference |
| `eds_quality_diversity_sparse_primary` | sparse | 4x4 | .05/.95 | .10 | .08 m | parent-sampling attribution |
| `eds_quality_diversity_uniform_grid3` | uniform | 3x3 | .05/.95 | .10 | .08 m | grid OFAT |
| `eds_quality_diversity_uniform_grid5` | uniform | 5x5 | .05/.95 | .10 | .08 m | grid OFAT |
| `eds_quality_diversity_uniform_q00100` | uniform | 4x4 | .00/1.00 | .10 | .08 m | quantile OFAT |
| `eds_quality_diversity_uniform_q1090` | uniform | 4x4 | .10/.90 | .10 | .08 m | quantile OFAT |
| `eds_quality_diversity_uniform_expand00` | uniform | 4x4 | .05/.95 | .00 | .08 m | expand OFAT |
| `eds_quality_diversity_uniform_expand20` | uniform | 4x4 | .05/.95 | .20 | .08 m | expand OFAT |
| `eds_quality_diversity_uniform_span04` | uniform | 4x4 | .05/.95 | .10 | .04 m | minimum-span OFAT |
| `eds_quality_diversity_uniform_span12` | uniform | 4x4 | .05/.95 | .10 | .12 m | minimum-span OFAT |

每个 parameter job 相对 `eds_quality_diversity_uniform_primary` 只改变表中对应一个因素。`eds_quality_diversity_sparse_primary` 只改变 parent sampling；不得把 sparse sampling 与其他 parameter profiles 组合。

QD jobs 的共同配置：

```yaml
qd_archive_mode: grid_archive
qd_descriptor: target_relative_endpoint_xy
qd_cell_capacity: 1
qd_sparse_exponent: 1.0
qd_overflow_policy: clamp_edge
qd_tie_break: stable_fingerprint
qd_metrics_observer: true
```

control 精确保持原始 `p2_stage_on_abs_rbf_control`：initial 与 rollout 都是 `absolute_eef` RBF，`qd_archive_mode=none`。`qd_metrics_observer=true` 只保存 detached replay stream，必须通过 observer OFF/ON bitwise gate。

```text
11 jobs x 10 tasks x 1 episode = 110 unique formal episodes
```

### 9.2 全阶段 Attempt ledger 与 retry

append-only attempt ledger 从第一次 LIBERO mechanism preflight 开始计数，统一覆盖 preflight、formal 和 retry：

```text
6 mechanism-preflight episodes
+ 110 unique formal episodes
+ at most 4 same-config recovery attempts
= hard cap 120 episode attempts
```

恢复规则：

- retry 只能恢复同一 job/task/seed/config/code fingerprint；
- 已完整、valid 且视频可读的 episode 不重复执行；
- infrastructure failure 与 deterministic policy failure 必须区分；
- policy timeout、collision、drop、wrong object、qpos/execution error 是 outcome，不得当作基础设施 failure 擅自 retry；
- OOM、host/API transient failure、损坏/缺失 artifact 可在审计后保留旧 attempt 并 conservative retry；
- 单 job failure 不停止其他已批准 jobs；
- preflight retry 与 formal retry 共用最多 4 个 recovery slots；
- 达到 120 attempts 后停止启动新 attempt，把剩余 job 标记为明确原因的 incomplete/failed；
- 不得把空余 attempts 用于矩阵外 grid/bounds 组合、top-N、其他 BD、alpha、quality mix 或第二次 outcome。

矩阵、task mapping 和 config fingerprint 必须在第一个 LIBERO mechanism-preflight episode 启动前冻结为只读 run manifest。

## 10. Validity、Task、Mechanism 与 Safety Gates

### 10.1 Job validity

每个进入 ranking 的 job 必须满足：

- 10/10 episode result records；
- 10 个完整、唯一且 ffprobe-readable 的落盘视频；
- suite 精确为 `libero_object_swap` 且 strict perturbation 两处验证；
- task/seed/config/code fingerprint 与 frozen manifest 一致；
- Hydra config/overrides、完整 log、EDS/QD metrics、Stage events、qualitative artifacts 齐全；
- output realpath 位于 `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/`；
- 0 nonfinite、0 action-mask violation；
- QD jobs 为 0 descriptor/archive/algorithm fallback；
- 0 archive accounting、elite monotonicity、final-selection mismatch；
- initial/rollout descriptor 均为 `absolute_eef`；
- credential scan 通过。

qpos/execution error 不删除 episode；它作为失败 outcome 和 safety/ranking 字段。只有确定为基础设施损坏时才按 ledger retry。

### 10.2 Task gate

对每个 QD candidate：

```text
success_count >= 5/10
success_count >= contemporaneous control success_count
paired gained_tasks >= paired lost_tasks
```

### 10.3 Mechanism hard gate

所有 QD jobs：

```text
elite monotonicity violations = 0
archive accounting violations = 0
final selection mismatch = 0
QD fallback = 0
complete chunk evaluation count = 176
additional reward/model/VLM calls vs control = 0
```

uniform job：

```text
每个 active iteration 的 max_slots - min_slots <= 1
```

sparse job：

```text
slot allocation 严格符合预注册 inverse-visitation + largest-remainder 公式
```

### 10.4 Mechanism claim gate

相对 contemporaneous control replay 出的 matching-profile shadow archive，按相同 task/seed、active EDS chunk 配对：

```text
paired median normalized final coverage delta >= 0.05
archive endpoint-XY spread median ratio >= 0.90
archive best reward median delta >= 0
archive replacement-active chunk ratio >= 0.50
descriptor overflow ratio P95 <= 0.25
```

coverage 必须与 profile-specific grid、meter-scale bounds、absolute endpoint spread 和 overflow 一起解释；不能只凭 occupancy 宣称真实多样性提升。

### 10.5 Safety gate

```text
qpos/execution error episodes = 0
collision/push/drop/wrong-object composite <= control
nonfinite = 0
action-mask violation = 0
algorithm fallback = 0
```

Task gate 失败时不得把 QD 宣称为工程成功；mechanism claim gate 失败时不得把任何 SR 变化归因于“archive 保留了有效生态位”；safety gate 失败时不得推荐 adoption。

## 11. Ranking 与 Adoption Rule

10 个 valid QD candidates 使用以下 deterministic ranking：

1. success count 降序；
2. control 成功 tasks 的 retention 降序；
3. paired gained-minus-lost tasks 降序；
4. qpos/execution error episodes 升序；
5. collision/push/drop/wrong-object composite 升序；
6. paired normalized-coverage gain 降序；
7. archive endpoint-XY spread retention 降序；
8. archive best-reward paired delta 降序；
9. selection latency P95 升序；
10. job label 字典序。

只有同时通过 validity、task、mechanism hard/claim 和 safety gates 的第一名可以标记：

```json
"recommended_for_adoption": true
```

若没有 QD candidate 满足全部 gates，decision manifest 必须记录：

```json
"decision": "no_adoption_keep_p2_stage_on_abs_rbf_control"
```

结果 gate 失败不授权修改 grid、BD、sampler 或追加实验。

## 12. Task-Level、统计与失败分析

最终报告必须逐 task 给出 control、primary uniform、primary sparse 和全部 parameter jobs 的 paired outcome，并至少分类：

- no target acquisition；
- target pushed away；
- target dropped after grasp；
- basket displaced/collision；
- clutter swept/wrong-object interaction；
- unstable transport；
- placement/release failure；
- premature guidance OFF；
- guidance oscillation；
- qpos/execution error；
- timeout without completion。

必须报告：

- 11-job 完整 outcome/validity 表，不得只展示 winner；
- success count、SR、Wilson interval；
- paired gained/lost/retained task matrix；
- uniform vs sparse 的 archive coverage、turnover、overflow 和 parent allocation；
- grid、quantiles、expand fraction、minimum span 的单因素主效应表；
- per-cell elite reward、global best reward 与 selected cell；
- real archive vs control shadow archive 的 paired comparison；
- endpoint XY meter-scale spread、EEF direction diversity；
- trajectory length、max-step、chunk-boundary jump；
- collision/push/drop/wrong-object/qpos 与 placement failures；
- EDS selection latency、QD overhead、Stage/VLM latency；
- 相同时间坐标的 qualitative contact sheets 和 archive heatmaps；
- failed/invalid/incomplete jobs、attempts 和原因。

每 job 只有 10 个固定 tasks。统计结论必须表述为该固定任务集上的 paired engineering evidence，不宣称统计显著性、总体泛化或 QD 理论被普遍验证。

## 13. Runner、Shared2、GPU 与 Credential

### 13.1 输出根与软链接

所有最终结果的 canonical storage root 为：

```text
/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/
```

本实验的独立目录为：

```text
/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/
```

新 worktree 的整个 `outputs` 路径只能是绝对软链接：

```text
/home/hynx/VLA-Pilot++/.worktrees/exp/eds-quality-diversity/outputs
  -> /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/outputs
```

执行前：

- canonical storage root 可写且 experiment root 至少 50 GiB 可用；
- 不覆盖、删除、移动或复用既有 P2/EDS Quality-Diversity 输出；
- 必须在任何测试 artifact、cache、preflight 或 formal output 生成前建立 `outputs` 软链接；
- worktree `outputs` 若已存在，必须先审计；若它不是指向上述目标的正确软链接则停止，不得自动删除或搬移；
- worktree 内不得创建真实 `outputs` 目录或保存视频、tensor、checkpoint/cache、Hydra、logs；
- 用 `readlink -f` 和 probe file 验证真实落盘；
- videos、metrics、Hydra、logs、manifests、tensors、heatmaps 和 runtime cache 全部落在 `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/`；
- Git 管理的 spec、测试报告和最终分析继续放 `docs/`。

### 13.2 GPU admission

允许使用物理索引 `0..7` 中任意空闲 GPU。每次 admission 必须记录 index、UUID、型号、总/可用显存、utilization、compute mode 和已有 compute process。eligible GPU 必须同时满足：

- index 在 `0..7`；
- 连续两次 admission snapshot 均无外部 compute process；
- utilization 不高于 5%，且显存满足下式；
- compute mode 与本轮独占单 worker 兼容。

```text
free_vram >= max(reference_peak_vram * 1.25,
                 reference_peak_vram + 4 GiB)
```

`reference_peak_vram` 由相同 checkpoint/control config 的加载 preflight 或已审计历史峰值冻结到 run manifest。本轮不与外部 compute job co-locate；发现外部进程的 GPU 直接排除，且不得终止、暂停、修改或抢占该进程。

- 默认每 GPU 最多 1 个本轮 worker；
- 最大并发为 `min(4, eligible_gpu_slots)`；
- dispatch 前再次确认 GPU 仍为空闲；
- OOM/资源争用只能把同一 job/task/seed/config 迁移到其他 eligible GPU；
- dispatch/finish 均记录 GPU index、UUID、显存快照和 process 状态。

### 13.3 Credential

Stage Recognition credential 只通过运行时环境变量注入。health check 不得回显 token。credential 不得进入 command line、Hydra、manifest、attempt ledger、log、report、tensor metadata 或 Git。所有正式 artifacts 和 Git diff 在结束前必须进行 credential-like pattern scan。

## 14. Audit、Decision Manifest 与最终报告

逐 job 审计必须验证：

- output completeness、video readability 与 uniqueness；
- task/seed/config/code/GPU provenance；
- strict perturbation、suite、Stage 和 grounding；
- archive state/accounting、parent formulas、fingerprints 和 final selection；
- no QD fallback、nonfinite 或 mask violation；
- control observer 不改变算法输出；
- preflight/formal/retry 总 attempt ledger 不超过 120；
- canonical shared2 realpath、worktree `outputs` symlink 和 credential scan。

所有 formal jobs 完成或被明确标记 failed/incomplete 后生成只读 decision manifest：

```text
/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/manifests/qd_ed_decision_manifest.json
```

manifest 必须包含：

- base commit、新 branch/worktree provenance；
- 11 个完整 profiles、OFAT matrix completeness 和 config/code fingerprints；
- 6 个 preflight、110 个 unique formal episodes 与全部 attempts；
- task-level results 和 failure taxonomy；
- validity/task/mechanism/safety gates；
- deterministic ranking evidence；
- `recommended_for_adoption` 或 `no_adoption_keep_p2_stage_on_abs_rbf_control`；
- results、videos、Hydra、metrics、traces、logs 的 checksums；
- canonical manifest checksum；
- 不含 credential。

manifest 写入后设置为只读，并以独立 SHA-256 文件验证不可变性。不得覆盖重写；如审计 bug 需要修正，保留旧版本并生成带 provenance 的新版本。

最终报告预注册路径：

```text
docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-06-eds-quality-diversity-report.md
```

## 15. 完成与进程清理

批准范围完成要求：

1. 新 branch/worktree provenance 已冻结；
2. config-controlled QD 实现与 legacy default 完成；
3. 目标测试、完整相关回归、`py_compile`、`git diff --check` 全部通过；
4. offline 与 LIBERO mechanism preflight 通过；
5. 11 个 formal jobs 已完成，或在 120-attempt cap 内有明确 failed/incomplete 原因；
6. 每个有效 job 10 个完整可读视频；
7. validity/task/mechanism/safety 审计、task-level 与定性分析完成；
8. immutable decision manifest 和最终报告完成；
9. Git diff 无 credential、无 P2 混入修改、无未审计产物；
10. 没有遗留 EDS Quality-Diversity runner、`main.py` 或实验子进程。

结果 gate 未通过不代表执行任务无法完成。完成预注册矩阵、失败分析、manifest、报告和清理后可以结束该阶段，但不得把失败解释为追加实验授权。

## 16. 停止条件与明确排除项

以下情况不得启动或继续新的 formal attempt，必须先修复并重新审计：

- 新 worktree 不基于明确 clean commit；
- legacy control 不再 bitwise-compatible；
- tests/preflight/storage/credential/GPU admission 失败；
- QD 改变了 reward/model call count 或 absolute-RBF 配置；
- archive accounting、selection fingerprint、RNG isolation 不成立；
- formal matrix/config fingerprint 冲突；
- attempt hard cap 已达到 120。

本阶段明确排除：

- top-N/cell capacity > 1；
- CVT-MAP-Elites、learned BD、3D/trajectory-shape BD；
- 预注册 3x3/4x4/5x5 之外的 grid 或自适应 grid；
- quality-biased mix、novelty score 或 QD-score optimization；
- cross-chunk/episode persistent archive；
- QD 与 Direction-Normalized RBF、adaptive ESS、anchors、memory、adaptive RBF/schedule 的组合；
- reward、VLM prompt、Stage policy 或 execution horizon 修改；
- 根据中间/final results 改 alpha、bounds、gates、ranking、tasks/seeds；
- 使用 retry reserve 追加 job 或第二套 outcome。

## 17. 待批准的冻结决策

执行前需将本文状态从 `Draft for review` 更新为 `Approved for execution`，并冻结以下设计：

1. 新 branch `exp/eds-quality-diversity` 与新 worktree `/home/hynx/VLA-Pilot++/.worktrees/exp/eds-quality-diversity`；
2. baseline 为原始 `p2_stage_on_abs_rbf_control`，initial/rollout 均为 absolute RBF；
3. BD 为 target-relative endpoint XY；
4. primary 为 chunk-local 4x4、q05/q95、10% expand、每轴最小 0.08 m，并按预注册 OFAT profiles sweep grid、quantiles、expand 和 minimum span；
5. cell capacity 为 1、higher-reward replacement、stable-fingerprint tie-break；
6. uniform-cell 与 inverse-visitation sparse-priority 两个 QD treatments；
7. `M=16`、`K=10`、alpha=1.0 和 P2 固定 mutation/search budget；
8. 11 jobs/110 formal episodes、6 preflight episodes、最多 4 个 recovery attempts、全阶段 hard cap 120；
9. GPU 仅使用 0..7 中通过 admission 的空闲设备；
10. 最终结果写入 `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/`，worktree `outputs` 仅为绝对软链接；
11. task/mechanism/safety gates、ranking、shared2/GPU/credential/manifest 标准。

批准后不得根据 preflight 或正式结果改写这些值；任何算法定义或实验矩阵变更必须先修订设计并重新审批。
