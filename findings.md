# Research Findings

## Research Question

Can a mechanism-grounded, compute-accounted successor to the audited EDS-QD baseline reach at least 5/10 valid successes on frozen LIBERO-PRO `libero_object_swap` without evaluation leakage or safety regression?

## Current Understanding

The historical QD implementation is mechanically coherent in its supported 3x3/4x4 paths: it preserves one reward elite per target-relative endpoint-XY cell, allocates exactly 16 offspring slots, keeps 176 evaluations per full chunk, and passes archive/accounting/replay hard gates. That correctness did not translate into mechanism or task benefit. The valid QD treatments produced median normalized coverage of 1.0 while their offspring overflow P95 was 0.938–1.0, paired coverage gain was exactly 0, replacement-active ratios stayed below 0.50, and best-reward deltas were approximately zero. This is evidence that the old coverage variable is saturated and not evidence that useful behavioral diversity was preserved.

The task evidence is worse than the control: control succeeded on tasks 3, 8, and 9 (3/10); uniform primary succeeded on none; sparse primary retained task 8, gained task 5, and lost tasks 3 and 9 (2/10). Contact sheets support genuine behavioral divergence between profiles, but the historical automatic label `timeout without completion` is intentionally non-causal. It does not by itself identify target acquisition, grasp, transport, placement, or Stage Recognition as the mechanism of failure.

There is also a geometry warning. The control's selected trajectory-length median was 0.093 m and chunk-boundary jump P95 was 2.983. Valid QD variants generally increased trajectory length to roughly 0.103–0.139 m and jump P95 to roughly 3.35–4.90. This motivates continuity and execution-stability hypotheses, but causal attribution requires paired, stage-resolved probes.

The historical Grid5 result is invalid algorithm evidence. Its episodes hit `IndexError: tuple index out of range` when final archive selection indexed stale particle-source bookkeeping. Current HEAD contains a QD-aware source bookkeeping branch, but the old Grid5 outcomes remain invalid and must not be used to rank grid resolution. Future tests must explicitly cover archives with more occupied cells than population-source tuples before any online promotion.

Post-v3 read-only replay identifies a new H5 bottleneck that is distinct from the failed global Direction-RBF intervention. Across 24 active-QD traces, 264 candidate streams, and 4,224 candidates, 65.10% of candidates collide with another candidate in the same 4x4 endpoint-XY cell. Among 1,019 colliding cells, the reward top-two trajectories still have median normalized direction/shape distances 0.3617/0.2501 while their median reward gap is only 0.01270. Capacity one therefore removes reward-near trajectory modes before they can become descendants. The v4 candidate tests capacity-two quality plurality locally inside each XY cell, retains v3's single global-quality parent anchor, and keeps final global-reward selection and 176/176/11 compute unchanged. This is a behavior-retention hypothesis, not yet success evidence.

Run040 validated the capacity-one replay (zero mismatch) and the aliasing/allocation observations, but rejected naive overall top-two retention before online evaluation. The counterfactual activated secondary lineages in 1,001/3,600 sparse slots and retained XY-cell allocation coverage, yet causal rebins produced 17 events where secondary history displaced a comparator quality lineage. Thus any next plurality mechanism must separate roles: a protected quality lane must reproduce capacity-one update/rebin exactly, while a secondary lane may preserve distinct behavior but may never evict or redefine the protected lane. This is a direct narrowing from a failed gate, not a threshold relaxation.

Run041 confirms that role separation resolves the exact Run040 failure without changing cell ecology or compute. Across all 264 streams the protected quality lane exactly matches capacity one, while a non-evicting secondary exists in 2,613/3,471 quality-cell snapshots and receives 28.89% of sparse parent slots. All 240 cell allocations, anchors and final quality selections remain comparator-identical. This justifies implementation testing, but supplies no environment-success evidence yet.

Run042/043 close the implementation and integrated-CPU risk. The default-off
implementation passed 408 applicable tests; the frozen Run043 harness then
passed ten mechanism gates and 424 full applicable regressions. In each protected
fixture, four secondary cells remained active at every iteration and supplied 72
of 150 sparse parents, while the expanding protected run and mode-none comparator
were identical on every authoritative quality, allocation and final-execution
field. Thus protected within-cell behavior can enter offspring generation without
changing quality elitism or the 176/176/11 compute contract. This remains zero-
episode mechanism evidence; only the frozen paired online mechanism split can
show whether it shrinks the task-success gap.

