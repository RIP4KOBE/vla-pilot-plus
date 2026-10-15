# VLA-Pilot++：RDT steering

在共享的机器人观测、在线视觉 Stage 控制器和执行链上，比较 **VLS、EDS、EDS+QD** 三种推理方法。当前验收范围是 **RDT + LIBERO ObjectSwap OOD**。每任务在线生成 reward 程序，候选评分与梯度在本地 Torch 中计算；在线服务还承担身份描述和执行过程中的视觉 Stage 查询。

2026-10-14：main 的公共评测配置已将 Codex 推理强度从 `low` 改为 `ultra`，三模式各十任务已全部完成并通过独立复核，30份视频均完整有效。此次没有观察到稳定的成功率提升：[推理强度对照报告](docs/steering/reasoning-effort-comparison.md)包含逐任务结果、Stage差异、耗时和所有重测记录。

| 方法 | 既有 low | 本次 ultra |
| --- | ---: | ---: |
| EDS | 3/10 | 3/10 |
| VLS | 1/10 | 1/10 |
| EDS+QD | 1/10 | 0/10 |

两轮各30回合均完整有效。ultra测试中另加强了传输恢复：重试1→8次、等待2→30秒，最终54个限流请求恢复，零回合级基础设施错误。首次ultra的独立有效VLS为2/10，分开保留；表中使用预先登记的新统一协议整组结果，没有按分数挑选回合。

2026-10-13 的low整合验收已通过三组有效且EDS≥3/10的门槛；当时发布基础设施在原环境与独立安装环境均通过 **1436项CPU测试**。本次改档及传输修订的检查另见对照报告。代码已于2026-10-15普通推送至远端 main；本次整理及最终发布记录见[维护报告](docs/maintenance/repository-consolidation-20261015.md)。[原low逐任务结果](docs/steering/results.md) · [整合验收状态](docs/steering/integration-status.md)。

这是每任务一个固定seed的ObjectSwap OOD比较，默认方法预算不同。EDS是本轮观测成功数最高的方法；结果不支持统计优越性、等计算预算或泛化结论。此前迁移版EDS的3/10单独保留。

| 方法 / CLI | 做什么 | 配置 |
| --- | --- | --- |
| VLS / `vls` | 20 个候选；reward 梯度、多样性梯度、自适应 FKD（允许 ESS 跳过重采样） | [vls.yaml](configs/steering/vls.yaml) |
| EDS / `eds` | 16 个候选；RBF 多样性、reward 评分、10 轮父代重采样与截断去噪 | [eds.yaml](configs/steering/eds.yaml) |
| EDS+QD / `eds_qd` | 共用 EDS 搜索；动作块内 4×4 archive 提供父代与最终候选 | [eds_qd.yaml](configs/steering/eds_qd.yaml) |

默认配置的计算预算不同。QD archive 每个动作块重新建立；算法、Stage 进度及其限制见[架构说明](docs/steering/architecture.md)。

## 项目与研发导航

- [Research Proposal v0.1](docs/research/research_proposal.md)：核心想法、可检验假设、QD 与递归改进路线；明确标注 Notion 图片尚未读取的来源缺口。
- [Research Progress](docs/research/research_progress.md)：当前能力、最可靠 EDS 对照、分协议逐任务结果和下一步验收。
- [AGENTS.md](AGENTS.md) 与 [CONTRIBUTING.md](CONTRIBUTING.md)：开发规则、检查命令和团队协作。
- [文档导航](docs/README.md) 与 [仓库整理报告](docs/maintenance/repository-consolidation-20261015.md)：历史材料、分支/工作树归档和发布状态。
- [GitHub 历史源码索引](docs/maintenance/historical-source-index-20261015.md)：历史分支、工作树未提交源码、stash 与外部源码快照的远端入口；[清理与控制依赖审查](docs/maintenance/main-scope-and-control-dependencies-20261015.md)说明哪些旧功能可退役、为何 Stage/Codex 仍需保留。
- [VLS 在线控制比较与非核心清理](docs/maintenance/vls-control-and-noncore-cleanup-20261015.md)：上游与当前闭环的区别、99 个远端分支的来源、已删除/归档文件及恢复索引；`core` 本轮未改动。

项目目标是在冻结 RDT 的推理阶段，以 EDS 为底座引入有用的 quality-diversity 和执行反馈。当前 QD 仅在动作块内维护档案；跨块/跨任务改进以及自动 BD 是待验证研究方向。

## 开始使用

远端 `main` 已包含验收框架。新合作者先 clone，再按下列安装与资产流程准备环境；普通 clone 不包含模型和完整原始实验归档。

