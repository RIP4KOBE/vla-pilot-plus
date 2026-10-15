# VLA-Pilot++: RDT steering

用共享的机器人观测、在线视觉 Stage 控制器和执行链，研究三种 RDT 推理方法：**VLS、EDS、EDS+QD**。重点是比较动作候选如何生成和选择，并保留足够证据解释每次运行。

> **整合草稿，尚未发布。** 当前公共入口只开放 EDS，十任务迁移验收仍待结案。VLS / EDS+QD 的公共配置、统一 Stage 进度接口和同条件对照待完成。本文中的“待接入”命令不能视为已发布功能。

| 方法 | 候选生成与选择 | 当前状态 |
| --- | --- | --- |
| VLS | 去噪过程中使用 reward 梯度、多样性梯度和可选 FKD 粒子重采样 | 内部实现存在；公共 profile 与统一 Stage 接口待接入、待评测 |
| EDS | RBF 多样性采样，reward 评分，父代重采样、重新加噪和截断去噪 | 公共入口可用；完整迁移验收待结案 |
| EDS+QD | 共用 EDS 搜索引擎，开启当前动作块内的行为网格 archive | 内部实现存在；公共 profile、机制验收和性能评测待完成 |

QD archive 不跨任务积累知识；这里没有已经验证的递归自我改进系统。VLS 与 EDS 的现有候选数和计算路径不同，不能把默认设置称为等计算预算对照。

## 开始使用

先按 [安装与资产](docs/steering/installation.md) 创建隔离环境、准备固定资产和机器配置。干净环境已通过真实入口导入、processor 行为检查及 **1118 项 CPU 测试**。这项验证不包含新环境的 GPU 推理或在线模型调用。

以下是**当前已有 CLI**，在仓库根目录、已激活的环境执行。示例路径需要替换，输出目录必须是新的目录。

```bash
# 只解析配置，不创建运行目录，不使用 GPU/API。
python scripts/run_steering.py --method eds \
  --local-config /path/to/local.yaml --output-dir outputs/eds-preview \
  --print-config

# 显式检查本机 GPU/渲染与一次真实 Codex 图像请求；不是任务成绩。
python scripts/check_steering.py --local-config /path/to/local.yaml \
  --output-dir outputs/preflight-001 --gpu --api

# 一个任务的诊断运行；不能记作 full10 结果。
python scripts/run_steering.py --method eds --tasks 0 \
  --local-config /path/to/local.yaml --output-dir outputs/eds-diagnostic-001

# 完整十任务；不传 --tasks，固定任务与 seed 配对。
python scripts/evaluate_steering.py --method eds \
  --local-config /path/to/local.yaml --output-dir outputs/eds-full10-001

# 重算已有运行的基础完整性审计；会更新该目录的 audit.json。
python scripts/audit_steering.py outputs/eds-full10-001
```

在线路径使用 **Codex CLI、gpt-6-astra、low reasoning effort**，需要使用者自己的有效 CLI 登录。每个任务新生成 reward 和身份描述，Stage 随执行在线查询。机器配置只保存资产位置与设备选择；不要把登录信息写入其中。调用记录能证明本地请求参数与收到的 transport 元数据，不能独立证明服务端实际运行的模型权重或路由。

目前不要通过手动修改冻结运行配置启用其他方法。待统一接口、profile 和验收完成后，本节才加入 VLS / EDS+QD 的正式命令。

## 结果与可复现范围

| 方法 / 验证 | 完整有效 cohort | 成功数 | 证据 |
| --- | --- | --- | --- |
| EDS 迁移 | 待完成最终审计 | 待填；不由部分任务推算 | 待填：最终 commit、run manifest、audit、逐任务结果 |
| VLS 同条件对照 | 未运行 | — | 待公共 profile 和统一 Stage 接口验收 |
| EDS+QD 同条件对照 | 未运行 | — | 待 archive 机制与公共 profile 验收 |
| 干净环境 CPU 验收 | 不适用 | 不适用 | 1118 passed、1 warning、86.53s；没有 GPU/API/模型推理 |

