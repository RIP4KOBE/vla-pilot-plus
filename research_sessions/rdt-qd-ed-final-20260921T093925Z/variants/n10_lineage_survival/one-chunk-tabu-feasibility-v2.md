# One-chunk QD parent tabu: read-only feasibility screen

This screen reuses only the four exposed N7 development episodes and the seven guided chunks whose already policy-visible target keypoint shifted at least 1 cm by the next chunk. `audit_tabu_feasibility.py` SHA-checks the prior and immediate next decision bundles and writes the decision-level record to `one-chunk-tabu-feasibility-v2.json`. It executes no alternative action or parent allocation.

| Task, perturbing step → immediate next step | Next chunk guided, same stage/target | Prior selected numeric QD cell | Its slots in next iteration-0 parent allocation | Same-cell height-bin interval overlap |
| --- | --- | ---: | ---: | ---: |
| 0, 24 → 32 | No | 11 | — | — |
| 0, 296 → 304 | Yes | 3 | 0 | 0 cm |
| 0, 304 → 312 | Yes | 5 | 2 | 3.88 cm |
| 0, 344 → 352 | Yes | 0 | 1 | 2.35 cm |
| 0, 512 → 520 | No; stage also changed | 7 | — | — |
| 3, 8 → 16 | Yes | 0 | 1 | 0 cm |
| 3, 16 → 24 | No | 7 | — | — |

Four of seven shifts are followed immediately by a guided decision with the same stage, target index 0, keypoint count, target-observation source, episode/reset sequence and `previous_decision_id` chain. Three of those four have at least one matching numeric parent cell; suppressing that cell would nominally reallocate **four of 64** next-iteration parent slots (2 + 1 + 1). Each next allocation has at least seven other occupied cells, so an alternate parent cell is present. None of the six guided chunks from successful tasks 6 and 9 crosses the 1 cm trigger; this is only a four-episode observation, not a specificity estimate.

Two identity qualifications matter. The bundles do not record the keypoint tracker's instance/generation or per-keypoint validity, although `main.py` registers the tracker once per episode and the native decision/reset chain is continuous. Thus **four are conditionally eligible by recorded context and code path, zero are natively attested for tracker identity**. A real policy should use the existing passive `execution_feedback_tracking_snapshot()` to verify generation and target validity, then fail closed. Also, N7's signed-height QD bounds are recomputed from each decision's initial candidates. They changed in all four eligible transitions. For task 3 step 8, the same numeric cell's old and new height intervals are disjoint, so that nominal slot does not reliably represent the perturbing behavior. Only **three of four** nominally reallocated slots lie in transitions with overlapping height-bin intervals; interval overlap still does not establish equivalent trajectories. A robust mechanism would need a stable physical descriptor or a reprojected prior behavior, not blindly tabuing a numeric cell ID.

The screen establishes only that a feedback-conditioned parent-allocation intervention has a small, auditable opportunity in this exposed Dev cohort. It does not establish that the target shift was harmful, that parent reallocation prevents it, or that it improves task success. The previous N9 lateral-sweep penalty failed its matched Dev gate, so this proposed parent-allocation intervention must be evaluated as a distinct hypothesis, with a task-success gate and unchanged candidate/score-call budget.
