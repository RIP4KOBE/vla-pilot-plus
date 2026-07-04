# RBF-Diverse Initial Denoising Sampling + Unchanged EDS 设计

## 1. 标题与摘要

方案名称：**RBF-diverse initial denoising sampling + unchanged EDS**。

本方案解决当前 EDS 初始动作候选由 iid Gaussian latent 完整 denoise 得到后容易坍塌到单一 RDT/VLA action mode 的问题。核心做法是在 initial population generation 阶段复用 VLS 风格的 RBF diversity guidance，让初始 denoising particles 在早期去噪阶段主动分散；完成 initial population 后，后续 EDS score、resample、renoise、rollout、iterative refinement 和 final best-particle selection 全部保持不变。

本方案的算法边界是：

- initial sampler 阶段允许使用 gradient；
- initial population 生成完成后，EDS refinement 主循环保持 gradient-free；
- 不改变 EPS-CoT / VLM reward；
- 不改变 Evolutionary Diffusion 的 refinement 逻辑；
- 不改变 VLS 路径。

配置层面只使用 `initial_sampling_mode` 区分不同 initial sampling 机制。`initial_sampling_mode="iid"` 表示当前 baseline；`initial_sampling_mode="rbf_diverse_denoise"` 表示启用本方案。不要再额外引入 `initial_diversity_enabled` 或 `initial_diversity_allow_grad`，避免配置冗余和状态不一致。

## 2. 背景与问题

当前 EDS 实现在 `core/rdt_policy_steer.py`。`_EDSConfig` 目前只包含 population、CEM、temperature、renoise、cache、reward mode 和 mechanism pretest 等字段，尚无 initial sampling strategy 字段（`core/rdt_policy_steer.py:47-63`）。`_predict_guided()` 在 `guidance_type="eds"` 时根据 `resolved_eds_config.population_size` 设置 batch size `B`，生成 `(B, 64, 128)` Gaussian latent `x_t`，然后进入 `_eds_guided_denoise_loop()`（`core/rdt_policy_steer.py:1155-1208`）。

`_eds_initial_population()` 的非 cache 路径当前是标准 iid denoising：

1. 将 `population = x_t`；
2. 在 `torch.no_grad()` 下完整遍历 scheduler timesteps；
3. 每步调用 `self._dit(population, t, cond)` 和 `scheduler.step(...)`；
4. 完成后调用 `_apply_action_mask()`；
5. 返回 `(population_size, 64, 128)` population（`core/rdt_policy_steer.py:1499-1537`）。

这个流程隐含假设：同一 observation/language condition 下，独立 Gaussian latent 会在完整 denoise 后自然覆盖多个行为模式。但强条件化 VLA/RDT policy 往往会把不同 latent basin 吸回同一个高概率 action mode。OOD object position shift、support surface shift、approach direction 改变或复杂双臂协作任务中，最可能需要的替代动作模式可能不在 iid initial population 覆盖范围内。

后续 `_eds_guided_denoise_loop()` 已经会对 initial population 评分，并执行 resample、renoise、short rollout、per-iteration metrics 和 final argmin cost selection（`core/rdt_policy_steer.py:1772-2072`）。如果 initial population 一开始坍塌，后续 EDS 的 evolutionary refinement 只是在狭窄局部邻域中重复采样，`renoise_t_max -> renoise_t_min` 的扰动不足以跨越行为模式边界。

VLS 的 `_vls_guided_denoise_loop()` 已经包含 RBF diversity phase：在 early denoising timesteps 中，当 `use_diversity` 为真且 `t > start_step` 时调用 `_compute_diversity_gradient(x_t)`，并将 masked diversity gradient 写回 RDT guided translation slots `[39,40,41]`（`core/rdt_policy_steer.py:1289-1368`）。该机制说明粒子间 repulsion 可以在去噪过程中提升 sampling coverage。本方案将这个机制作为 EDS initial sampler 的第一版实现参考，目标是最大化 glue coding 和接口复用。

## 3. 设计目标

本设计只改变 initial population generation，不改变 EDS refinement 语义：

