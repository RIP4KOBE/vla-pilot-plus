# RDT+EDS Qualitative Mechanism Pretest Design

Date: 2026-06-12

Worktree: `.worktrees/feat/rdt_ed_steering_integration`

Scope: design a small qualitative pretest for EDS mechanism inspection before running the full mechanism-validation plan in `docs/01_specs/rdt_eds_mechanism_validation_plan.md`. This document is design-only and does not change EDS implementation code.

## Motivation

The Level 0-3 evidence shows that EDS deployment is correct, but mechanism effectiveness is still unclear. Before implementing the full validation matrix, this pretest uses one real `libero_object` task and one first action chunk as a microscope for the EDS inner loop.

The pretest should answer:

- Does the initial action population contain useful candidate variation?
- Does the current normal reward assign higher scores to trajectories that are geometrically closer to the intended keypoint or stage goal?
- Does resampling actually favor high-reward parents?
- Does renoise perturb trajectories enough to explore without destroying parent structure?
- Does rollout denoise preserve or improve the high-reward parent advantage?
- Does the full EDS process converge to a final selected trajectory that is qualitatively more plausible than the initial best candidate?

This pretest is not a success-rate evaluation. A failed episode does not by itself fail the pretest, and a successful episode does not by itself prove EDS mechanism effectiveness.

## Experiment Setup

| Item | Setting |
| --- | --- |
| Suite | `libero_object` |
| Task | task id `1` |
| Episodes | `1` |
| Chunk scope | first generated action chunk only |
| Guidance | `main.use_guidance=true`, `main.guidance_type=eds` |
| Reward mode | `normal` first; optional follow-up with `zero` and `inverted` |
| Population | start with `population_size=16` |
| EDS iterations | start with `cem_iters=10` |
| CEM | `use_cem=false` for the first run |
| VLM/keypoints | use real task observation and real keypoints; cache the first-chunk keypoints and guidance outputs |
| Outputs | 3D plots, scalar CSV/JSONL, saved tensors for first chunk only |

The first run should use the normal reward only. If the visualization pipeline and scalar outputs are coherent, run two controls:

- `reward_mode=zero`
- `reward_mode=inverted`

Do not include shuffled keypoints, p32/c20, CEM sweeps, or OOD suites in the first pretest pass.

## Core Design

The pretest has two artifact groups.

### Single-Step EDS Inner Loop

This group visualizes exactly one EDS update, preferably iteration `0`.

| Stage | 3D visualization | Scalar evidence | Question |
| --- | --- | --- | --- |
| `00_initial_population` | Initial clean EEF trajectories, keypoint, start EEF pose. | pairwise trajectory diversity, distance-to-keypoint distribution. | Is the population diverse and useful? |
| `01_scored_population` | Same trajectories colored by reward. | reward mean/std/spread, reward rank, distance rank. | Does reward correlate with keypoint geometry? |
| `02_after_resample` | Parent trajectories after resampling; repeated parents shown by thicker lines or count labels. | parent ids, parent ranks, resampled counts, parent reward mean. | Are high-reward parents favored? |
| `03_after_renoise` | Renoised projected trajectories, plus faint parent references. | renoise delta norm, drift from parent, distance drift. | Is renoise too weak, too strong, or reasonable? |
| `04_after_rollout` | Rollout-denoised clean trajectories colored by new reward. | reward before rollout, reward after rollout, rollout delta norm. | Does rollout preserve or improve reward advantage? |

Important interpretation rule: the renoised population may be a noisy latent/action state and is not necessarily directly executable. Its 3D projection is a diagnostic for perturbation size, not a claim about executable robot motion.

### Full EDS Process

This group visualizes the complete `cem_iters` process for the same first chunk.

