# Research Progress

最近核对：2026-10-16（Asia/Shanghai）。本文概述项目当前能力、证据边界和开发优先级。研究动机与假设见 [Research Proposal](research_proposal.md)，使用方式见 [README](../../README.md)，完整配置、逐任务结果和受测源码身份见对应实验报告。

## 当前状态

VLS、EDS 和 EDS+QD 已进入共享的 RDT 推理与评测框架。**EDS（含 RBF）是当前最可靠的研发对照**：历史两套已验收 ObjectSwap 协议及本轮干净环境复测均取得 3/10。EDS+QD 的档案和父代机制已经运行并通过审计，但尚未证明成功率优势。

当前研究重点是解释行为分区、父代质量与实际操作效果之间的关系，再进行可归因的 QD 改进。跨动作块适应、跨任务学习和 recursive self-improvement 尚未完成验收。

新合作者安装验收已完成：从干净 clone 和新 Python 环境得到 VLS 1/10、EDS 3/10、EDS+QD 0/10；30 个主回合全部有效，没有回合级基础设施错误或未完成任务。安装中发现的 Robosuite 隐式兼容修改现已纳入显式安装与哈希核验。模型仍需维护者提供；本轮公共 LIBERO 下载失败后使用了校验复制路径。覆盖范围见[安装与评测验收报告](../steering/onboarding-validation.md)。

## 目标与实现状态

“已实现”表示存在代码；“已测试”表示有相应检查；“已验收”限定在报告声明的协议、源码和任务范围内。可选接口不自动继承默认配置的成绩。

| Proposal 目标 | 当前状态 | 已有证据 | 尚缺什么 |
| --- | --- | --- | --- |
| 共同 steering 框架 | 已实现、测试并在线验收 | 公共 launcher/worker、三种 profile、完整 cohort 审计 | 新机器仍需固定模型/任务资产 |
| EDS 对照 | 已实现、测试并在线验收 | low、ultra 与新环境 ultra 均 3/10，成功任务均 3、8、9 | 多 seed 稳定性、等计算预算及更广泛泛化 |
| RQ1：动作块内 QD | 已实现、测试、机制与运行有效性已验收 | BD/网格/精英/父代/最终选择日志及独立重建 | 成功率收益：low 1/10、ultra 0/10，不支持优势 |
| RQ2：操作相关 BD | 默认 XY 已验收；执行意图等可选代码存在 | `qd_descriptor`、`execution_intent_descriptor`、相关 CPU 测试 | 默认以外配置在共同协议的有效完整对照 |
| RQ3：质量与多样性平衡 | sparse 父代已验收；其他选项有代码/单测 | `allocate_parent_slots`、全局质量 anchor/secondary 等接口 | 每项独立消融和计算量一致的因果证据 |
| RQ4：跨块执行反馈 | 部分 warm-start/状态接口存在，默认关闭 | `EDSChunkMemory`、`warm_start_mix`，默认 `fresh` | 持久 QD、有效性/过期/反馈更新的完整在线验收 |
| RQ5：MLLM 自动 BD | 研究设想 | Notion 章节标题和 Proposal 路线 | 生成合同、实现与未见任务验证 |
| Recursive self-improving | 尚未证明 | 仅有块内搜索与在线 Stage 闭环 | 跨执行经验带来可重复收益，排除预算/重试/服务混杂 |


## 三种模式

| 模式 | 默认机制 | 已验收范围 |
| --- | --- | --- |
| `vls` | 20 候选；guide=80、diversity=10；5 步去噪，正常 guided 块 1 次 RBF + 4 次 reward 梯度；自适应 FKD 可因 ESS 跳过 | 完整 online 十任务；实际控制、梯度/FKD与选择证据 |
| `eds` | 16 候选，初始 5 步 + 10 轮截断去噪，reward 父代重采样；RBF scale=20；最终取末代最好 | 完整 online 十任务；独立 EDS reference 与动作/Stage 合同 |
| `eds_qd` | 共用 EDS；4×4 target-relative endpoint XY archive，每格 1 精英，sparse 父代；最终取 archive 全局最好 | 机制真实生效、完整运行、独立档案与父代证据；没有性能优势验收 |

当前 profile 不使用跨块 archive。几何投影不是候选分支仿真；RBF 不是 Gaussian kernel；reward 可评分不等于可用于 VLS 梯度。完整公式和模块边界见[架构合同](../steering/architecture.md)。

## 已验证结果

固定 LIBERO ObjectSwap OOD 十任务，每任务一个规定 seed。下表记录三组独立评测，涉及 low 和 ultra 两套协议；每个方法均完成十任务。

| 在线协议 | VLS | EDS | EDS+QD | 证据 |
| --- | ---: | ---: | ---: | --- |
| Codex / low | 1/10 | 3/10 | 1/10 | [逐任务结果与有效性](../steering/results.md) |
| Codex / ultra | 1/10 | 3/10 | 0/10 | [逐任务结果与对照限制](../steering/reasoning-effort-comparison.md) |
| Codex / ultra，新环境复测 | 1/10 | 3/10 | 0/10 | [安装、逐任务结果与计算量](../steering/onboarding-validation.md) |

当前默认使用 ultra。两套协议还存在传输恢复参数差异，不能把结果差异唯一归因于推理强度。方法计算量也不同；一次十任务评测不证明统计显著性或普遍泛化。

