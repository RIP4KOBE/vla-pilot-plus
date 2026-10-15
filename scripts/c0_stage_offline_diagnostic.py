#!/usr/bin/env python3
"""Compare Codex Stage protocols on exact C0 replay inputs without a GPU.

This probe does not edit the online adapter or make claims about closed-loop
success. Every call is recorded before the next is issued and can be resumed.
"""

from __future__ import annotations

import argparse
import base64
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from datetime import datetime, timezone

ROOT_CODE = Path(__file__).resolve().parents[1]
if str(ROOT_CODE) not in sys.path:
    sys.path.insert(0, str(ROOT_CODE))

from core.codex_stage import CodexStageRecognizer
from c0_stage_input_capture_preflight import CAPTURE, ROOT, STUDY, digest
from c0_trace_replay import TRACE, atomic_json


OUT = ROOT / "offline_probe"
MANIFEST = OUT / "manifest-v2.json"
RESULTS = OUT / "results.jsonl"
CONDITIONS = {
    "A_json_low": ("json_schema_v1", "low", "completed_known_startup_warnings_combo_v5"),
    "B_text_low_v6": ("legacy_text", "low", "completed_transport_cycles_v6"),
    "C_json_medium": ("json_schema_v1", "medium", "completed_known_startup_warnings_combo_v5"),
    "D_json_high": ("json_schema_v1", "high", "completed_known_startup_warnings_combo_v5"),
}
MAX_SELECTED = 24
MAX_NEW_CALLS = 446  # Four synthetic sentinel calls already consumed the 450-call plan.


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_trace() -> list[dict]:
    return [json.loads(line) for line in TRACE.read_text().splitlines() if line.strip()]


