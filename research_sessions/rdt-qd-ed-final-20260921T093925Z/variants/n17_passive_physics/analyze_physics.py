"""Analyze two passive full-episode Dev witnesses; never infer counterfactual SR."""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
SESSION = HERE.parents[1]
OUT = HERE / "physics-analysis-v1.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def longest_run(flags):
    best = cur = 0
    for flag in flags:
        cur = cur + 1 if flag else 0
        best = max(best, cur)
    return best


def analyze(attempt_id):
    path = SESSION / "artifacts/attempts" / attempt_id / "eds_eval"
    trace = path / "passive_physics_episode_000.jsonl"
    rows_all = [json.loads(line) for line in trace.open()]
    corrected = path / "passive-physics-audit-corrected-v2.json"
    if corrected.exists():
        audit = json.loads(corrected.read_text())
        digest = audit["trace_sha256"]
        expected_steps = audit["total_action_rows"]
        physics_steps = audit["preterminal_physics_rows"]
        if audit["post_reset_row"] != expected_steps - 1 or physics_steps != expected_steps - 1:
            raise ValueError("terminal reset correction is not one final row")
    else:
        audit = json.loads((path / "passive-physics-audit.json").read_text())
        digest = audit["sha256"]
        expected_steps = audit["steps"]
        physics_steps = expected_steps
    if sha(trace) != digest:
        raise ValueError("passive trace hash differs from audit")
    if len(rows_all) != expected_steps:
        raise ValueError("passive trace row count differs")
    rows = rows_all[:physics_steps]
    attempt = json.loads((path.parent / "attempt-result.json").read_text())
    if attempt["event"] != "valid" or attempt["outcome_valid"] is not True:
        raise ValueError("episode scientific outcome not accepted")
    target_names = {r["target_object_name"] for r in rows if r["target_tracker_valid"]}
    if len(target_names) != 1:
        raise ValueError(f"target identity unstable: {target_names}")
    target_name = target_names.pop()
    pose_key = target_name.removesuffix("_main")
    if any(pose_key not in r["object_bodies"] for r in rows):
        raise ValueError("target body pose missing")
    start = rows[0]["object_bodies"][pose_key]["xyz"]
    target_xyz = [r["object_bodies"][pose_key]["xyz"] for r in rows]
    target_contact = []
    finger_contact = []
    bilateral = []
    basket_contact = []
    contact_pair_counts = Counter()
    for row in rows:
        own = []
        for contact in row["contacts_at_action_boundary"]:
            pair = contact["body_names"]
            if target_name not in pair:
                continue
            other = pair[1] if pair[0] == target_name else pair[0]
            own.append(str(other))
            contact_pair_counts[str(other)] += 1
        target_contact.append(bool(own))
        finger_contact.append(any(other.startswith("gripper0_") for other in own))
        bilateral.append(any("leftfinger" in other for other in own)
                         and any("rightfinger" in other for other in own))
        basket_contact.append(any("basket" in other for other in own))
    lift = [xyz[2] - start[2] >= .03 for xyz in target_xyz]
    basket_keys = [key for key in rows[0]["object_bodies"] if "basket" in key]
    basket_distances = None
    if len(basket_keys) == 1:
        basket_distances = [math.dist(xyz[:2], row["object_bodies"][basket_keys[0]]["xyz"][:2])
                            for xyz, row in zip(target_xyz, rows)]
    return {
        "attempt_id": attempt_id, "trace_sha256": sha(trace), "action_steps": len(rows_all),
        "usable_physics_steps": len(rows),
        "target_name": target_name, "target_pose_key": pose_key,
        "target_tracker_valid_steps": sum(r["target_tracker_valid"] for r in rows),
        "contact_body_counts": dict(contact_pair_counts),
        "target_contact_steps": sum(target_contact),
        "gripper_contact_steps": sum(finger_contact),
        "first_gripper_contact_step": next((i for i, value in enumerate(finger_contact) if value), None),
        "max_consecutive_gripper_contact_steps": longest_run(finger_contact),
        "bilateral_finger_contact_steps": sum(bilateral),
        "basket_contact_steps": sum(basket_contact),
        "max_target_height_above_initial_m": max(xyz[2] - start[2] for xyz in target_xyz),
        "sustained_lift_ge_3cm_steps": longest_run(lift),
        "target_final_displacement_m": math.dist(start, target_xyz[-1]),
        "target_final_z_change_m": target_xyz[-1][2] - start[2],
        "target_basket_min_xy_m": min(basket_distances) if basket_distances else None,
        "target_basket_final_xy_m": basket_distances[-1] if basket_distances else None,
        "first_gripper_contact_stage": (rows[next(i for i, value in enumerate(finger_contact) if value)]["stage"]
                                        if any(finger_contact) else None),
        "first_gripper_contact_guided": (rows[next(i for i, value in enumerate(finger_contact) if value)]["guided"]
                                         if any(finger_contact) else None),
        "success_observed": bool(attempt["success"]),
        "terminal_physics_was_post_reset": physics_steps != expected_steps,
        "scope_limit": "MuJoCo contacts sampled at action boundaries; transient contacts may be missed",
    }


def main():
    status = json.loads((HERE / "supervisor-status-corrected-v2.json").read_text())
    if status["status"] != "completed_two_audited_with_terminal_reset_correction":
        raise ValueError("two accepted N17 paths required")
    result = {"schema": "n17-passive-physics-analysis-v1",
              "plan_sha256": sha(HERE / "plan.frozen.v2.json"),
              "paths": [analyze(item["attempt_id"]) for item in status["completed"]]}
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    for path in result["paths"]:
        print(path["attempt_id"], {key: path[key] for key in (
            "action_steps", "usable_physics_steps", "gripper_contact_steps", "bilateral_finger_contact_steps",
            "sustained_lift_ge_3cm_steps", "basket_contact_steps", "success_observed")})


if __name__ == "__main__":
    main()
