# main 保留范围与 Stage/Codex 依赖审查

核对日期：2026-10-15。核对基点：`5a9ea577bb4b8e2e74078de859315f48072df88f`。
本次是静态引用、配置和调用路径审查，没有改变运行时源码，也没有重跑 GPU 实验。
未发现引用不等于证明外部调用不存在；下述“可移除”均说明具体边界。

## 1. 主线范围

主线保留 RDT + LIBERO ObjectSwap 下的 VLS、EDS、EDS+QD 共用框架，包括观测/动作语义、在线 Stage、fresh reward、初始化与有效性审计。
当前 EDS 是已验收的 3/10 对照。QD 默认档案每动作块重建；可选接口存在不代表跨块学习已验收。
详见 [Proposal](../research/research_proposal.md)、[Progress](../research/research_progress.md)、[算法合同](../steering/architecture.md)。

## 2. 清理候选

| 类别 / 文件 | 证据与用途 | 是否可以移除 |
| --- | --- | --- |
| `utils/hydra_plugins/task_searchpath.py`、包目录 | 主体 `manipulate_search_path()` 为 `pass`；本仓库没有发现插件注册或调用 | 低风险候选；移除前检查 Hydra 兼容入口及安装侧注册 |
| `core/sam_refiner.py` | 本仓库未发现导入；保留独立 SAM 细化实现 | 可归档后移出 main；需要明确不再提供此可选接口 |
| `ablations/door_left_*.yaml`（4 个） | 旧 CALVIN/VLS 消融，不是 ObjectSwap QD profile；当前 launcher 不加载 | 可归档后移出；不能误删当前 `configs/steering/` |
| `utils/plot_results.py` | 独立绘图工具；没有发现当前运行链调用 | 可移至工具/历史归档；其余 `eds_*vis.py` 和 `vis_utils.py` 有实际调用 |
| `.gitmodules` 的 `sam3` 条目 | 当前 HEAD 只有 `calvin`、`lerobot`、`rdt` 三个 gitlink，无 `sam3` gitlink | 可移除孤立配置项；需要核对安装文档和子模块命令 |
| `NOTES.md` | 仅项目创建信息，与 README 有少量重复 | 可合并后移除，非算法代码 |
| `run.sh`、`setup.sh`、`scripts/run_libero_suites.sh` | 旧通用入口；`setup.sh` 仍包含 Poe 提示，`run.sh` 不加载已验收公共协议 | 建议退役或改成明确导航；不能继续当作当前复现入口 |
| `environment.yml`、`requirements.txt` | 旧依赖配方，与 `*-steering*` 当前配方并存 | 可随旧入口一起退役；先检查兼容 backend 的保留要求 |
| `docs/00_overview`、`01_specs`、`02_analysis`、`03_evidence`、`04_plans`、`05_runs`、`08_archive` | 历史设计、诊断和证据；含跨文档引用 | 可以整体移到远端归档并保留索引；属于研究证据，不是“无用代码” |
| 根目录 `HANDOFF.md` 及本次纳入的三份旧文档 | 用户原有未跟踪材料，描述旧日期的研究状态 | 原字节纳入 Git；通过文档索引标记过时，不覆盖当前 Progress |

以上是本次交付的删除分析，不在归档发布中顺带改变运行边界。当前公共运行时文件保持不变。

## 3. 有引用的兼容功能，需要成组退役

- `core/pi05_steer.py`、`core/diffusion_policy_steer.py`：`main.py` 在对应 policy 分支中导入；未参与本轮 RDT 成绩不等于无用。
- `core/env_adapters/calvin_adapter.py`、`configs/backend/calvin.yaml`、`configs/env/calvin.yaml`、`configs/task/`、`patches/light.py`：存在环境工厂、配置别名及 `main.py` 顶层补丁引用。若收缩为 RDT/LIBERO 专用，需要一起处理入口、依赖、测试和文档。
- `core/sam_segmenter.py`：由 `core.__init__` 的公开懒加载工厂提供；`sam3_segmenter.py` 由 `main.py` 导入，是否实例化由配置决定。
- `core/gemini_grounder.py`：除了旧 provider，还承担当前 Stage recognizer 工厂；`stage_observation.py` 也导入其基类与图像编码函数。公共 Codex 路径仍需要该模块可导入，不能因名字直接删除。
- `core/trace_replay_stage.py`、`stage_capture_trace_replay.py`：工厂保留明确 replay backend，供历史诊断与回归。可将来抽到 diagnostics，但需保留复现能力。
- `core/rdt_policy_steer.py`、`qd_ed.py` 内未默认启用的 memory/descriptor/parent 选项：其中一部分与 Proposal 后续方向直接相关，不适合以“本轮没用”为由删除。

