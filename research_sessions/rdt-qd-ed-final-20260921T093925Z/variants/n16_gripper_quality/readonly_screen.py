"""SHA-verified terminal-pool availability of near-target close commands."""
import hashlib
import json
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_name("readonly_screen.json")


def main():
    result = {"schema": "n16-near-close-readonly-v1", "threshold_m": .02,
              "scope": "N11 matched Dev N7/N11 arms only; terminal candidates are unexecuted unless selected",
              "paths": []}
    for task in (0, 3, 6, 9):
        for arm in ("n7", "n11"):
            eps = list((ROOT / "artifacts/attempts").glob(f"*n11_dev_t{task:02d}_{arm}_*/eds_eval/decision_evidence/episode_000"))
            if len(eps) != 1:
                raise ValueError(f"missing path {task}/{arm}")
            rows = []
            for line in (eps[0] / "events.jsonl").open():
                ref = json.loads(line)
                if not any(e["event"] == "final_selection" for e in ref["events"]):
                    continue
                p = eps[0] / ref["bundle"]
                if hashlib.sha256(p.read_bytes()).hexdigest() != ref["sha256"]:
                    raise ValueError(f"hash mismatch {p}")
                events = torch.load(p, map_location="cpu", weights_only=True)["events"]
                final = next(e for e in events if e["event"] == "final_selection")
                v = final["values"]
                grasp = v["terminal_population"]["grasp_selection"]
                reach, positive = grasp["projected_distances_m"], grasp["positive_commands"]
                if tuple(reach.shape) != (16, 8) or tuple(positive.shape) != (16, 8):
                    raise ValueError("terminal population shape mismatch")
                near_close = ((reach <= .02) & positive).any(dim=1)
                idx = int(v["selected_index"])
                rows.append({"step": final["global_step"], "near_close_count": int(near_close.sum()),
                             "selected_near_close": bool(near_close[idx]),
                             "selected_min_reach_m": float(reach[idx].min())})
            result["paths"].append({"task": task, "arm": arm,
                                    "guided_decisions": len(rows),
                                    "available_decisions": sum(x["near_close_count"] > 0 for x in rows),
                                    "selected_decisions": sum(x["selected_near_close"] for x in rows),
                                    "available_steps": [x["step"] for x in rows if x["near_close_count"] > 0],
                                    "rows": rows})
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    for x in result["paths"]:
        print(x["task"], x["arm"], x["available_decisions"], x["selected_decisions"], x["available_steps"])


if __name__ == "__main__":
    main()
