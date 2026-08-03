# RBF s20 Qualitative Diversity Supplement Report

日期：2026-07-10

## 1. 目的

本次补充实验针对 `rbf_s20_start06` 与 `rbf_s20_start08` 两个配置，补齐 final eval 过程中每个 EDS `select_action` chunk 的 RBF diversity 定性证据。目标不是修改 RBF+EDS 算法语义，而是在已有 eval/trace/visualization 路径上补充可复查的 qualitative artifacts，用于判断 RBF-diverse initial sampler 是否真实提升了 initial proposal diversity。

## 2. 实验与输出范围

目标 qualitative 目录：

- `outputs/rdt_eds_eval/level2_libero_object_rbf_s20_start06/eds_eval/qualitative`
- `outputs/rdt_eds_eval/level2_libero_object_rbf_s20_start08/eds_eval/qualitative`

补充生成的每个 chunk 目录包含：

- `RBF_diversity/eef_3d_before_after_final.png`
- `RBF_diversity/endpoint_scatter_before_after_final.png`
- `RBF_diversity/pairwise_distance_hist_before_after_final.png`
- `RBF_diversity/rbf_diversity_metrics.json`
- `RBF_diversity/rbf_diversity_trace.npz`
- `single_step_inner_loop/...`
- `full_eds_process/...`

运行时使用 cached VLM guidance，关闭在线 VLM/grounding；`OPENAI_API_KEY=dummy` 仅用于满足配置/启动路径，不参与本次 reward 生成。补充运行设置为 `main.eds_eval.save_qualitative=false` 与 `main.eds_eval.write_metrics=false`，避免覆盖已有 final eval 的标准 qualitative PNG 和 metrics；新增内容写入已有 per-chunk qualitative 子目录。

## 3. 完整性检查

| 配置 | Episode / chunk 覆盖 | RBF metrics JSON | RBF NPZ trace | RBF 3D/endpoint/hist PNG | single_step artifacts | full_process artifacts | RBF fallback |
|---|---:|---:|---:|---:|---:|---:|---:|
| `rbf_s20_start06` | `episode_000:30`, `episode_001:30`, `episode_002:30` | 90 | 90 | 90 / 90 / 90 | 90 | 90 | 0 |
| `rbf_s20_start08` | `episode_000:30`, `episode_001:17`, `episode_002:30` | 77 | 77 | 77 / 77 / 77 | 77 | 77 | 0 |

`start08` 的 `episode_001` 只有 17 个 chunk，因为该 episode 在 final eval 中提前成功终止；补充 qualitative 的 chunk 数与实际 select_action 调用数一致。

任务成功率与原 eval run 一致：

| 配置 | Success count | Success rate |
|---|---:|---:|
| `rbf_s20_start06` | 0 / 3 | 0.00% |
| `rbf_s20_start08` | 1 / 3 | 33.33% |

## 4. RBF Diversity 定量摘要

所有数值均来自每个 chunk 的 `RBF_diversity/rbf_diversity_metrics.json`，取 chunk mean。

