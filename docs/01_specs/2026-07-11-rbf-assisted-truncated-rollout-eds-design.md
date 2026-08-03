# RBF-Assisted Truncated Rollout + EDS Resampling 设计

## 1. 标题与摘要

方案名称：**RBF-assisted initial sampling + optional RBF-assisted truncated rollout + EDS resampling**。

本设计面向 `exp/eds-init-pg-diverse-sampling` 分支上的下一轮 RBF+EDS 算法优化。前三轮实验已经证明，`initial_sampling_mode=rbf_diverse_denoise` 能在 3D EEF trajectory space 中扩大 initial proposal diversity，但 naive truncated rollout 和多轮 reward-based resampling 会继续把 population 拉回 RDT/VLA prior，使 full EDS refinement 后的 diversity 下降。因此本方案在不改变 current EDS baseline 默认行为的前提下，为 truncated rollout 增加一个可选的 RBF-assisted 分支，用于评估 rollout 阶段的 diversity guidance 是否能提高 OOD 场景中的候选覆盖度和后续成功率。

本阶段只做设计，不实现代码。设计文档覆盖算法部署、配置字段、代码插入点、metrics/trace、level3 parameter sweep、风险和 MVP 范围。

## 2. 前三轮实验结论回顾

### 2.1 Aggressive initial RBF sweep

`docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-09-aggressive-rbf-parameter-sweep.md` 说明，RBF-assisted initial sampling 在 safety gate 上稳定运行：所有 aggressive RBF run 的 fallback、grad failure、nonfinite 和 action mask violation 均为 0。机制指标上，`initial_eef_diversity_after_rbf_phase` 与 `initial_eef_diversity_final` 相比 iid baseline 有明显提升。例如 `rbf_s20_start08` 的 `initial_eef_diversity_after_rbf_phase=0.456`，`initial_eef_diversity_final=0.156`，高于 iid baseline 的 `initial_eef_diversity_final=0.054`。

这说明 initial RBF path 本身是有效机制，但 after-RBF phase 到 final initial population 之间仍存在 denoising prior 收缩。

### 2.2 Qualitative diversity supplement

`docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-10-rbf-s20-qualitative-diversity-report.md` 进一步补充了 per-chunk qualitative evidence。每个 chunk 下保存：

- `RBF_diversity/eef_3d_before_after_final.png`
- `RBF_diversity/endpoint_scatter_before_after_final.png`
- `RBF_diversity/pairwise_distance_hist_before_after_final.png`
- `RBF_diversity/rbf_diversity_metrics.json`
- `RBF_diversity/rbf_diversity_trace.npz`
- `single_step_inner_loop/` 下的 single-step EDS inner-loop artifacts
- `full_eds_process/` 下的 per-iteration full-process artifacts

该报告明确指出，RBF phase 能在 3D EEF trajectory space 中打开粒子分布，但完整 denoising 后 diversity 会被 RDT policy prior 明显收缩。这正是本轮要继续处理的核心瓶颈。

### 2.3 Renoise tmax ablation

`docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-10-renoise-tmax-ablation-report.md` 与 `docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-11-renoise-rt1to1-start08-supplement.md` 表明，降低 `renoise_t_max` 可以提高 first-rollout EEF diversity，但不能阻止 full EDS refinement 后的 late-stage collapse。

关键机制观察是：

- first-rollout diversity 随较弱 truncated denoise 有所提高；
- final-iteration diversity 在所有 reduced-renoise setting 中仍保持较低；
- task success 与 first-rollout diversity 不单调一致；
- 仅继续减小 `renoise_t_max` 不足以解决多轮 EDS 后的 diversity loss。

因此本轮实验不应只继续调 `renoise_t_max`，而应测试 rollout denoising 内部是否需要额外的 RBF diversity guidance。

## 3. 当前问题定位

当前 EDS 数据流位于 `core/rdt_policy_steer.py`：

- `_EDSConfig` 定义 population、CEM、temperature、renoise、cache、reward、initial RBF 等字段，当前 initial sampling modes 为 `{"iid", "rbf_diverse_denoise"}`（`core/rdt_policy_steer.py:45-69`）。
- `_eds_initial_population()` 支持 cache、iid full denoise 和 `rbf_diverse_denoise`，最终 apply action mask 并验证 `(population_size, 64, 128)`（`core/rdt_policy_steer.py:1971-2064`）。
- `_eds_guided_denoise_loop()` 先 score initial population，再按 `np.linspace(cfg.renoise_t_max, cfg.renoise_t_min, cfg.cem_iters)` 生成每轮 `n_trunc_steps`（`core/rdt_policy_steer.py:2482-2488`）。
- 每轮 EDS 先基于 reward softmax 或 CEM resample parents，再 `_eds_renoise_reference()`，最后 `_eds_rollout_reference()` 做 truncated denoise 并重新 score（`core/rdt_policy_steer.py:2488-2597`）。
- `_eds_rollout_reference()` 当前完全在 `torch.no_grad()` 下遍历 `scheduler.timesteps[-n_trunc_steps:]`，每步只执行 DIT forward 和 scheduler step，然后 mask 与 score（`core/rdt_policy_steer.py:2077-2108`）。

