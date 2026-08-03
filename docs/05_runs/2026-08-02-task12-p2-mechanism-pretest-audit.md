# Task 12 P2 Mechanism Pretest Evidence/Spec 审计清单

日期：2026-08-02
审计范围：只读核对批准的 design、implementation plan Task 12、`scripts/rdt_eds_eval_runner.py` 及现有 metrics/trace/visualization 接口。本文不代表正式实验结论。

## 1. 规范来源

- Design：`docs/01_specs/2026-08-01-p2-adaptive-eds-rbf-ood-optimization-design.md`
- Plan Task 12：`docs/04_plans/2026-08-02-p2-adaptive-eds-rbf-ood-optimization.md:1059`
- Profile registry：`scripts/rdt_eds_eval_runner.py:422`
- Job builder/command：`scripts/rdt_eds_eval_runner.py:1658`、`scripts/rdt_eds_eval_runner.py:1764`
- Strict validity：`scripts/rdt_eds_eval_runner.py:3230`

Task 12 应固定为：`libero_object_swap`、Tasks `[0, 8]`、每 profile 2 episodes（每个 task 1 次）、共 6 jobs/12 episodes。pretest 只验证机制，不按 Task 0/8 的 success/failure 删除 profile。

## 2. 六个 Profile 与精确 Override

### 2.1 所有 profile 的共同 P2 基线

```yaml
population_size: 16
cem_iters: 10
use_cem: false
num_elites: 16
temperature: 0.1
renoise_t_max: 3
renoise_t_min: 1
reward_mode: normal
initial_sampling_mode: rbf_diverse_denoise
initial_diversity_scale: 20.0
initial_diversity_start_ratio: 0.8
truncated_rollout_mode: rbf_diverse
rollout_diversity_scale: 20.0
rollout_diversity_start_ratio: 0.6
rollout_diversity_iters: all
rollout_diversity_skip_final_steps: 0
parent_weighting_mode: legacy_temperature
selection_ess_target_ratio: 0.6
selection_beta_max: 100.0
selection_bisection_steps: 24
parent_coverage_mode: none
parent_anchor_count: 0
parent_anchor_reward_quantile: 0.5
elite_carryover_count: 0
rollout_diversity_control_mode: fixed
rollout_diversity_target_ratio: 1.0
rollout_diversity_band_ratio: 0.2
rollout_diversity_scale_min: 0.0
rollout_diversity_scale_max: 20.0
rollout_diversity_decay_floor: 0.25
chunk_population_mode: fresh
chunk_memory_fraction: 0.0
chunk_memory_renoise_steps: 2
chunk_memory_reward_guard_quantile: 0.25
search_schedule_mode: legacy_linear
adaptive_min_cem_iters: 4
adaptive_early_stop_patience: 2
adaptive_reward_improvement_eps: 0.001
execution_horizon_mode: fixed
execution_horizon_far: 8
execution_horizon_near: 4
execution_horizon_contact: 2
execution_near_distance: 0.08
execution_contact_distance: 0.04
max_episode_steps: 720
stage_recognition_enabled: true
gemini_grounding_enabled: false
seed: 0
task_ids_filter: [0, 8]
episodes: 2
```

共同 Hydra gate 还必须包含：`policy.type=rdt`、`backend=libero`、`backend.libero.suite_name=libero_object_swap`、`backend.libero.strict_perturbations=true`、`main.use_guidance=true`、`main.guidance_type=eds`、`main.eds_eval.save_qualitative=true`、`main.eds_mechanism_pretest.output_mode=qualitative_chunk`、`max_chunks=2`、`save_tensors=true`、`plot_3d=true`。

### 2.2 单 profile 差异

| Label | 相对共同基线的唯一算法 override | 预期作用 |
|---|---|---|
| `p2_legacy_stage_on_rerun` | 无 | P2 Stage-on legacy 对照 |
| `p2_sel_ess05` | `parent_weighting_mode=adaptive_ess`; `selection_ess_target_ratio=0.5` | Adaptive ESS parent weighting |
| `p2_adaptrbf_t10_s20` | `rollout_diversity_control_mode=adaptive_band` | target `1.0`、max scale `20` 的 adaptive rollout RBF |
| `p2_divres_k4_e2` | `parent_coverage_mode=eef_kcenter`; `parent_anchor_count=4`; `elite_carryover_count=2` | 每轮 4 anchors、2 elites、10 weighted offspring |
| `p2_memory25` | `chunk_population_mode=warm_start_mix`; `chunk_memory_fraction=0.25` | 16 粒子中最多 4 个 memory candidates |
| `p2_schedule_contact` | `search_schedule_mode=adaptive`; `execution_horizon_mode=adaptive_prefix` | 自适应 renoise/early-stop 与 2/4/8 execution prefix |

