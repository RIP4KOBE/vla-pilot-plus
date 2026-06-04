---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: unknown
source_commit: unknown
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/PI05_CODE_FLOW.md
summary: PI05Policy Postprocessor 代码执行流
duplicate_sources:
  - .worktrees/feat/rdt-libero-dataset_finetune/PI05_CODE_FLOW.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/PI05_CODE_FLOW.md
---

# PI05Policy Postprocessor 代码执行流

## 执行调用链

### 1. select_action() 调用 (pi05_steer.py:79-135)
```python
def select_action(self, batch, generate_new_chunk=False, ...):
    if generate_new_chunk:
        action_chunk = self._sample_actions_guided(...)  # 或 predict_action_chunk()
        # action_chunk: (B, H, action_dim) 原始去噪值 ∈ [-1, 1]
        self._cached_action_chunk = action_chunk
    else:
        action_chunk = self._cached_action_chunk

    # 调用 self._postprocessor
    # ↓↓↓ POSTPROCESSOR 在这里被调用 ↓↓↓
    return self._postprocessor(action_chunk)  # line 135
```

### 2. PolicyProcessorPipeline.__call__() (lerobot/processor/pipeline.py)
```python
class PolicyProcessorPipeline:
    def __call__(self, action: PolicyAction) -> PolicyAction:
        # PolicyAction 是 Tensor ∈ [-1, 1]

        # 遍历所有处理步骤
        for step in self.steps:
            action = step(action)  # 依次调用每个step

        return action  # 最终输出
```

### 3. 每个处理步骤的执行

#### Step 1: UnnormalizerProcessorStep.__call__()
```python
# lerobot/processor/normalize_processor.py:512-530
class UnnormalizerProcessorStep(ProcessorStep):
    def __call__(self, transition: EnvTransition) -> EnvTransition:
        # 注意: 这里处理的是EnvTransition（包含action等）
        # 当PolicyProcessorPipeline调用时，会先转换

        new_transition = transition.copy()
        action = new_transition.get(TransitionKey.ACTION)

        # 调用核心转换函数
        new_transition[TransitionKey.ACTION] = self._normalize_action(
            action,
            inverse=True  # ← 关键：反归一化
        )
        return new_transition

    def _normalize_action(self, action: Tensor, inverse: bool) -> Tensor:
        # 调用共享的转换逻辑
        return self._apply_transform(
            action,
            ACTION,  # feature key
            FeatureType.ACTION,
            inverse=inverse
        )

    def _apply_transform(self, tensor: Tensor, key: str,
                        feature_type: FeatureType,
                        *, inverse: bool = False) -> Tensor:

        # 获取此feature的归一化模式
        norm_mode = self.norm_map.get(feature_type, NormalizationMode.IDENTITY)

        # 获取统计数据
        stats = self._tensor_stats[key]  # {"min": ..., "max": ..., ...}

        if norm_mode == NormalizationMode.MIN_MAX:
            min_val = stats["min"]
            max_val = stats["max"]
            denom = max_val - min_val

            if inverse:  # 反归一化
                # 从 [-1, 1] → [min_val, max_val]
                return (tensor + 1) / 2 * denom + min_val
            else:  # 正常化
                # 从 [min_val, max_val] → [-1, 1]
                return 2 * (tensor - min_val) / denom - 1
```

