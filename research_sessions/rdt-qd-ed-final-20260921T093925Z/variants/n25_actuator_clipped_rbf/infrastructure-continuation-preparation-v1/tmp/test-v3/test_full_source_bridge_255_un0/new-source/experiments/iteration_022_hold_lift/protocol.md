# N22 conditional matched ten-task Dev protocol

Frozen after CPU implementation and before N21 candidate outcome is revealed. This is conditional preparation, not an execution release. N21 remains priority: if its frozen Dev gate passes, evaluate N21 under its existing validation plan before considering N22. If N21 is rejected at Dev or later validation, review and freeze N22 source/plan before using this new Dev cohort. No N21 or N22 result is reclassified or selected from retries.

## Hypothesis and single algorithm change

Use the opt-in `close_hold_then_lift_v1` mode described in `protocol-cpu-v1.md`. Everything in N21 is preserved except that projected lift bonus is zero if any deployed gripper command after the first eligible near-target close is open. This is command continuity, not a grasp detector. Existing saved-Dev replay verifies that this can change within-cell elite identities and subsequent ED parent actions (1/16 N20 task0 decisions and3/17 N17/N7 task0 decisions), although fixed-pool terminal selections are unchanged. There is no online N22 outcome yet. Full CPU implementation is960f90e; protocol and final source identities will be bound in the execution plan.

## Matched development experiment

Cohort `N22_HOLD_LIFT_DEV_20260930`, original Dev tasks0..9 in backend order, each with fresh contemporaneous C0, Q0, N21, N22 cells, task-major in that arm order. Reuse only original frozen Dev task/seed/init identities; these tasks are exposed development data and provide no independent generalization claim. No seed substitution. N21 is a same-round ablation comparator only and cannot be promoted or replace its earlier rejected cohort on the basis of these repeats. The prospective distinction is explicitly a new matched algorithm experiment, not an N21 retry.

One serial worker on idle GPU7 with the same verified UUID/EGL/probe and frozen E2 Codex Stage condition. Maximum40 dispatched attempts,21 GPU process hours; per episode1800-second timeout plus40-second cleanup reserve. Every abort/invalid/implementation failure remains charged. No automatic retry. Stop the cohort on any invalid outcome or failed independent native audit. Also stop for predeclared numeric futility after a completed task quadruple if N22 successes plus remaining tasks is less than5. A task0 failure alone is not a universal veto: original acceptance permits failures on individual tasks.

Dev promotion requires all40 cells valid and independently audited, N22 success count at least5/10 and no worse than contemporaneous C0,Q0,N21, substantive QD archive/quality/parent search and ED activity, unchanged deployed action contracts and176 canonical candidates/11 canonical score batches per guided decision. Report total episode model/reward/Stage calls and GPU time. Report hold-bonus, archive and selection effects as mechanism evidence without imposing arbitrary counts as an extra success veto. If success gates pass without evidence for the new explanation, disclose that limitation; do not claim causality. A failed Dev cohort is not resumable for best-of selection.

## Private resources under autonomous continuation

The latest user directive is `继续完成满足目标且无需我介入的autoresearch`; its recorded interpretation is in the N21 authorization record. Before dispatch, record the bounded N22 resource amendment: cumulative398→438 attempts; baseline31→41,development127→157,validation180,formal40,recovery20. Preserve100 GPU hours and validation/formal hour reserves32/12. This grants at most one40-cell N22 cohort; unused older slots are retained and not permission for unrecorded experiments. If actual remaining GPU hours cannot protect validation/formal, do not dispatch an over-cap episode; record and resolve that resource limit prospectively. No cloud purchase, other-study mutation, external-process preemption, or second GPU worker.

## Protected evaluation

Only after the full Dev gate passes may an unused pre-frozen candidate validation block be bound and released:20 candidate episodes and20 each C0/Q0, candidate>=10/20 and>=both controls. Prior exposed validation cannot guide N22 tuning. Formal then follows the original single-final-candidate ten-task historical acceptance rule, at least5/10 and>=controls, together with the compute-matched QD ablation and complete provenance. Neither protected phase is authorized by a Dev execution release. Goal status stays TARGET_NOT_MET until that full acceptance is met.
