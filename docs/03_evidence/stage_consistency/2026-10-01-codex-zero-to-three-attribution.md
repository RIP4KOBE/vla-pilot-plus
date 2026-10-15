**归因结论：从最近可比的 Codex V13（0/10）到 V17（3/10），最有力的证据指向 Stage 控制器对视觉证据与 ED 开关的两处衔接修复。模型、推理强度、RDT/ED 主参数没有变；V14 恢复 BBQ 和 pudding，V17 新增 orange。API 接入在失败版本中也正常。**

本分析于 2026-10-01（北京时间）重新读取冻结配置、原始 Stage 日志和逐动作记录，复算版本间首次动作分叉。没有发起新的模型请求或 GPU 实验，没有修改任何已验收运行结果或科学代码。机器证据见[本次独立复算](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z/artifacts/stage_closed_loop_20260929/attribution_20261001/evidence.json)，分析脚本保留在同目录。

先区分两次“Codex 0/10”

最早的“当前源码 + Codex”复核为 0/10，使用旧 Stage 接口与历史缓存；对应“历史源码 + Codex”为 1/10。两组在 task2 第408步面对相同提示词和图像，却得到不同 guidance 决策，后续随机数消耗分叉，task3–9 首批粒子随之不同。当时的环境 episode seed 没有隔离全局策略随机流，不能把 1/10 对 0/10 直接归因于源码退化。旧描述缓存还包含 alphabet soup 身份并被用于其他任务。这些都是早期对照的混杂条件。

后来，历史回复回放在两套源码中均得到 3/10、127 条 Stage 事件与十段完整视频匹配，证明已检查的环境/执行路径能够重建历史轨迹；它不验证新在线回复。经过初始化校准、目标身份与 reward 合同、动作直通等改动后，Codex V13 仍是有效 0/10。这次 V13 已具备与 V17 相同的历史初始化协议和核心科学条件，因而是分析最后 0→3 的主要对照。

不能将后面发现的 evidence controller 缺陷倒推为最早旧接口 0/10 的唯一原因，也不能把此前所有基础修复都计作最后三个成功的已隔离贡献。[早期双源码报告](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z/docs/03_evidence/c0_codex_repro/2026-09-25-report.md)与[固定回复回放报告](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z/docs/03_evidence/c0_trace_replay/2026-09-28-current-source-report.md)分别保存这些证据。

版本演化与收益

| 版本 | 科学对照关系与改动 | 有效完整十任务结果 | 能支持的归因 |
| --- | --- | --- | --- |
| V13 | 新 Codex 在线条件，初始化已校准 | 0/10 | 主要失败对照 |
| V14 | V13 + 接受明确的部分遮挡抓持证据 | 2/10：task3、8 | 恢复 BBQ、pudding |
| V15 | V14 + 交接距离 10cm→6cm | 2/10：task3、8 | 没有增加成功，未纳入最终配置 |
| V16 | 回到 V14 的 10cm，单独增加携带证据融合 | 2/10：task3、8 | milk 行为改变但仍失败，无成功增量证据 |
| V17 | V16 + 空抓、再张爪后的失败接触复查 | 3/10：task3、8、9 | 保留两项成功，新增 orange |

V16 的科学父版本是 V14，不是保留 V15 改动继续累加。重新解析 YAML 后，V13→V14、V14→V16、V16→V17 每段除运行名/路径外都只多一个对应科学开关。V13 与 V17 的 Codex 接入实现、Stage 观察模板、C0 reward 合同、RDT steering 实现、LIBERO adapter 均具有相同冻结哈希；改动集中在控制逻辑与审计及两份新增机制文件。

相同条件包括物理 GPU2、tasks0–9、种子44/235/43/546/6/621/197/87/151/548、720步上限、RDT Object EMA、ED16粒子/10轮/temperature0.1/renoise3→1、absolute EEF RBF、QD archive关闭，以及不覆盖七维原生动作。模型始终为当前账号的 Codex CLI ChatGPT 登录、gpt-6-astra / low，未提高推理强度，未改用 Poe。

为什么修复部分遮挡能从0变为2

V13 将“可以确认抓持”与“目标必须完全清晰可见”绑定。模型已返回 grasp=held、support=unsupported，但只要 visibility=occluded，旧控制器就不建立 Stage2 和抓持保持。夹爪抓住物体时恰好经常遮挡上半部，这条全清晰要求过于严格。

