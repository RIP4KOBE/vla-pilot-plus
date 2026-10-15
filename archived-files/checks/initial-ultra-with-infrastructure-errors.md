# Three-mode steering evaluation

Status: **partial_or_invalid**.

Evaluation completion requires three finished valid full v2 audits and identical shared source/assets/RNG/protocol. All use ultra; no minimum success rate is required.

| Mode | State | Completed | Observed successes | Validated cohort score | GPU / EGL | Stage queries / errors | Guided chunks | Elapsed seconds |
|---|---|---:|---:|---|---|---|---:|---:|
| eds | rejected | 9/10 | 3 | Pending | 0 / 2 | 281 / 1 | 209 | 15364.1 |
| vls | accepted | 10/10 | 2 | 2/10 | 1 / 3 | 353 / 0 | 395 | 19467.4 |
| eds_qd | rejected | 9/10 | 1 | Pending | 4 / 6 | 379 / 1 | 294 | 21975.7 |

All cohorts valid: **False**. Evaluation complete: **False**.
Previous EDS low reference is 3/10; observed ultra score: None.

Common commit: `6c83eb6a55fa6f92723e58a960d59ee4f606084e`.

Shared checks: commit=PASS, source_sha256=PASS, model_identity=PASS, rng=PASS, libero=PASS, imported_packages=PASS, submodules=PASS, codex_cli=PASS, local_nonpath=PASS, shared_protocol=PASS, manifest_protocol=PASS, source_commit_present=PASS.

Per-task seeds, provisional outcomes, videos, timings, compute counters, mechanism counts, source and audit hashes are in the adjacent JSON report. Unknown counters remain unknown; observed subtotals are labelled.

Pending cohorts have no validated score. Zero-success and low-scoring valid cohorts remain reportable outcomes.
