# 2026-09-14：20 任务新架构与 verifier 初始化

## 当前范围

- 服务器 hgpu1；实验代码 `/shared/hengyil6/vls/repo`。
- 新根目录 `/shared/hengyil6/vls/self_improve/fixed_budget_50/env_position20_20260914`。
- 原始 policy：`/shared/hengyil6/vls/models/pi05_libero_finetuned_v044`。
- 只选择 10 个 `use_environment` 与 10 个 `use_swap`（位置扰动）任务。
- 按用户最新确认，仅用下列两个任务初始化新 verifier；接受新 head 后，同一热进程自动开始正式 20 任务实验。下文较早的“不启动正式实验”状态属于当时的历史记录。
  - `libero_goal::open_the_middle_drawer_of_the_cabinet::use_environment`
  - `libero_goal::push_the_plate_to_the_front_of_the_stove::use_swap`
- “Planner 不干预 steering”仅限初始化：在线保持 VLS/FK 采样与执行，Planner 负责事后标签、数据和训练；正式阶段恢复候选选择、阶段/guidance 判断及完整 slow loop。
- 顶层 Planner 保持帐号任务 `01a0893c-15b0-7203-881c-de3c5bcee058`、GPT-6 Astra / ultra。未创建新任务或定时任务。

## Steering 对齐依据

参考已完成 baseline 的配置：
`/shared/hengyil6/vls/baseline_runs/env_position20_20260910/v44_vls_official_dev_20260911/config.json`
以及 `baseline/experiments/env_position20_20260910/vls_runtime_template.json`。

特别注意：模板的 `guide_scale=40` 被 LIBERO adapter 的任务推荐值覆盖。该 baseline 的 **2170 条实际 sampling/chunk 记录全部为 80**。新运行显式使用 80，并记录配置值与实际值的差异。

| 参数 | 新运行 / baseline 实际值 |
| --- | --- |
| 全部候选数 | 40 |
| 每 chunk policy steps | 10 |
| PI0.5 inference steps | 10 |
| guide / diversity scale | 80 / 10 |
| scale 上限 | 80 / 20 |
| MCMC steps | 4 |
| sigmoid k / x0 | 25 / 0.75 |
| FK potential / lambda | max / 10 |
| FK adaptive / frequency | true / 5 |
| stage query limit | 50 |
| episode horizon / reset wait | 720 / 5 |
| policy observation | 128 × 128 |

RE-STEER 上限 50 个 chunk，全部 retry multiplier 为 1/1，不随 retry 放大。新标签版本 `fixed_budget_50-v2`。原 fixed-4/fixed-10/v1 标签、预算字段和旧 verifier 权重均不迁入新训练。

这是 steering 数值配置对齐，并非声称所有 VLM provider 相同：当前顶层语义/阶段/ticket Planner 按用户指定保持 Codex 帐号，reward-code generator 的既有 provider 配置未在本次迁移中更换。

## 合并与现成示范

每个新 delta 使用 Planner 建议的同一 alpha：语言、视觉、动作系数完全相等。没有固定的候选 alpha 网格；候选在当前 parent 上重建，再按现有当前任务提升与旧任务遗忘差值、raw regression 和 trigger recheck 选用。

已核对 precollection completion、任务身份、native-success curation、HDF5 文件大小、LeRobot episode 数和成功 MP4 文件：**20 任务 × 15 = 300 条成功示范，300 个查看视频**。进入 slow loop 时 Planner 选择对应的已有任务数据，不重新采集。原示范 ticket 的旧 parent 不会成为当前 SFT parent；训练与新 delta 仍绑定当前运行 parent。合并失败记录拒绝结果，保留父模型，不自动要求补采。

## 初始化实现

`scripts/initialize_candidate_verifier.py` 使用新 registry，只注册原始 v44。新 head 从随机权重开始；`untrained_head.pt` 仅是未训练的初始化记录，**不是可部署模型**。

Planner 选择实际初始化 rollout 的任务/初始状态。每次经历保存双相机观测、全部候选、实际动作、native 结果与视频；由 Planner 自主解释、修订标签、选训练数据和独立检查经历、决定 retrain。独立检查 episode/snapshot 不进入梯度或 checkpoint 选择。只训练小型场景投影、全部候选轨迹编码、历史编码和两 logits 分类 head；v44 VLM 始终冻结。独立检查接受后才部署 learned verifier。

