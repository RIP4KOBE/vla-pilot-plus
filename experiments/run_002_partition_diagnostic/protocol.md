# `run_002_partition_diagnostic` Protocol

Status: `PROTOCOL_LOCKED`

Label: `CONFIRMATORY`

Scope: `QD-0` deterministic offline counterfactual; no algorithm behavior is changed by this run

Locked UTC: `2026-08-10T15:43:49Z`

## Objective and target link

Test exactly one implementable H1 partition change before spending an online episode. The question is whether a causal expanding 4x4 partition can turn the historical edge-clamped descriptor stream into better-resolved archive modes while preserving the reward-best action, archive endpoint spread, fixed parent-slot count, and the `176` evaluations per complete baseline chunk.

This run cannot change the historical `2/10` best or the target gap of three tasks. It can only authorize or reject one future `QD-1` candidate. If rejected, H1 is parked for this cycle; no neighboring bounds, grid, temperature, CVT, or reservoir variant may be tried.

## Immutable evidence packet

- Source manifest: `run_000_baseline_replay/analysis.json`, SHA-256 `6ad1308363a512c9b2529a090682669bb096d5000159571d5798ddd296bad963`.
- Its ordered table of 27 raw metrics paths, hashes, total records, and QD records has SHA-256 `d9ce3eaa6df1280cdd5dc58dcf51d3a71ac44d383f7e1c828938a0c440ac76cd` when emitted as tab-separated `path,sha256,records,qd_records` rows.
- Audited historical boundary: 4,705 QD chunks, raw descriptor-overflow P95 `0.875`, profile overflow P95 `0.98125`, coverage median `1.0`, and zero direct elite carryover.
- Task evidence link: control successes `{3,8,9}`; best QD successes `{5,8}`. A later online candidate must preserve the exploration sentinel 5 and retained task 8 while recovering task 3 or 9; offline geometry alone is not task success.
- Historical expand/bounds OFATs did not pass adoption, so this protocol does not test another scalar expansion. Grid3 was a valid task failure and old Grid5 was invalid due source bookkeeping; neither is reinterpreted here.

All source paths outside this worktree and the owned artifact root are read-only.

## Locked counterfactual: `causal_envelope_v1`

The baseline is the current fixed-initial partition in `core/qd_ed.py`: initial quantile bounds remain frozen and every later descriptor outside them is clamped to an edge cell.

The sole counterfactual keeps the descriptor, initial bounds, grid `(4,4)`, cell capacity one, reward elitism, parent policy, population, iterations, and final global-reward selection unchanged. At offspring iteration `i`, after the batch has been generated and scored but before insertion:

1. compute the finite component-wise minimum and maximum of that current descriptor batch;
2. replace each bound with the union of the previous bound and the current batch envelope: `lo_i = min(lo_{i-1}, batch_min)`, `hi_i = max(hi_{i-1}, batch_max)`;
3. if either bound changed, reassign the existing archive elites under the expanded bounds, resolving any collision with the existing reward-then-fingerprint rule;
4. assign and insert the current candidates under the same expanded bounds.

The bounds never shrink. Initial insertion is byte-for-byte baseline behavior. The rule uses only present/past descriptors, never future observation, task success, simulator state, Stage output, or reward to set a boundary. It introduces no tunable scale, extra model/reward/VLM call, new cell, or extra parent slot.

The offline replay uses stored candidate streams. It therefore identifies partition and archive effects under a common stream, but cannot simulate the later offspring that changed parent cells would generate online.

## Frozen estimands

- `raw_out_of_initial_bounds`: descriptors outside the original initial bounds. This must be reported and cannot be renamed away; it should remain identical between paired replays.
- `unrepresented_overflow`: descriptors outside the bounds actually used for their insertion. For the counterfactual this is measured after causal expansion.
- `within_cell_endpoint_sse`: for each batch, the sum of squared XY distance from each descriptor to the empirical centroid of the descriptors assigned to its cell, divided by candidate count. Empty/singleton cells contribute zero.
- `resolution_improvement = 1 - candidate_sse / baseline_sse`, evaluated only where baseline SSE is positive.
- `effective_occupied_modes`: final occupied archive-cell count.
- `archive_endpoint_spread`: mean pairwise XY distance among final archive elites.
- `archive_global_best`: reward, fingerprint, and selected cell under deterministic reward-then-fingerprint ordering.

Metrics are first computed per chunk, then aggregated with equal chunk weight and separately with equal profile/task weight. No result-dependent reweighting or threshold change is allowed.

## Validity gates

All must pass before scientific gates are interpreted:

1. all 27 source files exist and match the frozen SHA-256 table; malformed, missing-field, nonfinite, skipped, invalid-profile, and non-4x4 counts are explicit;
2. the fixed-initial replay exactly reproduces every eligible record's per-iteration occupied cells, coverage, overflow counts/ratios, per-cell elite rewards, archive-best reward, selected reward/fingerprint/cell, and accounting totals;
3. candidate accounting equals every stored population count; archive capacity is one and grid size remains 16;
4. three complete analyzer executions produce identical canonical scientific JSON SHA-256;
5. within-batch descriptor permutations leave bounds, cell assignments as a fingerprint-to-cell map, archive elites, and summary metrics invariant;
6. the analyzer reads only JSONL/manifest data and makes zero environment, model, reward, VLM, CUDA, or network calls.

The historical valid 3x3 profile is parsed and reported but excluded from the paired 4x4 candidate estimand. The invalid historical Grid5 profile is not in the frozen 27-file raw set. These exclusions are fixed by schema, not outcome.

## H1 support and rejection gates

All support gates must pass:

1. counterfactual `unrepresented_overflow` P95 is `<=0.25`, while paired `raw_out_of_initial_bounds` remains exactly unchanged and is reported beside it;
2. median `resolution_improvement >=0.20` across eligible chunk-iterations, and the equal-profile median is also `>=0.20`;
3. at least two of the target-linked historical task strata `{3,5,8,9}` have task-median resolution improvement `>=0.20`, with no stratum below `-0.05`;
4. median candidate/baseline final occupied-mode ratio is `>=0.90` and median archive-endpoint-spread ratio is `>=0.90`;
5. the global-best reward and fingerprint are preserved for `100%` of paired chunks; any loss is a hard reject;
6. no meter-scale descriptor/spread nonfinite value, call-budget change, accounting violation, or determinism/permutation failure occurs.

H1 is rejected for this cycle if any gate fails, if apparent improvement exists only because raw overflow is relabeled, or if resolution improves by collapsing archive modes/spread. A passing offline result authorizes only a separately protocol-locked `QD-1` implementation, tests, CPU preflight, and then the frozen LIBERO mechanism preflight/Dev-A gates. It does not authorize formal evaluation or claim success improvement.

## EDS+QD change map

| EDS+QD step | State | This run |
| --- | --- | --- |
| EDS initial proposal | Frozen | replay stored initial candidates |
| EDS rollout/mutation/budget | Frozen | replay stored offspring; no regeneration |
| QD descriptor/partition | Counterfactual only | compare fixed-initial with `causal_envelope_v1` |
| QD archive/replacement | Counterfactual only | deterministic rebin on expansion, capacity-one reward elite |
| QD parent/allocation | Frozen | no slot reallocation is inferred from stored streams |
| QD quality/elitism | Frozen | existing reward/fingerprint ordering |
| QD final selection | Frozen | archive global reward best |
| QD cross-chunk state | Frozen | fresh chunk-local replay |
| EDS+QD instrumentation | Changed after protocol | add deterministic JSONL counterfactual analyzer |

Checkpoint/backbone, perception/grounding, task prompts, Stage recognizer/settings, environment/reset, executor, evaluator, and all non-EDS+QD policy steps remain frozen.

## Execution

```bash
python src/analyze_qd_partition_counterfactual.py \
  --baseline-analysis /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_000_baseline_replay/analysis.json \
  --partition causal_envelope_v1 \
  --required-grid 4 4 \
  --task-strata 3 5 8 9 \
  --permutation-seed 1702 \
  --output-root /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_002_partition_diagnostic
```

- Split/tasks/seeds: immutable historical QD records only; task IDs are descriptive strata and do not alter the partition.
- Expected online episodes / attempts / GPU-hours: `0 / 0 / 0`.
- Expected model / reward / VLM / environment calls: `0 / 0 / 0 / 0`.
- GPU: none.
- Repeats: one canonical execution plus two isolated deterministic repeats; only canonical output is retained as the scientific artifact, repeat hashes are recorded.
- Outputs: owned `run_002_partition_diagnostic/{analysis.json,summary.md,input-manifest.json}` with SHA-256 references committed to Git.
- Pause: check `.autoresearch/PAUSE` immediately before execution; if present, do not dispatch.

## Precommitted decision

- All validity and H1 gates pass: `KEEP_DIAGNOSTIC_EVIDENCE_AND_AUTHORIZE_ONE_QD1_PROTOCOL`.
- Validity fails: mark `INVALID`; at most one schema-only repair may receive a new protocol commit before rerun. A second validity failure ends this run and triggers outer-loop review.
- Valid result but any H1 gate fails: `REJECT_H1_PARTITION_FOR_THIS_CYCLE`; do not test adjacent partition variants, and pivot to the next evidence-ranked EDS+QD mechanism.

In all cases the target gap stays three until valid online task results say otherwise.
