# VLA-Pilot++ 开发指导

## 项目目标与阅读顺序

研究冻结 VLA 的 inference-time steering：在完成主要任务的同时，利用 quality-diversity（QD）保留多种高质量行为，以适应用户偏好、环境约束与风险变化。EDS 是搜索基础，EDS+QD 扩展行为档案、精英和父代；VLS 是共同框架中的对照。跨执行策略演化及向 VLA 蒸馏是未来 Agentic recursive self-improvement（RSI）路线。

1. [Proposal](docs/research/research_proposal.md)：研究动机、方法思想、假设和 Future Work；不放实现流水。
2. [Progress](docs/research/research_progress.md)：主线实现、有效结果、缺失能力和下一步验收。
3. [Project Overview](docs/project_overview.md)：目录、代码职责、数据流与贡献入口。
4. [README](README.md)、[CONTRIBUTING](CONTRIBUTING.md)：安装运行与协作；本文件是统一 agent 指导。

当前 RDT 三模式已完成共同框架验收。EDS（含 RBF）是最可靠研发对照；QD 已实现并通过机制/完整运行审计，但尚未证明性能优势。具体模型、benchmark、low/ultra 及独立评测结果以 Progress 分组记录为准。默认每动作块重建 archive，不能宣称持久 QD、跨任务学习、偏好适应或 RSI 已经实现并验收。

π0.5 + VLS 已在标准 LIBERO Object 完成独立十任务验收（9/10，10/10 有效）；不能与 RDT ObjectSwap 直接排名，也不能据此证明相对无引导 π0.5 的增益。π0.5 EDS/QD 尚未支持。

## 主要入口与扩展边界

| 入口 | 职责 |
| --- | --- |
| `scripts/run_steering.py`、`scripts/evaluate_steering.py` | 三模式公共启动、冻结、进度与审计 |
| `configs/evaluation/`、`configs/steering/` | 共同科学协议与 `vls`、`eds`、`eds_qd` profile |
| `main.py`、`core/env_adapters/` | 任务准备、观测、动作执行与反馈 |
| `core/rdt_policy_steer.py`、`core/qd_ed.py` | 共用 RDT/VLS/EDS 搜索；描述符、档案、精英、父代 |
| `core/pi05_steer.py`、`scripts/run_pi05.py`、`scripts/audit_pi05.py` | π0.5 VLS 的独立模型适配、标准 LIBERO 协议与审计 |
| `core/stage/`、`core/online/` | 控制决策、视觉事实与 Codex 请求/捕获 |
| `vlm_query/`、`core/target_distance_reward.py` | 任务内容生成、提示词与本地 reward 合同 |
| `scripts/check_steering.py`、`scripts/prepare_steering_assets.py` | 预检、固定资产、显式依赖兼容与机器配置 |
| `scripts/prepare_public_models.py`、`scripts/public_model_sources.json` | 固定公开模型来源、下载/核验与 π0.5 配置；访问许可由使用者取得 |
| `scripts/audit_steering.py`、`scripts/audit_qd_mechanism.py` | 完整运行有效性与独立机制重建 |
| `tests/`、`docs/steering/` | 行为参考、CPU 回归、验收与证据索引 |

QD 复用 EDS 搜索，不复制整套推理代码。开发描述符、档案、父代与反馈时保留关闭 archive 的 `eds` 对照；新选项显式配置，不顺手重写默认 reference。兼容 backend、可选 memory/anchor/secondary 等接口不自动继承默认验收。仅按文件名或近期是否调用，不能认定模块无用；例如 Codex 仍复用 `gemini_grounder.py` 的基类和工具。

## 科学条件与实验有效性

- 模型/依赖、输入/预处理、初始化/RNG、提示词/Stage/reward、投影、动作切片/夹爪/执行长度、评分顺序/dtype、RBF、父代/精英/archive、缓存或服务参数的变化都可能改变科学条件。登记影响并验证，旧成绩不能证明新实现。
- 当前 RDT ObjectSwap 协议固定十任务、seed 与 prepare/rollout RNG fixtures。任务子集、seed 和 episode ordinal 不可互换；单任务诊断不得拼接为完整 cohort。
- 当前在线主协议是 Codex CLI / `gpt-6-astra` / `ultra`：任务身份、阶段和 reward fresh 生成；Stage 按触发条件评估当前观测；候选 reward/梯度在本地计算。不使用 Poe 或静默 provider 回退。模型、effort、transport 改动单独登记。
- `core/diagnostics/` 的 replay/缓存仅用于离线诊断。服务端输入 token 缓存与本地回复回放分开记录；不能将回放列入 fresh 在线成绩。
- 环境成功、机制有效性和基础设施状态分开报告。保留合法失败、错误和未完成运行；不挑成功回合、不放松 gate、不改原始 receipt 来恢复数值。
- 预测 reward、档案占用率与实际执行收益不同。未执行候选没有真实成功标签；块内搜索、跨执行适应和多轮 RSI 分开表述。QD 收益需排除普通精英保留、更多计算/记忆/重试等解释。
- 方法默认计算量不同，报告实际模型 calls/batch rows、评分/梯度、在线调用/重试和墙钟时间；等待时间不是 GPU 活跃小时。冻结运行时源码、依赖、资产和配置，使用新 run ID；中断后核对状态，避免重复或覆盖。
- 使用已授权且空闲的 GPU，核对 GPU/EGL 映射、进程与锁。当前用户授权所有可用 GPU，不限 GPU2；不终止其他项目任务。不得从历史方案恢复旧预算上限或重复审批。

