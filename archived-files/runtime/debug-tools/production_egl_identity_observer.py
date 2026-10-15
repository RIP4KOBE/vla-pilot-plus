"""Unapplied proposal: inspect an already-current production EGL context once.

Import and construction are CPU-only. Native queries run only when an explicit
after_successful_render callback is invoked. This module never creates a display
or context, makes one current, renders, steps a simulator, or reads credentials.
"""
from __future__ import annotations

import ctypes
import functools
import json
import os
from pathlib import Path
import re
import sys
import threading
import time


UNKNOWN = 'Unknown'
EXPECTED_FIELDS = (
    'physical_gpu', 'uuid', 'pci_bus_id', 'egl_device_index',
    'cuda_visible_devices', 'cuda_device_order', 'process_cuda_ordinal',
)
OBSERVED_FIELDS = (
    'egl_current_display', 'egl_current_context', 'egl_display_device',
    'egl_device_index', 'egl_device_cuda_ordinal', 'gl_vendor', 'gl_renderer',
    'gl_version', 'drm_device_file', 'drm_pci_bus_id', 'physical_gpu', 'gpu_uuid',
)


class ReadOnlyEGLQueries:
    """Use raw entrypoints from already-loaded PyOpenGL DLL handles only.

    Access cached platform attributes through __dict__ so lazy library loaders
    cannot run. Fresh ctypes call views omit wrappers/errcheck without changing
    the production function objects. Missing exports or extension proof remain
    unavailable; there is no eglGetProcAddress fallback.
    """

    def __init__(self):
        module = sys.modules.get('OpenGL.platform')
        platform = vars(module).get('PLATFORM') if module is not None else None
        cached = vars(platform) if platform is not None else {}
        self._egl, self._gl = cached.get('EGL'), cached.get('GL')
        if self._egl is None:
            raise LookupError('production EGL library is not already loaded')
        self._display_extensions = None
        self._device_extensions = {}
        self._display = None

    @staticmethod
    def raw(library, name, result, arguments):
        if library is None:
            raise LookupError('production library is not already loaded')
        original = getattr(library, name, None)
        if original is None:
            raise LookupError('raw query is not exported by loaded library')
        address = ctypes.cast(original, ctypes.c_void_p).value
        if not address:
            raise LookupError('raw query address is unavailable')
        return ctypes.CFUNCTYPE(result, *arguments)(address)

    def current_display(self):
        self._display = self.raw(self._egl, 'eglGetCurrentDisplay', ctypes.c_void_p, [])()
        return self._display

    def current_context(self):
        return self.raw(self._egl, 'eglGetCurrentContext', ctypes.c_void_p, [])()

    def gl_string(self, enum):
        value = self.raw(self._gl, 'glGetString', ctypes.c_char_p, [ctypes.c_uint])(enum)
        return value.decode('utf-8', errors='replace') if value else None

    def supports_display(self, *extensions):
        if self._display_extensions is None:
            function = self.raw(self._egl, 'eglQueryString', ctypes.c_char_p, [ctypes.c_void_p, ctypes.c_int])
            value = function(self._display, 0x3055)
            self._display_extensions = set(value.decode('ascii', errors='replace').split()) if value else set()
        if not any(extension in self._display_extensions for extension in extensions):
            raise LookupError('required extension support not proven on current display')

    def display_device(self, display):
        self.supports_display('EGL_EXT_device_query', 'EGL_EXT_device_base')
        function = self.raw(self._egl, 'eglQueryDisplayAttribEXT', ctypes.c_uint,
                            [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_ssize_t)])
        value = ctypes.c_ssize_t()
        return value.value if function(display, 0x322C, ctypes.byref(value)) else None

    def device_cuda_ordinal(self, device):
        self.supports_display('EGL_EXT_device_query', 'EGL_EXT_device_base')
        if device not in self._device_extensions:
            function = self.raw(self._egl, 'eglQueryDeviceStringEXT', ctypes.c_char_p, [ctypes.c_void_p, ctypes.c_int])
            value = function(device, 0x3055)
            self._device_extensions[device] = set(value.decode('ascii', errors='replace').split()) if value else set()
        if 'EGL_NV_device_cuda' not in self._device_extensions[device]:
            raise LookupError('CUDA device attribute support not proven on observed device')
        function = self.raw(self._egl, 'eglQueryDeviceAttribEXT', ctypes.c_uint,
                            [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_ssize_t)])
        value = ctypes.c_ssize_t()
        return value.value if function(device, 0x323A, ctypes.byref(value)) else None

    def device_indices(self, device):
        self.supports_display('EGL_EXT_device_enumeration', 'EGL_EXT_device_base')
        function = self.raw(self._egl, 'eglQueryDevicesEXT', ctypes.c_uint,
            [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_int)])
        count = ctypes.c_int()
        devices = (ctypes.c_void_p * 128)()
        if not function(128, devices, ctypes.byref(count)) or not 0 < count.value <= 128:
            return []
        return [index for index in range(count.value) if devices[index] == device]


