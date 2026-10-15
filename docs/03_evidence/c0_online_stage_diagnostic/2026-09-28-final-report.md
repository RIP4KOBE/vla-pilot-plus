# C0 在线 Codex Stage 排查最终报告

日期：2026-09-28。实验位置：`/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-gpu6-20260922T063626Z`，物理 GPU2，单 worker。范围仅为 C0 的在线 Stage 接入与诊断；RDT 权重、ED 参数、旧缓存、十任务顺序/种子、720 步及 QD 关闭条件保持不变。旧结果全部保留。

## 结论

**原始 Poe/Gemini C0 的 3/10 已在固定历史 Stage 回复下由历史及当前源码精确回放；本轮在线 Codex 条件没有恢复 3/10。** 经过格式、推理强度、缓存目标身份和 guidance 提示词筛选，选出的 E 条件在 GPU2 完成 10/10 有效任务，**成功 0/10**。十段视频、十条任务/种子元数据、`results.txt` 与计分一致，187/187 条 Stage 事件有完整回复且无最终查询错误；187/187 组原始提示词/PNG 也与事件指纹逐条匹配。第一次在线尝试因短时 Codex 连接故障于 task 0 第 40 步中止，列为无效基础设施尝试，绝不并入 0/10；扩大仅针对未完成回复的有限重试后，从新目录重跑取得上述完整结果。

因此，**不能把当前 Codex 在线 Stage 作为已恢复的 C0 统一基线，也不应据此开始新的 QD/ED 算法增益实验**。本轮排除了明显的图像顺序、PNG 字节、结构化解析和账号默认推理设置错误，确认 Codex 的 Stage 语义判断与历史 Poe 不同，且单独延长 stage 1 guidance 未改善成功率。它没有证明 Codex 模型原则上无法修好；严格复现原始在线供应方与模型则必须恢复 Poe/Gemini 接入。

## 可复现基础与本轮执行

历史在线 Poe/Gemini C0 为 3/10，成功 task 3、8、9。历史源码 + 在线 Codex `gpt-6-astra`/`low`/JSON 为 1/10（task 9），当前源码 + 同条件为 0/10；两者当时分别有 185/185、173/173 次成功 Stage 调用。历史源码及当前源码各自回放旧 127 条 Poe Stage 原文，都得到 3/10，127 条事件、十个首块粒子文件和十段视频与原实验完全一致。本轮再次在 GPU2 捕获历史回复回放的 127 个精确 Stage 输入，回放 3/10、事件及十段视频的哈希审计均通过。故当前代码、权重、仿真和基本 RDT+ED 路径在**固定旧 Stage 输入/输出**下可重现；这一结论不能外推成 Codex 在线协议已重现。

本轮 CPU 双图顺序哨兵 4/4 通过；真实输入按文本部件和 PNG 原字节保存，并经哈希校验。固定 24 个精确请求、每个重复 3 次的 A/B/C/D 筛选结果如下。与 Poe 决策一致率只是描述量，不是视觉真值或成功率。

| 条件 | 与旧 Stage 一致 | stage 1/off | 解释 |
| --- | ---: | ---: | --- |
| A：JSON、low、旧模板 | 45/72 | 38/72 | 当前在线 Codex 原协议 |
| B：三行自由文本、low | 45/72 | 36/72 | 与 A 的有效成对决策仅差 2/72，且为同一波动画面 |
| C：JSON、medium | 45/72 | 38/72 | 未见系统性变化 |
| D：JSON、high | 45/72 | 37/72 | 未见系统性变化；高推理设置确实被 CLI 使用 |
| E：澄清近距离/reward 不等于抓取，stage 1 未确认抓取时继续引导 | 33/72 | 0/72 | 有效改变 guidance，但过于全面；扩展 127/127 精确请求有效 |

缓存中的两行 Stage 描述把十个任务目标都写成 `alphabet soup can`，而任务指令与 keypoint 0 是实际物体。单变量 F 将两行描述修正为真实任务目标；在 62 个与 A 可配对的有效回复中只差 1 次，且是已知同图波动请求。Codex 原回复通常已经依据任务指令辨认了正确物体，因此该缓存错误真实存在，却不是本轮失败的充分解释。原缓存未在 GPU 在线 E 中改动，以维持单变量测试。

E 被选为 GPU2 闭环候选，是因为它在 task 9 的固定历史第 24 步画面，把原 Codex 的 stage 1/off 改为 stage 1/on：目标仍可见于桌面，继续引导有视觉依据。但它也把历史成功 task 3 的 stage 1/off 改成 on。离线成功任务请求对齐数和“像 Poe”程度都不能代替闭环测试。

第一次 E 在线尝试在 task 0 第 40 步收到连续五次没有完整回复的 `turn.failed`，保留 2 个已启动 episode、2 条 Stage 事件及 2/2 原始输入捕获；审计标记 `valid: false`。对同一失败请求的无 GPU 健康探测随后一次取得完整答复。恢复版只对**没有完整回复**的传输错误最多重试 12 次，退避从 2 秒起并封顶 30 秒；鉴权、权限、配额、完整但无效的回答不会重试。第二次 E 在线尝试在独立输出目录完成 10 个任务、耗时 5193.85 秒（1.44274 GPU 小时），审计 `valid: true`、**0/10**。187 条有效 Stage 事件实际用了 242 次 CLI 调用；13 个请求经历断线后恢复，单请求最多 8 次物理调用。连接故障的修复保证实验完成，不代表 Stage 语义已修复。第一次无效尝试上界 0.06706 GPU 小时；本轮两次在线尝试合计 12 个已启动 episode、1.50979 GPU 小时。用户已明确要求不再以旧预算作为停止条件；这些数字只用于溯源。