## 4. `core/stage_*` 是否必要

Stage 是三种搜索方法共用的控制层。它会影响引导开关、完成证据、reward reference、接触宽限与失败恢复；移除或改写即改变科学条件。

| 模块 | 实际调用关系 / 默认作用 | 结论 |
| --- | --- | --- |
| `stage_evidence.py` | `main._update_stage()` → `update_stage()`；默认 `stage_controller=online` | 必需 |
| `stage_contact_handoff.py` | evidence 控制器读取距离、应用 contact handoff；guard 也使用 | 必需 |
| `stage_robot_evidence.py` | online 路径检查机器人观测、目标几何、恢复优先级 | 必需 |
| `stage_failed_contact_recheck.py` | 默认开关 true；evidence 更新与审计器引用 | 必需 |
| `stage_carry_hold.py`、`stage_fused_carry_hold.py` | 默认 physical/fused carry 开关 true；evidence、guard 与审计器引用 | 必需 |
| `stage_grasp_guard.py` | evidence 使用夹爪宽度、held 复核和 visual hold；执行循环调用 `apply_to_action()` | 必需，不能把“动作覆盖关闭”误认为整个模块关闭 |
| `stage_release_guard.py` | `apply_to_action()` 中默认 `payload_release_enabled=true` 时计算 release 状态与记录 | 当前调用链会执行；最终动作是否覆盖另受总开关控制 |
| `stage_observation.py` | 工厂创建 `CodexObservationStageRecognizer`；使用当前图像进行在线事实观察 | 必需 |
| `stage_observation_json.py`、`stage_response_validation.py` | 解码和格式检查；重试格式错误，不为语义失败重抽答案 | 必需 |
| `stage_identity_memory.py` | 当前 `identity_memory_enabled=true`，每回合身份记忆 | 必需；不是跨任务学习 |
| `stage_target_marker.py` | 默认开启目标标记；保存原图与标记元数据 | 必需 |
| `stage_capture.py` | `stage_observation.py` 顶层导入，旧 capture 类的基类实现；当前 Codex 捕获主要在 Codex transport | 结构上仍有依赖；未来可拆分，不能直接删文件 |
| `stage_capture_trace_replay.py` | 只在显式 replay-capture backend 实例化 | 离线诊断保留；不参与 fresh 在线成绩 |

精确区别：当前 `grasp_action_guard_enabled=false` 最终恢复策略原始夹爪命令，但在此之前 guard 的几何/状态计算与证据记录仍执行。删除这些过程不能用“最终没有 override”来证明行为不变。

## 5. `core/codex_*` 是否必要

| 模块 | 实际职责 | 依赖 |
| --- | --- | --- |
| `codex_stage.py` | Codex CLI 调用、完成事件判断、超时、传输恢复与调用计数 | `CodexVisionTransport` 的基类 |
| `codex_vision.py` | 共用视觉 transport、上下文和请求/回复捕获 | Stage observation、`vlm_query/vlm_agent.py`、API 预检 |
| `codex_stage_policy.py` | 固定公开调用策略、环境边界及计数定义 | 两个 Codex 模块与 `scripts/codex_only_runtime.py` |

三者均是当前“仅使用当前 Codex 登录进行在线 Stage/reward”的基础设施。它们不是 QD 搜索机制本体，但删除后当前协议无法完整运行。未来可以整理为 `core/online/` 与 `core/stage/`，前提是独立重构、保持输入/输出/重试/时序并完成相应验证。

## 6. 建议顺序

1. 先完成远端历史源码快照及独立取回验证，主工作区保持干净。
2. 单独提交低风险、无运行时引用的候选；核查链接、配置和相关 CPU 回归。
3. 如明确收缩项目支持范围，再成组退役旧 policy/backend、安装入口和依赖。
4. 保留当前 EDS、Stage/reward 与 Codex 对照，优先开发 QD 的 descriptor、质量/稀疏父代平衡和执行反馈。

本次不以旧成绩替代修改后验收，不为目录整齐改变科学条件。
