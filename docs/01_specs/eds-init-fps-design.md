# EDS Initial Population FPS 多样化设计

## 1. 标题与摘要

方案名称：**Policy-Manifold Oversampling + Trajectory-Space FPS Filtering**。

本方案解决当前 EDS 初始动作候选容易集中到同一个 RDT/VLA action mode 的问题。核心做法是在 EDS initial population 阶段先生成大于最终 `population_size` 的 raw candidates，再在 trajectory/action feature space 中执行 farthest point selection，选出覆盖度更高的候选集作为后续 EDS resample、renoise、rollout 的起点。

该方案是一个 **gradient-free initial proposal diversification** 方法。它不调用 `torch.autograd.grad()`，不修改 VLS 路径，不直接扰动 action，不改变 action decoder，而是从 policy 已经完整 denoise 的候选中做多样化子集选择。

## 2. 背景与问题

当前 EDS 代码位于 `core/rdt_policy_steer.py`。`_EDSConfig` 只有 population、CEM、temperature、renoise、cache、reward mode 和 mechanism pretest 等字段，还没有 initial diversification 策略字段（`core/rdt_policy_steer.py:47-63`）。`_predict_guided()` 在 EDS 分支中根据 `resolved_eds_config.population_size` 设置 `B`，生成 `(B, 64, 128)` Gaussian latent `x_t`，再调用 `_eds_guided_denoise_loop()`（`core/rdt_policy_steer.py:1155-1208`）。

`_eds_initial_population()` 的非 cache 路径目前是：

1. `population = x_t`;
2. 通过 scheduler timesteps 完整 denoise；
3. 对结果调用 `_apply_action_mask()`；
4. 返回 `(population_size, 64, 128)` population（`core/rdt_policy_steer.py:1499-1537`）。

这等价于假设：同一个 observation/language condition 下，独立 Gaussian latent 经过 RDT/VLA denoiser 后会自然覆盖多个 action mode。但强条件化 policy 往往会把不同 latent basin 拉回同一个高概率动作模式，特别是在 OOD object position shift、support surface shift、approach direction 改变等场景中，初始候选可能只覆盖 policy 最熟悉的一条局部轨迹。

后续 `_eds_guided_denoise_loop()` 已经会先 score initial population，再执行 resample、renoise、short rollout 和 final selection（`core/rdt_policy_steer.py:1772-2072`）。问题是，如果 initial population 已经坍塌，后续 `renoise_t_max -> renoise_t_min` 的扰动只能在小邻域内搜索，CEM/MPPI 式选择也只能重复放大已有局部 mode，难以在 OOD 情况下找到替代 approach trajectory。

VLS 的对照路径 `_vls_guided_denoise_loop()` 在 early denoising phase 中调用 `_compute_diversity_gradient()`，把 RBF repulsion gradient 注入 guided translation slots（`core/rdt_policy_steer.py:1289-1368`）。但 `_compute_diversity_gradient()` 明确通过 `torch.enable_grad()` 和 `torch.autograd.grad()` 对 trajectory-space repulsion 反传到 `x_t`（`core/rdt_policy_steer.py:2188-2224`）。这不符合 EDS 的 gradient-free 约束。因此，EDS 需要把“粒子间排斥”改写成“生成后子集选择”。

## 3. 设计目标

- 保持 EDS gradient-free，不依赖 reward gradient、diversity gradient 或 trajectory gradient。
- 不改变 VLS 分支语义，不修改 `_vls_guided_denoise_loop()`。
- 不破坏 RDT full action shape，最终返回给 EDS 主循环的 population 必须是 `(population_size, 64, 128)`。
- 所有返回候选都必须经过 `_apply_action_mask()`，使 invalid action dimensions 保持为 0。
- 候选尽量留在 policy manifold 上：只从完整 denoise 的 raw candidates 中选择，不直接构造或 perturb action。
- 支持 `use_initial_cache` / `save_initial_cache`，并能记录 strategy metadata。
- 支持现有 EDS metrics 与 mechanism trace，同时扩展 raw-vs-selected diversity 观测。
- 第一版 MVP 应低风险、可回退，并能通过 config 关闭，默认行为保持当前 EDS。

## 4. 核心算法设计

令最终 EDS population size 为 `M = cfg.population_size`，oversample factor 为 `r`。FPS 初始化的 raw candidate 数量为：

