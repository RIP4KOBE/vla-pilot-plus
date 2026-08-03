# RBF-Assisted Truncated Rollout Main Metrics Analysis

Source report: `2026-07-11-rollout-rbf-level3-parameter-sweep.md`

Analysis date: `2026-07-12`

## 1. 分析范围

本文只分析源报告 `## Main Metrics` 表中的 128 组定量结果。实验固定 initial sampler 为：

- `initial_sampling_mode=rbf_diverse_denoise`
- `initial_diversity_scale=20.0`
- `initial_diversity_start_ratio=0.8`

本轮 sweep 的变量为：

- `renoise_t_max`: `[4, 3, 2, 1]`
- `rollout_diversity_scale`: `[5, 10, 15, 20]`
- `rollout_diversity_start_ratio`: `[0.6, 0.8]`
- `rollout_diversity_iters`: `[1, 3, 6, all]`

每个 job 跑 `3` 个 episode，因此 success rate 只能作为机制筛选信号，不能作为最终统计显著结论。

## 2. 总体结果

| 指标 | 结果 |
|---|---:|
| Jobs | 128 |
| Done | 128 |
| Total success | 155 / 384 |
| Overall success rate | 40.36% |
| `3/3` jobs | 1 |
| `2/3` jobs | 62 |
| `1/3` jobs | 28 |
| `0/3` jobs | 37 |
| Fallbacks | 0 |
| Nonfinite | 0 |
| Max action mask violation | 0.000 |

结论：算法实现层面稳定，所有 job 均完成，没有 fallback、nonfinite 或 action mask violation。性能层面存在强参数敏感性，尤其是 `rollout_diversity_iters` 和 `start_ratio`。

## 3. 按 `renoise_t_max` 聚合

| rtmax | jobs | success | SR | Records | EEF after | EEF final | Retention | Endpoint final | Select latency | EDS latency |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 32 | 40/96 | 0.417 | 74.2 | 0.283 | 0.283 | 1.000 | 0.140 | 1.745 | 1.667 |
| 2 | 32 | 40/96 | 0.417 | 75.2 | 0.319 | 0.319 | 1.000 | 0.158 | 1.844 | 1.764 |
| 3 | 32 | 38/96 | 0.396 | 75.7 | 0.290 | 0.217 | 0.708 | 0.108 | 2.291 | 2.208 |
| 4 | 32 | 37/96 | 0.385 | 75.2 | 0.307 | 0.224 | 0.700 | 0.112 | 2.814 | 2.736 |

观察：

- `rtmax=1/2` 的总体 success rate 最高，均为 `40/96 = 41.7%`，并且 latency 明显更低。
- `rtmax=3/4` 的 after-RBF diversity 不低，但 final diversity 被后续 denoise 消除了一部分，retention 只有约 `0.70`。
- `rtmax=4` 出现了唯一 `3/3` 最优单点，但总体均值并不优，说明 `rt4to1` 高潜力但参数敏感。

结论：如果目标是稳健和低延迟，`rt1to1` 或 `rt2to1` 更合适；如果目标是探索高上限，`rt4to1 + start=0.8 + scale=20 + iter=3` 值得继续扩大样本验证。

## 4. 按 rollout RBF scale 聚合

| Scale | jobs | success | SR | EEF after | EEF final | Endpoint final | Select latency |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 32 | 45/96 | 0.469 | 0.153 | 0.133 | 0.067 | 2.171 |
| 10 | 32 | 40/96 | 0.417 | 0.252 | 0.221 | 0.110 | 2.176 |
| 15 | 32 | 35/96 | 0.365 | 0.349 | 0.303 | 0.150 | 2.175 |
| 20 | 32 | 35/96 | 0.365 | 0.445 | 0.384 | 0.190 | 2.171 |

观察：

- Scale 对 diversity 有清晰、近似单调的增强作用。
- `scale=5 -> 20` 时，`EEF final` 从 `0.133` 增至 `0.384`，`Endpoint final` 从 `0.067` 增至 `0.190`。
- 但 success rate 不是单调提升，反而从 `46.9%` 下降到 `36.5%`。

结论：RBF scale 确实有效增强 rollout 后多样性，但过强 diversity 会损害执行成功率。`scale=20` 是高探索设置，不应直接作为默认；`scale=5/10` 更稳健，`scale=15/20` 更适合 OOD 探索候选。

