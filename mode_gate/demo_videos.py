"""CPU-only viewing copies of native-success demonstrations; never replay actions.

Each MP4 contains both recorded cameras, including the initial and final frame.
Only the viewing copy is rotated to match the teleoperation page. HDF5 pixels,
labels and training eligibility are never changed. Commands are one-shot jobs,
not a resident watcher or scheduled task.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import json
import logging
import os
from pathlib import Path
import subprocess
import sys

import h5py
import numpy as np

from .io_utils import atomic_write_json, sha256_file


def export_success_video(source: Path, output: Path) -> dict | None:
    """Export one committed native success, idempotently and atomically."""
    import imageio_ffmpeg

    source, output = Path(source).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    video = output / f"{source.stem}.success.mp4"
    manifest = video.with_suffix(".json")
    with (output / ".export.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        with h5py.File(source, "r") as handle:
            if not (handle.attrs.get("explicit_success", False)
                    and handle.attrs.get("simulator_success", False)
                    and (handle.attrs.get("collection_committed", False)
                         or handle.attrs.get("replay_validated", False))):
                return None
            steps = len(handle["action"])
            if not steps or not bool(handle["success"][-1]):
                raise ValueError("success video requires a native successful final transition")
            cameras = [handle[f"observation/images/{key}"] for key in ("image", "image2")]
            frames = steps + 1
            if any(array.shape != (frames, 256, 256, 3) or array.dtype != np.uint8 for array in cameras):
                raise ValueError("success video requires aligned T+1 uint8 dual-camera frames")
            fps = float(handle.attrs["fps"])
            if not np.isfinite(fps) or not 0 < fps <= 240:
                raise ValueError("invalid recorded simulation fps")
            if manifest.exists() and video.exists():
                prior = json.loads(manifest.read_text())
                if (prior.get("schema_version") == "libero-success-video-v1"
                        and prior.get("source_demo") == source.name
                        and prior.get("frame_count") == frames and prior.get("fps") == fps
                        and prior.get("video_sha256") == sha256_file(video)):
                    return prior
            temporary = output / f".{video.stem}.{os.getpid()}.tmp.mp4"
            encoder = imageio_ffmpeg.write_frames(str(temporary), (512, 256), fps=fps,
                codec="libx264", pix_fmt_in="rgb24", pix_fmt_out="yuv420p",
                ffmpeg_log_level="error", quality=None,
                output_params=["-threads", "1", "-preset", "veryfast", "-crf", "18",
                               "-movflags", "+faststart"])
            try:
                encoder.send(None)
                try:
                    # Bounded chunks avoid loading an entire long episode.
                    for start in range(0, frames, 32):
                        chunks = [array[start:start + 32] for array in cameras]
                        for left, right in zip(*chunks):
                            frame = np.concatenate((left[::-1, ::-1], right[::-1, ::-1]), axis=1)
                            encoder.send(np.ascontiguousarray(frame))
                finally:
                    encoder.close()
                encoded_frames, _ = imageio_ffmpeg.count_frames_and_secs(str(temporary))
                if encoded_frames != frames:
                    raise RuntimeError(f"video frame count mismatch: {encoded_frames} != {frames}")
                with temporary.open("rb") as stream:
                    os.fsync(stream.fileno())
                os.replace(temporary, video)
            finally:
                # Only this invocation's unfinished viewing copy is disposable.
                temporary.unlink(missing_ok=True)
            result = {"schema_version": "libero-success-video-v1",
                "source_demo": source.name, "source_hdf5": str(source),
                "source_hdf5_sha256_at_export": sha256_file(source),
                "video_path": str(video), "video_sha256": sha256_file(video),
                "frame_count": frames, "action_count": steps, "fps": fps,
                "duration_seconds": frames / fps, "simulation_action_seconds": steps / fps,
                "task": str(handle.attrs.get("task", "")),
                "task_instruction": str(handle.attrs.get("task_instruction", "")),
                "ticket_id": str(handle.attrs.get("ticket_id", "")),
                "init_state_id": str(handle.attrs.get("init_state_id", "")),
                "coverage_cell": str(handle.attrs.get("coverage_cell", "")),
                "demonstration_source": str(handle.attrs.get("demonstration_source", "human")),
                "native_success": True, "replay_validated_at_export": bool(handle.attrs.get("replay_validated", False)),
                "cameras_left_to_right": ["agentview", "robot0_eye_in_hand"],
                "display_transform": "rotate_each_camera_180_degrees_like_teleop_page",
                "encoding": {"codec": "h264", "pixel_format": "yuv420p", "crf": 18, "cpu_threads": 1},
                "created_at": datetime.now(timezone.utc).isoformat()}
            atomic_write_json(manifest, result)
            return result


def export_ticket_videos(ticket_root: Path) -> list[dict]:
    ticket_root = Path(ticket_root).resolve()
    results = []
    # Native-success traces rejected later for coverage/curation still deserve
    # a viewing copy. This does not re-admit them to a training dataset.
    for directory in ("raw", "rejected"):
        for source in sorted((ticket_root / directory).glob("demo-*.hdf5")):
            if source.name.count(".") != 1:
                continue
            result = export_success_video(source, ticket_root / "videos")
            if result is not None:
                results.append(result)
    return results


def start_success_video_export(ticket_root: Path) -> None:
    """Launch a finite CPU export after commit without blocking control/saving."""
    try:
        directory = Path(ticket_root).resolve() / "videos"
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / "export.log").open("ab") as log:
            subprocess.Popen([sys.executable, "-m", "mode_gate.demo_videos", "--ticket-root", str(directory.parent)],
                cwd=Path(__file__).resolve().parents[1], stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                env={**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"})
    except OSError:
        # A playback-copy failure must never lose a committed demonstration or
        # stop physical collection. The one-shot command can retry from HDF5.
        logging.exception("Could not start success-video export; original HDF5 is retained")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticket-root", type=Path, required=True)
    args = parser.parse_args()
    results = export_ticket_videos(args.ticket_root)
    print(json.dumps({"success_videos": len(results), "videos": [item["video_path"] for item in results]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
