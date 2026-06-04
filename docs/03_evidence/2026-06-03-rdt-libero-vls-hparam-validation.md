---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: feat/rdt-libero-gt-rollout-reintegration
source_commit: 360a6d052861
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/docs/docs/03_evidence/2026-06-03-rdt-libero-vls-hparam-validation.md
summary: RDT LIBERO VLS Steering Hyperparameter Validation Evidence
duplicate_sources: []
---

# RDT LIBERO VLS Steering Hyperparameter Validation Evidence

Date: 2026-06-03

Scope: this document records only hyperparameter validation runs for RDT LIBERO VLS steering. It is not a design document. Each row records the parameter mix, output directory, observed success rate, and whether the run can satisfy the implementation gate:

`guided_success_rate >= unguided_success_rate`

## Baseline

| Run | Guidance | Key Parameters | Output Directory | Success | Notes |
| --- | --- | --- | --- | --- | --- |
| `rdt_gate11_unguided_full` | off | `policy.type=rdt` | `outputs/libero/rdt_gate11_unguided_full` | `9/10 = 90.00%` | Unguided baseline. Guided runs must reach at least this rate. |

## Guided Runs

| Run | Key Parameters | Output Directory | Observed Success | Videos / Failure Files | Status |
| --- | --- | --- | --- | --- | --- |
| `rdt_gate11_guided_full` | default LIBERO task scales; effective task `guide_scale=80.0`; `sample_batch_size=20`; `use_diversity=true`; `diversity_scale=10.0`; `use_fkd=true`; `main.use_vlm_stage_recognition=false` | `outputs/libero/rdt_gate11_guided_full` | stopped at `2/4`; max possible after two failures was `< 9/10` | `episode_1/episode_1_success_agentview.mp4`; `episode_2/episode_2_success_agentview.mp4`; `episode_3/episode_3_fail_agentview.mp4`; `episode_4/episode_4_fail_agentview.mp4` | Failed early-stop criterion. |
| `rdt_gate11_guided_full_gs20` | attempted `main.guide_scale=20.0` without overriding LIBERO per-task scales | `outputs/libero/rdt_gate11_guided_full_gs20` | not counted | no final metric | Invalid tuning attempt: adapter still selected task `guide_scale=80.0`. |
| `rdt_gate11_guided_full_gs20_alltasks` | `main.guide_scale=20.0`; `backend.libero.task_guide_scales=[20.0]*10`; `sample_batch_size=20`; `use_diversity=true`; `diversity_scale=10.0`; `use_fkd=true`; `main.use_vlm_stage_recognition=false` | `outputs/libero/rdt_gate11_guided_full_gs20_alltasks` | stopped after `4/6`; max possible after two failures was `< 9/10` | successes: `episode_1` to `episode_4`; failure marker: `episode_5/episode_5_fail_error.txt`; failure video: `episode_6/episode_6_fail_agentview.mp4` | Failed early-stop criterion. Episode 5 failed during guidance validation: generated stage2 function returned `float` instead of `torch.Tensor`; episode 6 reached 720-step limit. |

## Active / Next Runs

