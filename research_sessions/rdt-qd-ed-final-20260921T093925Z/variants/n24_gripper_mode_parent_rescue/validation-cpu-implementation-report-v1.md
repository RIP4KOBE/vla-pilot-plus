# N24 conditional validation CPU preparation

Status: **CONDITIONAL_CPU_PREPARATION_ONLY**. Validation score and promotion are **Unknown**; no actual Dev results, protected outcomes, live journals, credentials, model/provider/simulator/GPU calls, state/budget/lock mutations, source integration or protected release occurred. The active owning source remains the parent's frozen Dev source. All preparation lives under this N24 variant.

Final isolated branch `codex/n24-validation-agent`, commit **d2e9feadc241fccc66b27255450025e2733c8d87**. Scope freeze e2a5822, implementation fee3d15, schema/activation documentation d2e9fea. Based exactly on Dev **3b7afa02757eb3519d95547e4b6e6e939f7068f2**. Worktree is `validation_implementation`; it was clean at delivery.

## Source and preserved semantics

`validation-source-manifest-v1.json` binds 242 files: all230 original Dev records plus12 new protocol/evaluation/test files. SHA256 **1404509b5d7b140cdee14b5d009f71038154d257a27a1f8d13cdabcc23e75924**.

`validation-source-bridge-v1.json` SHA256 **75632074ffa4510894ce39da68cfed0ab52f38118c39212d0195ce77e773868c** binds the exact Dev and evaluation sources. Original228 files are byte-identical. The runner changes are a finite, reversible set of literal validation-only routing/admission/exposure insertions. The shared worker differs by exactly3 lines inside `validate_context`; after removing them the complete file equals Dev. `run_worker`, `verify_receipt` and every other worker function are byte-identical. All core/main/config/provider/Stage/native arithmetic/audit and C0/Q0/N24 profiles remain byte-identical. `validation-source-diff-v1.patch` preserves the complete diff.

The eight new modules implement bridge, contract, evidence, identity, recovery, prepare, supervisor and report. The historical Dev reader verifies the original3b7 source and same-process audit evidence without incorrectly requiring the future evaluation HEAD to equal Dev. It retains original source/runtime/command/process/PID/start/boot/receipt/native/metric/cost associations and actual reviewed backend proof provenance; no additional CUDA audit or preflight is introduced.

A `n24_cohort` worker-only marker keeps the unchanged native worker branch active. Separate `n24_validation` admission explicitly excludes old N24 Dev/N23/N7 routing. This preserves profile-bound rescue audit and missing-all-markers rejection. Actual serialized provider-mode omissions stay valid for C0/Q0. Frozen N24 zero-guided missing-metrics compatibility is reused: explicit integer terminal0, compute0 and independent canonical0 must agree. Optional missing metrics/safety refs remain absent and later appearance invalidates their binding. Original diagnostic reader and N24 evidence packaging reader identities remain distinct.

Entry independently recomputes the actual complete40 Dev first-valid results, receipts, result/status agreement and all attempts/costs. It requires real N24>=5/10 and>=C0/Q0/N23 with substantive QD/ED. It cannot use partial, invalid, futility, hypothetical or running data. No actual promotion review is manufactured here.

Protected identities use only frozen identity metadata, history/exposure and reserved/dispatched identity projections. First unused c1..c4, both blocks intact, no outcome-based selection. The60 primary matrix remains block1/2 × task0..9 × C0/Q0/N24; maximum2 exact sole-timeout recoveries and62 total dispatches,32 GPU-process hours,1800+40 per attempt. Existing478/100, bucket51/187/180/40/20 and formal reserve are preserved. Every dispatch retains existing private one-worker GPU7/runtime/resource checks, complete remaining capacity and formal reserves. No validation futility, cohort restart, extra seed or generic retry exists.

Reports retain protected cell detail and all invalid/recovery costs while the public/root tuning disposition is aggregate-only. Valid journaled evidence followed by status/postprocessing failure remains charged and saved, with INVALID disposition. Missing values stay unknown; there is no fabricated0/20. Cache updates remain defined as batches whose best cache changes. Full60 and N24>=10/20 and>=C0/Q0 plus substantive fixed QD/ED determine promotion; rescue activation counts add no veto. Formal stays closed and target remains unmet.

## CPU verification

Final guarded command, from `validation_implementation`:

```sh
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONPATH=.. TMPDIR=../tmp PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -p n24_validation_cpu_guard_v2 -p no:cacheprovider --basetemp=../fixtures-validation-final-v1 tests/test_qd_ed_n24_validation.py tests/test_qd_ed_n24_validation_runtime.py -q
```

