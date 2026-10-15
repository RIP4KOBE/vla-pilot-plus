# Early executed feedback: read-only four-path comparison

The SHA-verified `early-feedback-readonly-v1.json` (SHA256
`ad673333a0ec3353c202005a4d1c7c3ddbbb9d12fbdb4e6ce3d67a8f49655370`)
extracts the first 40 recorded actions and robot observations for the matched
N11-cohort N7/N11 task3/task6 paths. It reuses only exposed Dev evidence;
there was no new simulator call, Stage request, model call or GPU work.

| Task / policy / whole-episode outcome | First positive gripper-command chunk | EEF distance to *static initial* target keypoint at that chunk | Guided QD–ED chunks before/at first close |
| --- | ---: | ---: | --- |
| task3 / N11 / success | 16 | 0.018 m | 0, 8, 16 |
| task3 / N7 / fail | 24 | 0.030 m | 0, 8, 16; close after guidance |
| task6 / N7 / success | 24 | 0.019 m | 0, 8; close after guidance |
| task6 / N11 / fail | 24 (last two actions; no sustained closure by step 40) | 0.029 m | 0, 8; close after guidance |

The two successful paths happened to begin closing within 2 cm of the first
target keypoint, while both failed paths began around 3 cm. This is a
**posthoc four-trajectory association**, not a validated threshold: the
keypoint is deliberately held at its initial estimate, so it can cease to
track the object after any physical movement. Robot/gripper observations
cannot certify object contact or carry. The late N7 task6 successful close
was outside QD–ED guided chunks, so a final-population-only distance gate
cannot explain or directly control all four outcomes. A rule tuned to the
2–3 cm gap here would also be tuned on these same exposed Dev outcomes.

Together with the approved task3 same-state contrast, this narrows the
unresolved question to whether a deployable, time-aligned object-motion/contact
signal exists across the guidance-to-Stage transition. N10's attempted passive
tracker measurement was invalid because of incomplete Stage turns, so that
signal has not yet been established. The current evidence does not justify
another QD–ED candidate or independent validation dispatch. Decision remains
`TARGET_NOT_MET`; the next contribution must establish an observable
feedback mechanism before freezing a new algorithm.
