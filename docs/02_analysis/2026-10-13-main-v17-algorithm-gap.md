**当前 main 与 Codex V17 的算法进度、实现与差距（2026-10-13）**

当前本地 main 的已提交算法停留在2026-06-04的 RDT/LIBERO 接入与 RDT+VLS 引导阶段；已经具备模型推理、观测/动作适配、可微轨迹代理、reward梯度、RBF和FKD、旧版在线Stage。ED/EDS外层搜索、QD模块、Codex CLI接入和V17外层控制协议仍在实验工作树中。

本报告依据当前Git与源码静态核验，不是一次新评测。没有运行GPU、API或测试，没有修改main。V17指9月30日验收的明确setting，不把该研究分支所有可选功能视为启用。

**一、进度边界与默认运行**

| 对象 | 当前状态 |
| --- | --- |
| main HEAD | `d51cb85f485502e0429c79529872efef2ec59981`，2026-06-04 14:36:10 UTC |
| 主要合入 | `689f487`，2026-06-04；RDT LIBERO VLS rollout |
| 最后修复 | 数值型no-op reward（如return 0）转成正确device/dtype的Tensor |
| 主线策略 | Diffusion Policy、PI05、RDT三类 |
| 裸默认 | backend=libero，suite=libero_object，policy=pi05，use_guidance=false |
| 默认Stage | 配置虽true，但无引导时提前跳过关键点、reward VLM和Stage构造 |
| 显式RDT无引导 | RDT Object EMA原生动作推理与LIBERO闭环 |
| 显式RDT有引导 | 旧版VLS：reward梯度 + RBF + FKD + 旧Stage |
| 主线ED/QD/Codex | 尚无ED路由、QD实现与Codex CLI provider分支 |

主线后续日期的未跟踪研究计划、根目录HANDOFF，以及归档的历史文档，不等于相关算法已经合入。

[主线能力索引](/home/hynx/lizhuo/VLA-Pilot++/docs/00_overview/rdt-libero-worktree-integration-index.md:20)
 · [默认配置](/home/hynx/lizhuo/VLA-Pilot++/configs/config.yaml:26)
 · [默认策略](/home/hynx/lizhuo/VLA-Pilot++/configs/policy.yaml:9)
 · [无引导提前返回](/home/hynx/lizhuo/VLA-Pilot++/main.py:242)

**二、主线已完成的RDT基础链路**

主线已解决早期RDT接LIBERO的观测和动作语义问题，这部分也是V17的基础：

1. 使用RDT-1B-LIBERO-Object EMA；T5语言编码、SigLIP图像编码；不是每轮重新训练模型。
2. 读取agentview与wrist图像的两帧历史、7个关节位置和2个夹爪qpos；夹爪状态按训练语义归一化，填入128维统一状态槽位。
3. 多粒子采样共享一次实际环境观测，不把同一观测重复推进成多帧历史。
4. RDT输出64×128动作表示；取slots [39,40,41,42,43,44,10]转为平移、旋转、夹爪7维动作；夹爪离散为±1。
5. 每次执行前8动作，20Hz，再观测；RDT配置num_inference_steps=null，读取当前指定checkpoint的5步DPM-Solver推理。
6. LIBERO默认上限来自backend的720动作；顶层main.max_episode_steps=240不能据此认定LIBERO只跑240。

[观测处理](/home/hynx/lizhuo/VLA-Pilot++/core/rdt_libero_obs_processor.py:74)
 · [动作解码](/home/hynx/lizhuo/VLA-Pilot++/core/rdt_libero_action_converter.py:31)
 · [RDT配置](/home/hynx/lizhuo/VLA-Pilot++/configs/policy.yaml:32)

候选末端轨迹使用线性累计位移：
`p_h = p_0 + 0.01 × Σ(a_τ,xyz)`。
它来自当前末端位置与候选平移动作，不对候选执行MuJoCo接触前瞻。V17沿用同一投影，因此不能把完整接触模拟视为V17新增能力。[投影](/home/hynx/lizhuo/VLA-Pilot++/core/env_adapters/libero_adapter.py:1542)

**三、主线RDT+VLS的实际算法**

以下参数指显式选择RDT并开启guidance后的默认引导配置；裸默认仍是无引导PI05。