```text
M_raw = ceil(r * M)
```

整体流程：

```text
Input:
  x_t:              (M, 64, 128) 当前 EDS 初始 Gaussian latent
  cond:             RDT conditioning dict, 包含 action_mask
  cfg.population_size = M
  cfg.initial_oversample_factor = r

1. 如果 cfg.use_initial_cache=true:
     保持现有 cache 读取路径，读取 selected population。

2. 如果 cfg.initial_diversity_mode="none":
     保持现有 EDS 行为：对 x_t 完整 denoise，mask，返回。

3. 如果 cfg.initial_diversity_mode="fps_oversample":
     3.1 生成 raw latent:
         x_raw = randn(M_raw, 64, 128)
         其中 M_raw >= M。

     3.2 使用当前 RDT denoising loop 完整 denoise:
         raw_candidates = full_denoise(x_raw, cond)

     3.3 应用 action mask:
         raw_candidates = _apply_action_mask(raw_candidates, cond)

     3.4 构造 diversity features:
         features = _eds_build_initial_diversity_features(raw_candidates)

     3.5 执行 validity / smoothness filtering:
         valid_indices = _eds_filter_initial_candidates(raw_candidates, features)

     3.6 执行 FPS / k-center selection:
         selected_indices = _eds_farthest_point_select(features[valid_indices], k=M)

     3.7 如果 valid candidates 不足 M:
         使用 fallback 策略从 raw candidates 或原始 baseline candidates 补齐。

     3.8 返回:
         population = raw_candidates[selected_indices]
         population = _apply_action_mask(population, cond)
```

设计重点是：`_eds_guided_denoise_loop()` 在 `population = self._eds_initial_population(...)` 之后仍然只看到 `(M,64,128)` population（`core/rdt_policy_steer.py:1772-1785`）。因此，后续 scoring、resample、renoise、rollout、final selection 无需改变。

## 5. Diversity Feature 与距离度量

### 5.1 normalized action feature

normalized action feature 直接从 raw RDT sample 中提取 active / guided action channels。当前 guidance action slots 是：

```python
RDT_GUIDED_ACTION_INDICES = [39, 40, 41, 42, 43, 44, 10]
```

`_decode_rdt_actions_for_guidance()` 会校验输入 shape 为 `(B,64,128)`，并取前 `H = self._action_chunk_horizon` 个 step 的这些 action indices（`core/rdt_policy_steer.py:2143-2148`）。

优点：

- 不依赖 adapter 或 env rollout；
- 与 RDT normalized action space 一致；
- 实现最简单，速度快。

缺点：

- normalized action distance 不一定对应真实 EE trajectory distance；
- rotation/gripper channel 可能支配距离；
- 对 OOD spatial shift 的意义弱于 EE trajectory feature。

### 5.2 decoded EE trajectory feature

`_rdt_sample_to_trajectory_3d()` 会先调用 `_decode_rdt_actions_for_guidance()`，再通过 adapter 的 `delta_actions_to_ee_trajectory()` 把 action chunk 转成 `(B, H+1, 3)` EE trajectory（`core/rdt_policy_steer.py:2149-2165`）。

推荐默认使用 EDS reward 对齐的 trajectory slice：

```text
trajs = _rdt_sample_to_trajectory_3d(raw_candidates)
feature_traj = _trajectory_reward_slice(trajs, "eds")
```

当前 `"eds"` slice 是 `trajs[:, 1:self._action_chunk_horizon, :3]`（`core/rdt_policy_steer.py:1227-1236`），与 `_eds_score_population_as_cost()` 经过 `_score_particles(..., slice_kind="eds")` 的评分路径一致（`core/rdt_policy_steer.py:1412-1452`）。

优点：

- 更接近实际末端执行器运动；
- 对 OOD spatial shift、target object displacement、approach direction 改变更有意义；
- 与现有 reward scoring 和 mechanism trace 的 trajectory 表示一致。

缺点：

- 依赖 adapter；
- 只是 delta action 到 EE path 的近似，不等于 controller、IK、collision 后的真实执行轨迹。

### 5.3 endpoint / final waypoint feature

只用整条 trajectory 的平均距离可能低估 final approach 的差异。建议将 final waypoint 单独加权：

