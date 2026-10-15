#!/usr/bin/env python3
"""Audit exact online Codex Stage input capture against emitted event fingerprints."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from c0_stage_input_capture_preflight import ROOT, digest
from c0_trace_replay import atomic_json, utc


def audit(output: Path, require_complete: bool = True) -> dict:
    events_file = output / "eds_eval/stage_events.jsonl"
    events = [json.loads(line) for line in events_file.read_text().splitlines()
              if line.strip()] if events_file.exists() else []
    captures = sorted((output / "captured_stage_inputs").glob("request_*"))
    problems = []
    for index, event in enumerate(events):
        folder = output / "captured_stage_inputs" / f"request_{index:04d}"
        if not folder.is_dir():
            problems.append(f"missing_capture_{index}")
            continue
        try:
            metadata = json.loads((folder / "metadata.json").read_text())
            parts = json.loads((folder / "parts.json").read_text())
            texts = [part["text"] for part in parts if part["type"] == "text"]
            images = [(folder / part["file"]).read_bytes() for part in parts
                      if part["type"] == "image_url"]
            prompt = "\n\n".join(texts)
            prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
            image_hashes = [hashlib.sha256(data).hexdigest() for data in images]
            if (metadata["query_index"] != index or
                metadata["prompt_sha256"] != prompt_hash or
                metadata["image_png_sha256"] != image_hashes or
                digest(folder / "codex_prompt.txt") != prompt_hash or
                any(part["sha256"] != digest(folder / part["file"])
                    for part in parts if part["type"] == "image_url") or
                event.get("transport", {}).get("request_fingerprint") != {
                    "prompt_sha256": prompt_hash, "image_png_sha256": image_hashes}):
                problems.append(f"fingerprint_mismatch_{index}")
        except (OSError, KeyError, ValueError, TypeError, json.JSONDecodeError):
            problems.append(f"malformed_capture_{index}")
    if require_complete and len(captures) != len(events):
        problems.append("capture_event_count_mismatch")
    result = {"schema": "c0-online-stage-capture-audit-v1", "utc": utc(),
              "output": str(output), "stage_events": len(events),
              "captured_queries": len(captures), "valid": not problems,
              "problems": problems}
    atomic_json(output / "capture-audit.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", required=True)
    parser.add_argument("--replicate", type=int, default=1)
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--partial", action="store_true")
    args = parser.parse_args()
    base = f"online_{args.condition}_replicate{args.replicate}"
    label = base if args.attempt == 1 else f"{base}_attempt{args.attempt}"
    result = audit(ROOT / "outputs" / label, require_complete=not args.partial)
    print(json.dumps(result, indent=2))
    if not result["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
