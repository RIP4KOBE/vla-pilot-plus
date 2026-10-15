# Node 15.4 bounded N34 release-boundary delivery

Status: committed for independent root review/adoption. No production acceptance or dispatch.

- Base: `dc327becc00cd205bda0bd7905c24e6ade8efd6b`
- Commit: `60fc00a55b1b8dfb5c98b52e92d979b0869b4cad`
- Worktree: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n34_observed_jaw_approach/production_worktree`
- Post-commit working tree: clean.
- Authority: `authority-v1.json`, SHA-256 `395a3373516f9ebb204979700d491bb2116d7a2db7080716e26eacc785cbd138`.
- Required lazy-runtime review hash verified: `68728765c48b00d7750a910a019d99b7bc5d593256b1953d0c24958325ae70fb`.

## Changes

The public `validate_release` now returns the complete existing
`verify_prospective_release` result. No closure condition was removed or weakened.
Disabled plans reject before the detached release is read. Bare-plan
`require_release` stays rejecting and cannot be enabled by booleans.

All runner/supervisor paths were inspected; their existing release validation and
locked admission remain intact. Worker context construction and validation now
require detached authority. Worker main validates before its parent gate and
revalidates through run_worker/internal execution before process identity,
process-record checks, writes, model/Main or environment actions. Internal execution
has no draft/dispatch-record bypass. Receipt validation inherits full context
validation; terminal validation requires explicit external release and unconditional
context/terminal/process bindings.

No scientific, controller, audit, task matrix, threshold, deadline, budget or
recovery behavior changed. Six intended files were committed:

- `docs/n34-detached-release-boundary-v1.md`
- `scripts/qd_ed_n34_contract.py`
- `scripts/qd_ed_n34_release.py`
- `scripts/qd_ed_n34_worker.py`
- `tests/test_n34_production_integration.py`
- `tests/test_n34_release_boundary.py`

## Exact tests/results

Every command used the requested interpreter, `-B`, empty CUDA visibility and
OMP/MKL/OpenBLAS/NumExpr thread limits of two. No broad suite was run. Repeated
suite runs below record additions to focused coverage, not independent scientific
replications.

initial boundary suite:

```sh
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -B -m pytest -q -p no:cacheprovider tests/test_n34_release_boundary.py
```

Result: **330 passed in 3.66s**, exit 0.

focused lifecycle/admission/draft regressions:

```sh
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -B -m pytest -q -p no:cacheprovider tests/test_n34_lifecycle.py tests/test_n34_production_integration.py -k 'not composition_and_constructor and not prospective_mismatch_rejected and not same_worker_native_audit_external_anchor'
```

Result: **41 passed, 12 deselected in 9.26s**, exit 0.

boundary suite with real negative CLI cases:

```sh
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -B -m pytest -q -p no:cacheprovider tests/test_n34_release_boundary.py
```

Result: **336 passed in 11.58s**, exit 0.

updated tiny-tensor native audit fixtures:

```sh
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -B -m pytest -q -p no:cacheprovider tests/test_n34_production_integration.py -k same_worker_native_audit_external_anchor
```

Result: **3 passed, 20 deselected, 3 warnings in 17.53s**, exit 0.

Existing core/fkd_class.py:39 SyntaxWarning: invalid escape sequence '\s'; scientific file unchanged.

final boundary suite (347 cases) plus two draft regressions:

```sh
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -B -m pytest -q -p no:cacheprovider tests/test_n34_release_boundary.py tests/test_n34_production_integration.py -k 'release_boundary or drafts_remain_unreleased or candidates_are_fresh_unknown_and_unreleasable'
```

Result: **349 passed, 21 deselected in 18.95s**, exit 0.

Final boundary coverage includes all eleven consumer surfaces, positive
next-gate reachability, disabled drafts/boolean-only attempts, missing references,
plan/release/review/authority/runtime/closure/controller/manifest hashes, tampered
release/source bytes, source binding, protocol, authority approval/caps/basis,
phase expansion and recovery limits. All eight substituted leaf failures propagate
through every consumer. Six actual `python -B -m` worker/runner CLI cases reject
before a parent gate or execution. Positive fixtures are temporary and deliberately
incapable of real production source/runtime acceptance.

`git diff --check`, staged diff check and committed diff check all passed.
No test failures occurred. The three pre-existing scientific-file SyntaxWarnings
were left untouched.

## Root construction and remaining checks

The committed `docs/n34-detached-release-boundary-v1.md` contains the exact document
schemas/fields and ordered construction instructions. The trust DAG is:
inputs/source/runtime + protocol/authority -> all30 manifests -> final externally
hashed plan -> independent root review -> detached externally hashed release ->
context/receipt. No review/release hash may be put back into the plan.

1. Independently review/adopt this commit; freeze the actual adopted operational source and unchanged scientific source at 71ffff1a0f70d9874b309db9ef1843c02bf17ebf.
2. Bind the reviewed runtime, complete runtime closure including reviewed lazy tokenizer imports/generated rules, controller semantics and source-review evidence for the exact checkout.
3. Freeze the exact existing n34-production-protocol-v1 and independently approved finite n34-budget-authority-v1 with real approval basis, current accounting, protected reserves and ledger prefixes.
4. Build the exact dev-only released plan including run/inventory/seed fields; remove draft review/release keys, regenerate all30 manifests, then freeze and externally hash the final plan.
5. Root independently reviews the exact expected release fields; freeze exact n34-root-production-review-v1 and then the detached n34-execution-release-v1 pointing to its external review hash.
6. Supply independent plan/release hashes to the full public validator; independently reconcile/adopt owning authority and verify all current admission/provider/probe/STOP/deadline/live-handle checks before root alone decides dispatch.

## Limitations

- Synthetic positives prove public consumer wiring, not real release acceptance. Installed-source, loaded-module, runtime, controller, stage, files/input and manifest leaves are checked test stand-ins; all eight leaf failures propagate through all eleven consumers.
- No production release, root review, protocol or budget approval was issued. No real closure was rebuilt or accepted; no model, GPU, simulator episode, network, package installation or dispatch was used.
- Native audit tests use tiny synthetic tensors and test-only context/dispatch substitution, not simulator episodes or production evidence. Lifecycle tests use temporary journals and fake processes only.
- Current owning state, ledgers, reservations, live handles, provider readiness and GPU readiness were not inspected or certified. No owning locks or state/ledger writes occurred.
- Root must independently review/adopt and regenerate affected committed operational-source/config manifests, freeze exact external documents, verify full real release closure and current locked admission before any execution.
- Scientific source, algorithm, native auditors, controller semantics, task matrix, thresholds, deadlines, budgets and zero-recovery rules were not changed. No new validation/formal access is enabled.
- Hash validation retains the existing point-in-time trust model; it is not a signature scheme or protection against a caller able to forge all trusted external references.

Bounded delivery stops here. Root owns all independent review, adoption, state, releases and dispatch.
