# GPU5 CUDA/EGL serialization diagnostic — prospective intervention

## Evidence and hypothesis

GPU5 migration did not resolve the failure. Attempt`...gpu6_native_c0_t00_r1__03c5d2b4a1df` was infrastructure-aborted after132.650617seconds. Fresh C0 search completed in5.754640seconds; subsequent mjv_updateScene and mjr_render returned in0.000136/0.000860seconds; mjr_readPixels remained entered when the kernel emitted a same-PID GRAPHICS Xid31. No environment action or Stage query occurred. Original terminal, costs and artifacts are preserved in`analysis/gpu5-migration/render-fault-audit.json`.

The bounded hypothesis is that explicit serialization and restoration of the renderer's EGL context may avoid a CUDA/graphics interaction. This is not an established cause or fix. MuJoCo requires a current OpenGL context on the calling thread (https://mujoco.readthedocs.io/en/stable/programming/visualization.html); torch.cuda.synchronize waits for device kernels/streams (https://docs.pytorch.org/docs/stable/generated/torch.cuda.synchronize.html). Those contracts motivate the test; they do not prove this fault's cause.

## Single prospective diagnostic

Create a separate intervention condition`GPU5_EGL_SERIAL_C0`, episode`gpu5_egl_serial_c0_t00`, development bucket. Same task0/env+policyseed1969522881/init0/C0 and720-step/1800-second caps; frozen RDT, provider, action/reward/image/simulation settings unchanged. It is a new engineering diagnostic condition, not a replacement or ordinary retry of the previous faulted condition, and cannot promote N1 or enter the30-cell success comparison. Counts against the original development100 and total240/48h limits.

Only this condition sets the frozen runtime environment`QD_ED_CUDA_EGL_SERIALIZE=1`. All other runtime manifests explicitly resolve the flag to0 even if inherited from a launching shell. The guard, installed at episode entry after startup, wraps the existing robosuite render call: record whether the current EGL context matches its owner, synchronize initialized CUDA logical0, make the owned EGL context current and verify identity, then invoke the original render exactly once with unchanged arguments. No new model call, image, simulation transition, RNG sampling or renderer setting is introduced. Keep existing nested timings and Xid31/109 monitor. Setup/binding/CUDA errors propagate; no silent fallback to unguarded rendering.

Dispatch exactly one diagnostic onGPU5 and stop to inspect evidence. If the same fault persists after successful sync/binding, do not claim this guard fixes it. If healthy, evaluate timing, images, full episode and Stage transition evidence before deciding whether a common-runtime N1R comparison is justified. No broad matrix or automatic diagnostic retry.
