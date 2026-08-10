# EDS+QD Autoresearch 统一迭代总账

状态：`EXECUTING — bootstrap_historical_replay — 0 algorithm iterations`

本文件是 EDS+QD autoresearch 所有 inner-loop 与 outer-loop 过程的单一人工审查入口。所有条目按 iteration ID append-only；不能删除、覆盖或为改善叙事而重写负结果、invalid attempt、infrastructure failure 或 revert 记录。大型 raw artifacts 不嵌入 Git，但必须以稳定路径和 SHA-256 引用。

## 总索引

| Iteration | 日期 | Scope level | 假设 | 修改摘要 | Split / tasks | 结果 | 决策 | Protocol commit | Result commit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
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
