# Level 4 VLS/PI05 LIBERO-PRO OOD Evaluation

Timestamp: `2026-06-20T17:17:56+00:00`

## Experiment Overview

- Benchmark: LIBERO-PRO OOD evaluation on `libero_object`.
- Suites: `libero_object_object`, `libero_object_swap`, `libero_object_lan`, `libero_object_task`, `libero_object_env`, `libero_object_temp`.
- New methods: `RDT+VLS`, `PI05+VLS`, `PI05 unguided`.
- Episodes per job: `10`.
- Strict perturbation mode: `backend.libero.strict_perturbations=true`.
- GPU allocation: runner configured for physical GPU2/GPU3. This host's EGL order differs from CUDA order, so GPU2 uses `CUDA_VISIBLE_DEVICES=2`, `MUJOCO_EGL_DEVICE_ID=2`, `device=cuda:0`; GPU3 uses `CUDA_VISIBLE_DEVICES=3`, `MUJOCO_EGL_DEVICE_ID=1`, `device=cuda:0`. The local `vla-pilot` robosuite import-time EGL assertion was patched to permit this CUDA/EGL split.
- New job completion: `18/18`.
- Existing RDT+EDS comparison report: `docs/03_evidence/eds_steering/level_4_libero_pro_ood.md`.

## Environment Patch Note

This host's EGL device order is `EGL0 -> GPU0`, `EGL1 -> GPU3`, `EGL2 -> GPU2`, `EGL3 -> GPU1`. robosuite's default import-time check incorrectly assumes `MUJOCO_EGL_DEVICE_ID` must be one of the CUDA visible device ordinals. To run on physical GPU3 without exposing physical GPU1 to CUDA, the local conda environment file was patched:

- Patched file: `/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/robosuite/utils/binding_utils.py`
- Patch intent: keep `MUJOCO_EGL_DEVICE_ID` constrained to an integer, but allow it to differ from `CUDA_VISIBLE_DEVICES`.
- Reason: GPU3 jobs need `CUDA_VISIBLE_DEVICES=3` and `MUJOCO_EGL_DEVICE_ID=1`; without the patch, robosuite rejects this valid CUDA/EGL split before LIBERO starts.

## Executive Summary

- All 18 new comparison jobs completed successfully: `6 suites x 3 methods x 10 episodes = 180 episodes`, with `180/180` per-episode videos saved.
- RDT+VLS is weak on this LIBERO-PRO OOD setup: aggregate `5/60` (`8.33%`). It only improves over RDT unguided on `env` and `temp`, where RDT unguided was `0/10` and RDT+VLS reached `1/10`.
- Existing RDT+EDS remains stronger than RDT+VLS in aggregate: RDT unguided `9/60`, RDT+EDS softmax `10/60`, RDT+EDS CEM `12/60`, RDT+VLS `5/60`.
- PI05 is much stronger than RDT on this benchmark: PI05 unguided reaches `32/60` (`53.33%`) and PI05+VLS reaches `31/60` (`51.67%`).
- PI05+VLS is not uniformly beneficial. It improves hard spatial/semantic rebinding suites (`swap`: `0/10 -> 4/10`; `task`: `1/10 -> 3/10`), is neutral on `env` (`5/10 -> 5/10`), and hurts easier/strong-base suites (`object`, `lan`, `temp`).
- No infrastructure failure was observed in the final run: no timeout, no perturbation fallback, no VLM/API crash, no checkpoint failure, and no missing videos.

## Parameter Sources

### RDT+VLS

- Source selected: `/home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-gt-rollout-reintegration/outputs/libero/rdt_full_sbs50_divs1_gs20_temp0`. This historical RDT+VLS base-`libero_object` ablation reports `6/10` and is tied for best among the documented VLS ablations found locally.
- Source results: `/home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-gt-rollout-reintegration/outputs/libero/rdt_full_sbs50_divs1_gs20_temp0/results.txt`; source overrides: `/home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-gt-rollout-reintegration/outputs/libero/rdt_full_sbs50_divs1_gs20_temp0/.hydra/overrides.yaml`.
- Current-config mapping used for this run: `main.vls_config.sample_batch_size=50`, `main.vls_config.guide_scale=20.0`, `main.vls_config.use_diversity=true`, `main.vls_config.diversity_scale=1.0`, `main.vls_config.use_fkd=true`, `main.use_vlm_stage_recognition=false`, `perception.vlm_agent.temperature=0.0`.
- Selection rationale: it is the best documented RDT+VLS setting with no ambiguous deprecated key mapping; the tied `start_step=70` result was not selected because current config uses grouped `main.vls_config.start_ratio` semantics.

