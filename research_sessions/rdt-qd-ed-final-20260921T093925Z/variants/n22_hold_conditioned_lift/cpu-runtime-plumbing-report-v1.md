# N22 matched Dev runtime plumbing — conditional CPU report

Committed as `ef10d49` on the isolated implementation branch, following scientific implementation `960f90e8b097e7f39c9f2fc5a57da3ac9f617e7c`. The implementation worktree is clean. No owning study source/state/ledger/tree was modified; no GPU, provider service, simulator, full model validation, actual frozen plan or execution release was used or created. Integration and actual model/runtime validation remain root-owned after N21 is terminal.

The existing `protocol-dev-v1.md` and `protocol-cpu-v1.md` bytes were preserved and copied into tracked `experiments/iteration_022_hold_lift/protocol.md` and `protocol-cpu.md`. The Dev protocol SHA is `650489b28f8b048b1963cfd7268dc937274a12f33132beabe93d4bc9bde0c295`; the bounded amendment SHA is `11607aa4a056e8defa8c2acafeab5b2270bb18f24ecb7780cb35762e61fe938f`.

## Implemented gates

- New `qd_ed_n22_dev_contract.py`, `qd_ed_n22_dev_prepare.py`, and `qd_ed_n22_dev_supervise.py`; runner support, both E2/180-second transport allowlists, and N22 dispatch/reconciliation markers.
- Exact cohort `N22_HOLD_LIFT_DEV_20260930`: original frozen Dev tasks 0..9, task-major arms C0, Q0, N21, N22; 40 unique cells, baseline 10 / development 30. Original seed/init/BDDL identities are derived from the source N21 plan's SHA-bound seed plan. N21 is an ablation control only.
- N22 plans containing N21 explicitly bypass N21-only contract/scope selection; ordinary N21 plans retain their existing behavior. Mixed stale N21 cohort metadata is rejected by the N22 contract.
- One GPU7 worker with the existing exact UUID/EGL/probe/runtime binding, 40 attempts / 21 GPU process hours, 1800 seconds plus 40-second cleanup headroom; exact private cumulative 438-attempt/100-hour authority with baseline41/development157/validation180/formal40/recovery20 and protected hour reserves32/12.
- No retry of even a previously reserved N22 cell. Every dispatch must follow the complete, valid, independently audited task-major prefix. Any invalid outcome/audit failure closes progression. Protected-hour and local-cap checks remain per dispatch.
- Numeric futility only after a complete task quadruple: candidate successes plus remaining tasks <5. Six initial failed N22 tasks stop after24 cells. Task0 failure does not veto later tasks.
- Promotion only after all40 cells are valid/audited, N22>=5/10 and >=each C0/Q0/N21, and native/metric evidence of active QD/ED with fixed176/11 per guided decision. Quality audits use `n22_hold_lift_quality_audit` for N22 and `n18_lift_quality_audit` for N21. Positive-bonus/ranking counts are reported without a new success veto. An episode with no guided decision can remain valid; a cohort with no substantive candidate QD/ED activity cannot promote.
- The status includes per-arm actual model/reward/Stage logical call totals and GPU process seconds, N21's control-only role, native counts, candidate success tasks and the explicit promotion result. Missing required cost telemetry fails the cohort. Validation/formal stay unauthorized in both plan and release.

`prepare.build_plan()` is pure: it hashes committed source and reads metadata but does not mutate state or query a GPU. It requires the root-owned predecessor review described below. `prepare.main()` additionally checks private authority/capacity/isolation, no active attempt/healthcheck, live GPU exclusivity and UUID/EGL/probe before freezing. The frozen plan binds all scientific source/tests, tracked protocol copies, external Dev protocol/amendment, inherited runtime and the predecessor review.

## Root-owned prerequisite record

Before an actual `build_plan()`/freeze, create `variants/n22_hold_conditioned_lift/predecessor-review-v1.json` only after the relevant N21 terminal scientific review. Exact top-level keys:

