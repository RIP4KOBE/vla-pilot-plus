# N25 conditional validation — CPU preparation only

Final isolated commit: `79caa4b6f8a3cc67a379b8da510dc9ab745b4c14`, branch `codex/n25-validation-agent`, clean worktree `validation_implementation`. Base Dev commit: `5a65ef15968cc68c82314e8c0773b3365ad45fa0`. This report grants no validation release, integration, budget adoption or GPU use. Actual validation efficacy and readiness are Unknown until the future gates pass.

## Delivered behavior

The new closed evaluation path prepares 60 matched C0/Q0/N25 primary cells on one metadata-selected fresh cohort, with at most two unchanged typed whole-episode Codex-timeout recoveries, one per cell. All 60 must be valid; N25 needs at least 10/20 and no fewer successes than either control, with original substantive QD/ED and native evidence gates. There is no partial promotion, futility, restart, new GPU proof or formal launcher. Original Dev science, raw Stage/provider/decoder, clipped RBF, zero-gradient behavior, profiles and witness arithmetic remain unchanged.

Entry independently reconstructs complete 40-cell Dev promotion and all costs, then binds the actual root terminal review by hash. It requires the real `n25-root-terminal-review-v1` schema, `ACCEPT_TERMINAL_RECONSTRUCTION` decision, and `ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION` disposition, with matching result/plan/257-file source/Dev-ledger references. It does not assume nonexistent top-level accepted or source_commit fields. The subsequent independent promotion-review record, full source review, metadata freshness, full capacity, separate adopted authority and explicit execution release remain mandatory.

Historical evidence verification reuses unchanged numerical proofs and charges through their recorded old source and same-process receipt identity. It validates both the earlier settled quality proof and the N25 12-case tensor resource proof; no new backend invocation occurs. The new evidence reader imports the existing identity verifier lazily. No production function cloning or shared-global replacement was added.

Profiles force N25 native gates even if all markers are removed. Valid all-zero RBF gradients are accepted. Zero-guided missing metrics remain allowed only with consistent original terminal, episode compute, native canonical counts and absent-file references; this never permits downgrading N25 audit. Costs preserve invalid attempts, incomplete token usage and unknown counters. Supervisor postprocessing or status failure retains the independently reconstructed journal prefix and all costs and closes INVALID. Controller reports stay exactly under `N25/validation-execution`; attempt payloads stay under the separate frozen artifact root. Protected detailed results stay on disk; iteration-facing output is aggregate disposition only.

Exact caps remain 494 attempts / 100 GPU hours, buckets 55/199/180/40/20, local validation 32 hours, protected validation/formal 32/12 hours, 1800+40 seconds per episode. GPU7 and current Codex managed login remain the only online configuration; no Poe calls or credential handling were introduced.

## Source closure

The final source manifest contains 270 files: the 257 original Dev files plus eight evaluation modules, two test files and three protocol/controller documents. Of the originals, 255 remain byte-identical. Shared runner changes are exactly the routing-addendum insertions; all original execution, cleanup, provider, resource and accounting primitives remain unchanged. The worker changes only `validate_context`; its other 15 functions, including run_worker and verify_receipt, are byte-identical. The explicit reverse substitutions reconstruct both original shared files exactly.

* `validation-source-manifest-v2.json`: SHA256 `f4b5d46342a6d334340836591d79bc2e662294cc8b9643452afe892080c8216d`.
* `validation-source-bridge-v2.json`: SHA256 `1c9f150271f2b5f55d901b91f4c599197f8574214e5b0f16fbf537ea85edd6ff`.
* `validation-function-bridge-v2.json`: enumerates original/new function identities and exact shared-file hashes.
* `validation-source-diff-v2.patch`: complete final diff against Dev.
* `validation-cpu-templates-v2/manifest.json`: SHA256 `017af518e3fe335a40e8b67777a13be9fd336445f84030dd96103ce9cd5f7be6`.

