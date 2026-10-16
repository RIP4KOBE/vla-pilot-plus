# 从 EDS 对照到 EDS+QD：合作者研发流程

本文是基于当前主线代码与既有验收证据的工作流分析，不代表已经执行新的实验，也不承诺通过调参可以达到指定成功率。研发起点是 **main 的 RDT + EDS + LIBERO ObjectSwap OOD**；RSI 原型分支的 π0.5 训练流程是另一条研究路线。

## 目标与已知起点

当前可依赖的对照是包含 RBF 的 EDS。Codex `ultra` 的主线验收和独立新环境验收都观察到：VLS 1/10、EDS 3/10、EDS+QD 0/10。EDS 在新环境验收成功的任务编号为 3、8、9。`low` 的 QD 1/10 属于另一协议；π0.5 标准 LIBERO Object 的 9/10 也不能用于这里的对比。见 [Progress](research_progress.md) 和[新环境验收](../steering/onboarding-validation.md)。

本次讨论的“超过 5/10”按严格含义是 **至少 6/10**。这应分成两个层次：在固定十任务开发协议中观察到 ≥6/10；在独立重复与保留测试条件中证明改善具有稳定性。一次十回合结果不等同于稳定 60% 成功率，也不足以单独证明 QD 优于普通精英保留。

## 1. 从 main 建立可审计的 EDS 对照

按[安装指南](../steering/installation.md)获取 main、必要子模块、新环境、固定公开权重和任务资产。保存当前 `git rev-parse HEAD`，不要从旧 worktree 或 RSI 环境隐式导入代码。只运行 RDT 时不需要下载 π0.5 或其 tokenizer。

必须固定的条件如下；精确值以[共同协议](../../configs/evaluation/libero_object_swap.yaml)和 [EDS profile](../../configs/steering/eds.yaml)为准。

| 条件 | 保留内容 |
| --- | --- |
| 模型 | 固定 revision 的 RDT LIBERO Object EMA checkpoint、T5、SigLIP、DINO 与兼容依赖 |
| Benchmark | `libero_object_swap` 的任务 0–9；不能换成标准 `libero_object` 或 PR 的环境/位置任务组 |
| 初始化 | seed 序列 `[44,235,43,546,6,621,197,87,151,548]`、episode ordinal、prepare/rollout RNG fixtures |
| 执行 | 每块执行 8 步、环境上限 720 步；固定观测、动作变换、夹爪和成功判定 |
| EDS | 16 个候选、既有去噪/进化迭代与 RBF 参数；archive 关闭，不启用跨块记忆 |
| 在线控制 | Codex CLI 0.156.1、`gpt-6-astra`、`ultra`；每任务 fresh 身份/阶段/reward，当前观测在线 Stage，本地 reward 评分 |
| 有效性 | 源码/配置/环境/资产冻结，保留失败与捕获，不混入回复回放或补跑拼接 |

在安装完成、已生成 `.local/rdt.yaml` 后，从仓库根目录执行；所有运行使用新的输出目录：

```bash
python scripts/check_steering.py --local-config .local/rdt.yaml \
  --output-dir outputs/eds-preflight-001 --gpu --api
python scripts/run_steering.py --method eds --local-config .local/rdt.yaml \
  --output-dir outputs/eds-preview-001 --print-config
# 单任务诊断：运行链路检查，不计入正式成绩。
python scripts/run_steering.py --method eds --local-config .local/rdt.yaml \
  --tasks 0 --output-dir outputs/eds-diagnostic-001
# 完整十任务：不得把上面的诊断回合拼入本组。
python scripts/evaluate_steering.py --method eds --local-config .local/rdt.yaml \
  --output-dir outputs/eds-reference-001
python scripts/audit_steering.py outputs/eds-reference-001 --no-write
```

配置预览只检查配置。诊断任务 0 本来就在历史失败任务中，因此“任务 0 失败”不能说明安装失败。完整验收要同时检查十回合完成、原生环境 success、基础设施状态和审计有效性，而非只看最后一个百分比。

如果同协议观察到 3/10，可建立本机研发对照；仍不能宣称远端 Codex 响应、reward 或每步轨迹逐字节相同。如果数值不同，先核对源码与导入位置、权重哈希、依赖补丁、初始化/RNG、GPU/EGL、在线输出和 Stage/reward 合同。允许事先登记的独立重复，用完整结果组报告变化；不能反复重跑直至挑出 3/10，或先修改 QD 来掩盖基线差异。

既有 EDS 十任务的墙钟时间约 3 小时 48 分钟，仅供排期参考；安装、资产下载、在线服务等待和机器差异会影响耗时。这不是 GPU 活跃小时。

## 2. 定位当前 QD 为什么没有带来收益

先在同一主协议中记录默认 QD 的完整对照，再开始修改；默认实现的 0/10 是需要解释的起点。

```bash
python scripts/evaluate_steering.py --method eds_qd --local-config .local/rdt.yaml \
  --output-dir outputs/qd-reference-001
python scripts/audit_steering.py outputs/qd-reference-001 --no-write
```

