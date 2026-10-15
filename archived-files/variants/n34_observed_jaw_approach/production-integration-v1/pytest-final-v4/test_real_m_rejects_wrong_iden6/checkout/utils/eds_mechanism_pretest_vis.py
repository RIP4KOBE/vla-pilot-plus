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
    "rollout_before_diversity": "rollout_before_diversity_3d.png",
    "rollout_after_diversity_phase": "rollout_after_diversity_phase_3d.png",
    "rollout_final": "rollout_final_3d.png",
    "after_rollout": "04_after_rollout_3d.png",
}

ROLLOUT_RBF_STAGE_ORDER = [
    ("rollout_before_diversity", "before rollout RBF"),
    ("rollout_after_diversity_phase", "after rollout RBF phase"),
    ("rollout_final", "final rollout population"),
]

SOURCE_COLORS = {
    "fresh": "#1f77b4",
    "memory": "#ff7f0e",
    "elite": "#2ca02c",
    "anchor_offspring": "#d62728",
    "weighted_offspring": "#9467bd",
}


def _prevalidate_trace_for_visualization(trace: EDSMechanismTrace) -> None:
    if not isinstance(trace, EDSMechanismTrace):
        raise ValueError("EDS visualization trace must be an EDSMechanismTrace")
    for stage_idx, stage in enumerate(trace.stages):
        prefix = f"EDS visualization trace stage {stage_idx} ({stage.stage!r})"
        if not torch.is_tensor(stage.trajectories):
            raise ValueError(f"{prefix} trajectories must be a tensor")
        if (
            stage.trajectories.ndim != 3
            or stage.trajectories.shape[0] <= 0
            or stage.trajectories.shape[1] <= 0
            or stage.trajectories.shape[2] != 3
        ):
            raise ValueError(
                f"{prefix} trajectories must have strict shape (N, T, 3) with N,T > 0"
            )
        if not torch.isfinite(stage.trajectories).all():
            raise ValueError(f"{prefix} trajectories must be finite")
        population_size = int(stage.trajectories.shape[0])
        for field_name in ("rewards", "costs"):
            value = getattr(stage, field_name)
            if not torch.is_tensor(value):
                raise ValueError(f"{prefix} {field_name} must be a tensor")
            if int(value.numel()) != population_size:
                raise ValueError(
                    f"{prefix} {field_name} length must match trajectory population"
                )
            if not torch.isfinite(value).all():
                raise ValueError(f"{prefix} {field_name} must be finite")

    if trace.keypoints is None:
        return
    if not torch.is_tensor(trace.keypoints):
        raise ValueError("EDS visualization trace keypoints must be a tensor or None")
    keypoints = trace.keypoints.detach()
    if keypoints.numel() == 0:
        return
    if keypoints.ndim < 1 or keypoints.shape[-1] < 3:
        raise ValueError(
            "EDS visualization trace keypoints must have at least three coordinates"
        )
    flattened = keypoints.reshape(-1, keypoints.shape[-1])
    indices = trace.scoring_keypoint_indices
    if indices:
        if any(
            isinstance(index, bool)
            or not isinstance(index, int)
            or index < 0
            or index >= flattened.shape[0]
            for index in indices
        ):
            raise ValueError(
                "EDS visualization trace scoring keypoint indices are invalid"
            )
        scoring = flattened.index_select(
            0,
            torch.tensor(indices, device=flattened.device, dtype=torch.long),
        )
    else:
        scoring = flattened[:1]
    if not torch.isfinite(scoring[..., :3]).all():
        raise ValueError("EDS visualization trace scoring keypoints must be finite")


def save_eds_mechanism_pretest_artifacts(
    output_dir: str | Path,
    trace: EDSMechanismTrace,
) -> list[str]:
    """Save 3D EDS mechanism plots and full-process summary artifacts."""
    _prevalidate_trace_for_visualization(trace)
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
    saved.extend(save_eds_rbf_diversity_artifacts(root, trace))
    saved.extend(save_eds_rollout_rbf_diversity_artifacts(root, trace))
    saved.extend(_save_adaptive_evidence_artifacts(root, trace))

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


