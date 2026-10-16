"""Combine fresh collection shards for the selected task protocol."""
from pathlib import Path

from .experiment import task_order
from .io import read_json, write_json
from .scope import scope_identity, check_input_root


def merged_bank(paths, destination, cfg, protocol):
    """Combine only newly collected task shards, preserving roles and lineage."""
    entries, seen, base = [], set(), None
    for path in paths:
        check_input_root(path, cfg)
        value = read_json(Path(path) / "rollouts.json")
        if value.get("experiment_scope") != scope_identity(cfg) or value["protocol_sha256"] != protocol.digest:
            raise ValueError("collection shard has a different experiment scope")
        if value["discount"] != cfg["rl2_vla"]["discount"] or value["execution_horizon"] != cfg["execution_horizon"]:
            raise ValueError("collection shard has different action/reward settings")
        if base is not None and value["base"] != base:
            raise ValueError("collection shard has a different v44 base")
        base = value["base"]
        for entry in value["entries"]:
            check_input_root(entry["path"], cfg)
            if entry["sha256"] in seen:
                raise ValueError("duplicate offline trajectory")
            seen.add(entry["sha256"])
            entries.append(entry)
    if {e["task_key"] for e in entries} != set(task_order(cfg, protocol)):
        raise ValueError("offline bank does not cover exactly the selected tasks")
    write_json(destination, {"schema_version": "baseline-offline-rollouts-v1", "base": base,
                            "protocol_sha256": protocol.digest, "experiment_scope": scope_identity(cfg),
                            "execution_horizon": cfg["execution_horizon"], "discount": cfg["rl2_vla"]["discount"],
                            "entries": entries, "source_shards": [str(p) for p in paths]})

