# RDT steering 架构与算法合同

**状态：EDS 迁移验收待结案；三模式公共接口尚未完成。** 本文区分当前实现与待实施设计，不给未评测的方法填写成绩。入口与证据索引见 [README](../../README.md)。

## 共享链路与执行边界

一次动作块的链路是：观测 → Stage 更新与 guidance 开关 → RDT 条件编码 → 候选生成/选择 → 动作转换 → 顺序执行。公共方法只使用 VLS、EDS、EDS+QD 三个名称。内部可保留两个采样路由 `guidance_type=vls/eds`，以 `qd_archive_mode` 控制 EDS 的 archive；不需要复制第三套引擎。

| 组件 | 实际职责 |
| --- | --- |
| `scripts/steering_runtime.py`、`run_steering.py`、`steering_worker.py` | 合成科学配置与机器配置；冻结源码/配置；设置导入、CUDA/EGL/Hydra 环境；安装 RNG hooks；启动及审计 |
| `main.py` | episode/动作块执行；每个新动作块前更新 Stage，再采样；记录 raw 与 executed 动作 |
| `core/rdt_policy_steer.py` | 共享 RDT 编码、VLS/EDS、轨迹投影、评分、候选选择和动作缓存 |
| `core/stage_evidence.py`、`stage_contact_handoff.py` | 视觉与 reward 能力判定、接触交接、guidance/reference 生命周期 |
| `core/target_distance_reward.py`、`vlm_query/target_distance/` | 新生成 reward 的数值合同与固定提示词 |
| `core/stage_capture.py`、Codex transport | 图像/提示词/模型回复捕获，合法事件生命周期及请求元数据 |
| `core/episode_rng_hooks.py` | 在规定的 preparation/rollout 边界恢复初始化 RNG 状态 |

RDT latent 是 `[B,64,128]`，使用当前图像、机器人状态和文本条件。执行只解码前 **8** 个 7D 动作，控制频率 20 Hz；夹爪二值化与动作后处理属于算法语义。多样性/reward 梯度只允许修改这 8 步的平移槽位。当前配置关闭外部抓取动作覆盖。

## EDS：评分与多样性采样

每个 **guided** 动作块重新生成 16 个候选。完整初始去噪并评分后，执行 10 轮“按已有分数选父代 → 重新加噪 → 截断去噪 → 对新候选评分”；每轮复用前一批分数，不重复计算它。未开启 CEM 拟合；配置里的 `cem_iters` 是迭代次数，不能由名称推断启用了 CEM。

| 固定项 | 当前 EDS 设置 |
| --- | --- |
| population / rounds / elites | 16 / 10 / 16；`use_cem=false` |
| 初始采样 | `rbf_diverse_denoise`，`absolute_eef`，scale=20，start ratio=0.8 |
| 每轮截断采样 | `rbf_diverse`，同一 descriptor，scale=20，start ratio=0.6，所有 10 轮 |
| 父代权重 | `legacy_temperature`，temperature=0.1；无覆盖锚点、无精英直通 |
| 噪声深度 | `linspace(3,1,10).astype(int)` = `[3,2,2,2,2,1,1,1,1,1]` |
| 动作块间记忆 | fresh；没有 warm start |
| QD | `none`；metrics observer 只观察 |

checkpoint 的 `noise_scheduler.num_inference_timesteps=5`，当前配置不覆盖它，因此初始去噪是 **5 步**。不要把训练扩散 1000 步、latent 长度 64 或其他 policy 配置的步数当作这里的推理步数。

初始 start ratio=0.8 转成 `timesteps[floor(5×0.8)]`，只在严格大于该 timestep 时施加 RBF，因此当前五步 schedule 的前四步生效。截断采样的 ratio 是另一种判定：某轮长度 n 的前 `ceil(0.6n)` 步生效；不是“等最后 60% 才开始”。

设候选 j 的 reward 为 r_j、cost 为 c_j=-r_j，父代概率为：

\[
w_j=\operatorname{softmax}(0.1r_j)=\operatorname{softmax}(-0.1c_j).
\]

实现先在 float64 算 logits/softmax，再转 float32 并重新归一化。**这里 temperature 是乘数，不是除数。** 父代有放回抽样，随后使用独立 `randn_like` 噪声，在完整 scheduler 的 `timesteps[-n]` 加噪，再走其最后 n 步。不要将之替换成高斯拟合、除温度、固定父代或新的噪声 schedule。

