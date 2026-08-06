"""Qualitative visualization helpers for RDT+EDS evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import cv2
import imageio.v2 as imageio
import matplotlib.pyplot as plt
import numpy as np
import torch

from utils.vis_utils import (
    draw_action_trajectory_on_vlm_image,
    draw_keypoints_on_image,
)


def _to_action_candidates(tensor: Any) -> torch.Tensor:
    """Return decoded LIBERO action candidates as a CPU float tensor."""
    if torch.is_tensor(tensor):
        return tensor.detach().cpu().float()
    return torch.as_tensor(tensor, dtype=torch.float32).detach().cpu()


def _as_uint8_image(image: Any) -> np.ndarray:
    if torch.is_tensor(image):
        arr = image.detach().cpu().numpy()
    else:
        arr = np.asarray(image)
    if arr.dtype == np.uint8:
        return arr.copy()
    if arr.size > 0 and np.nanmax(arr) <= 1.0:
        arr = arr * 255.0
    return np.clip(arr, 0, 255).astype(np.uint8)


def _adapter_image(adapter) -> np.ndarray:
    return _as_uint8_image(adapter.get_vlm_image())


def save_image(path: str | Path, image: Any) -> None:
    """Save an image, creating parent directories as needed."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    imageio.imwrite(output_path, _as_uint8_image(image))


