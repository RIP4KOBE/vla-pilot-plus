# RDT `_guided_denoise_loop` VLS Steering Analysis

Date: 2026-06-05

Scope: current worktree implementation analysis for `core/rdt_policy_steer.py`, with the VLS call chain from `main.py` and interface comparison against `core/diffusion_policy_steer.py` and `core/pi05_steer.py`.

Key source files and functions:

- `main.py`: `Main.__init__`, `Main.perform_task_for_episode`, `Main._run_episode`, `_get_visualization_action_chunk`
- `core/rdt_policy_steer.py`: `RDTSteer.select_action`, `_predict_guided`, `_guided_denoise_loop`, `_compute_keypoint_gradient`, `_compute_diversity_gradient`, `_apply_keypoint_guidance`, `_init_fkd`, `_score_particles`, `_select_particle_for_execution`, `_order_particles_for_visualization`, `_rdt_sample_to_trajectory_3d`, `_adaptive_scale_for_scheduler_t`
- `core/rdt_libero_action_converter.py`: `rdt_action_to_libero_raw`, `decode_rdt_libero_action_chunk`
- `core/fkd_class.py`: `FKD`
- `core/diffusion_policy_steer.py`: `DiffusionPolicySteer._guided_conditional_sample`
- `core/pi05_steer.py`: `PI05PolicySteer._sample_actions_guided`

## 1. 背景与调用链总览

`RDTSteer` 是 RDT-1B LIBERO policy 的 VLS 适配层。它对外刻意保持与 `DiffusionPolicySteer` / `PI05PolicySteer` 相同的 duck-typed 接口：`post_init()`、`select_action()`、`reset()`、`reset_stage()`、`get_normalized_reward()`、`get_last_scale()`、`_action_chunk_horizon` 和 `name`。主程序因此可以用同一套 `select_action(...)` 参数向三种 policy 传入 keypoints、VLM guidance functions、guide scale、diversity / FKD 开关等。

端到端调用链如下：

```text
main.py:Main._run_episode
  -> 每个 action chunk 边界:
     keypoints = keypoint_tracker.get_keypoint_positions()
     current_guidance_fns = self.guidance_fns[current_stage]
     guide_scale / sigmoid_k / sigmoid_x0 / use_diversity / use_fkd from cfg.main
  -> self.policy.select_action(...)
     -> core/rdt_policy_steer.py:RDTSteer.select_action
        -> _obs_processor.observe(batch)
        -> converted = _obs_processor.current()
        -> _get_lang_embed(converted.task)
        -> _predict_guided(...) if use_guidance else _predict_unguided(...)
           -> _rdt_model.encode_inputs(...)
           -> x_t = torch.randn(B, 64, 128)
           -> _guided_denoise_loop(...)
              -> diversity guidance on early scheduler timesteps
              -> keypoint gradient guidance on later scheduler timesteps
              -> optional FKD particle resampling
              -> best-particle selection
              -> visualization candidate ordering/cache
        -> _postprocess_actions(raw)
  -> optional adapter.env_postprocessor(action_chunk)
  -> adapter.step(action_chunk[0][action_executed])
```

`main.py` 中 VLS 相关传参集中在 `Main._run_episode`：`keypoints` 来自 `KeypointTracker`，`guidance_fns` 来自每个 stage 的 VLM 生成函数，`guide_scale` 可以被 adapter 的 `recommended_guide_scale` 覆盖，`sigmoid_k/sigmoid_x0/start_ratio/use_diversity/diversity_scale/use_fkd/fkd_config` 来自 `cfg.main`。`global_step` 和 `current_stage` 也传入 RDT，但当前 RDT loop 内没有实际使用它们。

RDT 与另外两个 policy 的一个重要差异是：`main.py` 对 `policy.type == "rdt"` 设置 identity pre/postprocessor，RDT 自己负责 observation 转换和 action decode。也就是说，RDT guidance 里的 `x_t` 不是 LeRobot 7D action tensor，而是 RDT 统一 128D action/state 空间中的 action trajectory。

## 2. `_guided_denoise_loop` 的整体算法流程

`core/rdt_policy_steer.py:_guided_denoise_loop` 的输入是已经初始化好的 noisy action samples `x_t` 和 RDT conditioning dict `cond`。它先设置 RDT inference scheduler timesteps，计算 guidance 切换点 `start_step`，按需初始化 FKD，然后遍历每个 scheduler timestep：

1. 用 RDT DiT 预测 `model_output = self._dit(x_t, t, cond)`。
2. 如果还处于早期 denoising 阶段，并且 diversity guidance 开启，则计算粒子间 inverse-distance potential 的梯度，修改 `model_output` 中 3D translation 对应的 RDT slots。
3. 否则如果进入 keypoint guidance 阶段，并且 keypoints 和 guidance functions 可用，则把当前 RDT samples 转成 3D EEF trajectories，计算 reward，对 `x_t` 反传得到归一化梯度，结合 adaptive scale 修改 `model_output`。
4. 调用 scheduler `step(model_output, t, x_t)` 得到下一步 `x_t = prev_sample`。
5. 如果 FKD 可用且当前 timestep 位于 keypoint guidance 区间，则用 reward function 对粒子重采样；若粒子发生替换，则重置 DPMSolver 多步 scheduler 的历史状态。
6. 采样结束后，如果这是当前 stage 的第一个 guided chunk，则记录 stage reward baseline。
7. 检查 `x_t` finite。
8. 从最终 particles 中选择一个执行粒子，并缓存排序后的 visualization candidates。

伪代码：

```python
scheduler = self._noise_scheduler
scheduler.set_timesteps(self._num_inference_steps)
start_step = _resolve_start_step(scheduler.timesteps, start_ratio)
use_keypoint_guidance = guidance_fns and keypoints is not None
fkd = _init_fkd(...) if use_fkd else None

for i, t in enumerate(scheduler.timesteps):
    with torch.no_grad():
        model_output = self._dit(x_t, t, cond)

    if use_diversity and t > start_step and B > 1:
        div_grad = _compute_diversity_gradient(x_t)
        model_output[..., translation_slots] += -diversity_scale * masked(div_grad)

    elif use_keypoint_guidance and t <= start_step:
        kp_grad, reward = _compute_keypoint_gradient(x_t, keypoints, guidance_fns)
        normalized_reward = _normalized_reward_from_value(reward)
        scale = _adaptive_scale_for_scheduler_t(...)
        model_output = _apply_keypoint_guidance(model_output, kp_grad, scale)

    step_output = scheduler.step(model_output, t, x_t)
    x0_for_reward = step_output.pred_original_sample or model_output
    x_t = step_output.prev_sample

    if fkd and t <= start_step and t != terminal_t:
        x_t, _ = fkd.resample(sampling_idx=t, latents=x_t, x0_preds=x0_for_reward)
        if resampled:
            _reset_scheduler_particle_history_after_resample(scheduler)

selected = _select_particle_for_execution(x_t, ...)
_last_visualization_action_candidates = decode(order_particles(x_t, ...))
return selected
```

## 3. 输入参数逐项解释

### `select_action(...)`

`core/rdt_policy_steer.py:RDTSteer.select_action` 是主程序调用入口。

