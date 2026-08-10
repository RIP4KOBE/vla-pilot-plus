# EDS-QD Autoresearch / LIBERO Object-Swap OOD 长程闭环优化实验设计

初始日期：`2026-08-08`

本次修订：`2026-08-10`（`>=5/10` 目标优先、EDS+QD 核心机制收敛、全工作区历史证据只读检索、单文档迭代总账、GPU 0–7 动态准入）

状态：`Draft for review — planning only, not approved for execution`

目标分支：`exp/eds-qd-autoresearch-libero-swap-ood`

目标 worktree：`/home/hynx/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood`

最终工程目标：在冻结的 LIBERO-PRO `libero_object_swap` 10-task 正式评估上达到 `success_count >= 5/10`，且不低于同轮 contemporaneous control，并通过 validity、safety、compute、artifact 与 credential 硬门；mechanism audit 用于解释和指导优化，不凌驾于真实有效的 task success。

> 本文只设计下一阶段研究并初始化可恢复状态。本文在状态更新为 `Approved for execution` 前，不授权算法实现、GPU dispatch、LIBERO episode、shared2 实验目录创建、正式评估或自动 continuity loop。

## 1. 摘要

现有 EDS-QD 基线在实现语义上通过 archive accounting、elite monotonicity、parent allocation replay 和 fixed-compute hard gates，但在任务和机制上失败：同轮 control 为 `3/10`，uniform QD 为 `0/10`，sparse QD 为 `2/10`；有效 QD profiles 的 median coverage 几乎全部饱和到 `1.0`，而 offspring overflow P95 高达 `0.938–1.0`，paired coverage gain 为 `0`，best-reward delta 近似 `0`。这说明旧算法成功维护了一个离散 archive，却没有证明 archive 划分、quality、selection 或跨 chunk 行为与真实 manipulation progress 对齐。

本阶段用 autoresearch 双循环替代一次性 OFAT sweep。Inner loop 每次锁定一个可证伪机制假设，先提交 protocol，再做最小修改、测试、运行、记录和 keep/revert 决策；outer loop 每 5 个有效实验、连续 3 次无进展或出现系统性矛盾时综合证据并选择 DEEPEN、BROADEN、PIVOT 或 CONCLUDE。负结果、invalid 结果和 infrastructure failure 均保留为 append-only 证据。

研究方向被硬限制在 EDS+QD 核心链路，且以 QD archive/search 过程为第一优先级。`BROADEN` 只能拓展到另一个 EDS+QD 内部机制，`PIVOT` 只能从一个 EDS+QD 机制切换到另一个；不能转向 checkpoint、感知、prompt、Stage 识别器、环境或其他独立算法模块。只有当 QD-only 修改被证据否证或连续停滞，才允许沿 QD 与 EDS 的明确接口修改 EDS；必要时可修改完整 EDS+QD 链路，但每次必须保持单一、可归因的机制变化。

评估采用五层隔离：静态/历史 replay、offline mechanism、独立 development seeds、独立 validation seeds、最后一次冻结 formal acceptance。旧正式 tasks/seeds 已经公开，因此不能称为 pristine unseen test；本文将其降格为 reuse-limited acceptance set：可以使用旧证据提出假设，但新候选在 formal 前必须冻结，formal 结果不得回流到同一研究周期继续选模。

Primary adoption track 保持 checkpoint、suite、strict perturbation、Stage settings、720-step budget 和正式 task/seed mapping；完整 chunk 默认保持 `16 + 10*16 = 176` evaluations。learned/adaptive QD descriptor 只有经过历史证据、offline diagnostic 与机制消融后才可进入 primary；额外 compute 或更多模型调用只能作为 exploratory-only 证据，不能直接获得 adoption。

## 2. 状态、授权边界与标签

### 2.1 当前批准范围

当前仅批准：

1. 审计旧设计、报告、代码、raw metrics、manifest、ledger、日志和定性产物；
2. 从明确 base commit 创建隔离 branch/worktree；
3. 初始化 `research-state.yaml`、`research-log.md`、`findings.md`、trajectory 和 review status；
4. 写入并提交本文；
5. 运行不加载模型、不启动 simulator 的 CPU 单元/runner/audit 健康检查。

当前明确不批准：

- 修改核心算法；
- 建立新 shared2 experiment root 或 `outputs` 软链接；
- GPU/model load；
- development、validation、preflight 或 formal episode；
- scheduled task、cron 或 `/loop`。

### 2.2 决策标签

本文所有设置必须带以下标签之一：

| 标签 | 含义 |
| --- | --- |
| `HISTORICAL-FROZEN` | 来自已审计旧实验，只能读，不能事后改写 |
| `PREREGISTERED-NEW` | 本文为新研究预注册；执行后不得根据结果静默修改 |
| `FREEZE-BEFORE-EXECUTION` | 当前缺少运行时事实，首个在线 attempt 前必须冻结到 manifest |
| `EXPLORATORY-ONLY` | 可帮助理解，但不具备 primary adoption 资格 |

任何执行期修订必须追加带日期、原因、影响范围和用户授权的 revision；不得覆盖原文本。

## 3. 研究目标与成功定义

### 3.1 核心研究问题

能否在相同感知、checkpoint、OOD benchmark 与基本 inference-time compute 下，把 EDS-QD 从“维护高覆盖 archive”改造成“保留对 manipulation completion 有价值的多样行为”，并使冻结候选在正式 10-task set 上达到至少 `5/10`？

这是唯一 primary objective，也是所有 autoresearch 决策的第一排序依据。历史 best EDS-QD 为 `2/10`，因此初始 `target_gap = 5 - 2 = 3` 个 task successes；每轮必须说明准备翻转哪些失败 task、为什么该 EDS+QD 修改能翻转它们，以及结果把 target gap 缩小、维持还是扩大。QD coverage、overflow、reward alignment、continuity 等机制指标只用于选择更可能提升 task success 的方向，不能因为指标“有研究价值”而脱离成功率继续探索。

### 3.2 正式成功条件

候选只有同时满足以下条件才算研究成功：

```text
valid formal records = 10/10
success_count >= 5/10
success_count >= contemporaneous_control_success_count
paired gained_tasks >= paired lost_tasks
all validity gates = PASS
all safety gates = PASS
all compute/accounting gates = PASS
artifact/credential audit = PASS
```

`>=5/10` 表示至少成功 5 个任务，不是大于 5/10。

机制审计必须完成，但不是独立于 task success 的额外否决项；只有当机制审计揭示 privileged information、leakage、accounting/selection 错误、不可复现或其他 validity/safety 问题时才阻断 adoption。若 success 达标但预期机制未被支持，仍可认定工程目标达成，但只能如实写为“有效性能提升、原机制解释未证实”。

### 3.3 结论边界

- 结果只代表冻结 10-task set 上的 paired engineering evidence；
- 不宣称统计显著性或总体泛化；
- formal 达标但预期机制未证实时，保留 adoption，但不得宣称该机制成立，必须记录替代解释；
- mechanism 成立但 formal `<5/10` 时，不得标记 adoption；
- formal 失败不授权用已揭示结果继续调参或重跑另一个候选。
- 一旦冻结 formal candidate 达到 task、validity、safety、compute 与 artifact gates，立即 CONCLUDE 并交付；不得为追求更高分、新颖性、论文完整性或更多 ablation 继续算法探索。

## 4. 基线 Git Provenance 与阶段隔离

### 4.1 已审计基线

| 字段 | 值 | 标签 |
| --- | --- | --- |
| Source branch | `exp/eds-quality-diversity` | `HISTORICAL-FROZEN` |
| Source worktree | `/home/hynx/VLA-Pilot++/.worktrees/exp/eds-quality-diversity` | `HISTORICAL-FROZEN` |
| Base commit | `5b0898e53d5b9e16200c17479a74746071215787` | `HISTORICAL-FROZEN` |
| Base subject | `docs: freeze quality diversity final report` | `HISTORICAL-FROZEN` |
| New branch | `exp/eds-qd-autoresearch-libero-swap-ood` | `PREREGISTERED-NEW` |
| New worktree | `/home/hynx/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood` | `PREREGISTERED-NEW` |
| Init commit | `54b2487` (`research(init): eds-qd autoresearch libero swap ood`) | `PREREGISTERED-NEW` |

基线 HEAD 和 index 没有 tracked diff。Source worktree 存在一个用户未跟踪文件：

```text
docs/01_specs/2026-08-08-eds-qd-search-budget-parameter-sweep-design.md
```