- 只通过 `initial_sampling_mode` 切换 initial sampler；
- `initial_sampling_mode="iid"` 默认保持当前 EDS baseline；
- `initial_sampling_mode="rbf_diverse_denoise"` 启用 RBF-diverse initial denoising；
- initial sampler 允许 gradient，用于 RBF diversity-guided denoising；
- EDS refinement 主循环保持 gradient-free；
- 不改变 EPS-CoT / VLM reward；
- 不改变 `_eds_score_population_as_cost()` 的 reward/cost 定义；
- 不改变 EDS resample、renoise、rollout、iterative refinement 和 final selection；
- 不改变 VLS 路径和 `_vls_guided_denoise_loop()` 现有行为；
- 不破坏 RDT 128D action shape；
- initial sampler 最终必须返回 `(population_size, 64, 128)`；
- 所有候选必须经过 `_apply_action_mask()`，保证 invalid action dimensions 不参与后续 EDS；
- 支持 `use_initial_cache`、`save_initial_cache`、metrics 和 mechanism trace；
- 第一版尽量复用现有 VLS diversity 相关接口，避免重复造轮子和自由发明新的 diversity 算法。

若实现时发现必须偏离 VLS 已有行为或参数设置，例如调整 diversity sign、改变 trajectory slice、改写 gradient normalization、改写 scheduler step 位置、写回非 translation slots，必须在实现前给出技术理由并请求 approval。

## 4. 核心算法设计

推荐 initial sampler 流程：

```text
x_t raw particles
  -> early denoising with VLS-style RBF diversity guidance
  -> late normal denoising without diversity
  -> action mask
  -> validated initial population
  -> unchanged EDS score / resample / renoise / rollout / final selection
```

### 4.1 baseline path

当 `initial_sampling_mode="iid"` 时，`_eds_initial_population()` 保持当前逻辑：在 `torch.no_grad()` 下完整 denoise，mask 后返回。该路径用于 baseline、cache 兼容和 fallback。

### 4.2 RBF-diverse denoising path

当 `initial_sampling_mode="rbf_diverse_denoise"` 时，`_eds_initial_population()` 进入 RBF-diverse initial sampler。第一版应尽量复制 VLS diversity phase 的控制结构：

```text
population = x_t
scheduler.set_timesteps(num_inference_steps)
start_step = resolve_start_step_like_vls(scheduler.timesteps, initial_diversity_start_ratio)

for i, t in enumerate(scheduler.timesteps):
    with torch.no_grad():
        model_output = self._dit(population, t, cond)

    if int(t.item()) > start_step and population.shape[0] > 1:
        div_grad = self._compute_diversity_gradient(population)
        if div_grad is not None and finite:
            masked_div = self._mask_guidance_gradient(div_grad).to(model_output)
            model_output[:, :, RDT_GUIDED_TRANSLATION_INDICES] += (
                RDT_DIVERSITY_SIGN
                * cfg.initial_diversity_scale
                * masked_div[:, :, RDT_GUIDED_TRANSLATION_INDICES]
            )
        else:
            log.warning(...)
            return _eds_initial_denoise_iid(x_t, cond, cfg)

    population = scheduler.step(model_output, t, population).prev_sample

population = _apply_action_mask(population, cond)
_eds_initial_validate_population(population, cond, cfg)
return population
```

这里的重点不是重新设计一个新的 sampler，而是把 VLS 已有 early diversity denoising glue 到 EDS initial population 生成路径中。后续 `_eds_guided_denoise_loop()` 看到的仍是标准 `(population_size, 64, 128)` population，因此后续 EDS refinement 不需要改动。

### 4.3 diversity phase

第一版应参考 VLS 的 `start_step` 机制。VLS 当前通过 `_resolve_start_step()` 得到 scheduler timestep threshold，然后在 `int(t.item()) > start_step` 时启用 diversity，在 `int(t.item()) <= start_step` 时进入 keypoint guidance / FKD phase（`core/rdt_policy_steer.py:1313-1369`）。EDS initial sampler 只需要前半段 diversity phase，不需要 keypoint guidance 和 FKD。

推荐配置：

```yaml
initial_sampling_mode: rbf_diverse_denoise
initial_diversity_scale: 1.0
initial_diversity_start_ratio: null
```

`initial_diversity_start_ratio` 默认 `null` 时，直接复用 `_resolve_start_step()` 的默认行为，即 `timesteps[len(timesteps)//3]`（`core/rdt_policy_steer.py:2300` 附近）。如果后续要把 scheduler timestep threshold 改成 loop-index ratio，需要单独说明理由并请求 approval，因为这会偏离 VLS 当前语义。

### 4.4 RBF distance space