## 3. 每 Job 必需 Artifact

以下条件全部满足才可把 pretest job 记为 valid：

- 根目录：`results.txt` 可解析且 total 为 `2`；`config_fingerprint.txt` 与当前 job 一致；`job_manifest.json` 可解析且 payload/fingerprint 一致。
- Hydra：`.hydra/config.yaml` 与 `.hydra/overrides.yaml` 均存在、可解析，且与 runner 规范化 command 的 key/value 集完全一致，不能缺失、重复或额外插入 override。
- 视频：`episode_1/*.mp4`、`episode_2/*.mp4` 各且仅各 1 个；总数为 2；两者均通过 `ffprobe`。
- Metrics：`eds_eval/eds_metrics.jsonl` 非空，episode 覆盖精确等于 `{0,1}`，每条记录含有限且为 0 的 `nonfinite_count`、有限且绝对值不超过 `1e-8` 的 `action_mask_violation_max`，所有 fallback/grad-failure count 为 0。
- Episode identity：`eds_eval/episode_metadata.jsonl` 覆盖 `{0,1}`，task multiset 精确为 `[0,8]`，并保存合法 `episode_seed`。
- Stage Recognition：`eds_eval/stage_events.jsonl` 每个 episode 至少 1 条 `query_status=ok`、`query_ok=true` 的记录；episode/task/seed 与 metadata 对齐，字段类型、step/chunk 范围和 latency 均合法。
- Qualitative：`eds_eval/qualitative/episode_000/` 和 `episode_001/` 均非空，并至少包含一个 mechanism/trace/metadata/tensors/selection/memory/schedule/single_step 标记的文件。
- Runner log：`runner_logs/pretest/<label>.log` 存在，用于核对真实命令、strict LIBERO-PRO 加载、warning、fallback 和进程退出状态。
- Identity：本 job 的 `level/suite/episodes/task_ids_filter/profile`、git revision、code-state hash、cache 路径和 command 必须与 fingerprint 绑定。

启用对应组件时，Task 9 规定的 profile-specific qualitative 文件还应逐个检查：

- ESS/k-center：`selection/parent_source_trajectories_3d.png`、`selection/parent_rank_and_probability.csv`、`selection/elite_anchor_survival.json`。
- Memory（有可用 memory 的 chunk）：`memory/fresh_vs_memory_trajectories_3d.png`、`memory/memory_acceptance.json`。
- Adaptive RBF/schedule：`schedule/adaptive_decisions.json`、`schedule/reward_diversity_schedule.png`。
- 通用 trace：`first_chunk_metadata.json`、`single_step_inner_loop/single_step_particles.csv`、`tensors/mechanism_trace.pt`，以及已有 single-step/full-process 图表。

“可读”不能只解释为 size > 0：PNG 应实际 decode，JSON/JSONL 应 parse，CSV 应有 header/data，`mechanism_trace.pt` 应通过现有 weights-only loader，视频应通过 `ffprobe`。

## 4. 五项 Mechanism Gate 的计算口径

### 4.1 Adaptive ESS

- Profile：`p2_sel_ess05`；target = `0.5`。
- 首选字段：每条 chunk record 的 `per_iter[*].selection_ess_ratio`；辅助字段为 `selection_ess_ratio_mean`、`selection_beta_mean`、`selection_degenerate_reward_count`。
- 计算：对所有有限 per-iteration 值计算 `abs(selection_ess_ratio - 0.5)`，再取 median。
- PASS：样本非空且 median `<= 0.1`；同时 selection mode 为 `adaptive_ess`、无 fallback/nonfinite。
- Equal-reward/不可达 target 的记录必须单列说明，不能静默丢弃；若选择排除，应同时报告包含与排除后的结果。

### 4.2 Adaptive Rollout RBF

- Profile：`p2_adaptrbf_t10_s20`。
- 首选字段：`per_iter[*].adaptive_rbf_scale_applied`；交叉字段为 `adaptive_rbf_scale_requested`、`adaptive_rbf_band_hit`、`adaptive_rbf_trigger_reason`、chunk-level `adaptive_rbf_*_mean`。
- 计算：收集所有 active iteration 的有限 applied scale；按数值容差（建议 round 到 6 位）去重。
- PASS：至少 2 个不同 scale，且不是全部为 `20.0`；`adaptive_rbf_active_iter_count > 0`，fallback/grad failure 为 0。

### 4.3 Reward-Constrained k-center + Elite Carryover

- Profile：`p2_divres_k4_e2`。
- 首选证据：trace `selection_info.per_iter[*].parent_count_by_source`、`parent_sources`、`parent_selection_kinds`；辅助字段为 `anchor_count_observed`、`elite_carryover_count_observed`。
- 每个 executed iteration 预期：`elite=2`、`anchor_offspring=4`、`weighted_offspring=10`，总计 16；elite/anchor parent index 唯一性与 source label 一致。
- PASS：每轮 source count 均与配置一致，不能只用 chunk-level max count；anchor shortfall 或 source 缺失均判 fail，并保留 warning/原因。

