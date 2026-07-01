# RDT+EDS Mechanism Validation Plan

Date: 2026-06-12

Worktree: `.worktrees/feat/rdt_ed_steering_integration`

Scope: design targeted mechanism-validation tests for the current RDT+EDS implementation. This document does not change EDS algorithm code and does not start new LIBERO-PRO or large-scale OOD evaluation.

## Background Conclusions

Current Level 0-3 evidence separates deployment correctness from mechanism effectiveness.

Deployment correctness is mostly verified:

- `main.guidance_type=eds` reaches the RDT EDS path instead of VLS or unguided fallback.
- Every guided chunk records `eds_enter_count=1`.
- `score_call_count == 1 + cem_iters`.
- `resample_count == renoise_count == rollout_count == cem_iters`.
- Population scores are finite.
- `selected_cost == -final_best_reward`, so final selected particle matches the best-cost particle under the current sign convention.
- `zero`, `shuffled_keypoints`, and `inverted` reward modes all run end-to-end.

Mechanism effectiveness is not yet proven:

- Level 1 failed: normal reward improved neither final reward nor target distance in `0/3` mechanism-probe chunks.
- Level 2 failed the effectiveness smoke gate: normal EDS p16/c10 reached `1/3`, while unguided and zero-reward EDS each reached `3/3`.
- Level 3 was inconclusive: unguided RDT reached `9/10`; practical normal EDS settings p16/c10, p16/c20, p32/c10 each reached `6/10`; p32/c20 reached `8/10` but was much slower.
- Level 3 ablations weaken the reward-guidance claim: zero and shuffled each reached `6/10`, equal to common normal settings; inverted dropped to `3/10`, but still showed many target-distance improvements.
- Existing JSONL metrics show low reward-improvement rates. For Level 3, p16/c10 improved reward in `14/149` chunks, p16/c20 in `22/182`, p32/c10 in `21/116`, p32/c20 in `13/132`, and p32/c10 CEM in `16/131`.
- `target_distance_after < target_distance_before` occurs even under `zero` reward, for example `73/166` Level 3 zero-reward chunks, so target distance is not sufficient mechanism evidence by itself.

Conclusion: current evidence proves that the EDS loop is active, but not that reward-guided steering is the causal reason for better action selection or task success.

## EDS Algorithm Step Map

The current RDT+EDS implementation should be understood as an action-population optimizer wrapped around RDT denoising.

