# Steering 整合阶段 1–3 证据审阅稿

生成时间：2026-10-13T10:03:26.582399+00:00。本稿只汇总已经发生并留下证据的工作；仅写入 `/tmp/steering-integration-report-draft.md`，没有修改 repository、冻结运行、配置、依赖或资产，没有启动 GPU、模拟器或 API。后续结果表和合并字段明确标为待完成。

当前结论：EDS 的迁移、离线检查、设备预检和任务 0 的完整执行对照已有证据；新的完整十任务在线验收仍在进行。现阶段没有新的 full10 分数，历史 **3/10 不能填入本次整合成绩**。公开方法统一使用 `vls`、`eds`、`eds_qd`，本文不把研究版本代号当作方法名称。

## 阶段 1：主分支起点、实际来源与冻结边界

主分支起点及本次只读核验的 `main` 均为 `d51cb85f485502e0429c79529872efef2ec59981`，原主仓库已包含 RDT、LIBERO 与 VLS。当前工作分支为 `codex/rdt-steering-integration`；此次在线评测固定提交为 `cfecb12db736f1a3408d9528d9336aadcb7e41b5`，尚未合并到 `main`。

实际迁移依据是已验收运行的 `accepted-setting.json`、`manifest.json`、`resolved-config.yaml` 及 `source/` 文件快照；来源工作树的 HEAD 不能单独代表该配置，因为其包含未提交和后续工作区修改。**来源工作树、来源 branch、历史代号与精确原始运行目录的映射只在 [README 来源与追溯](/home/hynx/lizhuo/VLA-Pilot++/README.md#来源与追溯) 登记**，此稿不重复建立另一份映射。

迁移前已保存 [pre-integration/manifest.json](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/pre-integration/manifest.json) 与 [accepted-source 快照](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/pre-integration/accepted-source)。清单包含 **48 个已核验来源文件**，其中原审阅状态为 37 个 untracked、5 个 tracked_modified、6 个 tracked_clean；48 个冻结副本与验收 SHA 全部一致。本次独立只读复核也确认这 48 个来源文件仍与清单 SHA 一致。已有 5 个主工作区未跟踪文档单独留存，来源工作树未被用于直接运行新入口。

新运行自身的 manifest 固定了 **105 个源码/config 文件 SHA**、commit、resolved config SHA、机器配置 SHA、environment SHA、任务/seed、provider/model/effort。48 个来源文件与105个新运行快照文件是两种不同范围，不能互相代替。

## 阶段 2：便携化资产、CPU 与设备链路

- 新入口、worker、配置解析及审计入口已落在当前仓库，实际方法本阶段只开放 `eds`。科学 prompt 的字节一致性已记录在 [源码迁移审计](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/checks/rdt-runtime-migration-audit.json)；原研究 runner 不作为新入口依赖。
- LIBERO 已在当前仓库 `third_party/libero_pro` 准备独立代码与必需资产，固定上游 commit 为 `eafdb809426b13153aa1e4c42d6601844217dfec`。正式规范化、补丁与 overlay 流程从本地固定 Git 对象重建，**2,308 个文件 SHA 全部一致**。该证据是离线重建，未声称已完成全新网络下载或干净 clone 安装。
- RNG 最小包位于 `tests/fixtures/steering_rng/`：**10 任务 × prepare/rollout 两阶段，共20个状态文件**；manifest采用相对路径，20个文件内容 SHA 均一致，calibration audit SHA 与 manifest 绑定。任务 seed 为 `[44,235,43,546,6,621,197,87,151,548]`。包仅保存 RNG 初始化，不包含历史回复、动作、reward 或环境状态。calibration 的10回合、127/127事件、首粒子和视频各10/10 hash一致属于诊断性历史重放，`online_performance_result=false`，不计入当前在线成绩。
- 权重内容没有改写。[model-assets.json](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/environment/model-assets.json) 记录 RDT config/EMA、normalization 所在源码、T5/SigLIP 精确 snapshot、DINO 权重及178个本地代码文件 SHA。T5 snapshot 为 `3db67ab1af984cf10548a73467f0e5bca2aaaeb2`，SigLIP snapshot 为 `9fdffc58afc957d1a03a25b10dba0329ab15c2a3`。RDT normalization 位于源码中的 `DATA_STAT`，本机 checkpoint 没有单独 normalization sidecar；报告没有凭空补一份。机器专属路径保留在不提交的 [local.yaml](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/local.yaml)。
- 主迁移与 runner CPU 检查最终结果为 **1,118 passed，2 warnings，82.42 秒**，含26项新增 runner 检查。此前源码迁移 JSON 中仍有1,092项较早记录，最终数量以 [cpu-migration.log](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/checks/cpu-migration.log) 为准。这不是在线任务成功率证据。
- 08:40:00–08:40:48 UTC 的组合预检通过：一次 Codex 图像响应、GPU tensor 运算、LIBERO ObjectSwap task0 reset/render `[128,128,3]`。它被明确记录为 `preflight_not_performance`。
- 独立设备查询确认当前主机 **物理 GPU2 → visible cuda:0 → EGL1**，GPU 为 NVIDIA H200 NVL，UUID `GPU-a5d6a5f8-b6df-7f3a-c3dc-19734c41ec0e`，PCI `0000:41:00.0`，`CUDA_DEVICE_ORDER=PCI_BUS_ID`。此结论来自 [gpu-mapping.json](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/environment/gpu-mapping.json)，不是由 CUDA 数字猜测 EGL 数字。

## 阶段 3：冻结的在线 EDS 与已完成对照

运行目录为 [eds-migration-20261013](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/runs/eds-migration-20261013)。manifest创建于2026-10-13 09:04:04 UTC，worker于09:04:05 UTC启动；固定任务0–9、上述10个seed、每任务上限720动作，`codex_cli` / ChatGPT / `gpt-6-astra` / `low`，每任务fresh reward、在线Stage，QD archive关闭。运行中的科学代码/config保持冻结。

| 已完成的检查范围 | 实际证据结论 | 不能据此扩大的结论 |
| --- | --- | --- |
| 任务0第一个 reward 的 prompt 与 query image | 两者分别与来源 SHA 完全相同；本次fresh reward的64 probes有效 | 相同输入不意味着调用复用了历史响应 |
| task0步骤0、8、16、64的4个初始guided chunks | 搜索科学字段相同；差异限于latency/job/method label/可视化路径等元数据 | 不是全十任务搜索轨迹等价 |
| task0前两个guided chunks（步骤0、8）的机制trace | **258 tensor leaves**及科学scalar一致；共检查5324 scalar leaves，差异为两个初始采样latency元字段 | `initial-trace-comparison.json` 的总 `identical` 为false；不能说整个文件逐字节一致 |
| task0完整动作序列 | 当前与来源均720步，**720步executed actions全部一致**，不同步骤数为0；`online_requests_replayed=false` | 不保证其他任务或另一次在线随机调用也相同 |
| task0 provider/新生成/Stage/control合同 | 1722项PASS；39 Stage captures（1 identity+38 observation）和1 fresh reward与compute对齐，720 action与720 adapter exits对齐 | 不是全cohort已通过，也不是独立服务端model attestation |

任务0已经正常完成720步，环境 `success: False`，对应 [console.log 第252行](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/runs/eds-migration-20261013/console.log:252) 与失败视频。它是必须保留的合法科学失败；目前没有证据把它误判为运行基础设施失败，也没有通过替换任务/挑选成功重跑来组成分数。完整动作与来源一致，只证明本任务迁移行为一致，不把任务失败改记成功。

独立补审草案与transport helper全部位于 `/tmp`，**44项CPU正反例通过**。合法reasoning、消息lifecycle、冻结policy允许的warning/reconnect/fallback/transport retry可接受；错seed/identity/reply、缺失/重复capture或compute、reward输入/输出篡改、动作override与marker形状错误会被拒绝。它不执行保存的reward代码，不导入历史runner。`cohort_valid`始终为null；CLI exit0仅表示没有FAIL，完整任务必须同时检查`task_contract_valid`及`task_evidence_complete`。

本稿只读快照中worker状态为 `running`。[progress.json](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/runs/eds-migration-20261013/progress.json) 在 `2026-10-13T10:03:22.804317+00:00` 记录completed=2、errors=0、successes=0、当前task=1、step=712。这是运行进度，**不能写为0/10或完整成绩**；后续状态可能继续变化。

## 已发现但尚未完成的纠正项

**依赖声明需要纠正，不能继续称“53个pins已准确复现环境”。** [实际CPU导入观察](/tmp/runtime-import-versions.json) 在独立CPU进程使用相同 runtime PYTHONPATH 记录了53个核心包导入路径/入口hash；6个既有精确pin与实际模块版本不同：

| 包 | 原声明pin | 实际导入版本 |
| --- | --- | --- |
| `accelerate` | `1.12.0` | `1.13.0` |
| `einops` | `0.8.1` | `0.8.2` |
| `gymnasium` | `1.2.2` | `1.2.3` |
| `numpy` | `2.2.0` | `2.2.6` |
| `pillow` | `11.3.0` | `12.2.0` |
| `psutil` | `7.1.3` | `7.2.2` |

实际 PyTorch 为 `2.7.1+cu126`、torchvision为`0.22.1+cu126`、transformers导出版本`4.53.3`、diffusers`0.35.2`、MuJoCo`3.7.0`、robosuite`1.4.0`。没有导出`__version__`的9个包不能仅凭dist-info冒充独立源版本证明。Draccus的官方0.10.0 wheel本身导出0.8.0旧标记，OpenCV的模块版本不含distribution build suffix，不能把这些机械改成模块字符串；另有networkx当前导入失败记录，不能声称完整传递依赖已通过。

该观察没有初始化CUDA、没有改共享环境，也不是对已运行worker内存的反射读取。原冻结环境清单继续作为当时产物保留；准确安装声明、干净环境重建验证由安装负责人后续处理，禁止在本轮冻结验收中原地修复共享环境。**NumPy实际为2.2.6**；README目前2.2.0的表述必须随安装说明一并纠正。

**公共命名尚不统一。** 当前README正文第3、12、15、17、46、108行仍散落 `V17`，违反用户要求的算法中立公共命名；后续应改为“EDS迁移基线/EDS配置/在线Stage”等准确方法或机制名称。研究代号与来源路径的对应关系只留在README来源追溯节。此稿仅指出问题，没有修改README。

## 最终三模式结果表（待完成；没有预填新成绩）

共同条件待正式锁定并登记：LIBERO object-swap OOD、10任务×1回合、同一seed/RNG协议、每任务720动作上限、同一在线Stage、同一fresh reward/provider/模型与权重。算法compute不同应记录实际reward/model/denoising评估次数和耗时，不能仅因episode动作上限相同就称等计算预算。

| 方法 | 新full10成功数 | 协议/控制审计 | 方法机制证据 | compute/耗时 | run manifest与代码SHA |
| --- | --- | --- | --- | --- | --- |
| `vls` | — 待完成 | 待完成 | guidance实际生效与Stage共用合同待验 | 待记录 | 待登记 |
| `eds` | — 在线进行中 | task0已补审；完整cohort待完成 | 当前为archive OFF；完整机制审计待完成 | 待汇总完整cohort | 已有冻结manifest；最终结论待登记 |
| `eds_qd` | — 待完成 | 待完成 | archive/descriptor/parent selection确实生效待验 | 待记录 | 待登记 |

“待完成”不代表已运行、通过或达到某个分数。历史3/10不填任何一行。完成后的科学结果与协议有效性分列；不能为了得到历史分数反复抽取幸运结果。

## 合并到main时必须填入的证据字段（待完成）

| 字段 | 本稿可填值/状态 |
| --- | --- |
| main起点 | `d51cb85f485502e0429c79529872efef2ec59981` |
| 整合分支 | `codex/rdt-steering-integration` |
| 本轮EDS冻结commit | `cfecb12db736f1a3408d9528d9336aadcb7e41b5` |
| 最终整合commit、merge commit、merge后main SHA | 待完成，不能用本轮冻结commit冒充已合并 |
| source/config/assets/model/RNG manifests及SHA | 已有本轮证据，最终合并版本须再次对应 |
| 精确依赖与干净安装验收 | 待安装声明纠正与复验 |
| 三模式配置、完整在线run、任务/seed/steps/success/error分母 | 待完成并保留所有科学失败 |
| provider/新生成/控制/marker/compute及QD机制audit | 任务0合同已补审；全量和模式审计待完成 |
| 最终CPU命令及结果 | 本轮1118项迁移检查与44项独立补审；最终合并检查待登记 |
| README公共命名、结果与唯一来源追溯映射 | 待统一和更新 |
| 本地merge、remote同步/推送状态 | 本地尚未merge；remote状态本稿未核验，不声称已发布 |

## 证据索引与SHA256

以下SHA是本稿读取的小型清单/报告文件内容hash；权重本体hash引用已生成的model-assets清单，没有重复读取数十GB权重。运行中的progress/status没有作为最终验收结果固定，最终全量报告应附结束时快照。

| 证据 | SHA256 |
| --- | --- |
| [迁移前来源清单](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/pre-integration/manifest.json) | `ba5b0215c1c9c3ca903dd07394db841721c7d949e069283d1a49970fe085595c` |
| [源码变换与科学 prompt 检查](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/checks/rdt-runtime-migration-audit.json) | `a20fc3e79c12d29389abc74847470f6977c1483b22eb4797e8d5f4ed3e301ca8` |
| [最终迁移 CPU 日志](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/checks/cpu-migration.log) | `06a32fe228e5e6cf53bc1825152b3685d55cc74f1f896e73b30293f7f42610fb` |
| [LIBERO 文件清单](/home/hynx/lizhuo/VLA-Pilot++/scripts/steering_assets_manifest.json) | `8b6fa91960398a25af011c2fa9458f910ad4aa4599b45a853b04d743cac7711c` |
| [LIBERO 离线重建](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/environment/libero-clean-reconstruction.json) | `5466e5576b70cc22e49a5b8cdbb7adfebebe3179fc92c64cba30d698c70e9564` |
| [资产完整性](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/environment/asset-verification.json) | `d97e5a82152a498ab9526bcf3d91303e197af58b6b2374b4ef8914e3e4378baf` |
| [模型与 normalization 哈希](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/environment/model-assets.json) | `b9701e584d6e3522716063af8ea5874007d352d1af620cdbc868afcd55ba0c7e` |
| [RNG manifest](/home/hynx/lizhuo/VLA-Pilot++/tests/fixtures/steering_rng/fixture-manifest.json) | `628c429d457def157c9163be94a1202721673f97f1e43aa6446e5a06889c6043` |
| [RNG calibration audit](/home/hynx/lizhuo/VLA-Pilot++/tests/fixtures/steering_rng/audit.json) | `25eaa4854a84bd2051646491741cc9cdcb3cf9fb377b5555301b8134585f6d95` |
| [组合预检](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/preflight-service/report.json) | `28130cc134589e4a58cfaaa0542878012859a622e6e891f52a20e5ddf05a659d` |
| [GPU/EGL 映射](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/environment/gpu-mapping.json) | `c9bac9b935e043ef13a72ad804ae81516a4180bb813718f8babc9d8470733d15` |
| [新运行 manifest](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/runs/eds-migration-20261013/manifest.json) | `ab4d36d2519b57185250fa647095768f1c70598ce8e55bc474cc77c68a90ca2c` |
| [新运行 resolved config](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/runs/eds-migration-20261013/resolved-config.yaml) | `4b4a27116b3602d9a28d8c4e30a1d89d3d927fffef5acec4499b0405a28c8844` |
| [新运行 environment](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/runs/eds-migration-20261013/environment.json) | `7e334dd1f7630f595346f885c1910314a5f1ce473ac05d73abe0bc3f79df275f` |
| [初始 prompt/image 对照](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/runs/eds-migration-20261013/initial-input-comparison.json) | `dfa06c5b0fa4bd0b6dd53a88b1311ce7c4b25c9ccf23ecbf03987eb635ac4660` |
| [4 个搜索 chunk 对照](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/runs/eds-migration-20261013/initial-search-comparison.json) | `d8c98fdb9fdea1c195524d9774602c0bb3a64c1749123570b34cfb6e6185ada4` |
| [前两个机制 trace 对照](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/runs/eds-migration-20261013/initial-trace-comparison.json) | `b1bb27a3fb45ff4726d656861cc56d5a3f3cc162cf3f9f49d52f653100207b6f` |
| [任务 0 全动作对照](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/runs/eds-migration-20261013/task0-action-comparison.json) | `7cd64f1d8f142a82c413541969c4034c97ce5f541da18c094e9c86a8ed90a6b1` |
| [任务 0 合同离线补审](/tmp/steering-task0-contract-v3.json) | `3c77f1e3ba3ed2b236a2298e5133a4969aceccbe4ef60aa572c2d24e0b2c4422` |
| [补审 CPU 验证及脚本清单](/tmp/steering-offline-audit-validation.json) | `ec1887626bf3c267f7f5a19408c8577017d97b45b9d74f97920c1305fbc75cbd` |
| [实际导入版本纠正](/tmp/runtime-import-versions.json) | `dd0a4911aef33b6a4d35136e420b0ceeba3f6dbf2ceb7ba00d01d412372d3983` |
