# EDS-QD Stage/Guidance Transition 优化实验设计

日期：`2026-08-10`

状态：`Approved for execution`

> 本文冻结本轮实现、验证和实验范围；不得根据中间结果调整 FSM 阈值、seed、矩阵或追加实验。

## 1. 目标与基线

目标是把现有 VLM 直接决定 stage/guidance 的机制替换为物理证据驱动、可逆且带迟滞的状态机，验证它能否减少“未抓到却关闭 guidance”和“掉落后未恢复 guidance”，并在固定 LIBERO Object-Swap OOD 设置上达到 `>=5/10`。

唯一算法基线：

- `eds_qd_uniform_expand20_p48_k20`：上一轮 valid，`1/10`（task 9）；
- 固定 `population_size=48`、`cem_iters=20`、`num_elites=16`、`use_cem=false`，其余 QD/reward/execution 参数不变。

历史结果只作背景。正式实验对 legacy 与 FSM 各运行两轮完整 10-task evaluation，以同轮 paired 对照和两轮 mean SR 归因。

## 2. Git 与产物隔离

执行获批后，从经重新审计的 `exp/eds-quality-diversity` clean commit 创建：

```text
branch:   exp/eds-qd-stage-guidance-transition
worktree: /home/hynx/VLA-Pilot++/.worktrees/exp/eds-qd-stage-guidance-transition
candidate base at design time: beb8d3f073857f3762a179ce8af4a3c28244b75d
```

正式执行前重新记录 source HEAD/status、base SHA、diff、config/code fingerprint。不得修改或覆盖旧 branch、旧代码和 immutable artifacts。新 worktree 的 `outputs` 必须指向 shared2 独立 namespace：

```text
/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/outputs/stage_guidance_transition_20260810/
```

## 3. 状态机

| FSM state | Legacy stage | Guidance | 转换条件 |
| --- | ---: | --- | --- |
| `ACQUIRE` | 1 | ON | 回合开始或抓取未成功 |
| `GRASP_VERIFY` | 1 | ON | 已执行 close，但尚未确认抓牢 |
| `TRANSPORT` | 2 | OFF | 持续物理证据确认抓牢 |
| `RELEASE_VERIFY` | 2 | OFF | 在目标区域主动释放，等待成功确认 |
| `RECOVERY` | 1 | ON | 抓取失效、非预期掉落或错误释放 |
| `DONE` | 0 | OFF | 环境确认 success，终态不可回退 |

固定循环：

```text
ACQUIRE/ON -> GRASP_VERIFY/ON -> TRANSPORT/OFF
TRANSPORT/OFF -> RECOVERY/ON -> GRASP_VERIFY/ON -> TRANSPORT/OFF
TRANSPORT/OFF -> RELEASE_VERIFY/OFF -> DONE 或 RECOVERY/ON
```

`current_stage` 和 `use_guidance` 必须由 FSM state 唯一派生，禁止独立写入。VLM 保持上一轮查询设置用于 shadow/advisory 日志，但其响应、超时或解析失败不得改变 FSM、guidance 或 action；失败时保持当前状态。

## 4. 物理判据与迟滞

判定在每次 `adapter.step()` 后执行，使用已执行夹爪命令、实际 gripper qpos、EEF pose 和目标物体跟踪位姿。状态变化时立即废弃 action chunk 剩余动作、重置 stage/QD chunk memory 并重新规划。

### 4.1 抓牢

close 只产生 `GRASP_VERIFY` 候选；同时满足下列条件并持续 `4` steps 才进入 `TRANSPORT`：

```text
已执行 close
AND 实际夹爪处于闭合/夹持区间
AND object–EEF 距离处于 near threshold
AND 物体相对 EEF 位姿稳定
AND 物体相对 pre-close 高度上升 >= 0.02 m
```

建议初始阈值：near `0.08 m`、4-step 随动误差 `<=0.02 m`；正式执行前必须通过历史轨迹/确定性 probe 校验量纲，任何调整须在首个 episode 前冻结。

### 4.2 掉落与抓取失效

`TRANSPORT` 中持续 `3` steps 出现任一证据则进入 `RECOVERY`：

- object–EEF 相对位姿漂移 `>=0.05 m`；
- 物体与 EEF 不再随动且物体下降 `>=0.02 m`；
- 夹爪实际张开，但不满足目标区域主动释放条件。

确认阈值严于失效阈值，并设置最小 state dwell `2` steps，防止 ON/OFF 抖动。单帧异常、QD reward 阈值或 VLM 判断不得单独触发转换。

### 4.3 放置

只有“已执行 open 且物体位于预注册 destination region”才能进入 `RELEASE_VERIFY`。环境 success 为真则进入 `DONE`；否则在 `8` steps 内出现区域外下落或验证超时，进入 `RECOVERY`。destination resolver 必须来自固定 task/keypoint metadata，禁止运行时由 VLM 猜测。

## 5. Signal 边界

