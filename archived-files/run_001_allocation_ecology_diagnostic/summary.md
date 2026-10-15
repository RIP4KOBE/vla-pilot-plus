# `run_001_allocation_ecology_diagnostic` Summary

Decision: `INVALID_REPAIR_ANALYZER`. H4 supported: `false`.

This is a zero-episode saved-trace diagnostic. The best remains `2/10`; target gap remains `3`.

## Accounting

- Profiles/traces/stages: `27` / `540` / `9000`.
- Saturated trace-iterations: `1070`.
- Child records: `28800`.
- Trace failures / root failures: `360` / `0`.

## Primary result

- Overall top-minus-bottom margin: mean `0.059122432756198925`, median `0.06258519490559895`.
- Trace-cluster bootstrap 95% CI: `[0.054995588467439224, 0.06335718570912359]`.
- Top-quartile slot share: uniform `0.25`, sparse `0.25`.
- Family median margins: uniform `0.06340484619140625`, sparse `0.05350494384765625`.
- Rank-1-minus-bottom overall median: `0.06802174401661706`.

## Gates

| Gate | Result | Criterion |
| --- | --- | --- |
| `profile_accounting` | `PASS` | exactly 27 valid profiles |
| `trace_accounting` | `FAIL` | exactly 540 traces and 9000 metadata-matched stages with no trace failures |
| `source_roots` | `PASS` | all traces under immutable /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity |
| `saturated_iteration_support` | `FAIL` | >=2700 saturated trace-iterations |
| `quality_blind_slot_share` | `PASS` | mean top-quartile slot share <=0.35 in both families |
| `overall_inheritance_bootstrap` | `PASS` | trace-cluster bootstrap 95% CI lower bound >0 |
| `family_inheritance` | `PASS` | median per-trace top-minus-bottom margin >0 in both families |
| `rank1_inheritance` | `PASS` | overall median per-trace rank1-minus-bottom margin >0 |

Historical success/failure and task 3/5/8/9 strata are descriptive only; see `analysis.json`.

Next direction: `repair_run_001_under_versioned_protocol`.
