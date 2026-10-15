#!/usr/bin/env python3
"""SHA-verified read-only summary of already exposed N11 matched Dev pools."""
from __future__ import annotations

import collections
import hashlib
import json
from pathlib import Path

import torch


HERE = Path(__file__).resolve().parent
SESSION = HERE.parents[1]
ARTIFACTS = SESSION / "artifacts"
REPORT = SESSION / "variants/n11_parent_survival/dev-comparison-v1.json"
OUTPUT = HERE / "terminal-affordance-readonly-v1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise SystemExit(f"immutable output already exists: {OUTPUT}")
    report = json.loads(REPORT.read_text())
    assert report["all_sixteen_valid"] and report["cohort"] == "N11_EXACT_PARENT_SURVIVAL_DEV_20260928"
    rows = []
    bundle_hashes = {}
    for task, arms in report["tasks"].items():
        for profile in ("N7", "N11"):
            cell = arms[profile]
            folder = ARTIFACTS / "attempts" / cell["attempt_id"] / "eds_eval/decision_evidence/episode_000"
            summaries = [json.loads(s) for s in (folder / "events.jsonl").read_text().splitlines()]
            count = 0
            for entry in summaries:
                if not any(e["event"] == "final_selection" for e in entry["events"]):
                    continue
                bundle = folder / entry["bundle"]
                digest = sha256(bundle)
                assert digest == entry["sha256"], bundle
                native = torch.load(bundle, map_location="cpu", weights_only=True)
                events = native["events"]
                assert collections.Counter(e["event"] for e in events) == collections.Counter(e["event"] for e in entry["events"])
                context = next(e for e in events if e["event"] == "decision_context")
                final = next(e["values"] for e in events if e["event"] == "final_selection")
                terminal = final["terminal_population"]
                grasp = terminal["grasp_selection"]
                idx = int(final["selected_index"])
                eligible = tuple(int(i) for i in grasp["eligible_indices"])
                assert all(0 <= i < 16 for i in eligible)
                assert idx in eligible or not eligible
                reach = grasp["projected_distances_m"]
                positive = grasp["positive_commands"]
                assert reach.shape == positive.shape == (16, 8)
                qualities = terminal["raw_provider_quality"]
                assert qualities.shape == (16,)
                assert torch.isfinite(reach).all() and torch.isfinite(qualities).all()
                close_reach = reach <= 0.06
                close_positive = close_reach & positive
                row = {
                    "task": int(task), "profile": profile, "episode_success": bool(cell["success"]),
                    "global_step": int(context["global_step"]), "stage": int(context["values"]["stage"]),
                    "selected_index": idx, "selected_exact_survivor": bool(profile == "N11" and idx < 4),
                    "eligible_count": len(eligible), "eligible_indices": list(eligible),
                    "positive_candidates": int(positive.any(dim=1).sum()),
                    "within_6cm_candidates": int(close_reach.any(dim=1).sum()),
                    "positive_within_6cm_candidates": int(close_positive.any(dim=1).sum()),
                    "selected_positive": bool(positive[idx].any()),
                    "selected_min_reach_m": float(reach[idx].min()),
                    "selected_quality": float(qualities[idx]),
                    "best_terminal_quality": float(qualities.max()),
                    "sha256": digest,
                }
                rows.append(row)
                bundle_hashes[str(bundle.relative_to(SESSION))] = digest
                count += 1
            assert count == cell["guided_decisions"], (task, profile, count)
    by_task = {}
    for task in sorted(int(t) for t in report["tasks"]):
        for profile in ("N7", "N11"):
            subset = [r for r in rows if r["task"] == task and r["profile"] == profile]
            key = f"task{task}/{profile}"
            by_task[key] = {
                "success": subset[0]["episode_success"],
                "guided_decisions": len(subset),
                "eligible_decisions": sum(r["eligible_count"] > 0 for r in subset),
                "positive_within_6cm_decisions": sum(r["positive_within_6cm_candidates"] > 0 for r in subset),
                "selected_positive_decisions": sum(r["selected_positive"] for r in subset),
                "first_three_guided": [
                    {k: r[k] for k in ("global_step", "stage", "eligible_count", "positive_within_6cm_candidates", "selected_positive", "selected_min_reach_m", "selected_exact_survivor")}
                    for r in subset[:3]
                ],
            }
    result = {
        "schema": "terminal-affordance-readonly-v1",
        "scope": "already exposed N11 matched Dev tasks 0,3,6,9; N7/N11 only; no alternate action executed",
        "report_sha256": sha256(REPORT),
        "bundle_hashes": bundle_hashes,
        "summary_by_task": by_task,
        "rows": rows,
        "limits": [
            "A projected reach and positive gripper command do not certify physical contact or success.",
            "The executed-policy episodes diverge after changed actions; later pools are not same-state counterfactuals.",
            "No validation or formal identities are read.",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"output": str(OUTPUT), "sha256": sha256(OUTPUT), "summary_by_task": by_task}, indent=2))


if __name__ == "__main__":
    main()
