# EGL current-context drift — applied diagnostic, CPU reviewed

This directory preserves the reviewed proposal and its patch. Following the
coordinator’s explicit authorization, exactly its three files were applied to
the working tree. No installed robosuite, runtime configuration, queue,
scheduling, algorithm, budget, or experiment state was changed. The coordinator
owns source freezing and dispatch under a new diagnostic identity. No existing
failed attempt is replaced or silently rerun.

## Narrow question

Does the calling thread still have the EGL display/context associated with its
existing robosuite renderer immediately before the first fresh policy call,
after that policy returns, and before the first subsequently intercepted
production `sim.render`? The first render marker literally means the first
tracked render after installation; if rendering precedes the policy, record
order reveals that fact. Initialization renders before installation are outside
scope. This proposal makes no renderer-GPU identity or device-mapping claim.

The candidate modifies only `core/render_phase_diagnostics.py` to connect a new
`core/egl_context_drift.py`. Existing Main phase markers supply the policy
boundaries. Existing `sim.render` observation supplies the render boundary. It
adds no wrapper around the policy and changes no original call arguments,
return values, exceptions, renderer lock, RNG or simulation steps. It clears
its extra simulator reference when the existing diagnostic observer closes.

## Native surface and records

At most three observations per observer/episode, with at most six native calls:
`eglGetCurrentDisplay()` and `eglGetCurrentContext()` only. Their symbols may be
resolved from the existing handle of an already-loaded PyOpenGL platform EGL
library using independent ctypes function views. The platform library must
already be cached; accessing its lazy loader is excluded. Missing modules,
loaded library handles, actual symbols or references remain `Unknown`. The helper never
imports EGL/GL modules, opens a DLL, uses eglGetProcAddress, queries error state,
queries devices or strings, synchronizes CUDA, creates a context, makes a
context current, performs an additional render, or sets an environment variable.

Independent ctypes function views resolve through the existing DLL handle without
mutating production function objects or invoking PyOpenGL error checkers. The
expected context is the existing `sim._render_context_offscreen.gl_ctx._context`;
the expected display is `EGL_DISPLAY` in that object's already-loaded class
module. NULL references cannot produce a positive equality assertion.

`egl_context_drift.jsonl` records fixed boundary names, Python/native thread IDs,
time, and enter/exit events. Exit records contain only NULL/equality/availability
booleans or `Unknown`; no pointer addresses, device identifiers, image data,
credentials, or exception text are logged. At most six records are written.
An enter marker is closed to disk before native querying, so a native fault
inside the observation itself does not masquerade as a policy/render failure.
The first write is create-only, preserving earlier artifacts; write failure
skips the observation and disables future writes/queries. Missing entrypoints
consume the boundary without retries.

## Falsifiable interpretation and limits

- Matching non-NULL references before policy, then NULL/mismatch after policy on
  the same thread establishes a context change across that observed interval.
  It does not identify which internal operation caused it.
- A mismatch already before policy is not evidence that this policy call caused
  the mismatch. Different thread IDs must be treated explicitly.
- Three matching observations exclude persistent current-context mismatch only
  at those exact boundaries. They do not rule out transient changes, stale
  MjrContext resources, rendering-command errors, or other native faults.
- `Unknown` cannot be interpreted as matching or as proof of safety.

CPU tests prove only Python boundary behavior, bounded calls, missing-entry
handling, unchanged return/exception identity, and no lazy library loading by
the helper. They **cannot prove native queries have no driver-level effects**.
Even EGL getters can fail or abort in native code; Python cannot isolate such
failures. The extra observation and file I/O also have real overhead, which
remains charged by the outer runner's process wall time. This is a proposed
hypothesis test, not a claimed fix or a scientifically equivalent result.

## CPU validation performed

```
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 \
/home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -q \
 candidate/tests/test_egl_context_drift.py -p no:cacheprovider
```

Result: 8 passed in 0.04 seconds. All native query interfaces were mocked; no GPU,
EGL context, DLL load, network request or new experiment was used. The revised
patch passed `git apply --check`, then was applied only to its three listed
files. The applied helper tests plus existing render/episode timing tests passed
together: **26 passed in 0.40 seconds**. CPU validation cannot establish native
getter side-effect safety. No commit or GPU dispatch was performed by this agent.
