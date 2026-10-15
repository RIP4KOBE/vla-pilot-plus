# N2 fixed final-pool check v1

Both authorized CPU runs exited 0. All 81 eligible decisions and 1,282 final slots were analyzed. The strict recorded-choice activity gate is met: C0 has 1/29 and Q0 4/52 tie-robust changed choices. No scientific promotion or physical benefit is established.

| Recorded episode | Eligible / final slots | Tie-robust changed | Deterministic changed | Mixed tie retaining selected | Maximum slots / multi-slot decisions | CPU wall s |
|---|---:|---:|---:|---:|---:|---:|
| t00-c0 | 29 / 464 | 1 | 1 | 0 | 29 / 0 | 28.912770 |
| t00-q0 | 52 / 818 | 4 | 5 | 1 | 53 / 1 | 51.969054 |

Every exact maximum is retained in the JSON. The Q0 mixed tie at step184 retains the actual selected fingerprint and is excluded from the activity count. A strata changed counts are C0 1/5 and Q0 3/17; non-A counts are C0 0/24 and Q0 1/35. These are descriptive strata, not independent samples.

The five tie-robust changes each have a unique maximum. Their original-quality losses and descriptive distances to the original frozen context target are:

| Episode / step | Original quality delta | Actual t7 → t8 (m) | Q8 maximum t7 → t8 (m) |
|---|---:|---:|---:|
| t00-c0 / 320 | -0.0015869140625 | 0.128331216 → 0.140348150 | 0.092421239 → 0.090826714 |
| t00-q0 / 192 | -3.81469726562e-05 | 0.014303095 → 0.019614199 | 0.009455948 → 0.010025147 |
| t00-q0 / 224 | -2.28881835938e-05 | 0.037744346 → 0.045931172 | 0.035776043 → 0.039698208 |
| t00-q0 / 344 | -0.000255584716797 | 0.023739726 → 0.030023152 | 0.015612580 → 0.011301299 |
| t00-q0 / 568 | -1.90734863281e-06 | 0.028759943 → 0.034356343 | 0.029770225 → 0.031869435 |

All five changes lose original provider quality. All five have smaller projected t8 distances to the original frozen target; t7 is larger for Q0 step568. These coordinates are model projections, not observed outcomes of executing the alternative. The report also preserves distances to the native scored target, which differs from the original target after dtype storage. Q8 always uses native scored keypoints and BF16 storage.

Both the formula and tie rule are unchanged. CPU numerical agreement does not prove GPU bitwise equality; fixed-pool choices do not simulate N2 search or establish contact/grasp/success. Identity-v3 remains post-data; previous map-v2 results and the invalid fourth observation are untouched.

Evidence:
- `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/n2-fixed-candidate-quality/t00-c0-v1/n2-fixed-pool.json` SHA `bd0e1526d34bb0c4cc9826527eff64131fb561aae8f5e7538cc04f566fd3a6f1`; command/stdout/stderr/exit/runtime in `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/n2-fixed-candidate-quality/t00-c0-execution-v1.json`.
- `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/n2-fixed-candidate-quality/t00-q0-v1/n2-fixed-pool.json` SHA `195a77627fca592afd748602f864099d107ac91471c740c3a1a160071a8fe769`; command/stdout/stderr/exit/runtime in `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/n2-fixed-candidate-quality/t00-q0-execution-v1.json`.
- Complete derived summary: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/n2-fixed-candidate-quality/summary-v1.json` SHA `51e04f816e9cadfe0e8c4812b8bddb931a882abff8e0be4fde2e173aa71d9fa9`.
