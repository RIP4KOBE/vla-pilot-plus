# RDT + QD + ED：Object-Swap ≥5/10 自主迭代执行 Prompt

生成日期：2026-09-21。

本文是供用户复制并明确启动的新研究指令。本次生成文件不启动实验、创建研究 goal 或激活任何 skill。下面的预算是新一轮的建议默认值，可在启动前修改；旧研究的预算和授权不自动继承。

本 prompt 不自动选择 Arbor 或 Orchestra Research。只有用户明确调用相应 skill 时才加载：Arbor 的入口是 `arbor-research-agent`，Orchestra Research 的 `autoresearch` 是另一套 skill。仅提到 autoresearch、阅读本文件或讨论计划不构成 skill 调用。遵守当前 AGENTS.md；Superpowers 始终禁用。

---

以下为可复制的完整执行指令：

你负责在现有研究基础上开展新一轮 RDT + QD + ED 算法迭代。这里的 ED 对应本仓库的 EDS 实现与配置，不要为了统一名称批量重命名旧代码或证据。

我的目标是：从当前有效且成绩最好的 RDT+EDS+QD 配置出发，优化 QD 与 EDS 的核心机制，使冻结版本在 LIBERO-PRO `libero_object_swap` 的 10-task 正式验收中达到至少 `5/10`，并交付可复现、可审计的正式 RDT+QD+ED 算法版本。

## 1. 执行范围与工作方式

在我明确要求执行本 prompt 后，在以下范围和预算内自主完成：历史证据核对、新 worktree 与研究状态初始化、算法实现、必要测试、离线诊断、开发实验、独立验证、正式验收和最终版本交付。不把常规实现、CPU 验证、预算内晋级或失败后的下一轮机制设计反复提交给我审批。

每个候选都先冻结假设、实验协议与晋级标准，再执行；冻结和记录可以由你自主完成。不要给每个普通分析或测试都增加一次独立的人工审批。遇到缺失凭据、预算扩大、范围外模块修改或必须使用外部资源时，集中说明实际阻塞与所需决定。

这是新的研究周期。历史 Run045 的 no-adoption 是旧周期的有效结论；不能改写它，也不能把旧周期的“禁止第六候选”当作新周期不能研究的理由。新周期仍须根据新证据开展工作，不能机械重跑旧候选。

建议的新轮执行参数如下。只有我明确启动本 prompt 后这些默认值才生效；若启动消息另有设置，以该消息为准：

```text
MAX_GPU_HOURS = 48
MAX_EPISODE_ATTEMPTS = 240
MAX_CONCURRENT_GPU_WORKERS = 2
GPU_POOL = 本机 0..7，动态选择无外部占用的设备
PRIMARY_SEARCH_BUDGET = 每个完整 guided chunk 176 candidate evaluations / 11 batched score calls
FORMAL_CANDIDATES = 1
```

任一预算用尽即停止新增执行。启动前规划并保留候选、P2 对照、起始 QD 对照和必要消融的验证/验收额度，不把预算全部用于开发。中断、健康检查、基础设施恢复及失败运行的 GPU 用量均计账；所有已 dispatch 的 episode attempt 均占用总名额，不仅统计有效成功运行。显式记录 reserved/dispatched/aborted/valid，避免双计或漏计。额外模拟器分支 rollout 如获批准，另设事前冻结的 transition 上限，不能靠不称为 episode 规避预算。

## 2. 先接受历史事实，准确建立起点

仓库：`/home/hynx/VLA-Pilot++`。

当前历史最优有效 QD 是两个并列 `2/10` 配置，没有任何历史 QD 配置通过全部 adoption gates：

| 角色 | 历史 profile | 历史结果与用途 |
| --- | --- | --- |
| 主要 QD 起点 Q0 | `eds_quality_diversity_sparse_primary` | `2/10`，成功 tasks `{5,8}`；作为本轮默认算法起点 |
| 并列 QD 参考 Q1 | `eds_quality_diversity_uniform_expand20` | `2/10`，成功 tasks `{5,7}`；保留为历史机制比较，不额外默认扩展在线矩阵 |
| 稳定比较对象 C0 | `p2_stage_on_abs_rbf_control` | QD OFF，同轮 `3/10`，成功 tasks `{3,8,9}` |