该文件没有被读取、修改、提交或复制；新 worktree 直接从完整 SHA 创建，因此它不进入本研究 provenance。Source worktree 其余内容保持只读。

### 4.2 新阶段隔离规则

- 所有新算法代码、config、tests、protocol、分析文档、索引和报告只允许写入新 branch/worktree；
- 仓库主工作区、其他 worktree/branch 以及其中的 tracked/untracked 文件全部只读，不得修改、格式化、暂存、提交、复制覆盖或清理；
- `/home/hynx/VLA-Pilot++/**` 中新 worktree 以外的历史代码、实验方案和报告可以只读分析；
- `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/**` 中全部历史实验产物可以只读分析，不能重命名、删除、覆盖、补写 sidecar 或改变权限；
- 未来新大型运行产物只能写入本研究独占的 canonical artifact root；它们的 protocol、摘要、索引与 checksum 必须回写到新 worktree；
- 不复制旧未提交文件；
- 不修改旧 report、manifest、ledger 或 checksum sidecar；
- legacy `qd_archive_mode=none` 和旧 `grid_archive` 行为必须保留可回归的 config-controlled 路径；
- 新算法不能在 core 中按 job label 分支。

任何命令执行前必须同时验证当前 Git common-dir、branch 与 worktree realpath。若写目标不在新 worktree 或本研究独占 artifact root 下，立即 fail closed；绝不通过 `git -C`、跨 worktree patch、共享脚本原地修改或 symlink 穿透边界。

## 5. 基线证据索引与证据等级

完整 machine-readable 索引位于 `data/baseline-evidence-index.json`。

| 证据 | SHA-256 / provenance | 等级 |
| --- | --- | --- |
| 旧设计 `docs/01_specs/2026-08-06-eds-quality-diversity-design.md` | `ea2e0c274591dfbd33d1518725de322c41e90f49d110a1cec0a0bf5c8f2a4251` | 预注册设计 |
| 旧报告 `docs/03_evidence/.../2026-08-06-eds-quality-diversity-report.md` | `cbaa9df290e40bc8cca4affedd7b17fb46b3d32832f6e68d63eb77ae1340e16c`；sidecar PASS | 冻结总结 |
| Formal audit JSON | `56c4320e2f793e9dc856e34b3830e49595d69eb541d83b9d624b764bd81170ba` | raw-derived audit |
| Run manifest | `62200ccc4692a946fb84d1d46851e28e610ece7aae9705356746302db2c4c1cc` | provenance |
| Attempt ledger | `609e45a513cfca4074cbd9bbd22a6fa4e0bb5d64892832312fd63a006ec89e5e` | append-only execution history |
| Decision manifest | `45ce8dc8948d8c472d4bd8255301cb824b3e5f2fbceab6857f00779cad8e984f`；mode `0444`；sidecar PASS | immutable decision |
| Raw metrics | 10 metadata rows/job；control 128、uniform 140、sparse 226 active metric rows | raw telemetry |
| Contact sheets | tasks `0..9`，每 task `1/3/5s`，共 30 张；Grid5 缺失用红色占位 | qualitative |
| Grid5 traceback | `IndexError: tuple index out of range` at historical final selected-source bookkeeping | failure evidence |

证据表达规则：

- `Observed`：直接来自 code/raw artifact/audit；
- `Reported`：来自冻结报告且 checksum 可验证；
- `Inferred`：由多项证据推导，必须明确可被新实验推翻；
- `Unknown`：历史 telemetry 不足，不能用自动 taxonomy 补全因果。

### 5.1 全工作区历史证据发现协议

历史证据不是只限于上述基线目录。每个 outer loop 和每个新 root hypothesis 的 protocol 前，允许并鼓励只读检索整个工作区及 shared2 历史产物，优先寻找与 EDS proposal、rollout、QD descriptor、archive、replacement、parent allocation、quality、selection、budget 和跨 chunk state 直接相关的实验。

执行期在新 worktree 内维护 `data/historical-evidence-catalog.jsonl`，每条至少记录：绝对源路径、来源 branch/worktree/commit（可获得时）、run ID、日期、benchmark/task/seed、算法与 config fingerprint、结果摘要、raw artifact/checksum、证据等级、与当前 EDS+QD 假设的关系、冲突证据以及首次引用的 iteration ID。检索顺序固定为：immutable manifest/ledger 与 raw metrics > resolved config/code fingerprint > 原始日志/视频 > 冻结报告 > 未冻结笔记。报告不能覆盖相冲突的 raw evidence。

每轮不能只写“参考历史实验”；必须在统一迭代总账中列出实际使用的路径、checksum/commit、提取出的数值或失败模式，以及这些证据如何改变本轮假设或设计。未完整盘点所有历史目录不构成阻塞，但重复已有失败方向前必须证明已检索相关 catalog；新发现证据采用 append-only 方式加入 catalog，不回写历史源。

## 6. 基线结果、实现审计与初步诊断

### 6.1 历史结果

| Job | Valid | Success | Paired relation to control | 主要 gate |
| --- | --- | ---: | --- | --- |
| `p2_stage_on_abs_rbf_control` | PASS | 3/10 | tasks 3, 8, 9 success | baseline |
| `eds_quality_diversity_uniform_primary` | PASS | 0/10 | lost 3, 8, 9 | task FAIL；mechanism claim FAIL |
| `eds_quality_diversity_sparse_primary` | PASS | 2/10 | gained 5；retained 8；lost 3, 9 | task FAIL；mechanism claim FAIL |
| `eds_quality_diversity_uniform_expand20` | PASS | 2/10 | gained 5, 7；lost 3, 8, 9 | task FAIL；mechanism claim FAIL |
| `eds_quality_diversity_uniform_grid5` | FAIL | 0/10 | invalid | bookkeeping IndexError / missing artifacts |

所有 valid QD candidates 均未达到旧 task gate，最终 decision 为 `no_adoption_keep_p2_stage_on_abs_rbf_control`。

### 6.2 Archive 与 descriptor 观察

旧 BD 为：

```text
b(a) = [p_H,x - target_x, p_H,y - target_y]
```

Grid bounds 只从当前 chunk 的 16 个 initial descriptors 冻结，后续 160 个 children 超界时 clamp 到 edge cell。Raw 示例中 sparse episode 0/chunk 0 的第 2–6 个 iterations overflow ratio 为 `0.875`，但 coverage 从 `0.9375` 很快到 `1.0`。Formal 汇总中：

- uniform/sparse/大多数 OFAT 的 coverage median = `1.0`；
- overflow P95 = `0.938–1.0`；
- paired normalized coverage delta = `0`；
- replacement-active chunk ratio = `0.190–0.461`，均低于旧 `0.50` gate；
- global-best reward delta 约为 `0–0.002`。

`Inferred`：旧 grid coverage 被 edge-clamped 后失去分辨率，不能再代表真实、可利用的 behavior coverage。H1 将直接检验该推断。

### 6.3 Quality 与 task progress 观察

`core/qd_ed.py` 每 cell 只保留 reward 最大 action；`core/rdt_policy_steer.py` 最终执行 archive 全局 reward 最大 elite。BD 不参与 quality，task success、future observation 和 privileged state 不进入 selection。这保证了旧实现语义干净，但也形成潜在错配：best reward 基本不变时，任务结果从 0/10 到 2/10 波动，并且 control-success tasks 经常丢失。

`Unknown`：现有 raw metrics 没有完成阶段校准，不能断言 reward 在 grasp、transport 或 placement 中的哪一段失效。H2 先做 observer-only rank/calibration 分析，再决定是否修改 quality 或 final selection。

### 6.4 轨迹与 chunk 连续性观察

| Job | Selected trajectory median m | Max-step median m | Chunk-boundary jump P95 |
| --- | ---: | ---: | ---: |
| control | 0.093 | 0.015 | 2.983 |
| uniform primary | 0.131 | 0.022 | 4.157 |
| sparse primary | 0.121 | 0.020 | 4.902 |
| expand20 | 0.113 | 0.019 | 3.999 |
| span12 | 0.103 | 0.018 | 3.350 |

`Inferred`：chunk-local fresh archive 可能放大 replanning discontinuity，并消耗 720-step budget。H3 必须用 paired stage-transition/continuity probes 区分因果与任务难度混杂。

### 6.5 Grid5 failure 的正确解释

历史 traceback 在 final archive selection 后使用 `best_idx` 索引 stale `last_particle_sources`，导致 `tuple index out of range`。当前 HEAD 已有 QD-aware selected-source 分支，但旧 Grid5 artifacts 仍然 invalid。

因此：

