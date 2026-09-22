# N1 execution-intent descriptor: CPU implementation and fixed-pool replay

Status: **CPU implementation PASS; descriptive historical replay only; online objective UNMEASURED**. Protocol was frozen at `56031d2a6136d6d1f0d0cb95c7d42f77a8158da3` before implementation. No GPU, new episode, API, model or simulator invocation was performed by this executor. CPU tests use stub models. No algorithm tuning or additional candidate was introduced.

## Implementation and invariants

New opt-in `qd_descriptor=target_distance_gripper_duty_v1` uses the projected EEF endpoint at executed action 8, its 3D Euclidean distance to current keypoint0 (meters), and the fraction of the exact eight deployed gripper commands that are +1 (dimensionless). Raw slot10 equal to zero decodes to +1, as in the original action converter. This is command duty, not grasp state or grasp probability.

Radial bounds reuse the historical .05/.95 quantile, .1 expansion, .08m minimum-span computation exactly. Duty bounds are always [0,1]; minimum spatial span does not affect duty. Existing 4×4/capacity-one archive, reward quality, fingerprint ties, replacement, sparse-priority allocation, decoder, eight-action horizon and 176/11 search remain. The resolver rejects combining N1 with changed grids/bounds or later causal-envelope, anchor, secondary-lane or fallback switches. Archive and bounds are recreated each chunk; reset and target-change tests confirm no state reuse.

Candidate profile `configs/qd_ed_final/candidate_n1.json` has `baseline_reference="Q0"`. Its full `profile` dictionary differs from the owned Q0 restored profile **only in qd_descriptor**, including preservation of historical method/label/role metadata. Top-level candidate label is N1. Baseline defaults in `configs/config.yaml` are unchanged.

N1 telemetry uses `qd_descriptor_axes`, `qd_descriptor_bounds`, `qd_descriptor_bounds_by_iter`, `qd_parent_descriptor_values_by_iter`, `qd_archive_descriptor_axis_span_by_iter`, and archive/observer `descriptor_values`. Axes are named `target_distance (m)` and `positive_gripper_command_duty (fraction)`. Misleading XY-meter/SSE fields are omitted for N1. Legacy descriptor output remains unchanged. `utils/eds_eval_vis.py` accepts the new metadata and labels units correctly while preserving legacy rendering. This file extension was explicitly approved by the coordinator.

## Historical fixed-pool replay

Input: the same 20 Q0 sparse traces, 220 saved initial/offspring batches, 3,520 candidate occurrences, 10 historical tasks. Every source trace path and SHA is recorded. Initial and offspring proposals/rewards stay fixed; changed parent allocation does not generate new children in this replay.

**Exact evidence:** Q0 per-iteration cell elite rewards and final selected fingerprints reproduce; decoded duty is exact. All82 previously identified gripper-discordant eliminations differ in duty and73 separate into four duty bins. Quality/tie/slot mechanics are executed by the current core archive implementation, not independently approximated.

**Geometry limitation:** historical saved trajectories contain only t1…t7 in BF16, and do not serialize starting EEF or t8Z. A single bounded attempt to recover a common BF16 start using all seven saved positions found no coordinate fully consistent across all saved streams under current CPU projector arithmetic in all20 traces. The replay therefore uses exact stored t8XY but explicitly approximate t8Z = saved t7Z + eighth Z action × .01 in float32. It does not claim exact historical N1 radial identity. N1 survivor/parent/new-alias counts below are descriptive approximate replay, not exact counterfactual execution evidence or task-success evidence.

| Descriptive fixed-pool statistic | Result |
|---|---:|
| Gripper-discordant Q0 elimination occurrences retained immediately by N1 | 27/82 |
| Those retained occurrences sampled on the next iteration | 25 |
| Original elimination occurrences present in final N1 archive | 21 |
| Parent batches with changed fingerprint multiset | 200/200 |
| Parent slot positions with changed fingerprint | 3,147/3,200 |
| New same-cell candidate-pair aliases introduced | 7,814 |
| Old same-cell candidate-pair aliases separated | 986 |
| Median occupied cells Q0 → N1 | 16 → 4 |
| Median original XY cells represented by N1 survivors | 4 |
| Updates with more / fewer positive-duty bins | 51 / 0 out of220 |
| Median duty-bin count Q0 → N1 | 1 → 1 |
| Reconstructed fixed-pool global reward-best invariance | 220/220 updates |