普通 EDS 最终选择第 10 轮当前 population 的最高 reward 候选；没有默认保留所有轮次全局最好候选。初始评分加每轮后评分共有 11 批、176 个候选评分。完整运行的额外 reward 调用、可视化与诊断开销仍应以计算日志为准。

### 实际“RBF”与轨迹投影

`LiberoAdapter.delta_actions_to_ee_trajectory` 使用当前实测末端位置 p_0，将候选平移量线性累计：

\[
p_h=p_0+0.01\sum_{t=0}^{h-1}a_{t,xyz},\quad h=1,\dots,8.
\]

这是可微近似投影，不是对每个候选执行 MuJoCo 环境分支，也不是完整机械臂前向运动学/碰撞/接触预测。代码里的截断 rollout 指截断扩散去噪。真正仿真执行发生在选定候选之后。

将每条轨迹的 p_1…p_8 展平为 z_i，当前 `absolute_eef` 多样性势函数是：

\[
U=\sum_{i\ne j}\frac{1}{\sqrt{\|z_i-z_j\|^2+10^{-6}}+10^{-6}}.
\]

实现对整个 batch 的 `∇latent U` 做全局范数归一化（分母加 10^-8），再遮罩到前 8 步平移槽位，以 `model_output -= 20×masked_gradient` 注入去噪输出。它是逆距离势，不是 Gaussian RBF。EDS 不需要 reward 对动作求梯度，但此多样性项仍使用自动微分；不能把整个 EDS 描述为完全无梯度。

### Reward 的时间片与数值合同

投影产生 p_0…p_8 共 9 点。EDS 评分和 VLS 最终候选/FKD 评分使用 **p_1…p_7**；多样性使用 p_1…p_8；VLS 内部 reward 梯度使用 p_0…p_7。这个切片差别是当前实现，不在接口清理时顺手修正。

Stage 1 为目标距离：对传入的 L 个点，前 `floor(0.7L)` 个点权重 1，其余权重 3，再归一化。单候选：

\[
r=-\sum_{h=0}^{L-1}\bar w_h\|p_h-q\|_2^2.
\]

这里 p 是已经切片的轨迹，q 是指定目标关键点。合同实现先 `norm` 再 `square`，时间权重使用 float32；尤其 bfloat16 下，不可将其改写成另一运算顺序并声称逐值等价。Stage 2 返回常数 0，当前控制器将其视为没有可用引导信号并关闭 guidance。有限探针验证可发现已知公式漂移，不是对生成程序所有输入的数学证明。

## VLS：保留内部梯度参考

VLS 在一个去噪过程的高噪声区间使用多样性项，后续使用 reward 对轨迹/latent 的梯度，且可按 FKD 势函数重采样粒子。普通路径按最终候选 reward 选择；单候选或 FKD terminal 路径有自己的直接返回条件。

内部引导 scale 随内部归一化 reward g 与噪声变化：

\[
s=\frac{\text{guide_scale}}{1+\exp(k(g-x_0))}\sqrt{1-\bar\alpha_t}.
\]

当前配置含 20 粒子、diversity_scale=10、k=25、x_0=0.75，以及 FKD 参数。注意 YAML 的 guide_scale=40 可能被 LIBERO adapter 的逐任务值 80 覆盖；待接入方案应显式固定有效值 80 及逐任务表，不能只抄表面值。这些是**待验收的公共 VLS 配方**。本 RDT 循环读取 `MCMC_steps=4`，但没有据此执行四次 Langevin/MCMC 内循环。不要把其他策略实现或未使用参数计算进预算。

VLS 与 EDS 的粒子数、重复去噪、reward 梯度、RBF、FKD/父代抽样成本不同。对照同时报告任务成功率、实际 DiT batch rows/calls、reward 调用、梯度次数、延迟和服务调用；如需等计算预算，另立明确实验条件。

## EDS+QD：动作块内的 archive

**公共 profile 与性能评测待完成。** 现有引擎可通过 `guidance_type=eds` + `qd_archive_mode=grid_archive` 激活 archive，共用初始采样、reward 和截断去噪。

