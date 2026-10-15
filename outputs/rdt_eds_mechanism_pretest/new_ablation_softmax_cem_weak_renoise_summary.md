# New RDT+EDS Ablations: Strong Selection + Weak Renoise

Date: 2026-06-18

This report adds two combination ablations on top of the prior five mechanism-pretest ablations. Both use real `libero_object` execution with `population_size=16`, `cem_iters=10`, `reward_mode=normal`, and weak renoise via temporary `renoise_scale=0.25`.

## Configurations

| run | resampling | selection setting | renoise | mechanism pretest run id | 10-episode run dir |
| --- | --- | --- | --- | --- | --- |
| `softmax_strong_weak_renoise` | softmax | `temperature=2.0`, `use_cem=false` | `renoise_scale=0.25` | `libero_object_task1_seed000_ablate_softmax_strong_weak_renoise_p16_c10` | `hydra_ablate_softmax_strong_weak_renoise_10ep` |
| `cem_weak_renoise` | CEM | `use_cem=true`, `num_elites=4` | `renoise_scale=0.25` | `libero_object_task1_seed000_ablate_cem_weak_renoise_p16_c10` | `hydra_ablate_cem_weak_renoise_10ep_retry` |

The first `cem_weak_renoise` 10-episode attempt is preserved at `hydra_ablate_cem_weak_renoise_10ep`, but episodes 5-8 failed during VLM preparation due to external API TLS handshake timeouts. The retry directory above is used for final 10-episode results because it produced 10 real episode videos and no preparation errors.

## Mechanism Pretest Artifacts

| run | artifact dir | reward curve | distance curve | diversity curve | single-step CSV | per-iter CSV |
| --- | --- | --- | --- | --- | --- | --- |
| `softmax_strong_weak_renoise` | `outputs/rdt_eds_mechanism_pretest/libero_object_task1_seed000_ablate_softmax_strong_weak_renoise_p16_c10` | `outputs/rdt_eds_mechanism_pretest/libero_object_task1_seed000_ablate_softmax_strong_weak_renoise_p16_c10/full_eds_process/reward_curve.png` | `outputs/rdt_eds_mechanism_pretest/libero_object_task1_seed000_ablate_softmax_strong_weak_renoise_p16_c10/full_eds_process/distance_curve.png` | `outputs/rdt_eds_mechanism_pretest/libero_object_task1_seed000_ablate_softmax_strong_weak_renoise_p16_c10/full_eds_process/diversity_curve.png` | `outputs/rdt_eds_mechanism_pretest/libero_object_task1_seed000_ablate_softmax_strong_weak_renoise_p16_c10/single_step_inner_loop/single_step_particles.csv` | `outputs/rdt_eds_mechanism_pretest/libero_object_task1_seed000_ablate_softmax_strong_weak_renoise_p16_c10/full_eds_process/per_iter_metrics.csv` |
| `cem_weak_renoise` | `outputs/rdt_eds_mechanism_pretest/libero_object_task1_seed000_ablate_cem_weak_renoise_p16_c10` | `outputs/rdt_eds_mechanism_pretest/libero_object_task1_seed000_ablate_cem_weak_renoise_p16_c10/full_eds_process/reward_curve.png` | `outputs/rdt_eds_mechanism_pretest/libero_object_task1_seed000_ablate_cem_weak_renoise_p16_c10/full_eds_process/distance_curve.png` | `outputs/rdt_eds_mechanism_pretest/libero_object_task1_seed000_ablate_cem_weak_renoise_p16_c10/full_eds_process/diversity_curve.png` | `outputs/rdt_eds_mechanism_pretest/libero_object_task1_seed000_ablate_cem_weak_renoise_p16_c10/single_step_inner_loop/single_step_particles.csv` | `outputs/rdt_eds_mechanism_pretest/libero_object_task1_seed000_ablate_cem_weak_renoise_p16_c10/full_eds_process/per_iter_metrics.csv` |

Both mechanism pretest directories contain 36 files and match the reference `libero_object_task1_seed000_ablate_weak_renoise_p16_c10` structure.

## Mechanism Metrics

| run | 1ep success | initial best reward | mean parent rank | top-4 parent frac | unique parents | mean renoise delta | rollout mean reward delta | after-rollout best reward | after-rollout best distance |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `softmax_strong_weak_renoise` | fail, 240 steps | -0.094727 | 9.750 | 0.062 | 12 | 24.773438 | +0.003448 | -0.098145 | 0.303264 |
| `cem_weak_renoise` | fail, 240 steps | -0.094727 | 2.375 | 1.000 | 4 | 24.796875 | -0.002197 | -0.098145 | 0.303264 |