| Run | Key Parameters | Output Directory | Success | Status |
| --- | --- | --- | --- | --- |
| `rdt_gate11_guided_full_gs40_alltasks_v2` | `main.guide_scale=40.0`; `backend.libero.task_guide_scales=[40.0]*10`; `sample_batch_size=20`; `use_diversity=true`; `diversity_scale=10.0`; `use_fkd=true`; `main.use_vlm_stage_recognition=false` | `outputs/libero/rdt_gate11_guided_full_gs40_alltasks_v2` | stopped at `2/4`; max possible after two failures was `< 9/10` | Failed early-stop criterion. Videos: `episode_1/episode_1_success_agentview.mp4`, `episode_2/episode_2_success_agentview.mp4`, `episode_3/episode_3_fail_agentview.mp4` (720-step limit), `episode_4/episode_4_fail_agentview.mp4` (720-step limit). |
| `rdt_tune_gs20_temp0_tasks45` | Targeted subset: `backend.libero.task_ids_filter=[4,5]`; `main.episode_num=2`; `main.guide_scale=20.0`; `backend.libero.task_guide_scales=[20.0,20.0]`; `perception.vlm_agent.temperature=0.0`; `sample_batch_size=20`; `use_diversity=true`; `diversity_scale=10.0`; `use_fkd=true`; `main.use_vlm_stage_recognition=false` | `outputs/libero/rdt_tune_gs20_temp0_tasks45` | `1/2 = 50.00%` | Targeted tuning run did not clear the known failure region. Videos: `episode_1/episode_1_fail_agentview.mp4`, `episode_2/episode_2_success_agentview.mp4`. |
| `rdt_tune_gs20_temp0_no_fkd_tasks45` | Targeted subset: `backend.libero.task_ids_filter=[4,5]`; `main.episode_num=2`; `main.guide_scale=20.0`; `backend.libero.task_guide_scales=[20.0,20.0]`; `perception.vlm_agent.temperature=0.0`; `sample_batch_size=20`; `use_diversity=true`; `diversity_scale=10.0`; `use_fkd=false`; `main.use_vlm_stage_recognition=false` | `outputs/libero/rdt_tune_gs20_temp0_no_fkd_tasks45` | `1/2 = 50.00%` | FKD ablation did not clear the known failure region. Videos: `episode_1/episode_1_fail_agentview.mp4`, `episode_2/episode_2_success_agentview.mp4`. |

## Full 10-Episode Ablations

All rows in this section must run the complete 10-episode LIBERO object suite. Do not early-stop after failures.

### Diversity Scale Sweep

Fixed parameters unless noted: `main.guide_scale=20.0`; `backend.libero.task_guide_scales=[20.0]*10`; `main.sample_batch_size=20`; `main.use_diversity=true`; `main.use_fkd=true`; `main.use_vlm_stage_recognition=false`; `perception.vlm_agent.temperature=0.0`; `main.episode_num=10`.

| Run | Swept Parameter | Output Directory | Success | Status |
| --- | --- | --- | --- | --- |
| `rdt_full_divs1_gs20_temp0` | `main.diversity_scale=1.0` | `outputs/libero/rdt_full_divs1_gs20_temp0` | `7/10 = 70.00%` | Complete. Videos: failures at `episode_1`, `episode_5`, `episode_8`; successes at `episode_2`, `episode_3`, `episode_4`, `episode_6`, `episode_7`, `episode_9`, `episode_10`. Does not meet the `9/10` gate. |
| `rdt_full_divs2_gs20_temp0` | `main.diversity_scale=2.0` | `outputs/libero/rdt_full_divs2_gs20_temp0` | `3/10 = 30.00%` | Complete. Videos: successes at `episode_2`, `episode_6`, `episode_10`; rollout failures at `episode_1`, `episode_3`, `episode_4`, `episode_5`, `episode_8`, `episode_9`; preparation error at `episode_7/error.txt` because VLM-generated `stage2_guidance.txt` returned `int` instead of `torch.Tensor`. Does not meet the `9/10` gate. |
| `rdt_full_divs5_gs20_temp0` | `main.diversity_scale=5.0` | `outputs/libero/rdt_full_divs5_gs20_temp0` | `5/10 = 50.00%` | Complete. Videos: successes at `episode_2`, `episode_3`, `episode_4`, `episode_6`, `episode_7`; rollout failures at `episode_5`, `episode_8`, `episode_9`, `episode_10`; preparation error at `episode_1/error.txt` because VLM-generated `stage2_guidance.txt` returned `int` instead of `torch.Tensor`. Does not meet the `9/10` gate. |
| `rdt_full_divs10_gs20_temp0` | `main.diversity_scale=10.0` | `outputs/libero/rdt_full_divs10_gs20_temp0` | `4/10 = 40.00%` | Complete. Videos: successes at `episode_2`, `episode_3`, `episode_4`, `episode_6`; rollout failures at `episode_5`, `episode_7`, `episode_8`, `episode_9`, `episode_10`; preparation error at `episode_1/error.txt` because VLM-generated `stage2_guidance.txt` returned `int` instead of `torch.Tensor`. Does not meet the `9/10` gate. |
| `rdt_full_divs20_gs20_temp0` | `main.diversity_scale=20.0` | `outputs/libero/rdt_full_divs20_gs20_temp0` | `4/10 = 40.00%` | Complete. Videos: successes at `episode_2`, `episode_3`, `episode_4`, `episode_7`; failures at `episode_1`, `episode_5`, `episode_6`, `episode_8`, `episode_9`, `episode_10`. No preparation errors. Does not meet the `9/10` gate. |

