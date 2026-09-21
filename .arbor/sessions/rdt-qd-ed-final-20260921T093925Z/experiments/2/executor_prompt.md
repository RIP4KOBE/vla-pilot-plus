## Codebase

Working directory: /home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z

## Git Isolation

Work in the assigned experiment branch/worktree. Do not switch back to the main repository for implementation or evaluation.

## Research Idea

**ID**: 2
**Hypothesis**:
Mechanism: Reproducible runtime and input identity verification before online evaluation.
Hypothesis: Stale absolute paths and task-ambiguous guidance cache can confound a new control; verifying identities before dispatch isolates infrastructure from QD effects.
Observable: Dependency, checkpoint, BDDL/init-state/cache and GPU7 admission inventory plus exact runnable evaluation contract; no GPU execution in this audit.
Conflicts: All historical artifacts remain immutable and the protected untracked stage-guidance design remains unread.

## Evaluation Info

- **Evaluation command (B_dev)**: `python /home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/scripts/qd_ed_final_runner.py run --split dev --iteration 2`
- **Evaluation command (B_test, do not use for routine experiments)**: `python /home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/scripts/qd_ed_final_runner.py run --split validation --iteration 2`
- **Dataset info**: Historical exposed object-swap; new Dev/Validation identities pending freeze. Historical Q0 2/10 and P2 3/10 are not new Dev baselines. GPU7 only; authoritative budget/status in research-state.yaml.

Use B_dev for final experiment scoring. Do NOT use B_test.

## Instructions

1. Understand the code before editing.
2. Implement the idea faithfully.
3. Run quick checks to ensure the new logic is active.
4. Iterate on implementation bugs.
5. Run the B_dev evaluation when credible.
6. Report Changes, Baseline vs Result, Score, and Insight. The score must be the absolute primary metric, not a delta.

Save results to `results/2-<brief-description>/`.
