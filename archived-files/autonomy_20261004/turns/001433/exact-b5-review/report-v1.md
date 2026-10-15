# Independent exact B5 review — Arbor leaf 15.6

**PASS_PREPARATION_REQUIRES_ROOT_RELEASE**. No unresolved CPU B5 blockers.

Source: `d01bc1e2e7acc876653a43ddf157d0b4a641f88a`.
Plan SHA-256: `42f1a6fa6f38b3bebcbc851fb00d3a8dbfc019e802b7b4a6f48394c3513d14ee`.
Bindings SHA-256: `9e87b3645b37234c3c22d16952ff6b94709657bf78d3adc0fd3bb80e944ad074`.
Consumer receipt: [b5-review-v1.json](b5-review-v1.json), SHA-256 `a1b807abeb43e1c84d5f778b93bcb48614a199655c92d97f36de5e0e8c58b42f`.

Use the standalone receipt for `plan.b5_review`. This detailed report contains extra fields and is not the exact-equality consumer object.

Score: null. Target met: false. Release enabled: false. Worker receipts are future. CPU evidence never proves scientific success.

- **EXACT_INPUTS**: Authority byte/hash bindings verified; exact source HEAD d01bc1e2e7acc876653a43ddf157d0b4a641f88a and tracked source clean. All ten admission.BINDINGS equal exact plan and disabled binding bundle.
- **MANIFESTS**: 40/40 regenerated in memory using production manifest API and compared byte-bound JSON equality; 10 each C0/Q0/N34/N36; task-major dev identities, seeds/init/task hashes, modes and schedule unchanged.
- **RUNTIME_DELTA**: 3300-file runtime inventory and 6767-module closure checked. Only release.py runtime file/module hash changed from accepted 001422 target; runtime preparation source/source_record/historical_runtime pointers refreshed. Three repaired production files and one test file present in exact source. Generated/native/required_after/controller semantic fields unchanged.
- **ACCOUNTING_REPAIR**: Exact retained arithmetic now accepts 75.53031173955723 and rejects old 75.52725286641478. New fixed preparation identity matches refreshed health policy. Accepted 001426/001428 19-test result preserved without rerun. No live accounting adoption claimed.
- **CONSUMER_RECEIPT**: Exact standalone b5-review-v1.json accepted by production admission.independent_review using in-memory draft plus receipt reference. Detailed report must not be used as plan.b5_review because extra keys violate exact consumer equality.
- **DEADLINE_AND_RELEASE**: Both canonical STOP entries absent before verification and finalization; exact deadline retained. Draft disabled, all phase authorizations false, worker receipts future, score null and target_met false.

The accepted fixture/source reviews from 001334 and 001340, accounting-health repair/reconciliation 001426/001428, and root controller review 001432 remain accepted within their original scope. Prior 001422 B5 / 001425 root disposition provide continuity, not release authority. Accepted repair tests (19 passed) were not rerun.

## Consumers and remaining requirements

- `scripts/qd_ed_n36_prepare.py`: Preparation emits disabled drafts and exact manifests. Historical controller inheritance is allowed only as disabled preparation; final target uses root-reviewed 001432 proof, checked independently through verify_semantics. No preparation function executed.
- `scripts/qd_ed_n36r3_preparation.py`: ledger_snapshot and arithmetic require repaired exact retained charge. Arithmetic recomputed on supplied bounded snapshot and matches. prepare is a package writer, not authority; not invoked.
- `scripts/qd_ed_n36r3_admission.py`: Exact equality for B5 schema/decision/all ten BINDINGS/future receipts/disabled release. Owner lexical path remains distinct from isolated SOURCE. Authority requires external adoption and finite accounting. live_journals validates exact baseline prefix then permits only bound cohort attempt/health suffix and no reservation suffix. Fixed new preparation identity shared by HEALTH/resource_events; old identity cannot be relabelled.
- `scripts/qd_ed_n36_release.py`: Repaired admission captures n3_local/n3_health from live_journals and uses those for finite cohort accounting. Full events/resources still feed global budget_snapshot and protected limits. Detached health/episode releases require exact root review; bare draft rejection verified. Production transaction not invoked.
- `scripts/qd_ed_n36r3_health.py`: Consumes verified suffix under owner locks; replay forbidden across all prior resources. Fixed preparation ID only before first outcome; max 41 invocations plus cumulative bounds, no abort replay. Global charges retained. reserve not invoked.
- `scripts/qd_ed_n36_accounting.py and scripts/qd_ed_n36_healthcheck.py`: N36R3 branches into distinct reserve/health-release consumer. Health caller requires genuine source_execution.attest before reservation. No alternate ID fallback, provider query or production attestation executed.
- `scripts/qd_ed_n36_supervise.py`: First-C0 terminal veto is unconditional for N36R3 and survives restarts. CPU evidence cannot close G3.
- `scripts/qd_ed_n34_source.py and scripts/qd_ed_n36_build.py`: Passive closure checks source bytes, interpreter/distributions, generated template rules and alias rules. Native manifest API body checked exact 75 files without importing torch/loading libraries; loaded-after receipts remain future.

