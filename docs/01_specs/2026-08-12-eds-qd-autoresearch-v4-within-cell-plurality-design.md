# EDS-QD Autoresearch v4：Within-Cell Quality Plurality 实验设计

日期：`2026-08-12`

状态：`APPROVED / EXECUTING — protocol-first versioned successor`

授权来源：用户在 v3 结论后明确要求“继续任务”，并要求自主持续闭环迭代，不把单个 versioned cycle 的结束误作整个研究目标的结束。

父状态：commit `01a8da96dca89ce07728a458f60f09ebfc9ae325`；v3 decision `CONCLUDE_NO_ADOPTION_WITHIN_V3_CYCLE_TARGET_NOT_MET`；v3 immutable decision manifest SHA-256 `5363af6996404c573f989c6c729d64a0f2c89a48a365e1e271b508654cec75a8`。

唯一首要目标：将 EDS-QD 在 LIBERO-PRO `libero_object_swap` 正式评估上的有效成功率提升到 `>=5/10`。每层先报告 task success、candidate-control delta、gained/lost tasks 与 target gap；QD proxy 只用于机制归因。正式达标立即停止并冻结。

## 1. v3 后的证据收敛

v1 causal envelope 改善 partition resolution 但 validation 仅 `1/10`；v2 exact-degenerate fallback 在线未激活且丢失 control task 9；v3 global-quality anchor 修复了 `67.11%` 的 global-best parent omission，在 Run033 获得 task 9，但 frozen Dev-A 为 `0/6 -> 0/6`。因此不再调整 bounds、fallback tolerance、anchor count、search budget、Stage transition 或 Direction-RBF。

只读预审计进一步排除了简单 reward/endpoint-progress selector：在 352 个历史 episodes 上，early reward、target distance、progress、progress efficiency 的成功排序 AUC 均约为随机；max reward 的 AUC 也只有 `0.3153`。历史 Direction-RBF 最佳只到 `3/10` 且丢失 control tasks 3/5/7，说明直接放大全局方向探索风险过高。

当前最直接的 QD 核心缺口是 capacity-one aliasing。对 owned、非 stale、可重放的 QD traces 做只读预审计：

- 24 条 active-QD traces、264 个 candidate streams、4,224 个候选有效；
- 2,750/4,224=`65.1042%` 候选位于包含至少两个候选的同一 endpoint-XY cell；
- 1,019 个碰撞 cell 中，quality winner 与最远同 cell 候选的归一化 direction/shape distance 中位数为 `0.4642 / 0.3228`；
- 即使只取同 cell reward 前两名，其 direction/shape distance 中位数仍为 `0.3617 / 0.2501`，reward gap 中位数仅 `0.01270`；
- 当前 `4x4 target-relative endpoint XY + capacity=1` 因而会丢弃大量“终点相近、reward 接近、接近轨迹不同”的候选。该观察支持 behavior retention 缺口，但不是 success 因果结论。

## 2. 单一根假设与候选

根假设 `H5-v4`：

> Endpoint-XY cell 的单 elite 容量把 reward 接近但轨迹形状不同的操作模式过早合并，阻断可能成为 grasp/transport stepping stone 的 lineage。每个 XY cell 保留 reward 排名前二的唯一 elite，并在不改变 16-parent、176-evaluation 预算的前提下让 sparse allocation 确定性轮换两个 lineage，同时继续保留 v3 的一个 global-quality anchor，可提高有效行为保留并转化为 task success。

唯一候选：`qd_within_cell_top2_v1`，algorithm iteration 4。

冻结语义：

1. 沿用 `sparse_priority + causal_envelope_v1 + qd_global_quality_anchor_count=1`；v2 fallback 关闭。
2. 显式 `qd_cell_capacity=2` 时，每个 XY cell 最多保留两个 fingerprint 唯一的 elite，严格按 `(reward desc, fingerprint asc)` 排序；默认 capacity 1 必须保持旧行为。
3. Archive update 只使用当轮及历史已见 action/reward/descriptor；不读取 future observation、success、task identity 或 evaluator state。
4. Rebin 合并后每个新 cell 仍保留全体来源 elite 的前两名；累计 XY-cell visits 总和必须守恒。
5. Dedicated global-quality slot 始终选择全 archive reward 第一名；其余 15 个 sparse slots 的 XY-cell counts 与 v3 allocator 相同。
6. 同一 XY cell 的 sparse slots 在其两个 elite 间按 stateless seed tuple `(episode, global_step, iter_idx, cell)` 确定起点并 round-robin；不得修改 global RNG。跨 iteration 必须实际激活 secondary lineage。
7. 两个 elite 都经过原 renoise/rollout；final execution 仍从整个 archive 按 `(reward desc, fingerprint asc, cell asc, slot asc)` 取全局第一名，因此不牺牲已保存的 quality best。
8. Complete chunk 保持 `176 search evaluations / 176 QD evaluations / 11 score calls`；population、rollout、reward/VLM/model call 数不变。
9. 新 telemetry 必须分别记录 quality/secondary insert、replace、reject、secondary parent activation、每 cell capacity、rebin collision 与 final slot。

禁止 capacity sweep、shape-distance threshold、reward tolerance、第三 elite、RBF/Stage/guidance/final-selector联动或追加 candidate。本周期只验证上述一个机制。

## 3. Run040 零-episode aliasing reconstruction

实现 core/config 前先提交并执行 `run_040_within_cell_aliasing_diagnostic`。输入只读绑定 owned QD trace/checksum，输出只写新 Run040 artifact root。

Confirmatory PASS 必须同时满足：

