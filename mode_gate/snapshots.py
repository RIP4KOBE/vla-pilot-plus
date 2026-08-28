"""Exact post-failure simulator/controller/RNG snapshot sidecars."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import random
from typing import Any, Mapping
from uuid import uuid4

import numpy as np
import torch

from .io_utils import atomic_write_json, sha256_file
from .types import DecisionSnapshot


class DecisionSnapshotStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def capture(
        self,
        *,
        adapter: Any,
        policy: Any,
        policy_id: str,
        controller_state: Mapping[str, Any],
        provenance: Mapping[str, Any],
        observation_image: np.ndarray,
        stateful_components: Mapping[str, Any] | None = None,
        snapshot_id: str | None = None,
    ) -> DecisionSnapshot:
        capture = getattr(adapter, "capture_simulator_state", None)
        if not callable(capture):
            raise RuntimeError("adapter does not implement capture_simulator_state")
        snapshot_id = snapshot_id or uuid4().hex
        directory = self.root / snapshot_id
        staging = self.root / f".{snapshot_id}.staging"
        staging.mkdir(parents=False, exist_ok=False)
        simulator_state = capture()
        simulator_path = staging / "simulator.npz"
        with simulator_path.open("wb") as stream:
            np.savez_compressed(
                stream,
                **{
                    str(key): np.asarray(value)
                    for key, value in simulator_state.items()
                },
            )
            stream.flush()
            os.fsync(stream.fileno())

        policy_capture = getattr(policy, "capture_runtime_state", None)
        policy_state = policy_capture() if callable(policy_capture) else _known_policy_state(policy)
        adapter_capture = getattr(adapter, "capture_runtime_state", None)
        adapter_state = adapter_capture() if callable(adapter_capture) else {}
        component_states = {}
        for name, component in (stateful_components or {}).items():
            component_capture = getattr(component, "capture_runtime_state", None)
            if not callable(component_capture):
                raise RuntimeError(f"snapshot component {name!r} is not stateful")
            component_states[str(name)] = component_capture()
        rng_path = staging / "runtime.pt"
        torch.save(
            {
                "python_rng": random.getstate(),
                "numpy_rng": np.random.get_state(),
                "torch_rng": torch.get_rng_state(),
                "cuda_rng": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [],
                "policy_state": policy_state,
                "adapter_state": adapter_state,
                "component_states": component_states,
            },
            rng_path,
        )
        with rng_path.open("rb") as stream:
            os.fsync(stream.fileno())
        image = np.asarray(observation_image)
        image_path = staging / "observation.npy"
        with image_path.open("wb") as stream:
            np.save(stream, image, allow_pickle=False)
            stream.flush()
            os.fsync(stream.fileno())

        file_hashes = {
            "simulator.npz": sha256_file(simulator_path),
            "runtime.pt": sha256_file(rng_path),
            "observation.npy": sha256_file(image_path),
        }
        snapshot_hash = hashlib.sha256(
            "\n".join(f"{key}:{file_hashes[key]}" for key in sorted(file_hashes)).encode()
        ).hexdigest()
        observation_hash = hashlib.sha256(image.tobytes()).hexdigest()
        manifest = {
            "schema_version": "decision-snapshot-v2",
            "snapshot_id": snapshot_id,
            "policy_id": policy_id,
            "controller_state": dict(controller_state),
            "provenance": dict(provenance),
            "file_hashes": file_hashes,
            "snapshot_hash": snapshot_hash,
            "observation_hash": observation_hash,
        }
        atomic_write_json(staging / "manifest.json", manifest)
        os.replace(staging, directory)
        return DecisionSnapshot(
            snapshot_id=snapshot_id,
            policy_id=policy_id,
            simulator_state_path=directory / "simulator.npz",
            controller_state=dict(controller_state),
            rng_state_path=directory / "runtime.pt",
            provenance=dict(provenance),
            snapshot_hash=snapshot_hash,
            observation_hash=observation_hash,
        )

    def restore(
        self,
        snapshot_id: str,
        *,
        adapter: Any,
        policy: Any,
        stateful_components: Mapping[str, Any] | None = None,
        rgb_atol: float = 2.0,
        restore_policy_state: bool = True,
    ) -> dict[str, Any]:
        directory = self.root / snapshot_id
        import json

        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        for name, expected in manifest["file_hashes"].items():
            actual = sha256_file(directory / name)
            if actual != expected:
                raise ValueError(f"snapshot sidecar checksum mismatch: {name}")
        with np.load(directory / "simulator.npz", allow_pickle=False) as data:
            simulator_state = {key: data[key] for key in data.files}
        restore = getattr(adapter, "restore_simulator_state", None)
        if not callable(restore):
            raise RuntimeError("adapter does not implement restore_simulator_state")
        restore(simulator_state)
        runtime = torch.load(directory / "runtime.pt", map_location="cpu", weights_only=False)
        random.setstate(runtime["python_rng"])
        np.random.set_state(runtime["numpy_rng"])
        torch.set_rng_state(runtime["torch_rng"])
        if torch.cuda.is_available() and runtime["cuda_rng"]:
            torch.cuda.set_rng_state_all(runtime["cuda_rng"])
        adapter_restore = getattr(adapter, "restore_runtime_state", None)
        if callable(adapter_restore):
            adapter_restore(runtime.get("adapter_state", {}))
        elif runtime.get("adapter_state"):
            raise RuntimeError("snapshot has adapter state but adapter cannot restore it")
        if restore_policy_state:
            policy_restore = getattr(policy, "restore_runtime_state", None)
            if callable(policy_restore):
                policy_restore(runtime["policy_state"])
            else:
                _restore_known_policy_state(policy, runtime["policy_state"])
        else:
            reset = getattr(policy, "reset", None)
            if not callable(reset):
                raise RuntimeError(
                    "new-policy counterfactual requires a canonical policy reset"
                )
            reset()
        components = stateful_components or {}
        saved_components = runtime.get("component_states", {})
        if set(components) != set(saved_components):
            raise ValueError(
                "snapshot component mismatch; "
                f"saved={sorted(saved_components)}, provided={sorted(components)}"
            )
        for name, component in components.items():
            component_restore = getattr(component, "restore_runtime_state", None)
            if not callable(component_restore):
                raise RuntimeError(f"snapshot component {name!r} cannot restore state")
            component_restore(saved_components[name])

        expected_image = np.load(directory / "observation.npy", allow_pickle=False)
        actual_image = np.asarray(adapter.get_vlm_image())
        if expected_image.shape != actual_image.shape:
            raise ValueError("restored RGB shape mismatch")
        rgb_error = float(
            np.abs(expected_image.astype(np.float32) - actual_image.astype(np.float32)).mean()
        )
        if rgb_error > rgb_atol:
            raise ValueError(
                f"restored RGB mean absolute error {rgb_error:.4f} exceeds {rgb_atol}"
            )
        return {"manifest": manifest, "rgb_mean_absolute_error": rgb_error}

    def restore_simulator_only(
        self,
        snapshot_id: str,
        *,
        adapter: Any,
        rgb_atol: float = 2.0,
    ) -> dict[str, Any]:
        """Restore a teleoperation start state without injecting old policy caches."""

        import json

        directory = self.root / snapshot_id
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        for name, expected in manifest["file_hashes"].items():
            if sha256_file(directory / name) != expected:
                raise ValueError(f"snapshot sidecar checksum mismatch: {name}")
        with np.load(directory / "simulator.npz", allow_pickle=False) as data:
            simulator_state = {key: data[key] for key in data.files}
        adapter.restore_simulator_state(simulator_state)
        expected_image = np.load(directory / "observation.npy", allow_pickle=False)
        actual_image = np.asarray(adapter.get_vlm_image())
        if expected_image.shape != actual_image.shape:
            raise ValueError("restored RGB shape mismatch")
        rgb_error = float(
            np.abs(expected_image.astype(np.float32) - actual_image.astype(np.float32)).mean()
        )
        if rgb_error > rgb_atol:
            raise ValueError(
                f"restored RGB mean absolute error {rgb_error:.4f} exceeds {rgb_atol}"
            )
        return {"manifest": manifest, "rgb_mean_absolute_error": rgb_error}


def _known_policy_state(policy: Any) -> dict[str, Any]:
    names = (
        "_cached_action_chunk",
        "_stage_init_reward",
        "_last_normalized_reward",
        "_last_scale",
    )
    return {name: getattr(policy, name) for name in names if hasattr(policy, name)}


def _restore_known_policy_state(policy: Any, state: Mapping[str, Any]) -> None:
    for name, value in state.items():
        setattr(policy, name, value)


__all__ = ["DecisionSnapshotStore"]
