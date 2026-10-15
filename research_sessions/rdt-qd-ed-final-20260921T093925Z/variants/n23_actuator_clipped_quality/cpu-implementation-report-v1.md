# N23 CPU implementation report

Status: **CONDITIONAL_BACKEND_NOT_READY**. Scientific source commit `cebed8f17122395a31866ac739e4dace0221bc04` on `codex/rdt-qd-ed-n23-clipped-quality-20260930`, based on `60425750c41c8a46e1102e02e2e4e4d2f97fb242`. No GPU release is justified by this report. N22 and its owning source/runtime were not changed.

## Implemented scope

The N7-derived profile adds only `qd_quality_mode=actuator_clipped_provider_v1`. It clips each candidate's first eight translation commands componentwise to [-1,1] in a separate internal native 0.01 multiply/cumsum/add view, then uses only t1..t7 with weights [1,1,1,1,3,3,3]/13 and the original native norm/square and FP32 weight/storage behavior. Candidates without clipping in the scored first seven actions retain the already-computed raw tensor value byte-for-byte, including signed zero. The t8 value cannot trigger a quality change. No lift/hold, Q8 objective, descriptor, N5 eligibility, external provider/projector or deployed-action modification is included.

The opt-in contract snapshots the actual applicable controller's static bounds, shape/type, OSC_POSE fixed/delta semantics, controller method source paths/hashes, and process/adapter/wrapper/environment/controller/task/episode/reset identities. Source functions and static limits are read; no controller dynamics, object/contact/success state, stepping, resetting or rendering is requested. The passive reset-generation increment only activates after an N23 snapshot. Metadata/provider/reset drift fails closed. The Stage selected reward uses the original raw channel and the existing archive spread definition; archive/parent/terminal action-quality associations retain both raw and effective values.

The independent auditor reconstructs projection and quality without importing the N23 production helper, checks static metadata/native source links, and retains existing descriptor/selector/Stage/action audits. It shares the existing bounded provider-template recognizer solely for target0 source identity. The CPU runner profile expansion is closed to this exact N7 delta; no N23 plan admission, scheduler, budget or protected-set path was added.

## CPU verification and counters

- 205 unit/regression tests pass; 20 guided-loop/early-rejection tests pass, for **225 unique test cases**. This includes new N23 tests and old N20/N21/N22 and provider/feedback/auditor/metrics/runner regressions. The latest source-level auditor was also replayed over all six retained N23 native fixtures.
- Accepted FP32 and BF16 fixtures each independently verify **176 candidates / 11 canonical score batches**, with 160 clipped-prefix candidates and 10 changed-ranking batches. Both change the final selected candidate versus paired N7. N23 archive insertions/replacements are FP32 10/16 and BF16 11/13, showing active archive and ED search, not a final-only synthetic helper test.
- Both pairs use 176 external provider returns, 16 stub-model forwards / 256 model rows, 25 decoder calls and **347 population-projector invocations at identical existing caller sites**. The scored candidate domain is 176 in both. The unchanged archive diagnostic processes an outcome-dependent number of occupied cells: FP32 total adapter projection rows are N7 1949 versus N23 1948; BF16 1949 versus 1949. `cpu-call-count-clarification-v1.md` identifies the exact existing caller and preserves this exception to global row-count parity.
- Additional N23 quality overhead is timed in `qd_actuator_overhead_seconds` (CPU fixtures approximately 0.108s FP32 / 0.171s BF16). Its scope includes static snapshot/validation and internal tensor operations, not native evidence/origin-copy timing. Origin capture reuses the existing projection read, at 176 × 3 native source elements per guided chunk; canonical raw/action association clones are also retained. These and archive-dependent diagnostics belong in total episode wall cost. No GPU timing claim is made.

