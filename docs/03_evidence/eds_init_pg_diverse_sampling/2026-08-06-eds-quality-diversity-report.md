# EDS Quality-Diversity / LIBERO Object-Swap OOD 最终报告

> 本报告只描述预注册的 10 个固定 Object-Swap tasks 上的 paired engineering evidence；不宣称统计显著性、总体泛化或 QD 理论普遍成立。

## 执行与 provenance

- Base commit：`b3db98cf4fd98a6479d92683e33ebe3d032f25d9`；QD code commit：`53187e6ea8b69e9f830c10be0bc25757db5d2794`。
- Decision：`no_adoption_keep_p2_stage_on_abs_rbf_control`。
- Completion：`complete`；mechanism preflight：`PASS`；formal：`110/110`（`completed`）。
- Stop reason：None。
- Attempts：实际 episode attempts `134/134`；recovery `18`；pre-episode aborted `18`；ledger `PASS`。
- Storage：`/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/outputs`；credential scan `PASS`。

## 11-job 完整结果

| Job | Execution | Valid | Success | SR | Wilson 95% | qpos | collision composite |
| --- | --- | --- | ---: | ---: | --- | ---: | ---: |
| `p2_stage_on_abs_rbf_control` | artifacts_present | PASS | 3/10 | 0.300 | [0.108, 0.603] | 0 | 0 |
| `eds_quality_diversity_uniform_primary` | artifacts_present | PASS | 0/10 | 0.000 | [0.000, 0.278] | 0 | 0 |
| `eds_quality_diversity_sparse_primary` | artifacts_present | PASS | 2/10 | 0.200 | [0.057, 0.510] | 0 | 0 |
| `eds_quality_diversity_uniform_grid3` | artifacts_present | PASS | 0/10 | 0.000 | [0.000, 0.278] | 0 | 0 |
| `eds_quality_diversity_uniform_grid5` | artifacts_present | FAIL | 0/10 | 0.000 | [0.000, 0.278] | 10 | 0 |
| `eds_quality_diversity_uniform_q00100` | artifacts_present | PASS | 0/10 | 0.000 | [0.000, 0.278] | 0 | 0 |
| `eds_quality_diversity_uniform_q1090` | artifacts_present | PASS | 1/10 | 0.100 | [0.018, 0.404] | 1 | 0 |
| `eds_quality_diversity_uniform_expand00` | artifacts_present | PASS | 1/10 | 0.100 | [0.018, 0.404] | 0 | 0 |
| `eds_quality_diversity_uniform_expand20` | artifacts_present | PASS | 2/10 | 0.200 | [0.057, 0.510] | 0 | 0 |
| `eds_quality_diversity_uniform_span04` | artifacts_present | PASS | 0/10 | 0.000 | [0.000, 0.278] | 0 | 0 |
| `eds_quality_diversity_uniform_span12` | artifacts_present | PASS | 0/10 | 0.000 | [0.000, 0.278] | 0 | 0 |

## Task-level paired outcome

| Task | `p2_stage_on_abs_rbf_control` | `eds_quality_diversity_uniform_primary` | `eds_quality_diversity_sparse_primary` | `eds_quality_diversity_uniform_grid3` | `eds_quality_diversity_uniform_grid5` | `eds_quality_diversity_uniform_q00100` | `eds_quality_diversity_uniform_q1090` | `eds_quality_diversity_uniform_expand00` | `eds_quality_diversity_uniform_expand20` | `eds_quality_diversity_uniform_span04` | `eds_quality_diversity_uniform_span12` |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | fail | fail | fail | fail | — | fail | success | fail | fail | fail | fail |
| 1 | fail | fail | fail | fail | — | fail | fail | fail | fail | fail | fail |
| 2 | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail |
| 3 | success | fail | fail | fail | — | fail | fail | fail | fail | fail | fail |
| 4 | fail | fail | fail | fail | — | fail | fail | fail | fail | fail | fail |
| 5 | fail | fail | success | fail | fail | fail | fail | fail | success | fail | fail |
| 6 | fail | fail | fail | fail | — | fail | fail | fail | fail | fail | fail |
| 7 | fail | fail | fail | fail | — | fail | fail | fail | success | fail | fail |
| 8 | success | fail | success | fail | fail | fail | fail | success | fail | fail | fail |
| 9 | success | fail | fail | fail | fail | fail | fail | fail | fail | fail | fail |

