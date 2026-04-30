# PI05 Checkpoint 加载问题全貌分析

> 索引：加载 `lerobot/pi05_libero_finetuned_v044` 时出现的 `remap state dict keys` 错误、根本原因、曾做过的修改（已全部撤销）、以及正确修复路径。

---

## 1. 错误现象

```
Warning: Could not remap state dict keys:
Error(s) in loading state_dict for PI05PolicySteer:
    Missing key(s) in state_dict: ...input_layernorm.weight...
    Unexpected key(s) in state_dict: ...input_layernorm.dense.weight...
```

---

## 2. 根本原因

### 2.1 Checkpoint 的 key 格式

Checkpoint 由 LeRobot 的 `save_pretrained` 保存，所有 key 都带 `model.` 前缀（因为 `PI05Policy.model` 才是实际的 `PI05Pytorch`）。例如：

```
model.paligemma_with_expert.gemma_expert.model.layers.0.input_layernorm.dense.weight
model.paligemma_with_expert.gemma_expert.model.layers.0.input_layernorm.dense.bias
```

共 812 个 key，其中 74 个是 adaRMS 的 `.dense.weight/.bias`。

### 2.2 原始代码的 regex 没有 `model.` 前缀

`_fix_pytorch_state_dict_keys`（`modeling_pi05.py:1036-1055`）只能匹配裸 key（无 `model.` 前缀），无法过滤带 `model.` 前缀的 checkpoint key，导致 74 个 `.dense.weight/.bias` key 原样透传给 `load_state_dict`，触发 "Unexpected key" 报错。

### 2.3 adaRMS 在已安装的 transformers 中不存在

Checkpoint 的 adaRMS key 对应的模块（`GemmaRMSNorm.dense`）在已安装的 `transformers==4.53.2` 中**根本不存在**。标准 `GemmaRMSNorm.forward(self, x)` 没有 `dense` 子层，没有 `cond` 参数，返回单个 tensor 而非 `(output, gate)` 元组。

---

## 3. 曾做过的「粗暴」修改（已全部撤销）

### 3.1 修改内容

| 位置 | 原始 | 修改后 |
|------|------|--------|
| `from_pretrained` 签名 | `strict: bool = True` | `strict: bool = False` |
| `load_state_dict` 调用 | `strict=strict` | 硬编码 `strict=False` |
| `_fix_pytorch_state_dict_keys` | 仅匹配裸 key | 重写：检测 `expert_uses_adarms`，条件性丢弃 `.dense.weight/bias` |

### 3.2 该修改解决了什么

- 消除了 "Unexpected key" 报错（74 个 `.dense.weight/bias` key 被 drop）
- 模型不再抛出异常，可以正常完成加载

### 3.3 该修改**没有**解决什么（为何撤销）

**将所有 adaRMS key 丢弃后，expert 模型完全失去对去噪时间步 `t` 的感知**，推理性能严重劣化，详见 §4。

---

## 4. adaRMS 缺失对推理的影响

### 4.1 时间步信息的唯一传递通道

在 `embed_suffix`（`modeling_pi05.py:643-688`）中：

```python
time_emb = sinusoidal_pos_embedding(timestep) → MLP(time_emb)
action_time_emb = action_emb        # ← 动作嵌入，不含时间
adarms_cond = time_emb              # ← 时间步仅通过此通道传入 Expert
```

`adarms_cond` 是 Expert 感知当前 Euler 步骤（`t ∈ {1.0, 0.9, …, 0.0}`）的**唯一途径**。

### 4.2 推理时的调用链

```
denoise_step()
  └── paligemma_with_expert.forward([None, suffix_embs], adarms_cond=[None, time_emb])
        └── elif inputs_embeds[0] is None:
              gemma_expert.model.forward(inputs_embeds=suffix_embs, adarms_cond=time_emb)
                └── GemmaModel.forward(**kwargs)  ← adarms_cond 进入 **kwargs 被默默丢弃
                      └── GemmaDecoderLayer.forward(hidden_states, ...)
                            └── self.input_layernorm(hidden_states)  ← 无 cond 参数
```

结果：Expert 在所有 10 个 Euler 步中预测**完全相同**的速度场，Flow Matching 退化，success rate 趋近 **0%**。

### 4.3 adaRMS 的实现机制（未在 transformers 中实现）