这个结构意味着 initial RBF 提升出的多样性会经历两类收缩：

1. **Resampling 收缩**：低 temperature reward sampling 会复制少数高分 parents，降低 `unique_parent_ratio` 和 mode coverage。
2. **Rollout prior 收缩**：truncated rollout 的 denoise step 会把 noisy parent 拉回 policy prior，尤其在当前 naive rollout 不含 diversity pressure 时，粒子容易重新聚到同一 action mode。

本方案只处理第二类收缩，即 rollout denoising 内部的 prior pull；parent selection 多样化可以作为后续独立方案，不混入本轮 MVP。

## 4. 设计目标与非目标

### 4.1 目标

- 保留 current EDS baseline 默认行为。
- 保留现有 `initial_sampling_mode=rbf_diverse_denoise` 路径。
- 新增 optional RBF-assisted truncated rollout。
- 通过 `truncated_rollout_mode` 在 baseline rollout 与 RBF-assisted rollout 之间切换。
- 最大化复用 `_compute_diversity_gradient()`、`_mask_guidance_gradient()`、`RDT_DIVERSITY_SIGN`、`RDT_GUIDED_TRANSLATION_INDICES`、`_rdt_sample_to_trajectory_3d()`。
- RBF distance space 与 VLS / initial RBF 一致，固定为 3D EEF trajectory space。
- 不破坏 action mask，所有 rollout final population 必须保持 `(population_size, 64, 128)`。
- final selected action 仍按 reward/cost 选择。
- fallback 必须显式 warning，并写入 metrics/trace。
- level3 sweep 与第三轮 renoise ablation 的任务、episodes、offline VLM、qualitative tracing 设置保持一致。

### 4.2 非目标

- 不改变 VLS 路径语义。
- 不改变 EPS-CoT / cached VLM reward。
- 不把 diversity 直接加入 final selection objective。
- 不在本轮同时实现 diversity-aware parent resampling、anchor carryover 或 island EDS。
- 不扩大到 LIBERO-PRO full OOD benchmark，直到机制实验通过。
- 不改变 RDT 128D action layout，不新增 action-space 或 hybrid diversity metric。
- 不把 rollout RBF 设为默认启用。

## 5. 算法方案总览

推荐架构如下：

```text
initial x_t
  -> _eds_initial_population()
       mode=iid 或 rbf_diverse_denoise
  -> score initial population
  -> for each EDS iter i:
       resample parents by current EDS rule
       _eds_renoise_reference(population, n_trunc_steps)
       _eds_rollout_reference(inputs, cfg, iter_idx=i)
          if truncated_rollout_mode == baseline:
              current naive truncated denoise
          if truncated_rollout_mode == rbf_diverse:
              selected rollout denoise steps add RBF diversity gradient
       score rollout population
  -> final selected = argmin(cost)
```

设计重点是保持 `_eds_rollout_reference()` 作为统一入口。它内部按 `cfg.truncated_rollout_mode` 分发到 baseline helper 或 RBF helper。这样 `_eds_guided_denoise_loop()` 的主控制流只需要传入 `cfg` 和 `iter_idx`，不需要在 EDS loop 中复制 denoising 逻辑。

## 6. RBF-Assisted Truncated Rollout 设计

### 6.1 baseline rollout

`truncated_rollout_mode="baseline"` 时，行为与当前 `_eds_rollout_reference()` 完全一致：

```text
scheduler.set_timesteps(num_inference_steps)
n_trunc_steps = clamp(n_trunc_steps, 1, len(timesteps))
x_t = noisy_action
with torch.no_grad():
    for t in scheduler.timesteps[-n_trunc_steps:]:
        model_output = self._dit(x_t, t, cond)
        x_t = scheduler.step(model_output, t, x_t).prev_sample
x_t = x_t * action_mask
costs, info = _eds_score_population_as_cost(x_t, scoring_context)
return x_t, costs, info
```

该路径用于 baseline、ablation 对照和 rollout RBF fallback。

### 6.2 RBF-assisted rollout

`truncated_rollout_mode="rbf_diverse"` 时，在 truncated rollout 的部分 denoising steps 中复用 RBF diversity gradient：

```text
rollout_timesteps = scheduler.timesteps[-n_trunc_steps:]
apply_until = resolve rollout_diversity_start_ratio over rollout_timesteps

for local_step, t in enumerate(rollout_timesteps):
    with torch.no_grad():
        model_output = self._dit(x_t, t, cond)

    if should_apply_rollout_diversity(
        iter_idx=i,
        local_step=local_step,
        t=t,
        n_trunc_steps=n_trunc_steps,
        cfg=cfg,
    ):
        div_grad = self._compute_diversity_gradient(x_t)
        if div_grad is valid:
            masked_div = self._mask_guidance_gradient(div_grad)
            model_output[:, :, RDT_GUIDED_TRANSLATION_INDICES] += (
                RDT_DIVERSITY_SIGN
                * cfg.rollout_diversity_scale
                * masked_div[:, :, RDT_GUIDED_TRANSLATION_INDICES]
            )
            record grad norm and after-rbf phase snapshot
        else:
            warn and fallback according to fallback policy

    x_t = scheduler.step(model_output, t, x_t).prev_sample

x_t = x_t * mask
score and return
```

