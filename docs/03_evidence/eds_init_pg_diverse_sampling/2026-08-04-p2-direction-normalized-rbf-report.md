# P2 Direction-Normalized RBF 最终实验、补充恢复与审计报告

生成时间：`2026-08-05T12:53:21.325395+00:00`

## 结论

- Decision：`no_adoption`。
- Task gate：`FAIL`；mechanism gate：`FAIL`；safety gate：`FAIL`。
- Contemporaneous control：`4/10`，tasks `[3, 5, 6, 7]`；primary W0/E050：`1/10`，tasks `[2]`。
- Parameter winner：`p2_stage_on_dirnorm_rbf_global_w2_e025`（`3/10`）；adoption ranking winner：`p2_stage_on_dirnorm_rbf_global_w2_e025`（`3/10`）。
- 本报告中的 success/fail 是任务 outcome；补充恢复的执行完成性另由 exact task/seed metadata、10 个 ffprobe-readable videos、metrics、Stage events 与 qualitative artifacts 验证。

## 批准范围、preflight、shared2 与 attempt ledger

- Mechanism preflight：`PASS`；scale-invariance max error `1.7702579498291016e-05`；hard failures `[]`。
- shared2 realpath：`/mnt/data/shared2/zhuoli/output/p2_direction_normalized_rbf`；worktree absolute link：`/home/hynx/VLA-Pilot++/.worktrees/exp/eds-init-pg-diverse-sampling/outputs/ood_eval/p2_direction_normalized_rbf` → `/mnt/data/shared2/zhuoli/output/p2_direction_normalized_rbf`。
- 原批准 ledger 保持 immutable effective `120/120`；用户明确授权的 supplemental recovery attempts `199`；合计 `319`。
- Complete video view：`/mnt/data/shared2/zhuoli/output/p2_direction_normalized_rbf/formal_complete_videos/recovery_20260805_final`。

## 实现与恢复机制

- `initial_diversity_descriptor_mode` / `rollout_diversity_descriptor_mode` 独立控制 `absolute_eef` 与 `direction_normalized_eef`；legacy 默认均为 `absolute_eef`。
- Direction 参数仍为 config-controlled weights、endpoint scale、path epsilon、distance epsilon；本次补跑未改变任何算法参数、task、seed、720-step budget 或正式矩阵。
- `main.episode_start_index` 保留 global episode 编号，LiberoAdapter 按 global episode 映射原 task；`main.episode_seed_schedule` 保证 suffix 使用预注册 seed。
- 每个 supplemental batch 使用独立 shared2 root、只读授权 manifest、追加式 supplemental ledger、dispatch/completion GPU snapshot；DINOv2 必需 cache 从 shared2 已审计副本离线 seed。
- Native abort diagnosis：`confirmed-and-recovered`；root cause：NVIDIA libnvidia-eglcore.so.580.65.06 aborted from mujoco.mjr_readPixels after GRAPHICS MMU faults/context-switch timeouts (Xid 31/109); no Direction-RBF nonfinite, action-mask, qpos, or Python exception preceded the abort.；recovery：Policy CUDA compute ran on independently admitted physical GPU 2 while MuJoCo EGL rendering ran on independently admitted physical GPU 3 (MUJOCO_EGL_DEVICE_ID=0), with JOBLIB_MULTIPROCESSING=0. Algorithm parameters, task ids, seeds, suite, 720-step limit, rendering semantics, and matrix were unchanged.。

## 11-job validity 与任务结果

