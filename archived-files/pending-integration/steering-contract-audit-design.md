# Steering 合同离线补审草案（2026-10-13 修订）

所有实现、测试与报告仅位于 `/tmp`。没有改动运行中的 repository、runtime、config、tests 或实验产物；没有启动 GPU、模拟器或 API。检查不导入仓库/历史 runner，不执行返回的奖励代码，不加载模型。

## 交付与调用

- `/tmp/audit_steering_contract_draft.py`：`audit_run(run_dir, task=0, model="gpt-6-astra", effort="low") -> dict` 为可共用只读接口；薄 CLI 仅写 `/tmp` 报告。失败检查或证据读取/结构错误返回非零退出码，完成前缺证据为 pending，科学失败本身不算合同失败。
- `/tmp/steering_transport_audit.py`：reviewer 提供的无 I/O 纯函数 `audit_transport(response, policy)`。
- `/tmp/test_steering_contract_offline.py`：真实 task0 证据的 CPU 内存变换测试；不修改原文件。
- `/tmp/test_steering_transport_audit.py`：合法 reasoning/lifecycle/recovery/retry 和非法 transport 摘要的纯 CPU 正反例。
- `/tmp/steering-audit-review-mutations.py`：reviewer 的独立绑定/形状负例与合法 reasoning/lifecycle/warning 正例。

```bash
/home/hynx/miniconda3/envs/vla-pilot/bin/python /tmp/audit_steering_contract_draft.py /home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/runs/eds-migration-20261013 --task 0 --report /tmp/steering-task0-contract-v3.json
/home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -q /tmp/test_steering_contract_offline.py /tmp/test_steering_transport_audit.py
```

主模块仅需 Python stdlib、PyYAML；图像校验使用 Pillow/OpenCV/NumPy CPU 操作。依赖缺失会 FAIL，不会算通过。CLI 的退出码 0 表示没有 FAIL；是否任务已完整通过还必须读取 `task_contract_valid`（pending 的任务为 false）。完整 cohort 合并逻辑仍属于主 audit，草案始终输出 `cohort_valid: null`。

## 已补齐的必要合同

1. **实际请求固定 provider/model/effort**：逐个 Stage identity、Stage observation、格式重试及本任务 reward capture 核对 `codex_cli` / `chatgpt` / `gpt-6-astra` / `low`。请求 policy、transport、completion 配置一致；public-policy SHA、固定 CLI flags、禁工具/网络/MCP/skills 配置检查；retry count/backoff/timeout/event policy 与 resolved role config 一致。没有把 YAML 配置当作全部实际请求证据。
2. **精确允许冻结 transport policy**：合法 reasoning 和消息 started/updated/completed lifecycle、精确 model metadata warning、v6 分阶段 reconnect/fallback、未完成的可重试传输失败可通过。错误 item/event 必须与允许 notice 一一对应；未知 error、语义重试、已完成后再重试、terminal auth/quota 错误均拒绝。不能用单一 `item_types == ['agent_message']` 误拒合法恢复。
3. **任务与 seed 锚定**：manifest 任务/seed 序列与 resolved config 相同；episode metadata、全部 Stage event/capture、compute 的 episode/task/seed 一致。任务 instruction 来自环境/资产 manifest 哈希绑定的 LIBERO task map，AST 只读取 literal，不执行文件。action 的 episode/task 也绑定，action 未保存 seed 的边界明确记录。
4. **capture/reply/observation 唯一绑定与计数守恒**：每个 validation attempt 的 capture index 唯一、不可重复使用；raw reply/completion、最后事件 reply/transport/parsed observation 绑定同一个 capture。独立做 JSON schema/enum/重复键检查，格式重试 payload 不变，first-valid-answer/attempt 顺序一致。identity+observation capture counter 与 query、episode Stage/reward/provider totals 对齐；包含 latency、failed/usage-complete/token counters，None 保留未知，HTTP counters 保持不可观测。
5. **identity 初始证据**：每任务只有首个 step0 query 产生一次 identity；正文由 task instruction/映射重建，identity memory 精确等于 capture reply；identity capture 先于观察；初始图像素等于本任务 reward 准备图。
6. **每任务 fresh reward**：关闭缓存；本任务目录只有一次生成请求；metadata query index、prompt/task/关键点映射/float32位置、query image、output raw 均绑定 capture；保存的 guidance 函数 AST 等于 raw response AST。64 个保存的 reward contract probes 校验计数、数值与 tolerance 内部一致性，不执行生成代码。不能要求跨任务 code hash 不同。
7. **无动作 override**：7 维 raw/executed command 必须 finite 且逐值相同，override=false，passthrough reason，进入 adapter 前 gripper 已为 ±1；step 唯一连续，与 adapter step exit 对齐。运行中的最后一个 safety row 可先于 adapter exit；已结束任务不能缺步。
8. **marker 投影/像素链路**：目标 indices 绑定任务映射；世界点/内外参/pixel 严格形状与有限数值；PNG/RGB hash、投影深度、二维坐标/status/分辨率一致；在内存按冻结 marker 规则重建，像素 hash 等于实际发送图像。合法 offscreen/behind-camera 不算 infra 失败。
9. **完成与缺证据**：worker 真正 running 才允许在途 pending；已有 compute/final video/后续 episode 表示本任务已结束。结束后缺 contract、capture、compute 或重复 compute 必须 FAIL；worker 整体结束后任何未完成 capture bundle 也 FAIL。运行中无法归属的后续 capture 只记未归属事实，不误伤已完成任务。

## 实证与验证

`/tmp/steering-task0-contract-v3.json`：1722 PASS、0 FAIL、0 pending；39 个 Stage captures（1 identity +38 observation）、1 fresh reward；720 个 action 与720 个 adapter exit；1 个 completed episode compute。该任务科学结果是失败，合同可有效通过，不能把成功率低归成 infra 问题。

`/tmp/steering-task1-contract-prefix.json`：读取时1114 PASS、1 compute pending；25 Stage captures、1 reward、432 actions/432 exits。仅为运行中的前缀，不能替代完成验收。

第一轮组合测试43项全部通过（18 主审计 +25 transport，19.69秒）；随后仅提取可共用函数并添加缺 metadata 的 fail-report 测试，最终结果记录在 `/tmp/steering-offline-audit-validation.json`。Reviewer 独立确认合法 reasoning/lifecycle/warning 各1722 PASS；错 seed、identity、attempt reply、observation、identity capture、prepare index、单坐标 marker 等负例被拒绝。

## 明确证据边界

- `response_model` 是冻结 transport 配置记录，不是独立的服务端模型 attestation。
- 原始 transport event stream/notice 全文未保存，无法独立完整重放 parser；helper 检查保存的摘要、索引、分类与冻结 runtime 成功校验声明。这一限制不能靠摘要 hash 消除。
- reward probe 报告是冻结 runtime 执行后的记录；此离线工具检查内部一致性，不再次执行生成代码。
- 逐动作证据位于 postprocessor/guard 到 adapter 之间，seed 从 episode 证据绑定，未保存 simulator 入口独立遥测；常规 OSC 控制缩放/裁剪不等同额外 arm/gripper override。
- marker 证明记录的几何→绘图→请求图像链条一致，不独立证明 keypoint 的语义来源正确。
- 审计运行仍需 manifest 指向、hash 匹配的本地 LIBERO task map；不依赖 LIBERO 导入或仿真。
- 不迁移旧 research runner/deep audit 的目录、gallery、动态 import、controller 名单或研究状态。模式特有 compute/QD 审计继续由主 audit 承担；共用合同只覆盖 provider、新生成、Stage证据与控制链。