```text
当前观测、语言、机器人状态
  → 编码条件
  → 20份64×128高斯噪声
  → 5步RDT去噪：
       第1步：RBF排斥
       后4步：reward梯度
       符合时点与ESS条件时：FKD重采样
  → 对最终候选评分，选择最高reward
  → 执行前8步
  → 在动作块边界检查旧Stage触发
  → 下一轮观察与生成
```

RDT预测clean sample，denoiser在no_grad运行。两种梯度从当前noisy x_t经可微末端轨迹计算，再修改模型的clean-sample输出，不反传穿过RDT网络。

**3.1 RBF排斥已经存在于main**

主线RBF与V17使用同一逆距离势：
`U=Σ(i≠j)1/(sqrt(||vec(P_i)-vec(P_j)||²+1e-6)+1e-6)`。

对整个batch的梯度范数归一化，只保留前8步平移槽位39–41，沿降低U方向调整输出。它不是Gaussian指数核。

main默认scale=10、start_ratio=null，5步时分界点取timesteps[1]；因此只在第1步施加RBF，后4步施加reward梯度，二者是if/elif互斥。V17 ED初始阶段则前4步RBF20，并在十轮短去噪继续施加。

[主线去噪循环](/home/hynx/lizhuo/VLA-Pilot++/core/rdt_policy_steer.py:1199)
 · [RBF](/home/hynx/lizhuo/VLA-Pilot++/core/rdt_policy_steer.py:1425)
 · [分界规则](/home/hynx/lizhuo/VLA-Pilot++/core/rdt_policy_steer.py:1535)

**3.2 reward梯度直接拉动动作候选**

主线VLM生成函数f，计算其对候选末端轨迹的reward梯度。它没有冻结为V17的C0公式；主线LIBERO模板还建议抓取时增加XY坐标权重。

设归一化reward进展为ρ，动态引导尺度为：
`s_t = G × sqrt(1-alpha_bar_t) / (1+exp(25×(ρ-0.75)))`。

候选越接近该阶段参考下的高进展区，sigmoid项越小。梯度只修改平移通道，不直接修改旋转和夹爪。

一个容易误读的覆盖关系是：config.yaml写guide_scale=40，但LIBERO adapter默认推荐80，main优先采用推荐值。因此按默认LIBERO配置开启RDT引导，基准G实际为80，随后再乘上述动态因子；不能仅改main.guide_scale就假定生效。

[reward梯度](/home/hynx/lizhuo/VLA-Pilot++/core/rdt_policy_steer.py:1462)
 · [尺度](/home/hynx/lizhuo/VLA-Pilot++/core/rdt_policy_steer.py:1542)
 · [任务尺度覆盖](/home/hynx/lizhuo/VLA-Pilot++/main.py:142)
 · [LIBERO默认80](/home/hynx/lizhuo/VLA-Pilot++/core/env_adapters/libero_adapter.py:1694)

**3.3 FKD是同一次去噪内的粒子重采样**

主线默认MAX势、lambda=10、adaptive_resampling=true、frequency=5。权重来自粒子历史最大reward的exp(10×reward)，按有效粒子数ESS决定是否有放回重采样。20粒子时ESS小于10才重采样；重采样后清空DPM-Solver多步历史。

默认5步调度、start_ratio=null下，仅第2个去噪位置存在一次实际FKD评分/重采样机会。终点虽被FKD类列入调度，RDT调用方明确跳过终点，因此最终由RDT显式argmax选择，而不是FKD终点校正分支。

这是在同一次5步去噪中的筛选，没有ED的十轮再加噪与短去噪搜索。[FKD调用](/home/hynx/lizhuo/VLA-Pilot++/core/rdt_policy_steer.py:1278) · [FKD实现](/home/hynx/lizhuo/VLA-Pilot++/core/fkd_class.py:247)

配置MCMC_steps=4只在RDT函数间传递，循环体未使用；不能声称主线RDT实际做了4次Langevin更新。此结论限RDT路径，不据此否定其他策略的MCMC实现。

**3.4 评分与reference的实现细节**

| 用途 | 主线实际轨迹切片 |
| --- | --- |
| reward梯度 | p0…p7，含当前起点 |
| FKD与最终选择 | p1…p7 |
| RBF | p1…p8 |
| 实际执行 | 8个动作 |