Run044 has no admissible online result yet. The first execution revealed that
LIBERO sorts an unsorted task filter before applying the supplied seed schedule,
crossing the two frozen task/seed pairs. IDs 91–94 and all partial outputs are
therefore infrastructure evidence only. Protocol-first repair now sorts the
paired seed schedule by task ID and passes runner regressions, but exact paired
recovery needs four reservations while the frozen global plan retained only
three. No H5-v5 success, failure or target-gap inference is permitted from this
incident.

The `run_000_baseline_replay` machine replay adds a stronger ecology boundary. Across 4,705 QD chunks from 27 original and budget-study metrics files, every chunk reported zero direct elite carryover and archive-only parent selection; the accumulated parent counts were 3,281,360 archive offspring and zero direct elites. The configured `num_elites` is a no-op in the non-CEM QD branch. Thus the current QD process has cell-local reward elitism but no explicit population budget reserved for globally strong lineages.

`run_001_allocation_ecology_diagnostic` is invalid and supplies no reward-inheritance conclusion. The audit exposed three telemetry semantics that must not be conflated: parent ranks apply to population occurrences rather than unique cells; parent slot maps are pre-update while same-index coverage is post-update; and sparse-priority can assign zero slots to occupied cells. After two infrastructure attempts the preregistered stop rule ended repair. H4 remains unresolved and is not authorized for online evaluation in this cycle.

Outer-loop cycle 1 pivots to H1 partition diagnostics. This choice is evidence-ranked, not novelty-ranked: H1 has valid and deterministic JSONL coverage/overflow telemetry, whereas H4's required inheritance evidence is invalid and H3's generic smoothing intervention has negative historical task evidence. Only one partition counterfactual is allowed before an online go/no-go, preventing a return to grid/bounds sweeps.

`run_002_partition_diagnostic` supports that single H1 counterfactual. Across 4,567 exact-replayed 4x4 chunks, causal monotonic bounds expansion reduced within-cell endpoint SSE by median 30.1% (30.9% with equal profile weight), with all target-linked historical task strata 3/5/8/9 above 27%. Median occupied-mode retention was 93.75%, archive endpoint spread increased 2.01x, and every global reward-best fingerprint was retained. The raw initial-bound overflow P95 remained explicitly 0.875; the zero candidate overflow is the post-envelope representability metric, not a claim that exploration stopped. This is strong offline authorization for one QD-1 test, not evidence of task success.

