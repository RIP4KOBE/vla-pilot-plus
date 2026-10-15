#!/usr/bin/env python3
"""One-chunk feedback-conditioned QD-parent tabu feasibility, exposed N7 Dev only."""
from __future__ import annotations

import collections
import hashlib
import json
from pathlib import Path

import torch

HERE=Path(__file__).resolve().parent
ART=HERE.parents[1]/"artifacts"
MOTION=HERE/"target-motion-audit-v1.json"
LINEAGE=HERE/"lineage-audit-v1.json"
REPORT=ART/"continuation_20260925/n7-dev-v1/full-dev-report-v1.json"
OUT=HERE/"one-chunk-tabu-feasibility-v2.json"


def read_native(entry,folder):
    file=folder/entry["bundle"]
    if hashlib.sha256(file.read_bytes()).hexdigest()!=entry["sha256"]:
        raise ValueError(f"SHA mismatch: {file}")
    return torch.load(file,map_location="cpu",weights_only=True)["events"]


def sole(events,name):
    x=[e for e in events if e["event"]==name]
    if len(x)!=1:raise ValueError(f"{name}: {len(x)}")
    return x[0]


def main():
    if OUT.exists():raise SystemExit(f"immutable result exists: {OUT}")
    motion=json.loads(MOTION.read_text())
    lineage=json.loads(LINEAGE.read_text())
    lin={(r["task_id"],r["global_step"]):r for r in lineage["rows"]}
    report=json.loads(REPORT.read_text())
    rows=[]; hash_count=0
    for cell in report["cells"]:
        task=cell["task_id"]
        folder=ART/"attempts"/cell["accepted_attempt_id"]/"eds_eval/decision_evidence/episode_000"
        contexts={}
        for line in (folder/"events.jsonl").open():
            entry=json.loads(line)
            for meta in entry["events"]:
                if meta["event"]=="decision_context":contexts[meta["global_step"]]=entry
        for m in motion["rows"]:
            if m["task_id"]!=task or m["target_shift_m"]<.01:continue
            g=m["global_step"]
            n=g+8
            if n not in contexts:raise ValueError(f"task {task} g{g}: no adjacent decision")
            current=read_native(contexts[g],folder);hash_count+=1
            following=read_native(contexts[n],folder);hash_count+=1
            curr_ctx=sole(current,"decision_context")
            next_ctx=sole(following,"decision_context")
            if curr_ctx["global_step"]!=g or next_ctx["global_step"]!=n:
                raise ValueError("global step mismatch")
            old_final=sole(current,"final_selection")["values"]
            old_target=old_final["terminal_population"]["grasp_selection"]["target_index"]
            if old_target!=0 or old_final["selected_cell"]!=lin[(task,g)]["selected_child_cell"]:
                raise ValueError("prior selected cell/target mismatch")
            same_context_chain=(
                next_ctx["values"]["previous_decision_id"]==curr_ctx["decision_id"]
                and next_ctx["episode"]==curr_ctx["episode"]
                and next_ctx["reset_sequence"]==curr_ctx["reset_sequence"]
            )
            same_stage=next_ctx["values"]["stage"]==curr_ctx["values"]["stage"]
            same_keypoint_count=(
                next_ctx["values"]["keypoints"].shape==curr_ctx["values"]["keypoints"].shape
            )
            same_target_source=(
                next_ctx["values"]["target_observation"]==curr_ctx["values"]["target_observation"]
            )
            next_guided=any(e["event"]=="final_selection" for e in following)
            next_target=None;slots=None;alternates=None;cell_counts=None;bounds_changed=None
            old_height_interval=None;new_height_interval=None;height_interval_overlap_m=None
            if next_guided:
                next_final=sole(following,"final_selection")["values"]
                next_target=next_final["terminal_population"]["grasp_selection"]["target_index"]
                allocation=[e["values"] for e in following if e["event"]=="archive_parent_allocation"
                            and e["values"]["iter_idx"]==0]
                if len(allocation)!=1:raise ValueError(f"task {task} g{n}: missing iter0 allocation")
                parent_cells=allocation[0]["parent_cell_ids"].tolist()
                if len(parent_cells)!=16:raise ValueError("parent allocation changed")
                prior_cell=int(old_final["selected_cell"])
                slots=parent_cells.count(prior_cell)
                alternates=len(set(parent_cells)-{prior_cell})
                cell_counts=dict(sorted(collections.Counter(parent_cells).items()))
                old_assign=[e["values"] for e in current if e["event"]=="qd_descriptor_assignment"
                            and e["values"]["iter_idx"]==9]
                new_assign=[e["values"] for e in following if e["event"]=="qd_descriptor_assignment"
                            and e["values"]["iter_idx"]==-1]
                if (len(old_assign),len(new_assign))!=(1,1):raise ValueError("missing QD bounds")
                bounds_changed=(
                    not torch.equal(old_assign[0]["bounds_lo"],new_assign[0]["bounds_lo"])
                    or not torch.equal(old_assign[0]["bounds_hi"],new_assign[0]["bounds_hi"])
                )
                height_bin=prior_cell//4
                def interval(assignment):
                    lo=float(assignment["bounds_lo"][1]);hi=float(assignment["bounds_hi"][1])
                    width=(hi-lo)/4
                    return [lo+height_bin*width,lo+(height_bin+1)*width]
                old_height_interval=interval(old_assign[0])
                new_height_interval=interval(new_assign[0])
                height_interval_overlap_m=max(0.0,min(old_height_interval[1],new_height_interval[1])
                                              -max(old_height_interval[0],new_height_interval[0]))
            conditional_eligible=bool(next_guided and same_context_chain and same_stage and same_keypoint_count
                                      and same_target_source and next_target==old_target)
            rows.append({"task_id":task,"episode_success":cell["success"],
                         "perturbing_global_step":g,"next_global_step":n,
                         "target_shift_m":m["target_shift_m"],
                         "prior_selected_cell":int(old_final["selected_cell"]),
                         "next_guided":next_guided,"same_stage":same_stage,
                         "same_context_chain":same_context_chain,
                         "same_keypoint_count":same_keypoint_count,
                         "same_target_source":same_target_source,
                         "prior_target_index":old_target,"next_target_index":next_target,
                         "tracker_identity_native_recorded":False,
                         "conditional_eligible":conditional_eligible,
                         "same_numeric_cell_parent_slots":slots,
                         "alternative_allocated_cells":alternates,
                         "iter0_parent_cell_slot_counts":cell_counts,
                         "decision_local_descriptor_bounds_changed":bounds_changed,
                         "prior_numeric_cell_height_interval_m":old_height_interval,
                         "next_numeric_cell_height_interval_m":new_height_interval,
                         "numeric_cell_height_interval_overlap_m":height_interval_overlap_m})
            del current,following
    if len(rows)!=7 or hash_count!=14:raise ValueError("expected seven perturbing chunks")
    elig=[r for r in rows if r["conditional_eligible"]]
    result={"schema":"n7-one-chunk-tabu-feasibility-v2",
            "scope":"four already-exposed N7 Dev episodes; read-only; one immediate 8-action chunk only",
            "sources_sha256":{"motion":hashlib.sha256(MOTION.read_bytes()).hexdigest(),
                              "lineage":hashlib.sha256(LINEAGE.read_bytes()).hexdigest(),
                              "dev_report":hashlib.sha256(REPORT.read_bytes()).hexdigest()},
            "native_bundles_sha_verified":hash_count,
            "triggered_perturbing_chunks":len(rows),
            "conditional_next_guided_same_stage_target":len(elig),
            "eligible_with_matching_numeric_cell_slots":sum(r["same_numeric_cell_parent_slots"]>0 for r in elig),
            "nominal_matching_slots_reallocatable":sum(r["same_numeric_cell_parent_slots"] for r in elig),
            "nominal_matching_slots_with_height_interval_overlap":sum(
                r["same_numeric_cell_parent_slots"] for r in elig
                if r["numeric_cell_height_interval_overlap_m"]>0),
            "all_eligible_have_alternative_cells":all(r["alternative_allocated_cells"]>0 for r in elig),
            "same_stage_success_episode_trigger_count":sum(r["episode_success"] for r in rows),
            "native_attested_tracker_identity_eligible_count":0,
            "limitations":{
                "tracker_identity":"No tracker instance/generation or per-keypoint validity in decision_context; same-episode continuity and main.py's one register_keypoints call support, but do not natively attest, a stable tracker. A runtime tabu needs to read the existing passive tracking snapshot and fail closed on invalid/mismatched identity.",
                "cell_identity":"N7's 4x4 descriptor uses per-decision fixed-initial quantile height bounds. The same numeric cell ID can represent different physical height intervals in adjacent decisions. Counts are nominal slots, not proof that suppressing that ID targets the same geometric behavior.",
                "counterfactual":"No alternate parent allocation or task outcome was executed. Replacement among observed alternative cells is combinatorially possible, but the resulting offspring or success is unknown."
            },"rows":rows}
    OUT.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print("output",OUT,"sha256",hashlib.sha256(OUT.read_bytes()).hexdigest())


if __name__=="__main__":main()
