# N32 bounded STOP-path repair

Completed CPU-only repair in the isolated implementation checkout.

Parent: `34c6f219af1829b2d929850a652af6607ed6b258`  
Commit: `abbdb396439094f034cd859d2d88217072f209d3`

`stop_path()` now resolves `<session>/study_worktree` and `<session>/variants/<variant>/implementation_worktree` to `<session>/autonomy_20261004/STOP`, rejecting other layouts with ValueError. STOP itself is not resolved, preserving rejection of dangling symlinks. Layout acceptance grants no execution authority.

The only production change is in `scripts/qd_ed_n32_contract.py`. Tests in `tests/test_n32_release.py` cover both layouts, seven unsupported layouts, absent STOP, files, live symlinks and dangling symlinks. `tests/test_n32_production.py` uses an owning-layout synthetic fixture and verifies execute_one refuses owning STOP before device probing or process dispatch, leaving the attempt ledger empty. Existing release and admission gates remain intact.

Validation: **160 passed**, six warnings, 47.48 seconds; exit **0**. Warnings originate from existing dependency/source code. `git diff --check` passed. No broader rerun was needed.

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 TMPDIR="$PWD/../stop-path-repair-v1" timeout 600 bash -c 'ulimit -t 1200; exec python -m pytest -q -p no:cacheprovider tests/test_n32_release.py tests/test_n32_release_worker.py tests/test_n32_production.py' > ../stop-path-repair-v1/test-logs/focused-n32.log 2>&1
```

Log SHA-256: `96eb9cdd5c2723888ad01c19ba11dd939b794eb7d411e883b4fbb9b0127db712`.

Original disabled draft and all 30 expected manifest hashes match their existing references; see `preservation-v1.json`. No owning state, source, tree, ledger, driver or lease changes were made. Scientific semantics, thresholds, identity, budgets and N31 are unchanged. No real release or authorization was generated. No additional integration blocker was discovered within this repair.

Remaining prerequisites:

- Root review and adoption into the owning checkout (not performed here).
- Root must compose and validate prospective protocol, authority arithmetic, source/runtime/task manifests and detached release against the actual adopted checkout before dispatch.
- GPU execution remains unauthorized by this delivery; native GPU latency, provider usage and fresh matched N32 efficacy remain unmeasured.

`result-v1.json` records changed-file hashes, parent/commit, test command/exit/log hash and resource constraints. The implementation checkout is clean and committed.