```text
d_final(i, j) = ||x_i[-1] - x_j[-1]||_2^2
```

对 OOD object position shift 来说，final waypoint spread 往往比全轨迹平均距离更直接。

### 5.4 gripper feature

gripper 不建议强行多样化。若 `w_grip` 太高，FPS 可能只是在 open/close timing 上分散，而非 spatial trajectory 上分散。第一版建议：

- 默认 `w_grip=0.0` 或很小；
- 只把 gripper 用作 validity/sanity check；
- 如果后续发现 grasp timing 是主要失败源，再独立做 gripper-aware grouping。

### 5.5 推荐默认 hybrid metric

推荐默认距离：

```text
d(i, j) =
  w_ee    * ||flatten(ee_traj_i) - flatten(ee_traj_j)||_2^2
+ w_final * ||endpoint_i - endpoint_j||_2^2
+ w_act   * ||flatten(action_i) - flatten(action_j)||_2^2
+ w_grip  * d_grip(i, j)
```

第一版默认建议：

```yaml
initial_distance_metric: hybrid
initial_feature_weights:
  ee: 1.0
  final: 2.0
  action: 0.1
  gripper: 0.0
```

默认更偏向 EE trajectory 和 endpoint，因为本方案目标是提升 OOD spatial coverage，而不是制造 rotation/gripper 的表面差异。

## 6. 代码插入点设计

### 6.1 `_eds_initial_population()` 改造

推荐把所有 FPS 初始化逻辑封装在 `_eds_initial_population()` 的非 cache 分支中。该函数当前已经是 initial population 的唯一入口，并且负责 cache 读取、完整 denoise、mask 和返回 population（`core/rdt_policy_steer.py:1499-1537`）。

改造后的结构：

```text
_eds_initial_population(x_t, cond, cfg):
  if cfg.use_initial_cache:
      return cached selected population

  if cfg.initial_diversity_mode == "none":
      return current full-denoise baseline

  if cfg.initial_diversity_mode == "fps_oversample":
      raw_candidates, raw_info = _eds_generate_raw_initial_candidates(...)
      features, feature_info = _eds_build_initial_diversity_features(...)
      valid_indices, filter_info = _eds_filter_initial_candidates(...)
      selected_indices, fps_info = _eds_farthest_point_select(...)
      population = raw_candidates[selected_indices]
      return _apply_action_mask(population, cond)
```

这样 `_eds_guided_denoise_loop()` 的主流程无需知道 oversampling 细节。它仍然在初始化后调用 `_eds_score_population_as_cost()`，并继续记录 `initial_best_reward`、`initial_mean_reward`、`population_diversity_initial` 和 `target_distance_before`（`core/rdt_policy_steer.py:1775-1806`）。

### 6.2 新增 helper 建议

#### `_eds_generate_raw_initial_candidates`

输入：

```text
x_t:  (M, 64, 128)
cond: dict
cfg:  _EDSConfig
```

输出：

```text
raw_candidates: (M_raw, 64, 128)
raw_info: dict
```

职责：

- 根据 `cfg.initial_oversample_factor` 生成 `M_raw` 个 latent；
- 复用当前 `_eds_initial_population()` 的完整 denoise 逻辑；
- denoise 后调用 `_apply_action_mask()`；
- 记录 raw candidate count、raw shape、denoise latency。

第一版可以忽略传入的 `x_t` 内容，仅复用它的 device、dtype、horizon 和 action dim。若 `initial_oversample_factor=1`，该 helper 应退化为当前行为。

#### `_eds_build_initial_diversity_features`

输入：

```text
raw_candidates: (M_raw, 64, 128)
cond: dict
cfg: _EDSConfig
```

输出：

```text
features: (M_raw, D_feature)
feature_info: dict
```

职责：

- 使用 `_decode_rdt_actions_for_guidance()` 构造 action feature；
- 使用 `_rdt_sample_to_trajectory_3d()` 和 `_trajectory_reward_slice(..., "eds")` 构造 EE trajectory feature；
- 构造 endpoint feature；
- 按 `initial_feature_weights` 拼接或加权归一化 features。

若 adapter 不存在，fallback 到 action-only feature，而不是失败。

#### `_eds_filter_initial_candidates`

输入：

