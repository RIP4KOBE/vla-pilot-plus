# EDS-QD 搜索预算参数 Sweep 简要设计

日期：`2026-08-08`

状态：`Approved design — execution not started`

## 1. 结论先行

本实验作为 `population_size × cem_iters` 的二维搜索预算 sweep 有意义，但按当前代码把 `num_elites` 作为第三个正式因子没有意义：

- `population_size` 控制 initial population 和每轮 QD offspring 数，代表搜索广度；
- `cem_iters` 在 `use_cem=false` 时仍控制 EDS/QD 循环次数，代表搜索深度；
- 两个 QD 基线均为 `use_cem=false`。QD 分支从 archive 为全部 population 分配 parent，显式使用空的 `elite_indices`，不会调用依赖 `num_elites` 的 CEM selector。因此 `num_elites=16/32` 当前是行为等价配置。

因此不运行原始的完整三因子矩阵：

```text
2 QD baselines × 3 population_size × 3 cem_iters × 2 num_elites
= 36 treatments / 360 formal episodes
```

它会把 18 个真实配置各重复一次，并可能把环境/API 波动误判为 `num_elites` 主效应。批准的正式矩阵固定 `num_elites=16`，只运行：

```text
2 QD baselines × 3 population_size × 3 cem_iters
= 18 treatments
= 18 jobs / 180 formal episodes
```

本轮不运行 control、原参数 QD reference、额外 parameter profile、LIBERO mechanism-preflight job 或 held-out confirmation job。若以后研究“QD elite 数量”，应另行定义 `qd_global_elite_carryover_count`、每 cell capacity 或 top-N archive 等新语义，不得复用当前无效的 `num_elites` 字段。

## 2. 动机与已有证据

上一轮固定 `population_size=16`、`cem_iters=10`：

- `p2_stage_on_abs_rbf_control` 为 `3/10`；
- `eds_quality_diversity_uniform_expand20` 为 `2/10`，成功 tasks `{5, 7}`；
- `eds_quality_diversity_sparse_primary` 为 `2/10`，成功 tasks `{5, 8}`；
- 两个候选均通过 mechanism hard 与 safety gates，但 task 和 mechanism claim gates 失败；
- 两者的 paired coverage delta median 均为 `0.000`，replacement-active ratio 分别为 `0.210/0.190`，overflow P95 均为 `0.938`。

证据见 `docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-06-eds-quality-diversity-report.md`。这说明增加 offspring 数或迭代深度可能提高 cell 内 replacement 和 best-reward 搜索，但它不是针对 descriptor、frozen bounds 或 overflow 的直接修复，成功率提升的先验预期应保持谨慎。

代码依据：

- `core/rdt_policy_steer.py:4967`：循环次数由 `cfg.cem_iters` 控制；
- `core/rdt_policy_steer.py:4982-5074`：QD 为全部 `cfg.population_size` 分配 archive parents，并令 `elite_indices` 为空；
- `core/rdt_policy_steer.py:4331-4344`：`num_elites` 只在 `cfg.use_cem` 的非 QD parent selector 中使用；
- `core/rdt_policy_steer.py:6255-6261`：完整 chunk 候选评估数为 `population_size × (cem_iters + 1)`。

## 3. 研究问题与假设

1. 增大 `population_size` 是否通过为每个 occupied cell 产生更多独立 offspring，提高 replacement、best reward 和 task success？
2. 增大 `cem_iters` 是否通过更长的 archive refinement 提高 task success，还是只增加 latency、轨迹漂移和同一 edge cell 上的重复搜索？
3. 在近似相同候选评估预算下，更宽 population 与更深 iterations 哪一种更有效？
4. uniform-expand20 与 sparse-primary 对搜索预算的响应是否不同？

预注册假设：

- **H1 — Breadth：** 较大 population 提高 replacement-active ratio 或 archive best reward，但 4×4、capacity=1 的最大 occupied cells 仍为 16，不预期仅靠 population 提高 coverage 上限。
- **H2 — Depth：** 较多 iterations 提高 cell 内 quality；若 replacement 很快归零，则继续增加 iterations 只会增加计算。
- **H3 — Breadth/depth：** 在近似等预算组合中，成功率、best reward、replacement 和 latency 可区分“更多并行 offspring”和“更多 refinement generations”。
- **H0 — `num_elites`：** 在当前 QD 路径中，16 与 32 的 mechanism trace 和最终 action 应完全相同；该假设只做静态/确定性测试，不消耗 LIBERO formal episodes。

