# N36 CPU implementation report

Commit: `e7cdf2c09a60ffb1d248f073c5639303b2ef01fa` (parent `52a87af0bf11f95b21ce17aba456dc98944d9774`).

Status: implemented and targeted CPU tested; independent root review pending. **Score: null. No promotion, source adoption, runtime release, GPU execution or task-success claim.**

## Implementation

- **authority:** Clean isolated worktree at exact base verified; direct root review/protocol/user authority/accounting hashes verified. Root review overrides draft proposed flags. Owning ledgers were not read or mutated.
- **independent memory:** Distinct N36 object; all composed arms disable N35. Exact winner occurrence and all equal-byte aliases, native decode, commit, eight ordered nonterminal acknowledgements, full episode/stage/provider/target/tracker/task/run/source continuity and adjacent step/decision identity.
- **arithmetic:** Committed fp32 values promoted to binary64; explicit j-order translation sums and xyz-order dot<=0 without epsilon; zero/nonfinite data fail closed. Consumption at boundary entry, ten-update frozen latch, expiry and protocol resets.
- **proposal:** Current observed quaternion/jaw geometry; unchanged N34 close priority and inactive fallback; deterministic minimum-absolute-component axis with xyz ties, right-handed tangent, half-prefix clipping, one native cast, native decoded sums/proxy endpoint. Other15, remainder, signed-zero bytes and 176/11 canonical contract preserved.
- **native evidence:** Actual initial/all10 candidates, ordinary population, scoring projection/provider inputs/results, source origins, actual archive projection/descriptor/bounds/cells, visits/parents, occurrence winners, decode/commit/ack and raw physical response are recorded and linked.
- **independent audit:** Separate lifecycle/path reference code; native arithmetic recomputed on explicit device; archive/tie/visit/seeded-parent replay and physical-response joins. Mandatory generic audit remains. 25 corruption/missing cases return INVALID_STOP and no next row rather than accepting producer PASS flags.
- **build:** Externally hash-bound native-build manifest; actual mapped Torch/CUDA/driver libraries checked before Main and after audit. Synthetic file/maps negatives reject changed/missing/unbound/deleted binaries. No actual CUDA build attestation performed.
- **controller:** Fresh exact 40-row task-major C0/Q0/N34/N36 matrix, disabled drafts, detached root review/release, source/runtime/config/build closures, zero retries, complete-quadruple futility, preserved costs/protected reserves/STOP/drain. Healthcheck <=60 seconds plus cleanup, <=41 invocations and aggregate1800 seconds, full1840-second episode deadline guard.
- **controls:** Six fp32/bf16 C0/Q0/N34 parity checks against base source pass: exact selected/canonical bytes, RNG state, compute counters and origin-query counts. Actual Main hooks and exceptions tested with synthetic services.
- **native scope:** CPU fixtures are not native GPU attestation, live simulation, task success or performance evidence. Production receipt consumer explicitly rejects CPU arithmetic as CUDA attestation.

## Tests and preserved failures

All runs used `CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1`; artifacts and exact commands are recorded in report-v1.json. Tests ran serially with controlled CPU services.

| Run | Result | Log |
| --- | --- | --- |
| 01 | 2 failed, 2 warnings in 11.30s | [log](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001152/implementation/test-01.log) |
| 02 | 2 failed, 2 warnings in 5.87s | [log](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001152/implementation/test-02.log) |
| 03 | 2 failed, 2 warnings in 11.17s | [log](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001152/implementation/test-03.log) |
| 04 | 2 failed, 96 passed, 2 warnings in 13.61s | [log](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001152/implementation/test-04.log) |
| 05 | 117 passed, 16 warnings in 56.97s | [log](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001152/implementation/test-05.log) |
| 06 | 2 failed, 22 passed, 12 warnings in 13.61s | [log](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001152/implementation/test-06.log) |
| 07 | 44 passed, 3 warnings in 8.09s | [log](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001152/implementation/test-07.log) |
| 08 | 7 failed, 16 passed, 11 warnings in 33.10s | [log](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001152/implementation/test-08.log) |
| 09 | 8 passed, 8 warnings in 2.85s | [log](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001152/implementation/test-09.log) |
| 10 | 29 passed, 14 warnings in 51.25s | [log](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001152/implementation/test-10.log) |

