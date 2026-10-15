# 协作与验收

公共方法名称只使用 **VLS、EDS、EDS+QD**。算法解释见 [架构说明](docs/steering/architecture.md)，安装输入与能力边界见 [安装说明](docs/steering/installation.md)。来源版本、研究目录及分支映射集中放在 README 的 provenance，不进入公共 profile 或新增产品命名。

## 当前整合边界

**完整 EDS 迁移验收尚未结案。** 当前冻结 runtime/config/scripts/tests，准备工作只形成外部草案。文档中的未来接口、资产 gate 和独立审计测试不代表已经应用。

实施顺序保持：

1. 固定并验收迁入的 EDS 行为、依赖、资产和完整在线 cohort。
2. 通过最小外层 Stage 进度接口统一三种模式，先证明 EDS 行为不变，再开放公共 profile。
3. 建立共享任务/seed/资产/Stage/服务规则的独立完整对照，明确计算预算差异。
4. 完成协作框架与共同主线交付，再进行 QD 优化、跨任务记忆或递归改进研究。

不要因为子集任务成功、CPU 测试通过或内部实现存在，就跳过前一步 gate。运行中的完整 cohort 不能一边修改源文件一边继续计成绩。

## 修改如何进入共同主线

保留来源快照和来源 worktree，实施只在整合分支进行。最终以评审过的代码和新环境证据提交 PR，先同步 main、解决冲突、复核科学文件与测试，再按团队规则合并。merge 本身不是性能验收。交付后同事从共同 main 建立各自功能分支，不直接在研究快照或运行目录做合作开发。

PR 说明应给出具体问题、最终行为、受影响的方法、验证结果与未验证边界。例行重命名也要检查动态 imports、提示词字节、Hydra工作目录、路径依赖、RNG hooks与实际导入源；不要仅凭 git diff 大小断言无行为变化。

机器路径、GPU/EGL编号与输出位置放在本机配置。模型、登录信息和大型日志/视频不混入源码提交。科学配置、固定资产 expected manifest、测试 fixture 及其 provenance 则应随代码审阅。

## 保持 EDS 科学语义

对不改变算法的接口重构，以下都必须保持：动作bytes/dtype及gripper符号、评分切片与运算顺序、候选/父代选择、RNG序列与恢复时点、模型/reward/梯度/去噪调用数、Stage/query触发时点、guidance开关、reward reference与接触交接。

不要在接口改动中顺手调整temperature解释、RBF核、迭代数、动作块长度、初始化协议、prompt文字、Stage阈值、选择规则或缓存。新的方法设定应有独立配置与新run，不覆盖已冻结目录。

未来统一接口的最小边界是 `core/rdt_policy_steer.py` 与 `core/stage_evidence.py`，以及针对性测试。EDS 新getter直接读取已有值；VLS增加独立的最终候选外层参考，保留内部梯度参考和scale。VLS专用梯度能力检查不能对EDS新增probe或随机数消耗。

## 有意义的验证

当前迁移 CPU 套件与干净安装记录见 README。新代码必须在**修改后实际**运行对应测试，不能沿用前一commit的通过数量。普通CPU开发命令如下；它不是禁止API的安全边界：

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 \
  python -m pytest tests -q --disable-warnings -p no:cacheprovider
```

正式离线验收还应使用审阅过的socket/provider命令阻断harness，并设置独立缓存，避免导入时写共享环境。harness最终仓库入口待发布；测试需要服务时应显式拆分，不依赖开发者恰好已登录。不要为“跑过”而通过缺目录skip跳过核心验收。

统一接口实施前先从冻结 EDS 创建独立CPU参考fixture，随后做实际 `Main → Stage → contact handoff → RDT EDS → postprocess → adapter` 闭环差分：只mock模型/encoder、仿真adapter和在线回复，保留真实评分、重采样、reference、Stage与动作缓存。比较每个动作、RNG状态、父代fingerprint、调用次数、query时点和Stage转移；计时、文件路径可排除。仅在同一个新实现里对比两个getter不足以证明before/after一致。

还需覆盖 reward≥0.8接触交接、距离拒绝、grace到期、陈旧unguided reward抑制、guidance恢复保留reference、Stage/episode重置、合法零梯度与不可微但可评分reward。VLS新增评分只出现在明确路径并计数；确保EDS从未调用VLS专用能力probe。

自包含离线审计fixture应仅包含必要的真实短片段、原PNG/JSON/代码、hash及裁剪provenance，路径相对测试包，不依赖研究worktree或运行目录。若合成完成状态/compute receipt来测试完整性审计，要明确为测试 scaffolding，不能伪装成真实短回合成功。

## 运行、比较与发布

一次完整对照匹配任务、seed、资产、模型请求参数、Stage规则、最大环境步、初始化协议和执行horizon。不同方法产生不同轨迹后，Stage查询时刻/次数可以自然分化；匹配规则和上限，不通过回复回放制造相同轨迹。VLS20候选与EDS16候选的默认预算不同，报告实际成本。

有效失败与基础设施失败分开。最终报告至少记录commit/源码快照、完整任务/seed、环境/资产identity、resolved配置、每任务结果、在线捕获、真实机制计数及audit状态。缺证据或worker异常应标无效/未完成，不补成任务失败，不静默切换CPU或缓存回复。

EDS+QD要证明archive在实际父代和最终选择中生效；shadow observer本身不够。新描述符、网格、稀疏规则、跨chunk或跨任务archive均为独立科学改动。递归自我改进目前属于未来研究，不是已交付能力。

发布README前填写最终结果与证据链接、确认CLI命令实际可用、新clone测试不依赖维护者目录，并将所有仍未实现或未验证事项保留为pending。公开成绩不能超出可共享证据的范围。
