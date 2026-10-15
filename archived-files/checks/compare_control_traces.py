"""Read-only paired trace diagnostics after complete low/ultra cohort audits.

Compare exact recorded action prefixes and same-image categorical observations.
This local evidence is descriptive; online history and responses may differ.
"""
import argparse
import hashlib
import json
from pathlib import Path

MODES = ("eds", "vls", "eds_qd")
LOW_SHA = "a67ee5e13f7563b86ea8fadd9e55dd5d5b80f53601cdd1e65f1af72a2c2402eb"
OBS_FIELDS = ("grasp", "support", "target_location", "target_visibility")
CONTROL_FIELDS = (
    "stage_after", "guidance_after", "contact_phase", "stage_decision_reason",
    "guidance_gate_reason", "visual_hold", "completion_confirmed",
)


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def observation(row):
    value = row.get("observation")
    return {key: value.get(key) for key in OBS_FIELDS} if isinstance(value, dict) else None


def control(row):
    return {key: row.get(key) for key in CONTROL_FIELDS}


def compare(low_path, ultra_path):
    if sha(low_path) != LOW_SHA:
        raise ValueError("Sealed low report changed")
    low, ultra = read(low_path), read(ultra_path)
    if not low["all_cohorts_valid"] or not ultra["all_cohorts_valid"]:
        raise ValueError("Full valid cohorts required")
    result = {
        "schema": "steering_paired_control_trace_diagnostic_v1",
        "low_report_sha256": sha(low_path), "ultra_report_sha256": sha(ultra_path),
        "limits": [
            "Exact action equality is a recorded trace comparison, not proof of identical unlogged internal state.",
            "Same raw image does not imply identical full prompt: identity and prior online answers may differ.",
            "A differing visual judgement is not labelled correct without independent visual/physical review.",
            "Reward probe agreement checks the fixed contract on probes, not universal mathematical equivalence.",
        ],
        "modes": {},
    }
    for mode in MODES:
        lr, ur = low["runs"][mode], ultra["runs"][mode]
        if not lr["accepted"] or not ur["accepted"]:
            raise ValueError("Unaccepted cohort")
        sources = [Path(r["run_dir"]) / "output" for r in (lr, ur)]
        action_rows = [rows(p / "evaluation/safety_events.jsonl") for p in sources]
        stage_rows = [rows(p / "evaluation/stage_events.jsonl") for p in sources]
        tasks = []
        for i, (lt, ut) in enumerate(zip(lr["tasks"], ur["tasks"])):
            assert (lt["task_id"], lt["seed"]) == (ut["task_id"], ut["seed"])
            task = lt["task_id"]
            actions = [[r for r in rr if r.get("event") == "stage_grasp_guard_action"
                        and r.get("task_id") == task] for rr in action_rows]
            for aa in actions:
                assert [a["global_step"] for a in aa] == list(range(len(aa)))
            first_diff = next((n for n, (a, b) in enumerate(zip(*actions))
                               if a["executed_action"] != b["executed_action"]), None)
            common = min(map(len, actions))
            exact_prefix = common if first_diff is None else first_diff
            stage_maps = [{r["global_step"]: r for r in rr if r.get("task_id") == task}
                          for rr in stage_rows]
            paired_observations = []
            differing_controls = []
            for step in sorted(set(stage_maps[0]) & set(stage_maps[1])):
                if step > exact_prefix:
                    break
                a, b = [d[step] for d in stage_maps]
                if control(a) != control(b):
                    differing_controls.append({"step": step, "low": control(a), "ultra": control(b)})
                am, bm = a.get("current_target_marker"), b.get("current_target_marker")
                if not isinstance(am, dict) or not isinstance(bm, dict):
                    continue
                raw_a, raw_b = am.get("raw_rgb_sha256"), bm.get("raw_rgb_sha256")
                if raw_a and raw_a == raw_b and observation(a) is not None and observation(b) is not None:
                    paired_observations.append({
                        "step": step, "same_raw_image_sha256": raw_a,
                        "marked_image_equal": am.get("marked_rgb_sha256") == bm.get("marked_rgb_sha256"),
                        "low": observation(a), "ultra": observation(b),
                        "categorical_equal": observation(a) == observation(b),
                        "low_control": control(a), "ultra_control": control(b),
                        "low_frame": am.get("raw_png_path"), "ultra_frame": bm.get("raw_png_path"),
                    })
            reward = []
            for p in sources:
                rpath = p / f"episode_{i+1}/vlm_agent/target_distance_reward.json"
                evidence = read(rpath)
                reward.append({"path": str(rpath), "sha256": sha(rpath), "valid": evidence["valid"],
                               "probe_count": evidence["probe_count"],
                               "max_absolute_difference": evidence["max_absolute_difference"]})
            tasks.append({
                "task_id": task, "seed": lt["seed"], "low_success": lt["success"], "ultra_success": ut["success"],
                "low_actions": len(actions[0]), "ultra_actions": len(actions[1]),
                "exact_action_prefix_rows": exact_prefix,
                "first_differing_executed_action_step": first_diff,
                "prefix_covers_both_complete_traces": first_diff is None and len(actions[0]) == len(actions[1]),
                "same_image_observations_before_or_at_first_action_difference": paired_observations,
                "control_differences_before_or_at_first_action_difference": differing_controls,
                "low_reward_contract": reward[0], "ultra_reward_contract": reward[1],
                "reward_source_bytes_equal": {
                    name: (sources[0] / f"episode_{i+1}/vlm_agent/{name}").read_bytes()
                    == (sources[1] / f"episode_{i+1}/vlm_agent/{name}").read_bytes()
                    for name in ("stage1_guidance.txt", "stage2_guidance.txt")
                },
            })
        assert len(tasks) == 10
        result["modes"][mode] = tasks
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--low", type=Path, required=True)
    parser.add_argument("--ultra", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Preserve previous diagnostics")
    result = compare(args.low, args.ultra)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({mode: {"tasks": len(ts), "identical_complete_actions": sum(t["prefix_covers_both_complete_traces"] for t in ts),
                            "tasks_with_same_image_judgement_change_before_actions_diverge": sum(any(not o["categorical_equal"] for o in t["same_image_observations_before_or_at_first_action_difference"]) for t in ts)}
                      for mode, ts in result["modes"].items()}))
