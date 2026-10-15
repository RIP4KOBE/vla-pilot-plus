#!/usr/bin/env python3
"""Check one-variable correction of stale C0 Stage target descriptions."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
import time

ROOT_CODE = Path(__file__).resolve().parents[1]
if str(ROOT_CODE) not in sys.path:
    sys.path.insert(0, str(ROOT_CODE))

from core.codex_stage import CodexStageRecognizer
from c0_stage_input_capture_preflight import ROOT, STUDY, digest
from c0_stage_offline_diagnostic import content_for, load_trace, prepare as base_prepare, result_row
from c0_trace_replay import atomic_json, utc


OUT = ROOT / "offline_identity_probe"
MANIFEST = OUT / "manifest.json"
RESULTS = OUT / "results.jsonl"
EXTENSION = OUT / "extension.jsonl"
NAME = "F_correct_stage_target_json_low"
SOURCE_TARGET = "alphabet soup can"


def corrected_stage_descriptions(stage_descriptions: str, instruction: str,
                                 keypoint_id_to_object: dict[int, str]) -> str:
    """Correct only the C0 cached target when task and keypoint zero agree."""
    match = re.fullmatch(r"pick up the ([a-z ]+) and place it in the basket", instruction)
    if not match:
        raise ValueError("Unexpected C0 task instruction")
    target = match.group(1)
    keypoint_zero = keypoint_id_to_object.get(0)
    if keypoint_zero != target.replace(" ", "_") + "_1_main":
        raise ValueError("C0 task and keypoint zero disagree")
    if stage_descriptions.count(SOURCE_TARGET) != 2:
        raise ValueError("Expected two original C0 target mentions")
    if target == "alphabet soup":
        return stage_descriptions
    return stage_descriptions.replace(SOURCE_TARGET, target)


def content_for_f(index: int) -> list[dict]:
    content = content_for(index)
    prompt = content[0]["text"]
    task = re.search(r"\*\*Task Instruction:\*\* (.+)\n", prompt)
    keypoint = re.search(r"(?m)^  Keypoint 0: (\S+)$", prompt)
    if task is None or keypoint is None:
        raise ValueError("Captured C0 prompt lacks task/keypoint zero")
    before = re.search(r"(?s)(?<=\*\*Stage Descriptions \(stages with guidance functions\):\*\*\n)(.*?)(?=\n\n\*\*Keypoint ID)", prompt)
    if before is None:
        raise ValueError("Captured C0 Stage description block absent")
    description = before.group(1)
    fixed = corrected_stage_descriptions(description, task.group(1), {0: keypoint.group(1)})
    if prompt.count(description) != 2:
        raise ValueError("Expected duplicated original C0 Stage description block")
    prompt = prompt.replace(description, fixed)
    content[0] = {"type": "text", "text": prompt}
    return content


def prepare() -> dict:
    base = base_prepare()
    for index in range(127):
        content_for_f(index)
    data = {
        "schema": "c0-codex-stage-identity-probe-v1", "created_utc": utc(),
        "condition": NAME, "selected_indices": base["selected_indices"], "repeats": 3,
        "base_manifest_sha256": digest(STUDY / "artifacts/c0_online_stage_diagnostic_20260928/offline_probe/manifest-v2.json"),
        "adapter_sha256": digest(STUDY / "core/codex_stage.py"),
        "policy_sha256": digest(STUDY / "core/codex_stage_policy.py"),
        "model": "gpt-6-astra", "reasoning_effort": "low",
        "output_format": "json_schema_v1", "event_policy": "completed_transport_cycles_v6",
        "transform_sha256": digest(Path(__file__)),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    if MANIFEST.exists():
        old = json.loads(MANIFEST.read_text())
        if {k: v for k, v in old.items() if k != "created_utc"} != {k: v for k, v in data.items() if k != "created_utc"}:
            raise RuntimeError("Identity probe manifest differs from frozen inputs")
        return old
    atomic_json(MANIFEST, data)
    return data


def recognizer() -> CodexStageRecognizer:
    return CodexStageRecognizer({"backend": "codex_cli", "model": "gpt-6-astra",
        "reasoning_effort": "low", "output_format": "json_schema_v1",
        "event_policy": "completed_transport_cycles_v6", "timeout_seconds": 180})


def invoke(indices: list[int], repeats: int, path: Path) -> None:
    historical = load_trace()
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []
    done = {(row["request_index"], row["repeat"]) for row in rows if row["error"] is None}
    client = recognizer()
    failures = 0
    with path.open("a") as stream:
        for index in indices:
            for repeat in range(repeats):
                if (index, repeat) in done:
                    continue
                row = result_row(index, NAME, repeat, client, historical[index],
                                 content=content_for_f(index))
                stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                stream.flush()
                rows.append(row)
                print(f"F {path.name} call={len(rows)} request={index} repeat={repeat} "
                      f"decision={row['stage']}/{row['guidance']} error={row['error']}", flush=True)
                if row["error"] and row["transport"].get("completed_turns") != 1:
                    failures += 1
                    if failures >= 5:
                        raise RuntimeError("Codex transport failed five consecutive identity calls")
                    time.sleep(min(120, 15 * 2 ** failures))
                else:
                    failures = 0


def summarize(path: Path, indices: list[int]) -> dict:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []
    effective = {}
    for row in rows:
        key = (row["request_index"], row["repeat"])
        if key not in effective or (effective[key]["error"] and row["error"] is None):
            effective[key] = row
    valid = [row for row in effective.values() if row["error"] is None]
    return {"schema": "c0-stage-identity-summary-v1", "utc": utc(),
        "condition": NAME, "physical_calls": len(rows), "valid_trials": len(valid),
        "target_trials": len(indices) * (3 if path == RESULTS else 1),
        "matches_old": sum(row["stage"] == row["old_stage"] and
                           row["guidance"] == row["old_guidance"] for row in valid),
        "matches_old_success_tasks": sum(row["stage"] == row["old_stage"] and
                           row["guidance"] == row["old_guidance"] for row in valid
                           if row["task_id"] in (3, 8, 9)),
        "success_task_valid_trials": sum(row["task_id"] in (3, 8, 9) for row in valid),
        "stage1_guidance_off": sum(row["stage"] == 1 and row["guidance"] is False for row in valid),
        "decision_counts": Counter(f"{row['stage']}/{row['guidance']}" for row in valid),
        "errors": Counter(row["error"] for row in rows if row["error"])}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "run", "extend"))
    action = parser.parse_args().action
    frozen = prepare()
    if action == "prepare":
        print(json.dumps(frozen, indent=2))
    elif action == "run":
        invoke(frozen["selected_indices"], 3, RESULTS)
        report = summarize(RESULTS, frozen["selected_indices"])
        atomic_json(OUT / "summary.json", report)
        print(json.dumps(report, indent=2, default=dict))
    else:
        screen = json.loads((OUT / "summary.json").read_text())
        if screen["valid_trials"] != 72:
            raise RuntimeError("Identity screen requires 72 valid trials")
        remaining = sorted(set(range(127)) - set(frozen["selected_indices"]))
        invoke(remaining, 1, EXTENSION)
        report = summarize(EXTENSION, remaining)
        atomic_json(OUT / "extension-coverage.json", report)
        print(json.dumps(report, indent=2, default=dict))


if __name__ == "__main__":
    main()
