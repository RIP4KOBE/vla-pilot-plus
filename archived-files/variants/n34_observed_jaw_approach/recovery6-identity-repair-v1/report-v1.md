# Arbor node15.4 N34R6 identity repair

CPU implementation complete on `codex/n34-production-integration`. Root review/adoption remains separate.

Base: `77e759096d1a2b114ab8ea4dd1240115607935d8` (clean at start). Commit: `cf0362af77867dc67b8aa814d345781a8a1ab892` (clean after commit).

Advanced the strict identity contract to `N34R6_OBSERVED_JAW_APPROACH_DEV_20261008`, with 30 fresh lowercase-profile keys. Task0 C0 explicitly replaces `n34r5_dev_t00_c0_20261008` in the recovery bucket, bound exactly to authority turn664 path/hash. Allocation remains 1 recovery / 9 baseline / 20 development, with zero automatic retries.

All six invalid cohorts remain required history with their original charges, buckets, unknowns and records. N34R5's computed control remains INVALID because lazy OpenGL conversion-handler runtime coverage was missing. Historical preparation costs remain global charges; the current cohort resource tag is N34R6.

Changed files:

- `scripts/qd_ed_n34_contract.py`
- `scripts/qd_ed_n34_release.py`
- `tests/test_n34_lifecycle.py`
- `tests/test_n34_recovery_identity.py`
- `tests/test_n34_release_boundary.py`

Validation: 377 focused tests passed in 2.93 seconds. Coverage includes all30 stale identities, N34R5 terminal/context bindings, turn654 stale closure path/hash rejection, exact replacement and bucket enforcement, six retained invalid charges, unknown/computed-control preservation, zero retries, and unchanged promotion/futility rules. The initial run had 372 passes and five lifecycle failures from pre-existing fixed history offsets/counts; those assertions now check the complete retained history and exact subsequent events. Commands/results are in `implementation-result-v1.json`; both logs are retained. `git diff --check` passed.

The authority comparison and base-source comparison passed (`scope-verification-v1.json`). Tasks, seeds, limits, audits, deadline, promotion/futility and all scientific files are unchanged from the clean base. The requested scientific implementation reference is `1065f38122379a515b60a9a424f574330405b66f`; the existing bridge separately pins `71ffff1a0f70d9874b309db9ef1843c02bf17ebf`. That pre-existing binding was preserved, not rewritten.

No scientific score was measured. No GPU/provider experiment calls, subagents, protected guidance/results access, owning state/ledger writes, runtime preparation or APPROVED release generation occurred. Test artifacts are synthetic and confined to this output directory. Historical source remains in git.

Root must separately review/adopt this commit and regenerate runtime composition with the new identities. Turn665 remains preparation only with OLD identities; its runtime inventory correction was not edited. This handoff grants no GPU release.
