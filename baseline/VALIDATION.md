# 验证记录（2026-09-07）

实现位于本地与 hgpu1 的 `vla-pilot-plus/baseline/`。本次验证没有运行正式的 40 任务训练或成功率评估。

## 已通过

| 检查 | 结果 |
|---|---|
| 本地 Python 语法、CLI help、四份配置 | 通过；四者均指向同一 v44 |
| hgpu1 CPU 测试 | **16 passed in 2.28s** |
| 现有合成 LeRobot 数据集读取 | 通过；输入两路图像、8D state，动作 `[1,50,7]`、padding `[1,50]` |
| v44 原始 processor / postprocessor | 通过；保留原始归一化统计 |
| 真实 v44 与缓存 prefix sampler | 相同输入、相同 noise 下最大绝对误差 **0.0** |
| latent 文件保存与读取 | 相同 noise 下采样一致 |
| CLARE | 18 个 action-expert FFN 的 adapter/AE 训练，重新构造后恢复预测一致 |
| MLR-IFA | flow + IFA 反向传播、FP32 权重更新和恢复；检查的 query 矩阵有 2,097,128 个元素更新 |
| Continual VLA RL | 10 个随机去噪转移、GRPO 梯度和 LoRA 恢复 |
| RL²-VLA | QAM 的 TD/flow/adjoint 梯度、LSTM 更新、模块恢复和 2 候选组合采样 |
| LIBERO-PRO | 真实 v44 在 `libero_spatial_object` 执行 10 步，suite/task/variant/init-state 与 protocol 一致 |

原始机器可读结果：[validation/v44_smoke.json](validation/v44_smoke.json)。

服务器完整运行目录：

```text
/shared/hengyil6/vls/baseline_runs/integration_v44_final_20260907_c/
```

`status.json` 为 `complete`，`smoke.json` 为 `passed: true`。验证使用物理 **GPU 7**，设备 UUID 为 `GPU-e6f54bec-13b1-3c6a-a1d7-9d3cbf4c6661`。本次小批量检查的 PyTorch 峰值已分配显存为 **14,891 MiB**，不包含同卡其他进程；这不是默认 batch size 或完整训练的显存保证。

权重 SHA-256：

```text
877b3ec1130548b69af7f8aeef3ec9d3fc7738040f0b9beb490857ec970997ae
```

CPU 数据读取使用已有的合成 `self_improve/preflight/training_smoke/dataset-v1`，仅作接口检查；没有用它训练正式 baseline，也没有读取生产 replay 的标签作为训练数据。

## 验证边界

Smoke 使用合成动作目标、缩小的辅助网络和训练步数。它验证真实 v44 上的执行、梯度和序列化接口，不代表方法性能、收敛结果或论文的原样复现。此次环境检查只覆盖一个 PRO task cell，未穷举全部 40 个 cell。正式训练所需的新示范或 RL² 离线数据，需要通过 README 中的数据契约提供/采集。

本地完成源码与入口检查；模型、processor、数据读取和环境运行验证在 hgpu1 的已有 Python 环境中执行，未在本地下载 v44 或安装新的训练依赖。

## Replay 隔离

未修改现有训练、replay、配置、checkpoint 或 protocol 文件，未更新共享依赖，未重启或向 replay 发送信号。验证结束后，原 **PID 92507** 仍运行 `replay-new-policy ... --device cuda:6`，GPU 6 上保留其进程；baseline 的 GPU 验证进程已经退出。

允许选择已有其他作业、但剩余显存足够的 GPU；启动器以 UUID 绑定设备，默认保护 GPU 6，实验输出独立保存。修复过的渲染兼容问题仅涉及 `baseline/environment.py`，由它正确调用项目已有的 EGL 补丁。

## 2026-09-08：主实验对齐与实验启动

本节为后续验证，以上 2026-09-07 的历史结果保持原样。

- CPU 检查：**22 passed in 3.75s**，新增有效 batch 32 梯度等价、主实验 scheduler、任务计划双随机种子、环境检查步数、正式示范验收来源、PRO 扰动语言等检查。
- 真实 v44：microbatch 4，CLARE/MLR 使用 8 次梯度累积；原始 sampler 最大误差 0.0，四方法的局部梯度和参数恢复检查通过。
- 真实 PRO 环境：保持配置的 720 步 horizon 和 5 步等待，独立短检查执行 10 个策略动作。检查仍使用合成目标及缩小的部分辅助模块，不代表正式方法成绩或收敛。
- 本次 GPU 检查峰值已分配显存 **15,014.5 MiB**；这是该检查的测量值，不是完整训练的显存上界。
- 单独复核主实验首个语言扰动 context：初始状态 21，环境 seed 586631865，policy seed 7452789587121265593；实际传入策略的文本等于已有 PRO BDDL 的扰动文本，原始文件未改写。

原始记录：[batch 32 检查](validation/aligned_batch32_20260908.json)、[PRO 语言检查](validation/pro_language_20260908.json)。运行设置和当前阶段见 [2026-09-08 实验说明](experiments/main_aligned_20260908/README.md) 与其 `launch_manifest.json`。

这轮已显式启动训练/采集流水线。CLARE 与 MLR-IFA 在正式示范就绪前仅等待，不计为已经训练；RL² 的收集阶段也不计为已经优化出模型。当时有效运行使用名称后缀 `_b`；早期 `_a` 启动的输出已标记无效并保留审计记录。后续恢复版本见下节。

## 2026-09-08：完整回合超时修复

RL² 采集和原始 v44 参考运行在失败回合触发 `executing action in terminated episode`。LIBERO 覆盖底层 `done` 后遗漏了 Robosuite 的 horizon 终止信号。修复限于 baseline：每个实际动作后读取该模拟器实例的终止状态，正确记录超时并结束回合，保持 horizon 720 与 reset 等待 5 步。

- hgpu1 CPU 测试：**26 passed in 3.39s**；新增超时、成功、最后一个不满 chunk 的 terminal/discount，以及采集/零更新 GRPO 数据继续的校验。
- 完整真实模拟器检查：CPU、合成零动作策略，实际执行 **715 个 policy actions + 5 个等待动作 = 720 个 simulator steps**，正常记录 `simulator_horizon`；最后一个 chunk 为 5 步，terminal 为 true，bootstrap discount 为 0。未依赖 v44 恰好提前成功来通过检查。
- 真实续跑数据检查：RL² 的 21 个文件内容及任务/初始状态/种子/角色符合 1350 条完整计划的前缀；Continual VLA RL 的 3 个完整零更新 group 可复用，旧 7 条部分组记录保留，7412 个既有环境动作全部计入累计成本。

原始检查记录：[完整超时检查](validation/timeout_recovery_20260908.json)。恢复后的 Continual VLA RL、RL² 和原始 v44 参考使用 `_c` 目录，绑定 GPU 4、5、7；详细恢复记录和实际运行核验见 [RECOVERY.md](experiments/main_aligned_20260908/RECOVERY.md)。CLARE、MLR-IFA 本次暂缓处理。
