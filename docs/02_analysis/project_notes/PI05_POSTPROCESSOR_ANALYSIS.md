---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: unknown
source_commit: unknown
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/PI05_POSTPROCESSOR_ANALYSIS.md
summary: PI05Policy Action Processing Pipeline: From Raw Output to LIBERO OSC Controller
duplicate_sources:
  - .worktrees/feat/rdt-libero-dataset_finetune/PI05_POSTPROCESSOR_ANALYSIS.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/PI05_POSTPROCESSOR_ANALYSIS.md
---

# PI05Policy Action Processing Pipeline: From Raw Output to LIBERO OSC Controller

## 完整处理链条

```
Flow-matching去噪 (B, H, action_dim) 原始值∈[-∞,∞]
    ↓ [_sample_actions_guided 返回]
    ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   POLICY POSTPROCESSOR PIPELINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    ↓ Step 1: UnnormalizerProcessorStep
    │ 反归一化：从训练分布 → 原始范围
    │ 公式 (MIN_MAX mode):
    │   - 从[-1, 1] → [min, max]
    │   - unnormalized = (action + 1) / 2 * (max - min) + min
    │
    ├─ 输入： (B, H, action_dim) normalized ∈ [-1, 1]
    └─ 输出： (B, H, action_dim) denormalized ∈ [min_val, max_val]
    ↓
    ↓ Step 2: AbsoluteActionsProcessorStep
    │ 如果启用相对动作模式，转换回绝对动作
    │ 公式：
    │   absolute = relative + state[..., :dims]
    │ (在预处理中被转换为相对，现在恢复)
    │
    ├─ 输入： (B, H, action_dim) relative/denormalized
    └─ 输出： (B, H, action_dim) absolute positions
    ↓
    ↓ Step 3: DeviceProcessorStep
    │ 移至CPU
    │
    ├─ 输入： (B, H, action_dim) 在CUDA上
    └─ 输出： (B, H, action_dim) 在CPU上
    ↓
POLICY POSTPROCESSOR 最终输出: (1, H, action_dim)
    ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ENVIRONMENT POSTPROCESSOR
   (LIBERO Adapter - Currently Empty)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    (LiberoAdapter[redacted env file]_postprocessor 当前为空pipeline)

    ↓ [使用梯度计算时通过]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   TRAJECTORY PROJECTION (仅限梯度计算)
   pi05_steer._sample_to_trajectory_3d()
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    ↓ Step 1: Apply policy_postprocessor again
    │ → (1, H, action_dim) denormalized
    ↓
    ↓ Step 2: env_postprocessor (if exists)
    │ → (仅转换数据格式，LIBERO为空)
    ↓
    ↓ Step 3: adapter.delta_actions_to_ee_trajectory()
    │ 转换动作到3D EEF轨迹
    │ → (1, H+1, 3) 3D位置
    ↓
用于梯度计算的3D轨迹 ∈ R³

    ↓ [最终执行时]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   FINAL ACTION TO ROBOT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    action = policy_postprocessor(action_chunk)
    action ∈ (1, H, action_dim)
        → 在select_action()中被返回
        → 在main.py中执行到环境
```

---

## Step 1: UnnormalizerProcessorStep (反归一化)

### 源码位置
- **LeRobot**: `/lerobot/processor/normalize_processor.py:478-535`
- **PI05 配置**: `/lerobot/policies/pi05/processor_pi05.py:160-166`

### 完整逻辑

#### 初始化
```python
# processor_pi05.py line 160-163
output_steps: list[ProcessorStep] = [
    UnnormalizerProcessorStep(
        features=config.output_features,  # ACTION feature定义
        norm_map=config.normalization_mapping,  # FeatureType → NormalizationMode
        stats=dataset_stats,  # mean, std, min, max 统计
    ),
    ...
]
```

#### 执行过程
```python
# normalize_processor.py:512-530
def __call__(self, transition: EnvTransition) -> EnvTransition:
    new_transition = transition.copy()

    # 获取动作（形式为 PolicyAction，通常是 Tensor）
    action = new_transition.get(TransitionKey.ACTION)

    # 应用反归一化转换
    new_transition[TransitionKey.ACTION] = self._normalize_action(
        action,
        inverse=True  # ← 关键：inverse=True 表示反归一化
    )

    return new_transition
```

#### 反归一化算法（MIN_MAX mode - 最常见）
```python
# normalize_processor.py:343-363
# 输入: action ∈ [-1, 1]
# 输出: action ∈ [min, max]

min_val = stats["min"]   # 训练数据中的最小值
max_val = stats["max"]   # 训练数据中的最大值

if inverse:  # 反归一化 (normalize_processor.py:359-361)
    # 从[-1, 1] 映射回 [min, max]
    return (action + 1) / 2 * (max_val - min_val) + min_val
```

