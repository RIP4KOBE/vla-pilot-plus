# Static review: repeated N26 validation work

The source contains substantial nested reconstruction of the same historical Git/provenance facts. This is a static duplication finding, **not a measured bottleneck or a reason to bypass active checks**. N26 remains at frozen 6026794; nothing in this review authorizes modifying its running controller.

Scope: 11 source files, 264,450 distinct source bytes, under the 20-file/2-MiB cap. Only source text, hashes and sizes were inspected. No production imports/execution, tests, Git-history commands, process inspection, runtime manifests, journals, results, tensors, credentials, GPU or APIs were accessed. Exact paths/hashes are in the accompanying source scope.

## Static call graph

```text
supervise.launch
  runner.validate_plan → contract.validate_contract
  [lock] contract.full_capacity
supervise.execute → each one_attempt
  runner.run_plan
    [runner lock] validate_plan
    selected one-row loop: validate_plan AGAIN
    check_budget → contract.require_state
    protected_budget → full_capacity → require_state + settled_control_proofs
    admission → all accepted prior cells
    worker.build_context → source_record
  accepted_cell + read_worker_report (again)

contract.validate_contract
  worker.source_record
  metadata → final_review; authority → final_review; predecessor
  validate_runtime
  require_state → budget_authority; authority → final_review

contract.final_review
  bridge.verify → bridge.build
  backend.verify_proof → backend.validate_plan → backend.authority
    → backend.source_review → bridge.verify → bridge.build AGAIN
  predecessor → logical.read_gate → common.build

bridge.build
  logical.verify_composition → historical git show + byte/AST/reverse comparisons
  Phase-A current-byte / historical-route checks
  verify_reverse → historical git show
  historical_control_proof → 257 historical git show operations
  predecessor → logical.read_gate → common.build

common.build
  NEW GitObjects cache → historical_sources (257 old + 271 continuation entries)
  historical metadata/result/cost reconstruction
  ALSO current helper bytes, absent-file checks and process cleanup
```

The two per-attempt `validate_plan` calls are explicit in [qd_ed_final_runner.py:1747](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n26_clean_output_rbf/conditional_implementation/scripts/qd_ed_final_runner.py:1747) and line 1786; the controller requests one cell at a time ([qd_ed_n26_supervise.py:26](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n26_clean_output_rbf/conditional_implementation/scripts/qd_ed_n26_supervise.py:26)). The metadata/authority/state recursion is in [qd_ed_n26_contract.py:100](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n26_clean_output_rbf/conditional_implementation/scripts/qd_ed_n26_contract.py:100), line 223 and line 233. The second bridge reconstruction inside the arithmetic-proof authority chain is visible in [qd_ed_n26_backend.py:17](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n26_clean_output_rbf/conditional_implementation/scripts/qd_ed_n26_backend.py:17), line 45 and line 145. No arithmetic worker is rerun by those metadata checks.

Historical composition loops are in [qd_ed_n26_logical.py:131](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n26_clean_output_rbf/conditional_implementation/scripts/qd_ed_n26_logical.py:131) and [qd_ed_n26_bridge.py:22](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n26_clean_output_rbf/conditional_implementation/scripts/qd_ed_n26_bridge.py:22). The common reader's Git cache exists, but is allocated anew by every default `build`: [qd_ed_n25_cont_downstream.py:34](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n26_clean_output_rbf/conditional_implementation/scripts/qd_ed_n25_cont_downstream.py:34), line 52 and line 166. Each uncached object uses separate size/blob Git subprocesses; the same object's later reads within that one build are cached. There is no visible cross-build cache. Exact total subprocess count per dispatch and elapsed cost were not measured.

