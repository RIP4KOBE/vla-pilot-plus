# RDT+EDS Level 4 LIBERO-PRO OOD Evaluation

Timestamp: `2026-06-20T13:02:47+00:00`

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
| `libero_object_task` | `eds_softmax_strong_weak_renoise` | `True` | 0/10 | 0.00 | 15.277 | 15.151 | 10 | 155 | 880 |
| `libero_object_task` | `eds_cem_resample_weak_renoise` | `True` | 0/10 | 0.00 | 12.347 | 12.243 | 10 | 192 | 880 |
| `libero_object_env` | `unguided` | `True` | 0/10 | 0.00 | - | - | 10 | 0 | 0 |
| `libero_object_env` | `eds_softmax_strong_weak_renoise` | `True` | 1/10 | 10.00 | 7.213 | 7.142 | 10 | 238 | 880 |
| `libero_object_env` | `eds_cem_resample_weak_renoise` | `True` | 1/10 | 10.00 | 6.076 | 6.010 | 10 | 206 | 880 |
| `libero_object_temp` | `unguided` | `True` | 0/10 | 0.00 | - | - | 10 | 0 | 0 |
| `libero_object_temp` | `eds_softmax_strong_weak_renoise` | `True` | 0/10 | 0.00 | 6.111 | 6.045 | 10 | 220 | 880 |
| `libero_object_temp` | `eds_cem_resample_weak_renoise` | `True` | 0/10 | 0.00 | 6.036 | 5.973 | 10 | 190 | 880 |

## Perturbation Interpretation

All Level 4 jobs use the `libero_object` base task family, whose original tasks are grocery-object pick-and-place tasks into a basket. The six LIBERO-PRO suites change different parts of the same base task distribution:

| Suite | Perturbation type | What is OOD | Observed result |
| --- | --- | --- | --- |
| `libero_object_object` | Object replacement | Object instance or visual appearance is changed while the task language is kept aligned with the original semantic object. | Unguided remains strongest at 60%; CEM is close at 50%; softmax drops to 30%. |
| `libero_object_swap` | Initial object position swap | Target and distractor initial positions are swapped. This stresses spatial priors and target localization. | All methods are 0%; EDS local steering does not recover from the wrong spatial prior. |
| `libero_object_lan` | Language paraphrase | The physical task and goal are unchanged, but instruction wording changes. | EDS is strongest here: both softmax and CEM improve from 30% to 60%. |
| `libero_object_task` | Task and goal remap | Language, goal, and object of interest are changed. This requires correct semantic rebinding to a new target. | All methods are 0%; EDS is not enough to repair semantic-goal mismatch. |
| `libero_object_env` | Environment surface replacement | The original `floor` surface is replaced by the configured environment surface, observed as `living_room_table` in this run. | EDS gives a small gain from 0% to 10%. |
| `libero_object_temp` | Temp-generated perturbation under current config | In this run, temp uses the enabled perturbation config, which is environment replacement only. Its BDDL semantics are environment-style, but generated init states differ. | All methods are 0%; this appears harder than the `env` init set. |

Implementation notes: `_parse_perturbation_type()` maps suite suffixes to LIBERO-PRO flags in `core/env_adapters/libero_adapter.py`; `_temp` sets `is_temp=True`, then `_apply_perturbations()` reads the active flags from `third_party/libero_pro/evaluation_config.yaml`. For this Level 4 run, `evaluation_config.yaml` enables `use_environment: true` and leaves `use_swap`, `use_object`, `use_language`, and `use_task` false. Therefore `libero_object_temp` should not be read as a multi-perturbation mixture in this run; it is an environment-style temp generation with a different initialization set.

Detailed perturbation analysis:

### `libero_object_object`: object replacement OOD

`object` replacement changes BDDL object identities and container variants while keeping the language block aligned with the original semantic task. A representative transformation is:

```text
Original language:
Pick the alphabet soup and place it in the basket

Perturbed object symbols:
alphabet_soup_1 -> bigger_alphabet_soup_1
basket_1 -> red_basket_1

Perturbed goal:
place bigger_alphabet_soup_1 into red_basket_1
```

This is primarily visual object and instance-level OOD, not language OOD. The result is:

- Unguided RDT: 60%
- EDS softmax: 30%
- EDS CEM: 50%

Interpretation: RDT already has some robustness to this object replacement distribution. EDS can be harmful here because VLM/keypoint reward may identify a plausible target, but the action distribution can be pulled away from RDT's learned grasp trajectory manifold. CEM is less harmful than softmax, which suggests hard elite selection is more stable than broad softmax population weighting for this suite.

### `libero_object_swap`: spatial initial-state OOD

`swap` keeps the language, goal, and object categories unchanged, but swaps target-object and distractor-object initial locations. A representative transformation is:

```text
Original:
alphabet_soup_1 On floor_target_object_region

Perturbed:
alphabet_soup_1 On floor_other_object_region_1
cream_cheese_1 On floor_target_object_region
```

This directly attacks the learned spatial prior. The result is:

- Unguided RDT: 0%
- EDS softmax: 0%
- EDS CEM: 0%

Interpretation: RDT appears to rely heavily on canonical initial layout priors for `libero_object`. The policy can behave as if the target remains in the usual target region instead of fully localizing the language-specified object from the current scene. Current EDS does not recover because it only reranks and steers candidate actions near the sampled RDT action manifold; it does not globally relocalize the target and replan from a broken spatial prior.

### `libero_object_lan`: language paraphrase OOD

`lan` changes only the `(:language ...)` field. BDDL goals, objects, object of interest, and initial positions are unchanged. A representative transformation is:

```text
Original:
Pick the alphabet soup and place it in the basket

Perturbed:
grab alphabet soup and put it into basket
```

The result is:

- Unguided RDT: 30%
- EDS softmax: 60%
- EDS CEM: 60%

Interpretation: this is the clearest positive EDS result. The physical task is unchanged, but RDT unguided loses performance under paraphrased language. EDS uses VLM-derived keypoints and reward during action sampling, which can partially compensate for language embedding shift. Since the target object and scene are unchanged, action-level steering is enough to recover some failures.

### `libero_object_task`: task-goal remapping OOD

`task` is the strongest semantic perturbation. It changes:

- language
- goal predicate
- object of interest

A representative transformation is:

```text
Original task:
Pick the alphabet soup and place it in the basket

Perturbed task:
Pick the cream cheese and place it in the basket

Original goal:
In alphabet_soup_1 basket_1_contain_region

Perturbed goal:
In cream_cheese_1 basket_1_contain_region
```

The result is:

- Unguided RDT: 0%
- EDS softmax: 0%
- EDS CEM: 0%

Interpretation: this is not a paraphrase. It remaps the actual target object and task semantics. RDT likely remains biased by the original task distribution or original object prior. EDS may know a new keypoint, but it is still constrained by the sampled RDT action prior and cannot reliably synthesize a full new object-selection and manipulation sequence. This confirms that current EDS is not a task planner.

### `libero_object_env`: environment and layout OOD

`env` replaces the support environment or scene region. For `libero_object`, the original surface is configured as `floor`; in this run the environment perturbation maps it to a table-style support surface, observed as `living_room_table` in the generated BDDL.

A representative transformation is:

```text
Original:
alphabet_soup_1 On floor_target_object_region

Perturbed:
alphabet_soup_1 On living_room_table_target_object_region
```

The result is:

- Unguided RDT: 0%
- EDS softmax: 10%
- EDS CEM: 10%

Interpretation: this is geometry and scene-distribution OOD. The support surface, object height, region names, camera geometry, and initialization distribution can all shift relative to the original policy training distribution. Unguided RDT fails completely, while EDS gets 1/10. This is weak but real evidence that action-level steering can help in a small subset of environment-shift cases. The bottleneck is still that RDT's action prior is adapted to the original scene distribution, and EDS mostly selects among nearby sampled trajectories rather than producing a large geometric strategy change.

### `libero_object_temp`: temp under current config

`temp` should be interpreted carefully. In this code path, `_temp` does not automatically mean object + language + task + swap + environment. It reads the active flags from `third_party/libero_pro/evaluation_config.yaml`. In this run, only:

```yaml
use_environment: true
use_swap: false
use_object: false
use_language: false
use_task: false
```

is enabled. Therefore `libero_object_temp` is best interpreted as environment-style perturbation under a temp-generation path, not a combined perturbation suite. The key difference from `libero_object_env` is the generated initialization set.

The result is:

- Unguided RDT: 0%
- EDS softmax: 0%
- EDS CEM: 0%

Interpretation: `temp` is not harder here because it combines object, language, task, swap, and environment perturbations. It is harder because the sampled initialization states under the environment-style perturbation appear more difficult in this 10-episode run. The contrast between `env` at 1/10 for EDS and `temp` at 0/10 shows that init-state variation alone can determine success in this small-sample OOD evaluation.

Core perturbation conclusion: EDS is most useful when the physical task remains inside RDT's reachable action manifold and the OOD shift mainly affects language (`lan`) or mild environment geometry (`env`). It is not enough for target relocation (`swap`) or semantic task remapping (`task`). On `object`, EDS is unstable because it can disturb RDT's existing object-level generalization. Current EDS is best understood as reward-biased action selection around RDT's sampled trajectory manifold, not as a planner or a complete OOD task solver.

## Latency And Runtime Analysis

