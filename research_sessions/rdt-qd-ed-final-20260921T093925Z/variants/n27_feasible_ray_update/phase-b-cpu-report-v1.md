# N27 Phase B — CPU preparation complete, online release closed

Frozen commit **095cfeecd6af55477d2529441c307ab712e8a8da** on `codex/n27-feasible-ray-update`; preceding protocol commit6cd66a1, accepted helper commitbcec3e5. Score **Unknown**. No actual GPU/API/model/simulator, live state/ledger changes, old native proof execution or protected reads occurred.

The345-file source manifest binds315 original602 files plus30 added files. Exactly3 original files change: policy call-site/config/witness routing, runner closed N27 admission, worker N27 native receipt routing. The reverse patch restores all3 byte-for-byte;312 original files, original N25/N26 arithmetic/controllers and the accepted Phase A helper/tests/note remain unchanged. The separate CPU source bridge records byte checks; it is not a live source/proof release.

N27 assigns a per-particle FP32 feasible ray prefix at the two existing RBF sites. The unconstrained native operand, alpha, assigned output and measured difference have distinct evidence fields. Native audit independently reconstructs unchanged N26 geometry and the ray; no production feasible helper is called by the oracle. Scalar-only later calls are not presented as exact independent replay. Zero gradients remain legal. The fixed first-guided11 witnesses fit original numeric/metadata bounds. All four arms are profile-bound and controls retain their original auditors.

The prepared screen is16 primaries over tasks0..3×C0/Q0/N26/N27, maximum18 dispatches/2 exact sole-timeout recoveries, local9.25h including the separately charged120+40s tensor proof. Existing522/100 and bucket/protected reserves remain unchanged. Full16 native-valid, N27>=2, >=controls and strictly>N26 plus substantiveQD/ED allows only separately frozen full-Dev preparation; otherwise REJECT_SCREEN. Partial/invalid/status disagreement is INVALID_OR_INTERRUPTED. Current Codex CLI/chatgpt, gpt-6-astra/low/180s stays unchanged, with no Poe/fallback/credential edits.

## CPU evidence

There are **229 distinct focused cases with passing assertion evidence** across the following files; no Phase A or unrelated numerical suite was rerun. This is not a claim that every invocation was guard-clean.

| Test file | Distinct cases | Main evidence |
|---|---:|---|
| test_n27_integration.py |29|Actual expanded profile→resolver and exact argv; FP32/BF16×3 layouts×2 call sites, unchanged model/scheduler order and tail/mask; full search, instrumentation parity|
| test_n27_native.py |3|Full synthetic native loop,11 witnesses,176/11 fixed compute, marker/origin/context/operand/output/cost corruption; N26 delegation|
| test_n27_backend.py |93|36 tensor cases; strict proof/UUID/source/source-layout/negative checks, one-shot health charge/timeout/cleanup, all-arm same-process receipt;100h+protected boundaries|
| test_n27_controller.py |27|16-row matrix, no10-task futility, strict N26 superiority,18-cost/two-recovery caps, unknown usage and status-journal mismatch preservation|
| test_n27_recovery.py |55|Unchanged exact timeout classifier with synthetic inputs; source/receipt/qpos/missing/extra-failure/whole-worker rejection; zero-guided absence and real runner charge/cleanup|
| test_n27_source_gates.py |22|Five bounded historical metadata refs, wrong source/result/disposition/cleanup/oversize/symlink rejection; all315 reverse bytes; absent authority/proof, exact finite budget gates|

All seven invocation logs and guard JSONs are retained. Cumulative measured test invocation time **55.63361583009828s /300s**, CPU affinity2/threads2,8GiB AS, CUDA invisible and `torch.cuda.is_initialized()==False` in every run.

| Invocation | Assertions | Guard status | Seconds |
|---|---|---|---:|
| phase-b-science-v1 |50passed/17failed|627 denied optional bytecode/numba metadata probes, not clean|11.280092118|
| phase-b-science-v2 |29passed/2failed|0 denied; fixture failure retained|15.305004653|
| phase-b-controller-v1 |84passed|1 denied numba `/proc/cpuinfo`, not clean|5.402442393|
| phase-b-remaining-v1 |95passed|1 denied numba `/proc/cpuinfo`, not clean|9.453920111|
| phase-b-recovery-v1 |55passed|0 denied|6.311235852|
| phase-b-source-gates-v1 |12passed/1failed|0 denied; fixture failure retained|4.085166163|
| phase-b-gate-fix-v1 |11passed|0 denied|3.795754540|

Failure explanations, preserved rather than relabeled:

- First17 failures exposed a **new config-boundary implementation defect**: `_EDSConfig` does not contain the outer-profile `execution_horizon_mode/far` attributes. Those incorrect attribute checks were removed; outer frozen profile, existing actual clipped-RBF horizon8 gate and immutable helper16×8×3 remain strict. No numerical rule changed.
- First guard rejected importlib bytecode probes; subsequent guards use an owned empty pycache prefix with bytecode writes disabled. `/proc/cpuinfo` rejection was traced to installed numba's `_os_supports_avx`; root explicitly allowed this one read-only CPU dependency metadata path in v4. Earlier runs remain marked non-clean. No experiment data was read by any denial.
- The two second-run failures were a synthetic serializer fixture omission: the real main loop attaches metric global_step; the fixture now attaches24 before independent metric binding. Full independent native loop already supplied this field.
- Exact-command fixture initially invented an `auth_mode` argv flag. Existing CODEX_CONFIG_KEYS intentionally omits it. The corrected fixture verifies managed auth in frozen runtime and its rejection gate, actual backend/model/timeout args, and absence of credential/auth override flags. Provider code is unchanged.
- CPU autograd emitted an internal `cudaGetDeviceCount` warning in Torch's C++ engine under the8GiB AS bound; there was no initialized CUDA and this is **not native CUDA arithmetic evidence**. Python CUDA initialization was blocked by the later guard; future actual proof remains mandatory.
- Existing `core/fkd_class.py` emits its unchanged docstring SyntaxWarning. The two pre-test authoring errors (ignored experiments git-add and wrong source-anchor argument) are separately retained in phase-b-packaging-failures-v1.txt; neither executed scientific code.

Reproducible bounded command pattern, from implementation:

```
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python ../phase-b-cpu-guard-v5.py NEW_LABEL <exact pytest selection>
```

Every guard JSON records its exact selectors. Distinct selection inventory and all failures are in phase-b-test-results-v1.json. Do not rerun passed matrices simply to increase counts; eventual changes need only their affected checks.

## Handoff and limits

See `implementation/docs/n27-phase-b-controller-contract.md` for exact activation order and schemas. Eight disabled authority/review/release templates plus a concrete16-row `plan.draft.disabled-v1.json` are external artifacts, all unadopted and with unresolved hashes. They cannot pass live release gates. Root must integrate/review exact source, verify actual runtime/provider/resource/accounting, build the focused bridge, adopt finite reuse and one-shot proof authority, run the sole native proof, then bind final source review/Dev authority/frozen plan/release. No old proof is rerun and no new budget is adopted here. Full native support, actual duration, empirical benefit and task success remain Unknown.