| Step | Code fact | Current evidence | Mechanism gap |
| --- | --- | --- | --- |
| Observation and chunk cache | `select_action()` first calls `_obs_processor.observe(batch)`. A new RDT sample is generated only when `generate_new_chunk=true`, no cached chunk exists, or cached steps are exhausted. Otherwise it returns the cached decoded action chunk. See `core/rdt_policy_steer.py:select_action`. | Online runs write EDS metrics only on generated guided chunks. | Mechanism tests must compare chunks, not every env step, because intermediate env steps may reuse the same cached action chunk. |
| Guided entry | `main.py` reads `guidance_type`, `vls_config`, and `eds_config`, then passes them into `policy.select_action()` when guidance is enabled. See `main.py:698-759`. | Level 0-3 logs and counters confirm EDS is entered online. | Does not show that selected actions are semantically better. |
| EDS dispatch | `_predict_guided()` validates `guidance_type in {"vls", "eds"}` and routes `eds` to `_eds_guided_denoise_loop()`. See `core/rdt_policy_steer.py:_predict_guided`. | Deployment verified. | No mechanism claim beyond route correctness. |
| Conditioning and hidden state | `_predict_guided()` calls `self._rdt_model.encode_inputs(state_128, state_mask_128, images, text_embed)` once, then uses the resulting `cond` during population denoise and rollout. In the current implementation there is no separate recurrent hidden state for EDS; the effective context is the observation processor's image/state history, language embedding, `cond`, and cached action chunk state. | Tests verify population batch shape and use of shared condition. | Need verify condition is still semantically aligned after resampling, renoise, and repeated rollouts. |
| Initial population | `_eds_initial_population()` either loads cached `(population_size,64,128)` actions or denoises random `x_t` fully through the scheduler, then applies `cond["action_mask"]`. | Population shape, finite values, and mask violation are checked. | Need know whether initial population is diverse and contains useful candidate variation. |
| Trajectory projection for reward | `_score_particles()` converts `(B,64,128)` samples through `_rdt_sample_to_trajectory_3d()`, which decodes action slots and calls `adapter.delta_actions_to_ee_trajectory()`. See `core/rdt_policy_steer.py:_score_particles`, `_rdt_sample_to_trajectory_3d`. | Reward scores are finite. | This is a major semantic risk: reward sees an approximate EEF trajectory, not necessarily the exact environment-executed outcome. |
| Reward/cost scoring | `_eds_score_population_as_cost()` computes reward through `guidance_fns`, supports `normal`, `zero`, `shuffled_keypoints`, and `inverted`, then returns `cost = -reward`. | Sign convention and best-cost selection are verified. | A correct sign does not prove reward distinguishes good from bad trajectories. |
| Resampling | `_eds_guided_denoise_loop()` either samples CEM elites when `use_cem=true`, or samples parents with `torch.multinomial(softmax(-cost * temperature))`. | Resample count equals `cem_iters`; unique parent ratio is recorded. | Need parent reward distribution and rank distribution to prove high-reward parents are actually favored. |
| Renoise | `_eds_renoise_reference()` applies scheduler `add_noise()` at a truncated timestep from `np.linspace(5, 1, cem_iters)`. | Renoise count equals `cem_iters`. | Need quantify whether renoise perturbation is too weak to explore or too strong to preserve reward. |
| Rollout denoise | `_eds_rollout_reference()` denoises the renoised population through the last `n_trunc_steps` scheduler steps, reapplies action mask, and re-scores. | Rollout count and finite scores are verified. | Need compare reward before rollout versus after rollout to see whether denoising preserves selected parent advantage. |
| Per-iteration update | Each `cem_iter` replaces population with resampled, renoised, rolled-out particles, then records best/mean reward, spread, entropy, diversity, and qualitative candidates. | Existing `per_iter` contains useful convergence metrics. | Current reports do not prove monotonic or statistically reliable convergence. |
| Final selection | `_eds_guided_denoise_loop()` selects `best_idx = argmin(population_scores)` and returns `population[best_idx:best_idx+1]`. | `selected_cost == -final_best_reward` is verified. | Need prove selected particle is better than the initial unguided action and survives environment execution. |
| Decode for execution | `_postprocess_actions()` calls `decode_rdt_libero_action_chunk()`, which selects LIBERO action slots `[39,40,41,42,43,44,10]`, binarizes gripper, and returns `(1,H,7)`. | Decode shape and finite values are checked. | Need compare this execution decode path with the trajectory projection path used for scoring and visualization. |
| Execute selected chunk | `select_action()` stores decoded output in `_cached_action_chunk`, decrements `_cached_action_steps_remaining`, and `main.py` optionally applies `adapter.env_postprocessor` before stepping the environment. See `core/rdt_policy_steer.py:select_action` and `main.py:825-828`. | Episodes run to success/failure and videos/results are written. | Need prove that the selected EDS particle, after decode and postprocessor, moves the real environment closer to the stage goal. |
| Qualitative artifacts | `main.py` calls `save_eds_qualitative_artifacts()` when enabled. It saves projected keypoints, selected EEF overlay, initial-best-vs-final-selected, final population overlay, and per-iter best/population overlays. | Artifacts exist for selected chunks. | Need reviewer protocol and numeric overlay alignment checks; images alone can mislead. |

### Verified Deployment Steps

- EDS route selection and grouped config propagation.
- Population shape `(population_size,64,128)`.
- Finite cost/reward values.
- Score/resample/renoise/rollout counters.
- Action mask application.
- Best-cost final particle selection.
- Metrics JSONL and qualitative artifact writing.

### Unverified Mechanism-Effectiveness Steps

- Reward function ranks semantically better trajectories higher.
- Keypoints, projected EEF trajectories, camera overlays, and environment action execution share a consistent coordinate frame.
- Resampling selects high-reward parents with enough pressure.
- Renoise and rollout preserve or improve reward rather than destroy selected parent advantage.
- Population diversity contracts in a useful way instead of collapsing or drifting randomly.
- Final selected particle improves over unguided RDT initial action in the actual closed-loop environment.
- Chunk-level reward or target-distance improvement correlates with episode success.

### Current Weak Links

- `_rdt_sample_to_trajectory_3d()` uses `adapter.delta_actions_to_ee_trajectory()`, and LIBERO uses an approximate fixed `ACTION_SCALE_POS = 0.01` inside `core/env_adapters/libero_adapter.py:delta_actions_to_ee_trajectory`.
- `target_distance_before/after` uses the first keypoint and selected final trajectory point. This may not represent the active stage goal.
- Reward spread is often very small in Level 2-3, so parent sampling may be near-random.
- Zero reward can still improve target distance and reach comparable SR, indicating target-distance and SR do not isolate reward-guided causality.
- Qualitative overlays use projected approximate trajectories; they need alignment validation before being treated as ground truth.

## Failure Hypotheses Table

