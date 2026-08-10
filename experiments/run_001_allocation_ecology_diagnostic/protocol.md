# `run_001_allocation_ecology_diagnostic` Protocol

Status: `PROTOCOL_LOCKED`

Label: `CONFIRMATORY`

Scope: `QD-0` saved-trace counterfactual; no behavioral or algorithm change

Locked UTC: `2026-08-10T15:20:46Z`

## Objective and target link

Determine whether the current saturated QD archive wastes fixed offspring slots on low-quality cells and whether high-quality archive parents actually produce higher-reward children. This is the minimum evidence required before authorizing a `QD-1` exploit/explore allocation change intended to recover control-success tasks 3 and 9 while retaining QD successes 5 and 8.

The historical best remains `2/10`; the target gap remains 3 tasks. This run consumes zero LIBERO episodes and cannot change either value. It may only authorize or reject a future allocation candidate.

## Evidence packet

| Evidence | SHA-256 / commit | Observation | Consequence |
| --- | --- | --- | --- |
| `run_000` analysis | `6ad1308363a512c9b2529a090682669bb096d5000159571d5798ddd296bad963` | 4,705/4,705 chunks use archive-only parents; direct elite carryover is zero | audit allocation productivity before changing descriptor |
| `run_000` result | `e0b252c` | 18 compute configs max at 1/10 | no further population/iteration scaling |
| Original task matrix | catalog-verified | control `{3,8,9}`; sparse `{5,8}` | desired allocation change must target retention, not coverage alone |
| `num_elites` no-op audit | `f75e48c5c12a80d18ef9378ae6db67690288c55f2c5963d1099f26272c778120` | non-CEM QD branch uses empty elite indices | `num_elites` cannot supply exploitation |
| Example sparse trace | `0d3d4d8f99230add03764fec2839f58a1932b858c9531238d78dd2a851135174` | stages contain child rewards, parent ranks/indices and QD slot telemetry | enables offline parent-quality inheritance analysis |
| QD source | Git blob `a9138b1f819d648f0d2b525a0a81e9142c13bd13` | allocation is uniform or inverse cumulative visitation; reward is not an allocation weight | quality-blind mechanism is code-grounded |

Conflicting evidence is explicit: a cell-local archive already retains its best reward, and the final action is the global archive best. Therefore zero direct elite carryover alone does not establish a defect. H4 is supported only if saved offspring show positive parent-quality inheritance while saturated allocation remains near quality-blind.

## Locked hypothesis and predictions

H4 mechanism statement: under a full 16-cell archive, uniform/inverse-visitation allocation gives roughly proportional budget to all occupied cells. If top-quality parents have better offspring yield, this under-exploits lineages most likely to retain task progress.

Predictions:

1. In saturated trace-iterations, the top reward quartile of archive parents receives no more than 35% of offspring slots in both uniform and sparse families.
2. Within a trace-iteration, children of top-quartile parents have higher mean reward than children of bottom-quartile parents.
3. The trace-cluster bootstrap 95% CI for the top-minus-bottom child-reward margin is strictly positive overall; family medians are positive for both uniform and sparse.
4. Rank-1 parent offspring outperform bottom-quartile offspring directionally, supporting an explicit global-quality component rather than only a broad top-quartile effect.
5. The effect is reported separately for historical success/failure tasks and tasks 3,5,8,9; no proxy-only subgroup result is promoted as task success.

## Dataset and estimator lock

