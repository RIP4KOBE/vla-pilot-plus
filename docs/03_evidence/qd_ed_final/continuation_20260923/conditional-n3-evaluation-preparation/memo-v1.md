# Conditional N3 protected-phase integration memo

Status: SOURCE-ONLY PREPARATION; NO PROMOTION OR EXECUTION AUTHORIZATION. The live
Dev source is `bd618b931eb9d8fc2c01b978c4ef220c9bb03889`. No new Dev payload,
protected outcome, model, provider, simulator or GPU was read/executed. Source
hashes and the scope of this review are in `source-review-v1.json` alongside
this memo. The old isolated evaluation prototype is `ed56611dc45d28dbc59ffa172a810a810360dfc1`.

## Required gates and matrices

The original user execution spec §§7–8 and N3 protocol's final section require
complete matched Dev evidence, N3 >=5/10 and >=C0/Q0, plus the frozen scientific,
native-feedback, raw-Stage, safety, compute and substantive-QD gates. A task0
checkpoint, counters, edited phase boolean or incomplete report cannot release
validation. Recompute the final frozen N3 report against its complete
base/revision/journal snapshot, preserving invalid predecessors, predispatch
records and costs. Bind the selected source and production bytes to the actual
reported Dev source, not a same-named candidate.

| Phase | Prospective originals | Numeric rule and release |
| --- | --- | --- |
| Validation | Two frozen new seed blocks × tasks0..9 × C0/Q0/N3 =60;20/arm | Full60 valid/audited, N3 >=10/20 and >=both controls, scientific review |
| Formal | Historical fixed tasks0..9 × C0/Q0/N3/N3_QD_OFF =40;10/arm | Full40 valid/audited, N3 >=5/10 and >=C0/Q0, scientific review; disclose ablation comparison |

The immutable seed plan remains unchanged. The former N2 precheck of c1 is
historical metadata, not current exposure authority. Recheck task/env-seed/init
identities and exposure registry under the shared lease; do not silently select
a new block or inspect outcomes to allocate one. Row0 with changed policy/env
seeds supports seed robustness, not new-layout generalization. Reports must key
the full task/seed/init/profile/block identity, keeping both validation blocks.
Formal is the already exposed historical acceptance set, with one final
candidate latched atomically before its first reservation. A validation failure
ends this candidate's promotion; formal failure cannot be tuned and rescored.

Source anchors: W user spec §§7.1–8 (lines166–223); N3 protocol lines35–41
(raw channel/ablation) and49–61 (matrices/promotion).

## Minimal reusable support and missing pieces

Reuse the *design*, not the old N2 authorization, of isolated
`qd_ed_n2_evaluation.py`, `qd_ed_n2_evaluate.py` and
`qd_ed_n2_evaluation_report.py`: exact production/tooling mapping, independently
recomputed certificates, full-cell reports, recovery references, atomic
allocation/formal latch, validated phase-hour permission and explicit settled
reservation release. That prototype hardcodes N2, Q8, its Dev reporter and
cohort IDs. It cannot certify N3. Its older report also bounds raw terminal
record count rather than real dispatched attempts; retain N3's newer
predispatch/inflight journal-excerpt semantics instead of copying that limit.

Reuse frozen N3 source helpers for native audit alignment, exact recovery
criteria, public metric checks, full-journal inventory and accepted-audit gate;
reuse the real global flock/120s stability/boot/UUID/PID/PCI-Xid supervisor and
original runner finally accounting. Unknown Xid remains nonretryable: ownership
does not prove an infrastructure cause. Never convert a preserved
valid/outcome_valid=false transport terminal into an aborted task outcome.

The minimum future implementation is three new N3 phase modules (closed
contract/builder, dedicated supervisor, independent full-cell report), a named
evaluation-profile manifest, prospective phase/budget documents and narrow
generic runner/queue dispatch guards. All plans start with phase flags false.
The protocol must enumerate these tooling changes; byte-identical production
files include N3 helper and semantic helper, RDT policy/QD/metrics, main/adapter,
tracker, Stage/provider, collector/auditor, configs and frozen model/native
inputs. Preserve the original Dev source; any required production behavior
change returns to Dev rather than inheriting its pass. Bind the new whole phase
HEAD/runtime/input and tooling-to-Dev map before the first protected reveal.

## QD-removal semantics: implementation support, remaining binding gap