| ID | Hypothesis | Code location | Observable symptom | Validation or falsification |
| --- | --- | --- | --- | --- |
| H1 | `reward_fn` does not separate good and bad trajectories. | `core/rdt_policy_steer.py:_score_particles`, `_eds_score_population_as_cost`; stage `guidance_fns` passed from `main.py`. | Low `reward_spread`; normal, zero, and shuffled have similar SR; reward-improve chunks below 70%. | Level A synthetic trajectories with known good/bad ordering. Pass only if ranking accuracy and sign correctness are high. |
| H2 | Keypoints and decoded EEF trajectories are in different coordinate frames. | `_rdt_sample_to_trajectory_3d`; `core/env_adapters/libero_adapter.py:delta_actions_to_ee_trajectory`; `utils/vis_utils.py:project_3d_to_2d`. | Overlay trajectory moves toward displayed keypoint but executed action does not; target distance improves under inverted or shuffled reward. | Level B numeric frame checks and projected overlay alignment against camera observations. |
| H3 | RDT 128D action decoding for reward differs from execution decoding. | `_decode_rdt_actions_for_guidance`, `_decode_visualization_action_candidates`, `_postprocess_actions`, `core/rdt_libero_action_converter.py`. | Scored best particle is not the action actually executed; qualitative overlay does not match env step delta. | Compare raw selected `(1,64,128)`, visualization decode, execution decode, and post-env action after `env_postprocessor`. |
| H4 | Approximate delta-to-EEF projection is not faithful to LIBERO OSC dynamics. | `core/env_adapters/libero_adapter.py:delta_actions_to_ee_trajectory`, `step`. | Predicted EEF displacement differs from measured EEF displacement after replaying the chunk. | Level B replay selected action for one env step or chunk and measure predicted-vs-real EEF error. |
| H5 | Target-distance proxy does not represent task progress. | `_eds_target_distance` uses first keypoint and final trajectory point. | Zero/shuffled/inverted show distance improvement without better SR; shuffled improves distance while failing. | Correlate chunk-level distance change with stage completion and episode success; test multiple keypoint/stage target definitions. |
| H6 | Reward sign/cost sign is operationally correct but semantically reversed. | `_eds_score_population_as_cost` returns `cost = -reward`; final selection uses `argmin(cost)`. | Inverted reward sometimes improves target-distance metrics; normal reward does not consistently outperform inverted. | Level A sign tests and Level F inverted reward should reliably move away or rank wrong trajectories lower. |
| H7 | Resampling is too weak or nearly random. | `_eds_sampling_probabilities_from_cost`, `torch.multinomial`, `temperature`. | Parent selection rank is close to uniform; `score_entropy` near maximum; normal resembles zero reward. | Record parent rank distribution and parent reward before resample. Parent mean reward should exceed population mean. |
| H8 | CEM elite selection is ineffective with current `num_elites` default. | CEM branch in `_eds_guided_denoise_loop`; `_EDSConfig.num_elites`. | `use_cem=true` only modestly changes SR; if `num_elites == population_size`, CEM degenerates toward random elite sampling over all particles. | Test p32 with `num_elites` smaller than population, for example 4 or 8, and measure parent advantage and diversity. |
| H9 | Renoise is too strong and destroys parent advantage. | `_eds_renoise_reference`, trunc schedule `np.linspace(5,1,cem_iters)`. | Parent reward high before renoise, but reward after rollout returns to population mean. | Record reward before resample, after resample, after renoise if scoreable, and after rollout. |
| H10 | Renoise is too weak and cannot explore. | Same as H9. | Diversity collapses quickly; best reward plateaus; selected final is close to initial best. | Measure `renoise_delta_norm`, diversity per iter, and selected-vs-initial action distance. |
| H11 | Rollout denoise breaks high-reward particles. | `_eds_rollout_reference`. | `reward_after_rollout < reward_before_rollout` systematically. | Level C one-iteration before/after test with fixed initial population. |
| H12 | Population diversity collapses too quickly. | `_eds_population_diversity`; resampling with replacement. | Many duplicate parents; `unique_parent_ratio_mean` low; final population lacks alternatives. | Track diversity by trajectory and action-space norms, not just flattened `(64,128)` latent norm. |
| H13 | Best selected particle is better under reward but worse under execution. | Final selection in `_eds_guided_denoise_loop`; decode/step in `main.py`. | Chunk reward improves but next observation is farther from stage goal or SR drops. | Level E closed-loop chunk replay comparing unguided initial, EDS initial best, and EDS final selected. |
| H14 | Qualitative visualization is inconsistent with metrics. | `utils/eds_eval_vis.py`, `utils/vis_utils.py`. | Images suggest movement toward goal, but numeric reward/distance does not, or vice versa. | Save per-iter overlays plus numeric CSV for the same chunk and require reviewer agreement. |
| H15 | VLM keypoint/stage reward is noisy or wrong. | `main.py` keypoint/guidance setup, `vlm_query/*`, stage guidance files under outputs. | Good reward trajectories aim at irrelevant object/part; shuffled keypoints not much worse. | Freeze keypoints, use oracle/synthetic reward, compare VLM-generated reward against hand-labeled target. |

