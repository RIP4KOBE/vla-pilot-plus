# 运行、结果与归档

公共入口是 `scripts/run_steering.py` 与 `scripts/evaluate_steering.py`，均使用同一launcher。默认评测十任务；`--tasks 0,1` 选择显式子集。每个方法/运行使用新的输出目录，期间冻结源码、配置、依赖和资产。安装与预检见[安装说明](installation.md)，已完成证据与发布身份见[状态页](integration-status.md)。


三种方法可在同一已分配设备上顺序运行，使用同一机器配置和不同新目录。下面的预览不启动任务；单任务诊断与完整cohort是二选一的不同用途，诊断成功不能拼入正式成绩。

```bash
STEERING_RUN_ID=my-new-run
for method in vls eds eds_qd; do
  python scripts/run_steering.py --method "$method" --local-config configs/local.yaml \
    --output-dir "outputs/${STEERING_RUN_ID}-${method}-preview" --print-config
done

# 可选：单任务诊断示例。
python scripts/run_steering.py --method eds --local-config configs/local.yaml \
  --output-dir "outputs/${STEERING_RUN_ID}-eds-task0" --tasks 0

# 正式三组，顺序执行；每组默认十任务。
for method in vls eds eds_qd; do
  python scripts/evaluate_steering.py --method "$method" --local-config configs/local.yaml \
    --output-dir "outputs/${STEERING_RUN_ID}-${method}-full10" || break
done
```

要并行运行，分别配置并验证已获分配的GPU/EGL和新的local配置；不要将示例循环改成共享同一设备的后台启动。本次已完成验收的结果见[完整结果](results.md)，无需为阅读报告重跑。

## 找到需要的证据

| 文件 / 目录 | 用途 |
| --- | --- |
| `manifest.json`、`resolved-config.yaml`、`source/` | 实际受测源码、任务/seed、方法与配置身份 |
| `local-config.yaml`、`environment.json` | 无凭据的机器配置快照、依赖入口、资产校验与设备绑定 |
| `status.json`、`progress.json`、`console.log` | worker/launcher状态、最近进度与故障；进度不是最终验收 |
| `output/evaluation/` | 新入口的Stage、方法机制、RNG、动作/计算等记录；具体目录由manifest声明 |
| `output/captured_stage_inputs/` | 在线Stage输入、图像、回复与transport记录 |
| `output/episode_*/vlm_agent/` | 每任务新生成reward的输入、程序、合同及请求记录 |
| `output/episode_*/` 下的视频 | 解释成功、失败和控制行为；保留完整原件 |
| `audit.json`及明细 | 完整性、在线合同与方法机制的验收结果 |

候选reward数值在本地计算，不能将候选评分次数算作模型API请求。在线计数按身份、reward生成/修复和Stage observation分别保存。fresh指本程序为当前任务/观测发起新请求，不使用旧回复回放；provider的`cached_input_tokens`是另一层输入前缀计数，照实保留。

## 只读复查与单独报告

```bash
# 完整cohort只读复查，不覆盖原审计。
python scripts/audit_steering.py outputs/eds-full10-001 --no-write

# 将新一次审计写到独立review目录，保留原audit.json。
python scripts/audit_steering.py outputs/eds-full10-001 \
  --output reviews/eds-full10-001/audit.json

# 每任务合同复查；完整验收应覆盖所有任务。
python scripts/audit_steering_contract.py outputs/eds-full10-001 \
  --task 0 --report reviews/eds-full10-001/task0-contract.json
```

最后一个命令的report父目录需先存在。任务审计只回答该任务的证据合同；完整cohort还要求全部任务/seed、退出状态、源码/config身份和方法机制一致。保存每个普通失败，区分基础设施错误、未完成和无效证据。视频、reward高分或单个成功任务不足以登记完整成功率。

默认VLS、EDS、EDS+QD预算不同，报告同时给出guided/unguided块数、DiT calls/batch rows、评分/梯度调用、延迟与在线请求。合法零梯度和FKD的ESS跳过按真实记录呈现。QD需证明archive实际供给父代和最终选择；shadow observer自身不能证明QD已启用。

## 保存与分享

保存原始源码快照、配置/环境receipt、所有输入输出、机制日志、动作和视频，连同逐文件hash及可访问的位置。模型和大型原始文件不进Git；必要fixture与小型报告随代码审阅。fixture中的裁剪/合成测试数据不替代完整原始运行。

本次完整运行归档与准确模型资产保存在维护者本机，没有配置公开下载包；小型[逐任务结果及证据hash](validation/final-results.json)随Git提供，维护者本机证据索引在 [README provenance](../../README.md#provenance)。分享时分别标明受测runtime commit、审计器commit/source hash、最终发布/merge commit。原始归档不可为了新机器路径或新审计器而改写receipt。

<a id="prepared-infrastructure"></a>
## 生命周期与可移植归档

本节功能已在三组原始验收与最终汇总封存后接入，并完成两环境CPU回归。它们不在本轮在线受测runtime中；后续checker与发布身份分别见[状态页](integration-status.md)。修复不改科学配置、策略、Stage或模型。

launcher在成功取得新目录后管理worker生命周期。SIGINT/SIGTERM会在仍持有GPU锁时清理其拥有的进程树，保留部分输出并写入`interrupted`状态，不自动重试。以下适用于使用当前launcher的新运行；PID应取自自己run的`status.json.launcher_pid`：

```bash
kill -TERM "$OWN_STEERING_LAUNCHER_PID"
```

SIGKILL、主机退出和提前逃逸/重新挂父的子进程需要外部监督；Python清理不能保证覆盖这些情况。冻结版本的旧launcher不能据本段获得新的终止保证。

归档审计从哈希绑定的原配置恢复原始run/job身份，用当前归档内的相对位置读取证据。新增support包只保存任务表与RNG manifest，并按原配置/资产清单校验准确hash。它不替代完整视频/捕获归档、模型资产或科学重跑所需RNG状态文件。使用新目录保存support与重审报告：

```bash
# source run须已终止；support-dir是原run之外的新目录。
python scripts/prepare_steering_archive.py /preserved/run \
  --support-dir /archive/run-support
# 原资产路径不可用时，可额外提供hash完全匹配的副本：
#   --task-map /verified/libero_suite_task_map.py
#   --rng-manifest /verified/fixture-manifest.json

# 对移动或改名后的完整副本写独立审计，不改原receipt。
python scripts/audit_steering.py /archive/copied-run \
  --archive-support /archive/run-support \
  --output /archive/review/audit.json
```

新审计器必须另记身份和调用；原实验仍属于其受测runtime。新的路径解析不能放宽数值、机制或完整性gate，也不能借原机器文件掩盖不完整的归档。


归档协议兼容按冻结schema区分：v1的job ID固定为`output`，v2为原run目录名；未知schema及交叉错配会失败。对已完成迁移归档的真实复制/改名验证已通过，但v1 wrapper仍仅为`legacy_basic_only`，不能提升为v2成绩。它保留auditor仓库内的RNG fixture查询路径，因此该验证将support中已校验的相同fixture放到独立auditor路径；十份任务合同直接使用support。完整验证范围见[整合状态](integration-status.md#验收后基础设施与归档)。

真实公共EDS v2归档已用接入前的独立checker完成复制/改名、原workspace路径不可读条件下的完整重审；原run字节与受测身份保持不变。这是独立checker的离线验证，不是重新运行任务；后续基础设施接入不改变原实验归属。见[验证receipt](../../.worktrees/exp/steering-integration/checks/archive-v2-candidate-validation/receipt.json)和[当前状态](integration-status.md)。
