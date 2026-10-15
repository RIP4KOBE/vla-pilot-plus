"""Diagnostic: at most three current-context observations per episode.

Only two standard getters on an already-loaded EGL library may be called. Import
and construction never query native state. No display/context creation, device
lookup, string query, error query, make_current, or library load is performed.
"""
import ctypes
import json
from pathlib import Path
import sys
import threading
import time

UNKNOWN = "Unknown"
BOUNDARIES = ("before_first_policy", "after_first_policy", "before_first_render")


def _pointer(value):
    if value is None:
        return 0
    if type(value) is int and value >= 0:
        return value
    return ctypes.cast(value, ctypes.c_void_p).value or 0


def _cached_raw_query(name):
    """Resolve only standard getters through an already-loaded EGL DLL handle."""
    if name not in ("eglGetCurrentDisplay", "eglGetCurrentContext"):
        raise LookupError("EGL entrypoint is outside the diagnostic surface")
    module = sys.modules.get("OpenGL.platform")
    platform = vars(module).get("PLATFORM") if module is not None else None
    # vars() deliberately avoids the platform's lazy EGL property / DLL loader.
    library = vars(platform).get("EGL") if platform is not None else None
    handle = vars(library).get("_handle") if library is not None else None
    if type(handle) is not int or handle == 0:
        raise LookupError("An already-loaded EGL library handle is unavailable")
    # ctypes resolves this symbol from the supplied library's existing handle;
    # it does not dlopen a library. A fresh function view also avoids PyOpenGL's
    # implicit error checks and never changes production function attributes.
    return ctypes.CFUNCTYPE(ctypes.c_void_p)((name, library))


def _reference_handles(sim):
    context = sim._render_context_offscreen.gl_ctx
    expected_context = _pointer(context._context)
    module = sys.modules.get(type(context).__module__)
    if module is None or "EGL_DISPLAY" not in vars(module):
        expected_display = UNKNOWN
    else:
        expected_display = _pointer(vars(module)["EGL_DISPLAY"])
    return expected_display, expected_context


def observe_current_context(sim, *, query_factory=_cached_raw_query):
    """Return nullable booleans, without exposing pointer values or input data."""
    result = {
        "current_display_is_null": UNKNOWN,
        "current_context_is_null": UNKNOWN,
        "display_matches_reference": UNKNOWN,
        "context_matches_reference": UNKNOWN,
        "reference_display_available": False,
        "reference_context_available": False,
    }
    expected_display = expected_context = UNKNOWN
    try:
        expected_display, expected_context = _reference_handles(sim)
    except Exception:
        pass
    for name, expected in (("display", expected_display), ("context", expected_context)):
        available = type(expected) is int and expected != 0
        result[f"reference_{name}_available"] = available
        try:
            query = query_factory("eglGetCurrent" + name.capitalize())
            observed = _pointer(query())
        except Exception:
            continue
        result[f"current_{name}_is_null"] = observed == 0
        if available:
            result[f"{name}_matches_reference"] = observed == expected
    return result


class ContextDriftObserver:
    """Consume each named boundary once; missing entries remain Unknown."""
    def __init__(self, path, sim, *, query=observe_current_context):
        self.path = Path(path)
        self.sim = sim
        self.query = query
        self._attempted = set()
        self._started = False
        self._write_failed = False
        self._lock = threading.Lock()

    def _write(self, record):
        if self._write_failed:
            return False
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Preserve earlier artifacts if an identity is accidentally reused.
            with self.path.open("a" if self._started else "x") as stream:
                stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
            self._started = True
            return True
        except Exception:
            self._write_failed = True
            return False

    def observe(self, boundary):
        if boundary not in BOUNDARIES or self._write_failed:
            return
        with self._lock:
            if boundary in self._attempted:
                return
            self._attempted.add(boundary)
        record = {
            "schema": "qd-ed-egl-context-drift-v1", "boundary": boundary,
            "thread_id": threading.get_ident(), "native_thread_id": threading.get_native_id(),
        }
        # If an extra native query itself fails fatally, leave an explicit
        # observation-enter marker, not a misleading policy/render boundary.
        if not self._write({**record, "event": "enter", "time_unix": time.time()}):
            return
        try:
            observation = self.query(self.sim)
        except Exception:
            observation = {
                "current_display_is_null": UNKNOWN, "current_context_is_null": UNKNOWN,
                "display_matches_reference": UNKNOWN, "context_matches_reference": UNKNOWN,
                "reference_display_available": UNKNOWN, "reference_context_available": UNKNOWN,
            }
        self._write({**record, "event": "exit", "time_unix": time.time(), **observation})
