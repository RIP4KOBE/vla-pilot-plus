# LIBERO-PRO Object-Swap 720-Step VLM Stage Recognition Ablation Report

Timestamp: `2026-08-01T03:03:01+00:00`

Verdict: `promising`

## 中文执行摘要

- 四组 720-step 配对实验均通过 validity gate：P1 OFF `1/10`、P1 ON `1/10`、P2 OFF `0/10`、P2 ON `3/10`。P2 的 Stage Recognition 带来 `+3` 个成功任务、`+30 pp`，达到“有希望”判据，但没有达到工程目标 `>=5/10`。
- P1 的总成功率没有变化，且成功任务从 Task 3 换成 Task 1；P2 新增成功发生在 Task 3、8、9。因此 Stage Recognition 的收益具有明显参数与任务依赖，不能从本轮 10 个固定任务外推为稳定提升。
- 当前机制并不是可靠的“抓取确认后再关闭 steering”：P1/P2 的全部 Stage ON episode 都在 step 16-128 内首次关闭 guidance，P2 更是在 10/10 个任务的 step 16-32 关闭。视频显示多数关停发生在目标尚未稳定抓取之前。
- Stage ON 的主要实际作用更接近“短前缀 EDS 后切回 unguided RDT prior”。这可以解释 P2 的部分收益，也解释 P1 中原本成功的 Task 3 被破坏，以及大量 premature OFF、状态震荡和错误目标交互。
- 结论：`use_vlm_stage_recognition=true` 在 P2 上给出值得继续优化的正信号，但当前版本不应直接作为最终方案。下一轮应优先部署可验证抓取的单调状态机、task-specific stage context 和结构化输出，再以同一 10-task protocol 冲击 `>=5/10`。

## Experiment Overview

- Suite: `libero_object_swap` with strict LIBERO-PRO perturbations.
- Jobs: `4`; episodes per job: `10`; total episodes: `40`.
- All new jobs use `max_episode_steps=720`, `seed=0`, Gemini grounding OFF, and cached guidance.
- Stage Recognition is the only within-run A/B variable for each P1/P2 profile.
- Historical runs used 240-step Stage OFF. Because no 240-step Stage ON cell exists, this is not a complete 2x2 factorial experiment and no horizon x stage interaction is claimed.
- GPU policy: GPU 2 only.
- Output root: `outputs/ood_eval/stage_recognition_ablation`.
- Cached guidance: `/home/hynx/VLA-Pilot++/outputs/libero/2026-06-04_13-21-01/episode_1/vlm_agent`.
- Policy/checkpoint and all resolved parameters are preserved in each job's `.hydra/config.yaml` and `.hydra/overrides.yaml`.
- Policy: RDT EMA weights from `/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object`, with an 8-action chunk horizon and 20 Hz control frequency.
- Stage model: `gemini-2.5-flash`, temperature `0`, real Poe-compatible API, and Gemini grounding disabled.
- Common EDS: `population_size=16`, `cem_iters=10`, `use_cem=false`, `num_elites=16`, `temperature=0.1`.
- Initial sampler: `rbf_diverse_denoise`, scale `20`, start ratio `0.8`.
- P1 rollout: renoise `2 -> 1`, RBF scale `5`, start ratio `0.2`, iterations `all`.
- P2 rollout: renoise `3 -> 1`, RBF scale `20`, start ratio `0.6`, iterations `all`.
- Stage query limit: `50`; complete resolved settings are stored in every job's `.hydra/config.yaml` and `.hydra/overrides.yaml`.
- Formal compute time was approximately `13,400 s` (`3 h 43 min`) across the four serial GPU2 jobs. P1 OFF is inferred from its start timestamp and `results.txt` mtime because the original foreground runner was interrupted after its child completed; the other three wall clocks are recorded directly in the manifest.

## Mechanism Pretest

