#!/usr/bin/env python3
"""Find exact PNG+prompt overlaps between captured Poe replay and Codex runs."""

from __future__ import annotations

from collections import defaultdict
import json

from c0_stage_input_capture_preflight import CAPTURE, ROOT, STUDY, digest
from c0_trace_replay import TRACE, atomic_json, utc


CODEX = STUDY / "artifacts/c0_codex_repro_20260925/outputs"
OUT = STUDY / "docs/03_evidence/c0_online_stage_diagnostic/exact-overlap-20260928.json"


def key(fingerprint: dict) -> tuple:
    return (fingerprint.get("prompt_sha256"), tuple(fingerprint.get("image_png_sha256", [])))


def audit() -> dict:
    old = [json.loads(line) for line in TRACE.read_text().splitlines() if line.strip()]
    captures = []
    for index in range(len(old)):
        folder = CAPTURE / f"request_{index:04d}"
        metadata = json.loads((folder / "metadata.json").read_text())
        fingerprint = {"prompt_sha256": digest(folder / "codex_prompt.txt"),
                       "image_png_sha256": [digest(folder / f"image_{i:02d}.png") for i in (1, 2)]}
        if (fingerprint["prompt_sha256"] != metadata["codex_prompt_sha256"] or
                fingerprint["image_png_sha256"] != metadata["image_png_sha256"]):
            raise RuntimeError(f"Capture request {index} changed")
        captures.append(fingerprint)
    cohorts = {}
    for arm in ("legacy", "current"):
        path = CODEX / arm / "eds_eval/stage_events.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        by_key = defaultdict(list)
        for row in rows:
            fingerprint = (row.get("transport") or {}).get("request_fingerprint")
            if fingerprint:
                by_key[key(fingerprint)].append(row)
        overlaps = []
        for index, fingerprint in enumerate(captures):
            for row in by_key.get(key(fingerprint), []):
                overlaps.append({
                    "capture_index": index, "task_id": old[index]["task_id"],
                    "global_step": old[index]["global_step"],
                    "codex_task_id": row.get("task_id"),
                    "codex_global_step": row.get("global_step"),
                    "poe_stage": old[index]["stage_after"],
                    "poe_guidance": old[index]["guidance_after"],
                    "codex_stage": row.get("stage_after"),
                    "codex_guidance": row.get("guidance_after"),
                    "codex_query_ok": row.get("query_ok"),
                    "same_decision": (old[index]["stage_after"] == row.get("stage_after")
                                      and old[index]["guidance_after"] == row.get("guidance_after")),
                })
        cohorts[arm] = {"online_events": len(rows), "exact_overlaps": len(overlaps),
                        "decision_disagreements": sum(not row["same_decision"] for row in overlaps),
                        "overlaps": overlaps}
    result = {"schema": "c0-stage-exact-overlap-v1", "utc": utc(),
              "captured_requests": len(captures), "cohorts": cohorts}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(OUT, result)
    return result


if __name__ == "__main__":
    result = audit()
    print(json.dumps(result, indent=2))