| 参数 | 来源 | 类型 | 实际作用 |
| --- | --- | --- | --- |
| `batch` | `main.py:Main._get_policy_observation()` | `dict` | RDT observation processor 的输入；RDT 分支不走 LeRobot policy preprocessor。 |
| `generate_new_chunk` | `main.py` 中 `action_executed == 0` | `bool` | 决定是否重新采样 action chunk；否则返回缓存 chunk。 |
| `use_guidance` | stage state + `cfg.main.use_guidance` | `bool` | 为 true 时进入 `_predict_guided`；false 时走 `_predict_unguided(B=1)`。 |
| `keypoints` | `KeypointTracker.get_keypoint_positions()` | `np.ndarray` 或 `None`, shape `(K,3)` | 当前世界坐标 keypoints；转成 tensor 后用于 guidance reward。 |
| `guidance_fns` | `self.guidance_fns[current_stage]` | `list[Callable]` 或 `None` | VLM 生成并加载的 reward 函数列表，签名通常为 `fn(keypoints, trajectory)`。 |
| `guide_scale` | `self.current_guide_scale` 或 `cfg.main.guide_scale` | `float` | keypoint gradient guidance 的基础强度。 |
| `sigmoid_k` | `cfg.main.sigmoid_k` | `float` | adaptive scale sigmoid 的斜率。 |
| `sigmoid_x0` | `cfg.main.sigmoid_x0` | `float` | normalized reward 达到该值时 sigmoid strength 约为 0.5。 |
| `start_ratio` | `cfg.main.start_ratio` | `float` 或 `None` | 转成 scheduler timestep index，决定 diversity -> keypoint guidance 的切换点。 |
| `use_diversity` | `cfg.main.use_diversity` | `bool` | 控制早期粒子分散 guidance。 |
| `diversity_scale` | `cfg.main.diversity_scale` | `float` | diversity gradient 加到 `model_output` 的倍率。 |
| `MCMC_steps` | `cfg.main.MCMC_steps` | `int` | 当前 RDT 代码只透传，不参与任何计算。 |
| `verbose` | `main.py` 固定传 `True` | `bool` | 触发 `_predict_guided` 初始日志和 keypoint reward 简短日志。 |
| `use_fkd` | `cfg.main.use_fkd` | `bool` | 控制是否把 `fkd_config` 传给 `_init_fkd`。 |
| `fkd_config` | `cfg.main.fkd` | `dict` 或 `None` | FKD 的 potential/resampling 参数。 |
| `global_step` | `main.py` rollout step counter | `int` | 当前 RDT 中未实际使用；diffusion/pi05 主要用于日志。 |
| `current_stage` | stage recognizer / stage state | `int` | 当前 RDT 中未实际使用；stage 只通过 `guidance_fns` 间接影响 reward。 |

`select_action` 每次都会调用 `_obs_processor.observe(batch)` 更新 RDT observation buffer。只有在 `generate_new_chunk`、缓存为空或缓存剩余步数为 0 时才重新采样。重新采样后，返回值仍是整个 cached chunk；`main.py` 用 `action_executed` 在 chunk 内取单步动作。

### `_predict_guided(...)`

`_predict_guided` 是 `_guided_denoise_loop` 的直接调用者，负责把 policy observation 编码成 RDT 条件、初始化 particles，并把 numpy keypoints 转成 torch tensor。

| 参数 | 来源/类型 | 含义 |
| --- | --- | --- |
| `state_128` | `converted.state_128`, `Tensor (1,128)` | LIBERO robot state 投入 RDT 统一 128D state/action 空间后的状态。 |
| `state_mask_128` | `converted.state_mask_128`, `Tensor (1,128)` | 128D state 中有效 LIBERO state slots 的 mask。 |
| `images` | `converted.images`, `list[PIL.Image or None]` | RDT 需要的多相机图像历史。 |
| `text_embed` | `_get_lang_embed(converted.task)`, `Tensor` | RDT text encoder 得到的 instruction embedding。 |
| 其余 guidance 参数 | 从 `select_action` 原样传入 | 继续传给 `_guided_denoise_loop`。 |

内部关键变量：

- `device/dtype`: 从 `self._dit.parameters()` 推断；若模型无参数则 fallback 到 `float32`。
- `cond`: `_rdt_model.encode_inputs(...)` 返回的 conditioning dict。真实 RDT 中包含 `lang_cond`、`lang_attn_mask`、`img_cond`、`state_traj`、`action_mask`、`ctrl_freqs`、`action_indices`、`unified_action_dim`。
- `unified_action_dim`: 必须为 `128`，否则直接报错。
- `B`: `max(1, int(self._sample_batch_size))`。`main.py` 通过 `policy.post_init(... sample_batch_size=cfg.main.sample_batch_size ...)` 设置。只有 guided 路径使用多粒子；unguided 路径固定 `B=1`。
- `pred_horizon`: 固定为 `64`，对应 RDT 的 full prediction horizon。
- `x_t`: 初始 Gaussian noisy action samples，shape `(B,64,128)`。
- `keypoints_tensor`: `keypoints` 非空时转成 `device/dtype` 一致的 tensor。
- `guided`: `_guided_denoise_loop` 返回的 selected sample，shape 通常为 `(1,64,128)`。
- `action_mask`: `cond["action_mask"]` 扩展后乘到 `guided` 上，保证只保留 LIBERO active action slots。

### `_guided_denoise_loop(...)`

`_guided_denoise_loop` 只接收 `_predict_guided` 已经准备好的 tensors 和参数。

| 参数 | 类型/形状 | 含义与作用 |
| --- | --- | --- |
| `x_t` | `Tensor (B,64,128)` | 当前 diffusion latent / noisy action trajectory；batch 维就是 particles。 |
| `cond` | `dict[str, Tensor/list/int]` | RDT DiT 条件；由 `_RDTModelAdapter.encode_inputs` 预先计算。 |
| `keypoints` | `Tensor (K,3)` 或 `None` | guidance reward 的 keypoint world positions。 |
| `guidance_fns` | `list[Callable]` 或 `None` | 对 trajectory 打分的 VLM-generated reward functions。 |
| `guide_scale` | `float` | keypoint gradient 基础倍率。 |
| `sigmoid_k` | `float` | adaptive scale sigmoid 斜率。 |
| `sigmoid_x0` | `float` | adaptive scale sigmoid 中心。 |
| `start_ratio` | `float` 或 `None` | 通过 `_resolve_start_step` 映射为 scheduler timestep value。 |
| `use_diversity` | `bool` | 早期是否执行 diversity guidance。 |
| `diversity_scale` | `float` | diversity gradient 对 `model_output` 的倍率。 |
| `MCMC_steps` | `int` | 当前未使用。 |
| `verbose` | `bool` | 只影响少量日志。 |
| `use_fkd` | `bool` | 控制 `_init_fkd` 是否收到 config。 |
| `fkd_config` | `dict` 或 `None` | FKD 参数，见 FKD 章节。 |
| `global_step` | `int` | 当前未使用。 |
| `current_stage` | `int` | 当前未使用。 |

## 4. 核心数据结构与张量形状

RDT 使用统一 128D action/state 空间。LIBERO action 的有效 slots 来自 `core/rdt_libero_action_converter.py`：

```python
LIBERO_ACTION_INDICES = [39, 40, 41, 42, 43, 44, 10]
```

`core/rdt_policy_steer.py` 中 guidance 相关常量：

```python
RDT_GUIDED_TRANSLATION_INDICES = [39, 40, 41]
RDT_GUIDED_ACTION_INDICES = [39, 40, 41, 42, 43, 44, 10]
RDT_GUIDANCE_SIGN = 1.0
RDT_DIVERSITY_SIGN = -1.0
```

含义：

- `[39,40,41]` 对应 LIBERO raw action 的 translation `dx,dy,dz`。
- `[42,43,44]` 对应 orientation action slots。
- `[10]` 对应 gripper slot。
- guidance gradient 最终只写回 translation slots `[39,40,41]`，不会直接修改旋转或 gripper。

`cond` 的字段语义：

| 字段 | 来源 | 形状/类型 | 用途 |
| --- | --- | --- | --- |
| `lang_cond` | `real.policy.adapt_conditions(...)` | RDT hidden tensor | DiT language condition。 |
| `lang_attn_mask` | text embedding length | bool tensor | DiT language mask。 |
| `img_cond` | SigLIP / RDT vision encoding | RDT hidden tensor | DiT image condition。 |
| `state_traj` | 128D state + action mask 经 state adaptor | tensor | 当前 observation state token。 |
| `action_mask` | LIBERO action slots mask | `(1,1,128)` | 告诉 RDT 哪些 action dim 有效；最终也用于 mask output。 |
| `ctrl_freqs` | RDT control frequency | `(1,)` tensor | 传入 RDT DiT。 |
| `action_indices` | `LIBERO_RDT_INDICES` | `list[int]` | 兼容 raw action dim < 128 的 lift/projection 分支。 |
| `unified_action_dim` | model config | `int`, 必须为 `128` | RDT action/state 维度校验。 |

