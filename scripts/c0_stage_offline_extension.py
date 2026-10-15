#!/usr/bin/env python3
"""Extend one screened Codex Stage condition across all captured C0 requests."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT_CODE = Path(__file__).resolve().parents[1]
if str(ROOT_CODE) not in sys.path:
    sys.path.insert(0, str(ROOT_CODE))

from core.codex_stage import CodexStageRecognizer
from c0_stage_input_capture_preflight import digest
from c0_stage_offline_diagnostic import (
    CONDITIONS, MAX_NEW_CALLS, OUT, RESULTS, load_trace,
    prepare, result_row, summary,
)
from c0_trace_replay import atomic_json


def run() -> None:
    frozen = prepare()
    selection_path = OUT / "selection.json"
    screening_path = OUT / "screening-summary.json"
    if not selection_path.is_file() or not screening_path.is_file():
        raise RuntimeError("Offline screening must be reviewed and frozen before extension")
    selection = json.loads(selection_path.read_text())
    condition = selection.get("condition")
    if condition not in CONDITIONS or selection.get("summary_sha256") != digest(screening_path):
        raise RuntimeError("Selected condition differs from frozen screening evidence")
    rows = [json.loads(line) for line in RESULTS.read_text().splitlines() if line.strip()]
    if len(rows) > MAX_NEW_CALLS:
        raise RuntimeError("Offline call cap exceeded")
    effective = {(row["request_index"], row["condition"], row["repeat"])
                 for row in rows if row["error"] is None}
    fmt, effort, event_policy = CONDITIONS[condition]
    recognizer = CodexStageRecognizer({
        "backend": "codex_cli", "model": "gpt-6-astra",
        "reasoning_effort": effort, "output_format": fmt,
        "event_policy": event_policy, "timeout_seconds": 180,
    })
    historical = load_trace()
    chosen = set(frozen["selected_indices"])
    with RESULTS.open("a") as stream:
        for index in range(len(historical)):
            if index in chosen or (index, condition, 0) in effective:
                continue
            if len(rows) >= MAX_NEW_CALLS:
                raise RuntimeError("Offline call cap reached before full extension")
            row = result_row(index, condition, 0, recognizer, historical[index])
            row["phase"] = "extension"
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            rows.append(row)
            print(f"extension {len(rows)} request={index} stage={row['stage']} "
                  f"guidance={row['guidance']} error={row['error']}", flush=True)
    report = summary()
    atomic_json(OUT / "extension-summary.json", report)
    valid_inputs = {row["request_index"] for row in rows
                    if row["condition"] == condition and row["error"] is None}
    coverage = {"schema": "c0-stage-extension-coverage-v1",
                "condition": condition, "valid_input_count": len(valid_inputs),
                "total_historical_inputs": len(historical),
                "missing_input_indices": sorted(set(range(len(historical))) - valid_inputs),
                "physical_calls": len(rows)}
    atomic_json(OUT / "extension-coverage.json", coverage)
    print(json.dumps(coverage, indent=2), flush=True)


if __name__ == "__main__":
    run()
