"""Bounded, lossless visual evidence for account-based skill planning.

Export recorded RGB frames, never render or step the simulator. Images are
observations, not instructions or a replacement for native success predicates.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from .io_utils import atomic_write_json


CAMERAS = {"image": ("agentview", "外部相机"),
           "image2": ("robot0_eye_in_hand", "腕部相机")}


def failure_frame_indices(actions, frame_count: int, *, active_skill=None,
                          count: int = 3, lookback: int = 10) -> list[tuple[int, str]]:
    """Select T+1 frames: failure, skill entry, and last gripper transition.

    A transition at action i is shown at observation i (before that command).
    Older traces lack skill entry indices, so the last yielded skill step is
    used to recover its entry. Additional temporal frames fill duplicate slots.
    """
    if frame_count < 1:
        raise ValueError("failure trace has no observations")
    last = frame_count - 1
    candidates = [(last, "failure")]
    step = int((active_skill or {}).get("step", 0))
    if step > 0:
        candidates.append((max(0, last - step), "failure_skill_entry"))
    actions = np.asarray(actions).reshape(-1, 7)
    if len(actions) > 1:
        changes = np.flatnonzero(np.signbit(actions[1:, 6]) != np.signbit(actions[:-1, 6])) + 1
        if len(changes):
            candidates.append((int(changes[-1]), "before_last_gripper_change"))
    candidates += [(max(0, last - lookback), "pre_failure"), (last // 2, "trajectory_midpoint"),
                   (0, "failed_attempt_initial")]
    selected = {}
    for index, reason in candidates:
        if index not in selected:
            selected[index] = reason
        if len(selected) >= count:
            break
    return sorted(selected.items())


def _export_images(directory: Path, get_image, indices, *, phase: str,
                   attempt_id: str, metadata: dict, failure_error: str | None = None):
    directory.mkdir(parents=True, exist_ok=True)
    images = []
    for index, reason in indices:
        for field, (camera, name_zh) in CAMERAS.items():
            rgb = np.asarray(get_image(index, field))
            if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[-1] != 3:
                raise ValueError("planning image must be recorded uint8 HWC RGB")
            image_id = f"{attempt_id}:{phase}:{index}:{camera}"
            path = directory / f"{phase}-{index:04d}-{camera}.png"
            # Same pixels/orientation as the dataset, not the webpage's CSS
            # rotation. No crop, resize, overlay or coordinate transform.
            Image.fromarray(rgb).save(path, format="PNG")
            images.append({"image_id": image_id, "path": str(path.resolve()),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "mime_type": "image/png", "camera": camera, "camera_zh": name_zh,
                "width": int(rgb.shape[1]), "height": int(rgb.shape[0]),
                "phase": phase, "frame_index": index, "selection_reason": reason,
                "init_state_id": str(metadata.get("init_state_id", "")),
                "coverage_cell": str(metadata.get("coverage_cell", "")),
                "failure_error": failure_error, "pixel_orientation": "as_recorded"})
    return images


def export_failure_images(writer, attempt: Path, *, detail: dict, count: int, lookback: int):
    indices = failure_frame_indices(writer.actions, len(writer.frames),
        active_skill=detail.get("active_skill"), count=count, lookback=lookback)
    images = _export_images(attempt / "visuals", lambda i, key: getattr(writer.frames[i], key),
        indices, phase="failure", attempt_id=attempt.name, metadata=writer.metadata,
        failure_error=detail.get("error"))
    atomic_write_json(attempt / "failure_visuals.json", {"images": images})
    return images


def _legacy_failure_images(failure: dict, *, count: int, lookback: int):
    """Reuse failures from the already-running geometry-only collector."""
    attempt = Path(failure["attempt"])
    detail = json.loads((attempt / "failure.json").read_text())
    with np.load(attempt / "trajectory.npz", allow_pickle=False) as trace:
        # Decompress each RGB array once, not once per selected frame.
        arrays = {key: trace[key] for key in CAMERAS}
        if len(arrays["image"]) != len(arrays["image2"]) or len(arrays["image"]) != len(trace["action"]) + 1:
            raise ValueError("failed visual trace violates T+1/T alignment")
        indices = failure_frame_indices(trace["action"], len(arrays["image"]),
            active_skill=failure.get("active_skill"), count=count, lookback=lookback)
        images = _export_images(attempt / "visuals", lambda i, key: arrays[key][i], indices,
            phase="failure", attempt_id=attempt.name, metadata=detail.get("writer_metadata", {}),
            failure_error=failure.get("error"))
    atomic_write_json(attempt / "failure_visuals.json", {"images": images})
    return images


def build_visual_context(writer, attempt: Path, failures: list[dict], *, count=3, lookback=10):
    if not writer.frames or writer.actions:
        raise ValueError("initial planning images require an initialized zero-action attempt")
    images = _export_images(attempt / "visuals", lambda i, key: getattr(writer.frames[i], key),
        [(0, "current_attempt_initial")], phase="initial", attempt_id=attempt.name,
        metadata=writer.metadata)
    # Text diagnostics retain the last three failures. Images focus on the
    # latest failure: at most two initial + six failure images by default.
    if failures:
        failure = failures[-1]
        manifest = Path(failure["attempt"]) / "failure_visuals.json"
        previous = (json.loads(manifest.read_text())["images"] if manifest.exists()
                    else _legacy_failure_images(failure, count=count, lookback=lookback))
        for item in previous:
            if item["init_state_id"] != str(writer.metadata["init_state_id"]) or item["coverage_cell"] != str(writer.metadata["coverage_cell"]):
                raise ValueError("failure images belong to a different collection entry")
        images.extend(previous)
    result = {"schema_version": "libero-skill-visuals-v1", "images": images,
        "usage": "Inspect every image using an image-viewing tool before planning. Use RGB to assess contact, occlusion and grasp posture; simulator geometry remains the metric reference, native predicates alone decide success. Report uncertainty and conflicts, never infer an invisible grasp as confirmed.",
        "selection_config": {"failure_keyframe_count": count, "failure_lookback_steps": lookback,
                             "failure_attempts": 1, "cameras": list(CAMERAS)},
        "source": "recorded_rgb_no_simulator_steps", "privileged_collection_only": True}
    result["manifest_sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    atomic_write_json(attempt / "visual_observations.json", result)
    return result


def include_ticket_visuals(visuals, ticket, *, output_path):
    """Include actual expansion images, explicitly distinct from the collection's current scene."""
    from .io_utils import sha256_file
    result = dict(visuals)
    result.pop("manifest_sha256", None)
    images = list(result.get("images", []))
    refs = list(ticket.get("multimodal_evidence", {}).get("images", []))
    overlay = ticket.get("multimodal_evidence", {}).get("failure_overlay")
    if overlay:
        refs.append(overlay)
    for index, ref in enumerate(refs):
        path = Path(ref["path"])
        if sha256_file(path) != ref["sha256"]:
            raise ValueError("expansion ticket image evidence changed")
        images.append({**ref, "image_id": f"ticket:{ticket['ticket_id']}:{index}",
                       "mime_type":"image/png", "phase":"ticket_failure_context",
                       "note_zh":"这是触发扩张时的真实画面，并非当前采集初始化；动作坐标以当前 scene 为准。"})
    result["images"] = images
    result["manifest_sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    atomic_write_json(output_path, result)
    return result
