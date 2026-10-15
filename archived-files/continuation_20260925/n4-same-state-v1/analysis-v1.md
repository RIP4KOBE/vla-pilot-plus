# N4 task-9 same-state diagnostic — completed

This is a **diagnostic-only** result from one exposed Dev scene, not an
official task-success observation. The user approved the single bounded
branch comparison on September 25. The frozen plan, child, supervisor,
protocol and exact outputs are in this directory. The machine-readable
recalculation is `analysis-v1.json` (SHA256
`b27327e495663008e620ecf8a96f1df3da735267a9163344acdb82d37768398f`).

The first N4 terminal-population selection and its simultaneous archive
reference produced different commands at all eight positions. Four resets
including the ordinary initial reset produced 20 settling steps; exactly
32 additional diagnostic transitions were executed. Two selected-prefix dry
runs and the selected contrast branch agreed **exactly at every state** on
MuJoCo state, raw observations, exposed controller state, time/step counters,
object/EEF poses, contacts and success predicate. The archive branch started
from the same complete initial signature.

| First eight commands | Final EEF-to-source distance | Source displacement | Source contact |
| --- | ---: | ---: | --- |
| N4 terminal selection | 0.257425 m | 0.002501 m | floor only |
| Archive reference | 0.260613 m | 0.002501 m | floor only |

The source ended at the exact same pose under both branches. Neither branch
had a gripper/source contact or task success in these eight steps. The N4
prefix ended 0.003188 m closer to the source. Its cost was 0.04931640625
versus the archive reference's 0.045166015625. This small distance contrast
does not show which branch would be better over a full 720-step episode, and
the passive 0.002501 m source displacement is not evidence of manipulation.

The owned GPU3 process took 84.480770 seconds. The attempt ledger charged one
development slot and 0.02346688 GPU hours; total N4 private use is now
93/240 attempts, 67/100 development slots and 12.885274797/48 GPU hours.
The child wrote one diagnostic compute record with 21 model forwards,
336 model batch rows, 256 reward calls, and zero Codex Stage calls. Validation
and formal remained closed. The N4-E1 official Dev result remains **1/4**,
below its frozen 2/4 gate.

The already recorded full N4 task-9 rollout has a separate, weaker candidate
selection witness: its terminal final pools at steps 16 and 24 contain 6/16
and 8/16 actions with at least one closed-gripper command, respectively;
the selected action has none at either step. At step 24, the selected
candidate's projected minimum EEF-to-keypoint distance is 0.0311 m; the
closest closed-gripper candidate has a projected minimum of 0.0486 m.
Those are current-observation kinematic projections, not measured contact
outcomes. The original selected rollout reaches approximately 0.0271 m from
tracked keypoint 0 by step 30 while its gripper command stays open, and the
external Stage log turns guidance off at step 32. The Stage text is a model
description and is not ground-truth object-contact evidence. This is a
falsifiable motivation to examine grasp-command timing inside QD selection,
not a claim that a rejected candidate would have succeeded.

No N4 promotion, protected evaluation release or new algorithm has been
authorized by this diagnostic itself. A new candidate requires its own frozen
hypothesis, implementation, tests and matched Dev comparison under the
remaining private budget.
