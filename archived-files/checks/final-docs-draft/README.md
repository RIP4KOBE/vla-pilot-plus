# VLA-Pilot++：RDT steering

在共享的机器人观测、在线视觉 Stage 控制器和执行链上，比较 **VLS、EDS、EDS+QD** 三种推理方法。当前验收范围是 **RDT + LIBERO ObjectSwap OOD**。每任务在线生成 reward 程序，候选评分与梯度在本地 Torch 中计算；在线服务还承担身份描述和执行过程中的视觉 Stage 查询。

三种方法已接入公共入口。冻结版本在原环境和独立安装环境均通过 **1403 项 CPU 测试**，设备/渲染、QD 数值诊断及公共 GPU/API 预检已通过。公共版本 **EDS 已完成完整有效 3/10（task 3、8、9）**，通过原始 v2 审计及重新执行的只读审计；**VLS、EDS+QD、整体整合与 main 合并仍为 PENDING**。此前迁移版 EDS 的有效3/10是独立一轮记录。[当前状态与证据](docs/steering/integration-status.md)。

| 方法 / CLI | 做什么 | 配置 |
| --- | --- | --- |
| VLS / `vls` | 20 个候选；reward 梯度、多样性梯度、自适应 FKD（允许 ESS 跳过重采样） | [vls.yaml](configs/steering/vls.yaml) |
| EDS / `eds` | 16 个候选；RBF 多样性、reward 评分、10 轮父代重采样与截断去噪 | [eds.yaml](configs/steering/eds.yaml) |
| EDS+QD / `eds_qd` | 共用 EDS 搜索；动作块内 4×4 archive 提供父代与最终候选 | [eds_qd.yaml](configs/steering/eds_qd.yaml) |

默认配置的计算预算不同。QD archive 每个动作块重新建立；算法、Stage 进度及其限制见[架构说明](docs/steering/architecture.md)。

## 开始使用

先完成[安装与资产准备](docs/steering/installation.md)：创建独立环境，单独安装并登录 Codex CLI，取得与清单匹配的模型/DINO 资产，再生成 `configs/local.yaml`。**精确资产包的共享入口仍待维护者提供**；仅 clone 仓库不足以在线运行。模型内容与实际加载路径校验是 configure、preflight 和真实 launcher 的必经步骤。

以下命令在仓库根目录、已激活的环境中执行。选择一个方法，使用新的输出目录；其余方法只需替换 `--method` 和目录名。

```bash
# 1. 配置预览；不创建输出目录或调用 GPU/API。
python scripts/run_steering.py --method eds --local-config configs/local.yaml \
  --output-dir outputs/eds-preview --print-config

# 2. 在已分配的空闲设备上验证资产、渲染及一次真实视觉请求。
python scripts/check_steering.py --local-config configs/local.yaml \
  --output-dir outputs/preflight-001 --gpu --api

# 3. 冻结源码和配置，执行完整十任务。
python scripts/evaluate_steering.py --method eds --local-config configs/local.yaml \
  --output-dir outputs/eds-full10-001

# 4. 完成后只读复查完整证据。
python scripts/audit_steering.py outputs/eds-full10-001 --no-write
```

可选单任务诊断使用 `scripts/run_steering.py --tasks 0`，保存独立目录和报告。机器配置决定 GPU/EGL 对应关系，shell 的 CUDA 编号不会覆盖它。在线配置固定为 **Codex CLI / gpt-6-astra / low**，使用自己的有效登录。目录存在时换新 run ID，运行期间保持源码、配置、提示词和资产不变。

## 结果与协作

每个 run 保存配置/源码/环境 manifest、状态、控制台日志、在线输入输出和视频。主要指标在 `output/evaluation/`，视频在 `output/episode_*/`；具体路径以 run manifest 为准。环境 success 与完整审计共同支持成绩。[结果读取、审计与归档](docs/steering/evaluation.md)列出文件用途、有效性规则和命令。

从共同分支创建功能分支，通过 PR 审阅合入；[CONTRIBUTING.md](CONTRIBUTING.md)说明配置冻结、算法变更和验证要求。原始日志、大视频和模型保存在外部归档，小型 fixture 用于测试。最终可访问证据归档、资产共享入口与 main 合并 commit 仍待补齐。

## 上游方法与许可

