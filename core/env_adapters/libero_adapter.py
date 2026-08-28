#!/usr/bin/env python

# Copyright 2025 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

import logging
import hashlib
import os
import sys
import yaml
import einops
import importlib.util
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from functools import partial
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union

import numpy as np
import torch
try:
    import gymnasium as gym
    from gymnasium import spaces
except ModuleNotFoundError:
    import gym
    from gym import spaces


# __file__ is in core/env_adapters/, so need .parent.parent.parent to get project root
LEROBOT_PATH = Path(__file__).parent.parent.parent / "third_party" / "lerobot" / "src"
if LEROBOT_PATH.exists() and str(LEROBOT_PATH) not in sys.path:
    sys.path.insert(0, str(LEROBOT_PATH))


# import lerobot
try:
    from lerobot.processor.pipeline import PolicyProcessorPipeline, ProcessorStep
    from lerobot.processor.env_processor import LiberoProcessorStep
    from lerobot.utils.constants import OBS_ENV_STATE, OBS_IMAGE, OBS_IMAGES, OBS_STATE, OBS_STR
except ModuleNotFoundError as exc:
    missing = exc.name or ""
    logging.getLogger(__name__).warning(
        "LeRobot processor dependencies unavailable (%s); using local LIBERO processor fallback",
        missing or "unknown module",
    )

    OBS_STR = "observation"
    OBS_ENV_STATE = OBS_STR + ".environment_state"
    OBS_STATE = OBS_STR + ".state"
    OBS_IMAGE = OBS_STR + ".image"
    OBS_IMAGES = OBS_IMAGE + "s"

    class ProcessorStep:
        pass

    class PolicyProcessorPipeline:
        def __init__(self, steps):
            self.steps = steps

        def __call__(self, transition):
            for step in self.steps:
                transition = step(transition)
            return transition

    class LiberoProcessorStep(ProcessorStep):
        def __call__(self, observation):
            return self.observation(observation)

        def observation(self, observation):
            processed_obs = observation.copy()
            for key in list(processed_obs.keys()):
                if key.startswith(f"{OBS_IMAGES}."):
                    processed_obs[key] = torch.flip(processed_obs[key], dims=[2, 3])

            if "observation.robot_state" in processed_obs:
                robot_state = processed_obs.pop("observation.robot_state")
                eef_pos = robot_state["eef"]["pos"]
                eef_quat = robot_state["eef"]["quat"]
                gripper_qpos = robot_state["gripper"]["qpos"]
                eef_axisangle = self._quat2axisangle(eef_quat)
                state = torch.cat((eef_pos, eef_axisangle, gripper_qpos), dim=-1).float()
                if state.dim() == 1:
                    state = state.unsqueeze(0)
                processed_obs[OBS_STATE] = state
            return processed_obs

        def _quat2axisangle(self, quat):
            if not isinstance(quat, torch.Tensor):
                raise TypeError(f"_quat2axisangle expected a torch.Tensor, got {type(quat)}")
            if quat.ndim != 2 or quat.shape[1] != 4:
                raise ValueError(f"_quat2axisangle expected shape (B, 4), got {tuple(quat.shape)}")

            quat = quat.to(dtype=torch.float32)
            device = quat.device
            batch_size = quat.shape[0]
            w = quat[:, 3].clamp(-1.0, 1.0)
            den = torch.sqrt(torch.clamp(1.0 - w * w, min=0.0))
            result = torch.zeros((batch_size, 3), device=device)
            mask = den > 1e-10
            if mask.any():
                angle = 2.0 * torch.acos(w[mask])
                axis = quat[mask, :3] / den[mask].unsqueeze(1)
                result[mask] = axis * angle.unsqueeze(1)
            return result

# Import LIBERO-PRO benchmark
LIBERO_PRO_PATH = Path(__file__).parent.parent.parent / "third_party" / "libero_pro"
if str(LIBERO_PRO_PATH) not in sys.path:
    sys.path.insert(0, str(LIBERO_PRO_PATH))
LIBERO_PATH = Path(__file__).parent.parent.parent / "third_party" / "libero"
if LIBERO_PATH.exists() and str(LIBERO_PATH) not in sys.path:
    sys.path.insert(0, str(LIBERO_PATH))
from libero.libero import benchmark, get_libero_path
import libero.libero as _libero_module
from libero.libero.envs import OffScreenRenderEnv

if os.environ.get("MUJOCO_GL", "").lower() == "egl":
    from patches.robosuite_egl import apply_robosuite_egl_compat

    apply_robosuite_egl_compat()


# vls
from .base_adapter import BaseEnvAdapter, Pose3D, CameraParams, TrackedObject, InteractableObject


# Import logging utility
from utils.logging_utils import SteerLogger
# Create logger instance
log = SteerLogger("LiberoAdapter")


# MuJoCo keeps randomized fixture placement and several domain parameters on
# ``MjModel`` rather than ``MjData``. A flattened/qpos/qvel snapshot therefore
# is not sufficient for exact cross-process replay: a freshly constructed
# LIBERO-PRO environment can have identical data state but different static
# fixture poses. Keep this list explicit so topology/derived arrays are never
# overwritten accidentally.
_MUJOCO_MODEL_REPLAY_FIELDS = (
    "body_pos",
    "body_quat",
    "body_ipos",
    "body_iquat",
    "body_mass",
    "body_inertia",
    "jnt_pos",
    "jnt_axis",
    "jnt_range",
    "jnt_stiffness",
    "dof_damping",
    "dof_frictionloss",
    "dof_armature",
    "geom_pos",
    "geom_quat",
    "geom_size",
    "geom_friction",
    "geom_solmix",
    "geom_solref",
    "geom_solimp",
    "geom_margin",
    "geom_gap",
    "geom_rgba",
    "site_pos",
    "site_quat",
    "site_size",
    "site_rgba",
    "cam_pos",
    "cam_quat",
    "cam_fovy",
    "light_pos",
    "light_dir",
    "light_ambient",
    "light_diffuse",
    "light_specular",
    "actuator_dynprm",
    "actuator_gainprm",
    "actuator_biasprm",
    "actuator_gear",
    "actuator_ctrlrange",
    "actuator_forcerange",
    "eq_data",
    "eq_solref",
    "eq_solimp",
    "eq_active",
    "mat_rgba",
    "mat_emission",
    "mat_specular",
    "mat_shininess",
    "mat_reflectance",
    "mat_texrepeat",
    "mat_texuniform",
    "mat_texid",
)
_MUJOCO_MODEL_REQUIRED_FIELDS = frozenset({"body_pos", "body_quat"})
_MUJOCO_MODEL_INVENTORY_KEY = "model__captured_fields_json"


def _capture_mujoco_model_state(
    model: Any,
    destination: Dict[str, np.ndarray],
) -> None:
    """Capture writable model inputs needed for exact cross-process replay."""

    import json

    captured: list[str] = []
    for name in _MUJOCO_MODEL_REPLAY_FIELDS:
        if not hasattr(model, name):
            continue
        value = np.asarray(getattr(model, name))
        if value.dtype == object:
            raise TypeError(f"unsupported MuJoCo model field dtype: {name}")
        destination[f"model__{name}"] = value.copy()
        captured.append(name)
    missing = sorted(_MUJOCO_MODEL_REQUIRED_FIELDS - set(captured))
    if missing:
        raise RuntimeError(
            "MuJoCo model is missing exact-replay fields: " + ", ".join(missing)
        )
    encoded = json.dumps(captured, separators=(",", ":")).encode("utf-8")
    destination[_MUJOCO_MODEL_INVENTORY_KEY] = np.frombuffer(
        encoded, dtype=np.uint8
    ).copy()


def _restore_mujoco_model_state(
    model: Any,
    state: Mapping[str, np.ndarray],
) -> None:
    """Restore captured model inputs, rejecting legacy/incompatible state."""

    import json

    if _MUJOCO_MODEL_INVENTORY_KEY not in state:
        raise ValueError(
            "LIBERO snapshot predates MuJoCo model-state capture and cannot be "
            "used for exact cross-process replay"
        )
    encoded = bytes(
        np.asarray(state[_MUJOCO_MODEL_INVENTORY_KEY], dtype=np.uint8)
    ).decode("utf-8")
    fields = json.loads(encoded)
    if (
        not isinstance(fields, list)
        or len(fields) != len(set(fields))
        or any(not isinstance(name, str) for name in fields)
    ):
        raise ValueError("snapshot MuJoCo model inventory is malformed")
    unknown = sorted(set(fields) - set(_MUJOCO_MODEL_REPLAY_FIELDS))
    missing = sorted(_MUJOCO_MODEL_REQUIRED_FIELDS - set(fields))
    if unknown or missing:
        raise ValueError(
            "snapshot MuJoCo model inventory is incompatible; "
            f"unknown={unknown}, missing={missing}"
        )
    for name in fields:
        key = f"model__{name}"
        if key not in state or not hasattr(model, name):
            raise ValueError(f"snapshot MuJoCo model field disappeared: {name}")
        current = np.asarray(getattr(model, name))
        stored = np.asarray(state[key])
        if current.shape != stored.shape or current.dtype != stored.dtype:
            raise ValueError(
                f"snapshot MuJoCo model field mismatch for {name}: "
                f"expected {current.shape}/{current.dtype}, "
                f"got {stored.shape}/{stored.dtype}"
            )
        if not current.flags.writeable:
            raise ValueError(f"MuJoCo model field is not writable: {name}")
        current[...] = stored
        if not np.array_equal(current, stored, equal_nan=True):
            raise ValueError(f"MuJoCo model field failed to restore: {name}")



def _convert_nested_dict(d, add_batch_dim: bool = True):
    """Convert nested dict with numpy arrays to torch tensors.

    Args:
        d: Nested dict with numpy arrays
        add_batch_dim: If True, add batch dimension to tensors (B=1)
    """
    result = {}
    for k, v in d.items():
        if isinstance(v, dict):
            result[k] = _convert_nested_dict(v, add_batch_dim)
        elif isinstance(v, np.ndarray):
            t = torch.from_numpy(v)
            if add_batch_dim:
                t = t.unsqueeze(0)  # Add batch dim: (D,) -> (1, D)
            result[k] = t
        else:
            result[k] = v
    return result


def _capture_runtime_fields(
    owner: Any,
    *,
    prefix: str,
    destination: Dict[str, np.ndarray],
) -> None:
    """Capture numeric Python-side simulator state without pickle payloads."""

    import json

    none_names: list[str] = []
    for name, value in vars(owner).items():
        key = f"{prefix}__{name}"
        if value is None:
            none_names.append(name)
        elif isinstance(value, np.ndarray) and value.dtype != object:
            destination[key] = value.copy()
        elif isinstance(value, (bool, int, float, np.generic)):
            destination[key] = np.asarray([value])
    encoded = json.dumps(sorted(none_names)).encode("utf-8")
    destination[f"{prefix}__none_names_json"] = np.frombuffer(
        encoded, dtype=np.uint8
    ).copy()


