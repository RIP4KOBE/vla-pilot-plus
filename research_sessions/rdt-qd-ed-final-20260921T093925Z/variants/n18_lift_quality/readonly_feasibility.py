"""SHA-verified Dev-only availability screen for projected close-then-lift."""
import hashlib
import json
from pathlib import Path
import sys

import torch


HERE = Path(__file__).resolve().parent
SESSION = HERE.parents[1]
sys.path.insert(0, str(SESSION / "study_worktree"))
from core.rdt_libero_action_converter import rdt_action_to_libero_raw


def inspect_episode(path):
    decision_rows = []
    for line in (path / "events.jsonl").open():
        ref = json.loads(line)
        if not any(e["event"] == "qd_descriptor_assignment" for e in ref["events"]):
            continue
        file = path / ref["bundle"]
        if hashlib.sha256(file.read_bytes()).hexdigest() != ref["sha256"]:
            raise ValueError(f"bundle hash mismatch {file}")
        events = torch.load(file, map_location="cpu", weights_only=True)["events"]
        context = next(e for e in events if e["event"] == "decision_context")
        by_seq = {e["sequence"]: e for e in events}
        assignments = [e for e in events if e["event"] == "qd_descriptor_assignment"]
        if len(assignments) != 11:
            raise ValueError("QD canonical round count differs")
        rows = []
        for assignment in assignments:
            v = assignment["values"]
            score = by_seq[v["scoring_batch_id"]]["values"]
            canonical = next(e for e in events if e["event"] == "canonical_candidate_batch"
                             and e["values"]["iter_idx"] == v["iter_idx"])
            if not torch.equal(score["samples"], canonical["values"]["candidates"]):
                raise ValueError("scoring candidates differ from canonical batch")
            samples = score["samples"]
            projected = score["projected_xyz"].float()
            target = score["keypoints"].reshape(-1)[:3].float()
            gripper = rdt_action_to_libero_raw(samples[:, :8, :])[:, :, 6]
            distance = torch.linalg.vector_norm(projected[:, 1:, :] - target.view(1, 1, 3), dim=2)
            near_close = (distance <= .04) & (gripper > 0)
            time_index = near_close.int().argmax(dim=1)
            has_close = near_close.any(dim=1)
            contact_height = projected[torch.arange(16), time_index + 1, 2]
            lift = (projected[:, 8, 2] - contact_height).clamp(min=0, max=.05)
            bonus = torch.where(has_close, lift.square(), torch.zeros_like(lift))
            rows.append({"iter_idx": v["iter_idx"],
                         "near_close_candidates": int(has_close.sum()),
                         "positive_lift_candidates": int((bonus > 0).sum()),
                         "lift_ge_3cm_candidates": int((has_close & (lift >= .03)).sum()),
                         "max_bonus_m2": float(bonus.max())})
        decision_rows.append({"step": context["global_step"], "stage": context["values"]["stage"],
                              "rounds": rows,
                              "any_positive_lift": any(r["positive_lift_candidates"] for r in rows),
                              "any_lift_ge_3cm": any(r["lift_ge_3cm_candidates"] for r in rows)})
    return decision_rows


def main():
    paths = []
    for task, pattern in (
        (0, "*n17_physics_t00_n7_*/eds_eval/decision_evidence/episode_000"),
        (3, "*n11_dev_t03_n7_*/eds_eval/decision_evidence/episode_000"),
        (6, "*n11_dev_t06_n7_*/eds_eval/decision_evidence/episode_000"),
        (9, "*n17_physics_t09_n7_*/eds_eval/decision_evidence/episode_000"),
    ):
        found = list((SESSION / "artifacts/attempts").glob(pattern))
        if len(found) != 1:
            raise ValueError(f"expected one exposed Dev N7 path for task {task}")
        decisions = inspect_episode(found[0])
        paths.append({"task": task, "episode": str(found[0]),
                      "guided_decisions": len(decisions),
                      "decisions_with_positive_lift": sum(x["any_positive_lift"] for x in decisions),
                      "decisions_with_lift_ge_3cm": sum(x["any_lift_ge_3cm"] for x in decisions),
                      "first_positive_lift_step": next((x["step"] for x in decisions if x["any_positive_lift"]), None),
                      "decisions": decisions})
    result = {"schema": "n18-close-lift-readonly-feasibility-v1",
              "descriptor": "first decoded positive gripper command with projected EEF <=4 cm from target; squared capped final EEF rise",
              "paths": paths,
              "limitation": "BF16 saved projection/latent streams; partition availability only, no alternate action execution"}
    out = HERE / "readonly_feasibility.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    for row in paths:
        print(row["task"], row["guided_decisions"], row["decisions_with_positive_lift"],
              row["decisions_with_lift_ge_3cm"], row["first_positive_lift_step"])


if __name__ == "__main__":
    main()
