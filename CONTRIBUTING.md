# 协作与验收

公共方法名称使用 **VLS、EDS、EDS+QD**，CLI 为 `vls`、`eds`、`eds_qd`。算法合同见[架构说明](docs/steering/architecture.md)，环境与资产见[安装说明](docs/steering/installation.md)。来源命名、历史目录和分支映射统一记录在 [README provenance](README.md#provenance来源与本地证据)，不加入新的公共入口。

## 当前交付状态

迁移版 EDS 的完整在线验收已通过。三模式 profile、统一 Stage 进度、模型身份验证和离线审计已接入；最终公共版本的完整 CPU/GPU 验证与三组十任务仍待完成。[整合状态](docs/steering/integration-status.md) 区分已完成证据和待办，合并代码不等于性能验收。

在共同主线建立功能分支，通过 PR 审阅合入。PR 应写清触发问题、最终行为、影响的方法、真实测试命令与结果、未验证边界。保留用户和其他协作者的改动；不要用研究输出目录充当源码分支，也不要用重新生成 reference 的方式消除回归。

## 配置与运行冻结

科学设置分为共享 [ObjectSwap 协议](configs/evaluation/libero_object_swap.yaml) 和 [方法 profile](configs/steering)。机器路径、设备和显存配置放在被忽略的 `configs/local.yaml`；凭据、模型权重和大视频不提交。资产 expected manifest、科学 fixture 与其来源说明随代码审阅，不能仅因文件大而删除运行所需资产。

每个完整 cohort 必须用新的输出目录。启动前记录待验证假设、源码与配置、任务/seed、资产身份、初始化协议和服务参数；运行期间不得修改冻结源码、profile、提示词、依赖或资产。结束后保留全部失败、异常和原始捕获，不能从多轮挑选成功拼成一个分数。目录存在即换新 run ID；不要覆盖旧配置或继续给已漂移的运行计成绩。

对照匹配 suite、任务/seed、初始化、资产、Stage 规则、动作 horizon、环境步数上限和模型请求参数。不同轨迹可产生不同查询时刻，不通过回复回放强制相同轨迹。默认 VLS20 与 EDS16 的计算路径不同，须报告实际模型 batch rows/calls、reward/梯度调用、延迟及在线调用数；等计算预算比较需要单独设定。

## 算法修改与验证

接口清理必须保持动作值/dtype/夹爪符号、评分切片与运算顺序、父代选择、RNG恢复时点、去噪与评分调用数、Stage/query时机和 reference 生命周期。temperature解释、RBF势函数、prompt、Stage阈值、动作块长度、初始化、缓存或 archive 规则的变化都是科学改动，应有独立配置和新运行。

`get_stage_reward()` 对 EDS 只读已有进度；VLS 使用独立的最终选中候选 score/reference，不能借用内部梯度进度冒充。新增 VLS 梯度能力检查或 telemetry 不得进入 EDS 路径消耗随机数或改变评分。reward可评分与可微分是不同能力；最优点合法零梯度不能一概判坏。

用与改动相关的测试验证行为，完成规定的全套检查。以下普通 CPU 命令隐藏 CUDA、关闭 `.env` 读取，但本身不是网络隔离器：

```bash
env -u VLA_CODEX_ONLY CUDA_VISIBLE_DEVICES='' PYTHON_DOTENV_DISABLED=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  python -m pytest tests -q --disable-warnings -p no:cacheprovider
```

[EDS CPU reference fixture](tests/fixtures/steering_eds_golden/README.md) 比较真实搜索、动作转换/cache、Stage和父代路径，模型/传感器/provider为确定性合成输入。它不验证GPU核、真实渲染、模型权重或在线成功率。新 clone 应直接运行，不依赖维护者工作区、私有缓存或缺路径时跳过测试。

离线证据测试可使用裁剪的真实捕获，必须保留原始文件哈希及裁剪来源；合成完成状态只是测试 scaffolding，不能登记为真实任务成功。QD 验收要证明 archive 参与父代和最终选择；仅有 observer 或 per-cell计数不够。数值不一致先保存输入和完整差异，再定位原因；不能在看到任务结果后放宽 gate。

## 资产、日志与发布

模型验证必须对固定 expected manifest 比较内容及实际加载选择。保留 HF snapshot 到 blob 的正常链接；已有 DINO bytecode 的兼容边界要披露。新分发包可使用严格 clean 检查，不清理正在使用的缓存。权重、源码与资产的可获取性、许可和身份均需说明，不能用模型名称代替文件身份。

最终报告包含：冻结源码/配置、方法、任务/seed、每任务 outcome、基础设施错误、环境/资产identity、初始化与在线捕获、真实机制计数、计算量和各级审计。任务 success、证据有效性、视觉语义正确性分别回答。未完成/无效任务不伪装成普通失败；未运行的方法保留 pending。

原始视频和日志保存在外部 run 归档，保留原文件、manifest与哈希；仓库只放可审阅的小型报告和必要fixture。分享或发布前补可访问归档链接、最终commit及已验证命令。现有 [MIT LICENSE](LICENSE) 只按其范围适用；保留第三方许可证，不推定模型、数据或服务有相同许可。