- Job: `stage_pretest_libero_object_swap_p1_stage_on_pretest` on task IDs `[0, 6]`.
- Valid: `True`; successful queries: `16`; stage events: `21`.
- Result: `0/2`; failure reason: `-`.
- Output: `outputs/ood_eval/stage_recognition_ablation/mechanism_pretest/stage_pretest_libero_object_swap_p1_stage_on_pretest`.
- Task 0 and Task 6 first disabled guidance at steps `56` and `48`, before a verified stable grasp in the reviewed videos. The pretest therefore proved that the real API and trace path were active, but already exposed premature-transition risk.
- Query reliability was `16/21` (`76.19%`), with mean query latency `26.94 s`. The pretest's `0/2` is not included in the 40-episode formal SR.
- Pretest contact sheets: `outputs/ood_eval/stage_recognition_ablation/qualitative_review/pretest_contact_sheets` (`2` PNGs).
- An earlier invalid pretest with corrupted RGB/empty segmentation is preserved under `outputs/ood_eval/stage_recognition_ablation/stale`; CUDA/EGL probing established physical GPU2 -> EGL device 1 before all accepted runs.

## Main Results

| Method | Profile | Stage | Valid | Success | SR | Videos | Metrics | Qual PNG | Stage Events | Query OK/All | Transitions | Guidance OFF | Query Latency | Select Latency | Failure Reason | Output |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `p1_stage_off` | `p1` | `OFF` | `True` | 1/10 | 10.00 | 10 | 891 | 1300 | 207 | 0/0 | 0 | 0 | - | 2.155 | - | `outputs/ood_eval/stage_recognition_ablation/stage_ablation_libero_object_swap_p1_stage_off` |
| `p1_stage_on` | `p1` | `ON` | `True` | 1/10 | 10.00 | 10 | 176 | 1300 | 154 | 126/154 | 139 | 31 | 7.159 | 2.154 | - | `outputs/ood_eval/stage_recognition_ablation/stage_ablation_libero_object_swap_p1_stage_on` |
| `p2_stage_off` | `p2` | `OFF` | `True` | 0/10 | 0.00 | 10 | 836 | 1300 | 255 | 0/0 | 0 | 0 | - | 2.587 | - | `outputs/ood_eval/stage_recognition_ablation/stage_ablation_libero_object_swap_p2_stage_off` |
| `p2_stage_on` | `p2` | `ON` | `True` | 3/10 | 30.00 | 10 | 128 | 1300 | 127 | 107/127 | 117 | 32 | 5.064 | 4.375 | - | `outputs/ood_eval/stage_recognition_ablation/stage_ablation_libero_object_swap_p2_stage_on` |

## EDS Metrics

All values are means over saved EDS chunk records; `-` means the metric was not available.

| Method | Initial EEF Final | Endpoint Final | Rollout EEF Final | Retention | Selected Reward | Target Distance | Initial Fallback | Rollout Fallback | Nonfinite | Mask Violation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `p1_stage_off` | 0.175 | 0.093 | 0.099 | 0.627 | -0.003 | 0.040 | 0 | 0 | 0 | 0.000 |
| `p1_stage_on` | 0.165 | 0.088 | 0.086 | 0.575 | -0.021 | 0.127 | 0 | 0 | 0 | 0.000 |
| `p2_stage_off` | 0.174 | 0.092 | 0.161 | 0.427 | -0.005 | 0.058 | 0 | 0 | 0 | 0.000 |
| `p2_stage_on` | 0.167 | 0.089 | 0.153 | 0.411 | -0.009 | 0.073 | 0 | 0 | 0 | 0.000 |

## Paired A/B Comparison

| Profile | 720-step OFF | 720-step ON | Success Delta | SR Delta (pp) |
| --- | ---: | ---: | ---: | ---: |
| `p1` | 1/10 | 1/10 | 0 | 0.00 |
| `p2` | 0/10 | 3/10 | 3 | 30.00 |

## Episode Seed Pairing

