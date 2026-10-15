# N3 complete-cohort descriptive diagnostic — final summary v3

Completed all30 accepted cells with exit0 in 270.953s CPU wall time. No CUDA initialization, fresh audit or new quality computation. All final cell JSON hashes match the complete index. V1 failure is preserved.

N3 feedback was operationally active, and the final selection evidence is stronger than scalar-change counts: 160 active decisions, 120 selected-relative final ordering witnesses and 120 strict negative selected raw gaps. There were 64 recognized inactive guided decisions. This rules out a blanket explanation that feedback never reached selection; it does not establish task benefit or a counterfactual better action.

The fixed retrospective previous-residual transport has a lower per-episode mean prediction MSE than zero in all10 N3 episodes, but this is a descriptive property of the realized N3 trajectories. C0 has 2 negative and 8 positive episode differences; Q0 has 8 negative and 2 positive. Native T7 scoring and this FP64 diagnostic are different computations; neither prediction association nor activity overrides the original failed Dev gate.

| Arm | Actual actions | Guided actions | Active feedback actions | Eligible structural pairs | Episode-mean transport − zero MSE | Reactivations | Stage OK |
|---|---:|---:|---:|---:|---:|---:|---:|
| C0 | 5920 | 1296 | N/A | 111 | +0.000825757785 | 41 | 173 |
| Q0 | 6594 | 1240 | N/A | 111 | -0.00139448605 | 34 | 187 |
| N3 | 7200 | 1792 | 1280 | 160 | -0.00929824779 | 54 | 253 |

All30 start ON and have an observed first OFF. Early endings remain 321/204/355 actions for C0 tasks5/8/9 and114 actions for Q0 task8; all other cells have720. Each action count uses the actual acknowledged prefix, including the four final partial chunks. No absent chronology is imputed.

Per-task table below uses existing fields only. Pairs are retrospective structural pairs, not a redefinition of runtime eligibility. N3 witness is the strict final raw-gap witness count; controls are not applicable. Δ is each episode’s existing mean transported-minus-zero prediction MSE.

| Task/arm | Actions | Guided | Active / inactive | First OFF | Reactivation steps | Pairs | N3 strict witness | Δ MSE |
|---|---:|---:|---:|---:|---|---:|---:|---:|
| t00-c0 | 720 | 232 | N/A | 24 | 72,136,200,304,400,472,544 | 21 | N/A | -0.001852912 |
| t00-q0 | 720 | 416 | N/A | 16 | 112,496,536,616,680 | 46 | N/A | -0.001388072 |
| t00-n3 | 720 | 264 | 28 / 5 | 40 | 104,312,400,608 | 28 | 19 | -0.008647919 |
| t01-c0 | 720 | 24 | N/A | 24 | none observed | 2 | N/A | +0.001726673 |
| t01-q0 | 720 | 24 | N/A | 24 | none observed | 2 | N/A | +0.0004438598 |
| t01-n3 | 720 | 32 | 3 / 1 | 32 | none observed | 3 | 3 | -0.008939726 |
| t02-c0 | 720 | 152 | N/A | 32 | 152,488,576 | 15 | N/A | +0.001482173 |
| t02-q0 | 720 | 296 | N/A | 24 | 56,200,344,440,464,480,496,512,528,544 | 26 | N/A | -0.003951838 |
| t02-n3 | 720 | 368 | 37 / 9 | 24 | 56,104,152,192,272,448,680,712 | 37 | 33 | -0.01857985 |
| t03-c0 | 720 | 24 | N/A | 24 | none observed | 2 | N/A | +0.005538957 |
| t03-q0 | 720 | 24 | N/A | 24 | none observed | 2 | N/A | +0.00708481 |
| t03-n3 | 720 | 88 | 6 / 5 | 32 | 256,528,616,680 | 6 | 4 | -0.006302476 |
| t04-c0 | 720 | 216 | N/A | 72 | 224,280,368,472,520,552,584,640 | 18 | N/A | +0.001187777 |
| t04-q0 | 720 | 160 | N/A | 24 | 176,264,384,432,512,640 | 13 | N/A | -0.0001403127 |
| t04-n3 | 720 | 184 | 13 / 10 | 56 | 88,168,224,280,368,408,472,608,712 | 13 | 10 | -0.01266263 |
| t05-c0 | 321 | 40 | N/A | 24 | 40,136 | 2 | N/A | +0.001145877 |
| t05-q0 | 720 | 48 | N/A | 16 | 352,368,448 | 2 | N/A | -0.0005173397 |
| t05-n3 | 720 | 24 | 1 / 2 | 16 | 464 | 1 | 0 | -0.002753046 |
| t06-c0 | 720 | 184 | N/A | 40 | 48,88,136,184,280,296 | 16 | N/A | +0.0003626973 |
| t06-q0 | 720 | 40 | N/A | 24 | 64 | 3 | N/A | -0.0005742077 |
| t06-n3 | 720 | 320 | 34 / 6 | 24 | 352,552,584,616,632 | 34 | 31 | -0.01326554 |
| t07-c0 | 720 | 280 | N/A | 24 | 64,128,184,248,280,360,440,592,608,656,712 | 23 | N/A | -0.00235094 |
| t07-q0 | 720 | 160 | N/A | 24 | 104,208,360,456,600,704 | 13 | N/A | -0.006483131 |
| t07-n3 | 720 | 200 | 16 / 9 | 32 | 72,144,184,384,472,568,608,640 | 16 | 8 | -0.001562435 |
| t08-c0 | 204 | 72 | N/A | 24 | 64 | 7 | N/A | +0.001008316 |
| t08-q0 | 114 | 16 | N/A | 16 | none observed | 1 | N/A | -0.001487392 |
| t08-n3 | 720 | 144 | 11 / 7 | 24 | 160,192,328,376,424,656 | 11 | 7 | -0.001553786 |
| t09-c0 | 355 | 72 | N/A | 32 | 88,152,216 | 5 | N/A | +8.960058e-06 |
| t09-q0 | 720 | 56 | N/A | 24 | 288,376,584 | 3 | N/A | -0.006931238 |
| t09-n3 | 720 | 168 | 11 / 10 | 32 | 144,224,296,360,424,504,600,664,704 | 11 | 5 | -0.01871507 |

