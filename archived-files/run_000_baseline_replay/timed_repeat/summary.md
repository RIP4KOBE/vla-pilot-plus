# `run_000_baseline_replay` Summary

Decision: `KEEP_DIAGNOSTIC_EVIDENCE`. All support gates passed: `true`.

## Target-linked result

This zero-episode replay does not change the historical best (`2/10`) or target gap (`3`). It rules out direct population/iteration scaling as the next intervention: the 18 valid budget configurations reached at most `1/10`.

## Mechanism facts

- Original task matrix: `{"eds_quality_diversity_sparse_primary": [5, 8], "eds_quality_diversity_uniform_primary": [], "p2_stage_on_abs_rbf_control": [3, 8, 9]}`.
- Budget success-task union: `[0, 7, 8, 9]`; no configuration reached `>=5/10`.
- Profile coverage median: `1.0`; overflow P95: `0.98125`.
- Parsed QD chunk records: `4705`; zero-direct-elite ratio: `1.000000`; archive-only-parent ratio: `1.000000`.
- Missing metrics files: `0`; malformed records: `0`; missing required fields: `0`.

## Gate table

| Gate | Result | Criterion |
| --- | --- | --- |
| `catalog_checksums` | `PASS` | all catalog files exist and SHA-256 match |
| `original_task_matrix` | `PASS` | exactly {'p2_stage_on_abs_rbf_control': [3, 8, 9], 'eds_quality_diversity_uniform_primary': [], 'eds_quality_diversity_sparse_primary': [5, 8]} |
| `budget_target_boundary` | `PASS` | maximum valid success <=1/10 and no >=5/10 result |
| `elite_and_parent_ecology` | `PASS` | >=95% zero direct elite carryover, >=95% archive-only parents, and num_elites no-op audit passes |
| `coverage_overflow_saturation` | `PASS` | profile coverage median >=0.9 and overflow P95 >=0.75 |
| `parser_accounting` | `PASS` | all expected metrics files parsed; malformed/skipped/missing-field counts explicit |

## Decision boundary

Observations support an allocation/quality-retention audit, not an immediate online change. H2 reward calibration and H5 aliasing remain unresolved. Generic continuity smoothing is deprioritized by the historical clean-tail task regression.

Next protocol candidate: `run_001_allocation_ecology_diagnostic`.
