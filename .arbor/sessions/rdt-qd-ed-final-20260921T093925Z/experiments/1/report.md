# Historical QD/EDS diagnosis — node 1

Run: `rdt-qd-ed-final-20260921T093925Z`. Scope: bounded CPU-only review and saved-trace replay; **zero new episodes, GPU/model/environment calls, source algorithm edits, or success measurements**. The protected old untracked design was not read, copied, modified, or staged. Old artifacts were read-only.

## Decision and evidence boundary

The historical outcome remains **target not met / no adoption**. Q0 sparse `2/10` is the selected research starting point, tied with expand20; contemporaneous historical P2 is `3/10`. Sparse gained task 5, retained 8, and lost 3/9 relative to P2. Expand20 succeeded on 5/7 and lost all three P2 successes. These are exposed fixed acceptance cells, not new Dev/Validation evidence.

A new bounded action-branch hypothesis is defensible for **diagnostic testing**, because exact trace replay now establishes that capacity-one XY selection eliminates candidates with different executable gripper sequences. It does **not** establish that these discarded branches would grasp correctly or complete a task. Existing reward prefers every retained branch in the observed discordant eliminations; this is not an exact-tie/fingerprint problem. Cache target identity must be repaired and the baseline re-established separately before attributing any new benefit to QD.

## Historical facts and what they do not establish

| Evidence | Supported observation | Unknown / excluded inference |
|---|---|---|
| [Original QD report](/home/hynx/VLA-Pilot++/.worktrees/exp/eds-quality-diversity/docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-06-eds-quality-diversity-report.md) | Q0 sparse `{5,8}` = 2/10; Q1 expand20 `{5,7}` = 2/10; P2 `{3,8,9}` = 3/10. Q0 coverage median 1.0 and overflow P95 0.938 did not meet task/adoption gates. | Q0 is not proven better than Q1. Cross-round P2 4/10 cannot be pooled with this 3/10. |
| [Run010](/home/hynx/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/experiments/run_010_causal_envelope_candidate/analysis.md) | H1 actually entered validation: candidate 1/10, control 0/10, gained task 0. Post-envelope overflow P95 0 and partition-resolution improvement 0.486–0.628 per task. | Better endpoint partitioning was insufficient. The claim that no candidate ever entered validation is incorrect. Timeout is not a grasp/target diagnosis. |
| [Run020](/home/hynx/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/experiments/run_020_quality_selection_calibration/analysis.md) | 473 unique exact-zero archive-reward chunks across tasks 0–9; 468 fail, 5 success. Equal reward chooses task-agnostic fingerprint. Frozen Stage-2 source returns exact zero. | Exact zero does not imply inevitable failure. Association with failed episodes is not causation. |
| [Run023](/home/hynx/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/experiments/run_023_reward_degenerate_online_mechanism/analysis.md) | H2 candidate 0/3 vs P2 1/3, lost task 9; fallback activated 0/74 chunks. Each reward spread was positive. | Online applicability of that routing predicate failed; fallback's effect **after actual activation** was not tested. No basis for adjacent tolerance sweep. |
| [Run034](/home/hynx/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/experiments/run_034_global_quality_anchor_dev_a/analysis.md) | H4 Dev 0/6 vs 0/6, with 1,060 activations and 425 rescued quality lineages. | Preserving reward-best parent lineage did not establish transferable task value. |
| [Run040](/home/hynx/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/experiments/run_040_within_cell_aliasing_diagnostic/analysis.md) | 2,750/4,224 candidates collided in XY cells; trajectory shape/direction differed. Naive top2 failed 17 protected-quality retention checks. | Generic capacity-two top2 is rejected; not all manipulation-aware behavior distinctions are refuted. |
| [Run044](/home/hynx/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/experiments/run_044_protected_quality_lane_online_mechanism/analysis.md) | H5 protected lane candidate/control 0/2; 1,685 secondary parents; 407/410 positive-secondary iterations. Correct executed mapping task5/666847 and task7/87603. | Three zero-secondary iterations violate the old gate, but fixing just those three has no task-linked evidence. Large activation counts do not establish progress. |
| [Run045 manifest](/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_045_global_no_adoption_conclusion/manifests/global_decision_manifest.json) | 70 effective online attempts, 98/144 reservations, 6.9468320556/48 GPU-hours, 0 new formal episodes, target_achieved=false. | The old cycle ended; it neither proves all QD/ED mechanisms impossible nor supplies successful adoption. |