- Dataset: every `mechanism_trace.pt` attached to the 27 valid profiles enumerated by `run_000` (9 original QD profiles plus 18 budget profiles), expected `27 × 20 = 540` traces and `5,400` full-process trace-iterations.
- Loader: `torch.load(..., map_location="cpu", weights_only=True)`; no policy/model import.
- Unit of analysis: `(profile, task, episode, chunk, iteration, child)` from `full_process_after_rollout` stages.
- Parent quality: `parent_ranks`, where rank 1 is best. Top quartile is ranks `1..4`; bottom quartile is ranks `13..16` for a saturated 16-cell archive.
- Saturated iteration: corresponding `qd_coverage_ratio_by_iter == 1.0`.
- Slot share: count of children assigned to the rank group divided by population size.
- Inheritance margin: within-iteration mean child reward(top ranks 1..4) minus mean child reward(bottom ranks 13..16).
- Aggregation: first average iteration margins within each trace; report profile/family/task distributions without weighting longer episodes more heavily.
- Uncertainty: deterministic trace-cluster bootstrap, 10,000 resamples with local NumPy RNG seed `1701`; percentile 95% CI. Global RNG state must not be modified.
- Prospective fixed-budget estimate: at official population 16, report the estimated mean reward effect of moving exactly 4 slots from bottom-quartile to top-quartile parent draws. This is a diagnostic estimate, not an executed counterfactual.

## Gates

Validity gates:

1. exact trace accounting: 540 files, 5,400 expected full-process stages, no unsafe load, malformed stage, nonfinite reward, missing rank, or population/slot mismatch;
2. all source paths remain under immutable historical roots and all outputs under the owned artifact root;
3. repeated analysis produces byte-identical canonical JSON.

H4 support gates, all required:

1. at least 2,700 saturated trace-iterations are available;
2. mean top-quartile slot share in saturated iterations is `<=0.35` separately in uniform and sparse families;
3. overall trace-cluster bootstrap 95% CI lower bound for top-minus-bottom child reward is `>0`;
4. median per-trace top-minus-bottom margin is `>0` separately for uniform and sparse families;
5. rank-1 versus bottom-quartile median per-trace margin is `>0` overall.

H4 is rejected for an allocation candidate if any support gate fails. A task subgroup is descriptive and cannot override a failed global gate. If rejected, the deterministic next direction is `run_002_partition_diagnostic` under H1. If supported, the next direction is a separate `QD-1` protocol for a fixed `4/16` quality-reserve plus `12/16` exploration allocation; no implementation is authorized by this protocol.

## EDS+QD change map

| EDS+QD step | State | Change |
| --- | --- | --- |
| EDS initial proposal | Frozen | none |
| EDS rollout/mutation/budget | Frozen | saved offspring only; fixed budget audited |
| QD descriptor/partition | Frozen | condition on saturated current cells |
| QD archive/replacement | Frozen | read parent-quality ranks only |
| QD parent/allocation | Frozen | measure slot share and offspring yield; no reallocation |
| QD quality/elitism | Frozen | use existing reward ranks; no new score |
| QD final selection | Frozen | none |
| QD cross-chunk state | Frozen | subgroup reporting only |
| EDS+QD instrumentation | Changed | deterministic CPU trace analyzer and compact summaries |

Checkpoint/backbone, perception/grounding, prompts, Stage recognizer, environment/reset, executor, evaluator, model/reward/VLM calls, task mapping and all historical artifacts are frozen.

## Execution

```bash
conda run -n vla-pilot python src/analyze_qd_allocation_ecology.py \
  --replay-analysis /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_000_baseline_replay/analysis.json \
  --output-root /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_001_allocation_ecology_diagnostic \
  --bootstrap-seed 1701 \
  --bootstrap-resamples 10000
```

- Split/tasks/seeds: historical saved traces only; task IDs are descriptive strata.
- Expected new online episodes / attempts / GPU-hours: `0 / 0 / 0`.
- Expected environment/model/reward/VLM calls: all zero.
- GPU: none.
- Storage admission: output is small; nevertheless the frozen 50 GiB floor remains in force for later online work.
- Raw outputs: `analysis.json`, `summary.md`, checksum, and optional compact CSV only in the owned `run_001` artifact directory.

## Precommitted decision

If validity and all H4 support gates pass, record `KEEP_DIAGNOSTIC_EVIDENCE`, keep target gap 3, and lock one fixed `4/16` QD-1 allocation protocol. If validity fails, mark `INVALID` and repair only the analyzer under a versioned protocol. If validity passes but H4 support fails, record `REJECT_H4_ALLOCATION_CANDIDATE` and move to H1 partition diagnostics without an H4 online run.
