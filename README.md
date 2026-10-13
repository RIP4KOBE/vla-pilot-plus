# VLA-Pilot++：RDT steering

在共享的机器人观测、在线视觉 Stage 控制器和执行链上，比较 **VLS、EDS、EDS+QD** 三种推理方法。公共入口分别使用 `vls`、`eds`、`eds_qd`，配置位于 [configs/steering](configs/steering)。

**当前处于主线整合阶段，尚未完成最终合并。** 迁移版 EDS 已完成有效十任务验收：**3/10，成功 task ID 为 3、8、9**。三模式配置、统一 Stage 进度接口与资产校验已落地；公共版本在原运行环境及独立安装环境均通过 1403 项 CPU 测试，三张卡的 CUDA/EGL 渲染和 QD 数值检查已通过；EDS、VLS、EDS+QD 各自完整十任务仍待完成。不要把迁移结果写成这三个新 cohort 的成绩。[完整状态与逐任务结果](docs/steering/integration-status.md)。

| 方法 | 候选生成与选择 | 配置 |
| --- | --- | --- |
| VLS | 在去噪中使用 reward 梯度、多样性梯度和 FKD 粒子重采样；20 个候选 | [vls.yaml](configs/steering/vls.yaml) |
| EDS | 16 个候选，RBF 多样性采样、reward 评分、10 轮父代重采样与截断去噪 | [eds.yaml](configs/steering/eds.yaml) |
| EDS+QD | 共用 EDS 搜索，动作块内 4×4 行为网格 archive 提供父代与最终候选 | [eds_qd.yaml](configs/steering/eds_qd.yaml) |

默认配置的计算预算不同；QD archive 每个动作块重新建立，没有跨任务记忆或递归自我改进。[算法细节与限制](docs/steering/architecture.md)。

## 从安装到运行

先按 [安装说明](docs/steering/installation.md) 创建独立环境，准备固定 LIBERO、模型/DINO 资产和 `configs/local.yaml`。已验证的依赖配方在真实干净环境通过 1118 项 CPU 测试；该证据不包含新环境 GPU 推理或在线服务。**模型内容与实际加载路径校验是 configure、preflight 和真实 launcher 的必经步骤**，不以“文件存在”代替身份校验。

以下命令从仓库根目录、已激活的新环境执行。输出目录必须不存在；示例在线命令是已实现入口，最终版本的运行验收仍待完成。

```bash
# 三种配置均可预览；只解析配置，不创建运行目录或调用 GPU/API。
python scripts/run_steering.py --method vls --local-config configs/local.yaml \
  --output-dir outputs/vls-preview --print-config
python scripts/run_steering.py --method eds --local-config configs/local.yaml \
  --output-dir outputs/eds-preview --print-config
python scripts/run_steering.py --method eds_qd --local-config configs/local.yaml \
  --output-dir outputs/eds-qd-preview --print-config

# 显式运行资产、GPU/渲染和一次真实 Codex 图像请求预检；不是任务成绩。
python scripts/check_steering.py --local-config configs/local.yaml \
  --output-dir outputs/preflight-001 --gpu --api

# 每种模式的单任务诊断入口；子集不能登记为十任务成绩。
python scripts/run_steering.py --method vls --tasks 0 \
  --local-config configs/local.yaml --output-dir outputs/vls-diagnostic-001
python scripts/run_steering.py --method eds --tasks 0 \
  --local-config configs/local.yaml --output-dir outputs/eds-diagnostic-001
python scripts/run_steering.py --method eds_qd --tasks 0 \
  --local-config configs/local.yaml --output-dir outputs/eds-qd-diagnostic-001

# 默认包含全部十任务。替换 --method 与新目录即可评测另外两种方法。
python scripts/evaluate_steering.py --method eds \
  --local-config configs/local.yaml --output-dir outputs/eds-full10-001
python scripts/evaluate_steering.py --method vls \
  --local-config configs/local.yaml --output-dir outputs/vls-full10-001
python scripts/evaluate_steering.py --method eds_qd \
  --local-config configs/local.yaml --output-dir outputs/eds-qd-full10-001
```

在线路径使用 **Codex CLI / gpt-6-astra / low**，需要使用者自己的有效 CLI 登录。每任务新生成身份描述和 reward，Stage 随执行在线查询。机器配置只保存资产路径与设备选择，不保存凭据。launcher 使用配置中的 GPU/EGL 编号，不能通过 shell 的 CUDA 编号覆盖它；只在设备已分配且空闲时启动，禁止中止他人进程。

## 查看与审计结果

每次运行保留 `manifest.json`、`resolved-config.yaml`、无凭据的 `local-config.yaml` 快照、`environment.json`、源码快照、`status.json`、`progress.json`、`console.log` 和 `audit.json`。新公共入口的机制/计算日志位于 `output/evaluation/`；原始在线捕获位于 `output/captured_stage_inputs/` 等捕获目录；视频位于 `output/episode_*/`。具体目录以 run manifest 为准。

