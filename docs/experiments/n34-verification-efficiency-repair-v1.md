# N34 node15.4 bounded verification engineering repair

Authority: `verification-efficiency-repair-v1/authority-v1.json`, bound diagnosis
SHA-256 `4e5ceb24e168cda216cd5f7437f2aa46138a7712209d8097e5086038367f127b`.
Executor base `60fc00a55b1b8dfb5c98b52e92d979b0869b4cad` and owning adopted
`3acfda1adea7b4d9880c81dab7e3882f1587d4d0` both have tree
`5e7aac297eae0eff83e5a3842f6a86278586f98f`.

## Change and boundaries

Source records now inventory each selected Git tree once and read selected blobs
in one local `cat-file --batch` per database. Each call resolves the registered
submodule database and superproject gitlink pin afresh. Dependency HEAD is never
used. Git retains `--no-replace-objects` and `GIT_NO_LAZY_FETCH=1`. Exact tree path,
regular mode/blob type, batch object identity/type/length, object content digest,
local path containment/symlink checks, and byte equality all fail closed. Canonical
record fields, sorting, SHA-256 commitments and commit binding remain unchanged.
Batch data exists only within the call; there is no persistent positive cache.

Each release transaction still validates caller-supplied detached release, root
review, authority and protocol references, full operational/scientific closure,
loaded source, runtime closure, controller semantics, runtime files/inputs and
all 30 independently hashed manifests. Its private row checker omits only the
already-completed shared closure work. No skip flag or reusable verification token
is exposed. Public `verify_manifest`, `validate_release`,
`verify_prospective_release`, `validate_context`, `run_worker` and
`_run_in_process` remain validating entrypoints. Context validation consumes its
selected manifest from its own complete release transaction, never a candidate
receipt or a previous invocation.

The worker's pre-gate and post-gate validations remain separate transactions.
The immediately redundant `run_worker` check is removed; `_run_in_process` owns
that check. Both post-Main and post-native-audit context checks remain. Runtime
and loaded-module before/after attestations, native audit code, receipt acceptance,
scientific configuration and the 1800-second episode bound are unchanged.

Flushed stderr JSON begins before worker project imports, then identifies context,
release, source/runtime closure, runtime files/inputs and all-manifest verification
with monotonic elapsed time and failure markers. These diagnostics have no
acceptance field and are never consumed as authority, a start receipt or scientific
evidence. Output paths are not taken from an unvalidated context for diagnostics.

## Focused validation

Run from the isolated production worktree, using the existing
`/home/hynx/miniconda3/envs/vla-pilot/bin/python`:

```bash
env CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 timeout --signal=TERM --kill-after=10s 180s python -B -m pytest -q -s tests/test_n34_verification_efficiency.py tests/test_n34_dependency_source.py tests/test_n34_worker_entrypoint.py tests/test_n34_release_boundary.py::test_public_consumer_reaches_next_gate_only_after_full_release tests/test_n34_release_boundary.py::test_no_context_release_is_never_a_draft_fallback tests/test_n34_release_boundary.py::test_missing_external_reference tests/test_n34_release_boundary.py::test_real_cli_fails_closed_without_parent_gate_or_side_effects > ../verification-efficiency-repair-v1/focused-tests-v1.log 2>&1
```

Exit 0: **85 passed in 42.43s**. `git diff --check` also exited 0.
The small legacy oracle produced identical canonical records. Both 10-file and
50-file fixtures used exactly 14 Git calls and 3 blob batches (superproject plus
two pinned databases), demonstrating database-scaled rather than file-scaled calls.

Tests exercise changed source after success, both dependency pins/databases,
missing/linked/traversal paths, bad object IDs/types/modes/content/framing,
changed runtime and loaded-module bytes/origins, all-row checks including an
unselected manifest, missing detached authority, gate-time mutation, wrong real
`-m` entrypoint spec/origin/hash, and early phase emission. Synthetic release leaf
stand-ins test orchestration only; they are explicitly not real release acceptance.
No broad historical suite, model/simulator execution or GPU dispatch was run.

## Full measurement limitation and next root review

No full production release verification was attempted. Modified operational source,
new test/docs inventory and the new commit cannot be accepted against the old
source-bound release. Root must independently review/adopt the engineering diff
and, if authorized, prepare newly anchored source/plan/review/detached release
artifacts. Old frozen authority is not rewritten. This repair grants neither a
recovery identity nor GPU admission.

After those prerequisites, root may run the following **single** CPU measurement
from the exact newly released checkout. Substitute independently trusted plan and
release paths and SHA-256 digests; do not derive trusted digests from candidate
receipts. The 600-second measurement bound is separate from the unchanged
1800-second episode bound. The command calls only the full release verifier and
never the worker, Main, model or simulator:

```bash
env CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 timeout --signal=TERM --kill-after=10s 600s /home/hynx/miniconda3/envs/vla-pilot/bin/python -B -u -c 'import json,sys,time; started=time.perf_counter(); print(json.dumps({"phase":"cpu_release_measurement","event":"begin"}),flush=True); from scripts.qd_ed_n34_release import verify_prospective_release; verify_prospective_release({"path":sys.argv[1],"sha256":sys.argv[2]},{"path":sys.argv[3],"sha256":sys.argv[4]}); print(json.dumps({"phase":"cpu_release_measurement","event":"end","elapsed_seconds":time.perf_counter()-started}),flush=True)' "$N34_REVIEWED_PLAN_PATH" "$N34_TRUSTED_PLAN_SHA256" "$N34_REVIEWED_RELEASE_PATH" "$N34_TRUSTED_RELEASE_SHA256" > "$N34_CPU_MEASUREMENT_LOG" 2>&1
```

Record the exact command, trusted references, exit status and phase log; a timeout
is an incomplete measurement. Review retained audit boundaries and source/runtime
binding independently before any further admission decision. The old invalid
`n34_dev_t00_c0_20261008` attempt and its entire 1800.0657490990125-second charge
remain intact. Any recovery still requires a separate finite prospective identity,
linkage and budget/reserve arithmetic plus fresh GPU7 admission. There is no claim
of scientific success or recovery authorization.
