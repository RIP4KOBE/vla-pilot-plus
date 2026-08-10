# `run_001_allocation_ecology_diagnostic` Protocol v3 Repair

Status: `PROTOCOL_LOCKED_V3_AFTER_INVALID_INFRASTRUCTURE_ATTEMPT`

Locked UTC: `2026-08-10T15:30:11Z`

Provenance:

- v1 commit: `dcf234b6999165de0a5bca4a8e44332896cc61dc`;
- v2 accounting amendment: `91ddd34f64d129549147f42c64244b552398a624`;
- invalid first analyzer artifact: `analysis.json` SHA-256 `c59cbe979706320fb90ecee7a1bfe874fe3222b5f0578a23fa3b0b2e0c5e24b5`;
- invalid classification: 540 files and 9,000 stages were found, but 360 budget traces were rejected because the analyzer incorrectly constrained occurrence ranks to `<=16`.

The invalid attempt is infrastructure evidence only. Its H4 reward/slot values are inadmissible and cannot influence the repaired result or direction decision.

## Root cause and repair lock

Source inspection confirms `allocate_parent_slots` creates parents by iterating occupied cell IDs in sorted order and repeating each cell according to `slot_counts`. Trace `parent_ranks`, however, ranks every parent occurrence in the population. Therefore budget profiles legitimately contain ranks `1..32`, `1..48`, or `1..64`; duplicated occurrences from the same archive cell receive adjacent but distinct ranks.

The repaired analyzer must, for every saturated iteration:

1. require `parent_ranks` to be a permutation of `1..population_size`;
2. reconstruct the child-to-parent-cell vector exactly as the source does: numeric-sort `qd_parent_slots_by_cell_by_iter[iter]`, then repeat each cell ID by its slot count;
3. require 16 unique cells and total slots equal to population size;
4. compute each cell's parent-quality score as the mean occurrence rank of that cell's repeated parents;
5. sort cells by `(mean_occurrence_rank, cell_id)` and define top/bottom quartiles as the best/worst four cells;
6. calculate child reward and slot-share metrics using those reconstructed cell groups.

For official population 16 this reduces exactly to ranks `1..4` and `13..16`. For larger historical budget profiles it preserves the v1 scientific estimand—top/bottom quartiles of 16 archive cells—without confusing occurrence rank with cell rank.

No threshold changes are permitted. V1 hypotheses, bootstrap seed/resamples, `>=2,700` saturated iterations, `<=0.35` family slot shares, strictly positive CI/family/rank-1 gates, task strata, decision rules and zero-call scope remain binding. V2's 540-file/9,000-stage accounting remains binding.

## Recovery execution

The invalid artifact remains at the original `run_001` root. Repaired outputs must use a new directory:

```bash
conda run -n vla-pilot python src/analyze_qd_allocation_ecology.py \
  --replay-analysis /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_000_baseline_replay/analysis.json \
  --output-root /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_001_allocation_ecology_diagnostic/repaired_v3 \
  --bootstrap-seed 1701 \
  --bootstrap-resamples 10000
```

The repaired canonical JSON must be reproduced byte-for-byte once. If the same failure recurs, the run remains invalid and no further repair is allowed without an outer-loop infrastructure review.
