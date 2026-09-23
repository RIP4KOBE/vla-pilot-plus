# N3 Dev runner support (CPU preparation only)

This implements the frozen N3 protocol; it does not authorize or dispatch a GPU episode. The existing N2 Dev validator, supervisor and report remain untouched. No future validation/formal adapter is activated. A new `N3_EXECUTED_FEEDBACK_DEV_20260923` matrix has task0..9 × C0/Q0/N3 in that order, identical exposed Dev seed/init rows, common decision observer, exact GPU3 runtime and source, and one real shared runner lease. C0/Q0 retain provider quality. The only candidate profile delta from Q0 is `qd_quality_mode=executed_feedback_v1`.

The builder produces an **unfrozen** plan after integration/commit of core plus this tooling. It verifies every listed source byte against the supplied HEAD, preserves model/seed inputs and the explicit native dependency snapshot, and requires the new feedback implementation, main, tracker, collector/auditor and report sources. It reuses existing same-boot engineering evidence only within its declared scope; it does not call the model or GPU or claim that old engineering evidence validates N3. The supervisor forbids implicit hardware revisions or automatic health probes. Any new preregistered health cost must be declared before the matrix starts; health attribution is part of immutable cohort identity. Prior proof costs are disclosed, never recharged.

Local limits: 30 original cells, at most four prospective infrastructure retries with one per cell, 34 total episode dispatches and 8 charged GPU-hours. Every attempt uses the full 1800-second timeout plus 40-second cleanup reserve; insufficient remaining local/global budget rejects admission rather than clipping the timeout. The existing global 240 attempts/48 hours and reserved 60 validation + 40 formal attempts / 14 + 10 hours override the local allowance. Health checks count GPU-hours, not episode attempts. No actual allocation or reservation event is written by preparation.

## Root integration and freeze sequence

1. Integrate the explicitly reviewed N3 core and these runner files into W. Keep the default-off baselines and all30 production sources identical. Commit once before freezing source/runtime/config evidence. Confirm the source inventory includes any additional module introduced by core implementation (the explicit required list already names `core/qd_executed_feedback.py`).
2. Complete the separately authorized recorded-final-pool CPU activity check. Freeze its report and review into an artifact attestation as below. The historical tracking-validity token is **Unknown**, so this is only conditional mathematical activity; it cannot release the online checkpoint by itself.
3. Prepare from an existing authoritative plan carrying either `observed_pair_prerequisites` or `n2_cohort.runtime_prerequisites.references`, a GPU3 runtime bound to W, and the final full source HEAD:

```sh
CUDA_VISIBLE_DEVICES='' python scripts/qd_ed_n3_plan.py \
  --base-plan /absolute/prior-plan.json \
  --runtime-manifest /absolute/frozen-gpu3-runtime.json \
  --source-head FULL_INTEGRATED_HEAD \
  --recorded-candidate-review /absolute/n3-recorded-review.json \
  --output /absolute/artifact-root/continuation_20260923/n3-dev-v1/plan.unfrozen.json
```

The first draft may omit `--recorded-candidate-review`; admission then fails closed. The runtime/whole model-byte verification, public CPU Hydra previews for all30 commands, prospective root review and existing `freeze-plan` procedure remain mandatory. No script here freezes a plan automatically.
4. Start only the first three keys with the dedicated supervisor and a new status artifact. The supervisor must run from authoritative W; isolated worktrees cannot dispatch. It waits for the real shared flock, revalidates boot/GPU identity/dependencies, reconciles only mutable state counters from terminal journal (never a live attempt), holds that real lease through the idle window and selected jobs, and installs owned PID/start-time/PCI Xid monitoring. The original runner owns process cleanup and terminal cost accounting even on failure.

```sh
python scripts/qd_ed_n3_supervise.py --plan /absolute/plan.frozen.json \
  --episode-key n3_dev_t00_c0_20260923 \
  --episode-key n3_dev_t00_q0_20260923 \
  --episode-key n3_dev_t00_n3_20260923 \
  --status-path /absolute/artifact-root/continuation_20260923/n3-dev-v1/first3-status.json
```

