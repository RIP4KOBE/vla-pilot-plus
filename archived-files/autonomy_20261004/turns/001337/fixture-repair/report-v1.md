# Node 15.6 bounded fixture repair

Completed test-only repair, committed `bee9f6a4703e9d5d802d6b8c7950b69beefac4c0` on exact clean parent `5da91e13a32211ac51ff0bb81d76aaefa0cc583f`. No merge or adoption.

Changed only:
- `tests/test_n36_audit_repair.py`
- `tests/test_n36_stop_guard.py`
- `tests/test_n36r2_draft.py`

Eight distinct reviewed cases now pass: seven in v3, then the remaining compiled-byte case in v4. No broad suite or scientific execution.

| Case | Retained runs | Final |
|---|---|---|
| test_stop_after_worker_entry_prevents_main_and_retains_receipt[0] | v3: passed | passed |
| test_stop_after_worker_entry_prevents_main_and_retains_receipt[1] | v3: passed | passed |
| test_stale_cache_repro_and_frozen_source_execution | v3: passed | passed |
| test_unsafe_entry_rejects_and_sourceless_rejects | v3: passed | passed |
| test_actual_runner_to_worker_entry_ignores_poisoned_dependencies | v3: passed | passed |
| test_compiled_bytes_join_rejects_changed_source_and_loader | v3: failed, v4: passed | passed |
| test_main_source_entry_preserves_script_semantics | v3: passed | passed |
| test_new_identity_cannot_release_or_admit | v3: passed | passed |

F1 uses the real immutable observation helper and asserts actual STOP rejection at both redirected locations. F2 copies the complete validator dependency chain and supplies synthetic bindings/inventories. F3 passes live child process/interpreter/context alias bindings through attestation and receipt verification. F4 accurately asserts malformed-input rejection. Production checks remain intact.

Containment review preceded test execution. Both STOP paths and all artifact writes are temporary. Inherited Landlock ABI 4 permits filesystem content writes only beneath this repair directory, with an existing `/dev/null` sink exception needed by dependency imports. Metadata limitations and reviewed write/subprocess paths are recorded in `containment-review.json` and its v3/v4 addenda. No canonical STOP write was attempted.

All failures are preserved: v1 startup failed on `/dev/null`; v2 collection failed on the same dependency requirement and exited -11; v3 retained one incomplete Torch inventory failure. v4 repaired only that inventory and passed. Commands, environment, XML results, logs, immutable STOP receipts, patch, and SHA-256 evidence manifest are retained here.

Production unchanged proof: all 3648 other tracked entries have identical mode/type/blob identities; checkout is clean after commit.

Remaining requirements include separate root adoption, actual runtime/source bindings, owning budget reconciliation, real authorized health and first-C0/G3 evidence, and the original validation/formal/ablation goals. Fixture success supplies none of those.

`gpu_authorized=false`, `release_enabled=false`, `source_adopted=false`, `target_met=false`, `score=null`.
