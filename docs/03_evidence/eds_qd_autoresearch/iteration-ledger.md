# EDS+QD Autoresearch 统一迭代总账

状态：`EXECUTING — run_010 final exact-cell recovery ready — 1 algorithm iteration`

本文件是 EDS+QD autoresearch 所有 inner-loop 与 outer-loop 过程的单一人工审查入口。所有条目按 iteration ID append-only；不能删除、覆盖或为改善叙事而重写负结果、invalid attempt、infrastructure failure 或 revert 记录。大型 raw artifacts 不嵌入 Git，但必须以稳定路径和 SHA-256 引用。

## 总索引

| Iteration | 日期 | Scope level | 假设 | 修改摘要 | Split / tasks | 结果 | 决策 | Protocol commit | Result commit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `run_010_causal_envelope_candidate` | 2026-08-10 | `QD-1` | H1 | sparse QD + causal bounds expansion/archive rebin；其余冻结 | offline PASS；两次 preflight dispatch 均在 episode 前 infra abort | `FINAL_EXACT_CELL_RECOVERY_READY`；0 task outcome | exact gitlink verified；final recovery pending | v1 `1017bf0…`; v2 `8fd3aea…`; v3 `b344dc8…`; v4 `8016905…` | `d6af68b…` blocker result |
| `run_002_partition_diagnostic` | 2026-08-10 | `QD-0` | H1 | fixed-initial vs 单一 `causal_envelope_v1` 4x4 partition replay | 27 frozen files；4,567 eligible chunks；task strata 3/5/8/9 | 10/10 gates PASS；resolution +30.1%；global best 100% | `KEEP_DIAGNOSTIC_EVIDENCE_AND_AUTHORIZE_ONE_QD1_PROTOCOL` | `862f7cc4f00d92a97f6a0103e760f3b6180a437f` | `29fcdb7940e35ce12d1d96e2651b7d813406052d` |
| `run_001_allocation_ecology_diagnostic` | 2026-08-10 | `QD-0` | H4 | saved-trace parent-quality inheritance 与 saturated slot audit | 540 traces / 9,000 stages；task strata 0–9 | 2 attempts `INVALID`；无可采纳 H4 outcome | `INVALID_CONCLUDE_AND_TRIGGER_OUTER_LOOP` | v1 `dcf234b…`; v2 `91ddd34…`; v3 `f6d7bc9…`; v4 `3d320f6…` | `cdd150b2c332e907c05cda90c7c09fd1f1799570` |
| `run_000_baseline_replay` | 2026-08-10 | `QD-0` | H1–H5 | 只读回放旧 QD 与预算 sweep，验证 target-linked failure boundary | historical only | 6/6 gates PASS；4,705 QD chunks；budget max 1/10 | `KEEP_DIAGNOSTIC_EVIDENCE` | `5255e924ee925487406e35a27548d9db4e988642` | `e0b252c983a3b62858c8fa676e7b32618660b364` |
| — | 2026-08-10 | — | — | 执行授权；尚未开始算法迭代 | — | — | `APPROVED_EXECUTING` | — | — |

## 累计状态

- 当前 best formal candidate：无。
- 当前 best formal success：未运行。
- 历史 best EDS-QD success：`2/10`。
- 当前 target gap：`5 - 2 = 3` tasks。
- 新在线 episodes：0。
- GPU jobs：3 个 v3 worker 均在 episode 前 import failure；当前 owned jobs 0。
- Formal evaluations：0。
- 累计 GPU-hours：`0.023594 / 48`（IDs 7–12 三个 worker 的 pre-episode import failure device-wall sum）。
- Attempt budget：IDs 1–12 均已 append-only 标为 pre-episode aborted；active/dispatched 0。实际 initialized episode attempts `0 / 143`；same-cell recovery slots 已用 6/15，v4 最终 recovery 将再用 6 slots。
- 已结束新实验：3 个 `QD-0`（2 complete，1 invalid）；QD-1 算法迭代 1 正在执行。
- 当前结论：`run_010` Stage-A PASS；replacement credential health PASS，但 v3 recovery 暴露当前 worktree 的 pinned RDT gitlink 未初始化。0 task outcome，best/gap 不变。v4 只允许初始化 exact gitlink并做最后一次 six-cell recovery；Dev-A 仍要求 candidate success `>= control + 1` 且零 control-success loss。相邻 partition、Dev-B、validation、formal 均未授权。

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
- 状态：`COMPLETE`。
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
| EDS+QD instrumentation | Changed | deterministic JSONL analyzer | `src/analyze_qd_partition_counterfactual.py` | QD-1 go/no-go |

- 明确冻结的非 EDS+QD 模块：checkpoint、perception/grounding、prompt、Stage、environment/reset、executor、evaluator。
- 逐文件 diff 摘要：protocol commit 只增加 protocol，并更新 state/log/ledger；没有 analyzer 或算法实现。
- Protocol commit：`862f7cc4f00d92a97f6a0103e760f3b6180a437f`。
- Code/config fingerprint：QD blobs `a9138b1f…bd13` / `1354e26c…dd95`；source manifest `6ad13083…963`。
- Protocol-lock dirty-state：仅用户受保护的 untracked stage-guidance design；不会 stage/modify。

#### E. 执行协议

- Split/tasks/seeds：27 immutable historical metrics files；仅 4x4 records 进入 paired estimand；task 3/5/8/9 作预注册 strata。
- Exact command：见 `experiments/run_002_partition_diagnostic/protocol.md`。
- 环境 fingerprint：CPU-only standard Python JSON analyzer；local permutation seed 1702。
- GPU index/UUID：不适用。
- Expected evaluations/model/reward/VLM calls：全部 0。
- Started / ended / wall time：canonical completed at `2026-08-10T15:56:20Z`，wall `149.2 s`；two repeats concurrent wall `148.9 s`。首次同命令受外层 120 s shell timeout 中止，未写 artifact；随后相同 commit/input/threshold 完成。

#### F. 结果

- 状态：`COMPLETE`；validity 与 scientific gates 全 PASS。

| Stratum | Resolution improvement median | Support threshold | Result |
| --- | ---: | ---: | --- |
| task 3 | 0.273937 | 0.20 | PASS |
| task 5 | 0.318165 | 0.20 | PASS |
| task 8 | 0.326254 | 0.20 | PASS |
| task 9 | 0.308536 | 0.20 | PASS |

- 全局：27/27 hashes；4,705 records；4,567 eligible 4x4 exact replay；138 个 3x3 records 按 protocol 排除；0 malformed、baseline mismatch、permutation failure。
- Primary：equal-chunk resolution `+0.300775`；equal-profile `+0.309348`。
- Guardrails：candidate represented-overflow P95 `0.0`，同时 raw initial-bound overflow P95 如实保持 `0.875`；occupied-mode ratio median `0.9375`；archive-spread ratio median `2.008744`；global best preserve `1.0`。
- Promotion vector：只通过 offline QD-0 → one QD-1 protocol；无 environment success、task gain/loss 或 formal promotion。
- 迭代后 best success / target gap：仍为历史 `2/10` / 3。
- 实际新增、保留与丢失 tasks：无在线 episode，均为空。
- Raw artifact：owned `run_002_partition_diagnostic/analysis.json` SHA-256 `e21d2598981f8dbe538d35da77b33b31585a92b4e960c7056bef7d729e20d9a7`；manifest `d322720…abcd`；summary `7b638e0f…7450`。
- Determinism：canonical + two complete repeats 三个 analysis hashes 完全相同；repeat 临时目录验证后移入 trash，仅保留 canonical 11 MiB artifact。
- Failure/recovery：首次 120 s 外层 shell timeout 在 artifact write 前终止；相同 command/commit/input 重跑完成。它不属于 episode attempt、data validity failure 或 scientific threshold amendment。
- 本轮与累计 episode/GPU-hour budget：`0/0`；累计 attempt `0/143`、GPU-hours `0/48`。

#### G. 分析与决策

- 观察事实：causal envelope 在 common stream 上显著降低 within-cell XY distortion，同时保留近满 archive mode count、扩大 meter-scale endpoint spread，并从不丢失 global reward best。
- Target gap：未缩小；本轮没有 task execution，不能把 geometry 结果当 success。
- H1：获得 offline support，授权一次 QD-1 因果测试；不授权参数 sweep 或 formal。
- 替代解释：parent cell 改变会改变未来 offspring，stored stream 不能覆盖；endpoint resolution 不是 stage progress。
- 决策：`KEEP_DIAGNOSTIC_EVIDENCE_AND_AUTHORIZE_ONE_QD1_PROTOCOL`。
- Result commit：`29fcdb7940e35ce12d1d96e2651b7d813406052d`。
- 下一步：先锁定 `run_010_causal_envelope_candidate` protocol，再以 TDD 实现 QD bounds expansion/archive rebin；CPU offline preflight PASS 后才进入 frozen mechanism preflight 与 Dev-A。

### `run_010_causal_envelope_candidate` — Sparse QD causal envelope 因果候选

#### A. 身份与状态

- 日期与 UTC 时间：`2026-08-10T16:08:00Z`。
- Inner/outer loop：outer-loop 001 下的首个 QD-1。
- 状态：`PROTOCOL_LOCKED`；无算法 diff、测试结果或 online outcome。
- 标签：`CONFIRMATORY`。
- 假设 ID：H1。
- Scope level：`QD-1`。
- 迭代前 best success / target gap：历史 EDS-QD `2/10`；gap 3。
- 本轮预计翻转的失败 task：以新 seed paired control 为准，在 3/5/8/9 中至少新增 1 个 success 且不丢任何 control success；机制目标为历史 retain 5/8、recover 3/9。

#### B. 历史证据与问题来源

| 绝对路径 | Commit / SHA-256 | 原始数值或失败模式 | 证据等级 | 对本轮设计的影响 |
| --- | --- | --- | --- | --- |
| owned `run_002_partition_diagnostic/analysis.json` | `e21d2598…d9a7` | 4,567 exact replays；resolution +30.1%；mode 0.9375；spread 2.0087；best retain 1.0 | confirmatory offline | 只授权 causal envelope 一个 QD-1 |
| original EDS-QD report | `cbaa9df2…16c` | control `{3,8,9}`；sparse `{5,8}` | audited task outcome | sparse primary 为 base；retain/recover task map |
| run_000 analysis | `6ad13083…963` | overflow P95 0.875；compute sweep max 1/10 | confirmatory replay | 不加 compute、不试邻近 grid/bounds |
| `core/qd_ed.py` / `core/rdt_policy_steer.py` | blobs `a9138b1f…bd13` / `1354e26c…dd95` | fixed clamp、capacity-one、sparse visits、global reward best | source | 冻结除 partition/rebin 外语义 |

- 已检索 catalog/query：run_000/001/002、original/budget reports、shadow streams、archive/metrics/config validation、runner attempt/GPU/storage/credential paths、frozen Dev-A split。
- 相冲突证据：expand20 未 adoption；因此本轮不是 expand scalar。Offline common stream 不模拟新 parent 产生的 offspring；因此必须用 paired Dev-A success 决断。
- 为什么没有重复已知失败：新 field 是 `qd_bounds_update_policy` 单点差异；grid、descriptor、capacity、allocation rule、reward、selection、Stage、compute 全冻结。

#### C. 锁定假设与判据

- 机制陈述：causal envelope 与 coherent archive/visit rebin 会把 offline geometry resolution 转化为更有效的 sparse parent/offspring feedback，从而至少翻转一个 Dev-A task 且不丢 control success。
- 可证伪预测：offline/preflight 全硬门 PASS；Dev-A candidate `success >= control + 1`、control-success retention 100%、gain-loss `>=1`；online resolution 在至少 3/4 tasks `>=20%`。
- Primary metric：paired Dev-A success count 与 gained/retained/lost task matrix。
- Support gate：成功、retention、validity/safety、3/4 mechanism 与 compute gates 全 PASS。
- Refute/reject gate：success tie/下降、任何 control-success loss、safety/call failure、只有 proxy gain、或机制 collapse；均停止 H1 不试相邻参数。
- Safety/compute：14 unique cells；attempt cap 143；48 GPU-hours；176 eval/complete candidate chunk；动态 GPU admission。
- 替代解释：new seeds 的 control outcome 可与历史 task map 不同；Stage telemetry 不是 success 替代；rebin/visit remap 的 online feedback 只能由本轮验证。

#### D. EDS+QD change map

| EDS+QD 步骤 | Frozen / Changed | 修改内容 | 文件/符号 | 归因理由 |
| --- | --- | --- | --- | --- |
| EDS initial proposal | Frozen | none | — | 保持 initial archive |
| EDS rollout/mutation/budget | Frozen | 16×10，176 eval | — | compute matching |
| QD descriptor/partition | Changed | current-batch causal no-shrink envelope | planned core helper/policy branch | H1 |
| QD archive/replacement | Changed | incumbent rebin、collision elite、visit remap | planned `QDArchive` method | cell consistency |
| QD parent/allocation | Frozen | sparse-priority rule不变 | existing allocator | 单点归因 |
| QD quality/elitism | Frozen | reward/fingerprint | existing archive | 不混入 H2 |
| QD final selection | Frozen | global reward best | existing selection | 不混入 H2 |
| QD cross-chunk state | Frozen | fresh | existing | 不混入 H3 |
| EDS+QD instrumentation | Changed | bounds/rebin/raw-overflow/resolution + owned runner/audit | planned metrics/scripts/tests | attribution/validity |

