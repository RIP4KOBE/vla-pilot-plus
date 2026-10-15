#!/usr/bin/env python3
"""Bounded read-only N7 Dev target-keypoint/actual-EEF motion audit."""
from __future__ import annotations

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
REPORT = ART / "continuation_20260925/n7-dev-v1/full-dev-report-v1.json"
OUT = HERE / "target-motion-audit-v1.json"


def norm(v):
    return math.sqrt(sum(float(x)**2 for x in v))


def sub(a,b):
    return [float(x)-float(y) for x,y in zip(a,b)]


def load(entry, folder, cache, hashes):
    key = entry["bundle"]
    if key not in cache:
        file = folder/key
        raw = file.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError(f"SHA mismatch: {file}")
        cache[key] = torch.load(file, map_location="cpu", weights_only=True)["events"]
        hashes.add(key)
    return cache[key]


def one_event(events, name):
    found = [x for x in events if x["event"] == name]
    if len(found) != 1:
        raise ValueError(f"{name}: {len(found)} events")
    return found[0]


def summarize(rows):
    if not rows:
        return {"paired_guided_decisions": 0}
    def stat(key):
        vals = [x[key] for x in rows if x[key] is not None]
        return {"n": len(vals), "mean": statistics.mean(vals) if vals else None,
                "median": statistics.median(vals) if vals else None,
                "max": max(vals) if vals else None}
    return {
        "paired_guided_decisions": len(rows),
        "target_shift_m": stat("target_shift_m"),
        "actual_eef_motion_m": stat("actual_eef_motion_m"),
        "target_eef_distance_start_m": stat("target_eef_distance_start_m"),
        "target_eef_distance_end_m": stat("target_eef_distance_end_m"),
        "target_eef_distance_change_m": stat("target_eef_distance_change_m"),
        "motion_cosine_if_target_shift_ge_1cm": stat("motion_cosine_if_target_shift_ge_1cm"),
        "target_shift_ge_1cm_count": sum(x["target_shift_m"] >= .01 for x in rows),
        "target_shift_ge_2cm_count": sum(x["target_shift_m"] >= .02 for x in rows),
        "target_shift_ge_5cm_count": sum(x["target_shift_m"] >= .05 for x in rows),
        "gripper_qpos_within_chunk_change": stat("gripper_qpos_within_chunk_change"),
    }