## 5. 按 start ratio 聚合

| Start ratio | jobs | success | SR | EEF after | EEF final | Retention | Endpoint final |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.6 | 64 | 75/192 | 0.391 | 0.281 | 0.203 | 0.704 | 0.102 |
| 0.8 | 64 | 80/192 | 0.417 | 0.318 | 0.318 | 1.000 | 0.157 |

观察：

- `start=0.8` 的 final diversity 和 endpoint spread 都明显高于 `start=0.6`。
- `start=0.8` 的 retention 为 `1.000`，说明 RBF 后几乎没有再被后续 denoise 拉回 prior。
- `start=0.6` 的 retention 只有 `0.704`，说明 RBF 过早注入后仍会被后续 rollout denoise 消除。

更细地看 `rtmax + start`：

| rtmax | start | success | SR | EEF final | Retention | Endpoint final |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.6 | 20/48 | 0.417 | 0.283 | 1.000 | 0.140 |
| 1 | 0.8 | 20/48 | 0.417 | 0.283 | 1.000 | 0.140 |
| 2 | 0.6 | 20/48 | 0.417 | 0.319 | 1.000 | 0.158 |
| 2 | 0.8 | 20/48 | 0.417 | 0.319 | 1.000 | 0.158 |
| 3 | 0.6 | 18/48 | 0.375 | 0.103 | 0.417 | 0.053 |
| 3 | 0.8 | 20/48 | 0.417 | 0.331 | 1.000 | 0.163 |
| 4 | 0.6 | 17/48 | 0.354 | 0.108 | 0.399 | 0.056 |
| 4 | 0.8 | 20/48 | 0.417 | 0.339 | 1.000 | 0.167 |

结论：`start=0.8` 是本轮最明确的机制改进点，尤其对 `rt3to1/rt4to1` 必须保留。`rt1to1/rt2to1` 下 start ratio 基本等效，因为 rollout 太短，RBF 作用后不会再经历明显的 prior pull-back。

## 6. 按 rollout diversity iters 聚合

| Iters | jobs | success | SR | Records | EEF final | Endpoint final | Select latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 32 | 60/96 | 0.625 | 66.2 | 0.257 | 0.127 | 2.034 |
| 3 | 32 | 51/96 | 0.531 | 69.7 | 0.258 | 0.128 | 2.109 |
| 6 | 32 | 44/96 | 0.458 | 74.5 | 0.258 | 0.128 | 2.215 |
| all | 32 | 0/96 | 0.000 | 90.0 | 0.270 | 0.134 | 2.336 |

Success distribution by `iters`：

| Iters | `3/3` | `2/3` | `1/3` | `0/3` |
|---|---:|---:|---:|---:|
| 1 | 0 | 28 | 4 | 0 |
| 3 | 1 | 19 | 10 | 2 |
| 6 | 0 | 15 | 14 | 3 |
| all | 0 | 0 | 0 | 32 |

观察：

- `iters=1` 是最稳健设置，success rate 达到 `62.5%`，且没有 `0/3` job。
- `iters=3` 有唯一 `3/3` 最优单点，但整体 success 低于 `iters=1`。
- `iters=6` 继续下降。
- `iters=all` 全部失败，`32/32` 个 job 都是 `0/3`，Records 全部打满 `90.0`。
- `iters=all` 的 final diversity 略高，但没有转化为成功率，说明“每一轮 EDS rollout 都强行加 RBF”会破坏 exploitation / policy-prior refinement。

结论：`rollout_diversity_iters=all` 不建议继续作为候选；`iters=1` 是默认候选，`iters=3` 是高探索候选。

## 7. Top settings