- 明确冻结的非 EDS+QD 模块：checkpoint、perception、prompt、Stage recognizer/settings、environment/reset、executor、evaluator、post-processing。
- 逐文件 diff 摘要：protocol commit 只新增 protocol 与 state/log/ledger；算法、runner、tests 尚未修改。
- Protocol commit：pending this commit。
- Protocol parent：`29fcdb7940e35ce12d1d96e2651b7d813406052d`；QD blobs 如上。
- Dirty-state：仅用户保护的 untracked stage-guidance design；不会修改/stage。

#### E. 执行协议

- Offline：冻结九文件 pytest suite + dedicated runner tests + machine offline preflight。
- Mechanism preflight：profiles control/sparse/candidate × tasks 3/5，seeds 512905/150741，`max_chunks=2`，6 cells。
- Dev-A：control/candidate × tasks `[3,5,8,9]`，seeds `[512905,150741,463456,452903]`，8 full episodes。
- Exact commands：见 per-run protocol；未实现前不执行。
- GPU：0–7 动态两次+dispatch snapshot admission；当前无 selection/UUID。
- Expected online unique cells / attempt / upper GPU budget：14 / 14 baseline attempts / 48 GPU-hours global cap。
- Started / ended：尚未开始。

#### F. 结果

- 状态：尚未实现或执行；无 task outcome、GPU、attempt 或 algorithm iteration。
- 当前 best / gap：历史 `2/10` / 3，不变。
- 当前累计：attempt `0/143`；GPU-hours `0/48`；formal 0。

#### G. 分析与决策

- 当前只锁定 causal-envelope single candidate 与 success-first reject rule，不声称 online support。
- 下一步：protocol commit 后 TDD 最小实现，固定/causal 两条 config path 和 dedicated runner；先过完整 CPU/offline gate。只有 offline PASS 才能 freeze manifest 与 GPU preflight。

#### H. 实现与提交（追加记录）

- 时间：`2026-08-10T16:39:09Z`；状态从 `PROTOCOL_LOCKED` 推进到 `IMPLEMENTED_OFFLINE_VALIDATION_PENDING`。
- Protocol commit：`1017bf0212780b2e386764517661cf9970090f8d`，严格早于 implementation commit `930cdb5295b8f9b4ee099298764c3af3c078d6b7`。
- 算法 iteration：1。尚无 online task outcome，best 仍为历史 `2/10`、target gap 仍为 3；attempt `0/143`、GPU-hours `0/48`、formal 0。
- TDD 记录：bounds/archive tests 首先因缺少 `expand_bounds` import 红灯；实现后 core tests 22 passed。Dedicated runner tests 首先因 runner 文件不存在而 6 failed；实现后扩充到 8 passed。最终冻结九文件 suite 为 `781 passed in 71.32s`。
- QD partition：新增 `expand_bounds`，每个已评分 offspring batch 只扩不缩，非有限输入 fail closed，checksum 对 batch permutation 稳定。
- QD archive：新增 deterministic `rebin`；按 reward/fingerprint 解 collision，将旧 cell cumulative visits 映射并求和，强制总 visits 守恒，global reward-best 不因 rebin 丢失。
- QD loop：只有 `qd_bounds_update_policy=causal_envelope_v1` 启用 expand→incumbent rebin→child insert；`fixed_initial` 为默认并保持既有路径。Population/iterations/reward/parent rule/final selection 均未改变，完整 chunk 仍为 176 evaluations / 11 score calls。
- Telemetry：新增逐 iteration active bounds/checksum、expand、rebin collision/visit、raw initial-bound overflow、post-envelope overflow、fixed/active within-cell SSE 和 resolution improvement；final selection/accounting/fallback 字段继续保留。
- Runner/audit：冻结 6-cell mechanism preflight 与 8-cell Dev-A；无 Dev-B/validation/formal CLI。加入 143-attempt fail-closed ledger、隐式 retry 拒绝、50 GiB storage、pause、credential、artifact checksum、checkpoint/LIBERO input fingerprint、GPU-hour、task/safety/mechanism/latency gates。
- GPU 隔离：移除旧 profile 的物理 GPU 5 EGL pin，使 MuJoCo 跟随每个动态 admitted worker GPU；本 worktree `.libero_config` 仅重绑定到本 worktree 的同版 LIBERO-PRO 文件，未写其他 worktree。
- Source SHA-256：`configs/config.yaml b20791a2…daf8`；`core/qd_ed.py 1516bb75…70b9`；`core/rdt_policy_steer.py b8806d7a…1ff2`；`core/eds_eval_metrics.py d8fb4d04…3429`；runner `c1887cac…c0a`；runner tests `5ae0a254…45a3`。
- Dirty-state：implementation commit 后仅保留用户保护的 untracked `docs/01_specs/2026-08-10-eds-qd-stage-guidance-transition-design.md`；从未修改、stage 或 commit。
- 下一步：先提交本状态索引，再运行 immutable offline preflight。只有 machine PASS 才能 freeze run manifest 和进入 GPU admission；当前不授权任何 GPU dispatch。

#### I. Stage-A 首次失败与唯一 protocol-first repair

- 时间：`2026-08-10T16:42:10Z`；命令为冻结的 `storage-preflight` 后接 `offline-preflight`；wall `79.2 s`；online attempt/GPU/formal 均为 0。
- Immutable failed artifact：`run_010_causal_envelope_candidate/analysis/offline_preflight.json`，mode `0444`，SHA-256 `1654574975a02df00be5ac6c78b986b18baf1657bf997a808c1fcb5aa58f9a61`。
- 已通过：storage（约 212.5 GiB free）、781 tests、full checkpoint `b4e3631d…aaa1` / aggregate `a2026bcf…6c28`、LIBERO input aggregate `259c469e…38b8`、source/config fingerprints、176 evaluations、11 score calls、10/10 accounting、raw overflow disclosed、post-envelope overflow 0、10/10 visit conservation、10/10 rebin global-best preservation、RNG passive。
- 唯一失败：synthetic iteration 0 的 fixed SSE 为 0，因此 resolution 正确为 `null`；iterations 1–9 均为 `1.0`。Runner 误加了“每轮都必须 finite 且 >=20%”这一 parent protocol 未注册的 quantifier。
- 分类：offline audit fixture/schema defect，不是候选算法逻辑或 scientific refutation；没有 success/task/seed/GPU 结果被观察。
- 唯一修复：新建 `protocol-v2.md`，先提交后才允许 runner 改为 v2 immutable path，并以 finite values median `>=0.20` 处理 zero-denominator；其余 gate 全部冻结。无第二次 schema repair。

#### J. Stage-A v2 PASS

- Repair protocol / implementation commits：`8fd3aea0b1ec063aba63fa0bffcf3829f03c006c` / `9729ff24ad34dc02a495f8fb5c717974da6f1756`；protocol-first 顺序满足。
- 时间 / wall：`2026-08-10T16:45:47Z`；命令 wall `78.4 s`，其中冻结 regression `75.068 s`。
- Immutable PASS artifact：`run_010_causal_envelope_candidate/analysis/offline_preflight.v2.json`，mode `0444`，size 19,777 bytes，SHA-256 `3097afadbf2f3a5ab827a8242c2f4bd43ed20bec46d0ff76c62fef2d7b62f7a9`。v1 failure `16545749…9a61` 同时保留。
- Provenance：code commit `9729ff24…1756`；code-state `6250e7ca…d78`；active checkpoint aggregate `a2026bcf…6c28`，full weight `b4e3631d…aaa1`；LIBERO swap inputs aggregate `259c469e…38b8`。
- Tests：冻结九文件 suite `781 passed`；无 test failure。
- Mechanism/accounting：176 evaluations、11 score calls、10×16 offspring accounting、10×16 parent slots；raw overflow counts `[12,12,12,16,16,16,16,16,16,16]`，post-envelope counts 全 0；rebin visits 10/10 conserved；global-best fingerprints 10/10 unchanged；RNG unchanged。
- Partition：iteration 0 fixed SSE=0 → resolution `null`；其余 9 个 finite improvements 均 1.0，中位数 1.0，PASS frozen `>=0.20` gate；首次 rebin collision 7，其余 0，winner/visit invariants PASS。
- Target impact：仍无 task execution，不能宣称 success 改善。Best `2/10`、gap 3；attempt `0/143`、GPU-hours `0/48`、formal 0。
- 决策：`KEEP_STAGE_A_PASS_AND_FREEZE_ONLINE_MANIFEST`。下一步只允许从该 v2 hash 和当前 committed code 冻结 immutable manifest，再做六-cell mechanism preflight GPU admission。

#### K. Online manifest freeze

- 时间：`2026-08-10T16:47:24Z`；pre-dispatch pause/storage checks PASS；仍为 attempt 0、GPU-hours 0、formal 0。
- Immutable manifest：`run_010_causal_envelope_candidate/manifests/run_manifest.json`，mode `0444`，size 17,890 bytes，file SHA-256 `cb211e2ed3fe2cfa2512f0982153295c9f23fa9964e3f623d1ef3b1eef10ae34`，payload SHA-256 `20e7e17c70c4360df4d8534c4bc3ff0c204988bc4fd7acfa544ca4b7c8e9511e`。
- Manifest binding：code commit `0f418417…54d5` / code-state `1b4c1c51…62e7`；offline v2 `3097afad…f7a9`；failed v1 `16545749…9a61`；checkpoint `a2026bcf…6c28`；LIBERO input `259c469e…38b8`；GPU reference `d49ea817…fff1`。
- Matrix：mechanism preflight 6 unique cells（control/sparse/candidate × tasks 3/5）；Dev-A 8 unique cells（control/candidate × tasks 3/5/8/9）；attempt cap 143、GPU-hour cap 48、formal authorized false。
- Runtime cache：6 files，provenance SHA-256 `4434ca3bafefdb8f0cdf747e6a4a60d73965033cb125bcd51be48ed14bdced7b`；全部位于 owned run root。
- 下一步：动态检查 GPU 0–7 两次快照和 dispatch snapshot；只在无外部 compute、utilization <=5%、VRAM headroom 合格时发出 frozen 6-cell mechanism preflight。

#### L. Mechanism preflight 首派发：episode 前 API 中止与恢复 protocol

- 时间：首派发从 `2026-08-10T16:48:32Z` 左右开始，GPU admission / reservation 于 `16:49:04Z` 完成；命令 wall `39.2 s`，随后 base runner 报 `Poe Gemini health check failed`。
- Exact command：`python scripts/eds_qd_autoresearch_runner.py run-mechanism-preflight --gpus auto --timeout-seconds 28800`。
- Pause/storage/credential-presence：PASS；credential 值未打印或持久化。
- GPU evidence：两次 admission snapshot 相隔 30 s，只有 GPU 7 合格；其 index/UUID 为 `7 / GPU-48473162-9548-1a19-04aa-ea86c5349187`，两次与 immediate dispatch snapshot 均无 compute process、utilization 0%、free VRAM 142,960 MiB。GPU 0–6 因外部 compute 和/或 utilization 被排除，没有抢占或干扰。
- GPU artifact：owned `run_010_causal_envelope_candidate/manifests/gpu_eds_qd_autoresearch_mechanism_preflight_1786380544.json`，SHA-256 `53db933fe0c2394643b36d2d76c39f8ec49558cc62e976e8e8cffa472c5ce579`。
- Attempt evidence：append-only ledger 在 incident protocol lock 前 SHA-256 `4e255f9380feb5a7c395002c8693ee0be813d2033426e23a343e02cdbc3f30ce`；IDs 1–6 对应 control/sparse/candidate × task 3/5，并有一次 phase dispatch。
- Pre-episode 证明：owned run root 中没有 online output directory、`run_manifest.csv`、phase status CSV、runner log、failure JSON 或 episode metrics；唯一新增文件是 GPU admission 与 attempt ledger。失败发生在 `base.run_level` 的启动 health check，尚未初始化 worker/episode。
- 分类：`INFRASTRUCTURE_FAILURE / API_TRANSIENT / DISPATCH_ABORTED_PRE_EPISODE`。它不是 task failure、policy timeout 或 mechanism gate outcome；task-level success 增减与失败原因均为 `N/A / 0 observed tasks`。
- Target impact：best 仍为历史 `2/10`，gap 3；本事件未缩小 gap，也没有产生反向调参信息。算法 iteration、profiles、tasks/seeds、promotion thresholds 与 formal authorization均不变。
- Protocol-first recovery：新增 `experiments/run_010_causal_envelope_candidate/protocol-v3.md`。它只授权一次 exact-cell recovery：先为 IDs 1–6 追加 pre-episode abort event；再在 API health PASS 后，以 frozen scientific revision `d018f8ac…991` / code-state `3626b52b…9839c` 创建 IDs 7–12，分别带 `recovery_of_attempt_id=1..6`；重新动态 admission；不修改 source 或 immutable manifest。
- Budget accounting：实际 initialized episode attempts 仍 `0/143`，GPU-hours 仍 0；6 个中止 reservation 永久保留，恢复最多占用 6/15 个 infrastructure slots。若恢复前 health 仍失败，则不产生新 reservation；若第二次仍在 worker 前失败，v3 要求中止并停止，不授权第三次派发。
- 决策：`RECOVER_EXACT_CELLS_ONCE`。下一步仅执行 v3 事务恢复；mechanism PASS 前不启动 Dev-A。
- Protocol commit：`b344dc850e8d63b2a78438d64d152693e8f7789f`，严格先于 abort event、恢复健康检查与诊断 artifact。
- Abort ledger：event 2 将 IDs 1–6 标为 `dispatch_aborted_pre_episode`；写入 event 2 时错误填写了正确前缀 `b344dc8` 但错误的完整 commit 后缀，event 3 以 append-only `provenance_correction` 给出正确完整 SHA；没有重写任一旧行。修正后 ledger SHA-256 `de67193d8a72c1f96ef1e0ca087cbaa7d6b14135ba390ad9abb1e8b350467fba`。
- v3 恢复前检查：临时切到 frozen scientific revision `d018f8ac…991` 后，pause/storage/manifest/ledger/cache/credential-presence 与零 online artifact assertions 均 PASS；随后 Poe health check 再次失败，wrapper 在 GPU admission 和 replacement reservation 之前退出，target branch 已恢复。
- 诊断：credential 存在且不是 dummy；`api.poe.com` DNS 解析 PASS（2 addresses），HTTPS endpoint 可达；authenticated `gemini-2.5-flash` 请求返回 HTTP 401、code `invalid_api_key`、type `authentication_error`。没有记录 credential 值、响应文本或 header。
- Immutable diagnostic：owned `run_010_causal_envelope_candidate/analysis/api_health_diagnostic_20260810T1659Z.json`，mode `0444`，size 907 bytes，SHA-256 `70afb86006c6c01517201b43562ea3c36e8d24680d8f1eec2f9ab2e219bcf227`。
- 恢复结果：未创建 IDs 7–12，未重新做 GPU admission，未启动 worker/episode，未生成 task outcome；initialized episode attempts `0/143`、GPU-hours 0、formal 0。v3 的一次 exact-cell dispatch authorization 尚未消耗。
- Failure reason / next-step basis：这是外部运行时 credential invalidity，不是可由 EDS+QD 修改解决的失败，也没有提供算法优化信号。继续 algorithm exploration 不会直接缩小 gap，违反 success-first 原则；故状态转为 `PAUSED_INVALID_RUNTIME_CREDENTIAL`，直到执行环境配置有效 `OPENAI_API_KEY` 后从 v3 pre-reservation health check 恢复。
- Infrastructure result commit：`d6af68b5cf21634c88c1ee07efa3a2aa43bd4160`。