注意：`_compute_diversity_gradient()` 内部已经使用 `torch.enable_grad()`，且返回全局 norm-normalized gradient（`core/rdt_policy_steer.py:2844-2879`）。因此第一版不再额外设计 gradient clipping config。若后续发现 normalized gradient 仍导致 low-noise action instability，再作为单独设计点加入。

### 6.3 作用 timestep

当前 initial RBF 的 `_resolve_start_step()` 是基于完整 scheduler timesteps 的 threshold：`start_ratio=None` 时使用 `timesteps[len(timesteps)//3]`，否则使用 `idx=int(len(timesteps) * ratio)` 并 clamp（`core/rdt_policy_steer.py:2954-2959`）。

rollout RBF 不建议直接复用完整 scheduler 的 absolute start_step，因为 truncated rollout 只使用 `scheduler.timesteps[-n_trunc_steps:]`。推荐定义：

```text
rollout_timesteps = scheduler.timesteps[-n_trunc_steps:]
diversity_step_count = ceil(len(rollout_timesteps) * rollout_diversity_start_ratio)
apply to first diversity_step_count rollout-local steps.
```

含义：

- `rollout_diversity_start_ratio=0.6`：对当前 truncated rollout 的前 60% local denoise steps 添加 diversity。
- `rollout_diversity_start_ratio=0.8`：对前 80% local steps 添加 diversity。
- `rollout_diversity_skip_final_steps=0`：MVP 默认不跳过最后 step，确保 `rt1to1` 也能实际评估 rollout RBF。

如果后续需要降低 low-noise step 风险，可以单独测试 `rollout_diversity_skip_final_steps=1`。但本轮已决定不把它作为 MVP 默认，也不在 sweep 中展开；因此 `n_trunc_steps=1` 不需要特殊 case：

```text
effective_skip = 0
```

这意味着 `rt1to1` 的单个 rollout denoise step 会被纳入 RBF-assisted rollout 的评估。

### 6.4 作用 EDS iterations

推荐新增 `rollout_diversity_iters` 控制前多少个 EDS iterations 使用 rollout RBF：

- `0`：禁用，等价 baseline；
- `1`：只在第 0 轮 EDS rollout 使用；
- `3`：只在前 3 轮使用；
- `6`：只在前 6 轮使用；
- `"all"`：所有 EDS iterations 使用。

第一版 sweep 直接覆盖 `[1, 3, 6, "all"]`。其中 `"all"` 的计算成本最高，也最可能持续对抗 reward exploitation；但本轮目标是完整记录不同 rollout intervention horizon 的效果，由实验结果再决定后续收窄范围。

### 6.5 fallback 行为

RBF-assisted rollout fallback 必须显式。推荐第一版 fallback policy 固定为：

```text
fallback to baseline rollout for the current rollout call
```

触发条件：

- `population_size <= 1`
- adapter 缺失导致 `_compute_diversity_gradient()` 返回 `None`
- diversity gradient 返回 `None`
- diversity gradient 非 finite
- modified `model_output` 非 finite
- scheduler step 后 `x_t` 非 finite
- action mask validation 后 violation 超过阈值

日志和 metrics 至少记录：

- `truncated_rollout_mode`
- `rollout_diversity_fallback_used`
- `rollout_diversity_fallback_reason`
- `iter_idx`
- `n_trunc_steps`
- local step index
- timestep
- population shape

不允许静默 fallback。若 fallback 频繁出现，该参数组合直接判为 safety gate failed。

## 7. Config 设计

新增 `_EDSConfig` 字段建议如下。

| 字段 | 默认值 | 类型 | 含义 | 推荐 sweep | Cache 影响 | Baseline 兼容 |
|---|---:|---|---|---|---|---|
| `truncated_rollout_mode` | `"baseline"` | str | truncated rollout 策略，`baseline` 为当前 naive rollout，`rbf_diverse` 为 rollout 阶段 RBF | `baseline`, `rbf_diverse` | 不影响 initial cache | 默认完全兼容 |
| `rollout_diversity_scale` | `1.0` | float | rollout RBF 写回 model_output 的强度 | `[5,10,15,20]` | 不影响 initial cache | 仅 `rbf_diverse` 使用 |
| `rollout_diversity_start_ratio` | `0.8` | float | rollout-local timesteps 中启用 RBF 的比例 | `[0.6,0.8]` | 不影响 initial cache | 仅 `rbf_diverse` 使用 |
| `rollout_diversity_iters` | `0` | int 或 `"all"` | 前多少个 EDS iterations 使用 rollout RBF；`0` 禁用，`"all"` 表示全部 EDS iterations | `[1,3,6,"all"]` | 不影响 initial cache | `0` 等价 baseline |
| `rollout_diversity_skip_final_steps` | `0` | int | 多步 rollout 时跳过最后几个低噪声 steps；MVP 默认不跳过，保证 `rt1to1` 也能测试 rollout RBF | 固定 `0` | 不影响 initial cache | 仅 `rbf_diverse` 使用 |

