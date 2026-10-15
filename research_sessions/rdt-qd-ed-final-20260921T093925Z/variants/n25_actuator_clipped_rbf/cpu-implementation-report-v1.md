# N25 conditional CPU preparation completed

**Result: CPU correctness/preparation only; task score Unknown/not run.** No registration, controller, budget adoption or online release. N24 remains the separately owned experiment, and its validation has priority if it promotes.

Branch `codex/n25-actuator-clipped-rbf`, exact commit `2a7e764107ea530928b31cd15c50ef8095ea71b8`, based on `3b7afa02757eb3519d95547e4b6e6e939f7068f2`; pre-implementation protocol commit `bd96a23`. Worktree `implementation/` is clean. The frozen protocol and bounded-witness CPU authority are copied byte-for-byte into tracked docs. All artifacts stay in this N25 variant.

## Implementation and novelty

One new opt-in mode, `actuator_clipped_eef_v1`, changes the existing initial and rollout RBF geometry. The temporary RBF input clips only first8 xyz39/40/41, using derivative1 strictly inside(-1,1) and0 at±1/outside. It retains original per-candidate projector calls, native dtype/origin/cumsum0.01 and the exact inverse-distance potential/normalization/sign/scales/schedules. It does not change the shared projector, score, quality, QD descriptor/archive/selector, decoder or Stage. N23 is the scientific parent, and N24 rescue remains OFF. Default and direction-normalized modes retain their original branches.

All-zero gradient is a valid mechanism result. Nonfinite inputs/outputs, unavailable gradients or missing adapter fail closed with no new-mode IID/raw fallback. Global normalization can concentrate force into fewer coordinates; the implementation does not promise lower force, less saturation or task benefit.

The only modified original file is `core/rdt_policy_steer.py`; new scientific helper is `core/qd_actuator_clipped_rbf.py`, with `configs/qd_ed_final/candidate_n25.json` and focused tests. Source bridge verifies229/230 original files byte identical and114/122 RDT class methods byte identical. Original absolute gradient, projector, masks, decoder and score methods are among unchanged methods. All baseline/C0/Q0/N23 profiles, main, adapters, provider/Stage transport, old native auditors, runner/controller remain byte identical. New profile changes exactly the two descriptor fields relative to N23.

## Evidence and tests

All four logs are preserved: `cpu-focused-v1.log`24PASS/6.46s; `cpu-focused-v2.log`27PASS/9.48s after witness implementation; `cpu-regression-v1.log`22PASS/5.43s; `cpu-closure-v1.log`6PASS/6.07s covering the three added fault tests and affected witness paths. Final coverage is30 distinct new tests plus22 selected old-mode tests; repeated executions are not counted as independent evidence. There were no failed pytest runs. Existing `fkd_class.py` invalid-escape SyntaxWarnings remain visible and were not altered.

Tests establish FP32/BF16 strict-interior bitwise equality to the original RBF, native forward clamp, declared exact-boundary derivatives, saturated/coincident zero gradients, shape/dtype/horizon/index binding, nontranslation zero updates, original sign/schedules and RNG/call accounting, profile/default compatibility, fail-closed nonfinite/model-output/missing-gradient behavior, real EDS metrics JSON serialization, and two full synthetic16×10 loops with176 canonical evaluations/11score batches/10resample+renoise+rollout. Stub neural/provider functions are synthetic CPU fixtures, not real model/API calls. No performance comparison was run.

The actual `DecisionEvidence` serializer was exercised with bounded synthetic tensors, including first-guided selection, missing slots/no backfill, episode reset, call/episode/metadata caps, before/after original +=, and byte-preserving CPU roundtrip. Recording on/off yields exactly equal selected actions, RNG, compute counters and origin acquisition counts. No tensors leak into JSON metrics. Exact CUDA arithmetic is Unknown.

The Python audit guard is installed before Torch/pytest import; it denies non-owned research inputs, credentials, actual data/artifact trees, non-owned writes, subprocess/network dispatch and CUDA initialization. It is a Python audit/explicit CUDA boundary, not an OS sandbox. Every log reports blocked_count0, CUDA uninitialized, intra/inter-op2. No actual attempt/protected payload, credential, online API, real model, simulator or GPU was accessed; no state/ledger/tree/active source was changed.

Reproduce the30-test focused suite with a fresh output basename, from `implementation/`:

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python -c 'import runpy,sys; runpy.run_path(sys.argv[1]); import pytest; raise SystemExit(pytest.main(sys.argv[2:]))' ../n25_cpu_guard_v1.py -q -p no:cacheprovider tests/test_n25_clipped_rbf.py --basetemp=../fixtures-reproduce
```

The regression log records22 passes from old default/profile incompatibility, original RBF application, legacy fallback, baseline rollout, fixed override/schedule and translation-mask checks. No broad historical/real-data suite was run.

## Telemetry and integration limits

All new-mode calls emit phase/iteration/timestep, shape/dtype/stride, clipping/boundary counts, gradient summaries and scaled update-operand summaries, attached to the enclosing decision/global_step/Stage. Rounded scalar summaries are not exact CUDA proof. `update_operand` is explicitly not measured output delta.

Optional witness was implemented only after root CPU authority4e2f6ea9. It samples no more than11 fixed calls in the first guided decision and records translation-only native tensors, same-call origins and actual model-output slices before/after the existing +=. Caps20KiB numeric/call,220KiB/episode,16KiB identity metadata/call are enforced. No full latent, second gradient/projector/origin fetch or outcome-dependent selection is used. Identity currently references the enclosing decision event plus the future metered source/runtime receipt, without new identity probes. A later source/worker audit must establish those complete bindings; this phase is not that admission proof.

Before any real N25 experiment, root still needs the completed N24 disposition, prospective online protocol/capacity, exact native N25 arithmetic/evidence audit, profile-bound anti-downgrade gates, source/runtime/worker proof bridge and closed controller admission. No runner integration or GPU preflight was prepared. No calibration threshold or minimum activity veto was introduced. CPU evidence does not establish actual noisy-domain activity or physical task utility.

## Executor record

`score: null`; `result: conditional CPU implementation and focused tests passed; online experiment not run`; `insight: clipping changes proposal geometry while preserving fixed search calls, but can legitimately collapse gradients or concentrate normalized force`; `code_ref: codex/n25-actuator-clipped-rbf@2a7e764107ea530928b31cd15c50ef8095ea71b8`.
