# Conditional protected evaluation tooling

CPU preparation only. No actual validation/formal report, model, CUDA, simulator,
provider call, allocation, state write or dispatch was used to develop these
files. The live Dev worktree/source remains unchanged. Integrate only after the
current Dev cohort closes; CPU tests and this commit do not promote N2.

## Frozen authority and source boundary

- `protocol-v1.md`: `75766ff02c4722c25f772e647937fc68cf9a3361129791585430115595f0e8fa`.
- `budget-entry-clarification-v1.md`: `9b1ccf9932f8fe2bf637d0e2a4674fae866740424ef523d83d665bac8c14c77c`.
- Original seed plan remains `9bbcf7107f6be4f739870a034ea84c4695819bdc1bffe5aa1148f453acf4a6b1`.
- Dev promotion reuses the frozen independent reporter, SHA
  `8299647ed0ec904e230058a96a8d0b2d2714e2a3879341ea6917416093c3dfe2`,
  plus its explicit SHA-bound original/revision plans, authorization, raw
  terminals, complete audits, compute and metrics. No generic legacy summary.

The exact permitted runtime tooling map is `qd_ed_n2_evaluation.TOOLING`:
`qd_ed_final_runner.py`, `qd_ed_available_gpu_queue.py`, the three new evaluation
scripts, `n2_evaluation_profiles.json` and the two protocol documents. All other
Dev `code_files` must still exist with identical hashes, including algorithm,
Stage, action, model, environment, perception, collector and auditor bytes.
Tests/docs are separate commit evidence, not permission to change production.
The isolated R branch predates the integrated N2 core; it deliberately does not
replace that core. Integrate only these files, then verify the production map.

## Closed plans and later reviewed release

Run these commands only in the subsequently integrated authoritative worktree,
using a committed tooling HEAD and an explicit selected frozen Dev plan:

```sh
CUDA_VISIBLE_DEVICES='' python scripts/qd_ed_n2_evaluate.py prepare \
  --dev-plan /absolute/frozen-dev-plan.json --phase validation \
  --source-head FULL_COMMITTED_HEAD --output /owned/new/validation.unfrozen.json
python scripts/qd_ed_final_runner.py validate-plan \
  --plan /owned/new/validation.unfrozen.json --allow-unfrozen
```

`prepare` does not access protected outcomes or alter the fixed seed plan. It
copies c1 b1 then b2, task0..9, C0/Q0/N2 (60 originals), or formal task0..9 with
C0/Q0/N2/N2_QD_OFF (40 originals). All phase flags are false. CPU-compose all
commands/overrides and freeze source/runtime/model/native inputs before release.
A separate root-reviewed immutable certificate is required. Merely editing a
phase flag, report pass boolean, first-three checkpoint or candidate label fails.

Certificate schema `qd-ed-n2-evaluation-promotion-v1` requires `target_phase`,
`target_binding=e.binding(plan)`, `candidate_fingerprint`, both protocol and
budget-clarification SHAs, and SHA references `report` and `review`. Every
reference is `{path, sha256}` under the owned artifact root. The scientific
review schema is `qd-ed-n2-scientific-review-v1`, binding that exact report and
fingerprint, all four `CHECKS`, and nonempty `evidence_by_check` references. Root
must actually review numerical/action integrity, unchanged source/compute, raw
Stage separation and substantive QD activity; the observed activity counters
alone do not prove effectiveness or justify a scientific approval.

Admission recomputes full30 Dev or full60 validation and compares the complete
attempt inventory and preserved terminal fields with the authoritative journal.
Validation needs N2 >=5/10 and >=controls; formal release needs validation N2
>=10/20 and >=controls. Audit failure, missing data or partial denominators cannot
release either phase. c1 exposure is rechecked under the real lease before first
allocation and on later admissions. A changed/exposed cohort needs a new
prospective decision, not an automatic seed substitution.

After root release and normal external freezing, dispatch only through:

```sh
python scripts/qd_ed_n2_evaluate.py run --plan /owned/frozen-phase-plan.json \
  --episode-key EXACT_FROZEN_KEY --status-path /owned/new/queue-status.json
```

Repeat `--episode-key` in frozen order for an authorized sequence. The entry is
restricted to W, holds the real shared flock across the 120-second GPU3 idle
window, reuses the existing boot/UUID/native proof and owned-PID Xid monitor,
and calls the original runner then the unchanged CPU auditor. It does not run
an extra probe, rewrite a terminal or create a retry. Missing/incomplete audit
stops later dispatch after original accounting. Generic queue/runner entry
rejects evaluation without the current PID/thread/plan/monitor/lease scope;
generic hardware binding also rejects evaluation before probing.