初始化进程首次启动 PID **819376**（GPU 6）。首个实采发现 `SamplingDiagnostics` 缺少真实 FKD 的 `resample_timesteps` 字段，已补齐并加入 FKD→candidate gate 兼容测试。错误发生在执行任何动作之前，不作为能力失败或训练样本。

首版 worker 当时没有恢复入口，因此为加载修复做了一次进程替换：**823396**。这次确实重新加载模型，未声称热修原进程。旧日志保留在 `initialization/worker.819376.infrastructure-abort.log`，替换记录在 `worker_replacement.json`。

新版异常后仍保留 `Main`/policy 对象；修复数据或网络问题后以 `initialization/resume.request` 恢复同一 context，新的 attempt 目录保留先前失败记录。测试验证重试前后 policy 对象相同、仅构造一次，失败尝试不进入完成经历 ledger。权威动态状态见 `initialization/status.json`、`initialization/worker.log` 与完成时的 `initialization/completion.json`。

## 旧实验与回退

旧 formal supervisor、fast loop、slow-loop replay 和遗留 teleop 已按 PID/命令身份检查后停止。旧 formal 输出有 stop/retired 标记；旧 registry、incidents、slow_loop、slow_work 标为废弃，不被新运行读取。为避免误删被 precollection 引用的成功示范，未递归删除整个旧 self_improve 根目录。

移除 3 个旧源码文件、2 个旧测试和 2 个旧配置，共 7 个。可恢复备份位于：
`/shared/hengyil6/vls/self_improve/candidate_v3_code_backup.kZsghU/sept14_previous`。
新代码 SHA-256 与部署记录在 `activation.json`；没有改变原始 v44、示范文件/视频或 baseline 目录。

## 验证

已完成合并张量逐模块数值测试、固定50预算/原生成功优先、独立训练输入、当前 parent 与旧示范来源分离、禁止重复采集、Hydra 实际配置和完整回归检查。服务器完整回归日志：
`/shared/hengyil6/vls/self_improve/candidate_v3_code_backup.kZsghU/sept14-production-tests.txt`。
生产回归结果：**609 passed, 1 skipped, 3 warnings，135.97 秒**；部署清单 SHA-256 全部一致。
首采修复及保温重试的针对性测试：16 passed；修复后生产完整回归为 **611 passed, 1 skipped, 3 warnings，82.33 秒**，另存为 `sept14-production-tests-after-startup-fix.txt`。最终代码清单为 `sept14-current.sha256`。
修复后 PID 823396 已进入 `SAMPLING_INITIALIZATION`；第1个 context 为 `libero_goal::open_the_middle_drawer_of_the_cabinet::use_environment`、init 2。真实 PI05 采样日志已记录 step 0 guidance scale=80、非恒定 reward。训练完成/部署可用尚未成立，仍须等待真实经历标注及新 head 的独立检查。
新 registry revision 1 的 policy 为 `pi05_v44_original`，verifier_id=null；初始化规划请求已由指定 Planner 正式 claim。
实际启动进度以初始化状态文件为准，不将单元测试拟合或随机 head 当作真实 verifier 已可用。

## 实采执行缓存修复

在 PID 823396 的首次实际执行中，逐步对比 `action_osc` 与 `analysis.npz`，确认了执行缓存缺陷：4 个 chunk 分别选择候选 35/5/15/37，但每个 chunk 只有第 1 步使用所选候选，后 9 步重新读取完整 policy cache 后误取候选 0。并非模型能力失败，也不是 50 步预测被当作 50 步执行。

修复 `_run_episode`：启用 candidate controller 时，在换 chunk 的边界采样/选择，边界之间保留已选择的 chunk，不再读取所有候选的缓存。经典 baseline 路径不变。针对真实 `_run_episode` 的测试同时覆盖 10 和 50 步预测，确保实际连续执行所选候选前 10 步。Planner 请求增加 `execution_horizon=10`，仍完整提供所有预测步。

