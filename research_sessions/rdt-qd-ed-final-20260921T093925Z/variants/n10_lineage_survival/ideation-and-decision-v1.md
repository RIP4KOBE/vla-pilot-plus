# Bounded outer-loop decision after N7/N9 (Dev evidence only)

The Arbor tree constraints were read before this ideation. This is an IDEATE
record, not an online candidate release. The current private validation
budget is zero and the fixed historical formal gate is closed.

## Probe block

- **Q1 First principles — wrong credit assignment / missing physical outcome:**
  N7's archive-best proxy quality exceeds final-row best in 31/33 guided
  decisions, including all six decisions in its successful Dev episodes.
  N9 reduced a projected lateral-sweep metric in six changed decisions but
  lost the N7 task-9 success. The internal proxy does not identify which
  actions physically complete manipulation.
- **Q2 Hidden assumption:** A higher provider reward or less projected sweep
  is a reliable stand-in for contact safety. Dropping it opens a feedback-
  conditioned QD mechanism based on actual previous target motion, subject
  to tracking validity.
- **Q3 Elephant:** Native per-step outcomes lack target pose/contact state;
  decision-boundary target keypoints move ≥1 cm in seven failed-task chunks
  and zero successful-task guided chunks, but the bundles omit the keypoint
  tracker's validity flags. That association is too weak for an online
  intervention without a bounded validity measurement.
- **Q4 Hamming:** No. Passive instrumentation is a measurement step, not an
  algorithm. A later physical-feedback-conditioned QD parent policy would be
  a distinct algorithm class if it changes real actions and task outcomes.

## Four moves and self-filter

1. **Assumption inversion:** Use actual previous-chunk target-keypoint motion
   and tracking validity to condition future search instead of preserving
   internal proxy best. This differs from N3's EEF prediction-residual reward.
2. **Backward from success:** A useful search should approach without
   unintentionally perturbing the target, then carry/place it when required.
   Existing logs do not yet certify which branch is occurring.
3. **Analogical transfer:** One-chunk tabu search could suppress a previously
   perturbing behavior, but numeric QD cell IDs are unstable across chunks:
   all four eligible transitions changed height bounds, and one same-number
   cell had disjoint height intervals. Any later memory must use stable
   physical coordinates or reprojected behavior with a validity guard.
4. **Failure-case reverse engineering:** Failed task0/3 have seven ≥1 cm
   target-keypoint shifts; successful task6/9 have none in their six guided
   chunks. Gripper commands and projected first-entry speed do not cleanly
   separate those shifts, so an open-loop geometric penalty is not selected.

Rejected now: (a) direct archive-best execution, already close to Q0 and
contradicted by N4/H4 outcomes; (b) simple N9 sweep/entry-speed retuning,
whose fixed Dev screen had weak specificity; (c) numeric-cell tabu, whose
cross-chunk semantics are unbound and whose observed reach is only four
nominal parent slots. All three are either prior-tested or explain only a
proxy. The survivor is a **measurement prerequisite**: passively log the
already available target-tracking validity at decision boundaries in four
N7 Dev reruns. Only if it establishes a trustworthy, action-relevant signal
will a separately frozen feedback-conditioned QD candidate be built. If not,
return to an explicitly different parent-to-offspring mechanism or report
that this budgeted cycle lacks a testable causal path.

This decision uses only exposed Dev traces. N7 C1 is used solely to know that
N7 was rejected, never to pick task/seed-specific changes. Formal is untouched.
