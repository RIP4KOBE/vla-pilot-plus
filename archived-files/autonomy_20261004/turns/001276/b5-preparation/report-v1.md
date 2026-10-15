# Node 15.6 — B5 preparation, release disabled

Status: **reviewable CPU preparation complete; production blocked**. Source commit `30c6321715df86c5bab623db607bab2811aed56d` (base `b1d20fc0481721da6ebaab161c5a2ef7c3d50173`), clean isolated worktree. Owner source remains the supplied `ca4e6a96`; no source adoption, budget adoption, root token, GPU/simulator/provider execution or scientific success. Score `null`, target_met `false`. B1/B3 and accepted B2/passive B4 remain historical accepted evidence; full B4/B5 release remain closed.

## Finite protocol and accounting

Fresh own ledger hashes match authority exactly: **504 attempts**, **75.49265038509455 GPUh**, 504 terminal episodes and23 terminal healthchecks, no in-flight workers/healthchecks. The reservation ledger still protects32 validation +12 formal GPUh. Both invalid charges remain: N36 **86.40354533703066s**, N36R1 **809.4826372319367s**. All unknown telemetry and historical invalid outcomes remain.

- Exact recorded decimal sum:271773.541386340166945s. Production floating-point snapshot is retained unchanged; add the frozen0.23357169027962GPUh margin once to obtain **75.72622207537417GPUh** conservative charge.
- Cohort:40×(1800+40)=73600s, plus1800s healthchecks and200s contingency = **75600s /21GPUh**. No extra attempt or automatic recovery.
- After maximum cohort:544/1800 attempts; baseline114/400, development343/1120, validation60/180, formal0/40, recovery27/60. Protected attempt headroom remains120 validation +40 formal.
- Conservative hours after cohort:96.72622207537417. Effective ceiling=min(224,53.08404692669838+168)=221.08404692669838. Remaining protected hours=24.2408240024308155 validation +12 formal. Unprotected effective headroom after maximum cohort=**88.1170008488933945GPUh**. No cap amendment needed or adopted.
- Unique preparation check `n36_healthcheck_n36r2_preparation_001276` plus one `n36_healthcheck_<episode_key>` per frozen primary cell:≤41 invocations,≤20s probe+40s cleanup each,≤1800s total (aggregate bound overrides41×60). IDs are absent from current own ledgers. Each new cost is freshly charged; failed/unknown/in-flight checks block, with no replay.

[Exact calculation](accounting-calculation-v1.json), [disabled protocol](protocol.prospective-disabled-v1.json), [disabled accounting](accounting.prospective-disabled-v1.json). Full1840s headroom is mandatory; max preflight+episode requires1900s. Coordinator deadline **2026-10-11T11:13:13Z** is unchanged. Full-cohort planning feasibility is a timestamped estimate, not a reservation or completion guarantee.

## Engineering and private routing

The old unconditional N36R2 rejection is replaced by gated prospective protocol validation, both-charge preservation, private journal routing, finite healthcheck identities/ceilings, independent B5 review and the unchanged full detached-release/source/runtime/native gate chain. Direct N36R2 admission additionally requires the real caller-supplied detached release references. Missing review/accounting/provenance/release fails closed.

Scientific source and worker cwd stay `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree`. State, private ledgers and runner/state operation locks route only to `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree`. No owner files or locks were changed. GPU7 UUID remains fixed and **not independently confirmed now**. Bootstrap excludes inherited adjacent-checkout paths, disables site startup and bytecode loading, and checks import search paths. Child routing remains current official gpt-6-astra only.

Actual workers must capture separate before/after runtime/source/native observations using exclusive-create, fsync and read-only files, hash-bound to the final worker receipt and process/context. Parent verification checks retained bytes and all existing native/runtime gates. These are tamper-evident retained files, not privileged-writer-proof WORM storage. **No actual worker receipts exist from this task.** CPU preflight cannot substitute for them.

[Precise patch](source-diff.patch), [changed-file hashes](source-change-manifest-v1.json), [routing and receipt specification](resource-routing-v1.json).

## Source bindings and validation

**The included plan is deliberately unbound and disabled.** Its old source/runtime/all40 manifest references remain stale historical references; all40 new contexts have `release:null`, and authority/root_review/execution_release/b5_review remain null. Do not reuse the prior source review for this commit. [Exact source-dependent rebinding list](source-dependent-rebindings-v1.json) identifies the affected inventory, runtime, controller references,40 manifests,40 contexts and derived joins. No completed B2/passive B4 broad hashes or broad suite was repeated.

Focused CPU checks: **11 tests passed**, plus **52 package rejection cases** and successful disabled-protocol structural validation. Includes real source-only bootstrap rejection of inherited adjacent paths, both invalid charges, finite healthcheck namespace, private root separation, missing release/review, reserve exhaustion/unknown duration, both STOP aliases/full deadline headroom, immutable receipt replay/tampering. Final tests and earlier focused iterations total **8.941s wall**, two-CPU affinity/thread caps, within180s. No GPU/worker/Main execution. [Tests](focused-tests-final.log), [package boundaries](package-boundary-checks-v1.json).

The owning state hash changed concurrently during preparation; the three ledger hashes and all budget fields remained unchanged. [State-drift evidence](owner-state-drift-v1.json) retains both hashes. This prospective snapshot is not live admission evidence.

The first package build caught an incorrect relocated owner-path assumption and rejected it. The owner route was corrected to the authority's exact path before regeneration; this retained finding is documented. The authority duplicates one STOP alias, so both accepted canonical aliases are explicitly checked without modifying authority.

## Remaining release prerequisites

1. Independent review of commit 30c6321715df86c5bab623db607bab2811aed56d and exact source diff, prospective protocol/accounting/private routing and CPU boundary evidence; no executor self-approval.
2. Complete listed source-dependent rebindings: new source/scientific_source inventories, affected runtime and runtime-closure records, controller references, all40 manifests/config joins, disabled plan/contexts; reject stale b1d20fc review for changed source.
3. Coordinator source adoption and owning-state adoption of externally reviewed N36R2 finite authority/accounting references after fresh live private-ledger reconciliation; existing224GPUh/1800 caps and protected reserves remain. No adoption performed.
4. Independently confirm current GPU7 UUID GPU-48473162-9548-1a19-04aa-ea86c5349187, idle/exclusive/private ACTIVE/PASS assignment, CUDA logical0/EGL4 mapping and current official gpt-6-astra provider readiness. No readiness established here.
5. External independent B5 review bound to final source/runtime/accounting/routing, root production review, final plan hash and detached external execution release. No root/external approval token exists in this package.
6. Immediately before each reservation and launch: both canonical STOP aliases absent (including dangling links), coordinator deadline2026-10-11T11:13:13Z and authority window permit full1840s, or1900s including maximal healthcheck; own locks held, no live/unsettled handles, all old/new charges retained, fresh ID/output and protected/global/cohort headroom.
7. During separately admitted actual worker: process-bound immutable before observations prior to Main, after observations after native audits; parent verifies hashes/process/context/source/runtime/native/controller/device continuity. Missing or invalid evidence retains costs and stops with no automatic recovery. This future evidence is not supplied by CPU preflight.

Both canonical STOP aliases were absent at final check `2026-10-10T03:53:50.853255+00:00`. Elapsed preparation time at report:717.9s of1200s. Existing active-worker drain/timeout/cleanup accounting policy is unchanged; STOP/deadline prevents new launches and never refunds a charge.

Machine-readable [report](report-v1.json); all artifacts are hash-bound by evidence-index-v1.json and report-checksums-v1.json.
