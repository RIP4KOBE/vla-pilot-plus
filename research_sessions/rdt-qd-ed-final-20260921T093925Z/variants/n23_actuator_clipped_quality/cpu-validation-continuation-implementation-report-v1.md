# N23 conditional validation continuation-evidence preparation

Prepared and frozen at `5c7aa990b30410c3240867059b5776cfcef9dd4e` in the isolated `validation_implementation` worktree, branch `codex/rdt-qd-ed-n23-validation-20260930`. The checkout is clean. This is CPU preparation only: no actual promotion/result/status was read, no validation was released, no GPU/API/simulator was invoked, and no owning source, active continuation, state, ledger, budget or lock was changed.

The only change from prior reviewed preparation `89aea3b` is the prospective evidence entry specified by addendum SHA `536c4508cdf21fdf59a86acdbd83ab2f8fc45b99c9e14e9b1a4bdf35329d484c`. Original scientific protocol SHA `b202e2bf03e13ea4d66fdd355f7959bbb40f264aeb3c9bd37f57959efdc63615` remains exact. The validation matrix, thresholds, freshness rule, 60+2/32-hour local allowance, original478/100 cumulative caps, recovery rule, single-worker ownership, provider/Stage/science/arithmetic, validation supervisor, report and recovery code remain unchanged.

The entry now requires `result-continuation-v1.json` / `n23-dev-continuation-result-v1` and its actual `supervisor-status-continuation-v1.json` / `n23-dev-supervisor-status-continuation-v1`, produced by the exact external reader SHA `93143e94b06802f2f681380f040b7e52b66b2c675c4fe3e3d3955fc441c0ec12`. It verifies the reviewed external eight files at historical commit `dd27e77edd5e8d67aba998c1d0441c2b8e48713c`, original imported writer, frozen manifest, actual source/authority/root-review hashes, launch process witness, and original failed v2 result/status. The original three valid failures and their exact identities/evidence/costs are preserved. `prefix()` receives only the filtered original Dev-cohort journal, not all historical groups.

The historical helper never calls the live continuation controller or asks the later evaluation worktree HEAD to equal5110447. It verifies original5110447 source/ref through the existing explicit source bridge and historical receipts, while independently checking external committed bytes with `git show dd27e77:<path>`. The historical N7 adapter is a byte-for-byte copy of the reviewed adapter, SHA `fc98d401fb6095fb0a4311fa2de5e04d9940b6f5406e96078ba3b350168821c5`. Only omitted legacy provider-mode N7 evidence is interpreted this way; explicit wrong/null modes remain fatal, and N23 native checks remain unchanged.

All40 first-valid scientific cells remain required in exact order, with original Dev snapshot and accepted metered backend proof. Counts, native and auxiliary totals, every primary/invalid/recovery cost and denominator are recomputed. The top-level GPU-process total and empty unreturned-attempt list must now also match the fully accepted completion. Partial, interrupted, invalid, numeric-futility or stale original-v2 results cannot enter validation. N23 must still achieve at least5/10 and match/exceed C0/Q0/N7 with substantiveQD/ED.

## CPU verification

`cpu-validation-continuation-v1.log`: **167 passed in9.01s**, covering the new provenance/prefix/adapter checks and existing reviewed validation gates, historical receipt/backend proof, source reversibility, unchanged routing, full matrix, fairness/recovery limits, accounting and aggregate disclosure. After adding explicit top-level cost completeness, only the affected promotion matrix was rerun: `cpu-validation-continuation-cost-v2.log`, **21 passed/73 deselected in3.80s**. All test runs had guard blocked_reads0 and CUDA remained uninitialized. No broad historical real-data suite was run.

Reproducible focused command from this isolated worktree:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.. OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -p no:cacheprovider -p n23_validation_cpu_pathguard_v1 -q tests/test_qd_ed_n23_validation_continuation.py tests/test_qd_ed_n23_validation_runtime.py tests/test_qd_ed_n23_validation.py --basetemp=../n23-v2-guarded-fixtures-validation-continuation-review
```

The initial packaging attempt wrote its new source manifest then the guard blocked a hash reread of that just-written artifact outside its whitelist. The initial manifest and `cpu-validation-continuation-packaging-v1.failure.log` are retained. This was not a historical/protected read. Packaging v2 computes hashes from exact serialized bytes already in memory and leaves the guard unchanged; v2 completed with blocked_reads0 and CUDA uninitialized.

## Source closure and root handoff

The new manifest has230 files (214 original fingerprints plus16 evaluation additions); its bridge reverses exactly the already allowed worker/runner validation insertions, then byte-checks every original scientific file. This commit adds **no further worker or runner modification** beyond89aea3b. The addendum and historical adapter/helpers/tests are in the tracked source scope.

- `source-manifest.validation.continuation.cpu-v2.json`: SHA `cb0ab21b2e157a7bfbe4daacd46dddf37f9607e340707ae34b82db1215696cf8`.
- `source-bridge.validation.continuation.cpu-v1.json`: SHA `88cb6c7763799408e1952e81a1064aafb4aa14720e5462b3300442d6ff94d883`.
- `cpu-validation-continuation-packaging-v2.json`: SHA `12cc35c035fc66e2724f521e5dae46ea35cfc297d47f14f5f8015f66ebf64b75`.

New separate artifacts preserve old drafts: `validation-plan.continuation.cpu-draft-v1.json`, `validation-dev-promotion-review.continuation.template-v1.json`, `validation-source-review.continuation.template-v1.json`, `validation-authorization.continuation.template-v1.json`. They are deliberately non-executable: missing actual reviews, false authorization, placeholder hashes, and an illustrative c1 label with freshness_not_evaluated. That label is not a cohort recommendation or release decision.

Root should wait for the actual full continuation result, independently verify promotion through the historical source/receipt/native/backend/cost gates, and review this new evaluation commit/bridge. Only after Dev is terminal may root integrate the evaluation branch, generate actual Dev/source reviews with the new required `continuation_evidence_addendum` reference, perform the unchanged metadata-only first-fresh-cohort selection and full protected-capacity checks under private locks, then adopt separate validation authorization and freeze/release using the existing prepared CLI. No additional Dev cell or backend preflight is needed or authorized. If Dev does not promote, this preparation stays inactive. Formal remains closed.