def _restore_runtime_fields(
    owner: Any,
    state: Mapping[str, np.ndarray],
    *,
    prefix: str,
) -> None:
    """Restore fields captured by :func:`_capture_runtime_fields`."""

    import json

    none_key = f"{prefix}__none_names_json"
    if none_key in state:
        encoded = bytes(np.asarray(state[none_key], dtype=np.uint8)).decode("utf-8")
        for name in json.loads(encoded):
            if hasattr(owner, name):
                setattr(owner, name, None)

    field_prefix = f"{prefix}__"
    for key, stored in state.items():
        if not key.startswith(field_prefix) or key == none_key:
            continue
        name = key[len(field_prefix) :]
        if not hasattr(owner, name):
            raise ValueError(f"snapshot runtime field disappeared: {prefix}.{name}")
        current = getattr(owner, name)
        value = np.asarray(stored)
        if isinstance(current, np.ndarray):
            # Some Robosuite fields (notably gripper.current_action) change
            # shape after their first control call.  Restoring the captured
            # array object is the correct pre-call state in that case.
            setattr(owner, name, value.copy())
        elif isinstance(current, (bool, int, float, np.generic)):
            scalar = value.reshape(-1)[0].item()
            setattr(owner, name, type(current)(scalar))
        elif current is None:
            # The field was numeric when captured and became None later.  Use a
            # detached array so replay cannot mutate the stored sidecar value.
            setattr(owner, name, value.copy())
        else:
            raise ValueError(f"unsupported runtime field type: {prefix}.{name}")


def _clone_runtime_value(value: Any) -> Any:
    """Clone adapter cache state for the checksummed runtime sidecar."""

    import copy

    if isinstance(value, torch.Tensor):
        return value.detach().cpu().clone()
    if isinstance(value, np.ndarray):
        return value.copy()
    if isinstance(value, Mapping):
        return {key: _clone_runtime_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clone_runtime_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_clone_runtime_value(item) for item in value)
    return copy.deepcopy(value)


def _file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _optional_file_sha256(path: str | Path | None) -> str:
    """Hash real suite resources while allowing dependency-isolation test doubles."""

    if not path:
        return ""
    resolved = Path(path)
    return _file_sha256(resolved) if resolved.is_file() else ""


# LIBERO_PRO perturbation module
perturbation_module = None
PERTURBATION_AVAILABLE = False

try:
    _perturbation_path = LIBERO_PRO_PATH / "perturbation.py"
    if _perturbation_path.exists():
        spec = importlib.util.spec_from_file_location("perturbation", _perturbation_path)
        perturbation_module = importlib.util.module_from_spec(spec)
        sys.modules['perturbation'] = perturbation_module  # Add to sys.modules
        spec.loader.exec_module(perturbation_module)
        from patches.libero_pro import (
            DEFAULT_LIBERO_PRO_SEED,
            normalize_libero_pro_seed,
            patch_environment_seed,
        )

        patch_environment_seed(perturbation_module)
        PERTURBATION_AVAILABLE = True
        log.info(f"Loaded perturbation module from {_perturbation_path}")
    else:
        log.debug(f"Perturbation module not found at {_perturbation_path} (optional, only needed for OOD suites)")
except Exception as e:
    log.warning(f"Could not load perturbation module: {e}")


def _parse_perturbation_type(suite_name: str) -> tuple[str, dict[str, bool]]:
    """
    Parse suite name to determine base suite and perturbation flags.

    Examples:
        - "libero_goal" -> ("libero_goal", all False)
        - "libero_goal_object" -> ("libero_goal", use_object=True)
        - "libero_goal_swap" -> ("libero_goal", use_swap=True)
        - "libero_goal_temp" -> ("libero_goal", multiple True - needs checking)

    Returns:
        (base_suite_name, perturbation_flags)
    """
    base_suites = {"libero_goal", "libero_spatial", "libero_object", "libero_10", "libero_90"}
    if suite_name in base_suites:
        return suite_name, {
            "use_environment": False,
            "use_swap": False,
            "use_object": False,
            "use_language": False,
            "use_task": False,
        }

    # Mapping of suffix to perturbation flag
    perturbation_mapping = {
        "_object": "use_object",
        "_swap": "use_swap",
        "_lan": "use_language",
        "_task": "use_task",
        "_env": "use_environment",
        "_temp": "use_temp",  # combined perturbations
    }

    flags = {
        "use_environment": False,
        "use_swap": False,
        "use_object": False,
        "use_language": False,
        "use_task": False,
    }

    base_suite = suite_name

    # Check if suite has perturbation suffix
    for suffix, flag_name in perturbation_mapping.items():
        if suite_name.endswith(suffix):
            candidate_base = suite_name[:-len(suffix)]
            if candidate_base not in base_suites:
                continue
            base_suite = candidate_base
            if flag_name == "use_temp":
                # For temp (combined), we need to check which ones are enabled
                # This will be handled by reading evaluation_config.yaml
                flags["is_temp"] = True
            else:
                flags[flag_name] = True
            break

    return base_suite, flags


def _validate_libero_pro_resource_pair(
    bddl_dir: Path,
    init_dir: Path,
    *,
    expected_init_states: int = 50,
) -> dict[str, Any]:
    """Fail closed unless a LIBERO-PRO BDDL/init pair is complete."""

    bddl_names = {path.stem for path in bddl_dir.glob("*.bddl")}
    init_paths = sorted(init_dir.glob("*.pruned_init"))
    init_names = {
        path.name[: -len(".pruned_init")]
        for path in init_paths
    }
    if not bddl_names:
        raise RuntimeError(f"LIBERO-PRO resource has no BDDL tasks: {bddl_dir}")
    if bddl_names != init_names:
        missing = sorted(bddl_names - init_names)
        extra = sorted(init_names - bddl_names)
        raise RuntimeError(
            "LIBERO-PRO BDDL/init task mismatch: "
            f"missing_init={missing}, extra_init={extra}"
        )
    counts: dict[str, int] = {}
    for path in init_paths:
        states = torch.load(path, weights_only=False)  # nosec B614
        try:
            count = len(states)
        except TypeError as exc:
            raise RuntimeError(f"invalid LIBERO-PRO init-state payload: {path}") from exc
        counts[path.name] = int(count)
        if count != expected_init_states:
            raise RuntimeError(
                f"LIBERO-PRO init-state count mismatch for {path}: "
                f"expected {expected_init_states}, got {count}"
            )
    return {
        "task_count": len(bddl_names),
        "init_state_count_per_task": expected_init_states,
    }


def _materialize_single_axis_perturbation(
    *,
    base_suite: str,
    target_suite: str,
    configs: Mapping[str, Any],
    target_bddl_dir: Path,
    target_init_dir: Path,
) -> None:
    """Generate one registered LIBERO-PRO suite without upstream `_temp` leakage.

    The pinned generator hard-codes both a stale script path and an `_temp`
    output directory.  Build both resources in an isolated staging directory,
    validate all 50 states per task, and publish the registered suffix as one
    best-effort transaction instead of mutating the third-party submodule.
    """

    import shutil
    import subprocess
    import tempfile

    if perturbation_module is None:
        raise RuntimeError("LIBERO-PRO perturbation module is unavailable")
    if target_bddl_dir.exists() or target_init_dir.exists():
        if target_bddl_dir.is_dir() and target_init_dir.is_dir():
            _validate_libero_pro_resource_pair(target_bddl_dir, target_init_dir)
            return
        raise RuntimeError(
            "refusing to overwrite a partial LIBERO-PRO resource pair: "
            f"bddl={target_bddl_dir.exists()}, init={target_init_dir.exists()}"
        )

    input_dir = Path(str(configs["bddl_files_path"]))
    generator = Path(__file__).resolve().parents[2] / "scripts" / "libero_pro_init_worker.py"
    if not input_dir.is_dir():
        raise FileNotFoundError(f"LIBERO-PRO base BDDL directory missing: {input_dir}")
    if not generator.is_file():
        raise FileNotFoundError(f"LIBERO-PRO init generator missing: {generator}")

    flags = perturbation_module.PerturbFlags(
        use_environment=bool(configs.get("use_environment", False)),
        use_swap=bool(configs.get("use_swap", False)),
        use_object=bool(configs.get("use_object", False)),
        use_language=bool(configs.get("use_language", False)),
        use_task=bool(configs.get("use_task", False)),
    )
    pipeline = perturbation_module.BDDLCombinedPerturbator(
        configs=dict(configs.get("ood_task_configs", {}))
    )
    seed = normalize_libero_pro_seed(configs.get("seed", DEFAULT_LIBERO_PRO_SEED))
    staging_root = Path(
        tempfile.mkdtemp(
            prefix=f".{target_suite}.staging-",
            dir=str(target_bddl_dir.parent),
        )
    )
    staged_bddl = staging_root / "bddl"
    staged_init = staging_root / "init"
    staged_bddl.mkdir()
    staged_init.mkdir()
    published_bddl = False
    try:
        inputs = sorted(input_dir.glob("*.bddl"))
        if not inputs:
            raise RuntimeError(f"LIBERO-PRO base suite has no BDDL files: {input_dir}")
        for source in inputs:
            content = source.read_text(encoding="utf-8")
            transformed = pipeline.perturb_content(
                content=content,
                task_suite_name=base_suite,
                task_name=source.stem,
                flags=flags,
                seed=seed,
            )
            (staged_bddl / source.name).write_text(transformed, encoding="utf-8")

        egl_device_id = int(
            configs.get(
                "render_gpu_device_id",
                os.environ.get("VLS_EGL_DEVICE_ID", "8"),
            )
        )
        for bddl_file in sorted(staged_bddl.glob("*.bddl")):
            task_digest = hashlib.sha256(
                f"{target_suite}\0{bddl_file.stem}".encode("utf-8")
            ).digest()
            task_seed = (
                int(seed or 0) + int.from_bytes(task_digest[:4], "big")
            ) % (2**32)
            subprocess.run(
                [
                    sys.executable,
                    str(generator),
                    "--bddl-file",
                    str(bddl_file),
                    "--output-file",
                    str(staged_init / f"{bddl_file.stem}.pruned_init"),
                    "--num-inits",
                    "50",
                    "--seed",
                    str(task_seed),
                    "--egl-device-id",
                    str(egl_device_id),
                ],
                check=True,
                env=os.environ.copy(),
            )
        _validate_libero_pro_resource_pair(staged_bddl, staged_init)
        os.replace(staged_bddl, target_bddl_dir)
        published_bddl = True
        os.replace(staged_init, target_init_dir)
    except BaseException:
        if published_bddl and target_bddl_dir.exists() and not staged_bddl.exists():
            os.replace(target_bddl_dir, staged_bddl)
        raise
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)


