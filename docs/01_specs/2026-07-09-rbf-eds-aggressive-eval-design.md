# RBF+EDS 第二轮 Aggressive Initial Diversity 实验评估设计

## 1. 摘要

本设计面向 `exp/eds-init-pg-diverse-sampling` 分支上的 EDS RBF-diverse initial sampler 第二轮实验评估。第一轮结果已经证明 `initial_sampling_mode=rbf_diverse_denoise` 路径可以正常运行，但默认参数 `initial_diversity_scale=1.0`、`initial_diversity_start_ratio=null` 只触发约 1 个 early diversity step，RBF 对 early denoise state 的影响大多被后续 RDT denoising prior 擦掉，最终 `initial_final` population 与 naive iid EDS 几乎无差异。

第二轮实验的核心目标是：使用更激进且更贴近 VLS 强度的 RBF 参数，验证 EEF trajectory-space diversity 是否能保留到真正交给 EDS scoring 的 `initial_final` population，并用更直接的 EEF metrics 判断 RBF diversity 是否产生了可执行候选覆盖度收益。

本设计只定义实验和观测方案，不实现代码。

## 2. 背景与第一轮结论

当前 EDS initial population 有两条路径：

- `initial_sampling_mode="iid"`：从 iid Gaussian latent 完整 denoise 得到 `(population_size, 64, 128)` population；
- `initial_sampling_mode="rbf_diverse_denoise"`：在 initial denoise 的 early steps 中复用 VLS 风格 RBF trajectory diversity gradient，之后继续普通 RDT denoise，再进入不变的 EDS score / resample / renoise / rollout。

第一轮 mechanism pretest 和 parameter sweep 的主要结论是：

- RBF sampler 确实启用，且无 fallback；
- 默认 RBF 设置只记录到 `initial_diversity_steps=1`；
- RBF 早期会改变 `initial_before_diversity -> initial_after_diversity_phase`；
- 但完整 denoise 后，`initial_final` trajectory spread 明显收缩；
- parameter sweep 中 `scale=0.5/1.0/2.0` 和 `start_ratio=null/0.25/0.5` 没有带来 selected reward、target distance 或 final qualitative overlay 的有效变化；
- 当前 action-space `population_diversity_initial` 不能充分解释 EEF trajectory-space 上的真实多样性。

第二轮实验因此不直接以 OOD success 为第一目标，而是先回答：

```text
更强 RBF 是否能让 EDS 可见的 initial_final EEF trajectory distribution 显著不同于 iid baseline？
```

## 3. 实验目标

第二轮实验需要回答四个问题：

1. 更大的 `initial_diversity_scale` 是否能显著提高 `initial_after_diversity_phase` 的 EEF trajectory diversity？
2. 更晚结束的 diversity phase，即 `start_ratio=0.6/0.8`，是否能让 diversity 保留到 `initial_final`？
3. 如果 `initial_final` diversity 提升，最终 selected reward 和 target distance 是否不劣于 iid baseline？
4. 如果最终行为仍与 iid 无差异，主要瓶颈是 RDT denoising prior 擦除、EDS reward selection pressure 不足，还是 RBF 破坏了 policy prior？

本轮的关键判断标准是：

```text
initial_eef_diversity_final 和 endpoint_spread_final 是否显著高于 iid baseline。
```

如果这两个指标仍然没有提升，则不建议直接进入大规模 OOD success rate 测试，应先改 RBF 注入位置或 initial proposal selection 机制。

## 4. 固定实验配置

固定 EDS 主参数：

```yaml
main.guidance_type: eds
main.use_guidance: true
main.eds_config.population_size: 16
main.eds_config.cem_iters: 10
main.eds_config.use_cem: false
main.eds_config.num_elites: 32
main.eds_config.temperature: 0.1
main.eds_config.renoise_t_max: 5
main.eds_config.renoise_t_min: 1
main.eds_config.use_initial_cache: false
main.eds_config.save_initial_cache: false
main.eds_config.initial_sampling_mode: rbf_diverse_denoise
```

