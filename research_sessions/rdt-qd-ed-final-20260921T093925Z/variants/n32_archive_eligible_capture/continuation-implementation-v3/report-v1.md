# N32R3 continuation implementation — node15.2

Implemented and committed on the existing isolated branch `exp/n32-archive-eligible-cpu-20261004`.

- Base: `1065f38122379a515b60a9a424f574330405b66f`
- Commit: `36aac818c8ea0ec3ce18413e678963818bb5bb5d`
- Status: **IMPLEMENTED_CPU_TESTED_NOT_RELEASED**
- Scientific score: **Unknown / not evaluated**. No scientific success or promotion is claimed.

## Authority and boundaries

The implementation authority, bound root preparation review and specification passed independent SHA-256/byte-length checks. The review records 356 passing checks and permits bounded CPU implementation only. Initial HEAD matched and the tracked worktree was clean. STOP was absent, the seven-day user window remained open, and completion is within the 30-minute authority window. Applied the Arbor executor skill under the user's narrower CPU-only instructions. No agents, coordinator/driver lease, provider/model/Stage/GPU calls, protected outcome reads, credential reads, owning-state/ledger changes, merge, cherry-pick or adoption occurred. Preparation artifacts remain byte-identical.

## Changes and implementation choices

Eight new `scripts/qd_ed_n32r3_*.py` modules implement the contract, original metadata verification, manifest bridge/composition entrypoint, release/admission, reconciliation, runner and worker. Three focused test files accompany them. Scientific files changed: **none**. Historical `qd_ed_n32_*.py` modules and the N32R2 validator/5 GPUh contract remain unchanged.

The sole shared edit is `scripts/qd_ed_final_runner.py:1023`: four added lines and one replaced line route only the exact N32R3 released-plan recovery row through its versioned contract. Previous default branches are unchanged. The source-continuity verifier checks this exact textual delta and rejects additional shared changes; it rejects any other existing scientific/audit-file delta.

The immutable map is pinned to the existing independent preparation-review digest and its artifact index. The historical verifier checks each original terminal/native/generic/context/command/process/manifest/Stage metadata digest and its own original plan/release/identity bindings. It does not rerun tensors or manufacture historical N32R3 lifecycle events. The old invalid terminal is retained as invalid and charged even though its separately reviewed native mechanics were accepted. Its original terminal has no native-receipt pointer; the immutable map separately commits that receipt.

Reconciliation permits exactly 14 historical occupants plus the unique `n32r3_recovery_t04_n32_20261008` recovery of `n32r2_dev_t04_n32_20261004`, then the 15 task5–9 rows. It blocks duplicate/aliased attempts, accepted replay, extra old-cohort execution, missing controls, repeated recovery and any new invalid terminal. Futility uses complete valid triples only; the original 30-cell/five-success/matched-control gate remains unchanged. No code authorizes promotion, validation or formal evaluation.

Original native/generic scientific functions are reused. The versioned worker retains same-process source/CUDA/evidence/native/generic/cost gates and adds explicit parent/map/source-continuity and semantic commitments. New lifecycle receipts retain those commitments. The runner uses the existing sole-child timeout/cleanup helpers and normal runner/state locks, checks old/new handles without signalling them, rechecks all journals/state under locks and leaves a STOP-after-reservation attempt unsettled. There is no automatic retry.

Operational source is the new commit; immutable scientific source remains `1065f38122379a515b60a9a424f574330405b66f`. Only the scientific N32 runtime binding retains the scientific commit, as required by the already-bound command candidates. Its run ID and composed/native config hashes are regenerated; full operational source is separately committed by plan/manifest/context/receipts. No new source is presented as the old digest. Source continuity and original parents are verified before historical pooling.

The manifest composition entrypoint accepts a disabled `n32r3-composition-input-v1` only after separate source-continuity approval; it writes manifests/index but grants no release. Future production requires `n32r3-released-plan-v1`, its adopted accounting authority, exact protocol, independent detached root review and caller-supplied release. Preparation NONEXECUTABLE candidates reject. Reference objects in executable plans use exact path/SHA pairs; preparation references may additionally bind byte length.

## CPU evidence

Final command (run from the isolated worktree):

```sh
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q tests/test_n32r3_continuation.py tests/test_n32r3_execution.py tests/test_n32r3_source.py tests/test_n32_production.py::test_null_retries_allowed_nonnull_forbidden_and_deterministic_ids tests/test_n32_production.py::test_generic_historical_charges_and_health_preserved tests/test_n32_release.py::test_matrix_and_immutable_draft -p no:cacheprovider --basetemp=../continuation-implementation-v3/pytest-tmp-v5
```

**127 passed in 11.27 seconds.** Diff whitespace check passed. Test logs and machine-readable coverage are in `test-evidence-v1.json`. Coverage includes positive carry-forward/recovery; receipt/hash-preserving identity substitution; profile/provider/auth/model/seed/init/command attacks; duplicate/replay; missing/invalid controls; threshold edges and 29-cell nonpromotion; old invalid/overhead accounting; unknown duration rejection; private caps/reserves; full1840 admission; STOP before/after reservation; stale/missing release approval; changed journals; wrong GPU identity/non-idle/live handles; exact source delta and stale hash rejection. Three existing N32R2 focused regression checks passed.

One incremental test fixture initially omitted reserved/dispatched events for an unattributed health charge; the generic journal checker rejected it before the intended admission assertion. The fixture was corrected, with no production check weakened. All final tests passed.

These are synthetic operational tests. Runner tests mock child/GPU/provider boundaries; release DAG tests spy expensive gates, with boundary logic separately exercised. No tensor audits, models, scientific evaluation or real future outcomes were generated. A bounded read-only compatibility check accepted the existing preparation map and original plan/release/review DAG without replaying the root's provenance work.

## Remaining release, manifest and admission blockers

1. Independent root review of this isolated commit and exact shared operational delta; no adoption into the owning study has occurred.
2. New complete operational source inventory and approved source-continuity attestation bound to the immutable parent plan/release, map and command candidates.
3. New runtime binding and all16 freshly composed/audited external manifests in the exact approved command/output identity. Command candidates retain the owning main.py path; this isolated checkout cannot silently substitute its path.
4. Separate approved/adopted N32R3 accounting authority/amendment, declaring preparation resource IDs and retaining original journal/health prefixes, all charges, weekly/global caps and protected reserves.
5. Fresh owning-state/journal reconciliation, no unsettled/live handles, STOP/deadline full1840-second margin, accounted GPU/EGL proof, idle GPU7 exact UUID and current approved provider/runtime admission.
6. New frozen protocol, independent detached root production review and caller-supplied detached release. Disabled preparation candidates remain rejected.

The 16-attempt/8.5-GPUh proposal remains a disabled candidate; no budget was adopted. Historical and HTTP telemetry remain **Unknown** where unknown. No approval artifact or scientific success was fabricated.

## Handoff artifacts

`implementation-result-v1.json` records status, exact commit, tests and blockers. `changed-files-v1.json` classifies every changed file. `exact-diff-v1.patch` is the full base-to-commit diff. `source-delta-v1.json` is an unapproved operational delta candidate, not source continuity approval. `artifact-index-v1.json` hashes the deliverables and excludes itself to avoid a circular digest. Owning coordinator remains driver-controlled.