| Artifact | Purpose |
| --- | --- |
| `iter_000_population_3d.png` through `iter_009_population_3d.png` | Show how the population moves and contracts over EDS iterations. |
| `iter_000_best_trajectory_3d.png` through `iter_009_best_trajectory_3d.png` | Show best trajectory evolution without population clutter. |
| `final_selected_vs_initial_best_3d.png` | Compare initial best and final selected trajectory against keypoint and start EEF. |
| `reward_curve.png` | Plot best, mean, and std reward per iteration. |
| `diversity_curve.png` | Plot action-space and EEF-space diversity per iteration. |
| `distance_curve.png` | Plot best final-point distance and min-trajectory distance to keypoint per iteration. |
| `full_process_summary.md` | Human-readable conclusion for the first chunk. |

## 3D Visualization Semantics

All 3D plots should use a consistent world coordinate frame and fixed axis limits across stages.

| Visual element | Encoding |
| --- | --- |
| Start EEF position | black sphere |
| Keypoint or stage target | red star |
| Population trajectory | semi-transparent polyline |
| Reward | sequential colormap, light for low reward and dark blue or purple for high reward |
| Best trajectory | thick gold or black line |
| Final selected trajectory | thick green line |
| Resampled parent count | line width or small text count near trajectory endpoint |
| Parent-to-renoise drift | faint dashed connector or paired before/after line |
| Rollout before/after | before in gray, after in reward-colored line |

Each figure title should include:

```text
suite=libero_object, task_id=1, chunk=0, iter=<k>,
reward_mode=<mode>, pop=<B>, cem_iters=<C>,
best_reward=<value>, mean_reward=<value>, reward_spread=<value>
```

Each figure should include a colorbar labeled `reward` when reward coloring is used.

## Data To Capture

Save one row per particle per stage.

| Field | Meaning |
| --- | --- |
| `stage` | `initial`, `scored`, `resampled`, `renoised`, `after_rollout`, or `final` |
| `iter_idx` | EDS iteration index |
| `particle_id` | Current particle id |
| `parent_id` | Source particle id before resampling |
| `parent_rank` | Reward rank before resampling |
| `resampled_count` | Number of children produced from the same parent |
| `reward` | Current reward used by EDS |
| `cost` | Current EDS cost |
| `reward_rank` | Rank by reward |
| `distance_to_keypoint_final` | Distance from final trajectory point to keypoint |
| `distance_to_keypoint_min` | Minimum distance over the trajectory to keypoint |
| `trajectory_length` | Sum of segment lengths in 3D |
| `renoise_delta_norm` | Norm between parent clean action and renoised action |
| `rollout_delta_norm` | Norm between renoised action and rollout-denoised action |
| `reward_before_rollout` | Parent or pre-rollout reward paired to this particle |
| `reward_after_rollout` | Reward after rollout denoise |

Save tensors for reproducibility:

- first observation metadata
- keypoints
- initial population
- per-stage populations for iteration 0
- per-iteration post-rollout populations
- per-iteration scores/rewards
- final selected particle

## Output Directory Layout

Recommended root:

```text
outputs/rdt_eds_mechanism_pretest/
```

Expected structure:

```text
outputs/rdt_eds_mechanism_pretest/
  libero_object_task1_seed000_normal_p16_c10/
    config.json
    first_chunk_metadata.json
    keypoints_3d.json
    tensors/
      initial_population.pt
      single_step_iter000.pt
      full_process_populations.pt
      final_selected.pt
    single_step_inner_loop/
      00_initial_population_3d.png
      01_scored_population_3d.png
      02_after_resample_3d.png
      03_after_renoise_3d.png
      04_after_rollout_3d.png
      single_step_particles.csv
    full_eds_process/
      iter_000_population_3d.png
      iter_000_best_trajectory_3d.png
      iter_001_population_3d.png
      iter_001_best_trajectory_3d.png
      ...
      final_selected_vs_initial_best_3d.png
      reward_curve.png
      diversity_curve.png
      distance_curve.png
      per_iter_metrics.csv
      full_process_summary.md
```

