# EDS RBF-Diverse Initial Sampling Mechanism Pretest and Parameter Sweep Report

## Scope

This report analyzes the experiment artifacts under:

- `outputs/rdt_eds_mechanism_pretest_rbf`
- `outputs/rdt_eds_eval`

The focus is the `rbf_diverse_denoise` initial sampler for EDS on the branch `exp/eds-init-pg-diverse-sampling`. The report separates three questions:

1. Did the RBF-diverse initial sampler actually run?
2. Did it measurably change the initial population?
3. Why did the downstream EDS behavior look almost identical to naive iid initialization?

## Executive Summary

The RBF-diverse initial sampler is operational. In the valid mechanism pretest run, it used `initial_sampling_mode=rbf_diverse_denoise`, applied `1` diversity step, recorded normalized diversity gradient norms, produced no fallback, and generated trace artifacts.

However, the effect is not preserved strongly enough to change downstream EDS behavior. The mechanism trace shows that RBF modifies the early partially denoised particles, but the remaining RDT denoising steps contract the population back onto a narrow policy mode. In the first mechanism chunk, trajectory-space diversity changes from `0.12408` before RBF to `0.12501` after the RBF phase, then collapses to `0.03706` at the final initial population.

The parameter sweep confirms this. Compared with iid EDS, `scale=0.5`, `scale=1.0`, and `start_ratio=0.25` produce almost the same selected rewards, final target distances, selected particle indices, and final qualitative overlays. For `scale=1.0`, selected reward is identical to iid on `28/30` chunks, target distance is identical on `27/30` chunks, and selected index is identical on `30/30` chunks.

The core diagnosis is: RBF is active, but it is too early, too weak, and too easily erased by the RDT prior and by EDS resample-renoise-rollout. At the same time, the EDS reward landscape has very low selection pressure: score entropy is approximately `ln(16)=2.772589`, meaning resampling is nearly uniform over the 16 particles. This prevents small diversity changes from being amplified into different selected actions.

## Experiment Inventory

### Mechanism Pretest

Valid completed run:

- Output root: `outputs/rdt_eds_mechanism_pretest_rbf`
- Valid Hydra run: `outputs/rdt_eds_mechanism_pretest_rbf/hydra_cached_no_proxy`
- Mechanism trace: `outputs/rdt_eds_mechanism_pretest_rbf/libero_object_task1_seed000_normal_p16_c10`
- Task: `libero_object`, `task_id=1`
- Episode count: `1`
- Result: `1/1`, success rate `100.00%`
- Guidance cache: cached VLM output from `outputs/libero/2026-06-04_13-21-01/episode_2/vlm_agent`
- Online VLM disabled: `main.use_vlm_stage_recognition=false`, `perception.gemini_grounding.enabled=false`
- `OPENAI_API_KEY=dummy` was used only to allow the client stack to initialize; reward functions came from the cached guidance directory.

Other directories under `outputs/rdt_eds_mechanism_pretest_rbf` such as `hydra_normal`, `hydra_cached`, and `hydra_cached_dummy_key` contain earlier Hydra attempts with configs/logs but no `results.txt`. The complete evidence should be taken from `hydra_cached_no_proxy` plus the `libero_object_task1_seed000_normal_p16_c10` mechanism trace directory.

### Parameter Sweep

Parameter sweep runs are under `outputs/rdt_eds_eval`.

Task setting:

- Suite: `libero_object`
- Task filter: `backend.libero.task_ids_filter=[0]`
- Task: pick up the alphabet soup and place it in the basket
- Episode count per run: `1`
- EDS population: `16`
- EDS iterations: `10`
- `use_cem=false`
- `num_elites=32`
- `temperature=0.1`
- `renoise_t_max=5`, `renoise_t_min=1`
- Offline cached guidance: `outputs/libero/2026-06-04_13-21-01/episode_1/vlm_agent`

The RBF sweep changed only:

- `main.eds_config.initial_sampling_mode=rbf_diverse_denoise`
- `main.eds_config.initial_diversity_scale`
- `main.eds_config.initial_diversity_start_ratio`

## Mechanism Pretest Results

### Initial Sampler Metadata

From `first_chunk_metadata.json`:

