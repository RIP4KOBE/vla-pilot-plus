# LIBERO-PRO Object-Swap RDT+EDS RBF Report

Timestamp: `2026-07-14T13:20:25+00:00`

Verdict: `pass`

## Scope

- Suite: `libero_object_swap`
- Episodes per job: `10`
- Level: `object_swap_ood_rbf` using strict LIBERO-PRO perturbations.
- Fixed initial sampler: `rbf_diverse_denoise`, scale `20.0`, start ratio `0.8`.
- Sweep: `renoise_t_max in [4,3,2,1]`, rollout RBF scale `[5,10,15,20]`, start ratio `[0.2,0.4,0.6,0.8]`, iterations `[1,3,6,all]`.
- Output root: `outputs/ood_eval`.
- Referenced Level-4 aggregate: `/home/hynx/VLA-Pilot++/.worktrees/feat/rdt_ed_steering_integration/docs/03_evidence/eds_steering/level_4_vls_pi05_libero_pro_ood.md`.

## Referenced Baselines

| Method | Source | Success | SR | Source Method |
| --- | --- | ---: | ---: | --- |
| `rdt_unguided` | `referenced_level4` | 0/10 | 0.00 | RDT unguided |
| `eds_iid_baseline` | `referenced_level4` | 0/10 | 0.00 | RDT+EDS softmax |

## New Results

