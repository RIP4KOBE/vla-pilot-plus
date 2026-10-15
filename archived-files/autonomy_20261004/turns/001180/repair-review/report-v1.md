# N36 independent CPU repair review

**PASS — bounded source repair review only.** Both SR-01 and SR-02 are repaired at `ab8e8c6f8fdfb66c3a82b0135c0441cf542a9557` relative to `e7cdf2c09a60ffb1d248f073c5639303b2ef01fa`. No new concrete source blocker was found. This is not source adoption, pinned runtime/native-build certification, or a full-episode audit.

`score=null`, `promotion=false`, `target_met=false`, `source_adopted=false`. Execution remains unreleased.

Authority SHA-256: `c915baa8d9e70fa3eafab6a4f3f052c35e47fff8738cee991fadc36dd72fb843`. All five direct references match their expected SHA-256. All 11 changed files match the candidate Git blobs and repair-report hashes; HEAD and parent match the requested commits.

## SR-01 — PASS: Stale filesystem bytecode no longer supplies the reviewed runner/worker/Main/auditor code path

Severity: HIGH / P1 prior finding; repaired in reviewed scope.

Actual worker_command delegates to source_execution.command: absolute bootstrap script with -I -S -B -X pycache_prefix=/dev/null. Runner execute_one requires an active bootstrap and attests its compiled inputs before admission/probes/dispatch. The bootstrap requires optimize=0 and a character-device /dev/null, disables ordinary sourceless and both modern and legacy zip execution, and reads/compiles source bytes directly in SourceFileLoader.get_code. This addresses cache reads, not merely cache writes.

The bootstrap compilation ledger retains fullname/path and SHA-256 of the same bytes passed to source_to_code. attest compares these digests against the frozen source/runtime inventory AND the current files, including transient source loads; it separately binds bootstrap and startup encoding hashes. Worker execution_before precedes Main; execution_after follows generic/native auditing. Parent verifies both receipts against loaded source/runtime receipts, requires prior compiled records to survive, and requires a Main compilation record. Existing module origin, worker __main__ spec, runtime, generated-source and mapped native-build checks remain.

Inherited auditor dependencies are not limited to the five hardcoded receipt names: verify_receipt lines 125-136 joins every .py in the separately checked loaded/runtime inventories. qd_ed_n31_reference.same/require and qd_ed_n30_native.provider_target remain imported dependencies; ordinary and transient SourceFileLoader imports use the patched loader. The generic auditor also has spec_from_file_location/exec_module decoder paths, which use the patched SourceFileLoader and leave compilation records even without persistent sys.modules entries.

Main is compiled with SourceFileLoader("main", exact root/main.py), then runpy._run_module_code preserves script __spec__=None, empty __package__, temporary __main__ and argv. It does not use run_path to deserialize a code cache. This relies on the bound CPython runpy implementation.

Read test assertions and hash-verified saved logs, including the stale-cache control that actually returns stale! under -B, the repaired source result, unchanged poisoned cache, sourceless/zip rejection, changed compiled-source/loader negatives, missing dependency receipt rejection, and Main globals restoration. Saved test10 copied bootstrap/source/runner/worker/native/arithmetic/N31-reference/proposal/policy files exactly match the candidate. No reliance solely on producer PASS fields.

Limits: End-to-end caller and receipt tracing is static. Existing subprocess evidence reaches copied-tree runner/worker --help and source-loader decoder extraction, not the released worker body, live policy/model, or native-build startup. The copied core initializer is intentionally suppressed and inventories are synthetic.

Source references: [scripts/qd_ed_n36_bootstrap.py:8-86](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/scripts/qd_ed_n36_bootstrap.py:8); [scripts/qd_ed_n36_source.py:23-139](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/scripts/qd_ed_n36_source.py:23); [scripts/qd_ed_n36_runner.py:62-67, 109, 125-148, 170-172](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/scripts/qd_ed_n36_runner.py:62); [scripts/qd_ed_n36_worker.py:201-271, 299-339](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/scripts/qd_ed_n36_worker.py:201); [scripts/qd_ed_n34_source.py:296-358, 373-443](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/scripts/qd_ed_n34_source.py:296).

## SR-02 — PASS: Archive descriptor origins are joined to actual ordered projection events and the cached physical observation

Severity: MEDIUM / P2 prior finding; repaired in reviewed scope.