| Job | Role | Exact videos/episodes | SR | Success tasks | Eligible | Invalid reason |
| --- | --- | ---: | ---: | --- | --- | --- |
| `p2_stage_on_abs_rbf_control` | control | 10/10 | 4/10 | `[3, 5, 6, 7]` | `True` | — |
| `p2_stage_on_dirnorm_rbf_rollout_w0_e050` | rollout_only | 10/10 | 1/10 | `[0]` | `True` | — |
| `p2_stage_on_dirnorm_rbf_global_w0_e025` | global | 10/10 | 0/10 | `[]` | `True` | — |
| `p2_stage_on_dirnorm_rbf_global_w0_e050` | global | 10/10 | 1/10 | `[2]` | `True` | — |
| `p2_stage_on_dirnorm_rbf_global_w0_e100` | global | 10/10 | 2/10 | `[0, 4]` | `True` | — |
| `p2_stage_on_dirnorm_rbf_global_w1_e025` | global | 10/10 | 2/10 | `[2, 7]` | `True` | — |
| `p2_stage_on_dirnorm_rbf_global_w1_e050` | global | 10/10 | 0/10 | `[]` | `True` | — |
| `p2_stage_on_dirnorm_rbf_global_w1_e100` | global | 10/10 | 1/10 | `[4]` | `True` | — |
| `p2_stage_on_dirnorm_rbf_global_w2_e025` | global | 10/10 | 3/10 | `[6, 8, 9]` | `True` | — |
| `p2_stage_on_dirnorm_rbf_global_w2_e050` | global | 10/10 | 0/10 | `[]` | `True` | — |
| `p2_stage_on_dirnorm_rbf_global_w2_e100` | global | 10/10 | 1/10 | `[6]` | `True` | — |

## Task-level paired outcomes

`S`=success，`F`=policy failure，`—`=无 eligible exact-seed outcome。

| Task | `p2_stage_on_abs_rbf_control` | `p2_stage_on_dirnorm_rbf_rollout_w0_e050` | `p2_stage_on_dirnorm_rbf_global_w0_e025` | `p2_stage_on_dirnorm_rbf_global_w0_e050` | `p2_stage_on_dirnorm_rbf_global_w0_e100` | `p2_stage_on_dirnorm_rbf_global_w1_e025` | `p2_stage_on_dirnorm_rbf_global_w1_e050` | `p2_stage_on_dirnorm_rbf_global_w1_e100` | `p2_stage_on_dirnorm_rbf_global_w2_e025` | `p2_stage_on_dirnorm_rbf_global_w2_e050` | `p2_stage_on_dirnorm_rbf_global_w2_e100` |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | F | S | F | F | S | F | F | F | F | F | F |
| 1 | F | F | F | F | F | F | F | F | F | F | F |
| 2 | F | F | F | S | F | S | F | F | F | F | F |
| 3 | S | F | F | F | F | F | F | F | F | F | F |
| 4 | F | F | F | F | S | F | F | S | F | F | F |
| 5 | S | F | F | F | F | F | F | F | F | F | F |
| 6 | S | F | F | F | F | F | F | F | S | F | S |
| 7 | S | F | F | F | F | S | F | F | F | F | F |
| 8 | F | F | F | F | F | F | F | F | S | F | F |
| 9 | F | F | F | F | F | F | F | F | S | F | F |

## Baseline、primary、parameter winner 与 adoption candidate

| Role | Label | SR | Gained vs control | Lost vs control | Retained control successes |
| --- | --- | ---: | --- | --- | --- |
| control | `p2_stage_on_abs_rbf_control` | 4/10 | `[]` | `[]` | `[3, 5, 6, 7]` |
| rollout attribution | `p2_stage_on_dirnorm_rbf_rollout_w0_e050` | 1/10 | `[0]` | `[3, 5, 6, 7]` | `[]` |
| primary reference | `p2_stage_on_dirnorm_rbf_global_w0_e050` | 1/10 | `[2]` | `[3, 5, 6, 7]` | `[]` |
| parameter winner | `p2_stage_on_dirnorm_rbf_global_w2_e025` | 3/10 | `[8, 9]` | `[3, 5, 7]` | `[6]` |
| adoption candidate | `p2_stage_on_dirnorm_rbf_global_w2_e025` | 3/10 | `[8, 9]` | `[3, 5, 7]` | `[6]` |

## Trajectory、max-step、direction diversity 与 latency