解析校验建议：

- `truncated_rollout_mode in {"baseline", "rbf_diverse"}`；
- `rollout_diversity_scale` finite；
- `rollout_diversity_start_ratio in [0,1]`；
- `rollout_diversity_iters` 为 `0`、正整数或字符串 `"all"`；
- `rollout_diversity_skip_final_steps >= 0`；
- 若 `truncated_rollout_mode="baseline"`，其他 rollout diversity 字段可解析但不生效。

不建议第一版加入的字段：

| 字段 | 不加入原因 |
|---|---|
| `rollout_diversity_enabled` | 与 `truncated_rollout_mode` 冗余，容易出现状态不一致 |
| `rollout_diversity_metric` | 当前要求与 VLS/initial RBF 一致，固定 3D EEF trajectory space |
| `rollout_diversity_slots` | 当前只允许 translation slots `[39,40,41]`，不暴露给 sweep |
| `rollout_diversity_fallback` | 第一版固定 fallback to baseline rollout，避免配置空间膨胀 |
| `rollout_diversity_decay` | timestep-dependent decay 可后续加入，第一版先保持机制可解释 |

## 8. 代码插入点设计

### 8.1 `_EDSConfig` 和解析逻辑

在 `_EDSConfig` 中新增 rollout diversity 字段。`_resolve_eds_config_with_reference_defaults()` 负责解析默认值和校验。默认必须保证旧配置无需修改即可运行。

需要同步更新：

- `EDSChunkMetrics` dataclass；
- metrics population helper；
- tests 中 config parsing 相关断言；
- runner command builder。

### 8.2 `_eds_guided_denoise_loop()`

当前 `_eds_guided_denoise_loop()` 调用 `_eds_rollout_reference()` 时只传入 `cond`、`action_mask`、`noisy_action`、`keypoints`、`guidance_fns`、`n_trunc_steps`、`reward_mode`、`shuffle_seed`（`core/rdt_policy_steer.py:2577-2586`）。

建议最小改动为：

```text
_eds_rollout_reference(
    existing rollout inputs,
    n_trunc_steps=n_trunc_steps,
    iter_idx=i,
    cfg=cfg,
)
```

返回值保持：

```text
tuple[Tensor, Tensor, dict]
```

其中 `info` 继续包含 rewards，同时追加 rollout diversity telemetry。

### 8.3 `_eds_rollout_reference()`

保留统一入口，内部做模式分发：

```text
if cfg.truncated_rollout_mode == "baseline":
    return _eds_rollout_baseline_reference(inputs)
if cfg.truncated_rollout_mode == "rbf_diverse":
    if not _eds_should_apply_rollout_diversity(cfg, iter_idx):
        return _eds_rollout_baseline_reference(inputs)
    return _eds_rollout_rbf_diverse_reference(inputs, cfg, iter_idx)
```

如果为了减少代码移动，也可以保留现有函数体作为 baseline 分支，在同一函数中添加小块 RBF 分支。但推荐 helper 化，便于 tests 覆盖 baseline 和 RBF 两条路径。

### 8.4 Helper 输入输出

建议 helper：

| Helper | 输入 | 输出 | 说明 |
|---|---|---|---|
| `_eds_rollout_baseline_reference` | `cond`, `action_mask`, `noisy_action`, `keypoints`, `guidance_fns`, `n_trunc_steps`, `reward_mode`, `shuffle_seed` | `(population, costs, info)` | 当前 naive rollout 原逻辑 |
| `_eds_rollout_rbf_diverse_reference` | baseline 输入 + `cfg`, `iter_idx` | `(population, costs, info)` | RBF-assisted rollout |
| `_eds_should_apply_rollout_diversity` | `cfg`, `iter_idx`, `n_trunc_steps` | bool | 控制 iteration 维度 |
| `_eds_rollout_diversity_step_mask` | `cfg`, `rollout_timesteps`, `local_step`, `n_trunc_steps` | bool | 控制 timestep 维度 |
| `_eds_rollout_fallback_to_baseline` | baseline 输入 + reason metadata | `(population, costs, info)` | warning + baseline rollout |

所有 population tensor shape 均为 `(population_size, 64, 128)`。trajectory metrics 通过 `_rdt_sample_to_trajectory_3d()` 投影到 `(population_size, H+1, 3)`。

### 8.5 Action mask 顺序

推荐顺序：