- **本轮 formal：** 使用当前栈已经依赖的 simulator-backed object/keypoint pose、EEF pose 和 gripper qpos；不新增 MuJoCo contact、privileged task predicate selection 或 future observation。
- **Oracle observer：** MuJoCo contact/ground-truth attachment 只允许 shadow 记录和审计，不能驱动正式 action/state。
- **可部署版本：** 应以 RGB-D object tracking、robot proprioception 和 executed command 替换 simulator object pose；不在本轮新增实验 job，也不得把本轮结果表述为 real-world deployable evidence。

## 6. TDD 与实验矩阵

先实现 config-controlled `legacy_vlm` 与 `physical_fsm_v1` 两条路径。最小测试覆盖：抓空不关 guidance、稳定抓牢 ON->OFF、瞬时抖动不切换、掉落 OFF->ON、重新抓牢 ON->OFF、目标内/外释放、VLM error hold-state、DONE 不回退、stage change 立即废弃旧 chunk，以及 legacy 路径回归。

通过目标测试、相关回归、`py_compile`、`git diff --check` 后，冻结以下 4-job matrix；不增加其他 QD family、参数 sweep、held-out 或 formal 配置：

| Round | Transition | Job label |
| ---: | --- | --- |
| 0 | legacy | `eds_qd_uniform_expand20_p48_k20_transition_legacy_r0` |
| 0 | FSM | `eds_qd_uniform_expand20_p48_k20_transition_fsm_v1_r0` |
| 1 | legacy | `eds_qd_uniform_expand20_p48_k20_transition_legacy_r1` |
| 1 | FSM | `eds_qd_uniform_expand20_p48_k20_transition_fsm_v1_r1` |

每 job 运行 tasks `0..9` 各 1 episode，即每种 transition 有 20 episodes、两轮 SR，共 `4 × 10 = 40 formal episodes`。不运行 episode-consuming preflight；same-config retry 最多 4 次，因此 attempt cap 固定为 `44`。

## 7. 固定评估与 gates

沿用上一轮：

```text
suite: libero_object_swap strict perturbation
tasks: 0..9
round 0 episode seeds: [44, 235, 43, 546, 6, 621, 197, 87, 151, 548]
round 1 episode seeds: [1044, 1235, 1043, 1546, 1006, 1621, 1197, 1087, 1151, 1548]
round root seeds: [0, 1]
max steps: 720
render/video: ON
per-round task gate: success_count >= 5/10
mean task gate: total success_count >= 10/20
GPU: 只使用 0..7 中通过 admission 的实时空闲设备
```

round 1 seeds 由 round 0 seeds 逐项加 `1000` 得到，必须在执行 manifest 中冻结。legacy/FSM 在同一 round 使用完全相同的 task-seed mapping。

Validity/safety 继续要求 10/10 唯一 task records、完整视频/metrics/trace/fingerprint，且 0 nonfinite、0 action-mask violation、0 QD fallback、0 qpos/execution error、credential/storage/GPU audit PASS。

FSM mechanism gate：

- 0 次未满足 `grasp_confirmed` 即 guidance OFF；
- 0 次 stage/guidance 非法组合；
- 100% transition 有结构化物理证据和 reason；
- VLM shadow response replay 不改变 state/action；
- drop/regrasp 存在时，确认后的 state commit latency `<=1` step；无对应事件则报告 `N/A`，不得伪造通过；
- legacy 与 FSM 均保持 QD `1008 evaluations/full chunk` accounting。

候选 adoption 要求：两轮均 valid，mean SR `>=0.5`、safety/FSM mechanism gates 全部 PASS，且相对同轮 legacy 聚合后的 paired gained tasks 不少于 lost tasks、总成功数不低于 legacy。逐轮 `5/10` 同时报告；若 mean gate 未通过，只报告负结果，不追加实验。

## 8. 日志、审计与停止

新增逐步 FSM trace：state before/after、transition reason、executed gripper command、actual qpos、object/EEF pose、relative drift、follow error、lift/fall、destination distance、确认计数器、guidance、VLM advisory/query status 和 chunk invalidation。

formal 与 retry 共用 append-only ledger；credential 仅由环境变量注入。完成后生成逐 job audit、task-level paired 分析、transition confusion/latency、掉落与 recovery 定性视频分析、只读 decision manifest 和最终报告，并确认无残留 runner/`main.py` 进程。

## 9. 批准决策

1. 唯一 QD family 为 `eds_qd_uniform_expand20_p48_k20`；legacy/FSM 各运行两轮完整 10-task evaluation；
2. 本轮 formal 接受当前 simulator-backed keypoint pose；真实可部署 perception transition 留到后续；
3. prospective branch/worktree、shared2 namespace 和 `40+4=44` attempt cap 已批准；
4. GPU 只从 `0..7` 中通过实时 admission 的空闲设备选择，不干扰或共置外部 compute；
5. 初始几何阈值仅允许在首个 episode 前通过非 episode 的量纲检查确认，随后写入 manifest 冻结。
