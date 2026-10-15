# 当前：Poe 已停止，切换 Codex 账号在线调用 — 2026-09-30 06:31 UTC

用户最新明确要求只使用当前 Codex 账号，不再使用 Poe。原 V12 worker 和 supervisor 已退出；完成2个失败回合，第3个在step528因用户切换要求中止，不能算作完整0/10。历史审计原样保留。当前处于 Codex 接入实现/验证阶段，无本研究 GPU worker。

Stage、每回合身份描述、新 reward/阶段描述全部切换官方 Codex CLI 的现有 ChatGPT 登录；禁止 Poe 回退，不读取/导出账号令牌。GPU2、原worktree、单worker和其他研究资源隔离继续有效。后续 Codex 批次与 Poe 结果分开记录。V11完整有效环境分数3/10，视频显示2次正常目标搬运及1次异常篮子运动成功；尚不能声称新 Codex setting已恢复性能。

授权记录：artifacts/stage_closed_loop_20260929/codex-only-provider-authorization-20260930.json。下一步：五字段Stage与fresh reward接入/CPU检查/真实Codex预检，然后冻结新十任务。下面旧ACTIVE记录仅是历史。

# 在线 Stage 性能闭环恢复（2026-09-29）

用户授权：自行闭环迭代解决失败，解决后再报告。上一轮 0/1 仅完成程序一致性验证，不算性能目标完成。

验收：固定一个候选、完整执行 object-swap 0–9 十任务；在线 Poe Gemini-3-Flash 观察，环境 success 为唯一任务标签，成功不少于历史参考的 3/10。保留所有开发失败；不拼接不同候选的成功任务，不以旧回复回放替代在线机制。5/10 是后续更高算法目标。

资源：原 worktree，物理 GPU2，同研究一个 worker。GPU2 当前存在其他服务，保留该服务；入场至少56 GiB空闲、本 worker Torch allocator 上限48 GiB。共享 GPU 的墙钟性能不可作为独占条件的速度比较。用户此前取消预算作为此诊断的阻断条件；继续逐回合记账，保留验证/正式保护额度。

协议：环境种子沿用 [44,235,43,546,6,621,197,87,151,548]。候选比较用 per_seed_v1 policy RNG：hash(run_seed,0,environment_seed)，避免前一任务的 ED 调用次数改变后一任务初始化。该协议不是历史连续 RNG 的严格复现；使用同协议复核选定候选，不能据此声称所有差异都来自 Stage。

H1 / contact_v2：原 Stage1 的负距离 reward 只负责接近，不能证明抓取成功。允许在当前距离 <=0.06m 或新鲜 ED 归一化改善 >=0.8 后，关闭 ED64步让 RDT 自然抓取；语义 Stage仍为1，在线观察持续。视觉证实 held 才Stage2；恢复至少16步接近后才能再次让渡。完成仍需跨时间的两次视觉证据。

首先开发任务3/8/9，各一个回合。reward固定为上次 Gem3 每任务新生成的函数，检查当前 keypoint 的对象映射一致。C0 RDT和ED参数保留。

H2 / grasp release guard（独立候选，H1完成后再接入）：根据旧失败动作日志，多次掉落前已有篮外OPEN命令。只在可见held时限制篮外提前松手，或对目标附近刚发出的CLOSE作短暂防抖；到篮筐上方可立即释放。保留六维手臂动作，逐步记录原始/执行夹爪命令、几何条件和覆盖理由。使用可获得的机器人末端位姿和既有keypoints；不得读取任务成功、物体附着真值或用任务ID指定动作。

H3（仅在证据需要时）：若接近/抓取仍失败，隔离现有reward的目标、尺度及接触阶段影响；可用历史数值reward作诊断，但必须单列条件。若视觉遮挡阻止有效确认，再评估多视角/时序证据，不能把unknown一律当成功。

开发阶段只指导选型。最终十任务从一个冻结manifest完整运行，报告所有十条结果和视频，不能用3个开发任务代替。

2026-09-29 10:29 UTC：contact_v2 与 grasp_v3 的三个开发任务均完整结束，均0/3，执行审计有效，性能未恢复。grasp_v3 的118个在线请求没有传输重试，不能将此次失败归因于API不可用。记录发现视觉held随后夹爪空闭仍保留持物状态，并对目标遮挡产生长时间Stage2停留。grasp_v3累计覆盖728个夹爪动作，不能将覆盖数量当作效果；此候选不采用。

H4 / proprio_v4：初始图仅用于同一在线模型生成目标外观记忆，后续Stage只输入当前图与该记忆，避免初始/当前机器人姿态和目标身份混淆。四张存档失败图的诊断支持继续验证此改变，但不是GPU性能证据。机器人两指实际开度连续16步小于5mm、目标距末端连续24步大于16cm等提供负持物证据；仍保留原始VLM回复。仅当既有目标关键点明确处于扩展篮筐XY范围之外才启动重新接近。空抓后张爪16步，最多每64步启动一次；取消无证据接触CLOSE防抖。机器人观测不能宣告任务成功，仍采用原环境success做最终计分。先按原协议完整跑任务3/8/9。

reward混杂诊断：对每任务80条固定随机轨迹，新reward与历史C0的候选排序在8/10任务不一致，分歧比例约5.3%–17.1%。结果保存在fresh-reward-vs-c0-functional-audit.json。这证明函数不同，不证明它单独导致0成功；H4仍固定同一批新reward，以隔离Stage与抓取恢复的改变。若H4仍失败，按H3单列历史数值reward的对照条件。