Initial geometry carries iter_idx=-1; each offspring descriptor carries its actual i. The actual policy decoder feeds each adapter projection. Metadata assigns candidate b and occurrence (iter_idx+1)*16+b, matching the archive occurrence ranges. The adapter captures the same queried raw start_position before its original native cast and records action_sequence, cast_eef_start and trajectory in the real projection_origin event. The recorder snapshots tensors/arrays without dtype conversion and returns the sequence used by geometry.

The whole-audit caller selects tagged projection_origin events between the actual canonical_candidate_batch and n36_archive_update of this decision. verify_assignment requires exactly 16, sequence-list equality, unique ascending order, strict interval bounds, matching iteration, candidate/occurrence identity, and episode/decision/global_step/reset agreement. Existing lifecycle replay independently enforces global event order and reset epochs.

Raw geometry origin must match both event source_eef_position and packet observed_eef via same(), which hashes dtype, shape and contiguous raw bytes and requires finite CPU tensors. Thus binary64 1.0 -> 1.001 cannot pass just because both cast to bf16 1.0; corrupting both geometry and event still conflicts with the packet. Action prefix, cast and projected trajectory are independently joined before unchanged deployed-shape arithmetic is recomputed.

Main constructs the boundary packet from cached observation fields. _convert_nested_dict uses torch.from_numpy without a float32 cast; capture_context preserves dtype, reshapes and clones. For subsequent nonterminal boundaries, the native auditor joins packet fields byte-exactly to the preceding pre_reset_outcome observation, with step adjacency. The first boundary uses the cached reset observation and does not fabricate a preceding physical record.

Read actual AST-extracted producer/adapter/recorder tests, independent verify_assignment assertions, six fp32/bf16 initial/first/final-update positives and fifteen corruption negatives. Saved test02/test04 evidence covers these paths. Producer_PASS is ignored. No new tensor replay or historical tensors were used.

Limits: Actual controller.ee_pos (adapter lines 1151-1161) versus cached robot0_eef_pos equality remains a prospective physical/runtime obligation. Missing/nonfinite required origin or any dtype/byte mismatch fails closed; this review does not assume equality in a simulator. No whole-episode or CUDA execution was performed.

Source references: [core/rdt_policy_steer.py:5083-5091, 5545-5593, 6608-6613, 6693-6708, 7953-7992](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/core/rdt_policy_steer.py:5083); [core/env_adapters/libero_adapter.py:1657-1697](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/core/env_adapters/libero_adapter.py:1657); [core/decision_evidence.py:25-37, 136-172](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/core/decision_evidence.py:25); [scripts/qd_ed_n36_native.py:88-129, 233-244](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/scripts/qd_ed_n36_native.py:88); [scripts/qd_ed_n36_arithmetic.py:66-117](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/scripts/qd_ed_n36_arithmetic.py:66); [scripts/qd_ed_n31_reference.py:12-20](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/scripts/qd_ed_n31_reference.py:12); [main.py:1662-1664, 1847-1874](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/main.py:1662); [core/qd_observed_jaw_approach.py:37-51](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/core/qd_observed_jaw_approach.py:37).

## RR-03 — PASS: Source-only startup assumptions and exceptions are bounded, but do not certify the deployed runtime

Severity: INFORMATIONAL; explicit trust boundary and later release gates.

Pre-hook imports are sys, frozen import machinery, posix and the _hashlib native extension; filesystem encoding imports precede the script. The impossible cache prefix is established by interpreter arguments, before those encoding imports, and their hashes are required. Linux/CPython startup, an intact /dev/null, immutable launch files and a frozen interpreter/runtime/native extension inventory are trusted. Startup hashes for bootstrap/encodings are read after their execution, not live-code attestations of hostile concurrent rewrites.

Frozen modules require FrozenImporter and _imp.is_frozen; their executable bytes are interpreter-bound rather than established by a stdlib .py hash. Native extensions are handled by inherited runtime inventories; mapped Torch/CUDA/driver checks are retained separately. torch.ops/classes are checked as instances of their exact inventoried owner classes. Existing generated-runtime owner/template/content/live-origin rules are still required in addition to compilation digests.

No-site startup suppresses .pth/sitecustomize execution. The bootstrap explicitly restores root, PYTHONPATH entries and site.getsitepackages directories; -I therefore does not mean PYTHONPATH is wholly ignored by this application. These imported sources must still join frozen inventories. This is a compatibility and trust assumption to validate in the actual pinned environment, not an automatic permission to restore hooks.