V13 完整日志中有15次明确 held+occluded+unsupported 的控制观测仍停在 Stage1。这里是模型已经提供可用的抓持信息，控制器没有采纳，不能统一称为“Codex没看懂”。

| 任务 | 相同图像上的关键观察 | V13 的后续行为 | V14 的后续行为 | 第一次实际动作分叉 |
| --- | --- | --- | --- | --- |
| BBQ | 第80步，两版均报告 held / unsupported / occluded | 留在Stage1；第96步宽限结束后重新开ED；720步失败 | 第80步建立Stage2/抓持保持，第96步保持ED关闭；120步成功 | 第96步，前96个动作完全相同 |
| pudding | 第160步，两版均报告 held / unsupported / occluded | 留在Stage1；第176步重新开ED；720步失败 | 第160步建立Stage2/抓持保持；211步成功 | 第176步，前176个动作完全相同 |

上述80/160步实际传输图片哈希相同，四个分类字段相同，新的状态机作出不同决定。Stage2 的 C0 reward 是常数0，正确门控下不运行 ED；RDT 负责后续搬运/放置。旧 Stage1 的接近型 reward 在抓住之后被重新启用，会干扰这一动作阶段。新规则保留 RDT 原生动作，并在正确时间停止接近引导。

修改没有把 unknown 强行当成 held，也没有放宽任务成功条件。它只允许已过机器人矛盾过滤、明确 held 且 unsupported 的部分遮挡观测建立抓持；视觉完成仍要求 clear、inside_goal、not_held、supported 两次间隔确认。对应实现见[抓持可用性判断](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z/core/stage_evidence.py:56)。

这两项在 V16、V17 中全部120/211个动作及完整视频保持一致。所以本次最终3项成功中的两项，来自V14已恢复并随后保留的能力，不能算成V17新规则产生的三项收益。[BBQ证据](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z/artifacts/stage_closed_loop_20260929/runs/codex_partial_visibility_v14_historical_initialization_online_full10/bbq-success-review.json)和[pudding证据](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z/artifacts/stage_closed_loop_20260929/runs/codex_partial_visibility_v14_historical_initialization_online_full10/pudding-success-review.json)保存完整窗口。

为什么空抓复查让orange从失败变为成功

这不是同一个“遮挡held被忽略”问题。Orange 在第24步按 reward0.863、目标距离8.23cm进入接触宽限，ED关闭。第40步，目标明确在篮外地面、未被抓住，测得指宽1.92mm且实际CLOSE，支持空抓。第56步，测得指宽79.01mm、实际OPEN，新的视觉仍为 supported/outside，grasp因遮挡为unknown。

V16已经拿到这些信息，但接触宽限仍持续到第88步，压住了重新接近的ED。V17将同一宽限内相隔16–32步的“明确空闭负证据”和“新鲜篮外支撑、实测再张开”联合使用，确认这次接触已经失败，取消宽限，恢复Stage1 ED。

| 证据/动作 | V16失败轨迹 | V17成功轨迹 |
| --- | --- | --- |
| 第40与56步输入图 | 与V17逐字节相同 | 与V16逐字节相同 |
| 第40与56步分类观察 | 与V17相同 | 与V16相同 |
| 第0–55步原生动作 | 与V17相同 | 与V16相同 |
| 第56步 | 保持ED关闭 | 确认失败、恢复ED，首次改变动作 |
| 首次恢复ED | 第88步 | 第56步，开始时间提前32步 |
| 最终结果 | 720步失败 | 214步环境成功 |

新规则实际仅在56、64两个动作块执行ED，72步又交接，因此“提前32步”不能解释成连续多引导32步。之后136步开始有携带证据，视频中目标被抬起、送至篮口、下降并执行原生OPEN，最终成功。新复查没有重置同一阶段的reward reference，没有改写原始视觉结果或直接覆盖夹爪命令。[关键窗口证据](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z/artifacts/stage_closed_loop_20260929/runs/codex_failed_contact_v17_historical_initialization_online_full10/orange-first-recovery-live-review.json)及[完整orange复核](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z/artifacts/stage_closed_loop_20260929/runs/codex_failed_contact_v17_historical_initialization_online_full10/orange-completed-review.json)保留了原图哈希和逐步状态。

这里存在必须披露的限制：orange全程仍为Stage1，Stage2语义并未正确建立。这条轨迹是通过更合适的ED恢复时机、接触交接与原生RDT动作达到环境成功；它不证明在线阶段识别已完全正确。

为什么不能归因于API、reward变强或QD优化

