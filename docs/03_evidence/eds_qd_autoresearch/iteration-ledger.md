# EDS+QD Autoresearch 统一迭代总账

状态：`EXECUTING — run_002 H1 causal-envelope protocol locked — 0 algorithm iterations`

本文件是 EDS+QD autoresearch 所有 inner-loop 与 outer-loop 过程的单一人工审查入口。所有条目按 iteration ID append-only；不能删除、覆盖或为改善叙事而重写负结果、invalid attempt、infrastructure failure 或 revert 记录。大型 raw artifacts 不嵌入 Git，但必须以稳定路径和 SHA-256 引用。

## 总索引

| Iteration | 日期 | Scope level | 假设 | 修改摘要 | Split / tasks | 结果 | 决策 | Protocol commit | Result commit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `run_002_partition_diagnostic` | 2026-08-10 | `QD-0` | H1 | fixed-initial vs 单一 `causal_envelope_v1` 4x4 partition replay | 27 frozen files；4x4 eligible chunks；task strata 3/5/8/9 | `PROTOCOL_LOCKED`；尚未执行 | pending | pending this commit | — |
| `run_001_allocation_ecology_diagnostic` | 2026-08-10 | `QD-0` | H4 | saved-trace parent-quality inheritance 与 saturated slot audit | 540 traces / 9,000 stages；task strata 0–9 | 2 attempts `INVALID`；无可采纳 H4 outcome | `INVALID_CONCLUDE_AND_TRIGGER_OUTER_LOOP` | v1 `dcf234b…`; v2 `91ddd34…`; v3 `f6d7bc9…`; v4 `3d320f6…` | `cdd150b2c332e907c05cda90c7c09fd1f1799570` |
| `run_000_baseline_replay` | 2026-08-10 | `QD-0` | H1–H5 | 只读回放旧 QD 与预算 sweep，验证 target-linked failure boundary | historical only | 6/6 gates PASS；4,705 QD chunks；budget max 1/10 | `KEEP_DIAGNOSTIC_EVIDENCE` | `5255e924ee925487406e35a27548d9db4e988642` | `e0b252c983a3b62858c8fa676e7b32618660b364` |
| — | 2026-08-10 | — | — | 执行授权；尚未开始算法迭代 | — | — | `APPROVED_EXECUTING` | — | — |

## 累计状态

- 当前 best formal candidate：无。
- 当前 best formal success：未运行。
- 历史 best EDS-QD success：`2/10`。
- 当前 target gap：`5 - 2 = 3` tasks。
- 新在线 episodes：0。
- GPU jobs：0。
- Formal evaluations：0。
- 累计 GPU-hours：0。
- Attempt budget：`0 / 143`。
- 已结束新实验：2 个 `QD-0`（1 complete，1 invalid）；另有 1 个 `QD-0` protocol locked；算法迭代仍为 0。
- 当前结论：`run_002` 只允许 `causal_envelope_v1` 一个 H1 partition counterfactual；其结果决定 QD-1 go/no-go。Formal evaluation 仍未授权。

### `run_001_allocation_ecology_diagnostic` — 饱和 archive 的 parent 质量继承与 slot 生态

#### A. 身份与状态

- 日期与 UTC 时间：`2026-08-10T15:20:46Z`。
- Inner/outer loop：inner loop 1。
- 状态：`INVALID`；标签 `INFRASTRUCTURE_FAILURE`。
- 标签：`CONFIRMATORY`。
- 假设 ID：H4。
- Scope level：`QD-0`。
- 迭代前 best success / target gap：历史 EDS-QD `2/10`；gap 3。
- 本轮预计翻转的失败 task：本轮零 episode、不翻转；若支持，唯一未来 QD-1 候选预期恢复 task 3 或 9，并保留 5/8。

#### B. 历史证据与问题来源

| 绝对路径 | Commit / SHA-256 | 原始数值或失败模式 | 证据等级 | 对本轮设计的影响 |
| --- | --- | --- | --- | --- |
| owned `run_000_baseline_replay/analysis.json` | `6ad13083…963` | 4,705 chunks；100% archive-only parents；0 direct elites | confirmatory replay | 从缺少 quality reserve 推进到 offspring yield 检验 |
| budget `num_elites_no_op_audit.json` | `f75e48c5…120` | non-CEM QD 的 `num_elites` 无行为作用 | code/behavior audit | 不把现有参数误认为 exploitation |
| original sparse `mechanism_trace.pt` example | `0d3d4d8f…174` | child reward、parent rank/index、slot telemetry 齐全 | raw tensor trace | 支持 0-episode counterfactual |
| `core/qd_ed.py` | Git blob `a9138b1f…bd13` | uniform/inverse-visitation allocation 无 reward weight | source evidence | 锁定 H4 mechanism chain |