#### Step 2: AbsoluteActionsProcessorStep.__call__()
```python
# lerobot/processor/relative_action_processor.py:175-200
class AbsoluteActionsProcessorStep(ProcessorStep):
    def __call__(self, transition: EnvTransition) -> EnvTransition:
        if not self.enabled:
            return transition  # 如果未启用，直接返回

        new_transition = transition.copy()
        action = new_transition.get(TransitionKey.ACTION)

        if action is None:
            return new_transition

        # 获取缓存的状态（由RelativeActionsProcessorStep在预处理时设置）
        state = self.relative_step._last_state  # (B, state_dim)

        # 创建掩码
        mask = self.relative_step._build_mask(action.shape[-1])
        # mask = [True, True, ..., True]（对于所有维度）

        # 转换回绝对
        new_transition[TransitionKey.ACTION] = to_absolute_actions(
            action,
            state,
            mask
        )
        return new_transition

def to_absolute_actions(actions, state, mask):
    """
    将相对动作转换为绝对动作
    absolute = relative + state (对于mask==True的维度)
    """
    mask_t = torch.tensor(mask, dtype=actions.dtype, device=actions.device)
    dims = mask_t.shape[0]

    # 获取状态的对应维度
    state_offset = state[..., :dims] * mask_t

    if actions.ndim == 3:
        state_offset = state_offset.unsqueeze(-2)  # 扩展时间维度

    # 加上状态偏移
    actions = actions.clone()
    actions[..., :dims] += state_offset
    return actions
```

#### Step 3: DeviceProcessorStep.__call__()
```python
# lerobot/processor/device_processor.py
class DeviceProcessorStep(ProcessorStep):
    def __call__(self, transition: EnvTransition) -> EnvTransition:
        # 简单地将所有张量移至指定设备
        new_transition = transition.copy()
        new_transition[TransitionKey.ACTION] = new_transition[
            TransitionKey.ACTION
        ].to(device=self.device)
        return new_transition
```

---

## 具体数值示例

### 输入
```
归一化action from flow-matching:
action_normalized = [0.2, -0.5, 0.8]  shape=(1, 8, 3)
范围: [-1, 1]
```

### Step 1: UnnormalizerProcessorStep

**配置示例**:
```python
stats = {
    "action": {
        "min": [-0.5, -1.0, -0.2],
        "max": [0.5, 1.0, 2.0]
    }
}
norm_map = {FeatureType.ACTION: NormalizationMode.MIN_MAX}
```

**计算过程**:
```python
min_val = [-0.5, -1.0, -0.2]
max_val = [0.5, 1.0, 2.0]
denom = max_val - min_val = [1.0, 2.0, 2.2]

# 反归一化公式: (tensor + 1) / 2 * denom + min_val
action_denormalized = (action_normalized + 1) / 2 * denom + min_val

# 对于 action_normalized[0, 0, :] = [0.2, -0.5, 0.8]
= ([0.2, -0.5, 0.8] + 1) / 2 * [1.0, 2.0, 2.2] + [-0.5, -1.0, -0.2]
= [1.2, 0.5, 1.8] / 2 * [1.0, 2.0, 2.2] + [-0.5, -1.0, -0.2]
= [0.6, 0.25, 0.9] * [1.0, 2.0, 2.2] + [-0.5, -1.0, -0.2]
= [0.6, 0.5, 1.98] + [-0.5, -1.0, -0.2]
= [0.1, -0.5, 1.78]  ✓
```

### Step 2: AbsoluteActionsProcessorStep

**假设预处理时缓存的状态**:
```python
state = [0.3, 0.1, 0.5]  # 当前关节位置
mask = [True, True, True]  # 所有维度转换
```

**计算过程**:
```python
# 相对动作已从预处理获得，现在转换回绝对
# absolute = relative + state[..., :dims]
action_absolute = action_denormalized + state
                = [0.1, -0.5, 1.78] + [0.3, 0.1, 0.5]
                = [0.4, -0.4, 2.28]  ✓
```

### Step 3: DeviceProcessorStep
```python
# 简单地将张量移至CPU
action_absolute = action_absolute.to(device="cpu")
```

**最终输出**:
```
(1, 8, action_dim) ∈ 原始action空间
绝对动作 ∈ [min, max] (real-world units)
在CPU上
```

---

## 梯度流（梯度计算时）