def _apply_perturbations(suite_name: str) -> tuple[str, bool]:
    """
    Apply OOD perturbations to create perturbed BDDL and init files if needed.

    Args:
        suite_name: Full suite name (e.g., "libero_goal_object", "libero_spatial_swap")
        evaluation_config_path: Path to evaluation_config.yaml

    Returns:
        Tuple of (suite_name, should_read_language_from_bddl)
        - suite_name: The suite name to use (may be modified for temp suites)
        - should_read_language_from_bddl: True if this perturbation type changes language
    """

    base_suite, flags = _parse_perturbation_type(suite_name)
    log.info(f"Parsed: base_suite='{base_suite}', flags={flags}")

    # If no perturbations needed, return original without touching the module
    if not any(flags.values()):
        log.info(f"No perturbations needed for '{suite_name}'")
        return suite_name, False

    if not PERTURBATION_AVAILABLE:
        log.warning(f"⚠ Perturbation module not available, using suite '{suite_name}' as-is")
        return suite_name, False

    # Load evaluation config
    evaluation_config_path = str(LIBERO_PRO_PATH / "evaluation_config.yaml")
    if not Path(evaluation_config_path).exists():
        log.warning(f"Warning: evaluation_config.yaml not found at {evaluation_config_path}")
        return suite_name

    with open(evaluation_config_path, "r") as f:
        configs = yaml.safe_load(f)

    # Update configs with perturbation flags
    configs.update(flags)
    # The pinned LIBERO-PRO generator has a broken missing-value default of
    # ``int`` despite documenting 28.  Always pass the seed explicitly so all
    # generated BDDL/init-state resources are deterministic.
    configs["seed"] = normalize_libero_pro_seed(
        configs.get("seed", DEFAULT_LIBERO_PRO_SEED)
    )
    configs["script_path"] = str(
        LIBERO_PRO_PATH / "notebooks" / "generate_init_states.py"
    )

    # Set paths relative to base suite
    bddl_base = Path(get_libero_path("bddl_files"))
    configs["bddl_files_path"] = str(bddl_base / base_suite)
    configs["task_suite_name"] = base_suite
    configs["init_file_dir"] = get_libero_path("init_states")

    # Resolve ood config paths relative to LIBERO-PRO directory
    if "ood_task_configs" in configs:
        for key, rel_path in configs["ood_task_configs"].items():
            configs["ood_task_configs"][key] = str(LIBERO_PRO_PATH / rel_path.lstrip("./"))

    # Handle temp (combined) perturbations
    if flags.get("is_temp"):
        # For temp suites, read actual flags from config
        for flag_key in ["use_environment", "use_swap", "use_object", "use_language", "use_task"]:
            if flag_key in configs:
                flags[flag_key] = configs[flag_key]

        # Check if environment needs to be created
        temp_bddl_path = bddl_base / f"{base_suite}_temp"
        temp_init_path = Path(get_libero_path("init_states")) / f"{base_suite}_temp"

        # Create log file content for verification
        log_content = ",".join([
            str(flags.get("use_swap", False)),
            str(flags.get("use_object", False)),
            str(flags.get("use_language", False)),
            str(flags.get("use_task", False)),
            str(flags.get("use_environment", False)),
        ])

        needs_regenerate = False
        if not temp_bddl_path.exists() or not temp_init_path.exists():
            needs_regenerate = True
        else:
            log_file = temp_bddl_path / "log.txt"
            if log_file.exists():
                with open(log_file, "r") as f:
                    existing_log = f.read().strip()
                if existing_log != log_content:
                    needs_regenerate = True
            else:
                needs_regenerate = True

        if needs_regenerate:
            log.info(f"Generating temp environment for {suite_name} with flags: {flags}")
            temp_bddl_path.mkdir(parents=True, exist_ok=True)
            temp_init_path.mkdir(parents=True, exist_ok=True)
            with open(temp_bddl_path / "log.txt", "w") as f:
                f.write(log_content)
            perturbation_module.create_env(configs=configs)

        # Check if any language-changing perturbations are enabled
        should_read_language = flags.get("use_task", False) or flags.get("use_language", False)
        return f"{base_suite}_temp", should_read_language

    # Handle single perturbation type
    else:
        # Determine perturbation suffix
        perturbation_key = None
        for key in ["use_swap", "use_object", "use_language", "use_task", "use_environment"]:
            if flags.get(key):
                perturbation_key = key
                break

        if perturbation_key:
            # Get the suffix from perturbation_mapping in config
            perturbation_mapping = configs.get("perturbation_mapping", {
                "use_environment": "env",
                "use_swap": "swap",
                "use_object": "object",
                "use_language": "lan",
                "use_task": "task",
            })
            suffix = perturbation_mapping.get(perturbation_key, "")

            # Check if perturbed environment exists
            perturbed_suite_name = f"{base_suite}_{suffix}"
            perturbed_bddl_path = bddl_base / perturbed_suite_name
            perturbed_init_path = Path(get_libero_path("init_states")) / perturbed_suite_name

            log.info(f"Target perturbed suite: {perturbed_suite_name}")
            log.info(f"   BDDL path: {perturbed_bddl_path} (exists: {perturbed_bddl_path.exists()})")
            log.info(f"   Init path: {perturbed_init_path} (exists: {perturbed_init_path.exists()})")

            if not perturbed_bddl_path.exists() or not perturbed_init_path.exists():
                log.info(f"Generating perturbed environment: {perturbed_suite_name}")
                _materialize_single_axis_perturbation(
                    base_suite=base_suite,
                    target_suite=perturbed_suite_name,
                    configs=configs,
                    target_bddl_dir=perturbed_bddl_path,
                    target_init_dir=perturbed_init_path,
                )
            else:
                _validate_libero_pro_resource_pair(
                    perturbed_bddl_path,
                    perturbed_init_path,
                )
                log.info(f"Perturbed environment already exists: {perturbed_suite_name}")

            # Determine if this perturbation type changes language
            should_read_language = perturbation_key in ["use_task", "use_language"]
            log.info(f"Should read language from BDDL: {should_read_language}")
            return perturbed_suite_name, should_read_language

    return suite_name, False


def _parse_camera_names(camera_name: str | Sequence[str]) -> list[str]:
    """Normalize camera_name into a non-empty list of strings."""
    if isinstance(camera_name, str):
        cams = [c.strip() for c in camera_name.split(",") if c.strip()]
    elif isinstance(camera_name, (list | tuple)):
        cams = [str(c).strip() for c in camera_name if str(c).strip()]
    else:
        raise TypeError(f"camera_name must be str or sequence[str], got {type(camera_name).__name__}")
    if not cams:
        raise ValueError("camera_name resolved to an empty list.")
    return cams


def _get_suite(name: str) -> benchmark.Benchmark:
    """Instantiate a LIBERO suite by name with clear validation."""
    bench = benchmark.get_benchmark_dict()
    if name not in bench:
        raise ValueError(f"Unknown LIBERO suite '{name}'. Available: {', '.join(sorted(bench.keys()))}")
    suite = bench[name]()
    if not getattr(suite, "tasks", None):
        raise ValueError(f"Suite '{name}' has no tasks.")
    return suite


def _select_task_ids(total_tasks: int, task_ids: Iterable[int] | None) -> list[int]:
    """Validate/normalize task ids. If None → all tasks."""
    if task_ids is None:
        return list(range(total_tasks))
    ids = sorted({int(t) for t in task_ids})
    for t in ids:
        if t < 0 or t >= total_tasks:
            raise ValueError(f"task_id {t} out of range [0, {total_tasks - 1}].")
    return ids


def _local_libero_root_candidates() -> list[Path]:
    """Return local LIBERO package roots that may contain bddl_files/init_files."""
    candidates: list[Path] = []
    module_file = getattr(_libero_module, "__file__", None)
    if module_file:
        candidates.append(Path(module_file).resolve().parent)

    if LIBERO_PATH.exists():
        candidates.extend(
            [
                LIBERO_PATH / "libero" / "libero",
                LIBERO_PATH / "libero",
            ]
        )

    seen: set[Path] = set()
    unique: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def _resolve_libero_resource(query_key: str, problem_folder: str, file_name: str) -> Path:
    configured_path = Path(get_libero_path(query_key)) / problem_folder / file_name
    if configured_path.exists():
        return configured_path

    resource_dir = "init_files" if query_key == "init_states" else query_key
    local_candidates = [
        root / resource_dir / problem_folder / file_name
        for root in _local_libero_root_candidates()
    ]
    for candidate in local_candidates:
        if candidate.exists():
            log.warning(
                f"LIBERO {query_key} path from user config is stale ({configured_path}); "
                f"using local package resource {candidate}"
            )
            return candidate

    searched = ", ".join(str(path) for path in [configured_path, *local_candidates])
    raise FileNotFoundError(f"LIBERO {query_key} file not found. Searched: {searched}")


def get_task_init_states(task_suite: Any, i: int) -> np.ndarray:
    init_states_path = _resolve_libero_resource(
        "init_states",
        task_suite.tasks[i].problem_folder,
        task_suite.tasks[i].init_states_file,
    )
    init_states = torch.load(init_states_path, weights_only=False)  # nosec B614
    return init_states


def get_libero_dummy_action():
    """Get dummy/no-op action, used to roll out the simulation while the robot does nothing."""
    return [0, 0, 0, 0, 0, 0, 0]


OBS_STATE_DIM = 8
ACTION_DIM = 7
AGENT_POS_LOW = -1000.0
AGENT_POS_HIGH = 1000.0
ACTION_LOW = -1.0
ACTION_HIGH = 1.0

SPATIAL_TASK_MAX_STEPS = 280 #280,  # longest training demo has 193 steps
OBJECT_TASK_MAX_STEPS = 280 #280,  # longest training demo has 254 steps
GOAL_TASK_MAX_STEPS = 300
TEN_TASK_MAX_STEPS = 520 #505,  # longest training demo has 505 steps
NINETY_TASK_MAX_STEPS = 400

TASK_SUITE_MAX_STEPS: dict[str, int] = {
    # Original LIBERO suites
    "libero_spatial": SPATIAL_TASK_MAX_STEPS,
    "libero_object": OBJECT_TASK_MAX_STEPS, # 280,  # longest training demo has 254 steps
    "libero_goal": GOAL_TASK_MAX_STEPS,  # longest training demo has 270 steps
    "libero_10": TEN_TASK_MAX_STEPS,  # longest training demo has 505 steps
    "libero_90": NINETY_TASK_MAX_STEPS,  # longest training demo has 373 steps
    # LIBERO-PRO perturbed suites (same max steps as originals)
    "libero_goal_temp": GOAL_TASK_MAX_STEPS,
    "libero_spatial_temp": SPATIAL_TASK_MAX_STEPS,
    "libero_10_temp": TEN_TASK_MAX_STEPS,
    "libero_object_temp": OBJECT_TASK_MAX_STEPS,
    "libero_goal_lan": GOAL_TASK_MAX_STEPS,
    "libero_spatial_lan": SPATIAL_TASK_MAX_STEPS,
    "libero_10_lan": TEN_TASK_MAX_STEPS,
    "libero_object_lan": OBJECT_TASK_MAX_STEPS,
    "libero_goal_object": GOAL_TASK_MAX_STEPS,
    "libero_spatial_object": SPATIAL_TASK_MAX_STEPS,
    "libero_10_object": TEN_TASK_MAX_STEPS,
    "libero_object_object": OBJECT_TASK_MAX_STEPS,
    "libero_goal_swap": GOAL_TASK_MAX_STEPS,
    "libero_spatial_swap": SPATIAL_TASK_MAX_STEPS,
    "libero_10_swap": TEN_TASK_MAX_STEPS,
    "libero_object_swap": OBJECT_TASK_MAX_STEPS,
    "libero_goal_task": GOAL_TASK_MAX_STEPS,
    "libero_spatial_task": SPATIAL_TASK_MAX_STEPS,
    "libero_10_task": TEN_TASK_MAX_STEPS,
    "libero_object_task": OBJECT_TASK_MAX_STEPS,
    "libero_goal_env": GOAL_TASK_MAX_STEPS,
    "libero_spatial_env": SPATIAL_TASK_MAX_STEPS,
    "libero_10_env": TEN_TASK_MAX_STEPS,
    "libero_object_env": OBJECT_TASK_MAX_STEPS,
}


