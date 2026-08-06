# P2 Direction-Normalized RBF 算法优化实验设计

日期：`2026-08-04`

状态：`Approved for execution`

## 1. 摘要

本轮以原始 `p2_stage_on` 为唯一算法基线，将当前基于 flattened EEF trajectory 绝对欧氏距离的 RBF diversity potential，替换为 Direction-Normalized RBF。新距离不再主要奖励“把整条轨迹拉长”，而是比较：

1. path-length-normalized endpoint direction；
2. path-length-normalized trajectory shape；
3. 权重较小且有界的 endpoint-position residual。

预注册组合权重为：

```text
0.6 × direction distance
+ 0.3 × normalized-shape distance
+ 0.1 × bounded endpoint-position distance
```

正式实验继续使用上一轮完全相同的 LIBERO-PRO `libero_object_swap` benchmark、strict perturbation、10 个 tasks、episode seeds、720-step budget、Stage Recognition ON 和 Gemini grounding OFF。为了同时验证完整替换和定位作用位置，本轮固定运行：

1. 1 个 contemporaneous P2 absolute-RBF baseline control；
2. 1 个只把 truncated rollout 改为 Direction-Normalized RBF 的 attribution ablation；
3. 9 个把 initial sampler 与 truncated rollout 都改为 Direction-Normalized RBF 的 global treatments，对 3 组 composite weights 和 3 组 endpoint scales 做完整 `3×3` sweep。

正式矩阵为 `11 jobs / 110 unique formal episodes`：1 个 control、1 个 rollout-only attribution ablation、9 个 global parameter jobs。另保留最多 10 个 episode attempts 作为同配置基础设施恢复预算，因此包括 retry 在内的实际执行总量也不得超过 120 episode attempts。恢复预算不能用于新参数或第二套 outcome。本轮只 sweep 已预注册的 composite weights 与 endpoint scale，不改变 RBF guidance scale、renoise、start ratio 或 clean-tail；`>=5/10` 仍是工程结果 gate，不是追加实验的授权。

## 2. 上一轮证据与问题定义

上一轮正式结果为：

| Method | Success | Success tasks | Final selected length P95 | Final max-step P95 | EEF direction median |
| --- | ---: | --- | ---: | ---: | ---: |
| P2 baseline rerun | 3/10 | `{3, 8, 9}` | 0.21200 | 0.03875 | 3.8558 |
| Low-scale Phase A winner | 2/10 | `{8, 9}` | 0.10162 | 0.01605 | 3.5444 |
| Winner + clean-tail | 0/10 | `{}` | 0.07257 | 0.00981 | 1.1039 |

低 scale 能降低 trajectory length 和 max-step，但没有超过 P2 baseline 的成功率；clean-tail 进一步压制动作幅值时，也把 EEF direction diversity 和 endpoint direction spread 大幅压低，最终从 2/10 降到 0/10。这说明仅降低 RBF scale 或直接关闭最后 denoise step 的 RBF 都没有解决核心矛盾：

- 绝对 EEF pairwise distance 会把路径长度当作 diversity；
- 候选可以通过扩大轨迹或单步位移获得更大的 RBF 距离；
- clean-tail 虽限制幅值，却同时失去有用的方向 mode coverage。

当前 `_compute_diversity_gradient` 将每条 EEF trajectory 的所有时刻坐标展平，再计算绝对欧氏距离：

```text
flat_h = flatten(EEF_h[1:])
distance(i, j) = ||flat_i - flat_j||_2
```

这一距离没有区分“方向/形状不同”和“同一方向但整体更长”。本轮目标是在保留 mode separation 的同时，让 uniform path stretching 不能无限增加 RBF diversity。

## 3. 研究问题与预注册假设

### 3.1 研究问题

1. Direction-Normalized RBF 是否能降低 absolute trajectory length、max-step displacement 和 chunk-boundary jump，同时保留 normalized direction diversity？
2. 只修改 truncated rollout 是否已经足够，还是 initial sampler 也必须使用相同 descriptor？
3. 新 descriptor 是否能把 RBF distance 与 path-length difference 解耦，并让 distance 更受方向和 shape 差异支配？
4. 机制改善能否转化为同一 10 tasks 上 `>=5/10` 的成功率？

### 3.2 假设

