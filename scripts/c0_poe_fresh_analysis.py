#!/usr/bin/env python3
"""CPU analysis of completed fresh-guidance C0 and cached-guidance reference."""
import collections
import json
import statistics
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import torch

from c0_poe_fresh_retest import ROOT, OUTPUT, MANIFEST
from c0_poe_online_retest import rows
from c0_trace_replay import STUDY, CACHE, atomic_json, digest
from utils.guidance_utils import load_functions_from_txt
from vlm_query.vlm_agent import VLMAgent

if (ROOT / "active-cohort.json").exists():
    selection = json.loads((ROOT / "active-cohort.json").read_text())
    OUTPUT = ROOT / selection["relative_output"]
    MANIFEST = ROOT / selection["relative_manifest"]

REFERENCE = STUDY / "artifacts/c0_poe_online_20260929/outputs/c0_poe_gemini3_flash_attempt1"
NAMES = ["alphabet soup", "cream cheese", "salad dressing", "bbq sauce", "ketchup",
         "tomato sauce", "butter", "milk", "chocolate pudding", "orange juice"]


def probe(folder):
    metadata = json.loads((folder / "metadata.json").read_text())
    kp = torch.tensor(metadata["init_keypoint_positions"], dtype=torch.float32)
    positions = [kp[0], kp[0] + torch.tensor([.10, 0., 0.]),
                 kp[0] + torch.tensor([0., .10, 0.]), kp[0] + torch.tensor([0., 0., .10]), kp[1]]
    result = {}
    for stage in range(1, metadata["num_stages"] + 1):
        path = folder / f"stage{stage}_guidance.txt"
        fns = load_functions_from_txt(str(path))
        scores = []
        for pos in positions:
            action = pos[None, None, :].repeat(1, 8, 1)
            scores.append(sum(float(fn(kp, action)) for fn in fns))
        historical_scores = None
        if (CACHE / path.name).exists():
            historical_fns = load_functions_from_txt(str(CACHE / path.name))
            historical_scores = [sum(float(fn(kp, pos[None, None, :].repeat(1, 8, 1)))
                                     for fn in historical_fns) for pos in positions]
        result[str(stage)] = {"function_count": len(fns), "scores": scores,
            "historical_scores_on_same_inputs": historical_scores,
            "finite": bool(np.isfinite(scores).all()), "all_zero_on_probe": all(v == 0 for v in scores),
            "source_sha256": digest(path), "historical_source_equal": (CACHE / path.name).exists() and digest(path) == digest(CACHE / path.name)}
    return {"keypoint_map": metadata["key_points_objects_map"],
        "positions": [p.tolist() for p in positions],
        "position_labels": ["keypoint0", "keypoint0_x_plus_0.1", "keypoint0_y_plus_0.1", "keypoint0_z_plus_0.1", "keypoint1"],
        "stages": result}


def analyze():
    audit = json.loads((OUTPUT / "audit.json").read_text())
    if not audit["valid"]:
        raise RuntimeError("Full cohort audit must pass first")
    events = rows(OUTPUT / "eds_eval/stage_events.jsonl")
    queries = [r for r in events if r.get("query_status") in ("ok", "error")]
    compute = rows(OUTPUT / "eds_eval/episode_compute.jsonl")
    old_compute = rows(REFERENCE / "eds_eval/episode_compute.jsonl")
    metrics = rows(OUTPUT / "eds_eval/eds_metrics.jsonl")
    manifest = json.loads(MANIFEST.read_text())
    per_task = []
    extractor = VLMAgent.__new__(VLMAgent)
    for task, name in enumerate(NAMES):
        group = [r for r in queries if r["task_id"] == task]
        row = next(r for r in compute if r["task_id"] == task)
        old = next(r for r in old_compute if r["task_id"] == task)
        folder = OUTPUT / f"episode_{task+1}/vlm_agent"
        particle = f"eds_eval/qualitative/episode_{task:03d}/chunk_000000/single_step_inner_loop/single_step_particles.csv"
        task_metrics = [r for r in metrics if r["episode"] == task]
        by_stage = collections.Counter()
        for metric in task_metrics:
            preceding = [event for event in group if event["global_step"] <= metric["global_step"]]
            stage = preceding[-1]["stage_after"] if preceding else 1
            by_stage[str(stage)] += 1
        per_task.append({"task_id": task, "name": name, "success": task in audit["success_task_ids"],
            "stage_queries": len(group), "parse_fallbacks": sum(not r.get("query_ok") for r in group),
            "guidance_api_request_attempts": row.get("guidance_api_request_attempts"),
            "guided_chunks": row["guided_chunks"], "unguided_chunks": row["unguided_chunks"],
            "guided_chunks_by_stage": dict(by_stage),
            "zero_reward_guided_chunks": sum(r.get("initial_best_reward") == 0 and r.get("final_best_reward") == 0 and r.get("final_mean_reward") == 0 for r in task_metrics),
            "reference_guided_chunks": old["guided_chunks"], "reference_unguided_chunks": old["unguided_chunks"],
            "guided_steps": [r["global_step"] for r in metrics if r["episode"] == task],
            "decisions": dict(collections.Counter(f"stage{r['stage_after']}/{'on' if r['guidance_after'] else 'off'}" for r in group)),
            "first_stage0_step": next((r["global_step"] for r in group if r["stage_after"] == 0), None),
            "initial_particles_equal_reference": digest(OUTPUT / particle) == digest(REFERENCE / particle),
            "stage_descriptions": extractor._extract_stage_descriptions_from_output(str(folder / "output_raw.txt")),
            "reward_probe": probe(folder)})
    result = {"score": f"{audit['success_count']}/10", "success_task_ids": audit["success_task_ids"],
        "per_task": per_task, "guidance_generations": len(per_task),
        "guidance_api_request_attempts": sum(r.get("guidance_api_request_attempts", 0) for r in compute),
        "stage_queries": len(queries),
        "stage_http_attempts": sum(r.get("api_request_attempts", 0) for r in queries),
        "stage_sdk_retry_attempts": sum(r.get("api_sdk_retry_attempts", 0) for r in queries),
        "stage_latency_total_s": sum(r.get("query_latency_s", 0) for r in queries),
        "stage_latency_median_s": statistics.median(r["query_latency_s"] for r in queries),
        "guided_chunks": sum(r["guided_chunks"] for r in compute),
        "unguided_chunks": sum(r["unguided_chunks"] for r in compute),
        "parse_fallbacks": audit["complete_response_parse_fallbacks"],
        "gripper_first_last_mismatch_events": sum(r.get("first_gripper_value") != r.get("last_gripper_value") for r in queries),
        "source_hashes_unchanged": all(digest(STUDY / name) == h for name, h in manifest["source_sha256"].items()),
        "reward_probe_scope": "CPU-only synthetic EEF candidates at actual initial keypoints; zero on these probes is not a proof for all possible inputs"}
    atomic_json(ROOT / "analysis.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(analyze(), ensure_ascii=False, indent=2))
