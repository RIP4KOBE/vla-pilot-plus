# 控制代码整理、研究分支收敛与开源入口发布

日期：2026-10-15。工作起点 `e8a3b6a76172431b6f3f510ceb25b3afd10e8730`。控制重构提交 `cca0210`，旧文件退役提交 `293450e`，用户原有导航文件删除单独保存在 `1892335`。
本轮为保持行为的组织重构和仓库整理，没有新增在线成功率结果。

## 控制代码

原 15 个 `stage_*`、3 个 `codex_*` 和 1 个 trace replay 模块，共 19 个散落文件，整理为 10 个实现文件和 3 个仅含说明的包入口：

| 包 | 实现文件 | 职责 |
| --- | --- | --- |
| `core/stage/` | `controller.py`、`contract.py`、`observation.py`、`grasp.py`、`carry.py`、`recovery.py` | 调度与门控、响应校验、身份/当前图像、机器人一致性、carry 保持、恢复与释放 |
| `core/online/` | `codex.py`、`policy.py`、`capture.py` | 共用 CLI/视觉传输、调用策略、兼容接口捕获 |
| `core/diagnostics/` | `stage_replay.py` | 历史回复回放与输入捕获 |

[模块映射](control-module-map-20261015.json)列出逐文件来源。公共入口、测试和当前文档均改用新路径，不在根目录遗留一批转发包装文件。

本轮不改阈值、决策顺序、reward、提示词、RNG 或动作行为。Codex 的异常类名称和兼容 Stage 类保持，便于既有诊断；`gemini_grounder.py` 仍提供兼容基类及工厂，并非默认切回旧 provider。

`steering_source_layout.py` 为审计器提供新旧布局识别。审计旧 cohort 时读取其原始文件与哈希；审计新布局时要求完整的新路径集合，拒绝缺失、混用旧路径回退或哈希不符。原始 fixture/source blob 和实验 receipt 未改写。

## 验证

详见[检查记录](control-layout-validation-20261015.json)。

- 421 项 Stage/Codex 定向 CPU 测试通过。
- 全套 CPU 回归：**1449 passed、3 skipped、1 warning，136.17 秒**。三项跳过为既有外置候选配置检查，不是本轮失败被隐藏。
- 原 19 模块的 66 个函数/类 AST 节点与 20 个模块级常量保持一致；对照仅忽略导入变化，并补偿迁移后 `__file__.parents` 的目录深度。
- RDT 搜索、QD、reward 合同、科学配置和提示词共 43 个文件字节不变。
- EDS 合成 CPU 闭环继续匹配冻结 reference，包含 float32/bfloat16 的动作、Stage、父代和 RNG 轨迹，以及错误动作负例。以整理前源码和整理后源码分别运行同一 harness，行为记录 SHA-256 完全相同；补充的最终 harness 三项检查全部通过。
- 新增审计负例检查新布局缺少 policy、混用旧路径、修改 marker 源码；旧布局 fixture 仍能审计。
- 对真实历史 `eds-common-20261013` 执行只读完整审计，**有效 10/10，成功 3/10**。这不是重新执行十回合；结果仍绑定原 runtime。

CPU 回归不替代新在线模型/仿真评测。本轮不声称整理后的提交取得了新的 3/10。

## 分支和历史索引

目标是 **main + 23 个与本地源码目录同名的研究分支**，共 24 个；目录 `.worktrees/exp/X` 对应 `exp/X`，`.worktrees/feat/X` 对应 `feat/X`。具体清单见[分支索引](branch-index.md)。

原 98 个非 main 尖端先保存为 `history/20261015/<旧分支名>` 标签并核验，然后才移除 94 个被替代的分支引用。4 个保留同名分支正常推进；其中 `exp/eds-init-pg-diverse-sampling` 使用双父提交保留旧远端历史，完整 tree 与已验证的历史源码快照相同，没有强制覆盖共享历史。删除采用精确旧 SHA lease，防止删除协作者并发更新。

4 个归档/评测管理目录和 1 个仅剩配置的目录不建立算法分支；文件保持原位。更深层研究变体通过标签及机器索引查找，避免每个 runner 变体再增加顶层分支。

已独立查询 GitHub 并核实：**24 个分支、98 个历史标签、94 个旧分支删除完成**，原 98 个非 main 尖端全部保留。逐项对应和哈希摘要见[远端核验](branch-consolidation-validation-20261015.json)。GitHub 曾多次出现 TLS 连接中断；每次重试先查远端状态，未核验前不删除，最终通过保留证书校验的连接完成。

## 文件与文档清理

- 退役 `run.sh`、`setup.sh`、`scripts/run_libero_suites.sh`、`environment.yml`、`requirements.txt`：当前统一使用经过验证的 steering 安装/运行入口；旧 backend 源码不随之删除，历史安装配方仍可从 Git 获取。
- 删除无调用的 `core/sam_refiner.py`。其他 SAM 实现及环境后端保留。
- 用户原有 `CLAUDE.md` 删除单独提交；统一使用 `AGENTS.md`。
- 本轮六项新增退役文件的原始哈希与恢复地址见[清单](public-release-retired-files-20261015.json)。上一轮八项清理及 HANDOFF 归档仍保留完整记录。
- README 参考 [Psi0](https://github.com/physical-superintelligence-lab/Psi0) 的项目介绍、导航、安装、运行、开发和引用组织方式重写，采用英文项目入口。没有复制其模型、成果、作者或许可主张。
- 运行时提交/本机路径/原始实验索引移入 [provenance](../steering/provenance.md)，当前 README 以方法、使用和协作为中心。研究和工程细节继续在中文专门文档维护。
- Proposal/Progress、AGENTS、架构文档和导航同步到新目录。历史来源索引保留原提交身份，浏览链接改到对应历史标签；科学证据文件未改字节。

## 后续开发

从远端 main 新建 `codex/<topic>`，保留 EDS 对照。QD 改动集中在 `core/qd_ed.py` 和公共 RDT 搜索接口；控制改动在 `core/stage/`；服务改动在 `core/online/`。任何科学条件变化仍需登记并补足对应验收。

当前限制保持明确：完整模型和原始录像没有公共下载包；当前 QD 没有显示优于 EDS；跨块/跨任务 recursive self-improvement 尚未验收。历史源码发布副本的脱敏边界见原发布报告。