## 4. 参数矩阵与计算预算

固定范围：

```yaml
population_size: [32, 48, 64]
cem_iters: [15, 20, 25]
num_elites: 16  # 当前 QD 路径无效，固定而不作为 formal 因子
use_cem: false
```

完整 EDS chunk 的候选评估数为 `M × (K + 1)`；原始 QD reference 为 `16 × 11 = 176`：

| population | iterations | evaluations/chunk | 相对原始预算 |
| ---: | ---: | ---: | ---: |
| 32 | 15 | 512 | 2.91× |
| 32 | 20 | 672 | 3.82× |
| 32 | 25 | 832 | 4.73× |
| 48 | 15 | 768 | 4.36× |
| 48 | 20 | 1008 | 5.73× |
| 48 | 25 | 1248 | 7.09× |
| 64 | 15 | 1024 | 5.82× |
| 64 | 20 | 1344 | 7.64× |
| 64 | 25 | 1664 | 9.45× |

主要等预算归因对：

- `p32_k25`（832）对 `p48_k15`（768）；
- `p48_k20`（1008）对 `p64_k15`（1024）；
- `p48_k25`（1248）对 `p64_k20`（1344）。

全 3×3 grid 用于观察响应面和交互；上述等预算配对用于区分 breadth 与 depth。不同总预算配置的成功率不得直接解释为参数本身优于另一配置，必须同时报告每 chunk evaluations、episode wall time、selection latency 和 success/evaluation。

## 5. 两个 QD family 与固定设置

### 5.1 QD family

`eds_quality_diversity_uniform_expand20` 固定：

```yaml
qd_parent_sampling: uniform_cells
qd_grid_shape: [4, 4]
qd_bounds_quantiles: [0.05, 0.95]
qd_bounds_expand_fraction: 0.20
qd_min_axis_span_m: 0.08
```

`eds_quality_diversity_sparse_primary` 固定：

```yaml
qd_parent_sampling: sparse_priority
qd_sparse_exponent: 1.0
qd_grid_shape: [4, 4]
qd_bounds_quantiles: [0.05, 0.95]
qd_bounds_expand_fraction: 0.10
qd_min_axis_span_m: 0.08
```

其余 QD、absolute-EEF RBF、reward、Stage Recognition、execution horizon、checkpoint 和 simulator 配置逐字段继承上一轮，不得与本 sweep 联动修改。

### 5.2 Benchmark

| 项目 | 固定值 |
| --- | --- |
| Suite | `libero_object_swap`，strict perturbation |
| Tasks | `0..9`，每 task 1 episode |
| Episode seeds | `[44, 235, 43, 546, 6, 621, 197, 87, 151, 548]` |
| Root seed | `0` |
| Max steps | `720` |
| Stage Recognition | ON，credential 仅由环境变量注入 |
| Gemini grounding | OFF |
| Rendering/video | ON |
| GPU | GPU `0..7` 中通过 admission 的设备；允许与外部 compute 共置 |

上一轮已审计的 control、uniform-expand20 和 sparse-primary 结果只作为冻结历史背景，不在本轮重跑，也不作为 contemporaneous causal control。正式 ranking 只包含以下 18 个新 jobs：

job 命名：

```text
eds_qd_{uniform_expand20|sparse_primary}_p{32|48|64}_k{15|20|25}
```

## 6. 最小实现、执行与审计

### 6.1 不增加实验 job 的最小审计

1. 增加 matrix/config/command/fingerprint 测试，断言恰好 18 个 formal jobs、固定 task-seed mapping、无重复 config，且只包含批准的 `2×3×3` 参数组合。
2. 对固定 QD input 分别设置 `num_elites=16/32`，断言 parent allocation、archive state、candidate fingerprints、reward、final action 和 RNG state 完全相同；若不相同，先解释代码路径，不得启动 formal。
3. 参数化 mechanism accounting，断言每完整 chunk 为 `M × (K+1)` 次评估，且没有额外 model/reward/VLM 调用。

