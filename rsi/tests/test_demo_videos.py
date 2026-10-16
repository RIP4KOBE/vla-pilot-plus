import json
from pathlib import Path

import h5py
import numpy as np
import pytest

from mode_gate.demo_videos import export_success_video, export_ticket_videos, start_success_video_export
from mode_gate.io_utils import sha256_file


def demo(tmp_path, *, success=True, committed=True, frames=5):
    path = tmp_path / "raw/demo-000-test.hdf5"
    path.parent.mkdir(parents=True)
    left = np.zeros((frames, 256, 256, 3), dtype=np.uint8)
    left[:, :128, :128, 0] = 255
    right = np.zeros_like(left)
    right[..., 1] = 255
    with h5py.File(path, "w") as handle:
        handle.create_dataset("observation/images/image", data=left)
        handle.create_dataset("observation/images/image2", data=right)
        handle.create_dataset("action", data=np.zeros((frames - 1, 7)))
        handle.create_dataset("success", data=np.asarray([False] * (frames - 2) + [success]))
        handle.attrs.update(explicit_success=True, simulator_success=success,
                            collection_committed=committed, fps=20, task="test", ticket_id="test")
    return path


def test_success_video_contains_both_cameras_and_final_frame(tmp_path):
    ffmpeg = pytest.importorskip("imageio_ffmpeg")
    path = demo(tmp_path)
    original = sha256_file(path)
    result = export_success_video(path, tmp_path / "videos")
    assert result["frame_count"] == 5 and result["action_count"] == 4
    assert result["fps"] == 20 and result["native_success"]
    assert result["replay_validated_at_export"] is False
    assert result["source_hdf5_sha256_at_export"] == original == sha256_file(path)
    reader = ffmpeg.read_frames(result["video_path"], pix_fmt="rgb24")
    metadata = next(reader)
    frames = list(reader)
    assert metadata["size"] == (512, 256) and len(frames) == 5
    rgb = np.frombuffer(frames[0], np.uint8).reshape(256, 512, 3)
    # Webpage orientation: original top-left red square is now bottom-right.
    assert rgb[200, 200, 0] > 240 and rgb[40, 40, 0] < 10
    assert rgb[100, 400, 1] > 240
    video = Path(result["video_path"])
    before = video.stat().st_mtime_ns
    assert export_ticket_videos(tmp_path) == [result]
    assert video.stat().st_mtime_ns == before and sha256_file(path) == original
    assert json.loads(video.with_suffix(".json").read_text()) == result


@pytest.mark.parametrize("success,committed", [(False, True), (True, False)])
def test_failed_or_uncommitted_demo_does_not_get_success_video(tmp_path, success, committed):
    path = demo(tmp_path, success=success, committed=committed)
    assert export_success_video(path, tmp_path / "videos") is None
    assert not list(tmp_path.rglob("*.mp4"))


def test_video_rejects_broken_t_plus_one_contract(tmp_path):
    path = demo(tmp_path)
    with h5py.File(path, "r+") as handle:
        del handle["observation/images/image2"]
        handle.create_dataset("observation/images/image2", data=np.zeros((4, 256, 256, 3), np.uint8))
    with pytest.raises(ValueError, match="T\\+1"):
        export_success_video(path, tmp_path / "videos")
    assert not list(tmp_path.rglob("*.mp4"))


def test_export_is_one_shot_and_never_requests_gpu(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("mode_gate.demo_videos.subprocess.Popen", lambda args, **kwargs: calls.append((args, kwargs)))
    start_success_video_export(tmp_path)
    args, kwargs = calls[0]
    assert args[1:4] == ["-m", "mode_gate.demo_videos", "--ticket-root"]
    assert args[-1] == str(tmp_path)
    assert kwargs["env"]["OMP_NUM_THREADS"] == "1" and kwargs["start_new_session"]


def test_video_launch_failure_does_not_break_success_commit(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("test spawn failure")
    monkeypatch.setattr("mode_gate.demo_videos.subprocess.Popen", fail)
    start_success_video_export(tmp_path)