Successful targeted groups cover the final affected paths; broad suites were not repeated. Final static AST and staged whitespace checks pass. No mandatory audit was removed or weakened to obtain passing tests.

- Two trigger assertions failed because the .01 synthetic fixture naturally selected an ordinary occurrence. Use a synthetic .08 geometry whose direct proposal wins ordinary scoring to exercise the active path. Production algorithm and selection were not modified or forced.
- Two NameErrors: tangent proposal called _same_native_bytes although the helper was imported as same. Use the existing same alias. Active tangent path then executed.
- Two audit errors: floating-only native_id helper applied to int64 cell IDs. Require int64 dtype and exact torch.equal for cell IDs/visits; retain native byte comparisons for floating tensors.
- Two fixture assertions demanded ten changed detours; actual later templates legitimately produced no_native_change. Assert immutable eligibility across ten updates and exact detour or no-native-change semantics; independent whole-episode audit remained mandatory.
- Two synthetic ten-template fixtures assigned unequal rewards to identical plans; the existing canonical alias consistency check correctly rejected them. Give synthetic rows distinct untouched remainder bytes. Ten actual best-template changes then pass; no alias audit weakened.
- Seven negative config tests tried mutating frozen _EDSConfig and failed before reaching validation. Use dataclasses.replace to create invalid configs. All eight final config/horizon negatives pass in iteration9.
- An edit script asserted an absent exact child-descriptor call string before writing files. Inspected the existing projection_out call and applied the targeted hook without changing unrelated branches.
- A timing-summary probe read test10.time before the test exited and raised AttributeError on a missing regex match. Waited for completion and parsed all final time files. No source/test evidence changed.
- Staged whitespace check found a trailing blank line in test_n36_composition.py. Removed the extra blank line; final staged diff check passed.

## Resource accounting

Measured CPU time for runs02–10: 269.09s. Run01 reported11.30s pytest wall time without process CPU timing; a conservative120s CPU charge gives 389.09s against the1800s budget. Wall time since authority issuance at report generation: 1654.7s against3600s. CUDA was disabled. No simulator, live healthcheck, provider probe or historical tensor replay ran.

## Remaining runtime obligations

- Independent root review of this source commit, protocol fidelity, audit completeness and controller implementation before adoption.
- Root must review the explicit same-device native arithmetic auditor choice: generic/lifecycle checks remain CPU; native projection/provider/descriptor/cell recomputation runs on assigned cuda:0 only inside a separately released metered worker. No external provider/model/simulator calls are added by the auditor.
- Materialize exact pinned RDT/LeRobot source in the adopted checkout and verify full source closure; isolated directories remain unmaterialized. No shared submodule edits or patch required.
- Compose fresh actual all40 manifests, runtime/source/module/checkpoint/cache/provider/task/init bindings, controller semantics and external native-build inventory. Synthetic test manifests/receipts are not usable releases.
- Reconcile current owning resource ledgers, wall window and protected reserves; adopt any prospective accounting/window and issue detached root execution release. No healthcheck, reservation, budget adoption or release occurred here.
- Obtain whole-episode actual CUDA/build/native-kernel, candidate/competition/final occurrence/decode/commit/ack/physical-response evidence on future authorized runs. Exact arithmetic mismatch must invalidate rather than introduce tolerances or suppress mandatory audits.
- Measure actual audit/source-hashing/storage/worker overhead within frozen1800s+40s and21h cohort limits. CPU fixtures do not prove operational feasibility or guarantee40 completion.
- Fresh matched task outcomes, detour final survival/execution, physical box entry and scientific efficacy remain Unknown. No protected validation/formal access, promotion or original-goal completion.

## Committed file hashes