## 机制与三类 gates

LIBERO mechanism preflight：`PASS`；formal：`110/110`。下表严格使用冻结阈值；validity、task、mechanism hard/claim 与 safety 任一失败即不得 adoption。

| Candidate | Task | Mechanism hard | Mechanism claim | Safety | All | Δcoverage median | spread ratio | Δbest reward | replacement-active | overflow P95 |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| `eds_quality_diversity_uniform_primary` | FAIL | PASS | FAIL | PASS | FAIL | 0.000 | 0.945 | 0.001 | 0.364 | 0.938 |
| `eds_quality_diversity_sparse_primary` | FAIL | PASS | FAIL | PASS | FAIL | 0.000 | 0.976 | 0.000 | 0.190 | 0.938 |
| `eds_quality_diversity_uniform_grid3` | FAIL | PASS | FAIL | PASS | FAIL | 0.000 | 0.914 | 0.002 | 0.319 | 0.938 |
| `eds_quality_diversity_uniform_grid5` | FAIL | PASS | FAIL | FAIL | FAIL | 0.000 | 1.021 | 0.000 | 0.455 | 0.972 |
| `eds_quality_diversity_uniform_q00100` | FAIL | PASS | FAIL | PASS | FAIL | 0.000 | 1.051 | 0.001 | 0.316 | 0.938 |
| `eds_quality_diversity_uniform_q1090` | FAIL | PASS | FAIL | FAIL | FAIL | 0.000 | 1.024 | 0.000 | 0.461 | 1.000 |
| `eds_quality_diversity_uniform_expand00` | FAIL | PASS | FAIL | PASS | FAIL | 0.000 | 0.953 | 0.001 | 0.286 | 1.000 |
| `eds_quality_diversity_uniform_expand20` | FAIL | PASS | FAIL | PASS | FAIL | 0.000 | 0.947 | 0.001 | 0.210 | 0.938 |
| `eds_quality_diversity_uniform_span04` | FAIL | PASS | FAIL | PASS | FAIL | 0.000 | 0.940 | 0.001 | 0.365 | 0.938 |
| `eds_quality_diversity_uniform_span12` | FAIL | PASS | FAIL | PASS | FAIL | 0.000 | 0.943 | 0.001 | 0.281 | 0.938 |

### Paired gained/lost/retained tasks

| Candidate | Gained | Lost | Retained control | Δ(gained-lost) |
| --- | --- | --- | --- | ---: |
| `eds_quality_diversity_uniform_primary` | [] | [3, 8, 9] | [] | -3 |
| `eds_quality_diversity_sparse_primary` | [5] | [3, 9] | [8] | -1 |
| `eds_quality_diversity_uniform_grid3` | [] | [3, 8, 9] | [] | -3 |
| `eds_quality_diversity_uniform_grid5` | [] | [3, 8, 9] | [] | -3 |
| `eds_quality_diversity_uniform_q00100` | [] | [3, 8, 9] | [] | -3 |
| `eds_quality_diversity_uniform_q1090` | [0] | [3, 8, 9] | [] | -2 |
| `eds_quality_diversity_uniform_expand00` | [] | [3, 9] | [8] | -2 |
| `eds_quality_diversity_uniform_expand20` | [5, 7] | [3, 8, 9] | [] | -1 |
| `eds_quality_diversity_uniform_span04` | [] | [3, 8, 9] | [] | -3 |
| `eds_quality_diversity_uniform_span12` | [] | [3, 8, 9] | [] | -3 |

## 单因素主效应

以下均相对 uniform primary；sparse 行只归因 parent sampler，其余为预注册 OFAT。