`run_010_causal_envelope_candidate` completed validation and failed the primary target. The unchanged candidate scored 1/10 (task 0) versus control 0/10, far below the frozen 5/10 gate. Its Dev-A/Dev-B gains on tasks 9/5/8 did not replicate. This was not a mechanism-plumbing failure: resolution support held on 10/10 validation tasks, post-envelope overflow P95 was 0, archive spread did not collapse, latency was 1.092x the sparse reference, and all safety/accounting/credential gates passed. H1 is therefore supported as a partition-resolution mechanism but refuted as a sufficient success mechanism. Protocol v11 forbids formal and outcome-driven reuse of this validation set.

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
- `run_010` Stage-A: immutable offline v2 PASS (`3097afad…f7a9`); 781 tests; full checkpoint and 20 LIBERO input files fingerprinted; 176/11 compute; zero post-envelope overflow; 10/10 visit/global-best invariants; finite synthetic resolution median 1.0. This remains mechanism evidence only.
- `run_010` mechanism preflight: after append-only recovery of two pre-episode infrastructure incidents, exact frozen attempts 13–18 completed; aggregate v2 audit PASS with 3/3 valid jobs and zero hard failures (`c7e93f92…08ab`). Control/sparse/candidate each scored 0/2 in the two-chunk plumbing horizon; this unlocks Dev-A only.
- `run_010` Dev-A: immutable v2 audit PASS (`9c6d3ece…9fa9`); candidate 1/4 vs control 0/4, gained task 9, lost none; 4/4 tasks support the partition mechanism and all safety/accounting/latency gates pass. Dev-B confirmation is required.
- `run_010` Dev-B: immutable audit PASS (`7a73b3ae…f64f`); candidate 2/4 vs control 0/4, gained tasks 5/8, lost none; pooled Dev-A+Dev-B gain +3; 4/4 mechanism support and all hard gates pass. A new validation protocol is authorized.
- `run_010` validation: immutable audit valid/target-FAIL (`3f72d025…0774`); candidate 1/10 (task 0) vs control 0/10; gained task 0, lost none; 10/10 mechanism support, post-overflow 0, latency 1.0922x, clean safety/accounting/credential, cumulative 2.9348 GPU-hours. Formal is forbidden.
- `run_043`: 10/10 CPU mechanism gates, protected secondary activation 72/150 sparse parents in both candidate fixtures, exact expanding-fixture quality identity versus mode-none, 176/176/11, 424 regressions, dual-artifact SHA `32a46d78…5f3a`, and zero online/GPU use.

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
10. Online transaction ordering is part of validity: the run_010 dispatcher reserved cells before the base runner repeated its Poe health check. The resulting IDs 1–6 are auditable pre-episode infrastructure aborts, not policy outcomes; an exact-cell recovery must health-check before creating replacement reservations.
11. Repeated health-check retries are not a productive inner loop when the service returns deterministic authentication failure. Runtime credential repair is required before any target-linked EDS+QD conclusion can be obtained.
12. Result audits must bind to the same frozen scientific revision as job manifests; documentation-only commits alter code-state/config binding and can create false invalidity without changing the executed policy.
13. Causal-envelope QD produced a paired full-episode gain on task 9 under a new seed while control failed all four Dev-A tasks; this is target-linked evidence, but a single split success is not sufficient to predict 5/10 formal acceptance.
14. Independent Dev-B replicated and strengthened the task advantage on different seeds (2/4 vs 0/4), with different gained tasks 5/8 and no losses. The cross-split direction now supports full ten-task validation without changing the candidate.
15. Perfectly activating the intended QD partition mechanism does not imply success transfer: all ten validation tasks showed resolution improvement, yet only task 0 succeeded and none of the three development gains replicated. Endpoint partition saturation was real but was not the dominant completion bottleneck.
16. The next evidence-supported QD question is quality rather than partition size: reward-only cell elitism and archive-global final selection remain unchanged after H1. This is a redesign hypothesis, not an authorized inference from validation task identities.
17. A threshold-free QD-quality guard can remove fingerprint-driven selection only where quality is exactly absent while preserving nondegenerate QD bit-for-bit and retaining the 176/11 search budget. This is verified offline but remains unproven as a success-rate intervention until paired online gates pass.
18. Integrated synthetic execution confirms the guard is a true per-chunk switch rather than persistent mode state: exact-zero output is identical to the existing EDS control including RNG, while a following nondegenerate chunk reactivates the unchanged QD archive. This closes offline integration risk but still supplies no task-success estimate.
19. A run-local ledger cannot reuse the legacy helper when scientific IDs are globally offset: its hard-coded 1..N validation fails after valid IDs 55–60 are reserved. This is a pre-dispatch accounting defect, not H2 evidence; recovery must preserve and void the original reservations append-only before using dedicated global-offset semantics.
20. Retrospective exact-zero reward prevalence did not transfer prospectively: all 74 candidate chunks across tasks 2/3/9 had strictly positive reward spread, so the exact-equality guard never activated. Meanwhile unchanged active QD lost the contemporaneous control success on task 9 (0/3 vs 1/3). Exact equality is therefore not a viable online routing predicate for this candidate; tolerance tuning would be a new threshold search, not a repair.
21. Role separation is sufficient to retain same-cell plurality without changing
    the capacity-one quality path: protected secondary parents can occupy nearly
    half of sparse slots in an integrated loop while quality bounds, visits,
    allocation counts and final execution remain comparator-identical. Whether
    those descendants improve manipulation success is now the sole open gate.

## Lessons and Constraints

- Never optimize or promote on normalized cell coverage alone.
- Do not treat edge-clamped cells as distinct useful modes without meter-scale and stage-progress evidence.
- Do not treat `timeout without completion` as a causal failure category.
- Preserve contemporaneous control and control-success retention in every promoted comparison.
- Keep the official task/seed mapping hidden from iterative selection after it is frozen.
- Protocol commits must precede results commits; invalid and negative results remain append-only evidence.
- The old Grid5 result is invalid because of a bookkeeping exception, not a valid negative result about 5x5 discretization.
- A wall-clock continuity loop has user consent in the execution phase, but it must preserve the pause sentinel, owned-process, write-boundary and no-duplication rules.
- Once a candidate has exposed the fixed validation set and failed the target, it cannot be modified and re-evaluated on that set. Further algorithm work requires a versioned redesign with new holdout seeds; it is not a routine adjacent iteration.