实验应继续使用 offline cached guidance，避免在线 VLM 抖动影响对比：

```yaml
main.use_vlm_stage_recognition: false
perception.gemini_grounding.enabled: false
```

如果运行入口仍要求 OpenAI client 初始化，可继续使用 dummy key，但报告中必须明确：

```text
OPENAI_API_KEY=dummy 只用于离线 cached guidance 模式下的客户端初始化，不代表实验调用在线 VLM 生成 reward。
```

## 5. Parameter Sweep 设计

### 5.1 对照组

保留两个对照组：

| Run | 用途 |
|---|---|
| `iid_baseline` | 当前 naive iid EDS 初始化 |
| `rbf_s1_start_null` | 第一轮默认 RBF 配置，用于判断 aggressive 参数是否真正增强机制 |

推荐复用或重跑：

```text
level2_libero_object_p16_c10
level2_libero_object_eds_rbf_diverse_initial
```

如果重跑，对照组必须与第二轮 sweep 使用同一代码版本、同一 cached guidance、同一 task filter 和同一 seed。

### 5.2 Aggressive RBF Sweep

RBF 参数范围：

```yaml
initial_diversity_scale: [5, 10, 20]
initial_diversity_start_ratio: [0.6, 0.8]
```

实验矩阵：

| Run | `initial_diversity_scale` | `initial_diversity_start_ratio` | 当前 5-step scheduler 下预期 diversity steps |
|---|---:|---:|---:|
| `rbf_s5_start06` | 5 | 0.6 | 3 |
| `rbf_s10_start06` | 10 | 0.6 | 3 |
| `rbf_s20_start06` | 20 | 0.6 | 3 |
| `rbf_s5_start08` | 5 | 0.8 | 4 |
| `rbf_s10_start08` | 10 | 0.8 | 4 |
| `rbf_s20_start08` | 20 | 0.8 | 4 |

不再测试 `start_ratio=1.0`。在当前约 5-step RDT scheduler 下：

```text
start_ratio=0.8 -> idx=int(5*0.8)=4
start_ratio=1.0 -> idx=int(5*1.0)=5 -> clamp 到 4
```

因此两者大概率等价，继续测试 `1.0` 会浪费 GPU 时间。

### 5.3 推荐执行顺序

本轮不再按 scale 分批执行。实验开始前先用 `nvidia-smi` 检查 8 块 H200 的空闲情况，然后将全部对照组和 aggressive RBF sweep jobs 直接并行提交到所有空闲 GPU。若空闲 GPU 数量少于待运行 jobs，则按空闲 GPU 数量自动排队或分轮补齐，但实验设计上不再将 `scale=20` 作为单独第二批。

完整并行 job 列表：

```text
iid_baseline
rbf_s1_start_null
rbf_s5_start06
rbf_s10_start06
rbf_s20_start06
rbf_s5_start08
rbf_s10_start08
rbf_s20_start08
```

如果某个 aggressive run 出现 nonfinite、fallback、action mask violation 或明显 reward 崩坏，不中断其他并行 run；但 evidence report 必须单独标记该 run safety gate failed，并在最终结论中说明该参数不可用。

## 6. 新增 Metrics 设计

第二轮是在现有 EDS metrics 基础上额外追加 EEF trajectory-space 指标，不替换、不删除、不弱化已有 metrics。原有字段如 `population_diversity_initial/final`、`initial_best_reward`、`selected_reward`、`target_distance_before/after`、`score_entropy`、`unique_parent_ratio_mean`、`action_mask_violation_max`、`nonfinite_count`、latency 和 fallback 相关字段都必须继续记录。

本轮新增字段只限定为下面 7 个 EEF trajectory-space metrics，避免继续扩张指标面：

### 6.1 Initial EEF Diversity

定义：

```text
trajs = _rdt_sample_to_trajectory_3d(population)
eef = trajs[:, 1:, :3]
feature = flatten(eef)
initial_eef_diversity = mean(pairwise_l2(feature))
```

记录三个阶段：