| 配置 | RBF scale | start ratio | diversity steps | initial EEF before | after RBF phase | final | retention ratio | endpoint before | endpoint after | endpoint final |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rbf_s20_start06` | 20.0 | 0.6 | 3 | 0.1214 | 0.3429 | 0.0765 | 0.2216 | 0.0607 | 0.1836 | 0.0436 |
| `rbf_s20_start08` | 20.0 | 0.8 | 4 | 0.1222 | 0.3958 | 0.1321 | 0.3326 | 0.0609 | 0.2135 | 0.0756 |

关键观察：

1. 两组都没有触发 diversity fallback，说明本次补充证据来自 RBF-diverse denoising path，而不是 iid baseline fallback。
2. `after RBF phase` 明显高于 `before RBF`：`start06` 的 EEF diversity 从 0.1214 增至 0.3429，`start08` 从 0.1222 增至 0.3958。
3. endpoint spread 同样在 RBF phase 后明显放大：`start06` 从 0.0607 增至 0.1836，`start08` 从 0.0609 增至 0.2135。
4. 完整 denoising 到 final proposal 后，多样性会被 RDT policy prior 拉回。`start06` final diversity 低于 before-RBF，说明 early RBF 扩散没有被最终动作样本充分保留；`start08` final diversity 略高于 before-RBF，说明更晚的 RBF 注入位置对最终保留更有利。

## 5. 定性证据索引

每个 chunk 的 `RBF_diversity` 图均使用同坐标轴、同视角对比 `before-RBF / after-RBF / final` 三个阶段，可直接观察 RBF phase 是否在 3D EEF trajectory space 中打开粒子分布。

代表性文件：

- `outputs/rdt_eds_eval/level2_libero_object_rbf_s20_start06/eds_eval/qualitative/episode_000/chunk_000000/RBF_diversity/eef_3d_before_after_final.png`
- `outputs/rdt_eds_eval/level2_libero_object_rbf_s20_start06/eds_eval/qualitative/episode_000/chunk_000000/RBF_diversity/endpoint_scatter_before_after_final.png`
- `outputs/rdt_eds_eval/level2_libero_object_rbf_s20_start06/eds_eval/qualitative/episode_000/chunk_000000/RBF_diversity/pairwise_distance_hist_before_after_final.png`
- `outputs/rdt_eds_eval/level2_libero_object_rbf_s20_start08/eds_eval/qualitative/episode_000/chunk_000000/RBF_diversity/eef_3d_before_after_final.png`
- `outputs/rdt_eds_eval/level2_libero_object_rbf_s20_start08/eds_eval/qualitative/episode_000/chunk_000000/RBF_diversity/endpoint_scatter_before_after_final.png`
- `outputs/rdt_eds_eval/level2_libero_object_rbf_s20_start08/eds_eval/qualitative/episode_002/chunk_000216/RBF_diversity/pairwise_distance_hist_before_after_final.png`

这些图和 JSON/NPZ trace 能清晰证明：RBF step 本身确实在 EEF trajectory space 中扩大了 initial proposal diversity。更需要继续分析的是，扩大的 diversity 在最终 denoised action proposals 中保留多少，以及它是否转化为 EPS-CoT reward selection 与环境成功率收益。

## 6. single_step 与 full_process 补充

为对齐 mechanism pretest 的观察方式，每个 chunk 同时补充：

- `single_step_inner_loop/initial_before_diversity_3d.png`
- `single_step_inner_loop/initial_after_diversity_phase_3d.png`
- `single_step_inner_loop/initial_final_3d.png`
- `single_step_inner_loop/initial_reward_hist.png`
- `single_step_inner_loop/initial_selected_rank.png`
- `full_eds_process/full_process_summary.md`
- `full_eds_process/iteration_*_population_3d.png`
- `full_eds_process/iteration_*_reward_hist.png`

这部分用于继续追踪：RBF-expanded initial population 在 EDS 后续 resample / renoise / rollout 中是否被保留，selected parent 是否来自更分散的候选，以及 final reward/target-distance 是否受益。

## 7. 结论

本次补充 qualitative evidence 已经可以回答“RBF 是否提升 initial proposal diversity”：可以，且证据清晰。两组配置在 `after RBF phase` 的 EEF trajectory diversity 与 endpoint spread 都显著高于 `before RBF`，且没有 fallback。

但它同时揭示了当前 RBF+EDS 的核心瓶颈：多样性提升主要发生在 RBF phase，最终 denoise 后会被 policy prior 明显收缩。`start08` 比 `start06` 有更好的 final diversity retention，并且 final eval 成功率为 1/3；`start06` 的 final diversity 被收缩到低于 before-RBF，对任务成功没有收益。这说明后续优化应优先围绕 RBF 注入时机、final diversity retention、以及 EDS selection 是否真正利用 EEF-space diversity 展开。

## 8. 注意事项

1. 本次改动只添加 eval/tracing/visualization 支撑，不修改 RBF+EDS 算法核心语义。
2. 第一次尝试在非默认 GPU/EGL 组合上运行 `start08` 时遇到 EGL/CUDA 初始化失败，随后使用可用 GPU/EGL 组合重新运行并生成了完整 artifacts；最终报告基于已验证的成功输出。
3. 本次补充运行不重新写 standard eval metrics 文件，只补充 qualitative per-chunk evidence。

## 9. 验证记录

已执行的代码级验证：

- `pytest tests/test_eds_mechanism_pretest_vis.py::test_save_eds_rbf_diversity_artifacts_writes_trace_metrics_and_plots tests/test_main_rdt_startup.py::test_eds_mechanism_pretest_output_root_can_target_qualitative_chunk -q`
- `pytest tests/test_eds_mechanism_pretest_vis.py tests/test_main_rdt_startup.py -q`
- `pytest tests/test_eds_mechanism_trace.py tests/test_eds_mechanism_pretest_runner.py -q`
- `python -m py_compile main.py utils/eds_mechanism_pretest_vis.py core/eds_mechanism_trace.py core/rdt_policy_steer.py scripts/rdt_eds_eval_runner.py`

已执行的 artifact 级验证：

- 两个目标 qualitative 目录的 JSON / NPZ / PNG / `single_step_inner_loop` / `full_eds_process` 数量一致。
- `rbf_diversity_metrics.json` 可解析，`rbf_diversity_trace.npz` 可读。
- 抽查 PNG 非空且尺寸正常：`eef_3d_before_after_final.png` 为 `1800x600`，`pairwise_distance_hist_before_after_final.png` 为 `800x500`。
