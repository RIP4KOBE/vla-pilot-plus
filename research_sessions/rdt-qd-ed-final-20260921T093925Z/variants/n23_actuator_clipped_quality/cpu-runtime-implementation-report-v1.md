# N23 closed runtime CPU implementation

Status: **CPU_RUNTIME_READY / GPU_RELEASE_CLOSED**. Commit `b8457ab040ef2d7dc2ebc2fb0062695a93a01ea8` extends backend preparation `c60629bbb7bbe2ae2c3eb453cceb04dcde51f371`; strict scientific prototype `cebed8f17122395a31866ac739e4dace0221bc04` is preserved. Worktree is clean. No GPU, simulator or external provider call, real state/ledger/lock/tree mutation, budget adoption, owning study-source change or dispatch was performed. N22 remains priority.

## Runtime behavior

The new contract fixes original Dev tasks 0..9 in C0/Q0/N7/N23 task-major order, 40 attempts / 21 actual exclusive-process GPU hours, 1800-second whole-worker timeout +40 cleanup. It preserves the frozen promotion/futility rules and no retry. N7 remains comparator only, with explicit exclusion from legacy N7 Dev/validation routing. C0/Q0/N7/N23 all use the existing same-process wrapper; original main.py/Hydra argv and normal Dev provider/runtime checks are retained. A missing/failed receipt invalidates a charged attempt, including dead-child reconciliation. No parent CUDA re-audit is added.

Preflight is a separate fixed iteration in the ordinary append-only attempt ledger, charged to recovery before Popen. It is limited to one 120+40-second attempt; any prior reservation, failed/interrupted attempt or alternate ID blocks repetition. It performs only static/runtime-file checks, metadata enumeration and reuse of the exact existing GPU7 CUDA/EGL proof. It never calls provider verification, a model, simulator or new probe. Its finite worker, corpus and arithmetic checks are unchanged from the accepted backend preparation.

Root alone may adopt cumulative 478/100h and buckets 51/187/180/40/20, with protected hours 32/12. Admission checks ACTIVE/PASS/private ownership, one worker/GPU7, no external hold, exact root predecessor/final-source/runtime reviews, idle UUID/EGL/probe, and existing private locks. The full remaining 21-hour local ceiling plus 160 seconds preflight and all remaining protected hours must fit; the full remaining matrix and recovery attempt must fit their buckets/cumulative attempt allowance. No borrowing or automatic adoption helper exists.

The actual single terminal recovery ledger record, process/report hashes, native input hashes, source commit/bytes and runtime bind the backend proof. A supplied result JSON cannot replace the ledger. Dev freezing requires that actual proof and identical source. Explicit preflight reconciliation checks a dead owned process and conservatively charges elapsed wall time as aborted; it never infers success or creates a retry.

Supervisor status includes per-task/arm audited outcomes, actual denominators, paired gains/losses, clipping counts/time and model/reward/Stage/GPU costs. It does not label incomplete cohorts with full ten-task rates or impose positive-clipping/bonus activation vetoes. For a thrown runner exception, the charged terminal ledger remains authoritative; status identifies that ledger rather than pretending the failed cell returned normally.

## Validation

**251 CPU tests passed in 22.09s**, including prior N21/N22 routing and accounting, the accepted backend suite and new N23 matrix/profile/source/runtime/proof/adoption/resource/reserve gates. New execution fixtures test all four wrapped arms, unchanged Hydra arguments, the whole 1800-second timeout, missing receipts, charge-before-launch, launch error, timeout, child error, failed proof, interruption, cleanup error and dead-process reconciliation. They use synthetic roots and mocked devices/processes, not online measurements. Deliberate no-provider hooks guard arithmetic-preflight tests.

Reproduce from `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n23_actuator_clipped_quality/implementation`:

```bash
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest tests/test_qd_ed_n23_dev.py tests/test_qd_ed_n23_backend.py tests/test_qd_ed_n22_dev.py tests/test_qd_ed_n21_dev.py tests/test_qd_ed_final_runner.py -q --basetemp=../cpu-runtime-fixtures-v1
```

Fixtures remain in [cpu-runtime-fixtures-v1](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n23_actuator_clipped_quality/cpu-runtime-fixtures-v1); [final log](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n23_actuator_clipped_quality/cpu-runtime-verified-v1.log) and earlier logs are preserved. `git diff --check` passed before commit. The scientific helper, main.py, provider, Stage, descriptor/selector, decoder and existing full-loop CPU fixtures are unchanged by this runtime commit; their prior strict native test evidence remains distinct from these runtime tests.

## Review artifacts and source closure

[Backend draft](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n23_actuator_clipped_quality/backend-preflight-plan.draft-v2.json) SHA `891ba6f49c1e88fa0215df9c44df8b3cd640ae4899d6ed7f9b545b482bb89c71` and [Dev draft](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n23_actuator_clipped_quality/plan.dev.draft-v1.json) SHA `72a128800b2d9884748964ac6976e0c5b33c49239f792017b8ed423b86167ca9` are non-executable. Both bind the same 192 sorted source records, manifest SHA `face59ba6927edd054e0ad477371058915fbfd4d706c9a0680c916877f3e23e8` and commit above. CPU draft review confirms the backend rejects missing predecessor, Dev is unfrozen with no backend proof, and CUDA remains uninitialized. Drafts reference the inherited actual runtime but do not certify it against this isolated worktree; only later integrated-source runtime validation can do so.

The [machine report](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n23_actuator_clipped_quality/cpu-runtime-implementation-report-v1.json) contains the complete source/profile list, file hashes, exact limits and log hashes. Active profiles are C0/Q0 from baseline_profiles.json, N7 from candidate_n7.json and N23 from candidate_n23.json; N23's only profile delta is `qd_quality_mode=actuator_clipped_provider_v1`. Protocol and prospective amendment bytes retain their root-frozen SHAs.

Exact external-review schemas, required root state, accounting boundaries and prospective CLI activation sequence are in [closed-runtime-admission-v1.md](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n23_actuator_clipped_quality/implementation/experiments/iteration_023_actuator_clipped_quality/closed-runtime-admission-v1.md). The final root review lives outside source and binds actual final source plus runtime/protocol/amendment refs. No future backend report hash or external review hash is compiled into source, so freeze is not circular. Finish all source integration before the one metered preflight; any later change invalidates proof.

## Remaining closed gates

1. N22 must first receive valid aggregate rejection under its frozen Dev rule, or valid validation rejection after Dev promotion. INVALID is not an automatic transition.
2. Root must review/integrate final source and runtime, record the external prerequisite/final review, and adopt the finite amendment under owning locks after recomputing actual reserves.
3. Verified-idle GPU7 must pass the one separately charged exact arithmetic preflight. The original CPU/GPU replay mismatch remains unresolved; no CUDA readiness or task gain is claimed by CPU tests.
4. Only then may root freeze/review/release the 40-cell Dev cohort. Validation/formal dispatch remain closed and require their distinct frozen gates.

Guided constant-zero Stage2 remains deliberately unsupported and fail-closed; the separate ten-task Stage1 compatibility audit is not a full two-stage compatibility claim. Existing mismatch/failure logs and immutable prior drafts were preserved. This executor stops here for root review, without online action.