## Targeted Mechanism Tests Table

These tests are ordered from lowest cost and highest diagnostic value to more realistic closed-loop checks. They should be run before any new large-scale LIBERO-PRO OOD evaluation.

| Level | Test | Setup | Primary outputs | What it proves |
| --- | --- | --- | --- | --- |
| A | Offline scoring sanity | Fixed observation, fixed keypoints, fixed reward function; construct synthetic trajectories that move toward target, away from target, orthogonal, and random. | Reward histogram, ranking accuracy, sign correctness, normal/zero/shuffled/inverted comparison. | Whether reward semantics are meaningful before EDS optimization. |
| B | Decode, FK, coordinate consistency | Take real RDT `(B,64,128)` samples and compare reward projection, visualization decode, execution decode, camera projection, and measured EEF movement. | Decode parity table, projection error, predicted-vs-measured EEF error, overlay images. | Whether EDS is optimizing the same action semantics the env executes. |
| C | Single-step EDS inner-loop | Fixed initial population and one EDS iteration: score, resample, renoise, rollout. | Parent rank distribution, parent reward mean, before/after reward, renoise/rollout delta norm. | Whether one EDS update applies useful reward pressure. |
| D | Multi-iteration EDS convergence | Fixed observation/keypoint; run full `cem_iters` with deterministic seed. | Per-iter best reward, mean reward, reward std, diversity, target distance, per-iter overlays. | Whether repeated EDS iterations converge under controlled conditions. |
| E | Closed-loop online chunk | Fixed LIBERO-object task and seed; compare unguided initial action, EDS initial best, and EDS final selected action for the same chunk. | Chunk reward delta, EEF progress after env step, stage progress, correlation with success. | Whether offline reward improvements translate to closed-loop behavior. |
| F | Ablation and falsification | Normal reward versus zero, shuffled, inverted, random selected particle, no-resample, no-renoise, no-rollout, oracle/synthetic reward. | Ablation deltas for reward, target distance, diversity, SR, and qualitative artifacts. | Which EDS steps are necessary and whether normal reward has causal effect. |

## Level A: Offline Scoring Sanity Tests

Purpose: test `guidance_fns(keypoints, trajectory)` without denoising, resampling, or environment stochasticity.

Procedure:

1. Freeze one `libero_object` observation, stage, keypoints, and reward function.
2. Construct synthetic EEF trajectories in the same tensor shape consumed by reward scoring:
   - toward target
   - away from target
   - random walk
   - stationary
   - overshoot target
   - wrong-object or shuffled-keypoint direction
3. Convert these synthetic trajectories into a direct scoring harness, or bypass action decode and call the reward functions on trajectory tensors.
4. Run normal, zero, shuffled-keypoint, and inverted modes.
5. Save reward histogram and ranking table.

Acceptance gate:

- Ranking accuracy for known ordered pairs should be `>= 90%`.
- Sign correctness should be `>= 95%`: toward-target reward must exceed away-from-target reward under normal mode, and inverted should reverse this.
- Zero reward must produce zero spread.
- Shuffled keypoints must degrade ranking accuracy relative to normal when keypoints encode distinct targets.

Evidence files:

- `outputs/rdt_eds_mechanism/level_a_scoring/<run_id>/synthetic_rewards.csv`
- `outputs/rdt_eds_mechanism/level_a_scoring/<run_id>/reward_histogram.png`
- `outputs/rdt_eds_mechanism/level_a_scoring/<run_id>/ranking_accuracy.json`

## Level B: Decode/FK/Coordinate Consistency Tests

Purpose: verify that reward scoring, visualization, and env execution refer to the same physical movement.

Procedure:

1. Sample or load a small RDT action population `(B,64,128)`.
2. Decode with all relevant paths:
   - `_decode_rdt_actions_for_guidance()` for reward trajectory input.
   - `_decode_visualization_action_candidates()` for qualitative overlays.
   - `_postprocess_actions()` and `decode_rdt_libero_action_chunk()` for execution.
3. Compare active action indices `[39,40,41,42,43,44,10]`, gripper binarization, dtype/device, horizon, and first-particle selection.
4. Use `adapter.delta_actions_to_ee_trajectory()` to predict EEF trajectory.
5. Execute the selected decoded action for one step, or replay one chunk in a cloned/reset env when feasible.
6. Compare predicted EEF displacement to measured post-step EEF displacement from `get_ee_pose_world()`.
7. Project keypoints and predicted EEF trajectory onto the VLM/camera image and measure pixel alignment.

