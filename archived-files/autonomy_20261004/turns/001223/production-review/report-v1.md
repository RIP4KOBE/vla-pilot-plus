# Node15.6 CPU production review — BLOCKED

Source: `066f2bf57e05111fea329ff7c393ac3e002d7c0f`. Candidate remains disabled. Root alone adopts this review; no execution release or matching APPROVED production-review artifact was issued.

## Findings

### PR-01: Source-only worker command cannot pass terminal receipt verification

runner.worker_command uses source_execution.command, producing python -I -S -B -X pycache_prefix=/dev/null bootstrap.py scripts.qd_ed_n36_worker. worker.verify_terminal instead requires python -m scripts.qd_ed_n36_worker. The exact source comparison rejects the actual runner command even when every other receipt field agrees. A successful worker therefore cannot become a valid terminal through this adapter; it becomes aborted/INVALID_STOP and remains charged.

**Required action:** A separately authorized source repair must make terminal command validation use the same source_execution.command contract (including all isolation/cache flags, bootstrap path, module, context path and digest). Do not restore the obsolete -m launcher or weaken exact command equality. Add a CPU regression comparing the command actually written by the runner with the terminal verifier and rejecting altered flags/module/context. New commit/source closure, review and all40 composition are then required.

Evidence: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001223/production-review/command-check-result-v1.json` SHA256 `11ad75a5797c9af99ab61410debd375812907cc23e8086d1123896e1700cd5d8`, `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/scripts/qd_ed_n36_runner.py` SHA256 `85a60c60c64bc2a9af8884ab3be99e710dec6670e68636fec3ea62983655ff00` lines 112-120,170-173, `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/scripts/qd_ed_n36_worker.py` SHA256 `42733eb91beaec98a4e2c86378ecb585a3b67d941fe2f886061f6d637a772dad` lines 378-383, `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/scripts/qd_ed_n36_source.py` SHA256 `a28f09cb8f899bf0001684f6edcb3b3e52a2ec75d632ba5a5f01b7acd417c771` lines 25-27

### PR-02: Candidate runner addresses stale implementation journals instead of adopted owning journals

execute_one derives root from plan.worktree and snapshot checks root/data/<journal>; it does not follow authority.ledger_prefixes[*].path. All three adopted prefixes match study_worktree, but all three fail against implementation_worktree. The implementation journals are independent regular files, not owning aliases. This currently fails closed before device admission and cannot be repaired by changing only the external authority path.

**Required action:** Root must choose and review a single accounting owner before release. Either adopt the repaired source into the actual owning study checkout and recompose every path/source/runtime binding there, or separately repair the adapter to bind an explicit authorized accounting root consistently for state, all journals, retained-margin reads and locks. A root-managed ownership migration is another operation requiring its own exact binding/review; merely copying stale or current journals into a second independently writable checkout is not a complete ownership solution. Preserve all historical prefixes and the original charge. This reviewer performs none of these mutations.

Evidence: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001223/production-review/checks-v1.json` SHA256 `d7d29e08a71700d747983c8081d2071eca73dfc51245fc765907876962eb4c06`, `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/scripts/qd_ed_n36_runner.py` SHA256 `85a60c60c64bc2a9af8884ab3be99e710dec6670e68636fec3ea62983655ff00` lines 26-35,63-75, `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/scripts/qd_ed_n36_release.py` SHA256 `1afd0b01617f0645c2ad1187c861cdeab1cdc3ff24eaa28002547ed81cd813c0` lines 168-174

### PR-03: Turn1222 budget document is compatible but execution-state adoption is incomplete

The new budget authority exactly binds N36R1 protocol/accounting/amendment, limits and caps. At this review snapshot the owning state still has n36_budget_authority pointing to turn1197, while implementation state has no n36_budget_authority. Owning budget.amendment is an envelope containing prospective_accounting; release.admission requires budget.amendment to equal the exact authority.amendment {path,sha256} reference. Neither state passes those admission predicates.

**Required action:** After resolving the single accounting owner, root must reconcile state from authoritative journals under the correct locks and explicitly adopt state.n36_budget_authority == final_plan.authority and state.budget.amendment == authority.amendment. Preserve the existing rich amendment envelope as immutable provenance, not by losing its history. Retain caps/reserves, approval basis, retained margin, all charges and finite deadlines; do not treat the turn1222 document alone as proof that these execution-state fields were updated.

