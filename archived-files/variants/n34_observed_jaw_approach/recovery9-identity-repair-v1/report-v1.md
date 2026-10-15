# Node15.4 N34R9 identity repair

Implemented and committed on the existing production branch: `a7331a0cf4b84d34aea2a1098773622643cec691`.
Base: `7cc32546ef70f6a9e28170ac184f9d9d30fb9a33`. Git was clean at start and after commit.

The four-file change advances all 30 task-major C0/Q0/N34 identities to
`N34R9_OBSERVED_JAW_APPROACH_DEV_20261008`, using lowercase profile episode keys.
Task0 C0 explicitly replaces `n34r8_dev_t00_c0_20261008` in recovery, bound to
turn694 `terminal-closure-v1.json` at the exact authority path and SHA-256
`cd6402fe26146565fbb6123888e5d73b2e65311e9c7d99da8a18aae51f23bbf4`.
The exact allocation remains 1 recovery, 9 baseline, 20 development, with zero
automatic retries. Resource-preparation accounting now selects the N34R9 tag;
old preparation costs remain globally charged.

All nine invalid N34 through N34R8 executions remain required history. The
prior eight-entry prefix is unchanged and N34R8 is appended. Computed N34R8 C0
remains INVALID because of unbound DINOv2 dynamic imports; no control result is
carried forward. Costs, unknown telemetry and arbitrary historical detail are
preserved without mutation.

Focused validation: **515 passed in 3.20s**. Coverage includes all stale rows,
N34R8 terminal/context bindings, closure path/hash rejection, all-cell bucket
and replacement enforcement, retained charges, no retry, unchanged promotion
and complete-valid-triple futility, and synthetic lifecycle accounting.
The initial run had 514 passes and one new-test assertion failure: aborted
attempts have their own existing accounting counter. The assertion was fixed;
production accounting was unchanged. Both logs are retained. No APPROVED
release fixture was executed; the selected release-boundary test is in memory.
`git diff --check` passed. Commands and results are in
`implementation-result-v1.json`.

Changed files:

- `scripts/qd_ed_n34_contract.py`
- `scripts/qd_ed_n34_release.py`
- `tests/test_n34_recovery_identity.py`
- `tests/test_n34_release_boundary.py`

Science, tasks, seeds, thresholds, audit rules, runtime inventory, N31 and owning
state/ledgers were not edited. The user-specified scientific implementation
reference `1065f38122379a515b60a9a424f574330405b66f` was not modified. The existing
N34 bridge scientific trust anchor is `71ffff1a0f70d9874b309db9ef1843c02bf17ebf`
and was deliberately left unchanged. No algorithm change was made.

This is CPU engineering evidence, not a scientific evaluation; score is null.
No GPU/provider experiment, API-key/Poe access, subagent, protected guidance or
protected-result access, runtime preparation, owning ledger/state mutation,
or release generation was performed. Temporary outputs are under this output
directory. The authorized Arbor executor instructions were applied within the
user's explicit executor-only scope.

Root separately reviews/adopts. Turn695 remains preparation with OLD identities;
root must regenerate after adoption. This implementation grants no GPU release.