- 已检索 catalog/query：`run_000` 27 profile summaries、mechanism trace schemas、archive timeline、elite survival metadata、QD allocation source。
- 相冲突证据：archive 已做 cell-local reward elitism且最终选 global best；所以 zero direct carryover 本身不是 defect，必须验证 parent-quality inheritance。
- 为什么没有重复已知失败：本轮不增加 population/iterations、不在线试 reserve ratio；只检验一个决定是否值得实现的因果前提。

#### C. 锁定假设与判据

- 机制陈述：饱和 archive 的 quality-blind slot allocation 欠采样高质量 parent；若 reward quality 可继承到 offspring，则固定 quality reserve 更可能保留已知成功模式。
- 可证伪预测：top ranks 获得 `<=35%` slots；top-quartile child reward 高于 bottom；cluster-bootstrap CI lower `>0`；uniform/sparse family median 均 `>0`；rank-1 margin `>0`。
- Primary metric：per-trace top-minus-bottom child reward margin；secondary 为 slot share、rank-1 margin、task subgroup。
- Support/refute gates：详见 per-run protocol；任一 H4 gate fail 均禁止 H4 online candidate。
- Safety/compute guardrails：540 immutable traces；0 episode/GPU/model/environment calls；local RNG seed 1701。
- 替代解释：reward inheritance 可能只延续 proxy bias；saved offspring 不能直接模拟未生成的 extra children；task success subgroup 样本少。

#### D. EDS+QD change map

| EDS+QD 步骤 | Frozen / Changed | 修改内容 | 文件/符号 | 归因理由 |
| --- | --- | --- | --- | --- |
| EDS initial proposal | Frozen | none | — | 不改变行为 |
| EDS rollout/mutation/budget | Frozen | saved offspring only | planned analyzer | 检验 fixed-budget yield |
| QD descriptor/partition | Frozen | condition on full archive | trace `qd_info` | 隔离 saturation |
| QD archive/replacement | Frozen | read ranks | trace stages | 识别 parent quality |
| QD parent/allocation | Frozen | audit slots/yield | planned analyzer | H4 核心 |
| QD quality/elitism | Frozen | existing reward rank only | trace stages | 不引入新 score |
| QD final selection | Frozen | none | — | 无执行 counterfactual |
| QD cross-chunk state | Frozen | subgroup only | path metadata | 不发散 |
| EDS+QD instrumentation | Changed | deterministic CPU analyzer | `src/analyze_qd_allocation_ecology.py`（protocol 后实现） | 形成 QD-1 go/no-go evidence |

- 明确冻结的非 EDS+QD 模块：checkpoint、perception、prompts、Stage、environment/reset、executor、evaluator。
- 逐文件 diff 摘要：本 protocol commit 仅新增 protocol 并更新 ledger/state/log/status；无 analyzer 或算法实现。
- Protocol commit v1：`dcf234b6999165de0a5bca4a8e44332896cc61dc`。
- Protocol v2 amendment：`91ddd34f64d129549147f42c64244b552398a624`。v1 把所有 trace 按原始 10 iterations 相乘而误写 5,400 stages；implementation 前按各 profile `cem_iters` 修正为 9,000。修订前未计算 reward margin、bootstrap、slot share 或 gate outcome；其余 hypotheses/gates 不变。
- Invalid attempt：首次 analyzer 找到 540 files / 9,000 stages，但错误地把 budget population occurrence ranks `1..N` 限制为 archive-cell ranks `1..16`，从而拒绝 360 traces；artifact SHA-256 `c59cbe97…24b5`。该次 H4 数值全部不可采信。
- Protocol v3 repair：`f6d7bc9a1d579fcbb55e36905beafd1a2ba8264c`。按 source 的 sorted-cell/repeated-slot 顺序重建 child-to-cell，并用每 cell mean occurrence rank 定义 16-cell quality quartiles；所有原 thresholds 不变。
- Protocol v4 temporal alignment：`3d320f6a143a74cbc31625f2f12ccdd77995c7f4`。两个 single-file precheck 发现 slot allocation 发生在 archive update 前，而 coverage 指标记录在 update 后；故用实际 parent slot map 的 16 个正计数 cells 定义饱和，排除 15→16 transition iteration。未运行 aggregate H4 statistics，原 thresholds 不变；这是本轮最后一次 schema amendment。
- Code/config/checkpoint fingerprint：QD blobs `a9138b1f…bd13` / `1354e26c…dd95`；checkpoint 不加载。
- Protocol-lock 时 Git dirty-state：仅禁止修改的用户 untracked stage-guidance design；无算法 diff。

