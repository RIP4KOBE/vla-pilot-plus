# Research Findings

## Research Question

Can a mechanism-grounded, compute-accounted successor to the audited EDS-QD baseline reach at least 5/10 valid successes on frozen LIBERO-PRO `libero_object_swap` without evaluation leakage or safety regression?

## Current Understanding

The historical QD implementation is mechanically coherent in its supported 3x3/4x4 paths: it preserves one reward elite per target-relative endpoint-XY cell, allocates exactly 16 offspring slots, keeps 176 evaluations per full chunk, and passes archive/accounting/replay hard gates. That correctness did not translate into mechanism or task benefit. The valid QD treatments produced median normalized coverage of 1.0 while their offspring overflow P95 was 0.938–1.0, paired coverage gain was exactly 0, replacement-active ratios stayed below 0.50, and best-reward deltas were approximately zero. This is evidence that the old coverage variable is saturated and not evidence that useful behavioral diversity was preserved.

The task evidence is worse than the control: control succeeded on tasks 3, 8, and 9 (3/10); uniform primary succeeded on none; sparse primary retained task 8, gained task 5, and lost tasks 3 and 9 (2/10). Contact sheets support genuine behavioral divergence between profiles, but the historical automatic label `timeout without completion` is intentionally non-causal. It does not by itself identify target acquisition, grasp, transport, placement, or Stage Recognition as the mechanism of failure.

There is also a geometry warning. The control's selected trajectory-length median was 0.093 m and chunk-boundary jump P95 was 2.983. Valid QD variants generally increased trajectory length to roughly 0.103–0.139 m and jump P95 to roughly 3.35–4.90. This motivates continuity and execution-stability hypotheses, but causal attribution requires paired, stage-resolved probes.

The historical Grid5 result is invalid algorithm evidence. Its episodes hit `IndexError: tuple index out of range` when final archive selection indexed stale particle-source bookkeeping. Current HEAD contains a QD-aware source bookkeeping branch, but the old Grid5 outcomes remain invalid and must not be used to rank grid resolution. Future tests must explicitly cover archives with more occupied cells than population-source tuples before any online promotion.

## Key Results

- Historical contemporaneous control: 3/10 on frozen tasks/seeds.
- Historical uniform QD primary: 0/10; valid but failed task and mechanism-claim gates.
- Historical sparse QD primary: 2/10; gained task 5, retained task 8, lost tasks 3 and 9.
- Historical valid QD profiles: coverage median 1.0 with overflow P95 0.938–1.0 and paired coverage gain 0.
- All QD candidates: no adoption; decision manifest and report checksums verify.
- Planning baseline health check: 56 QD archive/runner/audit tests pass on base commit.

## Patterns and Insights

1. Occupancy saturation plus edge clamping makes coverage a weak promotion signal under the existing descriptor and frozen initial bounds.
2. Reward preservation alone is insufficient: similar best-reward deltas coexist with materially different environment outcomes.
3. Exploration can discover a new success (task 5) but currently fails to retain known control successes, indicating an exploit/retain problem rather than a simple lack-of-diversity problem.
4. The QD policies tend to generate longer or more discontinuous selected motion, which may consume the 720-step budget without completing placement.
5. A ten-task formal suite is too small to serve simultaneously as an iterative tuning set and an unbiased final acceptance set; development and validation seeds must be isolated before execution.

## Lessons and Constraints

- Never optimize or promote on normalized cell coverage alone.
- Do not treat edge-clamped cells as distinct useful modes without meter-scale and stage-progress evidence.
- Do not treat `timeout without completion` as a causal failure category.
- Preserve contemporaneous control and control-success retention in every promoted comparison.
- Keep the official task/seed mapping hidden from iterative selection after it is frozen.
- Protocol commits must precede results commits; invalid and negative results remain append-only evidence.
- The old Grid5 result is invalid because of a bookkeeping exception, not a valid negative result about 5x5 discretization.
- Do not enable a wall-clock continuity loop during the current planning-only phase.

## Open Questions

- Which stage-resolved proxy best predicts eventual task success under the existing reward pipeline?
- Does overflow come from useful exploration beyond initial bounds or uncontrolled drift toward edge cells?
- Can control-success modes be retained with a fixed 176-evaluation budget while still exploring new behaviors?
- Is cross-chunk discontinuity a cause of timeout, or merely correlated with harder episodes?
- Which development/validation seeds provide representative but leakage-safe promotion evidence?

## Optimization Trajectory

No new-research experiment has run. Historical results are references, not entries in the new autoresearch trajectory. The trajectory starts only after an experiment protocol has been committed in the execution phase.