```text
raw_candidates: (M_raw, 64, 128)
features: (M_raw, D_feature)
cond: dict
cfg: _EDSConfig
```

输出：

```text
valid_indices: (M_valid,)
filter_info: dict
```

职责：

- 过滤非有限值；
- 检查 `_eds_action_mask_violation()`；
- 可选检查 decoded action/trajectory 的 finite；
- 可选检查 trajectory jump、endpoint workspace bounds、action norm outlier。

第一版 validity filter 应保守，只过滤显然 invalid 的候选，避免候选不足。

#### `_eds_farthest_point_select`

输入：

```text
features: (M_valid, D_feature)
k: int = cfg.population_size
cfg: _EDSConfig
optional_costs: Tensor | None
```

输出：

```text
selected_local_indices: (k,)
fps_info: dict
```

职责：

- 维护每个候选到已选集合的 nearest distance；
- 每轮选择 nearest distance 最大的候选；
- 支持不同 first seed 策略：
  - `medoid`: 选择离其他点平均距离最小的候选；
  - `random`: 使用 seed 随机选择；
  - `reward_best`: 如果已经传入 costs，则选 reward 最高候选；
  - `smoothest`: 选择 temporal jump 最小候选。

第一版 MVP 推荐 `medoid`，因为它不依赖 reward，且比 random 稳定。

### 6.3 与 `_eds_guided_denoise_loop()` 的关系

`_eds_guided_denoise_loop()` 不需要理解 raw candidate set。它只接收最终 selected population，并保持现有流程：

- initial score；
- score validation；
- metrics；
- mechanism trace；
- resample；
- renoise；
- rollout；
- final selection。

这保证 FPS 方案是 initial population plugin，而不是新的 EDS 主循环。

## 7. 新增配置字段建议

建议扩展 `_EDSConfig` 和 `_resolve_eds_config_with_reference_defaults()`（`core/rdt_policy_steer.py:2305-2348`）：

| 字段 | 默认值 | 含义 | 推荐范围 |
|---|---:|---|---|
| `initial_diversity_mode` | `"none"` | 初始化多样化策略。`none` 保持当前 EDS；`fps_oversample` 启用本方案。 | `none`, `fps_oversample` |
| `initial_oversample_factor` | `1` | raw candidate 数量倍率，`M_raw = factor * population_size`。 | MVP: 2 或 4 |
| `initial_distance_metric` | `"hybrid"` | FPS 使用的距离特征。 | `action`, `ee`, `endpoint`, `hybrid` |
| `initial_fps_seed` | `"medoid"` | FPS 第一个 seed 的选择方式。 | `medoid`, `random`, `reward_best`, `smoothest` |
| `initial_feature_weights` | `{"ee":1.0,"final":2.0,"action":0.1,"gripper":0.0}` | hybrid metric 的各 feature 权重。 | 非负 float |
| `initial_validity_filter` | `"finite_only"` | validity filter 严格程度。 | `none`, `finite_only`, `basic_smoothness`, `workspace` |
| `initial_min_valid_ratio` | `0.5` | valid candidates 少于该比例时触发 warning/fallback。 | 0.25-0.8 |
| `initial_cache_metadata` | `True` | cache 是否保存 diversity strategy metadata。 | bool |
| `initial_fallback_mode` | `"fill_from_raw"` | valid/selected 不足时如何补齐。 | `fill_from_raw`, `baseline_resample`, `disable_filter` |
| `initial_metrics_enabled` | `True` | 是否记录 raw-vs-selected 初始化指标。 | bool |

校验规则：

- `initial_oversample_factor >= 1`；
- `initial_diversity_mode="none"` 时允许所有新字段存在但不生效；
- `initial_diversity_mode="fps_oversample"` 时 `M_raw >= population_size`；
- feature weights 必须有限且非负；
- 若所有 feature weights 为 0，应报错或 fallback 到 `ee=1.0`。

## 8. Cache 与兼容性

### 8.1 `use_initial_cache`

当前 cache 读取逻辑要求 cached tensor shape 等于 `(population_size, x_t.shape[1], x_t.shape[2])`，并在读取后重新应用 action mask（`core/rdt_policy_steer.py:1500-1521`）。FPS 方案应保持这一行为：cache 中保存的是 **selected population**，不是 raw oversampled candidates。

好处：

