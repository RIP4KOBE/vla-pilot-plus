# 整合与验收状态

2026-10-13三组完整在线验收已通过：**EDS 3/10、VLS 1/10、EDS+QD 1/10，30/30任务有效、零基础设施错误**；三组有效且EDS≥3/10的整合gate通过。全部原始审计和最终汇总已在基础设施变更前封存。随后接入的生命周期/归档修复通过两环境各1436项CPU测试；已完成本地main合并，未推送远端。

[逐任务结果与计算预算](results.md) · [随Git结果JSON](validation/final-results.json) · [安装](installation.md) · [运行与归档](evaluation.md)

## 受测与发布身份

| 身份 / 阶段 | 结果 |
| --- | --- |
| 在线受测runtime | `33954ead452927fc3168efb610487a688f89169e` |
| 原始完整验收 | EDS 3/10（task 3、8、9）；VLS 1/10（task 3）；EDS+QD 1/10（task 5）；全部finished、exit 0、source unchanged |
| 最终整合汇总 | `final_accepted=true`；SHA-256 `a67ee5e13f7563b86ea8fadd9e55dd5d5b80f53601cdd1e65f1af72a2c2402eb` |
| 原始验收封存 | 17:18:34 UTC；SHA-256 `14502922a48c5c7ec8de5a59e698a2104d7a241cba2b4e1a9e95a4b51a4e4161` |
| 后续发布基础设施 / 审计器commit | `5bf01db84e8c05251f720a3f8b9a73aa019f9568`；未重跑科学任务、GPU或API |
| 最终代码版本 | `b68777b46a374760a19fa76e3c309d9c84cfcc4c`；相同runtime字节，补追踪原有两个Hydra兼容alias |
| 本地main合并commit / 团队基准 | `8c1051f85a57115163845ec478d06a3ccc68c190`；保留双亲合并记录，合并树与整合分支完全一致 |
| 远端发布 | 本轮未推送；普通远端clone尚不包含本次整合，需维护者发布后再获取 |
| 原始证据 / 精确模型资产 | 维护者本机持有，无公开下载包；位置与来源统一见[README provenance](../../README.md#provenance) |

[最终汇总](../../.worktrees/exp/steering-integration/checks/three-mode-final.json)、[封存记录](../../.worktrees/exp/steering-integration/checks/three-mode-final-seal.json)与[视频索引](../../.worktrees/exp/steering-integration/checks/video-health/index.json)都是本机ignored证据。Git保存的JSON记录全部30个task/seed/outcome、原审计hash和视频hash，普通clone可直接查看。

三组在线测试共30个episode，此前迁移另10个；没有额外科学重试。EDS是本轮观测成功数最多的方法。有效性与成功率分别判断；单seed、默认不同预算的十任务比较不构成统计优越性、非劣效或泛化证明。

发布版审计器还对三组保存的原始数据执行独立`--no-write`重审，均通过；[重审摘要](../../.worktrees/exp/steering-integration/checks/release-reaudit-summary.json)保存checker逐文件hash和原receipt不变证明。最终代码版本的[116/116源码绑定](../../.worktrees/exp/steering-integration/checks/release-build-source-binding.json)确认这些字节全部可从Git取得；其中两个兼容alias在原受测snapshot中已有，发布时仅补追踪。原线上归属仍由受测commit加完整manifest/source快照定义。

## 已完成验证

| 项目 | 真实结果 | 证据与范围 |
| --- | --- | --- |
| 冻结runtime CPU／原环境 | 1403 passed、2 warnings、124.18s | [日志](../../.worktrees/exp/steering-integration/checks/cpu-common-framework-002.log) |
| 冻结runtime CPU／独立安装环境 | 1403 passed、1 warning、124.63s | [日志](../../.worktrees/exp/steering-integration/checks/cpu-common-framework-clean.log) |
| 发布基础设施 CPU／原环境 | 1436 passed、3 skipped、2 warnings、129.98s | [日志](../../.worktrees/exp/steering-integration/checks/cpu-release-primary.log) |
| 发布基础设施 CPU／独立安装环境 | 1436 passed、3 skipped、1 warning、130.02s | [日志](../../.worktrees/exp/steering-integration/checks/cpu-release-clean.log) |
| 发布CLI | 6份help + 3模式print-config全部通过 | [receipt](../../.worktrees/exp/steering-integration/checks/release-cli/receipt.json)；未创建run目录 |
| EDS before/after reference | float32/bfloat16共352动作、RNG/父代/Stage精确比较 | 确定性合成模型/传感器，不覆盖真实模型/GPU核 |
| 固定资产 | 214个模型/DINO文件、2308个LIBERO文件、20个RNG状态 | 内容及加载选择校验，LIBERO四路径绑定进入environment |
| 设备映射与渲染 | GPU0→EGL2、GPU1→EGL3、GPU4→EGL6 | UUID、本进程C+G身份及LIBERO reset/render；均H200 NVL |
| QD数值诊断 | 318/318批、23,850个probe、零失败 | GPU4与独立CPU的bounds位模式/checksum/cell/overflow精确一致，RNG未变 |
| 公共GPU/API预检 | GPU0/EGL2及1次有效图像请求 | CLI 0.156.1 / gpt-6-astra / low，0 failed calls |
| 完整在线机制审计 | EDS205、VLS368、EDS+QD284个guided块 | 原v2审计及独立只读重审均通过；详见[结果](results.md) |
| 视频交付 | 30/30完整CPU解码通过 | 原件、帧数、时长、hash及checker身份登记；不替代任务合同 |

发布版3项skip仅为外置候选阶段的before/after配置对照；三项在应用前均通过。应用后独立复核确认97个科学路径中96个字节不变、1个只改注释且AST不变，三模式print-config与冻结版逐字节相同，worker及配置环境helper保持不变。[应用后复核](../../.worktrees/exp/steering-integration/checks/final-applied-review.json)保留范围；CPU/静态一致性不被记成新在线实验。

本地[公共预检](../../.worktrees/exp/steering-integration/preflight-common-20261013/report.json)、[设备映射](../../.worktrees/exp/steering-integration/checks/gpu014-mapping-summary.json)、[QD完整数值结果](../../.worktrees/exp/steering-integration/checks/qd-gpu4-numeric.json)保留原证据。数值报告SHA-256 `1428b81160316b77b293a02ceb789e1c27de81db3300f293a42a9c1f5e4f91b7`。有限输入诊断不保证全部GPU输入；独立安装环境仅验收CPU，没有重复GPU模型推理、在线服务或torchcodec native解码。

## 验收后基础设施与归档

生命周期取消与可移植归档修复在原始汇总封存后应用，并通过上面的发布版CPU回归。launcher原子取得新目录后才承担状态写入，SIGINT/SIGTERM持锁清理其拥有的worker树，保存partial输出与interrupted状态，不自动重试。SIGKILL/主机失败/提前逃逸子进程仍需外部监督。[命令及边界](evaluation.md#prepared-infrastructure)。

归档重审按哈希绑定的原config/environment恢复执行身份，使用精确任务表与RNG manifest support，直接验证当前归档内的raw PNG，不借原绝对路径补漏。未知schema、v1/v2错配或损坏sidecar均拒绝；不放宽科学数值或机制gate。

接入前独立checker已完成两种真实复制/改名验证，原始run从未修改：

| 已有数据 | 实际验证 | 明确边界 |
| --- | --- | --- |
| 迁移v1 | 4,045文件、913,826,636字节；十任务14,081项合同检查通过，缺失/同大小损坏frame及support负例被拒绝 | wrapper仅`legacy_basic_only`；独立auditor的legacy fixture路径放置与support同hash的fixture，不提升为v2 |
| 公共EDS v2 | 4,048文件、927,345,187字节；禁止读取原workspace其它路径仍完整通过10/10有效、3/10 | 直接使用support，无legacy补位；原run、复制品及当时113个源码hash未变，CUDA未初始化 |

[v1 receipt](../../.worktrees/exp/steering-integration/checks/archive-candidate-validation/receipt.json) SHA-256 `c2351c77e17d5c31cd8ee08d302e54b92cbe274e38a1a003f0f324f1150ba76e`；[v2 receipt](../../.worktrees/exp/steering-integration/checks/archive-v2-candidate-validation/receipt.json) SHA-256 `3781d788fcf08e426091ec140392ed2b0b3a4a6f22d0413c4dbf19f441220b2e`。receipt分别保存原受测身份、原audit hash及独立checker hash；路径可移植性检查不是新的任务成绩。

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

运行时间为2026-10-13 09:04:05–12:23:58 UTC。原始源码快照、控制器捕获、reward/identity输入输出、计算日志、完整视频与失败证据必须保留在该外部归档。大型原始文件不提交Git；目前没有配置公开的完整归档下载包；原始证据由维护者本地持有。

## 安装与资产交接

[配方](installation.md)包含62项直接依赖、172项约束、固定LeRobot的23项base声明及8项Conda显式版本。全新环境独立创建，未克隆共享环境或使用system-site-packages；最初完成pip check、62项依赖/入口import、真实当前源码的processor身份/行为、worker配置预览及1118项CPU测试，随后同一环境通过上述1403和1436项回归。

安装过程中补入BDDL未声明的future并最后重装同版headless OpenCV，最终配方已包含两项修正。为避免写当时冻结源码，editable metadata来自逐文件一致的外置副本，实际runtime导入当前clone源码。完整来源只在[README provenance](../../README.md#provenance)列出。

原始日志、模型、视频和复制归档保存在维护者本机ignored路径；没有配置公开分发服务。新clone需要维护者交付清单匹配的RDT checkpoint与固定DINO源码，T5/SigLIP本地snapshot revision有记录但远端可取回性未核验。严验始终开启，不能因暂缺资产用其他权重冒充本轮身份。
