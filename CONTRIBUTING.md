# 贡献说明

本仓库正在将 RDT 的 VLS、EDS 和 QD 扩展整理为公共实现。当前新入口只开放 `eds`；`vls` 和 `eds_qd` 的入口接入以 EDS 十任务验收完成为前置条件。请先阅读 [README](README.md) 与 [整合状态](docs/steering/integration-status.md)，确认待修改的是共享能力、某个方法，还是评测工具。

## 变更边界

- 保留 `vls`、`eds`、`eds_qd` 三种公共方法的明确语义。增加指标观察器不等于启用 QD archive；更换 Stage 控制器也不是仅调整日志。
- 算法、provider、提示词、关键点、动作转换、初始化、Stage/reference 和环境资产都可能改变结果。PR 必须列出实际变化的部分。
- 尽量把迁移、重构和算法实验分开提交。若同时改变，应说明无法拆分的原因，并提供对应验证。
- 不删除已有失败记录或覆盖冻结配置。新方法、新 seed、修复后的重跑均使用独立输出目录和运行标识。
- 不把个人模型缓存、凭据、登录状态、`.env` 或其他研究的队列/资源状态带入公共实现。

## 安装与离线开发

使用 [environment-steering.yml](environment-steering.yml)、[requirements-steering.txt](requirements-steering.txt) 和 [资产准备脚本](scripts/prepare_steering_assets.py)，避免把系统全局包或其他实验目录作为隐式依赖。新环境配方仍待干净 clone 验收，不要把本机可导入写成“干净 clone 可复现”，也不要原地升级正在执行 cohort 的共享环境。

`configs/local.yaml` 只包含机器路径与 GPU/EGL 编号，模板为 [local.example.yaml](configs/local.example.yaml)。配置解析可用 `scripts/run_steering.py --method eds --local-config configs/local.yaml --output-dir <新目录> --print-config`；它不使用 GPU 或调用模型。资产文件校验使用 `prepare_steering_assets.py verify-libero` 与 `verify-rng`。需要真实模型/GPU 时，显式使用 `check_steering.py` 的 `--api` / `--gpu`，并保存独立预检目录。

优先完成不需要模型、GPU 或在线调用的检查：配置解析、方法路由、输入输出形状、动作槽位、reward 合同、Stage 状态机、fixture/hash 和日志合同。针对会改变行为的代码，添加能够检出真实错误的测试；纯文字或低风险可逆调整无需编写镜像测试。

当前离线回归已有 1,118 项通过，含 26 项新增 runner 检查，真实日志位置与范围由 [整合状态](docs/steering/integration-status.md) 维护。执行 GPU smoke 或在线 cohort 前，应明确使用的设备、输出位置和运行范围；CUDA 运算与 EGL 渲染分别成功，不足以证明二者使用同一块 GPU。普通单元测试、模块导入和资产检查不得隐式触发完整评测或模型请求。

当前离线回归使用 `CUDA_VISIBLE_DEVICES='' python -m pytest tests -q --disable-warnings`。提交新入口或算法修改后，按改动范围运行对应检查，并记录所用 Python 环境、实际数量与失败信息；不要只复述上一次的通过数量。

## 配置冻结与比较

正式 cohort 开始前，保存解析后的配置，并记录：

1. 公共方法、启用机制、provider/model、提示词和 Stage 策略。
2. 源码版本及工作区差异，相关源文件哈希。
3. suite、任务顺序、每任务 seed、init state、步数上限和终止口径。
4. policy/encoder/DINO/仿真资产版本与校验值，以及环境与 CLI 版本。
5. 初始化协议；若使用 RNG fixture，记录 manifest 与每个状态文件哈希。
6. 输出路径、日志及审计策略。

运行期间不得继续修改会影响执行的源码或配置。确需修复时终止该版本的结论，保留已产生的原始记录，另开新运行。一个完整 cohort 必须来自同一冻结设置；不能把重复尝试中的成功拼成一个结果。

比较时保持 benchmark、策略、初始化、任务/seed、动作预算与 provider 条件一致。标准 Object 与 ObjectSwap OOD、PI05 与 RDT、缓存 Stage 与在线 Stage、普通 seed 与历史 RNG fixture 都应分别报告。改变其中任何一项时，明确其影响，避免把结果归因于单一算法开关。

## 结果与审计

环境 success、Stage 宣告完成、代理 reward 和局部动作效果分别记录。回合数、完整性、准备错误、运行异常、模型调用失败与保留的失败都必须可查。

历史结果可支持迁移设计，但不能作为新代码实测成绩。离线测试支持实现检查；短 smoke 支持运行链路检查；只有完整在线 cohort 才支持对应范围的在线成功率声明。固定十任务已经参与开发时，要披露该条件，不能称作独立泛化验证。

对机制改进的结论，提供触发前后的输入、状态变化与动作证据，并保留反例。一次恢复触发不等于任务成功，一次环境成功也不保证放置长期稳定或所有 Stage 语义正确。

## PR 内容

PR 描述应先说明具体问题和修改后的行为，然后写出：

- 涉及的方法、配置与资产；新增或变化的默认值。
- 已运行的验证命令和结果，以及尚未运行的检查。
- 是否存在在线结果；如果存在，给出完整输出和冻结配置位置。
- 与基线的可比较条件、未解决限制和迁移影响。

审阅者应能在不读取私人缓存或历史工作区的情况下理解修改。引用仓库内文件时使用相对链接。依赖变更同时更新环境声明、资产清单和安装说明；新 checkpoint 或 third-party 资产必须保留来源、许可证和校验记录。

## 许可证与第三方内容

保持 [LICENSE](LICENSE) 中的现有 MIT 许可与版权声明。修改第三方文件时保留其许可证和来源；不要假设仓库许可证覆盖权重、数据或外部服务。第三方大文件是否保留应由运行依赖、可获取性和许可证决定，不能仅按体积删除。
