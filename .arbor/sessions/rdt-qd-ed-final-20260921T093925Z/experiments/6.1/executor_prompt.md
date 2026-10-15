## Codebase

Working directory: /home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-executed-quality-20260923

## Git Isolation

Work in the assigned experiment branch/worktree. Do not switch back to the main repository for implementation or evaluation.

## Research Idea

**ID**: 6.1
**Hypothesis**:
Mechanism: Dual-channel full-executed-prefix QD quality before archive replacement and ED selection, with original provider quality retained for Stage.
Hypothesis: The exact recognized approach objective over t1..t8 can retain and select actions missed by t1..t7 ranking, where observed final alternatives require an original-quality tradeoff.
Observable: At least one recorded candidate choice changes under the frozen formula; prospective N2 reaches at least5/10 Dev and no fewer successes than matched P2/Q0 while passing action, Stage and compute gates.
Conflicts: H4/H5 retained old quality; N2 explicitly changes its semantics, does not promise old maximum retention, and keeps N1 descriptor changes off.

## Evaluation Info

- **Evaluation command (B_dev)**: `python /home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-executed-quality-20260923/scripts/qd_ed_final_runner.py run --split dev --iteration 6.1`
- **Evaluation command (B_test, do not use for routine experiments)**: `python /home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-executed-quality-20260923/scripts/qd_ed_final_runner.py run --split validation --iteration 6.1`
- **Dataset info**: Historical exposed object-swap; Dev and unused validation cohorts frozen in data/frozen-seed-plan.json at protocol commit56031d2. Init row0 fixed: stochastic-seed robustness only. New B_dev unknown. Physical GPU3 only; authoritative budget/status research-state.yaml.

Use B_dev for final experiment scoring. Do NOT use B_test.

## Insights From Prior Experiments

- ROOT: User explicitly requires continuation to target: engineering failures and missing targeted evidence trigger further recovery/collection, not overall termination. All current dispatch must use physical GPU3. Preserve prior invalid N1 cohort and all costs.

## Instructions

1. Understand the code before editing.
2. Implement the idea faithfully.
3. Run quick checks to ensure the new logic is active.
4. Iterate on implementation bugs.
5. Run the B_dev evaluation when credible.
6. Report Changes, Baseline vs Result, Score, and Insight. The score must be the absolute primary metric, not a delta.

Save results to `results/6.1-<brief-description>/`.