| Profile | OFF seeds | ON seeds | Exact Match |
| --- | --- | --- | ---: |
| `p1` | `{"0": 44, "1": 235, "2": 43, "3": 546, "4": 6, "5": 621, "6": 197, "7": 87, "8": 151, "9": 548}` | `{"0": 44, "1": 235, "2": 43, "3": 546, "4": 6, "5": 621, "6": 197, "7": 87, "8": 151, "9": 548}` | `True` |
| `p2` | `{"0": 44, "1": 235, "2": 43, "3": 546, "4": 6, "5": 621, "6": 197, "7": 87, "8": 151, "9": 548}` | `{"0": 44, "1": 235, "2": 43, "3": 546, "4": 6, "5": 621, "6": 197, "7": 87, "8": 151, "9": 548}` | `True` |

## Historical 240-Step Context

This comparison is descriptive only. It can reveal timeout-sensitive failures but cannot isolate a causal horizon effect across separately executed runs.

| Profile | Historical Stage OFF | 240-step Success | New 720-step OFF | 720-step Success |
| --- | --- | ---: | --- | ---: |
| `p1` | `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start02_iterall` | 1/10 | `p1_stage_off` | 1/10 |
| `p2` | `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start06_iterall` | 1/10 | `p2_stage_off` | 0/10 |

## Task-Level Outcomes

| Task | P1 OFF | P1 ON | P2 OFF | P2 ON |
| ---: | --- | --- | --- | --- |
| 0 | fail | fail | fail | fail |
| 1 | fail | success | fail | fail |
| 2 | fail | fail | fail | fail |
| 3 | success | fail | fail | success |
| 4 | fail | fail | fail | fail |
| 5 | fail | fail | fail | fail |
| 6 | fail | fail | fail | fail |
| 7 | fail | fail | fail | fail |
| 8 | fail | fail | fail | success |
| 9 | fail | fail | fail | success |

## Stage Event Summary

| Task | P1 ON events/query-ok/transitions/guidance-off | P2 ON events/query-ok/transitions/guidance-off |
| ---: | --- | --- |
| 0 | `7/5/5/2` | `3/3/3/1` |
| 1 | `4/2/2/1` | `8/7/7/2` |
| 2 | `27/21/25/5` | `21/17/21/6` |
| 3 | `23/22/22/2` | `2/2/2/1` |
| 4 | `14/11/14/5` | `21/18/21/6` |
| 5 | `12/10/11/2` | `26/21/20/4` |
| 6 | `5/5/5/1` | `17/16/17/4` |
| 7 | `6/4/5/2` | `8/8/8/2` |
| 8 | `30/25/24/5` | `11/9/10/3` |
| 9 | `26/21/26/6` | `10/6/8/3` |

## Stage/Guidance Timeline Artifacts

- Generated `20` per-episode timelines with stage, guidance, trigger, and query-status markers.
- Root: `outputs/ood_eval/stage_recognition_ablation/qualitative_review/stage_timelines`.
- `p1_stage_on`: `10` timelines in `outputs/ood_eval/stage_recognition_ablation/qualitative_review/stage_timelines/stage_ablation_libero_object_swap_p1_stage_on`.
- `p2_stage_on`: `10` timelines in `outputs/ood_eval/stage_recognition_ablation/qualitative_review/stage_timelines/stage_ablation_libero_object_swap_p2_stage_on`.

## Failure Classification

All 40 formal videos were reviewed using same-view 12-frame contact sheets. These labels describe the primary visible failure and do not replace the simulator success predicate.

| Task / object | P1 OFF | P1 ON | P2 OFF | P2 ON |
| --- | --- | --- | --- | --- |
| 0 alphabet soup | target displaced/dropped; no placement | premature OFF@56; target lost | basket/wrong-target interaction | premature OFF@24; no grasp |
| 1 cream cheese | no stable grasp | **success** | basket collision; no grasp | premature OFF@24; basket displaced |
| 2 salad dressing | bottle pushed; no transport | premature OFF@32; unstable grasp | bottle pushed away | premature OFF@24; bottle dropped |
| 3 BBQ sauce | **success** | premature OFF@48; basket collision | basket displaced; no grasp | **success**, OFF@32 then close@56 |
| 4 ketchup | target knocked down | wrong-object/oscillatory behavior | target pushed away; qpos error near step 672 | premature OFF@24; target pushed away |
| 5 tomato sauce | wrong-object interaction | wrong object dropped; OFF@32 | wrong-object/no grasp | OFF@24; clutter pushed away |
| 6 butter | wrong-object interaction | OFF@48; butter not acquired | clutter/bottle interaction | OFF@16; basket displaced |
| 7 milk | milk not acquired | OFF@56; basket collision | target not acquired | OFF@24; milk untouched |
| 8 chocolate pudding | target pushed; no placement | OFF@128; unstable grasp | target/clutter pushed | **success** despite repeated toggles |
| 9 orange juice | carton dragged away | OFF@32; no placement | carton pressed; qpos error near step 256 | **success**, carton placed after toggles |

