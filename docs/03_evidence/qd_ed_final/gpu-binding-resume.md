# GPU7 CUDA/EGL admission repair

The first accounted context probe (`fe302aecdabc`) stopped at the assertion
`actual EGL display is not bound to GPU7`. Its earlier Torch UUID assertion
passed. The old probe wrote its observation JSON only after validation, so
the exact rejected EGL ordinal was not retained and cannot be reconstructed
from that failed run's log.

The existing unmasked, enumeration-only evidence is
`/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/egl-device-metadata.json`.
It binds EGL index 4 to CUDA ordinal 7 and records physical GPU7 UUID
`GPU-48473162-9548-1a19-04aa-ea86c5349187`, PCI `00000000:E1:00.0`.
Its NVIDIA EGL device has no DRM path; the evidence therefore correctly
does not claim independent DRM PCI verification.

A fresh metadata-only enumeration used the exact child namespace:
`CUDA_VISIBLE_DEVICES=7 CUDA_DEVICE_ORDER=PCI_BUS_ID`, calling only
`eglGetProcAddress`, `eglQueryDevicesEXT`, `eglQueryDeviceAttribEXT`, and
`eglQueryDeviceStringEXT` through the existing enumeration helper. It did
not create a display, context, CUDA tensor, simulator, or GPU worker.
Exactly one EGL device returned a valid `EGL_CUDA_DEVICE_NV` attribute:
EGL index 4, CUDA ordinal **0**. The helper's historical field name
`physical_cuda_ordinal` is misleading when a visibility mask is present;
this observation is in the process-visible CUDA namespace.

The revised context probe requires all of the following simultaneously:

- The frozen, verified metadata mapping names physical GPU7.
- The actual child environment is mask `7`, order `PCI_BUS_ID`, with
  exactly one visible CUDA device.
- Torch logical0's UUID equals the frozen physical GPU7 UUID; the existing
  GPU admission check independently checks physical GPU7 through NVIDIA SMI.
- The actual current EGL display maps to frozen EGL index 4 and to visible
  CUDA ordinal 0.
- Enumeration in that same process has exactly one successful CUDA
  association: that same EGL index and ordinal 0.
- NVIDIA OpenGL identity, CUDA arithmetic, nonuniform frame, and zero
  simulation-step checks still pass.

The change rejects ordinal 7 in the masked context rather than accepting
both ordinals. A wrong UUID, wrong EGL index, different mask/order, missing
association, or duplicate association still fails admission. Raw render
observations are durably written before validation, with `pending`,
`rejected` plus the reason, or `passed` status, so another rejected probe
retains its diagnostic evidence.

CPU-only verification:
`CUDA_VISIBLE_DEVICES='' /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -q tests/test_qd_ed_gpu_probe.py`
passed **24 tests**. These include namespace/UUID/index ambiguity rejection,
persist-before-validation behavior, accounting mocks, and readiness guards.
No real context probe was rerun by this repair task. A successful accounted
probe is still required before runtime readiness can change.