- Grid5 不是关于 5x5 discretization 的有效负结果；
- 新 preflight 必须覆盖 occupied archive size、final best index 和 source bookkeeping 的所有边界；
- runner/audit 必须把 non-qpos Python exception 与 qpos failure 分开；
- 同类 exception 在 development 也只能计为 invalid/code failure，不能计为 policy outcome。

### 6.6 定性证据限制

Task 3 contact sheet 显示 control 已完成而 QD profiles 在相同时间坐标表现不同；task 5 显示 sparse/expand20 获得 control 未有的成功。该证据支持“QD 会改变真实行为”，但单帧不能证明 archive mechanism、reward alignment 或 timeout 根因。所有视觉结论必须与 trajectory、Stage events、task outcome 和视频时间线配对。

## 7. 当前代码边界与兼容性要求

### 7.1 现有实现

- `core/qd_ed.py`：endpoint-XY descriptor、initial quantile bounds、edge clamp、capacity-one archive、uniform/sparse allocation；
- `core/rdt_policy_steer.py`：唯一 EDS loop、QD config validation、archive integration、metrics 与 final selection；
- `configs/config.yaml`：legacy-safe QD defaults；
- `scripts/eds_quality_diversity_runner.py`：旧固定 matrix、ledger、GPU/storage/credential controls；
- `scripts/eds_quality_diversity_audit.py`：validity、mechanism、safety、ranking、immutable manifest；
- `tests/test_qd_ed_archive.py` 等：archive/grid/allocation/runner/audit 回归。

规划健康检查：

```text
pytest -q \
  tests/test_qd_ed_archive.py \
  tests/test_eds_quality_diversity_runner.py \
  tests/test_eds_quality_diversity_audit.py

56 passed in 3.22s
```

### 7.2 新实现必须满足

- 旧 `qd_archive_mode=none` 和旧 `grid_archive` 固定输入保持 backward compatible；
- 所有新机制由 config-controlled mode 启用；
- no job-label branch；
- observer 不消费 global RNG、不增加 reward/model/VLM calls、不改变 selected action；
- archive tensor detached；
- complete chunk call/evaluation accounting 精确；
- nonfinite、empty archive、source mismatch、selection mismatch fail closed；
- 新 descriptor/quality/continuity metrics JSON serializable 且 checksum 稳定。

## 8. 研究问题

1. 旧 coverage 饱和是否源于 initial-bound edge clamp，而不是真实 useful-mode saturation？
2. 哪些 stage-resolved、observation-derived 变量能预测 task completion，并揭示 reward/selection 错配？
3. 能否在 176 evaluations/chunk 内同时保留 control-success behavior 与探索新 behavior？
4. 跨 chunk continuity 是否能减少 timeout 或提升 stage transition，而不压制必要探索？
5. capacity-one endpoint-XY cell 是否合并了 future value 不同的 behaviors？
6. stage-aware BD/quality/selection 的收益来自更好 archive 还是额外语义信息？
7. 改进是否在独立 development/validation seeds 上成立，而非只重现旧 formal tasks 的已知结果？

## 9. 初始可证伪假设池

优先级是启动顺序，不是对结论的承诺。Outer loop 可根据证据重排或生成子假设。

### 9.1 Structured ideation review

本假设池按 problem-first、failure-boundary、tension、decomposition 和 simplicity 五个 lenses 收敛：

- **Problem-first**：真实问题不是“QD 参数未调好”，而是已审计 QD archive 在 fixed compute 下同时丢失 mechanism claim 和 control-task retention；
- **核心 tensions**：coverage vs exploitation、proxy reward vs task progress、exploration vs chunk continuity、archive expressiveness vs 16-particle feasibility；
- **Decomposition**：把旧 monolithic outcome 分解为 partition、quality/final selection、parent ecology、cross-chunk continuity、within-cell aliasing，避免一次修改多个组件；
- **Simplicity**：每个方向先用 stored stream/observer/counterfactual 获取信号，再实现最小 online candidate；
- **Stakeholders**：研究者需要可解释机制，operator 需要 fixed compute/可恢复运行，机器人部署需要安全与当前信息约束，审查者需要完整负结果和 leakage 边界。

两句 pitch：现有 EDS-QD 能维护满覆盖 archive，却因 descriptor 饱和、proxy/selection 错配和 chunk discontinuity 而无法把多样性转化为任务完成。我们先把这三个机制连同 parent ecology 与 cell aliasing 分开证伪，再只组合得到独立支持的最小组件，从而在不扩大 primary compute 的条件下保留已知成功并探索新行为。

最强反对意见是：10 个任务与公开历史结果不足以证明新方法泛化。本文不回避该限制；新 seeds 只提供工程鲁棒性，最终仍只报告 reuse-limited fixed-set evidence，不做统计显著性或普遍优越性宣称。

发散后 parked/rejected 的方向：

1. 直接增加 population/iterations：混淆算法与 compute，保留为 `EXPLORATORY-ONLY`；
2. 首轮即训练 learned BD/CVT encoder：复杂度、数据和归因成本过高，先做 offline partition diagnostic；
3. 宽 grid/BD/capacity/allocation sweep：信息价值低且易过拟合，禁止；
4. 同时修改 checkpoint、Stage prompt 或 grounding：超出 EDS-QD 问题边界；
5. 用多个 formal candidates 或 formal failure 继续选模：构成 outcome leakage。

候选排序采用 evidence-first，而不是按新颖度或实现便利度：任何 online candidate 必须先形成 `historical evidence packet`，至少包含一个可校验的 raw metric/manifest/code-path 证据、一个 task-level 正或负 outcome，以及它们指向具体 EDS+QD 步骤的因果链；若历史 telemetry 不足，则必须先用 `QD-0` observer/offline replay 补齐，不能直接试参数。历史上已经失败的同构修改只有在新机制解释指出先前 failure boundary、并给出不同可证伪预测时才可重试。

### H1 — Descriptor partition saturation

- **证据**：valid QD coverage median `1.0`、overflow P95 `0.938–1.0`、paired coverage gain `0`。
- **机制陈述**：initial-only endpoint-XY bounds 通过 edge clamp 把不同超界行为压入同一边缘 cell，导致 occupancy 饱和但 behavior resolution 降低；因此 overflow-aware/physical partition 应降低 edge collision 并提高 cell 对 stage progress 的解释力。
- **可证伪预测**：在同一 stored candidate stream 上，替代 partition 的 overflow P95 `<=0.25`，within-cell progress variance 至少降低 20%，且有效 mode count/endpoint spread 不低于 matching control replay 的 90%。
- **最小实验**：对旧 `shadow_qd_candidate_stream` 离线 replay fixed-grid、physical fixed-bounds、rank/CVT/overflow-reservoir variants，不改变 selection。
- **Primary metric**：overflow P95、within-cell stage-progress variance、cell-to-progress effect、effective occupied modes。
- **Guardrails**：meter-scale spread、best reward、call budget、determinism、permutation equivariance。
- **支持条件**：至少两个 development tasks/seeds 同方向，并通过 offline replay exactness。
- **否证条件**：overflow 降低但 progress resolution/selection regret 不改善，或只是增大 grid 产生虚假 modes。
- **成本**：offline 0 episode；最小 online Dev-A 4 episodes/candidate。
- **成功后**：DEEPEN 到 H1.1 partition + H2 quality guard 的可归因组合。
- **失败后**：排除 bounds/partition 为主瓶颈，转向 H2/H3。

### H2 — QD quality/elitism/final selection is not stage-aligned

- **证据**：best-reward delta 约 `0`，但 task outcome 与 control retention 显著变化；最终 action 永远是 archive reward global best。
- **机制陈述**：同一 proxy reward 在 acquisition、grasp、transport、placement 阶段的排序质量不同，QD 内部的 reward-only cell elitism 与 archive-global final selection 会保留局部几何最优但 future task value 低的 action；因此 observer-validated QD quality guard、replacement 或 final elite selection 应降低 progress regret。
- **可证伪预测**：旧/Dev baseline 中 reward-top1 相对 observer progress-top1 的 regret 在至少一个阶段偏高；新 selection 在不看 future observation 的条件下使 stage transition rate 提高、control-task retention 不下降。
- **最小实验**：observer-only 记录每 candidate 的当前 observation-derived stage features，测 reward rank correlation、top-k regret 和 calibration；不先改 reward。
- **Primary metric**：stage-stratified rank correlation、top1 progress regret、next-chunk stage transition。
- **Guardrails**：final reward、safety、no privileged selection input、no additional VLM query。
- **支持条件**：错配在 Dev-A/Dev-B 与至少两个 tasks 重复，且 candidate selection 改善 transition。
- **否证条件**：reward rank 与 progress 高度一致，或 selection 改动不改善 downstream transition。
- **成本**：offline replay + 4 Dev-A episodes/candidate。
- **成功后**：DEEPEN stage-conditioned quality/selection ablation。
- **失败后**：保留 reward-only，优先 H1/H3/H4。

