# Research Findings

## Research Question

Can a mechanism-grounded, compute-accounted successor to the audited EDS-QD baseline reach at least 5/10 valid successes on frozen LIBERO-PRO `libero_object_swap` without evaluation leakage or safety regression?

## Current Understanding

The historical QD implementation is mechanically coherent in its supported 3x3/4x4 paths: it preserves one reward elite per target-relative endpoint-XY cell, allocates exactly 16 offspring slots, keeps 176 evaluations per full chunk, and passes archive/accounting/replay hard gates. That correctness did not translate into mechanism or task benefit. The valid QD treatments produced median normalized coverage of 1.0 while their offspring overflow P95 was 0.938–1.0, paired coverage gain was exactly 0, replacement-active ratios stayed below 0.50, and best-reward deltas were approximately zero. This is evidence that the old coverage variable is saturated and not evidence that useful behavioral diversity was preserved.

The task evidence is worse than the control: control succeeded on tasks 3, 8, and 9 (3/10); uniform primary succeeded on none; sparse primary retained task 8, gained task 5, and lost tasks 3 and 9 (2/10). Contact sheets support genuine behavioral divergence between profiles, but the historical automatic label `timeout without completion` is intentionally non-causal. It does not by itself identify target acquisition, grasp, transport, placement, or Stage Recognition as the mechanism of failure.

There is also a geometry warning. The control's selected trajectory-length median was 0.093 m and chunk-boundary jump P95 was 2.983. Valid QD variants generally increased trajectory length to roughly 0.103–0.139 m and jump P95 to roughly 3.35–4.90. This motivates continuity and execution-stability hypotheses, but causal attribution requires paired, stage-resolved probes.

The historical Grid5 result is invalid algorithm evidence. Its episodes hit `IndexError: tuple index out of range` when final archive selection indexed stale particle-source bookkeeping. Current HEAD contains a QD-aware source bookkeeping branch, but the old Grid5 outcomes remain invalid and must not be used to rank grid resolution. Future tests must explicitly cover archives with more occupied cells than population-source tuples before any online promotion.

The `run_000_baseline_replay` machine replay adds a stronger ecology boundary. Across 4,705 QD chunks from 27 original and budget-study metrics files, every chunk reported zero direct elite carryover and archive-only parent selection; the accumulated parent counts were 3,281,360 archive offspring and zero direct elites. The configured `num_elites` is a no-op in the non-CEM QD branch. Thus the current QD process has cell-local reward elitism but no explicit population budget reserved for globally strong lineages.

`run_001_allocation_ecology_diagnostic` is invalid and supplies no reward-inheritance conclusion. The audit exposed three telemetry semantics that must not be conflated: parent ranks apply to population occurrences rather than unique cells; parent slot maps are pre-update while same-index coverage is post-update; and sparse-priority can assign zero slots to occupied cells. After two infrastructure attempts the preregistered stop rule ended repair. H4 remains unresolved and is not authorized for online evaluation in this cycle.

Outer-loop cycle 1 pivots to H1 partition diagnostics. This choice is evidence-ranked, not novelty-ranked: H1 has valid and deterministic JSONL coverage/overflow telemetry, whereas H4's required inheritance evidence is invalid and H3's generic smoothing intervention has negative historical task evidence. Only one partition counterfactual is allowed before an online go/no-go, preventing a return to grid/bounds sweeps.

`run_002_partition_diagnostic` supports that single H1 counterfactual. Across 4,567 exact-replayed 4x4 chunks, causal monotonic bounds expansion reduced within-cell endpoint SSE by median 30.1% (30.9% with equal profile weight), with all target-linked historical task strata 3/5/8/9 above 27%. Median occupied-mode retention was 93.75%, archive endpoint spread increased 2.01x, and every global reward-best fingerprint was retained. The raw initial-bound overflow P95 remained explicitly 0.875; the zero candidate overflow is the post-envelope representability metric, not a claim that exploration stopped. This is strong offline authorization for one QD-1 test, not evidence of task success.

`run_010_causal_envelope_candidate` is now implemented but has not produced outcome evidence. The candidate expands bounds only from the current scored offspring batch, deterministically re-bins incumbents, conserves cumulative sparse-priority visits, and retains the unchanged reward/fingerprint global-best selection. The fixed policy remains the default. The frozen nine-file regression suite passes 781 tests; this establishes implementation compatibility, not success improvement. Offline fingerprint/preflight and all online gates remain pending.

