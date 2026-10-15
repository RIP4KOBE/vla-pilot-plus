## Codebase

Working directory: /home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n24_gripper_mode_parent_rescue/implementation

## Git Isolation

Work in the assigned experiment branch/worktree. Do not switch back to the main repository for implementation or evaluation.

## Research Idea

**ID**: 10.1
**Hypothesis**:
Mechanism: N24 remembers the lowest-native-cost full-eight-positive canonical proposal within one guided search and substitutes it for one worst-cost parent only when the allocated sixteen contain no such mode.
Hypothesis: Restoring an actually missing generated closing-command mode before unchanged ED refinement can prevent allocation-level extinction and improve task outcomes without altering reward or forcing execution.
Observable: Frozen C0/Q0/N23/N24 ten-task Dev comparison requires N24 at least5/10 and no fewer successes than every control, with exact causal-source/action/176-score accounting; complete-quadruple numeric futility may stop the candidate early.
Conflicts: N23 remains rejected0/6 and is only the direct matched ablation; N11 cannot rescue modes absent from its already allocated pool, H4/H5 lacked this command-conditioned trigger, and no closing command is assumed to be a successful grasp.

## Evaluation Info

- **Evaluation command (B_dev)**: `python /home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n24_gripper_mode_parent_rescue/implementation/scripts/qd_ed_final_runner.py run --split dev --iteration 10.1`
- **Evaluation command (B_test, do not use for routine experiments)**: `python /home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n24_gripper_mode_parent_rescue/implementation/scripts/qd_ed_final_runner.py run --split validation --iteration 10.1`
- **Dataset info**: Original frozen Dev tasks0..9, C0/Q0/N21/N22 task-major40 cells. N21 ablation only; old Dev reuse disclosed. Protected phases require separate successful promotion.

Use B_dev for final experiment scoring. Do NOT use B_test.

## Insights From Prior Experiments

- ROOT: Target unmet; autonomous study continues after N23 numeric futility. N23 0/6 vs C0 1/6,Q0/N7 0/6, remaining4 cannot reach5/10;24 native-valid cells,no full-ten efficacy score,no reruns. Source5110447 unchanged; original failed v2 result retained. Native activation did not yield task success. Closed full8 command-survival diagnostic distinguishes proposal absence, actual-parent absence and final choice;25/27 new final-loss decisions lacked full8 at later actual allocation;4462/4525 allocated full8 parents kept mode in ordered offspring. Physical utility and archive replacement causes remain Unknown. N3 lower retrospective error0/10,N11 quality-ranked survival1/4 and historicalH4/H5 remain negative priors. Settled261/478 attempts,37.30680221848908/100GPUh; protected reserves intact,1private GPU7 worker maximum. Current-account codex_cli/chatgpt only,no Poe/fallback. One justified successor may be frozen within current capacity; validation/formal gates unchanged.

## Instructions

1. Understand the code before editing.
2. Implement the idea faithfully.
3. Run quick checks to ensure the new logic is active.
4. Iterate on implementation bugs.
5. Run the B_dev evaluation when credible.
6. Report Changes, Baseline vs Result, Score, and Insight. The score must be the absolute primary metric, not a delta.

Save results to `results/10.1-<brief-description>/`.