旧 40 步经历、sidecars、scene-feature cache 和 snapshots 已移出活跃数据目录，保留在：
`initialization/invalidated_selected_candidate_cache_823396`。
`invalidation.json` 保存原始 facts SHA、受影响 episode ID 和路径迁移映射；没有修改原始动作、标签或预算。旧 attempt 标记 `INVALID_FOR_TRAINING.json`。当时完成经历 ledger 为空，registry verifier_id=null，因此未产生被污染的训练模型。成功示范和视频完全未动。

修复通过完整 staging 回归：**615 passed, 1 skipped，83.13 秒**。为加载旧进程尚不支持的代码修复，按身份检查后进行一次显式替换，新 PID **831128**，从同一任务/init2 的 `attempt_002` 开始。记录为 `initialization/selected_candidate_cache_recovery.json`，没有将这次替换称为热加载。

新版在异常后的 `ERROR_WARM` 请求边界，可通过带 `reload_main_sha256` 的显式 `resume.request` 重载兼容 Main 方法，保留同一 policy 和冻结 encoder 对象；不构造/加载新权重，拒绝源码 hash 不匹配的请求后仍保持驻留。此入口不用于模型结构迁移；本次初始化阶段职责切换另加显式的、固定 PID 与脚本 hash 的 driver handoff。单元测试验证对象身份和错误请求恢复。

最新 71 文件生产源码清单为 `sept14-current-after-cache-fix.sha256`；先前 `activation.json` 与 `sept14-current.sha256` 是对应时刻的历史记录，不覆盖伪装为最新。完整原始模型、300 条示范及 baseline 目录不在本次修复范围内。

部署后生产完整回归再次通过：**615 passed, 1 skipped, 3 warnings，99.90 秒**，日志为 `sept14-production-tests-selected-candidate-fix.txt`。PID 831128 已完成加载并进入 `SAMPLING_INITIALIZATION`，第 1 个环境扰动抽屉 context / init2；step 0 的实际 guidance scale=80，已生成 40 条候选，由既定 Planner claim 新请求。此时尚无完成的初始化 episode，未开始梯度训练；正式实验也未启动。

真实执行回查通过：新请求 `f1aaaf81c35e4e76bfe31fe4e2aec3bf` 选中 `episode-001-step-00000-stage-1-b40f52c35e-r001-s035`。新 episode `b8607b9eb4fc476e973c233aa65492cd` 的第 1–10 步 `action_osc` 与该候选的对应动作逐元素最大误差均为 **0**，10 步均不再误取候选 0。首 chunk 实采修复验证完成，初始化继续推进。

## 两任务初始化与自动正式实验交接（用户澄清后）

用户明确确认在线 Planner 的限制只限初始化，正式实验保留完整架构。初始化采样与训练读入均限定上列两个任务，允许在这两个任务内选择不同初始状态；没有第三个任务，也没有固定必须采满的数据量。历史 `plan_000.json` 不被覆盖，实际执行使用过滤后的 `effective_plan_000.json`，完整阶段设置另存 `scope.json`。

初始化每次保留全部 40 个完整候选，以 VLS/FK 原始粒子次序中第一个未被物理安全检查否决的候选执行；不请求 Planner 语义打分、选择候选或决定阶段/guidance。兼容性结构中的零语义分明确标记为占位值，不冒充 Planner 输出。`initialization_posthoc_only=true`、`use_vlm_stage_recognition=false` 只覆盖初始化，既有 reward-code generator 和 steering 数值配置保留。标签解释、训练样本选择、训练时机及独立经历审查继续由既定 Planner 决定。

已完成抽屉任务 init2：**129 步 LIBERO-PRO 原生成功、10 条 RE-STEER 标签**；该经历与视频继续有效保留，不重采、不修改旧标签预算。盘子任务 init1 先前 30 步因人为请求边界暂停，属于中断的部分经历，不是任务能力失败，更不证明用尽 50 次。

此次切换保持同一 **PID 831128**、policy 和冻结 v44 scene encoder。`driver_handoff.json` 记录 `model_reloaded=false`，`RESUMING_WARM` 记录 `weights_reloaded=false`。旧 driver 在无动作的 `attempt_002` 入口交接到新 driver；新 driver 正在 `attempt_003` 继续盘子任务。没有启动另一套模型或定时任务。