#### E. 执行协议

- Split/tasks/seeds：540 historical saved traces；task IDs 0–9 仅作 descriptive strata。
- Exact command：见 `experiments/run_001_allocation_ecology_diagnostic/protocol.md`。
- 环境 fingerprint：`vla-pilot` CPU PyTorch loader；local bootstrap RNG。
- GPU index/UUID：不适用。
- Expected evaluations/model/reward/VLM calls：全部 0。
- Started / ended / wall time：尚未开始。

#### F. 结果

| Attempt | Result | Accounting | Failure | Artifact |
| --- | --- | --- | --- | --- |
| initial | INVALID | 27 profiles / 540 traces / 9,000 stages | occurrence rank 被误当 16-cell rank；360 budget traces rejected | `c59cbe97…24b5` |
| v4 recovery | INVALID | 27 / 540 / 9,000；374,400 children | 52 sparse traces 有合法 zero-slot cells，违反 v4 analyzer validity assumption | `489a7156…fda0` |

- Promotion vector：validity FAIL；所有 H4 reward/slot/task subgroup values inadmissible；无 success、retention 或 task progress 结论。
- 迭代后 best success / target gap：`2/10` / 3，不变。
- Raw artifacts：owned `run_001_allocation_ecology_diagnostic/{analysis.json,repaired_v3/analysis.json}`；完整 hashes 见 per-run analysis。
- Failure taxonomy：两次 `INFRASTRUCTURE_FAILURE`；无环境/算法/safety outcome。
- 本轮与累计 budget：0 episodes，0 GPU-hours；attempt `0/143`。

#### G. 分析与决策

- 观察事实：trace file/stage/root accounting 均正确；telemetry 的 occurrence-rank/cell-rank、pre/post-update occupancy、zero-slot semantics 不能由原 analyzer 假设安全合并。
- Target gap：未缩小；零在线 task evidence。
- H4：unresolved，不支持也不否证；本 cycle 不授权 H4 online candidate。
- 决策：`INVALID_CONCLUDE_AND_TRIGGER_OUTER_LOOP`，遵守 v4 禁止继续 repair。
- Result commit：`cdd150b2c332e907c05cda90c7c09fd1f1799570`。
- 下一步：outer-loop reflection 后 pivot 到 H1 partition diagnostic，以 JSONL descriptor stream 直接回答 overflow/aliasing，不继续 trace analyzer 探索。

#### H. Outer-loop reflection 001

- 触发原因：`run_001` 连续两次 infrastructure validity failure；继续修 analyzer 将偏离 `>=5/10` 第一目标。
- 全部结果：`run_000` 为 positive diagnostic、target gap 不变；`run_001` invalid、无算法结论、target gap 不变；无 negative online candidate。
- Task trajectory：仍只有历史 control `{3,8,9}` 与 best QD `{5,8}`；新 gained/retained/lost task 均为空。
- Descriptor evidence：13/13 hashes、4,705 JSONL chunks、coverage median 1.0、raw overflow P95 0.875、profile overflow P95 0.98125；证据有效且可直接 replay。
- Quality/ecology evidence：run_000 证明无 direct elite reserve 与 archive-only parent source；但 run_001 无有效 quality-inheritance gate，H4 parked，不能 online。
- Continuity evidence：历史 clean-tail 在 motion 更平滑时 success `3→2→0`，不是第一方向。
- Execution/Stage：冻结且 out of scope，不作为 pivot。
- Observation：initial-bound endpoint partition 将大量 later offspring clamp 到 edges，同时 coverage 已无法区分 useful modes。
- Inference：比继续修 trace 或堆 compute 更可能产生最小可归因 QD-1 的方向，是 overflow-aware/physically stable partition；仍需 counterfactual 证明它提高 resolution，而非仅改变 coverage 数字。
- 方向：`PIVOT_WITHIN_EDS_QD_TO_H1_PARTITION`。
- 下一轮唯一候选：`run_002_partition_diagnostic`，零 episode；若支持，未来单点 QD-1 预期保留 tasks 5/8 并恢复 3 或 9；若不支持，H1 reject 而不 sweep grids/bounds。
- Human report：`to_human/progress-001.html`。

