# N22 conditional validation CPU implementation

Status: **CPU_PREPARED_CONDITIONAL_NOT_RELEASED**. Final branch HEAD is `9287531163d0016bf4eb2faf15d9c72c3241f998`, following preserved initial commit `ed3a13fdf9cd6d33aeb56cf2872d334798120bb6`, both based on frozen N22 scientific commit `60425750c41c8a46e1102e02e2e4e4d2f97fb242`. Worktree: this variant's `validation_implementation`. It is clean. No source was integrated into active `study_worktree`; no online worker, state adoption, budget amendment, actual exposure reconciliation, release or new protected cohort was launched.

## What is implemented

- Separate prepare/contract/supervise/report route for exactly one N22 protected validation cohort. The full original 60-row b1,b2/task0..9/C0,Q0,N22 matrix is generated from frozen seed identities. Metadata-only first-unused c1..c4 selection considers history, registry, all reserved/dispatched identities, and blocks missing historical dispatch registration. Illustrative c2 is not a release choice.
- Actual 40/40 native-valid Dev promotion plus root reviews are hard prerequisites. The contract binds the fixed Dev plan SHA, actual terminal status, actual existing `n22-dev-cohort-result-v1` report, ordered charged attempts/audits, counts and every guided N22 cell's 176 candidates / 11 score batches / 10 parent rounds. Zero-guided cells are allowed. Actual writer logical execution-symlink paths and canonical review paths must resolve to the same file with identical SHA/content.
- Exact scientific source/profile/runtime preservation, separate validation-only state authorization and external hash-bound execution release. Existing N22 Dev, N21 and legacy validation routes retain their gates. No generic validation or formal launch is opened.
- Existing one-worker GPU7/UUID/EGL/probe, private locks, append-only charge/cleanup rules and 1800+40 timeout are reused. All 60 attempts and the entire remaining 32-hour local ceiling must fit 438/100, validation180 and remaining formal40/12-hour reserves. No retry, substitution, resume, early validation futility stop or automatic amendment.
- Every native checkpoint binds real runner terminal fields, identity/source/plan/profile/runtime/inventory fingerprints, frozen row and actual native audit bytes. Invalid/missing audit stops before the next cell. Native CPU auditing is unchanged; N23 CUDA arithmetic is absent.
- Detailed protected report stores complete cells, matched gains/losses, denominators and all 16 existing N22 cost fields. Separate progress/disposition has no per-task outcomes or arm counts. Promotion requires all60 accepted, N22>=10/20 and>=C0/Q0 and substantive fixed-compute QD/ED. Invalidity cannot be mistaken for valid aggregate rejection. Corrupt adjudication retains raw protected evidence separately.

The exact review/state/release/disposition schemas and prospective root-only steps are in tracked `experiments/iteration_022_hold_lift/validation-runtime-contract-v1.md` (SHA `626607447e335dceabfc8e31c36a50ee553676157344e0a438ffa2cf6a18f453`). There is no actual root authorization artifact supplied by this executor.

## Source and input closure

`validation-source-manifest-v2.json` SHA `1c2d8486ecc6f1727154ced17553b7959992b5440fbe72be95edead19e0d13e2` records all 178 files and final commit. All 170 original files except the explicitly allowed runner remain byte-identical to Dev. The only existing-file change is `scripts/qd_ed_final_runner.py` admission/routing/accounting hooks. Seven additions are:

- `scripts/qd_ed_n22_validation_contract.py`
- `scripts/qd_ed_n22_validation_prepare.py`
- `scripts/qd_ed_n22_validation_supervise.py`
- `scripts/qd_ed_n22_validation_report.py`
- `tests/test_qd_ed_n22_validation.py`
- `experiments/iteration_022_hold_lift/protocol-validation-conditional-v1.md`
- `experiments/iteration_022_hold_lift/validation-runtime-contract-v1.md`

