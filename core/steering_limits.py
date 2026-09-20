"""Absolute steering limits, applied after all retry/stage multipliers."""

import math


def bounded_steering_scales(policy, guide_scale, diversity_scale):
    guide_limit, diversity_limit = getattr(policy, "_steering_scale_limits", (80.0, 20.0))
    values = tuple(map(float, (guide_scale, diversity_scale, guide_limit, diversity_limit)))
    if any(not math.isfinite(value) or value < 0 for value in values) or min(values[2:]) <= 0:
        raise ValueError("steering scales must be finite, nonnegative, with positive limits")
    guide, diversity = min(values[0], values[2]), min(values[1], values[3])
    policy._last_steering_limits_report = {
        "requested_guide_scale": values[0], "requested_diversity_scale": values[1],
        "guide_scale": guide, "diversity_scale": diversity,
        "guide_scale_max": values[2], "diversity_scale_max": values[3],
    }
    return guide, diversity


def install_resident_steering_limits(policy):
    """Backport scale limiting to an existing loaded policy; preserve weights."""
    if getattr(policy, "_steering_limits_native", False) or getattr(policy, "_steering_limits_hook", False):
        return
    import functools
    import inspect

    original = policy.select_action
    signature = inspect.signature(original)

    @functools.wraps(original)
    def bounded(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        guide, diversity = bounded_steering_scales(
            policy, bound.arguments["guide_scale"], bound.arguments["diversity_scale"])
        bound.arguments.update(guide_scale=guide, diversity_scale=diversity)
        return original(*bound.args, **bound.kwargs)

    policy.select_action = bounded
    policy._steering_limits_hook = True