class LiberoEnv(gym.Env):
    metadata = {"render_modes": ["rgb_array"], "render_fps": 80}

    def __init__(
        self,
        task_suite: Any,
        task_id: int,
        task_suite_name: str,
        camera_name: str | Sequence[str] = "agentview_image, robot0_eye_in_hand_image",
        obs_type: str = "pixels_agent_pos",
        render_mode: str = "rgb_array",
        observation_width: int = 256,
        observation_height: int = 256,
        visualization_width: int = 640,
        visualization_height: int = 480,
        init_states: bool = True,
        episode_index: int = 0,
        camera_name_mapping: dict[str, str] | None = None,
        num_steps_wait: int = 10,
        read_language_from_bddl: bool = False,
        max_episode_steps: int | None = None,
        auto_reset: bool = False,
        render_gpu_device_id: int = -1,
        camera_depths: bool = True,
    ):
        super().__init__()
        self.task_id = task_id
        self.obs_type = obs_type
        self.render_mode = render_mode
        self.observation_width = observation_width
        self.observation_height = observation_height
        self.visualization_width = visualization_width
        self.visualization_height = visualization_height
        self.init_states = init_states
        self.camera_name = _parse_camera_names(
            camera_name
        )  # agentview_image (main) or robot0_eye_in_hand_image (wrist)

        # Map raw camera names to "image1" and "image2".
        # The preprocessing step `preprocess_observation` will then prefix these with `.images.*`,
        # following the LeRobot convention (e.g., `observation.images.image`, `observation.images.image2`).
        # This ensures the policy consistently receives observations in the
        # expected format regardless of the original camera naming.
        if camera_name_mapping is None:
            camera_name_mapping = {
                "agentview_image": "image",
                "robot0_eye_in_hand_image": "image2",

            }
        self.camera_name_mapping = camera_name_mapping

        self.num_steps_wait = num_steps_wait

        self.episode_index = episode_index
        self.read_language_from_bddl = read_language_from_bddl
        self.auto_reset = bool(auto_reset)
        self.render_gpu_device_id = int(render_gpu_device_id)
        self.camera_depths = bool(camera_depths)
        suite_tasks = getattr(task_suite, "tasks", None)
        if suite_tasks is not None:
            task_record = suite_tasks[self.task_id]
            self.init_states_file = str(
                _resolve_libero_resource(
                    "init_states",
                    task_record.problem_folder,
                    task_record.init_states_file,
                )
            )
        elif self.init_states:
            raise ValueError("init-state rollout requires suite task metadata")
        else:
            # Import/isolation tests can replace the suite and environment with
            # minimal doubles.  Production LIBERO suites always take the branch
            # above, so exact replay still receives a non-empty file and digest.
            self.init_states_file = ""
        # Load once and keep
        self._init_states = get_task_init_states(task_suite, self.task_id) if self.init_states else None
        self._init_state_id = self.episode_index  # tie each sub-env to a fixed init state

        default_steps = 500
        self._max_episode_steps = (
            int(max_episode_steps)
            if max_episode_steps is not None
            else TASK_SUITE_MAX_STEPS.get(task_suite_name, default_steps)
        )
        self._env = self._make_envs_task(task_suite, self.task_id)
        self._last_raw_obs: dict[str, Any] | None = None
        self.bddl_sha256 = _optional_file_sha256(
            getattr(self, "bddl_file_name", None)
        )
        self.init_states_sha256 = _optional_file_sha256(self.init_states_file)

        images = {}
        for cam in self.camera_name:
            images[self.camera_name_mapping[cam]] = spaces.Box(
                low=0,
                high=255,
                shape=(self.observation_height, self.observation_width, 3),
                dtype=np.uint8,
            )

        if self.obs_type == "state":
            raise NotImplementedError(
                "The 'state' observation type is not supported in LiberoEnv. "
                "Please switch to an image-based obs_type (e.g. 'pixels', 'pixels_agent_pos')."
            )

        elif self.obs_type == "pixels":
            self.observation_space = spaces.Dict(
                {
                    "pixels": spaces.Dict(images),
                }
            )
        elif self.obs_type == "pixels_agent_pos":
            self.observation_space = spaces.Dict(
                {
                    "pixels": spaces.Dict(images),
                    "robot_state": spaces.Dict(
                        {
                            "eef": spaces.Dict(
                                {
                                    "pos": spaces.Box(low=-np.inf, high=np.inf, shape=(3,), dtype=np.float64),
                                    "quat": spaces.Box(
                                        low=-np.inf, high=np.inf, shape=(4,), dtype=np.float64
                                    ),
                                    "mat": spaces.Box(
                                        low=-np.inf, high=np.inf, shape=(3, 3), dtype=np.float64
                                    ),
                                }
                            ),
                            "gripper": spaces.Dict(
                                {
                                    "qpos": spaces.Box(
                                        low=-np.inf, high=np.inf, shape=(2,), dtype=np.float64
                                    ),
                                    "qvel": spaces.Box(
                                        low=-np.inf, high=np.inf, shape=(2,), dtype=np.float64
                                    ),
                                }
                            ),
                            "joints": spaces.Dict(
                                {
                                    "pos": spaces.Box(low=-np.inf, high=np.inf, shape=(7,), dtype=np.float64),
                                    "vel": spaces.Box(low=-np.inf, high=np.inf, shape=(7,), dtype=np.float64),
                                }
                            ),
                        }
                    ),
                }
            )

        self.action_space = spaces.Box(
            low=ACTION_LOW, high=ACTION_HIGH, shape=(ACTION_DIM,), dtype=np.float32
        )

    def render(self):
        raw_obs = self._env.env._get_observations()
        image = self._format_raw_obs(raw_obs)["pixels"]["image"]
        image = image[::-1, ::-1]  # flip both H and W for visualization
        return image

    def _make_envs_task(self, task_suite: Any, task_id: int = 0):
        task = task_suite.get_task(task_id)
        self.task = task.name
        task_bddl_file = str(_resolve_libero_resource("bddl_files", task.problem_folder, task.bddl_file))
        self.bddl_file_name = task_bddl_file

        # Only read language from BDDL if perturbation type changes language (task or language perturbations)
        if self.read_language_from_bddl:
            self.task_description = self._extract_language_from_bddl(task_bddl_file)
            if self.task_description is None:
                # Fallback to task.language if BDDL parsing fails
                log.warning(f"Failed to read language from BDDL, falling back to task.language")
                self.task_description = task.language
            else:
                log.info(f"Read language from BDDL: {self.task_description}")
        else:
            # Use original task language for perturbations that don't change language
            self.task_description = task.language

        env_args = {
            "bddl_file_name": task_bddl_file,
            "camera_heights": self.observation_height,
            "camera_widths": self.observation_width,
            "camera_depths": self.camera_depths,
            "render_gpu_device_id": self.render_gpu_device_id,
            # Keep robosuite's internal terminal horizon identical to the
            # adapter/controller timeout.  Otherwise the underlying env stops
            # at its hard-coded 1000 steps even when a caller explicitly asks
            # for a longer human-teleoperation episode.
            "horizon": self._max_episode_steps,
            "ignore_done": False,
        }
        env = OffScreenRenderEnv(**env_args)
        env.reset()
        return env

    def _extract_language_from_bddl(self, bddl_file: str) -> str | None:
        """Extract language instruction from BDDL file."""
        try:
            import re
            with open(bddl_file, 'r') as f:
                content = f.read()
            # Match (:language ...) pattern
            match = re.search(r'\(:language\s+([^\)]+)\)', content)
            if match:
                return match.group(1).strip()
        except Exception as e:
            log.warning(f"Failed to extract language from BDDL: {e}")
        return None

    def _format_raw_obs(self, raw_obs: dict[str, Any]) -> dict[str, Any]:
        """Convert raw LIBERO observation to policy-compatible format."""
        observation = {}

        for key in (
            "agentview_image",
            "robot0_eye_in_hand_image",
            "robot0_joint_pos",
            "robot0_gripper_qpos",
        ):
            if key in raw_obs:
                observation[key] = raw_obs[key]

        task_description = getattr(self, "task_description", None)
        if task_description:
            observation["task"] = task_description

        # Process images: camera_name -> mapped_name, convert to (B, C, H, W) float32 [0,1]
        for cam_name in self.camera_name:
            img = raw_obs[cam_name]
            mapped_name = self.camera_name_mapping[cam_name]

            # numpy (H, W, C) uint8 -> torch (1, C, H, W) float32
            img_tensor = torch.from_numpy(img).unsqueeze(0)  # (1, H, W, C)
            img_tensor = img_tensor.permute(0, 3, 1, 2).contiguous().float() / 255.0  # (1, C, H, W)

            observation[f"{OBS_IMAGES}.{mapped_name}"] = img_tensor

        # Robot state
        observation[f"{OBS_STR}.robot_state"] = _convert_nested_dict({
            "eef": {
                "pos": raw_obs.get("robot0_eef_pos"),
                "quat": raw_obs.get("robot0_eef_quat"),
                "mat": self._env.robots[0].controller.ee_ori_mat,
            },
            "gripper": {
                "qpos": raw_obs.get("robot0_gripper_qpos"),
                "qvel": raw_obs.get("robot0_gripper_qvel"),
            },
            "joints": {
                "pos": raw_obs.get("robot0_joint_pos"),
                "vel": raw_obs.get("robot0_joint_vel"),
            },
        })



        return observation

    def reset(self, seed=None, init_state_id: int | None = None, **kwargs):
        super().reset(seed=seed)
        if init_state_id is not None:
            requested = int(init_state_id)
            if not self.init_states or self._init_states is None:
                raise ValueError("this LIBERO environment has no init-state catalog")
            if not 0 <= requested < len(self._init_states):
                raise ValueError(
                    f"init_state_id {requested} out of range [0, {len(self._init_states) - 1}]"
                )
            self._init_state_id = requested
        self._env.seed(seed)
        raw_obs = self._env.reset()
        if self.init_states and self._init_states is not None:
            raw_obs = self._env.set_init_state(self._init_states[self._init_state_id])

        # After reset, objects may be unstable (slightly floating, intersecting, etc.).
        # Step the simulator with a no-op action for a few frames so everything settles.
        # Increasing this value can improve determinism and reproducibility across resets.
        for _ in range(self.num_steps_wait):
            raw_obs, _, _, _ = self._env.step(get_libero_dummy_action())
        self._last_raw_obs = raw_obs
        observation = self._format_raw_obs(raw_obs)
        info = {"is_success": False}
        return observation, info

    def step(self, action: np.ndarray) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        if action.ndim != 1:
            raise ValueError(
                f"Expected action to be 1-D (shape (action_dim,)), "
                f"but got shape {action.shape} with ndim={action.ndim}"
            )
        raw_obs, reward, done, info = self._env.step(action)
        self._last_raw_obs = raw_obs

        is_success = self._env.check_success()
        terminated = done or is_success
        info.update(
            {
                "task": self.task,
                "task_id": self.task_id,
                "done": done,
                "success": is_success,
            }
        )
        observation = self._format_raw_obs(raw_obs)
        if terminated:
            info["final_info"] = {
                "task": self.task,
                "task_id": self.task_id,
                "done": bool(done),
                "success": bool(is_success),
            }
            if self.auto_reset:
                self.reset()
        truncated = False
        return observation, reward, terminated, truncated, info

    def close(self):
        self._env.close()


