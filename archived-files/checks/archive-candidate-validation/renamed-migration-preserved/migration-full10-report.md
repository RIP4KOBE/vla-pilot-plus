# EDS migration acceptance report

The frozen EDS migration cohort completed all 10 tasks: **3 successes out of 10**, with task IDs 3, 8, 9 successful and zero infrastructure-error episodes. The run finished normally with source unchanged. All ten task contracts are complete and valid; the frozen cohort gate passed.

The tested commit is `cfecb12db736f1a3408d9528d9336aadcb7e41b5`. The run used `codex_cli` / `gpt-6-astra` / `low`, physical GPU 2 (`GPU-a5d6a5f8-b6df-7f3a-c3dc-19734c41ec0e`) and EGL 1. It ran from 2026-10-13T09:04:05.392537+00:00 to 2026-10-13T12:23:58.287339+00:00 (11992.9 s including startup).

Saved evidence covers 5585 executed actions and adapter exits, 317 Stage captures (307 observations + 10 identity requests), and 10 fresh reward captures. The per-task audits report 14081 passing checks.

| Task | Seed | Outcome | Actions | Contract checks | Reference actions |
|---|---:|---|---:|---:|---|
| 0 | 44 | failure | 720 | 1722 PASS | all equal |
| 1 | 235 | failure | 720 | 1765 PASS | all equal |
| 2 | 43 | failure | 720 | 1808 PASS | 24 differ; first step 696 |
| 3 | 546 | success | 120 | 389 PASS | all equal |
| 4 | 6 | failure | 720 | 1550 PASS | 248 differ; first step 472 |
| 5 | 621 | failure | 720 | 1980 PASS | all equal |
| 6 | 197 | failure | 720 | 1679 PASS | all equal |
| 7 | 87 | failure | 720 | 1937 PASS | all equal |
| 8 | 151 | success | 211 | 604 PASS | all equal |
| 9 | 548 | success | 214 | 647 PASS | all equal |

The complete action sequences match the reference for eight tasks. Task 2 diverges at step 696 and task 4 at step 472; both remain failed but valid scientific observations. These differences are retained. A matching overall 3/10 result does not establish identical online requests or exact online execution for every task.

[Machine-readable acceptance and evidence hashes](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/runs/eds-migration-20261013/migration-full10-acceptance.json) contains all ten contract/action report hashes and anchors the frozen manifest, configuration, cohort gate, final status, progress, console outcome lines and initial-equivalence reports. Its SHA256 is `c3251c1546b75d85352c77bdda0ea49afed00ca4d74402f099b9794bd73c7178`.

This report accepts the EDS migration cohort. Three-mode integration, future VLS/EDS-QD online cohorts, and the current-GPU QD numerical check are subsequent work. No historical score is used as a substitute for this newly completed result.
