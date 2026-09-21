## Codebase

Working directory: /home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z

## Git Isolation

Work in the assigned experiment branch/worktree. Do not switch back to the main repository for implementation or evaluation.

## Research Idea

**ID**: 3
**Hypothesis**:
Mechanism: Historical baseline behavior restoration with explicit configuration parity.
Hypothesis: Starting from latest source while disabling later mechanisms can reproduce Q0/C0 semantics only if code-default and profile differences are audited explicitly.
Observable: Full Q0/C0 override manifests, source-difference classification and minimal regression plan against 5b0898e; no claim of online parity before measurement.
Conflicts: Newer HEAD is not presumed best; causal-envelope, anchor, protected lane and degenerate fallback remain disabled.

## Evaluation Info

- **Evaluation command (B_dev)**: `python /home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/scripts/qd_ed_final_runner.py run --split dev --iteration 3`
- **Evaluation command (B_test, do not use for routine experiments)**: `python /home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/scripts/qd_ed_final_runner.py run --split validation --iteration 3`
- **Dataset info**: Historical exposed object-swap; new Dev/Validation identities pending freeze. Historical Q0 2/10 and P2 3/10 are not new Dev baselines. GPU7 only; authoritative budget/status in research-state.yaml.

Use B_dev for final experiment scoring. Do NOT use B_test.

## Instructions

1. Understand the code before editing.
2. Implement the idea faithfully.
3. Run quick checks to ensure the new logic is active.
4. Iterate on implementation bugs.
5. Run the B_dev evaluation when credible.
6. Report Changes, Baseline vs Result, Score, and Insight. The score must be the absolute primary metric, not a delta.

Save results to `results/3-<brief-description>/`.
