# Source and evaluation provenance

Runtime identities and evidence are recorded separately for each evaluation. Current module paths are documented in [architecture](architecture.md); historical branch navigation is in the [branch index](../maintenance/branch-index.md).

## Clean-environment evaluation

The collaborator installation and evaluation uses runtime commit `ef74b02be6e9430e861ae6d1980a4b2641e4c716`, transferred through Git into a fresh clone originally obtained from remote main at `6c1e6557c6d0f34f644e711ad4afbfd0df92c290`. It uses a new Python environment and explicit, hash-verified Robosuite compatibility patches. All three ten-task cohorts completed: VLS 1/10, EDS 3/10, EDS+QD 0/10, with 30/30 valid episodes. Installation attempts, coverage, task outcomes, hashes, and the delivery-source comparison are recorded in the [onboarding validation report](onboarding-validation.md) and [compact evidence](validation/onboarding-20261015.json). Final documentation and dependency-recipe comments do not change the 113 frozen runtime files or effective dependency requirements. Historical scores below remain separate measurements.

## 历史来源与本地证据

历史名称与 worktree 映射集中在本节，不作为公共方法或配置入口。2026-10-15清理映射见[归档清单](../../docs/maintenance/cleanup-inventory-20261015.json)；旧工作区路径保留为静态归档别名，不再用于开发。受测 runtime、后续审计器与最终发布 commit 分别记录；基础设施补丁进入发布版本后，不能把旧 cohort 改称在新版本上运行。

历史源码随后发布为 `codex/archive/20261015/*`，见[发布报告](../../docs/maintenance/historical-source-publication-20261015.md)。GitHub 副本对凭据样式字符串及签名链接做了脱敏，原提交/文件哈希与发布版本有明确映射；原始科学证据继续保留原字节。新开发统一从 main 派生，不在归档分支继续实验。

| 来源 / 身份 | 范围 |
| --- | --- |
| 整合前 origin/main（历史） | `d51cb85f485502e0429c79529872efef2ec59981`；2026-10-13 17:22 UTC fetch核验 |
| 来源研究 worktree | `.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-gpu6-20260922T063626Z/study_worktree`；HEAD `77761b4cda78ac3b6762a6aa60f97b07fde7c1dc` |
| 来源在线 baseline | `codex_failed_contact_v17_historical_initialization_online_full10`，位于来源 worktree 的 `artifacts/stage_closed_loop_20260929/runs/`；3/10、QD OFF |
| 来源验收快照 | 48 个文件：37 个 untracked、5 个 modified、6 个 clean；来源 HEAD 本身不包含全部验收内容 |
| 迁移在线验收 | `cfecb12db736f1a3408d9528d9336aadcb7e41b5`；EDS 有效 3/10；[完整报告](../../.worktrees/exp/steering-integration/runs/eds-migration-20261013/migration-full10-report.md)与[验收 JSON](../../.worktrees/exp/steering-integration/runs/eds-migration-20261013/migration-full10-acceptance.json) |
| low三模式受测 runtime | `33954ead452927fc3168efb610487a688f89169e`；EDS 3/10、VLS 1/10、EDS+QD 1/10；30/30有效，整合gate通过 |
| 整合时最终代码版本 | `b68777b46a374760a19fa76e3c309d9c84cfcc4c`；补齐两个已受测、原先被ignored的Hydra兼容alias，按原字节追踪；后续文档commit不改科学源码 |
| 整合分支 / 最终 main 合并 | `codex/rdt-steering-integration` 的 `c67ea2eca18f408b99244fcbcd2987f78eee408a` 已合入本地main；merge及团队基准为 `8c1051f85a57115163845ec478d06a3ccc68c190`；2026-10-15随main普通发布 |
| 后续独立审计器 | 归档修复已接入；接入前的独立EDS复制归档重审将checker source hash与原runtime分别登记于[receipt](../../.worktrees/exp/steering-integration/checks/archive-v2-candidate-validation/receipt.json)；审计器/基础设施commit `5bf01db84e8c05251f720a3f8b9a73aa019f9568` |
| 首轮ultra受测 runtime | `6c83eb6a55fa6f92723e58a960d59ee4f606084e`；VLS有效2/10；EDS、EDS+QD各有1个HTTP429回合错误，整组无效 |
| ultra统一协议受测 runtime | `c99565de6e34278c14518748d7c608433a4c529a`；在main完成，未新增worktree；EDS 3/10、VLS 1/10、EDS+QD 0/10，30/30有效；[报告及来源索引](../../docs/steering/reasoning-effort-comparison.md) |

