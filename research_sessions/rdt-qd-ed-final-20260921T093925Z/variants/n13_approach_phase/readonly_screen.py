"""SHA-verified, read-only screen of a closest-approach QD descriptor.

This is partition analysis of exposed N7 candidate pools, not a simulation or
an estimate of success for unexecuted actions.
"""

import hashlib
import json
from collections import Counter
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[2]
ATTEMPTS = ROOT / "artifacts/attempts"
OUT = Path(__file__).with_name("readonly_screen.json")


def load_bound_bundle(directory, record):
    path = directory / record["bundle"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
        raise ValueError(f"bundle hash mismatch: {path}")
    return torch.load(path, map_location="cpu", weights_only=False)["events"]


def cells_for_approach(projected, target, initial_height_bounds):
    delta = projected[:, 1:, :] - target[:3].view(1, 1, 3)
    nearest_time = torch.linalg.vector_norm(delta[:, :, :2], dim=2).argmin(dim=1)
    nearest = delta[torch.arange(len(delta)), nearest_time]
    quadrant = 2 * (nearest[:, 0] >= 0).long() + (nearest[:, 1] >= 0).long()
    lo, hi = initial_height_bounds
    height_bin = torch.floor((nearest[:, 2] - lo) / (hi - lo) * 4).long().clamp(0, 3)
    return 4 * height_bin + quadrant, nearest_time + 1, nearest[:, 2]


def pair_counts(old, new):
    split = conflate = same = 0
    for i in range(len(old)):
        for j in range(i + 1, len(old)):
            if old[i] == old[j] and new[i] != new[j]:
                split += 1
            elif old[i] != old[j] and new[i] == new[j]:
                conflate += 1
            elif old[i] == old[j] and new[i] == new[j]:
                same += 1
    return split, conflate, same


def bounds_from_initial(height):
    q = torch.quantile(height.float(), torch.tensor([0.05, 0.95]))
    span = q[1] - q[0]
    lo, hi = q[0] - .1 * span, q[1] + .1 * span
    if hi - lo < .08:
        median = torch.quantile(height.float(), .5)
        lo, hi = median - .04, median + .04
    return float(lo), float(hi)


def main():
    report = {"schema": "n13-approach-phase-readonly-v1", "tasks": {}}
    for task in (0, 3, 6, 9):
        episodes = list(ATTEMPTS.glob(f"*n7_dev_t{task:02d}_*/eds_eval/decision_evidence/episode_000"))
        if len(episodes) != 1:
            raise ValueError(f"expected one N7 Dev evidence episode for task {task}: {len(episodes)}")
        episode = episodes[0]
        summary = Counter()
        decision_rows = []
        for line in (episode / "events.jsonl").open():
            record = json.loads(line)
            if not any(e["event"] == "qd_descriptor_assignment" for e in record["events"]):
                continue
            events = load_bound_bundle(episode, record)
            by_seq = {e["sequence"]: e for e in events}
            context = next(e for e in events if e["event"] == "decision_context")
            assignments = [e for e in events if e["event"] == "qd_descriptor_assignment"]
            if len(assignments) != 11:
                raise ValueError(f"expected 11 canonical QD assignments in {record['bundle']}")
            first = assignments[0]
            first_score = by_seq[first["values"]["scoring_batch_id"]]
            if first_score["values"]["scoring_scope"]["role"] != "canonical_initial":
                raise ValueError("initial scoring scope mismatch")
            initial_xyz = first_score["values"]["projected_xyz"]
            target = first_score["values"]["keypoints"].reshape(-1)[:3].float()
            initial_delta = initial_xyz[:, 1:, :] - target.view(1, 1, 3)
            times = torch.linalg.vector_norm(initial_delta[:, :, :2], dim=2).argmin(dim=1)
            height = initial_delta[torch.arange(16), times, 2]
            bounds = bounds_from_initial(height)
            row = Counter()
            for assignment in assignments:
                v = assignment["values"]
                score = by_seq[v["scoring_batch_id"]]
                sv = score["values"]
                if sv["scoring_scope"]["role"] not in ("canonical_initial", "canonical_offspring", "canonical_population"):
                    raise ValueError("noncanonical scoring scope")
                canonical = next(e for e in events if e["event"] == "canonical_candidate_batch" and e["values"]["iter_idx"] == v["iter_idx"])
                if not torch.equal(sv["samples"], canonical["values"]["candidates"]):
                    raise ValueError("scoring samples do not equal canonical candidates")
                xyz = sv["projected_xyz"]
                target = sv["keypoints"].reshape(-1)[:3].float()
                if tuple(xyz.shape) != (16, 9, 3):
                    raise ValueError("wrong projected shape")
                delta = xyz[:, 8, :3] - target
                expected = torch.stack((2 * (delta[:, 0] >= 0).float() + (delta[:, 1] >= 0).float(), delta[:, 2]), dim=1)
                if not torch.allclose(expected.float(), v["descriptors"].float(), atol=1e-5, rtol=0):
                    raise ValueError("recorded N7 descriptor differs from projection")
                old = v["cell_ids"].tolist()
                new, nearest_time, _ = cells_for_approach(xyz, target, bounds)
                split, conflate, same = pair_counts(old, new.tolist())
                row.update({"split_pairs": split, "conflated_pairs": conflate,
                            "shared_collision_pairs": same,
                            "old_occupied_sum": len(set(old)), "new_occupied_sum": len(set(new.tolist())),
                            "candidate_batches": 1, "nearest_before_endpoint": int((nearest_time < 8).sum())})
            summary.update(row)
            decision_rows.append({"decision_id": context["decision_id"], **dict(row)})
        report["tasks"][str(task)] = {"summary": dict(summary), "decisions": decision_rows,
                                          "evidence_episode": str(episode)}
    report["all_tasks"] = dict(sum((Counter(x["summary"]) for x in report["tasks"].values()), Counter()))
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report["all_tasks"], sort_keys=True))
    for task, val in report["tasks"].items():
        print(task, json.dumps(val["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