| Job | Length P95 | Max-step P95 | Length expansion med. | Max-step expansion med. | EEF direction med. | Endpoint spread med. | Chunk jump P95 | Select latency med. s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `p2_stage_on_abs_rbf_control` | 0.26111 | 0.04433 | 1.5357 | 1.6460 | 3.8606 | 1.0260 | 4.28362 | 4.458 |
| `p2_stage_on_dirnorm_rbf_rollout_w0_e050` | 0.26549 | 0.03756 | 1.6114 | 1.5133 | 3.8588 | 1.0359 | 3.86320 | 2.464 |
| `p2_stage_on_dirnorm_rbf_global_w0_e025` | 0.29393 | 0.04218 | 1.6596 | 1.5633 | 3.8496 | 1.0318 | 4.05980 | 2.920 |
| `p2_stage_on_dirnorm_rbf_global_w0_e050` | 0.27230 | 0.03649 | 1.5262 | 1.5051 | 3.8613 | 1.0403 | 3.46865 | 5.121 |
| `p2_stage_on_dirnorm_rbf_global_w0_e100` | 0.28336 | 0.04097 | 1.6324 | 1.5715 | 3.8459 | 1.0331 | 4.10869 | 2.531 |
| `p2_stage_on_dirnorm_rbf_global_w1_e025` | 0.35659 | 0.04924 | 2.0017 | 1.8120 | 3.8508 | 1.0346 | 4.16306 | 2.549 |
| `p2_stage_on_dirnorm_rbf_global_w1_e050` | 0.27658 | 0.04079 | 1.4631 | 1.4302 | 3.8474 | 1.0357 | 3.60021 | 7.334 |
| `p2_stage_on_dirnorm_rbf_global_w1_e100` | 0.31543 | 0.04326 | 1.8139 | 1.7285 | 3.8485 | 1.0333 | 3.93316 | 10.433 |
| `p2_stage_on_dirnorm_rbf_global_w2_e025` | 0.26850 | 0.03735 | 1.5009 | 1.4863 | 3.8583 | 1.0292 | 3.30588 | 2.785 |
| `p2_stage_on_dirnorm_rbf_global_w2_e050` | 0.27696 | 0.03841 | 1.8711 | 1.7463 | 3.8570 | 1.0303 | 3.96558 | 6.645 |
| `p2_stage_on_dirnorm_rbf_global_w2_e100` | 0.29975 | 0.04489 | 1.6645 | 1.6111 | 3.8642 | 1.0379 | 4.12103 | 2.509 |

Primary W0/E050 相对 contemporaneous control 的 mechanism ratios：

- EEF direction retention：`1.0002`（gate `>=0.90`）。
- Endpoint direction retention：`1.0139`（gate `>=0.90`）。
- Trajectory-length P95 ratio：`1.0428`（gate `<=0.85`）。
- Max-step P95 ratio：`0.8233`（gate `<=0.85`）。

## Direction-RBF components（initial / rollout）

