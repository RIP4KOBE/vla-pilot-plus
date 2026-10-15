# N4 shared resource conflict review

**Status: N4 is not currently executable.** This review supersedes only the
*current capacity premise* of the earlier N4 resource memo and the subsequent
one-Q0-to-baseline suggestion. It does not change any scientific protocol,
previous result, budget record, or approval. Snapshot: 2026-09-24 03:19:53 UTC;
W source `9e5c63632fbd9169e88b6437b50f365eac819d6b`. Exact paths, hashes,
resource metadata and live lease evidence are in `source-review-v1.json`.

## Authority and observed enforcement

The original execution spec §1 permits autonomous prospective work inside
48 GPU-hours/240 attempts, protects evaluation capacity, and identifies budget
expansion as a user decision. W `ARBOR_CONTRACT.md:11` records the original
20/100/60/40/20 phase allocation. The generic runner enforces the minimum of
its source `BUCKETS` and mutable state caps, plus global/protected limits and
no unfinished work (`scripts/qd_ed_final_runner.py:635–665`). A local spare
bucket is not an independent resource pool when the journals and lease are shared.

The newly supplied resource-only coordination document records a separate
external user approval to transfer nine baseline and thirteen recovery slots
to development. Authorization SHA
`ebd43aa5ad751aee9de02c956f9da91ffaa1e76312189ebcf07c3a99b682ea55`, approved
amendment SHA `f13ca0cb9b2dd4c6de3d697680a57c30ed0913756cd66badd22f23761fb21bce`,
and cohort manifest SHA
`d23b7108060654f4280b944d737e2cde0ea875466849a807aabed431c5a43b47` form a
consistent hash-linked resource record. The record contains the user instruction
“批准调拨并启动 GPU2 N1U（建议）”. This review verified the artifacts and their
source enforcement, not the original external conversation. The current session
has not independently issued a replacement allocation or priority instruction.

The external source at `4170aeb52c029be17bf31b2933ad6e5a62b02cb3` and its state
both implement baseline11/development122/validation60/formal40/recovery7;
source bytes match that commit. W source/state still have the original caps.
Thus the two local contracts disagree. W's stale larger baseline/recovery caps
must not be used to override the recorded allocation. This review neither adopts
new caps into W nor treats W's old counters as authority to reclaim them.

The manifest-bound wrapper holds the *same real runner lease for all 30 cells*,
not just each child. W and external lock paths resolve to the same device2051,
inode27280417. `/proc/locks` reports a write flock owned by PID2922757; its
start_ticks8189893 and boot2a1fa95f-ab0d-488c-a298-fc488ddd2af7 match the
coordination record. No lock was acquired or process interrupted during review.
GPU3 being idle would not make that lease or its budget allocation available.

## Capacity consequences

| Bucket | Current metadata usage | W unchanged cap | Approved external cap | Unused under external allocation |
| --- | ---: | ---: | ---: | ---: |
| Baseline |11|20|11|0|
| Development |93|100|122|29, committed to the remaining N1U cohort|
| Recovery |7|20|7|0|
| Validation |0|60|60|60 protected|
| Formal |0|40|40|40 protected|

The metadata shows111 dispatched and15.441015923040702 settled GPU-hours.
The parent-reported dispatched child is in flight; settled hours are not its
final cost. The lease holder was independently verified. This review did not
inspect its episode outcomes or attempt payloads.

Neither N4's frozen four-baseline/eight-development originals nor the proposed
five-baseline/seven-development variant fits the approved allocation. Moving
one Q0 control to baseline was a legitimate *old-cap conditional* possibility;
there are now zero unused baseline slots. Four allowed N4 recoveries cannot
be treated as allocated when no recovery slots remain. Candidate episodes
cannot be renamed baseline, and protected or recovery capacity cannot silently
be borrowed. No historical row may be relabeled.

If the approved N1U cohort dispatches all30 originals from its110-attempt start,
the totals will be140 attempts: baseline11/development122/recovery7. Exactly
100 global slots then remain, all protected for60 validation and40 formal
originals. Unprotected attempt capacity is zero even if GPU-hours remain.
Waiting for the current queue to finish therefore does not itself make N4 fit.
If it closes early, unused development slots and hours must be recomputed after
all costs settle; early closure does not automatically reverse the approved
transfer or grant this session priority.

## Concrete decision boundary

The safe current action is to respect the existing whole-cohort lease and retain
N4 as an unlaunched, resource-blocked prospective design. CPU/source work within
the existing scope can continue. Do not launch a competing GPU3 queue, change
source/state caps, pause an external child, or use its scientific outcomes.

Running N4 would require a coordinated, explicit resource/priority decision
that allocates enough *still unused* baseline/development/recovery capacity and
GPU-hours to its fixed matrix and resolves the remainder of N1U at a clean
shared boundary. Such a decision must preserve already dispatched costs and
protected evaluation reserves; supporting both cohorts beyond the remaining
unprotected capacity would require an explicit budget/scope change, not an
inference from the request to continue on GPU3. This memo requests no routine
analysis approval and does not itself authorize a reallocation.

After any approved resolution, freeze one consistent cap/priority contract,
refresh authoritative journal and healthcheck costs under the real shared
lease, and admit the whole proposed matrix with full1800+40-second per-attempt
headroom and all original global/bucket/protected gates. The N4 prerequisite
read, implementation, plan freeze and dispatch remain separately contingent;
none occurred in this review. The N4 protocols remain unchanged and their exact
current hashes are retained in the companion evidence.

No tests, GPU calls, model/provider/simulator work, scientific payload reads,
credential access, W/external edits, ledger updates, or process interventions
were performed. Verification used source/AST/hash checks and allowlisted
resource/proc metadata only.