1. rollout 前 `noisy_action` 假定已经来自 masked clean parent 的 renoise；
2. RBF gradient 通过 `_mask_guidance_gradient()` 只写 guided translation slots；
3. 每个 scheduler step 后不必强制 mask，否则可能改变 scheduler dynamics；
4. rollout final 必须 `x_t = x_t * mask`；
5. score 前记录 action mask violation；
6. violation 超阈值时 warning 并 fallback 或 raise，具体第一版建议 fallback to baseline rollout。

### 8.6 `torch.no_grad()` 与 autograd

baseline rollout 保持完整 `torch.no_grad()`。

RBF-assisted rollout 推荐：

```text
with torch.no_grad():
    model_output = self._dit(x_t, t, cond)

div_grad = self._compute_diversity_gradient(x_t)
```

`_compute_diversity_gradient()` 内部已有局部 `torch.enable_grad()` 和 `x_t.detach().requires_grad_(True)`。这样可以避免 DIT forward 被 autograd 追踪，同时只让 trajectory projection 和 RBF potential 参与 gradient 计算。

### 8.7 Warning 和 fallback

建议新建 `_eds_warn_rollout_diversity_fallback` helper 或沿用日志直接 warning。warning 文本必须包含足够上下文，便于查日志定位参数组合：

```text
EDS rollout diversity fallback to baseline:
mode=rbf_diverse reason=<reason>
iter=<i> local_step=<k> timestep=<t>
n_trunc_steps=<n> population_shape=(B,64,128)
```

## 9. Metrics 与 Mechanism Trace 设计

### 9.1 新增 chunk-level metrics

在 `EDSChunkMetrics` 中额外加入 rollout-specific 字段，不替代现有 initial metrics。

| 字段 | 含义 |
|---|---|
| `rollout_diversity_enabled` | 当前 chunk 是否启用过 rollout RBF |
| `rollout_diversity_mode` | `"baseline"` 或 `"rbf_diverse"` |
| `rollout_diversity_scale` | rollout RBF scale |
| `rollout_diversity_start_ratio` | rollout-local RBF step ratio |
| `rollout_diversity_iters_applied` | 实际使用 rollout RBF 的 EDS iterations 数 |
| `rollout_diversity_steps_applied` | 所有 iterations 中累计 RBF steps |
| `rollout_diversity_grad_norm_mean` | rollout RBF gradient norm 均值 |
| `rollout_diversity_grad_norm_max` | rollout RBF gradient norm 最大值 |
| `rollout_diversity_fallback_used` | 是否触发 rollout fallback |
| `rollout_diversity_fallback_reason` | fallback 原因 |
| `eef_diversity_before_rollout` | rollout 前 clean/noisy diagnostic population 的 EEF diversity |
| `eef_diversity_after_rollout_rbf_phase` | rollout RBF phase 后 EEF diversity |
| `eef_diversity_after_rollout_final` | rollout final population 的 EEF diversity |
| `eef_diversity_rollout_retention_ratio` | final / after_rbf_phase |
| `endpoint_spread_before_rollout` | rollout 前 endpoint spread |
| `endpoint_spread_after_rollout_rbf_phase` | rollout RBF phase 后 endpoint spread |
| `endpoint_spread_after_rollout_final` | rollout final endpoint spread |

聚合建议：

- 对 per-iteration telemetry，chunk-level metrics 默认记录第一个 EDS iteration 的 before/after/final，以及全 loop 的 applied counts 和 grad norms。
- full process 里每轮 diversity 由 `EDSIterMetrics.population_diversity` 和 mechanism trace 补充。
- 后续如需 per-iteration rollout EEF metrics，可在 evidence report 从 trace tensor 离线计算，不急于把全部 per-iter 字段塞进 JSONL。

### 9.2 Mechanism trace stage

当前 trace 已有：

- initial sampler stages；
- `initial`；
- `scored`；
- `resampled`；
- `renoised`；
- `after_rollout`；
- `full_process_after_rollout`。

建议新增 rollout RBF 相关 stage：

| Stage | iter_idx | 何时保存 |
|---|---:|---|
| `rollout_before_diversity` | i | RBF-assisted rollout 开始前，等价 renoised population |
| `rollout_after_diversity_phase` | i | 最后一个 RBF step 之后 |
| `rollout_final` | i | 完整 truncated rollout 后 |

为了兼容现有 visualization，`after_rollout` 可以继续保留，指向 rollout final。`rollout_final` 作为更明确的新 stage，用于 RBF rollout 对比图。

### 9.3 Qualitative artifacts

建议复用现有 qualitative chunk 输出约定，并增加 rollout-specific 目录：

```text
qualitative/episode_xxx/chunk_yyyyyy/
  RBF_diversity/
  single_step_inner_loop/
  full_eds_process/
  Rollout_RBF_diversity/
    rollout_eef_3d_before_after_final.png
    rollout_endpoint_scatter_before_after_final.png
    rollout_pairwise_distance_hist_before_after_final.png
    rollout_rbf_diversity_metrics.json
    rollout_rbf_diversity_trace.npz
```

