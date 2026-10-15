当前完整结果：V13有效0/10，417次在线Stage查询，完整437次CLI调用均完成；初始化、数值reward、原生动作和两层审计通过。完整报告：docs/03_evidence/stage_consistency/2026-09-30-codex-v13-full10-report.md。V14已在GPU2开始，supervisor2715952、worker2716202、接续队列2595833；377项安装后检查通过，新flag已在实际Stage事件中记录。仍未达到≥3/10，保持目标active，切勿重跑覆盖V13源代码审计或在V14运行时改冻结源码。

# 当前：GPU2 仅 Codex 在线十任务已启动 — 2026-09-30T06:50:24.185418+00:00

用户要求禁止 Poe；该限制已落实到启动器、worker环境与主程序。所有 Stage、每回合身份描述、fresh reward/阶段描述均通过当前 Codex CLI 的 ChatGPT 登录调用 **gpt-6-astra / low**。CLI显式强制ChatGPT登录，禁用工具/插件/其他模型接入，不加载.env，不读取Poe凭据，任何失败均无Poe回退。

当前冻结批次 `codex_only_v13_historical_initialization_online_full10`，supervisor 2217380，worker 2217645，GPU2单worker；原worktree管理。进度：artifacts/stage_closed_loop_20260929/runs/codex_only_v13_historical_initialization_online_full10/output/status.json；监督日志：artifacts/stage_closed_loop_20260929/codex-only-v13-supervisor.log。不要重复启动或修改运行中的冻结代码。预计2–4小时，按真实在线延迟修订；当前尚无完整成功率。

260项接入/旧接口/启动回归及65项控制器回归通过；真实Codex预检的reward通过64项C0数值检查，identity和五字段Stage均成功。预检不是GPU成功率。Codex输出程序每任务新生成，reward数值在本地执行计算。保留V12其余控制设置和已校准历史初始化RNG，禁用旧reward/Stage回复缓存、无任务失败重试。新版本独立统计，不能称为原Poe模型严格复现。

Poe V12因用户要求中止：2个失败回合完成、第3个step528中断，非完整0/10；所有旧审计保留。V11完整有效环境分数3/10，视频复核2次正常目标搬运和1次异常篮子运动成功。尚未达到新Codex setting性能验收，未开始QD优化。

授权：artifacts/stage_closed_loop_20260929/codex-only-provider-authorization-20260930.json；新冻结方案：artifacts/stage_closed_loop_20260929/runs/codex_only_v13_historical_initialization_online_full10/proposal.json。完成后保存completion和deep审计、初始张量比较、视频复核与本研究记账，继续依据结果闭环，不拼接版本成功数。

以下旧状态仅保留历史：

# 当前：Poe 已停止，切换 Codex 账号在线调用 — 2026-09-30 06:31 UTC

用户最新明确要求只使用当前 Codex 账号，不再使用 Poe。原 V12 worker 和 supervisor 已退出；完成2个失败回合，第3个在step528因用户切换要求中止，不能算作完整0/10。历史审计原样保留。当前处于 Codex 接入实现/验证阶段，无本研究 GPU worker。

Stage、每回合身份描述、新 reward/阶段描述全部切换官方 Codex CLI 的现有 ChatGPT 登录；禁止 Poe 回退，不读取/导出账号令牌。GPU2、原worktree、单worker和其他研究资源隔离继续有效。后续 Codex 批次与 Poe 结果分开记录。V11完整有效环境分数3/10，视频显示2次正常目标搬运及1次异常篮子运动成功；尚不能声称新 Codex setting已恢复性能。

授权记录：artifacts/stage_closed_loop_20260929/codex-only-provider-authorization-20260930.json。下一步：五字段Stage与fresh reward接入/CPU检查/真实Codex预检，然后冻结新十任务。下面旧ACTIVE记录仅是历史。

# 在线 Stage 与 C0 性能恢复报告（进行中）

更新时间：2026-09-30 06:07 UTC。**V11已有效3/10，达到环境计分门槛；但其中1例伴随篮子翻转，正常目标搬运仅2项。V12正在GPU2验证归一化参考修复，未宣称预期行为全面恢复，不开始QD/ED优化。**

## 当前结果与验收口径

已排除“旧环境完全坏了”这一解释：当前代码在历史回复回放下再次得到3/10，127条Stage事件、十个视频以及十个首批粒子文件均与历史完全一致。但新的Poe Gemini-3-Flash在线条件尚未恢复该成功数，最新完整V11有效3/10，但正常目标搬运仅2项，另1项伴随篮子翻转。

