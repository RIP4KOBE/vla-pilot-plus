# N23 v2 CPU delivery — no GPU release

Closed N23 v2 successor/recovery preparation is complete in the isolated N23 implementation worktree. Final branch commit is `8aa0ba8047fc65e3ccb129475220def2e469068b`, following `f06b251950b43aa42b3ed22f40a0735dfae27916`, based on `1bcf888e88181580bfb854b2e7aa1834bf85df99`. Both new commits must be integrated in order. The worktree is clean. Earlier v1 commits, protocols, drafts and failed logs are preserved.

The final source record binds205 files; canonical file-list SHA256 is `ff78d18581f2b036cc5dfd64b80da90aec09856b00dff52d8eb1f27e90fb0621`. Full record is `source-manifest-v2-cpu-final-v1.json`, file SHA256 `d634fec319e595ba059c4847f9a0e353871d4c18ad1dc1f372c9e78a5d7fb72d`. A future integration commit necessarily changes the commit identity: root must regenerate the manifest and both plans from the actual owning source before the one arithmetic preflight, then preserve that exact source for Dev. Do not reuse this isolated-worktree source record as an execution authority.

## Implemented boundary

New v2 modules are contract, predecessor, recovery, prepare, supervise, backend, and preflight_admit under `scripts/qd_ed_n23_v2_*`. Only two pre-existing files change: the final runner routes the explicit v2 cohort and retains bound same-worker receipts on invalid completions; the original v1 preflight admission now also rejects any v2 reservation/attempt. No main/core/policy/model/Stage/controller/provider/profile scientific code changes relative to the base. N23 still differs from N7 only by actuator_clipped_provider_v1, with original eligibility/descriptor/selector and176 canonical candidates/11 batches. External projected provider scores, raw-selected Stage binding and decoded actions retain their existing semantics.

V2 is a prospective new experiment, not a repaired or reclassified N22 result. Named predecessor admission requires the exact root-reviewed C0 task4 timeout proof, its native evidence, all16 prior audits,17 settled original ledger attempts, original INVALID_OR_INTERRUPTED result and current diagnostic reader bytes. The original valid aggregate rejection path remains; generic INVALID/invalid_resolved does not authorize entry. Root separately reports the actual predecessor proof passed; this executor did not read that actual proof/outcome data.

The diagnosed timeout remains scientifically invalid, with original incomplete token flags and observed counters preserved. An isolated copy of the original CPU validator records only three exact derivative gates; every other fault remains fatal. That result can authorize a typed recovery, never an accepted scientific cell. The sole optional safety-events absence is explicitly hash/presence bound. No empty file is created in historical output.

Every arm gets the same typed eligibility rule, at most two total whole-episode recoveries and at most one per cell. Original invalid primary costs remain charged; a recovery changes only budget bucket/retry lineage/eligibility reference. A failed recovery stops, never retries. The supervisor preserves a terminal journaled by run_plan before its invalid-result exception. Primary-attempt, all-attempt and first-valid-cell denominators are separate. Unknown token calls derive from every terminal's measured logical/usage-complete counters even if eligibility fails or recovery itself fails. Missing counters remain null. Token totals are observed partial aggregates; original missing candidate/score fields remain absent, with any diagnostic measurements separate.

The full forty-cell task-major C0/Q0/N7/N23 matrix, at most42 episode dispatches,22 local GPU hours and1800+40 episode limit are closed gates. Candidate futility is checked only after a complete quadruple. At least5 candidate successes, no worse than all comparators, all40 accepted native-valid cells and substantive fixed QD/ED are required for promotion. No per-episode clipping activation veto exists. N7 cannot promote; protected phases are closed.

The one120+40 arithmetic preflight is separately charged to recovery, never invokes provider/model/simulator and cannot be retried under either v1/v2 IDs. Any prior v1/v2 reservation/Dev dispatch closes that opportunity. Full remaining primary/recovery/preflight capacity plus protected32/12 GPU hours and180/40 attempt reserves must fit. Every episode uses the unchanged same-process worker wrapper/native audit, with PID/start ticks/boot and entire process wall accounted. Supervisor consumes receipt/report JSON only. CUDA arithmetic is restricted to N23 within that worker. Exact actual-GPU readiness remains unproven until the metered preflight.

## Validation

Focused suite: **189 passed in6.65 seconds**, log `cpu-v2-focused-final-v1.log`. Related regression: **165 passed in26.85 seconds**, log `cpu-v2-regression-v1.log`. Both used `n23_v2_cpu_pathguard_v1.py`, with **zero blocked reads** and CUDA uninitialized. Tests are synthetic; the path guard blocks actual artifact roots, current/owning worktree historical data/state and outcome JSON, while allowing named static protocols/Dev metadata and bounded fixtures. No actual root-created predecessor proof is whitelisted or read.