Evidence:

- Videos: each job's `episode_1` through `episode_10` directories.
- Contact sheets: `outputs/ood_eval/stage_recognition_ablation/qualitative_review/contact_sheets` (`40` PNGs).
- Stage/guidance timelines: `outputs/ood_eval/stage_recognition_ablation/qualitative_review/stage_timelines` (`20` PNGs).
- Raw stage events: each Stage ON job's `eds_eval/stage_events.jsonl`.

## Execution Stability

P2 OFF reproduced two gripper-state range failures on both its original run and the audited rerun. The rerun retained partial videos, tracebacks, and exact values, so these episodes remain in the denominator as deployment failures:

| Task | Last recorded step | Observed qpos | Nominal range | Partial video |
| ---: | ---: | --- | --- | --- |
| 4 | 664 (failure on next chunk) | `[0.035462, -0.045862]` | `[-0.04245, 0.05185]` | `episode_5/episode_5_fail_error_agentview.mp4` (66.6 s) |
| 9 | 248 (failure on next chunk) | `[0.012757, -0.044621]` | `[-0.04245, 0.05185]` | `episode_10/episode_10_fail_error_agentview.mp4` (25.4 s) |

The violation is a finite lower-bound overshoot, not an RBF fallback, nonfinite tensor, or action-mask violation. It should be investigated as a separate observation-processing/contact-stability issue; this report does not clamp it away or exclude the failed episodes post hoc.

## 中文定量与机制分析

### Stage Recognition 可靠性

| Profile | Query OK | 失败构成 | 首次 Guide OFF | OFF / ON 切换 | 有状态变化的事件 | Query latency sum / mean / max | EDS records OFF -> ON |
| --- | ---: | --- | --- | ---: | ---: | --- | ---: |
| P1 | `126/154` (`81.8%`) | 27 parse + 1 timeout | range `32-128`, median `52` | `31 / 22` | `139/154` (`90.3%`) | `1102.6 / 7.159 / 39.718 s` | `891 -> 176` (`-80.2%`) |
| P2 | `107/127` (`84.3%`) | 20 parse | range `16-32`, median `24` | `32 / 22` | `117/127` (`92.1%`) | `643.2 / 5.064 / 19.860 s` | `836 -> 128` (`-84.7%`) |

关键观察：

1. P2 的 10 个 episode 全部在最多 32 steps 内关闭 guidance，远早于 720-step horizon，也早于多数视频中的稳定抓取时刻。P1 的 median first-OFF 也只有 52 steps。
2. 两组 ON 合计 `233/281` 次查询成功，47 次解析失败的响应通常截断在 `stage N\nguidance:` 或 `stage N\nguidance`，另有 1 次请求超时。失败回退到 Stage 1 / Guide ON 会进一步制造 ON/OFF 震荡。
3. 90% 以上的 query event 都改变了 stage 或 guidance，且 P1/P2 分别出现 22 次重新开启 guidance。这不是稳定的阶段状态机行为。
4. Stage ON 将实际运行 EDS 的 chunk 数降低 80%-85%。因此 P2 的 `3/10` 更像“少量前置 EDS/RBF 定位 + 大部分 unguided RDT rollout”的收益，而不能直接归因于 VLM 正确识别了抓取、运输与放置阶段。

### 成功任务的机制解释