#### M. 运行时凭据恢复与 v3 resume

- 时间：`2026-08-11T00:07:53Z`；用户提供 replacement Poe runtime credential 并明确要求继续任务。
- 状态转换：`PAUSED_INVALID_RUNTIME_CREDENTIAL → RECOVERY_HEALTHCHECK_PENDING`；本转换先于任何新 API health check、GPU admission 或 attempt reservation。
- Secret handling：只允许作为当前 recovery process 的临时环境变量；不回显、不写 artifact/worktree、不进入 worker command/Hydra、manifest、attempt ledger、research docs 或 Git。总账不记录 credential 值或可逆 fingerprint。
- Resume invariants：branch 为 `exp/eds-qd-autoresearch-libero-swap-ood`；protected untracked design 未修改；pause sentinel absent；无 owned process；IDs 1–6 仍为 pre-episode aborted；active/dispatched attempts 0；recovery dispatch remaining 1；manifest/source/config/checkpoint/task/seed bindings不变。
- 下一步：提交本状态转换；临时切换 frozen scientific revision `d018f8ac…991`，先做 Poe health check。只有 PASS 才允许 fresh GPU admission 与 IDs 7–12 exact-cell recovery。

#### N. v3 recovery outcome 与 exact-gitlink v4 protocol

- 时间：credential health PASS 后，GPU admission artifact 创建于 `2026-08-11T00:09:32.658562Z`；attempts 7–12 于 `00:09:34Z` reserve/dispatch；三个 jobs 于 `00:09:40Z` 启动、`00:10:08Z` 结束。
- Credential：pre-reservation Poe health PASS；credential 值从未写入 artifact、worker command、Hydra、manifest、ledger、docs 或 Git。owned root exact-secret scan 0 matches。
- GPU admission：fresh snapshots 选择 GPU 0/1/2，UUID 分别 `GPU-4c78c923-a68a-8e06-e07b-11bdd642118e`、`GPU-053aaa97-5574-46a0-cb86-83d0518d8877`、`GPU-a5d6a5f8-b6df-7f3a-c3dc-19734c41ec0e`；两次 snapshots 与 immediate dispatch 均 util 0%、无 compute process、free 143,157 MiB。artifact SHA-256 `70a087481b05263b0946fe0d0de95b58ac2906e56fab119b8a2e4a4f6abb9ed4`。
- Attempt ledger：IDs 7–12 exact match IDs 1–6 的 phase/profile/task/seed/config/code-state，带 `recovery_of_attempt_id=1..6`；dispatch 后 ledger SHA-256 `3702dbc95318685d2e52fcf55e64debe282f7d7f8c589c68a628ae65cacefd3d`。
- 三个一致 failure boundary：Hydra started；LIBERO adapter built frozen task 3/5 envs；checkpoint path resolved；随后 `ModuleNotFoundError: scripts.maniskill_model` / `ImportError: Ensure third_party/rdt is initialized`。模型未构造，episode/reset/action/task observation 未开始。
- Task-level outcome：control/sparse/candidate 全部 `0 observed episodes`；success gain/retention/loss、failure taxonomy 与 mechanism metrics 均 N/A。不得把 missing results/videos/metrics 的 wrapper summary当 policy failure。
- Artifact evidence：phase CSV SHA `d5f2c5e7…c05c`；control/sparse/candidate output-tree hashes `ad1c60f9…a953` / `bb55001d…096a` / `e99a1a40…1132`；runner-log hashes `dc00a9b7…406` / `f8a4a2c3…e83c` / `c6134848…33e`。全部保留，未 overwrite/delete。
- Budget：worker walls `28.287/28.478/28.174 s`，device sum `84.939 s = 0.023594 GPU-hours`；initialized episode attempts 0，formal 0；six recovery slots consumed。
- Root cause：parent tree pins `third_party/rdt` gitlink `b896f4dcac8ed1c3fae4a056200db267607f131f`；当前 worktree submodule status 为 leading `-` / empty directory。只读 baseline worktree已在相同 gitlink初始化且 clean。故为 worktree bootstrap omission，不是算法/source version差异。
- Protocol-first decision：新增 `protocol-v4.md`，只允许 current worktree 初始化 exact gitlink、clean import probe、unchanged code-state验证、归档旧 artifacts、为 IDs 7–12 追加 pre-episode abort，再进行唯一 final IDs 13–18 recovery。v4 后不再授权完整 six-cell retry。
- Target impact：仍为历史 best `2/10` / gap 3；本结果没有算法优化信号，不能反向调参。
- Protocol v4 commit：`80169057ef170dbe702c5cd25c6f4ac03b14381e`，严格早于 abort/archive/submodule initialization/import probe。
- Attempt closure：ledger event 5 将 IDs 7–12 标为 `pre_episode_import_infrastructure`；IDs 1–12 全部 aborted，active/dispatched 0；ledger SHA-256 `5e8a913694ea4826a1f1ffa95f9a7fbbb60b304cd5fc0e15c13ee97b82cd2138`。
- Preservation：三 output trees、三 runner logs 与 phase CSV 已移动到 owned `stale/pre_episode_import_failure_20260811T001519Z/`；无 delete/overwrite。Immutable archive manifest mode 0444，SHA-256 `4b981ad1a36725aab2c4ea055f5c4f639025b9da3c13ef4b2e5849d3d13d6929`，payload `67e645ca…c8a`，credential pattern matches 0。
- Exact repair：仅在当前 worktree 执行 `git submodule update --init --checkout third_party/rdt`；实际 HEAD `b896f4dcac8ed1c3fae4a056200db267607f131f`，submodule clean，parent 无 tracked diff；其他 worktree/submodule未写。
- Pre-reservation verification：在 frozen revision `d018f8ac…991` 复算 code-state仍为 `3626b52b…9839c`；`vla-pilot` 成功 import `scripts.maniskill_model.create_model` 与 `models.rdt_runner.RDTRunner`；immutable manifest 与 ledger invariants PASS。
- 状态：`FINAL_EXACT_CELL_RECOVERY_READY`。下一步 health/storage/admission 再验后才可创建 IDs 13–18；这是 v4 授权的最后完整 six-cell retry。

#### O. v4 final recovery 结果与 mechanism audit v5 repair protocol

- 时间：final admission artifact 创建于 `2026-08-11T00:19:54Z`；完整 runner wall `489.7 s`。服务 health、storage、pause、manifest、runtime cache、frozen revision/code-state 与 exact RDT gitlink checks 均 PASS。
- GPU admission：fresh two-snapshot + immediate dispatch 选择 GPU 0/1/2；artifact SHA-256 `209553223e711b95763dba3942d79e97debb1f072dd7f90b3e0a65bbfb559914`。未抢占或干扰外部进程。
- Attempts：IDs 13–18 是 IDs 7–12 的 exact-cell recovery，覆盖 control/sparse/candidate × task 3/5；attempt ledger SHA-256 `5f4971382bc97f25c103a4a904a761cb45fa872412b0c4caa1377d6c4561065c`。IDs 1–12 继续作为 pre-episode abort append-only 保留；v4 不再剩余 full-matrix retry。
- Task-level outcome：control `0/2`、sparse `0/2`、candidate `0/2`；六个 task cells 均为 `timeout without completion`。这是冻结的 `max_chunks=2` mechanism plumbing probe，不是 Dev-A 或 formal 成功率判据；不得用这六个 outcome 调参。
- Failure analysis：所有 profile 均未在两个 chunks 内完成 task 3/5；无 qpos/execution、nonfinite、action-mask、fallback、drop/collision/wrong-object plumbing failure。短 horizon 只能证明机制运行路径，不提供可靠的阶段因果诊断。
- Mechanism：candidate raw initial-bound overflow P95 `0.9375`、post-envelope overflow P95 `0`；candidate/sparse selection latency P95 `2.65048/2.73929 s`，ratio `0.96758`；candidate 41 条 metrics 的 bounds/rebin/visit/global-best/accounting telemetry 均存在并通过单项检查。
- Compute：final profile walls `382.305/260.393/443.906 s`，合计 `0.301834 GPU-hours`；加 v3 pre-episode import failure 共 `0.325428 GPU-hours`。Projected frozen matrix `0.70428 GPU-hours`，远低于 48 cap。
- Credential handling：owned worktree/artifact exact-secret scan 0；未记录 credential 值或可逆 fingerprint。
- 首次 audit（INVALID）：`analysis/mechanism_preflight_audit.json`，size 287,125，SHA-256 `d42dee30fad4c9d1ef6e8ffa02b73cb78830e736d7ea7c5e7877be8a9be4d6c7`。操作员误在文档 HEAD `eb9dd733…735` 而非 frozen scientific revision `d018f8ac…991` 运行，导致三个 expected config fingerprints 与冻结 job manifests 不同；其宽泛 `sk-` substring detector 又将 runtime-cache 普通标题 `Task-Specific` 误判为 credential。该 audit 不得用于 candidate 结论。
- 只读 root-cause verification：在 `d018f8ac…991` 重建 jobs 后，control/sparse/candidate fingerprints 精确为 `7dd8ca75…ed2` / `d083b1b7…9f2` / `296f14ae…f83`，三者 `_p2_job_validity` 均 PASS；严格 standalone token/API assignment/Bearer detector 扫描 192 个文本 artifacts 为 0 matches。
- Protocol-first repair：新增 `protocol-v5.md`；只授权一次 no-episode/no-GPU v2 audit，使用 frozen revision、原科学 gates 和严格 credential predicate，写新 immutable `mechanism_preflight_audit.v2.json` 并保留 v1。无第三次 audit repair。
- Target impact：best 仍为历史 `2/10`、gap 3；formal 0。只有 v2 aggregate PASS 才允许执行已冻结 Dev-A；当前不授权 Dev-B/validation/formal。

#### P. Mechanism audit v2 PASS

- Protocol-first：audit repair protocol commit `adfadeaf3efcf2dfad257edfb3a452fd3028ac9b` 先于 v2 artifact；未修改 scientific runner、算法、config、manifest、task/seed/checkpoint 或阈值。
- Invocation：在 detached frozen revision `d018f8ac…991` 验证 code-state `3626b52b…9839c`、exact RDT gitlink、manifest `cb211e2e…ae34`、attempt ledger `5f497138…065c` 与 clean tracked state 后执行；无 API、GPU、episode、attempt 或 formal 消耗。
- Immutable v2：`analysis/mechanism_preflight_audit.v2.json`，mode 0444，size 287,404 bytes，SHA-256 `c7e93f9255aee10f71e2519fa9e539cd537ca4ed89c905cebe334db5c68508ab`。v1 invalid artifact `d42dee30…d6c7` 同样 mode 0444、永久保留。
- Validity：control/sparse/candidate `3/3` jobs valid；三个 config fingerprints 与 job manifests 精确匹配；hard failures `0`。
- Mechanism/safety/accounting：candidate bounds/rebin/visits/global-best PASS；raw/post overflow P95 `0.9375/0`；latency ratio `0.9675801291 <= 1.25`；qpos/execution、nonfinite、action-mask、fallback 与 disallowed safety failures 全 0。
- Attempts/budget：frozen phase actual cells 6、global effective dispatched 6、global reservations 18，attempt audit PASS；final run `0.301834 GPU-hours`，projected total `0.70428 GPU-hours <=48`。累计含 pre-episode import incident 为 `0.325428 GPU-hours`。
- Credential：strict v2 在 run root 对 standalone long `sk-` token、API-key assignment、Authorization Bearer 和 present environment-secret equality 均 0 matches；credential audit PASS。用户 credential 从未持久化。
- Task analysis：三 profile 在短 horizon 均 `0/2`，success gain/retention/loss 为 0/0/0；共同 failure `timeout without completion`，无可归因的 candidate safety/plumbing regression。该结果只满足 Stage-B 机制门，不缩小 target gap。
- 决策：`KEEP_MECHANISM_PREFLIGHT_PASS_AND_RUN_FROZEN_DEV_A`。历史 best `2/10`、gap 3、formal 0；下一步只允许 parent protocol 已冻结的 control/candidate × tasks `[3,5,8,9]` full episodes。Dev-A target tie 或失败必须立即 revert causal-envelope，不能以 proxy 继续。