| Fixture | Verdict | Verified N23 batches before completion/rejection | Error |
|---|---|---:|---|
| valid_fp32 | accepted | 11 | none |
| valid_bf16 | accepted | 11 | none |
| unclipped_quality_fp32 | rejected as intended | 1 | n23_native_clipped_quality |
| unclipped_quality_bf16 | rejected as intended | 1 | n23_native_clipped_quality |
| wrong_bounds_fp32 | rejected as intended | 0 | n23_controller_bounds |
| wrong_bounds_bf16 | rejected as intended | 0 | n23_controller_bounds |

Fixtures use CPU model/controller stubs and AST-extracted installed static controller methods plus the unchanged production adapter projector. Controller methods are never executed and no robosuite/MuJoCo instance is constructed. They establish implementation plumbing and CPU arithmetic, not current live controller metadata, GPU equivalence, real-environment behavior or success rate.

## Actual-GPU evidence boundary: release blocker

Root explicitly authorized read-only reuse of the existing N17/N7 task0/task9 and N21 task0 exposed paths. `cpu-gpu-boundary-readonly-v1.py` verified all **6139 saved bundle hashes** and checked **407 canonical batches / 6512 candidates**, without a simulator, provider or GPU call. On recorded GPU-native BF16 projections, CPU seven-point raw-quality reconstruction differs from the saved raw aggregate in **12/2992, 2/704, 8/2816** candidates respectively; maximum absolute differences are **0.00048828125, 0.0001220703125, 0.00048828125**. CPU raw projection reconstruction differs for **2725/2992, 624/704, 2369/2816** paths, with maxima **3.90625, 1.953125, 3.90625 mm**. CUDA remains uninitialized.

These are preserved numerical mismatches, not toleranced successes or N23 outcomes. The strict current CPU auditor would reject genuine GPU-native evidence; a passing CPU fixture is insufficient. The execution-device helper's raw-projection equality also needs a future check of exact operation order/layout on the assigned backend. This report does not resolve whether reduction order, layout or other native backend details explain each mismatch. No unexplained tolerance, altered projector, FP64 production substitution, or relaxed old-mode gate was added. Root requested the prototype be frozen with this blocker before a separately reviewed, metered backend contract/preflight.

The previously bounded FP64 fixed-pool ranking screen is descriptive evidence only; it changed a saved choice on a successful path. N2/N3 historical failures caution that geometry-error or ranking improvements do not establish task success. This implementation deliberately leaves raw descriptors and eligibility unchanged. Historical controller bounds were not recorded and cannot be inferred retroactively; the new snapshot is prospective.

## Reproduction and provenance

Run from `implementation` with the vla-pilot Python. Do not reuse a pytest `--basetemp` path containing preserved artifacts, since pytest clears that directory.

```bash
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest tests/test_qd_actuator_clipped_quality.py tests/test_qd_executed_quality.py tests/test_qd_executed_feedback.py tests/test_qd_lift_quality.py tests/test_qd_hold_lift_quality.py tests/test_decision_evidence_audit.py tests/test_eds_eval_metrics.py tests/test_qd_ed_final_runner.py -q
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest tests/test_rdt_steer.py -k 'n23 or n22_hold_condition or n21_positive_lift or n20_exact_profile' -q --basetemp=../cpu-native-reproduction-new-directory
```

The compact machine report `cpu-implementation-report-v1.json` gives exact source/profile/protocol hashes, commands, audit counters, fixture paths and log hashes. Root-owned CPU protocol bytes remain unchanged, SHA256 `e38d4c6825cca743539282818e8b49168c1910cf688720bd1901b7405ab8cf67`; byte-identical protocol/declaration/reference copies are committed under `experiments/iteration_023_actuator_clipped_quality`.

Preserved failures: `cpu-unit-first-v1.log` (AST fixture metaclass setup), `cpu-native-first-v1.log` (fixture type annotations), `cpu-native-second-v1.log` (new-mode audit admission omitted), `cpu-native-third-v1.log` (overly broad global diagnostic-row equality assertion). Subsequent passing logs and complete rejection fixtures are retained separately. All artifacts stay under this N23 variant directory. The three historical evidence paths were read-only; no owning study, state, ledger, Arbor tree, budget or active experiment source was changed.