`_RDTDiTAdapter.forward` 会把 batch=1 的 conditioning tensors expand 到 `B` 个 particles，然后构造 `action_traj = concat([x_unified, action_mask_full], dim=2)`，经 RDT `state_adaptor` 后与 `state_traj` 拼接，再调用 RDT DiT model。当前 `_predict_guided` 传入的 `x_t` 已经是 `(B,64,128)`，所以 adapter 不需要从低维 action lift 到 128D。

RDT scheduler 相关：

- `third_party/rdt/models/rdt_runner.py` 中 inference scheduler 是 `DPMSolverMultistepScheduler`。
- `third_party/rdt/configs/base.yaml` 的默认 `prediction_type: sample`。
- RDT 原始 `conditional_sample` 也是循环 `model_output = self.model(...)` 然后 `noise_scheduler_sample.step(model_output, t, noisy_action).prev_sample`。

因此，当前 RDT steering 是在 `prediction_type="sample"` 的 `model_output` 上注入梯度，而不是 diffusion policy 常见的 epsilon prediction 上注入。

## 5. denoising loop 分阶段执行逻辑

### 5.1 初始化阶段

`_guided_denoise_loop` 开始时执行：

```python
scheduler = self._noise_scheduler
scheduler.set_timesteps(self._num_inference_steps)
use_keypoint_guidance = guidance_fns is not None and len(guidance_fns) > 0 and keypoints is not None
reward_history = []
start_step = self._resolve_start_step(scheduler.timesteps, start_ratio)
terminal_t = int(scheduler.timesteps[-1].item())
fkd = self._init_fkd(... fkd_config=fkd_config if use_fkd else None ...)
```

`start_step` 是 scheduler timestep value，不是 loop index。若 `start_ratio is None`，当前实现取 `timesteps[len(timesteps)//3]`。由于 diffusion scheduler timesteps 通常从大到小，默认行为是：约前 1/3 个 denoising steps 使用 diversity guidance，后约 2/3 个 steps 使用 keypoint guidance。

若显式传 `start_ratio`，实现是：

```python
idx = int(len(timesteps) * float(start_ratio))
idx = clamp(idx, 0, len(timesteps)-1)
start_step = int(timesteps[idx].item())
```

所以 `start_ratio` 表示 timestep list 的 index fraction，不是数值 timestep 百分比，也不是 `main` 配置里旧的 `start_step`。当前 `main.py` 读取的是 `cfg.main.start_ratio`，不是一些 ablation config 里的 `start_step`。

### 5.2 每个 scheduler step

每轮先在 `torch.no_grad()` 下运行模型：

```python
model_output = self._dit(x_t, t, cond)
```

随后进入互斥的 `if / elif`：

- `if use_diversity and t > start_step and B > 1`: 早期 diversity guidance。
- `elif use_keypoint_guidance and t <= start_step`: 后期 keypoint guidance。
- 如果 early 阶段 diversity 关闭，则不会在同一 early step fallback 到 keypoint guidance，因为 keypoint 条件要求 `t <= start_step`。

接着总是执行 scheduler step：

```python
step_output = scheduler.step(model_output, t, x_t)
x0_for_reward = step_output.pred_original_sample if exists else model_output
x_t = step_output.prev_sample.to(dtype=model_output.dtype)
```

最后在 keypoint guidance 区间中按需 FKD resampling：

```python
if fkd is not None and t <= start_step and t != terminal_t:
    x_t, _ = fkd.resample(sampling_idx=t, latents=x_t, x0_preds=x0_for_reward)
```

## 6. Diversity guidance 机制

Diversity guidance 的启用条件：

```python
use_diversity is True
and int(t.item()) > start_step
and x_t.shape[0] > 1
```

此外，`_compute_diversity_gradient` 内部还要求 `self._adapter is not None`。如果 batch/particle 数量小于 2 或 adapter 不存在，则返回 `None`。

计算过程在 `core/rdt_policy_steer.py:_compute_diversity_gradient`：

1. `x_grad = x_t.detach().requires_grad_(True)`，切断旧图，只对当前 sample 建图。
2. 对每个 particle 调用 `_rdt_sample_to_trajectory_3d(x_grad[b:b+1])`。
3. `_rdt_sample_to_trajectory_3d` 先通过 `_decode_rdt_actions_for_guidance` 取 `sample[:, :H, RDT_GUIDED_ACTION_INDICES]`，得到 shape `(B,H,7)` 的 LIBERO raw action slots。
4. 调用 `adapter.delta_actions_to_ee_trajectory(actions[b])` 得到 `(H+1,3)` EEF trajectory。LIBERO adapter 当前只使用 `action[:3]`，乘 `ACTION_SCALE_POS = 0.01` 后累积成 world-frame trajectory。
5. diversity 使用 `trajs[:, 1:, :3]`，即跳过当前 EEF start point，保留 H 个未来轨迹点。
6. flatten 成 `(B,H*3)`，计算所有 particle pair 的 squared distance。
7. 计算 inverse-distance potential：

```python
dist = sqrt(sq_dist + 1e-6)
inv_dist = (1.0 / (dist + 1e-6)) * off_diagonal_mask
potential = inv_dist.sum()
```

8. 对 `potential` 关于 `x_grad` 求梯度，并按全局 norm 归一化。

写回 `model_output` 的逻辑：

```python
masked_div = _mask_guidance_gradient(div_grad)
model_output[:, :, [39,40,41]] += (
    RDT_DIVERSITY_SIGN * diversity_scale * masked_div[:, :, [39,40,41]]
)
```

由于 `RDT_DIVERSITY_SIGN = -1.0`，代码是在 `model_output` 上沿 inverse-distance potential 的负梯度方向调整，从而倾向于降低粒子之间的 inverse-distance potential，即拉开 particles。`_mask_guidance_gradient` 只保留前 `H = self._action_chunk_horizon` 步的 translation slots，其余全部置零。

实际影响动作生成的条件是：`use_guidance=True` 使 RDT 走 `_predict_guided`，`sample_batch_size > 1`，`use_diversity=True`，当前 timestep 处于 `t > start_step`，且 adapter 的 trajectory conversion 可微。若 `diversity_scale=0.0`，当前代码仍会计算 diversity gradient，但写回增量为 0，这是一个性能冗余。

## 7. Keypoint guidance 机制

Keypoint guidance 的启用条件：

```python
guidance_fns is not None
and len(guidance_fns) > 0
and keypoints is not None
and int(t.item()) <= start_step
```

`_compute_keypoint_gradient` 还要求 `self._adapter is not None`，并且 reward 必须是带梯度的 torch Tensor；如果 reward 是 Python number 或不需要梯度的 tensor，则返回 `(None, reward_value)`，不会修改 `model_output`。

计算链路：

```text
x_t (B,64,128)
  -> x_grad = x_t.detach().requires_grad_(True)
  -> _rdt_sample_to_trajectory_3d(x_grad)
     -> _decode_rdt_actions_for_guidance(sample[:, :H, [39,40,41,42,43,44,10]])
     -> adapter.delta_actions_to_ee_trajectory(action_sequence)
  -> traj_input = trajs[:, :H, :3]
  -> reward = sum(fn(keypoints, traj_input) for fn in guidance_fns)
  -> grad = autograd.grad(reward.sum(), x_grad)
  -> normalized_grad = grad / (norm(grad) + 1e-8)
```

`_rdt_sample_to_trajectory_3d` 是 RDT action sample 到 3D EEF trajectory 的关键桥：

- 输入必须是 `(B,64,128)`。
- 只取前 `self._action_chunk_horizon` 步和 `RDT_GUIDED_ACTION_INDICES` 七个 action slots。
- 不调用 `rdt_action_to_libero_raw` 的 gripper 二值化；但 trajectory conversion 只使用 action 前三维 translation，所以 gripper 对 keypoint/diversity gradient 没有直接影响。
- LIBERO adapter 的 `delta_actions_to_ee_trajectory` 将 `(T,7)` action sequence 的 `action[:, :3]` 乘 `0.01` 米并累积到当前 EEF world position，返回 `(T+1,3)`。

