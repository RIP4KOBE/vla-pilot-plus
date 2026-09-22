# GPU6 closed-loop C0 diagnostic — frozen before dispatch

The GPU6 CUDA/EGL probe passed in 15.178619 seconds. Synthetic real-model B1 unguided inference passed in 116.848773 seconds with finite output [1,64,128]. This narrows the native crash investigation but does not resolve the prior guided-transition/EGL/environment failure.

Run exactly one C0 episode on task0 with the existing Dev env/policy seed1969522881 and init row0. Identity: iteration GPU6_NATIVE_C0, episode gpu6_native_c0_t00, development bucket, maximum720 environment steps and1800 seconds. No C0 task0 has previously been dispatched. This is a prospective diagnostic, separate from the failed Q0 and from the subsequent30-cell comparison; its outcome cannot promote N1 or replace any historical failure. No automatic retry.

Use the frozen C0 algorithm, real Codex Stage, model/encoder/input identities and physicalGPU6. The only source change adds scalar phase boundaries and timings plus native-fault Python stacks without locals. It does not change operation arguments, branching, RNG, action selection or execution. An AST comparison confirms removing the observers restores the original Main control flow. Focused phase/startup/Stage tests:115 passed; earlier runner/GPU/native tests:133 passed.

Measure initial observation, keypoint/Stage update, fresh/cached policy selection, diagnostic artifact generation, visualization overlay, video append, adapter step and policy observation. The last durable phase entry plus faulthandler output should localize another native failure; phase durations should explain the long delays outside prior select_action calls. Missing native evidence remains Unknown. If this episode completes, inspect whether it traversed the suspect guidance transition before drawing conclusions.

The diagnostic is charged to the common development count and GPU-hours. Validation/formal remain closed; the independent repaired-runtime comparison is not started until the evidence warrants it. Preserve the old incomplete cohorts and all diagnostics, including unsuccessful ones.

## Infrastructure interruption and explicit recovery

Attempt `rdt-qd-ed-final-20260921T093925Z__gpu6_native_c0_t00__6e57273c45b3` was aborted after695.836222 GPU seconds when an external GPU6 process appeared. It completed13 environment steps and was in the step13 visualization phase; no Stage query or native failure was reached. Keep the original terminal infrastructure record and all costs. This does not establish a robot task outcome or a native-crash fix.

The user's explicit instruction to keep scanning GPU6 and use it once completely free supports one linked recovery, `gpu6_native_c0_t00_r1`, with identical iteration/profile/task/seeds/init/scientific settings and the original attempt as `retry_of`. Charge recovery reserve. Wait on CPU with only physical6 eligible, no compute process or detected declared CUDA reservation, memory below1024MiB, and120 seconds continuously observed idle. Do not terminate external work. The queue executes only this recovery and then stops for evidence review; it never retries a dispatched failure by itself.

Measured partial phases: fresh search3.904s atstep0; first diagnostic artifacts20.240s; repeated adapter steps and later visualizations each around21s. Root cause remains Unknown. No CPU quota or GPU throttle indication was observed during spot checks. Do not interpret the unchanged algorithm's very slow rendering/control path as an N1 result. Full30-cell ETA remains conditional on resolving this runtime bottleneck.