## Open Questions

- Which stage-resolved proxy best predicts eventual task success under the existing reward pipeline?
- Does overflow come from useful exploration beyond initial bounds or uncontrolled drift toward edge cells?
- Can control-success modes be retained with a fixed 176-evaluation budget while still exploring new behaviors?
- Is cross-chunk discontinuity a cause of timeout, or merely correlated with harder episodes?
- Which development/validation seeds provide representative but leakage-safe promotion evidence?
- Do high-reward archive cells produce better offspring than quality-blind or inverse-visitation slots on saved traces, and what is the smallest fixed-budget reserve justified by that counterfactual?
- Under a new leakage-safe design, can observation-derived progress calibrate QD replacement/final selection without privileged evaluator input or extra model calls?

## Optimization Trajectory

`run_000_baseline_replay` ruled out direct compute scaling; `run_001_allocation_ecology_diagnostic` ended invalid; `run_002_partition_diagnostic` supported H1 offline; and `run_010` algorithm iteration 1 passed mechanism/Dev-A/Dev-B but failed validation at 1/10 versus the 5/10 target. The historical formal best remains 2/10 and formal target gap remains 3 because formal was correctly not run; the candidate's observed validation gap is 4. The fixed validation set is now exposed, so outer-loop cycle 2 must conclude this frozen cycle or request a versioned redesign with new holdout seeds.

Outer-loop cycle 2 selected `CONCLUDE_NO_ADOPTION_WITHIN_FROZEN_CYCLE_REQUEST_VERSIONED_REDESIGN`. Execution is disabled; the only proposed future direction is H2 QD quality/replacement/final selection under a new design and holdout, not continued exploration on this cycle.

## Versioned H2 continuation — 2026-08-12

The user explicitly authorized the required redesign, so execution resumed with new leakage-safe Dev-A, Dev-B and validation seeds. The revealed v1 validation remains historical evidence only.

A more concrete H2 failure boundary is now observed. The frozen cached Stage-2 guidance source returns the exact scalar zero and says placement should be handled by the policy. Nevertheless, current QD still maintains an archive: cell-local equal-quality competition and global execution selection reduce to lexicographic action fingerprints. A task-agnostic hash therefore controls actions precisely when reward contains no preference. This is a structural QD quality/selection defect, not evidence that changing Stage recognition is needed.

The v2 cycle will first quantify this defect with a zero-episode replay. Only if exact-degenerate chunks are prevalent, the tie is reproducibly fingerprint-dependent, nondegenerate QD remains unchanged, and the existing control path preserves the 176/11 compute contract may one candidate be implemented: per-chunk fallback from degenerate QD ecology to the existing EDS control selection. No endpoint heuristic, threshold sweep, Stage modification or second candidate is authorized.

`run_020` passed all of those gates. It found 473 exact-zero QD chunks across all ten tasks among 7,080 valid raw rows; 468 were in failed episodes and 5 in successes, so prevalence is strong but not itself a causal task claim. Forty-four owned QD traces exactly reproduced current selection and showed that equalizing quality makes the executed action depend entirely on the direction of the fingerprint tie. All 44 nondegenerate selections were preserved by the observer replay. The existing non-QD branch supports a threshold-free per-chunk fallback at the same projected 176 evaluations and 11 score calls. This authorizes one implementation protocol, not an online success claim.

`run_021` implemented that sole candidate after a protocol-first commit. Offline fixed-input tests verify exact-only triggering, no QD archive construction on degenerate chunks, 176/11 complete search accounting, default legacy preservation, and bit-identical nondegenerate QD selection/archive behavior. Seven hundred non-overlapping regression tests passed. This closes implementation risk but does not change the 2/10 historical best or target gap; a separately frozen offline mechanism preflight is the only authorized next step.

`run_022` then passed an integrated eight-case double replay. Exact-zero candidate execution is identical to EDS control, near-equal (`1e-12`) and nondegenerate candidate execution are identical to legacy causal-envelope QD, complete accounting is preserved, and a same-instance second chunk proves QD reactivation. All 11 hard gates passed and two immutable artifacts are byte-identical. This authorizes only a protocol for six online mechanism episodes, not Dev-A or a success claim.

`run_023` credential health subsequently passed, but its first reservation transaction exposed a runner-only global-offset ledger defect before dispatch. IDs 55–60 are preserved as reserved-not-dispatched infrastructure records; no task result exists. Protocol v3 authorizes a six-slot exact-cell recovery only after an append-only void event, dedicated ledger repair, tests, and immutable manifest v3.