EDS is substantially slower than unguided RDT. The per-guided-chunk latency comes from scoring a population of 32 action trajectories over 20 EDS/CEM iterations, with resampling, renoise, and rollout at each iteration.

| Suite | Softmax mean EDS latency s | CEM mean EDS latency s |
| --- | ---: | ---: |
| `libero_object_object` | 5.991 | 6.191 |
| `libero_object_swap` | 6.003 | 6.016 |
| `libero_object_lan` | 9.307 | 5.983 |
| `libero_object_task` | 15.151 | 12.243 |
| `libero_object_env` | 7.142 | 6.010 |
| `libero_object_temp` | 6.045 | 5.973 |

Reconstructing job wall-clock from each Level 4 log's `START` and `END` timestamps gives:

| Method | Jobs | Mean wall-clock per 10-episode job | Min | Max |
| --- | ---: | ---: | ---: | ---: |
| `unguided` | 6 | 4.4 min | 3.4 min | 5.6 min |
| `eds_softmax_strong_weak_renoise` | 6 | 44.4 min | 26.4 min | 62.7 min |
| `eds_cem_resample_weak_renoise` | 6 | 45.3 min | 24.6 min | 69.8 min |

The effective runtime overhead is therefore about 10x versus unguided RDT. Jobs with more failed episodes are slower because failed episodes usually run to the 240-step timeout.

## EDS Loop Execution Evidence

The counters prove that the EDS path was actually entered and did not silently fall back to unguided denoising.

| Method | Metrics records | Counter records passing |
| --- | ---: | ---: |
| `eds_softmax_strong_weak_renoise` | 1111 | 1111/1111 |
| `eds_cem_resample_weak_renoise` | 1005 | 1005/1005 |

For every EDS metrics record, the following invariants held:

- `eds_enter_count=1`
- `population_shape=[32,64,128]`
- `resample_count=20`
- `renoise_count=20`
- `rollout_count=20`
- `score_call_count=21`
- `nonfinite_count=0`

This is the key deployment-correctness result: the implemented EDS loop executed score, resample, renoise, rollout, and final selection for every recorded guided chunk.

## Reward And Progress Evidence

The mechanism evidence is mixed. CEM shows consistent local optimization signals; softmax does not.

| Method | Records | `final_best_reward > initial_best_reward` | `final_mean_reward > initial_mean_reward` | `target_distance_after < target_distance_before` | Mean delta best reward | Mean delta target distance | Diversity initial -> final | Mean unique parent ratio |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| `eds_softmax_strong_weak_renoise` | 1111 | 15.2% | 23.0% | 36.4% | -0.000524 | +0.001400 | 4.651 -> 3.271 | 0.637 |
| `eds_cem_resample_weak_renoise` | 1005 | 47.3% | 51.7% | 61.4% | +0.000942 | -0.002378 | 4.885 -> 1.353 | 0.246 |

Per-suite CEM progress is strongest on `env` and `swap` in terms of reward/distance, even though only `env` produces nonzero task success:

| Suite | Method | Reward-improved chunks | Distance-improved chunks | Mean delta best reward | Mean delta target distance |
| --- | --- | ---: | ---: | ---: | ---: |
| `libero_object_env` | CEM | 63.1% | 70.4% | +0.001232 | -0.003930 |
| `libero_object_swap` | CEM | 64.3% | 73.4% | +0.001584 | -0.003951 |
| `libero_object_lan` | CEM | 27.4% | 63.0% | +0.000422 | -0.002755 |
| `libero_object_object` | CEM | 35.2% | 53.1% | +0.000498 | -0.001646 |
| `libero_object_task` | CEM | 42.7% | 44.3% | +0.001141 | +0.000661 |
| `libero_object_temp` | CEM | 43.2% | 63.7% | +0.000575 | -0.002716 |

This means CEM-style EDS is producing measurable local steering, but local reward/progress does not always convert to environment-level success. The mismatch is clearest on `swap`, `task`, and `temp`: the EDS loop can move trajectories toward the immediate keypoint or reward proxy, but the episode still times out because the higher-level object/goal/spatial binding is wrong or the local reward does not capture the full manipulation objective.

Softmax has weak optimization pressure. Its score entropy is close to the maximum entropy of a 32-particle distribution, and its mean unique parent ratio is high. In practice this behaves closer to broad population perturbation than focused optimization.

## Qualitative Evidence

Each EDS job saved keypoint overlays, selected EEF trajectory overlays, population clouds, per-iteration best trajectory overlays, and initial-best-vs-final-selected comparisons. The final report uses the counts in the success table as a completeness check; every EDS job has 880 qualitative PNGs.

Representative artifacts:

- CEM env selected-vs-initial trajectory: `outputs/rdt_eds_eval/level4_libero_object_env_eds_cem_resample_weak_renoise/eds_eval/qualitative/episode_001/chunk_000000/initial_best_vs_final_selected.png`
- CEM env final population cloud: `outputs/rdt_eds_eval/level4_libero_object_env_eds_cem_resample_weak_renoise/eds_eval/qualitative/episode_001/chunk_000000/population_overlay_iter_last.png`
- Softmax env selected-vs-initial trajectory: `outputs/rdt_eds_eval/level4_libero_object_env_eds_softmax_strong_weak_renoise/eds_eval/qualitative/episode_001/chunk_000000/initial_best_vs_final_selected.png`
- Softmax env final population cloud: `outputs/rdt_eds_eval/level4_libero_object_env_eds_softmax_strong_weak_renoise/eds_eval/qualitative/episode_001/chunk_000000/population_overlay_iter_last.png`

The sampled CEM env artifacts show visible trajectory change between initial best and final selected trajectories, and the final population cloud is visibly more concentrated. This matches the quantitative CEM diversity collapse from about 4.885 to 1.353. The sampled softmax artifacts show much smaller initial-to-final change and weaker concentration, matching the weaker quantitative progress.

## Failure Taxonomy

Most Level 4 failures are policy/task failures, not infrastructure failures. All failed episodes in these Level 4 logs ran to the 240-step timeout. Successful episodes terminate earlier.

| Failure class | Affected suites | Evidence | Interpretation |
| --- | --- | --- | --- |
| Local steering improves proxy but not task success | `swap`, `task`, `temp` | CEM has positive reward/progress in many chunks, but SR stays 0%. | The keypoint/reward proxy is too local for these OOD shifts. |
| Spatial prior failure | `swap` | All methods 0%, all failed episodes timeout. | Swapped target/distractor positions require robust target localization, not just local action reranking. |
| Semantic-goal rebinding failure | `task` | All methods 0%, all failed episodes timeout. | EDS is not a planner and does not rebind task language, object of interest, and goal predicates by itself. |
| Environment/init distribution difficulty | `env`, `temp` | `env` gets 1/10 with EDS; `temp` remains 0/10 despite same environment-style perturbation family. | Certain generated init states are beyond current action-level steering. |
| Off-manifold steering | `object` | Unguided 60%, softmax 30%, CEM 50%. | RDT already has useful object-OOD robustness, and EDS can perturb otherwise successful action chunks. |
| Weak softmax selection pressure | All softmax EDS jobs | Low reward improvement rates and high unique parent ratio. | Reward spread is too small, so softmax sampling is close to uniform resampling. |

## Level 4 Gate Assessment

| Gate | Criterion | Result |
| --- | --- | --- |
| Minimum | EDS normal/ablation SR is nonzero, or EDS has progress improvement over unguided/ablation. | Passed. Softmax has nonzero SR; CEM has nonzero SR and stronger progress evidence. |
| Target | EDS is better than unguided RDT on at least one OOD perturbation suite. | Passed. Both EDS variants improve `lan` from 30% to 60% and `env` from 0% to 10%. |
| Strong | EDS improves over unguided on multiple perturbation suites, with consistent reward/progress/qualitative evidence. | Partially passed, but not strict. CEM improves multiple suites and has strong progress evidence, but object-OOD regresses and several suites remain 0%. Softmax does not have consistent reward/progress evidence. |

## Final Conclusions

Deployment correctness is verified. The EDS loop is entered, all required counters match `cem_iters=20`, all score tensors are finite, and every EDS job produced metrics and qualitative artifacts.

`eds_cem_resample_weak_renoise` is the better of the two ablations. It has the best aggregate Level 4 SR (`12/60`), ties softmax on `lan` (`6/10`), ties softmax on `env` (`1/10`), is less harmful on `object` (`5/10` vs softmax `3/10`), and has much stronger reward/progress and population-concentration evidence.

`eds_softmax_strong_weak_renoise` is deployed correctly but is not a convincing steering mechanism in this configuration. It improves SR on `lan` and `env`, but its reward/progress statistics are weak or negative on average, suggesting that the softmax weights are too flat to reliably select better particles.

EDS is worth continuing, but the next optimization should focus on the CEM variant. The main technical priorities are:

- Increase reward contrast so particle ranking is less noisy.
- Improve keypoint and EEF reward alignment under OOD geometry and object replacements.
- Add safeguards against steering away from high-confidence RDT actions, especially for `object` OOD where unguided RDT is already strong.
- Add higher-level target or stage validation for `swap` and `task`, because action-level local steering cannot reliably repair global target-binding errors.
- Reduce runtime, because Level 4 EDS currently costs roughly 10x wall-clock versus unguided RDT.

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
