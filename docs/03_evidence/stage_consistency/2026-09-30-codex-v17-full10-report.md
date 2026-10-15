**最终结果：V17 在单次冻结、完整的 LIBERO object-swap 十任务在线评测中取得有效 3/10（30%），成功任务为 BBQ sauce、chocolate pudding、orange juice。当前 Codex 账号接入可用：325 次实际模型调用全部完成，0 次调用失败。基线恢复诊断的本轮验收条件已满足。**

实验于 2026-09-30 在原 worktree、物理 GPU2 完整执行，19:37:28 UTC 正常结束，退出码 0，运行 4806.82 秒（1小时20分7秒）。十任务均完成，七个失败原样保留，没有补跑后挑选成功，也没有拼接不同版本的成功。完成审计 62 项、深度审计 59 项全部通过；安装前后分别有 33 项草稿检查和 456 项安装后 CPU 回归检查。性能结论来自完整在线评测，CPU 检查仅支持实现正确性。

这是**达到历史 C0 成功数量的新 Codex 在线基线**。它不是旧 Poe/Gemini 模型、提示词和控制器的严格原样复现，也不证明所有 Stage 语义错误已经解决。本轮是开发中反复使用的固定十任务、固定种子，不能当作独立留出集上的 30% 泛化成功率。当前 QD archive 仍关闭，尚非最终 ≥5/10 的 RDT+QD+ED 算法版本。

**Codex 接入与在线性**

使用当前账号的官方 Codex CLI、ChatGPT 托管登录，模型 `gpt-6-astra`，推理强度 `low`。这是仓库通过 CLI 使用当前账号的接入路径，并非新增一把 OpenAI 平台 API key。没有读取或导出登录凭据，没有使用 Poe，也没有在失败后转向其他提供方。子调用关闭工具、插件、apps 与 MCP，保留原 HOME 以使用正常托管登录；provider 审计验证了实际记录的模型、登录方式和执行策略。

325 次调用包括 305 次在线 Stage 评估、10 次新目标身份描述生成和 10 次新 reward/阶段描述生成。每任务使用新生成函数，数值 reward 随控制过程在本地计算；并非每一个 reward 数值都向模型发请求。没有复用历史 reward 函数或 Stage 回复，没有 Stage 查询错误或格式验证重试。记录输入 3,145,459 tokens、输出 35,666 tokens，模型调用累计耗时 3611.95 秒。内部 HTTP 状态码和传输重试次数不可观测，不能把完整回复数量写成同样数量的 HTTP 200 或“每次网络传输都一次成功”。

因此，本轮失败无法归因为账号不可用或所有在线请求失败。也没有证据表明必须恢复 Poe 才能达到三项环境成功。对遮挡的保守判断、身份文本变化与控制状态机如何消费模型结果，仍会影响闭环轨迹；模型接入可用不等于视觉判断在每个时刻都正确。

**冻结设置**

| 项目 | V17 实际设置 |
| --- | --- |
| 运行位置 | 原实验 worktree，物理 GPU2；UUID `GPU-a5d6a5f8-b6df-7f3a-c3dc-19734c41ec0e` |
| 环境 | `libero_object_swap`，tasks 0–9，每任务 1 回合，环境上限 720 动作；使用 init states、等待 5 步 |
| 任务种子 | 按 task 0–9：44、235、43、546、6、621、197、87、151、548 |
| 策略 | RDT-1B-LIBERO-Object EMA，执行 chunk 8，20 Hz；推理步数不另作 CLI 覆盖 |
| ED | 16 particles、10 iterations、16 elites、use_cem=false、temperature=0.1、renoise 3→1 |
| 初始多样性 | rbf_diverse_denoise，absolute_eef，scale=20，start_ratio=0.8 |
| rollout 多样性 | rbf_diverse，absolute_eef，scale=20，start_ratio=0.6 |
| QD | archive_mode=none；metrics_observer=true，只记录观察指标 |
| reward | 每任务重新生成并验证 c0_xyz_v1 数值合同；Stage1 为轨迹加权负 MSE，后 30% 权重更高；Stage2 常数 0，因此该阶段 ED 关闭 |
| reward reference | 仅语义阶段切换时重建，同阶段单纯开关 guidance 保留 reference |
| Stage 查询 | 最小间隔 16 步，常规复查 32 步，不确定时 16 步，每任务上限 50 次 |
| Stage 完成 | 相隔至少 16 步的两次明确可见、目标受支撑、未被抓持、已在篮内证据；遮挡 unknown 不宣告完成 |
| 目标识别 | 当前画面目标标记 + 每任务新身份描述；标记利用跟踪关键点/相机几何，这是需要披露的额外感知条件 |
| 搬运处理 | 保留部分遮挡下明确 held 规则、物理携带续期和 V16 融合携带规则 |
| 接触交接 | 纯 proximity 交接功能关闭；reward≥0.8 且目标距离≤0.10 m，最少接近 16 步，接触宽限 64 步 |
| 原生动作 | grasp_action_guard_enabled=false；5,585 个七维动作均未被外部覆盖 |
| 新规则 | stage_failed_contact_recheck_enabled=true |
| 初始化 | historical_fixture_v1，仅恢复规定的 RNG 状态；不回放历史 Stage、reward、动作或环境回复 |
| Codex | gpt-6-astra / low，官方 CLI ChatGPT 登录；调用超时 180 秒、配置重试 1，完整回复校验策略 completed_transport_cycles_v6 |