- P1 ON 新增 Task 1，但丢失 P1 OFF 原本成功的 Task 3，净增益为 0。这证明开关本身会显著改变轨迹，但其方向不稳定。
- P2 ON 的 Task 3 在 reward-high@32 后关闭 guidance，close@56 后进入 Stage 2，随后完成 BBQ sauce 放置，是三次成功中时序最合理的一次。
- P2 ON 的 Task 8 在 step 24 就关闭 guidance，之后多次 OFF/ON 震荡仍然成功；Task 9 在 close@32 后关闭、parse failure 后重开，再次关闭后成功。两者说明 prior recovery 有用，但不是干净的单次阶段切换证据。
- P2 的 30% SR 相比配对 OFF 的 0% 是真实且配对的正信号，但 `n=10` 只支持工程性描述，不支持统计显著性或跨 seed 泛化结论。

### EDS/RBF 指标解释

- 四组均为 0 initial/rollout RBF fallback、0 nonfinite、0 action-mask violation，说明成功率差异不是由 RBF 机制异常或 mask 破坏造成。
- Stage ON 的 initial/rollout diversity、selected reward 和 target distance 均只在 guidance 仍开启的 chunk 上记录；由于 ON 组主动删去了大量后续 EDS chunks，和 OFF 组不是同一时序样本集合。因此表中的均值只能用于机制诊断，不能作为 Stage ON/OFF 的无偏质量比较。
- P1/P2 ON 的 final target distance 均高于 OFF，但 SR 分别持平和提高。这进一步说明最终行为差异主要来自“何时退出 steering”，而不是 ON 组在仍受引导时选出了更高 reward 的轨迹。

### 运行成本与基础设施

- P1 ON 的 API 查询累计约 18.4 分钟，P2 ON 约 10.7 分钟；尽管如此，过早关闭 EDS 使两组 ON 的总 job wall-clock 没有按查询开销同比增长。该速度收益来自减少 steering，而不是更高效的 stage recognizer。
- 正式运行全部使用 physical GPU 2，运行时映射为 `CUDA_VISIBLE_DEVICES=2`、`MUJOCO_EGL_DEVICE_ID=1`。最初无效预检暴露了该主机 CUDA/EGL 非同序映射；修正后 RGB、segmentation 和正式结果均正常，错误预检已归档到 `outputs/ood_eval/stage_recognition_ablation/stale`。
- 外部 API 在正式实验后曾出现一次 health-check 失败。runner 已修复为：resume 只补跑 Stage OFF 时不再无条件依赖 Poe health check；Stage ON 待跑时仍强制真实 credential 和健康检查。

## 决策与下一步

当前结论为 **promising but target missed**：P2 从 `0/10` 提升到 `3/10`，但距离 `>=5/10` 仍差两个任务，且现有阶段切换存在系统性 premature OFF。建议按以下顺序推进：

1. **Verified-grasp gate**：只有目标物体相对 gripper 保持稳定、出现可观测 lift/displacement，并持续至少 2 个 chunk 时，才允许 Stage 1 -> Stage 2；不得仅凭 gripper close command 推断抓取成功。
2. **单调状态机与防抖**：正常路径限制为 Stage 1 -> Stage 2 -> Done；设置 minimum dwell/cooldown。解析失败保持上一状态，不回退到 Stage 1 / Guide ON；只有验证掉落时才允许重新开启抓取 guidance。
3. **Task-specific stage context**：不再让所有 task 复用 alphabet-soup 文本；Stage 2 明确描述当前目标物体和 basket，并提供 transport/place reward，而不是进入 Stage 2 后直接使用零 reward 或完全依赖 prior。
4. **结构化 VLM 输出**：采用 JSON/schema 或 constrained decoding，提升 completion budget 并增加解析重试，消除当前约 17% 的截断/格式失败。
5. **机制消融**：在同一 10-task/720-step protocol 下同时比较 fixed early cutoff、deterministic verified-grasp gate、VLM-only gate 和 hybrid gate，判断 P2 的 `3/10` 究竟来自语义识别还是简单减少 over-steering。

## Validity Gate

