# Steering 整合状态

更新时间：2026-10-13。**阶段3的 EDS 迁移完整验收已通过；阶段4的公共三模式整合正在进行。** 公共版本已通过两环境 CPU 回归与三个设备的 CUDA/EGL 检查，EDS/VLS/EDS+QD 各自十任务和最终合并仍待完成。本文的结果表只登记已完成且有冻结证据的运行。

## 迁移版 EDS：完整有效 3/10

受测 commit 为 `cfecb12db736f1a3408d9528d9336aadcb7e41b5`。十个任务全部完成，成功 **3/10**，task ID **3、8、9**；零基础设施错误 episode，worker正常结束，运行期间源码未变。十份逐任务合同均完整有效，共 **14,081 项检查通过**。

运行保留 **5,585 个执行动作及 adapter出口记录**、307次在线Stage observation、10次身份请求和10份新生成reward捕获。Stage捕获总数317，其中307为observation。环境为LIBERO ObjectSwap OOD，请求为Codex CLI / gpt-6-astra / low；不将服务请求标记解读为服务端模型内部身份的独立证明。

| Task ID | Seed | 结果 | 动作数 | 合同检查 PASS | 对照记录的动作一致性 |
| --- | ---: | --- | ---: | ---: | --- |
| 0 | 44 | 失败，有效 | 720 | 1722 | 全部相同 |
| 1 | 235 | 失败，有效 | 720 | 1765 | 全部相同 |
| 2 | 43 | 失败，有效 | 720 | 1808 | 最后24个不同，首次step696 |
| 3 | 546 | 成功，有效 | 120 | 389 | 全部相同 |
| 4 | 6 | 失败，有效 | 720 | 1550 | 最后248个不同，首次step472 |
| 5 | 621 | 失败，有效 | 720 | 1980 | 全部相同 |
| 6 | 197 | 失败，有效 | 720 | 1679 | 全部相同 |
| 7 | 87 | 失败，有效 | 720 | 1937 | 全部相同 |
| 8 | 151 | 成功，有效 | 211 | 604 | 全部相同 |
| 9 | 548 | 成功，有效 | 214 | 647 | 全部相同 |