| Metric | 阶段 | 含义 |
|---|---|---|
| `initial_eef_diversity_before_rbf` | `initial_before_diversity` | RBF 注入前的 EEF trajectory spread |
| `initial_eef_diversity_after_rbf_phase` | `initial_after_diversity_phase` | RBF 注入后的 EEF trajectory spread |
| `initial_eef_diversity_final` | `initial_final` | 完整 initial denoise 后、真正交给 EDS scoring 的 EEF trajectory spread |

对 iid baseline：

- `initial_eef_diversity_before_rbf = null`
- `initial_eef_diversity_after_rbf_phase = null`
- `initial_eef_diversity_final = iid initial population 的 EEF diversity`

不要用 final 值填充 before/after，以免误导报告读者。

### 6.2 Initial EEF Diversity Retention Ratio

定义：

```text
initial_eef_diversity_retention_ratio =
    initial_eef_diversity_final / initial_eef_diversity_after_rbf_phase
```

边界处理：

- 如果 `initial_eef_diversity_after_rbf_phase` 为 `null`，ratio 为 `null`；
- 如果 denominator 小于极小值，例如 `1e-8`，ratio 为 `null` 并记录 warning；
- iid baseline 的 ratio 为 `null`。

含义：

```text
RBF 扩散出来的 EEF trajectory diversity 有多少保留到了最终 initial population。
```

判读：

| 现象 | 含义 |
|---|---|
| ratio 接近 1 | RBF 多样性基本保留 |
| ratio 远小于 1 | RDT denoise prior 把 RBF 多样性擦掉 |
| final diversity 高于 iid 但 ratio 低 | RBF 有增强，但仍被明显收缩 |
| final diversity 不高于 iid | aggressive RBF 对最终 EDS 可见候选无效 |

### 6.3 Endpoint Spread

定义：

```text
trajs = _rdt_sample_to_trajectory_3d(population)
endpoints = trajs[:, -1, :3]
endpoint_spread = mean(pairwise_l2(endpoints))
```

记录三个阶段：

| Metric | 阶段 | 含义 |
|---|---|---|
| `endpoint_spread_before_rbf` | `initial_before_diversity` | RBF 前 endpoint 分散度 |
| `endpoint_spread_after_rbf_phase` | `initial_after_diversity_phase` | RBF 后 endpoint 分散度 |
| `endpoint_spread_final` | `initial_final` | 最终 initial proposals endpoint 分散度 |

对 iid baseline：

- `endpoint_spread_before_rbf = null`
- `endpoint_spread_after_rbf_phase = null`
- `endpoint_spread_final = iid initial population endpoint spread`

Endpoint spread 比 full trajectory diversity 更贴近候选最终会到达哪里，是判断 OOD exploration coverage 的关键指标。

## 7. Metrics 写入位置与兼容性

新增 metrics 应写入每条 EDS chunk record，例如 `eds_metrics.jsonl`：

```json
{
  "initial_eef_diversity_before_rbf": 0.12,
  "initial_eef_diversity_after_rbf_phase": 0.14,
  "initial_eef_diversity_final": 0.08,
  "initial_eef_diversity_retention_ratio": 0.57,
  "endpoint_spread_before_rbf": 0.06,
  "endpoint_spread_after_rbf_phase": 0.08,
  "endpoint_spread_final": 0.04
}
```

同时应在 mechanism trace / qualitative pretest 中保留 stage-level 原始数据，方便复查：

```text
initial_before_diversity
initial_after_diversity_phase
initial_final
```

兼容性要求：

- 不改变现有 metric 字段语义；
- 不删除原有 `population_diversity_initial/final`；
- 对 iid baseline 使用 `null` 表示不存在 RBF phase；
- 如果 RBF fallback 到 iid，必须保留 fallback warning，并将 before/after/final metrics 记录为实际可解释的值；
- 若 fallback 后没有可用 RBF stages，`after_rbf_phase` 和 retention ratio 应为 `null`。

## 8. 定量分析表

每个 run 需要生成主表：

| Run | Scale | Start Ratio | Diversity Steps | Fallback | Nonfinite | Init EEF Before | Init EEF After | Init EEF Final | Retention | Endpoint Before | Endpoint After | Endpoint Final | Selected Reward | Target Distance After |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|