**具体例子**（假设 min=-0.5, max=0.5）：
```
normalized action = 0.0
→ denormalized = (0.0 + 1) / 2 * (0.5 - (-0.5)) + (-0.5)
              = 0.5 * 1.0 - 0.5
              = 0.0

normalized action = 1.0
→ denormalized = (1.0 + 1) / 2 * 1.0 - 0.5
              = 1.0 - 0.5 = 0.5

normalized action = -1.0
→ denormalized = (-1.0 + 1) / 2 * 1.0 - 0.5
              = 0.0 - 0.5 = -0.5
```

### 输入输出
| 阶段 | 形状 | 范围 | 含义 |
|------|------|------|------|
| **输入** | (B, H, action_dim) | [-1, 1] | Flow-matching 去噪输出 |
| **输出** | (B, H, action_dim) | [min, max] | 原始动作空间 |

**B** = batch size (通常1)
**H** = action_chunk_horizon (通常8)
**action_dim** = ManiSkill两臂14维 或 Libero单臂8维

---

## Step 2: AbsoluteActionsProcessorStep (相对→绝对转换)

### 源码位置
- **LeRobot**: `/lerobot/processor/relative_action_processor.py:158-208`
- **PI05 配置**: `/lerobot/policies/pi05/processor_pi05.py:164`

### 启用条件
```python
# processor_pi05.py:132-136, 164
relative_step = RelativeActionsProcessorStep(
    enabled=config.use_relative_actions,  # ← 决定是否启用
    ...
)

# 在postprocessor中
AbsoluteActionsProcessorStep(
    enabled=config.use_relative_actions,  # 必须与preprocessor一致
    relative_step=relative_step,  # 引用preprocessor的相对步骤
)
```

### 执行过程

#### 状态缓存机制
```python
# relative_action_processor.py:125-143
# 预处理时 (RelativeActionsProcessorStep)
def __call__(self, transition: EnvTransition):
    observation = transition.get(TransitionKey.OBSERVATION, {})
    state = observation.get(OBS_STATE)  # 获取当前状态 (7,)

    if state is not None:
        self._last_state = state  # ← 缓存当前状态供postprocessor使用

    if not self.enabled:
        return transition

    # 转换为相对动作
    action_relative = action - state
```

#### 反向转换（后处理）
```python
# relative_action_processor.py:175-200
# 后处理时 (AbsoluteActionsProcessorStep)
def __call__(self, transition: EnvTransition):
    if not self.enabled:
        return transition

    # 获取缓存的状态
    state = self.relative_step._last_state  # (B, state_dim)

    # 创建掩码（哪些维度转换）
    mask = self.relative_step._build_mask(action.shape[-1])

    # 转换回绝对动作
    action_absolute = to_absolute_actions(action, state, mask)
```

#### 转换公式
```python
# relative_action_processor.py:62-81
def to_absolute_actions(actions, state, mask):
    """
    absolute = relative + state (仅对masked维度)
    """
    mask_t = torch.tensor(mask, dtype=actions.dtype)  # (action_dim,)
    dims = mask_t.shape[0]

    # 获取状态的对应维度
    state_offset = state[..., :dims] * mask_t  # (B, dims)

    if actions.ndim == 3:
        state_offset = state_offset.unsqueeze(-2)  # (B, 1, dims)

    # 加回状态
    actions = actions.clone()
    actions[..., :dims] += state_offset
    return actions
```

### 什么时候启用？
根据PI05的配置：
```yaml
# 典型配置
use_relative_actions: true  # OpenPI使用相对动作
relative_exclude_joints: []  # 所有关节都转换

# 如果exclude_joints = ["gripper"]
# 则只有前7维(臂关节)被转换，gripper保持绝对
```

### 示例
```
假设：
- state = [0.5, 0.3, -0.2, ...]  (当前关节位置)
- relative_action = [0.1, -0.05, 0.0, ...]  (预测的相对增量)
- mask = [True, True, True, ...]  (所有维度都转换)

绝对动作 = relative_action + state
         = [0.1 + 0.5, -0.05 + 0.3, 0.0 + (-0.2), ...]
         = [0.6, 0.25, -0.2, ...]
```

---

## Step 3: DeviceProcessorStep

### 简单说明
- **功能**: 将张量移至指定设备（CPU/CUDA）
- **后处理配置**: 始终移至 CPU
```python
# processor_pi05.py:165
DeviceProcessorStep(device="cpu")
```

---

## Policy Postprocessor Pipeline 的配置

### 完整配置结构（processor_pi05.py:100-179）