### H3 — Chunk-local QD state causes execution discontinuity

- **证据**：QD trajectory length 与 chunk-boundary jump 普遍高于 control；archive 每 chunk fresh。
- **机制陈述**：每个 chunk 重建 QD archive 并独立选择 reward global best，使相邻 chunk 的 archive lineage、approach direction/velocity 不连续，延迟 grasp/transport/placement；因此 QD continuity-aware tie/guard、archive seeding 或 bounded QD memory 应减少 jump 并提升 steps-to-stage-transition。
- **可证伪预测**：在 reward 不下降超过预注册 epsilon 的 candidates 间加入 continuity guard，可使 jump P95 相对 paired QD baseline 降低至少 20%，trajectory length 不高于 control 120%，且 Dev stage transition/success 不下降。
- **最小实验**：offline selected-candidate counterfactual replay；随后 continuity 仅作 tie/quality guard，不先启用 full cross-chunk archive。
- **Primary metric**：chunk-boundary jump P95、steps-to-next-stage、trajectory length、timeout rate。
- **Guardrails**：endpoint spread、reward delta、collision/drop、compute budget。
- **支持条件**：降低 jump 与更快 stage transition 同时出现；仅平滑但 task progress 下降不算支持。
- **否证条件**：jump 降低但 stage transition/timeout 无改善，或 exploration collapse。
- **成本**：offline + 4 Dev-A episodes/candidate。
- **成功后**：DEEPEN bounded memory duration/fresh reset conditions。
- **失败后**：把 discontinuity 视为相关而非主因。

### H4 — Parent ecology over-explores low-value saturated cells

- **证据**：uniform primary 丢失全部 control successes；sparse gained 1、lost 2；现有 allocation 不设 global-quality reserve。
- **机制陈述**：当 cells 已近饱和时，均匀或 inverse-visitation allocation 把大部分 16 slots 分给低价值 niches，削弱已知高质量 lineage；因此 quality-guarded exploit/explore apportionment 会提高 control retention，并保持可测探索。
- **可证伪预测**：固定 16 slots 下保留预注册 global-quality reserve 后，top lineage survival 和 control-task retention 提高，unique useful modes/endpoint spread 不低于 baseline 90%。
- **最小实验**：synthetic allocation + stored archive replay，再做一个 Dev-A candidate。
- **Primary metric**：global-elite lineage survival、offspring progress yield、gained-minus-lost tasks。
- **Guardrails**：slot total 16、RNG isolation、spread retention、no extra calls。
- **支持条件**：Dev-A/Dev-B 均不丢失 contemporaneous control successes，并至少提升一个 progress gate。
- **否证条件**：只提高 reward、但 diversity/progress/success 不改善。
- **成本**：offline + 4 Dev-A episodes/candidate。
- **成功后**：DEEPEN allocation ratio around mechanism-supported value，禁止盲 sweep。
- **失败后**：保留旧 allocation，转向 descriptor/quality。

### H5 — Endpoint-XY capacity-one cells alias future value

- **证据**：旧 BD 不含 Z、approach direction、gripper、trajectory shape、stage 或 history；每 cell capacity 固定 1。
- **机制陈述**：endpoint XY 相同的 candidates 可能具有不同 Z、approach direction、gripper readiness 或 continuity，capacity-one reward elite 会删除 future value 更高的 stepping stone；因此 stage-aware descriptor 或小容量多样 elite 应降低 within-cell behavior aliasing。
- **可证伪预测**：旧 archive 内同 cell candidates 的 stage feature/next-progress variance 显著大于跨 resampled subcells；加入一项机制维度或 capacity=2 后 progress regret 下降且 fixed-compute task evidence 改善。
- **最小实验**：stored candidate stream within-cell variance audit；只在证据支持的单个维度上构造 candidate。
- **Primary metric**：within-cell feature/progress variance、elite regret、retained lineages。
- **Guardrails**：archive memory、selection latency、fixed calls、permutation equivariance。
- **支持条件**：aliasing 可重复，且单维/容量消融解释收益。
- **否证条件**：within-cell future value 方差不高，或容量只增加 memory/latency。
- **成本**：offline + 4 Dev-A episodes/candidate。
- **成功后**：DEEPEN selected descriptor/capacity；不并行增加多个维度。
- **失败后**：保留 endpoint-XY/capacity-one。

## 10. 固定控制变量、允许搜索空间与探索边界

### 10.1 Primary adoption track 固定项

| 项目 | 值 | 标签 |
| --- | --- | --- |
| Benchmark | LIBERO-PRO OOD | `HISTORICAL-FROZEN` |
| Suite | `libero_object_swap` | `HISTORICAL-FROZEN` |
| Strict perturbation | `true`，runner 与 resolved Hydra 双验证 | `HISTORICAL-FROZEN` |
| Formal tasks | `0..9` | `HISTORICAL-FROZEN` |
| Formal seeds | `[44,235,43,546,6,621,197,87,151,548]` | `HISTORICAL-FROZEN` |
| Root seed | `0` | `HISTORICAL-FROZEN` |
| Max episode steps | `720` | `HISTORICAL-FROZEN` |
| Stage Recognition | ON | `HISTORICAL-FROZEN` |
| Gemini grounding | OFF | `HISTORICAL-FROZEN` |
| Checkpoint | 与历史 control 完整 fingerprint 一致 | `FREEZE-BEFORE-EXECUTION` |
| Control EDS initial/rollout | absolute-EEF RBF | `HISTORICAL-FROZEN` |
| Control population/iterations | `16/10` | `HISTORICAL-FROZEN` |
| Default complete-chunk budget | `176` evaluations | `PREREGISTERED-NEW` |
| Success definition | environment success，不改判定 | `HISTORICAL-FROZEN` |

### 10.2 EDS+QD 核心机制边界

允许研究的完整链路只有以下九类；其中 3–8 是 QD 主过程，优先级高于 1–2：

1. EDS initial proposal 的表示、采样与初始化；
2. EDS rollout/mutation/candidate generation，以及固定 176 evaluations 内的 population/iteration 分配；
3. QD behavior descriptor、normalization、bounds、discretization/partition；
4. QD archive 的 capacity、insertion、replacement、eviction、overflow 与 elite retention；
5. QD parent sampling、cell visitation、exploit/explore allocation 和 offspring budget；
6. QD 内部 quality/novelty/progress score、cell-local elitism 与 tie-breaking；
7. QD archive 到最终执行 action 的 elite ranking/selection；
8. 跨 chunk 的 QD archive seeding、lineage、continuity memory 与 reset；
9. 直接服务上述机制的 observer、metrics、runner、audit、replay 和可视化。

当前 observation/Stage state 可以作为 QD descriptor 或 quality 的输入，但不得修改 Stage recognizer 本身，也不得使用 future observation、成功标签或 simulator privileged state 参与在线选择。EDS 内部已有 reward 到 QD quality 的变换/组合可改；checkpoint、上游 reward/model/VLM provider 和查询次数保持不变。

### 10.3 搜索优先级与升级条件

每个新候选按下列优先级推进，不能越级发散：

| 层级 | 范围 | 进入条件 |
| --- | --- | --- |
| `QD-0` | 历史 replay、observer、counterfactual diagnostic，不改变行为 | 所有假设默认起点 |
| `QD-1` | descriptor、archive、replacement、allocation、quality、selection、QD continuity 的单点修改 | `QD-0` 给出可证伪证据 |
| `QD-2` | 两个已分别得到支持的 QD 组件组合 | 两个单组件均通过独立 split 机制 gate |
| `EDS-QD-IF` | initial proposal、mutation、rollout 或预算在 QD 接口处的修改 | QD-only 方向被否证，或连续 3 个有效 QD iterations 无 progress，且历史证据定位到接口瓶颈 |
| `EDS-QD-FULL` | EDS+QD 链路内更深的联合重构 | outer-loop 明确证明较小修改不足，并提交新的 protocol/change map |

`BROADEN` 只能从一个表内机制转到另一个表内机制；`PIVOT` 只能重写 EDS+QD 内部机制假设。任何超出本表的方向直接标记 `OUT_OF_SCOPE` 并停止，不得以 exploratory run 绕过。

### 10.4 Primary track 允许修改

在保持 legacy default 的前提下，可 config-controlled 修改：