```bash
# 完整 cohort 审计：检查在线合同及方法机制，更新 audit.json 和明细。
python scripts/audit_steering.py outputs/eds-full10-001

# 只读复查已有结果，不覆盖原审计；历史格式会标明审计范围。
python scripts/audit_steering.py outputs/eds-full10-001 --no-write

# 每任务离线合同审计；完整验收须覆盖 0..9，不能只检查 task 0。
python scripts/audit_steering_contract.py outputs/eds-full10-001 \
  --task 0 --report outputs/eds-full10-001/task0-contract-review.json
```

任务失败只有在完整运行证据有效时才计入成功率。依赖/服务错误、缺捕获、初始化失败、源码或配置漂移应登记为无效或未完成。视频用于解释行为，环境 success 与完整审计共同支持成绩；一次固定十任务结果不证明独立泛化或统计稳健性。日志中的请求模型标记也不独立证明服务端内部模型权重或路由。

原始日志、视频和大型模型不进入 Git；必须在外部归档保留，随报告分享可访问的清单、哈希和位置。当前公开可访问的完整证据归档链接仍待维护者提供，仓库中的小型测试 fixture 不替代原始运行证据。

协作方式见 [CONTRIBUTING.md](CONTRIBUTING.md)。仓库现有 [LICENSE](LICENSE) 为 MIT；第三方代码、模型和数据分别受其原许可约束，不据此推定外部资产可再分发。

## Provenance：来源与本地证据

历史名称只在本节用于追溯，不作为公共方法或配置入口。下列身份属于不同阶段，不能合并为一次实验。

| 来源 | 身份与范围 |
| --- | --- |
| 原 main | `d51cb85f485502e0429c79529872efef2ec59981` |
| 来源研究 worktree | `.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-gpu6-20260922T063626Z/study_worktree`；来源 HEAD `77761b4cda78ac3b6762a6aa60f97b07fde7c1dc` |
| 来源在线 baseline | `codex_failed_contact_v17_historical_initialization_online_full10`，位于来源 worktree 的 `artifacts/stage_closed_loop_20260929/runs/`；该轮 3/10、QD OFF，是来源证据 |
| 来源快照 | 48 个验收文件，含 37 个 untracked、5 个 modified、6 个 clean；仅 merge 来源 HEAD 会遗漏内容 |
| 当前整合分支 | `codex/rdt-steering-integration`；最终合并 commit 待填 |
| 新迁移验收 | 冻结 commit `cfecb12db736f1a3408d9528d9336aadcb7e41b5`；新在线十任务有效 3/10；最终公共版本另行验收 |

命名映射：`core/c0_reward_contract.py` → `core/target_distance_reward.py`；`core/poe_stage_capture.py` → `core/stage_capture.py`；`vlm_query/c0_contract_v1` → `vlm_query/target_distance`；reward 合同 `c0_xyz_v1` → `target_distance`。Stage profile `evidence_v1/contact_v2/grasp_v3/proprio_v4` → `evidence/contact/grasp/online`。

科学提示词保持原字节，[guidance_template_libero.txt](vlm_query/target_distance/guidance_template_libero.txt) 中两处 **C0** 为保留原始模型 stimulus 的兼容例外。它不是公开方法名；改写这些文字须作为新实验条件评审。

历史 P2 同轮控制的 4/10 属于另一套 provider/reward/Stage 条件；标准 `libero_object` 的无引导 9/10、VLS 7/10也不是 ObjectSwap OOD 成绩，不能以数字直接排序当前方法。

以下链接指向维护者机器上的 ignored 证据目录，普通 clone 不会自带；它们不是安装依赖或公开下载承诺：

- [迁移完整报告](.worktrees/exp/steering-integration/runs/eds-migration-20261013/migration-full10-report.md)、[验收及逐文件哈希](.worktrees/exp/steering-integration/runs/eds-migration-20261013/migration-full10-acceptance.json)。该运行目录保留逐任务合同、动作比较、捕获、日志与视频。
- [迁移 CPU 日志](.worktrees/exp/steering-integration/checks/cpu-migration.log)：1118 passed、2 warnings、82.42s。
- [干净安装报告](.worktrees/exp/steering-integration/pending-integration/steering-clean-install-report.md)、[验收摘要](.worktrees/exp/steering-integration/pending-integration/clean-install-validation-summary.json)：1118 passed、1 warning、86.53s，绑定迁移提交。原始外置安装日志位置由该摘要记录。
- [首次 GPU/API 预检](.worktrees/exp/steering-integration/preflight-service/report.json)：CLI 0.156.1；本机 GPU2/EGL1 的身份关系见[设备记录](docs/steering/validation/gpu-mapping.json)。这不是可移植设备编号。

公共版本 CPU 两环境均为 1403 passed，GPU 映射及 QD 数值结果已记录；三模式独立 cohort、可分享的证据归档和合并 commit 仍待补，详见[整合状态](docs/steering/integration-status.md)。