reward 计算有两个路径：

- `_compute_keypoint_gradient`: 一次性把所有 particles 的 `traj_input` 传给每个 guidance function，得到整体 reward，再对所有 particles 的 `x_t` 求联合梯度。
- `_score_particles`: 逐 particle 调用 reward，用于 FKD 和最终 selection，返回 shape `(B,)` 的 reward tensor。

这意味着 gradient guidance 与 particle scoring 的 batch 语义不完全相同。如果 VLM guidance function 内部对 batch 维做 sum/mean，这通常可工作；但如果函数假设 batch size 为 1，`_compute_keypoint_gradient` 可能和 `_score_particles` 行为不同。

写回 `model_output`：

```python
scale = _adaptive_scale_for_scheduler_t(...)
model_output = _apply_keypoint_guidance(model_output, kp_grad, scale)
```

`_apply_keypoint_guidance` clone 一份 `model_output`，只在 `[:H, [39,40,41]]` 上加：

```python
guided_translation += RDT_GUIDANCE_SIGN * scale * normalized_kp_grad_translation
```

当前 `RDT_GUIDANCE_SIGN = 1.0`。这与 `diffusion_policy_steer.py` / `pi05_steer.py` 中常见的 `model_output -= scale * grad` 不同，原因是 RDT scheduler 配置为 `prediction_type: sample`，而 diffusion policy 常见路径是 epsilon prediction，PI0.5 是 flow velocity prediction。也就是说，符号差异来自被修改量的语义不同。

## 8. Adaptive scale 机制

Adaptive scale 由两部分相乘：

```python
strength = 1 / (1 + exp(sigmoid_k * (last_normalized_reward - sigmoid_x0)))
scale = guide_scale * strength * sqrt(clamp(1 - alpha_t, min=0))
```

变量来源：

- `guide_scale`: `main.py` 从 `current_guide_scale` 或 `cfg.main.guide_scale` 取值。`current_guide_scale` 可被 adapter task info 的 `recommended_guide_scale` 覆盖。
- `sigmoid_k`: `cfg.main.sigmoid_k`。
- `sigmoid_x0`: `cfg.main.sigmoid_x0`。
- `last_normalized_reward`: 由 `_normalized_reward_from_value(reward_value)` 或 `_compute_keypoint_gradient` 内部更新。
- `alpha_t`: 若 scheduler 有 `alphas_cumprod`，用 `scheduler.alphas_cumprod[int(t.item())]`；否则使用 `self._current_alpha_t`。当前 `self._current_alpha_t` 初始化为 `0.5`，没有看到在 RDT 代码中动态更新，所以只有在 scheduler 缺少 `alphas_cumprod` 时才会退化为固定 fallback。

normalized reward 计算：

```python
if self._stage_init_reward is not None and self._stage_init_reward < -1e-6:
    normalized_reward = 1.0 - reward_value / self._stage_init_reward
    normalized_reward = clamp(normalized_reward, 0.0, 1.2)
else:
    normalized_reward = 0.0
```

这隐含假设：guidance reward 是负的 cost-style reward，越接近 0 越好。例如初始 reward 为 `-10`，当前 reward 为 `-2` 时，`1 - (-2 / -10) = 0.8`。如果 VLM guidance function 返回正 reward 或初始 reward 接近 0，normalized reward 会一直是 0，sigmoid gate 不会根据进度衰减。

stage baseline 的建立：

- 第一个 guided chunk 中，`_stage_init_reward` 通常是 `None`，所以所有 normalized reward 都按 0 处理。
- loop 结束后，如果 `reward_history` 非空且 `_stage_init_reward is None`，取 `reward_history[-1][1]` 作为当前 stage baseline。
- `reset_stage()` 会把 `_stage_init_reward` 置为 `None`，供新 stage 重新建立 baseline。

`reward_history` 当前只用于设置 baseline，没有用于外部日志或其他控制。`self._last_scale` 用于 `main.py` 的 status overlay；`self._last_normalized_reward` 同时影响 stage trigger 和 status overlay。

## 9. FKD resampling 机制

### 9.1 `FKD.__init__` semantic map

`core/fkd_class.py:FKD.__init__` 做的是：保存重采样配置，初始化每个 particle 的历史 reward 状态，并预先算好哪些 scheduler timestep 会触发 FKD resampling。

```text
FKD.__init__(...)
  -> 保存配置参数
     potential_type / lmbda / num_particles / adaptive_resampling
     resample_frequency / resampling_t_start / resampling_t_end
     reward_fn / device

  -> 初始化 particle 历史状态
     population_rs
       每个 particle 的历史 reward 统计，语义随 potential_type 改变
     product_of_potentials
       terminal Feynman-Kac correction 用
     _last_idx_sampled = -1
       检查 resample() 调用顺序
     _reached_terminal_sample = False
       标记 FKD.resample() 是否走到最后一个 scheduler timestep

  -> 处理 scheduler timesteps
     timesteps = list[int]
     time_steps = len(timesteps)
     t_to_index = {timestep_value: loop_index}

  -> 构造 resampling_interval
     用 resampling_t_start / resampling_t_end 找到 index 区间
     按 resample_frequency 取子序列
     映射回具体 timestep value
     强制加入 terminal timestep
```

关键状态：

```python
self.population_rs = torch.ones(self.num_particles, device=self.device) * reward_min_value
self.product_of_potentials = torch.ones(self.num_particles).to(self.device)
self._last_idx_sampled = -1
self._reached_terminal_sample = False
```

`population_rs` 是每个 particle 的历史 reward 统计。`potential_type="max"` 时，它表示历史最大 reward；`"add"` 时，它表示累积 reward；`"diff"` 时，它相当于上一次 reward；`"rt"` 基本只看当前 reward。

`resampling_interval` 的元素是具体 scheduler timestep 值，不是 loop index。例如：

```python
timesteps = [999, 799, 599, 399, 199, 0]
resampling_t_start = 599
resampling_t_end = 0
resample_frequency = 2
```

对应的触发集合可能是：

```python
resampling_interval = [599, 199, 0]
```

调用方后续传给 `FKD.resample(sampling_idx=...)` 的 `sampling_idx` 必须能在 `t_to_index` 中找到，否则 FKD 会直接跳过。

### 9.2 `FKD.resample()` semantic map

`core/fkd_class.py:FKD.resample` 是核心算法入口。它输入当前 noisy particles `latents` 和用于打分的 `x0_preds`，在指定 timestep 上按 reward 权重重采样 particle population。

```text
FKD.resample(sampling_idx, latents, x0_preds)
  -> 解析当前 timestep
     sampling_t = int(sampling_idx)
     current_idx = t_to_index.get(sampling_t)

  -> 合法性检查
     unknown timestep: return latents, None
     current_idx <= _last_idx_sampled: raise ValueError
     更新 _last_idx_sampled

  -> terminal 判断
     at_terminal_sample = current_idx == time_steps - 1
     _reached_terminal_sample = at_terminal_sample

  -> 是否触发 resampling
     if sampling_t not in resampling_interval:
       return latents, None

  -> reward_fn 打分
     rs_candidates = reward_fn(x0_preds)
     shape 应为 (num_particles,)

  -> 根据 potential_type 计算权重
     MAX:  exp(lmbda * max(current_reward, history_reward))
     ADD:  exp(lmbda * (current_reward + history_reward))
     DIFF: exp(lmbda * (current_reward - history_reward))
     RT:   exp(lmbda * current_reward)

  -> 数值稳定处理
     clamp 到 [0, 1e10]
     NaN 置 0
     如果全 0，退回 uniform weights

  -> adaptive resampling
     计算 ESS = 1 / sum(normalized_w ** 2)
     若 ESS >= 0.5 * num_particles 且不是 terminal:
       不重采样，只更新 population_rs

  -> multinomial resampling
     indices = torch.multinomial(w, num_particles, replacement=True)
     latents = latents[indices]
     x0_preds = x0_preds[indices]
     population_rs = rs_candidates[indices]
     product_of_potentials = product_of_potentials[indices] * w[indices]

  -> terminal sorting
     若 at_terminal_sample:
       按 population_rs 降序排序，保证 index 0 是最高 reward particle

  -> return resampled_xt, resampled_x0
```

