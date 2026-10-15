"""N23 opt-in candidate quality; never changes provider or deployed actions."""
from dataclasses import dataclass, field
import hashlib
import inspect
import os
from pathlib import Path
import time

import numpy as np
import torch

from core.qd_executed_quality import ExecutedPrefixContract, _validate_keypoints

MODE = "actuator_clipped_provider_v1"


def _current_controller(adapter):
    try:
        wrapper = adapter._env[adapter.current_task_idx]
        env = adapter._get_current_robosuite_env()
        if env is not wrapper._env:
            raise ValueError("wrapper/environment mismatch")
        controller = env.robots[0].controller
        return wrapper, env, controller
    except (AttributeError, IndexError, TypeError) as exc:
        raise RuntimeError("N23 applicable controller unavailable") from exc


def _static_values(controller):
    cls = type(controller)
    if (cls.__module__, cls.__name__) != ("robosuite.controllers.osc", "OperationalSpaceController"):
        raise RuntimeError("N23 requires the installed OSC controller type")
    if (controller.name != "OSC_POSE" or controller.use_delta is not True
            or controller.use_ori is not True or type(controller.control_dim) is not int
            or controller.control_dim != 6 or controller.impedance_mode != "fixed"):
        raise RuntimeError("N23 requires fixed OSC_POSE delta semantics")
    values = {"controller_type": f"{cls.__module__}.{cls.__name__}",
              "name": controller.name, "use_delta": controller.use_delta,
              "use_ori": controller.use_ori, "control_dim": controller.control_dim,
              "impedance_mode": controller.impedance_mode}
    for name in ("input_min", "input_max", "output_min", "output_max"):
        array = getattr(controller, name)
        if (not isinstance(array, np.ndarray) or array.shape != (6,)
                or array.dtype.kind != "f" or not np.isfinite(array).all()):
            raise RuntimeError(f"N23 invalid controller {name}")
        values[name] = array.tolist()
        values[name + "_dtype"] = str(array.dtype)
    if values["input_min"][:3] != [-1.] * 3 or values["input_max"][:3] != [1.] * 3:
        raise RuntimeError("N23 translation input bounds must be exactly [-1,1]")
    for name in ("set_goal", "scale_action"):
        bound = getattr(controller, name)
        if getattr(bound, "__func__", None) is not getattr(cls, name):
            raise RuntimeError("N23 overridden controller method")
    return values


def _source_provenance(controller):
    result = {}
    for name in ("set_goal", "scale_action"):
        method = getattr(type(controller), name)
        path = Path(inspect.getsourcefile(method)).resolve()
        result[name] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "qualname": method.__qualname__}
    return result


@dataclass
class ActuatorClippedContract:
    base: ExecutedPrefixContract
    adapter: object = field(repr=False)
    mode: str = field(default=MODE, init=False)
    overhead_seconds: float = field(default=0., init=False)
    batches: int = field(default=0, init=False)
    candidates: int = field(default=0, init=False)
    changed_prefix_candidates: int = field(default=0, init=False)

    def __post_init__(self):
        started = time.perf_counter()
        if self.base.target_index != 0:
            raise RuntimeError("N23 requires recognized target0 provider")
        self._wrapper, self._env, self._controller = _current_controller(self.adapter)
        # LiberoEnv.reset increments this passive counter only after opt-in.
        if not hasattr(self._wrapper, "_actuator_quality_reset_generation"):
            self._wrapper._actuator_quality_reset_generation = 0
        self._methods = tuple(getattr(type(self._controller), n) for n in ("set_goal", "scale_action"))
        self.metadata = {"schema": "n23-static-actuator-snapshot-v1",
                         "semantics": _static_values(self._controller),
                         "source": _source_provenance(self._controller),
                         "context": self._context()}
        self.overhead_seconds += time.perf_counter() - started

    @property
    def target_index(self):
        return self.base.target_index

    @property
    def identity(self):
        return self.base.identity

    def _context(self):
        return {"pid": os.getpid(), "adapter_id": id(self.adapter),
                "wrapper_id": id(self._wrapper), "environment_id": id(self._env),
                "controller_id": id(self._controller), "task_index": self.adapter.current_task_idx,
                "episode_index": self.adapter.current_episode_idx,
                "inner_reset_generation": self._wrapper._actuator_quality_reset_generation}

    def validate(self, providers):
        started = time.perf_counter()
        self.base.validate(providers)
        current = _current_controller(self.adapter)
        if (any(a is not b for a, b in zip(current, (self._wrapper, self._env, self._controller)))
                or self._methods != tuple(getattr(type(self._controller), n) for n in ("set_goal", "scale_action"))
                or self._context() != self.metadata["context"]
                or _static_values(self._controller) != self.metadata["semantics"]):
            raise RuntimeError("N23 stale controller/reset/static metadata")
        self.overhead_seconds += time.perf_counter() - started

    def score(self, translations, source_origins, projected_xyz, keypoints, raw):
        started = time.perf_counter()
        quality, changed = actuator_clipped_quality(translations, source_origins, projected_xyz, keypoints, raw)
        self.batches += 1
        self.candidates += len(raw)
        self.changed_prefix_candidates += int(changed.sum().item())
        self.overhead_seconds += time.perf_counter() - started
        return quality, changed


def actuator_clipped_quality(translations, source_origins, projected_xyz, keypoints, raw):
    """Native seven-point expression; raw values retained exactly on unchanged rows."""
    _validate_keypoints(keypoints, 0)
    batch = len(raw)
    if (translations.shape != (batch, 8, 3) or projected_xyz.shape != (batch, 9, 3)
            or raw.shape != (batch,) or len(source_origins) != batch or batch == 0):
        raise ValueError("N23 native shape/origin coverage mismatch")
    if (any(v.dtype != raw.dtype or v.device != raw.device for v in (translations, projected_xyz, keypoints))
            or not raw.is_floating_point() or torch.get_default_dtype() != torch.float32):
        raise ValueError("N23 native dtype/device mismatch")
    if not all(bool(torch.isfinite(v).all()) for v in (translations, projected_xyz, keypoints, raw)):
        raise FloatingPointError("N23 nonfinite native inputs")
    changed = ((translations[:, :7] < -1) | (translations[:, :7] > 1)).any(dim=(1, 2))
    result = raw.detach().clone()
    weights = torch.tensor([1., 1., 1., 1., 3., 3., 3.], device=raw.device)
    weights = weights / weights.sum()
    for index in range(batch):
        source = source_origins[index]
        if not torch.is_tensor(source) or source.shape != (3,) or not bool(torch.isfinite(source).all()):
            raise ValueError("N23 invalid native source origin")
        origin = source.to(device=raw.device, dtype=raw.dtype)
        if not torch.equal(origin, projected_xyz[index, 0]):
            raise RuntimeError("N23 source/projected origin mismatch")
        # Verify reuse of the unchanged native projector, without a projection call.
        original = origin + torch.cumsum(translations[index] * .01, dim=0)
        if not torch.equal(original, projected_xyz[index, 1:]):
            raise RuntimeError("N23 original projection semantics mismatch")
        if bool(changed[index]):
            xyz = origin + torch.cumsum(translations[index].clamp(-1., 1.) * .01, dim=0)
            distances = torch.norm(xyz[:7].unsqueeze(0) - keypoints[0], dim=-1)
            value = -(distances ** 2 * weights).sum(dim=1)
            result[index] = value.mean().detach().to(raw.dtype)
    if not bool(torch.isfinite(result).all()):
        raise FloatingPointError("N23 nonfinite clipped quality")
    return result, changed
