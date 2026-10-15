# 文档导航

从[研究提案](research/research_proposal.md)理解目标，从[研究进度](research/research_progress.md)了解已完成内容和下一步；开发约束见根目录 [AGENTS.md](../AGENTS.md)。

| 用途 | 权威入口 |
| --- | --- |
| 安装、模型/任务资产与 Codex 接入 | [installation](steering/installation.md) |
| 三模式机制、公式、Stage/reward 合同 | [architecture](steering/architecture.md) |
| 运行、结果判读、审计与归档 | [evaluation](steering/evaluation.md) |
| 已验收 low 结果 | [results](steering/results.md) |
| ultra 对照、所有尝试与归因边界 | [reasoning-effort-comparison](steering/reasoning-effort-comparison.md) |
| 当前源码目录对应的研究分支与历史标签 | [分支索引](maintenance/branch-index.md) |
| 控制代码重构与开源入口整理 | [本轮发布报告](maintenance/public-release-20261015.md) |
| 主线发布、清理与历史工作区映射 | [整理报告](maintenance/repository-consolidation-20261015.md) |
| main 清理候选及 Stage/Codex 必要性 | [依赖审查](maintenance/main-scope-and-control-dependencies-20261015.md) |
| 从 GitHub 查阅历史分支、工作树和未提交源码 | [远端源码索引](maintenance/historical-source-index-20261015.md) |
| 历史源码发布范围、脱敏与验证 | [发布报告](maintenance/historical-source-publication-20261015.md) |
| 上游 VLS 在线控制比较、99 分支解释与本轮实际清理 | [控制比较与清理](maintenance/vls-control-and-noncore-cleanup-20261015.md) |

`00_overview`、`01_specs`、`02_analysis`、`03_evidence`、`04_plans`、`05_runs`、`08_archive` 保存早期研究依据，按原路径保留供历史引用。其旧日期说明、任务计划、绝对路径、模型和预算不是当前开发约束；不将其视为最新运行说明。当前机制与结果以 `research/`、`steering/` 及实际源码/配置为准。历史差异不通过回写旧证据消除。

2026-10-15 将用户原有的四份未跟踪文档按原字节纳入版本管理：[HANDOFF](08_archive/HANDOFF-20260915.md)（随后原字节移入历史归档）、[旧执行指令](01_specs/2026-09-21-rdt-qd-ed-autoresearch-execution-prompt.md)、[旧实验计划](01_specs/2026-09-22-rdt-qd-ed-object-swap-next-round-experiment-plan.md)、[旧 VLS 链路分析](02_analysis/vls_guidance/2026-06-05-rdt-guided-denoise-loop-vls-steering-analysis.md)。它们只描述各自日期的历史状态；其中旧入口、预算和“尚未合入 main”等结论不覆盖当前 Progress。原文中的机器路径按历史归档索引追溯，不保证在新 clone 中可直接访问。