核心伪代码：

```python
def resample(sampling_idx, latents, x0_preds):
    t = int(sampling_idx)
    idx = t_to_index.get(t)
    if idx is None:
        return latents, None
    if idx <= last_idx_sampled:
        raise ValueError

    at_terminal = idx == len(timesteps) - 1
    reached_terminal = at_terminal
    if t not in resampling_interval:
        return latents, None

    rewards = reward_fn(x0_preds)
    potential = make_potential(rewards, population_rs, potential_type)
    weights = exp(lmbda * potential)
    weights = stabilize(weights)

    if adaptive_resampling:
        ess = 1 / sum((weights / weights.sum()) ** 2)
        if ess >= 0.5 * num_particles and not at_terminal:
            population_rs = potential
            return latents, x0_preds

    indices = multinomial(weights, num_particles, replacement=True)
    latents = latents[indices]
    x0_preds = x0_preds[indices]
    population_rs = potential[indices]

    if at_terminal:
        sort particles by population_rs descending

    return latents, x0_preds
```

`adaptive_resampling=True` 时，FKD 不会在每个 `resampling_interval` timestep 都强制复制粒子。它先算 ESS，有效粒子数仍然足够大时只更新历史 reward，不改 `latents`。这能减少不必要的 particle degeneracy。

`potential_type` 的语义：

| 类型 | 公式 | 语义 |
| --- | --- | --- |
| `MAX` | `max(current_reward, history_reward)` | 保留历史最好表现，适合“曾经出现好轨迹就尽量保留”。 |
| `ADD` | `current_reward + history_reward` | 累积整个采样过程的 reward。 |
| `DIFF` | `current_reward - history_reward` | 奖励相对上次变好的 particle。 |
| `RT` | `current_reward` | 只看当前 reward。 |

数值上要注意：`w = exp(lmbda * potential)` 对 reward 尺度非常敏感。`lmbda=10` 时，正 reward 稍大就会使权重急剧集中；负 reward 很大时权重可能接近 0。当前实现用 clamp、NaN 清零和全 0 fallback 做了基础保护。

`reached_terminal` 不是“FKD 对象已经初始化到 terminal”，而是“`FKD.resample()` 这次是否被调用到了 scheduler 的最后一个 timestep”。它只在 `resample()` 内部更新：

```python
at_terminal_sample = current_idx == (self.time_steps - 1)
self._reached_terminal_sample = at_terminal_sample
```

如果调用方跳过 terminal timestep，`fkd.reached_terminal` 就不会变成 `True`。

### 9.3 RDT 中的 FKD 初始化条件

`_init_fkd` 返回非空 FKD 的条件：

```python
fkd_config is not None
and B > 1
and keypoints is not None
and guidance_fns is not empty
```

外层还要求 `use_fkd=True`，因为 `_guided_denoise_loop` 传入的是：

```python
fkd_config=fkd_config if use_fkd else None
```

FKD 参数：

| FKD 参数 | 来源 | 默认值 |
| --- | --- | --- |
| `potential_type` | `fkd_config["potential_type"]` | `"max"` |
| `lmbda` | `fkd_config["lmbda"]` | `10.0` |
| `num_particles` | `B` | 当前 sample batch size |
| `adaptive_resampling` | `fkd_config["adaptive_resampling"]` | `True` |
| `resample_frequency` | `fkd_config["resample_frequency"]` | `5` |
| `resampling_t_start` | `start_step` | guidance 切换 timestep |
| `resampling_t_end` | `timesteps[-1]` | terminal timestep |
| `timesteps` | scheduler timesteps | RDT DPMSolver timesteps |
| `reward_fn` | `_score_particles(... slice_kind="fkd")` | 每粒子 keypoint reward |
| `reward_min_value` | constant | `-inf` |

RDT 里默认 `reward_min_value=float("-inf")`。这对 `potential_type="max"` 是合理的，因为第一次 reward 会替换 `-inf`；如果后续改用 `ADD` 或 `DIFF`，需要重新检查 `-inf` 初始化是否会造成权重退化或爆炸。

### 9.4 Reward function

FKD reward function 是：

```python
def reward_fn(x0_preds):
    return self._score_particles(x0_preds, keypoints, guidance_fns, slice_kind="fkd")
```

`_score_particles` 会把 `x0_preds` 转成 3D EEF trajectories，然后根据 `slice_kind="fkd"` 取：

```python
trajs[:, 1:self._action_chunk_horizon, :3]
```

注意这个 slice 跳过了 start point，也排除了 index `H` 的最后一个未来点，因此长度是 `H-1`。这与 diversity 的 `trajs[:, 1:, :3]` 和 keypoint gradient 的 `trajs[:, :H, :3]` 不完全一致。

### 9.5 RDT 中的 resampling 时机

RDT loop 在 scheduler step 后执行 FKD：

```python
if fkd is not None and t <= start_step and t != terminal_t:
    before_resample = x_t
    x_t, _ = fkd.resample(sampling_idx=t, latents=x_t, x0_preds=x0_for_reward)
    if after is not before:
        _reset_scheduler_particle_history_after_resample(scheduler)
```

`x0_for_reward` 来自 `_select_fkd_x0_source`：

- 如果 scheduler step output 有 `pred_original_sample`，优先使用它；
- 否则使用 `model_output`。

在 RDT 默认 `prediction_type="sample"` 下，`model_output` 可被视为 predicted clean sample 的近似；若后续 RDT scheduler config 改成 epsilon/velocity 类型，这里会有 scoring 语义风险。

`core/fkd_class.py:FKD` 自身会根据 `resampling_interval` 决定是否真的重采样，并在 adaptive mode 下根据 ESS 决定是否跳过重采样。若重采样发生，`latents` 会按多项采样索引复制/丢弃 particles；若没有重采样，返回原 `xt` 对象。

RDT 在检测到返回对象不是原对象时调用 `_reset_scheduler_particle_history_after_resample`，清空 DPMSolver 的 `model_outputs` 历史并重置 `lower_order_nums`。这对多步 solver 很重要，因为粒子重采样会改变 batch 中每个 sample 的历史一致性。

### 9.6 对粒子选择的影响

FKD 有两种影响路径：

1. 采样过程中，重采样会直接改变后续 `x_t` 粒子群体，使高 reward 粒子被复制、低 reward 粒子被丢弃。
2. 如果 FKD 到达 terminal resampling，`FKD.resample` 会把 particles 按 reward 降序排序，使 `samples[0]` 是最高 reward。

当前 RDT loop 有一个值得注意的实现点：它显式跳过 `terminal_t` 的 FKD resampling：

```python
int(t.item()) != terminal_t
```

而 `FKD` 内部的 `reached_terminal` 只有在 `resample()` 被 terminal timestep 调用时才会置为 true。因此在当前 RDT 代码里，`fkd.reached_terminal` 分支很可能不会触发。RDT 最终仍会通过 `_select_particle_for_execution` 手动 `_score_particles` 并选择 argmax，所以执行粒子不完全依赖 FKD terminal sort；但 `FKD` 内置的 terminal correction/sort 可能被绕过。这与 `diffusion_policy_steer.py` 中 `t <= start_step` 就调用 FKD、没有跳过 terminal 的行为不同。

## 10. Particle selection 与 visualization candidates

### 执行粒子选择

`_guided_denoise_loop` 最终调用：

```python
selected = _select_particle_for_execution(x_t, keypoints, guidance_fns, fkd)
```

逻辑：

1. 如果 `B == 1`，直接返回全部 samples，即 shape `(1,64,128)`。
2. 如果 `fkd is not None and fkd.reached_terminal`，返回 `samples[0:1]`，假设 FKD 已经 terminal sort。
3. 否则调用 `_score_particles(samples, ..., slice_kind="fkd")`，取 reward 最大的 particle。