| Job | Success | rtmax | scale | start | iters | Records | EEF final | Endpoint final | Select latency |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
| `rbf_s20_start08_rt4to1_rollrbf_s20_start08_iter3` | 3/3 | 4 | 20 | 0.8 | 3 | 54 | 0.498 | 0.244 | 2.749 |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start08_iter1` | 2/3 | 3 | 20 | 0.8 | 1 | 65 | 0.490 | 0.240 | 2.166 |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start08_iter3` | 2/3 | 3 | 20 | 0.8 | 3 | 63 | 0.486 | 0.238 | 2.240 |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start08_iter1` | 2/3 | 2 | 20 | 0.8 | 1 | 62 | 0.476 | 0.234 | 1.723 |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start06_iter1` | 2/3 | 2 | 20 | 0.6 | 1 | 62 | 0.476 | 0.234 | 1.729 |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start06_iter1` | 2/3 | 1 | 20 | 0.6 | 1 | 63 | 0.410 | 0.201 | 1.609 |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start08_iter1` | 2/3 | 1 | 20 | 0.8 | 1 | 63 | 0.410 | 0.201 | 1.625 |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start08_iter3` | 2/3 | 1 | 20 | 0.8 | 3 | 66 | 0.409 | 0.200 | 1.654 |

推荐候选：

- 高上限候选：`rt4to1, scale=20, start=0.8, iters=3`。唯一 `3/3`，final diversity 也最高之一，但 latency 较高，需要更多 episode 复验。
- 稳健高探索候选：`rt3to1, scale=20, start=0.8, iters=1`。`2/3`，diversity 高，latency 低于 rt4。
- 低延迟候选：`rt2to1, scale=20, start=0.8, iters=1` 或 `rt1to1, scale=20, start=0.8, iters=1`。success 为 `2/3`，latency 明显更低。
- 默认保守候选：`iters=1`，scale 可在 `10/15` 间折中。若 OOD 需要强探索，再升到 `20`。

## 8. Reward 和 target distance 的解释

`selected_reward` 和 `target_distance_after` 在本表中不能单独作为算法好坏排序指标。原因是：

- `iters=all` 的平均 `target_distance_after=0.049`、`selected_reward=-0.004` 看起来更好，但 success 是 `0/96`。
- `iters=all` 的 Records 是 `90.0`，说明 episode 打满评估长度；成功组通常更早结束，Records 更低。
- 因此 reward / distance 受到 episode 终止、chunk 数量和统计窗口影响，必须与环境 success、Records、qualitative artifacts 一起解释。

结论：本轮主要评价指标应按优先级理解为：

1. environment success；
2. Records 是否过长；
3. rollout diversity retention；
4. action mask / fallback / nonfinite safety；
5. selected_reward 和 target_distance_after 作为辅助调试信号。

## 9. 关键结论

1. RBF-assisted truncated rollout 确实解决了“initial diversity 在 rollout 中被 prior 拉回”的机制问题。`start=0.8` 时 final EEF diversity 与 after-RBF diversity 基本一致，retention 为 `1.000`。

2. 多样性强度不是越大越好。`scale=20` 的 final diversity 最高，但整体 success 低于 `scale=5/10`；这说明 rollout RBF 的作用应是“保留足够探索”，不是每轮强行最大化分散。

3. `rollout_diversity_iters` 是最关键的成功率控制参数。`iters=1` 整体最好，`iters=3` 有最优单点，`iters=all` 全部失败。后续不建议继续测试 `all`，除非加入 decay、elite-only 或 reward-gated RBF。

4. `start_ratio=0.8` 是明确推荐值。特别是在 `rt3to1/rt4to1` 下，`start=0.6` 会被后续 denoise 明显消除，retention 只有约 `0.4`；`start=0.8` 可以保留 diversity 且 success 不差。

5. `rtmax=1/2` 是低延迟稳健区，`rtmax=3/4` 是高探索高敏感区。若要部署默认策略，优先考虑 `rt2to1 + start=0.8 + iters=1`；若要继续 OOD 探索，保留 `rt3/4 + scale=20 + start=0.8 + iters=1/3` 作为候选。

## 10. 推荐下一轮验证配置

建议不要继续全量扫 128 组，而是集中验证以下 6 组，每组增加 episode 数并加入 LIBERO-Pro/OOD：

| 用途 | rtmax | scale | start | iters | 理由 |
|---|---:|---:|---:|---|---|
| 高上限复验 | 4 | 20 | 0.8 | 3 | 本轮唯一 `3/3` |
| 高探索稳健 | 3 | 20 | 0.8 | 1 | diversity 高，latency 比 rt4 低 |
| 高探索折中 | 3 | 20 | 0.8 | 3 | 接近最优单点 |
| 低延迟强探索 | 2 | 20 | 0.8 | 1 | diversity 高，latency 低 |
| 低延迟部署候选 | 1 | 20 | 0.8 | 1 | latency 最低且 `2/3` |
| 保守默认候选 | 2 | 10 | 0.8 | 1 | success/latency/diversity 折中 |

最终判断仍需要更大样本量，因为当前每组只有 3 episodes。
