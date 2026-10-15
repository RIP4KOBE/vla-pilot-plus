# N36 CPU audit repair report

Committed `ab8e8c6f8fdfb66c3a82b0135c0441cf542a9557` from `e7cdf2c09a60ffb1d248f073c5639303b2ef01fa` in the isolated worktree. Worktree is clean.

**Status:** repaired with targeted CPU evidence; independent repair review required. This is not a comprehensive source/runtime/native PASS. `score=null`, `promotion=false`, `target_met=false`. No adoption or release.

## Repairs

- **SR-01:** source-only startup/import for runner, worker, Main and dependencies; compiled input digests join frozen source/runtime inventories. Existing module paths, generated-code rules and native-build attestation remain required. Explicit interpreter/native/Torch namespace exceptions are documented.
- **SR-02:** ordered descriptor projection events join exact raw origin bytes, native casts/actions/projections, decision/iteration/candidate identities and cached physical observations. Frozen arithmetic and scientific policy are unchanged.

## CPU checks

Measured aggregate test CPU: **91.033s / 900s** (including subprocess children); conservative static allowance: 10s. Two-thread environment, CUDA disabled. Wall since authority: 1000.4s / 3600s.

| Run | Outcome | CPU seconds | Wall seconds |
|---|---|---:|---:|
| 01 | 23 failed in 1.37s | 2.266 | 2.218 |
| 02 | 23 passed in 2.71s | 3.930 | 3.521 |
| 03 | 2 passed, 23 deselected in 9.33s | 10.350 | 10.083 |
| 04 | 32 passed in 14.73s | 15.824 | 15.641 |
| 05 | 1 failed, 2 passed, 27 deselected in 7.08s | 7.944 | 7.779 |
| 06 | 1 passed, 29 deselected in 9.69s | 10.648 | 10.383 |
| 07 | 5 passed, 25 deselected in 9.85s | 10.871 | 10.582 |
| 08 | 5 passed, 25 deselected in 10.01s | 10.965 | 10.684 |
| 09 | 1 failed in 6.75s | 7.592 | 7.427 |
| 10 | 1 passed in 9.68s | 10.644 | 10.382 |

Every command, environment, timing and failure is preserved in `test-NN.json` / `test-NN.log`. Initial failures and fixes are detailed in the JSON report; no failure was discarded. The combined regression run passed32 checks; final source-only checks passed5, and the extended poisoned-policy/actual runner-worker check passed subsequently.

The startup tests use isolated copied source with the unrelated core environment initializer suppressed and synthetic inventories. The policy decoder executes from source-loader compiled code without constructing a policy/model. Descriptor tests use real recorder/helpers/auditor plus unchanged AST-extracted methods. No live worker body, model/provider/simulator call or historical tensor replay was run.

## Remaining obligations

- The independent source review was partial. This repair is not a comprehensive PASS of N36 source, dynamic code, release/accounting or runtime behavior. Root must independently review this commit, including bootstrap trust assumptions and explicit exceptions, before adoption.
- Actual pinned RDT/LeRobot dependencies, all40 source/runtime/config/checkpoint/cache/provider/task/init/controller closures and external native-build inventory remain unmaterialized/unattested here. Future consumers must use the source-only entry and rebuilt frozen inventories; old receipts are not sufficient.
- Runtime startup without .pth/sitecustomize and complete imported/transient-source coverage must be validated in the actual pinned interpreter. Missing dependencies or unreviewed loaders fail closed; no fallback or audit weakening is authorized.
- Source-only import is not a sandbox against arbitrary malicious native code or arbitrary later monkeypatching. Existing reviewed dynamic provider/controller/generated-code obligations remain separate. Pre-script encoding modules are explicit filesystem-source exceptions under the impossible cache prefix; builtin/frozen code relies on the externally verified interpreter.
- No actual CUDA device, mapped deployed native build/kernel arithmetic, controller instance, simulator, provider, model or benchmark was exercised. Exact same-device arithmetic and complete prospective whole-episode evidence remain mandatory.
- Exact equality of descriptor controller-pose origins and cached physical observations must hold prospectively; mismatch or missing required provenance invalidates, without tolerance widening or scientific-policy changes. First boundary lacks a preceding physical execution record.
- Older-control regression here is projection/event/pose-read parity; full policy/RNG/model/scoring parity was not rerun because model/provider calls were excluded. Prior implementation evidence is referenced, not reasserted as new execution.
- Actual startup/source-hashing/telemetry/storage/audit overhead and frozen worker/cohort feasibility are unmeasured. Complete Dev outcomes, detour final survival, physical response/entry and scientific efficacy remain Unknown; protected validation/formal/ablations remain unopened and unreleased.

## Final source hashes

| File | SHA-256 |
|---|---|
| `core/env_adapters/libero_adapter.py` | `17fb74b3d475c91bc015222d4b61989c82a57f83935581b54935bab8080be26d` |
| `core/rdt_policy_steer.py` | `73387f980404b37997ac850619ff45770fae829ad079c62e8040e66887d2ef7d` |
| `docs/n36-cpu-audit-repair.md` | `cd27240c2ca9669509b4f1206a4255eb943bb2e1d1cf55ebbd3d4029d7551538` |
| `scripts/qd_ed_n36_arithmetic.py` | `af69bbf02ebddb95458ec9f70719221d29bec36fa88e1cda6f20848dd20de6ef` |
| `scripts/qd_ed_n36_bootstrap.py` | `84c569b975a21a5d075245e28b827acc7e23c8e10c00f31a3eba0febe0743cc4` |
| `scripts/qd_ed_n36_native.py` | `df3b354712901a382e3126ac3dac510c000dda99916ddd7388fcdcfbc8983536` |
| `scripts/qd_ed_n36_runner.py` | `2c4838375956c3010280dde22b272f34798a199d573f2bf7fd07fee8262f99a2` |
| `scripts/qd_ed_n36_source.py` | `a28f09cb8f899bf0001684f6edcb3b3e52a2ec75d632ba5a5f01b7acd417c771` |
| `scripts/qd_ed_n36_worker.py` | `7bdf32a721c00be9f21659ec42db458dbb4d60569ef7acccde3641c7aca37cf6` |
| `tests/test_n36_audit_repair.py` | `8a8874f39496bf2465401536a541fb35c4750f7332f7afb4bf2b2258a49acd26` |
| `tests/test_n36_runner.py` | `0e52130c7689784af3de3bb67abd6a70566821d1fcb21cf996dfe98a9d87bbca` |

The authority and all named direct document digests were verified, as were original reviewer reproduction artifacts and29 candidate Git blob hashes. The full protocol is interpreted together with the root review accepting its ten-update/comparator decisions. Authority self-hash was recorded locally; no external self-digest was supplied. Owning ledgers were not reconciled or modified.

Stopped after reporting. Independent repair review must precede source adoption, actual runtime/native validation or prospective release.