- 后续 EDS 行为完全可复现；
- cache 文件大小不随 oversample factor 增长；
- 现有 `_eds_guided_denoise_loop()` 不需要知道 raw candidates。

### 8.2 `save_initial_cache`

保存时建议从当前 `{ "initial_population": tensor }` 扩展为：

```python
{
  "initial_population": selected_population_cpu,
  "metadata": {
    "initial_diversity_mode": "fps_oversample",
    "initial_oversample_factor": 4,
    "initial_distance_metric": "hybrid",
    "initial_fps_seed": "medoid",
    "raw_candidate_count": 128,
    "selected_candidate_count": 32,
    "selected_indices": [...],
    "config_hash": "..."
  }
}
```

为了兼容旧 cache，读取时仍支持旧格式：如果是 dict 且包含 `"initial_population"`，继续取该字段；如果是裸 tensor，也继续兼容。

### 8.3 strategy mismatch

当 `use_initial_cache=true` 且 metadata 中的 strategy 与当前 config 不一致时，建议第一版使用 strict warning 而非 silent ignore：

- `initial_cache_metadata=True` 且 metadata 存在：若 mismatch，报错或 warning 后拒绝使用，推荐报错；
- metadata 不存在：允许读取旧 cache，但记录 warning；
- `initial_diversity_mode="none"` 读取 FPS cache 时，如果 shape 正确，仍可使用，但 warning 提醒该 cache 不是 baseline EDS。

### 8.4 与 VLS 兼容

FPS 方案只扩展 `_EDSConfig` 和 `_eds_initial_population()`。VLS 配置解析 `_resolve_vls_config()`、`_vls_guided_denoise_loop()` 和 `_compute_diversity_gradient()` 不应修改。这样可以维持 `guidance_type="vls"` 的行为兼容。

## 9. Metrics 与可视化

当前 `EDSChunkMetrics` 已记录：

- `population_size_observed`；
- `population_shape`；
- `score_shape`；
- `initial_best_reward`；
- `initial_mean_reward`；
- `population_diversity_initial`；
- `target_distance_before`；
- `action_mask_violation_max`；
- `eds_loop_latency_s`；
- per-iteration `score_entropy`、`unique_parent_ratio`、`population_diversity`（`core/eds_eval_metrics.py:11-63`）。

这些字段可直接用于比较 FPS 前后的 selected population 效果，但不足以说明 raw oversampled candidates 到 selected population 的提升。因此建议新增初始化专用 metrics：

| 字段 | 含义 |
|---|---|
| `initial_diversity_mode` | 使用的初始化策略 |
| `initial_raw_candidate_count` | raw candidates 数量 |
| `initial_selected_candidate_count` | FPS 后 selected 数量 |
| `initial_valid_candidate_count` | validity filter 后数量 |
| `initial_invalid_candidate_count` | 被过滤数量 |
| `initial_raw_diversity_action` | raw action feature 平均 pairwise distance |
| `initial_selected_diversity_action` | selected action feature 平均 pairwise distance |
| `initial_raw_diversity_ee` | raw EE trajectory 平均 pairwise distance |
| `initial_selected_diversity_ee` | selected EE trajectory 平均 pairwise distance |
| `initial_endpoint_spread_raw` | raw endpoint spread |
| `initial_endpoint_spread_selected` | selected endpoint spread |
| `initial_pairwise_min_selected` | selected set 的最小 pairwise distance |
| `initial_fps_selected_indices` | selected raw candidate indices |
| `initial_filter_fallback_used` | 是否触发 fallback |

`EDSMechanismTrace` 当前每个 stage 记录 `actions`、`trajectories`、`rewards`、`costs`、parent 信息、renoise/rollout delta 等（`core/eds_mechanism_trace.py:13-42`），保存时会输出 metadata、CSV 和可选 tensor payload（`core/eds_mechanism_trace.py:80-150`）。

建议 mechanism trace 增加两个初始化 stage：

```text
stage="initial_raw"
  actions: raw_candidates
  trajectories: raw candidate trajectories
  rewards/costs: optional, 可先全 0 或只在需要时 score

stage="initial_selected"
  actions: selected population
  trajectories: selected trajectories
  rewards/costs: selected scoring result
```

