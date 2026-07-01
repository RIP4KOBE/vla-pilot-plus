# RDT+EDS Level 4 LIBERO-PRO OOD Evaluation

Timestamp: `2026-06-20T07:03:13+00:00`

Verdict: `pass`

## Scope

- Policy: `rdt` only.
- Benchmark: LIBERO-PRO OOD perturbations on `libero_object` only.
- Episodes per job: `10`.
- Methods: `unguided`, `eds_softmax_strong_weak_renoise`, `eds_cem_resample_weak_renoise`.
- RDT+VLS, PI05, and previous wrong-checkpoint OOD runs are excluded.

## Method Configs

| Method | Guidance | population_size | cem_iters | use_cem | num_elites | temperature | renoise_t_max -> min |
| --- | --- | ---: | ---: | --- | ---: | ---: | --- |
| unguided | off | - | - | - | - | - | - |
| eds_softmax_strong_weak_renoise | EDS | 32 | 20 | False | 32 | 1.0 | 3 -> 1 |
| eds_cem_resample_weak_renoise | EDS | 32 | 20 | True | 8 | 1.0 | 3 -> 1 |

## Success Rates

| Suite | Method | Complete | Success | SR % | Mean select latency s | Mean EDS latency s | Videos | Metrics records | Qualitative PNGs |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `libero_object_object` | `unguided` | `True` | 6/10 | 60.00 | - | - | 10 | 0 | 0 |
| `libero_object_object` | `eds_softmax_strong_weak_renoise` | `True` | 3/10 | 30.00 | 6.057 | 5.991 | 10 | 144 | 880 |
| `libero_object_object` | `eds_cem_resample_weak_renoise` | `True` | 5/10 | 50.00 | 6.272 | 6.191 | 10 | 128 | 880 |
| `libero_object_swap` | `unguided` | `True` | 0/10 | 0.00 | - | - | 10 | 0 | 0 |
| `libero_object_swap` | `eds_softmax_strong_weak_renoise` | `True` | 0/10 | 0.00 | 6.073 | 6.003 | 10 | 212 | 880 |
| `libero_object_swap` | `eds_cem_resample_weak_renoise` | `True` | 0/10 | 0.00 | 6.091 | 6.016 | 10 | 154 | 880 |
| `libero_object_lan` | `unguided` | `True` | 3/10 | 30.00 | - | - | 10 | 0 | 0 |
| `libero_object_lan` | `eds_softmax_strong_weak_renoise` | `True` | 6/10 | 60.00 | 9.401 | 9.307 | 10 | 142 | 880 |
| `libero_object_lan` | `eds_cem_resample_weak_renoise` | `True` | 6/10 | 60.00 | 6.064 | 5.983 | 10 | 135 | 880 |
| `libero_object_task` | `unguided` | `True` | 0/10 | 0.00 | - | - | 10 | 0 | 0 |
| `libero_object_task` | `eds_softmax_strong_weak_renoise` | `True` | 0/10 | 0.00 | 6.063 | 5.991 | 9 | 171 | 792 |
| `libero_object_task` | `eds_cem_resample_weak_renoise` | `True` | 0/10 | 0.00 | 6.069 | 5.999 | 8 | 153 | 704 |
| `libero_object_env` | `unguided` | `True` | 0/10 | 0.00 | - | - | 10 | 0 | 0 |
| `libero_object_env` | `eds_softmax_strong_weak_renoise` | `True` | 1/10 | 10.00 | 7.213 | 7.142 | 10 | 238 | 880 |
| `libero_object_env` | `eds_cem_resample_weak_renoise` | `True` | 1/10 | 10.00 | 6.076 | 6.010 | 10 | 206 | 880 |
| `libero_object_temp` | `unguided` | `True` | 0/10 | 0.00 | - | - | 10 | 0 | 0 |
| `libero_object_temp` | `eds_softmax_strong_weak_renoise` | `True` | 0/10 | 0.00 | 11.420 | 11.308 | 8 | 168 | 704 |
| `libero_object_temp` | `eds_cem_resample_weak_renoise` | `True` | 0/10 | 0.00 | 6.087 | 6.016 | 9 | 212 | 792 |

## Output Index

