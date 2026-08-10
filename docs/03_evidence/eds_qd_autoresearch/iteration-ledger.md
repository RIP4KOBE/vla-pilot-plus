# EDS+QD Autoresearch 统一迭代总账

状态：`EXECUTING — run_000_baseline_replay / PROTOCOL_LOCKED — 0 algorithm iterations`

本文件是 EDS+QD autoresearch 所有 inner-loop 与 outer-loop 过程的单一人工审查入口。所有条目按 iteration ID append-only；不能删除、覆盖或为改善叙事而重写负结果、invalid attempt、infrastructure failure 或 revert 记录。大型 raw artifacts 不嵌入 Git，但必须以稳定路径和 SHA-256 引用。

## 总索引

| Iteration | 日期 | Scope level | 假设 | 修改摘要 | Split / tasks | 结果 | 决策 | Protocol commit | Result commit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `run_000_baseline_replay` | 2026-08-10 | `QD-0` | H1–H5 | 只读回放旧 QD 与预算 sweep，验证 target-linked failure boundary | historical only | pending | `PROTOCOL_LOCKED` | pending (this commit) | — |
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
- 当前结论：冻结方案已获正式执行授权；formal evaluation 仍须通过 promotion gates。

### `run_000_baseline_replay` — 历史基线与预算扩展回放

#### A. 身份与状态

- 日期与 UTC 时间：`2026-08-10T15:05:31Z`。
- Inner/outer loop：inner loop 0，bootstrap diagnostic。
- 状态：`PROTOCOL_LOCKED`。
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
- 逐文件 diff 摘要：本 protocol commit 仅新增 catalog/protocol 并更新 ledger/state/log/status；没有算法或 replay 实现。
- Protocol commit：pending (this commit；提交后回填 hash 只能在 result 记录，不改写 protocol)。
- Code/config/checkpoint fingerprint：`core/qd_ed.py` Git blob `a9138b1f…bd13`；`core/rdt_policy_steer.py` Git blob `1354e26c…dd95`；checkpoint 不加载。
- Protocol-lock 时 Git dirty-state：仅用户保留且禁止修改的 untracked `docs/01_specs/2026-08-10-eds-qd-stage-guidance-transition-design.md`；无算法 diff。

#### E. 执行协议

- Split/tasks/seeds：historical immutable records only。
- Exact command：见 per-run protocol；输出只写 owned artifact root。
- 环境 fingerprint：CPU/offline parser；Git HEAD before protocol `d35170073c8ef12d035f854446c439dcfeec1efe`。
- GPU index/UUID 与 admission snapshots：不适用。
- Expected evaluations/model/reward/VLM calls：全部 0。
- Started / ended / wall time：尚未开始。

#### F. 结果

Pending。Protocol lock 后才允许实现、运行与追加结果。

#### G. 分析与决策

- 预提交决策：support gates 全过则 `KEEP` 诊断证据，排除 compute scaling，并按 protocol 的确定性顺序只选一个下一 `QD-0`；否则 `INVALID` 并仅修复 provenance/parser。

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
