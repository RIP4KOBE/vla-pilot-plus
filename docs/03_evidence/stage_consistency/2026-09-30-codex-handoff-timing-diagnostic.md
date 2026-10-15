# Codex 在线控制的交接时机诊断

2026-09-30，V14 完整十任务仍在 GPU2 运行。本文件仅记录只读轨迹诊断，未修改 V14 源码或参数，不是整轮成功率结论。当前接入为 Codex 账号 gpt-6-astra/low，禁止 Poe。

## V14 已完成前两项

两个任务各执行720步，均失败。前两项初始化关键点、首批粒子与记录张量对齐历史C0，1440个执行动作均等于RDT原始七维输出，无覆盖。81次Stage查询无错误。

Alphabet soup：V13与V14前664个动作相同，step632与664原始图片分别逐字节一致。632的在线visibility标签有clear/occluded差异，不能把全部阶段分叉归因于单一代码改动。664两版均明确报告occluded+held+unsupported，旧版恢复接近ED，新版保持Stage2/ED关闭，符合修复目的；最终仍失败，因此局部控制正确不等于性能恢复。

Cream cheese：两版720个实际动作完全相同，修复没有改变这条失败轨迹。144原图可见目标被抓持；176目标被篮沿遮挡，unknown判断有图像依据。184无新图像，恢复来自张开夹爪、目标距离的持续测量和篮外几何，不能声称184有视觉确认。

证据：V14 run下 `first-two-observation-review.json`、`first-two-v13-trajectory-comparison.json`、`initialization-comparison.json`。后者在本检查时仅前两项可用，须由整轮结束后的检查覆盖十项。

## 历史成功橙汁任务的不同失效点

历史C0与已完成V13的step0/8/16中，完整候选流、observer checksum、选择索引和reward一致。第24步，历史继续执行ED；V13因normalized reward=0.8631944且目标距离0.082283米开始64步contact grace并关掉ED。此时模型报告grasp=unknown、support=supported，原图只支持“目标上部被遮挡、尚未确认安全抓持”。历史第32步才关ED。

V13第40步图像可见闭合手指与橙汁盒分离，模型也给出clear/not_held/supported/outside_goal，夹爪宽度0.00192075米。然而原纯夹爪空抓过滤需要持续16个环境步：第40步才满足width<0.005，第48步已张开而清除计时，因此没有触发恢复，grace持续至88。这里未发生API失败。

这定位了两个独立候选问题：reward+10厘米距离可能过早终止接近；明确负面视觉和空夹爪证据没有联合终止未成功的抓取宽限窗口。它们不是“必须恢复Poe”的证据，也不是完整失败因果已经证明。

原始证据：`artifacts/stage_closed_loop_20260929/v13-orange-handoff-diagnostic.json`，含历史/当前事件、前缀比较、原图人工复核。历史Stage也有可疑0/2转换，不将旧标签作为真实抓持或真实完成标注。

## 后续约束

先完成冻结V14的全部十任务、源代码与调用来源审计、视频复核。若完整结果仍低于3/10，再将contact-grace进入条件和空抓复查分别设计为前瞻性修改，检查是否伤害其他任务并完整重测。不得用历史回复控制在线回合、拼接版本成功数、预测修改后必然成功，或在当前批次中途应用候选修改。

## 80%阈值的语义不同

12:06 UTC 的源码只读检查进一步确认：`main.py` 的 legacy `_update_stage` 把 reward 跨过 `schmitt_upper=0.8` 用作查询触发；是否关闭ED由在线模型返回的 `need_guidance` 决定。历史橙汁step24恰好体现这一点：触发了80%查询，但仍保持Stage1/ED开启。

新 `core/stage_contact_handoff.py::apply_handoff` 则在reward≥0.8、distance≤0.10m及最小接近时间满足时，直接设置64步contact grace并关闭ED。它明确不是“抓持已成功”，但其行为与原查询阈值不同。这是控制机制差异，不应把相同数值称作相同实验setting，也不能推断换账号配置即可解决。未来若本轮不足3/10，需要单独验证handoff条件及失败窗口取消，而非把旧80%查询阈值自动视作充分的交接条件。当前V14仍然冻结，未应用任何新修改。

## 历史橙汁成功依赖一次失败后的恢复

12:14 UTC 补查原C0的285帧成功视频，人工检查32/40/48/56/88/104/284帧。32与40步夹爪和橙汁盒明显分离，旧Stage2并非真实抓持的可靠标注；48步原生张爪，56步重新打开引导，再次接近，后续才实际搬到篮内并于285步结束。不能把历史成功归因于首次Stage2正确，也不能仅复刻错误标签来证明新语义机制正确。应同时关注交接和失败恢复，但目前证据不预测任何新规则的成功率。

抽帧与复核：`artifacts/stage_closed_loop_20260929/orange-historical-video-review/extraction.json`、`review.json`。未调用Poe、未重放回复控制新轨迹、未修改冻结V14。

## V14 milk：已经观测到搬运线索，但缺少建立保持状态的路径

当前milk回合的352–424步已保存为 `runs/codex_partial_visibility_v14_historical_initialization_online_full10/milk-uncertain-carry-diagnostic.json`。人工复核376与408原图：376目标悬在夹爪下方、手指接触区域遮挡；408接触/卡住/篮沿支撑仍难以由单帧区分。

376的在线回复为occluded、grasp unknown、support unsupported；机器人信号显示目标相对初始关键点升高约9.17厘米、距手约4.73厘米、夹爪宽约5.39厘米、上一动作为CLOSE，carry线索已从360持续。现 `stage_carry_hold.finalize` 要求已经是Stage2且已有visual_hold，因而不能用该线索建立保持状态；408抓取窗口到期重新开启ED。

如果完整V14仍不足3/10，可以评估将明确的视觉悬空信息与持续的机器人搬运测量联合用于一种有独立来源记录的推断抓持。它必须保留原始unknown回复、拒绝负面机器人证据或释放中的状态，不能把抬升代理当成抓持真值或完成判据。这个方向未实施，不能预言保持ED关闭就会使milk成功；当前回合及整轮结果仍以真实环境评测为准。

## V14整轮负面视觉与空夹爪复查：并非可以无代价加入的规则

13:06 UTC 对完整V14做只读扫描，发现79条fresh clear/not_held/supported/outside_goal仍处于contact_grace，21条同时满足即时夹爪宽<0.005m且上个执行命令CLOSE。这些时间点持久性no_grasp尚未成立。原始结果 `runs/codex_partial_visibility_v14_historical_initialization_online_full10/negative-vision-during-contact-grace.json`。

需要特别保留反例：最终成功的pudding在48步也满足该条件（宽0.00242171m、contact_until88），所以立即取消grace会改变已有成功轨迹，不能宣称它必然保留两项成功。BBQ没有该类负面视觉条目。该扫描支持失败复查是独立机制问题，也说明必须与当前V15距离修改分开进行前瞻性验证；没有安装新规则，当前全十项继续冻结。

V15首项实际24步已因6cm条件保持ED开启，动作首次分叉恰在24；对应观测与reward数值同V14，首项全部初始化检查仍通过。检查点 `runs/codex_contact_radius_v15_historical_initialization_online_full10/first-handoff-checkpoint.json`。这里只证明条件实际生效，尚非成功率证据。