#### Q. Dev-A execution/audit binding protocol

- 状态：`DEV_A_PROTOCOL_LOCKED_READY`；protocol v6 在任何 Dev-A reservation/dispatch/result 前写入并提交。
- Matrix 不变：control/candidate × tasks `[3,5,8,9]` × seeds `[512905,150741,463456,452903]`，共 8 full episodes；两个 output roots 在 lock 时均不存在。
- Frozen bindings：scientific revision/code-state `d018f8ac…991` / `3626b52b…9839c`；control/candidate config fingerprints `298badf2…0e0` / `65502f2a…df0`。
- 已知 audit defect 前置关闭：execution 与 audit 都在 frozen revision；audit 复用 mechanism v2 已 PASS 的 strict credential predicate，不编辑 runtime cache，不改变任何科学 gate。
- Target rule：candidate 必须 `>= control +1`、保留全部 control-success tasks、gained-minus-lost `>=1`；tie/proxy-only 必须 reject/revert。Dev-B、validation、formal 仍未授权。

#### R. Dev-A pre-admission gate-path failure 与 v7 recovery

- 首次 invocation 在 `1.5 s` 内由 frozen runner 本地抛出 `mechanism preflight did not pass`；原因是 `run_phase` 固定读取保留的 invalid v1 audit path，未读取 v5 生成的 immutable PASS v2。
- Failure boundary：发生在 credential validation、API health、job build、GPU admission、attempt reservation、worker/episode 前。Attempt ledger 仍为 `5f497138…065c`；无 `dev_a__*` output 或 Dev-A GPU manifest；attempt/GPU/task/formal 增量全 0。
- 分类：`INFRASTRUCTURE_FAILURE / PRE_ADMISSION_GATE_PATH`，不是 policy、task 或 candidate failure，不可用于优化。
- Protocol-first：新增 v7，只允许一次 frozen process-local `MECHANISM_AUDIT_PATH → mechanism_preflight_audit.v2.json` 后调用 unchanged `run_phase`；v1/v2 均不覆盖，不改 source，不消费 same-cell recovery slot。
- Target impact：best `2/10`、gap 3 不变；v6 全部 matrix、audit 与 target gate 继续生效。

#### S. Dev-A execution 结果与 audit v8 repair protocol

- Execution：v7 process-local gate path 指向 immutable mechanism v2 后，health/admission PASS；GPU 0/1 执行 attempts 19–26，wrapper exit 0 / wall `909.1 s`。两个 job manifests 均 valid。
- Task matrix：control tasks 3/5/8/9 = fail/fail/fail/fail（`0/4`）；candidate = fail/fail/fail/success（`1/4`）。Gained `[9]`、retained `[]`、lost `[]`；target gate 的 `candidate >= control+1`、零丢失、gained-minus-lost `+1` 均满足。
- Failure analysis：两者 tasks 3/5/8 与 control task 9 均为 `timeout without completion`；candidate task 9 完成。无 collision/push/drop/wrong-object、qpos/execution、nonfinite、action-mask 或 fallback failure。不能从 timeout 标签臆测更细阶段原因。
- QD mechanism：candidate resolution medians task 3/5/8/9 = `0.62347/0.65301/0.53008/0.49968`，4/4 >=0.20；raw/post overflow P95 `0.9375/0`；occupied-mode ratios `1.20/1.091/1.182/1.182`，archive spread medians `0.238/0.222/0.221/0.210 m`，无 collapse；latency ratio `0.96824`。
- Accounting/budget：attempt audit expected/actual effective cells `14/14`、global reservations 26，PASS；Dev-A walls `736.411/864.636 s = 0.444735 GPU-hours`。Mechanism+Dev-A `0.746570`，含 pre-episode incident 总计 `0.770164/48 GPU-hours`。
- Evidence：GPU admission `0bd1214c…1b1b`；attempt ledger `591be919…ade7`；run CSV `34482e0e…8280`。
- 首次 Dev-A audit（INVALID）：`analysis/dev_a_audit.json`，size 361,984，SHA-256 `95d7d1fbb8fe0f076267cdc4af2aedcad8c7822be6128b53f948d7e8e23e3d4a`。唯一 hard failure 是其 internal `MECHANISM_AUDIT_PATH` 仍读取 invalid v1；同一 artifact 中其余 target/validity/mechanism/safety/latency/attempt/credential/budget 全 PASS。
- Protocol-first：新增 v8，只允许一次 no-episode v2 audit，同时设置 in-memory upstream path 为 immutable mechanism v2 并复用 strict credential predicate；不覆盖 v1、不修改 source、不重跑 task。若 v2 PASS，run_010 才能冻结为 Dev-A promotion PASS 并进入新 Dev-B protocol；当前 formal 仍 0。

#### T. Dev-A audit v2 PASS 与 promotion decision

- Protocol/result order：v8 commit `a49895c71df509c2a2ee6572893faf242057efd6` 先于 corrected audit；未产生新 API/GPU/attempt/episode/formal work。
- Immutable v2：`analysis/dev_a_audit.v2.json`，mode 0444，size 361,936 bytes，SHA-256 `9c6d3ecee60d50c7e574b2a795c864483c85c812c0883a96ec81aa5d5d889fa9`。Invalid v1 `95d7d1fb…3d4a` 同时 mode 0444 保留。
- Audit：`passed=true`、hard failures 0；task matrix candidate `[9]` vs control `[]`，gained `[9]`、lost `[]`；mechanism support 4/4；post-overflow 0；latency ratio `0.96824461`；attempt、safety、artifact、strict credential gates 全 PASS。
- Target gap 分析：本 split 从 paired control `0/4` 提升到 candidate `1/4`，新增一个 target-linked task success；但正式 best 仍是历史 `2/10`、formal target gap 仍 3，因为 Dev-A 不能替代 validation/formal。结果方向与“恢复 task 9 retention sentinel”预测一致。
- Decision：`KEEP_AND_AUTHORIZE_DEV_B_PROTOCOL`。Candidate code/config/threshold 不变；Dev-B 必须使用独立 seeds `[558482,165717,160148,160312]` 复现方向。不得直接跳 validation，不得因 Dev-A success 调参。

#### U. Dev-B confirmation protocol v9

- 状态：`DEV_B_PROTOCOL_LOCKED`；protocol 在任何 runner 修改、manifest、reservation/dispatch/result 前提交。
- 目标依据：Dev-A candidate 以 task 9 取得 `1/4 vs 0/4`，但正式 best/gap 仍 `2/10 / 3`。Dev-B 只回答独立 seeds 是否复现真实 success 优势，不为机制叙事追加计算。
- Matrix：unchanged control/candidate × tasks `[3,5,8,9]` × Dev-B seeds `[558482,165717,160148,160312]`，8 full episodes。
- Algorithm freeze：`qd_ed.py 1516bb75…70b9`；`rdt_policy_steer.py b8806d7a…c1ff2`；`eds_eval_metrics.py d8fb4d04…429`；`config.yaml b20791a2…daf8`。只允许 dedicated runner/tests plumbing。
- Promotion：Dev-B candidate 必须 `>=control+1`、zero lost、gained-minus-lost `>=1`；pooled Dev-A+Dev-B >=1；validity/safety/mechanism/latency/accounting/artifact/credential/budget 全 PASS。Success tie 直接 revert，不接受 proxy-only。
- Manifest：implementation/test commit 后冻结新 `dev_b_manifest.json`，绑定 original manifest、mechanism/Dev-A v2、algorithm blobs、checkpoint/LIBERO/cache/matrix/caps，`formal_authorized=false`。
- Budget projection：新增 unique/effective cells 8，预计 reservations 34、effective cells 22；按 Dev-A device wall 估计新增约 `0.445 GPU-hours`，总计约 `1.215/48`。
- Decision boundary：PASS 仅授权新 validation protocol；FAIL 则 revert causal-envelope 并 outer-loop，不能相邻调参。当前无 validation/formal authorization。

#### V. Dev-B runner implementation 与 tests

- Protocol-first：v9 commit `9664b9259373897fdeadd7b1963d8e1a00353dd6` 早于 runner/tests 修改。
- TDD 红灯：新增 matrix、strict credential、target gate、manifest 与 pre-reservation/binding tests 后为 `4 failed, 6 passed`，失败准确对应缺少 Dev-B level/target/manifest API 和旧 `Task-Specific` 误报。
- TDD 绿灯：dedicated runner tests `12 passed in 1.22s`；py_compile PASS；冻结九文件 suite `785 passed in 75.95s`。
- Runner change：新增 Dev-B level/seeds、versioned manifest freeze/validation、Dev-A PASS pre-gate、Dev-B CLI、target/pooled/mechanism/safety/latency/accounting/budget audit；Dev-B jobs 绑定新 manifest。没有 validation/formal command。
- Credential fix：canonical detector 只匹配 present environment secret equality、standalone long `sk-` token、长 API assignment 或 Bearer；普通 `Task-Specific` 不再误报，真实长 token test 仍 fail closed。
- Algorithm freeze verification：`qd_ed.py 1516bb75…70b9`、`rdt_policy_steer.py b8806d7a…c1ff2`、`eds_eval_metrics.py d8fb4d04…429`、`config.yaml b20791a2…daf8` 全部不变；算法 iteration 仍为 1。
- 当前无新 artifact/attempt/GPU/task/formal 结果。下一步：提交 implementation/state 后，从该 exact commit 冻结 immutable Dev-B manifest；未冻结前不得 dispatch。

#### W. Dev-B immutable manifest freeze

- Implementation commit/code-state：`9ae7c00c0699c3a27b8424ffddd64ad8eb6615cb` / `03119526333d76fcbead4cd58453fd3e0dca7437ef92ad86e4d825475307b59e`。
- Manifest：`manifests/dev_b_manifest.json`，mode 0444，size 8,682 bytes，file SHA-256 `375f78307ab4b02b112979486cccadd8bfcda6982133dd3fafdfc5c89919d9d6`，payload `296b25a832292be31a0a3d089b1f7d0dde7f0655a74e475861633d15b73ff3db`。
- Binding：original manifest `cb211e2e…ae34`、mechanism v2 `c7e93f92…08ab`、Dev-A v2 `9c6d3ece…9fa9`、checkpoint aggregate `a2026bcf…6c28`、LIBERO inputs `259c469e…38b8`、runtime cache、algorithm four hashes 与 exact 8-cell matrix。
- Policy：attempt cap 143、GPU-hour cap 48、GPU 0–7、strict perturbations、720 steps、`formal_authorized=false`；validation/formal CLI 不存在。
- 状态：`DEV_B_READY`。下一步只允许 detached implementation commit 上 preflight/health、fresh GPU admission、IDs 27–34 reservation/dispatch；若任何 pre-reservation gate fail，不创建 attempts。

#### X. Dev-B pre-reservation execution-context failure 与 v10

- 首次 invocation 通过 manifest/storage/credential health 与 fresh admission 后，在 `_attempt_records` 因 `KeyError: execution_record` 中止。
- Root cause：dedicated `configure_base()` 的 temporary `base.P2_LEVELS` union 只含 mechanism/Dev-A，遗漏新 Dev-B；base binder 按 fail-closed 规则原样返回 job。
- Boundary：attempt ledger 仍 `591be919…ade7`，IDs 27–34 不存在；无 `dev_b__*` output、worker、episode、task outcome 或 device-wall GPU-hour。分类为 pre-reservation infrastructure，不是 candidate result。
- Admission evidence：`gpu_eds_qd_autoresearch_dev_b_1786410996.json`，SHA `fa8d86718045a87a6cfcf3ef3e6dfd42b134fed16c6cc784ad402d497559310c`，selected 0/1；不得复用。
- Protocol-first v10：只允许 whitelist 一行修复 + real-binder test；因 code-state 改变，保留 manifest v1 `375f7830…d9d6`，从 repair commit 新冻 `dev_b_manifest.v2.json` 后 fresh admission。算法 hashes/gates/matrix 不变。
- Budget/target：attempt/GPU/task/formal 增量 0；best/gap 仍 `2/10 / 3`。若再次发生 pre-reservation code-path failure，停止 Dev-B 并 outer-loop，不再追加 runner repair。

#### Y. v10 execution-context repair implementation

- Protocol-first：v10 commit `922d435325fc24460f38d3b6c9309bc819d6f5f7` 早于 repair code/test。
- Real-binder TDD：在仅加入 `base.P2_LEVELS` 后首先因 `stage_dir` 仍不识别 Dev-B 红灯；同一 execution-context 边界内把 Dev-B 加入 level 与 stage-dir 两处 mapping 后，bound jobs 均含 execution record、config fingerprint 和 versioned manifest binding。
- Manifest versioning：constant/schema 升级到 `dev_b_manifest.v2.json` / v2；freeze 必须验证 preserved v1 mode/hash，v1 永不覆盖。
- Tests：dedicated `12 passed in 1.35s`；py_compile PASS；冻结九文件 `785 passed in 74.73s`。
- Algorithm freeze：四个 algorithm/config SHA-256 再次与 v9 完全一致；无 algorithm iteration 增量。
- 当前无新 manifest v2/attempt/GPU/task/formal。下一步：提交 repair implementation，从 exact commit 冻结 manifest v2，随后才允许 completely fresh admission。