完整设置以本轮 `resolved-config.yaml`、`manifest.json` 和 `source/` 快照为准。部分继承配置名称仍含 gemini/poe 或旧 method_label；实际启用 provider、grounding 开关和调用记录才是接入依据。不能只启动仓库默认配置，就声称运行了本轮 V17。

十任务第一批关键点、评分索引、粒子 CSV 及记录的初始化张量均与历史记录一致；20 次规定的 RNG 恢复顺序和值通过审计。这验证了初始化对齐，不代表新在线回复或整条轨迹应与历史相同。reward reference 数值逐样本重建一致，实际 ED 执行与开关、reward 能力匹配，原生动作未被覆盖。

**本轮唯一新增机制及实际作用**

科学父版本 V16 为完整有效 2/10；V17 只新增失败接触复查开关。配置对比的其余差异仅为作业名、输出目录和捕获路径，未混入交接距离或 QD 改动。启动后科学代码、配置、任务和种子保持冻结。

新规则先要求同一 Stage1 接触宽限内的新视觉明确报告 clear/not_held/supported/outside，同时测得夹爪空闭（宽度<5 mm）、上一实际命令 CLOSE。16–32 步后，另一条新视觉仍为 supported/outside、抓持 unknown 或 not_held，实测指宽>75 mm 且实际命令 OPEN，才取消失效宽限、恢复 ED。目标需明确在扩展后的篮子 XY 范围外、没有当前携带证据；held、悬空、入篮、阶段变化或证据过期会否定恢复链。

该规则没有把原始 unknown 改写为 held/not_held，没有直接宣告成功，没有覆盖动作，也没有重置同一阶段的 reward reference。实际确认了三次：cream cheese 第 64 步、butter 第 360 步、orange 第 56 步。其中只有 orange 新增成功，不能把所有局部触发都算成有效性能增益。

| Task | 目标 | 环境结果 | 动作数 | Stage 调用 | ED 块数 | 与 V16 首次动作分叉 |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | alphabet soup | 失败 | 720 | 38 | 26 | 全部相同 |
| 1 | cream cheese | 失败 | 720 | 38 | 29 | 64 |
| 2 | salad dressing | 失败 | 720 | 39 | 25 | 全部相同 |
| 3 | BBQ sauce | **成功** | 120 | 6 | 4 | 全部相同 |
| 4 | ketchup | 失败 | 720 | 36 | 18 | 488 |
| 5 | tomato sauce | 失败 | 720 | 44 | 27 | 全部相同 |
| 6 | butter | 失败 | 720 | 36 | 31 | 360 |
| 7 | milk | 失败 | 720 | 43 | 18 | 全部相同 |
| 8 | chocolate pudding | **成功** | 211 | 12 | 6 | 全部相同 |
| 9 | orange juice | **成功** | 214 | 13 | 7 | 56 |

**为什么 orange 从失败变为成功**

40 步明确空抓负证据、56 步新复查满足张开与篮外支撑条件；这两张模型输入图片与 V16 字节相同，离散观察结论相同。每任务身份文字是重新生成的，因此不是完全相同提示词的模型消融。

V17 在 56 步取消宽限并开启 ED，而 V16 实际到 88 步才恢复。0–55 步动作完全相同，第一次动作分叉恰在 56 步；同阶段 reward reference 未重置，七维动作未覆盖。这是新规则确实改变控制行为的直接证据。这里“提前 32 步”指恢复开始时间：新规则只在 56、64 两个块执行 ED，72 步又交接，不能写成连续多执行了 32 步 ED。