`Rollout_RBF_diversity` 中的三阶段含义为：

- before rollout RBF：`rollout_before_diversity`
- after rollout RBF phase：`rollout_after_diversity_phase`
- rollout final：`rollout_final` 或 `after_rollout`

图像必须使用同坐标轴、同视角，避免视觉误判。

## 10. Level3 Parameter Sweep 设计

### 10.1 固定 initial sampler

本轮固定：

```yaml
main.eds_config.initial_sampling_mode: rbf_diverse_denoise
main.eds_config.initial_diversity_scale: 20.0
main.eds_config.initial_diversity_start_ratio: 0.8
main.eds_config.population_size: 16
main.eds_config.cem_iters: 10
main.eds_config.use_cem: false
main.eds_config.num_elites: 16
main.eds_config.temperature: 0.1
```

简称：`rbf_s20_start08`。

说明：旧 runner 模板中常见 `population_size=16, use_cem=false, num_elites=32`。这在当前 non-CEM EDS 路径下可以运行，因为 `num_elites` 只有 `use_cem=true` 时才参与 elite sampling；但该写法容易误导，并且一旦切换 `use_cem=true` 会违反 `num_elites <= population_size` 校验。因此本设计将 `num_elites` 设为 16，保持配置语义自洽。与第三轮 baseline 的 `num_elites=32` 对照不受影响，因为两者均为 `use_cem=false`，该字段不参与算法路径。

### 10.2 Baseline 对照

必须保留相同 `renoise_t_max -> renoise_t_min` 下的 naive rollout baseline：

| Label | truncated rollout |
|---|---|
| `rbf_s20_start08_rt4to1_base` | baseline |
| `rbf_s20_start08_rt3to1_base` | baseline |
| `rbf_s20_start08_rt2to1_base` | baseline |
| `rbf_s20_start08_rt1to1_base` | baseline |

baseline 直接引用第三轮 renoise ablation 与 `rt1to1` supplement 的 naive rollout 结果，不额外重跑。报告中必须明确 baseline reference 来自既有输出，并说明新 run 与 baseline 均为 `use_cem=false`，`num_elites` 差异不影响算法路径。

### 10.3 参数范围

必须 sweep：

```yaml
renoise_t_max -> renoise_t_min:
  - 4 -> 1
  - 3 -> 1
  - 2 -> 1
  - 1 -> 1

rollout_diversity_scale:
  - 5
  - 10
  - 15
  - 20

rollout_diversity_start_ratio:
  - 0.6
  - 0.8

rollout_diversity_iters:
  - 1
  - 3
  - 6
  - all
```

Full factorial RBF-assisted 组合数：

```text
4 renoise settings * 4 scales * 2 start ratios * 4 iter settings = 128 jobs
```

baseline 直接引用第三轮和 `rt1to1` supplement 的 naive rollout 结果，不额外重跑。最终报告包含 128 个新 RBF-assisted rollout jobs 和 4 个 baseline reference rows。

### 10.4 推荐实际执行策略

本轮不分阶段，不做机制子集筛选。直接提交完整 128-job RBF-assisted rollout sweep，使用现有所有可用 H200 GPU 并行执行；所有结果完整记录，由人工后续排查和筛选。

```text
rt: [4->1, 3->1, 2->1, 1->1]
scale: [5, 10, 15, 20]
start_ratio: [0.6, 0.8]
iters: [1, 3, 6, all]
```

执行要求：

- 启动前用 `nvidia-smi` 检查空闲 GPU；
- 使用所有当前空闲 H200 并行调度；
- 若空闲 GPU 少于 128 个 jobs，则 runner 自动排队；
- 单个 job 失败不阻塞其他 jobs；
- 每个 job 必须保存完整 stdout/stderr log、Hydra config、metrics、qualitative artifacts 和 failure reason；
- 支持 `--resume`，避免中断后重复已完成 jobs；
- 报告中将 128 个新 jobs 与第三轮 naive rollout baseline reference 对齐比较。

### 10.5 Job 命名规范

建议命名：

```text
level3_libero_object_rbf_s20_start08_rt{T}to1_rollrbf_s{S}_start{SR}_iter{I}
```

示例：

```text
level3_libero_object_rbf_s20_start08_rt4to1_rollrbf_s10_start08_iter3
level3_libero_object_rbf_s20_start08_rt1to1_rollrbf_s20_start08_iter1
```

baseline：

```text
level3_libero_object_rbf_s20_start08_rt4to1_base
```

若 `rollout_diversity_iters="all"`，label 使用 `iterall`。

### 10.6 Output directory

沿用 runner 当前规范：

```text
outputs/rdt_eds_eval/<job_id>/
  .hydra/config.yaml
  eds_eval/
    eds_metrics.jsonl
    qualitative/
```

实验报告写入：

```text
docs/03_evidence/eds_init_pg_diverse_sampling/
```

建议新增：

```text
2026-07-XX-rollout-rbf-level3-parameter-sweep.md
logs/<job_id>.log
rdt_eds_eval_status.csv
```