只以同一冻结版本、原十任务与环境种子的完整在线回合计分。失败不按语义重试，不从不同版本拼接成功。无效批次、开发子集和历史回放均不作为在线恢复验收。环境成功谓词是最终计分；视频另外检查是否真的搬运目标入篮。

| 完整批次 | reward / 随机流 | 有效结果 | 说明 |
| --- | --- | --- | --- |
| 历史 C0 | 历史函数 / continuous | 3/10 | 旧 Gemini-2.5-Flash 在线历史记录，成功 task3/8/9 |
| proprio_v4_fresh_full10_r2 | 新模型自由生成 / per_seed_v1 | 1/10 | task6；视频主要搬动篮子，不能夸大成干净目标搬运 |
| payload_release_v5_c0_contract_online_full10 | 新生成但固定C0数值 / continuous | 2/10 | task4/6，视频均为目标搬运入篮 |
| recovery_priority_v6_c0_contract_online_full10 | 同上 | 无效，名义1/10 | task6因完整JSON被代码块包裹而解析中断；不能计作有效性能 |
| physical_carry_v7_c0_contract_online_full10 | 同上 | 1/10 | task5干净放置；338次Stage请求有效 |
| current_target_marker_v8_c0_contract_online_full10 | 同上，当前目标圈 | 0/10 | 十任务完整、363次Stage请求有效；有抓起目标但放置失败 |
| native_gripper_v9_c0_contract_online_full10 | 同V8，夹爪执行不覆盖 | 记录1/10，严格审计未通过 | 十回合完整；会话中断丢失原worker退出码，其余检查通过 |
| native_gripper_v10_historical_initialization_online_full10 | 同V9，逐任务历史RNG初始化 | **2/10** | task2/8；两层审计有效，十任务首批张量均与历史一致 |
| reward_progress_handoff_v11_historical_initialization_online_full10 | 同V10，仅取消距离单独触发交接 | **3/10** | task1/3/8；两层审计通过，task1伴随异常篮子翻转 |
| stage_reference_v12_historical_initialization_online_full10 | 同V11，仅恢复阶段reference跨引导切换保持 | **运行中** | 每任务仍全新生成reward/描述/identity/Stage |

开发子集、启动失败和定向回归的完整记录见[所有批次索引](../../../artifacts/stage_closed_loop_20260929/all-runs-index.md)。原始过程笔记保留在[工作记录](2026-09-29-closed-loop-recovery-working-notes-through-v8.md)。

## 目前可以下结论的原因

### 1. API接入成功与控制成功是两件事

V8十任务无执行、鉴权或解析错误，363次逻辑Stage查询、374次HTTP尝试（包括身份识别及1次SDK重试），两层审计通过。接口可用并不保证模型正确理解当前对象，也不保证控制器正确执行其后续动作。因此当前0/10不能解释成“API根本没有接通”。

早期新运行器确实发生过reward客户端未注入Poe密钥而Stage客户端有密钥的401错误。该次只有准备失败，修复后两条客户端共用同一私有运行时凭据。它解释该无效启动批次，不能解释后续有效0/10。

### 2. 旧轨迹能够重现，当前基础环境未表现出同轨迹回归

`historical_initialization_calibration_v1` 在当前源码的旧控制路径下有效重现3/10；127条Stage事件、十个视频SHA、十个首批粒子SHA全部一致。20个Python/NumPy/Torch CPU/CUDA随机状态已记录，记录操作没有推进随机流。

这是给定历史回复时的轨迹等价证据，不能代替新在线模型评测。校准结束后的审计曾因字符串路径类型报错，在不改冻结源码或轨迹的独立审计中规范化路径后通过；不是机器人回合失败。见[校准审计](../../../artifacts/stage_closed_loop_20260929/runs/historical_initialization_calibration_v1/audit.json)。

### 3. 自由生成reward不等于历史C0目标函数

8/10个自由生成任务的reward在测试轨迹上改变了排序；同初始粒子对照也出现不同动作选择。仅固定旧reward的开发子集仍0/3，所以reward差异不是全部原因。

后续完整批次每任务仍请求新模型生成函数，但提示词限定历史C0数学契约：Stage1保持原norm→square顺序、float32时间权重和负加权平均；Stage2为常数0。每个函数检查float32/bfloat16等64个有限探针，实际首任务ED全10轮张量也曾逐值对齐历史。有限探针不是数学证明，但已控制主要数值漂移。

历史C0的Stage2本来就没有执行ED；让常数零reward关闭ED，并未删除历史成功时实际存在的Stage2优化。见`historical-c0-stage2-gate-audit.json`与`formal-initial-particle-vs-historical-task0.json`。

### 4. 当前目标识别存在真实错误，简单改身份文字不足以修复