| Field | Value |
|---|---:|
| `initial_sampling_mode` | `rbf_diverse_denoise` |
| `initial_diversity_scale` | `1.0` |
| `initial_diversity_start_ratio` | `null` |
| `initial_diversity_steps` | `1` |
| `initial_diversity_grad_norm_mean` | `1.0` |
| `initial_diversity_grad_norm_max` | `1.0` |
| `initial_diversity_grad_failure_count` | `0` |
| `initial_diversity_fallback_used` | `false` |
| `initial_diversity_fallback_reason` | `null` |
| `initial_sampler_latency_s` | `0.5991879049688578` |

This establishes that the RBF path was active and did not silently fall back to iid.

### Stage-Level Mechanism Trace

The trace tensor was loaded from:

`outputs/rdt_eds_mechanism_pretest_rbf/libero_object_task1_seed000_normal_p16_c10/tensors/mechanism_trace.pt`

Key stage metrics:

| Stage | Action Norm | Traj Diversity | Endpoint Spread | Mean Traj Length | Best Reward | Mean Reward |
|---|---:|---:|---:|---:|---:|---:|
| `initial_before_diversity` | `84.780312` | `0.124081708` | `0.063339204` | `0.097066879` | `-0.096191406` | `-0.116363525` |
| `initial_after_diversity_phase` | `81.623283` | `0.125005752` | `0.064582005` | `0.093981981` | `-0.093261719` | `-0.113372803` |
| `initial_final` | `40.421871` | `0.037056711` | `0.022208283` | `0.033542752` | `-0.094726562` | `-0.102386475` |
| `resampled` | `40.372238` | `0.033054415` | `0.020139690` | `0.031479936` | `-0.094726562` | `-0.103240967` |
| `renoised` | `362.233948` | `0.112976998` | `0.056770064` | `0.098512262` | `-0.095214844` | `-0.109039307` |
| `after_rollout` | `40.044342` | `0.028679999` | `0.016227312` | `0.038961027` | `-0.097167969` | `-0.100738525` |
| final iter `9` | `41.180096` | `0.017955270` | `0.009909418` | `0.042431820` | `-0.097167969` | `-0.099334717` |

Important stage deltas:

| Transition | Action L2 Delta | Action Mean Abs Delta | Traj L2 Delta | Traj Mean Abs Delta |
|---|---:|---:|---:|---:|
| `initial_before_diversity -> initial_after_diversity_phase` | `11.567424` | `0.005253321` | `0.063842` | `0.002284300` |
| `initial_after_diversity_phase -> initial_final` | `84.014771` | `0.043260086` | `0.364244` | `0.015357806` |
| `initial_before_diversity -> initial_final` | `91.633583` | `0.047131933` | `0.404642` | `0.016925102` |
| `initial_final -> after_rollout` | `23.910885` | `0.005134723` | `0.133392` | `0.004481792` |

### Mechanism Interpretation

The RBF phase changes the early denoising state, but most of the change is overwritten by subsequent RDT denoising. This is visible in both the tensor statistics and the 3D plots:

- `initial_before_diversity_3d.png` and `initial_after_diversity_phase_3d.png` are close but not identical.
- `initial_final_3d.png` is much more compact than both early plots.
- `diversity_curve.png` decreases over EDS iterations, from about `0.029-0.031` early to about `0.018` by iteration `9`.

This means the mechanism pretest passes as a wiring test, but it does not prove that RBF diversity survives into final action selection.

## Parameter Sweep Results

### Run Summary

