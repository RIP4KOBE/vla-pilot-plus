#!/usr/bin/env python3
"""Read-only, SHA-verified audit of exposed N7/N9 development decisions.

No counterfactual action is executed.  Parent/child slot identity comes from the
native allocation and canonical-batch records, not descriptor similarity.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import statistics
from pathlib import Path

import torch


HERE = Path(__file__).resolve().parent
SESSION = HERE.parents[1]
ART = SESSION / "artifacts"
REPORTS = {
    "n7_original": ART / "continuation_20260925/n7-dev-v1/full-dev-report-v1.json",
    "n9_matched": ART / "continuation_20260928/n9-dev-v2/full-dev-report-v1.json",
}


def scalar(x):
    return float(x.item()) if isinstance(x, torch.Tensor) else float(x)


def vector(x):
    return x.tolist() if isinstance(x, torch.Tensor) else list(x)


def aggregate(rows):
    if not rows:
        return {"decisions": 0}
    keys = (
        "parent_slots", "unique_parent_fingerprints", "unique_parent_cells",
        "offspring_better_slots", "offspring_same_fingerprint_slots",
        "selected_parent_to_child_quality_delta", "parent_best_minus_terminal_best",
        "archive_best_minus_terminal_best", "terminal_best_minus_selected",
        "archive_best_minus_selected", "selected_parent_rank", "selected_terminal_rank",
        "selected_parent_cell_slots", "selected_cell_slots", "selected_archive_exact_match",
    )
    ans = {"decisions": len(rows)}
    for key in keys:
        vals = [r[key] for r in rows if r[key] is not None]
        ans[key] = {
            "n": len(vals),
            "sum": sum(vals),
            "mean": statistics.mean(vals) if vals else None,
            "median": statistics.median(vals) if vals else None,
        }
    ans["selection_rules"] = dict(collections.Counter(r["selection_rule"] for r in rows))
    ans["tasks"] = dict(collections.Counter(str(r["task_id"]) for r in rows))
    ans["terminal_best_lost_decisions"] = sum(r["archive_best_minus_terminal_best"] > 1e-6 for r in rows)
    ans["selection_lost_decisions"] = sum(r["terminal_best_minus_selected"] > 1e-6 for r in rows)
    ans["both_lost_decisions"] = sum(
        r["archive_best_minus_terminal_best"] > 1e-6
        and r["terminal_best_minus_selected"] > 1e-6 for r in rows
    )
    return ans


def inspect_decision(events, *, cohort, profile, task_id, success, bundle):
    by_name = collections.defaultdict(list)
    for event in events:
        by_name[event["event"]].append(event)
    expected = {
        "decision_context": 1, "archive_parent_allocation": 10,
        "parent_allocation": 10, "canonical_candidate_batch": 11,
        "qd_descriptor_assignment": 11, "final_selection": 1,
        "policy_action_decode": 1, "decision_committed": 1,
    }
    for name, count in expected.items():
        if len(by_name[name]) != count:
            raise ValueError(f"{bundle}: {name}: {len(by_name[name])} != {count}")
    canonical = {
        e["values"]["iter_idx"]: e["values"]
        for e in by_name["canonical_candidate_batch"]
    }
    allocation = {e["values"]["iter_idx"]: e["values"] for e in by_name["archive_parent_allocation"]}
    parent = {e["values"]["iter_idx"]: e["values"] for e in by_name["parent_allocation"]}
    assignment = {e["values"]["iter_idx"]: e["values"] for e in by_name["qd_descriptor_assignment"]}
    if set(canonical) != set(range(-1, 10)) or set(allocation) != set(range(10)):
        raise ValueError(f"{bundle}: incomplete iteration range")
    if set(parent) != set(range(10)) or set(assignment) != set(range(-1, 10)):
        raise ValueError(f"{bundle}: incomplete parent/descriptor range")

    total_parent_slots = better_slots = unchanged_fingerprint_slots = 0
    unique_parent_fp = set()
    unique_parent_cells = set()
    iteration_rows = []
    for i in range(10):
        a, p, child = allocation[i], parent[i], canonical[i]
        ps = a["parent_fingerprints"]
        cs = child["canonical_fingerprints"]
        pcells = vector(a["parent_cell_ids"])
        qparent = vector(a["parent_rewards"])
        qchild = vector(child["effective_quality"])
        if not all(len(x) == 16 for x in (ps, cs, pcells, qparent, qchild)):
            raise ValueError(f"{bundle}: non-16 allocation/canonical row")
        if p["parent_fingerprints"] != ps or p["source_fingerprints"] != ps:
            raise ValueError(f"{bundle}: parent fingerprint slot mismatch")
        if vector(p["parent_indices"]) != list(range(16)) or p["elite_count"] != 0:
            raise ValueError(f"{bundle}: parent index contract changed")
        if vector(p["parent_cell_ids"]) != pcells:
            raise ValueError(f"{bundle}: parent cell contract changed")
        if any(abs(x-y) > 1e-6 for x,y in zip(vector(p["source_quality"]),qparent)):
            raise ValueError(f"{bundle}: parent quality mismatch")
        if len(assignment[i]["cell_ids"]) != 16:
            raise ValueError(f"{bundle}: descriptor row mismatch")
        # The allocated slot is the canonical offspring slot after EDS perturbation.
        unchanged = sum(x == y for x,y in zip(ps,cs))
        better = sum(y > x + 1e-6 for x,y in zip(qparent,qchild))
        unchanged_fingerprint_slots += unchanged
        better_slots += better
        total_parent_slots += 16
        unique_parent_fp.update(ps)
        unique_parent_cells.update(pcells)
        iteration_rows.append({
            "iter_idx": i, "distinct_parent_fingerprints": len(set(ps)),
            "distinct_parent_cells": len(set(pcells)),
            "offspring_better_slots": better,
            "offspring_same_fingerprint_slots": unchanged,
            "parent_best_quality": max(qparent), "offspring_best_quality": max(qchild),
            "parent_best_minus_offspring_best": max(qparent)-max(qchild),
        })

    final = by_name["final_selection"][0]["values"]
    terminal = final["terminal_population"]
    idx = int(final["selected_index"])
    if not 0 <= idx < 16 or idx != int(terminal["selected_index"]):
        raise ValueError(f"{bundle}: final index mismatch")
    last = canonical[9]
    if last["canonical_fingerprints"][idx] != final["selected_canonical_fingerprint"]:
        raise ValueError(f"{bundle}: selected canonical identity mismatch")
    if last["occurrence_ids"][idx] != terminal["selected_occurrence_id"]:
        raise ValueError(f"{bundle}: selected occurrence mismatch")
    if int(vector(assignment[9]["cell_ids"])[idx]) != int(final["selected_cell"]):
        raise ValueError(f"{bundle}: selected child cell mismatch")
    if int(vector(allocation[9]["parent_cell_ids"])[idx]) != int(terminal["selected_parent_cell"]):
        raise ValueError(f"{bundle}: selected parent cell mismatch")
    if not torch.equal(final["population"], last["candidates"]):
        raise ValueError(f"{bundle}: final population not canonical terminal row")
    if not torch.equal(final["selected_latent"], last["candidates"][idx:idx+1]):
        raise ValueError(f"{bundle}: final selected latent mismatch")
    decoded = by_name["policy_action_decode"][0]["values"]
    committed = by_name["decision_committed"][0]["values"]
    if decoded["selected_canonical_fingerprint"] != final["selected_canonical_fingerprint"]:
        raise ValueError(f"{bundle}: decoded identity mismatch")
    if not torch.equal(decoded["selected_latent"], final["selected_latent"]):
        raise ValueError(f"{bundle}: decoded latent mismatch")
    if not torch.equal(decoded["action_chunk"], committed["action_chunk"]):
        raise ValueError(f"{bundle}: committed action mismatch")
    if not torch.equal(terminal["raw_provider_quality"], last["effective_quality"]):
        raise ValueError(f"{bundle}: terminal quality mismatch")
    terminal_q = vector(last["effective_quality"])
    selected_q = terminal_q[idx]
    if abs(selected_q - scalar(final["selected_quality"])) > 1e-6:
        raise ValueError(f"{bundle}: selected quality mismatch")
    archive = final["archive_reference"]
    if archive is None:
        raise ValueError(f"{bundle}: archive reference missing")
    archive_best = scalar(archive["selected_quality"])
    terminal_best = max(terminal_q)
    if archive_best + 1e-6 < terminal_best or terminal_best + 1e-6 < selected_q:
        raise ValueError(f"{bundle}: quality ordering violated")
    selected_parent_q = scalar(allocation[9]["parent_rewards"][idx])
    selected_parent_fp = allocation[9]["parent_fingerprints"][idx]
    parent_best = max(vector(allocation[9]["parent_rewards"]))
    parent_cell = int(terminal["selected_parent_cell"])
    child_cell = int(final["selected_cell"])
    ctx = by_name["decision_context"][0]
    return {
        "cohort": cohort, "profile": profile, "task_id": task_id,
        "episode_success": success, "global_step": ctx["global_step"],
        "stage": str(ctx["values"]["stage"]), "bundle": bundle,
        "parent_slots": total_parent_slots,
        "unique_parent_fingerprints": len(unique_parent_fp),
        "unique_parent_cells": len(unique_parent_cells),
        "offspring_better_slots": better_slots,
        "offspring_same_fingerprint_slots": unchanged_fingerprint_slots,
        "last_iter_distinct_parent_fingerprints": iteration_rows[-1]["distinct_parent_fingerprints"],
        "last_iter_distinct_parent_cells": iteration_rows[-1]["distinct_parent_cells"],
        "selected_parent_fingerprint": selected_parent_fp,
        "selected_canonical_fingerprint": final["selected_canonical_fingerprint"],
        "selected_occurrence_id": terminal["selected_occurrence_id"],
        "selected_index": idx, "selected_parent_cell": parent_cell,
        "selected_child_cell": child_cell,
        "selected_parent_cell_slots": vector(allocation[9]["parent_cell_ids"]).count(parent_cell),
        "selected_cell_slots": vector(assignment[9]["cell_ids"]).count(child_cell),
        "selected_parent_quality": selected_parent_q,
        "selected_child_quality": selected_q,
        "selected_parent_to_child_quality_delta": selected_q-selected_parent_q,
        "parent_best_minus_terminal_best": parent_best-terminal_best,
        "archive_best_minus_terminal_best": archive_best-terminal_best,
        "terminal_best_minus_selected": terminal_best-selected_q,
        "archive_best_minus_selected": archive_best-selected_q,
        "selected_parent_rank": 1+sum(x > selected_parent_q+1e-6 for x in vector(allocation[9]["parent_rewards"])),
        "selected_terminal_rank": 1+sum(x > selected_q+1e-6 for x in terminal_q),
        "selected_archive_exact_match": int(final["selected_canonical_fingerprint"] == archive["selected_fingerprint"]),
        "selection_rule": final["selection_rule"],
        "iteration_rows": iteration_rows,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=HERE/"lineage-audit-v1.json")
    ap.add_argument("--include-n9-matched", action="store_true", help="optional matched N7/N9 Dev extension")
    args = ap.parse_args()
    if args.output.exists():
        raise SystemExit(f"immutable result exists: {args.output}")
    rows = []
    coverage = []
    source_hashes = {}
    selected_reports = {"n7_original": REPORTS["n7_original"]}
    if args.include_n9_matched:
        selected_reports["n9_matched"] = REPORTS["n9_matched"]
    for cohort, report_path in selected_reports.items():
        report_bytes = report_path.read_bytes()
        source_hashes[cohort] = hashlib.sha256(report_bytes).hexdigest()
        report = json.loads(report_bytes)
        for cell in report["cells"]:
            profile = cell.get("profile", "N7")
            if cohort == "n9_matched" and profile not in ("N7", "N9"):
                continue
            folder = ART/"attempts"/cell["accepted_attempt_id"]/"eds_eval/decision_evidence/episode_000"
            events_path = folder/"events.jsonl"
            logs = [json.loads(line) for line in events_path.open()]
            count = 0
            for entry in logs:
                if not any(x["event"] == "qd_descriptor_assignment" for x in entry["events"]):
                    continue
                bundle = folder/entry["bundle"]
                if hashlib.sha256(bundle.read_bytes()).hexdigest() != entry["sha256"]:
                    raise ValueError(f"SHA mismatch: {bundle}")
                native = torch.load(bundle, map_location="cpu", weights_only=True)
                summary_count = collections.Counter(x["event"] for x in entry["events"])
                native_count = collections.Counter(x["event"] for x in native["events"])
                if summary_count != native_count:
                    raise ValueError(f"event count mismatch: {bundle}")
                rows.append(inspect_decision(
                    native["events"], cohort=cohort, profile=profile,
                    task_id=cell["task_id"], success=cell["success"],
                    bundle=str(bundle.relative_to(SESSION)),
                ))
                count += 1
                del native
            coverage.append({
                "cohort": cohort, "profile": profile, "task_id": cell["task_id"],
                "episode_success": cell["success"], "attempt_id": cell["accepted_attempt_id"],
                "event_bundle_summaries_scanned": len(logs),
                "guided_event_bundles_sha_verified": count, "guided_decisions": count,
                "report_guided_chunks": cell.get("guided_chunks"),
            })
            if cell.get("guided_chunks") is not None and count != cell["guided_chunks"]:
                raise ValueError(f"{cohort}/{profile}/{cell['task_id']}: guided count mismatch")
            print(f"{cohort}/{profile}/task{cell['task_id']}: {count} guided bundles SHA verified, {len(logs)} summaries scanned", flush=True)
    by_group = {}
    for cohort, profile in sorted({(r["cohort"], r["profile"]) for r in rows}):
        by_group[f"{cohort}/{profile}"] = aggregate([r for r in rows if (r["cohort"],r["profile"]) == (cohort,profile)])
    by_task = {}
    for cohort, profile, task in sorted({(r["cohort"],r["profile"],r["task_id"]) for r in rows}):
        by_task[f"{cohort}/{profile}/task{task}"] = aggregate([r for r in rows if (r["cohort"],r["profile"],r["task_id"]) == (cohort,profile,task)])
    result = {
        "schema": "lineage-audit-v1", "scope": "already-exposed development evidence only; no C1 validation/formal", 
        "source_report_sha256": source_hashes,
        "coverage": coverage, "summary_by_group": by_group, "summary_by_task": by_task,
        "metric_definitions": {
            "quality": "Native effective_quality (higher is better), within a single decision/stage; no cross-stage comparison.",
            "offspring_better_slots": "Count of same-index canonical child quality > allocated parent reward by 1e-6, across 10x16 slots per guided decision.",
            "archive_best_minus_terminal_best": "Final archive best quality minus highest quality in final canonical 16; loss from restricting execution to terminal row.",
            "terminal_best_minus_selected": "Highest quality in terminal canonical 16 minus quality of selected/executed slot; selection trade-off, not proven regret for task success.",
            "selected_parent_to_child_quality_delta": "Native quality of selected terminal child minus quality of its recorded immediate parent in iteration 9.",
            "exact_identity": "Parent allocation fingerprint/cell/reward -> same-slot canonical offspring fingerprint/reward -> selected terminal occurrence/index -> decoded/committed action chunk.",
            "ancestry_limit": "Original archive insertion occurrence is absent; a fingerprint is a latent identity but cannot disambiguate duplicate insertions or prove full unique genealogy.",
            "counterfactual_limit": "No task success or physical outcome is observed for any unexecuted parent, offspring or alternate final selection.",
        },
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    print("output",args.output,"sha256",hashlib.sha256(args.output.read_bytes()).hexdigest(),flush=True)


if __name__ == "__main__":
    main()