8个任务的完整记录动作序列与参考相同，总共5,313/5,585个动作相同。任务2和4的尾部差异被保留，并非为了同分删除失败。相同3/10不证明全部在线请求、视觉判断或每个任务轨迹严格重现。参考来源身份集中在 [README provenance](../../README.md#provenance来源与本地证据)。

本页是可随Git保存的结果摘要。下列原始证据位于 ignored 目录，只在维护者持有的归档中可用，普通clone不包含：

- [完整迁移报告](../../.worktrees/exp/steering-integration/runs/eds-migration-20261013/migration-full10-report.md)。
- [验收清单、逐任务报告及哈希](../../.worktrees/exp/steering-integration/runs/eds-migration-20261013/migration-full10-acceptance.json)，SHA-256 `c3251c1546b75d85352c77bdda0ea49afed00ca4d74402f099b9794bd73c7178`。
- [冻结manifest](../../.worktrees/exp/steering-integration/runs/eds-migration-20261013/manifest.json)、[配置](../../.worktrees/exp/steering-integration/runs/eds-migration-20261013/resolved-config.yaml)、[cohort audit](../../.worktrees/exp/steering-integration/runs/eds-migration-20261013/audit.json)、[最终status](../../.worktrees/exp/steering-integration/runs/eds-migration-20261013/status.json)。
- [task2动作比较](../../.worktrees/exp/steering-integration/runs/eds-migration-20261013/task2-action-comparison.json)、[task4动作比较](../../.worktrees/exp/steering-integration/runs/eds-migration-20261013/task4-action-comparison.json)、[task9动作比较](../../.worktrees/exp/steering-integration/runs/eds-migration-20261013/task9-action-comparison.json)。其余逐任务报告由验收清单索引。

运行时间为2026-10-13 09:04:05–12:23:58 UTC。原始源码快照、控制器捕获、reward/identity输入输出、计算日志、完整视频与失败证据必须保留在该外部归档。大型原始文件不提交Git；可公开访问的完整归档链接仍待维护者提供。

## 公共版本：已实现与待验收

| 项目 | 当前状态 | 证据边界 / 下一步 |
| --- | --- | --- |
| 三模式 CLI/profile | 已实现，三种 `--print-config` 已通过CPU解析 | 配置可解析不等于在线方法已验收 |
| 统一 Stage 进度 | 已实现；EDS只读已有进度，VLS使用独立selected-score/reference | 完整公共版本CPU和在线回归待结案 |
| VLS梯度能力/实际机制记录 | 已实现VLS专用探针、gradient/FKD/selection telemetry | 待完整在线机制与任务验证，不以配置开关证明调用发生 |
| EDS before/after CPU reference | 受控float32/bfloat16共352动作及RNG/父代/Stage精确比较通过 | 合成模型/传感器，不覆盖GPU、真实服务或完整仿真 |
| 固定模型与LIBERO路径校验 | configure、preflight与真实launcher始终验证模型；模型校验器35项针对性CPU测试通过 | 214项模型/DINO身份保持；LIBERO显式根和4项路径绑定进入environment证据；现有bytecode证明边界保留 |
| 离线合同与QD重建 | 工具和自包含fixture已接入 | 只证明已记录内容；完整公共套件仍待汇总 |
| 最终公共CPU套件 | **原环境与独立安装环境均 1403 passed** | 分别124.18s/2 warnings、124.63s/1 warning；日志如下 |
| GPU设备映射与渲染 | 已实证GPU0→EGL2、GPU1→EGL3、GPU4→EGL6 | CUDA UUID、实际EGL display与本进程C+G记录一致；均完成LIBERO reset/render，未执行动作 |
| GPU QD数值诊断 | **GPU4通过：318/318批，零失败** | 每批75个边界probe；bounds位模式/checksum/cell/overflow精确一致；不计任务成绩 |
| 最终公共GPU/API预检 | **待完成/登记** | 旧版预检不能替代最终源码的验证 |
| 最终公共 EDS 十任务 | **待运行，计划GPU0/EGL2** | 使用公共接口冻结后的新commit/config/run |
| 最终公共 VLS 十任务 | **待运行，计划GPU1/EGL3** | 单独有效cohort与实际机制证据 |
| 最终公共 EDS+QD 十任务 | **待运行，计划GPU4/EGL6** | 固定profile数值诊断已通过；在线archive机制与完整cohort仍待验收 |
| 最终主线合并 | **未完成** | 审阅最终代码、证据、文档后合并；commit待填 |

当前允许使用已分配的任意空闲GPU，不再限定GPU2。GPU2/3仍属于外部项目；其进程未被中止或占用。本次在另行授权的空闲GPU0/1/4完成设备验证，分别保存本机配置，原GPU2配置未改。三种方法拟使用相同型号H200 NVL，在最终源码冻结后并行开展各自完整cohort；当前没有提前登记启动或结果。见[设备映射与渲染摘要](../../.worktrees/exp/steering-integration/checks/gpu014-mapping-summary.json)。

[GPU4数值摘要](../../.worktrees/exp/steering-integration/checks/qd-gpu4-numeric-summary.json)与[完整逐例输入/结果](../../.worktrees/exp/steering-integration/checks/qd-gpu4-numeric.json)保留318组确定性16×2输入、共23,850个probe、源码hash、UUID与进程证明。CPU/CUDA全局RNG不变；核心QD与独立审计源码未变。完整报告SHA-256为 `1428b81160316b77b293a02ceb789e1c27de81db3300f293a42a9c1f5e4f91b7`。2GiB限制仅适用于PyTorch分配器；实际峰值reserved为2MiB。数值诊断不加载模型、不调用API、不执行任务，有限输入通过也不证明所有可能GPU输入。若后续发生数值分歧，保存完整差异，不在看到任务结果后放宽审计。

公共版本完整 CPU 日志分别为[原运行环境](../../.worktrees/exp/steering-integration/checks/cpu-common-framework-002.log)与[独立安装环境](../../.worktrees/exp/steering-integration/checks/cpu-common-framework-clean.log)。首次完整运行1397通过、2个旧VLS测试桩缺少新日志接口而失败；补齐测试桩并保留执行长度断言后完整重测，上述通过数字属于新运行。旧失败日志保留，未改写。迁移版全部201个实际EDS搜索块也通过新独立机制审计，见[逐块检查](../../.worktrees/exp/steering-integration/checks/migration-all-chunk-method-audit.json)；这是旧数据离线核验，不计新在线成绩。

## 安装证据与适用范围

[安装配方](installation.md)已接入62项直接依赖、172项约束、固定LeRobot的23项base声明，以及8项Conda显式版本。本轮文件逐行匹配真实验证输入。

真实干净Conda环境的验收绑定上述迁移commit：`pip check` 无损坏依赖；62项依赖与main入口import、当前clone真实LeRobot processor身份/行为、worker `--cfg job`通过；**1118 passed、1 warning、86.53s**。安装不是共享环境克隆，也未使用system-site-packages。为避免当时冻结源码写入，editable元数据来自逐文件一致的外置副本；实际runtime导入的是当前root源码。

真实首次安装补入BDDL缺失的future，并在最后重装同版headless OpenCV；最终配方已包含这些修正，没有声称又创建过第二个完整环境。原始日志/来源见 [README provenance](../../README.md#provenance来源与本地证据)。该新环境没有GPU/EGL reset/render、模型加载/推理、Codex/API或torchcodec native解码验收。

迁移前原工作环境的CPU记录为1118 passed、2 warnings、82.42s，与干净环境记录分别保存。两者均不能替代本次新增公共接口后的最终测试。模型资产的完整CPU身份校验、LIBERO2308文件重建、RNG文件身份和在线成绩也分别记账。

## 完成规则

新公共版本应依次完成最终CPU回归、资产/环境检查、设备身份确认、QD数值与机制gate，以及三种方法各自的完整cohort。每轮保留解析配置、源码hash、实际import环境、设备、在线调用、控制器与执行证据，记录失败和计算预算。

更新结果表时同时填写受测commit、run manifest、任务/seed、成功与基础设施错误、完整审计及可分享证据链接；未运行项保持pending。下一次文档更新不得将本页迁移成绩自动改名为公共版本成绩。
