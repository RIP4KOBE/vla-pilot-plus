# Bounded Git blob loader — CPU component only

The small loader is implemented and synthetically verified. No production adapter, real historical-object inventory, current-study Git read, controller integration, experiment/authority/state change, or GPU/API/model/simulator call occurred. The protocol remains SHA256 `95f89526965053844a56a851a642006cceefd3ed170e8c6d3fd4c923ee40e2f5`.

`bounded_git_blob.py` accepts an explicit canonical Git directory and its `(device,inode)`, an explicit objects-directory `(device,inode)`, repository/verifier keys, and an immutable allowlist of exact commit/path/SHA256/size tuples. There is no HEAD/branch discovery. SHA-1 commit IDs are supported; `commit^{commit}:path` enforces a commit object. Conservative ASCII relative paths include ordinary dotfiles but reject traversal, newline, colon, backslash, whitespace and leading-option names. No shell is used. The caller must obtain the binding/inventory from independently reviewed evidence; this module cannot discover or authorize either.

Both `core.bare=true` and `false` are supported. The loader operates directly on the supplied Git directory, not a discovered worktree. It checks a bounded minimal core config with no includes, remotes, helpers or extensions; global/system config, replace refs, inherited Git/loader variables, lazy fetching and network protocols are disabled. Known alternates/shallow layouts are refused. Canonical directory identities are rechecked on each miss. Unsupported normal repository layouts/configuration remain an explicit compatibility gap, not permission to fall back to an old unbounded reader.

The supported repository and local executable must be trusted and quiescent. This is not a security sandbox for an adversarial concurrently modified Git object store: inode/config checks are not a recursive immutable filesystem attestation. Future worktree/common-directory binding, object-store provenance, executable trust and release-time live checks remain the future adapter's responsibility. No claim is made that this study's actual repository currently satisfies this restricted contract.

## Bounded I/O and failures

- Declared size must be an integer in `[0,1048576]` before spawn, including on direct calls. Allowlist cap is 2048 entries. Repository config is at most 4096 bytes and bounded before reading.
- One local `git cat-file --batch` process per miss, argument vector only. Request is bounded and written nonblocking; a partial write fails closed. No automatic retry, fallback, disk cache, or decision cache exists.
- Header cap is 128 bytes. The reported object ID/type/decimal size must be well formed and the type exactly `blob`; size must equal the declaration before body accumulation. Body reads are bounded by remaining length and a one-byte trailer/excess sentinel. EOF, exact final newline, no extra output and exit code zero are required.
- Stderr is drained without retaining or printing its payload, with a 65536-byte cap plus one rejection sentinel. Even nonempty in-bound stderr rejects the load. Stdout/stderr are multiplexed to avoid pipe deadlock.
- Child deadline is finite and at most 5 seconds. Failure terminates/reaps only the Popen-owned child, allowing at most 0.25 seconds after TERM and 0.75 after KILL; failure to reap raises rather than certifying cleanup. All streams close. Process creation/OS scheduling are not claimed hard-real-time guarantees. No process-group or unrelated-PID kill occurs.
- A nonblocking instance lock rejects concurrent/reentrant calls. Failed loads are not retained. A later explicit caller request is distinct from an automatic retry.

Returned values are exact immutable `bytes`. The accepted cache was loaded from the unchanged source with SHA256 `f580ea88186b82364f14c4e8b2afbfa613e38a3a89683b0e2103fbe2e360675a`; it independently verifies actual size/SHA256 and retention limits. A real local-Git synthetic blob plus cache composition succeeds, and the second lookup is a warm hit with loader spawn_count still 1. Deliberately wrong SHA256 fails in the original cache and retains nothing. No whole-PASS or live-admission result is cached.

## CPU evidence and retained failures

All repositories were freshly created under this preparation's `fixtures/` using `git init --bare --template=<owned empty directory> --object-format=sha1`; fixture objects/commits are synthetic, not actual study history. Controlled fake children cover malformed/type/missing headers, oversize/mismatched lengths, short/missing/wrong trailers, immediate and delayed excess, stderr errors/overflow, nonzero exit, normal timeout, TERM resistance and closed pipes with a still-live child. Tests verify reap/closed streams, a maximum 1 MiB body, split output, empty blob, repository/object inode drift, unsafe config/alternates, identity/path/size/deadline rejection before spawn, inherited-environment isolation and reentry. Dotfile acceptance and all affected path-injection negatives received a final targeted check.

| Run | Outcome | Wall seconds | Unexpected guard denials |
|---|---|---:|---:|
| `cpu-run-01` | Retained fixture defect: a class `run` path shadowed unittest.run; 0 tests executed | 0.0445672540 | 0 |
| `cpu-run-02` | 54 passed / 3 fixture-construction errors: duplicate `commit` argument prevented those rejection assertions | 1.1624605870 | 0 |
| `cpu-run-03` | 63 passed after fixture fixes | 1.2400474850 | 0 |
| `cpu-run-04` | 10 affected path tests passed, including new dotfile support | 0.0646338330 | 0 |

There are **64 distinct passing tests** across the final full and targeted matrices. All four logs, summaries and synthetic repositories are retained; earlier failures are not counted as passing coverage. Total test wall time, including failures/setup/child probes, was **2.5117091590 seconds** of the 120-second cap. CPU affinity was restricted to two CPUs, thread variables to two, CUDA visibility empty, and Torch was never imported. Each run's three intentional negative guard checks rejected an outside read, socket construction and unapproved child launch. All unexpected denials were zero.

The Python audit guard restricts reads/writes to this preparation, exact accepted-cache source (read-only), standard interpreter dependencies and /dev/null; process launches are restricted to local Git and the fixed synthetic-child script in owned fixture working directories. Git's internal native syscalls are not intercepted by that Python hook; the fixture paths, sanitized Git environment/config and permitted fixed commands establish the test boundary. This is not presented as an OS sandbox or proof about arbitrary future Git executables.

Exact final full-suite command:

```text
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python -I -B /home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n26_clean_output_rbf/bounded-git-loader-preparation-v1/run_cpu_checks.py
```

The final targeted command appends exactly:

```text
LoaderTests.test_dotfile_path_supported LoaderTests.test_invalid_key_06 LoaderTests.test_invalid_key_07 LoaderTests.test_invalid_key_08 LoaderTests.test_invalid_key_09 LoaderTests.test_invalid_key_10 LoaderTests.test_invalid_key_11 LoaderTests.test_invalid_key_12 LoaderTests.test_invalid_key_13 LoaderTests.test_invalid_key_14
```

Bytecode and pytest caches are disabled/not used. The harness checks the recursive 256-file/8 MiB cap before and after every run and retains cumulative timing in separate summaries. The delivery manifest covers all regular files and synthetic fixtures except itself (its external digest is supplied in the handoff). No additional testing or production-source access is needed for this component delivery.

Actual inventory completeness, normal common-directory compatibility, original live-gate preservation, integration correctness and speedup remain unmeasured. All current source/HEAD/helper/absence/process/authority/budget/journal/GPU/provider predicates must remain fresh in any separately authorized future adapter. Current N26 and the deferred integration design are unchanged.