RBF distance space 与 VLS 保持一致：**3D EEF trajectories**。不设计 action-space 或 hybrid-space 变体。

当前 `_compute_diversity_gradient()` 已经实现了这一路径：它通过 `_rdt_sample_to_trajectory_3d()` 将 `(B,64,128)` sample 映射到 `(B,H+1,3)` trajectory，并用 `trajs[:,1:,:3]` 的 flattened distance 构造 inverse-distance potential（`core/rdt_policy_steer.py:2188-2224`）。trajectory projection 依赖 `_decode_rdt_actions_for_guidance()` 从 slots `[39,40,41,42,43,44,10]` 中取动作片段（`core/rdt_policy_steer.py:2143-2148`），再由 adapter 做 delta action 到 EE trajectory 转换（`core/rdt_policy_steer.py:2149-2165`）。

第一版直接复用这个 3D EEF trajectory RBF，不额外设计 `initial_diversity_metric`。如果实现中认为必须修改 trajectory slice 或 RBF potential 形式，需要先写出理由并请求 approval。

### 4.5 写回 slots 与污染控制

RBF diversity gradient 只允许写回 translation slots `[39,40,41]`。当前代码已有 `RDT_GUIDED_TRANSLATION_INDICES = [39, 40, 41]`（`core/rdt_policy_steer.py:41`）和 `_mask_guidance_gradient()`，后者只保留 action horizon 内 translation slots 的 gradient（`core/rdt_policy_steer.py:2169-2174`）。MVP 应复用这一 mask 逻辑，避免 rotation 和 gripper 被 diversity 直接污染。

### 4.6 fallback

如果 RBF-diverse path 出现 fallback，允许回到 iid baseline，但必须输出 warning，不允许静默 fallback。

触发 fallback 的情况包括：

- `population_size <= 1`；
- adapter 不存在；
- diversity gradient 返回 `None`；
- gradient 或 model output 出现 nonfinite；
- action mask violation 非 0；
- scheduler step 后 population 出现 nonfinite。

warning 至少应包含：

- `initial_sampling_mode=rbf_diverse_denoise`；
- fallback reason；
- current timestep / step index；
- population shape；
- 是否已生成 partial population；
- 后续使用 iid baseline。

默认 fallback 行为为 `iid`。不设计 `skip_step` 或 `raise` 作为 MVP 配置项，以免把第一版配置空间做得过宽。

## 5. 与 VLS RBF Diversity 的关系

VLS 当前 diversity phase 嵌在 `_vls_guided_denoise_loop()` 内，与 keypoint reward guidance、FKD resampling、final particle selection 同处一个 guided denoise loop（`core/rdt_policy_steer.py:1289-1400`）。EDS 当前是独立分支：`_predict_guided()` 根据 `guidance_type` 分发到 `_vls_guided_denoise_loop()` 或 `_eds_guided_denoise_loop()`（`core/rdt_policy_steer.py:1185-1206`）。

本方案不把 VLS loop 整体搬入 EDS，原因有三点：

1. VLS loop 包含 keypoint reward gradient 和 FKD，这会改变 EDS refinement 语义；
2. EDS 需要的是更分散的 initial population，而不是在整个 denoise loop 内持续做 VLS-style reward steering；
3. 保留 EDS score/resample/renoise/rollout 不变，才能隔离评估 initial sampler 对 OOD 成功率的贡献。

第一版原则是最大化复用：

- 复用 `_compute_diversity_gradient()`；
- 复用 `_mask_guidance_gradient()`；
- 复用 `RDT_DIVERSITY_SIGN`；
- 复用 `RDT_GUIDED_TRANSLATION_INDICES`；
- 复用 `_resolve_start_step()` 的默认 threshold 语义；
- 复用 `_rdt_sample_to_trajectory_3d()` 和 `_decode_rdt_actions_for_guidance()` 的 3D EEF trajectory projection。

可以新增薄 wrapper，例如 `_eds_initial_denoise_rbf_diverse()`，但 wrapper 只做 glue：调度 scheduler、调用现有 diversity helper、记录 metrics、处理 fallback 和 cache metadata。不要在 wrapper 中重新设计 RBF potential、distance space、slot mapping 或 denoising semantics。

## 6. 代码插入点设计

### 6.1 `_EDSConfig`

在 `_EDSConfig` 增加 initial sampling 相关配置。默认必须保持 baseline：

