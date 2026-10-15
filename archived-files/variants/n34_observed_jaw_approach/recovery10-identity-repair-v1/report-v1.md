# Node 15.4 CPU implementation handoff

Base: `a7331a0cf4b84d34aea2a1098773622643cec691` (clean at start). Commit: `cf11e91d2d9a4a0def0111c1ab24d0111c75988b` on `codex/n34-production-integration` (clean at finish).

Advanced the strict contract to `N34R10_OBSERVED_JAW_APPROACH_DEV_20261008` with 30 fresh lowercase-profile keys, task0 C0 recovery of `n34r9_dev_t00_c0_20261008`, and exact authority turn704 path/hash. Budget mapping remains 1 recovery / 9 baseline / 20 development; automatic retries remain zero. All ten N34 through N34R9 invalid executions are required in history with original charges and unknowns. The PIL._imagingmath computed control remains INVALID.

Changed files:
- `scripts/qd_ed_n34_contract.py`
- `scripts/qd_ed_n34_release.py`
- `tests/test_n34_recovery_identity.py`
- `tests/test_n34_release_boundary.py`

Focused validation: **556 passed in 3.15s**. Exact command and log are in `implementation-result-v1.json` and `focused-tests-v1.log`. Coverage includes all 30 stale rows for all ten historical cohorts, exact terminal path/hash rejection, parent terminal bindings, per-cell replacement/bucket gates, historical preparation costs, retained invalid telemetry/costs, lifecycle no-retry behavior, shared seed audit, promotion against both controls, and complete-valid-triple futility. Only the in-memory stale-plan test from release-boundary tests was run; no APPROVED fixture was generated.

`git diff --check` passed. Source function ASTs are identical to base after identity-string normalization. No scientific implementation, frozen tasks/seeds/thresholds, audit algorithm, N31 source, or runtime inventory was edited. No owning state/ledger writes, GPU/provider experiments, runtime preparation, or subagents. Test temporary outputs are under this output directory.

Turn705 remains preparation only with old identities. Root must review/adopt and regenerate its runtime composition separately; this handoff grants no release. Experimental score: not measured (CPU engineering only).

Review notes:
- User-supplied scientific implementation reference 1065f38122379a515b60a9a424f574330405b66f has Git subject Advance N32 recovery identities to N32R2 with isolation regressions. The pre-existing N34 bridge SCIENTIFIC_COMMIT is 71ffff1a0f70d9874b309db9ef1843c02bf17ebf. Neither reference nor scientific source/behavior was changed. Root should resolve the reference discrepancy separately.
- Initial overly broad identity search traversed tracked data/attempt-ledger.jsonl and emitted existing validation result rows. This was outside the requested read scope. No result values were used for implementation or scientific decisions; subsequent searches were restricted to source/tests/configuration. No ledger or result records were written.
