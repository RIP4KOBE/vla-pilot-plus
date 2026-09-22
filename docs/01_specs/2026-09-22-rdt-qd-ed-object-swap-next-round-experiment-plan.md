# RDT + QD + ED：Object-Swap 下一轮实验方案

版本：v3，2026-09-22。状态：**AUTHORIZED / 用户最新指定 GPU5，继续既定测试与条件迭代**。

初稿的历史状态截点为 2026-09-22 05:03 UTC。用户随后明确授权更新方案、新建 worktree/branch、以 goal 模式测试迭代，并指定 GPU6。执行修订如下；历史快照保留其原时点口径。未调用 Arbor/Orchestra Research skill。

## 最新执行修订：改用 GPU5

用户明确要求“在GPU5上执行任务”，本修订覆盖下文历史GPU6-only设备要求。CUDA与EGL都固定物理GPU5。已停止尚未派发的GPU6等待队列，按GPU5的UUID/PCI/EGL重新验证和冻结运行清单，再执行同一C0恢复诊断。算法、任务、seed/init、Stage、720步/1800秒限制、累计预算和晋级门保持不变。已有GPU6失败证据全部保留；更换设备本身不代表故障已修复。原worktree/branch/artifact名称含gpu6，仅作为历史标识保留。详见 `experiments/iteration_001_execution_intent/gpu5-migration-amendment.md`。

**GPU5首个诊断结果：** 更换GPU仍在第一次模型搜索后的 `mjr_readPixels` 发生同进程Xid31，自动中止耗时132.65秒。下一步为独立的 `GPU5_EGL_SERIAL_C0` 工程诊断：渲染前显式等待CUDA完成并绑定所属EGL上下文，任务/动作/图像设置保持原样；单次运行计入development额度。190项相关CPU测试通过，GPU有效性尚待验证。见 `experiments/iteration_001_execution_intent/gpu5-egl-serialization-diagnostic.md`。

**09:00 UTC诊断更新：** CUDA同步与EGL重新绑定仍未解决GPU5的Xid31；87.52秒后自动中止，0环境动作。5次渲染入口的上下文均正确，故障后保存图像为噪声。下一步仅运行一次600秒上限的资源生命周期观测，检查上下文创建/释放、缓冲区调整及GC时序；不重复失败条件、不计入算法成功率。详见 `experiments/iteration_001_execution_intent/gpu5-render-lifetime-diagnostic.md`。

## 历史执行修订：GPU6 专属运行与原生崩溃诊断

- 新 worktree：`/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z`；新分支：`exp/rdt-qd-ed-gpu6-20260922T063626Z`。按用户指定使用 `.worktree/exp`。
- 分支基于 `46f243873589f37620a40fee4381e12d06113e7b`，继承 N1、运行器修复及原生推理诊断。Goal 已创建；用户中断后工具状态为 paused，当前轮工作及独立等待队列继续，自动后续 goal 轮次需在界面恢复。目标与开发/验证/正式门槛保持本方案规定。
- 固定物理 GPU6（UUID `GPU-e6b7956b-3c69-0c35-dfaf-c860126692c6`），CUDA logical0，EGL index5 需由实测再次确认。仅一个 worker，不切换其他 GPU；用户停止外部任务后直接使用。
- 最新接入时，旧研究已有 5 次派发、2 个无效结果、3 个基础设施中止、0 个有效结果，累计 0.4306699062 GPU-hours。旧 Q0 在 Stage 调用后发生 SIGABRT，不能把它普通重试后替换成成功记录。
- 先做已计账的 CUDA/EGL 检查和单样本无仿真推理诊断；必要时增加有明确假设的引导切换/渲染诊断。未查清并处理崩溃前，不批量启动 30 次机器人任务。
- 原生问题得到证据支持的修复后，冻结共同工程条件，建立显式标记的修复后比较轮（N1R）；沿用原 Dev task/seed/init 映射，C0/Q0/N1 各 10。旧 N1 不完整 cohort 保留，修复后结果独立报告，不回填旧记录。这是所有组共同的工程复测，不把再次运行伪装成基础设施恢复，也不由成功率决定是否重跑。
- 继续使用同一研究的 240 attempts / 48 GPU-hours 累计预算；新 worktree 的账本和锁链接至已有权威账本，避免复制后重置成本。继承的 development 消耗也占 100 上限，因此后续完整矩阵能否运行必须按余额判断；不再保证最多三条开发路线均有名额。
- 原方案中的 any-GPU 规则由 GPU6-only 替代；“待批准”措辞属于初稿语境，不再构成重复询问许可的要求。算法选择仍依照冻结晋级门，验证/正式阶段不提前打开。

首轮耗时暂按 **8–15 小时评测时间**预留，另加尚未确定的崩溃诊断时间。该区间是保守调度估计，并非已测得的有效 episode 均值：当前新条件还没有有效完整运行，单次上限为 30 分钟，30 次的超时额度合计 15 小时。旧 provider 的批量日志跨度不能直接代表现在的单任务进程和 Codex Stage 成本。完成前 2–3 个有效 episode 后，以实际耗时和失败 episode 成本更新 ETA。