- 第 10.2 节列出的全部 EDS+QD 步骤，包括 EDS proposal/rollout 与完整 QD archive/search/selection；
- fixed 176 evaluations 内的 population、iteration、initial/offspring budget 重分配；
- stage-aware 但只使用当前可用 observation/Stage state 的 QD descriptor/quality/selection；
- learned descriptor 或 adaptive partition，但必须先有 handcrafted/offline diagnostic 证据、无 privileged input、无额外 policy/checkpoint 训练，并单独完成机制消融；
- observer、metrics、runner、audit 与可视化，但只能服务 EDS+QD 归因。

每个 candidate 必须附 `EDS+QD change map`，逐项列出九类步骤中哪些改变、哪些冻结。默认只改一个步骤；组合只在组件分别得到机制支持后出现。必要时允许修改 EDS+QD 全部步骤，但必须由 `EDS-QD-FULL` 升级条件触发，不得一次性混改后仅凭 success 归因。

### 10.5 Exploratory-only

- 超过 176 evaluations 的 population/iterations/score call 增加；
- 额外 reward/model/VLM query；
- privileged simulator state 进入 online selection；
- full persistent episode archive；
- 非 compute-matched execution horizon/search budget。

这些结果只能诊断 EDS+QD 的 compute/privilege 上界，不能直接进入 formal primary ranking；checkpoint、prompt 或其他非 EDS+QD 模块变化连 exploratory 都不允许。

### 10.6 明确禁止

- 修改正式 tasks/seeds/success definition；
- 修改 checkpoint/backbone、视觉感知/grounding、task prompt、Stage recognizer、环境/reset、动作执行器或 evaluator；
- 引入与 EDS+QD 并列的独立 planner、policy、controller 或后处理算法；
- 根据 formal outcome 选择下一 candidate；
- 删除负结果或重命名 policy failure 为 infrastructure failure；
- job label core branch；
- credential 入命令行/Hydra/log/Git；
- 终止、暂停或抢占其他用户进程；
- 使用付费云资源或新增外部权限。

## 11. Development / Validation / Formal 隔离

### 11.1 现实限制

旧正式 tasks/seeds 的 baseline 和 QD outcomes 已知。因此新 formal 不是 pristine unseen statistical test。可信度来自：

1. 新候选不在旧 formal seeds 上迭代运行；
2. development 和 validation 使用独立 deterministic seeds；
3. formal 前锁定 code/config/ranking；
4. formal 结果不回流同周期选模；
5. 报告明确 reuse-limited 属性。

### 11.2 Seed 生成规则

新 seeds 由以下规则预注册：

```text
payload = "eds-qd-autoresearch-v1|<split>|task=<task_id>"
seed = int.from_bytes(SHA256(payload)[:8], "big") mod 1_000_000
```

`<split>` 的规范 token 固定为 `dev_a`、`dev_b`、`validation`；表格中的 `Dev-A`/`Dev-B` 仅是显示名称，不参与哈希。

所有新 seeds 与正式 seeds 不重复。

### 11.3 Development A/B

选择 tasks `[3,5,8,9]`，明确使用历史 evidence 做 stratification：

- task 3/9：control success、QD lost，作为 retention sentinels；
- task 5：control fail、sparse/expand20 gain，作为 exploration sentinel；
- task 8：control/sparse retained，作为 stable success sentinel。

| Split | Task 3 | Task 5 | Task 8 | Task 9 | 标签 |
| --- | ---: | ---: | ---: | ---: | --- |
| Dev-A | 512905 | 150741 | 463456 | 452903 | `PREREGISTERED-NEW` |
| Dev-B | 558482 | 165717 | 160148 | 160312 | `PREREGISTERED-NEW` |

Dev-A 用于快速 candidate promotion；Dev-B 只确认 Dev-A top candidates，不调阈值。

### 11.4 Validation

Validation 使用 tasks `0..9`，seeds：

```text
[41678, 829779, 856474, 666150, 876784,
 652882, 288157, 522484, 262295, 200894]
```

Validation 同轮执行 contemporaneous control 与最多 2 个冻结 candidates。看到 validation 结果后可以选择 formal winner，但不得修改 candidate 后继续使用同一 validation set。

### 11.5 Formal acceptance

Formal 只执行 contemporaneous control 与一个在 validation 后冻结的 winner：

```text
tasks: 0..9
seeds: [44,235,43,546,6,621,197,87,151,548]
```

正式结果揭示后：达标则完成 adoption audit；不达标则记录 `no_adoption`；同一 cycle 不运行 second candidate；继续研究需要 versioned new design、新 holdout seeds 和明确授权，不能借 retry reserve 追加 outcome。

## 12. Metrics、Failure Taxonomy 与 Proxy Discipline

### 12.1 Promotion vector

不把不同阶段指标事后加权成一个可被 gaming 的单分数。每个实验记录以下有序 vector：

1. validity/safety hard gates；
2. environment success、`target_gap=max(0,5-best_success_count)`、本轮新增/丢失 task 与 control-task retention；
3. 对尚未成功 task 的 stage transition / steps-to-transition；
4. hypothesis-specific mechanism metric 与 success 的方向一致性；
5. reward-to-progress rank/calibration；
6. trajectory continuity；
7. compute/model/reward/VLM calls；
8. latency/VRAM。

第 2 项是唯一优化主目标。第 3–6 项只能在 success 样本稀疏或候选 success 持平时帮助选择下一步，不能覆盖明确的 task regression；任何只改善 coverage/overflow/continuity 而不改善失败 task progress、retention 或成功数的候选，不得因机制指标好看而长期 KEEP。

### 12.2 Stage-resolved observer metrics

Observer 可以读取当前时刻已有 observation、keypoints、gripper state、Stage state 与 evaluator telemetry，但不能把 future observation 或 task success 反馈给 selection。至少记录：

- current stage；
- EEF-to-target distance；
- target acquisition threshold crossings；
- grasp proxy 与持续步数；
- transport/release/placement transition（若 telemetry 可可靠定义）；
- remaining steps；
- next-chunk stage transition；
- reward rank vs progress rank；
- top1/top-k progress regret。

任何使用 simulator privileged state 的字段只能是 `observer_only=true`，并通过测试证明不进入 policy input/selection。

### 12.3 QD/geometry metrics

- real/shadow archive coverage；
- overflow count/ratio 与 edge-cell collision；
- physical endpoint/trajectory spread；
- within-cell progress/feature variance；
- archive turnover/replacement/rejection；
- per-cell quality/progress；
- selected lineage 与 global elite retention；
- parent slots/yield；
- selected trajectory length/max-step；
- chunk-boundary jump；
- selection/EDS/Stage latency。

### 12.4 Failure taxonomy

至少区分：target not acquired、target pushed/displaced、grasp not formed、grasp lost/drop、wrong-object interaction、unstable transport、basket collision/displacement、placement/release failure、premature Stage OFF/oscillation、qpos/action execution error、policy timeout without completion、Python/code exception、infrastructure/GPU/render/API failure、unknown insufficient telemetry。

`timeout without completion` 只描述终态，不自动推断前述因果类别。视觉 annotation 必须保留 provenance 与置信度。

## 13. 五阶段研究流程

### Stage 0 — Bootstrap and historical replay

- 审计 state/findings/evidence index；
- 只读扫描 `/home/hynx/VLA-Pilot++/**` 与 `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/**`，建立 EDS+QD 相关 `data/historical-evidence-catalog.jsonl`；
- 对过去的方案、code/config、formal/dev 结果、negative/invalid runs、raw metrics、ledger、视频和报告做去重与 checksum/provenance 关联；
- 定向文献搜索：MAP-Elites/CMA-ME、uncertain/noisy QD、behavior descriptor selection、planning-time diversity、VLA inference-time search；
- 每篇保存 title/authors/year/URL/DOI、结论、局限和本任务关联；
- 从旧 raw streams 计算 H1–H5 diagnostics；
- 不运行新 episode。

### Stage 1 — Offline mechanism and instrumentation

- 新 config validation/TDD；
- deterministic synthetic populations；
- stored shadow-stream replay；
- observer non-interference；
- source bookkeeping/high-cell-index regression；
- 176 evaluation/call budget accounting；
- protocol/result commits。

### Stage 2 — Dev-A discovery

- 每个 candidate 4 tasks × 1 Dev-A seed；
- 同轮 control 先冻结；
- 最多 12 candidates；
- 每个 candidate 对应单一主要假设；
- 未过 safety/validity 立即 reject；
- Dev-A 结果只能晋级，不允许结果驱动扩大参数 sweep。

