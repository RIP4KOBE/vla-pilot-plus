# 当前：Codex接口复测通过，V13运行，V14修复自动接续已排队 — 2026-09-30T10:02:03.756463+00:00

Codex独立真实图片请求于2026-09-30 09:48 UTC通过：gpt-6-astra/low，单次CLI调用，21.11秒，五字段JSON有效，无失败和应用层重试。证据：artifacts/stage_closed_loop_20260929/codex-availability-retest-20260930T094804Z/result.json。Poe继续禁止；当前账号接入可用不等于任务性能恢复。

V13 `codex_only_v13_historical_initialization_online_full10` 仍在GPU2运行：已完成7/10，成功0，当前task7 step656。supervisor2217380、worker2217645。前8个任务reward全部通过64项C0检查，首批关键点/粒子CSV/21阶段张量与历史一致；已记录查询无错误。完整分数尚未产生。

已确认Stage控制整合错误：Codex明确报告held+occluded+unsupported时，控制器因为要求clear而不进入Stage2；V13 BBQ step80/96均如此，step96 grace到期错误恢复接近ED。V13与V11前96个实际动作完全相同，首个分叉就在96；96步原图人工检查确为瓶子在夹爪下方悬空、位于篮上，目标上半部被夹爪遮挡。此证据支持具体控制修复，不说明所有失败皆同因，修复效果仍须在线实测。

V14草稿：仅允许明确held+occluded+unsupported经过原机器人矛盾过滤后建立Stage2与visual_hold；unknown不升级，完成依然要求clear+inside_goal+not_held+supported两次时间分隔确认。API模型/推理、reward、初始化、夹爪动作及其他设置均保持。137项草稿控制回归+6项队列保护检查通过；运行中的V13源文件哈希全部未变。

自动接续队列已启动，PID2595833，状态artifacts/stage_closed_loop_20260929/codex-v14-continuation/status.json。等待V13真实退出和完整两层有效审计；若最终<3/10，则保存V13视频/诊断/记账，核验源哈希，安装草稿，重跑安装后检查，冻结并启动GPU2 V14完整十任务。若V13>=3，停在视频复核节点；若任何检查失败，保存错误并等待本会话继续处理，绝不改写结果或回退Poe。队列与GPU worker必须一起管理，勿重复启动。队列未派发前可写queue/cancel.json取消后续派发；用户暂停时应停止本研究拥有的队列与worker。

V14方案与变更：artifacts/stage_closed_loop_20260929/drafts/codex_partial_visibility_v14/proposal.json、source-changes.json。总目标尚未完成，不把API可用/CPU测试/计分阈值等同正常目标搬运恢复。


正式十任务结果完成后在对应run审计与视频索引中保存。


## 验收口径澄清（V14启动前，2026-09-30T10:32:15.828695+00:00）

严格遵循用户明确门槛：单个冻结版本的完整在线十任务，环境成功率≥3/10，全部源代码/配置/请求来源/初始化/真实退出审计有效，并保存失败、配置、视频及最终分析。最新用户要求只用Codex，因此旧goal中的Poe名称不再代表当前接入授权。此前助手附加的“至少3次正常目标搬运”不是用户新增验收门槛；成功视频中的异常篮子运动必须如实另列，但不改写环境分数，也不以额外门槛替换原目标。这是在V14启动前固定的解释，不能在结果出现后调整计分。