Do not use generic `run-plan` or GPU queue for N3; these reject absent the dedicated in-process lease/owned-monitor scope before GPU/reservation. Source scope is a misuse guard, not a security boundary against arbitrary Python code mutation.
5. Each valid episode is independently audited with the frozen collector auditor; missing/rejected audit stops later rows without changing the raw task outcome or creating a retry. Task0 triplet is a correctness/activity checkpoint, **not a success pilot**. Valid failures count and cannot be repeated. Freeze a source-bound checkpoint review only after actual native past-feedback timing/selection, valid registry instance/generation/target continuity, the separate N3 native-feedback bundle alignment, raw Stage separation, fixed calls/176 evaluations/11 batches, finite action and substantive QD/feedback search activity are reviewed. Append the release reference in a new plan revision (all30 original rows and all scientific/source/runtime/health attribution unchanged), refreeze, then request the remaining27 fixed keys.
6. Recoveries require an explicit appended row, `retry_of`, unchanged full identity, recovery bucket and `n3_recovery_contract=binding(plan,runtime)`. No automatic retry is created. Only exact measured Codex transport invalidation, exact external GPU3 process arrival, or a structured 15-second exclusivity-monitor timeout qualify. Unknown Xid/native failure, identity drift, ordinary episode timeout, nonfinite/action error, incomplete audit, or any scientifically valid outcome cannot qualify. Original terminal events and all costs remain unchanged; checkpoint/report plan revisions must retain every original/invalid/recovery terminal.

## Attestation fields

Both attestations have `schema`, `cohort_id`, `source_commit`, `source_files_sha256` (the `source_identity(plan)` function), `protocol_sha256`, and a nonempty `evidence` list of immutable owned `{path,sha256}` artifacts. These are reviewed evidence bindings, not an automatic algorithm-performance decision.

* `qd-ed-n3-recorded-check-v1`: `passed=true`, `scope="conditional_recorded_final_pool_only"`, `historical_tracking_validity="Unknown"`, plus `changed_recorded_choice=true` **or** `quality_dependent_ranking_witness=true`. Preserve all exclusions/adverse results in the bound report.
* `qd-ed-n3-checkpoint-v1`: ordered task0 `attempt_ids` for the three accepted scientifically valid final attempts (including a legal explicit recovery if used); `runtime_tracking_validity="known_valid"`; `checks` exactly all keys in `qd_ed_n3_plan.CHECKS` set true. Evidence must establish the real online invariants; scalar quality differences alone do not prove changed selected action. No task-success threshold is used.

## Independent public-JSON report

`scripts/qd_ed_n3_report.py` is a new N3 report, copied/adapted from the separately frozen N2 reporter's generic public JSON checks. It never calls N2's validator or changes an old report. It reads only explicit SHA-bound terminal/audit/compute/metrics JSON references, not tensor bundles. Each terminal is checked against its own frozen base/recovery revision; source/runtime/candidate/health identity remains fixed. Invalid terminals are reported with their original status/cost and must not provide metrics/audit inputs.

A root-authorized manifest (`qd-ed-n3-report-input-v1`) supplies `script_sha256`, N3 `protocol_sha256`, `authorization` ref, `base_plan` ref, optional `plan_revisions`, all named `attempts`, `health_resources` in frozen declaration order (`resource_id,scope,terminal:{path,sha256}`), a `journal_excerpt` ref, and explicit `input_scope_complete`. The authorization schema is `qd-ed-n3-report-authorization-v1`, `status="authorized"`, exact `script:{path,sha256}`, `protocol_sha256`, and `base_plan_sha256` plus `journal_excerpt_sha256`. Each accepted attempt reference has `terminal,audit,compute,metrics`; invalid only `terminal`, unaudited valid only `terminal`, rejected audit only `terminal,audit`.