def _save_adaptive_evidence_artifacts(
    root: Path,
    trace: EDSMechanismTrace,
) -> list[str]:
    saved: list[str] = []
    if _selection_evidence_enabled(trace):
        selection_dir = root / "selection"
        stage = _selection_evidence_stage(trace)
        if stage is not None:
            plot_path = selection_dir / "parent_source_trajectories_3d.png"
            _plot_stage_by_source(plot_path, trace, stage)
            saved.append(str(plot_path))
            csv_path = selection_dir / "parent_rank_and_probability.csv"
            _write_parent_selection_csv(csv_path, trace.selection_info)
            saved.append(str(csv_path))
            survival_path = selection_dir / "elite_anchor_survival.json"
            _write_selection_survival(survival_path, trace.selection_info)
            saved.append(str(survival_path))

    memory_stages = _memory_evidence_stages(trace)
    if _memory_evidence_enabled(trace, memory_stages):
        memory_dir = root / "memory"
        plot_path = memory_dir / "fresh_vs_memory_trajectories_3d.png"
        mins, maxs = _plot_memory_comparison(plot_path, trace, memory_stages)
        saved.append(str(plot_path))
        acceptance_path = memory_dir / "memory_acceptance.json"
        payload = dict(trace.chunk_memory_info)
        payload["axis_limits"] = {"min": mins.tolist(), "max": maxs.tolist()}
        _write_json(acceptance_path, payload)
        saved.append(str(acceptance_path))

    if _schedule_evidence_enabled(trace):
        schedule_dir = root / "schedule"
        decisions_path = schedule_dir / "adaptive_decisions.json"
        _write_json(
            decisions_path,
            {
                "adaptive_rollout": trace.adaptive_rollout_info,
                "search_schedule": trace.search_schedule_info,
                "execution": trace.execution_info,
            },
        )
        saved.append(str(decisions_path))
        plot_path = schedule_dir / "reward_diversity_schedule.png"
        _plot_adaptive_schedule(plot_path, trace)
        saved.append(str(plot_path))
    return saved


def _selection_evidence_enabled(trace: EDSMechanismTrace) -> bool:
    info = trace.selection_info or {}
    return bool(info.get("enabled")) and bool(info.get("per_iter"))


def _selection_evidence_stage(trace: EDSMechanismTrace) -> EDSParticleStage | None:
    return next(
        (
            stage
            for stage in reversed(trace.stages)
            if stage.particle_sources is not None
            and stage.parent_selection_kinds is not None
        ),
        None,
    )


def _memory_evidence_stages(
    trace: EDSMechanismTrace,
) -> dict[str, EDSParticleStage]:
    wanted = {
        "memory_fresh_initial",
        "memory_adapted_candidates",
        "memory_composed_initial",
    }
    return {stage.stage: stage for stage in trace.stages if stage.stage in wanted}


def _memory_evidence_enabled(
    trace: EDSMechanismTrace,
    stages: dict[str, EDSParticleStage],
) -> bool:
    info = trace.chunk_memory_info or {}
    return (
        bool(info.get("enabled"))
        and bool(info.get("chunk_memory_available"))
        and int(info.get("chunk_memory_candidate_count") or 0) > 0
        and set(stages)
        == {
            "memory_fresh_initial",
            "memory_adapted_candidates",
            "memory_composed_initial",
        }
    )


def _schedule_evidence_enabled(trace: EDSMechanismTrace) -> bool:
    series = _build_adaptive_schedule_series(trace)
    iter_signal_keys = (
        "best_reward",
        "mean_reward",
        "diversity_reference",
        "diversity_current",
        "diversity_band_low",
        "diversity_band_high",
        "renoise_steps",
        "scale_requested",
        "scale_applied",
    )
    has_iter_signal = any(
        any(value is not None for value in series[key])
        for key in iter_signal_keys
    )
    return has_iter_signal or bool(series["execution_horizon"])


def _build_adaptive_schedule_series(trace: EDSMechanismTrace) -> dict:
    search_info = trace.search_schedule_info or {}
    rollout_info = trace.adaptive_rollout_info or {}
    execution_info = trace.execution_info or {}
    search_by_iter = (
        {
            int(item["iter_idx"]): item
            for item in search_info.get("per_iter", [])
        }
        if bool(search_info.get("enabled"))
        else {}
    )
    rollout_by_iter = (
        {
            int(item["iter_idx"]): item
            for item in rollout_info.get("per_iter", [])
        }
        if bool(rollout_info.get("enabled"))
        else {}
    )
    iter_ids = sorted(set(search_by_iter) | set(rollout_by_iter))

    def coalesce(*values):
        return next((value for value in values if value is not None), None)

    def values(search_key: str | None, rollout_key: str | None) -> list:
        output = []
        for iter_idx in iter_ids:
            search_item = search_by_iter.get(iter_idx, {})
            rollout_item = rollout_by_iter.get(iter_idx, {})
            output.append(
                coalesce(
                    rollout_item.get(rollout_key) if rollout_key else None,
                    search_item.get(search_key) if search_key else None,
                )
            )
        return output

    execution_enabled = bool(execution_info.get("enabled"))
    execution_horizon = execution_info.get("execution_horizon_resolved")
    return {
        "iter_ids": iter_ids,
        "best_reward": values("best_reward", None),
        "mean_reward": values("mean_reward", None),
        "diversity_reference": values(None, "diversity_reference"),
        "diversity_current": values("population_diversity", "diversity_current"),
        "diversity_band_low": values("diversity_band_low", "diversity_band_low"),
        "diversity_band_high": values("diversity_band_high", "diversity_band_high"),
        "renoise_steps": values("n_trunc_steps", None),
        "scale_requested": values(None, "scale_requested"),
        "scale_applied": values(None, "scale_applied"),
        "execution_x": [0] if execution_enabled and execution_horizon is not None else [],
        "execution_horizon": (
            [int(execution_horizon)]
            if execution_enabled and execution_horizon is not None
            else []
        ),
        "execution_reason": (
            [str(execution_info.get("execution_horizon_reason") or "unspecified")]
            if execution_enabled and execution_horizon is not None
            else []
        ),
    }