### Sample Batch Size Sweep

Fixed parameters unless noted: `main.guide_scale=20.0`; `backend.libero.task_guide_scales=[20.0]*10`; `main.use_diversity=true`; `main.diversity_scale=1.0`; `main.use_fkd=true`; `main.use_vlm_stage_recognition=false`; `perception.vlm_agent.temperature=0.0`; `main.episode_num=10`.

| Run | Swept Parameter | Output Directory | Success | Status |
| --- | --- | --- | --- | --- |
| `rdt_full_sbs10_divs1_gs20_temp0` | `main.sample_batch_size=10` | `outputs/libero/rdt_full_sbs10_divs1_gs20_temp0` | `6/10 = 60.00%` | Complete. Videos: successes at `episode_1`, `episode_2`, `episode_3`, `episode_4`, `episode_6`, `episode_10`; rollout failures at `episode_5`, `episode_8`, `episode_9`; preparation error at `episode_7/error.txt` because VLM-generated `stage2_guidance.txt` returned `int` instead of `torch.Tensor`. Does not meet the `9/10` gate. |
| `rdt_full_divs1_gs20_temp0` | `main.sample_batch_size=20` | `outputs/libero/rdt_full_divs1_gs20_temp0` | `7/10 = 70.00%` | Reused complete diversity-sweep run with matching fixed parameters. Videos: failures at `episode_1`, `episode_5`, `episode_8`; successes at `episode_2`, `episode_3`, `episode_4`, `episode_6`, `episode_7`, `episode_9`, `episode_10`. Does not meet the `9/10` gate. |
| `rdt_full_sbs30_divs1_gs20_temp0` | `main.sample_batch_size=30` | `outputs/libero/rdt_full_sbs30_divs1_gs20_temp0` | `4/10 = 40.00%` | Complete. Videos: successes at `episode_2`, `episode_3`, `episode_6`, `episode_7`; failures at `episode_1`, `episode_4`, `episode_5`, `episode_8`, `episode_9`, `episode_10`. No preparation errors. Does not meet the `9/10` gate. |
| `rdt_full_sbs40_divs1_gs20_temp0` | `main.sample_batch_size=40` | `outputs/libero/rdt_full_sbs40_divs1_gs20_temp0` | `4/10 = 40.00%` | Complete. Videos: successes at `episode_2`, `episode_3`, `episode_4`, `episode_6`; failures at `episode_1`, `episode_5`, `episode_7`, `episode_8`, `episode_9`, `episode_10`. No preparation errors. Does not meet the `9/10` gate. |
| `rdt_full_sbs50_divs1_gs20_temp0` | `main.sample_batch_size=50` | `outputs/libero/rdt_full_sbs50_divs1_gs20_temp0` | `6/10 = 60.00%` | Complete. Videos: successes at `episode_1`, `episode_2`, `episode_3`, `episode_6`, `episode_7`, `episode_10`; failures at `episode_4`, `episode_5`, `episode_8`, `episode_9`. No preparation errors. Does not meet the `9/10` gate. |

### Start Step Sweep

Fixed parameters unless noted: `main.guide_scale=20.0`; `backend.libero.task_guide_scales=[20.0]*10`; `main.sample_batch_size=20`; `main.use_diversity=true`; `main.diversity_scale=1.0`; `main.use_fkd=true`; `main.use_vlm_stage_recognition=false`; `perception.vlm_agent.temperature=0.0`; `main.episode_num=10`. `main.start_step` is an explicit RDT scheduler-timestep threshold: diversity runs while `timestep > start_step`; keypoint guidance and FKD run while `timestep <= start_step`.