## 检查、产物与证据

文档/无引用文件清理检查链接、引用和证据；路径/launcher/归档改动运行相应 CPU 回归；模型、搜索、Stage/reward 或动作等科学变更需要行为检查及明确登记的在线验收。纯文档不重跑 GPU 实验。

在安装指南配置的环境、仓库根目录执行：

```bash
# 仅配置预览，不验证模型、GPU 或在线服务。
python scripts/run_steering.py --method eds --local-config .local/rdt.yaml \
  --output-dir outputs/config-preview --print-config
# CPU 回归；不是通用网络隔离。
env -u VLA_CODEX_ONLY CUDA_VISIBLE_DEVICES='' PYTHON_DOTENV_DISABLED=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  python -m pytest tests -q --disable-warnings -p no:cacheprovider
# 将路径替换为实际已完成运行目录；只读审计。
python scripts/audit_steering.py /path/to/completed-run --no-write
```

新环境按安装指南执行 `install-runtime-compat` 和 `verify-runtime-compat`，显式恢复固定 Robosuite 兼容文件；依赖版本号或 `pip check` 不能替代文件哈希核验，不靠旧环境手工补丁完成安装。机器路径/GPU 配置按 README 放 ignored `.local/`；`configs/local.yaml` 仍可用，凭据不入 Git。

每个实验记录研究问题、runtime commit、source/config/asset hash、环境、任务/seed、服务条件、尝试/纳入规则、逐任务结果、计算量、日志/视频与审计器身份。大型模型和产物放现有外部归档；Git 保留必要小型报告、配置、索引和 fixtures。明确公开获取与本机验证的实际范围，不声称 clone 自动包含所有资产。

原始 evidence 保持字节和哈希；搬迁通过新增映射/support 与重审记录追溯。`.worktrees/exp/` 中历史别名/归档仅作证据，不修改封存数据，不重命名哈希固定的 source/capture/刺激文件。不能让当前运行从旧工作树隐式导入。历史名称与提交映射见 [provenance](docs/steering/provenance.md)。

## 协作与文档维护

先核对 Git 状态、远端和活动任务，保护既有未提交内容与冻结源码。通常从最新 main 派生 `codex/<topic>` 功能分支；明确授权的主线文档任务按用户范围执行。多人共享同一目录时先协调写入与分支切换，不能为整理中断他人实验。

提交应聚焦、可审核；PR 说明问题、最终行为、科学影响、验证与限制。普通 push，不强推或覆盖共享历史。提交/推送依当前用户授权及流程，不自动继承一次性发布任务的未来授权。新工作树仅在需要且获授权时使用；文档整理不新建工作树。删除前确认独有成果、dirty/ignored 文件、链接和活动进程，并可靠归档核验，不重置来消除冲突。

机制合入或完整实验完成更新 Progress；假设/路线变化更新 Proposal；目录/接口变化更新 Overview；入口和验证流程变化同步 README/AGENTS。研究设想、可选未验收接口与已验收默认能力分开写，以当前源码和报告为准，不仅依赖聊天记录。

## 技能与代理政策

- Superpowers 插件及全部 `superpowers:*` 技能禁用。不要安装、加载、为任务执行检查、调用或推荐；`disabled-skills`、临时副本和远端缓存不是可用技能。仅用户明确撤销本政策才能重新启用，提及名称不构成授权。
- Arbor（`arbor-research-agent`、所有 `arbor-agent-*`）与既有 Orchestra Research `autoresearch` 默认不激活。仅用户明确调用命名技能才使用；研究关键词、相似任务或其他技能推荐不构成调用授权。
- Arbor 公共入口为 `arbor-research-agent`；用户将 RUC-NLPIR/Arbor 称为 autoresearch 时使用该入口，与 Orchestra 的同名技能区分。安装/维护可检查其文件但不启动研究流程。授权只持续到所调用任务结束。
- 更新这些技能时保留 `policy.allow_implicit_invocation: false`，除非用户明确更改政策。
- 不主动创建 subagent；只有用户或适用指令明确要求代理分工/并行代理时才委派。常规独立检查可并行工具执行。
- 不自行创建 goal、预算或额外审批流程。遵守当前会话已明确的授权边界。
