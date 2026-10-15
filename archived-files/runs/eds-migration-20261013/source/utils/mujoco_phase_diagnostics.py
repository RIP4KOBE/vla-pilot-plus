"""Scalar observers around already-loaded MuJoCo functions; no extra GL calls."""
from __future__ import annotations

import functools
import json
from pathlib import Path
import sys
import time


def install(output, *, modules=None):
    modules = sys.modules if modules is None else modules
    module = modules.get('mujoco')
    if module is None:
        return False
    path = Path(output) / 'mujoco_phase_timing.jsonl'
    names = ('mjv_updateScene', 'mjr_render', 'mjr_readPixels')
    for name in names:
        original = getattr(module, name, None)
        if original is None or getattr(original, '_qd_ed_timed', False):
            continue
        sequence = [0]
        enabled = [True]

        def emit(record, _enabled=enabled):
            if not _enabled[0]:
                return
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('a') as stream:
                    stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + '\n')
            except Exception:
                _enabled[0] = False

        @functools.wraps(original)
        def timed(*args, _original=original, _name=name, _sequence=sequence, _emit=emit, **kwargs):
            _sequence[0] += 1
            record = {'schema': 'qd-ed-mujoco-phase-v1', 'name': _name, 'call_index': _sequence[0]}
            _emit({**record, 'event': 'enter', 'time_unix': time.time()})
            started = time.perf_counter()
            try:
                value = _original(*args, **kwargs)
            except BaseException:
                _emit({**record, 'event': 'exception', 'elapsed_s': time.perf_counter() - started,
                       'time_unix': time.time()})
                raise
            _emit({**record, 'event': 'exit', 'elapsed_s': time.perf_counter() - started,
                   'time_unix': time.time()})
            return value

        timed._qd_ed_timed = True
        setattr(module, name, timed)
    return True
