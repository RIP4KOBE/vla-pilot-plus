"""Capture backend must preserve the replay decision and exact Stage PNGs."""

import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.gemini_grounder import create_gemini_stage_recognizer
from core.diagnostics.stage_replay import CaptureTraceReplayStageRecognizer


def test_capture_replay_preserves_response_and_multimodal_input(tmp_path):
    template = tmp_path / "template.txt"
    template.write_text("{trigger_reason} {instruction} {stage_descriptions} {keypoint_info}")
    trace = tmp_path / "trace.jsonl"
    context = {
        "episode_id": 0, "task_id": 3, "episode_seed": 546,
        "global_step": 56, "chunk_id": 7, "trigger_reason": "gripper closed",
        "stage_before": 1, "guidance_before": False,
    }
    raw = "stage 2\nguidance: no\nevidence: grasped"
    trace.write_text(json.dumps({**context, "query_status": "ok", "raw_response": raw}) + "\n")
    root = tmp_path / "capture"
    config = {
        "backend": "trace_replay_capture", "replay_trace_path": str(trace),
        "capture_dir": str(root), "stage_template_path": str(template),
    }
    recognizer = create_gemini_stage_recognizer(config)
    assert isinstance(recognizer, CaptureTraceReplayStageRecognizer)
    recognizer.set_trace_context({
        "episode_id": 0, "task_id": 3, "episode_seed": 546,
        "global_step": 56, "chunk_id": 7, "current_stage": 1,
        "use_guidance": False,
    }, "gripper closed")
    initial = np.full((4, 5, 3), 20, dtype=np.uint8)
    current = np.full((6, 7, 3), 180, dtype=np.uint8)
    assert recognizer.identify_stage_and_guidance(
        current_rgb=current, init_img_with_keypoints=initial,
        instruction="put target in basket", stage_descriptions="stage 1 pick, stage 2 place",
        num_stages=2, trigger_reason="gripper closed",
    ) == (2, False)
    folder = root / "request_0000"
    metadata = json.loads((folder / "metadata.json").read_text())
    parts = json.loads((folder / "parts.json").read_text())
    assert metadata["historical_raw_response"] == raw
    assert metadata["context"] == context
    assert [part["type"] for part in parts] == ["text", "text", "image", "text", "image"]
    assert np.array_equal(np.asarray(Image.open(folder / "image_01.png")), initial)
    assert np.array_equal(np.asarray(Image.open(folder / "image_02.png")), current)
    assert metadata["image_png_sha256"] == [
        hashlib.sha256((folder / name).read_bytes()).hexdigest()
        for name in ("image_01.png", "image_02.png")
    ]
    assert hashlib.sha256((folder / "codex_prompt.txt").read_bytes()).hexdigest() == metadata["codex_prompt_sha256"]
    assert recognizer.cursor == 1
    with pytest.raises(ValueError, match="must not already exist"):
        create_gemini_stage_recognizer(config)