def main():
    if OUT.exists():
        raise SystemExit(f"immutable result exists: {OUT}")
    report_bytes = REPORT.read_bytes()
    report = json.loads(report_bytes)
    rows=[]; coverage=[]
    for cell in report["cells"]:
        folder = ART/"attempts"/cell["accepted_attempt_id"]/"eds_eval/decision_evidence/episode_000"
        entries = [json.loads(line) for line in (folder/"events.jsonl").open()]
        context_entries = {}
        step_entries = {}
        guided_steps = []
        for entry in entries:
            for meta in entry["events"]:
                if meta["event"] == "decision_context":
                    context_entries[meta["global_step"]] = entry
                elif meta["event"] == "pre_reset_outcome":
                    step_entries[meta["global_step"]] = entry
                elif meta["event"] == "qd_descriptor_assignment" and meta["global_step"] not in guided_steps:
                    guided_steps.append(meta["global_step"])
        metrics = [json.loads(line) for line in (folder.parents[1]/"eds_metrics.jsonl").open()]
        if len(guided_steps) != len(metrics):
            raise ValueError(f"task {cell['task_id']}: guided count {len(guided_steps)} != metrics {len(metrics)}")
        cache = {}; hashed = set()
        for g in guided_steps:
            if g not in context_entries or g+8 not in context_entries or g+7 not in step_entries or g not in step_entries:
                raise ValueError(f"task {cell['task_id']} global step {g}: incomplete adjacent chunk")
            current = load(context_entries[g], folder, cache, hashed)
            next_events = load(context_entries[g+8], folder, cache, hashed)
            first_step = load(step_entries[g], folder, cache, hashed)
            last_step = load(step_entries[g+7], folder, cache, hashed)
            context = one_event(current,"decision_context")["values"]
            next_context = one_event(next_events,"decision_context")["values"]
            final = one_event(current,"final_selection")["values"]
            target_index = int(final["terminal_population"]["grasp_selection"]["target_index"])
            if target_index != 0:
                raise ValueError(f"task {cell['task_id']} step {g}: target index changed to {target_index}")
            old_target = context["keypoints"][target_index].tolist()
            new_target = next_context["keypoints"][target_index].tolist()
            initial_score = [e for e in current if e["event"] == "scoring_inputs"
                             and e["values"]["scoring_scope"]["role"] == "canonical_initial"]
            if len(initial_score) != 1:
                raise ValueError(f"task {cell['task_id']} step {g}: missing canonical initial scoring")
            scored_target = initial_score[0]["values"]["keypoints"][target_index].tolist()
            if norm(sub(old_target,scored_target)) > .002:
                raise ValueError(f"task {cell['task_id']} step {g}: scored and context keypoint diverge")
            projections = [e for e in current if e["event"] == "projection_origin"]
            if not projections:
                raise ValueError(f"task {cell['task_id']} step {g}: no EEF projection origin")
            old_eef = projections[0]["values"]["source_eef_position"].tolist()
            a = one_event(first_step,"pre_reset_outcome")["values"]
            z = one_event(last_step,"pre_reset_outcome")["values"]
            for o in (a,z):
                if o.get("contemporaneous_target_pose") is not None:
                    raise ValueError(f"task {cell['task_id']} step {g}: target pose now logged; reassess scope")
            new_eef = z["observation"]["robot0_eef_pos"].tolist()
            gripper_first = a["observation"]["robot0_gripper_qpos"].tolist()
            gripper_last = z["observation"]["robot0_gripper_qpos"].tolist()
            dt=sub(new_target,old_target); de=sub(new_eef,old_eef)
            tn=norm(dt); en=norm(de)
            cosine = sum(x*y for x,y in zip(dt,de))/(tn*en) if tn>=.01 and en>1e-8 else None
            old_dist = norm(sub(old_target,old_eef))
            new_dist = norm(sub(new_target,new_eef))
            rows.append({
                "task_id":cell["task_id"],"episode_success":cell["success"],"global_step":g,
                "next_global_step":g+8,"target_index":target_index,
                "target_observation":context["target_observation"],
                "next_target_observation":next_context["target_observation"],
                "target_shift_xyz_m":dt,"target_shift_m":tn,
                "actual_eef_motion_xyz_m":de,"actual_eef_motion_m":en,
                "motion_cosine_if_target_shift_ge_1cm":cosine,
                "target_eef_distance_start_m":old_dist,
                "target_eef_distance_end_m":new_dist,
                "target_eef_distance_change_m":new_dist-old_dist,
                "gripper_qpos_within_chunk_change":norm(sub(gripper_last,gripper_first)),
                "gripper_qpos_first":gripper_first,"gripper_qpos_last":gripper_last,
                "reward_after_chunk":z["reward"],"success_after_chunk":z["success"],
            })
        coverage.append({"task_id":cell["task_id"],"episode_success":cell["success"],
                         "guided_chunks":len(guided_steps),"context_rows":len(context_entries),
                         "step_outcome_rows":len(step_entries),"native_bundles_sha_verified":len(hashed),
                         "target_distance_after_nonnull":sum(x.get("target_distance_after") is not None for x in metrics)})
        print(f"task {cell['task_id']}: {len(guided_steps)} adjacent pairs, {len(hashed)} bundles SHA verified",flush=True)
    if len(rows)!=33:
        raise ValueError(f"expected 33 paired guided decisions, got {len(rows)}")
    result={"schema":"n7-target-motion-audit-v1","scope":"already-exposed four N7 Dev episodes only",
            "source_report_sha256":hashlib.sha256(report_bytes).hexdigest(),
            "definitions":{
                "target_keypoint":"Existing simulator-object-pose-backed keypoint input at the policy's current and next decision; target_index from native grasp selection, 0 in all 33 decisions.",
                "eef_start":"Native projection_origin.source_eef_position at decision start, already fed to policy projection.",
                "eef_end":"Actual robot0_eef_pos in last pre_reset_outcome of the 8 executed actions, before automatic reset.",
                "target_shift":"Euclidean displacement of that keypoint from decision g to next decision g+8; includes any object motion and keypoint tracking changes; not a measured grasp outcome.",
                "physical_limit":"No contemporaneous_target_pose in step outcomes, no contact sensor or causal counterfactual. Same-run target/EFF co-motion is observational and may arise from scene dynamics or keypoint tracking; it does not prove grasp/carry."
            },"coverage":coverage,
            "overall":summarize(rows),
            "by_task":{str(t):summarize([r for r in rows if r['task_id']==t]) for t in (0,3,6,9)},
            "by_episode_outcome":{label:summarize([r for r in rows if r['episode_success']==value]) for label,value in (("failure",False),("success",True))},
            "rows":rows}
    OUT.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print("output",OUT,"sha256",hashlib.sha256(OUT.read_bytes()).hexdigest())


if __name__=="__main__":
    main()
