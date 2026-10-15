#!/usr/bin/env python3
"""Fixed-rule projected 6 cm contact-entry audit on exposed N7 Dev decisions."""
from __future__ import annotations

import collections
import hashlib
import json
import math
import statistics
from pathlib import Path

import torch

HERE=Path(__file__).resolve().parent
ART=HERE.parents[1]/"artifacts"
REPORT=ART/"continuation_20260925/n7-dev-v1/full-dev-report-v1.json"
MOTION=HERE/"target-motion-audit-v1.json"
OUT=HERE/"contact-entry-audit-v1.json"
RADIUS_M=.06
SCORE_TOLERANCE=.02


def entry_metrics(path,target):
    """Return first outside→inside transition on a projected 9-position path."""
    xyz=path.detach().float()
    target=target.detach().float()
    distances=torch.linalg.vector_norm(xyz-target,dim=-1)
    for t in range(1,9):
        if float(distances[t-1])>RADIUS_M and float(distances[t])<=RADIUS_M:
            length=float(torch.linalg.vector_norm(xyz[t]-xyz[t-1]))
            return {"entry_action_index":t-1,"entry_step_length_m":length,
                    "start_inside_radius":bool(float(distances[0])<=RADIUS_M),
                    "projected_min_reach_m":float(distances.min())}
    return {"entry_action_index":None,"entry_step_length_m":None,
            "start_inside_radius":bool(float(distances[0])<=RADIUS_M),
            "projected_min_reach_m":float(distances.min())}


def summary(rows):
    def metric(k):
        x=[r[k] for r in rows if r[k] is not None]
        return {"n":len(x),"mean":statistics.mean(x) if x else None,
                "median":statistics.median(x) if x else None,
                "min":min(x) if x else None,"max":max(x) if x else None}
    return {"decisions":len(rows),"entry_observed":sum(r["entry_action_index"] is not None for r in rows),
            "entry_unknown":sum(r["entry_action_index"] is None for r in rows),
            "start_inside_radius":sum(r["start_inside_radius"] for r in rows),
            "positive_gripper_at_entry":sum(r["gripper_sign_at_entry"]==1 for r in rows),
            "negative_gripper_at_entry":sum(r["gripper_sign_at_entry"]==-1 for r in rows),
            "entry_step_length_m":metric("entry_step_length_m"),
            "projected_min_reach_m":metric("projected_min_reach_m"),
            "target_shift_m":metric("target_shift_m"),
            "structural_alternative_exists":sum(r["qualifying_alternative_count"]>0 for r in rows if r["qualifying_alternative_count"] is not None),
            "structural_alternative_unknown":sum(r["qualifying_alternative_count"] is None for r in rows)}