**启动诊断实测更新：** GPU6 设备检查及无仿真 B1 推理已通过。完整 C0 诊断发现新动作搜索约 3.9 秒，而环境推进及后续可视化多次各约 21 秒；当前速度不足以在单次 30 分钟内完成 720 步。因此上面的 8–15 小时仅作为修复执行瓶颈后的调度预留，当前没有可靠的整轮完成 ETA；首轮批量评测须在该瓶颈与原生异常完成诊断后启动。详见新 artifact 根目录的 `analysis/first-closed-loop-phase-snapshot.json`。

**内核证据更新：** journalctl 将 GPU6 的 Xid31/109 图形故障精确关联到本次 C0 和先前 Q0 进程；C0 故障发生时尚无 Stage 调用。新增 MuJoCo 分段计时和运行中 Xid 监控，GPU6 空闲后先执行一次明确关联的 C0 恢复诊断，出现新故障立即停止并保存证据。历史两卡分离渲染方案不在当前 GPU6-only 范围内。详见 `experiments/iteration_001_execution_intent/gpu6-kernel-xid-amendment.md`。尚未确定根因或完成修复，30-cell 比较继续暂缓。

## 0. 具体会执行什么：先看这份清单

本方案优化的是固定 RDT 权重下的 QD/ED 推理搜索机制。主要显卡任务是让机器人在 Object-Swap 仿真中完成任务并评测成功率；没有训练、微调或反向传播任务。以下为已授权执行安排；实际完成状态以执行分支记录为准。

### 0.1 三个计数单位

- **任务（task）**：Object-Swap 的 10 个任务，编号 0…9。
- **完整运行（episode / 计划 cell）**：一种算法在一个 task 和一组固定 seed/init 条件下，从初始化执行到成功或达到 720 步上限。启动异常也须单独保留；不能把异常尝试当作已完成的有效 episode。
- **候选动作（candidate）**：RDT/ED 在一次动作选择中生成的动作序列。完整 guided chunk 的 176 个候选在内部评分后选出动作，模拟器只执行选中序列的前 8 步；不会把 176 个候选分别放入模拟器尝试。

所以“第一轮 30 次”是 **10 tasks × 3 种算法 × 每种一次**，不是 30 个不同任务，也不是训练 30 个模型。240 是包含历史消耗与恢复的全研究尝试上限，不是第一轮要跑的次数。

### 0.2 先做的检查：不启动机器人任务

| 编号 | 具体检查 | 使用资源 | 交付和进入下一步的条件 |
| --- | --- | --- | --- |
| T0 | 核对已有结果、代码版本、三组参数、任务/seed/init 清单、剩余预算及调度所有者 | CPU / 文件读取 | 明确哪些计划 cell 已完成、哪些待运行，避免重复派发；冻结共同条件 |
| T1 | N1 的八步夹爪命令比例是否计算正确，包括原始值为零的解码；距离是否有限；边界分桶、最多 16 elites、16 parent slots、chunk/target reset 是否正确 | CPU 小规模单元与回归测试 | 实质语义检查通过；旧 Q0 默认路径保持原行为 |
| T2 | Stage 与 grounding 配置是否独立，实际工厂是否选中正确 provider，mock 搜索循环是否保持 176 candidates / 11 score batches | CPU、mock 模型/provider | 排除已知启动问题和搜索计数错误；这不能替代真实 GPU 推理检查 |
| T3 | 用已保存的候选与 reward 重放 archive 和 parent 选择，比较 Q0/N1 的动作模式保留和空间信息损失 | CPU / 历史 trace | 输出机制差异表，标明 N1 历史 Z 重建的近似性；不据此计算任务成功率 |
| T4 | 读取运行产物，核对成功/失败、视频、任务身份、成本和恢复记录，生成逐任务对照表 | CPU / 运行产物 | 每轮结束后执行，结果与预算可复核 |

已有测试和重放结果先检查其代码、配置与输入身份；身份一致且证据完整时复用，不为本说明重复跑全部历史测试。N2/H 的专属实现测试只在进入对应分支后增加：N2 检查三轴编码及旧路径回归；H 检查 EDS 的 7/8 点评分输入及 VLS/FKD 路径保持不变。

Stage 的真实连通性探测会调用远端模型服务，本机不运行该大模型；可在 GPU 分配前进行。它只能验证接口和返回格式，不能证明机器人控制效果。涉及 CUDA/EGL 的检查另列如下。

### 0.3 显卡任务：先检查设备，再运行第一轮 30 个计划 episode

| 编号 | 显卡执行内容 | 数量 | 用途 |
| --- | --- | ---: | --- |
| G0 | CUDA/EGL 上下文与设备绑定检查，确认模型推理和仿真渲染使用指定设备 | 最小必要探测；设备/相关运行环境变化时复查 | 防止错卡、初始化失败；计 GPU 时间，不产生成功率样本。模型加载与推理检查尽量结合首个已记账运行，不另开未登记机器人 episode |
| G1 | **C0：RDT + ED，QD 关闭**，运行 tasks 0…9 | 10 | 测出当前共同运行条件下的性能对照 |
| G2 | **Q0：RDT + ED + 原 sparse QD**，运行 tasks 0…9 | 10 | 测出本轮优化起点 |
| G3 | **N1：RDT + ED + 距离/夹爪比例 QD**，运行 tasks 0…9 | 10 | 检验新行为表示是否提高成功率 |

G1/G2 按既有冻结顺序在同一 task 内交错执行，先完成这 20 个对照，再执行 G3 的 10 个候选运行。各组使用相同的 task/env_seed/policy_seed/init 条件，实际随机数消耗可能因算法而不同。N1 的前两个任务已经包含在这 10 次中，只检查实现和数值有效性，不额外加两次，也不依据其成功与否提前挑选结果。

