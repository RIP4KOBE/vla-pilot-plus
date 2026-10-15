# Partial post-data identity supplement

Three authorized CPU supplements completed; the fourth was not analyzed because its original frozen Stage transport condition was invalid. The CPU watcher exited with code 143 after root requested the stop. This is the end of this analysis subtask, not completion of the ongoing research task.

| Row | Target triples / guided | Eligible | A | B |
| --- | ---: | ---: | ---: | ---: |
| t00-c0 | 29/29 | 29 | 5 | 1 |
| t00-q0 | 52/52 | 52 | 17 | 14 |
| t05-c0 | 12/12 | 12 | 2 | 0 |
| t05-q0 | Unknown (transport invalid) | Unknown | Unknown | Unknown |

| Row | Median actual / predicted progress (m) | Median optimism (m) | Median EEF RMSE (m) | Median endpoint error (m) | Median response gain |
| --- | ---: | ---: | ---: | ---: | ---: |
| t00-c0 | 0.031869 / 0.067035 | 0.015803 | 0.036483 | 0.063409 | 0.482507 |
| t00-q0 | 0.011215 / 0.031693 | 0.019880 | 0.045290 | 0.063157 | 0.280658 |
| t05-c0 | 0.056977 / 0.055680 | 0.008572 | 0.049744 | 0.069997 | 0.560048 |

A appears in both observed tasks; B appears in task 0 only among the three admitted episodes. These are distinct execution records, not a generalization or improvement estimate. No promotion is recommended: an actionable causal predecision rule and a selection change among recorded candidates remain unverified, and task 5 lacks a valid matched Q0 result.

The task0-Q0 actual-progress reversal IDs are s224/s560/s576; only s224/s560 also meet A. The original per-row summary alias `A_progress_reversal_ids` means all actual reversals, so the JSON aggregate separates actual reversals and their A intersection. This is a display clarification, with no formula/threshold change.

All continuous ranges, witness IDs, source hashes and per-row artifact paths are in [partial-supplement-summary.json](partial-supplement-summary.json). [watcher-stop.json](watcher-stop.json) records the stop and fourth-row exclusion. Original frozen-map analyses remain unchanged.

- Original frozen map-v2 results remain separate and unchanged; these are post-data serialization-identity correction results.
- Witness counts are descriptive per episode; correlated chunks are not independent samples. Same-task C0/Q0 share task/seed and their guided/state/Stage paths differ.
- A has observed witnesses in three separate executions across two tasks. B has witnesses in the two task0 executions, and no witness among the 12 eligible task5-C0 prefixes; task5-Q0 is Unknown.
- No candidate quality-rank error, successful alternative action, or policy improvement is established.
- Target is the recorded decision-time keypoint, not contemporaneous object pose. EEF approach is not grasp/task success.
- The stored projection remains BF16-origin despite float64 arithmetic; numerical floors screen storage resolution, not physical noise.
- Fourth row remains frozen invalid and unpaired; complete physical steps do not override failed transport condition. No audit bypass, retry or relabel occurred.
- GPU cost/accounting remains root-owned; this report does not recompute or replace it.
