# 整合与验收状态

结果快照时间：2026-10-13 16:34 UTC。三模式runtime冻结为 `33954ead452927fc3168efb610487a688f89169e`，原环境及独立安装环境各1403项CPU测试、设备/渲染、QD数值及公共GPU/API预检已通过。EDS十任务已完成完整有效3/10并通过原始v2审计及重新执行的只读审计；VLS/EDS+QD、整体整合与main合并仍为PENDING。

## 公共三模式验收

| 方法 | 受测设备（本机） | 运行状态 | 完整成功率 | 完整审计 / 验收JSON |
| --- | --- | --- | --- | --- |
| EDS | GPU0 / EGL2 | finished，exit 0；10/10有效 | **3/10**，task 3、8、9 | [原始v2 audit](../../.worktrees/exp/steering-integration/runs/eds-common-20261013/audit.json)；[重新只读审计汇总](../../.worktrees/exp/steering-integration/checks/three-mode-eds-completed.json) |
| VLS | GPU1 / EGL3 | 已启动，最终状态 PENDING | **PENDING_VLS_SCORE** | **PENDING_VLS_ACCEPTANCE** |
| EDS+QD | GPU4 / EGL6 | 已启动，最终状态 PENDING | **PENDING_EDS_QD_SCORE** | **PENDING_EDS_QD_ACCEPTANCE** |

三组GPU均为H200 NVL。启动时间分别为13:15:18、13:14:27、13:14:34 UTC，任务与seed来自同一共享协议。设备编号仅属于这台机器；其他clone须独立验证映射。逐任务outcome、有效性、基础设施错误、实际计算与服务计数将在各组完整审计后填写，不从运行前缀推断总分。

EDS于16:33:14 UTC正常完成，零基础设施错误，运行期间源码未变。共 **205个guided、494个unguided动作块，309次有效Stage observation、0次查询错误**；另有10次身份请求和10次新reward请求。原始audit为`full_v2_contract_and_recorded_method_evidence`，SHA-256 `967a8532361bbe53c707e384a4f70531f6d94b4fe68c102e20dbb22394290899`。

16:34的重新只读审计汇总SHA-256为 `6aae054b581bd13c6b3f705ea188a105c2726876efa9cf457b15b3ea02381cac`。它确认EDS单组有效且达到≥3/10门槛；该文件整体仍为`partial_or_not_accepted`、`integration_acceptance=false`，因为另外两组尚未完整完成。最终三组验收仍必须在冻结源码下统一汇总。

本轮EDS与迁移轮的5,585个执行动作中5,313个相同，8个任务完整序列相同；仅task0末24个、task4末248个不同，详见[动作比较](../../.worktrees/exp/steering-integration/checks/eds-common-completed-action-comparison.json)。差异前的在线回复、Stage与guidance变化分别记录于[task0](../../.worktrees/exp/steering-integration/checks/eds-common-task0-online-divergence.json)和[task4](../../.worktrees/exp/steering-integration/checks/eds-common-task4-online-divergence.json)；这些是日志归因，未用反事实实验隔离身份文字与provider生成波动。

| 发布身份 | 当前值 |
| --- | --- |
| 本次在线受测runtime | `33954ead452927fc3168efb610487a688f89169e` |
| 冻结源码下的最终汇总 / hash | **PENDING_FINAL_ACCEPTANCE_JSON_AND_SHA256** |
| 三组有效且EDS≥3/10的整合gate | **PENDING_INTEGRATION_ACCEPTANCE** |
| 后续独立审计器commit / hash（若采用） | **PENDING_POST_COHORT_AUDITOR_IDENTITY** |
| 最终发布 / main merge commit | **PENDING_MAIN_MERGE_COMMIT** |
| 可访问的运行证据归档 | **PENDING_EVIDENCE_ARCHIVE** |
| 获准分享的精确模型/DINO资产入口 | **PENDING_MODEL_ASSET_ACCESS** |

