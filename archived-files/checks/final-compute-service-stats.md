# Final compute and service statistics

Original online commit `33954ead452927fc3168efb610487a688f89169e`; source is the sealed [three-mode final aggregate](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/checks/three-mode-final.json). All three cohorts passed their full evidence audits; the EDS integration threshold was met.

| Method | Score | Worker elapsed | Guided / unguided chunks | Stage queries / errors | Model forwards | Model batch rows |
|---|---:|---|---:|---:|---:|---:|
| EDS | 3/10 | 03:17:55 | 205 / 494 | 309 / 0 | 6,775 | 71,350 |
| VLS | 1/10 | 03:41:01 | 368 / 459 | 369 / 0 | 4,135 | 39,095 |
| EDS+QD | 1/10 | 04:01:43 | 284 / 554 | 380 / 0 | 8,734 | 98,194 |

The cohorts ran concurrently; earliest worker start to latest finish was 04:01:50. Worker elapsed includes model/provider waiting, simulation, rendering and process overhead. These are wall-clock times, not active GPU hours.

| Method | Provider completed turns / failed calls | Sum of provider call latency | Input tokens (cached subset) | Output tokens | Reasoning output breakdown |
|---|---:|---|---:|---:|---:|
| EDS | 329 / 0 | 02:57:04 | 3,183,949 (1,975,424) | 37,225 | 13,572 |
| VLS | 389 / 0 | 03:27:43 | 3,761,626 (2,345,856) | 47,366 | 19,839 |
| EDS+QD | 400 / 0 | 03:35:21 | 3,869,031 (2,421,888) | 46,953 | 18,465 |

Provider totals include10 initial identity calls and10 fresh reward-generation calls per cohort in addition to the Stage boundary queries. Cached tokens are a subset of input; reasoning tokens are a reported breakdown, not an additional term to sum into output. No monetary service cost is inferred.

EDS and EDS+QD use the same per-guided-chunk search budget:11 score calls and176 candidate evaluations. Their guided model work is21 forwards at B16 (336 batch rows); VLS uses5 forwards at B20 (100 batch rows). All modes use5 forwards at B1 for unguided chunks. Actual cohort totals differ with outcomes and Stage decisions, so this is not a matched total-compute comparison.

| Method | Search score calls | Search candidate evaluations | Total recorded reward evaluations | RBF gradient calls | Guided select_action mean |
|---|---:|---:|---:|---:|---:|
| EDS | 2255 | 36080 | 52,480 | 3,895 | 2.552 s |
| VLS | n/a | n/a | 51,520 | 368 | 0.675 s |
| EDS+QD | 3124 | 49984 | 72,704 | 5,396 | 2.619 s |

The full reward counters include work beyond the EDS search-scoring budget. select_action latency is a wall-clock region, not GPU kernel time. Full counters and exact timestamps are preserved in the adjacent JSON. A single ten-task cohort per mode does not establish statistical superiority.
