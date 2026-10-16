"""Runtime compatibility fixes for the pinned LIBERO-PRO submodule."""

from __future__ import annotations

from contextlib import contextmanager
import ctypes
from functools import wraps
import logging
from numbers import Integral
from pathlib import Path
import signal
import threading
from typing import Any


DEFAULT_LIBERO_PRO_SEED = 28
LOGGER = logging.getLogger(__name__)


def configure_libero_process_resources(min_open_files: int = 65_536) -> dict[str, Any]:
    """Keep repeated simulator construction within the process resource limit."""

    import resource

    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    target = (
        int(min_open_files)
        if hard == resource.RLIM_INFINITY
        else min(int(min_open_files), hard)
    )
    if soft != resource.RLIM_INFINITY and soft < target:
        resource.setrlimit(resource.RLIMIT_NOFILE, (target, hard))
        LOGGER.info("Raised LIBERO open-file soft limit from %s to %s", soft, target)
        soft = target
    disabled = disable_mujoco_316_asset_cache()
    return {"nofile_soft": soft, "nofile_hard": hard, "asset_cache_disabled": disabled}


def disable_mujoco_316_asset_cache() -> bool:
    """Avoid the pinned MuJoCo OBJ cache-hit FILE leak without changing physics.

    In 3.1.6, LoadOBJ returns cached mesh data without reading the newly opened
    resource; mju_closeResource then frees its file_spec without fclose(fp).
    A zero-sized compiler cache keeps the normal read-and-close path in use.
    This affects model compilation only, not policy weights or simulator state.
    """

    import mujoco

    if str(mujoco.__version__) != "3.1.6":
        return False
    if getattr(mujoco, "_vls_obj_cache_disabled", False):
        return True
    root = Path(mujoco.__file__).resolve().parent
    libraries = [
        *root.glob("libmujoco.so.3.1.6"),
        *root.glob("libmujoco.3.1.6.dylib"),
        *root.glob("mujoco.dll"),
    ]
    if len(libraries) != 1:
        raise RuntimeError(f"cannot locate the pinned MuJoCo 3.1.6 library: {root}")
    native = ctypes.CDLL(str(libraries[0]))
    native.mj_globalCache.argtypes = []
    native.mj_globalCache.restype = ctypes.c_void_p
    native.mj_setCacheSize.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    native.mj_setCacheSize.restype = None
    native.mj_setCacheSize(native.mj_globalCache(), 0)
    mujoco._vls_obj_cache_disabled = True
    LOGGER.info("Disabled MuJoCo 3.1.6 compiler asset cache to prevent OBJ file leaks")
    return True


@contextmanager
def libero_initialization_deadline(seconds: float = 120.0):
    """Bound simulator initialization on the main thread; preserve outer alarms."""

    if float(seconds) <= 0:
        raise ValueError("LIBERO initialization timeout must be positive")
    if (
        threading.current_thread() is not threading.main_thread()
        or not hasattr(signal, "setitimer")
        or signal.getitimer(signal.ITIMER_REAL)[0] > 0
    ):
        yield
        return
    previous = signal.getsignal(signal.SIGALRM)

    def expired(_signum, _frame):
        raise TimeoutError(f"LIBERO environment initialization exceeded {seconds:g}s")

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, float(seconds))
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def patch_control_env_reset(
    control_env_class=None,
    randomization_error=None,
    *,
    max_attempts: int = 100,
    timeout_seconds: float = 120.0,
) -> None:
    """Retry placement errors finitely and propagate all other reset failures.

    The pinned ControlEnv.reset has a finally: continue, which suppresses even
    OSError(EMFILE), TimeoutError and KeyboardInterrupt and loops forever.
    """

    if control_env_class is None:
        from libero.libero.envs.env_wrapper import ControlEnv

        control_env_class = ControlEnv
    if randomization_error is None:
        from robosuite.utils.errors import RandomizationError

        randomization_error = RandomizationError
    if max_attempts <= 0 or timeout_seconds <= 0:
        raise ValueError("LIBERO reset limits must be positive")
    if getattr(control_env_class, "_vls_bounded_reset", False):
        return

    @wraps(control_env_class.reset)
    def bounded_reset(self):
        with libero_initialization_deadline(timeout_seconds):
            for attempt in range(max_attempts):
                try:
                    return self.env.reset()
                except randomization_error:
                    if attempt + 1 == max_attempts:
                        LOGGER.error("LIBERO reset exhausted %s placement attempts", max_attempts)
                        raise
                    if attempt == 0:
                        LOGGER.warning("Retrying LIBERO placement with bounded reset attempts")

    control_env_class.reset = bounded_reset
    control_env_class._vls_bounded_reset = True


def normalize_libero_pro_seed(seed: Any) -> int | None:
    """Return the deterministic seed intended by the pinned LIBERO-PRO code.

    The upstream ``create_env`` implementation accidentally uses the ``int``
    *type* as its missing-value default (``configs.get("seed", int)``), while
    its own docstring specifies 28.  Treat that exact sentinel as the intended
    default and otherwise accept only integral values (including NumPy integer
    scalars).
    """

    if seed is None:
        return None
    if seed is int:
        return DEFAULT_LIBERO_PRO_SEED
    if isinstance(seed, bool) or not isinstance(seed, Integral):
        raise TypeError(
            "LIBERO-PRO seed must be an integer, None, or the pinned upstream "
            f"int sentinel; got {type(seed).__name__}"
        )
    return int(seed)


def patch_environment_seed(perturbation_module: Any) -> None:
    """Normalize the pinned upstream seed before Python ``random.seed``."""

    cls = getattr(perturbation_module, "EnvironmentReplacePerturbator", None)
    if cls is None or getattr(cls, "_vls_python312_seed_patch", False):
        return
    original = cls.perturb

    @wraps(original)
    def compatible(self: Any, task_suite_name: str, task_name: str, seed: Any = None):
        normalized = normalize_libero_pro_seed(seed)
        return original(
            self,
            task_suite_name=task_suite_name,
            task_name=task_name,
            seed=normalized,
        )

    cls.perturb = compatible
    cls._vls_python312_seed_patch = True


__all__ = [
    "DEFAULT_LIBERO_PRO_SEED",
    "configure_libero_process_resources",
    "disable_mujoco_316_asset_cache",
    "libero_initialization_deadline",
    "normalize_libero_pro_seed",
    "patch_control_env_reset",
    "patch_environment_seed",
]
