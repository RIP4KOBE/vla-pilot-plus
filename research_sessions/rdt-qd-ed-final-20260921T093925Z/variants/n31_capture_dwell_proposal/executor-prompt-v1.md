## Active phase override: CPU phase A only

Read `hypothesis-and-cpu-phase-a-v1.md` in this variant's parent directory first. Its finite CPU-only scope supersedes the generated evaluation suggestions below: implement a pure helper and synthetic tests in the assigned implementation worktree, and inspect integration sites statically. Do not invoke either generated B_dev/B_test command or generic instruction5. No GPU, new historical data measurements, model/scorer/environment/API use, production hookup, state/budget writes, or protected data. The old N21/N22 dataset metadata below is historical template context, not an N31 run plan. Deliver Score=Unknown with CPU/source evidence. All artifacts remain under this N31 variant.

## Codebase

Working directory: /home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n31_capture_dwell_proposal/implementation

## Git Isolation

Work in the assigned experiment branch/worktree. Do not switch back to the main repository for implementation or evaluation.

## Research Idea

**ID**: 15.1
**Hypothesis**:
Mechanism: N31 inserts one capture-dwell completion of the current Q0 archive best into offspring slot15 before canonical scoring, using observed hand geometry and the base plan's first projected entry.
Hypothesis: Holding subsequent pose increments at zero while issuing close commands through the remaining fixed prefix may prevent transient approach followed by premature withdrawal, while normal QD/ED competition preserves alternatives.
Observable: Full-ten matched C0/Q0/N31 Dev candidate at least5/10 and no lower than both controls, plus native proposal-to-selection trace and unchanged176 primary evaluations/11 batches; GPU requires sufficient approved bucket allowance.
Conflicts: N30 minimum-alignment screen found both selected minima already zero; N22 only rewarded existing close/lift, N24 rescued existing closing content, and N30 reused past tails. N31 creates a current-search coordinated dwell proposal; physical capture remains unproven.

## Evaluation Info

- **Evaluation command (B_dev)**: `python /home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n31_capture_dwell_proposal/implementation/scripts/qd_ed_final_runner.py run --split dev --iteration 15.1`
- **Evaluation command (B_test, do not use for routine experiments)**: `python /home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n31_capture_dwell_proposal/implementation/scripts/qd_ed_final_runner.py run --split validation --iteration 15.1`
- **Dataset info**: Original frozen Dev tasks0..9, C0/Q0/N21/N22 task-major40 cells. N21 ablation only; old Dev reuse disclosed. Protected phases require separate successful promotion.

Use B_dev for final experiment scoring. Do NOT use B_test.

## Insights From Prior Experiments

- ROOT: Goal NOT_MET. N29 all four arms0/6; N30 C0/Q0/N30 each0/2, rejected by frozen3/4 first-four gate, unrun cells Unknown. Fixed decision16 pool screen fully associated32 archive rows: both actual selected plans already minimum point-prism0, so minimum-alignment reranking lacks support. Task0 selected projected alignment is transient while actual hand withdraws during closure; task1 final archive contains no close command in first8. Capture/physical efficacy remain Unknown. Consider a temporally coordinated proposal operator, distinct from prior scalar lift bonuses, existing-close rescue, and cross-chunk continuation. Budget403/578,53.80872756284531/100GPUh; week revision pending; no GPU or protected-phase release.

## Instructions

1. Understand the code before editing.
2. Implement the idea faithfully.
3. Run quick checks to ensure the new logic is active.
4. Iterate on implementation bugs.
5. Run the B_dev evaluation when credible.
6. Report Changes, Baseline vs Result, Score, and Insight. The score must be the absolute primary metric, not a delta.

Save results to `results/15.1-<brief-description>/`.
