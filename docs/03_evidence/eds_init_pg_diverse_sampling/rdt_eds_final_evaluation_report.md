# RDT+EDS Final Evaluation Report

Timestamp: `2026-07-14T13:20:34+00:00`

## Scope

- Policy: `rdt` only.
- Base suite: `libero_object` only.
- OOD suites: LIBERO-PRO perturbations of `libero_object` only.
- Alternative guidance and policy comparisons are excluded.

## Per-Level Reports

- `docs/03_evidence/eds_init_pg_diverse_sampling/level_0_deployment_correctness.md`: `missing`
- `docs/03_evidence/eds_init_pg_diverse_sampling/level_1_mechanism_probe.md`: `missing`
- `docs/03_evidence/eds_init_pg_diverse_sampling/level_2_online_smoke.md`: `missing`
- `docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-11-rollout-rbf-level3-parameter-sweep.md`: `present`
- `docs/03_evidence/eds_init_pg_diverse_sampling/level_3_libero_object_success.md`: `missing`
- `docs/03_evidence/eds_init_pg_diverse_sampling/level_4_libero_pro_ood.md`: `missing`
- `docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-12-libero-pro-object-swap-rdt-eds-rbf-report.md`: `present`

## Final Verdict

- Deployment correctness: `inconclusive` until Level 0 passes.
- Algorithm effectiveness: `inconclusive` until Level 1 through Level 4 are reviewed.

Previous non-`libero_object` OOD results are excluded because they were caused by wrong checkpoint loading and are not evidence against EDS.
