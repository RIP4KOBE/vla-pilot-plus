"""Real observation, executed motion and explicitly suggested-path evidence bundles."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from .experiences import artifact_ref
from .io_utils import atomic_write_json


def policy_camera_images(adapter):
    images = {}
    for key, value in adapter.get_policy_observation(sample_num=1).items():
        if not str(key).startswith("observation.images."):
            continue
        if hasattr(value, "detach"):
            value = value.detach().cpu().numpy()
        array = np.asarray(value)
        if array.ndim == 4:
            array = array[0]
        if array.shape[0] in (1, 3, 4):
            array = np.moveaxis(array, 0, -1)
        if array.dtype != np.uint8:
            array = np.clip(array * 255 if array.max() <= 1 else array, 0, 255).astype(np.uint8)
        images[str(key)] = array[..., :3]
    return images


def build_decision_evidence(*, directory, context, analysis_path, executed_history,
                            images, project_points, library, episode_id):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    refs = []
    for i, (camera, image) in enumerate(images.items()):
        path = directory / f"observation_{i}.png"
        Image.fromarray(np.asarray(image, dtype=np.uint8)).save(path)
        refs.append(artifact_ref(path, kind="real_observation", camera=camera))
    canvas = Image.fromarray(np.asarray(context.observation_image, dtype=np.uint8))
    raw = directory / "failure_observation.png"
    canvas.save(raw)
    refs.append(artifact_ref(raw, kind="real_observation", camera="planner_camera"))
    drawing = ImageDraw.Draw(canvas)
    history = np.asarray(executed_history).reshape(-1, 15)
    projected_history = []
    if len(history) and project_points:
        pixels, valid = project_points(history[:, 7:10])
        for i in range(1, len(pixels)):
            if valid[i-1] and valid[i] and np.isfinite(pixels[i-1:i+1]).all():
                drawing.line([tuple(pixels[i-1]), tuple(pixels[i])], fill=(0, 210, 255), width=2)
        projected_history = [{"pixel_xy": np.asarray(p).tolist(), "visible": bool(v)} for p,v in zip(pixels,valid)]
    target = context.metadata.get("target_object_id")
    target_xyz = context.metadata.get("object_positions", {}).get(target)
    if target_xyz is not None and project_points:
        pixels, valid = project_points(np.asarray(target_xyz).reshape(1,3))
        if valid[0] and np.isfinite(pixels[0]).all():
            x,y = map(float,pixels[0])
            drawing.ellipse((x-5,y-5,x+5,y+5), outline=(255,60,60), width=2)
    overlay = directory / "executed_failure_overlay.png"
    canvas.save(overlay)
    full = library.finish_video(episode_id)
    segments = [x for x in library.media.iter_valid() if x["episode_id"] == episode_id]
    payload = {"schema_version":"multimodal-ticket-evidence-v3", "episode_id":episode_id,
        "decision_context_id":context.context_id, "task_instruction":context.task_instruction,
        "images":refs, "failure_overlay":artifact_ref(overlay, kind="observed_overlay"),
        "legend_zh":"蓝色为已执行的实测末端路径；红圈为真实场景中的目标位置。候选是预测，不是已执行。",
        "all_candidates":artifact_ref(analysis_path, kind="predicted_candidates") if analysis_path else None,
        "executed_history":history.tolist(), "executed_pixels":projected_history,
        "coordinate_frame":"world", "target_object_id":target,
        "object_positions":context.metadata.get("object_positions", {}),
        "clips":segments[-3:], "full_video":artifact_ref(full, kind="complete_episode_video") if full else None}
    path = directory / "evidence.json"
    atomic_write_json(path, payload)
    return path


def render_suggested_path(evidence, visual_guidance, *, output_dir):
    """A pixel-space sketch proposed by Planner; never claim it was executed."""
    path = visual_guidance.get("suggested_path_pixels", [])
    if not path:
        return None
    source = next((x for x in evidence.get("images", []) if x.get("camera") == "planner_camera"), None)
    if source is None:
        raise ValueError("suggested path requires its real source observation")
    points = np.asarray(path, dtype=float)
    image = Image.open(source["path"]).convert("RGB")
    if points.ndim != 2 or points.shape[1] != 2 or not np.isfinite(points).all():
        raise ValueError("suggested pixel path must contain finite xy pairs")
    if np.any(points < 0) or np.any(points >= np.array(image.size)):
        raise ValueError("suggested path lies outside its source image")
    draw = ImageDraw.Draw(image)
    if len(points) > 1:
        draw.line([tuple(p) for p in points], fill=(255,180,0), width=3)
    draw.text((5,5), "PLANNER SUGGESTION - NOT EXECUTED", fill=(255,180,0))
    output = Path(output_dir) / "planner_suggested_path.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    return artifact_ref(output, kind="suggested_path_overlay", source_image=source,
                        legend_zh="黄色路径仅为 Planner 建议，未执行，控制器仍需 IK/碰撞检查。")
