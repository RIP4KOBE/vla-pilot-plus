# EDS-QD Autoresearch v2：Reward-Degenerate QD Quality / Selection 实验设计

日期：`2026-08-12`

状态：`APPROVED / EXECUTING — protocol-first redesign`

授权来源：用户于 `2026-08-12` 明确要求继续 autoresearch。该授权满足上一周期结论中“versioned redesign + 新 holdout + 新预算 + 用户批准”的恢复条件。

继承方案：`docs/01_specs/2026-08-08-eds-qd-autoresearch-libero-swap-ood-design.md`

唯一目标：把 EDS-QD 在 LIBERO-PRO `libero_object_swap` 冻结正式 10-task 评估上的有效成功率提升到 `>=5/10`。每个 promotion 判断都以缩小该 target gap 为第一排序，不为机制新颖性或无休止探索延长研究。

## 1. 上一周期为什么停止、现在为什么可以恢复

上一周期的 causal-envelope candidate 在 validation 只得到 `1/10`，低于 `>=5/10`，所以 protocol v11 强制 `no formal`；同一 validation seeds 已揭示，不能在修改候选后复用。cycle-2 因此正确停止，而不是因为 GPU、密钥、实现或用户中断。

本设计建立独立 v2 cycle：旧 validation 仅作 `HISTORICAL-REVEALED` 诊断证据；所有 promotion 使用新的 Dev-A、Dev-B 和 validation seeds。旧 formal tasks/seeds 尚未在本研究运行，继续保留为最多一次、candidate freeze 后的 reuse-limited acceptance set。

## 2. 冻结范围与单一根假设

本周期只研究 H2：QD quality、cell replacement、archive search 与 archive-to-execution selection。H1 causal envelope 可作为已验证的 partition substrate 保留，但本周期唯一新增算法机制必须是 H2；不修改 checkpoint、prompt、perception、Stage recognizer、environment、executor 或 evaluator。

只读代码和 raw trace 已给出一个可证伪缺口：

1. `core/qd_ed.py` 每 cell 只按 reward/fingerprint replacement，最终按全局 reward/fingerprint 选执行 elite；
2. 冻结 runtime cache 的 `stage2_guidance` 明确返回常数 `0`，并注明 placement 由 policy 完成；
3. QD 路径在 reward 全相等时仍创建、更新、采样 archive；所有 quality 比较退化为 fingerprint 字典序；
4. 因此 placement 阶段的执行 action 不是由 task quality 或原 policy 选择，而由与任务无关的 hash tie-break 选择。

根假设 H2-v2：

> 当当前 chunk 的 QD quality 完全退化时，禁用该 chunk 的 QD archive ecology，并回退到同预算 EDS control selection，可避免 fingerprint 接管无 guidance placement，同时保留非退化 chunk 的 causal-envelope QD 搜索；这将恢复 control completion 能力并保留 QD 在 guided grasp 阶段的增益。

这不是 Stage 算法修改。Stage 与 guidance source 保持冻结；算法只根据 EDS 已计算的当前 candidate rewards 判断 QD 是否存在可排序的 quality。

## 3. 候选机制边界

唯一允许候选名：`reward_degenerate_control_fallback_v1`。

候选语义在 zero-episode calibration PASS 后才可实现：

- 在 initial population 已完成正常 reward scoring 后检测 exact degeneracy；不增加 model、reward 或 VLM call；
- exact degeneracy 定义为有限 reward tensor 中所有值逐位相等，不引入调参阈值；
- degenerate chunk 不建立 QD archive，沿现有 non-QD EDS control branch 完成相同 `16 + 10*16 = 176` evaluations；
- nondegenerate chunk 继续使用 `sparse_priority + causal_envelope_v1`，行为必须 byte-for-byte / fixed-input regression 等价；
- fallback 必须记录 reason、reward value、count、selected source、evaluation count 与 score-call count；
- legacy `qd_archive_mode=none`、旧 `grid_archive` 和 causal-envelope v1 均保持 config-controlled backward compatibility；
- fail closed：nonfinite、empty population、accounting mismatch 或 selection mismatch 不能伪装为 fallback。

禁止在本周期同时加入 endpoint weighting、gripper heuristic、Stage-specific threshold、cross-chunk memory、compute scaling 或新的 parent allocation。若 exact-degenerate guard 不足，当前单候选周期结论为不采纳，而不是在已揭示 split 上堆叠第二机制。

## 4. 零-episode calibration：run_020

在任何核心实现前，`run_020_quality_selection_calibration` 只读分析：

- 当前 owned root 的 run_010 mechanism/Dev-A/Dev-B/validation raw `eds_metrics.jsonl`、`stage_events.jsonl`、`mechanism_trace.pt`、`qd_archive_timeline.json`；
- 历史 EDS-QD baseline/budget raw metrics 与冻结报告；
- 当前 core QD update/selection 与 runtime cached guidance source；
- MAP-Elites/QD 一手文献只用于确认“cell elite 必须由有意义的 quality 比较产生”的算法语义，不替代本地证据。

Calibration PASS 必须同时满足：