新 head 经既定独立经历检查接受后，初始化 driver 直接调用正式 driver，继续使用原 Main/policy 对象；正式配置恢复在线 Planner、阶段判断、learned verifier、经验复用、现成示范 SFT 与统一三模块 alpha merge。初始化经历不会被记为正式实验成绩，正式阶段仍只覆盖环境/位置扰动 20 任务。

验证：完整 staging 回归 **623 passed, 1 skipped，92.56 秒**；最终阶段切换/职责/训练范围针对性检查 **28 passed，8.00 秒**。最新 71 文件源码清单为 `sept14-current-two-task-posthoc.sha256`；本次 13 文件修改前备份位于 `candidate_v3_code_backup.kZsghU/before_two_task_posthoc`。训练技能用于核对冻结 backbone、仅 head 训练及独立检查隔离，未因此引入新训练框架或采样配额。

部署后服务器完整回归为 **623 passed, 1 skipped, 3 warnings，66.16 秒**，记录于 `sept14-two-task-posthoc-production-tests.txt`。盘子新 attempt 已完成实际 step 0、step 10 的 VLS 采样，GPU 6 在采样时利用率达到 100%；原 PID 与显存驻留保持不变。

实采只读核验时已产生 8 个新 decision、79 个真实执行 step。前 3 个 chunk 均保留全部 40 个候选、执行原始粒子 0 的 10 步，动作逐元素最大误差均为 0。对应语义记录明确为 `provider=local_policy`、`planner_called=false`；此次热切换后的新顶层帐号请求数为 0。实际配置为 `initialization_posthoc_only=true`、`use_guidance=true`、`use_vlm_stage_recognition=false`。此时新 head 尚未训练完成、正式阶段尚未开始。

## 抽屉 init3 奖励代码准备失败与热恢复

两条有效经历完成后，Planner 在同一两任务范围内选取抽屉 `use_environment/init3` 和盘子 `use_swap/init2` 作为后续独立经历。抽屉新 context `42126c8b59d5330781f90a2ffae535e151762ea646090435c73084798b92ddfe` 的 `attempt_001` 在零动作准备阶段失败：生成的 stage2 奖励含 `start_pos.clone()` 和 `end_pos[0] -= 0.1`，不符合既有无副作用 AST 子集。拒绝发生在奖励加载时，不是 native task failure。

保留原安全验证器，未增加 clone、原位修改或其他白名单权限；文件 SHA-256 仍为 `74227b98d6f56e59b6ecf0ba25759528be50e94e69dd9403203596638d4113e7`。修复在 Main 的准备路径：向原 reward-code generator 明确实际执行子集，要求用函数式表达式而非下标写入；验证不通过时携原输出及错误有限重生成，默认最多 **3 次生成（含首次）**，各次原始代码及验证结果分别保留。未经验证的代码不执行；缓存代码只读验证、不自动改写。任务、图像、provider、steering 数值、预算和成功判据均不改变，也没有新增初始化在线 Planner 调用。

同时修复准备失败归属：未来此类零动作错误使用单独的 `preparation-...` episode ID，不借用上一条已完成经历。旧错挂中断事件 `ef0430563a9f4f3791a058fe391f59df` 保留原样，另追加 `preparation-attribution-correction:ef0430563a9f4f3791a058fe391f59df` 更正，明确属于抽屉 init3；盘子已完成 50 次重试的事实及既有 11 条 Planner 标签不因此撤销。

针对性 staging 检查 **25 passed，6.62 秒**。改动前生产文件保存在 `candidate_v3_code_backup.kZsghU/before_guidance_repair`；新的 72 文件源码清单为 `sept14-current-guidance-repair.sha256`。恢复记录 `initialization/guidance_preparation_recovery.json`；同一 **PID 831128** 已通过 Main hash 核验完成热更新，`weights_reloaded=false`，正在抽屉 init3 的 `attempt_002` 继续。没有重启模型或新增定时任务。

完整 staging 回归 **629 passed, 1 skipped，121.15 秒**，生产针对性检查 **25 passed，12.43 秒**；分别记录在 `sept14-guidance-repair-staging-tests.txt` 和 `sept14-guidance-repair-production-tests.txt`。

## 用户明确结束初始化采集