先完成[安装与资产准备](docs/steering/installation.md)：创建独立环境，单独安装并登录 Codex CLI，取得与清单匹配的模型/DINO 资产，再生成 `configs/local.yaml`。**目前没有配置公开的精确资产包**；RDT checkpoint与固定DINO源码需由维护者交付并通过清单验证，仅 clone 仓库不足以在线运行。模型内容与实际加载路径校验是 configure、preflight 和真实 launcher 的必经步骤。

根目录 `environment.yml`、`requirements.txt`、`run.sh`、`setup.sh` 保留旧后端兼容用途，未重新验收；当前三模式统一使用 `*-steering*` 安装配方和下方公共 launcher。旧安装脚本中的 Poe 提示不适用于当前 Codex 协议。

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

可选单任务诊断使用 `scripts/run_steering.py --tasks 0`，保存独立目录和报告。机器配置决定 GPU/EGL 对应关系，shell 的 CUDA 编号不会覆盖它。当前在线配置为 **Codex CLI / gpt-6-astra / ultra**，使用自己的有效登录；两类在线客户端共用180秒超时、最多8次未完成传输重试及30秒等待。完整回复不因任务失败而重采样。目录存在时换新 run ID，运行期间保持源码、配置、提示词和资产不变。

## 结果与协作

每个 run 保存配置/源码/环境 manifest、状态、控制台日志、在线输入输出和视频。主要指标在 `output/evaluation/`，视频在 `output/episode_*/`；具体路径以 run manifest 为准。环境 success 与完整审计共同支持成绩。[结果读取、审计与归档](docs/steering/evaluation.md)列出文件用途、有效性规则和命令。