| Job | Factor | Δsuccess | Δcoverage gain | Δspread retention | Δbest reward |
| --- | --- | ---: | ---: | ---: | ---: |
| `eds_quality_diversity_sparse_primary` | parent sampling | 2 | 0.000 | 0.031 | -0.001 |
| `eds_quality_diversity_uniform_grid3` | grid 3x3 | 0 | 0.000 | -0.031 | 0.001 |
| `eds_quality_diversity_uniform_grid5` | grid 5x5 | 0 | 0.000 | 0.076 | -0.001 |
| `eds_quality_diversity_uniform_q00100` | quantiles .00/.100 | 0 | 0.000 | 0.106 | 0.001 |
| `eds_quality_diversity_uniform_q1090` | quantiles .10/.90 | 1 | 0.000 | 0.079 | -0.001 |
| `eds_quality_diversity_uniform_expand00` | expand .00 | 1 | 0.000 | 0.009 | 0.000 |
| `eds_quality_diversity_uniform_expand20` | expand .20 | 2 | 0.000 | 0.002 | 0.001 |
| `eds_quality_diversity_uniform_span04` | min span .04 m | 0 | 0.000 | -0.005 | 0.000 |
| `eds_quality_diversity_uniform_span12` | min span .12 m | 0 | 0.000 | -0.002 | 0.000 |

## Archive、几何与 parent allocation

| Job | Active chunks | Exact replay | Coverage median | Turnover median | Overflow P95 | Endpoint spread m | EEF direction diversity | Global-best reward median |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `p2_stage_on_abs_rbf_control` | 128 | — | — | — | — | — | 3.856 | — |
| `eds_quality_diversity_uniform_primary` | 140 | PASS | 1.000 | 0.125 | 0.938 | 0.081 | 3.884 | -0.002 |
| `eds_quality_diversity_sparse_primary` | 226 | PASS | 1.000 | 0.125 | 0.938 | 0.090 | 3.827 | -0.002 |
| `eds_quality_diversity_uniform_grid3` | 138 | PASS | 1.000 | 0.062 | 0.938 | 0.092 | 3.819 | -0.002 |
| `eds_quality_diversity_uniform_grid5` | 11 | PASS | 0.920 | 0.188 | 1.000 | 0.075 | 3.897 | -0.003 |
| `eds_quality_diversity_uniform_q00100` | 117 | PASS | 1.000 | 0.125 | 0.938 | 0.118 | 3.892 | -0.001 |
| `eds_quality_diversity_uniform_q1090` | 115 | PASS | 1.000 | 0.125 | 1.000 | 0.080 | 3.874 | -0.002 |
| `eds_quality_diversity_uniform_expand00` | 189 | PASS | 1.000 | 0.062 | 1.000 | 0.073 | 3.907 | -0.001 |
| `eds_quality_diversity_uniform_expand20` | 248 | PASS | 1.000 | 0.062 | 0.938 | 0.077 | 3.912 | -0.001 |
| `eds_quality_diversity_uniform_span04` | 137 | PASS | 1.000 | 0.062 | 0.938 | 0.080 | 3.888 | -0.002 |
| `eds_quality_diversity_uniform_span12` | 153 | PASS | 1.000 | 0.062 | 0.938 | 0.074 | 3.877 | -0.001 |

### Selected cells 与 per-cell final elite reward median

以下 cell reward 只在同一 job/chunk 定义下作为 archive 证据，不解释为跨 task 可比的经典 QD-score。