先在受测源码仍完整匹配时完成三组最终汇总，再应用验收后的基础设施补丁。后续审计报告保留原runtime归属，并记录新审计器身份；发布commit不替代实际受测commit。来源分支、历史身份和命名例外统一见 [README provenance](../../README.md#provenance)。

## 已完成的公共runtime验证

| 项目 | 已有证据 | 范围 |
| --- | --- | --- |
| 三模式入口与Stage接口 | 统一profile、纯读外层进度、VLS专用梯度探针/telemetry已接入 | 在线完整机制结果由各cohort审计确认 |
| 全套CPU／原环境 | 1403 passed、2 warnings、124.18s | [原始日志](../../.worktrees/exp/steering-integration/checks/cpu-common-framework-002.log) |
| 全套CPU／独立安装环境 | 1403 passed、1 warning、124.63s | [原始日志](../../.worktrees/exp/steering-integration/checks/cpu-common-framework-clean.log)；该环境GPU/在线未验收 |
| EDS before/after reference | float32/bfloat16共352动作、RNG/父代/Stage精确比较 | 确定性合成模型/传感器；不覆盖真实模型/GPU核 |
| 固定资产 | 214个模型/DINO文件、2308个LIBERO文件、20个RNG状态 | 实际内容及加载选择校验；LIBERO四路径绑定进入environment |
| 设备映射与渲染 | GPU0→EGL2、GPU1→EGL3、GPU4→EGL6 | UUID、实际EGL display、本进程C+G身份与LIBERO reset/render；未执行任务动作 |
| QD数值诊断 | 318/318批、23,850个probe、零失败 | GPU4与独立CPU审计的bounds位模式/checksum/cell/overflow精确一致 |
| 公共GPU/API预检 | 13:11:44–13:12:52 UTC，pass | GPU0/EGL2 tensor/render；1次有效gpt-6-astra/low图像请求，0 failed calls |
| 完整三组在线验收 | **PENDING** | 不能由以上预检或旧迁移成绩替代 |

本地证据：[公共预检](../../.worktrees/exp/steering-integration/preflight-common-20261013/report.json)、[设备映射](../../.worktrees/exp/steering-integration/checks/gpu014-mapping-summary.json)、[QD数值摘要](../../.worktrees/exp/steering-integration/checks/qd-gpu4-numeric-summary.json)与[完整逐例结果](../../.worktrees/exp/steering-integration/checks/qd-gpu4-numeric.json)。后者SHA-256为 `1428b81160316b77b293a02ceb789e1c27de81db3300f293a42a9c1f5e4f91b7`，CPU/CUDA全局RNG未变。两张其他GPU的设备证据来自独立mapping检查，不声称三张卡各自再次调用了API。有限数值诊断不证明所有可能输入。

首次公共CPU检查保留了两个旧VLS测试桩接口缺失的失败记录；补齐测试桩并保持执行长度断言后，以上数字来自完整重跑。迁移数据中的201个实际EDS搜索块也通过了新独立机制审计，见[离线核验](../../.worktrees/exp/steering-integration/checks/migration-all-chunk-method-audit.json)；它属于旧数据重审。

## 验收后基础设施候选

生命周期取消与可移植归档修复目前只在外置review copy中，**未应用到运行中的runtime**。候选已通过36项新CPU回归及140项现有runner/合同测试；正常三模式配置保持一致。候选的测试数量不能覆盖或重命名上面的1403项冻结runtime记录。

候选支持持锁清理已拥有的worker进程树、保存interrupted状态，以及绑定原始配置/任务表/RNG清单的归档重审；SIGKILL和已逃逸进程仍需外部监督。使用条件与准备中的命令见[运行与审计](evaluation.md#prepared-infrastructure)。是否合入、补丁commit及合入后验证为 **PENDING_INFRA_INTEGRATION**。

真实迁移归档也完成外置候选验证：4,045个文件、913,826,636字节完整复制并改名，原文件及复制品最终hash一致；屏蔽原目录/原资产读取后，十任务合同共14,081项检查通过，缺失/同大小损坏raw frame及损坏support均被拒绝。该运行保留v1身份，wrapper只报告`legacy_basic_only`；外置auditor的legacy fixture路径放置了与support严格同hash的fixture。十份独立合同直接使用support，此结果不等于完整v2验收。[验证receipt](../../.worktrees/exp/steering-integration/checks/archive-candidate-validation/receipt.json)与[逐任务及负例摘要](../../.worktrees/exp/steering-integration/checks/archive-candidate-validation/offline-result.json)保留了实际命令、源hash和边界。

公共EDS的真实v2归档也已完整验证：4,048个文件、927,345,187字节复制并改名；禁止读取原workspace其它路径时，候选auditor仍通过完整v2审计，保留10/10有效与3/10成绩。该验证直接使用support中的任务表/RNG清单，没有legacy fixture补位。原run、复制品及113个冻结源码文件最终hash均未变，CUDA未初始化；这不是新科学运行。

[v2归档receipt](../../.worktrees/exp/steering-integration/checks/archive-v2-candidate-validation/receipt.json)的SHA-256为 `3781d788fcf08e426091ec140392ed2b0b3a4a6f22d0413c4dbf19f441220b2e`，分别记录原受测runtime `33954ead452927fc3168efb610487a688f89169e`、原audit hash、候选checker逐文件hash及[新审计结果](../../.worktrees/exp/steering-integration/checks/archive-v2-candidate-validation/reports/cohort-v2.json)。候选未合入根runtime；新审计器身份不替换实验源码身份。

## 迁移版 EDS：完整有效 3/10

受测身份见 [README provenance](../../README.md#provenance) 的迁移验收行。十个任务全部完成，成功 **3/10**，task ID **3、8、9**；零基础设施错误 episode，worker正常结束，运行期间源码未变。十份逐任务合同均完整有效，共 **14,081 项检查通过**。

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

8个任务的完整记录动作序列与参考相同，总共5,313/5,585个动作相同。任务2和4的尾部差异被保留，并非为了同分删除失败。相同3/10不证明全部在线请求、视觉判断或每个任务轨迹严格重现。参考来源身份集中在 [README provenance](../../README.md#provenance)。

本页是可随Git保存的结果摘要。下列原始证据位于 ignored 目录，只在维护者持有的归档中可用，普通clone不包含：

- [完整迁移报告](../../.worktrees/exp/steering-integration/runs/eds-migration-20261013/migration-full10-report.md)。
- [验收清单、逐任务报告及哈希](../../.worktrees/exp/steering-integration/runs/eds-migration-20261013/migration-full10-acceptance.json)，SHA-256 `c3251c1546b75d85352c77bdda0ea49afed00ca4d74402f099b9794bd73c7178`。
- [冻结manifest](../../.worktrees/exp/steering-integration/runs/eds-migration-20261013/manifest.json)、[配置](../../.worktrees/exp/steering-integration/runs/eds-migration-20261013/resolved-config.yaml)、[cohort audit](../../.worktrees/exp/steering-integration/runs/eds-migration-20261013/audit.json)、[最终status](../../.worktrees/exp/steering-integration/runs/eds-migration-20261013/status.json)。
- [task2动作比较](../../.worktrees/exp/steering-integration/runs/eds-migration-20261013/task2-action-comparison.json)、[task4动作比较](../../.worktrees/exp/steering-integration/runs/eds-migration-20261013/task4-action-comparison.json)、[task9动作比较](../../.worktrees/exp/steering-integration/runs/eds-migration-20261013/task9-action-comparison.json)。其余逐任务报告由验收清单索引。

运行时间为2026-10-13 09:04:05–12:23:58 UTC。原始源码快照、控制器捕获、reward/identity输入输出、计算日志、完整视频与失败证据必须保留在该外部归档。大型原始文件不提交Git；可公开访问的完整归档链接仍待维护者提供。

## 安装证据

[安装配方](installation.md)包含62项直接依赖、172项约束、固定LeRobot的23项base声明，以及8项Conda显式版本。真实新环境独立创建，未克隆共享环境或使用system-site-packages。最初完成pip check、依赖/入口import、真实当前clone的LeRobot processor身份/行为、worker `--cfg job`及1118项CPU测试；后来同一环境完成上述1403项公共runtime测试。

初次安装补入BDDL未声明的future，并最后重装同版headless OpenCV，最终配方已包含这两项修正。为避免当时冻结源码写入，editable metadata来自逐文件一致的外置副本，实际runtime导入当前clone源码。详细安装记录和初次验收身份见 [README provenance](../../README.md#provenance)。独立环境的CPU验收不包含GPU模型加载/策略推理、在线服务或torchcodec native解码。

## 最终填写规则

本次整合gate为：**三组完整cohort均有效，且本轮EDS成功率至少3/10**。cohort有效性与整合是否接受分别记录；低成功率仍可能来自有效cohort。这个工程验收门槛不构成统计非劣效或泛化能力证明。

从三份完整验收JSON及统一汇总填写成功数、有效任务数、逐任务outcome、错误、原始manifest/config/hash和计算预算；失败或pending项如实保留。填入可分享的原始日志/视频清单与hash，最后再填写实际main merge commit。只写已观察到的事实，不将迁移3/10改名为公共版本成绩。
