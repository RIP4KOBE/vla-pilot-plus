"""Continue into new run directories; original records remain immutable."""
from pathlib import Path

from .io import read_json, write_json, digest, append_json


def source_run(path, runtime, cfg):
    root = Path(path).resolve()
    if (root / "invalid.json").exists():
        raise ValueError("cannot continue a run marked invalid")
    previous = read_json(root / "config.json")
    ignored = {"output_root", "device", "gpu_min_free_mib", "protected_gpu_indices"}
    if {k: v for k, v in previous.items() if k not in ignored} != {k: v for k, v in cfg.items() if k not in ignored}:
        raise ValueError("continuation requires identical experiment settings")
    if read_json(root / "base_identity.json")["sha256"] != runtime.identity["sha256"]:
        raise ValueError("continuation base checkpoint differs")
    return root


def jsonl(path):
    import json
    path = Path(path)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def no_update_prefix(path, runtime, cfg, protocol, output):
    """Only skip complete zero-advantage groups before the first policy update.

    Partial groups must be recollected: old runs did not persist their latent
    transitions. Their acquisition cost is retained in the cumulative budget.
    A run with any update must instead use its completed-stage checkpoint.
    """
    from .experiment import task_order, training_contexts
    from .methods.continual_rl import group_advantages
    root = source_run(path, runtime, cfg)
    training = jsonl(root / "training.jsonl")
    rollouts = jsonl(root / "rollouts.jsonl")
    if list(root.glob("stage_*/manifest.json")) or any(r.get("phase") == "grpo_update" or r.get("updates", 0) for r in training):
        raise ValueError("no-update continuation cannot restore optimized weights; use --resume checkpoint")
    groups = [r for r in training if "returns" in r]
    key = task_order(cfg, protocol)[0]
    contexts = training_contexts(cfg, protocol, [key])
    size = cfg["continual_vla_rl"]["group_size"]
    kept = []
    for number, group in enumerate(groups, 1):
        if group["stage"] != 0 or group["group"] != number or group["informative"] or float(group_advantages(group["returns"]).abs().sum()):
            raise ValueError("source is not a contiguous zero-advantage prefix")
        rows = [r for r in rollouts if r["stage"] == 0 and r["group"] == number]
        if len(rows) != size or [r["member"] for r in rows] != list(range(size)):
            raise ValueError("completed group has missing or duplicate episodes")
        base = contexts[(number - 1) % len(contexts)]
        for member, row in enumerate(rows):
            expected_seed = (base.get("policy_seed", base["seed"]) + (number - 1) * 1009 + member) % (2**63 - 1)
            context = row["context"]
            if (context["task_key"], str(context["init_state_id"]), context["seed"], context["policy_seed"]) != (key, str(base["init_state_id"]), base["seed"], expected_seed):
                raise ValueError("source group does not match the paired experiment plan")
        if [float(r["success"]) for r in rows] != group["returns"]:
            raise ValueError("group rewards differ from its episodes")
        kept.extend(rows)
    for row in kept:
        append_json(output / "rollouts.jsonl", row)
    for row in groups:
        append_json(output / "training.jsonl", row)
    report = {"kind": "zero-update-prefix", "source": str(root), "completed_groups_reused": len(groups),
              "episodes_reused": len(kept), "discarded_partial_group_episodes": len(rollouts) - len(kept),
              "prior_environment_steps": sum(r["steps"] for r in rollouts),
              "source_hashes": {name: digest(root / name) for name in ("training.jsonl", "rollouts.jsonl") if (root / name).exists()}}
    write_json(output / "continuation.json", report)
    return len(groups), report["prior_environment_steps"]