| Method | Source | Status | Valid | Success | SR | Records | Videos | Qual PNG | rtmax | Rollout Scale | Rollout Start | Iters | select_latency | EDS latency | Failure Reason |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| `eds_rbf_init_s20_start08` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1180 | 1 | null | null | `null` | 1.578 | 1.510 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start02_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 5.0 | 0.2 | `1` | 2.608 | 2.538 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start02_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 5.0 | 0.2 | `3` | 2.661 | 2.589 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start02_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 5.0 | 0.2 | `6` | 2.821 | 2.752 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start02_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 5.0 | 0.2 | `all` | 2.906 | 2.834 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start04_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 5.0 | 0.4 | `1` | 2.621 | 2.552 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start04_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 5.0 | 0.4 | `3` | 2.725 | 2.655 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start04_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 5.0 | 0.4 | `6` | 2.827 | 2.753 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start04_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 5.0 | 0.4 | `all` | 2.950 | 2.882 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start06_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 5.0 | 0.6 | `1` | 2.630 | 2.563 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start06_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 5.0 | 0.6 | `3` | 2.712 | 2.644 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start06_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 5.0 | 0.6 | `6` | 2.864 | 2.797 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start06_iterall` | `new_run` | `failed` | `False` | 1/10 | 10.00 | 876 | 9 | 1300 | 4 | 5.0 | 0.6 | `all` | 3.009 | 2.929 | videos 9/10 |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start08_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 5.0 | 0.8 | `1` | 2.663 | 2.595 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start08_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 5.0 | 0.8 | `3` | 2.761 | 2.695 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start08_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 5.0 | 0.8 | `6` | 2.853 | 2.789 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start08_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 5.0 | 0.8 | `all` | 2.990 | 2.924 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start02_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 10.0 | 0.2 | `1` | 2.618 | 2.552 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start02_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 10.0 | 0.2 | `3` | 2.670 | 2.605 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start02_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 10.0 | 0.2 | `6` | 2.776 | 2.708 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start02_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 10.0 | 0.2 | `all` | 2.894 | 2.828 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start04_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 10.0 | 0.4 | `1` | 2.669 | 2.601 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start04_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 10.0 | 0.4 | `3` | 2.686 | 2.617 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start04_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 10.0 | 0.4 | `6` | 2.820 | 2.753 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start04_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 10.0 | 0.4 | `all` | 2.948 | 2.875 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start06_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 10.0 | 0.6 | `1` | 2.634 | 2.565 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start06_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 10.0 | 0.6 | `3` | 2.770 | 2.703 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start06_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 10.0 | 0.6 | `6` | 2.859 | 2.789 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start06_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 10.0 | 0.6 | `all` | 2.994 | 2.925 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start08_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 10.0 | 0.8 | `1` | 2.638 | 2.570 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start08_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 10.0 | 0.8 | `3` | 2.806 | 2.731 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start08_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 10.0 | 0.8 | `6` | 2.903 | 2.835 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start08_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 10.0 | 0.8 | `all` | 3.003 | 2.932 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start02_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 15.0 | 0.2 | `1` | 2.646 | 2.571 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start02_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 15.0 | 0.2 | `3` | 2.686 | 2.616 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start02_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 15.0 | 0.2 | `6` | 2.773 | 2.699 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start02_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 15.0 | 0.2 | `all` | 2.933 | 2.861 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start04_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 15.0 | 0.4 | `1` | 2.634 | 2.565 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start04_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 15.0 | 0.4 | `3` | 2.715 | 2.642 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start04_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 15.0 | 0.4 | `6` | 2.812 | 2.733 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start04_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 15.0 | 0.4 | `all` | 2.960 | 2.886 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start06_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 15.0 | 0.6 | `1` | 2.633 | 2.559 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start06_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 15.0 | 0.6 | `3` | 2.774 | 2.698 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start06_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 15.0 | 0.6 | `6` | 2.837 | 2.764 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start06_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 15.0 | 0.6 | `all` | 2.981 | 2.910 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start08_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 15.0 | 0.8 | `1` | 2.662 | 2.590 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start08_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 15.0 | 0.8 | `3` | 2.799 | 2.727 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start08_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 15.0 | 0.8 | `6` | 2.869 | 2.800 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start08_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 15.0 | 0.8 | `all` | 3.080 | 3.005 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start02_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 20.0 | 0.2 | `1` | 2.611 | 2.538 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start02_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 20.0 | 0.2 | `3` | 2.711 | 2.638 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start02_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 20.0 | 0.2 | `6` | 2.758 | 2.687 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start02_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 20.0 | 0.2 | `all` | 2.885 | 2.811 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start04_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 20.0 | 0.4 | `1` | 2.667 | 2.596 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start04_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 20.0 | 0.4 | `3` | 2.733 | 2.659 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start04_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 20.0 | 0.4 | `6` | 2.795 | 2.724 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start04_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 20.0 | 0.4 | `all` | 2.993 | 2.919 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start06_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 20.0 | 0.6 | `1` | 2.633 | 2.561 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start06_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 20.0 | 0.6 | `3` | 2.746 | 2.672 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start06_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 20.0 | 0.6 | `6` | 2.839 | 2.763 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start06_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 20.0 | 0.6 | `all` | 2.983 | 2.913 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start08_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 20.0 | 0.8 | `1` | 2.674 | 2.602 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start08_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 20.0 | 0.8 | `3` | 2.804 | 2.736 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start08_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 20.0 | 0.8 | `6` | 2.881 | 2.809 |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start08_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 4 | 20.0 | 0.8 | `all` | 3.049 | 2.980 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start02_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 5.0 | 0.2 | `1` | 2.123 | 2.053 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start02_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 5.0 | 0.2 | `3` | 2.228 | 2.153 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start02_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 5.0 | 0.2 | `6` | 2.260 | 2.185 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start02_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 5.0 | 0.2 | `all` | 2.393 | 2.318 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start04_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 5.0 | 0.4 | `1` | 2.174 | 2.102 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start04_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 5.0 | 0.4 | `3` | 2.180 | 2.107 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start04_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 5.0 | 0.4 | `6` | 2.307 | 2.233 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start04_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 5.0 | 0.4 | `all` | 2.439 | 2.364 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start06_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 5.0 | 0.6 | `1` | 2.126 | 2.057 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start06_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 5.0 | 0.6 | `3` | 2.197 | 2.126 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start06_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 5.0 | 0.6 | `6` | 2.336 | 2.266 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start06_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 5.0 | 0.6 | `all` | 2.820 | 2.750 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start08_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 5.0 | 0.8 | `1` | 2.160 | 2.092 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start08_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 5.0 | 0.8 | `3` | 2.300 | 2.228 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start08_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 5.0 | 0.8 | `6` | 2.417 | 2.347 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start08_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 5.0 | 0.8 | `all` | 4.213 | 4.125 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start02_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 10.0 | 0.2 | `1` | 2.201 | 2.128 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start02_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 10.0 | 0.2 | `3` | 2.267 | 2.196 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start02_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 10.0 | 0.2 | `6` | 4.024 | 3.935 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start02_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 10.0 | 0.2 | `all` | 2.483 | 2.410 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start04_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 10.0 | 0.4 | `1` | 2.213 | 2.137 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start04_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 10.0 | 0.4 | `3` | 2.278 | 2.206 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start04_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 10.0 | 0.4 | `6` | 4.510 | 4.415 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start04_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 10.0 | 0.4 | `all` | 2.835 | 2.758 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start06_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 10.0 | 0.6 | `1` | 2.210 | 2.140 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start06_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 10.0 | 0.6 | `3` | 2.939 | 2.863 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start06_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 10.0 | 0.6 | `6` | 3.996 | 3.908 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start06_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 10.0 | 0.6 | `all` | 3.391 | 3.309 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start08_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 10.0 | 0.8 | `1` | 2.229 | 2.152 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start08_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 10.0 | 0.8 | `3` | 3.697 | 3.603 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start08_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 10.0 | 0.8 | `6` | 4.561 | 4.466 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start08_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 10.0 | 0.8 | `all` | 2.539 | 2.463 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start02_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 15.0 | 0.2 | `1` | 3.430 | 3.339 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start02_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 15.0 | 0.2 | `3` | 2.253 | 2.179 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start02_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 15.0 | 0.2 | `6` | 4.392 | 4.300 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start02_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 15.0 | 0.2 | `all` | 2.473 | 2.399 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start04_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 15.0 | 0.4 | `1` | 3.448 | 3.357 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start04_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 15.0 | 0.4 | `3` | 4.158 | 4.062 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start04_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 15.0 | 0.4 | `6` | 2.366 | 2.290 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start04_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 15.0 | 0.4 | `all` | 4.149 | 4.055 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start06_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 15.0 | 0.6 | `1` | 2.570 | 2.488 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start06_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 15.0 | 0.6 | `3` | 2.304 | 2.228 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start06_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 15.0 | 0.6 | `6` | 3.577 | 3.494 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start06_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 15.0 | 0.6 | `all` | 2.880 | 2.803 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start08_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 15.0 | 0.8 | `1` | 2.226 | 2.153 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start08_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 15.0 | 0.8 | `3` | 2.310 | 2.238 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start08_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 15.0 | 0.8 | `6` | 2.431 | 2.360 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start08_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 15.0 | 0.8 | `all` | 3.601 | 3.516 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start02_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 20.0 | 0.2 | `1` | 2.196 | 2.126 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start02_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 20.0 | 0.2 | `3` | 2.273 | 2.203 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start02_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 20.0 | 0.2 | `6` | 3.274 | 3.192 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start02_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 20.0 | 0.2 | `all` | 2.476 | 2.404 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start04_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 20.0 | 0.4 | `1` | 2.216 | 2.143 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start04_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 20.0 | 0.4 | `3` | 3.091 | 3.009 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start04_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 20.0 | 0.4 | `6` | 2.366 | 2.296 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start04_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 20.0 | 0.4 | `all` | 2.497 | 2.423 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start06_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 20.0 | 0.6 | `1` | 2.988 | 2.905 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start06_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 20.0 | 0.6 | `3` | 2.299 | 2.224 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start06_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 20.0 | 0.6 | `6` | 2.410 | 2.339 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start06_iterall` | `new_run` | `done` | `True` | 1/10 | 10.00 | 286 | 10 | 1300 | 3 | 20.0 | 0.6 | `all` | 2.539 | 2.467 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start08_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 20.0 | 0.8 | `1` | 2.228 | 2.154 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start08_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 20.0 | 0.8 | `3` | 3.146 | 3.063 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start08_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 20.0 | 0.8 | `6` | 2.428 | 2.357 |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start08_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 3 | 20.0 | 0.8 | `all` | 2.561 | 2.484 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start02_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 5.0 | 0.2 | `1` | 2.586 | 2.497 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start02_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 5.0 | 0.2 | `3` | 1.828 | 1.756 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start02_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 5.0 | 0.2 | `6` | 1.926 | 1.853 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start02_iterall` | `new_run` | `done` | `True` | 1/10 | 10.00 | 295 | 10 | 1300 | 2 | 5.0 | 0.2 | `all` | 2.734 | 2.649 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start04_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 5.0 | 0.4 | `1` | 1.774 | 1.701 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start04_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 5.0 | 0.4 | `3` | 1.838 | 1.760 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start04_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 5.0 | 0.4 | `6` | 2.602 | 2.520 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start04_iterall` | `new_run` | `done` | `True` | 1/10 | 10.00 | 295 | 10 | 1300 | 2 | 5.0 | 0.4 | `all` | 2.049 | 1.975 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start06_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 5.0 | 0.6 | `1` | 1.788 | 1.713 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start06_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 5.0 | 0.6 | `3` | 2.555 | 2.470 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start06_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 5.0 | 0.6 | `6` | 1.937 | 1.864 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start06_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 5.0 | 0.6 | `all` | 2.078 | 2.001 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start08_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 5.0 | 0.8 | `1` | 2.558 | 2.476 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start08_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 5.0 | 0.8 | `3` | 1.847 | 1.774 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start08_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 5.0 | 0.8 | `6` | 1.952 | 1.878 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start08_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 5.0 | 0.8 | `all` | 2.065 | 1.991 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start02_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 10.0 | 0.2 | `1` | 1.779 | 1.707 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start02_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 10.0 | 0.2 | `3` | 2.568 | 2.482 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start02_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 10.0 | 0.2 | `6` | 1.926 | 1.856 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start02_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 10.0 | 0.2 | `all` | 2.059 | 1.981 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start04_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 10.0 | 0.4 | `1` | 2.535 | 2.447 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start04_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 10.0 | 0.4 | `3` | 1.837 | 1.764 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start04_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 10.0 | 0.4 | `6` | 1.928 | 1.855 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start04_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 10.0 | 0.4 | `all` | 2.816 | 2.731 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start06_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 10.0 | 0.6 | `1` | 1.788 | 1.713 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start06_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 10.0 | 0.6 | `3` | 1.848 | 1.774 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start06_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 10.0 | 0.6 | `6` | 2.705 | 2.621 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start06_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 10.0 | 0.6 | `all` | 2.057 | 1.982 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start08_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 10.0 | 0.8 | `1` | 1.786 | 1.707 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start08_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 10.0 | 0.8 | `3` | 2.514 | 2.432 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start08_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 10.0 | 0.8 | `6` | 1.936 | 1.863 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start08_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 10.0 | 0.8 | `all` | 2.064 | 1.989 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start02_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 15.0 | 0.2 | `1` | 1.773 | 1.701 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start02_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 15.0 | 0.2 | `3` | 2.535 | 2.451 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start02_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 15.0 | 0.2 | `6` | 1.932 | 1.858 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start02_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 15.0 | 0.2 | `all` | 2.055 | 1.978 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start04_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 15.0 | 0.4 | `1` | 1.775 | 1.702 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start04_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 15.0 | 0.4 | `3` | 2.555 | 2.474 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start04_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 15.0 | 0.4 | `6` | 1.936 | 1.862 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start04_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 15.0 | 0.4 | `all` | 2.046 | 1.974 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start06_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 15.0 | 0.6 | `1` | 2.541 | 2.458 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start06_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 15.0 | 0.6 | `3` | 1.849 | 1.779 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start06_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 15.0 | 0.6 | `6` | 1.946 | 1.872 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start06_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 15.0 | 0.6 | `all` | 2.825 | 2.749 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start08_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 15.0 | 0.8 | `1` | 1.779 | 1.714 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start08_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 15.0 | 0.8 | `3` | 1.846 | 1.777 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start08_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 15.0 | 0.8 | `6` | 1.940 | 1.867 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start08_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 15.0 | 0.8 | `all` | 2.785 | 2.702 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start02_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 20.0 | 0.2 | `1` | 1.793 | 1.718 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start02_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 20.0 | 0.2 | `3` | 1.830 | 1.757 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start02_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 20.0 | 0.2 | `6` | 1.934 | 1.858 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start02_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 20.0 | 0.2 | `all` | 2.740 | 2.655 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start04_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 20.0 | 0.4 | `1` | 1.778 | 1.701 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start04_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 20.0 | 0.4 | `3` | 1.844 | 1.769 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start04_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 20.0 | 0.4 | `6` | 2.647 | 2.565 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start04_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 20.0 | 0.4 | `all` | 2.057 | 1.982 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start06_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 20.0 | 0.6 | `1` | 1.793 | 1.718 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start06_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 20.0 | 0.6 | `3` | 2.495 | 2.412 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start06_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 20.0 | 0.6 | `6` | 1.936 | 1.866 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start06_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 20.0 | 0.6 | `all` | 2.076 | 1.996 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start08_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 20.0 | 0.8 | `1` | 2.505 | 2.420 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start08_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 20.0 | 0.8 | `3` | 1.862 | 1.777 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start08_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 20.0 | 0.8 | `6` | 1.936 | 1.862 |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start08_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 2 | 20.0 | 0.8 | `all` | 1.967 | 1.889 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start02_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 5.0 | 0.2 | `1` | 1.651 | 1.577 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start02_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 5.0 | 0.2 | `3` | 1.848 | 1.756 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start02_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 5.0 | 0.2 | `6` | 1.805 | 1.727 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start02_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 5.0 | 0.2 | `all` | 6.345 | 6.206 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start04_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 5.0 | 0.4 | `1` | 1.644 | 1.562 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start04_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 5.0 | 0.4 | `3` | 1.701 | 1.628 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start04_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 5.0 | 0.4 | `6` | 1.785 | 1.715 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start04_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 5.0 | 0.4 | `all` | 1.877 | 1.800 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start06_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 5.0 | 0.6 | `1` | 1.666 | 1.578 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start06_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 5.0 | 0.6 | `3` | 1.711 | 1.635 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start06_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 5.0 | 0.6 | `6` | 1.755 | 1.679 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start06_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 5.0 | 0.6 | `all` | 1.936 | 1.853 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start08_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 5.0 | 0.8 | `1` | 8.910 | 8.711 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start08_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 5.0 | 0.8 | `3` | 1.693 | 1.621 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start08_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 5.0 | 0.8 | `6` | 1.753 | 1.679 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start08_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 5.0 | 0.8 | `all` | 1.934 | 1.856 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start02_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 10.0 | 0.2 | `1` | 1.646 | 1.565 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start02_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 10.0 | 0.2 | `3` | 1.664 | 1.593 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start02_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 10.0 | 0.2 | `6` | 1.804 | 1.728 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start02_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 10.0 | 0.2 | `all` | 1.940 | 1.862 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start04_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 10.0 | 0.4 | `1` | 1.601 | 1.531 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start04_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 548 | 10 | 1300 | 1 | 10.0 | 0.4 | `3` | 3.889 | 3.765 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start04_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 10.0 | 0.4 | `6` | 1.800 | 1.728 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start04_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 10.0 | 0.4 | `all` | 1.867 | 1.798 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start06_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 10.0 | 0.6 | `1` | 1.641 | 1.568 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start06_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 463 | 10 | 1300 | 1 | 10.0 | 0.6 | `3` | 2.382 | 2.292 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start06_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 441 | 10 | 1300 | 1 | 10.0 | 0.6 | `6` | 1.860 | 1.778 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start06_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 396 | 10 | 1300 | 1 | 10.0 | 0.6 | `all` | 2.019 | 1.929 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start08_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 10.0 | 0.8 | `1` | 2.379 | 2.276 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start08_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 10.0 | 0.8 | `3` | 2.723 | 2.622 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start08_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 10.0 | 0.8 | `6` | 1.783 | 1.698 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start08_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 10.0 | 0.8 | `all` | 2.051 | 1.953 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start02_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 15.0 | 0.2 | `1` | 1.642 | 1.554 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start02_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 15.0 | 0.2 | `3` | 2.519 | 2.414 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start02_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 15.0 | 0.2 | `6` | 2.923 | 2.825 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start02_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 15.0 | 0.2 | `all` | 2.054 | 1.964 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start04_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 15.0 | 0.4 | `1` | 1.633 | 1.548 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start04_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 15.0 | 0.4 | `3` | 2.516 | 2.419 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start04_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 15.0 | 0.4 | `6` | 2.911 | 2.810 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start04_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 15.0 | 0.4 | `all` | 1.897 | 1.815 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start06_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 15.0 | 0.6 | `1` | 1.766 | 1.681 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start06_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 15.0 | 0.6 | `3` | 2.453 | 2.351 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start06_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 15.0 | 0.6 | `6` | 2.937 | 2.839 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start06_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 15.0 | 0.6 | `all` | 1.908 | 1.827 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start08_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 15.0 | 0.8 | `1` | 1.779 | 1.686 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start08_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 15.0 | 0.8 | `3` | 2.423 | 2.328 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start08_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 15.0 | 0.8 | `6` | 1.783 | 1.696 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start08_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 15.0 | 0.8 | `all` | 2.067 | 1.972 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start02_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 20.0 | 0.2 | `1` | 2.588 | 2.489 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start02_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 20.0 | 0.2 | `3` | 2.455 | 2.365 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start02_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 20.0 | 0.2 | `6` | 1.779 | 1.700 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start02_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 20.0 | 0.2 | `all` | 2.045 | 1.965 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start04_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 20.0 | 0.4 | `1` | 2.576 | 2.478 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start04_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 20.0 | 0.4 | `3` | 1.690 | 1.612 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start04_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 20.0 | 0.4 | `6` | 2.677 | 2.583 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start04_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 20.0 | 0.4 | `all` | 2.040 | 1.949 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start06_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 20.0 | 0.6 | `1` | 2.544 | 2.447 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start06_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 20.0 | 0.6 | `3` | 1.697 | 1.611 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start06_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 20.0 | 0.6 | `6` | 1.932 | 1.841 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start06_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 20.0 | 0.6 | `all` | 2.904 | 2.807 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start08_iter1` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 20.0 | 0.8 | `1` | 2.581 | 2.481 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start08_iter3` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 20.0 | 0.8 | `3` | 1.689 | 1.605 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start08_iter6` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 20.0 | 0.8 | `6` | 1.904 | 1.820 |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start08_iterall` | `new_run` | `done` | `True` | 0/10 | 0.00 | 300 | 10 | 1300 | 1 | 20.0 | 0.8 | `all` | 2.889 | 2.807 |  |

