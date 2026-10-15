# N34 node15.4 verification-efficiency repair

Committed scoped engineering repair: `83b4ceba312835410200713e3d65a03de89f0931`.
Tree: `9870d48409d0402c1caac56706507adadc11d340`. Isolated worktree clean.
No scientific success, release/adoption, recovery authorization or GPU admission is claimed.

## Authority and integrity

Authority SHA-256: `1cab57bcc8baa1b267ad9fba41238b993084c8751806f7d63a20d4ade935f801`.
Bound diagnosis SHA-256: `4e5ceb24e168cda216cd5f7437f2aa46138a7712209d8097e5086038367f127b` (matches authority).
Executor base `60fc00a55b1b8dfb5c98b52e92d979b0869b4cad` and owning adopted `3acfda1adea7b4d9880c81dab7e3882f1587d4d0` both resolve to tree `5e7aac297eae0eff83e5a3842f6a86278586f98f`.
Binary Git diff SHA-256 (`git --no-replace-objects diff --binary 60fc00a55b1b8dfb5c98b52e92d979b0869b4cad HEAD`): `9474d7f67011453a78db65db6ed9b579b5c58b45a59dc70d9df03f69be5027a4`.

## Changed files (SHA-256)

- `docs/experiments/n34-verification-efficiency-repair-v1.md`: `0735d851443fa43f1b1cf2ccb51d753e5560da42ccea3e6f2f8af49c1da7bf6d`
- `scripts/qd_ed_n34_bridge.py`: `b06361ce3f7cf980f9a028fd4fe61376c60530ea557bd6ebdfaee419873bfa63`
- `scripts/qd_ed_n34_release.py`: `6b643500e5d9e1107b3bac49335d84de8a8a914b89628ebafc497bb714bdd2b8`
- `scripts/qd_ed_n34_source.py`: `e59d4f523a66318cabd3bdbd98f876f6769e4b9e6516a303db099eaf0fed6a65`
- `scripts/qd_ed_n34_worker.py`: `b24610f6bde8c00f08b964a7aeb729330b9107f2142938c4804c5b9df6eea265`
- `tests/test_n34_release_boundary.py`: `0e1e2ba21381a09a9f217bda05a84fca09f3bf79c7e3afd66fcf70a635057cbb`
- `tests/test_n34_verification_efficiency.py`: `fedb81c0894175eea70c6755daea5ebb19c4e012dd98e52e7d461a87b6fea6d9`

## Implementation and preserved boundaries

Git source records use one recursive exact tree inventory and one local blob batch per selected object database. Root, superproject commit/gitlink, registered database and pinned dependency commit remain binding. No dependency HEAD, replacement object or lazy fetch is used. Exact paths, regular modes, blob types, response identity/framing, object content digest, symlink rejection and local byte comparisons are checked. Record schema/order/digests remain canonical. No persistent positive cache exists.

A release transaction validates the complete authority/source/runtime/input closure once, then checks every row against its independently trusted manifest reference using a private row-only helper. A context uses its selected manifest from that same newly completed transaction. Public manifest and release/context entrypoints remain fully validating, and changed bytes are rechecked on independent calls. There is no candidate receipt trust or public skip flag.

The worker retains full transactions before and after the parent gate. Only the duplicate immediate wrapper validation was removed. Both post-Main and post-audit context checks, runtime/loaded before-after receipts and native audits remain unchanged. An AST comparison confirmed 13 execution/audit/runtime functions are identical to the executor base.

Flushed stderr phase JSON begins before project imports and before expensive release validation. It records monotonic timing and failures; it has no acceptance field and is never consumed as authority or scientific success.

## Exact focused commands and results

Working directory: `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n34_observed_jaw_approach/production_worktree`.
Existing Python: `/home/hynx/miniconda3/envs/vla-pilot/bin/python`.
CUDA hidden; OMP/MKL/OpenBLAS/NumExpr threads set to 2.

```bash
env CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 timeout --signal=TERM --kill-after=10s 180s python -B -m pytest -q -s tests/test_n34_verification_efficiency.py tests/test_n34_dependency_source.py tests/test_n34_worker_entrypoint.py tests/test_n34_release_boundary.py::test_public_consumer_reaches_next_gate_only_after_full_release tests/test_n34_release_boundary.py::test_no_context_release_is_never_a_draft_fallback tests/test_n34_release_boundary.py::test_missing_external_reference tests/test_n34_release_boundary.py::test_real_cli_fails_closed_without_parent_gate_or_side_effects > ../verification-efficiency-repair-v1/focused-tests-v1.log 2>&1
```

Exit 0: **85 passed in 42.43s**. Log SHA-256: `6d288d6e57cbf08f0ed17c4b4ebac18de78b139d6566b5a388ee3bc9ceab3963`.
No broad historical test repeats. Adversarial coverage: Changed regular/dependency source after a prior successful check; Blob ID/type/size/content/truncation/trailing/missing response; Tree path/type/mode; actual wrong gitlink and tree-as-pin; Missing/linked/traversal paths and absent registered database/object; Wrong runtime bytes and loaded-module path/content; Modified unselected manifest bytes and semantics; Missing independently trusted detached authority; Wrong real -m worker entrypoint spec/origin/file/hash; Source mutation while parent gate waits.
Release orchestration tests use explicitly synthetic environment leaves, not usable production approvals.

