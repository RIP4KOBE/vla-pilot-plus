"""Mode Card rendering with camera-overlay and task-space fallback views."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


@dataclass(frozen=True)
class ModeCardResult:
    path: Path
    projection_unavailable: bool


class ModeCardRenderer:
    def __init__(
        self,
        project_points: Callable[[np.ndarray], tuple[np.ndarray, np.ndarray]] | None,
    ) -> None:
        self._project_points = project_points

    def render(
        self,
        *,
        observation_image: np.ndarray,
        mode_id: str,
        weight: float,
        representative_indices: Mapping[str, int],
        positions: np.ndarray,
        relative_positions: np.ndarray,
        relative_rotvecs: np.ndarray,
        grippers: np.ndarray,
        output_path: Path,
    ) -> ModeCardResult:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        projection_unavailable = False
        projected: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        try:
            if self._project_points is None:
                raise RuntimeError("camera projection callback is unavailable")
            for role, index in representative_indices.items():
                points, valid = self._project_points(positions[index])
                points = np.asarray(points, dtype=np.float64)
                valid = np.asarray(valid, dtype=bool)
                if points.shape != (positions.shape[1], 2) or valid.shape != (
                    positions.shape[1],
                ):
                    raise ValueError("camera projector returned invalid shapes")
                if valid.sum() < 2:
                    raise RuntimeError("fewer than two trajectory points are projectable")
                projected[role] = (points, valid)
        except Exception:
            projection_unavailable = True

        figure, axes = plt.subplots(1, 4, figsize=(16, 4), constrained_layout=True)
        image = _as_uint8_rgb(observation_image)
        axes[0].imshow(image)
        axes[0].set_title(f"Observation\n{mode_id} · weight={weight:.3f}")
        axes[0].axis("off")

        for axis, (role, index) in zip(axes[1:], representative_indices.items()):
            if projection_unavailable:
                self._draw_task_space_fallback(
                    axis,
                    role,
                    relative_positions[index],
                    relative_rotvecs[index],
                    grippers[index],
                )
            else:
                points, valid = projected[role]
                self._draw_overlay(
                    axis,
                    image,
                    role,
                    points,
                    valid,
                    grippers[index],
                )

        figure.suptitle(
            f"Trajectory Mode Card: {mode_id}"
            + (" · projection unavailable" if projection_unavailable else ""),
            fontsize=12,
        )
        figure.savefig(output_path, dpi=150)
        plt.close(figure)
        return ModeCardResult(output_path, projection_unavailable)

    @staticmethod
    def _draw_overlay(
        axis,
        image: np.ndarray,
        role: str,
        points: np.ndarray,
        valid: np.ndarray,
        gripper: np.ndarray,
    ) -> None:
        height, width = image.shape[:2]
        in_bounds = (
            valid
            & np.isfinite(points).all(axis=1)
            & (points[:, 0] >= 0)
            & (points[:, 0] < width)
            & (points[:, 1] >= 0)
            & (points[:, 1] < height)
        )
        path = points[in_bounds]
        axis.imshow(image)
        if len(path) >= 2:
            axis.plot(path[:, 0], path[:, 1], "-", color="#00e5ff", linewidth=2.5)
            axis.scatter(path[0, 0], path[0, 1], c="#00ff66", s=55, marker="o")
            axis.scatter(path[-1, 0], path[-1, 1], c="#ff3b30", s=65, marker="s")
            mid = max(0, len(path) // 2 - 1)
            axis.annotate(
                "",
                xy=path[min(mid + 1, len(path) - 1)],
                xytext=path[mid],
                arrowprops={"arrowstyle": "->", "color": "white", "lw": 2},
            )
        switches = np.flatnonzero((gripper[1:] >= 0) != (gripper[:-1] >= 0)) + 1
        for switch in switches:
            if switch < len(points) and in_bounds[switch]:
                axis.scatter(
                    points[switch, 0],
                    points[switch, 1],
                    c="#ffd60a",
                    s=85,
                    marker="*",
                    edgecolors="black",
                )
        axis.set_title(f"{role}\nstart ○  end □  grip ★")
        axis.axis("off")

    @staticmethod
    def _draw_task_space_fallback(
        axis,
        role: str,
        position: np.ndarray,
        rotvec: np.ndarray,
        gripper: np.ndarray,
    ) -> None:
        phase = np.linspace(0.0, 1.0, len(position))
        colors = ("#ff3b30", "#34c759", "#007aff")
        for component, color, label in zip(position.T, colors, ("x", "y", "z")):
            axis.plot(phase, component, color=color, label=f"pos {label}")
        axis.plot(
            phase,
            np.linalg.norm(rotvec, axis=1),
            "--",
            color="#af52de",
            label="rotation",
        )
        twin = axis.twinx()
        twin.step(phase, gripper, where="mid", color="#ff9500", alpha=0.7)
        twin.set_ylabel("gripper", color="#ff9500", fontsize=8)
        axis.set_title(f"{role} · task-space fallback")
        axis.set_xlabel("phase")
        axis.grid(alpha=0.2)
        axis.legend(fontsize=7, loc="best")


class CombinedModeCardRenderer:
    """Render all mode medoids on one image for a single Gemini request."""

    _colors = ("#00e5ff", "#ff2d55", "#34c759", "#ffd60a")

    def __init__(
        self,
        project_points: Callable[[np.ndarray], tuple[np.ndarray, np.ndarray]],
    ) -> None:
        self._project_points = project_points

    def render(
        self,
        *,
        observation_image: np.ndarray,
        mode_paths: Mapping[str, np.ndarray],
        output_path: Path,
    ) -> ModeCardResult:
        if not 1 <= len(mode_paths) <= 4:
            raise ValueError("combined mode overlay requires K in [1, 4]")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image = _as_uint8_rgb(observation_image)
        projection_unavailable = False
        figure, axis = plt.subplots(1, 1, figsize=(8, 6), constrained_layout=True)
        axis.imshow(image)
        height, width = image.shape[:2]
        for color, (mode_id, positions) in zip(self._colors, mode_paths.items()):
            try:
                pixels, valid = self._project_points(np.asarray(positions))
                pixels = np.asarray(pixels, dtype=np.float64)
                valid = np.asarray(valid, dtype=bool)
                in_bounds = (
                    valid
                    & np.isfinite(pixels).all(axis=1)
                    & (pixels[:, 0] >= 0)
                    & (pixels[:, 0] < width)
                    & (pixels[:, 1] >= 0)
                    & (pixels[:, 1] < height)
                )
                path = pixels[in_bounds]
                if len(path) < 2:
                    raise RuntimeError("mode has fewer than two visible points")
                axis.plot(path[:, 0], path[:, 1], color=color, linewidth=3, label=mode_id)
                axis.scatter(path[0, 0], path[0, 1], c=color, s=70, marker="o")
                axis.scatter(path[-1, 0], path[-1, 1], c=color, s=80, marker="s")
            except Exception:
                projection_unavailable = True
                break
        if projection_unavailable:
            plt.close(figure)
            figure, axis = plt.subplots(1, 1, figsize=(8, 6), constrained_layout=True)
            for color, (mode_id, positions) in zip(self._colors, mode_paths.items()):
                positions = np.asarray(positions, dtype=np.float64)
                relative = positions - positions[0]
                axis.plot(relative[:, 0], relative[:, 1], color=color, linewidth=3, label=mode_id)
                axis.scatter(relative[0, 0], relative[0, 1], c=color, s=70, marker="o")
                axis.scatter(relative[-1, 0], relative[-1, 1], c=color, s=80, marker="s")
            axis.set_xlabel("relative x (m)")
            axis.set_ylabel("relative y (m)")
            axis.set_aspect("equal", adjustable="box")
            axis.grid(alpha=0.2)
        axis.legend(title="mode ID", loc="best")
        axis.set_title("Mode medoids · start ○ · end □")
        axis.axis("off" if not projection_unavailable else "on")
        figure.savefig(output_path, dpi=150)
        plt.close(figure)
        return ModeCardResult(output_path, projection_unavailable)


def adapter_camera_projector(
    adapter: Any,
) -> Callable[[np.ndarray], tuple[np.ndarray, np.ndarray]]:
    """Create a projection callback without exposing the adapter to the gate."""

    def project(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        from utils.vis_utils import project_3d_to_2d

        params = adapter.get_camera_params(adapter.vlm_camera)
        pixels, valid = project_3d_to_2d(
            points,
            params.intrinsic,
            params.extrinsic,
        )
        pixels = np.asarray(pixels, dtype=np.float64)
        if hasattr(adapter, "get_vlm_image_raw"):
            pixels[:, 1] = float(params.height - 1) - pixels[:, 1]
        return pixels, np.asarray(valid, dtype=bool)

    return project


def _as_uint8_rgb(image: np.ndarray) -> np.ndarray:
    value = np.asarray(image)
    if value.shape[2] == 4:
        value = value[:, :, :3]
    if value.dtype == np.uint8:
        return value
    if value.size and float(np.nanmax(value)) <= 1.0:
        value = value * 255.0
    return np.clip(value, 0, 255).astype(np.uint8)