V13有437次完整Codex调用、0次失败，V14为361/0，V15为360/0，V16为363/0，V17为325/0。接入在0/10时就可用；请求数减少部分来自成功任务提前结束，不能倒过来当作API改善造成性能提升的证明。内部HTTP尝试/重试不可观测，这些是完整CLI模型调用计数。

Reward方面，V13到V17采用同一C0合同，每任务都重新生成函数和阶段描述，再做有限数值检查；数学目标不是这一段的实验变量。历史reward/Stage缓存没有参与控制。关键原因是同样的reward在何时被启用、关闭或恢复，而不是换了一套更高分的目标函数。有限探针不能证明所有输入下都等价；但十任务首批关键点、粒子与已记录初始化张量和历史一致，实际归一化重建一致，支持已测试范围内的计算对齐。

更早自由生成reward曾改变候选排序，因此统一C0合同是重要基础工作；V13已做而仍0/10，不能把最后的0→3单独记给它。同理，初始化校准、身份标记、动作不覆盖都是本轮的共同前提。标记和物理证据借助跟踪关键点/仿真几何，须在正式算法setting中披露，不能把这次成功描述为只换了API的纯视觉旧C0。

RDT没有重新训练；ED搜索参数没有优化；QD archive一直为none。实际5,585个V17七维动作没有外部覆盖。这里获得的是在线Stage与ED/RDT配合的恢复，不是新的QD搜索收益。

其他改动没有已证实的成功贡献

V15收紧交接距离没有增加成功，最终已回到10cm。V16携带融合在milk第376步实际触发，但该任务仍失败，因此不能把融合写为3/10的必要原因。它作为冻结V17的一部分保留；移除后是否仍3/10没有独立消融，既不能宣称必须，也不能宣称完全无用。

V17复查还在cream cheese第64步、butter第360步触发，两者都失败，采样抬升反而低于V16。这证明“提前恢复ED”具有任务依赖，不能把orange的收益直接推广到所有抓取。

Ketchup的同原始reward因Stage历史导致reference不同，从而使ED决策不同；milk的抓持保持到期后在连续unknown下仍维持Stage2/EDoff，且目标标记覆盖了部分可见信息。这些限制没有消失，是后续可解释的优化方向。

“复现成功”应怎样表述

| 成功任务 | 历史C0 | 新Codex V17 |
| --- | --- | --- |
| task3 BBQ | 120步 | 120步 |
| task8 pudding | 314步 | 211步 |
| task9 orange | 285步 | 214步 |

成功任务集合与历史一致，都是3、8、9，不只是碰巧总数同为3。但是pudding、orange完成步数与轨迹不同，在线模型、输入协议和控制器也改变了。因此准确表述是“新Codex在线条件恢复历史C0在固定十任务上的成功数量与成功任务集合”，不是“严格复现一个月前整套在线系统”。

本轮三条成功视频的关键帧显示目标被搬到篮口并执行原生OPEN，没有在所看帧观察到明显翻篮；环境在首次成功即停止，之后稳定放置未被观察。没有改写环境计分或把视觉完成当成环境成功。

归因证据强度与研究使用边界

对于“修复改变了什么时候开关ED”，有源码、同初始动作前缀、相同图像和分类结果、状态变化及首次动作分叉相吻合的直接证据。对于“当前开发十任务从0变为3”，有独立冻结完整批次和全部失败保留。两者结合足以支持上述工程机制归因。

但每任务只有一个固定种子，各版本重新在线生成身份文字，关键图像相同不代表完整提示词相同；未来回复也会随新轨迹改变。没有完成所有组件的全组合消融，也没有独立重复/留出验证。不能据此声称两项修复对真实总体成功率分别贡献20、10个百分点，或宣布Codex与旧Poe总体能力等价。

下一轮应把V17作为完整冻结的在线控制对照，明确模型/强度、目标身份/标记、阶段机、reward合同及reference、历史初始化协议、原生动作和所有查询时序。先复核独立重复的稳定性；若做QD/ED比较，应固定这些Stage设置，每项变更单独完整评估，把控制器修复收益与QD收益分开计量。尚未实施的新方向是milk类过期保持恢复、输入标记避让与reference/Stage历史解耦；它们不能计入本轮已实现收益。

[最终V17完整报告](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z/docs/03_evidence/stage_consistency/2026-09-30-codex-v17-full10-report.md)保留运行审计、逐任务失败和视频；本归因报告仅追加分析，不修改其验收结果。