Focused coverage includes real normal-runner terminal shapes; actual runner orchestration with mocked process/device/provider boundaries on all four arms; charge-before-launch; original Hydra argv and ownership markers; valid, missing-receipt, invalid-primary and failed-recovery paths; exact source/runtime/input/retry identity; typed positive and negative diagnostics; unknown token accounting independent of eligibility; recovery ceilings; prefix and complete-quadruple futility; native/176/11 checks; full forty-cell promotion/rejection and first-valid denominator accounting; plan/source/protocol/adoption/resource/protected-reserve closure; mandatory single metered proof; optional safety absence and logical/physical status path aliases; predecessor immutable hash and closure faults.

The regression covers original worker exit/receipt behavior and strict backend checks, N22/N21 Dev routing and normal final-runner validity/budget behavior. No legacy real-data recovery suite was executed. No broader testing is necessary absent a new integration change or failure.

Reproduce from this implementation directory using `/home/hynx/miniconda3/envs/vla-pilot/bin/python`:

```
PYTHONPATH=.. OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -p n23_v2_cpu_pathguard_v1 -q tests/test_qd_ed_n23_v2.py --basetemp=../n23-v2-guarded-fixtures-review-new
PYTHONPATH=.. OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -p n23_v2_cpu_pathguard_v1 -q tests/test_qd_ed_n23_backend.py tests/test_qd_ed_n22_dev.py tests/test_qd_ed_n21_dev.py tests/test_qd_ed_final_runner.py --basetemp=../n23-v2-guarded-fixtures-regression-review-new
```

Preserved failures are not represented as passes. `cpu-v2-fifth-v1.log` has132 passed/15 fixture errors; a synthetic empty native index was written as one blank JSONL line. `cpu-v2-sixth-v1.log` has148 passed/7 failed/15 errors; the same index issue and a missing synthetic output parent. Fixes changed only fixtures. `cpu-v2-seventh-v1.log` then passed170 tests, with final coverage extended to189. Earlier38/39/109-pass logs remain.

One manifest-packaging attempt wrote its own new source record, then the strict guard blocked rereading that new JSON solely to compute SHA. The completed packaging command added only the exact three executor-created output paths to its temporary whitelist, with no root proof/evidence/outcome allowance. `cpu-v2-source-closure-v1.log` records205 committed sources, permitted source delta, zero blocked reads and CUDA false. This packaging issue did not expose historical data or change any source/gate.

## Root handoff

The exact authority, predecessor, timeout eligibility, final review, preflight context/proof and Dev release schemas plus four prospective activation CLI commands are in the committed `experiments/iteration_023_actuator_clipped_quality/closed-runtime-admission-v2.md`. The shorter previously published `predecessor-proof-schema-v2.md` remains consistent. Reader hashes are unchanged from root's successful actual review:

- recovery: `88457287d2621836324cd881d185b60bb60274d006cd01564f88dfac9f9a20fb`
- predecessor: `f4ecc06186e303c2fd9375df17b784821a0e03bac48f9b035fbb2a4771714956`

CPU drafts are `plan.cpu-draft.v2.final-v1.json` (SHA `5a47cf5a2439453f3282589e27486a71af3f59f5749062c55f528c827155f256`) and `backend-plan.cpu-draft.v2.final-v1.json` (SHA `b50ce0dbfc8f8a5d021a81d24acb3d5d19dc90ea4d518c4ae7e26e4b828322bb`). They lack predecessor/source approval/backend proof; backend also lacks corpus. They cannot execute. All manifests, logs, fixtures and reports are under the N23 variant; no new scattered experiment directory was created.

Remaining root actions: integrate the two new commits after the earlier accepted N23 commits; rebuild the source record at final owning HEAD; independently review actual frozen runtime/controller/source bytes; create external final-source-runtime-review-v2.json; adopt the exact already frozen finite amendment through existing locks/append-only ledgers; verify no preflight/Dev reservation exists and full protected reserves fit; freeze/run the single arithmetic preflight using the separately approved bounded corpus; only after strict valid actual proof freeze the Dev plan and create separate release. Preserve the same source/runtime after preflight. The existing zero Stage2 provider remains unsupported/fail-closed; this v2 task did not broaden scientific provider semantics or add fallback. Stage remains the current Codex login, gpt-6-astra low180s, with no Poe use and credentials untouched.

No actual GPU/CUDA/provider/model/simulator calls, real budget/state/ledger/lock/Arbor mutations, owning-source edits or protected outcome reads occurred in this v2 task. This is CPU preparation, not a performance result or release authorization.