| Run | Swept Parameter | Output Directory | Success | Status |
| --- | --- | --- | --- | --- |
| `rdt_full_start50_sbs20_divs1_gs20_temp0` | `main.start_step=50` | `outputs/libero/rdt_full_start50_sbs20_divs1_gs20_temp0` | `5/10 = 50.00%` | Complete. Videos: successes at `episode_2`, `episode_3`, `episode_6`, `episode_7`, `episode_10`; rollout failures at `episode_1`, `episode_4`, `episode_5`, `episode_9`; preparation error at `episode_8/error.txt` because VLM-generated `stage2_guidance.txt` returned `int` instead of `torch.Tensor`. Does not meet the `9/10` gate. |
| `rdt_full_start60_sbs20_divs1_gs20_temp0` | `main.start_step=60` | `outputs/libero/rdt_full_start60_sbs20_divs1_gs20_temp0` | `6/10 = 60.00%` | Complete. Videos: successes at `episode_2`, `episode_3`, `episode_6`, `episode_7`, `episode_8`, `episode_10`; failures at `episode_1`, `episode_4`, `episode_5`, `episode_9`. No preparation errors. Does not meet the `9/10` gate. |
| `rdt_full_start70_sbs20_divs1_gs20_temp0` | `main.start_step=70` | `outputs/libero/rdt_full_start70_sbs20_divs1_gs20_temp0` | `6/10 = 60.00%` | Complete. Videos: successes at `episode_2`, `episode_3`, `episode_6`, `episode_7`, `episode_8`, `episode_10`; failures at `episode_1`, `episode_4`, `episode_5`, `episode_9`. No preparation errors. Does not meet the `9/10` gate. |
| `rdt_full_start80_sbs20_divs1_gs20_temp0` | `main.start_step=80` | `outputs/libero/rdt_full_start80_sbs20_divs1_gs20_temp0` | `3/10 = 30.00%` | Complete. Videos: successes at `episode_2`, `episode_3`, `episode_10`; rollout failures at `episode_1`, `episode_5`, `episode_6`, `episode_7`, `episode_8`, `episode_9`; preparation error at `episode_4/error.txt` because VLM-generated `stage2_guidance.txt` returned `int` instead of `torch.Tensor`. Does not meet the `9/10` gate. |

### VLM Stage Recognition Sweep

Fixed parameters unless noted: `main.guide_scale=20.0`; `backend.libero.task_guide_scales=[20.0]*10`; `main.sample_batch_size=20`; `main.use_diversity=true`; `main.diversity_scale=1.0`; `main.use_fkd=true`; `perception.vlm_agent.temperature=0.0`; `main.episode_num=10`.

| Run | Swept Parameter | Output Directory | Success | Status |
| --- | --- | --- | --- | --- |
| `rdt_full_divs1_gs20_temp0` | `main.use_vlm_stage_recognition=false` | `outputs/libero/rdt_full_divs1_gs20_temp0` | `7/10 = 70.00%` | Reused complete diversity-sweep run with matching fixed parameters. |
| `rdt_full_stage_rec_true_sbs20_divs1_gs20_temp0` | `main.use_vlm_stage_recognition=true` | `outputs/libero/rdt_full_stage_rec_true_sbs20_divs1_gs20_temp0` | `6/10 = 60.00%` | Complete. Videos: successes at `episode_2`, `episode_3`, `episode_4`, `episode_6`, `episode_7`, `episode_10`; failures at `episode_1`, `episode_5`, `episode_8`, `episode_9`. No preparation errors. Does not meet the `9/10` gate. |

## Current Best

Best guided full-suite setting in this evidence file remains `rdt_full_divs1_gs20_temp0`: `main.guide_scale=20.0`, `main.sample_batch_size=20`, `main.use_diversity=true`, `main.diversity_scale=1.0`, `main.use_fkd=true`, `main.use_vlm_stage_recognition=false`, with `7/10 = 70.00%`.

None of the completed guided ablations currently meets the implementation gate of `guided_success_rate >= unguided_success_rate` because the unguided RDT baseline is `9/10 = 90.00%`.

## Evidence Rules

- A full run is judged against `9/10 = 90.00%`.
- Current ablation phase requires complete 10-episode runs; do not early-stop after failures.
- Preparation errors caused by invalid VLM-generated guidance functions are recorded separately from policy execution failures.
- Video paths are relative to the worktree root.