VLS 上游方法见 [VLS: Steering Pretrained Robot Policies via Vision-Language Models](https://arxiv.org/abs/2602.03973)（Shuo Liu、Ishneet Sukhvinder Singh、Yiqing Xu、Jiafei Duan、Ranjay Krishna，2026）。本仓库的 RDT、在线 Stage、初始化和 EDS/QD 条件由当前配置与验收定义；本轮结果不代表该论文结果，EDS/EDS+QD 也不归属于该论文。

```bibtex
@article{liu2026vls,
  title   = {VLS: Steering Pretrained Robot Policies via Vision-Language Models},
  author  = {Shuo Liu and Ishneet Sukhvinder Singh and Yiqing Xu and Jiafei Duan and Ranjay Krishna},
  journal = {arXiv preprint arXiv:2602.03973},
  year    = {2026}
}
```

本仓库现有 [LICENSE](LICENSE) 为 MIT。RDT、LeRobot、LIBERO、外部模型和数据保留各自来源与许可；资产的分发授权需要分别确认。仓库中保留的其他 policy/backend、基准和真实机器人代码没有在本轮重新验收。

<a id="provenance"></a>
## Provenance：来源与本地证据

历史名称与 worktree 映射集中在本节，不作为公共方法或配置入口。受测 runtime、后续审计器与最终发布 commit 分别记录；基础设施补丁进入发布版本后，不能把旧 cohort 改称在新版本上运行。

| 来源 / 身份 | 范围 |
| --- | --- |
| 原 main | `d51cb85f485502e0429c79529872efef2ec59981` |
| 来源研究 worktree | `.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-gpu6-20260922T063626Z/study_worktree`；HEAD `77761b4cda78ac3b6762a6aa60f97b07fde7c1dc` |
| 来源在线 baseline | `codex_failed_contact_v17_historical_initialization_online_full10`，位于来源 worktree 的 `artifacts/stage_closed_loop_20260929/runs/`；3/10、QD OFF |
| 来源验收快照 | 48 个文件：37 个 untracked、5 个 modified、6 个 clean；来源 HEAD 本身不包含全部验收内容 |
| 迁移在线验收 | `cfecb12db736f1a3408d9528d9336aadcb7e41b5`；EDS 有效 3/10；[完整报告](.worktrees/exp/steering-integration/runs/eds-migration-20261013/migration-full10-report.md)与[验收 JSON](.worktrees/exp/steering-integration/runs/eds-migration-20261013/migration-full10-acceptance.json) |
| 本次三模式受测 runtime | `33954ead452927fc3168efb610487a688f89169e`；EDS完整有效3/10，VLS/EDS+QD及整体验收 **PENDING** |
| 整合分支 / 最终 main 合并 | `codex/rdt-steering-integration`；发布/merge commit **PENDING** |
| 后续独立审计器 | 外置候选已完成EDS复制归档重审，source hash与原runtime分别登记于[receipt](.worktrees/exp/steering-integration/checks/archive-v2-candidate-validation/receipt.json)；最终审计器commit **PENDING** |

命名映射：`core/c0_reward_contract.py` → `core/target_distance_reward.py`；`core/poe_stage_capture.py` → `core/stage_capture.py`；`vlm_query/c0_contract_v1` → `vlm_query/target_distance`；合同 `c0_xyz_v1` → `target_distance`。Stage profile `evidence_v1/contact_v2/grasp_v3/proprio_v4` → `evidence/contact/grasp/online`。

两类原始字节保留例外也集中在此：

- [科学提示词](vlm_query/target_distance/guidance_template_libero.txt)中两处 **C0** 保持原始 stimulus；改写须登记为新的实验条件。
- 哈希固定的原始 source/capture/fixture blob 可能包含 **N1V、V17** 等旧名、版本或本机路径。它们是追溯数据，不是新入口。保留原字节及 hash；公共文档/活动源码的命名清理不回写历史 blob。已准备的活动源码注释清理须等冻结运行结束后处理。

历史 P2 同轮控制的 4/10 属于另一套 provider/reward/Stage 条件；标准 `libero_object` 的无引导 9/10、VLS 7/10不属于 ObjectSwap OOD，不能据数值直接排序当前方法。

以下为维护者机器上的 ignored 证据，普通 clone 不自带；可分享的外部归档链接 **PENDING**：

- [迁移 CPU](.worktrees/exp/steering-integration/checks/cpu-migration.log)：1118 passed、2 warnings、82.42s；[最初干净安装报告](.worktrees/exp/steering-integration/pending-integration/steering-clean-install-report.md)与[验收摘要](.worktrees/exp/steering-integration/pending-integration/clean-install-validation-summary.json)：1118 passed、1 warning、86.53s，绑定迁移提交。
- [公共 runtime CPU／原环境](.worktrees/exp/steering-integration/checks/cpu-common-framework-002.log)与[同一独立安装环境](.worktrees/exp/steering-integration/checks/cpu-common-framework-clean.log)：分别1403 passed、124.18s与1403 passed、124.63s。
- [公共预检](.worktrees/exp/steering-integration/preflight-common-20261013/report.json)：CLI 0.156.1，GPU0/EGL2与一次有效图像请求；[设备映射](.worktrees/exp/steering-integration/checks/gpu014-mapping-summary.json)分别记录GPU0/1/4；[QD 数值摘要](.worktrees/exp/steering-integration/checks/qd-gpu4-numeric-summary.json)记录318批、23,850个probe精确一致。
- 新三组运行：[EDS](.worktrees/exp/steering-integration/runs/eds-common-20261013/manifest.json)、[VLS](.worktrees/exp/steering-integration/runs/vls-common-20261013/manifest.json)、[EDS+QD](.worktrees/exp/steering-integration/runs/eds_qd-common-20261013/manifest.json)。EDS的[原始audit](.worktrees/exp/steering-integration/runs/eds-common-20261013/audit.json)及[重新只读审计汇总](.worktrees/exp/steering-integration/checks/three-mode-eds-completed.json)已通过；VLS/EDS+QD及最终整合 **PENDING**，见[状态页](docs/steering/integration-status.md)。