### `run_000_baseline_replay` — 历史基线与预算扩展回放

#### A. 身份与状态

- 日期与 UTC 时间：`2026-08-10T15:05:31Z`。
- Inner/outer loop：inner loop 0，bootstrap diagnostic。
- 状态：`COMPLETE`。
- 标签：`CONFIRMATORY`。
- 假设 ID：H1–H5；本轮只审计，不一次性宣称全部成立。
- Scope level：`QD-0`。
- 迭代前 best success / target gap：历史 EDS-QD `2/10`；`5 - 2 = 3` tasks。
- 本轮预计翻转的失败 task：无；零 episode 诊断。本轮直接服务于删去无效方向并选择一个最可能翻转 task 3/5/8/9 的下一 QD 机制。

#### B. 历史证据与问题来源

| 绝对路径 | Commit / SHA-256 | 原始数值或失败模式 | 证据等级 | 对本轮设计的影响 |
| --- | --- | --- | --- | --- |
| `/home/hynx/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-06-eds-quality-diversity-report.md` | `cbaa9df…16c` | control 3/10 `{3,8,9}`；best QD 2/10 `{5,8}` | audited report | 锁定 task matrix 与 retention gap |
| `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/analysis/qd_ed_formal_audit.json` | `56c4320e…ba` | coverage 1.0、overflow 高、reward delta 近零 | audited raw | 回放 descriptor/ecology/quality 指标 |
| `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/outputs/search_budget_sweep_20260808/analysis/final_report.md` | `580cf8c0…c1e` | 18 configs 均为 0/10 或 1/10 | audited report | 检验并预期排除直接扩预算 |
| `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/outputs/search_budget_sweep_20260808/analysis/formal_audit.json` | `ff7a86b3…9f7` | 180 cells；201 physical attempts；超旧 cap 1 次 | audited raw with exception | 异常必须保留，不能把 sweep 当干净 acceptance |
| `/home/hynx/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-03-p2-rollout-clean-tail-parameter-sweep-report.md` | `7eeb573e…fd8c` | jump/长度下降但 success `3→2→0` | audited report | 排除通用平滑作为第一候选 |

- 已检索 catalog/query：`data/historical-evidence-catalog.jsonl`；原始 baseline formal metrics；search-budget manifests/audit/metrics；相关 EDS 报告。
- 相冲突证据：sparse 新增 task 5；budget sweep 偶发 task 0/7/8/9，但没有单调 compute benefit 或 control retention。
- 为什么没有重复已知失败：本轮明确不运行 grid/population/iteration sweep，只对 immutable artifacts 做 deterministic replay。

#### C. 锁定假设与判据

- 机制陈述：当前 QD 同时表现为 endpoint-cell coverage 饱和、edge overflow 和零 direct elite carryover；更多计算没有弥补质量保留/生态分配缺口。
- 可证伪预测：原 task matrix 精确复现；budget sweep max `<=1/10`；coverage median `>=0.9` 且 overflow P95 `>=0.75`；至少 95% 可解析 QD chunks 的 direct elite carryover 为 0；compute 与 success 无正单调关系。
- Primary metric：逐 profile 的 task success、validity、eval/chunk、coverage、overflow、turnover、reward delta、parent source、elite carryover。
- Support gate：见 `experiments/run_000_baseline_replay/protocol.md` 六项冻结 gate。
- Refute/reject gate：checksum/task matrix/determinism mismatch 即 `INVALID`；发现有效 `>=5/10` 立即停下审计；缺字段只标 unresolved。
- Safety/compute guardrails：0 online episodes、0 GPU-hours、无模型/environment/reward/VLM/action call。
- 替代解释：historical fixed formal exposure、budget sweep 无 contemporaneous control、reward telemetry 未必等价 stage progress。