### PI05+VLS

- Policy: `policy.type=pi05` using default `configs/policy.yaml` PI05 settings.
- Guidance: `main.use_guidance=true`, `main.guidance_type=vls`; VLS parameters are the default grouped `main.vls_config` from `configs/config.yaml`.
- No PI05-specific VLS tuning was applied.

### PI05 Unguided

- Policy: `policy.type=pi05` using default `configs/policy.yaml` PI05 settings.
- Guidance is disabled via `main.use_guidance=false`.

## Complete Result Table

| Suite | Method | Complete | Status | Success | SR % | Wall-clock s | Videos | VLS/debug artifacts | Log | Output | Failure reason |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| `libero_object_object` | `RDT+VLS` | `True` | `done` | 1/10 | 10.00 | 687.839 | 10 | 60 | `docs/03_evidence/eds_steering/vls_pi05_ood_eval/logs/level4_libero_object_object_rdt_vls.log` | `outputs/ood_eval/level4_libero_object_object_rdt_vls` | - |
| `libero_object_object` | `PI05+VLS` | `True` | `done` | 7/10 | 70.00 | 641.011 | 10 | 60 | `docs/03_evidence/eds_steering/vls_pi05_ood_eval/logs/level4_libero_object_object_pi05_vls.log` | `outputs/ood_eval/level4_libero_object_object_pi05_vls` | - |
| `libero_object_object` | `PI05 unguided` | `True` | `done` | 10/10 | 100.00 | 207.011 | 10 | 0 | `docs/03_evidence/eds_steering/vls_pi05_ood_eval/logs/level4_libero_object_object_pi05_unguided.log` | `outputs/ood_eval/level4_libero_object_object_pi05_unguided` | - |
| `libero_object_swap` | `RDT+VLS` | `True` | `done` | 0/10 | 0.00 | 698.879 | 10 | 60 | `docs/03_evidence/eds_steering/vls_pi05_ood_eval/logs/level4_libero_object_swap_rdt_vls.log` | `outputs/ood_eval/level4_libero_object_swap_rdt_vls` | - |
| `libero_object_swap` | `PI05+VLS` | `True` | `done` | 4/10 | 40.00 | 687.885 | 10 | 60 | `docs/03_evidence/eds_steering/vls_pi05_ood_eval/logs/level4_libero_object_swap_pi05_vls.log` | `outputs/ood_eval/level4_libero_object_swap_pi05_vls` | - |
| `libero_object_swap` | `PI05 unguided` | `True` | `done` | 0/10 | 0.00 | 284.472 | 10 | 0 | `docs/03_evidence/eds_steering/vls_pi05_ood_eval/logs/level4_libero_object_swap_pi05_unguided.log` | `outputs/ood_eval/level4_libero_object_swap_pi05_unguided` | - |
| `libero_object_lan` | `RDT+VLS` | `True` | `done` | 2/10 | 20.00 | 658.453 | 10 | 60 | `docs/03_evidence/eds_steering/vls_pi05_ood_eval/logs/level4_libero_object_lan_rdt_vls.log` | `outputs/ood_eval/level4_libero_object_lan_rdt_vls` | - |
| `libero_object_lan` | `PI05+VLS` | `True` | `done` | 8/10 | 80.00 | 520.282 | 10 | 60 | `docs/03_evidence/eds_steering/vls_pi05_ood_eval/logs/level4_libero_object_lan_pi05_vls.log` | `outputs/ood_eval/level4_libero_object_lan_pi05_vls` | - |
| `libero_object_lan` | `PI05 unguided` | `True` | `done` | 10/10 | 100.00 | 214.690 | 10 | 0 | `docs/03_evidence/eds_steering/vls_pi05_ood_eval/logs/level4_libero_object_lan_pi05_unguided.log` | `outputs/ood_eval/level4_libero_object_lan_pi05_unguided` | - |
| `libero_object_task` | `RDT+VLS` | `True` | `done` | 0/10 | 0.00 | 692.925 | 10 | 60 | `docs/03_evidence/eds_steering/vls_pi05_ood_eval/logs/level4_libero_object_task_rdt_vls.log` | `outputs/ood_eval/level4_libero_object_task_rdt_vls` | - |
| `libero_object_task` | `PI05+VLS` | `True` | `done` | 3/10 | 30.00 | 777.539 | 10 | 60 | `docs/03_evidence/eds_steering/vls_pi05_ood_eval/logs/level4_libero_object_task_pi05_vls.log` | `outputs/ood_eval/level4_libero_object_task_pi05_vls` | - |
| `libero_object_task` | `PI05 unguided` | `True` | `done` | 1/10 | 10.00 | 272.664 | 10 | 0 | `docs/03_evidence/eds_steering/vls_pi05_ood_eval/logs/level4_libero_object_task_pi05_unguided.log` | `outputs/ood_eval/level4_libero_object_task_pi05_unguided` | - |
| `libero_object_env` | `RDT+VLS` | `True` | `done` | 1/10 | 10.00 | 721.073 | 10 | 60 | `docs/03_evidence/eds_steering/vls_pi05_ood_eval/logs/level4_libero_object_env_rdt_vls.log` | `outputs/ood_eval/level4_libero_object_env_rdt_vls` | - |
| `libero_object_env` | `PI05+VLS` | `True` | `done` | 5/10 | 50.00 | 680.210 | 10 | 60 | `docs/03_evidence/eds_steering/vls_pi05_ood_eval/logs/level4_libero_object_env_pi05_vls.log` | `outputs/ood_eval/level4_libero_object_env_pi05_vls` | - |
| `libero_object_env` | `PI05 unguided` | `True` | `done` | 5/10 | 50.00 | 286.372 | 10 | 0 | `docs/03_evidence/eds_steering/vls_pi05_ood_eval/logs/level4_libero_object_env_pi05_unguided.log` | `outputs/ood_eval/level4_libero_object_env_pi05_unguided` | - |
| `libero_object_temp` | `RDT+VLS` | `True` | `done` | 1/10 | 10.00 | 720.948 | 10 | 60 | `docs/03_evidence/eds_steering/vls_pi05_ood_eval/logs/level4_libero_object_temp_rdt_vls.log` | `outputs/ood_eval/level4_libero_object_temp_rdt_vls` | - |
| `libero_object_temp` | `PI05+VLS` | `True` | `done` | 4/10 | 40.00 | 751.456 | 10 | 60 | `docs/03_evidence/eds_steering/vls_pi05_ood_eval/logs/level4_libero_object_temp_pi05_vls.log` | `outputs/ood_eval/level4_libero_object_temp_pi05_vls` | - |
| `libero_object_temp` | `PI05 unguided` | `True` | `done` | 6/10 | 60.00 | 264.416 | 10 | 0 | `docs/03_evidence/eds_steering/vls_pi05_ood_eval/logs/level4_libero_object_temp_pi05_unguided.log` | `outputs/ood_eval/level4_libero_object_temp_pi05_unguided` | - |

