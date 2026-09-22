# TARGET_NOT_MET — RDT QD-ED autoresearch 负结果

研究 `rdt-qd-ed-final-20260921T093925Z`；收尾时间 2026-09-22T12:20:20.701128+00:00；专用分支 `exp/rdt-qd-ed-final-20260921T093925Z`。最新实际执行源代码为 `2435f86f601fa97070f6697670b29063078e91ac`；每次运行的准确commit、命令及产物在下列逐次索引保留。收尾文档版本由本分支最终提交标识。

**目标未达，没有最佳有效候选，也没有正式成功算法。** 11次已派发episode尝试中，有效outcome为0；N1候选本身在线评估为0。Validation和Formal均未开始，不能写成0/10或用历史结果代替。N1的算法效果仍为Unknown。

## 停止依据

原N1比较中，一个Q0/task0对照最终不可重试无效，无法满足20个原定对照全部有效后才派发候选的门槛。同一N1科学cell已派发4次（含3次recovery），补齐其余29格至少需要33次，超过冻结的30次上限；失败和中止也计数。因此关闭为`INVALID_NOT_PROMOTABLE`，不重分类、不换名重开、不回填。依据：[候选协议](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/experiments/iteration_001_execution_intent/protocol.md)、[对照前置修订](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/experiments/iteration_001_execution_intent/startup-repair-amendment.md)。

有界定向复查仅发现“执行视界感知的QD质量使用”这一待诊断方向，缺少原始精度的起始EEF/t8Z、真实quality重建、实际选择变化及下一合法观测进展关联。17/220仅为最近目标XY候选argmin差异，不是实际quality排序错误。H1/H4/H5的几何、lineage或激活改善也没有建立任务收益。现有证据不足以升级新的主要机制，按[用户停止规则](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/docs/01_specs/2026-09-21-rdt-qd-ed-autoresearch-execution-prompt.md:163)及[负结果交付要求](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/docs/01_specs/2026-09-21-rdt-qd-ed-autoresearch-execution-prompt.md:259)作`CONCLUDE_TARGET_NOT_MET`决定。[历史诊断](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/docs/03_evidence/qd_ed_final/historical-diagnosis.md)与[N1分析](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/experiments/iteration_001_execution_intent/analysis.md)保留证据边界。**预算没有耗尽；这是协议和证据决定的停止，不是5/10成功验收。**

## 结果与分母

| 比较 | 派发情况 | 状态 | 有效SR、同轮gained/lost |
|---|---|---|---|
| 原baseline：Q0×10、C0/P2×10 | Q0/task0一次无效；19格未派发 | CLOSED_INCOMPLETE_INVALID | Unknown |
| N1同轮：Q0×10、C0/P2×10、N1×10 | 一个Q0格4次尝试；29格未派发 | INVALID_NOT_PROMOTABLE；N1效果Unknown | Unknown |
| 独立C0工程诊断 | 6次episode尝试：5aborted、1invalid | 不用于补N1对照或候选样本 | Unknown |
| Validation / Formal | 0 / 0 | 未暴露、未执行 | 未测量 |

[50个原定cells及task/seed/init状态](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/docs/03_evidence/qd_ed_final/final-planned-cells.csv)、[11次逐次尝试](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/docs/03_evidence/qd_ed_final/final-attempts.csv)、[20次GPU健康/工程诊断](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/docs/03_evidence/qd_ed_final/final-gpu-diagnostics.csv)分开报告。账本`event: valid`是历史会计标签；科学有效性以`outcome_valid:true`为准。本轮0有效、3invalid、8aborted，不能换算为候选0/10。

历史Q0为2/10（任务5、8），其同轮P2为3/10（任务3、8、9）；历史Q0 gained5、lost3/9。另一轮P2恢复4/10不与3/10合并。它们是已暴露历史背景，均不是本轮有效候选或新泛化证据。

## GPU3诊断

后续由本协调器派发的诊断固定在物理GPU3，UUID `GPU-62052fa1-37e0-79dc-21aa-5c0f25c0c315`、PCI `0000:61:00.0`，进程内CUDA0/EGL0，不自动换卡。此前GPU7/5/6及另一会话GPU2记录按实际设备保留；带GPU5标签的memcheck实际在GPU2，不能改为GPU3。未终止外部研究进程。

