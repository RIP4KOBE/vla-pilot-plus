# 主线发布与仓库整理记录 — 2026-10-15

本轮范围是发布、归档、整理和协作指导，不改变科学行为，不启动新的 GPU/API 实验。研究方向见 [Proposal](../research/research_proposal.md)，能力与结果见 [Progress](../research/research_progress.md)。整理已完成：原73个工作树收敛为1个，原76个本地分支收敛为main。原始检查保存在维护者本机 `.worktrees/exp/repository-maintenance-20261015/`。

## 发布身份

- 整理起点：main `6c0d72b7a56739ffc524b0e294c3c975d18c5ae4`。
- 首次 fetch：本地领先远端 18 个提交，远端无新增提交；扫描 277 个待发布 blob，未发现检查模式覆盖的凭据内容。这不是对所有历史的安全证明。
- 已普通推送上述提交到 `origin/main`，`ls-remote` 核对一致，作为远端回退点。未强推，未删除远端分支或标签。
- 最终发布：包含本报告和清理索引的main提交以普通push发布；可用 `git rev-parse HEAD` 与 `git ls-remote origin refs/heads/main` 核对。精确最终SHA与推送回执保存在维护目录的 `delivery-receipt.json`；受测 runtime 仍为 `c99565de6e34278c14518748d7c608433a4c529a`，不由文档提交替代。

## 清理分类与依据

完整列表在 [cleanup-inventory-20261015.json](cleanup-inventory-20261015.json)，记录每个历史分支的 tip、相对 main 的独有提交数、原工作树路径、静态快照路径和 bundle 身份。

| 分类 | 内容 | 依据 / 处理 |
| --- | --- | --- |
| 保留 | main 的 116 个冻结 runtime 文件、配置、提示词、资产清单、fixtures 和三模式入口 | 已验收身份；逐字节复核，不改变科学链 |
| 保留 | 其他 policy/backend、warm-start/可选 QD 接口、测试与旧配置 | 存在引用或扩展职责；最近未评测不等于废弃，未验收范围明确说明 |
| 保留 | 历史 `docs/00_overview` 至 `08_archive` 的研究记录 | 有引用、独有分析和历史证据；新增导航，保留原路径与字节 |
| 保留 | 根目录原有 5 个用户未跟踪文件 | 不丢弃、不混入本轮提交；逐文件 SHA 复核 |
| 归档 | 72 个历史工作树，合并为 13 个最外层快照组 | 全部文件（含 dirty、ignored、子目录和链接）复制并 checksum 验证，再退役注册 |
| 归档 | 全部 Git 管理状态与 all-ref bundle | 保留 76 个原分支 tip、独有提交和 detached HEAD；本地分支清理前独立验证 |
| 删除活动副本 | 75 个非 main 本地分支与 72 个工作树注册 | 成果留在已验证归档；旧路径用静态快照别名维持追溯 |
| 删除跟踪文件 | `pi05plot.py`、`plot_combined.py` | 无静态/动态入口、配置/CLI/测试/文档调用；硬编码的上游绘图数据/私人图片路径，不是本项目结果读取器 |
| 删除跟踪文件 | `cc_skills.md` | 过时的本机技能目录，含与明确禁用政策冲突的建议；政策统一到 AGENTS |
| 合并说明 | 旧 `CLAUDE.md` → 指向 `AGENTS.md` 的薄入口 | 删除“没有测试套件”等错误现状描述，不维护冲突规则 |
| 删除可再生缓存 | 主目录 `.pytest_cache`、`__pycache__` | 无运行任务依赖；只清这些根目录缓存，不清模型或封存实验缓存 |
| 待确认 / 保留 | 远端分支和标签、已有失效链接、资产公共分发 | 不在本轮远端删除授权内；不猜测修复历史链接，不声称公开资产已交付 |

根目录原有未跟踪文件：`HANDOFF.md`、`HANDOFF_REBOOT_PAUSE_20260923.md`、两份 2026-09 的 `docs/01_specs` 方案，以及 `docs/02_analysis/vls_guidance/2026-06-05-rdt-guided-denoise-loop-vls-steering-analysis.md`。它们保持原状；因此维护者本地 `git status` 仍会列出这 5 项，不表示发布提交混入了未验收文件。

## 归档布局与恢复

私有归档根：`/mnt/data/shared2/hynx/vla-pilot-repository-archive-20261015/`，仅作为维护者本地保存位置，没有公开下载服务。

```text
all-refs.bundle             原始 refs 与独有提交，SHA 见清理索引
bundle-heads.txt             精确 ref → commit 清单
git-admin/                  原 .git 管理状态，含工作树 index/refs 等
inventory-before.json       原工作树、状态、分支、受保护文件记录
cleanup-plan.json           执行前分类计划
workspaces/snapshot-01…13/  历史工作区完整静态副本
copy-receipt.json            复制/校验回执
accepted-cohorts/            新位置独立重审通过的代表性EDS完整副本
```