V7 pudding已被抬起时，模型仍描述它位于橙汁盒后方地面。两张固定当前图、保留/删除初始位置描述、各两次请求，共8次均误判not_held。

用已有跟踪关键点在同一当前图画TARGET圈后，遮挡较强的160步两次均改为occluded/unknown，192步两次均改为held/above_goal。该对照证明当前身份定位信息能改变错误判断，不支持“模型无论如何都无法判断抓持”的结论。

V8采用这一输入修复，仍完整0/10。因此离线视觉改善不能当作性能恢复。圈只说明目标身份位置，不说明抓持、支撑、完成或reward。它沿用现有仿真关键点跟踪；不能宣传成不依赖仿真状态辅助的真实机器人感知。

### 5. 后加的夹爪保护可能破坏原生放置，是当前优先排查项

V8有六个任务曾抬起目标，但累计1414个夹爪动作被覆盖。task1/3/8分别306/371/306次强制CLOSE。pudding视频中，93步策略OPEN被改成CLOSE，随后目标被持续带离篮子。见[视频接触图](../../../artifacts/stage_closed_loop_20260929/v8-pudding-failure-contact-sheet.jpg)和[覆盖统计](../../../artifacts/stage_closed_loop_20260929/v8-gripper-intervention-summary.json)。

局部回归已有更强证据：早期固定失败样例task8，放置许可修复前后前97步动作完全相同；97步放行原策略OPEN后116步成功，旧版720步失败。不过这只证明那个样例，不能证明所有保护规则都有效，更不能解释最早尚未加保护时的0/10。

V9只关闭夹爪执行覆盖。6617个执行动作均与策略输出一致，记录1/10（pudding，137步入篮），没有达到恢复门槛。保护层内部状态计算仍保留。因监督中断，退出码未能取得，严格审计worker_exit失败；不伪造0或修改旧结果。当前V10沿用此控制条件，仅改变初始化协议。

### 6. 相同环境seed不保证后序任务使用相同策略采样

历史continuous随机流跨任务延续。在线Stage改变ED调用数量和回合长度后，会改变后序任务的初始粒子，有时也改变检测关键点。因此不能把后序任务的所有差异都归因于该任务的一次Stage回复。

V8/V9保持原continuous协议。V10已启用严格校准的历史逐任务随机状态工具，作为独立的historical_fixture_v1协议；所有十个任务按原顺序使用校准状态，不挑选seed。每任务准备/策略开始各恢复一次，完成后必须核对20次restore和实际首批张量。该协议不回放任何历史Stage、reward、动作或环境状态。

V8/V9首任务的前136个执行动作相同，136步的完整请求文字、图片字节和身份描述也相同，但模型分别输出occluded/unknown与clear/not_held/outside_goal，导致ED开关分叉。两者温度均为0。这是在线输出不完全确定的直接证据；不能把两批分数差异全归因于夹爪开关。证据见[V9输入相等核对](../../../artifacts/stage_closed_loop_20260929/runs/native_gripper_v9_c0_contract_online_full10/v8-task0-input-equality.json)。

## 已实施的控制一致性修复

- LLM只返回五项视觉事实；关闭引导后仍定期复查，不把一次完成判断锁死。阶段完成需要间隔确认，且可撤销，只有环境成功才结束回合。
- 有效引导同时受主开关、阶段请求、非完成状态及reward可用性限制；日志状态与实际ED执行块逐一核对。
- 明确失败恢复优先于接触宽限窗口，防止恢复请求被再次关闭。原始视觉回复与经机器人测量校正的控制观察分别保存。
- 严格JSON验证只增加对单个完整外层代码块的无损解包；不接受截断JSON，不补造字段。语法重试使用同一请求并接受第一份有效回复，包括失败和unknown，不挑选有利语义。
- 物理携带信息可维持已有视觉抓持判断、降低与测量矛盾的视觉否定；不会单凭该信息宣布任务成功。保护控制仍可能有副作用，V9/V10已关闭其执行覆盖。

## V10冻结设置与运行方式

| 项目 | 设置 |
| --- | --- |
| 执行位置 | 原`.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z`，未新建worktree |
| GPU | 物理GPU2；单个本研究worker；48GiB分配器上限，保留其他服务 |
| Policy | RDT-1B-LIBERO-Object EMA checkpoint；5步去噪；动作块执行8步 |
| 任务 | libero_object_swap，task0–9，720步上限，原初始化设置 |
| 环境seed | 44,235,43,546,6,621,197,87,151,548 |
| 策略随机流 | historical_fixture_v1；每任务两次恢复校准RNG，固定原十任务全部状态；与continuous单列 |
| ED | 16粒子、10轮、16 elites、use_cem=false、temperature=0.1、renoise 3→1 |
| 多样性 | initial rbf_diverse_denoise / absolute_eef / scale20 / start0.8；rollout rbf_diverse / scale20 / start0.6 |
| QD | archive关闭；本阶段不优化QD |
| API | Poe Gemini-3-Flash；Stage temperature0/max_tokens8192；不发送显式推理强度参数 |
| reward | 每任务新生成并校验C0数学契约；无历史reward缓存 |
| Stage | 新身份描述、当前目标标记图、在线视觉事实；无历史回复回放 |
| 夹爪 | grasp_action_guard_enabled=false；其他控制设置保持V8 |

