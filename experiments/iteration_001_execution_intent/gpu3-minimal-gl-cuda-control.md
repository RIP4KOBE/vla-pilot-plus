# GPU3 minimal GL/CUDA differential control — prospective protocol

This engineering control is part of the user's 2026-09-23 explicit continuation of the original algorithm objective. It is not a new candidate, a task episode, a retry of any old resource, or evidence of task success. Preserve all previous invalid outcomes and the closed N1 cohort. The prior overall negative report remains a historical checkpoint.

## Question and evidence

Model-first resource `256bd92ec777` produced a finite original B1 then failed its next render with a GPU3 graphics MMU fault. Split-process resource `7a179aced1de` attributed a similar graphics fault to the renderer process, separate from the CUDA model parent. The native-lifetime resource `72a4dc721056` instead changed the first fresh-context wrist image before model loading. These do not establish hardware damage or a single common cause.

Test whether a minimal independent static MuJoCo scene is affected by progressively introducing small CUDA operations. This removes LIBERO, RDT, large model loading, native context recreation and all robot actions. A failure would narrow the issue to a smaller GL/CUDA execution path; a pass would leave the full application fault unresolved. Do not treat either outcome as an algorithm score or comprehensive hardware certification.

## Frozen procedure

- Physical GPU3 only, UUID `GPU-62052fa1-37e0-79dc-21aa-5c0f25c0c315`, PCI `0000:61:00.0`; the verified EGL enumeration index is 0, and masked CUDA device is 0. Use `CUDA_VISIBLE_DEVICES=3`, `CUDA_DEVICE_ORDER=PCI_BUS_ID`, `MUJOCO_EGL_DEVICE_ID=0`, `MUJOCO_GL=egl`, `PYOPENGL_PLATFORM=egl`.
- Construct one fixed XML scene containing a plane, a box, a light and fixed camera. Use the installed production EGL context implementation with low-level MuJoCo scene/render/readback calls. Freeze XML bytes and dependency sources before dispatch.
- Import torch without initializing CUDA. Assert this at the pre-render boundary. Construct one graphics context and keep it alive for the entire control. Do not reset, retire or rebuild it between boundaries.
- Exactly one `mj_forward` for scene initialization; zero `mj_step`, `mj_step1`, `mj_step2`, actions, robot environments, model loads, Stage calls or network requests. Simulation time and the relevant model/data state remain unchanged.
- Render two fixed 96×96 RGB/depth frames at each boundary: initial static scene; explicit CUDA initialization; a small deterministic CUDA allocation; a small deterministic matrix multiplication and synchronization. Cap ten total renders and 120 seconds of admitted child lifetime. No extra warming frames or data-dependent retries.
- Save every observed raw RGB/depth array losslessly with its shape, dtype, finite status and SHA256, plus exact comparison to the initial first frame. Before any GPU execution, require the baseline to contain at least two distinct RGB pixel colors and spatially varying depth with at least one value strictly inside (0,1), excluding a blank readback. Every depth value must be finite and in [0,1]. The second baseline frame must agree; later RGB must be byte-identical to baseline for a pass. Record depth differences without inventing a depth-equality requirement. Validate small CUDA output independently. The parent independently verifies these saved-array gates.
- Attribute the first abnormal boundary. On nonfinite output, RGB mismatch, device/scope mismatch, owned Xid31/109 or timeout, fail this control and stop the owned process. Preserve the failed raw arrays. No posthoc passing thresholds or success-based repeats.

## Resource supervision and decision

Use the shared runner lock and journal reconciliation; require 120 seconds of stable idle GPU3 and exclusive admission. Wait on GPU3 if occupied, with no device fallback or external process termination. Verify source/protocol/script/XML/runtime/dependency fingerprints before launch. Record exact commands, process identity and kernel cursor, and monitor only the owned resource for termination. An external process appearing on GPU3 invalidates exclusivity and stops only this worker.

Reserve at most 120 GPU-process seconds from recovery, preserving the existing 14-hour validation and 10-hour formal reservations. Account the complete admitted child lifetime including initialization and cleanup in the append-only GPU healthcheck ledger; this uses no scientific episode slot. Report errors, arrays and cost even on abort.

If the minimal control passes, investigate the application-specific resource state and the relevant incremental difference before another full-model run. If it fails, use the first failing operation and exact native fault to design the next discriminating control or a scoped compatibility repair. In both cases continue pursuing the user's task; this diagnostic is not an overall stop rule. Production images, action semantics, task definition, success evaluator, reward provider and model weights remain frozen.
