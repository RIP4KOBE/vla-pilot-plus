from __future__ import annotations

import csv
import json
import math
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import torch


@dataclass
class EDSParticleStage:
    stage: str
    iter_idx: int
    actions: torch.Tensor
    trajectories: torch.Tensor
    rewards: torch.Tensor
    costs: torch.Tensor
    parent_indices: torch.Tensor | None = None
    parent_ranks: torch.Tensor | None = None
    reward_before_rollout: torch.Tensor | None = None
    reward_after_rollout: torch.Tensor | None = None
    renoise_delta_norm: torch.Tensor | None = None
    rollout_delta_norm: torch.Tensor | None = None
    particle_sources: list[str] | None = None
    parent_probabilities: list[float | None] | None = None
    parent_selection_kinds: list[str] | None = None


@dataclass
class EDSMechanismTrace:
    suite: str | None
    task_id: int | None
    episode: int | None
    global_step: int
    reward_mode: str
    population_size: int
    cem_iters: int
    use_cem: bool
    keypoints: torch.Tensor | None
    scoring_keypoint_indices: list[int] | None = None
    stages: list[EDSParticleStage] = field(default_factory=list)
    selected_idx: int | None = None
    initial_sampler_info: dict[str, Any] = field(default_factory=dict)
    rollout_diversity_info: dict[str, Any] = field(default_factory=dict)
    selection_info: dict[str, Any] = field(default_factory=dict)
    adaptive_rollout_info: dict[str, Any] = field(default_factory=dict)
    chunk_memory_info: dict[str, Any] = field(default_factory=dict)
    search_schedule_info: dict[str, Any] = field(default_factory=dict)
    execution_info: dict[str, Any] = field(default_factory=dict)


CSV_FIELDS = [
    "stage",
    "iter_idx",
    "particle_id",
    "particle_source",
    "parent_id",
    "parent_rank",
    "parent_probability",
    "parent_selection_kind",
    "resampled_count",
    "reward",
    "cost",
    "reward_rank",
    "distance_to_keypoint_final",
    "distance_to_keypoint_min",
    "trajectory_length",
    "renoise_delta_norm",
    "rollout_delta_norm",
    "reward_before_rollout",
    "reward_after_rollout",
]


def build_run_id(
    *,
    suite: str,
    task_id: int,
    seed: int,
    reward_mode: str,
    population_size: int,
    cem_iters: int,
) -> str:
    return (
        f"{suite}_task{int(task_id)}_seed{int(seed):03d}_"
        f"{reward_mode}_p{int(population_size)}_c{int(cem_iters)}"
    )


