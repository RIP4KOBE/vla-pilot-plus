---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: unknown
source_commit: unknown
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/MAKE_PRE_POST_PROCESSORS_FACTORY.md
summary: make_pre_post_processors 工厂函数详解
duplicate_sources:
  - .worktrees/feat/rdt-libero-dataset_finetune/MAKE_PRE_POST_PROCESSORS_FACTORY.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/MAKE_PRE_POST_PROCESSORS_FACTORY.md
---

# make_pre_post_processors 工厂函数详解

## 源码位置
**文件**: `/lerobot/policies/factory.py:241-440`

---

## 工厂函数的核心逻辑

```python
def make_pre_post_processors(
    policy_cfg: PreTrainedConfig,
    pretrained_path: str | None = None,
    **kwargs: Unpack[ProcessorConfigKwargs],
) -> tuple[
    PolicyProcessorPipeline[dict[str, Any], dict[str, Any]],
    PolicyProcessorPipeline[PolicyAction, PolicyAction],
]:
    """
    创建或加载预/后处理器管道

    Args:
        policy_cfg: 策略配置对象（包含policy_cfg.type）
        pretrained_path: 可选的预训练模型路径（从中加载处理器）
        **kwargs: 处理器配置参数

    Returns:
        (preprocessor, postprocessor) 元组
    """
```

---

## 工厂函数的两条主要路径

### 路径1: 从预训练模型加载 (lines 271-312)

```python
if pretrained_path:
    # 从磁盘加载保存的处理器配置
    preprocessor = PolicyProcessorPipeline.from_pretrained(
        pretrained_model_name_or_path=pretrained_path,
        config_filename=f"{POLICY_PREPROCESSOR_DEFAULT_NAME}.json",
        overrides=kwargs.get("preprocessor_overrides", {}),
        to_transition=batch_to_transition,
        to_output=transition_to_batch,
    )
    postprocessor = PolicyProcessorPipeline.from_pretrained(
        pretrained_model_name_or_path=pretrained_path,
        config_filename=f"{POLICY_POSTPROCESSOR_DEFAULT_NAME}.json",
        overrides=kwargs.get("postprocessor_overrides", {}),
        to_transition=policy_action_to_transition,
        to_output=transition_to_policy_action,
    )

    # 重新连接相对动作步骤（反序列化后需要重新连接）
    _reconnect_relative_absolute_steps(preprocessor, postprocessor)

    return preprocessor, postprocessor
```

**应用场景**: 加载已保存的模型和处理器

---

### 路径2: 基于策略类型创建新的处理器 (lines 314-440)

```python
# 根据policy_cfg的类型派发到不同的处理器工厂
if isinstance(policy_cfg, TDMPCConfig):
    from .tdmpc.processor_tdmpc import make_tdmpc_pre_post_processors
    processors = make_tdmpc_pre_post_processors(config=policy_cfg, ...)

elif isinstance(policy_cfg, DiffusionConfig):
    from .diffusion.processor_diffusion import make_diffusion_pre_post_processors
    processors = make_diffusion_pre_post_processors(config=policy_cfg, ...)

elif isinstance(policy_cfg, PI05Config):
    from .pi05.processor_pi05 import make_pi05_pre_post_processors
    processors = make_pi05_pre_post_processors(config=policy_cfg, ...)

elif isinstance(policy_cfg, ACTConfig):
    from .act.processor_act import make_act_pre_post_processors
    processors = make_act_pre_post_processors(config=policy_cfg, ...)

# ... 其他策略类型 ...

else:
    # 动态加载第三方策略
    processors = _make_processors_from_policy_config(...)

return processors
```

---

## 派发流程详解

### 派发决策树