Use a new basename for any justified rerun; preserve prior fixtures/logs. Result: **179 passed in14.84s**; guard **blocked_count0**, **CUDA initialized false**, **CPU threads2**. Test/source imports were restricted to static source/protocol metadata and synthetic fixtures; the frozen N22 source-plan import was separately exact-SHA whitelisted. The final guard additionally rejects real N24 result, execution, adoption, review and plan paths, including physical artifact targets. No old legacy real-data tests were invoked.

Tests exercise actual EDS metrics serialization, original exact timeout classifier, runtime runner reserve/dispatch/terminal/cleanup shape, immutable source reversal, 60-cell and62-attempt reporting, no futility, failed recovery/unknown-token accounting, receipt/source/path alias faults, complete marker deletion, separate authority/capacity/freshness, explicit same-process worker route and historical receipt verification, old Dev routes and no restart. GPU identity/backend objects are faithful CPU mocks; these tests are not an actual GPU or protected runtime proof.

All logs are retained and referenced by SHA in `validation-cpu-test-results-v1.json` (SHA256 **67e2b8f87c328d973464aa15b97f2f42bdb14c77fc3ee44b21b920daaa64ce6d**):

- `cpu-validation-v1.log`:45 passed/1 failed. Synthetic empty JSONL contained a blank line; metadata projection now skips blank lines consistently with existing readers.
- `cpu-validation-v2.log`:95 passed.
- `cpu-validation-v3.log`:71 passed/2 failed. One assertion incorrectly addressed aggregate unknown-token accounting as a per-arm field and was corrected. The other found missing explicit terminal-to-receipt SHA association in the new validation selected-terminal reader; the implementation now checks receipt ref, exact context plan/ref/content and terminal artifact. Frozen Dev source was not changed.
- `cpu-validation-v4.log`:101 passed.
- `cpu-validation-v5.log`:68 passed.
- `cpu-validation-final-v1.log`:179 passed. Final complete necessary matrix; no further broad testing performed.

All runs report zero guarded read/call violations and CUDA uninitialized. Failures were neither deleted nor represented as passing runs. `git diff --cached --check` passed before implementation commit; post-commit bridge generation independently checked all230 original byte records and reported CUDA uninitialized.

## Non-executable templates and root handoff

`validation-cpu-templates-v1/` contains five immutable wrapped templates: Dev promotion review, source review, finite authority, release, and60-row plan draft. Every outer record has `executable:false`, `protected_execution_authorized:false`, `formal_authorized:false` and an explicit missing-prerequisite list. Authority/release payloads also deny validation; actual result/status/runtime/review/adoption refs are null. The plan uses **cX** and null seed/init values, frozen=false and all phases disabled. It neither selects a real cohort nor masquerades as a runnable plan.

Exact strict production schemas and commands are documented in tracked `experiments/qd_ed_n24/validation-controller-contract-v1.md`; templates must not be copied unchanged into production authority paths. Source/review/authority hashes are external and non-circular.

Root-only remaining steps, conditional on real Dev promotion:

1. Review the actual complete Dev result/status/ledger/native receipts and all costs. Create the future `validation-dev-promotion-review-v1.json`; incomplete/rejected/invalid closes this route.
2. Review/integrate exactd2e9fea only once the Dev worker is gone. Recompute242-source bridge, original230 equivalence, actual runtime and prior settled backend proof. Create `validation-source-review-v1.json` without release.
3. Under private locks reconcile identity metadata, select first fresh whole cohort, verify allremaining capacity/formal reserve, create/adopt the exact finite authority in state key `n24_validation_authority`. This CPU task does not do it.
4. Freeze using the owning checkout's `scripts/qd_ed_n24_validation_prepare.py --freeze --output <N24>/validation-plan.frozen.v1.gpu7.json`, independently inspect original-science60 commands/runtime/source, then create a distinct exact `validation-execution-release-v1.json`.
5. Launch only the owning checkout's `scripts/qd_ed_n24_validation_supervise.py --plan <N24>/validation-plan.frozen.v1.gpu7.json --release <N24>/validation-execution-release-v1.json --output-dir <N24>/validation-execution`. Output root must be owned under the original artifact root. Consume only aggregate disposition for mechanism selection; retain detailed protected evidence on disk.

No actual protected identity metadata was read or selected here. Actual future source integration, promotion evidence, capacity/freshness/resource checks, adoption and release remain root responsibilities. This is preparation only, not performance evidence or authorization to deploy.
