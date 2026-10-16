# VLA-Pilot++ 开发指导

## 目的与权威入口

研究冻结 VLA/RDT 的 inference-time steering，在 EDS 基础上引入 quality-diversity，探索有用的行为多样性和执行反馈驱动的改进。先读 [Proposal](docs/research/research_proposal.md)、[Progress](docs/research/research_progress.md)，运行与安装读 [README](README.md)。本文件为仓库统一 agent 指导。

当前已验收：VLS、EDS、EDS+QD 共同框架；ObjectSwap OOD low 成绩依次 1/10、3/10、1/10，ultra 及新环境独立复测均为 1/10、3/10、0/10。不同协议与评测组分开报告；[新环境验收](docs/steering/onboarding-validation.md)记录安装范围与限制。当前最可靠对照为含 RBF 的 EDS；QD 尚未证明优势。默认 archive 每动作块重建，不能宣称跨块/跨任务学习或 recursive self-improvement 已实现并验收。

## 目录与入口

| 路径 | 职责 |
| --- | --- |
| `scripts/run_steering.py` / `evaluate_steering.py` | 三模式公共 launcher，冻结、进度与运行审计 |
| `scripts/check_steering.py` / `prepare_steering_assets.py` | 预检、固定资产、显式依赖兼容补丁与机器配置 |
| `scripts/list_steering_devices.py` | NVIDIA/CUDA UUID 与 EGL 编号映射；实际 render 仍由预检核验 |
| `scripts/audit_steering.py` / `audit_qd_mechanism.py` | cohort 有效性、合同与机制重建 |
| `configs/evaluation/`、`configs/steering/` | 科学协议及方法差异 |
| `configs/local.yaml`（ignored） | 路径、GPU/EGL；不放凭据 |
| `main.py`、`core/env_adapters/` | 观测、动作转换与执行/反馈 |
| `core/rdt_policy_steer.py` | 共用 RDT、VLS/EDS 搜索与候选选择 |
| `core/qd_ed.py` | descriptor、档案、精英与父代 |
| `core/stage/`、`core/online/` | Stage 控制、视觉事实、Codex 请求与捕获 |
| `core/diagnostics/` | 显式离线 Stage 回放；不能计入在线成绩 |
| `core/target_distance_reward.py`、`vlm_query/target_distance/` | reward 合同与受控提示词 |
| `tests/`、`docs/steering/`、`docs/research/` | 回归、验收证据、研究方向/进展 |

公共方法名为 VLS/`vls`、EDS/`eds`、EDS+QD/`eds_qd`。QD 扩展 EDS 的档案/父代过程，不复制全套推理代码。旧安装配方和 shell 入口已退役；使用 `*-steering*` 配方及公共 launcher。其他 policy/backend 源码暂留兼容，尚不属于当前验收范围。

## 科学行为与实验有效性

- 开发 QD 时保留 `eds` 关闭 archive 的对照；新增选项显式配置，默认行为和 reference 不顺手重写。
- 模型/依赖、输入/预处理、初始化/RNG、提示词/Stage/reward、候选投影、动作切片/夹爪/执行长度、评分运算顺序/dtype、RBF、父代/精英/archive、缓存或服务参数的变化都可能改变科学条件。登记新配置、解释影响并验证；旧成绩不证明修改后的行为。
- 默认 ObjectSwap 十任务和 seed/prepare-rollout RNG fixtures 固定。任务子集、seed 与 episode ordinal 不是可互换的身份；不要用单任务补跑拼接完整 cohort。
- 当前在线协议为 Codex CLI / `gpt-6-astra` / `ultra`，身份/reward 每任务 fresh，Stage 使用当前观测在线评估。reward 候选评分在本地。没有 Poe 或静默 provider fallback；模型/effort/transport 修改需明确登记。
- replay/缓存可用于离线诊断，不能计入 fresh 在线成绩。服务端输入 token 缓存与本地回复回放分开记录。
- 环境 success、机制有效性和基础设施状态分开报告。保留合法失败、服务错误和未完成运行；不得挑选成功回合、放松 gate 或修改原始 receipt 来“恢复成绩”。
- 默认方法计算预算不同，报告真实模型 calls/batch rows、评分/梯度、在线请求/重试与墙钟时间。不要把等待时间写成 GPU 活跃小时。
- 运行期间固定源码、依赖、资产与配置，使用新 run ID。已有目录不覆盖；中断后先核对状态再决定如何继续，保留独立尝试记录。
- 使用已分配且空闲 GPU，核对 GPU/EGL 映射、进程与锁。当前用户授权所有可用 GPU，不限 GPU2；不终止其他项目任务。不要从已废弃历史方案引入预算上限或重复审批。