- **H1 — Scale exploit suppression。** 对同一 trajectory shape 做 uniform spatial scaling 时，direction 与 normalized-shape components 保持不变；总 composite distance 的变化最多来自权重为 0.1 的 bounded endpoint residual。
- **H2 — Mode retention。** 相对 contemporaneous P2 baseline，Direction-Normalized RBF 的 final EEF direction diversity 与 endpoint direction spread 至少保留 90%。
- **H3 — Magnitude control。** primary reference treatment（W0/E050）的 final selected trajectory-length P95 和 max-step P95 均不高于 baseline 的 85%。
- **H4 — Rollout attribution。** rollout-only treatment 若已满足 H2/H3，则 W0/E050 global treatment 与其差异可归因于 initial sampler descriptor；不得用结果事后改变 scope。
- **H5 — Task gate。** 至少一个有效 Direction-Normalized treatment 在同一 10 tasks 上达到 `>=5/10`，且无 qpos、nonfinite、action-mask 或 algorithm fallback violation。

H2/H3 是机制 claim gates，H5 是主要工程 adoption gate。即使 H5 通过，若 H2 失败，也不得宣称“保留方向 mode”；即使 H2/H3 通过但 H5 失败，也只能报告机制成立、任务收益未成立。

## 4. Direction-Normalized RBF 数学定义

### 4.1 轨迹记号

对 population 中第 `h` 个候选，RDT action 通过现有 differentiable adapter 投影为 EEF translation trajectory：

```text
P_h = [p_h,0, p_h,1, ..., p_h,H],  p_h,t ∈ R³
```

定义：

```text
Δp_h,t = p_h,t - p_h,t-1
L_h    = Σ_t ||Δp_h,t||₂
r_h    = p_h,H - p_h,0
```

其中 `L_h` 是 trajectory path length，`r_h` 是 endpoint displacement。只使用 XYZ translation；rotation、gripper 和 padding/action-mask 维度不进入 descriptor，与现有 RBF guidance mask 保持一致。

### 4.2 Direction descriptor

使用附图建议的 path-length-normalized endpoint displacement：

```text
q_h = r_h / (L_h + ε_L)
```

`q_h` 不只是单位 endpoint direction：其方向表示终点方向，其范数 `||q_h||≤1` 同时表示 path straightness。相同形状的轨迹做 uniform scaling 时，`r_h` 与 `L_h` 同比例变化，因此 `q_h` 基本不变。

两候选的 direction distance 定义为：

```text
D_dir(i,j) = 0.5 × ||q_i - q_j||₂
```

在非退化轨迹上 `D_dir∈[0,1]`。

### 4.3 Normalized trajectory-shape descriptor

先移除共同起点，再按各自 path length 归一化：

```text
S_h,t = (p_h,t - p_h,0) / (L_h + ε_L),  t=1...H
```

所有候选具有相同 action horizon，不需要结果驱动的重采样。shape distance 使用 time-normalized RMS，而不是再次 flatten 后直接求随 horizon 增长的 L2：

```text
D_shape(i,j)
  = 0.5 × sqrt((1/H) × Σ_t ||S_i,t - S_j,t||₂²)
```

`D_shape` 比较弯曲、绕行、侧向接近和上方接近等 normalized shape；对 common translation 和 uniform spatial scaling 不敏感。

### 4.4 Bounded endpoint-position residual

完全移除 endpoint magnitude 可能让轨迹只在方向上分离但落到几乎相同的可达位置，因此保留一个低权重、有界 residual：

```text
D_end(i,j)
  = tanh(||r_i - r_j||₂ / (τ_end + ε_L))
```

primary reference 预注册：

```yaml
direction_rbf_endpoint_scale_m: 0.05
```

`τ_end=0.05 m` 与本任务 4–8 cm 的接触/near-distance 量级一致。`D_end∈[0,1)`，即使无限拉长 endpoint，其对 composite distance 的最大贡献也受 endpoint weight 限制；使用 `tanh` 而不是 hard clamp，避免阈值外梯度突然归零。

### 4.5 Composite distance

```text
D_DN(i,j)
  = 0.6 × D_dir(i,j)
  + 0.3 × D_shape(i,j)
  + 0.1 × D_end(i,j)
```

primary reference 配置：

```yaml
direction_rbf_direction_weight: 0.6
direction_rbf_shape_weight: 0.3
direction_rbf_endpoint_weight: 0.1
direction_rbf_endpoint_scale_m: 0.05
direction_rbf_path_epsilon: 1.0e-6
direction_rbf_distance_epsilon: 1.0e-6
```

