# N30 approach→handoff：尚不足以提名新的 QD/ED 干预

**结论：NONE_YET；唯一建议是下述已禁用的最小 handoff 证据读取。** N30 R2 已闭合为 `REJECT_NUMERIC_DEV_FUTILITY`，C0/Q0/N30 各 **0/2**，不是0/4；剩余两任务即使全成功也达不到冻结3/4。原两次工程 invalid 与费用不改写。终态根审阅为 `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n30_executed_progress_continuation/feedback-repair-continuation-v1/root-terminal-review-v1.json`，SHA `0a840aebc3e63fd3f9940b0bd51b042fb471385e6522a74493c916b7b8c39f91`。

已接受的首次 active 诊断表明：两格 step8 插入和执行绑定正确；task0 在父代轮0/1各有一条可由内容支持的warm分支，之后未确认；task1没有。最终选中均为内容支持的nonwarm，然而已执行8步仍分别向固定step8目标快照接近 **89.527 / 92.151 mm**，所有这8步夹爪命令均为−1。抓取、接触和旧尾部优越性未知。直接内容或单亲谱系不是完整因果影响；QD分区/占用/分配及ED群体耦合仍可能传播插入影响。不能由此断言插入无影响，亦不支持直接重开保护lane。证据：`/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n30_executed_progress_continuation/lineage-diagnostic-v1/decode-v1/root-terminal-review-v1.json`（SHA `09b8d5e77df586478958fe1a15ccfafcc66667de363a5326110423e4ffcf505e`）及已绑定结果；本轮未重开其tensor。

## 两格完整索引得到同一首次切换

| task | 全部决策 / EDS metrics | 首个连续 handoff | canonical批 / parent轮 | 两段实际反馈 | 下次EDS step | stat容器/字节 |
|---|---:|---|---|---|---:|---:|
| 0 | 90 / 24 | e0:d3:s16 → e0:d4:s24 | 11/10 → 0/0 | 各8 action/outcome/return | 64 | 34 / 12,214,864 |
| 1 | 90 / 6 | e0:d3:s16 → e0:d4:s24 | 11/10 → 0/0 | 各8 action/outcome/return | 672 | 34 / 12,215,120 |

完整索引与全部metrics逐step一致，因此step24确为首次 realized EDS-off，非仅一条metrics缺失。两段reset_sequence均0，32个实际step的dispatch→action→outcome→return次序齐全。step16各有16个总评分批（11 canonical）；step24没有评分/父代/选择事件，但有decode、commit和实际执行/反馈。step24没有N30 ack，不等于没有环境执行。

这里的事件索引只有身份/类型，**没有Stage、use_guidance、provider内容、tracker或动作值**。reset_sequence=0排除记录中的环境reset，不证明Stage没变、N30内部history没清。缺失起点已确定，但“为何禁用”“是否回退/闭合/保持”仍Unknown。完整两格标识、所有90决策census、source/plan/context/receipt/audit哈希与精确68容器路径在 `handoff-bindings.disabled.v1.json`；payload哈希只是原索引与已绑定receipt的一致值，本轮没有重新测量。

## 静态语义约束了可解释范围

- Main:1383–1419接收原Stage查询的 `(new_stage, need_guidance)`；Stage改变调用 `reset_stage`，仅guidance改变则调用 `reset_eds_chunk_memory`。Main:1738–1749还会在需要引导却没有当前guidance函数时后置禁用，或者在配置路径缺失时禁用。**不能仅由本次EDS-off区分这几条分支，更不能叫Stage误判。**
- policy:1604–1609在新chunk且 `not use_guidance` 时清除N30history；:1620–1657分别走guided与单行unguided生成；Main:1788–1796传的是最后的use_guidance。N30不是所有阶段均生效的执行器记忆。
- progress:119–137要求相同episode、reset generation、Stage、provider和tracker/target身份，恰好连续8次ack，且对旧target快照严格接近；否则不能激活。policy:5093–5101还要求识别当前provider成功。因此跨Stage强行续用旧目标、强制EDS或修改Stage/感知/执行器，均不是当前已授权的QD/ED小改。
- recorder:200–206会保存最终Stage/use_guidance及provider身份；:238–270保存commit与实际反馈。它们的值在容器里，可由后续有限读取观察；**最终use_guidance仍不等于原查询need_guidance**。原provider代码/Stage回答不在建议范围。

