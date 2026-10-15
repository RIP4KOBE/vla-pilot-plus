# Node15.6 production repair

Status: source repairs committed; root adoption/rebinding required. No scientific success, runtime readiness or release claimed.

- Old commit: `066f2bf57e05111fea329ff7c393ac3e002d7c0f`
- New commit: `ca4e6a96d049c7ebb1f302d755883388ddbfdbd8`
- Worktree: `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree` (clean after commit)
- Scope: PR-01 and PR-04 only.

## Exact changes

PR-01: terminal verification now uses `source_execution.command` for exact interpreter, isolation/cache flags, bootstrap, module, context path and digest. Whole-envelope equality and subsequent receipt/native/generic audits remain intact.

PR-04: both final guards require at least 1840 seconds before the same minimum protocol/coordinator/weekly deadline. Rejected final start leaves the primary unsettled for root reconciliation. The full 1800-second worker timer and 40-second owned timeout cleanup remain unchanged; STOP does not cancel a live worker.

## CPU validation

`python -B tests/test_n36_production_repair.py`: 6 methods PASS. Includes exact runner/verifier agreement, 24 token mutations, 6 command-envelope mutations, 36 consumed-margin cases with no worker creation, 6 exact1840 acceptances and 2 late STOP rejections. Complete AST-extracted production functions execute against stdlib synthetic collaborators; no real worker/device/provider is invoked and journals remain in memory. These tests do not certify runtime imports or live audits.

Baseline negative control: two methods produce 25 expected failures against `066f2bf57e05111fea329ff7c393ac3e002d7c0f`, demonstrating both regressions. Syntax compilation and `git diff --check` pass. Only the two production files and focused test are committed.

## Remaining blockers and minimal rebindings

PR-02 is unresolved here: root will adopt into the owning study checkout. PR-03 is unresolved here: root will archive the rich amendment envelope and adopt exact references under state lock. No accounting-root feature, ownership migration, journal/state copying or mutation was performed.

1. Root adopts the repaired source into the single owning study checkout (PR-02); bind the resulting exact commit, owner/worktree paths and source inventory, including changed runner/worker bytes. No accounting-root feature or ownership migration was implemented.

2. Rebind existing turn1223 readiness evidence to the eventual source/owner and review applicability. Reuse unchanged CPU runtime/native inventory evidence only where exact bytes and context remain valid; this repair neither rebuilds runtime/provenance nor establishes readiness.

3. Refresh affected runtime/source-closure references and any controller evidence references that depend on changed runtime/owner paths. Preserve unchanged scientific/protocol/gate content; propagate exact new refs through all40 composed manifests and the final metadata-complete plan, and verify actual all40 composition in the owning checkout. Prior all40 receipts are context, not acceptance of new bindings.

4. Obtain a fresh independent production review of the adopted source and final bindings; root alone constructs matching final plan/review/detached release after PR-03 and other prerequisites. Old source-bound review/release or compiled-source receipts cannot approve this commit.

Live RT-03/RT-04 audits and RT-05 feasibility remain unresolved; no runtime/provenance rebuild was attempted.

## Hashes and limits

Exact old/new source hashes, authority/review hashes, skill hashes and all evidence hashes are recorded in `report-v1.json`; report hashes are in `report-hashes-v1.json`. STOP was absent at start and finish. Finished in 319.9 seconds against a 1800-second cap; authority deadline is 2026-10-11T11:13:13Z.

Initial tests used cleaned system temporary receipt directories; the committed harness confines them to the worktree. A baseline-summary assertion initially misparsed decimal subtest IDs; its log is retained, and corrected checks passed. No protected outcomes, forbidden design document, credentials or untracked dependencies were accessed for testing; no scientific/protocol/gate content or study state was changed.