从共同分支创建功能分支，通过 PR 审阅合入；[CONTRIBUTING.md](CONTRIBUTING.md)说明配置冻结、算法变更和验证要求。原始日志、大视频和模型保存在外部归档，小型 fixture 用于测试。Git内的[low结果摘要](docs/steering/validation/final-results.json)和[ultra对照摘要](docs/steering/validation/reasoning-effort-results.json)分别保存完整逐任务结果和证据hash；完整原始数据目前只有维护者本机归档，没有公开下载地址。资产获取边界见[安装说明](docs/steering/installation.md#固定模型与源码资产)。

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

历史名称与 worktree 映射集中在本节，不作为公共方法或配置入口。2026-10-15清理映射见[归档清单](docs/maintenance/cleanup-inventory-20261015.json)；旧工作区路径保留为静态归档别名，不再用于开发。受测 runtime、后续审计器与最终发布 commit 分别记录；基础设施补丁进入发布版本后，不能把旧 cohort 改称在新版本上运行。

历史源码随后发布为 `codex/archive/20261015/*`，见[发布报告](docs/maintenance/historical-source-publication-20261015.md)。GitHub 副本对凭据样式字符串及签名链接做了脱敏，原提交/文件哈希与发布版本有明确映射；原始科学证据继续保留原字节。新开发统一从 main 派生，不在归档分支继续实验。

| 来源 / 身份 | 范围 |
| --- | --- |
| 整合前 origin/main（历史） | `d51cb85f485502e0429c79529872efef2ec59981`；2026-10-13 17:22 UTC fetch核验 |
| 来源研究 worktree | `.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-gpu6-20260922T063626Z/study_worktree`；HEAD `77761b4cda78ac3b6762a6aa60f97b07fde7c1dc` |
| 来源在线 baseline | `codex_failed_contact_v17_historical_initialization_online_full10`，位于来源 worktree 的 `artifacts/stage_closed_loop_20260929/runs/`；3/10、QD OFF |
| 来源验收快照 | 48 个文件：37 个 untracked、5 个 modified、6 个 clean；来源 HEAD 本身不包含全部验收内容 |
| 迁移在线验收 | `cfecb12db736f1a3408d9528d9336aadcb7e41b5`；EDS 有效 3/10；[完整报告](.worktrees/exp/steering-integration/runs/eds-migration-20261013/migration-full10-report.md)与[验收 JSON](.worktrees/exp/steering-integration/runs/eds-migration-20261013/migration-full10-acceptance.json) |
| low三模式受测 runtime | `33954ead452927fc3168efb610487a688f89169e`；EDS 3/10、VLS 1/10、EDS+QD 1/10；30/30有效，整合gate通过 |
| 整合时最终代码版本 | `b68777b46a374760a19fa76e3c309d9c84cfcc4c`；补齐两个已受测、原先被ignored的Hydra兼容alias，按原字节追踪；后续文档commit不改科学源码 |
| 整合分支 / 最终 main 合并 | `codex/rdt-steering-integration` 的 `c67ea2eca18f408b99244fcbcd2987f78eee408a` 已合入本地main；merge及团队基准为 `8c1051f85a57115163845ec478d06a3ccc68c190`；2026-10-15随main普通发布 |
| 后续独立审计器 | 归档修复已接入；接入前的独立EDS复制归档重审将checker source hash与原runtime分别登记于[receipt](.worktrees/exp/steering-integration/checks/archive-v2-candidate-validation/receipt.json)；审计器/基础设施commit `5bf01db84e8c05251f720a3f8b9a73aa019f9568` |
| 首轮ultra受测 runtime | `6c83eb6a55fa6f92723e58a960d59ee4f606084e`；VLS有效2/10；EDS、EDS+QD各有1个HTTP429回合错误，整组无效 |
| ultra统一协议受测 runtime | `c99565de6e34278c14518748d7c608433a4c529a`；在main完成，未新增worktree；EDS 3/10、VLS 1/10、EDS+QD 0/10，30/30有效；[报告及来源索引](docs/steering/reasoning-effort-comparison.md) |

命名映射：`core/c0_reward_contract.py` → `core/target_distance_reward.py`；`core/poe_stage_capture.py` → `core/stage_capture.py`；`vlm_query/c0_contract_v1` → `vlm_query/target_distance`；合同 `c0_xyz_v1` → `target_distance`。Stage profile `evidence_v1/contact_v2/grasp_v3/proprio_v4` → `evidence/contact/grasp/online`。

两类原始字节保留例外也集中在此：

- [科学提示词](vlm_query/target_distance/guidance_template_libero.txt)中两处 **C0** 保持原始 stimulus；改写须登记为新的实验条件。
- 哈希固定的原始 source/capture/fixture blob 可能包含 **N1V、V17** 等旧名、版本或本机路径。它们是追溯数据，不是新入口。保留原字节及 hash；公共文档/活动源码的命名清理不回写历史 blob。活动源码中的历史名称注释已在三组验收封存后清理；科学提示词与原始blob未改写。

历史 P2 同轮控制的 4/10 属于另一套 provider/reward/Stage 条件；标准 `libero_object` 的无引导 9/10、VLS 7/10不属于 ObjectSwap OOD，不能据数值直接排序当前方法。

以下为维护者机器上的 ignored 证据，普通 clone 不自带。仓库根目录为 `/home/hynx/lizhuo/VLA-Pilot++`，证据根为其 `.worktrees/exp/steering-integration/`；维护者可按索引交付字节副本，目前没有配置公开归档或模型包：

- [迁移 CPU](.worktrees/exp/steering-integration/checks/cpu-migration.log)：1118 passed、2 warnings、82.42s；[最初干净安装报告](.worktrees/exp/steering-integration/pending-integration/steering-clean-install-report.md)与[验收摘要](.worktrees/exp/steering-integration/pending-integration/clean-install-validation-summary.json)：1118 passed、1 warning、86.53s，绑定迁移提交。
- [公共 runtime CPU／原环境](.worktrees/exp/steering-integration/checks/cpu-common-framework-002.log)与[同一独立安装环境](.worktrees/exp/steering-integration/checks/cpu-common-framework-clean.log)：分别1403 passed、124.18s与1403 passed、124.63s。
- [公共预检](.worktrees/exp/steering-integration/preflight-common-20261013/report.json)：CLI 0.156.1，GPU0/EGL2与一次有效图像请求；[设备映射](.worktrees/exp/steering-integration/checks/gpu014-mapping-summary.json)分别记录GPU0/1/4；[QD 数值摘要](.worktrees/exp/steering-integration/checks/qd-gpu4-numeric-summary.json)记录318批、23,850个probe精确一致。
- 三组完整运行：[EDS](.worktrees/exp/steering-integration/runs/eds-common-20261013/manifest.json)、[VLS](.worktrees/exp/steering-integration/runs/vls-common-20261013/manifest.json)、[EDS+QD](.worktrees/exp/steering-integration/runs/eds_qd-common-20261013/manifest.json)。[原始冻结汇总](.worktrees/exp/steering-integration/checks/three-mode-final.json)和[封存记录](.worktrees/exp/steering-integration/checks/three-mode-final-seal.json)在基础设施修改前完成；[30份视频索引](.worktrees/exp/steering-integration/checks/video-health/index.md)保存原件与健康检查位置。
- 发布基础设施的[原环境CPU](.worktrees/exp/steering-integration/checks/cpu-release-primary.log)和[独立环境CPU](.worktrees/exp/steering-integration/checks/cpu-release-clean.log)：各1436 passed、3 skipped，分别129.98s、130.02s；没有重跑科学任务、GPU或API。
- ultra实验管理目录为`.worktrees/exp/steering-ultra-20261014/`；[完整封存](.worktrees/exp/steering-ultra-20261014/checks/ultra-recovery-final-seal.json)、[30份视频](.worktrees/exp/steering-ultra-20261014/checks/video-health-recovery/index.md)与[全部尝试](.worktrees/exp/steering-ultra-20261014/checks/all-attempts-ledger.json)保留首轮、停止的重测和最终新组，原low数据未改写。