def save_mechanism_trace(
    output_dir: str | Path,
    trace: EDSMechanismTrace,
    save_tensors: bool,
) -> list[str]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    written_paths: list[str] = []

    metadata_path = root / "first_chunk_metadata.json"
    metadata_path.write_text(
        json.dumps(_metadata_payload(trace), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    written_paths.append(str(metadata_path))

    csv_path = root / "single_step_inner_loop" / "single_step_particles.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for stage in trace.stages:
            writer.writerows(_stage_rows(stage, _scoring_keypoints(trace)))
    written_paths.append(str(csv_path))

    if save_tensors:
        tensor_path = root / "tensors" / "mechanism_trace.pt"
        tensor_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(_tensor_payload(trace), tensor_path)
        written_paths.append(str(tensor_path))

    return written_paths


def load_mechanism_trace(input_dir: str | Path) -> EDSMechanismTrace:
    """Load a tensor-backed mechanism trace saved by :func:`save_mechanism_trace`."""
    source = Path(input_dir)
    tensor_path = source if source.is_file() else source / "tensors" / "mechanism_trace.pt"
    try:
        payload = torch.load(tensor_path, map_location="cpu", weights_only=True)
    except (pickle.UnpicklingError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError(
            "mechanism trace is not a safe weights-only tensor payload"
        ) from exc
    metadata, raw_stages = _validate_mechanism_trace_payload(payload)
    stages = [
        EDSParticleStage(
            stage=str(stage["stage"]),
            iter_idx=int(stage["iter_idx"]),
            actions=stage["actions"],
            trajectories=stage["trajectories"],
            rewards=stage["rewards"],
            costs=stage["costs"],
            parent_indices=stage.get("parent_indices"),
            parent_ranks=stage.get("parent_ranks"),
            reward_before_rollout=stage.get("reward_before_rollout"),
            reward_after_rollout=stage.get("reward_after_rollout"),
            renoise_delta_norm=stage.get("renoise_delta_norm"),
            rollout_delta_norm=stage.get("rollout_delta_norm"),
            particle_sources=stage.get("particle_sources"),
            parent_probabilities=stage.get("parent_probabilities"),
            parent_selection_kinds=stage.get("parent_selection_kinds"),
        )
        for stage in raw_stages
    ]
    return EDSMechanismTrace(
        suite=metadata.get("suite"),
        task_id=metadata.get("task_id"),
        episode=metadata.get("episode"),
        global_step=int(metadata.get("global_step", 0)),
        reward_mode=str(metadata.get("reward_mode", "normal")),
        population_size=int(metadata.get("population_size", 0)),
        cem_iters=int(metadata.get("cem_iters", 0)),
        use_cem=bool(metadata.get("use_cem", False)),
        keypoints=payload.get("keypoints"),
        scoring_keypoint_indices=payload.get("scoring_keypoint_indices"),
        stages=stages,
        selected_idx=metadata.get("selected_idx"),
        initial_sampler_info=metadata.get("initial_sampler_info", {}),
        rollout_diversity_info=metadata.get("rollout_diversity_info", {}),
        selection_info=metadata.get("selection_info", {}),
        adaptive_rollout_info=metadata.get("adaptive_rollout_info", {}),
        chunk_memory_info=metadata.get("chunk_memory_info", {}),
        search_schedule_info=metadata.get("search_schedule_info", {}),
        execution_info=metadata.get("execution_info", {}),
    )


def _validate_mechanism_trace_payload(
    payload: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(payload, dict):
        raise ValueError("mechanism trace payload must be a dict")
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("mechanism trace metadata must be a dict")
    raw_stages = payload.get("stages")
    if not isinstance(raw_stages, list):
        raise ValueError("mechanism trace stages must be a list")

    required_metadata = {
        "global_step": int,
        "reward_mode": str,
        "population_size": int,
        "cem_iters": int,
        "use_cem": bool,
    }
    for field_name, expected_type in required_metadata.items():
        if field_name not in metadata:
            raise ValueError(
                f"mechanism trace metadata is missing required field {field_name!r}"
            )
        value = metadata[field_name]
        if expected_type is int:
            valid = isinstance(value, int) and not isinstance(value, bool)
        else:
            valid = isinstance(value, expected_type)
        if not valid:
            raise ValueError(
                f"mechanism trace metadata field {field_name!r} has invalid type"
            )
    for field_name in (
        "initial_sampler_info",
        "rollout_diversity_info",
        "selection_info",
        "adaptive_rollout_info",
        "chunk_memory_info",
        "search_schedule_info",
        "execution_info",
    ):
        if field_name in metadata and not isinstance(metadata[field_name], dict):
            raise ValueError(
                f"mechanism trace metadata field {field_name!r} must be a dict"
            )

    keypoints = payload.get("keypoints")
    if keypoints is not None and not torch.is_tensor(keypoints):
        raise ValueError("mechanism trace keypoints must be a tensor or None")
    scoring_indices = payload.get("scoring_keypoint_indices")
    if scoring_indices is not None:
        if not isinstance(scoring_indices, list) or any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in scoring_indices
        ):
            raise ValueError(
                "mechanism trace scoring_keypoint_indices must be an integer list or None"
            )

    required_stage_tensors = ("actions", "trajectories", "rewards", "costs")
    optional_stage_tensors = (
        "parent_indices",
        "parent_ranks",
        "reward_before_rollout",
        "reward_after_rollout",
        "renoise_delta_norm",
        "rollout_delta_norm",
    )
    for stage_idx, stage in enumerate(raw_stages):
        prefix = f"mechanism trace stage {stage_idx}"
        if not isinstance(stage, dict):
            raise ValueError(f"{prefix} must be a dict")
        if not isinstance(stage.get("stage"), str):
            raise ValueError(f"{prefix} field 'stage' must be a string")
        iter_idx = stage.get("iter_idx")
        if isinstance(iter_idx, bool) or not isinstance(iter_idx, int):
            raise ValueError(f"{prefix} field 'iter_idx' must be an integer")
        for field_name in required_stage_tensors:
            if field_name not in stage or not torch.is_tensor(stage[field_name]):
                raise ValueError(f"{prefix} field {field_name!r} must be a tensor")
        for field_name in optional_stage_tensors:
            value = stage.get(field_name)
            if value is not None and not torch.is_tensor(value):
                raise ValueError(
                    f"{prefix} field {field_name!r} must be a tensor or None"
                )
        population_size = (
            int(stage["trajectories"].shape[0])
            if stage["trajectories"].ndim > 0
            else 0
        )
        _validate_optional_string_list(
            stage.get("particle_sources"),
            population_size,
            prefix=prefix,
            field_name="particle_sources",
        )
        _validate_optional_string_list(
            stage.get("parent_selection_kinds"),
            population_size,
            prefix=prefix,
            field_name="parent_selection_kinds",
        )
        probabilities = stage.get("parent_probabilities")
        if probabilities is not None:
            if not isinstance(probabilities, list) or len(probabilities) != population_size:
                raise ValueError(
                    f"{prefix} field 'parent_probabilities' must match population size"
                )
            for value in probabilities:
                if value is None:
                    continue
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(float(value))
                ):
                    raise ValueError(
                        f"{prefix} field 'parent_probabilities' has invalid item"
                    )
    return metadata, raw_stages


def _validate_optional_string_list(
    value: Any,
    population_size: int,
    *,
    prefix: str,
    field_name: str,
) -> None:
    if value is None:
        return
    if (
        not isinstance(value, list)
        or len(value) != population_size
        or any(not isinstance(item, str) for item in value)
    ):
        raise ValueError(
            f"{prefix} field {field_name!r} must be a string list matching population size"
        )


def _metadata_payload(trace: EDSMechanismTrace) -> dict[str, Any]:
    return {
        "suite": trace.suite,
        "task_id": trace.task_id,
        "episode": trace.episode,
        "global_step": trace.global_step,
        "reward_mode": trace.reward_mode,
        "population_size": trace.population_size,
        "cem_iters": trace.cem_iters,
        "use_cem": trace.use_cem,
        "selected_idx": trace.selected_idx,
        "scoring_keypoint_indices": trace.scoring_keypoint_indices,
        "initial_sampler_info": _json_safe(trace.initial_sampler_info),
        "rollout_diversity_info": _json_safe(trace.rollout_diversity_info),
        "selection_info": _json_safe(trace.selection_info),
        "adaptive_rollout_info": _json_safe(trace.adaptive_rollout_info),
        "chunk_memory_info": _json_safe(trace.chunk_memory_info),
        "search_schedule_info": _json_safe(trace.search_schedule_info),
        "execution_info": _json_safe(trace.execution_info),
        "keypoints_shape": _shape_or_none(trace.keypoints),
        "num_stages": len(trace.stages),
        "stages": [
            {
                "stage": stage.stage,
                "iter_idx": stage.iter_idx,
                "population_size": _population_size(stage),
                "actions_shape": _shape_or_none(stage.actions),
                "trajectories_shape": _shape_or_none(stage.trajectories),
            }
            for stage in trace.stages
        ],
    }


def _tensor_payload(trace: EDSMechanismTrace) -> dict[str, Any]:
    return {
        "metadata": _metadata_payload(trace),
        "selection_info": _json_safe(trace.selection_info),
        "adaptive_rollout_info": _json_safe(trace.adaptive_rollout_info),
        "chunk_memory_info": _json_safe(trace.chunk_memory_info),
        "search_schedule_info": _json_safe(trace.search_schedule_info),
        "execution_info": _json_safe(trace.execution_info),
        "keypoints": _detach_cpu_or_none(trace.keypoints),
        "scoring_keypoint_indices": trace.scoring_keypoint_indices,
        "stages": [
            {
                "stage": stage.stage,
                "iter_idx": int(stage.iter_idx),
                "actions": _detach_cpu_or_none(stage.actions),
                "trajectories": _detach_cpu_or_none(stage.trajectories),
                "rewards": _detach_cpu_or_none(stage.rewards),
                "costs": _detach_cpu_or_none(stage.costs),
                "parent_indices": _detach_cpu_or_none(stage.parent_indices),
                "parent_ranks": _detach_cpu_or_none(stage.parent_ranks),
                "reward_before_rollout": _detach_cpu_or_none(stage.reward_before_rollout),
                "reward_after_rollout": _detach_cpu_or_none(stage.reward_after_rollout),
                "renoise_delta_norm": _detach_cpu_or_none(stage.renoise_delta_norm),
                "rollout_delta_norm": _detach_cpu_or_none(stage.rollout_delta_norm),
                "particle_sources": (
                    list(stage.particle_sources)
                    if stage.particle_sources is not None
                    else None
                ),
                "parent_probabilities": (
                    _json_safe(stage.parent_probabilities)
                    if stage.parent_probabilities is not None
                    else None
                ),
                "parent_selection_kinds": (
                    list(stage.parent_selection_kinds)
                    if stage.parent_selection_kinds is not None
                    else None
                ),
            }
            for stage in trace.stages
        ],
    }


def _json_safe(value: Any) -> Any:
    if torch.is_tensor(value):
        return _json_safe(value.detach().cpu().tolist())
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if hasattr(value, "item"):
        return _json_safe(value.item())
    if hasattr(value, "tolist"):
        return _json_safe(value.tolist())
    return str(value)


def _detach_cpu_or_none(value: torch.Tensor | None) -> torch.Tensor | None:
    if value is None:
        return None
    return value.detach().cpu()


def _stage_rows(stage: EDSParticleStage, keypoints: torch.Tensor | None) -> list[dict[str, Any]]:
    population_size = _population_size(stage)
    rewards = _flatten_float_tensor(stage.rewards, population_size)
    costs = _flatten_float_tensor(stage.costs, population_size)
    reward_ranks = _rank_descending(rewards)
    parent_indices = _flatten_int_tensor(stage.parent_indices, population_size)
    parent_ranks = _flatten_int_tensor(stage.parent_ranks, population_size)
    particle_sources = _particle_sources(stage.particle_sources, population_size)
    parent_probabilities = _optional_parent_values(
        stage.parent_probabilities,
        population_size,
        field_name="parent_probabilities",
    )
    parent_selection_kinds = _optional_parent_values(
        stage.parent_selection_kinds,
        population_size,
        field_name="parent_selection_kinds",
    )
    parent_counts = _value_counts(parent_indices)
    trajectory_stats = _trajectory_stats(stage.trajectories, keypoints, population_size)

    rows = []
    for particle_id in range(population_size):
        parent_id = parent_indices[particle_id] if parent_indices is not None else None
        parent_rank = parent_ranks[particle_id] if parent_ranks is not None else None
        rows.append(
            {
                "stage": stage.stage,
                "iter_idx": int(stage.iter_idx),
                "particle_id": particle_id,
                "particle_source": particle_sources[particle_id],
                "parent_id": parent_id,
                "parent_rank": parent_rank,
                "parent_probability": parent_probabilities[particle_id],
                "parent_selection_kind": parent_selection_kinds[particle_id],
                "resampled_count": parent_counts.get(parent_id, 0) if parent_id is not None else None,
                "reward": rewards[particle_id],
                "cost": costs[particle_id],
                "reward_rank": reward_ranks[particle_id],
                "distance_to_keypoint_final": trajectory_stats[particle_id][0],
                "distance_to_keypoint_min": trajectory_stats[particle_id][1],
                "trajectory_length": trajectory_stats[particle_id][2],
                "renoise_delta_norm": _optional_particle_value(
                    stage.renoise_delta_norm, particle_id, population_size
                ),
                "rollout_delta_norm": _optional_particle_value(
                    stage.rollout_delta_norm, particle_id, population_size
                ),
                "reward_before_rollout": _optional_particle_value(
                    stage.reward_before_rollout, particle_id, population_size
                ),
                "reward_after_rollout": _optional_particle_value(
                    stage.reward_after_rollout, particle_id, population_size
                ),
            }
        )
    return rows


def _optional_parent_values(
    values: list[Any] | None,
    expected_len: int,
    *,
    field_name: str,
) -> list[Any | None]:
    if values is None:
        return [None for _ in range(expected_len)]
    if len(values) != expected_len:
        raise ValueError(
            f"EDS {field_name} length {len(values)} != population size {expected_len}"
        )
    return list(values)


def _particle_sources(
    values: list[str] | None,
    expected_len: int,
) -> list[str | None]:
    if values is None:
        return [None for _ in range(expected_len)]
    if len(values) != expected_len:
        raise ValueError(
            "EDS particle_sources length "
            f"{len(values)} != population size {expected_len}"
        )
    return [str(value) for value in values]


def _population_size(stage: EDSParticleStage) -> int:
    if stage.trajectories.ndim > 0:
        return int(stage.trajectories.shape[0])
    return int(stage.rewards.reshape(-1).shape[0])


def _shape_or_none(value: torch.Tensor | None) -> list[int] | None:
    if value is None:
        return None
    return [int(dim) for dim in value.shape]


def _flatten_float_tensor(value: torch.Tensor, expected_len: int) -> list[float | None]:
    flattened = value.detach().cpu().reshape(-1)
    return [_finite_float(flattened[i].item()) if i < flattened.numel() else None for i in range(expected_len)]


def _flatten_int_tensor(value: torch.Tensor | None, expected_len: int) -> list[int | None] | None:
    if value is None:
        return None
    flattened = value.detach().cpu().reshape(-1)
    return [int(flattened[i].item()) if i < flattened.numel() else None for i in range(expected_len)]


def _rank_descending(values: list[float | None]) -> list[int | None]:
    finite_values = [
        (idx, value)
        for idx, value in enumerate(values)
        if value is not None and math.isfinite(value)
    ]
    ranked = [None for _ in values]
    for rank, (idx, _value) in enumerate(
        sorted(finite_values, key=lambda item: item[1], reverse=True),
        start=1,
    ):
        ranked[idx] = rank
    return ranked


def _value_counts(values: list[int | None] | None) -> dict[int | None, int]:
    counts: dict[int | None, int] = {}
    if values is None:
        return counts
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _trajectory_stats(
    trajectories: torch.Tensor,
    keypoints: torch.Tensor | None,
    population_size: int,
) -> list[tuple[float | None, float | None, float | None]]:
    traj = trajectories.detach().cpu().float()
    if traj.ndim < 3 or traj.shape[-1] < 3:
        return [(None, None, None) for _ in range(population_size)]

    traj_xyz = traj[..., :3]
    keypoints_xyz = _keypoints_xyz(keypoints)
    stats = []
    for particle_id in range(population_size):
        particle_traj = traj_xyz[particle_id]
        length = _trajectory_length(particle_traj)
        if keypoints_xyz is None or keypoints_xyz.numel() == 0:
            stats.append((None, None, length))
            continue
        distances = torch.cdist(particle_traj, keypoints_xyz)
        final_distance = distances[-1].min().item()
        min_distance = distances.min().item()
        stats.append((_finite_float(final_distance), _finite_float(min_distance), length))
    return stats


def _keypoints_xyz(keypoints: torch.Tensor | None) -> torch.Tensor | None:
    if keypoints is None:
        return None
    kp = keypoints.detach().cpu().float()
    if kp.numel() == 0:
        return kp.reshape(0, 3)
    if kp.shape[-1] < 3:
        return None
    return kp.reshape(-1, kp.shape[-1])[:, :3]


def _scoring_keypoints(trace: EDSMechanismTrace) -> torch.Tensor | None:
    keypoints = _keypoints_xyz(trace.keypoints)
    if keypoints is None or keypoints.numel() == 0:
        return keypoints
    if not trace.scoring_keypoint_indices:
        return keypoints[:1]

    valid = [
        int(idx)
        for idx in trace.scoring_keypoint_indices
        if 0 <= int(idx) < keypoints.shape[0]
    ]
    if not valid:
        return keypoints[:1]
    indices = torch.tensor(valid, dtype=torch.long)
    return keypoints.index_select(0, indices)


def _trajectory_length(trajectory: torch.Tensor) -> float | None:
    if trajectory.shape[0] < 2:
        return 0.0
    step_lengths = torch.linalg.norm(trajectory[1:] - trajectory[:-1], dim=-1)
    return _finite_float(step_lengths.sum().item())


def _optional_particle_value(
    value: torch.Tensor | None,
    particle_id: int,
    population_size: int,
) -> float | None:
    if value is None:
        return None
    values = _flatten_float_tensor(value, population_size)
    return values[particle_id]


def _finite_float(value: float | int) -> float | None:
    value_f = float(value)
    return value_f if math.isfinite(value_f) else None