1. 至少 200 个 candidate streams、3,000 个候选与 500 个碰撞 cells；
2. 碰撞候选占比 `>=0.40`；
3. 同 cell reward 前两名的 direction 与 shape distance 中位数分别 `>=0.20 / >=0.15`；
4. reward 前两名 gap 中位数 `<=0.02`；
5. capacity=2 replay 对每个 transition 都保留 capacity=1 quality winner和全局 reward best，单 cell 不超过2、fingerprint不重复、rebin visits守恒；
6. 1+15 parent reconstruction 总数始终16，v3 XY-cell slot counts identity，secondary lineage占 sparse slots 至少20%，XY-cell coverage retention median `>=0.85`，RNG/accounting/finite 全部通过。

任一失败：拒绝 H5-v4，不改算法，立即 outer-loop；PASS 只授权单独 implementation protocol。

## 4. 实现与离线机制门

Run040 PASS 后另立 implementation protocol；允许范围仅为 `core/qd_ed.py`、`core/rdt_policy_steer.py`、`core/eds_eval_metrics.py`、`configs/config.yaml` 与对应 tests。Protocol commit 必须先于实现 commit。

TDD hard gates：capacity1 fixed-input identity；capacity2 top2/update/rebin/tie/fingerprint semantics；global-best identity；1+15 fixed compute；stateless round-robin determinism与global RNG isolation；secondary lineage真实进入 rollout；finite/mask/qpos/archive/final-selection/accounting；完整回归。实现 PASS 后另立 CPU integrated mechanism protocol，CPU PASS 后才可另立 online protocol与 immutable manifest。

## 5. 新 evaluation isolation

Task selection 与 seed 都由 v4 SHA-256 规则预注册，未根据 v3 task outcome挑选：task selection 按 `SHA256("eds-qd-autoresearch-v4|<split>|task-select=<task>")` 排序；seed 为 `SHA256("eds-qd-autoresearch-v4|<split>|task=<task>")` 前8 bytes 对 1,000,000 取模。所有 seeds 与 v1-v3、validation、formal seeds 不重叠。

### Online mechanism

Task selection 前两名 `[6,3]`，seeds `[954758,73621]`；paired control/candidate 共4 cells。PASS：candidate 不低于 control、lost control-success tasks为空、QD每record严格 top2/1+15/176/176/11、至少一次 secondary parent activation、safety/latency/artifact/credential gates通过。Success优先报告，但本层不要求绝对成功数。

### Dev-A

排除 mechanism tasks 后 task selection 前三名 `[0,2,1]`，seeds `[680973,206724,451423]`；paired 6 cells。PASS：candidate `>=2/3`、至少比 control多1、lost control-success tasks为空、全部硬门通过；否则本候选停止。

### Validation

Tasks `0..9`，seeds `[928691,104910,68735,757179,77810,597813,487873,96375,151261,603029]`；paired 20 cells。PASS：candidate `>=5/10`、不低于 control、lost control-success tasks为空、全部硬门通过。揭示后不得反馈调参。

### Formal

仅在 Validation PASS 且 candidate/code/config/manifest hashes 冻结后另立 protocol。沿用 reuse-limited acceptance tasks `0..9` 与 seeds `[44,235,43,546,6,621,197,87,151,548]`，paired 20 cells。PASS：candidate `>=5/10`、不低于 control、lost control-success tasks为空及全部 validity/safety/compute/artifact gates通过。通过后立即 `CONCLUDE_SUCCESS`。

Control 固定为 `p2_stage_on_abs_rbf_control`；candidate 仅为冻结的 v4 stack。

## 6. 剩余预算与连续闭环

进入 v4 前：66 effective online episodes、90/143 global reservations、`5.447063166666667/48` GPU-hours、formal 0。最大 scientific cells：mechanism4 + Dev-A6 + validation20 + formal20 = 50；若全部执行则 reservations `140/143`，保留3个 exact-cell infrastructure recovery slots。不得扩展全局 cap或把 recovery slots转换为 sweep。

任一 valid split FAIL 结束的是 v4 candidate，不是自动结束总研究目标。代理必须在同一任务中立即完成 result commit和outer-loop synthesis；若未使用预算仍足以支持一个合法候选、存在新的 task-linked QD证据且未触发 no-progress rule，则直接创建下一 versioned protocol，无需为常规决策再次询问。仅在以下条件之一停止自主闭环：

1. formal candidate 达到 `>=5/10` 并通过全部硬门；
2. 143 reservations、48 GPU-hours或恢复预算使下一合法 promotion chain 无法执行；
3. 连续两个 versioned cycles 未产生任何 task-level gain，且历史/新数据不能支持新的、非重复的 EDS+QD核心假设；
4. 用户明确暂停，或外部权限/credential/受保护流程构成不可自行修复的硬 blocker。

## 7. Git、write boundary、GPU 与 credential

- 严格 `design/protocol commit -> implementation commit -> immutable manifest -> result commit -> reflection`，protocol与实现/结果不得同 commit。
- 所有代码和文档只写当前 worktree/branch；大型产物只写 owned root下的新 Run040+ 目录；其他 workspace、worktree和 shared2 历史路径只读。
- 全过程追加到 `docs/03_evidence/eds_qd_autoresearch/iteration-ledger.md`，同时更新 `research-state.yaml`、`findings.md`、`research-log.md` 和 trajectory。
- 受保护未跟踪文件 `docs/01_specs/2026-08-10-eds-qd-stage-guidance-transition-design.md` 不得读取、修改、stage或commit。
- GPU 0-7 均可在 fresh two-snapshot admission 后使用；一卡一worker，不共享、不抢占、不终止外部进程。
- 用户已授权的 credential 只能注入 child-process runtime environment；不得进入命令行、文件、日志、artifact、manifest、fingerprint或Git；运行前 real health，运行后 exact-value与严格token扫描。
- 用户可随时暂停；收到暂停后不再新增 reservation，先保全 owned process、artifact、ledger与state。