| Job / scope | Direction mean | Shape mean | Endpoint mean | Composite mean | Weighted d/s/e | corr(composite,path ΔL) | corr(composite,direction) | Evidence n |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | ---: |
| `p2_stage_on_dirnorm_rbf_rollout_w0_e050` / rollout | 0.5480 | 0.3659 | 0.9259 | 0.5312 | 0.619/0.207/0.174 | 0.169 (n=327600) | 0.998 (n=327600) | 2730 |
| `p2_stage_on_dirnorm_rbf_global_w0_e025` / initial | 0.4809 | 0.3285 | 0.9835 | 0.4855 | 0.594/0.203/0.203 | -0.005 (n=103200) | 0.999 (n=103200) | 860 |
| `p2_stage_on_dirnorm_rbf_global_w0_e025` / rollout | 0.5405 | 0.3621 | 0.9780 | 0.5307 | 0.611/0.205/0.184 | 0.173 (n=387000) | 0.999 (n=387000) | 3225 |
| `p2_stage_on_dirnorm_rbf_global_w0_e050` / initial | 0.4839 | 0.3297 | 0.9251 | 0.4817 | 0.603/0.205/0.192 | -0.007 (n=117120) | 0.998 (n=117120) | 976 |
| `p2_stage_on_dirnorm_rbf_global_w0_e050` / rollout | 0.5439 | 0.3630 | 0.9228 | 0.5275 | 0.619/0.206/0.175 | 0.184 (n=439200) | 0.998 (n=439200) | 3660 |
| `p2_stage_on_dirnorm_rbf_global_w0_e100` / initial | 0.4847 | 0.3297 | 0.7646 | 0.4662 | 0.624/0.212/0.164 | 0.026 (n=79680) | 0.999 (n=79680) | 664 |
| `p2_stage_on_dirnorm_rbf_global_w0_e100` / rollout | 0.5442 | 0.3632 | 0.7819 | 0.5137 | 0.636/0.212/0.152 | 0.195 (n=298800) | 0.998 (n=298800) | 2490 |
| `p2_stage_on_dirnorm_rbf_global_w1_e025` / initial | 0.4834 | 0.3268 | 0.9839 | 0.4771 | 0.760/0.137/0.103 | -0.008 (n=66720) | 1.000 (n=66720) | 556 |
| `p2_stage_on_dirnorm_rbf_global_w1_e025` / rollout | 0.5387 | 0.3567 | 0.9768 | 0.5242 | 0.771/0.136/0.093 | 0.170 (n=250200) | 1.000 (n=250200) | 2085 |
| `p2_stage_on_dirnorm_rbf_global_w1_e050` / initial | 0.4808 | 0.3245 | 0.9218 | 0.4716 | 0.765/0.138/0.098 | 0.015 (n=115680) | 0.999 (n=115680) | 964 |
| `p2_stage_on_dirnorm_rbf_global_w1_e050` / rollout | 0.5405 | 0.3579 | 0.9191 | 0.5229 | 0.775/0.137/0.088 | 0.175 (n=433800) | 0.999 (n=433800) | 3615 |
| `p2_stage_on_dirnorm_rbf_global_w1_e100` / initial | 0.4817 | 0.3253 | 0.7552 | 0.4641 | 0.778/0.140/0.081 | 0.015 (n=67200) | 1.000 (n=67200) | 560 |
| `p2_stage_on_dirnorm_rbf_global_w1_e100` / rollout | 0.5401 | 0.3575 | 0.7727 | 0.5152 | 0.786/0.139/0.075 | 0.187 (n=252000) | 0.999 (n=252000) | 2100 |
| `p2_stage_on_dirnorm_rbf_global_w2_e025` / initial | 0.4809 | 0.3356 | 0.9838 | 0.4658 | 0.465/0.324/0.211 | -0.028 (n=69120) | 0.996 (n=69120) | 576 |
| `p2_stage_on_dirnorm_rbf_global_w2_e025` / rollout | 0.5366 | 0.3659 | 0.9775 | 0.5039 | 0.479/0.327/0.194 | 0.174 (n=259200) | 0.997 (n=259200) | 2160 |
| `p2_stage_on_dirnorm_rbf_global_w2_e050` / initial | 0.4824 | 0.3347 | 0.9241 | 0.4601 | 0.472/0.327/0.201 | -0.014 (n=94080) | 0.997 (n=94080) | 784 |
| `p2_stage_on_dirnorm_rbf_global_w2_e050` / rollout | 0.5413 | 0.3669 | 0.9233 | 0.5011 | 0.486/0.330/0.184 | 0.177 (n=352800) | 0.996 (n=352800) | 2940 |
| `p2_stage_on_dirnorm_rbf_global_w2_e100` / initial | 0.4855 | 0.3362 | 0.7657 | 0.4463 | 0.489/0.339/0.172 | 0.005 (n=108480) | 0.997 (n=108480) | 904 |
| `p2_stage_on_dirnorm_rbf_global_w2_e100` / rollout | 0.5447 | 0.3695 | 0.7851 | 0.4899 | 0.500/0.339/0.160 | 0.194 (n=406800) | 0.996 (n=406800) | 3390 |

## Weight、endpoint scale 主效应与交互

Estimable：`True`；complete eligible 3x3 grid。

完整 3×3 outcome grid（SR；`*` 表 eligible）：

| Weight | E025 | E050 | E100 |
| --- | --- | --- | --- |
| W0 | 0/10* | 1/10* | 2/10* |
| W1 | 2/10* | 0/10* | 1/10* |
| W2 | 3/10* | 0/10* | 1/10* |

Main-effect cell means：

