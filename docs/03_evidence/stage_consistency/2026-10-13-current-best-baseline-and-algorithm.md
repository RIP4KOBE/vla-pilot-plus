**截至 2026-10-13，按本研究的 RDT / LIBERO object-swap OOD 口径，最强已验证 baseline 家族仍是 P2/C0：RDT + ED + absolute-EEF RBF 多样性 + Stage ON，QD archive OFF。其历史最高完整单轮记录为4/10；本会话最近验收的新 Codex 在线版本 V17 为3/10。尚无新 QD 候选证明稳定超过这一 baseline。**

“最高历史观测值”“选定的C0参考轮次”“新Codex在线基线”是不同记录。此前对话中的3/10是指定C0参考轮次和V17的分数，不是整个仓库历史最高值。以下所有成功率均按各自原始分母报告，不合并不同轮次成功，不将小开发集与完整十任务直接排序。

| 条件 | 结果 | 关键边界 |
| --- | --- | --- |
| 历史P2/C0 absolute-RBF control | 4/10，tasks3/5/6/7 | 完整同一r03 recovery run；历史control validity PASS，Gemini-2.5-Flash在线Stage、旧缓存 |
| 首轮QD实验中的C0/P2对照 | 3/10，tasks3/8/9 | 选定的历史复现参考轮次，QD关闭 |
| 本会话Codex V17 | 3/10，tasks3/8/9 | Codex gpt-6-astra/low；每任务新reward/身份描述，在线Stage；完整审计通过 |
| 历史真正开启QD的最好配置 | sparse_primary、uniform_expand20各2/10 | 有效，但未通过全部采用门槛 |
| 后续N系列 | 没有完整、可比的胜出候选 | N7开发2/4但验证3/20；N35仅1/7；N36无有效候选成绩 |

历史4/10原始[结果](/mnt/data/shared2/zhuoli/output/p2_direction_normalized_rbf/supplemental_recovery/recovery_20260805_r03_control/formal/p2_stage_on_abs_rbf_control/results.txt:2)与[审计](/mnt/data/shared2/zhuoli/output/p2_direction_normalized_rbf/analysis/direction_rbf_formal_audit.json)仍在。十个selected episodes均来自同一个r03 control运行，全部视频可读。该记录也有27次Stage query error和2个collision/push/drop/wrong-object综合标签；按当时规则control有效，不代表零异常或已经按V17更严格接入规则重测通过。该报告对Direction新候选的adoption FAIL不等于control4/10无效。固定十任务一次评测也不支持“稳定40%”的统计结论。

最新主研究已核对到N36；正式验收派发0次。N34/N35的1/7为十任务计划在tasks0–6后按无望门停止，未观察tasks7–9，不能写成完整1/10或稳定14.3%泛化率。见[10月13日研究汇总](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/progress-and-cleanup-20261013.md)。

如果比较全仓库不同任务，标准libero_object还存在RDT9/10、PI05 10/10，另外PI05+VLS的swap曾有4/10但使用240步协议；模型、任务或步数不同，不能据此覆盖当前RDT720步Object-Swap排名。

代码位置

统一导航根为：
`/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood`

| 用途 | 当前实际worktree | 分支 / 当前HEAD |
| --- | --- | --- |
| 最简洁的历史P2 baseline实现 | [historical_variants/eds_init_pg_diverse_sampling](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/historical_variants/eds_init_pg_diverse_sampling) | exp/eds-init-pg-diverse-sampling / b3db98cf4fd98a6479d92683e33ebe3d032f25d9 |
| 历史C0 3/10及QD对照存档 | [historical_variants/eds_quality_diversity](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/historical_variants/eds_quality_diversity) | exp/c0-codex-historical-20260925 / 53187e6ea8b69e9f830c10be0bc25757db5d2794 |
| 已验收Codex V17实现 | [GPU2 study_worktree](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-gpu6-20260922T063626Z/study_worktree) | exp/rdt-qd-ed-gpu6-20260922T063626Z / 77761b4cda78ac3b6762a6aa60f97b07fde7c1dc |

历史4/10实际记录git_revision=849760962eb606ef6c6c04f8f422f079877355c9，另有code_state_sha256=b275a852934b17f43e6e1e2f2cc70ac66eee8b5efb75992132f9821ada3977ed。当前PG分支b3db98c是后续“freeze audited P2 baseline”提交，不能仅checkout旧revision就假定重建当时工作区。