Metrics:

- `decode_guidance_vs_visualization_l2`
- `decode_visualization_vs_execution_l2`
- `predicted_vs_measured_eef_delta_l2`
- `keypoint_projection_valid_rate`
- `eef_projection_valid_rate`
- `overlay_pixel_error_to_depth_point`
- `action_scale_sensitivity` for `ACTION_SCALE_POS`

Acceptance gate:

- Decode paths should match on active continuous action slots within `1e-6`, except expected gripper binarization.
- Predicted one-step EEF delta direction cosine with measured delta should be `>= 0.8` for nontrivial actions.
- Median predicted-vs-measured EEF delta error should be below a task-calibrated threshold, initially `<= 2 cm`.
- Projected keypoints and trajectory should be visible and aligned with the expected object/EEF in reviewed overlays.

Evidence files:

- `outputs/rdt_eds_mechanism/level_b_decode_fk/<run_id>/decode_consistency.csv`
- `outputs/rdt_eds_mechanism/level_b_decode_fk/<run_id>/eef_replay_error.json`
- `outputs/rdt_eds_mechanism/level_b_decode_fk/<run_id>/projection_overlay_*.png`

## Level C: Single-Step EDS Inner-Loop Tests

Purpose: isolate whether one EDS update actually increases reward before full convergence or task rollout.

Procedure:

1. Freeze `cond`, keypoints, reward function, scheduler seed, and initial population.
2. Score initial population.
3. Record parent selection probabilities and sampled parent indices.
4. Compare selected-parent rewards against population rewards.
5. Renoise selected parents.
6. Roll out denoise for the chosen `n_trunc_steps`.
7. Re-score final population.

Metrics:

- `population_reward_before_resample_mean/std/max`
- `parent_reward_before_resample_mean/std`
- `parent_selection_rank_distribution`
- `parent_mean_reward_minus_population_mean`
- `reward_before_rollout`
- `reward_after_rollout`
- `reward_after_minus_before_rollout`
- `renoise_delta_norm`
- `rollout_delta_norm`
- `unique_parent_ratio`

Acceptance gate:

- Parent mean reward should exceed population mean reward in `>= 80%` of chunks under normal reward.
- Parent selected-rank distribution should be top-heavy under normal reward and near-uniform under zero reward.
- Rollout should not systematically reduce reward: median `reward_after_minus_before_rollout >= 0` or no worse than a small calibrated tolerance.
- Normal reward must differ from zero reward on parent rank distribution.

Evidence files:

- `outputs/rdt_eds_mechanism/level_c_single_step/<run_id>/single_step_metrics.jsonl`
- `outputs/rdt_eds_mechanism/level_c_single_step/<run_id>/parent_rank_histogram.png`

## Level D: Multi-Iteration EDS Convergence Tests

Purpose: test whether repeated EDS iterations produce measurable convergence under fixed inputs.

Procedure:

1. Freeze observation, keypoints, seed, initial population, and reward function.
2. Run full EDS for p16/c10, p32/c20, and p32/c10 CEM.
3. Save per-iteration population, scores, decoded action candidates, and overlays.
4. Compare normal reward against zero, shuffled, inverted, and oracle/synthetic reward.

Metrics:

- `per_iter_best_reward`
- `per_iter_mean_reward`
- `per_iter_reward_std`
- `per_iter_reward_spread`
- `per_iter_score_entropy`
- `per_iter_population_diversity_action`
- `per_iter_population_diversity_eef`
- `per_iter_target_distance_best`
- `selected_vs_initial_action_distance`
- `selected_vs_initial_eef_distance`

Acceptance gate:

- Normal reward should show `final_best_reward > initial_best_reward` in `>= 70%` fixed-input chunks.
- Normal reward should show `final_mean_reward > initial_mean_reward` in `>= 60%` chunks.
- Diversity should contract but not collapse: final EEF diversity should remain above a small nonzero threshold and should not become duplicate-only.
- Zero/shuffled/inverted should not show the same convergence trend as normal.
- Oracle/synthetic reward should pass strongly; failure under oracle implies EDS update mechanics are broken rather than VLM reward semantics.

Evidence files:

- `outputs/rdt_eds_mechanism/level_d_convergence/<run_id>/eds_metrics.jsonl`
- `outputs/rdt_eds_mechanism/level_d_convergence/<run_id>/per_iter_convergence.csv`
- `outputs/rdt_eds_mechanism/level_d_convergence/<run_id>/best_trajectory_overlay_iter_*.png`
- `outputs/rdt_eds_mechanism/level_d_convergence/<run_id>/population_cloud_iter_*.png`

