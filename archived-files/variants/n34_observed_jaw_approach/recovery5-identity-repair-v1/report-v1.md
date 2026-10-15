Arbor node15.4 CPU identity implementation is complete and committed for root review.

Base: `b9f20b8a25766138843b691136ce143566567d3c` (clean at start). Commit: `77e759096d1a2b114ab8ea4dd1240115607935d8` on `codex/n34-production-integration` (clean at finish).

The strict contract now requires `N34R5_OBSERVED_JAW_APPROACH_DEV_20261008` and all 30 lowercase-profile `n34r5_dev_tXX_PROFILE_20261008` keys. Task0 C0 explicitly replaces `n34r4_dev_t00_c0_20261008` in recovery, bound to the exact turn654 path and SHA-256 in authority-v1.json. The allocation remains 1 recovery / 9 baseline / 20 development, with zero automatic retries.

All N34 through N34R4 invalid attempts remain required history with original costs, buckets, unknowns and invalid outcomes. Computed N34R4 C0 remains INVALID because lazy OpenGL conversion-handler runtime coverage was missing; it is never reused as a valid control. Tests also retain the corresponding N34R3 regression.

Scientific source remains `71ffff1a0f70d9874b309db9ef1843c02bf17ebf`. Tasks, seeds, arms, thresholds, caps, deadline, promotion, complete-valid-triple futility and worker audits are unchanged. Only the following files changed:

- `scripts/qd_ed_n34_contract.py`
- `scripts/qd_ed_n34_release.py`
- `tests/test_n34_lifecycle.py`
- `tests/test_n34_recovery_identity.py`
- `tests/test_n34_release_boundary.py`

Focused validation: **328 passed in 2.49s**; `git diff --check` passed. Coverage includes every stale historical row, N34R4 terminal/context bindings, stale closure path/hash, all30 bucket/replacement enforcement and sequential admissions, all five retained invalid charges, historical preparation costs, frozen seed auditing, promotion and futility. The exact test command and results are in implementation-result-v1.json; output is in focused-tests-v1.log. An AST comparison against base verified unchanged frozen contract constants; authority and scope checks are recorded in invariant-check-v1.json.

Tests used synthetic CPU fixtures with PYTHONDONTWRITEBYTECODE=1, pytest cache disabled, and temporary outputs under this output directory. No APPROVED release fixtures were executed. No GPU/provider experiment calls, subagents, protected guidance/results access, owning state/ledger writes, or runtime inventory/preparation changes occurred. No new experiment score is claimed.

Turn655 remains preparation only with OLD identities. Root must regenerate runtime composition after adoption and separately review release/accounting/admission. The terminal reference was matched exactly to authority; its external contents and owning ledgers were outside this executor's read scope.
