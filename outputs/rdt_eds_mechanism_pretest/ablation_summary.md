# RDT+EDS Mechanism Ablation Summary

Date: 2026-06-16

All five ablations were run on real `libero_object` task 1, one episode, first action chunk trace only, `population_size=16`, `cem_iters=10`. Reward is interpreted as larger-is-better; EDS converts reward to cost internally as `cost = -reward`.

## Artifact Check

| run | files | matches reference | episode success | steps | reward_mode | scoring keypoint |
| --- | ---: | --- | --- | ---: | --- | --- |
| `resample_only` | 36 | yes | false | 240 | `normal` | `[0]` |
| `weak_renoise` | 36 | yes | false | 240 | `normal` | `[0]` |
| `softmax_strong` | 36 | yes | true | 119 | `normal` | `[0]` |
| `cem_resample` | 36 | yes | true | 121 | `normal` | `[0]` |
| `negative_reward` | 36 | yes | false | 240 | `inverted` | `[0]` |

## Single-Step Inner-Loop Metrics

| run | initial best reward | resampled mean parent rank | top-4 parent fraction | unique parents | mean renoise delta | rollout mean reward delta | after-rollout best reward | after-rollout best distance |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `resample_only` | -0.094727 | 9.750 | 0.062 | 12 | 0.000000 | 0.000000 | -0.094727 | 0.297108 |
| `weak_renoise` | -0.094727 | 9.750 | 0.062 | 12 | 24.773438 | 0.003448 | -0.098145 | 0.303264 |
| `softmax_strong` | -0.094727 | 9.750 | 0.062 | 12 | 91.093750 | 0.002563 | -0.097168 | 0.300007 |
| `cem_resample` | -0.094727 | 2.375 | 1.000 | 4 | 91.125000 | -0.003113 | -0.097168 | 0.300024 |
| `negative_reward` | 0.109863 | 7.312 | 0.312 | 12 | 91.093750 | -0.002563 | 0.107910 | 0.324468 |

## Full-Process Trend

| run | iter0 best reward | iter9 best reward | delta reward | iter0 distance | iter9 distance | delta distance | iter0 diversity | iter9 diversity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `resample_only` | -0.094727 | -0.100586 | -0.005859 | 0.297108 | 0.308226 | 0.011118 | 0.032421 | 0.031441 |
| `weak_renoise` | -0.098145 | -0.096680 | 0.001465 | 0.303264 | 0.300526 | -0.002738 | 0.018431 | 0.007543 |
| `softmax_strong` | -0.097168 | -0.097168 | 0.000000 | 0.300007 | 0.300905 | 0.000898 | 0.028770 | 0.018027 |
| `cem_resample` | -0.097168 | -0.094727 | 0.002441 | 0.300024 | 0.297174 | -0.002850 | 0.028799 | 0.014099 |
| `negative_reward` | 0.107910 | 0.103516 | -0.004395 | 0.324468 | 0.314384 | -0.010084 | 0.028770 | 0.018027 |

## Readout

- `resample_only` preserved artifact structure but did not solve the task; as intended, renoise and rollout deltas are zero/empty diagnostics, and the full-process reward/distance trend is flat-to-marginal because there is no denoising refinement.
- `weak_renoise` reduced mean renoise delta relative to normal-strength diagnostic runs, but this single episode still failed at 240 steps; rollout slightly reduced reward in the first inner loop.
- `softmax_strong` succeeded in 119 steps. Its first-step parent selection remained weak in this seed because normal reward differences are very small; the success signal mainly appears in full episode outcome, not a dramatic first-loop parent-rank shift.
- `cem_resample` succeeded in 121 steps and shows the clearest resampling pressure: top-4 parent fraction is 1.0 and unique parents collapse to the elite set.
- `negative_reward` failed at 240 steps and selected parents according to the inverted objective, supporting that the normal reward/cost sign is not simply flipped.

Primary artifact directories:
- `outputs/rdt_eds_mechanism_pretest/libero_object_task1_seed000_ablate_resample_only_p16_c10`
- `outputs/rdt_eds_mechanism_pretest/libero_object_task1_seed000_ablate_weak_renoise_p16_c10`
- `outputs/rdt_eds_mechanism_pretest/libero_object_task1_seed000_ablate_softmax_strong_p16_c10`
- `outputs/rdt_eds_mechanism_pretest/libero_object_task1_seed000_ablate_cem_resample_p16_c10`
- `outputs/rdt_eds_mechanism_pretest/libero_object_task1_seed000_ablate_negative_reward_p16_c10`