| GPU3主要诊断 | 计费秒数 | 结论 |
|---|---:|---|
| [静态场景](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/gpu3-static-scene-diagnostic/rdt-qd-ed-final-20260921T093925Z__gpu3_static_scene__b8f0b3b6214f/healthcheck-result.json) | 10.328 | 12帧有效；零动作 |
| [先场景后模型](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/gpu3-scene-model-diagnostic/diagnostic-analysis.json) | 73.727 | 加载后首帧故障，尚未B1 |
| [分段加载](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/gpu3-model-load-phases-diagnostic/diagnostic-analysis.json) | 42.836 | CUDA初始化/seed后深度非有限，尚未加载权重 |
| [CUDA先初始化](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/gpu3-cuda-first-diagnostic/diagnostic-analysis.json) | 82.972 | T5加载后深度非有限 |
| [渲染独立线程](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/gpu3-render-thread-diagnostic/diagnostic-analysis.json) | 72.352 | 模型加载后Xid31 |
| [模型/渲染分进程](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/gpu3-render-process-diagnostic/diagnostic-analysis.json) | 72.529 | 渲染进程Xid31，无post-load render_exit |
| [无模型等待75秒](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/gpu3-render-idle-diagnostic/rdt-qd-ed-final-20260921T093925Z__gpu3_render_idle__8d9503386162/healthcheck-result.json) | 82.932 | 10帧有效，图像与静态参考一致 |
| [完整模型先于场景](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/gpu3-model-first-diagnostic/diagnostic-analysis.json) | 73.690 | 原B1有效；其后首帧非有限+Xid31 |
| [B1前销毁/后重建整个context](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/gpu3-context-lifetime-diagnostic/diagnostic-analysis.json) | 81.472 | 无Xid、B1一致；首张128图像不一致，判失败 |
| [仅管理原生con/gl_ctx](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/gpu3-native-render-lifetime-diagnostic/diagnostic-analysis.json) | 6.335 | 模型加载前第2张受管wrist图像不一致，判失败 |

这些静态探针没有执行机器人动作或积分步骤，不属于任务成功率样本。最后一轮仅6帧、0模型加载、0B1；第一次重建原生资源后wrist128图像不一致，4份原始数组保留在[结果目录](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/gpu3-native-render-lifetime-diagnostic/rdt-qd-ed-final-20260921T093925Z__gpu3_native_render_lifetime__72a4dc721056/frames)。图像门槛未放宽，所有诊断原型均未作为生产修复应用。

完整context重建额外调用一次mj_forward；仅重建原生资源虽避免了额外forward，仍在加载模型前改变图像。故障根因未确定，不能据此宣布硬件、驱动或库版本有确定缺陷。完整DINO、640深度/分割、guided C0、动作/reset及生产异步调度尚未通过共同条件验证。收尾时GPU3空闲、无本任务GPU worker。

## 方法、代码与检查

唯一候选N1是固定16格的“t8目标距离×8动作正夹爪指令占比”描述符，保留原quality、sparse父代分配、ED与最终reward-best选择。完整伪代码、archive更新/replacement、parent allocation、ED、final selection、reset、源码位置与证据限制见[方法记录](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/docs/03_evidence/qd_ed_final/final-n1-method.md)。[候选配置](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/configs/qd_ed_final/candidate_n1.json)SHA256为`5e74d72f108df53897e790677154c5ca3691b1aeb318297168d3bffcb84bfe3c`，不是正式成功版本。

既有N1实施记录为417项CPU/stub检查及2项有重叠计数检查，不相加或当作当前在线验证。最近native-lifetime helper17项、诊断入口3项CPU检查通过，但GPU图像门槛失败。Stage变量覆盖、Codex接口/遥测、observer生命周期等既有工程修复分别记录，不能将修复收益归于QD。未合并main、推送或发布。

## 成本与余额