新环境与历史 ultra 的逐任务成功/失败一致：VLS 成功 task 3，EDS 成功 task 3、8、9，EDS+QD 无成功任务。任务编号从 0 开始。它支持安装和运行链路恢复到可验收状态，不证明在线输出或完整轨迹逐字节一致。运行中有按原协议恢复的请求级传输重试；不把回合有效误写为在线服务从未出错。

中断、服务错误、早期迁移、其他 provider 和回复回放实验保存在原报告及[追溯索引](../steering/provenance.md)，不混入上表。后续结果按独立 cohort 追加，保留合法任务失败；基础设施错误和未完成运行单独报告。

## 保留 EDS 对照的条件

| 条件 | 当前协议 |
| --- | --- |
| 模型与依赖 | 固定 RDT EMA、T5、SigLIP、DINO 资产及 steering 安装配方；逐文件校验 |
| 任务与初始化 | ObjectSwap task 0–9、规定 seed、prepare/rollout 两个时点的 RNG fixtures |
| 执行 | 每块执行 8 个动作，仿真控制频率 20 Hz，最多 720 执行步；固定动作与夹爪转换；不代表墙钟实时运行 |
| 搜索 | `configs/steering/eds.yaml`：16 候选、10 轮、RBF、reward 父代重采样，QD 关闭 |
| 在线服务 | Codex CLI / `gpt-6-astra` / `ultra`；固定超时与重试策略，无 provider 回退 |
| Stage / reward | 每任务 fresh 生成内容；当前观测在线 Stage；候选 reward 本地评分 |
| 证据 | 固定受测提交、源码/配置/资产哈希；完整任务记录、捕获、视频和审计 |

精确参数以[公共协议](../../configs/evaluation/libero_object_swap.yaml)、[方法配置](../../configs/steering/eds.yaml)和[架构说明](../steering/architecture.md)为准。资产获取和设备配置见[安装说明](../steering/installation.md)。尚无完整公共模型包；新使用者需要取得匹配资产。固定模型请求名也不能保证在线服务长期输出相同，3/10 是已观察结果而非每次运行的保证。

## 下一步开发

| 优先级 | 对应 RQ | 工作 | 完成标准 |
| --- | --- | --- | --- |
| P0 | 全部 | 维护已验收 EDS 对照，补齐可交付的模型/任务资产获取方式 | 已完成新环境三模式验收；后续资产分发能按清单核验，不依赖维护者隐式路径 |
| P1 | RQ1/RQ3 | 用现有轨迹分析 QD 失败：质量下降、稀疏选择、archive 输出与 Stage 时序 | 可复查的任务/动作块定位；至少一个单变量假设；不再只看 archive occupancy |
| P2 | RQ1/RQ3 | EDS vs 全局精英保留 vs QD；质量锚点/稀疏父代独立消融 | EDS 关闭 QD 的行为回归保持；机制张量与审计一致；完整共同协议在线对照 |
| P3 | RQ2 | 固定 reward/Stage，比较 XY 与执行相关 BD；检查投影/实际动作偏差 | 清楚定义单位、可控性、质量和覆盖；有效多样性及任务指标有证据 |
| P4 | RQ4 | 有状态复用和执行反馈更新 | reset/过期/Stage 边界测试；fresh 与持久版本多 seed 对照，排除额外预算优势 |
| P5 | RQ5 | 受约束自动 BD 与跨任务研究 | 生成合同、独立评测划分、未见任务证据；再讨论递归自我改进 |

单轮 5/10 可以作为阶段信号，不能直接宣称方法稳定优于 3/10。在线服务变化与搜索改动应分开控制；不要在同次实验同时更换 reward、Stage、descriptor 和父代策略。

## 贡献入口

| 要改什么 | 入口 | 最小验证方向 |
| --- | --- | --- |
| BD、cell、精英、父代 | `core/qd_ed.py`、`configs/steering/eds_qd.yaml` | 有限值/边界/平手/分配守恒、实际父代和最终输出 |
| 搜索接入 | `core/rdt_policy_steer.py` | EDS reference 不变；QD 分支实际使用档案，评分/RNG/调用数可审计 |
| 执行反馈 | `main.py`、`core/env_adapters/libero_adapter.py`、`core/eds_eval_metrics.py` | 区分预测与实测；动作后处理、时序、reset 和观测权限 |
| Stage/reward（另立科学条件） | `core/stage/controller.py`、`target_distance_reward.py`、`vlm_query/target_distance/` | 门控/失败复查/评分能力一致；新协议在线验收 |
| 评测/归档 | `scripts/run_steering.py`、`steering_runtime.py`、`audit_steering.py`、`steering_archive.py` | 配置冻结、进程所有权、无效运行区分、搬迁后只读重审 |


新贡献从 main 派生功能分支，保留 EDS 关闭 QD 的行为对照。运行与变更范围匹配的回归；影响科学条件时登记新协议并补足完整在线验收。具体检查与协作规则见 [CONTRIBUTING](../../CONTRIBUTING.md) 和 [AGENTS](../../AGENTS.md)。

## 更新规则

机制合入、协议改变或完整评测结束后更新本文，说明能力变化、有效结果和下一步。研究假设变化同步更新 Proposal。

每次结果报告应记录：研究问题、受测提交、配置与资产身份、服务条件、任务与 seed、纳入规则、逐任务结果、有效性、计算量、日志/视频位置及限制。详细提交、工作树和历史映射放入[追溯索引](../steering/provenance.md)，不在本文维护开发流水。原始实验记录不可因文档整理而重写。