| 操作 | 描述 |
|------|------|
| `gate = tanh(dense(time_emb))` | 从时间步嵌入计算门控，`dense: Linear(1024→1024)` |
| `(norm_out, gate) = input_layernorm(x, cond=time_emb)` | AdaRMSNorm 返回 `(归一化输出, gate)` |
| `residual = _gated_residual(x, attn_out, gate)` | 门控残差：`x + gate * attn_out` |

---

## 5. 正确修复路径（待实现）

需要修改两处：

### 5.1 修改 `transformers` 中的 `modeling_gemma.py`

路径：`/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/transformers/models/gemma/modeling_gemma.py`

需添加/修改：

1. **新增 `AdaGemmaRMSNorm` 子类**
   ```python
   class AdaGemmaRMSNorm(GemmaRMSNorm):
       def __init__(self, dim, cond_dim, eps=1e-6):
           super().__init__(dim, eps)
           self.dense = nn.Linear(cond_dim, dim, bias=True)
           nn.init.zeros_(self.dense.weight); nn.init.zeros_(self.dense.bias)
       def forward(self, x, cond=None):
           out = super().forward(x)  # 标准 RMSNorm
           if cond is not None:
               gate = torch.tanh(self.dense(cond)).unsqueeze(1)
               return out, gate
           return out, None
   ```

2. **新增 `_gated_residual`**
   ```python
   def _gated_residual(residual, x, gate):
       return residual + x if gate is None else residual + x * gate
   ```

3. **修改 `GemmaDecoderLayer.__init__`**：当 `config.use_adarms=True` 时改用 `AdaGemmaRMSNorm`

4. **修改 `GemmaDecoderLayer.forward`**：从 `**kwargs` 中提取 `adarms_cond`，传给 layernorm，使用 `_gated_residual`

5. **修改 `GemmaModel.forward`**：从 `**kwargs` 提取 `adarms_cond`，透传给每一层

6. **修改 `GemmaModel.__init__`**：最终 `self.norm` 也使用 `AdaGemmaRMSNorm`

### 5.2 `_fix_pytorch_state_dict_keys` 无需额外修改

`_fix_pytorch_state_dict_keys` 已有 `expert_uses_adarms = hasattr(first_layer.input_layernorm, "dense")` 检测逻辑：
- 一旦 `AdaGemmaRMSNorm` 实装，`hasattr(..., "dense") == True`，进入 `else` 分支，checkpoint 的 `.dense.weight/bias` 将**不再被丢弃**，而是正常加载进模型

---

## 6. 关键文件索引

| 文件 | 关键位置 | 说明 |
|------|---------|------|
| [modeling_pi05.py](../third_party/lerobot/src/lerobot/policies/pi05/modeling_pi05.py) | `:643` `embed_suffix` | `adarms_cond = time_emb`，时间步通道 |
| [modeling_pi05.py](../third_party/lerobot/src/lerobot/policies/pi05/modeling_pi05.py) | `:219` `compute_layer_complete` | 训练时双流联合注意力 + adaRMS 调用（需 `_gated_residual`） |
| [modeling_pi05.py](../third_party/lerobot/src/lerobot/policies/pi05/modeling_pi05.py) | `:832` `denoise_step` | 推理时 Expert forward，adarms_cond 在此被 transformers 丢弃 |
| [modeling_pi05.py](../third_party/lerobot/src/lerobot/policies/pi05/modeling_pi05.py) | `:1025` `_fix_pytorch_state_dict_keys` | checkpoint key 过滤，已有双分支逻辑 |
| transformers `modeling_gemma.py` | `:49` `GemmaRMSNorm` | 需扩展为支持 `cond` 参数的 `AdaGemmaRMSNorm` |
| transformers `modeling_gemma.py` | `:261` `GemmaDecoderLayer` | 需线程化 `adarms_cond` |
| transformers `modeling_gemma.py` | `:345` `GemmaModel` | 需线程化 `adarms_cond` + 支持 adaRMS final norm |

---

## 7. Checkpoint 关键统计

| 项目 | 数值 |
|------|------|
| 总 key 数 | 812 |
| 所有 key 的前缀 | `model.`（LeRobot `save_pretrained` 包装） |
| adaRMS `.dense.weight/bias` key 数 | 74（Expert 18层 × 2 norm + 1 final norm = 37 modules × 2） |
| 文件大小 | 7.47 GB（7,473,096,344 bytes，fp32） |
| 保存路径 | `/mnt/data/hf_cache/hub/models--lerobot--pi05_libero_finetuned_v044/` |
