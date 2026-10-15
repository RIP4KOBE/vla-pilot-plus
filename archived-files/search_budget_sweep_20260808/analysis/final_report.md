# EDS-QD 搜索预算 Sweep 最终报告

> 18 个候选共享固定的 10-task Object-Swap 集；结果是工程 gate 证据，不代表统计显著性或 held-out 泛化。历史 p16_k10 仅作跨轮背景比较。

## 执行摘要

- Completion：`complete`，jobs `18`，accepted episodes `180/180`。
- Attempts：physical `201/200`；ledger reserved `200`；recovery `20`；hard cap `FAIL`；user soft override `True`。
- Decision：`no_configuration_passed_task_and_safety_gates`；存在 5/10 配置：`False`。
- Credential / storage / GPU audit：`PASS` / `PASS` / `PASS`。
- Execution exception：`True`；provenance `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/outputs/search_budget_sweep_20260808/output_store/stale/formal/recovery_tool_timeout_20260808T215900Z/eds_qd_uniform_expand20_p48_k20/interruption_provenance.json`；audit `PASS`。

## 18-job 定量结果与 gates

| Job | Status | Success | Tasks | Task | Mechanism | Safety | Eval/chunk | Candidates/success | Select P95 s |
| --- | --- | ---: | --- | --- | --- | --- | ---: | ---: | ---: |
| `eds_qd_uniform_expand20_p32_k15` | valid | 1/10 | [7] | FAIL | PASS | PASS | 512 | 95744 | 6.834 |
| `eds_qd_uniform_expand20_p32_k20` | valid | 0/10 | [] | FAIL | PASS | PASS | 672 | — | 8.602 |
| `eds_qd_uniform_expand20_p32_k25` | valid | 1/10 | [9] | FAIL | PASS | PASS | 832 | 166400 | 10.405 |
| `eds_qd_uniform_expand20_p48_k15` | valid | 0/10 | [] | FAIL | PASS | PASS | 768 | — | 9.979 |
| `eds_qd_uniform_expand20_p48_k20` | valid | 1/10 | [9] | FAIL | PASS | PASS | 1008 | 290304 | 12.476 |
| `eds_qd_uniform_expand20_p48_k25` | valid | 1/10 | [9] | FAIL | PASS | PASS | 1248 | 164736 | 15.261 |
| `eds_qd_uniform_expand20_p64_k15` | valid | 0/10 | [] | FAIL | PASS | PASS | 1024 | — | 13.297 |
| `eds_qd_uniform_expand20_p64_k20` | valid | 0/10 | [] | FAIL | PASS | PASS | 1344 | — | 16.510 |
| `eds_qd_uniform_expand20_p64_k25` | valid | 0/10 | [] | FAIL | PASS | PASS | 1664 | — | 20.389 |
| `eds_qd_sparse_primary_p32_k15` | valid | 0/10 | [] | FAIL | PASS | PASS | 512 | — | 6.746 |
| `eds_qd_sparse_primary_p32_k20` | valid | 1/10 | [0] | FAIL | PASS | PASS | 672 | 135072 | 8.534 |
| `eds_qd_sparse_primary_p32_k25` | valid | 1/10 | [8] | FAIL | PASS | PASS | 832 | 164736 | 10.462 |
| `eds_qd_sparse_primary_p48_k15` | valid | 0/10 | [] | FAIL | PASS | PASS | 768 | — | 9.923 |
| `eds_qd_sparse_primary_p48_k20` | valid | 0/10 | [] | FAIL | PASS | PASS | 1008 | — | 12.367 |
| `eds_qd_sparse_primary_p48_k25` | valid | 0/10 | [] | FAIL | PASS | PASS | 1248 | — | 15.201 |
| `eds_qd_sparse_primary_p64_k15` | valid | 0/10 | [] | FAIL | PASS | PASS | 1024 | — | 13.216 |
| `eds_qd_sparse_primary_p64_k20` | valid | 1/10 | [0] | FAIL | PASS | FAIL | 1344 | 254016 | 16.503 |
| `eds_qd_sparse_primary_p64_k25` | valid | 1/10 | [8] | FAIL | PASS | PASS | 1664 | 274560 | 20.308 |

## Task-level outcome

| Task | `eds_qd_uniform_expand20_p32_k15` | `eds_qd_uniform_expand20_p32_k20` | `eds_qd_uniform_expand20_p32_k25` | `eds_qd_uniform_expand20_p48_k15` | `eds_qd_uniform_expand20_p48_k20` | `eds_qd_uniform_expand20_p48_k25` | `eds_qd_uniform_expand20_p64_k15` | `eds_qd_uniform_expand20_p64_k20` | `eds_qd_uniform_expand20_p64_k25` | `eds_qd_sparse_primary_p32_k15` | `eds_qd_sparse_primary_p32_k20` | `eds_qd_sparse_primary_p32_k25` | `eds_qd_sparse_primary_p48_k15` | `eds_qd_sparse_primary_p48_k20` | `eds_qd_sparse_primary_p48_k25` | `eds_qd_sparse_primary_p64_k15` | `eds_qd_sparse_primary_p64_k20` | `eds_qd_sparse_primary_p64_k25` |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | success | fail | fail | fail | fail | fail | success | fail |
| 1 | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail |
| 2 | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail |
| 3 | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail |
| 4 | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail |
| 5 | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail |
| 6 | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail |
| 7 | success | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail |
| 8 | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | success | fail | fail | fail | fail | fail | success |
| 9 | fail | fail | success | fail | success | success | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail |

## QD mechanism 与历史同-family 背景

| Job | Coverage | Spread m | Replacement-active | Turnover | Overflow P95 | Best reward | Δbest vs history |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `eds_qd_uniform_expand20_p32_k15` | 1.000 | 0.068 | 1.000 | 0.031 | 0.812 | -0.000595 | 0.000080 |
| `eds_qd_uniform_expand20_p32_k20` | 1.000 | 0.058 | 1.000 | 0.031 | 0.875 | -0.000277 | 0.000399 |
| `eds_qd_uniform_expand20_p32_k25` | 1.000 | 0.070 | 1.000 | 0.031 | 0.812 | -0.000755 | -0.000080 |
| `eds_qd_uniform_expand20_p48_k15` | 1.000 | 0.057 | 1.000 | 0.021 | 0.792 | -0.000292 | 0.000383 |
| `eds_qd_uniform_expand20_p48_k20` | 1.000 | 0.061 | 1.000 | 0.021 | 0.792 | -0.000271 | 0.000404 |
| `eds_qd_uniform_expand20_p48_k25` | 1.000 | 0.074 | 1.000 | 0.021 | 0.771 | -0.001606 | -0.000931 |
| `eds_qd_uniform_expand20_p64_k15` | 1.000 | 0.059 | 1.000 | 0.031 | 0.766 | -0.000368 | 0.000307 |
| `eds_qd_uniform_expand20_p64_k20` | 1.000 | 0.070 | 1.000 | 0.016 | 0.750 | -0.000211 | 0.000464 |
| `eds_qd_uniform_expand20_p64_k25` | 1.000 | 0.056 | 1.000 | 0.016 | 0.750 | -0.000525 | 0.000151 |
| `eds_qd_sparse_primary_p32_k15` | 1.000 | 0.071 | 1.000 | 0.031 | 0.875 | -0.000647 | 0.001329 |
| `eds_qd_sparse_primary_p32_k20` | 1.000 | 0.059 | 1.000 | 0.031 | 0.875 | -0.000675 | 0.001301 |
| `eds_qd_sparse_primary_p32_k25` | 1.000 | 0.057 | 1.000 | 0.031 | 0.875 | -0.000353 | 0.001623 |
| `eds_qd_sparse_primary_p48_k15` | 1.000 | 0.071 | 1.000 | 0.042 | 0.833 | -0.000284 | 0.001692 |
| `eds_qd_sparse_primary_p48_k20` | 1.000 | 0.050 | 1.000 | 0.021 | 0.833 | -0.000374 | 0.001602 |
| `eds_qd_sparse_primary_p48_k25` | 1.000 | 0.058 | 1.000 | 0.021 | 0.833 | -0.000639 | 0.001337 |
| `eds_qd_sparse_primary_p64_k15` | 1.000 | 0.054 | 1.000 | 0.031 | 0.797 | -0.000547 | 0.001429 |
| `eds_qd_sparse_primary_p64_k20` | 1.000 | 0.061 | 1.000 | 0.016 | 0.797 | -0.000374 | 0.001602 |
| `eds_qd_sparse_primary_p64_k25` | 1.000 | 0.055 | 1.000 | 0.016 | 0.797 | -0.000572 | 0.001404 |

## 参数主效应与等预算 breadth/depth

完整 grid 可估计：`True`；complete valid 2x3x3 grids。主效应为描述性均值，不把不同总候选预算误作单参数因果效应。

| Family | Factor | Level | Mean success | Replacement-active median | Select P95 median s |
| --- | --- | ---: | ---: | ---: | ---: |
| sparse_primary | population_size | 32 | 0.667 | 1.000 | 8.534 |
| sparse_primary | population_size | 48 | 0.000 | 1.000 | 12.367 |
| sparse_primary | population_size | 64 | 0.667 | 1.000 | 16.503 |
| sparse_primary | cem_iters | 15 | 0.000 | 1.000 | 9.923 |
| sparse_primary | cem_iters | 20 | 0.667 | 1.000 | 12.367 |
| sparse_primary | cem_iters | 25 | 0.667 | 1.000 | 15.201 |
| uniform_expand20 | population_size | 32 | 0.667 | 1.000 | 8.602 |
| uniform_expand20 | population_size | 48 | 0.667 | 1.000 | 12.476 |
| uniform_expand20 | population_size | 64 | 0.000 | 1.000 | 16.510 |
| uniform_expand20 | cem_iters | 15 | 0.333 | 1.000 | 9.979 |
| uniform_expand20 | cem_iters | 20 | 0.333 | 1.000 | 12.476 |
| uniform_expand20 | cem_iters | 25 | 0.667 | 1.000 | 15.261 |

