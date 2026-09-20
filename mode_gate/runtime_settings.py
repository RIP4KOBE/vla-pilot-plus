"""Apply explicit steering requests at safe boundaries without reloading models."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from typing import Any

from .io_utils import AtomicJsonl


def apply_runtime_steering_settings(
    runner: Any, *, request_path: Path, at_episode_boundary: bool = False,
) -> dict[str, Any] | None:
    """Only change retry multipliers, never labels, policies, demos, or state.

    A request is consumed at an episode boundary, or while EXPANSION has
    already closed its factual labels and the simulator is waiting for demos.
    The complete new contract/hash travels with subsequent snapshots/labels.
    """
    path = Path(request_path)
    if not path.is_file():
        return None
    encoded = path.read_bytes()
    digest = hashlib.sha256(encoded).hexdigest()
    if getattr(runner, "_runtime_steering_request_hash", None) == digest:
        from core.steering_limits import install_resident_steering_limits
        runner.policy._steering_scale_limits = runner._runtime_steering_absolute_limits
        install_resident_steering_limits(runner.policy)
        return None
    request = json.loads(encoded)
    if request.get("schema_version") != "vls-runtime-steering-v1":
        raise ValueError("unknown runtime steering request")
    schedule = tuple(tuple(map(float, pair)) for pair in request["retry_schedule"])
    upper = float(request["guide_multiplier_upper_bound"])
    config = runner.mode_gate_config
    if (len(schedule) != config.retry_budget or not math.isfinite(upper) or upper <= 0
            or any(len(pair) != 2 or any(not math.isfinite(value) or value <= 0 for value in pair)
                   or pair[0] > upper for pair in schedule)
            or max(pair[0] for pair in schedule) != upper):
        raise ValueError("invalid bounded retry schedule")
    runtime = runner.mode_aware_runtime
    if runtime is None:
        return None
    if runtime._pending_factual:
        raise RuntimeError("cannot change steering with unfinished factual labels")
    phase = runtime.controller.state.phase.value
    if not at_episode_boundary and phase != "EXPAND":
        raise RuntimeError("steering changes require an episode or expansion boundary")
    old_schedule = tuple(tuple(map(float, level)) for level in config.retry_schedule)
    before = config.experiment_contract()
    from .experiment_contract import FixedBudgetExperimentContract
    from core.steering_limits import install_resident_steering_limits
    limits = (float(request['guide_scale_max']), float(request['diversity_scale_max']))
    if limits != (80.0, 20.0):
        raise ValueError('runtime scale limits must match the current 80/20 contract')
    after = FixedBudgetExperimentContract.from_mapping({**before.to_dict(),
        'retry_schedule': schedule, 'guide_scale_max': limits[0], 'diversity_scale_max': limits[1]})
    policy_identity, adapter_identity = id(runner.policy), id(runner.adapter)
    updated = replace(config, retry_schedule=schedule)

    # Long-lived processes may still have imports of the previous default
    # contract. Synchronize only these code-owned constants, not old artifacts
    # or any deployed verifier metadata. Old evidence keeps its original hash.
    aliases = []
    for name, module in tuple(sys.modules.items()):
        if module is None or not name.startswith("mode_gate."):
            continue
        for key, value in (("DEFAULT_RETRY_SCHEDULE_10", schedule),
                           ("FIXED_BUDGET_10_CONTRACT", after)):
            if key in vars(module):
                aliases.append((module, key, getattr(module, key)))
                setattr(module, key, value)
    try:
        updated.validate()
    except Exception:
        for module, key, value in aliases:
            setattr(module, key, value)
        raise
    runner.mode_gate_config = updated
    runner.policy._steering_scale_limits = limits
    install_resident_steering_limits(runner.policy)
    runtime.config = updated
    runtime.controller.config = updated
    runtime.gate.config = updated
    legacy_controller = getattr(runner, "mode_gate_controller", None)
    if legacy_controller is not None:
        legacy_controller.config = updated
    if getattr(runner, "cfg", None) is not None:
        runner.cfg.mode_gate.retry_schedule = [list(pair) for pair in schedule]
    assert id(runner.policy) == policy_identity and id(runner.adapter) == adapter_identity
    result = {
        "event": "WARM_STEERING_SETTINGS_APPLIED", "pid": os.getpid(),
        "event_id": f"warm-steering-{os.getpid()}-{digest}",
        "request_sha256": digest, "request_path": str(path), "phase": phase,
        "old_retry_schedule": [list(pair) for pair in old_schedule],
        "retry_schedule": [list(pair) for pair in schedule],
        "guide_multiplier_upper_bound": upper,
        "guide_scale_max": limits[0], "diversity_scale_max": limits[1],
        "old_contract_hash": before.contract_hash,
        "label_config": after.to_dict(), "label_contract_hash": after.contract_hash,
        "retry_budget": updated.retry_budget, "chunk_horizon": updated.chunk_horizon,
        "policy_object_unchanged": True, "adapter_object_unchanged": True,
        "existing_labels_modified": False,
    }
    AtomicJsonl(path.with_suffix(".events.jsonl")).append(result)
    runner._runtime_steering_request_hash = digest
    runner._runtime_steering_absolute_limits = limits
    return result


def install_warm_steering_hook(runner: Any, *, request_path: Path) -> None:
    """Backport the episode-boundary hook to an already-resident runner once."""
    if getattr(runner, "_warm_steering_hook_installed", False):
        return
    from types import MethodType

    original = runner._reload_active_deployment

    def reload_at_boundary(self):
        apply_runtime_steering_settings(self, request_path=request_path, at_episode_boundary=True)
        result = original()
        # A deployment can replace the policy object while retaining the old
        # class in an already-warm process. Apply the same caps to that object.
        apply_runtime_steering_settings(self, request_path=request_path, at_episode_boundary=True)
        return result

    runner._reload_active_deployment = MethodType(reload_at_boundary, runner)
    runner._warm_steering_hook_installed = True
