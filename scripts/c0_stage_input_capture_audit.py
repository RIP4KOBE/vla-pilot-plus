#!/usr/bin/env python3
"""Check that Stage-input capture left the historical C0 replay unchanged."""

from __future__ import annotations

import hashlib
import json

import c0_current_trace_replay as replay
from c0_stage_input_capture_preflight import CAPTURE, OUTPUT


def audit() -> dict:
    replay.OUTPUT = OUTPUT
    baseline = replay.audit()
    rows = [json.loads(line) for line in (OUTPUT / "eds_eval/stage_events.jsonl").open()]
    problems = []
    captured = sorted(CAPTURE.glob("request_*")) if CAPTURE.is_dir() else []
    if len(captured) != len(rows):
        problems.append(f"capture count {len(captured)} != event count {len(rows)}")
    keys = ("episode_id", "task_id", "episode_seed", "global_step", "chunk_id",
            "trigger_reason", "stage_before", "guidance_before")
    for index, (folder, event) in enumerate(zip(captured, rows)):
        if folder.name != f"request_{index:04d}":
            problems.append(f"unexpected request folder {folder.name}")
            break
        try:
            metadata = json.loads((folder / "metadata.json").read_text())
            parts = json.loads((folder / "parts.json").read_text())
            prompt = (folder / "codex_prompt.txt").read_bytes()
            images = [(folder / f"image_{i:02d}.png").read_bytes() for i in (1, 2)]
        except (OSError, ValueError) as exc:
            problems.append(f"request {index} unreadable: {type(exc).__name__}")
            break
        if metadata.get("query_index") != index:
            problems.append(f"request {index} index mismatch")
        if metadata.get("historical_raw_response") != event.get("raw_response"):
            problems.append(f"request {index} raw reply mismatch")
        if any(metadata.get("context", {}).get(key) != event.get(key) for key in keys):
            problems.append(f"request {index} context mismatch")
        if [part.get("type") for part in parts] != ["text", "text", "image", "text", "image"]:
            problems.append(f"request {index} part order mismatch")
        if metadata.get("codex_prompt_sha256") != hashlib.sha256(prompt).hexdigest():
            problems.append(f"request {index} prompt hash mismatch")
        if metadata.get("image_png_sha256") != [hashlib.sha256(image).hexdigest() for image in images]:
            problems.append(f"request {index} image hash mismatch")
    result = {
        "schema": "c0-stage-input-capture-audit-v1",
        "valid": baseline.get("valid_full_replay") is True and len(captured) == len(rows) == 127
                 and not problems,
        "historical_replay_valid": baseline.get("valid_full_replay"),
        "success_count": baseline.get("success_count"),
        "success_task_ids": baseline.get("success_task_ids"),
        "video_sha256_equal_by_task": baseline.get("video_sha256_equal_by_task"),
        "stage_event_count": len(rows), "captured_request_count": len(captured),
        "problems": problems,
    }
    (OUTPUT / "capture-audit.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


if __name__ == "__main__":
    result = audit()
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["valid"]:
        raise SystemExit(1)
