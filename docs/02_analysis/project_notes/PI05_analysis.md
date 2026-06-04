---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: feat/rdt-libero-gt-rollout-reintegration
source_commit: 360a6d052861
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/docs/docs/02_analysis/project_notes/PI05_analysis.md
summary: PI05 模型架构与代码实现详解
duplicate_sources:
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/docs/02_analysis/project_notes/PI05_analysis.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/docs/docs/02_analysis/project_notes/PI05_analysis.md
  - .worktrees/feat/rdt-libero-gt-rollout-integration/analysis/PI05_analysis.md
  - .worktrees/feat/rdt-libero-gt-rollout-integration/docs/superpowers/analysis/PI05_analysis.md
  - .worktrees/feat/rdt-libero-dataset_finetune/analysis/PI05_analysis.md
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/superpowers/analysis/PI05_analysis.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/analysis/PI05_analysis.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/docs/superpowers/analysis/PI05_analysis.md
  - analysis/PI05_analysis.md
---

# PI05 模型架构与代码实现详解

> 基于 `third_party/lerobot/src/lerobot/policies/pi05/modeling_pi05.py` 的深度分析
> 原始来源：Physical Intelligence (OpenPI) `pi0.5` 架构

---

## 1. 总体设计思路

PI05 是一个 **双流 Transformer + Flow Matching** 的机器人动作生成模型：

- **"感知流"（Prefix）**：PaliGemma（视觉-语言模型）负责理解图像 + 语言指令，输出场景的语义表征
- **"动作流"（Suffix）**：Gemma Expert 负责在噪声动作上做去噪，生成干净的动作序列
- **关键创新**：两个 Transformer 的每一层共享注意力计算（Joint Attention），让动作流能直接 Attend 到视觉语言上下文

与扩散策略（Diffusion Policy）不同，PI05 使用 **Flow Matching**，只需 10 步 Euler 积分，推理极快。

---

## 2. 整体类层次结构

```
PI05PolicySteer          ← VLS 项目扩展（core/pi05_steer.py）
  └── PI05Policy         ← LeRobot 策略基类封装（modeling_pi05.py:871）
        └── PI05Pytorch  ← 核心神经网络模型（modeling_pi05.py:510）
              └── PaliGemmaWithExpertModel  ← 双流Transformer（modeling_pi05.py:328）
                    ├── PaliGemmaForConditionalGeneration  ← 感知流（HuggingFace Transformers）
                    │     ├── SigLIP Vision Tower          ← 图像编码器
                    │     └── Gemma Language Model (2B)    ← 语言/前缀Transformer
                    └── GemmaForCausalLM (300M)            ← 动作专家/后缀Transformer
```

---

## 3. 模型配置（PI05Config）

文件：`configuration_pi05.py`

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `paligemma_variant` | `"gemma_2b"` | 视觉语言主干，2B 参数 |
| `action_expert_variant` | `"gemma_300m"` | 动作专家，300M 参数 |
| `chunk_size` | 50 | 一次预测的动作步数（action horizon） |
| `max_action_dim` | 32 | 动作向量最大维度（不足补零） |
| `max_state_dim` | 32 | 状态向量最大维度（不足补零） |
| `num_inference_steps` | 10 | Flow matching 推理步数 |
| `dtype` | `"bfloat16"` | 主干精度，LayerNorm 保持 F32 |
| `image_resolution` | `(224, 224)` | 输入图像分辨率 |
| `time_sampling_beta_alpha/beta` | 1.5 / 1.0 | 训练时时间步 Beta 分布采样参数 |

**关键设计**：`max_action_dim=32` 是填充维度，实际机器人动作维度（如 7DoF）不足 32 维时会补零。这使得模型可以 **零样本适配不同机器人**，无需更改网络结构。

---

## 4. 核心子模块：PaliGemmaWithExpertModel

文件：`modeling_pi05.py:328`

### 4.1 初始化

```python
# modeling_pi05.py:521-526
self.paligemma_with_expert = PaliGemmaWithExpertModel(
    paligemma_config,          # gemma_2b: width=2048, depth=18 layers
    action_expert_config,      # gemma_300m: width=1024, depth=18 layers
    use_adarms=[False, True],  # PaliGemma不用adaRMS，Expert用adaRMS（当前代码实际未实现）
    precision=config.dtype,    # bfloat16
)
```

**两个子模型的规格对比：**

| | PaliGemma (语言部分) | Gemma Expert |
|--|---------------------|--------------|
| 隐藏维度 | 2048 | 1024 |
| 层数 | 18 | 18 |
| 注意力头数 | 8 | 8 |
| KV 头数 | 1 (GQA) | 1 (GQA) |
| Head Dim | 256 | 256 |
| MLP 维度 | 16384 | 4096 |