The [historical ledger](/home/hynx/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/docs/03_evidence/eds_qd_autoresearch/iteration-ledger.md) header remains stale (`run_010 recovery ready`, zero episodes). Final per-run artifacts and Run045 govern outcome/accounting. The ledger's earlier continuity summary reports cleaner motion but success 3→2→0; generic smoothing is not promoted here. The existing 257-job RBF and 18-configuration budget scans constrain this study against repeating broad parameter/compute sweeps.

## Proposal, selection, closed loop

**Proposal.** The Q0 saved trace set covers the first two saved chunks of each of 10 tasks: 20 traces, 220 initial/offspring batches, 3,520 candidate occurrences. These are historical samples with substantial early-chunk bias. They provide actual proposed actions and proxy trajectories, not simulator counterfactual outcomes. Whether any unexecuted proposal would grasp/transport/place successfully is **Unknown**.

**Selection.** The CPU diagnostic reproduces every recorded per-iteration Q0 cell elite reward and all 20 final selected fingerprints. This guards against the temporal-alignment/schema problems of the earlier invalid allocation analysis. Core behavior is source-defined: [descriptor](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/core/qd_ed.py:45) uses final EEF XY; [cell winner](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/core/qd_ed.py:406) uses reward then fingerprint; [final choice](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/core/rdt_policy_steer.py:6317) uses archive global reward-best. The deployed [decoder](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/core/rdt_libero_action_converter.py:31) maps negative grip values to -1 and zero/positive to +1.

| New deterministic historical diagnostic | Value |
|---|---:|
| Same-batch endpoint-XY collision cells | 987 |
| Collision cells containing different executed 8-step gripper sign sequences | 43 / 987 |
| Collision cells containing different final gripper sign | 21 / 987 |
| Actual discordant archive elimination events | 82 |
| New candidate rejected / incumbent displaced | 69 / 13 |
| Equal-reward discordant eliminations | 0 |
| Discordant eliminations with different positive-command duty | 82 / 82 |
| Discordant eliminations separated by four fixed duty bins | 73 / 82 (89.0%) |
| Final selections with a different-gripper-sequence alternative anywhere in the saved proposal pool | 8 / 20 |
| Selected reward minus best such alternative | 0.014511–0.096436; positive in all 8 |
| Within-collision scored-prefix Z span median / P95 | 0.108398 / 0.285156 m |

The 82 elimination events are **occurrences**, not distinct task failures. By task 0–9 they are `[0,8,6,4,8,2,22,0,0,32]`; task 9 (a historical Q0 loss vs P2) has 32. No task-ID branching follows from this stratification. This is concrete branch loss under correct reward-based replacement, not proof of lost success. The raw proxy excludes gripper/orientation from reward and XY partition excludes vertical motion; proposals can therefore share a cell despite different executable manipulation actions. The relatively large alternative reward deficits are a reason to test lineage utility cautiously, rather than claim a trivial tie fix will help.

**Execution boundary.** [Trajectory projection](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/core/env_adapters/libero_adapter.py:1620) returns start+t1…t8 using kinematic cumulative deltas. QD uses t8; [EDS scoring slice](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/core/rdt_policy_steer.py:1649) uses t1…t7; decoder executes all 8. Stored metadata confirms reward trajectory shape `[16,7,3]` and execution horizon 8. Comparing stored t8 XY descriptor with saved t7 XY gives 342/3,520 different 4x4 cells, 17/220 different nearest-target-XY candidate identities, and endpoint XY gap median/P95 0.007837/0.013283 m. This descriptive result uses BF16 trajectory samples and float32 descriptors, so boundary changes are not a precise physical-error estimate. It supersedes the exploratory reconstructed-t8/3D count of 18/220. Provider semantics remain frozen; no change has been made.