| File | SHA-256 |
| --- | --- |
| `configs/config.yaml` | `15084693bfbfd5a07956fe8aa9af543d1023a319119c9da995b5817714cad355` |
| `core/qd_nonprogress_tangent.py` | `39a5ce066485208c2da46e46b88014c3a54c87e13a73279b1bf858ec02c2bf71` |
| `core/rdt_policy_steer.py` | `b511d28f427760329ab5101465764026b3d9e4fcb9c1e64d7f8bea2addd78844` |
| `docs/n36-cpu-implementation.md` | `175d310fd567b2982961e9acce97d69c1d642bac8860657b6785d42a745d70e8` |
| `main.py` | `b8ca130703d2c15e698ffbbe0a8ff2b0c612bc0bfaebbb968c3ae8cd3fd26e99` |
| `scripts/qd_ed_n36_accounting.py` | `eb432948208425f4db215340fb554a809fad0426a41960b05dee9bf45be39af3` |
| `scripts/qd_ed_n36_arithmetic.py` | `e5fd7725781a854398e66c2933f1d2ff1745e5a5e611d58be73df5774f2301b0` |
| `scripts/qd_ed_n36_bridge.py` | `4dc364935c51f958e30882cfcdcb5f5c8c27deb03596caa20b39c443a7388488` |
| `scripts/qd_ed_n36_build.py` | `ef9f575fb2d3f7f374adcf19397e4a005bb4e9877acae7a3c93684bbef3c44bd` |
| `scripts/qd_ed_n36_contract.py` | `7bd0b036414a81cac2ca3382922aaedefcabe3cdfca1d4fb5e7ea3e699ebe288` |
| `scripts/qd_ed_n36_healthcheck.py` | `cbc99d2c36bbf11886a1cb515e33c3319cc58fe31f957584a8d80e0eb65f66e3` |
| `scripts/qd_ed_n36_lifecycle.py` | `23aa7a2a302045a73e45b25b7dbf34fdf46c9ada83aeb0c8001b66870939a1f0` |
| `scripts/qd_ed_n36_native.py` | `0b38c7d3a3a060f639f8243bec343f1b730794b29957a2ff92059a15fed3320b` |
| `scripts/qd_ed_n36_prepare.py` | `9781096c6c91c6dd43157644600a85809553958c9aa7d0059b59aea34d429d3e` |
| `scripts/qd_ed_n36_reference.py` | `5659b925022a85b40346d7435feea22ef7321a952f602bb75f1c716930c44be5` |
| `scripts/qd_ed_n36_release.py` | `c9445e234aa8c57c82d4a3771f6c16c67593331b97d169efdd66b2b649f42da2` |
| `scripts/qd_ed_n36_report.py` | `6b2b6d58810623b2144d2bc0e2df00944341f82a3c5e0f8e4fe4a12aaf0e6fab` |
| `scripts/qd_ed_n36_response.py` | `20f7769d780d4df29a7207386db7461df94e9009f9856561f3a83bd85c93b803` |
| `scripts/qd_ed_n36_runner.py` | `9270fc2679a51165b29e671117ced1cc1ed124a6559b2dd1ab1c03d8b284c69f` |
| `scripts/qd_ed_n36_supervise.py` | `5c6e8008561e00919a14eb2e045d664cd8a4d517a96d0aac86eeef0d17f07380` |
| `scripts/qd_ed_n36_worker.py` | `9a58ee0c17a02d544cfaae84d952d813f9f7862ac44de66d2a785d3cdfdacfbb` |
| `tests/test_n36_boundaries.py` | `31629e2f97a6c0b778d4f0ed700616f2ee93554b7d31a7da8710707594d9e5e6` |
| `tests/test_n36_build.py` | `c9c34841d71703e41d14b0a9a87be524889b3bef41511e2e2a5a58c656fceb93` |
| `tests/test_n36_compatibility.py` | `88c3a44445c15e9bd4ed3eb7964c856a2ba695f4128f20a23219bb280af6ac40` |
| `tests/test_n36_composition.py` | `f85c64f0cc54d0b36f1c3e5ab885a9df82f2db7a17f44f6c85de7585a1688f9e` |
| `tests/test_n36_controller.py` | `139c5ce40a83473d6d4cffdfd1abcb38c47626c4d085346ebe324892e96c663e` |
| `tests/test_n36_integration.py` | `c2335e04c76026ccb830ddc39955c704f538d65ba3bfb624fff04e3efbda5193` |
| `tests/test_n36_release.py` | `1989b303753965434615bf39c0f30f1a4be2d17c41d55b04b86f78bb3ce5c102` |
| `tests/test_n36_runner.py` | `3a7d08e3a4da43c120bc834cb8a7f86cb6ab76d5b91e2a475daecaabde9f82b9` |

RDT and LeRobot pins and source/runtime preparation requirements are documented in `docs/n36-cpu-implementation.md`. No submodule checkout was changed. Owning research state, ledgers, tree/checkpoint and other studies remain untouched. The worktree is clean.
