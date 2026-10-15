N35 CPU implementation, node15.5 — ready for root review, not a GPU release.

Commit `c3730e5287fe659dffc95c40bf6d8b7ba95d1da9` on `exp/n35-closure-intent-cpu-20261009`; base `969d5fb57c90f61dfc93331346f0ea8158f4eaf1`. The isolated worktree is preserved. The commit contains 26 source/config/test files and excludes copied `AGENTS.md`, state, ledgers and results.

Authority and all 22 bound references matched their exact hashes. Frozen protocol v2, its independent PASS review, root CPU-only acceptance, hypothesis and bound CPU feasibility review were followed. No new scientific context or hypothesis change was introduced. [Authority verification](authority-verification-v1.json) records the checks.

The direct occurrence and execution chain is implemented as follows:

1. Canonical native populations carry decision-local occurrence IDs: initial rows 0..15, parent round i rows (i+1)*16..(i+2)*16-1. Decision/episode identity disambiguates reuse across chunks.
2. QDArchive transports the actual winning occurrence through detach/clone, equal-content deduplication, incumbent retention, snapshots and selection. Reward/fingerprint/cell tie ordering is unchanged. Old callers omit occurrence IDs and retain their original snapshot schema.
3. Origin is assigned to the actual inserted slot15 occurrence, never recovered from hashes, parent ancestry or another equal-content occurrence. Only directly selected observed_close_dwell can arm. Ordinary and memory winners remain their own origins even when equal to N34 bytes. Missing/merged transport is a mandatory audit failure; an explicitly unresolved origin cannot arm.
4. The selected occurrence is bound to native dtype/shape/content, selected latent, actual float32 decoder output, committed postprocessed eight-command chunk, and eight identity/order/action-linked acknowledgements recorded only after adapter.step returns.
5. After eight nonterminal acknowledgements, the token retains a minimal execution witness and drops both native and decoded trajectories. All eight decoded grip commands must be positive. Terminal, exception, incomplete execution, changed episode/target/provider/Stage/tracker, unguided operation, or a nonadjacent boundary cannot rearm it.
6. At immediate next guided boundary, same recognized target/Stage/provider/tracker continuity and finite strictly decreasing measured qpos[0]-qpos[1] are required. Transfer consumes prior state once; missing physical trigger evidence is visible ineligibility, while missing mandatory audit evidence invalidates the run.
7. A frozen boundary latch applies to all ten existing parent rounds. Every round clones its current archive best and changes only native [:8,10] to +1 in slot15. The latch expires regardless of selection. N34 remains fallback when ineligible; C0/Q0/N34 have no closure memory.
8. Independent lifecycle and native replays verify occurrence transport, archive retention/ties, actual step returns, all ten proposals, other15 commitments, untouched bytes, exact source/runtime anchors, compute counts and native/decoded delta telemetry, including decoded delta zero. Same-process receipts and the parent verifier require these gates.

The prospective controller preserves the frozen fresh 40-cell task-major schedule, complete-quadruple futility, invalidity stop, no retries/replays, full atomic 1840-second reservation, separate 1800-second cumulative healthcheck allowance, 21-hour cohort bound, both 224-hour and 221.08404692669838-hour cumulative ceilings, and remaining protected validation/formal reserves. STOP and deadline block new work and drain the admitted child. The healthcheck wrapper requires a future detached release, uses only the owned child, settles its separate charge, and never updates frozen runtime readiness.

CPU validation has passing coverage for 130 N35 cases and 43 additional pinned compatibility/source/runtime cases across focused runs. These are overlapping runs, not a single 173-test suite. Earlier failures and their logs remain preserved; no audit was relaxed to obtain a pass. The collected current inventory is [test-inventory-v1.log](test-inventory-v1.log). The full JSON report records the command selections, per-file coverage and log hashes.

| Log | Result and scope |
| --- | --- |
| [test-integrated-v2.log](test-integrated-v2.log) | 83 passed before a healthcheck exception-class fixture mismatch; fixed and covered by subsequent focused runs. |
| [test-compatibility-v1.log](test-compatibility-v1.log) | 10 passed: original 969d source versus current policy, five prior arms, float32/bfloat16. |
| [test-remaining-v1.log](test-remaining-v1.log) | 28 passed, including all four worker arms and full synthetic detached-release DAG. |
| [test-health-v1.log](test-health-v1.log) | 33 passed before the newly added healthcheck import failed; package-compatible source imports fixed the actual issue. |
| [test-health-v2.log](test-health-v2.log) | 6 passed after the package import fix. |
| [test-reset-drain-v1.log](test-reset-drain-v1.log) | 6 passed: observer on/off, actual step exceptions, STOP and deadline draining. |
| [test-final-worker-v1.log](test-final-worker-v1.log) | 4 passed after final source changes: same-process audit and tampered receipt rejection for each arm. |
| [test-source-runtime-v1.log](test-source-runtime-v1.log) | 6 passed: reused exact Git/dependency/generated-runtime closure mechanics in inert CPU fixtures. |
| [test-probe-import-v1.log](test-probe-import-v1.log) | 37 passed: legacy direct-script imports and exact probe reuse checks, with mocked CPU process/device fixtures. |

