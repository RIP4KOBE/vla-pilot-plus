# N26 conditional CPU delivery

Status: **CPU preparation complete; online score Unknown; GPU/controller release closed.**

Final source commit: `8fd01eb77e2e83a100e54b21dc955c34bda9a3cc`, branch `codex/n26-clean-output-rbf`.
Base: `5a65ef15968cc68c82314e8c0773b3365ad45fa0`. Protocol was committed first as `1f1c824`.
The owning N25 worktree, active experiment and inactive N25 validation worktree were not changed.

## Implemented scientific delta

The profile adds exactly one option, `diversity_input_source=model_output_sample_v1`.
The absent/default value remains `noisy_sample`. Both existing initial and rollout callsites pass the same already-computed, unmodified model output object to N25's shared clipped geometry function. No tensor cast, layout conversion, extra forward, model backward, new RNG or projector call is introduced. N25's detached geometry leaf and original negative masked scale20 update remain in place.

The actual scheduler/config is checked for `prediction_type=sample` before the first forward and again at each active RBF call. Missing/epsilon/v-prediction is rejected for N26, while the old default has no new scheduler requirement. N26 rejects incompatible RBF modes and population-cache options. All original grid/archive/quality/selector checks remain.

The profile inherits N25's clipped quality, N7 descriptor, N5 selector and rescue OFF. No reward, Stage, provider, decoder, physical controller, model, QD replacement, scheduler or selection rule changed. No provider call occurred; future transport remains current-account Codex only, without Poe or fallback.

## Evidence and compatibility

N26 all-call summaries and bounded witnesses have distinct schema/source/event names and explicit clean-input/sample/no-model-Jacobian fields. The witness compares input_xyz to model_output_before as uint8 bytes, including signed zero. The existing before/after capture surrounds the original in-place addition. The operand remains labelled an operand, not measured rounded output delta.

Selection/caps remain first guided search, first active initial call and first active call per ten rollout iterations: at most11 calls,20KiB numeric/call,220KiB/episode,16KiB metadata/call; no backfill or activity selection. Episode reset resets the selector. Zero gradients remain valid. No tensor enters metrics JSON.

The 263-file manifest extends the frozen257-file N25 source closure:254 prior files are byte-identical, three are modified, six are added. The three modified files are config.yaml, rdt_policy_steer.py and qd_actuator_clipped_rbf.py. The latter only parameterizes BoundedWitness schema/source/event constants: reversing that metadata edit reproduces the entire original file's SHA. Its mathematical functions are unchanged byte-for-byte. Source-delta inventory records all functions:153/159 original RDT functions unchanged, six changed and one added;10/12 helper functions unchanged, only emit/finish changed.

## CPU verification

97 different focused checks are covered in the final implementation:65 N26 checks and32 existing N25 regression checks.

- Independent CPU expression uses a where-based strict-interior derivative and direct cumulative projection, without calling the helper/projector under test. FP32/BF16 comparisons are exact uint8 equality, with no tolerance increase; interior, exact boundaries, saturation, coincident and mixed cases all pass.
- Layouts: contiguous, transpose-backed, and model-like sliced backing `(16,67,128)[:, -64:]` with stride8576/128/1 and offset384. The latter is static-source-informed synthetic evidence; actual live model output layout remains unobserved in this task.
- Initial/rollout caller checks prove same object/stride before modification, no-grad one-forward ordering, no model gradient, negative20 update, unchanged nontranslation/tail fields and original scheduler ordering.
- Complete synthetic guided searches retain21 forward calls,19 RBF calls,176 canonical candidates,11 score batches and10 resample/renoise/rollout operations. Default omitted versus explicit noisy option matches byte-for-byte. Witness on/off matches selected output, RNG, counters, scalar summaries and origin-read count.
- Wrong scheduler/options, nonfinite output, altered input bytes/signed zero, wrong witness schema/source/prediction/Jacobian, extra fields and size/metadata cap corruption are rejected.

Logs are preserved:
- `cpu-results/focused-v1.log`:41 failed/42 passed,21.08s. Every failure had the same engineering cause: the first implementation mistakenly named nonexistent `_EDSConfig.use_ed_cache`. It was replaced by the real initial_population_cache/ed_population_cache and existing use/save fields. No scientific arithmetic changed. The42 passing tests comprise32 N25 regressions plus10 N26 source/witness checks.
- `cpu-results/focused-v2.log`:55 passed/10 deselected,12.49s. Only affected N26 checks were rerun, adding the model-like layout. Previously passed unaffected regressions were not repeated.

Both runs used2 Torch/intra-op threads and2 inter-op threads, hidden CUDA, no CUDA initialization, and zero denied operations. The Python audit guard restricts file access to synthetic/source paths and read-only dependencies, blocks network/subprocess dispatch and real environment/model-package imports, and intercepts CUDA lazy initialization. This is a Python-process guard, not OS sandbox attestation. There were no real model, API, simulator, attempt/protected/Stage/credential reads or writes, and no online source/state/ledger/budget edits.

The legacy fkd_class invalid-escape SyntaxWarning is unchanged. Test artifacts under tmp are synthetic and are not research outcomes.

## Reproducible focused check

From this variant directory, with an existing owned tmp directory:

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python - <<'PY'
import runpy, sys
runpy.run_path('n26_cpu_guard_v1.py')
sys.path.insert(0, 'implementation')
import pytest
raise SystemExit(pytest.main(['-q', '-p', 'no:cacheprovider',
    '--basetemp=tmp/reproduction-unused',
    'implementation/tests/test_n26_clean_output_rbf.py',
    'implementation/tests/test_n25_clipped_rbf.py']))
PY
```

Use a new synthetic basetemp when reproducing. The actual two commands/log selections above are recorded in cpu-test-results-v1.json.

## Remaining work; no release implied

CPU reference agreement and witness input equality are wiring/arithmetic checks, not independent native CUDA proof or task benefit. N25's old backend proof cannot certify this source change. A future phase must independently bind and audit N26 sample-input witness/native arithmetic, add closed profile/controller/runner routes and prospective matched Dev admission, and review real source/runtime/budget/resource capacity after N25 terminal disposition. No such routes, plans, preflight, controller, budget adoption or evaluation release are included here. All online and protected evaluation remains closed. This phase makes no task success, physical-feasibility or runtime-overhead claim.
