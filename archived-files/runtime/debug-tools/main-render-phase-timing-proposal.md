# Prospective main and shared-render timing patch

Status: prepared and CPU-tested only; **not applied**. No source, HEAD, configuration,
state, GPU process, simulator, scientific outcome, or recovery authorization was changed.

Base worktree: `/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z`

Base HEAD: `8771eaa74ede4159efb004e0709232175a6c0b8d`

Patch: `main-render-phase-timing-proposal.patch`

SHA256: `7d62df655c630a318c28f28ea7a99765ab1482880a179e3a63fcd7207ae927da`

The patch adds `core/render_phase_diagnostics.py`, two CPU test files, and sequential
main enter/exit markers. It includes the previous main timing/faulthandler proposal;
do not apply both patches. GPU6's original phase writer was checked against that
proposal. Its subsequently added global `utils.mujoco_phase_diagnostics.install`
was deliberately not copied into this instance-scoped candidate.

When EDS evaluation is enabled, faulthandler uses existing stderr and all Python
threads, without locals. The main markers cover initial/policy observations,
fresh/cached select_action, chunk keypoints/Stage transition, diagnostic artifacts,
overlay, video append, and adapter.step. Fresh select_action's existing metric and
all original expressions/statements remain unchanged.

Additional wrappers observe only already-created instances in the current LIBERO
chain `adapter._env[current_task_idx]._env.env`. They observe `_format_raw_obs`,
`_pre_action`, `_update_observables`, `sim.forward`, `sim.step`, `sim.render`, and
existing offscreen context `render`/`read_pixels`. They forward the original
positional and keyword arguments exactly, return the original object, and preserve
the original exception without retries. Replacement contexts are observed when
production code creates them; diagnostics create no contexts. Closing restores
inherited and per-instance method bindings and does not replace later third-party
bindings. The next episode closes the previous observer before installing its own.

Output uses the existing configured EDS directory:

- `phase_timing.jsonl`: main enter/exit markers, schema v2.
- `render_phase_timing.jsonl`: nested call IDs and parent main phase, allowing the
  same render path to be attributed to overlay versus adapter observation.
- `render_phase_overhead.jsonl`: per-main-phase detailed record count, estimated
  observer overhead, and append-I/O time. It excludes its own summary write.

All files are append-only. Each event closes its file, flushing to the kernel;
there is no fsync. Enter-only evidence survives a native abort once that write
finishes. No action arrays, images, requests, exceptions, environment, or credentials
are serialized. Camera labels are restricted to agentview/robot0_eye_in_hand/other;
only bounded integer dimensions and boolean render flags are recorded.

Timing definitions and limits:

- `observed_wall_s` covers the original call, including nested diagnostic work.
  The current call's own enter/exit writes are outside its interval.
- `nested_observer_s` estimates nested instrumentation cost, including its file I/O.
  `elapsed_s = max(0, observed_wall_s - nested_observer_s)`. The main phase applies
  the corresponding per-phase correction; existing scientific metrics are untouched.
- These are **inclusive** host timings. Do not add parents and children, or sum
  nested physics/update_observables/render phases as independent work. Direct-child
  subtraction can estimate uninstrumented residual time, not a unique root cause.
- Context render includes scene preparation and rasterization; read_pixels includes
  readback and its existing postprocessing. The original render lock is untouched.
  sim.render time before context.render includes setup and possible lock wait; it
  is not an isolated lock-wait measurement.
- Clock reads, wrapper dispatch and bookkeeping contribute small unaccounted costs;
  subtracting measured costs cannot reconstruct an uninstrumented execution exactly.
  Per-physics-substep records can be numerous and may change wall-clock overhead.
  No CUDA synchronization is added, so these are not CUDA kernel timings.
- The observer assumes the existing sequential episode execution. It does not
  claim correct nesting for concurrent calls through the same simulator instance.
  Initialization before `_run_episode` is outside this instrumentation. Native
  aborts yield an unmatched entry, not an exit duration or an inferred cause.
- This pure-stdlib timing patch does not query or prove actual EGL/CUDA identity.
  The independently prepared production identity observer can be reviewed separately
  at the original sim.render's successful return boundary; it is not merged here.
- Diagnostic write/setup failures disable or omit observation without changing
  control flow. Missing diagnostics mean unknown. Existing scientific failures and
  the fixed episode deadline retain their original interpretation.

Validation: **18 CPU-only tests passed in 0.27 s**, using disposable artifact-tree
copies. They never import main, Torch, CUDA, MuJoCo or a simulator. Tests cover exact
call count/order/argument identity/return identity, exception identity with enter-only
evidence, disabled observations, file-write failure, nested attribution, allowlisted
serialization, replacement contexts, rollback/restoration, and overhead accounting.

`git apply --check` passed against the base worktree. An AST transformer removes only
the newly named helpers/markers/timer assignments/faulthandler import; the remaining
entire main AST is identical to the original, SHA256
`84588176042beb0f99ea483245f68ae32dbb267d84fbba026ad483d5c6105e1a`.
Original main SHA256:
`a6ef52a2ea08564e9358f675a1db3d75b662f6b25b6c54b3894a93b4709821b3`.
The AST check preserves call/control expressions; CPU mocks additionally verify the
runtime wrapper contract. Neither is proof of GPU performance or simulator behavior.

Only after the root executor reviews the diagnostic scope and prepares a new frozen
source/plan revision, apply from the base worktree:

```sh
git apply --check /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/debug-tools/main-render-phase-timing-proposal.patch
git apply /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/debug-tools/main-render-phase-timing-proposal.patch
python -m pytest -q -p no:cacheprovider tests/test_episode_phase_timing.py tests/test_render_phase_diagnostics.py
```

These commands do not authorize a new episode, retry, or GPU dispatch. Subsequent
authorized execution remains restricted to GPU7, with existing resource/budget gates.
The standalone builder `build-render-phase-proposal.py` reproduces the patch and
checks in disposable artifact copies without applying it to the worktree.
