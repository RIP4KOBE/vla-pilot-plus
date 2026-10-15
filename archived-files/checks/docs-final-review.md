# 公共文档最终只读审阅

审阅基线：`33954ead452927fc3168efb610487a688f89169e`，2026-10-13。范围：README、CONTRIBUTING、docs/steering，以及这些页面所引用的配置、CLI parser、策略/Stage/FKD 实现与已有验收记录。没有修改受测源码、配置、资产或任何 cohort 原始文件，没有启动测试、GPU 或 API；本文件是独立审阅产物。以下文字供运行冻结解除后审阅应用。

结论：没有发现文档命令指向不存在的公共入口，也没有发现 EDS/QD 主算法描述与受测实现相反的错误。交付前需要刷新状态、补足外部安装前提，并明确在线 reward 生成与本地评分的区别。三组完整在线成绩仍不能提前登记。

## 需修正或交付前补齐

### 1. 将旧的“待 CPU/GPU 验证、待运行”更新为有证据的当前状态

位置：CONTRIBUTING.md:7；docs/steering/architecture.md:3、123；docs/steering/integration-status.md:40、44、48–54。README.md:5、101 和 integration-status.md:45 已正确记录两环境 1403 passed，其他段落仍写完整 CPU/GPU 待完成。三组状态文件在本次读取时均为 running，不能继续写“待运行”或“当前没有提前登记启动”。

可直接替换各页面状态摘要：

> 公共三模式代码已冻结为 `33954ead452927fc3168efb610487a688f89169e`。原运行环境和独立安装环境均通过 1403 项 CPU 测试，GPU0/1/4 的 CUDA/EGL 与 QD 数值诊断已通过，最终公共 GPU/API 预检已通过。EDS、VLS、EDS+QD 的独立十任务 cohort 已启动，完整结果和最终合并仍待验收；迁移版 3/10 不作为这些新 cohort 的成绩。

已读取证据：

- `checks/cpu-common-framework-002.log`、`checks/cpu-common-framework-clean.log`（既有结果索引）；
- `preflight-common-20261013/report.json`：status=pass，2026-10-13 13:11:44–13:12:52 UTC；214 项模型资产、2308 项 LIBERO 文件、20 项 RNG 状态有效；GPU0/EGL2 tensor/render；1 次完成的图像请求，gpt-6-astra/low，零 failed_calls。此处不能扩展为三张卡各自都重新调用了 API；其他两张卡的设备/渲染证据来自独立 mapping 检查；
- `runs/eds-common-20261013/status.json`：13:15:18 UTC 启动，GPU0/EGL2；
- `runs/vls-common-20261013/status.json`：13:14:27 UTC 启动，GPU1/EGL3；
- `runs/eds_qd-common-20261013/status.json`：13:14:34 UTC 启动，GPU4/EGL6。

上述路径均相对 `.worktrees/exp/steering-integration/`。正式文档落地前应重新读取最终状态，将 running 改为对应事实；不要从本报告时间点推断最终完成。最终结果必须同时给 commit、manifest、完整 audit、逐任务 outcome 和可访问证据位置。README provenance 的最终 merge commit 继续保留待填，直到真正合并完成。

### 2. Codex CLI 是独立安装前提；准确资产交付入口仍是可复现交接缺项

位置：docs/steering/installation.md:7、48、87；README.md:17、51、71。

现有 Conda/pip 清单不安装 Codex CLI。页面虽然提到自己的 CLI 登录及验证版本，但最短安装流程没有先列出这个独立前提。建议在安装前提后补：

> 在线运行还需要单独提供 Codex CLI，并完成使用者自己的登录。该 CLI 不由本页的 Conda/pip 命令安装；验收记录使用 0.156.1。先用 `codex --version` 检查实际可执行文件，再进行本页后续 GPU/API 预检。不同 CLI 版本需重新确认本项目使用的 exec 参数与事件格式兼容性。

这里仅提出本地版本检查，没有虚构 CLI 安装命令、登录参数或已经完成的新 clone 在线验证。

安装顺序和依赖约束与实际清单一致，OpenCV headless 最后覆盖是必要步骤。已有文档也正确承认 RDT 权重/DINO 源码 revision 未知、固定资产分发位置待提供。**该占位意味着同事不能仅凭新 clone 就取得完整在线运行资产。** 最终交接仍需提供获准分享的精确资产包/现有存储入口、访问方式、逻辑根布局与 expected manifest；不能以模型名字或猜测的远端链接替代。独立环境 CPU 成功不填补此缺项。

### 3. 明确远程生成 reward 与本地候选评分之间的边界

位置：README.md:51；docs/steering/architecture.md:15、67–77。

建议在架构 reward 段落前补：

> 每个任务准备阶段在线生成新的 reward Python 程序，并按合同检查；必要修复请求属于准备阶段调用。任务中的候选 reward 评分随后在本地 Torch 执行，VLS 的 reward 梯度也由本地自动微分计算，并非每个候选都调用 Codex。在线服务还承担初始身份描述和执行过程中的视觉 Stage 查询；这三类请求与本地评分次数分别记账。