若担心 tensor 文件过大，可通过 `mechanism_pretest` 配置只在 first chunk 或小样本 pretest 中保存 raw stage。

## 10. 计算成本

设最终 population 为 `M`，oversample factor 为 `r`：

- 完整 denoise 成本约为当前初始化的 `r` 倍；
- raw candidates 数量为 `M_raw = r * M`；
- pairwise distance 复杂度约为 `O((rM)^2 * D_feature)`；
- FPS 如果维护 nearest distance，复杂度约为 `O(M * rM)` 次 feature distance 更新；
- 不需要额外 VLM 调用；
- 不需要 autograd；
- 不增加后续 EDS resample/renoise/rollout 每轮成本。

推荐第一组实验：

```yaml
main:
  eds_config:
    population_size: 32
    initial_diversity_mode: fps_oversample
    initial_oversample_factor: 2
    initial_distance_metric: hybrid
    initial_fps_seed: medoid
```

若 `oversample_factor=2` 对 diversity 提升不明显，再试 `4`。不建议第一版直接使用 `8`，因为 initial denoise latency 会明显上升，且 OOD rollout 调参会变慢。

## 11. 风险与失败模式

### raw candidates 本身完全坍塌

如果 `M_raw` 内的候选几乎完全相同，FPS 只能选择微小差异，不能创造新 mode。此时 metrics 会表现为 `initial_raw_diversity_ee` 和 `initial_selected_diversity_ee` 都很低。后续应考虑 diffusion restart / mixture-of-noise-level branching，而不是继续增加 FPS 复杂度。

### FPS 选到 outlier

最远点可能是异常动作或 denoising failure。必须保留 finite check、mask violation check、trajectory jump check 等 validity filter。第一版 seed 使用 medoid，可以降低 outlier 先进入 selected set 的概率。

### gripper channel 干扰 spatial diversity

如果 gripper 权重过高，FPS 可能选择 open/close timing 差异，而不是 spatial trajectory 差异。第一版建议 `w_grip=0.0`。

### oversample latency 过高

`r=4` 会让 initial denoise 成本约增加到 4 倍。需要通过 `eds_loop_latency_s` 和新增 initial latency metrics 监控。

### trajectory approximation 与真实 controller 执行不一致

`_rdt_sample_to_trajectory_3d()` 依赖 adapter 的 delta action to EE trajectory approximation。它更适合做 candidate feature 和 reward proxy，不代表真实 collision-free rollout。因此 final evaluation 必须看真实 LIBERO rollout 成功率。

### validity filter 过严导致候选不足

如果 filter 过严，可能不足 `population_size`。fallback 不能失败退出，除非所有 raw candidates 都 invalid。推荐 fallback 顺序：

1. 从未选 raw candidates 按 medoid/finite 补齐；
2. 放宽 smoothness/workspace filter；
3. 最后退回 baseline initial population。

## 12. 实验验证计划

### 12.1 unit tests

目标：证明 FPS 初始化不会破坏基本接口。

建议测试：

- `initial_diversity_mode="none"` 时行为保持当前 baseline。
- `fps_oversample` 返回 shape 为 `(population_size, 64, 128)`。
- 返回 tensor finite。
- `_eds_action_mask_violation(population, cond) == 0`。
- `use_initial_cache=true` 可读取旧 tensor cache 和新 metadata cache。
- `save_initial_cache=true` 保存 selected population，而不是 raw candidates。
- `initial_oversample_factor=1` 时可退化到 baseline 或 FPS over same-size set。

成功判据：所有 CPU/mock tests 通过，不需要真实 RDT checkpoint。

### 12.2 mechanism pretest

目标：证明 FPS 真的提升 initial diversity。

比较：

- baseline EDS initial population；
- FPS raw candidates；
- FPS selected population。

关键指标：

- selected EE pairwise mean distance > baseline；
- selected endpoint spread > baseline；
- selected min pairwise distance 不低于 baseline；
- invalid candidate count 合理；
- action mask violation 仍为 0；
- initial best reward 不显著低于 baseline。

建议先在 1 个 LIBERO Object OOD task、1 个 seed、first chunk 上保存 mechanism trace。

### 12.3 small OOD smoke

目标：验证不会明显伤害 rollout。

配置：

```text
population_size=32
oversample_factor=2
cem_iters 保持 baseline
episode_num=3-5
```