def select_indices(rows: list[dict]) -> list[int]:
    if len(rows) != 127:
        raise RuntimeError("Expected 127 exact historical C0 queries")
    chosen: list[int] = []

    def add(index: int) -> None:
        same_task = sum(rows[item]["task_id"] == rows[index]["task_id"] for item in chosen)
        if index not in chosen and len(chosen) < MAX_SELECTED and same_task < 3:
            chosen.append(index)

    # Preserve the earliest known on/off divergence, successful tasks, all
    # task identities, parser fallback cases and all trigger types.
    for index, row in enumerate(rows):
        if row["task_id"] == 0 and row["global_step"] == 32:
            add(index)
    for task_id in (3, 8, 9):
        candidates = [i for i, row in enumerate(rows) if row["task_id"] == task_id]
        for index in (candidates[:1] + candidates[-1:]):
            add(index)
    for task_id in range(10):
        candidates = [i for i, row in enumerate(rows) if row["task_id"] == task_id]
        if candidates:
            add(candidates[0])
            add(candidates[len(candidates) // 2])
    for reason in sorted({row["trigger_reason"] for row in rows}):
        candidates = [i for i, row in enumerate(rows) if row["trigger_reason"] == reason]
        if candidates:
            add(candidates[len(candidates) // 2])
    for index, row in enumerate(rows):
        if row["query_status"] == "error":
            add(index)
            if sum(rows[i]["query_status"] == "error" for i in chosen) >= 4:
                break
    # Deterministic spread over any remaining slots.
    remaining = sorted((i for i in range(len(rows)) if i not in chosen),
                       key=lambda i: hashlib.sha256(f"c0-offline-v1:{i}".encode()).hexdigest())
    for index in remaining:
        add(index)
    return sorted(chosen)


def validate_capture() -> list[dict]:
    audit_path = ROOT / "outputs/capture_replay/capture-audit.json"
    if not audit_path.is_file() or json.loads(audit_path.read_text()).get("valid") is not True:
        raise RuntimeError("Exact C0 input capture has not passed full replay audit")
    rows = load_trace()
    for index in range(len(rows)):
        folder = CAPTURE / f"request_{index:04d}"
        metadata = json.loads((folder / "metadata.json").read_text())
        if metadata["query_index"] != index or metadata["historical_raw_response"] != rows[index]["raw_response"]:
            raise RuntimeError(f"Capture request {index} differs from historical reply")
        if digest(folder / "codex_prompt.txt") != metadata["codex_prompt_sha256"]:
            raise RuntimeError(f"Capture prompt {index} changed")
        if [digest(folder / f"image_{i:02d}.png") for i in (1, 2)] != metadata["image_png_sha256"]:
            raise RuntimeError(f"Capture PNG {index} changed")
    return rows


def prepare() -> dict:
    rows = validate_capture()
    selected = select_indices(rows)
    data = {
        "schema": "c0-codex-stage-offline-probe-v2",
        "created_utc": utc(),
        "capture_audit_sha256": digest(ROOT / "outputs/capture_replay/capture-audit.json"),
        "trace_sha256": digest(TRACE),
        "adapter_sha256": digest(STUDY / "core/codex_stage.py"),
        "policy_sha256": digest(STUDY / "core/codex_stage_policy.py"),
        "selected_indices": selected,
        "conditions": {key: list(value) for key, value in CONDITIONS.items()},
        "retired_pilot": "B_text_low/strict_v1: 11 preserved calls, including a complete reply rejected after known reconnect notices",
        "repeats": 3, "maximum_new_calls": MAX_NEW_CALLS,
        "minimum_success_task_coverage": [3, 8, 9],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    if MANIFEST.exists():
        frozen = json.loads(MANIFEST.read_text())
        comparable = {key: value for key, value in data.items() if key != "created_utc"}
        if {key: value for key, value in frozen.items() if key != "created_utc"} != comparable:
            raise RuntimeError("Offline probe manifest differs from frozen version")
        return frozen
    atomic_json(MANIFEST, data)
    return data


def content_for(index: int) -> list[dict]:
    folder = CAPTURE / f"request_{index:04d}"
    parts = json.loads((folder / "parts.json").read_text())
    content = []
    for part in parts:
        if part["type"] == "text":
            content.append({"type": "text", "text": part["text"]})
        else:
            data = (folder / part["file"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != part["sha256"]:
                raise RuntimeError(f"Input PNG changed for request {index}")
            content.append({"type": "image_url", "image_url": {
                "url": "data:image/png;base64," + base64.b64encode(data).decode()}})
    return content


def result_row(index: int, condition: str, repeat: int, recognizer: CodexStageRecognizer,
               historical: dict, content: list[dict] | None = None) -> dict:
    error = None
    normalized = None
    request_content = content if content is not None else content_for(index)
    prompt_text = "\n\n".join(part["text"] for part in request_content if part["type"] == "text")
    try:
        normalized = recognizer._request_stage_response(request_content)
    except Exception as exc:
        error = str(exc) if str(exc).startswith("codex_") else type(exc).__name__
    stage = guidance = None
    if normalized is not None:
        stage_match = re.search(r"stage\s+(\d+)", normalized.lower())
        guidance_match = re.search(r"guidance:\s*(yes|no)", normalized.lower())
        if stage_match and guidance_match:
            stage = min(int(stage_match.group(1)), 2)
            guidance = guidance_match.group(1) == "yes"
        else:
            stage, guidance, error = 1, True, "legacy_parse_fallback"
    return {
        "schema": "c0-stage-offline-call-v1", "utc": utc(), "request_index": index,
        "condition": condition, "repeat": repeat,
        "task_id": historical["task_id"], "global_step": historical["global_step"],
        "trigger_reason": historical["trigger_reason"],
        "old_stage": historical["stage_after"],
        "old_guidance": historical["guidance_after"],
        "old_query_status": historical["query_status"],
        "input_prompt_sha256": hashlib.sha256(prompt_text.encode()).hexdigest(),
        "input_image_sha256": [digest(CAPTURE / f"request_{index:04d}/image_{i:02d}.png") for i in (1, 2)],
        "model": recognizer.model, "reasoning_effort": recognizer.reasoning_effort,
        "format": recognizer.output_format,
        "public_config_sha256": recognizer.transport_metadata["public_config_sha256"],
        "raw_response": recognizer._call_raw_response,
        "normalized_response": normalized, "stage": stage, "guidance": guidance,
        "error": error, "transport": recognizer._call_transport,
    }


def run() -> None:
    frozen = prepare()
    historical = load_trace()
    completed = [json.loads(line) for line in RESULTS.read_text().splitlines() if line.strip()] if RESULTS.exists() else []
    if len(completed) > MAX_NEW_CALLS:
        raise RuntimeError("Offline Codex call cap exceeded")
    done = {(row["request_index"], row["condition"], row["repeat"])
            for row in completed if row["error"] is None}
    recognizers = {}
    for name, (output_format, effort, event_policy) in CONDITIONS.items():
        recognizers[name] = CodexStageRecognizer({
            "backend": "codex_cli", "model": "gpt-6-astra",
            "reasoning_effort": effort, "output_format": output_format,
            "event_policy": event_policy, "timeout_seconds": 180,
        })
    with RESULTS.open("a") as stream:
        consecutive_transport_failures = 0
        for condition in CONDITIONS:
            for index in frozen["selected_indices"]:
                for repeat in range(frozen["repeats"]):
                    key = (index, condition, repeat)
                    if key in done:
                        continue
                    if len(completed) >= MAX_NEW_CALLS:
                        raise RuntimeError("Offline Codex call cap reached")
                    row = result_row(index, condition, repeat, recognizers[condition], historical[index])
                    stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                    stream.flush()
                    done.add(key)
                    completed.append(row)
                    print(f"{len(completed)} {condition} request={index} repeat={repeat} "
                          f"stage={row['stage']} guidance={row['guidance']} error={row['error']}", flush=True)
                    transport = row["transport"]
                    if row["error"] and (transport.get("process_returncode") != 0 or
                                         transport.get("completed_turns") != 1):
                        consecutive_transport_failures += 1
                        if consecutive_transport_failures >= 5:
                            raise RuntimeError("Codex transport failed five consecutive calls; resume later")
                        delay = min(120, 15 * 2 ** consecutive_transport_failures)
                        print(f"Transport cooldown {delay}s after failed call", flush=True)
                        time.sleep(delay)
                    else:
                        consecutive_transport_failures = 0


def summary() -> dict:
    frozen = prepare()
    rows = [json.loads(line) for line in RESULTS.read_text().splitlines() if line.strip()] if RESULTS.exists() else []
    effective = {}
    for row in rows:
        key = (row["request_index"], row["condition"], row["repeat"])
        if key not in effective or (effective[key]["error"] is not None and row["error"] is None):
            effective[key] = row
    conditions = {}
    for name in CONDITIONS:
        subset = [row for row in effective.values() if row["condition"] == name]
        valid = [row for row in subset if row["error"] is None]
        by_input: dict[int, list[dict]] = {}
        for row in valid:
            by_input.setdefault(row["request_index"], []).append(row)
        successful_task_rows = [row for row in valid if row["task_id"] in (3, 8, 9)]
        parseable_old_rows = [row for row in valid if row["old_query_status"] == "ok"]
        per_task = {}
        for task_id in range(10):
            task_rows = [row for row in valid if row["task_id"] == task_id]
            per_task[str(task_id)] = {
                "valid_calls": len(task_rows),
                "matches_old": sum(row["stage"] == row["old_stage"] and
                                   row["guidance"] == row["old_guidance"] for row in task_rows),
            }
        conditions[name] = {
            "calls": len(subset), "valid_calls": len(valid),
            "errors": Counter(row["error"] for row in subset if row["error"]),
            "decision_counts": Counter(f"{row['stage']}/{row['guidance']}" for row in valid),
            "matches_old": sum(row["stage"] == row["old_stage"] and row["guidance"] == row["old_guidance"] for row in valid),
            "matches_old_success_tasks": sum(row["stage"] == row["old_stage"] and
                                             row["guidance"] == row["old_guidance"]
                                             for row in successful_task_rows),
            "success_task_valid_calls": len(successful_task_rows),
            "matches_old_parseable_only": sum(row["stage"] == row["old_stage"] and
                                               row["guidance"] == row["old_guidance"]
                                               for row in parseable_old_rows),
            "parseable_old_valid_calls": len(parseable_old_rows),
            "per_task": per_task,
            "unstable_inputs": sorted(index for index, items in by_input.items()
                                      if len(items) >= 2 and len({(item["stage"], item["guidance"]) for item in items}) > 1),
        }
    return {"schema": "c0-stage-offline-summary-v1", "utc": utc(),
            "selected_input_count": len(frozen["selected_indices"]),
            "calls": len(rows), "effective_input_trials": len(effective),
            "conditions": conditions}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "run", "summary"))
    args = parser.parse_args()
    if args.action == "prepare":
        print(json.dumps(prepare(), indent=2))
    elif args.action == "run":
        run()
        atomic_json(OUT / "summary.json", summary())
    else:
        print(json.dumps(summary(), indent=2, default=dict))


if __name__ == "__main__":
    main()
