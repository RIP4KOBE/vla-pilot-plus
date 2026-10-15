# Independent N26 terminal metadata review

This external reader does not change or import the frozen experiment implementation. It reviews the existing immutable result, never writes or repairs it, and never authorizes another GPU dispatch. The expected experiment source is commit `6026794cd5d52f3a5054bf2704ebb3c516f9f47e`, with its original 315-file manifest. Actual evidence remains unread during CPU preparation.

## Root execution prerequisites

1. Wait for the N26 controller to terminate. Preserve its original status, result and every charged attempt, including an invalid final worker. Do not reinterpret engineering invalidity as scientific rejection.
2. While owning source remains 6026794, collect a separately reviewed closed metadata inventory. Root may execute the existing `validate_plan` and original `build_command` for the frozen 40 rows to produce the prerequisite attestation below. This establishes original source/runtime/prerequisite checks; it does **not** certify outcomes, costs or event chronology on behalf of this reader. No model, provider, simulator or native auditor call is part of collection or review.
3. Under the existing supervisor/runner locks, collect current **N26-only** attempt events and the matching one N26 tensor-resource group. Do not include full private journals. Record the full source-journal reference, collection time, count and `all_matching_events: true`, plus the current stat anchor. The source path is statted only, never opened by this reader. Refresh projections after unrelated appends; a full-ledger hash is not a permanent historical-validity condition.
4. Inventory existing public process identities, including the controller, tensor worker and every episode worker. A missing process record is a typed absence and remains Unknown. Record the cleanup attestation below. The CLI independently inspects `/proc` after acquiring both locks and sends no signals. Known boot/start/PID identities and worker session/group descendants are checked; the worktree command scan is supplementary. Missing historical identities prevent `cleanup.downstream_cleanup_gate_satisfied` even if no matching command is currently visible.
5. Root authorizes the concrete manifest only after reviewing the external source hashes and metadata scope. Ensure the existing `N26/execution/` and both lock files already exist. Invoke the reader from its own directory with normal Python script import semantics. No study `scripts/` import or import-path adjustment is required.

The CLI requires owning `study_worktree`, takes the existing `N26/execution/supervisor.lock` and `study_worktree/data/qd-ed-runner.lock` nonblocking, and writes only `N26/root-terminal-review-v1.json` using exclusive creation. It refuses an existing review. An early malformed input/live process/lock error prints a rejection and exits nonzero without a review file; preserve that command log. Missing original result is recorded as a rejected reconstruction, never fabricated.

## Exact input envelope

`schema: n26-terminal-metadata-input-v1`, `root_authorized: true`, `executable: true`, `source_root` (owning W), `files`, `refs`, `attempts`, and `static_objects`. The disabled example has both booleans false and unresolved references; it cannot run.

Each `files` entry has exactly `{role,path,present,sha256,bytes}`. All paths are absolute; resolved aliases cannot duplicate entries. At most 512 metadata files, 16 MiB per file and 128 MiB distinct bytes are allowed. Size is checked before bounded allocation, and actual bytes/SHA must equal the declaration. Each present file is read/parsed at most once. JSON duplicate keys and nonfinite values are rejected. JSONL is used for metrics/compute and may also be used for filtered events. Final leaf symlinks, tensor/image paths, `decision_evidence/`, raw Stage/native events, and full private journal filenames are prohibited. No nested reference grants read permission.

`refs` must provide typed references for: `plan`, `source`, `runtime`, `source_review`, `source_bridge`, `result`, `status`, `journal`, `current_journal`, `resources`, `controller`, `release`, `precheck`, `proof`, `cleanup_attestation`. A reference is `{path,sha256}`; an explicitly allowed absent file has `sha256: null`, `present: false`, `bytes: 0` and must still be absent. The proof additionally references four inventoried roles `proof_plan`, `proof_report`, `proof_process`, `proof_terminal`.

`attempts` is ordered exactly like journal attempt groups and includes every reservation, including pre-dispatch aborts and unsettled attempts. Each entry is `{attempt_id,refs}` with optional `eligibility` and `recovery_attestation` for an original recovery. Its `refs` contains exactly these nine roles and filenames under that attempt's frozen artifact directory:

| Role | Relative path |
|---|---|
| terminal | attempt-result.json |
| context | n23-worker-context.json |
| command | command.json |
| process | process.json |
| audit_start | eds_eval/in-worker-audit-start.json |
| receipt | eds_eval/in-worker-audit-receipt.json |
| audit | eds_eval/decision-evidence-audit.json |
| metrics | eds_eval/eds_metrics.jsonl |
| compute | eds_eval/episode_compute.jsonl |

Metrics may be absent only under the original zero-guided native/compute/terminal checks for accepted cells. Other missing audit/receipt files are retained for invalid/unsettled attempts and cannot become accepted scientific evidence. The canonical receipt `evidence.files` digest is checked **as metadata**; referenced tensor/index/Stage files are never followed or rehashed. Original same-process native audit integrity is an explicit historical trust dependency.

`static_objects` lists at most 32 `{path,sha256}` Python files, each at most 512 KiB, covering the three delivered reader modules and every external collector/wrapper referenced by attestations. The CLI rehashes these and all original 315 study files, without importing them. Root owns provenance of the commit-to-manifest mapping; the reader independently verifies all supplied manifest bytes and actual current files.

