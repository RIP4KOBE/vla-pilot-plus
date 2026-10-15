# N35 closure-intent proposal memory — CPU feasibility registration

This is a new hypothesis, not a released GPU protocol. Existing N34 source, results and gates remain unchanged. Only exposed Dev evidence may be used. No validation/formal access.

PROBE BLOCK
Q1 First principles: loss of action intent across replanning boundaries. Turn877 task6 executes +1 at536–543 then -1 at544–551 with measured jaw closure/reopening; turn876 task6 had30/44 direct proposal-content selections yet failed. These support a control-state failure hypothesis, not grasp causation.
Q2 Hidden assumption: the current observation and archive alone retain useful closure intent. Dropping it permits an explicitly expiring memory of a physically executed close event.
Q3 Elephant: tracked target proximity and jaw closure are not contact or grasp labels; persisting a false closure can worsen performance.
Q4 Hamming: yes, temporarily preserving an otherwise discarded physical action intent is a meaningful class-level planning question; only task success can support efficacy.

Four moves considered:
- Assumption inversion: one-boundary closure-intent memory as an ordinary QD competitor (selected).
- Backward from success: contact-confirmed lift option; defer because present evidence lacks a reliable nonprivileged contact signal and it combines another intervention.
- Analogical transfer: hysteretic forced gripper latch; reject because forced execution bypasses ordinary QD/ED selection and obscures the original goal.
- Failure reverse engineering: rescue all closed archive candidates; reject as N24-style within-search retention without a new counter.

Survivor declaration:
1. Assumption challenged: useful intent must be reconstructed independently every chunk.
2. Mechanism class: planning/control state in QD proposal generation.
3. Mechanism and hypothesis: one expiring close-intent competitor may reduce immediate reopening because actual execution and jaw response establish a prior action event; test fresh matched Dev success and native selection/execution, not jaw motion alone.
4. Orthogonality: N31/N32 forecast entry within a chunk; N33/N34 use present geometry. N30 shifts a previous winner after approach progress. N35 retains only closure intent after actual full-prefix execution, does not replay or shift a prior trajectory, and leaves ordinary quality/ED unchanged.
5. Conflicts: N24 and N30 failed; this does not infer that memory generally works. It specifically tests the previously unrepresented executed close event. N34's task5 success has no direct selected proposal and is not evidence for this change.
Self-check: not a scalar tuning change, prompt tweak or increased compute; falsifiable discrete state with explicit expiry and negative outcomes. No claim of novelty beyond local mechanism distinction.

CPU contract (frozen before reading additional native fields):
Use only N34 Dev task6 contexts/decisions/actions already bound by turn877 extraction, steps528–552. At boundary544, eligibility requires (a) prior guided536 chunk with direct selected content equal to its observed_close_dwell proposal, (b) all eight executed gripper commands positive and identity-linked, (c) same recognized target and same Stage between536 and544 with guidance enabled at544, and (d) finite measured jaw separation strictly decreased across the boundary. Any missing required field is Unknown, not eligible. Do not substitute ancestry, tracker motion or commanded closure for these requirements.
If eligible, define a single-use memory for boundary544 only. In the ordinary offspring replacement slot, copy the current ordinary archive best and replace only its first-eight gripper commands with native +1; leave translations/rotations/later actions untouched. It competes with the other15 unchanged candidates under unchanged scoring/archive/ED selection. It does not force action execution, add model calls or persist through unguided steps. Expire after that boundary regardless of selection; no rearming from a memory-generated closure. Reset on episode/target/Stage change or incomplete execution. Existing N34 current-observation proposal is the fallback when memory is ineligible; the memory proposal replaces that same slot when eligible, never adds a slot.
CPU feasibility must establish all trigger fields, identity linkage, one nonidentical native proposal, and an executable production hook without protected inputs. Any absent trigger, missing provenance, identical proposal, or unresolvable source ambiguity rejects this exact design; no threshold/gate relaxation using task6. CPU result never demonstrates task gain.

Before implementation: independent CPU executor review must assess these gates and exact source hook, including whether repeated parent rounds can consume one boundary memory consistently without changing total proposal count. Coordinator does not edit benchmark code.
Before GPU: separate immutable prospective Dev protocol with fresh matched C0/Q0/N34/N35 controls, task/seed identities, success/futility gates at least as strict as retained necessary5/10 and >=controls, full cost/native audits, finite budget arithmetic and protected reserves. Exact counts/order/cap/deadline must be frozen and reviewed before dispatch. No reuse of old controls as fresh evidence. Current registration authorizes no GPU execution or scientific promotion.
