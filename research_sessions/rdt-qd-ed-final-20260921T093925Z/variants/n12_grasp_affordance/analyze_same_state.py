#!/usr/bin/env python3
"""Predefined descriptive analysis of the bounded task3 contrast, if approved."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
RELEASE = HERE / "same-state-plan.approved.v1.json"
OUTPUT = HERE / "same-state-analysis-v1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def length(vector):
    return math.sqrt(sum(float(value) ** 2 for value in vector))


def delta(left, right):
    return [float(a) - float(b) for a, b in zip(left, right)]


def contact_summary(trace):
    pairs = []
    for step, state in enumerate(trace):
        for contact in state["contacts"]:
            left, right = contact["geom1"], contact["geom2"]
            if not isinstance(left, str) or not isinstance(right, str):
                continue
            target_left = "bbq_sauce" in left.lower()
            target_right = "bbq_sauce" in right.lower()
            finger_left = any(word in left.lower() for word in ("finger", "gripper"))
            finger_right = any(word in right.lower() for word in ("finger", "gripper"))
            if (target_left and finger_right) or (target_right and finger_left):
                pairs.append({"branch_step": step, "geom1": left, "geom2": right,
                              "contact_distance": contact["distance"]})
    return pairs


def summarize(trace, target_name):
    if target_name not in trace[0]["object_pose"] or target_name not in trace[-1]["object_pose"]:
        raise ValueError("expected task3 target object absent from simulator snapshots")
    start = trace[0]["object_pose"][target_name]["xyz"]
    end = trace[-1]["object_pose"][target_name]["xyz"]
    contact = contact_summary(trace)
    distances = []
    for state in trace:
        target = state["object_pose"][target_name]["xyz"]
        distances.append(length(delta(state["eef_xyz"], target)))
    return {
        "executed_actions": len(trace) - 1,
        "short_prefix_success_predicate": any(state["success"] for state in trace),
        "target_displacement_m": length(delta(end, start)),
        "target_height_change_m": float(end[2]) - float(start[2]),
        "eef_target_min_distance_m": min(distances),
        "eef_target_final_distance_m": distances[-1],
        "target_finger_contact_pairs": contact,
        "target_finger_contact_detected": bool(contact),
        "final_gripper_qpos": trace[-1]["gripper_qpos"],
    }


def resolve_target_body_key(trace, expected_name):
    """LIBERO's semantic `_main` geom names use the unsuffixed object body key."""
    keys = set(trace[0]["object_pose"])
    if expected_name in keys:
        target_name = expected_name
    elif expected_name.endswith("_main") and expected_name[:-5] in keys:
        target_name = expected_name[:-5]
    else:
        raise ValueError("expected task3 target object absent from simulator snapshots")
    if any(target_name not in state["object_pose"] for state in trace):
        raise ValueError("target body key missing from a simulator snapshot")
    return target_name


def main():
    if len(sys.argv) != 1:
        raise SystemExit("no parameters: analysis is fixed by the released plan")
    if OUTPUT.exists():
        raise SystemExit("immutable analysis already exists")
    plan = json.loads(RELEASE.read_text())
    result_path = Path(plan["output_dir"]) / "result.json"
    result = json.loads(result_path.read_text())
    if result["status"] != "COMPLETED_CONTRAST" or result["official_task_success_rate"] is not None:
        raise RuntimeError("valid same-state contrast unavailable")
    branches = {row["name"]: row["trace"] for row in result["branches"]}
    if set(branches) != {"selected_dry_a", "selected_dry_b", "selected", "alternative"}:
        raise RuntimeError("branch set changed")
    if branches["selected_dry_a"] != branches["selected_dry_b"] or branches["selected_dry_a"] != branches["selected"]:
        raise RuntimeError("selected parity failed")
    if branches["selected"][0] != branches["alternative"][0]:
        raise RuntimeError("branches did not start from the same complete state")
    selected_key = resolve_target_body_key(branches["selected"], plan["expected_target_object"])
    alternate_key = resolve_target_body_key(branches["alternative"], plan["expected_target_object"])
    if selected_key != alternate_key:
        raise RuntimeError("target object body keys differ between branches")
    selected = summarize(branches["selected"], selected_key)
    alternate = summarize(branches["alternative"], alternate_key)
    conclusion = {
        "schema": "n12-task3-same-state-analysis-v1",
        "diagnostic_only": True, "official_task_success_rate": None,
        "plan_sha256": sha256(RELEASE), "result_sha256": sha256(result_path),
        "task_id": 3, "global_step": 16,
        "expected_target_geom_name": plan["expected_target_object"],
        "resolved_target_body_key": selected_key,
        "selected": selected, "alternative": alternate,
        "alternative_minus_selected_target_displacement_m": alternate["target_displacement_m"] - selected["target_displacement_m"],
        "alternative_minus_selected_target_height_change_m": alternate["target_height_change_m"] - selected["target_height_change_m"],
        "limits": [
            "Contact classification requires named target and finger/gripper geoms; an empty list may mean absent or unrecognized naming.",
            "Eight-step physical contrast on one exposed Dev state is not an official episode success-rate estimate.",
            "No unexecuted full-episode counterfactual, validation or formal result is inferred.",
        ],
    }
    OUTPUT.write_text(json.dumps(conclusion, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({"output": str(OUTPUT), "sha256": sha256(OUTPUT),
                      "selected": selected, "alternative": alternate}, indent=2))


if __name__ == "__main__":
    main()