### 10.7 Runner level 设计

建议在 `scripts/rdt_eds_eval_runner.py` 新增 level：

```text
rollout_rbf_ablation
```

原因：

- `level3` 当前是通用 EDS baseline methods；
- `renoise_ablation` 已经用于第三轮；
- 新 level 可以隔离 rollout RBF 组合、命名和 report writer；
- 方便后续扩展到 LIBERO-PRO 时复用 job schema。

Runner 需要追加 Hydra overrides：

```text
main.eds_config.truncated_rollout_mode=rbf_diverse
main.eds_config.rollout_diversity_scale=<S>
main.eds_config.rollout_diversity_start_ratio=<SR>
main.eds_config.rollout_diversity_iters=<I>
main.eds_config.rollout_diversity_skip_final_steps=0
```

baseline jobs 使用：

```text
main.eds_config.truncated_rollout_mode=baseline
```

### 10.8 与第三轮实验一致的设置

第一版保持：

```yaml
backend.libero.suite_name: libero_object
backend.libero.task_ids_filter: [0]
main.episode_num: 3
backend.libero.max_episode_steps: 240
main.use_vlm_stage_recognition: false
perception.gemini_grounding.enabled: false
main.cached_functions_dir: /home/hynx/VLA-Pilot++/outputs/libero/2026-06-04_13-21-01/episode_1/vlm_agent
main.eds_mechanism_pretest.enabled: true
main.eds_mechanism_pretest.first_chunk_only: false
main.eds_mechanism_pretest.output_mode: qualitative_chunk
main.eds_mechanism_pretest.max_chunks: 2
main.eds_mechanism_pretest.save_tensors: true
main.eds_mechanism_pretest.plot_3d: true
main.eds_mechanism_pretest.max_full_process_iters: 10
```

## 11. Benchmark 与资源计划

### 11.1 当前 level3 benchmark

本轮只跑 `libero_object` task filter `[0]`，episodes 与第三轮一致，使用 offline cached guidance。原因是当前目标是机制验证，不是最终 OOD 成功率声明。

### 11.2 后续 LIBERO-PRO 扩展

若 level3 通过，应扩展到 LIBERO-PRO / OOD benchmark。扩展时建议：

- 保留同一 config schema 和 job naming；
- 只把完整 128-job sweep 中通过 safety + utility gate 的 top 2-3 个 setting 放进 OOD；
- 对照组至少包含 unguided RDT、current EDS iid baseline、RBF initial only、RBF initial + rollout RBF；
- 输出仍写入 `docs/03_evidence/eds_init_pg_diverse_sampling`，但按 suite 分节。

### 11.3 GPU 并行策略

当前服务器有 8 块 H200。建议执行前用 `nvidia-smi` 检查空闲 GPU：

- 使用所有当前空闲 H200 并行提交完整 128-job rollout RBF sweep；
- 若 8 卡空闲，runner 以 8-way 并行队列持续执行，直到所有 jobs 完成；
- 每个 job 独立日志，失败不阻塞其他 jobs；
- runner resume 必须支持跳过已完成 job；
- 如果某些 GPU/EGL 组合不稳定，优先使用已验证的 GPU/EGL mapping。

### 11.4 Latency 预期

rollout RBF 的额外成本来自每个 RBF step 的 `_compute_diversity_gradient()`，它需要对 population 投影到 3D EEF trajectory 并做 pairwise distance/autograd。粗略估计：

```text
extra_grad_calls_per_chunk
  ~= applied_iters * applied_rollout_rbf_steps_per_iter
```

例如 `rt4to1, start_ratio=0.8, skip_final_steps=0`：

- local rollout steps 为 4；
- RBF steps 约为 ceil(4*0.8) = 4；
- `rollout_diversity_iters=3` 时每个 chunk 约 12 次额外 diversity gradient；
- `rollout_diversity_iters="all"` 且 `cem_iters=10` 时每个 chunk 约 40 次额外 diversity gradient。

这比 initial RBF 的约 4 个 gradient steps 更贵，因此第一版需要记录 `select_action_latency_s`、`eds_loop_latency_s` 和 rollout-specific latency 或 grad step counts。

## 12. 成功判据

本轮是否进入 LIBERO-PRO OOD benchmark，至少需要满足：

1. Success rate 不低于相同 rt setting 的 naive rollout baseline。
2. First-rollout EEF diversity 高于 naive rollout baseline。
3. Final-iteration EEF diversity 高于 naive rollout baseline，或 full-process diversity curve 明显延后 collapse。
4. `selected_reward` 不低于 baseline，或下降在明确可接受范围内。
5. `target_distance_after` 不劣于 baseline。
6. `rollout_diversity_fallback_used` 为 false，或 fallback rate 极低且所有 fallback 均有 warning 和 reason。
7. `action_mask_violation_max = 0`。
8. `nonfinite_count = 0`。
9. `select_action_latency_s` 增幅可接受；完整 sweep 中需要按 `rollout_diversity_iters` 分组报告 latency，尤其单独标记 `"all"` 设置。
10. Qualitative plots 能清楚展示 rollout RBF 在 EDS iteration 内保留 diversity，而不是只在 initial RBF phase 打开。

