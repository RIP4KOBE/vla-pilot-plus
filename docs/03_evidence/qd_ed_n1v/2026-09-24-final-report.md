# N1V GPU2 实验结论：Stage 事件解析失败，候选尚未测试

N1V 已关闭为 **INCOMPLETE_UNEXPECTED_STAGE_ERROR_ITEM_NO_ADOPTION**。
30 个主回合只派发了 Q0/task0：0 个有效结果、1 个无效结果；29 个未派发，
恢复次数0/6。N1 未测试，不能声称 N1 改善、退化或达到 ≥5/10。

## 执行与错误证据

- 执行源码：`c0a2b2a851a1b35ccd99d5bec5b4d4ddaeb5d394`。
- 冻结计划：`data/qd-ed-n1v-approved-plan.json`，SHA
  `d91ef55173c76c1f2df308f57912a515fa3e7006d23dbf0d255f4aa3e7e7fefc`。
- 批准记录：`resource/n1v-approved/authorization.json`，SHA
  `531c66107cafe3ad650b974f459f0f4a3ddc085042dd8354d7e59b562af87015`。
- 实际 GPU2/EGL1；回合进程3220158、队列3214148均已退出，共享运行锁已释放。
- 主回合共317.970286秒（0.0883250795 GPU小时），到152环境步、19动作chunk；
  7个引导chunk、12个非引导chunk。全部已记录搜索为176候选/11评分批次；
  配置、任务身份、计数和数值/选择不变量检查通过，GPU Xid记录为空。
- Stage 共5次应用层调用，前4次成功。第5次97.145296秒后有完整回复、完整
  用量、`turn.completed`、退出码0，`process_timed_out=false`；异常为
  `codex_unexpected_item`，不是180秒的`codex_timeout`。
- 第5次事件序列包含4条编号重连提示、1个`error` item、1个`agent_message`、
  1个完成事件。回复可严格解析为stage/guidance/evidence三字段JSON。
- error item的脱敏类别为stream_disconnected/websocket/transport_fallback，
  长度105，SHA `0501c4478535c7c3cb21c2debf3b9f2a76d84cd3ca2be4259a091fc70b53e40f`。
  在固定CLI0.155.1二进制中确认存在字面前缀
  `Falling back from WebSockets to HTTPS transport. `。
  这支持“传输回退通知被严格拒绝”的解释；原始error文本未保留，不能声称
  已逐字重放该历史事件，底层连接不稳定的根因仍未确定。

本次tokens完整：输入54,432（其中缓存13,824），输出289；不要将缓存重复
加到输入。内部HTTP请求数和重试数仍未知。新的恢复分类器明确拒绝本次回合：
`N1V execution error is not a Stage timeout`。保留原始终态`event=valid`及
`outcome_valid=false`：前者是账本的完成类别，不代表科学有效。

## 为什么停止而不重跑

用户批准的 `n1v-bounded-recovery-proposal.md` 只授权明确、不完整的
`codex_timeout`，并明确要求“不可恢复错误……停止版本”。本次有完整回复且
未超时，因此不能动用6次超时恢复额度，不能事后重新分类，也不能直接采用
该回复补写缺失的后续环境轨迹。合法任务成败与本次无效执行应分开报告。

## 预算与修复准备

共享总计115/250次尝试、16.1696985304/48 GPU小时；分组实际
baseline13/development95/recovery7，验证/正式均0。现行上限仍为
13/124/60/40/13，扣除受保护100次/24GPU小时，可用29开发+6恢复、
7.8303014696 GPU小时。未改写旧结果或挪用保护额度。

N1V启动前207项不同CPU检查通过，完整源码/模型/任务输入/登录检查通过。
关闭后实现了**尚未启用**的独立策略`completed_transport_fallback_v1`：
只接受至多1个完整匹配固定前缀的回退error item，必须位于唯一turn内、完整
回复之前；之后必须依次得到唯一合法JSON回复和完整usage、零退出码，其他
未知错误、工具、重复/乱序回复、超时和缺失用量仍拒绝。应用层仍调用一次。
新增策略不会改变旧策略哈希，N1V runner仍拒绝新策略；没有新增GPU或在线
Stage诊断。最新202项CPU检查通过6.57秒，包括明确旧策略仍拒绝该item、
重复回退、错误顺序、非零退出和不完整证据拒绝路径。

新策略公共哈希：`47b97a211a069a6f104f7928e32aeaa0f72031e7a948ee320ee1ef3416fdd6d2`。
下一版具体方案见`experiments/iteration_001_execution_intent/n1w-transport-fallback-proposal.md`。
其改变有效响应的接受规则和分组额度，需要新协议授权；尚未生效。

完整机器审计：`/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z/analysis/n1v/final-audit.json`。

关闭后核验：`analysis/n1v/closure-verification.json`的10项检查全部通过；N1V之前的整个账本字节与授权时SHA一致，原计划和全部终态证据未变，87个执行源码文件可从原提交逐字恢复。关闭后的修复提交为`5386efc1bff9b7a8d2c5aa9a12ec1e0499e2adc3`，没有用于任何N1V回合。