1. cached Stage-2 guidance 的常数零语义和 SHA-256 被记录；
2. 至少 `20` 个、覆盖至少 `5` 个 task 的 valid QD chunks 存在 exact-degenerate reward；
3. replay 证明当前 degenerate winner 会随 fingerprint/tie ordering 改变，且没有 task-quality 区分；
4. proposed fallback 可完全复用现有 non-QD control path，预计 complete-chunk evaluations 仍为 `176`、score calls 仍为 `11`；
5. 非退化 stream 的 archive/update/selected fingerprint 在 observer replay 中完全不变；
6. 没有 privileged evaluator、future observation、success label 或 formal result 进入在线决策。

任一失败则 `CONCLUDE_H2_OFFLINE_NOT_JUSTIFIED`，新增在线 episode 为 0。

## 5. 新 evaluation isolation

Seed 生成规则冻结为：

```text
seed = int.from_bytes(
  SHA256("eds-qd-autoresearch-v2|<split>|task=<task>")[:8], "big"
) mod 1_000_000
```

### Dev-A

Tasks `[0,1,2,4,6,7]`，seeds：

```text
[800391, 520957, 146970, 28448, 354436, 197646]
```

### Dev-B

Tasks `[0,1,2,4,6,7]`，seeds：

```text
[535679, 62876, 831264, 171158, 322701, 726499]
```

### Validation

Tasks `[0,1,2,3,4,5,6,7,8,9]`，seeds：

```text
[721508, 998896, 286646, 83688, 350257,
 399156, 52579, 878578, 116024, 323195]
```

上述 seeds 与 v1 Dev-A、Dev-B、validation 及 formal seeds 不重叠。新 validation 一旦揭示不能复用。

Formal 仍为 tasks `0..9`、seeds `[44,235,43,546,6,621,197,87,151,548]`，只能在新 validation PASS、候选及所有 hashes 冻结后另立 protocol，且最多运行一次 candidate/control paired acceptance。

## 6. Task-first promotion gates

所有在线层均 paired contemporaneous control/candidate，control 保持原 `p2_stage_on_abs_rbf_control`，candidate 只增加 H2-v2 guard。

1. Mechanism preflight（6 episodes）：只验证 fallback 在 degenerate chunks 被触发、非退化 chunks 不误触发、176/11 accounting、safety、latency 与 artifact gates；不以短 episode success promotion。
2. Dev-A（12 episodes）：candidate `>=3/6`，candidate 至少比 control 多 1 个 success，`gained >= lost`，且所有 hard gates PASS；否则停止。
3. Dev-B（12 episodes）：独立满足 candidate `>=3/6`、比 control多至少 1、`gained >= lost`；Dev-A+B pooled 至少 4 个 candidate successes，且净 gains 为正；否则停止。
4. Validation（20 episodes）：candidate `>=5/10`、不低于 control、`gained >= lost`，全部 validity/safety/compute/artifact/credential gates PASS；否则 `no formal` 并结束本周期。
5. Formal（20 episodes）：candidate `>=5/10`、不低于 control、`gained >= lost`，全部硬门 PASS；PASS 后立即冻结、报告和停止优化。

Task success 永远高于 degenerate fallback ratio、reward、coverage、overflow 或 latency proxy。每轮必须写 task-level successes、gains/losses、失败边界、距 5/10 gap 及下一步依据。

## 7. 预算

v1 已使用 42 effective episodes、54 reservations、`2.9347668/48` device-wall GPU-hours。原全局上限 `143` reservations 和 `48` GPU-hours不变。

v2 最多新增：

| 层 | 新 reservations |
| --- | ---: |
| mechanism preflight | 6 |
| Dev-A | 12 |
| Dev-B | 12 |
| validation | 20 |
| formal | 20 |
| 合计 scientific cells | 70 |

执行全部层后 global reservations 最多 `124`，仍保留 `19` 个只用于已审计 same-cell infrastructure recovery。不得把 recovery reserve 转换成新候选/sweep。GPU 总上限仍为 `48` 小时；任一更早 stop gate 立即节省后续预算。

GPU 0–7 只能使用 fresh admission 通过且无外部 compute process 的设备；不共卡、不抢占、不终止外部进程。常规资源等待不授权改变协议。

## 8. Git、artifact 与中断协议

- 所有 code/docs/tests/manifest 只写当前 worktree 和 branch；大型产物只写既有 owned artifact root 下的 `run_020_*` / 后续 versioned run root；
- 其他 worktree、workspace 和 shared2 历史目录全部只读；
- 受保护的未跟踪文件 `docs/01_specs/2026-08-10-eds-qd-stage-guidance-transition-design.md` 不得读取、修改、stage 或 commit；
- 每个 algorithm iteration 必须 `protocol commit -> implementation commit -> immutable manifest -> result commit -> reflection`；
- 所有轮次共同追加 `docs/03_evidence/eds_qd_autoresearch/iteration-ledger.md`；
- 用户可随时暂停；检测 `.autoresearch/PAUSE` 或收到用户暂停消息后停止新 reservation，保全现有 owned process/artifact/state；
- 用户提供的 credential 仅允许进程内临时环境使用，绝不写入 Git、日志、manifest、命令记录或可逆 fingerprint。

## 9. 停止规则

- Formal PASS：立即成功结束，不继续探索。
- 任一 promotion FAIL：停止后续 split，记录 no-adoption；不在同一已揭示 split 调参重试。
- 三次连续无 target-linked progress、预算触顶、validity/safety/credential/write-boundary 失败：outer-loop CONCLUDE。
- 本设计只有一个 H2 候选；不允许以“还可以再试一个阈值”为理由延长周期。