Direct compute scaling is no longer an active direction. The 18 valid budget configurations ranged from 512 to 1,664 evaluations per complete chunk but all scored 0/10 or 1/10, with aggregate Spearman correlation 0.0 between evaluations/chunk and success. This does not prove compute can never help; it shows that compute without changing QD allocation/retention did not shrink the target gap.

## Key Results

- Historical contemporaneous control: 3/10 on frozen tasks/seeds.
- Historical uniform QD primary: 0/10; valid but failed task and mechanism-claim gates.
- Historical sparse QD primary: 2/10; gained task 5, retained task 8, lost tasks 3 and 9.
- Historical valid QD profiles: coverage median 1.0 with overflow P95 0.938–1.0 and paired coverage gain 0.
- All QD candidates: no adoption; decision manifest and report checksums verify.
- Planning baseline health check: 56 QD archive/runner/audit tests pass on base commit.
- `run_000_baseline_replay`: 6/6 gates PASS; 13/13 input hashes; 27/27 metrics files; 4,705 QD chunks; deterministic analysis SHA-256 `6ad13083…963`.
- Search-budget replay: 18 valid configurations, max 1/10, success-task union `{0,7,8,9}`, and no valid `>=5/10` result.
- `run_002_partition_diagnostic`: 10/10 frozen validity/scientific gates PASS; 4,567 exact 4x4 replays; resolution `+30.1%`; mode retention `0.9375`; spread ratio `2.0087`; global best retention `1.0`; three identical analysis hashes.

## Patterns and Insights

1. Occupancy saturation plus edge clamping makes coverage a weak promotion signal under the existing descriptor and frozen initial bounds.
2. Reward preservation alone is insufficient: similar best-reward deltas coexist with materially different environment outcomes.
3. Exploration can discover a new success (task 5) but currently fails to retain known control successes, indicating an exploit/retain problem rather than a simple lack-of-diversity problem.
4. The QD policies tend to generate longer or more discontinuous selected motion, which may consume the 720-step budget without completing placement.
5. A ten-task formal suite is too small to serve simultaneously as an iterative tuning set and an unbiased final acceptance set; development and validation seeds must be isolated before execution.
6. Increasing QD population/iterations without changing archive ecology does not preserve or combine successful modes.
7. The absence of a direct global-quality reserve is a concrete, code-and-telemetry-supported retention gap; it is not yet proof that any particular reserve ratio improves task success.
8. Saved mechanism traces require explicit temporal and entity-level schemas; occurrence ranks, archive-cell ranks, allocation occupancy and post-update coverage are not interchangeable.
9. A parameter-free causal envelope can improve geometric partition resolution without losing the reward-best candidate on a common stream, but only online parent/offspring feedback can establish a task benefit.

## Lessons and Constraints

- Never optimize or promote on normalized cell coverage alone.
- Do not treat edge-clamped cells as distinct useful modes without meter-scale and stage-progress evidence.
- Do not treat `timeout without completion` as a causal failure category.
- Preserve contemporaneous control and control-success retention in every promoted comparison.
- Keep the official task/seed mapping hidden from iterative selection after it is frozen.
- Protocol commits must precede results commits; invalid and negative results remain append-only evidence.
- The old Grid5 result is invalid because of a bookkeeping exception, not a valid negative result about 5x5 discretization.
- A wall-clock continuity loop has user consent in the execution phase, but it must preserve the pause sentinel, owned-process, write-boundary and no-duplication rules.

## Open Questions

- Which stage-resolved proxy best predicts eventual task success under the existing reward pipeline?
- Does overflow come from useful exploration beyond initial bounds or uncontrolled drift toward edge cells?
- Can control-success modes be retained with a fixed 176-evaluation budget while still exploring new behaviors?
- Is cross-chunk discontinuity a cause of timeout, or merely correlated with harder episodes?
- Which development/validation seeds provide representative but leakage-safe promotion evidence?
- Do high-reward archive cells produce better offspring than quality-blind or inverse-visitation slots on saved traces, and what is the smallest fixed-budget reserve justified by that counterfactual?

## Optimization Trajectory

`run_000_baseline_replay` is complete; `run_001_allocation_ecology_diagnostic` ended invalid after two infrastructure attempts; `run_002_partition_diagnostic` passed all gates; and `run_010` algorithm iteration 1 is implemented at `930cdb5` with 781 regression tests passing. No development episode, GPU job, or formal evaluation has run, so success remains historical 2/10 and target gap remains 3. The next action is the immutable offline preflight, followed by frozen mechanism preflight/Dev-A gates only if it passes.
