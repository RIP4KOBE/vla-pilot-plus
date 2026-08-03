# RBF+EDS Renoise Tmax Ablation Report

Timestamp: `2026-07-10T16:53:51+00:00`

## Summary

This run evaluates whether lowering EDS `renoise_t_max` preserves RBF-diverse initial proposals through the first truncated rollout.

Result: lowering `renoise_t_max` can modestly increase first-rollout EEF diversity, especially for `start_ratio=0.8, rt2to1`, but it does not prevent full EDS refinement from collapsing population diversity by the final iteration. The best task result in this sweep is `rbf_s20_start08_rt4to1` with `3/3` success.

## Execution

Worktree:

`/home/hynx/VLA-Pilot++/.worktrees/exp/eds-init-pg-diverse-sampling`

Command:

```bash
conda run -n vla-pilot python scripts/rdt_eds_eval_runner.py run-level \
  --level renoise_ablation \
  --episodes 3 \
  --gpus 0,1,2,3,4,5 \
  --timeout-seconds 28800 \
  --cached-functions-dir /home/hynx/VLA-Pilot++/outputs/libero/2026-06-04_13-21-01/episode_1/vlm_agent \
  --offline-vlm
```

All six H200 jobs exited with code `0`. Online VLM was disabled and cached guidance functions were used.

## Job Status

| Job | GPU | `start_ratio` | `renoise_t_max -> min` | Status | Success |
|---|---:|---:|---:|---|---:|
| `level3_libero_object_rbf_s20_start06_rt4to1` | 0 | 0.6 | 4 -> 1 | done | 2/3 |
| `level3_libero_object_rbf_s20_start06_rt3to1` | 1 | 0.6 | 3 -> 1 | done | 0/3 |
| `level3_libero_object_rbf_s20_start06_rt2to1` | 2 | 0.6 | 2 -> 1 | done | 0/3 |
| `level3_libero_object_rbf_s20_start08_rt4to1` | 3 | 0.8 | 4 -> 1 | done | 3/3 |
| `level3_libero_object_rbf_s20_start08_rt3to1` | 4 | 0.8 | 3 -> 1 | done | 2/3 |
| `level3_libero_object_rbf_s20_start08_rt2to1` | 5 | 0.8 | 2 -> 1 | done | 1/3 |

Hydra configs were checked for all jobs: each has `initial_sampling_mode=rbf_diverse_denoise`, `initial_diversity_scale=20.0`, `renoise_t_min=1`, and `main.eds_mechanism_pretest.output_mode=qualitative_chunk`.

## Quantitative Results

The first two rows are the prior `5 -> 1` baseline runs. New ablations use the same `libero_object` task filter and 3 episodes.

| Run | Success Rate | Records | Initial Retention | Initial Final Diversity | Endpoint Final | Selected Reward | Target Distance | Latency s | Fallbacks |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `level2_libero_object_rbf_s20_start06` | 0.00 | 90 | 0.228 | 0.091 | 0.048 | -0.010 | 0.079 | 2.785 | 0 |
| `level2_libero_object_rbf_s20_start08` | 33.33 | 77 | 0.340 | 0.156 | 0.082 | -0.010 | 0.078 | 2.785 | 0 |
| `level3_libero_object_rbf_s20_start06_rt4to1` | 66.67 | 61 | 0.193 | 0.076 | 0.040 | -0.011 | 0.082 | 2.578 | 0 |
| `level3_libero_object_rbf_s20_start06_rt3to1` | 0.00 | 90 | 0.184 | 0.072 | 0.037 | -0.010 | 0.072 | 2.036 | 0 |
| `level3_libero_object_rbf_s20_start06_rt2to1` | 0.00 | 90 | 0.198 | 0.078 | 0.040 | -0.023 | 0.116 | 1.662 | 0 |
| `level3_libero_object_rbf_s20_start08_rt4to1` | 100.00 | 61 | 0.309 | 0.137 | 0.071 | -0.009 | 0.068 | 2.594 | 0 |
| `level3_libero_object_rbf_s20_start08_rt3to1` | 66.67 | 63 | 0.323 | 0.145 | 0.076 | -0.010 | 0.071 | 2.042 | 0 |
| `level3_libero_object_rbf_s20_start08_rt2to1` | 33.33 | 80 | 0.340 | 0.156 | 0.082 | -0.010 | 0.077 | 1.630 | 0 |

## Mechanism Trace Comparison

The table below uses the same qualitative subset for every run: `episode_000/001/002` and chunks `000000`, `000008` where available. This avoids comparing all baseline chunks against only the first two chunks from the new runs.

