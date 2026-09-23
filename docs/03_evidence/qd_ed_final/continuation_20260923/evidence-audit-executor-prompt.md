## Codebase

Working directory: /home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z

## Git Isolation

Work in the assigned experiment branch/worktree. Do not switch back to the main repository for implementation or evaluation.

## Research Idea

**ID**: 5.2
**Hypothesis**:
Mechanism: Full-precision decision-to-observation evidence contract.
Hypothesis: Actual provider quality, candidate identity and executed-horizon geometry linked to lawful next observations can distinguish real selection errors from XY-only proxy differences.
Observable: Audit of available data and minimal observational instrumentation specification with exact ranking reconstruction and no online lookahead.
Conflicts: Historical17/220 XY argmin differences are not quality misranking; no N1 rename, privileged evaluator input or external reward change.

## Evaluation Info

- **Evaluation command (B_dev)**: `python /home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/scripts/qd_ed_final_runner.py run --split dev --iteration 5.2`
- **Evaluation command (B_test, do not use for routine experiments)**: `python /home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/scripts/qd_ed_final_runner.py run --split validation --iteration 5.2`
- **Dataset info**: Historical exposed object-swap; Dev and unused validation cohorts frozen in data/frozen-seed-plan.json at protocol commit56031d2. Init row0 fixed: stochastic-seed robustness only. New B_dev unknown. Physical GPU3 only; authoritative budget/status research-state.yaml.

Use B_dev for final experiment scoring. Do NOT use B_test.

## Insights From Prior Experiments

- ROOT: User explicitly requires continuation to target: engineering failures and missing targeted evidence trigger further recovery/collection, not overall termination. All current dispatch must use physical GPU3. Preserve prior invalid N1 cohort and all costs.

## Additional Context

CPU audit/preparation only. No GPU dispatch by executor. Outputs in the assigned local continuation subdirectory while data mount is unavailable. Preserve original protected paths, failed evidence, reward/model/action/eval semantics. Coordinator freezes and dispatches GPU3-only diagnostics.

## Instructions

1. Understand the code before editing.
2. Implement the idea faithfully.
3. Run quick checks to ensure the new logic is active.
4. Iterate on implementation bugs.
5. Run the B_dev evaluation when credible.
6. Report Changes, Baseline vs Result, Score, and Insight. The score must be the absolute primary metric, not a delta.

Save results to `results/5.2-<brief-description>/`.
