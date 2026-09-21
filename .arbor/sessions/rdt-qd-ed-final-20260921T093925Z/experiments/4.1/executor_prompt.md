## Codebase

Working directory: /home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z

## Git Isolation

Work in the assigned experiment branch/worktree. Do not switch back to the main repository for implementation or evaluation.

## Research Idea

**ID**: 4.1
**Hypothesis**:
Mechanism: Sixteen-cell radial-distance by executed positive-gripper-duty QD archive.
Hypothesis: Replacing XY-only equivalence separates lower-reward gripper-intent branches during parent search, yielding useful new proposals without extra model evaluations.
Observable: Correct constant-budget behavior, changed actual parent lineage, N1 Dev>=5/10 and noninferior to same-round P2/Q0 before validation.
Conflicts: H5 secondary trajectory lanes failed; N1 changes equivalence at capacity16 and leaves quality/allocation/EDS switches unchanged; azimuth/timing information loss is explicitly tested.

## Evaluation Info

- **Evaluation command (B_dev)**: `python /home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/scripts/qd_ed_final_runner.py run --split dev --iteration 4.1`
- **Evaluation command (B_test, do not use for routine experiments)**: `python /home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/scripts/qd_ed_final_runner.py run --split validation --iteration 4.1`
- **Dataset info**: Historical exposed object-swap; new Dev/Validation identities pending freeze. Historical Q0 2/10 and P2 3/10 are not new Dev baselines. GPU7 only; authoritative budget/status in research-state.yaml.

Use B_dev for final experiment scoring. Do NOT use B_test.

## Insights From Prior Experiments

- ROOT: New B_dev score remains unknown. CPU diagnosis found82 gripper-discordant archive eliminations,73 duty-bin separations; these are explanatory counts, never task-success scores. Historical no-adoption preserved; engineering input repairs and online prerequisites pending.

## Instructions

1. Understand the code before editing.
2. Implement the idea faithfully.
3. Run quick checks to ensure the new logic is active.
4. Iterate on implementation bugs.
5. Run the B_dev evaluation when credible.
6. Report Changes, Baseline vs Result, Score, and Insight. The score must be the absolute primary metric, not a delta.

Save results to `results/4.1-<brief-description>/`.
