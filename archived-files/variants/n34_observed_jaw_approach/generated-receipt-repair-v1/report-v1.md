# Node 15.4 generated receipt repair

Implemented in isolated production worktree; ready for independent root review.
Commit: `dc327becc00cd205bda0bd7905c24e6ade8efd6b` (base `1eeaddf1416e5a2d6b3ed3ab143f15cf5f85da81`).
Only the four intended operational source/worker/test/doc files were committed.
Git status is clean; report artifacts are outside the checkout in the authorized repair directory.

## Repair

The actual runner waits for worker exit, then references the receipt and calls
`verify_terminal` → `verify_receipt`; reconciliation uses the same consumer.
The old parent predicate could never accept v2 generated entries because their
names are deliberately absent from ordinary closure modules.

Worker receipt v2 now carries runtime receipt v2 envelopes for both phases.
Each has exact ordinary modules and separately retained generated evidence,
bound to context, frozen closure reference, worker process identity and phase.
The source live attestor still verifies all generator/template/content/name/spec/
loader/owner/finalizer checks. The wrapper retains source UTF-8 bytes and those
checked origin claims. Parent verifies the external prospective rule and content,
then all evidence fields without reopening cleaned-up worker temporary paths.
Before/after generated identity must remain identical when already present before.
Ordinary records remain exact and fail closed; required-after completeness and
all surrounding controller/native/source/process/device/evidence gates remain.

## Validation

```sh
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -B -m pytest -q -p no:cacheprovider tests/test_n34_generated_receipt.py
```

44 passed in 14.85s (exit 0).

```sh
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -B -m pytest -q -p no:cacheprovider tests/test_n34_generated_runtime.py tests/test_n34_source_controller.py tests/test_n34_worker_entrypoint.py -k 'generated_runtime or runtime_closure_verification or full_external_module_inventory or real_m'
```

68 passed, 55 deselected in 35.45s (exit 0).

```sh
git diff --check
```

passed; no output (exit 0).

Total: 112 focused passing cases. Earlier receipt-suite iterations passed
32 and 44 cases; the final 44-case command was rerun on the committed code after
organizing the test entrypoint/imports. No broad suite was run.

The parent integration starts a test-only ordinary-inventory discovery process
and two independently verified legitimate processes. Both real Torch-generated
TemporaryDirectories are absent before parent consumption, and paths differ.
It tests absent-before and already-loaded-before snapshots, ordinary-only v1
closure compatibility, tampered rule/content/hash/origin/loader/name/owner/cache/
finalizer evidence, missing/unknown records, ordinary exactness, external rehashed
invalid rules, phase/process/context/closure bindings, and before/after swaps.
Controller/native tampering fails their real gates. Dispatch/context setup is
stubbed; source/device/controller/native scalar documents are synthetic fixtures.
No models, generated forward functions, simulation environments or episodes run.

## Prospective freeze and limitations

The committed documentation specifies complete ordinary inventory construction,
the exact supported generated rule and prospective source reconstruction, then
root freezing through the existing external hash references. Root must update the
operational source commitment and use matching v2 producer/consumer code. This
executor did not construct, adopt or release a production manifest.

- Retained origin metadata is a trusted worker point-in-time claim. After cleanup, parent checks frozen content and claim consistency, not the destroyed directory/finalizer.
- No cryptographic signing or protection against arbitrary worker memory forgery, coherent replacement of the entire receipt plus its trusted hash/bindings, or post-check filesystem races.
- Parent integration substitutes dispatch/context setup only; synthetic source/controller/device/native scalar fixtures exercise real receipt gates but are not deployment evidence.
- No lazy model/environment/native runtime coverage or readiness established. Root must independently freeze production ordinary inventory, generated rule and updated operational source.
- New producer and parent require worker/runtime receipt v2; old flat worker receipts fail closed. Closure v1 remains supported for ordinary-only use, closure v2 for generated rules.

No GPU dispatch, network, installs, extra agents, coordinator/driver locks,
scientific or threshold/protocol edits, or owning state/ledger writes occurred.
Applicable ancestor/scoped AGENTS locations were checked; no additional on-disk
instructions were found. Prohibited design/results/credentials and foreign study
state were not read. Root-owned state, releases and adoption remain untouched.

Execution detail: an initial text rewrite used system `python3`; validation used
the requested environment interpreter and two-thread limits. Existing entrypoint
test child invocations omit `-B` but inherit `PYTHONDONTWRITEBYTECODE=1` and use the
requested interpreter; new receipt children explicitly use `-B`.