| Run | Records | Success | Mode | Scale | Start Ratio | Diversity Steps | Fallback | Init Latency | Select Latency | Init Diversity | Final Diversity | Initial Best Reward | Selected Reward | Target Distance After |
|---|---:|---:|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `level2_libero_object_p16_c10` | 30 | `0/1` | `iid` | `1.0` | `null` | `0:30` | 0 | `0.370940` | `2.715316` | `5.840201` | `3.693156` | `-0.011359` | `-0.012529` | `0.095691` |
| `level2_libero_object_eds_rbf_scale05` | 30 | `0/1` | `rbf_diverse_denoise` | `0.5` | `null` | `1:30` | 0 | `0.427454` | `2.735044` | `5.957725` | `3.694549` | `-0.011357` | `-0.012539` | `0.095846` |
| `level2_libero_object_eds_rbf_diverse_initial` | 30 | `0/1` | `rbf_diverse_denoise` | `1.0` | `null` | `1:30` | 0 | `0.426961` | `2.729208` | `5.960670` | `3.694549` | `-0.011341` | `-0.012539` | `0.095846` |
| `level2_libero_object_eds_rbf_scale2` | 30 | `0/1` | `rbf_diverse_denoise` | `2.0` | `null` | `1:30` | 0 | `0.431605` | `2.763544` | `5.956101` | `3.542112` | `-0.011891` | `-0.012940` | `0.097091` |
| `level2_libero_object_eds_rbf_start025` | 30 | `0/1` | `rbf_diverse_denoise` | `1.0` | `0.25` | `1:30` | 0 | `0.427613` | `2.746917` | `5.960670` | `3.694549` | `-0.011341` | `-0.012539` | `0.095846` |
| `level2_libero_object_eds_rbf_start05` | 30 | `0/1` | `rbf_diverse_denoise` | `1.0` | `0.5` | `2:30` | 0 | `0.442669` | `2.762723` | `5.165898` | `3.715309` | `-0.011805` | `-0.012596` | `0.096163` |

Additional controls:

| Run | Records | Success | Mode | Notes |
|---|---:|---:|---|---|
| `level2_libero_object_unguided` | n/a | `1/1` | unguided RDT | No EDS metrics JSONL |
| `level2_libero_object_zero` | 15 | `1/1` | EDS iid, zero reward | EDS does not receive meaningful reward signal |
| `level2_libero_object_inverted` | 17 | `1/1` | EDS iid, inverted reward | Not a valid improvement signal, but useful as reward sanity evidence |
| `level2_libero_object_shuffled` | 30 | `0/1` | EDS iid, shuffled keypoints | Worse reward and target distance |

The controls strongly suggest that this one-episode level2 task is not a clean success-rate gate for RBF initialization. Unguided RDT and zero-reward EDS succeeded, while normal EDS and all RBF variants failed.

### Deltas vs iid Baseline

Compared against `level2_libero_object_p16_c10`, matched by `global_step`.

| Run | Init Diversity Delta | Final Diversity Delta | Initial Best Reward Delta | Selected Reward Delta | Target Distance After Delta | Selected Index Same |
|---|---:|---:|---:|---:|---:|---:|
| `rbf_scale05_start_null` | `+0.117524` | `+0.001393` | `+0.000002` | `-0.000010` | `+0.000155` | `30/30` |
| `rbf_scale1_start_null` | `+0.120469` | `+0.001393` | `+0.000018` | `-0.000010` | `+0.000155` | `30/30` |
| `rbf_scale2_start_null` | `+0.115900` | `-0.151044` | `-0.000532` | `-0.000411` | `+0.001400` | `23/30` |
| `rbf_scale1_start025` | `+0.120469` | `+0.001393` | `+0.000018` | `-0.000010` | `+0.000155` | `30/30` |
| `rbf_scale1_start05` | `-0.674304` | `+0.022153` | `-0.000446` | `-0.000067` | `+0.000472` | `15/30` |

Interpretation:

- `scale=0.5`, `scale=1.0`, and `start_ratio=0.25` slightly increase the action-space initial diversity metric, but this does not translate into better selected rewards or target distances.
- `start_ratio=0.25` is effectively identical to `start_ratio=null` under the current 5-step RDT scheduler. Both apply one diversity step.
- `start_ratio=0.5` applies two diversity steps, but it does not improve selected reward or target distance.
- `scale=2.0` introduces larger differences in some later chunks, but those differences are unstable and slightly worse on average.

### Equality Counts vs iid

| Run vs iid | Matched Chunks | Selected Reward Equal | Target Distance Equal | Init Diversity Equal | Selected Index Equal |
|---|---:|---:|---:|---:|---:|
| `rbf_scale05_start_null` | 30 | 28 | 27 | 0 | 30 |
| `rbf_scale1_start_null` | 30 | 28 | 27 | 0 | 30 |
| `rbf_scale2_start_null` | 30 | 12 | 14 | 0 | 23 |
| `rbf_scale1_start025` | 30 | 28 | 27 | 0 | 30 |
| `rbf_scale1_start05` | 30 | 7 | 8 | 0 | 15 |