136 步开始有物理携带证据；128 帧可见橙汁盒在篮旁抬起，200 帧在篮口上方，213 帧降入篮口、原生 OPEN 正在执行，214 动作后环境判成功。已复核实际输入 40/56 与视频 56/128/200/213；所看帧篮子保持直立，采样篮子 XY 中点最大移动 6.46 cm，没有观察到明显翻篮。视频完整保留。

限制同样明确：orange 全程仍为 Stage1，控制器没有确认 Stage2 或视觉完成。它通过接触交接、原生策略和局部恢复完成了环境任务，不代表 Stage 语义已完全恢复。环境在第一次成功后停止，之后的完全释放、持续稳定放置未被观测；最后 208 步的粗几何采样先于 214 步终止，不能据采样中心未入篮单独推翻终止成功。单个固定种子新增成功支持候选有效，但不足以证明新规则对所有任务普遍有益。

**保留的成功与七项失败**

BBQ、pudding 的全部原生动作与完整编码视频均和 V16 相同。BBQ 在 80 步使用已有的部分遮挡明确抓持规则，101 步原生 OPEN，120 步成功；pudding 在 160 步建立同类 Stage2，203 步 OPEN，211 步成功。新复查与融合没有参与这两项成功，不能算作 V17 新规则增益。已复核各自关键帧，未见明显翻篮；采样篮子 XY 最大移动分别 5.23 cm、0.65 cm。成功后的稳定性仍未知。

Pudding 也提供反例：48 步空抓负证据并不足够；64 步 support=unknown、指宽约 74.4 mm，80 步已是 CLOSE，故没有错误确认新恢复。本轮保住了这条已有成功，但不能据此承诺以后所有在线回复均不会误触发。

Cream cheese 的 48→64 复查实际比 V16 的 80 步恢复提前 16 步；butter 的 344→360 实际比 V16 的 368 步提前 8 步。两者对应输入图片相同、首次动作分叉与恢复同步，却最终仍失败。最大采样目标抬升分别从父版本 16.16 cm / 15.61 cm 降到本轮 0.75 mm / 1.25 mm，没有 Stage2 或携带。终帧目标均在篮外地面、与手分离。Butter 的篮子在新规则触发前已明显倾斜，不能归因于 360 步的新干预；本轮两任务篮子最大 XY 移动分别 10.36 cm / 15.97 cm。提前 ED 并不自动改善接触质量。

Ketchup 的新复查未确认：352 步有明确空抓负证据，但 368/384 步指宽仅 4.83/3.89 cm，不满足 7.5 cm 条件。原始输入显示目标横卧篮外，368 步另一个绿色瓶子悬于手下，接触部分遮挡，支持干扰物被抓取的解释。这一段不能归为 Codex 把目标误判为 held。

Ketchup 第 488 步的首次动作分叉另有明确原因：两版上一 ED 原始 reward 均为 -0.001007080078125、目标距离均为 2.996 cm；V16 经 424 步 Stage2、472 步回 Stage1，reference 变为 -0.00119781494140625，归一化 0.1592356688，继续 ED。V17 此前保持 Stage1，reference 仍为 -0.08056640625，归一化 0.9875，触发交接关闭 ED。精确算术复核通过；是在线 Stage 历史经 reference 影响控制的脆弱性，不是此次新复查的增益，也不是 API 传输错误。560 步进入 Stage2、562 步 OPEN，最终目标仍在篮外，720 步失败。

Milk 与 V16 的完整动作和视频相同：376 步已有携带融合建立保持，388 步原生 OPEN，416 步几何位置到篮外。动作记录中的抓持保持在 464 步已到期，第一条对应 Stage 查询在 472 步记录为 false；472–712 的 31 个块却仍 Stage2/EDoff。夹爪充分张开、目标篮外、无携带，手距目标最多 9.24 cm，未达到现有 open-far 恢复的 >10 cm；持续遮挡 unknown 又保留旧语义阶段。432 步之后目标最大位移仅 7.35 mm。终帧红色盒体上部露在篮后沿，精确支撑被遮挡，720 步失败；篮子最大 XY 位移 11.51 cm。这是尚未修复的释放后失败恢复缺口。