The formal candidate latch is atomic under the state lock and persists across
restart/recovery. No second candidate or production fingerprint can replace it.
N2_QD_OFF changes only archive mode to none, retaining Q8, inactive sparse parent
setting, the full ED loop and raw Stage. Formal numeric acceptance is N2 >=5/10
and >=C0/Q0. The ablation comparison is fully reported without an invented extra
superiority threshold; a tie does not establish a causal QD benefit.

## Recovery and accounting

At most4 validation or2 formal recoveries, at most1 per cell, bounded by the
remaining global recovery slots and240/48 totals. A root immutable
`qd-ed-n2-evaluation-recovery-v1` certificate binds `retry_of`, exact
`frozen_identity=e.binding(plan)` and the complete original terminal reference.
The appended row retains the original identity/1800-second timeout, changes
only key, recovery bucket and certificate/link fields, and includes
`n2_evaluation_recovery_contract=e.binding(plan)`. No automatic certificate or
retry creation is implemented.

Eligible cases are narrowly checked: exact Codex transport-invalid completion,
exact external GPU3 occupancy abort, or the structured15-second metadata monitor
timeout. Valid failure, ordinary episode timeout, identity drift, algorithm or
numerical failure, unknown CUDA/kernel/Xid cause, and missing audit are excluded.
The original `valid/outcome_valid=false` transport event is preserved. Owned-PID
attribution alone does not establish that a native fault is infrastructure.

A verified per-row budget capability changes only which hour reservation is
excluded: an original or certified recovery can use its own phase hours and
unprotected slack. Raw recovery buckets, counts, healthcheck charges, original
60/40 slot reservations and the48h/240 ceiling are unchanged. The helper's old
behavior is unchanged without this explicit capability. Every admission needs
the full1800+40 seconds; dedicated entry rejects clipping. The14h/10h reservations
are minima, not additional phase caps. Formal still protects any unused
validation reservation until the separate explicit release below occurs.

`e.prepare_reservation_release(...)` only returns a proposed existing
`gpu_hour_reservations_changed` event; it never appends it or changes state.
Inputs: formal plan/certificate, full episode/resource journals, root/runner,
`healthcheck_inventory` SHA reference, rationale, time. Its explicit
`qd-ed-settled-healthcheck-inventory-v1` JSON contains `resources`, one
`{resource_id, terminal:{path,sha256}}` per raw health resource. Every terminal
must exactly match the authoritative settled resource event. Unrecognized,
missing, inflight or malformed costs reject. A genuine full60 passing/audited
validation certificate is recomputed; wrong phase, partial/failing validation,
unsettled episodes or prior formal allocation reject release.

The proposed event binds the formal identity, certificate, both settled journal
prefixes and their SHAs, the exact raw budget snapshot and the explicit health
inventory. Only root may later append it under the real locks and atomically
update mutable state to validation=0/formal=10; no such action occurs here.
`e.verify_reservation_release(...)` accepts only the exact completion-bound
ledger event/state pair, even after new later formal costs are appended. It
never silently overrides reservations in memory.

## Reports and remaining review

```sh
CUDA_VISIBLE_DEVICES='' python scripts/qd_ed_n2_evaluation_report.py \
  --manifest /owned/reviewed-input.json --output /owned/new/report.json \
  --execute-reviewed
```

Input schema `qd-ed-n2-evaluation-report-input-v1` binds this report script SHA,
protocol SHA, explicit base/revision plan references, and `attempts` with the
same terminal/audit/compute/metrics references as the frozen Dev reporter. Cell
identity additionally includes the seed block; no two-block/task collapse.
Every original/recovery terminal and episode cost remains represented. Shared
health costs remain in the authoritative global ledger/budget snapshot; prior
proofs are reused references, never charged a second time. Missing/invalid cells
stay Unknown; complete 20/arm or10/arm denominators are fixed. Reports do not issue
release authority. For ablation only, the metrics adapter validates Q8 as N2
while independently requiring archive inactivity; deployed N2 activity review
remains mandatory.

Synthetic tests use temporary fake evidence and the real frozen reporter code,
not actual protected results. The existing production regression
`test_n2_full_loop_native_raw_stage_and_cpu_call_budget` (archive grid/none,
fp32/bf16) in the N2 core worktree covers176/11 and raw Stage behavior. Root must
rerun that relevant integration test after combining tooling with the unchanged
production source; no core copy or GPU test is included here. Engineering CPU
checks cannot guarantee future model/provider/runtime success or scientific
promotion. Plans must remain closed unless all prospective evidence passes.