如果没有 keypoints 或 guidance functions，`_score_particles` 返回全 0，`torch.argmax` 会选择 index 0。因此纯 diversity guided 或误传空 guidance 的多粒子 RDT 最终执行第一个 particle。

`_predict_guided` 得到 `selected` 后，会乘上 `cond["action_mask"]`；`select_action` 随后用 `_postprocess_actions` 调用 `decode_rdt_libero_action_chunk`，只解码第一个 particle 的前 `H` 步，得到 `(1,H,7)` LIBERO raw action chunk。

### Visualization candidates

RDT 是三种 steer policy 中唯一实现 `get_last_visualization_action_candidates()` 的分支。`_guided_denoise_loop` 在返回前还会：

```python
ordered_candidates = _order_particles_for_visualization(x_t, ...)
_last_visualization_action_candidates = _decode_visualization_action_candidates(ordered_candidates)
```

排序逻辑：

- `B <= 1`: 原样 detach。
- `fkd.reached_terminal`: 原样 detach，假设 FKD 已经按 reward 排序。
- 否则用 `_score_particles(... slice_kind="fkd")` 找 best particle，并把 best 放到 batch index 0，其余保持原相对顺序。

`_decode_visualization_action_candidates` 要求输入 shape `(B,64,128)`，然后用 `rdt_action_to_libero_raw(actions[:, :H, :])` 解码所有 particles 的前 `H` 步成 `(B,H,7)`。这份缓存不是执行动作本身，而是给 `main.py:_get_visualization_action_chunk` 在 `debug_draw_trajectory=True` 时绘制候选轨迹使用。`main.py` 若发现 adapter 有 `env_postprocessor`，会对 candidates 再执行一次环境后处理，以匹配可视化坐标/动作语义。

## 11. Closed-loop execution control 与 stage switching

RDT 版本的 closed-loop execution control 和 stage switching 分布在两个层次：

- `core/rdt_policy_steer.py` 负责 policy 侧的 action chunk 缓存、按需重新采样、reward/stage baseline 状态暴露。
- `main.py` 负责真正的闭环环境执行、stage switching 触发、VLM stage recognizer 查询，以及为 RDT 选择当前 stage 的 guidance functions。

### 11.1 RDT policy 侧的 chunk-level closed loop

`core/rdt_policy_steer.py:RDTSteer.select_action` 是 RDT policy 的闭环入口。每次 `main.py` 有新 observation 后都会调用它；函数先执行：

```python
self._obs_processor.observe(batch)
```

这意味着 RDT observation buffer 每个 env step 都会接收最新 observation。但 RDT 不会每个 single action 都重新 denoise，它使用 action chunk 缓存：

```python
should_sample = (
    generate_new_chunk
    or self._cached_action_chunk is None
    or self._cached_action_steps_remaining <= 0
)
```

只有 chunk boundary、缓存为空或缓存执行完时，RDT 才重新规划一个 action chunk。否则直接返回旧的 `_cached_action_chunk`。重新采样后：

```python
self._cached_action_chunk = self._postprocess_actions(raw)
self._cached_action_steps_remaining = self._cached_action_chunk.shape[1]
```

每次调用都会递减：

```python
self._cached_action_steps_remaining = max(0, self._cached_action_steps_remaining - 1)
```

因此当前实现是 chunk-level closed loop：

```text
env step -> new observation -> select_action()
  -> 如果 action chunk 未用完: 返回缓存 chunk
  -> 如果 action chunk 用完: 用最新 observation/keypoints/stage 重新 denoise
```

`use_guidance` 决定新 chunk 的生成路径：

```python
if use_guidance:
    raw = self._predict_guided(...)
else:
    raw = self._predict_unguided(...)
```

当前 `current_stage` 虽然从 `main.py` 传到 `select_action`、`_predict_guided` 和 `_guided_denoise_loop`，但 RDT 内部没有读取它。stage 对 RDT 动作生成的实际影响来自 `guidance_fns=current_guidance_fns`，也就是 `main.py` 已经根据 `current_stage` 选好的 reward function 列表。

### 11.2 RDT 暴露给 stage switching 的状态接口

RDT 中和 stage switching 相关的状态在 `RDTSteer.__init__` 中初始化：

```python
self._last_normalized_reward = 0.0
self._last_scale = 0.0
self._stage_init_reward = None
self._last_raw_reward = 0.0
self._cached_action_steps_remaining = 0
```

`reset()` 用于 episode reset，清空 action cache 和 reward/stage 状态：

```python
self._cached_action_chunk = None
self._cached_action_steps_remaining = 0
self._stage_init_reward = None
self._last_normalized_reward = 0.0
self._last_scale = 0.0
self._last_raw_reward = 0.0
```

`reset_stage()` 只重置 stage baseline：

```python
def reset_stage(self) -> None:
    self._stage_init_reward = None
```

这个接口由 `main.py:_update_stage` 在 stage 改变时调用。它不会清空 action cache，也不会重置 `_last_normalized_reward`，只是让新 stage 的后续 guided chunk 重新建立 `_stage_init_reward` baseline。

RDT 给主循环读取的接口：

```python
def get_normalized_reward(self) -> float:
    return self._last_normalized_reward

def get_last_scale(self) -> float:
    return self._last_scale
```

`get_normalized_reward()` 是 stage trigger 的输入；`get_last_scale()` 主要用于 status overlay。

### 11.3 Normalized reward 与 stage baseline 如何产生

`_guided_denoise_loop` 中，keypoint guidance 生效时会调用：

```python
normalized_reward = self._normalized_reward_from_value(reward_value)
reward_history.append((i, reward_value, normalized_reward))
```

`_normalized_reward_from_value` 使用 `_stage_init_reward` 作为当前 stage baseline，假设 reward 是负数 cost-style reward：

```python
normalized_reward = 1.0 - (reward_value / self._stage_init_reward)
normalized_reward = max(0.0, min(1.2, normalized_reward))
```

如果当前 stage 还没有 baseline，normalized reward 先按 0 处理。denoising loop 结束后，如果本 chunk 有 reward history 且 `_stage_init_reward is None`：

```python
self._stage_init_reward = reward_history[-1][1]
```

这使得 stage 的第一个 guided chunk 负责建立 baseline；后续 chunks 的 normalized reward 才能表示“相对 stage 初始 reward 的进度”。

### 11.4 `main.py:_update_stage` semantic map

真正 stage switching 在 `main.py:_update_stage` 中完成。它不是直接生成动作，而是维护 `stage_state`：

```python
stage_state = {
    "prev_norm_reward": 0.0,
    "prev_gripper_open": None,
    "current_stage": current_stage,
    "use_guidance": use_guidance,
    "vlm_query_count": 0,
}
```

`_update_stage(state, gripper_val, upper_th, lower_th)` 的流程：

```text
_update_stage
  -> curr_reward = policy.get_normalized_reward()
  -> prev_reward = state["prev_norm_reward"]
  -> prev_gripper = state["prev_gripper_open"]

  -> 根据 gripper_val 判断当前 gripper 是否 open
     action[-1] < 0: open
     action[-1] >= 0: closed

  -> 检测 gripper transition
     gripper_just_closed
     gripper_just_opened

  -> 检测 normalized reward Schmitt trigger
     reward_rising:
       prev_reward < upper_th and curr_reward >= upper_th
     reward_falling:
       prev_reward > lower_th and curr_reward <= lower_th

  -> 按优先级构造 trigger_reason
     gripper closed
     gripper opened
     reward rose above upper threshold
     reward dropped below lower threshold

  -> 若触发且 VLM query 未超限:
     gemini_stage_recognizer.identify_stage_and_guidance(...)
       输入当前 VLM 图像、任务描述、stage descriptions、初始 keypoint 图、
       keypoint-object map、stage 数量和 trigger reason
     返回 new_stage, need_guidance

  -> 若 stage 改变:
     policy.reset_stage()
     curr_reward = 0.0

  -> 更新 state["current_stage"] 和 state["use_guidance"]
  -> 保存 state["prev_norm_reward"] 和 state["prev_gripper_open"]
  -> return state
```

