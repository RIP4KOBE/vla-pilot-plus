# Independent B5: FAIL

Exact source: `b8d6b98164f24a599a9aa1fa6ce862b12cb2fcf6`.

The canonical refreshed preparation is internally inconsistent. Its source inventory correctly binds the new G7 code, but reused runtime and runtime-closure artifacts still bind the old hashes for:

- `scripts/qd_ed_n36_healthcheck.py`
- `scripts/qd_ed_n36_runner.py`
- `scripts/qd_ed_n36_worker.py`

Runtime fingerprints are at `/files/3294`, `/files/3296`, and `/files/3298`; closure fingerprints are under the corresponding `scripts.qd_ed_n36_*` module names. Exact recorded/actual hashes and sizes are in [focused-runtime-incompatibility-v1.json](focused-runtime-incompatibility-v1.json). Current unmodified passive consumer predicates reject all six entries. The matrix claims that these records can be reused byte-identically are therefore false. Direct root hashes being correct does not make the transitive source bindings complete.

Independent checks recorded 2,132 predicates: 2,130 passed and two compatibility checks failed, followed by six focused rejection confirmations. Exact disabled plan/audit/equivalence checks passed. The 1,110 inventoried source digests, all40 cells, 41 manifest deltas, frozen science, protocol, deployment, and retained ledger prefixes were checked. Controller semantics pass locally against the old reference pair, but their runtime/closure references and three root review-evidence bindings become affected when those records change.

The minimal next gate is a bounded owner-directed refresh of the stale runtime/closure leaves and their affected references, followed by fresh B5 on the new canonical roots. Preserve source, all40 cells, frozen thresholds, charges/reserves and every old record including the failed first refresh and this FAIL. Controller proof rebinding requires its owner; this review supplies no approval or adoption. No source edit is indicated by these artifact findings.

No PASS object was emitted: the current consumer accepts only an exact PASS schema. The machine-readable verdict is [report-v1.json](report-v1.json), sealed by [report-v1.sha256](report-v1.sha256). Existing disabled preparation, absent root approvals and unobserved readiness remain distinct from these preparation blockers. No GPU, native/model/provider execution, scientific result, source/accounting adoption, owner-state mutation, or authority grant occurred. Deadline and canonical STOP remain binding.
