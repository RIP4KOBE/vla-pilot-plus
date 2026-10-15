# Immutable source-byte cache: CPU preparation only

Status: UNWIRED_CPU_PREPARATION_ONLY. No experiment, historical Git object, production helper, live state, runtime proof, GPU, API, model or simulator was accessed. No existing research source was edited and no integration is authorized. Performance on the actual validation path is unmeasured.

The component is `verified_immutable_cache.py` (SHA-256 `f580ea88186b82364f14c4e8b2afbfa613e38a3a89683b0e2103fbe2e360675a`). Its only dependencies are Python's standard library; it performs no filesystem, subprocess, network or Git operations.

## Contract

`ObjectKey` fixes all six identity fields: repository identity, full lowercase 40- or 64-hex commit ID, canonical relative POSIX path, expected SHA-256, declared size and verifier/source-bridge version. Mutable labels, traversal, malformed identities and duplicate allowlist entries are rejected. Repository identity is an exact opaque string, not automatically resolved; the future adapter must bind it to the reviewed repository. The finite allowlist is copied, so later caller list mutations cannot authorize keys.

`VerifiedImmutableCache(allowlist, ...).get(key, loader)` returns exact immutable `bytes`. Defaults and hard maxima are 2,048 entries, 1 MiB per object and 64 MiB retained bytes; callers can choose smaller limits. On misses, declared capacity is checked before invoking the loader. Actual length and SHA-256 must pass before insertion. Failures retain no entry and do not poison a later independent retry. There is no eviction, persistence, discovery or environment fallback. Zero-length verified objects are valid entries.

A nonblocking lock is held through the callback and verification. Reentrant or concurrent access, including a statistics snapshot during a callback, raises `CacheBusy`; it never invokes a nested loader or reserves a second object's capacity. Both an uncaught nested failure followed by a successful retry and a caught nested failure followed by a capacity refusal are tested. A two-thread synthetic check also verifies concurrent refusal.

`stats()` returns an immutable snapshot: admitted requests, hits, loader attempts, verified/failed loads, pre-load refusals, retained object/byte counts and observed bytes returned by callbacks. Busy refusals are outside these counters because they cannot acquire the state lock. Cumulative returned bytes can exceed retained capacity after failed loads; this is traffic accounting, not an allocation/I/O bound.

The callback is trusted to enforce its own finite reads before allocation. This cache cannot constrain arbitrary callback side effects or allocations. An oversized returned value is rejected before hashing or retention, but already exists at that point. The future adapter must also ensure its allowlist denotes reviewed historical source objects: this component has no semantic classifier for arbitrary byte contents, no live-verdict API and no execution authority. Dictionaries/booleans/views/mutable byte arrays are not acceptable values.

## Responsibilities that remain live

This cache must never supply an admission PASS, current working-file digest or HEAD resolution, journal subset/current reservation, missing-file assertion, process cleanup conclusion, budget or provider/GPU decision. Future integration must retain each dispatch's fresh working-source/import/identity and plan/runtime checks, current authority and relevant journal/resource reconciliation, reservations and protected-budget admission, process/lock/GPU ownership and device checks, and the frozen current-Codex-login transport checks. Poe remains unused. Historical source equality and source-bridge verification cannot be replaced by an unreviewed key or an old whole-validation PASS.

The future adapter owns bounded object I/O, trusted manifest provenance, repository/commit identity and these live checks. Root review and a separately frozen integration are prerequisites; no production loader is supplied here.

## Synthetic verification and retained failures

Final run: **49 passed**, pytest test body 0.02 seconds; guard had **zero denied operations**, CPU affinity was 2, CUDA was hidden and Torch was not imported. Four startup/test runs used **0.5168208191171288 seconds in aggregate**, below the 120-second cap. All inputs were in-memory synthetic bytes. Coverage includes identity separation, finite allowlists, immutable returns/statistics, wrong hash/size/type, callback exceptions, retry integrity, entry/object/retained limits, pre-callback refusal, zero-byte hits, counters, reentrancy, concurrency and rejection of live-verdict-shaped values.

All earlier failed runs remain in the one append-only `cpu-checks.log`:

1. Run 1 (0.105275563 s) and run 2 (0.104199918 s) were guard-blocked at an open of the owned preparation directory before tests. The first two logs did not record open mode/flags, so their exact operation is not directly preserved. Allowing only a read-only directory open did not resolve it. Static inspection of installed pytest's `_pytest/capture.py` showed `FDCapture` constructs `TemporaryFile`; disabling capture with `-s` removed this startup issue. No temporary-file write permission was added.
2. Run 3 (0.160579739 s) executed 49 test assertions, but attempted bytecode-cache probes and pytest's final same-directory restoration were denied. It is **not** guard-clean acceptance.
3. Final run (0.146765599 s) preloaded only the two owned source files from bytes, used `--assert=plain`, and allowed restoration solely to this owned directory. No `__pycache__` path was opened to the guard. Assertions remained active; the cache implementation was unchanged across these runs.

The guard also blocks subprocess/network operations, external writes, forbidden imports and reads outside owned files or the standard Python/pytest installation. It is an execution boundary for these synthetic tests, not a sandbox guarantee against malicious callbacks. Test plugin autoload, pytest's cache, capture and bytecode writes are disabled. No temporary fixtures or directories are produced.

Exact invocation, with this preparation directory as cwd:

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -B run_cpu_checks.py >> cpu-checks.log 2>&1
```

The harness accounts prior log summaries before a rerun and refuses an unsettled prior run or an exhausted cumulative test budget. Reproduction appends to the log and therefore requires a new delivery manifest afterwards.

## Delivery boundary

Seven regular files including the unchanged root protocol are delivered; total size is recorded in `manifest.json` and is below 1 MiB. The manifest hashes the six other files and deliberately excludes itself. It contains the complete test timing/guard history and explicit no-integration status. No worktree or additional protocol was created. No production-source performance benchmark was run.