```python
initial_sampling_mode: str = "iid"
initial_diversity_scale: float = 1.0
initial_diversity_start_ratio: Optional[float] = None
initial_diversity_fallback: str = "iid"
initial_cache_metadata: bool = True
```

不增加 `initial_diversity_enabled`。是否启用由 `initial_sampling_mode` 唯一决定。不增加 `initial_diversity_allow_grad`。`rbf_diverse_denoise` 这一模式本身已经表达 initial sampler 使用 gradient 的事实。

### 6.2 `_resolve_eds_config_with_reference_defaults()`

在配置解析中读取新字段并校验（`core/rdt_policy_steer.py:2305-2348`）。关键校验：

- `initial_sampling_mode` 必须属于 `{"iid", "rbf_diverse_denoise"}`；
- `initial_diversity_scale` 必须 finite；
- `initial_diversity_start_ratio` 为 `None` 或 `[0,1]` 内 float；
- `initial_diversity_fallback` MVP 只允许 `"iid"`；
- 不暴露 slots、metric、allow_grad、enabled 等冗余字段。

### 6.3 `_eds_initial_population()`

这是主要插入点。当前函数已经负责 cache、full denoise、mask 和返回 initial population（`core/rdt_policy_steer.py:1499-1537`）。建议改为模式分发：

```text
_eds_initial_population(x_t, cond, cfg):
  if cfg.use_initial_cache:
      return cached population

  if cfg.initial_sampling_mode == "iid":
      population, info = _eds_initial_denoise_iid(x_t, cond, cfg)
  elif cfg.initial_sampling_mode == "rbf_diverse_denoise":
      population, info = _eds_initial_denoise_rbf_diverse(x_t, cond, cfg)

  population = _apply_action_mask(population, cond)
  _eds_initial_validate_population(population, cond, cfg)
  maybe save cache payload
  stash info for metrics / trace
  return population
```

### 6.4 helper 设计

#### `_eds_initial_denoise_iid`

- 输入 shape：`x_t: (B,64,128)`；
- 输出 shape：`population: (B,64,128)`；
- 是否使用 autograd：否；
- 是否影响 VLS：否；
- fallback：无，是其他路径的 fallback；
- action mask：返回前或外层统一 mask。

#### `_eds_initial_denoise_rbf_diverse`

- 输入 shape：`x_t: (B,64,128)`；
- 输出 shape：`population: (B,64,128)`；
- 是否使用 autograd：是，仅通过复用 `_compute_diversity_gradient()`；
- 是否影响 VLS：否；
- fallback：warning 后回到 `_eds_initial_denoise_iid()`；
- action mask：外层统一 mask，内部尽量保持 VLS diversity path 的行为。

#### `_eds_initial_validate_population`

- 输入 shape：`population: (B,64,128)`；
- 输出：原 population 或触发 warning + fallback；
- 检查 finite、shape、action mask violation；
- 是否使用 autograd：否。

#### `_eds_initial_cache_payload`

- 输入：population、cfg、initial sampler info；
- 输出：cache dict；
- 记录 sampling mode、scale、start ratio、fallback、grad norm stats。

不建议新增 `_eds_initial_diversity_gradient()` 作为独立算法实现。若为了日志和异常处理新增 wrapper，该 wrapper 内部应直接调用 `_compute_diversity_gradient()`，避免重复造轮子。

## 7. 新增配置字段建议

| 字段 | 默认值 | 含义 | 推荐范围 |
|---|---:|---|---|
| `initial_sampling_mode` | `"iid"` | initial population 采样模式，也是唯一机制开关 | `iid`, `rbf_diverse_denoise` |
| `initial_diversity_scale` | `1.0` | 复用 VLS RBF diversity gradient 的强度 | 0.1-10，首轮 1.0 |
| `initial_diversity_start_ratio` | `None` | 传给 `_resolve_start_step()` 的 ratio；`None` 表示复用 VLS 默认 | `None` 或 0-1 |
| `initial_diversity_fallback` | `"iid"` | RBF path 失败时 fallback 到 iid baseline | MVP 仅 `iid` |
| `initial_cache_metadata` | `True` | cache 是否保存 strategy metadata | bool |

默认配置不改变 baseline EDS：

```yaml
main:
  eds_config:
    initial_sampling_mode: iid
```

启用本方案：

```yaml
main:
  eds_config:
    initial_sampling_mode: rbf_diverse_denoise
    initial_diversity_scale: 1.0
    initial_diversity_start_ratio: null
```

