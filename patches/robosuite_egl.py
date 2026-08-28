"""Compatibility patch for Robosuite's legacy PyOpenGL EGL context.

Robosuite 1.4 constructs ``eglChooseConfig`` with ``ctypes.byref(config)``.
Recent PyOpenGL releases require an actual ``EGLConfig`` array, matching the
implementation shipped by MuJoCo 3.x.  Applying this patch leaves Robosuite's
public API untouched and is safe to call more than once.
"""

from __future__ import annotations

import atexit
import ctypes


def apply_robosuite_egl_compat() -> bool:
    """Patch Robosuite's EGL constructor and return whether it was applied."""

    from OpenGL import error
    from robosuite.renderers.context import egl_context as context
    from robosuite.utils import binding_utils

    context_class = context.EGLGLContext
    if getattr(context_class, "_vls_pyopengl_compat", False):
        return False

    def create_display(device_id=0):
        """Select an EGL device independently of CUDA process visibility.

        On hgpu1 the functional headless display is EGL index 8, while policy
        workers commonly expose only CUDA device 0.  EGL and CUDA indices are
        separate namespaces in this container, so Robosuite's legacy
        membership assertion is invalid here.
        """

        all_devices = context.EGL.eglQueryDevicesEXT()
        candidates = (
            all_devices
            if int(device_id) == -1
            else all_devices[int(device_id) : int(device_id) + 1]
        )
        for device in candidates:
            display = context.EGL.eglGetPlatformDisplayEXT(
                context.EGL.EGL_PLATFORM_DEVICE_EXT,
                device,
                None,
            )
            if (
                display == context.EGL.EGL_NO_DISPLAY
                or context.EGL.eglGetError() != context.EGL.EGL_SUCCESS
            ):
                continue
            try:
                initialized = context.EGL.eglInitialize(display, None, None)
            except error.GLError:
                continue
            if (
                initialized == context.EGL.EGL_TRUE
                and context.EGL.eglGetError() == context.EGL.EGL_SUCCESS
            ):
                return display
        return context.EGL.EGL_NO_DISPLAY

    context.create_initialized_egl_device_display = create_display

    def compatible_init(self, max_width, max_height, device_id=0):
        del max_width, max_height
        self._context = None
        config_size = 1
        configs = (context.EGL.EGLConfig * config_size)()
        num_configs = ctypes.c_long()
        context.EGL.eglReleaseThread()

        if context.EGL_DISPLAY is None:
            context.EGL_DISPLAY = context.create_initialized_egl_device_display(
                device_id=device_id
            )
            if context.EGL_DISPLAY == context.EGL.EGL_NO_DISPLAY:
                raise ImportError(
                    "Cannot initialize an EGL device display for Robosuite."
                )
            atexit.register(context.EGL.eglTerminate, context.EGL_DISPLAY)

        context.EGL.eglChooseConfig(
            context.EGL_DISPLAY,
            context.EGL_ATTRIBUTES,
            configs,
            config_size,
            num_configs,
        )
        if num_configs.value < 1:
            raise RuntimeError(
                "EGL found no framebuffer configuration matching Robosuite's "
                f"attributes: {context.EGL_ATTRIBUTES}"
            )
        context.EGL.eglBindAPI(context.EGL.EGL_OPENGL_API)
        try:
            self._context = context.EGL.eglCreateContext(
                context.EGL_DISPLAY,
                configs[0],
                context.EGL.EGL_NO_CONTEXT,
                None,
            )
        except error.GLError as exc:
            raise RuntimeError("Cannot create a Robosuite EGL context") from exc
        if not self._context:
            raise RuntimeError("Cannot create a Robosuite EGL context")

    compatible_init.__name__ = "__init__"
    context_class.__init__ = compatible_init
    context_class._vls_pyopengl_compat = True
    # binding_utils imported the class into a module-level alias.  Assign it
    # explicitly so the patch also works if Robosuite changes that import.
    binding_utils.GLContext = context_class
    return True