### _sample_to_trajectory_3d() 的梯度流
```python
# pi05_steer.py:331-355
def _sample_to_trajectory_3d(self, sample: Tensor) -> Tensor:
    device, dtype = sample.device, sample.dtype

    # ← 这里需要梯度
    actions = self._postprocessor(sample).to(device, dtype)
    #         ^^^^^^^^^^^^^^^^^^^
    #         通过整个pipeline，包括所有反向操作

    # 梯度在这里流动
    # UnnormalizerProcessorStep 反向: min_val + (denorm - min_val) * denom -> tensor
    # AbsoluteActionsProcessorStep 反向: absolute - state -> relative

    # ...
    traj = self._adapter.delta_actions_to_ee_trajectory(actions)
    return traj
```

### 梯度计算示例
```python
# _compute_keypoint_gradient() line 357-409
with torch.enable_grad():
    sample_grad = sample.detach().requires_grad_(True)

    # 需要梯度的Unnormalizer反向
    # 需要梯度的Absolute反向
    traj = self._sample_to_trajectory_3d(sample_grad)

    reward = guidance_fn(keypoints, traj)

    # 反向传播
    grad = torch.autograd.grad(reward, sample_grad)[0]
    #                                    ^^^^^^^^^^^
    #                                    样本空间中的梯度
```

---

## 关键配置来源

### 从 dataset_stats 加载
```python
# main.py line 83-84
from lerobot.policies.factory import make_pre_post_processors

self.policy_preprocessor, self.policy_postprocessor = (
    make_pre_post_processors(
        policy_cfg=policy_config,
        dataset_stats=dataset_meta.stats  # ← 从LeRobot数据集
    )
)
```

### dataset_stats 的结构
```python
dataset_stats = {
    "action": {
        "min": tensor([...]),     # (action_dim,)
        "max": tensor([...]),     # (action_dim,)
        "mean": tensor([...]),    # (action_dim,)
        "std": tensor([...]),     # (action_dim,)
    },
    "observation.images": {...},
    "observation.state": {...},
    ...
}
```

---

## 处理器状态管理

### 预处理器 (RelativeActionsProcessorStep) 中的状态缓存
```python
# relative_action_processor.py:125-143
class RelativeActionsProcessorStep:
    _last_state: Tensor = None  # ← 缓存

    def __call__(self, transition):
        state = transition.get(OBS_STATE)
        if state is not None:
            self._last_state = state  # ← 缓存当前状态
        ...
```

### 后处理器 (AbsoluteActionsProcessorStep) 使用缓存
```python
# relative_action_processor.py:175-200
class AbsoluteActionsProcessorStep:
    relative_step: RelativeActionsProcessorStep  # ← 引用预处理器

    def __call__(self, transition):
        state = self.relative_step._last_state  # ← 读取缓存
        ...
```

---

## 性能考虑

### 张量操作成本
1. **UnnormalizerProcessorStep**: O(action_dim) 算术运算
2. **AbsoluteActionsProcessorStep**: O(action_dim) 加法运算
3. **DeviceProcessorStep**: O(action_dim) 内存移动

总体: **极低开销** (所有操作都是逐元素的)

### 梯度反向传播成本
- UnnormalizerProcessorStep: 可微分，支持autograd
- AbsoluteActionsProcessorStep: 可微分，支持autograd
- DeviceProcessorStep: 数据移动，不影响梯度

---

## 常见问题

### Q: 为什么需要反归一化？
**A**: Flow-matching模型在归一化的[-1,1]空间训练。执行时需要回到原始动作空间的单位（弧度、米等）。

### Q: 为什么需要相对→绝对转换？
**A**: OpenPI在相对空间训练（delta from current state），但执行需要绝对位置。预处理转为相对，后处理转回绝对。

### Q: 如果 use_relative_actions=False 呢？
**A**: AbsoluteActionsProcessorStep 的 enabled=False，会跳过这个步骤。

### Q: 梯度为何能通过这些步骤？
**A**: 所有操作都是可微分的（加减乘除、张量操作），PyTorch的autograd支持完整的反向传播。
