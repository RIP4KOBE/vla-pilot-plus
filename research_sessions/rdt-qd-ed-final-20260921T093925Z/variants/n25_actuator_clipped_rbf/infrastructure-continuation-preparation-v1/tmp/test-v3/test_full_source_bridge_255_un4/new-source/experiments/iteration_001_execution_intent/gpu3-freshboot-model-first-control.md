# GPU3 original model-first workflow after external reboot

The server rebooted externally on 2026-09-23 at04:19:42UTC. Its boot identity changed from `aa293923b32a4a98911cabd80cf10d6d` to `2a1fa95f-ab0d-488c-a298-fc488ddd2af7`. Both data mounts subsequently recovered externally; this coordinator did not modify disks, mounts or drivers. Physical GPU3 remains UUID `GPU-62052fa1-37e0-79dc-21aa-5c0f25c0c315`, PCI `0000:61:00.0`, driver580.65.06, and a fresh metadata-only query still maps it to EGL index0.

## Hypothesis and scope

Before reboot, resource `256bd92ec777` loaded the original models before graphics creation, produced seven finite initial frames and a finite original B1, then failed the next render with a graphics Xid31. A prior split-process control also faulted in its renderer. An external reset of device/driver state is a new engineering condition. Test once whether the exact original model-first workflow still fails under the fresh boot, without another application repair or configuration change.

Use the byte-identical original worker `runtime/debug-tools/libero-task0-model-first.py`, SHA256 `63d0acaed3b5c1a3088dab79f49c2f224374406a0d9078c4c3aeeb2364eb2519`, and its original dependency/scene/model/seed/policy/physics-call contract. Preserve the old model-first protocol in the worker's required source set; also fingerprint this prospective continuation protocol. Freeze a new resource ID, new contract and new output directory under `continuation_20260923/freshboot-model-first`. Do not overwrite old runtime artifacts, contracts or results.

Require current boot identity before admission and dispatch, and record it throughout kernel attribution. PhysicalGPU3/CUDA0/EGL0 only; no fallback, external process sharing or external process termination. Take the shared runner lock, reconcile all attempts/resources, verify unchanged model/source/input bytes, require120seconds stable idle and apply the original single-worker admission and owned-Xid supervision.

## Evaluation and accounting

Use the original complete model load before scene creation, original task0 Dev seed/initrow, camera calls and original single B1/synchronization. Zero executed actions, simulator integration, DINO loads or Stage calls. Do not add warmup renders, model calls, context rebuilds or altered image processing. Keep all original scientific/engineering validation checks, including finite B1, exact compute evidence and canonical static RGB comparison. One run only, at most600GPU-process seconds, no automatic retry or posthoc passing thresholds.

Save command, source/dependency/contract identities, worker process identity, kernel cursor/owned faults, original events, result and full admitted lifetime including cleanup. Charge the healthcheck ledger against the existing48GPU-hour shared budget and recovery allocation, protecting14validation+10formal hours. This is not an episode or task success measurement, and does not replace any invalid N1 control.

If it passes, report only that this bounded original workflow now passes after the external reboot; the root cause remains unresolved, and full guided/DINO/depth/segmentation/action/reset operation still requires prospective checks. If it fails, retain the first failing stage and proceed to the independent minimal GL/CUDA or native-state investigation. Either outcome continues the overall algorithm objective. Do not equate a device reset correlation with proof of hardware damage or a verified production repair.
