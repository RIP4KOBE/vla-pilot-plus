**V13 完整在线结果：有效 0/10；Codex 接入正常，存在明确的 Stage 判定整合错误。**

本轮固定十任务、种子和已校准历史初始化，使用当前 Codex CLI 的 ChatGPT 登录，模型 `gpt-6-astra`、推理强度 `low`。每任务新生成 reward 函数、阶段描述与目标身份描述；执行中实时请求 Stage，reward 数值在本地计算。没有使用 Poe、旧 reward 函数或旧 Stage 回复来控制回合。历史 RNG fixtures 仅用于恢复初始化，不能将本轮称为原 Poe/Gemini 模型的严格复现。

十任务均执行完 720 步，成功数 0。总耗时 13521.04 秒（约3小时45分钟），真实 worker 退出码0，Stage/回合错误0；completion 的51项检查与 deep audit 的53项检查均通过。所有十个失败视频和配置保留。

在线调用总计 437 次 CLI 调用并完成同样数量的回复：10次reward生成、10次身份描述、417次Stage查询。没有格式重试；各回合用量记录完整。这些是CLI层计数，内部HTTP尝试/重试不可见，保持null，不能把它们写成HTTP 200统计。独立图片可用性复测用时21.11秒且通过五字段解析。API可用不等于每个视觉判断正确，也不等于任务成功。

十个新reward均通过64项C0有限数值探针；20次RNG恢复有效，十任务首批关键点、候选CSV及全部21个记录阶段张量与历史一致。7200个实际动作均保留RDT原始七维输出。reward门控、ED执行记录、阶段reference重置记录均通过审计。这排除了已检查范围内的初始化、reward数值、动作覆盖和调用失败问题；不构成整个研究系统所有状态的无回归证明。

已发现 15 次明确的 `occluded + held + unsupported` 控制观测被留在Stage1。原 `decide` 与 `update_visual_hold` 都要求visibility=clear，导致抓持信息未被采用；接触宽限期结束后恢复接近目标的ED，干扰本应由RDT执行的搬运/放置。

两个有逐动作前缀及图片证据的案例：BBQ与V11的前96个实际动作完全相同，在Codex第80/96步已报告抓持但被忽略后，第96步重新开启ED并首次分叉；布丁前176个实际动作完全相同，第160/176步同类回复被忽略，第176步重新开启ED并首次分叉。两张原图已人工查看，目标可见部分悬空在夹爪下方。它们支持这条控制规则存在缺陷；V11另有provider及reference设置差异，不能据此把全部失败都归因于单一原因。

| Task | 目标 | 环境成功 | Stage查询 | 被忽略的明确部分遮挡抓持步 |
| --- | --- | --- | --- | --- |
| 0 | alphabet soup | 0 | 40 | 616, 632, 648, 664, 680 |
| 1 | cream cheese | 0 | 43 | 128 |
| 2 | salad dressing | 0 | 40 | 712 |
| 3 | BBQ sauce | 0 | 44 | 80, 96, 112, 128 |
| 4 | ketchup | 0 | 38 | 无 |
| 5 | tomato sauce | 0 | 44 | 无 |
| 6 | butter | 0 | 40 | 无 |
| 7 | milk | 0 | 43 | 无 |
| 8 | chocolate pudding | 0 | 44 | 160, 176, 192, 208 |
| 9 | orange juice | 0 | 41 | 无 |

V14仅新增受控接受规则：经过原机器人矛盾过滤后，明确held、occluded且unsupported可建立Stage2与visual_hold。unknown不升级；完成依然需要clear、inside_goal、not_held、supported两次时间分隔确认。模型、推理强度、任务/种子、RNG fixtures、reward、原生动作及其他设置不变。解析后的配置对比只有该flag与输出路径/运行编号变化。137项草稿检查和6项队列保护检查通过；安装后377项检查通过。V14已在GPU2启动完整十任务，尚无其完整成功率。

验收保持用户原条件：单一冻结版本、完整在线十任务、环境成功率至少3/10，并完成审计、视频复核与报告。异常目标搬运另列，不改写环境计分，不跨版本拼接成功。V13未达到门槛，当前目标继续。

证据：[completion audit](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z/artifacts/stage_closed_loop_20260929/runs/codex_only_v13_historical_initialization_online_full10/audit.json), [deep audit](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z/artifacts/stage_closed_loop_20260929/runs/codex_only_v13_historical_initialization_online_full10/deep-audit.json), [全部十个失败视频](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z/artifacts/stage_closed_loop_20260929/runs/codex_only_v13_historical_initialization_online_full10/videos.html), [初始化对照](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z/artifacts/stage_closed_loop_20260929/runs/codex_only_v13_historical_initialization_online_full10/initialization-comparison.json), [布丁逐步证据](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z/artifacts/stage_closed_loop_20260929/runs/codex_only_v13_historical_initialization_online_full10/pudding-partial-visibility-evidence.json), [V14配置对照](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z/artifacts/stage_closed_loop_20260929/runs/codex_partial_visibility_v14_historical_initialization_online_full10/predecessor-config-comparison.json), [在线复测](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z/artifacts/stage_closed_loop_20260929/codex-availability-retest-20260930T094804Z/result.json)
