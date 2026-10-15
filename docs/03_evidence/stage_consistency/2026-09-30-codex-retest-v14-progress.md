# Codex 再次实测与 V14 运行检查

记录时间：2026-09-30T10:54:27.864892+00:00。总研究目标尚未完成；本文件为运行检查点，不是完整十任务结论。

## 当前账号接入

本机 `codex login status` 为 ChatGPT 登录。新真实图片请求于 2026-09-30T10:52:34.142372+00:00 发起，2026-09-30T10:52:50.596549+00:00 完成，gpt-6-astra / low，耗时 16.45 秒。结果 PASS：单次 CLI 调用、单次完整回复、五字段 Stage JSON 有效、零失败。HTTP 内部尝试/重试不可观测，不能表述为 HTTP 200 或零内部重试。旧图片仅用作新请求输入，没有复用旧回复，也未控制正在运行的 rollout。

实验与独立探针均只用当前 Codex 账号，Poe 禁用。官方 CLI 支持 ChatGPT 登录与 API key 两种不同方式：[OpenAI 身份验证说明](https://learn.chatgpt.com/docs/auth)。这里验证的是当前账号经 CLI 调用，不是单独的 Platform API key。

证据：`artifacts/stage_closed_loop_20260929/codex-availability-retest-20260930T105232Z/result.json`、`requests/request_0000/response.json`、`requests/request_0000/public-policy.json`。

## 实验进度与初步控制检查

GPU2 单 worker 2716202、supervisor 2715952、续接队列 2595833 均已核对存活。2026-09-30T10:54:26.387415+00:00 时完成 1/10，已完成成功数 0，当前 task1 step200，查询错误 0。冻结源码哈希差异 0。

第一个任务 alphabet soup 720 步失败。step632 的 clear+held 已进入 Stage2；step664 新规则接受了 occluded+held+unsupported 并保持 visual_hold，未误判完成。已查看未标记原图，目标确实悬在夹爪下方、位于篮外，顶端被夹爪部分遮挡。step696 原图显示夹爪与目标分离、目标仍在篮外；单帧不能证明稳定落地。该轨迹证明新规则实际执行，但不能把局部正确当作性能恢复，也不能说是新规则首次建立这次 Stage2。

保持冻结配置继续完整十任务；完成后再审计、复核成功/失败视频，并按完整结果决定是否继续修复。没有开始 QD 优化。

原始检查点：`artifacts/stage_closed_loop_20260929/codex-availability-retest-20260930T105232Z/experiment-checkpoint.json`。

## 12:46 UTC 再次独立实测

当前账号 gpt-6-astra/low 的新图片请求于12:46:38发起、12:46:58完成，19.757秒，1次CLI调用/1次完整回复，0失败；五字段Stage JSON有效。仍不将不可观测的HTTP内部尝试写作HTTP 200或零重试。证据：`artifacts/stage_closed_loop_20260929/codex-availability-retest-20260930T124636Z/result.json`。该独立回复不控制正在运行的回合。GPU2此时完成9/10、成功2项、最终orange juice仍运行，无查询错误；冻结源hash无变化，完整结果未产生。