- `libero_object_object` / `unguided`: output `outputs/rdt_eds_eval/level4_libero_object_object_unguided`, metrics `outputs/rdt_eds_eval/level4_libero_object_object_unguided/eds_eval/eds_metrics.jsonl`
- `libero_object_object` / `eds_softmax_strong_weak_renoise`: output `outputs/rdt_eds_eval/level4_libero_object_object_eds_softmax_strong_weak_renoise`, metrics `outputs/rdt_eds_eval/level4_libero_object_object_eds_softmax_strong_weak_renoise/eds_eval/eds_metrics.jsonl`
- `libero_object_object` / `eds_cem_resample_weak_renoise`: output `outputs/rdt_eds_eval/level4_libero_object_object_eds_cem_resample_weak_renoise`, metrics `outputs/rdt_eds_eval/level4_libero_object_object_eds_cem_resample_weak_renoise/eds_eval/eds_metrics.jsonl`
- `libero_object_swap` / `unguided`: output `outputs/rdt_eds_eval/level4_libero_object_swap_unguided`, metrics `outputs/rdt_eds_eval/level4_libero_object_swap_unguided/eds_eval/eds_metrics.jsonl`
- `libero_object_swap` / `eds_softmax_strong_weak_renoise`: output `outputs/rdt_eds_eval/level4_libero_object_swap_eds_softmax_strong_weak_renoise`, metrics `outputs/rdt_eds_eval/level4_libero_object_swap_eds_softmax_strong_weak_renoise/eds_eval/eds_metrics.jsonl`
- `libero_object_swap` / `eds_cem_resample_weak_renoise`: output `outputs/rdt_eds_eval/level4_libero_object_swap_eds_cem_resample_weak_renoise`, metrics `outputs/rdt_eds_eval/level4_libero_object_swap_eds_cem_resample_weak_renoise/eds_eval/eds_metrics.jsonl`
- `libero_object_lan` / `unguided`: output `outputs/rdt_eds_eval/level4_libero_object_lan_unguided`, metrics `outputs/rdt_eds_eval/level4_libero_object_lan_unguided/eds_eval/eds_metrics.jsonl`
- `libero_object_lan` / `eds_softmax_strong_weak_renoise`: output `outputs/rdt_eds_eval/level4_libero_object_lan_eds_softmax_strong_weak_renoise`, metrics `outputs/rdt_eds_eval/level4_libero_object_lan_eds_softmax_strong_weak_renoise/eds_eval/eds_metrics.jsonl`
- `libero_object_lan` / `eds_cem_resample_weak_renoise`: output `outputs/rdt_eds_eval/level4_libero_object_lan_eds_cem_resample_weak_renoise`, metrics `outputs/rdt_eds_eval/level4_libero_object_lan_eds_cem_resample_weak_renoise/eds_eval/eds_metrics.jsonl`
- `libero_object_task` / `unguided`: output `outputs/rdt_eds_eval/level4_libero_object_task_unguided`, metrics `outputs/rdt_eds_eval/level4_libero_object_task_unguided/eds_eval/eds_metrics.jsonl`
- `libero_object_task` / `eds_softmax_strong_weak_renoise`: output `outputs/rdt_eds_eval/level4_libero_object_task_eds_softmax_strong_weak_renoise`, metrics `outputs/rdt_eds_eval/level4_libero_object_task_eds_softmax_strong_weak_renoise/eds_eval/eds_metrics.jsonl`
- `libero_object_task` / `eds_cem_resample_weak_renoise`: output `outputs/rdt_eds_eval/level4_libero_object_task_eds_cem_resample_weak_renoise`, metrics `outputs/rdt_eds_eval/level4_libero_object_task_eds_cem_resample_weak_renoise/eds_eval/eds_metrics.jsonl`
- `libero_object_env` / `unguided`: output `outputs/rdt_eds_eval/level4_libero_object_env_unguided`, metrics `outputs/rdt_eds_eval/level4_libero_object_env_unguided/eds_eval/eds_metrics.jsonl`
- `libero_object_env` / `eds_softmax_strong_weak_renoise`: output `outputs/rdt_eds_eval/level4_libero_object_env_eds_softmax_strong_weak_renoise`, metrics `outputs/rdt_eds_eval/level4_libero_object_env_eds_softmax_strong_weak_renoise/eds_eval/eds_metrics.jsonl`
- `libero_object_env` / `eds_cem_resample_weak_renoise`: output `outputs/rdt_eds_eval/level4_libero_object_env_eds_cem_resample_weak_renoise`, metrics `outputs/rdt_eds_eval/level4_libero_object_env_eds_cem_resample_weak_renoise/eds_eval/eds_metrics.jsonl`
- `libero_object_temp` / `unguided`: output `outputs/rdt_eds_eval/level4_libero_object_temp_unguided`, metrics `outputs/rdt_eds_eval/level4_libero_object_temp_unguided/eds_eval/eds_metrics.jsonl`
- `libero_object_temp` / `eds_softmax_strong_weak_renoise`: output `outputs/rdt_eds_eval/level4_libero_object_temp_eds_softmax_strong_weak_renoise`, metrics `outputs/rdt_eds_eval/level4_libero_object_temp_eds_softmax_strong_weak_renoise/eds_eval/eds_metrics.jsonl`
- `libero_object_temp` / `eds_cem_resample_weak_renoise`: output `outputs/rdt_eds_eval/level4_libero_object_temp_eds_cem_resample_weak_renoise`, metrics `outputs/rdt_eds_eval/level4_libero_object_temp_eds_cem_resample_weak_renoise/eds_eval/eds_metrics.jsonl`

## Completion Gate

- All 18 Level 4 jobs have complete output markers.
- Every EDS job has a non-empty `eds_eval/eds_metrics.jsonl`.
- `backend.libero.strict_perturbations=true` was used for Level 4 commands.

## Notes

- Success/failure is parsed from each job's `results.txt`; process exit code alone is not treated as the result.
- Video counts are based on `episode_*/*.mp4` under each job output directory.
- Qualitative counts include saved keypoint, selected trajectory, population cloud, per-iteration best trajectory, and initial-vs-final overlays.