V17位于原来的`/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z`兼容链接下，物理路径为表中统一归档位置。其分支存在未提交修改/未跟踪文件，HEAD本身不能代表V17。此次核验[accepted-setting.json](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-gpu6-20260922T063626Z/study_worktree/artifacts/stage_closed_loop_20260929/runs/codex_failed_contact_v17_historical_initialization_online_full10/accepted-setting.json)、manifest、resolved-config和全部48份冻结source文件哈希匹配，当前对应源码也匹配。复用时以该冻结包为准。上述研究机制没有完整合入main；直接在main运行默认配置也不等于P2或V17。

核心算法：RDT给动作先验，ED搜索候选，RBF减少候选重合，Stage决定何时引导

P2是推理时搜索配置，不是新训练的checkpoint。使用RDT-1B-LIBERO-Object EMA和固定编码器；不在每次实验中重新训练RDT。当前观测图像、语言和机器人状态编码后，RDT生成64步、128维统一动作表示，实际解码前8步为LIBERO7维动作（平移3、旋转3、夹爪1），按20Hz执行，再获取新观测。

| 参数 | P2及V17共同核心设置 |
| --- | --- |
| 任务 | libero_object_swap；tasks0–9；每回合最多720环境动作 |
| 种子 | 44、235、43、546、6、621、197、87、151、548 |
| RDT | Object EMA；预测64步；实际执行前8步 |
| 推理调度 | 配置num_inference_steps=null，读取checkpoint的5步DPMSolver；prediction_type=sample |
| ED群体与轮数 | 16候选、10轮；use_cem=false |
| 父代权重 | legacy_temperature，参数0.1；实际softmax(0.1×reward) |
| 初始多样性 | rbf_diverse_denoise；absolute_eef；scale20；start_ratio0.8 |
| 短去噪多样性 | rbf_diverse；absolute_eef；scale20；start_ratio0.6；全部搜索轮 |
| 加噪/短去噪长度 | [3,2,2,2,2,1,1,1,1,1] |
| 跨chunk记忆 / 保留精英 | fresh population；chunk_memory_fraction0；elite_carryover_count0 |
| QD档案 | 关闭；V17的qd_metrics_observer只记录观察指标 |

第一步：Stage判断本chunk是否需要ED。历史P2使用Gemini-2.5-Flash在线返回阶段/引导决定，reward与阶段描述来自旧缓存。V17改为Codex在线生成事实字段，再交由带时间状态的控制器决定阶段、接触宽限和引导；不能把两个版本的Stage行为混为相同setting。ED关闭时走RDT原生去噪与动作执行；ED开启时进入下面的16候选搜索。

第二步：从16份独立噪声生成初始候选。每份噪声经过5步RDT去噪。在配置规定的步骤，用预测末端轨迹之间的排斥梯度调整模型预测的clean sample。源码虽命名RBF，但absolute_eef分支实际使用逆距离势，不是常见的高斯exp核：

`U = Σ(i≠j) 1 / (sqrt(||vec(P_i)-vec(P_j)||² + 1e-6) + 1e-6)`

对U求梯度，做全局范数归一化后，以scale20沿降低U方向更新，让候选轨迹分散。只作用于前8步平移通道，不直接修改旋转与夹爪。初始start_ratio0.8的实际实现是5步去噪的前4步施加，不是“到80%之后才施加”。[P2 RBF实现](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/historical_variants/eds_init_pg_diverse_sampling/core/rdt_policy_steer.py:6117)。

第三步：把候选动作投影为末端位置轨迹并评分。这里的“rollout”不是对每个候选克隆MuJoCo、模拟抓取碰撞。实际使用当前环境提供的EEF位置，线性累计平移：

`p_h = p_0 + 0.01 × Σ(τ=1..h) a_τ,xyz`

因此它是可微运动代理，只预测末端平移，不预测目标物体是否真正被夹住、碰撞、滑动或掉落。“libero_gt_rollout”的配置名称不能当作完整动力学模拟证明。[投影实现](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/historical_variants/eds_init_pg_diverse_sampling/core/env_adapters/libero_adapter.py:1620)。

Stage1的C0目标为接近当前目标关键点q：
`R(A) = -Σ_h w_h ||p_h-q||² / Σ_h w_h`，靠后的轨迹点权重3，其他点权重1。Stage2函数返回0；V17检测到常数零reward无有效搜索信号，实际关闭ED，让RDT执行搬运/放置。这里的reward数值由本地函数计算，模型只生成函数/阶段信息，不为每个粒子发API请求。