不增加 `initial_diversity_enabled`，因为它会与 `initial_sampling_mode` 产生双开关歧义。不增加 `initial_diversity_allow_grad`，因为 `rbf_diverse_denoise` 的语义已经足够明确。

## 8. Cache 与兼容性

当前 `use_initial_cache=true` 时，`_eds_initial_population()` 从 `initial_population_cache` 读取 tensor 或 dict 中的 `"initial_population"`，校验 shape 后重新 `_apply_action_mask()`（`core/rdt_policy_steer.py:1500-1521`）。本方案应保持对旧 cache 的读取兼容。

`save_initial_cache=true` 时，建议保存最终 initial population，而不是保存 denoising 中间状态：

```python
{
  "initial_population": population.detach().cpu(),
  "metadata": {
    "initial_sampling_mode": "rbf_diverse_denoise",
    "initial_diversity_scale": 1.0,
    "initial_diversity_start_ratio": None,
    "initial_diversity_steps": 10,
    "initial_diversity_fallback_used": False,
    "initial_diversity_fallback_reason": None,
    "config_hash": "..."
  }
}
```

当 cache metadata 与当前 config 不一致时：

- metadata 存在且 strategy mismatch：默认报错，避免把 RBF-diverse cache 当成 iid baseline；
- metadata 缺失：允许读取旧 cache，但输出 warning；
- `initial_sampling_mode="iid"` 读取 RBF-diverse cache：默认报错，除非未来显式增加 mismatch override；
- cache metadata 不记录已删除的 `allow_grad` 或 `enabled` 字段。

## 9. Metrics 与可视化

当前 `EDSChunkMetrics` 已记录 population shape、initial/final reward、population diversity、target distance、action mask violation、latency 和 per-iteration statistics（`core/eds_eval_metrics.py:11-63`）。RBF-diverse initial sampler 应复用这些字段，并新增 initial sampler 专用指标：

- `initial_sampling_mode`;
- `initial_diversity_scale`;
- `initial_diversity_steps`;
- `initial_diversity_grad_norm_mean`;
- `initial_diversity_grad_norm_max`;
- `initial_diversity_grad_failure_count`;
- `initial_pairwise_traj_distance_before`;
- `initial_pairwise_traj_distance_after`;
- `initial_endpoint_spread`;
- `initial_action_mask_violation`;
- `initial_nonfinite_count`;
- `initial_sampler_latency_s`;
- `initial_diversity_fallback_used`;
- `initial_diversity_fallback_reason`。

`EDSMechanismTrace` 当前 stage 可记录 actions、trajectories、rewards、costs、parent ranks、renoise/rollout delta 等（`core/eds_mechanism_trace.py:13-42`），保存时会输出 metadata、CSV 和可选 tensor payload（`core/eds_mechanism_trace.py:80-170`）。建议为 mechanism pretest 增加以下 stage：

- `initial_iid_reference`：可选，仅用于同 seed 对照；
- `initial_before_diversity`：raw `x_t` 或第一个 denoise step 后的 trajectory；
- `initial_after_diversity_phase`：early diversity phase 结束后的 population；
- `initial_final`：完成 late normal denoise 和 action mask 后的 population；
- `scored`：沿用现有 initial scoring stage。

trace metadata 应记录 diversity step range、scale、grad norm stats 和 fallback 状态。可视化上重点比较 diversity 前后的 EE trajectory spread、endpoint spread 和最终 selected particle 后续 EDS refinement 轨迹。

## 10. 计算成本

相比 iid initial denoise，RBF-diverse initial denoise 的主要额外成本来自 autograd：

- 每个 diversity step 需要对 population 构建 trajectory graph；
- `_rdt_sample_to_trajectory_3d()` 当前逐 particle 调 adapter，B 较大时开销明显（`core/rdt_policy_steer.py:2149-2165`）；
- `torch.autograd.grad()` 会增加显存占用；
- pairwise distance 是 `O(B^2 * H)`，B=32 时仍可接受，但 B=64 以上需要关注显存。

降低成本的策略：

- 复用 VLS 默认 early diversity phase；
- 初始实验用 `population_size=16` 或 `32`；
- 复用 `_compute_diversity_gradient()` 中的 `create_graph=False`；
- 对 grad norm 做 detach logging；
- 如显存不足，可先降低 `population_size` 或减少 EDS eval episode 数，而不是先改 RBF 算法。

