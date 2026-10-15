# 2026-09-29 Poe 在线 C0 重测

用户授权：保留历史 reward 函数缓存，恢复 Poe 在线 Stage，GPU2 完整重跑 C0 十任务；确认基线后才继续 QD/ED。新凭据已通过当前 Poe 模型的实际生成请求验证。密钥只存在本机权限 0600 的独立文件中，不进入命令、配置快照、源码、报告或实验日志。

## 原模型可用性与用户修订

历史 `gemini-2.5-flash` 的四次生成调用（含历史双图请求、最小文本以及名称大小写检查）均返回 HTTP 500。模型目录不包含原模型；Poe 原模型页面标为 `Gemini-2.5-Flash_DEPRECATED`、`PRIVATE`。目录接口本身无需鉴权，其 HTTP 200 不能证明凭据有效；另用当前 `gemini-3-flash` 实际生成 `OK`，确认新凭据可用。未更改服务器代理；现有代理可访问 Poe，直连不可达。

用户随后明确选择“改用 Gemini-3-Flash 重测新 C0”。因此本轮是 **新的 Poe 在线 Stage 模型条件**，不能称为原 Gemini-2.5 模型的严格复现。官方依据：[原模型页面](https://poe.com/Gemini-2.5-Flash)、[模型目录说明](https://creator.poe.com/api-reference/listModels)、[Poe 接口说明](https://creator.poe.com/docs/external-applications/openai-compatible-api)。本地请求结果位于 `artifacts/c0_poe_online_20260929/`。

## 冻结设置

- 当前源码；原有 worktree；物理 GPU2；单 worker；独立本研究锁，不干预其他 GPU。
- `RDT-1B-LIBERO-Object` EMA；原文本/视觉编码器；LIBERO object-swap 十任务 0–9；每任务最多 720 步。
- 种子 `[44,235,43,546,6,621,197,87,151,548]`，主 seed 0；保留历史跨 episode 连续策略 RNG，不启用新的逐 episode RNG 协议。
- ED population 16、10 轮、非 CEM、temperature 0.1、renoise 3→1、absolute EEF RBF；历史 64 项 ED 设置逐项核对。QD archive 关闭。
- 历史六个缓存文件逐项 SHA 校验；reward 函数代码复用，数值在当前状态/轨迹上本地重新计算；不生成新 reward。
- 在线 Stage：Poe `gemini-3-flash`，原 `stage_template.txt`、原双图顺序、原文本解析器、max_tokens 256、temperature 0；查询触发和 50 次上限保持原样。Grounding 关闭。
- 保留原解析失败时 stage 1/guidance on 的处理。完整但无法解析的回复单列报告，不针对语义或任务失败重抽回复。无完整回复的连接故障与合法任务失败分别记录。
- API SDK 默认重试保持不变。捕获器仅保存送入原调用的图片/文本和原始返回值；不改请求参数及决策。SDK 默认超时不同于 Codex 的 timeout 配置，不能混用两者解释。

## 执行和判据

1. 原历史双图请求对新模型进行一次连接/格式探测，不能把探测结果算作机器人任务成功；已通过。
2. 完成 CPU 捕获器等价性检查和 Hydra 配置核对，冻结源码、命令、缓存和授权哈希。
3. 使用 `scripts/c0_poe_online_retest.py run` 在 GPU2 运行全部十个任务。记录每次请求输入、原始回复、事件、种子、视频、最终环境 success。既有结果不覆盖。
4. 十任务完成后审计：顺序及种子正确、十段视频、最终结果一致、在线请求有回复、输入捕获与事件匹配、缓存及源码未变化。完整解析回退单独统计。
5. 报告成功率和任务明细，与旧 Poe 3/10、Codex 条件结果分开对照。≥3/10 只是达到历史观测水平的初步门槛，不能证明两个在线模型统计等价或轨迹完全相同；低于门槛不得宣称基线恢复。后续 QD/ED 必须继续使用当前观测生成 Stage，不得复用旧轨迹的决策序列。

正常任务失败不重试；连接失败保留无效记录并排查。九小时进程看门狗仅用于挂起保护；旧预算不构成本次任务停止理由，仍记录实际 episode 数与 GPU 时间。验证/正式阶段保护额度及其他研究状态不改动。

预估正式十任务 30–90 分钟，取决于 Stage 延迟与请求数。正式进程开始后持续在会话报告进度。完整 C0 审计前不启动 QD/ED 候选。
