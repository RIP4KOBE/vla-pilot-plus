N34R8 identity implementation completed for node15.4 on `codex/n34-production-integration`.

Base: `1f0e8becba733dc174e78b9248567feafbc052d7` (clean at start). Commit: `7cc32546ef70f6a9e28170ac184f9d9d30fb9a33` (clean after commit).

The four-file patch advances all 30 task-major C0/Q0/N34 rows to fresh lowercase-profile N34R8 keys. Task0 C0 explicitly replaces `n34r7_dev_t00_c0_20261008` in recovery, bound to the authority's exact turn684 terminal-closure path and SHA-256. Buckets remain 1 recovery / 9 baseline / 20 development; automatic retries remain zero. Current preparation-cost identity is N34R8; historical N34R7 preparation costs remain globally charged.

All eight N34 through N34R7 invalid executions retain their original charges, buckets, unknowns and history. The added SentencePiece protobuf case verifies that computed N34R7 C0 remains invalid and cannot enter the result matrix or promotion gate. No owning records were edited.

Changed files:

- `scripts/qd_ed_n34_contract.py`
- `scripts/qd_ed_n34_release.py`
- `tests/test_n34_recovery_identity.py`
- `tests/test_n34_release_boundary.py`

Focused validation: **471 passed in 3.16s**. Full command and output are in `implementation-result-v1.json` and `focused-tests-v1.log`. Coverage includes all stale N34 through N34R7 rows, stale turn674 terminal bindings, all 30 bucket/replacement assignments and admissions, every historical invalid charge, same-process parent identity rejection, frozen seed auditing, zero-retry lifecycle, complete-valid-triple futility and independent comparison against both controls. `git diff --check` and authority/frozen-constant assertions also passed.

Scientific behavior, tasks, seeds, thresholds and audit logic are unchanged from the clean base. Provenance caveat: the supplied implementation reference is `1065f38122379a515b60a9a424f574330405b66f`, while the existing N34 bridge pins `71ffff1a0f70d9874b309db9ef1843c02bf17ebf`; the base already differs from 1065f38 in scientific files. Both the existing code and bridge anchor were preserved. This patch makes no claim that those two commits are identical.

Only CPU synthetic tests ran, with bytecode disabled and temporary outputs under this output directory. No GPU/provider experiments, subagents, protected guidance/results, owning state/ledger writes, runtime inventory edits, runtime preparation or APPROVED release generation occurred. The release-boundary test ran only its in-memory stale-matrix gate; approval-producing fixtures were not run.

Root must separately review/adopt the commit and regenerate runtime composition. Turn685 remains preparation with OLD identities; this handoff grants no runtime release or GPU authorization. No scientific score was produced.
