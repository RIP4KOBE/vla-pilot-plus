# N32 production adapter — bounded CPU delivery

**Implemented and committed for root review; no release, adoption or GPU execution.**

Commit `34c6f219af1829b2d929850a652af6607ed6b258`; parent `1e50517b32b63ef9c6ad58cf56e522a436be01b8`. The isolated implementation worktree is clean. Seven source files changed (three modifications, four additions);538 source files are byte-for-byte invariant against the parent. The545-file committed inventory and exact changed/invariant SHA256 values are recorded in [result-v1.json](result-v1.json) and [committed-verification-v1.json](committed-verification-v1.json).

## Delivered

- Detached root release validation with an acyclic inputs→plan→review→release→context chain. Required real protocol/approval/authority/source/runtime objects are externally hash-bound. The original disabled draft is byte-for-byte unchanged; no real authority/review/release object was created.
- Prospective production runner under only normal runner/state locks: preserve original ledger prefixes; recompute generic accounting; reconcile valid/live/unknown/unsettled/orphan handles; reserve→dispatch→terminal; never replay a valid cell. Exact task-major C0/Q0/N32 identities, all30 manifests, actual committed source and generic checkpoint/task/cache/init/BDDL gates precede dispatch.
- One deterministic identity contract: attempt ID equals episode key. Null non-retry fields are accepted; all non-null retry/recovery values are rejected. Context/output/process/receipt/terminal bindings are tested. The parent records PID/boot/start before opening the child gate; the child verifies that record before Main.
- Original generic and native audits remain in the bounded worker. Parent verification retains generic identity, outcome, cost, Stage/provider and video checks. Missing/malformed audit or terminal evidence stops INVALID with retained charges; it cannot become valid task failure or success. Existing terminal artifacts must agree with the journal on resume.
- Generic historical episode/health accounting, reservation and integer admission functions are reused, including weekly effective ceiling and private/global/bucket/protected/full1840s/cohort5GPUh checks. All95 other generic definitions remain unchanged; modified generic definitions are the runtime/budget helper extractions and an optional bounded monitor callback. All N31 scientific source, controls, Main and core policy files are invariant.
- STOP/deadline/coordinator checks precede dispatch and never signal an existing episode. Monitoring errors remain INVALID even after exit0. Monitor queries share the1800s deadline; exact owned-child timeout cleanup is bounded10s TERM+30s KILL, with charge retained. No process group, foreign PID or restored handle is signalled.

Production entrypoint/schema documentation is committed at `docs/experiments/n32_production_adapter.md`. The standalone runner requires externally supplied plan/release paths and digests; it cannot generate or adopt them.

## Validation

Final N32 command exited0: **143 passed**,6 inherited SyntaxWarnings,46.22s.

```sh
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 timeout 1200 bash -c 'ulimit -t 1200; exec python -m pytest -q tests/test_n32_release.py tests/test_n32_release_worker.py tests/test_n32_production.py' > ../production-adapter-v1/test-logs/n32-final-03.log 2>&1
```

Focused shared-runner/N31 regression command exited0: **37 passed**,59 deselected,2.19s.

```sh
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 timeout 1200 bash -c 'ulimit -t 1200; exec python -m pytest -q tests/test_qd_ed_final_runner.py tests/test_n31_admission.py tests/test_n31_controller.py -k "budget or frozen_plan_binds or model_mutation or exclusivity or monitor or admission"' > ../production-adapter-v1/test-logs/shared-regression-final.log 2>&1
```

The180 final tests cover retained scientific/config/native-receipt behavior, lifecycle/identity/replay/invalid-stop/STOP cases, all release links, bound cleanup and monitor queries, historical/health/unknown/reserved/inflight accounting, cap boundaries and generic/N31 input/admission regression. Tests use temporary fixtures only. Release-schema dependency gates are spied in the DAG fixtures and checked separately by retained source tests, actual committed-source verification and selected generic input-file tests; this is not a real-root production execution.

One early test failed because this Python build lacks `os.pidfd_open`. The final implementation uses a single explicit direct-child Popen contract with PID/boot/start and parent verification. A real new CPU sleeping child verifies cleanup and identity-mismatch refusal. No foreign process was touched. Every test command, exit and log SHA256, including that resolved failure, is recorded in [result-v1.json](result-v1.json).

Committed verification exited0:545 source files checked against Git,7 changes,538 invariants,95 unchanged generic definition ASTs, original disabled draft unchanged, clean worktree. Final diff whitespace check passed.

## Remaining root prerequisites and limits

1. Root review of this commit, then explicit adoption/freeze of the actual execution checkout; no owning source was adopted here.
2. Real approved protocol, approval basis, finite budget authority, plan, detached root review and execution release, supplied with external hashes. No real release/approval object was generated.
3. Root-bound actual runtime/checkpoint/seed/init-row/BDDL/task-cache inventory and all30 external manifests recomposed for the finally adopted committed checkout; no trace-derived expectations.
4. Actual adopted private state n32_budget_authority and matching caps/amendment, immutable historical ledger prefixes, and fresh journal-derived accounting under normal runner/state locks.
5. Existing hash-bound accounted CUDA/EGL proof plus idle GPU7 UUID admission and current-login official Codex provider gates before each launch; no new probe or provider call from this CPU task.
6. Real GPU/device behavior, provider usage and worst-case720-step same-worker audit latency remain unmeasured. The first root-authorized attempt must retain the1800s plus40s cleanup cap and invalid-stop rules.
7. Root must settle interrupted/unknown or unkillable live attempts and missing duration telemetry; this adapter blocks further dispatch, never fabricates zero charge, restores a PID handle or automatically recovers.

No owning code/state/tree/ledger, driver or lease was changed. No GPU/probe, model/checkpoint load, simulation, protected validation/formal result read, provider/API/credential access, alternate account/provider, dependency installation, cloud or additional agent was used. Accounting tests charge only synthetic fixtures; actual owning balances were not recomputed or amended here.

Only complete valid triples permit numeric futility; all30 valid cells, N32>=5/10 and matched controls remain necessary for prospective promotion consideration. Unrun cells, score/efficacy and HTTP counters remain Unknown. Validation/formal/ablations and all automatic recoveries remain closed.