N3 inactive reasons are retained exactly: {"eligible_immediate_full_prefix": 160, "guidance_off_or_mode_changed": 12, "no_complete_history": 10, "stage_change": 42}. There is no unsupported-provider disposition in these ten accepted N3 episodes; this observation is not a new all-task applicability gate.

Stage after-state and sent-gripper associations (known match/mismatch/Unknown are kept distinct):

- C0: after-state {'known_match': 173}; first sent {'True': 173}; last sent {'True': 140, 'False': 33}; Stage source {'recorded': 10}; skipped/limit records 0.
- Q0: after-state {'known_match': 187}; first sent {'True': 187}; last sent {'True': 153, 'False': 34}; Stage source {'recorded': 10}; skipped/limit records 0.
- N3: after-state {'known_match': 253}; first sent {'True': 253}; last sent {'True': 213, 'False': 40}; Stage source {'recorded': 10}; skipped/limit records 0.

All Stage query records here are successful, but response correctness and actual normalized Stage input values remain Unknown. Physical grasp/contact/release, target progress, resolved controller clipping and counterfactual task outcomes are not measured. Differences in ON/OFF chronology show differing exposure to guidance; they do not identify its cause or justify adjusting a Stage threshold. The task-level outcome and cost remain exclusively in the unchanged original matrix report.

Provenance:

- index: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/n3-post-dev-analysis/read-v2/index.json`; SHA256 `2df36b7b0de39655dcfe7fa566f24271b3e4e8a5b104685886ca2b69cd26885b`.
- provenance: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/n3-post-dev-analysis/read-v2/provenance.json`; SHA256 `5581ed63d89c8de170c1750ba18fe1d131dd83eacc384305ab6eb90de684658c`.
- status: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/n3-post-dev-analysis/read-v2/status.json`; SHA256 `eb496308e45a84c093fd2685c194f4974e312464e49d26978b80b31cd47678e0`.
- process_start: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/n3-post-dev-analysis/launch-v2/process-start.json`; SHA256 `2c8a70576ade0a1ac96dd2a18ed69dbe790d9fb3e9b18c8b4e4f4f27523445a7`.
- process_result: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/n3-post-dev-analysis/launch-v2/process-result.json`; SHA256 `4ac207cf4e80348cfa453ad0f4baaf5272ac4b51145f8c8b2ea3ef2834c1f661`.

Derived machine-readable summary: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/n3-post-dev-analysis/summary-v3/summary.json`; SHA256 `0958cd7dada1ba72b0bad087054041d38f6836d7acb2d80740626fd7c039f74f`.

This report supersedes summary-v2 only for its erroneous extra finite-action display. Original matrix/audit remains finite-action authority; this final report does not recompute that property. The actual reader, final index, cell summaries and scientific definitions are unchanged. Observed-action denominators remain the existing collector counts.
