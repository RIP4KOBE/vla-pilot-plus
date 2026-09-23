## Codebase

Working directory: /home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z

## Git Isolation

Work in the assigned experiment branch/worktree. Do not switch back to the main repository for implementation or evaluation.

## Research Idea

**ID**: 5.1
**Hypothesis**:
Mechanism: Differential audit of native render state and model interaction.
Hypothesis: The pre-model wrist-image drift in resource72a4dc721056 exposes a resource-state discrepancy that ordering-only probes did not isolate.
Observable: Exact source-level discrepancy and a bounded prospective repair/diagnostic contract preserving physics and image semantics on physical GPU3.
Conflicts: Preserve all old Xid/image-parity failures; no retroactive threshold relaxation or production patch without evidence.

## Evaluation Info

- **Evaluation command (B_dev)**: `python /home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/scripts/qd_ed_final_runner.py run --split dev --iteration 5.1`
- **Evaluation command (B_test, do not use for routine experiments)**: `python /home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/scripts/qd_ed_final_runner.py run --split validation --iteration 5.1`
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

Save results to `results/5.1-<brief-description>/`.
