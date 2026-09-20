"""Render every predicted candidate; real observations remain explicitly identified."""
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
class CandidateCardResult:
    path: Path
    projection_unavailable: bool

class CandidateCardRenderer:
    def __init__(self, project_points: Callable | None) -> None:
        self._project_points = project_points

    def render(self, *, observation_image: np.ndarray,
               candidate_paths: Mapping[str, np.ndarray], output_path: Path) -> CandidateCardResult:
        if not candidate_paths:
            raise ValueError("at least one candidate is required")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image = _as_uint8_rgb(observation_image)
        figure, axes = plt.subplots(1, 2, figsize=(14, 7), constrained_layout=True)
        axes[0].imshow(image)
        axes[0].set_title("Real observation + predicted trajectories")
        axes[0].axis("off")
        unavailable = False
        for index, (candidate_id, positions) in enumerate(candidate_paths.items()):
            points = np.asarray(positions, dtype=np.float64)
            color = plt.get_cmap("turbo")(index / max(1, len(candidate_paths) - 1))
            axes[1].plot(points[:, 0], points[:, 1], color=color, lw=1,
                         label=f"{index}: {candidate_id}")
            axes[1].scatter(*points[-1, :2], color=color, s=12)
            try:
                if self._project_points is None:
                    raise ValueError("projection unavailable")
                pixels, valid = self._project_points(points)
                pixels = np.asarray(pixels, dtype=float).copy()
                valid = np.asarray(valid, dtype=bool) & np.isfinite(pixels).all(axis=1)
                if not valid.any():
                    raise ValueError("no visible points")
                # NaNs break lines across invisible segments; do not invent connections.
                pixels[~valid] = np.nan
                axes[0].plot(pixels[:, 0], pixels[:, 1], color=color, lw=1)
            except (ValueError, RuntimeError, TypeError):
                unavailable = True
        axes[1].set_title(f"All {len(candidate_paths)} candidates (world XY, metres)")
        axes[1].set_aspect("equal", adjustable="datalim")
        axes[1].grid(alpha=.2)
        if len(candidate_paths) <= 12:
            axes[1].legend(fontsize=6)
        figure.savefig(output_path, dpi=150)
        plt.close(figure)
        return CandidateCardResult(output_path, unavailable)

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