如果后续认为必须 chunk trajectory projection、减少 diversity steps、或改变 `_compute_diversity_gradient()` 的内部实现，需要先说明原因并请求 approval。

## 11. 风险与失败模式

- RBF diversity 可能把候选推离 policy manifold，导致 late denoising 无法修复。
- diversity sign 与 scheduler prediction type 不匹配，可能让 particles 更集中或动作异常。
- action slots 写错会污染 non-translation dimensions。
- gripper / rotation 被污染会破坏 grasp timing 或 wrist orientation。
- diversity scale 过大可能导致 nonfinite、trajectory jump 或 denoising 崩坏。
- adapter trajectory projection 不稳定会让 gradient 指向错误方向。
- grad norm 爆炸或接近 0 会导致更新不可控或无效。
- OOD reward proxy 改善不代表真实 rollout 成功率提升。
- latency 和显存增加可能抵消方法价值。
- 如果 `use_initial_cache` 混用了 iid/RBF cache，可能导致实验归因错误。
- fallback 如果没有 warning 会掩盖 RBF path 实际失效，因此 fallback 必须显式 warning 并进入实验报告。

## 12. 实验验证计划

### 12.1 unit tests

成功判据：

- `initial_sampling_mode="iid"` 时保持 baseline shape 和 behavior；
- `initial_sampling_mode="rbf_diverse_denoise"` 返回 `(population_size,64,128)`；
- action mask violation 为 0；
- nonfinite count 为 0；
- RBF path gradient failure 会 warning 并 fallback 到 iid；
- cache metadata strategy mismatch 可被检测；
- `core/` 以外的实验报告和 artifacts 不影响默认运行。

### 12.2 mechanism tests + qualitative evaluation

机制测试需要同时包含数值指标和 qualitative evaluation。qualitative 部分参考：

`/home/hynx/VLA-Pilot++/.worktrees/feat/rdt_ed_steering_integration/docs/01_specs/2026-06-12-rdt-eds-qualitative-pretest-design.md`

建议先在真实 `libero_object` 任务上做 first-chunk microscope：

| Item | Setting |
|---|---|
| Suite | `libero_object` |
| Task | task id `1` |
| Episodes | `1` |
| Chunk scope | first generated action chunk only |
| Guidance | `main.use_guidance=true`, `main.guidance_type=eds` |
| Reward mode | `normal` first; optional controls: `zero`, `inverted` |
| Population | start with `population_size=16` |
| EDS iterations | start with `cem_iters=10` |
| Outputs | 3D plots, scalar CSV/JSONL, saved tensors for first chunk only |

需要保存和检查的 qualitative artifacts：

- `00_initial_population_3d.png`：检查 initial trajectories 是否覆盖多个方向和幅度；
- `01_scored_population_3d.png`：按 reward 着色，检查 reward 是否与 keypoint geometry 对齐；
- `initial_before_diversity_3d.png`：RBF diversity 前 trajectory spread；
- `initial_after_diversity_phase_3d.png`：RBF diversity phase 后 trajectory spread；
- `initial_final_3d.png`：late normal denoise 后最终 initial population；
- `02_after_resample_3d.png`、`03_after_renoise_3d.png`、`04_after_rollout_3d.png`：沿用 EDS single-step inner-loop 可视化；
- `final_selected_vs_initial_best_3d.png`；
- `reward_curve.png`、`diversity_curve.png`、`distance_curve.png`；
- `full_process_summary.md`。

成功判据：

- RBF-diverse initial trajectory pairwise distance 高于 iid baseline；
- endpoint spread 高于 iid baseline；
- action mask violation 为 0；
- initial selected reward 不显著低于 iid baseline；
- grad norm 没有爆炸；
- qualitative plots 能显示 diversity phase 前后 spread 提升；
- reward-colored trajectories 与 keypoint/stage target 的几何关系基本一致；
- full-process best reward 或 target-distance trend 不比 baseline 更差。

### 12.3 small OOD smoke

配置建议：

```yaml
population_size: 16
cem_iters: baseline
initial_sampling_mode: rbf_diverse_denoise
initial_diversity_scale: 1.0
initial_diversity_start_ratio: null
```

成功判据：

- 3-5 个 OOD episodes 不崩溃；
- latency 增长可接受；
- 成功数不低于 iid EDS smoke；
- fallback 如发生必须有 warning 和 metrics 记录；
- 失败视频中不出现明显 gripper/rotation 异常。