Optional control runs should use the same layout with `zero` or `inverted` in the run id.

## Qualitative Review Protocol

A human reviewer should inspect the artifacts in this order:

1. `00_initial_population_3d.png`: check whether trajectories cover multiple directions and magnitudes rather than collapsing immediately.
2. `01_scored_population_3d.png`: check whether darker or higher-reward trajectories are geometrically closer to the keypoint or more aligned with the intended stage.
3. `02_after_resample_3d.png`: check whether duplicated or thicker parent trajectories correspond to high reward ranks.
4. `03_after_renoise_3d.png`: check whether renoise creates meaningful but not destructive perturbations.
5. `04_after_rollout_3d.png`: check whether rollout returns to clean plausible trajectories and preserves high-reward structure.
6. Full-process curves: check whether best reward, mean reward, and distance trends are coherent.
7. `final_selected_vs_initial_best_3d.png`: check whether final selected is visibly more plausible than initial best.

The reviewer should write one of:

- `pass`: reward geometry, parent selection, perturbation, rollout, and final selection are coherent.
- `mixed`: some stages look coherent but at least one stage is ambiguous or contradictory.
- `fail`: reward geometry or inner-loop dynamics are visibly inconsistent.

## Pretest Acceptance Criteria

This pretest is qualitative, but it should still have explicit gates.

| Gate | Pass expectation |
| --- | --- |
| Population diversity | Initial population has visible spread and nonzero EEF-space diversity. |
| Reward geometry | Higher reward trajectories are generally closer to or better aligned with the keypoint/stage target. |
| Resampling pressure | High-reward parents have higher resampled counts or visibly thicker representation. |
| Renoise scale | Renoise produces visible drift without erasing the parent trajectory structure. |
| Rollout preservation | Reward after rollout is not systematically lower than reward before rollout. |
| Full-process trend | Best reward or validated target-distance improves over the first chunk. |
| Final selected plausibility | Final selected trajectory is at least as plausible as the initial best and preferably more goal-directed. |
| Artifact completeness | All required plots, CSV files, JSON metadata, and tensors exist for the first chunk. |

## Failure Interpretation

| Failure | Likely next debugging target |
| --- | --- |
| Reward color does not match keypoint geometry | Reward function, keypoint semantics, coordinate frame. |
| High-reward parents are not resampled more often | Sampling temperature, cost sign, parent-index logging, CEM settings. |
| Renoise barely changes trajectories | Trunc step schedule or scheduler noise scale may be too weak. |
| Renoise destroys all structure | Trunc step schedule or scheduler noise scale may be too strong. |
| Rollout reduces reward consistently | Rollout denoise breaks parent advantage; inspect `_eds_rollout_reference()`. |
| Full process collapses to one bad trajectory | Diversity collapse or over-aggressive resampling. |
| Final selected looks worse despite high reward | Reward-to-execution mismatch; run Level B decode/FK consistency tests. |

## Recommended Implementation Boundary

This design can be implemented with an eval-only script or config path. It should not change default EDS behavior.

Recommended switches:

```yaml
main:
  eds_mechanism_pretest:
    enabled: true
    first_chunk_only: true
    save_single_step: true
    save_full_process: true
    save_tensors: true
    plot_3d: true
```

If implementation requires temporary hooks inside `_eds_guided_denoise_loop()`, guard all additional tensor capture behind the eval-only switch and keep formal `outputs/rdt_eds_eval/*` metrics unchanged.

## Final Recommendation

Run this pretest before building the full mechanism-validation suite. If the normal reward visualization already fails on the first `libero_object` task1 chunk, prioritize reward/keypoint/coordinate debugging before adding no-resample, no-renoise, no-rollout, or larger OOD experiments. If the normal run is coherent, repeat the same first-chunk visualization for `zero` and `inverted` controls to verify that the qualitative pattern is reward-dependent.
