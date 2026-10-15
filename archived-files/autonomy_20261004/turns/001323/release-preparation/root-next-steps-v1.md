# N36R3 root review preparation

This package is disabled. It does not adopt source, change owning accounting,
claim runtime readiness, approve a release, or close G3. The accepted turn 001317
composition is bound directly through turn 001322's review; historical provenance
is not rebuilt. New plumbing changes invalidate any claim that the accepted old
source/runtime bindings cover the current commit.

Generate a new immutable package from this committed isolated checkout:

```bash
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 \
python -m scripts.qd_ed_n36r3_preparation \
  --authority "$AUTHORITY" --authority-sha256 "$AUTHORITY_SHA256" \
  --output "$NEW_OUTPUT_DIRECTORY"
```

The authority path/hash are external inputs. The output must be a new direct
child of its authorized output directory. The generator reads all three owning
ledger files, verifies the reviewed historical prefixes, binds complete current
bytes, and requires 505 retained dispatched/reserved attempts and
75.52725286641478 GPUh. It does not lock or write the owner. A concurrent ledger
change fails the snapshot; root must take a fresh locked accounting snapshot at
admission regardless. Reservation ledger reconciliation remains a root task.

Exact prospective arithmetic:

- 40 cells × (1,800 episode + 40 cleanup) = 73,600 seconds.
- Health allowance = 1,800 seconds; unused contingency = 200 seconds.
  Total finite ceiling = 75,600 seconds = 21 GPUh.
- Health bounds are simultaneous: at most 41 invocations, each at most 20 probe
  + 40 cleanup seconds, within 1,800 cumulative seconds. 41 × 60 = 2,460, so
  only 30 full 60-second reservations fit. This is not 41 guaranteed probes.
- Retained cost + retained conservative admission margin:
  75.52725286641478 + 0.23357169027962 = 75.76082455669440 GPUh.
  Add 21 = 96.76082455669440 GPUh.
- Absolute cap 224; effective cap min(224, 53.08404692669838 + 168) =
  221.08404692669838. After full cohort and full protected 32 validation +
  12 formal GPUh, effective prospective remainder = 80.32322237000398 GPUh.
- 505 + 40 = 545 attempts; 1,800 − 545 = 1,255. Baseline gets 10 and
  development 30; validation/formal caps remain 180/40, with no phase authority.
  Exact current bucket counts are in the generated accounting artifact.

These numbers are planning deductions, not current spendable headroom. No
automatic retries or recoveries are allowed. Standing authorization permits root
to prepare budget amendments without another user gate; it does not substitute
for exact-source root review, owning adoption, fresh readiness or detached release.
STOP remains a veto at both canonical paths. Deadline: 2026-10-11T11:13:13Z;
full episode admission needs at least 1,840 seconds before it.

Root sequence (separate transactions, none performed by this executor):

1. Review the exact commit and package digests. Compare changes using
   `git diff bb20aedb952638548dd347b9705dab2beba176c5 <source_after> -- scripts tests docs`.
   Review unchanged worker Main, receipt consumer, native/generic audits, scientific
   task/seed/threshold contracts and the new restart-persistent C0 veto.
2. Adopt the reviewed commit through the owning source workflow, separately from
   execution. A possible Git operation is `git -C "$OWNER" cherry-pick "$SOURCE_AFTER"`
   only after root resolves the differing owner history and reviews the complete
   prerequisite source composition; this isolated commit alone is not that composition.
   Rebuild source/runtime/closure/controller bindings for the actual adopted paths
   and commit; retain all five required_after modules and frozen runtime content.
3. Fresh readiness must be performed separately under owning accounting. Reconcile
   all three current journals and reservations under normal locks, preserve every
   historical charge and protected reserve, and bind finite authority to standing
   authorization. Check idle assigned GPU7, CUDA/EGL and official current-login
   Codex gpt-6-astra readiness with separately metered finite health allowance.
   No provider/GPU readiness command is executed or authorized by this package.
4. Remaining engineering blocker: N36R3 is deliberately draft-only in
   `cohort`, `pre_dispatch`, and release verification. Root must commission/review
   an explicit N36R3 authority validator and owner/source routing, finite health
   accounting and release transaction before admission can exist. Do not flip
   flags in these artifacts or relabel N36R2 authority. Then bind a fresh released
   plan, independent exact-source review and detached release by external hashes.
5. Only after those gates, the existing launch form is:
   `"$PYTHON" -I -S -B -X pycache_prefix=/dev/null "$ADOPTED_SOURCE/scripts/qd_ed_n36_bootstrap.py" scripts.qd_ed_n36_runner --plan "$PLAN" --plan-sha256 "$PLAN_SHA256" --release "$RELEASE" --release-sha256 "$RELEASE_SHA256"`.
   This is a future command template, not an executable release supplied here.
6. The first production C0 terminal is charged once before returning
   PAUSED_FOR_ROOT_G3 (or INVALID_STOP). Journal reconciliation also pauses on
   every restart and rejects any later dispatch. No plan field or CPU fixture
   waives the pause. Root must reconcile actual PID/boot/start ticks, dispatch
   context, worker before/after identities, immutable observations, required_after,
   monotonic executed inventory including Main, generated identities, native/generic
   audits and exact terminal charge. A separately reviewed continuation binding
   implementation is still required after G3; this patch has no resume override.

An invalid C0 retains failure/partial evidence and stops the cohort. A passing
CPU test, preparation package or C0 task outcome is not G3 or scientific acceptance.

Readiness API template for root's separate transaction (not run here): after
hash-verifying the newly adopted runtime and plan, call
`qd_ed_n36_runner.device_check()`,
`qd_ed_final_runner.verify_provider(runtime, qd_ed_n36r2_admission.child_environment(plan, runtime), root=source_root)`,
and `qd_ed_final_runner.runtime_gpu(runtime, owning_state)` under the normal
owning locks and reviewed N36R3 routing. These checks do not prove CUDA/EGL or
execute a task. The separately metered health transaction uses
`qd_ed_n36_healthcheck.run_healthcheck(plan_ref, release_ref, resource_id, timeout_seconds=20)`
only after its own valid root release/finite reservation authority exists. Its
current N36R3 rejection is a blocker, not a reason to bypass the release gate.
Root must resolve the preparation-health authority versus fresh episode-release
ordering explicitly; a historic provider_ready/cuda_egl_verified flag is not
fresh readiness evidence.
