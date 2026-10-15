# Completed VLS read-only task review

Frozen online runtime: `33954ead452927fc3168efb610487a688f89169e`. Worker finished with exit code 0 and `source_unchanged=true`. The independent watcher stopped normally after task 9. All 10 task contracts, every guided VLS chunk, task identity/video bindings, Stage outer-reference continuity, and the final 113-file source guard passed. This report complements the frozen full-cohort wrapper; it does not replace the final cohort or three-mode integration acceptance.

Observed task success: **1/10**, task 3. The remaining nine episodes are valid scientific failures, not infrastructure failures.

| Task | Seed | Outcome | Guided chunks | Contract PASS |
| --- | --- | --- | ---: | ---: |
| 0 | 44 | failure | 27 | 1765 |
| 1 | 235 | failure | 35 | 1765 |
| 2 | 43 | failure | 38 | 1894 |
| 3 | 546 | success | 5 | 432 |
| 4 | 6 | failure | 23 | 1765 |
| 5 | 621 | failure | 36 | 1851 |
| 6 | 197 | failure | 28 | 1937 |
| 7 | 87 | failure | 46 | 1765 |
| 8 | 151 | failure | 64 | 1808 |
| 9 | 548 | failure | 66 | 1765 |

Across 368 guided chunks, gradient guidance was attempted/applied **1472/1472** times and RBF was attempted/applied **368/368** times. Zero, nonfinite, exception, and unavailable counters were all zero. FKD had **1104 calls**, **368 scoring opportunities**, **368 ESS skips**, and **0 actual resamples**. Observed ESS ranged from 14.233225822 to 19.999992371; every score opportunity met the configured adaptive ESS skip condition. These records demonstrate enabled and evaluated FKD, not an executed resampling event.

Stage continuity was checked over 827 recorded chunk boundaries. 373 boundaries consumed a fresh outer progress diagnostic (this includes initial zero values); 28 reference resets were recorded. The 373 reward-handoff records count boundaries where reward participated in the contact decision, not newly entered contact-grace windows. Outer selected progress ranged from 0.0 to 0.9832367549668874. For a concrete observed handoff, task 0 / step 24 consumed progress 0.9784564393939394 with target distance 0.03391569775772874 m, entered contact grace until step 88, and changed guidance from true to false.

All reports and evidence hashes are in this folder; raw cohort outputs were not modified. No GPU or provider request was made by this watcher. Per-task audit files are immutable completed-task snapshots. `summary.json` SHA-256: `dbda7d3cac0bb0ebe8ab4dbedbd6f2afdedc92612591be0fba0de520122826c8`. Source-manifest SHA-256: `cec2f59b8dc9ec67e8c8613a87bf762180807097a5a4142469277a94283ec35c`.
