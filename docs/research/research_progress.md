# VLA-Pilot++ Research Progress

最近核对：**2026-10-15**。本文件是“当前做到哪里”的权威入口，与 [Proposal v0.1](research_proposal.md) 的 RQ1–RQ5 对应。实验报告保留原日期与原始字节；本次包含控制代码组织重构、仓库发布、归档和文档整理，没有新增科学实验。

## 1. 当前结论与源码身份

**当前最可靠的研发对照是 RDT+EDS（含 RBF），在已验收的共同 ObjectSwap 协议中为 3/10。** 三模式已整合；EDS+QD 机制生效且可审计，但尚未显示优于 EDS。下一步应解释父代选择、行为分区和实际执行之间的关系，再做 QD 单变量改进。

| 身份 | 提交 / 证据 |
| --- | --- |
| 本次整理起点与首次远端发布 | main `6c0d72b7a56739ffc524b0e294c3c975d18c5ae4`，2026-10-15 普通推送并核对远端 |
| 团队整合 merge | `8c1051f85a57115163845ec478d06a3ccc68c190` |
| low 三模式受测 runtime | `33954ead452927fc3168efb610487a688f89169e` |
| ultra 最终共同协议受测 runtime | `c99565de6e34278c14518748d7c608433a4c529a` |
| 整理后的发布身份 | 包含本文件的 main 提交；用 `git rev-parse HEAD` 确认，并与[整理报告](../maintenance/repository-consolidation-20261015.md)中的发布记录核对 |

此前整理前曾核对 116 个 runtime 文件与 ultra 冻结快照逐字节一致。2026-10-15 的后续模块重构改变了文件路径与源码哈希：19 个控制/传输模块合为 10 个实现文件，66 个函数/类逻辑节点及 20 个模块常量经限定的 AST 对照一致，EDS 离线闭环匹配冻结参考，全套 CPU 检查为 1449 passed、3 skipped。该证据不能描述为新版重新取得在线 3/10；在线成绩仍归属上表原 runtime。见[本轮发布报告](../maintenance/public-release-20261015.md)及[检查记录](../maintenance/control-layout-validation-20261015.json)。

## 2. 研究目标与实现状态

“已实现”表示代码存在；“已测试”需要对应测试证据；“已验收”还需明确协议及完整结果。未启用的实验接口不继承默认 profile 的成绩。

| Proposal 目标 | 当前状态 | 已有证据 | 尚缺什么 |
| --- | --- | --- | --- |
| 共同 steering 框架 | 已实现、测试并在线验收 | 公共 launcher/worker、三种 profile、完整 cohort 审计 | 新机器仍需固定模型/任务资产 |
| EDS 对照 | 已实现、测试并在线验收 | low 与最终 ultra 分别 3/10，成功任务均 3、8、9 | 多 seed 稳定性、等计算预算及更广泛泛化 |
| RQ1：动作块内 QD | 已实现、测试、机制与运行有效性已验收 | BD/网格/精英/父代/最终选择日志及独立重建 | 成功率收益：low 1/10、ultra 0/10，不支持优势 |
| RQ2：操作相关 BD | 默认 XY 已验收；执行意图等可选代码存在 | `qd_descriptor`、`execution_intent_descriptor`、相关 CPU 测试 | 默认以外配置在共同协议的有效完整对照 |
| RQ3：质量与多样性平衡 | sparse 父代已验收；其他选项有代码/单测 | `allocate_parent_slots`、全局质量 anchor/secondary 等接口 | 每项独立消融和计算量一致的因果证据 |
| RQ4：跨块执行反馈 | 部分 warm-start/状态接口存在，默认关闭 | `EDSChunkMemory`、`warm_start_mix`，默认 `fresh` | 持久 QD、有效性/过期/反馈更新的完整在线验收 |
| RQ5：MLLM 自动 BD | 研究设想 | Notion 章节标题和 Proposal 路线 | 生成合同、实现与未见任务验证 |
| Recursive self-improving | 尚未证明 | 仅有块内搜索与在线 Stage 闭环 | 跨执行经验带来可重复收益，排除预算/重试/服务混杂 |

