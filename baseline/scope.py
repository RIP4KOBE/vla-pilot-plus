"""Versioned task subsets without changing the parent protocol or its seeds."""
import hashlib
import json
from pathlib import Path

from .io import read_json


def selected_tasks(cfg, protocol):
    if not cfg.get("task_selection"):
        return None
    value = read_json(cfg["task_selection"])
    unsigned = {k: v for k, v in value.items() if k != "selection_sha256"}
    actual = hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if actual != value.get("selection_sha256") or value.get("parent_protocol_sha256") != protocol.digest:
        raise ValueError("task selection checksum or parent protocol mismatch")
    if value.get("experiment_id") != cfg.get("experiment_id"):
        raise ValueError("task selection belongs to a different experiment")
    keys = value["task_keys"]
    if not keys or len(keys) != len(set(keys)) or not set(keys) <= set(protocol.tasks):
        raise ValueError("invalid selected task keys")
    variants = value.get("perturbation_variants", [])
    if any(protocol.tasks[k]["perturbation_variant"] not in variants for k in keys):
        raise ValueError("task outside the selected perturbations")
    return keys


def scope_identity(cfg):
    return {"experiment_id": cfg.get("experiment_id"),
            "selection_sha256": read_json(cfg["task_selection"])["selection_sha256"] if cfg.get("task_selection") else None}


def check_input_root(path, cfg):
    """New experiments may resume their own work, never retired baseline runs."""
    if cfg.get("fresh_baseline_inputs"):
        root = Path(cfg["output_root"]).resolve()
        if not Path(path).resolve().is_relative_to(root):
            raise ValueError("fresh experiment refuses artifacts/data from another baseline output root")


def check_task_keys(keys, cfg, protocol):
    selected = selected_tasks(cfg, protocol)
    if selected is not None and not set(keys) <= set(selected):
        raise ValueError("task is outside this experiment's frozen subset")