命名映射：`core/c0_reward_contract.py` → `core/target_distance_reward.py`；`core/poe_stage_capture.py` → `core/stage_capture.py`；`vlm_query/c0_contract_v1` → `vlm_query/target_distance`；合同 `c0_xyz_v1` → `target_distance`。Stage profile `evidence_v1/contact_v2/grasp_v3/proprio_v4` → `evidence/contact/grasp/online`。

两类原始字节保留例外也集中在此：

- [科学提示词](../../vlm_query/target_distance/guidance_template_libero.txt)中两处 **C0** 保持原始 stimulus；改写须登记为新的实验条件。
- 哈希固定的原始 source/capture/fixture blob 可能包含 **N1V、V17** 等旧名、版本或本机路径。它们是追溯数据，不是新入口。保留原字节及 hash；公共文档/活动源码的命名清理不回写历史 blob。活动源码中的历史名称注释已在三组验收封存后清理；科学提示词与原始blob未改写。

历史 P2 同轮控制的 4/10 属于另一套 provider/reward/Stage 条件；标准 `libero_object` 的无引导 9/10、VLS 7/10不属于 ObjectSwap OOD，不能据数值直接排序当前方法。

以下为维护者机器上的 ignored 证据，普通 clone 不自带。仓库根目录为 `/home/hynx/lizhuo/VLA-Pilot++`，证据根为其 `.worktrees/exp/steering-integration/`；维护者可按索引交付字节副本，目前没有配置公开归档或模型包：

- [迁移 CPU](../../.worktrees/exp/steering-integration/checks/cpu-migration.log)：1118 passed、2 warnings、82.42s；[最初干净安装报告](../../.worktrees/exp/steering-integration/pending-integration/steering-clean-install-report.md)与[验收摘要](../../.worktrees/exp/steering-integration/pending-integration/clean-install-validation-summary.json)：1118 passed、1 warning、86.53s，绑定迁移提交。
- [公共 runtime CPU／原环境](../../.worktrees/exp/steering-integration/checks/cpu-common-framework-002.log)与[同一独立安装环境](../../.worktrees/exp/steering-integration/checks/cpu-common-framework-clean.log)：分别1403 passed、124.18s与1403 passed、124.63s。
- [公共预检](../../.worktrees/exp/steering-integration/preflight-common-20261013/report.json)：CLI 0.156.1，GPU0/EGL2与一次有效图像请求；[设备映射](../../.worktrees/exp/steering-integration/checks/gpu014-mapping-summary.json)分别记录GPU0/1/4；[QD 数值摘要](../../.worktrees/exp/steering-integration/checks/qd-gpu4-numeric-summary.json)记录318批、23,850个probe精确一致。
- 三组完整运行：[EDS](../../.worktrees/exp/steering-integration/runs/eds-common-20261013/manifest.json)、[VLS](../../.worktrees/exp/steering-integration/runs/vls-common-20261013/manifest.json)、[EDS+QD](../../.worktrees/exp/steering-integration/runs/eds_qd-common-20261013/manifest.json)。[原始冻结汇总](../../.worktrees/exp/steering-integration/checks/three-mode-final.json)和[封存记录](../../.worktrees/exp/steering-integration/checks/three-mode-final-seal.json)在基础设施修改前完成；[30份视频索引](../../.worktrees/exp/steering-integration/checks/video-health/index.md)保存原件与健康检查位置。
- 发布基础设施的[原环境CPU](../../.worktrees/exp/steering-integration/checks/cpu-release-primary.log)和[独立环境CPU](../../.worktrees/exp/steering-integration/checks/cpu-release-clean.log)：各1436 passed、3 skipped，分别129.98s、130.02s；没有重跑科学任务、GPU或API。
- ultra实验管理目录为`.worktrees/exp/steering-ultra-20261014/`；[完整封存](../../.worktrees/exp/steering-ultra-20261014/checks/ultra-recovery-final-seal.json)、[30份视频](../../.worktrees/exp/steering-ultra-20261014/checks/video-health-recovery/index.md)与[全部尝试](../../.worktrees/exp/steering-ultra-20261014/checks/all-attempts-ledger.json)保留首轮、停止的重测和最终新组，原low数据未改写。
