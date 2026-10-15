# N23 conditional validation CPU preparation v1

Preparation only. The executor has not released validation, integrated owning source, changed any real research state/budget/ledger/locks, or called CUDA, a provider, model or simulator. Actual Dev promotion remains a hard prerequisite.

## Source and scope

Commit: `89aea3be3522a388484c6c65dd479c5d8174b290`, branch `codex/rdt-qd-ed-n23-validation-20260930`, isolated `validation_implementation`.

The worktree was fast-forwarded from the clean fbe5ac9 base to the exact Dev source `51104470983cdbafd08feb87f2f39b7553779405` before this implementation. The frozen validation protocol SHA256 is `b202e2bf03e13ea4d66fdd355f7959bbb40f264aeb3c9bd37f57959efdc63615`; its tracked copy preserves the exact original bytes, including the final blank line.

The explicit source bridge retains all 214 Dev source records and adds 12 evaluation/test/protocol files, yielding 226 records. It checks each old fingerprint against the original Git object. For the worker it removes exactly the new validation route inserted in `validate_context` and requires all remaining file bytes to equal Dev. The runner is similarly reversible through eight fixed routing edits. The bridge rejects other changes even within those two files. No production/core/config/main/provider/controller/decoder/arithmetic/UUID/backend or earlier recovery helper bytes changed.

Artifacts:

| Artifact | SHA256 |
|---|---|
| Source record canonical hash | `6ffe7bb619844889820f47df4b0ef4543b1e8d39776b22d2a8a5f403092edc94` |
| `source-manifest.validation.cpu-v2.json` | `d1cfbd19fcadff2c7154f61fa194c3b799d4b77364a8f59c5f610e1e9cbe6638` |
| `source-bridge.validation.cpu-v1.json` | `14daab17f8d99bd4d5df34c7a9db4972cd8e4eae5dcc5481fbb75fda6782d92c` |
| `validation-plan.cpu-draft-v1.json` | `2eb29c0cbd1e4f0367a4b0059d3f7ef6589a6552c7e50027fa004814d4d7f9ad` |
| `validation-source-review.template-v1.json` | `114c23b1ca922a440416d5b288d963180822b0798b320d6b8ea8b2c62810333d` |
| `validation-dev-promotion-review.template-v1.json` | `3cbffcad9bf019f4288b0a2c5050247634bb7f432dbf858055321fff29aeddad` |
| `validation-authorization.template-v1.json` | `9eeeff195adf9dcfe75f6843f6ffe1be940af9d893d8660c1063b288ff092f45` |

The draft's c2 is illustrative, not a selected release cohort. The draft is unfrozen, references the isolated worktree, and lacks actual promotion/source review and authorization. No template grants authority. The complete packaging references are also in `cpu-validation-packaging-v2.json`.

## Implemented behavior

Entry binds the actual frozen Dev plan SHA `acd2b2c639f7756cdc353b6a7eea8c93a4d735a8ce6ee25838d9502c938d07f0`, the terminal status and root-reviewed `result-v2.json`. The actual external writer `summarize_cohort_cpu_v2.py` SHA is `d9918d9f52e4bb37c9f71e7be09af880a7b6f4723ed9a68566bfda38b363224c`. Its JSONL Dev-only journal snapshot, accepted-cell order, receipts, terminal refs, complete attempt accounting, native counters, auxiliary costs and summaries are checked against the declared schema. Logical/physical status paths may identify the same file, but hashes/content must agree.

All 40 accepted Dev cells, N23 at least 5/10 and at least C0/Q0/N7, substantive QD/ED and exact fixed compute are required. Partial, interrupted, invalid and numerical-futility results cannot enter validation.

A new read-only historical evidence adapter verifies original Dev worker contexts/receipts/processes/native evidence under the actual original source. It does not pretend the evaluation commit equals the Dev commit and does not patch module globals or clone worker code objects. The original four-attempt arithmetic proof is retained by hash and its unchanged prior-lineage helper is reused, together with exact UUID and arithmetic-completeness gates. No additional backend preflight exists in this validation path. Root independently reported that the actual completed C0 Dev receipt matches the inspected receipt schema; no real receipt was read by this executor.

Freshness selection uses frozen seed/init metadata, historical identities, the reconciled registry and all reserved/dispatched identity metadata. One consumed identity excludes its complete cohort; c1 through c4 are considered in order. Historical dispatched validation identities must be reconciled in the registry. Freeze and external release recheck under the private locks. New validation dispatches are registered after the append-only journal write; a missing registration prevents silently continuing after a crash.

The matrix is 2 blocks × 10 tasks × C0/Q0/N23, block/task/arm order. The closed local limits are 60 primary cells, at most two typed whole-episode recoveries, 62 dispatches, 32 GPU-process hours, 1800+40 seconds per worker, GPU7. Existing 478/100 cumulative caps and buckets 51/187/180/40/20 remain unchanged. Complete remaining local capacity and formal reserves must fit.

Validation has its own recovery key/schema and its own two-slot cohort count. The unchanged Dev forensic diagnostic is reused as a leaf; its preexisting derivative-failure mechanism is not modified or expanded. Only the exact completed single Codex timeout condition with accepted independent native evidence can qualify, equally for all three arms. Failed primary costs and unknown usage remain explicit. A valid task failure, another fault, a second retry of a cell, process interruption, whole-worker timeout, exhausted allowance or failed recovery closes the cohort. Original Stage remains Codex managed ChatGPT login with unchanged model/settings; no Poe invocation or fallback is added.

