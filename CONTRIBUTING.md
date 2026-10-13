# 协作与验收

公共方法为 **VLS、EDS、EDS+QD**，CLI 使用 `vls`、`eds`、`eds_qd`。先读[架构合同](docs/steering/architecture.md)与[当前验收状态](docs/steering/integration-status.md)，安装见[环境说明](docs/steering/installation.md)。历史来源和命名例外统一放在 [README provenance](README.md#provenance)。

## 提交与评审

从更新后的main建立功能分支，通过PR合入。本次发布的main合并身份见[状态页](docs/steering/integration-status.md)；该字段填写前，整合分支尚不代表已发布的main。PR 写清具体问题、最终行为、影响方法、真实验证命令/结果与未验证范围。保留其他协作者改动，不通过重建 reference 消除回归。

```bash
# 在工作区干净且本次整合已发布到main后执行。
git fetch origin
git switch main
git pull --ff-only origin main
git switch -c codex/my-steering-change
# 编辑并完成相应验证，再提交并推送自己的功能分支。
git push -u origin codex/my-steering-change
```

| 变更类型 | 验证重点 |
| --- | --- |
| 策略、Stage、提示词、初始化或科学配置 | 行为回归、新配置身份与新的在线 cohort |
| launcher、资产/审计、安装等基础设施 | 故障与负例回归；证明正常科学输入不变；运行仍绑定实际受测 commit |
| 文档、注释与纯展示 | 来源与命令核对；编辑后的发布 commit 不替代旧实验 runtime 身份 |

三组完整在线验收已封存：EDS 3/10、VLS 1/10、EDS+QD 1/10，30个任务全部有效，整合gate通过。随后接入的生命周期/归档修复在两环境各通过1436项CPU测试；在线成绩仍绑定原受测runtime，见[状态页](docs/steering/integration-status.md)和[运行与归档说明](docs/steering/evaluation.md#prepared-infrastructure)。

## 配置冻结与对照

科学设置放在[共享 ObjectSwap 协议](configs/evaluation/libero_object_swap.yaml)和[方法 profile](configs/steering)。机器路径、GPU/EGL与显存选择放在 ignored `configs/local.yaml`。凭据、权重和大视频不提交；必要科学 fixture、expected manifest与来源说明随代码审阅。

每次完整 cohort 使用新目录。启动前记录假设、源码/配置、任务与seed、资产、初始化和服务参数；运行期间保持源码、profile、提示词、依赖及资产不变。保留全部成功、失败、基础设施异常和原始捕获。中断/源码漂移不自动重试，不把多轮成功拼成一个分数。

对照匹配 suite、任务/seed、初始化、资产、Stage规则、动作 horizon、720步上限及模型请求参数。不同轨迹允许有不同在线查询时刻。默认 VLS 与 EDS/QD 不等计算预算，应同时报告模型 calls/batch rows、reward与梯度调用、引导/非引导块、延迟和在线调用数；等预算比较需单独配置。

## 算法语义与测试

接口清理保持动作值/dtype/夹爪符号、评分切片与运算顺序、父代选择、RNG恢复时点、模型/评分调用数、Stage/query时机及reference生命周期。temperature、RBF势函数、prompt、Stage阈值、动作块、初始化、缓存或 archive 规则的变化均需作为科学改动登记。

EDS 的 `get_stage_reward()` 只读已有进度；VLS 使用独立最终选中候选 score/reference。VLS梯度能力探针或telemetry不能进入EDS路径消耗随机数或改变评分。可评分与可微分是不同能力；合法的最优点零梯度、FKD的ESS跳过须保留。

先运行与改动有关的行为/负例测试，再完成规定全套检查。普通CPU命令如下；它隐藏CUDA并关闭`.env`读取，但不构成网络隔离：

```bash
env -u VLA_CODEX_ONLY CUDA_VISIBLE_DEVICES='' PYTHON_DOTENV_DISABLED=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  python -m pytest tests -q --disable-warnings -p no:cacheprovider
```

[EDS CPU reference](tests/fixtures/steering_eds_golden/README.md)检查搜索、转换/cache、Stage、父代与RNG，模型/传感器/provider为确定性合成输入。新clone的测试不应依赖维护者私有路径、模型或在线服务。裁剪真实捕获需保留hash与来源；合成结束receipt只用于测试。QD实际参与需由archive更新、父代来源和最终选择证明，observer计数本身不够。遇数值差异先保存完整输入和差异，再定位原因。

## 结果、资产与发布

报告分别回答任务success、证据有效性与机制记录一致性。记录受测runtime commit、配置/资产/环境identity、逐任务outcome、基础设施错误、初始化与在线捕获、实际计算量、审计器身份和报告hash。未完成/无效任务保持相应状态；不能登记为正常失败或提前宣告方法优劣。

资产验证比较固定内容和真实加载选择。保留正常HF snapshot链接；DINO bytecode兼容边界与clean分发策略见[安装说明](docs/steering/installation.md)。权重、源码和数据的获取方式与许可分别交接。

原始日志/视频保存在外部归档，Git保存小型报告、manifest和必要fixture。本次全部逐任务结果与原始证据hash保存在[随Git摘要](docs/steering/validation/final-results.json)；完整归档与精确模型包只由维护者本地持有，尚无公开分发入口。交接时给出实际可访问的副本位置、字节hash和许可边界，分别登记runtime/auditor/release身份与真正的main merge commit。后续审计器只在独立报告中重新核验原始快照，原始receipt与运行成绩的源码归属保持不变。现有[MIT LICENSE](LICENSE)与各第三方许可分别适用。
