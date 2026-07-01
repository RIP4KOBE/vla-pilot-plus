# RDT+EDS Level 2 Online Smoke Report

Timestamp: `2026-06-11T12:05:00+00:00`

Verdict: `fail`

## Scope

- Policy: `rdt`
- Suite: `libero_object`
- Task filter: `backend.libero.task_ids_filter=[0]`
- Episodes per method: `3`
- Horizon: `backend.libero.max_episode_steps=240`
- EDS baseline setting: `population_size=16`, `cem_iters=10`, `use_cem=false`
- Qualitative artifacts: enabled for EDS runs
- Level 4 LIBERO-PRO OOD: not run

## Results

| method | SR | chunks | counters | finite | selected=best | reward improve | distance improve | either improve | reward_spread_mean | select_latency_s | eds_loop_s | diversity init->final |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| unguided | 3/3 (100.00%) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p16_c10 | 1/3 (33.33%) | 48 | 48/48 | 48/48 | 48/48 | 5/48 | 23/48 | 23/48 | 0.0005 | 3.1290 | 3.0474 | 4.2031->2.5685 |
| zero | 3/3 (100.00%) | 40 | 40/40 | 40/40 | 40/40 | 0/40 | 22/40 | 22/40 | 0.0000 | 2.7030 | 2.6312 | 2.9976->2.2733 |
| shuffled | 0/3 (0.00%) | 51 | 51/51 | 51/51 | 51/51 | 4/51 | 30/51 | 33/51 | 0.0026 | 2.6995 | 2.6284 | 5.2534->3.7511 |
| inverted | 3/3 (100.00%) | 41 | 41/41 | 41/41 | 41/41 | 3/41 | 26/41 | 29/41 | 0.0006 | 3.6804 | 3.6090 | 3.0116->2.4119 |

## Evidence Files

- Status table: `docs/03_evidence/eds_steering/rdt_eds_eval_status.csv`
- Unguided output: `outputs/rdt_eds_eval/level2_libero_object_unguided/results.txt`
- Normal EDS output: `outputs/rdt_eds_eval/level2_libero_object_p16_c10/results.txt`
- Zero-reward output: `outputs/rdt_eds_eval/level2_libero_object_zero/results.txt`
- Shuffled-keypoint output: `outputs/rdt_eds_eval/level2_libero_object_shuffled/results.txt`
- Inverted-reward output: `outputs/rdt_eds_eval/level2_libero_object_inverted/results.txt`
- EDS metrics JSONL:
  - `outputs/rdt_eds_eval/level2_libero_object_p16_c10/eds_eval/eds_metrics.jsonl`
  - `outputs/rdt_eds_eval/level2_libero_object_zero/eds_eval/eds_metrics.jsonl`
  - `outputs/rdt_eds_eval/level2_libero_object_shuffled/eds_eval/eds_metrics.jsonl`
  - `outputs/rdt_eds_eval/level2_libero_object_inverted/eds_eval/eds_metrics.jsonl`
- Qualitative artifacts are under each EDS run's `eds_eval/qualitative/episode_*/chunk_*` directory.

## Deployment Correctness

Level 2 confirms the EDS path is executed online, not silently replaced by unguided denoising. Every EDS chunk has:

- `eds_enter_count=1`
- `score_call_count=1+cem_iters=11`
- `resample_count=10`
- `renoise_count=10`
- `rollout_count=10`
- `nonfinite_count=0`
- `action_mask_violation_max=0.0`
- `selected_cost == -final_best_reward`

This satisfies the online deployment/counter part of the gate for all four EDS reward modes.

## Algorithm Effectiveness

The smoke test does not support the claim that current EDS improves RDT on this setup.

- Normal EDS reached only `1/3` success, while unguided RDT and zero-reward EDS both reached `3/3`.
- Normal EDS improved the recorded reward in only `5/48` guided chunks and improved the proxy target distance in `23/48` chunks, below the protocol's >=70% Level-1/Level-2 directional expectation.
- Zero-reward EDS had `reward_spread_mean=0.0`, as expected, but still achieved `3/3`. This means task success in this small smoke run cannot by itself prove reward-guided optimization.
- Inverted reward also achieved `3/3`, and shuffled keypoints produced many target-distance improvements while failing `0/3`. This indicates the current proxy metrics and/or reward-keypoint semantics are not yet reliable enough to certify algorithmic correctness.

## Latency

Mean `select_action_latency_s`:

- normal EDS p16/c10: `3.1290s`
- zero reward: `2.7030s`
- shuffled keypoints: `2.6995s`
- inverted reward: `3.6804s`

Unguided latency is not instrumented in the same JSONL path, so this report does not make a precise unguided-vs-EDS latency claim.

## Qualitative Review Targets

Review the following first chunk artifacts before interpreting success-rate differences:

- `outputs/rdt_eds_eval/level2_libero_object_p16_c10/eds_eval/qualitative/episode_000/chunk_000000/keypoints_selected_eef_overlay.png`
- `outputs/rdt_eds_eval/level2_libero_object_p16_c10/eds_eval/qualitative/episode_000/chunk_000000/initial_best_vs_final_selected.png`
- `outputs/rdt_eds_eval/level2_libero_object_p16_c10/eds_eval/qualitative/episode_000/chunk_000000/population_overlay_iter_last.png`
- `outputs/rdt_eds_eval/level2_libero_object_p16_c10/eds_eval/qualitative/episode_000/chunk_000000/best_trajectory_overlay_iter_009.png`

The qualitative gate is not passed by SR alone. The selected trajectory should visibly move toward the relevant keypoint/stage reward under normal reward, and zero/shuffled/inverted reward should not show the same trend.

## Conclusion

Level 2 passes the online deployment-correctness portion of the protocol but fails the algorithm-effectiveness smoke gate. The strongest evidence is the mismatch between normal EDS (`1/3`) and the ablations (`zero=3/3`, `inverted=3/3`). Level 3 should still run as planned on the full `libero_object` suite to determine whether this is a small-run anomaly or a systematic reward/guidance issue.
