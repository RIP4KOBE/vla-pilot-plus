"""Read-only feasibility screen for a stalled near-contact QD memory gate."""
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "n14_feedback_signal"))
from readonly_audit import ATTEMPTS, read_contexts  # SHA-verifies native bundles


def main():
    rows = []
    for task in (0, 3, 6, 9):
        eps = list(ATTEMPTS.glob(f"*n11_dev_t{task:02d}_n7_*/eds_eval/decision_evidence/episode_000"))
        if len(eps) != 1:
            raise ValueError(f"missing matched N7 task {task}")
        ctx = read_contexts(eps[0])
        for step, cur in sorted(ctx.items()):
            nxt = ctx.get(step + 8)
            if not cur["guided"] or nxt is None:
                continue
            stable = cur["tracked"] and nxt["tracked"] and cur["instance_id"] == nxt["instance_id"] and cur["generation"] == nxt["generation"]
            target_shift = math.dist(cur["target"], nxt["target"]) if stable else None
            eef_shift = math.dist(cur["eef_start"], nxt["eef_start"]) if cur["eef_start"] is not None and nxt["eef_start"] is not None else None
            same_stage_guided = nxt["guided"] and cur["stage"] == nxt["stage"]
            trigger = bool(stable and same_stage_guided and cur["selected_projected_min_reach_m"] is not None
                           and cur["selected_projected_min_reach_m"] <= .06
                           and target_shift < .01 and eef_shift is not None and eef_shift >= .02)
            rows.append({"task": task, "step": step, "next_step": step + 8,
                         "stable": stable, "same_stage_guided": same_stage_guided,
                         "target_shift_m": target_shift, "eef_shift_m": eef_shift,
                         "selected_projected_min_reach_m": cur["selected_projected_min_reach_m"],
                         "trigger": trigger})
    out = {"schema": "n15-stalled-contact-readonly-screen-v1",
           "thresholds": {"projected_reach_max_m": .06, "target_motion_max_m": .01, "eef_motion_min_m": .02},
           "rows": rows,
           "trigger_count_by_task": {str(task): sum(x["trigger"] for x in rows if x["task"] == task) for task in (0, 3, 6, 9)}}
    p = HERE / "stall_screen.json"
    p.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(out["trigger_count_by_task"])
    print([(x["task"], x["step"]) for x in rows if x["trigger"]])


if __name__ == "__main__":
    main()