Small legacy and new algorithms produced identical canonical records. Both 10-file and 50-file fixtures took **14 Git calls and 3 blob batches** over three databases. Each context transaction performs one source/runtime closure and checks all 30 manifests. The two worker pre-Main transactions preserve the parent-gate boundary. These are structural/call-count results, not an end-to-end production speedup claim.

```bash
git diff --check
git diff --cached --check
```

Both exit 0 with no output. The staged check ran immediately before commit.

```bash
env CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 python -B - <<'PY'
import ast, subprocess
from pathlib import Path
base = '60fc00a55b1b8dfb5c98b52e92d979b0869b4cad'
checks = {
    'scripts/qd_ed_n34_worker.py': ['_run_in_process', 'attest_worker_loaded', 'verify_receipt', 'native_counts', 'audit_native'],
    'scripts/qd_ed_n34_source.py': ['_runtime_file', '_live_source', '_generated_runtime', 'attest_loaded', 'verify_runtime', 'attest_runtime', 'attest_runtime_receipt', 'verify_runtime_receipt'],
}
for path, names in checks.items():
    before = ast.parse(subprocess.check_output(['git', '--no-replace-objects', 'show', base + ':' + path]))
    after = ast.parse(Path(path).read_bytes())
    for name in names:
        old = next(n for n in before.body if isinstance(n, ast.FunctionDef) and n.name == name)
        new = next(n for n in after.body if isinstance(n, ast.FunctionDef) and n.name == name)
        assert ast.dump(old, include_attributes=False) == ast.dump(new, include_attributes=False), (path, name)
print('PASS: 13 execution/audit/runtime function ASTs identical to executor base.')
assert not subprocess.check_output(['git', 'status', '--porcelain']).strip()
print('PASS: committed isolated worktree clean.')
PY
```

Exit 0:
```
PASS: 13 execution/audit/runtime function ASTs identical to executor base.
PASS: committed isolated worktree clean.
```

## Full CPU measurement limitation

**No full production verification measurement was attempted (zero attempts).**
Modified source, added source-inventory members and a new commit require fresh independently reviewed source-bound authority. Frozen release authority was neither forged nor rewritten. A valid old-release timing cannot establish acceptance of this repair.

After independent root review/adoption and appropriate newly anchored plan/review/detached release, root may run one bounded measurement from that exact checkout. Set paths and hashes from independent trusted authority, not from candidate receipts:

```bash
env CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 timeout --signal=TERM --kill-after=10s 600s /home/hynx/miniconda3/envs/vla-pilot/bin/python -B -u -c 'import json,sys,time; started=time.perf_counter(); print(json.dumps({"phase":"cpu_release_measurement","event":"begin"}),flush=True); from scripts.qd_ed_n34_release import verify_prospective_release; verify_prospective_release({"path":sys.argv[1],"sha256":sys.argv[2]},{"path":sys.argv[3],"sha256":sys.argv[4]}); print(json.dumps({"phase":"cpu_release_measurement","event":"end","elapsed_seconds":time.perf_counter()-started}),flush=True)' "$N34_REVIEWED_PLAN_PATH" "$N34_TRUSTED_PLAN_SHA256" "$N34_REVIEWED_RELEASE_PATH" "$N34_TRUSTED_RELEASE_SHA256" > "$N34_CPU_MEASUREMENT_LOG" 2>&1
```

The 600-second subprocess timeout is only a CPU measurement bound; the episode limit remains 1800 seconds. Record exact references, command, exit status and phase log. Exit 124/137 or a missing end marker is an incomplete measurement. The command invokes only release verification, not the worker, Main, a model or a simulator.

Other limitations: source batching retains selected blob bytes in memory per database; synthetic tests do not attest the installed full runtime; original timeout phase remains unknown. Early diagnostics cover future authorized execution only.

## Preservation and next root steps

No owning checkout/state/ledger, coordinator lock, frozen protocol/release/plan, scientific algorithm/threshold or native/runtime audit was modified. No GPU/model/simulator dispatch, validation/formal result access, prohibited design-document read, credential-file access, Superpowers use or additional agent launch occurred.

The diagnosis's old `n34_dev_t00_c0_20261008` INVALID_STOP and full **1800.0657490990125 seconds** remain charged; no attempt/ledger bytes were read or rewritten here.

1. Independently review commit, seven-file diff, hashes and focused CPU evidence; specifically inspect private row-check call sites and retained before/after audit boundaries.
2. Review/adopt only the bounded engineering change into owning source; do not mutate old releases, attempt identity, charges or frozen protocols.
3. If separately authorized, prepare newly source-bound prospective plan/review/detached authority and execute one bounded CPU full verification with the supplied command.
4. Any recovery requires its own finite prospective amendment/identity linked to the invalid attempt, protected-reserve budget arithmetic, independent review and fresh GPU7 admission.

This artifact reports engineering completion only. It neither authorizes recovery nor reports scientific success.