That exact-cell recovery completed validly. The candidate never triggered fallback in 74 chunks and scored 0/3, while control scored 1/3 on task 9. All other accounting, safety, latency, artifact, and credential gates passed. H2's exact-degenerate fallback candidate is rejected before Dev-A; the v2 cycle has no second-candidate authorization.

## V2 Cycle Conclusion

The v2 cycle concludes with no adopted EDS-QD successor. Run023 is a valid negative mechanism result, not an infrastructure ambiguity: the candidate ran the unchanged active-QD path in all 74 chunks, lost the only contemporaneous control success, and failed the preregistered fallback-observation gate. The historical formal best remains 2/10, so the target gap remains 3; formal evaluation was correctly not run.

The v3 global-quality anchor closes the specific allocation defect and produces the first positive online transfer for H4. In valid Run033 paired evidence, control was 0/3 and the unchanged one-anchor candidate was 1/3, gaining task 9 with no lost control success. All 110 candidate records used the frozen 1+15 allocation and 176/176/11 compute; 1,100 activations produced 751 real rescues, with clean safety/accounting/final-selection gates and latency ratio 1.060499. This supports promotion to the frozen six-task Dev-A, not adoption or formal evaluation.

Anchor rescue frequency is necessary mechanism evidence but not a task-success surrogate. Candidate tasks 3 and 8 accumulated 114 and 624 rescues yet both timed out; only task 9 succeeded with 13 rescues. The next decision must therefore be driven by Dev-A success/retention (`>=3/6`, at least +1 over control, lost tasks empty), not by increasing anchor count, maximizing rescue rate, or exploring thresholds.

Run033 also exposed an infrastructure lesson without changing science: assigning `v3.base.P2_TORCH_HUB_SEED = v2.base.P2_TORCH_HUB_SEED` is self-referential because both aliases name the same imported module, leaving isolated caches unseeded. Exact source-path binding plus append-only recovery preserved IDs 67–72 as pre-episode failures and ran science only in IDs 73–78. The incident cost 0.059858 GPU-hours, consumed six recovery slots, and yielded no admissible task result.

Across H1 and H2, geometric archive resolution and exact-zero reward routing were real, measurable QD issues, but neither produced evidence sufficient to approach `>=5/10`. The remaining evidence-supported bottleneck is alignment between QD quality/final selection and observable task progress while retaining control-success behavior. That statement is an outer-loop hypothesis, not an authorized implementation or success claim.

The immutable v2 decision is `CONCLUDE_NO_ADOPTION_WITHIN_V2_CYCLE_REQUEST_VERSIONED_REDESIGN`. Any successor must use a versioned design, fresh leakage-safe holdout seeds, an explicit budget, and explicit approval. Reusing Run023 outcomes for a tolerance sweep, adjacent candidate, Dev, validation, or formal evaluation is prohibited.

## Versioned H4-v3 continuation — 2026-08-12

The user explicitly approved a new versioned cycle. The successor does not relax H2's failed exact-equality predicate. A read-only allocation audit instead identified a direct exploit/retain defect inside QD: among 666 comparable Run023 transitions, the archive cell with the previous iteration's highest reward received zero offspring slots 450 times (67.6%). The omission rates on tasks 2/3/9 were 51.3%/76.9%/25.9%. This explains how cell-local quality elitism can coexist with loss of the best lineage under inverse-visitation parent allocation.

V3 freezes one candidate: reserve exactly one of 16 QD parent slots for the current archive global-best cell and allocate the remaining 15 with unchanged sparse priority. All 16 still undergo the original renoise/rollout, so compute remains 176 evaluations and 11 score calls; this is lineage retention rather than direct action carryover. The proposal must first pass a checksum-bound zero-episode reconstruction proving baseline identity at anchor=0, complete omission removal at anchor=1, and at least 85% allocation-coverage retention. It remains a hypothesis until task-linked gates pass.

`run_030` passed that reconstruction. Across five exact owned files, the current production allocator reproduced all 3,205 eligible saved transitions. The prior global-best cell had zero descendants in 2,151 transitions (67.1%), with every task above the preregistered omission gate. The 1+15 counterfactual gave the best cell at least one descendant in all transitions while median occupied-cell coverage retention remained 1.0. This establishes a pervasive allocation-retention defect and a compute-neutral repair shape; it does not establish reward-to-success alignment or task improvement.

