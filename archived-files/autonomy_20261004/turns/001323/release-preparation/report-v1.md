# Leaf 15.6 — N36R3 release preparation

CPU preparation complete, disabled. **score=null; production_accepted=false;
release_enabled=false; source_adopted=false.** G3 and G4 remain open.

Source: `bb20aedb952638548dd347b9705dab2beba176c5` → `b86ac1291b08ba2b6bf33e7a6e19326016f4c40e`
on `exp/n36r3-generated-import-001299`. Worktree clean. Two commits: implementation and documentation.

Implemented immutable disabled accounting/adoption/release bindings and mandatory
first-C0 pause after durable terminal charge. Restart reconciliation also pauses;
any later cell is rejected. Invalid terminals retain the existing stop behavior.
No approval or resume override exists. Science, seeds, thresholds, Main, receipt
consumer and native/generic audits are unchanged.

Final package: [review-package-v2/package.disabled-v1.json](review-package-v2/package.disabled-v1.json)
SHA256 `99304997d656b03758b3e6de16f258a9cafee806ab24d9c561e07be768e5c401`. All component paths, sizes and SHA256 values,
source file before/after hashes, exact commands/results and current ledger prefixes
are in [report-v1.json](report-v1.json). Package v1 is superseded by v2.

Retained: **505 attempts; 75.52725286641478 GPUh**. No ledger or owner writes.
Prospective: 40 × 1840 + 1800 + 200 = 75600 seconds (21 GPUh), 545 attempts total.
Conservative cost including retained margin and full cohort: 96.76082455669440 GPUh.
After the 221.08404692669838 effective cap and full 44 protected GPUh reserve,
prospective remainder is 80.32322237000398 GPUh; this is not admission headroom.
Health: at most 41 invocations AND 1800 cumulative seconds; only 30 full
60-second reservations fit. Zero automatic retries. Deadline 2026-10-11T11:13:13Z.
Standing authorization is hash-bound; no further user budget permission requested.

Tests: 24 focused passed (1.55s); controller subset plus focused tests 31 passed,
1 deselected (1.63s). Initial run: 30 passed, 2 failed (1.71s). The new fixture
transition was corrected. The pre-existing temporary-STOP-path test fails against
the existing canonical-STOP contract; neither check nor test was weakened.
All tests used two threads and 180-second bounds, totaling 4.89 reported seconds.
Actual package generation, hash checks and disabled direct/forged admission
rejections passed. Synthetic tests do not close G3.

Root's separate adoption/readiness/release commands and requirements:
[root-next-steps-v1.md](root-next-steps-v1.md).

Remaining blockers:

- N36R3 remains explicitly draft-only: separately reviewed authority validation, owner/source routing, finite health accounting and released-plan support are still required. No executable release is supplied.
- Root exact-source review and adoption of complete prerequisite composition into differing owner history remain outstanding; old accepted source/runtime/controller hashes do not attest this new commit.
- Fresh locked accounting/reservation reconciliation and idle GPU7, official current-login Codex gpt-6-astra and CUDA/EGL readiness remain outstanding; readiness ordering needs distinct root-bound finite health authority.
- G3 is open until actual later admitted production C0 evidence is reconciled. Pause has no override: a separate reviewed continuation binding implementation is required after G3.
- Existing tests/test_n36_controller.py::test_full1840_deadline_and_stop fails because it supplies a temporary STOP path rejected by the pre-existing canonical STOP contract. Test and contract unchanged; not hidden or weakened.

No GPU, simulator, Main, provider, network, install, credential access, protected
validation/formal artifact reads, owner state/locks/driver writes or other agents.