**Closed loop.** `target_distance_before/after` must not be read as before/after simulator progress: [_eds_target_distance](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/core/rdt_policy_steer.py:4039) measures candidate proxy endpoints. Future observed object motion, stable grasp, transport, placement and their relation to selected actions remain **Unknown** in this replay. Stage is a noisy existing observation, not an evaluator oracle. For the Run044 candidate, task7 has only 3 EDS records through step16, but 5 Stage events through step712, all `guidance_after=false`. Task5 has 38 EDS records through step712 and 32 Stage events through step672 (20 guidance-off,12 on). Low EDS row count does not mean short episodes or early completion. Source: `run_044.../mechanism__eds_qd_protected_quality_secondary_v1/eds_eval/{stage_events,eds_metrics}.jsonl`. With guidance inactive, a QD-only change has no immediate selection influence; this bounds attribution.

## Ranked mechanism queue (two directions only)

### 1. Executable gripper-mode retention — recommended next bounded diagnostic

**Hypothesis:** XY-only archive replacement discards a distinct executable gripper mode before ED can refine its accompanying translation. Preserving a reward-best representative of a *different executed gripper sequence* can alter future offspring in useful ways. The 82 exact elimination events and 8/20 final-pool alternatives establish an observable mechanism opportunity; outcome utility remains to be tested.

**Single conceptual intervention recommended after coordinator review:** replace XY with projected terminal target distance × positive-command gripper duty, using four radial bins and four fixed duty bins (16 cells, capacity one). Duty is the number of deployed +1 commands in the eight-action chunk divided by eight; bins are `min(floor(4*duty),3)`. Freeze radial bounds from the initial candidate population with the historical quantile/expansion rule; fixed duty bounds are [0,1]. Preserve existing reward quality, sparse parent allocation, global reward-best final selection, 176 evaluations/11 score batches, decoder/provider and 8-action execution. This is representation-only; no semantic parent reserve, extra capacity or old H1/H4/H5 switch is included.

All 82 discordant eliminations differ in duty, and 73/82 separate under these four duty bins independently of the proposed radial coordinate. Per-task separated/observed events are task1 8/8, task2 5/6, task3 4/4, task4 8/8, task5 1/2, task6 22/22, task9 25/32. This is stronger support than generic trajectory distance. **Tradeoffs:** radial distance drops azimuth and sign of vertical displacement; the same duty can encode different opening/closing timing; fixed four bins merge some eighth-fraction differences; radial coarsening can create new collisions and reduce represented spatial modes. Positive duty should not be named “closure duty” before controller polarity is checked. Pairwise separation is not proof that 73 candidates survive the complete new archive or become parents.

**Difference from old hypotheses:** H1 expanded XY bounds; H2 routed exact-degenerate reward into QD-off control; H4 always reserved the current reward-best lineage; H5 kept a generic second reward-ranked action per XY cell. None conditioned preservation on a deployed gripper-action distinction, and all still ranked with the same proxy. The new mechanism can be inactive when no distinct mode exists; claiming universal secondary activation would recreate H5's unsupported gate.

**Next falsifiable diagnostic:** Replay fixed saved pools with the frozen radial×duty descriptor and record (a) which of the 82 discordant eliminations become retained/allocated after all new collisions, (b) unchanged global reward-best winner, (c) exact 16-parent allocation and 176/11 prospective accounting, (d) no candidate fabrication and reset equivalence, (e) radial/XY spatial-mode loss and gripper-mode retention. Reconstruct terminal 3D geometry using the original projection precision; do not substitute the t7 score endpoint silently. Reject if retention never changes real parent identities or breaks quality/accounting. This replay only establishes mechanism; fixed saved offspring cannot prove what changed parents will generate.

**Same-round outcome test:** After corrected-cache P2 and Q0 baseline validation and GPU7 admission, use new Dev cells frozen by the coordinator, candidate vs contemporaneous P2 plus the candidate's unmodified Q0 comparator. Log mode opportunities, actual parent substitution, resulting offspring lineage, selected mode, observed next-chunk action/observation and complete episode success. Abandon/promote by the preregistered task gate; if mode activation is real but task success fails to improve over controls, do not preserve it merely for higher mode retention. No counterfactual simulator rollout is authorized by this recommendation.

### 2. Executed-horizon-aware QD use of existing quality — secondary diagnostic, not automatic implementation