E 在线决策为 stage 1/on 115 次、stage 2/off 64 次、stage 0/off 8 次，没有 stage 1/off。其十任务结果全部失败；task 3 在第 40/48 步仍保持 stage 1/on，第 160 步才进入 stage 2，历史 Poe 成功轨迹在第 32 步为 stage 1/off、第 56 步为 stage 2/off。task 8 第 136 步被判 stage 0，环境仍失败。task 9 多次在 stage 1/on 与 stage 2/off 间切换，亦失败。E 比旧 Codex 当前源码的 173 条 Stage 查询更频繁（187 条），但这种计数变化不能单独证明因果。

## 故障机制与证据边界

1. **接入层没有发现导致旧 0/10 的确定性实现缺陷。** 合成双图哨兵通过，真实提示词/两张 PNG 的顺序及字节可审计；JSON 原文严格验证后送入旧 stage/guidance 解析器。旧在线 Codex 185/185 和 173/173 次 Stage 均完成，故本轮新出现的 `turn.failed` 是执行可靠性问题，而非那两批低成功率的解释。当前 CLI 直接使用 ChatGPT 登录，显式指定 `gpt-6-astra`/`low`；用户级默认 `gpt-6-sol`/`xhigh` 不参与 Stage。改成 medium/high 或旧文本格式，在固定画面上未改变主要决策。没有证据支持修改账号默认设置即可恢复 3/10。
2. **语义差异确定存在，但不能把 Poe 的每个答案当真值。** 旧固定 task 0 第 32 步，Poe 因“夹爪闭合”判 stage 2/off，Codex 判 stage 1/on；画面里目标仍在桌面，Poe 的理由本身可疑。另一个 task 9 画面，目标仍在桌面，旧 Poe 为 stage 1/on，原 Codex 为 stage 1/off。原提示词同时把 reward 接近暗示为可以关闭 guidance；该 reward 是本地轨迹代理，E 在线 task 8 判完成时查询前归一化 reward 约 0.93，环境仍失败。这说明高 reward 不是放置完成真值。
3. **Codex 的完成判定存在可定位的视觉/推理失误。** E 的 8 次 stage 0 中多次以“目标不在原位置、夹爪在篮筐上方”推断已经放入。保存的 task 0 第 328 步画面中汤罐仍在桌面；task 1 的 cream cheese 也可见于篮外；task 8 第 136 步篮筐明显为空，Codex 却宣称 chocolate pudding 已释放进去。task 3 的 BBQ sauce 在单帧中看似位于篮筐边缘，环境最终仍失败。由于旧 Poe 成功轨迹中也出现过提前 stage 0，且 stage 0/off 与 stage 2/off 都关闭 guidance，这些观察证明判断不可靠，却**不能单凭当前日志证明 stage 0 错误造成了所有任务失败**。没有在这一批在线事件中保存完整仿真物体位姿/接触真值，单帧视觉不能作为抓取稳定性的真值标签。
4. **闭环随机流会放大早期差异。** C0 逐 episode 的种子用于环境 reset，但原协议在进程启动后持续使用全局策略 RNG。Stage 决策一旦改变早期任务的动作和采样，后面任务即使任务/环境种子相同，初始粒子也可能不同。历史源码与当前源码 Codex 对照曾在完全相同的 task 2 第 408 步输入上给出不同 guidance；之后 task 3–9 已不再严格配对。因此旧 Poe 3/10、历史源码 Codex 1/10、当前源码 Codex 0/10 和 E 0/10 反映真实各自协议的得分，却不是逐任务相同初始策略随机状态下的纯模型因果效应。当前源码回放旧 Poe 回复的精确 3/10 已单独排除“当前代码根本无法成功”的说法。

## 后续决定

当前已执行的格式、推理强度、目标名称及 E guidance 修正均没有把在线 Codex C0 恢复到 3/10。**不能据此判定“Codex 模型天生无法做 Stage”，也不能称“必须换 Poe 才能让任何在线算法工作”。** 若目标是严格核对一个月前 Poe/Gemini 的在线 3/10，恢复原 Poe/Gemini 接入是必要条件；ChatGPT 登录的 Codex CLI 不是同一个模型/API。若目标是建立新的 Codex 在线 Stage 统一条件，下一步应把 target 的视觉定位/连续两帧状态与 stage 0 完成验证作为独立、可测试的机制，并在新协议中逐 episode 隔离策略 RNG，成对重跑旧模板 C0 与修订模板 C0。仿真真值只用于离线诊断标签，最终在线 Stage 不可偷用环境 success 信号。只有在新条件下 C0 稳定、完整重测后，才适合用它评价 RDT+ED+QD；冻结旧 Poe Stage 回复仅适合检查旧 C0 执行链，轨迹改变的 QD 候选不能通用地复用这 127 条回复。

证据入口：`artifacts/c0_online_stage_diagnostic_20260928/outputs/capture_replay/capture-audit.json`、`offline_probe/screening-summary.json`、`offline_prompt_probe/summary.json`、`offline_prompt_probe/extension-coverage.json`、`offline_probe/selection.json`、`outputs/online_E_guidance_persistence_json_low_replicate1/online-audit.json`（无效连接尝试）、`outputs/online_E_guidance_persistence_json_low_replicate1_attempt2/online-audit.json`（有效 0/10）、同目录 `capture-audit.json`（187/187）、原始 `eds_eval/stage_events.jsonl`、十段视频及冻结运行清单。CPU 相关检查 146 项通过；详细协议见 `experiments/iteration_001_execution_intent/c0-codex-online-stage-diagnostic-plan-20260928.md`、`online-e-candidate-20260928.md`。
