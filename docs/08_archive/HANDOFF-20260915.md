# VLA-Pilot++ 技术交接

审查日期：2026-09-15（UTC）；Git、进程、设备与路径为本次只读审查快照，主要状态复核于 07:42 UTC。本文为首次根目录交接文件，不替代各实验的冻结协议和原始证据。

## 接手速读摘要

- **项目不是“尚未接通”，而是“基础接通、OOD 算法收益仍未达标”。** RDT 的 LIBERO GT observation/action 链路及 VLS 已整合进 `main`；EDS、RBF/P2、QD、autoresearch 和物理 Stage/FSM 的后续工作主要留在实验 worktree，未整合进主线。
- **EDS-QD 的 Object-Swap `>=5/10` 目标没有完成。** 历史 QD 中通过 validity 的最好记录是 `2/10`，但没有 QD 候选通过全部 adoption gates。运行对照仍推荐 P2 absolute-RBF + Stage ON、QD OFF：QD 首轮同轮对照为 `3/10`；另一轮 Direction-RBF 恢复审计中对照为 `4/10`，不能混作同一次实验或当成 QD 成绩。
- **autoresearch 已于 2026-08-12 收束为 no-adoption，不是在等待一个正在运行的实验。** 当前 HEAD `744e08ba4398`；最终账面为 70 个有效在线 episode attempts、98/144 reservations、6.946832/48 GPU-hours、**本研究新 formal episodes 为 0**。停止依据是版本化 no-progress/候选边界，不是耗尽 GPU-hour 总预算。
- **接手先读本文件第 5、6 节，再读 autoresearch 总账末尾和 Run045 manifest。** 最终报告存在“没有进入 validation”的错误概括；H1 实际进入独立 validation，候选 `1/10`、对照 `0/10`。部分状态字段、CSV 和事件索引滞后，不能直接据其恢复调度。
- **不要直接重跑旧 runner。** 旧 formal 已暴露，旧输出多为冻结证据；设备当前全部繁忙，部分依赖不受顶层 Git 跟踪，若干绝对路径已经失效。继续算法研究、修复代码、恢复环境或整合分支，均须另行明确范围；本次只新增本文，没有执行实验或修复。

## 目录

