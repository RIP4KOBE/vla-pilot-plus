# Run 033 protocol v2 — exact-cell recovery after pre-episode DINO cache failure

Date: 2026-08-12  
Parent protocol: `protocol.md` at commit `bdb1b161622e6289ebbd918c5ddc9f87dacc9655`  
Frozen scientific implementation: `94336b8baa5a6a2d28345fff285caf6974f46c4d`  
Parent immutable manifest: `manifests/mechanism_manifest.json`, SHA-256 `8c80cf3f898f694f9c18356e646e48510c962f331ab73754eb21fc2b8fcd3820`

## Incident classification

The first Run 033 dispatch reserved and dispatched global attempt IDs 67–72 on admitted GPUs 2 and 4, but both workers stopped before episode 0, policy action generation, EDS-QD search, task interaction, or result/metric/video creation. Both failures have the same traceback: `torch.hub.load('facebookresearch/dinov2', ...)` attempted a GitHub validation request and received HTTP 403 `rate limit exceeded` while constructing `KeypointDetector`.

This is a paired pre-episode infrastructure failure, not a control or candidate outcome. The two `run_manifest.csv` rows have exit code 1, zero metrics, zero metadata, zero videos and device walls 107.784/107.706 seconds. Their summed infrastructure device wall is `215.490 s = 0.05985833333333333 GPU-hours`; it is charged to the global GPU-hour cap but not to any scientific episode, success, mechanism, retention or latency denominator.

Preserved evidence before this amendment:

- attempt ledger SHA-256: `df5c8055f2a7c6d40df0a0ac3d6bd5746ec5d61c08af7233b2e9101ecd473a91`;
- failed run manifest SHA-256: `7ebf4ca4a12b40e61131e8066984267e5a764141925680c5e1f33a1ae34b31f8`;
- control log SHA-256: `b0179476df89dcc27bddcb015de320f766371ea3b842adf7f514c282155f1a82`;
- candidate log SHA-256: `9bcf23c45e3272705fa28c32468f5c36b79736dc0f895a7ad5fa2652e6b22d1f`;
- admission artifact SHA-256: `c772bb5b4f97b90f02ca9d568aa625e70118ce0d2bdebe1eb8f7c3ac25280068`.

The runner defect is infrastructure-only: v3 `configure_base()` assigns `base.P2_TORCH_HUB_SEED` from `v2.base.P2_TORCH_HUB_SEED`, but these names refer to the same imported module and the value is still `None`. Consequently the already audited local DINOv2 seed is not copied into each isolated XDG cache. The keypoint loader and all scientific source/config fingerprints remain unchanged.

## Authorized repair

Exactly one versioned recovery is authorized:

1. Preserve the failed output directories, runner logs, run manifest and admission snapshot under an incident archive inside the Run 033 owned artifact root. Do not overwrite or reinterpret them.
2. Append a `dispatch_aborted_pre_episode` event for IDs 67–72. Dispatched IDs are never deleted or voided.
3. Change only the v3 runner binding so `base.P2_TORCH_HUB_SEED` points to the same immutable local seed used by the audited v2 infrastructure:
   `/mnt/data/shared2/zhuoli/output/p2_direction_normalized_rbf/runtime_cache/formal/p2_stage_on_dirnorm_rbf_global_w0_e025/xdg/torch/hub`.
4. Add fail-closed tests for the exact cache source, append-only aborted-dispatch semantics, one-to-one cell identity recovery, budget accounting, and rejection of a second recovery.
5. After the repair commit, freeze `manifests/mechanism_manifest.v2.json`. It must bind the repaired runner commit/source fingerprints, parent manifest SHA, incident evidence hashes, exact recovery IDs and unchanged scientific payload.
6. Repeat only the six frozen cells, mapping IDs 73–78 one-to-one to IDs 67–72. Use a fresh real health check and fresh two-snapshot GPU admission; any of GPUs 0–7 may be selected only if admitted, one worker per GPU.

The control/candidate profiles, LIBERO-PRO suite, tasks `[3,8,9]`, seeds `[955865,522754,845886]`, 720-step horizon, 16-chunk cap, checkpoint, cached Stage functions, perturbations, QD settings, success gates, latency gate, retention gate and formal prohibition are byte-for-byte unchanged. Runtime credential handling remains environment-only and secret material is forbidden from Git, manifests, logs and artifacts.

## Ledger, budget and stop rules

- IDs 67–72 remain append-only `pre_episode_dinov2_cache_infrastructure` records and never enter scientific denominators.
- Recovery IDs are exactly 73–78, each carrying `recovery_of_attempt_id` for the corresponding original cell. After reservation, global reservations are `78/143`.
- The recovery consumes 6 of the v3 design's 19 infrastructure slots; 13 remain reserved for later audited exact-cell infrastructure needs and cannot become new candidates or sweeps.
- Global charged GPU-hours before recovery are `3.7471009444444445 + 0.05985833333333333 = 3.806959277777778`, below 48. Recovery device wall is added normally.
- A health/admission failure before recovery reservation consumes no new ID and may wait without changing science. Any outcome after episode initialization is final and cannot be retried. A repeated Run 033 pre-episode execution failure ends this recovery rather than authorizing another six-cell retry.
- Only IDs 73–78 may contribute to Run 033 mechanism, task-success, safety, latency and promotion gates. A valid scientific FAIL stops v3 with no Dev-A. PASS only authorizes the already frozen Dev-A protocol step; it does not authorize formal evaluation.

