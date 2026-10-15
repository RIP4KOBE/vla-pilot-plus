# N23 v2 predecessor proof schema (CPU preparation; no release)

The stable entry helpers are `implementation/scripts/qd_ed_n23_v2_recovery.py::diagnose` and `implementation/scripts/qd_ed_n23_v2_predecessor.py::gate`. All file references are `{path: absolute path, sha256: byte SHA256}`. `worker.read_ref` permits an existing file through parent-directory aliases but rejects a symlink file itself; use canonical refs from `contract.ref` when constructing new records. Existing result plan/status references accept logical/physical aliases only when resolved file and SHA agree. Root must independently review the helpers and real evidence before constructing these artifacts. No actual data was consulted by executor tests.

Create `<N23>/predecessor-review-v2.json`:

```json
{
 "schema":"n23-n22-prerequisite-v2",
 "source_plan":{"path":"<N22 plan>","sha256":"30846268778c46f2d9ad25a92abe7869395d3ead218da1a97dbf24fae4d07218"},
 "route":"named_n22_c0_task4_timeout",
 "allow_n23_v2":true,
 "rationale":"<root reviewed prospective transition; N22 remains invalid/incomplete>",
 "timeout_observability":{"path":"<N23>/timeout-observability-addendum-v2.md","sha256":"fa0723919c67d0417b101be2a36d9832cfaaf15e4b1c4e0cdfbf61caa43e34c6"},
 "named_failure_proof":{"path":"<root-owned proof file>","sha256":"<SHA>"}
}
```

The proof has **exactly** these fields:

```json
{
 "schema":"n23-named-n22-timeout-proof-v2",
 "disposition":"invalid_incomplete_not_scientific_rejection",
 "allow_n23_v2":true,
 "source_plan":{"path":"<N22 plan>","sha256":"<fixed plan SHA>"},
 "source_commit":"60425750c41c8a46e1102e02e2e4e4d2f97fb242",
 "terminal_status":{"path":"<N22 terminal supervisor status>","sha256":"<SHA>"},
 "terminal_result":{"path":"<N22>/result-v1.json","sha256":"<SHA>"},
 "named_attempt":"rdt-qd-ed-final-20260921T093925Z__n22_dev_t04_c0_20260930__43653a91ead8",
 "named_terminal":{"path":"<named output>/attempt-result.json","sha256":"<SHA>"},
 "native_audit":{"path":"<root independent native audit>","sha256":"<SHA>"},
 "timeout_diagnostic":{"path":"<root saved diagnose result>","sha256":"<SHA>"},
 "evidence_files":{
  "stage_events":{"path":"<output>/eds_eval/stage_events.jsonl","sha256":"<SHA>"},
  "episode_compute":{"path":"<output>/eds_eval/episode_compute.jsonl","sha256":"<SHA>"},
  "episode_metadata":{"path":"<output>/eds_eval/episode_metadata.jsonl","sha256":"<SHA>"},
  "safety_events":{"path":"<output>/eds_eval/safety_events.jsonl","present":false,"sha256":null},
  "metrics":{"path":"<output>/eds_eval/eds_metrics.jsonl","sha256":"<SHA>"},
  "resolved_config":{"path":"<output>/.hydra/config.yaml","sha256":"<SHA>"},
  "results":{"path":"<output>/results.txt","sha256":"<SHA>"}
 },
 "native_evidence":{"files":[{"path":"<relative native evidence path>","sha256":"<SHA>"}],"sha256":"<canonical list SHA>"},
 "ledger_closure":{"path":"<root closure record>","sha256":"<SHA>"},
 "prior_cell_audits":[{"attempt_id":"<one of first16, in frozen order>","report":{"path":"<native audit>","sha256":"<SHA>"}}],
 "owned_worker_absent":true,
 "n22_promoted":false,
 "timeout_observability":{"path":"<addendum>","sha256":"<fixed addendum SHA>"}
}
```

`native_audit` may be the separately saved root audit; it need not be written into the original output. Its actual `episode_dir` and `episode_compute_file` must name the original charged output. `native_evidence` is exactly `worker.evidence_record(output)` (hashes only, no CUDA or model): it binds compute/status/index/all bundles, and is rechecked at entry. `evidence_files` is exactly `recovery.evidence_files(output)`. Only `safety_events` may legitimately be absent: it always uses `{path,present,sha256}`, with present=false/sha256=null for absence, or present=true/current SHA when a file exists. Current presence is rebound at every check; an absent-to-present change fails. No empty safety file is created. All other files remain mandatory hash references. Never alter original attempt files to satisfy references.

The closure record exact schema:

```json
{"schema":"n22-terminal-ledger-closure-v1","ledger":"<actual private attempt-ledger.jsonl absolute path>","snapshot_bytes":123,"snapshot_sha256":"<exact prefix SHA>","cohort_id":"N22_HOLD_LIFT_DEV_20260930","attempt_ids":["<17 ordered charged attempt IDs>"],"all_terminal":true,"dispatched":17,"unsettled":0,"owned_worker_absent":true,"source_commit":"60425750c41c8a46e1102e02e2e4e4d2f97fb242"}
```

Root must establish no owned workers remain and all charges are settled. Later ledger appends are allowed; the exact reviewed prefix cannot change. Actual release separately rechecks budget/owned-work/resource gates, so a past absence assertion is not a fresh GPU admission.

To produce the named diagnostic after reviewing its source, call `recovery.diagnose(final, row16, expanded_C0_profile, unchanged_runtime, vars(original_runner), native_report=<accepted independent root audit>, named_step=112)`. Use the actual original N22 row and source-frozen runner/profile/runtime. The helper executes no model/provider/simulator; it calls the existing CPU artifact validator in private function globals. Only the enumerated token-incomplete, failed-Stage and failed-call-usage derivative checks are recorded; all other validations remain fatal. It returns outcome_valid=false, unknown_token_calls=1 and partial observed-token lower bounds. It preserves original terminal counters and derives canonical counts from metrics, so missing `candidate_evaluations`/`score_batches` on the original invalid terminal are not invented or required. Do not use the diagnostic's intermediate validator return as a valid result.

Then call `predecessor.gate(contract.ref(<review>))` for the complete hash/schema gate. Do not overwrite the N22 status, result, original terminal or budgets. This proof alone authorizes neither amendment adoption nor preflight; final source/runtime review and separate closed admission remain required.

The alternative valid rejection route uses the same common six fields, `route="valid_aggregate_rejection"`, and `valid_rejection_review` instead of `named_failure_proof`. That reference must satisfy the unchanged v1 strict valid aggregate rejection helper. Arbitrary INVALID, `invalid_resolved`, interrupted jobs, missing evidence and failed recovery are not routes.
