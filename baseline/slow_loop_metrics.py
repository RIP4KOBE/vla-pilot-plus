"""A lower-triangular continual evaluation matrix; unseen cells stay null."""
from collections import defaultdict
import math


def context_identity(context):
    return tuple(context[k] for k in ("task_key", "init_state_id", "seed", "split"))


def summarize_episodes(rows, expected):
    identities = [context_identity(r["context"]) for r in rows]
    planned = [context_identity(c) for c in expected]
    if len(set(identities)) != len(identities) or identities != planned:
        raise ValueError("evaluation is incomplete, duplicated, reordered or from another context plan")
    by_task, by_variant = defaultdict(list), defaultdict(list)
    for row in rows:
        if type(row["success"]) is not bool:
            raise ValueError("success must be a recorded native boolean")
        by_task[row["context"]["task_key"]].append(int(row["success"]))
        by_variant[row["context"]["perturbation_variant"]].append(int(row["success"]))
    def counts(values):
        return {"successes": sum(values), "episodes": len(values),
                "success_rate": sum(values) / len(values)}
    tasks = {key: counts(values) for key, values in by_task.items()}
    return {"episodes": len(rows), "successes": sum(r["success"] for r in rows),
            "micro_success": sum(r["success"] for r in rows) / len(rows),
            "macro_success": sum(v["success_rate"] for v in tasks.values()) / len(tasks),
            "per_task": tasks,
            "per_task_success": {key: v["success_rate"] for key, v in tasks.items()},
            "per_variant": {key: counts(values) for key, values in by_variant.items()}}


def continual_report(order, stage_summaries, reference=None):
    n = len(order)
    if not n or len(set(order)) != n or len(stage_summaries) > n:
        raise ValueError("invalid task order or number of completed stages")
    matrix, stages = [], []
    for t, summary in enumerate(stage_summaries):
        rates = summary["per_task_success"]
        if set(rates) != set(order[:t + 1]):
            raise ValueError("each completed stage must evaluate exactly all seen tasks")
        values = [rates[key] for key in order[:t + 1]]
        if any(not math.isfinite(v) or not 0 <= v <= 1 for v in values):
            raise ValueError("invalid success rate")
        matrix.append(values + [None] * (n - len(values)))
        forgetting = {order[i]: max(matrix[k][i] for k in range(i, t + 1)) - values[i]
                      for i in range(t)}
        bwt = {order[i]: values[i] - matrix[i][i] for i in range(t)}
        stages.append({"tasks_learned": t + 1, "seen_average_success": sum(values) / len(values),
                       "current_task_success": values[-1],
                       "forgetting": sum(forgetting.values()) / t if t else None,
                       "backward_transfer": sum(bwt.values()) / t if t else None,
                       "per_task_forgetting": forgetting, "per_task_backward_transfer": bwt,
                       "per_variant": summary["per_variant"]})
    result = {"schema_version": "baseline-continual-matrix-v1", "task_order": order,
              "tasks_completed": len(matrix), "matrix": matrix,
              "unseen_cell": None, "stages": stages,
              "metric_role": "development_heldout", "evaluation_controls_training": False,
              "forgetting_definition": "mean over previous tasks of best observed post-learning success minus current success",
              "bwt_definition": "mean over previous tasks of current success minus success immediately after learning"}
    if reference is not None:
        result["v44_reference"] = [reference["per_task_success"][key] for key in order]
    if stages:
        result["latest"] = stages[-1]
    return result
