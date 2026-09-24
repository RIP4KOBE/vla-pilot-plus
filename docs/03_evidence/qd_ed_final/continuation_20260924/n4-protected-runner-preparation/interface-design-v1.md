# Conditional N4 protected-phase tooling: interface proposal

CPU preparation only. This is not a promotion certificate, a phase release, a
frozen plan, or permission to inspect protected outcomes. The current remaining
N4 Dev executions are not read by this preparation. Source base is
`f6a9ab04c0f184bbe2f8c837b33492835bc8fec9`. The input memo is
`A/continuation_20260923/n4-protected-evaluation-preparation-v1/memo-v1.md`,
SHA `632c8dd210aaa950d54d8f5ab7caff41563596ea66034a35e9cc911afb802ee0`.
Root coordinates the Arbor tree and later review; this isolated executor owns
only the proposed contract/builder/supervisor/resource changes.

## Proposed file and API boundary

- `scripts/qd_ed_n4_evaluation.py`: pure contract validation, exact source mapping,
  full cell identity, promotion/recovery/release checks, phase budget capability,
  exposure/allocation and formal candidate latch. It imports unchanged
  `qd_ed_n4_plan` for source-bound metadata/audit checks only; it must not call
  N4 Dev admission to legitimize a protected phase.
- `scripts/qd_ed_n4_evaluate.py`: CPU prepare plus dedicated owned supervisor.
  Prepare needs the complete predecessor's reviewed certificate before reading
  actual protected seed metadata or emitting a real 60/40-row artifact. Output
  remains unfrozen, all phase authorization false, and has no execution release.
  Synthetic row construction for tests is separate from artifact preparation.
- E owns `scripts/qd_ed_n4_evaluation_report.py` and a separately frozen
  ablation-only native audit adapter. Proposed API:
  `recompute_dev(manifest, root, runner)` and `recompute(manifest, root, runner)`
  return `(computed_report, attempts, base_plan)`. Both validate named source
  dependencies, full terminal/inflight inventories, actual originating plan
  revisions, all SHA references and the immutable journal excerpt. No bare
  boolean certificate substitutes for recomputation.
- Generic runner/queue need explicit protected-N4 routing before the existing
  Dev-only N4 detector; direct dispatch requires the owned phase scope. The
  routing change is tooling-only and must preserve legacy N4 Dev behavior.
  Current production policy, configs, helper, Stage, decoder, environment,
  collector and deployed native auditor bytes remain exactly the selected Dev
  bytes. No integration into running W occurs during preparation.

## New contract, certificates and closed defaults

Use new versioned `n4_evaluation` schemas and phase cohort IDs, separate from
`n4_cohort` Dev and all N2/N3 schemas. The contract binds the selected Dev base
and all accepted source-identical checkpoint/recovery revisions, full source
inventory, frozen reporter identity, candidate profile, observed controls,
runtime/input/seed inventory, private resource authorization and prospective
protected-phase protocol. Production bytes are mapped exactly; only an explicit
list of new phase tooling and generic dispatch adapters may change.

Validation requires recomputed `complete_valid_12`, the frozen N4 >=2/4 and
>=C0/Q0 criterion, the Dev actual-prefix difference criterion, complete native
consumer/source/raw-Stage/safety/fixed-compute evidence, and substantive archive
behavior/quality/parent use. A first-three checkpoint, partial matrix, old N2/N3
report, changed selected production source, or report with omitted original
invalid/predispatch records is insufficient.

Formal requires the complete 60-row validation report, N4 >=10/20 and >=C0/Q0,
all correctness/cost/source gates, and the identical scientific candidate.
Before any first formal reservation, atomically persist one candidate
fingerprint under the private state lock. Restarts and eligible recoveries must
match; a new candidate cannot reuse the latch. Formal acceptance remains N4
>=5/10 and >=both controls. No extra ablation-superiority threshold is invented.
The >=1 actual-prefix difference is the preregistered Dev promotion gate; it is
reported in protected phases without adding a new per-phase quota.

Each released plan still needs a separate root execution-release reference,
binding exact plan SHA, source, scientific fingerprint, profile/runtime,
protocol, private resources, selected ordered keys and the real prerequisite
certificate. The release is not embedded back into the plan. No output report
sets `phase_authorized=true` or automatically creates a release.

