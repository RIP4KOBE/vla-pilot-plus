# Arbor node15.4 N34R7 identity repair

Completed CPU engineering on existing branch `codex/n34-production-integration`.

- Base: `cf0362af77867dc67b8aa814d345781a8a1ab892` (clean at start).
- Commit: `1f0e8becba733dc174e78b9248567feafbc052d7` (clean at finish).
- Authority: `authority-v1.json`, SHA-256 `845e8ce5f7196cdc5239127d3a61cb6b9cdab5bc6fe15f86ad1176c97a881d25`.
- Score: not evaluated; no experiment or valid control result is claimed.

## Changes

Advanced all30 task-major C0/Q0/N34 identities to `N34R7_OBSERVED_JAW_APPROACH_DEV_20261008` and lowercase-profile `n34r7_dev_tXX_PROFILE_20261008` keys. Task0 C0 explicitly replaces `n34r6_dev_t00_c0_20261008`, bound to `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000674/terminal-closure-v1.json` with SHA-256 `6ecf4d613b27b100e2c68892fec8dce09e996ca94001dfce9a76776f0c78940e`.

Retained exact 1 recovery / 9 baseline / 20 development mapping, zero automatic retries, strict audits, caps, deadline, tasks, seeds, and thresholds. Added N34R6 to required invalid history while preserving the prior six entries. N34R6's computed C0 remains INVALID due to missing lazy Numba JIT dependency runtime coverage; its outcome and unknown telemetry are never reused as a valid control. Historical resource costs remain global; N34R7 preparation costs are selected by either its cohort or its preparation kind.

Changed files:

- `scripts/qd_ed_n34_contract.py`
- `scripts/qd_ed_n34_release.py`
- `tests/test_n34_recovery_identity.py`
- `tests/test_n34_release_boundary.py`

## Validation

`430 passed in 3.07s`, exit 0. Exact command:

```sh
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n34_observed_jaw_approach/recovery7-identity-repair-v1/tmp python -m pytest -q -p no:cacheprovider --basetemp=/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n34_observed_jaw_approach/recovery7-identity-repair-v1/pytest-focused tests/test_n34_recovery_identity.py tests/test_n34_lifecycle.py tests/test_n34_release_boundary.py::test_stale_n34r6_release_matrix_rejected
```

Coverage includes all30 stale identities across N34 through N34R6, stale terminal path/hash and worker bindings, every-cell bucket/replacement enforcement, all seven invalid charges and unknowns, admission continuity, zero retry lifecycle, and unchanged complete-valid-triple futility and promotion against each control. Preparation accounting tests independently exercise cohort and kind selectors. The selected release-boundary test is in-memory and creates no APPROVED release.

`git diff --check` passed. `contract-verification-v1.json` records an in-memory comparison against the base source: frozen row fields, audit constants, limits, caps, deadline, and six pre-existing invalid entries are unchanged; authority binding is exact. `focused-tests.log` retains pytest output. Temporary test files are confined to this output directory, with bytecode and pytest caching disabled.

## Scope and handoff

No scientific or runtime implementation files changed. User-designated scientific implementation `1065f38122379a515b60a9a424f574330405b66f` remains untouched; the pre-existing bridge scientific-source anchor `71ffff1a0f70d9874b309db9ef1843c02bf17ebf` was also left unchanged. No GPU/provider experiments, runtime preparation, runtime inventory correction, protected guidance/results access, owning state/ledger writes, subagents, or APPROVED release generation occurred. Synthetic lifecycle journals exist only under the output directory.

Historical source remains in git. Root separately reviews and adopts this commit. Turn675 composition remains preparation with OLD identities; root must regenerate it after adoption. This implementation confers no GPU release authority.