一个实际代码细节必须保留：H=8时，reward切片是`trajectory[:,1:H]`，即只评分p1..p7；RBF使用p1..p8，最终也执行8步。对应七点评分权重为[1,1,1,1,3,3,3]/13。这是评分范围与实际执行范围的现存差异，不能写成完整64步物理规划或完整8步reward评分。[历史切片](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/historical_variants/eds_init_pg_diverse_sampling/core/rdt_policy_steer.py:1600)、[V17合同](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-gpu6-20260922T063626Z/study_worktree/core/c0_reward_contract.py:36)。

第四步：执行10轮父代重采样、加噪、短去噪与评分。按当前16个候选reward分配父代概率：
`P(i) = exp(0.1 R_i) / Σ_j exp(0.1 R_j)`。
参数名虽然叫temperature，legacy实现是乘0.1而不是除0.1。然后有放回抽取16个父代，对其重新加噪，再用RDT短程去噪产生新16候选并评分；没有开启CEM top-k精英筛选。

短程步数由`np.linspace(3,1,10).astype(int)`得到[3,2,2,2,2,1,1,1,1,1]。初期扰动相对大，后期更局部。rollout RBF作用于每轮前ceil(0.6k)个去噪步骤，所以k=3时前2步、k=2时全部2步、k=1时唯一一步都施加；并没有默认干净尾段。每个完整ED chunk名义上5+16=21次批量去噪调用，评分候选数16×(1+10)=176；不是21或176次模型API请求。

第五步：只从第10轮最终群体选择reward最高的候选，解码并执行前8动作。默认未保存跨轮全局最优、没有精英保留，旧轮的最好轨迹可能在重采样/扰动中丢失；也不是QD archive中的全局最好。执行后重新观测，并在chunk边界更新Stage与下一次搜索。[P2最终选择](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/historical_variants/eds_init_pg_diverse_sampling/core/rdt_policy_steer.py:5698)。

V17对上述骨干增加了哪些控制规则

V17保留RDT/ED/RBF核心参数，但用当前Codex账号官方CLI、gpt-6-astra/low，每任务重新生成身份描述、reward函数和阶段描述，执行中持续在线判断。历史fixture只对齐RNG初始化，不回放旧Stage、reward、动作或环境回复。

其控制规则包括：明确的held+unsupported在部分遮挡时也可建立Stage2；物理携带证据可维持或在限定条件下建立短时抓持保持；接近reward达到0.8且目标距离≤10cm后暂时关闭ED交给RDT；同一宽限内出现明确空闭夹爪，再隔16–32步有新视觉篮外支撑、实测张开>7.5cm且实际OPEN，可取消无效宽限并恢复ED；同一语义阶段仅开关guidance时不重置reward reference；完成需要两次间隔明确视觉证据，而正式计分仍取环境success。

V17的全部5,585个7维动作未经控制器覆盖。它在线恢复了BBQ120步、pudding211步、orange214步三项成功，但orange全程仍为Stage1，milk有释放后恢复缺口，不能称阶段语义完全正确。这些是Stage控制增量，不是QD算法收益。

此baseline的能力与局限

RDT提供有用的动作先验；ED负责按任务reward筛选、局部再搜索；RBF减少群体轨迹重合；Stage避免在不合适的操作阶段持续使用接近reward。其强项是低训练成本、可追踪的推理搜索，已有完整OOD结果作为对照。

局限包括：投影不模拟接触和目标运动；主要reward只约束末端接近，不直接判断抓持/搬运质量；多样性只改平移；评分7步与执行8步不一致；最终选择仅看末轮、旧精英可能丢失；Stage在线输出与状态历史仍可改变轨迹；目标关键点/标记利用仿真状态辅助；当前十任务开发结果不是独立留出泛化结论。仅增加多样性、档案占用率或搜索预算不保证成功率提高。

若目标是阅读最强历史baseline的简洁实现，从PG/P2 worktree和4/10冻结config入手；若目标是在用户指定Codex条件下继续当前研究，使用V17的accepted-setting/source/config作为统一对照。不可把旧Gemini4/10直接当作新Codex运行的预期成绩，也不可用main默认配置或仅一个branch HEAD代替完整冻结setting。

