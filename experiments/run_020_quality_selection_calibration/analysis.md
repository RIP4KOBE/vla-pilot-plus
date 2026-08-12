# run_020 H2 reward-degenerate QD calibration — PASS

Protocol commit：`a0b4cada663c9efa1f611177c2710f84509bc9d7`

Implementation commit：`174630302cbfa6668292bc566c54d3e738159e27`

模式：只读、zero episode、zero GPU、zero API/model/VLM。

## 结论

六个预注册 calibration gates 全部 PASS。结果授权且只授权一个后续候选 protocol：`reward_degenerate_control_fallback_v1`。当前尚未修改核心算法，也未授权 GPU/LIBERO episode。

当前 QD 的 exact-degenerate quality 不是边缘现象：50 个 raw metrics 文件中的 7,080 条 valid QD rows 里，去重后有 473 个 final archive rewards 全部 exact zero，覆盖 tasks 0–9。历史层 411 条、owned v1 层 62 条。Retrospective outcome 分层为 468 fail、5 success；该分层说明 defect 与失败高度共现，但不能单独证明因果，5 个 success 也明确阻止“exact-zero 必然失败”的过度结论。

## 直接机制证据

1. Frozen Stage-2 guidance SHA-256 `ca058cc1dcf87ce5910181800bb2f65b8cd4d92788b27f3b10b1e33dbc103f84`，AST 验证唯一 return 为 exact `torch.tensor(0.0, ...)`。
2. 当前 `core/qd_ed.py` 在 equal reward 下按 fingerprint 决定 cell winner/global winner；quality 不再区分 action。
3. 44 个 owned QD mechanism traces 均精确重放 recorded reward/fingerprint global selection（44/44），其 nondegenerate selection identity 全部保持（44/44）。
4. 把同一 final archive 的 quality observer-only 等值后，smallest 与 largest fingerprint tie policy 在 44/44 traces 选择不同 action；反转 input iteration order 仍在 44/44 选择同一个 smallest fingerprint。这证明 current choice 与输入顺序无关，但完全依赖 task-agnostic hash tie。
5. Static control-path audit 确认 QD guard 下已存在 non-QD `argmin(population_scores)` selection 和固定 CEM iteration loop；候选可保持 complete chunk `176` evaluations / `11` score calls，不需额外模型或 reward call。

QD 文献把 archive 定义为每个 behavior niche 的 high-performing elite；quality 必须提供 cell-local/global exploitation 的比较语义。[MAP-Elites 原始论文](https://arxiv.org/abs/1504.04909)和[QD optimization 综述](https://arxiv.org/abs/2012.04322)支持该一般边界。本次候选动机仍以本地 code/raw evidence 为主，不从文献推断 task gain。

## Gate 结果

| Gate | 结果 | 证据 |
| --- | --- | --- |
| >=20 exact-degenerate chunks | PASS | 473 |
| >=5 tasks | PASS | 10/10 tasks |
| Stage-2 exact zero | PASS | source SHA / AST |
| fingerprint tie task-agnostic | PASS | 44/44 tie-policy action changes；44/44 input-order invariant |
| existing fixed-compute control path | PASS | projected 176 evaluations / 11 calls |
| nondegenerate selection preserved | PASS | 44/44 |

## Task 分布

```text
task 0:   1
task 1:  23
task 2: 109
task 3:  97
task 4: 131
task 5:  23
task 6:  12
task 7:  22
task 8:  21
task 9:  34
```

Exact zero 并不均匀：tasks 2/3/4 占多数，因此后续机制 preflight 必须包含不同 task，而不能从 count 直接预测新 Dev/Validation success。

## Artifacts 与确定性

- Canonical：`/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_020_quality_selection_calibration/analysis/calibration.v1.json`
- Replay：同目录 `calibration.replay.v1.json`
- 两文件 mode `0444`，size `505,982` bytes，file SHA-256 均为 `56c05f906528de78d720d99366b8db39e7ec84518968c8ec01cb9508ceb31034`。
- Payload analysis SHA-256：`62ec462243cc3f5690e0c374a122f2ca55b887fa0eaaac0e6064fb2f0edbaa87`。
- Credential match count `0`；online attempts `0`；GPU-hours `0.0`。
- Tests：new diagnostic `7 passed`；existing QD archive/runner/audit regression `60 passed`。

## Target impact 与决策

没有运行 task episode，所以 historical formal best 仍为 `2/10`、formal target gap 仍为 `3`；不能用 473 个 proxy rows 宣称成功率提高。

Decision：`KEEP_H2_CALIBRATION_PASS_AND_AUTHORIZE_ONE_QD1_PROTOCOL`。

下一步必须先提交独立 implementation protocol，冻结 exact-degeneracy 语义、TDD、metrics、nondegenerate equivalence、176/11 accounting 与 offline mechanism gates；protocol commit 前不得修改 core/config。