These results demonstrate a mechanism opportunity and substantial information loss: radial distance collapses azimuth and vertical direction, while duty compresses action timing. It would be incorrect to report pairwise73/82 separation as73 rescued or useful branches. Many populations have only one duty mode, causing lower occupancy even though maximum capacity remains16. Parent changes can reflect both regained grip diversity and lost spatial diversity. No information-loss threshold was added after seeing these results and bin values were not tuned.

The next scientific decision requires a same-round corrected-input Q0/P2/N1 comparison under the frozen Dev protocol. The implementation is not promoted on proxy counts. Actual online parent duty and observed next-chunk feedback must be recorded; all unexecuted candidate outcomes remain Unknown.

Artifact: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/iteration_001_execution_intent/fixed-pool-replay.json`, SHA256 `4e0d834b6dca576ce687afc422d41dc0ac02c4abd249dc60a4d40ef241cbe19c`.

Reproduce from owned worktree:

```bash
CUDA_VISIBLE_DEVICES='' /home/hynx/miniconda3/envs/vla-pilot/bin/python scripts/qd_ed_execution_intent_replay.py \
  --diagnostic /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/iteration_000_intake/executable-behavior-diagnostic.json \
  --output /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/iteration_001_execution_intent/fixed-pool-replay.json
```

## Actual compute accounting (common observational engineering change)

At the coordinator's request, RDTSteer exposes `get_episode_compute_counters()` and `reset_episode_compute_counters()`. `reset()` clears totals; `reset_stage()` does not. The getter returns an independent JSON-safe snapshot. The runtime agent owns writing unified per-episode records from main; this executor did not edit main.py or the new runner.

Counters increment at invocation boundaries, including failed invocation attempts; they are not inferred from176 candidate evaluations:

- `model_forward_calls`, `model_batch_rows`, `model_forward_batch_sizes`: actual DiT adapter invocations and particle batch sizes, including guided and unguided paths.
- `denoising_invocations`, `model_denoising_steps`, `denoising_step_batch_rows`, `renoise_invocations`: actual loop/scheduler boundaries; scheduler steps are separate from DiT calls.
- `reward_calls`, `reward_evaluations`: actual provider function invocations and candidate rows. `reward_scoring_batches` counts actual `_score_particles` calls with a provider.
- `rbf_gradient_calls`, `rbf_gradient_batch_rows`: actual diversity-gradient computation attempts, excluding B<2/no-adapter early exits.
- `vision_encoder_forward_calls`, `vision_encoder_batch_rows`, `text_encoder_forward_calls`, `text_encoder_batch_rows`: temporary observational pre-hooks on actual encoder modules. A cached text embedding does not create a fictitious encoder forward.
- `guided_chunks`, `unguided_chunks`: new chunk dispatches, excluding cached-action reuse.

No counters alter actions, RNG, reward semantics or model scheduling. DiT counters do not implicitly cover DINO/perception; other components require their own named telemetry. Provider HTTP attempts are implemented by the runtime agent separately. All source-side preconditions and model/provider failures still propagate normally.

**Search budget is not total reward cost.** Existing qualitative/pretest paths score intermediate initial/rollout populations in addition to the11 search batches. Actual `reward_scoring_batches` can exceed the summed `score_call_count` in normal traced runs; enforcing equality would reject valid tracing and hide its overhead. The runner agent was notified. For complete EDS-only runs, guided-chunk count can be compared with EDS metric rows, while failures retain their attempt accounting separately.

## Validation

- Full existing and N1-specific QD/RDT/visual suite: **417 passed**, one pre-existing NetworkX deprecation warning. Command: `CUDA_VISIBLE_DEVICES='' /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -q tests/test_qd_ed_archive.py tests/test_rdt_steer.py tests/test_eds_eval_vis.py`.
- Then added explicit unguided/cached-action compute coverage; targeted compute suite: **2 passed**. Together the files now contain418 test cases; the coordinator will run integrated final validation.
- N1 tests exercise t8 vs deliberately different t7, full3D distance, exact8 decoded commands including raw zero, fixed-duty boundaries, permutation-stable bounds, unchanged radial rule, full-loop176/11,16 parent slots, <=16 elites, selected fingerprint identity, honest metadata, target changes, stage reset and episode reset.
- Compute tests verify actual multiple-provider evaluation counts, DiT batch sizes, no RNG change, getter isolation, stage-vs-episode reset, unguided5-step inference and zero additional cost on cached-action reuse.
- Renderer covers legacy XY and new radial/duty metadata. Existing legacy output/config/archive/steering regressions pass. `git diff --check` passes.

Absolute primary success score for N1: **unmeasured**. Baseline historical Q0 remains2/10. GPU7/provider/runtime gates remain outside this CPU result. No commit was created by this executor.

## Source fingerprints at executor handoff

- `core/qd_ed.py`: `4415ea7f16029e2fa2e7528c1f7065ba673b7a5a512723bfa9611f992298daa4`
- `core/rdt_policy_steer.py`: `82c8515542780acc5389d3043d7f25e14e9d23f6149fb067a6dfa99fb9aa584e`
- `core/eds_eval_metrics.py`: `0e07c57167dd92c07a31395f6ebba0b56d0f65bc62f4fb1e4d5fb30549fd6ae0`
- `utils/eds_eval_vis.py`: `d155d2b2e6e72bd877899c1fdc6f0e57d847ea63d68b55a74a0606c90ab86676`
- `tests/test_qd_ed_archive.py`: `d8f392c2c554889cd3ba0af18d3079bab0948d5b1deaaba5375de22a7f0c00b3`
- `tests/test_rdt_steer.py`: `0fa5a80ac5aeeaec91ac56f16b7040c6d193117a131efca352254f5cfbb27689`
- `tests/test_eds_eval_vis.py`: `34cd0e13b11bdafdb956ca40b5c042d1fcf39d9a68ba1bc352bd34fd8f45ebed`
- `scripts/qd_ed_execution_intent_replay.py`: `b602818b3753c6110d2baf9c4d2e9fed5a23f9456829c71912e425bb90280bf1`
- `configs/qd_ed_final/candidate_n1.json`: `5e74d72f108df53897e790677154c5ca3691b1aeb318297168d3bffcb84bfe3c`
- `experiments/iteration_001_execution_intent/protocol.md`: `e3d3c2ed50db4a845e4d0713671db225c96f124ca8719d171e5d7006f0a5e0b0`

## Final adjudication — 2026-09-22

The prospective next steps above describe the original executor handoff, not an active queue. The N1 cohort is now **INVALID_NOT_PROMOTABLE**: its original Q0/task0 control is nonretryable invalid, and four dispatches on that one cell plus the remaining 29 unique cells would require 33 attempts, exceeding the frozen 30-attempt cap. Recovery attempts count toward that cap. The required 20 valid original controls were never obtained. N1 itself has zero online evaluations; its algorithm effect and success rate remain Unknown.

All later coordinator diagnostics used physical GPU3. The final native-resource lifecycle probe failed the wrist RGB parity gate before model loading. No diagnostic prototype was accepted as a production repair. A bounded review of the remaining executed-horizon quality direction lacked exact provider-quality reconstruction, actual selection changes and linkage to lawful next observations; historical XY nearest-target argmin differences do not establish quality misranking.

The study is closed under the user specification's bounded-review stop rule as **TARGET_NOT_MET / NO_ADOPTION**. It used 1.0262591123256264 of 48 GPU-hours and 11 episode attempts (8 aborted, 3 invalid, 0 valid). Validation and formal were not started. No cohort retry, new candidate or automatic GPU dispatch remains authorized under this concluded study. Complete outcomes, method, cost limitations and evidence needed for further research are recorded in the [final report](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/docs/03_evidence/qd_ed_final/final-report.md).