```python
def make_pi05_pre_post_processors(config, dataset_stats):

    # 输出pipeline (后处理)
    output_steps: list[ProcessorStep] = [
        # Step 1: 反归一化
        UnnormalizerProcessorStep(
            features=config.output_features,
            norm_map=config.normalization_mapping,
            stats=dataset_stats,  # 从训练数据集
        ),

        # Step 2: 相对→绝对 (如果启用)
        AbsoluteActionsProcessorStep(
            enabled=config.use_relative_actions,
            relative_step=relative_step,  # 引用preprocessor的相对步骤
        ),

        # Step 3: 移至CPU
        DeviceProcessorStep(device="cpu"),
    ]

    return (preprocessor, postprocessor)
```

### 在main.py中的使用
```python
# main.py:83-84
from lerobot.policies.factory import make_pre_post_processors

# line ~150-170
self.policy_preprocessor, self.policy_postprocessor = make_pre_post_processors(
    policy_cfg=policy_config,
    dataset_stats=dataset_meta.stats,
)

# 传给PI05Policy
policy.post_init(
    adapter=self.adapter,
    postprocessor=self.policy_postprocessor,  # ← 在这里使用
    ...
)
```

---

## 梯度计算时的完整流程

在 `pi05_steer._sample_to_trajectory_3d()` 中（pi05_steer.py:331-355）：

```python
def _sample_to_trajectory_3d(self, sample: Tensor) -> Tensor:
    """
    (B, H, action_dim) 去归一化 + 转换→3D轨迹
    """
    device, dtype = sample.device, sample.dtype

    # 1. 应用policy_postprocessor
    #    - UnnormalizerProcessorStep: [-1,1] → [min,max]
    #    - AbsoluteActionsProcessorStep: relative→absolute
    #    - DeviceProcessorStep: 移至CPU
    actions = self._postprocessor(sample).to(device, dtype)

    # 2. 包装为transition dict
    action_transition = {"action": actions}

    # 3. 如果有env_postprocessor (LIBERO目前为空)
    if hasattr(self._adapter, 'env_postprocessor'):
        action_transition = self._adapter[redacted env file]_postprocessor(action_transition)
        actions = action_transition["action"]

    # 4. 转换为EEF 3D轨迹（用于梯度计算）
    if batch_size == 1:
        traj = self._adapter.delta_actions_to_ee_trajectory(
            actions.squeeze(0)[:self._action_chunk_horizon]  # (H, action_dim)
        )
        return traj.unsqueeze(0).to(device, dtype)

    # 多个批次
    trajs = [
        self._adapter.delta_actions_to_ee_trajectory(
            actions[b, :self._action_chunk_horizon]
        )
        for b in range(batch_size)
    ]
    return torch.stack(trajs, dim=0).to(device, dtype)
```

---

## 梯度反向传播

在 `_compute_keypoint_gradient()` 中（pi05_steer.py:357-409）：

```python
with torch.enable_grad():
    sample_grad = sample.detach().requires_grad_(True)  # 需要梯度

    # 通过整个postprocessor处理（梯度传播）
    traj = self._sample_to_trajectory_3d(sample_grad)  # 需要计算图

    # 计算reward
    reward = guidance_fn(keypoints, traj)

    # 反向传播到原始action空间
    grad = torch.autograd.grad(reward, sample_grad)[0]

    # 归一化梯度
    grad_norm = torch.norm(grad)
    normalized_grad = grad / (grad_norm + 1e-8)
```

**关键点**: 梯度通过 policy_postprocessor 反向传播，所以引导作用于反归一化的动作空间。

---

## 总结表

### Action的状态变化

| 步骤 | 处理器 | 输入形状 | 输入范围 | 输出范围 | 输出形状 |
|------|--------|---------|---------|---------|---------|
| 0 | 去噪loop | (B, H, action_dim) | [-∞, ∞] | [-1, 1] | (B, H, action_dim) |
| 1 | UnnormalizerProcessorStep | (B, H, action_dim) | [-1, 1] | [min, max] | (B, H, action_dim) |
| 2 | AbsoluteActionsProcessorStep | (B, H, action_dim) | relative | absolute | (B, H, action_dim) |
| 3 | DeviceProcessorStep | (B, H, action_dim) | — | — | (1, H, action_dim) |
| 最终 | select_action() | — | — | — | (1, H, action_dim) |

### 关键参数来源

| 参数 | 来源 | 说明 |
|------|------|------|
| `min`, `max` | `dataset_stats` | 从训练数据集统计 |
| `use_relative_actions` | `config` | 是否使用相对动作（OpenPI特性） |
| `stats` | `dataset_meta.stats` | 在 main.py 加载的数据集元数据 |

### LIBERO特殊性

- **env_postprocessor**: 当前为空（无步骤）
- **delta_actions_to_ee_trajectory**: 由adapter实现，不由postprocessor处理
- **最终动作**: 来自 policy_postprocessor，直接被环境执行