## New root-authored metadata schemas

These are prospective collection records, not claims already established during CPU preparation.

* `n26-terminal-prerequisite-attestation-v1`: `source`, `plan`, `runtime`, `source_bridge`, `proof` references; `source_commit` 6026794; `source_files_verified: 315`; `operations: [validate_plan,build_command]`; `all_prerequisites_passed: true`; `model_api_sim_calls: 0`; `historical_proof_lineage_verified: true`; `predecessor_current_subset_checked: true`; `collector` reference. `historical_lineage` contains exact refs `predecessor`, `prior_n25_backend_proof`, `prior_quality_proof`, plus `original_n25_disposition: INVALID_OR_INTERRUPTED` and logical N25 disposition `REJECT` or `REJECT_NUMERIC_FUTILITY`. The refs must equal the original final review/source bridge. `command_templates` contains all 40 ordered `{episode_key,argv}` records from original `build_command`, with only the attempt ID replaced by literal `__N26_REVIEW_ATTEMPT__`. Original scientific outcomes are not attested here.
* `n26-current-terminal-journal-projection-v1` and `n26-current-terminal-resource-projection-v1`: `cohort_id`, `events`, `event_count`, `all_matching_events: true`, `source_ledger` ref, `source_ledger_stat: {size,mtime_ns,inode}`, numeric `collected_at`, `collector` ref. The first equals the immutable result's filtered journal snapshot. The second contains exactly the original tensor resource's reserved/dispatched/completed events. Completeness is root-attested; the reader verifies visible events and compares stat anchors before/after its locked read.
* `n26-original-typed-eligibility-attestation-v1` (only if a recovery exists): exact `eligibility`, `source`, `plan` refs and `primary_attempt_id`; `method: original_frozen_controller_and_classifier_metadata`; canonical `classification_basis_sha256`; `root_verified_original_basis: true`; `stage_and_tensors_reaudited_by_terminal_reader: false`; `collector` ref. The reader independently binds the original typed record, primary terminal/receipt/report/process, reader source identities, three exact derivative failures, observed counters, episode identity and unique first-valid retry. It relies on root attestation of the frozen classifier's actual execution and restricted Stage/tensor basis; generic `True` without the bound record is insufficient. No recovery implies no recovery attestation is needed.
* `n26-terminal-cleanup-attestation-v1`: `plan`, `controller`, `current_journal`, `resources` refs; `expected_processes` maps `controller`, `proof`, and every attempted ID to `{pid,proc_start_ticks,boot_id}` or null; `all_owned_processes_inspected: true`; `collector` ref. This is collection provenance, not a substitute for CLI `/proc` checks. Null never proves historical cleanup.

The existing controller schema is `n26-root-controller-process-v1`: nested process identity, `source_commit`, plan/release/entrypoint/wrapper refs, physical GPU 7 and `one_launch: true`. Existing episode terminals do **not** have `cleanup_complete`; no such field is invented. The tensor resource terminal does have it. Original N26 plan carries `n26_cohort.final_review`, **not** `n26_cohort.source_bridge`; source bridge and actual same-source arithmetic proof are reached via the final source review.

## Independent decisions and costs

The reader checks global contiguous task-major cell order, sequential timestamps/group chronology, at most two typed whole-episode recoveries and one per cell, full original identity/source/runtime/profile fingerprints, first-valid selection and all visible cost categories. Any later reservation after the first hopeless complete task quadruple is a protocol inconsistency. Counts never substitute zero for missing telemetry. Failed/reserved attempts retain measured wall time and partial/unknown provider usage; unsettled cost stays Unknown and reconstruction cannot be accepted.

Promotion requires all 40 valid audited cells, N26 at least 5/10 and at least each control, with substantive QD/ED. Zero gradient is legal and never an activity or success gate. C0/Q0 provider-mode serialization omission is preserved. Native gates remain profile-bound, including zero-guided N26; deleting all N26 markers cannot downgrade evidence to N25.

The frozen supervisor checks futility also after cell 40, but the frozen writer prioritizes full-40 `REJECT` before its status consistency check. Therefore a first futility at cell 40 can yield original result `INVALID_OR_INTERRUPTED` with `journal_reconstructed_disposition: REJECT`. The external reader reproduces that disagreement and never silently certifies valid rejection. It does not modify either active module.

A shorter status prefix after a valid journal result retains both prefixes, all journal costs, and INVALID disposition. Free-form original exception text is preserved, not independently re-attributed to transport or native causality. Pure `reconstruct` does not observe process cleanup; only CLI output adds the independent cleanup observations. Even accepted reconstruction is not downstream release, and missing historical PID remains an additional closed gate.

## Future root command (not authorized by this delivery)

```bash
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python /ABS/N26/terminal-review-preparation-v1/terminal_reader_v1.py --input /ABS/ROOT_AUTHORIZED_METADATA_INPUT.json --output /ABS/N26/root-terminal-review-v1.json
```

Use the exact real paths from the reviewed closed manifest; do not run the disabled template. Preserve the original result/status, new immutable review and complete CLI log. Source/runtime/proof history is read only as metadata; no model, API, simulator, CUDA, tensor audit, automatic retry, result repair, protected validation or formal dispatch is enabled.
