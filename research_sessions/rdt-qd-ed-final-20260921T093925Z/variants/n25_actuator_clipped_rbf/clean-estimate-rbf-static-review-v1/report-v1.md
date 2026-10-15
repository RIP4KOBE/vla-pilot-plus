# Clean-estimate RBF 静态审阅

结论：**同一次已有 denoiser forward 的 clean-action estimate 在静态配置链中确实可得；当前 RBF 尚未使用它作为几何输入。这是不同于旧 clean-tail 的可检验机制缺口，但不是已证明的工程 bug 或收益来源。** 可保留“输出坐标中的 stop-gradient 几何更新”这一待审假设；本报告没有实现、注册或释放候选，也未读取当前 Dev 结果。

## 数据流证据

使用12个源/配置文件、3个闭合叙述，完整路径和SHA在 source-index-v2.json。I为冻结5a65ef的N25/implementation；W只读了根明确授权的两个第三方源文件。没有导入模型或scheduler。

| 核验项 | 具体证据与结论 |
|---|---|
| 类型与步数 | [checkpoint config](/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object/config.json:32)为 sample、5 inference steps、1000 train steps。根的存在性/stat检查确认它是[loader搜索](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n25_actuator_clipped_rbf/implementation/core/rdt_policy_steer.py:1130)第一命中；flat conversion在540行原样传递noise_scheduler。日志中写死的sample字符串不是证明。 |
| 实际采样类 | [RDTRunner](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree/third_party/rdt/models/rdt_runner.py:59)训练用DDPMScheduler，采样用DPMSolverMultistepScheduler；后者只传训练步数、beta schedule、prediction_type。[安装源码默认值](/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/diffusers/schedulers/scheduling_dpmsolver_multistep.py:212)为solver_order=2、dpmsolver++、midpoint、thresholding=False。config的type=ddpm不能据此把采样误称DDPM。 |
| 输出含义 | [训练目标](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree/third_party/rdt/models/rdt_runner.py:210)的sample分支target=action_gt；[DPM转换](/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/diffusers/schedulers/scheduling_dpmsolver_multistep.py:672)直接x0_pred=model_output；[适配器](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n25_actuator_clipped_rbf/implementation/core/rdt_policy_steer.py:775)返回同一模型输出。noise_pred变量名/注释不改变语义。 |
| 初始时序 | [初始循环](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n25_actuator_clipped_rbf/implementation/core/rdt_policy_steer.py:2984)：no_grad forward → 对noisy population算RBF → 修改model_output → scheduler.step。start_ratio=.8及[阈值算法](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n25_actuator_clipped_rbf/implementation/core/rdt_policy_steer.py:7911)在5步下激活前4步，不是最后20%。 |
| Rollout时序 | [rollout](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n25_actuator_clipped_rbf/implementation/core/rdt_policy_steer.py:3858)同样先forward，再把noisy x_t交给RBF、改model_output、step。N25 profile为all/scale20/.6/skip0；[mask](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n25_actuator_clipped_rbf/implementation/core/rdt_policy_steer.py:3695)激活每轮前ceil(.6n)步。10轮n=[3,2,2,2,2,1,1,1,1,1]，对应RBF=[2,2,2,2,2,1,1,1,1,1]。 |
| 梯度和应用 | [helper](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n25_actuator_clipped_rbf/implementation/core/qd_actuator_clipped_rbf.py:59)把输入detach后建叶子，前8步平移clip/投影→inverse-distance potential→整批global norm归一化。[应用](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n25_actuator_clipped_rbf/implementation/core/rdt_policy_steer.py:3033)负号、scale20、仅39:42平移，修改的是model_output。 |
| scheduler传播 | [step](/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/diffusers/schedulers/scheduling_dpmsolver_multistep.py:1093)转换并保存已修改输出的历史，以一/二阶公式推进sample，最后转回输出dtype；只返回prev_sample。x0 estimate、更新后的model_output、prev_sample与最终执行动作是不同量。 |

这是冻结源/配置的静态解析；运行实例scheduler属性、实际timesteps和张量值在本范围内仍Unknown。该边界不妨碍确认代码的输入/更新坐标域不同。

