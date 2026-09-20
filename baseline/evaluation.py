"""Paired development episodes and continual success-matrix summaries."""
from collections import defaultdict
import math

from .artifacts import make_method, load_stage
from .io import append_json, write_json
from .rollout import episode


def evaluate(runtime, cfg, protocol, output, *, artifact=None, split="fixed_development_probe", limit=None, task_keys=None):
    from .experiment import task_order
    from .scope import check_task_keys, scope_identity
    task_keys = task_keys or task_order(cfg, protocol)
    check_task_keys(task_keys, cfg, protocol)
    method = None
    if artifact:
        method = make_method(runtime, cfg)
        load_stage(artifact, runtime, protocol, method, cfg)
    if split == "main_online":
        from .experiment import main_contexts
        contexts = [c for c in main_contexts(cfg, protocol) if not task_keys or c["task_key"] in task_keys]
    else:
        contexts = protocol.contexts(split, cfg["seed"], task_keys)
    if limit is not None:
        contexts = contexts[:limit]
    results = []
    for context in contexts:
        summary, _ = episode(runtime, cfg, context, method=method)
        results.append(summary)
        append_json(output / "episodes.jsonl", summary)
        print(f"evaluate {len(results)}/{len(contexts)} success={summary['success']} {context['task_key']}", flush=True)
    per_task = defaultdict(list)
    for row in results:
        per_task[row["context"]["task_key"]].append(int(row["success"]))
    rates = {key: sum(values) / len(values) for key, values in per_task.items()}
    summary = {"schema_version": "baseline-evaluation-v1", "method": cfg["method"] if artifact else "pi05_v44",
               "artifact": str(artifact) if artifact else None, "protocol_sha256": protocol.digest,
               "base": runtime.identity, "split": split, "seed": cfg["seed"], "episodes": len(results),
               "metric_role": "online_pool_not_heldout" if split == "main_online" else "development_heldout",
               "micro_success": sum(r["success"] for r in results) / max(len(results), 1),
               "macro_success": sum(rates.values()) / max(len(rates), 1), "per_task_success": rates,
               "environment_steps": sum(r["steps"] for r in results), "seconds": sum(r["seconds"] for r in results),
               "interventions": sum(r["interventions"] for r in results),
               "partial_development_check": limit is not None, "experiment_scope": scope_identity(cfg)}
    write_json(output / "summary.json", summary)
    return summary


def continual_metrics(matrix):
    """R[t][i] = success on task i after learning task t; fractions, not percent."""
    if not matrix or any(len(row) != len(matrix) for row in matrix):
        raise ValueError("expected a square stage x task success matrix")
    if any(not math.isfinite(x) or not 0 <= x <= 1 for row in matrix for x in row):
        raise ValueError("success rates must be finite fractions in [0,1]")
    n = len(matrix)
    final = sum(matrix[-1]) / n
    forgetting = sum(max(matrix[t][i] for t in range(i, n)) - matrix[-1][i] for i in range(n - 1)) / max(n - 1, 1)
    bwt = sum(matrix[-1][i] - matrix[i][i] for i in range(n - 1)) / max(n - 1, 1)
    seen_curve = [sum(row[:t + 1]) / (t + 1) for t, row in enumerate(matrix)]
    return {"final_average_success": final, "forgetting": forgetting, "backward_transfer": bwt,
            "mean_seen_success_over_stages": sum(seen_curve) / n, "seen_curve": seen_curve}