Current-source checks also repeat: [qd_ed_n23_worker.py:54](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n26_clean_output_rbf/conditional_implementation/scripts/qd_ed_n23_worker.py:54) obtains HEAD, runs `git show` per path, compares working bytes and hashes them. Context construction, worker entry, successful worker completion and receipt verification can reach it (lines 111, 130, 201, 259; N26 context route at [qd_ed_n26_contract.py:254](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n26_clean_output_rbf/conditional_implementation/scripts/qd_ed_n26_contract.py:254)). Prior-cell admission rechecks accepted receipts, so this work can grow with prefix length. Receipt checking also calls `evidence_record`; its payload-hashing cost was not profiled and is outside a proposed historical-Git cache.

The runner already caches file SHA by resolved path/device/inode/size/mtime/ctime ([qd_ed_final_runner.py:157](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n26_clean_output_rbf/conditional_implementation/scripts/qd_ed_final_runner.py:157)). Therefore repeated `verify_files` does **not** imply every model/runtime byte is rehashed on every call. Worker `sha/source_record` and the historical Git loops have separate behavior.

## Pure historical work versus live obligations

| Potentially reusable deterministic work, with exact identity key | Must remain fresh or drift-checked |
|---|---|
| Immutable commit/path/blob verification; fixed reverse patches and AST/function-boundary comparisons | Owning root/import identity, actual HEAD, every current source/profile/route byte and link resolution, complete manifest membership |
| Deriving a historical logical disposition and cost summary from identical sealed metadata bytes | All referenced metadata/protocol/authority hashes; original absences; current process boot/PID/start/group cleanup |
| Fixed proof/report schema/source/runtime/36-case associations, with original provenance retained | Current matching predecessor Dev/resource journal subsets, settled resource and absence of later reservations; current authority adoption |

Do not memoize `common.build`, `read_gate`, `final_review` or `full_capacity` wholesale: those functions mix the two columns. In particular, `logical.current_matching` calls the original root-attested subset comparison ([qd_ed_n26_logical.py:81](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n26_clean_output_rbf/conditional_implementation/scripts/qd_ed_n26_logical.py:81)), and common build performs fresh absence/process checks ([qd_ed_n25_cont_downstream.py:166](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n26_clean_output_rbf/conditional_implementation/scripts/qd_ed_n25_cont_downstream.py:166), [qd_ed_n25_cont_evidence.py:63](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n26_clean_output_rbf/conditional_implementation/scripts/qd_ed_n25_cont_evidence.py:63)).

## At most two future optimizations

1. **Reuse bounded, verified historical Git objects and their pure byte/AST derivations.** A future implementation could batch immutable object reads or keep a controller-local cache keyed by repository identity, exact commit/path, expected content SHA and verifier/source-bridge version. Keep the original finite object/byte allowlist; never resolve mutable branch names as cache keys or relabel old proofs as new. Independently compare current source/profile bytes, root/link/import identities and HEAD at each required boundary, including worker entry/completion and receipt verification. Cache mismatch/error must fail closed. This could reduce Git subprocess setup and repeated AST parsing; benefit is unmeasured.

2. **Share a verified historical evaluation within one admission, while splitting out live checks explicitly.** A future source bridge could carry the identical immutable evaluation through metadata → authority → backend-proof checks, instead of rebuilding it in each nested branch. Key it by all transitive source, protocol, plan, runtime, metadata, proof and review hashes. On every dispatch under the original locks still reread current state/authority adoption and filtered journals; enforce no hold, single owner, no unsettled costs, exact cell/first-valid/recovery order, whole-quad futility, cumulative/local/bucket caps and protected reserves, full 1840-second capacity, current proof settlement, preserved missing-evidence/process checks, GPU7 UUID/EGL/exclusivity and current Codex-login transport/no fallback. Recheck device/provider immediately before dispatch; preserve same-process metering, cleanup, native/profile gates and terminal costs. A cached historical PASS must never itself authorize dispatch. Benefit is unmeasured.

Both require a separately reviewed future change after N26 closes, with equivalence and drift/fault tests. No optimization, cache, bypass, new source, or execution permission is delivered here. Future Stage remains current Codex account only; this review made zero calls.