## Matrices and ablation proposal requiring prospective freeze

Validation is two preselected frozen ten-task seed blocks, task-major C0/Q0/N4,
60 originals and 20 per arm. Formal uses the existing historical ten-task mapping
and task-major C0/Q0/N4/N4_QD_OFF, 40 originals. Full identity includes task,
env seed, policy seed, init index and row/file/BDDL SHA, profile and seed block;
blocks must not collapse into the old `(task, profile)` Dev key.

Before actual preparation/admission, verify exposure metadata under the private
lease/state lock. Seed novelty is checked independently from layout identity:
row0 reuse remains explicitly disclosed as seed robustness, not new-layout
generalization. Current c1 availability is not established by this source-only
work. No automatic replacement seed block is permitted after exposure.

The only currently supported QD-removal proposal is archive `none` with the
compatibility final-selection setting `archive_global_best`; production rejects
terminal mode plus no archive. With no archive the existing loop chooses the
last population first argmin. Keep provider quality (N2/N3 OFF), population16,
ten rounds and 176/11 compute. Removing the archive also changes archive parent
allocation/retention and its Stage scale reference to the ordinary population.
This is total QD removal, not a parent-only causal contrast. A profile that is
actively equivalent to C0 must be disclosed, while retaining all ten fourth-arm
episodes. E's ablation-specific native consumer audit cannot claim ten archive
parent rounds or a live archive reference, and cannot weaken deployed N4 audits.
The exact profile and CPU active-delta proof need root review before freeze.

## Private resource and recovery boundary

The new explicit independent-budget authority is
`A/resource-isolation-20260924-v1/authorization.json`, SHA
`4026c141ff9bd06f31734c0a43122327b359c35bd847670f641961df9ce81f47`.
W alone has 240 attempts/48 GPUh, original20/100/60/40/20 bucket caps and singleton
GPU3; X state, locks, ledger and scientific results are outside this phase.
Require the validated private migration/ACTIVE evidence and distinct own lock
paths; do not reinterpret the old shared-named N4 Dev record as having always
authorized independent budgets. Reuse existing same-boot engineering evidence
with unchanged files and no double charge; no implicit new GPU probe.

Proposed recovery maxima are four validation and two formal, one per original
cell, additionally constrained by remaining private/global recovery capacity.
These maxima and budget behavior need the new N4 prospective contract; the old
N2 authorization is not authority for this phase. Preserve raw recovery buckets,
invalid original terminals and all charged health/predispatch/episode costs.
Eligible causes remain exact known transport failure or independently evidenced
external occupancy/metadata-monitor timeout, with unchanged source/runtime;
unknown Xid, ordinary episode timeout, algorithm/safety/source or audit failure,
and a valid task failure cannot become recovery permission.

Every dispatch needs its full 1800+40s window. A verified phase capability may
exclude only its own protected hour reservation from the unavailable hours;
validation protects formal's10h. Raw accounting is never relabelled. Fourteen
and ten hours are protected minimum allocations, not guaranteed execution time
or new phase caps. All remaining originals and allowed recovery slots must fit
attempt/bucket limits; 100 episodes at worst-case duration are not promised.
Only a complete accepted validation and settled recognized costs may support a
new explicit reservation event changing validation hours to0/formal10 before
formal. Keep original60/40 attempt slots and all historical charges intact.
There is no reservation mutation during CPU preparation.

## Focused synthetic validation scope

Reject partial/forged/first-three promotion; changed source despite a matching
new fingerprint; missing invalid/predispatch records; duplicate or collapsed
seed-block cells; wrong decoded/native association; QD-active requirements
misapplied to QD_OFF; recovery plan row absent from the immutable base; exceeded
raw dispatch/recovery caps; wrong GPU/owner/boot; generic/direct entry without
owned scope; stale budget or incomplete1840 window; exposed seeds; changed final
candidate latch; and premature/unknown-cost reservation release. Positive
fixtures use complete synthetic60/40 matrices and genuine source-identical
plan revisions. CPU tests establish tooling behavior only, never task benefit.