同时生成相对 iid 的 delta 表：

| Run | Δ Initial EEF Div Final | Δ Endpoint Spread Final | Δ Selected Reward | Δ Target Distance After | Verdict |
|---|---:|---:|---:|---:|---|

如果 `rbf_s1_start_null` 作为第一轮默认 RBF 对照，也应额外生成相对默认 RBF 的 delta 表：

| Run | Δ Initial EEF Div Final vs s1 | Δ Endpoint Spread Final vs s1 | Δ Selected Reward vs s1 | Δ Target Distance After vs s1 |
|---|---:|---:|---:|---:|

## 9. 通过条件

### 9.1 Safety Gate

所有 aggressive RBF run 必须满足：

```text
initial_diversity_fallback_used = false
initial_diversity_grad_failure_count = 0
nonfinite_count = 0
action_mask_violation_max = 0
```

若任一 run 失败，报告中必须显式标注，不允许静默 fallback 后继续把结果当作 RBF 成功样本。

### 9.2 Mechanism Gate

至少一个 aggressive RBF 配置满足：

```text
initial_eef_diversity_after_rbf_phase > rbf_s1_start_null
initial_eef_diversity_final > iid_baseline
endpoint_spread_final > iid_baseline
```

推荐相对阈值：

```text
initial_eef_diversity_final >= iid_baseline * 1.10
endpoint_spread_final >= iid_baseline * 1.10
```

并且：

```text
initial_eef_diversity_retention_ratio 明显高于第一轮默认 RBF
```

如果 `after_rbf_phase` 显著提升但 `final` 不提升，则结论应是 RDT denoising prior 擦除 RBF diversity，而不是 RBF 未生效。

### 9.3 Utility Gate

不能为了多样性显著破坏 EDS：

```text
selected_reward >= iid_baseline - 1e-3
target_distance_after <= iid_baseline + 5e-3
select_action_latency_s 在可接受范围内
```

如果 mechanism gate 通过但 utility gate 失败，说明 aggressive RBF 可能推离 policy prior 或制造不可用 outlier。

## 10. 定性可视化要求

每个 RBF run 至少保存前 2 个 chunks：

```text
chunk_000000
chunk_000008
```

如果成本允许，建议设置：

```yaml
main.eds_eval.max_visual_chunks_per_episode: 4
```

保存：

```text
chunk_000000
chunk_000008
chunk_000016
chunk_000024
```

本轮必须额外保存或报告 initial sampler stages 的 3D 定性图：

```text
initial_before_diversity_3d
initial_after_diversity_phase_3d
initial_final_3d
```

否则 qualitative 只能看到最终 EDS 行为，无法定位 RBF diversity 在哪里被擦掉。

注意：第一轮报告发现 `initial_best_vs_final_selected.png` 的左图当前并不严格代表 true initial best，而更像 initial candidate visualization。第二轮报告中不应把该图作为严格 best-vs-selected 证据，除非后续实现修正其选取逻辑。

## 11. GPU 调度策略

服务器当前有 8 块 H200。第二轮实验可以使用所有空闲 GPU 并行运行，但必须遵守以下规则：

1. 实验开始前运行 `nvidia-smi`，记录 8 张卡的显存占用、GPU utilization 和已有进程；
2. 只选择空闲或低负载 GPU；
3. 不抢占已有任务，不 kill 其他用户或其他实验的进程；
4. 每个 run 使用独立 `CUDA_VISIBLE_DEVICES=<gpu_id>`；
5. 每个 run 写入独立 `hydra.run.dir` 和 `main.eds_eval.output_dir`，避免并行写文件冲突；
6. 若多张 GPU 同时空闲，可以一张卡跑一个 sweep job；
7. 若空闲 GPU 数量少于 jobs 数量，则先填满所有空闲 GPU，剩余 jobs 等 GPU 释放后继续提交；
8. 实验报告中记录实际使用的 physical GPU ids、开始时间、结束时间和是否有中断/重启。