选择 sparse 作为起点是本轮研究设计选择，不代表它已经证明优于并列的 expand20。P2 在另一次恢复审计中有 `4/10`，但不同轮次的成功集合和运行条件不能合并。不得把 P2 的成绩写成 QD 的成绩，或把最新 HEAD 默认当作性能最优版本。

Git 身份：

- 历史 QD 报告冻结基线：`5b0898e53d5b9e16200c17479a74746071215787`。
- P2 来源：`b3db98cf4fd98a6479d92683e33ebe3d032f25d9`。
- 最新已结束 autoresearch 实现：`744e08ba4398f2f8e34fb05619c829fc01397f69`。
- 根目录 main 的平台代码尚未整合全部 EDS/QD，不能直接以 main 默认配置代替研究起点。

默认从 `744e08b` 创建独立新 worktree，以复用必要的记录与修复能力；显式恢复 Q0/C0 的完整 profile，并关闭 causal envelope、global anchor、protected secondary lane、degenerate fallback 等后来实验开关。先验证其与历史起点的行为契约。若发现行为差异，列出来源并固定实际起点；不能把差异隐藏在“同一 baseline”标签下。必要时使用 `5b0898e` 加最小且经过验证的工程修复作为来源。

以下历史边界必须进入新研究总账：

- 257-job RBF 扫描只有 3 个有效配置各 `1/10`，不支持重复原样大扫。
- 18 个增大 QD population/iterations 的配置全部 `0/10` 或 `1/10`，不支持默认靠扩算力解决问题。
- H1 改善 partition/overflow，且实际进入独立 validation：候选 `1/10`、对照 `0/10`，未达目标。最终报告中“没有进入 validation”的概括有误。
- H2 在历史数据中观察到 exact-zero reward；后续在线 fallback 没有触发，不能认定已检验其触发后的效果。
- H3 continuity/memory 被降低优先级，没有完成独立在线否证；也没有足够证据把它默认列为首选。
- H4 有大量 quality lineage rescue，但 Dev 为 `0/6 -> 0/6`。
- H5 top2 离线出现 17 次 quality-retention 违规；protected lane 修复相关一致性问题，但在线为 `0/2 -> 0/2`，且 3/410 iterations 未激活 secondary。
- 独立 FSM 使用不同的 QD/P48/K20 配置，存在无效/安全失败，不能直接移植或声称证明所有阶段策略无效。
- 旧 autoresearch 已结束：70 effective online attempts、98/144 reservations、约 6.946832/48 GPU-hours、新 formal 为 0。它没有完成目标，也没有证明整个 QD-ED 机制空间不可改进。

## 3. 必需证据与隔离目录

先读以下文件中与本轮有关的部分，按需检查 raw artifact，不要求逐轮重读全部历史：

```text
HANDOFF.md
.worktrees/exp/eds-quality-diversity/docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-06-eds-quality-diversity-report.md
.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/docs/03_evidence/eds_qd_autoresearch/iteration-ledger.md
.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/experiments/run_010_causal_envelope_candidate/analysis.md
.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/experiments/run_020_quality_selection_calibration/analysis.md
.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/experiments/run_023_reward_degenerate_online_mechanism/analysis.md
.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/experiments/run_034_global_quality_anchor_dev_a/analysis.md
.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/experiments/run_040_within_cell_aliasing_diagnostic/analysis.md
.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/experiments/run_044_protected_quality_lane_online_mechanism/analysis.md
```

终局原始证据：

```text
/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_045_global_no_adoption_conclusion/manifests/global_decision_manifest.json
```

启动时生成唯一 `run_id`，建议使用：

```text
branch:   exp/rdt-qd-ed-final-<run_id>
worktree: /home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-<run_id>
artifacts:/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-<run_id>
```

所有新代码、实验配置、协议、状态和报告写入新 worktree；大型产物写入新 artifact root。旧 worktree、旧结果和 immutable manifest 只读，禁止覆盖、清理或原地修复。特别不要读取、修改、复制或提交旧 autoresearch worktree 内受保护的未跟踪文件 `docs/01_specs/2026-08-10-eds-qd-stage-guidance-transition-design.md`。

历史 YAML 有重复 key、H5 pending 等状态滞后，新状态应从最终 manifest 与总账核对后重建，并用拒绝重复 key 的解析方式验证；不要直接恢复旧 runner、复制旧 active_experiment 或继续旧 attempt IDs。