**注意**：`gemma_expert.model.embed_tokens = None`（line 379）—— Expert 不需要 token embedding，其输入是连续的动作嵌入向量，而非离散 token。

### 4.2 混合精度策略

```python
# modeling_pi05.py:392-403
params_to_keep_float32 = [
    "vision_tower...patch_embedding...",  # SigLIP patch embedding 保持 F32
    "input_layernorm",                    # 所有 LayerNorm 保持 F32（数值稳定性）
    "post_attention_layernorm",
    "model.norm",
]
# 其余参数（QKV、MLP、projector）转为 BF16
```

**原因**：LayerNorm 对数值精度敏感，BF16 会导致归一化数值不稳定；矩阵乘法（GEMM）在 BF16 下计算高效且精度损失可接受。

---

## 5. PI05Pytorch：核心计算图

### 5.1 关键线性层

```python
# modeling_pi05.py:528-532
self.action_in_proj  = nn.Linear(max_action_dim=32,  expert_width=1024)  # 动作输入投影
self.action_out_proj = nn.Linear(expert_width=1024,  max_action_dim=32)  # 动作输出投影
self.time_mlp_in     = nn.Linear(expert_width=1024,  expert_width=1024)  # 时间步MLP
self.time_mlp_out    = nn.Linear(expert_width=1024,  expert_width=1024)
```

### 5.2 时间步嵌入（embed_suffix）

```python
# modeling_pi05.py:643-688
def embed_suffix(self, noisy_actions, timestep):
    # Step 1: 正弦余弦时间嵌入
    time_emb = create_sinusoidal_pos_embedding(
        timestep, dim=1024, min_period=4e-3, max_period=4.0
    )
    # Step 2: 时间MLP：Linear → SiLU → Linear → SiLU
    time_emb = silu(time_mlp_out(silu(time_mlp_in(time_emb))))

    # Step 3: 动作投影
    action_emb = action_in_proj(noisy_actions)  # [B, chunk_size, 1024]

    # time_emb 作为 adaRMS 的条件，action_emb 作为 suffix tokens
    adarms_cond = time_emb  # [B, 1024]
    return action_emb, pad_masks, att_masks, adarms_cond
```

时间步嵌入公式：
```
period[k] = min_period * (max_period/min_period)^(k / (D/2))
sin_input[b,k] = timestep[b] * 2π / period[k]
emb = [sin(sin_input), cos(sin_input)]  ∈ R^D
```
这与 Transformer 位置编码的形式相同，但用于编码扩散/流时间步。

### 5.3 前缀嵌入（embed_prefix）

```python
# modeling_pi05.py:600-641
def embed_prefix(self, images, img_masks, tokens, masks):
    # 图像：SigLIP → 图像 patch 特征序列
    img_emb = paligemma.embed_image(img)   # [B, num_patches, 2048]

    # 语言：token embedding，并乘以 sqrt(dim) 进行尺度归一化
    lang_emb = paligemma.embed_language_tokens(tokens) * sqrt(2048)  # [B, seq_len, 2048]

    # 拼接：图像 + 语言 → prefix 序列
    # att_masks: 全为 0（前缀内部双向注意力）
```

---

## 6. 注意力掩码设计（核心机制）

这是 PI05 最关键的设计之一：**前缀双向注意 + 后缀因果注意 + 后缀可见前缀**。

### 6.1 att_masks 含义

`att_masks` 是一个整数序列，`make_att_2d_masks` 将其转为 2D bool 掩码：

```python
# modeling_pi05.py:101-130
cumsum = cumsum(att_masks, dim=1)
att_2d_masks[i, j] = True  当且仅当  cumsum[j] <= cumsum[i]
```

- `att_mask=0`：与前一个 token 共享相同的 cumsum → 可双向互相 attend
- `att_mask=1`：比前一个 token 的 cumsum 大 1 → 开始新的因果块

### 6.2 前缀掩码（图像+语言）

```python
att_masks = [0, 0, ..., 0]  # 所有前缀 token
```
→ 所有前缀 token 互相可见（**双向注意力**，类似 BERT）

### 6.3 后缀掩码（动作 chunk）

```python
att_masks = [1] + [0] * (chunk_size - 1)  # modeling_pi05.py:681
```
→ 第一个动作 token 的 att_mask=1（新块开始），其余 0
→ 所有动作 token 互相可见（双向），且共同 attend 前缀

