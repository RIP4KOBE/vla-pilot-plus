# N17 passive physics Dev diagnosis: contact without lift versus sustained grasp

Two original N7 Dev identities were dispatched serially on physical GPU3 under the frozen E2 Stage condition. Both native attempts and decision-evidence audits are valid. No branch simulation, candidate algorithm, validation or formal evaluation was run. Plan v2 SHA-256 is `2b379e94f31b5e708d42d8702b2845d75f9123cf5932823d08ab88683c30e97f`; source commit is `5a26845`. The complete numeric result and attempt IDs are in `physics-analysis-v1.json`.

| Path | Outcome | Target–gripper contact steps | Bilateral finger-contact steps | Longest continuous ≥3 cm target lift | Target maximum rise |
| --- | --- | ---: | ---: | ---: | ---: |
| task 0, alphabet soup | fail, 720 actions | 115 | 0 | 0 | 1.27 cm |
| task 9, orange juice | success, 524 actions | 438 | 152 | 332 | 14.95 cm |

Task 0 first contacted the target at action step 19 while guidance was on, but it never raised the object by 3 cm. Task 9 first contacted at step 25 after guidance had turned off; it then carried the object and reached the basket. The actual success predicate, not proximity or contact counts, labels task 9 successful. These are two correlated paths and do not prove a universal grasp rule.

The first supervisor audit rejected task 9 because its final `sim_time` changed from 26.40 s to 0.25 s. Source inspection showed that `LiberoAdapter.step` records the valid terminal outcome and then automatically resets before returning. The original failed supervisor status and all raw bytes remain unchanged. `reaudit_terminal_reset.py` SHA-verified the same 524-row trace, found one time reset exactly at the successful final action, and excluded only that post-reset *physics snapshot*; the native task success remains valid. The corrected independent audit is `supervisor-status-corrected-v2.json` and 523 preterminal action-boundary physics rows were analyzed. No GPU retry was made.

The result motivates one QD–ED candidate: use the **projected EEF lift after a near-target closing command** as a proposal/quality term while retaining the frozen external reward and 176/11 canonical search budget. The term must use only candidate actions and policy-visible current keypoints, not the diagnostic's privileged MuJoCo contact/pose. It should be zero when no credible near-close phase exists; this protects tasks such as 9 where the decisive grasp occurred outside guidance. The candidate still needs a prospective protocol, CPU mechanism/parity tests, and the remaining 12 development attempts for a matched C0/Q0/candidate gate before any validation.

GPU3 cumulative accounting after N17: 204/393 dispatched attempts, 113/125 development attempts, 27.2685431984/100 GPU hours. The 12 remaining development slots are reserved for the next three-arm four-task Dev cohort; validation and formal remain closed.
