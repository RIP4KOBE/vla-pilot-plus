# Three-mode steering evaluation

Status: **partial_or_not_accepted**.

Integration acceptance requires three finished, valid full v2 audits, identical shared source/assets/RNG/protocol, and EDS at least 3/10. Cohort validity and integration performance are separate gates.

| Mode | State | Completed | Observed successes | Validated cohort score | GPU / EGL | Stage queries / errors | Guided chunks | Elapsed seconds |
|---|---|---:|---:|---|---|---|---:|---:|
| eds | partial | 1/10 | 0 | Pending | 0 / 2 | 50 / 0 | 38 | 2183.5 |
| vls | partial | 1/10 | 0 | Pending | 1 / 3 | 55 / 0 | 48 | 2235.0 |
| eds_qd | partial | 1/10 | 0 | Pending | 4 / 6 | 49 / 0 | 32 | 2227.4 |

All cohorts valid: **False**. Integration accepted: **False**.
EDS integration threshold: at least 3/10; observed validated score: None.

Common commit: `33954ead452927fc3168efb610487a688f89169e`.

Shared checks: commit=PASS, source_sha256=PASS, model_identity=PASS, rng=PASS, libero=PASS, imported_packages=PASS, submodules=PASS, codex_cli=PASS, local_nonpath=PASS, shared_protocol=PASS, manifest_protocol=PASS, source_commit_present=PASS.

Per-task seeds, provisional outcomes, videos, timings, compute counters, mechanism counts, source and audit hashes are in the adjacent JSON report. Unknown counters remain unknown; observed subtotals are labelled.

Pending cohorts have no validated score. A completed valid cohort retains its score even if EDS falls below the integration threshold; that outcome is not relabeled invalid.