The N3 protocol explicitly retains feedback, internal quality, ED and raw Stage
while removing the archive mechanism. W's `core/rdt_policy_steer.py` resolves
`executed_feedback_v1` with `qd_archive_mode` grid or none, initializes feedback
independently of archive creation, and keeps raw quality distinct. Source test
`test_n3_full_loop_feedback_native_raw_stage_and_176_11` covers grid/none and
FP32/BF16. This is source/test evidence, not a new test execution here.

Define N3_QD_OFF as an exact copy of the frozen N3 profile with only active
delta `qd_archive_mode=none` (plus its descriptive profile label). Keep the
now-inactive sparse-parent setting unchanged, population16/10 iterations,
176 canonical evaluations/11 batches, native t1..7 past-residual quality,
all reset/OFF/acknowledgement/registry rules and raw Stage. Do not substitute C0
or N2/Q8. Archive removal necessarily removes archive retention, archive-based
parent allocation and final-elite selection; the existing none branch supplies
the unchanged ED behavior. The resulting executed history may differ: retain
the rule, not another arm's recorded residual values.

Exact W anchors: `core/rdt_policy_steer.py:4860` (feedback setup independent of
archive), `:4929` (archive flag), `:7814` (quality/grid-or-none resolution);
`tests/test_rdt_steer.py:10033` (full-loop test);
`scripts/qd_ed_final_runner.py:868` (resolved mode/11/176/raw transport gates).

Current N3 report `scripts/qd_ed_n3_report.py:239` treats profile !=N3 as provider quality, while its supervisor
`scripts/qd_ed_n3_supervise.py:116`
routes the native alignment check only for profile==N3. A new phase adapter must
explicitly route both N3 and N3_QD_OFF through the identical N3 native audit,
require archive-inactive on the ablation, and reserve substantive-QD deployment
gates for N3. Reuse `scripts/qd_ed_n3_plan.py:57` for exact count alignment and the frozen
`scripts/audit_decision_evidence.py:416` specialized gate. No production audit
relaxation is indicated. All recognized/active
counts must match the specialized audit exactly. No extra arbitrary ablation
superiority threshold is warranted; disclose ties/adverse differences and do
not turn equal scores into a causal QD benefit.

## Budget and prospective decisions still required

Keep 60 validation +40 formal original slots and14h+10h reservations intact.
Original rows charge their own phase buckets; certified recoveries retain raw
recovery buckets. If root adopts the old prototype's at-most4 validation/2
formal recoveries, freeze those ceilings anew for N3, at most one per cell,
with exact unchanged identity and remaining global/recovery limits. A validated
phase context may allow its own recovery to use its phase hours while protecting
later-phase hours; no unvalidated row label grants that permission. Full
1800+40 must fit every admission, never a clipped timeout. Release an unused
validation hour reserve only through an explicit completion-bound ledger event
after passing full60, all episode/health costs settled and genuine certificate;
do not perform that release during CPU preparation.

Root subsequently supplied checkpoint totals82 attempts/12.1038625485h; its
three episodes are already inside N3's34/8h, not additional to that envelope.
No live ledger was opened for this memo.

Capacity illustration only, using the supplied *pre-N3*79 attempts/11.7253744095h:
at N3's maximum34/8h, 127 slots and28.2746255905h remain. The100 originals plus
proposed6 recoveries fit the slot total (219/240 overall; raw recovery16/20),
assuming no additional shared-journal work. This is not a current budget audit
or a completion guarantee. Even100 full1800+40 windows total51.111h, exceeding
that available time;14h/10h are protected minimum allocations, not proof the
workload fits. At Dev close, recompute authoritative settled costs and all
outstanding identities, account for external shared-journal work, then freeze a
feasible phase allowance with slack or report insufficiency without borrowing,
altering caps, reducing the matrix or retrying valid failures.

Before implementation/release, root must freeze the exact unused seed cohort,
order/keys, N3_QD_OFF delta, recovery/hour rules, production/tooling map, native
audit/report schemas, complete promotion certificate inputs and formal latch.
Focused synthetic regressions should cover unreleased/generic dispatch refusal;
source/seed/exposure drift; full60/40 denominators and base+recovery revisions;
predispatch/inflight/invalid inventory; both quality-preserving ablation routes;
exact native active counts; recovery phase-hour isolation/full-window rejection;
and settled-only reservation release. No such implementation or release is
performed by this memo.