```
make_pre_post_processors(policy_cfg)
    ↓
    ├─ pretrained_path 提供?
    │  ├─ YES → 从磁盘加载 (return早期)
    │  └─ NO  → 继续
    │
    ├─ isinstance(policy_cfg, TDMPCConfig)?
    │  └─ YES → make_tdmpc_pre_post_processors()
    │
    ├─ isinstance(policy_cfg, DiffusionConfig)?
    │  └─ YES → make_diffusion_pre_post_processors()
    │
    ├─ isinstance(policy_cfg, PI05Config)?
    │  └─ YES → make_pi05_pre_post_processors()
    │
    ├─ isinstance(policy_cfg, ACTConfig)?
    │  └─ YES → make_act_pre_post_processors()
    │
    ├─ ... 其他策略 ...
    │
    └─ 都不匹配?
       └─ _make_processors_from_policy_config()
          (动态导入第三方)
```

---

## 各策略处理器的派发映射

### 完整支持的策略列表 (factory.py:314-430)

| 策略类型 | Config类 | 处理器工厂函数 | 文件位置 |
|---------|---------|-------------|---------|
| **TDMPC** | TDMPCConfig | make_tdmpc_pre_post_processors | policies/tdmpc/processor_tdmpc.py |
| **Diffusion** | DiffusionConfig | make_diffusion_pre_post_processors | policies/diffusion/processor_diffusion.py |
| **ACT** | ACTConfig | make_act_pre_post_processors | policies/act/processor_act.py |
| **MultiTaskDiT** | MultiTaskDiTConfig | make_multi_task_dit_pre_post_processors | policies/multi_task_dit/processor_multi_task_dit.py |
| **VQBeT** | VQBeTConfig | make_vqbet_pre_post_processors | policies/vqbet/processor_vqbet.py |
| **PI0** | PI0Config | make_pi0_pre_post_processors | policies/pi0/processor_pi0.py |
| **PI05** | PI05Config | make_pi05_pre_post_processors | policies/pi05/processor_pi05.py |
| **SAC** | SACConfig | make_sac_pre_post_processors | policies/sac/processor_sac.py |
| **SmolVLA** | SmolVLAConfig | make_smolvla_pre_post_processors | policies/smolvla/processor_smolvla.py |
| **SARM** | SARMConfig | make_sarm_pre_post_processors | policies/sarm/processor_sarm.py |
| **Gr00t** | GrootConfig | make_groot_pre_post_processors | policies/groot/processor_groot.py |
| **XVLA** | XVLAConfig | make_xvla_pre_post_processors | policies/xvla/processor_xvla.py |
| **WallX** | WallXConfig | make_wall_x_pre_post_processors | policies/wall_x/processor_wall_x.py |

---

## PI05 和 Diffusion 的派发代码

### PI05 派发 (lines 365-371)

```python
elif isinstance(policy_cfg, PI05Config):
    from .pi05.processor_pi05 import make_pi05_pre_post_processors

    processors = make_pi05_pre_post_processors(
        config=policy_cfg,
        dataset_stats=kwargs.get("dataset_stats"),
    )
```

**输入**: PI05Config对象
**输出**: (PI05预处理器, PI05后处理器)
**处理器特点**: 相对动作 + PaliGemma tokenizer

### Diffusion 派发 (lines 323-329)

```python
elif isinstance(policy_cfg, DiffusionConfig):
    from .diffusion.processor_diffusion import make_diffusion_pre_post_processors

    processors = make_diffusion_pre_post_processors(
        config=policy_cfg,
        dataset_stats=kwargs.get("dataset_stats"),
    )
```

**输入**: DiffusionConfig对象
**输出**: (Diffusion预处理器, Diffusion后处理器)
**处理器特点**: 简洁的归一化/反归一化

---

## 在 main.py 中的使用

### 初始化处理器 (main.py:~150-170)

```python
from lerobot.policies.factory import make_pre_post_processors

# 根据策略类型加载或创建处理器
if policy_config.get('pretrained_path'):
    # 方式1: 从预训练模型加载
    self.policy_preprocessor, self.policy_postprocessor = (
        make_pre_post_processors(
            policy_cfg=policy,  # 已加载的策略对象
            pretrained_path=policy_config['pretrained_path'],
        )
    )
else:
    # 方式2: 创建新的处理器
    self.policy_preprocessor, self.policy_postprocessor = (
        make_pre_post_processors(
            policy_cfg=policy.config,  # 策略的配置对象
            dataset_stats=dataset_meta.stats,  # 归一化统计
        )
    )
```