#### Z. Dev-B manifest v2 freeze 与 final readiness

- Repair commit/code-state：`31bb8d5bb7a9a30f83de1b03abf36af5e9e2d381` / `63b380a786692fa57e76205b525d2c83d7a1322616ad970f821f88126accf258`。
- Manifest v2：`manifests/dev_b_manifest.v2.json`，mode 0444，size 8,963 bytes，file SHA `20b1349da2f09335f1ce1be7f96e7cdd81c1bb689b41dfb6d275acdaaaa1278e`，payload `05a8ff3f388e1da3486203aaf889fa4bcf59978a37e5f88ea38e8c31327e78ba`。
- Preservation：v2 显式绑定 preserved v1 `375f7830…d9d6`，以及 v9 的 original/mechanism/Dev-A/algorithm/checkpoint/LIBERO/cache/matrix/caps 全部不变。
- Binding probe：control/candidate bound jobs 均含 execution record、config fingerprint，manifest SHA 均精确为 `20b1349d…278e`。
- 状态：`DEV_B_FINAL_READY`。下一步 detached `31bb8d5` 完全 fresh health/admission；成功才创建 IDs 27–34。若再发生 pre-reservation code-path failure，按 v10 stop boundary 中止 Dev-B。

#### AA. Dev-B execution/audit PASS 与 validation decision

- Execution：fresh admission artifact `73a0da5e…06dc`，GPU 0/1；IDs 27–34；wrapper exit 0 / wall `851.9 s`。Control/candidate 两 jobs 均 valid，manifest SHA `20b1349d…278e`。
- Task matrix：control tasks 3/5/8/9 = fail/fail/fail/fail（`0/4`）；candidate = fail/success/success/fail（`2/4`）。Gained `[5,8]`、lost `[]`；Dev-B target gain +2，和 Dev-A `[9]` pooled gained-minus-lost `+3`。
- Failure analysis：control 四 tasks 与 candidate tasks 3/9 为 `timeout without completion`；candidate tasks 5/8 完成。Collision/push/drop/wrong-object、qpos/nonfinite/action-mask/fallback 全 0。
- Mechanism：resolution medians task 3/5/8/9 `0.48837/0.52565/0.49856/0.60343`，4/4 >=0.20；raw/post overflow P95 `0.971875/0`；archive mode ratios >1、spreads `0.212–0.227 m`；latency ratio `0.966079`。
- Budget/accounting：Dev-B walls `807.166/694.879 s = 0.417235 GPU-hours`；含 incident/mechanism/Dev-A 累计 `1.187398/48`。Attempt expected/actual effective `22/22`，global reservations 34，PASS。
- Immutable audit：`analysis/dev_b_audit.json`，mode 0444，size 361,566 bytes，SHA `7a73b3ae67d3980147bb48d14198b4de9cbabb14262c82effce656b3f91ff64f`；hard failures 0，strict credential scan 544 files / 0 failures。
- Target impact：development direction连续两 split 正增益且零 loss，支持 candidate 可能缩小正式 gap；但 formal best/gap 仍 `2/10 / 3`，因为 development outcome 不替代 validation/formal。
- Decision：`KEEP_AND_AUTHORIZE_NEW_VALIDATION_PROTOCOL`。Candidate code/config/threshold 必须保持不变；下一步 full 10-task independent validation paired control/candidate。当前 formal 仍未授权。

#### AB. Full validation protocol v11

- 状态：`VALIDATION_PROTOCOL_LOCKED`，任何 runner change/manifest/reservation/result 前提交。
- 依据：Dev-A/Dev-B unchanged candidate 对 paired controls 分别 `1/4 vs 0/4`、`2/4 vs 0/4`，pooled gains tasks 9/5/8、zero losses。Validation 直接检验达到 5/10 的可迁移性。
- Matrix：control/candidate × tasks 0–9 × seeds `[41678,829779,856474,666150,876784,652882,288157,522484,262295,200894]`，20 full episodes。
- Goal gate：candidate 必须 validation `>=5/10`、不低于 control、gained-minus-lost >=0；否则不运行 formal。不能用 validation outcomes 调参后复用 split。
- Mechanism/safety：resolution >=0.20 至少 7/10 tasks、post overflow <=0.25、archive noncollapse、latency <=1.25x、calls/accounting/safety/credential 全硬门。
- Implementation：只允许 dedicated runner/tests；algorithm four hashes冻结。Implementation commit 后新冻 `validation_manifest.json`，`formal_authorized=false`。
- Budget：新增 effective/unique cells 20，预计 global effective 42 / reservations 54；按 Dev-B 比例约新增 `~2.09 GPU-hours`，projected total `~3.28/48`。
- Decision：PASS 仅冻结 single validation winner 并授权新 formal protocol；FAIL 则 `CONCLUDE_VALIDATION_NO_FORMAL`。当前 formal 0。

#### AC. Validation runner implementation 与 tests

- Protocol-first：v11 commit `4b9c72c0eec68538839195a181bd5128b44ab4d7` 早于 runner/tests 修改。
- TDD：新增 validation level/matrix/target/manifest/pre-gate/real-binder tests 后 `5 failed, 10 passed`；实现后 dedicated `16 passed in 1.59s`，py_compile PASS。
- Frozen regression：九文件 suite `789 passed in 88.75s`。
- Runner：新增 exact 10-task validation seeds、20-cell versioned manifest、Dev-B PASS pre-gate、10-episode run count、`>=5/10`/not-below-control/7-of-10 mechanism/safety/latency/accounting/budget audit；无 formal command。
- Algorithm freeze：四个 algorithm/config hashes 与 v9/v11 完全一致；算法 iteration 仍 1。
- 当前无 validation manifest/attempt/GPU/task/formal。下一步从 committed implementation freeze manifest；未冻结不 dispatch。

#### AD. Validation immutable manifest freeze

- Implementation binding：`838b5550f96dfb9d8dbcf59bfc8052b9e1038350`；code-state `5446d4fd7a1011fc1c1b96a5cd4d1c7abaa4cc976657a0241e802385c8cf5024`。
- Manifest：`manifests/validation_manifest.json`，mode 0444，size 9,055 bytes，file SHA-256 `0b9a19fc648bc7b0cf7291bd003387c01be82a015087b684e2d85007d41acd02`，payload `242833f405d48d282238e7739ff94e8620c733980be72ea8ad080e3e479916a3`。
- Exact matrix：control/candidate × tasks 0–9 × frozen validation seeds，共 20 episodes；matrix SHA-256 `a2bd300ffd8fe95be554832d7c6c7b1da2f8c6811a77d4fca70799f40cdaba81`。两个 bound jobs 均含 execution record，并精确引用该 manifest file SHA。
- Parent/identity：绑定 original run manifest、mechanism v2、Dev-A v2、Dev-B manifest/audit、checkpoint、LIBERO inputs、runtime cache 与未改变的四个 algorithm/config hashes；`formal_authorized=false`。
- 状态：`VALIDATION_READY`。Freeze 本身新增 attempt/GPU/task/formal 均为 0；下一步只允许 detached implementation commit 上 fresh health/admission 后执行 IDs 35–54。Validation PASS 才能另立 formal protocol，FAIL 必须不运行 formal。

#### AE. Validation pre-reservation GPU admission wait

- Invocation boundary：在 detached implementation `838b555…` 以 ephemeral runtime credential 调用 frozen `run-validation --gpus auto`。Immutable parent evidence、validation manifest、runtime cache 与 credential health 已通过；two-snapshot admission 返回 `eligible_gpu_indices=[]`，随后 `_select_gpus` fail closed。
- Resource cause：连续 snapshots 中 GPU 0–7 每张均存在外部 compute process；冻结方案禁止任何共卡。后续约 55 分钟只读监控仍显示跨八卡外部负载，且期间出现更多外部进程；本研究未终止、暂停、修改或抢占它们。
- Failure boundary：发生在 admission artifact 写入、immediate dispatch snapshot、attempt reservation、worker/model load、API episode 与 LIBERO reset 之前。因此没有失败 admission artifact；这不是算法/task outcome，也不占 same-cell recovery。
- Accounting proof：episode attempt ledger 仍为 42 JSONL records、22 effective cells、last attempt ID 34，SHA-256 `beee12bf7c142fabfe5ee29b62700c9d51d16a412bb4bd88b83d720406d9ccc4`；`validation__*` output directories 为 0；新增 attempt/episode/device-wall GPU-hour/formal use 全 0。
- Target impact：candidate validation 仍未观测，历史正式 best `2/10`、gap 3 不变。Decision `WAIT_FOR_FRESH_GPU_ADMISSION_WITHOUT_PROTOCOL_OR_SCIENCE_CHANGE`；资源可用时从同一 detached implementation/manifest 重新 fresh admission，不修改 matrix、seed、gate 或算法。

#### AF. Validation execution, target FAIL, and no-formal decision

- Iteration：`run_010_causal_envelope_candidate / H1 / QD-1 validation / CONFIRMATORY`。问题是 causal-envelope 在 Dev-A/Dev-B 的 tasks 9/5/8 gains 是否能迁移并达到 `>=5/10`；prediction 为 candidate 至少 5 successes、不低于 control、zero net loss，同时 mechanism/safety/compute gates PASS。
- Frozen change map：算法 iteration 仍为 1，只改变 QD bounds update 为 `causal_envelope_v1`；current offspring 驱动 no-shrink bounds、incumbent/visit deterministic rebin，reward/fingerprint global-best execution 不变。Protocol/implementation/code-state：`4b9c72c…4ab4d7` / `838b5550…1038350` / `5446d4fd…5024`。四个 algorithm/config blobs 与 validation manifest `0b9a19fc…d02` 均未改变；protected untracked design 未 stage/commit。
- Resource recovery：首个 invocation 因八卡均有 external compute process 在 reservation 前 fail closed。等待后 fresh admission `e03d1e7f…36eda` 选 GPU 0/1，UUID `GPU-4c78c923…118e` / `GPU-053aaa97…8877`；两次 snapshots 与 dispatch 均 143,149 MiB free、0% util、零 compute process。未共卡、未抢占外部进程。
- Exact matrix/command：control/candidate × tasks 0–9 × seeds `[41678,829779,856474,666150,876784,652882,288157,522484,262295,200894]`；detached implementation 上 `python scripts/eds_qd_autoresearch_runner.py run-validation --gpus auto --timeout-seconds 28800`，runtime credential 仅进程环境使用。
- Task result：control tasks 0–9 全 fail（`0/10`）；candidate 仅 task 0 success（`1/10`），tasks 1–9 fail。Gained `[0]`、retained `[]`、lost `[]`、net +1。全部失败只标记 `timeout without completion`，不能据此臆测更细 causal stage。Dev-A/Dev-B gains tasks 9/5/8 均未在 validation 复现。
- Target gap：candidate 距 validation target 4，且比 historical EDS-QD best `2/10` 少 1；formal 未运行，因此 historical formal best/gap 仍 `2/10 / 3`。唯一 hard failure 是 `candidate validation success is below 5/10`，不能由 proxy 覆盖。
- Mechanism：resolution medians tasks 0–9 为 `0.628/0.544/0.592/0.556/0.579/0.624/0.594/0.623/0.486/0.601`，10/10 >=0.20；raw/post overflow P95 `0.9375/0`；occupied-mode ratio 全 >1，archive spread median `0.195–0.226 m`，无 collapse。Selection latency P95 `2.991739 s`，对 sparse ratio `1.092159 <=1.25`。
- Safety/validity：两 jobs valid/exit 0；collision/push/drop/wrong-object、qpos、nonfinite、action-mask、QD fallback 全 0。Strict credential scan run-root 947 files、0 failures；未记录 credential value/fingerprint。
- Accounting/artifacts：IDs 35–54；control/candidate walls `3140.809/3149.717 s`，validation `1.747368 GPU-hours`，累计含 incident `2.934767/48`。Attempt expected/actual effective `42/42`，dispatched/reserved `42/54`，ledger `df733b97…da1a`。Run CSV `ed3f6bbf…de2`。Artifact aggregate control `a5e1a953…289`（1,560 files），candidate `e43e034c…e0cf`（1,800 files）。
- Immutable audit：`analysis/validation_audit.json`，mode 0444，size 880,602 bytes，SHA-256 `3f72d025b492e24e7f615db7c3207c4927710794797dd228edf0579ab1290774`；`passed=false` 仅因 target gate。
- Interpretation：H1 partition-resolution mechanism 被跨十 tasks 支持，但“该机制足以将成功率推到 5/10”被否证。更好 resolution 不是 completion 的充分条件；development gains 的幅度不具 validation 稳健性。不能将 10/10 mechanism support 误报为算法成功。
- Decision：`REJECT_CAUSAL_ENVELOPE_AS_INSUFFICIENT_AND_CONCLUDE_VALIDATION_NO_FORMAL`。按 v11 不运行 formal、不修改 candidate 后复用已揭示 validation、不做相邻参数试探；触发 outer-loop cycle 2 决定当前冻结 cycle 的 CONCLUDE 或 versioned redesign 请求。

#### AG. Outer-loop cycle 2 conclusion protocol