## 4. 固定实验条件与可修改的算法范围

固定 RDT Object EMA checkpoint、图像/状态/动作语义、执行器、任务定义、成功判据、strict perturbation、720-step 上限、20 Hz、8-action execution chunk，以及历史 P2 的 Stage/cache/perception/prompt 设置。首个在线运行前冻结全部 resolved config 与模型、BDDL、init states、guidance cache 和依赖指纹。

启动检查必须核对缓存的目标身份和已有 Stage 输入契约。若发现影响对照有效性的错误，先单独报告并修复新研究副本中的工程问题；修复后的对照重新标记和验证，不能把修复收益归因于 QD。

主要允许修改：

- QD behavior descriptor、分区、archive 容量与更新规则、去重、replacement。
- 基于当前可用 observation、动作、历史执行反馈的 QD quality、ranking 与 final selection。
- QD parent allocation、exploration/exploitation 分配、lineage 保留、预算内 proposal 选择。
- QD 与 EDS resample/renoise/rollout 的接口；必要时调整 EDS 内部机制，但保持归因清楚和计算预算可比。
- 有明确机制证据的跨 chunk archive/state/continuity；确保 reset、目标变化和失效时不会使用过期状态。

默认冻结外部 reward provider，允许在 QD 内改变如何利用现有 reward 和可观测进展特征。不得伪装为 QD 改动去修改 Stage 识别器、VLM prompt、grounding、环境扰动、success predicate、动作执行时长或 RDT checkpoint；不进行 RDT/backbone 微调。新 learned scorer/descriptor 涉及训练时，须先说明数据隔离、训练预算和模型依赖，获得范围扩展后才能开展。

禁止按 task ID、seed、job label、已知成功任务或隐藏 evaluator 状态分支；禁止用未来 observation 或当前候选尚未执行的真实结果参与部署时选择。允许使用原本可获得的任务条件和观测。

最终候选必须实际保留 QD 的行为区分、质量选择和 ED 搜索作用，并有 trace 证明；不能通过关闭 QD、把它变成无效装饰或换模型来完成目标。

## 5. 第一轮先诊断，再选择一个改动

优先区分三个问题，不能预设“唯一原因已经是 reward alignment”：

1. Proposal：已有候选是否包含能推进抓取/运输/放置的动作？
2. Selection：如果包含，当前 quality/selection 是否把它选中？
3. Closed loop：如果短期推进了任务，后续 chunk 是否保留了进展？

先利用现有 metrics、candidate traces、Stage events、视频和代码做有边界的诊断。优先检查成功集合的 gained/lost、评分退化、同 cell 不同行为的淘汰，以及选中动作到实际执行结果之间的差异。不把“timeout without completion”自动解释为错误目标、未抓取或 reward 失配。

若没有候选的真实反事实结果，明确记录 Unknown。只有完整状态可恢复且另行批准额外分支仿真范围时，才运行同一状态下的候选短期 rollout；这些结果只用于诊断，不作为正式方法可访问的 privileged input，不混入正式 SR。

建立按证据排序的机制队列，但一次只实现一个主要改动。可考虑的方向包括：能区分实际操作后果的 descriptor、与观测进展有关的质量判断、避免无区分度 reward 主导选择、保留可继续完成任务的动作分支、基于反馈的跨 chunk 保持。它们都是待验证假设，不能仅凭名字进入大规模实验。

不要自动开启 H1+H4+H5 全套开关，也不要先把它们堆叠后解释总效果。重复历史方向必须指出新增证据、具体机制区别，以及为何旧负结果不能直接否定这次修改。

## 6. 自主内外循环

每个 inner-loop iteration 执行以下完整闭环：

1. 写 hypothesis card：历史依据、目标失败行为、因果假设、唯一改动、可证伪预测、对照、split、预算、晋级/停止标准。
2. 冻结协议与源代码身份；实现最小必要改动，保持原路径可回归，运行与修改有关的测试。
3. 验证 input/output、reset、archive/selection/source accounting 和默认关闭行为；不要把单元测试数量当作效果证据。
4. 必要时进行小规模在线机制检查；机制活跃和有限性检查通过后，进入开发集任务评估。
5. 报告逐任务 outcome、同轮对照差值、gained/lost、错误、延迟与预算，再给机制指标。
6. 做 KEEP / REJECT / INVALID / INVESTIGATE 决策，追加总账并继续下一步。

