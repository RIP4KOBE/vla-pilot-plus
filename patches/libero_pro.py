"""Runtime compatibility fixes for the pinned LIBERO-PRO submodule."""

from __future__ import annotations

from functools import wraps
from numbers import Integral
from typing import Any


DEFAULT_LIBERO_PRO_SEED = 28


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
    "normalize_libero_pro_seed",
    "patch_environment_seed",
]