| Factor | Level | Mean success | Mean length P95 | Mean max-step P95 | Mean EEF direction | Mean endpoint spread |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| weight | W0 | 1.000 | 0.28320 | 0.03988 | 3.8523 | 1.0351 |
| weight | W1 | 1.000 | 0.31620 | 0.04443 | 3.8489 | 1.0345 |
| weight | W2 | 1.333 | 0.28174 | 0.04021 | 3.8598 | 1.0325 |
| endpoint | E025 | 1.667 | 0.30634 | 0.04292 | 3.8529 | 1.0319 |
| endpoint | E050 | 0.333 | 0.27528 | 0.03857 | 3.8552 | 1.0354 |
| endpoint | E100 | 1.333 | 0.29951 | 0.04304 | 3.8529 | 1.0348 |

Success-count interaction residual `cell - W mean - E mean + grand mean`：

| Weight | E025 | E050 | E100 |
| --- | ---: | ---: | ---: |
| W0 | -1.556 | 0.778 | 0.778 |
| W1 | 0.444 | -0.222 | -0.222 |
| W2 | 1.111 | -0.556 | -0.556 |

## Safety、失败 attempt 与 qualitative provenance

- Safety gate：`FAIL`；winner qpos/execution errors `0`，collision/push/drop/wrong-object composite `4`；control composite `2`。
- Classification summary：`{'basket displaced/collision': 8, 'clutter swept/wrong-object interaction': 10, 'no target acquisition': 17, 'placement/release failure': 5, 'target pushed away': 9, 'timeout without task completion': 46}`；详情 `/mnt/data/shared2/zhuoli/output/p2_direction_normalized_rbf/analysis/failure_classification.json`。
- Final invalid/incomplete jobs：`[]`。
- Rejected historical/recovery attempts：`64`；它们保留原始 BF16、native abort、wrong-seed、SSL/cache 或 interruption provenance，不进入 selected outcome。

## Credential、GPU、Git 与进程审计