| Job | Selected-cell counts | Per-cell elite reward median |
| --- | --- | --- |
| `eds_quality_diversity_uniform_primary` | 0:11, 1:6, 10:3, 11:9, 12:6, 13:6, 14:8, 15:11, 2:7, 3:25, 4:9, 5:6, 6:7, 7:12, 8:9, 9:5 | 0:-0.008, 1:-0.007, 10:-0.008, 11:-0.006, 12:-0.011, 13:-0.010, 14:-0.009, 15:-0.007, 2:-0.005, 3:-0.006, 4:-0.009, 5:-0.008, 6:-0.007, 7:-0.005, 8:-0.009, 9:-0.009 |
| `eds_quality_diversity_sparse_primary` | 0:34, 1:18, 10:6, 11:19, 12:19, 13:1, 14:4, 15:14, 2:14, 3:26, 4:14, 5:4, 6:8, 7:17, 8:20, 9:8 | 0:-0.004, 1:-0.005, 10:-0.008, 11:-0.008, 12:-0.008, 13:-0.009, 14:-0.011, 15:-0.011, 2:-0.006, 3:-0.007, 4:-0.005, 5:-0.007, 6:-0.008, 7:-0.008, 8:-0.006, 9:-0.008 |
| `eds_quality_diversity_uniform_grid3` | 0:8, 1:9, 2:23, 3:12, 4:8, 5:19, 6:13, 7:16, 8:30 | 0:-0.008, 1:-0.007, 2:-0.005, 3:-0.007, 4:-0.007, 5:-0.004, 6:-0.007, 7:-0.007, 8:-0.005 |
| `eds_quality_diversity_uniform_grid5` | 0:2, 11:1, 13:1, 14:1, 3:1, 4:1, 5:1, 6:3 | 0:-0.005, 1:-0.005, 10:-0.003, 11:-0.003, 12:-0.008, 13:-0.015, 14:-0.017, 15:-0.004, 16:-0.020, 17:-0.004, 18:-0.020, 19:-0.012, 2:-0.009, 20:-0.004, 21:-0.010, 22:-0.006, 23:-0.008, 24:-0.009, 3:-0.007, 4:-0.006, 5:-0.003, 6:-0.004, 7:-0.012, 8:-0.041, 9:-0.013 |
| `eds_quality_diversity_uniform_q00100` | 0:8, 1:3, 10:3, 11:11, 12:11, 13:4, 14:5, 15:10, 2:6, 3:17, 4:5, 5:5, 6:6, 7:11, 8:7, 9:5 | 0:-0.004, 1:-0.003, 10:-0.002, 11:-0.003, 12:-0.005, 13:-0.003, 14:-0.003, 15:-0.004, 2:-0.003, 3:-0.003, 4:-0.002, 5:-0.001, 6:-0.002, 7:-0.003, 8:-0.002, 9:-0.002 |
| `eds_quality_diversity_uniform_q1090` | 0:14, 1:3, 11:13, 12:9, 13:4, 14:3, 15:18, 2:2, 3:20, 4:5, 5:2, 7:15, 8:5, 9:2 | 0:-0.009, 1:-0.009, 10:-0.012, 11:-0.006, 12:-0.009, 13:-0.009, 14:-0.008, 15:-0.005, 2:-0.007, 3:-0.006, 4:-0.009, 5:-0.008, 6:-0.007, 7:-0.006, 8:-0.009, 9:-0.012 |
| `eds_quality_diversity_uniform_expand00` | 0:19, 1:12, 10:2, 11:14, 12:9, 13:6, 14:5, 15:18, 2:10, 3:39, 4:12, 5:6, 6:4, 7:17, 8:5, 9:11 | 0:-0.003, 1:-0.003, 10:-0.004, 11:-0.003, 12:-0.005, 13:-0.005, 14:-0.005, 15:-0.004, 2:-0.003, 3:-0.003, 4:-0.003, 5:-0.003, 6:-0.003, 7:-0.003, 8:-0.004, 9:-0.004 |
| `eds_quality_diversity_uniform_expand20` | 0:15, 1:16, 10:3, 11:13, 12:11, 13:3, 14:2, 15:17, 2:17, 3:26, 4:28, 5:34, 6:11, 7:17, 8:23, 9:12 | 0:-0.004, 1:-0.003, 10:-0.004, 11:-0.005, 12:-0.006, 13:-0.004, 14:-0.005, 15:-0.006, 2:-0.004, 3:-0.005, 4:-0.003, 5:-0.002, 6:-0.003, 7:-0.005, 8:-0.003, 9:-0.003 |
| `eds_quality_diversity_uniform_span04` | 0:10, 1:4, 10:5, 11:5, 12:4, 13:4, 14:10, 15:16, 2:6, 3:29, 4:10, 5:6, 6:5, 7:8, 8:8, 9:7 | 0:-0.008, 1:-0.007, 10:-0.008, 11:-0.006, 12:-0.012, 13:-0.012, 14:-0.009, 15:-0.007, 2:-0.005, 3:-0.005, 4:-0.009, 5:-0.009, 6:-0.007, 7:-0.005, 8:-0.011, 9:-0.010 |
| `eds_quality_diversity_uniform_span12` | 0:11, 1:22, 10:9, 11:9, 12:8, 13:5, 14:4, 15:9, 2:21, 3:6, 4:14, 5:9, 6:7, 7:7, 8:6, 9:6 | 0:-0.003, 1:-0.002, 10:-0.003, 11:-0.004, 12:-0.006, 13:-0.005, 14:-0.005, 15:-0.007, 2:-0.002, 3:-0.004, 4:-0.003, 5:-0.003, 6:-0.003, 7:-0.003, 8:-0.003, 9:-0.003 |