Gripper trigger 的代码语义：

```python
curr_gripper_open = (gripper_val < 0) if gripper_val is not None else None
gripper_changed = (
    prev_gripper is not None
    and curr_gripper_open is not None
    and curr_gripper_open != prev_gripper
)
gripper_just_closed = gripper_changed and not curr_gripper_open
gripper_just_opened = gripper_changed and curr_gripper_open
```

Reward trigger 使用 Schmitt trigger：

```python
reward_rising = state["use_guidance"] and (prev_reward < upper_th and curr_reward >= upper_th)
reward_falling = state["use_guidance"] and (prev_reward > lower_th and curr_reward <= lower_th)
```

默认阈值来自 `cfg.main.schmitt_upper` 和 `cfg.main.schmitt_lower`，fallback 为 `0.8` 和 `0.6`。双阈值设计避免 normalized reward 在单一阈值附近抖动时反复触发 stage recognition。

触发优先级是 gripper 高于 reward：

```python
if gripper_just_closed:
    trigger_reason = "gripper closed"
elif gripper_just_opened:
    trigger_reason = "gripper opened"
elif reward_rising:
    trigger_reason = f"reward rose above {upper_th:.0%}"
elif reward_falling:
    trigger_reason = f"reward dropped below {lower_th:.0%}"
```

如果触发并且 `gemini_stage_recognizer` 可用，`main.py` 会查询 VLM：

```python
new_stage, need_guidance = self.gemini_stage_recognizer.identify_stage_and_guidance(...)
```

如果 VLM 认为 stage 改变：

```python
if new_stage != state["current_stage"]:
    self.policy.reset_stage()
    curr_reward = 0.0
```

对 RDT 来说，这会调用 `RDTSteer.reset_stage()`，让新 stage 重新建立 reward baseline。

### 11.5 `_run_episode` 中 stage switching 的调用时机

`main.py:_run_episode` 中只有在 action chunk boundary 才调用 `_update_stage`：

```python
generate_new_chunk = (action_executed == 0)

if generate_new_chunk and self.config.get("use_guidance", True) and hasattr(self, "guidance_fns"):
    keypoints = self.keypoint_tracker.get_keypoint_positions()
    mask_ids = self.keypoint_tracker.get_mask_ids()

    gripper_val = self._get_gripper_value(action_chunk, action_executed)
    stage_state = self._update_stage(stage_state, gripper_val, UPPER_THRESHOLD, LOWER_THRESHOLD)

    current_stage = stage_state["current_stage"]
    use_guidance = stage_state["use_guidance"]
    current_guidance_fns = self.guidance_fns.get(current_stage, []) if use_guidance else None
```

随后把状态传给 RDT：

```python
action_chunk = self.policy.select_action(
    observation,
    generate_new_chunk=generate_new_chunk,
    use_guidance=use_guidance,
    keypoints=keypoints,
    guidance_fns=current_guidance_fns,
    global_step=global_steps,
    current_stage=current_stage,
)
```

实际环境执行是逐 action 的：

```python
obs, reward, terminated, truncated, info = self.adapter.step(action_chunk[0][action_executed])
action_executed += 1
if action_executed == action_horizon:
    action_executed = 0
observation = self._get_policy_observation()
global_steps += 1
```

因此闭环结构是：

```text
每个 env step:
  执行 action_chunk[0][action_executed]
  读取新 observation
  action_executed += 1

每个 chunk boundary:
  刷新 tracked keypoints
  用 reward/gripper 触发 stage recognition
  根据 current_stage 选择 guidance_fns
  调用 RDT select_action 重新生成 chunk
```

### 11.6 当前实现风险

这部分有几个和 RDT guidance 相关的注意点：

1. `current_stage` 参数在 RDT 内部未使用。真正切换 guidance 的是 `main.py` 传入的 `current_guidance_fns`。
2. Stage switching 只在 chunk boundary 执行。如果中途 gripper 或 reward 已经变化，要等当前 action chunk 执行完才会触发识别。
3. `reset_stage()` 只清空 `_stage_init_reward`，不清空 cached action chunk。由于它在 chunk boundary 调用，随后通常会重新生成 chunk；如果调用时机改变，需要确认不会继续执行旧 stage chunk。
4. `main.py` 在 chunk boundary 调用 `_get_gripper_value(action_chunk, action_executed)`，而此时 `action_executed == 0`。如果 `action_chunk` 是上一轮刚执行完的 chunk，这里读到的是上一 chunk 的第 0 个 gripper，而不是最后执行的 gripper action。这可能影响 gripper-trigger stage recognition 的准确性。

一句话总结：RDT policy 提供 chunk-level action generation/cache 和 reward progress 状态；`main.py` 基于 gripper event 与 normalized reward Schmitt trigger 查询 VLM stage recognizer，再把当前 stage 对应的 `guidance_fns` 传回 RDT 生成下一段 guided action chunk。

## 12. 已实际影响动作生成的逻辑

当前确实会改变最终动作的逻辑：

- `use_guidance=True` 使 RDT 从 `_predict_unguided(B=1)` 切到 `_predict_guided(B=sample_batch_size)`。
- `guide_scale`、`sigmoid_k`、`sigmoid_x0`、scheduler `alpha_t`、`_last_normalized_reward` 共同决定 keypoint gradient 写入 `model_output` 的 scale。
- `start_ratio` 决定 diversity/keypoint guidance 切换时刻。
- `use_diversity` 和 `diversity_scale` 在 early timesteps 修改 translation slots 的 `model_output`。
- `guidance_fns` 和 `keypoints` 决定 keypoint reward、keypoint gradient、FKD reward、最终 particle selection。
- `use_fkd` 和 `fkd_config` 在 keypoint guidance 区间内改变 particle population。
- `sample_batch_size` 决定 particle 数量，影响 diversity、FKD 和 final selection。
- `action_chunk_horizon` 决定 guidance mask、trajectory conversion、decode 出来的执行 chunk 长度。
- `RDT_GUIDED_TRANSLATION_INDICES` / `RDT_GUIDED_ACTION_INDICES` 决定哪些 128D slots 被解释为 LIBERO action，哪些 slots 可被 gradient 修改。

## 13. 只用于日志、可视化或接口兼容的逻辑

只用于日志/状态展示：

- `verbose`: RDT 中只触发 `_predict_guided` 的初始 `[RDT_GUIDE]` 日志和 `_compute_keypoint_gradient` 的 `reward/norm_r` 简短日志。
- `self._last_scale`: 不直接反馈进 denoising loop；由 `_adaptive_scale_for_scheduler_t` 设置，供 `main.py` status overlay 展示。
- `self._last_normalized_reward`: 会影响后续 adaptive scale，也被 `main.py` 用于 stage trigger/status overlay；它既是算法状态也是日志状态。
- `self._last_raw_reward`: 当前只在 `_compute_keypoint_gradient` 中赋值，没有看到外部读取。

只用于可视化：

- `_last_visualization_action_candidates`
- `get_last_visualization_action_candidates`
- `_order_particles_for_visualization`
- `_decode_visualization_action_candidates`
- `main.py:_get_visualization_action_chunk`

接口兼容/当前未实际使用：

- `MCMC_steps`: RDT 接收并传入 `_guided_denoise_loop`，但没有任何读取。
- `global_step`: RDT 接收并传入 `_guided_denoise_loop`，但没有任何读取。diffusion/pi05 用它拼日志。
- `current_stage`: RDT 接收并传入 `_guided_denoise_loop`，但没有任何读取。stage 只通过 `guidance_fns` 的选择间接生效。
- `_adaptive_scale(self, reward, ...)`: 当前 RDT 没有调用；其中 `reward` 参数也没有被函数体使用。
- `slice_kind="diversity"` in `_trajectory_reward_slice`: 当前没有调用点；diversity 直接在 `_compute_diversity_gradient` 里取 `trajs[:,1:,:3]`。
- 配置里的旧字段 `main.start_step`: 当前 `main.py` 传的是 `start_ratio=self.config.get("start_ratio", None)`，不是 `start_step`。

