# GPU3 N10 continuation budget proposal (inactive, revision 2)

Status: **proposal for user audit; no budget cap, resource state, or peer study
has been changed**. This applies only to the GPU3 study
`rdt-qd-ed-final-20260921T093925Z`. The existing GPU2 study keeps its own
budget, card, locks, and artifacts. All previous attempts and costs remain
charged; no failed episode is retrospectively accepted or rerun to select a
favorable result.

## Decision basis

The private GPU3 journal now records **184/240** episode attempts and
**24.179518/48 GPU-process hours**. Bucket use is baseline 20/20,
development 97/100, validation 60/60, formal 0/40, recovery 7/20. The
accepted passive N7 task0 diagnostic exactly reproduced its original 90
action fingerprints and five ≥1 cm target-keypoint shifts, with valid stable
tracking. Task3 returned a final Stage answer equivalent to the historical
one but had seven preceding Codex error events and an error item; the frozen
E1 transport gate rejected it and the fallback changed the subsequent
policy trajectory. The stopped diagnostic used two Dev attempts and 0.228598
GPUh; task6/9 were not dispatched. Its mechanism gate did **not** pass.

The new E2 transport condition is prepared as an opt-in, code-only change,
with default E1 parity and 67 CPU tests passing. It accepts only completed,
fully accounted, single-answer streams with recoverable errors strictly
before the final message, records those errors, and leaves all other failures
fatal. This does not retroactively rescue task3. Its exact prospective
four-task diagnostic is described in
`variants/n10_lineage_survival/e2-prospective-measurement-protocol-v1.md`.
The original execution specification §4 freezes the Stage recognizer and
requires authorization for a scope expansion. **Approval of this proposal
also explicitly authorizes only this narrowly specified E2 transport
acceptance change**. It does not authorize changing the Stage prompt,
semantic parser, model, grounding, success predicate, or action horizon.

## Proposed cumulative hard limits

| Bucket | Current cap | Proposed cap | Extra | Bound use |
| --- | ---: | ---: | ---: | --- |
| Baseline | 20 | 28 | 8 | At most two C0 four-task matched Dev arms |
| Development | 100 | 125 | 25 | Four E2 N7 tracking cells, then at most two Q0/N7/candidate × four-task Dev comparisons; the three old unused Dev slots count toward this |
| Validation | 60 | 180 | 120 | At most two distinct fresh 20-cell seed blocks × C0/Q0/candidate |
| Formal | 40 | 40 | 0 | One historical fixed 10-task acceptance × C0/Q0/candidate/QD ablation |
| Recovery | 20 | 20 | 0 | Thirteen remaining slots, exact-identity infrastructure recovery only |
| **Total** | **240** | **393** | **153** | At most **209** further attempts from today's 184 |

Proposed cumulative GPU-process limit: **100 hours**, up from 48 (+52).
This is a ceiling, not a spending target. Local ceilings: prospective E2
diagnostic 4.2 hours; two matched Dev cohorts 6 hours each; two validation
cohorts 16 hours each; final formal 12 hours; further non-diagnostic recovery
and health checks together 8 hours. Adding those local ceilings to current
consumption gives **92.379518 hours**, leaving **7.620482 hours** of global
margin. Admission must also preserve validation/formal reserved hours and
the per-bucket attempt limits. A timeout plus cleanup grace that does not fit
must be rejected before dispatch. An invalid or failed cell may leave budget
unspent.

The versioned amendment will raise protected GPU-hour reservations from
validation 14/formal 10 to **validation 32/formal 12 hours**, with the
required append-only reservation-change event. Those are ceilings for the
planned two validation cohorts and single formal cohort, not permission to
spend them in Dev. The runner must reject a non-protected dispatch that would
consume either remaining reserve.

## Gates and anti-leakage rules

1. On GPU3 only, run the complete four-cell N7 E2 passive diagnostic in
   original task/seed/init order, each once. All cells use the same E2
   condition, unchanged N7 profile and passive keypoint observer. This is
   reused Dev evidence, not generalization evidence. Stop on any invalid
   Stage/native/tracking condition; no automatic retry. Require the frozen
   two-distinct-task tracked-shift and same-stage-opportunity design gate.
2. If that gate passes, implement one physical feedback conditioned QD
   mechanism with a behavior defined in stable physical coordinates, not a
   raw QD cell index. Freeze its source, config, hypothesis, comparator arms
   and admission before an online four-task Dev cohort. Controls C0, Q0 and
   N7 run under the same E2 condition and seed/init as the candidate. A
   candidate can advance only with safety/compute/evidence validity,
   ≥3/4 task successes, strictly more than same-round N7, and no fewer than
   same-round C0 and Q0. A second candidate, if needed, must have a distinct
   preregistered mechanism; no coefficient sweep based on a failed cohort.
3. Only a Dev-qualified candidate may enter a fresh 60-cell validation
   cohort: two pre-frozen seed blocks per 10 tasks × C0/Q0/candidate, with
   input hashes and E2 condition fixed. Require ≥10/20 candidate successes
   and no lower total than both same-round controls. If the first candidate
   fails validation, its observed block cannot be used to tune a second;
   the second receives new pre-frozen seeds disjoint from Dev, prior
   validation and formal identities. Fixed init row0 remains a seed
   robustness claim, not new-layout generalization.
4. At most one validated candidate reaches formal. Freeze its source,
   settings, QD ablation and historical fixed task→seed/init map before
   release. Acceptance requires ≥5/10, no worse than contemporary C0 and
   Q0, active QD, full provenance and safety. No tuning or rerun of the
   exposed formal set after failure.

If the E2 tracking mechanism gate fails, this feedback branch stops. A new
candidate would need a separately documented parent-to-offspring mechanism
and a frozen comparison within the same ceiling; no validation/formal spend
is authorized by a diagnostic alone. If two candidate cycles fail, report
`TARGET_NOT_MET` with negative results and remaining budget instead of
claiming success. The target is not guaranteed by this allocation.

## Implementation and isolation after approval

Approval would authorize a versioned amendment to this study's
`research-state.yaml`, `research_config.yaml`, owning `AGENTS.md` resource
notice, local budget/runner guard and runtime condition,
followed by CPU checks of over-cap rejection, protected reservations,
exact-identity recovery and GPU2 isolation. The current runner still rejects
limits above 240/48; this proposal alone cannot start an expanded run.
An isolated, inactive runner patch is already prepared under
`variants/n10_lineage_survival/stage_transport_e2`; 129 related CPU tests
pass, including exact amended-cap admission and unchanged default E1 behavior.
It has not been integrated into the owning runner or used for GPU work.
Historical ledger lines, N7 C1 validation, invalid task3, and the 40 formal
slots stay intact. One GPU3 worker; no other study's GPU, budget, locks,
state or output paths. All new code, plans, reports and heavy-artifact links
remain under the unified `eds-qd-autoresearch-libero-swap-ood` root.

Approval scope: these numerical ceilings, the E2 transport exception above,
and the bounded staged process. Each
specific candidate still needs its own frozen scientific plan before GPU
dispatch. No new GPU attempt above the old budget may begin until the user
explicitly approves this amendment.