def _with_label(image: Any, label: str) -> np.ndarray:
    labeled = _as_uint8_image(image)
    cv2.putText(
        labeled,
        str(label),
        (10, 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return labeled


def _pad_to_height(image: np.ndarray, height: int) -> np.ndarray:
    if image.shape[0] == height:
        return image
    pad = height - image.shape[0]
    return cv2.copyMakeBorder(image, 0, pad, 0, 0, cv2.BORDER_CONSTANT, value=(0, 0, 0))


def save_side_by_side(
    path: str | Path,
    left: Any,
    right: Any,
    labels: tuple[str, str],
) -> None:
    """Save two labeled images concatenated horizontally."""
    left_img = _with_label(left, labels[0])
    right_img = _with_label(right, labels[1])
    height = max(left_img.shape[0], right_img.shape[0])
    combined = np.concatenate(
        [_pad_to_height(left_img, height), _pad_to_height(right_img, height)],
        axis=1,
    )
    save_image(path, combined)


def draw_population_cloud(adapter, population_actions, max_particles: int = 16) -> np.ndarray:
    """Draw up to ``max_particles`` decoded action trajectories on the VLM image."""
    candidates = _to_action_candidates(population_actions)
    if candidates.ndim == 2:
        candidates = candidates.unsqueeze(0)
    if candidates.ndim != 3 or candidates.shape[-1] != 7:
        raise ValueError(f"Expected action candidates with shape (B,H,7), got {tuple(candidates.shape)}")

    candidates = candidates[: max(0, int(max_particles))]
    return draw_action_trajectory_on_vlm_image(
        adapter=adapter,
        action_chunk=candidates,
        num_steps=min(16, candidates.shape[1]),
        global_step=0,
        action_executed=0,
    )


def _selected_candidate(actions: torch.Tensor, selected_idx: int) -> torch.Tensor | None:
    if actions.ndim == 2:
        return actions.unsqueeze(0)
    if actions.ndim != 3 or actions.shape[0] == 0:
        return None
    idx = min(max(int(selected_idx), 0), actions.shape[0] - 1)
    return actions[idx : idx + 1]


def _best_candidate(actions: torch.Tensor, scores: torch.Tensor) -> torch.Tensor | None:
    if actions.ndim == 2:
        return actions.unsqueeze(0)
    if actions.ndim != 3 or actions.shape[0] == 0:
        return None
    flat_scores = scores.reshape(-1)
    if flat_scores.numel() == 0:
        return actions[0:1]
    best_idx = int(torch.argmin(flat_scores[: actions.shape[0]]).item())
    return actions[best_idx : best_idx + 1]


def _draw_actions(adapter, actions: torch.Tensor, *, global_step: int) -> np.ndarray:
    return draw_action_trajectory_on_vlm_image(
        adapter=adapter,
        action_chunk=actions,
        num_steps=min(16, actions.shape[1]),
        global_step=global_step,
        action_executed=0,
    )


def _draw_keypoints_or_raw(adapter, image: np.ndarray, keypoints, mask_ids) -> np.ndarray:
    try:
        return draw_keypoints_on_image(
            adapter=adapter,
            image=image,
            keypoints=keypoints,
            mask_ids=mask_ids,
        )
    except Exception:
        return _adapter_image(adapter)


def _iter_artifacts(items: Iterable[dict[str, Any]], max_iters: int) -> Iterable[dict[str, Any]]:
    limit = max(0, int(max_iters))
    for idx, item in enumerate(items):
        if idx >= limit:
            break
        yield item


def _save_mechanism_metric_curves(
    path: Path,
    per_iter: list[dict[str, Any]],
) -> bool:
    rows = [
        (int(item["iter_idx"]), item.get("mechanism_metrics", {}))
        for item in per_iter
        if isinstance(item, dict) and isinstance(item.get("mechanism_metrics"), dict)
    ]
    if not rows:
        return False
    series = (
        ("selected_trajectory_length", "selected length"),
        ("population_trajectory_length_mean", "population length mean"),
        ("selected_max_step_displacement", "selected max-step"),
        ("population_max_step_mean", "population max-step mean"),
        ("eef_direction_diversity", "EEF direction diversity"),
        ("endpoint_direction_spread", "endpoint direction spread"),
    )
    figure, axes = plt.subplots(3, 1, figsize=(8, 10), sharex=True)
    groups = (series[:2], series[2:4], series[4:])
    for axis, group in zip(axes, groups):
        for key, label in group:
            xs = []
            ys = []
            for iter_idx, metrics in rows:
                value = metrics.get(key)
                if value is None:
                    continue
                value_f = float(value)
                if not np.isfinite(value_f):
                    continue
                xs.append(iter_idx)
                ys.append(value_f)
            if xs:
                axis.plot(xs, ys, marker="o", label=label)
        axis.grid(True, alpha=0.3)
        axis.legend(loc="best")
    axes[-1].set_xlabel("EDS iteration")
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)
    return True


def _qd_archive_states(artifacts: dict[str, Any], max_iters: int):
    initial = artifacts.get("qd_initial_archive")
    if isinstance(initial, dict) and initial:
        yield "initial", initial
    by_iter = {
        int(item.get("iter_idx", -999)): item
        for item in artifacts.get("qd_archive_by_iter", [])
        if isinstance(item, dict)
    }
    for iter_idx, label in ((0, "iter_001"), (4, "iter_005"), (9, "iter_010")):
        if iter_idx < int(max_iters) and iter_idx in by_iter:
            yield label, by_iter[iter_idx]


def _save_qd_heatmap(
    path: Path,
    state: dict[str, Any],
    *,
    grid_shape: tuple[int, int],
    bounds_xy_m: list[list[float]],
) -> None:
    grid_x, grid_y = grid_shape
    rewards = np.full((grid_y, grid_x), np.nan, dtype=np.float64)
    for entry in state.get("archive", []):
        cell_id = int(entry["cell_id"])
        if not 0 <= cell_id < grid_x * grid_y:
            raise ValueError("QD archive cell id is outside visualization grid")
        rewards[cell_id // grid_x, cell_id % grid_x] = float(entry["reward"])
    figure, axis = plt.subplots(figsize=(6, 5))
    masked = np.ma.masked_invalid(rewards)
    image = axis.imshow(masked, origin="lower", cmap="viridis")
    for y in range(grid_y):
        for x in range(grid_x):
            value = rewards[y, x]
            label = "empty" if not np.isfinite(value) else f"{value:.3g}"
            axis.text(x, y, label, ha="center", va="center", fontsize=8)
    axis.set_xlabel("cell x")
    axis.set_ylabel("cell y")
    axis.set_title(
        "QD occupancy / elite reward\n"
        f"bounds lo={bounds_xy_m[0]} hi={bounds_xy_m[1]} m"
    )
    figure.colorbar(image, ax=axis, label="elite reward")
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def _save_qd_trajectories(
    path: Path,
    adapter,
    state: dict[str, Any],
    *,
    grid_shape: tuple[int, int],
    keypoints,
) -> None:
    actions = _to_action_candidates(state.get("actions"))
    cell_values = torch.as_tensor(state.get("cell_ids"), dtype=torch.long).reshape(-1)
    if actions.ndim != 3 or actions.shape[-1] != 7:
        raise ValueError("QD qualitative actions must have shape (archive,H,7)")
    if cell_values.numel() != actions.shape[0]:
        raise ValueError("QD qualitative cell ids must match archive actions")
    figure = plt.figure(figsize=(15, 4.8))
    axis_xy = figure.add_subplot(1, 3, 1)
    axis_xz = figure.add_subplot(1, 3, 2)
    axis_3d = figure.add_subplot(1, 3, 3, projection="3d")
    cmap = plt.get_cmap("tab20")
    cell_count = grid_shape[0] * grid_shape[1]
    for action, raw_cell in zip(actions, cell_values.tolist()):
        trajectory = adapter.delta_actions_to_ee_trajectory(action).detach().cpu().float()
        if trajectory.ndim != 2 or trajectory.shape[1] < 3:
            raise ValueError("adapter returned invalid QD EEF trajectory")
        xyz = trajectory[:, :3].numpy()
        color = cmap(int(raw_cell) / max(cell_count - 1, 1))
        label = f"cell {int(raw_cell)}"
        axis_xy.plot(xyz[:, 0], xyz[:, 1], color=color, label=label)
        axis_xz.plot(xyz[:, 0], xyz[:, 2], color=color, label=label)
        axis_3d.plot(xyz[:, 0], xyz[:, 1], xyz[:, 2], color=color, label=label)
    target = None
    if keypoints is not None:
        target_values = np.asarray(keypoints, dtype=np.float64).reshape(-1)
        if target_values.size >= 3 and np.isfinite(target_values[:3]).all():
            target = target_values[:3]
    if target is not None:
        axis_xy.scatter(target[0], target[1], marker="*", s=120, c="red")
        axis_xz.scatter(target[0], target[2], marker="*", s=120, c="red")
        axis_3d.scatter(target[0], target[1], target[2], marker="*", s=120, c="red")
    axis_xy.set(xlabel="X (m)", ylabel="Y (m)", title="EEF XY by QD cell")
    axis_xz.set(xlabel="X (m)", ylabel="Z (m)", title="EEF XZ by QD cell")
    axis_3d.set(xlabel="X (m)", ylabel="Y (m)", zlabel="Z (m)", title="EEF 3D by QD cell")
    for axis in (axis_xy, axis_xz, axis_3d):
        axis.grid(True, alpha=0.3)
    handles, labels = axis_xy.get_legend_handles_labels()
    unique = dict(zip(labels, handles))
    figure.legend(unique.values(), unique.keys(), loc="lower center", ncol=4, fontsize=7)
    figure.tight_layout(rect=(0, 0.08, 1, 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def _save_qd_qualitative_artifacts(
    output_root: Path,
    adapter,
    keypoints,
    artifacts: dict[str, Any],
    max_iters: int,
) -> list[str]:
    states = list(_qd_archive_states(artifacts, max_iters))
    if not states:
        return []
    raw_grid_shape = artifacts.get("qd_grid_shape")
    if (
        not isinstance(raw_grid_shape, (list, tuple))
        or len(raw_grid_shape) != 2
    ):
        raise ValueError("QD qualitative artifacts require qd_grid_shape")
    grid_shape = (int(raw_grid_shape[0]), int(raw_grid_shape[1]))
    bounds_xy_m = artifacts.get("qd_bounds_xy_m")
    if not isinstance(bounds_xy_m, list) or len(bounds_xy_m) != 2:
        raise ValueError("QD qualitative artifacts require qd_bounds_xy_m")
    saved = []
    timeline = []
    for label, state in states:
        heatmap_path = output_root / f"qd_archive_heatmap_{label}.png"
        _save_qd_heatmap(
            heatmap_path,
            state,
            grid_shape=grid_shape,
            bounds_xy_m=bounds_xy_m,
        )
        saved.append(str(heatmap_path))
        trajectory_path = output_root / f"qd_archive_trajectories_{label}.png"
        _save_qd_trajectories(
            trajectory_path,
            adapter,
            state,
            grid_shape=grid_shape,
            keypoints=keypoints,
        )
        saved.append(str(trajectory_path))
        timeline.append(
            {
                "label": label,
                "iter_idx": int(state.get("iter_idx", -1)),
                "archive": state.get("archive", []),
                "parent_slots_by_cell": state.get("parent_slots_by_cell", {}),
            }
        )
    timeline_path = output_root / "qd_archive_timeline.json"
    timeline_path.write_text(
        json.dumps(timeline, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    saved.append(str(timeline_path))
    return saved


def save_eds_qualitative_artifacts(
    output_dir: str | Path,
    adapter,
    keypoints,
    mask_ids,
    artifacts: dict[str, Any],
    episode: int,
    global_step: int,
    max_iters: int = 10,
) -> list[str]:
    """Save qualitative EDS evaluation overlays for one generated action chunk."""
    output_root = Path(output_dir) / f"episode_{episode:03d}" / f"chunk_{global_step:06d}"
    output_root.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []

    if keypoints is not None:
        image = _draw_keypoints_or_raw(adapter, _adapter_image(adapter), keypoints, mask_ids)
        path = output_root / "keypoints_projected.png"
        save_image(path, image)
        saved.append(str(path))

    final_actions = artifacts.get("final_actions")
    final_candidates = _to_action_candidates(final_actions) if final_actions is not None else None
    selected_idx = int(artifacts.get("selected_idx", 0))
    final_selected = (
        _selected_candidate(final_candidates, selected_idx)
        if final_candidates is not None
        else None
    )

    if final_candidates is not None and final_selected is not None:
        selected_img = _draw_actions(adapter, final_selected, global_step=global_step)
        if keypoints is not None:
            selected_img = _draw_keypoints_or_raw(adapter, selected_img, keypoints, mask_ids)
        path = output_root / "keypoints_selected_eef_overlay.png"
        save_image(path, selected_img)
        saved.append(str(path))

        path = output_root / "population_overlay_iter_last.png"
        save_image(path, draw_population_cloud(adapter, final_candidates))
        saved.append(str(path))

    initial_actions = artifacts.get("initial_actions")
    if initial_actions is not None and final_selected is not None:
        initial_candidates = _to_action_candidates(initial_actions)
        initial_best = _selected_candidate(initial_candidates, 0)
        if initial_best is not None:
            left = _draw_actions(adapter, initial_best, global_step=global_step)
            right = _draw_actions(adapter, final_selected, global_step=global_step)
            path = output_root / "initial_best_vs_final_selected.png"
            save_side_by_side(path, left, right, ("initial best", "final selected"))
            saved.append(str(path))

    for item in _iter_artifacts(artifacts.get("per_iter", []), max_iters):
        population = _to_action_candidates(item["actions"])
        scores = _to_action_candidates(item["scores"]).reshape(-1)
        best = _best_candidate(population, scores)
        iter_idx = int(item["iter_idx"])

        if best is not None:
            path = output_root / f"best_trajectory_overlay_iter_{iter_idx:03d}.png"
            save_image(path, _draw_actions(adapter, best, global_step=global_step))
            saved.append(str(path))

        path = output_root / f"population_cloud_iter_{iter_idx:03d}.png"
        save_image(path, draw_population_cloud(adapter, population))
        saved.append(str(path))

    mechanism_curve_path = output_root / "mechanism_metric_curves.png"
    if _save_mechanism_metric_curves(
        mechanism_curve_path,
        list(_iter_artifacts(artifacts.get("per_iter", []), max_iters)),
    ):
        saved.append(str(mechanism_curve_path))

    saved.extend(
        _save_qd_qualitative_artifacts(
            output_root,
            adapter,
            keypoints,
            artifacts,
            max_iters,
        )
    )

    return saved