每次完整运行中，资源分工如下：

```text
CPU：仿真状态推进、任务控制与调度
  ↓ 相机观测（通过 GPU/EGL 渲染）
GPU：图像编码、RDT 动作生成、ED 去噪搜索
  ↓ reward 评分与 QD archive/parent 选择（按现有 CPU/GPU 张量实现）
选出动作 → 模拟器执行前 8 步 → 获取新观测 → 重复
  ↓
任务成功或达到 720 步上限 → 保存结果、日志和视频
```

Stage 在触发时调用远端服务；本机 GPU 可能保留模型并等待。ED/QD 参与的是推理搜索，具体张量计算可能在 GPU 上执行；只有离线重放和小规模逻辑检查归入前面的 CPU 测试。Stage 关闭引导后的周期按现有无引导路径执行，不能把每个周期都计成 176 个候选。

### 0.4 后续显卡任务：满足条件才加入队列

| 阶段 | 进入条件 | 实际运行哪些算法 | 计划 episode 数 | 回答的问题 |
| --- | --- | --- | ---: | --- |
| 第一轮 D1 | 准备检查和运行前提满足 | C0、Q0、N1，各 10 | **30** | 新 N1 是否优于当前起点并达到开发门槛？ |
| 条件分支 D2 | N1 未晋级，且证据支持保留 XY 并加入夹爪模式 | C0、Q0、N2，各 10 | **30** | 在容量仍为 16 时，XY×夹爪联合分区是否更有效？ |
| 条件分支 D3 | 前一候选未晋级，且有实际评分窗口问题的依据 | C0、C_H、Q0、Q_H，各 10 | **40** | 评分覆盖 8 步是否改善结果，收益是否来自通用 ED 改动？ |
| 独立验证 V | 第一个候选 Dev ≥5/10、且不低于同轮 C0/Q0；H 还需不低于 C_H | 冻结候选、C0、Q0；每组 10 tasks×2 seeds | **60** | 开发结果能否在未用于开发的随机种子上复现？ |
| 正式验收 F | V 候选 ≥10/20、且不低于同轮 C0/Q0，必要有效性检查通过 | 候选、C0、Q0 各 10；H 路线另加 C_H×10 | **30 或 40** | 固定验收条件下是否达到 ≥5/10，以及 QD 消融结果如何？ |

C_H 是 C0 改成八步评分；Q_H 是 Q0 改成八步评分。D2/D3 的先后由失败诊断决定，任一候选晋级就停止新增开发分支。验证失败即停止本版晋级流程；不会看过验证结果后再调参数并重测同一组。

两个预算例子：N1 直接晋级并通过验证，则计划量为 `30 + 60 + 30 = 120` 个 episode；若 N1、N2 均未晋级，H 晋级并通过验证，则为 `30 + 30 + 40 + 60 + 40 = 200`。这些是对应路径的计划 cell 数，不包含旧 baseline 和 infrastructure recovery 的额外尝试，也不表示这些运行已经发生。预算不足时停止派发，不能保证预留小时数足以跑完全部 cells。

**第一批可审阅的工作包就是 T0–T3、必要 G0，以及 C0/Q0/N1 三组共 30 个计划 episode，再用 T4 汇总结果。** 本机按一个独占 GPU worker 串行调度；多个算法组不等于同时占用多张卡。全研究累计上限仍为 240 attempts / 48 GPU-hours，等待远端 Stage 时的 GPU 占用也计费。

## 1. 审阅摘要

建议以 **P2（C0，QD OFF）作为性能对照，sparse QD（Q0）作为算法起点**。先完成已经冻结的 C0/Q0/N1 同轮实验；若 N1 未获得晋级资格，再根据证据选择空间与夹爪联合表示 N2 或执行窗口一致性 H。三条路线分别评估，本版不叠加。

目标是冻结一个实际保留 QD+ED 作用的候选，在 `libero_object_swap` 固定 10-task 工程验收上达到 **≥5/10，且不低于同轮 P2 和起始 QD**；独立验证集、机制消融和全部失败记录随版本一并交付。

| 审阅项 | 建议采用的设计 | 主要取舍 |
| --- | --- | --- |
| 与现有研究的关系 | 作为当前 study 的前瞻性扩展，不新开一份 240-attempt 额度；N1 协议保持不变 | 避免重复 baseline、污染旧 cohort 或重置失败记录 |
| 第一优先级 | 完成 C0×10、Q0×10、N1×10 | 当前没有新有效在线成功率，先补齐最关键证据 |
| 条件候选 N2 | 4×2×2 的 XY×夹爪命令模式 archive，总容量仍 16 | 保留二维空间，但牺牲一半 Y 轴分辨率；有待检验 |
| 条件候选 H | t1…t7 与 t1…t8 的评分窗口对照，P2/Q0 两种算法各一对 | 可区分通用 ED 窗口收益与 QD 交互；不是 descriptor 改动 |
| 开发额度 | N1 30 + N2 30 + H 40，至多 100 个计划开发 cells | 有候选晋级即停止新增开发矩阵，不要求三条路线全跑 |
| 验证与正式额度 | 保留 validation 60、formal 至多 40 | 默认只支持一个完整 validation 候选和一个 formal 候选 |
| 本版暂缓 | 新 learned scorer、Stage/FSM 改造、跨 chunk memory、重训 RDT、额外模拟器分支 rollout | 先解决已有证据指向的具体问题，维持归因和预算边界 |