def create_libero_envs(
    suite_name: str,
    camera_name: str | Sequence[str] = "agentview_image,robot0_eye_in_hand_image",
    auto_apply_perturbations: bool = True,
    task_ids_filter: list[int] | None = None,
    observation_width: int = 256,
    observation_height: int = 256,
    visualization_width: int = 640,
    visualization_height: int = 480,
    num_steps_wait: int = 10,
    max_episode_steps: int | None = None,
    auto_reset: bool = False,
    render_gpu_device_id: int = -1,
    camera_depths: bool = True,
) -> List["LiberoEnv"]:
    """
    Create vectorized LIBERO-PRO environments with a consistent return shape.

    Supports LIBERO-PRO perturbed suites for generalization evaluation:
    - Object perturbation: libero_goal_object, libero_spatial_object, libero_10_object, libero_object_object
    - Position perturbation: libero_goal_swap, libero_spatial_swap, libero_10_swap, libero_object_swap
    - Language perturbation: libero_goal_lan, libero_spatial_lan, libero_10_lan, libero_object_lan
    - Task perturbation: libero_goal_task, libero_spatial_task, libero_10_task, libero_object_task
    - Environment perturbation: libero_goal_env, libero_spatial_env, libero_10_env, libero_object_env
    - Combined perturbation: libero_goal_temp, libero_spatial_temp, libero_10_temp, libero_object_temp

    Args:
        task: Suite name(s) (single or comma-separated)
        camera_name: Camera name(s) to use
        auto_apply_perturbations: Automatically generate perturbed environments if needed

    Returns:
        dict[suite_name][task_id] -> vec_env (env_cls([...]) with exactly n_envs factories)
    Notes:
        - n_envs is the number of rollouts *per task* (episode_index = 0..n_envs-1).
        - `task` can be a single suite or a comma-separated list of suites.
        - You may pass `task_ids` (list[int]) inside `gym_kwargs` to restrict tasks per suite.
    """

    camera_names = _parse_camera_names(camera_name)
    suite_name = [s.strip() for s in str(suite_name).split(",") if s.strip()]
    if not suite_name:
        raise ValueError("`task` must contain at least one LIBERO suite name.")

    # Handle single suite name (convert list back to string if needed)
    suite_name_str = suite_name[0] if len(suite_name) == 1 else suite_name[0]

    log.info(f"Creating LIBERO-PRO envs | suite={suite_name_str}")
    if task_ids_filter is not None:
        log.info(f"Restricting to task_ids={task_ids_filter}")

    out: List[LiberoEnv] = []

    # Apply OOD perturbations if needed
    actual_suite_name = suite_name_str
    read_language_from_bddl = False

    if auto_apply_perturbations:
        try:
            actual_suite_name, read_language_from_bddl = _apply_perturbations(suite_name_str)
            if actual_suite_name != suite_name_str:
                log.info(f"Applied perturbations: {suite_name_str} -> {actual_suite_name}")
                log.info(f"Read language from BDDL: {read_language_from_bddl}")
        except Exception as e:
            log.warning(f"Failed to apply perturbations for {suite_name_str}: {e}")
            actual_suite_name = suite_name_str
            read_language_from_bddl = False

    suite = _get_suite(actual_suite_name)
    total = len(suite.tasks)
    selected = _select_task_ids(total, task_ids_filter)
    if not selected:
        raise ValueError(f"No tasks selected for suite '{actual_suite_name}' (available: {total}).")

    for tid in selected:
        env = LiberoEnv(
            task_suite=suite,
            task_id=tid,
            task_suite_name=actual_suite_name,
            camera_name=camera_names,
            observation_width=observation_width,
            observation_height=observation_height,
            visualization_width=visualization_width,
            visualization_height=visualization_height,
            init_states=True,
            episode_index=0,
            num_steps_wait=num_steps_wait,
            read_language_from_bddl=read_language_from_bddl,
            max_episode_steps=max_episode_steps,
            auto_reset=auto_reset,
            render_gpu_device_id=render_gpu_device_id,
            camera_depths=camera_depths,
        )
        out.append(env)
        log.info(f"Built env | suite={actual_suite_name} | task_id={tid}")

    return out