## Level E: Closed-Loop Online Chunk Tests

Purpose: verify that selected final actions improve real environment state, not only proxy reward.

Procedure:

1. Use one fixed `libero_object` task id, preferably task 0 first.
2. Use fixed env seed and model seed.
3. At a new action chunk, save:
   - unguided RDT action
   - EDS initial best particle
   - EDS final selected particle
4. From the same reset state, execute each candidate for one step or one chunk in separate cloned runs.
5. Measure post-action EEF pose, object pose when available, stage-goal distance, reward proxy, and final episode outcome.
6. Repeat across 10-20 chunks before scaling to episodes.

Metrics:

- `unguided_reward`
- `eds_initial_best_reward`
- `eds_final_selected_reward`
- `eef_progress_after_one_step`
- `eef_progress_after_chunk`
- `object_progress_after_chunk`
- `stage_goal_distance_delta`
- `chunk_reward_delta`
- `episode_success`
- `reward_success_correlation`

Acceptance gate:

- EDS final selected should beat unguided initial on stage-goal progress in `>= 60%` of matched chunks.
- EDS final selected should not degrade env progress relative to unguided by more than a small tolerance in more than `30%` of chunks.
- Chunk-level reward improvement should have positive correlation with stage progress and episode success.
- If reward improves but env progress worsens, the mechanism claim fails and Level B/H4 should be prioritized.

Evidence files:

- `outputs/rdt_eds_mechanism/level_e_closed_loop_chunk/<run_id>/matched_chunk_metrics.jsonl`
- `outputs/rdt_eds_mechanism/level_e_closed_loop_chunk/<run_id>/candidate_replay_videos/`
- `outputs/rdt_eds_mechanism/level_e_closed_loop_chunk/<run_id>/reward_success_correlation.json`

## Level F: Ablation and Falsification Tests

Purpose: prove which EDS components are necessary and falsify reward-guidance claims when controls behave the same as normal.

Required comparisons:

| Comparison | Mechanism question | Expected if EDS reward guidance works |
| --- | --- | --- |
| normal vs zero | Does reward matter at all? | Normal has higher parent reward, convergence, and progress. |
| normal vs shuffled keypoints | Does spatial target identity matter? | Normal beats shuffled on ranking and progress. |
| normal vs inverted reward | Does reward sign matter? | Inverted moves away or ranks wrong trajectories and performs worse. |
| normal vs random selected particle | Does final best selection matter? | Best selection beats random final particle. |
| normal vs no-resampling | Is parent selection necessary? | No-resampling reduces convergence and progress. |
| normal vs no-renoise | Is exploration necessary? | No-renoise reduces improvement or causes stagnation. |
| normal vs no-rollout | Is denoise repair necessary? | No-rollout produces invalid/noisy or lower-progress actions. |
| normal vs oracle/synthetic reward | Is VLM/keypoint reward the bottleneck? | Oracle passes even if VLM normal fails. |

Implementation note: some ablations require temporary instrumentation switches. Keep them under explicit eval-only config, for example `main.eds_mechanism_eval.enabled=true`, and do not change default EDS behavior.

Acceptance gate:

- Normal must beat zero and shuffled on mechanism metrics, not only SR.
- Inverted must be measurably worse on reward-consistent movement.
- Oracle/synthetic reward must produce clear convergence; otherwise debug resample/renoise/rollout before reward semantics.
- Random selected particle should underperform best selected particle under a meaningful reward.

Evidence files:

- `outputs/rdt_eds_mechanism/level_f_ablation/<run_id>/ablation_summary.csv`
- `outputs/rdt_eds_mechanism/level_f_ablation/<run_id>/eds_metrics.jsonl`
- `outputs/rdt_eds_mechanism/level_f_ablation/<run_id>/qualitative/`

## Metrics and Instrumentation Proposal

Existing useful metrics in `core/eds_eval_metrics.py`:

- `initial_best_reward`
- `final_best_reward`
- `initial_mean_reward`
- `final_mean_reward`
- `reward_spread`
- `selected_reward`
- `selected_cost`
- `score_entropy`
- `unique_parent_ratio_mean`
- `population_diversity_initial/final`
- `target_distance_before/after`
- `per_iter.best_reward`
- `per_iter.mean_reward`
- `per_iter.reward_spread`
- `per_iter.score_entropy`
- `per_iter.population_diversity`

Add mechanism-only metrics:

| Metric | Why it is needed | Suggested location |
| --- | --- | --- |
| `per_iter_reward_std` | Distinguish real separation from tiny spread. | Extend `EDSIterMetrics` in `core/eds_eval_metrics.py`. |
| `parent_indices` or sampled rank histogram | Prove high-reward parents are selected. | `_eds_guided_denoise_loop()` immediately after resampling. |
| `parent_reward_before_resample` | Measure selection pressure. | Before replacing `population` with parent samples. |
| `parent_selection_rank_distribution` | Detect random-like resampling. | Eval-only JSONL or histogram artifact. |
| `reward_before_rollout` | Isolate whether rollout preserves reward. | Before `_eds_renoise_reference()` or immediately after parent selection. |
| `reward_after_rollout` | Compare with before rollout. | Already available after `_eds_rollout_reference()`, but store paired values. |
| `renoise_delta_norm` | Quantify perturbation strength. | Around `_eds_renoise_reference()`. |
| `rollout_delta_norm` | Quantify denoise repair distance. | Around `_eds_rollout_reference()`. |
| `population_diversity_eef_per_iter` | Latent diversity may not equal trajectory diversity. | Decode to EEF trajectories inside eval-only instrumentation. |
| `selected_vs_initial_action_distance` | Show final selected differs from initial best. | After final selection. |
| `selected_vs_unguided_action_distance` | Compare to RDT baseline action. | Requires matched unguided sample in Level E harness. |
| `keypoint_to_eef_distance_per_iter` | Target-distance trend by iteration. | After each scoring pass. |
| `projected_keypoint_pixel_error` | Validate visualization/coordinate alignment. | `utils/eds_eval_vis.py` or Level B script. |
| `predicted_vs_executed_eef_delta` | Validate approximate dynamics. | Level B/E replay harness. |
| `reward_success_correlation` | Connect proxy to task outcome. | Post-processing script over JSONL plus episode results. |
| `qualitative_artifact_paths` | Make review traceable. | Already partly stored by `main.py`; keep complete list. |

Where to record:

- Keep default evaluation metrics in `outputs/rdt_eds_eval/*/eds_eval/eds_metrics.jsonl`.
- Write mechanism-specific metrics to a separate root, for example `outputs/rdt_eds_mechanism/<level>/<run_id>/`, to avoid polluting formal evaluation.
- Add an explicit config namespace such as `main.eds_mechanism_eval.enabled=true`.
- Store large tensors only when requested. JSONL should contain scalar metrics and paths to tensor/artifact files.
- Save parent indices, per-iter populations, and decoded trajectories as `.pt` or `.npz` artifacts only for fixed small runs.

## Acceptance Gates

Global mechanism gates before claiming EDS effectiveness:

| Gate | Pass criterion |
| --- | --- |
| Deployment | Same as Level 0: EDS enters, finite scores, correct counters, best-cost selection, no action-mask violation. |
| Reward sanity | Level A ranking accuracy `>= 90%`, sign correctness `>= 95%`, zero reward spread exactly zero. |
| Coordinate consistency | Decode paths match active action slots; predicted-vs-measured EEF direction cosine `>= 0.8`; median one-step EEF error `<= 2 cm` initially. |
| Parent pressure | Resampled parent mean reward exceeds population mean in `>= 80%` normal chunks; not true under zero reward. |
| Rollout preservation | Median `reward_after_rollout - reward_before_rollout >= 0`, or no systematic negative drift. |
| Convergence | Normal final best reward exceeds initial best reward in `>= 70%` fixed-input chunks. |
| Target progress | Normal `target_distance_after < target_distance_before` in `>= 70%` fixed-input chunks, using a validated stage target. |
| Ablation separation | Zero, shuffled, and inverted must not show the same convergence trend as normal. |
| Qualitative consistency | Selected trajectory overlays visibly move toward the relevant keypoint/stage goal and agree with numeric metrics. |
| Online chunk transfer | EDS final selected beats unguided or EDS initial best on matched closed-loop chunk progress in `>= 60%` of chunks. |
| SR sanity | Online SR should be close to unguided on ID, or show better robustness in validated OOD, but SR alone is never sufficient. |

Failure interpretation:

- If Level A fails, debug reward/keypoint semantics before touching EDS optimization.
- If Level B fails, debug action decode, FK/projection, and coordinate frames before interpreting reward metrics.
- If Level C fails but A/B pass, debug resampling temperature, CEM elite count, renoise, and rollout.
- If Level D fails but C passes, debug multi-iteration collapse or drift.
- If Level E fails while A-D pass, debug proxy-to-environment transfer and closed-loop stage logic.

## Recommended Next Experiments

Run these as a small, low-cost matrix focused on mechanism localization.

### Fixed Inputs

- Suite: `libero_object`
- Task id: `0` first, then 1-2 additional task ids only after Level A-C pass.
- Seeds: one fixed seed for initial diagnosis, then 3 seeds for stability.
- VLM/keypoints: freeze cached outputs for deterministic mechanism runs.
- Qualitative sampling: save full per-iter overlays for the first 2 chunks per run, then scalar metrics only.