**本方案不保证达到 5/10。** 达标与未达标都应形成可复核的结论；不得靠更换任务、挑 seed、重复 formal 或删除失败获得目标数字。

## 2. 研究现状与证据基础

### 2.1 当前 baseline

| ID | Profile | 历史成功数 | 成功任务 | 定位 |
| --- | --- | ---: | --- | --- |
| C0 | `p2_stage_on_abs_rbf_control` | 3/10 | `{3,8,9}` | 首轮 QD 的同轮性能对照 |
| Q0 | `eds_quality_diversity_sparse_primary` | 2/10 | `{5,8}` | 本轮主要 QD 起点 |
| Q1 | `eds_quality_diversity_uniform_expand20` | 2/10 | `{5,7}` | 并列最优历史 QD 参考，不默认增加在线矩阵 |

另一轮 Direction-RBF 恢复审计中的 C0 为 4/10，不能与上述 3/10 合并为稳定性能；Q0 未被证明优于 Q1。base Object 的 RDT unguided 9/10 不属于 Swap。历史 QD 候选均没有通过全部采用标准。

### 2.2 新研究状态快照

现有 worktree：`/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z`。

本次观察 HEAD：`16f7fae1d948ad8359fa1b64d56352a1914e89ac`。状态文件更新于 `2026-09-22T05:03:31Z`：

- N1 已实现，`CPU_READY_UNEVALUATED`，在线分数 null；项目目标仍未达成。
- 累计 2 个 dispatched attempts：1 个旧 baseline 启动无效样本，1 个 N1-round Q0 在启动期间因外部 GPU 进程出现而中止；有效在线结果为 0。
- 两次均没有形成可用于 N1 效果判断的动作执行结果；累计约 `0.0288724 GPU-hours`。
- 原 baseline cohort 已以 1 invalid、19 not-dispatched 关闭，不回填、不删除，不计算完整 SR。
- 新 N1 cohort 的外部设备冲突属于单独保留的 infrastructure abort；是否恢复以其精确身份和现有恢复记录为准。
- 最新资源修订允许当前服务器上任一满足准入条件的 GPU，仍为一个独占 worker。早期文档中的 GPU7-only/GPU5-only 已被后续修订替代。

以上是时间快照，不是执行前的实时状态。若本文获准执行，应先重读最新总账：已经完成的 cells 不重复跑，已经揭示的结果不得假装未见。本文不覆盖现有恢复和资源调度。

### 2.3 为什么选择这三条路线

1. 历史 Q0 的 20 条 trace 精确重放发现 82 次涉及不同八步夹爪命令序列的 archive 淘汰，equal-reward 情形为 0；说明存在具体动作差异被 reward-based replacement 合并的机会，尚未证明被淘汰动作更能成功。
2. N1 的 radial×duty 近似固定候选池回放保留了 27/82 个旧淘汰出现记录，其中 25 个随后成为 parent；同时占用 cell 中位数 16→4，新合并候选对 7,814、分开旧候选对 986。它可能保留夹爪差异，却丢失较多空间信息。
3. 当前代码评分 t1…t7，QD descriptor 和真实执行覆盖到 t8。历史记录中 342/3,520 个候选的 t7/t8 XY cell 不同，17/220 个 batch 的最近目标 XY 候选身份不同；是否影响实际 reward 排名和任务结果仍未知。
4. H1/H4/H5 已经表明 partition、quality lineage rescue、secondary activation 可以改善而任务仍失败。因此，本版以任务成功为主要晋级条件，机制指标用于解释，不再追逐通用 coverage/activation 高分。

N1 的 t8 Z 在旧 trace 回放中是近似重建；它的 survivor/alias 统计不是精确在线反事实证据。未执行候选的真实任务后果仍为 Unknown。

## 3. 所有实验的公共设置

| 项目 | 冻结设置 |
| --- | --- |
| Policy/checkpoint | RDT-1B LIBERO-Object EMA，固定模型和 T5/SigLIP 指纹 |
| Observation/action | `libero_gt_rollout`，现有 GT 槽位和 decoder；不修改动作执行器 |
| Task suite | `libero_object_swap`，tasks 0…9，strict perturbations |
| Episode | 最大 720 environment steps，20 Hz，8-action execution chunk |
| Prediction/inference | 64-step prediction；不覆盖 checkpoint 的常规 5-step 去噪设置 |
| Guidance | `use_guidance=true`，`guidance_type=eds`，Stage ON，grounding OFF |
| 新共同 Stage 条件 | `codex_login_astra_low_v1`，固定当前 wrapper、prompt、parser、查询触发和模型条件 |
| 缓存与输入 | task-bound Stage 描述、canonical reward、关键点/BDDL/init/dependency 指纹固定 |
| RNG/init | 每 task 明确 env_seed、policy_seed；记录实际 init-file 与 row hash |
| EDS | population=16，iterations=10，use_cem=false，temperature=0.1 |
| Initial RBF | `rbf_diverse_denoise`，absolute EEF，scale=20，start=0.8 |
| Rollout RBF | `rbf_diverse`，absolute EEF，scale=20，start=0.6，iters=all |
| Renoise/schedule | 3→1，`legacy_linear`，skip_final_steps=0 |
| Chunk memory | fresh，memory fraction=0 |
| Q0 | target-relative endpoint XY；4×4，capacity=1，sparse_priority，exponent=1 |
| Q0 bounds | initial quantiles `[0.05,0.95]`，expand=0.10，minimum span=0.08m，clamp_edge |
| 后期旧开关 | fixed_initial；global anchor=0，secondary lane=none，degenerate fallback=none |
| 模型搜索预算 | 完整 guided chunk 176 candidates / 11 batched score calls |