| 项目 | 已用 | 上限 / 余额 |
|---|---:|---|
| GPU小时，含初始化/终止/清理 | 1.026259112326 | 48 / 余46.973740887674 |
| episode attempts | 11 | 240 / 余229 |
| baseline桶 | 1 | 原cohort关闭；余19不转移 |
| development桶 | 5 | 100 / 余95 |
| recovery桶 | 5 | 20 / episode额度余15 |
| validation / formal | 0 / 0 | 60 / 40；14h / 10h仍保护 |

20个GPU健康检查的0.236900145772小时已包含在总计和recovery时长中，不能再相加，也不算20个科学episode。扣除24h保留后，其他工作账面余额约22.973740888h；这不能解除N1自己的30次门槛。[机器可读总成本](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/final_delivery/accounting.json)由追加式账本汇总。

组件全研究总成本、完整tokens/失败次数/延迟、货币费用仍Unknown。仅1/11个完整episode计数窗口，且以execution_error结束。留存记录提供至少10次已完成fresh-policy调用及36.9021秒延迟小计；Stage留存1次逻辑调用，10800输入/42输出token、19.7721秒。缺失窗口不填零，Codex HTTP请求/重试次数不可见。详见[成本审计](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/docs/03_evidence/qd_ed_final/final-cost-telemetry.md)和[逐项证据JSON](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/debug-tools/final-cost-telemetry.json)；这些小计不含独立健康检查、CLI探针或代理工作，重叠计时不可相加，不支持成本/成功率比较。

## 冻结身份、复现和下一研究需要

保持RDT Object EMA、T5/SigLIP/DINO、LIBERO object-swap strict任务、initrow0、720-step上限、20Hz、8-action执行及原Stage/cache/perception/prompt条件。缓存身份、Stage配置和provider迁移等工程修订单独标记。Stage条件为`codex_login_astra_low_v1`，使用已登录Codex CLI；Poe配置/凭据保留，报告不复制凭据。

- [种子计划](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/data/frozen-seed-plan.json)SHA256：`9bbcf7107f6be4f739870a034ea84c4695819bdc1bffe5aa1148f453acf4a6b1`。
- [模型清单](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/data/runtime-inventory.json)SHA256：`44d456203ca168eec9eddfb6834d54347153b2c859eb1b4fc0dea02c15138b83`。
- [GPU3 runtime](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/gpu3-render-diagnostic/runtime-manifest.json)SHA256：`2118d25a2e91c170c2842aec7ef11159df6c15a314d1a28153779722f22aea8e`。本机驱动核对为580.65.06，这不是根因结论。
- [episode账本](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/data/attempt-ledger.jsonl)、[GPU账本](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/data/gpu-healthcheck-ledger.jsonl)及每次输出目录的command.json/process.json/结果、原Hydra配置、部分episode视频/metrics均保留。逐次CSV给出完整原命令与结果路径；部分视频不等于完成episode。
- [暴露登记](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/data/exposure-registry.jsonl)保留54条历史记录，追加一个本轮保守Dev task0/seed/init身份及11次尝试引用。冻结historical inventory及其hash不变；新seed不证明新布局。Validation/Formal没有新增结果。

复现应按逐次CSV取当时准确commit、命令与contract，不能拿最终文档HEAD代替实际执行源码。每个探针都有脚本/监督器/依赖SHA。原失败ID和关闭队列不能直接重跑来替代本结果；CPU检查命令与方法分析可独立审阅。

继续首先需要保持图像/物理/动作语义的完整执行条件，以及原始精度quality、实际选择变化、下一合法观测进展证据。只有这些支持一个新的具体机制，才能另行冻结预算、完整同轮对照和候选协议。相同N1的新比较涉及明确改变研究设计，不能自动恢复旧cohort。未执行候选的真实反事实成功仍Unknown，额外分支仿真未获本次自动执行授权。

权威记录为[research-state.yaml](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/research-state.yaml)与[统一总账](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/docs/03_evidence/qd_ed_final/iteration-ledger.md)。不提供主线采用候选、formal成功视频或统计优势声明；最终结论为**TARGET_NOT_MET / NO_ADOPTION**。
