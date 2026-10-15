# 文档定稿最小清单

此目录是外置草稿，未写回根文档。文档基线为冻结runtime `33954ead452927fc3168efb610487a688f89169e`；草稿以2026-10-13 16:34 UTC汇总为结果快照：EDS完整有效3/10，VLS/EDS+QD与整体整合仍PENDING。用下面清单定稿，保留原始受测身份。

1. **先完成冻结验收。** 三组结束后，在源码仍匹配时运行最终汇总；读取每组完整audit、逐任务合同/机制报告、status和统一acceptance JSON，记录文件SHA。不从stdout片段或成功视频数独立填分。
2. **填写唯一结果表与整合gate。** 在 `docs/steering/integration-status.md` 保留已完成EDS的原始audit与重新只读审计汇总依据，替换 `PENDING_{VLS,EDS_QD}_{SCORE,ACCEPTANCE}`，补每任务outcome、validity、基础设施错误及实际计算/服务统计。整合要求三组cohort均完整有效且本轮EDS≥3/10，写入 `PENDING_INTEGRATION_ACCEPTANCE`；低分可仍是有效cohort，该工程门槛不是统计非劣效证明。保留迁移3/10整节。无效/未完成组如实保留，不以旧轮或选中任务补齐。
3. **刷新状态摘要。** 更新README开头、CONTRIBUTING状态段、architecture开头和status核对时间/运行状态；完整CPU1403、设备/数值与公共预检是已完成事实，不改回pending。更新后的三组状态须对应同一汇总快照。
4. **分别填身份。** 将最终冻结验收JSON/hash写入 `PENDING_FINAL_ACCEPTANCE_JSON_AND_SHA256`。若采用后续审计器，写入 `PENDING_POST_COHORT_AUDITOR_IDENTITY`；真正合入main后才填 `PENDING_MAIN_MERGE_COMMIT` 和README provenance。运行仍绑定原runtime commit，即使发布commit包含基础设施修复。来源版本/worktree映射及prompt/raw-blob命名例外只留README provenance。
5. **处理候选功能。** `evaluation.md` 的 lifecycle/archive命令目前明确“已准备、未应用”。只有候选补丁实际接入且验证通过，才更新 `PENDING_INFRA_INTEGRATION`、命令状态与新测试记录；保持冻结runtime1403与候选36项新回归/140项已有回归分别归属；保留真实复制迁移归档14081项合同检查及legacy-only边界，并分别保留公共EDS真实v2复制归档receipt及独立checker身份；两者不能混称同一种验证。未合入则保留候选说明或删去未交付功能，不能称现有保证。
6. **补交接入口并检查。** 将 `PENDING_EVIDENCE_ARCHIVE`、`PENDING_MODEL_ASSET_ACCESS` 替换为获准分享且可访问的清单/位置，保留原始日志、视频、hash与许可证。核对相对链接、三个method帮助/CPU配置解析、实际命令与版本；确认文档只引用已完成事实，最后生成文档diff交审阅。

外部已核验引用来自 `upstream-attribution-draft.md` 与 `codex-install-doc-note.md`；本次编辑没有重复发起网络、模型、GPU或登录请求。VLS引用只归属上游方法，不把本轮结果写成论文成绩。