### Stage 2b — Dev-B confirmation

- 最多 4 个 Dev-A candidates；
- 使用独立 Dev-B seeds；
- 阈值、代码和 config 在 Dev-B dispatch 前冻结；
- Dev-A/Dev-B 方向不一致则 inconclusive，不进入 validation。

### Stage 3 — Validation

- contemporaneous control + 最多 2 candidates；
- 全 10 tasks、独立 validation seeds；
- 选出唯一 formal winner；
- validation 后只能修复明确 invalidity 并完整重跑同 fingerprint cell；不能修改算法后复用 validation。

### Stage 4 — Formal acceptance

- contemporaneous control + 一个 winner；
- 旧固定 tasks/seeds；
- 生成 immutable decision manifest 和 final report；
- formal 后 CONCLUDE，不回到 inner loop。

## 14. Autoresearch Inner Loop

每个 iteration 必须：

1. 验证 cwd/branch/worktree/write allowlist，读取 `research-state.yaml`、`findings.md`、统一迭代总账、pause sentinel 和 running processes；
2. 从 `historical-evidence-catalog.jsonl` 检索与当前 EDS+QD 机制最相关的正/负/invalid 历史证据；必要时只读扫描全工作区补充 catalog；
3. 按 `QD-0 → QD-1 → QD-2 → EDS-QD-IF → EDS-QD-FULL` 选最高优先级 pending hypothesis；
4. 创建 `run_NNN_<slug>`；
5. 写 `experiments/<id>/protocol.md`，包含历史证据引用、当前 best success 与 target gap、预计翻转的具体 task、假设、预测、EDS+QD change map、metrics、tasks/seeds、budget、support/refute criteria；
6. 在统一迭代总账中先追加 `PLANNED/PROTOCOL_LOCKED` 记录，再提交 `research(protocol): <id> — <hypothesis>`；
7. 做最小实现和目标测试，所有写入仅在新 worktree；
8. sanity check baseline、data/telemetry、no NaN/Inf、call accounting；
9. 运行实验并保存 raw artifacts；
10. 标记 CONFIRMATORY / EXPLORATORY / INVALID / INFRASTRUCTURE_FAILURE；
11. 写 `analysis.md`，先回答 success/retention/task-progress 是否缩小 target gap，再解释机制支持/否证、排除项和下一步；
12. 在统一迭代总账同一 iteration 条目中追加实际改动、命令、GPU、结果、artifact/checksum、迭代前后 target gap、解释和 KEEP/REVERT/PIVOT；
13. 更新 state/log/findings/trajectory；
14. 提交 `research(results): <id> — <outcome>`；
15. 检查是否触发 outer loop。

Protocol commit 必须早于 result commit。禁止在看到结果后改写 protocol；修订另建带 provenance 的 protocol version。

每轮结束前必须作出方向性结论，禁止以“需要更多探索”作为无证据默认动作：`KEEP` 要说明它如何提高成功概率；`REVERT` 要说明排除了什么；`DEEPEN/PIVOT` 要给出下一个具体失败 task 与预期翻转路径。没有 target-linked 下一步就触发 outer-loop CONCLUDE，而不是继续试参。

## 15. Autoresearch Outer Loop

触发条件：5 个有效 inner-loop experiments、连续 3 个实验没有 success/retention/失败-task progress、proxy 与 task outcome 矛盾、development/validation 方向冲突、infrastructure failures 重复、搜索退化为随机 sweep，或发现可解释多个结果的模式。

Outer loop 必须：

1. 汇总所有结果，包括 negative/invalid，并首先计算 best success、target gap、gained/lost tasks 与每个失败 task 的 progress trajectory；
2. 按 descriptor、quality、ecology、continuity、execution 分类；
3. 区分 observation 与 inference；
4. 更新 `findings.md` 的 Current Understanding / Patterns / Lessons / Open Questions；
5. 必要时只读重扫全工作区历史结果、文献或代码；
6. 只在 EDS+QD 九类核心步骤内生成/重排假设；
7. 选择 DEEPEN、BROADEN、PIVOT 或 CONCLUDE，其中 BROADEN/PIVOT 不得越出 EDS+QD scope；
8. 把 reflection、证据引用、方向和下一轮候选追加到统一迭代总账；
9. 提交 `research(reflect): <direction> — <reason>`；
10. 生成 `to_human/progress-NNN.html`（必要时 PDF）与 trajectory plot。

目标纪律：连续两个 outer-loop cycles 都没有缩小 development/validation success gap，且没有新的 task-level progress 能明确支持下一个 EDS+QD candidate 时，必须 `CONCLUDE_NO_ADOPTION_WITHIN_BUDGET` 或提交 versioned redesign 请求，不能继续无休止探索。达到正式 `>=5/10` 后必须立即 `CONCLUDE_SUCCESS`。

## 16. 实验记录、目录与 Git Protocol

### 16.1 状态文件

```text
research-state.yaml
research-log.md
findings.md
literature/
src/
data/
  baseline-evidence-index.json
  historical-evidence-catalog.jsonl
  experiment-trajectory.jsonl
docs/03_evidence/eds_qd_autoresearch/
  iteration-ledger.md
experiments/<experiment-id>/
  protocol.md
  code/
  results/
  analysis.md
to_human/current-status.md
paper/
```

`docs/03_evidence/eds_qd_autoresearch/iteration-ledger.md` 是所有 inner/outer-loop 过程的单一、面向人工审查的 canonical ledger。它按 iteration ID 顺序 append-only，顶部维护索引表；per-experiment `protocol.md`、`analysis.md` 和 raw artifacts 仍用于机器复现，但不能成为只有局部目录才看得到的唯一记录。一个 iteration 在总账未同时包含 protocol 与 result 两部分前不得标记 complete，也不得启动下一轮 online candidate。

### 16.2 每轮必记字段

统一迭代总账的每轮条目必须详细包含：

- iteration/experiment/hypothesis ID、状态与 CONFIRMATORY/EXPLORATORY 标签；
- 本轮引用的历史证据绝对路径、commit/checksum、关键数值/失败模式及其对设计的影响；
- 问题陈述、机制假设、可证伪预测、support/refute/reject gates；
- `EDS+QD change map`、逐文件算法 diff 摘要、protocol/result commit、code/config/checkpoint fingerprint 和 dirty-state；
- task/seed/split、exact command、环境 fingerprint、GPU index/UUID/snapshots、started/ended/wall time；
- baseline/candidate 全量 promotion vector、task-level outcome、机制指标、safety/compute/latency 和累计预算；
- raw artifact 路径/checksum、validity/failure taxonomy、异常、retry 与恢复 provenance；
- 结果解释、替代解释、限制、KEEP/REVERT/DEEPEN/BROADEN/PIVOT/CONCLUDE、下一步及理由；
- 若代码 revert，记录 reverted commit 与保留证据位置，绝不删除失败条目。

总账只嵌入可审查的小型表格与摘要；视频、tensor、逐步 raw log 用稳定路径和 checksum 引用。每次 protocol commit 和 result commit 都必须包含总账对应更新，从而通过 Git 时间顺序证明“先计划、后结果”。

### 16.3 Commit patterns

```text
research(init): eds-qd autoresearch libero swap ood
research(plan): freeze eds-qd autoresearch design
research(plan): constrain autoresearch to eds-qd core
research(protocol): <experiment-id> — <hypothesis>
research(results): <experiment-id> — <outcome>
research(reflect): <direction> — <reason>
research(report): <milestone>
```

不得把大视频、tensor、checkpoint/cache 加入 Git。`experiments/` 默认被仓库忽略；只对小型 protocol/analysis/metadata 做精确 `git add -f`，不得全目录 force-add。

## 17. Candidate Promotion、Rejection 与 Revert

### 17.1 Offline → Dev-A

必须：候选属于第 10.2 节 EDS+QD 九类步骤、scope level 与升级证据合法、`EDS+QD change map` 完整、引用相关历史正负证据、hypothesis-specific offline prediction PASS、legacy/QD regression PASS、observer no-effect PASS、call/evaluation accounting PASS、no nonfinite/mask/fallback/source mismatch、code/config fingerprint frozen、preflight valid。

### 17.2 Dev-A → Dev-B

必须：

- 4/4 valid records；
- safety 不劣于 paired control；
- success_count 不低于 paired control；若 success 持平，必须在 protocol 指定的至少一个失败 task 上产生可重复的 stage/task progress，且该 progress 明确指向下一轮成功翻转，不接受只有 archive proxy 改善；
- control-success sentinel retention 不出现无法解释的净退化；
- primary mechanism effect 在至少 3/4 tasks 同方向；
- trajectory/latency/call guardrails PASS。