## 可自洽的梯度定义

令同次预测为 y₀=fθ(xₜ,t,c)，P为原8步平移clip/投影，E为原inverse-distance potential。sample模式可以把stop-gradient(y₀)作为独立输出叶子u，求g₀=∂E(P(u))/∂u，然后按原mask/归一化/负号更新y₀，并交给原scheduler.step。梯度图只包含clip→投影→potential，不含模型，因此不需额外forward、模型反传、训练或仿真。

这不是完整的∂E(P(fθ(xₜ)))/∂xₜ。若把sample输出detach后仍要求对xₜ求导，梯度就是0；加straight-through identity或恢复模型Jacobian是另一干预，不能暗中加入。epsilon模式的x̂₀=(xₜ−σₜε)/αₜ对输出有−σₜ/αₜ Jacobian，符号/尺度不同；当前sample模式不应套这个系数。

保持时点后，名义每个完整guided search仍为初始5+rollout16=21次denoiser forward，4+15=19次RBF。176候选/11评分批是另一个分母，不是模型调用数。替换RBF输入可保持这些次数及每次16行投影，但clone/证据开销与实际wall time仍须计量，不能宣称耗时相同。

## 是否重复旧探索

[闭合clean-tail报告](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n25_actuator_clipped_rbf/implementation/docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-03-p2-rollout-clean-tail-parameter-sweep-report.md:9)只把skip_final_steps从0改1，没有把几何输入换成model_output。报告记录winner2/10→clean-tail0/10，90%短rollout迭代失去RBF，幅度/分散度一并收缩。这反对“更平滑自然更好”，没有直接检验本输入域变化；其结果也不是当前协议的匹配证据。

[已有FKD x0选择](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n25_actuator_clipped_rbf/implementation/core/rdt_policy_steer.py:1810)用于VLS奖励/重采样；同路径1953行RBF仍读x_t，当前N25则走EDS。12源/3叙述内未见等价实现，不声称穷尽全部历史。N25本身改变clip几何，仍未改变noisy输入域。

## 必须保留的限制

* clean预测是模型估计，不保证更正确或更可执行；原0.01累计投影也不是实际运动。目标/抓取/成功均不能从投影改善推出。
* 原N25自定义clip导数在±1及外侧为0；coincident/全饱和预测可产生合法零梯度。未读实际张量，不能承诺clean域更少饱和或更活跃。
* global normalization可把固定norm20集中在更少坐标；局部负梯度不保证有限20步长降低potential。BF16、stride、cumsum/norm归约和精确边界都需另行数值验证，不能顺便改dtype或容差。
* [DPM++一阶](/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/diffusers/schedulers/scheduling_dpmsolver_multistep.py:772)/[二阶](/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/diffusers/schedulers/scheduling_dpmsolver_multistep.py:850)把输出变化与sample及历史一起传播。scheduler会把sample上转FP32，但RBF/模型输出仍有native dtype边界。operand不是实测加法delta，更不是执行EEF位移。
* 当前witness的input_xyz语义为noisy输入；未来若换输入，证据语义/独立审计须明确改版，旧证明不能冒充新算法证明。本次没有读witness。

## 一个可否证假设

同次clean-output几何中，原noisy-input力在部分真实激活调用并非下降方向；把求导坐标换到已有clean输出，可在相同模型/评分次数下消除这种局部失配。明确判别量为非零g₀与原gₜ的内积：若g₀ᵀgₜ≤0，原负向更新在clean potential上是非下降方向；若所有可测调用都方向一致且效果相同，或clean域梯度恒零，该具体机制解释应被削弱/否决。这不是有效性或成功率阈值，也未实际计算。

唯一缺少的调用域事实是：真实激活时noisy输入与同次未修改clean输出的梯度方向/零梯度关系。静态可行性足以提出有限机制检验，不足以声称任务收益；即使proxy改善，仍须另行冻结匹配任务实验。没有给当前N25运行追加任何规则。

范围记录：首次文件名定位过宽，列出部分旧worktree/fixture名称，未读其内容；随后只用精确清单。未运行测试、Torch导入、模型、API、网络、GPU或仿真，未改科学源、计划、预算、状态或树。
