Independent B5 disposition: **PASS_PREPARATION_REQUIRES_ROOT_RELEASE**.

Exact leaf 15.6 preparation at source `4347951a24b63cdb7f0c8a585591d89f1be778ae` passes this independent CPU review. There are no identified preparation blockers. Release remains disabled; production parent attestation and worker receipts remain future. Score: null. Target met: false.

Reviewed authority-bound inputs:

- Plan SHA-256: `b16a5298e9c1b14b4ce129118ef59c744ab713dbddbe8ba47b5693c76d19547e`.
- Disabled bindings SHA-256: `50b2862a553d26a8e009e7a5f067c21cdf56fa15f04afa2bfd81f7ddc3ecf6c1`.
- Controller review SHA-256: `217f6a59371383ef7b724dbf6322dad91a993a4fa177d555df158b41681321ff`.
- Exact admission-consumable [b5-review-v1.json](b5-review-v1.json): `3f833d9adb2e3e2cce85e80efb21a6c216f74872e5d21d18be648a8b995d2e50`.

The production admission consumer requires whole-dictionary equality. Use the B5 sidecar as `plan.b5_review`; this explanatory report includes additional fields and is not that consumer document. The sidecar has schema `n36r3-independent-b5-review-v1`, the exact ten `admission.BINDINGS`, `worker_receipts_are_future=true` and `release_enabled=false`. Its actual independent-review consumer passed using an in-memory reference; no prepared binding was altered and no root governance was synthesized.

Checks and findings:

- **B5-01 (verified_preparation):** Authority hashes match exact 001410 plan and bindings. All ten admission.BINDINGS are identical, source/scientific_source equal commit 4347951a24b63cdb7f0c8a585591d89f1be778ae. Source verifier checks 1100 committed files and registered dependency pins; tracked source clean.

- **B5-02 (verified_preparation):** All 40 externally hashed expected manifests exactly equal production bridge recomposition: task-major Dev tasks 0..9, C0/Q0/N34/N36, fixed seeds/init/BDDL identities, 720 steps, 20Hz, horizon 8, exclusive arm modes and bindings. No protected outcomes inspected.

- **B5-03 (verified_preparation):** Prospective runtime API validates 6767 modules, bound interpreter/distribution versions, generated rule and alias contract. 3300 runtime files and 75 native libraries validate by passive hashes. Generated template commitment and native inventory unchanged. required_after exactly preserves generated remote module, OSC, T5, SigLIP and _cyutility; observed-loaded-after remains false.

- **B5-04 (verified_preparation):** 001407 accepted repair is precisely two production caller additions plus two test files. Both callers now pass verified release_ref, validated plan runtime_closure, live w.process_identity(), runtime_before into unchanged runtime_receipt_binding. Health validates then attests before reservation; episode validates then attests before locks/admission. Source-only bootstrap, live frozen alias checks and receipt checks are unchanged.

- **B5-05 (future_execution_requirement):** Exact production parent runtime attestation was NOT executed. Both real release validators reject this exact disabled plan with N36R3 draft only; separate root bindings required, before reading a release or reaching parent attestation. No synthetic authority, accounting, release or successful receipt was constructed. Bound-interpreter CPU verifier execution is not production source-only bootstrap evidence.

- **B5-06 (verified_preparation):** 001410 ROOT_REVIEWED controller reference passes production verify_semantics; inherited instance, semantics, source and substantive evidence findings unchanged. 001408 draft-controller rejection is retained history and is resolved for this manifest by the authorized 001410 static review. Physical gain remains uncertified; actual production controller instance evidence is future.

- **B5-07 (verified_preparation):** Lexical owner remains admission.OWNER; isolated execution remains admission.SOURCE. GPU7/UUID routing unchanged. No owner/source routing substitution, owner adoption or journal writes. qd_ed_n36_prepare emits disabled manifests; qd_ed_n36r3_preparation emits disabled preparation only, with no spendable balance or release.

- **B5-08 (verified_preparation):** Exact 001410 refresh differs from 001408 draft only in controller_semantics, artifact_root and expected_manifests. Relative to accepted 001358 plan, scientific identities, protocol/review/accounting references, limits, worker contract, STOP authority and deadline are unchanged. Runtime delta is exactly two callers plus source/predecessor preparation metadata; no native/generated/required_after contract drift.

- **B5-09 (future_execution_requirement):** supervisor.reconcile returns PAUSED_FOR_ROOT_G3 after the first valid task-0 C0 terminal, requires a single group and rejects subsequent dispatch; no plan field overrides it. Invalid terminals stop. Fresh worker evidence must prove same PID/boot/start/context, immutable before/after observations, Main execution, monotonic compiled/native inventory, required_after, stable generated identity, real controller and generic/native/CUDA audits. No later-cell continuation plumbing is approved.

- **B5-10 (verified_preparation):** Scientific gate remains complete 40-cell Dev evidence with N36 successes >= max(5,C0,Q0,N34), followed by mechanism and independent review. CPU checks cannot satisfy it; target_met remains false, score null, validation/formal unauthorized and HTTP counters Unknown.