**Hypothesis:** t7-scored candidates and t8 behavior/execution differ enough to misrank actual executed-prefix geometry. First verify 17/220 proxy identity discrepancies with higher-precision decoded trace reconstruction and the corrected cache, then relate selected t8 geometry to the next *observed* chunk. Only then consider a frozen QD-local final-action/progress ranking feature; do not silently globally change reward slicing or the external provider.

This differs from H1 partition expansion, H2 exact-zero routing, H4 reward-best allocation and H5 generic per-cell capacity. It has direct boundary evidence but currently lacks task-outcome linkage. Reject/park if discrepancies are rounding artifacts, do not affect selected actions, or show no observable relation to execution. It is lower priority than action-mode retention and must not be combined with direction 1 in the first candidate.

**No third candidate is proposed.** Generic cross-chunk smoothing/memory lacks new task-linked evidence here; the prior smoother-motion negative result and Stage/guidance gating make blind continuity reuse unjustified.

## Input/cache and exposure integrity

The [root handoff](/home/hynx/VLA-Pilot++/HANDOFF.md:355) explicitly warns that the reused historical guidance cache originates from one task and cannot be presumed valid for all target identities. Parallel runtime intake reports alphabet-soup target descriptions reused across tasks; this node does not use that report as evidence of any particular episode's failure. Treat the target mismatch as a separate engineering baseline validity problem, audit each task's instruction/cache targets, preserve historical evidence, and relabel/re-establish repaired controls. Any repair benefit is not QD benefit. Historical trace findings remain observations about that historical pipeline and require replication under corrected inputs.

The [exposure inventory](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/data/historical-exposure-inventory.jsonl) contains 54 unique task/seed cells, 419 episode-metadata occurrences and 378 task/seed-bearing ledger records from the original QD output root and the old autoresearch artifact root, including historical invalid/recovery paths. Each occurrence has source path, line and SHA-256. These counts are **not attempt accounting**; repeated metadata/ledger copies must not be summed as episodes. Actual metadata is preferred to intended reservation mapping; both are conservatively excluded when choosing new seed cells.

Per-task distinct exposed seed counts (0…9): `[4,4,5,7,4,7,4,6,6,7]`. All 54 cells have actual metadata somewhere. This bounded inventory is not claimed exhaustive over every unrelated historical worktree; the coordinator must merge any other known exposures before freeze.

The backend fixes `episode_index=0`, hence init row0, rather than selecting init by env seed ([adapter](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/core/env_adapters/libero_adapter.py:621), make_env line940). Each inventory record stores task name, known Run010 init-file SHA, expected init index0 and the explicit caveat that this is a source-bound expectation, not a separately serialized old per-episode init snapshot. Run010 input hashes are historical reference identities and are not asserted independently verified for every older job. New seeds provide stochastic-seed robustness evidence, **not new-layout generalization**. Task order is from the backend's object-swap task map; this suite does not apply the standard-suite permutation.

## Reproducibility and artifacts

- Diagnostic: [script](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/scripts/qd_ed_executable_behavior_diagnostic.py).
- Artifact: [executable-behavior-diagnostic.json](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/iteration_000_intake/executable-behavior-diagnostic.json), with all 20 trace paths/hashes, 82 elimination records, selected/alternative identities, per-task counts, software and script fingerprint.
- Tests: `CUDA_VISIBLE_DEVICES='' /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -q tests/test_qd_ed_executable_behavior_diagnostic.py` → **3 passed** (decoder zero semantics, fingerprint tie displacement, lower-quality branch rejection). Actual 20-trace exact replay is the main validation.
- No authoritative Arbor state/tree was modified by this node; no commits were created.

Reproduce:

```bash
CUDA_VISIBLE_DEVICES='' /home/hynx/miniconda3/envs/vla-pilot/bin/python scripts/qd_ed_executable_behavior_diagnostic.py \
  --trace-root /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/outputs/formal/eds_quality_diversity_sparse_primary/eds_eval/qualitative \
  --output /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/iteration_000_intake/executable-behavior-diagnostic.json
```

This node's absolute primary task score is **unmeasured** (zero new episodes). Historical Q0 remains 2/10; no score gain or adoption claim is made.