### 4.4 Cross-chunk Population Memory

- Profile：`p2_memory25`。
- 按 `(episode, global_step)` 排序 metrics；首 chunk 应为 fresh。第一个 memory-eligible 后续 chunk 应出现 `chunk_memory_available=true`、`chunk_memory_candidate_count=4`，并且 `chunk_memory_used=true`、`chunk_memory_source_counts.memory > 0`。
- 用 `chunk_memory_acceptance_ratio`、`chunk_memory_fraction_observed`、`selected_chunk_population_source` 和 memory qualitative trace 交叉验证，不能仅凭 available 宣称 used。
- 从 `stage_events.jsonl` 找到真实 stage change，并在随后 chunk 要求 `chunk_memory_reset_reason=stage_change`、旧 memory 未继续使用。
- PASS：第二个 eligible chunk 实际使用 memory，且观测到的 stage change 有明确 reset 证据。若两个 task 均未发生 stage change，该 reset 子项只能记为 `not observed/inconclusive`，不可默认通过。

### 4.5 Adaptive Search / Execution Schedule

- Profile：`p2_schedule_contact`。
- Renoise：收集 `per_iter[*].n_trunc_steps`；execution：收集 chunk-level `execution_horizon_resolved`；同时报告 `eds_iters_executed`、`early_stop_used/reason`。
- PASS：`unique(n_trunc_steps)` 至少 2 个，或 `unique(execution_horizon_resolved)` 至少 2 个。两者都只有单值则 fail。
- `eds_iters_executed` 的变化是有价值的支持证据，但不能替代 plan 明确要求的 renoise/horizon 多值 gate。

## 5. Strict LIBERO-PRO、凭据与回退安全 Gate

- 运行前：runner preflight 必须验证 LIBERO-PRO registry、perturbation 文件、生成的 BDDL/init、路径指向本 worktree 的 `third_party/libero_pro`，且 OOD BDDL 不等同普通 `libero_object`。
- Hydra 双验证：`backend.libero.strict_perturbations=true` 且 suite 精确为 `libero_object_swap`；config 与 overrides 两处都必须与 command 一致。
- 禁止 normal-LIBERO fallback：日志/config/results 中不得出现 normal fallback 迹象；strict 失败必须让 job failed/invalid，不能继续计入结果。
- Stage Recognition 必须在线：禁止 `--offline-vlm`，`OPENAI_API_KEY` 不能是空或 dummy，Poe Gemini health check 成功；每 episode 至少一个成功且 identity 对齐的 query trace。
- Gemini grounding 必须为 OFF：`perception.gemini_grounding.enabled=false`。
- 凭据只通过环境提供；command、Hydra、manifest、JSON/JSONL、log、TXT、MD、CSV 中不得出现 key 名值或 token。正式报告也不得复制 secret。
- 任何 `fallback_used=true`、非空 `fallback_reason`、正数 `grad_failure_count/fallback_count` 都使 job invalid；日志 warning 还需人工审计，以排除没有被 metrics 序列化的 silent fallback。

## 6. 提前发现的风险

1. **高优先级：strict telemetry 校验键名与真实 metrics 不一致。** `_p2_component_telemetry_failures()` 当前查找 `selection_effective_sample_size_ratio/selection_ess_ratio`、`adaptive_rbf_requested_scale/rollout_diversity_scale_requested`、`parent_anchor_count_observed`；真实 `EDSChunkMetrics` 顶层字段分别是 `selection_ess_ratio_mean`、`adaptive_rbf_scale_requested_mean`（per-iter 为 `adaptive_rbf_scale_requested`）、`anchor_count_observed`。全仓库搜索显示前三组 alias 只在 runner 测试 fixture 中生成，实际算法不生成。因此 ESS、adaptive-RBF、k-center pretest 即使机制正常，也可能被 strict validity 误判 invalid。运行前应修正 runner validator/test fixture 并走既定 review；本审计未改代码。
2. **高优先级：runner 未提供 P2 pretest 专用 report writer。** `run_level()` 不为 P2 level 自动生成 `docs/03_evidence/...pretest-report.md`，CLI `write-report` 的 choices 也不含 P2。Task 12 正式报告需要独立聚合脚本或受审查的人工生成流程，不能假设 runner 已产出报告。
3. **中优先级：qualitative strict validity 过于宽松。** 当前只要求每 episode 存在任一带 marker 的非空文件，不要求 profile-specific 文件齐全，也不 decode PNG/parse trace。Task 12 报告必须执行本清单中的逐文件可读性检查。
4. **中优先级：`max_chunks=2` 限制图形化覆盖。** 它足以尝试捕获 memory 的第二 chunk，但 stage change 可能更晚；memory reset gate 必须读取全量 metrics/stage events。若没有可观测 stage change，应诚实记为 inconclusive，而不是用缺证据的 PASS。
5. **低优先级：通用 preflight 会检查全部 OOD suites。** 即使 Task 12 只跑 swap，其他 LIBERO-PRO suite 的缺失也可能阻止 preflight；若发生，应区分“全局环境 gate”与 swap 本身配置错误，但不得绕过已批准 preflight。