## Comparison With Existing RDT+EDS Level 4

| Suite | RDT unguided | RDT+EDS softmax | RDT+EDS CEM | RDT+VLS | PI05 unguided | PI05+VLS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `libero_object_object` | 60.00 | 30.00 | 50.00 | 10.00 | 100.00 | 70.00 |
| `libero_object_swap` | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 40.00 |
| `libero_object_lan` | 30.00 | 60.00 | 60.00 | 20.00 | 100.00 | 80.00 |
| `libero_object_task` | 0.00 | 0.00 | 0.00 | 0.00 | 10.00 | 30.00 |
| `libero_object_env` | 0.00 | 10.00 | 10.00 | 10.00 | 50.00 | 50.00 |
| `libero_object_temp` | 0.00 | 0.00 | 0.00 | 10.00 | 60.00 | 40.00 |

## Runtime / Latency

Wall-clock is measured by the batch runner around each full 10-episode `main.py` process. It includes model loading, VLM calls, LIBERO reset/rendering, policy inference, and video writing.

| Method | Jobs | Aggregate success | Mean wall-clock / 10 episodes | Main interpretation |
| --- | ---: | ---: | ---: | --- |
| `RDT+VLS` | 6 | 5/60 | 696.69 s | Slowest RDT baseline here because it uses `sample_batch_size=50` plus VLS/FKD steering. |
| `PI05+VLS` | 6 | 31/60 | 676.40 s | Similar wall-clock to RDT+VLS because VLS perception/API and guided sampling dominate. |
| `PI05 unguided` | 6 | 32/60 | 254.94 s | About 2.6x faster than PI05+VLS and slightly better aggregate SR in this run. |