### 识别策略类型

```python
# main.py:148-150
policy_type = policy_config.get('type', 'diffusion')

if policy_type == 'pi05':
    policy_config = PI05Config(...)  # ← isinstance 检查会识别这个

elif policy_type == 'diffusion':
    policy_config = DiffusionConfig(...)  # ← isinstance 检查会识别这个
```

---

## 处理器配置参数 (ProcessorConfigKwargs)

### 类型定义 (factory.py:219-238)

```python
class ProcessorConfigKwargs(TypedDict, total=False):
    """处理器配置的类型提示"""

    # 预处理器配置
    preprocessor_config_filename: str | None
    preprocessor_overrides: dict[str, Any] | None

    # 后处理器配置
    postprocessor_config_filename: str | None
    postprocessor_overrides: dict[str, Any] | None

    # 共享配置
    dataset_stats: dict[str, dict[str, torch.Tensor]] | None
```

### 使用示例

```python
# 方式1: 基本使用（自动检测）
processors = make_pre_post_processors(
    policy_cfg=policy_config,
    dataset_stats=dataset.meta.stats,
)

# 方式2: 覆盖配置
processors = make_pre_post_processors(
    policy_cfg=policy_config,
    dataset_stats=custom_stats,  # 使用自定义统计
    preprocessor_overrides={
        "normalizer_processor": {
            "eps": 1e-6,  # 自定义epsilon
        }
    },
    postprocessor_overrides={
        "unnormalizer_processor": {
            "eps": 1e-6,
        }
    },
)

# 方式3: 从预训练路径加载
processors = make_pre_post_processors(
    policy_cfg=policy_config,
    pretrained_path="path/to/model",
    preprocessor_config_filename="custom_preprocessor.json",
)
```

---

## 动态派发机制 (_make_processors_from_policy_config)

### 处理第三方策略 (factory.py:610-635)

```python
def _make_processors_from_policy_config(
    config: PreTrainedConfig,
    dataset_stats: dict[str, dict[str, torch.Tensor]] | None = None,
) -> tuple[Any, Any]:
    """
    动态导入第三方策略的处理器

    用于LeRobot插件系统支持自定义策略
    """

    # 提取策略类型
    policy_type = config.type  # 例如 "custom_policy"

    # 生成函数名: custom_policy → make_custom_policy_pre_post_processors
    function_name = f"make_{policy_type}_pre_post_processors"

    # 生成模块路径: configuration_custom_policy → processor_custom_policy
    module_path = config.__class__.__module__.replace(
        "configuration_", "processor_"
    )

    # 动态导入
    module = importlib.import_module(module_path)
    function = getattr(module, function_name)

    # 调用处理器工厂
    return function(config, dataset_stats=dataset_stats)
```

**示例**: 如果添加自定义策略 `MyNewPolicy`

```python
# my_new_policy/configuration_my_new_policy.py
class MyNewPolicyConfig(PreTrainedConfig):
    type = "my_new_policy"
    ...

# my_new_policy/processor_my_new_policy.py
def make_my_new_policy_pre_post_processors(config, dataset_stats):
    # 自定义处理逻辑
    return (preprocessor, postprocessor)

# 自动派发！
processors = make_pre_post_processors(
    policy_cfg=MyNewPolicyConfig(...)
)
# → 自动找到 make_my_new_policy_pre_post_processors 并调用
```

---

## 相对动作步骤的重新连接

### 问题描述

序列化后，AbsoluteActionsProcessorStep 中的 `relative_step` 引用会丢失（因为它指向另一个对象）。

### 解决方案 (factory.py:65-81)

