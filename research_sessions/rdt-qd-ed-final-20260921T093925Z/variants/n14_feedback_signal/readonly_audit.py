"""Audit policy-visible target tracking in the matched N11 Dev cohort.

This reads only completed original Dev episodes and verifies every referenced
native bundle hash before extracting decision contexts.
"""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[2]
ATTEMPTS = ROOT / "artifacts/attempts"
OUT = Path(__file__).with_name("readonly_signal_audit.json")


def read_contexts(episode):
    contexts = {}
    for line in (episode / "events.jsonl").open():
        ref = json.loads(line)
        if not any(x["event"] == "decision_context" for x in ref["events"]):
            continue
        p = episode / ref["bundle"]
        if hashlib.sha256(p.read_bytes()).hexdigest() != ref["sha256"]:
            raise ValueError(f"hash mismatch: {p}")
        events = torch.load(p, map_location="cpu", weights_only=True)["events"]
        context = [x for x in events if x["event"] == "decision_context"]
        if len(context) != 1:
            raise ValueError("decision context cardinality")
        x = context[0]
        v = x["values"]
        origins = [e for e in events if e["event"] == "projection_origin"]
        decode = [e for e in events if e["event"] == "policy_action_decode"]
        final = [e for e in events if e["event"] == "final_selection"]
        selected_min_reach = None
        if final:
            fv = final[0]["values"]
            reach = fv["terminal_population"]["grasp_selection"]["projected_distances_m"]
            selected_min_reach = float(reach[int(fv["selected_index"])].min())
        snap = v.get("keypoint_tracking_snapshot")
        valid = (isinstance(snap, dict) and isinstance(snap.get("instance_id"), int)
                 and isinstance(snap.get("generation"), int)
                 and snap.get("targets", {}).get("0") == {"valid": True, "status": "tracked"})
        pos = v.get("keypoints")
        contexts[x["global_step"]] = {
            "stage": v["stage"], "guided": bool(v["use_guidance"]),
            "tracked": valid,
            "instance_id": snap.get("instance_id") if valid else None,
            "generation": snap.get("generation") if valid else None,
            "target": pos[0].tolist() if pos is not None else None,
            "eef_start": origins[0]["values"]["source_eef_position"].tolist() if origins else None,
            "gripper_commands": decode[0]["values"]["action_chunk"].reshape(-1, 7)[:, 6].tolist() if decode else None,
            "selected_projected_min_reach_m": selected_min_reach,
        }
    return contexts


def main():
    report = {"schema": "n14-policy-visible-feedback-readonly-v1", "paths": []}
    for task in (0, 3, 6, 9):
        for arm in ("n7", "n11"):
            episodes = list(ATTEMPTS.glob(f"*n11_dev_t{task:02d}_{arm}_*/eds_eval/decision_evidence/episode_000"))
            if len(episodes) != 1:
                raise ValueError(f"expected one matched path {task}/{arm}: {len(episodes)}")
            ctx = read_contexts(episodes[0])
            count = Counter()
            shifts = []
            for step, v in sorted(ctx.items()):
                count["decisions"] += 1
                if v["tracked"]:
                    count["tracked_decisions"] += 1
                if not v["guided"]:
                    continue
                count["guided"] += 1
                n = ctx.get(step + 8)
                if n is None:
                    continue
                stable = (v["tracked"] and n["tracked"]
                          and v["instance_id"] == n["instance_id"]
                          and v["generation"] == n["generation"])
                if not stable:
                    count["unstable_adjacent"] += 1
                    continue
                count["stable_adjacent"] += 1
                distance = math.dist(v["target"], n["target"])
                if distance >= .01:
                    target_motion = [b - a for a, b in zip(v["target"], n["target"])]
                    eef_motion = ([b - a for a, b in zip(v["eef_start"], n["eef_start"])]
                                  if v["eef_start"] is not None and n["eef_start"] is not None else None)
                    aligned_xy = (sum(a * b for a, b in zip(target_motion[:2], eef_motion[:2]))
                                  if eef_motion is not None else None)
                    count["shift_ge_1cm"] += 1
                    same_stage_next_guided = n["guided"] and n["stage"] == v["stage"]
                    if same_stage_next_guided:
                        count["same_stage_next_guided_shift"] += 1
                    shifts.append({"step": step, "target_shift_m": distance,
                                   "target_motion_xyz": target_motion,
                                   "eef_motion_xyz": eef_motion,
                                   "eef_target_xy_motion_dot": aligned_xy,
                                   "gripper_commands": v["gripper_commands"],
                                   "next_guided_same_stage": same_stage_next_guided})
            report["paths"].append({"task": task, "arm": arm, "episode": str(episodes[0]),
                                    "counts": dict(count), "shifts": shifts})
    report["signal_ready_gate"] = {
        "distinct_tasks_with_valid_shift": len({p["task"] for p in report["paths"] if p["counts"].get("shift_ge_1cm", 0) > 0}),
        "immediate_same_stage_guided_opportunities": sum(p["counts"].get("same_stage_next_guided_shift", 0) for p in report["paths"]),
    }
    gate = report["signal_ready_gate"]
    gate["status"] = "SIGNAL_READY" if gate["distinct_tasks_with_valid_shift"] >= 2 and gate["immediate_same_stage_guided_opportunities"] >= 2 else "SIGNAL_NOT_READY"
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    for p in report["paths"]:
        print(p["task"], p["arm"], p["counts"])
    print(gate)


if __name__ == "__main__":
    main()