Protocol freezes are commits 74b5e20 and ab5469c. Initial implementation is 58b3cc9; 79caa4b only adds actual root terminal reconstruction binding and its tests/documentation. Version-1 source/bridge/diff/templates are retained as history, not the final source. No current owning or implementation worktree source was changed.

## CPU verification and retained failure

All tests used Python 3.12 from `/home/hynx/miniconda3/envs/vla-pilot`, two Torch/inter-op threads, CUDA invisible, no GPU initialization, network/subprocess guards and synthetic fixtures. No actual attempt, protected outcome, Stage payload or credential content was read.

| Log | Result | Scope |
|---|---:|---|
| cpu-validation-first-v1.log | 2 collection errors, retained | Import-time legacy helper attempted opening the old N22 frozen plan; guard rejected both opens before content access. No tests ran. |
| cpu-validation-second-v1.log | 193 passed, 15.84 s | Matrix, source/reverse bridge, exact Dev result schema, promotion/release/freshness/capacity, receipts, original worker routing, typed recovery, original run_plan with mocked owned processes, cleanup/error accounting, real metric serializer, split report/attempt roots and reporting failure paths. |
| cpu-validation-proof-v1.log | 17 passed, 0.99 s | Historical proofs, old/new arithmetic and charge negatives; zero-gradient acceptance; zero-guided missing metrics; complete N25 marker removal rejection. |
| cpu-validation-proof-v2.log | 13 passed, 0.97 s | Necessary repeat of historical proof cases after strict real tensor-authority schema, source-review/budget and historical boot-ID binding. |
| cpu-validation-root-binding-v1.log | 23 passed, 8.78 s | Existing 13 Dev-promotion checks plus 10 actual root-review schema/reference/manifest positive and negative checks. |
| cpu-validation-source-export-v1.log / v2.log | passed | Actual production source-record/reverse-bridge export, committed byte equality, clean HEAD; only read-only Git source queries allowed. |

The final targeted runs and both source exports each report zero blocked operations and CUDA uninitialized. The retained initial failure reports two blocked opens of the same out-of-scope plan, with zero content reads. The fix is exclusively a lazy import in the new N25 module; the guard was not relaxed and old helper/source bytes were not edited. Test-only exact pure-function AST loading supplies synthetic identity dependencies; it is not production behavior. There are 220 distinct synthetic cases represented by the successful runs, with only affected subsets repeated. This is not a claim that every case was rerun at the final commit; the later production delta is limited to the separately tested historical and root-review binding.

Reproduce the root-review subset from `validation_implementation` with a new synthetic basetemp:

```bash
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONPATH=.. TMPDIR=../tmp PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -p n25_validation_cpu_guard_v1 -p no:cacheprovider --basetemp=../fixtures-validation-review-reproduction tests/test_qd_ed_n25_validation.py -k 'actual_dev_result_schema or actual_root_terminal_review' -q
```

The complete original synthetic command substitutes both test files, removes `-k`, and uses another fresh basetemp. It is documented for reproducibility, not a request to repeat unchanged suites. Original failures and successful logs are indexed in the delivery manifest.

## Root handoff and remaining limits

The tracked `experiments/qd_ed_n25/validation-controller-contract-v1.md` documents exact external schemas and prospective CLI activation order. Disabled v2 templates include null future hashes and no selected real seed cohort; their wrapper schemas and false authorization flags cannot pass live admission. No circular actual result or release hash is embedded in source.

Future root work is: establish immutable complete Dev promotion; create the actual root terminal and separate promotion reviews; independently review the exact commit/source bridge/runtime/settled proof evidence; integrate only after Dev closure; select identities from metadata and verify current capacity under locks; write/adopt separate finite validation authority; freeze the exact plan; write its separate release; launch the original supervised runner through the new explicit route. No proof should be rerun. If any gate fails or Dev does not promote, this preparation remains inactive.

No actual protected cohort has been selected, consumed or evaluated by this task. Synthetic process and receipt tests do not prove live resource availability or future runtime success. Budget sufficiency, fresh identities, actual root-review bytes and actual Dev promotion are intentionally unresolved. The full research target remains unmet; this is conditional evaluation infrastructure only.