def _plot_stage_by_source(
    path: Path,
    trace: EDSMechanismTrace,
    stage: EDSParticleStage,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    trajectories = _trajectory_xyz(stage)
    sources = stage.particle_sources or ["unknown"] * len(trajectories)
    mins, maxs = _axis_limits(trace, stage)
    keypoints = _scoring_keypoints_xyz(trace)
    fig = plt.figure(figsize=(8, 7))
    ax = fig.add_subplot(111, projection="3d")
    ax.set_proj_type("ortho")
    ax.view_init(elev=68, azim=-72)
    seen: set[str] = set()
    for idx, trajectory in enumerate(trajectories):
        source = str(sources[idx]) if idx < len(sources) else "unknown"
        color = SOURCE_COLORS.get(source, "#7f7f7f")
        label = source if source not in seen else None
        seen.add(source)
        ax.plot(
            trajectory[:, 0],
            trajectory[:, 1],
            trajectory[:, 2],
            color=color,
            linewidth=2.6 if idx == trace.selected_idx else 1.3,
            alpha=0.9,
            label=label,
        )
        ax.scatter(*trajectory[-1], color=color, s=28)
    if keypoints is not None and keypoints.size:
        ax.scatter(
            keypoints[:, 0],
            keypoints[:, 1],
            keypoints[:, 2],
            color="black",
            marker="*",
            s=160,
            label="scoring keypoint",
        )
    _format_trajectory_axes(ax, mins, maxs, "parent source trajectories")
    if seen or (keypoints is not None and keypoints.size):
        ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _write_parent_selection_csv(path: Path, selection_info: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "iter",
        "particle_id",
        "parent_id",
        "parent_rank",
        "source",
        "probability",
        "selection_kind",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in selection_info.get("per_iter", []):
            parent_ids = item.get("parent_indices", [])
            parent_ranks = item.get("parent_ranks", [])
            sources = item.get("parent_sources", [])
            probabilities = item.get("parent_probabilities", [])
            kinds = item.get("parent_selection_kinds", [])
            row_count = len(parent_ids)
            if not all(
                len(values) == row_count
                for values in (parent_ranks, sources, probabilities, kinds)
            ):
                raise ValueError("EDS selection trace parent metadata lengths must match")
            for particle_id in range(row_count):
                writer.writerow(
                    {
                        "iter": int(item["iter_idx"]),
                        "particle_id": particle_id,
                        "parent_id": parent_ids[particle_id],
                        "parent_rank": parent_ranks[particle_id],
                        "source": sources[particle_id],
                        "probability": probabilities[particle_id],
                        "selection_kind": kinds[particle_id],
                    }
                )


def _write_selection_survival(path: Path, selection_info: dict) -> None:
    payload = {
        key: selection_info.get(key)
        for key in (
            "parent_weighting_mode",
            "parent_coverage_mode",
            "elite_survival_to_final_count",
            "initial_anchor_lineage_count",
            "final_unique_anchor_lineage_survival_count",
            "final_unique_anchor_lineage_survival_ratio",
            "selected_parent_source",
            "parent_count_by_source",
            "anchor_unique_ratio",
            "anchor_min_pairwise_eef_distance",
        )
    }
    _write_json(path, payload)


def _plot_memory_comparison(
    path: Path,
    trace: EDSMechanismTrace,
    stages: dict[str, EDSParticleStage],
) -> tuple[np.ndarray, np.ndarray]:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = [
        ("memory_fresh_initial", "fresh initial"),
        ("memory_adapted_candidates", "adapted memory"),
        ("memory_composed_initial", "accepted composition"),
    ]
    mins, maxs = _axis_limits_for_stages(trace, [stages[name] for name, _ in ordered])
    keypoints = _scoring_keypoints_xyz(trace)
    fig = plt.figure(figsize=(18, 6))
    for subplot_idx, (stage_name, title) in enumerate(ordered, start=1):
        stage = stages[stage_name]
        trajectories = _trajectory_xyz(stage)
        sources = stage.particle_sources or ["unknown"] * len(trajectories)
        ax = fig.add_subplot(1, 3, subplot_idx, projection="3d")
        ax.set_proj_type("ortho")
        ax.view_init(elev=68, azim=-72)
        seen: set[str] = set()
        for idx, trajectory in enumerate(trajectories):
            source = str(sources[idx]) if idx < len(sources) else "unknown"
            color = SOURCE_COLORS.get(source, "#7f7f7f")
            label = source if source not in seen else None
            seen.add(source)
            ax.plot(
                trajectory[:, 0],
                trajectory[:, 1],
                trajectory[:, 2],
                color=color,
                linewidth=1.5,
                alpha=0.9,
                label=label,
            )
            ax.scatter(*trajectory[-1], color=color, s=24)
        if keypoints is not None and keypoints.size:
            ax.scatter(
                keypoints[:, 0],
                keypoints[:, 1],
                keypoints[:, 2],
                color="black",
                marker="*",
                s=120,
                label="scoring keypoint",
            )
        _format_trajectory_axes(ax, mins, maxs, title)
        ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return mins, maxs


def _format_trajectory_axes(ax, mins: np.ndarray, maxs: np.ndarray, title: str) -> None:
    ax.set_xlim(float(mins[0]), float(maxs[0]))
    ax.set_ylim(float(mins[1]), float(maxs[1]))
    ax.set_zlim(float(mins[2]), float(maxs[2]))
    ax.set_box_aspect(np.maximum(maxs - mins, 1e-3))
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_zlabel("z")
    ax.set_title(title)


def _plot_adaptive_schedule(path: Path, trace: EDSMechanismTrace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    series = _build_adaptive_schedule_series(trace)

    def has_values(key: str) -> bool:
        return any(value is not None for value in series[key])

    panels: list[str] = []
    if has_values("best_reward") or has_values("mean_reward"):
        panels.append("reward")
    if any(
        has_values(key)
        for key in (
            "diversity_reference",
            "diversity_current",
            "diversity_band_low",
            "diversity_band_high",
        )
    ):
        panels.append("diversity")
    if any(
        has_values(key)
        for key in ("renoise_steps", "scale_requested", "scale_applied")
    ):
        panels.append("controls")
    if series["execution_horizon"]:
        panels.append("execution")
    if not panels:
        raise ValueError("adaptive schedule plot requires at least one non-empty series")

    fig, axes = plt.subplots(len(panels), 1, figsize=(9, 3.2 * len(panels)))
    axes = np.atleast_1d(axes)
    for ax, panel in zip(axes, panels):
        if panel == "reward":
            if has_values("best_reward"):
                ax.plot(series["iter_ids"], series["best_reward"], marker="o", label="best reward")
            if has_values("mean_reward"):
                ax.plot(series["iter_ids"], series["mean_reward"], marker="o", label="mean reward")
            ax.set_ylabel("reward")
        elif panel == "diversity":
            for key, label, style in (
                ("diversity_reference", "diversity reference", ":"),
                ("diversity_current", "EEF diversity", "-"),
                ("diversity_band_low", "target band low", "--"),
                ("diversity_band_high", "target band high", "--"),
            ):
                if has_values(key):
                    ax.plot(series["iter_ids"], series[key], linestyle=style, marker="o", label=label)
            ax.set_ylabel("diversity")
        elif panel == "controls":
            if has_values("renoise_steps"):
                ax.step(series["iter_ids"], series["renoise_steps"], where="mid", label="renoise steps")
            if has_values("scale_requested"):
                ax.plot(series["iter_ids"], series["scale_requested"], marker="^", label="RBF scale requested")
            if has_values("scale_applied"):
                ax.plot(series["iter_ids"], series["scale_applied"], marker="s", label="RBF scale applied")
            ax.set_ylabel("resolved value")
        else:
            ax.scatter(series["execution_x"], series["execution_horizon"], s=70, label="execution horizon")
            ax.annotate(
                series["execution_reason"][0],
                (series["execution_x"][0], series["execution_horizon"][0]),
                xytext=(8, 8),
                textcoords="offset points",
            )
            ax.set_ylabel("executed steps")
            ax.set_xticks(series["execution_x"], ["chunk decision"])
        ax.legend(loc="best")
        ax.grid(alpha=0.2)
    axes[-1].set_xlabel("EDS iteration" if series["iter_ids"] else "execution decision")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _json_safe(value):
    if torch.is_tensor(value):
        return _json_safe(value.detach().cpu().tolist())
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (float, np.floating)):
        value = float(value)
        return value if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if hasattr(value, "item"):
        return _json_safe(value.item())
    return str(value)


def save_eds_rbf_diversity_artifacts(
    output_dir: str | Path,
    trace: EDSMechanismTrace,
) -> list[str]:
    """Save before/after/final RBF initial sampler diversity evidence."""
    _prevalidate_trace_for_visualization(trace)
    stages = _rbf_initial_stages(trace)
    if set(stages) != {
        "initial_before_diversity",
        "initial_after_diversity_phase",
        "initial_final",
    }:
        return []

    root = Path(output_dir) / "RBF_diversity"
    root.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []

    comparison_path = root / "eef_3d_before_after_final.png"
    _plot_rbf_eef_comparison(comparison_path, trace, stages)
    saved.append(str(comparison_path))

    endpoint_path = root / "endpoint_scatter_before_after_final.png"
    _plot_rbf_endpoint_scatter(endpoint_path, trace, stages)
    saved.append(str(endpoint_path))

    hist_path = root / "pairwise_distance_hist_before_after_final.png"
    _plot_rbf_pairwise_distance_hist(hist_path, stages)
    saved.append(str(hist_path))

    metrics_path = root / "rbf_diversity_metrics.json"
    _write_rbf_diversity_metrics(metrics_path, trace, stages)
    saved.append(str(metrics_path))

    trace_path = root / "rbf_diversity_trace.npz"
    _write_rbf_diversity_npz(trace_path, stages)
    saved.append(str(trace_path))

    return saved


def save_eds_rollout_rbf_diversity_artifacts(
    output_dir: str | Path,
    trace: EDSMechanismTrace,
) -> list[str]:
    """Save before/after/final RBF rollout diversity evidence."""
    _prevalidate_trace_for_visualization(trace)
    stages = _rollout_rbf_stages(trace)
    if set(stages) != {
        "rollout_before_diversity",
        "rollout_after_diversity_phase",
        "rollout_final",
    }:
        return []

    root = Path(output_dir) / "Rollout_RBF_diversity"
    root.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []

    comparison_path = root / "rollout_eef_3d_before_after_final.png"
    _plot_rollout_rbf_eef_comparison(comparison_path, trace, stages)
    saved.append(str(comparison_path))

    endpoint_path = root / "rollout_endpoint_scatter_before_after_final.png"
    _plot_rollout_rbf_endpoint_scatter(endpoint_path, trace, stages)
    saved.append(str(endpoint_path))

    hist_path = root / "rollout_pairwise_distance_hist_before_after_final.png"
    _plot_rollout_rbf_pairwise_distance_hist(hist_path, stages)
    saved.append(str(hist_path))

    metrics_path = root / "rollout_rbf_diversity_metrics.json"
    _write_rollout_rbf_diversity_metrics(metrics_path, trace, stages)
    saved.append(str(metrics_path))

    trace_path = root / "rollout_rbf_diversity_trace.npz"
    _write_rollout_rbf_diversity_npz(trace_path, stages)
    saved.append(str(trace_path))

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


def _plot_rbf_eef_comparison(
    path: Path,
    trace: EDSMechanismTrace,
    stages: dict[str, EDSParticleStage],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mins, maxs = _axis_limits_for_stages(trace, list(stages.values()))
    keypoints = _scoring_keypoints_xyz(trace)
    stage_order = [
        ("initial_before_diversity", "before RBF"),
        ("initial_after_diversity_phase", "after RBF phase"),
        ("initial_final", "final denoised initial population"),
    ]

    fig = plt.figure(figsize=(18, 6))
    for panel_idx, (stage_name, title) in enumerate(stage_order, start=1):
        ax = fig.add_subplot(1, 3, panel_idx, projection="3d")
        ax.set_proj_type("ortho")
        ax.view_init(elev=68, azim=-72)
        _plot_population_trajectories_on_axis(ax, _trajectory_xyz(stages[stage_name]))
        if keypoints is not None and keypoints.size:
            ax.scatter(
                keypoints[:, 0],
                keypoints[:, 1],
                keypoints[:, 2],
                color="red",
                marker="*",
                s=130,
                label="scoring keypoint",
            )
        _set_3d_axis(ax, mins, maxs)
        ax.set_title(title)
        if panel_idx == 1:
            ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_rbf_endpoint_scatter(
    path: Path,
    trace: EDSMechanismTrace,
    stages: dict[str, EDSParticleStage],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mins, maxs = _axis_limits_for_stages(trace, list(stages.values()))
    keypoints = _scoring_keypoints_xyz(trace)
    stage_order = [
        ("initial_before_diversity", "before RBF"),
        ("initial_after_diversity_phase", "after RBF phase"),
        ("initial_final", "final"),
    ]
    colors = ["tab:blue", "tab:orange", "tab:green"]

    fig = plt.figure(figsize=(18, 6))
    for panel_idx, ((stage_name, title), color) in enumerate(zip(stage_order, colors), start=1):
        ax = fig.add_subplot(1, 3, panel_idx, projection="3d")
        ax.set_proj_type("ortho")
        ax.view_init(elev=68, azim=-72)
        endpoints = _trajectory_endpoints(_trajectory_xyz(stages[stage_name]))
        if endpoints.size:
            ax.scatter(endpoints[:, 0], endpoints[:, 1], endpoints[:, 2], color=color, s=40)
        if keypoints is not None and keypoints.size:
            ax.scatter(
                keypoints[:, 0],
                keypoints[:, 1],
                keypoints[:, 2],
                color="red",
                marker="*",
                s=130,
                label="scoring keypoint",
            )
        _set_3d_axis(ax, mins, maxs)
        ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_rbf_pairwise_distance_hist(
    path: Path,
    stages: dict[str, EDSParticleStage],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stage_order = [
        ("initial_before_diversity", "before RBF"),
        ("initial_after_diversity_phase", "after RBF phase"),
        ("initial_final", "final"),
    ]
    colors = ["tab:blue", "tab:orange", "tab:green"]

    fig, ax = plt.subplots(figsize=(8, 5))
    for (stage_name, label), color in zip(stage_order, colors):
        distances = _pairwise_trajectory_distances(_trajectory_xyz(stages[stage_name]))
        if distances.size:
            ax.hist(distances, bins=20, alpha=0.45, color=color, label=label)
    ax.set_xlabel("pairwise EEF trajectory distance")
    ax.set_ylabel("count")
    if ax.get_legend_handles_labels()[0]:
        ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_rollout_rbf_eef_comparison(
    path: Path,
    trace: EDSMechanismTrace,
    stages: dict[str, EDSParticleStage],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mins, maxs = _axis_limits_for_stages(trace, list(stages.values()))
    keypoints = _scoring_keypoints_xyz(trace)

    fig = plt.figure(figsize=(18, 6))
    for panel_idx, (stage_name, title) in enumerate(ROLLOUT_RBF_STAGE_ORDER, start=1):
        ax = fig.add_subplot(1, 3, panel_idx, projection="3d")
        ax.set_proj_type("ortho")
        ax.view_init(elev=68, azim=-72)
        _plot_population_trajectories_on_axis(ax, _trajectory_xyz(stages[stage_name]))
        if keypoints is not None and keypoints.size:
            ax.scatter(
                keypoints[:, 0],
                keypoints[:, 1],
                keypoints[:, 2],
                color="red",
                marker="*",
                s=130,
                label="scoring keypoint",
            )
        _set_3d_axis(ax, mins, maxs)
        ax.set_title(title)
        if panel_idx == 1:
            ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_rollout_rbf_endpoint_scatter(
    path: Path,
    trace: EDSMechanismTrace,
    stages: dict[str, EDSParticleStage],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mins, maxs = _axis_limits_for_stages(trace, list(stages.values()))
    keypoints = _scoring_keypoints_xyz(trace)
    colors = ["tab:blue", "tab:orange", "tab:green"]

    fig = plt.figure(figsize=(18, 6))
    for panel_idx, ((stage_name, title), color) in enumerate(
        zip(ROLLOUT_RBF_STAGE_ORDER, colors),
        start=1,
    ):
        ax = fig.add_subplot(1, 3, panel_idx, projection="3d")
        ax.set_proj_type("ortho")
        ax.view_init(elev=68, azim=-72)
        endpoints = _trajectory_endpoints(_trajectory_xyz(stages[stage_name]))
        if endpoints.size:
            ax.scatter(endpoints[:, 0], endpoints[:, 1], endpoints[:, 2], color=color, s=40)
        if keypoints is not None and keypoints.size:
            ax.scatter(
                keypoints[:, 0],
                keypoints[:, 1],
                keypoints[:, 2],
                color="red",
                marker="*",
                s=130,
                label="scoring keypoint",
            )
        _set_3d_axis(ax, mins, maxs)
        ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_rollout_rbf_pairwise_distance_hist(
    path: Path,
    stages: dict[str, EDSParticleStage],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    colors = ["tab:blue", "tab:orange", "tab:green"]

    fig, ax = plt.subplots(figsize=(8, 5))
    for (stage_name, label), color in zip(ROLLOUT_RBF_STAGE_ORDER, colors):
        distances = _pairwise_trajectory_distances(_trajectory_xyz(stages[stage_name]))
        if distances.size:
            ax.hist(distances, bins=20, alpha=0.45, color=color, label=label)
    ax.set_xlabel("pairwise EEF trajectory distance")
    ax.set_ylabel("count")
    if ax.get_legend_handles_labels()[0]:
        ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_population_trajectories_on_axis(ax, trajectories: np.ndarray) -> None:
    if not trajectories.size:
        return
    cmap = plt.get_cmap("viridis")
    denom = max(trajectories.shape[0] - 1, 1)
    for idx, trajectory in enumerate(trajectories):
        color = cmap(idx / denom)
        ax.plot(
            trajectory[:, 0],
            trajectory[:, 1],
            trajectory[:, 2],
            color=color,
            alpha=0.82,
            linewidth=1.4,
        )
        ax.scatter(
            trajectory[-1, 0],
            trajectory[-1, 1],
            trajectory[-1, 2],
            color=color,
            s=22,
            alpha=0.9,
        )
    start = trajectories[0, 0]
    ax.scatter(start[0], start[1], start[2], color="black", s=50, label="start EEF")


def _set_3d_axis(ax, mins: np.ndarray, maxs: np.ndarray) -> None:
    ax.set_xlim(float(mins[0]), float(maxs[0]))
    ax.set_ylim(float(mins[1]), float(maxs[1]))
    ax.set_zlim(float(mins[2]), float(maxs[2]))
    ax.set_box_aspect(np.maximum(maxs - mins, 1e-3))
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_zlabel("z")


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


def _write_rbf_diversity_metrics(
    path: Path,
    trace: EDSMechanismTrace,
    stages: dict[str, EDSParticleStage],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    before = _trajectory_xyz(stages["initial_before_diversity"])
    after = _trajectory_xyz(stages["initial_after_diversity_phase"])
    final = _trajectory_xyz(stages["initial_final"])
    after_diversity = _mean_or_none(_pairwise_trajectory_distances(after))
    final_diversity = _mean_or_none(_pairwise_trajectory_distances(final))
    retention = (
        final_diversity / after_diversity
        if after_diversity is not None and after_diversity > 1e-12 and final_diversity is not None
        else None
    )
    info = trace.initial_sampler_info or {}
    payload = {
        "initial_eef_diversity_before_rbf": _mean_or_none(
            _pairwise_trajectory_distances(before)
        ),
        "initial_eef_diversity_after_rbf_phase": after_diversity,
        "initial_eef_diversity_final": final_diversity,
        "initial_eef_diversity_retention_ratio": retention,
        "endpoint_spread_before_rbf": _mean_or_none(
            _pairwise_endpoint_distances(before)
        ),
        "endpoint_spread_after_rbf_phase": _mean_or_none(
            _pairwise_endpoint_distances(after)
        ),
        "endpoint_spread_final": _mean_or_none(
            _pairwise_endpoint_distances(final)
        ),
        "initial_diversity_scale": info.get("initial_diversity_scale"),
        "initial_diversity_start_ratio": info.get("initial_diversity_start_ratio"),
        "initial_diversity_steps": info.get("initial_diversity_steps"),
        "initial_diversity_fallback_used": info.get("initial_diversity_fallback_used"),
        "initial_diversity_fallback_reason": info.get("initial_diversity_fallback_reason"),
        "population_size": int(trace.population_size),
        "episode": trace.episode,
        "global_step": trace.global_step,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_rbf_diversity_npz(
    path: Path,
    stages: dict[str, EDSParticleStage],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    before = _trajectory_xyz(stages["initial_before_diversity"])
    after = _trajectory_xyz(stages["initial_after_diversity_phase"])
    final = _trajectory_xyz(stages["initial_final"])
    np.savez(
        path,
        before_trajectories=before,
        after_rbf_phase_trajectories=after,
        final_trajectories=final,
        before_endpoints=_trajectory_endpoints(before),
        after_rbf_phase_endpoints=_trajectory_endpoints(after),
        final_endpoints=_trajectory_endpoints(final),
        before_pairwise_distances=_pairwise_trajectory_distances(before),
        after_rbf_phase_pairwise_distances=_pairwise_trajectory_distances(after),
        final_pairwise_distances=_pairwise_trajectory_distances(final),
    )


def _write_rollout_rbf_diversity_metrics(
    path: Path,
    trace: EDSMechanismTrace,
    stages: dict[str, EDSParticleStage],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    before = _trajectory_xyz(stages["rollout_before_diversity"])
    after = _trajectory_xyz(stages["rollout_after_diversity_phase"])
    final = _trajectory_xyz(stages["rollout_final"])
    after_diversity = _mean_or_none(_pairwise_trajectory_distances(after))
    final_diversity = _mean_or_none(_pairwise_trajectory_distances(final))
    retention = (
        final_diversity / after_diversity
        if after_diversity is not None and after_diversity > 1e-12 and final_diversity is not None
        else None
    )
    info = trace.rollout_diversity_info or {}
    payload = {
        "eef_diversity_before_rollout": _mean_or_none(
            _pairwise_trajectory_distances(before)
        ),
        "eef_diversity_after_rollout_rbf_phase": after_diversity,
        "eef_diversity_after_rollout_final": final_diversity,
        "eef_diversity_rollout_retention_ratio": retention,
        "endpoint_spread_before_rollout": _mean_or_none(
            _pairwise_endpoint_distances(before)
        ),
        "endpoint_spread_after_rollout_rbf_phase": _mean_or_none(
            _pairwise_endpoint_distances(after)
        ),
        "endpoint_spread_after_rollout_final": _mean_or_none(
            _pairwise_endpoint_distances(final)
        ),
        "rollout_diversity_enabled": info.get("rollout_diversity_enabled"),
        "rollout_diversity_mode": info.get("rollout_diversity_mode"),
        "rollout_diversity_scale": info.get("rollout_diversity_scale"),
        "rollout_diversity_start_ratio": info.get("rollout_diversity_start_ratio"),
        "rollout_diversity_iters_applied": info.get(
            "rollout_diversity_iters_applied"
        ),
        "rollout_diversity_steps_applied": info.get(
            "rollout_diversity_steps_applied"
        ),
        "rollout_diversity_grad_norm_mean": info.get(
            "rollout_diversity_grad_norm_mean"
        ),
        "rollout_diversity_grad_norm_max": info.get(
            "rollout_diversity_grad_norm_max"
        ),
        "rollout_diversity_fallback_used": info.get(
            "rollout_diversity_fallback_used"
        ),
        "rollout_diversity_fallback_reason": info.get(
            "rollout_diversity_fallback_reason"
        ),
        "population_size": int(trace.population_size),
        "episode": trace.episode,
        "global_step": trace.global_step,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_rollout_rbf_diversity_npz(
    path: Path,
    stages: dict[str, EDSParticleStage],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    before = _trajectory_xyz(stages["rollout_before_diversity"])
    after = _trajectory_xyz(stages["rollout_after_diversity_phase"])
    final = _trajectory_xyz(stages["rollout_final"])
    np.savez(
        path,
        before_rollout_trajectories=before,
        after_rollout_rbf_phase_trajectories=after,
        final_rollout_trajectories=final,
        before_rollout_endpoints=_trajectory_endpoints(before),
        after_rollout_rbf_phase_endpoints=_trajectory_endpoints(after),
        final_rollout_endpoints=_trajectory_endpoints(final),
        before_rollout_pairwise_distances=_pairwise_trajectory_distances(before),
        after_rollout_rbf_phase_pairwise_distances=_pairwise_trajectory_distances(after),
        final_rollout_pairwise_distances=_pairwise_trajectory_distances(final),
    )


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


def _axis_limits_for_stages(
    trace: EDSMechanismTrace,
    stages: list[EDSParticleStage],
) -> tuple[np.ndarray, np.ndarray]:
    point_sets = []
    for stage in stages:
        trajectories = _trajectory_xyz(stage)
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


def _rbf_initial_stages(trace: EDSMechanismTrace) -> dict[str, EDSParticleStage]:
    wanted = {
        "initial_before_diversity",
        "initial_after_diversity_phase",
        "initial_final",
    }
    return {stage.stage: stage for stage in trace.stages if stage.stage in wanted}


def _rollout_rbf_stages(trace: EDSMechanismTrace) -> dict[str, EDSParticleStage]:
    wanted = {
        "rollout_before_diversity",
        "rollout_after_diversity_phase",
        "rollout_final",
    }
    return {stage.stage: stage for stage in trace.stages if stage.stage in wanted}


def _trajectory_endpoints(trajectories: np.ndarray) -> np.ndarray:
    if trajectories.ndim < 3 or trajectories.shape[0] == 0 or trajectories.shape[1] == 0:
        return np.zeros((0, 3), dtype=np.float32)
    return trajectories[:, -1, :3]


def _pairwise_trajectory_distances(trajectories: np.ndarray) -> np.ndarray:
    if trajectories.ndim < 3 or trajectories.shape[0] < 2:
        return np.array([], dtype=np.float32)
    body = trajectories[:, 1:, :3] if trajectories.shape[1] > 1 else trajectories[..., :3]
    flattened = body.reshape(body.shape[0], -1)
    return _pairwise_distances(flattened)


def _pairwise_endpoint_distances(trajectories: np.ndarray) -> np.ndarray:
    endpoints = _trajectory_endpoints(trajectories)
    if endpoints.shape[0] < 2:
        return np.array([], dtype=np.float32)
    return _pairwise_distances(endpoints)


def _pairwise_distances(points: np.ndarray) -> np.ndarray:
    if points.ndim != 2 or points.shape[0] < 2:
        return np.array([], dtype=np.float32)
    distances = []
    for left in range(points.shape[0] - 1):
        delta = points[left + 1 :] - points[left]
        distances.extend(np.linalg.norm(delta, axis=1).tolist())
    return np.asarray(distances, dtype=np.float32)


def _mean_or_none(values: np.ndarray) -> float | None:
    if values.size == 0:
        return None
    mean = float(np.nanmean(values))
    return mean if np.isfinite(mean) else None


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