Evidence: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001223/production-review/checks-v1.json` SHA256 `d7d29e08a71700d747983c8081d2071eca73dfc51245fc765907876962eb4c06`, `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001222/budget-authority-v1.json` SHA256 `4b8721b2553e5759748ad261a372791ffcc78fd8b255f935151094f8748e1dfd`, `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/scripts/qd_ed_n36_release.py` SHA256 `1afd0b01617f0645c2ad1187c861cdeab1cdc3ff24eaa28002547ed81cd813c0` lines 191-196

### PR-04: Final handoff can consume the reserved absolute-deadline margin

pre_dispatch requires 1840 seconds remaining, but after further context/release verification and durable writes the runner checks only now < end at reservation and worker start. The worker then receives a fresh 1800-second timer, plus up to 40 seconds cleanup. Exact AST evaluation confirms both late guards accept one second remaining. This is a deadline race demonstrated on guard logic, not a measured running-worker overrun.

**Required action:** Separately repair both final handoff guards to require the full 1840-second remaining allowance immediately before admission/worker start, with the same min(protocol, coordinator, weekly) end. Keep the full episode budget rather than silently shortening it. Add a fake-clock CPU regression where preparation consumes the margin after initial admission; refuse worker creation, retain any unsettled reservation for root reconciliation and never signal a live process due to STOP.

Evidence: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001223/production-review/checks-v1.json` SHA256 `d7d29e08a71700d747983c8081d2071eca73dfc51245fc765907876962eb4c06`, `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/scripts/qd_ed_n36_contract.py` SHA256 `d6a7d10c3304f4e49f62c676065fa9794c5f230807f4f84cccb51e81552d0bd5` lines 145-185, `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/scripts/qd_ed_n36_runner.py` SHA256 `85a60c60c64bc2a9af8884ab3be99e710dec6670e68636fec3ea62983655ff00` lines 116-141, `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/scripts/qd_ed_n32_runner.py` SHA256 `09c3388d8c56b5e70bf822505538e1b65ec49928a0b2ae56aacd3246621eeda3` lines 45-73

### PR-05: Ready runtime and matching detached root approval are absent by design

Candidate remains n36-release-draft-v1 with frozen=false, release_enabled=false, authority=null and every phase disabled. Runtime provider_ready=false and cuda_egl_verified=false. Static native library inventory and inherited ROOT_REVIEWED controller semantics do not certify a current provider, CUDA/EGL device, live controller or same-worker audit.

**Required action:** Root separately reviews current official-login provider evidence and accounted reusable CUDA/EGL proof, then creates a new ready runtime and rebinds closure, controller evidence/proof and all40 manifests in a new immutable directory. Do not flip flags without evidence and do not use the N36 healthcheck API to bootstrap readiness: it already requires a valid detached release. No review or release is issued here.