成功判据：

- 不出现 runtime error；
- mean select latency 可接受；
- success count 不低于 baseline small smoke；
- 失败视频中不出现明显 gripper/rotation 异常。

### 12.4 full OOD eval

目标：与 baseline EDS 做正式对比。

对照：

- unguided RDT；
- current EDS baseline；
- EDS + FPS r=2；
- EDS + FPS r=4；
- 可选 VLS baseline。

固定：

- task ids；
- seed；
- episode count；
- reward mode；
- CEM/temperature/renoise schedule；
- VLM guidance generation cache。

成功判据：

- OOD success rate 高于 current EDS baseline；
- initial selected diversity 明显高于 baseline；
- final best reward 或 target distance after 不劣于 baseline；
- latency 增长在可接受范围内。

## 13. MVP 实施范围

### 最小代码改动列表

1. 扩展 `_EDSConfig`：
   - `initial_diversity_mode`;
   - `initial_oversample_factor`;
   - `initial_distance_metric`;
   - `initial_fps_seed`;
   - `initial_feature_weights`;
   - `initial_validity_filter`;
   - `initial_min_valid_ratio`;
   - `initial_cache_metadata`;
   - `initial_fallback_mode`;
   - `initial_metrics_enabled`。

2. 扩展 `_resolve_eds_config_with_reference_defaults()`：
   - 解析新字段；
   - 校验 factor、weights、mode。

3. 改造 `_eds_initial_population()` 的非 cache 分支：
   - `none` 维持现有完整 denoise；
   - `fps_oversample` 走 raw generate + feature + filter + FPS + selected return。

4. 新增 helper：
   - `_eds_generate_raw_initial_candidates`;
   - `_eds_build_initial_diversity_features`;
   - `_eds_filter_initial_candidates`;
   - `_eds_farthest_point_select`;
   - `_eds_pairwise_feature_stats`;
   - `_eds_initial_cache_metadata`。

5. 扩展 metrics：
   - `EDSChunkMetrics` 增加 initial raw/selected diversity 字段；
   - `_last_eds_artifacts` 增加 raw/selected FPS 信息；
   - mechanism trace 可选记录 `initial_raw` 和 `initial_selected`。

### 第一版不做的事情

- 不修改 VLS `_vls_guided_denoise_loop()`。
- 不调用 `_compute_diversity_gradient()`。
- 不直接 perturb action。
- 不修改 decoder 或 LIBERO action converter。
- 不在第一版做 DPP exact sampling；FPS/k-center 贪心即可。
- 不把 reward-novelty quality-diversity 合进 MVP；可以作为下一阶段。

### 推荐第一版默认配置

为了安全落地，默认保持 baseline 行为：

```yaml
main:
  eds_config:
    initial_diversity_mode: none
    initial_oversample_factor: 1
```

实验配置使用：

```yaml
main:
  eds_config:
    initial_diversity_mode: fps_oversample
    initial_oversample_factor: 2
    initial_distance_metric: hybrid
    initial_fps_seed: medoid
    initial_feature_weights:
      ee: 1.0
      final: 2.0
      action: 0.1
      gripper: 0.0
    initial_validity_filter: finite_only
    initial_min_valid_ratio: 0.5
    initial_fallback_mode: fill_from_raw
```

若 mechanism pretest 证明 selected diversity 提升但 OOD success 没有提升，再尝试：

- `initial_oversample_factor: 4`;
- 更高 `final` 权重；
- reward-novelty quality-diversity；
- diffusion restart / branch 初始化。

## 14. 结论

Policy-Manifold Oversampling + Trajectory-Space FPS Filtering 是当前 EDS initial proposal 多样化的最低风险第一版方案。它把 VLS 中“粒子间互动提升多样性”的思想改写为 EDS 可接受的 gradient-free subset selection：先让 policy 在自己的 manifold 上产生更多候选，再用 trajectory-space FPS 选出覆盖度更高的一组。

该方案的主要优点是局部、可回退、易观测：只改 initial population，不改变后续 EDS 主循环；默认可保持 baseline；metrics 可以直接验证 raw diversity、selected diversity 与 OOD success 的关系。它不能凭空创造 policy prior 中完全不存在的 action mode，但作为第一版 OOD EDS 探索增强，是最合适的 MVP。
