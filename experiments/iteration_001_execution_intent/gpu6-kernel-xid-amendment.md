# GPU6 kernel-fault evidence and prospective diagnostic amendment

This amendment follows the user's authorization to test and iterate on GPU6, and to scan until it is free. It changes diagnostics and infrastructure termination only. It does not change C0/Q0/N1 algorithms, images, simulation actions, seeds, Stage provider or task-success criteria.

## New evidence

Kernel journal audit at `analysis/gpu6-xid-audit/audit.json` in the GPU6 artifact root links five Xid events to C0 process4130356 and five to earlier Q0 process4006998, on physicalGPU6 / PCI0000:c1:00. C0 has three graphics MMU faults(Xid31) and two context-switch timeouts(Xid109), beginning06:54:06UTC. Its terminal interruption remains the observed external GPU process; the journal adds evidence of graphics failures before that interruption. No Stage call occurred in C0, so the Stage guidance transition is not necessary for these graphics faults. Exact cause of the previous SIGABRT remains unproven without a native stack.

Historical independent evidence is `/mnt/data/shared2/zhuoli/output/p2_direction_normalized_rbf/analysis/runtime_diagnostics/native_egl_abort_diagnosis.json`: H200NVL, driver580.65.06, MuJoCo3.7.0, native abort in mjr_readPixels, Xid31/109. Its successful CUDA/EGL split used two GPUs. That workaround is not applied under the current GPU6-only instruction. No device reset, system driver change, external-process termination, or scientific outcome reclassification is performed.

## Prospective execution

The undispatched recovery queue4171021 was administratively stopped while holding the shared study runner lock, using verified process start ticks and a pidfd. No GPU worker or attempt was stopped/added. Its plan/status/log remain preserved. The same undispatched explicit recovery key `gpu6_native_c0_t00_r1` will be refrozen with the following observers; retry_of remains the C0 infrastructure abort, recovery bucket,720-step/1800-second caps.

1. Wrap already-loaded MuJoCo mjv_updateScene, mjr_render and mjr_readPixels. Record scalar enter/exit/exception times and call numbers only. Forward original arguments, return values and exceptions; introduce no render, synchronize, simulation or RNG calls. Diagnostic write failure does not alter the operation.
2. Before each episode dispatch, establish a current-boot kernel journal cursor. Every worker-monitor poll and after child exit, inspect new records on the frozen GPU PCI address. Save only matching NVIDIA Xid records, with exact timestamp and PID attribution. A new Xid31 or109 aborts the owned attempt as infrastructure; journal-monitor unavailability fails closed. Do not reject using stale historical Xids. This is a prospective rule, not a retrospective retry expansion.
3. Relaunch a CPU wait queue restricted to GPU6,30-second polls,120-second idle stability. Run exactly that one linked C0 recovery, then stop for evidence review. No automatic retries or30-cell matrix dispatch.

## Interpretation and next decision

A complete healthy C0 diagnostic is necessary evidence, not proof of repaired QD execution. If Xid recurs, inspect nested timings and fault position, then prepare a bounded common-runtime repair within GPU6 and the same cumulative budget. Do not continue full scientific batches on a known failing render path. If C0 completes, first verify that all costs/artifacts/Stage transitions are valid before proposing the next diagnostic or freezing N1R.

There is still no effective online C0/Q0/N1 comparison in this execution and no measured improvement in N1 success. The30-cell matrix remains prepared, not dispatchable. The earlier8–15hour reservation is conditional on runtime readiness; current completion ETA is unknown.