### 17.3 Dev-B → Validation

必须：Dev-B 独立 seeds 复现 effect；Dev-A + Dev-B pooled gained-minus-lost `>=0`；候选提高 success count，或在 success 持平时对预注册失败 tasks 给出跨 seed 重复的 completion progress；hypothesis support criteria PASS；split 间不改 config/threshold；必要 ablation 已完成。

### 17.4 Validation → Formal

最多两个 candidates 按以下确定性 ranking 选一个：

1. validation success count 降序；
2. contemporaneous control success retention 降序；
3. gained-minus-lost 降序；
4. safety failures 升序；
5. hypothesis-specific mechanism margin 降序；
6. chunk jump/trajectory guardrail 降序；
7. compute/latency 升序；
8. label 字典序。

任何 invalid/safety/call-budget failure 直接 reject。被 reject code 可以保留历史 commit，但 active branch 回到最近 KEEP checkpoint；不得删除失败 evidence。

### 17.5 Goal-directed early stop

- 单个 candidate 若在 Dev-A 同时没有新增 success、没有保留优势、也没有预注册失败 task progress，立即 REVERT，不为调通 mechanism metric 追加 online runs；
- 连续 3 个有效 candidates 没有缩小任何 target-linked gap，立即触发 outer loop，不继续相邻参数试探；
- outer loop 只能保留一个最可能缩小 `target_gap` 的 next candidate；其余想法 parked；
- validation 只提升最可能达到 `>=5/10` 的候选，不为机制叙事完整而消耗 formal budget；
- formal 达标立即结束；formal 未达标按冻结规则结束本 cycle，不做 outcome-driven second candidate。

## 18. 初始实验组合与搜索节奏

初始 portfolio 不是冻结参数 sweep；它定义先获取什么信息：

| ID | 假设 | 类型 | 目的 | Episode |
| --- | --- | --- | --- | ---: |
| `run_000_baseline_replay` | H1–H5 | confirmatory audit | 复算旧 metrics/manifest/checksums | 0 |
| `run_001_partition_diagnostic` | H1 | confirmatory offline | replay overflow、within-cell progress resolution | 0 |
| `run_002_reward_calibration` | H2 | confirmatory offline | stage-stratified reward/progress alignment | 0 |
| `run_003_continuity_counterfactual` | H3 | exploratory offline | continuity guard counterfactual | 0 |
| `run_004_aliasing_audit` | H5 | confirmatory offline | within-cell future-value variance | 0 |
| `run_010_partition_candidate` | H1 | confirmatory online | 最小 evidence-selected partition | Dev-A 4 |
| `run_011_quality_guard_candidate` | H2 | confirmatory online | observer-supported selection/quality guard | Dev-A 4 |
| `run_012_continuity_guard_candidate` | H3 | confirmatory online | bounded continuity guard | Dev-A 4 |
| `run_013_ecology_guard_candidate` | H4 | confirmatory online | fixed-slot exploit/explore guard | Dev-A 4 |
| `run_014_descriptor_or_capacity_candidate` | H5 | confirmatory online | 单一 evidence-selected dimension/capacity | Dev-A 4 |

剩余 candidate slots 由 outer loop 根据证据生成，最多 12 个 Dev-A candidates。禁止一次同时 sweep 多个 BD、grid、capacity 与 allocation；组合 candidate 只有在组件各自支持后才可出现。

## 19. TDD、Regression 与 Preflight

### 19.1 必须保留的既有 tests

```text
tests/test_qd_ed_archive.py
tests/test_eds_quality_diversity_runner.py
tests/test_eds_quality_diversity_audit.py
tests/test_rdt_steer.py
tests/test_eds_eval_metrics.py
tests/test_eds_eval_runner.py
tests/test_main_rdt_startup.py
tests/test_env_adapters_imports.py
```

### 19.2 新目标 tests

- high occupied-cell count/final index/source bookkeeping；
- new descriptor/partition permutation equivariance；
- overflow/underflow and physical scale；
- capacity/replacement deterministic tie；
- quality/continuity guard no future-state access；
- observer ON/OFF bitwise equality；
- stage feature current-observation-only；
- global RNG isolation；
- call count and `176` budget；
- pause sentinel blocks dispatch；
- split/seed leakage audit；
- retry same-cell fingerprint；
- Python exception vs qpos taxonomy；
- report/manifest/checksum determinism。

### 19.3 Offline preflight

每个 candidate 输出 machine-readable JSON：input checksum、archive/selection state、call count、RNG state、mechanism prediction、support/refute gate。失败不得启动 online。

### 19.4 LIBERO mechanism preflight

在首个 Dev-A 前，仅运行 control、旧 QD reference、新机制 candidate，各 tasks `[3,5]` 一个 development preflight seed、`max_chunks=2`：

```text
3 profiles × 2 tasks = 6 unique preflight episodes
```

Preflight outcome 不参与 candidate task ranking，只验证 runtime、Stage、descriptor frame、selection、artifact、storage、GPU 与 credential pipeline。

## 20. 初始资源预算与 Attempt Ledger

### 20.1 Unique online cells

| 阶段 | Matrix | Unique episodes |
| --- | --- | ---: |
| Mechanism preflight | 3 profiles × 2 tasks | 6 |
| Dev-A | 1 control ×4 + 最多12 candidates ×4 | 52 |
| Dev-B | 1 control ×4 + 最多4 candidates ×4 | 20 |
| Validation | 1 control ×10 + 最多2 candidates ×10 | 30 |
| Formal | 1 control ×10 + 1 winner ×10 | 20 |
| **合计** |  | **128** |

### 20.2 Recovery 与 hard caps

```text
unique online cells = 128
same-cell infrastructure recovery slots <= 15
actual episode-attempt hard cap = 143
initial GPU-hour hard cap = 48 GPU-hours
paid cloud budget = 0
```

标签：`PREREGISTERED-NEW`。

若 preflight 测得单 episode 时间使 48 GPU-hours 不足，必须在首个 Dev-A 前暂停并修订预算；不得边运行边静默放宽。达到 episode 或 GPU-hour 任一 cap 后停止 dispatch，标记剩余 cells incomplete。

### 20.3 Retry

- append-only ledger 从 preflight attempt 1 开始；
- retry 只能恢复同 task/seed/config/code/checkpoint fingerprint；
- policy timeout/collision/drop/wrong object/qpos 是 outcome，不 retry；
- OOM、Xid、render corruption、API transient、artifact 损坏可在证据审计后 same-cell retry；
- 旧 attempt/artifacts 保留；
- 未使用 reserve 不得添加 candidate/outcome。

## 21. Storage 与 Artifact Layout

新 canonical root：

```text
/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/
```

Worktree link：

```text
/home/hynx/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/outputs
  -> /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/outputs
```

二者当前均未创建。执行批准后，任何 artifact/cache 前必须：canonical parent realpath 验证；experiment root 至少 50 GiB free；write/read/delete probe；若 path/link 已存在先审计且不自动删除/移动；`outputs` 必须是绝对软链接；videos/metrics/logs/Hydra/tensors/cache 落 shared2；Git 只保存小型文本；每轮生成 checksum inventory。

## 22. GPU Admission、Runtime 与 Credential

### 22.1 GPU admission

用户已授权未来 execution phase 使用物理 GPU `0..7` 中任何可用设备；该授权不改变当前 planning-only 的 `0 GPU job` 边界。新阶段不继承旧 GPU 5 co-location exception，所有卡统一动态 admission：

- 连续两次 snapshot；
- 记录 index、UUID、model、total/free VRAM、utilization、compute mode、process list；
- 无外部 compute process；
- utilization `<=5%`；
- `free_vram >= max(1.25*reference_peak, reference_peak+4096 MiB)`；
- 每 GPU 最多 1 worker；
- concurrency `<=min(8, eligible_slots)`，可以使用全部八张合格 GPU；
- dispatch 前再次确认；
- 不终止、暂停、修改或抢占外部进程。

并行只允许展开同一个已冻结 protocol 中相互独立的 task/seed/control cells；不能提前并行运行尚未经过上一轮 KEEP/REVERT 决策的未来 candidates。GPU index 只用于调度，provenance/rerun 以 UUID 为准。48 GPU-hour cap 按所有设备 wall time 求和，不因并行而放宽。

Checkpoint fingerprint、reference VRAM peak、CUDA/driver/container/environment fingerprint 均为 `FREEZE-BEFORE-EXECUTION`。

### 22.2 Credential