用户随后要求“这次结束之后就可以开始初始化head然后进入正式实验了，不要一直卡在这里”。以正在运行的抽屉 `use_environment/init3` 为采集截止点，不再继续原 plan001 中尚未执行的盘子 init2，也不再开新初始化 context。该抽屉 attempt002 已于 **94 步原生成功**，初始化 ledger 现有 **3 条有效经历**：两条不同初态的抽屉成功、一条盘子实际用尽重试预算的失败。

已向既定 Planner 下达立即标注必要决策、利用现有两任务经历发起 head 训练并走既有同进程正式交接的指令。新抽屉经历可用于与训练 episode 不重叠的独立诊断；不额外要求独立集包含两个类别、固定数量或统计显著。独立指标仍须如实报告，不将初始化部署称为已证明泛化；输入、有限损失/权重、冻结 v44 和加载检查仍保留。此次训练检查规范不引入新的采集门槛。

用户截止意图保存在 `initialization/finalization_request.json`，同步至 AGENTS 与 Planner 任务；现有 driver 的训练成功分支直接进行正式交接。没有中断当前经历或重启模型。最新源码清单为 `sept14-current-initialization-cutoff.sha256`。此记录写入时属于标注/训练调度阶段，尚未据此宣称梯度训练或正式实验已经开始。

## 新 head 完成，正式实验已自动启动

Planner 正式提交训练请求 `51ea96f794344078a2ca7b6c88301485`：旧抽屉成功的 10 条 RE-STEER 与旧盘子真实耗尽的 11 条 EXPANSION 用于训练；新抽屉 init3 episode `6600aea3aed94b8c82e498269e6548af` 的 step80、step90 两条标签仅作独立诊断，不进入梯度或 checkpoint 选择。

GPU 6 完成新 head `candidate-verifier-39c170b17de59be357bb`，best epoch=100。训练 21 快照 accuracy=1、CE=5.097595e-6；独立 2 快照 accuracy=1、CE=1.823879e-5。两条独立快照同属一个成功 episode，只检查这条经历中没有误触发 EXPANSION；未验证独立负类、其他任务泛化或相对旧 head 改善。Planner 在明确上述限制后接受其作为初始化起点。`initialization/completion.json` 已存在且 `refreshed=true`，registry revision=2，policy 仍是 `pi05_v44_original`，controller=`learned_verifier`。

2026-09-14 **06:57:52 UTC / 14:57:52 中国时间**，原 **PID 831128** 自动写入 `initialization/formal_handoff.json` 并进入正式 driver；`same_process=true`、`model_resident=true`、`scheduled_task=false`。正式状态已为 `RUNNING`，20 contexts / 20 tasks，当前 **第 1/20**：`libero_10_env`、`KITCHEN_SCENE4_put_the_black_bowl_in_the_bottom_drawer_of_the_cabinet_and_close_it`、init37。未继续待定的初始化盘子 init2，初始化有效经历保持 3 条。正式实验成绩单独记录于 `formal_experiment`，不混入初始化成绩。

## 正式流程修订：完整 rollout、原生成功、50 仅为上限

用户明确选择：取消初始化式固定预算执行流程，保留最多 50 个 RE-STEER chunks；正式每个 attempt 在进入 EXPANSION 前，必须至少完成一次完整任务 rollout（原生 success、terminal 或原任务 720 步上限），不是只完成一个 10-step chunk。原生 success 是唯一成功标准，出现后立即停止，不要求跑满时长，也不经 Planner/VLM/replay 再确认。

实现中将 head 原始提议与实际路由分开：过早的 EXPANSION 提议记录为 proposal，实际路由为原 rollout 的 EXECUTE 延续，不伪造 RE-STEER 标签、不消耗或补充重试预算；真实 RE-STEER 仍最多 50 次。安全 veto 无可执行候选时为安全中止，不强行完成轨迹，不进入正常 EXPANSION。新的正式配置禁用 fixed-budget fallback；slow loop 保留现有初始化 head，若其不可用则报错，不悄悄退回固定预算采集。POLICY_STAGED 原本即直接进入 Planner 自主 verifier refresh，不附加自动固定预算 replay。

