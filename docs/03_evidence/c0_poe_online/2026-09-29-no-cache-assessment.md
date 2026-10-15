# 无历史缓存在线 C0 的诊断价值与视频入口

当前已完成条件：Poe Gemini-3-Flash 在线 Stage + 历史 reward 函数缓存，0/10。
本记录仅分析新条件并整理视频，未发起新 GPU 回合或 API 请求。

## 新条件究竟改变什么

把 main.cached_functions_dir 设为 null 后，main.py 的初始化路径会在每个任务开始时，利用当前图像、任务指令和关键点映射调用 VLMAgent.generate_guidance，生成新的 reward 函数、阶段描述与元数据。执行中 Stage 继续在线查询；reward 数值由生成的函数在本地计算，并非每个动作都向 API 请求一个分数。本次新生成文件应保留供审计，不从历史实验读取生成结果。

本轮缓存路径绕过了 VLMAgent 的生成请求，因此此前 Stage 成功不能证明新的 reward 生成路径也已验证。两个模块有独立配置：perception.gemini.model 与 perception.vlm_agent.model；后者默认 gpt-4o。新条件必须显式将两条调用路径都配置为已选定的 Poe Gemini-3-Flash，核对 endpoint 与模型，不能只清空缓存目录。

## 新发现：生成模板要求 stage 2 为零

vlm_query/guidance_template_libero.txt:41 明确要求将物体放入篮筐的任务无需第二阶段 reward，直接返回 0。第 42 行对 caddy、第 46 行对 rack 也有类似要求。因此不改模板、仅重新生成 reward，预期仍保留第二阶段零评分；这不是旧缓存偶然损坏。若新回复意外生成非零评分，需要记录为模板遵循差异，不能预设会产生有效放置信号。

## 建议的实验解释

值得进行一次固定十任务的诊断条件：保留 C0 策略权重、ED 参数、原任务和种子顺序、当前触发/控制规则与模板，仅取消历史 reward/阶段描述缓存，同时固定在线 provider/model。它回答新模型按各任务重新生成描述和评分是否改变闭环表现，不能单独分离 reward 与阶段描述两项贡献。

若达到 3/10，则建立新模型、新生成内容下的观测基线，保存生成物与全部输入输出；单批十任务不足以证明稳定恢复或定位唯一原因。若仍 0/10，需要核对生成结果是否真的改变、是否继续 stage2=0、何时关闭 ED、是否错误宣称完成，再开展控制机制修复；不能据此断言必须换回旧 Poe。

新增 reward 生成可能改变随机数消耗及后续路径；任何严格配对因果对照均应同时重跑参考条件和新条件，使用相同逐 episode 策略 RNG 约定。不能把改 RNG 后的新条件和旧连续随机流的 0/10 当作严格单变量比较。此协议改变应单独声明。

不把夹爪时序、关闭后的复查、阶段二奖励重设计同时混入第一轮缓存消融，也不通过合法任务失败后的重试挑选成功结果。

## 视频

[十任务视频页及三个历史成功对照](videos.html)。本轮每段 72 秒、720 帧、640×640、10 fps，视频不含 API 等待时间。回放对照须标为历史回复回放，而非新的在线成功。

- Task 0 / alphabet soup：[本轮失败视频](../../../artifacts/c0_poe_online_20260929/outputs/c0_poe_gemini3_flash_attempt1/episode_1/episode_1_fail_agentview.mp4)。
- Task 1 / cream cheese：[本轮失败视频](../../../artifacts/c0_poe_online_20260929/outputs/c0_poe_gemini3_flash_attempt1/episode_2/episode_2_fail_agentview.mp4)。
- Task 2 / salad dressing：[本轮失败视频](../../../artifacts/c0_poe_online_20260929/outputs/c0_poe_gemini3_flash_attempt1/episode_3/episode_3_fail_agentview.mp4)。
- Task 3 / bbq sauce：[本轮失败视频](../../../artifacts/c0_poe_online_20260929/outputs/c0_poe_gemini3_flash_attempt1/episode_4/episode_4_fail_agentview.mp4)；[历史回复回放成功视频](../../../artifacts/c0_trace_replay_20260925/outputs/current/episode_4/episode_4_success_agentview.mp4)。
- Task 4 / ketchup：[本轮失败视频](../../../artifacts/c0_poe_online_20260929/outputs/c0_poe_gemini3_flash_attempt1/episode_5/episode_5_fail_agentview.mp4)。
- Task 5 / tomato sauce：[本轮失败视频](../../../artifacts/c0_poe_online_20260929/outputs/c0_poe_gemini3_flash_attempt1/episode_6/episode_6_fail_agentview.mp4)。
- Task 6 / butter：[本轮失败视频](../../../artifacts/c0_poe_online_20260929/outputs/c0_poe_gemini3_flash_attempt1/episode_7/episode_7_fail_agentview.mp4)。
- Task 7 / milk：[本轮失败视频](../../../artifacts/c0_poe_online_20260929/outputs/c0_poe_gemini3_flash_attempt1/episode_8/episode_8_fail_agentview.mp4)。
- Task 8 / chocolate pudding：[本轮失败视频](../../../artifacts/c0_poe_online_20260929/outputs/c0_poe_gemini3_flash_attempt1/episode_9/episode_9_fail_agentview.mp4)；[历史回复回放成功视频](../../../artifacts/c0_trace_replay_20260925/outputs/current/episode_9/episode_9_success_agentview.mp4)。
- Task 9 / orange juice：[本轮失败视频](../../../artifacts/c0_poe_online_20260929/outputs/c0_poe_gemini3_flash_attempt1/episode_10/episode_10_fail_agentview.mp4)；[历史回复回放成功视频](../../../artifacts/c0_trace_replay_20260925/outputs/current/episode_10/episode_10_success_agentview.mp4)。