主线归一化为`clip(1-r/r_ref,0,1.2)`。reference取首个guided chunk中最后一次成功reward梯度评估值，来自当时noisy粒子和整批reward求和。V17 ED reference取该阶段首次最终所选粒子的reward；形式相似但数值来源不同，不能直接比较两个ρ。

main本来就只在语义Stage变化时reset reference；同阶段仅开关guidance不reset。V17保留/强化此合同，并新增审计，不能将其描述为main完全没有的机制。

[切片](/home/hynx/lizhuo/VLA-Pilot++/core/rdt_policy_steer.py:1139)
 · [reference建立](/home/hynx/lizhuo/VLA-Pilot++/core/rdt_policy_steer.py:1288)
 · [语义阶段reset](/home/hynx/lizhuo/VLA-Pilot++/main.py:510)

**四、主线已有的reward与Stage，以及明确缺口**

开启guidance后，main可为每episode生成阶段描述与reward函数，也可从指定缓存目录读取。函数保存、加载、device/dtype包装、随机dummy验证都已存在；最后一次main提交还修复了return 0这种数值返回。

但缓存仅验证目录存在，缺少当前task/keypoint身份绑定。dummy验证主要检查可执行、非None/Tensor，缺梯度只是警告；未固定C0目标公式、多精度数值行为，也没有“当前reward实际能否支持引导”的能力门控。dummy随机样本会使用全局Torch RNG。

主线Stage使用OpenAI兼容SDK，默认model=gemini-2.5-flash；reward默认gpt-4o。实际endpoint可由配置/环境改变，本次没有读取凭据或调用接口，不能断言当前正在使用Poe。源码没有当前Codex账号CLI接入分支。

模型输入是初始关键点图、当前图、任务、阶段描述和触发原因，模型直接输出stage N和guidance yes/no。查询只在动作块边界由夹爪命令变号或reward跨0.8/0.6触发。没有V17的首次/周期/不确定复查、结构化视觉事实、携带保持和失败接触复查。

两处静态可证的控制缺陷：

- action_executed在块执行结束时归零，下一边界用旧chunk索引0提取“刚执行的夹爪命令”，而非最后实际执行动作；可能漏掉块内开合。V17记录previous_executed_gripper_command。
- recognizer预设(stage1,true)，调用异常或解析缺字段时仍可能返回该值；main没有独立query-valid状态，继续采纳。API失败因而可能改变控制状态，无法与有效Stage判断清晰区分。

它们是代码层面的风险，不足以单独量化某次任务失败的原因；需要对应运行轨迹验证。

Stage0不会直接记实验成功：主线真实success依然取环境info.success。差距是完成判断缺少V17的双时点明确证据，而非旧版用模型自评冒充环境成功。

[reward准备](/home/hynx/lizhuo/VLA-Pilot++/main.py:416)
 · [基础验证](/home/hynx/lizhuo/VLA-Pilot++/utils/guidance_utils.py:113)
 · [查询触发](/home/hynx/lizhuo/VLA-Pilot++/main.py:467)
 · [错误回退](/home/hynx/lizhuo/VLA-Pilot++/core/gemini_grounder.py:188)
 · [夹爪索引](/home/hynx/lizhuo/VLA-Pilot++/main.py:654)
 · [环境成功](/home/hynx/lizhuo/VLA-Pilot++/main.py:766)

**五、main与V17验收配置逐项对照**