```python
def _reconnect_relative_absolute_steps(
    preprocessor: PolicyProcessorPipeline,
    postprocessor: PolicyProcessorPipeline,
) -> None:
    """
    从预训练模型加载后，重新连接相对/绝对动作步骤的引用
    """

    # 在预处理器中找到RelativeActionsProcessorStep
    relative_step = next(
        (s for s in preprocessor.steps
         if isinstance(s, RelativeActionsProcessorStep)),
        None
    )

    if relative_step is None:
        return  # 没有相对动作，无需连接

    # 在后处理器中找到AbsoluteActionsProcessorStep
    for step in postprocessor.steps:
        if isinstance(step, AbsoluteActionsProcessorStep) and step.relative_step is None:
            # 重新建立引用！
            step.relative_step = relative_step
```

**执行流程**:

```
加载预训练模型
    ↓
preprocessor.steps = [... RelativeActionsProcessorStep ...]
postprocessor.steps = [... AbsoluteActionsProcessorStep(relative_step=None) ...]
    ↓
_reconnect_relative_absolute_steps(preprocessor, postprocessor)
    ↓
AbsoluteActionsProcessorStep.relative_step = <RelativeActionsProcessorStep对象>
    ↓
后处理时可以正常访问缓存的状态
```

---

## 特殊情况: Gr00t 策略处理

### Gr00t 的特殊处理 (factory.py:272-291)

```python
if isinstance(policy_cfg, GrootConfig):
    # Gr00t处理自己的归一化，需要特殊覆盖
    preprocessor_overrides = {}
    postprocessor_overrides = {}

    # 在预处理器中传递自定义统计
    preprocessor_overrides["groot_pack_inputs_v3"] = {
        "stats": kwargs.get("dataset_stats"),
        "normalize_min_max": True,
    }

    # 在后处理器中传递自定义统计和action_dim
    env_action_dim = policy_cfg.output_features[ACTION].shape[0]
    postprocessor_overrides["groot_action_unpack_unnormalize_v1"] = {
        "stats": kwargs.get("dataset_stats"),
        "normalize_min_max": True,
        "env_action_dim": env_action_dim,  # Gr00t需要知道环境action维度
    }

    kwargs["preprocessor_overrides"] = preprocessor_overrides
    kwargs["postprocessor_overrides"] = postprocessor_overrides
```

**为什么**: Gr00t 有自己的特殊处理器步骤 (`groot_pack_inputs_v3`, `groot_action_unpack_unnormalize_v1`)，需要特定的参数。

---

## 处理器配置文件格式

### 从磁盘加载时的文件结构

```
pretrained_model/
├── preprocessor_config.json      # PreProcessor配置
├── postprocessor_config.json     # PostProcessor配置
├── config.json                   # 策略配置
├── pytorch_model.bin             # 模型权重
└── ...
```

### preprocessor_config.json 示例 (PI05)

```json
{
  "name": "preprocessor_processor",
  "steps": [
    {
      "class_name": "RenameObservationsProcessorStep",
      "config": {"rename_map": {}}
    },
    {
      "class_name": "AddBatchDimensionProcessorStep",
      "config": {}
    },
    {
      "class_name": "RelativeActionsProcessorStep",
      "config": {
        "enabled": true,
        "exclude_joints": [],
        "action_names": ["joint0", "joint1", ...]
      }
    },
    {
      "class_name": "NormalizerProcessorStep",
      "config": {
        "features": {...},
        "norm_map": {...},
        "eps": 1e-8
      }
    },
    ...
  ]
}
```

---

## 流程总结

```
用户代码:
    make_pre_post_processors(policy_cfg, dataset_stats)
        ↓
工厂函数检查:
    ├─ 是否有pretrained_path?
    │  └─ 是 → 从磁盘加载处理器 (return)
    │
    └─ 否 → 继续
        ↓
    isinstance 检查:
        ├─ PI05Config? → make_pi05_pre_post_processors()
        ├─ DiffusionConfig? → make_diffusion_pre_post_processors()
        ├─ ...其他?
        └─ 都不是 → 动态导入第三方处理器

        ↓
    相对动作重新连接 (如果需要)
        ↓
返回 (preprocessor, postprocessor)
    ↓
调用方在策略中使用
```