新的 Stage provider、task cache 身份和独立任务进程 RNG 与历史条件不同。所有 arm 都采用相同的新条件，标记 `input_repaired + codex_login_astra_low_v1`。历史 3/10、2/10 仅作背景，不作为新轮差值的分母。

176/11 不代表全部计算相同。记录实际 DiT/encoder/感知/reward 调用、batch rows、denoising、guided/unguided chunks、Stage 调用/token/延迟、episode wall time 和 GPU-hours；等待 Stage 的 GPU 占用也计入成本。

## 4. 三条机制路线

### 4.1 N1：完成既有 radial×duty 候选

N1 不重新设计、不根据新的离线统计调整 bins。沿用 `56031d2` 中冻结的算法假设及后续有效工程修订。

Descriptor：`[||p_t8-target||_2, positive_gripper_command_duty]`。Duty 是实际八步解码命令中 +1 的比例；它不是 grasp probability，也不是已经验证的闭合比例。

- 径向轴 4 bins：沿用历史 quantile/expansion/minimum span；duty 轴 4 bins，固定 `[0,1]`。
- 总容量 16、capacity=1；quality、tie、sparse allocation、ED 和执行器不变。
- 完成原定 C0×10、Q0×10，再运行 N1×10。前两个 candidate tasks 仅检查实现与有限性，不按成败提前筛选。
- 缺失的诊断数据记为 Unknown；不为增加日志而静默改变已冻结 N1 的科学路径。新增统一观测若必需，应先追加工程说明并对所有比较 arm 一致应用。

重点报告：候选池是否有不同 duty、是否保留并采样、是否进入实际执行、是否伴随后续可观测进展，以及空间/方向模式是否流失。

N1 的晋级条件保持原样：Dev ≥5/10，且不低于同轮 C0/Q0，正确性和必要安全检查通过。Occupancy=4 不是事后新增失败门，73/82 pair separation 也不是晋级证据。

### 4.2 N2：保留 XY 的空间—夹爪联合表示（条件执行，尚未实现）

**假设：** N1 丢失 azimuth 的代价过大；在总 archive 容量 16 内保留二维目标相对位置，并用一部分空间分辨率换取夹爪命令模式，可能更好地兼顾接近几何与可执行动作差异。

本版提出一个可审阅的具体结构，不启动参数扫描：

```text
descriptor = [target-relative t8 X, target-relative t8 Y, gripper_mode]
gripper_mode = 0 if positive_command_duty < 0.5 else 1
grid = 4 × 2 × 2
cell_capacity = 1
maximum_elites = 16
```

X/Y 边界分别使用 Q0 的固定初始化 quantile/expansion/minimum span。归一化后：

```text
ix = clamp(floor(4 * normalized_x), 0, 3)
iy = clamp(floor(2 * normalized_y), 0, 1)
ig = gripper_mode
cell_id = ((ix * 2) + iy) * 2 + ig
```

这相当于把 Q0 的一个 Y 轴细分位替换为夹爪模式位。选择 X4/Y2 是本方案预先提出的固定设计，不声称为历史最优；获批后不根据 Dev 结果交换成 X2/Y4、扫描 duty threshold 或叠加容量变化。

保持 Q0 的 reward、stable fingerprint、replacement、sparse-priority、16-parent、176/11、fresh chunk 和 reset。只为新 descriptor 提供隔离的三轴编码/metadata，旧 Q0 的二维路径必须保持回归等价。

**已知代价：** Y 分辨率减半；如果只有一个夹爪模式，最多只有 8 个 cells 可用；相同 duty mode 仍可能包含不同开合时序。N2 不是无损表示，也不预设其必然优于 N1。

CPU/固定池检查：

- 在同一批可用 trace 上比较 Q0/N1/N2 的分支保留、parent 身份、XY 空间覆盖和新增合并；N1 近似径向重建仍明确标注。
- N2 的存储 t8 XY 与解码 duty 可使用精确值，不把未知 Z 伪造成 exact evidence。
- 每轮不超过 16 elites、恰好 16 parent slots，score/model 预算不增加，reset/target-change/source fingerprint 正确。
- 至少存在一个实测候选流产生不同分区并改变 parent 身份；若与 Q0 恒等，则机制未实际实现/激活，不能以该标签进入任务比较。

同轮矩阵：C0×10、Q0×10、N2×10，共 30 cells。选择独立 Dev cohort D2；与 N1 的跨 cohort 分数仅作描述，不直接宣称 N2 优于 N1。要主张直接优于 N1，需要另外预注册并计入预算的同轮 N1 arm，本版不包含。

该矩阵检验联合表示的整体作用，不能单独分离“降低 Y 分辨率”和“加入夹爪位”的因果贡献；若结果成功，论文式细粒度归因需要额外匹配消融，不由本版 30-cell 矩阵自动支持。