实现必须验证三个 weights 有限、非负且和为 1；只允许使用下节预注册的三组 profile，不得在正式实验后重新归一化或调整。

### 4.6 Composite weights 与 endpoint-scale sweep

在附图建议的 W0 基础上增加两组定向消融：W1 提高 endpoint-direction 的主导程度并进一步降低绝对 endpoint residual；W2 提高 normalized shape 的相对权重，检验弯曲/侧向/上方接近 mode 是否需要更强 shape separation。

| Weight profile | Direction | Shape | Endpoint | 解释 |
| --- | ---: | ---: | ---: | --- |
| W0 | 0.60 | 0.30 | 0.10 | 附图建议，primary reference |
| W1 | 0.75 | 0.20 | 0.05 | direction-heavy、最弱 absolute residual |
| W2 | 0.45 | 0.45 | 0.10 | direction/shape balanced |

endpoint scale 在 W0 的 0.05 m 两侧做对数对称的 `0.5×/2×` 消融：

| Endpoint profile | `τ_end` | 解释 |
| --- | ---: | --- |
| E025 | 0.025 m | 更早饱和，进一步限制 position residual 的作用范围 |
| E050 | 0.050 m | primary reference |
| E100 | 0.100 m | 更慢饱和，在常见操作距离内保留更多 endpoint-position discrimination |

global treatments 使用 `W{0,1,2} × E{025,050,100}` 完整全因子矩阵，共 9 jobs。这样报告可以分别估计 weight 主效应、endpoint-scale 主效应及二者交互；不得只挑选看起来更好的 cell 报告。

### 4.7 RBF potential 与 gradient

除 pairwise distance 外，保持当前 inverse-distance potential、gradient normalization、sign、denoise step mask 和 translation-only action mask 不变：

```text
V = Σ_i≠j 1 / (sqrt(D_DN(i,j)² + ε_D²) + ε_D)
g = ∂V/∂x
g_norm = g / (||g||₂ + ε_g)
```

然后沿用现有：

```text
model_output += RDT_DIVERSITY_SIGN × configured_scale × masked(g_norm)
```

这样正式 treatment 与 P2 control 的唯一算法差异是 EEF pairwise descriptor；不会同时改变 RBF scale、gradient normalization 或 scheduler 行为。

### 4.8 Degenerate path 与数值语义

- 当 `L_h≤ε_L` 时，使用公式本身得到有限的 `q_h` 和 `S_h`，同时记录 `zero_path_descriptor_count`；不得除零或产生 NaN。
- Direction-Normalized scope 内不得自动 fallback 到 absolute distance。任何 absolute fallback 都使 job invalid。
- population size 大于 1 时，若 composite gradient norm 为 0，必须记录 `direction_rbf_zero_gradient_count`；正式 job 要求该计数为 0。
- nonfinite descriptor、pairwise component、potential 或 gradient 必须显式失败并保留 evidence，不得静默继续。
- current absolute mode 必须保留为独立、bitwise-backward-compatible branch，供 control 与旧实验复现。

## 5. 配置与实现边界

### 5.1 新配置字段

新增机制必须沿用前几轮实验的集成方式：在现有 `_EDSConfig`、Hydra overrides、metrics 和 runner profile 中增加字段，通过 config 显式开启/关闭，不复制第二套 policy/core，也不根据 job label 在核心代码中硬编码分支。

为了分别控制 initial 和 rollout scope，新增：

```yaml
initial_diversity_descriptor_mode: absolute_eef
rollout_diversity_descriptor_mode: absolute_eef
```

合法值：

```text
absolute_eef
direction_normalized_eef
```

默认值必须是 `absolute_eef`，保证所有旧配置不变。Direction-Normalized weights 和 endpoint scale 只在对应 scope 为 `direction_normalized_eef` 时生效。

这里的 descriptor mode 本身就是机制开关：

```text
absolute_eef             = Direction-Normalized RBF OFF，执行 legacy absolute branch
direction_normalized_eef = Direction-Normalized RBF ON
```

不再新增可能与 mode 冲突的第二个 boolean `enabled`。weights 与 endpoint scale 同样必须来自 config：