开发比较至少包含候选与同轮 P2；研究起点 Q0 在基线建立、关键候选晋级和最终验收时出现。可以增加“仅移除本轮改动”的同轮消融，区分真实改动收益和多组件差异；是否运行必须计入预算。多候选不得只和不同日期的历史数字比较。

每 3 个有效候选实验、连续 2 次没有任务改善，或出现机制与结果矛盾时，执行 outer-loop：

- 总结什么已证实、什么被否证、什么仍未知。
- 检查是否反复优化同一个 proxy、是否有协议或分析错误。
- 选择 DEEPEN / PIVOT_WITHIN_QD_ED / COLLECT_TARGETED_EVIDENCE / CONCLUDE_TARGET_NOT_MET。
- 新机制有任务相关依据且预算允许时，自主冻结下一协议并继续；单个候选 FAIL 不自动结束整个目标。

也不得无证据无限生成候选。经过一次有边界的定向复查仍找不到新的、可证伪的 QD-ED 假设，或预算耗尽时，保存状态并如实报告目标未达，说明继续需要的具体证据或范围扩展。不能把“本轮结束”写成“目标已完成”。

## 7. 数据隔离、晋级与 formal 规则

### 7.1 启动时冻结评估结构

维护已暴露 task/seed/init-state 清单。历史 formal/validation 和本轮已查看结果都不是未见测试集。冻结 task->seed 映射后按 backend 的真实任务顺序生成运行列表，不能直接 zip 两个可能被重排的列表。

- Historical：可用于提出假设和复核，不作新泛化证据。
- Dev：用于机制选择和开发，逐次记录复用，不包装为独立检验。
- Validation：每个 task 至少 2 个预先冻结的新 seed；候选、P2、Q0 同轮比较。进入前冻结完整算法、超参数和数据使用记录。
- Formal：一个最终候选，10 tasks 各 1 episode，同时运行冻结对照和必要消融。

新 seed 必须核对实际 env init-state 身份；如果仅改变采样噪声而没有改变布局，只声称 seed 鲁棒性，不声称新布局泛化。验证集与历史暴露记录去重，禁止依据结果挑 seed。

### 7.2 Validation 晋级规则

建议本轮冻结以下标准：20 个 candidate validation episodes 中成功数至少 10，且总成功数不低于同轮 P2 与 Q0。逐 seed block 和逐任务结果完整披露，不要求每个开发 cell 都无回退，也不从回退任务中事后删样本。

这些是本 prompt 建议的新工程标准，不是历史已经达到的结果。若用户在启动前选择其他验证规模，应同时事前确定阈值；结果揭示后不能降低门槛。

Validation 失败结束该候选的晋级。预算允许时可以返回开发，但不能依照已揭示 validation 的任务/seed 结果做定向调参；后继候选只能使用新的事前冻结 validation，保留并报告全部验证尝试和选模次数。

### 7.3 Formal acceptance

沿用既有 10-task 工程验收的映射：

```text
task:  0    1    2    3    4   5    6    7   8    9
seed: 44  235   43  546    6 621  197   87 151  548
```

这组数据已在历史研究中暴露，必须称为“历史固定 acceptance set”，不能声称是独立未见测试。新 validation 提供另一组证据，但不能消除历史集的暴露事实。formal 前再次绑定 task/seed/init/checkpoint/config 身份。

正式候选必须同时满足：

```text
expected task/seed records = 10/10
candidate success_count >= 5/10
candidate success_count >= contemporaneous P2 success_count
candidate success_count >= contemporaneous starting-QD success_count
runtime/data/selection/accounting validity = PASS
preregistered numerical/action/execution safety checks = PASS
compute and artifact provenance = PASS
QD is substantively active in the deployed candidate = TRUE
```

最后一次 formal 前冻结代码、所有 profile、对照、QD 消融和报告逻辑。只执行一个最终候选。formal 失败不得在这组已暴露结果上修改候选后再刷分；保留失败结论，本轮未完成目标。如需新周期，应重新确定独立证据与验收设计。

基础设施故障只允许按事前规定恢复完全相同的科学身份，旧 attempt 保留；合法任务失败不能重跑择优。算法引发的 qpos、nonfinite、执行错误等计入失败与安全审计，不能当作基础设施故障删除。

## 8. 计算公平性与机制证据