- Valid jobs: `4/4`.
- Jobs with parsed results: `4/4`.
- Jobs with 10 videos: `4/4`.
- Stage-ON jobs with successful query trace: `2/2`.
- Exact OFF/ON episode-seed pairing: `True`.
- Hydra validity checks cover strict perturbation, suite, 720-step budget, Stage ON/OFF, grounding OFF, cached guidance, EDS/RBF parameters, and seed 0.
- Serialized config/log checks reject Poe API key material.
- P2 OFF's two execution-error episodes each have exactly one readable partial failure video and remain counted as failures; no episode was dropped from the denominator.
- The original invalid P2 OFF output and runner log are preserved under `outputs/ood_eval/stage_recognition_ablation/stale/stage_ablation_libero_object_swap_p2_stage_off_20260801T015142160269Z`.

## Verification Evidence

- Runner validity: mechanism pretest `1/1` valid; formal jobs `4/4` valid; strict perturbation and suite checks all passed.
- Video audit: `42/42` non-stale MP4 files (2 pretest + 40 formal) are readable by `ffprobe`; every formal job has exactly 10 episode videos.
- Qualitative audit: `40` same-view contact sheets and `20` Stage ON stage/guidance timelines exist and were visually reviewed.
- Seed audit: P1 and P2 OFF/ON `episode_metadata.jsonl` files are byte-for-byte identical within each profile.
- Safety audit: all four jobs report 0 initial fallback, 0 rollout fallback, 0 nonfinite, and max action-mask violation `0.0`.
- Code verification: targeted regression `244 passed in 36.03s`; `py_compile` and `git diff --check` passed.
- Credential audit: no serialized credential value or `OPENAI_API_KEY=` assignment was found in current outputs, stale archives, report, configs, or logs.
- Process audit: no stage-recognition runner, `main.py`, or matching conda evaluation process remained after completion.
- Final storage: experiment root `2.5G`; filesystem retained approximately `59G` free.

## Conclusion

- Best valid setting: `p2_stage_on`, `3/10` (`30%`), a paired `+3/10` over P2 OFF. P1 remains neutral at `1/10 -> 1/10` with different successful tasks.
- The initial `>=5/10` engineering target was **not reached**. The current result is promising but not deployment-ready and does not justify expanding to other suites yet.
- The three P2 ON successes demonstrate that early removal of strong continuous EDS guidance can help Tasks 3, 8, and 9. However, 10/10 P2 episodes switched OFF by step 32, often before stable grasp, and the controller then spent most chunks on unguided RDT. The experiment therefore does not isolate a reliable semantic-stage-recognition benefit from a stochastic early steering cutoff.
- Current VLM state control is too unstable: combined query success is `82.92%`, transitions occur on `91.10%` of queries, and OFF/ON oscillations are common. Reusing an alphabet-soup-oriented cache across all objects and a Stage 2 function that returns zero further confounds the intended grasp/transport semantics.

### Recommended Next Iteration on the Same 10 Tasks

1. Gate Stage 1 -> Stage 2 on verified grasp evidence: target-object lift, persistent object/gripper relative pose, or contact/segmentation evidence over multiple frames. A gripper-close command alone is insufficient.
2. Use a monotonic state machine with debounce/cooldown. Preserve the previous state on API/parse failure; do not reset to Stage 1 / Guide ON and oscillate.
3. Replace free-form parsing with constrained structured output and address responses truncated before the `yes/no` token. Log and separately gate any fallback.
4. Generate task-specific stage descriptions and explicitly decide whether transport/place needs basket-conditioned guidance instead of always using the cached zero Stage 2 reward.
5. Add a deterministic fixed-cutoff baseline at steps 24/32 and a verified-grasp heuristic baseline. This will distinguish semantic VLM value from the observed short-prefix EDS schedule.
6. Diagnose the small finite gripper-qpos lower-bound overshoots before another P2 sweep; compare tolerance-aware observation handling against the current hard failure without silently clipping simulator instability.

Only after a grasp-verified controller reaches `>=5/10` on this paired task set should the evaluation expand to additional seeds or `libero_object_task/env/temp`.
