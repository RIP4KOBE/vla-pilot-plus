# Three-mode steering evaluation

Status: **complete_valid**.

Evaluation completion requires three finished valid full v2 audits and identical shared source/assets/RNG/protocol. All use ultra; no minimum success rate is required.

| Mode | State | Completed | Observed successes | Validated cohort score | GPU / EGL | Stage queries / errors | Guided chunks | Elapsed seconds |
|---|---|---:|---:|---|---|---|---:|---:|
| eds | accepted | 10/10 | 3 | 3/10 | 0 / 2 | 308 / 0 | 188 | 18277.0 |
| vls | accepted | 10/10 | 1 | 1/10 | 1 / 3 | 367 / 0 | 336 | 20853.2 |
| eds_qd | accepted | 10/10 | 0 | 0/10 | 4 / 6 | 402 / 0 | 277 | 22739.8 |

All cohorts valid: **True**. Evaluation complete: **True**.
Previous EDS low reference is 3/10; observed ultra score: 3.

Common commit: `c99565de6e34278c14518748d7c608433a4c529a`.

Shared checks: commit=PASS, source_sha256=PASS, model_identity=PASS, rng=PASS, libero=PASS, imported_packages=PASS, submodules=PASS, codex_cli=PASS, local_nonpath=PASS, shared_protocol=PASS, manifest_protocol=PASS, source_commit_present=PASS.

Per-task seeds, provisional outcomes, videos, timings, compute counters, mechanism counts, source and audit hashes are in the adjacent JSON report. Unknown counters remain unknown; observed subtotals are labelled.

Pending cohorts have no validated score. Zero-success and low-scoring valid cohorts remain reportable outcomes.