This is the clearest quantitative evidence for "almost no downstream difference" at the default RBF setting. The initial population is numerically different, but the selected outcome is nearly identical.

### Resampling Signal

For all RBF runs:

- `initial_diversity_fallback_used=false`
- `initial_diversity_grad_failure_count=0`
- `action_mask_violation_max=0`
- `nonfinite_count=0`
- `score_entropy_mean=2.772589`

For `population_size=16`, maximum entropy is:

```text
ln(16) = 2.772589
```

The observed score entropy is essentially maximum. This means the EDS resampling distribution is nearly uniform, so reward-guided selection pressure is very weak. In that regime, small diversity changes do not reliably change parent selection or the final selected trajectory.

## Qualitative Evidence

Saved qualitative artifacts exist for only two chunks per run:

- `episode_000/chunk_000000`
- `episode_000/chunk_000008`

For both saved chunks, several key PNGs are byte-identical across iid and all RBF sweep variants:

| Artifact | chunk `000000` | chunk `000008` | Interpretation |
|---|---:|---:|---|
| `population_overlay_iter_last.png` | identical across iid/RBF | identical across iid/RBF | Final population overlay looks the same |
| `population_cloud_iter_000.png` | identical across iid/RBF | identical across iid/RBF | First EDS iteration population cloud looks the same in 2D projection |
| `best_trajectory_overlay_iter_000.png` | identical across iid/RBF | identical across iid/RBF | Best trajectory overlay at iter 0 looks the same |
| `keypoints_selected_eef_overlay.png` | identical across iid/RBF | identical across iid/RBF | Final selected EEF overlay looks the same |

`initial_best_vs_final_selected.png` differs in file hash for some RBF variants, but visual inspection shows the same short trajectory near the gripper. Also, this artifact has a limitation in the current visualization helper: the left panel labeled `initial best` is created from `initial_candidates[0]`, not from the actual initial best index. Therefore it should not be treated as a strict best-vs-selected diagnostic.

The qualitative evidence is consistent with the quantitative evidence: final EDS-visible behavior is almost unchanged.

## Why RBF-Diverse Initialization Looks Like iid EDS

### 1. The RBF intervention is real but only early and small

With the current RDT scheduler, total denoising is about 5 steps. For `initial_diversity_start_ratio=null`, the resolver picks `timesteps[len//3]`, which results in one early diversity step. The default sweep setting therefore injects RBF diversity only once.

The default `initial_diversity_scale=1.0` is also conservative. It is much lower than the project VLS config's `diversity_scale=10.0`. Because `_compute_diversity_gradient()` normalizes the gradient norm, `scale=1.0` gives a bounded perturbation that is easy for later denoising to absorb.

### 2. The remaining RDT denoising pulls particles back to the same policy mode

The mechanism trace shows this directly:

- Before RBF: trajectory diversity `0.12408`
- After RBF phase: trajectory diversity `0.12501`
- After full initial denoise: trajectory diversity `0.03706`

The diversity does not survive the final initial proposal. This supports the hypothesis that RDT/VLA's learned prior is strongly contracting the action chunk toward one dominant action mode.

### 3. RBF acts in EEF trajectory space but metrics and selection mostly operate elsewhere

The RBF gradient is computed from 3D EEF trajectories, but the logged `population_diversity_initial` metric is full flattened `(64,128)` action-space distance. This metric can increase slightly without representing a meaningful new executable EEF mode.

Conversely, final 2D qualitative overlays can look identical even when full action-space diversity changes, because only a small decoded 7D EEF trajectory is rendered.

### 4. Only translation slots receive the diversity gradient

The implementation masks guidance to `RDT_GUIDED_TRANSLATION_INDICES = [39, 40, 41]`. This is conservative and preserves action mask safety, but it means the RBF sampler cannot diversify gripper behavior, rotation, or other RDT latent channels. If the mode collapse is dominated by non-translation decisions or by the full RDT policy prior, this gradient has limited leverage.

### 5. EDS reward scores provide almost no selection pressure

The average score entropy is `2.772589`, which is maximum entropy for 16 particles. Reward spreads are tiny, around `0.002`.