旧正式 attempt001 的 episode `6f086c2c001b470ebadad0dbe65cd1bd` 在第 30 步就触发了 job `187756ddeb0a4af1abc8127318e14311`，尚未完整执行任务。其 lookup 先后遇到 Planner 的非规范标签和将 media event_id 当作 facts event_id 的 citation 错误；两次均未写入有效训练标签，也尚未产生 ticket/SFT。按新规则采用追加 CANCELLED 与 ATTEMPT_EXCLUDED 的方式撤销旧请求，原 30 步动作及原始记录不篡改，不计正式失败、不进入训练。仍以同一任务/init37 开启新的合法 attempt，不重训初始化 head。

全量 staging 测试：**642 passed, 1 skipped，65.83 秒**。覆盖早期 EXPANSION 延迟、720 步普通 rollout 不变成 50 次强制 RE-STEER、重试上限不回填、原生 success 无 terminal 标志仍立即结束、安全中止、取消任务与驻留模型对象身份保持。热更新请求由固定 PID 与源码 hash 校验，使用已有 initializer 的 Main 热更新边界，再替换控制器方法/config；不构造新的 policy、冻结 VLM 或 verifier 对象，不新建定时任务。

生产针对性测试 **25 passed，3.95 秒**，74 个发布文件 hash 全部核对一致，清单 `candidate_v3_code_backup.kZsghU/sept14-current-formal-rollout-protocol.sha256`。2026-09-14 **07:34:01 UTC / 15:34:01 中国时间**，同 PID 831128 在同任务/init37 的 `attempt_002` 恢复 RUNNING。`formal_experiment/protocol_updates.jsonl` 实测记录 policy、冻结 encoder、verifier 三个对象身份均未变化；GPU 6 驻留显存约 14342 MiB。有效配置 `controller_mode=learned_verifier`、`require_learned_verifier=true`、`require_complete_rollout_before_expansion=true`、retry cap=50；旧 job 已为 CANCELLED，旧 attempt 为 ATTEMPT_EXCLUDED，正式完成数仍为 0/20，没有把 30 步算成完整任务失败。

## Verifier 实测判断反馈与后续纠错训练

用户要求利用 verifier 判断与后续实际结果之间的差异，作为后续 retrain 的奖励信号。新增 `mode_gate/verifier_feedback.py`：原始事实、head 提议和决策时输入不改动；另生成版本为 `observed-verifier-action-feedback-v1` 的可核验衍生证据，保存在 incidents 下的 `verifier_action_feedback.jsonl`。没有新 controller、奖励模型、固定数据配额或自动 replay。

- 同一 episode、同一 policy 的连续实际动作，在原决策 `remaining_budget × 10` 步内原生成功：目标 RE-STEER。原 head 提议 EXPANSION 时记录 `decision_reward=-1`，原提议 RE-STEER 时为 `+1`。
- 实际完整执行全部剩余 RE-STEER chunks 且未成功：目标 EXPANSION。原提议一致时为 `+1`，原提议 RE-STEER 时为 `-1`。这是该次实际续跑的结果，不宣称所有可能轨迹均无法成功。
- 提前停止、没有实际执行、原记录作废、动作缺失/重置、换 policy 后成功等，均不自动产生二分类奖惩。普通完整 rollout 前置 EXECUTE 不能伪造 retry 计数；不能以计数未增长为由把超过实际步数窗口的成功称作预算内成功。窗口只用于反馈归因，**不否认任何 LIBERO-PRO 原生成功的任务成功判定**。

Planner 在既有事后经验审查时自主决定是否使用、纠正标签、正的有限样本权重、与其他来源的混合和 retrain 时机；annotation 记录 `feedback_id`、`decision_reward`、两条原始 decision/outcome 事实引用，并保留修订链。训练选样时重新核对衍生证据及原决策的预算/时间，排除后续失效的证据。优化仍为纠正目标上的正权重交叉熵，不把 `-1` 当成负 loss 权重；训练记录关联每条反馈的使用情况，未来结果不进入特征。沿用现有 head warm start、冻结 v44、独立经历检查后才部署。

新事后审查 worker 自动发布并提供 `verifier_feedback` / `verifier_feedback_unresolved` catalog。为保持 GPU 6 的 PID 831128 原样运行，没有为更新事后审查模块重启/热改当前模型或控制器；已向既定帐号 Planner 同步有限命令 `python -m mode_gate.verifier_feedback --incidents <campaign>/incidents --publish`，在当前保温进程缓存旧审查类时于现有审查入口使用，再走原正式 annotate/retrain 动作。旧接口支持额外 annotation 字段及正权重训练，训练使用记录可由 annotation ID 回溯。此命令不请求模拟动作、不创建定时任务。