### 近似等预算配对

| Family | Left | Right | Eval ratio L/R | Δsuccess L-R | Δbest reward L-R | Latency ratio L/R |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| uniform_expand20 | p32_k25 | p48_k15 | 1.083 | 1 | -0.000463 | 1.043 |
| uniform_expand20 | p48_k20 | p64_k15 | 0.984 | 1 | 0.000097 | 0.938 |
| uniform_expand20 | p48_k25 | p64_k20 | 0.929 | 1 | -0.001395 | 0.924 |
| sparse_primary | p32_k25 | p48_k15 | 1.083 | 1 | -0.000069 | 1.054 |
| sparse_primary | p48_k20 | p64_k15 | 0.984 | 0 | 0.000174 | 0.936 |
| sparse_primary | p48_k25 | p64_k20 | 0.929 | -1 | -0.000265 | 0.921 |

## Safety、latency 与失败审计

| Job | qpos | collision composite | nonfinite | mask | fallback | Job wall s | Episode wall mean s | Failure taxonomy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `eds_qd_uniform_expand20_p32_k15` | 0 | 0 | 0 | 0 | 0 | 2802.7 | 280.3 | success:1, timeout without completion:9 |
| `eds_qd_uniform_expand20_p32_k20` | 0 | 0 | 0 | 0 | 0 | 4387.8 | 438.8 | timeout without completion:10 |
| `eds_qd_uniform_expand20_p32_k25` | 0 | 0 | 0 | 0 | 0 | 4585.8 | 458.6 | success:1, timeout without completion:9 |
| `eds_qd_uniform_expand20_p48_k15` | 0 | 0 | 0 | 0 | 0 | 4523.8 | 452.4 | timeout without completion:10 |
| `eds_qd_uniform_expand20_p48_k20` | 0 | 0 | 0 | 0 | 0 | 2038.1 | 203.8 | success:1, timeout without completion:9 |
| `eds_qd_uniform_expand20_p48_k25` | 0 | 0 | 0 | 0 | 0 | 4585.2 | 458.5 | success:1, timeout without completion:9 |
| `eds_qd_uniform_expand20_p64_k15` | 0 | 0 | 0 | 0 | 0 | 4493.2 | 449.3 | timeout without completion:10 |
| `eds_qd_uniform_expand20_p64_k20` | 0 | 0 | 0 | 0 | 0 | 4812.7 | 481.3 | timeout without completion:10 |
| `eds_qd_uniform_expand20_p64_k25` | 0 | 0 | 0 | 0 | 0 | 5084.5 | 508.4 | timeout without completion:10 |
| `eds_qd_sparse_primary_p32_k15` | 0 | 0 | 0 | 0 | 0 | 2900.7 | 290.1 | timeout without completion:10 |
| `eds_qd_sparse_primary_p32_k20` | 0 | 0 | 0 | 0 | 0 | 3442.8 | 344.3 | success:1, timeout without completion:9 |
| `eds_qd_sparse_primary_p32_k25` | 0 | 0 | 0 | 0 | 0 | 3742.1 | 374.2 | success:1, timeout without completion:9 |
| `eds_qd_sparse_primary_p48_k15` | 0 | 0 | 0 | 0 | 0 | 3131.0 | 313.1 | timeout without completion:10 |
| `eds_qd_sparse_primary_p48_k20` | 0 | 0 | 0 | 0 | 0 | 3924.5 | 392.4 | timeout without completion:10 |
| `eds_qd_sparse_primary_p48_k25` | 0 | 0 | 0 | 0 | 0 | 4380.4 | 438.0 | timeout without completion:10 |
| `eds_qd_sparse_primary_p64_k15` | 0 | 0 | 0 | 0 | 0 | 4353.1 | 435.3 | timeout without completion:10 |
| `eds_qd_sparse_primary_p64_k20` | 1 | 0 | 0 | 0 | 0 | 5063.7 | 506.4 | qpos/execution error:1, success:1, timeout without completion:8 |
| `eds_qd_sparse_primary_p64_k25` | 0 | 0 | 0 | 0 | 0 | 5309.1 | 530.9 | success:1, timeout without completion:9 |

## 排名与结论

无 valid 且同时通过 task/safety gates 的候选。

## 证据局限

- 每配置仅 10 个固定 tasks，各一个 episode；18 候选 winner selection 存在选择偏差，不能解释为统计显著。
- 本轮没有 contemporaneous control/reference；历史差异可能混入跨轮基础设施、API 与时序波动。
- population 与 iterations 改变总候选数；仅等预算配对适合谨慎讨论 breadth/depth，其余响应面是描述性结果。
- 失败 taxonomy 优先依据错误栈和 telemetry；无明确因果证据的未完成轨迹保守标为 timeout，不以成功率反推原因。
- Raw videos、metrics、trace 与 QD qualitative artifacts 保留在每个 job 输出目录，未补跑或追加 winner confirmation。