All 25 changed Python files compiled without import/bytecode output, disabled configuration defaults were checked, and the staged diff passed whitespace checks. The original-source parity test covers C0, Q0, N31, N32 and N34 in float32 and bfloat16. Production tests use synthetic deployment leaves and fake processes; source/runtime closure mechanics are separately tested with inert registered-Git fixtures. They do not certify the installed GPU runtime.

Known limits and required follow-up:

- CPU implementation has not received independent implementation/native-audit/controller review. This executor does not issue a root acceptance or scientific PASS.
- Real installed dependency/controller/provider/runtime closure and the actual GPU audit backend were not exercised. Production tests explicitly mock deployment leaves and device calls; reused source/runtime mechanics were tested separately on inert fixtures. Root must materialize and verify the exact pinned source/runtime closure.
- No source adoption, runtime readiness mutation, live plan/manifests/release, owning accounting adoption, resource reservation or dispatch was performed. CPU authority is rejected as execution authority.
- The existing probe and queue received package-compatible import support while preserving CLI behavior. Their file hashes changed. Any retained CUDA/EGL proof must pass the existing exact probe-source check; if it does not, root needs separately authorized bounded preparation, new proof/runtime closure and a newly reviewed detached release. The N35 healthcheck wrapper never mutates frozen runtime readiness.
- No B_dev, native simulator episode, GPU worker, training, protected validation/formal evaluation or benchmark scoring ran. Zero decoded deltas are retained and are not evidence of novelty, grasp improvement or efficacy.

Exact next steps for root:

1. Root reviews commit c3730e5287fe659dffc95c40bf6d8b7ba95d1da9 on the preserved isolated branch, especially archive occurrence transport, independent lifecycle replay, actual Main acknowledgement hooks, and atomic admission/healthcheck paths. Do not treat this report as source adoption.
2. Obtain the required independent CPU implementation/native-audit/controller review using the existing authorized official session workflow; fix any review blocker in a separately reviewable source commit. No delegation was performed by this executor.
3. Only under separate root execution authority: adopt exact source, materialize pinned dependencies, verify installed controller semantics/provider identity, source/runtime closure and all 40 fresh manifests; reconcile the exact owning attempt, healthcheck and reservation prefixes against both cumulative caps and remaining protected reserves.
4. Revalidate exact source-bound CUDA/EGL proof. If preparation is needed, root must explicitly release bounded preparation; scripts.qd_ed_n35_healthcheck.run_healthcheck(plan_ref, release_ref, resource_id, timeout_seconds=120) is a prospective fixed-probe wrapper, not an automatic fallback. It reserves timeout+40 seconds and charges the separate health ledger, never an episode.
5. Freeze a new plan, exact budget authority, root production review and detached execution release, then validate the full public closure before any GPU work. The disabled prepare draft is insufficient.
6. Only after that release, the future runner may execute the 40-cell task-major C0/Q0/N34/N35 Dev prefix with no replay/retry. Stop on invalidity or complete-quadruple futility; STOP/deadline blocks new launches and drains the admitted worker. All40 valid necessary success gates still require mechanism and independent scientific review; validation/formal stay separately gated.

Changed files:

- `configs/config.yaml`
- `core/qd_closure_intent.py`
- `core/qd_ed.py`
- `core/rdt_policy_steer.py`
- `main.py`
- `scripts/qd_ed_available_gpu_queue.py`
- `scripts/qd_ed_gpu_probe.py`
- `scripts/qd_ed_n35_accounting.py`
- `scripts/qd_ed_n35_bridge.py`
- `scripts/qd_ed_n35_contract.py`
- `scripts/qd_ed_n35_healthcheck.py`
- `scripts/qd_ed_n35_lifecycle.py`
- `scripts/qd_ed_n35_native.py`
- `scripts/qd_ed_n35_prepare.py`
- `scripts/qd_ed_n35_release.py`
- `scripts/qd_ed_n35_report.py`
- `scripts/qd_ed_n35_runner.py`
- `scripts/qd_ed_n35_supervise.py`
- `scripts/qd_ed_n35_worker.py`
- `tests/test_n35_closure_intent.py`
- `tests/test_n35_closure_intent_integration.py`
- `tests/test_n35_compatibility.py`
- `tests/test_n35_controller.py`
- `tests/test_n35_futility_accounting.py`
- `tests/test_n35_production.py`
- `tests/test_n35_release_source.py`

There are no known unresolved CPU test failures or remaining code blockers identified by this executor; independent implementation review remains pending. No GPU worker, native simulator rollout, training, B_dev, protected evaluation, live release, source adoption, owning state/ledger write, external message, delegation or credential inspection was performed. Synthetic test journals are confined to CPU fixtures. Superpowers remained disabled.

`target_met=false`; `gpu_authorized=false`; `benchmark_score=null`. CPU work establishes no benchmark score or efficacy.