### 6.4 推理时的后缀掩码（denoise_step）

```python
# modeling_pi05.py:846-848
prefix_pad_2d_masks = prefix_pad_masks[:, None, :].expand(batch, suffix_len, prefix_len)
suffix_att_2d_masks = make_att_2d_masks(suffix_pad_masks, suffix_att_masks)
full_att_2d_masks = cat([prefix_pad_2d_masks, suffix_att_2d_masks], dim=2)
```

完整注意力矩阵布局：
```
           [前缀 tokens]    [后缀 tokens]
前缀 tokens [  KV Cache  ]       N/A
后缀 tokens [  全可见   ←]  [双向可见  ]
```

---

## 7. Flow Matching 原理与训练

### 7.1 Flow Matching 数学

Flow Matching 定义了一条从噪声 $\epsilon$ 到干净动作 $a$ 的直线插值路径：

$$x_t = t \cdot \epsilon + (1 - t) \cdot a, \quad t \in [0, 1]$$

目标速度（即真实流）为：

$$u_t = \epsilon - a$$

模型学习预测速度场 $v_\theta(x_t, t) \approx u_t$，损失：

$$\mathcal{L} = \mathbb{E}_{t, a, \epsilon} \| v_\theta(x_t, t) - (\epsilon - a) \|_2^2$$

```python
# modeling_pi05.py:698-743（训练 forward）
x_t = t * noise + (1 - t) * actions   # 插值路径
u_t = noise - actions                  # 真实速度
v_t = model_predict(x_t, t)           # 预测速度
loss = MSE(u_t, v_t)
```

### 7.2 时间步采样（训练）

```python
# modeling_pi05.py:593-598
time_beta = Beta(alpha=1.5, beta=1.0).sample(bsize)   # Beta分布
time = time_beta * 0.999 + 0.001                       # 映射到 [0.001, 1.0]
```

Beta(1.5, 1.0) 偏向高时间步（接近 1 的噪声区域），与原始 OpenPI 一致，使模型更多训练于高噪声阶段。

### 7.3 推理：Euler 积分

```python
# modeling_pi05.py:787-830（sample_actions）
x_t = noise           # t=1，纯高斯噪声
dt = -1/num_steps     # = -0.1（10步）

while t >= 0:
    v_t = denoise_step(x_t, t)  # 预测速度
    x_t += dt * v_t             # Euler 步：x_{t+dt} = x_t + dt * v_t
    t += dt
# t: 1.0 → 0.9 → 0.8 → ... → 0.0
```

**10 步 Euler 积分，轨迹为直线**（Flow Matching 的理论优势），比 DDPM 的 100 步 MCMC 采样快 10 倍。

---

## 8. 推理优化：KV Cache

推理时的关键优化（`sample_actions`，line 779-785）：

```python
# Step 1: 只计算前缀一次（图像 + 语言），缓存 KV
_, past_key_values = paligemma_with_expert.forward(
    inputs_embeds=[prefix_embs, None],  # 只有前缀
    use_cache=True,                     # 生成 KV cache
)

# Step 2: 每个去噪步只计算后缀（重用 KV cache）
for step in range(10):
    v_t = denoise_step(
        past_key_values=past_key_values,  # 复用缓存
        x_t=x_t, timestep=t,
    )
```

**效果**：18 层 PaliGemma 语言模型的 KV 只计算一次，10 次去噪循环中复用，推理速度提升约 2×。

---

## 9. 双流联合前向传播（compute_layer_complete）

文件：`modeling_pi05.py:219-289`

这是整个模型最核心、最复杂的函数，实现了两个 Transformer 流在每一层的 **联合注意力**：

```python
def compute_layer_complete(layer_idx, inputs_embeds, attention_mask, position_ids, ...):
    # inputs_embeds = [prefix_hidden_states, suffix_hidden_states]

    # Step 1: 各流独立做 LayerNorm + QKV 投影
    for i, hidden_states in enumerate([prefix_states, suffix_states]):
        layer = models[i].layers[layer_idx]
        hidden_states, gate = layer.input_layernorm(hidden_states, cond=adarms_cond[i])
        q = layer.q_proj(hidden_states)   # [B, seq_len_i, H, D]
        k = layer.k_proj(hidden_states)
        v = layer.v_proj(hidden_states)

    # Step 2: 跨流拼接 Q/K/V
    Q = cat([Q_prefix, Q_suffix], dim=seq_dim)   # 合并序列维度
    K = cat([K_prefix, K_suffix], dim=seq_dim)
    V = cat([V_prefix, V_suffix], dim=seq_dim)

    # Step 3: 统一做 RoPE 旋转位置编码
    cos, sin = paligemma.rotary_emb(dummy, position_ids)
    Q, K = apply_rotary_pos_emb(Q, K, cos, sin)

    # Step 4: 联合注意力计算（用统一的 attention_mask 控制可见性）
    att_output = eager_attention_forward(Q, K, V, attention_mask)

    # Step 5: 按原始分割切回各自的序列
    att_prefix = att_output[:, :prefix_len]
    att_suffix = att_output[:, prefix_len:]

    # Step 6: 各流独立做残差连接 + FFN
    for i in [prefix, suffix]:
        out = o_proj(att_i) + hidden_i              # 第一残差
        out = layernorm(out) → mlp(out) + out       # FFN + 第二残差
```