- Stage credential 只由运行时环境变量注入；
- health check 不回显 token；
- command line/Hydra/manifest/ledger/log/report/Git 不含 credential；
- artifact 与 Git diff 在每个 milestone 扫描 credential-like pattern；
- 发现泄漏立即停止、隔离 evidence，并请求用户轮换；不得传播泄漏值。

## 23. 暂停、恢复与 Continuity Loop

### 23.1 Pause sentinel

执行阶段约定：`.autoresearch/PAUSE`。

用户发送“暂停/停止/先别继续”或 sentinel 存在时：不启动新 attempt；记录时间与原因；只检查本研究 PID/job；优雅等待或停止本研究拥有的进程；不影响其他用户进程；更新 state/log/current-status；保存 active experiment、artifact、PID、task/seed/fingerprint；给出恢复命令。

### 23.2 Resume checklist

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood
git status --short --branch
test ! -e .autoresearch/PAUSE
```

随后读取 `research-state.yaml`、`findings.md`、`research-log.md`、统一迭代总账、historical evidence catalog、`to_human/current-status.md`、最新 protocol/analysis、attempt ledger、owned process/artifact status。有效 completed cells 不重复。

### 23.3 Automatic continuity

用户已明确同意后续正式执行阶段启用 automatic continuity，但当前 planning phase 禁止创建。设计批准后可使用：

```text
/loop 20m Continue EDS-QD autoresearch in /home/hynx/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood. Work only on EDS+QD core mechanisms and prioritize QD. Read research-state.yaml, findings.md, the canonical iteration ledger, and historical evidence catalog first. Treat every other worktree/workspace path and all historical shared2 artifacts as read-only. Check .autoresearch/PAUSE and owned jobs. Continue the active experiment without duplication; if stalled, rescan historical EDS+QD evidence or run an in-scope outer-loop reflection. Append every protocol, change, result, artifact, decision, and next step to the canonical ledger. Never start formal evaluation before the frozen promotion gates authorize it.
```

Loop 是 wall-clock nudge，不是 research phase boundary。实验未完成时只检查健康，不重启/复制。

## 24. Formal Evaluation Protocol 与 Gates

### 24.1 Frozen matrix

```text
2 jobs × 10 tasks × 1 episode = 20 unique formal episodes
```

Jobs：`p2_stage_on_abs_rbf_control` contemporaneous control，以及 validation 后冻结的唯一 primary winner。

### 24.2 Validity gate

- 10/10 records；
- 10 unique ffprobe-readable videos；
- suite/strict/task/seed/code/config/checkpoint fingerprints 匹配 manifest；
- complete logs/Hydra/metrics/Stage/qualitative artifacts；
- shared2 realpath 正确；
- 0 nonfinite、0 mask violation、0 unexplained fallback；
- selection/accounting/source bookkeeping 一致；
- credential scan PASS。

### 24.3 Task gate

```text
candidate_success_count >= 5
candidate_success_count >= contemporaneous_control_success_count
paired_gained_tasks >= paired_lost_tasks
```

### 24.4 Mechanism audit

所有 candidates 必须报告 hypothesis-specific offline prediction 是否在 formal telemetry 中同方向；同时要求 no accounting/selection/RNG violation、primary track 无额外 calls、required ablation 在 formal 前完成、mechanism metrics 不依赖 post-outcome threshold change。

不得继续使用旧固定 coverage `delta>=0.05` 作为所有新 candidates 的通用机制 gate；新 gate 必须在每个 protocol 中由对应 hypothesis 冻结。

该审计用于解释“为什么成功/失败”和检查实现可信度。预期机制不同方向本身不否决一个真实、有效且安全的 `>=5/10` 结果；但 accounting、selection、RNG、privileged input、leakage 或 post-outcome threshold change 属于 validity failure，必须否决。

### 24.5 Safety/compute gate

```text
nonfinite = 0
action-mask violation = 0
unexplained algorithm fallback = 0
qpos/execution error episodes = 0
collision/push/drop/wrong-object composite <= control
complete-chunk evaluation/call budget = frozen primary budget
GPU-hour and attempt caps not exceeded
```

## 25. Ranking 与 Adoption Rule

Formal 只含一个 candidate，不做 outcome-driven multi-candidate ranking。Acceptance 硬门顺序：validity；success `>=5/10`；not below control；gained-minus-lost；safety；compute/latency；artifact/credential。Mechanism audit 决定结论措辞，不在没有 validity 问题时覆盖真实 task success。

全部通过：

```json
{"decision":"adopt_eds_qd_autoresearch_winner","recommended_for_adoption":true}
```

任一失败：

```json
{"decision":"no_adoption_keep_contemporaneous_control","recommended_for_adoption":false}
```

不得因为 candidate 达到 5/10 就忽略 invalid/safety/compute/artifact failure；也不得因为预期机制未被证实就抹去一个通过全部硬门的真实成功结果。通过硬门后立即停止搜索并生成最终交付。

## 26. Progress Reports、Final Manifest 与完成条件

### 26.1 Human-facing progress

在 outer-loop 发现重要模式、trajectory 持续提升、PIVOT、validation 前、formal/conclusion 时生成 `to_human/progress-NNN.html`，必要时 PDF。报告包含问题、trajectory、关键结果、失败 decision map、当前理解和下一步；presentation 不替代 append-only audit。

### 26.2 Immutable manifests

```text
manifests/research_run_manifest.json
manifests/episode_attempt_ledger.jsonl
manifests/formal_decision_manifest.json
manifests/formal_decision_manifest.json.sha256
```

Decision manifest 写入后 mode `0444`，修正只能新建 version。包含 base/init/protocol/result commits、splits/seeds、all candidates、negative/invalid outcomes、gates、task matrix、checksums、GPU provenance、budget 和 final decision。

### 26.3 完成条件

本 planning task 完成：新 branch/worktree 建立；autoresearch state/log/findings/trajectory 初始化；本文完成并提交；CPU health tests PASS；Git diff/status/credential scan PASS；0 GPU/LIBERO/scheduled loop。

未来 execution task 完成：approved matrix 全部完成或在 hard cap 内明确 incomplete；final gates/manifest/report 完成；state 标记 concluded；owned processes 清理；结论按证据边界准确表述。

## 27. 明确排除项、主要风险与待冻结决策

### 27.1 排除项

- 对正式 seeds 反复调参；
- formal second candidate；
- 无机制解释的宽 sweep；
- 未经 `EDS-QD-FULL` 升级、独立组件证据和 change map 就同时改变 descriptor、quality、allocation、memory 和 compute；
- 修改 checkpoint/success/tasks/seeds；
- 转向 EDS+QD 之外的算法模块；
- privileged future state 进入 selection；
- 旧 shared2 产物覆盖；
- Superpowers plugin/skills；
- 付费云、外部协调或越权资源操作。

### 27.2 主要风险

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 正式 set 已有历史曝光 | 结果可能过拟合固定 tasks | 新 dev/validation seeds、formal 一次性冻结、明确 reuse-limited |
| 10 tasks 方差高 | 5/10 可能是偶然工程波动 | paired control、independent validation、task-level 报告 |
| Stage/runtime instability | attempt 浪费/invalid | 6-episode preflight、health check、same-cell audited retry |
| GPU/render/Xid | artifact 损坏 | admission、snapshots、ledger、checksum、15 recovery cap |
| proxy gaming | mechanism 指标升但 task 不升 | promotion vector、success/retention 优先、formal gate |
| 组合爆炸 | autoresearch 退化为 sweep | 单假设最小修改、最多 12 Dev-A candidates、outer-loop gating |
| 轨迹平滑压制探索 | progress 下降 | reward/spread guard、counterfactual 先行 |
| 新 BD 使用 privileged 信息 | 不可部署提升 | observer/selection 数据流测试、fail closed |

### 27.3 执行前必须冻结

以下当前为 `FREEZE-BEFORE-EXECUTION`：

1. 设计状态从 Draft 更新为 Approved；
2. checkpoint 完整 fingerprint 与加载路径；
3. GPU reference peak/environment fingerprint；
4. Stage credential health（不记录 credential）；
5. 新 storage root/link/write probe；
6. development/validation/formal manifest checksum；
7. 48 GPU-hour估算是否足够；
8. runner 对 pause sentinel、attempt cap 与 split leakage 的测试；
9. continuity loop 实际创建与验证（只能在 execution approval 后）。

本文批准后，routine inner/outer-loop 决策不再逐次请求人工确认；用户可随时通过消息或 pause sentinel 中断。任何超出 search space、budget、formal policy、权限或安全边界的变更必须停止并请求新授权。
