# C0 在线 Codex Stage 排查：首阶段执行记录

日期：2026-09-28。此记录只涵盖当前预算允许的无 GPU 工作；未启动新的 GPU2 episode，未产生新的 C0 成功率。

## 现有证据和初步判断

- 历史 Poe 回复回放为 3/10（任务 3、8、9）；历史源码在线 Codex 为 1/10（任务 9）；当前源码在线 Codex 为 0/10。两组 Codex Stage 请求分别 185/185、173/173 成功，因此目前没有证据把主要差异归因于 API 鉴权、调用失败或 JSON 解析失败。静态审计见 `static-audit-20260928.json`。
- Codex Stage 适配器使用显式 `gpt-6-astra`、`low`、`json_schema_v1`，经 ChatGPT 登录的 CLI 0.156.1；该 CLI 版本与原 Codex C0 清单相同。适配器把穿插在图片之间的文本合并为 stdin 的文字段，随后按初始图、当前图的顺序附加两张 PNG。这可能改变多模态对齐，但四次合成红蓝图正反顺序调用均正确辨认当前图，未发现明显的图片丢失或顺序颠倒。合成试验不能证明复杂机器人画面的视觉判断正确。
- task 0 第 32 步：历史回复为 stage 2、guidance off；Codex 两次在线运行均给 stage 1、guidance on。这是可疑的控制决策差异，并非已证实的实现错误。task 2 第 408 步在两组 Codex 在线日志中具有相同提示词和两图哈希，guidance 却相反，说明同输入决策存在波动。日志只保存哈希，无法用旧运行的原始 PNG 重放这个特定请求。
- 十任务比较的随机数协议也是干扰因素：历史回放与历史源码 Codex 仅任务 0 的首块粒子哈希相同。在线分叉后不能把 3/10 与 1/10 的每个任务直接解释为单条 Stage 回复的因果效果。
- 原历史 Stage 包含 20 条解析回退至 stage 1、guidance on 的回复；Codex 两组在线回复均成功解析。两种输出协议产生的控制分布不同，应在同一批精确画面上单变量比较。

## 已实施的诊断工具与验证

- `scripts/c0_codex_stage_sentinel.py`：使用原在线设置做两图附加顺序哨兵；4/4 通过，记录于 `sentinel-20260928.json`。
- `core/stage_capture_trace_replay.py`：新建只读历史回复回放后端，保存每次请求的原始部件顺序、两张 PNG 字节、Codex 文字串和上下文；不调用模型、不改变回复。`core/gemini_grounder.py` 注册该后端，`main.py` 保持启动失败时不回退到在线模型。
- `scripts/c0_stage_input_capture_preflight.py`、`scripts/c0_stage_input_capture_audit.py` 和 `scripts/c0_stage_input_capture_run.py`：冻结原 C0 十任务采集命令；运行后核对 127 条 Stage 事件、十段视频、首块粒子及 127 组输入。启动器检查授权文件、预算、物理 GPU2 空闲和单 worker 锁；即使异常退出，也按已创建的 episode 目录和运行时长保存预算计费。无授权试运行被门禁拒绝，未派遣 GPU 工作。
- 相关 CPU 测试 261 项通过，Python 编译和 Hydra 配置预检通过。冻结命令见 `capture-preflight-v2-20260928.json`，SHA-256 为 `d6c2eea1012c782fbd1bdde2564d92c6937d6430c8433460374fddfe2edd1034`。原在线 Codex 清单 `artifacts/c0_codex_repro_20260925/manifest.json` 中 CLI 版本同为 0.156.1；当前模板 SHA-256 仍为 `758d71a441496074410428b005a068a18b6d92273b9278c1181334cf9e67005b`。

## 停点与后续判定

本 study 已有效使用 158/258 个 episode、15.020869809/48 GPU 小时；未使用的 100 个 episode 和 24 GPU 小时是验证/正式阶段保护额度，因此可供当前诊断的 episode 为零。精确真实画面采集必须运行十个仿真 episode，无法从现存视频恢复逐字节相同的 PNG。预算调拨提议为 `experiments/iteration_001_execution_intent/c0-codex-stage-budget-amendment-proposal-20260928.md`，请求总次数上限 258→298，48 GPU 小时及保护额度不变；获批后立即只派遣首个最多十次的采集回合。未获批前不运行 GPU2 任务。

采集及审计通过后，才对最多 24 个精确请求做 Codex JSON/旧文本格式、推理强度和经证实的协议缺陷单变量离线比较；最后冻结一个候选条件进行 GPU2 闭环测试。当前结论只是不支持“明显鉴权/解析失败”解释；尚不能断言 Codex 模型天然无效，也不能断言修复后一定恢复 3/10。
