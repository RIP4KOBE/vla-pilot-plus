"""Unapplied, single-thread diagnostic prototype; imports no graphics/CUDA library.

Install on a freshly created, current LIBERO context before instance render
observers. An installed instance is managed until destruction, not uninstalled.
Failed native cleanup is quarantined and requires ending the diagnostic process.
"""
from __future__ import annotations

import threading
import types
import weakref


_OWNER = "_diagnostic_native_render_lifetime"
_QUARANTINE = []
_EGL_OBSERVER_LOCK = threading.Lock()
_CPU_FIELDS = ("scn", "cam", "vopt", "pert")


class NativeLifetimeError(RuntimeError):
    pass


def _managed_context_finalizer(context):
    owner = vars(context).get(_OWNER)
    if owner is not None:
        owner._finalize_context(context)


class NativeRenderLifetime:
    """Own native lifetime for one stable Python MjRenderContext / MjSim pair."""

    def __init__(self, sim, *, egl, max_width=640, max_height=480):
        context = sim._render_context_offscreen
        if context is None or _OWNER in vars(context):
            raise NativeLifetimeError("existing_unmanaged_context_required")
        original = sim.render
        if ("render" in vars(sim) or not isinstance(original, types.MethodType)
                or original.__self__ is not sim):
            raise NativeLifetimeError("install_before_instance_render_observers")
        if any(name not in vars(context) for name in (*_CPU_FIELDS, "con", "gl_ctx")):
            raise NativeLifetimeError("complete_existing_context_required")
        for name in ("eglDestroyContext", "eglReleaseThread", "eglMakeCurrent"):
            if not callable(vars(egl).get(name)):
                raise NativeLifetimeError("already_loaded_egl_entrypoints_required")
        self._sim = weakref.ref(sim)
        self._context = weakref.ref(context)
        self._original_render = original.__func__
        self._gl_type = type(context.gl_ctx)
        self._device_id = context.device_id
        self._dimensions = (max_width, max_height)
        self._egl = egl
        self._thread_id = threading.get_ident()
        self._call_lock = threading.Lock()
        self._busy = False
        self._closed = False
        self._finalized = False
        self._unknown_factory_allocation = False
        self.failed = False
        self.last_cleanup_success = None
        self.events = []
        managed_type = type("DiagnosticNativeLifetime_" + type(context).__name__,
            (type(context),), {"__slots__": (), "__del__": _managed_context_finalizer})
        setattr(context, _OWNER, self)
        try:
            context.__class__ = managed_type
        except BaseException:
            delattr(context, _OWNER)
            raise NativeLifetimeError("context_instance_layout_not_supported") from None
        # No extra render lock: original MjSim.render owns its non-reentrant lock.
        # The wrapper is intentionally single-thread-only for this diagnostic.
        sim.render = self.render
        self.events.append({"event": "installed", "thread_id": self._thread_id,
            "existing_native_resources_reused_on_first_render": True})

    def _enter(self):
        if threading.get_ident() != self._thread_id:
            self.failed = True
            raise NativeLifetimeError("different_render_thread")
        if self._closed or self.failed:
            raise NativeLifetimeError("native_lifetime_closed_or_failed")
        if not self._call_lock.acquire(blocking=False):
            self.failed = True
            raise NativeLifetimeError("concurrent_or_reentrant_render")
        self._busy = True

    def _ensure_native(self, context):
        fields = vars(context)
        if "con" in fields and "gl_ctx" in fields:
            self.events.append({"event": "reuse_existing_native"})
            return
        if "con" in fields or "gl_ctx" in fields:
            raise NativeLifetimeError("incomplete_idle_native_state")
        self.events.append({"event": "native_create_enter"})
        try:
            gl = self._gl_type(max_width=self._dimensions[0], max_height=self._dimensions[1],
                device_id=self._device_id)
        except BaseException:
            # An exception before the factory returns cannot prove whether native
            # allocation occurred. Do not claim successful retirement or retry.
            self._unknown_factory_allocation = True
            raise
        context.gl_ctx = gl
        gl.make_current()
        context._set_mujoco_context_and_buffers()
        self.events.append({"event": "native_create_exit"})

    def _observed_gl_free(self, gl):
        """Observe original calls only, detecting failures swallowed by gl.free()."""
        if not _EGL_OBSERVER_LOCK.acquire(blocking=False):
            return False, {"error": "egl_observer_already_active"}
        handle = vars(gl).get("_context")
        originals, wrappers, observations = {}, {}, []
        failure = None
        try:
            for name in ("eglDestroyContext", "eglReleaseThread", "eglMakeCurrent"):
                original = vars(self._egl)[name]
                originals[name] = original
                def observed(*args, _name=name, _original=original, **kwargs):
                    record = {"call": _name, "thread_matches": threading.get_ident() == self._thread_id}
                    if _name == "eglDestroyContext":
                        record["owned_handle_matches"] = len(args) == 2 and args[1] is handle
                    observations.append(record)
                    if not record["thread_matches"]:
                        record["error_type"] = "DifferentThread"
                        raise NativeLifetimeError("egl_operation_on_different_thread")
                    try:
                        result = _original(*args, **kwargs)
                    except BaseException as error:
                        record["error_type"] = type(error).__name__
                        raise
                    record["success"] = bool(result)
                    return result
                wrappers[name] = observed
                setattr(self._egl, name, observed)
            try:
                gl.free()
            except BaseException as error:
                failure = type(error).__name__
        except BaseException as error:
            failure = type(error).__name__
        finally:
            for name, original in originals.items():
                if vars(self._egl).get(name) is wrappers.get(name):
                    setattr(self._egl, name, original)
                else:
                    failure = "EGLObserverChanged"
            _EGL_OBSERVER_LOCK.release()
        destroys = [item for item in observations if item["call"] == "eglDestroyContext"]
        releases = [item for item in observations if item["call"] == "eglReleaseThread"]
        okay = (failure is None and handle is not None and len(destroys) == 1 and len(releases) == 1
            and destroys[0].get("owned_handle_matches") is True
            and all(item.get("success") is True and item["thread_matches"] for item in observations)
            and vars(gl).get("_context") is None)
        return okay, {"observations": observations, "exception_type": failure}

    def _retire_native(self, context):
        # A replacement may have made a different GL context current. Freeing
        # this old MjrContext under it is unsafe; quarantine without native calls.
        sim = self._sim()
        if (any(name in vars(context) for name in ("con", "gl_ctx"))
                and (sim is None or vars(sim).get("_render_context_offscreen") is not context)):
            for name in ("con", "gl_ctx"):
                resource = vars(context).pop(name, None)
                if resource is not None:
                    _QUARANTINE.append(resource)
            self.failed = True
            self.last_cleanup_success = False
            self.events.append({"event": "ownership_drift_quarantined", "verified": False})
            return False
        con = vars(context).pop("con", None)
        gl = vars(context).pop("gl_ctx", None)
        if con is None and gl is None:
            if self._unknown_factory_allocation:
                self.failed = True
                self.last_cleanup_success = False
            return not self._unknown_factory_allocation
        had_con = con is not None
        okay = True
        self.events.append({"event": "native_release_enter"})
        if con is not None:
            try:
                con.free()
            except BaseException as error:
                okay = False
                _QUARANTINE.append(con)
                self.events.append({"event": "mjr_free_failed", "exception_type": type(error).__name__})
            # Matches the original update_offscreen_size free-then-delete order,
            # while this GL context is still current. Never explicitly free twice.
            con = None
        if gl is not None:
            verified, details = self._observed_gl_free(gl)
            okay = okay and verified
            self.events.append({"event": "egl_release_observed", "verified": verified, **details})
            if not verified:
                _QUARANTINE.append(gl)
        elif had_con:
            okay = False
        self.last_cleanup_success = bool(okay and not self._unknown_factory_allocation)
        self.events.append({"event": "native_release_exit", "verified": self.last_cleanup_success})
        if not self.last_cleanup_success:
            self.failed = True
        return self.last_cleanup_success

    def render(self, *args, **kwargs):
        self._enter()
        context, sim = self._context(), self._sim()
        original_error = None
        try:
            if context is None or sim is None or sim._render_context_offscreen is not context:
                raise NativeLifetimeError("managed_context_replaced")
            self._ensure_native(context)
            return self._original_render(sim, *args, **kwargs)
        except BaseException as error:
            original_error = error
            self.failed = True
            raise
        finally:
            try:
                okay = context is not None and self._retire_native(context)
                if not okay:
                    self.failed = True
                    if original_error is None:
                        raise NativeLifetimeError("native_retirement_not_verified")
                if self.failed and original_error is None:
                    raise NativeLifetimeError("failure_observed_during_render")
            except BaseException:
                self.failed = True
                if original_error is None:
                    raise
            finally:
                self._busy = False
                self._call_lock.release()

    def close(self):
        """Terminal stop, not uninstall. The safe context finalizer remains installed."""
        if self._closed:
            return
        if threading.get_ident() != self._thread_id or self._busy:
            self.failed = True
            raise NativeLifetimeError("close_requires_idle_owner_thread")
        self._closed = True
        context = self._context()
        if context is not None and not self._retire_native(context):
            self.failed = True
            raise NativeLifetimeError("native_retirement_not_verified")

    def _finalize_context(self, context):
        if self._finalized:
            return
        self._finalized = self._closed = True
        try:
            if threading.get_ident() != self._thread_id or self._busy:
                for name in ("con", "gl_ctx"):
                    resource = vars(context).pop(name, None)
                    if resource is not None:
                        _QUARANTINE.append(resource)
                        self.failed = True
                self.events.append({"event": "finalizer_wrong_thread_or_busy", "failed": self.failed})
            elif not self._retire_native(context):
                self.failed = True
        except BaseException as error:
            self.failed = True
            self.events.append({"event": "finalizer_error", "exception_type": type(error).__name__})
        finally:
            for name in _CPU_FIELDS:
                vars(context).pop(name, None)
            self.events.append({"event": "context_finalized", "failed": self.failed})

    def snapshot(self):
        context = self._context()
        return {"failed": self.failed, "closed": self._closed, "finalized": self._finalized,
            "owner_thread_id": self._thread_id, "last_cleanup_success": self.last_cleanup_success,
            "native_attributes_present": context is not None and any(name in vars(context) for name in ("con", "gl_ctx")),
            "unreturned_factory_allocation_unknown": self._unknown_factory_allocation,
            "events": [dict(item) for item in self.events]}
