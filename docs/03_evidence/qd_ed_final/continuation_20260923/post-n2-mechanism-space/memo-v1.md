# N2 后 outer-loop：待证伪机制队列（仅文档，非下一实验授权）

结论：先选 **COLLECT_TARGETED_EVIDENCE**。以下两项是有具体反驳条件的待审假设，不是已经有充分依据进入下一轮 Dev 的候选。排序表示证据核查优先级；二者都尚无直接支持其核心因果链的测量，不能只凭名称实施。若本次有边界的完整 chronology／必要定向复查仍补不上这个缺口，应按原任务 §6 报告 `CONCLUDE_TARGET_NOT_MET` 及缺少的证据，而非再换权重试跑。

Root 告知 N2 本轮 30 valid / 31 dispatch：C0 2/10（tasks 5、8），Q0 1/10（8），N2 1/10（8）。本备忘录没有读取或重新验证完整 cohort 报告，也没有打开 task1–9 的任何实际产物。这些数字只能支持 N2 未过其冻结数值门；不是研究完成，也不是某一失效原因的证据。不能用 task5 或已知成功标签形成部署分支。

## 已有依据及不可跨越的边界

- 原 prompt §4（107–125 行）允许 observation/action/过去执行反馈参与 QD quality、ranking、parent/proposal 和有证据的跨 chunk 状态；固定 Stage、外部 provider、checkpoint、动作／成功语义。§5（127–141 行）要求区分 proposal、selection、closed loop，未执行候选结果仍 Unknown，一次一个主要改动。§6（143–163 行）规定先冻结后实现、同轮对照、outer-loop 和无依据时停止。§8（214–224 行）保留 population16 / 10 iterations / 176 evaluations / 11 calls，并核对全部模型与辅助成本。
- N2 protocol 第7–15行已经把内部 Q8 与实际所选动作的原始 raw quality 分开，保留 raw→原归一化→Stage。第35–39行明确：正确且活跃而结果差的机制应拒绝，不能把它重新包装为有利结果。下一假设不延长执行 horizon、不再调 Q8 的截断点或权重，也不叠加失败 N2 后把差异归于另一组件。
- 已授权 task0 数值摘要显示 first OFF：N2=C0=24，Q0=16；此后 reactivation 分别0/7/5。N2 后696 actions均 OFF，但 EEF 仍有约0.397m净位移和1.168m路径。Stage 五次查询均成功。这里没有“初次更早关指导”“完全不动”或“Stage传输失败”的证据。
- task0 原始所选 raw/internal 关联已完整，但只是3/29/52个 guided decisions。N2 step0 已知有原 raw tradeoff；它说明新目标改变了选择，不能说明改变改善了物理结果。目标相对进展、selected projection tracking、抓取、接触、物体位姿和未执行反事实仍 Unknown。
- 已授权固定视频格子只补充场景和遮挡描述：不能证明抓取、放置或目标身份。keypoint 同 index 位移也不能自动当成被操作物体的真实进展。

因此，改变 Stage prompt/trigger、把旧 gripper-first 输入改成 last、强制持续指导、或在 OFF 时额外执行 QD 都不属于本备忘录的算法提案。只能改变原本会发生的 guided search。N2 task0 长期 OFF 后的行为不是这些机制能直接干预的区间；是否存在足够、任务相关的可作用区间需要完整 chronology 回答。

## 1．以最近已执行偏差校正内部几何评估（优先核查；目前证据弱）

**可证伪解释。** 如果同一观测／动作契约下的短期几何投影存在局部可重复偏差，那么 Q0/N2 在正确优化其预测距离时，仍可能误排真实可执行运动。新机制不是再改距离权重，而是让上一段真正执行过的反馈纠正下一段的内部预测坐标。N2 的无收益只使这个解释值得检查，不证明偏差存在。