### 12.4 full OOD evaluation

对照组：

- unguided RDT；
- current EDS iid baseline；
- EDS + RBF-diverse initial sampler。

测试任务：

- `libero_object_swap`；
- `libero_object_task`；
- `libero_object_task`。

如果两个 `libero_object_task` 对应不同 task id 或不同 OOD split，实验报告必须记录具体 task id、suite config、seed 和命令行 overrides，避免后续分析时混淆。

固定 task ids、seed、episode count、reward mode、CEM/temperature/renoise schedule 和 VLM guidance cache。

成功判据：

- OOD success rate 不为 0 且高于 current EDS baseline；
- initial trajectory diversity 与 endpoint spread 高于 baseline；
- selected reward 不低于 baseline；
- final target distance 不劣于 baseline；
- `initial_sampler_latency_s` 与总 `select_action_latency_s` 在可接受范围内。

### 12.5 实验报告要求

最终实验必须记录详细报告，供后续分析和 debug。报告至少包含：

- branch、commit hash、worktree path；
- exact command；
- full config overrides；
- sweep id、参数组合、validation gate pass/fail；
- `CUDA_VISIBLE_DEVICES`、GPU id、运行前 `nvidia-smi` 摘要；
- task suite、task ids、seeds、episode count；
- checkpoint 和 policy type；
- guidance type、reward mode、VLM/keypoint cache 信息；
- initial sampling mode 和 diversity 参数；
- success count / total、success rate；
- 每 episode 结果、失败原因初判、视频路径；
- `initial_sampler_latency_s`、`select_action_latency_s`；
- initial/final diversity、endpoint spread、selected reward、target distance；
- fallback warning 次数和原因；
- qualitative artifact 路径；
- 与 baseline 的差异总结；
- 下一步 debug 建议。

建议报告落在：

```text
docs/03_evidence/eds_init_pg_diverse_sampling/
```

或对应 `outputs/...` run 目录中，并在 docs 中保留索引。

### 12.6 闭环迭代部署与参数 sweep

RBF-diverse initial sampler 的实验部署应采用闭环迭代流程：在不改变算法核心逻辑的前提下，通过配置参数 sweep 逐步寻找满足验证指标的可用设置。这里的“闭环”指实验反馈驱动下一轮配置选择，而不是在线改变 EDS 算法语义。

推荐流程：

1. 固定代码路径和算法语义：`initial_sampling_mode="rbf_diverse_denoise"` 只改变 EDS initial population generator，后续 EDS resample / renoise / rollout / final selection 不变。
2. 先跑 current EDS iid baseline，记录 success、initial diversity、endpoint spread、selected reward、target distance 和 latency。
3. 跑 RBF-diverse 默认配置，检查 unit tests、mechanism tests、small OOD smoke、full OOD evaluation 的所有 validation gates。
4. 如果某项指标未通过，只做参数 sweep，不直接改 RBF distance space、gradient 方向、trajectory projection、reward、action slot 写回或 EDS refinement 主循环。
5. 每一轮 sweep 都记录参数、GPU、seed、任务、artifact 路径、pass/fail gate 和失败初判。
6. 当所有指标通过时冻结该配置作为 candidate default；如果多轮 sweep 仍不能通过，需要单独提交失败报告和下一步算法改动 proposal，再请求 approval。

允许优先 sweep 的参数：

- initial sampler 参数：`initial_diversity_scale`、`initial_diversity_start_ratio`、`initial_diversity_steps`、`initial_grad_clip_norm`；
- population 参数：`population_size`；
- EDS 既有 refinement 参数：`cem_iters`、`temperature`、`renoise_t_min`、`renoise_t_max`、`num_elites`。

参数 sweep 的推荐顺序：

1. 先固定 EDS refinement，只 sweep initial sampler 参数，确认 diversity phase 自身是否有效；
2. 如果 initial diversity 提升但 selected reward 或 target distance 变差，再小范围 sweep `initial_diversity_scale` 和 `initial_diversity_start_ratio`；
3. 如果 success rate 仍低但 trajectory metrics 合格，再考虑 sweep EDS 既有 refinement 参数；
4. 不应通过大幅提高 `population_size` 掩盖 initial sampler 失效，除非 latency 仍在可接受范围内且报告中明确说明成本。

每轮 sweep 的 pass/fail gate：