- Trigger：valid validation target FAIL 与 development/validation magnitude mismatch；formal 未授权。Outer-loop 对 descriptor/quality/ecology/continuity/execution 证据重新分类，优先判断是否存在不泄漏且能直接缩小 4-success validation gap 的同-cycle next candidate。
- Read-only evidence：当前 validation audit `3f72d025…0774` 与 result analysis `a6d02543…8c5b3`；search-budget report `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/outputs/search_budget_sweep_20260808/analysis/final_report.md`，SHA `580cf8c0…30c1e`（18 configs 全 0/10 或 1/10）；Stage/guidance report `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/outputs/stage_guidance_transition_20260810/analysis/final_report.md`，SHA `ecc7554c…ac426`（FSM 0/20、lost task 7、safety FAIL）。外部源零写入。
- Synthesis：H1 的 descriptor partition 问题确实存在但不是 dominant completion bottleneck；直接 compute scaling 已被否证为有效方向；generic Stage/guidance transition 既无 success 又有安全/retention 退化；H4 telemetry 无有效结论；H2 reward-quality/final-selection 仍是 EDS+QD 内合理方向，但没有已冻结且未见 validation 的候选。
- Isolation boundary：validation seeds 已揭示。任何现在基于结果修改的 H2/H3/H4 candidate 均不能复用它们；没有新的 holdout seeds/预算/design authorization 时无法生成 formal-eligible winner。此边界比剩余 GPU/attempt budget优先。
- Protocol-first：新增 `protocol-v12.md`，在 cycle decision manifest/final report 前冻结：0 algorithm/config/GPU/API/LIBERO/attempt/formal；只允许 evidence freeze、final reporting 与 strict scans。
- Direction：`CONCLUDE_NO_ADOPTION_WITHIN_FROZEN_CYCLE_REQUEST_VERSIONED_REDESIGN`。未来最有依据的 redesign proposal 是 H2 QD quality/replacement/final-selection calibration，但必须新设计、新 leakage-safe holdout seeds、明确预算和用户批准；当前不执行。

#### AH. Cycle decision freeze and final handoff

- Protocol/result order：validation result commit `eca85e69504cb4240e8b059f65f6237d4fb54272` 先于 conclusion protocol commit `028e3029ee13a7139b5508d250ec9e9947334b80`；v12 又先于 decision manifest/report。没有 post-validation algorithm/config change 或 episode。
- Immutable decision：`manifests/cycle_decision_manifest.json`，mode 0444，size 5,263 bytes，SHA-256 `dc443cea6baa1194aead93b289a5aef36dde67de54114aa017c53b25727b06a0`。绑定 frozen design、v11/v12、implementation/code-state/result commit、四个 algorithm hashes、validation/mechanism/Dev audits、task matrix、attempt/GPU-hour、formal=0、write boundary 与 credential=false。
- Final objective：未达成。Candidate validation `1/10`，gap 4；historical formal best/gap `2/10 / 3`，因为 formal 正确未运行。Mechanism 10/10 PASS 不能覆盖 target FAIL。
- Budget final：42 effective online episodes，54 total reservations，`2.934767/48 GPU-hours`，formal episodes 0。剩余预算不授权突破 holdout isolation。
- Reports：`docs/03_evidence/eds_qd_autoresearch/2026-08-11-eds-qd-autoresearch-final-report.md`，SHA `6bce8c7b…a54858d`；`to_human/progress-002.html`，SHA `3c0efdbd…f294af`。Canonical ledger 本文保留全部算法改动、protocol/result、task-level outcome、failure、GPU、artifact/hash 与 decision。
- Workspace：所有 code/docs 修改仅当前 branch/worktree；large artifacts 仅 owned root；protected `docs/01_specs/2026-08-10-eds-qd-stage-guidance-transition-design.md` 保持 untracked、未修改、未 stage/commit；历史 worktree/shared2 只读。
- Final state：`concluded_no_adoption_current_cycle`，GPU/formal execution disabled。未来若要继续，必须显式批准 versioned redesign：新 validation holdout、新预算，并限定 H2 QD quality/replacement/final-selection；不得复用已揭示 validation 做 tuning。

#### AI. 用户恢复授权与 v2 H2 protocol freeze

- 恢复原因：用户于 2026-08-12 明确要求继续 autoresearch，满足 AH 要求的 versioned redesign 用户授权。上一周期停下是 validation `1/10 < 5/10` 后的 protocol-mandated no-formal/leakage stop，不是 GPU、密钥或实现故障。
- 新设计：`docs/01_specs/2026-08-12-eds-qd-autoresearch-v2-quality-selection-design.md`。旧 validation seeds 仅为 `HISTORICAL_REVEALED_DIAGNOSTIC_ONLY`；新 Dev-A、Dev-B、validation seeds 用冻结 SHA-256 规则生成且与旧 splits/formal 不重叠。
- H2 证据：`core/qd_ed.py` 在 equal reward 下由 fingerprint tie 决定 replacement/global selection；owned runtime cache 的 Stage-2 guidance 返回 exact zero 并声明 placement 由 policy 完成。当前 QD 因而在无 quality signal 时由 task-agnostic hash 接管 action。
- 单候选边界：先执行 `run_020_quality_selection_calibration` 零-episode replay；PASS 后最多实现一个 `reward_degenerate_control_fallback_v1`。不加入 endpoint heuristic、threshold sweep、Stage 修改、memory、compute scaling 或第二候选。
- Promotion：Dev-A/Dev-B 各要求 candidate `>=3/6` 且 paired +1；validation/formal 均要求 `>=5/10`、不低于 control、gained >= lost 和全部硬门。任一 FAIL 立即停止后续 split。
- 预算：v1 已用 42 effective / 54 reservations / 2.934767 GPU-hours；v2 scientific cells 最多 70，全部执行后 global reservations 124，保留 19 recovery slots；原 143/48 上限不变。
- 当前授权：只允许 run_020 diagnostic implementation/result；算法修改、GPU、API、LIBERO attempt 和 formal 均未由本 protocol 授权。受保护未跟踪文件保持未读取、未修改、未 stage/commit。

#### AJ. run_020 H2 zero-episode calibration PASS

- Protocol/implementation：`a0b4cada663c9efa1f611177c2710f84509bc9d7` / `174630302cbfa6668292bc566c54d3e738159e27`。新增诊断 tests `7 passed`；原 QD archive/runner/audit `60 passed`。
- Raw prevalence：50 metrics files、7,080 valid/unique QD rows；473 exact-zero final archive-quality chunks，tasks 0–9 全覆盖；historical 411、owned v1 62；retrospective fail/success 468/5。Success 分层只用于避免过度结论，不能作为在线 feature。
- Guidance/code：Stage-2 source SHA `ca058cc1…03f84`，AST exact-zero PASS；core policy SHA `b8806d7a…c1ff2`，existing non-QD control branch/fixed iteration loop PASS，候选 projected compute 176 evaluations / 11 score calls。
- Trace replay：44/44 recorded reward/fingerprint selections reproduced；44/44 nondegenerate selections preserved；equalized quality 下 changing fingerprint tie direction 在 44/44 改变 action，而 reverse input order 在 44/44 不改变 smallest-fingerprint winner。结论是 tie task-agnostic/hash-dependent，不是 input-order bug。
- Determinism/artifact：canonical/replay mode 0444、size 505,982、共同 file SHA `56c05f906528de78d720d99366b8db39e7ec84518968c8ec01cb9508ceb31034`；payload SHA `62ec4622…baa87`；credential matches 0。
- Budget/target：online attempts 0、GPU-hours 0；historical formal best/gap 仍 `2/10 / 3`。Proxy PASS 不代表成功率已提高。
- Decision：`KEEP_H2_CALIBRATION_PASS_AND_AUTHORIZE_ONE_QD1_PROTOCOL`。下一步必须先冻结 `reward_degenerate_control_fallback_v1` implementation protocol；当前尚无 core/config 修改，GPU/LIBERO/formal 仍未授权。

#### AK. run_021 H2 candidate implementation protocol

- Parent：run_020 result `3065fad8f248292aeb680d4b8b93d212f01d799b` / artifact `56c05f90…1034`。Algorithm iteration 2 只增加 H2 exact-degenerate fallback，H1 causal-envelope substrate 不变。
- Rule：initial population reward validation 后，`grid_archive + control_v1 + all rewards exactly equal` 才逐 chunk 禁用 QD archive ecology并复用 existing non-QD EDS path；无 epsilon/Stage/task/job/outcome/future-state feature。
- Compatibility：default `none`、legacy QD equal-reward fingerprint path、nondegenerate causal-envelope QD、`qd_archive_mode=none` 全部保留。Fallback 无跨 chunk hidden state。
- Accounting：新增 configured-vs-active/fallback/reward/search-evaluation metrics；fallback QD evaluations 0，但 complete search 176 / score calls 11；active QD complete search/QD evaluations均176。
- Whitelist：仅 core policy、EDS metrics、config default、`test_rdt_steer.py`；protocol commit 必须早于所有 core/config edits。当前 GPU/API/model/LIBERO/attempt/Dev/Validation/Formal 授权仍为 0。

#### AL. run_021 H2 candidate implementation PASS

- Protocol/implementation：`7afebccaf02d4f0cbb4da2c930e31e4cb267f30e` / `f010e8e4ff1f129e12499b1e0f8d284f505f7455`，顺序正确。Algorithm iteration 2 只增加 `qd_degenerate_fallback_policy=none|control_v1` 与逐 chunk exact-equal reward gate。
- Core behavior：candidate 在 initial rewards 非空、finite、全部逐位相等时不创建 QD archive，复用原 non-QD EDS parent/final-selection path；下一 chunk 重新判断。无 epsilon、Stage/task/job/outcome/future feature，无额外 model/reward/VLM call。
- Compatibility：default `none` 的 exact-zero legacy QD path 保留；nondegenerate `control_v1` 与 `none` 的 selected action bit-identical，fingerprint、bounds checksum、visits、initial/per-iter archive snapshots 恒等；`qd_archive_mode=none` 不调用 detector。
- Accounting：fallback complete chunk 为 search evaluations `176` / score calls `11` / QD evaluations `0`；active QD 为 `176/11/176`。新增 configured-vs-active、policy/used/reason/value 和 search count metrics，可 JSON 序列化。
- Tests：focused `6 passed`；QD archive/metrics/runner/audit/autoresearch/calibration/full RDTSteer `463 passed in 48.03s`；general EDS eval runner `237 passed in 38.09s`；非重叠总计 700 PASS。py_compile、diff check、四文件 whitelist 和 credential scan PASS。
- Blobs：policy `890068dd…159e`；metrics `cbe31284…a450`；config `c5844368…acc5e`；tests `632e694a…c5e`。Protected untracked design 保持未读取、未修改、未 stage/commit。
- Result analysis：`experiments/run_021_reward_degenerate_control_fallback/analysis.md`，SHA-256 `9d2ef19a42b7bfd1df66e1bbae6b2b8af728489db2b01185cd987b74f2792bd3`。
- Target/budget：这只是 offline implementation evidence，新增 online episode/GPU-hour/reservation/formal 均 0；historical formal best/gap 仍 `2/10 / 3`，不得声称成功率提升。
- Decision：`KEEP_IMPLEMENTATION_PASS_AND_REQUIRE_PROTOCOL_FIRST_OFFLINE_MECHANISM_PREFLIGHT`。下一步仅可先提交 deterministic exact-zero/nondegenerate mechanism preflight protocol；GPU/API/model/LIBERO/Dev/Validation/Formal 仍未授权。

#### AM. run_022 offline mechanism preflight protocol

- Parent order：run_021 protocol/implementation/result 为 `7afebcc…` / `f010e8e…` / `7d131fd…`。Run_022 不改变 algorithm iteration 2 的 core/config blobs。
- Fixture：冻结 float64 `(16,64,128)` population、4x4 endpoint layout、seed `22022` 与十个 deterministic rollouts；integrated loop 运行 candidate/control/legacy QD 的 exact-zero、equal-negative、`1e-12` near-equal 与 nondegenerate cases。
- Gates：exact-equal candidate 必须与同输入 EDS control 的 selected/final/RNG 恒等且 `176/11/0`；legacy exact-zero 必须保留 archive/fingerprint path `176/11/176`；near-equal/nondegenerate candidate 与 legacy 的 action/archive/bounds/visits/RNG 完全恒等；全部 safety/accounting PASS。
- Determinism/artifact：两次完整运行 scientific payload byte-identical；canonical/replay 仅写 owned `run_022.../analysis`，mode 0444、identical bytes、credential 0。
- Whitelist：只允许新增 dedicated script/test；existing core/config/runner/audit/Stage/prompt/历史 artifact/protected design 零修改。当前 online/GPU/API/LIBERO/attempt/Dev/Validation/Formal 授权仍为 0。
- PASS 仅授权新的六 episode online mechanism protocol；FAIL 则 no-online。任何 schema-only repair 也必须 protocol-first，不能改科学 gates。

#### AN. run_022 offline mechanism preflight PASS

