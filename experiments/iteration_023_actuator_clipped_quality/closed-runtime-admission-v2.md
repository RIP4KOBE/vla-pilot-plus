# N23 v2 closed runtime preparation

This is a new prospective successor protocol. N23 v1 remains unrun historical preparation. N22's named invalid primary and all its costs remain invalid; this code neither resumes N22 nor pools N22 results with N23. Scientific files, profiles, Stage, decoder, model and controller are unchanged from commit 1bcf888e88181580bfb854b2e7aa1834bf85df99. The single quality delta of N23 versus N7 remains actuator_clipped_provider_v1. No validation or formal launcher is included.

## Authority and finite scope

The four tracked immutable documents are protocol-dev-v2-prospective.md, backend-arithmetic-protocol-v2.md, budget-amendment-v2.md, and timeout-observability-addendum-v2.md. Their exact hashes are constants in qd_ed_n23_v2_contract.py; both original and tracked copy bytes are checked. A root review and a later arithmetic proof are external references, never embedded into scientific source hashes.

The root alone may adopt the already frozen finite amendment. Under existing runner/state locks, it must preserve historical consumed costs and append budget/protected-reservation changes using the existing authoritative ledger mechanism. Required state is max_episode_attempts=478, max_gpu_hours=100, reserved={baseline:51, development:187, validation:180, formal:40, recovery:20}, gpu_hour_reservations={validation:32, formal:12}, exact runner.GPU7_N23_V2_AMENDMENT, active validated private isolation, gpu_pool=[7], max_concurrent_gpu_workers=1, no external hold. The separate state binding is:

```
n23_v2_gpu7_binding:
  scope: N23_CLIPPED_QUALITY_DEV_V2_20260930_and_backend_preflight_only
  user_reply: <qd_ed_n23_v2_contract.AUTONOMOUS_REPLY exactly>
  selected_gpu: 7
  addendum_path: <absolute N23/protocol-dev-v2-prospective.md>
  addendum_sha256: 11a311d46f62c809160ba18b7960c6eb36ad612450601b32998a3d6e21f95e0d
```

There is no automatic adoption helper or budget expansion. Before preflight, the entire remaining 40 primary cells, two possible episode recovery slots, one arithmetic recovery attempt, 22 local GPU hours plus 160 seconds, and remaining protected reserves must fit. A reserved/attempted preflight or Dev under either N23 version consumes the sole arithmetic opportunity. Every error, timeout or interruption stays charged; no new ID bypasses that gate.

Dev contains task-major task0..9 × C0,Q0,N7,N23, exactly the original exposed Dev seeds and input identities. Limits are 40 accepted scientific cells, 42 dispatched episodes, two total recoveries and one per cell, 22 local GPU hours, 1800 seconds plus 40 cleanup per episode. Candidate numerical futility is evaluated only after a complete task quadruple. All40 accepted native-valid cells, N23 at least5 successes and at least each comparator, plus substantive fixed176/11 QD/ED, are required for promotion. Clipping frequency is descriptive; zero clipping in an individual episode is not a veto.

## Predecessor schemas

All refs are exact `{path: absolute_path, sha256: digest}`. Source/status aliases compare their resolved file identity and digest. Root review `predecessor-review-v2.json` has exactly schema=`n23-n22-prerequisite-v2`, source_plan, route, allow_n23_v2=true, nonempty rationale, timeout_observability, and one route-specific reference. `route=valid_aggregate_rejection` adds valid_rejection_review and delegates to the unchanged valid aggregate rejection gate. No generic invalid or invalid_resolved route exists.

The named route is `named_n22_c0_task4_timeout`, adding named_failure_proof. Its exact fields are schema=`n23-named-n22-timeout-proof-v2`, disposition=`invalid_incomplete_not_scientific_rejection`, allow_n23_v2=true, source_plan, source_commit, terminal_status, terminal_result, named_attempt, named_terminal, native_audit, timeout_diagnostic, evidence_files, ledger_closure, prior_cell_audits, native_evidence, owned_worker_absent=true, n22_promoted=false, timeout_observability. Source must be60425750c41c8a46e1102e02e2e4e4d2f97fb242 and the original N22 frozen plan hash30846268778c46f2d9ad25a92abe7869395d3ead218da1a97dbf24fae4d07218. The sole named attempt ends43653a91ead8. Exactly16 prior audited cells and17 settled dispatched attempts are required.

The terminal result uses the real n22-dev-cohort-result-v1 schema with decision INVALID_OR_INTERRUPTED, dispatched17/audited_cells16/planned40, unchanged false invalid/native flags on the last original result row, and an exact status content/ref binding. Prior16 audits remain separately hashed. Ledger closure fields are schema=`n22-terminal-ledger-closure-v1`, ledger, snapshot_bytes, snapshot_sha256, cohort_id, attempt_ids, all_terminal=true, dispatched17, unsettled0, owned_worker_absent=true, source_commit. The reviewed prefix of the owning actual ledger must contain those17 ordered reserved/dispatched/valid groups with original identities and validity; later appended records are allowed.

Evidence keys are stage_events, episode_compute, episode_metadata, safety_events, metrics, resolved_config, results. Only safety_events may be absent; it binds `{path,present:false,sha256:null}` and must remain absent. A present safety file binds `{path,present:true,sha256}`. Never create a replacement empty file in historical output. Native bundle/status/index/compute hashes bind the exact output directory. Root's independent timeout diagnostic must bind the current diagnostic reader bytes and only the named step112 timeout with unknown_token_calls1; original cost/outcome invalid flags remain false. The diagnostic helper independently runs all original validation checks except recording precisely the three derivative messages enumerated in qd_ed_n23_v2_recovery.DERIVATIVE. Its return is not a scientific result.