1. [项目总览与推荐入口](#overview)
2. [全部 worktree、分支与未提交状态](#worktrees)
3. [开发历史时间线](#history)
4. [核心功能与算法进度](#implementation)
5. [实验结果、可比性与经验](#experiments)
6. [未完成事项、矛盾与交接风险](#risks)
7. [接手操作指南](#operations)
8. [后续工作优先级与授权边界](#next)
9. [证据索引与审查覆盖](#evidence)

<a id="overview"></a>
## 1. 项目总览与推荐入口

### 1.1 项目解决什么问题

项目在预训练机器人策略推理时进行语言/关键点引导和候选动作搜索，希望改善分布外操作，不以重新训练模型为当前 EDS-QD 主路径。现有平台包含 Diffusion Policy、PI05、RDT 三类 policy wrapper，以及 CALVIN/LIBERO 适配。近期研究集中在 RDT-1B 的 LIBERO-PRO `libero_object_swap`：保持任务目标和物体类别，但交换目标与干扰物的初始位置，考验策略对位置先验的依赖。

主要运行链路是：`main.py` 创建 adapter/policy/perception → 获取 observation、关键点和分阶段 guidance → policy 生成 action chunk → VLS 或 EDS/QD 引导/选择 → decoder 和 adapter 执行动作 → 记录 simulator success、视频、metrics 和 stage events。代码入口见[模块索引](#implementation)。

概念必须分开：

- VLS 在 denoising 中使用 guidance/diversity 梯度与可选 FKD resampling。
- 原始 EDS 进行 population scoring、resample、renoise、短 denoise rollout、最终选择。后来的 EDS+RBF 会使用 diversity 梯度，不能把整个 P2/QD 栈笼统描述为完全 gradient-free。
- P2 是固定的一组 EDS + initial/rollout absolute-RBF + Stage ON 配置，不是新的 checkpoint。
- QD 在 EDS 内增加行为描述、archive、cell elite 和 parent allocation；“QD 被正确执行”不等于“成功率提高”。

[README](README.md) 可用于认识上游方法和安装思路，但其中论文收益数字、旧默认命令不构成本仓库各分支的实验验收证据。

### 1.2 当前该从哪里开始

| 接手目的 | 推荐入口 | 使用条件 |
| --- | --- | --- |
| 了解当前研究停在哪里 | [autoresearch worktree][WA]，`744e08ba4398`；[总账][ALEDGER]、[Run045 protocol][A45P]、[最终 decision manifest][A45M] | 先按 no-adoption 结论阅读；不是自动恢复授权 |
| 接手 EDS-QD 核心实现 | 同上；比较 QD 分叉基线 `5b0898e53d5b` 与当前 core/config diff | 新功能默认关闭；保留负结果和旧协议，不直接启用所有候选 |
| 获得较简洁的 EDS/P2 对照代码 | [PG/P2 worktree][WP]，冻结基线 `b3db98cf4fd9` | 显式使用 P2 profile；默认 YAML 不等于 P2 |
| 核对最初 QD 对照与预算 sweep | [QD worktree][WQ]，`beb8d3f07385` | 基线对照 3/10；两个有效 QD 最好 2/10，均未 adoption |
| 维护主平台、RDT GT I/O、PI05/VLS | [根目录](.)，`main@d51cb85f4855` | 主线没有后期 EDS/QD；本地 LIBERO-PRO 目录缺失，不能承诺即刻可运行 |
| 研究 Stage/FSM | [独立 FSM worktree][WS]，`4b3ed17476d5` | 已有负结果；它不是 autoresearch 的延续，也未合入其分支 |

当前没有可推荐为“达成 Object-Swap 目标的生产算法”的配置。原始 `libero_object` 的 RDT unguided `9/10` 和 PI05 `10/10`，与 Swap OOD 是不同评估，不填补该目标缺口。

<a id="worktrees"></a>
## 2. 全部 worktree、分支与未提交状态

### 2.1 Git 普查

`git worktree list --porcelain` 列出 **11 个 worktree，全部目录存在**；未报告 locked/prunable 项。本次在仓库 `.worktrees` 范围检查的额外 `.git` 标记与登记清单一致，未发现额外遗留工作树。共有 **12 条本地分支、8 条缓存 remote-tracking refs、1 条 stash、无 tag**；`git rev-list --all --count` 为 288 个可达提交。没有 fetch，故不推断远端当前状态或备份完整性。

下表时间是 HEAD commit 时间（UTC），不是实验完成时间。`main-only / branch-only` 是 `git rev-list --left-right --count main...<branch>`，不等于未整合功能数，尤其不能识别 squash 后的代码采用情况。

| ID / 实际 worktree 路径（相对根目录） | 分支 / HEAD | HEAD 日期；最近证据活动 | Git 工作区；相对 main | 用途、状态与建议 |
| --- | --- | --- | --- | --- |
| W0：`.` | `main` / `d51cb85f4855` | 06-04；未跟踪分析标注 06-05 | 仅 U1；0/0 | **平台整合已完成，后期研究未整合**。保留默认 PI05 入口及 RDT GT/VLS 能力；不直接在此开发实验算法 |
| W1：[`.worktrees/debug-diffusion-baseline`](.worktrees/debug-diffusion-baseline) | `debug/diffusion-baseline` / `c52834769741` | 05-26；未发现 outputs | clean；8/1 | **状态不明、保留参考**。只有 3 文件小改动：切换 `lerobot/diffusion_pusht`、200-step 配置和 action horizon key 兼容；无验证产物证明调试完成 |
| W2：[`.worktrees/exp/eds-init-fps`](.worktrees/exp/eds-init-fps) | `exp/eds-init-fps` / `2628fab7cda7` | 07-01；有未跟踪 FPS 设计 | 仅 U2；0/19 | **设计待验证，未见独有实现**。HEAD 与 W10 完全相同，分支间代码 diff 为空；不要误认为 FPS 已实现或已跑实验 |
| W3：[`.worktrees/exp/eds-init-pg-diverse-sampling`][WP] | `exp/eds-init-pg-diverse-sampling` / `b3db98cf4fd9` | 08-06；Direction 恢复报告至 08-05 | 仅 U3；0/45 | **P2 基线冻结、系列实验已完成，目标未达**。RBF、adaptive components、clean-tail、direction-RBF；保留为运行对照与历史证据 |
| W4：[`.worktrees/exp/eds-qd-autoresearch-libero-swap-ood`][WA] | `exp/eds-qd-autoresearch-libero-swap-ood` / `744e08ba4398` | 08-12 14:32；结论 14:29 | 仅 U4（受保护）；0/172 | **本轮已完成 / no-adoption**。协议、候选实现和总账最完整；当前接手主入口，但不授权新一轮在线实验 |
| W5：[`.worktrees/exp/eds-qd-stage-guidance-transition`][WS] | `exp/eds-qd-stage-guidance-transition` / `4b3ed17476d5` | 08-10 15:13；外部报告 19:19 | clean；0/65 | **实验已完成、负结果、保留参考**。物理 FSM 默认关闭；4 jobs 中 3 个未通过完整有效/安全审计 |
| W6：[`.worktrees/exp/eds-quality-diversity`][WQ] | `exp/eds-quality-diversity` / `beb8d3f07385` | 08-08 22:52；原始 QD 报告 08-07 冻结 | clean；0/63 | **首轮 QD 与预算 sweep 已完成，无 adoption**。保留原始基线和独立 sweep 审计；FSM 外部产物嵌在此 outputs 下，不代表代码已合并 |
| W7：[`.worktrees/feat/rdt-integration`](.worktrees/feat/rdt-integration) | `feat/rdt-integration` / `3835192744a4` | 05-26；早期 04–05 月实验 | 顶层 clean；3/28 | **早期路线被替代、保留参考**。ManiSkill/RDT 到 LIBERO 的语义调试；13 份 results 中 12 份 0/10，唯一 10/10 实为 PI05，不是 RDT |
| W8：[`.worktrees/feat/rdt-libero-gt-rollout-reintegration`](.worktrees/feat/rdt-libero-gt-rollout-reintegration) | `feat/rdt-libero-gt-rollout-reintegration` / `73b90c69b7ad` | 06-04；GT/VLS 验证至 06-03 | clean；3/95 | **GT/VLS 成果已择取整合，保留参考**。不能因 HEAD 非 main ancestor 就声称全部未合并；详见下方 squash 说明 |
| W9：[`.worktrees/feat/rdt-libero-object-ckpt`](.worktrees/feat/rdt-libero-object-ckpt) | `feat/rdt-libero-object-ckpt` / `1be4afbf17ea` | 05-26；训练/部署分析 05 月 | clean；3/64 | **已合入 W8、旧语义方案被替代**。训练管线与 checkpoint 对照有价值；本地微调模型不作为当前 RDT baseline |
| W10：[`.worktrees/feat/rdt_ed_steering_integration`][WE] | `rdt_ed_steering_integration` / `2628fab7cda7` | 07-01；Level4 证据 06-20 | 顶层 clean；0/19 | **EDS 集成完成、历史 OOD 队列另有暂停项**。PG/QD 祖先；独立 LIBERO-PRO 子仓库有修改，见 2.3 |

没有独立 worktree 的本地开发线：`chore/integrate-rdt-libero-vls@25e98a8fe2ad`，2026-06-04。其 tree 与 `main` 上的 `689f487` **完全一致**（本次 `git diff --stat 25e98a8 689f487` 为空），属于已经 squash 采用的整合成果，不应重复合并。

缓存远端方面：PG 本地比 `origin/exp/eds-init-pg-diverse-sampling@8497609` 多 `b3db98c` 这一提交；FPS、QD、autoresearch、FSM 没有对应 upstream。其余 7 条缓存 remote refs 与同名本地分支 HEAD 一致。**本地有提交不代表已推送或外部产物有备份。**

### 2.2 未提交、未暂存与 stash

11 个顶层 worktree 均无 staged 或 unstaged tracked diff。以下 **4 个未跟踪文件原样保留**：

| 标记 | 所在树 / 路径 | 接手注意 |
| --- | --- | --- |
| U1 | W0：[RDT guided-denoise/VLS 分析](docs/02_analysis/vls_guidance/2026-06-05-rdt-guided-denoise-loop-vls-steering-analysis.md) | 有价值的主线调用链分析，但未提交，且早于 EDS grouped config |
| U2 | W2：[FPS 初始化设计](.worktrees/exp/eds-init-fps/docs/01_specs/eds-init-fps-design.md) | oversampling + trajectory FPS 提案，不是已实现功能 |
| U3 | W3：`docs/01_specs/2026-08-06-eds-quality-diversity-goal-execution-prompt.md` | 尚未提交的执行提示词，不作为当前批准证据 |
| U4 | W4：`docs/01_specs/2026-08-10-eds-qd-stage-guidance-transition-design.md` | **明确受保护；本次未读取其内容、未修改或暂存。** W5 的同名已提交设计独立审查，不能混淆两份文件 |

此外，`stash@{0}` = `c15327572eba1046b381c4b56ef8a79e32bfcb76`，2026-04-28，基于 `feat/rdt-integration@b02e248`；统计涉及 `configs/policy.yaml`、LIBERO adapter、`main.py`、requirements 和旧 `test/pi05_loading.py` 共 5 个文件。本次只核对元数据/变更统计，未 apply/pop；是否存在仍有价值的未整合内容待专项比对，不得自动恢复覆盖当前代码。

### 2.3 子模块、非 Git 副本与工作区隐患

顶层 HEAD 真正的 gitlink 只有 `calvin`、`lerobot`、`rdt` 三项；`.gitmodules` 还列出 SAM3/LIBERO-PRO，但不能据此认定这些依赖都由 Git 固定或已初始化。

| 工作树组 | CALVIN | LeRobot | RDT |
| --- | --- | --- | --- |
| W0 | 未初始化 `13ec2d33…` | 已初始化 `715debf6…` | 已初始化 `b896f4dc…` |
| W1 | 无上述 gitlink 状态条目 | 同左 | 同左 |
| W2 | 未初始化 `13ec2d33…` | 未初始化 `715debf6…` | 未初始化 `b896f4dc…` |
| W3/W4/W5/W6/W10 | 未初始化 `13ec2d33…` | 未初始化 `715debf6…` | 已初始化 `b896f4dc…` |
| W7 | 未初始化 `de70e956…` | 未初始化 `715debf6…` | 已初始化旧 pin `cd79363a…` |
| W8/W9 | 未初始化 `de70e956…` | 已初始化 `715debf6…` | 已初始化 `b896f4dc…` |

已初始化的 RDT/LeRobot 子模块本次均 clean。**但 W10 的 `third_party/libero_pro` 是独立嵌套 Git 仓库**，HEAD `eafdb809426b`：有 1 个未暂存 tracked 修改 `libero_ood/ood_object.yaml`，以及 6 类 perturbation 的 BDDL/init 共 12 个未跟踪目录。顶层 clean 不会充分反映这项依赖状态。

W3/W4/W5/W6 有实际 LIBERO-PRO 文件副本，但未发现各自 `.git` 标记；W0 的 `third_party/libero_pro`、`third_party/libero`、`third_party/sam3` 均不存在。重建环境须采用各实验 manifest 的输入 fingerprint，而不是仅 `git submodule update` 或任意新版 LIBERO-PRO。

### 2.4 继承与整合关系

```text
早期 RDT integration（共享祖先 fc41b9d）
  └─ object-ckpt 1be4afb ── merge 5c11136 ──> GT reintegration 73b90c6
       GT 成果择取/整理 -> chore 25e98a8 ==tree== main 689f487
                                             └─ main d51cb85
                                                 └─ EDS 2628fab == FPS HEAD
                                                     └─ PG/P2 b3db98c
                                                         └─ QD 5b0898e
                                                             ├─ autoresearch 744e08b
                                                             └─ budget sweep beb8d3f
                                                                 └─ Stage/FSM 4b3ed17
debug c528347 从更早的 16aa782 分叉，独立保留。
```

实际祖先计数：EDS→PG 26 个提交，PG→QD 当前 18 个，QD 当前→FSM 2 个；QD 与 autoresearch 的 merge-base 为 `5b0898e`，两侧分别独有 3/112 个提交。autoresearch **没有继承**后来的预算 sweep/FSM 实现；读取过对方报告不等于合并代码。

旧归档中的目录别名 `rdt-maniskill-ckpt-libero-integration`、`rdt-libero-dataset_finetune`、`rdt-libero-gt-rollout-integration` 对应当前 W7/W9/W8。它们不是新增的三个活跃 worktree；定位依据是[整合索引][RINDEX]的 branch/commit，而非旧绝对路径。

<a id="history"></a>
## 3. 开发历史时间线

| 阶段 | 目标与问题 → 实现/变更 → 验证与决策 → 后续影响 |
| --- | --- |
| 04-19～04-22：平台起点 | `1e72702` 初始提交，`26289e3` VLS baseline；建立多 policy、关键点 guidance、diversity/FKD 路径。README 的上游论文表述与本地结果分开。W7 中 04-28 的 10/10 配置实际 `policy.type=pi05`，说明不能按工作树名字判断使用模型 |
| 04-22～05 月：RDT/ManiSkill 接入 | RDT wrapper 和配置接入（如 `6cb0590`）；多轮检查 observation/image/FK/action slots。早期 RDT 多为 0/10，保留 round-1～4 审计。错误 embodiment/action 语义不能通过“shape 正确”排除 |
| 05-20～05-26：LIBERO 微调与 checkpoint 路线 | 先验证 HDF5 loader、128D state/action、单步及 10-step training；之后有 mixed-suite full-finetune 与 checkpoint-60000/72000/98000 的历史记录。最后 98000 部署仍 0/10。[GT 差异分析][GTDIFF]发现训练 state/action target 与成功参考实现不同；低 loss 不证明 rollout 语义正确。当前 `/mnt/data/rdt_checkpoints` 不存在，不能承诺恢复旧训练 |
| 05-26：GT rollout 重整 | 将 observation 改为 raw 图像、7 joints + 2 gripper qpos，动作解码切到 GT slots；保持单次 online observation，修复 reset/init state、图像历史、checkpoint/语言输入 fail-fast。`62196b2`、`774632c`、`0173b50` 等形成新 contract；W9 通过 `5c11136` 合入 W8。RDT unguided 在 base Object 达到 9/10 |
| 06-02～06-04：RDT+VLS 与主线整合 | keypoint guidance、RBF diversity、FKD、最终粒子选择（`9832f8e`、`dede1a8`、`2f80586`、`727180e`）。VLS sweep 未达到同轮 unguided 9/10 gate；随后择取为 `25e98a8`，以 tree-identical `689f487` 进入 main。`d51cb85` 接受 numeric no-op reward，解决一类 generated guidance 返回 int/float 的错误 |
| 06-06～06-20；07-01 汇总：EDS 集成与 OOD | grouped config、EDS 路由、population/resample/renoise/rollout/counters（如 `253cbf9`）。早期 06-06 报告 EDS 8/10；06-11 独立 Level3 为 p32_c20 8/10、p16_c10 6/10，不能混同。06-20 完成正确 checkpoint 的 Object 六类 perturbation；Swap 的 RDT/EDS 均 0/10，促使研究聚焦难 OOD。此前 cross-suite 错 checkpoint 队列不再用于算法否证 |
| 07-04～07-14：初始化与 rollout RBF | FPS 停留设计；实际推进的是 PG/RBF 初始分散、truncated-rollout RBF 和 trace。单 task/3-episode smoke 的收益未迁移到完整 Swap：257-job sweep 中 256 有效，只有 3 配置各 1/10，另 1 配置视频不足无效。07-14 早间 handoff 的“正在运行”被当日后续报告取代 |
| 07-31～08-06：P2 及后继对照 | 720-step Stage ablation：P2 OFF 0/10→ON 3/10；Stage 过早 OFF 使机制更像短 EDS 前缀后回到 RDT prior。Adaptive Stage A 的 10 个新组件配置、clean-tail、Direction-RBF 均未超过各自 contemporaneous control；Stage B 因无 eligible component 合法不运行。`b3db98c` 冻结 P2 基线 |
| 08-06～08-08：QD 与预算 sweep | `3b55c1e` 引入 config-controlled QD。首轮 11 jobs、110 formal 记录：对照 3/10，最好 QD 2/10；Grid5 bookkeeping 异常使该格无效。`5b0898e` 冻结报告。后续 18-job population×iterations sweep 全部低于 5/10，出现 201/200 physical attempts 的披露例外；`beb8d3f` 保留该例外，而非伪写预算 PASS |
| 08-10：独立物理 Stage/FSM | 从 `beb8d3f` 另建 W5；protocol `4b8165c` 先于实现 `4b3ed17`。使用 p48_k20 uniform_expand20 固定算法做两轮 paired legacy/FSM；FSM 0/20，部分 jobs qpos/审计失败，结论 keep legacy。不是 W4 的 QD-core candidate |
| 08-10～08-12：autoresearch | 冻结方案 `1aee76489ea8989a832dec49b747239f2db90981`；state 记录 approved/executing 于 08-10 15:00:35。依次做 H1 bounds、H2 degenerate fallback、H4 quality anchor、H5 top2/protected lane；H1 到 validation，后续在机制或 Dev 阶段停止。多次 infrastructure/预算/用户恢复后，Run045 protocol `a806ce1` → 结论 manifest/报告 → results commit `744e08b`，目标未达、无新 formal |

<a id="implementation"></a>
## 4. 核心功能与算法进度

### 4.1 代码地图

| 功能 | 实现与启用入口 | 当前完成程度 / 不应推导的结论 |
| --- | --- | --- |
| 调度、episode、Stage、记录 | [main.py](main.py)、[LIBERO adapter](core/env_adapters/libero_adapter.py)、[配置](configs/config.yaml) | 主线可选 RDT/PI05，后期各树 `main.py`/配置有所分化；没有全局统一的最新执行入口 |
| RDT GT observation/action | [obs processor](core/rdt_libero_obs_processor.py)、[action converter](core/rdt_libero_action_converter.py)、[observation sampling](core/policy_observation_sampling.py) | 已整合 main。state indices `[0..6,10,11]`，action indices `[39..44,10]`，raw gripper 按符号输出；旧 `[30..35,10]`/FK 转换文档不是当前 contract |
| RDT/VLS、PI05/VLS、Diffusion | [RDT steer](core/rdt_policy_steer.py)、[PI05 steer](core/pi05_steer.py)、[diffusion steer](core/diffusion_policy_steer.py)、[FKD](core/fkd_class.py) | RDT 为 128D/64-step prediction，默认执行前 8 actions，20 Hz。VLS 可运行但未证明普遍胜过 unguided |
| EDS 主循环 | [W10 RDT steer](.worktrees/feat/rdt_ed_steering_integration/core/rdt_policy_steer.py)，`main.use_guidance=true` + `main.guidance_type=eds` | 已实现路由、score/resample/renoise/rollout、cache 与 counters，未合 main；实际 EDS 必须用 metrics 验证，不只看配置 |
| RBF/P2、adaptive ESS、resampling、memory、schedule | [W3 RDT steer](.worktrees/exp/eds-init-pg-diverse-sampling/core/rdt_policy_steer.py)、[runner](.worktrees/exp/eds-init-pg-diverse-sampling/scripts/rdt_eds_eval_runner.py) | 都已有 config-controlled 实现；P2 保留作对照，其余未获 adoption。`initial_sampling_mode=rbf_diverse_denoise`、`truncated_rollout_mode=rbf_diverse` 不等于 FPS |
| QD archive/search | [W6 qd_ed.py](.worktrees/exp/eds-quality-diversity/core/qd_ed.py)、[首轮 runner](.worktrees/exp/eds-quality-diversity/scripts/eds_quality_diversity_runner.py)、[audit](.worktrees/exp/eds-quality-diversity/scripts/eds_quality_diversity_audit.py) | `qd_archive_mode=grid_archive`；target-relative endpoint XY，cell elite，uniform/sparse parents，stable fingerprint ties。实现/回放成功，task/claim gate 未通过 |
| autoresearch QD 后继 | [W4 qd_ed.py](.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/core/qd_ed.py)、[W4 RDT steer](.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/core/rdt_policy_steer.py)、[W4 config](.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/configs/config.yaml) | H1 `qd_bounds_update_policy=causal_envelope_v1`；H4 `qd_global_quality_anchor_count=1`；H5 `qd_secondary_lane_mode=protected_reward_v1`。H2 有独立 fallback 开关。保留实现，不建议因 proxy 活跃就启用 |
| Stage/FSM | [FSM core](.worktrees/exp/eds-qd-stage-guidance-transition/core/stage_guidance_fsm.py)、[FSM runner](.worktrees/exp/eds-qd-stage-guidance-transition/scripts/eds_qd_stage_guidance_transition_runner.py) | `main.stage_transition_mode=physical_fsm_v1`；默认 `legacy_vlm`。六状态、迟滞、drop recovery、切换时废弃旧 chunk 已实现；只有该分支有完整路径，在线未获采用 |
| 观测与证据 | [W4 metrics](.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/core/eds_eval_metrics.py)、[trace](.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/core/eds_mechanism_trace.py)、各 runner/audit | `eds_eval/eds_metrics.jsonl`、`episode_metadata.jsonl`、`stage_events.jsonl`、qualitative、`.hydra` 和 manifest 是交叉核对入口；不要只解析 results.txt |

W4 当前默认仍是 `use_guidance=false`、`guidance_type=vls`、EDS `iid`/baseline rollout、`qd_archive_mode=none`、`qd_secondary_lane_mode=none`、anchor=0、fixed bounds。**直接运行默认 `main.py` 不会启动 P2 或 QD。**

历史 Grid5 的错误来自 archive final selection 与旧 particle-source bookkeeping 不一致。后续代码含 QD-aware source 处理，但不能把旧 Grid5 的 0/10 修饰成有效消融，也不能仅因修复已存在就宣称该配置重新验证通过。

### 4.2 验证证据的层次

| 证据 | 能证明什么 | 不能证明什么 |
| --- | --- | --- |
| 05-23 loader/compat 单测 10 passed；1/10 training-step smoke | 当时数据、训练、保存路径接通 | full training 收敛、GT 语义等价、rollout 成功 |
| EDS 06-06 报告 78 个 RDT tests；06-11 counters/finite/selected-best 审计 | EDS 路由和统计语义有验证记录 | reward 是成功的主要原因 |
| Clean-tail 报告 749 passed | 当时 runner、机制、Stage、I/O 回归通过 | 当日环境能逐包复现、clean-tail 有收益 |
| QD baseline 08-08 记录 56 passed | archive/runner/audit 目标测试 | 所有配置 validity 或全部软件测试都通过 |
| FSM [test_evidence.json][STEST]：`4b3ed17` 上 987 passed | 已保存的完整 `tests` 执行记录、py_compile 与 diff 检查成功 | online safety PASS；实际 3/4 jobs 未过完整 gate |
| Run042/043 总账：408/424 个相关回归通过 | protected lane 的默认等价、分配、rebin、固定 176/176/11 accounting 有 CPU 证据 | 0/2 在线机制结果可推广，或候选已采用 |

以上均为历史执行证据；**本次没有重新运行测试、模型、训练或评估**，不能称为本次 CI 验证通过。

<a id="experiments"></a>
## 5. 实验结果、可比性与经验

### 5.1 先固定口径

当前多数后期 Swap 实验共用：RDT `/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object` EMA；8-action execution chunk、20 Hz；`libero_object_swap`、strict perturbations；tasks `0..9` 各 1 episode；720-step 上限；Stage ON、Gemini grounding OFF、历史 guidance cache。常用 root seed=0，对应 episode seeds：

```text
task:  0    1    2    3    4   5    6    7   8    9
seed: 44  235   43  546    6 621  197   87 151  548
```

P2 的主要参数：population=16、iterations=10、use_cem=false、temperature=0.1；initial RBF scale=20/start=0.8；rollout renoise 3→1、RBF scale=20/start=0.6/iters=all；absolute EEF descriptor、fixed horizon、QD OFF。完整启用项以对应 runner profile 与 resolved config 为准，尤其不能漏掉 Stage/cache/suite 设置。

以下几种口径不合并排名：

1. base `libero_object`、其他 suite、PI05 和 RDT 是不同基线。
2. 240-step Stage OFF 与 720-step Stage ON 有多个变化；跨轮不同缓存/API/设备时序也不保证等价。
3. 单 task 的 3 次 rollout不是 3 个 tasks；mechanism `0/2`、Dev `0/6`、validation `1/10` 不是 formal `0/10`。
4. 历史文件中的 `formal` 往往表示完整工程矩阵，并非独立 holdout；反复使用这 10 个 seeds 的 sweep 有选择偏差。autoresearch 明确把旧 formal 降格为 reuse-limited acceptance set。
5. valid outcome、safety、mechanism hard/claim、adoption 分开看；保留 deployment failures 在分母，不事后删掉失败。不同协议的 validity 定义有差别。
6. 小样本、重复 task/seed 和不同随机数消耗使置信区间/因果解释有限；同 seed 不等于逐 action 反事实配对。QD 报告的 Wilson 区间只是有限样本描述，不证明显著差异。

### 5.2 主要实验总览

表中的原始核对包括 results.txt、结构化 audit/manifest、task metadata 或视频文件清单；未在本次逐帧重看所有视频。视觉失败解释注明为报告观察，不能升级成已证实的因果机制。

| 实验 / 时间 | 条件、规模与结果 | 有效性、结论与证据 |
| --- | --- | --- |
| 早期 RDT integration / 04–05 月 | W7 13 份 results：12×0/10；另 10/10 的 04-28 run 是 PI05 unguided、base Object、root seed0 | 0/10 属旧接入路径。原始：W7 `outputs/libero/`，10/10 配置在 `2026-04-28_17-17-50/.hydra/config.yaml`；不可错认 RDT 最优 |
| 本地微调 checkpoint / 05-26 | 历史 checkpoint-98000 EMA、base Object、10 episodes，0/10 | GT 语义分析指出不同训练 contract；报告保留完整路径，但权重根目录本次不存在。见[失败总结][RFAIL]、[训练证据][RFINE] |
| GT RDT / 06-04 主目录实测 | base Object，EMA，root seed0，backend 上限720，unguided 9/10 | 本次核对[原始 results](outputs/libero/2026-06-04_12-47-05/results.txt)和 `.hydra/config.yaml`；可作 I/O 恢复参考，不是 Swap |
| RDT VLS sweep / 06-03 | base Object，10 episodes；diversity=1、sample batch20、guide20 配置报告 7/10，对照9/10；其余不同完整 ablation 3–6/10 | 未过同轮9/10 gate；有 generated guidance numeric-return 错误混入部分 jobs。7/10 的 results 文件仍存在，旧报告后续“最好6/10”概括不完整。见[VLS 证据][RVLS] |
| EDS 初期 / 06-06 | base Object、240steps、Stage/grounding OFF，报告 p16_c10 8/10、VLS4/10、unguided9/10、zero-reward7/10；EDS约745s/10ep | 该报告引用的 `outputs/formal_eds_10_p16_c10_poe_20260606_124847` 本次未找到，独立episode seed mapping待核实；仅作历史 reported evidence，不取代下行可核对结果。见[早期 EDS 报告][EINITIAL] |
| EDS Level3 / 06-11 | base Object、240 steps、Stage/grounding ON；9 个配置各10 episodes。p16_c10/p16_c20/p32_c10各6/10；p32_c20=8/10；CEM7/10；zero/shuffled6/10、inverted3/10；unguided9/10 | 本次核对 p32_c20 原始 results；counters/finite/selected-best 历史审计通过，收益不足以证明 reward 主导。p32_c20约31.9min、mean select9.855s。见[Level3][ELEVEL3] |
| Object 六种 OOD / 06-20 | 每方法每suite10 episodes、240-step 系列。Swap：RDT unguided/EDS softmax/EDS CEM/RDT VLS均0/10；PI05 unguided0/10、PI05 VLS4/10 | 完成正确 checkpoint 的 Object perturbation；PI05 4/10 原始结果仍存在，但它不是 EDS-QD 成绩。其余 suites 见 5.3、[RDT/EDS报告][ELEVEL4]与[VLS/PI05报告][EPI05] |
| RBF initial/rollout / 07-09～11 | base Object task0，每job3 episodes；aggressive initial s20/start0.8出现1/3。rollout Level3共128 jobs完成 | 机制/小样本探索，不作完整 Object 或 Swap 成功率。报告 execution pass、effectiveness inconclusive，见[单 task rollout sweep][PROLL] |
| Swap RBF sweep / 07-12～14 | initial s20/start0.8；240-step、缓存、Stage OFF；1 initial-only +256 rollout配置，各10 episodes | 表格程序汇总：253有效0/10、3有效1/10、1无效1/10（9/10视频）；无新同轮 unguided 对照。257 jobs并不等于2570个有效结果。见[Swap sweep][PSWAP] |
| 720-step Stage ablation / 07-31～08-01 | P1 OFF/ON=1/10→1/10；P2 OFF/ON=0/10→3/10，40ep；共同 seeds如5.1 | P2 gained `{3,8,9}`；P1 lost3/gained1。按该协议四组valid，P2 OFF仍有2个qpos失败计入分母。报告观察到 P2全10tasks在step16–32先关闭guidance，不能解释为可靠抓牢确认。见[Stage ablation][PSTAGE] |
| P2 Adaptive Stage A / 08-02 | 11 profiles ×10ep、720step。control3/10；k2/e1为2/10（`{0,4}`）；两个schedule各1/10；其余7个新配置0/10 | 全11通过该轮validity；2个qpos失败、Stage query419/1890错误保留。0个组件eligible，Stage B=0 jobs不是漏跑。见[Stage A][PSTAGEA]、[P2总报告][PFINAL] |
| P2 clean-tail / 08-03～04 | 12参数+1baseline+1派生clean-tail，共140ep。baseline3/10；Phase A winner2/10 `{8,9}`；Phase B0/10 | skip-final确实生效，但丢失winner2个成功、方向覆盖大幅收缩；无adoption。原旧shared2路径已迁移。见[报告][PCLEAN]、[Phase B audit][PCLEANA] |
| Direction-normalized RBF / 08-04～05 | 11完整配置；同轮恢复control4/10 `{3,5,6,7}`；primary1/10 `{2}`；最好新配置W2/E025=3/10 `{6,8,9}` | 原始 structured audit确认11eligible；task/mechanism/safety总gate FAIL。winner gained8/9、lost3/5/7，net−1；native EGL故障同identity恢复不能当新算法成功。见[报告][PDIR]、[审计][PDIRA] |
| 首轮 QD / 08-06～07 | 1P2+10QD，每job10ep，720step，P16/K10。control3/10；sparse与uniform_expand20各2/10；uniform primary0/10 | 110 formal记录完成不等于110个可用于机制结论的有效episode；Grid5全格无效，q1090另有安全失败。全部无adoption。见[QD报告][QREPORT]、[结构化审计][QAUDIT] |
| QD search-budget sweep / 08-08 | 2 families ×P{32,48,64}×K{15,20,25}=18job/180ep；每配置0或1/10，无5/10 | 17/18 safety PASS，所有task gate FAIL；无同轮P16 control。每chunk512–1664 eval、selection P95约6.7–20.4s；更大预算没有在此矩阵产生达标配置。physical201/200预算FAIL被明确披露。见[报告][QBREPORT]、[audit][QBAUDIT] |
| QD Stage/FSM / 08-10 | 固定uniform_expand20 P48/K20；root seeds0/1两轮各legacy/FSM，40ep。r0：0/10→0/10；r1：1/10→0/10（lost7） | FSM观测总数0/20，但不能当作20个全部通过safety/validity的有效研究结果。legacy_r0仅一格全valid；两个FSM格各1个qpos错误，r1另有QD/safety审计失败。见[报告][SREPORT]、[audit][SAUDIT] |

### 5.3 历史 OOD 的横向背景（仅同一历史系列）

06-20 Level4 报告的每格为 10 episodes 成功数；RDT-EDS 两种配置都为 P32/K20、renoise3→1，softmax 与 CEM elite选择不同。PI05使用 `lerobot/pi05_libero_finetuned_v044`；不得用模型间差异归因 QD。

| Suite 后缀 | RDT unguided | EDS softmax | EDS CEM | RDT VLS | PI05 unguided | PI05 VLS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| object | 6 | 3 | 5 | 1 | 10 | 7 |
| swap | 0 | 0 | 0 | 0 | 0 | 4 |
| lan | 3 | 6 | 6 | 2 | 10 | 8 |
| task | 0 | 0 | 0 | 0 | 1 | 3 |
| env | 0 | 1 | 1 | 1 | 5 | 5 |
| temp | 0 | 0 | 0 | 1 | 6 | 4 |

来源：[RDT/EDS Level4][ELEVEL4]、[VLS/PI05 Level4][EPI05]。当轮 `temp` 按 active config 实际是 environment-style temp generation，不是所有 perturbations 混合。早期 `libero_10/goal/spatial` 0/10/timeout队列被后续报告认定涉及 wrong checkpoint，不应用于否定正确 Object-checkpoint EDS 路径。

### 5.4 QD 与 autoresearch 的关键 task-level 对照

首轮 QD 的原始 results、完整 audit 与报告一致：

| 方法 | 成功tasks | 相对P2 `{3,8,9}` 的 gained / lost | 解释 |
| --- | --- | --- | --- |
| P2 control | `{3,8,9}` | — | 3/10，对照，不是QD |
| uniform primary | `{}` | `{}` / `{3,8,9}` | 0/10 |
| sparse primary | `{5,8}` | `{5}` / `{3,9}` | 2/10，净−1 |
| uniform expand20 | `{5,7}` | `{5,7}` / `{3,8,9}` | 2/10，净−1 |

首轮每完整chunk 176 evaluations；archive median coverage几乎全1.0、overflow P95约0.938–1.0，paired coverage gain为0。**coverage饱和不是有效行为覆盖改善**。选择延迟P95：control2.577s、sparse5.364s、expand20 2.701s；不同GPU运行条件限制严格时间归因。

autoresearch 的确执行了多轮，但正式目标没有被验证达成：

| 假设 / run | 冻结评估与结果 | 机制、停止决定与局限 |
| --- | --- | --- |
| H1 causal-envelope / Run002→010 | Dev-A control0/4、candidate1/4（gain9）；Dev-B 0/4→2/4（gain5/8）；validation 0/10→1/10（gain0） | envelope降低overflow到0并改善resolution；validation低于5/10，结束H1、不进formal。validation GPU约1.747368h；[Run010 analysis][A10]与[原始audit][A10J]均可核对 |
| H2 exact-degenerate fallback / Run020→023 | tasks `{2,3,9}`，同轮control1/3（task9）、candidate0/3，lost9 | 历史zero-reward chunks支持诊断，但online74个candidate chunks无fallback，dual-mode gate失败；不能声称fallback触发后损害任务，因为它没有触发。该run约0.812334GPUh；[Run023][A23] |
| H3 continuity/memory | state标记 `deprioritized_by_counterevidence` | 有历史反证和降优先级记录，但**不是已经完成独立H3在线消融**；不存在“五个方向都被逐一完整测试否定”的证据 |
| H4 global-quality anchor / Run030→033→034 | mechanism control0/3→candidate1/3（gain9）；Dev-A tasks`{0,1,2,4,6,7}`两边0/6 | anchor修复parent omission：Dev106records、1060 activations、425rescues；未产生completion，低于3/6且无+1，终止v3；Dev约1.263960GPUh。[Run034][A34] |
| H5-v4 within-cell top2 / Run040 | offline：24traces、264candidate streams、4224candidates；65.10%有同cell碰撞，counterfactual出现17个quality-retention违规 | 在实现/online之前拒绝naive top2；这是counterfactual否证，不是online task outcome |
| H5-v5 protected quality lane / Run041–044 | CPU机制通过；online有效pairs `(task5,666847)`、`(task7,87603)`，control0/2、candidate0/2，无gain/loss | 41candidate records，1685secondary parents，407/410迭代positive；3迭代0secondary导致预注册universal-activation FAIL。latency ratio1.045684；未进Dev-A/validation/formal。[Run044 analysis][A44]、[audit][A44J] |
| Run045 | 无新experiment，只写结论与manifest | no-adoption，目标未达；保留对照。不能把该决策解释为证明整个EDS+QD空间没有可行改进 |

H1 Dev tasks `{3,5,8,9}`；Dev-A seeds `[512905,150741,463456,452903]`，Dev-B `[558482,165717,160148,160312]`。H1 validation tasks0..9的seeds为 `[41678,829779,856474,666150,876784,652882,288157,522484,262295,200894]`，不是历史formal seeds。v2/v3/v4/v5分别另有fresh split，确切mapping以各 `experiments/run_*/protocol*.md` 与manifest为准，不根据段落中的task顺序重新zip种子。

Run023的task→seed为`2→932032、3→615132、9→718536`；Run033为`3→955865、8→522754、9→845886`；Run034按tasks`[0,1,2,4,6,7]`使用`[307995,262892,731741,14859,648306,960581]`。这些结果均不能与5.1的旧formal cells直接配对。

独立FSM第二轮seeds为第一轮逐项加1000，即 `[1044,1235,1043,1546,1006,1621,1197,1087,1151,1548]`。该设计mean gate为至少10/20且两轮valid、safety/机制通过；不是把某一轮的单个成功当作通过5/10目标。

H5v5只有3条task7的EDS metrics不意味着episode在step16结束：本次查看stage events仍有task7后续到step712的记录；guidance关闭后可能没有EDS metrics。所有 `timeout without completion` 在这些审计中是粗粒度、非因果标签，不能单凭它断言没有抓住、物体错误或API崩溃。

### 5.5 暂停、预算与 promotion 决策审计

| 决策域 | 规则及触发证据 | 当前应如何处理 |
| --- | --- | --- |
| 06-10旧OOD队列 | [暂停根因笔记][EPAUSE]：timeout/failed曾被自动claim，出现重复8h超时；后改为只claim pending | 旧paused/failed不是应自动补跑的任务；且该组wrong-checkpoint结果不再具算法解释资格 |
| P2 Stage B | [总报告][PFINAL]及integration manifest：所有Stage A组件不eligible | 0job是合法收束，不把空CSV当调度故障 |
| 初始QD | 110formal +6preflight +18recovery =134 attempts；audit另记18pre-episode aborted | 同一ledger不同类别不能相加当有效episodes；Grid5异常结果保留但不排名 |
| QD预算sweep | accepted180/180；physical201、ledger reserved200、cap200；`hard_cap_passed=false` | soft override/timeout exception已披露，不能称“所有硬门通过”；例外只属于这轮，不延伸授权至其他研究 |
| autoresearch基础协议 | [冻结方案][ADESIGN]§17/20：每5有效实验或连续3次无进展触发outer-loop；连续2 cycles无gap改善且无task-linked依据时收束或versioned redesign；143attempt、48GPUh初始上限 | 中间candidate stop与整个目标完成不同；v3结束后确有用户继续与v4设计，不可把旧v3“无第四候选”当作后来v4非法或当前未完成实验 |
| Run044 identity incident | 原IDs91–94因backend排序把task/seed交叉，全部invalid；repair protocol `5f94fd4`→实现`fd1a5f3`；恢复需4cells而本版reserve只剩3 | 用户特批额外1个reservation，cap143→144，仅用于第4恢复cell；`5da58a0` protocol→`c071a76` runner→IDs95–98；不能推广为无限恢复权限 |
| 最终Run044/045 | v5版本禁止第六candidate的条件边界；Run044无task gain且universal gate FAIL；Run045把v4/v5归为连续无task gain cycles | 最终manifest98/144、6.946832/48GPUh，**并非全局预算耗尽**。这是当前已登记的研究收束；没有新授权前不运行Dev/formal或放宽gate |

基础方案还写明机制解释不应凌驾于有效真实task success；v5却设置逐迭代positive-secondary硬门。该设计选择需要下轮事前审查其必要性，不能事后删除失败门。当前0/2本就没有达成task目标，但它也不足以独立证明“reward/progress alignment是唯一剩余瓶颈”。最终报告的这一归因应视为研究解释，而非排他性因果结论。

### 5.6 可复用经验

- **先验证语义再比较算法。** GT state/action slots、reset/init、image history和checkpoint必须一致；早期微调低loss+0/10就是反例。
- **P2是真实但脆弱的对照。** 在多轮固定seeds下出现3/10，另一轮恢复control4/10且成功task换组；跨轮API/缓存/恢复条件足以限制直接归因，不能把“最好数字”当稳定总体性能。
- **现有分散机制能改变轨迹，不保证保住成功mode。** RBF、k-center、QD、anchor/secondary均有激活证据；成功集合的gain/loss比单一coverage值更有用。
- **不建议重复原样大扫。** 257-job RBF、18-job大QD预算、clean-tail和Direction-RBF已有明确负/有限结果。若重试，须有不同可证伪预测和独立批准，不沿旧formal结果选参数。
- **仍值得验证的是假设，不是既定结论。** reward-to-progress对齐、有效mode保留、continuity以及Stage影响有证据动机；不能以此直接授权超出QD scope的perception/Stage/模型修改。

<a id="risks"></a>
## 6. 未完成事项、矛盾与交接风险

### 6.1 必须显式解决的文档/状态冲突

| 编号 | 冲突或缺口 | 本次采用的依据 / 解阻条件 |
| --- | --- | --- |
| R1 | autoresearch最终报告称无candidate进入validation，但同文表格及Run010记1/10 validation | 采用Run010 immutable audit与其任务表；不改原报告。本次核对SHA通过，见9.2；未来经授权修正文案并保留变更原因 |
| R2 | “五个方向均覆盖”容易误读为全部实测淘汰；H3实际上deprioritized | 以 `research-state.yaml` 的H3状态和run清单为准；区分反证降优先级、offline拒绝、online否证 |
| R3 | state root已concluded，H5条目仍写online_pending；`experiments.active_experiment.decision`出现3次 | YAML AST本次检出decision行310/359/413重名；宽松loader可能静默覆盖。恢复前需schema/duplicate-key硬检查及状态归一；本次不修复 |
| R4 | `data/experiment-trajectory.jsonl`有46行但最后停Run042 implementation protocol；state total_runs=17，research-log达88条 | 这些是不同粒度且部分滞后，不能都当“迭代总数”。最近终局用总账BW、Run045manifest和HEAD；继续前补齐机器索引需独立修改授权 |
| R5 | W3的`rdt_eds_eval_status.csv`当前只有4个Stage ablation pending；旧07-14 handoff还写204done/4running/48pending | 现有Stage/Swap报告和对应产物已完成；不从该CSV重新初始化/覆盖旧输出。W3 `rdt_eds_final_evaluation_report.md`也停07-14模板、漏后期P2结果 |
| R6 | 06-11 Level0–3 checkpoint文档称Level4 pending；06-20两份Level4已完成 | 按较后执行证据判断该Object OOD系列完成，保留旧文档的阶段快照语义 |
| R7 | 旧RDT/VLS参数来源写最好6/10，06-03详细表有7/10 | 7/10原始results路径仍在；选择sbs50=6/10可能有映射考虑，但不能说没有7/10。不同key/start-step映射限制比较 |
| R8 | `HANDOFF`/报告绝对worktree路径沿旧别名；clean-tail报告写旧shared2 root | 改导航而不改旧证据：实际W7/W9/W8以及新clean-tail root见7.2。旧path缺失不自动等于数据丢失 |
| R9 | `complete`与`valid`混用风险：首轮QD110完成含Grid5无效；FSM40完成含3invalid；预算sweep hard cap FAIL | 同时引用completion、job validity、safety、attempt ledger，不只读final SR或“PASS”标题 |
| R10 | 最终报告推断“剩下是reward alignment”，或将0/2视为机制空间耗尽 | 仅支持当前小矩阵无任务收益、某gate失败；需要更强证据才能排除其他因素。没有视频逐帧复核或反事实实验时标为待验证解释 |
| R11 | Run044恢复ledger的`recovery_of_attempt_id`按位置关联：95→91、96→92、97→93、98→94，但旧记录task顺序7/5，新记录5/7；四条指向的旧frozen identity均不相同 | 本次读取[原始ledger][A44L]并对照runner约1005行确认。按profile/task/seed应对应95→92、96→91、97→94、98→93。实际恢复metadata的task/seed正确，不改变两边0/2观测；但说明audit PASS未覆盖恢复血缘一致性，不能笼统声称所有provenance无缺陷。未来应追加erratum/一致性检查，不覆盖immutable原账 |

### 6.2 工程与证据保存风险

- **主线落后于实验线。** EDS及后续代码未整合；大规模直接merge可能带入旧实验默认值、绝对路径和audit脚本。须先做功能级采用清单与回归范围，不把172个分支独有提交全当生产改进。
- **环境不由仓库充分锁定。** RDT training用`rdt`环境，online用`vla-pilot`；05月曾发生依赖污染/回滚，缺少可证明逐包复现的lock。主目录缺LIBERO-PRO，实验树含副本/嵌套未提交依赖；确认当前安装路径、dependency pin和input hash后才可运行。
- **EGL/CUDA映射不能照抄。** 历史不同批次记录不同physical→EGL映射，并有local robosuite补丁、libnvidia-eglcore native abort和Xid31/109报告。相同device数字不足以确定同一渲染设备；解除条件是新admission/映射验证及环境审查，而不是反复重试。
- **旧模型与训练恢复缺口。** 当前RDT Object EMA/T5/SigLIP缓存存在；旧`/mnt/data/rdt_checkpoints`缺失，checkpoint cleanup manifest只是当时建议，不证明执行删除或备份存在。缺少旧权重时只能保留reported训练结论，不能声称可恢复98k训练。
- **存储不能沿用旧余量。** 本次`df -h`：根文件系统约30GiB可用、93%占用；shared2约246GiB可用、99%占用。旧文档“4.7TiB空闲”已失效。新产物需要独占namespace、容量预算和备份策略，不能因本次审查擅自清理。
- **raw evidence与报告有局部缺口。** 06-06特定formal目录缺失，部分旧文档路径失效，PG status CSV被后续矩阵替换；目前不能逐个证明所有历史实验完整复现。关键后期审计仍在，但庞大JSON（QD约22MB、预算sweep约102MB、FSM约55MB）和视频不应当作普通Git内容。
- **凭据不属于交接文件。** 仅保留`OPENAI_API_KEY`/`GOOGLE_API_KEY`等配置入口；本次未读取`.env`、shell历史、会话凭据或进程environ，未测试API可用性。接手者通过批准的运行时secret配置方式提供凭据，不放命令行、Hydra、Git或报告。

### 6.3 当前运行任务

本次只读取进程名、PID、可访问的cwd与GPU进程表，未打印完整cmdline/environ，未停止任何进程。未发现可核实为上述worktree内正在执行的研究runner/rollout；根目录有shell、语言服务/编辑器代理等进程，不能当成研究调度器。对不可访问cwd或在其他位置启动的进程，不作“绝对不存在”的断言。

GPU0–7均有compute使用，观察时utilization约96–100%。例如PID1522797/1522798占GPU0/1，1525037/1525038占2/3，2835849/2835850占4/5，2298802/2298803占6/7；还有2295989、2325166跨设备使用。这些是外部/未归属本研究的进程，**不得抢占或终止**；数字只作当时快照，不用于后续进程操作。继续运行须等待资源满足对应协议admission。

<a id="operations"></a>
## 7. 接手操作指南

### 7.1 建议阅读与最小核对顺序

1. 在W4确认branch/HEAD和U4仍未动；读[最终总账][ALEDGER]末尾、[Run045manifest][A45M]、[冻结方案][ADESIGN]与[v5设计][AV5]。先理解“研究结束、目标未达”，不要点击任何resume即运行。
2. 对照本文件R1–R5，人工确认Run010 validation确实存在、Run044只有95–98为合法恢复、state重复key和旧CSV不能作为调度输入。
3. 将W6的P2 control/sparse/expand20原始结果和audit做三方对照；再看W3的Stage A、Direction control差异。算法接手应先固定对照口径，而不是挑最好成功率。
4. 核对checkpoint、LIBERO-PRO、缓存、模型输入hash、artifact realpath和磁盘；读取当前`git submodule status`并检查非gitlink依赖。只有得到后续修改/执行范围后，才补环境或进行CPU回归。
5. 若批准继续研究，先制定新versioned protocol、泄漏安全split与预算，再创建/确认专属工作树和artifact namespace；既有formal/validation暴露范围必须保留在设计里。

### 7.2 环境、模型、数据与产物位置

| 用途 | 当前位置 / 可用性 |
| --- | --- |
| Online Python | `/home/hynx/miniconda3/envs/vla-pilot/bin/python` 存在（环境目录为Python3.12）；未在本次加载模型/验证全包兼容 |
| 旧训练Python | `/home/hynx/miniconda3/envs/rdt` 存在；历史training证据为Python3.10、Torch2.1/CUDA12.1等，不代表当前版本逐项相同 |
| RDT当前权重 | `/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object/ema/model.safetensors` 存在；checkpoint aggregate以各manifest为准，本次未重复hash数GB权重 |
| Encoder | `/mnt/data/hf_cache/hub/models--google--t5-v1_1-xxl` 与 `models--google--siglip-so400m-patch14-384` 存在 |
| LIBERO-PRO输入 | W10 `third_party/libero_pro`（嵌套repo含本地修改）；W3/W4/W5/W6对应副本；BDDL/init/ood config必须按manifest核对，不替换为任意新版 |
| 历史guidance cache | `/home/hynx/VLA-Pilot++/outputs/libero/2026-06-04_13-21-01/episode_1/vlm_agent` 存在；它是某任务cache，不能不校验身份就复制给全部tasks |
| P2 adaptive | [/mnt/data/shared2/hynx/VLA-Pilot++/eds-init-pg-diverse-sampling/outputs/ood_eval/p2_adaptive_eds_rbf][PADAPTROOT]；W3相应outputs子目录为有效symlink |
| P2 clean-tail | [/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/p2_rollout_clean_tail_sweep][PCLEANROOT] 存在；报告旧`/mnt/data/shared2/zhuoli/output/p2_rollout_clean_tail_sweep`不存在，W3当前未见该旧兼容link |
| Direction-RBF | [/mnt/data/shared2/zhuoli/output/p2_direction_normalized_rbf][PDIRROOT]；W3有主link及13个supplemental recovery links。结果须按`selected_attempts`/complete-video view选取，不盲合所有retries |
| 首轮QD | [/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity][QROOT]；W6整个outputs指向其`outputs/` |
| QD预算sweep | [QD outputs/search_budget_sweep_20260808][QBROOT]；含output_store、manifest、audit及stale恢复证据 |
| Stage/FSM | [QD outputs/stage_guidance_transition_20260810][SROOT]；W5 outputs正指向此目录，不是W4的owned root |
| autoresearch独占产物 | [/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood][AROOT]；W4 outputs指向此root；run编号不是连续episode号 |

RDT数据/模型缓存、P2/QD产物目录与Git仓库是不同保存域；复制代码或推送分支不会自动交接它们。历史HDF5训练数据曾从`/mnt/data/hf_cache/hub`读取；本次未枚举/解码全部训练数据，训练集恢复完整性待核实。

### 7.3 命令：哪些本次核验过，哪些只是后续入口

下列是本次只读调查方式对应的复核命令，个别参数整理为便于接手的形式；不表示这些整理后的命令全部按原样执行过。时间敏感输出会变化：

```bash
cd /home/hynx/VLA-Pilot++
GIT_OPTIONAL_LOCKS=0 git worktree list --porcelain
GIT_OPTIONAL_LOCKS=0 git status --short
GIT_OPTIONAL_LOCKS=0 git -C .worktrees/exp/eds-qd-autoresearch-libero-swap-ood status --short
GIT_OPTIONAL_LOCKS=0 git -C .worktrees/exp/eds-qd-autoresearch-libero-swap-ood submodule status
GIT_OPTIONAL_LOCKS=0 git log --all --decorate --oneline -30
GIT_OPTIONAL_LOCKS=0 git diff --stat 5b0898e 744e08b -- core configs scripts
readlink -f .worktrees/exp/eds-qd-autoresearch-libero-swap-ood/outputs
df -h /home/hynx/VLA-Pilot++ /mnt/data/shared2
nvidia-smi --query-gpu=index,uuid,name,memory.used,memory.total,utilization.gpu --format=csv,noheader
```

以下是**历史已执行过、但本次未重跑**的CPU验证入口，不是当前所有工作树都保证通过的命令。执行会生成测试产物，须在另行批准的工作树/验证范围内运行：

```bash
# QD目标测试：在QD或autoresearch树；08-08基线记录为56 passed
/home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -q \
  tests/test_qd_ed_archive.py tests/test_eds_quality_diversity_runner.py \
  tests/test_eds_quality_diversity_audit.py

# FSM分支历史完整测试记录：987 passed；不是其他分支的计数
/home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -q tests
```

关键在线命令的**身份与风险**：

- H1历史验证入口：`python scripts/eds_qd_autoresearch_runner.py run-validation --gpus auto --timeout-seconds 28800`，历史执行实现 `838b5550`；该split已经揭示并失败，不能再次拿来调参。
- v5修复后入口：`scripts/eds_qd_autoresearch_v5_runner.py` 包含 `run-recovery-mechanism`、`validate-recovery-manifest` 等subcommands。当前Run044已结束，95–98已消耗，不能再次执行恢复。
- PG通用runner的 `print-command --level ...` 和 `run-level --level ... --resume` 参数可从[源码](.worktrees/exp/eds-init-pg-diverse-sampling/scripts/rdt_eds_eval_runner.py)查；`p2_adaptive_eds_rbf_stage_a`是矩阵入口，`stage_b`必须有eligible immutable manifest。**不是给一个resume就继续优化的守护服务。** `write-report`/audit类命令也可能写文件，本次未运行。
- 上述命令若在不同HEAD运行，可能因fingerprint变化被合法拒绝；不要删除校验、改旧manifest或从旧日志取凭据绕过。

接手后的最小验证应先是：状态/输入fingerprint正确 → 必需CPU测试 → 经批准的独立小规模环境检查 → 证据审计。正式评估必须另按protocol promotion，不把smoke、preflight或渲染检查计入研究成功率。

<a id="next"></a>
## 8. 后续工作优先级与授权边界

**本次已有授权只覆盖审查和根目录HANDOFF编写。** 历史执行批准、GPU0–7使用许可、Run044额外1cell批准均有上下文和预算边界；本文不将其扩展为新的实验、修复、merge、环境安装或清理授权。

| 优先级 | 目的与依据 | 前置条件 | 预期产出 / 验收 |
| --- | --- | --- | --- |
| 接手当天：只读核对终局与所有权 | 防止R1–R5使下一人误恢复旧实验；确认4个untracked、stash与嵌套LIBERO修改 | 可读Git/manifest；不需运行模型 | 明确HEAD、终局、候选/轮次/项目目标的区别；任何恢复不能依据旧pending CSV |
| 接手当天：确认可复用对照 | P2 3/10、跨轮4/10与QD2/10口径不同 | 阅读Q/P2原始audit、resolved config与task table | 选定一份明确commit/profile/task/seed/cache/compute定义的对照，不宣称稳定4/10或已达5/10 |
| 接手当天：资源与资料接管 | 存储紧张、路径迁移、local-only分支/外部数据不随Git备份 | 只读检查可先做；备份/迁移写操作另批 | 列出实际可访问root、容量/配额、备份负责人；不删除旧实验 |
| 近期：修复状态/文档一致性 | YAML重复key、H5 pending、trajectory/CSV滞后、恢复血缘错配 | **新增修改授权**，限定专属worktree | schema拒绝duplicate keys；终局与最新run一致；对R11追加校正说明和身份测试，不改变旧outcome、gate或immutable manifest |
| 近期：建立可复现的环境/运行入口 | top-level submodule不足以恢复LIBERO-PRO，EGL存在历史native abort | **批准环境与CPU/环境检查范围**，设备admission | 固定依赖、模型/BDDL/init hash、fresh CUDA/EGL mapping、非敏感凭据配置说明；最小检查证据完整 |
| 近期：决定主线采用哪些工程成果 | EDS未合main；负结果代码不应整体默认启用 | **新增Git整合/测试授权**，处理U1–U4和嵌套修改归属 | 功能级cherry-pick/merge方案、默认关闭研究特性、main回归报告；不要把adoption失败解释为代码都无价值 |
| 研究：是否重启EDS-QD目标 | 当前study已concluded，budget有余额不等于可继续 | **用户批准新versioned design**、独立splits/预算/写边界 | 明确目标仍>=5/10，formal单候选冻结，分清必须硬门与解释性proxy；成功或no-progress均能合法停止 |
| 研究：选择一个task-linked机制而非新大扫 | 旧gain/loss、H1验证落差、H4/H5无迁移，说明proxy alone不足 | 历史evidence packet；先非泄漏诊断；QD外改动另批 | 一个可证伪候选、明确要保留/翻转的行为、计算匹配与task-level验收；不能从暴露formal结果反复调参 |

本次不建议直接恢复FPS、重复257格RBF、增大QD预算或把FSM合进autoresearch。它们可以是未来明确设计的比较对象，但各自已有设计/负结果/不同scope，不能作为“继续任务”的默认动作。

<a id="evidence"></a>
## 9. 证据索引与审查覆盖

### 9.1 资料导航

- 主线历史：[整合索引][RINDEX]、[文档归档manifest](docs/00_overview/rdt-libero-archived-documents-manifest.md)、[归档缺口整合报告](docs/00_overview/2026-06-04-worktree-agent-md-gap-integration-report.md)。原始round-1～4证据在[rdt_intergration目录](docs/03_evidence/rdt_intergration)。
- 语义转折：[训练证据][RFINE]、[GT训练差异][GTDIFF]、[0/10调试总结][RFAIL]、[GT重整设计](docs/01_specs/2026-05-26-rdt-libero-gt-rollout-reintegration-design.md)、[VLS设计](docs/01_specs/2026-06-02-rdt-libero-vls-steering-design.md)。旧分析中的action slots必须与当前code核对。
- EDS历史：[早期报告][EINITIAL]、[Level3][ELEVEL3]、[RDT/EDS Level4][ELEVEL4]、[VLS/PI05 Level4][EPI05]、[旧暂停队列根因][EPAUSE]。
- PG/P2：[RBF证据目录](.worktrees/exp/eds-init-pg-diverse-sampling/docs/03_evidence/eds_init_pg_diverse_sampling)、[旧07-14 handoff](.worktrees/exp/eds-init-pg-diverse-sampling/docs/05_runs/2026-07-14-libero-pro-object-swap-rbf-handoff.md)、[Stage ablation][PSTAGE]、[P2总报告][PFINAL]、[Stage A深入分析](.worktrees/exp/eds-init-pg-diverse-sampling/docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-03-p2-adaptive-eds-rbf-stage-a-detailed-results-analysis.md)、[clean-tail][PCLEAN]、[Direction][PDIR]。
- QD：[初始设计](.worktrees/exp/eds-quality-diversity/docs/01_specs/2026-08-06-eds-quality-diversity-design.md)、[报告][QREPORT]、[audit][QAUDIT]、[预算设计](.worktrees/exp/eds-quality-diversity/docs/01_specs/2026-08-08-eds-qd-search-budget-parameter-sweep-design.md)、[预算报告][QBREPORT]。
- 独立Stage：[W5已提交设计](.worktrees/exp/eds-qd-stage-guidance-transition/docs/01_specs/2026-08-10-eds-qd-stage-guidance-transition-design.md)、[结果][SREPORT]、[audit][SAUDIT]。没有链接到/读取W4受保护副本内容。
- autoresearch：[冻结方案][ADESIGN]、[v2](.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/docs/01_specs/2026-08-12-eds-qd-autoresearch-v2-quality-selection-design.md)、[v3](.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/docs/01_specs/2026-08-12-eds-qd-autoresearch-v3-global-quality-anchor-design.md)、[v4](.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/docs/01_specs/2026-08-12-eds-qd-autoresearch-v4-within-cell-plurality-design.md)、[v5][AV5]。
- autoresearch运行索引：[state](.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research-state.yaml)、[findings](.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/findings.md)、[research-log](.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research-log.md)、[统一总账][ALEDGER]、[experiment protocols](.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/experiments)、[历史evidence catalog](.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/data/historical-evidence-catalog.jsonl)、[最终报告][AFINAL]。优先用终局manifest/总账解决索引滞后。

### 9.2 本次独立校验的关键不可变文件

| 文件 | 本次实测 SHA-256 / 状态 |
| --- | --- |
| [H1 validation audit][A10J] | `3f72d025b492e24e7f615db7c3207c4927710794797dd228edf0579ab1290774`；880602 bytes，mode0444；candidate1/10、control0/10 |
| [Run044 recovery audit][A44J] | `57544a8226b00fbf8085a4944a11d4908709be754990fcbce416b241f21c1cc9`；190521 bytes，mode0444；唯一hard failures为3个zero-secondary迭代 |
| [Run045 final decision][A45M] | `112cc6b19b9ab1970e392f04385ff572a8b8712e362c69c1b27fdd2f5a427d99`；6638 bytes，mode0444；target_achieved=false、new_formal_episodes=0 |

hash一致证明本次所读文件与记录一致，不自动证明其分类逻辑或结论解释正确；R1/R2/R10就是仍需区分的例子。

### 9.3 完整HEAD记录

```text
main                                     d51cb85f485502e0429c79529872efef2ec59981
debug/diffusion-baseline                  c528347697413a4c29f0c798009af37dacee0b21
exp/eds-init-fps                          2628fab7cda767c474cf2d163c3564218d119657
exp/eds-init-pg-diverse-sampling           b3db98cf4fd98a6479d92683e33ebe3d032f25d9
exp/eds-qd-autoresearch-libero-swap-ood     744e08ba4398f2f8e34fb05619c829fc01397f69
exp/eds-qd-stage-guidance-transition       4b3ed17476d5a1fb31e4134f0ce8bbbec8d50731
exp/eds-quality-diversity                 beb8d3f073857f3762a179ce8af4a3c28244b75d
feat/rdt-integration                      3835192744a4be5dc00790774e0593383cbeacf8
feat/rdt-libero-gt-rollout-reintegration    73b90c69b7ad5517a5313cd0bd4ba4d44a16eee0
feat/rdt-libero-object-ckpt                1be4afbf17eaac9066e417ea1309cc1d326d1520
rdt_ed_steering_integration               2628fab7cda767c474cf2d163c3564218d119657
chore/integrate-rdt-libero-vls             25e98a8fe2ada8f0b363a6539b819dfd8f909956
```

### 9.4 审查方法、覆盖与限制

- 覆盖全部11个登记worktree、12本地分支、缓存远端与stash；检查实际目录、HEAD、状态、子模块及主要继承/择取关系。未发现适用于本次根目录编辑的仓库内AGENTS.md；遵守用户提供的全局技能禁用和受保护文件约束。
- 对重复继承文档以源分支/归档索引去重，重点审查影响checkpoint/对照选择、目标、停止与promotion的证据；不把每个继承副本当作独立实验。
- 输出树程序化枚举（不递归追踪子目录symlink）找到：W0有8份results.txt，W7有13份、W8有13份、W9有6份、W10有77份、W3有418份、W4有17份、W6有43份，W5有4份；W1/W2没有outputs。**这是文件覆盖数，不是有效run/episode数**，包含stale/partial，W6还包含W5及budget子树；外部P2 roots另行核对，不能加总这些数称为项目实验量。
- 独立读取了关键results、task/seed metadata、audit、manifest及selected configs；对257-job矩阵程序化汇总状态。没有逐个重看视频/图片、重新训练/评估、重算所有metrics或所有大文件hash。视觉归因主要来自已有报告，已明确其证据等级。
- 本次未改其他worktree、历史产物、依赖或进程；未切branch、commit、merge、清理或删除。唯一交付改动是本文件；最后以11树Git状态/HEAD及链接检查确认范围。未跟踪用户文件保持原状。

[WA]: .worktrees/exp/eds-qd-autoresearch-libero-swap-ood
[WP]: .worktrees/exp/eds-init-pg-diverse-sampling
[WQ]: .worktrees/exp/eds-quality-diversity
[WS]: .worktrees/exp/eds-qd-stage-guidance-transition
[WE]: .worktrees/feat/rdt_ed_steering_integration
[RINDEX]: docs/00_overview/rdt-libero-worktree-integration-index.md
[RFINE]: docs/03_evidence/2026-05-23-rdt-libero-finetune-evidence-report.md
[GTDIFF]: docs/02_analysis/rdt_intergration/2026-05-26-rdt-libero-finetune-gt-diff-analysis.md
[RFAIL]: docs/02_analysis/rdt_intergration/libero/2026-05-26-rdt-libero-0-success-debugging-summary.md
[RVLS]: docs/03_evidence/2026-06-03-rdt-libero-vls-hparam-validation.md
[EINITIAL]: .worktrees/feat/rdt_ed_steering_integration/docs/03_evidence/eds_steering/rdt_eds_steering_evaluation.md
[ELEVEL3]: .worktrees/feat/rdt_ed_steering_integration/docs/03_evidence/eds_steering/level_3_libero_object_success.md
[ELEVEL4]: .worktrees/feat/rdt_ed_steering_integration/docs/03_evidence/eds_steering/level_4_libero_pro_ood.md
[EPI05]: .worktrees/feat/rdt_ed_steering_integration/docs/03_evidence/eds_steering/level_4_vls_pi05_libero_pro_ood.md
[EPAUSE]: .worktrees/feat/rdt_ed_steering_integration/docs/03_evidence/eds_steering/ood_eval/paused_jobs_root_cause.md
[PROLL]: .worktrees/exp/eds-init-pg-diverse-sampling/docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-11-rollout-rbf-level3-parameter-sweep.md
[PSWAP]: .worktrees/exp/eds-init-pg-diverse-sampling/docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-12-libero-pro-object-swap-rdt-eds-rbf-report.md
[PSTAGE]: .worktrees/exp/eds-init-pg-diverse-sampling/docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-31-libero-pro-object-swap-vlm-stage-recognition-ablation-report.md
[PSTAGEA]: .worktrees/exp/eds-init-pg-diverse-sampling/docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-02-p2-adaptive-eds-rbf-stage-a-report.md
[PFINAL]: .worktrees/exp/eds-init-pg-diverse-sampling/docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-02-p2-adaptive-eds-rbf-object-swap-report.md
[PCLEAN]: .worktrees/exp/eds-init-pg-diverse-sampling/docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-03-p2-rollout-clean-tail-parameter-sweep-report.md
[PDIR]: .worktrees/exp/eds-init-pg-diverse-sampling/docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-04-p2-direction-normalized-rbf-report.md
[PADAPTROOT]: /mnt/data/shared2/hynx/VLA-Pilot++/eds-init-pg-diverse-sampling/outputs/ood_eval/p2_adaptive_eds_rbf
[PCLEANROOT]: /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/p2_rollout_clean_tail_sweep
[PCLEANA]: /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/p2_rollout_clean_tail_sweep/analysis/phase_b_audit.json
[PDIRROOT]: /mnt/data/shared2/zhuoli/output/p2_direction_normalized_rbf
[PDIRA]: /mnt/data/shared2/zhuoli/output/p2_direction_normalized_rbf/analysis/direction_rbf_formal_audit.json
[QROOT]: /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity
[QREPORT]: .worktrees/exp/eds-quality-diversity/docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-06-eds-quality-diversity-report.md
[QAUDIT]: /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/analysis/qd_ed_formal_audit.json
[QBROOT]: /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/outputs/search_budget_sweep_20260808
[QBREPORT]: /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/outputs/search_budget_sweep_20260808/analysis/final_report.md
[QBAUDIT]: /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/outputs/search_budget_sweep_20260808/analysis/formal_audit.json
[SROOT]: /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/outputs/stage_guidance_transition_20260810
[SREPORT]: /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/outputs/stage_guidance_transition_20260810/analysis/final_report.md
[SAUDIT]: /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/outputs/stage_guidance_transition_20260810/analysis/formal_audit.json
[STEST]: /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/outputs/stage_guidance_transition_20260810/analysis/test_evidence.json
[AROOT]: /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood
[ADESIGN]: .worktrees/exp/eds-qd-autoresearch-libero-swap-ood/docs/01_specs/2026-08-08-eds-qd-autoresearch-libero-swap-ood-design.md
[AV5]: .worktrees/exp/eds-qd-autoresearch-libero-swap-ood/docs/01_specs/2026-08-12-eds-qd-autoresearch-v5-protected-quality-lane-design.md
[ALEDGER]: .worktrees/exp/eds-qd-autoresearch-libero-swap-ood/docs/03_evidence/eds_qd_autoresearch/iteration-ledger.md
[AFINAL]: .worktrees/exp/eds-qd-autoresearch-libero-swap-ood/docs/03_evidence/eds_qd_autoresearch/2026-08-12-eds-qd-autoresearch-final-report.md
[A10]: .worktrees/exp/eds-qd-autoresearch-libero-swap-ood/experiments/run_010_causal_envelope_candidate/analysis.md
[A10J]: /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_010_causal_envelope_candidate/analysis/validation_audit.json
[A23]: .worktrees/exp/eds-qd-autoresearch-libero-swap-ood/experiments/run_023_reward_degenerate_online_mechanism/analysis.md
[A34]: .worktrees/exp/eds-qd-autoresearch-libero-swap-ood/experiments/run_034_global_quality_anchor_dev_a/analysis.md
[A44]: .worktrees/exp/eds-qd-autoresearch-libero-swap-ood/experiments/run_044_protected_quality_lane_online_mechanism/analysis.md
[A44J]: /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_044_protected_quality_lane_online_mechanism/analysis/mechanism_recovery_v2_audit.json
[A44L]: /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_044_protected_quality_lane_online_mechanism/manifests/episode_attempt_ledger.jsonl
[A45P]: .worktrees/exp/eds-qd-autoresearch-libero-swap-ood/experiments/run_045_global_no_adoption_conclusion/protocol.md
[A45M]: /mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_045_global_no_adoption_conclusion/manifests/global_decision_manifest.json