建议并行策略：

```text
一次性准备 iid baseline、default RBF 和 6 个 aggressive RBF jobs；
用所有空闲 H200 直接并行执行；
每张 GPU 同时只跑一个 job；
所有 jobs 使用独立 output_dir，完成后统一聚合 metrics 和 evidence report。
```

## 12. 输出与证据归档

原始实验输出建议继续放在：

```text
outputs/rdt_eds_eval/<job_id>
```

每个 run 至少包含：

```text
.hydra/config.yaml
.hydra/overrides.yaml
results.txt
main.log
eds_eval/eds_metrics.jsonl
eds_eval/qualitative/
```

最终实验结果必须记录在：

```text
docs/03_evidence/eds_init_pg_diverse_sampling
```

推荐新增报告文件：

```text
docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-09-aggressive-rbf-parameter-sweep.md
```

最终 evidence report 应至少包含：

- branch、commit、worktree；
- 8 GPU 服务器状态和实际使用 GPU；
- 每个 run 的完整 command 或 Hydra overrides；
- raw output directory；
- success count 和 success rate；
- safety gate 表；
- mechanism gate 表；
- utility gate 表；
- EEF metrics 主表；
- 相对 iid baseline delta 表；
- 相对 default RBF delta 表；
- qualitative artifacts 路径；
- fallback / warning / nonfinite 汇总；
- 是否进入 OOD evaluation 的结论；
- 若不进入 OOD，明确阻塞原因。

## 13. 结果解释模板

### 情况 A：After RBF 高，Final 低

```text
initial_eef_diversity_after_rbf_phase ↑
initial_eef_diversity_final ≈ iid
retention_ratio 低
```

结论：

```text
RBF 注入有效，但被后续 RDT denoise prior 擦掉。
```

下一步应考虑更晚注入 RBF，或者做 final proposal trajectory-space filtering。

### 情况 B：Final 高，但 Reward / Distance 不变

```text
initial_eef_diversity_final ↑
endpoint_spread_final ↑
selected_reward ≈ iid
target_distance_after ≈ iid
```

结论：

```text
RBF 解决了 initial diversity，但 EDS reward selection pressure 不足。
```

下一步应分析 reward spread、score entropy 和 temperature。

### 情况 C：Final 高，但 Reward / Distance 变差

```text
initial_eef_diversity_final ↑
endpoint_spread_final ↑
selected_reward ↓
target_distance_after ↑
```

结论：

```text
RBF 太强，把候选推离 policy prior 或生成 outlier。
```

下一步应降低 scale 或加入 validity filtering。

### 情况 D：Final 高，Reward / Distance 也改善

```text
initial_eef_diversity_final ↑
endpoint_spread_final ↑
selected_reward >= iid
target_distance_after <= iid
```

结论：

```text
aggressive RBF initial sampler 值得进入 OOD evaluation。
```

## 14. MVP 范围

第二轮 MVP 只包含：

```text
scale=[5,10,20]
start_ratio=[0.6,0.8]
新增 7 个 EEF metrics
保留 iid + default RBF 对照
使用所有空闲 H200 并行跑实验
最终结果归档到 docs/03_evidence/eds_init_pg_diverse_sampling
```

新增 metrics：

```text
initial_eef_diversity_before_rbf
initial_eef_diversity_after_rbf_phase
initial_eef_diversity_final
initial_eef_diversity_retention_ratio
endpoint_spread_before_rbf
endpoint_spread_after_rbf_phase
endpoint_spread_final
```

本轮不做：

- 不改变 VLS 路径；
- 不改变 EDS resample / renoise / rollout 核心逻辑；
- 不新增 FPS / oversampling 机制；
- 不扩大到 full OOD evaluation，除非 mechanism gate 和 utility gate 至少部分通过；
- 不把 action-space diversity 当作唯一成功指标。

最终判据：

```text
若 aggressive RBF 仍不能提高 initial_eef_diversity_final 和 endpoint_spread_final，则应停止继续放大 RBF scale，转向更晚注入、final proposal filtering 或 reward selection pressure 修复。
```
