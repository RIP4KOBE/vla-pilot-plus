#!/usr/bin/env python3
"""Describe a completed Poe C0 cohort and exact overlaps with archived inputs."""
import collections
import json
from pathlib import Path
import statistics

from c0_poe_online_retest import OUTPUT, ROOT, MANIFEST, rows
from c0_trace_replay import CACHE, STUDY, TRACE, atomic_json, digest


def decision(row):
    return row.get("stage_after"), row.get("guidance_after")


def fingerprint(meta):
    return meta.get("prompt_sha256", meta.get("codex_prompt_sha256")), tuple(meta["image_png_sha256"])


def analyze():
    audit = json.loads((OUTPUT / "audit.json").read_text())
    if not audit["valid"]:
        raise RuntimeError("Do not interpret an incomplete cohort as a ten-task score")
    events = rows(OUTPUT / "eds_eval/stage_events.jsonl")
    queries = [e for e in events if e.get("query_status") in ("ok", "error")]
    historical = rows(TRACE)
    old_capture = STUDY / "artifacts/c0_online_stage_diagnostic_20260928/captured_stage_inputs"
    index = {}
    for folder in sorted(old_capture.glob("request_*")):
        meta = json.loads((folder / "metadata.json").read_text())
        index.setdefault(fingerprint(meta), []).append(meta["query_index"])
    overlap = []
    for number, event in enumerate(queries):
        meta = json.loads((OUTPUT / f"captured_stage_inputs/request_{number:04d}/metadata.json").read_text())
        for old_index in index.get(fingerprint(meta), []):
            old = historical[old_index]
            if old["task_id"] != event["task_id"]:
                continue
            overlap.append({"online_query_index": number, "historical_query_index": old_index,
                            "task_id": event["task_id"], "step": event["global_step"],
                            "historical_decision": decision(old), "online_decision": decision(event),
                            "decision_equal": decision(old) == decision(event),
                            "historical_parse_ok": old.get("query_ok"), "online_parse_ok": event.get("query_ok")})
    per_task = []
    for task in range(10):
        group = [e for e in queries if e["task_id"] == task]
        per_task.append({"task_id": task, "success": task in audit["success_task_ids"],
            "stage_queries": len(group), "parse_fallbacks": sum(not r.get("query_ok") for r in group),
            "latency_total_s": sum(r.get("query_latency_s", 0) for r in group),
            "decisions": dict(collections.Counter(f"stage{r['stage_after']}/{'on' if r['guidance_after'] else 'off'}" for r in group)),
            "first_stage0_step": next((r["global_step"] for r in group if r["stage_after"] == 0), None)})
    manifest = json.loads(MANIFEST.read_text())
    result = {"score": f"{audit['success_count']}/10", "success_task_ids": audit["success_task_ids"],
        "per_task": per_task, "stage_queries": len(queries),
        "total_http_attempts": sum(r.get("api_request_attempts", 0) for r in queries),
        "sdk_retry_attempts": sum(r.get("api_sdk_retry_attempts", 0) for r in queries),
        "latency_median_s": statistics.median(r["query_latency_s"] for r in queries),
        "latency_total_s": sum(r["query_latency_s"] for r in queries),
        "historical_parse_fallbacks": sum(not r.get("query_ok") for r in historical),
        "online_parse_fallbacks": audit["complete_response_parse_fallbacks"],
        "exact_input_overlap": overlap,
        "exact_input_overlap_matching_decisions": sum(r["decision_equal"] for r in overlap),
        "source_hashes_unchanged": all(digest(STUDY / n) == h for n, h in manifest["source_sha256"].items()),
        "reward_cache_unchanged": all(digest(CACHE / n) == h for n, h in manifest["cache_sha256"].items())}
    atomic_json(ROOT / "analysis.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(analyze(), indent=2))
