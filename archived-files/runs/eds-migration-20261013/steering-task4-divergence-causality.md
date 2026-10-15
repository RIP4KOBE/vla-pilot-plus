# 任务1–4合同补审与任务4动作分歧

只读时间：2026-10-13T11:18:00.578037+00:00。使用pending-integration中的独立离线审计，冻结commit仍为`cfecb12db736f1a3408d9528d9336aadcb7e41b5`；仅在`/tmp`保存本次报告，没有GPU/API/源码/config修改。完整cohort尚未验收。

| task | PASS | Stage captures / queries | fresh reward | action / adapter exit | 完成任务合同 |
| --- | --- | --- | --- | --- | --- |
| 1 | 1765 | 40 / 39 | 1 | 720 / 720 | PASS，0FAIL/0pending |
| 2 | 1808 | 41 / 40 | 1 | 720 / 720 | PASS，0FAIL/0pending |
| 3 | 389 | 8 / 7 | 1 | 120 / 120 | PASS，0FAIL/0pending |
| 4 | 1550 | 35 / 34 | 1 | 720 / 720 | PASS，0FAIL/0pending |

总计124 Stage captures、4 fresh rewards、2280 actions/adapter exits完成对账。task0既有1722PASS报告未重复执行。[汇总和脚本/报告SHA](/tmp/steering-completed-tasks1-4-contract-summary.json)；逐任务报告为`/tmp/steering-task1-contract-complete.json`至`/tmp/steering-task4-contract-complete.json`。`task_contract_valid`和`task_evidence_complete`均true，但`cohort_valid`仍null；其他正在写入且无法归属的capture只记在途事实，不影响已完成任务。

任务4的**首次动作差异在472，导致控制分支不同的Stage回复发生在464**。原始在线回复更早已有措辞或观察字段差异；不能把464说成首次回复变化。

| 步骤 | 当前运行 | 已验收来源 | 直接含义 |
| --- | --- | --- | --- |
| 448 | occluded/outside_goal/unknown/unknown | clear/outside_goal/unknown/unknown | 均留Stage1、guidance OFF；尚无动作差异 |
| 464 | clear/outside_goal/**held/unsupported**；`visually_held_target`，Stage1→2，reference reset | clear/outside_goal/**unknown/unknown**；保留Stage1，contact_grace到472 | 阶段首次不同，但当前Stage2 constant reward、来源controller_hold，guidance均OFF |
| 464–471 | 动作与来源相同 | 动作与当前相同 | Stage变化不是立刻更改动作的override |
| 472 | **没有新Stage查询**；Stage2，`constant_on_probes`，guidance OFF | **没有新Stage查询**；contact_until472到期，Stage1 `usable_reward`，guidance ON | guidance首次不同，动作从这一步首次分歧 |

第464步current response：

```json
{"target_visibility":"clear","target_location":"outside_goal","grasp":"held","support":"unsupported","evidence":"The ketchup bottle is horizontal in front of and left of the basket, visibly suspended with its capped neck between the robot fingers. It is outside the basket interior."}
```

第464步reference response：

```json
{"target_visibility":"clear","target_location":"outside_goal","grasp":"unknown","support":"unknown","evidence":"The ketchup lies sideways below the gripper and left of the basket, outside its interior. Its cap is near the fingers, but finger contact and support are unclear."}
```

两份response均为`codex_cli`/ChatGPT/`gpt-6-astra`/`low`，1 physical call、1 completed turn且ok；观察来自各自真实在线调用。发送PNG的SHA完全相同：`e57a9946242f5ce3fa114ebaf5277c263de5c4ebc4ec5415a08c42136db6c88a`。但prompt SHA分别为`f59759d0a385493ac617dde919f3ba20a73348053d952a0b75b101f130d6d7ef`与`98c8670b732de847133ad8ad372ccffa5a31d21d84258db682d8636ab088f4ee`，**唯一文本差异是每任务fresh生成的initial identity-memory那一行**。因此这里支持“在线Stage链条的语义差异进入控制”，不能断言“同一完整请求随机返回不同答案”，也不能仅凭记录判断哪个抓取描述符合物理真值。

第472步，current原始/执行动作均为`[-0.052734375, 0.021484375, -0.1259765625, 0.0025482177734375, 0.041748046875, -0.0186767578125, 1.0]`；reference均为`[-0.50390625, -1.7109375, -0.23828125, 0.022216796875, -0.012939453125, -0.034912109375, 1.0]`。臂动作不同，gripper均为+1；双方`override=false`、reason=`policy_gripper_passthrough`。0–471共472个动作逐值一致，472–719共248个动作不同；截至472的robot_evidence仍一致。参考运行在472有一次10迭代EDS搜索记录，当前运行在472没有guided metric行，与guidance gate相符。双方本任务最终均记录为720步失败。

证据位置：当前与来源的`stage_events.jsonl`均第344行是464、第345行是472；`safety_events.jsonl`均第2753行是动作472。当前[Stage464](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/runs/eds-migration-20261013/output/eds_eval/stage_events.jsonl:344)、[Stage472](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/runs/eds-migration-20261013/output/eds_eval/stage_events.jsonl:345)、[动作472](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/runs/eds-migration-20261013/output/eds_eval/safety_events.jsonl:2753)；来源[Stage464](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-gpu6-20260922T063626Z/study_worktree/artifacts/stage_closed_loop_20260929/runs/codex_failed_contact_v17_historical_initialization_online_full10/output/eds_eval/stage_events.jsonl:344)、[Stage472](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-gpu6-20260922T063626Z/study_worktree/artifacts/stage_closed_loop_20260929/runs/codex_failed_contact_v17_historical_initialization_online_full10/output/eds_eval/stage_events.jsonl:345)、[动作472](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-gpu6-20260922T063626Z/study_worktree/artifacts/stage_closed_loop_20260929/runs/codex_failed_contact_v17_historical_initialization_online_full10/output/eds_eval/safety_events.jsonl:2753)。原始捕获为[当前request0150](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/runs/eds-migration-20261013/output/captured_stage_inputs/request_0150)、[来源request0147](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-gpu6-20260922T063626Z/study_worktree/artifacts/stage_closed_loop_20260929/runs/codex_failed_contact_v17_historical_initialization_online_full10/output/captured_stage_inputs/request_0147)。完整selected fields、reply、hash和行号见[因果证据JSON](/tmp/steering-task4-divergence-causality.json)。

冻结实现与记录一致：`stage_evidence.decide`对可用held观察转Stage2（[source/core/stage_evidence.py](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/runs/eds-migration-20261013/source/core/stage_evidence.py:92)）；`apply_handoff`在Stage2清除contact等待，在Stage1等待到期后重新请求guidance（[source/core/stage_contact_handoff.py](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/runs/eds-migration-20261013/source/core/stage_contact_handoff.py:34)）；capability gate拒绝constant reward而接受usable reward（[guidance gate](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration/runs/eds-migration-20261013/source/core/stage_evidence.py:107)）。本次没有执行反事实重放，故报告是有记录支持的控制因果路径，不是干预实验；没有据此声明全cohort等价或基础设施失败。