#### D. EDS+QD change map

| EDS+QD 步骤 | Frozen / Changed | 修改内容 | 文件/符号 | 归因理由 |
| --- | --- | --- | --- | --- |
| EDS initial proposal | Frozen | read-only | — | 不改变行为 |
| EDS rollout/mutation/budget | Frozen | audit only | planned replay script | 排除无效 compute scaling |
| QD descriptor/partition | Frozen | audit only | planned replay script | 检验 saturation/overflow |
| QD archive/replacement | Frozen | audit only | planned replay script | 检验 turnover/reward |
| QD parent/allocation | Frozen | audit only | planned replay script | 检验 source/elite retention |
| QD quality/elitism | Frozen | audit only | planned replay script | 识别 quality gap，不修改 |
| QD final selection | Frozen | 无 counterfactual execution | — | 防止 outcome leakage |
| QD cross-chunk state | Frozen | 不评估 | — | 不发散 |
| EDS+QD instrumentation | Changed | deterministic historical parser | `src/replay_historical_eds_qd.py`（protocol 后实现） | 形成可复核 evidence packet |

- 明确冻结的非 EDS+QD 模块：checkpoint/backbone、perception/grounding、prompts、Stage recognizer、environment/reset、executor、evaluator。
- 逐文件 diff 摘要：protocol commit 仅新增 catalog/protocol 与状态记录；result commit 新增 `src/replay_historical_eds_qd.py` 和本轮 `analysis.md`，只读解析 historical audit/metrics；无算法行为修改。
- Protocol commit：`5255e924ee925487406e35a27548d9db4e988642`。
- Code/config/checkpoint fingerprint：`core/qd_ed.py` Git blob `a9138b1f…bd13`；`core/rdt_policy_steer.py` Git blob `1354e26c…dd95`；checkpoint 不加载。
- Protocol-lock 时 Git dirty-state：仅用户保留且禁止修改的 untracked `docs/01_specs/2026-08-10-eds-qd-stage-guidance-transition-design.md`；无算法 diff。

#### E. 执行协议

- Split/tasks/seeds：historical immutable records only。
- Exact command：见 per-run protocol；输出只写 owned artifact root。
- 环境 fingerprint：CPU/offline parser；Git HEAD before protocol `d35170073c8ef12d035f854446c439dcfeec1efe`。
- GPU index/UUID 与 admission snapshots：不适用。
- Expected evaluations/model/reward/VLM calls：全部 0。
- Started / ended / wall time：timed deterministic replay `2026-08-10T15:15:49Z → 15:15:55Z`；wall `6.16 s`，CPU `5.71 s`，max RSS `271,376 KiB`。另有 protocol-required independent repeat，canonical JSON hash 相同。

#### F. 结果

| Historical profile/config | Control outcome | Candidate outcome | Mechanism metric | Safety | Calls | Validity |
| --- | --- | --- | --- | --- | --- | --- |
| original uniform primary | `{3,8,9}` | `{}` = 0/10 | coverage 1.0；overflow P95 0.9375 | PASS | historical 176 eval/full chunk | valid |
| original sparse primary | `{3,8,9}` | `{5,8}` = 2/10 | coverage 1.0；overflow P95 0.9375 | PASS | historical 176 eval/full chunk | valid |
| budget uniform family, 9 configs | historical control only | each 0/10 or 1/10；union `{7,9}` | eval/chunk 512–1664；success/eval Spearman -0.2598 | PASS | historical only | 9/9 valid |
| budget sparse family, 9 configs | historical control only | each 0/10 or 1/10；union `{0,8}` | eval/chunk 512–1664；success/eval Spearman +0.2598 | one qpos episode at p64/k20 | historical only | 9/9 base-valid; safety exception preserved |

