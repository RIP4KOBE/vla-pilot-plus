# `run_001_allocation_ecology_diagnostic` Protocol v4 Temporal-Alignment Amendment

Status: `PROTOCOL_LOCKED_V4_BEFORE_RECOVERY_EXECUTION`

Locked UTC: `2026-08-10T15:32:29Z`

Provenance: v3 commit `f6d7bc9a1d579fcbb55e36905beafd1a2ba8264c`. After v3, two single-file validity prechecks (not an aggregate run) showed that an iteration can report `qd_coverage_ratio_by_iter[i] == 1.0` while its parent slot map contains 15 cells.

## Root cause

Source ordering is:

1. allocate parents from the current archive and record `qd_parent_slots_by_cell_by_iter[i]`;
2. generate/evaluate offspring;
3. update the archive;
4. record `qd_coverage_ratio_by_iter[i]` from the post-update archive.

Thus post-update coverage is one step too late for identifying whether the archive used for parent allocation was saturated. The transition iteration that inserts the 16th cell is not a saturated-parent allocation, even though its post-update coverage is 1.0.

## Binding correction

The scientific estimand remains “allocation when the parent archive is saturated.” It is now source-faithfully defined as:

> `qd_parent_slots_by_cell_by_iter[i]` contains exactly 16 numeric cell IDs and every slot count is positive.

`qd_coverage_ratio_by_iter[i]` remains a reported post-update diagnostic but is not the saturation selector. The analyzer must not classify a 15-cell slot map as malformed merely because the post-update coverage is 1.0; it must exclude that transition iteration from saturated-parent metrics.

All v1–v3 accounting, cell reconstruction, quality grouping, thresholds, bootstrap, decision rules, output path and zero-call scope remain unchanged. No aggregate H4 result was computed between v3 and v4. V4 is the final permitted schema amendment for this run; any further validity failure triggers infrastructure review rather than another repair.