- **ROOT_ADOPTION_ACCOUNTING** (future_governance_execution_requirement): No source/runtime adoption, owning accounting or current spendable headroom established by this review. Root must bind exact B5 plus admission.BINDINGS and reconcile attempt, health and reservation journals under locks. Supplied accepted snapshot remains prospective; not re-read live here.
- **FINITE_LIMITS** (future_admission_requirement): Retained 505 attempts / 75.53031173955723 GPUh; +40 attempts ->545. Retained margin 0.23357169027962h, finite cohort 21h ->96.76388342983685h conservative total; effective cap 221.08404692669838h; protected 44h; prospective unprotected remainder 80.32016349686153h. Both 41-health invocation and 1800 cumulative seconds apply: 41 full 60s reservations do not fit (2460s); at most 30 full reservations. No cap increase or retry.
- **PRODUCTION_PARENT_AND_FRESH_HEALTH** (future_real_production_evidence): Production parent/import attestation remains unexecuted. Real governance must precede production validators, actual imported source/generated/native/controller evidence and fresh charged GPU/provider health with fixed ID n36_healthcheck_n36r3_preparation_001426. Historical readiness booleans and old health are not current readiness.
- **FIRST_C0_G3** (mandatory_future_root_pause): Separate episode release follows validated fresh health lifecycle. Supervisor returns PAUSED_FOR_ROOT_G3 with next_row=null at valid first task-0 C0; invalid terminal stops. Health reservation also respects this boundary. No continuation override exists; root must inspect actual production/audit evidence and separately review continuation plumbing.

## Checks and preserved failures

The CPU script verified all 40 exact manifests, source, runtime inventory/closure, passive native inventory, controller semantics, owner/SOURCE routing, arithmetic, disabled release rejection and first-C0 boundary. Hash-bound per-manifest results and commands are in [report-v1.json](report-v1.json) and [checks-v1.json](checks-v1.json).

Two reviewer expectation errors are preserved: initial delta check expected admission.py rather than release.py; first followup assumed change metadata contained runtime entries only. Corrected bounded followup verified all four source changes, the sole runtime/closure release.py delta and preparation metadata; production independent_review accepted the exact B5 receipt. No source or prepared binding was altered. Prior reported failures remain embedded in the JSON report.

No production parent attestation, provider query, GPU work, health execution, dispatch, release, adoption, owner journal/state mutation, broad tests or protected-result access occurred. Both STOP paths were absent; deadline remains 2026-10-11T11:13:13Z. Current live accounting/headroom was not established; historical readiness is not current readiness.

## Exact next root action

Root should reconcile and accept this exact preparation-only B5, using b5-review-v1.json sha256 a1b807abeb43e1c84d5f778b93bcb48614a199655c92d97f36de5e0e8c58b42f. Under real governance, reconcile all three current owner journals and retained 505 attempts / 75.53031173955723 GPU-hours, including existing reservation reconciliation; preserve all historical costs/failures and protected reserves. Adopt the exact source/runtime and supply the exact source-adoption, owning-accounting amendment, finite authority and detached health release required by admission/release consumers. Bind current released-plan runtime inventory/seed/run fields without modifying this draft or any old artifact. Then execute genuine production parent attestation and new durably charged health n36_healthcheck_n36r3_preparation_001426; never replay prior health. Only after valid fresh readiness issue a separate first-C0 episode release. Pause at its terminal for mandatory root G3; no later cell, retry or automatic recovery. Recheck both STOP paths and deadline 2026-10-11T11:13:13Z. Any changed reviewed BINDINGS require refreshed exact B5.
