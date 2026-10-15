# N11 four-arm matched Dev result

All 16 original exposed Dev identities were run once on GPU3 and audited. The first four use frozen plan v1; the other twelve use audit-correction continuation plan v2. The policy algorithm and Stage condition are unchanged between the plans. The original failed task0 N11 audit remains preserved; an independent corrected audit accepts the same SHA-verified native evidence.

| Task | C0 | Q0 | N7 | N11 |
| --- | ---: | ---: | ---: | ---: |
| 0 | 0 | 0 | 0 | 0 |
| 3 | 0 | 0 | 0 | 1 |
| 6 | 0 | 0 | 1 | 0 |
| 9 | 1 | 0 | 0 | 0 |
| **Total** | **1/4** | **0/4** | **1/4** | **1/4** |

N11 gained task3 versus N7 but lost task6; both failed task0 and task9. Exact survivor selection changed actions, but the outcome gain did not generalize. N11 fails its preregistered >=3/4 gate and is not promoted to validation or formal acceptance.

GPU3 process wall time charged to this cohort: 9029.454 s (2.508182 GPU h), within the 6 h local cap. Cumulative budget: 201/393 attempts, 26.849243/100 GPU h. Protected validation and formal reserves remain closed.

The task3 success is a useful mechanism signal, not an accepted candidate: its three guided decisions contain 30 audited survivor rounds and 120 exact survivor slots, and all three selected actions differ from N7 at the same decision steps. Task6 shows the opposing failure case. Detailed per-attempt costs, selected-action differences, audit hashes and provenance are in `dev-comparison-v1.json`.
