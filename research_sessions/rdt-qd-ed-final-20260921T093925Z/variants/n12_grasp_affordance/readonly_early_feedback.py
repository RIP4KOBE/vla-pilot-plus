#!/usr/bin/env python3
"""Summarize already recorded Dev robot feedback; no simulator or candidate replay."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import torch


HERE = Path(__file__).resolve().parent
SESSION = HERE.parents[1]
REPORT = SESSION / "variants/n11_parent_survival/dev-comparison-v1.json"
ARTIFACTS = SESSION / "artifacts/attempts"
OUTPUT = HERE / "early-feedback-readonly-v1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise SystemExit("immutable output already exists")
    comparison = json.loads(REPORT.read_text())
    assert comparison["all_sixteen_valid"]
    rows = {}
    for task in ("3", "6"):
        for profile in ("N7", "N11"):
            attempt = comparison["tasks"][task][profile]["attempt_id"]
            root = ARTIFACTS / attempt / "eds_eval"
            qpath = root / "qualitative/episode_000/chunk_000000/keypoints_3d.json"
            q = json.loads(qpath.read_text())
            assert len(q["keypoints_3d"]) == 1
            target = q["keypoints_3d"][0]
            folder = root / "decision_evidence/episode_000"
            events_path = folder / "events.jsonl"
            ledger = [json.loads(line) for line in events_path.read_text().splitlines()]
            observed = {}
            actions = {}
            digests = {}
            for entry in ledger:
                if not any(e["event"] in {"pre_reset_outcome", "executed_action"}
                           and e.get("global_step", 999999) < 40 for e in entry["events"]):
                    continue
                path = folder / entry["bundle"]
                digest = sha256(path)
                if digest != entry["sha256"]:
                    raise RuntimeError(f"native bundle hash mismatch: {path}")
                digests[path.name] = digest
                bundle = torch.load(path, map_location="cpu", weights_only=True)
                for event in bundle["events"]:
                    step = int(event.get("global_step", -1))
                    if step < 0 or step >= 40:
                        continue
                    if event["event"] == "pre_reset_outcome":
                        o = event["values"]["observation"]
                        eef = [float(v) for v in o["robot0_eef_pos"]]
                        grip = [float(v) for v in o["robot0_gripper_qpos"]]
                        observed[step] = {
                            "eef_xyz": eef,
                            "gripper_qpos": grip,
                            "eef_to_static_initial_keypoint_m": math.dist(eef, target),
                            "success_observation": bool(event["values"]["success"]),
                        }
                    elif event["event"] == "executed_action":
                        action = [float(v) for v in event["values"]["action_numpy"]]
                        assert len(action) == 7
                        actions[step] = action
            common = sorted(set(observed) & set(actions))
            if common != list(range(min(40, max(common) + 1))):
                raise RuntimeError(f"early action/observation gap: {task}/{profile}")
            summary = {
                "attempt_id": attempt,
                "outcome_success": comparison["tasks"][task][profile]["success"],
                "static_initial_keypoint_xyz": target,
                "keypoint_sha256": sha256(qpath),
                "event_index_sha256": sha256(events_path),
                "verified_bundle_sha256": digests,
                "steps": [
                    {"step": i, **observed[i], "gripper_command": actions[i][6]}
                    for i in common
                ],
            }
            rows[f"task{task}_{profile}"] = summary
    output = {
        "schema": "n12-early-feedback-readonly-v1",
        "split": "already_exposed_dev",
        "diagnostic_only": True,
        "comparison_sha256": sha256(REPORT),
        "rows": rows,
        "limitations": [
            "The first-chunk keypoint is held static here and is not actual object pose after movement.",
            "Robot EEF, gripper and action observations do not prove object contact or grasp.",
            "Four exposed Dev paths cannot establish a general decision rule or episode counterfactual.",
        ],
    }
    OUTPUT.write_text(json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({"output": str(OUTPUT), "sha256": sha256(OUTPUT),
                      "steps": {key: len(row["steps"]) for key, row in rows.items()}}, indent=2))


if __name__ == "__main__":
    main()
