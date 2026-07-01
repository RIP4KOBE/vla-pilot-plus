"""Qualitative visualization helpers for RDT+EDS evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import cv2
import imageio.v2 as imageio
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

    return saved