## Typed episode recovery

Supervisor first journals every returned or newly journaled invalid attempt. Eligibility requires exactly one completed primary, sole timeout/no completion/no agent message, all other Stage calls successful, reconciled non-token costs, native accepted same-worker receipt, exact source/profile/runtime/seed/input identity and no other fault. No interrupted/whole-worker-timeout, missing receipt, semantic/numeric/safety failure, valid failure or failed recovery may retry.

The immutable `eligibility-v2/<primary_attempt>.json` schema is `n23-v2-typed-timeout-eligibility-v1` with cohort_id, primary_attempt_id, episode_key, scientific_row, plan, source_commit, protocol, timeout_observability, terminal, native_receipt, native_report, process, evidence_files, diagnostic, primary_outcome_valid=false, unknown_token_calls=1, retry_budget_bucket=recovery, same_cell_max_recoveries=1. The contract rebuilds and compares this record from measured evidence at admission. The dynamic recovery row changes only budget_bucket to recovery and adds retry_of and n23_v2_recovery_eligibility. Frozen40-row worker context and scientific identity remain unchanged. Once a recovery is dispatched, historical eligibility is rechecked against its pre-dispatch journal prefix. Only the first valid outcome contributes one cell.

Exactly one no-completion timeout may explain derivative token-incomplete flags for eligibility; successful recovery still passes the unchanged normal validator. Original missing candidate/score fields are retained; diagnostic-derived counts remain separate. Reporting derives unknown calls from each terminal's measured logical/usage-complete counters independently of eligibility. Missing or inconsistent counters produce null, never zero. All-attempt token sums are observed partial totals with missing-attempt IDs; accepted-cell, primary-attempt and all-attempt denominators are distinct.

## Review, preflight and Dev activation

First integrate and commit every intended source/test/protocol byte in the owning worktree. Recompute `worker.source_record(root, contract.source_paths(vars(runner)))`, which contains sorted `{path,sha256}` records, commit and canonical SHA. `source_delta` permits only the explicit evaluation/admission files; every actual helper and scientific input remains included. Do not change any source after arithmetic preflight: future Dev must have the exact same commit and bytes.

Root's external `final-source-runtime-review-v2.json` is exactly schema=`n23-final-source-runtime-review-v2`, disposition=accepted, source=<complete source_record>, runtime=<frozen GPU7 runtime ref>, dev_protocol, backend_protocol, amendment, timeout_observability, no_gpu_release=true. This review does not dispatch anything. No provider verification is called for arithmetic admission; it uses existing frozen runtime/input bytes and GPU7 UUID/EGL/probe/ownership metadata. Dev retains normal frozen Codex login, gpt-6-astra, low,180-second Stage transport verification. Poe is never invoked; credentials are untouched.

Prospective CLI from the final owning source (not executed during CPU preparation):

```
python scripts/qd_ed_n23_v2_prepare.py --kind backend --corpus-index <root-reviewed bounded index> --output <N23>/backend-preflight-plan.frozen.v2.json --freeze
python scripts/qd_ed_n23_v2_preflight_admit.py --plan <N23>/backend-preflight-plan.frozen.v2.json
python scripts/qd_ed_n23_v2_prepare.py --kind dev --backend-proof <charged-preflight-output>/backend-proof-reference.json --output <N23>/plan.frozen.v2.gpu7.json --freeze
python scripts/qd_ed_n23_v2_supervise.py --plan <N23>/plan.frozen.v2.gpu7.json --release <N23>/dev-execution-release-v2.json --status <owned-artifact-status-path>
```

The single preflight admission writes exact context schema n23-recovery-attempt-context-v2: attempt_id, output_dir, budget_bucket=recovery, plan, timeout_seconds120, cleanup_seconds40. Its release schema n23-backend-preflight-release-v2 contains plan, source, runtime, limits, attempt_id, predecessor_review. It charges before Popen, executes one bounded arithmetic worker with main.py ownership marker, and reconciles PID/start ticks/boot and actual whole-process wall. All-invalid/missing-proof paths block Dev. A dead preflight can only be explicitly reconciled with `--reconcile-attempt`; never retried.

Actual proof is `{plan,report,attempt_id}`, binding the valid charged recovery terminal, same PID/start ticks/boot, source/runtime, immutable corpus hashes, strict backend arithmetic,120+40 limit and future Dev source. CPU fixtures do not constitute such a proof. Root creates the separate Dev release only after proof/plan validation. Exact Dev release fields are schema=`n23-dev-execution-release-v2`, plan, source_commit, cohort_id, episode_keys=<ordered40>, physical_gpu7, limits=<contract.LIMITS>, timeout_observability, validation_authorized=false, formal_authorized=false.

All four arms use the unchanged same-process runpy main wrapper and native audit before process exit. Only N23 uses CUDA arithmetic audit. The entire worker, including audit, is metered and subject to1800-second timeout. Supervisor reads hashed receipt/report JSON; no second CUDA audit process exists. Missing or rejected receipt invalidates the charged attempt.

## CPU-only review artifacts

Non-executable Dev/backend drafts intentionally lack prerequisite/root review/backend proof; backend draft also lacks corpus unless separately provided. They grant no authority. Guarded synthetic tests cover real runner terminal shapes, optional safety absence, path aliases, all four arms, journal-before-error behavior, bounded recovery, source/proof closure, failure costs, ownership, unknown token reporting and full quadruple stops. Original failure logs are retained. Actual backend readiness remains unresolved until the one reviewed metered preflight.