### Minimal Matrix

| Block | Configs | Purpose |
| --- | --- | --- |
| Scoring sanity | normal, zero, shuffled, inverted, oracle/synthetic | Identify reward/keypoint semantic failure. |
| EDS base | p16/c10 normal and p32/c20 normal | Compare practical and stronger settings. |
| CEM | p32/c10 CEM with `num_elites=4`, `8`, and current default | Check whether current CEM is too weak. |
| Parent mechanics | p16/c10 normal vs zero with parent rank logging | Prove resampling pressure. |
| Component ablations | no-resample, no-renoise, no-rollout, random-final-selection | Prove each EDS step is necessary. |
| Decode/FK | selected action replay for 10 chunks | Validate reward-to-execution semantics. |
| Online chunk | unguided initial vs EDS initial best vs EDS final selected | Check transfer before full episodes. |

### Suggested Run Order

1. Level A reward sanity on 1 observation and 100 synthetic trajectories.
2. Level B decode/FK consistency on 10 saved RDT samples.
3. Level C single-step EDS on p16/c10 normal, zero, inverted, and oracle reward.
4. Level D convergence on p16/c10 and p32/c20 normal, zero, shuffled, inverted, oracle.
5. Level F no-resample/no-renoise/no-rollout/random-selected ablations on fixed inputs.
6. Level E matched online chunk replay on task 0 for 10-20 chunks.
7. Only after these pass, rerun a small 10-episode ID comparison.

Do not start new large-scale LIBERO-PRO OOD evaluation until the reward, decode/FK, and parent-pressure gates pass.

## Expected Evidence Files

Recommended output root:

```text
outputs/rdt_eds_mechanism/
```

Expected files:

| Evidence | Path pattern |
| --- | --- |
| Scoring synthetic trajectories | `outputs/rdt_eds_mechanism/level_a_scoring/<run_id>/synthetic_trajectories.pt` |
| Reward histogram | `outputs/rdt_eds_mechanism/level_a_scoring/<run_id>/reward_histogram.png` |
| Ranking accuracy | `outputs/rdt_eds_mechanism/level_a_scoring/<run_id>/ranking_accuracy.json` |
| Decode consistency | `outputs/rdt_eds_mechanism/level_b_decode_fk/<run_id>/decode_consistency.csv` |
| Replay error | `outputs/rdt_eds_mechanism/level_b_decode_fk/<run_id>/eef_replay_error.json` |
| Projection overlays | `outputs/rdt_eds_mechanism/level_b_decode_fk/<run_id>/projection_overlay_*.png` |
| Single-step metrics | `outputs/rdt_eds_mechanism/level_c_single_step/<run_id>/single_step_metrics.jsonl` |
| Parent rank histogram | `outputs/rdt_eds_mechanism/level_c_single_step/<run_id>/parent_rank_histogram.png` |
| Convergence metrics | `outputs/rdt_eds_mechanism/level_d_convergence/<run_id>/eds_metrics.jsonl` |
| Per-iter convergence table | `outputs/rdt_eds_mechanism/level_d_convergence/<run_id>/per_iter_convergence.csv` |
| Per-iter qualitative overlays | `outputs/rdt_eds_mechanism/level_d_convergence/<run_id>/qualitative/chunk_*/best_trajectory_overlay_iter_*.png` |
| Matched online chunks | `outputs/rdt_eds_mechanism/level_e_closed_loop_chunk/<run_id>/matched_chunk_metrics.jsonl` |
| Candidate replay videos | `outputs/rdt_eds_mechanism/level_e_closed_loop_chunk/<run_id>/candidate_replay_videos/` |
| Ablation summary | `outputs/rdt_eds_mechanism/level_f_ablation/<run_id>/ablation_summary.csv` |
| Final mechanism summary | `docs/03_evidence/eds_steering/rdt_eds_mechanism_validation_report.md` |

## Final Recommendation

The next step should not be a larger OOD run. The immediate priority is a targeted mechanism-validation pass:

1. Prove reward semantics offline.
2. Prove coordinate/decode/FK consistency.
3. Prove one-step EDS parent selection, renoise, and rollout improve or preserve reward.
4. Prove multi-iteration convergence under fixed inputs.
5. Prove closed-loop chunk transfer against unguided RDT.

Only if these gates pass should EDS be promoted from "deployed and runnable" to "mechanistically effective." If any early gate fails, the failure will localize the problem to reward semantics, coordinate/decode mismatch, resampling pressure, renoise/rollout dynamics, or proxy-to-environment transfer.