- Promotion vector：offline validity 6/6 gates PASS；environment success 不变；target gap 不变；no new/lost tasks；机制诊断支持但未授权 online promotion。
- 迭代后 best success / target gap：历史 `2/10`；gap `3`，均不变。
- 实际新增、保留与丢失 tasks：新实验无 task execution；历史 sparse 对 control 为 gain `{5}`、retain `{8}`、loss `{3,9}`。
- Raw artifact：`/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_000_baseline_replay/analysis.json`，SHA-256 `6ad1308363a512c9b2529a090682669bb096d5000159571d5798ddd296bad963`；summary SHA-256 `e0defa0b535d27cca8c84a3085d4958cbf1de98baf8d621a6ef82d2eea79f245`。
- Failure taxonomy / exception：本轮无 failure；保留历史 budget-sweep `201 > 200` physical-attempt exception 与一个 qpos safety episode。
- Retry/recovery provenance：无在线 retry；三个 replay 的 canonical JSON SHA-256 一致。
- 本轮与累计 episode/GPU-hour budget：`0/0`；累计 attempt `0/143`，GPU-hours `0/48`。

#### G. 分析与决策

- 观察到的事实：13/13 catalog hashes；27/27 metrics files；4,705/4,705 records 为 zero direct elite carryover 且 archive-only parents；3,281,360 archive-parent selections 对 0 direct-elite selections；coverage median 1.0；raw overflow P95 0.875；18 个 budget configs 最大 1/10，总 success/eval Spearman 0.0。
- 本轮是否缩小 `>=5/10` target gap：否，零 episode 诊断，gap 保持 3。
- 对机制假设的支持/否证：H1 和 H4 获诊断支持；H2/H5 unresolved；H3 因 clean-tail `3→2→0` 被降级但未否证。
- 替代解释与限制：budget sweep 没有 contemporaneous control；formal mapping 已曝光；archive reward 不是 stage progress；overflow 仍可能包含 useful exploration。
- 决策：`KEEP_DIAGNOSTIC_EVIDENCE`。保留的是可复核 failure boundary，不是算法候选。
- Reverted commit：不适用，无行为修改。
- Result commit：`e0b252c983a3b62858c8fa676e7b32618660b364`。
- 下一步及理由：锁定 `run_001_allocation_ecology_diagnostic`。历史 task loss 表明 retention 是直接 target gap；raw mechanism traces 可在 0 episode 下检验 quality-blind slots 与 elite lineage，符合 protocol 的预提交优先顺序。

## Execution authorization

- UTC：`2026-08-10T15:00:35Z`。
- Frozen design commit：`1aee76489ea8989a832dec49b747239f2db90981`。
- State transition：`paused/design_review → active/bootstrap_historical_replay`。
- 授权范围：按冻结方案自主执行 EDS+QD autoresearch；GPU 0–7 动态准入；routine inner/outer-loop decisions 不逐次请求确认。
- 未改变：target `>=5/10`、split/formal/budget/write-boundary、安全与暂停规则。
- 授权时计数：algorithm iterations 0、online episodes 0、GPU jobs 0、formal evaluations 0、GPU-hours 0。

## 条目模板（每轮复制并追加）

### `run_NNN_<slug>` — `<title>`

#### A. 身份与状态

- 日期与 UTC 时间：
- Inner/outer loop：
- 状态：`PLANNED | PROTOCOL_LOCKED | RUNNING | COMPLETE | INVALID | PAUSED`
- 标签：`CONFIRMATORY | EXPLORATORY | INFRASTRUCTURE_FAILURE`
- 假设 ID：
- Scope level：`QD-0 | QD-1 | QD-2 | EDS-QD-IF | EDS-QD-FULL`
- 迭代前 best success / target gap：
- 本轮预计翻转的失败 task：

#### B. 历史证据与问题来源

| 绝对路径 | Commit / SHA-256 | 原始数值或失败模式 | 证据等级 | 对本轮设计的影响 |
| --- | --- | --- | --- | --- |

- 已检索 catalog/query：
- 相冲突证据：
- 为什么没有重复已知失败：

#### C. 锁定假设与判据

- 机制陈述：
- 可证伪预测：
- Primary metric：
- Support gate：
- Refute/reject gate：
- Safety/compute guardrails：
- 替代解释：

#### D. EDS+QD change map

| EDS+QD 步骤 | Frozen / Changed | 修改内容 | 文件/符号 | 归因理由 |
| --- | --- | --- | --- | --- |
| EDS initial proposal |  |  |  |  |
| EDS rollout/mutation/budget |  |  |  |  |
| QD descriptor/partition |  |  |  |  |
| QD archive/replacement |  |  |  |  |
| QD parent/allocation |  |  |  |  |
| QD quality/elitism |  |  |  |  |
| QD final selection |  |  |  |  |
| QD cross-chunk state |  |  |  |  |
| EDS+QD instrumentation |  |  |  |  |

