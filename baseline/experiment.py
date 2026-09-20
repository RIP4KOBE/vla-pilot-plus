"""Read a frozen copy of the main online plan; never write to the live run."""
from .io import read_json
from .protocol import TRAIN_SPLIT


def main_contexts(cfg, protocol):
    if not cfg["experiment_plan"]:
        raise ValueError("main_online requires a frozen experiment_plan")
    plan = read_json(cfg["experiment_plan"])
    if plan["manifest_sha256"] != protocol.digest or plan["task_count"] != 40:
        raise ValueError("main plan belongs to another benchmark protocol")
    contexts = []
    seen = set()
    for row in plan["contexts"]:
        task = protocol.tasks[row["task_key"]]
        if row["source_split"] != TRAIN_SPLIT or str(row["init_state_id"]) not in task["splits"][TRAIN_SPLIT]:
            raise ValueError("online plan includes non-training or sealed states")
        if row["context_id"] in seen:
            raise ValueError("duplicate online context")
        seen.add(row["context_id"])
        for key in ("runtime_suite", "task_id", "task_index", "perturbation_variant"):
            if str(row[key]) != str(task[key]):
                raise ValueError(f"main plan context differs from protocol: {key}")
        contexts.append({**row, "seed": row["env_seed"], "split": TRAIN_SPLIT})
    if {c["task_key"] for c in contexts} != set(protocol.tasks):
        raise ValueError("main plan must contain all forty task cells")
    return contexts


def task_order(cfg, protocol):
    from .scope import selected_tasks
    selected = selected_tasks(cfg, protocol)
    if selected is not None:
        return selected
    if cfg["experiment_plan"]:
        return list(dict.fromkeys(c["task_key"] for c in main_contexts(cfg, protocol)))
    return protocol.order(cfg["seed"])


def training_contexts(cfg, protocol, keys):
    from .scope import check_task_keys
    check_task_keys(keys, cfg, protocol)
    rows = protocol.contexts(TRAIN_SPLIT, cfg["seed"], keys)
    if cfg["experiment_plan"]:
        paired = {(r["task_key"], str(r["init_state_id"])): r for r in main_contexts(cfg, protocol)}
        rows = [{**r, **paired.get((r["task_key"], str(r["init_state_id"])), {})} for r in rows]
    return rows