## Failure taxonomy

| Job | Categories |
| --- | --- |
| `p2_stage_on_abs_rbf_control` | success: 3, timeout without completion: 7 |
| `eds_quality_diversity_uniform_primary` | timeout without completion: 10 |
| `eds_quality_diversity_sparse_primary` | success: 2, timeout without completion: 8 |
| `eds_quality_diversity_uniform_grid3` | timeout without completion: 10 |
| `eds_quality_diversity_uniform_grid5` | qpos/execution error: 10 |
| `eds_quality_diversity_uniform_q00100` | timeout without completion: 10 |
| `eds_quality_diversity_uniform_q1090` | qpos/execution error: 1, success: 1, timeout without completion: 8 |
| `eds_quality_diversity_uniform_expand00` | success: 1, timeout without completion: 9 |
| `eds_quality_diversity_uniform_expand20` | success: 2, timeout without completion: 8 |
| `eds_quality_diversity_uniform_span04` | timeout without completion: 10 |
| `eds_quality_diversity_uniform_span12` | timeout without completion: 10 |

### Failed / invalid / execution-error evidence

| Job | Valid | Error episodes | Exception types | Validity reason |
| --- | --- | --- | --- | --- |
| `p2_stage_on_abs_rbf_control` | PASS | — | — | — |
| `eds_quality_diversity_uniform_primary` | PASS | — | — | — |
| `eds_quality_diversity_sparse_primary` | PASS | — | — | — |
| `eds_quality_diversity_uniform_grid3` | PASS | — | — | — |
| `eds_quality_diversity_uniform_grid5` | FAIL | [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] | ['IndexError'] | episode 0 video count 0 != 1; episode 1 video count 0 != 1; episode 3 video count 0 != 1; episode 4 video count 0 != 1; episode 6 video count 0 != 1; episode 7 video count 0 != 1; total video count 4 != 10; metrics episode coverage [2, 5, 8, 9] != [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]; episode 0 qualitative evidence missing; episode 0 mechanism evidence missing; episode 1 qualitative evidence missing; episode 1 mechanism evidence missing; episode 3 qualitative evidence missing; episode 3 mechanism evidence missing; episode 4 qualitative evidence missing; episode 4 mechanism evidence missing; episode 6 qualitative evidence missing; episode 6 mechanism evidence missing; episode 7 qualitative evidence missing; episode 7 mechanism evidence missing; successful stage query missing for episodes: 0,1,2,3,4,6,7,8,9; episode 0 video count 0 != 1; episode 1 video count 0 != 1; episode 3 video count 0 != 1; episode 4 video count 0 != 1; episode 6 video count 0 != 1; episode 7 video count 0 != 1; episode  |
| `eds_quality_diversity_uniform_q00100` | PASS | — | — | — |
| `eds_quality_diversity_uniform_q1090` | PASS | [4] | ['ValueError'] | — |
| `eds_quality_diversity_uniform_expand00` | PASS | — | — | — |
| `eds_quality_diversity_uniform_expand20` | PASS | — | — | — |
| `eds_quality_diversity_uniform_span04` | PASS | — | — | — |
| `eds_quality_diversity_uniform_span12` | PASS | — | — | — |

## Latency 与定性证据

