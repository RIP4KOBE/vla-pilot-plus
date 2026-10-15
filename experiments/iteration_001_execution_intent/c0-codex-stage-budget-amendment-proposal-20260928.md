# GPU2 在线 Codex Stage 排查：预算增量与首个采集回合（待批准）

2026-09-28。科学方案见 `c0-codex-online-stage-diagnostic-plan-20260928.md`，用户已批准先按现有预算实施并在不足时报告。本文件只提出不足部分的预算变更；在获得单独确认并更新账本之前，**不得派遣新 GPU episode**。

## 已完成的无 GPU 工作

- 当前代码/历史结果的静态审计已保存于 `docs/03_evidence/c0_online_stage_diagnostic/static-audit-20260928.json`：历史回复回放 3/10，历史源码在线 Codex 1/10，当前源码在线 Codex 0/10；在线 Codex 185/185 和 173/173 次 Stage 请求成功。task 2 第 408 步两组 Codex 请求的提示词及两张图片 SHA 完全相同，guidance 却一 ON 一 OFF。
- 旧 Stage/解析测试 160 项通过；新增精确请求采集后，相关 CPU 测试 226 项通过。双图红蓝哨兵使用实验同款 `gpt-6-astra`/`low`/JSON/ChatGPT CLI，正反顺序共 4 次，4/4 读出正确“当前图”。证据在 `docs/03_evidence/c0_online_stage_diagnostic/sentinel-20260928.json`。
- 未发现能直接解释 1/10 的鉴权、明显图像顺序颠倒或解析失败。原在线日志只保存 Stage 输入 PNG 的 SHA，不保存原 PNG 字节，视频解码也无法恢复逐字节相同的请求。所以严格的同图模型/格式/推理强度比较，需要先采集真实请求。
- 新增独立的 `trace_replay_capture` 后端，只在历史回复回放时保存原始多模态部件顺序、两张原 PNG、Codex 视角的文本序列化和上下文。它不调用 Poe 或 Codex，不更改历史回复或算法。Hydra 配置构造、Python 编译与 CPU 回放单元检查通过。

首个 GPU2 采集回合的冻结预检：`docs/03_evidence/c0_online_stage_diagnostic/capture-preflight-v2-20260928.json`，SHA-256 `d6c2eea1012c782fbd1bdde2564d92c6937d6430c8433460374fddfe2edd1034`。其中列明完整运行命令、源码/缓存/旧 trace 哈希、任务种子及输出路径。启动器为 `scripts/c0_stage_input_capture_run.py`，会在新预算与用户授权文件匹配、GPU2 空闲、单 worker 锁可获得后才启动。

## 为什么当前额度不足

本 GPU2 study 有效已运行 **158/258** 个 episode、**15.020869809/48 GPU 小时**；其余 **100 个 episode、24 GPU 小时**保留给验证和正式评估。因此开发/诊断可直接使用的 episode 为 **0**。无 GPU 的代码检查和已完成的四次 Codex CLI 哨兵未占用 episode；下一步十任务精确输入采集必须运行仿真，不能从受保护额度自行借用。

## 请求的单次预算调整

| 项目 | 现状 | 提议 |
| --- | ---: | ---: |
| GPU2 study 总 episode 上限 | 258 | **298（+40）** |
| GPU 小时总上限 | 48 | **48，不变** |
| 验证/正式保护 | 100 次、24 小时 | **不变** |
| 本轮 Stage 诊断硬上限 | 无可用次数 | **至多 40 次、6 GPU 小时** |
| 当前立即可派遣 | 0 | **仅首个采集回合最多 10 次** |

新增的 40 次严格分阶段：第一步最多 10 次历史 C0 回复回放以采集 127 个 Stage 输入，使用物理 GPU2、EGL1、一个 worker、原十任务/种子/缓存/720 步/RDT+ED 配置，QD 关闭；墙钟 GPU 上界 1 小时，历史同类回放约 0.271 小时。它必须保持 127/127 Stage 事件、10/10 首块粒子和 10/10 完整视频 SHA 与历史原实验相同，且 127 个请求全部保存并通过哈希审计，否则立即停止，不启动后续在线条件。第二步最多 450 次无 GPU 的离线 Codex CLI 模型调用，按科学方案逐项比较协议/推理强度/提示词。第三步仅一个离线选出的修订条件及必要的单缺陷修复，最多 30 个在线 C0 episode；先十任务，达到 3/10 门槛才独立重复。未用额度不得自动转作 QD 或正式评估。

原 C0、在线 Codex、历史回放、N1AB 的结果与账本均不改写。新结果另存于当前 `.worktrees/exp` 下的本 study artifact root。运行时对 Stage 服务错误、GPU 故障、预算/超时或事件分叉保留无效证据并停止，不把基础设施错误记作科学失败。每个阶段结束后核算本 study 的实际 episode 与 GPU 小时，不触碰 GPU3 study 或其状态。

若批准，需以批准文本写入 `artifacts/c0_online_stage_diagnostic_20260928/authorization.json`，将本 study 的 `research-state.yaml` 上限调整为 298，同时保持受保护额度，然后运行冻结的首个采集回合。授权文件和账本必须引用本提议与冻结预检的哈希；新增计划或代码版本应另冻，不能改写本版。