以上均为本地确定性测试/静态审计，不启动 LIBERO episode，不计入 18 个实验 jobs。除实现这 18-job matrix 所必需的目标测试和相关回归外，不新增算法消融、参数试跑或结果探索测试。

### 6.2 Formal-only 执行

不运行独立 LIBERO preflight episodes。第一个 formal attempt 启动前只做 storage、credential、config fingerprint、进程和 GPU admission 检查。正式矩阵冻结后完整执行 18 jobs；单 job 失败不删除或改变其他组合。

formal 与 same-config retry 使用同一 append-only ledger。预注册 `20` 个 recovery attempts；retry 只能保持相同 job/task/seed/config/code fingerprint：

```text
180 formal + at most 20 recovery = attempt cap 200
```

所有新产物写入既有 shared2 软链接下的独立 `search_budget_sweep_20260808/` namespace，不覆盖上一轮 immutable artifacts。不得在 worktree 的 home 实体目录写入视频、tensor、cache 或大日志。

GPU admission 在 `0..7` 上动态进行：

- 外部 compute process、非零利用率或已有显存占用本身不构成拒绝理由；
- 设备必须有足够的实时空闲显存、正常 compute mode 且无新的 Xid/ECC/driver fault；
- 可同时使用多个通过 admission 的 GPU，每个 GPU 同时最多运行一个本实验 job；
- OOM 或硬件异常只能把同一 attempt 审计后迁移到另一台通过 admission 的 GPU，不得改变配置；
- 不终止、限速或干扰外部进程。

## 7. Gates、排名与停止规则

### 7.1 Validity 与 mechanism hard gate

- 每 job 必须有 10/10 唯一 task records、完整可读视频、metrics、trace、config/code fingerprint；
- 0 nonfinite、0 action-mask violation、0 QD fallback、0 archive accounting/monotonicity/final-selection mismatch；
- 每完整 chunk 的评估数严格为 `M × (K+1)`；
- uniform/sparse parent allocation 分别符合既有公式；
- credential scan、shared2 realpath 和 GPU provenance 通过。

### 7.2 Task 与 safety gate

每个候选的 task gate 保持：

```text
success_count >= 5/10
```

safety gate 保持 0 qpos/execution error、0 nonfinite、0 mask violation、0 algorithm fallback；collision/push/drop/wrong-object composite 同时报告并不得高于对应 frozen historical family reference。由于不运行 contemporaneous control，任何跨轮差异都必须标注为历史比较。

### 7.3 Mechanism 解释与排名

每个候选报告 coverage、spread、replacement-active ratio、turnover、overflow P95、archive best reward、trajectory geometry、selection latency 和 candidates evaluated，并与同 family 的冻结历史 `p16_k10` 结果作带限定的背景比较。由于本 sweep 不修改 descriptor/bounds，若 task gate 通过但 coverage/overflow 未改善，只能归因为“更高搜索预算相关的工程提升”，不得宣称 QD niche coverage 问题已解决。

只在 valid 且通过 task/safety gates 的候选中排名：

1. success count 降序；
2. 相对同 family 冻结历史 reference 的 paired gained-minus-lost tasks 降序；
3. candidates evaluated per success 升序；
4. selection latency P95 升序；
5. replacement-active ratio 和 best-reward delta 降序；
6. job label 字典序。

`>=5/10` 是固定 10-task 集上的工程 gate。由于从 18 个候选中选择 winner，不能把它解释为统计显著或总体泛化；winner 冻结后不得在同一结果上调参、重跑确认或追加组合。

停止条件：18 个 formal jobs 完成或在 attempt cap 内留下明确审计的 failed/incomplete；结果未达到 `5/10` 不授权追加参数。单一配置 OOM 或严重超时只影响该配置的 same-config retry/failed 状态，不停止其他 jobs，也不得静默缩小配置。

## 8. 冻结决策

1. 正式矩阵严格为 `2 families × 3 population_size × 3 cem_iters = 18 jobs`；
2. `num_elites=16` 固定，只做不消耗 episode 的 no-op audit；
3. 不增加 control/reference/preflight/held-out 或其他实验 jobs；same-config retry 不属于新 job；
4. GPU 从 `0..7` 动态 admission，允许与外部 compute 共置；
5. 执行前冻结 branch/commit、18-job manifest、shared2 namespace 和 attempt cap。