N2 的 Dev 晋级门事前固定为 ≥5/10 且不低于同轮 C0/Q0。分支/coverage 改善不能替代任务门；无需要求每一个控制成功任务都零回退，但必须完整报告 gained/lost。

### 4.3 H：评分窗口与八步执行一致性（条件执行，尚未实现）

**假设：** EDS reward 使用 t1…t7，却执行到 t8，可能使搜索依据与实际执行前缀不一致。先检验实际 reward 排名变化，而非把最近目标 XY 候选身份变化直接当作 reward 错排。

离线准备：使用当前任务绑定的 canonical reward，保存或核对高精度 t0…t8 和完整八步 decoded actions；比较 t1…t7/t1…t8 的 reward、排序、最终选择和计算量。若旧 trace 不足以准确重建，就利用开发运行中预先定义的观察记录，不能把近似值标记为精确。

唯一拟改动：新增默认关闭的 EDS-only 评分窗口选项，候选使用 t1…t8；旧模式仍使用 t1…t7。不修改 VLS/FKD 的共享窗口语义，不改 reward 函数、Stage、decoder、Q0 descriptor 或 ED population。

```text
C0:       P2, QD OFF, legacy t1…t7
C_H:      P2, QD OFF, full executed t1…t8
Q0:       sparse QD, legacy t1…t7
Q_H:      sparse QD, full executed t1…t8
```

在 D3 的同一 10-task cohort 上各运行一次，共 40 cells。四组逐 task 的执行顺序事前确定并交错，固定其他条件。

分析：

- `ΔED = success(C_H) - success(C0)`。
- `ΔQD = success(Q_H) - success(Q0)`。
- `interaction = ΔQD - ΔED`，只作为小样本配对描述，不作显著性结论。
- Q_H 与 C_H 对比用于检查 QD 在新窗口下的额外作用；若二者都提高，不得把全部收益归因于 QD。

模型 candidate evaluations/score batch 次数保持相同，但每次 reward 接收 8 个而非 7 个轨迹点，算术量并不完全相同；按实际成本披露。

Q_H 晋级需 ≥5/10、不低于同轮 Q0、C0，且不低于 C_H。只有 C_H 达标不能完成 RDT+QD+ED 目标；若 Q_H 与 C_H 持平，允许作为工程候选，但 QD 的净性能贡献仍未建立。

**边界：** H 属于 ED 内部评分输入改动。本方案批准时应明确允许这一范围；它不等于授权更改外部 reward provider 或 Stage。当前默认推荐将其作为第二条条件路线，单独冻结，不与 N1/N2 叠加。

## 5. 执行顺序、分支选择与候选选择

1. **P0：准备和账本复核。** 无新增模型 rollout。核对最新 HEAD、active worker、已 dispatch identities、runtime fingerprint 和预算；识别已有 N1 的完成/恢复状态。不能与现有 runner 竞争或复制启动。
2. **D1：完成现有 N1 三组比较。** 使用原先冻结的 Dev identities。旧 baseline 失败独立保留，N1 cohort 不被改名为旧 baseline 的成功重试。
3. **若 N1 达到晋级门，冻结 N1 进入 validation，停止新增 N2/H 开发。** 不为寻找更高分额外搜索。
4. **若 N1 未晋级，进行一次限定于已有记录的复查：**
   - 若保留/执行了夹爪差异，同时明确损失 XY 分辨率或空间行为，则优先 N2；
   - 若 t7/t8 导致实际 reward 排名/最终动作差异，且与已执行反馈存在待验证联系，则可优先 H；
   - 若 N1 实际没有动作模式机会，先记录适用性不足，不通过调 bins 强行激活。
5. N2/H 的顺序在其运行前写入 outer-loop 决策；另一路只在前一路未晋级、仍有机制依据且预算足够时运行。不得因看过 validation 而回来挑另一候选。
6. 第一个符合冻结 Dev 条件的候选进入唯一完整 validation；本版不承诺 validation 失败后还能再跑第二个候选。失败则保留当前 study 的未达标结论，新的候选验证需要前瞻性预算和独立 cohort 设计。

N1/N2/H 若都未晋级，本版结束为 `TARGET_NOT_MET`。单一候选失败允许按上述分支继续，不允许无证据增加第四个机制或反复扫描参数。

## 6. 分阶段矩阵与预算

### 6.1 Episode 预算：沿用现有 240 上限，不重置

| Bucket / phase | 计划内容 | 上限 |
| --- | --- | ---: |
| 原 baseline | 现有预留 20；其中 1 个 invalid 已消耗，原 cohort 已关闭；其余不自动重用 | 20 |
| Development D1 | C0/Q0/N1 各 10，现有矩阵；已 dispatch 的那次 infrastructure abort 占其中一个原始 attempt | 30 |
| Development D2 | C0/Q0/N2 各 10，条件执行 | 30 |
| Development D3 | C0/C_H/Q0/Q_H 各 10，条件执行 | 40 |
| Validation V | 最终候选/C0/Q0 各 20 | 60 |
| Formal F | 最终候选/C0/Q0/独立 QD 消融，各至多 10 | 40 |
| Infrastructure recovery | 仅精确身份恢复，包含现有未完成的合法 infrastructure recovery | 20 |
| **总计** | 全 study 的 dispatched attempt 上限 | **240** |

D1+D2+D3=100，与现有 development bucket 对齐。一个原始 cell 因 infrastructure abort 未得到有效结果时，原 attempt 留在原 bucket，恢复 attempt 计 recovery bucket；不把恢复写成免费的额外 valid episode。算法/数值/执行器导致的合法失败不得重新跑到成功。

