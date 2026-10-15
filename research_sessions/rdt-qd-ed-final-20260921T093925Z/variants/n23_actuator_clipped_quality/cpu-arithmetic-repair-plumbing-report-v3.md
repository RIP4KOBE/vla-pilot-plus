# N23 arithmetic repair v3: isolated CPU implementation handoff

Status: source frozen for root review; executor has not adopted authority, integrated owning source, changed real state or ledgers, or run CUDA, a model, provider, or simulator.

The two separate commits are:

- Numerical audit correction: `7f908c58ef7d1ed7867de38a505f861d3c22151e`.
- Closed fourth-attempt admission and proof: `51104470983cdbafd08feb87f2f39b7553779405` (final HEAD).

The worktree is `arithmetic_repair_implementation`, branch `codex/rdt-qd-ed-n23-arithmetic-audit-20260930`, clean at final inspection. The earlier N23 implementation remains preserved; conditional validation preparation remains paused.

## Numerical correction and limits

The scientific implementation and original provider normalize the seven weights with a tensor denominator, `weights / weights.sum()`. The independent auditor and two preflight calculations instead used a Python scalar denominator. PyTorch 2.7.1's [CUDA division implementation](https://raw.githubusercontent.com/pytorch/pytorch/v2.7.1/aten/src/ATen/native/cuda/BinaryDivTrueKernel.cu) handles a CPU scalar divisor by multiplying by its rounded reciprocal, while a tensor divisor takes direct division. Those operations can differ in FP32 and cross a subsequent BF16 rounding boundary.

Commit 7f908c5 changes exactly three normalization expressions across two audit/preflight files to use the original tensor denominator. It changes no production policy, provider, controller, Stage logic, descriptor, selector, profile, decoder, executed action, or tolerance. The independent reconstruction remains independent and retains bitwise comparison and corruption rejection. The same corrected auditor is used later inside the metered Dev worker.

The separate report `cpu-arithmetic-correction-report-v1.md` preserves the CPU branch model, fixed BF16 boundary example, historical-function reproduction, layout review and limitations. Its SHA256 is `f1f21ce683222bcb8c62684142fd18a9e841b2909a706afff200cfe6f9689a5f`.

CPU tests reproduce the rejected categories using synthetic values and the faithfully modeled scalar-division branch. They do not emulate every CUDA reduction/layout detail. In particular, the exact original FP32 synthetic GPU rejection was not reproduced under unchanged CPU reductions. The forthcoming actual backend preflight must establish whether this correction is sufficient; no CUDA success is claimed here.

## Closed admission

The new helper `scripts/qd_ed_n23_arithmetic_repair.py` reuses the existing runtime, budget, process ownership, timeout, metering, prior failure, UUID and proof functions. Its public root-review interfaces are `final_review(source, runtime)`, `authority(...)`, `named_failures(events, runner)`, and `source_delta(root)`.

The separately frozen exception is `arithmetic-repair-engineering-exception-v3.md`, SHA256 `bf3f28caf3967c4d3cf4cc6674bdaafd2d54abbdd22f5e9bc676853a12424727`. This is an explicit prospective engineering exception under the continuing autonomous instruction. It does not reuse an exhausted UUID authority.

Exactly three previous charged failures are required:

1. `rdt-qd-ed-final-20260921T093925Z__n23_backend_preflight_v2__7ca117f9b7fb`.
2. `rdt-qd-ed-final-20260921T093925Z__n23_backend_uuid_repair__41eab61a8079`.
3. `rdt-qd-ed-final-20260921T093925Z__n23_backend_uuid_native_repair__839018c768de`.

Their immutable reports, plans, source snapshots, adopted authorities, ordered ledger groups and measured costs remain bound. The third must match the exact recorded complete corpus and mismatch pattern, including the FP32 synthetic failure. Root reported that the new named-failure check passed against actual private records without initializing CUDA; this is root's check, not an executor reading of those records.

