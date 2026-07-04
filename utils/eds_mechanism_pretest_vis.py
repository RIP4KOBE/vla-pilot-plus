"""3D visualization helpers for EDS mechanism pretest traces."""

from __future__ import annotations

import csv
import json
from dataclasses import replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

from core.eds_mechanism_trace import EDSMechanismTrace, EDSParticleStage


STAGE_FILENAMES = {
    "initial_before_diversity": "initial_before_diversity_3d.png",
    "initial_after_diversity_phase": "initial_after_diversity_phase_3d.png",
    "initial_final": "initial_final_3d.png",
    "initial": "00_initial_population_3d.png",
    "scored": "01_scored_population_3d.png",
    "resampled": "02_after_resample_3d.png",
    "renoised": "03_after_renoise_3d.png",
    "after_rollout": "04_after_rollout_3d.png",
}


def save_eds_mechanism_pretest_artifacts(
    output_dir: str | Path,
    trace: EDSMechanismTrace,
) -> list[str]:
    """Save 3D EDS mechanism plots and full-process summary artifacts."""
    root = Path(output_dir)
    single_step_dir = root / "single_step_inner_loop"
    full_process_dir = root / "full_eds_process"
    saved: list[str] = []

    config_path = root / "config.json"
    _write_config(config_path, trace)
    saved.append(str(config_path))

    keypoints_path = root / "keypoints_3d.json"
    _write_keypoints(keypoints_path, trace)
    saved.append(str(keypoints_path))

    for stage in trace.stages:
        filename = STAGE_FILENAMES.get(stage.stage)
        if filename is not None:
            path = single_step_dir / filename
            _plot_stage(path, trace, stage, title=_stage_title(trace, stage))
            saved.append(str(path))

        if stage.stage in {"full_process_after_rollout", "after_rollout"}:
            path = full_process_dir / f"iter_{int(stage.iter_idx):03d}_population_3d.png"
            _plot_stage(path, trace, stage, title=_stage_title(trace, stage))
            saved.append(str(path))

            best_path = full_process_dir / f"iter_{int(stage.iter_idx):03d}_best_trajectory_3d.png"
            _plot_stage(best_path, trace, _best_particle_stage(stage), title=f"best {_stage_title(trace, stage)}")
            saved.append(str(best_path))

    reward_curve = full_process_dir / "reward_curve.png"
    _plot_reward_curve(reward_curve, trace)
    saved.append(str(reward_curve))

    diversity_curve = full_process_dir / "diversity_curve.png"
    _plot_diversity_curve(diversity_curve, trace)
    saved.append(str(diversity_curve))

    distance_curve = full_process_dir / "distance_curve.png"
    _plot_distance_curve(distance_curve, trace)
    saved.append(str(distance_curve))

    metrics_csv = full_process_dir / "per_iter_metrics.csv"
    _write_per_iter_metrics(metrics_csv, trace)
    saved.append(str(metrics_csv))

    selected_path = full_process_dir / "final_selected_vs_initial_best_3d.png"
    _plot_final_selected_vs_initial_best(selected_path, trace)
    saved.append(str(selected_path))

    summary = full_process_dir / "full_process_summary.md"
    _write_summary(summary, trace)
    saved.append(str(summary))

    return saved


