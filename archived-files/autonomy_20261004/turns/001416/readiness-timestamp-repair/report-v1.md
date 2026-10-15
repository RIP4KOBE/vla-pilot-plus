Node 15.6: bounded CPU-only engineering repair committed. No G3 or research success claimed.

Source before: `4347951a24b63cdb7f0c8a585591d89f1be778ae`. Source after: `4e632c3bf1afe682d9287a518e531e6f2a6eba42`. Branch: `exp/n36r3-generated-import-001299`. Worktree: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r3_generated_import_001299/implementation_worktree`.

Authority: `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001416/readiness-timestamp-repair/authority-v1.json` (SHA-256 `90819ed675ec8b987ea19c25522027559e5ed7debd8447e59069231501bb3656`). Diagnosis: `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001416/release-failure-diagnosis-v1.json` (SHA-256 `32130ff7441e25c56278c4a13435aeaa399ebfd17d92f2d364195ffcd1868b24`).

The authorized diagnosis reports probe observation 1791630125.6529133 and terminal completion 1791630145.40565. The parent intentionally records completion after consuming the probe; the consumer incorrectly required equality. Historical evidence was not rewritten or revalidated as live readiness.

Read original probe time_unix as observation and terminal time_unix as completion. Require finite nonnegative numeric times and authority starts_at <= observation <= completion <= min(current UTC time, coordinator_ends_at, weekly_window.ends_at). Only time_unix is excluded from cross-document equality, with this explicit replacement check. No schema or timestamp-writing behavior changed; writer comments clarify semantics.

Changed files:

- `scripts/qd_ed_n36_healthcheck.py`
- `scripts/qd_ed_n36r3_admission.py`
- `tests/test_n36r3_admission.py`

Exact diff: [repair-v1.patch](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001416/readiness-timestamp-repair/repair-v1.patch), SHA-256 `08347fd69d92dda174536ffc02feffa534fa75905e489ab5cab94ed9055b513e`. Per-file before/after hashes are in [report-v1.json](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001416/readiness-timestamp-repair/report-v1.json).

The test fixture now includes the real probe timestamp, accepts the existing attestation binding keyword, and supplies canonical owner metadata. These are test-only corrections; source/runtime/owner checks remain strict.

Test commands and outcomes:

- `python -m pytest -q tests/test_n36r3_admission.py`: 21 failed, 7 passed, 32 errors in 4.55s Stale synthetic attest stub did not accept existing binding keyword; fixed test stub only.
- `python -m pytest -q tests/test_n36r3_admission.py --tb=short`: 21 failed, 7 passed, 32 errors in 7.58s Synthetic owner state lacked existing canonical_worktree requirement; added test fixture field only.
- `python -m pytest -q tests/test_n36r3_admission.py --tb=short --show-capture=no`: 3 failed, 57 passed in 11.69s Nonfinite probe values correctly raised JSON GateError before finite validation; test exception expectation corrected.
- `python -m pytest -q tests/test_n36r3_admission.py -k 'invalid_times and probe and (nan or inf)' --tb=short --show-capture=no`: 3 passed, 57 deselected in 1.96s Only the three failed cases repeated after test-only correction; no full green rerun claimed.
- `git diff --check`: No whitespace errors. 

All 60 collected cases have passing evidence across the last full run (57) and failed-case rerun (3). 32 new cases cover ordered/equal timestamps, reversed/nonfinite/future/pre-start/end-window times, missing/non-numeric timestamps and 11 non-time tampering cases. Synthetic CPU only; hardware/provider/process and scientific audits are substituted. No production readiness or G3 acceptance claim.

Falsifiable implications:

- Otherwise valid synthetic readiness with distinct ordered observation/completion times passes; the baseline all-field equality rejects that case.
- Reversed, future, nonfinite or out-of-authority-window timestamps still reject; changing non-time evidence, frame bytes or bound source/runtime/plan/release/terminal/journal still rejects.
- This commit cannot be substituted into old source-bound health evidence. Attempting exact new-source readiness with an old-source terminal must fail the unchanged source/plan/runtime binding gates.
- CPU tests do not establish GPU/provider readiness, episode validity, G3, or any research improvement.

Smallest lawful subsequent procedure, left to root:

1. Root reviews and explicitly adopts exact repaired commit and only necessary source-dependent review/runtime/plan bindings through its lawful process. This executor generated no adoption, plan, release, manifest, freeze, or authority.
2. Old readiness remains immutable and bound to the old source. Do not relabel source_commit, plan/release refs, hashes, timestamps or journal entries to reuse it for this commit. Preserve old charges and the failed first-C0 release record.
3. Before any new health activity, root must establish a remaining lawful distinct health resource and authority, budget and time window with no replay or automatic retry. The preparation ID is already used; if existing allowances cannot lawfully supply a new check, remain blocked pending explicit root authority. This report does not authorize a new slot or a rerun.
4. Only after separate authorization, obtain newly produced health evidence under the exact adopted source/runtime and health release; verify identity, source, runtime, probe/frame, ordered finite times and exact durable reserved/dispatched/completed journal. Then root may issue a detached episode release binding that new terminal and perform locked admission. First-C0/G3 review remains a separate unresolved gate.

Unresolved gates: root exact-source review/adoption and necessary source-dependent bindings; lawful distinct health resource, retained charges and current budget/window authority; fresh exact-source health evidence and durable accounting; detached root episode release and locked admission; first-C0/G3 review; no research outcome.

No completed production evidence, health charge, failure, timestamp, owner state/ledger, protected validation/formal data, or freeze was edited. Only three repair/test files committed in the isolated existing branch; report artifacts written in the requested output directory. Test mutations were restricted to synthetic temporary fixtures.

No GPU/provider probes, production health reruns, episode attempts, new launch, delegation, API fallback, owning-study commit, or authority adoption occurred. The isolated branch is clean after the repair commit. This executor stops at bounded repair evidence.
