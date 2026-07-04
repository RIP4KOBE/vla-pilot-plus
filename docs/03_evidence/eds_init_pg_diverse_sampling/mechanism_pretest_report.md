# Mechanism Pretest Report

- Branch: `exp/eds-init-pg-diverse-sampling`
- Commit: `4c0816193fdf09c34f29a521f3dac4de515964c5`
- Worktree: `/home/hynx/VLA-Pilot++/.worktrees/exp/eds-init-pg-diverse-sampling`
- GPU: physical GPU 3, NVIDIA H200 NVL
- `CUDA_VISIBLE_DEVICES`: `3`
- Pre-run `nvidia-smi` summary: GPU 3 was idle at `0MiB / 143771MiB`, `0%` utilization, while GPUs 0-2 were occupied.
- Command:

```bash
env -u ALL_PROXY -u all_proxy -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy \
  OPENAI_API_KEY=dummy CUDA_VISIBLE_DEVICES=3 \
  python main.py \
  policy.type=rdt \
  backend=libero \
  backend.libero.suite_name=libero_object \
  backend.libero.task_ids_filter=[1] \
  backend.libero.max_episode_steps=240 \
  main.episode_num=1 \
  main.use_vlm_stage_recognition=false \
  perception.gemini_grounding.enabled=false \
  main.cached_functions_dir=/home/hynx/VLA-Pilot++/outputs/libero/2026-06-04_13-21-01/episode_2/vlm_agent \
  main.render=false \
  main.visualize_trajectory=false \
  main.debug_draw_trajectory=false \
  main.use_guidance=true \
  main.guidance_type=eds \
  main.eds_config.population_size=16 \
  main.eds_config.cem_iters=10 \
  main.eds_config.use_cem=false \
  main.eds_config.initial_sampling_mode=rbf_diverse_denoise \
  main.eds_config.initial_diversity_scale=1.0 \
  main.eds_config.initial_diversity_start_ratio=null \
  main.eds_eval.enabled=true \
  main.eds_eval.write_metrics=true \
  main.eds_eval.save_qualitative=false \
  main.eds_eval.reward_mode=normal \
  main.eds_mechanism_pretest.enabled=true \
  main.eds_mechanism_pretest.first_chunk_only=true \
  main.eds_mechanism_pretest.save_single_step=true \
  main.eds_mechanism_pretest.save_full_process=true \
  main.eds_mechanism_pretest.save_tensors=true \
  main.eds_mechanism_pretest.plot_3d=true \
  main.eds_mechanism_pretest.output_dir=outputs/rdt_eds_mechanism_pretest_rbf \
  hydra.run.dir=outputs/rdt_eds_mechanism_pretest_rbf/hydra_cached_no_proxy
```

- Output root: `outputs/rdt_eds_mechanism_pretest_rbf`
- Initial sampler: `rbf_diverse_denoise`
- Diversity scale: `1.0`
- Fallback warnings: `0`; `initial_diversity_fallback_used=false` for all 17 metric records.
- Initial trajectory diversity: first chunk `4.898603916168213`; mean across recorded chunks `3.3259300414253685`.
- Endpoint spread: not recorded by current runner as a dedicated metric; qualitative artifacts include initial/final 3D trajectory spreads.
- Selected reward: first chunk initial best `-0.0947265625`, final best `-0.09716796875`; mean initial best `-0.01487124667448156`, mean final best `-0.015139299280503216`.
- Target distance: first chunk before `0.296875`, after `0.30078125`; mean before `0.07970024557674632`, mean after `0.08053409352022059`.
- Latency: first chunk `initial_sampler_latency_s=0.5991879049688578`, mean `initial_sampler_latency_s=0.43592769616310867`; mean `select_action_latency_s=2.7719680814291623`.
- Qualitative artifacts:
  - `outputs/rdt_eds_mechanism_pretest_rbf/libero_object_task1_seed000_normal_p16_c10/single_step_inner_loop/initial_before_diversity_3d.png`
  - `outputs/rdt_eds_mechanism_pretest_rbf/libero_object_task1_seed000_normal_p16_c10/single_step_inner_loop/initial_after_diversity_phase_3d.png`
  - `outputs/rdt_eds_mechanism_pretest_rbf/libero_object_task1_seed000_normal_p16_c10/single_step_inner_loop/initial_final_3d.png`
  - `outputs/rdt_eds_mechanism_pretest_rbf/libero_object_task1_seed000_normal_p16_c10/full_eds_process/full_process_summary.md`
  - `outputs/rdt_eds_mechanism_pretest_rbf/hydra_cached_no_proxy/episode_1/episode_1_success_agentview.mp4`
- Verdict: pass for mechanism pretest. The episode completed successfully (`1/1`, 129 steps), the RBF-diverse initial sampler trace artifacts were generated, and no diversity fallback was recorded.
- Debug notes:
  - `third_party/rdt` had to be initialized before runtime because it was an empty submodule checkout.
  - The default runner path requires OpenAI/Gemini credentials for guidance generation. This pretest used an existing cached guidance directory for the matching cream-cheese-to-basket task, disabled Gemini grounding/stage recognition, supplied a dummy `OPENAI_API_KEY`, and cleared proxy variables so the OpenAI client could initialize without `socksio`.
  - `Endpoint spread` should be promoted to an explicit metric before full OOD analysis if numeric gating requires it.
