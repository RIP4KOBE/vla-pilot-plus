# RDT+EDS Mechanism Ablation Run Notes

Date: 2026-06-16

Output root: `outputs/rdt_eds_mechanism_pretest`

Reference structure: `libero_object_task1_seed000_normal_p16_c10`

All runs use LIBERO object task 1, seed 0, one episode, first action chunk only, population size 16, CEM iterations 10, and mechanism pretest artifact saving enabled.

Runs:

- `libero_object_task1_seed000_ablate_resample_only_p16_c10`: softmax resampling only; renoise and rollout disabled through temporary eval-only hook.
- `libero_object_task1_seed000_ablate_weak_renoise_p16_c10`: normal softmax resampling and rollout; renoise noise scale set to 0.25 through temporary eval-only hook.
- `libero_object_task1_seed000_ablate_softmax_strong_p16_c10`: normal pipeline; softmax temperature set to 2.0 to strengthen high-reward parent selection.
- `libero_object_task1_seed000_ablate_cem_resample_p16_c10`: normal pipeline; CEM resampling enabled with 4 elites.
- `libero_object_task1_seed000_ablate_negative_reward_p16_c10`: normal pipeline; reward mode set to inverted as a sign-control ablation.

Code hygiene requirement: restore the temporary `ablation_mode` and `renoise_scale` code/test hooks after all runs complete; keep generated outputs and this note.