精确文件完整SHA和上述窗口SHA见 `input-source-manifest-v1.json` / `static-source-read-v*.json`。核心源：Main `5209b0ac…28f93`；policy `ba1728c6…9928a`；progress `7aead7c8…39d9c0`；recorder `899659e6…e2295`。没有生产导入、测试或数值重放。

## 为什么不提名新干预

现在新增的依据是“**实际接近之后，首次在24步离开搜索**”，而不是“warm不存活所以失败”。两段缺失的实际动作与状态足以改变后续研究判断，但尚不能指定一个有新依据的quality、parent或ED变异公式。N3式几何残差、N5/N12/N22式近距/close重排、N24式行为保留及N30更长尾部保护都不能仅因这次handoff而成为新机制。既有复核也明确N25并非全部零成功；不混合cohort成功率。N29各0/6的活跃限距负结果不证明一切反馈都被否证。

**唯一可证伪的定位问题：** 在两格固定16→24切换处，已执行命令与EEF/夹爪是否继续先前接近，还是出现局部反向、停滞或命令开闭改变？若两格都继续接近，则“这次handoff即打断接近”的强解释被反驳；若有反向，也只成立时间相关，不能归因为Stage错误、不能证明保持EDS/旧尾部会成功。若Stage/目标身份已变，对旧快照的距离只作旧参考描述，不能当新阶段进展。无真实接触/holding标签时，不把qpos闭合称抓取，不拟合orientation或距离阈值。因而本次**0个算法提名**，不提交GPU行、参数菜单或效果门。

## 唯一 disabled 后续建议

`minimum-evidence-proposal.disabled.v1.json`选择tensor路线，**没有同时申请视频路线**。全部两格各取已冻结的step16与24决策及实际steps16..31；共68容器、**24,429,984 bytes**，每份最多读取/哈希/CPU解码一次。一个guided主容器包含未执行候选、评分与parent等共存数据，weights_only仍会完整解码；必须另行明确授权整容器，分析/导出只限身份、最终guidance/provider是否存在、固定step16目标快照、实际命令及EEF/quat/gripper状态。provider body、评分、reward/success、未执行候选一律不分析。无需新模型、打分、RBF、仿真或视频。

这一个路线可直接区分**动作切换后实际退化**与继续接近，也可发现**记录目标/tracker身份或快照变化**；但不能把后者等同选错物体，也不能从夹爪qpos证明**未抓到**或持有物体。若这两个物理/语义解释仍决定算法选择，结论继续Unknown；本次不并列申请第二种视觉读取。

建议root若选择执行，再冻结reader及一次120CPU/120wall秒、2CPU、16GiBAS、ZIP/unique storage各64MiB上限；缺字段/身份歧义保留Unknown，失败保留且不自动重试。本文件和绑定清单均 `executable=false`，当前没有decoder、payload读取或后续release。唯一可能改变的下一决策是“是否已有足够任务相关证据来设计新的QD/ED干预”；不是自动改变Stage、保持memory或降低3/4门槛。

资源/读取：主metadata扫描0.276443CPU秒，17,024,378读取字节；加静态来源（含重复）和一次scope复读后17,737,664字节。guard拒绝0；payload open/hash/decode均0。静态与交付处理详见 `resource-summary-v1.json`，小型展示命令未单独计CPU，另收取保守预算预留而不伪报精确测量。所有写入只在本目录；旧诊断/代码/状态/预算保持冻结。