如果只提升 diversity 但 selected reward 和 target distance 明显变差，应判为机制有收益但 utility gate fail，不进入 OOD。

## 13. 风险与 Fallback 策略

| 风险 | 表现 | 缓解 |
|---|---|---|
| 破坏 RDT/VLA action prior | 轨迹发散、target distance 变差 | 本轮默认不跳过最后 step，因此必须依赖 scale sweep、reward/distance gate 和 qualitative plots 判读 |
| diversity 与 reward exploitation 冲突 | diversity 提升但 selected reward 下降 | final selection 保持 reward-only，report 同时看 reward/distance |
| low-noise timestep 过强 | rt1to1 或最后 step 动作不稳定 | 本轮保留该风险以完整评估 `rt1to1`，通过 nonfinite/action mask/reward/distance/qualitative gate 过滤 |
| 计算成本过高 | latency 明显上升 | 直接完整记录 `[1,3,6,all]` 的 latency，由后续报告筛选可用设置 |
| 仍被 parent resampling 吃掉 | after rollout 有 diversity，下一轮又 collapse | report 记录 unique_parent_ratio 和 full process curve，后续再做 parent diversity |
| scale 越大不一定越好 | s20 reward 或 distance 变差 | 保留 `[5,10,15,20]` sweep，不把 s20 设为默认 |
| fallback 频繁触发 | warning 多、metrics fallback true | 该组合 safety gate fail |
| autograd context 错误 | memory 增长或 DIT 被追踪 | DIT forward 保持 no_grad，只有 diversity helper enable_grad |
| action mask 破坏 | masked dims 非零 | final apply mask，score 前记录 violation |
| trace 体积过大 | qualitative 输出过重 | 继续 `max_chunks=2`，full_process 限制 `max_full_process_iters=10` |

## 14. MVP 推荐实现范围

MVP 建议只做以下内容：

1. `_EDSConfig` 增加 5 个 rollout diversity 字段。
2. `_resolve_eds_config_with_reference_defaults()` 增加解析和校验。
3. `_eds_rollout_reference()` 保持统一入口，新增 baseline/helper 分支。
4. 新增 `_eds_rollout_rbf_diverse_reference()`，复用 `_compute_diversity_gradient()`。
5. `_eds_guided_denoise_loop()` 传入 `cfg` 和 `iter_idx`。
6. `EDSChunkMetrics` 增加 rollout-specific metrics。
7. mechanism trace 增加 rollout before/after/final stage。
8. qualitative visualization 增加 rollout RBF before/after/final 对比 artifacts。
9. `scripts/rdt_eds_eval_runner.py` 增加 `rollout_rbf_ablation` level。
10. tests 覆盖 config parsing、baseline compatibility、RBF rollout calls、fallback warning、metrics serialization、runner jobs。

MVP 不做：

- diversity-aware parent resampling；
- anchor carryover；
- island EDS；
- final objective 加 diversity；
- adaptive schedule；
- LIBERO-PRO full OOD；
- rollout diversity metric/slot 可配置化；
- timestep-dependent scale decay。

一句话 MVP：**在保持 current EDS baseline 默认不变的前提下，为 `_eds_rollout_reference()` 增加 `truncated_rollout_mode=rbf_diverse` 可选分支，只在前若干 EDS iterations 和 rollout-local early steps 中复用现有 3D EEF RBF diversity gradient，并用 level3 sweep 验证它是否能把 initial RBF diversity 留到 rollout 和 full EDS 后期。**

## 15. 已确认的设计决策

本节记录本轮设计 review 后已经确认的决策，后续 implementation plan 应按这些决策执行：

1. 接受 `truncated_rollout_mode` 作为唯一开关，不新增 `rollout_diversity_enabled`。
2. 接受 rollout RBF 的 timestep 语义采用 rollout-local ratio，不复用完整 scheduler absolute start_step。
3. 不接受 `rollout_diversity_skip_final_steps=1` 作为 MVP 默认；本轮固定 `rollout_diversity_skip_final_steps=0`，不为 `n_trunc_steps=1` 设计 special case。
4. 不接受只 sweep `[iters=1,3]`；本轮 `rollout_diversity_iters` sweep 为 `[1,3,6,"all"]`。
5. 不采用 Phase A/Phase B 分阶段策略；直接使用所有可用 GPU 并行完成完整 sweep。
6. 接受第一版不做 parent diversity resampling，本轮只评估 rollout RBF 的独立贡献。
7. Naive rollout baseline 直接引用第三轮 renoise ablation 与 `rt1to1` supplement 结果，不额外重跑。
8. Visualization 是必做项；implementation plan 必须包含 rollout RBF qualitative plots、trace tensors、metrics JSON/JSONL 和 full-process artifacts。