## 检查与证据

新环境按安装文档执行 `install-runtime-compat` 和 `verify-runtime-compat`，显式恢复固定 Robosuite 兼容文件。预检/launcher 会检查哈希，原始依赖版本号和 `pip check` 不能替代该核验；不要靠手改旧环境完成安装。

按改动范围验证：文档/无引用文件清理检查链接、引用和证据；路径/launcher/归档改动运行相关 CPU 回归；搜索/Stage/动作等科学变更需要行为回归和明确登记的在线验收。无需为纯文档重跑 GPU 实验。

```bash
# 在按安装文档配置的 Python 环境、仓库根目录执行。
python scripts/run_steering.py --method eds --local-config configs/local.yaml \
  --output-dir outputs/config-preview --print-config
env -u VLA_CODEX_ONLY CUDA_VISIBLE_DEVICES='' PYTHON_DOTENV_DISABLED=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  python -m pytest tests -q --disable-warnings -p no:cacheprovider
python scripts/audit_steering.py /path/to/completed-run --no-write
```

配置预览不验证模型/GPU/API；CPU 命令不等于网络隔离。必要时按 [CONTRIBUTING](CONTRIBUTING.md) 完成相关负例/回归。完整在线命令和搬迁后审计在[评测文档](docs/steering/evaluation.md)。

记录 runtime commit、source/config/asset hash、环境、任务/seed、在线捕获、逐任务结果、审计器身份、日志与视频位置。原始 evidence 不改字节；移动后新增映射/support/审计报告。大型模型和产物放外部归档，Git 只保存必要小型报告、配置、索引与 fixtures。没有公共模型包时明确说明，不声称 clone 即可复现。

`.worktrees/exp/` 中的历史别名与归档只作证据来源，不作为新开发入口，不修改封存数据。不要因路径名称包含旧版本号而重命名哈希固定的刺激、source/capture blob。历史版本映射在 README provenance 和维护报告。

## 协作与文档维护

先检查 git 状态和现有进程，保护用户未提交内容；从最新 main 创建 `codex/<topic>` 功能分支。提交应聚焦、可审核，PR 说明问题、最终行为、科学影响、验证与限制。普通 push，不强推共享历史；提交/推送按当前用户授权及仓库流程，不自动继承一次性发布任务的未来授权。

新工作树仅在任务需要且有授权时使用；本轮整理不新建工作树。删除前确认独有提交、dirty 文件、ignored 产物、符号链接与活动任务，可靠归档并验证后再清理。保留其他合作者工作，不重置来消除冲突。

每次机制合入或完整实验完成更新 Progress；假设/路线变化更新 Proposal 并标明证据。研究设想、可选未验收接口与默认已验收功能分开写。具体状态以仓库和报告为准，不只依据聊天记录。

## 技能与代理政策

- Superpowers 插件及全部 `superpowers:*` 技能禁用。不要安装、加载、为任务执行检查、调用或推荐；`disabled-skills`、临时副本和远端缓存不是可用技能。仅用户明确撤销本政策才能重新启用，提及名称不构成授权。
- Arbor（`arbor-research-agent`、所有 `arbor-agent-*`）与既有 Orchestra Research `autoresearch` 默认不激活。仅用户明确调用命名技能才使用；研究关键词、相似任务或其他技能推荐不构成调用授权。
- Arbor 公共入口为 `arbor-research-agent`；用户将 RUC-NLPIR/Arbor 称为 autoresearch 时使用该入口，与 Orchestra 的同名技能区分。安装/维护可检查其文件但不启动研究流程。授权只持续到所调用任务结束。
- 更新这些技能时保留 `policy.allow_implicit_invocation: false`，除非用户明确更改政策。
- 不主动创建 subagent；只有用户或适用指令明确要求代理分工/并行代理时才委派。常规独立检查可并行工具执行。
- 不自行创建 goal、预算或额外审批流程。遵守当前会话已明确的授权边界。