**核心思想**：两个流在同一层"合并"做注意力（共享 Q/K/V 空间），但因为 attention_mask 的设计，后缀（动作）可以 attend 前缀（图像+语言），但前缀不能 attend 后缀（推理时前缀 KV cache 不包含后缀信息）。

---

## 10. 训练 vs 推理的 Forward 差异

| | 训练（`PI05Pytorch.forward`） | 推理（`sample_actions` + `denoise_step`） |
|--|------|------|
| 输入 | 干净动作 + 加噪 | 随机高斯噪声 |
| 前缀 | 每次计算 | 计算一次，KV 缓存 |
| 后缀 | 联合双流 forward | 仅 suffix，读 KV cache |
| 输出 | MSE loss（速度场误差） | 去噪后的动作 chunk |
| 步数 | 1 次 forward | 10 次 Euler 步 |
| `use_cache` | False | True（前缀），False（后缀） |

---

## 11. PI05Policy → PI05PolicySteer 扩展（VLS项目）

`core/pi05_steer.py` 中的 `PI05PolicySteer` 在 `select_action` 中重写了 `sample_actions`，在 Flow Matching 的每个 Euler 步注入梯度引导：

```
推理流程对比：

标准 PI05:
  noise → [10次 denoise_step] → action_chunk

PI05PolicySteer（有引导时）:
  noise → [10次 denoise_step + gradient_guidance] → action_chunk
                                 ↑
              _compute_keypoint_gradient / _compute_diversity_gradient
```

- `t > start_time`（高噪声阶段）：多样性梯度（RBF 排斥力），让 N 个粒子分散探索
- `t ≤ start_time`（去噪阶段）：关键点距离梯度（吸引力），引导 EE 轨迹接近目标

---

## 12. 参数量估算

| 子模块 | 参数量 |
|--------|--------|
| SigLIP Vision Tower | ~400M |
| PaliGemma Language Model (Gemma 2B) | ~2.0B |
| Gemma Expert (300M) | ~300M |
| action_in/out_proj + time_mlp | ~4M |
| **总计（约）** | **~2.7B** |
| **checkpoint 文件大小** | **7.47 GB (fp32) / ~3.7 GB (bf16)** |

---

## 13. 关键设计决策总结

1. **Flow Matching 而非 Diffusion**：直线插值路径 → 10 步推理 vs 扩散策略的 100 步，速度快 10×，且理论上路径更优

2. **PaliGemma 作为视觉-语言主干**：复用预训练 VLM 的语义理解能力，相比专门训练的策略网络，zero-shot 泛化更强

3. **双流联合注意力**：动作流不是简单地用 cross-attention 读取视觉语言特征，而是在每一层都与 VLM 做联合自注意力，使两者深度耦合

4. **max_dim 填充**：动作/状态维度固定填充到 32，使同一模型可适配 6-DoF / 7-DoF 等不同机械臂，无需修改网络

5. **KV Cache 复用**：前缀只算一次，在 10 步去噪循环中大幅节省计算

6. **adaRMS（自适应归一化）**：时间步信息通过 adaRMS 调制 Expert 的 LayerNorm（`cond=time_emb`），使每一层都感知当前去噪进度。当前代码将 adaRMS 权重 drop 掉，退化为普通 RMSNorm（全1初始化）。

---

## 14. 代码文件索引

| 文件 | 内容 |
|------|------|
| `modeling_pi05.py` | 完整模型实现（本文档分析对象） |
| `configuration_pi05.py` | `PI05Config` 配置数据类 |
| `core/pi05_steer.py` | VLS 引导扩展 `PI05PolicySteer` |
| `configs/policy.yaml` | 运行时配置（pretrained_path 等） |
| `third_party/lerobot/src/lerobot/policies/pretrained.py` | `PreTrainedPolicy` 基类（from_pretrained 逻辑） |
