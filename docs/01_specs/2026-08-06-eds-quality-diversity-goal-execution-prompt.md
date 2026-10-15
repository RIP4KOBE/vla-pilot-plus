# EDS Quality-Diversity Goal 执行 Prompt

进入 Goal 模式，完整执行已批准的 EDS Quality-Diversity 算法优化与 LIBERO Object-Swap OOD 实验。

唯一执行依据：

`/home/hynx/VLA-Pilot++/.worktrees/exp/eds-init-pg-diverse-sampling/docs/01_specs/2026-08-06-eds-quality-diversity-design.md`

开始后先完整读取设计文档，将状态从 `Draft for review` 更新为 `Approved for execution`。不得修改其中已批准的算法定义、参数矩阵、tasks/seeds、attempt cap、gates、ranking、GPU admission、validity 或 storage 规则。

首先调用 `get_goal`：

- 没有 active Goal 或现有 Goal 已完成时，创建新 Goal，不设置 token budget；
- 若存在不属于本任务的未完成 Goal，不得虚假标记 complete/blocked，报告冲突并等待清理。

Goal objective：

> 基于已审计的原始 `p2_stage_on_abs_rbf_control`，创建 `exp/eds-quality-diversity` branch 和 `/home/hynx/VLA-Pilot++/.worktrees/exp/eds-quality-diversity` worktree，严格按批准设计完成 config-controlled QD-ED 实现、TDD与相关回归、mechanism preflight、全部正式实验、逐job审计、不可变decision manifest、最终报告和进程清理，并判断同一套 `libero_object_swap` tasks 是否通过 task、mechanism 和 safety gates。

执行要求：

- 先检查 source worktree 的 Git 状态；不得回退、覆盖、复制或提交无关未提交修改。新 worktree 必须来自设计规定的 clean audited base commit，并记录完整 provenance。
- 所有实现与实验只在新 branch/worktree 中进行；legacy default 和原始 absolute-RBF control 必须保持兼容。
- 新 worktree 的 `outputs` 必须先建立为设计规定的 shared2 绝对软链接；任何大文件、视频、tensor、cache、log 或实验产物不得写入 home 下的真实 `outputs` 目录。
- 严格 TDD；目标测试、完整相关回归、`py_compile`、`git diff --check` 和全部 mechanism preflight 未通过前不得启动 formal jobs。
- 只使用 GPU 0..7 中通过 admission 的空闲设备，不干扰或共置外部 compute 进程。
- preflight、formal 和 retry 共用 append-only ledger，实际 episode attempts 不得超过 120；单 job 失败不停止其他 jobs，retry 不得改变 job/task/seed/config。
- credential 只由环境变量注入，不得进入 CLI、Hydra、日志、manifest、报告或 Git。
- 不得依据中间或最终结果调参、删减矩阵、追加实验或把 recovery slots 改作新配置。
- 正式结束后完成 task-level、参数主效应、archive机制、定性失败、安全和 latency 分析，生成只读 manifest 与最终报告，并确认无残留 runner/`main.py` 实验进程。
- 只有批准范围内实现、验证、preflight、11 个 formal jobs、审计、manifest、报告和清理全部完成，或在 attempt cap 内有明确审计后的 failed/incomplete 交付，才能将 Goal 标记 complete。结果 gate 失败不授权追加实验，也不妨碍完成已批准范围。
- 不安装、加载、调用或推荐已禁用的 Superpowers plugin/skills。

最终用中文简要报告：Goal 状态与用量、实现/config、测试与 preflight、shared2/软链接/GPU、jobs/episodes/attempts、task-level SR、QD 参数与机制结果、三类 gates、失败或无效 jobs、manifest/report 路径、credential/进程/Git 审计及剩余风险。
