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
