# 原始 π0.5 v44 + VLS steering

这是第五个方法 baseline，仅执行推理评测。权重、tokenizer 和归一化器与原始 v44 参考结果相同。它复用项目的 VLS 奖励生成、关键点跟踪、梯度引导、RBF 多样性及 FK 重采样；关闭 mode gate、自进化、示范采集、训练、模型检索和部署注册表。

入口为 `baseline/vls.py`，独立 API 实现在 `baseline/vls_provider.py`，网络重试和奖励代码适配分别位于 `baseline/vls_retry.py`、`baseline/vls_guidance.py`，无需改变四个训练方法的控制器。配置为 `baseline/experiments/env_position20_20260910/v44_vls.json`。本地和 hgpu1 均保留同一份 baseline 实现；实际执行读取 hgpu1 项目 `.env` 中已有的 `OPENAI_API_KEY`、`GOOGLE_API_KEY`，不保存密钥到输出中。

API 模型固定到 [VLS 官方代码 b6e87ed](https://github.com/Vision-Language-Steering/code/blob/b6e87edc217a2a7682caadba285677fc79eb6f81/configs/perception.yaml)：奖励函数生成用 **gpt-5.1**，阶段识别用 **gemini-3-flash-preview**。官方代码、提示词、MIT 许可证及 SHA256 保存在 `baseline/references/vls/`。阶段 API 使用服务器已有的 `google-genai` SDK 的 `generate_content`，保持官方提示词、两张图像的顺序和默认生成设置；奖励生成器直接使用保存的官方源码。

基准在自己的进程内、初始化 Main 之前替换 provider 工厂；不创建、唤醒或依赖任何 Codex 任务，不创建阶段规划队列。不修改主实验的 `main.py`、`core/`、全局配置或模型调用方式。初始化后验证实际 recognizer 类型；两个 API 的请求模型及响应模型分别记入 provider 调用日志。

## 配对及推理设置

- 范围：环境扰动 10 项、位置扰动 10 项；与本轮 baseline 相同的 40 条 `fixed_development_probe`。启动时逐条核对原始 v44 的 context，并校验模型与 tokenizer 文件摘要。最终封存分区不开放。
- 每次采样 40 个候选。主方法虽然保留 `main.sample_batch_size=20`，启用 mode gate 后实际使用 `mode_gate.sample_count=40`；这里匹配实际预算。
- 去噪 10 步、执行 horizon 10、128×128 双路策略图像、720 步仿真上限，其中 5 步初始化等待。基础引导强度 40、多样性强度 10、sigmoid/FK 等使用已冻结的主实验配置。与原生 Main 相同，适配器的任务级推荐引导强度可覆盖基础值（首个任务实际为 80），每个 chunk 记录实际值。
- 保留 `MCMC_steps=4` 配置以匹配来源；当前 π0.5 VLS 实现接收这个参数，但引导采样没有独立 MCMC 内循环。不能把配置值报告为实际运行了四轮 MCMC。
- 每回合最多 50 次 Gemini 阶段查询。GPT-5.1 使用官方配置的 temperature=1、max_completion_tokens=2000；Gemini 保留官方默认生成参数，没有另外指定 thinking level。API 请求超时上限 180 秒，不自动切换模型或任务。
- LIBERO 原生分割和主实验的 DINOv2 特征用于关键点检测，π0.5 权重和采样预算继续与本轮主实验匹配；这属于面向本 benchmark 的 VLS 迁移，不能声称完整复现官方所有感知设置（官方默认 DINOv3）。每个回合单独生成并保存奖励代码，不复用其他实验的学习结果或示范。
- 保存动作、逐动作 native success、引导 chunk 数、阶段查询次数、种子、初始状态及运行时间。VLM 输出有随机性，保存输出用于审计，不声称仅凭仿真随机种子即可复现所有 VLM 结果。

## 执行与恢复

在仓库根目录使用服务器 Python：

```bash
python -m baseline.vls plan --config baseline/experiments/env_position20_20260910/v44_vls.json
python -m baseline.vls evaluate --config baseline/experiments/env_position20_20260910/v44_vls.json --run-name v44_vls_official_dev_20260911 --gpu 0
```

GPU6 始终被禁止。控制器持有单 GPU baseline 锁，所有子进程继承同一物理 GPU UUID；每个回合使用新进程，回合间不保留控制状态。hgpu1 EGL 8 是独立的软件渲染设备编号，不是训练 GPU8。

输出在 `/shared/hengyil6/vls/baseline_runs/env_position20_20260910/v44_vls_official_dev_20260911/`。`status.json` 记录总进度，`episode_NNN/status.json` 记录当前阶段和动作步数；`episodes.json` 和 `summary.json` 仅包含有效完成的回合。显式 `--resume` 校验相同配置、来源代码和已完成 context 后继续，保留被中止的回合目录。目录中的 `stop.request` 在回合边界停止派发。

自 2026-09-11 网络修复起，Gemini 和 GPT 请求遇到连接中断、SSL 错误、超时、408/409/425/429 或 5xx 时，在当前查询内**无限次重试**，退避 2、4、8、16、32 秒，之后每次最多等待 60 秒；单次请求仍保留 180 秒超时。在网络恢复前不推进仿真、不更换模型或输入、不占用额外阶段查询额度。GPT 流式响应先完整缓冲，中断时丢弃不完整文本并重新请求，防止两次生成的代码拼接。Gemini 决策格式缺失时，也在同一次逻辑查询内重新请求，并单独标记为响应格式重试。认证/配置错误独立报错，不记为任务失败。

`episode_NNN/provider_status.json` 显示当前请求或重试等待状态；`stage_api_calls/call_NNN/attempts.jsonl`、`reward_api_calls/call_NNN/attempts.jsonl` 记录每次尝试、错误类型和退避时间。逻辑查询日志仍只记一条最终结果，不因重试虚增阶段次数。修复时保留前 5 个有效回合，第 6 个被中止的回合留档后以原 context 和种子重跑；代码/计划迁移摘要保存在独立恢复记录中。

2026-09-11 第 7 回合暴露了官方生成代码与项目加载器的兼容问题：函数内部的 `import torch` 被现有 AST 校验拒绝。现在仅删除无别名的冗余 `import torch`，使用加载器已提供的同名命名空间，并继续执行原 AST 校验；其他导入、未允许的调用及命名空间重绑定不会被放行。官方生成源码、首轮提示词、模型和生成参数均保留。

每个生成程序在发布给 Main 前，必须具有完整的阶段文件，并用当前场景的真实关键点数量在 CPU 上检查奖励输出与梯度。确定性测试输入覆盖 FK 的 `(B=1,T=9)` 及梯度引导的 `(B=1/40,T=10)`，不消耗仿真或策略 RNG。解析失败、缺失阶段、非法语法、越界关键点、非有限奖励、不可微的非零奖励以及生成长度截断，会在同一场景重新生成；后续提示词追加具体执行错误与加载器格式要求，首轮仍使用官方提示词。该反馈是 benchmark 的执行兼容适配，所有额外生成成本均留档。

2026-09-12 修正零奖励阶段的兼容检查：官方提示词明确要求放入篮子、caddy 后隔间等任务的第二阶段返回零，这类阶段不需要奖励梯度。原生加载器已将 Python 数字零转成张量，原生 π0.5 会跳过其奖励梯度并保留正常的 FK/多样性处理。现在接受有限、形状正确且全部为零的无梯度输出，保持生成函数原文，不添加虚构梯度或改变任务阶段；非零奖励仍必须对动作可微。已有梯度连接的输出仍检查梯度，即使其奖励值恰为零，也不放过 NaN/Inf 梯度。验证记录用 `reward_mode=zero_reward`、`gradient_finite=null` 区分未调用梯度计算的零奖励阶段。修复覆盖了第 21 回合的真实两阶段输出及 11 个关键点；前 20 个有效结果保留，第 21 个未执行动作的中断回合留档后使用原 context 和种子恢复。

`guidance_attempts/attempt_NNN/` 保存每次原始输出、原始/适配后的函数及验证记录，`guidance_status.json` 显示生成、重新生成或有效状态。只有全部阶段验证通过的程序才发布到 `vlm_agent/` 并开始动作。此次恢复保留前 6 个有效回合，第 7 个中断回合另行留档后按原 context 重跑，不把无效尝试计为失败成绩。

先前 `v44_vls_dev_20260911/` 使用 Codex/GPT-4o 的尝试已退役，所有回合从头开始，旧结果不并入本版本统计。新配置 v2 也拒绝恢复旧 v1 配置。

VLS 不写入主实验注册表、tickets、模型或评估账本，也不随主实验的部署更新切换权重。该对照不是“完整主方法只关闭自进化”的消融。
