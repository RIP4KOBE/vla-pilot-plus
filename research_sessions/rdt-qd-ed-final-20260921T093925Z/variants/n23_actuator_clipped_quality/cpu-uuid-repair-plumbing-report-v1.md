# N23 single named UUID repair — CPU delivery

Final frozen commit is `675c2f4d07e787a7e160a2a26312c8ab2e4a19f6`, following the isolated strict UUID fix `9822ed48d3049c2258484be65bf53b638be97661`, on original source `77302aab40d6b059e85c8d1d8011ea36cb3d3856`. Worktree clean. Root alone integrates, reviews/adopts and dispatches; this executor made no actual GPU/CUDA/provider/model/simulator call, no real outcome read, and no real state/ledger/lock/Arbor mutation.

**Evidence clarification:** the failed worker did not retain raw actual_uuid. The earlier standalone normalization report's wording about a bare UUID being returned by that failed worker was too strong. A prior successful accounted GPU7 probe recorded the bare form; unchanged source inspection and CPU fixtures reproduce the literal-format failure. These support the compatibility diagnosis, not a claim that the failed worker's live raw value was observed. The repaired worker will record raw and canonical values; a genuine mismatch remains fatal.

## Scope and implementation

The root-frozen prospective exception is `uuid-repair-engineering-exception-v1.md`, SHA `d5c80006512203343d89dc24ab4de53356c045bc0f755800bf0e8337524d5f20`. Its exact tracked copy is included. Original v1/v2 protocols, original failed attempt/source/plan/review/report, and costs remain immutable. Original no-retry admission remains closed by default. This exception permits one explicit additional recovery of only attempt `rdt-qd-ed-final-20260921T093925Z__n23_backend_preflight_v2__7ca117f9b7fb`; it does not declare that prior protocol allowed a retry.

A189-line helper, `scripts/qd_ed_n23_uuid_repair.py`, implements exact named failure, external authority, science/source identity and two-attempt lineage checks. Four existing v2 plumbing modules add explicit repair branches; existing runtime, capacity, charge/cleanup, arithmetic and proof checks are reused. No cohort duplication or generic retry switch was added.

All original failed report/plan/terminal references are hashed against root's immutable failure review (`95353cd515ca1e759e781d63108ecf03fcdea62372c7d1578159fe79a225c661`). The original plan SHA must be `44147944afdc773938d2a97ce564dc2fc9e184ac2cac2957df006d70489213d1`, original source77302aab, error exactly `RuntimeError:audit physical CUDA UUID differs or unavailable`, zero arithmetic and synthetic batches, false outcome, original reserved/dispatched/aborted ledger group, unchanged6.538148973020725 seconds and no retry_of. Historical probe values are independently reconciled with their hashed top-level evidence, including GPU7/logical0/count1/EGL4/zero simulator steps. This is supporting historical evidence only.

Repair admission requires an exact new authority ref in private state, final complete source/runtime review, unchanged478/100 limits and bucket caps51/187/180/40/20, full remaining Dev22-hour ceiling, both Dev recovery slots, the repaired120+40 opportunity and all remaining protected reserves. Any previous repair reservation/attempt, another backend ID, incomplete original ledger group, different/partial arithmetic failure, prior N23 Dev reservation, live resource owner or unavailable capacity blocks dispatch. No increase to existing recovery20 allowance occurs.

The repaired attempt keeps the same original `N23_BACKEND_PREFLIGHT_V2_20260930` iteration and uses a fresh explicit `n23_backend_uuid_repair_once` key and attempt-name marker, with `retry_of` naming the original. It remains visibly the second backend opportunity, not a renamed algorithm. Across originals and repair exactly two backend attempts are allowed. Every failure/timeout/launch error remains charged and closes repair; no third attempt is admitted.

The repaired frozen plan copies the entire original plan byte-for-byte in content except final complete source and one uuid_repair binding. Thus runtime/corpus/order/batch bounds/synthetic cases/arithmetic settings remain identical. Source delta from77302aab is restricted to the declared UUID compatibility files, repair plumbing/tests and exception copy; all main/core/config/profile/Stage/controller bytes must stay unchanged. No tolerance changes or protected-phase launch exists.

The strict proof retains both backend attempts and their original chronology. It binds repaired source/runtime/process/wall/receipt and explicit retry lineage. Repair cannot occur after Dev reservation; later original Dev is permitted only after valid completed repair. The unchanged40-cell N23 v2 matrix gains repair provenance in n23_cohort.uuid_repair and uses the repaired backend proof. Source/runtime must match the repaired preflight exactly. Private authority, immutable protocol hashes and final review are rechecked for Dev as well.

## Tests and limitations

Initial strict UUID/backend suite: **111 passed in29.55s**, `cpu-uuid-normalization-v1.log`. Final repair+original v2 suite: **254 passed in7.66s**, `cpu-uuid-repair-plumbing-v2.log`. An additional **9 passed,54 deselected in2.21s**, `cpu-uuid-repair-composition-v3.log`, extends the repaired-preflight→metered-proof→unchanged40-cell Dev composition through the actual c.validate_contract and tests forbidden science/profile/main deltas. These are focused CPU tests, not GPU arithmetic readiness evidence. No broad protected-data suite was executed.

