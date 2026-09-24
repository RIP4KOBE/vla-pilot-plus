# GPU2 N1U 最终记录：Stage 超时，未形成正式算法版本

本版本于 **2026-09-24 03:28:17 UTC** 结束，结论为
`INCOMPLETE_STAGE_TIMEOUT_FINAL_NO_ADOPTION`。Object-Swap ≥5/10 的正式目标
未被证明；N1 尚未进入在线测试，不能据此认定其算法机制有效或无效。

## 执行结果

| 组别 | 有效结果 | 无效回合 | 未执行 | 本轮可得结论 |
|---|---|---:|---:|---|
| Q0：RDT+ED+原 sparse QD | task0 失败，0/1 | 0 | 9 | 只有一个有效对照结果 |
| C0：RDT+ED | 无有效结果 | task0，1 个 | 9 | Stage 超时中断 |
| N1：目标距离×夹爪正向指令占比描述符 | 未测试 | 0 | 10 | 效果未知 |

计划30回合，实际派发2回合，科学有效1回合，无效1回合，未执行28回合。
这些不构成任何一组的完整10-task成功率，也不能作为新的 baseline 排名。
验证和正式验收均未启动。旧 N1R/N1S/N1T、另一工作树的 N2/N3 结果不并入
本轮分母，不补用旧对照，不以 Stage 判断代替环境成功信号。

Q0/task0 完成720步，用时670.029360179秒；17次 Stage 查询全部正常完成，
52个引导动作段各176个候选、11批评分，共9152个候选评分。所检查的数值、
计数、精英单调性和最终选择不变量均无违规，成本记录完整，内核无 Xid
记录。这个有效任务失败保留原样。

## 故障证据及解释边界

C0/task0 在完成88个环境步后，第5次 Stage 查询耗时180.209659953秒，
超过冻结的180秒等待上限。该调用只有1次应用层调用，记录8条编号重连
提示及一个 error 类型的 item，没有正常完成 turn、有效响应或完整用量。
`process_timed_out=true`；清理后的进程退出码0不能视为查询成功。

失败回合总计406.162460781秒，前4次 Stage 查询正常。两回合合计22次
应用层查询，21次正常完成、1次超时；这衡量调用完整性，不衡量判断准确率。
重连提示条数不等于实际 HTTP 请求或重试次数，后者仍不可观测。
失败调用的 token 用量未知；原日志中的已观测零值不能解释为实际零消耗。

内核监控没有记录 Xid。证据能定位到 Stage 调用超时并伴随重连事件，
不足以判断底层网络、服务端、配额或其他根因。此次失败不能归因于 QD
机制，也没有证据要求再次重启 GPU 或服务器。

失败身份：`rdt-qd-ed-final-20260921T093925Z__n1u_dev_t00_c0__aa2a8c792842`。
保留原终态：账本事件名 `valid` 是已完成判定的记账标签，而
`outcome_valid=false` 才是科学有效性；`failure_class=task_failure`、
`retryable_infrastructure=false` 均未改写。保留失败输出及全部成本。

## 停止依据与预算

用户已批准 baseline 剩余9次和 recovery 剩余13次转给 development。
已落实上限11/122/60/40/7，总上限仍240次/48 GPU小时；验证60次/14小时、
正式40次/10小时受保护。调拨及“再次无效即关闭最后一轮”的执行规则见
[批准记录](../../../experiments/iteration_001_execution_intent/n1u-budget-reallocation-approved.md)。

N1U 是已约定的最后一次共同工程条件修订。该规则要求出现无效结果或
基础设施失败时结束当前版本，不自动重试或建立新的替代 cohort，因此剩余
28回合没有继续派发。此处是研究路线停止条件，不是声称已经耗尽所有数值预算。

- N1U 两回合共0.2989421725 GPU进程小时（约17.9分钟），含无效回合。
- 全研究累计112/240次；development94/122，baseline11/11，recovery7/7；
  validation0/60，formal0/40。
- 全研究消耗15.7399580955/48 GPU小时；扣除24小时保护额度后剩8.2600419045小时。
- development 尚余28次，不足另建完整30回合比较；recovery 无剩余回合额度。
  不自动撤销已批准调拨，也不挪用保护预算。

队列和其 GPU worker 已退出，共享 runner 锁已释放，GPU2 空闲；没有手动
杀掉进行中的实验。源码、冻结计划和历史账本未被事后修改来接受此次失败。

## 实现与验证

执行源码为 `4170aeb52c029be17bf31b2933ad6e5a62b02cb3`。预算修改仅影响
分组准入上限；原30个回合的身份、顺序、种子、任务输入和算法配置逐项相同，
运行清单未变。预算、共享锁、队列和 provider 启动相关126项 CPU 检查通过，
完整模型/输入/source SHA及托管登录检查通过；没有增加合成在线查询或 GPU 探针。

执行计划 `data/qd-ed-n1u-budget-approved-plan.json`，SHA256
`84dedea9a5adbf38d13333faa0a1f843796013c2a73e46653b1b5f93d3400884`。
共享 Stage 条件 `codex_login_astra_low_json_reconnect_180s_v1`，
一次应用调用，固定 CLI0.155.1 / gpt-6-astra / low，严格 JSON 与完成状态验证。
单回合720步/1800秒、GPU2/EGL1、单 worker 和120秒空闲准入均保留。

## 下一步研究方向

下一版本应先独立排查 Stage 传输可靠性和失败可观测性，再消耗 GPU 做
机制比较。当前日志缺少 error item 的可诊断内容，现有证据不足以选择
“继续加长超时”作为修复；不应反复重跑整套对照来测试服务是否稳定。
预先确定脱敏错误分类、完整性/延迟验收及失败处理方式，三组使用相同冻结
条件，才有可解释的后续比较。

N1 原描述符假设仍待检验，应保留其实现和先验机制证据；此次事件不支持
改写它的有效性结论。任何后续全量比较都需独立、明确的版本与预算安排，
不能恢复已判定无效的身份，也不能把历史控制结果拼接成新轮次。

## 可复核产物

- [故障与最终预算审计](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z/analysis/n1u-stage-timeout/audit.json)：原文件 SHA、失败调用、终态和费用。
- [有效回合运行审计](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z/analysis/n1u/completed-runtime-audit.json)。
- [QD 机制审计](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z/analysis/n1u/finished-mechanism-audit.json)。
- [授权与调拨记录](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z/resource/n1u-budget-approval/authorization.json)。