- Shared2 credential scan：`PASS`；finding paths `[]`。
- GPU reference peak `17921 MiB`；required free `22401.25 MiB`；runtime roles `{'p2_stage_on_abs_rbf_control': {'compute_gpu_index': 3, 'render_gpu_index': 3, 'mujoco_egl_device_id': 0}, 'p2_stage_on_dirnorm_rbf_rollout_w0_e050': {'compute_gpu_index': 2, 'render_gpu_index': 2, 'mujoco_egl_device_id': 1}, 'p2_stage_on_dirnorm_rbf_global_w0_e025': {'compute_gpu_index': 5, 'render_gpu_index': 5, 'mujoco_egl_device_id': 7}, 'p2_stage_on_dirnorm_rbf_global_w0_e050': {'compute_gpu_index': 3, 'render_gpu_index': 3, 'mujoco_egl_device_id': 0}, 'p2_stage_on_dirnorm_rbf_global_w0_e100': {'compute_gpu_index': 2, 'render_gpu_index': 2, 'mujoco_egl_device_id': 1}, 'p2_stage_on_dirnorm_rbf_global_w1_e025': {'compute_gpu_index': 5, 'render_gpu_index': 5, 'mujoco_egl_device_id': 7}, 'p2_stage_on_dirnorm_rbf_global_w1_e050': {'compute_gpu_index': 2, 'render_gpu_index': 2, 'mujoco_egl_device_id': 1}, 'p2_stage_on_dirnorm_rbf_global_w1_e100': {'compute_gpu_index': 2, 'render_gpu_index': 3, 'mujoco_egl_device_id': 0}, 'p2_stage_on_dirnorm_rbf_global_w2_e025': {'compute_gpu_index': 5, 'render_gpu_index': 5, 'mujoco_egl_device_id': 7}, 'p2_stage_on_dirnorm_rbf_global_w2_e050': {'compute_gpu_index': 3, 'render_gpu_index': 3, 'mujoco_egl_device_id': 0}, 'p2_stage_on_dirnorm_rbf_global_w2_e100': {'compute_gpu_index': 5, 'render_gpu_index': 5, 'mujoco_egl_device_id': 7}}`。
- Delivery audit：`{'schema': 'p2-direction-rbf-delivery-audit-v1', 'created_at': '2026-08-05T12:51:05+00:00', 'completed': True, 'tests': 'PASS: 822 passed in 124.74s', 'test_command': '/home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -q tests', 'py_compile': 'PASS: all changed and untracked Python sources compiled', 'git_diff_check': 'PASS', 'mechanism_preflight': {'status': 'PASS', 'scale_invariance_max_abs_error': 1.7702579498291016e-05, 'hard_failures': [], 'nonfinite_count': 0, 'zero_gradient_count': 0}, 'git_credential_scan': 'PASS: 25 changed/untracked paths inspected, zero findings; tests/test_eds_eval_runner.py excluded as the exact synthetic credential-redaction fixture', 'shared2_credential_scan': 'PASS: 4024 text artifacts inspected with no secret value emitted; the fail-closed scanner identified two metrics files only because each exceeded 128 MiB, and independent full-content scans found zero runtime-secret, token-pattern, or credential-value matches', 'symlink_audit': 'PASS: outputs/ood_eval/p2_direction_normalized_rbf is an absolute symlink to /mnt/data/shared2/zhuoli/output/p2_direction_normalized_rbf', 'storage_audit': 'PASS: /mnt/data/shared2 has approximately 5.0 TiB available at finalization', 'process_cleanup': 'PASS: no Direction-RBF runner, rdt_eds_eval_runner Direction job, or matching main.py experiment process; unrelated P23 tmux sessions preserved', 'cuda_bf16_preflight': 'PASS: vla-pilot CUDA BF16 Direction-RBF gradient returned finite float32', 'native_runtime_diagnosis': '/mnt/data/shared2/zhuoli/output/p2_direction_normalized_rbf/analysis/runtime_diagnostics/native_egl_abort_diagnosis.json', 'successful_recovery_root': '/mnt/data/shared2/zhuoli/output/p2_direction_normalized_rbf/supplemental_recovery/recovery_20260805_r13_w1e100_split_egl', 'successful_recovery_revalidation': '/mnt/data/shared2/zhuoli/output/p2_direction_normalized_rbf/supplemental_recovery/recovery_20260805_r13_w1e100_split_egl/manifests/post_run_revalidation.json', 'worktree_policy': 'Initial dirty worktree preserved; no reset/revert/overwrite of unrelated clean-tail or Stage-A changes', 'task_owned_paths': ['configs/config.yaml', 'core/eds_eval_metrics.py', 'core/env_adapters/libero_adapter.py', 'core/rdt_policy_steer.py', 'main.py', 'scripts/rdt_eds_eval_runner.py', 'scripts/p2_direction_normalized_rbf_runner.py', 'scripts/p2_direction_normalized_rbf_audit.py', 'tests/test_eds_eval_metrics.py', 'tests/test_eds_eval_runner.py', 'tests/test_env_adapters_imports.py', 'tests/test_main_rdt_startup.py', 'tests/test_rdt_steer.py', 'tests/test_direction_normalized_rbf.py', 'tests/test_p2_direction_normalized_rbf_runner.py', 'tests/test_p2_direction_normalized_rbf_audit.py', 'docs/01_specs/2026-08-04-p2-direction-normalized-rbf-design.md', 'docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-04-p2-direction-normalized-rbf-report.md'], 'preexisting_or_adjacent_dirty_paths_preserved': ['docs/01_specs/2026-08-01-p2-adaptive-eds-rbf-ood-optimization-design.md', 'docs/01_specs/2026-08-03-p2-rollout-clean-tail-parameter-sweep-design.md', 'docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-03-p2-adaptive-eds-rbf-stage-a-detailed-results-analysis.md', 'docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-03-p2-rollout-clean-tail-parameter-sweep-report.md', 'scripts/p2_rollout_clean_tail_runner.py', 'tests/test_p2_rollout_clean_tail_runner.py', 'utils/eds_eval_vis.py']}`。
- Decision manifest 保存 profiles、selected attempt provenance、task outcomes、gates、metrics/mechanism、checksums、supplemental ledger 和 complete-video view，并以 canonical checksum + `0444` 冻结。

## 风险与下一步

- 每 cell 仅 10 个固定 tasks；结果是工程配对证据，不代表统计显著性或跨任务泛化。
- 早期失败 attempts 仍揭示 native simulator、外网 cache 与长时 supervisor 风险；生产运行应继续使用离线 cache、独立 batch 与 exact-seed resume。
- Gate 结论不授权改变已批准矩阵、参数或追加新 sweep。
