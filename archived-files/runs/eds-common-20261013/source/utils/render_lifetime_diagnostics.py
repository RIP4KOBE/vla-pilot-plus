"""Opt-in lifetime observations; never rebind, free, render or collect resources."""
from __future__ import annotations

import ctypes
import functools
import gc
import json
from pathlib import Path
import threading
import time


def pointer(value):
    return ctypes.cast(value, ctypes.c_void_p).value if value else None


def install(output, *, bindings=None, current_context=None, handle=pointer,
            callbacks=None):
    if bindings is None:
        from robosuite.utils import binding_utils as bindings
    if current_context is None:
        from OpenGL import EGL
        current_context = EGL.eglGetCurrentContext
    cls = bindings.MjRenderContext
    if getattr(cls, '_qd_ed_lifetime_observer', None) is not None:
        return cls._qd_ed_lifetime_observer
    path = Path(output) / 'render_lifetime.jsonl'
    enabled = [True]

    def emit(event, **values):
        if not enabled[0]:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('a') as stream:
                stream.write(json.dumps({'schema': 'qd-ed-render-lifetime-v1',
                    'event': event, 'time_unix': time.time(),
                    'thread_id': threading.get_native_id(), **values}) + '\n')
        except Exception:
            enabled[0] = False

    def snapshot(instance, kind):
        values = {'object_id': id(instance)}
        try:
            ctx = instance if kind == 'context' else getattr(instance, '_render_context_offscreen', None)
            values['renderer_id'] = id(ctx) if ctx is not None else None
            gl = getattr(ctx, 'gl_ctx', None)
            owned = handle(getattr(gl, '_context', None))
            current = handle(current_context())
            values.update(owned_context=owned, current_context=current,
                          current_context_matches=current == owned if owned else None)
            con = getattr(ctx, 'con', None)
            values['mjr_context_id'] = id(con) if con is not None else None
            for field in ('offFBO', 'offColor', 'offDepthStencil', 'baseMesh', 'rangeMesh', 'ntexture'):
                value = getattr(con, field, None)
                if value is not None:
                    values[field] = int(value)
        except Exception:
            values['snapshot_available'] = False
        return values

    def wrap(owner, name, kind):
        original = getattr(owner, name)

        @functools.wraps(original)
        def observed(instance, *args, **kwargs):
            emit('enter', method=name, kind=kind, **snapshot(instance, kind))
            try:
                value = original(instance, *args, **kwargs)
            except BaseException:
                emit('exception', method=name, kind=kind, **snapshot(instance, kind))
                raise
            emit('exit', method=name, kind=kind, **snapshot(instance, kind))
            return value

        setattr(owner, name, observed)

    for name in ('__init__', '__del__', 'update_offscreen_size', 'render'):
        wrap(cls, name, 'context')
    wrap(bindings.MjSim, 'free', 'sim')

    def collection(phase, info):
        emit('gc_' + phase, generation=info.get('generation'),
             collected=info.get('collected'), uncollectable=info.get('uncollectable'))

    (gc.callbacks if callbacks is None else callbacks).append(collection)
    cls._qd_ed_lifetime_observer = emit
    emit('installed')
    return emit
