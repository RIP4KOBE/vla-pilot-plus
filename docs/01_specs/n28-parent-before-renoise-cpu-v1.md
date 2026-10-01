# N28：父代变异后再加噪、去噪（事前假设）

状态：登记一个候选，仅授权 CPU 实现准备；GPU 计划与预算尚未放行。来源 e21d48ab33dbd3aca017349b6004c2ba7d981493。所有产物留在本目录。

## 依据和目标失败行为

N26 与 N27 的匹配 Dev 未改善任务。N27 完整四任务筛选中 C0/Q0/N26/N27 均0/4，更新处的受限赋值确实活跃，但不能证明最终动作有用。task0 首个引导决策的固定 schedule 显示，10轮 rollout 中9轮在末次模型 forward 后仍直接修改 model_output。

旧 skip_final=1 已有负结果，且大部分单步 rollout 完全失去变异；本候选不会重试该参数。新的有限 CPU 父代检查完整覆盖同一个已暴露决策的10轮：每16槽只有6–8个独特父代，但160/160槽均有非零参考赋值变化，3736/3840分量在严格内部。它排除这个有限 CPU 域上的“新算子完全不活跃”反驳；CUDA行为、去噪后的传递及任务收益仍 Unknown。

依据：../n27_feasible_ray_update/hydra-continuation-v1/root-terminal-review-v1.json；../n27_feasible_ray_update/conditional-operator-placement-review-v1/review-v1.md；../n27_feasible_ray_update/parent-domain-cpu-audit-v1/root-review-v1.json。

## 唯一主要改动

在每一轮 QD parent allocation 已产生原有 offspring 后、原有 renoise 之前，对这一实际父代副本执行一次 clipped-EEF 几何的负梯度、原全局归一化/scale20、逐粒子 feasible-ray 赋值。随后执行完全相同的原噪声抽样和所有 RDT denoising/scheduler 步；这一候选的 rollout model_output 不再附加 RBF 变异。

初始 population 路径保留 N27 的原4次变异；QD descriptor、quality、archive、parent allocation、final selection、Stage、reward、动作语义、执行长度、模型和数据全部保持 N27。无跨 chunk memory、无新噪声/抖动、无新 scale、无额外模型或评分调用。重复组不能靠隐式噪声被拆开；原 renoise 噪声仍按原位置和次数抽样。

新输入语义必须叫 current-chunk selected parent offspring；不得伪标为 same_forward_unmodified_model_output。父代可能来自本 chunk 较早 archive，不保证已在[-1,1]或在真实可行流形。可行射线只保持本次变异的严格内部支持和未改坐标，并不保证去噪后/执行时的边界或安全。

这是一次 proposal operator 的替换，输入对象、位置与 RBF 调用数共同变化，不能称纯时序单因素或同总算力：rollout RBF 15→10，initial4不变，总19→14；原模型 denoise schedule、噪声次数和完整 guided chunk 176候选/11评分批次不变，实际成本另报。

## 可证伪预测、比较和终止

机制预测：真实父代变异应有可核对的输入→赋值→原 renoise→原 denoise 链，并保持默认关闭路径、RNG、尾部/非xyz动作和计算契约。合法零梯度如实计入，不成为工程 invalid，也不靠挑案例或加抖动补救。单路径 parent→final 差异不能证明变异传递；不额外调用模型作反事实，不运行额外仿真分支。传递归因仍 Unknown，匹配任务结果决定晋级。

计划比较 C0、Q0、N27（移除本轮改动）、N28，沿原冻结 Dev 的 task0..3、原 task-seed-init 映射及 task-major 顺序，共16格，禁止按历史成功挑任务。完整筛选后 N28>=2/4、>=C0/Q0、严格>N27，且QD/ED实质活跃，才可另行冻结完整Dev；否则 REJECT_SCREEN。错误停止，保留全部消耗；未授权自动 retry。此处不允许运行GPU矩阵，不修改已有协议门槛。

模型调用、reward/VLM调用、RBF/投影次数、latency和episode GPU-hours必须完整报告。若机制活跃但任务无收益，拒绝候选；不再仅以 spread、可行性或非零变异为理由继续同轴扫参。验证/正式集保持关闭，所有已有结果不变。

## 当前 CPU 实现范围

独立 worktree：本目录 implementation；分支 codex/n28-parent-before-renoise-20261001，基于 e21d48a。只实现最小算子、默认关闭的配置及主循环接线、真实语义的有限 trace/witness、相关必要 CPU 单测和实际 Hydra 配置组合检查。无需新 GPU controller、预算 gate、native GPU proof 或线上注册；这些待 root 实现审查后分别处理。

测试重点：原路径关闭时不改变行为/调用数/RNG；父代变异恰好在原 renoise 前每轮一次；原 denoiser 调用/顺序保持、rollout 后无重复变异；合法重复父代/零梯度、边界、BF16/FP32、零operand字节和非xyz/尾部不变；真实候选 override 能被 Hydra 接受。只用有意义的合成输入与 stub 调用链，不启动模型/环境/API，不读取新实验或保护集 payload。

CPU 测试累计≤180 CPU秒，2 CPU affinity/2线程，CUDA隐藏；记录 Torch 内部设备发现探测与实际 CUDA 工作的区别。只允许根据具体失败做必要修复重测，不重复已经通过的未变检查。输出代码提交、diff、测试结果、资源记录和未解决问题供 root 审查。不得直接合入 study_worktree、修改其状态/账本/预算或启动GPU。