**单一可操作机制草案。** 从原 Q0 出发，不叠加 N2。对紧邻的、完整执行且无 reset/语义变化的 guided chunk，取已选候选已有投影终点与当前实测 EEF 的差 `r = p_actual,end − p_projected,end`。最小待审形式为当前候选既有投影的 `x'_t = x_t + (t/8) r`，起点不变；内部质量按经 source/code 严格识别的原 provider 距离表达式和原 t1..t7 权重计算。没有训练、参数拟合、额外 projector/provider/model 调用。第一段、身份不明、缺反馈或不连续时回退原 Q0；reset、目标语义／registry 身份变化、OFF间隔和不完整执行均清空。这个“上一段偏差可迁移”的固定单位增益是待证伪结构假设，不是已获批准或可从结果调节的系数。

原 XY archive、质量驱动 replacement、parent allocation 和 ED 搜索继续实际作用；改变的是供它们使用的内部 scalar。原 provider 仍吃原投影t1..t7，原 raw 随候选身份流转到 Stage，辅助预测／梯度不变。不能把校正坐标传回外部 provider、Stage、environment 或观测。native arithmetic、dtype、ties 和 active 后数值失败须在新卡冻结，不能通过 CPU 重建精度获得虚假排序变化。

**先检查什么。** 完整 chronology 可列出所有 eligible 连续 guided pairs、reset/Stage/指导断点与实际 EEF/gripper区间，不能直接计算 `r`。当前冻结 reader 明确没有 selected projection 分析，故需另立很小的已审计 Dev 读取扩展：只把实际所选候选已有 full projection 与该候选真实8步 prefix、时间原点和坐标系精确关联。所有 eligible pairs 都计入，不按任务成败或残差符号选样。若投影基准与真实 EEF 不同坐标/时刻，先判 Unknown，不计算看似有效的误差。

**反驳与晋级前条件。** 用较早 chunk 的 `r` 预测紧邻较晚 chunk 的残差；逐 episode 报告校正前后真实 selected-prefix 误差及方向，跨 task 只作分层，不把相关 chunks 当独立样本。若误差主要随机／不重复，校正没有稳定降低下一段误差，或者原生存储下根本不改变候选选择，则不实施或拒绝此解释。不得因少数获益 task 改增益。一个离线改选 witness 只证明活动，未执行候选结果仍 Unknown；最终收益仍由新的同轮 C0/Q0/候选 Dev 决定，不能用误差下降替代成功门。

**限制。** `r` 可能混合控制误差、动作后处理、投影近似及观测延迟；不识别具体原因。它不修复错误目标或接触模型。目标身份／tracker 失效不可观察时，不能宣称可靠长期校准；默认清空/回退优先。当前 task0 摘要没有测过残差，因此该方向尚未达到“有直接机制证据”的程度。

## 2．仅把已执行且反馈相符的计划续段作为下一次 ED proposal（次选；证据更弱）

**可证伪解释。** 如果有真实执行进展的计划在相邻 guided chunk 的重新初始化中被反复丢弃，而已有计划尾段仍有可用的行为差异，那么“每段从零开始”的 proposal 分布可能导致 closed-loop 反复变化。这里不把 Stage 反复开关或 gripper 命令变化本身叫作丢失进展；需要先看到实际已执行 prefix 与下一段之间的具体关联。

**单一可操作机制草案。** 同样从 Q0 出发，内部 quality/provider 都不改；只在紧邻、语义相同且先前真实 prefix 可核对的 guided chunk 中，把前次选中完整动作计划移去已经执行的8步，将剩余续段经现有 ED renoise 接口形成 **一个** 当前16槽中的 proposal，替换原槽而非增加 batch、iteration、denoising 或调用。不足的尾端只能用本来就生成的 proposal 数据补齐，不能另调模型。进入 QD archive 后与其他候选按原 quality 正常竞争，无保送精英、保护 lane 或强制执行。是否能够在现有初始化接口做到严格等调用/等去噪步数，仍须先作源码可行性核对；做不到就不把它列为计算可比候选。

携带对象是过去已选计划的未执行尾段，不是声称已经验证其结果。只有前缀真的执行完成才考虑续段；未执行尾段、跨 OFF、reset、目标变化、observation错位或身份不明不能当成“已证实好计划”。若需要“反馈相符／进展”的质量门，该门必须来自可计算、source-bound 的过去 EEF与冻结目标关系，在新卡事前定义；目前没有该门的证据或批准阈值，不默认 target0。原 raw Stage 输入仍属于当前实际最终选中候选，不复用前一段 raw。