2026-09-29 10:47 UTC：H4开发任务8成功、任务9完整失败、任务3在264步因不完整JSON中止，名义计分1/3但整批执行审计无效。API返回finish_reason=stop但正文在字符串中截断，不能将其视为合法Stage结果；该回合单列接口异常，不能并入正常失败率。原始回复、视频和source_unchanged审计保留。

下一冻结候选保留H4控制参数，Stage输出上限8192，格式校验最多请求2次，严格对同一图像和同一提示词重发，接受第一份有效回复（包括unknown/negative），绝不对语义失败挑选更有利答案。失败与重试分别留存。此前2048与8192的同输入离线复测都返回了完整JSON，因此不能声称仅提高token上限就已定位或消除服务端截断根因；有界校验重试用于恢复可靠执行。

接下来完整十任务采用reward=regenerate：每个任务重新在线生成reward和阶段描述，初始目标外观也重新在线生成，Stage始终在线；不读历史或本日函数缓存。这样直接检查用户要求的完整在线流程。代码、参数、提示词和种子在开跑前冻结，全部十任务无论成败跑完，再判断是否达到3/10。开发结果不拼入最终分数。

传输文档依据（2026-09-29查询）：[Poe参数兼容说明](https://creator.poe.com/docs/external-applications/openai-compatible-api)指出Chat Completions的response_format被忽略，不能依赖服务端严格JSON模式；[Gemini输出预算说明](https://ai.google.dev/gemini-api/docs/generate-content/thinking)指出思考token也可能占输出预算。后者不能单独证明本次Poe截断的原因。另一次显式extra_body reasoning_effort=low的探针确实返回了2184个reasoning tokens，但没有用于当前候选，避免额外改变模型条件。

2026-09-29 10:53 UTC：首次完整在线候选的新增启动器误复用了“旧reward缓存+在线Stage”的worker_env，只给GOOGLE_API_KEY放入当前Poe凭据，OPENAI_API_KEY仍为回放占位值。reward客户端读取后者，十个准备阶段均401；没有机器人rollout。这是本次新增启动代码的接线错误，不能解释此前已成功在线生成十套reward却0/10的实验，也不能记为新算法有效0/10。已改用已有完整在线worker_env，同时在启动时验证两客户端凭据一致；对真实两客户端工厂的假凭据测试覆盖此路径。旧失败全部保留，准备尝试仍计账；修复后使用新名称proprio_v4_fresh_full10_r2重新执行完整十任务。

2026-09-29 11:25 UTC的独立CPU分析：task3在H4开发批与完整在线r2中的环境种子、policy种子307703885、初始关键点、初始16个动作粒子逐元素完全相同；reward不同使初始最终粒子的最佳下标从8变为2，第4次ED迭代后动作粒子也分叉。证据 `initial-particle-control-task3.json`。这直接证明自由重生成reward会改变控制输入，尚未涉及后续Stage差异。r2继续完整跑完。

若r2未达3/10，按已定义H3优先进行受控对照：同一proprio_v4控制、同一固定task3/8/9种子和Poe在线输入，唯一变化为历史C0数值reward。不得称这组是全新reward实验，也不拼入r2分数。若该对照支持reward定义漂移是关键问题，再考虑让新Poe每任务生成符合固定C0数学合同的函数（验证等价、无历史函数文件读取），以建立可重复的在线setting，而不是反复更换随机种子。

另一个待验证机制：H4 task3在可信程度有限的“视觉held+非空夹爪+近距离”窗口中，目标关键点从未进入篮筐XY范围，且Stage2全程零ED；task8成功回合在放置前进入了该范围。详见 `diagnostic-transport-gap.json`。放置引导缺失是后备假设；不能把仅恢复空抓复查等同于已解决最终放置。

## 12:02 UTC：全量候选未达到门槛；成功视频复核

`proprio_v4_fresh_full10_r2` 已完成九个任务，环境成功一次（butter），最后 orange juice 正在继续，保留完整十任务结果，不提前截断。至少尚不能达到 3/10 验收。

对 butter 的八帧视频复核显示机器人明显抓住并搬动了篮子；终局被环境判为 success，但这不是干净的“抓取 butter → 搬运 → 放入固定篮子”轨迹。环境分数照实保留，不能据此宣称该行为已可靠恢复。证据：`artifacts/stage_closed_loop_20260929/butter-success-r2-contact-sheet.jpg` 与原视频；图中 SUCCESS 是整集最终标签，不表示每一帧都成功。

当前候选采用已预先公开的 per_seed_v1 RNG，与旧 C0 的连续随机流不同。development 内部对照保持同一协议；若恢复数值成功率，也只能称新 setting 达到历史分数，不能宣称旧随机轨迹的严格复现。后续整体验收须报告这点，不能混合不同 RNG 的任务结果。

下一步先执行已冻结的 `proprio_v4_historical_reward_dev389`：仅恢复旧 C0 数值 reward，保留实时新的 identity/Stage 和当前控制器，固定 tasks 3/8/9 及种子，不选新种子。该对照用于区分数值 reward 与 Stage 控制。三个新 API 按固定 C0 公式重新生成 reward 的离线检查已通过，但不是性能证据，暂不替换正在执行的版本。

## 2026-09-29T12:09:11.472027+00:00：r2 结果与 H3 启动

完整新 reward + 在线 Stage r2 结果：有效 1/10，两个 audit 全通过，4264.67 秒；320 logical Stage / 333 HTTP / 2 SDK retries / 1 format retry，十个 reward 与 identity 均现场新生成。GPU2 已启动预注册 H3 `proprio_v4_historical_reward_dev389`。

## 2026-09-29T12:14:33.196909+00:00：放置窗口缺陷

新增离线轨迹分析 `scripts/stage_motion_diagnose.py`，r2 task8 在 steps40–224 多次符合“抬高3cm、非空夹爪、目标近手”几何代理，并在80/88/96/104处目标XY进入篮子边界。step97–101的策略 OPEN 被基于 EEF 中心的 release guard 拦截；102–103只有两步 OPEN，104又关闭。位置和视觉观察共同支持“目标在篮子上方但手中心未对齐”是一个真实的动作门控缺陷。不能单凭离线反事实断定修正必然成功。task5虽然也经过篮子上方，当时原策略全程 CLOSE，单修 release guard 不保证解决该任务。

已准备 `core/stage_release_guard.py` 未接入原型：以目标物体相对篮子的XY和高度检查补充释放许可；只在策略主动请求OPEN且已有携带证据时启动8步短暂张爪维持，不主动发起释放，不改变手臂6维动作，不宣告成功。4个定向 CPU 检查通过。此文件目前没有进入任何运行中的执行路径；待 H3 完成后才考虑新增冻结版本进行实测。

## 2026-09-29T12:29:05.317412+00:00：正式比较协议与执行精度

事前明确：development 小批任务继续使用 per_seed_v1，以便对子集做成对控制；最终完整十任务恢复历史 C0 的 continuous policy RNG 和既定十个环境种子，直接对应此前完整 fresh-online 0/10 的原协议。不会按新结果在两种 RNG 中择优混报，不改变任务/种子，不把 development 三任务拼成十任务。r2 的 per_seed_v1 1/10 作为诊断批单列，不能直接归因于 Stage 修复。

通过旧成功视频接触图确认旧 C0 tasks3/8/9 均呈现目标物体抓取/搬运/入篮，区别于 r2 butter 搬篮子的特殊成功；该定性证据保存在 historical-c0-success-contact-sheet.jpg。

另发现尚未接入的固定 reward 原型只验证 float32，不能保证真实 bfloat16 输入上的 C0 数值一致。历史 C0 是 norm→square，时间权重 float32；elementwise square→sum 或将权重转为 bfloat16 会改变分数。64 个固定探针中旧原型与历史函数 float32 最大差 7.45e-9，bfloat16 最大差 3.33e-4（63/64 超过1e-6）；这说明原型校验缺口，不证明它导致当前失败，因为原型尚未启用。现在校验使用相同操作顺序、两种精度共64个条件，并保留 RNG。新增定向检测拒绝仅float32等价的代数改写。与 release 原型合计11个检查通过，新 API 生成程序的 bfloat16合同验证正在进行。

## 2026-09-29T12:30:27.254482+00:00：下一轮事前执行定义

新生成三个 reward（tasks3/8/9）均通过64个float32/bfloat16探针，与旧C0参考最大数值差0，输出位于 canonical_bfloat16_codegen_probe。尚无对应GPU性能结论。

H3后先实施已记录的 payload release 修复；以 r2 task8 的同一已生成 reward、per_seed_v1、同一environment seed151 做一次定向回归测试（prospective run `payload_release_v5_r2_task8`），只打开 payload_release_enabled。Stage/identity仍实时生成，保留与r2的动作前缀对比，不能把单任务成功当作整批恢复。此处缓存reward是为了隔离唯一控制变更。

若定向回归支持修复，则冻结完整正式候选：保持C0采样/ED参数与原十任务种子；continuous policy RNG；新Poe每任务重新生成满足C0数值合同的两阶段reward及描述（temperature0,max_completion_tokens8192，读取c0_contract_v1模板）、在线identity/Stage（8192 tokens,2次格式有效性尝试）、proprio_v4加payload release修复。十任务完整执行，验收至少3/10，全部视频人工复核。没有API或旧函数/Stage回复缓存，禁止按结果挑种子。此批恢复的是新模型条件下性能与一致setting，不是旧Gemini模型的严格在线复现。

## 2026-09-29T12:43:02.478489+00:00：payload 修复已实测；十任务启动

H3固定旧reward有效0/3，96Stage/101HTTP/2SDKretry，1640.66秒左右（准确值见audit）。两个审计通过。payload集成187检查通过，默认legacy路径未改变。

定向回归 `payload_release_v5_r2_task8` 有效1/1，116步任务成功，180.016秒墙钟。与r2旧失败轨迹前97步执行动作逐值完全一致；第一处执行差异是97步 raw OPEN被新规则放行，原始策略动作直到104步才因环境反馈产生差异。这为已定位release guard缺陷提供了可复查的因果证据。两次policy主动释放请求在97、111步触发，额外保持OPEN共5个动作，六维手臂命令没有改写；两个审计有效，视频目标入篮。

按事前定义，已启动 `payload_release_v5_c0_contract_online_full10`：continuous RNG、原十种子、全新在线reward/描述+identity/Stage、固定C0数值合同、payload修复、其余C0 ED设置。单任务成功不算全量门槛。

## 2026-09-29T12:46:31.740534+00:00：正式候选首任务初始轨迹与历史完全一致

`formal-initial-particle-vs-historical-task0.json` 对比历史 C0 与当前正式候选 task0/chunk0：keypoints逐值相同；从initial_before_diversity到full_process_after_rollout（ED迭代0–9）所有可对比的actions、trajectories、rewards、parent_indices均逐值相同。这是在新Poe现场生成reward、C0数值合同验证、continuous RNG下得到的实际bfloat16粒子结果，支持初始C0控制链路保留。不能外推后续不同在线Stage路径的动作仍相同，也不是整批成功率证据。

## 2026-09-29T13:11:28.311994+00:00：后续待验证假设（当前版本不变）

若本批仍未达标，一个明确需检查的剩余保护器问题是：visual_hold 目前只由 VLM 的 clear/held 设置，而强制阻止原策略OPEN没有同时要求目标已被抬起、手指非空与目标近手。因此可能把视觉假阳性变成强制CLOSE。r2 orange juice step32就是width0.077m、目标只抬高约9mm、原策略OPEN被改成CLOSE；随后空夹爪与目标分离。当前full10前段也已出现4个width>0.075的强制CLOSE（partial诊断文件 formal-open-finger-hold-diagnostic.json）。这些是值得检查的动作干预，不足以证明取消它们就会成功；有些可能是已开始张爪后的延迟保护。

若需要下一候选，优先测试只允许在视觉held且已有关键点抬升/近手/非空手指证据时阻止策略OPEN，缺少携带证据时保留原策略动作。仍不主动规划新的手臂动作、不改C0 reward、不用环境grasptruth。现在不改冻结源码，也不提前开启下一GPU回合。

## 2026-09-29T13:16:19.453683+00:00：失败恢复优先级缺陷已复现，补丁暂不应用

实际r2日志有两例：task0 step328和task2 step544已经是robot_observed_failed_grasp_reacquire，却仍处contact_grace且guidance_after=False。根因是apply_recovery只在64步物理重开冷却结束后才清除contact_until，因此短时间内第二次失败恢复会被apply_handoff旧窗口覆盖。纯函数按task0数值复现成功：先request=True，handoff后又变False。应将“取消接触窗口、恢复approach/guide”与“限频物理张爪pulse”分开：前者每次确定失败立即执行，后者仍保留64步冷却且不延长16步张爪。

`pending-recovery-priority.patch` 以及 `pending_test_stage_recovery_priority.py` 已准备、git apply --check通过，但尚未应用；当前十任务源码保持冻结。需要当前批结束后修复该一致性问题并验证。当前正式批前段暂未观察到此条件，不能据此推断后续不会发生。

## 2026-09-29T13:22:48.205364+00:00：正式候选首个成功

完整批次前5任务为1/5，task4 ketchup 在262动作步获得环境成功。接触图 formal-ketchup-success-contact-sheet.jpg 显示目标瓶被抓起、搬至篮子并放置，非搬篮子的特殊成功。该任务没有触发新的payload release许可（原EEF对齐规则已允许相应OPEN），因此不能把这个成功单独归因于该新增分支。全新reward合同、在线identity/Stage和全批冻结条件正常，第6任务继续中。

## 2026-09-29T13:33:24.306824+00:00：正式候选第二个成功

完整候选已到2/7：task6 butter 在183步环境成功；视频 formal-butter-success-contact-sheet.jpg 显示目标被抓起搬入篮子（篮子有碰撞位移，但不是r2中搬篮子覆盖目标的路径）。跟踪目标最大抬升约0.182m。继续剩余tasks7/8/9，尚不停止或宣布达标。

## 2026-09-29T13:37:56.098458+00:00：优先级补丁缩小作用域；当前批已命中

已将待应用补丁修订为 `pending-recovery-priority-v2.patch`：在handoff之后、reward gate之前，仅当no_grasp/outside_goal/Stage1/contact_grace同时成立时恢复approach与guide。保持其他所有状态不变，不在每个远离目标的样本上重置approach时钟。最初always-cancel版本不再使用。待复制的同名pending测试已更新为3例（实际冲突、张爪冷却有界、无冲突零改动）。

当前正式v5批次已经在task3 steps688/696命中该冲突。因补丁会改变实际执行决策，不能只靠“本批分支未触发”来迁移性能结论；完成本批后必须修复并对最终版本做新的真实评测，不能把v5的分数冒称修复后版本的分数。当前v5暂为2/7，继续完整十任务。

## 2026-09-29T14:00:12.177392+00:00：v5结束，v6启动

v5完整在线为有效2/10，仅tasks4/6成功，两个audit全通过；308Stage/324HTTP/5SDKretry/1formatretry，4324.520679秒。所有10个新生成reward合同通过。已应用narrow v2失败恢复优先级补丁，190个集成检查通过；新候选 `recovery_priority_v6_c0_contract_online_full10` 在GPU2完整重测，其他条件与v5相同，不拼接成功任务。旧v5实测冲突共5处：task3/688、696，task7/624，task8/584、592。修复改变这些决策，故不能直接迁移v5分数。

按用户已经给出的预算不阻塞授权，本研究登记GPU小时上限48→50，以便保持24小时/100次保护额度。原消耗台账不改写，新账单独累计；其他研究与共卡服务不变。

## 2026-09-29T14:21:37.775440+00:00：真实携带超时与精确输入复查

v5 task3 的视觉hold始于480步，560步到达80步超时；当时目标抬升0.118m、夹爪宽0.030m、距手0.052m、最新视觉仍held。566步原策略OPEN被放行，576步目标落下。task8亦在272→352步超时，目标仍抬升0.183m且距手0.027m，361步开放后掉落。详见physical-carry-timeout-diagnostic.json。这里证明时间顺序和控制冲突，不声称改后一定成功。

已准备待应用physical carry refresh：只为既有Stage2/visual_hold，在连续至少8步同时满足目标较初始抬升≥3cm、非空未全开的手指(.005,.075)m、距手<.10m、最后执行CLOSE、没有negative grasp证据时刷新hold期限。它不建立新grasp、不改变语义Stage、不推翻负面观测/失败恢复、不自主发起OPEN、不改手臂。无测量支持时旧超时照常到期；已有payload释放优先。15个草案CPU检查通过。代码和集成补丁只存artifacts，尚未改动正在运行的v6冻结代码。v6完整结束后需验证该实际缺陷的修复版本。

同一task0 step488图像下，v5/v6身份文字不同。各自完整请求固定重复3次：v5 held,held,unknown；v6 not_held,not_held,unknown。所有6次格式正常，同一组payload hash相同，model均gemini-3-flash、temperature0、max_tokens8192。证明至少本样本上temperature0不保证语义确定性，且不能据两份提示词的差异单独断言身份文字是唯一原因；回复不用于机器人控制。结果在exact_input_repeat_probe_488。

## 2026-09-29T14:48:34.364579+00:00：v7事前收敛为统一的实测携带许可

v6前5任务0/5，task3目标最大抬升约2.5e-6m却收到12次held；task4最大抬升仅0.0173m，8次held。不能只修已抬起物体的TTL：尚未形成真实携带时，视觉误报也会让保护器阻止原策略OPEN，妨碍重抓。待应用v7因此把同一物理carry证据用于两处：没有已确认carry时保留原策略OPEN；持续carry时更新保护期限。其余Stage语义、C0 reward、ED、手臂命令和失败/释放优先级不变。该配置对全部任务一致，不按成功任务特判。

草案17项CPU检查通过。shadow审计显示v5各任务会取消部分未获carry支持的强制CLOSE；v5成功ketchup也会改变15步，故不声称成功样例全部不受影响。已成功的payload task8定向回归没有此类变化，v5butter也没有。shadow不生成后续轨迹，不能当作成功率。当前v6仍完整跑完，之后应用补丁、执行集成检查并冻结physical_carry_v7_c0_contract_online_full10，保持v5/v6的continuous RNG、原十种子、每任务全新C0合同reward/描述及在线identity/Stage。无跨批拼接，>=3/10且所有审计有效才算达到本轮性能门槛。

## 2026-09-29T15:00:41.545098+00:00：v6出现格式包装错误，整批不作有效验收

v6 task6 butter step152收到完整stop回复，但合法五字段JSON外层为单一Markdown json围栏。两次相同请求均同样回复，被现有strict parser拒绝，导致该任务执行错误。旧结果保留；本批即使其余任务结束也不能作为有效完整十任务，后续继续收集剩余任务证据，不把该错误等同于合法机器人失败。

v7加入仅损失无关展示包装的解析：允许单一完整外层json/无语言代码围栏，随后仍严格五字段、枚举、唯一key、完整JSON解析；不截取花括号、不补全、不给默认Stage、不接受额外prose/多对象/截断。raw回复保留，记录presentation；第一次格式正确（即使unknown/negative）的回复即接受，不按成功含义重试。草案pending-observation-json-fence.patch及15项定向测试已准备，隔离CPU进程验证通过，正在运行的冻结源码未改。

## 2026-09-29T15:12:01.323648+00:00：v7补足同一carry证据的矛盾观测过滤

v6 butter在88步进入Stage2，120步目标仍抬升0.106m、距手0.01398m、宽0.0394m，却被在线回复写成“The butter (chocolate pudding box) is resting on the floor”。核对初始标记图：butter为点0小盒，地面chocolate pudding为点8；当前帧中手下仍露出目标，回复认错地面干扰物。控制器接受not_held后切回Stage1并开启ED，126/127及131以后放行OPEN，144步目标落下。错误样例为v6-butter-contradictory-negative.json。格式错误在更晚的152步，是另一层独立问题。

v7使用同一个持续carry测量做对称一致性处理：只在此前已经Stage2且visual_hold、当前仍持续抬升/近手/非空CLOSE、无negative robot证据和释放窗口时，把冲突的not_held控制值降为unknown，保留原始回复和其他字段。不凭传感代理制造held，不建立新Stage；明确空夹爪、远离手或执行OPEN时不允许该过滤。随后统一使用此cue许可/续期夹持。草案纯函数25检查通过，运行路径测试覆盖raw/control分离以及物理失败覆盖旧carry，待实际源文件应用后全量集成验证。当前v6冻结源仍未改变。

## 2026-09-29T15:26:33.984745+00:00：v7已应用并启动整批

v6最终nominal1/10，task8成功，但task6有JSON围栏解析中断，整批无效。完成/deep审计及源冻结证明已存；304逻辑Stage/321HTTP/6SDKretry/1格式retry，4845.574811秒。task8搬运目标入篮区域，后续调整伴随约0.117m篮子位移，不声称完美行为。所有失败及错误保留。

已应用v7统一carry一致性和无损JSON包装解析，239项集成检查通过。冻结完整新在线十任务physical_carry_v7_c0_contract_online_full10，15:24:23 UTC在GPU2启动（session50504，worker1262475）。v6原有设置保留，增加physical_carry_hold_enabled=true。三处carry用途（动作许可、期限刷新、矛盾negative降unknown）共享同一持续测量，不增加新Stage或手臂动作；动作和query审计加强。保护预算不变，按已授权不阻塞指令把记账户GPU小时cap50→52以留足余量，自己的尝试上限368。

## 2026-09-29T15:54:21.606408+00:00：若v7未达标，优先隔离跨任务初始化耦合

现有formal-initial-particle-prefix-comparison.json证明v5仅task0初始粒子/关键点与历史逐值一致，tasks1–3初始粒子均不同，task2目标关键点亦不同。main.run每任务不重置policy RNG（continuous），ED/原策略调用数随前一任务Stage变化，因此跨任务初始条件发生传播。这属于原评估协议的耦合，并非新发现的API故障。

如果v7仍未达3/10且没有必须先修复的执行错误，下一个优先对照是历史初始随机状态固定：以旧Stage历史回放仅作校准，记录每任务“任务准备前”和“策略回合前”的Python/NumPy/Torch CPU/CUDA RNG状态，并验证记录动作没有改变历史十条轨迹和3/10；随后在相同原十任务/环境种子上，用这些固定起点运行新Poe在线reward/description/identity/Stage及冻结修复控制器。在线阶段不回放旧Stage回复、不缓存旧reward；历史初始化数据仅用于控制比较条件，不搜索新种子，也不按结果挑任务。

这会是一个明确命名的新初始化协议，必须与continuous批次分列，不能冒称原continuous评估严格复现或把不同协议分数拼接。该对照的目的在于分离初始采样与在线机制影响；如果最终用作新统一baseline，报告必须明确其初始化条件。当前v7不变，也尚未实现或启动此对照。

## 2026-09-29 16:38 UTC：后续对照预注册补充

V7 十任务尚在最后一个任务；当前 1/9，无执行错误。BBQ sauce 视频可见抓持后移动离开篮子；task1/3/6 分别已有 306/368/414 个强制 CLOSE 覆盖，而成功 task5 为零覆盖。这只是机制风险证据，不是覆盖导致失败的因果结论。

若 V7 未达标，先执行此前已写明的历史初始化校准（纯诊断），要求历史 127 个 Stage 事件、10 个视频 hash、10 个首批粒子 hash 和 3/10 均完全一致，才导出每任务 prepare/rollout 两处 RNG 状态。新在线批次继续每任务生成 reward/描述与在线 identity/Stage，不回放历史回复、不读历史 reward。该批次与 continuous 协议分开报告。

若历史初始化下的 V7 仍未达标，下一项预定消融为夹爪命令直接使用 RDT 原始输出，保留相同在线判定、reward 数值、任务、环境 seed 与历史 RNG fixtures；审计要求所有 7 维执行动作等于原始动作。仅去除夹爪执行干预，记录原本建议的干预用于诊断。不得从多个版本拼接成功率。必要时再在原 continuous 协议下复核通过候选。没有计划引入 Stage2 新 reward、改变 ED/QD 参数或搜索环境 seed。

初始化工具新增 14 项 CPU 检查通过；GPU 校准尚未启动。新辅助文件当前未被正在运行的 V7 导入，V7 冻结源文件保持不变。

## 2026-09-29 17:05 UTC：依据新的配对证据优先修复当前目标定位

历史初始化校准已完整通过：3/10、127 条 Stage 事件、10 个视频与10个首批粒子 hash 全部一致；20 个 RNG fixtures 已导出。收尾审计的字符串/Path 类型问题在不修改冻结源码或轨迹的独立审计进程中修复并保存有效结果，随后源代码已修正；不是机器人执行失败。

新发现：V7 pudding 的同一当前图（160/192 步）在原提示及仅删除初始位置描述的8次离线请求中，均被误认成仍在地面的目标；用现有跟踪关键点在当前图画 TARGET 圈后，160步两次均正确表达遮挡不确定，192步两次均表达已抓持且悬于篮子上方。该干预增加了当前目标身份定位，不能声称相同原始输入下模型自发改善，也不是任务成功证据。

因此调整后续优先级：下一批 `current_target_marker_v8_c0_contract_online_full10` 只新增当前目标标记及其说明，保留 V7 全部控制、原连续随机流、原十任务/seed 和 C0 数值参数；不加载历史 RNG fixtures，不更改夹爪覆盖开关。每任务仍在线新生成 reward/阶段描述/身份信息，Stage 使用带目标圈的当前图，记录对应未标记图、输入 hash、当前关键点和相机矩阵。目标圈不表示可见性、抓持、完成或 reward。离屏/相机后方点不画圈，不强行移入视野。

158 项相关 CPU 检查通过，运行模块生成的两张诊断标记图与离线探针图逐像素相同。先以完整十任务判断这一输入修复是否恢复 >=3/10；若不足，保留已校准的初始化对照与原生夹爪消融作为后续分离因素的工具。暂不改变 ED/QD 参数，也不引入 Stage2 新 reward。

## 2026-09-30 02:08 UTC：V8结果及V9原生夹爪对照

V8完整十任务有效0/10；363次Stage查询、374次HTTP尝试、1次SDK重试、无执行/解析错误，运行3624.337秒。完成审计和归档源文件审计均通过。Task1/3/5/6/7/8曾抬起目标，但全部放置失败。累计1414个夹爪覆盖，其中task1/3/8分别306/371/306次强制CLOSE。pudding视频可见在93步首次策略OPEN被拦截，随后目标被持续带离篮子区域。不能把离线目标定位改善称为端到端成功。

按已准备的单因素消融，下一批`native_gripper_v9_c0_contract_online_full10`继续V8全部设置，唯一控制变化为`main.grasp_action_guard_enabled=false`。仍保留在线目标标记、每任务新reward/描述/身份、在线Stage、continuous RNG、原十env seeds及C0数值参数。记录本会建议的保护动作，但实际全部7维动作须与RDT原始动作完全一致；审计要求零夹爪覆盖。不得用历史Stage、reward或RNG fixtures。完成十任务后报告独立分数，不从旧轮次拼接成功率。

## 2026-09-30 02:40 UTC：V9运行中确认初始化比较限制

V9与V8的task0首批粒子及全套初始记录张量完全一致，但task1/2关键点与首批粒子不同。证据：V9目录`live-initialization-vs-v8.json`。因此单个控制开关虽然是唯一配置变化，实时API与continuous随机流会共同影响后序起点，不能把跨批次的后序成功或失败全部归因于该开关。

条件性下一步已固定：若V9完整十任务仍未达到3/10，执行`native_gripper_v10_historical_initialization_online_full10`，保持V9全部算法与在线API条件，唯一实验协议变化是使用已严格校准的原历史十任务prepare/rollout RNG状态。每个任务仍在线新生成reward/描述/identity并使用在线Stage；不回放历史动作、Stage或reward，不改变环境seed，不挑选成功任务。必须同时审计20次状态恢复、每任务初始关键点与粒子对齐情况及完整十任务结果。此为独立历史初始化协议，绝不与continuous结果混称，也不声称严格恢复旧Gemini模型。V9必须完整结束并保留全部失败后才启动。


### 2026-09-30 03:23 UTC：会话中断后的监督接管

V9 原监督进程在会话中断时退出，PID1657013 的独立 GPU2 worker 继续运行。已启动独立会话监控 PID1804320，持有本研究运行锁，仅监控原 worker，不重跑、不终止、不启动并行 worker。状态来源与进程身份见该批 `supervisor-interruption.json`。若不能观察到真实进程退出码，将记录 null 并让原审计中的 worker_exit 检查如实失败，不伪造 0；十个实际回合、视频、API日志和成功数仍保留。

后续 V10 的监督进程也通过 start_new_session=True、重定向标准流独立启动，使会话中断不再同时失去监督与退出码。V10 已 prepare，未运行。`preflight-vs-v9.json` 核实运行源码哈希相同，唯一科学条件变化为历史逐任务 RNG 初始化，其他差异仅输出标识与路径。该方式不读取历史 Stage、reward、动作或环境状态。

V8/V9 task0 的前136个动作相同；136步捕获的完整文字与图片字节也相同，但在线模型分别返回 occluded/unknown 与 clear/not_held/outside_goal，导致 ED 开关分叉。证据保存在 V9 的 `v8-task0-input-equality.json` 与 `v8-task0-first-divergence.json`。所以此次单开关配置对照不能视为全程确定的因果干预。


### 2026-09-30：V10 对齐后识别的接近阶段交接差异（条件候选，尚未实施）

V10 task3 的初始关键点、所有记录初始张量以及 step0/8/16 的完整 ED 候选指纹与历史一致。step24 真实手部距离为0.05585495m、归一化reward为0.79722222；当前 contact_v2 派生规则因 `distance <= 0.06` 关闭ED，而历史此刻仍执行ED，并在step32的reward上升触发后关闭。证据：V10/bbq-handoff-prefix-comparison.json。不能把此时的差异归因于API接入、reward代码数值或首批采样。它是新增本地交接规则的可定位差异；还不能仅凭这个差异宣称更改后一定成功。

仅当V10完整有效结果仍不足3/10时，候选V11优先移除这一“仅靠距离即可关闭ED”的旁路，保留reward>=0.8且测量距离<=0.10的既有交接条件、在线视觉阶段更新、失败复查、原生夹爪、历史逐任务初始化和全部C0数值。建议用默认true的显式开关 `contact_proximity_handoff_enabled`，新候选置false；无需扫描任意新距离阈值。运行V10结束并保存原审计后才可修改运行源码、做相关CPU验证与冻结新批次。V11仍完整十任务、新生成reward/描述/identity/Stage；不得把V10成功拼入V11或用历史阶段回复控制机器人。若V10达标则不执行这个条件候选。

### 2026-09-30 04:56 UTC：V11冻结运行期间的归一化只读核对

新增独立诊断脚本scripts/stage_reward_reference_diagnose.py（不属于runtime SOURCES，不改变实验）。V10逐条selected_reward和reset规则能精确重建319份归一化读数；当前控制器在纯guidance切换时也调用reset_stage，旧C0只清除chunk memory、保留阶段reward reference。反事实只计算同一个已观察reward相对阶段进入时reference的数值，不推断反事实轨迹或成功率。27处满足距离<=.10m的记录在两种reference下跨越.8阈值；salad step96等存在例子。

该差异是候选机制问题，不是已证明导致失败。V11运行期间不修改任何冻结源代码。若V11完整有效达到>=3/10，优先完成报告；若仍不足，结合V11轨迹复核后考虑只恢复旧C0的“阶段改变重置reference，纯引导切换仅清chunk memory”规则。保持before_guidance限制，关闭引导期间的旧reward值仍不用于新交接，避免把“保留归一化参考”误作“重用陈旧reward测量”。

### 2026-09-30 05:55 UTC：视频审查后的验收解释（末项运行期间）

V11当前环境成功3/9，最后task9未结束。task3 BBQ和task8 pudding是实际目标抓起搬运并放入篮子；task1 cream cheese虽环境成功，却有明显篮子翻转/拖移0.28m。环境分数绝不改写，但不能用这一异常成功宣称已恢复历史三个正常搬运成功的行为质量。若最终正常目标搬运不足3项，继续已有闭环排查和机制候选验证，不把数字门槛当作全部问题解决。该质量门槛是基于已要求的视频核查提出的额外解释，不替换LIBERO原始score，也不把跨版本成功拼接。若最后task9成功且视频确认正常搬运，完成整批审计后即可结束本轮恢复工作。

已有V12草稿条件相应扩展：V11完成并保存有效审计后，如环境<3或正常搬运成功<3，可在复核reward-reference差异后考虑单项reference保持测试；不得改动V11冻结结果、筛选seed或补跑V11失败项。仍然完整新生成reward/描述/identity/Stage十任务，原全部初始化状态和RDT/ED参数固定。

2026-09-30 06:10 UTC附注：复查V11 orange juice step96/176原图，step96可见纸盒在夹爪下方倾斜、至少有抓持/抬离局部地面的视觉证据；原跟踪点z相对初始为负，不能据此断言模型held必错。长物体旋转改变已有keypoint高度，3cm lift只是诊断proxy，不是物理抓持真值。没有实施“低于3cm就否决Stage2”的新规则，也没有发送这一假设的API探针。V12仍只改归一化reference保持。


# 当前：GPU2 仅 Codex 在线十任务已启动 — 2026-09-30T06:50:24.185418+00:00

用户要求禁止 Poe；该限制已落实到启动器、worker环境与主程序。所有 Stage、每回合身份描述、fresh reward/阶段描述均通过当前 Codex CLI 的 ChatGPT 登录调用 **gpt-6-astra / low**。CLI显式强制ChatGPT登录，禁用工具/插件/其他模型接入，不加载.env，不读取Poe凭据，任何失败均无Poe回退。

当前冻结批次 `codex_only_v13_historical_initialization_online_full10`，supervisor 2217380，worker 2217645，GPU2单worker；原worktree管理。进度：artifacts/stage_closed_loop_20260929/runs/codex_only_v13_historical_initialization_online_full10/output/status.json；监督日志：artifacts/stage_closed_loop_20260929/codex-only-v13-supervisor.log。不要重复启动或修改运行中的冻结代码。预计2–4小时，按真实在线延迟修订；当前尚无完整成功率。

260项接入/旧接口/启动回归及65项控制器回归通过；真实Codex预检的reward通过64项C0数值检查，identity和五字段Stage均成功。预检不是GPU成功率。Codex输出程序每任务新生成，reward数值在本地执行计算。保留V12其余控制设置和已校准历史初始化RNG，禁用旧reward/Stage回复缓存、无任务失败重试。新版本独立统计，不能称为原Poe模型严格复现。

Poe V12因用户要求中止：2个失败回合完成、第3个step528中断，非完整0/10；所有旧审计保留。V11完整有效环境分数3/10，视频复核2次正常目标搬运和1次异常篮子运动成功。尚未达到新Codex setting性能验收，未开始QD优化。

授权：artifacts/stage_closed_loop_20260929/codex-only-provider-authorization-20260930.json；新冻结方案：artifacts/stage_closed_loop_20260929/runs/codex_only_v13_historical_initialization_online_full10/proposal.json。完成后保存completion和deep审计、初始张量比较、视频复核与本研究记账，继续依据结果闭环，不拼接版本成功数。



# 当前：Codex接口复测通过，V13运行，V14修复自动接续已排队 — 2026-09-30T10:02:03.756463+00:00

Codex独立真实图片请求于2026-09-30 09:48 UTC通过：gpt-6-astra/low，单次CLI调用，21.11秒，五字段JSON有效，无失败和应用层重试。证据：artifacts/stage_closed_loop_20260929/codex-availability-retest-20260930T094804Z/result.json。Poe继续禁止；当前账号接入可用不等于任务性能恢复。

V13 `codex_only_v13_historical_initialization_online_full10` 仍在GPU2运行：已完成7/10，成功0，当前task7 step656。supervisor2217380、worker2217645。前8个任务reward全部通过64项C0检查，首批关键点/粒子CSV/21阶段张量与历史一致；已记录查询无错误。完整分数尚未产生。

已确认Stage控制整合错误：Codex明确报告held+occluded+unsupported时，控制器因为要求clear而不进入Stage2；V13 BBQ step80/96均如此，step96 grace到期错误恢复接近ED。V13与V11前96个实际动作完全相同，首个分叉就在96；96步原图人工检查确为瓶子在夹爪下方悬空、位于篮上，目标上半部被夹爪遮挡。此证据支持具体控制修复，不说明所有失败皆同因，修复效果仍须在线实测。

V14草稿：仅允许明确held+occluded+unsupported经过原机器人矛盾过滤后建立Stage2与visual_hold；unknown不升级，完成依然要求clear+inside_goal+not_held+supported两次时间分隔确认。API模型/推理、reward、初始化、夹爪动作及其他设置均保持。137项草稿控制回归+6项队列保护检查通过；运行中的V13源文件哈希全部未变。

自动接续队列已启动，PID2595833，状态artifacts/stage_closed_loop_20260929/codex-v14-continuation/status.json。等待V13真实退出和完整两层有效审计；若最终<3/10，则保存V13视频/诊断/记账，核验源哈希，安装草稿，重跑安装后检查，冻结并启动GPU2 V14完整十任务。若V13>=3，停在视频复核节点；若任何检查失败，保存错误并等待本会话继续处理，绝不改写结果或回退Poe。队列与GPU worker必须一起管理，勿重复启动。队列未派发前可写queue/cancel.json取消后续派发；用户暂停时应停止本研究拥有的队列与worker。

V14方案与变更：artifacts/stage_closed_loop_20260929/drafts/codex_partial_visibility_v14/proposal.json、source-changes.json。总目标尚未完成，不把API可用/CPU测试/计分阈值等同正常目标搬运恢复。



## 验收口径澄清（V14启动前，2026-09-30T10:32:15.828695+00:00）

严格遵循用户明确门槛：单个冻结版本的完整在线十任务，环境成功率≥3/10，全部源代码/配置/请求来源/初始化/真实退出审计有效，并保存失败、配置、视频及最终分析。最新用户要求只用Codex，因此旧goal中的Poe名称不再代表当前接入授权。此前助手附加的“至少3次正常目标搬运”不是用户新增验收门槛；成功视频中的异常篮子运动必须如实另列，但不改写环境分数，也不以额外门槛替换原目标。这是在V14启动前固定的解释，不能在结果出现后调整计分。