最小计划采用已有目标相对末端 XY 描述符、4×4 网格、每格容量 1、初始固定边界、`sparse_priority` 父代分配、稳定 fingerprint tie-break。格权重为 `(累计候选访问数+1)^(-1)`；按权重分配16个槽位，整数余数平手使用局部 RNG，访问数包括未入档候选。当前 EDS 关闭的 archive 配置里出现 `uniform_cells`，不能据此推断待接入 QD 的正式方案。边界来自初始候选 5%/95% 分位数，扩张 10%，每轴最小跨度 0.08m，越界 clamp 到边格。配置/profile 尚须正式冻结，不能以本段替代解析后配置。

archive 在一个 guided 动作块中创建，接收初始 population 与 10 轮结果，保留各格高质量候选，并影响父代选择；最终从 archive 选全局最好。它可以保留早期轮次候选，这和普通 EDS 的最终 population 选择不同。当前 fresh 模式下，每个新动作块重新开始；没有跨任务 archive、在线模型训练或递归自我改进。

`qd_metrics_observer=true` 可以在普通 EDS 中产生 shadow 指标，**不证明 archive 已参与搜索**。验收需同时证明 active flag、176 次评价/11 批评分、cell 更新、父代来源和最终选择一致。离线重建记录能核对机制日志；若没有实际父代 tensor 证据，就不能额外宣称已证明执行时 tensor 重采样。未来 QD 优化与长期记忆应分开命名配置和验收。

## Stage 进度与接触门控

Stage 在新动作块采样前读取上一 guided 块的 reward 进度。当前 EDS 已记录最终选中候选 r，首个有效 selected reward 为 reference r_0：

\[
g=\operatorname{clip}(1-r/r_0,0,1.2)\text{，若 }r_0<-10^{-6};\quad g=0\text{ otherwise}.
\]

它参与接触交接：fresh guided progress≥0.8、实测目标距离≤0.10m、接近至少16步，可开启64步 contact grace。单独 proximity 触发当前关闭。不能因为某个视觉事件字段写着 reward 未用于基础视觉判定，就断言整个在线控制器不消费 reward。

语义 Stage 改变会重建 reference；同 Stage 的 guidance 关闭/恢复保留 reference。先前 unguided 块不应把陈旧进度重新送入交接。接触、携带、释放与失败接触复查共同控制 guidance；最终成功以环境结果为准，不由 reward 高或视觉回复直接替代。

视觉查询最小间隔16步、常规复查32步、最多50次；完成证据需要间隔至少16步的两次明确视觉判断。unknown/遮挡不自动等于成功。失败接触恢复结合可见的篮外支撑/未持物证据与实测夹爪状态，不覆盖策略动作。

### 待实施的统一外层接口

计划新增纯读取 `get_stage_reward()`，并让 `stage_evidence.update_stage` 优先使用它。对 EDS，它必须直接返回已有值，不能重新评分、改 dtype、写 reference、调用 RNG 或增加计数。

对 VLS，建立独立的**最终选中候选** score/reference，复用已有最终选择评分；单候选/FKD 直接返回路径若增加一次评分，要明确计数。内部梯度 reward/reference 与 scale 计算保持原样。无法评分不能退回内部梯度 reward 伪装为外层进度。

reward 的可评分能力继续供 EDS 使用；只对 VLS 增加有限、连通且在至少一个非最优探针非零的梯度检查。最优点的零梯度合法。接口与检查均待完整 EDS gate 通过后实施、做闭环 parity，再开放公共模式。

## 感知、初始化与证据限制

当前系统依赖仿真提供的机器人/末端状态、目标/关键点跟踪与几何测量，且 Stage 图像包含投影标记。它不是仅凭原始 RGB 的零真值部署方案，也没有在真实机器人上验证。几何近似 reward 不表达完整抓持、碰撞、支撑或放置稳定性。

20 个 RNG 状态文件只定义 10 个任务 preparation 与 rollout 两个时点的 Python/NumPy/Torch 初始化；不包含历史动作、reward、模型回复或环境回放。SHA 校验确认文件身份，运行 hook 才确认生效时点。普通固定 seed 不能直接替换该协议。

基础 run 审计核对 cohort 完整性与机制字段；更细的 prompt/image/code/marker/transport/动作一致性离线审计已在独立 CPU 草案验证，**仍待合入 runtime 工具链**。测试可使用裁剪的真实捕获 fixture，但合成的结束 receipt 只是测试输入，不能作为在线任务成绩。日志中的请求模型标记、CPU 合同探针和视频均有各自证明范围，不是服务端模型、视觉真值或所有执行路径的完全证明。