`run_031` implemented that repair behind default-off `qd_global_quality_anchor_count`. Tests establish exact legacy allocation at zero, deterministic global-best selection and exact same-seed 1+15 composition at one, including both omission rescue and non-deduplicated overlap. The integrated mock retained ten 16-parent rollout batches, archive-global final selection, and 176/176/11 accounting. This clears implementation risk only; it is not evidence of LIBERO success and requires a separate CPU mechanism artifact before online evaluation.

`run_032` supplied that immutable CPU mechanism evidence. A dense global-best fixture forced ten consecutive sparse omissions and the anchor rescued all ten; a balanced fixture kept positive sparse best-cell allocation and added the dedicated slot without deduplication. Both candidate fixtures and the zero-anchor comparator preserved ten 16-parent rollout batches, 176/176/11, final archive-global selection, safety/accounting, and deterministic replay. Online reward-to-success value remains untested.

`run_034` refutes cross-task transfer of the single global-quality-anchor candidate at the frozen Dev-A gate. Control and candidate both scored `0/6` on tasks `[0,1,2,4,6,7]`; every episode timed out without completion. The candidate nevertheless activated the anchor 1,060 times and rescued 425 sparse omissions across 106 valid records, with exact 176/176/11 accounting, clean safety and a 1.052894 latency ratio. Thus the intervention reliably changes QD lineage allocation but does not supply a general task-completion advantage. Its Run033 task-9 gain was isolated and cannot justify validation, formal evaluation, anchor-count tuning, or another v3 candidate.

The v3 task-level evidence is now internally consistent with the primary objective rule: one positive `0/3 -> 1/3` mechanism result was promoted once, then the unseen six-task gate returned `0/6 -> 0/6`. The target remains unachieved; historical formal best is still `2/10`, target gap 3, and formal episodes remain zero. V3 must conclude no adoption under its frozen no-progress rule.

## V3 Cycle Conclusion

The immutable v3 decision is `CONCLUDE_NO_ADOPTION_WITHIN_V3_CYCLE_TARGET_NOT_MET`. One dedicated global-quality parent repairs a pervasive sparse-allocation lineage omission without increasing compute, but Dev-A shows that lineage retention alone is not sufficient for task completion. V3 ends after 66 effective online episodes, 90 reservations and 5.447063 GPU-hours, with no v3 validation or formal episode.

No same-cycle candidate remains. Any future design must treat Run034 as revealed historical evidence and cannot tune on its tasks/seeds. The remaining evidence-supported diagnosis is that archive reward/final selection is weakly aligned with observable manipulation progress; pursuing it requires a new versioned, QD-first EDS+QD design and explicit approval rather than continuation of v3.

## V5 Protected-Quality Lane Conclusion

Run044 exact recovery is a valid negative result. Both control and protected
secondary candidate scored `0/2` on the exact task 5/7 cells, with all four
outcomes timing out; task delta, gained tasks and lost tasks are all zero. The
candidate's secondary lane was highly active (1,685 parents; 407/410 QD
iterations positive), but three real task-5 iterations had no secondary parent,
which fails the frozen per-iteration activation gate. Thus role separation
solves quality eviction and usually provides alternate lineages, but does not
guarantee online alternate availability or translate to task completion.
Aggregate secondary activity must not be treated as success evidence.

H5-v5 is the frozen final evidence-backed candidate without prior task gain, and
Run044 produced no task gain. Its valid mechanism FAIL therefore forbids Dev-A,
validation, formal, a gate relaxation, an outcome-driven rerun and a sixth
candidate. Cumulative accounting is 70 effective online episodes, 98/144
reservations and 6.946832/48 GPU-hours; historical formal best/gap remain 2/10
and 3. The next step is an immutable outer-loop no-adoption conclusion, not more
mechanism exploration.

The outer-loop conclusion is now immutable. Run045 decision manifest SHA
`112cc6b19b9ab1970e392f04385ff572a8b8712e362c69c1b27fdd2f5a427d99`
records `CONCLUDE_NO_ADOPTION_WITHIN_GLOBAL_BUDGET_TARGET_NOT_MET`; final report
SHA is `6cdaf99749a22b984753ca4b300098d00fb94e6a4b66de5077016aaf4fc7a0fb`.
The target was not reached, and the study ends with the historical control as
the recommended operational baseline.