All test runs used the existing read guard with zero blocked reads and CUDA uninitialized. Source closure also passed the strict changed-file allowlist and208-file committed-byte check under the guard. Synthetic composition uses CPU fake arithmetic/backend metadata solely for process/report/lineage plumbing; it does not claim actual CUDA arithmetic parity. Actual strict arithmetic remains the bounded metered repair worker's responsibility.

The preserved first plumbing log `cpu-uuid-repair-plumbing-v1.log` records248 passes/6 failures caused by a synthetic reservation event omitting required time_unix. The original budget validator correctly rejected it. The fixture was corrected; production budget checks were not relaxed. Original logs and earlier manifests/templates remain intact.

Reproduce from implementation:

```
PYTHONPATH=.. OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -p n23_v2_cpu_pathguard_v1 -q tests/test_qd_ed_n23_uuid_repair.py tests/test_qd_ed_n23_v2.py --basetemp=../n23-v2-guarded-fixtures-uuid-repair-review-new
```

## Frozen source and review templates

`source-manifest.uuid-repair.cpu-v1.json` contains208 committed records. File SHA `7926b645057b08c9d30a9c900ec56ac24e06e2502b3b19b163b41810e8bb7f35`; canonical file-list SHA `43c0ac639fd99fd2b57382be931abdf0aa7f43aeb5483adfe95aac6a40d4cede`. `cpu-uuid-repair-source-diff-v1.patch` SHA `66d5ffc1099cb960594ee7ba7463845fb64f6f49b2f519dadc67e28209895d1d` contains all10 allowed changed paths. `cpu-uuid-repair-source-closure-v1.log` records exact source/allowlist checks, no CUDA and no blocked reads.

Two intentionally non-executable CPU templates are provided:

- `final-source-runtime-review.uuid-repair.cpu-template-v1.json`, SHA `7c787d1c5acbad57b281d9e08dd4e8439f48bf60cda0d4c90d07cf0f14c9f136`. disposition is PENDING_ROOT_REVIEW.
- `uuid-repair-authority.cpu-template-v1.json`, SHA `7f1ac3731622094c6cfdb2927e6bf9aa7925a6c33d790b3bb88465468fba5c9a`. final review SHA, interpretation and timestamp are null. It is not adopted and cannot authorize a worker.

Root should verify final source bytes at the actual owning HEAD, review actual failure/runtime/corpus evidence, and create the **new** `final-source-runtime-review.uuid-repair.v1.json`. Its exact fields are schema=`n23-final-source-runtime-review-uuid-repair-v1`, disposition=accepted, source=<full source record>, runtime=<frozen ref>, dev_protocol, backend_protocol, amendment, timeout_observability, exception, failed_review, no_gpu_release=true. All document hashes are checked against constants before repaired dispatch.

Root then writes `uuid-repair-adoption-v1/authority.json` with exact schema=`n23-uuid-repair-authority-v1`, exception, failed_review, final_source_review, source, runtime, nonempty authority_interpretation, recorded_at, user_message=<original autonomous user text>, cumulative_caps={attempts478,gpu_hours100,buckets:{baseline51,development187,validation180,formal40,recovery20}}, limits={additional_backend_attempts1,timeout_seconds120,cleanup_seconds40,physical_gpu7,budget_bucket:recovery}, validation_authorized=false, formal_authorized=false. Under the existing owning locks/append-only authority record practice, state field `n23_uuid_repair_authority` must equal `{path:absolute_authority_path,sha256:actual_digest}`. No budget limit changes are needed or implemented. Templates do not perform adoption.

Plan uuid_repair binding has exact schema=`n23-uuid-repair-binding-v1`, exception ref, failed_review ref, authority ref, retry_of=<exact original failed ID>. New plan path is `backend-preflight-plan.uuid-repair.frozen.v1.json`. Each new attempt keeps fresh release.json/attempt-context.json with explicit retry_of; reports use `n23-backend-uuid-repair-start-v1.json` and `n23-backend-uuid-repair-report-v1.json`. Original artifacts are not overwritten.

## Prospective root commands — not executed here

After source integration, actual source review and locked authority adoption, from the final owning source:

```
python scripts/qd_ed_n23_v2_prepare.py --kind uuid-repair --output <N23>/backend-preflight-plan.uuid-repair.frozen.v1.json --freeze
python scripts/qd_ed_n23_v2_preflight_admit.py --plan <N23>/backend-preflight-plan.uuid-repair.frozen.v1.json
```

Only if the sole repaired worker yields a valid strictly accepted proof and no source/runtime byte changes:

```
python scripts/qd_ed_n23_v2_prepare.py --kind dev --backend-proof <repaired-attempt>/backend-proof-reference.json --output <N23>/plan.frozen.v2.gpu7.json --freeze
```

Root independently verifies the resulting plan/proof and writes the existing exact Dev execution release schema before starting the unchanged v2 supervisor. That release's plan hash transitively binds exception/authority/both backend attempts. No Dev source change after repair, no alternate retry ID, no provider fallback and no protected-phase authorization is granted. Stage remains the frozen current Codex managed login; Poe is unused and credentials unchanged.
