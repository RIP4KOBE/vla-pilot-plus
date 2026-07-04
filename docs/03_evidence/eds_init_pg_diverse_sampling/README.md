# EDS RBF-Diverse Initial Sampling Evidence Protocol

Use this protocol for every RDT+EDS run that evaluates `initial_sampling_mode=rbf_diverse_denoise`.
Do not treat a run as comparable unless every field below is recorded.

## Provenance

- Branch: `exp/eds-init-pg-diverse-sampling`
- Commit hash: record `git rev-parse HEAD`
- Worktree path: `/home/hynx/VLA-Pilot++/.worktrees/exp/eds-init-pg-diverse-sampling`
- Sweep id: record the runner sweep/job id and any external tracker id
- Validation gate: record `pass` or `fail`, including the command and failure reason if failed

## Exact Command

Record the exact shell command, including environment variables. Template:

```bash
CUDA_VISIBLE_DEVICES=<logical_gpu> python scripts/rdt_eds_eval_runner.py run-level --level level4 --episodes 10 --gpus <logical_gpu> --timeout-seconds 28800 --resume
```

For a single command snapshot, record:

```bash
python scripts/rdt_eds_eval_runner.py print-command --level level4 --episodes 10 --job-index <index> --gpu <logical_gpu> --timeout-seconds 28800
```

## Full Config Overrides

Record the complete Hydra override list emitted by the runner. The RBF-diverse initial sampler job must include:

```text
policy.type=rdt
backend=libero
backend.libero.suite_name=<suite>
main.episode_num=10
backend.libero.max_episode_steps=240
backend.libero.strict_perturbations=true
main.use_vlm_stage_recognition=true
perception.gemini_grounding.enabled=true
main.render=true
main.visualize_trajectory=true
main.debug_draw_trajectory=true
main.eds_eval.enabled=true
main.eds_eval.write_metrics=true
main.eds_eval.save_qualitative=true
main.eds_eval.method_label=eds_rbf_diverse_initial
main.eds_eval.job_id=<job_id>
main.eds_eval.output_dir=<output_dir>/eds_eval
hydra.run.dir=<output_dir>
main.use_guidance=true
main.guidance_type=eds
main.eds_config.population_size=16
main.eds_config.cem_iters=10
main.eds_config.use_cem=false
main.eds_config.num_elites=32
main.eds_config.temperature=0.1
main.eds_config.renoise_t_max=5
main.eds_config.renoise_t_min=1
main.eds_eval.reward_mode=normal
main.eds_config.initial_sampling_mode=rbf_diverse_denoise
main.eds_config.initial_diversity_scale=1.0
main.eds_config.initial_diversity_start_ratio=null
```

## Hardware Pre-Run Record

- `CUDA_VISIBLE_DEVICES`: record the exact value
- Physical GPU id: record the mapped physical GPU id for each logical id
- Pre-run `nvidia-smi` summary: record timestamp, GPU model, driver/CUDA versions, memory used/free, utilization, temperature, and any active processes

## Evaluation Scope

- Task suite: record the exact suite, for example `libero_object_object`
- Task ids: record each task id included by the benchmark
- Seeds: record environment, policy, sampler, and any framework seeds
- Episode count: record attempted and completed counts
- Checkpoint: record absolute path and checksum when available
- Policy type: `rdt`
- Guidance type: `eds`
- Reward mode: `normal`
- VLM/keypoint cache: record cache path, hit/miss counts, and whether cache was warmed before the run
- Initial sampling mode: `rbf_diverse_denoise`
- Diversity parameters: `initial_diversity_scale=1.0`, `initial_diversity_start_ratio=null`

## Required Outcomes

- Success count / total and success rate
- Per-episode result table with episode id, task id, seed, success/failure, failure notes, and video path
- `initial_sampler_latency_s` per episode/action and mean
- `select_action_latency_s` per episode/action and mean
- Initial diversity, final diversity, endpoint spread, selected reward, and target distance
- Fallback warning count and fallback reasons, including `initial_diversity_fallback_used` and `initial_diversity_fallback_reason`
- Qualitative artifact paths: videos, qualitative PNGs, metrics JSONL, logs, and Hydra output directory

## Comparison Baselines

Compare the RBF-diverse initial sampler against:

- Unguided RDT: `main.use_guidance=false`, no EDS initial sampler overrides
- Current EDS iid baseline: `main.guidance_type=eds`, `main.eds_config.initial_sampling_mode=iid`, `main.eds_config.initial_diversity_scale=1.0`, `main.eds_config.initial_diversity_start_ratio=null`

For each comparison, report success count / total, success rate, select-action latency mean, EDS latency mean, initial sampler latency mean, fallback count, qualitative artifact paths, and any systematic failure notes.