```json
{
  "schema": "n22-n21-prerequisite-v1",
  "source_plan": {
    "path": "<canonical SESSION>/variants/n21_stage_raw_reward_binding/plan.frozen.v1.gpu7.json",
    "sha256": "<actual SHA256>"
  },
  "source_status": {
    "path": "<absolute root-owned immutable N21 terminal status or aggregate disposition path>",
    "sha256": "<actual SHA256>"
  },
  "phase": "dev",
  "disposition": "rejected",
  "allow_n22": true,
  "cause_resolved": false,
  "rationale": "<nonempty root scientific review>"
}
```

For a valid Dev rejection, the source status must be `rejected_task0_necessary_gate` or `completed_all_twelve_audited`, with `dev_gate_promoted: false`. For a failed/interrupted Dev predecessor, use `disposition: "invalid_resolved"` and `cause_resolved: true` only after the root documents/resolves the cause; a failed/invalid result cannot masquerade as a valid numeric failure. In-progress or promoted Dev statuses are rejected.

For a later validation rejection, set `phase: "validation"` and point only to a root-produced aggregate disposition with exactly these fields (no per-task protected outcomes):

```json
{
  "schema": "n21-validation-aggregate-disposition-v1",
  "cohort_id": "<actual frozen validation cohort>",
  "aggregate_only": true,
  "terminal": true,
  "gate_passed": false,
  "outcome_valid": true
}
```

A valid aggregate rejection uses `disposition: "rejected"`. An invalid aggregate may use `invalid_resolved` only with `cause_resolved: true`. The contract reads no protected per-task outcomes, and rejects extra aggregate fields. Status paths must resolve inside the private session or its existing artifact root; source plan/status hashes and the predecessor review hash are frozen.

## Exact private authority fields needed by root

`budget.amendment`:

```json
{
  "schema": "gpu7-n22-budget-amendment-v1",
  "proposal_sha256": "11607aa4a056e8defa8c2acafeab5b2270bb18f24ecb7780cb35762e61fe938f",
  "physical_gpu": 7
}
```

Set only the already documented cumulative caps and preserve historical consumed/dispatched values and reservation provenance. `gpu_pool: [7]`, `max_concurrent_gpu_workers: 1`, and resource isolation ACTIVE/PASS/private-budget true are required. `n22_gpu7_binding` must be exactly:

```json
{
  "scope": "N22_HOLD_LIFT_DEV_20260930_only",
  "user_reply": "继续完成满足目标且无需我介入的autoresearch",
  "selected_gpu": 7,
  "addendum_path": "<canonical SESSION>/variants/n22_hold_conditioned_lift/protocol-dev-v1.md",
  "addendum_sha256": "650489b28f8b048b1963cfd7268dc937274a12f33132beabe93d4bc9bde0c295"
}
```

The Dev protocol acts as the new binding addendum; no extra binding file was created. The runtime/probe remain exactly inherited.

The separate execution release schema is `n22-dev-execution-release-v1`, with exact resolved plan path/SHA, frozen source commit, cohort ID, all40 frozen episode keys, `physical_gpu: 7`, `validation_authorized: false`, and `formal_authorized: false`. The supervisor requires a fresh status path and will not resume an existing status.

## CPU verification

Command:

```text
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -q tests/test_qd_ed_n22_dev.py tests/test_qd_ed_n21_dev.py tests/test_qd_ed_final_runner.py
```

**103 passed**, including33 new N22 runtime cases. Coverage includes original ten-task identities, N21 routing/scopes, exact budget and protected/local-hour caps, predecessor phase/hash/invalid distinctions, rejecting protected per-task aggregate additions, order/no-retry/audit/futility admission, task0-fail eventual promotion, ties and inferior controls, positive-mechanism-count absence without an extra veto, no-guided-cohort rejection, invalid/audit/fixed-compute/inactive-QD stops, full contract/profile/fingerprint/phase checks, pure builder GPU isolation, exact release fields, and pre-GPU prepare rejection of insufficient/wrong authority.

These tests use synthetic outcomes and mock runtime inventory/dispatch. The full-contract CPU fixture checks actual source profiles/protocol/runtime metadata but substitutes committed-record and predecessor/state fixtures because no real N21 terminal review exists yet. It does not substitute for root's actual committed-source/model/runtime fingerprint validation after N21 closure. Python compilation and `git diff --check` also passed. Logs and hashes are in `cpu-runtime-tests-v1.log`, `cpu-runtime-collection-v1.log`, and `cpu-runtime-results-v1.json`.