The protocol copy retains SHA `b2e94ebd3a79495a6a12db052ddd8ca6db764f65b2632fa092c31d593cd7c51b`. Frozen baseline manifest `configs/qd_ed_final/n4_observed_baseline_profiles.json` (C0,Q0) retains SHA `9ad91066bc0cf91bc8c79d9b02acbd4b83e5e5a45ae31072b0e92d2221baa54f`; `configs/qd_ed_final/candidate_n22.json` retains SHA `e2e119a364ae06f8e77790c9cf8e859da7c7981d51f2e34cde2b3f4c2676922e`. Runtime SHA is unchanged `8b9aebb5af45ab355f4c03bf7669ed78c50b595185ff1e624ebc180dcca89dd7`. Current Codex login, model, provider/Stage/E2/cache/perception/decoder/checkpoint/action semantics are unchanged. Poe credentials are untouched and not invoked.

`validation-plan.preview-c2-v2.json` SHA `34211891f8003ecbc0379c07cc5f9d482cc98c7ac6156dadf6354221a640a0f7` is a pure illustrative 60-cell draft: frozen=false, no Dev/source reviews, no release. It does not read actual exposure or protected outcomes. v1 manifest/preview remain as immutable initial-commit history.

## Tests and limitations of test evidence

Final inspected, path-guarded regression: **194 passed in 7.23s**, including 91 new validation tests; `validation-cpu-guarded-regression-v3.log` records zero denied data reads. Coverage includes actual-style Dev result/status/source and symlink identity, single guided-cell audit omission, canonical corruption, exact source allowlist and default science parity, full matrix/profile/runtime/Codex/GPU metadata, absent/malformed reviews/authorization/release, fresh metadata/registry/one-cohort gating, full capacity/formal reserve, no retries/prefix identity, journaled exposure and charging, complete reporting and corruption, mocked 60-cell supervisor execution, invalid second-cell stop, resource/probe rejection, and resume rejection. Existing N22 Dev/N21 Dev/final-runner tests cover routing, budget, process ownership and timeout behavior with mocks. `git diff --check` passed. No actual model/runtime/provider/GPU validation was attempted.

Reproducible command from `validation_implementation` (use a new fixture suffix to preserve prior fixtures/logs):

```sh
PYTHONPATH=.. OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -p validation_cpu_pathguard_v1 -q tests/test_qd_ed_n22_validation.py tests/test_qd_ed_n22_dev.py tests/test_qd_ed_n21_dev.py tests/test_qd_ed_final_runner.py --basetemp=../validation-guarded-fixtures-review
```

The guard script and explicit static metadata whitelist are in `validation_cpu_pathguard_v1.py`. `validation-cpu-pathguard-negative-v1.json` records three forbidden reads blocked before file open: isolated ledger, active ledger and a Stage-event path under the physical artifact root. This Python-process guard does not sandbox arbitrary subprocesses; only inspected mocked-runtime tests and bounded git-source fixture operations were run.

**A read-scope deviation remains part of provenance.** Earlier `validation-cpu-regression-v1.log` was 198 passed / 1 failed and is not claimed as PASS. An inadvertently included old N7 continuation test read historical protected journal/recovery/Stage evidence and failed on an already-consumed recovery. The separate `validation-cpu-read-scope-deviation-v1.md` documents files and fields solely from source inspection, limitations, and corrective action. No actual protected success was printed or used to alter science/cohort choice; nevertheless the Python-process read was outside scope. Nothing was changed to make that legacy test pass, and it was not rerun. Earlier logs are preserved, including the first synthetic missing-directory fixture failure (89 passed / 1 failed). Corrected guarded tests do not retroactively erase either failure or the deviation.

## Root integration and remaining blockers

Only after actual Dev terminal promotion: review the full commit range (or cherry-pick `ed3a13f` then `9287531`) into the owning study; recompute the 178-file manifest against the still-frozen Dev source. Create exact external Dev promotion/source reviews, review/apply the pending C1 metadata reconciliation, verify fresh untouched cohort and full remaining budget, and add the separate validation state authorization. Then prepare the exact fixed `validation-plan.frozen.v1.gpu7.json`, independently review/create the root execution release, and use the closed supervisor. See the tracked contract document for full CLI/schema. Adoption/reconciliation/release are not automated here.

Remaining blockers are intentionally mandatory: actual Dev promotion/result, root source review, metadata reconciliation/freshness, complete remaining budget, root state/release and real frozen runtime/GPU ownership validation. The active N22 run is unaffected. Actual integration changes source commit and therefore requires newly generated source review/plan hashes. No validation success-rate claim, formal launcher, independent-layout claim or N23 release follows from these CPU tests.