现有 QD 复用 EDS 搜索，按目标相对末端 XY 描述符构造 4×4 网格，每格一个精英，以稀疏优先策略选父代；默认每动作块重建档案。档案存在且生效，不代表保留了对抓取/搬运有用的多样性。

需要把 `output/evaluation`、Stage 在线捕获、候选/档案记录和视频按任务、阶段与动作块对齐，回答：

- 丢失 EDS 原有成功任务发生在接近、接触、抓持、搬运还是放置？先区分环境合法失败和运行无效。
- 稀疏优先是否反复抽到低质量父代？描述符是否集中于边界、只有少量有效格子，或把动力学上近似的轨迹分成不同格子？
- 档案最高预测 reward 与执行后距离、抓持/掉落、原生成功是否一致？未执行候选没有真实环境成功标签，不能称为“本来能成功”。
- 档案精英是在旧迭代中保留下来的，还是多样性确实产生了新的可执行行为？性能变化是否只是更多记忆或不同计算量？

历史捕获可用于离线定位候选排序、父代和描述符问题，但不能填入完整在线成功率。不同方法独立 fresh 生成内容时，在线模型也会引入变化；应保留输出并做独立重复，不能把单组差值全部归因于 QD。

## 3. 按单变量顺序改进

| 顺序 | 假设与改动方向 | 应观察的证据 |
| --- | --- | --- |
| 先做质量约束的父代分配 | 稀疏优先可能牺牲任务质量；研究质量锚点与多样父代的混合，保留 EDS/RBF 其余行为 | 父代质量分布、后代改善、原成功任务是否保留；不能只看 archive occupancy |
| 再做任务相关描述符 | 末端 XY 可能漏掉接触、抬升、路径形状与实际执行前缀的差别；逐个验证低维描述符与边界 | 有效格子、边界夹紧率、实际动作差异，以及失败阶段的改善 |
| 再检查精英与执行选择 | 搜索需要多样性，但最终执行仍需任务质量；区分档案维护、父代选择、最终候选选择各自贡献 | 同候选集的选择诊断、可执行前缀质量、任务结果；不改 reward 来追分 |
| 块内有效后才研究持久性 | 跨块复用需状态对齐、重评、失效与 reset；跨阶段 reward 不能直接比较 | 同容量普通记忆对照、过期候选率、反馈归因；单独登记新协议 |

以上均为待检验假设。不要同时改变 reward、Stage、RBF、描述符、父代和记忆，再把整体提升叫作 QD 的收益。

建议至少保留四个对照：原始 EDS、仅全局精英保留、同容量普通候选库、QD。尽量匹配模型调用/候选行数、迭代、reward/梯度计算与存储容量；无法相同时报告实际成本。还应消融描述符和父代策略，并检查 RBF 与 QD 的互补性。

## 4. 在代码中从哪里修改

- `core/qd_ed.py`：描述符、分格、档案更新、精英和父代。
- `core/rdt_policy_steer.py`：在 EDS 搜索中的接入、候选评分及最终动作选择；保持 `eds` 关闭 archive 的对照。
- `configs/steering/eds_qd.yaml`：在功能分支上登记 QD 差异；共同协议和 EDS profile 不顺手重写。
- `scripts/steering_runtime.py`、`scripts/audit_qd_mechanism.py`：配置有效性与机制审计。新增枚举/配置字段时同步校验和回归；不删除审计规则来接受新方法。
- `main.py`、`core/env_adapters/`：先用于读取执行反馈与失败证据。改变动作或初始化需要额外验收，不属于纯 QD 参数修改。

当前 launcher 只提供 `vls`、`eds`、`eds_qd` 三个公开方法，不存在任意 `--profile` 参数。初期可从 main 派生独立功能分支，在版本控制下修改 QD profile 与实现，由 launcher 保存有效配置/源码哈希。若以后需要同时维护多个候选 profile，应先实现显式、受审计的实验配置入口，而不是使用未记录的命令行覆盖。

## 5. 筛选、验收与协作

每次实验先写明假设、唯一主要变量、对照、任务范围、计算条件和失败标准。先做相关 CPU 行为回归与离线机制诊断，再用少量任务筛选；筛选结果只用于开发，不能拼成十任务成绩。进入候选验收后冻结实现，运行完整在线十任务，并保留全部原始记录。

达到 ≥6/10 后仍需：独立重复、与同服务时段的 EDS 对照比较、保留 seed/初始化的验证、精英/候选库/描述符/父代消融。长期针对这十任务迭代会产生开发集过拟合；保留测试条件应在选择最终方案前约定。新增 seed 组属于新的评测条件，不改写原十任务定义。

功能分支完成检查后提交 PR，附算法差异、逐任务结果、有效性、计算开销和证据索引。合入 main 时更新 Progress；假设或路线变化更新 Proposal。研究优势应来自质量与有用行为多样性，而不是只追求单次成功率。

RSI 分支用于另外验证“失败识别 → 数据/策略更新 → 独立评估 → 新一轮部署”的闭环。它不能替代这里冻结 RDT 的 QD 对照，也不能把 π0.5 的权重训练收益算作 inference-time QD 增益。
