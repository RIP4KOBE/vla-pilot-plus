# Production EGL identity observation — unapplied proposal

This artifact does not change the active worktree, installed robosuite, runtime
manifest, queue, environment, or frozen plan. Importing or constructing the
observer performs no native query. Only an explicitly connected callback after
an original production render succeeds initiates one observation attempt.

## Integration point

The existing `robosuite.utils.binding_utils.MjSim.render` holds
`_MjSim_render_lock`, calls its existing offscreen context's `render`, then calls
`read_pixels` and returns that original result. Prefer the success boundary of
the existing `read_pixels` call, before returning to `MjSim.render`: its original
renderer lock remains held and the original rendering thread is unchanged.
The success boundary of the outer `sim.render` is also supported on the same
thread. No extra render, `make_current`, context creation, simulator step,
environment reset, or device selection is added.

Proposed callback interface for the separate timing wrapper:

```python
observer = CurrentContextIdentityObserver(
    run_output / 'production-egl-context-identity.json',
    expected={
        'physical_gpu': runtime['gpu_mapping']['physical_gpu'],
        'uuid': runtime['gpu_mapping']['uuid'],
        'pci_bus_id': runtime['gpu_mapping']['pci_bus_id'],
        'egl_device_index': runtime['gpu_mapping']['egl_device_index'],
        'cuda_visible_devices': str(runtime['gpu_mapping']['physical_gpu']),
        'cuda_device_order': 'PCI_BUS_ID',
        'process_cuda_ordinal': 0,
    },
)

# At the existing successful read_pixels/render boundary only:
# result = original(*args, **kwargs)
observer.after_successful_render()
# return result
```

Alternatively, `wrap_render_once(original, observer)` returns a callable that
calls the original exactly once, preserving its arguments and returned object;
it invokes the callback only if that original call returns successfully. The
wrapper preserves original exceptions without invoking the observer. Do not
connect both alternatives: use one observation boundary per observer instance.
This is an interface example, not an applied patch or a dispatched experiment.

## Data and limits

The helper reuses **only already-loaded** EGL/GL DLL handles cached on
`OpenGL.platform.PLATFORM`; it bypasses lazy properties through `__dict__`.
It constructs independent raw ctypes call views of available exported entry
addresses, avoiding PyOpenGL wrappers and their implicit error-checking calls
without modifying the original function objects. It does not import GL modules,
load libraries, resolve additional extensions with `eglGetProcAddress`, or call
`eglGetError`/`glGetError`.

The helper queries the calling thread's current EGL display/context handles,
`GL_VENDOR`, `GL_RENDERER`, `GL_VERSION`, the display's `EGL_DEVICE_EXT`, device
enumeration index, and `EGL_CUDA_DEVICE_NV` ordinal where safely available.
Device attributes require proof of the corresponding extension in the current
display's extension string; the CUDA ordinal additionally requires
`EGL_NV_device_cuda` in the observed device's extension string. Without that
proof or an existing exported raw entry, the field stays `Unknown`. Some systems
advertise device-query support only in client extensions, so this intentionally
conservative approach can leave device fields unknown. It does not query extra
client displays or extend its implementation to fill those gaps. DRM/PCI
queries are omitted to keep this proposal minimal.

Expected identity is separately recorded from observed identity. Missing current
context, unavailable extensions and query failures stay
`Unknown`. In particular, environment masks and expected GPU UUIDs are never
copied into observed physical GPU/UUID fields. These queries do not independently
resolve a NVIDIA physical index or UUID; those comparison fields stay `Unknown`.
EGL index and CUDA ordinal comparisons individually report true, false or
`Unknown`; PCI stays `Unknown`. A successful synthetic native-MuJoCo probe does not substitute for
this production-context observation.

The first success boundary consumes the observer's single attempt even if data
are unavailable; there is no repeated querying. Diagnostic Python exceptions,
serialization failures, duplicate output paths and I/O failures are isolated
from the original result. The output file is create-only and never overwrites
an earlier observation. Normal process interrupts still propagate; native
driver faults cannot be caught by Python and remain a limitation of any
same-process native query. Supported native queries can still have driver-level
effects; this proposal does not claim perfect native-state transparency. Python
mocks prove call transparency and Python failure isolation only, not real driver
behavior. This helper therefore remains a proposal for observational review.

## CPU validation

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 \
  /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -q \
  /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/debug-tools/test_production_egl_identity_observer.py \
  -p no:cacheprovider
```

Result: **17 passed**. Tests use mock query objects and CPU ctypes callbacks
exclusively; no EGL library is loaded, GPU context queried, network request sent,
or package installed.
Coverage includes exact original render/pixel call counts, unchanged arguments,
return-object and exception identity, original lock ownership, one-shot query
failure isolation, missing context, partial observations, expected/observed
separation, raw entry reuse without error-checking wrappers or lazy loading,
unsupported attribute rejection, and preservation of an earlier artifact.
