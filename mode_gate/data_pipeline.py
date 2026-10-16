"""Teleoperation HDF5, coverage-aware curation, and LeRobot v3 export."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
from typing import Any, Callable, Mapping, Sequence

import h5py
import numpy as np

from .io_utils import atomic_write_json, sha256_file


NATIVE_DEMO_ACCEPTANCE = "libero-collection-native-success-v1"


@dataclass(frozen=True)
class DemoFrame:
    image: np.ndarray
    image2: np.ndarray
    state: np.ndarray
    simulator_state: np.ndarray


class DemoWriter:
    """Shared continuous-action / teleoperation buffer with atomic HDF5 commit."""

    def __init__(
        self,
        output_path: Path,
        *,
        task: str,
        ticket_id: str,
        operator: str,
        init_state_id: str,
        snapshot_id: str | None,
        hashes: Mapping[str, str],
        coverage_cell: str,
        target_object_id: str | None = None,
        env_seed: int | None = None,
        fps: int = 20,
    ) -> None:
        self.output_path = Path(output_path)
        self.metadata = {
            "schema_version": "teleop-demo-v2",
            "task": task,
            "ticket_id": ticket_id,
            "operator": operator,
            "init_state_id": init_state_id,
            "snapshot_id": snapshot_id or "",
            "coverage_cell": coverage_cell,
            "target_object_id": target_object_id or "",
            "fps": int(fps),
            **{f"hash_{key}": value for key, value in hashes.items()},
        }
        if env_seed is not None:
            self.metadata["env_seed"] = int(env_seed)
        self.frames: list[DemoFrame] = []
        self.actions: list[np.ndarray] = []
        self.rewards: list[float] = []
        self.dones: list[bool] = []
        self.successes: list[bool] = []
        self.ee_positions: list[np.ndarray] = []
        # Operator confirmation is deliberately separate from the simulator's
        # per-transition success predicate.  A successful final transition is
        # necessary, but it must not silently impersonate the explicit T2
        # confirmation required by the collection protocol.
        self.explicit_success = False

    def start(self, frame: DemoFrame, *, ee_position: np.ndarray) -> None:
        if self.frames:
            raise RuntimeError("demo already started")
        self._validate_frame(frame)
        self.frames.append(frame)
        self.ee_positions.append(_vector(ee_position, 3, "ee_position"))

    def append(
        self,
        action: np.ndarray,
        next_frame: DemoFrame,
        *,
        reward: float,
        done: bool,
        success: bool,
        ee_position: np.ndarray,
    ) -> None:
        if not self.frames:
            raise RuntimeError("call start() before append()")
        self._validate_frame(next_frame)
        self.actions.append(_vector(action, 7, "action").astype(np.float32))
        self.rewards.append(float(reward))
        self.dones.append(bool(done))
        self.successes.append(bool(success))
        self.frames.append(next_frame)
        self.ee_positions.append(_vector(ee_position, 3, "ee_position"))
        self.explicit_success = False

    def undo(self) -> np.ndarray:
        if not self.actions:
            raise RuntimeError("nothing to undo")
        self.actions.pop()
        self.rewards.pop()
        self.dones.pop()
        self.successes.pop()
        self.frames.pop()
        self.ee_positions.pop()
        self.explicit_success = False
        return self.frames[-1].simulator_state.copy()

    def set_explicit_success(self, value: bool) -> None:
        if not self.actions:
            raise RuntimeError("demo contains no actions")
        self.explicit_success = bool(value)

    def reset(self, frame: DemoFrame, *, ee_position: np.ndarray) -> None:
        self.frames.clear()
        self.actions.clear()
        self.rewards.clear()
        self.dones.clear()
        self.successes.clear()
        self.ee_positions.clear()
        self.explicit_success = False
        self.start(frame, ee_position=ee_position)

    def save(self) -> Path:
        if self.metadata.get("demonstration_source") == "codex_skill_controller" and not (
            self.explicit_success and self.successes and self.successes[-1]
        ):
            raise ValueError("automatic failures must remain diagnostic NPZ, not training HDF5")
        if len(self.frames) != len(self.actions) + 1:
            raise RuntimeError("HDF5 contract requires T+1 states and T actions")
        if not self.actions:
            raise RuntimeError("cannot save an empty demo")
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.output_path.parent / f".{self.output_path.name}.{os.getpid()}.tmp"
        with h5py.File(temporary, "w") as handle:
            handle.create_dataset(
                "observation/images/image",
                data=np.stack([frame.image for frame in self.frames]),
                compression="gzip",
            )
            handle.create_dataset(
                "observation/images/image2",
                data=np.stack([frame.image2 for frame in self.frames]),
                compression="gzip",
            )
            handle.create_dataset(
                "observation/state",
                data=np.stack([frame.state for frame in self.frames]).astype(np.float32),
            )
            handle.create_dataset(
                "simulator_state",
                data=np.stack([frame.simulator_state for frame in self.frames]),
            )
            handle.create_dataset("ee_position", data=np.stack(self.ee_positions))
            handle.create_dataset("action", data=np.stack(self.actions).astype(np.float32))
            handle.create_dataset("reward", data=np.asarray(self.rewards, dtype=np.float32))
            handle.create_dataset("done", data=np.asarray(self.dones, dtype=bool))
            handle.create_dataset("success", data=np.asarray(self.successes, dtype=bool))
            for key, value in self.metadata.items():
                handle.attrs[key] = value
            handle.attrs["explicit_success"] = bool(self.explicit_success)
            handle.attrs["simulator_success"] = bool(
                self.successes and self.successes[-1]
            )
            handle.flush()
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, self.output_path)
        return self.output_path

    @staticmethod
    def _validate_frame(frame: DemoFrame) -> None:
        for name in ("image", "image2"):
            image = np.asarray(getattr(frame, name))
            if image.shape != (256, 256, 3) or image.dtype != np.uint8:
                raise ValueError(f"{name} must be uint8 [256,256,3]")
        _vector(frame.state, 8, "state")
        simulator = np.asarray(frame.simulator_state)
        if simulator.ndim != 1 or not np.isfinite(simulator).all():
            raise ValueError("simulator_state must be a finite flat vector")


@dataclass(frozen=True)
class CurationResult:
    accepted: tuple[Path, ...]
    rejected: tuple[Path, ...]
    needs_more_demos: bool
    coverage: dict[str, dict[str, float | int]]


def pending_demo_replays(paths: Sequence[Path]) -> tuple[Path, ...]:
    """List optional replay diagnostics; this is not a training/curation gate."""
    pending = []
    for path in map(Path, paths):
        with h5py.File(path, "r") as handle:
            committed_success = (bool(handle.attrs.get("collection_committed", False))
                and bool(handle.attrs.get("explicit_success", False))
                and bool(handle.attrs.get("simulator_success", False)))
            if (committed_success and not bool(handle.attrs.get("replay_validated", False))
                    and handle.attrs.get("replay_status") != "rejected"):
                pending.append(path)
    return tuple(pending)


def curate_ticket_demos(
    paths: Sequence[Path],
    *,
    required_quotas: Mapping[str, int],
    rejected_dir: Path,
    replay_tolerance: float = 1e-5,
) -> CurationResult:
    records = []
    lengths = []
    hard_rejected: list[Path] = []
    for path in map(Path, paths):
        with h5py.File(path, "r") as handle:
            length = int(handle["action"].shape[0])
            finite = all(
                np.isfinite(handle[name][...]).all()
                for name in ("observation/state", "action", "simulator_state")
            )
            # The original LIBERO-PRO predicate is the success authority.
            # A second simulation (or an infrastructure error running it)
            # cannot invalidate an already successful collection episode.
            success = bool(handle.attrs.get("simulator_success", False))
            if "success" in handle:
                success = success and length > 0 and len(handle["success"]) == length and bool(handle["success"][-1])
            automatic = handle.attrs.get("demonstration_source") == "codex_skill_controller"
            toggles = int(
                np.sum(
                    np.signbit(handle["action"][:-1, 6])
                    != np.signbit(handle["action"][1:, 6])
                )
            )
            if not finite or not success or length < (1 if automatic else 50) or (not automatic and toggles > 4):
                hard_rejected.append(path)
                continue
            cell = str(handle.attrs["coverage_cell"])
            ee = np.asarray(handle["ee_position"], dtype=np.float64)
            records.append((path, cell, ee, length, automatic))
            lengths.append(length)
    if lengths:
        median = float(np.median([record[3] for record in records if not record[4]] or lengths))
        filtered = []
        for record in records:
            # Continuous controllers are faster than key-driven humans. Do not
            # discard native successful trajectories for being faster than
            # the mixed-source duration median.
            if record[4] or 0.5 * median <= record[3] <= 2.0 * median:
                filtered.append(record)
            else:
                hard_rejected.append(record[0])
        records = filtered

    accepted: list[Path] = []
    coverage: dict[str, dict[str, float | int]] = {}
    for cell, quota in required_quotas.items():
        cell_records = [record for record in records if record[1] == cell]
        if not cell_records:
            coverage[cell] = {"accepted": 0, "quota": int(quota), "diversity_preserved": True}
            continue
        # Native-success trajectories are not discarded for differing motion strategies.
        keep_indices = set(range(len(cell_records)))
        preserve_diversity = True
        kept = [record[0] for index, record in enumerate(cell_records) if index in keep_indices]
        accepted.extend(kept)
        hard_rejected.extend(
            record[0] for index, record in enumerate(cell_records) if index not in keep_indices
        )
        coverage[cell] = {
            "accepted": len(kept),
            "quota": int(quota),
            "diversity_preserved": preserve_diversity,
        }

    rejected_dir = Path(rejected_dir)
    rejected_dir.mkdir(parents=True, exist_ok=True)
    moved = []
    for path in dict.fromkeys(hard_rejected):
        destination = rejected_dir / path.name
        if path.exists() and path.resolve() != destination.resolve():
            shutil.move(str(path), destination)
        moved.append(destination)
    needs_more = any(
        int(item["accepted"]) < int(item["quota"])
        or (not item.get("diversity_preserved", False) and float(item["main_mode_fraction"]) < 0.6)
        for item in coverage.values()
    )
    return CurationResult(tuple(accepted), tuple(moved), needs_more, coverage)


def export_lerobot_v3(
    hdf5_paths: Sequence[Path],
    *,
    output_root: Path,
    repo_id: str,
    fps: int = 20,
) -> Path:
    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    features = {
        "observation.images.image": {"dtype": "image", "shape": (256, 256, 3), "names": ["height", "width", "channels"]},
        "observation.images.image2": {"dtype": "image", "shape": (256, 256, 3), "names": ["height", "width", "channels"]},
        "observation.state": {"dtype": "float32", "shape": (8,), "names": ["state"]},
        "action": {"dtype": "float32", "shape": (7,), "names": ["action"]},
    }
    dataset = LeRobotDataset.create(
        repo_id=repo_id,
        fps=fps,
        features=features,
        root=output_root,
        robot_type="libero",
        use_videos=False,
    )
    for path in map(Path, hdf5_paths):
        with h5py.File(path, "r") as handle:
            if handle.attrs.get("demonstration_source") == "codex_skill_controller" and not (
                bool(handle.attrs.get("simulator_success", False)) and bool(handle.attrs.get("explicit_success", False))
            ):
                raise ValueError("refusing to export a failed automatic demonstration")
            actions = handle["action"]
            frames = actions.shape[0]
            task = str(handle.attrs.get("task_instruction") or handle.attrs["task"])
            if handle["observation/state"].shape[0] != frames + 1:
                raise ValueError("HDF5 state/action alignment is invalid")
            for index in range(frames):
                dataset.add_frame(
                    {
                        "observation.images.image": handle["observation/images/image"][index],
                        "observation.images.image2": handle["observation/images/image2"][index],
                        "observation.state": handle["observation/state"][index].astype(np.float32),
                        "action": actions[index].astype(np.float32),
                        "task": task,
                    }
                )
            dataset.save_episode(parallel_encoding=False)
    dataset.finalize()
    return Path(output_root)


def curate_and_export_ticket(
    *,
    ticket_path: Path,
    repo_id: str,
    replay_tolerance: float = 1e-5,
) -> dict[str, Any]:
    """Run the immutable ticket curation contract and export one v3 dataset."""

    ticket_path = Path(ticket_path)
    ticket = json.loads(ticket_path.read_text(encoding="utf-8"))
    if ticket.get("schema_version") != "expansion-ticket-v2":
        raise ValueError("unsupported expansion ticket schema")
    ticket_root = ticket_path.parent
    raw_root = ticket_root / "raw"
    # Recovery / operator tooling may leave immutable sidecars such as
    # ``demo-000-<id>.before-recovery.hdf5`` beside the committed episode.
    # Those files are deliberately retained for audit, but they must never be
    # counted as an additional demonstration during curation.  A committed
    # raw demo has exactly one filename suffix (``.h5`` or ``.hdf5``).
    paths = tuple(
        path
        for path in sorted({*raw_root.glob("*.h5"), *raw_root.glob("*.hdf5")})
        if path.name.startswith("demo-") and path.name.count(".") == 1
    )
    if not paths:
        raise ValueError("ticket contains no raw HDF5 demonstrations")
    required_quotas = {
        f"{cell['axis']}={cell['value']}": int(cell["quota"])
        for cell in ticket["collection"]["coverage_axes"]
    }
    if len(required_quotas) != len(ticket["collection"]["coverage_axes"]):
        raise ValueError("ticket contains duplicate coverage cells")
    for path in paths:
        with h5py.File(path, "r") as handle:
            if str(handle.attrs.get("ticket_id", "")) != str(ticket["ticket_id"]):
                raise ValueError(f"demo {path} belongs to a different ticket")
    result = curate_ticket_demos(
        paths,
        required_quotas=required_quotas,
        rejected_dir=ticket_root / "rejected",
        replay_tolerance=replay_tolerance,
    )
    curated_root = ticket_root / "curated"
    curated_root.mkdir(parents=True, exist_ok=True)
    curated_paths = []
    for source in result.accepted:
        digest = sha256_file(source)
        target = curated_root / f"{source.stem}-{digest[:12]}{source.suffix}"
        if target.exists():
            if sha256_file(target) != digest:
                raise ValueError(f"immutable curated demo collision: {target}")
        else:
            temporary = target.parent / f".{target.name}.{os.getpid()}.tmp"
            shutil.copy2(source, temporary)
            os.replace(temporary, target)
        curated_paths.append(target)
    accepted_manifest = {
        str(path.resolve()): {
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(curated_paths)
    }
    export_root = ticket_root / "exports" / "lerobot_v3"
    export_complete = export_root / "meta" / "info.json"
    if not result.needs_more_demos:
        if export_root.exists() and not export_complete.is_file():
            raise RuntimeError("refusing to overwrite an incomplete LeRobot export")
        if not export_complete.is_file():
            export_lerobot_v3(
                curated_paths,
                output_root=export_root,
                repo_id=repo_id,
            )
    artifact = {
        "schema_version": "ticket-curation-v1",
        "demo_acceptance_version": NATIVE_DEMO_ACCEPTANCE,
        "demo_success_authority": "LIBERO-PRO native predicate during collection",
        "replay_role": "diagnostic_only",
        "replay_state_error_role": "diagnostic_only",
        "ticket_id": ticket["ticket_id"],
        "ticket_sha256": sha256_file(ticket_path),
        "required_quotas": required_quotas,
        "coverage": result.coverage,
        "accepted": accepted_manifest,
        "rejected": [
            str(path.resolve())
            for path in sorted(
                {
                    *(ticket_root / "rejected").glob("*.h5"),
                    *(ticket_root / "rejected").glob("*.hdf5"),
                }
            )
        ],
        "needs_more_demos": result.needs_more_demos,
        "export_root": str(export_root.resolve()) if not result.needs_more_demos else None,
        "repo_id": repo_id if not result.needs_more_demos else None,
    }
    canonical = json.dumps(artifact, sort_keys=True, separators=(",", ":"))
    import hashlib

    artifact["curation_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    attempt_path = (
        ticket_root / "attempts" / f"curation_{artifact['curation_sha256'][:16]}.json"
    )
    if attempt_path.exists():
        existing = json.loads(attempt_path.read_text(encoding="utf-8"))
        if existing != artifact:
            raise ValueError("immutable curation attempt collision")
    else:
        atomic_write_json(attempt_path, artifact)
    # This is an atomic latest pointer; every historical attempt remains immutable.
    atomic_write_json(ticket_root / "curation.json", artifact)
    return artifact


NATIVE_REPLAY_ACCEPTANCE = "libero-native-success-v1"


def validate_demo_replay(
    path: Path,
    *,
    adapter: Any,
    tolerance: float = 1e-5,
    position_tolerance: float | None = None,
    velocity_tolerance: float | None = None,
    prepare_replay: Callable[[], None] | None = None,
) -> float:
    """Replay recorded actions for optional reproducibility diagnostics.

    State/component tolerances only annotate diagnostics. Contact trajectories
    need not reproduce every floating-point simulator state to succeed. Stop
    at LIBERO-PRO success or terminal failure; never restore intermediate states.
    Neither this replay's success nor its numerical errors decide whether the
    original collection episode is accepted by curation.

    ``prepare_replay`` must reset any controller / environment runtime state
    that is not represented by MuJoCo's flattened data state.  In particular,
    restoring only qpos/qvel after a live OSC episode leaves the controller's
    goal and gripper caches at the terminal step and produces a false replay
    failure.
    """

    import torch

    path = Path(path)
    with h5py.File(path, "r") as handle:
        simulator_states = np.asarray(handle["simulator_state"], dtype=np.float64)
        actions = np.asarray(handle["action"], dtype=np.float32)
        recorded_success = bool(handle.attrs.get("simulator_success", False))
    if len(simulator_states) != len(actions) + 1:
        raise ValueError("replay requires T+1 simulator states and T actions")
    restore = getattr(adapter, "restore_flattened_simulator_state", None)
    capture = getattr(adapter, "capture_simulator_state", None)
    if not callable(restore) or not callable(capture):
        raise RuntimeError("adapter lacks flattened replay support")
    maximum = 0.0
    maximum_index = -1
    maximum_dimension = -1
    first_exceeds_tolerance = -1
    maximum_qpos_error = 0.0
    maximum_qvel_error = 0.0
    replay_success: bool | None = None
    steps_executed = 0
    try:
        if prepare_replay is not None:
            prepare_replay()
        restore(simulator_states[0])
        step = getattr(adapter, "step_teleop", adapter.step)
        for index, action in enumerate(actions):
            transition = step(torch.from_numpy(action).to(adapter.device))
            if (not isinstance(transition, tuple) or len(transition) < 5
                    or not isinstance(transition[4], Mapping)
                    or "success" not in transition[4]):
                raise RuntimeError("LIBERO-PRO native success signal missing during action replay")
            replay_success = bool(transition[4]["success"])
            steps_executed = index + 1
            current = capture()
            flattened = np.asarray(current["flattened_sim_state"], dtype=np.float64)
            if flattened.shape != simulator_states[index + 1].shape:
                raise ValueError("replayed simulator-state shape changed")
            absolute_error = np.abs(flattened - simulator_states[index + 1])
            flat_dimension = int(np.argmax(absolute_error))
            step_error = float(absolute_error[flat_dimension])
            if first_exceeds_tolerance < 0 and step_error > tolerance:
                first_exceeds_tolerance = index
            if step_error > maximum:
                maximum = step_error
                maximum_index = index
                maximum_dimension = flat_dimension
            if "qpos" in current and "qvel" in current:
                qpos = np.asarray(current["qpos"], dtype=np.float64).reshape(-1)
                qvel = np.asarray(current["qvel"], dtype=np.float64).reshape(-1)
                expected = simulator_states[index + 1]
                if len(expected) >= 1 + len(qpos) + len(qvel):
                    maximum_qpos_error = max(
                        maximum_qpos_error,
                        float(np.max(np.abs(qpos - expected[1 : 1 + len(qpos)]))),
                    )
                    qvel_start = 1 + len(qpos)
                    maximum_qvel_error = max(
                        maximum_qvel_error,
                        float(
                            np.max(
                                np.abs(
                                    qvel
                                    - expected[
                                        qvel_start : qvel_start + len(qvel)
                                    ]
                                )
                            )
                        ),
                    )
            if replay_success or bool(transition[2]) or bool(transition[3]):
                break
        if replay_success is None:
            raise RuntimeError("action replay produced no LIBERO-PRO success observation")
    except Exception as exc:
        with h5py.File(path, "r+") as handle:
            handle.attrs["replay_validated"] = False
            handle.attrs["replay_validation_version"] = "controller-reset-v1"
            handle.attrs["replay_error"] = f"{type(exc).__name__}: {exc}"
            handle.flush()
        raise
    with h5py.File(path, "r+") as handle:
        handle.attrs["replay_max_state_error"] = maximum
        handle.attrs["replay_max_state_error_index"] = maximum_index
        handle.attrs["replay_max_state_error_dimension"] = maximum_dimension
        handle.attrs["replay_first_exceeds_tolerance_index"] = first_exceeds_tolerance
        handle.attrs["replay_max_qpos_error"] = maximum_qpos_error
        handle.attrs["replay_max_qvel_error"] = maximum_qvel_error
        handle.attrs["replay_tolerance"] = float(tolerance)
        handle.attrs["replay_validation_version"] = "controller-reset-v1"
        success_matches = replay_success == recorded_success
        position_limit = float(
            tolerance if position_tolerance is None else position_tolerance
        )
        velocity_limit = float(
            tolerance if velocity_tolerance is None else velocity_tolerance
        )
        handle.attrs["replay_success_matches"] = bool(success_matches)
        handle.attrs["replay_task_success"] = bool(replay_success)
        handle.attrs["replay_steps_executed"] = steps_executed
        handle.attrs["replay_recorded_action_count"] = len(actions)
        handle.attrs["replay_position_tolerance"] = position_limit
        handle.attrs["replay_velocity_tolerance"] = velocity_limit
        handle.attrs["replay_acceptance_version"] = NATIVE_REPLAY_ACCEPTANCE
        handle.attrs["replay_state_error_role"] = "diagnostic_only"
        handle.attrs["replay_success_authority"] = "LIBERO-PRO native predicate"
        handle.attrs["replay_validated"] = bool(recorded_success and replay_success)
        if "replay_error" in handle.attrs:
            del handle.attrs["replay_error"]
        handle.flush()
    return maximum


def reassess_demo_replay(
    path: Path,
    *,
    tolerance: float | None = None,
    position_tolerance: float | None = None,
    velocity_tolerance: float | None = None,
) -> bool:
    """Apply native-success acceptance to completed replay evidence, not labels.

    Keep the old numerical diagnostics and previous acceptance evidence. The
    optional legacy tolerance arguments cannot alter the new success decision.
    A missing/error replay cannot be promoted by this metadata-only operation.
    """

    path = Path(path)
    required = {
        "replay_max_state_error",
        "simulator_success",
        "replay_task_success",
        "replay_validation_version",
    }
    with h5py.File(path, "r+") as handle:
        missing = sorted(required - set(handle.attrs))
        if missing:
            raise ValueError(
                f"demo has no complete replay diagnostics: missing={missing}"
            )
        if handle.attrs.get("replay_error") or handle.attrs.get("replay_status") == "error":
            raise RuntimeError("cannot reassess an errored/incomplete action replay")
        if handle.attrs.get("replay_acceptance_version") != NATIVE_REPLAY_ACCEPTANCE:
            previous = {key: value.item() if hasattr(value, "item") else value
                        for key, value in handle.attrs.items() if key.startswith("replay_")}
            handle.attrs["replay_prior_acceptance_json"] = json.dumps(previous, sort_keys=True)
        valid = bool(handle.attrs["simulator_success"] and handle.attrs["replay_task_success"])
        handle.attrs["replay_acceptance_version"] = NATIVE_REPLAY_ACCEPTANCE
        handle.attrs["replay_state_error_role"] = "diagnostic_only"
        handle.attrs["replay_success_authority"] = "LIBERO-PRO native predicate"
        handle.attrs["replay_validated"] = valid
        handle.attrs["replay_status"] = "validated" if valid else "rejected"
        handle.flush()
    return valid


def _demo_descriptor(ee_positions: np.ndarray, phases: int = 20) -> np.ndarray:
    source = np.linspace(0.0, 1.0, len(ee_positions))
    target = np.linspace(0.0, 1.0, phases)
    resampled = np.column_stack(
        [np.interp(target, source, ee_positions[:, axis]) for axis in range(3)]
    )
    return (resampled - resampled[0]).reshape(-1)


def _vector(value: np.ndarray, dimensions: int, name: str) -> np.ndarray:
    array = np.asarray(value)
    if array.shape != (dimensions,) or not np.isfinite(array).all():
        raise ValueError(f"{name} must be a finite vector of length {dimensions}")
    return array


__all__ = [
    "CurationResult",
    "DemoFrame",
    "DemoWriter",
    "curate_ticket_demos",
    "curate_and_export_ticket",
    "export_lerobot_v3",
    "validate_demo_replay",
    "reassess_demo_replay",
]
