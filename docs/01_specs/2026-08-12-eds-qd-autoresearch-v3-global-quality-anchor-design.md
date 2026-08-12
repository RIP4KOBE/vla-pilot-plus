# EDS-QD Autoresearch v3：Global-Quality Parent Anchor 实验设计

日期：`2026-08-12`

状态：`APPROVED / EXECUTING — protocol-first versioned successor`

授权来源：用户在 v2 结论及其 versioned-redesign 边界后明确回复“批准”，授权创建并执行新版方案、新 leakage-safe holdout 与显式剩余预算。

父状态：commit `99825fd`；v2 decision `CONCLUDE_NO_ADOPTION_WITHIN_V2_CYCLE_REQUEST_VERSIONED_REDESIGN`；v2 immutable decision manifest SHA-256 `4010b620976ee8aa26ee05e6655a60c6ec4bc194511698254e9b2eb0bf9f1334`。

唯一首要目标：将 EDS-QD 在 LIBERO-PRO `libero_object_swap` 正式评估上的有效成功率提升到 `>=5/10`。一旦候选通过 formal 全部硬门，立即停止优化并冻结；任一 promotion FAIL 立即停止后续 split，不在已揭示数据上追加相邻机制。

## 1. 证据驱动的方向选择

v1 H1 causal envelope 改善了 partition resolution，但 validation 只有 `1/10`。v2 H2 exact-zero fallback 在线 74/74 chunks 未激活，candidate `0/3` 并丢失 control task 9。继续调 exact-zero tolerance、Stage transition 或 descriptor bounds 都是在已反证方向上扩展，不获授权。

当前最直接的 QD 核心缺口来自父分配：QD archive 以 cell 为单位做 quality elitism，但 sparse parent allocation 只按 inverse visitation 分配 16 个后代，没有全局质量保留。对已冻结数据的只读预审计显示：

- Run023 有 666 个可比的 iter-to-iter parent transitions，其中上一轮 global-best reward cell 在下一轮得到 0 slots 的次数为 450，遗漏率 `67.57%`；
- task 2/3/9 的遗漏率分别为 `51.32% / 76.89% / 25.93%`；
- Run010 causal-envelope 数据同样显示高遗漏，而 legacy formal 数据的遗漏明显更低；该差异与 causal rebin 后 sparse visitation ecology 相符；
- `run_000` 已证明现有 QD 路径 4,705 chunks 全部是 archive-only parents，`num_elites` 对 QD 是 no-op；因此这是已由代码和数据共同支持的 retention gap。

这些是 allocation observations，不是 success 因果结论。v3 先做零-episode preregistered reconstruction，再决定是否实现。

## 2. 单一根假设与候选

根假设 `H4-v3`：

> Sparse-QD 在 causal rebin 后经常不给当前全局最高质量 cell 分配任何后代，使最有希望的 reward lineage 被 quality-blind visitation allocation 截断。每轮固定保留一个 global-quality parent slot，并把其余 15 slots 交给原 sparse-QD，可在 `176 evaluations / 11 score calls` 不变的条件下恢复 exploit/retain 能力，同时保留大部分 QD cell exploration，从而提升 task success 并不丢失 contemporaneous control successes。

唯一候选：`qd_global_quality_anchor_v1`，algorithm iteration 3。

冻结语义：

1. 仅在 `qd_archive_mode=grid_archive` 且显式 `qd_global_quality_anchor_count=1` 时生效；默认 0 完全保持旧行为。
2. 每个 CEM/QD iteration 在 parent allocation 前，按既有 `(reward desc, fingerprint asc, cell asc)` 选择 archive global-best cell。
3. 一个 parent slot 确定性使用该 cell 的 elite action；其余 15 slots 使用现有 `sparse_priority` largest-remainder allocation，seed、visitation weights 与 causal-envelope semantics 不变。
4. 16 个 parents 均走原 renoise/rollout；这是 parent-lineage anchor，不是未经评估的 action carryover。
5. 允许 sparse allocation 额外选择 global-best cell；telemetry 必须区分 dedicated anchor 与 sparse slots。
6. Archive update、cell replacement、causal envelope、最终 global-reward selection、checkpoint、Stage、prompt、environment、executor、evaluator全部不变。
7. v2 `control_v1` exact-degenerate fallback 必须关闭，不叠加失败机制。
8. Complete chunk 必须仍为 `176 search evaluations / 176 QD evaluations / 11 score calls`，不增加 model/reward/VLM calls。

禁止第二个 anchor count、reserve ratio、reward threshold、tolerance sweep、control/QD 混合比例、Stage gating 或 final-selection heuristic。本周期只有一个候选。

## 3. run_030 零-episode allocation reconstruction

实现任何 core/config 变更前，`run_030_global_quality_anchor_diagnostic` 只读审计 owned Run010/Run023 与历史 baseline traces/metrics，并冻结全部输入 checksum。

Confirmatory PASS 必须同时满足：

1. 至少 300 个有效 iter-to-iter transitions，覆盖至少 3 个 tasks；
2. 当前 causal-envelope sparse-QD 的 prior global-best cell 零 slot 比例至少 25%，且至少两个 task 各自达到 20%；
3. `anchor_count=0` reconstruction 与保存的 16-slot allocation 逐 transition 完全一致；
4. `anchor_count=1` 在每个 transition 精确生成 1 dedicated anchor + 15 sparse slots、总数 16，并将 global-best cell 零 slot降为 0；
5. candidate occupied-cell coverage 相对原 allocation 的 transition-median retention `>=0.85`，不存在 nonfinite、negative count、RNG global-state mutation 或 accounting error；
6. global-best selection只使用当轮已存在 archive reward/fingerprint/cell，不使用 future observation、episode success、evaluator state、task identity或 holdout outcome。

