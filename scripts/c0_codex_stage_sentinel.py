#!/usr/bin/env python3
"""CPU-only live check that Codex Stage sees two images in the intended order.

Uses the same Stage adapter/model/output protocol as the C0 Codex experiment.
The images are synthetic; this is an input-transport check, not a robot score.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
from datetime import datetime, timezone

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.codex_stage import CodexStageRecognizer


TEMPLATE = """Inspect the two attached images in the documented order: Initial Image,
then Current Image. The visible image labels are A RED and B BLUE. Decide using
the Current Image only, regardless of the Initial Image and trigger reason.
If Current Image is B BLUE, respond stage 2, guidance no, and say BLUE in evidence.
If Current Image is A RED, respond stage 1, guidance yes, and say RED in evidence.
Use the Stage output format required by the caller.

Trigger: {trigger_reason}
Task: {instruction}
Stages: {stage_descriptions}
Keypoints: {keypoint_info}
"""


def _image(name: str) -> np.ndarray:
    color = (235, 30, 30) if name == "red" else (25, 70, 235)
    image = Image.new("RGB", (256, 256), color)
    canvas = ImageDraw.Draw(image)
    label = "A RED" if name == "red" else "B BLUE"
    canvas.rectangle((24, 98, 232, 154), fill="white")
    canvas.text((40, 116), label, fill="black")
    return np.asarray(image).copy()


def run(output: Path, repeats: int) -> dict:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")
    if not 1 <= repeats <= 3:
        raise ValueError("repeats must be between 1 and 3")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="c0_stage_sentinel_") as temporary:
        template = Path(temporary) / "stage_template.txt"
        template.write_text(TEMPLATE)
        recognizer = CodexStageRecognizer({
            "backend": "codex_cli", "model": "gpt-6-astra",
            "reasoning_effort": "low", "timeout_seconds": 180,
            "output_format": "json_schema_v1",
            "event_policy": "completed_known_startup_warnings_combo_v5",
            "stage_template_path": str(template),
        })
        rows = []
        for _ in range(repeats):
            for initial, current in (("red", "blue"), ("blue", "red")):
                stage, guidance = recognizer.identify_stage_and_guidance(
                    current_rgb=_image(current),
                    init_img_with_keypoints=_image(initial),
                    instruction="synthetic image-order transport diagnostic",
                    stage_descriptions="1: current red; 2: current blue",
                    num_stages=2, trigger_reason="synthetic diagnostic",
                )
                result = recognizer.last_result or {}
                expected_stage = 2 if current == "blue" else 1
                expected_guidance = current == "red"
                row = {
                    "initial_image": initial, "current_image": current,
                    "expected_stage": expected_stage,
                    "expected_guidance": expected_guidance,
                    "observed_stage": stage, "observed_guidance": guidance,
                    "query_ok": result.get("ok"), "error": result.get("error"),
                    "evidence": result.get("evidence"),
                    "raw_response": result.get("raw_response"),
                    "latency_s": result.get("query_latency_s"),
                    "request_fingerprint": (result.get("transport") or {}).get("request_fingerprint"),
                    "model": recognizer.model,
                    "reasoning_effort": recognizer.reasoning_effort,
                    "public_config_sha256": recognizer.transport_metadata["public_config_sha256"],
                }
                row["pass"] = (row["query_ok"] is True and stage == expected_stage
                               and guidance is expected_guidance
                               and current.upper() in (row["evidence"] or "").upper())
                rows.append(row)
                output.write_text(json.dumps({
                    "schema": "c0-codex-stage-sentinel-v1",
                    "created_utc": datetime.now(timezone.utc).isoformat(),
                    "calls_completed": len(rows), "all_pass": all(item["pass"] for item in rows),
                    "rows": rows,
                }, indent=2, sort_keys=True) + "\n")
                print(f"{initial}->{current}: stage={stage} guidance={guidance} pass={row['pass']}", flush=True)
                if not result.get("ok"):
                    raise RuntimeError(f"Stage call failed: {result.get('error')}")
        return json.loads(output.read_text())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args()
    result = run(args.output, args.repeats)
    if not result["all_pass"]:
        raise SystemExit("Synthetic image-order sentinel failed")


if __name__ == "__main__":
    main()
