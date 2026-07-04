# RBF-Diverse Initial Sampling Parameter Sweep

- Branch: `exp/eds-init-pg-diverse-sampling`
- Worktree: `/home/hynx/VLA-Pilot++/.worktrees/exp/eds-init-pg-diverse-sampling`
- Base commit for these runs: `2b8ec51c8ffac70869cfe92e9ac2d0e6eab3f082`
- GPU: physical GPU 3, NVIDIA H200 NVL
- `CUDA_VISIBLE_DEVICES`: `3`
- Suite/task: `libero_object`, `backend.libero.task_ids_filter=[0]`
- Task: pick up the alphabet soup and place it in the basket
- Episodes per run: `1`
- Guidance cache: `/home/hynx/VLA-Pilot++/outputs/libero/2026-06-04_13-21-01/episode_1/vlm_agent`
- Offline VLM mode: `main.use_vlm_stage_recognition=false`, `perception.gemini_grounding.enabled=false`, `OPENAI_API_KEY=dummy`, proxy env vars cleared.

An earlier run used the wrong cached guidance directory for task 0 and was discarded. The results below use the matching alphabet-soup task cache.

## Commands

Baseline iid EDS was executed through:

```bash
python scripts/rdt_eds_eval_runner.py run-level --level level2 --episodes 1 --gpus 3 --timeout-seconds 28800 --cached-functions-dir /home/hynx/VLA-Pilot++/outputs/libero/2026-06-04_13-21-01/episode_1/vlm_agent --offline-vlm
```

Manual RBF sweeps used the same generated level2 command with only these overrides changed:

```text
main.eds_eval.method_label=<sweep_label>
main.eds_eval.job_id=<sweep_job_id>
main.eds_eval.output_dir=outputs/rdt_eds_eval/<sweep_job_id>/eds_eval
hydra.run.dir=outputs/rdt_eds_eval/<sweep_job_id>
main.eds_config.initial_sampling_mode=rbf_diverse_denoise
main.eds_config.initial_diversity_scale=<scale>
main.eds_config.initial_diversity_start_ratio=<ratio_or_null>
```

## Results

| Run | Scale | Start Ratio | Success | Records | Fallback | Diversity Steps | Init Latency Mean | Select Latency Mean | Initial Diversity Mean | Final Diversity Mean | Initial Best Reward Mean | Selected Reward Mean | Target Distance After Mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `iid_p16_c10` | n/a | n/a | 0/1 | 30 | 0 | 0 | 0.370940 | 2.715316 | 5.840201 | 3.693156 | -0.011359 | -0.012529 | 0.095691 |
| `rbf_scale05_start_null` | 0.5 | null | 0/1 | 30 | 0 | 1 | 0.427454 | 2.735044 | 5.957725 | 3.694549 | -0.011357 | -0.012539 | 0.095846 |
| `rbf_scale1_start_null` | 1.0 | null | 0/1 | 30 | 0 | 1 | 0.426961 | 2.729208 | 5.960670 | 3.694549 | -0.011341 | -0.012539 | 0.095846 |
| `rbf_scale2_start_null` | 2.0 | null | 0/1 | 30 | 0 | 1 | 0.431605 | 2.763544 | 5.956101 | 3.542112 | -0.011891 | -0.012940 | 0.097091 |
| `rbf_scale1_start025` | 1.0 | 0.25 | 0/1 | 30 | 0 | 1 | 0.427613 | 2.746917 | 5.960670 | 3.694549 | -0.011341 | -0.012539 | 0.095846 |
| `rbf_scale1_start05` | 1.0 | 0.5 | 0/1 | 30 | 0 | 2 | 0.442669 | 2.762723 | 5.165898 | 3.715309 | -0.011805 | -0.012596 | 0.096163 |

## Gate Check

| Gate | Criterion | Observation | Verdict |
|---|---|---|---|
| Fallback | `initial_diversity_fallback_used=false` | All RBF sweeps recorded fallback count `0`. | pass |
| Initial diversity | Higher than iid baseline | Scale 0.5/1.0/2.0 and start 0.25 are above baseline; start 0.5 is below baseline. | partial |
| Endpoint spread | Higher than baseline | Not yet recorded as an explicit numeric metric in the runner. | not measured |
| Selected reward | Not lower than iid baseline | Best RBF selected reward mean is `-0.012539`, slightly below iid `-0.012529`. | fail |
| Final target distance | Not worse than iid baseline | Best RBF target distance after is `0.095846`, slightly worse than iid `0.095691`. | fail |
| Level2 smoke success | At least not worse than iid | iid and all RBF sweeps are `0/1`; no improvement. | fail |
| Latency | Acceptable overhead | RBF init latency increases about `0.056s`; select-action latency stays within about `0.02s-0.05s` of iid for scale 0.5/1.0. | pass |

## Interpretation

The RBF-diverse initial sampler is operational: it records the expected mode, applies one or two diversity steps depending on scheduler threshold, produces no fallback, and adds only modest latency. On this cached level2 task, however, the current glue implementation does not improve success rate, selected reward, or final target distance.

The `start_ratio=0.25` run matched the default `null` result exactly in the reported population metrics. With the current five-step scheduler, both settings resolve to the same effective diversity step count. Increasing to `start_ratio=0.5` enables two diversity steps but reduces initial diversity and does not improve downstream metrics. Increasing `initial_diversity_scale` to `2.0` hurts selected reward and target distance. Lowering scale to `0.5` preserves the small diversity gain but still does not pass reward or distance gates.

Full OOD evaluation is intentionally not launched from these results. The level2 smoke gates are not met, and a final code review also identified compatibility/cache telemetry issues that must be fixed before treating OOD metrics as trustworthy.

## Artifacts

- Baseline iid metrics: `outputs/rdt_eds_eval/level2_libero_object_p16_c10/eds_eval/eds_metrics.jsonl`
- Default RBF metrics: `outputs/rdt_eds_eval/level2_libero_object_eds_rbf_diverse_initial/eds_eval/eds_metrics.jsonl`
- Scale 0.5 metrics: `outputs/rdt_eds_eval/level2_libero_object_eds_rbf_scale05/eds_eval/eds_metrics.jsonl`
- Scale 2.0 metrics: `outputs/rdt_eds_eval/level2_libero_object_eds_rbf_scale2/eds_eval/eds_metrics.jsonl`
- Start 0.25 metrics: `outputs/rdt_eds_eval/level2_libero_object_eds_rbf_start025/eds_eval/eds_metrics.jsonl`
- Start 0.5 metrics: `outputs/rdt_eds_eval/level2_libero_object_eds_rbf_start05/eds_eval/eds_metrics.jsonl`