| 层面 | main RDT+VLS | V17验收setting | 差距性质 |
| --- | --- | --- | --- |
| 默认启用 | 裸默认其实PI05无引导 | 显式RDT+ED profile | 入口/配置 |
| 主搜索机制 | 一次5步VLS去噪 | 初始5步+十轮ED | 实质算法变化 |
| 群体规模 | 20 | 16 | 算法参数 |
| reward作用 | 直接梯度+FKD+最终评分 | 重采样权重+最终评分，不调用reward梯度/FKD | 实质算法变化 |
| RBF | 初始前1步，scale10 | 初始前4步及短去噪，scale20 | 搜索覆盖变化 |
| 父代选择 | FKD MAX exp(10×历史reward)，ESS门控 | 每轮softmax(0.1×reward) | 实质算法变化 |
| 搜索迭代 | 无外层ED | 10轮，短去噪[3,2,2,2,2,1,1,1,1,1] | 实质算法变化 |
| 最终选择 | 完整去噪末群体argmax | 第10轮群体argmax，无跨轮精英 | 同为最终群体，搜索过程不同 |
| QD | 未实现 | 代码/observer存在，验收archive=none | 不代表V17开启了QD |
| 轨迹代理 | 末端累计位移 | 同一代理 | 共同局限 |
| provider | OpenAI兼容SDK，默认Gemini Stage/GPT-4o reward | Codex CLI gpt-6-astra/low三条调用链 | 接入/实验条件 |
| Stage控制 | 模型直接输出阶段与开关 | 视觉事实+机器人证据+有状态控制器 | 实质控制变化 |
| 失败恢复 | 事件触发，无明确失败复查 | 接触宽限、携带保持、失败接触复查 | 闭环机制 |
| reward | 通用生成/可选缓存/基本验证 | fresh c0_xyz_v1数值合同 | 科学条件与可靠性 |
| guidance gate | 模型bool与函数列表是否存在 | 控制请求且reward有效、非恒定 | 一致性机制 |
| reference | 首块最后梯度评估，整批reward | 首次最终所选粒子reward | 信号语义变化 |
| 初始化 | 每episode从Torch全局流抽seed | 固定task/seed+20次RNG状态恢复 | 可复现协议 |
| 审计 | 基础日志/视频/结果 | 输入/回复/开关/reward/动作/provider/初始化审计 | 证据完整性 |
| 分发状态 | 基础代码已提交，但资产/环境仍有本机依赖 | 验收包完整度较高，许多核心文件未提交 | 都需要整合与便携化 |

V17主循环：
```text
在线视觉事实与机器人证据
  → 控制器决定Stage、接触/携带状态与ED开关
  → reward能力门控
  → 若ED ON：
       16份噪声 → 5步RDT+RBF
       → [评分 → softmax重采样 → 加噪 → 短去噪+RBF] × 10
       → 末轮最高reward候选
  → 若ED OFF：原生RDT
  → 执行8动作 → 继续观测、复查
```

名义上每个ED块21次批量denoiser调用，176个候选评分；与main一次5步VLS路径的计算安排不同。V17仍有相同的接触预测能力限制，Stage也未完全正确；不能把迁移解读为获得完整物理规划器。

**六、主线性能证据应如何解释**

主线归档的VLS超参报告标明来源是历史工作树commit 360a6d052861，而不是本次新跑的main HEAD。标准libero_object下记录无引导9/10，所列完整guided调参中最好7/10（Stage OFF）；同一最优VLS设置改为Stage ON为6/10，均未达到当时guided≥unguided门槛。部分旧失败来自数值型reward验证问题，而main最后提交随后修了该类型兼容问题，因此更不能把旧分数直接当修复后精确成绩。

根目录也保存6月4日标准Object结果，但缺少绑定精确源码/运行时状态的manifest。当前核查没有给main新增成绩，也没有证据支持“当前main在Object-Swap OOD等于某个固定分数”。

V17的3/10来自Object-Swap OOD，不能与标准Object的9/10或7/10直接比较。历史P2 4/10、V17 3/10以及后续N系列研究结果均未因文件存在于同一仓库目录而成为main的成绩。

[归档超参证据](/home/hynx/lizhuo/VLA-Pilot++/docs/03_evidence/2026-06-03-rdt-libero-vls-hparam-validation.md:19)
 · [V17完整结果](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-gpu6-20260922T063626Z/study_worktree/docs/03_evidence/stage_consistency/2026-09-30-codex-v17-full10-report.md)

**七、对整合方案的直接影响**

整合重点应明确为：

1. 复用main已有的RDT观测、动作、模型加载、末端投影、RBF及旧VLS/FKD能力，避免重复改写。
2. 增加ED搜索路由和冻结参数，并让V17 profile明确选择ED；旧VLS仍可用。
3. 增加Codex三条调用链、结构化Stage控制、C0 reward合同、RNG协议与审计。
4. 补齐准确LIBERO-PRO/模型/环境依赖，消除旧WT路径；把V17未提交代码形成可审阅提交。
5. 通过离线迁移检查和完整在线十任务记录新成绩。

因此，main到V17跨越的是“搜索方法 + 阶段控制 + 在线接入 + 复现实验协议”四部分，无法仅靠更换模型名或调几个参数完成；同时，已有RDT基础链路不需要推倒重做。