主要路线保持 population=16、10 iterations、完整 guided chunk 176 evaluations/11 batched score calls，并以模型 batch size、denoising steps、model/reward/VLM calls、wall time 和 GPU-hours 辅助核对。不能只用 score-call 次数掩盖更多模型计算。由于 Stage 活跃时间可能随行为改变，同时报告完整 episode 的总计算量。

若确需调整搜索预算，必须在运行前声明为额外计算探索，并提供匹配预算的 P2/Q0 对照；不得直接拿它与低预算历史结果宣称机制优势。超出总预算仍需另行批准。

正确性硬门包括身份匹配、信息无泄漏、数值有效、动作契约、确定性的 accounting，以及声称实现的算法语义。coverage、overflow、rescue 次数、secondary 激活率、descriptor spread 等通常作为解释指标，不设置脱离任务目标的任意否决门。

如果新方法改变了 quality 定义，不应要求它永远保留旧 scalar reward 的最大值；应事前写明新的语义和测试。相反，若候选明确承诺某种保留不变量，就必须按承诺验证，不能失败后删门。

达到成功率但机制解释未获支持时，记录“工程验收通过，原机制解释未证实”；不能因此伪称 QD 的因果贡献。正式版本需要计算匹配的 QD 移除/替换消融和 trace，说明具体机制作用；小样本持平只能写贡献未建立，不能选择性隐藏。如果实现实际退化为 QD-OFF，不满足本任务的算法目标。

## 9. 工程执行与记录

启动时重新检查 GPU/磁盘/依赖和 CUDA-EGL 对应，不能照抄 handoff 的资源快照。只使用空闲且准入通过的 GPU，不终止、抢占或共享外部研究进程。凭据使用已有的运行时注入方式，不读取历史日志找 secret，不写入命令行、Hydra、Git、manifest 或报告。

在新 worktree 维护一个权威状态文件和一份统一总账，其他索引从它们导出。最少保留：

```text
research-state.yaml
docs/03_evidence/qd_ed_final/iteration-ledger.md
experiments/<iteration_id>/protocol.md
experiments/<iteration_id>/analysis.md
data/exposure-registry.jsonl
data/attempt-ledger.jsonl
docs/03_evidence/qd_ed_final/final-report.md
```

每轮总账记录 source commit、代码/config/input 指纹、假设、对照、task/seed/init、结果、gained/lost、错误、耗时、累计预算、产物路径和决策。研究状态应区分 candidate、study 和 project target；解析时拒绝 duplicate keys。恢复关系按 profile/task/seed/init 身份关联，不能按 ledger 行号或位置匹配。

必要时在独占新分支提交清晰的协议、实现和结果版本，禁止改写旧研究历史。最终不自动 merge main、不推送或发布；先交付可审查的分支和版本。工作中持续给出简短进展，不把用户的状态询问当作取消研究。

## 10. 达标后的正式版本交付

满足验收后停止新的算法探索，完成必要的整理与验证，交付：

1. 正式算法版本与准确 commit、专用 profile、环境/input 指纹及完整运行命令；候选开发开关与正式配置明确分开。
2. 算法说明与伪代码：descriptor、quality、archive update/replacement、parent allocation、ED rollout、final selection、跨 chunk/reset 行为。
3. 同轮结果：P2、起始 QD、最终候选及关键 QD 消融；独立 validation 与历史 acceptance 分开列出。
4. 所有正式 task/seed outcomes、视频、metrics、config、manifest，以及 invalid/failed/recovery 记录。
5. 计算成本、延迟、任务 gain/loss、已支持和未支持的机制解释、剩余失效模式。
6. 与本次改动有关的测试和回归结果、复现说明、面向主线的后续采用清单。

不要把 5/10 工程验收夸大成总体成功率稳定达到 50% 或统计显著优于对照。不要把尚未验证的候选命名为正式成功版本。

若目标未达，交付相同口径的完整负结果、真实最优有效候选、预算余额/耗尽情况和下一项具体研究需要，明确写 `TARGET_NOT_MET`。

现在按顺序推进：读取必要证据，确认 Q0/P2 身份，建立新研究目录和预算表，冻结数据划分，然后选择最有任务证据支持的一个 QD-ED 机制假设进入闭环。不要从“全部历史实验重新运行”开始，也不要在只写完计划时结束已获授权的执行任务。