The new attempt is limited to 120 seconds plus 40 seconds cleanup on the original GPU7/runtime identity, recovery bucket, with explicit `retry_of` the third attempt. Its episode key is `n23_backend_arithmetic_repair_once`, attempt prefix is `__n23_backend_arithmetic_repair__`, and the existing `N23_BACKEND_PREFLIGHT_V2_20260930` iteration is retained. Reservation consumes this opportunity. Any other backend attempt, prior Dev reservation/dispatch, missing authority, or lineage mismatch blocks. Four total backend attempts are permitted; no fifth opportunity exists in this code.

The cumulative cap remains 478 attempts / 100 GPU hours, with buckets baseline51, development187, validation180, formal40, recovery20. Existing admission checks require the entire remaining Dev allocation, bounded preflight and protected 32/12-hour reserves to fit. No protected reserve is borrowed. Validation and formal authorization remain false.

Successful proof requires all 176 real BF16 batches of 16 candidates plus FP32 and BF16 synthetic batches of four candidates, explicit accepted/empty-mismatch/production-helper/independent/negative-control fields and wrong-bounds rejection. Existing exact arithmetic checks remain unchanged. The proof binds actual metered terminal/process/report, corpus hashes, current native UUID evidence, runtime, final source bytes and commit. Future Dev must use that exact source; no unmetered CUDA re-audit occurs in the supervisor.

## Source closure

The source record contains 214 files:

- Canonical source-record SHA256: `44bcd54ababf263a83985bc4d72c843615794c831020fdcf344319c3b85c3759`.
- `source-manifest.arithmetic-repair.cpu-v1.json` file SHA256: `7ad0c538150e34264e875fc8fe37a1dbdb7b40c1406161b681a4e1baaa99cb23`.

All source entries matched committed bytes. The source-delta gate passed. Relative to `fbe5ac996467e00fcbc7a1d7e5f24659725f6b3d`, the changes are limited to:

- `scripts/audit_decision_evidence.py`.
- `scripts/qd_ed_n23_backend_preflight.py`.
- `scripts/qd_ed_n23_arithmetic_repair.py`.
- `scripts/qd_ed_n23_v2_contract.py`.
- `scripts/qd_ed_n23_v2_backend.py`.
- `scripts/qd_ed_n23_v2_preflight_admit.py`.
- `scripts/qd_ed_n23_v2_prepare.py`.
- `tests/test_qd_ed_n23_backend.py`.
- `tests/test_qd_ed_n23_arithmetic_repair.py`.
- The tracked exact copy of the v3 exception.

The correction file hashes are fixed by the helper:

- Auditor: `8c47a4d90fbec4e22329bdab7d53fddc2d01e88c742352e4f9e01a65d1dc8182`.
- Preflight arithmetic: `fbdd30ac1864ea9d282ce849f45faddda4738c6a5f092351e08bd0d2d13795be`.

The core, configs, main.py, worker, UUID backend and both earlier UUID repair helpers are byte-identical to fbe5ac9. `cpu-arithmetic-repair-plumbing-v3.patch` preserves the plumbing diff after the separate arithmetic commit. The static routing uses the existing provenance field `uuid_repair` with the distinct `n23-arithmetic-repair-binding-v3` schema; authority is not interpreted through the old UUID schemas.

## CPU verification

From the isolated worktree, use this command prefix:

```bash
PYTHONPATH=.. OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -p n23_arithmetic_cpu_pathguard_v1 -q
```

The exact test suffixes and retained logs are:

| Scope | Test suffix | Result | Log |
|---|---|---|---|
| Numerical correction | `tests/test_qd_ed_n23_backend.py --basetemp=../n23-v2-guarded-fixtures-arithmetic-correction-v1` | 147 passed, 33.52s | `cpu-arithmetic-correction-v1.log` |
| Initial complete affected routing and v2 regression | `tests/test_qd_ed_n23_arithmetic_repair.py tests/test_qd_ed_n23_uuid_native_repair.py tests/test_qd_ed_n23_uuid_repair.py tests/test_qd_ed_n23_v2.py --basetemp=../n23-v2-guarded-fixtures-arithmetic-plumbing-v1` | 420 passed, 14.52s | `cpu-arithmetic-plumbing-v1.log` |
| Final success-proof completeness change, affected suites only | `tests/test_qd_ed_n23_arithmetic_repair.py tests/test_qd_ed_n23_uuid_native_repair.py tests/test_qd_ed_n23_uuid_repair.py --basetemp=../n23-v2-guarded-fixtures-arithmetic-plumbing-v2` | 235 passed, 9.11s | `cpu-arithmetic-plumbing-v2.log` |