copy 使用不跟随符号链接的文件复制，逐组 checksum/元数据对比；外部模型、视频和既有数据盘目标继续保留在原位置，链接文本不改。5,376 个历史链接中，整理前已有 45 个目标不可达，原样登记；复制完成和退役后分别核对：72个原工作区地址均正确解析到归档，5,376个链接没有新增失效。不将45个既有缺口写成全部历史资产完整。系统盘可用空间由约4.2GiB恢复至186GiB。

静态副本中的原 `.git` 文件只是保存的字节；它可能指向已退役的工作树 metadata，**不是可直接继续开发的 Git 工作树**。从 main 开新功能分支进行工作；需要恢复历史时，在新目录从 bundle 恢复提交，再按清单恢复那一工作区独有的 dirty/ignored 文件。不得对共享 main 使用 reset 来恢复历史。

```bash
# 仅在需要恢复历史时；不是本轮自动执行的新工作树。
ARCHIVE_ROOT=/mnt/data/shared2/hynx/vla-pilot-repository-archive-20261015
git bundle verify "$ARCHIVE_ROOT/all-refs.bundle"
git clone --no-checkout "$ARCHIVE_ROOT/all-refs.bundle" /path/to/new-recovery-repo
# 在新 recovery repo 按清理索引选择原分支或提交，再恢复所需未提交文件。
```

旧 `.worktrees/exp/...` 地址与部分外部地址保留为兼容别名。当前 launcher 的 GPU 锁目录 `.worktrees/exp/steering-integration` 保留；没有因清理改写 runtime 的锁路径。新的开发从 main 开始，新的实验使用新的输出目录；这些别名不是新的活动工作区。

## 原始证据与复核

当前 low/ultra 六组结果保持原目录、原配置与原始 receipt。使用仓库现有 `prepare_steering_archive.py` 的 hash-bound support 机制和独立输出路径重新审计，未修改原 run。

| 协议 | EDS | VLS | EDS+QD | 本轮复核 |
| --- | ---: | ---: | ---: | --- |
| low / `33954ea` | 3/10 | 1/10 | 1/10 | 三组完整 v2 合同与记录机制审计通过 |
| ultra / `c99565d` | 3/10 | 1/10 | 0/10 | 三组完整 v2 合同与记录机制审计通过 |

另外将low EDS完整组复制到新归档位置 `accepted-cohorts/low-eds-preserved`，checksum一致且独立完整重审为有效3/10；原run未改写。

这次离线重审不重新执行模拟器，不重读全部模型权重，也不是新的在线成绩。视频完整解码依据原已封存检查；本轮不重复宣称重新解码了全部视频。新审计结果/支持文件位于维护目录的 `cohort-review/`、`archive-support/`，索引为 `cohort-review-index.json`；公开摘要见最终验证文件。

## 文档与来源处理

新增 `docs/research/research_proposal.md`、`research_progress.md`，统一根 `AGENTS.md`、README、CONTRIBUTING 与文档导航。保留 EDS 基线、区分已实现/已测试/已验收/研究设想；当前 QD 不包装成跨任务自我改进。

Notion 只读来源和读取失败范围记录在 [notion-source-20261015.json](../research/notion-source-20261015.json)。已读取 Proposal 的文字和标题，用户要求直接读取图片后也尝试了文件 URI；连接器拒绝该 URI，且没有提供二进制下载或签名 URL。26 张图片及书签细节仍未读取；v0.1 对这些部分明确留白，而非猜测原文。没有将整页私人材料或凭据加入 Git。

## 检查与限制

- 宿主进程/GPU核验无活动本项目实验；7 个运行锁可获取，当前用户 crontab 无项目队列。旧队列计划仍作为历史数据保存，不能从文件存在推断仍在执行。
- 归档/公共入口相关 CPU 回归：**144 passed、3 skipped**，11.89s；跳过的是原先仅用于外置候选的检查。没有新增镜像实现式测试。
- 六组已验收 cohort 共 60 回合重新审计通过，原 manifest/config/environment/audit/status 哈希保持。
- 116个runtime文件与受测冻结字节一致；20个RNG文件、2,308个LIBERO文件校验通过，三模式配置预览与5个CLI help通过，受保护5文件SHA保持。链接/归档和最终证据见[验证摘要](validation-20261015.json)；未因纯文档清理重跑GPU。
- Notion 图片细节、公共模型/原始数据分发、历史 45 个失效链接，以及未验收 backend/研究选项均是明确保留的限制。

## 合作者最短流程

```bash
git clone https://github.com/RIP4KOBE/vla-pilot-plus.git
cd vla-pilot-plus
git switch -c codex/my-qd-hypothesis
```

先读 README → Proposal → Progress → AGENTS；按安装文档取得并校验资产、准备自己的 Codex 登录和 `configs/local.yaml`，预览三模式配置。以当前 EDS 为对照，每个 PR 只提出可归因的机制变化；运行相应检查与登记后的实验，更新 Progress，推送功能分支并提交 PR。
