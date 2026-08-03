# RBF+EDS Start08 Renoise 1->1 Supplement

Timestamp: `2026-07-11T09:45:01+00:00`

## Summary

This supplement adds one missing local-refinement setting to the third-round renoise ablation:

- `initial_sampling_mode=rbf_diverse_denoise`
- `initial_diversity_scale=20.0`
- `initial_diversity_start_ratio=0.8`
- `renoise_t_max=1`
- `renoise_t_min=1`

The setting was run on base `libero_object`, task id 0, with the same evaluation and qualitative tracing requirements as the third-round ablation.

Result: `1 -> 1` reaches `2/3` success. It gives the highest first-rollout EEF diversity among the `start08` renoise settings, but it does not beat `4 -> 1` on task success.

## Execution

Output directory:

`outputs/rdt_eds_eval/level3_libero_object_rbf_s20_start08_rt1to1`

Log:

`docs/03_evidence/eds_init_pg_diverse_sampling/logs/level3_libero_object_rbf_s20_start08_rt1to1.log`

GPU:

`CUDA_VISIBLE_DEVICES=0`, `MUJOCO_EGL_DEVICE_ID=0`

Command used the same core settings as third-round renoise ablation:

```bash
conda run -n vla-pilot python main.py \
  policy.type=rdt \
  backend=libero \
  backend.libero.suite_name=libero_object \
  backend.libero.task_ids_filter=[0] \
  main.episode_num=3 \
  backend.libero.max_episode_steps=240 \
  main.use_vlm_stage_recognition=false \
  perception.gemini_grounding.enabled=false \
  main.cached_functions_dir=/home/hynx/VLA-Pilot++/outputs/libero/2026-06-04_13-21-01/episode_1/vlm_agent \
  main.use_guidance=true \
  main.guidance_type=eds \
  main.eds_config.population_size=16 \
  main.eds_config.cem_iters=10 \
  main.eds_config.use_cem=false \
  main.eds_config.num_elites=32 \
  main.eds_config.temperature=0.1 \
  main.eds_config.renoise_t_max=1 \
  main.eds_config.renoise_t_min=1 \
  main.eds_config.initial_sampling_mode=rbf_diverse_denoise \
  main.eds_config.initial_diversity_scale=20.0 \
  main.eds_config.initial_diversity_start_ratio=0.8 \
  main.eds_mechanism_pretest.enabled=true \
  main.eds_mechanism_pretest.first_chunk_only=false \
  main.eds_mechanism_pretest.output_mode=qualitative_chunk \
  main.eds_mechanism_pretest.max_chunks=2
```

The main run log ended with `exit=0`.

## Validation

| Check | Result |
|---|---:|
| Success count | 2/3 |
| Success rate | 66.67% |
| Metrics records | 63 |
| Qualitative PNGs | 354 |
| RBF diversity NPZ traces | 6 |
| RBF diversity metrics JSON | 6 |
| Fallback count | 0 |
| Nonfinite max | 0 |
| Action mask violation max | 0 |

Hydra config confirms:

- `suite_name: libero_object`
- `strict_perturbations: false`
- `task_ids_filter: [0]`
- `renoise_t_max: 1`
- `renoise_t_min: 1`
- `initial_sampling_mode: rbf_diverse_denoise`
- `initial_diversity_scale: 20.0`
- `initial_diversity_start_ratio: 0.8`
- `output_mode: qualitative_chunk`
- `max_chunks: 2`

All six `rbf_diversity_trace.npz` files were loaded successfully. Each contains before / after-RBF-phase / final EEF trajectories, endpoints, and pairwise distances.

## Comparison Against Start08 Renoise Sweep

| Run | Success | Records | Initial Retention | Initial Final Div | Endpoint Final | First Rollout Div | Final Iter Div | Selected Reward | Target Distance | Latency s | Fallbacks |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `level2_libero_object_rbf_s20_start08` | 1/3 | 77 | 0.340 | 0.156 | 0.082 | 0.018 | 0.014 | -0.010 | 0.078 | 2.785 | 0 |
| `level3_libero_object_rbf_s20_start08_rt4to1` | 3/3 | 61 | 0.309 | 0.137 | 0.071 | 0.020 | 0.014 | -0.009 | 0.068 | 2.594 | 0 |
| `level3_libero_object_rbf_s20_start08_rt3to1` | 2/3 | 63 | 0.323 | 0.145 | 0.076 | 0.024 | 0.012 | -0.010 | 0.071 | 2.042 | 0 |
| `level3_libero_object_rbf_s20_start08_rt2to1` | 1/3 | 80 | 0.340 | 0.156 | 0.082 | 0.036 | 0.015 | -0.010 | 0.077 | 1.630 | 0 |
| `level3_libero_object_rbf_s20_start08_rt1to1` | 2/3 | 63 | 0.315 | 0.141 | 0.073 | 0.064 | 0.015 | -0.010 | 0.073 | 1.556 | 0 |

## Interpretation

`1 -> 1` is the strongest local refinement setting in this sweep. It has only one truncated rollout denoise step in every EDS iteration, so it preserves more of the parent/action signal after rollout.

Mechanistically, it does what we expected:

- first-rollout diversity increases from `0.018` in the `5 -> 1` start08 baseline to `0.064`;
- latency is the lowest among the start08 settings;
- fallback remains zero.

But task performance does not monotonically improve with first-rollout diversity:

- `4 -> 1` remains the best start08 setting by success rate: `3/3`;
- `1 -> 1` reaches `2/3`, matching `3 -> 1` and beating `2 -> 1`;
- final-iteration diversity is still low, so the full EDS loop continues to converge even when first-rollout diversity is higher.

## Recommendation

Keep `start08_rt4to1` as the current best practical setting for task success.

Use `start08_rt1to1` as an important diagnostic point: it supports the hypothesis that weaker truncated renoise preserves first-rollout diversity, but it also shows that preserving diversity alone is not sufficient. The next algorithmic experiment should target diversity preservation during parent selection or carryover, rather than reducing `renoise_t_max` further.

## Verification

Tests:

```text
tests/test_eds_eval_runner.py tests/test_eds_mechanism_pretest_vis.py
30 passed in 10.23s
```

No RBF+EDS algorithm core code was changed for this supplement. This was a direct evaluation run with existing instrumentation.