The ledger proves the inputs to the standard source loader and the reviewed caller path. It is not a sandbox or exhaustive attestation of arbitrary exec/eval, native-generated code, arbitrary no-file module objects or later monkeypatching. Live integrity and generated provider/controller semantics remain trusted/reviewed separately. The active loader identity checks do not eliminate this boundary.

Worker_imports timing starts after interpreter/bootstrap/runpy and initial os/json/pathlib/time imports. Thus that phase alone is not total startup time. The parent starts its process-wall timer before Popen and waits under the existing 1800-second worker bound, so omitted bootstrap time is still charged in parent process wall time. No measured pinned-startup/whole-audit overhead or feasibility claim follows from the short copied-tree tests.

Limits: No actual pinned interpreter/native-build startup receipt was produced. Fail-closed compatibility failures during later preparation must be resolved concretely; do not weaken hashes or replay old receipts.

Source references: [scripts/qd_ed_n36_bootstrap.py:16-78](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/scripts/qd_ed_n36_bootstrap.py:16); [scripts/qd_ed_n36_source.py:28-38, 54-109, 119-139](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/scripts/qd_ed_n36_source.py:28); [scripts/qd_ed_n36_worker.py:14-35, 220-259](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/scripts/qd_ed_n36_worker.py:14); [scripts/qd_ed_n36_runner.py:125-143](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/scripts/qd_ed_n36_runner.py:125); [scripts/qd_ed_n36_build.py:43-67](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/scripts/qd_ed_n36_build.py:43); [docs/n36-cpu-audit-repair.md:37-52, 80-103](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/docs/n36-cpu-audit-repair.md:37).

## RR-04 — PASS: Collateral changes preserve the scientific arithmetic and control branches within the repair diff

Severity: INFORMATIONAL.

All 11 changed files were inspected versus the base. Policy changes add descriptor evidence metadata only. The adapter retains the single pose query, tensor cast, 0.01 multiplication, cumsum, addition and concatenation. No extra projection/provider/model/simulator call or scientific parameter is added.

verify_scores and verify_parents ASTs are identical across revisions. Existing projection/descriptor/quantile/bounds/cell operations and exact comparisons remain unchanged; only raw/cast/event joins are added around them. Proposal geometry, memory/latch, config/control definitions, scoring/archive algorithms, other15/remainder behavior, task/seed identities and gates are outside this diff.

Older control paths omit iter_idx descriptor metadata and retain the old projection event fields; four saved source-parity cases cover fp32/bf16 with and without origin capture, including equal native bytes and one pose read. This is not full model/RNG/control-policy parity certification.

Test-runner collateral stubs active/attest only in the synthetic lifecycle fixture and adds a synthetic runtime_closure. Those journal/Popen tests cannot substantiate real interpreter attestation; the dedicated import fixture supplies the narrower startup evidence. Documentation states the source/runtime limits. All ten changed Python files parse; git diff --check succeeds.

Limits: Added CPU snapshots, device copies, file hashing and no-cache import compilation can affect latency/storage. Timing effects are not scientific arithmetic changes, but must fit the later frozen worker/cohort budget.

Source references: [core/env_adapters/libero_adapter.py:1657-1697](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/core/env_adapters/libero_adapter.py:1657); [core/rdt_policy_steer.py:5546, 6610, 7971-7992](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/core/rdt_policy_steer.py:5546); [scripts/qd_ed_n36_arithmetic.py:15-63, 96-117, 120-149](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/scripts/qd_ed_n36_arithmetic.py:15); [tests/test_n36_audit_repair.py:285-332](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/tests/test_n36_audit_repair.py:285); [tests/test_n36_runner.py:128-145](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree/tests/test_n36_runner.py:128).

## Checks and reused evidence

Read test code and hash-verified all ten logs/timing records, verification/static-check records and harness. Iterations 1,5,9 failed and remain preserved; later fixes/tests are recorded. Test02: 23 passed; test04: 32 passed across then-current targeted repair/runner/native-build fixtures; test08: 5 selected startup tests passed; final test10: expanded actual import/decoder fixture passed. These are incremental recorded runs, not a new all-tests-at-final-commit run.

AST-extracted projection methods, synthetic tensors/observations, copied core initializer suppression, synthetic inventories, --help exit and extracted decoder execution only; no real released worker body, Main/model or whole episode.