```yaml
direction_rbf_direction_weight: 0.60
direction_rbf_shape_weight: 0.30
direction_rbf_endpoint_weight: 0.10
direction_rbf_endpoint_scale_m: 0.05
direction_rbf_path_epsilon: 1.0e-6
direction_rbf_distance_epsilon: 1.0e-6
```

absolute control 即使收到这些默认字段也必须完全忽略它们，保持 legacy output bitwise-compatible。每个 formal job 的 resolved config、Hydra overrides、job manifest 和 config fingerprint 必须记录实际 mode/weights/scale。

### 5.2 预期代码结构

建议将当前 `_compute_diversity_gradient` 拆分为：

```text
_eds_eef_rbf_pairwise_distance(..., descriptor_mode, descriptor_cfg)
_eds_direction_normalized_descriptor(...)
_eds_direction_normalized_distance_components(...)
_compute_diversity_gradient(..., descriptor_mode, descriptor_cfg)
```

initial sampler 必须显式传入 `initial_diversity_descriptor_mode`；truncated rollout 必须显式传入 `rollout_diversity_descriptor_mode`。禁止依赖 mutable global “current mode”，避免并发或 resume 时 scope 混淆。

所有新增 helper 必须服务于同一个 core execution path；不得创建 `rdt_policy_steer_directional.py`、复制 `_eds_rollout_rbf_diverse_reference`，或在 runner 内替换算法函数。runner 只负责生成 config，核心行为只能由 resolved config 决定。

### 5.3 不允许同时修改

本轮不得修改：

- initial/rollout RBF scale 或 start ratio；
- renoise schedule、rollout iters、skip-final steps；
- population size、EDS iterations、temperature、reward；
- parent weighting、ESS、anchors、elite carryover、memory 或 adaptive controller；
- execution horizon、Stage Recognition、VLM prompt、Gemini grounding；
- RDT checkpoint、scheduler inference steps、action layout；
- 预注册矩阵之外的 direction/shape/endpoint weights、`τ_end` 或 epsilon。

如需调整上述任一项，必须先修改设计并重新审批，不得根据正式结果追加。

## 6. 必需 Metrics 与机制证据

保留上一轮全部 metrics，并新增：

```text
initial_diversity_descriptor_mode
rollout_diversity_descriptor_mode
direction_rbf_weights
direction_rbf_endpoint_scale_m
direction_rbf_pairwise_direction_mean/p90/max_by_iter
direction_rbf_pairwise_shape_mean/p90/max_by_iter
direction_rbf_pairwise_endpoint_mean/p90/max_by_iter
direction_rbf_pairwise_composite_mean/p90/max_by_iter
direction_rbf_weighted_component_fraction_by_iter
direction_rbf_distance_path_length_delta_correlation_by_iter
direction_rbf_distance_direction_correlation_by_iter
direction_rbf_zero_path_descriptor_count_by_iter
direction_rbf_zero_gradient_count
direction_rbf_nonfinite_count
direction_rbf_grad_norm_before_normalization_by_iter
direction_rbf_grad_norm_after_mask_by_iter
```

initial sampler 与 rollout 必须分别记录，不能只给 job-level 合计。已有以下 metrics 继续作为主分析指标：

- selected/population trajectory length mean/P90/max；
- selected/population max-step displacement mean/P90/max；
- trajectory-length 与 max-step expansion ratio；
- `eef_direction_diversity_by_iter`；
- `endpoint_direction_spread_by_iter`；
- `chunk_boundary_action_jump`；
- `rollout_rbf_steps_by_iter`；
- `gripper_qpos_violation_count`；
- Stage events、query latency、guidance OFF/ON transitions；
- selection/action latency、reward、parent/lineage 和 qualitative trace。

所有 correlation 必须同时记录 valid pair count；方差为 0 时输出 `null + warning`，不得伪造为 0。

## 7. TDD 与实现前机制测试

正式实验前至少覆盖以下测试。

### 7.1 Descriptor 单元测试

- common translation invariance；
- uniform scaling `α∈{0.5, 2, 4}` 时 `D_dir` 与 `D_shape` 在容差内不变；
- 同 direction/shape 但不同 scale 时，composite 变化只来自 bounded endpoint term，且不超过 0.1；
- 相同 path length、不同 endpoint direction 时 `D_dir>0`；
- 相同 endpoint、不同弯曲 shape 时 `D_shape>0`；
- endpoint residual 单调、有限且严格小于 1；
- pairwise matrix 对称、对角为 0、permutation equivariant；
- zero-length、near-zero、mixed precision 和极端 finite trajectory 不产生 nonfinite；
- weights 与 `τ_end/epsilon` 的 invalid config 被拒绝。