def _plot_stage(
    path: Path,
    trace: EDSMechanismTrace,
    stage: EDSParticleStage,
    *,
    title: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    trajectories = _trajectory_xyz(stage)
    rewards = _to_numpy(stage.rewards).reshape(-1)
    keypoints = _scoring_keypoints_xyz(trace)
    mins, maxs = _axis_limits(trace, stage)

    fig = plt.figure(figsize=(8, 7))
    ax = fig.add_subplot(111, projection="3d")
    ax.set_proj_type("ortho")
    ax.view_init(elev=68, azim=-72)
    cmap = plt.get_cmap("viridis")
    reward_min = float(np.nanmin(rewards)) if rewards.size else 0.0
    reward_max = float(np.nanmax(rewards)) if rewards.size else 1.0
    norm = plt.Normalize(vmin=reward_min, vmax=reward_max)

    for idx, trajectory in enumerate(trajectories):
        reward = float(rewards[idx]) if idx < rewards.size else reward_min
        color = cmap(norm(reward))
        linewidth = 3.0 if idx == trace.selected_idx else 1.2
        ax.plot(
            trajectory[:, 0],
            trajectory[:, 1],
            trajectory[:, 2],
            color=color,
            alpha=0.85,
            linewidth=linewidth,
        )
        ax.scatter(
            trajectory[:, 0],
            trajectory[:, 1],
            trajectory[:, 2],
            color=color,
            s=8,
            alpha=0.28,
        )
        ax.scatter(
            trajectory[-1, 0],
            trajectory[-1, 1],
            trajectory[-1, 2],
            color=color,
            s=26,
        )

    if trajectories.size:
        start = trajectories[0, 0]
        ax.scatter(start[0], start[1], start[2], color="black", s=60, label="start EEF")

    if keypoints is not None and keypoints.size:
        ax.scatter(
            keypoints[:, 0],
            keypoints[:, 1],
            keypoints[:, 2],
            color="red",
            marker="*",
            s=180,
            label="scoring keypoint",
        )

    colorbar = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), ax=ax, shrink=0.72)
    colorbar.set_label("reward")
    ax.set_xlim(float(mins[0]), float(maxs[0]))
    ax.set_ylim(float(mins[1]), float(maxs[1]))
    ax.set_zlim(float(mins[2]), float(maxs[2]))
    ax.set_box_aspect(np.maximum(maxs - mins, 1e-3))
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_zlabel("z")
    ax.set_title(title)
    if trajectories.size or (keypoints is not None and keypoints.size):
        ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_reward_curve(path: Path, trace: EDSMechanismTrace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stages = _full_process_stages(trace)
    xs = [int(stage.iter_idx) for stage in stages]
    best = [_reward_stat(stage, "max") for stage in stages]
    mean = [_reward_stat(stage, "mean") for stage in stages]
    std = [_reward_stat(stage, "std") for stage in stages]

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(xs, best, marker="o", label="best reward")
    ax.plot(xs, mean, marker="o", label="mean reward")
    ax.fill_between(xs, np.array(mean) - np.array(std), np.array(mean) + np.array(std), alpha=0.2)
    ax.set_xlabel("iteration")
    ax.set_ylabel("reward")
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_diversity_curve(path: Path, trace: EDSMechanismTrace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stages = _full_process_stages(trace)
    xs = [int(stage.iter_idx) for stage in stages]
    diversity = [_trajectory_diversity(stage) for stage in stages]

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(xs, diversity, marker="o", label="trajectory diversity")
    ax.set_xlabel("iteration")
    ax.set_ylabel("mean pairwise EEF distance")
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_distance_curve(path: Path, trace: EDSMechanismTrace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stages = _full_process_stages(trace)
    xs = [int(stage.iter_idx) for stage in stages]
    distances = [_best_distance_to_keypoint(stage, trace) for stage in stages]

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(xs, distances, marker="o", label="best distance to keypoint")
    ax.set_xlabel("iteration")
    ax.set_ylabel("distance")
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_final_selected_vs_initial_best(path: Path, trace: EDSMechanismTrace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    initial = _initial_reference_stage(trace)
    final = _full_process_stages(trace)[-1] if _full_process_stages(trace) else None

    fig = plt.figure(figsize=(8, 7))
    ax = fig.add_subplot(111, projection="3d")
    ax.set_proj_type("ortho")
    ax.view_init(elev=68, azim=-72)
    mins, maxs = _axis_limits(trace)
    keypoints = _scoring_keypoints_xyz(trace)

    if initial is not None:
        initial_traj = _trajectory_xyz(initial)
        if initial_traj.size:
            idx = _best_index(initial)
            _plot_named_trajectory(ax, initial_traj[idx], "initial best", "tab:blue", "--")

    if final is not None:
        final_traj = _trajectory_xyz(final)
        if final_traj.size:
            idx = trace.selected_idx if trace.selected_idx is not None else _best_index(final)
            idx = min(max(int(idx), 0), final_traj.shape[0] - 1)
            _plot_named_trajectory(ax, final_traj[idx], "final selected", "tab:green", "-")

    if keypoints is not None and keypoints.size:
        ax.scatter(
            keypoints[:, 0],
            keypoints[:, 1],
            keypoints[:, 2],
            color="red",
            marker="*",
            s=180,
            label="scoring keypoint",
        )

    ax.set_xlim(float(mins[0]), float(maxs[0]))
    ax.set_ylim(float(mins[1]), float(maxs[1]))
    ax.set_zlim(float(mins[2]), float(maxs[2]))
    ax.set_box_aspect(np.maximum(maxs - mins, 1e-3))
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_zlabel("z")
    ax.set_title("final selected vs initial best")
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _initial_reference_stage(trace: EDSMechanismTrace) -> EDSParticleStage | None:
    initial_final = next(
        (stage for stage in trace.stages if stage.stage == "initial_final"),
        None,
    )
    if initial_final is not None:
        return initial_final
    return next((stage for stage in trace.stages if stage.stage == "initial"), None)


def _write_summary(path: Path, trace: EDSMechanismTrace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# EDS Mechanism Pretest Summary",
                "",
                f"- suite: `{trace.suite}`",
                f"- task_id: `{trace.task_id}`",
                f"- reward_mode: `{trace.reward_mode}`",
                f"- population_size: `{trace.population_size}`",
                f"- cem_iters: `{trace.cem_iters}`",
                f"- selected_idx: `{trace.selected_idx}`",
                "",
                "Renoised trajectory plots are diagnostic projections of noisy action state, not directly executable actions.",
                "",
                "## Qualitative Review Checklist",
                "",
                "- population diversity: pass / mixed / fail",
                "- reward geometry: pass / mixed / fail",
                "- resampling pressure: pass / mixed / fail",
                "- renoise scale: pass / mixed / fail",
                "- rollout preservation: pass / mixed / fail",
                "- full-process trend: pass / mixed / fail",
                "- final selected plausibility: pass / mixed / fail",
                "",
                "## Reviewer Notes",
                "",
                "- Overall verdict: pass / mixed / fail",
                "- Notes:",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_config(path: Path, trace: EDSMechanismTrace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
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
                "stages": [
                    {"stage": stage.stage, "iter_idx": int(stage.iter_idx)}
                    for stage in trace.stages
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_keypoints(path: Path, trace: EDSMechanismTrace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keypoints = _scoring_keypoints_xyz(trace)
    all_keypoints = _keypoints_xyz(trace.keypoints)
    payload = {
        "all_keypoints_count": int(all_keypoints.shape[0]) if all_keypoints is not None else 0,
        "keypoints_3d": keypoints.tolist() if keypoints is not None else [],
        "scoring_keypoint_indices": trace.scoring_keypoint_indices or ([0] if keypoints is not None and keypoints.size else []),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_per_iter_metrics(path: Path, trace: EDSMechanismTrace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "iter_idx",
        "best_idx",
        "best_reward",
        "mean_reward",
        "reward_std",
        "trajectory_diversity",
        "best_distance_to_keypoint",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for stage in _full_process_stages(trace):
            writer.writerow(
                {
                    "iter_idx": int(stage.iter_idx),
                    "best_idx": _best_index(stage),
                    "best_reward": _reward_stat(stage, "max"),
                    "mean_reward": _reward_stat(stage, "mean"),
                    "reward_std": _reward_stat(stage, "std"),
                    "trajectory_diversity": _trajectory_diversity(stage),
                    "best_distance_to_keypoint": _best_distance_to_keypoint(stage, trace),
                }
            )


def _stage_title(trace: EDSMechanismTrace, stage: EDSParticleStage) -> str:
    return f"{stage.stage} iter={int(stage.iter_idx)} reward_mode={trace.reward_mode}"


def _full_process_stages(trace: EDSMechanismTrace) -> list[EDSParticleStage]:
    stages = [
        stage
        for stage in trace.stages
        if stage.stage in {"full_process_after_rollout", "after_rollout"}
    ]
    return stages or list(trace.stages)


def _best_particle_stage(stage: EDSParticleStage) -> EDSParticleStage:
    idx = _best_index(stage)
    return replace(
        stage,
        actions=_slice_particle(stage.actions, idx),
        trajectories=_slice_particle(stage.trajectories, idx),
        rewards=_slice_particle(stage.rewards, idx),
        costs=_slice_particle(stage.costs, idx),
        parent_indices=_slice_optional_particle(stage.parent_indices, idx),
        parent_ranks=_slice_optional_particle(stage.parent_ranks, idx),
        reward_before_rollout=_slice_optional_particle(stage.reward_before_rollout, idx),
        reward_after_rollout=_slice_optional_particle(stage.reward_after_rollout, idx),
        renoise_delta_norm=_slice_optional_particle(stage.renoise_delta_norm, idx),
        rollout_delta_norm=_slice_optional_particle(stage.rollout_delta_norm, idx),
    )


def _axis_limits(
    trace: EDSMechanismTrace,
    stage: EDSParticleStage | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    point_sets = []
    stages = [stage] if stage is not None else trace.stages
    for current_stage in stages:
        trajectories = _trajectory_xyz(current_stage)
        if trajectories.size:
            point_sets.append(trajectories.reshape(-1, 3))

    keypoints = _scoring_keypoints_xyz(trace)
    if keypoints is not None and keypoints.size:
        point_sets.append(keypoints)

    if not point_sets:
        return np.array([-1.0, -1.0, -1.0]), np.array([1.0, 1.0, 1.0])

    points = np.concatenate(point_sets, axis=0)
    mins = np.nanmin(points, axis=0)
    maxs = np.nanmax(points, axis=0)
    span = np.maximum(maxs - mins, 0.04)
    pad = float(span.max()) * 0.12
    return mins - pad, maxs + pad


def _trajectory_xyz(stage: EDSParticleStage) -> np.ndarray:
    trajectories = _to_numpy(stage.trajectories)
    if trajectories.ndim < 3 or trajectories.shape[-1] < 3:
        return np.zeros((0, 0, 3), dtype=np.float32)
    return trajectories[..., :3]


def _keypoints_xyz(keypoints: torch.Tensor | None) -> np.ndarray | None:
    if keypoints is None:
        return None
    points = _to_numpy(keypoints)
    if points.size == 0 or points.shape[-1] < 3:
        return None
    return points.reshape(-1, points.shape[-1])[:, :3]


def _scoring_keypoints_xyz(trace: EDSMechanismTrace) -> np.ndarray | None:
    keypoints = _keypoints_xyz(trace.keypoints)
    if keypoints is None or not keypoints.size:
        return keypoints

    indices = trace.scoring_keypoint_indices
    if not indices:
        return keypoints[:1]

    valid = [idx for idx in indices if 0 <= int(idx) < keypoints.shape[0]]
    if not valid:
        return keypoints[:1]
    return keypoints[np.array(valid, dtype=np.int64)]


def _to_numpy(tensor: torch.Tensor | None) -> np.ndarray:
    if tensor is None:
        return np.array([], dtype=np.float32)
    return tensor.detach().cpu().float().numpy()


def _slice_particle(tensor: torch.Tensor, idx: int) -> torch.Tensor:
    if tensor.ndim == 0:
        return tensor.reshape(1)
    return tensor[idx : idx + 1]


def _slice_optional_particle(tensor: torch.Tensor | None, idx: int) -> torch.Tensor | None:
    if tensor is None:
        return None
    return _slice_particle(tensor, idx)


def _best_index(stage: EDSParticleStage) -> int:
    rewards = stage.rewards.detach().cpu().float().reshape(-1)
    if rewards.numel() == 0:
        return 0
    return int(torch.argmax(rewards).item())


def _reward_stat(stage: EDSParticleStage, stat: str) -> float:
    rewards = stage.rewards.detach().cpu().float().reshape(-1)
    if rewards.numel() == 0:
        return 0.0
    if stat == "max":
        return float(rewards.max().item())
    if stat == "std":
        return float(rewards.std(unbiased=False).item())
    return float(rewards.mean().item())


def _trajectory_diversity(stage: EDSParticleStage) -> float:
    trajectories = stage.trajectories.detach().cpu().float()
    if trajectories.ndim < 3 or trajectories.shape[0] < 2:
        return 0.0
    flattened = trajectories[..., :3].reshape(trajectories.shape[0], -1)
    return float(torch.pdist(flattened).mean().item())


def _best_distance_to_keypoint(stage: EDSParticleStage, trace: EDSMechanismTrace) -> float:
    trajectories = _trajectory_xyz(stage)
    keypoints = _scoring_keypoints_xyz(trace)
    if not trajectories.size or keypoints is None or not keypoints.size:
        return 0.0
    best = trajectories[_best_index(stage)]
    distances = np.linalg.norm(best[:, None, :3] - keypoints[None, :, :3], axis=-1)
    return float(np.nanmin(distances))


def _plot_named_trajectory(ax, trajectory: np.ndarray, label: str, color: str, linestyle: str) -> None:
    ax.plot(
        trajectory[:, 0],
        trajectory[:, 1],
        trajectory[:, 2],
        color=color,
        linestyle=linestyle,
        linewidth=2.4,
        label=label,
    )
    ax.scatter(
        trajectory[-1, 0],
        trajectory[-1, 1],
        trajectory[-1, 2],
        color=color,
        s=45,
    )
