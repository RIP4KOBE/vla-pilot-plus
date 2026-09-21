## Codebase

Working directory: /home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z

## Git Isolation

Work in the assigned experiment branch/worktree. Do not switch back to the main repository for implementation or evaluation.

## Research Idea

**ID**: 1
**Hypothesis**:
Mechanism: Evidence-separated causal diagnosis across proposal, selection, and closed-loop behavior.
Hypothesis: Historical aggregate proxy gains conceal unresolved failure classes; separating observed facts from counterfactual unknowns can identify a testable task-linked mechanism.
Observable: A source-cited evidence matrix and bounded in-scope mechanism queue, with zero new episodes or invented success scores.
Conflicts: Historical H1/H2/H4/H5 negative outcomes remain valid; no direction is replayed without new evidence and a specific difference.

## Evaluation Info

- **Evaluation command (B_dev)**: `python /home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/scripts/qd_ed_final_runner.py run --split dev --iteration 1`
- **Evaluation command (B_test, do not use for routine experiments)**: `python /home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/scripts/qd_ed_final_runner.py run --split validation --iteration 1`
- **Dataset info**: Historical exposed object-swap; new Dev/Validation identities pending freeze. Historical Q0 2/10 and P2 3/10 are not new Dev baselines. GPU7 only; authoritative budget/status in research-state.yaml.

Use B_dev for final experiment scoring. Do NOT use B_test.

## Instructions

1. Understand the code before editing.
2. Implement the idea faithfully.
3. Run quick checks to ensure the new logic is active.
4. Iterate on implementation bugs.
5. Run the B_dev evaluation when credible.
6. Report Changes, Baseline vs Result, Score, and Insight. The score must be the absolute primary metric, not a delta.

Save results to `results/1-<brief-description>/`.