The runtime result matters: PI05+VLS only pays off where it changes the outcome, mainly `swap` and `task`. On `object`, `lan`, and `temp`, the extra VLS cost reduces success rate relative to PI05 unguided.

## Perturbation-Wise Analysis

### `libero_object_object`

- OOD type: object/visual instance replacement.
- Result summary: Best observed method is `pi05_unguided` at 100.00%. 0/6 compared method results are zero.
- Interpretation: PI05 already handles this object/visual perturbation extremely well without guidance. VLS hurts PI05 (`100% -> 70%`) and hurts RDT relative to both RDT unguided (`60%`) and RDT+EDS CEM (`50%`). This suggests VLS can over-steer or select trajectories away from a strong policy prior when the base policy already localizes the object correctly.

### `libero_object_swap`

- OOD type: target-distractor initial-position swap.
- Result summary: Best observed method is `pi05_vls` at 40.00%. 5/6 compared method results are zero.
- Interpretation: This is the clearest positive VLS result. RDT unguided, RDT+EDS, RDT+VLS, and PI05 unguided are all `0/10`, while PI05+VLS reaches `4/10`. That indicates VLS can help PI05 recover from a broken spatial prior by using VLM/keypoint guidance, but the same guidance is not enough to rescue RDT's action prior.

### `libero_object_lan`

- OOD type: language paraphrase with unchanged physical task.
- Result summary: Best observed method is `pi05_unguided` at 100.00%. 0/6 compared method results are zero.
- Interpretation: Existing RDT+EDS was strong here (`60%`) while RDT+VLS is only `20%`, below RDT unguided (`30%`). PI05 unguided is already perfect (`10/10`), so PI05+VLS only adds overhead and reduces success to `8/10`. For pure language paraphrase OOD, EDS is the better RDT steering result from the available evidence, while PI05 does not need VLS on this 10-episode run.

### `libero_object_task`

- OOD type: task/goal/object-of-interest remapping.
- Result summary: Best observed method is `pi05_vls` at 30.00%. 4/6 compared method results are zero.
- Interpretation: RDT remains at `0/10` for unguided, EDS, and VLS, confirming that these RDT steering variants do not solve semantic goal/object rebinding. PI05 has some base robustness (`1/10`) and VLS improves it to `3/10`, suggesting VLS can help when the policy can already produce some relevant trajectories.

### `libero_object_env`

- OOD type: environment/support-surface replacement.
- Result summary: Best observed method is `pi05_vls` at 50.00%. 1/6 compared method results are zero.
- Interpretation: RDT+VLS matches the small RDT+EDS gain (`1/10`) over RDT unguided (`0/10`), but remains weak. PI05 is much stronger at `5/10`, and VLS is neutral (`5/10 -> 5/10`). This looks like a policy-capacity/generalization gap more than a guidance-only problem.

### `libero_object_temp`

