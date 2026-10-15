# Three-mode steering evaluation

Status: **partial_or_not_accepted**.

Final acceptance requires three finished, valid full v2 audits plus identical shared source, assets, RNG and protocol.

| Mode | State | Completed | Observed successes | Final accepted score | GPU / EGL | Stage queries / errors | Guided chunks | Elapsed seconds |
|---|---|---:|---:|---|---|---|---:|---:|
| eds | partial | 0/10 | 0 | Pending | 0 / 2 | 26 / 0 | 21 | 1203.5 |
| vls | partial | 0/10 | 0 | Pending | 1 / 3 | 30 / 0 | 22 | 1255.0 |
| eds_qd | partial | 0/10 | 0 | Pending | 4 / 6 | 25 / 0 | 20 | 1247.4 |

Common commit: `33954ead452927fc3168efb610487a688f89169e`.

Shared checks: commit=PASS, source_sha256=PASS, model_identity=PASS, rng=PASS, libero=PASS, imported_packages=PASS, submodules=PASS, codex_cli=PASS, local_nonpath=PASS, shared_protocol=PASS, manifest_protocol=PASS, source_commit_present=PASS.

Per-task seeds, provisional outcomes, videos, timings, compute counters, mechanism counts, source and audit hashes are in the adjacent JSON report. Unknown counters remain unknown; observed subtotals are labelled.

The report is a snapshot of running cohorts until `final_accepted` is true. Observed successes are not a final result.
