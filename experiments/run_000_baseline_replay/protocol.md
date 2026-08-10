# `run_000_baseline_replay` Protocol

Status: `PROTOCOL_LOCKED`  
Label: `CONFIRMATORY`  
Scope: `QD-0` observer/offline replay; no behavioral or algorithm change  
Locked UTC: `2026-08-10T15:05:31Z`

## Objective and target link

Recompute the original EDS-QD and later search-budget evidence from immutable raw artifacts, verify their checksums and task matrices, and determine which single QD mechanism diagnosis most directly supports closing the historical `2/10 → >=5/10` target gap. This run consumes zero LIBERO episodes and cannot change the current best or target gap.

The replay must distinguish observations from inferences and must not promote a candidate merely because an archive proxy improves. It is expected to rule out direct population/iteration scaling and to select exactly one next `QD-0` diagnosis. No online candidate is authorized by this protocol.

## Historical evidence packet

The machine-readable source list is frozen in `data/historical-evidence-catalog.jsonl`. The primary evidence is:

| Source | SHA-256 | Frozen observation | Design impact |
| --- | --- | --- | --- |
| Original EDS-QD report | `cbaa9df290e40bc8cca4affedd7b17fb46b3d32832f6e68d63eb77ae1340e16c` | control `3/10` tasks 3,8,9; best QD `2/10` tasks 5,8 | replay the loss/retention matrix; no reuse of formal results for tuning |
| Original formal audit | `56c4320e2f793e9dc856e34b3830e49595d69eb541d83b9d624b764bd81170ba` | coverage saturated; overflow high; reward changes near zero | quantify H1/H2/H4 diagnostics from raw records |
| Budget-sweep report | `580cf8c007053c497866d80a5e8c643a4a15c3bbb8281f8de5742a5bbff30c1e` | 18 configs, all `0/10` or `1/10` | reject brute-force compute scaling if machine replay agrees |
| Budget-sweep formal audit | `ff7a86b349e989f433aa5402abfbef6a75ff5e68510118c80a40e6ae278291f7` | 180 cells; 201 physical attempts; old cap exceeded by one | retain exception; do not treat sweep as a clean acceptance study |
| Clean-tail report | `7eeb573ea941d7dbf5467c950d3201d59de2960dbe2c2ca32c0d01293f7cfd8c` | motion smoothing changed `3→2→0` despite much smaller jumps | reject generic continuity smoothing as first intervention |
| `num_elites` no-op audit | source under budget-sweep `analysis/` | QD branch carries zero direct CEM elites | audit the global-quality-retention gap before changing allocation |

Conflicting evidence is preserved: the sparse baseline gains task 5 while larger-budget profiles occasionally succeed on tasks 0,7,8,9. These sporadic gains show behavioral variation, but not monotonic compute benefit or retention of the known control successes.

## Locked hypotheses and predictions

- H1 observation prediction: across valid QD records, final normalized coverage is near saturation while descriptor overflow remains high; coverage therefore does not resolve useful behavior.
- H4 observation prediction: QD iterations report zero direct elite carryover and allocate offspring only through archive-cell parents; `num_elites` is behaviorally inactive when CEM is disabled.
- Budget prediction: success count has no positive monotonic relationship with population, iterations, or candidate evaluations across the 18-config sweep.
- H3 boundary prediction: generic reduction of motion length/jump is not sufficient for success, as the clean-tail historical task outcome worsened.
- H2/H5 limitation prediction: existing telemetry is insufficient to claim stage-progress reward calibration or within-cell future-value aliasing; those claims must remain unresolved.

## Primary metrics and gates

Primary output is a deterministic evidence table containing exact task successes, validity, evaluations-per-chunk, median final coverage, descriptor-overflow P95, turnover, elite carryover, parent-source counts, and reward delta for every parseable profile/config.

Support gates:

1. all catalog inputs exist and SHA-256 match;
2. original audited task matrix replays exactly: control `{3,8,9}`, uniform primary `{}`, sparse primary `{5,8}`;
3. budget-sweep maximum valid success count is `<=1/10`, with no valid `>=5/10` result;
4. at least 95% of parseable QD chunk records have `elite_carryover_count_observed == 0`, and their QD parent source is archive offspring;
5. final coverage median `>=0.9` and overflow P95 `>=0.75` for the replayed primary/budget QD evidence;
6. parser accounting is explicit: skipped/invalid/missing records are counted, not silently dropped.

Refute or invalidate:

- any checksum mismatch, task-matrix mismatch, or non-deterministic repeated replay makes the run `INVALID`;
- a valid budget configuration at `>=5/10` refutes the premise and stops algorithm modification pending audit;
- positive monotonic task success with compute refutes the decision to rule out scaling;
- failure to obtain required raw fields leaves the corresponding mechanism unresolved rather than treating absence as support.

## EDS+QD change map

| EDS+QD step | State | Change |
| --- | --- | --- |
| EDS initial proposal | Frozen | read-only historical metrics |
| EDS rollout/mutation/budget | Frozen | audit compute scaling only |
| QD descriptor/partition | Frozen | replay coverage/overflow only |
| QD archive/replacement | Frozen | replay turnover/reward only |
| QD parent/allocation | Frozen | replay parent-source/elite-retention telemetry only |
| QD quality/elitism | Frozen | audit reward and no-op `num_elites` evidence only |
| QD final selection | Frozen | no counterfactual execution |
| QD cross-chunk state | Frozen | not evaluated |
| EDS+QD instrumentation | Changed | add deterministic read-only replay script and small JSON/Markdown summaries |

Checkpoint/backbone, perception, prompts, Stage recognizer, environment/reset, executor, and evaluator are frozen. The only implementation after this commit may be offline parsing/instrumentation.

## Execution

```bash
python src/replay_historical_eds_qd.py \
  --catalog data/historical-evidence-catalog.jsonl \
  --artifact-root /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity \
  --budget-root /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/outputs/search_budget_sweep_20260808 \
  --output-root /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_000_baseline_replay
```

- Split/tasks/seeds: immutable historical records only; no new split use.
- Expected online episodes / attempts / GPU-hours: `0 / 0 / 0`.
- GPU: none.
- Determinism check: run twice into separate temporary summaries and require identical canonical JSON SHA-256.
- Raw outputs: owned artifact root `run_000_baseline_replay/`; only compact analysis/checksum references enter Git.
- Safety: no environment, model, reward, VLM, or action calls.

## Precommitted decision

If all support gates pass, mark `KEEP` for the diagnostic evidence only, permanently reject direct compute scaling as the next optimization, and select one next `QD-0` audit by this order: (1) quality-retention/allocation ecology if raw lineage and reward telemetry can resolve it; otherwise (2) overflow-aware partition counterfactual; otherwise (3) reward-progress calibration. The next audit receives a new protocol commit. If gates fail, repair only the parser/provenance under a versioned protocol; do not start online work.
