# Future immutable-cache integration design — static only

This is preparation for a future cohort, not an N26 change. Active source 6026794 must stay untouched through terminal review. The component in ../validation-cost-cache-preparation-v1 has root CPU acceptance only (root-cpu-review-v1.json SHA 59c0cac1c575a2957b778e180d79532e66d81e6d414dfa8b69d9d816ba157a76). Actual-source integration and GPU execution remain closed.

Design the smallest feasible future integration using only static source. Read this protocol, that cache preparation directory's eight exact files, and ../validation-cost-static-review-v1/report.md plus its source-scope-v1.json and the eleven files explicitly listed there. Verify listed source hashes and cap before reading. Do not follow artifact paths embedded in source, invoke Git/history, import production code, inspect /proc, read experimental records or credentials, or execute tests/models/providers/simulators. CPU only, no GPU or network.

Write only this directory: at most three files including this protocol, at most 256 KiB total. Deliver design.md and source-scope-v1.json. Do not write implementation, patches, branches, plans, budgets, state, checkpoints, releases or experiment results.

Identify exact immutable-byte read boundaries and the smallest new adapter/call-site change. Explain how a finite trusted allowlist with known sizes and hashes could be constructed prospectively, how repository/commit identity is bound, how object reads would be bounded before allocation, and how same-process cache lifetime would reduce duplicate work. Do not claim cross-process reuse or speedup without measurement. If the eleven-source boundary cannot establish provenance or enumerate the allowlist, state the missing evidence instead of reading more.

Keep live checks fully separate and fresh: current working files and HEAD, source equivalence assumptions, relevant current journals/resources, authority and reservations, historical-artifact absence requirements, locks/process cleanup, GPU identity/ownership, and current Codex login/provider policy. Never cache entire bridge/build/validate/admission outcomes or old live predicates. Include invalidation/failure behavior and meaningful future negative tests for stale live state despite cache hits.

Compare integration complexity against probable benefit from the static call graph. Recommend defer if a narrow verified adapter cannot be defined without rebuilding the provenance system. Preserve current scientific work as the priority. This design is not integration authorization.