This means the EDS resample step is close to random sampling rather than reward-driven selection. If reward ranking barely distinguishes candidates, then even a better-diversified initial population will not be exploited.

### 6. EDS resample-renoise-rollout erases small initialization differences

After initial scoring, EDS repeatedly:

1. resamples parents,
2. renoises,
3. denoises/rolls out truncated scheduler steps,
4. scores again.

The mechanism trace shows that renoise briefly expands trajectory diversity, but rollout contracts it again. By the end of the process, diversity decreases rather than increases. This makes the final selected action insensitive to small initial RBF perturbations.

### 7. The task-level gate is confounded by reward/steering alignment

On this one-episode task:

- Unguided RDT succeeds: `1/1`
- Zero-reward EDS succeeds: `1/1`
- Normal iid EDS fails: `0/1`
- All RBF EDS variants fail: `0/1`

This suggests that the dominant issue in this smoke setting is not only initial population diversity. The normal EDS reward/keypoint steering path may be misaligned with actual task success or may disturb a policy that would otherwise succeed.

### 8. Current qualitative artifacts are not sensitive enough for this mechanism

The saved qualitative overlays mostly show final decoded trajectories over an image. They do not show the RBF-specific initial sampler stages for parameter sweep runs. The mechanism pretest has those stages, but the sweep qualitative artifacts do not. Therefore the parameter sweep visuals are better at showing "final behavior did not change" than at explaining where RBF diversity was lost.

## Root Cause Assessment

The evidence does not support "RBF path failed to run." It did run.

The current best root-cause hypothesis is:

> RBF diversity is injected too early and too weakly relative to the strong RDT denoising prior, and the downstream EDS score/resample process has nearly uniform reward weights, so the small initial differences are either denoised away or not selected. The final decoded EEF trajectories therefore remain visually and behaviorally equivalent to iid EDS.

Secondary contributing factors:

- Current sweep used only low scales `0.5`, `1.0`, `2.0`; it did not test VLS-like `10.0` or `20.0`.
- Current RDT scheduler has only about 5 denoising steps, so `start_ratio` has coarse effects.
- `start_ratio=null` and `start_ratio=0.25` both resolve to one effective diversity step.
- The visualization for `initial_best_vs_final_selected.png` is mislabeled or under-instrumented because it uses candidate `0` as the initial left panel.
- Parameter sweep qualitative artifacts do not include `initial_before_diversity`, `initial_after_diversity_phase`, and `initial_final`, so they cannot localize the loss of diversity.

## Recommendations Before Further OOD Runs

1. Add trajectory-space initial diversity metrics to normal EDS eval:
   - initial before diversity,
   - after diversity phase,
   - final initial population,
   - after first rollout,
   - final selected population.

2. Fix or rename `initial_best_vs_final_selected.png`:
   - either pass the true `initial_best_idx`,
   - or rename the left panel to `initial candidate 0`.

3. Save initial sampler trace artifacts for at least the first chunk of every parameter sweep run:
   - `initial_before_diversity`,
   - `initial_after_diversity_phase`,
   - `initial_final`.

4. Treat success rate from this one-episode level2 smoke as diagnostic only. It is not enough for algorithmic comparison, especially because unguided and zero-reward controls succeed while normal EDS fails.

5. If continuing this algorithm family, test stronger but controlled settings only after adding the above metrics:
   - `initial_diversity_scale=5.0`
   - `initial_diversity_scale=10.0`
   - optionally `initial_diversity_scale=20.0`
   - keep explicit warnings/fallback checks.

6. Investigate EDS reward/keypoint selection pressure:
   - score entropy is currently maximum,
   - reward spread is tiny,
   - selected reward and target distance do not improve.

7. Consider designs that diversify after or near the final initial denoise, or filter final policy samples in trajectory space. The current evidence suggests early RBF perturbations are too easy for the policy prior to erase.

## Final Verdict

Mechanism pretest: pass as a wiring and artifact-generation test.

Parameter sweep: fail as an algorithm-improvement test. The tested RBF initial sampler variants did not improve success rate, selected reward, or final target distance over naive iid EDS.

Main reason: the RBF diversity signal is visible only in the early denoising state and is mostly erased before final initial proposals reach EDS selection. Downstream EDS scoring then has almost no selection pressure, so even residual differences do not affect the final selected action.