表中是预留上限，不是必须全部消费。原 baseline 的未用 19 个名额没有被本方案挪作新研究；validation/formal 的 100 个名额在晋级前保持保留。若现有研究在审阅期间新增消耗，按实际余额减少可执行矩阵，不能自动追加 240。

### 6.2 GPU-hours 与运行资源

| 阶段 | 计划预留 GPU-hours |
| --- | ---: |
| 原 baseline | 4 |
| Development | 16 |
| Validation | 14 |
| Formal | 10 |
| Recovery / probes | 4 |
| **总计** | **48** |

任一总预算耗尽即停止新 dispatch。开始下一阶段前，以实际完成任务的耗时、720-step 失败 episode 的耗时和当前 provider 延迟估计剩余需求；这些小时数是预留而非运行时间保证。新 Stage synthetic probe 不能证明整轮耗时或配额可行。

按当前 study 的最新资源修订，可在本机空闲 GPU 中动态选择，仍为一个独占 worker；绑定 UUID/PCI/CUDA/EGL 并记录硬件变更。设备切换不得修改科学配置。Stage 等待、失败启动、context probes、恢复都计 GPU 用量；GPU 分配前的 CPU 等待不计。外部进程出现时只处理本研究自有 worker，不抢占他人任务。

## 7. 数据划分、验证与正式验收

### 7.1 Cohort 冻结

- D1：沿用现有 N1 已冻结的 task/env_seed/policy_seed/init identities，不重新抽取。
- D2/D3：只在执行前从未暴露记录中建立并冻结 task-complete Dev cohort；禁止读取 validation/formal outcome 来选择它们。每个候选与其同轮对照使用完全相同的 identities。
- V：使用现有 seed plan 中下一个未使用的 validation cohort，10 tasks×2 seeds；候选/C0/Q0 共 60 cells。不能依据 Dev 成败定向挑 seed。
- F：历史固定 acceptance map `{0:44,1:235,2:43,3:546,4:6,5:621,6:197,7:87,8:151,9:548}`；它已暴露，不能称为 unseen test。

当前 backend 固定 init row0，随机 seed 不自动改变布局。因此 V 提供随机性稳健性证据，不能称为未见布局泛化。每个 cell 记录实际 init-file 和 row hash；扩展布局属于后续单独设计。

同 seed 不保证两种搜索算法消耗相同的随机数流，更不构成逐动作反事实配对。配对分析的单位是 task/env/policy/init 条件下的完整 episode。

### 7.2 Validation 晋级

冻结候选算法和全部超参数后，完整执行 V：

```text
candidate >= 10/20
candidate >= C0 on the same 20 cells
candidate >= Q0 on the same 20 cells
identity / information / numerical / action / accounting validity PASS
required execution-safety and evidence checks PASS
```

报告两个 seed blocks 和全部 task-level gain/loss；不要求每一个 task 都改善，不根据结果降低阈值。V 失败不进入 formal，也不在该 V 上改算法后重测。本版保留的是一次完整 V 的预算。

### 7.3 Formal acceptance 与重复 arm

通过 V 后冻结最终 commit、resolved configs、输入、对照/消融定义与报告脚本；只允许一个正式候选：

```text
10/10 expected task/seed identities have terminal records
candidate success_count >= 5/10
candidate success_count >= same-round C0 success_count
candidate success_count >= same-round Q0 success_count
numerical/action/execution validity and required safety PASS
compute / artifact / provenance PASS
QD substantively active in deployed algorithm
```

正式第四组定义为移除 QD、保持候选的其余 ED 设置：

- N1/N2 的 QD-OFF 若与 C0 完全同构，则直接标记为 C0 的同一对照，不伪造独立组；F 可只运行 30 cells，剩余 10 不挪去刷另一个候选。
- Q_H 的 QD-OFF 为 C_H，与 legacy C0 不同，因此 F 为四组 40 cells。
- N1/N2 恢复旧 descriptor 的消融就是 Q0，不能把同一结果重复包装成额外样本。

正式失败不允许换候选后继续使用同一 acceptance 刷分。样本和失败保留，study 目标未达。达到门槛时交付工程版本；若 QD-OFF 持平，只能说工程验收通过、QD 的额外净性能贡献尚未建立，不能声称消融证明机制优越。

## 8. 观测、分析与真实性要求

每个 episode 至少保留 task/seed/init/config/commit、terminal outcome、视频、完整 Stage timeline、guided/unguided chunk 数、实际计算成本、错误分类和 attempt 恢复身份。

每个 guided chunk 尽可能记录：

- 实际用于评分和执行的 horizon、起始 EEF、t1…t8 投影、八步 decoded gripper commands、当前目标关键点；数值精度与来源明确。
- 候选 descriptor、reward、archive surviving fingerprint、parent allocation、selected action，以及不同夹爪模式的机会和实际使用情况。
- 预测几何与下一次真实 observation 的对应；二者分字段，`target_distance_before/after` 等旧代理指标不能冒充环境进展。

N2/H 的记录格式在它们执行前冻结；若要补记昂贵数据，限定预先选定的 chunks，所有对照统一记录并计实际开销。不要仅保存成功片段或只在候选上做额外评分。