## SR Comparison

| Method | Source | Success | SR | Delta vs RDT unguided | Delta vs EDS IID baseline |
| --- | --- | ---: | ---: | ---: | ---: |
| `rdt_unguided` | `referenced_level4` | 0/10 | 0.00 | 0.00 | 0.00 |
| `eds_iid_baseline` | `referenced_level4` | 0/10 | 0.00 | 0.00 | 0.00 |
| `eds_rbf_init_s20_start08` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start02_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start02_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start02_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start02_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start04_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start04_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start04_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start04_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start06_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start06_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start06_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start08_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start08_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start08_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start08_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start02_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start02_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start02_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start02_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start04_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start04_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start04_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start04_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start06_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start06_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start06_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start06_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start08_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start08_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start08_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start08_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start02_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start02_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start02_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start02_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start04_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start04_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start04_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start04_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start06_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start06_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start06_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start06_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start08_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start08_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start08_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start08_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start02_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start02_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start02_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start02_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start04_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start04_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start04_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start04_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start06_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start06_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start06_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start06_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start08_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start08_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start08_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start08_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start02_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start02_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start02_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start02_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start04_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start04_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start04_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start04_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start06_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start06_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start06_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start06_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start08_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start08_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start08_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start08_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start02_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start02_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start02_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start02_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start04_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start04_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start04_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start04_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start06_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start06_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start06_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start06_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start08_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start08_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start08_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start08_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start02_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start02_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start02_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start02_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start04_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start04_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start04_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start04_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start06_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start06_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start06_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start06_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start08_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start08_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start08_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start08_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start02_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start02_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start02_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start02_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start04_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start04_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start04_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start04_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start06_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start06_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start06_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start06_iterall` | `new_run` | 1/10 | 10.00 | 10.00 | 10.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start08_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start08_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start08_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start08_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start02_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start02_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start02_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start02_iterall` | `new_run` | 1/10 | 10.00 | 10.00 | 10.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start04_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start04_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start04_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start04_iterall` | `new_run` | 1/10 | 10.00 | 10.00 | 10.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start06_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start06_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start06_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start06_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start08_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start08_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start08_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start08_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start02_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start02_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start02_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start02_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start04_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start04_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start04_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start04_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start06_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start06_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start06_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start06_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start08_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start08_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start08_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start08_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start02_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start02_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start02_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start02_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start04_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start04_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start04_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start04_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start06_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start06_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start06_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start06_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start08_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start08_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start08_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start08_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start02_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start02_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start02_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start02_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start04_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start04_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start04_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start04_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start06_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start06_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start06_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start06_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start08_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start08_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start08_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start08_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start02_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start02_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start02_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start02_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start04_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start04_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start04_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start04_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start06_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start06_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start06_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start06_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start08_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start08_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start08_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start08_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start02_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start02_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start02_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start02_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start04_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start04_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start04_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start04_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start06_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start06_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start06_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start06_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start08_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start08_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start08_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start08_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start02_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start02_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start02_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start02_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start04_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start04_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start04_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start04_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start06_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start06_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start06_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start06_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start08_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start08_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start08_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start08_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start02_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start02_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start02_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start02_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start04_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start04_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start04_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start04_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start06_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start06_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start06_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start06_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start08_iter1` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start08_iter3` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start08_iter6` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start08_iterall` | `new_run` | 0/10 | 0.00 | 0.00 | 0.00 |

## Aggregated Analysis

- Expected jobs: `257`.
- Jobs with result files: `257`.
- Jobs passing validity gate: `256`.
- Best observed setting: `rbf_s20_start08_rt2to1_rollrbf_s5_start02_iterall` with `1/10` (`10.00` SR).

## Safety/Validity Gate

| Method | Valid | Strict | Suite | Videos | Metrics | Qualitative | Failure Reason |
| --- | --- | --- | --- | ---: | ---: | --- | --- |
| `eds_rbf_init_s20_start08` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start02_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start02_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start02_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start02_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start04_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start04_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start04_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start04_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start06_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start06_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start06_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start06_iterall` | `False` | Strict perturbation verified | suite verified | 9 | 876 | present | videos 9/10 |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start08_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start08_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start08_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s5_start08_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start02_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start02_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start02_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start02_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start04_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start04_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start04_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start04_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start06_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start06_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start06_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start06_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start08_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start08_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start08_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s10_start08_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start02_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start02_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start02_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start02_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start04_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start04_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start04_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start04_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start06_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start06_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start06_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start06_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start08_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start08_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start08_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s15_start08_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start02_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start02_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start02_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start02_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start04_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start04_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start04_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start04_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start06_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start06_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start06_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start06_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start08_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start08_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start08_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt4to1_rollrbf_s20_start08_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start02_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start02_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start02_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start02_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start04_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start04_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start04_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start04_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start06_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start06_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start06_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start06_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start08_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start08_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start08_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s5_start08_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start02_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start02_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start02_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start02_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start04_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start04_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start04_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start04_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start06_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start06_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start06_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start06_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start08_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start08_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start08_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s10_start08_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start02_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start02_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start02_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start02_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start04_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start04_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start04_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start04_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start06_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start06_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start06_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start06_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start08_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start08_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start08_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s15_start08_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start02_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start02_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start02_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start02_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start04_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start04_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start04_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start04_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start06_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start06_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start06_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start06_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 286 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start08_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start08_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start08_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt3to1_rollrbf_s20_start08_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start02_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start02_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start02_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start02_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 295 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start04_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start04_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start04_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start04_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 295 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start06_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start06_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start06_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start06_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start08_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start08_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start08_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s5_start08_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start02_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start02_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start02_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start02_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start04_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start04_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start04_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start04_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start06_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start06_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start06_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start06_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start08_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start08_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start08_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s10_start08_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start02_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start02_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start02_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start02_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start04_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start04_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start04_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start04_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start06_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start06_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start06_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start06_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start08_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start08_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start08_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s15_start08_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start02_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start02_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start02_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start02_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start04_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start04_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start04_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start04_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start06_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start06_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start06_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start06_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start08_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start08_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start08_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt2to1_rollrbf_s20_start08_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start02_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start02_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start02_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start02_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start04_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start04_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start04_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start04_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start06_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start06_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start06_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start06_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start08_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start08_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start08_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s5_start08_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start02_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start02_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start02_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start02_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start04_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start04_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 548 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start04_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start04_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start06_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start06_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 463 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start06_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 441 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start06_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 396 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start08_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start08_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start08_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s10_start08_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start02_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start02_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start02_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start02_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start04_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start04_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start04_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start04_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start06_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start06_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start06_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start06_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start08_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start08_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start08_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s15_start08_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start02_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start02_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start02_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start02_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start04_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start04_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start04_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start04_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start06_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start06_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start06_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start06_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start08_iter1` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start08_iter3` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start08_iter6` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |
| `rbf_s20_start08_rt1to1_rollrbf_s20_start08_iterall` | `True` | Strict perturbation verified | suite verified | 10 | 300 | present |  |

## Conclusion

At least one validated RBF run improves over the referenced EDS IID baseline on object-swap OOD.

## Output Index

- `eds_rbf_init_s20_start08`: output `outputs/ood_eval/level4_libero_object_swap_eds_rbf_init_s20_start08`, metrics `outputs/ood_eval/level4_libero_object_swap_eds_rbf_init_s20_start08/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_eds_rbf_init_s20_start08.log`
- `rbf_s20_start08_rt4to1_rollrbf_s5_start02_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start02_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start02_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start02_iter1.log`
- `rbf_s20_start08_rt4to1_rollrbf_s5_start02_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start02_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start02_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start02_iter3.log`
- `rbf_s20_start08_rt4to1_rollrbf_s5_start02_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start02_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start02_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start02_iter6.log`
- `rbf_s20_start08_rt4to1_rollrbf_s5_start02_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start02_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start02_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start02_iterall.log`
- `rbf_s20_start08_rt4to1_rollrbf_s5_start04_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start04_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start04_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start04_iter1.log`
- `rbf_s20_start08_rt4to1_rollrbf_s5_start04_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start04_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start04_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start04_iter3.log`
- `rbf_s20_start08_rt4to1_rollrbf_s5_start04_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start04_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start04_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start04_iter6.log`
- `rbf_s20_start08_rt4to1_rollrbf_s5_start04_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start04_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start04_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start04_iterall.log`
- `rbf_s20_start08_rt4to1_rollrbf_s5_start06_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start06_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start06_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start06_iter1.log`
- `rbf_s20_start08_rt4to1_rollrbf_s5_start06_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start06_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start06_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start06_iter3.log`
- `rbf_s20_start08_rt4to1_rollrbf_s5_start06_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start06_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start06_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start06_iter6.log`
- `rbf_s20_start08_rt4to1_rollrbf_s5_start06_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start06_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start06_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start06_iterall.log`
- `rbf_s20_start08_rt4to1_rollrbf_s5_start08_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start08_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start08_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start08_iter1.log`
- `rbf_s20_start08_rt4to1_rollrbf_s5_start08_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start08_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start08_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start08_iter3.log`
- `rbf_s20_start08_rt4to1_rollrbf_s5_start08_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start08_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start08_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start08_iter6.log`
- `rbf_s20_start08_rt4to1_rollrbf_s5_start08_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start08_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start08_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s5_start08_iterall.log`
- `rbf_s20_start08_rt4to1_rollrbf_s10_start02_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start02_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start02_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start02_iter1.log`
- `rbf_s20_start08_rt4to1_rollrbf_s10_start02_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start02_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start02_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start02_iter3.log`
- `rbf_s20_start08_rt4to1_rollrbf_s10_start02_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start02_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start02_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start02_iter6.log`
- `rbf_s20_start08_rt4to1_rollrbf_s10_start02_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start02_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start02_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start02_iterall.log`
- `rbf_s20_start08_rt4to1_rollrbf_s10_start04_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start04_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start04_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start04_iter1.log`
- `rbf_s20_start08_rt4to1_rollrbf_s10_start04_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start04_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start04_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start04_iter3.log`
- `rbf_s20_start08_rt4to1_rollrbf_s10_start04_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start04_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start04_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start04_iter6.log`
- `rbf_s20_start08_rt4to1_rollrbf_s10_start04_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start04_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start04_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start04_iterall.log`
- `rbf_s20_start08_rt4to1_rollrbf_s10_start06_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start06_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start06_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start06_iter1.log`
- `rbf_s20_start08_rt4to1_rollrbf_s10_start06_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start06_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start06_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start06_iter3.log`
- `rbf_s20_start08_rt4to1_rollrbf_s10_start06_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start06_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start06_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start06_iter6.log`
- `rbf_s20_start08_rt4to1_rollrbf_s10_start06_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start06_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start06_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start06_iterall.log`
- `rbf_s20_start08_rt4to1_rollrbf_s10_start08_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start08_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start08_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start08_iter1.log`
- `rbf_s20_start08_rt4to1_rollrbf_s10_start08_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start08_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start08_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start08_iter3.log`
- `rbf_s20_start08_rt4to1_rollrbf_s10_start08_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start08_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start08_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start08_iter6.log`
- `rbf_s20_start08_rt4to1_rollrbf_s10_start08_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start08_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start08_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s10_start08_iterall.log`
- `rbf_s20_start08_rt4to1_rollrbf_s15_start02_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start02_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start02_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start02_iter1.log`
- `rbf_s20_start08_rt4to1_rollrbf_s15_start02_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start02_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start02_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start02_iter3.log`
- `rbf_s20_start08_rt4to1_rollrbf_s15_start02_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start02_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start02_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start02_iter6.log`
- `rbf_s20_start08_rt4to1_rollrbf_s15_start02_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start02_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start02_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start02_iterall.log`
- `rbf_s20_start08_rt4to1_rollrbf_s15_start04_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start04_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start04_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start04_iter1.log`
- `rbf_s20_start08_rt4to1_rollrbf_s15_start04_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start04_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start04_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start04_iter3.log`
- `rbf_s20_start08_rt4to1_rollrbf_s15_start04_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start04_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start04_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start04_iter6.log`
- `rbf_s20_start08_rt4to1_rollrbf_s15_start04_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start04_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start04_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start04_iterall.log`
- `rbf_s20_start08_rt4to1_rollrbf_s15_start06_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start06_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start06_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start06_iter1.log`
- `rbf_s20_start08_rt4to1_rollrbf_s15_start06_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start06_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start06_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start06_iter3.log`
- `rbf_s20_start08_rt4to1_rollrbf_s15_start06_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start06_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start06_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start06_iter6.log`
- `rbf_s20_start08_rt4to1_rollrbf_s15_start06_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start06_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start06_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start06_iterall.log`
- `rbf_s20_start08_rt4to1_rollrbf_s15_start08_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start08_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start08_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start08_iter1.log`
- `rbf_s20_start08_rt4to1_rollrbf_s15_start08_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start08_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start08_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start08_iter3.log`
- `rbf_s20_start08_rt4to1_rollrbf_s15_start08_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start08_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start08_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start08_iter6.log`
- `rbf_s20_start08_rt4to1_rollrbf_s15_start08_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start08_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start08_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s15_start08_iterall.log`
- `rbf_s20_start08_rt4to1_rollrbf_s20_start02_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start02_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start02_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start02_iter1.log`
- `rbf_s20_start08_rt4to1_rollrbf_s20_start02_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start02_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start02_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start02_iter3.log`
- `rbf_s20_start08_rt4to1_rollrbf_s20_start02_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start02_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start02_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start02_iter6.log`
- `rbf_s20_start08_rt4to1_rollrbf_s20_start02_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start02_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start02_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start02_iterall.log`
- `rbf_s20_start08_rt4to1_rollrbf_s20_start04_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start04_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start04_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start04_iter1.log`
- `rbf_s20_start08_rt4to1_rollrbf_s20_start04_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start04_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start04_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start04_iter3.log`
- `rbf_s20_start08_rt4to1_rollrbf_s20_start04_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start04_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start04_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start04_iter6.log`
- `rbf_s20_start08_rt4to1_rollrbf_s20_start04_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start04_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start04_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start04_iterall.log`
- `rbf_s20_start08_rt4to1_rollrbf_s20_start06_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start06_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start06_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start06_iter1.log`
- `rbf_s20_start08_rt4to1_rollrbf_s20_start06_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start06_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start06_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start06_iter3.log`
- `rbf_s20_start08_rt4to1_rollrbf_s20_start06_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start06_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start06_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start06_iter6.log`
- `rbf_s20_start08_rt4to1_rollrbf_s20_start06_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start06_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start06_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start06_iterall.log`
- `rbf_s20_start08_rt4to1_rollrbf_s20_start08_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start08_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start08_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start08_iter1.log`
- `rbf_s20_start08_rt4to1_rollrbf_s20_start08_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start08_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start08_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start08_iter3.log`
- `rbf_s20_start08_rt4to1_rollrbf_s20_start08_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start08_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start08_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start08_iter6.log`
- `rbf_s20_start08_rt4to1_rollrbf_s20_start08_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start08_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start08_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt4to1_rollrbf_s20_start08_iterall.log`
- `rbf_s20_start08_rt3to1_rollrbf_s5_start02_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start02_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start02_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start02_iter1.log`
- `rbf_s20_start08_rt3to1_rollrbf_s5_start02_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start02_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start02_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start02_iter3.log`
- `rbf_s20_start08_rt3to1_rollrbf_s5_start02_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start02_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start02_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start02_iter6.log`
- `rbf_s20_start08_rt3to1_rollrbf_s5_start02_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start02_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start02_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start02_iterall.log`
- `rbf_s20_start08_rt3to1_rollrbf_s5_start04_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start04_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start04_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start04_iter1.log`
- `rbf_s20_start08_rt3to1_rollrbf_s5_start04_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start04_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start04_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start04_iter3.log`
- `rbf_s20_start08_rt3to1_rollrbf_s5_start04_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start04_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start04_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start04_iter6.log`
- `rbf_s20_start08_rt3to1_rollrbf_s5_start04_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start04_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start04_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start04_iterall.log`
- `rbf_s20_start08_rt3to1_rollrbf_s5_start06_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start06_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start06_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start06_iter1.log`
- `rbf_s20_start08_rt3to1_rollrbf_s5_start06_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start06_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start06_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start06_iter3.log`
- `rbf_s20_start08_rt3to1_rollrbf_s5_start06_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start06_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start06_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start06_iter6.log`
- `rbf_s20_start08_rt3to1_rollrbf_s5_start06_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start06_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start06_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start06_iterall.log`
- `rbf_s20_start08_rt3to1_rollrbf_s5_start08_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start08_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start08_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start08_iter1.log`
- `rbf_s20_start08_rt3to1_rollrbf_s5_start08_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start08_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start08_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start08_iter3.log`
- `rbf_s20_start08_rt3to1_rollrbf_s5_start08_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start08_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start08_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start08_iter6.log`
- `rbf_s20_start08_rt3to1_rollrbf_s5_start08_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start08_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start08_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s5_start08_iterall.log`
- `rbf_s20_start08_rt3to1_rollrbf_s10_start02_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start02_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start02_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start02_iter1.log`
- `rbf_s20_start08_rt3to1_rollrbf_s10_start02_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start02_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start02_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start02_iter3.log`
- `rbf_s20_start08_rt3to1_rollrbf_s10_start02_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start02_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start02_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start02_iter6.log`
- `rbf_s20_start08_rt3to1_rollrbf_s10_start02_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start02_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start02_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start02_iterall.log`
- `rbf_s20_start08_rt3to1_rollrbf_s10_start04_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start04_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start04_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start04_iter1.log`
- `rbf_s20_start08_rt3to1_rollrbf_s10_start04_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start04_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start04_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start04_iter3.log`
- `rbf_s20_start08_rt3to1_rollrbf_s10_start04_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start04_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start04_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start04_iter6.log`
- `rbf_s20_start08_rt3to1_rollrbf_s10_start04_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start04_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start04_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start04_iterall.log`
- `rbf_s20_start08_rt3to1_rollrbf_s10_start06_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start06_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start06_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start06_iter1.log`
- `rbf_s20_start08_rt3to1_rollrbf_s10_start06_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start06_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start06_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start06_iter3.log`
- `rbf_s20_start08_rt3to1_rollrbf_s10_start06_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start06_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start06_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start06_iter6.log`
- `rbf_s20_start08_rt3to1_rollrbf_s10_start06_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start06_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start06_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start06_iterall.log`
- `rbf_s20_start08_rt3to1_rollrbf_s10_start08_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start08_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start08_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start08_iter1.log`
- `rbf_s20_start08_rt3to1_rollrbf_s10_start08_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start08_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start08_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start08_iter3.log`
- `rbf_s20_start08_rt3to1_rollrbf_s10_start08_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start08_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start08_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start08_iter6.log`
- `rbf_s20_start08_rt3to1_rollrbf_s10_start08_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start08_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start08_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s10_start08_iterall.log`
- `rbf_s20_start08_rt3to1_rollrbf_s15_start02_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start02_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start02_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start02_iter1.log`
- `rbf_s20_start08_rt3to1_rollrbf_s15_start02_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start02_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start02_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start02_iter3.log`
- `rbf_s20_start08_rt3to1_rollrbf_s15_start02_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start02_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start02_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start02_iter6.log`
- `rbf_s20_start08_rt3to1_rollrbf_s15_start02_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start02_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start02_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start02_iterall.log`
- `rbf_s20_start08_rt3to1_rollrbf_s15_start04_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start04_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start04_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start04_iter1.log`
- `rbf_s20_start08_rt3to1_rollrbf_s15_start04_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start04_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start04_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start04_iter3.log`
- `rbf_s20_start08_rt3to1_rollrbf_s15_start04_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start04_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start04_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start04_iter6.log`
- `rbf_s20_start08_rt3to1_rollrbf_s15_start04_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start04_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start04_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start04_iterall.log`
- `rbf_s20_start08_rt3to1_rollrbf_s15_start06_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start06_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start06_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start06_iter1.log`
- `rbf_s20_start08_rt3to1_rollrbf_s15_start06_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start06_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start06_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start06_iter3.log`
- `rbf_s20_start08_rt3to1_rollrbf_s15_start06_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start06_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start06_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start06_iter6.log`
- `rbf_s20_start08_rt3to1_rollrbf_s15_start06_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start06_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start06_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start06_iterall.log`
- `rbf_s20_start08_rt3to1_rollrbf_s15_start08_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start08_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start08_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start08_iter1.log`
- `rbf_s20_start08_rt3to1_rollrbf_s15_start08_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start08_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start08_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start08_iter3.log`
- `rbf_s20_start08_rt3to1_rollrbf_s15_start08_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start08_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start08_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start08_iter6.log`
- `rbf_s20_start08_rt3to1_rollrbf_s15_start08_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start08_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start08_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s15_start08_iterall.log`
- `rbf_s20_start08_rt3to1_rollrbf_s20_start02_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start02_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start02_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start02_iter1.log`
- `rbf_s20_start08_rt3to1_rollrbf_s20_start02_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start02_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start02_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start02_iter3.log`
- `rbf_s20_start08_rt3to1_rollrbf_s20_start02_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start02_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start02_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start02_iter6.log`
- `rbf_s20_start08_rt3to1_rollrbf_s20_start02_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start02_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start02_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start02_iterall.log`
- `rbf_s20_start08_rt3to1_rollrbf_s20_start04_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start04_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start04_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start04_iter1.log`
- `rbf_s20_start08_rt3to1_rollrbf_s20_start04_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start04_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start04_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start04_iter3.log`
- `rbf_s20_start08_rt3to1_rollrbf_s20_start04_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start04_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start04_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start04_iter6.log`
- `rbf_s20_start08_rt3to1_rollrbf_s20_start04_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start04_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start04_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start04_iterall.log`
- `rbf_s20_start08_rt3to1_rollrbf_s20_start06_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start06_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start06_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start06_iter1.log`
- `rbf_s20_start08_rt3to1_rollrbf_s20_start06_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start06_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start06_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start06_iter3.log`
- `rbf_s20_start08_rt3to1_rollrbf_s20_start06_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start06_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start06_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start06_iter6.log`
- `rbf_s20_start08_rt3to1_rollrbf_s20_start06_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start06_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start06_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start06_iterall.log`
- `rbf_s20_start08_rt3to1_rollrbf_s20_start08_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start08_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start08_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start08_iter1.log`
- `rbf_s20_start08_rt3to1_rollrbf_s20_start08_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start08_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start08_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start08_iter3.log`
- `rbf_s20_start08_rt3to1_rollrbf_s20_start08_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start08_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start08_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start08_iter6.log`
- `rbf_s20_start08_rt3to1_rollrbf_s20_start08_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start08_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start08_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start08_iterall.log`
- `rbf_s20_start08_rt2to1_rollrbf_s5_start02_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start02_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start02_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start02_iter1.log`
- `rbf_s20_start08_rt2to1_rollrbf_s5_start02_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start02_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start02_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start02_iter3.log`
- `rbf_s20_start08_rt2to1_rollrbf_s5_start02_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start02_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start02_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start02_iter6.log`
- `rbf_s20_start08_rt2to1_rollrbf_s5_start02_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start02_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start02_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start02_iterall.log`
- `rbf_s20_start08_rt2to1_rollrbf_s5_start04_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start04_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start04_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start04_iter1.log`
- `rbf_s20_start08_rt2to1_rollrbf_s5_start04_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start04_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start04_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start04_iter3.log`
- `rbf_s20_start08_rt2to1_rollrbf_s5_start04_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start04_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start04_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start04_iter6.log`
- `rbf_s20_start08_rt2to1_rollrbf_s5_start04_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start04_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start04_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start04_iterall.log`
- `rbf_s20_start08_rt2to1_rollrbf_s5_start06_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start06_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start06_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start06_iter1.log`
- `rbf_s20_start08_rt2to1_rollrbf_s5_start06_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start06_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start06_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start06_iter3.log`
- `rbf_s20_start08_rt2to1_rollrbf_s5_start06_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start06_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start06_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start06_iter6.log`
- `rbf_s20_start08_rt2to1_rollrbf_s5_start06_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start06_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start06_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start06_iterall.log`
- `rbf_s20_start08_rt2to1_rollrbf_s5_start08_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start08_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start08_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start08_iter1.log`
- `rbf_s20_start08_rt2to1_rollrbf_s5_start08_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start08_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start08_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start08_iter3.log`
- `rbf_s20_start08_rt2to1_rollrbf_s5_start08_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start08_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start08_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start08_iter6.log`
- `rbf_s20_start08_rt2to1_rollrbf_s5_start08_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start08_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start08_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start08_iterall.log`
- `rbf_s20_start08_rt2to1_rollrbf_s10_start02_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start02_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start02_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start02_iter1.log`
- `rbf_s20_start08_rt2to1_rollrbf_s10_start02_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start02_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start02_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start02_iter3.log`
- `rbf_s20_start08_rt2to1_rollrbf_s10_start02_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start02_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start02_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start02_iter6.log`
- `rbf_s20_start08_rt2to1_rollrbf_s10_start02_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start02_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start02_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start02_iterall.log`
- `rbf_s20_start08_rt2to1_rollrbf_s10_start04_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start04_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start04_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start04_iter1.log`
- `rbf_s20_start08_rt2to1_rollrbf_s10_start04_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start04_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start04_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start04_iter3.log`
- `rbf_s20_start08_rt2to1_rollrbf_s10_start04_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start04_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start04_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start04_iter6.log`
- `rbf_s20_start08_rt2to1_rollrbf_s10_start04_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start04_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start04_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start04_iterall.log`
- `rbf_s20_start08_rt2to1_rollrbf_s10_start06_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start06_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start06_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start06_iter1.log`
- `rbf_s20_start08_rt2to1_rollrbf_s10_start06_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start06_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start06_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start06_iter3.log`
- `rbf_s20_start08_rt2to1_rollrbf_s10_start06_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start06_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start06_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start06_iter6.log`
- `rbf_s20_start08_rt2to1_rollrbf_s10_start06_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start06_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start06_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start06_iterall.log`
- `rbf_s20_start08_rt2to1_rollrbf_s10_start08_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start08_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start08_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start08_iter1.log`
- `rbf_s20_start08_rt2to1_rollrbf_s10_start08_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start08_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start08_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start08_iter3.log`
- `rbf_s20_start08_rt2to1_rollrbf_s10_start08_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start08_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start08_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start08_iter6.log`
- `rbf_s20_start08_rt2to1_rollrbf_s10_start08_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start08_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start08_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s10_start08_iterall.log`
- `rbf_s20_start08_rt2to1_rollrbf_s15_start02_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start02_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start02_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start02_iter1.log`
- `rbf_s20_start08_rt2to1_rollrbf_s15_start02_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start02_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start02_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start02_iter3.log`
- `rbf_s20_start08_rt2to1_rollrbf_s15_start02_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start02_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start02_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start02_iter6.log`
- `rbf_s20_start08_rt2to1_rollrbf_s15_start02_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start02_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start02_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start02_iterall.log`
- `rbf_s20_start08_rt2to1_rollrbf_s15_start04_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start04_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start04_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start04_iter1.log`
- `rbf_s20_start08_rt2to1_rollrbf_s15_start04_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start04_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start04_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start04_iter3.log`
- `rbf_s20_start08_rt2to1_rollrbf_s15_start04_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start04_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start04_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start04_iter6.log`
- `rbf_s20_start08_rt2to1_rollrbf_s15_start04_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start04_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start04_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start04_iterall.log`
- `rbf_s20_start08_rt2to1_rollrbf_s15_start06_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start06_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start06_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start06_iter1.log`
- `rbf_s20_start08_rt2to1_rollrbf_s15_start06_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start06_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start06_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start06_iter3.log`
- `rbf_s20_start08_rt2to1_rollrbf_s15_start06_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start06_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start06_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start06_iter6.log`
- `rbf_s20_start08_rt2to1_rollrbf_s15_start06_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start06_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start06_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start06_iterall.log`
- `rbf_s20_start08_rt2to1_rollrbf_s15_start08_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start08_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start08_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start08_iter1.log`
- `rbf_s20_start08_rt2to1_rollrbf_s15_start08_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start08_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start08_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start08_iter3.log`
- `rbf_s20_start08_rt2to1_rollrbf_s15_start08_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start08_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start08_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start08_iter6.log`
- `rbf_s20_start08_rt2to1_rollrbf_s15_start08_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start08_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start08_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s15_start08_iterall.log`
- `rbf_s20_start08_rt2to1_rollrbf_s20_start02_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start02_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start02_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start02_iter1.log`
- `rbf_s20_start08_rt2to1_rollrbf_s20_start02_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start02_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start02_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start02_iter3.log`
- `rbf_s20_start08_rt2to1_rollrbf_s20_start02_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start02_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start02_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start02_iter6.log`
- `rbf_s20_start08_rt2to1_rollrbf_s20_start02_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start02_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start02_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start02_iterall.log`
- `rbf_s20_start08_rt2to1_rollrbf_s20_start04_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start04_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start04_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start04_iter1.log`
- `rbf_s20_start08_rt2to1_rollrbf_s20_start04_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start04_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start04_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start04_iter3.log`
- `rbf_s20_start08_rt2to1_rollrbf_s20_start04_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start04_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start04_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start04_iter6.log`
- `rbf_s20_start08_rt2to1_rollrbf_s20_start04_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start04_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start04_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start04_iterall.log`
- `rbf_s20_start08_rt2to1_rollrbf_s20_start06_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start06_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start06_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start06_iter1.log`
- `rbf_s20_start08_rt2to1_rollrbf_s20_start06_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start06_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start06_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start06_iter3.log`
- `rbf_s20_start08_rt2to1_rollrbf_s20_start06_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start06_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start06_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start06_iter6.log`
- `rbf_s20_start08_rt2to1_rollrbf_s20_start06_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start06_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start06_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start06_iterall.log`
- `rbf_s20_start08_rt2to1_rollrbf_s20_start08_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start08_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start08_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start08_iter1.log`
- `rbf_s20_start08_rt2to1_rollrbf_s20_start08_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start08_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start08_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start08_iter3.log`
- `rbf_s20_start08_rt2to1_rollrbf_s20_start08_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start08_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start08_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start08_iter6.log`
- `rbf_s20_start08_rt2to1_rollrbf_s20_start08_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start08_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start08_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s20_start08_iterall.log`
- `rbf_s20_start08_rt1to1_rollrbf_s5_start02_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start02_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start02_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start02_iter1.log`
- `rbf_s20_start08_rt1to1_rollrbf_s5_start02_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start02_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start02_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start02_iter3.log`
- `rbf_s20_start08_rt1to1_rollrbf_s5_start02_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start02_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start02_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start02_iter6.log`
- `rbf_s20_start08_rt1to1_rollrbf_s5_start02_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start02_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start02_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start02_iterall.log`
- `rbf_s20_start08_rt1to1_rollrbf_s5_start04_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start04_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start04_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start04_iter1.log`
- `rbf_s20_start08_rt1to1_rollrbf_s5_start04_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start04_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start04_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start04_iter3.log`
- `rbf_s20_start08_rt1to1_rollrbf_s5_start04_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start04_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start04_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start04_iter6.log`
- `rbf_s20_start08_rt1to1_rollrbf_s5_start04_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start04_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start04_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start04_iterall.log`
- `rbf_s20_start08_rt1to1_rollrbf_s5_start06_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start06_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start06_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start06_iter1.log`
- `rbf_s20_start08_rt1to1_rollrbf_s5_start06_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start06_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start06_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start06_iter3.log`
- `rbf_s20_start08_rt1to1_rollrbf_s5_start06_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start06_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start06_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start06_iter6.log`
- `rbf_s20_start08_rt1to1_rollrbf_s5_start06_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start06_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start06_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start06_iterall.log`
- `rbf_s20_start08_rt1to1_rollrbf_s5_start08_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start08_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start08_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start08_iter1.log`
- `rbf_s20_start08_rt1to1_rollrbf_s5_start08_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start08_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start08_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start08_iter3.log`
- `rbf_s20_start08_rt1to1_rollrbf_s5_start08_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start08_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start08_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start08_iter6.log`
- `rbf_s20_start08_rt1to1_rollrbf_s5_start08_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start08_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start08_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s5_start08_iterall.log`
- `rbf_s20_start08_rt1to1_rollrbf_s10_start02_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start02_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start02_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start02_iter1.log`
- `rbf_s20_start08_rt1to1_rollrbf_s10_start02_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start02_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start02_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start02_iter3.log`
- `rbf_s20_start08_rt1to1_rollrbf_s10_start02_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start02_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start02_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start02_iter6.log`
- `rbf_s20_start08_rt1to1_rollrbf_s10_start02_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start02_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start02_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start02_iterall.log`
- `rbf_s20_start08_rt1to1_rollrbf_s10_start04_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start04_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start04_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start04_iter1.log`
- `rbf_s20_start08_rt1to1_rollrbf_s10_start04_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start04_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start04_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start04_iter3.log`
- `rbf_s20_start08_rt1to1_rollrbf_s10_start04_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start04_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start04_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start04_iter6.log`
- `rbf_s20_start08_rt1to1_rollrbf_s10_start04_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start04_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start04_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start04_iterall.log`
- `rbf_s20_start08_rt1to1_rollrbf_s10_start06_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start06_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start06_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start06_iter1.log`
- `rbf_s20_start08_rt1to1_rollrbf_s10_start06_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start06_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start06_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start06_iter3.log`
- `rbf_s20_start08_rt1to1_rollrbf_s10_start06_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start06_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start06_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start06_iter6.log`
- `rbf_s20_start08_rt1to1_rollrbf_s10_start06_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start06_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start06_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start06_iterall.log`
- `rbf_s20_start08_rt1to1_rollrbf_s10_start08_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start08_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start08_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start08_iter1.log`
- `rbf_s20_start08_rt1to1_rollrbf_s10_start08_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start08_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start08_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start08_iter3.log`
- `rbf_s20_start08_rt1to1_rollrbf_s10_start08_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start08_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start08_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start08_iter6.log`
- `rbf_s20_start08_rt1to1_rollrbf_s10_start08_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start08_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start08_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s10_start08_iterall.log`
- `rbf_s20_start08_rt1to1_rollrbf_s15_start02_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start02_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start02_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start02_iter1.log`
- `rbf_s20_start08_rt1to1_rollrbf_s15_start02_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start02_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start02_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start02_iter3.log`
- `rbf_s20_start08_rt1to1_rollrbf_s15_start02_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start02_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start02_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start02_iter6.log`
- `rbf_s20_start08_rt1to1_rollrbf_s15_start02_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start02_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start02_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start02_iterall.log`
- `rbf_s20_start08_rt1to1_rollrbf_s15_start04_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start04_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start04_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start04_iter1.log`
- `rbf_s20_start08_rt1to1_rollrbf_s15_start04_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start04_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start04_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start04_iter3.log`
- `rbf_s20_start08_rt1to1_rollrbf_s15_start04_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start04_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start04_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start04_iter6.log`
- `rbf_s20_start08_rt1to1_rollrbf_s15_start04_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start04_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start04_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start04_iterall.log`
- `rbf_s20_start08_rt1to1_rollrbf_s15_start06_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start06_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start06_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start06_iter1.log`
- `rbf_s20_start08_rt1to1_rollrbf_s15_start06_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start06_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start06_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start06_iter3.log`
- `rbf_s20_start08_rt1to1_rollrbf_s15_start06_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start06_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start06_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start06_iter6.log`
- `rbf_s20_start08_rt1to1_rollrbf_s15_start06_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start06_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start06_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start06_iterall.log`
- `rbf_s20_start08_rt1to1_rollrbf_s15_start08_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start08_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start08_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start08_iter1.log`
- `rbf_s20_start08_rt1to1_rollrbf_s15_start08_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start08_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start08_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start08_iter3.log`
- `rbf_s20_start08_rt1to1_rollrbf_s15_start08_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start08_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start08_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start08_iter6.log`
- `rbf_s20_start08_rt1to1_rollrbf_s15_start08_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start08_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start08_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s15_start08_iterall.log`
- `rbf_s20_start08_rt1to1_rollrbf_s20_start02_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start02_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start02_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start02_iter1.log`
- `rbf_s20_start08_rt1to1_rollrbf_s20_start02_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start02_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start02_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start02_iter3.log`
- `rbf_s20_start08_rt1to1_rollrbf_s20_start02_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start02_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start02_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start02_iter6.log`
- `rbf_s20_start08_rt1to1_rollrbf_s20_start02_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start02_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start02_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start02_iterall.log`
- `rbf_s20_start08_rt1to1_rollrbf_s20_start04_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start04_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start04_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start04_iter1.log`
- `rbf_s20_start08_rt1to1_rollrbf_s20_start04_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start04_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start04_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start04_iter3.log`
- `rbf_s20_start08_rt1to1_rollrbf_s20_start04_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start04_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start04_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start04_iter6.log`
- `rbf_s20_start08_rt1to1_rollrbf_s20_start04_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start04_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start04_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start04_iterall.log`
- `rbf_s20_start08_rt1to1_rollrbf_s20_start06_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start06_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start06_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start06_iter1.log`
- `rbf_s20_start08_rt1to1_rollrbf_s20_start06_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start06_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start06_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start06_iter3.log`
- `rbf_s20_start08_rt1to1_rollrbf_s20_start06_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start06_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start06_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start06_iter6.log`
- `rbf_s20_start08_rt1to1_rollrbf_s20_start06_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start06_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start06_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start06_iterall.log`
- `rbf_s20_start08_rt1to1_rollrbf_s20_start08_iter1`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start08_iter1`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start08_iter1/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start08_iter1.log`
- `rbf_s20_start08_rt1to1_rollrbf_s20_start08_iter3`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start08_iter3`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start08_iter3/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start08_iter3.log`
- `rbf_s20_start08_rt1to1_rollrbf_s20_start08_iter6`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start08_iter6`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start08_iter6/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start08_iter6.log`
- `rbf_s20_start08_rt1to1_rollrbf_s20_start08_iterall`: output `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start08_iterall`, metrics `outputs/ood_eval/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start08_iterall/eds_eval/eds_metrics.jsonl`, log `docs/03_evidence/eds_init_pg_diverse_sampling/logs/level4_libero_object_swap_rbf_s20_start08_rt1to1_rollrbf_s20_start08_iterall.log`
