# `run_001_allocation_ecology_diagnostic` Summary

Decision: `INVALID_REPAIR_ANALYZER`. H4 supported: `false`.

This is a zero-episode saved-trace diagnostic. The best remains `2/10`; target gap remains `3`.

## Accounting

- Profiles/traces/stages: `27` / `540` / `9000`.
- Saturated trace-iterations: `7041`.
- Child records: `374400`.
- Trace failures / root failures: `52` / `0`.

## Primary result

- Overall top-minus-bottom margin: mean `0.0406184389470919`, median `0.03530883789062501`.
- Trace-cluster bootstrap 95% CI: `[0.038534826763014285, 0.04269928904889965]`.
- Top-quartile slot share: uniform `0.25`, sparse `0.20869183407493672`.
- Family median margins: uniform `0.0389802720811632`, sparse `0.031898230032647294`.
- Rank-1-minus-bottom overall median: `0.039696587456597224`.

## Gates

| Gate | Result | Criterion |
| --- | --- | --- |
| `profile_accounting` | `PASS` | exactly 27 valid profiles |
| `trace_accounting` | `FAIL` | exactly 540 traces and 9000 metadata-matched stages with no trace failures |
| `source_roots` | `PASS` | all traces under immutable /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity |
| `saturated_iteration_support` | `PASS` | >=2700 saturated trace-iterations |
| `quality_blind_slot_share` | `PASS` | mean top-quartile slot share <=0.35 in both families |
| `overall_inheritance_bootstrap` | `PASS` | trace-cluster bootstrap 95% CI lower bound >0 |
| `family_inheritance` | `PASS` | median per-trace top-minus-bottom margin >0 in both families |
| `rank1_inheritance` | `PASS` | overall median per-trace rank1-minus-bottom margin >0 |

Historical success/failure and task 3/5/8/9 strata are descriptive only; see `analysis.json`.

Next direction: `repair_run_001_under_versioned_protocol`.