- shape、finite、action mask violation 全部通过；
- fallback warning 次数为 0，或 fallback 原因被明确记录并单独分析；
- initial trajectory diversity 和 endpoint spread 高于 iid baseline；
- selected reward 不低于 baseline；
- final target distance 不劣于 baseline；
- OOD success rate 不为 0 且高于 current EDS baseline；
- `initial_sampler_latency_s` 和总 `select_action_latency_s` 在可接受范围内。

不允许在未获得 approval 前改变的内容：

- VLS 一致的 3D EEF trajectory RBF distance space；
- `_compute_diversity_gradient()` / `_mask_guidance_gradient()` 的核心语义；
- RDT 128D action layout 与 translation slot 写回语义；
- EPS-CoT / VLM reward；
- EDS iterative refinement 主循环；
- fallback 到 iid 时的 warning 与 metrics 记录要求。

### 12.7 H200 GPU 资源调度策略

当前可用硬件假设为 4 块 H200。测试时应择机选择空闲 GPU 运行，默认优先考虑 GPU 3，但不能假设 GPU 3 永远空闲。

运行规范：

- 每次实验前用 `nvidia-smi` 检查 4 张卡的显存占用和 utilization；
- 单个 eval job 默认绑定单卡，例如 `CUDA_VISIBLE_DEVICES=3 ...`；
- 如果 GPU 3 繁忙而其他卡短暂空闲，可选择其他空闲 GPU；
- 如果多张卡空闲，可以并行跑不同 sweep config，但每个 job 应绑定单独 GPU、单独 output dir 和明确 seed；
- 不在 eval launcher 未验证支持的情况下启用单 job 多 GPU；
- 不抢占已有高负载实验；若无空闲 GPU，应等待或只做 CPU 侧文档/配置检查；
- 实验报告必须记录 GPU id、`CUDA_VISIBLE_DEVICES`、运行前 `nvidia-smi` 摘要、命令和输出目录。

推荐调度策略：

1. small OOD smoke 优先用 GPU 3 单卡；
2. mechanism qualitative pretest 可在任意空闲单卡上运行；
3. full OOD evaluation 优先保证同一对照组配置在一致资源策略下完成；
4. 参数 sweep 可在 GPU 3 与其他临时空闲卡之间并行，但必须避免共享输出目录和 seed 冲突。

## 13. MVP 实施范围

### 第一版只做

- 在 EDS initial sampler 中增加 RBF diversity denoising；
- 通过 `initial_sampling_mode` 切换，默认 `iid`；
- 复用 `_compute_diversity_gradient()`；
- 复用 `_mask_guidance_gradient()`；
- 复用 VLS 的 3D EEF trajectory RBF space；
- 复用 VLS 的 translation slot 写回逻辑 `[39,40,41]`；
- 增加 initial sampler metrics；
- 增加 cache metadata；
- fallback 到 iid 时必须 warning；
- mechanism trace 记录 diversity phase 前后 population；
- 不改 EDS refinement 主循环。

### 第一版不做

- 不改 EPS-CoT / VLM reward；
- 不改 CEM / MPPI / resample；
- 不改 renoise / rollout；
- 不改 final selection；
- 不改 VLS loop；
- 不直接 perturb decoded action；
- 不做 action-space 或 hybrid RBF distance；
- 不做真实机器人部署；
- 不引入新的 reward function；
- 不做双臂特化逻辑，只保留未来扩展接口。

## 14. 结论

RBF-diverse initial denoising sampling 是一种比 iid initial sampling 更主动的 EDS 初始化策略。第一版设计应尽量贴近 VLS 现有 RBF diversity 实现，通过 glue coding 将 early diversity denoising 用作 EDS initial population generator，而不是重新设计 sampling 算法。

MVP 应以默认关闭、只改 initial population、复用 VLS trajectory RBF、只写 translation slots、fallback 必须 warning 为原则。若 mechanism tests 证明 initial trajectory spread 和 endpoint spread 明显提升，再进入 small OOD smoke 和 full OOD evaluation。

实验阶段应采用闭环参数 sweep：在保持算法核心逻辑不变的前提下迭代配置，直到所有验证指标通过，或形成明确失败报告并提出需要 approval 的算法改动。H200 测试资源按空闲 GPU 动态分配，优先单卡隔离运行，并在最终实验报告中记录完整命令、GPU 状态、配置、指标和 artifacts，供后续分析和 debug。