Milk 另发现输入标记遮挡：已逐像素核对 472/488 的原始无标记图片和真实带标记输入，固定 TARGET 文字覆盖部分可见盒体文字、圆圈覆盖邻近篮沿。每帧共有 968 像素被标记改变；人工选定矩形包含背景，不能把矩形变化比例当成目标遮挡比例。这个可验证的输入缺陷应单独改进，但本轮没有“移开标记后模型是否改善”的反事实 API 对照，不能宣称它就是失败的唯一原因。

Soup、salad、tomato 的全部动作和完整视频均与 V16 相同，新复查未参与。Soup 终帧罐在篮外、手分离；salad 696 步才进入 Stage2，终帧仍在篮左侧举瓶；tomato 始终 Stage1，360 步 reward=0.90669、目标距离 9.45 cm 触发交接，但终帧目标仍在篮外物体群。三任务采样篮子 XY 最大位移分别 19.43 cm、11.41 cm、约 0，异常篮子移动已保留记录。

全部十段视频的关键帧和机制窗口已复核，不声称观看了每一帧。视频 SUCCESS/FAIL 字样是事后回合标签，不是逐帧真值，也不是发送给模型的评估答案。每任务 review 保存输入、动作、视频 SHA 与具体限制。

**可以开始什么，仍需解决什么**

本轮已达到事先明确的“一个有效冻结十任务 ≥3 环境成功 + 完整在线证据、失败保留和报告”目标，可以将 V17 冻结为下一轮比较的 Codex 在线基线。没有必要为了达到本轮三项成功强行恢复 Poe；也无需继续用局部成功替代完整结果。当前结论不支持“所有在线 Stage 问题完全解决”或“已经达到最终五项成功”。

下一轮最值得做的是：

1. 单独修复 milk 类“保持已过期、目标在篮外、无携带、持续不确定，却长期维持 Stage2/EDoff”的恢复缺口。先用现存成功轨迹做误恢复反例检查，再用新在线完整十任务验证；现有只读命中只能说明代码路径可触发，不保证改后成功。
2. 单独修复目标标记遮挡，用同一原始帧对照原标记、避让标记或无标记输入，量化对 grasp/support 判断的影响；每组保持模型与观察信息边界一致。当前只证明像素覆盖，尚未证明性能收益。
3. 对 reward reference 与 Stage 历史的耦合做单变量实验。Ketchup 提供了相同原始 reward、不同 reference、相反 ED 决策的精确样本；目标应是可解释的交接一致性，同时检查 orange、BBQ、pudding 是否退化。
4. 再以冻结 V17 控制器/提供方作为比较条件优化 QD/ED；每个候选完整计入失败，并为最终 ≥5/10 结论保留独立重复种子或留出验证。当前固定十任务被多次用于选规则，不能承担独立泛化验收。

本次没有启动上述新实验。GPU worker、supervisor 和本轮队列均已退出。累计记账为本研究 371 次已完成尝试、43.37809 GPU 小时上界，本轮计 10 次、1.33523 小时；保留的验证/正式 100 次与 24 小时未动用，预算停止按用户既有指令豁免。没有修改其他研究状态或终止他人 GPU 进程。

证据入口：[完整十任务视频](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z/artifacts/stage_closed_loop_20260929/runs/codex_failed_contact_v17_historical_initialization_online_full10/videos.html)、[本轮结果汇总](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z/artifacts/stage_closed_loop_20260929/runs/codex_failed_contact_v17_historical_initialization_online_full10/full10-evidence-summary.json)、[Codex 实际调用审计](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z/artifacts/stage_closed_loop_20260929/runs/codex_failed_contact_v17_historical_initialization_online_full10/codex-full10-availability-proof.json)、[冻结配置](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z/artifacts/stage_closed_loop_20260929/runs/codex_failed_contact_v17_historical_initialization_online_full10/resolved-config.yaml)。同目录保存两层审计、初始化/归一化诊断、十任务 review、新规则与父版本对比，以及全部冻结源码、原始回复和轨迹。

[新增 orange 成功视频](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z/artifacts/stage_closed_loop_20260929/runs/codex_failed_contact_v17_historical_initialization_online_full10/output/episode_10/episode_10_success_agentview.mp4) · [BBQ 成功视频](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z/artifacts/stage_closed_loop_20260929/runs/codex_failed_contact_v17_historical_initialization_online_full10/output/episode_4/episode_4_success_agentview.mp4) · [pudding 成功视频](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z/artifacts/stage_closed_loop_20260929/runs/codex_failed_contact_v17_historical_initialization_online_full10/output/episode_9/episode_9_success_agentview.mp4)