## 7. Reviewer Sign-off 条件

- [x] 6 个 label、2 episodes、Tasks `[0,8]` 与 registry/manifest 完全一致。
- [x] 上述 telemetry validator 键名风险已修复并有真实字段 fixture 测试，或所有受影响 job 明确标为 blocked/invalid。
- [x] 每 job 通过 `_p2_job_validity()`，且人工 profile-specific artifact audit 通过。
- [x] 五项 mechanism gate 按本文件口径给出原始样本数、聚合值和 PASS/FAIL/INCONCLUSIVE。
- [x] strict LIBERO-PRO、online stage query、0 fallback、0 nonfinite、0 mask violation、0 credential serialization 全部通过。
- [x] 正式报告只写入 `docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-02-p2-adaptive-eds-rbf-pretest-report.md`，并明确 pretest SR 不用于 profile 淘汰。

## 8. 正式运行审计记录

### 8.1 第三次尝试（已归档，未作为最终证据）

- 归档路径：`outputs/ood_eval/p2_adaptive_eds_rbf/attempts/pretest_attempt3_runtime_and_validator_20260802T151927Z/`。
- 终态：4 个 `done`、1 个 `failed`、1 个 `invalid`；所有原始输出与 runner log 均完整保留。
- `p2_adaptrbf_t10_s20`：原生进程以 `exit=134` abort，仅覆盖 episode 0 的 3 个 metrics，不能计入证据。
- `p2_memory25`：算法进程正常退出且有 2 个视频，但旧 validator 将 `max_chunks=2` 之外的所有 memory-active metrics 都错误要求有 qualitative trace，因此判为 invalid。
- 修复采用 TDD：新增“首个 eligible chunk 有证据时允许后续未采样 metrics”的失败测试；validator 现在仍强制首个 eligible memory chunk 的 trace/PNG/JSON 完整可读，同时不要求未被 qualitative sampler 保存的后续 chunk 生成不存在的图。
- 修复后 runner 测试：`206 passed`；`py_compile` 和 `git diff --check` 通过。
- 因 runner 源码属于执行 code-state fingerprint 的组成部分，本次修复后不直接改判旧产物，必须重新生成统一指纹的 6-profile pretest。

### 8.2 第四次正式尝试与 clean retry（最终证据）

- 第四次运行统一使用修复后的 code-state fingerprint，终态先得到 5 个 `done/valid` 与 legacy profile 的一次 `exit=134` native abort。
- 失败的 legacy 半成品与日志完整归档到 `outputs/ood_eval/p2_adaptive_eds_rbf/attempts/pretest_attempt4_legacy_native_abort_20260802T154540Z/`，未在原目录追加或改写。
- 随后在 GPU 3 使用同一指纹执行 `--resume`；另外 5 组均为 `resume-skip`，仅 legacy 从干净目录重跑并通过。
- 最终 manifest：`6 done / 6 valid`；每组 2 个视频，strict perturbation 与 suite 均为 true，实验结束后无 runner/main.py 残留进程。
- 五项 gate：Adaptive ESS、Adaptive rollout RBF、k-center + elite、cross-chunk memory、adaptive schedule 全部 PASS。Memory 有 28 次 stage change；按 `(episode_id, global_step)` 精确匹配，4 次 transition 使 guided EDS 开启且全部在同 step 验证 reset（4/4），其余 24 次 guidance 为 off、不会读取 population memory，按 not applicable 记录。旧报告器的 `23/28` 是四条 metric 被宽松后继匹配重复使用的聚合缺陷，不作为结论依据。
- 正式报告：`docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-02-p2-adaptive-eds-rbf-pretest-report.md`。
- 正式证据通过独立只读复核：6/6 valid、140/140 qualitative artifacts 可读、五项 gate 与安全 gate 均获 APPROVED。
- 运行后进一步以 TDD 修复 report writer 的 stage-reset 多对一宽松匹配：改为 exact-step matching、单 metric 单次消费、guidance-off N/A，并新增两个失败回归测试；runner 全量测试更新为 `208 passed`。该修复只影响后续报告/runner，未改 policy 算法，Stage A 将绑定修复后的新 code-state fingerprint。