**先检查什么。** 完整 chronology 先给出相邻 guided 区间和真实 motion 的覆盖，确认作用点不是全部位于不可干预的 OFF 长段。之后只有在单独批准的 selected-plan 读取中，才能对全部 eligible 邻接对计算已执行前缀／当前新计划的动作衔接、实际 EEF方向及是否保留前次冻结目标的观测进展；不能用未执行尾段的投影声称其真实优势。若可用相邻段不存在、旧计划和新计划没有结构性区别，或所谓“进展”无法在部署可用观测下定义，则不给该机制在线预算。

**反驳与局限。** 一次预算内机制检查必须看到续段确实以替代槽进入搜索、被重新评估并经 QD参与 parent/final竞争，且没有额外模型工作；“存了 memory 但无影响”不是机制证据。若实际匹配前缀也不能预示下一段更连贯的观测进展，或任务收益未过预先冻结的 Dev 门，则拒绝，不增加保留槽或延长 TTL救结果。此机制完全不能强迫 N2 task0 在step24之后再启动 QD。

这与 H4/H5 的同段未执行 lineage rescue / protected secondary 不同；不承诺保留旧 raw 最大值，不通过更好的 retention 指标证明任务收益。它更接近历史 H3，但原 prompt 第67行已说 H3 缺乏首选依据；只有新“真实前缀推进后，在下一个可干预 chunk 丢失”的证据才能提升优先级。目前该证据没有建立。这里也没有重开 N1 无效 cell、复用其名字或调整其分区参数。

## 完整 chronology 后的有限决策

1. 先消费经 root 单独授权且 all30 身份/audit/report-authority 均通过的 chronology；按任务完整列出 guided机会、Stage/OFF运行和实际 EEF/gripper动作。成功标签仅用于最终完整 outcome 报告，不用于筛机制资格或删“不好解释”的样本。明确实际 motion 并不等于任务进展。
2. 该报告本身若只说明未指导区间差异，不能推出 QD search 的误选或上述校准／续接必要性。只对有清晰可计算缺口的一个方向再冻结小范围 selected-plan/projection 读取；不扩展到所有候选、隐藏评估或额外仿真。无授权时不读。
3. 只选一个主要机制，不把二者叠加。需要肯定的部署可用关联、原生质量改选／proposal作用的见证、默认关闭回归和完整 raw-Stage 隔离后，才写新 hypothesis card、source freeze 与同轮 C0/Q0/候选协议。没有证据则停止假设生成；原 §6 的 `CONCLUDE_TARGET_NOT_MET` 是诚实退出，不代表空间被穷尽。
4. Root 目前给出的累计约79 dispatched 未在此查账；若79为准确已消费数，则240总上限减100保护名额只剩61个可用于其他目的的 attempt，但这只是算术，不是准入。48h上限及保护24h必须结合实际 charged time、未结算／预留、健康检查再核对。当前没有小时余额，不能分配新 GPU预算；不借用 validation/formal，且旧 valid task failure 不重跑。

本备忘录没有进行实现、额外科学读取、模型／provider／projector／simulator调用或 GPU操作；也没有修改 W、当前 N2 定义或任一结果。下一步的证据收集不代表候选晋级，更不代表目标完成。

## 精确依据

- W `docs/01_specs/2026-09-21-rdt-qd-ed-autoresearch-execution-prompt.md`，重点§4–6；§2只用于该文件已有的H1/H3/H4/H5历史约束，§8只用于计算契约。
- W `experiments/iteration_002_executed_quality/protocol.md`，7–15、29–39行。
- N `docs/03_evidence/qd_ed_final/continuation_20260923/task0-closed-loop-exploration/findings-v3.md`，5–29、48–56行；同目录 `source-schema-v1.json` 只作已授权字段/缺口清单。
- N `docs/03_evidence/qd_ed_final/continuation_20260923/task0-recorded-video-exploration/chronological-note-v1.md`，既有48格观察摘要；本次没有重新查看图片。
- 本次 parent 指令中的 cohort totals 是未在本轮独立核验的外部报告值；没有从其他实际 episode 补数据。

上述文件的本次读取 SHA 记录在 `sources-v1.json`；不引用受保护旧设计文档。
