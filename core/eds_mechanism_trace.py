from __future__ import annotations

import csv
import json
import math
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


CSV_FIELDS = [
    "stage",
    "iter_idx",
    "particle_id",
    "parent_id",
    "parent_rank",
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
            }
            for stage in trace.stages
        ],
    }


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
                "parent_id": parent_id,
                "parent_rank": parent_rank,
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