任一失败：`CONCLUDE_H4_V3_OFFLINE_NOT_JUSTIFIED`，新增在线 episodes 为 0。PASS 只授权新的 implementation protocol，不等于 task 提升。

## 4. 实现、TDD 与离线机制门

run_030 PASS 后必须先提交单独 implementation protocol。允许修改范围仅为：

- `core/qd_ed.py`
- `core/rdt_policy_steer.py`
- `core/eds_eval_metrics.py`
- `configs/config.yaml`
- 对应 QD/RDT tests

实现 hard gates：default/anchor=0 fixed-input bit identity；anchor=1 deterministic global-best selection；1+15 allocation；176/176/11 accounting；全 finite/mask/qpos/archive monotonicity；final selection unchanged；RNG isolation；candidate telemetry 完整。实现 commit 后必须另立 CPU integrated mechanism protocol和 immutable artifact；该层 PASS 才可另立 online manifest/protocol。

## 5. 新 evaluation isolation

Seed 冻结规则：

```text
seed = int.from_bytes(
  SHA256("eds-qd-autoresearch-v3|<split>|task=<task>")[:8], "big"
) mod 1_000_000
```

这些 seeds 与 v1/v2 Dev、validation、mechanism 及 formal seeds 均不重叠。

### Online mechanism

Tasks `[3,8,9]`，seeds `[955865,522754,845886]`，control/candidate 共 6 cells。用途是验证真实 archive 中 anchor 激活、rescue、1+15、176/176/11、safety、latency和 artifact；success 记录但不单独构成正向 promotion。若 candidate 丢失任一 contemporaneous control-success task，则立即 FAIL。

### Dev-A

Tasks `[0,1,2,4,6,7]`，seeds `[307995,262892,731741,14859,648306,960581]`，paired control/candidate 共 12 cells。

PASS：candidate `>=3/6`、至少比 control 多 1 success、lost control-success tasks 为 0、全部硬门 PASS。否则停止。

### Validation

Tasks `0..9`，seeds `[733557,563986,984766,598490,834409,827884,504577,82408,891085,7487]`，paired 20 cells。

PASS：candidate `>=5/10`、candidate 不低于 control、lost control-success tasks 为 0、全部硬门 PASS。Validation 一经揭示不可复用；FAIL 则 no formal并结束周期。

### Formal

沿用 reuse-limited acceptance tasks `0..9`、seeds `[44,235,43,546,6,621,197,87,151,548]`，只在 validation PASS、候选和所有 hashes 冻结后另立 protocol，最多 paired 20 cells。

PASS：candidate `>=5/10`、不低于 control、lost control-success tasks 为 0、全部 validity/safety/compute/artifact/credential gates PASS。PASS 后立即冻结并停止。

Control 始终为 `p2_stage_on_abs_rbf_control`。Candidate 是 sparse causal-envelope QD + 本设计唯一 global-quality anchor；不携带 v2 fallback。

## 6. 显式剩余预算

进入 v3 前已使用：48 effective online episodes、66 global reservations、`3.7471009444444445` GPU-hours、formal 0。全局上限仍为 143 reservations 和 48 GPU-hours。

| 层 | 新 scientific cells |
| --- | ---: |
| Online mechanism | 6 |
| Dev-A | 12 |
| Validation | 20 |
| Formal | 20 |
| 合计 | 58 |

若全部执行，global reservations 为 `124/143`，保留 19 个只用于审计后的 exact-cell infrastructure recovery；不得转换为 sweep或第二候选。任一早停立即节省剩余预算。GPU admission仍限 0–7 空闲设备，一卡一 worker，不共享、不抢占、不终止外部进程。

## 7. Promotion、target gap 与 no-progress

每轮第一排序必须写 task-level success、gained/lost tasks、candidate-control delta、距 `5/10` gap、失败原因和下一步依据。Reward、anchor rescue、coverage、latency等只用于归因，不能覆盖 success gate。

连续层级规则：run_030 -> implementation/offline mechanism -> online mechanism -> Dev-A -> validation -> formal。不得越级。任一 valid scientific FAIL 结束本周期；infrastructure recovery只能 same-cell、append-only、protocol-first，不得改变 science。

`H1 validation FAIL`、`H2 online FAIL` 已构成两轮未缩小 formal gap的历史；若 H4-v3 在 online mechanism 或 Dev-A 未产生 target-linked progress，则直接 `CONCLUDE_NO_ADOPTION`，不生成第四候选。Validation/Formal 的 `>=5/10` 是唯一成功终点。

## 8. Git、write boundary、credential 与中断

- 严格 `design/protocol commit -> implementation commit -> immutable manifest -> result commit -> reflection`；protocol不得与结果同 commit。
- 所有代码/文档只写当前 worktree/branch；大型产物只写 owned root下的新 `run_030_*` 及后续 run root；其他 workspace/worktree/shared2历史目录只读。
- 统一追加 `docs/03_evidence/eds_qd_autoresearch/iteration-ledger.md`。
- 受保护未跟踪文件 `docs/01_specs/2026-08-10-eds-qd-stage-guidance-transition-design.md` 不得读取、修改、stage或commit。
- Credential只允许用户已授权的 child-process runtime environment注入；不得进入 command line、文件、artifact、log、manifest、fingerprint或Git；每轮运行前 real health，运行后 exact-value和严格token扫描。
- 用户可随时暂停；暂停后不新增 reservation，先保全 owned process、ledger、artifact与state。