| Job | Selection P95 s | QD update P95 s | Parent allocation P95 s | EDS loop P95 s | Stage P95 s |
| --- | ---: | ---: | ---: | ---: | ---: |
| `p2_stage_on_abs_rbf_control` | 2.577 | 0.000 | 0.000 | 2.509 | 12.415 |
| `eds_quality_diversity_uniform_primary` | 2.612 | 0.031 | 0.002 | 2.546 | 10.899 |
| `eds_quality_diversity_sparse_primary` | 5.364 | 0.125 | 0.018 | 5.262 | 11.369 |
| `eds_quality_diversity_uniform_grid3` | 5.476 | 0.146 | 0.022 | 5.364 | 11.117 |
| `eds_quality_diversity_uniform_grid5` | 4.007 | 0.093 | 0.009 | 3.910 | 7.771 |
| `eds_quality_diversity_uniform_q00100` | 2.652 | 0.031 | 0.002 | 2.546 | 7.053 |
| `eds_quality_diversity_uniform_q1090` | 2.726 | 0.031 | 0.002 | 2.563 | 8.358 |
| `eds_quality_diversity_uniform_expand00` | 2.742 | 0.033 | 0.002 | 2.588 | 7.196 |
| `eds_quality_diversity_uniform_expand20` | 2.701 | 0.033 | 0.002 | 2.588 | 21.706 |
| `eds_quality_diversity_uniform_span04` | 2.675 | 0.033 | 0.002 | 2.591 | 79.904 |
| `eds_quality_diversity_uniform_span12` | 2.720 | 0.033 | 0.002 | 2.592 | 19.360 |

### 轨迹几何

| Job | Trajectory length median m | Max-step median m | Chunk-boundary jump P95 |
| --- | ---: | ---: | ---: |
| `p2_stage_on_abs_rbf_control` | 0.093 | 0.015 | 2.983 |
| `eds_quality_diversity_uniform_primary` | 0.131 | 0.022 | 4.157 |
| `eds_quality_diversity_sparse_primary` | 0.121 | 0.020 | 4.902 |
| `eds_quality_diversity_uniform_grid3` | 0.139 | 0.022 | 3.871 |
| `eds_quality_diversity_uniform_grid5` | 0.125 | 0.019 | 2.465 |
| `eds_quality_diversity_uniform_q00100` | 0.139 | 0.022 | 4.166 |
| `eds_quality_diversity_uniform_q1090` | 0.129 | 0.021 | 4.175 |
| `eds_quality_diversity_uniform_expand00` | 0.118 | 0.020 | 3.665 |
| `eds_quality_diversity_uniform_expand20` | 0.113 | 0.019 | 3.999 |
| `eds_quality_diversity_uniform_span04` | 0.122 | 0.021 | 4.093 |
| `eds_quality_diversity_uniform_span12` | 0.103 | 0.018 | 3.350 |

- Raw qualitative heatmaps/trajectories：各 job 的 `eds_eval/qualitative/episode_*/chunk_*/`。
- 同时间坐标 contact sheets：`/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/analysis/qualitative_contact_sheets`；生成 `30` 张，审计 `FAIL`。失败项来自 invalid grid5 缺失/损坏视频，保留红色占位而未伪造画面。
- 自动 failure taxonomy 对无明确 telemetry 的失败保守标为 `timeout without completion`；视觉复核注释单独保留，不把未观察到的因果机制写成事实。

## Ranking 与结论

1. `eds_quality_diversity_sparse_primary` — all gates `False`
2. `eds_quality_diversity_uniform_expand20` — all gates `False`
3. `eds_quality_diversity_uniform_expand00` — all gates `False`
4. `eds_quality_diversity_uniform_q1090` — all gates `False`
5. `eds_quality_diversity_uniform_q00100` — all gates `False`
6. `eds_quality_diversity_uniform_primary` — all gates `False`
7. `eds_quality_diversity_uniform_span12` — all gates `False`
8. `eds_quality_diversity_uniform_span04` — all gates `False`
9. `eds_quality_diversity_uniform_grid3` — all gates `False`

最终 decision：`no_adoption_keep_p2_stage_on_abs_rbf_control`。Gate 失败不构成追加实验或改变冻结参数的授权。