- OOD type: temp generation under active evaluation_config flags.
- Result summary: Best observed method is `pi05_unguided` at 60.00%. 3/6 compared method results are zero.
- Interpretation: Under the current LIBERO-PRO config, `temp` is environment-style perturbation with a different init set. RDT+VLS reaches `1/10`, while RDT unguided and RDT+EDS are `0/10`; this is a minimum positive RDT+VLS signal. PI05 unguided is strongest (`6/10`), and PI05+VLS drops to `4/10`, again showing that VLS can hurt when the base PI05 policy already has a good action prior.

## Failure Taxonomy

| Category | Jobs / evidence |
| --- | --- |
| timeout | - |
| grasp failure | - |
| wrong object / wrong target | - |
| language/goal binding failure | - |
| perturbation loading failure | - |
| VLM/API failure | - |
| policy loading/checkpoint failure | - |
| EGL/render device failure | - |
| task execution failure; inspect videos for grasp/wrong-object/language binding | - |
| missing episode videos | - |
| success parsing failure | - |

Automatic taxonomy only captures infrastructure and parse failures. It does not label behavior-level failures from video. For low-SR or zero-SR jobs, the saved videos and `episode_*/vlm_agent` artifacts should be used to manually separate grasp failure, wrong-object selection, wrong-target placement, and language/goal binding errors. The most important behavior-review targets are:

- `outputs/ood_eval/level4_libero_object_swap_rdt_vls`: `0/10`, tests whether RDT+VLS still goes to canonical positions after swap.
- `outputs/ood_eval/level4_libero_object_task_rdt_vls`: `0/10`, tests whether RDT+VLS binds the remapped object of interest.
- `outputs/ood_eval/level4_libero_object_swap_pi05_vls`: `4/10`, inspect successful vs failed episodes to understand when VLS fixes spatial swaps.
- `outputs/ood_eval/level4_libero_object_object_pi05_vls`: `7/10` vs PI05 unguided `10/10`, inspect whether VLS over-steers otherwise successful PI05 trajectories.

## Gate And Conclusions

- RDT+VLS beats RDT unguided on suites: `libero_object_env`, `libero_object_temp`.
- PI05 unguided beats RDT unguided on suites: `libero_object_object`, `libero_object_lan`, `libero_object_task`, `libero_object_env`, `libero_object_temp`.
- PI05+VLS beats PI05 unguided on suites: `libero_object_swap`, `libero_object_task`.
- VLS stability should be judged per perturbation suite; aggregate SR alone hides whether gains come from language, object, or geometry shifts.
- Remaining zero-SR suites should be debugged by inspecting saved episode videos, VLM outputs under `episode_*/vlm_agent`, and hydra overrides to separate policy failures from perturbation/API failures.

Detailed conclusions:

- RDT+VLS does not outperform RDT+EDS overall on this Level-4 benchmark. RDT+VLS is `5/60`, while existing RDT+EDS CEM is `12/60` and RDT+EDS softmax is `10/60`.
- RDT+VLS provides only weak OOD evidence: it gets nonzero success on `object`, `lan`, `env`, and `temp`, but it is worse than RDT unguided on `object` and `lan`, and only improves from `0/10` to `1/10` on `env` and `temp`.
- PI05 unguided is the strongest aggregate policy among the new controls (`32/60`), narrowly above PI05+VLS (`31/60`) and far above RDT+VLS (`5/60`).
- PI05+VLS is useful for the hardest localization/rebinding cases (`swap`, `task`) but not as a default always-on improvement. The same guidance hurts `object`, `lan`, and `temp`.
- VLS has policy-dependent value: it can steer PI05 when PI05 has a reachable action prior, but it does not reliably rescue RDT on `swap` or `task`.
- The recommended next step is not a larger blind rerun. First inspect videos for `swap` and `task` successes/failures, then tune VLS gating or stage-specific activation so VLS is applied only when the base policy is likely to be wrong.

## Completion Audit

- Jobs with complete valid outputs: `18/18`.
- Status CSV: `docs/03_evidence/eds_steering/vls_pi05_ood_eval/job_status.csv`.
- Markers: `docs/03_evidence/eds_steering/vls_pi05_ood_eval/markers`.
- All 18 jobs have `results.txt`, 10 videos, strict perturbation config, and parseable success metrics.