### 7.2 Gradient 测试

- autograd gradient finite、shape 正确且 population permutation equivariant；
- normalized direction/shape gradient 对 uniform radial scaling direction 的投影接近 0；
- endpoint component 的 radial effect 有界；
- gradient normalization 与当前 absolute branch 一致；
- action mask 后只修改有效 horizon 的 XYZ translation，rotation、gripper、padding 不变；
- zero/nonfinite gradient 计数和 fail-closed 语义正确；
- Direction-Normalized mode 不会进入 absolute fallback；
- `absolute_eef` branch 对固定输入与当前实现 bitwise 一致。

### 7.3 Runner、Validity 与报告测试

- 正式矩阵严格为 11 jobs / 110 episodes，不含低-scale winner 或 clean-tail；
- global parameter matrix 恰好是 3 weights × 3 endpoint scales 的 9 个唯一 cells，无缺失、重复或额外组合；
- baseline profile 与原始 P2 完全一致；
- rollout-only 只改变 rollout descriptor；
- W0/E050 global reference 只改变 initial 和 rollout descriptor；
- 其他 global cells 相对 W0/E050 只改变预注册 weights 和/或 endpoint scale；
- descriptor mode 由 config 控制，legacy default 为 OFF，核心代码中不存在 job-label 分支；
- tasks/seeds、Stage、strict perturbation 和其他 profile 完全相同；
- resume 跳过完整 valid job，invalid/incomplete job 可恢复；
- episode-attempt ledger 对正式运行和 retry 统一计数，hard cap 为 120；
- 已完成且有效的 episode 不得在 retry 中重复执行，恢复预算最多 10 attempts；
- 单 job failure 不终止其他 jobs，retry 不改变配置；
- shared2 realpath、绝对软链接、视频可读性、Hydra、日志和 credential scan；
- descriptor-mode audit、无 silent fallback、metrics completeness；
- deterministic adoption ranking 与 immutable decision manifest；
- final report writer 的 task-level、mechanism、latency 和 qualitative tables。

正式运行前必须通过目标测试、完整相关回归、`py_compile` 和 `git diff --check`。

## 8. 固定 Benchmark 与运行设置

| 项目 | 固定值 |
| --- | --- |
| Benchmark | LIBERO-PRO OOD Evaluation |
| Suite | `libero_object_swap` |
| Strict perturbation | `true` |
| Tasks | `0..9`，每 task 1 episode |
| Episode seeds | `[44, 235, 43, 546, 6, 621, 197, 87, 151, 548]` |
| Root seed | `0` |
| Max episode steps | `720` |
| Stage Recognition | ON，使用真实环境变量 credential |
| Gemini grounding | OFF |
| Rendering/video | ON |
| Action execution horizon | `8` |

