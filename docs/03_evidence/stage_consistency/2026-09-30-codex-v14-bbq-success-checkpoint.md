# V14 Codex 在线 BBQ 成功检查点

2026-09-30 11:21 UTC，冻结 V14 第四项任务 BBQ sauce 成功，环境评测120步结束。当时整轮4/10已完成、累计1/4成功；余下六项仍按同一冻结配置运行，不能称为恢复3/10或完成goal。

新规则在第80步接受Codex明确的occluded+held+unsupported，建立Stage2及visual_hold。第96步未重新开启接近ED；旧V13在这一点因未接受遮挡抓持而恢复ED，并产生首个动作分叉。这次120个实际七维动作与Poe V11的成功BBQ回合逐项一致，零动作覆盖。V11还有provider/reward-reference差异，不由单例推断两种provider整体等价。

六次Stage查询、一次identity、一次fresh reward共八次CLI完成，零失败。完成判定没有放宽：视频末段仍为Stage2，环境先满足真实成功条件而终止；不能把环境成功说成视觉已经获得两次稳定落地确认。

已检查原视频40/80/96/112/119帧：目标抓起并搬到篮口内，最终片段执行原生OPEN，没有观察到篮子翻转或大幅拖移。已采样篮中心最大平移约0.0523米。由于成功时立即结束，没有后续稳定支撑观测；不声称视频已证明长时间稳定放置。视频右上角SUCCESS是最终回合结果水印，出现在所有保存帧，不是40步即成功，也不进入在线视觉输入。

原始证据位于 `artifacts/stage_closed_loop_20260929/runs/codex_partial_visibility_v14_historical_initialization_online_full10/bbq-success-review.json`，包括动作比较、控制事件、视频hash和抽帧记录。

视频：`output/episode_4/episode_4_success_agentview.mp4`，对应上述run。完整十任务结束后仍需最终源代码/退出码/在线请求/reward/初始化审计以及全部成功视频复核；当前不修改源码、不派发其他GPU worker、不调用Poe。