| Run | Trace Count | Initial Div | After Renoise Div | First Rollout Div | Final Iter Div |
|---|---:|---:|---:|---:|---:|
| `level2_libero_object_rbf_s20_start06` | 6 | 0.050 | 0.128 | 0.018 | 0.014 |
| `level2_libero_object_rbf_s20_start08` | 6 | 0.126 | 0.122 | 0.018 | 0.014 |
| `level3_libero_object_rbf_s20_start06_rt4to1` | 6 | 0.048 | 0.120 | 0.018 | 0.014 |
| `level3_libero_object_rbf_s20_start06_rt3to1` | 6 | 0.049 | 0.109 | 0.020 | 0.014 |
| `level3_libero_object_rbf_s20_start06_rt2to1` | 6 | 0.050 | 0.087 | 0.022 | 0.015 |
| `level3_libero_object_rbf_s20_start08_rt4to1` | 6 | 0.127 | 0.125 | 0.020 | 0.014 |
| `level3_libero_object_rbf_s20_start08_rt3to1` | 6 | 0.124 | 0.124 | 0.024 | 0.012 |
| `level3_libero_object_rbf_s20_start08_rt2to1` | 6 | 0.128 | 0.125 | 0.036 | 0.015 |

Interpretation:

- `rt2to1` improves first-rollout diversity most clearly, especially for `start08`.
- `rt3to1` gives a smaller first-rollout diversity gain.
- `rt4to1` barely changes first-rollout diversity, but gives the strongest success rate.
- Final-iteration diversity remains low for all settings, so lower renoise alone does not solve late EDS population collapse.

## Qualitative Artifacts

Each new job saved 6 qualitative mechanism chunks: two chunks per episode for three episodes. Each job contains:

- 354 qualitative PNG files.
- 6 `RBF_diversity/rbf_diversity_trace.npz` files.
- 6 `RBF_diversity/rbf_diversity_metrics.json` files.
- `single_step_inner_loop` artifacts, including `00_initial_population_3d.png` and `04_after_rollout_3d.png`.
- `full_eds_process` artifacts, including per-iteration population plots, `reward_curve.png`, `diversity_curve.png`, `distance_curve.png`, `per_iter_metrics.csv`, and `full_process_summary.md`.

Example artifact root:

`outputs/rdt_eds_eval/level3_libero_object_rbf_s20_start08_rt4to1/eds_eval/qualitative/episode_000/chunk_000000`

NPZ trace validation passed for all 36 new RBF diversity trace files. Keys include:

`before_trajectories`, `after_rbf_phase_trajectories`, `final_trajectories`, endpoint arrays, and pairwise-distance arrays.

## Answers To Design Questions

1. Lowering `renoise_t_max` did not consistently improve initial diversity retention in the all-chunk metrics. `start08_rt2to1` roughly matches the `5 -> 1` baseline retention, while `start06` variants are lower.
2. `renoise_t_max=2` best avoids first-rollout collapse mechanically, but only in the early trace subset. It does not preserve diversity through final EDS iteration.
3. `renoise_t_max=2` can hurt utility: `start06_rt2to1` has much worse selected reward and target distance.
4. `renoise_t_max=4` is the best task-performance setting in this sweep: `start08_rt4to1` reaches 100% success and improves target distance vs the `start08` baseline.
5. `start_ratio=0.8` is more stable than `0.6` under reduced renoise. All three `start08` variants have nonzero success; two `start06` variants fail all episodes.
6. Yes, there is a diversity/success mismatch. `start08_rt2to1` has the clearest first-rollout diversity improvement but lower success than `start08_rt4to1`.
7. Latency improves as `renoise_t_max` decreases because rollout uses fewer denoising steps. `rt2to1` is about 1.63-1.66s per select action vs about 2.79s for the `5 -> 1` baseline.
8. No RBF fallback occurred in any new run.
9. Qualitative artifacts can show RBF initial diversity and first-rollout diversity differences, but they also show that full EDS still converges to low diversity later.
10. The next algorithmic step should not be only smaller `renoise_t_max`. The most promising follow-up is combining `start08_rt4to1` with a diversity-preserving mechanism during parent selection or carryover.

## Recommendation

Use `initial_diversity_start_ratio=0.8`, `initial_diversity_scale=20`, and `renoise_t_max=4 -> renoise_t_min=1` as the current best MVP setting.

Rationale:

- It gives the best observed success rate: `3/3`.
- It improves target distance vs the `5 -> 1` `start08` baseline.
- It preserves enough restart/exploration to avoid the overly local behavior seen in `rt2to1`.
- It reduces latency slightly compared with `5 -> 1`.

The mechanism evidence says reduced renoise alone is not sufficient to keep population diversity through all EDS iterations. The next round should test one of:

- diversity-aware parent resampling;
- elite/diverse anchor carryover;
- rollout-phase RBF only in early EDS iterations;
- adaptive renoise schedule based on measured first-rollout diversity collapse.

## Verification

- `tests/test_eds_eval_runner.py`: passed, 23 tests.
- `tests/test_eds_mechanism_pretest_vis.py`: passed, 7 tests.
- All six job directories exist under `outputs/rdt_eds_eval`.
- All six `.hydra/config.yaml` files have expected `renoise_t_max`, `renoise_t_min`, RBF start ratio, and qualitative trace settings.
- All six `eds_eval/eds_metrics.jsonl` files are non-empty.
- All 36 new `rbf_diversity_trace.npz` files are readable.
- No fallback or failed chunk was observed in metrics.

Evaluation/runner code was modified to add the `renoise_ablation` sweep and to enable qualitative-chunk mechanism traces for this sweep. RBF+EDS algorithm core logic was not changed.