- **B5-11 (consumer_contract):** admission.independent_review uses whole-dictionary equality. b5-review-v1.json contains exactly schema, decision, ten BINDINGS, worker_receipts_are_future and release_enabled; actual consumer accepted it in a disabled in-memory plan view. This richer report is explanatory and MUST NOT be supplied as plan.b5_review. Source adoption must reference the exact sidecar hash.

Commands and results are retained in [checks-v1.json](checks-v1.json), [supplemental-checks-v1.json](supplemental-checks-v1.json), and the reproducible verifier scripts. The initial run used the bound interpreter, CPU affinity [0,1], two-thread limits, a 300-second CPU cap and 420-second wall alarm. It produced 18 passes and one retained comparison failure. Four supplemental checks passed and resolved only that comparison; the 40-manifest, runtime and native checks were not repeated. Both real release validators rejected the disabled plan before attestation. No production caller, source-only bootstrap attestation, GPU, provider query or runtime health ran.

Required next stages (execution blockers, not failed preparation checks):

- **R1 — root_governance:** Root review this exact B5 and create fresh n36r3-source-adoption-v1 approved record binding all ten unchanged BINDINGS, exact lexical owner_root/source_cwd and b5-review-v1.json hash. Prior 001361 adoption is continuity only and does not approve 4347951.

- **R2 — root_accounting:** Root reconcile owner state and all three journals under authorized locks, preserve retained 505 attempts/75.52725286641478 GPUh baseline and every subsequent legitimate charge/failure, reservation events, 0.23357169027962 margin and protected 32+12 GPUh. Adopt finite accounting/caps separately. This review did not recompute live accounting or claim current spendable headroom. Production preparation arithmetic retains 40 cells, 75600s cohort, 1800s health aggregate, 1840s episode+cleanup, at most 41 health invocations each 60s reserved; aggregate admits at most 30 full health reservations; zero automatic recovery.

- **R3 — health_release_and_parent_attestation:** After valid adoption/accounting and detached root health-only release, use the exact bound interpreter and source-only -I -S -B -X pycache_prefix=/dev/null bootstrap through the repaired actual health parent. Retain any pre-reservation attestation rejection; do not claim prior CPU/source/static checks are successful production attestation. Do not replay the old failed health invocation.

- **R4 — fresh_charged_health:** Separately authorized current idle assigned-device and official current-login provider admission, actual CUDA/EGL/provider health evidence and charged reserved/dispatched/completed terminal are mandatory. Frozen runtime provider_ready/cuda_egl_verified flags are historical; preparation.runtime_ready=false and historical_readiness_is_not_current=true. No health/provider/device query was run here.

- **R5 — first_C0_and_G3:** Root detached episode release must bind successful fresh health terminal. Real episode parent and worker receipts remain future. Enforce STOP/deadline, exact accounting and full time headroom. Run at most authorized first C0 and pause at PAUSED_FOR_ROOT_G3; root must reconcile real Main/controller/native/process/receipt/cost evidence and separately review continuation before any later cell. Deadline 2026-10-11T11:13:13Z unchanged.

Failure history remains preserved:

- 001334 accepted independent source review preserved; F1-F4 fixture defects and historical real-STOP containment incident F5 retained, not rerun or erased.

- 001340 scoped fixture acceptance preserved: eight distinct cases across v3 (7 pass/1 fail) and v4 remaining case pass; earlier v1/v2 harness failures and v3 failure retained, no single final-source full eight-case rerun claimed.

- 001407 accepted scoped parent-caller repair and retained 239-test evidence preserved without rerun; synthetic governance in those tests is not production readiness; earlier failed setup and health invocation remain failures.

- 001408 initial KeyError ledger_prefix is preserved in its report; supplemental adapter correction is accepted context, not grounds to rewrite its failure. Parent production attestation remains unexecuted; draft-controller gate is historical and replaced only by 001410 root static controller reference.

- This review initially failed an overstrict runtime preparation metadata comparison. checks-v1.json remains intact. Supplemental checks prove only intended source/source_record/historical_runtime metadata changed with false readiness/release preserved; no production or prepared input was modified.

Exact next root action: Root inspect report-v1.json and the exact b5-review-v1.json hash, then separately adopt source/runtime/controller composition 4347951 and reconcile/adopt current owning accounting under locks. Only after those governance records exist may root prepare a fresh detached health-only release and assess real production parent attestation before reservation, then fresh charged health and a separately released first C0 with mandatory G3 pause. Do not replay old health or treat this preparation PASS as execution permission.

Both canonical STOP entries were absent at verification and completion. Deadline remains `2026-10-11T11:13:13Z`. All outputs are confined to this review directory; source, owner state/journals, prepared bindings and older artifacts were not edited. Named prior reviews were used only as bounded continuity context. No protected validation/formal results, credentials, prohibited untracked design document or foreign study were opened. No broad tests or child agents were used.

CPU evidence never proves scientific success. Full hash-bound evidence and commands are in [report-v1.json](report-v1.json).