def main():
    if OUT.exists():raise SystemExit(f"immutable result exists: {OUT}")
    report=json.loads(REPORT.read_text())
    motion=json.loads(MOTION.read_text())
    motion_lookup={(r["task_id"],r["global_step"]):r for r in motion["rows"]}
    rows=[];sha_count=0
    for cell in report["cells"]:
        folder=ART/"attempts"/cell["accepted_attempt_id"]/"eds_eval/decision_evidence/episode_000"
        for line in (folder/"events.jsonl").open():
            entry=json.loads(line)
            if not any(e["event"]=="final_selection" for e in entry["events"]):continue
            file=folder/entry["bundle"]
            if hashlib.sha256(file.read_bytes()).hexdigest()!=entry["sha256"]:
                raise ValueError(f"SHA mismatch: {file}")
            sha_count+=1
            events=torch.load(file,map_location="cpu",weights_only=True)["events"]
            context=[e for e in events if e["event"]=="decision_context"]
            final=[e for e in events if e["event"]=="final_selection"]
            decode=[e for e in events if e["event"]=="policy_action_decode"]
            scoring=[e for e in events if e["event"]=="scoring_inputs"
                     and e["values"]["scoring_scope"]["role"]=="canonical_offspring"
                     and e["values"]["scoring_scope"]["iter_idx"]==9]
            if tuple(len(x) for x in (context,final,decode,scoring))!=(1,1,1,1):
                raise ValueError("missing native canonical row or selection")
            g=context[0]["global_step"]
            key=(cell["task_id"],g)
            if key not in motion_lookup:raise ValueError(f"unpaired guided decision {key}")
            f=final[0]["values"]
            idx=int(f["selected_index"])
            s=scoring[0]["values"]
            path=s["projected_xyz"]
            if tuple(path.shape)!=(16,9,3) or not torch.equal(s["samples"],f["population"]):
                raise ValueError(f"canonical projection/population mismatch: {key}")
            target_index=f["terminal_population"]["grasp_selection"]["target_index"]
            if target_index!=0:raise ValueError(f"target index changed: {key}")
            target=s["keypoints"][target_index]
            q=f["terminal_population"]["raw_provider_quality"]
            if tuple(q.shape)!=(16,) or abs(float(q[idx])-float(f["selected_quality"]))>1e-6:
                raise ValueError(f"native provider quality mismatch: {key}")
            selected=entry_metrics(path[idx],target)
            grip=decode[0]["values"]["action_chunk"][0,:,6]
            if not bool(((grip==-1)|(grip==1)).all()):raise ValueError(f"nonbinary gripper: {key}")
            index=selected["entry_action_index"]
            selected_sign=None if index is None else int(grip[index])
            alternatives=[]
            if selected["entry_step_length_m"] is not None:
                for j in range(16):
                    if j==idx:continue
                    candidate=entry_metrics(path[j],target)
                    step=candidate["entry_step_length_m"]
                    if (step is not None
                            and step<selected["entry_step_length_m"]-1e-6
                            and float(q[j])>=float(q[idx])-SCORE_TOLERANCE-1e-6):
                        alternatives.append({"index":j,"entry_step_length_m":step,
                                             "raw_provider_quality":float(q[j]),
                                             "quality_delta_vs_selected":float(q[j])-float(q[idx])})
            shift=float(motion_lookup[key]["target_shift_m"])
            rows.append({"task_id":cell["task_id"],"episode_success":cell["success"],
                         "global_step":g,"target_shift_m":shift,"shift_ge_1cm":shift>=.01,
                         "selected_index":idx,"selected_quality":float(q[idx]),
                         "entry_action_index":index,
                         "entry_step_length_m":selected["entry_step_length_m"],
                         "start_inside_radius":selected["start_inside_radius"],
                         "projected_min_reach_m":selected["projected_min_reach_m"],
                         "gripper_sign_at_entry":selected_sign,
                         "qualifying_alternative_count":len(alternatives) if index is not None else None,
                         "best_qualifying_alternative":min(alternatives,key=lambda x:x["entry_step_length_m"]) if alternatives else None})
            del events
    if len(rows)!=33 or sha_count!=33:raise ValueError(f"expected 33 guided decisions, got {len(rows)}")
    shift=[r for r in rows if r["shift_ge_1cm"]]
    still=[r for r in rows if not r["shift_ge_1cm"]]
    result={"schema":"n7-contact-entry-audit-v1",
            "scope":"four exposed N7 Dev episodes; 33 SHA-verified guided terminal bundles; no alternative action executed",
            "source_sha256":{"dev_report":hashlib.sha256(REPORT.read_bytes()).hexdigest(),
                             "target_motion":hashlib.sha256(MOTION.read_bytes()).hexdigest()},
            "radius_m":RADIUS_M,"quality_tolerance_absolute":SCORE_TOLERANCE,
            "definition":"First projected path transition p[t-1] outside 6 cm to p[t] inside/on 6 cm of target keypoint0, t=1..8. Entry step length is ||p[t]-p[t-1]||; gripper sign is selected decoded action t-1. If no transition, entry step/sign Unknown. Structural alternate requires lower entry length and raw provider quality >= selected minus 0.02, same terminal 16.",
            "limitations":"Projected EEF path and target keypoint are model/policy inputs, not measured contact. Target tracking validity is not persisted; no unexecuted candidate success is observable. Decisions within an episode are correlated; this is no threshold sweep or causal estimate.",
            "by_shift":{"shift_ge_1cm":summary(shift),"below_1cm":summary(still)},
            "by_task":{str(t):summary([r for r in rows if r["task_id"]==t]) for t in (0,3,6,9)},
            "rows":rows}
    OUT.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print("output",OUT,"sha256",hashlib.sha256(OUT.read_bytes()).hexdigest())


if __name__=="__main__":main()
