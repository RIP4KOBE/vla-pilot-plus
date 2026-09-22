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
- **Dataset info**: Historical exposed object-swap; Dev and unused validation cohorts frozen in data/frozen-seed-plan.json at protocol commit56031d2. Init row0 fixed: stochastic-seed robustness only. New B_dev unknown. Physical GPU7 only; authoritative budget/status research-state.yaml.

Use B_dev for final experiment scoring. Do NOT use B_test.

## Insights From Prior Experiments

- ROOT: New B_dev score remains unknown. CPU diagnosis found82 gripper-discordant archive eliminations,73 duty-bin separations; these are explanatory counts, never task-success scores. Historical no-adoption preserved; engineering input repairs and online prerequisites pending.
- 4: Execution-aware representation N1 implemented under preregistered protocol; task benefit remains unknown.

## Additional Context

User explicitly authorizes current saved Codex ChatGPT login to replace unusable Poe. Implement common provider migration infrastructure only for Q0/P2/N1, preserving task Stage prompt, triggers and canonical reward. Physical GPU7 only, zero online episodes until root freezes migration and passes preflight. Poe configuration retained. Three executor assignments have disjoint file ownership; never modify historical worktrees, root main or the protected historical untracked design file. No credentials printed, copied or extracted; use official CLI managed login. HTTP retry counts unavailable through CLI must be represented as unknown, not zero. Root owns state, runtime freeze and dispatch. No success score can be reported from CPU/probe evidence.

## Instructions

1. Understand the code before editing.
2. Implement the idea faithfully.
3. Run quick checks to ensure the new logic is active.
4. Iterate on implementation bugs.
5. Run the B_dev evaluation when credible.
6. Report Changes, Baseline vs Result, Score, and Insight. The score must be the absolute primary metric, not a delta.

Save results to `results/4.1-<brief-description>/`.
