# Unapplied native render lifetime diagnostic

This artifact is a CPU-tested diagnostic prototype. It is not installed in the
benchmark worktree, and no GPU execution was performed for these tests. It makes
no claim that a native fault is fixed or that GPU pixels remain equivalent.

## Limited assembly contract

Import `native_render_lifetime.py` by its artifact path and construct:

```python
lifetime = NativeRenderLifetime(sim, egl=already_loaded_EGL,
                                max_width=640, max_height=480)
# Existing sim.render(...), unchanged arguments and return values.
snapshot = lifetime.snapshot()
lifetime.close()  # Before the original env.close(); terminal, not uninstall.
```

Install on the fresh existing offscreen context after environment creation and
initial state setup, before the first explicit diagnostic render and before
instance render observers. The existing context must still be current on the
installing thread. This is a caller precondition: the helper neither queries
current EGL state nor makes an extra first-render binding call. Only one sim,
one context, one render thread and the EGL backend are supported. The supplied
EGL module must already expose the three original cleanup entrypoints. No
library import, dynamic native lookup, new getter or extra synchronization is
performed by this helper.

The first complete `MjSim.render` reuses the existing native resources. Its
`finally` block frees `con` before freeing `gl_ctx`. Later calls create the same
GLContext class with the original size/device arguments, call its original
`make_current`, and call the existing `_set_mujoco_context_and_buffers`; then
they execute the original complete `MjSim.render`, including readback, and
release native resources again. Original `MjSim.render` owns its original
non-reentrant lock; this helper does not nest that lock. A separate nonblocking
guard rejects reentry, and a different thread fails before any native call.

The same Python context, `scn`, `cam`, `vopt`, `pert`, model/data references and
sim registration survive. No context constructor, `sim.forward`, physics step,
CUDA call, tensor operation or model read is added. Original buffer growth,
camera selection, segmentation flags and segmentation-ID decoding still run in
the installed robosuite methods. RGB and depth arrays are returned unchanged.

## Failure and destruction contract

This one context instance receives a same-layout dynamic subclass with a safe
finalizer, leaving installed class definitions unchanged. The original finalizer
unconditionally accesses native attributes, so it cannot run once those are
retired. The managed finalizer frees remaining live resources at most once on
the owner thread, then deletes the same four CPU fields as the original. It is
idempotent. Instance observers may retain this stable Python object while it
has no native context between renders.

During original `gl_ctx.free()` only, wrappers observe its existing
`eglMakeCurrent`, `eglDestroyContext` and `eglReleaseThread` calls and restore the
exact entrypoints afterward. Successful retirement requires exactly one destroy
of the owned handle and one release, every observed return true, no observed
exception, and the Python GL handle cleared. This matters because installed
`EGLGLContext.free` swallows exceptions and does not check native return values.
The helper records public booleans and exception types, not handle addresses.

A creation exception before the factory returns leaves allocation status
Unknown. Any render/readback/creation/cleanup error poisons this instance and
blocks subsequent renders; an existing primary exception is preserved. Failed
or uncertain resource cleanup retains Python references in a process-local
quarantine. Context replacement, or loss of the owning sim while old native
resources remain, quarantines without calling native free under an unknown
current context. Wrong-thread/busy destruction likewise avoids native calls.
These states require ending the diagnostic process, are never successful
cleanup, and are not a recovery path. Interpreter shutdown behavior of retained
native objects is outside the CPU proof; do not reuse that process.

The helper must not be used for direct `context.render/read_pixels`, texture
upload, viewer rendering, manual context replacement, multiple EGL threads or
continued operation after failure. Hard reset creates a different context and
needs a separately reviewed ownership boundary; this prototype deliberately
rejects replacement. It is not a general production integration.

## Evidence and strict next gate

CPU tests extract the actual installed `MjRenderContext` class and `MjSim.render`
AST from `robosuite/utils/binding_utils.py` and execute them with fake native
functions. They cover first reuse, subsequent create/read/release ordering,
stable Python state, original resize and segmentation results, zero extra
forward/registration, partial creation, original exception identity, swallowed
EGL failure, finalizer idempotence, observer retention, reentry/thread rejection
and context-replacement quarantine for render/close/finalizer entrypoints.

```sh
/home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -q test_native_render_lifetime.py
```

Result: **17 passed**. This validates Python control flow against the installed
source with fake native calls. It cannot establish native side-effect freedom,
real destruction correctness beyond observed API returns, GPU image equality,
or absence of graphics faults.

For the proposed nine-explicit-render diagnostic, success requires one reuse,
eight native-create exits, nine verified native-release exits, `failed=false`,
no live native attributes, the original B1/model counters, original physics
counts and exact canonical RGB/depth validity gates. Existing scene creation and
initial-state internal renders remain outside this helper. Record snapshots
after each call and on exceptions. Events are buffered Python records, without
an immediate callback; a native abort may prevent the last internal event from
being persisted.

No pixel tolerance is introduced: a different first frame remains a diagnostic
failure, even if later frames match and no Xid occurs. Native creation/free cost
per camera is Unknown until measured. Existing production CUDA work can be
asynchronous; this helper adds no CUDA fence and cannot claim that GPU kernels
have completed merely because a Python inference call returned. The existing
B1 diagnostic synchronization must remain unchanged and cannot establish the
equivalence of unsynchronized production execution.

## Installed source boundaries

- `robosuite/utils/binding_utils.py:69`: original context constructor performs
  forward/registration and creates the CPU scene objects; it is never repeated.
- `robosuite/utils/binding_utils.py:109`: original native MjrContext/buffer setup,
  reused directly without forward.
- `robosuite/utils/binding_utils.py:113`: original resize free/delete/recreate
  sequence remains active inside render.
- `robosuite/utils/binding_utils.py:126` and `:164`: original render and readback,
  including segmentation mapping through the stable scene.
- `robosuite/utils/binding_utils.py:194`: original finalizer replaced on this
  one instance to support absent native attributes.
- `robosuite/utils/binding_utils.py:1092`: original whole-render lock and ordered
  render/readback calls, retained by delegating to its bound implementation.
- `robosuite/renderers/context/egl_context.py:111`, `:141`, `:145`: original
  GL construction, binding and swallowed-exception cleanup behavior.
