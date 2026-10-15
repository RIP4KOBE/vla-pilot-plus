# run_002 Partition Diagnostic Summary

Decision: `KEEP_DIAGNOSTIC_EVIDENCE_AND_AUTHORIZE_ONE_QD1_PROTOCOL`

Validity gates: `PASS`
Scientific gates: `PASS`

## Primary observations

- Eligible 4x4 records: 4567
- Baseline replay mismatches: 0
- Candidate unrepresented overflow P95: 0.0
- Raw out-of-initial-bounds P95: 0.875
- Equal-chunk resolution improvement median: 0.30077537050932673
- Equal-profile resolution improvement median: 0.3093476806981762
- Occupied-mode ratio median: 0.9375
- Archive-spread ratio median: 2.0087442728526663
- Global-best preservation: 1.0

## Gates

| Gate | Type | Result | Observed |
| --- | --- | --- | --- |
| `input_manifest` | validity | PASS | `{"expected_records":4705,"files":27,"matching_hashes":27,"source_records":4705}` |
| `baseline_exactness` | validity | PASS | `{"eligible_records":4567,"mismatch_records":0}` |
| `record_validity_and_accounting` | validity | PASS | `{"analyzed_records":4567,"malformed_records":0,"non_4x4_records":138}` |
| `permutation_equivariance` | validity | PASS | `{"failure_records":0}` |
| `unrepresented_overflow` | scientific | PASS | `{"candidate_p95":0.0,"raw_initial_bounds_p95":0.875}` |
| `endpoint_resolution` | scientific | PASS | `{"equal_chunk_median":0.30077537050932673,"equal_profile_median":0.3093476806981762}` |
| `target_task_strata` | scientific | PASS | `{"support_count":4,"task_medians":{"3":0.27393654158461966,"5":0.3181650791508178,"8":0.32625430750283024,"9":0.30853641714640234},"worst":0.27393654158461966}` |
| `mode_and_spread_retention` | scientific | PASS | `{"archive_spread_ratio_median":2.0087442728526663,"occupied_mode_ratio_median":0.9375}` |
| `global_best_preservation` | scientific | PASS | `{"preserved_ratio":1.0}` |
| `zero_external_calls` | validity | PASS | `{"cuda":0,"environment":0,"model":0,"network":0,"reward":0,"vlm":0}` |

This is zero-episode geometry/archive evidence. It does not change the 2/10 historical best or the three-task target gap.