历史分支含更多研究变体，已归档可查；不能将未合入 main 的实现或旧协议实验升级成当前能力。

2026-10-15 的[远端历史源码索引](../maintenance/historical-source-index-20261015.md)提供历史分支、工作树未提交源码、stash 和外部源码快照的 GitHub 入口。发布副本存在凭据样式内容脱敏，原始字节与提交映射另存；不将归档发布描述为新算法验收。main 运行时行为未因本次整理改变。

## 3. 三模式实际运行机制

统一入口：`scripts/evaluate_steering.py --method METHOD --local-config configs/local.yaml --output-dir NEW_DIR`。先按[安装说明](../steering/installation.md)准备配置和资产，预览与预检见 [README](../../README.md#开始使用)。

| 模式 | 默认机制 | 已验收范围 |
| --- | --- | --- |
| `vls` | 20 候选；guide=80、diversity=10；5 步去噪，正常 guided 块 1 次 RBF + 4 次 reward 梯度；自适应 FKD 可因 ESS 跳过 | 完整 online 十任务；实际控制、梯度/FKD与选择证据 |
| `eds` | 16 候选，初始 5 步 + 10 轮截断去噪，reward 父代重采样；RBF scale=20；最终取末代最好 | 完整 online 十任务；独立 EDS reference 与动作/Stage 合同 |
| `eds_qd` | 共用 EDS；4×4 target-relative endpoint XY archive，每格 1 精英，sparse 父代；最终取 archive 全局最好 | 机制真实生效、完整运行、独立档案与父代证据；没有性能优势验收 |

当前 profile 不使用跨块 archive。几何投影不是候选分支仿真；RBF 不是 Gaussian kernel；reward 可评分不等于可用于 VLS 梯度。完整公式和模块边界见[架构合同](../steering/architecture.md)。

## 4. 结果按协议分别记录

| 协议 | 日期 / runtime | EDS | VLS | EDS+QD | 有效性 |
| --- | --- | ---: | ---: | ---: | --- |
| Codex / Astra low，共同框架 | 2026-10-13 / `33954ea` | 3/10 | 1/10 | 1/10 | 三组均 10/10 完整有效，0 回合级基础设施错误 |
| Codex / Astra ultra，传输恢复修订后的统一协议 | 2026-10-14 / `c99565d` | 3/10 | 1/10 | 0/10 | 三组均 10/10 完整有效，30 视频有效，0 回合级基础设施错误 |

逐任务数据由 [low JSON](../steering/validation/final-results.json) 和 [ultra JSON](../steering/validation/reasoning-effort-results.json) 支持；表内失败均是完整有效的科学任务失败。

| task | seed | low EDS | low VLS | low EDS+QD | ultra EDS | ultra VLS | ultra EDS+QD |
| ---: | ---: | --- | --- | --- | --- | --- | --- |
| 0 | 44 | 失败 | 失败 | 失败 | 失败 | 失败 | 失败 |
| 1 | 235 | 失败 | 失败 | 失败 | 失败 | 失败 | 失败 |
| 2 | 43 | 失败 | 失败 | 失败 | 失败 | 失败 | 失败 |
| 3 | 546 | 成功 | 成功 | 失败 | 成功 | 成功 | 失败 |
| 4 | 6 | 失败 | 失败 | 失败 | 失败 | 失败 | 失败 |
| 5 | 621 | 失败 | 失败 | 成功 | 失败 | 失败 | 失败 |
| 6 | 197 | 失败 | 失败 | 失败 | 失败 | 失败 | 失败 |
| 7 | 87 | 失败 | 失败 | 失败 | 失败 | 失败 | 失败 |
| 8 | 151 | 成功 | 失败 | 失败 | 成功 | 失败 | 失败 |
| 9 | 548 | 成功 | 失败 | 失败 | 成功 | 失败 | 失败 |

补充实验必须单列：

- 迁移版 EDS：`cfecb12` 下 3/10，属于公共接口完成前的独立验收，不能代替其后的共同框架成绩。
- 首轮 ultra / `6c83eb6`：VLS 独立有效 2/10（task 3、6）；EDS、EDS+QD 各有一个 HTTP429 错误，整组无效。后续停止的两组重测不完整。所有尝试保留在 [ultra 报告](../steering/reasoning-effort-comparison.md)，不拼接最好回合。
- ultra 共启动 66 回合，最终预先登记的新 30 回合作为统一协议主要结果。54 个逻辑请求经传输重试恢复；传输错误恢复不等于重跑合法失败任务。
- 早期 Poe/Gemini、缓存 reward、固定 Stage 回复回放、P2 同轮控制，以及标准 `libero_object` 成绩均属不同协议。历史 P2 的 4/10 和标准任务无引导 9/10 不能据数值排在当前 ObjectSwap 共同基线之前；索引见 [README provenance](../../README.md#provenance)。本轮没有重审所有历史协议，不另给不充分的统一排行榜。

**推理强度结论：** ultra 没有显示稳定成功率提升，且传输重试由 1→8、等待由 2→30 秒，不能当作仅改变 effort 的因果实验。选定请求中出现相同图像但不同 Stage 判断、引导开关和后续动作；提示词的任务身份描述也不同。有限 reward 探针相等不能证明函数全域等价，更不能唯一归因于模型能力。完整归因边界见[推理强度对照](../steering/reasoning-effort-comparison.md)。

## 5. EDS 基线复现条件

新一轮默认保留 **当前 main 的 ultra EDS** 作为明确对照；历史 low 是另一套已封存协议。切回 low、修改传输参数或服务版本都需要登记新条件，不能在一个 cohort 中混用。

| 条件 | 要求 |
| --- | --- |
| 代码 | 记录运行时提交与 source SHA；当前科学/运行时文件对应 `c99565d`；后续修改另验收 |
| 模型/依赖 | RDT EMA checkpoint、T5、SigLIP、DINO 与固定清单；Python 3.12.12、Torch 2.7.1+cu126 等固定配方 |
| 任务 | `libero_object_swap` task 0–9，seed 如上表；固定任务/初始化资产及扰动 |
| RNG | 20 个 prepare/rollout 状态文件，并由运行 hook 在规定时点恢复；仅设置 seed 不足以代替 |
| 执行 | H=8，20Hz，最多 720 执行步，固定转换/夹爪语义与预处理 |
| EDS | 16×10；初始 RBF 20/0.8、rollout RBF 20/0.6；noise `[3,2,2,2,2,1,1,1,1,1]`；父代 `softmax(0.1*r)`；末代最好；QD off |
| 在线 | Codex CLI 0.156.1 / ChatGPT 登录；请求 `gpt-6-astra`、`ultra`；两类客户端均 180s、transport retry=8、backoff=30s；没有 Poe fallback |
| reward/Stage | 每任务 fresh 身份、阶段/reward；本地评分；运行中当前观测在线 Stage；固定 target-distance 合同及控制 profile |
| 设备 | 使用已分配且空闲的 GPU，单独验证 GPU/EGL 映射；当前用户授权可用 GPU，不限 GPU2；不停止他人进程 |
| 审计 | 完整 10 任务、成功/合法失败均保留；记录基础设施失败和未完成；使用 `audit_steering.py` |

精确模型与原始完整实验没有公开下载包；由维护者提供匹配字节后按[资产准备](../steering/installation.md#固定模型与源码资产)校验。请求模型名相同不保证长期后端不变，3/10 是验收参照，不承诺每次 fresh 在线请求复现完全同轨迹。

## 6. 下一步优先事项与验收

| 优先级 | 对应 RQ | 工作 | 完成标准 |
| --- | --- | --- | --- |
| P0 | 全部 | 在当前公开入口建立协作者可用环境，保留 EDS 对照和完整证据；补读 Notion 图片 | 配置/资产/入口检查通过，源码身份明确；原意与草案差异登记 |
| P1 | RQ1/RQ3 | 用现有轨迹分析 QD 失败：质量下降、稀疏选择、archive 输出与 Stage 时序 | 可复查的任务/动作块定位；至少一个单变量假设；不再只看 archive occupancy |
| P2 | RQ1/RQ3 | EDS vs 全局精英保留 vs QD；质量锚点/稀疏父代独立消融 | EDS 关闭 QD 的行为回归保持；机制张量与审计一致；完整共同协议在线对照 |
| P3 | RQ2 | 固定 reward/Stage，比较 XY 与执行相关 BD；检查投影/实际动作偏差 | 清楚定义单位、可控性、质量和覆盖；有效多样性及任务指标有证据 |
| P4 | RQ4 | 有状态复用和执行反馈更新 | reset/过期/Stage 边界测试；fresh 与持久版本多 seed 对照，排除额外预算优势 |
| P5 | RQ5 | 受约束自动 BD 与跨任务研究 | 生成合同、独立评测划分、未见任务证据；再讨论递归自我改进 |

单轮 5/10 可以作为阶段信号，不能直接宣称方法稳定优于 3/10。在线服务变化与搜索改动应分开控制；不要在同次实验同时更换 reward、Stage、descriptor 和父代策略。

## 7. 协作者从哪里入手

| 要改什么 | 入口 | 最小验证方向 |
| --- | --- | --- |
| BD、cell、精英、父代 | `core/qd_ed.py`、`configs/steering/eds_qd.yaml` | 有限值/边界/平手/分配守恒、实际父代和最终输出 |
| 搜索接入 | `core/rdt_policy_steer.py` | EDS reference 不变；QD 分支实际使用档案，评分/RNG/调用数可审计 |
| 执行反馈 | `main.py`、`core/env_adapters/libero_adapter.py`、`core/eds_eval_metrics.py` | 区分预测与实测；动作后处理、时序、reset 和观测权限 |
| Stage/reward（另立科学条件） | `core/stage/controller.py`、`target_distance_reward.py`、`vlm_query/target_distance/` | 门控/失败复查/评分能力一致；新协议在线验收 |
| 评测/归档 | `scripts/run_steering.py`、`steering_runtime.py`、`audit_steering.py`、`steering_archive.py` | 配置冻结、进程所有权、无效运行区分、搬迁后只读重审 |

测试文件按职责分布于 `tests/test_qd_ed_archive.py`、`test_rdt_steer.py`、`test_steering_eds_parity.py`（引用 `steering_eds_golden.py`）、`test_steering_runner.py` 和 Stage/transport 系列；先以 `rg --files tests` 确认实际文件名及范围。完整开发约束见 [AGENTS.md](../../AGENTS.md) 与 [CONTRIBUTING.md](../../CONTRIBUTING.md)。

## 8. 证据与维护规则

公开 Git 中保留 low/ultra 小型 JSON、报告、配置和 fixtures。原始 capture、视频、研究源码快照和机器配置在维护者归档中；[整理报告](../maintenance/repository-consolidation-20261015.md)及[清理索引](../maintenance/cleanup-inventory-20261015.json)记录归档映射。旧路径别名只用于追溯，不应再作为开发工作树。

每次机制合入、协议改变或完整 cohort 结束后更新本文件；proposal 的 RQ/阶段变化也同步更新。历史报告不回写成绩，纠错使用追加说明与新的证据文件。更新模板：

```text
日期 / 负责人 / PR：
对应 RQ 与假设：
实现状态：已实现 / 已测试 / 已验收 / 尚未验证
runtime commit / config hash / assets / initialization：
provider / model / effort / transport / fresh-or-replay：
任务、seed、预算、纳入规则：
逐任务 outcome / 成功数 / 完整有效数 / 基础设施错误：
审计器身份 / 报告、原始证据和视频索引：
结论、替代解释和适用边界：
下一步与验收标准：
```

不要手动把“最近 main SHA”改成一个尚不存在的自引用提交。记录受测提交、文档发布所依附的提交和最终远端核对 receipt 即可。
