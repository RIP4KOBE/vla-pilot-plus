# Unstarted real-scene rendering diagnostic

Script: `libero-task0-render-only.py`

SHA256: `237f1c4125488379f2230c3cd854808c3bc330979d09c120ad10dfb7497fd115`

Five CPU fake tests passed in 0.15 seconds; syntax compilation passed. Preparation
did not launch a GPU, simulator, model, or network request and did not change source,
state, dependencies, runner, or commit. This artifact is now stable for root review.

The real entrypoint is `libero.libero.envs.OffScreenRenderEnv`, imported from the
current worktree's `third_party/libero_pro`. It receives the frozen task0 BDDL
directly, native `renderer='mujoco'`, agentview and robot0_eye_in_hand cameras,
128x128 observations and depth enabled, matching `LiberoEnv._make_envs_task`.
No synthetic XML, main, adapter, RDT, T5, DINO or Stage implementation is loaded.
Torch is imported only to deserialize the existing small init-state file onto CPU.
The BDDL/init file hashes and float64 row0 bytes are checked against the seed plan.

Control flow:

1. Validate runtime, input hashes, source HEAD, GPU3/EGL0 and required environment.
2. Install process-local call guards before any environment construction.
3. Construct the ordinary OffScreenRenderEnv. Its original model and native context
   construction remain intact. `Observable._check_sensor_validity` invokes the
   camera sensor during construction, so these renders count toward the same cap.
4. Call `env.set_init_state(row0)` directly. The existing implementation sets state,
   calls sim.forward, checks success, postprocesses, updates camera observables, and
   returns cached observations. These render calls also count toward the cap.
5. Perform eight explicit camera calls, cycling agentview128 RGB+depth,
   wrist128 RGB+depth, agentview640 RGB. Stop at the global cap if reached sooner.
6. Close the original environment. No reset loop, policy action, settling action,
   or task rollout is invoked.

The standard BDDL constructor `_reset_internal` calls `mujoco.mj_step1`; robosuite
initialization also calls forward. Therefore this is **zero actions and no complete
integration transition**, not zero native dynamics calls. The script preserves
mj_step1 and mj_forward, counts them and records simulation time before/after,
rejecting unexpected time advance. Calls to mj_step, mj_step2 or MjSim.step raise
before reaching the original operation. It never silently skips an intended step.
The loaded init row may set a saved simulation time; no advancement is allowed
after that binding. Literal zero mj_step-family calls are unavailable through this
unchanged standard constructor.

Ordinary adapter reset would perform five dummy settling actions in this frozen
configuration. They are intentionally absent from this diagnostic. Thus success
here only shows the unstepped scene can render in isolation; it cannot exonerate
scene dynamics, accumulated simulation state, context lifecycle, neural workload,
or their interactions. Failure before any neural model loads would show neural
inference is unnecessary for that reproduced failure. Neither result is SR or a
method assessment, and it does not alter any prior outcome.

Root-supervised CLI (substitute frozen hashes and a new resource output directory):

```sh
/home/hynx/miniconda3/envs/vla-pilot/bin/python \
  /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/debug-tools/libero-task0-render-only.py \
  --runtime /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/gpu3-render-diagnostic/runtime-manifest.json \
  --runtime-sha256 <frozen-runtime-sha256> \
  --seed-plan /home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/data/frozen-seed-plan.json \
  --seed-plan-sha256 9bbcf7107f6be4f739870a034ea84c4695819bdc1bffe5aa1148f453acf4a6b1 \
  --source-head <full-a5e1236-commit> \
  --output <new-owned-resource-output-directory> \
  --max-renders 32 --timeout-seconds 600
```

The supervising parent must supply the frozen environment (GPU3, CUDA PCI_BUS_ID,
EGL0, egl backends, owned LIBERO_CONFIG_PATH), verify source/input fingerprints and
resource exclusivity, reserve/account GPU wall time, and impose an external ceiling
of at most 600 seconds including native hangs. The internal alarm alone cannot
guarantee timely interruption of a blocked native call. This child never performs
resource admission, accounting, retry, recovery, or GPU selection.

Append-only `scene_render_events.jsonl` includes native/render entry and exit,
sim time, camera/shape, RGB SHA/dtype/finite/min/max/nonuniform and depth finite.
It records actual loaded dependency-source hashes and generated real-model XML
hash; root prefreezes and checks these dependency hashes. No image files or secrets
are written. Existing stderr receives faulthandler stacks. Native abort can leave
enter-only records; the supervisor owns terminal classification and Xid correlation.
