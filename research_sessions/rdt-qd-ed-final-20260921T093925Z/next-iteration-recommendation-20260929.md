# Next iteration recommendation after N12 task3 contrast

**Status:** recommendation and evidence plan only. No new algorithm, GPU
attempt, Stage transport change, validation or formal release is authorized by
this document. The study target is still `TARGET_NOT_MET`.

## Priority 1: zero-GPU signal and input-contract audit

Use only exposed Dev evidence: the N10 passive N7 task0/task3 attempts, the
same-round N7/N11 task3/task6 records, and the approved N12 task3 physical
contrast. Verify hashes and compare timestamps, target-keypoint identity,
tracker instance/generation/validity, EEF/gripper motion and Stage/guidance
boundaries. Separate pre-error measurements from complete-episode validity:
N10's frozen E2 task0 cell remains scientifically invalid and must not be
retroactively promoted. Do not use N7 C1 validation outcomes to tune a rule.

The existing `KeypointTracker` calls `LiberoAdapter.get_object_pose_by_segment`,
which reads the simulator body pose. This is part of the current benchmark
pipeline, but it is not an image-only or real-robot sensor. Explicitly declare
whether a proposed feedback variable is already available to the frozen
policy under the benchmark contract; never import privileged poses/contacts
from a diagnostic branch as a new policy input. If the desired variable is
not allowed, test whether existing policy-visible RGB-D observations can
produce it before freezing a QD–ED method.

Deliver a binary `SIGNAL_READY`/`SIGNAL_NOT_READY` result. `SIGNAL_READY` needs
at least two distinct task paths with valid target tracking and action-linked
motion, at least two immediate same-stage next guided opportunities with
stable tracker identity, and a physically defined cross-chunk behavior
descriptor. These are feasibility requirements, not an efficacy claim. Missing
pose/identity, Stage incompleteness, or a signal only available after guidance
ends is reported as Unknown or not ready, not as zero motion.

## Priority 2: one prospective feedback-conditioned QD–ED candidate

Only if `SIGNAL_READY`, freeze one hypothesis card and implementation. The
candidate would use the previous executed chunk's *valid, policy-visible*
target-motion and EEF/gripper feedback to condition QD parent allocation or
quality in stable physical coordinates. It must not simply tabu a numeric
cell ID whose quantile bounds change across chunks, relax N5's close gate, or
retune N9's projected lateral penalty. Keep RDT, Stage condition, QD activity,
population 16, 10 iterations, 176 evaluations and 11 score batches per guided
chunk; fail closed when tracking is invalid. Require CPU tests for identity,
input legality, unchanged compute and native action/lineage accounting before
any GPU release.

For a first online Dev gate, pre-freeze four exposed tasks 0/3/6/9 with
same-round C0, Q0 and candidate arms: 12 original attempts, one GPU3 worker,
no legal-task-failure retry. Require candidate at least 3/4, strictly above
both same-round controls, and audited QD/feedback activation before any new
validation plan. This 12-attempt proposal fits the remaining development
14/125 cap **only if** no additional GPU measurement is needed. Any GPU
diagnostic consuming more than the two spare development slots, or a desired
four-arm N7 ablation, needs a new explicit bucket amendment before dispatch.
If Dev passes, use a newly frozen 20-cell-per-arm C0/Q0/candidate validation
(60 attempts) with the existing ≥10/20 candidate gate; preserve the 40-attempt
formal bucket and 32/12 GPU-hour protected validation/formal reserves. The
historical fixed 10-task acceptance set is used only after validation passes.

If the CPU audit returns `SIGNAL_NOT_READY`, do not spend GPU on a speculative
feedback candidate. Report the precise missing observable or input-contract
constraint and propose a separately scoped diagnostic if it can resolve that
gap. Any additional same-state branch simulation requires its own §5 approval.