The final saved import fixture matches the candidate loader, runner, worker, native/arithmetic auditor, inherited N31 reference, proposal and policy source. Ten changed Python files parse; `git diff --check` passes. `verify_scores` and `verify_parents` have identical ASTs. No new CPU reproduction was needed or run; new test CPU charge is 0 seconds. Full hashes and evidence paths are retained in report-v1.json.

## Open runtime and release obligations

- **RT-01 (Later source/runtime preparation):** Adopt source only through the separate authorized process and rebuild externally frozen all40 source/runtime/config/checkpoint/cache/provider/task/init/controller manifests using the source-only runner/worker command. This review grants no adoption or release and does not inspect or change owning state.
- **RT-02 (Actual pinned startup/native-build preparation):** Materialize pinned RDT/LeRobot and full dependencies, verify actual isolated/no-site startup and imported/transient source closure, encoding/frozen/native/generated exceptions, runpy behavior and mapped interpreter/Torch/CUDA/driver build. Copied --help with a suppressed core initializer and synthetic inventories is insufficient.
- **RT-03 (Separately authorized metered execution):** Require before/after live worker source-execution/runtime/native-build receipts with parent joins, exact assigned-device projection/provider/descriptor/bounds/cells recomputation, and retained evidence throughout auditing. No CPU arithmetic proxy, epsilon, restored uncontrolled loader or producer PASS substitution.
- **RT-04 (Prospective whole-episode audit):** Demonstrate exact controller-pose/raw-observation joins, first-boundary cached anchor, subsequent physical observation continuity, every actual candidate/occurrence/order, all ten offspring updates and archive/parents/final-selection/decode/commit/ordered acknowledgements/response, plus control absence. No fixed historical later populations or tensor replay substitute.
- **RT-05 (Runtime feasibility/accounting preparation):** Measure complete interpreter/bootstrap/import, source hashing, snapshots/storage and audit overhead under the existing parent process-wall/cohort limits; worker_imports excludes early bootstrap time. Reconcile release/accounting independently. No runtime feasibility or healthcheck is certified here.
- **RT-06 (Later scientific evaluation):** Fresh matched task outcomes, detour survival and physical benefit remain Unknown. Protected validation/formal results and required QD/ED ablations remain untouched and outside this review.

No smallest source repair is requested: no additional demonstrated source defect was found in this bounded review. The open runtime gates cannot be replaced by this PASS.

## Source SHA-256

| Changed file | Candidate SHA-256 |
|---|---|
| core/env_adapters/libero_adapter.py | `17fb74b3d475c91bc015222d4b61989c82a57f83935581b54935bab8080be26d` |
| core/rdt_policy_steer.py | `73387f980404b37997ac850619ff45770fae829ad079c62e8040e66887d2ef7d` |
| docs/n36-cpu-audit-repair.md | `cd27240c2ca9669509b4f1206a4255eb943bb2e1d1cf55ebbd3d4029d7551538` |
| scripts/qd_ed_n36_arithmetic.py | `af69bbf02ebddb95458ec9f70719221d29bec36fa88e1cda6f20848dd20de6ef` |
| scripts/qd_ed_n36_bootstrap.py | `84c569b975a21a5d075245e28b827acc7e23c8e10c00f31a3eba0febe0743cc4` |
| scripts/qd_ed_n36_native.py | `df3b354712901a382e3126ac3dac510c000dda99916ddd7388fcdcfbc8983536` |
| scripts/qd_ed_n36_runner.py | `2c4838375956c3010280dde22b272f34798a199d573f2bf7fd07fee8262f99a2` |
| scripts/qd_ed_n36_source.py | `a28f09cb8f899bf0001684f6edcb3b3e52a2ec75d632ba5a5f01b7acd417c771` |
| scripts/qd_ed_n36_worker.py | `7bdf32a721c00be9f21659ec42db458dbb4d60569ef7acccde3641c7aca37cf6` |
| tests/test_n36_audit_repair.py | `8a8874f39496bf2465401536a541fb35c4750f7332f7afb4bf2b2258a49acd26` |
| tests/test_n36_runner.py | `0e52130c7689784af3de3bb67abd6a70566821d1fcb21cf996dfe98a9d87bbca` |

The JSON also records hashes of unchanged source dependencies inspected during tracing. Only the two requested reports were written. Previous evidence is preserved; no source/commit/adoption/owning-state mutation, GPU/provider/model/simulator/healthcheck call, historical tensor/protected-result access, credential access, prohibited document access or delegation occurred.