## 14. 潜在 bug、冗余与实现风险

1. FKD terminal resampling 被跳过。RDT loop 条件 `t != terminal_t` 使 `FKD.reached_terminal` 很可能永远为 false，FKD 内部 terminal correction/sort 不生效。虽然 RDT 最终手动 `_score_particles` 选 best，但 FKD 的 terminal potential correction 被绕过，且 `_select_particle_for_execution` 的 `fkd.reached_terminal` 分支基本成为死分支。

2. Reward slice 不一致。keypoint gradient 用 `trajs[:, :H, :3]`，diversity 用 `trajs[:, 1:, :3]`，FKD/selection 用 `trajs[:, 1:H, :3]`。由于 `delta_actions_to_ee_trajectory` 返回 `(H+1,3)`，keypoint 包含 start point 但排除最后一个未来点；FKD 排除 start point 且长度是 `H-1`；diversity 使用 H 个未来点。这可能导致 gradient reward、FKD reward、final selection reward 对齐不完全。

3. `diversity_scale=0.0` 时仍会计算 diversity gradient。只要 `use_diversity=True` 且 `B>1`，early timesteps 会进入 `_compute_diversity_gradient`，即使最终乘 0。这对 ablation 或调参运行有不必要开销。

4. Adaptive reward normalization 假设 reward baseline 为负。若 VLM-generated guidance function 返回正 reward、或者初始 reward 接近 0，`_stage_init_reward < -1e-6` 条件不满足，`normalized_reward` 将保持 0，sigmoid gating 不会按任务进度衰减。

5. `_score_particles` 与 `_compute_keypoint_gradient` 的 batch 语义不同。前者逐 particle 调 guidance function，后者把整个 `(B,H,3)` trajectory batch 一次传给 guidance function。如果 guidance function 对 batch 维处理不明确，gradient 和 selection 可能评价不同目标。

6. FKD reward 的 `x0_for_reward` fallback 依赖 `prediction_type="sample"`。当前 RDT base config 是 sample prediction，所以 fallback 到 `model_output` 可以解释为 clean sample prediction。若后续 scheduler/model 改为 epsilon prediction，应同步改 `_select_fkd_x0_source` 或 reward decode，否则 FKD 会对噪声预测打分。

7. `global_step/current_stage` 在 RDT 中失去日志作用。与 diffusion/pi05 相比，RDT verbose 日志无法直接定位 rollout step/stage，调试多 stage guidance 时信息较少。

8. `_current_alpha_t` fallback 没有动态更新。如果 scheduler 没有 `alphas_cumprod`，scale 会固定使用初始化值 `0.5`。当前 DPMSolver scheduler 通常有 `alphas_cumprod`，但 fallback 语义不完整。

9. 纯 diversity 多粒子路径最终会选第一个 particle。如果 `use_guidance=True` 但 `guidance_fns/keypoints` 缺失，RDT 仍可能做 early diversity，后续没有 keypoint/FKD reward，最终 `_score_particles` 全 0，执行 index 0。

10. `start_ratio` 名义清楚但与 diffusion/pi05 不完全一致。RDT 的 ratio 是 timestep list index fraction；PI05 的 `start_ratio` 是 continuous flow time threshold；diffusion policy 的 `select_action` 在显式 ratio 时把 ratio 乘以 `num_inference_steps`，与 scheduler timestep value 的语义存在差异。

## 15. 与 `diffusion_policy_steer.py` / `pi05_steer.py` 的接口一致性和差异

接口一致性：

- 三者都暴露 `select_action(... use_guidance, keypoints, guidance_fns, guide_scale, start_ratio, use_diversity, diversity_scale, MCMC_steps, use_fkd, fkd_config, global_step, current_stage, sigmoid_k, sigmoid_x0 ...)` 这一类参数。
- 三者都在 action chunk 边界生成新 chunk，并缓存给后续 rollout steps 使用。
- 三者都使用两阶段 guidance：early diversity，late keypoint gradient。
- 三者都使用 stage baseline `_stage_init_reward`、`_last_normalized_reward`、`_last_scale` 支持 reward-based adaptive scale 和主程序 overlay。
- 三者都接受 FKD 配置，并把 keypoint reward function 接到 FKD。

关键差异：

| 维度 | RDT | DiffusionPolicySteer | PI05PolicySteer |
| --- | --- | --- | --- |
| sample 空间 | `(B,64,128)` RDT unified action space | `(B,horizon,action_dim)` LeRobot diffusion action space | `(B,chunk_size,max_action_dim)` flow action space |
| observation pre/post | RDT 内部处理，main identity pre/post | LeRobot pre/postprocessor | LeRobot pre/postprocessor |
| scheduler/动力学 | DPMSolverMultistep, `prediction_type=sample` | diffusion noise scheduler, often epsilon/sample depending config | flow matching Euler update |
| keypoint 写回符号 | `model_output += +scale * grad` on RDT translation slots | `model_output -= scale * grad` on first 3 action dims | `v_t -= scale * grad` on first 3 action dims |
| diversity 写回 | `model_output += -diversity_scale * grad` on slots `[39,40,41]` | `model_output += diversity_scale * grad[:, :, :3]` | `v_t += diversity_scale * grad[:, :, :3]` |
| trajectory conversion | 取 RDT 128D slots `[39,40,41,42,43,44,10]` 后 adapter conversion | postprocessor(sample) 后 adapter conversion | postprocessor + env_postprocessor 后 adapter conversion |
| final particle selection | 显式 reward argmax 选择执行 particle | 无专门 selection，通常返回 batch，由 main 执行 index 0 | 无专门 selection，通常返回 batch，由 main 执行 index 0 |
| visualization candidates | 有 `get_last_visualization_action_candidates()` | 无 | 无 |
| FKD x0 scoring source | `pred_original_sample` 或 `model_output` | 当前 sample | 当前 `x_t` |
| scheduler history reset | FKD resample 后重置 DPMSolver history | 无 | 无需 multistep scheduler history |
| `global_step/current_stage` | 当前未使用 | verbose 日志使用 | verbose 日志使用 |
| `MCMC_steps` | 未使用 | 未使用 | 未使用 |

RDT 版本更完整地处理了“多 particles 中最终执行哪一条”和“可视化展示哪些候选”这两个问题；这也是它相对另外两个 steer policy 的主要新增行为。

## 16. 总结

当前 `core/rdt_policy_steer.py:_guided_denoise_loop` 已经实现了 RDT 版本 VLS steering 的核心闭环：在 RDT 128D action sample denoising 过程中，先用 diversity gradient 拉开 particles，再用 VLM keypoint reward 的可微梯度调整 translation slots，并可选使用 FKD 在采样中重采样高 reward particles；最后显式按 reward 从多 particles 中选出执行轨迹，并缓存候选轨迹供可视化。

真正生效的参数包括 `use_guidance`、`sample_batch_size`、`guide_scale`、`sigmoid_k`、`sigmoid_x0`、`start_ratio`、`use_diversity`、`diversity_scale`、`use_fkd`、`fkd_config`、`keypoints`、`guidance_fns` 和 `action_chunk_horizon`。只透传或当前未实际使用的参数包括 `MCMC_steps`、`global_step`、`current_stage`，以及未调用的 `_adaptive_scale(... reward, ...)`。日志/可视化相关但不直接改变动作的逻辑主要是 `verbose`、`_last_visualization_action_candidates`、`get_last_visualization_action_candidates()` 和 `main.py` 的 overlay。

建议后续优先优化四点：对齐 keypoint/FKD/diversity 的 trajectory reward slice；决定是否恢复 FKD terminal resampling 或删除 `fkd.reached_terminal` 依赖；在 `diversity_scale == 0` 时跳过 diversity gradient 计算；明确 guidance function 的 reward 符号约定和 batch 语义，并在加载/验证 guidance functions 时检查。
