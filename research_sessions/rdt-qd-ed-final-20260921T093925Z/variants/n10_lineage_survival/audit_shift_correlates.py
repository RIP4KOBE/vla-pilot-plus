#!/usr/bin/env python3
"""Compare selected gripper/projection signals in shifted vs still target chunks."""
from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
ART = HERE.parents[1]/"artifacts"
SOURCE = HERE/"target-motion-audit-v1.json"
LINEAGE = HERE/"lineage-audit-v1.json"
REPORT = ART/"continuation_20260925/n7-dev-v1/full-dev-report-v1.json"
OUT = HERE/"shift-correlates-v1.json"


def stats(rows):
    def one(key):
        v=[r[key] for r in rows if r[key] is not None]
        return {"n":len(v),"mean":statistics.mean(v) if v else None,
                "median":statistics.median(v) if v else None,
                "min":min(v) if v else None,"max":max(v) if v else None}
    return {"chunks":len(rows),
            **{k:one(k) for k in (
                "target_shift_m","actual_eef_motion_m","motion_cosine_if_target_shift_ge_1cm",
                "selected_positive_gripper_duty","selected_projected_min_reach_m",
                "selected_projected_min_reach_at_positive_command_m",
                "archive_best_minus_terminal_best","gripper_qpos_within_chunk_change",
            )},
            "any_positive_gripper_chunks":sum(r["selected_positive_gripper_duty"]>0 for r in rows),
            "all_positive_gripper_chunks":sum(r["selected_positive_gripper_duty"]==1 for r in rows),
            "projected_reach_le_6cm_chunks":sum(r["selected_projected_min_reach_m"]<=.06 for r in rows)}


def main():
    if OUT.exists():raise SystemExit(f"immutable result exists: {OUT}")
    motion=json.loads(SOURCE.read_text())
    lineage=json.loads(LINEAGE.read_text())
    by_key={(r["task_id"],r["global_step"]):dict(r) for r in motion["rows"]}
    lin={(r["task_id"],r["global_step"]):r for r in lineage["rows"]}
    if set(by_key)!=set(lin) or len(by_key)!=33:
        raise ValueError("motion/lineage row mismatch")
    report=json.loads(REPORT.read_text());sha_count=0
    for cell in report["cells"]:
        folder=ART/"attempts"/cell["accepted_attempt_id"]/"eds_eval/decision_evidence/episode_000"
        for line in (folder/"events.jsonl").open():
            entry=json.loads(line)
            if not any(x["event"]=="final_selection" for x in entry["events"]):continue
            file=folder/entry["bundle"]
            if hashlib.sha256(file.read_bytes()).hexdigest()!=entry["sha256"]:
                raise ValueError(f"SHA mismatch {file}")
            sha_count+=1
            events=torch.load(file,map_location="cpu",weights_only=True)["events"]
            ctx=[e for e in events if e["event"]=="decision_context"]
            final=[e for e in events if e["event"]=="final_selection"]
            decode=[e for e in events if e["event"]=="policy_action_decode"]
            if (len(ctx),len(final),len(decode))!=(1,1,1):
                raise ValueError("missing decision/selection/decode")
            g=ctx[0]["global_step"]
            key=(cell["task_id"],g)
            if key not in by_key:raise ValueError(f"unexpected decision {key}")
            f=final[0]["values"]
            idx=int(f["selected_index"])
            selected=decode[0]["values"]["action_chunk"][0]
            grip=selected[:,6]
            if not bool(((grip==-1)|(grip==1)).all()):raise ValueError("nonbinary gripper")
            positive=grip>0
            gs=f["terminal_population"]["grasp_selection"]
            if int(gs["target_index"])!=0:raise ValueError("target index changed")
            dist=gs["projected_distances_m"][idx].float()
            if len(dist)!=8:raise ValueError("distance horizon changed")
            motion_row=by_key[key]
            motion_row.update({
                "selected_gripper_commands":grip.tolist(),
                "selected_positive_gripper_duty":float(positive.float().mean()),
                "selected_projected_min_reach_m":float(dist.min()),
                "selected_projected_min_reach_at_positive_command_m":float(dist[positive].min()) if bool(positive.any()) else None,
                "archive_best_minus_terminal_best":lin[key]["archive_best_minus_terminal_best"],
            })
            del events
    rows=list(by_key.values())
    if sha_count!=33:raise ValueError(f"expected 33 guided bundle hashes, got {sha_count}")
    shifted=[r for r in rows if r["target_shift_m"]>=.01]
    still=[r for r in rows if r["target_shift_m"]<.01]
    result={"schema":"n7-shift-correlates-v1","scope":"33 guided N7 Dev chunks; observational, nonindependent",
            "source_sha256":{"motion":hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                             "lineage":hashlib.sha256(LINEAGE.read_bytes()).hexdigest(),
                             "dev_report":hashlib.sha256(REPORT.read_bytes()).hexdigest()},
            "native_guided_bundles_sha_verified":sha_count,
            "shift_threshold_m":.01,
            "definitions":{
                "positive_gripper":"Decoded selected action channel 6 is +1; N5 grasp selector treats +1 as its positive/closing-command eligibility condition. It is a command, not measured object contact.",
                "projected_min_reach":"Minimum over 8 projected EEF-to-target distances for selected terminal candidate, from final_selection.terminal_population.grasp_selection; not measured contact.",
                "target_keypoint_validity":"decision_context.target_observation is a source label only. No per-keypoint tracker status/validity or target object pose is persisted in these native decision bundles. KeypointTracker can fallback to initial point if pose unavailable, so a zero displacement does not prove no physical motion.",
                "causal_limit":"Motion association across four episodes and 33 correlated chunks does not establish object grasp/carry or the effect of a different policy."
            },
            "shifted":stats(shifted),"below_threshold":stats(still),
            "by_task":{str(t):{"shifted":stats([r for r in shifted if r["task_id"]==t]),
                                "below_threshold":stats([r for r in still if r["task_id"]==t])} for t in (0,3,6,9)},
            "shifted_chunks":[{k:r[k] for k in (
                "task_id","global_step","target_shift_m","actual_eef_motion_m",
                "motion_cosine_if_target_shift_ge_1cm","selected_gripper_commands",
                "selected_positive_gripper_duty","selected_projected_min_reach_m",
                "selected_projected_min_reach_at_positive_command_m",
                "gripper_qpos_within_chunk_change","archive_best_minus_terminal_best",
            )} for r in shifted]}
    OUT.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print("output",OUT,"sha256",hashlib.sha256(OUT.read_bytes()).hexdigest())


if __name__=="__main__":main()