```sh
CUDA_VISIBLE_DEVICES='' python scripts/qd_ed_n3_report.py \
  --manifest /absolute/n3-report-manifest.json --execute-reviewed \
  --output /absolute/artifact-root/continuation_20260923/n3-dev-v1/report-new.json
```

The report keeps pending/invalid rows, all costs, per-episode activity and Unknown reasons, and same-task paired gained/lost tasks. N3>=5/10 and >=C0/Q0 is evaluated only for complete30 valid cells; no chunk independence/p-values or pooling with old cohorts. A numeric pass still does not authorize validation/formal: correctness/activity/global-cost review and a new phase protocol are required.

The root supplies a SHA-bound N3-only authoritative journal excerpt (`qd-ed-n3-journal-excerpt-v1`) with `cohort_id`, `extraction="all_events_all_n3_attempts_through_snapshot"`, `source_journal:{path,sha256}` for W/data/attempt-ledger.jsonl, every N3 `events` record in original order, ordered `terminal_attempt_ids` for every completed group, and `inflight_attempt_ids` for all reserved/dispatched groups without a terminal. The root authorizes that precise extraction SHA; the report does not open other cohorts' journal payloads. It checks exact event order/identity, every completed terminal, and that manifest attempts are exactly the excerpt's completed terminal set. In-flight groups retain identity/dispatched presence with no task-outcome read or success classification; any in-flight snapshot requires `input_scope_complete=false`, complete cost remains Unknown and only settled subtotal is reported. A claimed `n3_episode_dispatched` boolean must match actual `dispatched` presence. Pre-dispatch aborted records remain in `predispatch_records` and all-cost accounting but do not consume a scientific cell/dispatch allowance or satisfy order/checkpoint/validity. Multiple rejected reservations plus one actual original and one allowed actual recovery are supported. The reader never treats omitted invalid/reservation records as harmless.

The N3 scalar report additionally checks native record shape/dtype metadata, the previous selected fingerprint/projection/origin against its earlier guided record, exact eight-ack timing, Stage/provider/registry continuity and known target validity, and the CPU float64 stored residual formula. The newly required N3 native bundle audit plus reviewed checkpoint must prove native tensor byte/value/actual execution association. The prior generic auditor acceptance alone does not establish it. `qd_quality_applicable=true` without history can still have `qd_feedback_active=false`: all11 canonical batches must then retain raw quality exactly. Feedback-active/quality-changed counters do not certify changed selected action or successful execution. Reported `qd_feedback_overhead_seconds` covers the implementation's recorded chunk bookkeeping; full process/episode costs remain authoritative.

The supervisor, following-row admission and independent report now require the frozen `n3-native-feedback-audit-v1` scope and exact `checked_decisions == applicable chunks`, `active_previous_ack_verified == active chunks`, and inactive remainder counts. Counts are nonnegative native JSON integers, never boolean substitutes. All-unsupported N3 can retain a valid task outcome without a native gate, but neither unsupported nor recognized/no-history task0 can release the checkpoint: at least one native-audited actual active decision is necessary. A quality-dependent search witness remains a separate reviewed requirement. An alignment failure saves the original audit plus a separate wrapper failure observation, stops later rows after runner accounting, and never rewrites task validity or creates recovery eligibility.

Before the first N3 dispatch, the source-bound `../accounting-clarification.md` prospectively assigns all10 original C0 rows to baseline, Q0/N3 (20 rows) to development, and all explicit retries to recovery. Split/seed block remain Dev. The plan freezes `budget_allocation` and `budget_allocation_amendment` in its resource identity; the reporter checks each terminal retains its planned bucket. Original 20/100/20 caps, global 48h/240 and protected24h/100 stay fixed; no historical journal event is relabeled. Preserve the old unlaunched plan and prepare/freeze a new path from the newly committed source. Reissue source-bound review/preview metadata with unchanged algorithm/helper fingerprints; do not copy obsolete source attestations into the new plan. Recheck the live budget under the shared lease.
