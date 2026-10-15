# EDS-QD Stage/Guidance Transition 最终报告

生成时间：`2026-08-10T19:19:33.608385+00:00`

## 结论

- 决策：`negative_result_keep_legacy`。
- FSM 两轮合计：`0/20`，mean SR `0.00`；mean gate：`FAIL`。
- FSM mechanism gate：`PASS`；safety gate：`FAIL`。

## 两轮 paired 结果

- Round 0: legacy `0/10`，FSM `0/10`，gained `[]`，lost `[]`。
- Round 1: legacy `1/10`，FSM `0/10`，gained `[]`，lost `[7]`。

## 逐 job 审计

- `eds_qd_uniform_expand20_p48_k20_transition_legacy_r0`: success `0/10`，valid `PASS`，safety `PASS`，FSM mechanism `PASS`。
- `eds_qd_uniform_expand20_p48_k20_transition_fsm_v1_r0`: success `0/10`，valid `FAIL`，safety `FAIL`，FSM mechanism `PASS`。
- `eds_qd_uniform_expand20_p48_k20_transition_legacy_r1`: success `1/10`，valid `FAIL`，safety `FAIL`，FSM mechanism `PASS`。
- `eds_qd_uniform_expand20_p48_k20_transition_fsm_v1_r1`: success `0/10`，valid `FAIL`，safety `FAIL`，FSM mechanism `PASS`。

## 执行与审计

- formal episodes：`40/40`；attempts：`40/44`。
- GPU：`PASS`；shared2 storage：`PASS`。
- Git：`PASS`；credential：`PASS`；process cleanup：`PASS`。
- 无效或失败 jobs：`['eds_qd_uniform_expand20_p48_k20_transition_fsm_v1_r0', 'eds_qd_uniform_expand20_p48_k20_transition_legacy_r1', 'eds_qd_uniform_expand20_p48_k20_transition_fsm_v1_r1']`。
- 本设计不授权依据结果追加实验或调参。
