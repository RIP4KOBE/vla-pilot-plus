#!/usr/bin/env python3
"""Read-only N8 descriptor screen on the four exposed, matched N9-cohort N7 runs."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

import torch

from replay_exposed_n7_pools import bins, bounds, pair_counts


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "artifacts/continuation_20260928/n9-dev-v2/full-dev-report-v1.json"
OUTPUT = Path(__file__).with_name("n8-post-n9-readonly-v1.json")


def main() -> None:
    if OUTPUT.exists():
        raise SystemExit(f"immutable result exists: {OUTPUT}")
    report_bytes = REPORT.read_bytes()
    report = json.loads(report_bytes)
    assert report["decision"] == "REJECT_DEV" and report["accepted_cells"] == 16
    cells = [cell for cell in report["cells"] if cell["profile"] == "N7"]
    assert [cell["task_id"] for cell in cells] == [0, 3, 6, 9]
    rows = []
    for cell in cells:
        folder = ROOT / "artifacts/attempts" / cell["accepted_attempt_id"] / "eds_eval/decision_evidence/episode_000"
        for line in (folder / "events.jsonl").open():
            summary = json.loads(line)
            if not any(event["event"] == "qd_descriptor_assignment" for event in summary["events"]):
                continue
            bundle = folder / summary["bundle"]
            assert hashlib.sha256(bundle.read_bytes()).hexdigest() == summary["sha256"]
            events = torch.load(bundle, map_location="cpu", weights_only=True)["events"]
            contexts = [event for event in events if event["event"] == "decision_context"]
            assignments = [event for event in events if event["event"] == "qd_descriptor_assignment"]
            scoring = {event["sequence"]: event for event in events if event["event"] == "scoring_inputs"}
            assert len(contexts) == 1 and len(assignments) == 11
            assert [event["values"]["iter_idx"] for event in assignments] == list(range(-1, 10))
            radial_bounds = height_bounds = None
            for assignment in assignments:
                values = assignment["values"]
                source = scoring[values["scoring_batch_id"]]["values"]
                assert source["scoring_scope"]["iter_idx"] == values["iter_idx"]
                xyz = source["projected_xyz"][:, 8, :3].float()
                target = source["keypoints"][0].float()
                assert xyz.shape == (16, 3) and target.shape == (3,)
                delta = xyz - target
                radius = torch.sqrt(delta[:, 0].square() + delta[:, 1].square())
                height = delta[:, 2]
                quadrant = 2 * (delta[:, 0] >= 0).long() + (delta[:, 1] >= 0).long()
                if radial_bounds is None:
                    radial_bounds = bounds(radius.unsqueeze(1))
                    height_bounds = (values["bounds_lo"][1].float(), values["bounds_hi"][1].float())
                    expected = bounds(height.unsqueeze(1))
                    assert abs(height_bounds[0] - expected[0][0]) <= 1e-6
                    assert abs(height_bounds[1] - expected[1][0]) <= 1e-6
                n8 = (quadrant + 4 * bins(radius, *radial_bounds, 2) + 8 * bins(height, *height_bounds, 2)).tolist()
                n7 = (quadrant + 4 * bins(height, *height_bounds, 4)).tolist()
                assert n7 == values["cell_ids"].tolist()
                split, conflated = pair_counts(n7, n8)
                rows.append({
                    "task_id": cell["task_id"], "global_step": contexts[0]["global_step"],
                    "iter_idx": values["iter_idx"], "n7_distinct_cells": len(set(n7)),
                    "n8_distinct_cells": len(set(n8)), "n7_same_cell_n8_split_pairs": split,
                    "n7_different_cell_n8_conflated_pairs": conflated,
                })
    assert rows
    by_task = defaultdict(list)
    for row in rows:
        by_task[row["task_id"]].append(row)
    metrics = ("n7_same_cell_n8_split_pairs", "n7_different_cell_n8_conflated_pairs")
    payload = {
        "schema": "n8-post-n9-readonly-v1",
        "scope": "SHA-verified exposed N7 canonical candidate pools from the N9 matched Dev cohort; no new simulator, model or candidate outcome",
        "source_report_sha256": hashlib.sha256(report_bytes).hexdigest(),
        "cell_rule": "quadrant4 + 4*radial2 + 8*height2; initial quantile bounds; 16 capacity-one cells",
        "decisions": len(rows) // 11,
        "batches": len(rows),
        "totals": {key: sum(row[key] for row in rows) for key in metrics},
        "by_task": {
            str(task): {
                "decisions": len(task_rows) // 11,
                "batches": len(task_rows),
                **{key: sum(row[key] for row in task_rows) for key in metrics},
                "initial_n7_distinct_cells": [row["n7_distinct_cells"] for row in task_rows if row["iter_idx"] == -1],
                "initial_n8_distinct_cells": [row["n8_distinct_cells"] for row in task_rows if row["iter_idx"] == -1],
            }
            for task, task_rows in sorted(by_task.items())
        },
        "rows": rows,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in payload.items() if key != "rows"}, indent=2))
    print("sha256", hashlib.sha256(OUTPUT.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