- Protocol/implementation：`cb87d75f7779569889994ae3e2efff64e0942ec7` / `786e7ed1310fb77bc33b2c04b965c50a45173eeb`。Core/config hashes 与 run_021 完全不变。
- TDD red history：第一次在 scientific case 前因独立脚本缺 repo `sys.path` 停止；第二次在 active-QD hard gate 因 draft decimal float64 carrier 经 archive float32 往返末位不等停止。两者均无 artifact/online/GPU/API/model/LIBERO/attempt；最终使用显式 repo import 与 deterministic binary-exact carrier，保留协议的 float64、initial rewards、seed、cases、threshold 与 gates。
- Tests：integrated 8-case + sequential probe PASS；dedicated `3 passed in 97.33s`；run_021 focused `6 passed`；QD archive `22 passed`；py_compile PASS。
- Exact-zero：candidate 与 EDS control selected tensor/fingerprint `01d89d4e…74a3c`、ordered final set `5891b67a…cb82b`、scores/source/RNG 恒等；candidate accounting `176/11/0`。Legacy exact-zero 保持 QD archive selection fingerprint `001564f8…9d261`、final set `03dc76fd…13b4a`、accounting `176/11/176`。
- Nontrigger identity：`1e-12` near-equal 与 nondegenerate candidate 均不触发，和 legacy QD 的 selected `e13b75b0…f9d4f`、final set `4b0b28a7…d00661`、完整 archive/bounds/visits/accounting/RNG 恒等。
- State/safety：同一 instance exact-zero 后的下一 nondegenerate chunk 恢复 active QD/176 QD evals；8/8 cases 均 search 176 / calls 11，nonfinite/mask/accounting/monotonicity/selection violations 全 0。
- Artifact：fixture `78a639ba…979a`；scientific/replay payload `8fd3f06b…c13e`；canonical/replay mode 0444、513,735 bytes、byte-identical file SHA `320fabf54847c77d944ed0ff5bdc2c530331c765d3bcfbef2aa5173c46279bac`；credential 0。只写 owned run_022 root。
- Result analysis：`experiments/run_022_reward_degenerate_mechanism_preflight/analysis.md`，SHA-256 `860d282adf9dd591d0df58f490f928e2f6f541430d4ab8cf4b4ad9e94bb89930`。
- Target/budget：online/GPU/reservation/validation/formal 新增均 0；historical formal best/gap 仍 `2/10 / 3`。Mechanism PASS 不等于 success 提升。
- Decision：`KEEP_OFFLINE_MECHANISM_PASS_AND_AUTHORIZE_ONLINE_MECHANISM_PROTOCOL_ONLY`。下一步必须先冻结 6 episode paired mechanism matrix、profile/runner/audit semantics、manifest、admission 和预算；Dev-A/B、validation、formal 尚未授权。

#### AO. run_023 online mechanism protocol

- Evidence selection：run_020 的 tasks 2/3/9 分别有 109/97/34 exact-degenerate chunks，owned-v1 为 11/49/2，三者 earliest global step 均 24；在 seed 生成前据此冻结 `max_chunks=16`。该历史统计不进入在线算法。
- Matrix：control/candidate × tasks `[2,3,9]` × seeds `[932032,615132,718536]`，共 6 unique cells；seeds 来自 v2 `mechanism` SHA rule。Control 是原 `p2_stage_on_abs_rbf_control`；candidate 是 sparse causal-envelope QD + 唯一 H2 `control_v1` guard。
- Purpose：只检验真实 chunk 同时出现 fallback/active QD、configured-vs-active telemetry、`176/11` compute、selection、安全、latency、artifact；short task success 只记录，不用于 promotion。
- Implementation boundary：只允许新增 dedicated v2 runner/test；core/config/v1 runner/audit/Stage/prompt/env/executor/evaluator 零修改。Implementation commit 后必须先冻 owned run_023 `mechanism_manifest.json`，绑定全部 code/profile/checkpoint/LIBERO/cache/offline artifact/matrix/caps，mode 0444、credential 0。
- Transaction：manifest/cache/input/code 验证 -> runtime credential + real health（不记录值）-> two-snapshot admission + immediate snapshot -> 才 reserve global IDs 55–60 -> dispatch。此前 global 54；完成 scientific reservations 为 60/143。
- Gates：candidate 至少一 fallback 和一 active chunk；fallback `176/11/0` 且 non-QD selection，active `176/11/176` 且 QD selection；control QD off；全 validity/safety/accounting/credential/write-boundary PASS，candidate latency P95 <= control 1.25x。
- Current authorization：runner/audit implementation 与 manifest freeze only；manifest 前 GPU/attempt=0，Dev-A/B/validation/formal 均未授权。

#### AP. run_023 runner/manifest freeze and pre-reservation credential block

- Implementation/tests：runner commit `d3f09b82dcd87ad0cde2038da0200e93287db3b7`；new/v1 runner+QD tests 88 PASS，run_021 focused 6 PASS，general eval/metrics/startup 352 PASS，非重叠总计 446。Core/config hashes 未变。
- Manifest：owned `mechanism_manifest.json`，mode 0444，size 15,842，file SHA `d51a44042357b129595cc220faeecd5a9029f2424e0b803711a32ed31a8ec718`，payload `944047076b4347e582f9dd442e685c7b820f358e78dd0a9631fca01d700066c3`，code-state `26001c76…bb96`。Control/candidate fingerprints `f21f6ac6…2aa9` / `862b0d95…2d9c`；tasks/seeds/cells/run_022/checkpoint/LIBERO/cache/caps/formal=false 全绑定。
- Transaction failure：manifest/storage/cache/credential-presence PASS 后，真实 pre-reservation Stage/Poe health FAIL。一次脱敏 diagnostic 仅输出 `AuthenticationError / HTTP 401 / invalid_api_key`；credential value、headers、exception text、reversible fingerprint 均未写入。
- Boundary/accounting：failure 在 two-snapshot admission、immediate snapshot、GPU manifest、reservation、dispatch、worker/model、LIBERO reset 前。Run_023 attempt ledger 不存在；global reservations 仍 54，IDs 55–60 未使用；新增 online episode/GPU-hour/validation/formal 均 0。
- Incident record：`experiments/run_023_reward_degenerate_online_mechanism/pre-reservation-health.md`，SHA-256 `779c515a67f0991e381fedad28ceda9b6045a66adb4d77fce06364df0ead00fe`。
- Interpretation：纯 infrastructure/auth blocker，不是 H2 算法或 task outcome；historical formal best/gap 仍 `2/10 / 3`，六 cell 与所有 gates 不变。
- Resume：需要 valid process-environment credential。由于本 incident record 会推进 documentation HEAD，恢复前必须 protocol-first versioned manifest/rebind，保留完全相同 runner/core/config/profile/matrix/input/cache/caps 和未使用 IDs；不得改 science。

#### AQ. run_023 recovery protocol v2 lock

- Trigger：用户再次要求继续并提供 replacement credential material；其值、片段、hash/fingerprint 均不进入任何 research record。
- Secret boundary：当前执行工具没有独立的不序列化 secret/env 注入字段；聊天值不等于进程环境配置。禁止把它拼入 shell command、补丁、文件、manifest、artifact、attempt ledger、文档或 Git。只有从非序列化 runtime environment 读取到凭据时才允许 health。
- Protocol-first：新增 `experiments/run_023_reward_degenerate_online_mechanism/protocol-v2.md`，严格先于 runner/test 与 manifest-v2 变更。
- Frozen science：保留 v1 manifest SHA `d51a4404…c718`，runner science、run_021 core/config、run_022 evidence、control/candidate profiles、tasks/seeds、`max_chunks=16`、checkpoint/LIBERO/cache、gates/caps/formal=false 以及未使用 IDs 55–60 全部不变。
- Authorized plumbing：仅允许修改 dedicated v2 runner/test，引入并验证 immutable `mechanism_manifest.v2.json`，绑定 v1、incident、recovery protocol、implementation HEAD/code-state；v1 必须继续 mode 0444 且 checksum 不变。
- Transaction：v2 freeze/validation -> non-serialized env credential + real health -> fresh two-snapshot admission -> IDs 55–60 reservation/dispatch。任一 health/admission failure仍为 zero-attempt，不能反馈到算法。
- Target/budget：historical formal best/gap 仍 `2/10 / 3`；新增 reservation/episode/GPU-hour/validation/formal 均 0。下一步只做 manifest-v2 plumbing 与测试。

#### AR. run_023 credential health PASS and global-offset pre-dispatch failure

- Manifest recovery：protocol v2 / implementation 为 `70678d2…` / `ac43b87…`；immutable v2 mode 0444、size 16,341、file SHA `8e47ebb3…d2df`、payload `4600fe0b…5185`。父 v1 SHA `d51a4404…c718` 未变；六 cell、science 与 formal=false 不变。
- Credential：用户明确授权直接 runtime injection。值仅进入 detached child environment；没有进入 command line、worktree/artifact、manifest、ledger、docs、Git 或 fingerprint。真实 Stage/Poe health PASS。
- Admission：fresh two-snapshot admission 只允许 idle GPU 2/5；immutable artifact SHA `9ff20450…cbe`。随后精确写入 global IDs 55–60。
- Failure boundary：在 append `phase_dispatch` 时，legacy helper 把 standalone ledger 的 global offset 55 错判为非 1-based contiguous。没有 phase-dispatch event、worker/model、LIBERO reset、output、metric、video、episode 或 task outcome；`0` GPU execution hours。
- Preserved evidence：六行 ledger prefix SHA `6d586f32…47af`；immutable runtime log `fdd858a0…b19c`；output files 0；credential scan 0。任务成功增减与失败原因均为 `N/A / no episode`，不能反馈算法。
- Protocol-first v3：严格在 ledger mutation/runner repair 前冻结。IDs 55–60 将 append-only 标记 `reservation_void`；仅 dedicated v2 runner/test 可增加 global-offset ledger semantics 和 v3 manifest；exact cells 以 recovery IDs 61–66 重跑，并带 `recovery_of_attempt_id`。
- Budget：当前 global reservations 60/143，scientific executions仍 0；授权 recovery 后为 66/143，消耗 6/19 recovery slots、余 13。historical formal best/gap 仍 `2/10 / 3`，formal 0。
- Stop：若修复后再次发生 local pre-dispatch code failure，停止 Run023，不授权第三组 reservation；health/admission wait 不消耗 attempt。

#### AS. run_023 valid online mechanism FAIL and no-Dev decision

- Recovery implementation：protocol/implementation `27fc65c56347a1ee94353511a1d2cf9da3be65a1` / `6374e23a5073f0708ee4345935df024207740258`。Dedicated/global-offset tests + v1 runner/QD `51 passed`；H2 focused test `1 passed`；四个 core/config SHA 与 run_021 冻结值完全一致。
- Manifest v3：mode 0444、17,002 bytes，file SHA `9429fe7420cfb613565fd83ee537e37fba5c3cd43093bc38f0bc1c7087d8793a`、payload `6160bf2d6f4fcf9c53a0613016dc0cc33efe2246870f38257a5550133a15399c`；v1/v2 `d51a4404…c718` / `8e47ebb…d2df` 保持不变。
- Execution：real health PASS 后 fresh admission 选择 GPU 2/5；IDs 55–60 append-only void，exact-cell recovery IDs 61–66 带 parent mapping 并 dispatch。Control/candidate 均 exit 0、3/3 metadata、3 videos、strict perturbation/suite valid。
- Task-level：control tasks 2/3 fail、task 9 success，合计 `1/3`；candidate tasks 2/3/9 全 fail，合计 `0/3`。Candidate gained `[]`、lost `[9]`。全部 failure 只分类为 `timeout without completion`，不臆测 finer cause。
- Candidate mechanism：task 2/3/9 分别 `21/50/3` chunks，fallback 全为 0，active-QD 为 `21/50/3`；74/74 active。最低 reward spread 分别 `0.0135803/0.0122940/0.0351257`，均非 exact zero。Online prospective observation 不支持 run_020 retrospective exact-zero prevalence。
- Compute/accounting：candidate 每 chunk `176 search / 176 QD / 11 calls`；control `176/0/11`。Candidate post-envelope overflow恒为 0，finite resolution median约 `0.6400/0.5741/0.6576`，但这些 proxy 不能覆盖 missing fallback 与 task 9 regression。
- Safety/latency/artifact：disallowed safety、nonfinite、mask/qpos、accounting/monotonicity/selection、Stage/service fallback、credential matches均 0；candidate/control latency P95 `2.98266/2.97889 s`，ratio `1.001266 <= 1.25`；root credential audit 145 files PASS。
- Budget：Run023 `0.812334` GPU-hours，累计 `3.747101/48`；global reservations `66/143`；recovery reserve消耗 6/19、余 13；valid online episodes 6。Formal 0，historical formal best/gap 仍 `2/10 / 3`。
- Immutable result：audit mode 0444、SHA `7f123ecdf3ffb7fbbb881ffebe197ddb2ae8e4b1237233dd2316f6f67e832c54`，唯一 hard failure `candidate missing fallback record`；attempt ledger `3f445b32…a63c`；run manifest `5a142003…b748`。
- Interpretation：exact-equality fallback 在真实新 observation 上完全不激活，candidate 反而丢失 control task 9。禁止改成 tolerance sweep 或追加相邻候选。Decision `CONCLUDE_H2_ONLINE_MECHANISM_FAIL_NO_DEV`；Dev-A/B、validation、formal 全部禁止。
- Next：本 v2 design 的 single candidate 已耗尽；result commit 后必须 outer-loop conclusion。任何后续算法 candidate 都需要 versioned design、新 holdout seeds 与明确授权。

#### AT. outer-loop cycle 3 conclusion protocol

