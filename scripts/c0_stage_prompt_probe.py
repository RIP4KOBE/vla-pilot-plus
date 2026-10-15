#!/usr/bin/env python3
"""Optional single-concept Codex Stage prompt check on captured C0 inputs."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import time

ROOT_CODE = Path(__file__).resolve().parents[1]
if str(ROOT_CODE) not in sys.path:
    sys.path.insert(0, str(ROOT_CODE))

from core.codex_stage import CodexStageRecognizer
from c0_stage_input_capture_preflight import ROOT, STUDY, digest
from c0_stage_offline_diagnostic import content_for, load_trace, prepare as base_prepare, result_row
from c0_trace_replay import atomic_json, utc


OUT = ROOT / "offline_prompt_probe"
MANIFEST = OUT / "manifest.json"
RESULTS = OUT / "results.jsonl"
EXTENSION = OUT / "extension.jsonl"
NAME = "E_guidance_persistence_json_low"
OLD_TEMPLATE = STUDY / "vlm_query/stage_template.txt"
NEW_TEMPLATE = STUDY / "vlm_query/stage_template_codex_guidance_persistence_v1.txt"
REPLACEMENTS = (
    ('- **"reward rose above X%"**: The robot is getting close to the current stage target → May be ready to advance or disable guidance.',
     '- **"reward rose above X%"**: The local trajectory reward indicates proximity to the current stage target. It does not prove a grasp or task completion; keep stage 1 guidance until grasp is confirmed.'),
    ('  - The gripper is ALREADY CLOSE to the next target.\n', ''),
    ('  - Guidance is needed to direct the robot toward a specific object among multiple options.',
     '  - Guidance is needed to direct the robot toward a specific object among multiple options.\n  - Stage 1 is still trying to grasp the target, even if the gripper looks close or the local reward is high.'),
    ('stage 1\nguidance: no\nevidence: The gripper is very close to the red cube; the NEXT chunk will complete the grasp; no guidance is needed.',
     'stage 1\nguidance: yes\nevidence: The gripper is close to the red cube, but the cube is not visibly grasped; guidance remains on for the NEXT grasp chunk.'),
)


def content_for_e(index: int) -> list[dict]:
    content = content_for(index)
    prompt = content[0]["text"]
    for old, new in REPLACEMENTS:
        if prompt.count(old) != 1:
            raise RuntimeError(f"Prompt change is not one-to-one for request {index}")
        prompt = prompt.replace(old, new, 1)
    content[0] = {"type": "text", "text": prompt}
    return content


def prepare() -> dict:
    base = base_prepare()
    if digest(NEW_TEMPLATE) == digest(OLD_TEMPLATE):
        raise RuntimeError("Prompt variant equals historical Stage template")
    if content_for_e(base["selected_indices"][0])[0]["text"] == content_for(base["selected_indices"][0])[0]["text"]:
        raise RuntimeError("Prompt variant was not applied")
    data = {
        "schema": "c0-codex-stage-prompt-probe-v1", "created_utc": utc(),
        "condition": NAME, "selected_indices": base["selected_indices"], "repeats": 3,
        "base_manifest_sha256": digest(STUDY / "artifacts/c0_online_stage_diagnostic_20260928/offline_probe/manifest-v2.json"),
        "old_template_sha256": digest(OLD_TEMPLATE),
        "new_template_sha256": digest(NEW_TEMPLATE),
        "adapter_sha256": digest(STUDY / "core/codex_stage.py"),
        "policy_sha256": digest(STUDY / "core/codex_stage_policy.py"),
        "model": "gpt-6-astra", "reasoning_effort": "low",
        "output_format": "json_schema_v1",
        "event_policy": "completed_transport_cycles_v6",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    if MANIFEST.exists():
        old = json.loads(MANIFEST.read_text())
        if {k: v for k, v in old.items() if k != "created_utc"} != {k: v for k, v in data.items() if k != "created_utc"}:
            raise RuntimeError("Prompt probe manifest differs from frozen inputs")
        return old
    atomic_json(MANIFEST, data)
    return data


def run() -> None:
    frozen = prepare()
    historical = load_trace()
    rows = [json.loads(line) for line in RESULTS.read_text().splitlines() if line.strip()] if RESULTS.exists() else []
    done = {(row["request_index"], row["repeat"]) for row in rows if row["error"] is None}
    recognizer = CodexStageRecognizer({
        "backend": "codex_cli", "model": "gpt-6-astra",
        "reasoning_effort": "low", "output_format": "json_schema_v1",
        "event_policy": "completed_transport_cycles_v6", "timeout_seconds": 180,
    })
    failures = 0
    with RESULTS.open("a") as stream:
        for index in frozen["selected_indices"]:
            for repeat in range(frozen["repeats"]):
                if (index, repeat) in done:
                    continue
                row = result_row(index, NAME, repeat, recognizer, historical[index],
                                 content=content_for_e(index))
                stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                stream.flush()
                rows.append(row)
                print(f"E call {len(rows)} request={index} repeat={repeat} "
                      f"decision={row['stage']}/{row['guidance']} error={row['error']}", flush=True)
                if row["error"] and row["transport"].get("completed_turns") != 1:
                    failures += 1
                    if failures >= 5:
                        raise RuntimeError("Codex transport failed five consecutive prompt calls")
                    time.sleep(min(120, 15 * 2 ** failures))
                else:
                    failures = 0
    effective = {}
    for row in rows:
        key = (row["request_index"], row["repeat"])
        if key not in effective or (effective[key]["error"] and row["error"] is None):
            effective[key] = row
    valid = [row for row in effective.values() if row["error"] is None]
    report = {
        "schema": "c0-stage-prompt-probe-summary-v1", "utc": utc(),
        "physical_calls": len(rows), "valid_trials": len(valid),
        "matches_old": sum(row["stage"] == row["old_stage"] and
                           row["guidance"] == row["old_guidance"] for row in valid),
        "stage1_guidance_off": sum(row["stage"] == 1 and row["guidance"] is False for row in valid),
        "decision_counts": Counter(f"{row['stage']}/{row['guidance']}" for row in valid),
        "errors": Counter(row["error"] for row in rows if row["error"]),
    }
    atomic_json(OUT / "summary.json", report)
    print(json.dumps(report, indent=2, default=dict), flush=True)


def extend() -> None:
    frozen = prepare()
    screen = OUT / "summary.json"
    if not screen.is_file() or json.loads(screen.read_text()).get("valid_trials") != 72:
        raise RuntimeError("Prompt screen requires 72 valid selected-input trials")
    historical = load_trace()
    rows = [json.loads(line) for line in EXTENSION.read_text().splitlines() if line.strip()] if EXTENSION.exists() else []
    done = {row["request_index"] for row in rows if row["error"] is None}
    recognizer = CodexStageRecognizer({
        "backend": "codex_cli", "model": "gpt-6-astra",
        "reasoning_effort": "low", "output_format": "json_schema_v1",
        "event_policy": "completed_transport_cycles_v6", "timeout_seconds": 180,
    })
    selected = set(frozen["selected_indices"])
    failures = 0
    with EXTENSION.open("a") as stream:
        for index in range(len(historical)):
            if index in selected or index in done:
                continue
            row = result_row(index, NAME, 0, recognizer, historical[index],
                             content=content_for_e(index))
            row["phase"] = "extension"
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            rows.append(row)
            print(f"E extension {len(rows)} request={index} "
                  f"decision={row['stage']}/{row['guidance']} error={row['error']}", flush=True)
            if row["error"] and row["transport"].get("completed_turns") != 1:
                failures += 1
                if failures >= 5:
                    raise RuntimeError("Codex transport failed five consecutive extension calls")
                time.sleep(min(120, 15 * 2 ** failures))
            else:
                failures = 0
    coverage = {"schema": "c0-stage-prompt-extension-coverage-v1", "utc": utc(),
                "condition": NAME, "selected_input_count": len(selected),
                "extension_valid_inputs": len({row["request_index"] for row in rows if row["error"] is None}),
                "extension_target_inputs": len(historical) - len(selected),
                "physical_extension_calls": len(rows)}
    atomic_json(OUT / "extension-coverage.json", coverage)
    print(json.dumps(coverage, indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "run", "extend"))
    args = parser.parse_args()
    if args.action == "prepare":
        print(json.dumps(prepare(), indent=2))
    elif args.action == "run":
        run()
    else:
        extend()


if __name__ == "__main__":
    main()