- 明确冻结的非 EDS+QD 模块：
- 逐文件 diff 摘要：
- Protocol commit：
- Code/config/checkpoint fingerprint：
- Protocol-lock 时 Git dirty-state：

#### E. 执行协议

- Split/tasks/seeds：
- Exact command：
- 环境 fingerprint：
- GPU index/UUID 与 admission snapshots：
- Expected evaluations/model/reward/VLM calls：
- Started / ended / wall time：

#### F. 结果

| Task / seed | Control outcome | Candidate outcome | Mechanism metric | Safety | Calls | Validity |
| --- | --- | --- | --- | --- | --- | --- |

- Promotion vector：
- 迭代后 best success / target gap：
- 实际新增、保留与丢失 tasks：
- Raw artifact 路径与 SHA-256：
- Failure taxonomy / exception：
- Retry/recovery provenance：
- 本轮与累计 episode/GPU-hour budget：

#### G. 分析与决策

- 观察到的事实：
- 本轮是否缩小 `>=5/10` target gap：
- 对机制假设的支持/否证：
- 替代解释与限制：
- 决策：`KEEP | REVERT | DEEPEN | BROADEN_WITHIN_EDS_QD | PIVOT_WITHIN_EDS_QD | CONCLUDE`
- Reverted commit 与保留 evidence（若适用）：
- Result commit：
- 下一步及理由：

#### H. Outer-loop reflection（触发时填写）

- 自上次 reflection 的全部 positive/negative/invalid 结果：
- 全工作区历史证据新增发现：
- 当前 EDS+QD 机制理解：
- 方向选择及 scope 合规性：
- Findings/state/report 更新：

### `run_002_partition_diagnostic` — Causal envelope 分区反事实

#### A. 身份与状态

- 日期与 UTC 时间：`2026-08-10T15:43:49Z`。
- Inner/outer loop：outer-loop 001 pivot 后的 inner-loop QD-0。
- 状态：`PROTOCOL_LOCKED`；尚未实现或执行。
- 标签：`CONFIRMATORY`。
- 假设 ID：H1。
- Scope level：`QD-0`。
- 迭代前 best success / target gap：历史 EDS-QD `2/10`；gap 3。
- 本轮预计翻转的失败 task：本轮 0 episode；若全部 offline gate 支持，未来唯一 QD-1 候选必须保留 5/8 并恢复 3 或 9，才直接缩小 gap。

#### B. 历史证据与问题来源

| 绝对路径 | Commit / SHA-256 | 原始数值或失败模式 | 证据等级 | 对本轮设计的影响 |
| --- | --- | --- | --- | --- |
| owned `run_000_baseline_replay/analysis.json` | `6ad13083…963` | 27 files / 4,705 QD chunks；raw overflow P95 0.875；coverage median 1.0 | confirmatory replay | 冻结 raw JSONL 输入与 H1 failure boundary |
| `core/qd_ed.py` | blob `a9138b1f…bd13` | initial bounds 后永久 clamp；capacity-one reward elite | source evidence | 单点修改仅针对 bounds/partition 与 rebin |
| original EDS-QD report | `cbaa9df2…16c` | control `{3,8,9}`；best QD `{5,8}` | audited task outcome | task strata 与未来 retain/recover 目标 |
| frozen design H1 | commit `1aee7648…981` | overflow P95 `<=0.25`、resolution `>=20%`、spread/mode guard | frozen protocol | 阈值不得由结果反向修改 |

- 已检索 catalog/query：27-file manifest、original/budget profile metadata、`shadow_qd_candidate_stream`、bounds、per-iteration archive/overflow/reward/fingerprint fields，以及 current archive update/tie-break source。
- 相冲突证据：expand20 与其他 bounds OFAT 均未 adoption；所以本轮不再试 expand scalar。Stored stream 不能重建 partition 改变后的 offspring，只能回答是否值得一次在线因果检验。
- 为什么没有重复已知失败：唯一规则是无标量超参的 causal envelope + archive rebin；grid、descriptor、reward、allocation 与 compute 均不 sweep。

#### C. 锁定假设与判据

