# RDT+EDS Level 3 LIBERO-Object Evaluation Report

Timestamp: `2026-06-11T14:29:36+00:00`

Verdict: `inconclusive`

## Scope

- Policy: `rdt`
- Suite: `libero_object`
- Episodes: `10`
- Horizon: `backend.libero.max_episode_steps=240`
- VLM stage recognition: enabled
- Gemini grounding: enabled
- Rendering: disabled
- Trajectory visualization/debug artifacts: enabled
- Level 4 LIBERO-PRO OOD: not run

## Results

| method | SR | wall-clock | chunks | counters | finite | selected=best | reward improve | distance improve | either improve | reward_spread_mean | select_latency_s | eds_loop_s | diversity init->final |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| unguided | 9/10 (90.00%) | 3.6m | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p16_c10 | 6/10 (60.00%) | 17.7m | 149 | 149/149 | 149/149 | 149/149 | 14/149 | 55/149 | 57/149 | 0.0007 | 2.975 | 2.901 | 4.199->3.037 |
| p16_c20 | 6/10 (60.00%) | 27.2m | 182 | 182/182 | 182/182 | 182/182 | 22/182 | 62/182 | 65/182 | 0.0005 | 5.045 | 4.975 | 4.313->2.608 |
| p32_c10 | 6/10 (60.00%) | 20.0m | 116 | 116/116 | 116/116 | 116/116 | 21/116 | 45/116 | 52/116 | 0.0010 | 5.133 | 5.065 | 4.364->3.646 |
| p32_c20 | 8/10 (80.00%) | 31.9m | 132 | 132/132 | 132/132 | 132/132 | 13/132 | 49/132 | 52/132 | 0.0008 | 9.855 | 9.787 | 3.929->2.986 |
| p32_c10_cem | 7/10 (70.00%) | 21.2m | 131 | 131/131 | 131/131 | 131/131 | 16/131 | 55/131 | 56/131 | 0.0008 | 5.115 | 5.043 | 3.999->3.358 |
| zero | 6/10 (60.00%) | 18.1m | 166 | 166/166 | 166/166 | 166/166 | 0/166 | 73/166 | 73/166 | 0.0000 | 2.757 | 2.689 | 4.151->3.152 |
| shuffled | 6/10 (60.00%) | 19.1m | 180 | 180/180 | 180/180 | 180/180 | 25/180 | 90/180 | 104/180 | 0.0020 | 2.764 | 2.694 | 4.370->3.124 |
| inverted | 3/10 (30.00%) | 20.6m | 196 | 196/196 | 196/196 | 196/196 | 34/196 | 113/196 | 144/196 | 0.0020 | 2.713 | 2.649 | 4.758->3.604 |

## Evidence Files

- Status table: `docs/03_evidence/eds_steering/rdt_eds_eval_status.csv`
- Logs: `docs/03_evidence/eds_steering/logs/level3_libero_object_*.log`
- Outputs: `outputs/rdt_eds_eval/level3_libero_object_*`
- EDS metrics: `outputs/rdt_eds_eval/level3_libero_object_*/eds_eval/eds_metrics.jsonl`
- Qualitative artifacts: `outputs/rdt_eds_eval/level3_libero_object_*/eds_eval/qualitative/episode_*/chunk_*`

Representative qualitative files to inspect:

- `outputs/rdt_eds_eval/level3_libero_object_p32_c20/eds_eval/qualitative/episode_000/chunk_000000/keypoints_selected_eef_overlay.png`
- `outputs/rdt_eds_eval/level3_libero_object_p32_c20/eds_eval/qualitative/episode_000/chunk_000000/initial_best_vs_final_selected.png`
- `outputs/rdt_eds_eval/level3_libero_object_p32_c20/eds_eval/qualitative/episode_000/chunk_000000/population_overlay_iter_last.png`
- `outputs/rdt_eds_eval/level3_libero_object_p32_c20/eds_eval/qualitative/episode_000/chunk_000000/best_trajectory_overlay_iter_009.png`

## Deployment Correctness

Deployment-correctness gates passed for all EDS runs:

- Every EDS metrics file was written.
- Every guided chunk entered EDS once.
- `score_call_count == 1 + cem_iters` for every guided chunk.
- `resample_count == renoise_count == rollout_count == cem_iters` for every guided chunk.
- `nonfinite_count == 0` for every guided chunk.
- `selected_cost == -final_best_reward` for every guided chunk, so the returned particle matches the best final score under the current cost sign convention.

This confirms the Level 3 online runs used the EDS loop rather than falling back to unguided denoising.

## Algorithm Effectiveness

The current EDS implementation is not consistently better than unguided RDT on `libero_object`.

- Unguided RDT reached `9/10`.
- Lightweight normal EDS settings (`p16_c10`, `p16_c20`, `p32_c10`) each reached only `6/10`.
- `p32_c10_cem` improved to `7/10`, suggesting CEM-style parent selection helps slightly.
- `p32_c20` reached `8/10`, which is within 10 percentage points of unguided and is the only tested normal EDS setting close to the baseline.
- `p32_c20` is also the most expensive setting, with mean `select_action_latency_s=9.855` and wall-clock `31.9m` for 10 episodes.

The ablations do not support a clean claim that the current reward signal is reliably steering toward task success:

- `zero` reached `6/10`, equal to the common lightweight normal EDS result.
- `shuffled` also reached `6/10`, despite using shuffled keypoints.
- `inverted` dropped to `3/10`, which is directionally useful evidence that reward sign matters, but chunk-level proxy metrics still show many target-distance improvements under inverted reward. That indicates the current target-distance proxy is too weak or partially misaligned with true task progress.

## Parameter Findings

- Increasing `cem_iters` from 10 to 20 at population 16 did not improve SR: `p16_c10=6/10`, `p16_c20=6/10`.
- Increasing population from 16 to 32 at `cem_iters=10` did not improve SR: `p16_c10=6/10`, `p32_c10=6/10`.
- Combining larger population and more iterations improved SR: `p32_c20=8/10`, but roughly tripled mean chunk latency compared with `p16_c10`.
- Enabling CEM at `p32_c10` improved SR from `6/10` to `7/10`, but did not reach unguided.

## Conclusion

Level 3 confirms that EDS is deployed correctly and can run end-to-end on `libero_object`. The algorithm-effectiveness gate is only partially satisfied: EDS is not zero-success, and the strongest setting (`p32_c20`) is close to unguided, but EDS does not consistently outperform or match unguided across practical parameter settings. The next debugging priority should be reward/keypoint semantics and qualitative trajectory validation, not simply more CEM iterations.

Level 4 LIBERO-PRO OOD evaluation remains pending and must not be started until user approval.