Evidence: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001219/runtime-input-repair/cpu-v1/runtime-candidate-v1/draft/plan.metadata-complete.draft.json` SHA256 `534ac627428a9106a257142843f2887d3b45edcdc900adacc8c5d55297d9ce5d`, `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001219/runtime-input-repair/cpu-v1/runtime-candidate-v1/runtime.disabled-candidate.json` SHA256 `76e9893ede5b719c87b76287adc457f76c0e82c4d2005bca0fa6f3e5e1bb08cc`, `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001219/runtime-input-repair/cpu-v1/runtime-candidate-v1/native-build.disabled-candidate.json` SHA256 `3e7e4f522f8d463671e7fe83bef4762f45f0ab0e32298959e38b8357998052d7`, `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001219/runtime-input-repair/cpu-v1/runtime-candidate-v1/controller-semantics.candidate.json` SHA256 `1b65a5df76cea22ebe778f95910f7c1be1e5259837d5a24c3ad3dac02f9bb2fc`, `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/scripts/qd_ed_n36_release.py` SHA256 `1afd0b01617f0645c2ad1187c861cdeab1cdc3ff24eaa28002547ed81cd813c0` lines 44-128

## Accepted evidence and independent checks

Inherited turn1221 acceptance: 72 artifact hashes, 160 restored dependency paths, 3,291 runtime files and 40 actual composed manifests. Full CPU preparation/composition was not repeated. The retained earlier LFS scope exception remains in inherited evidence.

Own CPU checks: all four exact authority-bound records; protocol/accounting/adopted budget compatibility; all40 row/dependency hashes and unused outputs; original reserved/dispatched/aborted primary with exactly 86.40354533703066 GPU seconds; absence of fresh N36R1 attempts; owning versus implementation prefixes/state; relevant source bytes; static controller proof; draft/bare-reference rejections; deadline boundary and actual command/receipt mismatch reproductions. Tests evaluate exact pure source AST with explicit dependencies, not running production integration.

Checks: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001223/production-review/checks-v1.json` SHA256 `d7d29e08a71700d747983c8081d2071eca73dfc51245fc765907876962eb4c06`.
Command reproduction: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001223/production-review/command-check-result-v1.json` SHA256 `11ad75a5797c9af99ab61410debd375812907cc23e8086d1123896e1700cd5d8`.

## Live obligations remain open

- **RT-03:** Same-worker source/runtime/native library/build/device attestations before/after, GPU7 UUID, and deployed arithmetic. Static CPU or reusable EGL evidence cannot replace them.
- **RT-04:** Live controller, full decision/occurrence/archive/decode/commit/ack chain and control absence. Missing mandatory evidence is INVALID and stops advancement. Legitimately unavailable physical response remains Unknown, never inferred.
- **RT-05:** Whole-episode timing including imports and audits remains unmeasured.

## Exact root review / release shape

`qd_ed_n36_release._verify_release_contents` uses exact dictionary equality. Required review keys: `accounting`, `approved`, `authority`, `cohort`, `controller_semantics`, `decision`, `limits`, `native_build`, `phase_authorization`, `plan`, `protocol`, `protocol_review`, `runtime`, `runtime_closure`, `schema`, `scientific_source`, `source`.

The schema must be `n36-root-production-review-v1`, `approved` must be `true`, and `decision` must be `APPROVED`. `plan` is the final external `{path,sha256}` reference. All other fields equal the final plan bindings. This CPU review cannot truthfully emit that artifact.

The detached release uses the same fields, changes schema to `n36-execution-release-v1`, removes `decision` and adds only `root_review={path,sha256}`. The final plan must contain neither `root_review` nor `execution_release`. References accept no extra `bytes` key. DAG: ready inputs → immutable final plan → root review → detached release.

## Remaining root steps

1. Resolve PR-01/PR-04 source defects and PR-02 owner binding under separate root-authorized work. Review the new commit and relevant regression tests. This report is bound to 066f2bf57e05111fea329ff7c393ac3e002d7c0f and cannot approve a future commit.

2. Complete root accounting reconciliation/adoption for the single execution owner. The following is an equality contract, not a state-writing command.

3. After root accepts current provider and reusable metered CUDA/EGL proof, write a NEW ready runtime. Preserve frozen official current-login Codex gpt-6-astra low/E2/t180 contract, actual worktree and artifact root, tasks/inventory/seeds; bind reviewed provider evidence and accepted device proof. Static CPU review does not set readiness.

4. Write new closure and controller evidence bound to ready runtime ref. Validate any changed module/interpreter/distribution/native bytes rather than copying old acceptance.

5. Recompose all40 with the actual approved checkout/interpreter after readiness/source/path rebind. Destination must be new. The following argv is a template with explicitly named root-supplied placeholders, not an executed command.

Exact preparation argv template (root supplies the named placeholders only after prerequisites):

```json
[
  "<closure-bound python3.12>",
  "-B",
  "<final reviewed execution checkout>/scripts/qd_ed_n36_prepare.py",
  "--output",
  "<new immutable draft directory>",
  "--runtime",
  "<ready runtime JSON>",
  "--runtime-sha256",
  "<ready runtime SHA256>",
  "--runtime-closure",
  "<new closure JSON>",
  "--controller-semantics",
  "<new controller proof JSON>",
  "--native-build",
  "<reviewed native inventory JSON>",
  "--native-build-sha256",
  "<native inventory SHA256>",
  "--recovery-protocol",
  "/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001205/identity-repair/protocol.n36r1.unsigned-v1.json",
  "--recovery-protocol-sha256",
  "d76046f9e697831114b04f23e1db3746e614d504a018e2923fdbc4e3f927b3ce"
]
```

Rebind inventory/seed lexical paths if checkout changes, retain expected input bytes. prepare omits these metadata fields; add them to a new metadata-complete draft, then verify actual composition for that final metadata-bearing plan. Do not reuse old expected manifests: each embeds runtime/closure/controller/native/source refs and output paths.

6. Root alone constructs final plan, exact review and detached release in that order using the shape documented here, after blockers are resolved. Independently pin caller-supplied final plan/release hashes. Full verify_prospective_release(plan_ref,release_ref) is read-only closure verification; it does not replace locked admission, current resource/provider checks or same-worker native audits. No release JSON or runnable launch command is issued by this review.

The JSON report supplies the exact state, ready-runtime, closure/controller/native, metadata and detached-review equality contracts, plus actual CPU validation APIs. There is no invented budget-adoption or approval CLI. Rebinding ready inputs alone cannot fix PR-01/PR-04 source defects or PR-02 ownership.

## Limits

No GPU/provider probes, allocations, model loads, workers, agents, process signaling, source edits or state/journal/tree writes. No credentials/Poe, prohibited design document or protected outcomes accessed. Only this output directory was written. No provider/CUDA/EGL readiness, live native audit, scientific success or protected-phase authorization claimed.

STOP absent (including symlink check) and deadline active at final check 2026-10-10T01:00:00.076196+00:00; authorization ends 2026-10-11T11:13:13Z. Review remained within 1,800 seconds.

The first AST harness attempt failed because its namespace omitted `contextmanager`; v1 was preserved and corrected v2 passed. Two read-only summary assumptions (null control runtime binding and absent implementation amendment) were corrected; they were not production failures.

Full report: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001223/production-review/report-v1.json` SHA256 `21ecadb1df77e78a5b103e8595b63b4add386e84d02415881e69fc0b63201f1e`.