def query_current_context(queries_factory=ReadOnlyEGLQueries):
    """Observe only the calling thread's current context; absent data stays Unknown."""
    observed = {field: UNKNOWN for field in OBSERVED_FIELDS}
    unavailable = []
    def attempt(field, function):
        try:
            value = function()
        except Exception as exc:
            unavailable.append({'field': field, 'reason': type(exc).__name__})
            return None
        if value is None or value == '' or value == []:
            unavailable.append({'field': field, 'reason': 'query_unavailable'})
            return None
        return value
    queries = attempt('egl_library', queries_factory)
    if queries is None:
        return {'observed': observed, 'unavailable': unavailable}
    display = attempt('egl_current_display', queries.current_display)
    context = attempt('egl_current_context', queries.current_context)
    if display:
        observed['egl_current_display'] = hex(display)
    if context:
        observed['egl_current_context'] = hex(context)
    if not display or not context:
        unavailable.append({'field': 'current_context', 'reason': 'no_current_display_or_context'})
        return {'observed': observed, 'unavailable': unavailable}
    for field, enum in (('gl_vendor', 0x1F00), ('gl_renderer', 0x1F01), ('gl_version', 0x1F02)):
        value = attempt(field, lambda enum=enum: queries.gl_string(enum))
        if value is not None:
            observed[field] = value
    device = attempt('egl_display_device', lambda: queries.display_device(display))
    if device:
        observed['egl_display_device'] = hex(device)
        ordinal = attempt('egl_device_cuda_ordinal', lambda: queries.device_cuda_ordinal(device))
        if ordinal is not None:
            observed['egl_device_cuda_ordinal'] = ordinal
        indices = attempt('egl_device_index', lambda: queries.device_indices(device))
        if indices is not None and len(indices) == 1:
            observed['egl_device_index'] = indices[0]
        elif indices is not None:
            unavailable.append({'field': 'egl_device_index', 'reason': 'ambiguous_device_enumeration'})
    # Current EGL metadata does not independently provide a NVIDIA index/UUID.
    # In particular, do not substitute CUDA_VISIBLE_DEVICES or expected values.
    return {'observed': observed, 'unavailable': unavailable}


def comparisons(expected, observed):
    def equal(observed_field, expected_field, normalize=lambda value: value):
        left, right = observed.get(observed_field, UNKNOWN), expected.get(expected_field, UNKNOWN)
        if left == UNKNOWN or right == UNKNOWN:
            return UNKNOWN
        try:
            return normalize(left) == normalize(right)
        except Exception:
            return UNKNOWN
    def pci(value):
        match = re.fullmatch(r'([0-9a-fA-F]+):([0-9a-fA-F]{2}):([0-9a-fA-F]{2})\.([0-7])', value)
        if match is None:
            raise ValueError('invalid PCI identifier')
        return tuple(int(group, 16) for group in match.groups())
    return {'egl_device_index_matches': equal('egl_device_index', 'egl_device_index'),
            'process_cuda_ordinal_matches': equal('egl_device_cuda_ordinal', 'process_cuda_ordinal'),
            'drm_pci_bus_id_matches': equal('drm_pci_bus_id', 'pci_bus_id', pci),
            'physical_gpu_index_matches': UNKNOWN, 'gpu_uuid_matches': UNKNOWN}


class CurrentContextIdentityObserver:
    """Best-effort callback; at most one query attempt after successful rendering."""

    def __init__(self, output_path, expected, *, query_fn=query_current_context):
        self.output_path = Path(output_path)
        self.expected = {field: expected.get(field, UNKNOWN) for field in EXPECTED_FIELDS}
        self.query_fn = query_fn
        self._attempted = False
        self._lock = threading.Lock()
        self.last_record = None

    def after_successful_render(self):
        # The diagnostic's own lock does not replace or acquire the renderer lock.
        with self._lock:
            if self._attempted:
                return
            self._attempted = True
        record = {'schema': 'production-egl-current-context-observation-v1',
                  'time_unix': time.time(), 'thread_id': threading.get_ident(),
                  'trigger': 'original_production_render_returned_successfully',
                  'expected': self.expected,
                  'observation_policy': 'current calling-thread context only; environment is not device evidence',
                  'extra_render_calls': 0, 'extra_simulation_steps': 0,
                  'context_create_calls': 0, 'make_current_calls': 0}
        try:
            record.update(self.query_fn())
        except Exception as exc:
            record.update(observed={field: UNKNOWN for field in OBSERVED_FIELDS},
                          unavailable=[{'field': 'identity_query', 'reason': type(exc).__name__}])
        try:
            record['comparison'] = comparisons(self.expected, record['observed'])
            self.last_record = record
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            # Create-only: never overwrite a prior run's context observation.
            with self.output_path.open('x') as stream:
                stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + '\n')
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            # A missing/unwritable path, malformed diagnostic value, or duplicate
            # artifact cannot change the original renderer's result or exception.
            return


def wrap_render_once(original, observer):
    """Optional instance wrapper: exactly one original call with untouched args."""
    @functools.wraps(original)
    def wrapped(*args, **kwargs):
        result = original(*args, **kwargs)
        try:
            observer.after_successful_render()
        except Exception:
            pass
        return result
    return wrapped