- Trigger：Run023 result commit `00964434d2a5e245758c26f25dbc77e17c182dce` 后，v2 single-candidate promotion FAIL；同 cycle 没有合法 Dev/validation/formal 路径。
- Protocol-first：`experiments/run_023_reward_degenerate_online_mechanism/protocol-v4.md` 在 decision manifest、final report、progress page 与 reflection 前冻结；授权 online/GPU/API/attempt/algorithm change 均为 0。
- Cross-cycle evidence：H1 causal envelope 在 mechanism/Dev 有 proxy/gain，但 validation 仅 1/10；H2 offline exact-zero prevalence/identity成立，但 online 74/74 active、0 fallback，且 candidate 0/3 丢失 control task 9。两轮都没有缩小 formal historical gap 3。
- Observation vs inference：观察到 prospective reward spread 全部严格非零、candidate task 9 proxy并不差但未成功；因此 exact equality 不可用且 reward proxy不能代表 completion。未来 stage-progress quality/retention 仍只是 inference/proposal，尚无授权。
- Frozen decision：`CONCLUDE_NO_ADOPTION_WITHIN_V2_CYCLE_REQUEST_VERSIONED_REDESIGN`。禁止 tolerance sweep、Run023 seed reuse、second candidate、Dev-A/B、validation、formal。
- Redesign boundary：仅可提议 EDS+QD scope 内 QD-first 的 observation-derived stage-progress quality/final selection 或 guarded control-success retention；需要 versioned design、新 holdout、明确 budget 与用户授权。
- Required outputs：immutable v2 cycle decision manifest、final report、progress page、state/log/findings/trajectory/ledger reflection、credential/write-boundary checks与 reflection commit。

#### AU. v2 cycle final reflection and stop boundary

- Immutable decision：owned artifact `run_023_reward_degenerate_online_mechanism/manifests/cycle_decision_manifest.json`，mode 0444、size 5,721 bytes、SHA-256 `4010b620976ee8aa26ee05e6655a60c6ec4bc194511698254e9b2eb0bf9f1334`；冻结 decision 为 `CONCLUDE_NO_ADOPTION_WITHIN_V2_CYCLE_REQUEST_VERSIONED_REDESIGN`。
- Final reporting：`docs/03_evidence/eds_qd_autoresearch/2026-08-12-eds-qd-autoresearch-v2-final-report.md` SHA `30931300…73af`；`to_human/current-status.md` SHA `bf8fb4f2…2174`；`to_human/progress-003.html` SHA `b1e9f598…8094`。
- Target outcome：正式目标 `>=5/10` 未达到。历史 formal best/gap 仍为 `2/10 / 3`；Run023 contemporaneous control/candidate 为 `1/3 / 0/3`，candidate gained `[]`、lost `[9]`，failure 全部仅标记 `timeout without completion`。
- Mechanism conclusion：candidate 74/74 chunks 走 active QD、fallback 0/74；exact-degenerate predicate 在线未激活。H1 改善 partition resolution 但 validation 只有 1/10；H2 offline defect 在线不转移。不得用 proxy 覆盖 success regression。
- Final accounting：跨周期 effective online episodes 48；global reservations 66/143；累计 GPU `3.7471009444444445/48` hours；formal episodes 0；Dev-A/B、validation、formal 均未由 Run023 解锁。
- Integrity：decision manifest 与 Run023 evidence 均位于本研究独占 artifact root；worktree write boundary 保持；protected untracked design 未读、未改、未 stage。Credential 只曾在明确授权的 runtime child environment 中使用，value/fingerprint 未进入 command、worktree、artifact、log、manifest、docs 或 Git；最终扫描要求 zero matches。
- Stop：state 进入 `concluded_no_adoption_v2_cycle_waiting_versioned_redesign_approval`。后续仅可在明确批准的 versioned design、新 leakage-safe holdout seeds 与 explicit budget 下继续；当前禁止 algorithm/GPU/API/LIBERO/attempt/Dev/validation/formal execution。

#### AV. explicit approval and v3 global-quality anchor design

- Authorization：用户在 v2 停止边界后明确回复“批准”，满足 versioned successor design、新 holdout、explicit budget与用户授权四项恢复条件。State 从 concluded/no-adoption 恢复到 v3 design locked；这不是对 v2 split 的继续调参。
- Evidence selection：只读预审计 Run023 666 个可比 parent transitions；prior global-best reward cell 下一 iteration 的 slots 为 0 共 450 次，ratio `0.6756756756756757`。Task 2/3/9 分别 `97/189`、`346/450`、`7/27`。Run000 的 4,705 chunks archive-only parent结论进一步支持 global-quality retention gap。
- Single candidate：`qd_global_quality_anchor_v1`，algorithm iteration 3。每 iteration 固定 1 slot 为 archive global-best parent，剩余 15 使用原 sparse-priority；16 parents 全部正常 renoise/rollout。Causal envelope保留；v2 exact-zero fallback关闭；final selection、Stage、checkpoint、prompt、env、executor、evaluator不变。
- Compute/target：complete chunk冻结 `176 search / 176 QD / 11 calls`；historical formal best/gap仍 `2/10 / 3`。Allocation observation不等于 success evidence。
- Isolation：mechanism tasks/seeds `[3,8,9] / [955865,522754,845886]`；Dev-A `[0,1,2,4,6,7] / [307995,262892,731741,14859,648306,960581]`；validation tasks 0..9 / `[733557,563986,984766,598490,834409,827884,504577,82408,891085,7487]`；全部与先前 split/formal 不重叠。
- Budget：v3 前 48 effective episodes、66 reservations、`3.7471009444444445` GPU-hours、formal 0。新 scientific cap 58；全走完为 124/143，保留 19 recovery；GPU cap仍48 hours。
- Protocol boundary：design commit 前后均无 core/config change、GPU/API/LIBERO/reservation。下一步只能 protocol-first `run_030_global_quality_anchor_diagnostic` zero-episode checksum-bound reconstruction；PASS只授权implementation protocol。

#### AW. run_030 allocation reconstruction protocol

- Temporal lock：v3 design commit `f30e47c` 后、analyzer implementation与aggregate confirmatory result前冻结 `experiments/run_030_global_quality_anchor_diagnostic/protocol.md`。
- Inputs：精确绑定 owned Run010 preflight/Dev-A/Dev-B/validation candidate metrics 与 Run023 candidate metrics，共5 files/419 rows；SHA分别 `09a77e90…7eca`、`535be576…6e84`、`6f948370…048d`、`7afb70e2…00bd`、`f18e2fcf…7273`。Production QD SHA `1516bb75…70b9`；禁止recursive/stale/outcome/protected input。
- Eligibility：每 row只用 i=1..9 的 prior rewards/visits 与 next saved slots；只接受 unique maximum reward，equal maxima因缺 fingerprint tie data而显式排除；固定 run_seed0、episode/global_step/iter、sparse exponent1。
- Baseline：用synthetic archive调用 unchanged production allocator population16，必须 100%等于保存slot map。Candidate：unique global-best dedicated 1 slot + unchanged allocator population15；分别记录dedicated/sparse/total。
- Gates：>=300 transitions/>=3 tasks；baseline zero-slot overall >=25%且>=2 tasks各>=20%；candidate 1+15/16、zero omission；median occupied-cell coverage retention >=0.85；dual scientific payload byte identity、Torch RNG isolation、credential/write/accounting PASS。
- Boundary：只允许新增 dedicated script/test；large JSON只写 owned Run030 root。当前 core/config/GPU/API/model/LIBERO/reservation/Dev/validation/formal授权均0；PASS只授权implementation protocol。

#### AX. run_030 allocation reconstruction PASS

- Order/tests：protocol/implementation `96c43db` / `dee49eb`，顺序正确。Analyzer TDD先修复standalone repo import和importlib dataclass registration；二者发生在aggregate input前且不改science。Dedicated + production QD `26 passed`，py_compile PASS。
- Inputs/validity：5/5 exact files、419 rows checksum/row-count PASS；3,771 possible transitions中3,205 unique-max eligible，566 equal-max按协议排除；覆盖10 tasks。Production allocator baseline 3,205/3,205 exact slot-map identity。
- Observation：prior global-best cell baseline zero slots `2151/3205 = 0.6711388455538222`；task ratios全部越过门，范围约0.5356–0.8556。该值是allocation defect，不是success estimate。
- Counterfactual：每 transition dedicated anchor=1、sparse=15、total=16；global-best zero slot 0/3,205；occupied-cell coverage retention median 1.0；Torch global RNG unchanged；9/9 gates PASS。
- Artifacts：canonical/replay byte-identical、mode0444、6,101,386 bytes、file SHA `cede7bbb823621e5ac21a3b5eb10c7ceb6e4acdf967d63ab5fb61135f472d812`、payload `7f793a70…c880`、credential 0；只写 owned Run030 root。
- Target/accounting：historical formal best/gap仍 `2/10 / 3`；新增 GPU/API/model/LIBERO/reservation/online/formal均0。Decision `KEEP_H4_V3_DIAGNOSTIC_PASS_AND_AUTHORIZE_IMPLEMENTATION_PROTOCOL_ONLY`；下一步必须先提交 algorithm iteration 3 implementation protocol。

#### AY. run_031 algorithm iteration 3 implementation protocol

- Trigger/order：Run030 result独立提交 `dc3d955` 后才冻结本protocol；在本protocol commit前不允许 core/config/test change。
- Single change：`qd_global_quality_anchor_count=1` 时先按既有reward/fingerprint/cell规则取global best dedicated parent，再以相同seed tuple运行原allocator的15-slot sparse allocation；不去重，16个parent全部renoise/rollout。
- Default/fail closed：默认/显式0保持旧allocation科学输出；仅允许0/1，1只在grid archive + sparse priority合法；bool不作为int静默接受。v2 fallback保持关闭。
- Telemetry：单独记录dedicated cell/fingerprint/count、sparse/total slot maps、activation/rescue和两种QD offspring source；不得复用旧EDS generic anchor字段。
- Gates：anchor0 identity；global-best tie order；candidate 1+15与独立population15 exact equality；omission rescue/no dedup；determinism/global RNG；integrated finite/mask/qpos/archive/final selection；完整chunk `176/176/11`；全量QD/RDT回归。
- Scope/accounting：只允许3 core + config + 2 tests；GPU/API/model/LIBERO/reservation/online/formal均0。PASS只授权另立CPU integrated mechanism protocol；历史formal best/gap仍2/10、3。

#### AZ. run_031 implementation PASS

- Order/scope：protocol `4dc55c5` -> implementation `f453e64`；变更精确限制为3 core + config + 2 tests，受保护未跟踪方案未读、未改、未stage。
- TDD/tests：red phase 11个missing-feature预期失败；focused 11 passed；QD+RDT+metrics full regression 414 passed；py_compile/diff/whitelist/credential checks PASS。
- Semantics：默认/显式0保留旧allocation tensors/order/counts/weights/fingerprints/RNG；显式1按既有global-best顺序prepend dedicated parent，其余与same-seed population15 sparse allocation逐tensor一致。
- Mechanism：sparse omission时total补为1；sparse已选择best cell时不去重，total=sparse+1。10 iterations每轮16 parents全部进入rollout；source/activation/cell/fingerprint/sparse/rescue telemetry完整。
- Safety/accounting：fail-closed mode/sampling/bounds/fallback validation、finite/mask/qpos/archive/final global-best regression PASS；complete chunk仍176 search/176 QD/11 calls。
- Target：这是实现门，不是success evidence。新增GPU/API/model/LIBERO/reservation/online/formal均0；历史best/gap 2/10、3。Decision `KEEP_H4_V3_IMPLEMENTATION_PASS_AND_AUTHORIZE_CPU_MECHANISM_PROTOCOL_ONLY`。

#### BA. run_032 CPU integrated mechanism protocol

- Order：Run031 protocol/implementation/result `4dc55c5 -> f453e64 -> fe1a06b` 完成后冻结；artifact只能在新harness implementation commit之后创建。
- Fixtures：candidate_rescue以13/1/1/1 visits让global-best sparse count每轮为0；candidate_overlap以4/4/4/4确保best sparse count>0；legacy fixture只把anchor count改为0。三者均跑真实RDTSteer QD loop十轮。
- Gates：candidate精确10次1+15/16；rescue 10/10，overlap sparse+1且不去重；legacy 16 sparse；三者176/176/11、finite/mask/archive/rebin/final-selection/source/RNG PASS；双suite byte identity。
- Scope/artifact：只允许新增dedicated script/test；canonical/replay仅写owned Run032 analysis，byte-identical、0444、secret-free。core/config/GPU/API/model/LIBERO/reservation/online/formal授权均0。
- Decision：PASS只授权另立six-cell online mechanism protocol与immutable manifest流程；historical formal best/gap仍2/10、3。

#### BB. run_032 CPU mechanism PASS

- Order/tests：protocol `a252ad1` -> harness implementation `83a9715` -> artifacts；TDD初始唯一failure为script尚不存在，随后dedicated 3/3、full QD/RDT/metrics 417/417、py_compile PASS。
- Rescue fixture：10/10 activation、10/10 rescue；每轮pre-update global-best sparse=0、total=1。
- Overlap fixture：10/10 activation、0 rescue；每轮best sparse>0且total=sparse+1，无dedup。Comparator保持anchor/activation/rescue=0和原160 sparse source schema。
- Integrated gates：三case均10个16-parent rollout batches、176 search/176 QD/11 calls；finite/mask/qpos/archive/rebin/final-selection/source/RNG/hash/secret全部PASS。
- Artifacts：canonical/replay byte-identical、0444、11,411 bytes、file SHA `31dd437c…e24b`、payload `f147193e…ddf4`、credential 0，仅位于owned Run032 root。
- Target/accounting：仍非success evidence；新增GPU/API/model/LIBERO/reservation/online/formal均0，historical best/gap仍2/10、3。Decision `KEEP_H4_V3_CPU_MECHANISM_PASS_AND_AUTHORIZE_ONLINE_MECHANISM_PROTOCOL_ONLY`。