全量 staging 回归：**674 passed, 1 skipped，62.82 秒**；生产针对性回归：**43 passed，5.40 秒**，JUnit 报告 `candidate_v3_code_backup.kZsghU/verifier-feedback-production-tests.xml`。覆盖 EXPANSION 纠错、RE-STEER 正反馈、真实重试耗尽、20/21 步预算边界、换模型/重置/缺失记录拒绝归因、普通标签与反馈混合训练、正权重、原始输入不变、独立经历隔离及证据事后失效。部署前代码备份为 `candidate_v3_code_backup.kZsghU/before_verifier_feedback.yYFaXj`。

首次生产发布结果：旧作废 episode `6f086c2c001b470ebadad0dbe65cd1bd` 为 CENSORED；当前 episode `ef259c5cd76c4381b673cc66a3c4e237` 的 decision `f95ad796dd4f433eb0e40f3f6da7f4e2` 为 PENDING，尚未产生可确认的奖励/纠错标签。本次不伪造训练样本，也没有据此声称当前 head 已经改善。原 PID 和正式 rollout 继续保留。

## 用户快速实验设置：合并系数固定为 0.8，SFT 配方不变

复查确认反向奖励已在上一版实现并有测试：原 head 选择 RE-STEER，但连续真实执行耗尽当时剩余重试预算仍未成功，目标为 EXPANSION、`decision_reward=-1`；原判断与实际预算内成功/实际预算耗尽结果一致，均为 `+1`。没有将一次 chunk 失败、提前中止或尚在执行的经历直接当作耗尽预算。

用户暂时取消合并系数搜索。在 `configs/candidate_experiment.json` 添加可编辑配置 `merge_coefficients={"mode":"fixed_uniform","alpha":0.8}`，新训练 delta 与所选历史 remedy 都只生成一个合并候选：语言/视觉/动作 `alpha_map` 全部为 0.8，沿用现有统一 delta 合并算法。新 delta 的公式为 `parent + 0.8*(theta_ft-parent)`，即 20% parent + 80% 本轮 SFT；不改变历史已接受的 lineage 系数或原始 v44。

固定模式不调用帐号 Planner 搜索合并系数；未消费的旧多系数缓存不能覆盖当前用户配置。Planner 仍负责候选轨迹、经验分析、remedy 和训练数据选择，但 remedy 响应中的旧多系数建议仅保留为原始历史，实际重建使用 `[0.8]`。有效配置写入 merge selection、ticket 和 policy-gate 交接产物。当前父模型对照、raw regression、trigger recheck 和已有 baseline/control 实验不改动，不额外测试别的 merged alpha。

SFT 数据文件及采样器保持原样：有旧已部署任务示范时新/旧/original replay=50%/25%/25%；没有旧示范时新/original replay=50%/50%。`mode_gate/training.py` SHA-256 保持 `c21d47ad6a45b000a8143d848b4ef639578fbe12167b02993efce139698e3740`，本次生产 `coft_sources.json` 保持 `44f284a1a165ee2e127067e80dcb34908a3fdb51711ad2cae6fb03e4c7dc199c`。SFT 步数、优化器、数据来源和 source sampler 未改动；verifier 的 Planner 自主选样策略也不受 SFT 比例约束影响。

修改时正式进程仍为 PID 831128、RUNNING，第一个任务已执行到 step60；slow loop 中仅有先前的 CANCELLED job，没有活跃 SFT、merge selection 或候选模型需要回退。部署只更新后续 slow-loop 代码/配置，不重启当前 policy/冻结 encoder/head。修改前代码备份：`candidate_v3_code_backup.kZsghU/before_fixed_alpha_08.LXhWoP`。

