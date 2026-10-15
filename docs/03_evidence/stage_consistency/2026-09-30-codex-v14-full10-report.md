**V14 完整在线结果：有效 2/10（20%）。较同条件 V13 的 0/10 恢复了两项实际成功，尚未达到 ≥3/10 的验收门槛。**

本轮在物理 GPU2 执行，2026-09-30 10:35 至 12:56 UTC，耗时 8473.31 秒（2小时21分13秒）。十个固定任务和种子全部完成，真实 worker 退出码 0；completion 54 项和 deep audit 53 项检查全部通过。当前 Codex 账号经 CLI 的 ChatGPT 登录调用 `gpt-6-astra / low`；没有 Poe 请求或回退。保留 C0 的 RDT/ED 参数和已校准历史初始化，加入当前 Stage 控制修复，不能称作旧 Poe 模型原样复现。

每任务在线新生成 reward 函数、阶段描述和目标身份描述，执行期间在线评估 Stage；reward 数值由生成的函数在本地计算。总计 361 次 CLI 调用与完整回复：341 次 Stage 查询、10 次身份描述、10 次 reward 生成。失败调用 0、查询错误 0，用量记录完整。记录到 3,493,897 输入 tokens、38,171 输出 tokens。内部 HTTP 尝试与重试不可观测，保持 null。服务端输入 token 缓存不等于复用旧 Stage 回复或 reward 文件。

12:46 UTC 另做一次独立真实图片请求，19.757 秒返回有效五字段 Stage JSON，1 次调用、0 次失败；不参与 rollout 控制。这与整轮调用共同支持当前接入可用，没有证据要求修改账号 setting 或恢复 Poe 才能继续。它不保证视觉判断始终正确，也不保证任务达到成功率目标。

| Task | 目标 | 环境结果 | 执行动作 | Stage 查询 |
| --- | --- | --- | --- | --- |
| 0 | alphabet soup | 失败 | 720 | 39 |
| 1 | cream cheese | 失败 | 720 | 42 |
| 2 | salad dressing | 失败 | 720 | 39 |
| 3 | BBQ sauce | 成功 | 120 | 6 |
| 4 | ketchup | 失败 | 720 | 35 |
| 5 | tomato sauce | 失败 | 720 | 44 |
| 6 | butter | 失败 | 720 | 40 |
| 7 | milk | 失败 | 720 | 43 |
| 8 | chocolate pudding | 成功 | 211 | 12 |
| 9 | orange juice | 失败 | 720 | 41 |

十个 fresh reward 均通过 64 项 C0 有限数值检查；20 次历史 RNG 状态恢复有效。十任务首批关键点、评分关键点索引、粒子 CSV 和 21 个已记录阶段张量均与历史 C0 一致。6091 个执行动作与 RDT 原始七维输出完全一致，动作覆盖 0。引导开关与 ED 执行、reward 可用性及阶段 reference 重置一致性通过审计。这排除了已检查范围内的初始化、reward 数值和动作覆盖问题，不是对所有潜在状态的无回归证明。

V14 只增加对明确 `occluded + held + unsupported` 观测的接受：经过原机器人矛盾过滤后，可建立 Stage2 及抓持保持。unknown 不升级，完成判定仍要求清晰可见、篮内、未抓持、已有支撑的两次分隔确认。与 V13 的科学配置只差这一开关，安装后 377 项检查通过。

BBQ 在第80步获得明确的部分遮挡抓持证据，避免第96步错误恢复接近引导，120动作后环境成功；pudding 在160步建立 Stage2，避免176步错误恢复引导，211动作后成功。两例分别与此前 Poe V11 的对应成功轨迹全部 120/211 动作完全一致。关键视频帧已复核：目标由夹爪搬到篮口区域并执行原生 OPEN，没有观察到大幅翻篮或拖篮。记录在环境首次成功时终止，未观察之后的稳定支撑或完整释放；当时语义 Stage 尚为2，不能把环境成功说成视觉完成已确认。两条轨迹支持该控制整合修复有实际价值；在线输出非确定，V11 另有设置差异，不能将全部跨版本差异归因于单一因素。

剩余失败不是统一的 API 故障。Cream cheese、salad dressing、tomato sauce、butter、milk 和 orange juice 的720个动作分别与 V13 完全相同；新规则未改变这些轨迹。Alphabet soup 和 ketchup 虽产生分叉，仍未成功。Milk 的视觉 grasp unknown 与持续悬空测量支持进一步检查联合抓持判断，不能当成抓持真值。

Orange juice 的直接问题是交接过早：第24步 reward 0.8631944、距离8.228厘米时直接关闭 ED；第40步视觉 not_held 且夹爪空闭合，但抓取宽限期未终止；第56步仍关闭引导。历史 C0 的0.8只触发查询，第24步继续引导，第一抓失败后第56步恢复引导。这是控制语义差异，不能用相同阈值声称相同 setting。人工复核本轮24/40/56/719帧，最终盒子明确位于篮外，全部720动作与 V13 相同。视频 FAIL/SUCCESS 水印是整回合事后标签，不是逐帧真值或模型输入。

下一版 V15 只将 reward 触发交接允许的最大距离从0.10m收紧到已有0.06m，保留0.8阈值、关闭纯距离触发及 V14 其他设置。四个已观察输入的 CPU 条件检查显示：orange24 不再立即交接，BBQ32 与 pudding24/112 仍通过；这不预言未来轨迹或成功率。规则统一用于所有物体，不修改完成判据、原生动作、reward、模型或推理强度。使用新编号冻结完整十任务；若仍不足3/10，再分别验证失败宽限期取消或不确定抓持下的持续搬运判断，不将它们混入这一轮。

本轮资源记账已完成：本研究累计341次已派发完成尝试、37.185696 GPU小时上界，保护的100次/24小时保留。用户已豁免预算停止条件，后续只更新本研究记账，不占用或停止其他研究进程。未开始 QD 优化，goal 继续 active，不跨版本拼接成功数。

证据位于本 worktree 的 `artifacts/stage_closed_loop_20260929/runs/codex_partial_visibility_v14_historical_initialization_online_full10/`：`audit.json`、`deep-audit.json`、`full10-evidence-summary.json`、`initialization-comparison.json`、`bbq-success-review.json`、`pudding-success-review.json`、`orange-complete-failure-review.json`。所有视频在 [视频索引](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z/artifacts/stage_closed_loop_20260929/runs/codex_partial_visibility_v14_historical_initialization_online_full10/videos.html)。独立接口实测见 [原始结果](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z/artifacts/stage_closed_loop_20260929/codex-availability-retest-20260930T124636Z/result.json)。