Counts overlap and are not additive. All runs had zero denied reads and CUDA remained uninitialized; `git diff --check` passed. The CPU composition covers synthetic repaired preflight, valid metered proof and unchanged 40-cell Dev planning, with negative source/runtime/authority/lineage/attempt-limit/proof gates and timeout/error accounting. Its process/arithmetic stubs do not constitute real CUDA validation.

The executor read only the specifically authorized root arithmetic-failure summary, not its referenced real terminal, ledger, report bodies or protected outcomes. Synthetic guards remained enabled; no legacy real-data recovery tests were run in this task.

## External review and authority templates

The templates are deliberately non-executable and are outside the committed source manifest, avoiding circular hashes.

- `final-source-runtime-review.arithmetic-repair.template-v3.json`: SHA256 `6de8fc028051b9ff9471e055c3bdff815defd6deea068706780289124ac5a8f2`. Its disposition is `ROOT_REVIEW_REQUIRED`.
- `arithmetic-repair-authority.template-v3.json`: SHA256 `f882135148be4c8bbb0c0d954d21d7e05f2b9abdfdc203760207d8ebead6e0f4`. It contains explicit unfilled review/interpretation/time placeholders.

The exact accepted review schema is `n23-final-source-runtime-review-arithmetic-repair-v3`, with keys `schema, disposition, source, runtime, dev_protocol, backend_protocol, amendment, timeout_observability, exception, failed_review, prior_failure, audit_correction, no_gpu_release`. Disposition must be `accepted`, source/runtime exact, references hash-bound, and `no_gpu_release=true`. Root writes it to `final-source-runtime-review.arithmetic-repair.v3.json`.

The authority schema is `n23-arithmetic-repair-authority-v3`, with exact keys `schema, exception, failed_review, prior_failure, final_source_review, source, runtime, authority_interpretation, recorded_at, user_message, cumulative_caps, limits, validation_authorized, formal_authorized`. User message equals the frozen autonomous instruction. Both protected authorization flags are false. Limits contain one additional backend attempt, 120/40 seconds, GPU7, recovery bucket and four total backend attempts. Root writes `arithmetic-repair-adoption-v3/authority.json` and adopts only its `{path, sha256}` under private state key `n23_arithmetic_repair_authority`, preserving all prior authorities. No executor adoption was performed.

## Root-only prospective activation

1. Integrate the final exact commit while owning workers are absent; independently verify source/runtime, immutable protocols, the three actual settled failure groups and costs, no Dev reservation, available capacity and the preserved Codex managed-login contract.
2. Create the accepted external final review, then the finite authority; adopt its exact reference under existing private locks. Do not overwrite earlier plans/reviews/proofs.
3. From owning study_worktree, freeze the distinct new plan:

```bash
/home/hynx/miniconda3/envs/vla-pilot/bin/python scripts/qd_ed_n23_v2_prepare.py --kind arithmetic-repair --freeze --output <N23>/backend-preflight-plan.arithmetic-repair.frozen.v3.json
```

4. Execute the one metered attempt through the existing admission process:

```bash
/home/hynx/miniconda3/envs/vla-pilot/bin/python scripts/qd_ed_n23_v2_preflight_admit.py --plan <N23>/backend-preflight-plan.arithmetic-repair.frozen.v3.json
```

5. Only if that attempt yields a valid bound `backend-proof-reference.json`, freeze the unchanged N23 v2 Dev plan with `--kind dev --freeze --backend-proof <attempt>/backend-proof-reference.json --output <N23>/plan.frozen.v2.gpu7.json`, then use the existing v2 supervisor after its normal gates. The 40 primary scientific cells, at most two strictly typed whole-episode recoveries, first-valid denominator and full-quad futility rules are unchanged.

Here `<N23>` is the absolute variant parent, not a literal argument. If the fourth actual preflight fails, preserve its full failure and charge; this exception authorizes no further attempt. Subsequent diagnosis must not relax the exact arithmetic or silently reuse old authority.

