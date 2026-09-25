# N7 C1 independent validation: numeric rejection

The frozen two-block, ten-task C1 cohort completed all 60 original C0/Q0/N7 cells on physical GPU3. Native per-cell audits accepted every original identity. One earlier C0 Stage stream transport failure remains an invalid charged attempt; its sole typed identical-science recovery is charged to recovery. The full cohort therefore has 61 terminal attempts, 60 accepted cells, and 28,603.353270446067 GPU-process seconds including the invalid attempt.

| Arm | Block 1 | Block 2 | Total |
| --- | ---: | ---: | ---: |
| C0/P2 | 0/10 | 0/10 | 0/20 |
| Q0 | 1/10 | 2/10 | 3/20 |
| N7 | 1/10 | 2/10 | 3/20 |

N7 misses the prospectively frozen promotion gate of at least 10/20, despite tying Q0 and exceeding C0. Its formal release is closed. The 3/20 result is seed robustness evidence on the same init rows, not new-layout generalization. Its pre-validation 2/4 Dev result was overoptimistic for this cohort; this does not establish that the descriptor alone caused failure or that all QD/ED mechanisms are ineffective.

The complete machine report is `artifacts/continuation_20260925/n7-validation-c1-recovery-v1/full-validation-report-v1.json`, SHA-256 `999752f85dbf27534ae35939f38b3237ac21165f0df5808e13946ce1079b1bae`. The original C1 plan SHA-256 is `f2f0242d11711163603e62fc66ad63967bbfeda1884bb948356f805c7b130f9c`; the continuation plan SHA-256 is `9fd4ace8f49b3e676d3a00b4aa8b2ca03fc3d2a26bfaffeff0c28cc6ba85f77b`. No C1 task/seed result is used to choose a successor's task-specific algorithm setting. Any new candidate needs a fresh prospectively frozen validation cohort and a separate budget decision before that validation can be dispatched.