- 机制陈述：initial-only bounds 使 later descriptors 在 edge cells 内发生几何 aliasing；当前 batch 可见后单调扩展 envelope 并重分箱 incumbents，应降低 within-cell endpoint SSE，而不牺牲 mode count、endpoint spread 或全局 reward best。
- 可证伪预测：unrepresented overflow P95 `<=0.25`；chunk/profile median resolution improvement `>=20%`；task 3/5/8/9 至少两个同方向；mode/spread median ratio各 `>=0.90`；global best 100% preserved。
- Primary metric：paired `within_cell_endpoint_sse` 的 `1 - candidate/baseline`。
- Support / reject：全部 validity + 6 项 H1 gates 见 per-run protocol；任一有效 gate fail 即本 cycle PARK H1，不试邻近 partition。
- Safety/compute guardrails：0 episode/GPU/model/reward/VLM/environment call；同一 stored candidates；4x4、capacity one、16 slots、baseline evaluation budget不变。
- 替代解释：几何 resolution 改善可能不对应 manipulation stage progress；因 parent cells 改变，真正 offspring stream 只能由随后 QD-1 Dev-A 验证。

#### D. EDS+QD change map

| EDS+QD 步骤 | Frozen / Changed | 修改内容 | 文件/符号 | 归因理由 |
| --- | --- | --- | --- | --- |
| EDS initial proposal | Frozen | stored initial batch；initial insertion不变 | JSONL stream iter -1 | 隔离 partition |
| EDS rollout/mutation/budget | Frozen | stored offspring；无再生成 | JSONL stream iter >=0 | 0-call paired replay |
| QD descriptor/partition | Counterfactual | fixed initial vs `causal_envelope_v1` | protocol 后 analyzer | H1 核心 |
| QD archive/replacement | Counterfactual | bounds 扩展时 deterministic incumbent rebin | protocol 后 analyzer | 维持 cell semantic consistency |
| QD parent/allocation | Frozen | 不从 stored stream 推断新 offspring | — | 防止无效因果外推 |
| QD quality/elitism | Frozen | reward 再 fingerprint tie-break | source parity | 保持 quality 不变 |
| QD final selection | Frozen | global reward best | replay | 检验 best preservation |
| QD cross-chunk state | Frozen | fresh local archive | — | 不发散到 H3 |
| EDS+QD instrumentation | Planned | deterministic JSONL analyzer | `src/analyze_qd_partition_counterfactual.py` | QD-1 go/no-go |

- 明确冻结的非 EDS+QD 模块：checkpoint、perception/grounding、prompt、Stage、environment/reset、executor、evaluator。
- 逐文件 diff 摘要：protocol commit 只增加 protocol，并更新 state/log/ledger；没有 analyzer 或算法实现。
- Protocol commit：pending this commit。
- Code/config fingerprint：QD blobs `a9138b1f…bd13` / `1354e26c…dd95`；source manifest `6ad13083…963`。
- Protocol-lock dirty-state：仅用户受保护的 untracked stage-guidance design；不会 stage/modify。

#### E. 执行协议

- Split/tasks/seeds：27 immutable historical metrics files；仅 4x4 records 进入 paired estimand；task 3/5/8/9 作预注册 strata。
- Exact command：见 `experiments/run_002_partition_diagnostic/protocol.md`。
- 环境 fingerprint：CPU-only standard Python JSON analyzer；local permutation seed 1702。
- GPU index/UUID：不适用。
- Expected evaluations/model/reward/VLM calls：全部 0。
- Started / ended / wall time：尚未开始。

#### F. 结果

- 状态：尚未执行；无可用 result、task outcome 或 mechanism statistic。
- Promotion vector：未评估。
- 迭代后 best success / target gap：仍为历史 `2/10` / 3。
- 本轮与累计 episode/GPU-hour budget：`0/0`；累计 attempt `0/143`、GPU-hours `0/48`。

#### G. 分析与决策

- 当前决策：只锁定 protocol，不提前声称 H1 support。
- 结果决策树：全部 gate pass → 仅授权一个 QD-1 protocol；valid gate fail → reject/park H1；首次 schema failure → 最多一次 protocol-first repair；第二次 → invalid + outer-loop。
- 下一步：在本 protocol commit 后实现 analyzer，先做 baseline exactness，再执行三次 deterministic replay；任何算法实现仍未授权。
