# Protocol — run_021 reward-degenerate QD control fallback implementation

Status: `LOCKED BEFORE CORE/CONFIG IMPLEMENTATION`

Parent evidence：run_020 result commit `3065fad8f248292aeb680d4b8b93d212f01d799b`，canonical artifact file SHA-256 `56c05f906528de78d720d99366b8db39e7ec84518968c8ec01cb9508ceb31034`。

Hypothesis：H2-v2。Algorithm iteration：`2`（H1 causal envelope substrate + one H2 change）。

本 protocol 只授权 TDD、最小 core/config/metrics 实现和 CPU offline gate；不授权 GPU admission、model/API/VLM、LIBERO episode、attempt reservation、Dev/Validation/Formal 或 shared2 新在线 run root。

## 唯一算法变化

新增 config：

```text
eds.qd_degenerate_fallback_policy: none | control_v1
```

Default `none` 必须完全保持 legacy 行为。候选 profile 才设置 `control_v1`。

触发点固定在 initial population 完成正常 scoring、finite/shape validation 和 reward extraction 之后，QD archive 创建之前。仅当以下条件全部成立才触发：

```text
qd_archive_mode == grid_archive
qd_degenerate_fallback_policy == control_v1
population_rewards nonempty and finite
all rewards exactly equal to rewards[0]
```

不使用 epsilon、近似阈值、Stage ID、guidance source name、task ID、job label、future observation、success/evaluator result 或 formal/validation outcome。

触发后：

- 当前 chunk 不创建 QD archive、不执行 QD parent allocation/replacement/final selection；
- 复用同一函数内已存在的 non-QD EDS control path，继续完整 `cem_iters=10`；
- complete chunk 总 candidate evaluations 保持 `16 + 10*16 = 176`，score calls 保持 `11`；
- Stage/guidance、EDS sampler/rollout、action mask、execution horizon 和所有非 QD 逻辑不变；
- 下一 chunk 重新因果判断，不保留 hidden fallback state。

未触发时，causal-envelope QD 必须与 parent commit fixed-input identity 一致，包括 archive snapshots、global selected fingerprint、score/evaluation accounting、RNG consumption 和 metrics 旧字段。

## Metrics

在 `EDSChunkMetrics` 新增并序列化：

```text
qd_degenerate_fallback_policy
qd_degenerate_fallback_used
qd_degenerate_fallback_reason
qd_degenerate_reward_value
qd_archive_active_for_chunk
search_evaluation_count
```

语义：`qd_archive_enabled` 继续表示 config requested；`qd_archive_active_for_chunk` 表示本 chunk 是否真实建立 archive。Fallback chunk 的 `qd_evaluation_count=0`（没有 QD archive evaluation），但 `search_evaluation_count=176`。非 fallback QD complete chunk 两者均为 176。Failure/early stop 必须如实记录实际 count。

## 允许修改的文件

- `core/rdt_policy_steer.py`
- `core/eds_eval_metrics.py`
- `configs/config.yaml`
- `tests/test_rdt_steer.py`

如测试必须增加一个新、专用 test file，可在 implementation commit 前追加 protocol amendment；不得顺手修改 runner、audit、Stage、prompt、perception 或 protected untracked design。

## TDD 与 offline PASS gates

先建立失败测试，再实现。至少覆盖：

1. default `none` 和 invalid enum validation；
2. exact-zero、equal-nonzero 触发；`1e-12` 差异不触发；nonfinite fail closed；
3. `grid_archive + control_v1 + exact-degenerate` 不创建/调用 QD archive；
4. fallback 使用 existing non-QD final selection，selected source 不是 `qd_archive`；
5. `grid_archive + none + exact-degenerate` 保持 legacy fingerprint-tied QD path；
6. nondegenerate `control_v1` 与 `none` fixed-input selected action/fingerprint/archive/metrics identity（仅新增 policy/active 字段允许不同）；
7. `qd_archive_mode=none` 不受新 policy 影响；
8. fallback 与 active QD complete chunk 均 `search_evaluation_count=176`、`score_call_count=11`；fallback `qd_evaluation_count=0`；
9. action-mask/nonfinite/accounting/selection mismatch 回归；
10. 新 metrics 可 JSONL 序列化，legacy readers 对缺失新字段兼容。

PASS 要求：专用测试全部通过；现有 QD archive/runner/audit、autoresearch runner 和相关 `test_rdt_steer` 回归全部通过；py_compile PASS；Git diff 只含允许文件；credential/write-boundary scan PASS。

## Decision

Implementation PASS 只授权一个独立 offline mechanism preflight protocol，用 synthetic exact-zero/nondegenerate streams 冻结候选 hashes 和 176/11 accounting。实现/测试 FAIL 最多允许一次 protocol-first root-cause repair；仍 FAIL 则 `CONCLUDE_H2_IMPLEMENTATION_INVALID`。任何 online dispatch 都需要之后的新 protocol 与 immutable manifest。
