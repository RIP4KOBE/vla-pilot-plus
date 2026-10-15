"""Opt-in diagnostic: serialize visible CUDA work before owned EGL rendering.

No image, action, simulator, RNG, renderer settings or numerical inputs change.
This is a prospective runtime hypothesis, not an established driver fix.
"""
from __future__ import annotations

import ctypes
import functools
import json
from pathlib import Path
import sys
import time


def pointer(context):
    return ctypes.cast(context, ctypes.c_void_p).value if context else None


def install(output, *, bindings=None, torch_module=None, current_context=None, handle=pointer):
    bindings = bindings or sys.modules.get('robosuite.utils.binding_utils')
    torch_module = torch_module or sys.modules.get('torch')
    if bindings is None or torch_module is None:
        raise RuntimeError('CUDA/EGL guard requires loaded robosuite and torch')
    if current_context is None:
        from OpenGL import EGL
        current_context = EGL.eglGetCurrentContext
    cls = bindings.MjRenderContext
    original = cls.render
    if getattr(original, '_qd_ed_cuda_egl_guard', False):
        return
    path = Path(output) / 'cuda_egl_guard.jsonl'
    enabled = [True]
    counter = [0]

    def emit(record):
        if not enabled[0]:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('a') as stream:
                stream.write(json.dumps({'schema': 'qd-ed-cuda-egl-guard-v1',
                                         'time_unix': time.time(), **record}) + '\n')
        except OSError:
            enabled[0] = False

    @functools.wraps(original)
    def render(context, *args, **kwargs):
        counter[0] += 1
        common = {'call_index': counter[0]}
        expected = handle(context.gl_ctx._context)
        if expected is None:
            raise RuntimeError('CUDA/EGL guard found no owned EGL context')
        emit({**common, 'event': 'enter',
              'current_context_matches': handle(current_context()) == expected})
        started = time.perf_counter()
        if torch_module.cuda.is_initialized():
            # CUDA logical0 is explicitly bound to the sole admitted GPU.
            torch_module.cuda.synchronize(device=0)
        emit({**common, 'event': 'cuda_complete', 'elapsed_s': time.perf_counter() - started})
        context.gl_ctx.make_current()
        if handle(current_context()) != expected:
            raise RuntimeError('CUDA/EGL guard failed to bind the owned EGL context')
        emit({**common, 'event': 'egl_current'})
        return original(context, *args, **kwargs)

    render._qd_ed_cuda_egl_guard = True
    cls.render = render