class LiberoAdapter(BaseEnvAdapter):
    def __init__(self, env: None, env_config: dict, device: str = "cuda"):
        super().__init__(env, env_config, device)

        self._env = create_libero_envs(
            env_config["suite_name"],
            env_config["camera_name"],
            env_config["auto_apply_perturbations"],
            env_config["task_ids_filter"],
            observation_width=env_config.get("observation_width", 256),
            observation_height=env_config.get("observation_height", 256),
            visualization_width=env_config.get("visualization_width", 640),
            visualization_height=env_config.get("visualization_height", 480),
            num_steps_wait=env_config.get("num_steps_wait", 10),
            max_episode_steps=env_config.get("max_episode_steps"),
            auto_reset=env_config.get("auto_reset", False),
            render_gpu_device_id=env_config.get("render_gpu_device_id", -1),
            camera_depths=env_config.get("camera_depths", True),
        )

        # LIBERO-PRO related attributes
        self.suite_name = env_config["suite_name"]
        self.task_num = len(self._env)
        self.current_task_idx = 0  # Start with first task

        # total number of episodes to collect, must divide evenly by the number of tasks for desired suites
        self.total_episodes_num = env_config.get("episode_num", self.task_num)
        assert self.total_episodes_num % self.task_num == 0, f"episode_num ({self.total_episodes_num}) must divide evenly by the number of tasks ({self.task_num})"
        self.episodes_per_task = self.total_episodes_num // self.task_num
        self.current_episode_idx = -1  # Will be incremented to 0 on first reset

        # Cache for robot state and observations
        self._last_obs = None
        self._robot_state = None
        self._last_goal_predicate_count: int | None = None

        env_preprocessor_steps: list[ProcessorStep] = []
        env_postprocessor_steps: list[ProcessorStep] = []
        env_preprocessor_steps.append(LiberoProcessorStep())
        self.env_preprocessor = PolicyProcessorPipeline(steps=env_preprocessor_steps)
        self.env_postprocessor = PolicyProcessorPipeline(steps=env_postprocessor_steps)


    def get_vlm_image(self) -> np.ndarray:
        """
        Get the current VLM image in (H, W, C) uint8 format for visualization.

        Returns image WITH flipud for correct human-viewable orientation.
        Uses visualization_width/height for higher resolution.
        """
        robosuite_env = self._get_current_robosuite_env()
        if robosuite_env is None:
            return None

        sim = robosuite_env.sim
        camera_name = self.vlm_camera or 'agentview'

        # Render at visualization resolution (e.g., 640x640)
        width = self._env_config.get('visualization_width', 640)
        height = self._env_config.get('visualization_height', 640)

        rgb = sim.render(
            camera_name=camera_name,
            width=width,
            height=height,
            depth=False
        )

        # Ensure uint8
        if rgb.dtype != np.uint8:
            if rgb.max() <= 1.0:
                rgb = (rgb * 255).astype(np.uint8)
            else:
                rgb = rgb.astype(np.uint8)

        # Flip for correct human-viewable orientation
        rgb = np.flipud(rgb).copy()
        return rgb

    def get_vlm_image_raw(self) -> np.ndarray:
        """
        Get raw VLM image WITHOUT flipping for projection calculations.
        Used internally by draw_action_trajectory_on_vlm_image.
        Uses visualization_width/height for higher resolution.
        """
        robosuite_env = self._get_current_robosuite_env()
        if robosuite_env is None:
            return None

        sim = robosuite_env.sim
        camera_name = self.vlm_camera or 'agentview'

        # Render at visualization resolution (e.g., 640x640)
        width = self._env_config.get('visualization_width', 640)
        height = self._env_config.get('visualization_height', 640)

        rgb = sim.render(
            camera_name=camera_name,
            width=width,
            height=height,
            depth=False
        )

        # Ensure uint8
        if rgb.dtype != np.uint8:
            if rgb.max() <= 1.0:
                rgb = (rgb * 255).astype(np.uint8)
            else:
                rgb = rgb.astype(np.uint8)

        # NO FLIP - return raw MuJoCo image for projection
        return rgb

    def get_policy_observation(self, sample_num: int = 1) -> Dict[str, torch.Tensor]:
        """
        Get observation in format expected by policy.

        Args:
            sample_num: Number of samples to expand batch dimension

        Returns:
            Dict with policy-expected keys (images already (B,C,H,W), state tensors)
        """
        if self._last_obs is None:
            return {}

        obs = self._last_obs.copy()

        # Task description needs to be replicated for each sample in batch
        task_desc = self._env[self.current_task_idx].task_description
        obs["task"] = [task_desc] * sample_num
        rdt_raw_obs = {
            key: obs[key]
            for key in (
                "agentview_image",
                "robot0_eye_in_hand_image",
                "robot0_joint_pos",
                "robot0_gripper_qpos",
                "task",
            )
            if key in obs
        }

        # Run preprocessor first (creates state tensor from robot_state)
        obs = self.env_preprocessor(obs)
        obs.update(rdt_raw_obs)

        # Expand batch dimension for multi-sample inference if needed
        # This must happen AFTER env_preprocessor since it creates new tensors
        if sample_num > 1:
            for key, val in obs.items():
                if isinstance(val, torch.Tensor) and val.shape[0] == 1:
                    obs[key] = val.expand(sample_num, *val.shape[1:])

        return obs

    def get_teleop_observation(
        self,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Return the pinned T2 dual-camera/state contract without stepping."""

        raw = self._get_cached_teleop_raw_obs()

        def image(name: str) -> np.ndarray:
            value = np.asarray(raw[name], dtype=np.uint8)
            if value.shape != (256, 256, 3):
                import cv2

                value = cv2.resize(value, (256, 256), interpolation=cv2.INTER_AREA)
            return np.ascontiguousarray(value)

        joints = np.asarray(raw["robot0_joint_pos"], dtype=np.float32).reshape(-1)
        gripper = np.asarray(raw["robot0_gripper_qpos"], dtype=np.float32).reshape(-1)
        if joints.shape != (7,) or gripper.size == 0:
            raise ValueError("LIBERO teleop requires 7 joints and gripper state")
        state = np.concatenate(
            [joints, np.asarray([float(gripper.mean())], dtype=np.float32)]
        )
        return (
            image("agentview_image"),
            image("robot0_eye_in_hand_image"),
            state,
            self.get_ee_pose_world().position.astype(np.float32),
        )

    def get_teleop_preview_observation(self) -> tuple[np.ndarray, np.ndarray]:
        """Return cached native-resolution camera frames for the human UI.

        These frames are display-only.  ``get_teleop_observation`` remains the
        frozen 256x256 LeRobot data contract used by :class:`DemoWriter`.
        Reading the cache also avoids a second MuJoCo render after every key.
        """

        raw = self._get_cached_teleop_raw_obs()

        def image(name: str) -> np.ndarray:
            value = np.asarray(raw[name], dtype=np.uint8)
            if value.ndim != 3 or value.shape[2] != 3:
                raise ValueError(f"teleop preview {name} must be HWC RGB")
            return np.ascontiguousarray(value)

        return image("agentview_image"), image("robot0_eye_in_hand_image")

    def _get_cached_teleop_raw_obs(self) -> dict[str, Any]:
        environment = self._env[self.current_task_idx]
        raw = getattr(environment, "_last_raw_obs", None)
        if raw is None:
            raw = self._get_raw_obs()
            environment._last_raw_obs = raw
        return raw

    def get_task_description(self) -> str:
        """Get the task description for the current task."""
        return self._env[self.current_task_idx].task_description

    # ==================== Core Robot State ====================

    def _get_current_robosuite_env(self):
        """Get the current robosuite environment."""
        return self._env[self.current_task_idx]._env

    def _get_raw_obs(self) -> dict:
        """Read raw observations without advancing the simulator."""
        robosuite_env = self._get_current_robosuite_env()
        observation_env = getattr(robosuite_env, "env", robosuite_env)
        get_observations = getattr(observation_env, "_get_observations", None)
        if not callable(get_observations):
            raise RuntimeError("LIBERO environment cannot produce a read-only observation")
        return get_observations()

    def get_ee_pose(self) -> Pose3D:
        """
        Get end-effector pose in robot base frame.
        For LIBERO, robot base is at world origin, so this is the same as world pose.
        """
        robosuite_env = self._get_current_robosuite_env()
        robot = robosuite_env.robots[0]
        controller = robot.controller

        pos = controller.ee_pos.copy()
        ori_mat = controller.ee_ori_mat.copy()

        # Convert rotation matrix to quaternion (wxyz format)
        from scipy.spatial.transform import Rotation as R
        rot = R.from_matrix(ori_mat)
        quat_xyzw = rot.as_quat()  # scipy returns xyzw
        quat_wxyz = np.array([quat_xyzw[3], quat_xyzw[0], quat_xyzw[1], quat_xyzw[2]])

        return Pose3D(position=pos, quaternion=quat_wxyz)

    def get_ee_pose_world(self) -> Pose3D:
        """
        Get end-effector pose in world frame.
        For LIBERO, robot base is at world origin.
        """
        return self.get_ee_pose()

    def get_robot_base_pose(self) -> Pose3D:
        """
        Get robot base pose in world frame.
        For LIBERO, the robot base is at the world origin.
        """
        return Pose3D(
            position=np.array([0.0, 0.0, 0.0]),
            quaternion=np.array([1.0, 0.0, 0.0, 0.0])  # Identity quaternion (wxyz)
        )

    def get_joint_positions(self) -> np.ndarray:
        """
        Get current joint positions.

        Returns:
            (7,) array of joint positions in radians
        """
        robosuite_env = self._get_current_robosuite_env()
        robot = robosuite_env.robots[0]
        return robot._joint_positions.copy()

    def get_gripper_state(self) -> float:
        """
        Get current gripper state.

        Returns:
            Gripper opening width (0 = closed, positive = open)
        """
        raw = self._get_cached_teleop_raw_obs()
        observed = np.asarray(raw.get("robot0_gripper_qpos", ()), dtype=np.float64)
        if observed.size:
            return float(observed.sum())

        robosuite_env = self._get_current_robosuite_env()
        robot = robosuite_env.robots[0]
        names = tuple(getattr(robot.gripper, "joints", ()) or ())
        values = []
        for name in names:
            joint_id = int(robosuite_env.sim.model.joint_name2id(name))
            qpos_address = int(robosuite_env.sim.model.jnt_qposadr[joint_id])
            values.append(float(robosuite_env.sim.data.qpos[qpos_address]))
        if not values:
            raise RuntimeError("LIBERO gripper state is unavailable")
        return float(sum(values))

    # ==================== Camera & Perception ====================

    def get_camera_params(self, camera_name: str) -> CameraParams:
        """
        Get camera intrinsic and extrinsic parameters from MuJoCo.

        Args:
            camera_name: Name of the camera ('agentview', 'robot0_eye_in_hand', etc.)

        Returns:
            CameraParams object with intrinsic, extrinsic, width, height
        """
        robosuite_env = self._get_current_robosuite_env()
        sim = robosuite_env.sim
        model = sim.model

        # Get camera ID from name
        try:
            cam_id = model.camera_name2id(camera_name)
        except:
            raise ValueError(f"Camera '{camera_name}' not found in MuJoCo model")

        # Get camera parameters from MuJoCo
        fovy_deg = model.cam_fovy[cam_id]  # FOV in degrees
        cam_pos = model.cam_pos[cam_id].copy()  # Camera position in world frame
        cam_quat_wxyz = model.cam_quat[cam_id].copy()  # Camera orientation (wxyz)

        # Use visualization resolution for VLM camera, observation resolution for others
        vlm_camera = self._env_config.get('vlm_camera', 'agentview')
        if camera_name == vlm_camera:
            width = self._env_config.get('visualization_width', 640)
            height = self._env_config.get('visualization_height', 640)
        else:
            width = self._env_config.get('observation_width', 256)
            height = self._env_config.get('observation_height', 256)

        # Compute intrinsic matrix from FOV
        fovy_rad = np.radians(fovy_deg)
        focal_length = (height / 2.0) / np.tan(fovy_rad / 2.0)
        cx, cy = width / 2.0, height / 2.0

        intrinsic = np.array([
            [focal_length, 0.0, cx],
            [0.0, focal_length, cy],
            [0.0, 0.0, 1.0]
        ], dtype=np.float32)

        # Compute extrinsic matrix for vis_utils.py (world-to-camera)
        # Convert quaternion to rotation matrix
        from scipy.spatial.transform import Rotation as R
        quat_xyzw = np.array([cam_quat_wxyz[1], cam_quat_wxyz[2], cam_quat_wxyz[3], cam_quat_wxyz[0]])
        rot = R.from_quat(quat_xyzw)
        R_cam_axes = rot.as_matrix()  # Camera axes in world frame

        # IMPORTANT: MuJoCo camera Z-axis points BACKWARD (opposite of OpenCV)
        # We need to flip Z-axis to match OpenCV convention (Z forward)
        R_cam_axes[:, 2] = -R_cam_axes[:, 2]

        # Build cam2world transform
        cam2world = np.eye(4, dtype=np.float32)
        cam2world[:3, :3] = R_cam_axes
        cam2world[:3, 3] = cam_pos

        # vis_utils.py and BaseAdapter.project_3d_to_2d() expect world2cam
        # So we return world2cam (inverse of cam2world)
        world2cam = np.linalg.inv(cam2world)

        extrinsic = world2cam

        return CameraParams(
            intrinsic=intrinsic,
            extrinsic=extrinsic,
            width=width,
            height=height
        )

    def get_camera_names(self) -> List[str]:
        """Get list of available camera names."""
        robosuite_env = self._get_current_robosuite_env()
        # Get camera names from the environment's camera configuration
        libero_env = self._env[self.current_task_idx]
        return list(libero_env.camera_name)

    # ==================== Scene Objects ====================

    def get_interactable_objects(self) -> List[InteractableObject]:
        """
        Get list of interactable/touchable objects in LIBERO scene.

        Filters out robot components and returns only task-relevant objects.
        """
        robosuite_env = self._get_current_robosuite_env()
        sim = robosuite_env.sim

        interactables = []
        segment_index = 1  # Start from 1 (0 reserved for background)

        # Method 1: Scan through all MuJoCo bodies and find task objects
        robot_keywords = ['panda', 'gripper', 'robot', 'mount', 'link', 'finger', 'eef', 'hand']
        env_keywords = ['world', 'floor', 'table', 'wall', 'arena']

        for body_id in range(sim.model.nbody):
            body_name = sim.model.body_id2name(body_id)
            body_name_lower = body_name.lower()

            # Skip robot components
            if any(kw in body_name_lower for kw in robot_keywords):
                continue

            # Skip environment/arena
            if any(kw in body_name_lower for kw in env_keywords):
                continue

            # This is likely a task object!
            interactables.append(InteractableObject(
                name=body_name,
                object_id=body_id,
                link_index=-1,
                segment_index=segment_index
            ))
            segment_index += 1

        # Method 2: If no objects found, try mujoco_objects attribute
        if len(interactables) == 0 and hasattr(robosuite_env, 'env') and hasattr(robosuite_env.env, 'model'):
            if hasattr(robosuite_env.env.model, 'mujoco_objects'):
                for obj_name, mujoco_obj in robosuite_env.env.model.mujoco_objects.items():
                    try:
                        body_id = sim.model.body_name2id(mujoco_obj.root_body)
                        interactables.append(InteractableObject(
                            name=obj_name,
                            object_id=body_id,
                            link_index=-1,
                            segment_index=segment_index
                        ))
                        segment_index += 1
                    except:
                        pass

        return interactables

    def get_scene_objects(self) -> List[TrackedObject]:
        """
        Get trackable objects in LIBERO scene with their world positions.
        """
        interactables = self.get_interactable_objects()
        robosuite_env = self._get_current_robosuite_env()
        sim = robosuite_env.sim

        objects = []
        for interactable in interactables:
            # Try to get object position from simulation
            # LIBERO objects are typically named like "object_name_1"
            try:
                # Get body ID from object name in simulation
                body_id = sim.model.body_name2id(interactable.name)
                body_pos = sim.data.body_xpos[body_id].copy()
                body_quat_wxyz = sim.data.body_xquat[body_id].copy()  # MuJoCo uses wxyz

                pose = Pose3D(position=body_pos, quaternion=body_quat_wxyz)

                objects.append(TrackedObject(
                    name=interactable.name,
                    pose=pose,
                    obj_ref={
                        'object_id': interactable.object_id,
                        'segment_index': interactable.segment_index
                    }
                ))
            except:
                # If object not found in sim, skip it
                continue

        return objects

    def get_object_pose(self, object_name: str) -> Optional[Pose3D]:
        """Get pose of a specific object by name."""
        objects = self.get_scene_objects()
        for obj in objects:
            if obj.name == object_name:
                return obj.pose
        return None

    def get_object_pose_by_segment(self, segment_index: int) -> Optional[Pose3D]:
        """
        Get current world pose of an object by its segment index.
        """
        objects = self.get_scene_objects()
        for obj in objects:
            if obj.obj_ref.get('segment_index') == segment_index:
                return obj.pose
        return None

    # ==================== Segmentation Processing ====================

    def process_segmentation(
        self,
        seg_image: np.ndarray,
    ) -> Tuple[np.ndarray, List[InteractableObject], Dict[int, str]]:
        """
        Process raw segmentation image to show only interactable objects.

        Args:
            seg_image: Raw segmentation image from MuJoCo (instance IDs)
                      Can be (H, W) or (H, W, 2) where channel 1 contains geom IDs

        Returns:
            processed_seg: Segmentation image with interactable object indices (background = 0)
            interactable_list: List of InteractableObject found in the image
            segment_id_to_name: Dict mapping segment index to object name
        """
        # MuJoCo segmentation might be multi-channel: [body_id, geom_id]
        # Use the second channel (geom_id) if available, which has more detail
        if seg_image.ndim == 3 and seg_image.shape[2] > 1:
            seg_ids = seg_image[:, :, 1]  # Geom ID channel
        else:
            seg_ids = seg_image if seg_image.ndim == 2 else seg_image[:, :, 0]

        # Get interactable objects
        interactables = self.get_interactable_objects()

        # Build lookup table: object_id (body_id) -> InteractableObject
        body_id_to_obj = {obj.object_id: obj for obj in interactables}

        # Create processed segmentation image (everything starts as background)
        processed_seg = np.zeros_like(seg_ids, dtype=np.int32)
        segment_id_to_name = {0: "background"}
        found_objects = []

        # Get unique IDs in the segmentation
        unique_ids = np.unique(seg_ids)

        # Access simulation
        robosuite_env = self._get_current_robosuite_env()
        sim = robosuite_env.sim

        # For each geom in the segmentation, check if it belongs to an interactable object
        for seg_id in unique_ids:
            if seg_id == 0 or seg_id == -1:  # Background
                continue

            try:
                if seg_id >= sim.model.ngeom:
                    continue

                # Get the body that owns this geom
                geom_bodyid = sim.model.geom_bodyid[seg_id]

                # Check if this body is an interactable object
                if geom_bodyid in body_id_to_obj:
                    obj = body_id_to_obj[geom_bodyid]

                    # Assign this geom's pixels to the object's segment index
                    mask = (seg_ids == seg_id)
                    processed_seg[mask] = obj.segment_index

                    if obj not in found_objects:
                        found_objects.append(obj)
                        segment_id_to_name[obj.segment_index] = obj.name
                # else: keep as background (0)

            except:
                # If any error, keep as background
                pass

        return processed_seg, found_objects, segment_id_to_name

    def _depth_to_pointcloud(self, depth: np.ndarray, camera_params: CameraParams) -> np.ndarray:
        """
        Convert depth image to 3D point cloud in world coordinates.

        Args:
            depth: Depth image (H, W) in meters
            camera_params: CameraParams object

        Returns:
            points: Point cloud (H, W, 3) in world coordinates
        """
        H, W = depth.shape

        # Get camera intrinsics
        intrinsic = camera_params.intrinsic
        fx, fy = intrinsic[0, 0], intrinsic[1, 1]
        cx, cy = intrinsic[0, 2], intrinsic[1, 2]

        # Get camera extrinsics and compute cam2world
        extrinsic = camera_params.extrinsic  # world2cam
        cam2world = np.linalg.inv(extrinsic)

        # Create pixel coordinates
        u, v = np.meshgrid(np.arange(W), np.arange(H))

        # Convert to camera space
        z = depth
        x = (u - cx) * z / fx
        y = (v - cy) * z / fy

        # Stack to get points in camera space (H, W, 3)
        points_cam = np.stack([x, y, z], axis=-1)

        # Filter invalid points
        valid_mask = (z > 0) & (z < 10.0)

        # Transform to world space
        points_cam_flat = points_cam.reshape(-1, 3)
        points_cam_homo = np.concatenate([points_cam_flat, np.ones((points_cam_flat.shape[0], 1))], axis=-1)
        points_world_homo = (points_cam_homo @ cam2world.T)[:, :3]

        # Reshape back to image shape
        points_world = points_world_homo.reshape(H, W, 3)

        # Apply valid mask
        points_full = np.zeros((H, W, 3), dtype=np.float32)
        points_full[valid_mask] = points_world[valid_mask]

        return points_full

    def get_keypoint_detection_inputs(
        self,
        camera_name: str = None
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict[int, str]]:
        """
        Get all inputs needed for keypoint detection.

        Args:
            camera_name: Name of the camera to use (default: use vlm_camera)

        Returns:
            rgb: RGB image (H, W, 3), uint8
            depth: Depth image (H, W), float32 in meters
            points: Point cloud (H, W, 3) in world coordinates
            segmentation: Processed segmentation with interactable objects only
            segment_id_to_name: Dict mapping segment index to object name
        """
        if camera_name is None:
            camera_name = self.vlm_camera or 'agentview'

        robosuite_env = self._get_current_robosuite_env()
        sim = robosuite_env.sim

        # Render RGB, depth, and segmentation
        width = self._env_config.get('visualization_width', 640)
        height = self._env_config.get('visualization_height', 640)

        # Render with depth
        rgb, depth = sim.render(
            camera_name=camera_name,
            width=width,
            height=height,
            depth=True
        )

        # Render with segmentation
        seg_raw = sim.render(
            camera_name=camera_name,
            width=width,
            height=height,
            segmentation=True
        )

        # MuJoCo returns depth in range [0, 1] normalized by near/far planes
        # Use robosuite's official depth conversion formula
        # Reference: robosuite.utils.camera_utils.get_real_depth_map
        model = sim.model
        extent = model.stat.extent
        near = model.vis.map.znear * extent  # Scale by extent!
        far = model.vis.map.zfar * extent    # Scale by extent!

        # Convert normalized depth to actual meters
        # Formula: z = near / (1 - depth * (1 - near/far))
        depth_meters = near / (1.0 - depth * (1.0 - near / far))
        depth_meters = depth_meters.astype(np.float32)

        # Process segmentation to get only interactable objects
        segmentation, interactable_list, segment_id_to_name = self.process_segmentation(seg_raw)

        # Get camera parameters
        camera_params = self.get_camera_params(camera_name)

        # Convert depth to point cloud
        points = self._depth_to_pointcloud(depth_meters, camera_params)
        # points[:, 0] -= 0.15

        # Ensure RGB is uint8
        if rgb.dtype != np.uint8:
            if rgb.max() <= 1.0:
                rgb = (rgb * 255).astype(np.uint8)
            else:
                rgb = rgb.astype(np.uint8)

        # MuJoCo renders images with origin at bottom-left
        # OpenCV/NumPy uses origin at top-left, so flip Y-axis only
        rgb = np.flipud(rgb).copy()
        depth_meters = np.flipud(depth_meters).copy()
        segmentation = np.flipud(segmentation).copy()
        points = np.flipud(points).copy()

        return rgb, depth_meters, points, segmentation, segment_id_to_name

    # ==================== Action Processing ====================

    def get_action_space_info(self) -> Dict[str, Any]:
        """Get action space information for LIBERO."""
        robosuite_env = self._get_current_robosuite_env()
        robot = robosuite_env.robots[0]
        controller = robot.controller

        return {
            'dim': 7,  # 6D pose + 1D gripper
            'type': 'delta_ee_pose',  # OSC controller uses delta control
            'bounds': (np.array([-1.0] * 7), np.array([1.0] * 7)),
            'normalized': True,
            'control_type': controller.control_type if hasattr(controller, 'control_type') else 'OSC_POSE',
            'control_dim': controller.control_dim if hasattr(controller, 'control_dim') else 6,
        }

    def delta_actions_to_ee_trajectory(
        self,
        action_sequence: Union[torch.Tensor, np.ndarray],
    ) -> torch.Tensor:
        """
        Transform delta action sequence to 3D trajectory of end-effector.

        LIBERO uses OSC (Operational Space Control) with delta EE pose:
        - action[:3]: delta position (dx, dy, dz) in world frame
        - action[3:6]: delta orientation (axis-angle or euler)
        - action[6]: gripper action

        Args:
            action_sequence: (T, action_dim) action sequence (torch.Tensor or np.ndarray)

        Returns:
            trajectory_3d: (T+1, 3) 3D position trajectory (including start point)
        """
        # Convert to torch if needed
        if isinstance(action_sequence, np.ndarray):
            action_sequence = torch.from_numpy(action_sequence).float()

        device = action_sequence.device
        dtype = action_sequence.dtype

        # Get starting position as tensor
        start_pos = torch.tensor(
            self.get_ee_pose_world().position,
            device=device,
            dtype=dtype
        )

        # Extract delta positions (T, 3)
        # For robosuite OSC, actions are typically normalized to [-1, 1]
        # The actual scale depends on controller settings
        # Default OSC position scale is around 0.05 m per unit action
        ACTION_SCALE_POS = 0.01  # meters per normalized action unit

        delta_positions = action_sequence[:, :3] * ACTION_SCALE_POS

        # Cumulative sum of deltas - differentiable operation
        cumsum_deltas = torch.cumsum(delta_positions, dim=0)  # (T, 3)

        # Build trajectory: [start_pos, start_pos + cumsum[0], start_pos + cumsum[1], ...]
        trajectory = torch.cat([
            start_pos.unsqueeze(0),           # (1, 3)
            start_pos + cumsum_deltas         # (T, 3)
        ], dim=0)  # (T+1, 3)

        return trajectory

    def capture_simulator_state(self) -> Dict[str, np.ndarray]:
        """Capture an exact MuJoCo decision state without stepping the env."""
        import json

        robosuite_env = self._get_current_robosuite_env()
        sim = robosuite_env.sim
        state: Dict[str, np.ndarray] = {
            "qpos": np.asarray(sim.data.qpos).copy(),
            "qvel": np.asarray(sim.data.qvel).copy(),
            "time": np.asarray([float(sim.data.time)], dtype=np.float64),
            "episode_step": np.asarray([self.episode_step], dtype=np.int64),
            "current_task_idx": np.asarray([self.current_task_idx], dtype=np.int64),
            "current_episode_idx": np.asarray([self.current_episode_idx], dtype=np.int64),
            "task_id_catalog": np.asarray(
                [environment.task_id for environment in self._env], dtype=np.int64
            ),
            "init_state_id": np.asarray(
                [self._env[self.current_task_idx]._init_state_id], dtype=np.int64
            ),
        }
        get_state = getattr(sim, "get_state", None)
        if callable(get_state):
            full_state = get_state()
            flatten = getattr(full_state, "flatten", None)
            flattened = flatten() if callable(flatten) else np.asarray(full_state)
            state["flattened_sim_state"] = np.asarray(flattened).copy()
        if getattr(sim.data, "act", None) is not None:
            state["act"] = np.asarray(sim.data.act).copy()
        if getattr(sim.data, "mocap_pos", None) is not None:
            state["mocap_pos"] = np.asarray(sim.data.mocap_pos).copy()
        if getattr(sim.data, "mocap_quat", None) is not None:
            state["mocap_quat"] = np.asarray(sim.data.mocap_quat).copy()
        _capture_mujoco_model_state(sim.model, state)
        raw_environment = getattr(robosuite_env, "env", robosuite_env)
        _capture_runtime_fields(
            raw_environment,
            prefix="robosuite_env",
            destination=state,
        )
        robot = robosuite_env.robots[0]
        _capture_runtime_fields(robot, prefix="robot", destination=state)
        _capture_runtime_fields(
            robot.controller,
            prefix="controller",
            destination=state,
        )
        _capture_runtime_fields(
            robot.gripper,
            prefix="gripper",
            destination=state,
        )
        environment = self._env[self.current_task_idx]
        rng = getattr(environment, "np_random", None)
        if rng is not None and hasattr(rng, "bit_generator"):
            encoded = json.dumps(rng.bit_generator.state, sort_keys=True).encode("utf-8")
            state["env_rng_json"] = np.frombuffer(encoded, dtype=np.uint8).copy()
        return state

    def capture_runtime_state(self) -> Dict[str, Any]:
        """Capture the exact cached observation consumed by the policy."""

        return {
            "last_obs": _clone_runtime_value(self._last_obs),
            "robot_state": _clone_runtime_value(self._robot_state),
            "last_goal_predicate_count": self._last_goal_predicate_count,
        }

    def restore_runtime_state(self, state: Mapping[str, Any]) -> None:
        """Restore cached policy inputs after simulator reconstruction."""

        if not state:
            return
        self._last_obs = _clone_runtime_value(state.get("last_obs"))
        self._robot_state = _clone_runtime_value(state.get("robot_state"))
        value = state.get("last_goal_predicate_count")
        self._last_goal_predicate_count = None if value is None else int(value)

    def get_progress_predicate(self) -> Dict[str, Any]:
        """Return exact monotonic progress when BDDL goal clauses advance.

        Many LIBERO tasks expose only the final clause.  In that case this
        method intentionally returns no confident stage until the clause
        becomes true, allowing the controller to use its Gemini/relation
        fallback instead of treating a sparse predicate as proof of
        stagnation.
        """

        wrapper = self._get_current_robosuite_env()
        environment = getattr(wrapper, "env", wrapper)
        parsed = getattr(environment, "parsed_problem", None)
        evaluate = getattr(environment, "_eval_predicate", None)
        if not isinstance(parsed, Mapping) or not callable(evaluate):
            return {
                "stage_id": None,
                "advanced": None,
                "source": "no_bddl_goal_predicates",
            }
        goal_states = tuple(parsed.get("goal_state", ()))
        if not goal_states:
            return {
                "stage_id": None,
                "advanced": None,
                "source": "empty_bddl_goal_predicates",
            }
        values = tuple(bool(evaluate(state)) for state in goal_states)
        completed = sum(values)
        previous = self._last_goal_predicate_count
        advanced = previous is not None and completed > previous
        self._last_goal_predicate_count = completed
        return {
            "stage_id": (
                f"bddl-goals:{completed}/{len(values)}" if advanced else None
            ),
            "advanced": True if advanced else None,
            "completed_count": completed,
            "goal_count": len(values),
            "predicate_vector": values,
            "task_success": completed == len(values),
            "source": "bddl_goal_predicates",
        }

    def restore_simulator_state(self, state: Mapping[str, np.ndarray]) -> None:
        """Restore a captured decision state and refresh cached observations."""
        import json

        task_index = int(np.asarray(state["current_task_idx"]).reshape(-1)[0])
        expected_catalog = np.asarray(
            [environment.task_id for environment in self._env], dtype=np.int64
        )
        saved_catalog = np.asarray(state.get("task_id_catalog", expected_catalog))
        if not np.array_equal(saved_catalog, expected_catalog):
            raise ValueError(
                "snapshot task catalog mismatch; recreate the adapter with the original task filter"
            )
        if not 0 <= task_index < len(self._env):
            raise ValueError(f"snapshot task index is out of range: {task_index}")
        self.current_task_idx = task_index
        robosuite_env = self._get_current_robosuite_env()
        sim = robosuite_env.sim
        qpos = np.asarray(state["qpos"])
        qvel = np.asarray(state["qvel"])
        if qpos.shape != np.asarray(sim.data.qpos).shape:
            raise ValueError("snapshot qpos shape mismatch")
        if qvel.shape != np.asarray(sim.data.qvel).shape:
            raise ValueError("snapshot qvel shape mismatch")
        set_flattened = getattr(sim, "set_state_from_flattened", None)
        if "flattened_sim_state" in state and callable(set_flattened):
            set_flattened(np.asarray(state["flattened_sim_state"]))
        else:
            sim.data.qpos[:] = qpos
            sim.data.qvel[:] = qvel
            sim.data.time = float(np.asarray(state["time"]).reshape(-1)[0])
            if "act" in state and getattr(sim.data, "act", None) is not None:
                sim.data.act[:] = np.asarray(state["act"])
            if "mocap_pos" in state and getattr(sim.data, "mocap_pos", None) is not None:
                sim.data.mocap_pos[:] = np.asarray(state["mocap_pos"])
            if "mocap_quat" in state and getattr(sim.data, "mocap_quat", None) is not None:
                sim.data.mocap_quat[:] = np.asarray(state["mocap_quat"])
        # Static fixture placements and domain parameters live on MjModel and
        # are not part of MuJoCo's flattened data state. Restore them before
        # forward() so derived body/geom transforms match the captured scene.
        _restore_mujoco_model_state(sim.model, state)
        sim.forward()
        raw_environment = getattr(robosuite_env, "env", robosuite_env)
        _restore_runtime_fields(raw_environment, state, prefix="robosuite_env")
        robot = robosuite_env.robots[0]
        _restore_runtime_fields(robot, state, prefix="robot")
        _restore_runtime_fields(robot.controller, state, prefix="controller")
        _restore_runtime_fields(robot.gripper, state, prefix="gripper")
        self.episode_step = int(np.asarray(state["episode_step"]).reshape(-1)[0])
        self.current_episode_idx = int(
            np.asarray(state["current_episode_idx"]).reshape(-1)[0]
        )
        environment = self._env[self.current_task_idx]
        if "init_state_id" in state:
            environment._init_state_id = int(
                np.asarray(state["init_state_id"]).reshape(-1)[0]
            )
        if "env_rng_json" in state:
            rng = getattr(environment, "np_random", None)
            if rng is not None and hasattr(rng, "bit_generator"):
                decoded = bytes(np.asarray(state["env_rng_json"], dtype=np.uint8)).decode(
                    "utf-8"
                )
                rng.bit_generator.state = json.loads(decoded)
        observation_env = getattr(robosuite_env, "env", robosuite_env)
        get_observations = getattr(observation_env, "_get_observations", None)
        if not callable(get_observations):
            raise RuntimeError("restored LIBERO environment cannot produce observations")
        raw_obs = get_observations()
        environment._last_raw_obs = raw_obs
        self._last_obs = environment._format_raw_obs(raw_obs)
        np.testing.assert_allclose(np.asarray(sim.data.qpos), qpos, rtol=0.0, atol=1e-10)
        np.testing.assert_allclose(np.asarray(sim.data.qvel), qvel, rtol=0.0, atol=1e-10)

    def restore_flattened_simulator_state(self, flattened: np.ndarray) -> None:
        """Restore one HDF5 replay state for deterministic demo validation."""

        robosuite_env = self._get_current_robosuite_env()
        setter = getattr(robosuite_env.sim, "set_state_from_flattened", None)
        if not callable(setter):
            raise RuntimeError("LIBERO simulator cannot restore a flattened state")
        setter(np.asarray(flattened, dtype=np.float64))
        robosuite_env.sim.forward()
        raw_obs = self._get_raw_obs()
        self._env[self.current_task_idx]._last_raw_obs = raw_obs
        self._last_obs = self._env[self.current_task_idx]._format_raw_obs(raw_obs)

    def has_forbidden_contact(self) -> bool:
        """Report configured forbidden contacts; normal grasp contacts are ignored."""
        forbidden = set(self._env_config.get("forbidden_geom_names", []))
        if not forbidden:
            return False
        sim = self._get_current_robosuite_env().sim
        for index in range(int(sim.data.ncon)):
            contact = sim.data.contact[index]
            names = {
                sim.model.geom_id2name(int(contact.geom1)),
                sim.model.geom_id2name(int(contact.geom2)),
            }
            if forbidden.intersection(name for name in names if name is not None):
                return True
        return False

    def unnormalize_action(self, action: np.ndarray) -> np.ndarray:
        """
        Unnormalize action from normalized to actual delta values.

        For LIBERO/robosuite OSC, actions are already in normalized form [-1, 1]
        and the controller handles the scaling internally.
        """
        # LIBERO OSC controller handles scaling internally, so just return as-is
        return action

    # ==================== Environment Interface ====================
    def step(self, action: torch.Tensor) -> Tuple[Dict, float, bool, bool, Dict]:
        """Step the LIBERO-PRO environment."""

        action_transition = {"action": action}
        action_transition = self.env_postprocessor(action_transition)
        action = action_transition["action"]
        # Convert gripper action to binary (-1 or 1) before exporting to NumPy.
        action = action.clone()
        action[-1] = 1 if action[-1] > 0 else -1
        # Convert to CPU / numpy. Cast to float32 first — pi05 outputs bfloat16
        # but LIBERO environments expect float32.
        action_numpy: np.ndarray = action.float().to("cpu").numpy()

        current_env = self._env[self.current_task_idx]
        observation, reward, terminated, truncated, info = current_env.step(action_numpy)
        self.episode_step += 1

        # Cache observation and robot state
        self._last_obs = observation

        # Check for truncation based on max steps
        truncated = self.episode_step >= current_env._max_episode_steps

        # Add task info to info dict
        info['task_idx'] = self.current_task_idx
        info['task_id'] = current_env.task_id
        info['task_description'] = getattr(current_env, 'task_description', '')

        return observation, reward, terminated, truncated, info

    def step_teleop(self, action: torch.Tensor) -> Tuple[Dict, float, bool, bool, Dict]:
        """Step T2 without materializing unused policy image tensors.

        Robosuite already returns the two RGB arrays needed by ``DemoWriter``.
        The normal policy path additionally converts both 512px images into
        batched float tensors on every action, even though browser teleop never
        consumes them.  Avoiding that conversion keeps simulator semantics and
        raw observations identical while shortening the interactive hot path.
        """

        transition = self.env_postprocessor({"action": action})
        processed = transition["action"].clone()
        processed[-1] = 1 if processed[-1] > 0 else -1
        action_numpy = processed.float().to("cpu").numpy()
        current_env = self._env[self.current_task_idx]
        raw_obs, reward, done, info = current_env._env.step(action_numpy)
        current_env._last_raw_obs = raw_obs
        success = bool(current_env._env.check_success())
        terminated = bool(done or success)
        self.episode_step += 1
        truncated = self.episode_step >= current_env._max_episode_steps
        info = dict(info or {})
        info.update(
            {
                "task": current_env.task,
                "task_id": current_env.task_id,
                "done": bool(done),
                "success": success,
                "task_idx": self.current_task_idx,
                "task_description": getattr(current_env, "task_description", ""),
            }
        )
        if terminated:
            info["final_info"] = {
                "task": current_env.task,
                "task_id": current_env.task_id,
                "done": bool(done),
                "success": success,
            }
        return {}, float(reward), terminated, bool(truncated), info

    def reset(self, **kwargs) -> Tuple[Dict, Dict]:
        """
        Reset the current LIBERO-PRO environment.

        Handles task switching logic:
        - After completing episodes_per_task episodes, switch to next task
        - Cycles through all tasks in order

        Returns:
            (observation, info) tuple
        """
        # Increment episode counter
        self.current_episode_idx += 1

        # Check if we need to switch to next task
        if self.current_episode_idx > 0 and self.current_episode_idx % self.episodes_per_task == 0:
            # Move to next task (cycle back to 0 if at end)
            self.current_task_idx = (self.current_task_idx + 1) % self.task_num
            log.info(f"Switching to task {self.current_task_idx} (episode {self.current_episode_idx})")

        # Reset episode step counter
        self.episode_step = 0
        self._last_goal_predicate_count = None

        # Get current environment and reset it
        current_env = self._env[self.current_task_idx]
        result = current_env.reset(**kwargs)

        # Cache robot state from observation
        if isinstance(result, tuple):
            obs, info = result
        else:
            obs, info = result, {}

        self._last_obs = obs

        # Add task info to info dict
        info['task_idx'] = self.current_task_idx
        info['task_id'] = current_env.task_id
        info['task_description'] = getattr(current_env, 'task_description', '')
        info['task_name'] = getattr(current_env, 'task', '')
        info['episode_idx'] = self.current_episode_idx
        info['init_state_id'] = int(getattr(current_env, '_init_state_id', -1))

        return obs, info

    def set_init_state_id(self, init_state_id: int) -> None:
        """Select an exact catalog init state for the next reset."""

        current = self._env[self.current_task_idx]
        if not current.init_states or current._init_states is None:
            raise ValueError("current LIBERO task has no init-state catalog")
        requested = int(init_state_id)
        if not 0 <= requested < len(current._init_states):
            raise ValueError(
                f"init_state_id {requested} out of range [0, {len(current._init_states) - 1}]"
            )
        current._init_state_id = requested

    def get_context_provenance(self) -> Dict[str, Any]:
        """Return stable policy/verifier grouping fields for the current cell."""

        current = self._env[self.current_task_idx]
        base_suite, flags = _parse_perturbation_type(str(self.suite_name))
        active_flags = sorted(name for name, enabled in flags.items() if enabled)
        variant = "+".join(active_flags) if active_flags else "base"
        return {
            # Protocol keys always use the formal base suite plus an explicit
            # perturbation variant.  Keeping the composed runtime suite in the
            # same field would make frozen-manifest lookup impossible.
            "suite": str(base_suite),
            "runtime_suite": str(self.suite_name),
            "base_suite": str(base_suite),
            "task_id": str(getattr(current, "task", current.task_id)),
            "task_index": int(current.task_id),
            "task_name": str(getattr(current, "task", "")),
            "perturbation_variant": variant,
            "init_state_id": str(getattr(current, "_init_state_id", -1)),
            "episode_id": str(self.current_episode_idx),
            "bddl_file": str(getattr(current, "bddl_file_name", "")),
            "bddl_sha256": str(getattr(current, "bddl_sha256", "")),
            "init_states_file": str(getattr(current, "init_states_file", "")),
            "init_states_sha256": str(
                getattr(current, "init_states_sha256", "")
            ),
        }

    def get_obs(self) -> Dict:
        """Get current observation."""
        if self._last_obs is not None:
            return self._last_obs
        return {}

    # ==================== Task-Specific Information ====================

    def get_task_info(self) -> Dict[str, Any]:
        """
        Get task-related information for guidance adjustment.

        Returns task-specific hints and metadata.
        """
        task_idx = self.current_task_idx
        # Get specific guide scale for this task if configured as a list
        task_guide_scales = self._env_config.get("task_guide_scales", [])
        recommended_scale = None
        if isinstance(task_guide_scales, (list, tuple)) and task_idx < len(task_guide_scales):
            recommended_scale = task_guide_scales[task_idx]

        if recommended_scale is None:
            recommended_scale = 80.0  # Default guide scale for LIBERO

        return {
            'instruction': self.get_instruction(),
            'recommended_guide_scale': recommended_scale,
            'task_type': 'manipulation',
            'requires_precision': True,
            'task_name': self._env[task_idx].task,
            'task_id': task_idx,
        }

    def get_instruction(self) -> str:
        """Get the current task instruction/description."""
        return self.get_task_description()