P2 baseline 固定配置：

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
```

上一轮的 `scale=5` winner 和 `skip_final=1` clean-tail 只作为历史证据，不进入本轮配置或 formal ranking。

## 9. 正式实验矩阵

### 9.1 十一个预注册 jobs

| Job / family | 数量 | 角色 | Initial descriptor | Rollout descriptor | Weights / endpoint scale |
| --- | ---: | --- | --- | --- | --- |
| `p2_stage_on_abs_rbf_control` | 1 | contemporaneous control | `absolute_eef` | `absolute_eef` | ignored by legacy branch |
| `p2_stage_on_dirnorm_rbf_rollout_w0_e050` | 1 | attribution ablation | `absolute_eef` | `direction_normalized_eef` | W0 / E050 |
| `p2_stage_on_dirnorm_rbf_global_w{0,1,2}_e{025,050,100}` | 9 | global full-factorial treatments | `direction_normalized_eef` | `direction_normalized_eef` | 3×3 matrix |

9 个 global labels 必须精确展开为：

```text
p2_stage_on_dirnorm_rbf_global_w0_e025
p2_stage_on_dirnorm_rbf_global_w0_e050
p2_stage_on_dirnorm_rbf_global_w0_e100
p2_stage_on_dirnorm_rbf_global_w1_e025
p2_stage_on_dirnorm_rbf_global_w1_e050
p2_stage_on_dirnorm_rbf_global_w1_e100
p2_stage_on_dirnorm_rbf_global_w2_e025
p2_stage_on_dirnorm_rbf_global_w2_e050
p2_stage_on_dirnorm_rbf_global_w2_e100
```

job manifest 必须同时保存 label 所对应的三个展开 weights 和浮点 endpoint scale；runner 不得只从 label 反向解析参数。

```text
1 control
+ 1 rollout-only attribution
+ 9 global parameter cells
= 11 jobs × 10 episodes
= 110 formal episodes
```

110 unique episodes 是本轮完整正式矩阵。剩余 10 episode attempts 只作为基础设施失败恢复预算；正式运行与 retry 共用一个 append-only attempt ledger，实际启动 attempt 数 hard cap 为 120。恢复只能继续同一个 formal job 的同一 task/seed/config，已完整有效的 episode 不重复运行，并保留 attempt provenance。预算不得用于第二套 outcome、补跑新参数或结果驱动实验；若恢复会使总 attempt 数超过 120，则停止并将对应 job 标记为有明确原因的 incomplete/failed。

11 个 jobs 可在 mechanism preflight 和全部测试通过后按 GPU admission 结果并行运行；矩阵在启动前一次性冻结，禁止根据中间 task results 停止、改权重、删 cell 或追加配置。

### 9.2 对比解释

- control vs rollout-only：truncated rollout descriptor 的净效应；
- rollout-only W0/E050 vs global W0/E050：initial sampler descriptor 的增量效应；
- control vs global W0/E050：本轮附图默认方案的 primary comparison；
- global 9-cell grid：weights、endpoint scale 的主效应和交互；
- control vs 预注册 adoption winner：最终工程候选对比。

primary reference treatment 始终是 global W0/E050，不能在报告中因其他 cell 或 rollout-only 结果更好而改写 primary hypothesis。预注册 adoption rule 可以从 10 个 Direction-Normalized jobs 中选择唯一工程候选，但必须同时完整报告 9-cell grid 和 rollout attribution。

## 10. 实现前 Mechanism Preflight

Mechanism preflight 不计入 110 个 formal episodes，不读取 formal outcome，也不允许用于调参。它只验证实现语义：

1. synthetic straight/curved/side-approach/upward-approach trajectories；
2. 对同一 shape 做 `0.5×/2×/4×` scaling；
3. 固定 recorded tensor 或 deterministic stub population；
4. absolute 与 Direction-Normalized pairwise component、potential 和 gradient 对比；
5. mixed precision、action-mask 和 zero-path stress test。

必须生成 machine-readable preflight JSON，固定记录：config、input checksum、component distances、scale-invariance error、gradient norm、masked dimensions、nonfinite/zero-gradient count。Preflight 任一 hard gate 失败时不得启动正式实验。

Preflight 只允许修复实现 bug；不得基于 preflight 数值改变 W0/W1/W2、E025/E050/E100、formal matrix 或 task protocol，除非重新送审本文档。

## 11. 结果 Gate 与 Adoption Rule

### 11.1 Validity eligibility

进入分析的每个 job 必须满足：

- 10/10 episode results；
- 10 个 ffprobe-readable videos；
- strict perturbation 与 `libero_object_swap` suite 验证；
- Hydra config/overrides、job manifest、完整 log、EDS metrics、Stage events 和 qualitative artifacts；
- output realpath 位于本轮 shared2 root；
- 0 nonfinite、0 action-mask violation；
- 无普通 LIBERO fallback、无 algorithm/descriptor silent fallback；
- Direction-Normalized scope 中 0 absolute fallback、0 zero-gradient、0 direction-RBF nonfinite；
- credential scan 通过。

qpos/execution error 不静默删除 episode，必须作为失败 outcome、safety evidence 和 ranking 字段报告。若属于基础设施损坏而非 deterministic policy execution，必须按预注册 retry 规则处理并保留旧 attempt。

### 11.2 三类结果 gate

**Task gate：**

```text
success_count >= 5/10
```

**Mechanism claim gate，相对 contemporaneous control：**

```text
final EEF direction diversity median ratio >= 0.90
final endpoint direction spread median ratio >= 0.90
final selected trajectory-length P95 ratio <= 0.85
final selected max-step P95 ratio <= 0.85
```

**Safety gate：**

```text
qpos/execution error episodes = 0
collision/push/drop/wrong-object composite <= control
nonfinite = 0
action-mask violation = 0
fallback = 0
```

Task gate 未通过时不得把“机制指标更好”表述为算法成功；mechanism gate 未通过时不得把 SR 提升归因为“保留 mode 且限制幅值”。

### 11.3 Direction-Normalized candidate ranking

10 个 Direction-Normalized jobs（1 个 rollout-only W0/E050 + 9 个 global cells）中的 eligible jobs 按以下九级规则确定唯一 adoption candidate：

1. success count 降序；
2. control 成功 tasks 的 retention 降序；
3. qpos/execution error episodes 升序；
4. collision/push/drop/wrong-object composite 升序；
5. final selected max-step P95 升序；
6. final selected trajectory-length P95 升序；
7. direction-retention score 降序，其中 `score=min(EEF direction ratio, endpoint direction ratio)`；
8. selection latency median 升序；
9. label 字典序。

只有同时通过 task、validity 和 safety gates 的 candidate 才能标记为 `recommended_for_adoption=true`。如果所有 Direction-Normalized jobs 都未达到 5/10，decision manifest 必须明确记录 `no_adoption`，不得把 10-attempt recovery reserve 转为额外 sweep。

baseline control 不进入 Direction-Normalized candidate ranking，但若无 candidate 通过 gate，工程结论应保留原始 P2 baseline。

## 12. Failure、Task-Level 与统计报告要求

报告必须逐 task 给出 control、rollout-only 和 global 的 paired outcome，并至少保留上一轮的失败类别：

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
- timeout without task completion。

必须报告：

- task success transition matrix，包括 control→treatment gained/lost/retained tasks；
- success rate、success count 和 Wilson interval；
- global 9-cell 的完整 outcome/validity 表，不得只展示 winner；
- weights 的主效应：每个 W profile 跨 3 个 endpoint scales 聚合；
- endpoint scale 的主效应：每个 E profile 跨 3 个 weight profiles 聚合；
- weight × endpoint-scale interaction heatmap/table；
- trajectory length、max-step、expansion ratio、direction diversity、endpoint direction spread；
- Direction-Normalized 三个 component 的分布和 weighted contribution；
- composite distance 与 path-length delta / direction distance 的 correlation；
- initial 与 rollout 的分项机制差异；
- collision、推远、掉落、wrong-object、qpos 和 placement failures；
- action latency、Stage query latency、query errors、OFF/ON transitions；
- 相同时间坐标的 qualitative contact sheets 和关键 tensor/curve evidence。

每 job 只有 10 episodes，所有推断必须表述为固定任务集上的工程配对结果，不宣称统计显著性或泛化性能。

## 13. Runner、存储与 Credential

预注册新输出根目录：

```text
/mnt/data/shared2/zhuoli/output/p2_direction_normalized_rbf
```

worktree 兼容路径：

```text
outputs/ood_eval/p2_direction_normalized_rbf
```

执行前要求与上一轮相同：

- shared2 目标可写且至少 50 GiB 可用；
- 安全创建不存在的目标，不覆盖、删除或移动既有输出；
- link path 若存在必须先审计；
- 使用绝对软链接，并以 `readlink -f` 和 probe file 验证落盘；
- videos、metrics、Hydra、logs、manifests、qualitative evidence 和 runtime cache 全部位于 shared2；
- Git 管理的设计与报告继续保存在 `docs/`。

runner 必须支持 per-job resume、independent failure、conservative retry、完整-valid skip 和 immutable config fingerprint。

GPU 不再限定为 2/3/4/5。runner 可以使用服务器上任意可见 GPU，包括：

- 完全空闲的 GPU；
- 已有其他任务、但显存和 compute mode 允许安全共存的 GPU。

GPU admission 必须基于运行时资源审计，而不是只看 utilization 是否为 0：

1. 枚举全部 visible CUDA devices，记录 index、UUID、型号、总/可用显存、utilization、compute mode 和已有 compute-process count；
2. 设备不得处于不兼容的 exclusive mode；
3. 可用显存必须至少满足 `max(reference_peak_vram × 1.25, reference_peak_vram + 4 GiB)`；`reference_peak_vram` 由同 checkpoint/config 的只加载 preflight 或已审计历史峰值确定并冻结到 run manifest；
4. 允许与外部任务 co-locate，但不得终止、暂停、修改或抢占其进程；
5. 默认每个 GPU 最多放置 1 个本轮 worker；最大并发为 `min(4, eligible_gpu_slots)`；
6. OOM 或资源争用失败只允许将同一个 job 以相同 config/task/seed 迁移到其他 eligible GPU，旧 attempt 和 failure reason 必须保留；
7. dispatch 与完成时记录实际 GPU UUID、显存快照和 co-location 状态，报告中分析 GPU/latency 混杂。

空闲设备优先，但“已有任务”本身不构成排除条件；资源不足或 exclusive mode 才构成排除条件。

Stage Recognition credential 只通过运行时环境变量注入；health check 不得回显 token。credential 不得进入命令行、Hydra、manifest、log、report 或 Git。

## 14. Manifest 与最终报告

所有 11 个 formal jobs 完成并通过 audit 后，生成只读 decision manifest：

```text
manifests/direction_rbf_decision_manifest.json
```

manifest 必须包含：

- 11 个完整 profiles 与 config/code fingerprints；
- W0/W1/W2 × E025/E050/E100 的 9-cell matrix completeness evidence；
- task-level results；
- validity/safety/mechanism gates；
- Direction-Normalized ranking evidence；
- primary global W0/E050 treatment 的独立结论；
- weights、endpoint scale 主效应与 interaction evidence；
- `recommended_for_adoption` 或 `no_adoption`；
- results、Hydra、metrics、Stage events 和 logs 的 checksums；
- canonical manifest checksum；
- 不含任何 credential。

最终报告预注册路径：

```text
docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-04-p2-direction-normalized-rbf-report.md
```

## 15. 停止条件与禁止的结果驱动操作

以下情况停止正式启动并修复/重新审计：

- mechanism preflight、测试或 storage/credential health check 失败；
- baseline 不再复现 absolute branch 语义；
- Direction-Normalized config scope 与矩阵不符；
- nonfinite、mask violation 或 silent fallback；
- formal output fingerprint 冲突且无法安全恢复。

以下操作禁止：

- 根据前几个 tasks 调整 W0/W1/W2、E025/E050/E100、RBF guidance scale 或 scope；
- 因 rollout-only 优于 global 而提前停止 global；
- 因未达到 5/10 而追加 scale/weight/renoise sweep；
- 将未使用的 recovery attempts 解释为追加一个新 job 的授权；
- 复用失败 episode 并更换 seed；
- 删除失败 attempt 或无审计覆盖输出；
- 将上一轮 scale-5 winner 或 clean-tail 混入本轮矩阵。

完成批准的 11 jobs、validity audit、decision manifest 和报告后，无论 `>=5/10` 是否通过，本轮实验均可结束；gate 失败时必须明确报告失败原因和后续建议。

## 16. 已纳入确认项与待审决策点

本次修订已纳入以下用户确认约束：

- 在附图 W0 权重外增加两组 composite-weight experiments；
- 在 E050 外增加两组 endpoint-scale ablations；
- 总规模不超过 120 episodes；
- 可使用服务器上任意空闲或资源允许安全共存的 GPU；
- 新 RBF 机制沿用前几轮方式，通过 config 开启/关闭，不复制或硬编码核心路径。

请在批准执行前审阅以下具体落地值：

1. **Scope：** primary treatment 为 initial+rollout 全局替换，并保留 rollout-only attribution ablation；
2. **Composite weights：** W0=`0.60/0.30/0.10`、W1=`0.75/0.20/0.05`、W2=`0.45/0.45/0.10`；
3. **Endpoint scale：** E025=`0.025 m`、E050=`0.050 m`、E100=`0.100 m`，均使用 `tanh` bounded residual；
4. **正式规模：** 1 control + 1 rollout-only + 9 global cells，共 110 unique formal episodes；加最多 10 个同配置 recovery attempts 后，实际执行 hard cap 为 120；
5. **GPU admission：** 任意 visible GPU，允许安全 co-location，按动态显存 headroom 审计，最多 4 workers；
6. **Gates：** task `>=5/10`、direction retention `>=0.90`、length/max-step P95 `<=0.85× control`，并使用本文九级 adoption rule。

在这些决策点全部批准前，本文保持 `Draft for review`，不得进入实现或正式实验。