最终全量 staging 回归 **684 passed, 1 skipped，65.91 秒**；生产针对性回归 **56 passed，6.63 秒**。覆盖固定模式不调用 Planner 搜索、新 delta/历史 remedy 均只生成 0.8、旧多系数缓存不生效、原始 remedy 证据不改写、三模块张量数值正确、重复进入可恢复、配置随评估交接保留、SFT 两种来源比例不变，以及 verifier 正反奖励。生产报告为 `candidate_v3_code_backup.kZsghU/fixed-alpha-08-production-tests.xml`；76 个发布文件与 `sept14-current-fixed-alpha-08.sha256` 全部一致。生产实际读取结果 `alpha_values=[0.8]`、三模块均 0.8、`search_enabled=false`；SFT 代码/来源和 promotion 配置的修改前后 SHA 一致。已同步给现有 Planner，原 PID 831128 仍为 RUNNING，未重启模型。

## 后续用户变更：正式 steering 不再请求帐号 Planner

此项覆盖本文此前“仅初始化不干预、正式恢复在线 Planner”的阶段约定。新增独立开关 `main.planner_steering_enabled=false`，正式 campaign 同步记录；不会借用 `initialization_posthoc_only` 或关闭 learned verifier。在线语义候选选择、视觉 grounding、阶段识别和 guidance 开关判断均不再请求帐号 Planner。VLS/FK 保留全部候选并执行原顺序中第一个未被硬安全 veto 的候选；占位语义分明确标为 `local_policy/planner_called=false`，不冒充 Planner 判断。

既有 reward-code generator、VLS 采样与 guidance 开启配置保留。`use_vlm_stage_recognition=true` 是从 baseline 继承的子开关，但被上述总开关禁止调用；有效 `online_stage_guidance_judgment=false` 写入决策上下文。没有换用另一个 API、没有新增固定步数/奖励阈值的阶段判定器；rollout 沿用初始阶段/guidance 状态，不再由帐号 Planner 动态切换。其余正式协议保持：完整任务 rollout 前不进入 slow loop，最多 50 次 RE-STEER 不是配额，native success 唯一成功标准，verifier 正反反馈与事后自主标注/选样/retrain、既有示范 SFT、统一三模块 alpha=0.8 和 SFT 配比不变。

采用显式 PID/源码 hash 核验的 attempt 边界热切换：现存 `Main.run` 的协调器重载入口装入新 runtime，并只替换五个兼容 Main 方法，不调用构造器、不加载 policy/冻结 encoder/head，不在 live episode 中修改 simulator。被人为配置切换中断的旧 attempt 原始动作/视频保留，另追加 `ATTEMPT_EXCLUDED` 与 censored 事实，不算正式失败，不生成负奖励；仍从同一 task/init37 的新 attempt 开始。修改前 76 文件 hash 均与上一版清单一致，备份为 `candidate_v3_code_backup.kZsghU/before_online_planner_role.lntS4S`。

针对性 staging 验证 **96 passed**：本地选择跳过硬安全 veto，全部 40 候选仍进入 learned head，RE-STEER/EXPANSION 两种输出及完整 rollout 前延迟 EXPANSION 均保持，预算不重填；阶段触发不调用在线 Planner；无阶段 recognizer 也可进入正式 driver；方法热更新检查 PID/hash 并保持模型对象，固定 0.8 与反馈测试通过。

部署与实采复核：**694 passed, 1 skipped，143.64 秒**（全量 staging），生产针对性 **51 passed，26.72 秒**。76 个发布文件与 `sept14-current-online-planner-disabled.sha256` 全部一致。PID 831128 原样存活，policy、冻结 encoder、verifier 三个对象均未替换，GPU 6 显存仍 14342 MiB。旧 attempt002 的 130 步和视频留存，其 7 条 verifier 反馈均为 CENSORED、reward=null。

北京时间 16:40:08 已从同一 task/init37 热续跑 attempt003、episode `21767cbca4df4be2b8e8e0615b562e49`。16:42:44 实采到 step125，13 个 decision 均为 40 候选且 `planner_called=false`，恢复以来新增帐号请求 **0**。首 4 个完整 chunk 实际动作与本地所选粒子逐元素最大误差为 **0**；head 已实际给出 7 次 EXPANSION 提议，按已有完整 rollout 前置条件继续原轨迹，没有被关闭或退回初始化。完整配置和核验留存在 `.codex/online-planner-disabled-verification.json` 及服务器副本；事后 Planner 已收到新职责通知。SFT 源码与 coft_sources SHA 和上节一致，未改比例。