完整可重建参数及冻结源码见[V10 manifest](../../../artifacts/stage_closed_loop_20260929/runs/native_gripper_v10_historical_initialization_online_full10/manifest.json)与[配置](../../../artifacts/stage_closed_loop_20260929/runs/native_gripper_v10_historical_initialization_online_full10/resolved-config.yaml)。运行器拒绝覆盖已有输出。

V11已完整有效3/10，但正常目标搬运仅2项；V12仍在验证，尚不开始QD/ED优化。新Poe模型与旧Gemini-2.5-Flash不同；即使恢复3/10，也应称为新在线条件下恢复基线性能，而不是旧模型服务的严格复现。十个固定任务的单次分数也不是稳定总体成功率的统计保证。

## V10完整结果与V11单项验证

V10于04:38:23 UTC结束，完整有效2/10（salad dressing 698步、pudding 211步），341次Stage查询、355次HTTP尝试、4次SDK重试；零查询/回合错误和零夹爪覆盖。20次RNG恢复与校准一致，十任务首批关键点/粒子CSV/21阶段张量均逐值对齐历史。视频确认目标抓起运输入篮，pudding在环境判定成功时即结束，不能据此保证之后长期静止。

BBQ前三个ED块step0/8/16的候选指纹、奖励与选择完全相同；首个交接差异在step24，当前距离0.055855m且reward0.7972222，6cm旁路提前关ED，而旧C0此时仍引导。这定位了一个可修复的本地控制差异，但并不证明它是全部失败原因。V11仅取消距离单独触发，继续要求reward>=.8且距离<=.10m才进入原生抓取窗口。53项CPU检查通过；十任务仍全部在线、新生成reward、不覆盖动作，并单独计分。

[V10审计](../../../artifacts/stage_closed_loop_20260929/runs/native_gripper_v10_historical_initialization_online_full10/audit.json)；[V10视频](../../../artifacts/stage_closed_loop_20260929/runs/native_gripper_v10_historical_initialization_online_full10/videos.html)；[V11冻结差分](../../../artifacts/stage_closed_loop_20260929/runs/reward_progress_handoff_v11_historical_initialization_online_full10/prelaunch-comparison.json)。

## V11正式结果及继续V12的原因

V11有效3/10，304次Stage逻辑查询/327次HTTP尝试/13次SDK重试，exit0、无查询或回合错误、零动作覆盖，4645.575秒。completion和deep审计全部通过，20次RNG恢复与十任务初始张量逐值一致。成功task1 cream cheese（644步）、task3 BBQ（120步）、task8 pudding（211步）。

视频明确区分：BBQ和pudding实际抓起目标并运输入篮、策略松开；cream cheese后来抓住并翻转/拖移篮子约28cm，不能当作正常目标放置。3/10是保留不改的环境分数，正常目标搬运2/10是额外人工视频解释，不替换benchmark。因此先继续修复，不能仅凭数字相同宣布恢复旧C0行为质量。05:55 UTC、末项仍在运行时已记录这一验收解释。

V12只恢复旧C0的reference重置规则：真正换阶段才重置，同阶段ED开关仅清chunk memory。before_guidance=false时依旧不读取陈旧reward。59项CPU检查通过；原十任务/所有初始化、RDT/ED数值、Poe模型和全在线新生成均不变。先前保存reward重算显示V11有13处阈值差异，其中5个实际交接窗口在固定阶段reference下不应触发；这是可验证的实现差异，不是新成功率预测。

[V11审计](../../../artifacts/stage_closed_loop_20260929/runs/reward_progress_handoff_v11_historical_initialization_online_full10/audit.json)；[视频及全部失败](../../../artifacts/stage_closed_loop_20260929/runs/reward_progress_handoff_v11_historical_initialization_online_full10/videos.html)；[视频质量记录](../../../artifacts/stage_closed_loop_20260929/runs/reward_progress_handoff_v11_historical_initialization_online_full10/qualitative-review.json)；[V12冻结配置差分](../../../artifacts/stage_closed_loop_20260929/runs/stage_reference_v12_historical_initialization_online_full10/prelaunch-comparison.json)。