任务失败只有在运行证据有效时才计入成功率分母。依赖错误、模型/服务失败、缺捕获、初始化失败、配置或源码漂移不能伪装成一个有效的 0/10。一次固定十任务结果也不能替代多 seed 或独立任务集的统计结论。

运行目录保存配置、源码身份、环境与资产记录、控制器事件、计算量、在线调用证据和视频。视频可帮助解释行为，但环境 success 与审计决定其是否成为有效成绩。[架构说明](docs/steering/architecture.md) 解释算法和证据边界；[协作指南](CONTRIBUTING.md) 解释修改、对照与验收流程。

## Provenance 与本地证据

本节保留来源名称，仅用于追踪来源，不作为公共方法命名。以下记录属于迁移前后不同证据，不能合并成同一次实验。

| 来源 | 身份 / 含义 |
| --- | --- |
| 原 main | `d51cb85f485502e0429c79529872efef2ec59981` |
| 来源研究 worktree | `.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-gpu6-20260922T063626Z/study_worktree`；来源 HEAD `77761b4cda78ac3b6762a6aa60f97b07fde7c1dc` |
| 来源在线 baseline | `codex_failed_contact_v17_historical_initialization_online_full10`，位于来源 worktree 的 `artifacts/stage_closed_loop_20260929/runs/`；该来源轮次 **3/10、QD 关闭**，不是新的迁移结果 |
| 来源快照 | 验收 manifest 覆盖 48 个文件，其中 37 个 untracked、5 个 modified、6 个 clean；直接 merge 来源 HEAD 会漏文件 |
| 整合分支与冻结点 | `codex/rdt-steering-integration`；EDS 冻结 commit `cfecb12db736f1a3408d9528d9336aadcb7e41b5`；最终合并 commit 待填 |
| 新 EDS cohort | `.worktrees/exp/steering-integration/runs/eds-migration-20261013`；最终状态与结果待结案 |

源码按职责迁移：`core/c0_reward_contract.py` → `core/target_distance_reward.py`；`core/poe_stage_capture.py` → `core/stage_capture.py`；提示词目录 `vlm_query/c0_contract_v1` → `vlm_query/target_distance`；reward 合同 `c0_xyz_v1` → `target_distance`。控制器 profile `evidence_v1/contact_v2/grasp_v3/proprio_v4` 分别映射为 `evidence/contact/grasp/online`。

科学提示词保持原字节，包括其中两处 **C0** 字样。这是冻结实验输入的兼容例外，不是公开算法名称；文字清理会改变在线模型 stimulus，应作为新的实验条件评审。

当前证据只在维护者机器保存，**没有在此声明公开下载地址**。新 clone 不应依赖这些目录运行单元测试。协作者需要维护者分享明确归档，或自行创建新的运行目录。

- 迁移 CPU 日志：`.worktrees/exp/steering-integration/checks/cpu-migration.log`，1118 passed、2 warnings、82.42s。
- 干净安装日志：维护者本机 `/mnt/data/shared2/hynx/steering-integration-envs/clean-20261013-01/` 下的 `validation-summary.json`、`logs/pytest.log`、`logs/pip-check.log`、`logs/clean-import-versions.json`、`logs/processor-behavior.log`、`logs/worker-cfg.log`。该环境的 CPU 验收与在线 cohort 环境分别记录。
- 待整合证据包：`.worktrees/exp/steering-integration/pending-integration/`，含安装输入、独立审计与资产验证材料；它不是已经应用到 runtime 的功能清单。
- 上表 cohort 目录含 `manifest.json`、`resolved-config.yaml`、`environment.json`、`progress.json`、`status.json`、`console.log`、`audit.json`，以及 `eds_eval/`、捕获目录和各 episode 视频。请以实际文件及最终归档索引为准，勿将缺失视频写作已提供。

发布时待补：可供协作者访问的证据归档链接、最终结果表、最终 commit 和三模式正式命令。此 README 草稿不代表这些项目已完成。
