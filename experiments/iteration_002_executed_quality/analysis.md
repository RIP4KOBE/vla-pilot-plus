# N2 Dev decision: REJECT; study continues

Recorded 2026-09-23 after all 30 matched Dev cells completed on physical GPU3. This closes N2's performance evaluation, not the user-authorized research task. No validation or formal candidate is released and the target remains unmet.

| Task | C0 | Q0 | N2 |
|---|---|---|---|
| 0 | failure | failure | failure |
| 1 | failure | failure | failure |
| 2 | failure | failure | failure |
| 3 | failure | failure | failure |
| 4 | failure | failure | failure |
| 5 | success | failure | failure |
| 6 | failure | failure | failure |
| 7 | failure | failure | failure |
| 8 | success | success | success |
| 9 | failure | failure | failure |
| Total | 2/10 | 1/10 | 1/10 |

N2 gains no successful task against either matched control, loses task5 against C0, and ties Q0. It fails the preregistered threshold of at least 5/10 and no fewer successes than either control. These are observed small-sample comparisons, not a claim of statistical equivalence or proof that every QD/ED mechanism is ineffective.

All 30 selected representatives have accepted, complete decision-evidence audits. There were 31 dispatches: the original task0 Q0 transport-invalid attempt remains invalid, contributes cost, and is excluded from scientific trajectory analysis. Its prospectively permitted identical-identity recovery supplies the one valid Q0 representative. Valid task failures were not retried. Source remained `525506ca3198f54d86dadf84bbb76eb64926d87a`, with fixed seeds, runtime, transport and action contracts throughout.

| Arm | GPU process seconds, all attempts | Valid guided chunks | Valid model forwards | Valid provider logical calls |
|---|---:|---:|---:|---:|
| C0 | 6067.048104607 | 200 | 7135 | 201 |
| Q0 | 6292.725439663 | 185 | 7085 | 193 |
| N2 | 4568.884975124 | 131 | 6221 | 149 |

The cohort total is 16928.658519394 seconds, including 570.876267048 seconds for the invalid original Q0 attempt. It is not the entire study's charge. Complete guided chunks retain 176 canonical evaluations and 11 score batches. Full-episode computation differs because execution lengths and guidance trajectories differ; N2's lower total is not evidence of a more efficient successful algorithm. Internal HTTP requests/retries remain unobserved through the Codex CLI.

N2's recognized Q8 objective was applicable on all 131 guided chunks and changed 22655 recorded candidate scalar values. The first-three checkpoint established actual quality-dependent search/selection activity, native raw-quality association, finite actions and unchanged canonical computation. Changed scalar counts alone do not establish changed actions or task benefit. The original raw channel remained the Stage input source; the exact normalized Stage argument was not recorded.

The separately frozen CPU chronology completed all 30 representatives and 30 fresh audits without CUDA initialization or outcome changes. Guided actions were C0 1600/6285, Q0 1480/6594 and N2 1048/6594; OFF-to-ON reactivations were 48, 34 and 24. Successful task8 Q0/N2 runs each used only 16 guided actions out of 114. Thus a long OFF interval alone does not identify a failure cause or justify forcing guidance on. All 543 recorded Stage queries succeeded and their after-states agreed with the same-step decision context; this establishes recorded consistency, not semantic correctness.

The outer loop selects bounded additional evidence collection: compare existing selected projections with their actual executed EEF responses, then examine a fixed past-residual prediction on eligible consecutive guided chunks. This diagnostic is separately specified before reading its numerical results. It does not modify Stage, the external provider/projector, the controller, the checkpoint, or the task. Grasp/contact, target progress, unexecuted candidate outcomes and causal failure explanations remain unknown. A subsequent algorithm needs evidence and a new prospective protocol; N2 is not retuned or promoted by changing its gate.

Evidence under the study artifact root `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/`:

- `continuation_20260923/n2-matrix-report/report-full-dev-v1.json`, SHA `d376f98a0d0d23d7b73b0a20ab768594c63ed6a6abce9473e0e67d2247bc88ab`.
- `continuation_20260923/n2-matrix-report/root-candidate-decision-v1.json`, SHA `140d1429c3cc76854c3e230cfed5bc3b43be9f9fdebc550c20fda87968aa41f2`.
- `continuation_20260923/full-dev-closed-loop-analysis/read-v1/index.json`, SHA `a0d26a8b61761a95c48d1c93dc80b8c5cc0c5f3779aa2bac7facb78f0583a7c0`.
- `continuation_20260923/full-dev-closed-loop-analysis/read-v1/inputs-and-audit.json`, SHA `ccfc8cd622ab2c9c659a6ae89dc618c853a77dc4f80af3e590ba44589d74a3ce`.

At this closure, journal-derived accounting was 11.72537440950208/48 GPU-hours and 79/240 dispatched attempts, with no running attempt. Validation/formal retain 24 GPU-hours and 100 attempts, leaving 12.27462559049792 hours and 61 unreserved attempts. Admission must recompute these values before any new dispatch. All future online work remains on GPU3 only.