失败过程标注使用统一规则：目标接近、可见稳定持有、抬升、运输、放置、掉落、错误物体或未知。视频无法确认时写 Unknown；Stage 输出本身不能当作真实抓取标签。诊断可使用明确标记的模拟器真值作 observer，但不得反馈给部署时选择器。

主结果：成功数/分母、同轮差值、gained/lost/retained、部署错误与不完整记录。机制与成本随后报告。coverage、overflow、cell occupancy、rescue、激活率通常是解释指标，不新增任意 promotion 硬门。

实现声称的不变量必须满足，例如容量、slot 数、source identity、默认行为回归；若新算法承诺保护某种质量，就按事前定义检查。不得在看到失败后删除硬门，也不得要求新 quality 永远保留旧 scalar reward 最大值而阻断合理的新假设。

10-task 小样本只作配对工程证据；可以描述区间和配对 discordance，但不据此声称总体成功率稳定为 50% 或有统计显著性。所有开发、validation 选择和失败均完整披露。

## 9. 暂缓方向及重新进入条件

| 方向 | 本版处理 | 重新进入所需证据 |
| --- | --- | --- |
| 新 quality / progress scorer | 只补观察，不实现 | 证明当前选择常拒绝在真实已执行反馈中更有价值的行为；明确可部署信息、评分规则和独立预算 |
| 跨 chunk memory / continuity | 暂缓 | 观察到真实进展被下一次重规划破坏，排除只减少曲线跳变而无任务价值 |
| Stage/FSM 改造 | 固定当前共同条件 | 独立的控制时序假设与同轮消融；不得混入 N2/H 收益 |
| 增大 population/iterations、grid/bounds 扫描 | 不默认重跑 | 有与旧负结果不同的可证伪机制依据，并提供计算匹配对照 |
| RDT 微调/新模型/learned descriptor | 范围外 | 独立训练与数据隔离方案、资源批准 |
| 模拟器候选分支 rollout | 范围外 | 完整状态恢复正确性、额外 transition 预算、诊断信息与部署信息隔离 |

## 10. 实施边界、交付与审阅点

本文批准后，应先形成 append-only 研究修订并处理当前 active worker/runner 所有权，再为 N2/H 建立独立 iteration/source/manifest；不要原地改写 N1 已 dispatch 的科学身份。可在当前专属研究 worktree 的新提交实施，或按并发需要另建隔离 worktree，但只有一个调度所有者和总账。

历史 worktree、manifest、日志和受保护未跟踪文件保持原状。本方案只在根目录新增文档；它不是旧报告勘误或主线整合。必要 CPU 测试覆盖实质语义变化，在线启动不由本文自动触发。

交付物：

1. 每条实际执行路线的 protocol、代码/config 身份、任务级结果和机制解释。
2. 一份权威预算/attempt 总账，区分 invalid、合法失败、infrastructure abort 和未执行。
3. 达标时的正式 profile、准确 commit、算法伪代码、复现说明、validation/formal/消融结果及局限。
4. 未达标时的 `TARGET_NOT_MET` 报告，指出证据排除了什么、仍未知什么、下一步需要何种新增证据。

**建议重点审阅：**

- 是否接受“先完成既有 N1，后续 N2/H 条件执行”的顺序和单候选验证策略？
- 是否接受 N2 的固定 4×2×2 结构，以一位 Y 分辨率换一位夹爪命令模式，不进行参数扫描？
- 是否允许 H 修改 EDS-only 的评分窗口，同时使用 C0/C_H/Q0/Q_H 四组分离归因？
- 是否沿用累计 240 attempts / 48 GPU-hours，并保留 validation ≥10/20、formal ≥5/10 且不低于同轮对照的门槛？

## 11. 证据索引

- [根目录 handoff](/home/hynx/VLA-Pilot++/HANDOFF.md)：历史范围与结果口径；9 月新进度另看下列文件。
- [首轮 QD 报告](/home/hynx/VLA-Pilot++/.worktrees/exp/eds-quality-diversity/docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-06-eds-quality-diversity-report.md)：C0/Q0/Q1 结果与固定设置。
- [当前研究状态](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/research-state.yaml)、[统一总账](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/docs/03_evidence/qd_ed_final/iteration-ledger.md)：动态执行状态与授权修订。
- [恢复的 baseline profiles](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/configs/qd_ed_final/baseline_profiles.json)、[baseline parity](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/docs/03_evidence/qd_ed_final/baseline-parity.md)：算法起点与工程条件差异。
- [历史动作诊断](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/docs/03_evidence/qd_ed_final/historical-diagnosis.md)、[N1 分析](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/experiments/iteration_001_execution_intent/analysis.md)：82 次淘汰、N1 信息损失与 t7/t8 边界证据。
- [N1 冻结协议](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/experiments/iteration_001_execution_intent/protocol.md)、[启动修复和顺序修订](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/experiments/iteration_001_execution_intent/startup-repair-amendment.md)：D1 不覆盖的既有约束。
- [Stage provider 修订](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/experiments/iteration_001_execution_intent/codex-provider-amendment.md)、[可用 GPU 修订](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/experiments/iteration_001_execution_intent/available-gpu-amendment.md)：共同运行条件；资源以最新总账复核。
- [当前评估与预算规则](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/docs/03_evidence/qd_ed_final/evaluation-policy.md)：数据隔离、240/48 上限和 validation/formal 门槛；早期固定 GPU 描述以较后资源修订为准。