The original same-process worker performs the native arithmetic audit and its full lifetime is metered. Supervisor verification consumes hashes/JSON and never starts CUDA. All 60 first-valid scientific cells are required for validation promotion: N23 at least 10/20 and at least C0/Q0, plus substantive native QD/ED. There is no validation futility or per-episode clipping-activation veto.

Detailed protected reports retain block/task/arm results, paired comparisons, primary/accepted/all-attempt denominators, invalid/recovery attempts, actual observed costs and partial/unknown token limits. The separate aggregate disposition omits task, seed and arm outcomes. It is the permitted input to later mechanism selection. Formal launch remains closed.

## CPU tests and limitations

Final required regression:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.. OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
/home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -p no:cacheprovider -p n23_validation_cpu_pathguard_v1 -q \
tests/test_qd_ed_n23_validation.py tests/test_qd_ed_n23_validation_runtime.py \
tests/test_qd_ed_n23_v2.py tests/test_qd_ed_n23_backend.py \
--basetemp=../n23-v2-guarded-fixtures-validation-regression-v1
```

Result: **474 passed in 46.24 seconds**, zero blocked reads, CUDA uninitialized. The log is `cpu-validation-regression-v1.log`. Earlier passing logs are `cpu-validation-v1.log` (70) and `cpu-validation-v4.log` (117); counts overlap.

Coverage includes actual writer-shaped promotion data, JSONL snapshot and path aliases, source-byte bridge negatives, old routing preservation, fresh-cohort identity checks, missing authorization/capacity/formal reserves, complete frozen plan comparison, historical receipt/backend binding, explicit worker context/command validation, all-arm typed timeout eligibility using existing real runner-format synthetic fixtures, whole-matrix serial supervisor calls, invalid terminal retention after runner raises, failed recovery stop, no resume, block-aware paired denominators and unknown costs.

Failures were retained rather than erased:

- `cpu-validation-v2.log`: a stray plus sign in a newly appended test caused collection failure; zero blocked reads.
- `cpu-validation-v3.log`: three positive fixture cases initially set artifact root equal to output, correctly rejected by ownership.
- `cpu-validation-timeout-v1.log`: fixture native report had not been written; the qpos negative initially used an inapplicable metadata key. The report was written and the actual safety-event violation shape used. Final regression exercises the intended gates.

The initial metadata packaging script wrote `source-manifest.validation.cpu-v1.json` and then the guard blocked its immediate SHA reread, because new JSON outputs outside synthetic basetemp are not general read-whitelisted. It did not read historical/private/protected data. The original file is preserved. Packaging v2 computes hashes from the exact output bytes in memory, retains guard boundaries, verifies all committed source inputs and reports zero blocked reads. No real protected outcome, Stage log or real ledger was consulted by the executor.

The regression ran before a final whitespace-only removal of extra blank lines from newly added Python files. No semantic source change followed it. The committed source/bridge check subsequently passed. `git diff --check` passes excluding the immutable protocol copy's intentional inherited final blank line. Tests use synthetic fixtures/mocks for GPU and runtime processes; they are CPU preparation, not an actual validation run or efficacy result.

## Root handoff and prospective activation

Do not integrate this evaluation commit while Dev is active. Only after actual Dev terminal promotion:

1. Run the original Dev terminal reader under the original source and preserve its real `result-v2.json`, status, all attempts and accepted refs. Create `validation-dev-promotion-review-v1.json` with exact schema `n23-dev-promotion-review-v1`, `disposition=promoted`, `allow_validation=true`, and `dev_plan/dev_status/dev_result/backend_proof`.
2. Review and integrate this exact evaluation commit while owned workers are absent. Recompute the 226-file source record and explicit bridge from the original 214-file Dev plan. Verify the actual historical receipt/backend paths and metadata without consuming protected outcomes.
3. Create `validation-source-review-v1.json` from the template with `disposition=accepted`; it binds source, source_bridge, Dev plan, protocol, original runtime and original backend proof, with `no_execution_release=true`.
4. Under private locks, select the first untouched complete cohort from metadata and record the separate `n23_validation_authorization` key. Exact fields are `schema, cohort_id, seed_cohort, protocol_sha256, dev_review, source_review, run_once, physical_gpu`; schema `n23-validation-authorization-v1`, current cohort, `run_once=true`, GPU7. No budget amendment is made by this code.
5. From owning study_worktree, freeze the final plan with:
   `python scripts/qd_ed_n23_validation_prepare.py --freeze --output <N23>/validation-plan.frozen.v1.gpu7.json`.
6. After rechecking exact capacity/freshness, create the external release required by `qd_ed_n23_validation_supervise.release_check`. Schema `n23-validation-execution-release-v1` binds plan, source_commit, cohort_id, seed_cohort, all episode_keys, limits, dev_review, source_review, backend_proof, physical_gpu, uuid, `validation_authorized=true`, `formal_authorized=false`.
7. Run the serial supervisor using `--plan`, `--release` and an owned `--output-dir`. Preserve detailed protected evidence; later algorithm steering consumes only `aggregate-disposition.json`.

Here `<N23>` is the absolute variant parent. All commands use the existing vla-pilot Python/runtime. No automatic formal release, alternate cohort, extra backend preflight or generic recovery authority is supplied.

Remaining blockers are actual Dev full promotion, independent final root source review, real metadata/capacity checks and separate root validation release. A Dev rejection or invalidity leaves this preparation inactive.