| run | iter0 best reward | iter9 best reward | delta reward | iter0 distance | iter9 distance | delta distance | iter0 diversity | iter9 diversity | delta diversity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `softmax_strong_weak_renoise` | -0.098145 | -0.096680 | +0.001465 | 0.303264 | 0.300526 | -0.002738 | 0.018431 | 0.007543 | -0.010888 |
| `cem_weak_renoise` | -0.098145 | -0.095703 | +0.002441 | 0.303264 | 0.299350 | -0.003914 | 0.018395 | 0.005204 | -0.013191 |

Mechanism readout: CEM+weak renoise creates much stronger parent selection than strong-softmax+weak renoise (`top-4=1.0` vs `0.062`) and stronger full-process reward/distance improvement in the first chunk. Both weak-renoise variants reduce diversity sharply, with CEM producing the strongest collapse.

## 10-Episode Results

| run | success count | success rate | avg steps | run dir |
| --- | ---: | ---: | ---: | --- |
| `softmax_strong_weak_renoise` | 6/10 | 60.00% | 176.5 | `outputs/rdt_eds_mechanism_pretest/hydra_ablate_softmax_strong_weak_renoise_10ep` |
| `cem_weak_renoise` | 4/10 | 40.00% | 197.3 | `outputs/rdt_eds_mechanism_pretest/hydra_ablate_cem_weak_renoise_10ep_retry` |

### Per-Episode Results

| run | ep1 | ep2 | ep3 | ep4 | ep5 | ep6 | ep7 | ep8 | ep9 | ep10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `softmax_strong_weak_renoise` | S/120 | F/240 | S/118 | F/240 | F/240 | S/201 | S/128 | S/117 | F/240 | S/121 |
| `cem_weak_renoise` | S/120 | F/240 | F/240 | S/111 | F/240 | F/240 | S/126 | S/176 | F/240 | F/240 |

### Video Paths

`softmax_strong_weak_renoise` videos:

- `outputs/rdt_eds_mechanism_pretest/hydra_ablate_softmax_strong_weak_renoise_10ep/episode_1/episode_1_success_agentview.mp4`
- `outputs/rdt_eds_mechanism_pretest/hydra_ablate_softmax_strong_weak_renoise_10ep/episode_2/episode_2_fail_agentview.mp4`
- `outputs/rdt_eds_mechanism_pretest/hydra_ablate_softmax_strong_weak_renoise_10ep/episode_3/episode_3_success_agentview.mp4`
- `outputs/rdt_eds_mechanism_pretest/hydra_ablate_softmax_strong_weak_renoise_10ep/episode_4/episode_4_fail_agentview.mp4`
- `outputs/rdt_eds_mechanism_pretest/hydra_ablate_softmax_strong_weak_renoise_10ep/episode_5/episode_5_fail_agentview.mp4`
- `outputs/rdt_eds_mechanism_pretest/hydra_ablate_softmax_strong_weak_renoise_10ep/episode_6/episode_6_success_agentview.mp4`
- `outputs/rdt_eds_mechanism_pretest/hydra_ablate_softmax_strong_weak_renoise_10ep/episode_7/episode_7_success_agentview.mp4`
- `outputs/rdt_eds_mechanism_pretest/hydra_ablate_softmax_strong_weak_renoise_10ep/episode_8/episode_8_success_agentview.mp4`
- `outputs/rdt_eds_mechanism_pretest/hydra_ablate_softmax_strong_weak_renoise_10ep/episode_9/episode_9_fail_agentview.mp4`
- `outputs/rdt_eds_mechanism_pretest/hydra_ablate_softmax_strong_weak_renoise_10ep/episode_10/episode_10_success_agentview.mp4`

`cem_weak_renoise` retry videos:

- `outputs/rdt_eds_mechanism_pretest/hydra_ablate_cem_weak_renoise_10ep_retry/episode_1/episode_1_success_agentview.mp4`
- `outputs/rdt_eds_mechanism_pretest/hydra_ablate_cem_weak_renoise_10ep_retry/episode_2/episode_2_fail_agentview.mp4`
- `outputs/rdt_eds_mechanism_pretest/hydra_ablate_cem_weak_renoise_10ep_retry/episode_3/episode_3_fail_agentview.mp4`
- `outputs/rdt_eds_mechanism_pretest/hydra_ablate_cem_weak_renoise_10ep_retry/episode_4/episode_4_success_agentview.mp4`
- `outputs/rdt_eds_mechanism_pretest/hydra_ablate_cem_weak_renoise_10ep_retry/episode_5/episode_5_fail_agentview.mp4`
- `outputs/rdt_eds_mechanism_pretest/hydra_ablate_cem_weak_renoise_10ep_retry/episode_6/episode_6_fail_agentview.mp4`
- `outputs/rdt_eds_mechanism_pretest/hydra_ablate_cem_weak_renoise_10ep_retry/episode_7/episode_7_success_agentview.mp4`
- `outputs/rdt_eds_mechanism_pretest/hydra_ablate_cem_weak_renoise_10ep_retry/episode_8/episode_8_success_agentview.mp4`
- `outputs/rdt_eds_mechanism_pretest/hydra_ablate_cem_weak_renoise_10ep_retry/episode_9/episode_9_fail_agentview.mp4`
- `outputs/rdt_eds_mechanism_pretest/hydra_ablate_cem_weak_renoise_10ep_retry/episode_10/episode_10_fail_agentview.mp4`

## Comparison To Prior Ablations

Prior 1-episode mechanism pretest outcomes:

| prior run | 1ep success | key mechanism signal |
| --- | --- | --- |
| `resample_only` | fail, 240 steps | no denoising refinement; reward/distance degraded |
| `weak_renoise` | fail, 240 steps | weaker perturbation but still failed; diversity collapsed |
| `softmax_strong` | success, 119 steps | normal renoise with stronger softmax succeeded |
| `cem_resample` | success, 121 steps | strongest parent selection; normal renoise succeeded |
| `negative_reward` | fail, 240 steps | no evidence of reward/cost sign error |

New 1-episode pretests both failed at 240 steps despite better first-chunk reward/distance trends. This is the key tension: weak renoise can make the first-chunk full-process metrics look smoother, but it did not improve real episode success in these two combination runs.

Available prior 10-episode references found in the workspace:

| baseline | result | path |
| --- | ---: | --- |
| unguided RDT formal 10ep | 9/10, 90.00% | `outputs/formal_unguided_10_20260606_124553/results.txt` |
| RDT+EDS level3 p16_c10 | 6/10, 60.00% | `outputs/rdt_eds_eval/level3_libero_object_p16_c10/results.txt` |
| RDT+EDS level3 p32_c10_cem | 7/10, 70.00% | `outputs/rdt_eds_eval/level3_libero_object_p32_c10_cem/results.txt` |

The new `softmax_strong_weak_renoise` 10ep result matches the prior p16_c10 EDS 60% result, but remains below unguided RDT. The new `cem_weak_renoise` retry reaches 40%, below both prior p32 CEM and unguided RDT.

## Conclusions

1. Strong softmax + weak renoise is not better than strong softmax alone in this evidence set. The single 1ep pretest failed at 240 steps, while prior strong softmax 1ep succeeded in 119 steps. Its 10ep success rate is 60%, below unguided RDT's 90%.

2. CEM + weak renoise is not better than CEM with normal renoise. First-chunk selection pressure is strong and reward/distance metrics improve, but 1ep failed and retry 10ep success is 40%. Prior CEM-related 10ep evidence available in `level3_libero_object_p32_c10_cem` is 70%.

3. Weak renoise appears to improve local first-chunk metric smoothness but likely weakens exploration. Both weak-renoise variants show large diversity collapse. The first chunk can look more converged while the full task success rate does not improve.

4. Stronger selection and weaker renoise are not clearly complementary here. CEM+weak produces the cleanest first-chunk selection and convergence metrics, but the lower 10ep success rate suggests over-concentration or insufficient exploration.

5. Current recommendation: do not adopt weak renoise as the default. If continuing EDS, prioritize normal renoise with stronger but not overly collapsing selection, and evaluate against unguided RDT because the best baseline found here is still 90% unguided success.

## Verification Notes

- Mechanism pretest structure checked: both new directories have 36 files, matching the reference structure.
- `softmax_strong_weak_renoise_10ep`: 10/10 episode videos produced, no preparation errors detected.
- `cem_weak_renoise_10ep_retry`: 10/10 episode videos produced, no preparation errors detected.
- `cem_weak_renoise_10ep` attempt1 is retained for provenance but excluded from final 10ep comparison because episodes 5-8 were skipped due to external VLM API preparation timeouts.
