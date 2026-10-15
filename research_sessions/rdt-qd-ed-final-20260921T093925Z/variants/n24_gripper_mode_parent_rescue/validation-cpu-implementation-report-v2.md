# N24 conditional validation CPU delivery v2

Status remains **CONDITIONAL_CPU_PREPARATION_ONLY**, protected execution unauthorized, validation score **Unknown**. Final source is **8f640f04e8cc3565512cb934ad5bbd0fd5d8642d**, branch `codex/n24-validation-agent`, isolated `validation_implementation`. No owning source, scientific profile/code, GPU/runtime, actual Dev/protected output, state, budget, ledger or authority was accessed or changed by this correction. All v1 source/manifest/bridge/drafts/logs/report remain preserved.

This supersedes the v1 delivery source only after root review. The conditional scientific protocol SHA3748383067805ce084613567a1715e2bd6b749d53404e0c3491fa7937782fc2d and all evaluation gates/limits remain unchanged.

## Root-reviewed operational correction

Root found that v1 constrained controller output to the attempt `artifact_root`, while launch required the variant's `validation-execution` directory. These are separate source/artifact volumes in the intended production layout, so the initial implementation would reject before dispatch. No actual validation was attempted.

The new shared `validation_report.output_directory` checks both ownership under `c.RUN_DIR` and equality to the exact `c.RUN_DIR/validation-execution` path. Launch, execute and terminal reporting all use it before creating output. The original attempt path remains under frozen `plan.artifact_root`; nothing is moved. Different variant output paths, attempt-root controller paths and a symlink escape are rejected. Only the new validation report/supervisor, their tests and contract documentation changed; frozen Dev science and worker functions did not.

The v1 report's statement that the validation controller output must be under the original artifact root is superseded: **controller/detail/aggregate files live in the owned variant/validation-execution; episode attempts remain on the original artifact volume**. The tracked schema/activation document is corrected.

## Guard clarification and evidence

Root also found that external guard v2 checked writes before sensitive evidence path prefixes. Its sensitive-path branch therefore protected reads but did **not** independently forbid writes to sensitive names located directly beneath the N24 variant. The earlier zero-blocked reports only show that the executed tests did not attempt such access; they do not establish the write protection that v2 lacked. There is no evidence of actual sensitive-path writes, and none was performed.

Guard v1/v2 are preserved. New `n24_validation_cpu_guard_v3.py` checks sensitive real Dev/validation execution, frozen-plan, result, root-review, adoption/authority paths for **both reads and writes first**, considering lexical and resolved paths, before generic allowed-source/fixture output rules. Non-executable templates occupy their separate `validation-cpu-templates-v2` directory; no execution-prefix exception was added.

Two narrow guarded runs after the correction:

- `cpu-validation-pathfix-v1.log`: **26 passed,89 deselected /5.01s**, covering split variant/attempt roots, rejection of wrong roots/symlink escape at launch/execute/report, existing60-cell reporting, status failure retention, recovery costs and release checks.
- `cpu-validation-guard-v3.log`: **10 passed,115 deselected /0.53s**. Tests execute the actual guard callback AST with a synthetic root, invoking no filesystem operation. Each of10 sensitive path forms rejects read/write/append; the distinct template directory remains allowed. Intentional negative callbacks affect only the isolated mock counter, not the real installed guard or actual paths.

Both installed v3 guard reports: blocked_count0, CUDA initialized false, CPU threads2. The prior179-test final suite remains valid historical evidence for the unchanged components; it was not unnecessarily rerun or relabeled as a run on this later commit. `git diff --check` passed and exact source bridge generation passed after commit, CUDA uninitialized.

Reproduce from the isolated worktree using a fresh basetemp:

```sh
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONPATH=.. TMPDIR=../tmp PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -p n24_validation_cpu_guard_v3 -p no:cacheprovider --basetemp=../fixtures-validation-pathfix-v1 tests/test_qd_ed_n24_validation_runtime.py -k 'production_split or full_denominator or supervisor_60cells or release_rechecks' -q
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONPATH=.. TMPDIR=../tmp PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -p n24_validation_cpu_guard_v3 -p no:cacheprovider --basetemp=../fixtures-validation-guard-v3 tests/test_qd_ed_n24_validation_runtime.py -k guard_v3 -q
```

Preserve original directories/logs if rerunning; choose unused basetemp names.

## Immutable handoff

- `validation-source-manifest-v2.json`,242 files, SHA256 **80970d842f39a1e5d43c4c9c488ac9d60b625b823a2b0b3f32ef7b9876aa8ab9**.
- `validation-source-bridge-v2.json`, exact original230 to new242 records, SHA256 **73170e8909820ae4390b74f7d53d5b843f9412b569ec5e1a30218a3cf83b971c**.
- `validation-source-diff-v2.patch` is the entire delta from3b7; `validation-path-fix-diff-v2.patch` is only this correction fromd2e9fea.
- `validation-cpu-templates-v2/` has the five updated non-executable, denied-authority templates with exact new source/bridge and links to prior templates. Actual future result/status/runtime/review/authority refs remain null. Illustrative60-row cX plan has no seeds or runnable identity; it is not a selected cohort.
- `validation-cpu-test-results-v2.json` and `validation-delivery-manifest-v2.json` bind v1 history, both new logs, v3 guard, current source/bridge/diffs/templates and this report.

Root-only activation steps are unchanged from the tracked `experiments/qd_ed_n24/validation-controller-contract-v1.md`, with the corrected controller path: actual complete Dev promotion and independent terminal review first; then exact source integration/review and old-proof/runtime check; metadata-only first-fresh whole cohort and full capacity/formal reserve; separate finite validation authority adopted under private locks; exact plan freeze and separate release; one serial validation launch. Current root has not authorized protected execution by accepting CPU preparation alone. No validation restart, new preflight or formal launcher was added.

CPU work is complete and source frozen pending root review. No scientific efficacy claim follows from this preparation.