源码对应：main.py:964–1021（生成/载入 guidance 与合同输入）；core/rdt_policy_steer.py:1786 起（本地粒子评分）、2027 起（EDS population 评分）、7224 起（本地 reward 梯度）。公共运行禁止旧回复/缓存替代 fresh generation。这样可避免把 EDS 每块 176 个候选评分误读成 176 次模型 API 请求。

### 4. 避免把启用 FKD 等同于每块必然执行重采样

位置：README.md:9；docs/steering/architecture.md:81、89、121。

README 方法表可以把“FKD 粒子重采样”改为“自适应 FKD 粒子重采样（允许 ESS 跳过）”。架构中建议补：

> 当前固定 checkpoint 的五步 schedule 为 `[999,799,599,400,200]`。公共 VLS profile 在正常 guided 块中执行 1 次 RBF 与 4 次 reward 梯度尝试；FKD 被调用 3 次，但 frequency=5 只安排其中 1 次评分机会。非末步 ESS≥10 时不调用 multinomial，实际重采样次数为 0 仍是合法行为。当前 RDT 循环排除 terminal timestep 的 FKD 调用；文中单候选/FKD-terminal 直接返回路径是兼容代码分支，不是默认 20 粒子 profile 的必经路径。

源码对应：core/rdt_policy_steer.py:1975 明确排除 terminal_t；core/fkd_class.py:144–158 构造评分时刻，303–332 执行 ESS 决策和实际 multinomial。实际在线初始 3 块也观察到每块 4 次 gradient applied、1 次 RBF applied、3 次 FKD 调用/1 次评分/0 次实际重采样，且独立审计通过；该前缀证据仅支持机制解释，不是完整任务成绩。

可选同时说明 telemetry 会读取 CUDA 数值到 CPU，运行延迟包含这些同步/记录开销；不要将其称为纯模型 kernel 时间或把三种默认 profile 称为等计算预算。

## 可选精简与准确性补充

- README.md:21–49 同一代码块列出三次配置预览、三次单任务诊断和三次 full10。将单任务诊断标为“可选”，最短流程保留一种方法的 preview → preflight → full10 → audit，其他模式作为替换示例，避免同事把全部命令当作必做步骤。
- architecture.md:123 的 VLS 能力探针说明补“至少一个非最优探针在可控 p1…p7 上存在非零梯度”；p0 是固定当前状态，只有 p0 梯度不算可引导能力。EDS 仍仅要求可评分。
- 可在共享协议说明增加实际 ObjectSwap 上限为 720 个执行步，并直接链接 `configs/evaluation/libero_object_swap.yaml` 中 backend 设置；不要误用其中另一层 main.max_episode_steps=240 推算任务预算。正式填入前按 adapter 对 backend 配置的消费再核对。

## 已核对一致，无需重新描述或改算法

- 三个公共 method 值均有实际 parser/profile 路由：`vls`、`eds`、`eds_qd`；`evaluate_steering.py` 复用同一个 launcher，默认全十任务，仍支持显式子集。`--print-config` 不产生 GPU/API 调用，但不是资产内容验证。
- README 的 run/check/audit/contract 参数都在真实 CLI 中存在；安装的 install-libero/verify-libero/verify-rng/configure 入口及顺序存在。此次只做静态对应核查，没有为了审阅再次执行在线命令。
- EDS 的 B16、初始 5 步、10 轮深度 `[3,2,2,2,2,1,1,1,1,1]`、初始/截断 RBF 生效区间、softmax(0.1r) 的乘温度、float64→float32 权重、最终第 10 轮当前 population 选择描述正确。
- “RBF”实际是逆距离势；轨迹为末端平移线性累计，不是候选 MuJoCo 分支 rollout。EDS 免 reward 梯度，不免多样性自动微分。
- reward 使用 p1…p7、RBF 使用 p1…p8、VLS 内部梯度使用 p0…p7；Stage 2 常数 reward 不提供 guidance。EDS 外层 getter 纯读，VLS selected-score/reference 与内部梯度 reference 分离；contact handoff 使用 fresh outer progress，文档没有误说 Stage 完全不消费 reward。
- EDS+QD 的 grid_archive、4×4/capacity1/fixed bounds/sparse_priority、每块 fresh、archive 父代及最终跨轮最好选择描述正确。observer 不证明 QD 激活；没有跨任务 archive 或递归自我改进。
- 非等预算比较、仿真状态/关键点依赖、请求模型元数据证明边界、未知 RDT/DINO revision、未独立重演环境、部分父代 tensor 证据边界、任务成功与有效性分开报告均已明确。
- 历史版本/来源 worktree/分支具体映射集中在 README provenance；两处不可改的 C0 科学提示词例外有明确说明。其他公共页面未发现新引入这些来源名称作为方法入口。
- 现有依赖配方和源副本安装证据有如实区分；没有声称原干净环境做过 GPU/API/真实权重推理。原始视频/logs 为 ignored 本地归档、小 fixture 不能替代原始证据，文档已说明。

## 最终协作交接剩余边界

运行冻结结束后，统一更新公共三组结果、commit/config/manifest/audit 哈希及计算预算；保留 partial/无效运行原件。补可访问的准确模型资产和运行日志/视频归档入口。真正合入共同 main 后才填 merge commit 与同事派生 feature branch 的基点。上述工作完成前可称“已实现、CPU 与设备预检通过、在线验收进行中”，不能称“三模式已完整验收并完成协作交付”。
